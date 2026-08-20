#!/usr/bin/env python
"""Prepare or execute DD-260's 30-second vapor-holdup trajectory."""

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

import run_core_v3_vapor_holdup_five_second_recovery as dd259  # noqa: E402
import run_core_v3_vapor_holdup_five_second_reporting_successor as dd258  # noqa: E402
import run_core_v3_vapor_holdup_parallel_trajectory as dd254  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import compact_provider_report  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitEvaluation,
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)


SCHEMA = "dd260-core-v3-c3c4-vapor-holdup-thirty-second-contract-v1"
RESULT_SCHEMA = "dd260-core-v3-c3c4-vapor-holdup-thirty-second-result-v1"
RECOVERY_SCHEMA = "dd260-core-v3-c3c4-vapor-holdup-thirty-second-recovery-v1"
CONTRACT = Path("logs/dd260_core_v3_c3c4_vapor_holdup_thirty_second_contract_20260820.json")
RESULT = Path("logs/dd260_core_v3_c3c4_vapor_holdup_thirty_second_20260820.json")
RECOVERY = Path("logs/dd260_core_v3_c3c4_vapor_holdup_thirty_second_recovery_20260820.json")
EVIDENCE = Path("logs/dd260_core_v3_c3c4_vapor_holdup_thirty_second_20260820.npz")
CONTRACT_DOC = Path("docs/dd_260_core_v3_c3c4_vapor_holdup_thirty_second_contract_20260820.md")
RESULT_DOC = Path("docs/dd_260_core_v3_c3c4_vapor_holdup_thirty_second_20260820.md")
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_thirty_second_trajectory.py"),
    Path("tools/run_core_v3_vapor_holdup_five_second_recovery.py"),
    Path("src/dynamic_distillation/core_v3/colored_jacobian_v1.py"),
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


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    dd259._atomic_json(path, payload)


def _atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    dd259._atomic_npz(path, **arrays)


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    dd259_result = json.loads((ROOT / dd259.RESULT).read_text(encoding="utf-8"))
    dd259_contract = json.loads((ROOT / dd259.CONTRACT).read_text(encoding="utf-8"))
    dd249_contract = json.loads((ROOT / dd249.CONTRACT).read_text(encoding="utf-8"))
    if not dd259_result.get("pass_gate"):
        raise RuntimeError("DD-260 requires the accepted DD-259 five-second trajectory")
    if dd259_result.get("controller_attempted"):
        raise RuntimeError("DD-260 requires DD-259's open-loop path")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": {
            "source": "explicit user authorization after DD-259",
            "scope": "one 30-second open-loop extension and one local final-step refinement",
        },
        "sources": {
            dd259.CONTRACT.as_posix(): _sha(dd259.CONTRACT),
            dd259.RESULT.as_posix(): _sha(dd259.RESULT),
            dd259.EVIDENCE.as_posix(): _sha(dd259.EVIDENCE),
            dd249.CONTRACT.as_posix(): _sha(dd249.CONTRACT),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "trajectory": {
            "nominal_step_sec": 0.25,
            "nominal_steps": 120,
            "nominal_duration_sec": 30.0,
            "refinement_start_sec": 29.75,
            "refined_step_sec": 0.125,
            "refined_steps": 2,
        },
        "disturbance": dd259_contract["disturbance"],
        "solver": dd259_contract["solver"],
        "method": dd259_contract["method"],
        "operating_inputs": dd259_contract["operating_inputs"],
        "limits": {
            "scaled_residual": 1.0e-8,
            "rank": 258,
            "condition": 1.0e8,
            "fugacity_residual": 1.0e-10,
            "eos_relative_residual": 1.0e-10,
            "component_identity_lbmol": 1.0e-6,
            "energy_identity_relative": 1.0e-8,
            "refinement_component_max_lbmol": dd249_contract["limits"]["maximum_component_inventory_difference_lbmol"],
            "refinement_component_l1_lbmol": dd249_contract["limits"]["component_inventory_difference_l1_lbmol"],
            "refinement_signed_total_lbmol": dd249_contract["limits"]["signed_total_inventory_difference_lbmol"],
            "refinement_temperature_F": dd249_contract["limits"]["temperature_difference_F"],
            "refinement_pressure_psia": dd249_contract["limits"]["pressure_difference_psia"],
            "refinement_flow_relative": dd249_contract["limits"]["flow_relative_difference"],
            "refinement_phase_transfer_scaled": dd249_contract["limits"]["phase_transfer_scaled_difference"],
            "refinement_duty_relative": dd249_contract["limits"]["duty_relative_difference"],
            "maximum_step_temperature_F": 0.5,
            "maximum_step_pressure_psia": 0.1,
            "maximum_step_composition": 0.01,
            "maximum_step_flow_relative": 0.01,
            "maximum_step_phase_inventory_relative": 0.01,
            "maximum_step_duty_relative": 0.01,
            "logical_provider_calls": 1_200_000,
            "wall_clock_sec": 480.0,
        },
        "reporting": {
            "atomic_json": True,
            "atomic_npz": True,
            "incremental_recovery_after_each_nominal_endpoint": True,
            "complete_final_stage_profile": True,
            "trajectory_time_series": True,
        },
        "hard_stops": [
            "any nominal or refinement root fails its scientific or physical gates",
            "the trajectory becomes discontinuous or total accumulation ceases to be positive and monotonic",
            "the final local refinement exceeds the inherited DD-249 timestep limits",
            "conservation, provider, call, wall-clock, recovery, or reporting gates fail",
            "a retry, alternate setting, controller, fallback, or extension beyond 30 seconds occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    if (ROOT / contract_path).exists() or (ROOT / contract_doc_path).exists():
        raise RuntimeError("DD-260 contract artifact already exists")
    (ROOT / contract_path).write_text(dd259._json_text(payload), encoding="utf-8")
    (ROOT / contract_doc_path).write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    trajectory = payload["trajectory"]
    return "\n".join(
        (
            "# DD-260 Thirty-Second Vapor-Holdup Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Nominal path: `{trajectory['nominal_steps']}` x `{trajectory['nominal_step_sec']} s` endpoints.",
            f"- Final refinement: `{trajectory['refined_steps']}` x `{trajectory['refined_step_sec']} s` from `{trajectory['refinement_start_sec']} s`.",
            "- Physics, disturbance, operating inputs, and modified-Newton method are inherited unchanged from DD-259.",
            "- Every endpoint must remain physical, conservative, full rank, smooth, and recoverable.",
            "- No controller, retry, fallback, tolerance change, or extension is authorized.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-260 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-260 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-260 implementation changed: {path}")
    if (ROOT / result_path).exists() or (ROOT / RECOVERY).exists():
        raise RuntimeError("DD-260 result or recovery exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _evaluate(
    context: Mapping[str, Any],
    reference: VaporHoldupImplicitReference,
    numerical: VaporHoldupImplicitNumericalSpec,
    coordinates: np.ndarray,
    state_id: str,
) -> VaporHoldupImplicitEvaluation:
    return evaluate_vapor_holdup_implicit_residual(
        context["contract"],
        context["geometry"],
        reference,
        context["balance_inputs"],
        context["spec"].hydraulic_geometry,
        numerical,
        context["provider"],
        context["audit"],
        coordinates,
        state_id=state_id,
        evaluation_kind="jacobian",
    )


def _solve_endpoint(
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    reference: VaporHoldupImplicitReference,
    initial_coordinates: np.ndarray,
    timestep_sec: float,
    root_name: str,
) -> tuple[Any, VaporHoldupImplicitEvaluation, dict[str, Any], np.ndarray]:
    numerical = replace(context["numerical"], timestep_sec=timestep_sec)
    pattern = vapor_holdup_structural_pattern(context["contract"])
    lower, upper = dd249._bounds()
    cached_matrix: np.ndarray | None = None
    build_count = 0

    def objective(candidate: np.ndarray, state_id: str = "residual") -> np.ndarray:
        return _evaluate(context, reference, numerical, candidate, f"{root_name}:{state_id}").scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal cached_matrix, build_count
        if cached_matrix is None:
            cached_matrix, groups = colored_central_difference_jacobian(
                objective,
                candidate,
                pattern=pattern,
                step=float(payload["solver"]["difference_step"]),
                state_id=f"{root_name}:jacobian",
            )
            if len(groups) != 28:
                raise RuntimeError("DD-260 color count changed")
            build_count += 1
        return cached_matrix

    solution = least_squares(
        objective,
        initial_coordinates,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=np.asarray(payload["solver"]["x_scale"], dtype=float),
        ftol=float(payload["solver"]["ftol"]),
        xtol=float(payload["solver"]["xtol"]),
        gtol=float(payload["solver"]["gtol"]),
        max_nfev=int(payload["solver"]["max_nfev_per_step"]),
        verbose=0,
    )
    final = _evaluate(context, reference, numerical, solution.x, f"{root_name}:accepted")
    rank, condition, _singular = dd249._rank_condition(np.asarray(solution.jac))
    report = {
        "success": bool(solution.success),
        "status": int(solution.status),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "cost": float(solution.cost),
        "optimality": float(solution.optimality),
        "scaled_residual_inf_norm": float(np.max(np.abs(final.scaled))),
        "jacobian_rank": int(rank),
        "jacobian_condition": float(condition),
        "maximum_fugacity_residual": float(np.max(np.abs(final.fugacity_residual))),
        "maximum_eos_relative_residual": float(np.max(np.abs(final.properties.eos_relative_residual))),
        "physical_pass": bool(dd249._physical(final)),
        "jacobian_build_count": int(build_count),
    }
    return solution, final, report, solution.x.copy()


def _total_inventory(evaluation: VaporHoldupImplicitEvaluation) -> float:
    endpoint = evaluation.endpoint
    return float(
        np.sum(endpoint.liquid_component_inventory_lbmol)
        + np.sum(endpoint.vapor_component_inventory_lbmol)
    )


def _compositions(inventory: np.ndarray) -> np.ndarray:
    return inventory / np.sum(inventory, axis=1, keepdims=True)


def _relative_max(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.max(np.abs(left - right) / np.maximum(np.abs(right), 1.0)))


def _continuity(
    initial: VaporHoldupImplicitReference,
    evaluations: list[VaporHoldupImplicitEvaluation],
) -> dict[str, float]:
    prior_t = initial.temperature_F
    prior_p = initial.pressure_psia
    prior_l = initial.hydraulic_liquid_flow_lbmolph
    prior_v = initial.vapor_flow_lbmolph
    prior_nl = initial.liquid_component_inventory_lbmol
    prior_nv = initial.vapor_component_inventory_lbmol
    prior_q = initial.condenser_duty_BTUph
    maxima = {
        "temperature_F": 0.0,
        "pressure_psia": 0.0,
        "composition": 0.0,
        "flow_relative": 0.0,
        "phase_inventory_relative": 0.0,
        "duty_relative": 0.0,
    }
    for evaluation in evaluations:
        endpoint = evaluation.endpoint
        maxima["temperature_F"] = max(maxima["temperature_F"], float(np.max(np.abs(endpoint.temperature_F - prior_t))))
        maxima["pressure_psia"] = max(maxima["pressure_psia"], float(np.max(np.abs(endpoint.pressure_psia - prior_p))))
        maxima["composition"] = max(
            maxima["composition"],
            float(np.max(np.abs(_compositions(endpoint.liquid_component_inventory_lbmol) - _compositions(prior_nl)))),
            float(np.max(np.abs(_compositions(endpoint.vapor_component_inventory_lbmol) - _compositions(prior_nv)))),
        )
        maxima["flow_relative"] = max(
            maxima["flow_relative"],
            _relative_max(endpoint.hydraulic_liquid_flow_lbmolph, prior_l),
            _relative_max(endpoint.vapor_flow_lbmolph, prior_v),
        )
        maxima["phase_inventory_relative"] = max(
            maxima["phase_inventory_relative"],
            _relative_max(endpoint.liquid_component_inventory_lbmol, prior_nl),
            _relative_max(endpoint.vapor_component_inventory_lbmol, prior_nv),
        )
        maxima["duty_relative"] = max(
            maxima["duty_relative"],
            abs(endpoint.condenser_duty_BTUph - prior_q) / abs(prior_q),
        )
        prior_t = endpoint.temperature_F
        prior_p = endpoint.pressure_psia
        prior_l = endpoint.hydraulic_liquid_flow_lbmolph
        prior_v = endpoint.vapor_flow_lbmolph
        prior_nl = endpoint.liquid_component_inventory_lbmol
        prior_nv = endpoint.vapor_component_inventory_lbmol
        prior_q = endpoint.condenser_duty_BTUph
    return maxima


def _run_nominal(context: dict[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    trajectory = payload["trajectory"]
    reference = context["reference"]
    initial_reference = reference
    initial_coordinates = np.zeros(258)
    evaluations: list[VaporHoldupImplicitEvaluation] = []
    reports: list[dict[str, Any]] = []
    coordinates: list[np.ndarray] = []
    pre_final_reference: VaporHoldupImplicitReference | None = None
    pre_final_coordinates: np.ndarray | None = None
    for endpoint_index in range(int(trajectory["nominal_steps"])):
        if endpoint_index == int(trajectory["nominal_steps"]) - 1:
            pre_final_reference = reference
            pre_final_coordinates = initial_coordinates.copy()
        solution, final, report, accepted_coordinates = _solve_endpoint(
            context,
            payload,
            reference,
            initial_coordinates,
            float(trajectory["nominal_step_sec"]),
            f"dd260:nominal_{endpoint_index + 1}",
        )
        report["index"] = endpoint_index + 1
        report["time_sec"] = (endpoint_index + 1) * float(trajectory["nominal_step_sec"])
        report["total_liquid_inventory_lbmol"] = float(np.sum(final.endpoint.liquid_component_inventory_lbmol))
        report["total_vapor_inventory_lbmol"] = float(np.sum(final.endpoint.vapor_component_inventory_lbmol))
        report["condenser_duty_BTUph"] = float(final.endpoint.condenser_duty_BTUph)
        evaluations.append(final)
        reports.append(report)
        coordinates.append(accepted_coordinates)
        reference = dd249._next_reference(reference, final)
        initial_coordinates = accepted_coordinates
        recovery = {
            "schema_id": RECOVERY_SCHEMA,
            "contract_payload_sha256": payload["contract_payload_sha256"],
            "status": "in_progress",
            "completed_endpoint_count": len(evaluations),
            "last_time_sec": report["time_sec"],
            "endpoint_reports": reports,
            "endpoint_coordinates": np.stack(coordinates),
            "next_reference": dd254._reference_payload(reference),
            "logical_provider_calls_so_far": int(context["audit"].record_count),
        }
        _atomic_json(RECOVERY, recovery)
        if (endpoint_index + 1) % 10 == 0:
            print(
                f"DD-260 accepted {endpoint_index + 1}/120 endpoints "
                f"(t={report['time_sec']:.2f} s, residual={report['scaled_residual_inf_norm']:.2e})",
                flush=True,
            )
    if pre_final_reference is None or pre_final_coordinates is None:
        raise RuntimeError("DD-260 did not capture its refinement branch point")
    return {
        "initial_reference": initial_reference,
        "final_reference": reference,
        "pre_final_reference": pre_final_reference,
        "pre_final_coordinates": pre_final_coordinates,
        "evaluations": evaluations,
        "endpoint_reports": reports,
        "coordinates": np.stack(coordinates),
        "response": dd249._path_response(
            initial_reference,
            evaluations,
            [float(trajectory["nominal_step_sec"])] * len(evaluations),
        ),
    }


def _run_refinement(
    context: dict[str, Any], payload: Mapping[str, Any], nominal: Mapping[str, Any]
) -> dict[str, Any]:
    trajectory = payload["trajectory"]
    reference = nominal["pre_final_reference"]
    initial_coordinates = nominal["pre_final_coordinates"]
    evaluations: list[VaporHoldupImplicitEvaluation] = []
    reports: list[dict[str, Any]] = []
    for index in range(int(trajectory["refined_steps"])):
        _solution, final, report, accepted_coordinates = _solve_endpoint(
            context,
            payload,
            reference,
            initial_coordinates,
            float(trajectory["refined_step_sec"]),
            f"dd260:refined_{index + 1}",
        )
        report["index"] = index + 1
        report["time_sec"] = float(trajectory["refinement_start_sec"]) + (index + 1) * float(trajectory["refined_step_sec"])
        evaluations.append(final)
        reports.append(report)
        reference = dd249._next_reference(reference, final)
        initial_coordinates = accepted_coordinates
    return {"evaluations": evaluations, "reports": reports, "final": evaluations[-1]}


def _refinement_comparison(
    nominal: VaporHoldupImplicitEvaluation,
    refined: VaporHoldupImplicitEvaluation,
    scale: np.ndarray,
) -> dict[str, float]:
    full = nominal.endpoint
    half = refined.endpoint
    full_inventory = (
        full.liquid_component_inventory_lbmol
        + full.vapor_component_inventory_lbmol
    )
    refined_inventory = (
        half.liquid_component_inventory_lbmol
        + half.vapor_component_inventory_lbmol
    )
    inventory_difference = full_inventory - refined_inventory
    return {
        "maximum_component_inventory_difference_lbmol": float(np.max(np.abs(inventory_difference))),
        "component_inventory_difference_l1_lbmol": float(np.sum(np.abs(inventory_difference))),
        "signed_total_inventory_difference_lbmol": float(abs(np.sum(inventory_difference))),
        "temperature_difference_F": float(np.max(np.abs(full.temperature_F - half.temperature_F))),
        "pressure_difference_psia": float(np.max(np.abs(full.pressure_psia - half.pressure_psia))),
        "liquid_flow_relative_difference": _relative_max(full.hydraulic_liquid_flow_lbmolph, half.hydraulic_liquid_flow_lbmolph),
        "vapor_flow_relative_difference": _relative_max(full.vapor_flow_lbmolph, half.vapor_flow_lbmolph),
        "phase_transfer_scaled_difference": float(np.max(np.abs(full.phase_transfer_lbmolph - half.phase_transfer_lbmolph) / scale)),
        "duty_relative_difference": float(abs(full.condenser_duty_BTUph - half.condenser_duty_BTUph) / abs(half.condenser_duty_BTUph)),
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
    context = dd254._make_main_context()
    started = time.perf_counter()
    nominal = _run_nominal(context, payload)
    refined = _run_refinement(context, payload, nominal)
    wall = time.perf_counter() - started
    limits = payload["limits"]
    final = nominal["evaluations"][-1]
    profile = dd258.stage_profile(context, final.endpoint)
    initial_total = float(
        np.sum(nominal["initial_reference"].liquid_component_inventory_lbmol)
        + np.sum(nominal["initial_reference"].vapor_component_inventory_lbmol)
    )
    total_inventory = np.asarray([_total_inventory(item) for item in nominal["evaluations"]])
    inventory_changes = total_inventory - initial_total
    continuity = _continuity(nominal["initial_reference"], nominal["evaluations"])
    refinement = _refinement_comparison(
        final,
        refined["final"],
        nominal["initial_reference"].phase_transfer_scale_lbmolph,
    )
    all_reports = nominal["endpoint_reports"] + refined["reports"]
    scientific = all(
        item["success"]
        and item["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and item["jacobian_rank"] == limits["rank"]
        and item["jacobian_condition"] < limits["condition"]
        and item["maximum_fugacity_residual"] < limits["fugacity_residual"]
        and item["maximum_eos_relative_residual"] < limits["eos_relative_residual"]
        and item["physical_pass"]
        and item["jacobian_build_count"] == 1
        for item in all_reports
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
    provider_calls = int(context["audit"].record_count)
    gates = {
        "path_complete": len(nominal["evaluations"]) == 120,
        "scientific_endpoints": bool(scientific),
        "positive_monotonic_accumulation": bool(np.all(inventory_changes > 0.0) and np.all(np.diff(inventory_changes) > 0.0)),
        "component_identity": nominal["response"]["component_inventory_identity_max_abs_lbmol"] < limits["component_identity_lbmol"],
        "energy_identity": nominal["response"]["energy_identity_relative"] < limits["energy_identity_relative"],
        "temperature_ordering": bool(all(np.all(np.diff(item.endpoint.temperature_F) > 0.0) for item in nominal["evaluations"])),
        "continuity": bool(all(continuity_gates.values())),
        "final_refinement": bool(all(refinement_gates.values())),
        "provider": bool(provider["pass"] and not provider["fallback_attempted"]),
        "report_complete": len(profile) == 20,
        "call_count": provider_calls < limits["logical_provider_calls"],
        "wall_clock": wall < limits["wall_clock_sec"],
        "no_retry_or_controller": True,
    }
    passed = bool(all(gates.values()))
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": "thirty_second_vapor_holdup_trajectory_passed" if passed else "thirty_second_vapor_holdup_trajectory_failed",
        "decision": "accept_open_loop_vapor_holdup_dynamics_through_thirty_seconds" if passed else "retain_five_second_vapor_holdup_boundary",
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "component_names": list(context["contract"].component_names),
        "operating_inputs": payload["operating_inputs"],
        "simulation_time_sec": 30.0,
        "wall_clock_sec": wall,
        "simulation_to_wall_ratio": 30.0 / wall,
        "logical_provider_calls": provider_calls,
        "final_condenser_duty_BTUph": float(final.endpoint.condenser_duty_BTUph),
        "inventory_change_by_endpoint_lbmol": inventory_changes,
        "response": nominal["response"],
        "continuity": continuity,
        "continuity_gates": continuity_gates,
        "refinement": refinement,
        "refinement_gates": refinement_gates,
        "endpoints": nominal["endpoint_reports"],
        "refined_endpoints": refined["reports"],
        "final_stage_profile": profile,
        "provider": provider,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_setting_attempted": False,
        "controller_attempted": False,
        "fallback_attempted": False,
        "longer_trajectory_attempted": False,
    }
    _atomic_npz(
        evidence_path,
        endpoint_coordinates=nominal["coordinates"],
        inventory_change_by_endpoint_lbmol=inventory_changes,
        temperature_F=np.stack([item.endpoint.temperature_F for item in nominal["evaluations"]]),
        pressure_psia=np.stack([item.endpoint.pressure_psia for item in nominal["evaluations"]]),
        liquid_inventory_lbmol=np.stack([item.endpoint.liquid_component_inventory_lbmol for item in nominal["evaluations"]]),
        vapor_inventory_lbmol=np.stack([item.endpoint.vapor_component_inventory_lbmol for item in nominal["evaluations"]]),
        liquid_flow_lbmolph=np.stack([item.endpoint.hydraulic_liquid_flow_lbmolph for item in nominal["evaluations"]]),
        vapor_flow_lbmolph=np.stack([item.endpoint.vapor_flow_lbmolph for item in nominal["evaluations"]]),
        condenser_duty_BTUph=np.asarray([item.endpoint.condenser_duty_BTUph for item in nominal["evaluations"]]),
    )
    _atomic_json(result_path, report)
    (ROOT / result_doc_path).write_text(_result_markdown(dd259.json_native(report)), encoding="utf-8")
    _atomic_json(
        RECOVERY,
        {
            "schema_id": RECOVERY_SCHEMA,
            "contract_payload_sha256": payload["contract_payload_sha256"],
            "status": "complete",
            "completed_endpoint_count": 120,
            "last_time_sec": 30.0,
            "result_path": result_path.as_posix(),
            "evidence_path": evidence_path.as_posix(),
            "result_sha256": _sha(result_path),
            "evidence_sha256": _sha(evidence_path),
        },
    )
    return dd259.json_native(report)


def _result_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# DD-260 Thirty-Second Vapor-Holdup Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Nominal endpoints: `{len(payload['endpoints'])}`",
        f"- Final condenser duty: `{payload['final_condenser_duty_BTUph'] / 1.0e6:.6f} MMBTU/h`",
        f"- Final inventory change: `{payload['response']['total_inventory_change_lbmol']:.9e} lbmol`",
        f"- Worst residual: `{max(item['scaled_residual_inf_norm'] for item in payload['endpoints']):.6e}`",
        f"- Worst condition: `{max(item['jacobian_condition'] for item in payload['endpoints']):.6e}`",
        f"- Provider calls: `{payload['logical_provider_calls']}`",
        f"- Wall: `{payload['wall_clock_sec']:.3f} s`; simulation/wall: `{payload['simulation_to_wall_ratio']:.5f}`",
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
    lines.extend(("", "Retry, alternate setting, controller, fallback, or extension: `False`", ""))
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
