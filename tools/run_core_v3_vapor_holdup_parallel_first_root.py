#!/usr/bin/env python
"""Prepare or execute DD-252's serial/parallel first-root equivalence gate."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
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

import benchmark_core_v3_vapor_holdup_parallel_jacobian as dd251  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


SCHEMA = "dd252-core-v3-c3c4-vapor-holdup-parallel-first-root-contract-v1"
RESULT_SCHEMA = "dd252-core-v3-c3c4-vapor-holdup-parallel-first-root-result-v1"
CONTRACT = Path(
    "logs/dd252_core_v3_c3c4_vapor_holdup_parallel_first_root_contract_20260820.json"
)
RESULT = Path(
    "logs/dd252_core_v3_c3c4_vapor_holdup_parallel_first_root_20260820.json"
)
CONTRACT_DOC = Path(
    "docs/dd_252_core_v3_c3c4_vapor_holdup_parallel_first_root_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_252_core_v3_c3c4_vapor_holdup_parallel_first_root_20260820.md"
)
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_parallel_first_root.py"),
    Path("tools/benchmark_core_v3_vapor_holdup_parallel_jacobian.py"),
    Path("src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
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


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    benchmark = json.loads((ROOT / dd251.RESULT).read_text(encoding="utf-8"))
    moving_contract = json.loads((ROOT / dd249.CONTRACT).read_text(encoding="utf-8"))
    if not benchmark.get("pass_gate"):
        raise RuntimeError("DD-252 requires accepted DD-251 evidence")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd251.CONTRACT.as_posix(): _sha(dd251.CONTRACT),
            dd251.RESULT.as_posix(): _sha(dd251.RESULT),
            dd249.CONTRACT.as_posix(): _sha(dd249.CONTRACT),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "root": {
            "state": "DD-249 first full 0.25 s moving endpoint",
            "serial_root_count": 1,
            "parallel_root_count": 1,
            "worker_count": 8,
            "persistent_pool_count": 1,
            "spawn_context": True,
            "startup_ping_delay_sec": 0.15,
        },
        "solver": moving_contract["solver"],
        "limits": {
            "scaled_residual": 1.0e-8,
            "rank": 258,
            "condition": 1.0e8,
            "jacobian_absolute_difference": 1.0e-10,
            "coordinate_absolute_difference": 1.0e-12,
            "residual_absolute_difference": 1.0e-12,
            "parallel_solve_time_ratio": 0.75,
            "main_provider_calls_each": 20000,
            "worker_provider_calls": 100000,
            "wall_clock_sec": 240.0,
        },
        "hard_stops": [
            "a source or implementation hash changes",
            "serial and parallel SciPy decisions, Jacobians, or endpoints differ outside fixed limits",
            "either root fails residual, rank, condition, provider, call, or wall gates",
            "all eight isolated workers do not participate",
            "parallel solve wall excluding startup is not at least 25 percent lower",
            "a root is accepted as a state advance or a retry, controller, or trajectory occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-252 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-252 Vapor-Holdup Parallel First-Root Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Root: first DD-249 `0.25 s`, `+0.1%` feed endpoint.",
            "- Solves: one serial and one persistent eight-worker parallel root.",
            "- Main process retains SciPy residual, trust-region, convergence, and acceptance decisions.",
            "- Delegated work: only 28-color central-difference residual tasks.",
            "- Endpoint agreement: `1e-12`; Jacobian agreement: `1e-10`.",
            "- Performance: parallel solve wall at most 75% of serial wall, excluding startup.",
            "- State advance, retry, controller, or trajectory: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-252 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-252 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-252 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-252 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _root_summary(solution: Any, wall: float) -> dict[str, Any]:
    matrix = np.asarray(solution.jac, dtype=float)
    rank, condition, _singular = dd249._rank_condition(matrix)
    return {
        "success": bool(solution.success),
        "status": int(solution.status),
        "message": str(solution.message),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "cost": float(solution.cost),
        "optimality": float(solution.optimality),
        "scaled_residual_inf_norm": float(np.max(np.abs(solution.fun))),
        "rank": rank,
        "condition": condition,
        "wall_clock_sec": wall,
    }


def execute(contract_path: Path, result_path: Path, result_doc_path: Path) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    serial_point, serial_pattern, serial_objective, serial_audit, _serial_provider = dd251._context()
    parallel_point, parallel_pattern, parallel_objective, parallel_audit, _parallel_provider = dd251._context()
    if not np.array_equal(serial_pattern, parallel_pattern):
        raise RuntimeError("DD-252 serial and parallel patterns differ")
    if not np.array_equal(serial_point, parallel_point):
        raise RuntimeError("DD-252 serial and parallel target evidence differs")
    lower, upper = dd249._bounds()
    x_scale = np.asarray(payload["solver"]["x_scale"], dtype=float)
    serial_matrices: list[np.ndarray] = []
    parallel_matrices: list[np.ndarray] = []
    worker_evidence: list[dict[str, Any]] = []

    def serial_jacobian(candidate: np.ndarray) -> np.ndarray:
        matrix, groups = colored_central_difference_jacobian(
            serial_objective,
            candidate,
            pattern=serial_pattern,
            step=float(payload["solver"]["difference_step"]),
            state_id=f"dd252:serial:jacobian:{len(serial_matrices) + 1}",
        )
        if len(groups) != 28:
            raise RuntimeError("DD-252 serial color count changed")
        serial_matrices.append(matrix.copy())
        return matrix

    total_started = time.perf_counter()
    serial_started = time.perf_counter()
    serial_solution = least_squares(
        lambda point: serial_objective(point, "dd252:serial:residual"),
        np.zeros(258),
        jac=serial_jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=x_scale,
        ftol=float(payload["solver"]["ftol"]),
        xtol=float(payload["solver"]["xtol"]),
        gtol=float(payload["solver"]["gtol"]),
        max_nfev=int(payload["solver"]["max_nfev_per_step"]),
        verbose=0,
    )
    serial_wall = time.perf_counter() - serial_started

    root = payload["root"]
    context = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(root["worker_count"]),
        mp_context=context,
        initializer=dd251._worker_initialize,
    ) as pool:
        pings = [
            pool.submit(dd251._worker_ping, root["startup_ping_delay_sec"])
            for _ in range(int(root["worker_count"]))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(startup_raw - float(root["startup_ping_delay_sec"]), 0.0)

        def parallel_jacobian(candidate: np.ndarray) -> np.ndarray:
            tasks, groups = build_colored_central_difference_tasks(
                candidate,
                pattern=parallel_pattern,
                step=float(payload["solver"]["difference_step"]),
                state_id=f"dd252:parallel:jacobian:{len(parallel_matrices) + 1}",
            )
            raw = list(pool.map(dd251._worker_evaluate, tasks, chunksize=1))
            matrix = assemble_colored_central_difference_jacobian(
                tasks,
                [
                    ColoredCentralDifferenceResult(
                        order=int(item["order"]),
                        residual=tuple(float(value) for value in item["residual"]),
                    )
                    for item in raw
                ],
                pattern=parallel_pattern,
                step=float(payload["solver"]["difference_step"]),
            )
            parallel_matrices.append(matrix.copy())
            worker_evidence.append(
                {
                    "worker_ids": sorted({int(item["process_id"]) for item in raw}),
                    "logical_provider_calls": int(
                        sum(int(item["logical_provider_calls"]) for item in raw)
                    ),
                    "provider_pass": all(bool(item["provider_pass"]) for item in raw),
                    "fallback_attempted": any(bool(item["fallback_attempted"]) for item in raw),
                    "color_count": len(groups),
                    "task_count": len(raw),
                }
            )
            return matrix

        parallel_started = time.perf_counter()
        parallel_solution = least_squares(
            lambda point: parallel_objective(point, "dd252:parallel:residual"),
            np.zeros(258),
            jac=parallel_jacobian,
            bounds=(lower, upper),
            method="trf",
            x_scale=x_scale,
            ftol=float(payload["solver"]["ftol"]),
            xtol=float(payload["solver"]["xtol"]),
            gtol=float(payload["solver"]["gtol"]),
            max_nfev=int(payload["solver"]["max_nfev_per_step"]),
            verbose=0,
        )
        parallel_wall = time.perf_counter() - parallel_started
    total_wall = time.perf_counter() - total_started

    serial_summary = _root_summary(serial_solution, serial_wall)
    parallel_summary = _root_summary(parallel_solution, parallel_wall)
    if len(serial_matrices) != len(parallel_matrices):
        matrix_difference = float("inf")
    else:
        matrix_difference = max(
            float(np.max(np.abs(left - right)))
            for left, right in zip(serial_matrices, parallel_matrices, strict=True)
        )
    coordinate_difference = float(
        np.max(np.abs(serial_solution.x - parallel_solution.x))
    )
    residual_difference = float(
        np.max(np.abs(serial_solution.fun - parallel_solution.fun))
    )
    worker_calls = int(sum(item["logical_provider_calls"] for item in worker_evidence))
    limits = payload["limits"]
    solve_ratio = parallel_wall / serial_wall
    gates = {
        "root_success": serial_solution.success and parallel_solution.success,
        "root_residual": serial_summary["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and parallel_summary["scaled_residual_inf_norm"] < limits["scaled_residual"],
        "rank": serial_summary["rank"] == limits["rank"]
        and parallel_summary["rank"] == limits["rank"],
        "condition": serial_summary["condition"] < limits["condition"]
        and parallel_summary["condition"] < limits["condition"],
        "solver_decisions": serial_summary["status"] == parallel_summary["status"]
        and serial_summary["nfev"] == parallel_summary["nfev"]
        and serial_summary["njev"] == parallel_summary["njev"],
        "jacobian_count": len(serial_matrices) == len(parallel_matrices) > 0,
        "jacobian_equivalence": matrix_difference <= limits["jacobian_absolute_difference"],
        "coordinate_equivalence": coordinate_difference <= limits["coordinate_absolute_difference"],
        "residual_equivalence": residual_difference <= limits["residual_absolute_difference"],
        "process_isolation": len(ping_ids) == root["worker_count"]
        and all(len(item["worker_ids"]) == root["worker_count"] for item in worker_evidence),
        "worker_tasks": all(
            item["color_count"] == 28 and item["task_count"] == 56
            for item in worker_evidence
        ),
        "provider": serial_audit.report()["pass"]
        and parallel_audit.report()["pass"]
        and all(item["provider_pass"] for item in worker_evidence)
        and not any(item["fallback_attempted"] for item in worker_evidence),
        "provider_calls": serial_audit.record_count < limits["main_provider_calls_each"]
        and parallel_audit.record_count < limits["main_provider_calls_each"]
        and worker_calls < limits["worker_provider_calls"],
        "meaningful_speed": solve_ratio <= limits["parallel_solve_time_ratio"],
        "wall_clock": total_wall < limits["wall_clock_sec"],
        "no_state_advance": True,
    }
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "vapor_holdup_parallel_first_root_exact_and_faster"
            if passed
            else "vapor_holdup_parallel_first_root_failed"
        ),
        "decision": (
            "authorize_persistent_parallel_vapor_holdup_trajectory_contract"
            if passed
            else "retain_serial_vapor_holdup_solver"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "serial": serial_summary,
        "parallel": parallel_summary,
        "comparison": {
            "jacobian_count": len(serial_matrices),
            "jacobian_max_abs_difference": matrix_difference,
            "coordinate_max_abs_difference": coordinate_difference,
            "residual_max_abs_difference": residual_difference,
            "parallel_solve_time_ratio": solve_ratio,
            "parallel_solve_speedup": 1.0 / solve_ratio,
        },
        "worker_evidence": worker_evidence,
        "worker_logical_provider_calls": worker_calls,
        "serial_main_provider_calls": serial_audit.record_count,
        "parallel_main_provider_calls": parallel_audit.record_count,
        "startup_wall_sec_raw": startup_raw,
        "startup_wall_sec_adjusted": startup_adjusted,
        "total_wall_clock_sec": total_wall,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "state_advance_attempted": False,
        "controller_attempted": False,
        "trajectory_attempted": False,
        "retry_attempted": False,
    }
    destination = ROOT / result_path
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(report), encoding="utf-8")
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    comparison = payload["comparison"]
    return "\n".join(
        (
            "# DD-252 Vapor-Holdup Parallel First-Root Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Serial/parallel residual: `{payload['serial']['scaled_residual_inf_norm']:.6e}` / `{payload['parallel']['scaled_residual_inf_norm']:.6e}`",
            f"- Serial/parallel `nfev,njev`: `{payload['serial']['nfev']},{payload['serial']['njev']}` / `{payload['parallel']['nfev']},{payload['parallel']['njev']}`",
            f"- Jacobian evaluations: `{comparison['jacobian_count']}` each",
            f"- Jacobian/coordinate difference: `{comparison['jacobian_max_abs_difference']:.6e}` / `{comparison['coordinate_max_abs_difference']:.6e}`",
            f"- Serial/parallel solve wall: `{payload['serial']['wall_clock_sec']:.6f} s` / `{payload['parallel']['wall_clock_sec']:.6f} s`",
            f"- Parallel solve speedup: `{comparison['parallel_solve_speedup']:.3f}x`",
            f"- Adjusted worker startup: `{payload['startup_wall_sec_adjusted']:.3f} s`",
            f"- Gates: `{payload['gates']}`",
            "- State advance, retry, controller, or trajectory: `False`",
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
                    "root": report["root"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc)
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
