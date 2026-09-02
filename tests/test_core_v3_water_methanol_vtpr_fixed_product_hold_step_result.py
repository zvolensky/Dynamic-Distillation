from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT
    / "logs/core_v3_water_methanol_vtpr_fixed_product_hold_step_20260831.json"
)


def test_first_fixed_product_hold_step_is_motionless_and_accepted():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["classification"] == "fixed_product_stationary_hold_step_passed"
    assert report["pass_gate"]
    assert report["component_specific_logic"] is False
    assert report["handoff_mode"] == "fixed_terminal_products"
    assert report["timestep_sec"] == 0.25
    assert report["solver"]["success"]
    assert report["scaled_residual_inf_norm"] < 1.0e-8
    assert report["maximum_coordinate_movement"] < 1.0e-8
    assert report["maximum_inventory_rate_lbmolph"] < 1.0e-5
    assert report["component_inventory_identity_error_lbmol"] < 1.0e-8
    assert report["energy_inventory_identity_error_BTU"] < 1.0e-5
    assert report["physical_pass"]
    assert report["endpoint_jacobian"]["pass_gate"]
    assert all(item["rank"] == 98 for item in report["endpoint_jacobian"]["steps"])
    assert all(report["gates"].values())
    assert report["provider"]["pass_gate"]
    assert not report["retry_attempted"]
    assert not report["disturbance_applied"]
    assert report["timestep_accepted"]
    assert not report["dynamic_trajectory_attempted"]
    assert report["decision"] == "authorize_separately_bounded_small_disturbance_step"
