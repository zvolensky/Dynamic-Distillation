from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT / "logs/core_v3_water_methanol_vtpr_feed_pulse_trajectory_20260831.json"
)


def test_feed_pulse_trajectory_passes_and_restores_nominal_feed():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["classification"] == "fixed_product_feed_pulse_restored_passed"
    assert report["pass_gate"]
    assert report["component_specific_logic"] is False
    assert report["handoff_mode"] == "fixed_terminal_products"
    assert report["condenser_duty_mode"] == "solved_column_variable"
    assert report["timestep_sec"] == 0.25
    assert report["pulse"]["feed_multiplier"] == 1.001
    assert report["pulse"]["duration_sec"] == 1.0
    assert not report["pulse"]["composition_changed"]
    assert not report["pulse"]["specific_enthalpy_changed"]
    assert report["step_count_completed"] == report["step_count_requested"] == 5
    assert [step["feed_multiplier"] for step in report["steps"]] == [
        1.001,
        1.001,
        1.001,
        1.001,
        1.0,
    ]
    assert all(step["pass_gate"] for step in report["steps"])
    assert all(step["scaled_residual_inf_norm"] < 1.0e-8 for step in report["steps"])
    assert all(
        step["component_identity_error_lbmol"] < 1.0e-6
        for step in report["steps"]
    )
    assert all(
        step["energy_identity_relative_error"] < 1.0e-8
        or step["energy_identity_absolute_error_BTU"] < 1.0e-5
        for step in report["steps"]
    )
    assert report["restoration"]["feed_multiplier"] == 1.0
    assert report["restoration"]["restored_before_final_step"]
    assert not report["restoration"]["disturbance_active_at_end"]
    assert report["feed_disturbance_removed"]
    assert report["endpoint_jacobian"]["pass_gate"]
    assert all(item["rank"] == 98 for item in report["endpoint_jacobian"]["steps"])
    assert report["provider"]["pass_gate"]
    assert all(report["gates"].values())
    assert not report["retry_attempted"]
    assert not report["adaptive_timestep_used"]
    assert report["decision"] == "feed_pulse_experiment_complete_nominal_feed_restored"
