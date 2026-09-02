from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from dynamic_distillation.core_v3.total_reboiler_implicit_v1 import (
    apply_total_reboiler_implicit_boundary,
    total_reboiler_implicit_structural_pattern,
)


def _contract():
    derivative = (
        SimpleNamespace(name="dNL[top,A]/dt", block="liquid_component_inventory_rate", owner="top"),
        SimpleNamespace(name="dNL[bottom,A]/dt", block="liquid_component_inventory_rate", owner="bottom"),
        SimpleNamespace(name="dNL[bottom,B]/dt", block="liquid_component_inventory_rate", owner="bottom"),
        SimpleNamespace(name="dNV[bottom,A]/dt", block="vapor_component_inventory_rate", owner="bottom"),
        SimpleNamespace(name="dNV[bottom,B]/dt", block="vapor_component_inventory_rate", owner="bottom"),
    )
    algebraic = (
        SimpleNamespace(name="T[top]", block="temperature", owner="top"),
        SimpleNamespace(name="T[bottom]", block="temperature", owner="bottom"),
    )
    rows = (
        SimpleNamespace(block="other", owner="top"),
        SimpleNamespace(block="full_phase_equilibrium", owner="bottom"),
        SimpleNamespace(block="full_phase_equilibrium", owner="bottom"),
        SimpleNamespace(block="other", owner="bottom"),
        SimpleNamespace(block="other", owner="bottom"),
        SimpleNamespace(block="other", owner="bottom"),
        SimpleNamespace(block="other", owner="bottom"),
    )
    topology = SimpleNamespace(
        column=SimpleNamespace(
            bottom_volume="bottom",
            volume_ids=("top", "bottom"),
            vapor_links=(("bottom", "top", "V"),),
        )
    )
    return SimpleNamespace(
        derivative_variables=derivative,
        algebraic_variables=algebraic,
        rows=rows,
        component_names=("A", "B"),
        topology=topology,
    )


@dataclass(frozen=True)
class _Evaluation:
    endpoint: object
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    row_names: tuple[str, ...]
    fugacity_residual: np.ndarray


def test_total_reboiler_replaces_bottom_implicit_rows() -> None:
    contract = _contract()
    base_pattern = np.ones((7, 7), dtype=bool)
    pattern = total_reboiler_implicit_structural_pattern(
        contract, base_pattern=base_pattern
    )
    assert np.array_equal(np.flatnonzero(pattern[1]), np.asarray((1, 2, 3, 4)))
    assert np.array_equal(np.flatnonzero(pattern[2]), np.asarray((5, 6)))

    endpoint = SimpleNamespace(
        liquid_component_inventory_lbmol=np.asarray(((1.0, 1.0), (8.0, 2.0))),
        vapor_component_inventory_lbmol=np.asarray(((1.0, 1.0), (6.0, 4.0))),
        temperature_F=np.asarray((100.0, 110.0)),
    )
    evaluation = _Evaluation(
        endpoint=endpoint,
        raw=np.zeros(7),
        scaled=np.zeros(7),
        scales=np.ones(7),
        row_names=tuple(f"r{index}" for index in range(7)),
        fugacity_residual=np.zeros((2, 2)),
    )
    replaced = apply_total_reboiler_implicit_boundary(
        contract, evaluation, temperature_scale_F=10.0
    )
    assert replaced.raw[1] == pytest.approx(np.log((0.6 / 0.4) / (0.8 / 0.2)))
    assert replaced.raw[2] == pytest.approx(10.0)
    assert replaced.fugacity_residual[-1] == pytest.approx(
        (replaced.raw[1], replaced.raw[2] / 10.0)
    )
