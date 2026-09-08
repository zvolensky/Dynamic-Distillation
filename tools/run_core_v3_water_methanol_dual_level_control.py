#!/usr/bin/env python
"""Run the water-methanol partial-reboiler case with both level controllers."""

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
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_step_bounds_v1 import (  # noqa: E402
    vapor_holdup_implicit_step_coordinate_bounds,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    VaporHoldupLevelControllerSpecification,
    audit_vapor_holdup_terminal_control_contract,
    build_vapor_holdup_terminal_control_contract,
    terminal_geometry_from_specs,
    terminal_level_fractions,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_implicit_residual_v1 import (  # noqa: E402
    controlled_implicit_initial_coordinates,
    evaluate_vapor_holdup_terminal_control_implicit_residual,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_zero_time_v1 import (  # noqa: E402
    vapor_holdup_terminal_control_pattern,
)


TIMESTEP_SEC = 0.5
DRUM_KC = 42.0
DRUM_TI_SEC = 365.0
BOTTOM_KC = 24.0
BOTTOM_TI_SEC = 365.0
RESIDUAL_LIMIT = 1.0e-8
COMPONENT_LIMIT_LBMOL = 1.0e-6
ENERGY_ABSOLUTE_LIMIT_BTU = 1.0e-4
ENERGY_RELATIVE_LIMIT = 1.0e-8
MAX_NFEV = 40
RECOVERY_MAX_NFEV = 160


def _solver_diagnostics(solution: Any, *, attempt: str) -> dict[str, Any]:
    """Capture convergence evidence without treating an under-solved step as valid."""

    return {
        "attempt": str(attempt),
        "success": bool(solution.success),
        "status": int(solution.status),
        "message": str(solution.message),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "cost": float(solution.cost),
        "optimality": float(solution.optimality),
    }


def _solve_with_recovery(
    solve: Any,
    initial_point: np.ndarray,
) -> tuple[Any, list[dict[str, Any]]]:
    """Retry only an exhausted nonlinear solve; all physics gates stay strict."""

    primary = solve(initial_point, MAX_NFEV)
    attempts = [_solver_diagnostics(primary, attempt="primary")]
    if bool(primary.success):
        return primary, attempts

    retry = solve(np.asarray(primary.x, dtype=float), RECOVERY_MAX_NFEV)
    attempts.append(_solver_diagnostics(retry, attempt="extended-warm-start"))
    return retry, attempts


def _bounds(contract) -> tuple[np.ndarray, np.ndarray]:
    base_lower, base_upper = vapor_holdup_implicit_step_coordinate_bounds(
        contract.base
    )
    base_rate_count = len(contract.base.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    lower = np.empty(len(contract.rows), dtype=float)
    upper = np.empty(len(contract.rows), dtype=float)
    lower[:base_rate_count] = base_lower[:base_rate_count]
    upper[:base_rate_count] = base_upper[:base_rate_count]
    lower[base_rate_count : base_rate_count + 2] = -0.01
    upper[base_rate_count : base_rate_count + 2] = 0.01
    algebraic_start = base_rate_count + 2
    algebraic_stop = algebraic_start + base_algebraic_count
    lower[algebraic_start:algebraic_stop] = base_lower[base_rate_count:]
    upper[algebraic_start:algebraic_stop] = base_upper[base_rate_count:]
    ratio_low, ratio_high = contract.controllers.product_rate_ratio_bounds
    lower[algebraic_stop:] = np.log(ratio_low)
    upper[algebraic_stop:] = np.log(ratio_high)
    return lower, upper


def _stack(values: list[np.ndarray]) -> np.ndarray:
    return np.stack(values)


def execute(
    *, duration_sec: float, feed_multiplier: float
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if duration_sec <= 0.0 or not np.isclose(
        duration_sec / TIMESTEP_SEC, round(duration_sec / TIMESTEP_SEC)
    ):
        raise ValueError("duration must be a positive multiple of 0.5 seconds")
    if not np.isfinite(feed_multiplier) or feed_multiplier <= 0.0:
        raise ValueError("feed multiplier must be positive and finite")

    started = time.perf_counter()
    step_count = int(round(duration_sec / TIMESTEP_SEC))
    case = support.load_partial_hydraulic_case()
    workbook_case = support.starting_state.load_case_from_excel(
        str(case.problem["workbook"])
    )
    geometry = terminal_geometry_from_specs(workbook_case.specs)
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
        state_id="water_methanol:dual_level_control:initial_level",
        evaluation_kind="residual",
    )
    initial_levels = terminal_level_fractions(
        initial.liquid_component_inventory_lbmol,
        initial_properties.liquid_density_lbmol_ft3,
        geometry,
    )
    controllers = VaporHoldupLevelControllerSpecification(
        drum_level_setpoint_fraction=float(initial_levels[0]),
        drum_kc=DRUM_KC,
        drum_ti_sec=DRUM_TI_SEC,
        sump_level_setpoint_fraction=float(initial_levels[1]),
        sump_kc=BOTTOM_KC,
        sump_ti_sec=BOTTOM_TI_SEC,
        product_rate_ratio_bounds=(0.1, 10.0),
    )
    contract = build_vapor_holdup_terminal_control_contract(
        case.contract,
        geometry=geometry,
        controllers=controllers,
    )
    structural = audit_vapor_holdup_terminal_control_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("dual level-control structural contract failed")
    pattern = vapor_holdup_terminal_control_pattern(contract)
    lower, upper = _bounds(contract)
    active_inputs = replace(
        case.base_inputs,
        feed_component_lbmolph=(
            float(feed_multiplier)
            * np.asarray(case.base_inputs.feed_component_lbmolph, dtype=float)
        ),
        feed_enthalpy_BTUph=(
            float(feed_multiplier) * float(case.base_inputs.feed_enthalpy_BTUph)
        ),
    )

    reference = initial
    previous_coordinates: np.ndarray | None = None
    controller_memory = np.zeros(2, dtype=float)
    controller_rates = np.zeros(2, dtype=float)
    product_logs = np.zeros(2, dtype=float)
    steps: list[dict[str, Any]] = []
    provider_reports: list[dict[str, Any]] = []
    expected_component = np.zeros(len(case.contract.component_names), dtype=float)
    expected_energy = 0.0
    times = [0.0]
    feed_multipliers = [1.0]
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
    drum_levels = [float(initial_levels[0])]
    bottom_levels = [float(initial_levels[1])]
    memory_history = [controller_memory.copy()]
    rate_history = [controller_rates.copy()]
    log_history = [product_logs.copy()]

    for index in range(1, step_count + 1):
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
            return evaluate_vapor_holdup_terminal_control_implicit_residual(
                contract,
                case.problem["geometry"],
                reference,
                active_inputs,
                case.problem["spec"].hydraulic_geometry,
                numerical,
                case.provider,
                audit,
                candidate,
                controller_memory_previous=controller_memory,
                state_id=(
                    f"water_methanol:dual_level_control:step={index}:"
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
                    f"water_methanol:dual_level_control:step={index}:"
                    f"jacobian={counters['jacobian']}"
                ),
            )
            return matrix

        point = controlled_implicit_initial_coordinates(
            contract,
            controller_rates_per_sec=controller_rates,
            timestep_sec=TIMESTEP_SEC,
            previous_coordinates=previous_coordinates,
            product_log_ratios_previous=product_logs,
        )
        def solve(candidate: np.ndarray, max_nfev: int) -> Any:
            return least_squares(
                objective,
                candidate,
                jac=jacobian,
                bounds=(lower, upper),
                method="trf",
                x_scale=1.0,
                ftol=1.0e-9,
                xtol=1.0e-9,
                gtol=1.0e-9,
                max_nfev=max_nfev,
                verbose=0,
            )

        solution, solver_attempts = _solve_with_recovery(solve, point)
        evaluation = evaluate_vapor_holdup_terminal_control_implicit_residual(
            contract,
            case.problem["geometry"],
            reference,
            active_inputs,
            case.problem["spec"].hydraulic_geometry,
            numerical,
            case.provider,
            audit,
            solution.x,
            controller_memory_previous=controller_memory,
            state_id=f"water_methanol:dual_level_control:step={index}:final",
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
            np.sum(
                base.properties.total_stored_energy_BTU
                - reference.total_stored_energy_BTU
            )
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
            "time_sec": index * TIMESTEP_SEC,
            "feed_multiplier": float(feed_multiplier),
            "solver_success": bool(solution.success),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "solver_attempts": solver_attempts,
            "retry_attempted": len(solver_attempts) > 1,
            "scaled_residual_inf_norm": residual_norm,
            "controller_residual_inf_norm": float(
                np.max(np.abs(evaluation.scaled[-4:]))
            ),
            "component_identity_error_lbmol": component_error,
            "energy_identity_absolute_error_BTU": energy_error_abs,
            "minimum_bound_distance": minimum_bound_distance,
            "distillate_lbmolph": evaluation.distillate_lbmolph,
            "bottoms_lbmolph": evaluation.bottoms_lbmolph,
            "drum_level_fraction": float(evaluation.level_fraction[0]),
            "bottom_level_fraction": float(evaluation.level_fraction[1]),
            "controller_rate_per_sec": evaluation.controller_rate_per_sec.tolist(),
            "controller_memory": evaluation.controller_memory_endpoint.tolist(),
            "gates": gates,
            "pass_gate": all(gates.values()),
        }
        steps.append(row)
        provider_reports.append(provider_report)
        expected_component += expected_component_step
        expected_energy += expected_energy_step
        times.append(index * TIMESTEP_SEC)
        feed_multipliers.append(float(feed_multiplier))
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
        drum_levels.append(float(evaluation.level_fraction[0]))
        bottom_levels.append(float(evaluation.level_fraction[1]))
        memory_history.append(evaluation.controller_memory_endpoint.copy())
        rate_history.append(evaluation.controller_rate_per_sec.copy())
        log_history.append(evaluation.product_log_ratio.copy())
        if index % 20 == 0 or index == step_count or not row["pass_gate"]:
            print(
                json.dumps(
                    {
                        "step": index,
                        "time_sec": row["time_sec"],
                        "pass": row["pass_gate"],
                        "residual": residual_norm,
                        "drum_level_percent": 100.0 * row["drum_level_fraction"],
                        "bottom_level_percent": 100.0
                        * row["bottom_level_fraction"],
                        "distillate_lbmolph": row["distillate_lbmolph"],
                        "bottoms_lbmolph": row["bottoms_lbmolph"],
                    }
                ),
                flush=True,
            )
        if not row["pass_gate"]:
            break
        reference = support.next_reference(case, base)
        previous_coordinates = solution.x.copy()
        controller_memory = evaluation.controller_memory_endpoint.copy()
        controller_rates = evaluation.controller_rate_per_sec.copy()
        product_logs = evaluation.product_log_ratio.copy()

    dimension = coordinates[0].size if coordinates else 0
    evidence = {
        "time_sec": np.asarray(times, dtype=float),
        "feed_multiplier": np.asarray(feed_multipliers, dtype=float),
        "coordinates": (
            _stack(coordinates) if coordinates else np.empty((0, dimension))
        ),
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
        "distillate_command_lbmolph": np.asarray(distillate, dtype=float),
        "bottoms_flow_lbmolph": np.asarray(bottoms, dtype=float),
        "bottoms_command_lbmolph": np.asarray(bottoms, dtype=float),
        "distillate_drum_level_fraction": np.asarray(drum_levels, dtype=float),
        "bottom_drum_level_fraction": np.asarray(bottom_levels, dtype=float),
        "controller_memory": _stack(memory_history),
        "controller_rate_per_sec": _stack(rate_history),
        "product_log_ratio": _stack(log_history),
        "structural_pattern": pattern,
    }
    actual_component = np.sum(
        liquid[-1] + vapor[-1] - liquid[0] - vapor[0], axis=0
    )
    component_error = float(np.max(np.abs(actual_component - expected_component)))
    actual_energy = float(np.sum(energy[-1] - energy[0]))
    energy_error_abs = abs(actual_energy - expected_energy)
    energy_error_rel = energy_error_abs / max(
        abs(actual_energy), abs(expected_energy), 1.0
    )
    summary_case = replace(case, base_inputs=active_inputs)
    end_summary, summary_provider, _summary_calls = support.build_trajectory_end_summary(
        summary_case,
        evidence,
        state_id="water_methanol:dual_level_control:end_summary",
    )
    wall = float(time.perf_counter() - started)
    top_errors = np.asarray(drum_levels) - float(initial_levels[0])
    bottom_errors = np.asarray(bottom_levels) - float(initial_levels[1])
    gates = {
        "structural_contract": bool(structural.pass_gate),
        "trajectory_complete": bool(
            len(steps) == step_count and all(row["pass_gate"] for row in steps)
        ),
        "component_identity": component_error < COMPONENT_LIMIT_LBMOL,
        "energy_identity": bool(
            energy_error_rel < ENERGY_RELATIVE_LIMIT
            or energy_error_abs < ENERGY_ABSOLUTE_LIMIT_BTU
        ),
        "provider": bool(
            summary_provider["pass"]
            and all(item["pass"] for item in provider_reports)
        ),
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    workbook = Path(case.problem["workbook"])
    report = {
        "schema_id": "core-v3-water-methanol-dual-level-control-v1",
        "classification": (
            "dual_level_control_feed_step_passed"
            if passed and not np.isclose(feed_multiplier, 1.0)
            else ("dual_level_control_hold_passed" if passed else "dual_level_control_run_failed")
        ),
        "component_specific_logic": False,
        "starting_state": "accepted_hydraulic_partial_reboiler_stationary_root",
        "reboiler_type": "partial",
        "timestep_sec": TIMESTEP_SEC,
        "duration_requested_sec": float(duration_sec),
        "duration_completed_sec": len(steps) * TIMESTEP_SEC,
        "feed_multiplier": float(feed_multiplier),
        "controllers": {
            "drum": {
                "controlled_variable": "geometry_based_distillate_drum_level_fraction",
                "manipulated_variable": "distillate_flow_lbmolph",
                "setpoint_fraction": float(initial_levels[0]),
                "kc": DRUM_KC,
                "ti_sec": DRUM_TI_SEC,
            },
            "bottom": {
                "controlled_variable": "geometry_based_bottom_sump_level_fraction",
                "manipulated_variable": "bottoms_flow_lbmolph",
                "setpoint_fraction": float(initial_levels[1]),
                "kc": BOTTOM_KC,
                "ti_sec": BOTTOM_TI_SEC,
            },
            "activation": "bumpless_at_current_levels",
            "numerical_product_ratio_guard": [0.1, 10.0],
            "equipment_flow_limit_claimed": False,
        },
        "structural_contract": {
            "dimension": structural.solve_variable_count,
            "structural_rank": structural.structural_rank,
            "pass_gate": bool(structural.pass_gate),
        },
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
            "initial_distillate_lbmolph": float(distillate[0]),
            "final_distillate_lbmolph": float(distillate[-1]),
            "initial_bottoms_lbmolph": float(bottoms[0]),
            "final_bottoms_lbmolph": float(bottoms[-1]),
            "initial_drum_level_fraction": float(drum_levels[0]),
            "final_drum_level_fraction": float(drum_levels[-1]),
            "maximum_absolute_drum_level_error_fraction": float(
                np.max(np.abs(top_errors))
            ),
            "initial_bottom_level_fraction": float(bottom_levels[0]),
            "final_bottom_level_fraction": float(bottom_levels[-1]),
            "maximum_absolute_bottom_level_error_fraction": float(
                np.max(np.abs(bottom_errors))
            ),
            "final_controller_memory": memory_history[-1].tolist(),
            "final_controller_rate_per_sec": rate_history[-1].tolist(),
        },
        "end_of_run": end_summary,
        "wall_clock_sec": wall,
        "clock_time_per_sim_time": wall / float(duration_sec),
        "sim_time_per_clock_time": float(duration_sec) / wall,
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "feed_disturbance_removed": True,
        "restoration": {
            "feed_multiplier_after_run": 1.0,
            "disturbance_active_at_end": False,
            "method": "experiment-local feed inputs discarded; source case unchanged",
        },
        "gates": gates,
        "pass_gate": passed,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    response = report["controller_response"]
    return "\n".join(
        (
            "# Water-methanol dual level-control feed disturbance",
            "",
            f"- Result: `{report['classification']}`",
            f"- Feed multiplier: `{report['feed_multiplier']}`",
            f"- Duration: `{report['duration_completed_sec']} s`",
            f"- Distillate: `{response['initial_distillate_lbmolph']:.6f}` to `{response['final_distillate_lbmolph']:.6f} lbmol/h`",
            f"- Bottoms: `{response['initial_bottoms_lbmolph']:.6f}` to `{response['final_bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Drum level: `{100.0 * response['initial_drum_level_fraction']:.6f}%` to `{100.0 * response['final_drum_level_fraction']:.6f}%`",
            f"- Bottom level: `{100.0 * response['initial_bottom_level_fraction']:.6f}%` to `{100.0 * response['final_bottom_level_fraction']:.6f}%`",
            f"- Clock/sim ratio: `{report['clock_time_per_sim_time']:.6f}`",
            f"- Feed disturbance removed: `{report['feed_disturbance_removed']}`",
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
    parser.add_argument("--feed-multiplier", type=float, default=1.0)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--doc", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    args = parser.parse_args()
    report, evidence = execute(
        duration_sec=args.duration_sec,
        feed_multiplier=args.feed_multiplier,
    )
    for path in (args.json, args.doc, args.matrix):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.doc.write_text(_markdown(report), encoding="utf-8")
    support.write_core_v3_docx_report(report["end_of_run"], args.doc.with_suffix(".docx"), title="Core V3 Water-Methanol Dual-Level Control Run", metadata=report, trajectory=evidence)
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
