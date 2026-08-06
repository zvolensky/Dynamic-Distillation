#!/usr/bin/env python
"""Prepare or execute DD-151 compact parallel captured five-minute trajectory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_parallel_captured_short_trajectory as dd149


SCHEMA = "dd151-core-v3-parallel-captured-multiminute-trajectory-contract-v1"
RESULT_SCHEMA = "dd151-core-v3-parallel-captured-multiminute-trajectory-result-v1"
DD146_CONTRACT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_contract_20260805.json"
)
DD146_RESULT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_20260805.json"
)
DD150_RESULT = Path(
    "logs/dd150_core_v3_parallel_captured_longer_trajectory_20260805.json"
)
CONTRACT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.json"
)
RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
CONTRACT_DOC = Path(
    "docs/dd_151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_151_core_v3_parallel_captured_multiminute_trajectory_20260805.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd149.IMPLEMENTATION,
            "tests/test_core_v3_parallel_capture_evidence_v1.py",
            "tools/run_core_v3_parallel_captured_multiminute_trajectory.py",
        )
    )
)


def prepare() -> dict[str, Any]:
    prior_contract = dd149._load(DD146_CONTRACT)
    prior_result = dd149._load(DD146_RESULT)
    dd150_result = dd149._load(DD150_RESULT)
    if (
        not prior_result["pass"]
        or not dd150_result["pass"]
        or dd150_result["decision"]
        != "authorize_separately_frozen_multiminute_parallel_trajectory"
    ):
        raise RuntimeError("DD-151 requires immutable passing DD-146/DD-150 results")

    payload = {
        key: value
        for key, value in prior_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "source_contract_payload_sha256",
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
    dd150_wall = float(dd150_result["total_wall_clock_sec"])
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": dd149._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd149._sha(ROOT / path)
                for path in (DD146_CONTRACT, DD146_RESULT, DD150_RESULT)
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd146_result_sha256": dd149._sha(ROOT / DD146_RESULT),
            "source_dd150_result_sha256": dd149._sha(ROOT / DD150_RESULT),
            "scientific_contract_changes": [
                "duration_seconds: 60.0 -> 300.0; step sizes unchanged"
            ],
            "administrative_contract_changes": [
                "wall_clock_limit_sec: 180.0 -> 330.0",
                "successful full captures replaced by deterministic per-root SHA-256 summaries; failures retain full replay evidence",
            ],
            "trajectory_grid": {
                "duration_seconds": 300.0,
                "coarse_step_seconds": 1.0,
                "coarse_steps": 300,
                "refined_step_seconds": 0.5,
                "refined_steps": 600,
            },
            "wall_clock_limit_sec": 330.0,
            "parallel_trajectory": {
                "worker_count": 4,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.25,
                "persistent_pool_count": 1,
                "expected_roots": 900,
                "tasks_per_root": 42,
                "expected_tasks": 37800,
                "provider_calls_per_task": 28,
                "expected_parallel_provider_calls": 1058400,
                "serial_reference": "DD-146 first 60-second prefix",
                "reference_prefix_steps": {"coarse": 60, "refined": 120},
                "compact_success_capture": True,
                "serial_dd144_wall_sec": dd150_wall,
                "total_wall_ratio_limit": 5.0,
                "total_wall_limit_sec": 330.0,
                "trajectory_equivalence_absolute_limit": 1.0e-10,
                "endpoint_equivalence_absolute_limit": 1.0e-10,
            },
            "implementation_sha256": {
                path: dd149._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-146/DD-150 source or DD-151 implementation hash changes",
                "anything except duration, corresponding step counts, wall budget, or success-artifact compaction changes",
                "the first 60-second prefix differs from DD-146 beyond 1e-10",
                "either 300-second path is incomplete or any inherited scientific gate fails",
                "more than one worker pool is created or it is not retained across all 900 roots",
                "any worker uses stale previous inventory, energy, controller memory, or timestep",
                "any root lacks immutable complete in-memory capture before success compaction",
                "task count, provider calls, rank, condition, physicality, conservation, or worker ownership fails",
                "governed wall reaches five times DD-150 or 330 seconds",
                "a rebuild, retry, fallback, clipping, projection, controller change, or grid change occurs",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = dd149._hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-151 Frozen Parallel Captured Five-Minute Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Sole scientific change from DD-146: duration `60 s -> 300 s`",
                "- Grids: `300 x 1.0 s` and `600 x 0.5 s`",
                "- Solver/parallel path: exact DD-150 captured modified Newton and one persistent four-process pool",
                "- Frozen oracle: first `60/120` roots exactly reproduce DD-146 within `1e-10`",
                "- Remaining acceptance: inherited endpoint refinement, physicality, pressure, conservation, direction, and kinematics",
                "- Exact work: 37,800 tasks and 1,058,400 worker-provider calls",
                "- Successful evidence: deterministic per-root capture and call-audit SHA-256 summaries",
                "- Failure evidence: complete replay captures retained",
                "- Governed wall: `<5x` DD-150 and `<330 s` including pool lifetime",
                "- Rebuild, retry, fallback, clipping, projection, controller change, or grid change: prohibited",
                "",
                "Passing establishes a five-minute parallel controlled trajectory. Failure stops with full replay evidence.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def execute() -> dict[str, Any]:
    payload = dd149._load(CONTRACT)
    original = (
        dd149.CONTRACT,
        dd149.RESULT,
        dd149.CONTRACT_DOC,
        dd149.RESULT_DOC,
        dd149.RESULT_SCHEMA,
        dd149.DD144_RESULT,
    )
    dd149.CONTRACT = CONTRACT
    dd149.RESULT = RESULT
    dd149.CONTRACT_DOC = CONTRACT_DOC
    dd149.RESULT_DOC = RESULT_DOC
    dd149.RESULT_SCHEMA = RESULT_SCHEMA
    dd149.DD144_RESULT = DD146_RESULT
    try:
        result = dd149.execute()
    finally:
        (
            dd149.CONTRACT,
            dd149.RESULT,
            dd149.CONTRACT_DOC,
            dd149.RESULT_DOC,
            dd149.RESULT_SCHEMA,
            dd149.DD144_RESULT,
        ) = original

    result["schema_id"] = RESULT_SCHEMA
    result["source_dd146_result_sha256"] = payload["source_dd146_result_sha256"]
    result["source_dd150_result_sha256"] = payload["source_dd150_result_sha256"]
    result["serial_reference"] = "DD-146 first 60-second prefix"
    result["wall_multiple_vs_dd150"] = result.pop("wall_ratio_vs_dd144")
    result["classification"] = (
        "parallel_captured_five_minute_trajectory_passed"
        if result["pass"]
        else "parallel_captured_five_minute_trajectory_failed"
    )
    result["decision"] = (
        "five_minute_parallel_controlled_trajectory_established"
        if result["pass"]
        else "stop_with_replay_complete_multiminute_evidence"
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")

    roots = len(result["parallel_jacobian_evidence"])
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-151 Parallel Captured Five-Minute Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed coarse/refined roots: `{len(result['trajectories']['coarse'])}` / `{len(result['trajectories']['refined'])}`",
                f"- Total roots: `{roots}`",
                f"- Worker calls/tasks: `{result['parallel_provider_calls']}` / `{sum(item['task_count'] for item in result['parallel_jacobian_evidence'])}`",
                f"- DD-146 prefix capture differences: `{result['capture_differences']}`",
                f"- DD-146 prefix accepted-step differences: `{result['trajectory_differences']}`",
                f"- Endpoint refinement: `{result['endpoint_refinement']}`",
                f"- Capture storage: `{result['capture_storage']}`",
                f"- Pool startup: `{result['pool_startup_wall_sec']:.3f} s`",
                f"- Governed wall: `{result['total_wall_clock_sec']:.3f} s` (`{result['wall_multiple_vs_dd150']:.3f}x` DD-150)",
                f"- Gates: `{result['gates']}`",
                "",
                "The first 60 seconds reproduce DD-146 exactly. Successful full captures are represented by deterministic per-root digests; a failed campaign would retain full replay evidence.",
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
