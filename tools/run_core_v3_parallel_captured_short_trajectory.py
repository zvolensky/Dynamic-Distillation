#!/usr/bin/env python
"""Prepare or execute DD-149 parallel captured short trajectory."""

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
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_captured_modified_newton as dd137
import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_modified_newton_short_controlled_trajectory as dd134
import run_core_v3_parallel_captured_first_root as dd148
import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.core_v3.captured_modified_newton_v1 import (
    solve_captured_modified_newton,
)
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
import dynamic_distillation.core_v3.controlled_terminal_trajectory_v1 as trajectory_module


SCHEMA = "dd149-core-v3-parallel-captured-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd149-core-v3-parallel-captured-short-trajectory-result-v1"
DD144_CONTRACT = Path(
    "logs/dd144_core_v3_post_cachefix_captured_short_trajectory_contract_20260805.json"
)
DD144_RESULT = Path(
    "logs/dd144_core_v3_post_cachefix_captured_short_trajectory_20260805.json"
)
DD148_RESULT = Path(
    "logs/dd148_core_v3_parallel_captured_first_root_20260805.json"
)
CONTRACT = Path(
    "logs/dd149_core_v3_parallel_captured_short_trajectory_contract_20260805.json"
)
RESULT = Path("logs/dd149_core_v3_parallel_captured_short_trajectory_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_149_core_v3_parallel_captured_short_trajectory_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_149_core_v3_parallel_captured_short_trajectory_20260805.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd148.IMPLEMENTATION,
            "src/dynamic_distillation/core_v3/controlled_terminal_trajectory_v1.py",
            "tests/test_core_v3_controlled_terminal_trajectory_v1.py",
            "tools/run_core_v3_parallel_captured_short_trajectory.py",
        )
    )
)


_WORKER_CONTEXT: dict[str, Any] | None = None


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


def _worker_initialize(contract_path: str) -> None:
    global _WORKER_CONTEXT
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
    evaluate_controlled_terminal_zero_time(
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
        state_id=f"dd149:worker_{os.getpid()}:warmup",
        evaluation_kind="residual",
        **common,
    )
    _WORKER_CONTEXT = {
        "contract": contract,
        "spec": spec,
        "reference": reference,
        "template": template,
        "provider": provider,
        "call_audit": call_audit,
        "level_setpoints": TerminalLevelSetpoints(**payload["moved_level_setpoints"]),
        "step_common": {
            "component_rate_scale_lbmolph": float(
                payload["component_rate_scale_lbmolph"]
            ),
            "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
            "fixed_steady_scales": payload["fixed_steady_residual_scales"],
            "storage_scales_BTU": payload["storage_scales_BTU"],
            "pressure_numerical": common["pressure_numerical"],
        },
    }


def _worker_ping(delay_seconds: float) -> dict[str, int]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-149 worker context was not initialized")
    time.sleep(float(delay_seconds))
    return {
        "process_id": int(os.getpid()),
        "provider_calls": len(_WORKER_CONTEXT["call_audit"].records),
    }


def _worker_evaluate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-149 worker context was not initialized")
    task: ColoredCentralDifferenceTask = payload["task"]
    call_audit = _WORKER_CONTEXT["call_audit"]
    before = len(call_audit.records)
    started = time.perf_counter()
    evaluation = evaluate_controlled_terminal_backward_euler_residual(
        _WORKER_CONTEXT["contract"],
        _WORKER_CONTEXT["spec"],
        _WORKER_CONTEXT["reference"],
        _WORKER_CONTEXT["template"],
        _WORKER_CONTEXT["provider"],
        call_audit,
        previous_inventory_lbmol=np.asarray(
            payload["previous_inventory_lbmol"], dtype=float
        ),
        previous_top_internal_energy_BTU=float(payload["previous_top_u_BTU"]),
        previous_lower_internal_energy_BTU=np.asarray(
            payload["previous_lower_u_BTU"], dtype=float
        ),
        previous_controller_memory=np.asarray(
            payload["previous_controller_memory"], dtype=float
        ),
        level_setpoints=_WORKER_CONTEXT["level_setpoints"],
        solve_coordinates=np.asarray(task.coordinates, dtype=float),
        step_seconds=float(payload["step_seconds"]),
        state_id=task.state_id,
        evaluation_kind="jacobian",
        **_WORKER_CONTEXT["step_common"],
    )
    elapsed = time.perf_counter() - started
    after = len(call_audit.records)
    return {
        "order": int(task.order),
        "residual": [float(value) for value in evaluation.scaled],
        "process_id": int(os.getpid()),
        "provider_calls": int(after - before),
        "wall_clock_sec": float(elapsed),
    }


def _compare(left: Any, right: Any) -> tuple[float, bool]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if set(left) != set(right):
            return float("inf"), False
        comparisons = [_compare(left[key], right[key]) for key in left]
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return float("inf"), False
        comparisons = [_compare(a, b) for a, b in zip(left, right, strict=True)]
    elif isinstance(left, bool) or isinstance(right, bool):
        return 0.0, bool(left is right)
    elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)), True
    else:
        return 0.0, bool(left == right)
    if not comparisons:
        return 0.0, True
    return max(item[0] for item in comparisons), all(item[1] for item in comparisons)


def prepare() -> dict[str, Any]:
    prior_contract = _load(DD144_CONTRACT)
    prior_result = _load(DD144_RESULT)
    dd148_result = _load(DD148_RESULT)
    if (
        not prior_result["pass"]
        or not dd148_result["pass"]
        or dd148_result["decision"]
        != "authorize_separately_frozen_parallel_captured_short_trajectory_contract"
    ):
        raise RuntimeError("DD-149 requires immutable passing DD-144/DD-148 results")
    payload = {
        key: value
        for key, value in prior_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "source_contract_payload_sha256",
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
    serial_wall = float(prior_result["wall_clock_sec"])
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD144_CONTRACT, DD144_RESULT, DD148_RESULT)
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd144_result_sha256": _sha(ROOT / DD144_RESULT),
            "source_dd148_result_sha256": _sha(ROOT / DD148_RESULT),
            "scientific_contract_changes": [],
            "parallel_trajectory": {
                "worker_count": 4,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.25,
                "persistent_pool_count": 1,
                "expected_roots": 30,
                "tasks_per_root": 42,
                "expected_tasks": 1260,
                "provider_calls_per_task": 28,
                "expected_parallel_provider_calls": 35280,
                "serial_dd144_wall_sec": serial_wall,
                "total_wall_ratio_limit": 0.60,
                "total_wall_limit_sec": 75.0,
                "trajectory_equivalence_absolute_limit": 1.0e-10,
                "endpoint_equivalence_absolute_limit": 1.0e-10,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-144/DD-148 source or DD-149 implementation hash changes",
                "the DD-144 state, disturbance, grids, solver, bounds, scales, gates, or limits change",
                "more than one worker pool is created or the pool is not retained across both grids",
                "any worker evaluates a Jacobian against stale previous inventory, energy, memory, or timestep",
                "any root omits immutable residual, Jacobian, correction, or line-search evidence",
                "any accepted step or endpoint differs from DD-144 beyond a frozen limit",
                "task count, provider calls, rank, condition, physicality, conservation, or worker ownership fails",
                "total wall exceeds 60 percent of DD-144 or 75 seconds",
                "a rebuild, retry, fallback, clipping, projection, or grid change occurs",
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
                "# DD-149 Frozen Parallel Captured Short-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific experiment: exact DD-144 `10 s` coarse/refined trajectory",
                "- Solver: immutable captured modified Newton",
                "- Parallel work: one persistent four-process pool for all 30 Jacobians",
                "- Dynamic worker context: actual previous inventory, energy, controller memory, and timestep for every root",
                "- Capture: complete residual, matrix, correction, and line-search evidence for every root",
                "- Serial equivalence: every step and both endpoints `<=1e-10` versus DD-144",
                "- Exact work: 1,260 tasks and 35,280 worker-provider calls",
                "- Meaningful wall gate: `<60%` of DD-144 and `<75 s` including startup/shutdown",
                "- Rebuild, retry, fallback, clipping, projection, or grid change: prohibited",
                "",
                "Passing authorizes only a separately frozen modest parallel trajectory extension. Failure retains the serial path.",
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
        raise RuntimeError("DD-149 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-149 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-149 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-149 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    parallel_contract = payload["parallel_trajectory"]
    accepted = _load(DD144_RESULT)
    pattern = controlled_terminal_step_pattern(dd128._contract(payload))
    evidence: list[dict[str, Any]] = []
    captures: dict[str, Any] = {}
    original_paths = (dd134.CONTRACT, dd134.RESULT, dd134.RESULT_DOC, dd134.RESULT_SCHEMA)
    original_run = dd134.run_controlled_terminal_trajectory
    original_solver = trajectory_module.solve_modified_newton
    context = mp.get_context("spawn")
    total_started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(parallel_contract["worker_count"]),
        mp_context=context,
        initializer=_worker_initialize,
        initargs=(str((ROOT / CONTRACT).resolve()),),
    ) as pool:
        pings = [
            pool.submit(
                _worker_ping, float(parallel_contract["startup_ping_delay_sec"])
            )
            for _ in range(int(parallel_contract["worker_count"]))
        ]
        ping_records = [future.result() for future in pings]
        process_ids = sorted({int(item["process_id"]) for item in ping_records})
        startup_wall = time.perf_counter() - pool_started

        def captured_parallel_run(*args, **kwargs):
            def step_factory(
                _objective,
                previous_inventory,
                previous_top_u,
                previous_lower_u,
                previous_memory,
                step_seconds,
            ):
                def jacobian(candidate, state_id):
                    tasks, groups = build_colored_central_difference_tasks(
                        candidate,
                        pattern=pattern,
                        step=float(payload["jacobian_step"]),
                        state_id=state_id,
                    )
                    work = [
                        {
                            "task": task,
                            "previous_inventory_lbmol": np.asarray(
                                previous_inventory, dtype=float
                            ).tolist(),
                            "previous_top_u_BTU": float(previous_top_u),
                            "previous_lower_u_BTU": np.asarray(
                                previous_lower_u, dtype=float
                            ).tolist(),
                            "previous_controller_memory": np.asarray(
                                previous_memory, dtype=float
                            ).tolist(),
                            "step_seconds": float(step_seconds),
                        }
                        for task in tasks
                    ]
                    started = time.perf_counter()
                    raw = list(pool.map(_worker_evaluate, work, chunksize=1))
                    matrix = assemble_colored_central_difference_jacobian(
                        tasks,
                        [
                            ColoredCentralDifferenceResult(
                                order=int(item["order"]),
                                residual=tuple(
                                    float(value) for value in item["residual"]
                                ),
                            )
                            for item in raw
                        ],
                        pattern=pattern,
                        step=float(payload["jacobian_step"]),
                    )
                    evidence.append(
                        {
                            "state_id": state_id,
                            "step_seconds": float(step_seconds),
                            "wall_clock_sec": float(time.perf_counter() - started),
                            "color_count": len(groups),
                            "task_count": len(raw),
                            "task_process_ids": sorted(
                                {int(item["process_id"]) for item in raw}
                            ),
                            "provider_calls": sum(
                                int(item["provider_calls"]) for item in raw
                            ),
                            "per_task_provider_calls": [
                                int(item["provider_calls"]) for item in raw
                            ],
                        }
                    )
                    return matrix

                return jacobian

            trajectory_module.solve_modified_newton = solve_captured_modified_newton
            try:
                outcome = original_run(
                    *args, **kwargs, step_jacobian_factory=step_factory
                )
            finally:
                trajectory_module.solve_modified_newton = original_solver
            captures[outcome.name] = [
                {
                    "index": step.index,
                    "time_seconds": step.time_seconds,
                    "capture": dd137._record(step.outcome),
                }
                for step in outcome.steps
            ]
            return outcome

        dd134.CONTRACT = CONTRACT
        dd134.RESULT = RESULT
        dd134.RESULT_DOC = RESULT_DOC
        dd134.RESULT_SCHEMA = RESULT_SCHEMA
        dd134.run_controlled_terminal_trajectory = captured_parallel_run
        try:
            result = dd134.execute()
        finally:
            (
                dd134.CONTRACT,
                dd134.RESULT,
                dd134.RESULT_DOC,
                dd134.RESULT_SCHEMA,
            ) = original_paths
            dd134.run_controlled_terminal_trajectory = original_run
            trajectory_module.solve_modified_newton = original_solver
    total_wall = time.perf_counter() - total_started

    accepted_captures = accepted["captured_trajectory_evidence"]
    capture_differences = {}
    capture_metadata = {}
    for name, items in captures.items():
        difference, metadata_equal = _compare(items, accepted_captures[name])
        capture_differences[name] = float(difference)
        capture_metadata[name] = bool(metadata_equal)
    trajectory_differences = {}
    trajectory_metadata = {}
    for short_name in ("coarse", "refined"):
        difference, metadata_equal = _compare(
            result["trajectories"][short_name], accepted["trajectories"][short_name]
        )
        trajectory_differences[short_name] = float(difference)
        trajectory_metadata[short_name] = bool(metadata_equal)

    roots = len(evidence)
    tasks = sum(item["task_count"] for item in evidence)
    calls = sum(item["provider_calls"] for item in evidence)
    limit = float(parallel_contract["trajectory_equivalence_absolute_limit"])
    source_gates = dict(result["gates"])
    parallel_gates = {
        "source_scientific_gates": bool(result["pass"] and all(source_gates.values())),
        "one_persistent_pool": True,
        "worker_process_ownership": len(process_ids)
        == parallel_contract["worker_count"]
        and all(
            len(item["task_process_ids"]) == parallel_contract["worker_count"]
            for item in evidence
        ),
        "complete_root_capture": roots == parallel_contract["expected_roots"]
        and sum(len(items) for items in captures.values()) == roots,
        "exact_task_count": tasks == parallel_contract["expected_tasks"]
        and all(
            item["task_count"] == parallel_contract["tasks_per_root"]
            for item in evidence
        ),
        "exact_parallel_provider_calls": calls
        == parallel_contract["expected_parallel_provider_calls"]
        and all(
            value == parallel_contract["provider_calls_per_task"]
            for item in evidence
            for value in item["per_task_provider_calls"]
        ),
        "captured_serial_equivalence": max(capture_differences.values()) <= limit
        and all(capture_metadata.values()),
        "accepted_step_serial_equivalence": max(trajectory_differences.values())
        <= parallel_contract["endpoint_equivalence_absolute_limit"]
        and all(trajectory_metadata.values()),
        "meaningful_total_wall_improvement": total_wall
        < parallel_contract["total_wall_ratio_limit"]
        * parallel_contract["serial_dd144_wall_sec"],
        "absolute_wall": total_wall < parallel_contract["total_wall_limit_sec"],
        "no_rebuild_retry_fallback_or_grid_change": bool(
            not result["jacobian_rebuild_attempted"]
            and not result["fallback_attempted"]
            and not result["retry_attempted"]
            and not result["grid_changed"]
        ),
    }
    passed = all(parallel_gates.values())
    result.update(
        {
            "schema_id": RESULT_SCHEMA,
            "classification": (
                "parallel_captured_short_trajectory_equivalent"
                if passed
                else "parallel_captured_short_trajectory_failed"
            ),
            "decision": (
                "authorize_separately_frozen_modest_parallel_trajectory_extension"
                if passed
                else "retain_serial_captured_trajectory_path"
            ),
            "source_dd134_gates": source_gates,
            "captured_trajectory_evidence": captures,
            "parallel_jacobian_evidence": evidence,
            "worker_process_ids": process_ids,
            "worker_startup_provider_calls": ping_records,
            "pool_startup_wall_sec": float(startup_wall),
            "trajectory_wall_clock_sec": float(result["wall_clock_sec"]),
            "total_wall_clock_sec": float(total_wall),
            "wall_ratio_vs_dd144": float(
                total_wall / parallel_contract["serial_dd144_wall_sec"]
            ),
            "parallel_provider_calls": int(calls),
            "capture_differences": capture_differences,
            "capture_metadata_equal": capture_metadata,
            "trajectory_differences": trajectory_differences,
            "trajectory_metadata_equal": trajectory_metadata,
            "gates": parallel_gates,
            "pass": bool(passed),
            "persistent_pool_count": 1,
            "campaign_executed_once": True,
        }
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-149 Parallel Captured Short-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed roots: `{roots}`",
                f"- Worker calls/tasks: `{calls}` / `{tasks}`",
                f"- Capture differences: `{capture_differences}`",
                f"- Accepted-step differences: `{trajectory_differences}`",
                f"- Pool startup: `{startup_wall:.3f} s`",
                f"- Total wall: `{total_wall:.3f} s` (`{result['wall_ratio_vs_dd144']:.3f}x` DD-144)",
                f"- Gates: `{parallel_gates}`",
                "",
                "The exact DD-144 coarse/refined science is retained. One persistent process-isolated DWSIM pool supplies all Jacobians, while residuals, globalization, and state acceptance remain in the main process.",
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
                    "total_wall_clock_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
