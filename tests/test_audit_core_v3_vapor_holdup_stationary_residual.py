from __future__ import annotations

import json

from tools import audit_core_v3_vapor_holdup_stationary_residual as dd243


def test_dd243_saved_artifact_passes_stationary_residual_gate():
    saved = json.loads((dd243.ROOT / dd243.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["dimension"] == 260
    assert saved["structural_audit"]["structural_rank"] == 260
    assert saved["terminal_inventory_residual_lbmol"] == [0.0, 0.0]
    assert saved["maximum_relative_eos_residual"] < 1.0e-12
    assert saved["provider_calls"]["governing_residual"] == 120
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["timestep_accepted"]
