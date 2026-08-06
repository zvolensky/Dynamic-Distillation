#!/usr/bin/env python
"""Prepare or execute DD-157 production exact-memoization saved-state proof."""

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
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import probe_core_v3_worker_lifetime_efficiency as dd153
import run_core_v3_parallel_captured_short_trajectory as dd149
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


SCHEMA = "dd157-core-v3-production-exact-memoization-contract-v1"
RESULT_SCHEMA = "dd157-core-v3-production-exact-memoization-result-v1"
DD151_CONTRACT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.json"
)
DD151_RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
DD153_RESULT = Path("logs/dd153_core_v3_worker_lifetime_efficiency_probe_20260806.json")
DD156_RESULT = Path("logs/dd156_core_v3_exact_thermo_memoization_20260806.json")
CONTRACT = Path(
    "logs/dd157_core_v3_production_exact_memoization_contract_20260806.json"
)
RESULT = Path("logs/dd157_core_v3_production_exact_memoization_20260806.json")
CONTRACT_DOC = Path(
    "docs/dd_157_core_v3_production_exact_memoization_contract_20260806.md"
)
RESULT_DOC = Path("docs/dd_157_core_v3_production_exact_memoization_20260806.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/thermo_provider_v1.py",
    "tests/test_core_v3_exact_thermo_memoization_production.py",
    "tools/prove_core_v3_production_exact_memoization.py",
    "tools/run_core_v3_parallel_captured_short_trajectory.py",
)


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


def _work_for_state(
    state: Mapping[str, Any],
    pattern: np.ndarray,
    step: float,
    *,
    memo_epoch: str | None,
):
    tasks, groups = build_colored_central_difference_tasks(
        state["coordinates"],
        pattern=pattern,
        step=float(step),
        state_id=f"dd157:{state['path']}:root_{state['root_index']}",
    )
    work = []
    for task in tasks:
        item = {
            "task": task,
            "previous_inventory_lbmol": state["previous_inventory_lbmol"],
            "previous_top_u_BTU": state["previous_top_u_BTU"],
            "previous_lower_u_BTU": state["previous_lower_u_BTU"],
            "previous_controller_memory": state["previous_controller_memory"],
            "step_seconds": state["step_seconds"],
        }
        if memo_epoch is not None:
            item["thermo_memo_epoch"] = str(memo_epoch)
        work.append(item)
    return tasks, groups, work


def _evaluate_matrix(
    pool: ProcessPoolExecutor,
    state: Mapping[str, Any],
    *,
    pattern: np.ndarray,
    step: float,
    mode: str,
    memo_epoch: str | None,
) -> dict[str, Any]:
    tasks, groups, work = _work_for_state(
        state, pattern, step, memo_epoch=memo_epoch
    )
    started = time.perf_counter()
    raw = list(pool.map(dd149._worker_evaluate, work, chunksize=1))
    wall = time.perf_counter() - started
    matrix = assemble_colored_central_difference_jacobian(
        tasks,
        [
            ColoredCentralDifferenceResult(
                order=int(item["order"]),
                residual=tuple(float(value) for value in item["residual"]),
            )
            for item in raw
        ],
        pattern=pattern,
        step=float(step),
    )
    memo_hits = sum(
        int(item.get("thermo_memo_delta", {}).get("hits", 0)) for item in raw
    )
    memo_misses = sum(
        int(item.get("thermo_memo_delta", {}).get("misses", 0)) for item in raw
    )
    return {
        "mode": str(mode),
        "path": str(state["path"]),
        "root_index": int(state["root_index"]),
        "memo_epoch": memo_epoch,
        "wall_sec": float(wall),
        "color_count": int(len(groups)),
        "task_count": int(len(raw)),
        "logical_provider_calls": int(
            sum(int(item["provider_calls"]) for item in raw)
        ),
        "per_task_provider_calls": [int(item["provider_calls"]) for item in raw],
        "process_ids": sorted({int(item["process_id"]) for item in raw}),
        "memo_hits": int(memo_hits),
        "memo_misses": int(memo_misses),
        "memo_calls": int(memo_hits + memo_misses),
        "memo_hit_fraction": float(
            memo_hits / (memo_hits + memo_misses)
            if memo_hits + memo_misses
            else 0.0
        ),
        "saved_matrix_sha256": str(state["saved_jacobian_sha256"]),
        "matrix_sha256": _matrix_sha(matrix),
        "matrix_max_abs_difference": float(
            np.max(np.abs(matrix - state["saved_jacobian"]))
        ),
    }


def _classify_pairs(
    records: Sequence[Mapping[str, Any]],
    *,
    speedup_minimum: float,
    hit_fraction_minimum: float,
) -> dict[str, Any]:
    pairs = []
    for path in ("coarse", "refined"):
        uncached = next(
            item for item in records if item["path"] == path and item["mode"] == "uncached"
        )
        memoized = next(
            item for item in records if item["path"] == path and item["mode"] == "memoized"
        )
        speedup = float(uncached["wall_sec"] / memoized["wall_sec"])
        pairs.append(
            {
                "path": path,
                "speedup": speedup,
                "hit_fraction": float(memoized["memo_hit_fraction"]),
                "pass": bool(
                    speedup >= speedup_minimum
                    and memoized["memo_hit_fraction"] >= hit_fraction_minimum
                ),
            }
        )
    return {
        "pairs": pairs,
        "all_pairs_pass": bool(all(item["pass"] for item in pairs)),
    }


def prepare() -> dict[str, Any]:
    dd151 = _load(DD151_RESULT)
    dd153_result = _load(DD153_RESULT)
    dd156_result = _load(DD156_RESULT)
    if (
        dd151["pass"]
        or not dd153_result["pass"]
        or not dd156_result["pass"]
        or dd156_result["decision"]
        != "authorize_bounded_production_memoization_and_saved_state_proof"
    ):
        raise RuntimeError("DD-157 requires immutable DD-151/DD-153/DD-156 decisions")
    payload = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD151_CONTRACT, DD151_RESULT, DD153_RESULT, DD156_RESULT)
        },
        "proof": {
            "states": [
                {"path": "coarse", "root_index": 180},
                {"path": "refined", "root_index": 360},
            ],
            "mode_order": ["uncached", "memoized"],
            "worker_count": 4,
            "spawn_context": True,
            "startup_ping_delay_sec": 0.25,
            "expected_pools": 1,
            "expected_matrices": 4,
            "tasks_per_matrix": 42,
            "logical_provider_calls_per_task": 28,
            "expected_logical_provider_calls": 4704,
            "expected_startup_provider_calls": 116,
            "expected_memo_calls_per_matrix": 1176,
            "matrix_absolute_limit": 1.0e-10,
            "fresh_reference_ratio_minimum": 0.65,
            "fresh_reference_ratio_maximum": 1.50,
            "speedup_minimum_each_path": 1.50,
            "hit_fraction_minimum_each_path": 0.60,
            "wall_limit_sec": 60.0,
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "a DD-151/DD-153/DD-156 result, source, or DD-157 implementation hash changes",
            "a state, mode, process, task, exact key, memo epoch, or threshold changes",
            "memoization is enabled without a unique per-Jacobian epoch",
            "any reconstructed matrix differs from DD-151 beyond 1e-10",
            "call, cache, ownership, representativeness, speed, or wall integrity fails",
            "a nonlinear solve, correction, state acceptance, timestep, trajectory, retry, clipping, projection, or fallback occurs",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-157 Frozen Production Exact-Memoization Proof Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- States: DD-151 coarse root `180` and refined root `360`",
                "- Modes: uncached, then production exact memo with a unique per-Jacobian epoch",
                "- Exact work: one four-worker pool, 4 matrices, 168 tasks, 4,704 logical calls",
                "- Matrix reproduction: `<=1e-10` absolute",
                "- Each state: speedup `>=1.50x`, memo hit fraction `>=0.60`",
                "- Wall limit: `<60 s`",
                "",
                "Passing authorizes only a separately frozen short-trajectory integration proof. It does not authorize multi-minute operation.",
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
        raise RuntimeError("DD-157 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-157 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-157 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-157 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    proof = payload["proof"]
    dd151 = _load(DD151_RESULT)
    dd153_result = _load(DD153_RESULT)
    source_contract = _load(DD151_CONTRACT)
    source_contract_path = str((ROOT / DD151_CONTRACT).resolve())
    pattern = np.asarray(
        controlled_terminal_step_pattern(dd149.dd128._contract(source_contract)),
        dtype=bool,
    )
    step = float(source_contract["jacobian_step"])
    states = {
        item["path"]: dd153._saved_state(
            dd151, item["path"], int(item["root_index"])
        )
        for item in proof["states"]
    }
    fresh_references = {
        item["path"]: float(item["fresh_median_wall_sec"])
        for item in dd153_result["checkpoints"]
        if any(
            state["path"] == item["path"]
            and int(state["root_index"]) == int(item["root_index"])
            for state in proof["states"]
        )
    }

    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(proof["worker_count"]),
        mp_context=mp.get_context("spawn"),
        initializer=dd149._worker_initialize,
        initargs=(source_contract_path,),
    ) as pool:
        pings = [
            pool.submit(dd149._worker_ping, float(proof["startup_ping_delay_sec"]))
            for _ in range(int(proof["worker_count"]))
        ]
        startup = [future.result() for future in pings]
        startup_wall = time.perf_counter() - pool_started
        for mode in proof["mode_order"]:
            for path, state in states.items():
                records.append(
                    _evaluate_matrix(
                        pool,
                        state,
                        pattern=pattern,
                        step=step,
                        mode=mode,
                        memo_epoch=(f"dd157:{path}:{state['root_index']}" if mode == "memoized" else None),
                    )
                )
    pool_lifetime = time.perf_counter() - pool_started
    elapsed = time.perf_counter() - started

    diagnosis = _classify_pairs(
        records,
        speedup_minimum=float(proof["speedup_minimum_each_path"]),
        hit_fraction_minimum=float(proof["hit_fraction_minimum_each_path"]),
    )
    logical_calls = sum(int(item["logical_provider_calls"]) for item in records)
    worker_ids = sorted({pid for item in records for pid in item["process_ids"]})
    fresh_ratios = {
        path: float(
            next(item["wall_sec"] for item in records if item["path"] == path and item["mode"] == "uncached")
            / fresh_references[path]
        )
        for path in states
    }
    gates = {
        "source_integrity": bool(
            not dd151["pass"] and dd153_result["pass"] and _load(DD156_RESULT)["pass"]
        ),
        "single_pool": proof["expected_pools"] == 1,
        "exact_matrix_task_and_logical_calls": len(records) == proof["expected_matrices"]
        and sum(int(item["task_count"]) for item in records)
        == proof["expected_matrices"] * proof["tasks_per_matrix"]
        and logical_calls == proof["expected_logical_provider_calls"]
        and all(
            value == proof["logical_provider_calls_per_task"]
            for item in records
            for value in item["per_task_provider_calls"]
        ),
        "memo_accounting": all(
            item["memo_calls"] == proof["expected_memo_calls_per_matrix"]
            for item in records
            if item["mode"] == "memoized"
        )
        and all(item["memo_calls"] == 0 for item in records if item["mode"] == "uncached"),
        "startup_calls": sum(int(item["provider_calls"]) for item in startup)
        == proof["expected_startup_provider_calls"],
        "worker_ownership": len(worker_ids) == proof["worker_count"]
        and all(len(item["process_ids"]) == proof["worker_count"] for item in records),
        "matrix_reproduction": max(
            float(item["matrix_max_abs_difference"]) for item in records
        )
        <= proof["matrix_absolute_limit"],
        "fresh_baseline_representative": all(
            proof["fresh_reference_ratio_minimum"]
            <= ratio
            <= proof["fresh_reference_ratio_maximum"]
            for ratio in fresh_ratios.values()
        ),
        "memoization_effective_each_path": bool(diagnosis["all_pairs_pass"]),
        "wall": elapsed < proof["wall_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "production_exact_memoization_proved"
            if passed
            else "production_exact_memoization_proof_failed"
        ),
        "decision": (
            "authorize_separately_frozen_short_trajectory_memoization_proof"
            if passed
            else "disable_production_exact_memoization"
        ),
        "fresh_references_wall_sec": fresh_references,
        "fresh_baseline_ratios": fresh_ratios,
        "startup_wall_sec": float(startup_wall),
        "pool_lifetime_sec": float(pool_lifetime),
        "analysis_wall_sec": float(elapsed),
        "records": records,
        "diagnosis": diagnosis,
        "worker_process_ids": worker_ids,
        "logical_provider_calls": int(logical_calls),
        "state_advanced": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "retry_attempted": False,
        "gates": gates,
        "pass": bool(passed),
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-157 Production Exact-Memoization Proof Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Records: `{records}`",
                f"- Diagnosis: `{diagnosis}`",
                f"- Gates: `{gates}`",
                f"- Wall: `{elapsed:.3f} s`",
                "",
                "No solve, state acceptance, or trajectory occurred. Each memoized matrix used a unique epoch that cleared worker-local exact caches lazily before its first task.",
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
                    "analysis_wall_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
