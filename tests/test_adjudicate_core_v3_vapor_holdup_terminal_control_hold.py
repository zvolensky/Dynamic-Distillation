from __future__ import annotations

import json

from tools import adjudicate_core_v3_vapor_holdup_terminal_control_hold as dd266


def test_dd266_saved_read_only_adjudication_passes():
    saved = json.loads((dd266.ROOT / dd266.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["source"]["failed_gates"] == ["energy_identity", "solver"]
    assert saved["endpoint"]["scaled_residual_inf_norm"] < 1.0e-8
    assert (
        saved["energy_adjudication"]["absolute_error_BTU"]
        < saved["energy_adjudication"]["residual_consistent_bound_BTU"]
    )
    assert saved["endpoint"]["distillate_lbmolph"] < 2519.763701913325
    assert saved["endpoint"]["bottoms_lbmolph"] > 4623.21029792288
    assert not saved["property_evaluation_attempted"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["state_advance_attempted"]
