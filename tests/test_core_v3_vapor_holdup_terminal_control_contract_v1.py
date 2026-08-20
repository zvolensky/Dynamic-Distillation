from pathlib import Path

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
    audit_vapor_holdup_terminal_control_contract,
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"


def _actual_contract():
    case = load_case_from_excel(str(WORKBOOK))
    column = build_column_spec_from_case(case)
    feed = column.streams["Feed"]
    topology = build_column_topology(
        rectifying_volume_count=int(feed.stage_1based) - 2,
        stripping_volume_count=int(column.n_stages) - int(feed.stage_1based) - 1,
    )
    volume_geometry = build_column_vapor_geometry(column, case.specs, topology)
    vapor_topology = build_vapor_holdup_topology(
        column=topology,
        vapor_volume_ft3=gross_capacity_mapping(volume_geometry),
    )
    base = build_vapor_holdup_dae_contract(
        tuple(column.components_excel), topology=vapor_topology
    )
    geometry = terminal_geometry_from_specs(case.specs)
    controllers = level_controllers_from_specs(case.specs)
    return (
        build_vapor_holdup_terminal_control_contract(
            base,
            geometry=geometry,
            controllers=controllers,
        ),
        geometry,
        controllers,
    )


def test_c3c4_terminal_geometry_comes_from_workbook_values():
    _contract, geometry, controllers = _actual_contract()

    assert geometry.drum_diameter_ft == pytest.approx(12.1)
    assert geometry.drum_tangent_length_ft == pytest.approx(36.3)
    assert geometry.drum_gross_capacity_ft3 == pytest.approx(5101.729437737338)
    assert geometry.sump_diameter_ft == pytest.approx(18.1759)
    assert geometry.sump_height_ft == pytest.approx(12.0)
    assert geometry.sump_gross_capacity_ft3 == pytest.approx(3113.601133512231)
    assert controllers.drum_level_setpoint_fraction == pytest.approx(0.5)
    assert controllers.sump_level_setpoint_fraction == pytest.approx(0.5)


def test_full_c3c4_terminal_control_contract_is_square_and_full_rank():
    contract, _geometry, _controllers = _actual_contract()
    audit = audit_vapor_holdup_terminal_control_contract(contract)

    assert audit.solve_variable_count == 262
    assert audit.row_count == 262
    assert audit.structural_rank == 262
    assert audit.controller_state_count == 2
    assert audit.controller_rate_count == 2
    assert audit.controller_output_count == 2
    assert audit.controller_row_count == 4
    assert audit.boundary_rows_own_product_outputs
    assert audit.fixed_product_parameters_removed
    assert audit.pass_gate


def test_terminal_control_contract_remains_generic_in_component_count():
    source, geometry, controllers = _actual_contract()
    topology = source.base.topology
    base = build_vapor_holdup_dae_contract(("light", "heavy"), topology=topology)
    contract = build_vapor_holdup_terminal_control_contract(
        base,
        geometry=geometry,
        controllers=controllers,
    )
    audit = audit_vapor_holdup_terminal_control_contract(contract)

    assert audit.component_count == 2
    assert audit.solve_variable_count == audit.row_count
    assert audit.structural_rank == audit.expected_count
    assert audit.pass_gate


def test_missing_workbook_geometry_is_rejected():
    with pytest.raises(ValueError, match="Top Drum Diameter"):
        terminal_geometry_from_specs({})
