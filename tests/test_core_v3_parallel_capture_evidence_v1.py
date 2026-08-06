from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_parallel_captured_short_trajectory as dd149


def _capture(index):
    return {
        "index": index,
        "time_seconds": float(index),
        "capture": {
            "success": True,
            "iterations": 1,
            "residual_evaluations": 2,
            "jacobian_evaluations": 1,
            "linear_solves": 1,
            "rejected_line_search_steps": 0,
            "rejected_bound_steps": 0,
            "final_residual_inf_norm": 1.0e-11,
            "jacobian_rank": 50,
            "jacobian_condition": 2.0e5,
            "final_residual_vs_evaluation_max_abs": 0.0,
            "all_capture_arrays_read_only": True,
            "large_array": [float(index), 2.0],
        },
    }


def test_reference_pair_selects_frozen_prefix_without_accepting_short_input():
    actual = [_capture(index) for index in range(1, 6)]
    reference = [_capture(index) for index in range(1, 4)]
    left, right = dd149._reference_pair(actual, reference, prefix_count=3)
    assert left == right
    assert len(left) == 3
    with pytest.raises(ValueError, match="outside"):
        dd149._reference_pair(actual, reference, prefix_count=4)


def test_compact_capture_record_is_deterministic_and_omits_large_arrays():
    item = _capture(2)
    first = dd149._compact_capture_record(item)
    second = dd149._compact_capture_record(item)
    assert first == second
    assert len(first["capture_sha256"]) == 64
    assert "large_array" not in first
    assert first["residual_identity_max_abs"] == 0.0
    changed = _capture(2)
    changed["capture"]["large_array"][0] += 1.0
    assert (
        dd149._compact_capture_record(changed)["capture_sha256"]
        != first["capture_sha256"]
    )


def test_compact_parallel_record_retains_exact_call_audit_digest():
    record = dd149._compact_parallel_record(
        {
            "state_id": "root:1",
            "step_seconds": 1.0,
            "wall_clock_sec": 0.2,
            "color_count": 21,
            "task_count": 42,
            "task_process_ids": [1, 2, 3, 4],
            "provider_calls": 1176,
            "per_task_provider_calls": [28] * 42,
        }
    )
    assert record["provider_calls"] == 1176
    assert record["per_task_provider_calls_min"] == 28
    assert record["per_task_provider_calls_max"] == 28
    assert len(record["per_task_provider_calls_sha256"]) == 64
