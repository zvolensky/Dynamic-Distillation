from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

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
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_zero_time_v1 import (
    bumpless_controller_state,
    controlled_zero_time_coordinates,
    vapor_holdup_terminal_control_pattern,
    vapor_holdup_terminal_control_variable_names,
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


def test_control_pattern_matches_full_rank_c3c4_contract():
    contract = _actual_contract()
    pattern = vapor_holdup_terminal_control_pattern(contract)

    assert pattern.shape == (262, 262)
    assert len(vapor_holdup_terminal_control_variable_names(contract)) == 262
    assert structural_rank(csr_matrix(pattern)) == 262


def test_bumpless_state_reproduces_reference_products_without_a_jump():
    contract = _actual_contract()
    levels = np.asarray((0.44, 0.53))
    rates, memory, product_logs = bumpless_controller_state(contract, levels)
    point = controlled_zero_time_coordinates(
        contract,
        controller_rates_per_sec=rates,
        product_log_ratios=product_logs,
    )

    errors = levels - 0.5
    gains = np.asarray((0.5, 8.0))
    times = np.asarray((120.0, 120.0))
    assert product_logs.tolist() == [0.0, 0.0]
    assert memory == pytest.approx(-gains * errors)
    assert rates == pytest.approx(gains * errors / times)
    assert point.shape == (262,)
    assert np.count_nonzero(point) == 2
