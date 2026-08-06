#!/usr/bin/env python
"""Prepare or execute DD-159 memoized captured 60-second trajectory proof."""

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

import run_core_v3_parallel_captured_longer_trajectory as dd150


SCHEMA = "dd159-core-v3-memoized-captured-longer-trajectory-contract-v1"
RESULT_SCHEMA = "dd159-core-v3-memoized-captured-longer-trajectory-result-v1"
DD146_RESULT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_20260805.json"
)
DD150_CONTRACT = Path(
    "logs/dd150_core_v3_parallel_captured_longer_trajectory_contract_20260805.json"
)
DD150_RESULT = Path(
    "logs/dd150_core_v3_parallel_captured_longer_trajectory_20260805.json"
)
DD158_RESULT = Path(
    "logs/dd158_core_v3_memoized_captured_short_trajectory_20260806.json"
)
CONTRACT = Path(
    "logs/dd159_core_v3_memoized_captured_longer_trajectory_contract_20260806.json"
)
RESULT = Path(
    "logs/dd159_core_v3_memoized_captured_longer_trajectory_20260806.json"
)
CONTRACT_DOC = Path(
    "docs/dd_159_core_v3_memoized_captured_longer_trajectory_contract_20260806.md"
)
RESULT_DOC = Path(
    "docs/dd_159_core_v3_memoized_captured_longer_trajectory_20260806.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd150.IMPLEMENTATION,
            "tools/run_core_v3_memoized_captured_longer_trajectory.py",
            "tests/test_core_v3_memoized_captured_longer_trajectory.py",
        )
    )
)


_BASE_WORKER_INITIALIZE = dd150.dd149._worker_initialize


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
    if dd150.dd149._WORKER_CONTEXT is None:
        raise RuntimeError("DD-159 worker context was not initialized")
    dd150.dd149._WORKER_CONTEXT["auto_thermo_memoization"] = True


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
    source_contract = _load(DD150_CONTRACT)
    dd150_result = _load(DD150_RESULT)
    dd158_result = _load(DD158_RESULT)
    if (
        not dd150_result["pass"]
        or not dd158_result["pass"]
        or dd158_result["decision"]
        != "authorize_separately_frozen_longer_memoized_trajectory"
    ):
        raise RuntimeError("DD-159 requires immutable passing DD-150/DD-158 results")

    payload = {
        key: value
        for key, value in source_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "source_contract_payload_sha256",
            "source_dd146_result_sha256",
            "source_dd149_result_sha256",
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
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD146_RESULT, DD150_CONTRACT, DD150_RESULT, DD158_RESULT)
            },
            "source_contract_payload_sha256": source_contract[
                "contract_payload_sha256"
            ],
            "source_dd146_result_sha256": source_contract[
                "source_dd146_result_sha256"
            ],
            "source_dd149_result_sha256": source_contract[
                "source_dd149_result_sha256"
            ],
            "scientific_contract_changes": [],
            "administrative_contract_changes": [
                "enable DD-157 exact-state thermo memoization with one unique epoch per Jacobian"
            ],
            "parallel_trajectory": source_contract["parallel_trajectory"],
            "thermo_memoization": {
                "enabled": True,
                "epoch_source": "colored-task state prefix before :color_",
                "unique_epoch_per_jacobian": True,
                "expected_memo_roots": 180,
                "expected_memo_calls_per_root": 1176,
                "expected_memo_calls": 211680,
                "minimum_hit_fraction_each_root": 0.60,
                "trajectory_reference": "DD-150",
                "trajectory_reference_wall_sec": float(
                    dd150_result["trajectory_wall_clock_sec"]
                ),
                "trajectory_wall_ratio_vs_dd150_maximum": 0.80,
                "total_wall_limit_sec": 60.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-146/DD-150/DD-158 source or DD-159 implementation hash changes",
                "the DD-150 initial state, controller move, solver, grids, bounds, scales, tolerances, or scientific gates change",
                "more than one worker pool is created or it is not retained across all 180 roots",
                "a Jacobian lacks a unique exact-memo epoch or any root hit fraction is below 0.60",
                "any capture, solver decision, accepted state, or endpoint differs from DD-150 beyond 1e-10",
                "root, task, logical call, worker ownership, memo accounting, or wall integrity fails",
                "trajectory wall exceeds 0.80 times DD-150 or total wall reaches 60 seconds",
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
                "# DD-159 Frozen Memoized Captured 60-Second Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific case: exact DD-150/DD-146 `60 s`, `60 x 1.0 s` and `120 x 0.5 s`",
                "- Only change: production exact memoization with one unique epoch per Jacobian",
                "- Exact work: 180 roots, 7,560 tasks, 211,680 logical worker-provider calls",
                "- Equivalence: complete captures and accepted states `<=1e-10` versus DD-150",
                "- Memo accounting: 1,176 calls/root and hit fraction `>=0.60` for every root",
                "- Performance: trajectory wall `<=0.80x` DD-150; total wall `<60 s`",
                "",
                "Passing may authorize only a separately frozen five-minute memoized trajectory.",
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
        raise RuntimeError("DD-159 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-159 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-159 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-159 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    memo_contract = payload["thermo_memoization"]
    accepted = _load(DD150_RESULT)
    original = (
        dd150.CONTRACT,
        dd150.RESULT,
        dd150.CONTRACT_DOC,
        dd150.RESULT_DOC,
        dd150.RESULT_SCHEMA,
        dd150.dd149._worker_initialize,
    )
    dd150.CONTRACT = CONTRACT
    dd150.RESULT = RESULT
    dd150.CONTRACT_DOC = CONTRACT_DOC
    dd150.RESULT_DOC = RESULT_DOC
    dd150.RESULT_SCHEMA = RESULT_SCHEMA
    dd150.dd149._worker_initialize = _memo_worker_initialize
    try:
        result = dd150.execute()
    finally:
        (
            dd150.CONTRACT,
            dd150.RESULT,
            dd150.CONTRACT_DOC,
            dd150.RESULT_DOC,
            dd150.RESULT_SCHEMA,
            dd150.dd149._worker_initialize,
        ) = original

    memo = _memo_summary(result["parallel_jacobian_evidence"])
    trajectory_ratio = float(
        result["trajectory_wall_clock_sec"]
        / memo_contract["trajectory_reference_wall_sec"]
    )
    inherited_gates = dict(result["gates"])
    gates = {
        "inherited_dd150_scientific_and_equivalence_gates": bool(
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
        <= memo_contract["trajectory_wall_ratio_vs_dd150_maximum"],
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
                "memoized_captured_longer_trajectory_equivalent"
                if passed
                else "memoized_captured_longer_trajectory_failed"
            ),
            "decision": (
                "authorize_separately_frozen_five_minute_memoized_trajectory"
                if passed
                else "retain_validated_memoized_short_trajectory_only"
            ),
            "source_dd150_gates": inherited_gates,
            "thermo_memoization": memo,
            "trajectory_wall_ratio_vs_dd150": trajectory_ratio,
            "gates": gates,
            "pass": bool(passed),
            "campaign_executed_once": True,
        }
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-159 Memoized Captured 60-Second Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed coarse/refined roots: `{len(result['trajectories']['coarse'])}` / `{len(result['trajectories']['refined'])}`",
                f"- Memo hits/misses: `{memo['hits']}` / `{memo['misses']}` (`{memo['hit_fraction']:.4%}` hits)",
                f"- Minimum per-root hit fraction: `{memo['minimum_root_hit_fraction']:.4%}`",
                f"- Trajectory wall: `{result['trajectory_wall_clock_sec']:.6f} s`",
                f"- DD-150 trajectory ratio: `{trajectory_ratio:.6f}`",
                f"- Total wall: `{result['total_wall_clock_sec']:.6f} s`",
                f"- Capture differences: `{result['capture_differences']}`",
                f"- Trajectory differences: `{result['trajectory_differences']}`",
                f"- Gates: `{gates}`",
                "",
                "The only scientific-path change is one exact memo epoch per colored Jacobian. The complete 60-second trajectory is compared against DD-150.",
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
