#!/usr/bin/env python
"""Prepare or execute DD-160 memoized captured five-minute trajectory proof."""

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

import run_core_v3_parallel_captured_multiminute_trajectory as dd151


SCHEMA = "dd160-core-v3-memoized-captured-multiminute-trajectory-contract-v1"
RESULT_SCHEMA = "dd160-core-v3-memoized-captured-multiminute-trajectory-result-v1"
DD146_RESULT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_20260805.json"
)
DD151_CONTRACT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_contract_20260805.json"
)
DD151_RESULT = Path(
    "logs/dd151_core_v3_parallel_captured_multiminute_trajectory_20260805.json"
)
DD159_RESULT = Path(
    "logs/dd159_core_v3_memoized_captured_longer_trajectory_20260806.json"
)
CONTRACT = Path(
    "logs/dd160_core_v3_memoized_captured_multiminute_trajectory_contract_20260806.json"
)
RESULT = Path(
    "logs/dd160_core_v3_memoized_captured_multiminute_trajectory_20260806.json"
)
CONTRACT_DOC = Path(
    "docs/dd_160_core_v3_memoized_captured_multiminute_trajectory_contract_20260806.md"
)
RESULT_DOC = Path(
    "docs/dd_160_core_v3_memoized_captured_multiminute_trajectory_20260806.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd151.IMPLEMENTATION,
            "tools/run_core_v3_memoized_captured_multiminute_trajectory.py",
            "tests/test_core_v3_memoized_captured_multiminute_trajectory.py",
        )
    )
)


_BASE_WORKER_INITIALIZE = dd151.dd149._worker_initialize
_BASE_COMPACT_PARALLEL_RECORD = dd151.dd149._compact_parallel_record


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
    if dd151.dd149._WORKER_CONTEXT is None:
        raise RuntimeError("DD-160 worker context was not initialized")
    dd151.dd149._WORKER_CONTEXT["auto_thermo_memoization"] = True


def _memo_compact_parallel_record(item: Mapping[str, Any]) -> dict[str, Any]:
    record = _BASE_COMPACT_PARALLEL_RECORD(item)
    record["thermo_memo_hits"] = int(item.get("thermo_memo_hits", 0))
    record["thermo_memo_misses"] = int(item.get("thermo_memo_misses", 0))
    return record


def _memo_compact_capture_record(item: Mapping[str, Any]) -> dict[str, Any]:
    capture = item["capture"]
    final_residual = [float(value) for value in capture["final_residual"]]
    return {
        "index": int(item["index"]),
        "time_seconds": float(item["time_seconds"]),
        "capture_sha256": _hash(item),
        "success": bool(capture["success"]),
        "iterations": int(capture["iterations"]),
        "residual_evaluations": int(capture["residual_evaluations"]),
        "jacobian_evaluations": int(capture["jacobian_evaluations"]),
        "linear_solves": int(capture["linear_solves"]),
        "rejected_line_search_steps": int(capture["rejected_line_search_steps"]),
        "rejected_bound_steps": int(capture["rejected_bound_steps"]),
        "final_residual_inf_norm": max(map(abs, final_residual), default=0.0),
        "jacobian_rank": int(capture["jacobian_rank"]),
        "jacobian_condition": float(capture["jacobian_condition"]),
        "residual_identity_max_abs": float(
            capture["final_residual_vs_evaluation_max_abs"]
        ),
        "all_capture_arrays_read_only": bool(
            capture["all_capture_arrays_read_only"]
        ),
    }


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


def _compare_complete_replay(
    result: Mapping[str, Any], reference: Mapping[str, Any]
) -> dict[str, Any]:
    trajectory_differences = {}
    trajectory_metadata = {}
    capture_differences = {}
    capture_metadata = {}
    for name in ("coarse", "refined"):
        difference, metadata_equal = dd151.dd149._compare(
            result["trajectories"][name], reference["trajectories"][name]
        )
        trajectory_differences[name] = float(difference)
        trajectory_metadata[name] = bool(metadata_equal)

        capture_name = f"dd134:{name}"
        expected = [
            _memo_compact_capture_record(item)
            for item in reference["captured_trajectory_evidence"][capture_name]
        ]
        difference, metadata_equal = dd151.dd149._compare(
            result["captured_trajectory_evidence"][capture_name], expected
        )
        capture_differences[capture_name] = float(difference)
        capture_metadata[capture_name] = bool(metadata_equal)
    return {
        "trajectory_differences": trajectory_differences,
        "trajectory_metadata_equal": trajectory_metadata,
        "capture_differences": capture_differences,
        "capture_metadata_equal": capture_metadata,
        "all_equal": bool(
            max(trajectory_differences.values()) == 0.0
            and all(trajectory_metadata.values())
            and max(capture_differences.values()) == 0.0
            and all(capture_metadata.values())
        ),
    }


def prepare() -> dict[str, Any]:
    source_contract = _load(DD151_CONTRACT)
    dd151_result = _load(DD151_RESULT)
    dd159_result = _load(DD159_RESULT)
    dd151_failed = {key for key, value in dd151_result["gates"].items() if not value}
    if (
        dd151_failed
        != {
            "source_scientific_gates",
            "meaningful_total_wall_improvement",
            "absolute_wall",
        }
        or len(dd151_result["trajectories"]["coarse"]) != 300
        or len(dd151_result["trajectories"]["refined"]) != 600
        or not dd159_result["pass"]
        or dd159_result["decision"]
        != "authorize_separately_frozen_five_minute_memoized_trajectory"
    ):
        raise RuntimeError(
            "DD-160 requires DD-151's complete scientific replay and passing DD-159"
        )

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
            "source_dd150_result_sha256",
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
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (
                    DD146_RESULT,
                    DD151_CONTRACT,
                    DD151_RESULT,
                    DD159_RESULT,
                )
            },
            "source_contract_payload_sha256": source_contract[
                "contract_payload_sha256"
            ],
            "source_dd146_result_sha256": source_contract[
                "source_dd146_result_sha256"
            ],
            "source_dd150_result_sha256": source_contract[
                "source_dd150_result_sha256"
            ],
            "scientific_contract_changes": [],
            "administrative_contract_changes": [
                "enable DD-157 exact-state thermo memoization with one unique epoch per Jacobian",
                "retain memo hit and miss counts in compact successful parallel evidence",
                "add exact complete-capture and accepted-state comparison against DD-151",
            ],
            "thermo_memoization": {
                "enabled": True,
                "epoch_source": "colored-task state prefix before :color_",
                "unique_epoch_per_jacobian": True,
                "expected_memo_roots": 900,
                "expected_memo_calls_per_root": 1176,
                "expected_memo_calls": 1058400,
                "expected_memo_hits": 736200,
                "expected_delegate_calls": 322200,
                "minimum_hit_fraction_each_root": 0.60,
                "trajectory_reference": "DD-151",
                "trajectory_reference_wall_sec": float(
                    dd151_result["trajectory_wall_clock_sec"]
                ),
                "total_reference_wall_sec": float(
                    dd151_result["total_wall_clock_sec"]
                ),
                "trajectory_wall_ratio_vs_dd151_maximum": 0.60,
                "total_wall_limit_sec": 300.0,
            },
            "complete_replay_equivalence_absolute_limit": 0.0,
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-146/DD-151/DD-159 source or DD-160 implementation hash changes",
                "the DD-151 initial state, controller move, solver, grids, bounds, scales, tolerances, or scientific gates change",
                "more than one worker pool is created or it is not retained across all 900 roots",
                "a Jacobian lacks a unique exact-memo epoch or any root hit fraction is below 0.60",
                "any complete capture, solver decision, accepted state, or endpoint differs from DD-151",
                "root, task, logical call, worker ownership, memo accounting, compact evidence, or wall integrity fails",
                "trajectory wall exceeds 0.60 times DD-151 or total governed wall reaches 300 seconds",
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
                "# DD-160 Frozen Memoized Captured Five-Minute Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific case: exact DD-151 `300 s`, `300 x 1.0 s` and `600 x 0.5 s`",
                "- Only runtime change: production exact memoization with one unique epoch per Jacobian",
                "- Exact work: 900 roots, 37,800 tasks, 1,058,400 logical worker-provider calls",
                "- Complete replay: every accepted state and full capture digest must equal DD-151 exactly",
                "- Memo accounting: 1,176 calls/root and hit fraction `>=0.60` for every root",
                "- Performance: trajectory wall `<=0.60x` DD-151; governed total wall `<300 s`",
                "- Rebuild, retry, fallback, clipping, projection, controller change, or grid change: prohibited",
                "",
                "Passing establishes the first accepted five-minute Core V3 controlled trajectory. No longer run is authorized.",
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
        raise RuntimeError("DD-160 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-160 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-160 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-160 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    memo_contract = payload["thermo_memoization"]
    reference = _load(DD151_RESULT)
    original = (
        dd151.CONTRACT,
        dd151.RESULT,
        dd151.CONTRACT_DOC,
        dd151.RESULT_DOC,
        dd151.RESULT_SCHEMA,
        dd151.dd149._worker_initialize,
        dd151.dd149._compact_capture_record,
        dd151.dd149._compact_parallel_record,
    )
    dd151.CONTRACT = CONTRACT
    dd151.RESULT = RESULT
    dd151.CONTRACT_DOC = CONTRACT_DOC
    dd151.RESULT_DOC = RESULT_DOC
    dd151.RESULT_SCHEMA = RESULT_SCHEMA
    dd151.dd149._worker_initialize = _memo_worker_initialize
    dd151.dd149._compact_capture_record = _memo_compact_capture_record
    dd151.dd149._compact_parallel_record = _memo_compact_parallel_record
    try:
        result = dd151.execute()
    finally:
        (
            dd151.CONTRACT,
            dd151.RESULT,
            dd151.CONTRACT_DOC,
            dd151.RESULT_DOC,
            dd151.RESULT_SCHEMA,
            dd151.dd149._worker_initialize,
            dd151.dd149._compact_capture_record,
            dd151.dd149._compact_parallel_record,
        ) = original

    memo = _memo_summary(result["parallel_jacobian_evidence"])
    replay = _compare_complete_replay(result, reference)
    trajectory_ratio = float(
        result["trajectory_wall_clock_sec"]
        / memo_contract["trajectory_reference_wall_sec"]
    )
    total_ratio = float(
        result["total_wall_clock_sec"] / memo_contract["total_reference_wall_sec"]
    )
    inherited_gates = dict(result["gates"])
    gates = {
        "inherited_dd151_scientific_and_execution_gates": bool(
            result["pass"] and all(inherited_gates.values())
        ),
        "complete_dd151_replay_exact": replay["all_equal"],
        "compact_success_evidence": result["capture_storage"]
        == "compact_sha256_per_root"
        and not result["full_capture_retained_on_failure"],
        "exact_memo_root_and_call_accounting": len(memo["per_root"])
        == memo_contract["expected_memo_roots"]
        and memo["calls"] == memo_contract["expected_memo_calls"]
        and memo["hits"] == memo_contract["expected_memo_hits"]
        and memo["misses"] == memo_contract["expected_delegate_calls"]
        and all(
            item["calls"] == memo_contract["expected_memo_calls_per_root"]
            for item in memo["per_root"]
        ),
        "memo_hit_fraction_each_root": memo["minimum_root_hit_fraction"]
        >= memo_contract["minimum_hit_fraction_each_root"],
        "trajectory_wall_improvement": trajectory_ratio
        <= memo_contract["trajectory_wall_ratio_vs_dd151_maximum"],
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
                "memoized_captured_five_minute_trajectory_passed"
                if passed
                else "memoized_captured_five_minute_trajectory_failed"
            ),
            "decision": (
                "five_minute_memoized_controlled_trajectory_established"
                if passed
                else "stop_with_frozen_dd160_evidence"
            ),
            "source_dd151_gates": inherited_gates,
            "complete_dd151_replay": replay,
            "thermo_memoization": memo,
            "trajectory_wall_ratio_vs_dd151": trajectory_ratio,
            "total_wall_ratio_vs_dd151": total_ratio,
            "gates": gates,
            "pass": bool(passed),
            "campaign_executed_once": True,
        }
    )
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-160 Memoized Captured Five-Minute Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed coarse/refined roots: `{len(result['trajectories']['coarse'])}` / `{len(result['trajectories']['refined'])}`",
                f"- Complete DD-151 replay: `{replay}`",
                f"- Memo hits/misses: `{memo['hits']}` / `{memo['misses']}` (`{memo['hit_fraction']:.4%}` hits)",
                f"- Minimum per-root hit fraction: `{memo['minimum_root_hit_fraction']:.4%}`",
                f"- Trajectory wall: `{result['trajectory_wall_clock_sec']:.6f} s` (`{trajectory_ratio:.6f}x` DD-151)",
                f"- Governed total wall: `{result['total_wall_clock_sec']:.6f} s` (`{total_ratio:.6f}x` DD-151)",
                f"- Endpoint refinement: `{result['endpoint_refinement']}`",
                f"- Gates: `{gates}`",
                "",
                "The only runtime-path change from DD-151 is exact thermo memoization. All 900 accepted states and full capture digests are compared against DD-151.",
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
