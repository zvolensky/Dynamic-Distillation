#!/usr/bin/env python
"""Prepare or execute DD-158 memoized captured 10-second trajectory proof."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_parallel_captured_short_trajectory as dd149


SCHEMA = "dd158-core-v3-memoized-captured-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd158-core-v3-memoized-captured-short-trajectory-result-v1"
DD144_RESULT = Path("logs/dd144_core_v3_post_cachefix_captured_short_trajectory_20260805.json")
DD149_CONTRACT = Path("logs/dd149_core_v3_parallel_captured_short_trajectory_contract_20260805.json")
DD149_RESULT = Path("logs/dd149_core_v3_parallel_captured_short_trajectory_20260805.json")
DD157_RESULT = Path("logs/dd157_core_v3_production_exact_memoization_20260806.json")
CONTRACT = Path("logs/dd158_core_v3_memoized_captured_short_trajectory_contract_20260806.json")
RESULT = Path("logs/dd158_core_v3_memoized_captured_short_trajectory_20260806.json")
CONTRACT_DOC = Path("docs/dd_158_core_v3_memoized_captured_short_trajectory_contract_20260806.md")
RESULT_DOC = Path("docs/dd_158_core_v3_memoized_captured_short_trajectory_20260806.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/thermo_provider_v1.py",
    "tests/test_core_v3_memoized_captured_short_trajectory.py",
    "tools/run_core_v3_memoized_captured_short_trajectory.py",
    "tools/run_core_v3_parallel_captured_short_trajectory.py",
)


_BASE_WORKER_INITIALIZE = dd149._worker_initialize


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


def _memo_worker_initialize(contract_path: str) -> None:
    _BASE_WORKER_INITIALIZE(str(contract_path))
    if dd149._WORKER_CONTEXT is None:
        raise RuntimeError("DD-158 worker context was not initialized")
    dd149._WORKER_CONTEXT["auto_thermo_memoization"] = True


def _memo_summary(evidence: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    per_root = []
    for item in evidence:
        hits = int(item.get("thermo_memo_hits", 0))
        misses = int(item.get("thermo_memo_misses", 0))
        calls = hits + misses
        per_root.append(
            {
                "state_id": str(item["state_id"]),
                "hits": hits,
                "misses": misses,
                "calls": calls,
                "hit_fraction": float(hits / calls) if calls else 0.0,
            }
        )
    hits = sum(item["hits"] for item in per_root)
    misses = sum(item["misses"] for item in per_root)
    return {
        "per_root": per_root,
        "hits": int(hits),
        "misses": int(misses),
        "calls": int(hits + misses),
        "hit_fraction": float(hits / (hits + misses)) if hits + misses else 0.0,
        "minimum_root_hit_fraction": float(
            min(item["hit_fraction"] for item in per_root)
        ) if per_root else 0.0,
    }


def prepare() -> dict[str, Any]:
    source_contract = _load(DD149_CONTRACT)
    dd149_result = _load(DD149_RESULT)
    dd157_result = _load(DD157_RESULT)
    if (
        not dd149_result["pass"]
        or not dd157_result["pass"]
        or dd157_result["decision"]
        != "authorize_separately_frozen_short_trajectory_memoization_proof"
    ):
        raise RuntimeError("DD-158 requires immutable passing DD-149/DD-157 results")
    payload = {
        key: value
        for key, value in source_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
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
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD144_RESULT, DD149_CONTRACT, DD149_RESULT, DD157_RESULT)
            },
            "thermo_memoization": {
                "enabled": True,
                "epoch_source": "colored-task state prefix before :color_",
                "unique_epoch_per_jacobian": True,
                "expected_memo_roots": 30,
                "expected_memo_calls_per_root": 1176,
                "expected_memo_calls": 35280,
                "minimum_hit_fraction_each_root": 0.60,
                "trajectory_wall_ratio_vs_dd149_maximum": 0.75,
                "total_wall_limit_sec": 30.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-144/DD-149/DD-157 result, source, or DD-158 implementation hash changes",
                "the DD-149 initial state, controller move, solver, grids, bounds, scales, tolerances, or scientific gates change",
                "a Jacobian lacks a unique exact-memo epoch or any root hit fraction is below 0.60",
                "any capture, solver decision, accepted state, or endpoint differs from DD-149 beyond 1e-10",
                "root, task, logical call, worker ownership, memo accounting, or wall integrity fails",
                "a rebuild, retry, fallback, clipping, projection, controller change, or grid change occurs",
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
                "# DD-158 Frozen Memoized Captured Short-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific case: exact DD-149/DD-144 `10 s`, `10 x 1.0 s` and `20 x 0.5 s`",
                "- Only change: production exact memoization with one unique epoch per Jacobian",
                "- Exact work: 30 roots, 1,260 tasks, 35,280 logical worker-provider calls",
                "- Equivalence: complete captures and accepted states `<=1e-10` versus DD-149",
                "- Memo accounting: 1,176 calls/root and hit fraction `>=0.60` for every root",
                "- Performance: trajectory wall `<=0.75x` DD-149; total wall `<30 s`",
                "",
                "Passing may authorize only a separately frozen longer memoized trajectory. Multi-minute operation remains unauthorized.",
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
        raise RuntimeError("DD-158 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-158 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-158 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-158 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    memo_contract = payload["thermo_memoization"]
    accepted = _load(DD149_RESULT)
    original = (
        dd149.CONTRACT,
        dd149.RESULT,
        dd149.RESULT_DOC,
        dd149.RESULT_SCHEMA,
        dd149._worker_initialize,
    )
    dd149.CONTRACT = CONTRACT
    dd149.RESULT = RESULT
    dd149.RESULT_DOC = RESULT_DOC
    dd149.RESULT_SCHEMA = RESULT_SCHEMA
    dd149._worker_initialize = _memo_worker_initialize
    try:
        result = dd149.execute()
    finally:
        (
            dd149.CONTRACT,
            dd149.RESULT,
            dd149.RESULT_DOC,
            dd149.RESULT_SCHEMA,
            dd149._worker_initialize,
        ) = original

    memo = _memo_summary(result["parallel_jacobian_evidence"])
    trajectory_ratio = float(
        result["trajectory_wall_clock_sec"] / accepted["trajectory_wall_clock_sec"]
    )
    inherited_gates = dict(result["gates"])
    gates = {
        "inherited_dd149_scientific_and_equivalence_gates": bool(
            result["pass"] and all(inherited_gates.values())
        ),
        "exact_memo_root_and_call_accounting": len(memo["per_root"])
        == memo_contract["expected_memo_roots"]
        and memo["calls"] == memo_contract["expected_memo_calls"]
        and all(
            item["calls"] == memo_contract["expected_memo_calls_per_root"]
            for item in memo["per_root"]
        ),
        "memo_hit_fraction_each_root": memo["minimum_root_hit_fraction"]
        >= memo_contract["minimum_hit_fraction_each_root"],
        "trajectory_wall_improvement": trajectory_ratio
        <= memo_contract["trajectory_wall_ratio_vs_dd149_maximum"],
        "total_wall": result["total_wall_clock_sec"]
        < memo_contract["total_wall_limit_sec"],
        "no_rebuild_retry_fallback_or_grid_change": bool(
            not result["jacobian_rebuild_attempted"]
            and not result["fallback_attempted"]
            and not result["retry_attempted"]
            and not result["grid_changed"]
        ),
    }
    passed = all(gates.values())
    result.update(
        {
            "schema_id": RESULT_SCHEMA,
            "classification": (
                "memoized_captured_short_trajectory_equivalent"
                if passed
                else "memoized_captured_short_trajectory_failed"
            ),
            "decision": (
                "authorize_separately_frozen_longer_memoized_trajectory"
                if passed
                else "disable_trajectory_memoization"
            ),
            "source_dd149_gates": inherited_gates,
            "thermo_memoization": memo,
            "trajectory_wall_ratio_vs_dd149": trajectory_ratio,
            "gates": gates,
            "pass": bool(passed),
            "campaign_executed_once": True,
        }
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-158 Memoized Captured Short-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Memo accounting: `{memo}`",
                f"- Trajectory wall: `{result['trajectory_wall_clock_sec']:.6f} s`",
                f"- DD-149 trajectory ratio: `{trajectory_ratio:.6f}`",
                f"- Total wall: `{result['total_wall_clock_sec']:.6f} s`",
                f"- Capture differences: `{result['capture_differences']}`",
                f"- Trajectory differences: `{result['trajectory_differences']}`",
                f"- Gates: `{gates}`",
                "",
                "The only scientific-path change is one exact memo epoch per colored Jacobian. Complete captures and accepted trajectories are compared against DD-149.",
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
                    "trajectory_wall_clock_sec",
                    "total_wall_clock_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
