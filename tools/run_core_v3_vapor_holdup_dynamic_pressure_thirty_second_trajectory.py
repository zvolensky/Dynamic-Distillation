#!/usr/bin/env python
"""Prepare or execute DD-274's thirty-second dynamic-pressure trajectory."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_vapor_holdup_dynamic_pressure_residual as dd273  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_terminal_control_short_trajectory as dd267  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dynamic_pressure_contract,
    build_vapor_holdup_dynamic_pressure_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_implicit_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_dynamic_pressure_implicit_residual,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_implicit_residual_v1 import (  # noqa: E402
    controlled_implicit_initial_coordinates,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_zero_time_v1 import (  # noqa: E402
    vapor_holdup_terminal_control_pattern,
)


SCHEMA = "dd274-core-v3-c3c4-vapor-holdup-dynamic-pressure-thirty-second-contract-v1"
RESULT_SCHEMA = "dd274-core-v3-c3c4-vapor-holdup-dynamic-pressure-thirty-second-result-v1"
CONTRACT = Path("logs/dd274_core_v3_c3c4_vapor_holdup_dynamic_pressure_thirty_second_contract_20260820.json")
RESULT = Path("logs/dd274_core_v3_c3c4_vapor_holdup_dynamic_pressure_thirty_second_20260820.json")
EVIDENCE = Path("logs/dd274_core_v3_c3c4_vapor_holdup_dynamic_pressure_thirty_second_20260820.npz")
JOURNAL = Path("logs/dd274_core_v3_c3c4_vapor_holdup_dynamic_pressure_thirty_second_journal_20260820")
CONTRACT_DOC = Path("docs/dd_274_core_v3_c3c4_vapor_holdup_dynamic_pressure_thirty_second_contract_20260820.md")
RESULT_DOC = Path("docs/dd_274_core_v3_c3c4_vapor_holdup_dynamic_pressure_thirty_second_20260820.md")
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_dynamic_pressure_thirty_second_trajectory.py"),
    Path("tools/audit_core_v3_vapor_holdup_dynamic_pressure_residual.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_dynamic_pressure_contract_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_dynamic_pressure_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_terminal_control_implicit_residual_v1.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def prepare() -> dict[str, Any]:
    source = json.loads((ROOT / dd273.RESULT).read_text(encoding="utf-8"))
    if not source.get("pass_gate"):
        raise RuntimeError("DD-274 requires the accepted DD-273 audit")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": "DD-273 authorizes one frozen thirty-second fixed-duty pressure-dynamic trajectory",
        "sources": {
            dd273.RESULT.as_posix(): _sha(dd273.RESULT),
            dd273.EVIDENCE.as_posix(): _sha(dd273.EVIDENCE),
            dd273.SOURCE_RESULT.as_posix(): _sha(dd273.SOURCE_RESULT),
            dd273.SOURCE_EVIDENCE.as_posix(): _sha(dd273.SOURCE_EVIDENCE),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "trajectory": {
            "accepted_handoff": "DD-271 endpoint at 30 seconds",
            "nominal_steps": 120,
            "nominal_step_sec": 0.25,
            "nominal_final_time_sec": 30.0,
            "refinement_start_sec": 29.75,
            "refined_steps": 2,
            "refined_step_sec": 0.125,
            "specified_condenser_duty_BTUph": source["specified_condenser_duty_BTUph"],
            "pressure_controller_active": False,
            "terminal_level_controllers_active": True,
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
        },
        "limits": {
            "scaled_residual": 1.0e-8,
            "controller_residual": 1.0e-10,
            "fixed_duty_relative_error": 1.0e-10,
            "rank": 262,
            "condition": 1.0e8,
            "component_identity_lbmol": 1.0e-6,
            "energy_identity_BTU": 0.1,
            "controller_aware_refinement_identity_lbmol": 1.0e-6,
            "maximum_step_temperature_F": 0.01,
            "maximum_step_pressure_psia": 0.01,
            "maximum_step_composition": 1.0e-4,
            "maximum_step_flow_relative": 1.0e-3,
            "maximum_step_phase_inventory_relative": 1.0e-3,
            "maximum_step_product_relative": 1.0e-3,
            "maximum_total_pressure_drift_psia": 5.0,
            "refinement_component_l1_lbmol": 5.0e-4,
            "refinement_temperature_F": 1.0e-4,
            "refinement_pressure_psia": 1.0e-4,
            "refinement_flow_relative": 1.0e-4,
            "refinement_phase_transfer_scaled": 1.0e-3,
            "refinement_level_fraction": 1.0e-6,
            "refinement_product_relative": 1.0e-5,
            "logical_provider_calls": 750000,
            "wall_clock_sec": 900.0,
        },
        "hard_stops": [
            "the accepted DD-271 handoff cannot be replayed",
            "any root fails residual, rank, condition, physical, controller, fixed-duty, or continuity gates",
            "pressure becomes nonpositive, unordered, discontinuous, or drifts by more than five psi",
            "component or residual-consistent energy conservation fails",
            "the final half-step refinement fails",
            "a retry, alternate grid, tuning change, fallback, pressure controller, or extension occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    if any((ROOT / path).exists() for path in (CONTRACT, CONTRACT_DOC)):
        raise RuntimeError("DD-274 contract already exists")
    (ROOT / CONTRACT).write_text(_json(payload), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    run = payload["trajectory"]
    return "\n".join(
        (
            "# DD-274 Dynamic-Pressure Thirty-Second Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Start: `{run['accepted_handoff']}`.",
            f"- Nominal path: `{run['nominal_steps']}` x `{run['nominal_step_sec']} s`.",
            f"- Condenser duty: `{run['specified_condenser_duty_BTUph']:.6f} BTU/h` fixed.",
            "- Reflux-drum pressure is dynamic; no pressure controller is active.",
            "- Drum and sump geometry-based level controllers remain active.",
            "- One fresh 16-color Jacobian is allowed per root; final half-step refinement is mandatory.",
            "- Retry, alternate grid, tuning, fallback, or extension: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-274 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-274 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-274 implementation changed: {path}")
    if any((ROOT / path).exists() for path in (RESULT, EVIDENCE, JOURNAL)):
        raise RuntimeError("DD-274 result exists; rerun is prohibited")
    _git("ls-files", "--error-unmatch", CONTRACT.as_posix())


def _evaluate(
    context: Mapping[str, Any],
    reference: Any,
    memory: np.ndarray,
    coordinates: np.ndarray,
    timestep_sec: float,
    specified_duty: float,
    state_id: str,
    evaluation_kind: str = "jacobian",
):
    return evaluate_vapor_holdup_dynamic_pressure_implicit_residual(
        context["contract"],
        context["geometry"],
        reference,
        context["balance_inputs"],
        context["spec"].hydraulic_geometry,
        replace(context["numerical"], timestep_sec=float(timestep_sec)),
        context["provider"],
        context["audit"],
        coordinates,
        controller_memory_previous=memory,
        specified_condenser_duty_BTUph=specified_duty,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )


def _solve_endpoint(
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    reference: Any,
    memory: np.ndarray,
    previous_coordinates: np.ndarray,
    previous_evaluation: Any,
    timestep_sec: float,
    specified_duty: float,
    root_name: str,
):
    pattern = vapor_holdup_terminal_control_pattern(context["contract"])
    lower, upper = dd267.dd265._bounds(context["contract"])
    point = controlled_implicit_initial_coordinates(
        context["contract"],
        controller_rates_per_sec=previous_evaluation.controller_rate_per_sec,
        timestep_sec=timestep_sec,
        previous_coordinates=previous_coordinates,
        product_log_ratios_previous=previous_evaluation.product_log_ratio,
    )
    cached_matrix: np.ndarray | None = None
    groups_used = 0
    calls = 0

    def objective(candidate: np.ndarray, state_id: str = "residual") -> np.ndarray:
        nonlocal calls
        calls += 1
        return _evaluate(
            context, reference, memory, candidate, timestep_sec, specified_duty,
            f"{root_name}:{state_id}:{calls}",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal cached_matrix, groups_used
        if cached_matrix is None:
            cached_matrix, groups = colored_central_difference_jacobian(
                objective,
                candidate,
                pattern=pattern,
                step=float(payload["solver"]["difference_step"]),
                state_id=f"{root_name}:jacobian",
            )
            groups_used = len(groups)
        return cached_matrix

    solution = least_squares(
        objective,
        point,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=float(payload["solver"]["x_scale"]),
        ftol=float(payload["solver"]["ftol"]),
        xtol=float(payload["solver"]["xtol"]),
        gtol=float(payload["solver"]["gtol"]),
        max_nfev=int(payload["solver"]["max_nfev_per_root"]),
        verbose=0,
    )
    final = _evaluate(
        context, reference, memory, solution.x, timestep_sec, specified_duty,
        f"{root_name}:accepted", "residual",
    )
    if cached_matrix is None:
        raise RuntimeError("DD-274 root did not build its required Jacobian")
    rank, condition, _ = dd249._rank_condition(cached_matrix)
    memory_error = float(
        np.max(
            np.abs(
                final.controller_memory_endpoint
                - memory
                - timestep_sec * final.controller_rate_per_sec
            )
        )
    )
    endpoint = final.base.endpoint
    topology = context["contract"].base.topology.column
    top = topology.top_volume
    top_tray = next(source for source, destination, _name in topology.vapor_links if destination == top)
    top_index = topology.volume_ids.index(top)
    tray_index = topology.volume_ids.index(top_tray)
    duty_error = abs(endpoint.condenser_duty_BTUph / specified_duty - 1.0)
    report = {
        "scipy_success": bool(solution.success),
        "scipy_status": int(solution.status),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "function_calls_observed": calls,
        "jacobian_build_count": 1,
        "color_count": groups_used,
        "scaled_residual_inf_norm": float(np.max(np.abs(final.scaled))),
        "controller_residual_inf_norm": float(np.max(np.abs(final.scaled[-4:]))),
        "jacobian_rank": rank,
        "jacobian_condition": condition,
        "physical_pass": dd267._physical(final),
        "controller_memory_recurrence_error": memory_error,
        "fixed_duty_relative_error": duty_error,
        "condenser_duty_BTUph": float(endpoint.condenser_duty_BTUph),
        "reflux_drum_pressure_psia": float(endpoint.pressure_psia[top_index]),
        "top_tray_pressure_psia": float(endpoint.pressure_psia[tray_index]),
        "bottom_pressure_psia": float(endpoint.pressure_psia[-1]),
        "top_tray_minus_drum_pressure_psia": float(
            endpoint.pressure_psia[tray_index] - endpoint.pressure_psia[top_index]
        ),
        "level_fraction": final.level_fraction.tolist(),
        "controller_memory_endpoint": final.controller_memory_endpoint.tolist(),
        "controller_rate_per_sec": final.controller_rate_per_sec.tolist(),
        "product_log_ratio": final.product_log_ratio.tolist(),
        "distillate_lbmolph": final.distillate_lbmolph,
        "bottoms_lbmolph": final.bottoms_lbmolph,
    }
    return solution.x.copy(), final, report, cached_matrix


def _journal(index: str, time_sec: float, report: Mapping[str, Any], coordinates: np.ndarray) -> None:
    destination = ROOT / JOURNAL / f"endpoint_{index}.json"
    if destination.exists():
        raise RuntimeError(f"DD-274 journal collision: {destination}")
    destination.write_text(
        _json({"schema_id": "dd274-pressure-endpoint-journal-v1", "index": index, "time_sec": time_sec, "report": report, "coordinates": coordinates.tolist()}),
        encoding="utf-8",
    )


def execute() -> dict[str, Any]:
    payload = json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))
    _verify(payload)
    original_context = dd267._context()
    replay = dd273._replay(original_context)
    successor = build_vapor_holdup_dynamic_pressure_contract(original_context["contract"])
    structure = audit_vapor_holdup_dynamic_pressure_contract(successor)
    if not structure.pass_gate:
        raise RuntimeError("DD-274 successor structure failed")
    context = {**original_context, "contract": successor}
    specified_duty = float(payload["trajectory"]["specified_condenser_duty_BTUph"])
    initial_reference = replay["reference"]
    initial_products = np.asarray((replay["final"].distillate_lbmolph, replay["final"].bottoms_lbmolph))
    reference = initial_reference
    memory = replay["memory"]
    prior = replay["final"]
    coordinates = np.zeros(len(successor.rows), dtype=float)
    evaluations: list[Any] = []
    coordinate_rows: list[np.ndarray] = []
    memory_rows: list[np.ndarray] = []
    reports: list[dict[str, Any]] = []
    matrices: list[np.ndarray] = []
    branch = None
    (ROOT / JOURNAL).mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    for index in range(1, 121):
        coordinates, final, endpoint_report, matrix = _solve_endpoint(
            context, payload, reference, memory, coordinates, prior, 0.25,
            specified_duty, f"dd274:nominal_{index}",
        )
        time_sec = index * 0.25
        endpoint_report.update({"index": index, "time_sec": time_sec})
        _journal(f"nominal_{index}", time_sec, endpoint_report, coordinates)
        evaluations.append(final)
        coordinate_rows.append(coordinates.copy())
        memory_rows.append(final.controller_memory_endpoint.copy())
        reports.append(endpoint_report)
        matrices.append(matrix)
        reference = dd249._next_reference(reference, final.base)
        memory = final.controller_memory_endpoint.copy()
        prior = final
        if index == 119:
            branch = (reference, memory.copy(), coordinates.copy(), final)
        if index % 20 == 0:
            print(
                f"DD-274 t={time_sec:5.2f} s: Pdrum={endpoint_report['reflux_drum_pressure_psia']:.6f}, "
                f"Ptop={endpoint_report['top_tray_pressure_psia']:.6f}, "
                f"Pbottom={endpoint_report['bottom_pressure_psia']:.6f} psia",
                flush=True,
            )
    if branch is None:
        raise RuntimeError("DD-274 refinement branch was not captured")
    refined_reference, refined_memory, refined_coordinates, refined_prior = branch
    refined_evaluations: list[Any] = []
    refined_reports: list[dict[str, Any]] = []
    refined_coordinate_rows: list[np.ndarray] = []
    refined_memory_rows: list[np.ndarray] = []
    for index in range(1, 3):
        refined_coordinates, final, endpoint_report, matrix = _solve_endpoint(
            context, payload, refined_reference, refined_memory, refined_coordinates,
            refined_prior, 0.125, specified_duty, f"dd274:refined_{index}",
        )
        time_sec = 29.75 + index * 0.125
        endpoint_report.update({"index": index, "time_sec": time_sec})
        _journal(f"refined_{index}", time_sec, endpoint_report, refined_coordinates)
        refined_evaluations.append(final)
        refined_reports.append(endpoint_report)
        refined_coordinate_rows.append(refined_coordinates.copy())
        refined_memory_rows.append(final.controller_memory_endpoint.copy())
        matrices.append(matrix)
        refined_reference = dd249._next_reference(refined_reference, final.base)
        refined_memory = final.controller_memory_endpoint.copy()
        refined_prior = final
    wall = time.perf_counter() - started
    nominal_response = dd267._response(initial_reference, evaluations, [0.25] * 120)
    refined_path = [*evaluations[:119], *refined_evaluations]
    refined_response = dd267._response(initial_reference, refined_path, [0.25] * 119 + [0.125, 0.125])
    continuity = dd267._continuity(initial_reference, evaluations, initial_products)
    refinement = dd267._refinement(evaluations[-1], refined_evaluations[-1], initial_reference)
    nominal_actual = np.asarray(nominal_response["actual_component_change_lbmol"])
    refined_actual = np.asarray(refined_response["actual_component_change_lbmol"])
    nominal_expected = np.asarray(nominal_response["expected_component_change_lbmol"])
    refined_expected = np.asarray(refined_response["expected_component_change_lbmol"])
    unexplained = (nominal_actual - refined_actual) - (nominal_expected - refined_expected)
    limits = payload["limits"]
    pressure = np.asarray(
        [[item["reflux_drum_pressure_psia"], item["top_tray_pressure_psia"], item["bottom_pressure_psia"]] for item in reports]
    )
    initial_pressure = np.asarray((initial_reference.pressure_psia[0], initial_reference.pressure_psia[1], initial_reference.pressure_psia[-1]))
    total_pressure_drift = np.max(np.abs(pressure - initial_pressure), axis=0)
    endpoint_gate = all(
        item["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and item["controller_residual_inf_norm"] < limits["controller_residual"]
        and item["fixed_duty_relative_error"] < limits["fixed_duty_relative_error"]
        and item["jacobian_rank"] == limits["rank"]
        and item["jacobian_condition"] < limits["condition"]
        and item["physical_pass"]
        and item["controller_memory_recurrence_error"] < 1.0e-14
        and item["jacobian_build_count"] == 1
        and item["color_count"] == payload["solver"]["expected_color_count"]
        for item in (*reports, *refined_reports)
    )
    gates = {
        "source_replay": max(replay["parity"].values()) < 1.0e-10,
        "structure": structure.pass_gate,
        "endpoints": endpoint_gate,
        "nominal_complete": len(evaluations) == 120,
        "refinement_complete": len(refined_evaluations) == 2,
        "pressure_dynamic": bool(np.max(np.abs(pressure[-1] - initial_pressure)) > 1.0e-10),
        "pressure_bounded": bool(np.max(total_pressure_drift) < limits["maximum_total_pressure_drift_psia"]),
        "component_identity_nominal": nominal_response["component_identity_max_abs_lbmol"] < limits["component_identity_lbmol"],
        "component_identity_refined": refined_response["component_identity_max_abs_lbmol"] < limits["component_identity_lbmol"],
        "energy_identity_nominal": nominal_response["energy_identity_absolute_BTU"] < limits["energy_identity_BTU"],
        "energy_identity_refined": refined_response["energy_identity_absolute_BTU"] < limits["energy_identity_BTU"],
        "continuity": bool(
            continuity["temperature_F"] < limits["maximum_step_temperature_F"]
            and continuity["pressure_psia"] < limits["maximum_step_pressure_psia"]
            and continuity["composition"] < limits["maximum_step_composition"]
            and continuity["flow_relative"] < limits["maximum_step_flow_relative"]
            and continuity["phase_inventory_relative"] < limits["maximum_step_phase_inventory_relative"]
            and continuity["product_relative"] < limits["maximum_step_product_relative"]
        ),
        "refinement_identity": float(np.max(np.abs(unexplained))) < limits["controller_aware_refinement_identity_lbmol"],
        "refinement": bool(
            refinement["component_l1_lbmol"] < limits["refinement_component_l1_lbmol"]
            and refinement["temperature_F"] < limits["refinement_temperature_F"]
            and refinement["pressure_psia"] < limits["refinement_pressure_psia"]
            and refinement["flow_relative"] < limits["refinement_flow_relative"]
            and refinement["phase_transfer_scaled"] < limits["refinement_phase_transfer_scaled"]
            and refinement["level_fraction"] < limits["refinement_level_fraction"]
            and refinement["product_relative"] < limits["refinement_product_relative"]
        ),
        "provider": bool(context["audit"].report()["pass"] and not context["audit"].fallback_attempted),
        "calls": context["audit"].record_count < limits["logical_provider_calls"],
        "wall": wall < limits["wall_clock_sec"],
        "journals": len(list((ROOT / JOURNAL).glob("endpoint_*.json"))) == 122,
        "no_retry_or_alternate": True,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    pressure_series = [
        {
            "time_sec": 0.0,
            "reflux_drum_pressure_psia": float(initial_pressure[0]),
            "top_tray_pressure_psia": float(initial_pressure[1]),
            "bottom_pressure_psia": float(initial_pressure[2]),
        },
        *[
            {
                "time_sec": item["time_sec"],
                "reflux_drum_pressure_psia": item["reflux_drum_pressure_psia"],
                "top_tray_pressure_psia": item["top_tray_pressure_psia"],
                "bottom_pressure_psia": item["bottom_pressure_psia"],
            }
            for item in reports
        ],
    ]
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": "vapor_holdup_dynamic_pressure_thirty_second_passed" if passed else "vapor_holdup_dynamic_pressure_thirty_second_failed",
        "decision": "pressure_response_available_for_assessment" if passed else "stop_pressure_dynamic_path",
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "specified_condenser_duty_BTUph": specified_duty,
        "source_replay_parity": replay["parity"],
        "nominal_endpoints": reports,
        "refined_endpoints": refined_reports,
        "pressure_time_series": pressure_series,
        "pressure_total_drift_psia": {
            "reflux_drum": float(total_pressure_drift[0]),
            "top_tray": float(total_pressure_drift[1]),
            "bottom": float(total_pressure_drift[2]),
        },
        "nominal_response": nominal_response,
        "refined_response": refined_response,
        "continuity": continuity,
        "refinement": refinement,
        "controller_aware_refinement_unexplained_max_abs_lbmol": float(np.max(np.abs(unexplained))),
        "final_profile": dd267._profile(context, evaluations[-1]),
        "component_names": list(successor.base.component_names),
        "provider": dd267.compact_provider_report(context["audit"].report()),
        "logical_provider_calls": context["audit"].record_count,
        "wall_clock_sec": wall,
        "simulation_wall_ratio": 30.0 / max(wall, 1.0e-300),
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "tuning_change_attempted": False,
        "pressure_controller_active": False,
        "longer_trajectory_attempted": False,
    }
    (ROOT / RESULT).write_text(_json(report), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(_result_markdown(report), encoding="utf-8")
    np.savez_compressed(
        ROOT / EVIDENCE,
        nominal_coordinates=np.stack(coordinate_rows),
        nominal_controller_memory=np.stack(memory_rows),
        refined_coordinates=np.stack(refined_coordinate_rows),
        refined_controller_memory=np.stack(refined_memory_rows),
        pressure_time_series=np.asarray([[row[key] for key in ("time_sec", "reflux_drum_pressure_psia", "top_tray_pressure_psia", "bottom_pressure_psia")] for row in pressure_series]),
        **{f"jacobian_root_{index}": matrix for index, matrix in enumerate(matrices, 1)},
    )
    return report


def _result_markdown(report: Mapping[str, Any]) -> str:
    first = report["pressure_time_series"][0]
    final = report["nominal_endpoints"][-1]
    return "\n".join(
        (
            "# DD-274 Dynamic-Pressure Thirty-Second Result",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Fixed Qc: `{report['specified_condenser_duty_BTUph'] / 1.0e6:.6f} MMBTU/h`",
            f"- Initial drum/top/bottom pressure: `{first['reflux_drum_pressure_psia']:.6f} / {first['top_tray_pressure_psia']:.6f} / {first['bottom_pressure_psia']:.6f} psia`",
            f"- Final drum/top/bottom pressure: `{final['reflux_drum_pressure_psia']:.6f} / {final['top_tray_pressure_psia']:.6f} / {final['bottom_pressure_psia']:.6f} psia`",
            f"- Final D/B: `{final['distillate_lbmolph']:.6f} / {final['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Final drum/sump levels: `{final['level_fraction']}`",
            f"- Provider calls/wall: `{report['logical_provider_calls']} / {report['wall_clock_sec']:.3f} s`",
            f"- Gates: `{report['gates']}`",
            "- Retry, alternate grid, tuning change, pressure controller, or extension: `False`.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        report = prepare()
        print(json.dumps({"schema_id": report["schema_id"], "contract_payload_sha256": report["contract_payload_sha256"]}, indent=2))
        return 0
    report = execute()
    print(json.dumps({"classification": report["classification"], "pass_gate": report["pass_gate"], "failed_gates": [key for key, value in report["gates"].items() if not value]}, indent=2))
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
