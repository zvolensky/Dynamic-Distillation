#!/usr/bin/env python
"""Prepare or execute DD-150 parallel captured 60-second trajectory."""

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


SCHEMA = "dd150-core-v3-parallel-captured-longer-trajectory-contract-v1"
RESULT_SCHEMA = "dd150-core-v3-parallel-captured-longer-trajectory-result-v1"
DD146_CONTRACT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_contract_20260805.json"
)
DD146_RESULT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_20260805.json"
)
DD149_RESULT = Path(
    "logs/dd149_core_v3_parallel_captured_short_trajectory_20260805.json"
)
CONTRACT = Path(
    "logs/dd150_core_v3_parallel_captured_longer_trajectory_contract_20260805.json"
)
RESULT = Path("logs/dd150_core_v3_parallel_captured_longer_trajectory_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_150_core_v3_parallel_captured_longer_trajectory_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_150_core_v3_parallel_captured_longer_trajectory_20260805.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd149.IMPLEMENTATION,
            "tools/run_core_v3_parallel_captured_longer_trajectory.py",
        )
    )
)


def prepare() -> dict[str, Any]:
    prior_contract = dd149._load(DD146_CONTRACT)
    prior_result = dd149._load(DD146_RESULT)
    dd149_result = dd149._load(DD149_RESULT)
    if (
        not prior_result["pass"]
        or not dd149_result["pass"]
        or dd149_result["decision"]
        != "authorize_separately_frozen_modest_parallel_trajectory_extension"
    ):
        raise RuntimeError("DD-150 requires immutable passing DD-146/DD-149 results")

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
    serial_wall = float(prior_result["wall_clock_sec"])
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": dd149._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd149._sha(ROOT / path)
                for path in (DD146_CONTRACT, DD146_RESULT, DD149_RESULT)
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd146_result_sha256": dd149._sha(ROOT / DD146_RESULT),
            "source_dd149_result_sha256": dd149._sha(ROOT / DD149_RESULT),
            "scientific_contract_changes": [],
            "administrative_contract_changes": [
                "replace serial colored Jacobians with the DD-149 persistent four-process implementation"
            ],
            "parallel_trajectory": {
                "worker_count": 4,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.25,
                "persistent_pool_count": 1,
                "expected_roots": 180,
                "tasks_per_root": 42,
                "expected_tasks": 7560,
                "provider_calls_per_task": 28,
                "expected_parallel_provider_calls": 211680,
                "serial_reference": "DD-146",
                "serial_reference_wall_sec": serial_wall,
                "serial_dd144_wall_sec": serial_wall,
                "total_wall_ratio_limit": 0.60,
                "total_wall_limit_sec": 75.0,
                "trajectory_equivalence_absolute_limit": 1.0e-10,
                "endpoint_equivalence_absolute_limit": 1.0e-10,
            },
            "implementation_sha256": {
                path: dd149._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-146/DD-149 source or DD-150 implementation hash changes",
                "any DD-146 state, disturbance, grid, solver, bound, scale, gate, or limit changes",
                "more than one worker pool is created or it is not retained across all 180 roots",
                "any worker uses stale previous inventory, energy, controller memory, or timestep",
                "any root omits immutable residual, Jacobian, correction, or line-search evidence",
                "any accepted step or endpoint differs from DD-146 beyond 1e-10",
                "task count, provider calls, rank, condition, physicality, conservation, or worker ownership fails",
                "total wall reaches 60 percent of DD-146 or 75 seconds",
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
                "# DD-150 Frozen Parallel Captured 60-Second Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific reference: exact accepted DD-146 trajectory and captures",
                "- Duration/grids: `60 s`, `60 x 1.0 s`, and `120 x 0.5 s`",
                "- Solver: immutable captured modified Newton",
                "- Parallel work: one persistent four-process pool for all 180 Jacobians",
                "- Dynamic worker context: actual previous inventory, energy, controller memory, and timestep",
                "- Serial equivalence: every capture, accepted step, and endpoint `<=1e-10` versus DD-146",
                "- Exact work: 7,560 tasks and 211,680 worker-provider calls",
                "- Meaningful wall gate: `<60%` of DD-146 and `<75 s` including startup/shutdown",
                "- Rebuild, retry, fallback, clipping, projection, controller change, or grid change: prohibited",
                "",
                "Passing may authorize a separately frozen multi-minute parallel trajectory. Failure retains the validated serial path.",
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
    result["source_dd149_result_sha256"] = payload["source_dd149_result_sha256"]
    result["serial_reference"] = "DD-146"
    result["serial_reference_wall_sec"] = payload["parallel_trajectory"][
        "serial_reference_wall_sec"
    ]
    result["wall_ratio_vs_dd146"] = result.pop("wall_ratio_vs_dd144")
    result["classification"] = (
        "parallel_captured_longer_trajectory_equivalent"
        if result["pass"]
        else "parallel_captured_longer_trajectory_failed"
    )
    result["decision"] = (
        "authorize_separately_frozen_multiminute_parallel_trajectory"
        if result["pass"]
        else "retain_validated_serial_longer_trajectory_path"
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")

    roots = len(result["parallel_jacobian_evidence"])
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-150 Parallel Captured 60-Second Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed coarse/refined roots: `{len(result['trajectories']['coarse'])}` / `{len(result['trajectories']['refined'])}`",
                f"- Total captured roots: `{roots}`",
                f"- Worker calls/tasks: `{result['parallel_provider_calls']}` / `{sum(item['task_count'] for item in result['parallel_jacobian_evidence'])}`",
                f"- Capture differences: `{result['capture_differences']}`",
                f"- Accepted-step differences: `{result['trajectory_differences']}`",
                f"- Pool startup: `{result['pool_startup_wall_sec']:.3f} s`",
                f"- Total wall: `{result['total_wall_clock_sec']:.3f} s` (`{result['wall_ratio_vs_dd146']:.3f}x` DD-146)",
                f"- Gates: `{result['gates']}`",
                "",
                "The complete 60-second DD-146 coarse/refined trajectory is reproduced with one persistent process-isolated DWSIM pool. Main-process residual evaluation, globalization, and state acceptance remain unchanged.",
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
