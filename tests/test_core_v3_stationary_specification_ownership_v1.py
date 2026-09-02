from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v3.prescribed_pressure_stationary_v1 import (
    prescribed_pressure_structural_pattern,
)
from dynamic_distillation.core_v3.stationary_specification_ownership_v1 import (
    fixed_bottoms_solved_reboiler_pattern,
    fixed_bottoms_solved_reboiler_trial,
    specification_aware_variable_names,
)
from test_core_v3_vapor_holdup_stationary_residual_v1 import _stationary_problem


def test_bottom_product_coordinate_is_reassigned_to_reboiler_duty():
    _provider, _spec, contract, _geometry, reference, inputs, _numerical = (
        _stationary_problem()
    )
    point = np.zeros(len(contract.variables))
    bottom_index = next(
        index
        for index, variable in enumerate(contract.variables)
        if variable.block == "terminal_level_product_flow"
        and variable.owner == contract.topology.column.bottom_volume
    )
    point[bottom_index] = np.log(1.1)
    fixed_bottoms = 0.9 * reference.bottoms_lbmolph

    trial = fixed_bottoms_solved_reboiler_trial(
        contract,
        reference,
        inputs,
        point,
        fixed_bottoms_lbmolph=fixed_bottoms,
    )

    assert np.isclose(
        trial.base_coordinates[bottom_index],
        np.log(fixed_bottoms / reference.bottoms_lbmolph),
    )
    assert trial.balance_inputs.bottoms_lbmolph == fixed_bottoms
    assert np.isclose(trial.reboiler_duty_BTUph, 1.1 * inputs.reboiler_duty_BTUph)
    assert specification_aware_variable_names(contract)[bottom_index] == "Q_R"

    pattern = fixed_bottoms_solved_reboiler_pattern(
        contract,
        base_pattern=prescribed_pressure_structural_pattern(contract),
    )
    bottom_energy_row = next(
        index
        for index, row in enumerate(contract.rows)
        if row.block == "total_energy_balance"
        and row.owner == contract.topology.column.bottom_volume
    )
    assert np.flatnonzero(pattern[:, bottom_index]).tolist() == [bottom_energy_row]
