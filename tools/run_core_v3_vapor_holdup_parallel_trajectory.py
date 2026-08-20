#!/usr/bin/env python
"""Prepare or execute DD-254's persistent-parallel vapor-holdup trajectory."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import hashlib
import json
import multiprocessing as mp
import os
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

import adjudicate_core_v3_vapor_holdup_parallel_first_root as dd253  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_stationary_hold as dd248  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.persistent_parallel_colored_jacobian_v1 import (  # noqa: E402
    PersistentParallelColoredJacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitEvaluation,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)


SCHEMA = "dd254-core-v3-c3c4-vapor-holdup-parallel-trajectory-contract-v1"
RESULT_SCHEMA = "dd254-core-v3-c3c4-vapor-holdup-parallel-trajectory-result-v1"
CONTRACT = Path(
    "logs/dd254_core_v3_c3c4_vapor_holdup_parallel_trajectory_contract_20260820.json"
)
RESULT = Path(
    "logs/dd254_core_v3_c3c4_vapor_holdup_parallel_trajectory_20260820.json"
)
CONTRACT_DOC = Path(
    "docs/dd_254_core_v3_c3c4_vapor_holdup_parallel_trajectory_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_254_core_v3_c3c4_vapor_holdup_parallel_trajectory_20260820.md"
)
EVIDENCE = Path(
    "logs/dd254_core_v3_c3c4_vapor_holdup_parallel_trajectory_20260820.npz"
)
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_parallel_trajectory.py"),
    Path("src/dynamic_distillation/core_v3/persistent_parallel_colored_jacobian_v1.py"),
    Path("src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
)

_WORKER_CONTEXT: dict[str, Any] | None = None


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


def _reference_payload(reference: VaporHoldupImplicitReference) -> dict[str, Any]:
    return {
        "liquid_component_inventory_lbmol": reference.liquid_component_inventory_lbmol.tolist(),
        "vapor_component_inventory_lbmol": reference.vapor_component_inventory_lbmol.tolist(),
        "phase_transfer_lbmolph": reference.phase_transfer_lbmolph.tolist(),
        "phase_transfer_scale_lbmolph": reference.phase_transfer_scale_lbmolph.tolist(),
        "temperature_F": reference.temperature_F.tolist(),
        "pressure_psia": reference.pressure_psia.tolist(),
        "hydraulic_liquid_flow_lbmolph": reference.hydraulic_liquid_flow_lbmolph.tolist(),
        "vapor_flow_lbmolph": reference.vapor_flow_lbmolph.tolist(),
        "condenser_duty_BTUph": float(reference.condenser_duty_BTUph),
        "total_stored_energy_BTU": reference.total_stored_energy_BTU.tolist(),
    }


def _reference_from_payload(payload: Mapping[str, Any]) -> VaporHoldupImplicitReference:
    return VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=np.asarray(
            payload["liquid_component_inventory_lbmol"], dtype=float
        ),
        vapor_component_inventory_lbmol=np.asarray(
            payload["vapor_component_inventory_lbmol"], dtype=float
        ),
        phase_transfer_lbmolph=np.asarray(payload["phase_transfer_lbmolph"], dtype=float),
        phase_transfer_scale_lbmolph=np.asarray(
            payload["phase_transfer_scale_lbmolph"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        pressure_psia=np.asarray(payload["pressure_psia"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        condenser_duty_BTUph=float(payload["condenser_duty_BTUph"]),
        total_stored_energy_BTU=np.asarray(
            payload["total_stored_energy_BTU"], dtype=float
        ),
    )


def _disturbed_problem() -> dict[str, Any]:
    problem = dd248._problem()
    return {
        **problem,
        "balance_inputs": replace(
            problem["balance_inputs"],
            feed_component_lbmolph=(
                problem["balance_inputs"].feed_component_lbmolph * 1.001
            ),
            feed_enthalpy_BTUph=(
                problem["balance_inputs"].feed_enthalpy_BTUph * 1.001
            ),
        ),
        "numerical": replace(problem["numerical"], timestep_sec=0.25),
    }


def _worker_initialize() -> None:
    global _WORKER_CONTEXT
    problem = _disturbed_problem()
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    _WORKER_CONTEXT = {
        "problem": problem,
        "audit": audit,
        "provider": provider,
        "root_epoch": None,
        "reference": None,
    }


def _worker_ping(delay_sec: float) -> int:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-254 worker was not initialized")
    time.sleep(float(delay_sec))
    return int(os.getpid())


def _worker_evaluate(work: Mapping[str, Any]) -> dict[str, Any]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-254 worker context is unavailable")
    context = _WORKER_CONTEXT
    root_epoch = str(work["root_epoch"])
    basis_rebuilt = context["root_epoch"] != root_epoch
    if basis_rebuilt:
        context["reference"] = _reference_from_payload(work["reference"])
        context["root_epoch"] = root_epoch
    task = work["task"]
    problem = context["problem"]
    audit = context["audit"]
    before = audit.record_count
    evaluation = evaluate_vapor_holdup_implicit_residual(
        problem["contract"],
        problem["geometry"],
        context["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        context["provider"],
        audit,
        np.asarray(task.coordinates, dtype=float),
        state_id=task.state_id,
        evaluation_kind="jacobian",
    )
    provider_report = audit.report()
    return {
        "order": int(task.order),
        "residual": evaluation.scaled.tolist(),
        "process_id": int(os.getpid()),
        "method": str(work["method"]),
        "root_epoch": root_epoch,
        "basis_rebuilt": basis_rebuilt,
        "logical_provider_calls": int(audit.record_count - before),
        "provider_pass": bool(provider_report["pass"]),
        "fallback_attempted": bool(provider_report["fallback_attempted"]),
    }


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    source = json.loads((ROOT / dd253.RESULT).read_text(encoding="utf-8"))
    moving_contract = json.loads((ROOT / dd249.CONTRACT).read_text(encoding="utf-8"))
    if not source.get("pass_gate"):
        raise RuntimeError("DD-254 requires accepted DD-253 evidence")
    problem = _disturbed_problem()
    pattern = vapor_holdup_structural_pattern(problem["contract"])
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd253.CONTRACT.as_posix(): _sha(dd253.CONTRACT),
            dd253.RESULT.as_posix(): _sha(dd253.RESULT),
            dd249.CONTRACT.as_posix(): _sha(dd249.CONTRACT),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "trajectory": {
            "duration_sec": 1.0,
            "step_sec": 0.25,
            "steps_per_path": 4,
            "serial_path_count": 1,
            "parallel_path_count": 1,
            "worker_count": 8,
            "persistent_pool_count": 1,
            "matrix_shape": list(pattern.shape),
            "color_count": 28,
            "tasks_per_matrix": 56,
            "startup_ping_delay_sec": 0.15,
        },
        "solver": moving_contract["solver"],
        "limits": {
            "scaled_residual": 1.0e-8,
            "rank": 258,
            "condition": 1.0e8,
            "fugacity_residual": 1.0e-10,
            "eos_relative_residual": 1.0e-10,
            "matrix_absolute_difference": 1.0e-10,
            "coordinate_absolute_difference": 1.0e-12,
            "response_absolute_difference_lbmol": 1.0e-12,
            "component_identity_lbmol": 1.0e-6,
            "energy_identity_relative": 1.0e-8,
            "parallel_trajectory_time_ratio": 0.75,
            "governed_time_ratio_including_startup": 1.25,
            "logical_provider_calls_each_path": 300000,
            "wall_clock_sec": 300.0,
        },
        "hard_stops": [
            "serial and parallel paths do not complete the same four endpoints",
            "any Jacobian, solver decision, coordinate, response, or scientific gate differs outside fixed limits",
            "the persistent pool does not rebuild exactly one basis per worker and root",
            "parallel trajectory wall excluding startup is not at least 25 percent lower",
            "provider ownership, work parity, call, or wall gates fail",
            "a retry, alternate grid, controller, or longer trajectory occurs",
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
        raise RuntimeError("DD-254 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-254 Persistent-Parallel Vapor-Holdup Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Paths: four serial and four persistent-parallel `0.25 s` endpoints.",
            "- Disturbance: unchanged DD-249 `+0.1%` feed and enthalpy.",
            "- Pool: one persistent eight-worker DWSIM process pool.",
            "- Each accepted endpoint supplies the next worker reference basis.",
            "- Jacobian, solver-decision, endpoint, conservation, physical, and provider equivalence are required.",
            "- Parallel path excluding startup must be at least 25% faster.",
            "- Retry, alternate grid, controller, or longer trajectory: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-254 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-254 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-254 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-254 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _make_main_context() -> dict[str, Any]:
    problem = _disturbed_problem()
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    return {**problem, "audit": audit, "provider": provider}


def _evaluate(
    context: Mapping[str, Any],
    reference: VaporHoldupImplicitReference,
    coordinates: np.ndarray,
    state_id: str,
    evaluation_kind: str,
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
        evaluation_kind=evaluation_kind,
    )


def _run_path(
    name: str,
    context: dict[str, Any],
    payload: Mapping[str, Any],
    jacobian_factory: Any,
) -> dict[str, Any]:
    reference = context["reference"]
    initial_reference = reference
    initial_coordinates = np.zeros(258)
    lower, upper = dd249._bounds()
    x_scale = np.asarray(payload["solver"]["x_scale"], dtype=float)
    evaluations: list[VaporHoldupImplicitEvaluation] = []
    solutions: list[Any] = []
    matrices: list[np.ndarray] = []
    endpoint_reports: list[dict[str, Any]] = []
    for endpoint_index in range(int(payload["trajectory"]["steps_per_path"])):
        root_epoch = f"dd254:{name}:root_{endpoint_index + 1}"

        def objective(candidate: np.ndarray, state_id: str = "residual") -> np.ndarray:
            return _evaluate(
                context,
                reference,
                candidate,
                f"{root_epoch}:{state_id}",
                "jacobian",
            ).scaled

        def jacobian(candidate: np.ndarray) -> np.ndarray:
            matrix = jacobian_factory(
                objective,
                candidate,
                f"{root_epoch}:jacobian:{len(matrices) + 1}",
                root_epoch,
                reference,
            )
            matrices.append(matrix.copy())
            return matrix

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
            f"{root_epoch}:accepted",
            "residual",
        )
        rank, condition, _singular = dd249._rank_condition(np.asarray(solution.jac))
        endpoint_reports.append(
            {
                "index": endpoint_index + 1,
                "time_sec": (endpoint_index + 1) * 0.25,
                "success": bool(solution.success),
                "status": int(solution.status),
                "nfev": int(solution.nfev),
                "njev": int(solution.njev or 0),
                "cost": float(solution.cost),
                "optimality": float(solution.optimality),
                "scaled_residual_inf_norm": float(np.max(np.abs(final.scaled))),
                "jacobian_rank": rank,
                "jacobian_condition": condition,
                "maximum_fugacity_residual": float(np.max(np.abs(final.fugacity_residual))),
                "maximum_eos_relative_residual": float(
                    np.max(np.abs(final.properties.eos_relative_residual))
                ),
                "physical_pass": dd249._physical(final),
            }
        )
        evaluations.append(final)
        solutions.append(solution)
        reference = dd249._next_reference(reference, final)
        initial_coordinates = solution.x.copy()
    response = dd249._path_response(
        initial_reference,
        evaluations,
        [0.25] * len(evaluations),
    )
    return {
        "initial_reference": initial_reference,
        "evaluations": evaluations,
        "solutions": solutions,
        "matrices": matrices,
        "endpoint_reports": endpoint_reports,
        "response": response,
    }


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    serial_context = _make_main_context()
    parallel_context = _make_main_context()
    pattern = vapor_holdup_structural_pattern(serial_context["contract"])

    def serial_factory(objective, point, state_id, _root_epoch, _reference):
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=float(payload["solver"]["difference_step"]),
            state_id=state_id,
        )
        if len(groups) != 28:
            raise RuntimeError("DD-254 serial color count changed")
        return matrix

    total_started = time.perf_counter()
    serial_started = time.perf_counter()
    serial = _run_path("serial", serial_context, payload, serial_factory)
    serial_wall = time.perf_counter() - serial_started

    trajectory = payload["trajectory"]
    mp_context = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(trajectory["worker_count"]),
        mp_context=mp_context,
        initializer=_worker_initialize,
    ) as pool:
        pings = [
            pool.submit(_worker_ping, trajectory["startup_ping_delay_sec"])
            for _ in range(int(trajectory["worker_count"]))
        ]
        startup_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(trajectory["startup_ping_delay_sec"]), 0.0
        )
        jacobians = PersistentParallelColoredJacobian(
            pool,
            _worker_evaluate,
            pattern=pattern,
            step=float(payload["solver"]["difference_step"]),
            worker_count=int(trajectory["worker_count"]),
            require_all_workers=True,
        )

        def parallel_factory(_objective, point, state_id, root_epoch, reference):
            return jacobians.build(
                point,
                state_id,
                method="backward_euler",
                root_epoch=root_epoch,
                work_basis={"reference": _reference_payload(reference)},
            )

        parallel_started = time.perf_counter()
        parallel = _run_path(
            "parallel", parallel_context, payload, parallel_factory
        )
        parallel_wall = time.perf_counter() - parallel_started
    total_wall = time.perf_counter() - total_started

    matrix_differences = [
        float(np.max(np.abs(left - right)))
        for left, right in zip(
            serial["matrices"], parallel["matrices"], strict=True
        )
    ]
    coordinate_differences = [
        float(np.max(np.abs(left.x - right.x)))
        for left, right in zip(
            serial["solutions"], parallel["solutions"], strict=True
        )
    ]
    residual_differences = [
        float(np.max(np.abs(left.fun - right.fun)))
        for left, right in zip(
            serial["solutions"], parallel["solutions"], strict=True
        )
    ]
    solver_decisions_equal = all(
        left.status == right.status
        and left.nfev == right.nfev
        and left.njev == right.njev
        and left.cost == right.cost
        and left.optimality == right.optimality
        for left, right in zip(
            serial["solutions"], parallel["solutions"], strict=True
        )
    )
    limits = payload["limits"]
    all_endpoints = serial["endpoint_reports"] + parallel["endpoint_reports"]
    scientific_endpoints = all(
        item["success"]
        and item["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and item["jacobian_rank"] == limits["rank"]
        and item["jacobian_condition"] < limits["condition"]
        and item["maximum_fugacity_residual"] < limits["fugacity_residual"]
        and item["maximum_eos_relative_residual"] < limits["eos_relative_residual"]
        and item["physical_pass"]
        for item in all_endpoints
    )
    serial_provider = compact_provider_report(serial_context["audit"].report())
    parallel_provider = compact_provider_report(parallel_context["audit"].report())
    worker_calls = jacobians.logical_provider_calls
    serial_work = serial_context["audit"].record_count
    parallel_work = parallel_context["audit"].record_count + worker_calls
    parallel_ratio = parallel_wall / serial_wall
    governed_ratio = (startup_adjusted + parallel_wall) / serial_wall
    basis_by_root: dict[str, list[Any]] = {}
    for item in jacobians.evidence:
        basis_by_root.setdefault(item.root_epoch, []).append(item)
    evolving_basis = bool(
        len(basis_by_root) == trajectory["steps_per_path"]
        and all(
            records[0].basis_rebuilds == trajectory["worker_count"]
            and all(record.basis_rebuilds == 0 for record in records[1:])
            for records in basis_by_root.values()
        )
    )
    response_difference = abs(
        serial["response"]["total_inventory_change_lbmol"]
        - parallel["response"]["total_inventory_change_lbmol"]
    )
    gates = {
        "paths_complete": len(serial["evaluations"])
        == len(parallel["evaluations"])
        == trajectory["steps_per_path"],
        "scientific_endpoints": scientific_endpoints,
        "solver_decisions": solver_decisions_equal,
        "jacobians_exact": max(matrix_differences)
        <= limits["matrix_absolute_difference"],
        "coordinates_exact": max(coordinate_differences)
        <= limits["coordinate_absolute_difference"],
        "residuals_exact": max(residual_differences)
        <= limits["coordinate_absolute_difference"],
        "response_exact": response_difference
        <= limits["response_absolute_difference_lbmol"],
        "component_identity": max(
            serial["response"]["component_inventory_identity_max_abs_lbmol"],
            parallel["response"]["component_inventory_identity_max_abs_lbmol"],
        )
        < limits["component_identity_lbmol"],
        "energy_identity": max(
            serial["response"]["energy_identity_relative"],
            parallel["response"]["energy_identity_relative"],
        )
        < limits["energy_identity_relative"],
        "process_isolation": all(
            len(item.worker_ids) == trajectory["worker_count"]
            for item in jacobians.evidence
        ),
        "evolving_basis": evolving_basis,
        "provider": serial_provider["pass"]
        and parallel_provider["pass"]
        and not serial_provider["fallback_attempted"]
        and not parallel_provider["fallback_attempted"]
        and all(item.provider_pass and not item.fallback_attempted for item in jacobians.evidence),
        "logical_work_parity": serial_work == parallel_work,
        "provider_calls": serial_work < limits["logical_provider_calls_each_path"]
        and parallel_work < limits["logical_provider_calls_each_path"],
        "parallel_speed": parallel_ratio
        <= limits["parallel_trajectory_time_ratio"],
        "governed_speed": governed_ratio
        <= limits["governed_time_ratio_including_startup"],
        "wall_clock": total_wall < limits["wall_clock_sec"],
        "no_retry_or_controller": True,
    }
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "persistent_parallel_vapor_holdup_trajectory_exact_and_faster"
            if passed
            else "persistent_parallel_vapor_holdup_trajectory_failed"
        ),
        "decision": (
            "adopt_persistent_parallel_vapor_holdup_step_path"
            if passed
            else "retain_serial_vapor_holdup_step_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "serial": {
            "wall_clock_sec": serial_wall,
            "endpoints": serial["endpoint_reports"],
            "response": serial["response"],
            "main_provider_calls": serial_context["audit"].record_count,
        },
        "parallel": {
            "wall_clock_sec": parallel_wall,
            "endpoints": parallel["endpoint_reports"],
            "response": parallel["response"],
            "main_provider_calls": parallel_context["audit"].record_count,
            "worker_provider_calls": worker_calls,
        },
        "comparison": {
            "matrix_max_abs_differences": matrix_differences,
            "coordinate_max_abs_differences": coordinate_differences,
            "residual_max_abs_differences": residual_differences,
            "response_absolute_difference_lbmol": response_difference,
            "serial_logical_work": serial_work,
            "parallel_logical_work": parallel_work,
            "parallel_trajectory_time_ratio": parallel_ratio,
            "parallel_trajectory_speedup": 1.0 / parallel_ratio,
            "governed_time_ratio_including_startup": governed_ratio,
        },
        "parallel_jacobian_evidence": [
            {
                "root_epoch": item.root_epoch,
                "state_id": item.state_id,
                "worker_ids": list(item.worker_ids),
                "basis_rebuilds": item.basis_rebuilds,
                "logical_provider_calls": item.logical_provider_calls,
            }
            for item in jacobians.evidence
        ],
        "startup_process_ids": startup_ids,
        "startup_wall_sec_raw": startup_raw,
        "startup_wall_sec_adjusted": startup_adjusted,
        "total_wall_clock_sec": total_wall,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "controller_attempted": False,
        "longer_trajectory_attempted": False,
    }
    destination = ROOT / result_path
    document = ROOT / result_doc_path
    matrix_destination = ROOT / evidence_path
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(report), encoding="utf-8")
    np.savez_compressed(
        matrix_destination,
        serial_coordinates=np.stack([item.x for item in serial["solutions"]]),
        parallel_coordinates=np.stack([item.x for item in parallel["solutions"]]),
        serial_final_liquid_inventory=serial["evaluations"][-1].endpoint.liquid_component_inventory_lbmol,
        serial_final_vapor_inventory=serial["evaluations"][-1].endpoint.vapor_component_inventory_lbmol,
        parallel_final_liquid_inventory=parallel["evaluations"][-1].endpoint.liquid_component_inventory_lbmol,
        parallel_final_vapor_inventory=parallel["evaluations"][-1].endpoint.vapor_component_inventory_lbmol,
    )
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    comparison = payload["comparison"]
    return "\n".join(
        (
            "# DD-254 Persistent-Parallel Vapor-Holdup Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Serial/parallel endpoints: `{len(payload['serial']['endpoints'])} / {len(payload['parallel']['endpoints'])}`",
            f"- Maximum Jacobian difference: `{max(comparison['matrix_max_abs_differences']):.6e}`",
            f"- Maximum coordinate difference: `{max(comparison['coordinate_max_abs_differences']):.6e}`",
            f"- Serial/parallel trajectory wall: `{payload['serial']['wall_clock_sec']:.6f} s` / `{payload['parallel']['wall_clock_sec']:.6f} s`",
            f"- Parallel trajectory speedup: `{comparison['parallel_trajectory_speedup']:.3f}x`",
            f"- Adjusted startup: `{payload['startup_wall_sec_adjusted']:.3f} s`",
            f"- Serial/parallel logical work: `{comparison['serial_logical_work']} / {comparison['parallel_logical_work']}`",
            f"- Gates: `{payload['gates']}`",
            "- Retry, alternate grid, controller, or longer trajectory: `False`",
            "",
        )
    )


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
        print(
            json.dumps(
                {
                    "schema_id": report["schema_id"],
                    "contract_payload_sha256": report["contract_payload_sha256"],
                    "trajectory": report["trajectory"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc, args.evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
