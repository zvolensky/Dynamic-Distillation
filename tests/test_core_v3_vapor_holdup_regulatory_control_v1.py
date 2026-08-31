from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.provider_governed_registry_v1 import build_column_topology
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_contract_v1 import (
    CONDENSER_DUTY_PARAMETER,
    build_vapor_holdup_dynamic_pressure_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.core_v3.vapor_holdup_regulatory_control_contract_v1 import (
    REFLUX_OUTPUT,
    VaporHoldupRegulatoryControllerSpecification,
    audit_vapor_holdup_regulatory_control_contract,
    build_vapor_holdup_regulatory_control_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_regulatory_control_implicit_residual_v1 import (
    regulatory_control_bounds,
    regulatory_control_initial_coordinates,
    regulatory_control_variable_names,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"


def _contract():
    case = load_case_from_excel(str(WORKBOOK))
    column = build_column_spec_from_case(case)
    feed_stage = int(column.streams["Feed"].stage_1based)
    topology = build_column_topology(
        rectifying_volume_count=feed_stage - 2,
        stripping_volume_count=int(column.n_stages) - feed_stage - 1,
    )
    geometry = build_column_vapor_geometry(column, case.specs, topology)
    vapor_topology = build_vapor_holdup_topology(
        column=topology,
        vapor_volume_ft3=gross_capacity_mapping(geometry),
    )
    base = build_vapor_holdup_dae_contract(
        ("n-Propane", "n-Butane", "n-Pentane"), topology=vapor_topology
    )
    level = build_vapor_holdup_terminal_control_contract(
        base,
        geometry=terminal_geometry_from_specs(case.specs),
        controllers=level_controllers_from_specs(case.specs),
    )
    dynamic = build_vapor_holdup_dynamic_pressure_contract(level)
    spec = VaporHoldupRegulatoryControllerSpecification(
        pressure_setpoint_psia=221.32122601060775,
        pressure_kc_per_psia=300_000.0 / 50_894_825.691564746,
        pressure_ti_sec=180.0,
        condenser_duty_reference_BTUph=-50_894_825.691564746,
        condenser_duty_ratio_bounds=(0.5, 1.5),
        composition_component="n-Butane",
        composition_setpoint_molfrac=0.11987175180429868,
        composition_kc_per_molfrac=5_000.0 / 5952.48,
        composition_ti_sec=600.0,
        reflux_reference_lbmolph=5952.48,
        reflux_ratio_bounds=(0.5, 1.5),
    )
    return build_vapor_holdup_regulatory_control_contract(dynamic, spec)


def test_regulatory_contract_is_square_full_rank_and_owns_both_mvs() -> None:
    contract = _contract()
    audit = audit_vapor_holdup_regulatory_control_contract(contract)

    assert audit.pass_gate
    assert audit.solve_variable_count == audit.row_count == audit.structural_rank == 265
    assert audit.pressure_controller_row_count == 2
    assert audit.composition_controller_row_count == 2
    assert audit.fixed_condenser_duty_removed
    assert CONDENSER_DUTY_PARAMETER not in contract.fixed_parameters
    assert REFLUX_OUTPUT in tuple(v.name for v in contract.algebraic_variables)


def test_regulatory_predictor_upgrades_old_checkpoint_bumplessly() -> None:
    contract = _contract()
    old = np.zeros(len(contract.predecessor.rows))
    product_logs = np.asarray((0.04, -0.001))
    rates = np.asarray((1.0e-4, -2.0e-5, 3.0e-6, 4.0e-7))

    point = regulatory_control_initial_coordinates(
        contract,
        controller_rates_per_sec=rates,
        timestep_sec=0.5,
        previous_coordinates=old,
        product_log_ratios_previous=product_logs,
        reflux_log_ratio_previous=0.0,
    )

    assert point.shape == (265,)
    assert point[120:122] == pytest.approx(rates[:2])
    assert point[122:124] == pytest.approx(rates[2:])
    assert point[-3:-1] == pytest.approx(product_logs + 0.5 * rates[:2])
    assert point[-1] == pytest.approx(0.5 * rates[3])


def test_regulatory_bounds_allow_feed_step_vapor_redistribution() -> None:
    contract = _contract()
    names = regulatory_control_variable_names(contract)
    lower, upper = regulatory_control_bounds(
        contract,
        SimpleNamespace(condenser_duty_BTUph=-50_894_825.691564746),
    )

    vapor_indices = [index for index, name in enumerate(names) if name.startswith("V[")]
    assert len(vapor_indices) == len(contract.base.topology.column.vapor_links)
    assert lower[vapor_indices] == pytest.approx(-0.05)
    assert upper[vapor_indices] == pytest.approx(0.05)
