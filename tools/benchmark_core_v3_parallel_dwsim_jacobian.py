#!/usr/bin/env python
"""Prepare or execute DD-147 process-isolated parallel DWSIM Jacobian benchmark."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
import run_core_v3_longer_post_cachefix_captured_trajectory as dd146
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    evaluate_controlled_terminal_zero_time,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (
    ColoredCentralDifferenceResult,
    ColoredCentralDifferenceTask,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


SCHEMA = "dd147-core-v3-parallel-dwsim-jacobian-benchmark-contract-v1"
RESULT_SCHEMA = "dd147-core-v3-parallel-dwsim-jacobian-benchmark-result-v1"
DD146_CONTRACT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_contract_20260805.json"
)
DD146_RESULT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_20260805.json"
)
CONTRACT = Path(
    "logs/dd147_core_v3_parallel_dwsim_jacobian_benchmark_contract_20260805.json"
)
RESULT = Path(
    "logs/dd147_core_v3_parallel_dwsim_jacobian_benchmark_20260805.json"
)
CONTRACT_DOC = Path(
    "docs/dd_147_core_v3_parallel_dwsim_jacobian_benchmark_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_147_core_v3_parallel_dwsim_jacobian_benchmark_20260805.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd146.IMPLEMENTATION,
            "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
            "tests/test_core_v3_parallel_colored_jacobian_v1.py",
            "tools/benchmark_core_v3_parallel_dwsim_jacobian.py",
        )
    )
)


_WORKER_OBJECTIVE = None
_WORKER_CALL_AUDIT = None


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _matrix_sha(matrix: Any) -> str:
    return hashlib.sha256(np.asarray(matrix, dtype="<f8").tobytes()).hexdigest()


def _worker_initialize(contract_path: str) -> None:
    global _WORKER_OBJECTIVE, _WORKER_CALL_AUDIT
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = (
        dd121._context(payload)
    )
    contract = dd128._contract(payload)
    point = np.asarray(payload["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(payload["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    original_setpoints = TerminalLevelSetpoints(**payload["original_level_setpoints"])
    moved_setpoints = TerminalLevelSetpoints(**payload["moved_level_setpoints"])
    zero = evaluate_controlled_terminal_zero_time(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        controller_memory=memory,
        level_setpoints=original_setpoints,
        solve_coordinates=point,
        state_id=f"dd147:worker_{os.getpid()}:warmup",
        evaluation_kind="residual",
        **common,
    )
    top_u = float(zero.base.live_internal_energy_BTU[0])
    step_common = {
        "component_rate_scale_lbmolph": float(payload["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_controlled_terminal_backward_euler_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=inventory,
            previous_top_internal_energy_BTU=top_u,
            previous_lower_internal_energy_BTU=lower_u,
            previous_controller_memory=memory,
            level_setpoints=moved_setpoints,
            solve_coordinates=candidate,
            step_seconds=1.0,
            state_id=state_id,
            evaluation_kind="jacobian",
            **step_common,
        ).scaled

    _WORKER_OBJECTIVE = objective
    _WORKER_CALL_AUDIT = call_audit


def _worker_ping(delay_seconds: float) -> int:
    if _WORKER_OBJECTIVE is None:
        raise RuntimeError("DD-147 worker objective was not initialized")
    time.sleep(float(delay_seconds))
    return int(os.getpid())


def _worker_evaluate(task: ColoredCentralDifferenceTask) -> dict[str, Any]:
    if _WORKER_OBJECTIVE is None or _WORKER_CALL_AUDIT is None:
        raise RuntimeError("DD-147 worker objective was not initialized")
    before = len(_WORKER_CALL_AUDIT.records)
    started = time.perf_counter()
    residual = np.asarray(
        _WORKER_OBJECTIVE(np.asarray(task.coordinates, dtype=float), task.state_id),
        dtype=float,
    ).reshape((-1,))
    elapsed = time.perf_counter() - started
    after = len(_WORKER_CALL_AUDIT.records)
    return {
        "order": int(task.order),
        "residual": [float(value) for value in residual],
        "process_id": int(os.getpid()),
        "provider_calls": int(after - before),
        "wall_clock_sec": float(elapsed),
    }


def _first_dd146_matrix(result: Mapping[str, Any]) -> np.ndarray:
    return np.asarray(
        result["captured_trajectory_evidence"]["dd134:coarse"][0]["capture"][
            "frozen_jacobian"
        ],
        dtype=float,
    )


def prepare() -> dict[str, Any]:
    prior_contract = _load(DD146_CONTRACT)
    prior_result = _load(DD146_RESULT)
    if (
        not prior_result["pass"]
        or prior_result["decision"]
        != "authorize_separately_frozen_trajectory_efficiency_design"
    ):
        raise RuntimeError("DD-147 requires the immutable passing DD-146 decision")
    accepted = _first_dd146_matrix(prior_result)
    singular = np.linalg.svd(accepted, compute_uv=False)

    payload = {
        key: value
        for key, value in prior_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "source_contract_payload_sha256",
            "source_dd144_result_sha256",
            "source_dd145_result_sha256",
            "scientific_contract_changes",
            "administrative_contract_changes",
            "implementation_sha256",
            "hard_stops",
            "contract_payload_sha256",
            "live_property_evaluation_attempted",
            "nonlinear_solve_attempted",
            "timestep_attempted",
            "dynamic_integration_attempted",
            "campaign_executed",
        }
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD146_CONTRACT, DD146_RESULT)
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd146_result_sha256": _sha(ROOT / DD146_RESULT),
            "accepted_matrix_sha256": _matrix_sha(accepted),
            "accepted_matrix_rank": int(np.linalg.matrix_rank(accepted)),
            "accepted_matrix_condition": float(singular[0] / singular[-1]),
            "benchmark": {
                "state": "DD-146 first coarse root start",
                "step_seconds": 1.0,
                "jacobian_step": float(prior_contract["jacobian_step"]),
                "color_count": 21,
                "tasks_per_matrix": 42,
                "provider_calls_per_task": 28,
                "provider_calls_per_matrix": 1176,
                "worker_counts": [1, 2, 4],
                "schedule": [[1, 2, 4], [4, 2, 1], [2, 1, 4]],
                "repeats_per_worker_count": 3,
                "fresh_pool_per_repeat": True,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.25,
                "matrix_absolute_limit": 1.0e-10,
                "matrix_relative_frobenius_limit": 1.0e-10,
                "singular_spectrum_relative_limit": 1.0e-8,
                "condition_limit": 1.0e8,
                "four_worker_time_ratio_limit": 0.60,
                "four_worker_speedup_minimum": 1.0 / 0.60,
                "projected_dd146_wall_limit_sec": 75.0,
                "dd146_wall_clock_sec": float(prior_result["wall_clock_sec"]),
                "dd146_jacobian_provider_call_fraction": 211680.0 / 221845.0,
                "benchmark_wall_limit_sec": 300.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-146 source or DD-147 implementation hash changes",
                "any worker shares mutable DWSIM provider state across processes",
                "any of the nine frozen pool runs is omitted, retried, or reordered",
                "any matrix differs from the accepted serial matrix beyond a frozen limit",
                "rank, condition, provider-call count, task count, or process-isolation gate fails",
                "four-worker median Jacobian time exceeds 60 percent of serial median",
                "projected DD-146-equivalent wall time is not below 75 seconds",
                "a nonlinear solve, correction, state acceptance, timestep, or trajectory occurs",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-147 Frozen Parallel DWSIM Jacobian Benchmark Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- State: exact DD-146 first coarse root start",
                "- Work: one complete `50 x 50`, 21-color, central-difference Jacobian",
                "- Pools: fresh spawn-based `1`, `2`, and `4` process workers",
                "- Repetitions: three per worker count in frozen interleaved order",
                "- Process ownership: one independent live DWSIM provider per worker",
                "- Numerical agreement: absolute and relative Frobenius `<=1e-10`",
                "- Meaningful speed gate: four-worker median `<=60%` of serial median",
                "- Projected DD-146-equivalent wall gate: `<75 s` including adjusted pool startup",
                "- Benchmark wall limit: `<300 s`",
                "- Solve, correction, state acceptance, timestep, or trajectory: prohibited",
                "",
                "Passing may authorize a separately frozen parallel colored-Jacobian integration contract. Failure retains the serial path.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-147 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-147 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-147 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-147 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    benchmark = payload["benchmark"]
    prior = _load(DD146_RESULT)
    accepted = _first_dd146_matrix(prior)
    if _matrix_sha(accepted) != payload["accepted_matrix_sha256"]:
        raise RuntimeError("DD-147 accepted matrix changed")

    contract = dd128._contract(payload)
    pattern = controlled_terminal_step_pattern(contract)
    tasks, groups = build_colored_central_difference_tasks(
        payload["zero_time_coordinates"],
        pattern=pattern,
        step=float(benchmark["jacobian_step"]),
        state_id="dd147:first_coarse_root:frozen_jacobian",
    )
    context = mp.get_context("spawn")
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    contract_path = str((ROOT / CONTRACT).resolve())
    for round_index, round_workers in enumerate(benchmark["schedule"]):
        for workers in round_workers:
            pool_started = time.perf_counter()
            with ProcessPoolExecutor(
                max_workers=int(workers),
                mp_context=context,
                initializer=_worker_initialize,
                initargs=(contract_path,),
            ) as pool:
                pings = [
                    pool.submit(
                        _worker_ping, float(benchmark["startup_ping_delay_sec"])
                    )
                    for _ in range(int(workers))
                ]
                ping_pids = sorted({int(future.result()) for future in pings})
                startup_raw = time.perf_counter() - pool_started
                startup_adjusted = max(
                    startup_raw - float(benchmark["startup_ping_delay_sec"]), 0.0
                )
                jacobian_started = time.perf_counter()
                raw = list(pool.map(_worker_evaluate, tasks, chunksize=1))
                jacobian_wall = time.perf_counter() - jacobian_started
            shutdown_complete = time.perf_counter() - pool_started

            results = [
                ColoredCentralDifferenceResult(
                    order=int(item["order"]),
                    residual=tuple(float(value) for value in item["residual"]),
                )
                for item in raw
            ]
            matrix = assemble_colored_central_difference_jacobian(
                tasks,
                results,
                pattern=pattern,
                step=float(benchmark["jacobian_step"]),
            )
            singular = np.linalg.svd(matrix, compute_uv=False)
            accepted_singular = np.linalg.svd(accepted, compute_uv=False)
            delta = matrix - accepted
            records.append(
                {
                    "round": int(round_index + 1),
                    "workers": int(workers),
                    "ping_process_ids": ping_pids,
                    "task_process_ids": sorted(
                        {int(item["process_id"]) for item in raw}
                    ),
                    "startup_wall_sec_raw": float(startup_raw),
                    "startup_wall_sec_adjusted": float(startup_adjusted),
                    "jacobian_wall_sec": float(jacobian_wall),
                    "pool_lifetime_sec": float(shutdown_complete),
                    "task_count": len(raw),
                    "provider_calls": int(
                        sum(int(item["provider_calls"]) for item in raw)
                    ),
                    "per_task_provider_calls": [
                        int(item["provider_calls"]) for item in raw
                    ],
                    "task_wall_sec_sum": float(
                        sum(float(item["wall_clock_sec"]) for item in raw)
                    ),
                    "matrix": matrix.tolist(),
                    "matrix_sha256": _matrix_sha(matrix),
                    "max_abs_difference_from_accepted": float(
                        np.max(np.abs(delta))
                    ),
                    "relative_frobenius_difference_from_accepted": float(
                        np.linalg.norm(delta)
                        / max(float(np.linalg.norm(accepted)), np.finfo(float).tiny)
                    ),
                    "rank": int(np.linalg.matrix_rank(matrix)),
                    "condition": float(singular[0] / singular[-1]),
                    "singular_spectrum": singular.tolist(),
                    "singular_spectrum_relative_difference": float(
                        np.max(
                            np.abs(singular - accepted_singular)
                            / np.maximum(np.abs(accepted_singular), np.finfo(float).tiny)
                        )
                    ),
                }
            )
    elapsed = time.perf_counter() - started

    by_workers = {
        workers: [record for record in records if record["workers"] == workers]
        for workers in benchmark["worker_counts"]
    }
    medians = {
        str(workers): {
            "jacobian_wall_sec": float(
                statistics.median(
                    record["jacobian_wall_sec"] for record in by_workers[workers]
                )
            ),
            "startup_wall_sec_adjusted": float(
                statistics.median(
                    record["startup_wall_sec_adjusted"]
                    for record in by_workers[workers]
                )
            ),
        }
        for workers in benchmark["worker_counts"]
    }
    serial_median = medians["1"]["jacobian_wall_sec"]
    two_ratio = medians["2"]["jacobian_wall_sec"] / serial_median
    four_ratio = medians["4"]["jacobian_wall_sec"] / serial_median
    call_fraction = float(benchmark["dd146_jacobian_provider_call_fraction"])
    projected = (
        medians["4"]["startup_wall_sec_adjusted"]
        + float(benchmark["dd146_wall_clock_sec"])
        * ((1.0 - call_fraction) + call_fraction * four_ratio)
    )
    matrix_gates = {
        "absolute": all(
            record["max_abs_difference_from_accepted"]
            <= benchmark["matrix_absolute_limit"]
            for record in records
        ),
        "relative_frobenius": all(
            record["relative_frobenius_difference_from_accepted"]
            <= benchmark["matrix_relative_frobenius_limit"]
            for record in records
        ),
        "spectrum": all(
            record["singular_spectrum_relative_difference"]
            <= benchmark["singular_spectrum_relative_limit"]
            for record in records
        ),
    }
    gates = {
        "frozen_schedule": len(records) == 9
        and [record["workers"] for record in records]
        == [workers for row in benchmark["schedule"] for workers in row],
        "color_and_task_count": len(groups) == benchmark["color_count"]
        and len(tasks) == benchmark["tasks_per_matrix"]
        and all(record["task_count"] == len(tasks) for record in records),
        "process_isolation": all(
            len(record["ping_process_ids"]) == record["workers"]
            and len(record["task_process_ids"]) == record["workers"]
            for record in records
        ),
        "provider_calls": all(
            record["provider_calls"] == benchmark["provider_calls_per_matrix"]
            and all(
                value == benchmark["provider_calls_per_task"]
                for value in record["per_task_provider_calls"]
            )
            for record in records
        ),
        "matrix_absolute": matrix_gates["absolute"],
        "matrix_relative_frobenius": matrix_gates["relative_frobenius"],
        "singular_spectrum": matrix_gates["spectrum"],
        "rank_and_condition": all(
            record["rank"] == payload["accepted_matrix_rank"]
            and record["condition"] < benchmark["condition_limit"]
            for record in records
        ),
        "timing_monotonic": medians["4"]["jacobian_wall_sec"]
        < medians["2"]["jacobian_wall_sec"]
        < medians["1"]["jacobian_wall_sec"],
        "meaningful_four_worker_speed": four_ratio
        <= benchmark["four_worker_time_ratio_limit"],
        "projected_dd146_wall": projected
        < benchmark["projected_dd146_wall_limit_sec"],
        "benchmark_wall": elapsed < benchmark["benchmark_wall_limit_sec"],
        "no_solve_or_state_advance": True,
    }
    passed = all(gates.values())
    numerical_integrity = all(
        gates[key]
        for key in (
            "frozen_schedule",
            "color_and_task_count",
            "process_isolation",
            "provider_calls",
            "matrix_absolute",
            "matrix_relative_frobenius",
            "singular_spectrum",
            "rank_and_condition",
        )
    )
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "parallel_dwsim_jacobian_meaningful_speedup"
            if passed
            else (
                "parallel_dwsim_jacobian_valid_but_not_meaningful"
                if numerical_integrity
                else "parallel_dwsim_jacobian_integrity_failed"
            )
        ),
        "decision": (
            "authorize_parallel_colored_jacobian_integration_contract"
            if passed
            else "retain_serial_colored_jacobian_path"
        ),
        "records": records,
        "median_timings": medians,
        "two_worker_time_ratio": float(two_ratio),
        "two_worker_speedup": float(1.0 / two_ratio),
        "four_worker_time_ratio": float(four_ratio),
        "four_worker_speedup": float(1.0 / four_ratio),
        "projected_dd146_wall_sec": float(projected),
        "benchmark_wall_clock_sec": float(elapsed),
        "gates": gates,
        "pass": bool(passed),
        "campaign_executed_once": True,
        "nonlinear_solve_attempted": False,
        "correction_attempted": False,
        "state_acceptance_attempted": False,
        "timestep_attempted": False,
        "trajectory_attempted": False,
        "retry_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-147 Parallel DWSIM Jacobian Benchmark Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Serial median Jacobian: `{serial_median:.6f} s`",
                f"- Two-worker median/speedup: `{medians['2']['jacobian_wall_sec']:.6f} s` / `{result['two_worker_speedup']:.3f}x`",
                f"- Four-worker median/speedup: `{medians['4']['jacobian_wall_sec']:.6f} s` / `{result['four_worker_speedup']:.3f}x`",
                f"- Four-worker time ratio: `{four_ratio:.6f}` (limit `<=0.60`)",
                f"- Projected DD-146 wall: `{projected:.3f} s` (limit `<75 s`)",
                f"- Benchmark wall: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "The benchmark evaluates complete colored-Jacobian perturbation residuals in isolated DWSIM worker processes. It performs no nonlinear solve or state advance.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    output = prepare() if args.prepare else execute()
    print(
        json.dumps(
            {
                key: output[key]
                for key in output
                if key
                in {
                    "schema_id",
                    "classification",
                    "decision",
                    "contract_payload_sha256",
                    "four_worker_speedup",
                    "projected_dd146_wall_sec",
                    "benchmark_wall_clock_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
