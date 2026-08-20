#!/usr/bin/env python
"""Prepare or execute DD-261's journaled continuation from DD-260 endpoint 81."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_five_second_recovery as dd259  # noqa: E402
import run_core_v3_vapor_holdup_five_second_reporting_successor as dd258  # noqa: E402
import run_core_v3_vapor_holdup_parallel_trajectory as dd254  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_thirty_second_trajectory as dd260  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import compact_provider_report  # noqa: E402


SCHEMA = "dd261-core-v3-c3c4-vapor-holdup-thirty-second-resume-contract-v1"
RESULT_SCHEMA = "dd261-core-v3-c3c4-vapor-holdup-thirty-second-resume-result-v1"
CONTRACT = Path("logs/dd261_core_v3_c3c4_vapor_holdup_thirty_second_resume_contract_20260820.json")
RESULT = Path("logs/dd261_core_v3_c3c4_vapor_holdup_thirty_second_resume_20260820.json")
EVIDENCE = Path("logs/dd261_core_v3_c3c4_vapor_holdup_thirty_second_resume_20260820.npz")
RECOVERY = Path("logs/dd261_core_v3_c3c4_vapor_holdup_thirty_second_resume_recovery_20260820.json")
JOURNAL = Path("logs/dd261_core_v3_c3c4_vapor_holdup_thirty_second_journal_20260820")
SOURCE_RECOVERY = Path("logs/dd260_core_v3_c3c4_vapor_holdup_aborted_endpoint81_20260820.json")
DD260_ABORT = Path("logs/dd260_core_v3_c3c4_vapor_holdup_thirty_second_abort_20260820.json")
CONTRACT_DOC = Path("docs/dd_261_core_v3_c3c4_vapor_holdup_thirty_second_resume_contract_20260820.md")
RESULT_DOC = Path("docs/dd_261_core_v3_c3c4_vapor_holdup_thirty_second_resume_20260820.md")
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_thirty_second_resume.py"),
    Path("tools/run_core_v3_vapor_holdup_thirty_second_trajectory.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments), cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    recovered = json.loads((ROOT / SOURCE_RECOVERY).read_text(encoding="utf-8"))
    dd260_contract = json.loads((ROOT / dd260.CONTRACT).read_text(encoding="utf-8"))
    abort = json.loads((ROOT / DD260_ABORT).read_text(encoding="utf-8"))
    if recovered.get("completed_endpoint_count") != 81 or recovered.get("last_time_sec") != 20.25:
        raise RuntimeError("DD-261 requires the exact validated DD-260 endpoint-81 recovery")
    if abort.get("scientific_failure_observed") or abort.get("rerun_attempted"):
        raise RuntimeError("DD-261 permits only a reporting-abort continuation")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": {
            "source": "user-authorized autonomous continuation after DD-260",
            "classification": "new successor using DD-260 recovery, not a DD-260 rerun",
        },
        "sources": {
            SOURCE_RECOVERY.as_posix(): _sha(SOURCE_RECOVERY),
            DD260_ABORT.as_posix(): _sha(DD260_ABORT),
            dd260.CONTRACT.as_posix(): _sha(dd260.CONTRACT),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "trajectory": {
            "recovered_endpoint_count": 81,
            "start_time_sec": 20.25,
            "nominal_step_sec": 0.25,
            "remaining_nominal_steps": 39,
            "final_time_sec": 30.0,
            "refinement_start_sec": 29.75,
            "refined_step_sec": 0.125,
            "refined_steps": 2,
        },
        "disturbance": dd260_contract["disturbance"],
        "solver": dd260_contract["solver"],
        "method": dd260_contract["method"],
        "operating_inputs": dd260_contract["operating_inputs"],
        "limits": dd260_contract["limits"],
        "reporting": {
            "immutable_unique_endpoint_journal": True,
            "single_live_recovery_replacement": False,
            "atomic_final_json": True,
            "atomic_final_npz": True,
            "complete_final_stage_profile": True,
        },
        "hard_stops": [
            "any continuation or refinement endpoint fails its frozen science or physical gates",
            "any immutable endpoint journal fails to serialize",
            "the combined 30-second conservation or accumulation gate fails",
            "the final local timestep comparison exceeds DD-260's frozen limits",
            "a retry, controller, fallback, setting change, or extension beyond 30 seconds occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    if (ROOT / contract_path).exists() or (ROOT / contract_doc_path).exists():
        raise RuntimeError("DD-261 contract artifact already exists")
    (ROOT / contract_path).write_text(dd259._json_text(payload), encoding="utf-8")
    (ROOT / contract_doc_path).write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    trajectory = payload["trajectory"]
    return "\n".join(
        (
            "# DD-261 Journaled Thirty-Second Resume Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- DD-260 remains a reporting abort and is not rerun or reclassified.",
            f"- Resume: endpoint `{trajectory['recovered_endpoint_count']}` at `{trajectory['start_time_sec']} s`.",
            f"- Continuation: `{trajectory['remaining_nominal_steps']}` x `{trajectory['nominal_step_sec']} s` to `{trajectory['final_time_sec']} s`.",
            f"- Final refinement: `{trajectory['refined_steps']}` x `{trajectory['refined_step_sec']} s` from `{trajectory['refinement_start_sec']} s`.",
            "- Every new endpoint is written once to a unique immutable journal file.",
            "- Physics, solver, disturbance, operating inputs, and gates remain unchanged.",
            "- No retry, controller, fallback, setting change, or extension is authorized.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-261 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-261 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-261 implementation changed: {path}")
    if any((ROOT / path).exists() for path in (result_path, RECOVERY, EVIDENCE, JOURNAL)):
        raise RuntimeError("DD-261 output already exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _journal_endpoint(
    payload: Mapping[str, Any],
    global_index: int,
    time_sec: float,
    report: Mapping[str, Any],
    coordinates: np.ndarray,
    reference: Any,
) -> Path:
    destination = JOURNAL / f"endpoint_{global_index:03d}.json"
    if (ROOT / destination).exists():
        raise RuntimeError(f"DD-261 journal collision: {destination}")
    dd259._atomic_json(
        destination,
        {
            "schema_id": "dd261-core-v3-c3c4-vapor-holdup-endpoint-journal-v1",
            "contract_payload_sha256": payload["contract_payload_sha256"],
            "global_endpoint_index": global_index,
            "time_sec": time_sec,
            "report": report,
            "endpoint_coordinates": coordinates,
            "next_reference": dd254._reference_payload(reference),
        },
    )
    return destination


def _combined_response(initial: Any, final: Any, duration_sec: float) -> dict[str, Any]:
    endpoint = final.endpoint
    actual_component = np.sum(
        endpoint.liquid_component_inventory_lbmol
        + endpoint.vapor_component_inventory_lbmol
        - initial.liquid_component_inventory_lbmol
        - initial.vapor_component_inventory_lbmol,
        axis=0,
    )
    expected_component = final.transport.external_component_rate_lbmolph * (duration_sec / 3600.0)
    actual_energy = float(np.sum(final.properties.total_stored_energy_BTU - initial.total_stored_energy_BTU))
    expected_energy = float(final.transport.external_energy_rate_BTUph * (duration_sec / 3600.0))
    energy_scale = max(abs(actual_energy), abs(expected_energy), 1.0)
    return {
        "component_inventory_change_lbmol": actual_component,
        "expected_component_inventory_change_lbmol": expected_component,
        "component_inventory_identity_max_abs_lbmol": float(np.max(np.abs(actual_component - expected_component))),
        "total_inventory_change_lbmol": float(np.sum(actual_component)),
        "expected_total_inventory_change_lbmol": float(np.sum(expected_component)),
        "stored_energy_change_BTU": actual_energy,
        "expected_stored_energy_change_BTU": expected_energy,
        "energy_identity_relative": abs(actual_energy - expected_energy) / energy_scale,
    }


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    dd259._reporting_preflight()
    recovered = json.loads((ROOT / SOURCE_RECOVERY).read_text(encoding="utf-8"))
    context = dd254._make_main_context()
    initial_reference = context["reference"]
    reference = dd254._reference_from_payload(recovered["next_reference"])
    initial_coordinates = np.asarray(recovered["endpoint_coordinates"][-1], dtype=float)
    (ROOT / JOURNAL).mkdir(parents=True, exist_ok=False)
    evaluations: list[Any] = []
    reports: list[dict[str, Any]] = []
    coordinates: list[np.ndarray] = []
    journal_paths: list[Path] = []
    pre_final_reference = None
    pre_final_coordinates = None
    trajectory = payload["trajectory"]
    started = time.perf_counter()
    for local_index in range(int(trajectory["remaining_nominal_steps"])):
        global_index = int(trajectory["recovered_endpoint_count"]) + local_index + 1
        if global_index == 120:
            pre_final_reference = reference
            pre_final_coordinates = initial_coordinates.copy()
        _solution, final, report, accepted_coordinates = dd260._solve_endpoint(
            context,
            payload,
            reference,
            initial_coordinates,
            float(trajectory["nominal_step_sec"]),
            f"dd261:nominal_{global_index}",
        )
        time_sec = global_index * float(trajectory["nominal_step_sec"])
        report.update(
            {
                "index": global_index,
                "time_sec": time_sec,
                "total_liquid_inventory_lbmol": float(np.sum(final.endpoint.liquid_component_inventory_lbmol)),
                "total_vapor_inventory_lbmol": float(np.sum(final.endpoint.vapor_component_inventory_lbmol)),
                "condenser_duty_BTUph": float(final.endpoint.condenser_duty_BTUph),
            }
        )
        evaluations.append(final)
        reports.append(report)
        coordinates.append(accepted_coordinates)
        reference = dd249._next_reference(reference, final)
        initial_coordinates = accepted_coordinates
        journal_paths.append(
            _journal_endpoint(payload, global_index, time_sec, report, accepted_coordinates, reference)
        )
        if global_index % 10 == 0:
            print(
                f"DD-261 accepted endpoint {global_index}/120 "
                f"(t={time_sec:.2f} s, residual={report['scaled_residual_inf_norm']:.2e})",
                flush=True,
            )
    if pre_final_reference is None or pre_final_coordinates is None:
        raise RuntimeError("DD-261 did not capture the final refinement branch")
    refined_evaluations: list[Any] = []
    refined_reports: list[dict[str, Any]] = []
    refined_reference = pre_final_reference
    refined_coordinates = pre_final_coordinates
    for index in range(int(trajectory["refined_steps"])):
        _solution, final, report, accepted_coordinates = dd260._solve_endpoint(
            context,
            payload,
            refined_reference,
            refined_coordinates,
            float(trajectory["refined_step_sec"]),
            f"dd261:refined_{index + 1}",
        )
        report["index"] = index + 1
        report["time_sec"] = float(trajectory["refinement_start_sec"]) + (index + 1) * float(trajectory["refined_step_sec"])
        refined_evaluations.append(final)
        refined_reports.append(report)
        refined_reference = dd249._next_reference(refined_reference, final)
        refined_coordinates = accepted_coordinates
    wall = time.perf_counter() - started
    final = evaluations[-1]
    limits = payload["limits"]
    previous_reports = recovered["endpoint_reports"]
    all_nominal_reports = previous_reports + reports
    all_science_reports = all_nominal_reports + refined_reports
    scientific = all(
        item["success"]
        and item["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and item["jacobian_rank"] == limits["rank"]
        and item["jacobian_condition"] < limits["condition"]
        and item["maximum_fugacity_residual"] < limits["fugacity_residual"]
        and item["maximum_eos_relative_residual"] < limits["eos_relative_residual"]
        and item["physical_pass"]
        and item["jacobian_build_count"] == 1
        for item in all_science_reports
    )
    response = _combined_response(initial_reference, final, 30.0)
    initial_total = float(
        np.sum(initial_reference.liquid_component_inventory_lbmol)
        + np.sum(initial_reference.vapor_component_inventory_lbmol)
    )
    previous_totals = np.asarray(
        [item["total_liquid_inventory_lbmol"] + item["total_vapor_inventory_lbmol"] for item in previous_reports]
    )
    continuation_totals = np.asarray([dd260._total_inventory(item) for item in evaluations])
    inventory_changes = np.concatenate((previous_totals, continuation_totals)) - initial_total
    continuity = dd260._continuity(dd254._reference_from_payload(recovered["next_reference"]), evaluations)
    refinement = dd260._refinement_comparison(
        final,
        refined_evaluations[-1],
        initial_reference.phase_transfer_scale_lbmolph,
    )
    refinement_gates = {
        "component_max": refinement["maximum_component_inventory_difference_lbmol"] < limits["refinement_component_max_lbmol"],
        "component_l1": refinement["component_inventory_difference_l1_lbmol"] < limits["refinement_component_l1_lbmol"],
        "signed_total": refinement["signed_total_inventory_difference_lbmol"] < limits["refinement_signed_total_lbmol"],
        "temperature": refinement["temperature_difference_F"] < limits["refinement_temperature_F"],
        "pressure": refinement["pressure_difference_psia"] < limits["refinement_pressure_psia"],
        "liquid_flow": refinement["liquid_flow_relative_difference"] < limits["refinement_flow_relative"],
        "vapor_flow": refinement["vapor_flow_relative_difference"] < limits["refinement_flow_relative"],
        "phase_transfer": refinement["phase_transfer_scaled_difference"] < limits["refinement_phase_transfer_scaled"],
        "duty": refinement["duty_relative_difference"] < limits["refinement_duty_relative"],
    }
    continuity_gates = {
        "temperature": continuity["temperature_F"] < limits["maximum_step_temperature_F"],
        "pressure": continuity["pressure_psia"] < limits["maximum_step_pressure_psia"],
        "composition": continuity["composition"] < limits["maximum_step_composition"],
        "flow": continuity["flow_relative"] < limits["maximum_step_flow_relative"],
        "phase_inventory": continuity["phase_inventory_relative"] < limits["maximum_step_phase_inventory_relative"],
        "duty": continuity["duty_relative"] < limits["maximum_step_duty_relative"],
    }
    provider = compact_provider_report(context["audit"].report())
    continuation_calls = int(context["audit"].record_count)
    combined_calls = int(recovered["logical_provider_calls_so_far"]) + continuation_calls
    profile = dd258.stage_profile(context, final.endpoint)
    journal_complete = len(journal_paths) == 39 and all((ROOT / path).exists() for path in journal_paths)
    gates = {
        "combined_path_complete": len(all_nominal_reports) == 120,
        "scientific_endpoints": bool(scientific),
        "positive_monotonic_accumulation": bool(np.all(inventory_changes > 0.0) and np.all(np.diff(inventory_changes) > 0.0)),
        "component_identity": response["component_inventory_identity_max_abs_lbmol"] < limits["component_identity_lbmol"],
        "energy_identity": response["energy_identity_relative"] < limits["energy_identity_relative"],
        "temperature_ordering": bool(all(np.all(np.diff(item.endpoint.temperature_F) > 0.0) for item in evaluations)),
        "continuation_continuity": bool(all(continuity_gates.values())),
        "final_refinement": bool(all(refinement_gates.values())),
        "provider": bool(provider["pass"] and not provider["fallback_attempted"]),
        "journal_complete": journal_complete,
        "report_complete": len(profile) == 20,
        "combined_call_count": combined_calls < limits["logical_provider_calls"],
        "continuation_wall_clock": wall < limits["wall_clock_sec"],
        "no_retry_or_controller": True,
    }
    passed = bool(all(gates.values()))
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": "journaled_thirty_second_vapor_holdup_trajectory_passed" if passed else "journaled_thirty_second_vapor_holdup_trajectory_failed",
        "decision": "accept_open_loop_vapor_holdup_dynamics_through_thirty_seconds" if passed else "retain_dd260_endpoint_81_boundary",
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "component_names": list(context["contract"].component_names),
        "operating_inputs": payload["operating_inputs"],
        "recovered_endpoint_count": 81,
        "continuation_endpoint_count": 39,
        "simulation_time_sec": 30.0,
        "continuation_wall_clock_sec": wall,
        "continuation_simulation_to_wall_ratio": 9.75 / wall,
        "dd260_provider_calls": int(recovered["logical_provider_calls_so_far"]),
        "continuation_provider_calls": continuation_calls,
        "combined_provider_calls": combined_calls,
        "final_condenser_duty_BTUph": float(final.endpoint.condenser_duty_BTUph),
        "inventory_change_by_endpoint_lbmol": inventory_changes,
        "response": response,
        "continuity": continuity,
        "continuity_gates": continuity_gates,
        "refinement": refinement,
        "refinement_gates": refinement_gates,
        "prior_endpoint_reports": previous_reports,
        "continuation_endpoint_reports": reports,
        "refined_endpoint_reports": refined_reports,
        "final_stage_profile": profile,
        "provider": provider,
        "journal_files": [path.as_posix() for path in journal_paths],
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "dd260_rerun_attempted": False,
        "retry_attempted": False,
        "controller_attempted": False,
        "fallback_attempted": False,
        "longer_trajectory_attempted": False,
    }
    dd259._atomic_npz(
        evidence_path,
        continuation_coordinates=np.stack(coordinates),
        inventory_change_by_endpoint_lbmol=inventory_changes,
        final_liquid_inventory=final.endpoint.liquid_component_inventory_lbmol,
        final_vapor_inventory=final.endpoint.vapor_component_inventory_lbmol,
        final_temperature_F=final.endpoint.temperature_F,
        final_pressure_psia=final.endpoint.pressure_psia,
        final_liquid_flow_lbmolph=final.endpoint.hydraulic_liquid_flow_lbmolph,
        final_vapor_flow_lbmolph=final.endpoint.vapor_flow_lbmolph,
    )
    dd259._atomic_json(result_path, report)
    (ROOT / result_doc_path).write_text(_result_markdown(dd259.json_native(report)), encoding="utf-8")
    dd259._atomic_json(
        RECOVERY,
        {
            "schema_id": "dd261-core-v3-c3c4-vapor-holdup-thirty-second-recovery-v1",
            "contract_payload_sha256": payload["contract_payload_sha256"],
            "status": "complete",
            "completed_endpoint_count": 120,
            "last_time_sec": 30.0,
            "journal_file_count": len(journal_paths),
            "result_path": result_path.as_posix(),
            "evidence_path": evidence_path.as_posix(),
            "result_sha256": _sha(result_path),
            "evidence_sha256": _sha(evidence_path),
        },
    )
    return dd259.json_native(report)


def _result_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# DD-261 Journaled Thirty-Second Vapor-Holdup Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Endpoint path: `{payload['recovered_endpoint_count']} recovered + {payload['continuation_endpoint_count']} continued = 120`.",
        f"- Final condenser duty: `{payload['final_condenser_duty_BTUph'] / 1.0e6:.6f} MMBTU/h`",
        f"- Final inventory change: `{payload['response']['total_inventory_change_lbmol']:.9e} lbmol`",
        f"- Component identity: `{payload['response']['component_inventory_identity_max_abs_lbmol']:.6e} lbmol`",
        f"- Energy identity relative: `{payload['response']['energy_identity_relative']:.6e}`",
        f"- Combined provider calls: `{payload['combined_provider_calls']}`",
        f"- Continuation wall: `{payload['continuation_wall_clock_sec']:.3f} s`; segment simulation/wall: `{payload['continuation_simulation_to_wall_ratio']:.5f}`",
        f"- Continuity: `{payload['continuity']}`",
        f"- Final refinement: `{payload['refinement']}`",
        f"- Gates: `{payload['gates']}`",
        "",
        "## Final stage profile",
        "",
        "| Volume | T (F) | P (psia) | N_L | N_V | L out | V out | xC3 | xC4 | xC5 | yC3 | yC4 | yC5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["final_stage_profile"]:
        liquid = "" if item["liquid_flow_out_lbmolph"] is None else f"{item['liquid_flow_out_lbmolph']:.3f}"
        vapor = "" if item["vapor_flow_out_lbmolph"] is None else f"{item['vapor_flow_out_lbmolph']:.3f}"
        x = item["liquid_mole_fractions"]
        y = item["vapor_mole_fractions"]
        lines.append(
            f"| {item['volume']} | {item['temperature_F']:.4f} | {item['pressure_psia']:.5f} | "
            f"{item['liquid_inventory_lbmol']:.5f} | {item['vapor_inventory_lbmol']:.5f} | {liquid} | {vapor} | "
            f"{x[0]:.6f} | {x[1]:.6f} | {x[2]:.6f} | {y[0]:.6f} | {y[1]:.6f} | {y[2]:.6f} |"
        )
    lines.extend(("", "DD-260 rerun, retry, controller, fallback, or extension: `False`", ""))
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.prepare:
        report = prepare(args.contract, args.contract_doc)
        print(dd259._json_text({
            "schema_id": report["schema_id"],
            "contract_payload_sha256": report["contract_payload_sha256"],
            "trajectory": report["trajectory"],
            "campaign_executed": report["campaign_executed"],
        }), end="")
        return 0
    report = execute(args.contract, args.result, args.result_doc, args.evidence)
    print(dd259._json_text({
        "classification": report["classification"],
        "pass_gate": report["pass_gate"],
        "decision": report["decision"],
    }), end="")
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
