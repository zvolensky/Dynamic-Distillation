from __future__ import annotations

import json

from tools import audit_core_v3_vapor_holdup_zero_motion as dd247


def test_dd247_saved_zero_motion_audit_passes():
    saved = json.loads((dd247.ROOT / dd247.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["dimension"] == 258
    assert saved["scaled_residual_inf_norm"] < 1.0e-8
    assert saved["maximum_inventory_rate_lbmolph"] == 0.0
    assert saved["energy_history"]["current_previous_identical"]
    assert all(item["rank"] == 258 for item in saved["jacobian_steps"])
    assert saved["provider"]["pass_gate"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["timestep_accepted"]
