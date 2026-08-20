from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_stationary_root as dd245


def test_dd245_saved_root_passes_all_frozen_gates():
    saved = json.loads((dd245.ROOT / dd245.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["scaled_residual_inf_norm"] < 1.0e-8
    assert saved["endpoint"]["physical_pass"]
    assert saved["endpoint"]["pressure_ordered"]
    assert saved["endpoint_jacobian"]["pass_gate"]
    assert all(item["rank"] == 260 for item in saved["endpoint_jacobian"]["steps"])
    assert not saved["provider"]["fallback_attempted"]
    assert not saved["retry_attempted"]
    assert not saved["continuation_attempted"]
    assert not saved["timestep_attempted"]
