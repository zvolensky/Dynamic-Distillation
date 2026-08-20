from __future__ import annotations

import json

from tools import audit_core_v3_vapor_holdup_terminal_control_zero_time as dd264


def test_dd264_saved_live_bumpless_handoff_passes():
    saved = json.loads((dd264.ROOT / dd264.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["dimension"] == 262
    assert saved["scaled_residual_inf_norm"] < 1.0e-8
    assert saved["controller_residual_inf_norm"] < 1.0e-10
    assert saved["maximum_physical_inventory_rate_lbmolph"] == 0.0
    assert not saved["bumpless_initialization"]["instantaneous_product_jump"]
    assert saved["bumpless_initialization"]["product_log_ratio"] == [0.0, 0.0]
    assert all(item["rank"] == 262 for item in saved["jacobian_steps"])
    assert saved["provider"]["pass_gate"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["timestep_accepted"]
