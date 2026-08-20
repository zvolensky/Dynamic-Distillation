from __future__ import annotations

import json

from tools import map_core_v3_vapor_holdup_dynamic_handoff as dd246


def test_dd246_saved_handoff_consumes_root_once_without_live_work():
    saved = json.loads((dd246.ROOT / dd246.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert saved["stationary_coordinate_count"] == 260
    assert saved["mapping"]["consumed_once_count"] == 260
    assert saved["mapping"]["conserved_state_count"] == 120
    assert saved["mapping"]["zero_derivative_count"] == 120
    assert saved["mapping"]["algebraic_count"] == 138
    assert saved["mapping"]["fixed_product_reference_count"] == 2
    assert saved["bdf2_history"]["component_history_values"] == 240
    assert saved["bdf2_history"]["energy_history_values_deferred"] == 40
    assert not saved["property_evaluation_attempted"]
    assert not saved["residual_evaluation_attempted"]
    assert not saved["timestep_attempted"]
