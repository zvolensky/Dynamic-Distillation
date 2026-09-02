from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "logs/core_v3_water_methanol_vtpr_dt_0p5_qualification_20260901.json"


def test_half_second_step_matches_two_quarter_second_steps():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["classification"] == "nominal_feed_dt_0p5_qualified"
    assert report["pass_gate"]
    assert report["component_specific_logic"] is False
    assert report["feed_multiplier"] == 1.0
    assert report["comparison"]["one_step_sec"] == 0.5
    assert report["comparison"]["reference_step_sec"] == 0.25
    assert report["comparison"]["reference_step_count"] == 2
    assert report["comparison"]["pass_gate"]
    assert all(report["comparison"]["gates"].values())
    assert report["half_step"]["pass_gate"]
    assert all(step["pass_gate"] for step in report["quarter_steps"])
    assert report["endpoint_jacobian"]["pass_gate"]
    assert all(item["rank"] == 98 for item in report["endpoint_jacobian"]["steps"])
    assert report["provider"]["pass_gate"]
    assert all(report["gates"].values())
    assert not report["retry_attempted"]
    assert not report["long_run_attempted"]
    assert report["decision"] == "authorize_120_second_nominal_feed_run_at_dt_0p5"
