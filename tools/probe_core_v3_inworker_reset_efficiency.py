#!/usr/bin/env python
"""Prepare or execute DD-155 in-worker thermo reset efficiency probe."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import gc
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_terminal_gauge_invariance as dd121
import probe_core_v3_worker_lifetime_efficiency as dd153
import run_core_v3_parallel_captured_short_trajectory as dd149
from dynamic_distillation import pr_flash_backend_v1 as dwsim_backend
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    evaluate_controlled_terminal_zero_time,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


SCHEMA = "dd155-core-v3-inworker-reset-efficiency-contract-v1"
RESULT_SCHEMA = "dd155-core-v3-inworker-reset-efficiency-result-v1"
DD151_CONTRACT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.json"
)
DD151_RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
DD153_RESULT = Path("logs/dd153_core_v3_worker_lifetime_efficiency_probe_20260806.json")
DD154_RESULT = Path("logs/dd154_core_v3_pool_renewal_cadence_20260806.json")
CONTRACT = Path("logs/dd155_core_v3_inworker_reset_efficiency_contract_20260806.json")
RESULT = Path("logs/dd155_core_v3_inworker_reset_efficiency_20260806.json")
CONTRACT_DOC = Path(
    "docs/dd_155_core_v3_inworker_reset_efficiency_contract_20260806.md"
)
RESULT_DOC = Path("docs/dd_155_core_v3_inworker_reset_efficiency_20260806.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/pr_flash_backend_v1.py",
    "src/dynamic_distillation/thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "tests/test_core_v3_inworker_reset_efficiency.py",
    "tools/probe_core_v3_inworker_reset_efficiency.py",
    "tools/run_core_v3_parallel_captured_short_trajectory.py",
)


_SOURCE_CONTRACT_PATH: str | None = None


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
    global _SOURCE_CONTRACT_PATH
    _SOURCE_CONTRACT_PATH = str(contract_path)
    dd149._worker_initialize(str(contract_path))


def _clear_python_provider_caches(provider: Any) -> dict[str, int]:
    before = {
        "rhoL": len(getattr(provider, "_rhoL_cache", {})),
        "cp": len(getattr(provider, "_cp_cache", {})),
        "mw": int(getattr(provider, "_mw_components_cache", None) is not None),
    }
    provider._rhoL_cache.clear()
    provider._cp_cache.clear()
    provider._mw_components_cache = None
    return before


def _force_backend_reinitialize_for_diagnostic() -> None:
    dwsim_backend._dwsim_initialized = False
    dwsim_backend._dtlc = None
    dwsim_backend._prop_package = None
    dwsim_backend._carray = None
    gc.collect()


def _replace_worker_provider(*, reset_backend: bool) -> int:
    if _SOURCE_CONTRACT_PATH is None or dd149._WORKER_CONTEXT is None:
        raise RuntimeError("DD-155 worker context was not initialized")
    if reset_backend:
        _force_backend_reinitialize_for_diagnostic()
    payload = json.loads(Path(_SOURCE_CONTRACT_PATH).read_text(encoding="utf-8"))
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = (
        dd121._context(payload)
    )
    contract = dd149._WORKER_CONTEXT["contract"]
    evaluate_controlled_terminal_zero_time(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=np.asarray(payload["inventory_lbmol"], dtype=float),
        lower_internal_energy_BTU=np.asarray(
            payload["lower_internal_energy_BTU"], dtype=float
        ),
        controller_memory=np.asarray(payload["controller_memory"], dtype=float),
        level_setpoints=TerminalLevelSetpoints(**payload["original_level_setpoints"]),
        solve_coordinates=np.asarray(payload["zero_time_coordinates"], dtype=float),
        state_id=f"dd155:worker_{os.getpid()}:reset_warmup",
        evaluation_kind="residual",
        **common,
    )
    dd149._WORKER_CONTEXT["provider"] = provider
    dd149._WORKER_CONTEXT["call_audit"] = call_audit
    return int(len(call_audit.records))


def _worker_reset(payload: Mapping[str, Any]) -> dict[str, Any]:
    if dd149._WORKER_CONTEXT is None:
        raise RuntimeError("DD-155 worker context was not initialized")
    time.sleep(float(payload["occupancy_delay_sec"]))
    mode = str(payload["mode"])
    started = time.perf_counter()
    provider_calls = 0
    cache_sizes: dict[str, int] = {}
    if mode == "python_cache_reset":
        cache_sizes = _clear_python_provider_caches(dd149._WORKER_CONTEXT["provider"])
    elif mode == "provider_rebuild":
        provider_calls = _replace_worker_provider(reset_backend=False)
    elif mode == "backend_reinitialize":
        provider_calls = _replace_worker_provider(reset_backend=True)
    else:
        raise ValueError(f"unsupported DD-155 reset mode: {mode}")
    return {
        "mode": mode,
        "process_id": int(os.getpid()),
        "wall_sec": float(time.perf_counter() - started),
        "provider_calls": int(provider_calls),
        "cleared_cache_sizes": cache_sizes,
    }


def _work_for_state(state: Mapping[str, Any], pattern: np.ndarray, step: float):
    tasks, groups = build_colored_central_difference_tasks(
        state["coordinates"],
        pattern=pattern,
        step=float(step),
        state_id=f"dd155:{state['path']}:root_{state['root_index']}",
    )
    work = [
        {
            "task": task,
            "previous_inventory_lbmol": state["previous_inventory_lbmol"],
            "previous_top_u_BTU": state["previous_top_u_BTU"],
            "previous_lower_u_BTU": state["previous_lower_u_BTU"],
            "previous_controller_memory": state["previous_controller_memory"],
            "step_seconds": state["step_seconds"],
        }
        for task in tasks
    ]
    return tasks, groups, work


def _evaluate_matrix(
    pool: ProcessPoolExecutor,
    state: Mapping[str, Any],
    *,
    pattern: np.ndarray,
    step: float,
    stage: str,
    repeat: int,
) -> dict[str, Any]:
    tasks, groups, work = _work_for_state(state, pattern, step)
    started = time.perf_counter()
    raw = list(pool.map(dd149._worker_evaluate, work, chunksize=1))
    wall = time.perf_counter() - started
    matrix = assemble_colored_central_difference_jacobian(
        tasks,
        [
            ColoredCentralDifferenceResult(
                order=int(value["order"]),
                residual=tuple(float(x) for x in value["residual"]),
            )
            for value in raw
        ],
        pattern=pattern,
        step=float(step),
    )
    return {
        "stage": str(stage),
        "repeat": int(repeat),
        "root_index": int(state["root_index"]),
        "wall_sec": float(wall),
        "color_count": int(len(groups)),
        "task_count": int(len(raw)),
        "provider_calls": int(sum(int(value["provider_calls"]) for value in raw)),
        "per_task_provider_calls": [int(value["provider_calls"]) for value in raw],
        "process_ids": sorted({int(value["process_id"]) for value in raw}),
        "saved_matrix_sha256": str(state["saved_jacobian_sha256"]),
        "matrix_sha256": _matrix_sha(matrix),
        "matrix_max_abs_difference": float(
            np.max(np.abs(matrix - state["saved_jacobian"]))
        ),
    }


def _stage_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("DD-155 stage requires at least one matrix")
    walls = [float(item["wall_sec"]) for item in records]
    return {
        "matrix_count": len(records),
        "wall_sec": walls,
        "median_wall_sec": float(statistics.median(walls)),
        "maximum_matrix_difference": float(
            max(float(item["matrix_max_abs_difference"]) for item in records)
        ),
    }


def _classify_reset(
    stage_medians: Mapping[str, float],
    *,
    fresh_reference_sec: float,
    aged_ratio_minimum: float,
    recovered_to_fresh_ratio_maximum: float,
    speedup_minimum: float,
) -> dict[str, Any]:
    aged = float(stage_medians["no_reset"])
    aged_ratio = aged / float(fresh_reference_sec)
    modes = ("python_cache_reset", "provider_rebuild", "backend_reinitialize")
    diagnostics = {
        mode: {
            "to_fresh_ratio": float(stage_medians[mode] / fresh_reference_sec),
            "speedup_vs_aged": float(aged / stage_medians[mode]),
        }
        for mode in modes
    }
    recovered = [
        mode
        for mode in modes
        if diagnostics[mode]["to_fresh_ratio"] <= recovered_to_fresh_ratio_maximum
        and diagnostics[mode]["speedup_vs_aged"] >= speedup_minimum
    ]
    return {
        "aging_reproduced": bool(aged_ratio >= aged_ratio_minimum),
        "aged_to_fresh_ratio": float(aged_ratio),
        "interventions": diagnostics,
        "first_recovering_intervention": recovered[0] if recovered else None,
        "recovery_observed": bool(recovered),
    }


def prepare() -> dict[str, Any]:
    dd151 = _load(DD151_RESULT)
    dd153_result = _load(DD153_RESULT)
    dd154_result = _load(DD154_RESULT)
    if (
        dd151["pass"]
        or not dd153_result["pass"]
        or dd154_result["pass"]
        or dd154_result["decision"]
        != "retain_persistent_pool_without_trajectory_extension"
    ):
        raise RuntimeError("DD-155 requires immutable DD-151/DD-153/DD-154 decisions")
    payload = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD151_CONTRACT, DD151_RESULT, DD153_RESULT, DD154_RESULT)
        },
        "probe": {
            "path": "coarse",
            "aging_root_start": 2,
            "aging_root_end": 180,
            "probe_root": 180,
            "stage_order": [
                "no_reset",
                "python_cache_reset",
                "provider_rebuild",
                "backend_reinitialize",
            ],
            "stage_repeats": 2,
            "worker_count": 4,
            "spawn_context": True,
            "startup_ping_delay_sec": 0.25,
            "reset_occupancy_delay_sec": 0.25,
            "expected_pools": 1,
            "expected_aging_matrices": 179,
            "expected_probe_matrices": 8,
            "tasks_per_matrix": 42,
            "provider_calls_per_task": 28,
            "expected_worker_evaluation_calls": 219912,
            "expected_reset_provider_calls": 232,
            "expected_startup_provider_calls": 116,
            "matrix_absolute_limit": 1.0e-10,
            "aged_to_fresh_ratio_minimum": 1.20,
            "recovered_to_fresh_ratio_maximum": 1.15,
            "speedup_vs_aged_minimum": 1.20,
            "wall_limit_sec": 180.0,
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "a DD-151/DD-153/DD-154 result, source, or DD-155 implementation hash changes",
            "the single pool, saved coarse root sequence 2..180, stage order, or repeat count changes",
            "a reset task is omitted, retried, or does not execute exactly once in each of four workers",
            "any reconstructed Jacobian differs from DD-151 beyond 1e-10",
            "task, provider-call, process-ownership, aging, recovery, or wall integrity fails",
            "the diagnostic backend reset is represented as a production implementation",
            "a nonlinear solve, correction, state acceptance, timestep, trajectory, clipping, projection, retry, or fallback occurs",
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
                "# DD-155 Frozen In-Worker Thermo Reset Efficiency Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Aging workload: one persistent four-worker pool, saved DD-151 coarse roots `2..180`",
                "- Probe: root `180`, two matrices per stage",
                "- Stages: no reset, Python cache clear, provider reconstruction, DWSIM backend reinitialization",
                "- Exact work: 187 matrices, 7,854 tasks, 219,912 worker-evaluation calls, 232 reset calls",
                "- Matrix reproduction: `<=1e-10` absolute",
                "- Aging gate: no-reset/fresh `>=1.20`",
                "- Recovery gate: reset/fresh `<=1.15` and no-reset/reset speedup `>=1.20`",
                "- Wall limit: `<180 s`",
                "",
                "The DWSIM reset directly clears process-local backend objects for diagnosis only. Passing may authorize a separately implemented and frozen reset API plus saved-state equivalence proof. No trajectory is authorized.",
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
        raise RuntimeError("DD-155 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-155 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-155 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-155 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    probe = payload["probe"]
    dd151 = _load(DD151_RESULT)
    dd153_result = _load(DD153_RESULT)
    source_contract_path = str((ROOT / DD151_CONTRACT).resolve())
    source_contract = _load(DD151_CONTRACT)
    pattern = np.asarray(
        controlled_terminal_step_pattern(dd149.dd128._contract(source_contract)),
        dtype=bool,
    )
    step = float(source_contract["jacobian_step"])
    aging_states = [
        dd153._saved_state(dd151, probe["path"], root_index)
        for root_index in range(
            int(probe["aging_root_start"]), int(probe["aging_root_end"]) + 1
        )
    ]
    probe_state = dd153._saved_state(dd151, probe["path"], probe["probe_root"])
    fresh_reference = next(
        float(item["fresh_median_wall_sec"])
        for item in dd153_result["checkpoints"]
        if item["path"] == probe["path"]
        and int(item["root_index"]) == int(probe["probe_root"])
    )

    context = mp.get_context("spawn")
    aging_records: list[dict[str, Any]] = []
    stage_records: dict[str, list[dict[str, Any]]] = {
        stage: [] for stage in probe["stage_order"]
    }
    reset_records: dict[str, list[dict[str, Any]]] = {}
    started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(probe["worker_count"]),
        mp_context=context,
        initializer=_worker_initialize,
        initargs=(source_contract_path,),
    ) as pool:
        pings = [
            pool.submit(dd149._worker_ping, float(probe["startup_ping_delay_sec"]))
            for _ in range(int(probe["worker_count"]))
        ]
        startup = [future.result() for future in pings]
        startup_wall = time.perf_counter() - pool_started
        for state in aging_states:
            aging_records.append(
                _evaluate_matrix(
                    pool,
                    state,
                    pattern=pattern,
                    step=step,
                    stage="aging",
                    repeat=int(state["root_index"]),
                )
            )
        for stage in probe["stage_order"]:
            if stage != "no_reset":
                group_started = time.perf_counter()
                futures = [
                    pool.submit(
                        _worker_reset,
                        {
                            "mode": stage,
                            "occupancy_delay_sec": probe["reset_occupancy_delay_sec"],
                        },
                    )
                    for _ in range(int(probe["worker_count"]))
                ]
                records = [future.result() for future in futures]
                reset_records[stage] = records
                for record in records:
                    record["group_wall_sec"] = float(
                        time.perf_counter() - group_started
                    )
            for repeat in range(1, int(probe["stage_repeats"]) + 1):
                stage_records[stage].append(
                    _evaluate_matrix(
                        pool,
                        probe_state,
                        pattern=pattern,
                        step=step,
                        stage=stage,
                        repeat=repeat,
                    )
                )
    pool_lifetime = time.perf_counter() - pool_started
    elapsed = time.perf_counter() - started

    stage_summaries = {
        stage: _stage_summary(records) for stage, records in stage_records.items()
    }
    stage_medians = {
        stage: float(summary["median_wall_sec"])
        for stage, summary in stage_summaries.items()
    }
    diagnosis = _classify_reset(
        stage_medians,
        fresh_reference_sec=fresh_reference,
        aged_ratio_minimum=float(probe["aged_to_fresh_ratio_minimum"]),
        recovered_to_fresh_ratio_maximum=float(
            probe["recovered_to_fresh_ratio_maximum"]
        ),
        speedup_minimum=float(probe["speedup_vs_aged_minimum"]),
    )
    all_matrices = [*aging_records]
    for records in stage_records.values():
        all_matrices.extend(records)
    reset_flat = [item for records in reset_records.values() for item in records]
    task_calls = sum(int(item["provider_calls"]) for item in all_matrices)
    reset_calls = sum(int(item["provider_calls"]) for item in reset_flat)
    worker_ids = sorted({pid for item in all_matrices for pid in item["process_ids"]})
    gates = {
        "source_integrity": bool(
            not dd151["pass"] and dd153_result["pass"] and not _load(DD154_RESULT)["pass"]
        ),
        "single_pool": True,
        "exact_matrix_count": len(aging_records)
        == probe["expected_aging_matrices"]
        and sum(len(records) for records in stage_records.values())
        == probe["expected_probe_matrices"],
        "exact_task_and_worker_calls": sum(item["task_count"] for item in all_matrices)
        == (probe["expected_aging_matrices"] + probe["expected_probe_matrices"])
        * probe["tasks_per_matrix"]
        and task_calls == probe["expected_worker_evaluation_calls"]
        and all(
            value == probe["provider_calls_per_task"]
            for item in all_matrices
            for value in item["per_task_provider_calls"]
        ),
        "reset_calls": reset_calls == probe["expected_reset_provider_calls"],
        "worker_ownership": len(worker_ids) == probe["worker_count"]
        and all(len(item["process_ids"]) == probe["worker_count"] for item in all_matrices)
        and all(
            len({int(item["process_id"]) for item in reset_records[stage]})
            == probe["worker_count"]
            for stage in reset_records
        ),
        "startup_calls": sum(int(item["provider_calls"]) for item in startup)
        == probe["expected_startup_provider_calls"],
        "matrix_reproduction": max(
            float(item["matrix_max_abs_difference"]) for item in all_matrices
        )
        <= probe["matrix_absolute_limit"],
        "aging_reproduced": bool(diagnosis["aging_reproduced"]),
        "reset_recovery": bool(diagnosis["recovery_observed"]),
        "wall": elapsed < probe["wall_limit_sec"],
    }
    passed = all(gates.values())
    intervention = diagnosis["first_recovering_intervention"]
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            f"{intervention}_recovery_confirmed"
            if passed
            else "inworker_reset_probe_failed"
        ),
        "decision": (
            "authorize_separately_frozen_reset_api_and_saved_state_proof"
            if passed
            else "retain_persistent_workers_and_stop_reset_implementation"
        ),
        "fresh_reference_wall_sec": float(fresh_reference),
        "dd151_aged_reference_wall_sec": float(probe_state["aged_wall_sec"]),
        "startup_wall_sec": float(startup_wall),
        "pool_lifetime_sec": float(pool_lifetime),
        "analysis_wall_sec": float(elapsed),
        "worker_process_ids": worker_ids,
        "startup_records": startup,
        "aging_records": aging_records,
        "stage_records": stage_records,
        "stage_summaries": stage_summaries,
        "reset_records": reset_records,
        "diagnosis": diagnosis,
        "worker_evaluation_provider_calls": int(task_calls),
        "reset_provider_calls": int(reset_calls),
        "total_governed_provider_calls": int(
            task_calls
            + reset_calls
            + sum(int(item["provider_calls"]) for item in startup)
        ),
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
                "# DD-155 In-Worker Thermo Reset Efficiency Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Fresh root-180 reference: `{fresh_reference:.6f} s`",
                f"- Stage medians: `{stage_medians}`",
                f"- Diagnosis: `{diagnosis}`",
                f"- Reset group records: `{reset_records}`",
                f"- Provider calls: `{result['total_governed_provider_calls']}`",
                f"- Wall: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "No solve, state acceptance, or trajectory occurred. Backend reinitialization in this probe is diagnostic internal mutation, not a production reset API.",
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
