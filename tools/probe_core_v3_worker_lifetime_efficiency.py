#!/usr/bin/env python
"""Prepare or execute DD-153 fresh-pool saved-state Jacobian probe."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
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

import audit_core_v3_multiminute_timing as dd152
import run_core_v3_controlled_terminal_first_step as dd128
import run_core_v3_parallel_captured_short_trajectory as dd149
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


SCHEMA = "dd153-core-v3-worker-lifetime-efficiency-probe-contract-v1"
RESULT_SCHEMA = "dd153-core-v3-worker-lifetime-efficiency-probe-result-v1"
DD151_CONTRACT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.json"
)
DD151_RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
DD152_RESULT = Path("logs/dd152_core_v3_multiminute_timing_audit_20260806.json")
CONTRACT = Path(
    "logs/dd153_core_v3_worker_lifetime_efficiency_probe_contract_20260806.json"
)
RESULT = Path("logs/dd153_core_v3_worker_lifetime_efficiency_probe_20260806.json")
CONTRACT_DOC = Path(
    "docs/dd_153_core_v3_worker_lifetime_efficiency_probe_contract_20260806.md"
)
RESULT_DOC = Path(
    "docs/dd_153_core_v3_worker_lifetime_efficiency_probe_20260806.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "tests/test_core_v3_worker_lifetime_efficiency_probe.py",
    "tools/probe_core_v3_worker_lifetime_efficiency.py",
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


def _path_evidence(result: Mapping[str, Any], path: str) -> list[Mapping[str, Any]]:
    token = f":{path}:"
    return [
        item
        for item in result["parallel_jacobian_evidence"]
        if token in str(item["state_id"])
    ]


def _saved_state(
    result: Mapping[str, Any], path: str, root_index: int
) -> dict[str, Any]:
    if root_index <= 1:
        raise ValueError("DD-153 selected roots must have a saved previous endpoint")
    trajectories = result["trajectories"][path]
    captures = result["captured_trajectory_evidence"][f"dd134:{path}"]
    evidence = _path_evidence(result, path)
    if root_index > len(trajectories) or root_index > len(captures):
        raise ValueError("selected root is outside the saved trajectory")
    previous = trajectories[root_index - 2]
    capture = captures[root_index - 1]["capture"]
    saved_jacobian = np.asarray(capture["frozen_jacobian"], dtype=float)
    return {
        "path": path,
        "root_index": int(root_index),
        "step_seconds": 1.0 if path == "coarse" else 0.5,
        "state_id": str(evidence[root_index - 1]["state_id"]),
        "coordinates": np.asarray(capture["initial_coordinates"], dtype=float),
        "previous_inventory_lbmol": previous["inventory_lbmol"],
        "previous_top_u_BTU": previous["top_internal_energy_BTU"],
        "previous_lower_u_BTU": previous["lower_internal_energy_BTU"],
        "previous_controller_memory": previous["controller_memory"],
        "saved_jacobian": saved_jacobian,
        "saved_jacobian_sha256": _matrix_sha(saved_jacobian),
        "aged_wall_sec": float(evidence[root_index - 1]["wall_clock_sec"]),
    }


def _classify(
    checkpoint_records: Sequence[Mapping[str, Any]],
    *,
    speed_ratio_threshold: float,
    required_checkpoint_count: int,
    physical_state_ratio_limit: float,
) -> tuple[str, dict[str, Any]]:
    ratios = [float(item["aged_to_fresh_ratio"]) for item in checkpoint_records]
    passing = sum(value >= speed_ratio_threshold for value in ratios)
    by_path = {
        path: sorted(
            (item for item in checkpoint_records if item["path"] == path),
            key=lambda item: int(item["root_index"]),
        )
        for path in ("coarse", "refined")
    }
    physical_ratios = {
        path: float(
            items[-1]["fresh_median_wall_sec"] / items[0]["fresh_median_wall_sec"]
        )
        for path, items in by_path.items()
    }
    lifetime = bool(
        statistics.median(ratios) >= speed_ratio_threshold
        and passing >= required_checkpoint_count
        and max(physical_ratios.values()) <= physical_state_ratio_limit
    )
    classification = (
        "persistent_worker_lifetime_slowdown_confirmed"
        if lifetime
        else "worker_lifetime_not_isolated"
    )
    return classification, {
        "aged_to_fresh_ratios": ratios,
        "median_aged_to_fresh_ratio": float(statistics.median(ratios)),
        "checkpoints_above_threshold": int(passing),
        "fresh_late_to_early_ratio": physical_ratios,
    }


def prepare() -> dict[str, Any]:
    prior_contract = _load(DD151_CONTRACT)
    dd151 = _load(DD151_RESULT)
    dd152_result = _load(DD152_RESULT)
    if (
        dd151["pass"]
        or not dd152_result["pass"]
        or dd152_result["decision"]
        != "authorize_separately_frozen_persistent_pool_state_efficiency_probe"
    ):
        raise RuntimeError("DD-153 requires immutable DD-151/DD-152 decisions")
    payload = {
        key: value
        for key, value in prior_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "source_contract_payload_sha256",
            "source_dd146_result_sha256",
            "source_dd150_result_sha256",
            "scientific_contract_changes",
            "administrative_contract_changes",
            "parallel_trajectory",
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
    selected = [
        {"path": "coarse", "root_index": value} for value in (60, 180, 300)
    ] + [
        {"path": "refined", "root_index": value} for value in (120, 360, 600)
    ]
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (
                    DD151_CONTRACT,
                    DD151_RESULT,
                    DD152_RESULT,
                    Path("src/dynamic_distillation/thermo_provider_v1.py"),
                    Path("tools/run_core_v3_parallel_captured_short_trajectory.py"),
                )
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd151_result_sha256": _sha(ROOT / DD151_RESULT),
            "source_dd152_result_sha256": _sha(ROOT / DD152_RESULT),
            "probe": {
                "selected_states": selected,
                "rounds": 2,
                "schedule": [selected, list(reversed(selected))],
                "fresh_pool_per_matrix": True,
                "worker_count": 4,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.25,
                "expected_pools": 12,
                "expected_matrices": 12,
                "tasks_per_matrix": 42,
                "provider_calls_per_task": 28,
                "expected_provider_calls": 14112,
                "matrix_absolute_limit": 1.0e-10,
                "fresh_repeat_relative_spread_limit": 0.30,
                "speed_ratio_threshold": 1.25,
                "required_checkpoint_count": 4,
                "physical_state_ratio_limit": 1.25,
                "wall_limit_sec": 180.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-151/DD-152 result, provider/parallel source, or DD-153 implementation hash changes",
                "a selected root, round, or frozen schedule entry is omitted, retried, or reordered",
                "a pool is reused between matrices or does not contain four independent workers",
                "any reconstructed matrix differs from its saved DD-151 matrix beyond 1e-10",
                "task, call, matrix, process, repeat-spread, or wall integrity fails",
                "a nonlinear solve, correction, state acceptance, timestep, trajectory, clipping, projection, or fallback occurs",
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
                "# DD-153 Frozen Worker-Lifetime Efficiency Probe Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- States: DD-151 coarse roots `60/180/300`, refined roots `120/360/600`",
                "- Repeats: two fresh four-worker pools per state, second round reversed",
                "- Work: one saved-state 21-color Jacobian per pool; no solve or state acceptance",
                "- Exact work: 12 matrices, 504 tasks, 14,112 governing calls",
                "- Matrix reproduction: `<=1e-10` absolute",
                "- Fresh repeat spread: `<30%` relative",
                "- Lifetime confirmation: median aged/fresh `>=1.25`, at least 4/6 checkpoints, fresh late/early `<=1.25`",
                "- Wall limit: `<180 s`",
                "",
                "Passing lifetime isolation may authorize only a separately frozen pool-renewal cadence benchmark. No trajectory is authorized.",
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
        raise RuntimeError("DD-153 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-153 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-153 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-153 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    probe = payload["probe"]
    dd151 = _load(DD151_RESULT)
    pattern = controlled_terminal_step_pattern(dd128._contract(payload))
    saved = {
        (item["path"], int(item["root_index"])): _saved_state(
            dd151, item["path"], int(item["root_index"])
        )
        for item in probe["selected_states"]
    }
    context = mp.get_context("spawn")
    contract_path = str((ROOT / CONTRACT).resolve())
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    for round_index, schedule in enumerate(probe["schedule"], start=1):
        for item in schedule:
            state = saved[(item["path"], int(item["root_index"]))]
            tasks, groups = build_colored_central_difference_tasks(
                state["coordinates"],
                pattern=pattern,
                step=float(payload["jacobian_step"]),
                state_id=f"dd153:{state['path']}:root_{state['root_index']}:round_{round_index}",
            )
            work = [
                {
                    "task": task,
                    "previous_inventory_lbmol": state["previous_inventory_lbmol"],
                    "previous_top_u_BTU": state["previous_top_u_BTU"],
                    "previous_lower_u_BTU": state["previous_lower_u_BTU"],
                    "previous_controller_memory": state[
                        "previous_controller_memory"
                    ],
                    "step_seconds": state["step_seconds"],
                }
                for task in tasks
            ]
            pool_started = time.perf_counter()
            with ProcessPoolExecutor(
                max_workers=int(probe["worker_count"]),
                mp_context=context,
                initializer=dd149._worker_initialize,
                initargs=(contract_path,),
            ) as pool:
                pings = [
                    pool.submit(
                        dd149._worker_ping, float(probe["startup_ping_delay_sec"])
                    )
                    for _ in range(int(probe["worker_count"]))
                ]
                ping_records = [future.result() for future in pings]
                startup_wall = time.perf_counter() - pool_started
                matrix_started = time.perf_counter()
                raw = list(pool.map(dd149._worker_evaluate, work, chunksize=1))
                matrix_wall = time.perf_counter() - matrix_started
            pool_wall = time.perf_counter() - pool_started
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
                step=float(payload["jacobian_step"]),
            )
            records.append(
                {
                    "round": int(round_index),
                    "path": state["path"],
                    "root_index": state["root_index"],
                    "aged_wall_sec": state["aged_wall_sec"],
                    "fresh_matrix_wall_sec": float(matrix_wall),
                    "startup_wall_sec": float(startup_wall),
                    "pool_lifetime_sec": float(pool_wall),
                    "ping_process_ids": sorted(
                        {int(value["process_id"]) for value in ping_records}
                    ),
                    "task_process_ids": sorted(
                        {int(value["process_id"]) for value in raw}
                    ),
                    "color_count": len(groups),
                    "task_count": len(raw),
                    "provider_calls": sum(int(value["provider_calls"]) for value in raw),
                    "per_task_provider_calls": [
                        int(value["provider_calls"]) for value in raw
                    ],
                    "saved_matrix_sha256": state["saved_jacobian_sha256"],
                    "fresh_matrix_sha256": _matrix_sha(matrix),
                    "matrix_max_abs_difference": float(
                        np.max(np.abs(matrix - state["saved_jacobian"]))
                    ),
                }
            )
    elapsed = time.perf_counter() - started

    checkpoints = []
    for item in probe["selected_states"]:
        matches = [
            record
            for record in records
            if record["path"] == item["path"]
            and record["root_index"] == item["root_index"]
        ]
        fresh = [float(record["fresh_matrix_wall_sec"]) for record in matches]
        median_fresh = float(statistics.median(fresh))
        spread = float((max(fresh) - min(fresh)) / median_fresh)
        checkpoints.append(
            {
                "path": item["path"],
                "root_index": int(item["root_index"]),
                "aged_wall_sec": float(matches[0]["aged_wall_sec"]),
                "fresh_wall_sec": fresh,
                "fresh_median_wall_sec": median_fresh,
                "fresh_repeat_relative_spread": spread,
                "aged_to_fresh_ratio": float(
                    matches[0]["aged_wall_sec"] / median_fresh
                ),
            }
        )
    classification, diagnosis = _classify(
        checkpoints,
        speed_ratio_threshold=float(probe["speed_ratio_threshold"]),
        required_checkpoint_count=int(probe["required_checkpoint_count"]),
        physical_state_ratio_limit=float(probe["physical_state_ratio_limit"]),
    )
    gates = {
        "saved_source_integrity": bool(
            not dd151["pass"]
            and dd151["capture_storage"] == "full_replay"
            and len(dd151["parallel_jacobian_evidence"]) == 900
        ),
        "exact_schedule": len(records) == probe["expected_matrices"]
        and [
            (record["path"], record["root_index"])
            for record in records
        ]
        == [
            (item["path"], int(item["root_index"]))
            for schedule in probe["schedule"]
            for item in schedule
        ],
        "fresh_process_ownership": all(
            len(record["ping_process_ids"]) == probe["worker_count"]
            and len(record["task_process_ids"]) == probe["worker_count"]
            for record in records
        ),
        "exact_work": sum(record["task_count"] for record in records)
        == probe["expected_matrices"] * probe["tasks_per_matrix"]
        and sum(record["provider_calls"] for record in records)
        == probe["expected_provider_calls"]
        and all(
            value == probe["provider_calls_per_task"]
            for record in records
            for value in record["per_task_provider_calls"]
        ),
        "matrix_reproduction": all(
            record["matrix_max_abs_difference"] <= probe["matrix_absolute_limit"]
            for record in records
        ),
        "repeat_stability": all(
            item["fresh_repeat_relative_spread"]
            <= probe["fresh_repeat_relative_spread_limit"]
            for item in checkpoints
        ),
        "wall": elapsed < probe["wall_limit_sec"],
        "no_solve_or_state_advance": True,
    }
    passed = all(gates.values())
    decision = (
        "authorize_separately_frozen_pool_renewal_cadence_benchmark"
        if passed and classification == "persistent_worker_lifetime_slowdown_confirmed"
        else "retain_current_pool_implementation_without_trajectory_extension"
    )
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification if passed else "worker_lifetime_probe_invalid",
        "decision": decision,
        "records": records,
        "checkpoints": checkpoints,
        "diagnosis": diagnosis,
        "wall_clock_sec": float(elapsed),
        "provider_calls": int(sum(record["provider_calls"] for record in records)),
        "nonlinear_solve_attempted": False,
        "state_advanced": False,
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
                "# DD-153 Worker-Lifetime Efficiency Probe Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Checkpoints: `{checkpoints}`",
                f"- Diagnosis: `{diagnosis}`",
                f"- Provider calls: `{result['provider_calls']}`",
                f"- Wall: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "Fresh pools reconstruct saved DD-151 Jacobians only. No nonlinear root is solved and no state or trajectory advances.",
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
                    "wall_clock_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
