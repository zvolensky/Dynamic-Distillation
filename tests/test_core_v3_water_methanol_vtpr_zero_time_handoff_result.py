from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "logs/core_v3_water_methanol_vtpr_zero_time_handoff_20260831.json"


def test_fixed_product_zero_time_handoff_is_exact_and_step_stable():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["classification"] == "fixed_product_zero_time_dynamic_handoff_passed"
    assert report["pass_gate"]
    assert report["handoff_mode"] == "fixed_terminal_products"
    assert not report["controller_mode_selected"]
    assert not report["component_specific_logic"]
    assert report["scaled_residual_inf_norm"] < 1.0e-8
    assert report["maximum_physical_inventory_rate_lbmolph"] == 0.0
    assert report["maximum_state_relative_difference"] == 0.0
    assert not report["fixed_terminal_products"]["instantaneous_product_jump"]
    assert report["structural_audit"]["pass_gate"]
    assert all(item["rank"] == 98 for item in report["jacobian_steps"])
    assert all(item["condition"] < 1.0e8 for item in report["jacobian_steps"])
    assert report["matrix_relative_change"] < 0.05
    assert report["spectrum_relative_change"] < 0.25
    assert report["provider"]["pass_gate"]
    assert report["missing_controller_specifications"]
    assert not report["nonlinear_solve_attempted"]
    assert not report["timestep_accepted"]
    assert not report["dynamic_integration_attempted"]
    assert report["decision"] == (
        "authorize_separately_bounded_fixed_product_hold_step"
    )
