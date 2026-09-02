from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import Unknown
from dynamic_distillation.core_v3.vapor_holdup_stationary_bounds_v1 import (
    VaporHoldupStationaryBoundSettings,
    vapor_holdup_stationary_coordinate_bounds,
)


def _fixture():
    components = ("component_a", "component_b", "component_c")
    variables = tuple(
        Unknown(f"NL[volume,{component}]", "liquid_component_inventory", "volume")
        for component in components
    ) + tuple(
        Unknown(f"NV[volume,{component}]", "vapor_component_inventory", "volume")
        for component in components
    ) + (
        Unknown("M[volume,component_a]", "interphase_component_transfer", "volume"),
        Unknown("T[volume]", "temperature", "volume"),
        Unknown("P[volume]", "pressure", "volume"),
        Unknown("L[volume]", "francis_liquid_flow", "volume"),
        Unknown("V[volume]", "pressure_driven_vapor_flow", "link"),
        Unknown("Q_C", "solved_condenser_duty", "column"),
        Unknown("D", "terminal_level_product_flow", "column"),
    )
    contract = SimpleNamespace(variables=variables)
    reference = SimpleNamespace(
        liquid_component_inventory_lbmol=np.array([[90.0, 9.0, 1.0]]),
        vapor_component_inventory_lbmol=np.array([[0.1, 0.2, 9.7]]),
    )
    return contract, reference


def test_inventory_bounds_use_phase_totals_instead_of_component_identity():
    contract, reference = _fixture()
    settings = VaporHoldupStationaryBoundSettings()
    lower, upper = vapor_holdup_stationary_coordinate_bounds(
        contract,
        reference,
        settings,
    )

    liquid_reference = reference.liquid_component_inventory_lbmol.reshape((-1,))
    vapor_reference = reference.vapor_component_inventory_lbmol.reshape((-1,))
    liquid_absolute_upper = liquid_reference * np.exp(upper[:3])
    vapor_absolute_upper = vapor_reference * np.exp(upper[3:6])

    assert np.allclose(liquid_absolute_upper, liquid_absolute_upper[0])
    assert np.allclose(vapor_absolute_upper, vapor_absolute_upper[0])
    assert upper[2] > np.log(10.0)
    assert upper[3] > np.log(10.0)
    assert np.all(lower < 0.0)
    assert np.all(upper > 0.0)


def test_noninventory_bounds_preserve_general_coordinate_rules():
    contract, reference = _fixture()
    lower, upper = vapor_holdup_stationary_coordinate_bounds(contract, reference)

    assert np.allclose(lower[6:], [-5.0, -5.0, -20.0, np.log(0.2), np.log(0.2), np.log(0.5), np.log(0.5)])
    assert np.allclose(upper[6:], [5.0, 5.0, 20.0, np.log(5.0), np.log(5.0), np.log(1.5), np.log(1.5)])
