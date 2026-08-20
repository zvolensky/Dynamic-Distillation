from __future__ import annotations

import json

from tools import audit_core_v3_vapor_holdup_full_residual as dd240


def test_dd240_saved_artifact_passes_complete_residual_gate():
    saved = json.loads((dd240.ROOT / dd240.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["dimension"] == 258
    assert saved["structural_audit"]["structural_rank"] == 258
    assert saved["maximum_relative_eos_residual"] < 1.0e-12
    assert saved["provider_calls"]["governing_residual"] == 120
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["timestep_accepted"]
