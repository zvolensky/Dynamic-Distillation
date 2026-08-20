from __future__ import annotations

import json

from tools import audit_core_v3_vapor_holdup_stationary_jacobian as dd244


def test_dd244_saved_artifact_passes_stationary_jacobian_gate():
    saved = json.loads((dd244.ROOT / dd244.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["dimension"] == 260
    assert all(item["rank"] == 260 for item in saved["step_results"])
    assert all(item["condition"] < 1.0e8 for item in saved["step_results"])
    assert all(item["pass_gate"] for item in saved["sentinel_columns"])
    assert not saved["provider_fallback_attempted"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["timestep_accepted"]
