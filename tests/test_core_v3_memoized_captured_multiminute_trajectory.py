from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_memoized_captured_multiminute_trajectory as dd160


def test_compact_parallel_record_retains_memo_accounting():
    item = {
        "state_id": "coarse:1",
        "step_seconds": 1.0,
        "wall_clock_sec": 0.25,
        "color_count": 42,
        "task_count": 42,
        "task_process_ids": [1, 2, 3, 4],
        "provider_calls": 1176,
        "per_task_provider_calls": [28] * 42,
        "thermo_memo_hits": 818,
        "thermo_memo_misses": 358,
    }
    record = dd160._memo_compact_parallel_record(item)
    assert record["thermo_memo_hits"] == 818
    assert record["thermo_memo_misses"] == 358


def test_memo_summary_tracks_five_minute_accounting():
    summary = dd160._memo_summary(
        [
            {"state_id": "a", "thermo_memo_hits": 818, "thermo_memo_misses": 358},
            {"state_id": "b", "thermo_memo_hits": 818, "thermo_memo_misses": 358},
        ]
    )
    assert summary["hits"] == 1636
    assert summary["misses"] == 716
    assert summary["calls"] == 2352
    assert summary["minimum_root_hit_fraction"] == 818 / 1176


def test_compact_capture_record_derives_final_residual_norm():
    item = {
        "index": 1,
        "time_seconds": 1.0,
        "capture": {
            "success": True,
            "iterations": 2,
            "residual_evaluations": 3,
            "jacobian_evaluations": 1,
            "linear_solves": 2,
            "rejected_line_search_steps": 0,
            "rejected_bound_steps": 0,
            "final_residual": [-1.0e-10, 2.0e-10],
            "jacobian_rank": 50,
            "jacobian_condition": 2.0e5,
            "final_residual_vs_evaluation_max_abs": 0.0,
            "all_capture_arrays_read_only": True,
        },
    }
    record = dd160._memo_compact_capture_record(item)
    assert record["final_residual_inf_norm"] == 2.0e-10


def test_complete_replay_comparison_accepts_compacted_reference(monkeypatch):
    capture = {"index": 1, "time_seconds": 1.0, "capture": {"value": 2.0}}
    compact = {"index": 1, "time_seconds": 1.0, "capture_sha256": "same"}
    monkeypatch.setattr(dd160, "_memo_compact_capture_record", lambda item: compact)
    trajectory = [{"index": 1, "value": 3.0}]
    result = {
        "trajectories": {"coarse": trajectory, "refined": trajectory},
        "captured_trajectory_evidence": {
            "dd134:coarse": [compact],
            "dd134:refined": [compact],
        },
    }
    reference = {
        "trajectories": {"coarse": trajectory, "refined": trajectory},
        "captured_trajectory_evidence": {
            "dd134:coarse": [capture],
            "dd134:refined": [capture],
        },
    }
    comparison = dd160._compare_complete_replay(result, reference)
    assert comparison["all_equal"] is True
