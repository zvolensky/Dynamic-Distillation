from dataclasses import replace

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    SolveVariable,
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)


def _contract(components=("Propane", "n-Butane", "n-Pentane")):
    return build_dynamic_dae_contract(components)


def test_dd095_three_component_implicit_ledger_is_38_by_38_and_full_rank():
    audit = audit_dynamic_dae_contract(_contract())

    assert audit.state_coordinate_count == 15
    assert audit.derivative_variable_count == 15
    assert audit.algebraic_variable_count == 23
    assert audit.solve_variable_count == audit.row_count == 38
    assert audit.structural_rank == 38
    assert audit.structural_nullity == 0
    assert audit.pass_gate


def test_dd095_ledger_scales_as_ten_c_plus_eight():
    for components in (("light", "heavy"), ("a", "b", "c", "d")):
        audit = audit_dynamic_dae_contract(_contract(components))
        expected = 10 * len(components) + 8

        assert audit.solve_variable_count == audit.row_count == expected
        assert audit.structural_rank == expected
        assert audit.pass_gate


def test_dd095_preserves_balance_equilibrium_and_flow_ownership():
    audit = audit_dynamic_dae_contract(_contract())

    assert audit.component_balance_count == 15
    assert audit.energy_balance_count == 5
    assert audit.full_fugacity_count == 12
    assert audit.francis_count == 3
    assert audit.condenser_bubble_count == 3
    assert audit.vapor_link_count == 4
    assert audit.condenser_duty_count == 1
    assert audit.component_conservation_passed
    assert audit.energy_conservation_passed


def test_dd095_uses_inventory_coordinates_and_derived_energy_storage():
    contract = _contract()
    audit = audit_dynamic_dae_contract(contract)

    assert all(name.startswith("N[") for name in contract.state_coordinates)
    assert "dU[j]/dt" in contract.internal_energy_storage
    assert audit.independent_internal_energy_coordinates == ()
    assert audit.temperature_derivative_variables == ()
    assert "implicit-index-1 candidate" in contract.index_claim


def test_dd095_open_loop_contract_has_no_level_constraint_or_controller():
    contract = _contract()
    audit = audit_dynamic_dae_contract(contract)

    assert audit.fixed_product_parameters_present
    assert audit.terminal_amount_constraint_rows == ()
    assert audit.controller_rows == ()
    assert audit.profile_dependencies == ()
    assert "D_dd094_root" in contract.fixed_parameters
    assert "B_dd094_root" in contract.fixed_parameters


def test_dd095_is_preparation_only_and_declares_consistent_root_source():
    contract = _contract()
    audit = audit_dynamic_dae_contract(contract)

    assert audit.accepted_root_declared
    assert audit.preparation_only
    assert not contract.property_evaluation_attempted
    assert not contract.mass_matrix_evaluation_attempted
    assert not contract.nonlinear_solve_attempted
    assert not contract.dynamic_integration_attempted


def test_dd095_rejects_an_unowned_condenser_duty_column():
    contract = _contract()
    rows = tuple(
        replace(
            row,
            solve_dependencies=tuple(
                dependency
                for dependency in row.solve_dependencies
                if dependency != "Q_C"
            ),
        )
        for row in contract.rows
    )
    audit = audit_dynamic_dae_contract(replace(contract, rows=rows))

    assert audit.zero_solve_columns == ("Q_C",)
    assert not audit.pass_gate


def test_dd095_rejects_independent_internal_energy_coordinates():
    contract = _contract()
    bad = replace(
        contract,
        state_coordinates=(*contract.state_coordinates, "U[reflux_drum]"),
        derivative_variables=(
            *contract.derivative_variables,
            SolveVariable(
                "dU[reflux_drum]/dt",
                "independent_internal_energy_rate",
                "reflux_drum",
            ),
        ),
    )
    audit = audit_dynamic_dae_contract(bad)

    assert audit.independent_internal_energy_coordinates == ("U[reflux_drum]",)
    assert not audit.pass_gate
