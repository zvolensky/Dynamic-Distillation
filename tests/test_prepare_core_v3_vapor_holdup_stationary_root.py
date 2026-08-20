from __future__ import annotations

import numpy as np

from tools import prepare_core_v3_vapor_holdup_stationary_root as dd245


def test_dd245_contract_freezes_one_bounded_campaign_without_live_work():
    contract = dd245.build_contract()

    assert contract["dimension"] == 260
    assert len(contract["start"]) == 260
    assert np.all(np.asarray(contract["start"]) == 0.0)
    assert np.all(
        np.asarray(contract["lower_bounds"])
        < np.asarray(contract["upper_bounds"])
    )
    assert contract["solver"]["method"] == "trf"
    assert contract["solver"]["max_nfev"] == 120
    assert contract["source_scaled_conditions"][0] < 1.0e8
    assert not contract["property_evaluation_attempted"]
    assert not contract["nonlinear_solve_attempted"]
    assert not contract["timestep_attempted"]
