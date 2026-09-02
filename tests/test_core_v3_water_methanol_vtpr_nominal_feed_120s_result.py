from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_20260901.json"
EVIDENCE = ROOT / "logs/core_v3_water_methanol_vtpr_nominal_feed_120s_20260901.npz"


def test_nominal_feed_120_second_trajectory_is_complete_and_accepted():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["classification"] == "nominal_feed_120s_trajectory_passed"
    assert report["pass_gate"]
    assert report["component_specific_logic"] is False
    assert report["feed_multiplier"] == 1.0
    assert report["disturbance_active"] is False
    assert report["timestep_sec"] == 0.5
    assert report["duration_completed_sec"] == report["duration_requested_sec"] == 120.0
    assert report["step_count_completed"] == report["step_count_requested"] == 240
    assert all(step["pass_gate"] for step in report["steps"])
    assert all(step["feed_multiplier"] == 1.0 for step in report["steps"])
    assert all(not step["disturbance_active"] for step in report["steps"])
    assert report["global_conservation"]["component_identity_error_lbmol"] < 1.0e-6
    assert (
        report["global_conservation"]["energy_identity_absolute_error_BTU"]
        < 1.0e-4
    )
    assert report["endpoint_jacobian"]["pass_gate"]
    assert all(item["rank"] == 98 for item in report["endpoint_jacobian"]["steps"])
    assert report["provider"]["pass_gate"]
    assert all(report["gates"].values())
    assert not report["retry_attempted"]
    assert not report["adaptive_timestep_used"]
    assert report["feed_disturbance_removed"]
    assert report["decision"] == "accept_120_second_nominal_feed_recovery_trajectory"
    end = report["end_of_run"]
    assert end["duties"]["condenser_BTUph"] < 0.0
    assert end["duties"]["reboiler_BTUph"] > 0.0
    assert end["products"]["distillate"]["flow_lbmolph"] > 0.0
    assert end["products"]["bottoms"]["flow_lbmolph"] > 0.0
    assert 0.0 < end["terminal_levels"]["distillate_drum_fraction"] < 1.0
    assert 0.0 < end["terminal_levels"]["bottom_drum_fraction"] < 1.0
    assert end["steady_state"]["score"] <= 1.0
    assert end["steady_state"]["steady"]
    assert len(end["profiles"]) == 10

    with np.load(EVIDENCE) as evidence:
        assert evidence["time_sec"].shape == (241,)
        assert evidence["time_sec"][-1] == 120.0
        assert np.all(evidence["feed_multiplier"] == 1.0)
