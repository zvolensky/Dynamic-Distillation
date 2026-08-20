from pathlib import Path

import numpy as np
import pytest

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_implicit_residual_v1 import (
    controlled_implicit_initial_coordinates,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"


def _actual_contract():
    case = load_case_from_excel(str(WORKBOOK))
    column = build_column_spec_from_case(case)
    feed_stage = int(column.streams["Feed"].stage_1based)
    topology = build_column_topology(
        rectifying_volume_count=feed_stage - 2,
        stripping_volume_count=int(column.n_stages) - feed_stage - 1,
    )
    volume_geometry = build_column_vapor_geometry(column, case.specs, topology)
    vapor_topology = build_vapor_holdup_topology(
        column=topology,
        vapor_volume_ft3=gross_capacity_mapping(volume_geometry),
    )
    base = build_vapor_holdup_dae_contract(
        tuple(column.components_excel), topology=vapor_topology
    )
    return build_vapor_holdup_terminal_control_contract(
        base,
        geometry=terminal_geometry_from_specs(case.specs),
        controllers=level_controllers_from_specs(case.specs),
    )


def test_controlled_predictor_advances_only_pi_rates_and_outputs():
    contract = _actual_contract()
    rates = np.asarray((-2.5e-4, 1.5e-3))

    point = controlled_implicit_initial_coordinates(
        contract,
        controller_rates_per_sec=rates,
        timestep_sec=0.25,
    )

    base_rate_count = len(contract.base.derivative_variables)
    output_start = base_rate_count + 2 + len(contract.base.algebraic_variables)
    assert point.shape == (262,)
    assert point[base_rate_count : base_rate_count + 2] == pytest.approx(rates)
    assert point[output_start:] == pytest.approx(0.25 * rates)
    assert np.count_nonzero(point) == 4


def test_controlled_predictor_preserves_prior_point_and_advances_absolute_outputs():
    contract = _actual_contract()
    previous = np.full(262, 1.0e-6)
    rates = np.asarray((-2.5e-4, 1.5e-3))
    logs = np.asarray((-6.0e-5, 3.9e-4))

    point = controlled_implicit_initial_coordinates(
        contract,
        controller_rates_per_sec=rates,
        timestep_sec=0.125,
        previous_coordinates=previous,
        product_log_ratios_previous=logs,
    )

    base_rate_count = len(contract.base.derivative_variables)
    output_start = base_rate_count + 2 + len(contract.base.algebraic_variables)
    assert point[base_rate_count : base_rate_count + 2] == pytest.approx(rates)
    assert point[output_start:] == pytest.approx(logs + 0.125 * rates)
    assert point[0] == pytest.approx(previous[0])


@pytest.mark.parametrize("timestep", [0.0, -0.25, np.nan])
def test_controlled_predictor_rejects_invalid_timestep(timestep):
    contract = _actual_contract()

    with pytest.raises(ValueError, match="timestep"):
        controlled_implicit_initial_coordinates(
            contract,
            controller_rates_per_sec=(0.0, 0.0),
            timestep_sec=timestep,
        )
