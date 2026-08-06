from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_multiminute_timing as dd152


def test_timing_windows_and_trend_detect_growth():
    values = [0.1] * 4 + [0.2] * 4 + [0.4] * 4
    windows = dd152._window_summaries(values, 4)
    trend = dd152._trend(values)
    assert [item["mean_sec"] for item in windows] == pytest.approx([0.1, 0.2, 0.4])
    assert windows[-1]["mean_sec"] / windows[0]["mean_sec"] == pytest.approx(4.0)
    assert trend["slope_sec_per_root"] > 0.0
    assert trend["pearson_root_order"] > 0.8


def test_timing_windows_reject_partial_window():
    with pytest.raises(ValueError, match="complete windows"):
        dd152._window_summaries([0.1] * 5, 4)


def test_decomposition_telescopes_saved_timing():
    result = {
        "parallel_jacobian_evidence": [
            {"wall_clock_sec": 1.0},
            {"wall_clock_sec": 2.0},
        ],
        "trajectory_wall_clock_sec": 5.0,
        "total_wall_clock_sec": 7.0,
    }
    out = dd152._decomposition(result)
    assert out["jacobian_sec"] == 3.0
    assert out["trajectory_non_jacobian_sec"] == 2.0
    assert out["outside_trajectory_sec"] == 2.0
    assert out["total_sec"] == 7.0


def test_summary_reports_expected_statistics():
    out = dd152._summary([1.0, 2.0, 3.0, 4.0])
    assert out["count"] == 4
    assert out["sum_sec"] == 10.0
    assert out["mean_sec"] == 2.5
    assert out["median_sec"] == 2.5
    assert np.isfinite(out["p95_sec"])
