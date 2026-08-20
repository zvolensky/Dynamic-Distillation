from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_stationary_hold as dd248


def test_dd248_saved_stationary_hold_passes_without_motion():
    saved = json.loads((dd248.ROOT / dd248.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["timestep_accepted"]
    assert saved["scaled_residual_inf_norm"] < 1.0e-8
    assert saved["maximum_coordinate_movement"] == 0.0
    assert saved["maximum_inventory_rate_lbmolph"] == 0.0
    assert all(item["rank"] == 258 for item in saved["endpoint_jacobian"]["steps"])
    assert not saved["provider"]["fallback_attempted"]
    assert not saved["retry_attempted"]
    assert not saved["disturbance_applied"]
