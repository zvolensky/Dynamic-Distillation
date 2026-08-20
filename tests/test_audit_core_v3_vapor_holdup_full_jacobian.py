from __future__ import annotations

import json

from tools import audit_core_v3_vapor_holdup_full_jacobian as dd241


def test_dd241_saved_artifact_passes_complete_jacobian_gate():
    saved = json.loads((dd241.ROOT / dd241.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["dimension"] == 258
    assert all(item["rank"] == 258 for item in saved["step_results"])
    assert all(item["condition"] < 1.0e8 for item in saved["step_results"])
    assert all(item["pass_gate"] for item in saved["sentinel_columns"])
    assert not saved["provider_fallback_attempted"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["timestep_accepted"]
