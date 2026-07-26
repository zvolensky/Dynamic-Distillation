from dataclasses import replace

from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    audit_conserved_nu_pressure_dae_contract,
    build_conserved_nu_pressure_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    VAPOR_LINKS,
    VOLUME_IDS,
)


COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def _contract():
    return build_conserved_nu_pressure_dae_contract(COMPONENTS)


def test_dd108_conserved_nu_pressure_ledger_is_square_and_full_rank():
    audit = audit_conserved_nu_pressure_dae_contract(_contract())

    assert audit.state_coordinate_count == 19
    assert audit.derivative_variable_count == 19
    assert audit.algebraic_variable_count == 27
    assert audit.solve_variable_count == audit.row_count == 46
    assert audit.structural_rank == 46
    assert audit.structural_nullity == 0
    assert not audit.zero_solve_columns
    assert not audit.zero_rows
    assert audit.pass_gate


def test_dd108_internal_energy_is_independent_and_has_one_rate_per_volume():
    contract = _contract()
    audit = audit_conserved_nu_pressure_dae_contract(contract)

    assert audit.internal_energy_state_count == len(VOLUME_IDS) - 1 == 4
    assert audit.internal_energy_rate_count == len(VOLUME_IDS) - 1
    assert {
        variable.name
        for variable in contract.derivative_variables
        if variable.block == "internal_energy_rate"
    } == {f"dU[{volume}]/dt" for volume in VOLUME_IDS[1:]}


def test_dd108_energy_balances_use_dU_not_reduced_dN_gradient():
    contract = _contract()
    audit = audit_conserved_nu_pressure_dae_contract(contract)
    rows = tuple(row for row in contract.rows if row.block == "energy_balance")

    assert audit.energy_rows_use_valid_storage_rates
    top = next(row for row in rows if row.owner == VOLUME_IDS[0])
    assert not any(item.startswith("dU[") for item in top.solve_dependencies)
    assert sum(item.startswith("dN[") for item in top.solve_dependencies) == len(COMPONENTS)
    for row in (row for row in rows if row.owner != VOLUME_IDS[0]):
        assert f"dU[{row.owner}]/dt" in row.solve_dependencies
        assert not any(item.startswith("dN[") for item in row.solve_dependencies)


def test_dd108_storage_closure_uses_live_state_and_pressure():
    contract = _contract()
    audit = audit_conserved_nu_pressure_dae_contract(contract)
    rows = tuple(
        row for row in contract.rows if row.block == "liquid_internal_energy_storage"
    )

    assert audit.storage_rows_cover_all_independent_energy_volumes
    assert audit.storage_rows_use_live_lower_pressure
    assert {row.owner for row in rows} == set(VOLUME_IDS[1:])
    for row in rows:
        assert f"P[{row.owner}]" in row.solve_dependencies
        assert f"T[{row.owner}]" in row.solve_dependencies
        assert f"U[{row.owner}]" in row.state_dependencies


def test_dd108_pressure_stays_algebraic_with_single_top_anchor():
    contract = _contract()
    audit = audit_conserved_nu_pressure_dae_contract(contract)

    assert audit.top_pressure_remains_parameter
    assert audit.pressure_rate_count == 0
    assert audit.pressure_drop_count == len(VAPOR_LINKS) == 4
    assert not audit.explicit_vapor_inventory_present


def test_dd108_preserves_conservation_and_single_flow_ownership():
    audit = audit_conserved_nu_pressure_dae_contract(_contract())

    assert audit.component_conservation_passed
    assert audit.energy_conservation_passed
    assert audit.single_vapor_flow_owner_passed
    assert audit.storage_property_ownership_passed


def test_dd108_is_generic_in_component_count():
    components = ("light", "heavy")
    audit = audit_conserved_nu_pressure_dae_contract(
        build_conserved_nu_pressure_dae_contract(components)
    )

    assert audit.expected_count == 10 * len(components) + 16 == 36
    assert audit.solve_variable_count == audit.row_count == 36
    assert audit.structural_rank == 36
    assert audit.pass_gate


def test_dd108_remains_property_free_and_open_loop():
    contract = _contract()
    audit = audit_conserved_nu_pressure_dae_contract(contract)

    assert audit.preparation_only
    assert not audit.controller_rows
    assert not audit.profile_dependencies
    assert not audit.cap_or_relaxation_dependencies
    assert not contract.property_evaluation_attempted
    assert not contract.nonlinear_solve_attempted
    assert not contract.dynamic_integration_attempted


def test_dd108_rejects_missing_energy_rate_owner():
    contract = _contract()
    derivatives = tuple(
        variable
        for variable in contract.derivative_variables
        if variable.name != f"dU[{VOLUME_IDS[-1]}]/dt"
    )
    audit = audit_conserved_nu_pressure_dae_contract(
        replace(contract, derivative_variables=derivatives)
    )

    assert not audit.energy_rows_use_valid_storage_rates
    assert not audit.pass_gate


def test_dd108_rejects_fixed_pressure_storage_row():
    contract = _contract()
    rows = tuple(
        replace(
            row,
            solve_dependencies=tuple(
                item for item in row.solve_dependencies if not item.startswith("P[")
            ),
        )
        if row.block == "liquid_internal_energy_storage"
        and row.owner == VOLUME_IDS[1]
        else row
        for row in contract.rows
    )
    audit = audit_conserved_nu_pressure_dae_contract(replace(contract, rows=rows))

    assert not audit.storage_rows_use_live_lower_pressure
    assert not audit.pass_gate
