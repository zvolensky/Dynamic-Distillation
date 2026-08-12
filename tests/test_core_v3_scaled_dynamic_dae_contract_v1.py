from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)


COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


def _scaled_contract(rectifying=2, stripping=2, components=COMPONENTS):
    topology = build_column_topology(
        rectifying_volume_count=rectifying,
        stripping_volume_count=stripping,
    )
    return build_dynamic_dae_contract(
        components,
        topology=topology,
        accepted_root_artifact=(
            "logs/dd169_core_v3_seven_volume_steady_root_20260807.json"
        ),
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )


def test_dd170_seven_volume_contract_is_54_by_54_and_full_rank():
    contract = _scaled_contract()
    audit = audit_dynamic_dae_contract(contract)

    assert len(contract.topology.volume_ids) == 7
    assert audit.state_coordinate_count == 21
    assert audit.derivative_variable_count == 21
    assert audit.algebraic_variable_count == 33
    assert audit.solve_variable_count == audit.row_count == 54
    assert audit.structural_rank == 54
    assert audit.structural_nullity == 0
    assert audit.pass_gate


def test_dd170_seven_volume_block_ownership_scales_with_topology():
    audit = audit_dynamic_dae_contract(_scaled_contract())

    assert audit.component_balance_count == 21
    assert audit.energy_balance_count == 7
    assert audit.full_fugacity_count == 18
    assert audit.francis_count == 5
    assert audit.condenser_bubble_count == 3
    assert audit.vapor_link_count == 6
    assert audit.condenser_duty_count == 1
    assert audit.component_conservation_passed
    assert audit.energy_conservation_passed


def test_dd170_scaled_contract_uses_declared_root_and_product_parameters():
    contract = _scaled_contract()
    audit = audit_dynamic_dae_contract(contract)

    assert contract.product_flow_parameters == (
        "D_dd169_root",
        "B_dd169_root",
    )
    assert set(contract.product_flow_parameters).issubset(
        contract.fixed_parameters
    )
    assert contract.accepted_root_artifact.endswith(
        "dd169_core_v3_seven_volume_steady_root_20260807.json"
    )
    assert audit.fixed_product_parameters_present
    assert audit.accepted_root_declared
    assert audit.preparation_only


def test_dd170_adjacency_is_generated_for_every_scaled_volume():
    contract = _scaled_contract()
    rows = {row.name: row for row in contract.rows}
    topology = contract.topology

    for source, destination, symbol in topology.vapor_links:
        source_y = f"y[{source},{COMPONENTS[0]}]"
        for volume in (source, destination):
            row = rows[f"component_balance[{volume},{COMPONENTS[0]}]"]
            assert symbol in row.solve_dependencies
            assert source_y in row.solve_dependencies

    for source, destination, symbol in topology.liquid_links:
        if symbol == "R":
            continue
        for volume in (source, destination):
            row = rows[f"component_balance[{volume},{COMPONENTS[0]}]"]
            assert symbol in row.solve_dependencies


def test_dd170_formula_holds_for_another_topology_and_component_count():
    components = ("a", "b", "c", "d")
    contract = _scaled_contract(rectifying=3, stripping=2, components=components)
    audit = audit_dynamic_dae_contract(contract)
    volume_count = len(contract.topology.volume_ids)
    expected = 2 * volume_count * (len(components) + 1) - 2

    assert volume_count == 8
    assert audit.solve_variable_count == audit.row_count == expected == 78
    assert audit.structural_rank == expected
    assert audit.pass_gate


def test_dd170_contains_no_controller_profile_or_dynamic_execution():
    contract = _scaled_contract()
    audit = audit_dynamic_dae_contract(contract)

    assert audit.controller_rows == ()
    assert audit.profile_dependencies == ()
    assert audit.terminal_amount_constraint_rows == ()
    assert not contract.property_evaluation_attempted
    assert not contract.mass_matrix_evaluation_attempted
    assert not contract.nonlinear_solve_attempted
    assert not contract.dynamic_integration_attempted
