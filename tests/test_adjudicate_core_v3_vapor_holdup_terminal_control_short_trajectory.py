from __future__ import annotations

import json

from tools import adjudicate_core_v3_vapor_holdup_terminal_control_short_trajectory as dd268


def test_dd268_saved_controller_aware_refinement_adjudication_passes():
    saved = json.loads((dd268.ROOT / dd268.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["source"]["failed_gates"] == ["refinement"]
    assert (
        saved["controller_aware_refinement"][
            "unexplained_component_max_abs_lbmol"
        ]
        < 1.0e-6
    )
    assert saved["gates"]["all_non_refinement_gates_passed"]
    assert not saved["property_evaluation_attempted"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["state_advance_attempted"]
