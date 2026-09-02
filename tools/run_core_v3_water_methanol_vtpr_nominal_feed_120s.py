#!/usr/bin/env python
"""Run 120 seconds from the post-pulse state at exactly nominal feed."""

from __future__ import annotations

import argparse
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


SOURCE_QUALIFICATION = Path(
    "logs/core_v3_water_methanol_vtpr_dt_0p5_qualification_20260901.json"
)
DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_20260901.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_vtpr_nominal_feed_120s_20260901.md"
)
DEFAULT_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_20260901.npz"
)
DEFAULT_CHECKPOINT_JSON = Path(
    "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_checkpoint_20260901.json"
)
DEFAULT_CHECKPOINT_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_checkpoint_20260901.npz"
)

TIMESTEP_SEC = 0.5
DURATION_SEC = 120.0
STEP_COUNT = int(DURATION_SEC / TIMESTEP_SEC)
CHECKPOINT_INTERVAL_STEPS = 20
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)
CONDITION_LIMIT = 1.0e8
MATRIX_CHANGE_LIMIT = 0.05
SPECTRUM_CHANGE_LIMIT = 0.25
GLOBAL_COMPONENT_LIMIT_LBMOL = 1.0e-6
GLOBAL_ENERGY_ABSOLUTE_LIMIT_BTU = 1.0e-4
GLOBAL_ENERGY_RELATIVE_LIMIT = 1.0e-8
STEP_PROVIDER_CALL_LIMIT = 100000
WALL_LIMIT_SEC = 3600.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _history_evidence(
    times: list[float],
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
        "feed_multiplier": np.ones(len(times), dtype=float),
        "coordinates": (
            np.stack(coordinates)
            if coordinates
            else np.empty((0, dimension), dtype=float)
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


def _write_checkpoint(
    json_path: Path,
    matrix_path: Path,
    *,
    step_reports: list[dict[str, Any]],
    evidence: dict[str, np.ndarray],
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_id": "core-v3-water-methanol-vtpr-nominal-feed-120s-checkpoint-v1",
        "feed_multiplier": 1.0,
        "disturbance_active": False,
        "timestep_sec": TIMESTEP_SEC,
        "last_completed_step": len(step_reports),
        "last_completed_time_sec": len(step_reports) * TIMESTEP_SEC,
        "all_completed_steps_pass": all(
            item["pass_gate"] for item in step_reports
        ),
        "steps": step_reports,
    }
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    np.savez_compressed(matrix_path, **evidence)


def execute(
    checkpoint_json: Path,
    checkpoint_matrix: Path,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    qualification_path = support.rooted(SOURCE_QUALIFICATION).resolve()
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    if (
        not qualification.get("pass_gate")
        or qualification.get("decision")
        != "authorize_120_second_nominal_feed_run_at_dt_0p5"
        or qualification.get("feed_multiplier") != 1.0
        or qualification.get("component_specific_logic") is not False
    ):
        raise RuntimeError("120-second run requires the accepted 0.5-second qualification")

    case = support.load_post_pulse_case()
    initial = case.post_pulse_reference
    reference = initial
    previous_guess: np.ndarray | None = None
    step_reports: list[dict[str, Any]] = []
    provider_reports: list[dict[str, Any]] = []
    provider_calls = case.history_provider_calls
    expected_component_total = np.zeros(
        len(case.contract.component_names), dtype=float
    )
    expected_energy_total = 0.0
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
    final_step = None

    for step_index in range(1, STEP_COUNT + 1):
        solved = support.solve_nominal_step(
            case,
            reference,
            timestep_sec=TIMESTEP_SEC,
            step_id=f"water_methanol:nominal_120s:step={step_index}",
            initial_guess=previous_guess,
        )
        evaluation = solved.evaluation
        endpoint = evaluation.endpoint
        step_metrics = dict(solved.metrics)
        step_metrics.update(
            {
                "step_index": step_index,
                "time_sec": step_index * TIMESTEP_SEC,
                "feed_multiplier": 1.0,
                "disturbance_active": False,
                "provider_call_limit": bool(
                    solved.provider_calls < STEP_PROVIDER_CALL_LIMIT
                ),
            }
        )
        step_metrics["pass_gate"] = bool(
            step_metrics["pass_gate"] and step_metrics["provider_call_limit"]
        )
        step_reports.append(step_metrics)
        provider_reports.append(solved.provider_report)
        provider_calls += solved.provider_calls
        expected_component_total += (
            evaluation.transport.external_component_rate_lbmolph
            * TIMESTEP_SEC
            / 3600.0
        )
        expected_energy_total += float(
            evaluation.transport.external_energy_rate_BTUph
            * TIMESTEP_SEC
            / 3600.0
        )
        times.append(step_index * TIMESTEP_SEC)
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
        if step_index % 10 == 0 or not step_metrics["pass_gate"]:
            print(
                json.dumps(
                    {
                        "step": step_index,
                        "time_sec": step_index * TIMESTEP_SEC,
                        "pass_gate": step_metrics["pass_gate"],
                        "residual": step_metrics["scaled_residual_inf_norm"],
                        "nfev": step_metrics["nfev"],
                    }
                ),
                flush=True,
            )
        evidence = _history_evidence(
            times,
            coordinates,
            liquid,
            vapor,
            transfer,
            temperature,
            pressure,
            liquid_flow,
            vapor_flow,
            duty,
            energy,
        )
        if step_index % CHECKPOINT_INTERVAL_STEPS == 0 or not step_metrics["pass_gate"]:
            _write_checkpoint(
                checkpoint_json,
                checkpoint_matrix,
                step_reports=step_reports,
                evidence=evidence,
            )
        if not step_metrics["pass_gate"]:
            break
        reference = support.next_reference(case, evaluation)
        previous_guess = solved.solution.x.copy()

    trajectory_complete = len(step_reports) == STEP_COUNT
    all_steps_pass = trajectory_complete and all(
        item["pass_gate"] for item in step_reports
    )
    matrices: list[np.ndarray] = []
    jacobian_steps: list[dict[str, Any]] = []
    if all_steps_pass and final_step is not None:
        for difference_step in ENDPOINT_STEPS:
            matrix, groups = support.colored_central_difference_jacobian(
                final_step.objective,
                final_step.solution.x,
                pattern=case.pattern,
                step=difference_step,
                state_id=(
                    "water_methanol:nominal_120s:final_endpoint:"
                    f"h={difference_step:.1e}"
                ),
            )
            rank, condition, singular = support.rank_condition(matrix)
            matrices.append(matrix)
            jacobian_steps.append(
                {
                    "step": difference_step,
                    "rank": rank,
                    "condition": condition,
                    "singular_values": [float(value) for value in singular],
                    "color_count": len(groups),
                    "zero_rows": int(
                        np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)
                    ),
                    "zero_columns": int(
                        np.count_nonzero(np.linalg.norm(matrix, axis=0) <= 1.0e-12)
                    ),
                }
            )
    if len(matrices) == 2:
        spectrum_change = support.relative_change(
            np.asarray(jacobian_steps[0]["singular_values"]),
            np.asarray(jacobian_steps[1]["singular_values"]),
        )
        matrix_change = support.relative_change(matrices[0], matrices[1])
        dimension = len(case.contract.rows)
        jacobian_pass = bool(
            all(item["rank"] == dimension for item in jacobian_steps)
            and all(item["condition"] < CONDITION_LIMIT for item in jacobian_steps)
            and all(item["zero_rows"] == 0 for item in jacobian_steps)
            and all(item["zero_columns"] == 0 for item in jacobian_steps)
            and spectrum_change < SPECTRUM_CHANGE_LIMIT
            and matrix_change < MATRIX_CHANGE_LIMIT
        )
    else:
        spectrum_change = float("inf")
        matrix_change = float("inf")
        jacobian_pass = False

    if final_step is not None:
        provider_calls += final_step.audit.record_count - final_step.provider_calls
        provider_reports[-1] = support.compact_provider_report(
            final_step.audit.report()
        )

    actual_component_total = np.sum(
        liquid[-1]
        + vapor[-1]
        - liquid[0]
        - vapor[0],
        axis=0,
    )
    global_component_error = float(
        np.max(np.abs(actual_component_total - expected_component_total))
    )
    actual_energy_total = float(np.sum(energy[-1] - energy[0]))
    global_energy_error_absolute = abs(actual_energy_total - expected_energy_total)
    global_energy_error_relative = global_energy_error_absolute / max(
        abs(actual_energy_total), abs(expected_energy_total), 1.0
    )
    end_summary, end_summary_provider, end_summary_calls = (
        support.build_trajectory_end_summary(
            case,
            evidence,
            state_id="water_methanol:nominal_120s:end_of_run_summary",
        )
    )
    provider_calls += end_summary_calls
    provider_pass = bool(
        case.history_provider_report["pass"]
        and all(item["pass"] for item in provider_reports)
        and all(item["gates"]["provider"] for item in step_reports)
        and end_summary_provider["pass"]
    )
    nominal_feed_pass = bool(
        len(step_reports) > 0
        and all(item["feed_multiplier"] == 1.0 for item in step_reports)
        and all(not item["disturbance_active"] for item in step_reports)
        and all(item["gates"]["nominal_feed"] for item in step_reports)
    )
    wall = time.perf_counter() - started
    gates = {
        "trajectory_complete": all_steps_pass,
        "nominal_feed_throughout": nominal_feed_pass,
        "global_component_identity": (
            global_component_error < GLOBAL_COMPONENT_LIMIT_LBMOL
        ),
        "global_energy_identity": bool(
            global_energy_error_relative < GLOBAL_ENERGY_RELATIVE_LIMIT
            or global_energy_error_absolute < GLOBAL_ENERGY_ABSOLUTE_LIMIT_BTU
        ),
        "endpoint_jacobian": jacobian_pass,
        "provider": provider_pass,
        "wall": wall < WALL_LIMIT_SEC,
    }
    gates = {name: bool(value) for name, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": "core-v3-water-methanol-vtpr-nominal-feed-120s-v1",
        "classification": (
            "nominal_feed_120s_trajectory_passed"
            if passed
            else "nominal_feed_120s_trajectory_failed"
        ),
        "decision": (
            "accept_120_second_nominal_feed_recovery_trajectory"
            if passed
            else "stop_and_correct_nominal_feed_trajectory"
        ),
        "component_specific_logic": False,
        "starting_state": "accepted_post_pulse_state_with_feed_restored",
        "feed_multiplier": 1.0,
        "disturbance_active": False,
        "timestep_sec": TIMESTEP_SEC,
        "duration_requested_sec": DURATION_SEC,
        "duration_completed_sec": len(step_reports) * TIMESTEP_SEC,
        "step_count_requested": STEP_COUNT,
        "step_count_completed": len(step_reports),
        "checkpoint_interval_steps": CHECKPOINT_INTERVAL_STEPS,
        "checkpoint_interval_sec": CHECKPOINT_INTERVAL_STEPS * TIMESTEP_SEC,
        "steps": step_reports,
        "global_conservation": {
            "actual_component_change_lbmol": [
                float(value) for value in actual_component_total
            ],
            "expected_component_change_lbmol": [
                float(value) for value in expected_component_total
            ],
            "component_identity_error_lbmol": global_component_error,
            "actual_energy_change_BTU": actual_energy_total,
            "expected_energy_change_BTU": expected_energy_total,
            "energy_identity_absolute_error_BTU": global_energy_error_absolute,
            "energy_identity_relative_error": global_energy_error_relative,
        },
        "state_change": {
            "total_component_inventory_change_lbmol": float(
                np.sum(actual_component_total)
            ),
            "maximum_temperature_change_F": float(
                np.max(np.abs(temperature[-1] - temperature[0]))
            ),
            "maximum_pressure_change_psia": float(
                np.max(np.abs(pressure[-1] - pressure[0]))
            ),
            "maximum_liquid_flow_relative_change": float(
                np.max(
                    np.abs(
                        liquid_flow[-1] / liquid_flow[0] - 1.0
                    )
                )
            ),
            "maximum_vapor_flow_relative_change": float(
                np.max(np.abs(vapor_flow[-1] / vapor_flow[0] - 1.0))
            ),
            "condenser_duty_change_BTUph": float(duty[-1] - duty[0]),
        },
        "end_of_run": end_summary,
        "endpoint_jacobian": {
            "steps": jacobian_steps,
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_change": matrix_change,
            "pass_gate": jacobian_pass,
        },
        "provider": {
            "history": case.history_provider_report,
            "end_of_run_summary": end_summary_provider,
            "total_calls": provider_calls,
            "all_step_reports_pass": provider_pass,
            "pass_gate": provider_pass,
        },
        "sources": {
            str(SOURCE_QUALIFICATION).replace("\\", "/"): _sha256(
                qualification_path
            ),
            str(support.SOURCE_PULSE).replace("\\", "/"): _sha256(
                support.rooted(support.SOURCE_PULSE)
            ),
            str(support.SOURCE_PULSE_MATRIX).replace("\\", "/"): _sha256(
                support.rooted(support.SOURCE_PULSE_MATRIX)
            ),
        },
        "gates": gates,
        "wall_clock_sec": wall,
        "retry_attempted": False,
        "adaptive_timestep_used": False,
        "feed_disturbance_removed": True,
        "pass_gate": passed,
    }
    evidence = _history_evidence(
        times,
        coordinates,
        liquid,
        vapor,
        transfer,
        temperature,
        pressure,
        liquid_flow,
        vapor_flow,
        duty,
        energy,
    )
    evidence.update(
        {
            "jacobian_h1": matrices[0] if matrices else np.empty((0, 0)),
            "jacobian_h2": matrices[1] if len(matrices) > 1 else np.empty((0, 0)),
            "structural_pattern": case.pattern,
        }
    )
    _write_checkpoint(
        checkpoint_json,
        checkpoint_matrix,
        step_reports=step_reports,
        evidence=evidence,
    )
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    jacobian_steps = report["endpoint_jacobian"]["steps"]
    rank_text = (
        f"{jacobian_steps[0]['rank']} / {jacobian_steps[1]['rank']}"
        if len(jacobian_steps) == 2
        else "not evaluated"
    )
    body = "\n".join(
        (
            "# Core V3 water-methanol 120-second nominal-feed trajectory",
            "",
            f"- Result: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Completed: `{report['duration_completed_sec']} / {report['duration_requested_sec']} s`",
            f"- Steps: `{report['step_count_completed']} / {report['step_count_requested']}` at `{report['timestep_sec']} s`",
            f"- Feed multiplier: `{report['feed_multiplier']}`",
            f"- Disturbance active: `{report['disturbance_active']}`",
            f"- Global component error: `{report['global_conservation']['component_identity_error_lbmol']:.6e} lbmol`",
            f"- Global energy error: `{report['global_conservation']['energy_identity_absolute_error_BTU']:.6e} BTU`",
            f"- Final Jacobian rank: `{rank_text}`",
            f"- Provider pass: `{report['provider']['pass_gate']}`",
            "- Retry or adaptive timestep: `False`",
            "",
            "The entire trajectory used the nominal feed. The original feed disturbance remained off.",
            "",
        )
    )
    if "end_of_run" in report:
        body += "\n".join(
            (
                "## End-of-run operating summary",
                "",
                "```text",
                support.format_end_of_run_summary(report["end_of_run"]),
                "```",
                "",
            )
        )
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument(
        "--checkpoint-json", type=Path, default=DEFAULT_CHECKPOINT_JSON
    )
    parser.add_argument(
        "--checkpoint-matrix", type=Path, default=DEFAULT_CHECKPOINT_MATRIX
    )
    args = parser.parse_args()
    checkpoint_json = support.rooted(args.checkpoint_json)
    checkpoint_matrix = support.rooted(args.checkpoint_matrix)
    report, evidence = execute(checkpoint_json, checkpoint_matrix)
    json_path = support.rooted(args.json)
    doc_path = support.rooted(args.doc)
    matrix_path = support.rooted(args.matrix)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    np.savez_compressed(matrix_path, **evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "duration_completed_sec": report["duration_completed_sec"],
                "feed_multiplier": report["feed_multiplier"],
            },
            indent=2,
        ),
        flush=True,
    )
    print(support.format_end_of_run_summary(report["end_of_run"]), flush=True)
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
