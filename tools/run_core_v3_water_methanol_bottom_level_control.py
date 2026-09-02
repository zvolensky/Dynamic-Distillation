#!/usr/bin/env python
"""Run the water-methanol partial-reboiler case with bottom-sump PI control."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import core_v3_water_methanol_vtpr_dynamic_support as support  # noqa: E402
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.vapor_holdup_bottom_level_control_v1 import (  # noqa: E402
    BottomLevelControllerSpecification,
    audit_vapor_holdup_bottom_level_control_contract,
    bottom_level_control_bounds,
    bottom_level_control_initial_coordinates,
    bottom_level_control_pattern,
    build_vapor_holdup_bottom_level_control_contract,
    evaluate_vapor_holdup_bottom_level_control_residual,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    terminal_geometry_from_specs,
    terminal_level_fractions,
)


TIMESTEP_SEC = 0.5
KC = 24.0
TI_SEC = 365.0
RESIDUAL_LIMIT = 1.0e-8
COMPONENT_LIMIT_LBMOL = 1.0e-6
ENERGY_ABSOLUTE_LIMIT_BTU = 1.0e-4
ENERGY_RELATIVE_LIMIT = 1.0e-8
MAX_NFEV = 40


def _stack(values: list[np.ndarray]) -> np.ndarray:
    return np.stack(values)


def execute(
    *,
    duration_sec: float,
    bottoms_bias_multiplier: float = 1.0,
    bottoms_bias_duration_sec: float = 0.0,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if duration_sec <= 0.0 or not np.isclose(
        duration_sec / TIMESTEP_SEC, round(duration_sec / TIMESTEP_SEC)
    ):
        raise ValueError("duration must be a positive multiple of 0.5 seconds")
    if not np.isfinite(bottoms_bias_multiplier) or bottoms_bias_multiplier <= 0.0:
        raise ValueError("bottoms bias multiplier must be positive and finite")
    if (
        not np.isfinite(bottoms_bias_duration_sec)
        or bottoms_bias_duration_sec < 0.0
        or bottoms_bias_duration_sec > duration_sec
        or not np.isclose(
            bottoms_bias_duration_sec / TIMESTEP_SEC,
            round(bottoms_bias_duration_sec / TIMESTEP_SEC),
        )
    ):
        raise ValueError("bottoms bias duration must be a timestep-aligned part of the run")

    started = time.perf_counter()
    step_count = int(round(duration_sec / TIMESTEP_SEC))
    case = support.load_partial_hydraulic_case()
    workbook_case = support.starting_state.load_case_from_excel(
        str(case.problem["workbook"])
    )
    terminal_geometry = terminal_geometry_from_specs(workbook_case.specs)
    initial = case.post_pulse_reference
    initial_audit = ProviderCallAudit(**case.problem["provider_audit_kwargs"])
    initial_properties = evaluate_vapor_holdup_trial_properties(
        case.problem["geometry"],
        initial.liquid_component_inventory_lbmol,
        initial.vapor_component_inventory_lbmol,
        initial.temperature_F,
        initial.pressure_psia,
        case.provider,
        initial_audit,
        state_id="water_methanol:bottom_level_control:initial_level",
        evaluation_kind="residual",
    )
    initial_levels = terminal_level_fractions(
        initial.liquid_component_inventory_lbmol,
        initial_properties.liquid_density_lbmol_ft3,
        terminal_geometry,
    )
    controller = BottomLevelControllerSpecification(
        setpoint_fraction=float(initial_levels[1]),
        kc=KC,
        ti_sec=TI_SEC,
    )
    contract = build_vapor_holdup_bottom_level_control_contract(
        case.contract,
        geometry=terminal_geometry,
        controller=controller,
    )
    structural = audit_vapor_holdup_bottom_level_control_contract(contract)
    if not structural["pass_gate"]:
        raise RuntimeError("bottom-level control structural contract failed")
    pattern = bottom_level_control_pattern(contract)
    lower, upper = bottom_level_control_bounds(contract)

    reference = initial
    previous_coordinates: np.ndarray | None = None
    controller_memory = 0.0
    controller_rate = 0.0
    bottoms_log = 0.0
    steps: list[dict[str, Any]] = []
    provider_reports: list[dict[str, Any]] = []
    expected_component = np.zeros(len(case.contract.component_names), dtype=float)
    expected_energy = 0.0
    times = [0.0]
    coordinates: list[np.ndarray] = []
    liquid = [initial.liquid_component_inventory_lbmol.copy()]
    vapor = [initial.vapor_component_inventory_lbmol.copy()]
    transfer = [initial.phase_transfer_lbmolph.copy()]
    temperature = [initial.temperature_F.copy()]
    pressure = [initial.pressure_psia.copy()]
    liquid_flow = [initial.hydraulic_liquid_flow_lbmolph.copy()]
    vapor_flow = [initial.vapor_flow_lbmolph.copy()]
    duty = [float(initial.condenser_duty_BTUph)]
    energy = [initial.total_stored_energy_BTU.copy()]
    distillate = [float(case.base_inputs.distillate_lbmolph)]
    bottoms = [float(case.base_inputs.bottoms_lbmolph)]
    bottoms_command = [float(case.base_inputs.bottoms_lbmolph)]
    actuator_multipliers = [1.0]
    top_levels = [float(initial_levels[0])]
    bottom_levels = [float(initial_levels[1])]
    controller_memories = [controller_memory]
    controller_rates = [controller_rate]

    for index in range(1, step_count + 1):
        step_time_sec = index * TIMESTEP_SEC
        actuator_multiplier = (
            float(bottoms_bias_multiplier)
            if step_time_sec <= float(bottoms_bias_duration_sec) + 1.0e-12
            else 1.0
        )
        numerical = support.numerical_spec(
            case.problem,
            timestep_sec=TIMESTEP_SEC,
            top_pressure_psia=float(initial.pressure_psia[0]),
        )
        audit = ProviderCallAudit(**case.problem["provider_audit_kwargs"])
        if hasattr(case.provider, "set_exact_state_memoization"):
            case.provider.set_exact_state_memoization(True, clear=True)
        counters = {"function": 0, "jacobian": 0}

        def objective(candidate: np.ndarray, state_id: str = "solver") -> np.ndarray:
            counters["function"] += 1
            return evaluate_vapor_holdup_bottom_level_control_residual(
                contract,
                case.problem["geometry"],
                reference,
                case.base_inputs,
                case.problem["spec"].hydraulic_geometry,
                numerical,
                case.provider,
                audit,
                candidate,
                controller_memory_previous=controller_memory,
                bottoms_actuator_multiplier=actuator_multiplier,
                state_id=(
                    f"water_methanol:bottom_level_control:step={index}:"
                    f"{state_id}:{counters['function']}"
                ),
                evaluation_kind="jacobian",
            ).scaled

        def jacobian(candidate: np.ndarray) -> np.ndarray:
            counters["jacobian"] += 1
            matrix, _groups = support.colored_central_difference_jacobian(
                objective,
                candidate,
                pattern=pattern,
                step=support.DIFFERENCE_STEP,
                state_id=(
                    f"water_methanol:bottom_level_control:step={index}:"
                    f"jacobian={counters['jacobian']}"
                ),
            )
            return matrix

        point = bottom_level_control_initial_coordinates(
            contract,
            controller_rate_per_sec=controller_rate,
            timestep_sec=TIMESTEP_SEC,
            previous_coordinates=previous_coordinates,
            bottoms_log_ratio_previous=bottoms_log,
        )
        solution = least_squares(
            objective,
            point,
            jac=jacobian,
            bounds=(lower, upper),
            method="trf",
            x_scale=1.0,
            ftol=1.0e-9,
            xtol=1.0e-9,
            gtol=1.0e-9,
            max_nfev=MAX_NFEV,
            verbose=0,
        )
        evaluation = evaluate_vapor_holdup_bottom_level_control_residual(
            contract,
            case.problem["geometry"],
            reference,
            case.base_inputs,
            case.problem["spec"].hydraulic_geometry,
            numerical,
            case.provider,
            audit,
            solution.x,
            controller_memory_previous=controller_memory,
            bottoms_actuator_multiplier=actuator_multiplier,
            state_id=f"water_methanol:bottom_level_control:step={index}:final",
            evaluation_kind="residual",
        )
        base = evaluation.base
        endpoint = base.endpoint
        actual_component_step = np.sum(
            endpoint.liquid_component_inventory_lbmol
            + endpoint.vapor_component_inventory_lbmol
            - reference.liquid_component_inventory_lbmol
            - reference.vapor_component_inventory_lbmol,
            axis=0,
        )
        expected_component_step = (
            base.transport.external_component_rate_lbmolph
            * TIMESTEP_SEC
            / 3600.0
        )
        component_error = float(
            np.max(np.abs(actual_component_step - expected_component_step))
        )
        actual_energy_step = float(
            np.sum(base.properties.total_stored_energy_BTU - reference.total_stored_energy_BTU)
        )
        expected_energy_step = float(
            base.transport.external_energy_rate_BTUph * TIMESTEP_SEC / 3600.0
        )
        energy_error_abs = abs(actual_energy_step - expected_energy_step)
        energy_error_rel = energy_error_abs / max(
            abs(actual_energy_step), abs(expected_energy_step), 1.0
        )
        residual_norm = float(np.max(np.abs(evaluation.scaled)))
        minimum_bound_distance = float(
            np.min(np.minimum(solution.x - lower, upper - solution.x))
        )
        provider_report = support.compact_provider_report(audit.report())
        gates = {
            "solver": bool(solution.success),
            "residual": residual_norm < RESIDUAL_LIMIT,
            "bounds": minimum_bound_distance > 1.0e-6,
            "component_identity": component_error < COMPONENT_LIMIT_LBMOL,
            "energy_identity": bool(
                energy_error_rel < ENERGY_RELATIVE_LIMIT
                or energy_error_abs < ENERGY_ABSOLUTE_LIMIT_BTU
            ),
            "physical": support._physical(base),
            "provider": bool(provider_report["pass"] and not audit.fallback_attempted),
        }
        gates = {key: bool(value) for key, value in gates.items()}
        row = {
            "step_index": index,
            "time_sec": step_time_sec,
            "solver_success": bool(solution.success),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "scaled_residual_inf_norm": residual_norm,
            "controller_residual_inf_norm": float(np.max(np.abs(evaluation.scaled[-2:]))),
            "component_identity_error_lbmol": component_error,
            "energy_identity_absolute_error_BTU": energy_error_abs,
            "minimum_bound_distance": minimum_bound_distance,
            "bottoms_lbmolph": evaluation.bottoms_lbmolph,
            "bottoms_command_lbmolph": evaluation.bottoms_command_lbmolph,
            "bottoms_actuator_multiplier": actuator_multiplier,
            "bottoms_bias_active": not np.isclose(actuator_multiplier, 1.0),
            "bottom_level_fraction": float(evaluation.level_fraction[1]),
            "bottom_level_error": evaluation.bottom_level_error,
            "controller_rate_per_sec": evaluation.controller_rate_per_sec,
            "controller_memory": evaluation.controller_memory_endpoint,
            "gates": gates,
            "pass_gate": all(gates.values()),
        }
        steps.append(row)
        provider_reports.append(provider_report)
        expected_component += expected_component_step
        expected_energy += expected_energy_step
        times.append(step_time_sec)
        coordinates.append(solution.x.copy())
        liquid.append(endpoint.liquid_component_inventory_lbmol.copy())
        vapor.append(endpoint.vapor_component_inventory_lbmol.copy())
        transfer.append(endpoint.phase_transfer_lbmolph.copy())
        temperature.append(endpoint.temperature_F.copy())
        pressure.append(endpoint.pressure_psia.copy())
        liquid_flow.append(endpoint.hydraulic_liquid_flow_lbmolph.copy())
        vapor_flow.append(endpoint.vapor_flow_lbmolph.copy())
        duty.append(float(endpoint.condenser_duty_BTUph))
        energy.append(base.properties.total_stored_energy_BTU.copy())
        distillate.append(float(evaluation.distillate_lbmolph))
        bottoms.append(float(evaluation.bottoms_lbmolph))
        bottoms_command.append(float(evaluation.bottoms_command_lbmolph))
        actuator_multipliers.append(actuator_multiplier)
        top_levels.append(float(evaluation.level_fraction[0]))
        bottom_levels.append(float(evaluation.level_fraction[1]))
        controller_memories.append(float(evaluation.controller_memory_endpoint))
        controller_rates.append(float(evaluation.controller_rate_per_sec))
        if index % 20 == 0 or index == step_count or not row["pass_gate"]:
            print(
                json.dumps(
                    {
                        "step": index,
                        "time_sec": step_time_sec,
                        "pass": row["pass_gate"],
                        "residual": residual_norm,
                        "bottom_level_percent": 100.0 * row["bottom_level_fraction"],
                        "bottoms_lbmolph": row["bottoms_lbmolph"],
                        "bottoms_bias_active": row["bottoms_bias_active"],
                    }
                ),
                flush=True,
            )
        if not row["pass_gate"]:
            break
        reference = support.next_reference(case, base)
        previous_coordinates = solution.x.copy()
        controller_memory = float(evaluation.controller_memory_endpoint)
        controller_rate = float(evaluation.controller_rate_per_sec)
        bottoms_log = float(evaluation.bottoms_log_ratio)

    evidence = {
        "time_sec": np.asarray(times, dtype=float),
        "coordinates": np.stack(coordinates) if coordinates else np.empty((0, 0)),
        "liquid_component_inventory_lbmol": _stack(liquid),
        "vapor_component_inventory_lbmol": _stack(vapor),
        "phase_transfer_lbmolph": _stack(transfer),
        "temperature_F": _stack(temperature),
        "pressure_psia": _stack(pressure),
        "liquid_flow_lbmolph": _stack(liquid_flow),
        "vapor_flow_lbmolph": _stack(vapor_flow),
        "condenser_duty_BTUph": np.asarray(duty, dtype=float),
        "total_stored_energy_BTU": _stack(energy),
        "distillate_flow_lbmolph": np.asarray(distillate, dtype=float),
        "bottoms_flow_lbmolph": np.asarray(bottoms, dtype=float),
        "bottoms_command_lbmolph": np.asarray(bottoms_command, dtype=float),
        "bottoms_actuator_multiplier": np.asarray(actuator_multipliers, dtype=float),
        "distillate_drum_level_fraction": np.asarray(top_levels, dtype=float),
        "bottom_drum_level_fraction": np.asarray(bottom_levels, dtype=float),
        "controller_memory": np.asarray(controller_memories, dtype=float),
        "controller_rate_per_sec": np.asarray(controller_rates, dtype=float),
        "structural_pattern": pattern,
    }
    actual_component = np.sum(liquid[-1] + vapor[-1] - liquid[0] - vapor[0], axis=0)
    component_error = float(np.max(np.abs(actual_component - expected_component)))
    actual_energy = float(np.sum(energy[-1] - energy[0]))
    energy_error_abs = abs(actual_energy - expected_energy)
    energy_error_rel = energy_error_abs / max(
        abs(actual_energy), abs(expected_energy), 1.0
    )
    end_summary, summary_provider, _summary_calls = support.build_trajectory_end_summary(
        case,
        evidence,
        state_id="water_methanol:bottom_level_control:end_summary",
    )
    level_error_array = np.asarray(bottom_levels, dtype=float) - float(initial_levels[1])
    peak_index = int(np.argmax(np.abs(level_error_array)))
    bias_removed = bool(
        np.isclose(actuator_multipliers[-1], 1.0)
        and all(
            np.isclose(value, 1.0)
            for value, time_value in zip(actuator_multipliers, times, strict=True)
            if time_value > float(bottoms_bias_duration_sec) + 1.0e-12
        )
    )
    wall = float(time.perf_counter() - started)
    gates = {
        "structural_contract": bool(structural["pass_gate"]),
        "trajectory_complete": bool(
            len(steps) == step_count and all(row["pass_gate"] for row in steps)
        ),
        "component_identity": component_error < COMPONENT_LIMIT_LBMOL,
        "energy_identity": bool(
            energy_error_rel < ENERGY_RELATIVE_LIMIT
            or energy_error_abs < ENERGY_ABSOLUTE_LIMIT_BTU
        ),
        "provider": bool(
            summary_provider["pass"] and all(item["pass"] for item in provider_reports)
        ),
        "bottoms_bias_removed": bias_removed,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    workbook = Path(case.problem["workbook"])
    report = {
        "schema_id": "core-v3-water-methanol-bottom-level-control-v1",
        "classification": (
            "bottom_level_control_bias_recovery_passed"
            if passed and not np.isclose(bottoms_bias_multiplier, 1.0)
            else ("bottom_level_control_hold_passed" if passed else "bottom_level_control_run_failed")
        ),
        "component_specific_logic": False,
        "starting_state": "accepted_hydraulic_partial_reboiler_stationary_root",
        "reboiler_type": "partial",
        "timestep_sec": TIMESTEP_SEC,
        "duration_requested_sec": float(duration_sec),
        "duration_completed_sec": len(steps) * TIMESTEP_SEC,
        "feed_multiplier": 1.0,
        "bottoms_bias": {
            "multiplier": float(bottoms_bias_multiplier),
            "duration_sec": float(bottoms_bias_duration_sec),
            "removed_after_duration": bias_removed,
            "active_at_end": not np.isclose(actuator_multipliers[-1], 1.0),
        },
        "controller": {
            "controlled_variable": "geometry_based_bottom_sump_level_fraction",
            "manipulated_variable": "bottoms_flow_lbmolph",
            "setpoint_fraction": float(initial_levels[1]),
            "kc": KC,
            "ti_sec": TI_SEC,
            "activation": "bumpless_at_current_level",
            "distillate_level_controller_active": False,
            "numerical_bottoms_ratio_guard": [0.1, 10.0],
            "equipment_flow_limit_claimed": False,
        },
        "structural_contract": structural,
        "steps": steps,
        "global_conservation": {
            "actual_component_change_lbmol": actual_component.tolist(),
            "expected_component_change_lbmol": expected_component.tolist(),
            "component_identity_error_lbmol": component_error,
            "actual_energy_change_BTU": actual_energy,
            "expected_energy_change_BTU": expected_energy,
            "energy_identity_absolute_error_BTU": energy_error_abs,
            "energy_identity_relative_error": energy_error_rel,
        },
        "controller_response": {
            "initial_bottoms_lbmolph": float(bottoms[0]),
            "final_bottoms_lbmolph": float(bottoms[-1]),
            "final_bottoms_command_lbmolph": float(bottoms_command[-1]),
            "bottoms_change_lbmolph": float(bottoms[-1] - bottoms[0]),
            "minimum_bottoms_lbmolph": float(np.min(bottoms)),
            "maximum_bottoms_lbmolph": float(np.max(bottoms)),
            "initial_bottom_level_fraction": float(bottom_levels[0]),
            "final_bottom_level_fraction": float(bottom_levels[-1]),
            "maximum_absolute_level_error_fraction": float(np.max(np.abs(level_error_array))),
            "peak_level_error_fraction": float(level_error_array[peak_index]),
            "peak_level_error_time_sec": float(times[peak_index]),
            "final_level_error_fraction": float(level_error_array[-1]),
            "recovery_fraction_from_peak": float(
                1.0
                - abs(level_error_array[-1])
                / max(abs(level_error_array[peak_index]), 1.0e-300)
            ),
            "final_controller_memory": float(controller_memories[-1]),
            "final_controller_rate_per_sec": float(controller_rates[-1]),
        },
        "end_of_run": end_summary,
        "wall_clock_sec": wall,
        "clock_time_per_sim_time": wall / float(duration_sec),
        "sim_time_per_clock_time": float(duration_sec) / wall,
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "feed_disturbance_removed": True,
        "bottoms_bias_removed": bias_removed,
        "restoration": {
            "feed_multiplier_after_run": 1.0,
            "bottoms_actuator_multiplier_after_run": 1.0,
            "disturbance_active_at_end": False,
            "method": "experiment-local actuator multiplier discarded; source case unchanged",
        },
        "gates": gates,
        "pass_gate": passed,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    response = report["controller_response"]
    return "\n".join(
        (
            "# Water-methanol bottom-sump level-control run",
            "",
            f"- Result: `{report['classification']}`",
            f"- Controller: `Kc={report['controller']['kc']}, Ti={report['controller']['ti_sec']} s`",
            f"- Bottoms bias: `{report['bottoms_bias']['multiplier']}` through `{report['bottoms_bias']['duration_sec']} s`; removed: `{report['bottoms_bias_removed']}`",
            f"- Bottoms: `{response['initial_bottoms_lbmolph']:.6f}` to `{response['final_bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Bottom level: `{100.0 * response['initial_bottom_level_fraction']:.6f}%` to `{100.0 * response['final_bottom_level_fraction']:.6f}%`",
            f"- Clock/sim ratio: `{report['clock_time_per_sim_time']:.6f}`",
            "- Component-specific logic: `False`",
            "",
            "```text",
            support.format_end_of_run_summary(report["end_of_run"]),
            "```",
            "",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-sec", type=float, required=True)
    parser.add_argument("--bottoms-bias-multiplier", type=float, default=1.0)
    parser.add_argument("--bottoms-bias-duration-sec", type=float, default=0.0)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--doc", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    args = parser.parse_args()
    report, evidence = execute(
        duration_sec=args.duration_sec,
        bottoms_bias_multiplier=args.bottoms_bias_multiplier,
        bottoms_bias_duration_sec=args.bottoms_bias_duration_sec,
    )
    for path in (args.json, args.doc, args.matrix):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.doc.write_text(_markdown(report), encoding="utf-8")
    np.savez_compressed(args.matrix, **evidence)
    print(support.format_end_of_run_summary(report["end_of_run"]), flush=True)
    print(
        json.dumps(
            {
                "pass_gate": report["pass_gate"],
                "wall_clock_sec": report["wall_clock_sec"],
                "clock_time_per_sim_time": report["clock_time_per_sim_time"],
                "json": str(args.json),
                "matrix": str(args.matrix),
            }
        ),
        flush=True,
    )
    if not report["pass_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
