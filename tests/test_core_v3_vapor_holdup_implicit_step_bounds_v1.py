from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import Unknown
from dynamic_distillation.core_v3.vapor_holdup_implicit_step_bounds_v1 import (
    vapor_holdup_implicit_step_coordinate_bounds,
)


def test_implicit_step_bounds_follow_variable_blocks_not_positions():
    contract = SimpleNamespace(
        derivative_variables=(
            Unknown("rate_b", "vapor_component_inventory_rate", "v"),
            Unknown("rate_a", "liquid_component_inventory_rate", "v"),
        ),
        algebraic_variables=(
            Unknown("P", "algebraic_pressure", "v"),
            Unknown("M", "interphase_component_transfer", "v"),
            Unknown("Q", "solved_condenser_duty", "v"),
            Unknown("T", "temperature", "v"),
            Unknown("L", "francis_liquid_flow", "v"),
            Unknown("V", "pressure_driven_vapor_flow", "v"),
        ),
    )

    lower, upper = vapor_holdup_implicit_step_coordinate_bounds(contract)

    assert np.allclose(
        upper,
        [0.01, 0.01, 0.1, 0.1, 0.01, 0.1, 0.01, 0.01],
    )
    assert np.allclose(lower, -upper)
