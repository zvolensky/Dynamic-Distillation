from __future__ import annotations

import json

import numpy as np

from tools import run_core_v3_vapor_holdup_small_moving_step as dd249


def test_dd249_coordinate_scale_is_fixed_positive_and_well_shaped():
    scale = dd249._coordinate_scale()

    assert scale.shape == (258,)
    assert np.all(np.isfinite(scale))
    assert np.all(scale > 0.0)
    assert np.median(scale) == 1.0


def test_dd249_saved_contract_is_frozen_and_nonexecuted():
    saved = json.loads((dd249.ROOT / dd249.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["disturbance"]["feed_component_multiplier"] == 1.001
    assert saved["steps"] == {"full_seconds": 0.25, "half_seconds": 0.125}


def test_dd249_saved_result_passes_moving_response_and_refinement_gates():
    saved = json.loads((dd249.ROOT / dd249.RESULT).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert all(saved["campaign_gates"].values())
    assert saved["response"]["full"]["total_inventory_change_lbmol"] > 0.0
    assert saved["response"]["full"]["component_inventory_identity_max_abs_lbmol"] < 1.0e-6
    assert saved["refinement"]["maximum_component_inventory_difference_lbmol"] < 2.0e-5
    assert all(item["jacobian_rank"] == 258 for item in saved["steps"].values())
    assert not saved["retry_attempted"]
    assert not saved["controller_action_attempted"]
