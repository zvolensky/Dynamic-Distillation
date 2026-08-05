#!/usr/bin/env python
"""Prepare or execute DD-146 longer post-cache-fix captured trajectory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

import sys

for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_extended_post_cachefix_captured_trajectory as dd145


SCHEMA = "dd146-core-v3-longer-post-cachefix-captured-trajectory-contract-v1"
RESULT_SCHEMA = "dd146-core-v3-longer-post-cachefix-captured-trajectory-result-v1"
DD145_CONTRACT = Path(
    "logs/dd145_core_v3_extended_post_cachefix_captured_trajectory_contract_20260805.json"
)
DD145_RESULT = Path(
    "logs/dd145_core_v3_extended_post_cachefix_captured_trajectory_20260805.json"
)
CONTRACT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_contract_20260805.json"
)
RESULT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_20260805.json"
)
CONTRACT_DOC = Path(
    "docs/dd_146_core_v3_longer_post_cachefix_captured_trajectory_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_146_core_v3_longer_post_cachefix_captured_trajectory_20260805.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd145.IMPLEMENTATION,
            "tools/run_core_v3_longer_post_cachefix_captured_trajectory.py",
        )
    )
)


def prepare() -> dict[str, Any]:
    prior_contract = dd145.dd144._load(DD145_CONTRACT)
    prior_result = dd145.dd144._load(DD145_RESULT)
    if (
        not prior_result["pass"]
        or prior_result["decision"]
        != "authorize_separately_frozen_longer_captured_trajectory_contract"
    ):
        raise RuntimeError("DD-146 requires the immutable passing DD-145 decision")

    payload = {
        key: value
        for key, value in prior_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "source_contract_payload_sha256",
            "scientific_contract_changes",
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
            "preparation_base_commit": dd145.dd144._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd145.dd144._sha(ROOT / path)
                for path in (DD145_CONTRACT, DD145_RESULT)
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd145_result_sha256": dd145.dd144._sha(ROOT / DD145_RESULT),
            "scientific_contract_changes": [
                "duration_seconds: 20.0 -> 60.0; step sizes unchanged"
            ],
            "administrative_contract_changes": [
                "provider_call_limit: 80000 -> 240000"
            ],
            "trajectory_grid": {
                "duration_seconds": 60.0,
                "coarse_step_seconds": 1.0,
                "coarse_steps": 60,
                "refined_step_seconds": 0.5,
                "refined_steps": 120,
            },
            "provider_call_limit": 240000,
            "implementation_sha256": {
                path: dd145.dd144._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-145 source or DD-146 implementation hash changes",
                "anything except duration, corresponding step counts, or provider-call budget changes from DD-145",
                "either 60-second path is incomplete or any inherited scientific gate fails",
                "any step omits immutable initial/final residuals, frozen Jacobian, correction, or line-search evidence",
                "captured residual identity is nonzero or any capture array is writeable",
                "a Jacobian rebuild, alternate solver, retry, fallback, clipping, projection, controller move, or changed step size occurs",
                "provider calls reach 240000 or wall clock reaches 180 seconds",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = dd145.dd144._hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-146 Frozen Longer Post-Cache-Fix Captured-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Sole scientific change from DD-145: duration `20 s -> 60 s`",
                "- Administrative change: provider-call limit `80000 -> 240000`",
                "- Initial state/controller move: exact DD-145",
                "- Grids: `60 x 1.0 s` and `120 x 0.5 s`",
                "- Solver: one frozen 21-color Jacobian and factorization per root",
                "- Complete immutable per-step evidence: required",
                "- Wall-clock limit: `<180 s`",
                "- Rebuild, alternate solver, retry, fallback, clipping, projection, or controller change: prohibited",
                "",
                "This is the final brute-force fully captured extension. Passing may authorize only a separately frozen trajectory-efficiency design before multi-minute operation. Failure stops with replay-complete evidence.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def execute() -> dict[str, Any]:
    payload = dd145.dd144._load(CONTRACT)
    original = (
        dd145.CONTRACT,
        dd145.RESULT,
        dd145.RESULT_DOC,
        dd145.RESULT_SCHEMA,
    )
    dd145.CONTRACT = CONTRACT
    dd145.RESULT = RESULT
    dd145.RESULT_DOC = RESULT_DOC
    dd145.RESULT_SCHEMA = RESULT_SCHEMA
    try:
        result = dd145.execute()
    finally:
        (
            dd145.CONTRACT,
            dd145.RESULT,
            dd145.RESULT_DOC,
            dd145.RESULT_SCHEMA,
        ) = original

    result["schema_id"] = RESULT_SCHEMA
    result["source_dd145_result_sha256"] = payload["source_dd145_result_sha256"]
    result["classification"] = (
        "longer_post_cachefix_captured_trajectory_passed"
        if result["pass"]
        else "longer_post_cachefix_captured_trajectory_failed"
    )
    result["decision"] = (
        "authorize_separately_frozen_trajectory_efficiency_design"
        if result["pass"]
        else "stop_with_replay_complete_longer_trajectory_evidence"
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")

    completed = {
        name: len(steps) for name, steps in result["trajectories"].items()
    }
    residuals = [
        step["residual_inf_norm"]
        for steps in result["trajectories"].values()
        for step in steps
    ]
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-146 Longer Post-Cache-Fix Captured-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed coarse/refined steps: `{completed.get('coarse', 0)}` / `{completed.get('refined', 0)}`",
                f"- Worst residual: `{max(residuals):.9e}`",
                f"- Endpoint refinement: `{result['endpoint_refinement']}`",
                f"- Capture gates: `{result['capture_gates']}`",
                f"- DWSIM calls: `{result['provider_provenance']['total_calls']}`",
                f"- Wall clock: `{result['wall_clock_sec']:.3f} s`",
                "",
                "The sole scientific change from DD-145 is the 60-second duration. Complete captured evidence is retained for every attempted step.",
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
