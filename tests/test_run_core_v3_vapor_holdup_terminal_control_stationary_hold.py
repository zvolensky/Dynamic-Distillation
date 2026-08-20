from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from tools import run_core_v3_vapor_holdup_terminal_control_stationary_hold as dd265


def test_controlled_product_bounds_come_from_physical_rate_ratio_contract():
    contract = SimpleNamespace(
        rows=(None,) * 262,
        base=SimpleNamespace(
            derivative_variables=(None,) * 120,
            algebraic_variables=(None,) * 138,
        ),
        controllers=SimpleNamespace(product_rate_ratio_bounds=(0.25, 2.0)),
    )

    lower, upper = dd265._bounds(contract)

    assert lower[-2:] == pytest.approx(np.log(0.25))
    assert upper[-2:] == pytest.approx(np.log(2.0))
    assert lower[-3] == pytest.approx(-0.01)
    assert upper[-3] == pytest.approx(0.01)


def test_dd265_saved_endpoint_preserves_formal_failure_and_physical_result():
    saved = json.loads((dd265.ROOT / dd265.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert not saved["pass_gate"]
    assert saved["prior_serialization_failure"]
    assert saved["retry_attempted"]
    assert saved["scaled_residual_inf_norm"] < 1.0e-8
    assert saved["controller_residual_inf_norm"] < 1.0e-10
    assert saved["gates"]["physical"]
    assert saved["gates"]["distillate_direction"]
    assert saved["gates"]["bottoms_direction"]
    assert saved["gates"]["drum_level_direction"]
    assert saved["gates"]["sump_level_direction"]
    assert not saved["gates"]["solver"]
    assert not saved["gates"]["energy_identity"]
    assert all(item["rank"] == 262 for item in saved["endpoint_jacobian"]["steps"])
