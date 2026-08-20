#!/usr/bin/env python
"""Prepare or execute DD-271's bound-corrected controlled trajectory."""

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

import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_short_trajectory as dd267  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_five_second_trajectory as dd269  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_thirty_second_trajectory as dd270  # noqa: E402


SCHEMA = "dd271-core-v3-c3c4-vapor-holdup-terminal-control-bound-corrected-contract-v1"
RESULT_SCHEMA = "dd271-core-v3-c3c4-vapor-holdup-terminal-control-bound-corrected-result-v1"
CONTRACT = Path(
    "logs/dd271_core_v3_c3c4_vapor_holdup_terminal_control_bound_corrected_contract_20260820.json"
)
RESULT = Path(
    "logs/dd271_core_v3_c3c4_vapor_holdup_terminal_control_bound_corrected_20260820.json"
)
EVIDENCE = Path(
    "logs/dd271_core_v3_c3c4_vapor_holdup_terminal_control_bound_corrected_20260820.npz"
)
JOURNAL = Path(
    "logs/dd271_core_v3_c3c4_vapor_holdup_terminal_control_bound_corrected_journal_20260820"
)
CONTRACT_DOC = Path(
    "docs/dd_271_core_v3_c3c4_vapor_holdup_terminal_control_bound_corrected_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_271_core_v3_c3c4_vapor_holdup_terminal_control_bound_corrected_20260820.md"
)
SOURCE_RESULT = dd269.RESULT
SOURCE_EVIDENCE = dd269.EVIDENCE
SOURCE_ABORT = dd270.RESULT
SOURCE_JOURNAL = dd270.JOURNAL
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_terminal_control_thirty_second_bound_corrected.py"),
    Path("tools/run_core_v3_vapor_holdup_terminal_control_thirty_second_trajectory.py"),
    Path("tools/run_core_v3_vapor_holdup_terminal_control_five_second_trajectory.py"),
    Path("tools/run_core_v3_vapor_holdup_terminal_control_short_trajectory.py"),
    Path("tools/run_core_v3_vapor_holdup_terminal_control_stationary_hold.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_terminal_control_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/colored_jacobian_v1.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    source = json.loads((ROOT / SOURCE_RESULT).read_text(encoding="utf-8"))
    abort = json.loads((ROOT / SOURCE_ABORT).read_text(encoding="utf-8"))
    if not source.get("pass_gate"):
        raise RuntimeError("DD-271 requires the accepted DD-269 result")
    if abort.get("classification") != "vapor_holdup_terminal_control_thirty_second_aborted_at_product_bound":
        raise RuntimeError("DD-271 requires the preserved DD-270 bound abort")
    journal_sources = {
        (SOURCE_JOURNAL / f"endpoint_{index}.json").as_posix():
        _sha(SOURCE_JOURNAL / f"endpoint_{index}.json")
        for index in range(21, 27)
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": (
            "DD-270 authorizes one separately frozen product-bound semantics correction"
        ),
        "sources": {
            SOURCE_RESULT.as_posix(): _sha(SOURCE_RESULT),
            SOURCE_EVIDENCE.as_posix(): _sha(SOURCE_EVIDENCE),
            SOURCE_ABORT.as_posix(): _sha(SOURCE_ABORT),
            **journal_sources,
        },
        "implementation_sha256": {
            path.as_posix(): _sha(path) for path in IMPLEMENTATION
        },
        "trajectory": {
            "accepted_source_time_sec": 6.5,
            "source_replay_steps": 26,
            "nominal_continuation_steps": 94,
            "nominal_step_sec": 0.25,
            "nominal_final_time_sec": 30.0,
            "refinement_start_sec": 29.75,
            "refined_steps": 2,
            "refined_step_sec": 0.125,
        },
        "solver": {
            "method": "least_squares_trf_one_fresh_jacobian_per_root",
            "difference_step": 1.0e-5,
            "expected_color_count": 16,
            "x_scale": 1.0,
            "ftol": 1.0e-11,
            "xtol": 1.0e-11,
            "gtol": 1.0e-11,
            "max_nfev_per_root": 40,
            "acceptance_basis": (
                "residual and physical gates; SciPy termination status is reported"
            ),
        },
        "corrected_product_bounds": {
            "source": "contract.controllers.product_rate_ratio_bounds",
            "rate_ratio": [0.25, 2.0],
            "log_ratio": [float(np.log(0.25)), float(np.log(2.0))],
            "all_other_bounds_unchanged": True,
        },
        "limits": {
            "scaled_residual": 1.0e-8,
            "controller_residual": 1.0e-10,
            "rank": 262,
            "condition": 1.0e8,
            "component_identity_lbmol": 1.0e-6,
            "controller_aware_refinement_identity_lbmol": 1.0e-6,
            "maximum_step_temperature_F": 0.01,
            "maximum_step_pressure_psia": 0.01,
            "maximum_step_composition": 1.0e-4,
            "maximum_step_flow_relative": 1.0e-3,
            "maximum_step_phase_inventory_relative": 1.0e-3,
            "maximum_step_duty_relative": 1.0e-3,
            "maximum_step_product_relative": 1.0e-3,
            "refinement_component_l1_lbmol": 5.0e-4,
            "refinement_temperature_F": 1.0e-4,
            "refinement_pressure_psia": 1.0e-4,
            "refinement_flow_relative": 1.0e-4,
            "refinement_phase_transfer_scaled": 1.0e-3,
            "refinement_duty_relative": 1.0e-4,
            "refinement_level_fraction": 1.0e-6,
            "refinement_product_relative": 1.0e-5,
            "logical_provider_calls": 750000,
            "wall_clock_sec": 900.0,
        },
        "energy_identity": {
            "volume_count": 20,
            "energy_residual_scale_BTUph": 54_706_000.0,
            "aggregate_bound_from_scaled_residual": True,
        },
        "hard_stops": [
            "the saved one-second source cannot be replayed exactly enough to continue",
            "any new endpoint exceeds a residual, rank, condition, physical, controller, or continuity limit",
            "level or product direction reverses while the corresponding level error retains its sign",
            "component or residual-consistent energy conservation fails",
            "nominal/refined inventory difference is not explained by integrated boundary histories",
            "a non-inventory refinement limit fails",
            "more than one Jacobian is built in any new root",
            "a retry, alternate grid, tuning change, fallback, parallel worker, or extension occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    if (ROOT / contract_path).exists() or (ROOT / contract_doc_path).exists():
        raise RuntimeError("DD-271 contract artifact already exists")
    (ROOT / contract_path).write_text(_json_text(payload), encoding="utf-8")
    (ROOT / contract_doc_path).write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    trajectory = payload["trajectory"]
    return "\n".join(
        (
            "# DD-271 Bound-Corrected Controlled Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Saved replay: `{trajectory['source_replay_steps']}` endpoints through `{trajectory['accepted_source_time_sec']} s` without solving.",
            f"- New continuation: `{trajectory['nominal_continuation_steps']}` x `{trajectory['nominal_step_sec']} s` to `{trajectory['nominal_final_time_sec']} s`.",
            f"- Final refinement: `{trajectory['refined_steps']}` x `{trajectory['refined_step_sec']} s` from `{trajectory['refinement_start_sec']} s`.",
            "- Product-output log bounds come from the existing physical rate-ratio contract: `log(0.25)` to `log(2.0)`.",
            "- Each new root receives one fresh 16-color Jacobian held only within that root.",
            "- Refinement inventory differences must equal differences in integrated controlled boundaries.",
            "- Endpoint journals, final profile, conservation, continuity, provider, call, and wall gates are mandatory.",
            "- Retry, alternate grid, tuning change, fallback, parallel worker, or extension: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-271 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-271 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-271 implementation changed: {path}")
    if any((ROOT / path).exists() for path in (RESULT, EVIDENCE, JOURNAL)):
        raise RuntimeError("DD-271 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _journal(index: int | str, time_sec: float, report: Mapping[str, Any], coordinates: np.ndarray) -> None:
    destination = ROOT / JOURNAL / f"endpoint_{index}.json"
    if destination.exists():
        raise RuntimeError(f"DD-271 journal collision: {destination}")
    destination.write_text(
        _json_text(
            {
                "schema_id": "dd271-controlled-endpoint-journal-v1",
                "index": index,
                "time_sec": time_sec,
                "report": report,
                "coordinates": coordinates.tolist(),
            }
        ),
        encoding="utf-8",
    )


def _replay_source(context: Mapping[str, Any]) -> dict[str, Any]:
    source = json.loads((ROOT / SOURCE_RESULT).read_text(encoding="utf-8"))
    evidence = np.load(ROOT / SOURCE_EVIDENCE)
    coordinates = np.asarray(evidence["nominal_coordinates"], dtype=float)
    memories = np.asarray(evidence["nominal_controller_memory"], dtype=float)
    coordinate_rows = [row.copy() for row in coordinates]
    memory_rows = [row.copy() for row in memories]
    reports = list(source["nominal_endpoints"])
    hold = json.loads((ROOT / dd267.SOURCE_HOLD).read_text(encoding="utf-8"))
    memory_previous = np.asarray(
        hold["terminal"]["controller_memory_previous"], dtype=float
    )
    reference = context["reference"]
    evaluations: list[Any] = []
    for index in range(20):
        evaluation = dd267._evaluate(
            context,
            reference,
            memory_previous,
            coordinates[index],
            0.25,
            f"dd271:source_replay_{index + 1}",
            "residual",
        )
        if np.max(np.abs(evaluation.controller_memory_endpoint - memories[index])) > 1.0e-12:
            raise RuntimeError("DD-271 DD-269 controller-memory parity failed")
        evaluations.append(evaluation)
        reference = dd249._next_reference(reference, evaluation.base)
        memory_previous = evaluation.controller_memory_endpoint.copy()
    for index in range(21, 27):
        saved = json.loads(
            (ROOT / SOURCE_JOURNAL / f"endpoint_{index}.json").read_text(
                encoding="utf-8"
            )
        )
        row = np.asarray(saved["coordinates"], dtype=float)
        evaluation = dd267._evaluate(
            context,
            reference,
            memory_previous,
            row,
            0.25,
            f"dd271:dd270_replay_{index}",
            "residual",
        )
        saved_memory = np.asarray(
            saved["report"]["controller_memory_endpoint"], dtype=float
        )
        if np.max(np.abs(evaluation.controller_memory_endpoint - saved_memory)) > 1.0e-12:
            raise RuntimeError("DD-271 DD-270 controller-memory parity failed")
        evaluations.append(evaluation)
        coordinate_rows.append(row.copy())
        memory_rows.append(saved_memory.copy())
        reports.append(saved["report"])
        reference = dd249._next_reference(reference, evaluation.base)
        memory_previous = evaluation.controller_memory_endpoint.copy()
    final_report = reports[-1]
    final = evaluations[-1]
    parity = {
        "distillate_lbmolph": abs(
            final.distillate_lbmolph - float(final_report["distillate_lbmolph"])
        ),
        "bottoms_lbmolph": abs(
            final.bottoms_lbmolph - float(final_report["bottoms_lbmolph"])
        ),
        "level_fraction": float(
            np.max(
                np.abs(
                    final.level_fraction
                    - np.asarray(final_report["level_fraction"], dtype=float)
                )
            )
        ),
    }
    if max(parity.values()) > 1.0e-10:
        raise RuntimeError("DD-271 source endpoint parity failed")
    return {
        "evaluations": evaluations,
        "coordinates": np.stack(coordinate_rows),
        "memories": np.stack(memory_rows),
        "reference": reference,
        "memory": memory_previous,
        "prior": final,
        "parity": parity,
        "reports": reports,
    }


def execute(contract_path: Path) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path)
    context = dd267._context()
    replay = _replay_source(context)
    (ROOT / JOURNAL).mkdir(parents=True, exist_ok=False)
    initial_reference = context["reference"]
    initial_products = np.asarray(
        (
            float(context["balance_inputs"].distillate_lbmolph),
            float(context["balance_inputs"].bottoms_lbmolph),
        )
    )
    reference = replay["reference"]
    memory = replay["memory"]
    coordinates = replay["coordinates"][-1].copy()
    prior = replay["prior"]
    nominal_evaluations = list(replay["evaluations"])
    nominal_coordinates = [row.copy() for row in replay["coordinates"]]
    nominal_memories = [row.copy() for row in replay["memories"]]
    nominal_reports = list(replay["reports"])
    new_reports: list[dict[str, Any]] = []
    matrices: list[np.ndarray] = []
    branch = None
    started = time.perf_counter()
    for index in range(27, 121):
        coordinates, final, report, matrix = dd267._solve_endpoint(
            context,
            payload,
            reference,
            memory,
            coordinates,
            prior,
            0.25,
            f"dd271:nominal_{index}",
        )
        time_sec = index * 0.25
        report.update({"index": index, "time_sec": time_sec})
        _journal(index, time_sec, report, coordinates)
        nominal_evaluations.append(final)
        nominal_coordinates.append(coordinates.copy())
        nominal_memories.append(final.controller_memory_endpoint.copy())
        nominal_reports.append(report)
        new_reports.append(report)
        matrices.append(matrix)
        reference = dd249._next_reference(reference, final.base)
        memory = final.controller_memory_endpoint.copy()
        prior = final
        if index == 119:
            branch = (reference, memory.copy(), coordinates.copy(), final)
        if index % 4 == 0:
            print(
                f"DD-271 accepted endpoint {index}/120 "
                f"(t={time_sec:.2f} s, residual={report['scaled_residual_inf_norm']:.2e})",
                flush=True,
            )
    if branch is None:
        raise RuntimeError("DD-271 refinement branch was not captured")
    refined_reference, refined_memory, refined_coordinates, refined_prior = branch
    refined_evaluations: list[Any] = []
    refined_reports: list[dict[str, Any]] = []
    refined_coordinate_rows: list[np.ndarray] = []
    refined_memory_rows: list[np.ndarray] = []
    for index in range(1, 3):
        refined_coordinates, final, report, matrix = dd267._solve_endpoint(
            context,
            payload,
            refined_reference,
            refined_memory,
            refined_coordinates,
            refined_prior,
            0.125,
            f"dd271:refined_{index}",
        )
        time_sec = 29.75 + index * 0.125
        report.update({"index": index, "time_sec": time_sec})
        _journal(f"refined_{index}", time_sec, report, refined_coordinates)
        refined_evaluations.append(final)
        refined_reports.append(report)
        refined_coordinate_rows.append(refined_coordinates.copy())
        refined_memory_rows.append(final.controller_memory_endpoint.copy())
        new_reports.append(report)
        matrices.append(matrix)
        refined_reference = dd249._next_reference(refined_reference, final.base)
        refined_memory = final.controller_memory_endpoint.copy()
        refined_prior = final
    wall = time.perf_counter() - started
    nominal_response = dd267._response(
        initial_reference, nominal_evaluations, [0.25] * 120
    )
    refined_path = [*nominal_evaluations[:119], *refined_evaluations]
    refined_response = dd267._response(
        initial_reference, refined_path, [0.25] * 119 + [0.125, 0.125]
    )
    continuity = dd267._continuity(
        initial_reference, nominal_evaluations, initial_products
    )
    refinement = dd267._refinement(
        nominal_evaluations[-1], refined_evaluations[-1], initial_reference
    )
    levels = np.asarray(
        [evaluation.level_fraction for evaluation in nominal_evaluations]
    )
    products = np.asarray(
        [
            (evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph)
            for evaluation in nominal_evaluations
        ]
    )
    limits = payload["limits"]
    energy_bound = (
        int(payload["energy_identity"]["volume_count"])
        * float(limits["scaled_residual"])
        * float(payload["energy_identity"]["energy_residual_scale_BTUph"])
        * 30.0
        / 3600.0
    )
    nominal_actual = np.asarray(
        nominal_response["actual_component_change_lbmol"], dtype=float
    )
    refined_actual = np.asarray(
        refined_response["actual_component_change_lbmol"], dtype=float
    )
    nominal_expected = np.asarray(
        nominal_response["expected_component_change_lbmol"], dtype=float
    )
    refined_expected = np.asarray(
        refined_response["expected_component_change_lbmol"], dtype=float
    )
    refinement_unexplained = (nominal_actual - refined_actual) - (
        nominal_expected - refined_expected
    )
    endpoint_gate = all(
        report["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and report["controller_residual_inf_norm"] < limits["controller_residual"]
        and report["jacobian_rank"] == limits["rank"]
        and report["jacobian_condition"] < limits["condition"]
        and report["physical_pass"]
        and report["controller_memory_recurrence_error"] < 1.0e-14
        and report["jacobian_build_count"] == 1
        and report["color_count"] == payload["solver"]["expected_color_count"]
        for report in new_reports
    )
    gates = {
        "source_replay_parity": max(replay["parity"].values()) < 1.0e-10,
        "new_endpoints": endpoint_gate,
        "nominal_complete": len(nominal_evaluations) == 120,
        "refinement_complete": len(refined_evaluations) == 2,
        "drum_level_monotonic_toward_setpoint": bool(np.all(np.diff(levels[:, 0]) > 0.0)),
        "sump_level_monotonic_toward_setpoint": bool(np.all(np.diff(levels[:, 1]) < 0.0)),
        "distillate_monotonic": bool(np.all(np.diff(products[:, 0]) < 0.0)),
        "bottoms_monotonic": bool(np.all(np.diff(products[:, 1]) > 0.0)),
        "component_identity_nominal": nominal_response["component_identity_max_abs_lbmol"]
        < limits["component_identity_lbmol"],
        "component_identity_refined": refined_response["component_identity_max_abs_lbmol"]
        < limits["component_identity_lbmol"],
        "energy_identity_nominal": nominal_response["energy_identity_absolute_BTU"]
        < energy_bound,
        "energy_identity_refined": refined_response["energy_identity_absolute_BTU"]
        < energy_bound,
        "continuity": bool(
            continuity["temperature_F"] < limits["maximum_step_temperature_F"]
            and continuity["pressure_psia"] < limits["maximum_step_pressure_psia"]
            and continuity["composition"] < limits["maximum_step_composition"]
            and continuity["flow_relative"] < limits["maximum_step_flow_relative"]
            and continuity["phase_inventory_relative"]
            < limits["maximum_step_phase_inventory_relative"]
            and continuity["duty_relative"] < limits["maximum_step_duty_relative"]
            and continuity["product_relative"] < limits["maximum_step_product_relative"]
        ),
        "controller_aware_refinement_identity": float(
            np.max(np.abs(refinement_unexplained))
        )
        < limits["controller_aware_refinement_identity_lbmol"],
        "refinement": bool(
            refinement["component_l1_lbmol"] < limits["refinement_component_l1_lbmol"]
            and refinement["temperature_F"] < limits["refinement_temperature_F"]
            and refinement["pressure_psia"] < limits["refinement_pressure_psia"]
            and refinement["flow_relative"] < limits["refinement_flow_relative"]
            and refinement["phase_transfer_scaled"]
            < limits["refinement_phase_transfer_scaled"]
            and refinement["duty_relative"] < limits["refinement_duty_relative"]
            and refinement["level_fraction"] < limits["refinement_level_fraction"]
            and refinement["product_relative"] < limits["refinement_product_relative"]
        ),
        "provider": bool(
            context["audit"].report()["pass"]
            and not context["audit"].fallback_attempted
        ),
        "calls": context["audit"].record_count < limits["logical_provider_calls"],
        "wall": wall < limits["wall_clock_sec"],
        "product_outputs_within_contract_bounds": bool(
            np.all(
                products
                >= initial_products
                * float(payload["corrected_product_bounds"]["rate_ratio"][0])
            )
            and np.all(
                products
                <= initial_products
                * float(payload["corrected_product_bounds"]["rate_ratio"][1])
            )
        ),
        "one_fresh_jacobian_per_new_root": len(matrices) == 96,
        "journals_complete": len(list((ROOT / JOURNAL).glob("endpoint_*.json"))) == 96,
        "no_retry_or_alternate": True,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "vapor_holdup_terminal_control_bound_corrected_passed"
            if passed
            else "vapor_holdup_terminal_control_bound_corrected_failed"
        ),
        "decision": (
            "authorize_separately_frozen_extended_controlled_trajectory_contract"
            if passed
            else "stop_controlled_trajectory_extension"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "source_replay_parity": replay["parity"],
        "nominal_endpoints": nominal_reports,
        "new_endpoint_reports": new_reports,
        "refined_endpoints": refined_reports,
        "nominal_response": nominal_response,
        "refined_response": refined_response,
        "energy_identity_bound_BTU": energy_bound,
        "continuity": continuity,
        "refinement": refinement,
        "controller_aware_refinement_unexplained_component_lbmol": refinement_unexplained.tolist(),
        "controller_aware_refinement_unexplained_max_abs_lbmol": float(
            np.max(np.abs(refinement_unexplained))
        ),
        "final_profile": dd267._profile(context, nominal_evaluations[-1]),
        "component_names": list(context["contract"].base.component_names),
        "provider": dd267.compact_provider_report(context["audit"].report()),
        "logical_provider_calls": context["audit"].record_count,
        "wall_clock_sec": wall,
        "simulation_wall_ratio": 25.0 / max(wall, 1.0e-300),
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "tuning_change_attempted": False,
        "parallel_worker_attempted": False,
        "longer_trajectory_attempted": False,
    }
    (ROOT / RESULT).write_text(_json_text(report), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(_result_markdown(report), encoding="utf-8")
    np.savez_compressed(
        ROOT / EVIDENCE,
        nominal_coordinates=np.stack(nominal_coordinates),
        nominal_controller_memory=np.stack(nominal_memories),
        refined_coordinates=np.stack(refined_coordinate_rows),
        refined_controller_memory=np.stack(refined_memory_rows),
        **{f"jacobian_new_root_{index}": matrix for index, matrix in enumerate(matrices, 1)},
    )
    return report


def _result_markdown(report: Mapping[str, Any]) -> str:
    final = report["nominal_endpoints"][-1]
    return "\n".join(
        (
            "# DD-271 Bound-Corrected Controlled Trajectory Result",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Nominal endpoints: `{len(report['nominal_endpoints'])}` through `30.0 s`",
            f"- New/refined roots: `{len(report['new_endpoint_reports']) - len(report['refined_endpoints'])} / {len(report['refined_endpoints'])}`",
            f"- Final drum/sump levels: `{final['level_fraction']}`",
            f"- Final D/B: `{final['distillate_lbmolph']:.6f} / {final['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Component identity, nominal/refined: `{report['nominal_response']['component_identity_max_abs_lbmol']:.6e} / {report['refined_response']['component_identity_max_abs_lbmol']:.6e} lbmol`",
            f"- Controller-aware refinement error: `{report['controller_aware_refinement_unexplained_max_abs_lbmol']:.6e} lbmol`",
            f"- Provider calls: `{report['logical_provider_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            f"- Gates: `{report['gates']}`",
            "- Retry, alternate grid, tuning change, parallel worker, or extension: `False`",
            "",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.prepare:
        report = prepare(args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": report["schema_id"],
                    "contract_payload_sha256": report["contract_payload_sha256"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "failed_gates": [
                    key for key, value in report["gates"].items() if not value
                ],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
