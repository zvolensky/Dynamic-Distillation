#!/usr/bin/env python
"""Prepare or execute DD-181's seven-volume parallel-Jacobian benchmark."""

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

import run_core_v3_seven_volume_physical_longer_trajectory as dd180  # noqa: E402
import run_core_v3_seven_volume_physical_modest_trajectory as dd178  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    contract_sparsity_pattern,
)
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    component_rate_scales,
    evaluate_backward_euler_residual,
    governing_storage_vector,
    zero_rate_evaluation,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    ColoredCentralDifferenceTask,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)


SCHEMA = "dd181-core-v3-seven-volume-parallel-jacobian-benchmark-contract-v1"
RESULT_SCHEMA = "dd181-core-v3-seven-volume-parallel-jacobian-benchmark-result-v1"
DD180_CONTRACT = Path(
    "logs/dd180_core_v3_seven_volume_physical_longer_trajectory_contract_20260812.json"
)
DD180_RESULT = Path(
    "logs/dd180_core_v3_seven_volume_physical_longer_trajectory_20260812.json"
)
CONTRACT = Path(
    "logs/dd181_core_v3_seven_volume_parallel_jacobian_benchmark_contract_20260812.json"
)
RESULT = Path(
    "logs/dd181_core_v3_seven_volume_parallel_jacobian_benchmark_20260812.json"
)
CONTRACT_DOC = Path(
    "docs/dd_181_core_v3_seven_volume_parallel_jacobian_benchmark_contract_20260812.md"
)
RESULT_DOC = Path(
    "docs/dd_181_core_v3_seven_volume_parallel_jacobian_benchmark_20260812.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "tools/benchmark_core_v3_seven_volume_parallel_jacobian.py",
    "tests/test_core_v3_seven_volume_parallel_jacobian_benchmark.py",
)


_WORKER_OBJECTIVE = None
_WORKER_AUDIT = None
_WORKER_PROVIDER = None


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


def dd180_runtime_accounting(result: Mapping[str, Any]) -> dict[str, float | int]:
    coarse = list(result["coarse"]["steps"])
    refined = list(result["refined"]["steps"])
    coarse_wall = float(sum(float(step["wall_clock_sec"]) for step in coarse))
    refined_wall = float(sum(float(step["wall_clock_sec"]) for step in refined))
    campaign_wall = float(result["wall_clock_sec"])
    simulated_seconds = float(result["paths"]["duration_seconds"])
    provider_counts = result["provider"]["counts"]
    jacobian_calls = sum(
        int(row["count"])
        for row in provider_counts
        if row["evaluation_kind"] == "jacobian"
    )
    logical_calls = int(result["provider"]["total_calls"])
    return {
        "campaign_wall_sec": campaign_wall,
        "coarse_step_wall_sec": coarse_wall,
        "refined_step_wall_sec": refined_wall,
        "non_step_overhead_sec": campaign_wall - coarse_wall - refined_wall,
        "coarse_steps": len(coarse),
        "refined_steps": len(refined),
        "coarse_mean_step_wall_sec": coarse_wall / len(coarse),
        "refined_mean_step_wall_sec": refined_wall / len(refined),
        "production_wall_per_simulated_second": coarse_wall / simulated_seconds,
        "production_simulated_to_wall_ratio": simulated_seconds / coarse_wall,
        "logical_provider_calls": logical_calls,
        "jacobian_logical_provider_calls": jacobian_calls,
        "jacobian_logical_call_fraction": jacobian_calls / logical_calls,
        "memo_hits": int(result["exact_state_memoization"]["hits"]),
        "memo_misses": int(result["exact_state_memoization"]["misses"]),
    }


def _context(payload: Mapping[str, Any]):
    spec = dd178.dd177.dd175.dd173.dd172.dd171.dd168._spec(
        payload["disturbed_source_mapping"],
        float(payload["disturbed_operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd178.dd177.dd175.dd173.dd172.dd171.dd168._reference(
        payload["reference"]
    )
    state = dd178.dd177.dd175.dd173.dd172.dd171._state(
        payload["accepted_root_state"]
    )
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=payload["accepted_root_artifact"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-181 seven-volume contract changed")
    provider = dd178.dd177.dd175.dd173.dd172.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    baseline = zero_rate_evaluation(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        inventory_lbmol=inventory,
        algebraic_coordinates=algebraic,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        state_id=f"dd181:worker_{os.getpid()}:scale_basis",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(contract, baseline)
    previous_storage = governing_storage_vector(spec, baseline, inventory)
    point = np.concatenate(
        (np.zeros(len(contract.derivative_variables), dtype=float), algebraic)
    )
    step_seconds = float(payload["benchmark"]["step_seconds"])

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_backward_euler_residual(
            contract,
            spec,
            reference,
            state,
            provider,
            audit,
            previous_inventory_lbmol=inventory,
            previous_internal_energy_BTU=previous_storage,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=candidate,
            step_seconds=step_seconds,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        ).scaled

    pattern, _names = contract_sparsity_pattern(
        contract, include_state_rate_dependencies=True
    )
    objective(point, f"dd181:worker_{os.getpid()}:warmup_residual")
    return point, pattern, objective, audit, provider


def _worker_initialize(contract_path: str) -> None:
    global _WORKER_OBJECTIVE, _WORKER_AUDIT, _WORKER_PROVIDER
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    _point, _pattern, objective, audit, provider = _context(payload)
    _WORKER_OBJECTIVE = objective
    _WORKER_AUDIT = audit
    _WORKER_PROVIDER = provider


def _worker_ping(delay_seconds: float) -> int:
    if _WORKER_OBJECTIVE is None:
        raise RuntimeError("DD-181 worker was not initialized")
    time.sleep(float(delay_seconds))
    return int(os.getpid())


def _worker_evaluate(task: ColoredCentralDifferenceTask) -> dict[str, Any]:
    if _WORKER_OBJECTIVE is None or _WORKER_AUDIT is None or _WORKER_PROVIDER is None:
        raise RuntimeError("DD-181 worker was not initialized")
    before_records = len(_WORKER_AUDIT.records)
    before_memo = _WORKER_PROVIDER.get_exact_state_memoization_stats()
    started = time.perf_counter()
    residual = np.asarray(
        _WORKER_OBJECTIVE(np.asarray(task.coordinates), task.state_id), dtype=float
    ).reshape((-1,))
    elapsed = time.perf_counter() - started
    after_memo = _WORKER_PROVIDER.get_exact_state_memoization_stats()
    return {
        "order": int(task.order),
        "residual": residual.tolist(),
        "process_id": int(os.getpid()),
        "logical_provider_calls": int(len(_WORKER_AUDIT.records) - before_records),
        "memo_hits": int(after_memo["hits"] - before_memo["hits"]),
        "memo_misses": int(after_memo["misses"] - before_memo["misses"]),
        "wall_clock_sec": float(elapsed),
    }


def prepare() -> dict[str, Any]:
    source = _load(DD180_CONTRACT)
    result = _load(DD180_RESULT)
    if result.get("pass_gate") is not True or result.get("completed_roots") != 360:
        raise RuntimeError("DD-181 requires the accepted complete DD-180 result")
    accounting = dd180_runtime_accounting(result)

    spec = dd178.dd177.dd175.dd173.dd172.dd171.dd168._spec(
        source["disturbed_source_mapping"],
        float(source["disturbed_operating_spec"]["feed_enthalpy_BTUph"]),
    )
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=source["accepted_root_artifact"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    pattern, _names = contract_sparsity_pattern(
        contract, include_state_rate_dependencies=True
    )
    zero_point = np.zeros(pattern.shape[1], dtype=float)
    tasks, groups = build_colored_central_difference_tasks(
        zero_point,
        pattern=pattern,
        step=float(source["solver"]["jacobian_step"]),
        state_id="dd181:structural",
    )
    payload = {
        key: value
        for key, value in source.items()
        if key not in {
            "schema_id",
            "preparation_base_commit",
            "dd178_contract_path",
            "dd178_contract_sha256",
            "dd179_result_path",
            "dd179_result_sha256",
            "accuracy_policy_document",
            "accuracy_policy_document_sha256",
            "implementation_sha256",
            "hard_stops",
            "contract_payload_sha256",
            "property_evaluation_attempted",
            "nonlinear_solve_attempted",
            "timestep_attempted",
            "controller_attempted",
            "trajectory_attempted",
            "campaign_executed",
        }
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(DD180_CONTRACT).replace("\\", "/"): _sha(ROOT / DD180_CONTRACT),
                str(DD180_RESULT).replace("\\", "/"): _sha(ROOT / DD180_RESULT),
            },
            "dd180_runtime_accounting": accounting,
            "benchmark": {
                "state": "DD-180 first coarse-step initial point",
                "step_seconds": float(source["paths"]["coarse_step_seconds"]),
                "jacobian_step": float(source["solver"]["jacobian_step"]),
                "matrix_shape": list(pattern.shape),
                "color_count": len(groups),
                "tasks_per_matrix": len(tasks),
                "worker_counts": [1, 2, 4],
                "schedule": [[1, 2, 4], [4, 2, 1], [2, 1, 4]],
                "repeats_per_worker_count": 3,
                "fresh_pool_per_repeat": True,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.15,
                "matrix_absolute_limit": 1.0e-10,
                "matrix_relative_frobenius_limit": 1.0e-10,
                "singular_spectrum_relative_limit": 1.0e-8,
                "condition_limit": 1.0e8,
                "four_worker_time_ratio_limit": 0.75,
                "projected_production_wall_limit_sec": 105.0,
                "benchmark_wall_limit_sec": 300.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-180 source or DD-181 implementation hash changes",
                "a worker shares mutable DWSIM state with another process",
                "the frozen nine-run schedule is changed or retried",
                "a matrix, rank, spectrum, or condition integrity gate fails",
                "four workers do not provide the frozen meaningful speedup",
                "a nonlinear solve, state advance, controller, or trajectory occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "controller_attempted": False,
            "trajectory_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-181 Seven-Volume Parallel Jacobian Benchmark Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- State: DD-180 first coarse-step initial point",
                f"- Matrix: `{pattern.shape[0]} x {pattern.shape[1]}`, `{len(groups)}` colors, `{len(tasks)}` residual tasks",
                "- Workers: `1`, `2`, and `4`; three fresh spawned pools each",
                "- Numerical gate: matrix, rank, singular spectrum, and condition equivalence",
                "- Performance gate: four-worker median `<=75%` of one-worker median",
                "- Solve, state advance, controller, and trajectory: prohibited",
                "",
                f"DD-180 production-equivalent path: `{accounting['coarse_step_wall_sec']:.3f} s` wall for `30 s` simulated.",
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
        raise RuntimeError("DD-181 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-181 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-181 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-181 result exists; rerun is prohibited")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    point, pattern, _objective, _audit, provider = _context(payload)
    provider.set_exact_state_memoization(False, clear=True)
    benchmark = payload["benchmark"]
    tasks, groups = build_colored_central_difference_tasks(
        point,
        pattern=pattern,
        step=float(benchmark["jacobian_step"]),
        state_id="dd181:first_coarse_root:jacobian",
    )
    context = mp.get_context("spawn")
    contract_path = str((ROOT / CONTRACT).resolve())
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    for round_index, worker_row in enumerate(benchmark["schedule"]):
        for workers in worker_row:
            pool_started = time.perf_counter()
            with ProcessPoolExecutor(
                max_workers=int(workers),
                mp_context=context,
                initializer=_worker_initialize,
                initargs=(contract_path,),
            ) as pool:
                pings = [
                    pool.submit(_worker_ping, benchmark["startup_ping_delay_sec"])
                    for _ in range(int(workers))
                ]
                ping_pids = sorted({int(future.result()) for future in pings})
                startup_raw = time.perf_counter() - pool_started
                startup_adjusted = max(
                    startup_raw - float(benchmark["startup_ping_delay_sec"]), 0.0
                )
                matrix_started = time.perf_counter()
                raw = list(pool.map(_worker_evaluate, tasks, chunksize=1))
                matrix_wall = time.perf_counter() - matrix_started
            pool_wall = time.perf_counter() - pool_started
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
            records.append(
                {
                    "round": int(round_index + 1),
                    "workers": int(workers),
                    "ping_process_ids": ping_pids,
                    "task_process_ids": sorted({int(item["process_id"]) for item in raw}),
                    "startup_wall_sec_raw": float(startup_raw),
                    "startup_wall_sec_adjusted": float(startup_adjusted),
                    "jacobian_wall_sec": float(matrix_wall),
                    "pool_lifetime_sec": float(pool_wall),
                    "task_count": len(raw),
                    "logical_provider_calls": int(sum(item["logical_provider_calls"] for item in raw)),
                    "memo_hits": int(sum(item["memo_hits"] for item in raw)),
                    "memo_misses": int(sum(item["memo_misses"] for item in raw)),
                    "task_wall_sec_sum": float(sum(item["wall_clock_sec"] for item in raw)),
                    "matrix": matrix.tolist(),
                    "matrix_sha256": _matrix_sha(matrix),
                    "rank": int(np.linalg.matrix_rank(matrix)),
                    "condition": float(singular[0] / singular[-1]),
                    "singular_spectrum": singular.tolist(),
                }
            )
    elapsed = time.perf_counter() - started

    baseline = next(record for record in records if record["workers"] == 1)
    baseline_matrix = np.asarray(baseline["matrix"], dtype=float)
    baseline_singular = np.asarray(baseline["singular_spectrum"], dtype=float)
    for record in records:
        matrix = np.asarray(record["matrix"], dtype=float)
        singular = np.asarray(record["singular_spectrum"], dtype=float)
        delta = matrix - baseline_matrix
        record["max_abs_difference_from_serial"] = float(np.max(np.abs(delta)))
        record["relative_frobenius_difference_from_serial"] = float(
            np.linalg.norm(delta)
            / max(float(np.linalg.norm(baseline_matrix)), np.finfo(float).tiny)
        )
        record["singular_spectrum_relative_difference"] = float(
            np.max(
                np.abs(singular - baseline_singular)
                / np.maximum(np.abs(baseline_singular), np.finfo(float).tiny)
            )
        )

    by_workers = {
        int(workers): [r for r in records if r["workers"] == int(workers)]
        for workers in benchmark["worker_counts"]
    }
    medians = {
        str(workers): {
            "jacobian_wall_sec": float(statistics.median(r["jacobian_wall_sec"] for r in rows)),
            "startup_wall_sec_adjusted": float(statistics.median(r["startup_wall_sec_adjusted"] for r in rows)),
            "memo_misses": float(statistics.median(r["memo_misses"] for r in rows)),
        }
        for workers, rows in by_workers.items()
    }
    serial_median = medians["1"]["jacobian_wall_sec"]
    four_ratio = medians["4"]["jacobian_wall_sec"] / serial_median
    accounting = payload["dd180_runtime_accounting"]
    jacobian_fraction = float(accounting["jacobian_logical_call_fraction"])
    projected_wall = float(accounting["coarse_step_wall_sec"]) * (
        1.0 - jacobian_fraction + jacobian_fraction * four_ratio
    )
    gates = {
        "frozen_schedule": [r["workers"] for r in records]
        == [workers for row in benchmark["schedule"] for workers in row],
        "color_and_task_count": len(groups) == benchmark["color_count"]
        and len(tasks) == benchmark["tasks_per_matrix"]
        and all(r["task_count"] == len(tasks) for r in records),
        "process_isolation": all(
            len(r["ping_process_ids"]) == r["workers"]
            and len(r["task_process_ids"]) == r["workers"]
            for r in records
        ),
        "matrix_absolute": all(
            r["max_abs_difference_from_serial"] <= benchmark["matrix_absolute_limit"]
            for r in records
        ),
        "matrix_relative": all(
            r["relative_frobenius_difference_from_serial"]
            <= benchmark["matrix_relative_frobenius_limit"]
            for r in records
        ),
        "spectrum": all(
            r["singular_spectrum_relative_difference"]
            <= benchmark["singular_spectrum_relative_limit"]
            for r in records
        ),
        "rank_and_condition": all(
            r["rank"] == 54 and r["condition"] < benchmark["condition_limit"]
            for r in records
        ),
        "meaningful_four_worker_speed": four_ratio
        <= benchmark["four_worker_time_ratio_limit"],
        "projected_production_wall": projected_wall
        < benchmark["projected_production_wall_limit_sec"],
        "benchmark_wall": elapsed < benchmark["benchmark_wall_limit_sec"],
        "no_solve_or_state_advance": True,
    }
    passed = all(gates.values())
    integrity = all(
        gates[key]
        for key in (
            "frozen_schedule",
            "color_and_task_count",
            "process_isolation",
            "matrix_absolute",
            "matrix_relative",
            "spectrum",
            "rank_and_condition",
        )
    )
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "seven_volume_parallel_jacobian_meaningful_speedup"
            if passed
            else (
                "seven_volume_parallel_jacobian_valid_but_not_meaningful"
                if integrity
                else "seven_volume_parallel_jacobian_integrity_failed"
            )
        ),
        "decision": (
            "authorize_persistent_parallel_step_solver_design"
            if passed
            else "retain_serial_step_solver_and_profile_other_costs"
        ),
        "dd180_runtime_accounting": accounting,
        "records": records,
        "median_timings": medians,
        "two_worker_speedup": float(serial_median / medians["2"]["jacobian_wall_sec"]),
        "four_worker_speedup": float(1.0 / four_ratio),
        "four_worker_time_ratio": float(four_ratio),
        "projected_production_wall_sec_for_30_simulated_sec": float(projected_wall),
        "benchmark_wall_clock_sec": float(elapsed),
        "gates": gates,
        "pass_gate": bool(passed),
        "campaign_executed_once": True,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "controller_attempted": False,
        "trajectory_attempted": False,
        "retry_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-181 Seven-Volume Parallel Jacobian Benchmark Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- One-worker median Jacobian: `{serial_median:.6f} s`",
                f"- Two-worker speedup: `{result['two_worker_speedup']:.3f}x`",
                f"- Four-worker speedup: `{result['four_worker_speedup']:.3f}x`",
                f"- Projected production path: `{projected_wall:.3f} s` wall per `30 s` simulated",
                f"- Benchmark wall: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "The benchmark evaluated complete seven-volume colored-Jacobian perturbations in isolated DWSIM processes. It performed no nonlinear solve or state advance.",
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
                if key in {
                    "schema_id",
                    "classification",
                    "decision",
                    "contract_payload_sha256",
                    "two_worker_speedup",
                    "four_worker_speedup",
                    "projected_production_wall_sec_for_30_simulated_sec",
                    "benchmark_wall_clock_sec",
                    "pass_gate",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass_gate"] else 2)
