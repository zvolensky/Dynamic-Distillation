from __future__ import annotations

import json

import numpy as np

from tools import run_core_v3_vapor_holdup_broyden_trajectory as dd256


def test_good_broyden_update_satisfies_latest_secant():
    matrix = np.array([[2.0, 0.0], [0.0, 3.0]])
    step = np.array([0.5, -0.25])
    residual_change = np.array([0.8, -1.1])

    updated, error = dd256.good_broyden_update(matrix, step, residual_change)

    assert np.allclose(updated @ step, residual_change, atol=1.0e-15)
    assert error < 1.0e-15


def test_dd256_saved_contract_freezes_broyden_update():
    saved = json.loads((dd256.ROOT / dd256.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["method"]["fresh_jacobians_per_root"] == 1
    assert saved["method"]["parallel_workers"] == 0
    assert saved["trajectory"]["steps_per_path"] == 4
    assert saved["limits"]["coordinate_absolute_difference"] == 1.0e-9
