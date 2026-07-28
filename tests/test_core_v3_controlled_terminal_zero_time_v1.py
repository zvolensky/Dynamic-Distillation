import inspect

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.controlled_terminal_dynamic_contract_v1 import (
    LevelControllerSpecification,
    TerminalGeometry,
    build_controlled_terminal_dynamic_contract,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    controlled_terminal_zero_time_pattern,
    controlled_terminal_zero_time_variable_names,
    evaluate_controlled_terminal_zero_time,
    horizontal_drum_level_fraction,
    horizontal_drum_liquid_volume_ft3,
    horizontal_drum_total_volume_ft3,
    terminal_level_fractions,
    vertical_sump_level_fraction,
)


def _geometry():
    return TerminalGeometry(
        drum_diameter_ft=12.1,
        drum_tangent_length_ft=36.3,
        drum_head_shape="two_hemispherical",
        sump_diameter_ft=18.1759,
        sump_height_ft=12.0,
    )


def _contract(components):
    return build_controlled_terminal_dynamic_contract(
        components,
        geometry=_geometry(),
        controllers=LevelControllerSpecification(
            drum_kc=0.5,
            drum_ti_sec=120.0,
            sump_kc=8.0,
            sump_ti_sec=120.0,
            product_rate_ratio_bounds=(0.25, 2.0),
        ),
    )


def test_horizontal_drum_geometry_is_symmetric_and_invertible():
    geometry = _geometry()
    total = horizontal_drum_total_volume_ft3(geometry)

    assert horizontal_drum_liquid_volume_ft3(0.0, geometry) == 0.0
    assert np.isclose(
        horizontal_drum_liquid_volume_ft3(geometry.drum_diameter_ft, geometry),
        total,
    )
    assert np.isclose(horizontal_drum_level_fraction(0.5 * total, geometry), 0.5)


def test_terminal_level_fractions_use_terminal_inventory_and_density():
    geometry = _geometry()
    drum_total = horizontal_drum_total_volume_ft3(geometry)
    sump_total = (
        np.pi * (0.5 * geometry.sump_diameter_ft) ** 2 * geometry.sump_height_ft
    )
    inventory = np.ones((5, 2), dtype=float)
    density = np.ones(5, dtype=float)
    inventory[0] *= 0.25 * drum_total / 2.0
    inventory[-1] *= 0.75 * sump_total / 2.0

    levels = terminal_level_fractions(inventory, density, geometry)

    assert 0.0 < levels[0] < 0.5
    assert np.isclose(levels[1], 0.75)
    assert np.isclose(vertical_sump_level_fraction(0.75 * sump_total, geometry), 0.75)


def test_zero_time_pattern_matches_full_rank_dynamic_contract():
    contract = _contract(("n-Propane", "n-Butane", "n-Pentane"))
    pattern = controlled_terminal_zero_time_pattern(contract)

    assert pattern.shape == (50, 50)
    assert len(controlled_terminal_zero_time_variable_names(contract)) == 50
    assert structural_rank(csr_matrix(pattern)) == 50


def test_zero_time_pattern_remains_generic_for_two_components():
    contract = _contract(("water", "methanol"))
    pattern = controlled_terminal_zero_time_pattern(contract)

    assert pattern.shape == (40, 40)
    assert structural_rank(csr_matrix(pattern)) == 40


def test_zero_time_kernel_accepts_the_shared_pressure_numerical_keyword():
    parameters = inspect.signature(evaluate_controlled_terminal_zero_time).parameters

    assert "pressure_numerical" in parameters
    assert "numerical" not in parameters
