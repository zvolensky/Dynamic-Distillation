#!/usr/bin/env python
"""Prepare or execute DD-251's vapor-holdup parallel Jacobian benchmark."""

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


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_stationary_hold as dd248  # noqa: E402

from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    ColoredCentralDifferenceTask,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)


SCHEMA = "dd251-core-v3-c3c4-vapor-holdup-parallel-jacobian-contract-v1"
RESULT_SCHEMA = "dd251-core-v3-c3c4-vapor-holdup-parallel-jacobian-result-v1"
CONTRACT = Path(
    "logs/dd251_core_v3_c3c4_vapor_holdup_parallel_jacobian_contract_20260820.json"
)
RESULT = Path(
    "logs/dd251_core_v3_c3c4_vapor_holdup_parallel_jacobian_20260820.json"
)
CONTRACT_DOC = Path(
    "docs/dd_251_core_v3_c3c4_vapor_holdup_parallel_jacobian_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_251_core_v3_c3c4_vapor_holdup_parallel_jacobian_20260820.md"
)
DD249_MATRIX = Path(
    "logs/dd249_core_v3_c3c4_vapor_holdup_small_moving_step_20260820.npz"
)
IMPLEMENTATION = (
    Path("tools/benchmark_core_v3_vapor_holdup_parallel_jacobian.py"),
    Path("src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py"),
    Path("src/dynamic_distillation/core_v3/colored_jacobian_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
)

_WORKER_OBJECTIVE = None
_WORKER_AUDIT = None
_WORKER_PROVIDER = None


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


def _matrix_sha(matrix: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(matrix, dtype="<f8").tobytes()).hexdigest()


def _context():
    problem = dd248._problem()
    multiplier = 1.001
    balance_inputs = replace(
        problem["balance_inputs"],
        feed_component_lbmolph=(problem["balance_inputs"].feed_component_lbmolph * multiplier),
        feed_enthalpy_BTUph=(problem["balance_inputs"].feed_enthalpy_BTUph * multiplier),
    )
    numerical = replace(problem["numerical"], timestep_sec=0.25)
    point = np.asarray(np.load(ROOT / DD249_MATRIX)["full_coordinates"], dtype=float)
    pattern = vapor_holdup_structural_pattern(problem["contract"])
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_vapor_holdup_implicit_residual(
            problem["contract"],
            problem["geometry"],
            problem["reference"],
            balance_inputs,
            problem["spec"].hydraulic_geometry,
            numerical,
            provider,
            audit,
            candidate,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled

    return point, pattern, objective, audit, provider


def _worker_initialize() -> None:
    global _WORKER_OBJECTIVE, _WORKER_AUDIT, _WORKER_PROVIDER
    _point, _pattern, objective, audit, provider = _context()
    _WORKER_OBJECTIVE = objective
    _WORKER_AUDIT = audit
    _WORKER_PROVIDER = provider


def _worker_ping(delay_sec: float) -> int:
    if _WORKER_OBJECTIVE is None:
        raise RuntimeError("DD-251 worker was not initialized")
    time.sleep(float(delay_sec))
    return int(os.getpid())


def _worker_evaluate(task: ColoredCentralDifferenceTask) -> dict[str, Any]:
    if _WORKER_OBJECTIVE is None or _WORKER_AUDIT is None:
        raise RuntimeError("DD-251 worker context is unavailable")
    before = _WORKER_AUDIT.record_count
    residual = np.asarray(
        _WORKER_OBJECTIVE(np.asarray(task.coordinates), task.state_id), dtype=float
    )
    report = _WORKER_AUDIT.report()
    return {
        "order": int(task.order),
        "residual": residual.tolist(),
        "process_id": int(os.getpid()),
        "logical_provider_calls": int(_WORKER_AUDIT.record_count - before),
        "provider_pass": bool(report["pass"]),
        "fallback_attempted": bool(report["fallback_attempted"]),
    }


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    dd250 = json.loads(
        (
            ROOT
            / "logs/dd250_core_v3_c3c4_vapor_holdup_short_trajectory_20260820.json"
        ).read_text(encoding="utf-8")
    )
    if not dd250.get("pass_gate"):
        raise RuntimeError("DD-251 requires accepted DD-250 evidence")
    point, pattern, _objective, _audit, _provider = _context()
    tasks, groups = build_colored_central_difference_tasks(
        point,
        pattern=pattern,
        step=1.0e-5,
        state_id="dd251:structural",
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd249.RESULT.as_posix(): _sha(dd249.RESULT),
            DD249_MATRIX.as_posix(): _sha(DD249_MATRIX),
            "logs/dd250_core_v3_c3c4_vapor_holdup_short_trajectory_20260820.json": _sha(
                Path("logs/dd250_core_v3_c3c4_vapor_holdup_short_trajectory_20260820.json")
            ),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "benchmark": {
            "state": "DD-249 accepted full 0.25 s endpoint",
            "matrix_shape": list(pattern.shape),
            "color_count": len(groups),
            "task_count": len(tasks),
            "difference_step": 1.0e-5,
            "worker_count": 8,
            "spawn_context": True,
            "startup_ping_delay_sec": 0.15,
            "matrix_absolute_limit": 1.0e-10,
            "matrix_relative_limit": 1.0e-10,
            "spectrum_relative_limit": 1.0e-8,
            "rank": 258,
            "condition_limit": 1.0e8,
            "parallel_time_ratio_limit": 0.75,
            "logical_call_limit_each": 20000,
            "wall_clock_limit_sec": 180.0,
        },
        "hard_stops": [
            "a source or implementation hash changes",
            "workers do not own isolated provider instances",
            "the serial and parallel matrices differ outside the frozen numerical limits",
            "rank, condition, provider ownership, call, or wall gates fail",
            "eight workers do not reduce matrix wall time by at least 25 percent",
            "a solve, state advance, controller, or trajectory occurs",
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
        raise RuntimeError("DD-251 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    benchmark = payload["benchmark"]
    return "\n".join(
        (
            "# DD-251 Vapor-Holdup Parallel Jacobian Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Matrix: `{benchmark['matrix_shape'][0]} x {benchmark['matrix_shape'][1]}` with `{benchmark['color_count']}` colors and `{benchmark['task_count']}` tasks.",
            "- Comparison: one serial matrix and one eight-worker process-isolated matrix.",
            "- State: accepted DD-249 full-step endpoint.",
            "- Matrix, rank, spectrum, condition, provider, call, and wall gates are fixed.",
            "- Performance gate: parallel matrix wall at most 75% of serial wall.",
            "- Nonlinear solve, state advance, controller, or trajectory: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-251 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-251 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-251 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-251 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def execute(contract_path: Path, result_path: Path, result_doc_path: Path) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    benchmark = payload["benchmark"]
    point, pattern, objective, serial_audit, _provider = _context()
    tasks, groups = build_colored_central_difference_tasks(
        point,
        pattern=pattern,
        step=float(benchmark["difference_step"]),
        state_id="dd251:matrix",
    )
    total_started = time.perf_counter()
    serial_started = time.perf_counter()
    serial_raw = [
        ColoredCentralDifferenceResult(
            order=task.order,
            residual=tuple(
                float(value)
                for value in objective(np.asarray(task.coordinates), task.state_id)
            ),
        )
        for task in tasks
    ]
    serial_matrix = assemble_colored_central_difference_jacobian(
        tasks,
        serial_raw,
        pattern=pattern,
        step=float(benchmark["difference_step"]),
    )
    serial_wall = time.perf_counter() - serial_started
    serial_report = serial_audit.report()

    context = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(benchmark["worker_count"]),
        mp_context=context,
        initializer=_worker_initialize,
    ) as pool:
        pings = [
            pool.submit(_worker_ping, benchmark["startup_ping_delay_sec"])
            for _ in range(int(benchmark["worker_count"]))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(benchmark["startup_ping_delay_sec"]), 0.0
        )
        parallel_started = time.perf_counter()
        worker_raw = list(pool.map(_worker_evaluate, tasks, chunksize=1))
        parallel_wall = time.perf_counter() - parallel_started
    total_wall = time.perf_counter() - total_started
    parallel_matrix = assemble_colored_central_difference_jacobian(
        tasks,
        [
            ColoredCentralDifferenceResult(
                order=int(item["order"]),
                residual=tuple(float(value) for value in item["residual"]),
            )
            for item in worker_raw
        ],
        pattern=pattern,
        step=float(benchmark["difference_step"]),
    )
    serial_rank, serial_condition, serial_singular = dd249._rank_condition(serial_matrix)
    parallel_rank, parallel_condition, parallel_singular = dd249._rank_condition(parallel_matrix)
    maximum_difference = float(np.max(np.abs(serial_matrix - parallel_matrix)))
    relative_difference = dd249._relative_change(serial_matrix, parallel_matrix)
    spectrum_difference = dd249._relative_change(serial_singular, parallel_singular)
    worker_ids = sorted({int(item["process_id"]) for item in worker_raw})
    worker_calls = int(sum(int(item["logical_provider_calls"]) for item in worker_raw))
    parallel_ratio = parallel_wall / serial_wall
    gates = {
        "task_shape": len(groups) == benchmark["color_count"] and len(tasks) == benchmark["task_count"],
        "process_isolation": len(ping_ids) == benchmark["worker_count"] and len(worker_ids) == benchmark["worker_count"],
        "matrix_absolute": maximum_difference <= benchmark["matrix_absolute_limit"],
        "matrix_relative": relative_difference <= benchmark["matrix_relative_limit"],
        "spectrum": spectrum_difference <= benchmark["spectrum_relative_limit"],
        "rank": serial_rank == benchmark["rank"] and parallel_rank == benchmark["rank"],
        "condition": serial_condition < benchmark["condition_limit"] and parallel_condition < benchmark["condition_limit"],
        "provider": bool(serial_report["pass"])
        and all(bool(item["provider_pass"]) for item in worker_raw)
        and not any(bool(item["fallback_attempted"]) for item in worker_raw),
        "provider_calls": serial_audit.record_count < benchmark["logical_call_limit_each"]
        and worker_calls < benchmark["logical_call_limit_each"],
        "meaningful_speed": parallel_ratio <= benchmark["parallel_time_ratio_limit"],
        "wall_clock": total_wall < benchmark["wall_clock_limit_sec"],
        "no_solve_or_state_advance": True,
    }
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "vapor_holdup_parallel_jacobian_qualified"
            if passed
            else "vapor_holdup_parallel_jacobian_not_qualified"
        ),
        "decision": (
            "authorize_persistent_parallel_vapor_holdup_step_integration"
            if passed
            else "retain_serial_vapor_holdup_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "serial": {
            "wall_clock_sec": serial_wall,
            "logical_provider_calls": serial_audit.record_count,
            "matrix_sha256": _matrix_sha(serial_matrix),
            "rank": serial_rank,
            "condition": serial_condition,
        },
        "parallel": {
            "wall_clock_sec": parallel_wall,
            "logical_provider_calls": worker_calls,
            "matrix_sha256": _matrix_sha(parallel_matrix),
            "rank": parallel_rank,
            "condition": parallel_condition,
            "worker_ids": worker_ids,
            "ping_worker_ids": ping_ids,
        },
        "comparison": {
            "matrix_max_abs_difference": maximum_difference,
            "matrix_relative_difference": relative_difference,
            "spectrum_relative_difference": spectrum_difference,
            "parallel_time_ratio": parallel_ratio,
            "speedup": 1.0 / parallel_ratio,
        },
        "startup_wall_sec_raw": startup_raw,
        "startup_wall_sec_adjusted": startup_adjusted,
        "total_wall_clock_sec": total_wall,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "nonlinear_solve_attempted": False,
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
            "# DD-251 Vapor-Holdup Parallel Jacobian Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Serial/parallel matrix wall: `{payload['serial']['wall_clock_sec']:.6f} s` / `{payload['parallel']['wall_clock_sec']:.6f} s`",
            f"- Parallel speedup: `{comparison['speedup']:.3f}x`",
            f"- Matrix maximum difference: `{comparison['matrix_max_abs_difference']:.6e}`",
            f"- Serial/parallel rank: `{payload['serial']['rank']} / {payload['parallel']['rank']}`",
            f"- Worker startup: `{payload['startup_wall_sec_adjusted']:.3f} s` adjusted",
            f"- Gates: `{payload['gates']}`",
            "- Solve, state advance, controller, or trajectory: `False`",
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
                    "benchmark": report["benchmark"],
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
