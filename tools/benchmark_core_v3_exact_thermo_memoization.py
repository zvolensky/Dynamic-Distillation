#!/usr/bin/env python
"""Prepare or execute DD-156 exact-state thermo memoization benchmark."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
import os
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

import probe_core_v3_inworker_reset_efficiency as dd155
import probe_core_v3_worker_lifetime_efficiency as dd153
import run_core_v3_parallel_captured_short_trajectory as dd149
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
)


SCHEMA = "dd156-core-v3-exact-thermo-memoization-contract-v1"
RESULT_SCHEMA = "dd156-core-v3-exact-thermo-memoization-result-v1"
DD151_CONTRACT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.json"
)
DD151_RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
DD153_RESULT = Path("logs/dd153_core_v3_worker_lifetime_efficiency_probe_20260806.json")
DD155_RESULT = Path("logs/dd155_core_v3_inworker_reset_efficiency_20260806.json")
CONTRACT = Path("logs/dd156_core_v3_exact_thermo_memoization_contract_20260806.json")
RESULT = Path("logs/dd156_core_v3_exact_thermo_memoization_20260806.json")
CONTRACT_DOC = Path(
    "docs/dd_156_core_v3_exact_thermo_memoization_contract_20260806.md"
)
RESULT_DOC = Path("docs/dd_156_core_v3_exact_thermo_memoization_20260806.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "tests/test_core_v3_exact_thermo_memoization.py",
    "tools/benchmark_core_v3_exact_thermo_memoization.py",
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


class _ExactMemoProvider:
    """Diagnostic exact-key wrapper; it does not alter the production provider."""

    _METHODS = ("fugacity", "enthalpy", "density", "vapor_z", "molecular_weight")

    def __init__(self, delegate: Any, *, enabled: bool = False):
        self.delegate = delegate
        self.enabled = bool(enabled)
        self._caches = {name: {} for name in self._METHODS}
        self._hits = {name: 0 for name in self._METHODS}
        self._misses = {name: 0 for name in self._METHODS}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    @staticmethod
    def _state_key(
        phase: str, temperature_F: float, pressure_psia: float, composition: Sequence[float]
    ) -> tuple[Any, ...]:
        return (
            str(phase),
            float(temperature_F),
            float(pressure_psia),
            tuple(float(value) for value in composition),
        )

    def _lookup(self, method: str, key: Any, evaluate):
        cache = self._caches[method]
        if self.enabled and key in cache:
            self._hits[method] += 1
            value = cache[key]
        else:
            self._misses[method] += 1
            value = evaluate()
            if self.enabled:
                cache[key] = value.copy() if isinstance(value, np.ndarray) else value
        return value.copy() if isinstance(value, np.ndarray) else value

    def phase_fugacity_coefficients(self, phase, T_F, P_psia, comp):
        key = self._state_key(phase, T_F, P_psia, comp)
        return self._lookup(
            "fugacity",
            key,
            lambda: np.asarray(
                self.delegate.phase_fugacity_coefficients(phase, T_F, P_psia, comp),
                dtype=float,
            ),
        )

    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        key = self._state_key(phase, T_F, P_psia, comp)
        return float(
            self._lookup(
                "enthalpy",
                key,
                lambda: float(
                    self.delegate.phase_enthalpy_BTU_lbmol(phase, T_F, P_psia, comp)
                ),
            )
        )

    def liquid_density_lbmol_ft3(self, T_F, P_psia, comp):
        key = self._state_key("liquid", T_F, P_psia, comp)
        return self._lookup(
            "density",
            key,
            lambda: self.delegate.liquid_density_lbmol_ft3(T_F, P_psia, comp),
        )

    def vapor_z_factor_F_psia(self, T_F, P_psia, comp):
        key = self._state_key("vapor", T_F, P_psia, comp)
        return self._lookup(
            "vapor_z",
            key,
            lambda: self.delegate.vapor_z_factor_F_psia(T_F, P_psia, comp),
        )

    def component_mw_lbm_per_lbmol(self):
        return self._lookup(
            "molecular_weight",
            "fixed",
            lambda: np.asarray(self.delegate.component_mw_lbm_per_lbmol(), dtype=float),
        )

    def clear(self) -> None:
        for cache in self._caches.values():
            cache.clear()

    def reset_counts(self) -> None:
        for name in self._METHODS:
            self._hits[name] = 0
            self._misses[name] = 0

    def snapshot(self) -> dict[str, Any]:
        methods = {
            name: {
                "hits": int(self._hits[name]),
                "misses": int(self._misses[name]),
                "cache_entries": int(len(self._caches[name])),
            }
            for name in self._METHODS
        }
        hits = sum(item["hits"] for item in methods.values())
        misses = sum(item["misses"] for item in methods.values())
        return {
            "methods": methods,
            "hits": int(hits),
            "misses": int(misses),
            "calls": int(hits + misses),
            "hit_fraction": float(hits / (hits + misses)) if hits + misses else 0.0,
        }


def _worker_initialize(contract_path: str) -> None:
    dd149._worker_initialize(str(contract_path))


def _worker_memo_control(payload: Mapping[str, Any]) -> dict[str, Any]:
    if dd149._WORKER_CONTEXT is None:
        raise RuntimeError("DD-156 worker context was not initialized")
    time.sleep(float(payload["occupancy_delay_sec"]))
    mode = str(payload["mode"])
    provider = dd149._WORKER_CONTEXT["provider"]
    if mode == "install_passthrough":
        if isinstance(provider, _ExactMemoProvider):
            raise RuntimeError("DD-156 memo wrapper was already installed")
        provider = _ExactMemoProvider(provider, enabled=False)
        dd149._WORKER_CONTEXT["provider"] = provider
        snapshot = provider.snapshot()
    elif mode == "enable_clear":
        if not isinstance(provider, _ExactMemoProvider):
            raise RuntimeError("DD-156 memo wrapper is absent")
        provider.enabled = True
        provider.clear()
        provider.reset_counts()
        snapshot = provider.snapshot()
    elif mode == "snapshot_reset_counts":
        if not isinstance(provider, _ExactMemoProvider):
            raise RuntimeError("DD-156 memo wrapper is absent")
        snapshot = provider.snapshot()
        provider.reset_counts()
    else:
        raise ValueError(f"unsupported DD-156 memo control: {mode}")
    return {
        "mode": mode,
        "process_id": int(os.getpid()),
        "snapshot": snapshot,
    }


def _control_all(
    pool: ProcessPoolExecutor, mode: str, *, worker_count: int, delay: float
) -> list[dict[str, Any]]:
    futures = [
        pool.submit(
            _worker_memo_control,
            {"mode": mode, "occupancy_delay_sec": float(delay)},
        )
        for _ in range(int(worker_count))
    ]
    return [future.result() for future in futures]


def _aggregate_snapshots(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    methods: dict[str, dict[str, int]] = {}
    for name in _ExactMemoProvider._METHODS:
        methods[name] = {
            field: int(sum(item["snapshot"]["methods"][name][field] for item in records))
            for field in ("hits", "misses", "cache_entries")
        }
    hits = sum(item["hits"] for item in methods.values())
    misses = sum(item["misses"] for item in methods.values())
    return {
        "methods": methods,
        "hits": int(hits),
        "misses": int(misses),
        "calls": int(hits + misses),
        "hit_fraction": float(hits / (hits + misses)) if hits + misses else 0.0,
        "process_ids": sorted({int(item["process_id"]) for item in records}),
    }


def _classify(
    *,
    baseline_wall_sec: float,
    warm_wall_sec: float,
    warm_hit_fraction: float,
    speedup_minimum: float,
    hit_fraction_minimum: float,
) -> dict[str, Any]:
    speedup = float(baseline_wall_sec / warm_wall_sec)
    return {
        "speedup": speedup,
        "speedup_pass": bool(speedup >= speedup_minimum),
        "hit_fraction": float(warm_hit_fraction),
        "hit_fraction_pass": bool(warm_hit_fraction >= hit_fraction_minimum),
        "memoization_effective": bool(
            speedup >= speedup_minimum and warm_hit_fraction >= hit_fraction_minimum
        ),
    }


def prepare() -> dict[str, Any]:
    dd151 = _load(DD151_RESULT)
    dd153_result = _load(DD153_RESULT)
    dd155_result = _load(DD155_RESULT)
    if (
        dd151["pass"]
        or not dd153_result["pass"]
        or dd155_result["pass"]
        or dd155_result["decision"]
        != "retain_persistent_workers_and_stop_reset_implementation"
    ):
        raise RuntimeError("DD-156 requires immutable DD-151/DD-153/DD-155 decisions")
    payload = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD151_CONTRACT, DD151_RESULT, DD153_RESULT, DD155_RESULT)
        },
        "benchmark": {
            "path": "coarse",
            "root_index": 180,
            "stage_order": ["uncached", "memo_cold", "memo_warm"],
            "worker_count": 4,
            "spawn_context": True,
            "startup_ping_delay_sec": 0.25,
            "control_occupancy_delay_sec": 0.25,
            "expected_pools": 1,
            "expected_matrices": 3,
            "tasks_per_matrix": 42,
            "logical_provider_calls_per_task": 28,
            "expected_logical_provider_calls": 3528,
            "expected_startup_provider_calls": 116,
            "matrix_absolute_limit": 1.0e-10,
            "fresh_reference_ratio_minimum": 0.65,
            "fresh_reference_ratio_maximum": 1.35,
            "warm_speedup_minimum": 1.50,
            "warm_hit_fraction_minimum": 0.50,
            "wall_limit_sec": 60.0,
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "a DD-151/DD-153/DD-155 result, source, or DD-156 implementation hash changes",
            "the saved root, single pool, three-stage order, exact keys, or thresholds change",
            "the wrapper rounds, normalizes approximately, interpolates, or reuses a non-identical state",
            "any reconstructed matrix differs from DD-151 beyond 1e-10",
            "task, logical-call, process-ownership, cache-accounting, speed, or wall integrity fails",
            "diagnostic memoization is represented as a production implementation",
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
                "# DD-156 Frozen Exact-State Thermo Memoization Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- State: saved DD-151 coarse root `180`",
                "- Stages: uncached pass-through, cold exact memo, warm exact memo",
                "- Scope: fugacity, phase enthalpy, liquid density, vapor Z, and molecular weight",
                "- Exact keys: phase, unrounded float temperature/pressure, and unrounded composition tuple",
                "- Exact work: one four-worker pool, 3 matrices, 126 tasks, 3,528 logical governing calls",
                "- Matrix reproduction: `<=1e-10` absolute",
                "- Performance: warm speedup `>=1.50x`, warm hit fraction `>=0.50`",
                "- Wall limit: `<60 s`",
                "",
                "Passing may authorize only a separately implemented bounded exact-state memoization layer plus saved-state equivalence benchmark. No trajectory is authorized.",
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
        raise RuntimeError("DD-156 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-156 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-156 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-156 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    benchmark = payload["benchmark"]
    dd151 = _load(DD151_RESULT)
    dd153_result = _load(DD153_RESULT)
    source_contract = _load(DD151_CONTRACT)
    source_contract_path = str((ROOT / DD151_CONTRACT).resolve())
    contract = dd149.dd128._contract(source_contract)
    pattern = np.asarray(controlled_terminal_step_pattern(contract), dtype=bool)
    step = float(source_contract["jacobian_step"])
    state = dd153._saved_state(dd151, benchmark["path"], benchmark["root_index"])
    fresh_reference = next(
        float(item["fresh_median_wall_sec"])
        for item in dd153_result["checkpoints"]
        if item["path"] == benchmark["path"]
        and int(item["root_index"]) == int(benchmark["root_index"])
    )

    context = mp.get_context("spawn")
    matrix_records: list[dict[str, Any]] = []
    control_records: dict[str, list[dict[str, Any]]] = {}
    counter_records: dict[str, dict[str, Any]] = {}
    started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(benchmark["worker_count"]),
        mp_context=context,
        initializer=_worker_initialize,
        initargs=(source_contract_path,),
    ) as pool:
        pings = [
            pool.submit(dd149._worker_ping, float(benchmark["startup_ping_delay_sec"]))
            for _ in range(int(benchmark["worker_count"]))
        ]
        startup = [future.result() for future in pings]
        startup_wall = time.perf_counter() - pool_started
        control_records["install_passthrough"] = _control_all(
            pool,
            "install_passthrough",
            worker_count=benchmark["worker_count"],
            delay=benchmark["control_occupancy_delay_sec"],
        )
        matrix_records.append(
            dd155._evaluate_matrix(
                pool,
                state,
                pattern=pattern,
                step=step,
                stage="uncached",
                repeat=1,
            )
        )
        baseline_snapshot = _control_all(
            pool,
            "snapshot_reset_counts",
            worker_count=benchmark["worker_count"],
            delay=benchmark["control_occupancy_delay_sec"],
        )
        counter_records["uncached"] = _aggregate_snapshots(baseline_snapshot)
        control_records["enable_clear"] = _control_all(
            pool,
            "enable_clear",
            worker_count=benchmark["worker_count"],
            delay=benchmark["control_occupancy_delay_sec"],
        )
        matrix_records.append(
            dd155._evaluate_matrix(
                pool,
                state,
                pattern=pattern,
                step=step,
                stage="memo_cold",
                repeat=1,
            )
        )
        cold_snapshot = _control_all(
            pool,
            "snapshot_reset_counts",
            worker_count=benchmark["worker_count"],
            delay=benchmark["control_occupancy_delay_sec"],
        )
        counter_records["memo_cold"] = _aggregate_snapshots(cold_snapshot)
        matrix_records.append(
            dd155._evaluate_matrix(
                pool,
                state,
                pattern=pattern,
                step=step,
                stage="memo_warm",
                repeat=1,
            )
        )
        warm_snapshot = _control_all(
            pool,
            "snapshot_reset_counts",
            worker_count=benchmark["worker_count"],
            delay=benchmark["control_occupancy_delay_sec"],
        )
        counter_records["memo_warm"] = _aggregate_snapshots(warm_snapshot)
    pool_lifetime = time.perf_counter() - pool_started
    elapsed = time.perf_counter() - started

    by_stage = {item["stage"]: item for item in matrix_records}
    diagnosis = _classify(
        baseline_wall_sec=by_stage["uncached"]["wall_sec"],
        warm_wall_sec=by_stage["memo_warm"]["wall_sec"],
        warm_hit_fraction=counter_records["memo_warm"]["hit_fraction"],
        speedup_minimum=float(benchmark["warm_speedup_minimum"]),
        hit_fraction_minimum=float(benchmark["warm_hit_fraction_minimum"]),
    )
    logical_calls = sum(int(item["provider_calls"]) for item in matrix_records)
    worker_ids = sorted({pid for item in matrix_records for pid in item["process_ids"]})
    control_flat = [item for records in control_records.values() for item in records]
    snapshot_processes = {
        stage: records["process_ids"] for stage, records in counter_records.items()
    }
    fresh_ratio = float(by_stage["uncached"]["wall_sec"] / fresh_reference)
    gates = {
        "source_integrity": bool(
            not dd151["pass"] and dd153_result["pass"] and not _load(DD155_RESULT)["pass"]
        ),
        "single_pool": benchmark["expected_pools"] == 1,
        "exact_matrix_task_and_logical_calls": len(matrix_records)
        == benchmark["expected_matrices"]
        and sum(int(item["task_count"]) for item in matrix_records)
        == benchmark["expected_matrices"] * benchmark["tasks_per_matrix"]
        and logical_calls == benchmark["expected_logical_provider_calls"]
        and all(
            value == benchmark["logical_provider_calls_per_task"]
            for item in matrix_records
            for value in item["per_task_provider_calls"]
        ),
        "cache_accounting": all(
            counter_records[stage]["calls"]
            == benchmark["tasks_per_matrix"] * benchmark["logical_provider_calls_per_task"]
            for stage in benchmark["stage_order"]
        ),
        "startup_calls": sum(int(item["provider_calls"]) for item in startup)
        == benchmark["expected_startup_provider_calls"],
        "worker_ownership": len(worker_ids) == benchmark["worker_count"]
        and all(len(item["process_ids"]) == benchmark["worker_count"] for item in matrix_records)
        and all(
            len({int(item["process_id"]) for item in records}) == benchmark["worker_count"]
            for records in control_records.values()
        )
        and all(
            len(processes) == benchmark["worker_count"]
            for processes in snapshot_processes.values()
        ),
        "matrix_reproduction": max(
            float(item["matrix_max_abs_difference"]) for item in matrix_records
        )
        <= benchmark["matrix_absolute_limit"],
        "fresh_baseline_representative": benchmark["fresh_reference_ratio_minimum"]
        <= fresh_ratio
        <= benchmark["fresh_reference_ratio_maximum"],
        "memoization_effective": bool(diagnosis["memoization_effective"]),
        "wall": elapsed < benchmark["wall_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "exact_thermo_memoization_effective"
            if passed
            else "exact_thermo_memoization_not_authorized"
        ),
        "decision": (
            "authorize_bounded_production_memoization_and_saved_state_proof"
            if passed
            else "retain_uncached_direct_thermo_path"
        ),
        "fresh_reference_wall_sec": float(fresh_reference),
        "fresh_baseline_ratio": fresh_ratio,
        "startup_wall_sec": float(startup_wall),
        "pool_lifetime_sec": float(pool_lifetime),
        "analysis_wall_sec": float(elapsed),
        "matrix_records": matrix_records,
        "counter_records": counter_records,
        "control_process_ids": sorted({int(item["process_id"]) for item in control_flat}),
        "worker_process_ids": worker_ids,
        "diagnosis": diagnosis,
        "logical_provider_calls": int(logical_calls),
        "startup_provider_calls": int(sum(int(item["provider_calls"]) for item in startup)),
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
                "# DD-156 Exact-State Thermo Memoization Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Matrix wall: `{ {stage: by_stage[stage]['wall_sec'] for stage in benchmark['stage_order']} }`",
                f"- Cache accounting: `{counter_records}`",
                f"- Diagnosis: `{diagnosis}`",
                f"- Gates: `{gates}`",
                f"- Wall: `{elapsed:.3f} s`",
                "",
                "No solve, state acceptance, or trajectory occurred. The exact memo wrapper is diagnostic and is not part of the production provider.",
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
