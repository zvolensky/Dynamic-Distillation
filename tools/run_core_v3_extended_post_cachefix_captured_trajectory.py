#!/usr/bin/env python
"""Prepare or execute DD-145 extended post-cache-fix captured trajectory."""

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

import run_core_v3_post_cachefix_captured_short_trajectory as dd144


SCHEMA = "dd145-core-v3-extended-post-cachefix-captured-trajectory-contract-v1"
RESULT_SCHEMA = "dd145-core-v3-extended-post-cachefix-captured-trajectory-result-v1"
DD144_CONTRACT = Path(
    "logs/dd144_core_v3_post_cachefix_captured_short_trajectory_contract_20260805.json"
)
DD144_RESULT = Path(
    "logs/dd144_core_v3_post_cachefix_captured_short_trajectory_20260805.json"
)
CONTRACT = Path(
    "logs/dd145_core_v3_extended_post_cachefix_captured_trajectory_contract_20260805.json"
)
RESULT = Path(
    "logs/dd145_core_v3_extended_post_cachefix_captured_trajectory_20260805.json"
)
CONTRACT_DOC = Path(
    "docs/dd_145_core_v3_extended_post_cachefix_captured_trajectory_contract_20260805.md"
)
RESULT_DOC = Path(
    "docs/dd_145_core_v3_extended_post_cachefix_captured_trajectory_20260805.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd144.IMPLEMENTATION,
            "tools/run_core_v3_extended_post_cachefix_captured_trajectory.py",
        )
    )
)


def prepare() -> dict[str, Any]:
    prior_contract = dd144._load(DD144_CONTRACT)
    prior_result = dd144._load(DD144_RESULT)
    if (
        not prior_result["pass"]
        or prior_result["decision"]
        != "authorize_separately_frozen_controlled_trajectory_extension_contract"
    ):
        raise RuntimeError("DD-145 requires the immutable passing DD-144 decision")

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
            "preparation_base_commit": dd144._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd144._sha(ROOT / path)
                for path in (DD144_CONTRACT, DD144_RESULT)
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd144_result_sha256": dd144._sha(ROOT / DD144_RESULT),
            "scientific_contract_changes": [
                "duration_seconds: 10.0 -> 20.0; step sizes unchanged"
            ],
            "trajectory_grid": {
                "duration_seconds": 20.0,
                "coarse_step_seconds": 1.0,
                "coarse_steps": 20,
                "refined_step_seconds": 0.5,
                "refined_steps": 40,
            },
            "implementation_sha256": {
                path: dd144._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-144 source or DD-145 implementation hash changes",
                "anything except duration and corresponding step counts changes from DD-144",
                "either 20-second path is incomplete or any inherited gate fails",
                "any step omits immutable initial/final residuals, frozen Jacobian, correction, or line-search evidence",
                "captured residual identity is nonzero or any capture array is writeable",
                "a Jacobian rebuild, alternate solver, retry, fallback, clipping, projection, controller move, or changed step size occurs",
                "provider calls reach 80000 or wall clock reaches 180 seconds",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = dd144._hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-145 Frozen Extended Post-Cache-Fix Captured-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Sole scientific change from DD-144: duration `10 s -> 20 s`",
                "- Initial state/controller move: exact DD-144",
                "- Grids: `20 x 1.0 s` and `40 x 0.5 s`",
                "- Solver: one frozen 21-color Jacobian and factorization per root",
                "- Complete immutable per-step evidence: required",
                "- Provider-call limit: `<80000`",
                "- Wall-clock limit: `<180 s`",
                "- Rebuild, alternate solver, retry, fallback, clipping, projection, or controller change: prohibited",
                "",
                "Passing may authorize only a separately frozen longer trajectory contract. Failure stops with replay-complete evidence.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def execute() -> dict[str, Any]:
    payload = dd144._load(CONTRACT)

    original = (
        dd144.CONTRACT,
        dd144.RESULT,
        dd144.RESULT_DOC,
        dd144.RESULT_SCHEMA,
    )
    dd144.CONTRACT = CONTRACT
    dd144.RESULT = RESULT
    dd144.RESULT_DOC = RESULT_DOC
    dd144.RESULT_SCHEMA = RESULT_SCHEMA
    try:
        result = dd144.execute()
    finally:
        (
            dd144.CONTRACT,
            dd144.RESULT,
            dd144.RESULT_DOC,
            dd144.RESULT_SCHEMA,
        ) = original

    result["schema_id"] = RESULT_SCHEMA
    result["source_dd144_result_sha256"] = payload["source_dd144_result_sha256"]
    result["classification"] = (
        "extended_post_cachefix_captured_trajectory_passed"
        if result["pass"]
        else "extended_post_cachefix_captured_trajectory_failed"
    )
    result["decision"] = (
        "authorize_separately_frozen_longer_captured_trajectory_contract"
        if result["pass"]
        else "stop_with_replay_complete_extended_trajectory_evidence"
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
    refinement = result["endpoint_refinement"]
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-145 Extended Post-Cache-Fix Captured-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed coarse/refined steps: `{completed.get('coarse', 0)}` / `{completed.get('refined', 0)}`",
                f"- Worst residual: `{max(residuals):.9e}`",
                f"- Endpoint refinement: `{refinement}`",
                f"- Capture gates: `{result['capture_gates']}`",
                f"- DWSIM calls: `{result['provider_provenance']['total_calls']}`",
                f"- Wall clock: `{result['wall_clock_sec']:.3f} s`",
                "",
                "The sole scientific change from DD-144 is the 20-second duration. Complete captured evidence is retained for every attempted step.",
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
