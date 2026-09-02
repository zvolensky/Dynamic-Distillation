#!/usr/bin/env python
"""Run an undisturbed dynamic hold from the reconciled hydraulic root."""

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


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import core_v3_water_methanol_vtpr_dynamic_support as support  # noqa: E402


TIMESTEP_SEC = 0.5
COMPONENT_LIMIT_LBMOL = 1.0e-6
ENERGY_ABSOLUTE_LIMIT_BTU = 1.0e-4
ENERGY_RELATIVE_LIMIT = 1.0e-8
JACOBIAN_CONDITION_LIMIT = 1.0e8


def _history(
    times: list[float],
    feed_multipliers: list[float],
    coordinates: list[np.ndarray],
    liquid: list[np.ndarray],
    vapor: list[np.ndarray],
    transfer: list[np.ndarray],
    temperature: list[np.ndarray],
    pressure: list[np.ndarray],
    liquid_flow: list[np.ndarray],
    vapor_flow: list[np.ndarray],
    duty: list[float],
    energy: list[np.ndarray],
) -> dict[str, np.ndarray]:
    dimension = coordinates[0].size if coordinates else 0
    return {
        "time_sec": np.asarray(times, dtype=float),
        "feed_multiplier": np.asarray(feed_multipliers, dtype=float),
        "coordinates": (
            np.stack(coordinates) if coordinates else np.empty((0, dimension))
        ),
        "liquid_component_inventory_lbmol": np.stack(liquid),
        "vapor_component_inventory_lbmol": np.stack(vapor),
        "phase_transfer_lbmolph": np.stack(transfer),
        "temperature_F": np.stack(temperature),
        "pressure_psia": np.stack(pressure),
        "liquid_flow_lbmolph": np.stack(liquid_flow),
        "vapor_flow_lbmolph": np.stack(vapor_flow),
        "condenser_duty_BTUph": np.asarray(duty, dtype=float),
        "total_stored_energy_BTU": np.stack(energy),
    }


def execute(
    *,
    duration_sec: float,
    qualify_jacobian: bool,
    reboiler_type: str,
    feed_multiplier: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if duration_sec <= 0.0 or not np.isclose(duration_sec / TIMESTEP_SEC, round(duration_sec / TIMESTEP_SEC)):
        raise ValueError("duration must be a positive multiple of 0.5 seconds")
    step_count = int(round(duration_sec / TIMESTEP_SEC))
    started = time.perf_counter()
    if reboiler_type == "partial":
        case = support.load_partial_hydraulic_case()
    elif reboiler_type == "total":
        case = support.load_reconciled_hydraulic_case()
    else:
        raise ValueError("reboiler type must be partial or total")
    feed_multiplier = float(feed_multiplier)
    if not np.isfinite(feed_multiplier) or feed_multiplier <= 0.0:
        raise ValueError("feed multiplier must be positive and finite")
    active_inputs = replace(
        case.base_inputs,
        feed_component_lbmolph=(
            feed_multiplier * np.asarray(case.base_inputs.feed_component_lbmolph)
        ),
        feed_enthalpy_BTUph=(
            feed_multiplier * float(case.base_inputs.feed_enthalpy_BTUph)
        ),
    )
    initial = case.post_pulse_reference
    reference = initial
    previous_guess: np.ndarray | None = None
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
    final_step = None

    for index in range(1, step_count + 1):
        solved = support.solve_nominal_step(
            case,
            reference,
            timestep_sec=TIMESTEP_SEC,
            step_id=f"water_methanol:reconciled_nominal:step={index}",
            initial_guess=previous_guess,
            balance_inputs=active_inputs,
            expected_feed_multiplier=feed_multiplier,
        )
        evaluation = solved.evaluation
        endpoint = evaluation.endpoint
        row = dict(solved.metrics)
        row.update(
            {
                "step_index": index,
                "time_sec": index * TIMESTEP_SEC,
                "feed_multiplier": feed_multiplier,
                "disturbance_active": not np.isclose(feed_multiplier, 1.0),
            }
        )
        steps.append(row)
        provider_reports.append(solved.provider_report)
        expected_component += (
            evaluation.transport.external_component_rate_lbmolph
            * TIMESTEP_SEC
            / 3600.0
        )
        expected_energy += float(
            evaluation.transport.external_energy_rate_BTUph
            * TIMESTEP_SEC
            / 3600.0
        )
        times.append(index * TIMESTEP_SEC)
        feed_multipliers.append(feed_multiplier)
        coordinates.append(solved.solution.x.copy())
        liquid.append(endpoint.liquid_component_inventory_lbmol.copy())
        vapor.append(endpoint.vapor_component_inventory_lbmol.copy())
        transfer.append(endpoint.phase_transfer_lbmolph.copy())
        temperature.append(endpoint.temperature_F.copy())
        pressure.append(endpoint.pressure_psia.copy())
        liquid_flow.append(endpoint.hydraulic_liquid_flow_lbmolph.copy())
        vapor_flow.append(endpoint.vapor_flow_lbmolph.copy())
        duty.append(float(endpoint.condenser_duty_BTUph))
        energy.append(evaluation.properties.total_stored_energy_BTU.copy())
        final_step = solved
        if index % 20 == 0 or index == step_count or not row["pass_gate"]:
            print(
                json.dumps(
                    {
                        "step": index,
                        "time_sec": index * TIMESTEP_SEC,
                        "pass": row["pass_gate"],
                        "residual": row["scaled_residual_inf_norm"],
                        "movement": row["maximum_coordinate_movement"],
                    }
                ),
                flush=True,
            )
        if not row["pass_gate"]:
            break
        reference = support.next_reference(case, evaluation)
        previous_guess = solved.solution.x.copy()

    evidence = _history(
        times, feed_multipliers, coordinates, liquid, vapor, transfer, temperature, pressure,
        liquid_flow, vapor_flow, duty, energy,
    )
    actual_component = np.sum(
        liquid[-1] + vapor[-1] - liquid[0] - vapor[0], axis=0
    )
    component_error = float(np.max(np.abs(actual_component - expected_component)))
    actual_energy = float(np.sum(energy[-1] - energy[0]))
    energy_error_abs = abs(actual_energy - expected_energy)
    energy_error_rel = energy_error_abs / max(abs(actual_energy), abs(expected_energy), 1.0)

    jacobian: dict[str, Any] = {"requested": bool(qualify_jacobian), "pass_gate": True}
    matrix = np.empty((0, 0), dtype=float)
    if qualify_jacobian and final_step is not None and len(steps) == step_count:
        matrix, groups = support.colored_central_difference_jacobian(
            final_step.objective,
            final_step.solution.x,
            pattern=case.pattern,
            step=1.0e-5,
            state_id="water_methanol:reconciled_nominal:endpoint_jacobian",
        )
        rank, condition, singular = support.rank_condition(matrix)
        dimension = len(case.contract.rows)
        jacobian = {
            "requested": True,
            "rank": rank,
            "dimension": dimension,
            "condition": condition,
            "color_count": len(groups),
            "minimum_singular_value": float(singular[-1]),
            "pass_gate": bool(rank == dimension and condition < JACOBIAN_CONDITION_LIMIT),
        }

    summary_case = replace(case, base_inputs=active_inputs)
    end_summary, summary_provider, _summary_calls = support.build_trajectory_end_summary(
        summary_case,
        evidence,
        state_id="water_methanol:reconciled_nominal:end_summary",
    )
    wall = float(time.perf_counter() - started)
    gates = {
        "trajectory_complete": bool(len(steps) == step_count and all(row["pass_gate"] for row in steps)),
        "requested_feed_throughout": bool(
            all(row["feed_multiplier"] == feed_multiplier for row in steps)
        ),
        "component_identity": component_error < COMPONENT_LIMIT_LBMOL,
        "energy_identity": bool(energy_error_rel < ENERGY_RELATIVE_LIMIT or energy_error_abs < ENERGY_ABSOLUTE_LIMIT_BTU),
        "provider": bool(case.history_provider_report["pass"] and summary_provider["pass"] and all(item["pass"] for item in provider_reports)),
        "endpoint_jacobian": bool(jacobian["pass_gate"]),
    }
    passed = all(gates.values())
    workbook = Path(case.problem["workbook"])
    report = {
        "schema_id": "core-v3-water-methanol-reconciled-nominal-v1",
        "classification": (
            "open_loop_feed_step_passed" if passed else "open_loop_feed_step_failed"
        ),
        "component_specific_logic": False,
        "starting_state": f"accepted_hydraulic_{reboiler_type}_reboiler_stationary_root",
        "reboiler_type": reboiler_type,
        "feed_multiplier": feed_multiplier,
        "disturbance_active_during_run": not np.isclose(feed_multiplier, 1.0),
        "timestep_sec": TIMESTEP_SEC,
        "duration_requested_sec": float(duration_sec),
        "duration_completed_sec": len(steps) * TIMESTEP_SEC,
        "step_count_requested": step_count,
        "step_count_completed": len(steps),
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
        "state_change": {
            "maximum_coordinate_movement": float(max((row["maximum_coordinate_movement"] for row in steps), default=0.0)),
            "maximum_temperature_change_F": float(np.max(np.abs(temperature[-1] - temperature[0]))),
            "maximum_pressure_change_psia": float(np.max(np.abs(pressure[-1] - pressure[0]))),
            "condenser_duty_change_BTUph": float(duty[-1] - duty[0]),
        },
        "endpoint_jacobian": jacobian,
        "end_of_run": end_summary,
        "wall_clock_sec": wall,
        "clock_time_per_sim_time": wall / float(duration_sec),
        "sim_time_per_clock_time": float(duration_sec) / wall,
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "feed_disturbance_removed": True,
        "restoration": {
            "feed_multiplier_after_run": 1.0,
            "disturbance_active_at_end": False,
            "method": "experiment-local balance inputs discarded; case default unchanged",
        },
        "gates": gates,
        "pass_gate": passed,
    }
    evidence["endpoint_jacobian"] = matrix
    evidence["structural_pattern"] = case.pattern
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        (
            "# Reconciled water-methanol dynamic feed-step run",
            "",
            f"- Result: `{report['classification']}`",
            f"- Simulated: `{report['duration_completed_sec']} s` at `{report['timestep_sec']} s` per step",
            f"- Wall clock: `{report['wall_clock_sec']:.6f} s`",
            f"- Clock/sim ratio: `{report['clock_time_per_sim_time']:.6f}`",
            f"- Component conservation error: `{report['global_conservation']['component_identity_error_lbmol']:.6e} lbmol`",
            f"- Energy conservation error: `{report['global_conservation']['energy_identity_absolute_error_BTU']:.6e} BTU`",
            f"- Feed multiplier during run: `{report['feed_multiplier']}`",
            f"- Feed disturbance removed after run: `{report['feed_disturbance_removed']}`",
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
    parser.add_argument("--qualify-jacobian", action="store_true")
    parser.add_argument(
        "--reboiler-type", choices=("partial", "total"), default="total"
    )
    parser.add_argument("--feed-multiplier", type=float, default=1.0)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--doc", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    args = parser.parse_args()
    report, evidence = execute(
        duration_sec=args.duration_sec,
        qualify_jacobian=args.qualify_jacobian,
        reboiler_type=args.reboiler_type,
        feed_multiplier=args.feed_multiplier,
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
