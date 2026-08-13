from dataclasses import replace

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (
    TerminalPIParameters,
    TerminalVesselGeometry,
    audit_terminal_inventory_control_contract,
    build_terminal_inventory_control_contract,
)


COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


def _contract(*, rectifying=2, stripping=2, components=COMPONENTS):
    topology = build_column_topology(
        rectifying_volume_count=rectifying,
        stripping_volume_count=stripping,
    )
    base = build_dynamic_dae_contract(
        components,
        topology=topology,
        accepted_root_artifact=(
            "logs/dd169_core_v3_seven_volume_steady_root_20260807.json"
        ),
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    return build_terminal_inventory_control_contract(
        base,
        geometry=TerminalVesselGeometry(
            top_diameter_ft=12.1,
            top_tangent_length_ft=36.3,
            top_head_shape="two_hemispherical",
            bottom_diameter_ft=18.1759,
            bottom_height_ft=12.0,
        ),
        controllers=TerminalPIParameters(
            top_kc=0.5,
            top_ti_sec=120.0,
            bottom_kc=8.0,
            bottom_ti_sec=120.0,
            product_rate_ratio_bounds=(0.25, 2.0),
        ),
    )


def test_dd184_seven_volume_control_contract_is_58_by_58_and_full_rank():
    contract = _contract()
    audit = audit_terminal_inventory_control_contract(contract)

    assert audit.volume_count == 7
    assert audit.state_coordinate_count == 23
    assert audit.derivative_variable_count == 23
    assert audit.algebraic_variable_count == 35
    assert audit.solve_variable_count == audit.row_count == 58
    assert audit.structural_rank == 58
    assert audit.structural_nullity == 0
    assert audit.pass_gate


def test_dd184_replaces_fixed_products_with_live_terminal_outputs():
    contract = _contract()
    audit = audit_terminal_inventory_control_contract(contract)

    assert contract.product_output_variables == (
        "log_D_level_output",
        "log_B_level_output",
    )
    assert not set(contract.base.product_flow_parameters).intersection(
        contract.fixed_parameters
    )
    assert audit.fixed_product_parameters_removed
    assert audit.boundary_rows_own_live_product_outputs


def test_dd184_controller_ownership_is_terminal_only():
    contract = _contract()
    audit = audit_terminal_inventory_control_contract(contract)
    terminals = {
        contract.base.topology.top_volume,
        contract.base.topology.bottom_volume,
    }
    controller_rows = [row for row in contract.rows if "controller" in row.block]

    assert len(controller_rows) == 4
    assert {row.owner for row in controller_rows} == terminals
    assert audit.interior_rows_without_controller_dependencies


def test_dd184_controller_rows_have_exact_live_level_dependencies():
    contract = _contract()
    rows = {row.name: row for row in contract.rows}

    for volume in (
        contract.base.topology.top_volume,
        contract.base.topology.bottom_volume,
    ):
        integrator = rows[f"level_integrator[{volume}]"]
        output = rows[f"level_output[{volume}]"]
        assert integrator.solve_dependencies == (
            f"dI_level[{volume}]/dt",
            f"T[{volume}]",
        )
        assert f"T[{volume}]" in output.solve_dependencies
        assert f"I_level[{volume}]" in output.state_dependencies
        assert all(
            f"N[{volume},{component}]" in output.state_dependencies
            for component in contract.base.component_names
        )


def test_dd184_contract_scales_without_named_interior_logic():
    contract = _contract(
        rectifying=3,
        stripping=2,
        components=("a", "b", "c", "d"),
    )
    audit = audit_terminal_inventory_control_contract(contract)
    expected = len(contract.base.rows) + 4

    assert audit.volume_count == 8
    assert audit.solve_variable_count == audit.row_count == expected == 82
    assert audit.structural_rank == expected
    assert audit.pass_gate


def test_dd184_is_structural_only():
    contract = _contract()
    audit = audit_terminal_inventory_control_contract(contract)

    assert audit.preparation_only
    assert not contract.property_evaluation_attempted
    assert not contract.nonlinear_solve_attempted
    assert not contract.controller_execution_attempted
    assert not contract.dynamic_integration_attempted


def test_dd184_rejects_invalid_geometry_or_tuning():
    contract = _contract()
    bad_geometry = replace(
        contract,
        geometry=replace(contract.geometry, bottom_height_ft=0.0),
    )
    bad_tuning = replace(
        contract,
        controllers=replace(contract.controllers, top_ti_sec=0.0),
    )

    assert not audit_terminal_inventory_control_contract(bad_geometry).pass_gate
    assert not audit_terminal_inventory_control_contract(bad_tuning).pass_gate
