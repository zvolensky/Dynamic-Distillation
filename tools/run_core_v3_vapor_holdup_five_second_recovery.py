#!/usr/bin/env python
"""Prepare or execute DD-259's recoverable five-second vapor-holdup run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_five_second_reporting_successor as dd258  # noqa: E402
import run_core_v3_vapor_holdup_modified_newton_trajectory as dd255  # noqa: E402
import run_core_v3_vapor_holdup_parallel_trajectory as dd254  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitEvaluation,
    VaporHoldupImplicitReference,
    decode_vapor_holdup_endpoint,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)


SCHEMA = "dd259-core-v3-c3c4-vapor-holdup-five-second-recovery-contract-v1"
RESULT_SCHEMA = "dd259-core-v3-c3c4-vapor-holdup-five-second-recovery-result-v1"
RECOVERY_SCHEMA = "dd259-core-v3-c3c4-vapor-holdup-endpoint-recovery-v1"
CONTRACT = Path("logs/dd259_core_v3_c3c4_vapor_holdup_five_second_contract_20260820.json")
RESULT = Path("logs/dd259_core_v3_c3c4_vapor_holdup_five_second_20260820.json")
RECOVERY = Path("logs/dd259_core_v3_c3c4_vapor_holdup_five_second_recovery_20260820.json")
CONTRACT_DOC = Path("docs/dd_259_core_v3_c3c4_vapor_holdup_five_second_contract_20260820.md")
RESULT_DOC = Path("docs/dd_259_core_v3_c3c4_vapor_holdup_five_second_20260820.md")
EVIDENCE = Path("logs/dd259_core_v3_c3c4_vapor_holdup_five_second_20260820.npz")
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_five_second_recovery.py"),
    Path("tools/run_core_v3_vapor_holdup_parallel_trajectory.py"),
    Path("tools/run_core_v3_vapor_holdup_five_second_reporting_successor.py"),
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


def json_native(value: Any) -> Any:
    """Recursively convert NumPy values to JSON-native Python values."""
    if isinstance(value, np.ndarray):
        return [json_native(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_native(item) for item in value]
    return value


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(json_native(payload), indent=2, allow_nan=False) + "\n"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    destination = ROOT / path
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(_json_text(payload), encoding="utf-8")
    json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(destination)


def _atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    destination = ROOT / path
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    with np.load(temporary) as saved:
        if set(saved.files) != set(arrays):
            raise RuntimeError("DD-259 NPZ preflight key mismatch")
    temporary.replace(destination)


def _reporting_preflight() -> dict[str, Any]:
    problem = dd254._disturbed_problem()
    endpoint = decode_vapor_holdup_endpoint(
        problem["contract"],
        problem["reference"],
        problem["numerical"],
        np.zeros(258),
    )
    profile = dd258.stage_profile(problem, endpoint)
    synthetic = {
        "numpy_bool": np.bool_(True),
        "numpy_float": np.float64(1.25),
        "numpy_int": np.int64(20),
        "numpy_array": np.asarray([1.0, 2.0]),
        "stage_profile": profile,
    }
    decoded = json.loads(_json_text(synthetic))
    if (
        decoded["numpy_bool"] is not True
        or decoded["numpy_float"] != 1.25
        or decoded["numpy_int"] != 20
        or decoded["numpy_array"] != [1.0, 2.0]
        or len(decoded["stage_profile"]) != 20
    ):
        raise RuntimeError("DD-259 JSON-native preflight failed")
    with tempfile.TemporaryDirectory(prefix="dd259_preflight_") as directory:
        temporary_root = Path(directory)
        json_path = temporary_root / "representative.json"
        npz_path = temporary_root / "representative.npz"
        json_temp = json_path.with_suffix(".json.tmp")
        json_temp.write_text(_json_text(synthetic), encoding="utf-8")
        json.loads(json_temp.read_text(encoding="utf-8"))
        json_temp.replace(json_path)
        npz_temp = npz_path.with_suffix(".npz.tmp")
        with npz_temp.open("wb") as stream:
            np.savez_compressed(stream, coordinates=np.zeros((1, 258)))
        with np.load(npz_temp) as saved:
            if saved["coordinates"].shape != (1, 258):
                raise RuntimeError("DD-259 NPZ preflight failed")
        npz_temp.replace(npz_path)
        if not json_path.exists() or not npz_path.exists():
            raise RuntimeError("DD-259 atomic replacement preflight failed")
    return {
        "json_native": True,
        "atomic_json": True,
        "atomic_npz": True,
        "complete_stage_profile": True,
    }


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    dd255_result = json.loads((ROOT / dd255.RESULT).read_text(encoding="utf-8"))
    dd258_result = json.loads((ROOT / dd258.RESULT).read_text(encoding="utf-8"))
    dd258_contract = json.loads((ROOT / dd258.CONTRACT).read_text(encoding="utf-8"))
    dd250_contract = json.loads(
        (ROOT / "logs/dd250_core_v3_c3c4_vapor_holdup_short_trajectory_contract_20260820.json").read_text(
            encoding="utf-8"
        )
    )
    if dd255_result.get("logical_provider_call_ratio", 1.0) >= 0.30:
        raise RuntimeError("DD-259 requires DD-255's demonstrated call reduction")
    if dd258_result.get("decision") != "stop_five_second_extension_work":
        raise RuntimeError("DD-259 requires DD-258's preserved serialization stop")
    preflight = _reporting_preflight()
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": {
            "source": "explicit user authorization after DD-258",
            "preserve_historical_results": True,
            "new_campaign_not_reclassification": True,
        },
        "sources": {
            dd255.RESULT.as_posix(): _sha(dd255.RESULT),
            dd255.EVIDENCE.as_posix(): _sha(dd255.EVIDENCE),
            dd258.CONTRACT.as_posix(): _sha(dd258.CONTRACT),
            dd258.RESULT.as_posix(): _sha(dd258.RESULT),
            dd254.RESULT.as_posix(): _sha(dd254.RESULT),
            dd254.EVIDENCE.as_posix(): _sha(dd254.EVIDENCE),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "trajectory": dd258_contract["trajectory"],
        "disturbance": dd258_contract["disturbance"],
        "solver": dd258_contract["solver"],
        "method": {
            "name": "one fresh 28-color Jacobian per endpoint root",
            "basis": "DD-255 scientifically clean modified-Newton path",
            "fresh_jacobians_per_root": 1,
            "parallel_workers": 0,
        },
        "operating_inputs": {
            "reflux_lbmolph": 5952.48,
            "distillate_lbmolph": 2519.763701913325,
            "bottoms_lbmolph": 4623.21029792288,
            "reboiler_duty_BTUph": 54706000.0,
        },
        "first_second_reference": {
            "source": dd254.EVIDENCE.as_posix(),
            "non_duty_coordinate_absolute_difference": 1.0e-9,
            "condenser_duty_relative_difference": 1.0e-8,
            "phase_inventory_absolute_difference_lbmol": dd250_contract["limits"][
                "maximum_common_time_component_difference_lbmol"
            ],
            "response_absolute_difference_lbmol": 1.0e-10,
        },
        "limits": {
            "scaled_residual": 1.0e-8,
            "rank": 258,
            "condition": 1.0e8,
            "fugacity_residual": 1.0e-10,
            "eos_relative_residual": 1.0e-10,
            "component_identity_lbmol": 1.0e-6,
            "energy_identity_relative": 1.0e-8,
            "logical_provider_calls": 300000,
            "wall_clock_sec": 150.0,
        },
        "reporting": {
            "preflight": preflight,
            "json_native_conversion": True,
            "json_allow_nan": False,
            "atomic_final_json": True,
            "atomic_final_npz": True,
            "incremental_recovery_after_each_endpoint": True,
            "complete_final_stage_profile": True,
        },
        "hard_stops": [
            "any root or scientific, conservation, physical, provider, replay, call, or wall gate fails",
            "more than one finite-difference Jacobian is built for any root",
            "incremental recovery does not serialize after every accepted endpoint",
            "final JSON or NPZ validation and atomic replacement fails",
            "retry, alternate step, alternate tolerance, worker, controller, fallback, or extension beyond five seconds occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-259 contract artifact already exists")
    destination.write_text(_json_text(payload), encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    replay = payload["first_second_reference"]
    return "\n".join(
        (
            "# DD-259 Recoverable Five-Second Vapor-Holdup Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Authorization: explicit user override; DD-255/DD-257/DD-258 remain unchanged.",
            "- Path: 20 serial `0.25 s` endpoints with one fresh Jacobian per root.",
            f"- Replay: non-duty coordinates `<={replay['non_duty_coordinate_absolute_difference']:.1e}`; condenser duty relative `<={replay['condenser_duty_relative_difference']:.1e}`.",
            "- Recovery: one atomic JSON checkpoint after every accepted endpoint.",
            "- Final artifacts: validated atomic JSON, NPZ, and full 20-volume profile.",
            "- Retry, alternate setting, worker, controller, fallback, or extension: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-259 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-259 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-259 implementation changed: {path}")
    if (ROOT / result_path).exists() or (ROOT / RECOVERY).exists():
        raise RuntimeError("DD-259 result or recovery exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _evaluate(
    context: Mapping[str, Any],
    reference: VaporHoldupImplicitReference,
    coordinates: np.ndarray,
    state_id: str,
) -> VaporHoldupImplicitEvaluation:
    return evaluate_vapor_holdup_implicit_residual(
        context["contract"],
        context["geometry"],
        reference,
        context["balance_inputs"],
        context["spec"].hydraulic_geometry,
        context["numerical"],
        context["provider"],
        context["audit"],
        coordinates,
        state_id=state_id,
        evaluation_kind="jacobian",
    )


def _reference_payload(reference: VaporHoldupImplicitReference) -> dict[str, Any]:
    return dd254._reference_payload(reference)


def _run_path(
    context: dict[str, Any], payload: Mapping[str, Any]
) -> dict[str, Any]:
    reference = context["reference"]
    initial_reference = reference
    initial_coordinates = np.zeros(258)
    lower, upper = dd249._bounds()
    x_scale = np.asarray(payload["solver"]["x_scale"], dtype=float)
    pattern = vapor_holdup_structural_pattern(context["contract"])
    evaluations: list[VaporHoldupImplicitEvaluation] = []
    solutions: list[Any] = []
    reports: list[dict[str, Any]] = []
    coordinates: list[np.ndarray] = []
    jacobian_builds: list[int] = []
    for endpoint_index in range(int(payload["trajectory"]["steps_per_path"])):
        root_name = f"dd259:root_{endpoint_index + 1}"
        cached_matrix: np.ndarray | None = None
        build_count = 0

        def objective(candidate: np.ndarray, state_id: str = "residual") -> np.ndarray:
            return _evaluate(
                context,
                reference,
                candidate,
                f"{root_name}:{state_id}",
            ).scaled

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
                    raise RuntimeError("DD-259 color count changed")
                build_count += 1
            return cached_matrix

        solution = least_squares(
            objective,
            initial_coordinates,
            jac=jacobian,
            bounds=(lower, upper),
            method="trf",
            x_scale=x_scale,
            ftol=float(payload["solver"]["ftol"]),
            xtol=float(payload["solver"]["xtol"]),
            gtol=float(payload["solver"]["gtol"]),
            max_nfev=int(payload["solver"]["max_nfev_per_step"]),
            verbose=0,
        )
        final = _evaluate(
            context,
            reference,
            solution.x,
            f"{root_name}:accepted",
        )
        rank, condition, _singular = dd249._rank_condition(np.asarray(solution.jac))
        report = {
            "index": endpoint_index + 1,
            "time_sec": (endpoint_index + 1) * 0.25,
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
            "maximum_eos_relative_residual": float(
                np.max(np.abs(final.properties.eos_relative_residual))
            ),
            "physical_pass": bool(dd249._physical(final)),
            "jacobian_build_count": int(build_count),
        }
        evaluations.append(final)
        solutions.append(solution)
        reports.append(report)
        coordinates.append(solution.x.copy())
        reference = dd249._next_reference(reference, final)
        initial_coordinates = solution.x.copy()
        jacobian_builds.append(build_count)
        recovery = {
            "schema_id": RECOVERY_SCHEMA,
            "contract_payload_sha256": payload["contract_payload_sha256"],
            "status": "in_progress",
            "completed_endpoint_count": len(evaluations),
            "last_time_sec": report["time_sec"],
            "endpoint_reports": reports,
            "endpoint_coordinates": np.stack(coordinates),
            "next_reference": _reference_payload(reference),
            "logical_provider_calls_so_far": int(context["audit"].record_count),
        }
        _atomic_json(RECOVERY, recovery)
    return {
        "initial_reference": initial_reference,
        "final_reference": reference,
        "evaluations": evaluations,
        "solutions": solutions,
        "endpoint_reports": reports,
        "coordinates": np.stack(coordinates),
        "jacobian_builds": jacobian_builds,
        "response": dd249._path_response(initial_reference, evaluations, [0.25] * len(evaluations)),
    }


def _baseline_duties(initial_duty: float, coordinates: np.ndarray) -> np.ndarray:
    duties = []
    duty = float(initial_duty)
    for point in coordinates:
        duty *= float(np.exp(point[-1]))
        duties.append(duty)
    return np.asarray(duties)


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    _reporting_preflight()
    context = dd254._make_main_context()
    started = time.perf_counter()
    path = _run_path(context, payload)
    wall = time.perf_counter() - started
    baseline_evidence = np.load(ROOT / dd254.EVIDENCE)
    baseline_coordinates = baseline_evidence["serial_coordinates"]
    candidate_coordinates = path["coordinates"][:4]
    non_duty_difference = float(
        np.max(np.abs(candidate_coordinates[:, :-1] - baseline_coordinates[:, :-1]))
    )
    baseline_duties = _baseline_duties(
        path["initial_reference"].condenser_duty_BTUph, baseline_coordinates
    )
    candidate_duties = np.asarray(
        [item.endpoint.condenser_duty_BTUph for item in path["evaluations"][:4]]
    )
    duty_relative_difference = float(
        np.max(np.abs(candidate_duties - baseline_duties) / np.abs(baseline_duties))
    )
    first_second_liquid_difference = float(
        np.max(
            np.abs(
                path["evaluations"][3].endpoint.liquid_component_inventory_lbmol
                - baseline_evidence["serial_final_liquid_inventory"]
            )
        )
    )
    first_second_vapor_difference = float(
        np.max(
            np.abs(
                path["evaluations"][3].endpoint.vapor_component_inventory_lbmol
                - baseline_evidence["serial_final_vapor_inventory"]
            )
        )
    )
    initial_total = float(
        np.sum(path["initial_reference"].liquid_component_inventory_lbmol)
        + np.sum(path["initial_reference"].vapor_component_inventory_lbmol)
    )
    total_inventory = np.asarray(
        [
            np.sum(item.endpoint.liquid_component_inventory_lbmol)
            + np.sum(item.endpoint.vapor_component_inventory_lbmol)
            for item in path["evaluations"]
        ],
        dtype=float,
    )
    inventory_changes = total_inventory - initial_total
    dd254_result = json.loads((ROOT / dd254.RESULT).read_text(encoding="utf-8"))
    first_second_response_difference = abs(
        inventory_changes[3]
        - dd254_result["serial"]["response"]["total_inventory_change_lbmol"]
    )
    profile = dd258.stage_profile(context, path["evaluations"][-1].endpoint)
    provider_report = compact_provider_report(context["audit"].report())
    provider_calls = int(context["audit"].record_count)
    limits = payload["limits"]
    replay = payload["first_second_reference"]
    scientific = all(
        item["success"]
        and item["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and item["jacobian_rank"] == limits["rank"]
        and item["jacobian_condition"] < limits["condition"]
        and item["maximum_fugacity_residual"] < limits["fugacity_residual"]
        and item["maximum_eos_relative_residual"] < limits["eos_relative_residual"]
        and item["physical_pass"]
        for item in path["endpoint_reports"]
    )
    gates = {
        "path_complete": bool(len(path["evaluations"]) == 20),
        "scientific_endpoints": bool(scientific),
        "one_fresh_jacobian_per_root": bool(all(count == 1 for count in path["jacobian_builds"])),
        "first_second_non_duty_coordinates": bool(
            non_duty_difference <= replay["non_duty_coordinate_absolute_difference"]
        ),
        "first_second_condenser_duty": bool(
            duty_relative_difference <= replay["condenser_duty_relative_difference"]
        ),
        "first_second_phase_inventories": bool(
            max(first_second_liquid_difference, first_second_vapor_difference)
            <= replay["phase_inventory_absolute_difference_lbmol"]
        ),
        "first_second_response": bool(
            first_second_response_difference <= replay["response_absolute_difference_lbmol"]
        ),
        "positive_monotonic_accumulation": bool(
            np.all(inventory_changes > 0.0) and np.all(np.diff(inventory_changes) > 0.0)
        ),
        "component_identity": bool(
            path["response"]["component_inventory_identity_max_abs_lbmol"]
            < limits["component_identity_lbmol"]
        ),
        "energy_identity": bool(
            path["response"]["energy_identity_relative"]
            < limits["energy_identity_relative"]
        ),
        "provider": bool(provider_report["pass"] and not provider_report["fallback_attempted"]),
        "report_complete": bool(len(profile) == 20),
        "call_count": bool(provider_calls < limits["logical_provider_calls"]),
        "wall_clock": bool(wall < limits["wall_clock_sec"]),
        "no_retry_or_controller": True,
    }
    passed = bool(all(gates.values()))
    final = path["evaluations"][-1].endpoint
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "recoverable_five_second_vapor_holdup_trajectory_passed"
            if passed
            else "recoverable_five_second_vapor_holdup_trajectory_failed"
        ),
        "decision": (
            "accept_modified_newton_vapor_holdup_dynamics_through_five_seconds"
            if passed
            else "retain_one_second_vapor_holdup_boundary"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "component_names": list(context["contract"].component_names),
        "operating_inputs": payload["operating_inputs"],
        "final_condenser_duty_BTUph": float(final.condenser_duty_BTUph),
        "endpoints": path["endpoint_reports"],
        "inventory_change_by_endpoint_lbmol": inventory_changes,
        "response": path["response"],
        "first_second_comparison": {
            "non_duty_coordinate_max_abs_difference": non_duty_difference,
            "condenser_duty_relative_difference": duty_relative_difference,
            "liquid_inventory_max_abs_difference_lbmol": first_second_liquid_difference,
            "vapor_inventory_max_abs_difference_lbmol": first_second_vapor_difference,
            "total_response_absolute_difference_lbmol": first_second_response_difference,
        },
        "final_stage_profile": profile,
        "provider": provider_report,
        "logical_provider_calls": provider_calls,
        "wall_clock_sec": wall,
        "simulation_time_sec": 5.0,
        "simulation_to_wall_ratio": 5.0 / wall,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "recovery_endpoint_count": 20,
        "retry_attempted": False,
        "alternate_step_attempted": False,
        "parallel_worker_attempted": False,
        "controller_attempted": False,
        "longer_trajectory_attempted": False,
    }
    result_text = _json_text(report)
    json.loads(result_text)
    _atomic_npz(
        evidence_path,
        endpoint_coordinates=path["coordinates"],
        inventory_change_by_endpoint_lbmol=inventory_changes,
        final_liquid_inventory=final.liquid_component_inventory_lbmol,
        final_vapor_inventory=final.vapor_component_inventory_lbmol,
    )
    _atomic_json(result_path, report)
    (ROOT / result_doc_path).write_text(_result_markdown(json_native(report)), encoding="utf-8")
    recovery_complete = {
        "schema_id": RECOVERY_SCHEMA,
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "status": "complete",
        "completed_endpoint_count": 20,
        "last_time_sec": 5.0,
        "result_path": result_path.as_posix(),
        "evidence_path": evidence_path.as_posix(),
        "result_sha256": _sha(result_path),
        "evidence_sha256": _sha(evidence_path),
    }
    _atomic_json(RECOVERY, recovery_complete)
    return json_native(report)


def _result_markdown(payload: Mapping[str, Any]) -> str:
    comparison = payload["first_second_comparison"]
    lines = [
        "# DD-259 Recoverable Five-Second Vapor-Holdup Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Endpoints: `{len(payload['endpoints'])}`",
        f"- Final condenser duty: `{payload['final_condenser_duty_BTUph'] / 1.0e6:.6f} MMBTU/h`",
        f"- Final inventory change: `{payload['response']['total_inventory_change_lbmol']:.9e} lbmol`",
        f"- Worst residual: `{max(item['scaled_residual_inf_norm'] for item in payload['endpoints']):.6e}`",
        f"- First-second non-duty coordinate difference: `{comparison['non_duty_coordinate_max_abs_difference']:.6e}`",
        f"- First-second duty relative difference: `{comparison['condenser_duty_relative_difference']:.6e}`",
        f"- Provider calls: `{payload['logical_provider_calls']}`",
        f"- Wall: `{payload['wall_clock_sec']:.3f} s`; simulation/wall: `{payload['simulation_to_wall_ratio']:.5f}`",
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
    lines.extend(("", "Retry, alternate setting, worker, controller, or extension: `False`", ""))
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
        print(_json_text({
            "schema_id": report["schema_id"],
            "contract_payload_sha256": report["contract_payload_sha256"],
            "method": report["method"],
            "reporting": report["reporting"],
            "campaign_executed": report["campaign_executed"],
        }), end="")
        return 0
    report = execute(args.contract, args.result, args.result_doc, args.evidence)
    print(_json_text({
        "classification": report["classification"],
        "pass_gate": report["pass_gate"],
        "decision": report["decision"],
    }), end="")
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
