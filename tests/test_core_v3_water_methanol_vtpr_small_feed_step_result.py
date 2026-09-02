from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "logs/core_v3_water_methanol_vtpr_small_feed_step_20260831.json"


def test_small_uniform_feed_step_is_bounded_conservative_and_accepted():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["classification"] == "fixed_product_small_feed_step_passed"
    assert report["pass_gate"]
    assert report["component_specific_logic"] is False
    assert report["handoff_mode"] == "fixed_terminal_products"
    assert report["timestep_sec"] == 0.25
    assert report["disturbance"]["kind"] == "uniform_feed_rate_multiplier"
    assert report["disturbance"]["feed_multiplier"] == 1.001
    assert report["disturbance"]["feed_composition_max_change"] < 1.0e-14
    assert (
        report["disturbance"]["feed_specific_enthalpy_change_BTU_per_lbmol"]
        < 1.0e-10
    )
    assert report["disturbance"]["terminal_product_flows_fixed"]
    assert report["disturbance"]["condenser_duty_mode"] == "solved_column_variable"
    assert report["solver"]["success"]
    assert report["scaled_residual_inf_norm"] < 1.0e-8
    assert report["maximum_coordinate_movement"] > 1.0e-12
    assert report["total_component_change_lbmol"] > 0.0
    assert report["expected_total_component_change_lbmol"] > 0.0
    assert report["component_inventory_identity_error_lbmol"] < 1.0e-6
    assert report["energy_inventory_identity_relative_error"] < 1.0e-8
    assert report["physical_pass"]
    assert report["minimum_bound_distance"] > 1.0e-6
    assert report["endpoint_jacobian"]["pass_gate"]
    assert all(item["rank"] == 98 for item in report["endpoint_jacobian"]["steps"])
    assert all(report["gates"].values())
    assert report["provider"]["pass_gate"]
    assert not report["retry_attempted"]
    assert report["disturbance_applied"]
    assert report["timestep_accepted"]
    assert not report["dynamic_trajectory_attempted"]
    assert (
        report["decision"]
        == "authorize_separately_bounded_short_fixed_product_trajectory"
    )
