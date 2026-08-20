from dataclasses import replace

import pytest

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import SolveVariable
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    PhysicalOwnership,
    audit_vapor_holdup_dae_contract,
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)


COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


def _volumes(column):
    return {volume: 100.0 for volume in column.volume_ids}


def _contract():
    column = build_column_topology()
    return build_vapor_holdup_dae_contract(
        COMPONENTS,
        topology=build_vapor_holdup_topology(
            column=column,
            vapor_volume_ft3=_volumes(column),
        ),
    )


def test_vapor_holdup_successor_is_square_full_rank_and_property_free():
    contract = _contract()
    audit = audit_vapor_holdup_dae_contract(contract)

    assert audit.volume_count == 5
    assert audit.component_count == 3
    assert audit.state_coordinate_count == 30
    assert audit.liquid_state_count == audit.vapor_state_count == 15
    assert audit.derivative_variable_count == 30
    assert audit.algebraic_variable_count == 33
    assert audit.solve_variable_count == audit.row_count == 63
    assert audit.structural_rank == 63
    assert audit.structural_nullity == 0
    assert audit.preparation_only
    assert audit.pass_gate


def test_vapor_holdup_successor_scales_generically():
    components = ("a", "b", "c", "d")
    column = build_column_topology(
        rectifying_volume_count=3,
        stripping_volume_count=2,
    )
    vapor_topology = build_vapor_holdup_topology(
        column=column,
        vapor_volume_ft3=_volumes(column),
    )
    contract = build_vapor_holdup_dae_contract(
        components,
        topology=vapor_topology,
    )
    audit = audit_vapor_holdup_dae_contract(contract)
    expected = 3 * 8 * 4 + 4 * 8 - 2

    assert audit.volume_count == 8
    assert audit.solve_variable_count == audit.row_count == expected == 126
    assert audit.structural_rank == expected
    assert audit.pass_gate


def test_vapor_composition_is_derived_only_from_conserved_inventory():
    contract = _contract()
    audit = audit_vapor_holdup_dae_contract(contract)

    assert contract.vapor_composition_definition == (
        "y[j,k]=NV[j,k]/sum_k(NV[j,k])"
    )
    assert audit.independent_vapor_composition_variables == ()
    assert all(
        not variable.name.startswith("y[")
        for variable in contract.algebraic_variables
    )


def test_every_vapor_state_has_a_rate_balance_volume_and_energy_owner():
    audit = audit_vapor_holdup_dae_contract(_contract())

    assert audit.unowned_vapor_states == ()
    assert audit.missing_vapor_volume_declarations == ()
    assert audit.vapor_balance_count == 15
    assert audit.vapor_volume_eos_count == 5
    assert audit.total_energy_storage_includes_both_phases
    assert audit.every_energy_row_uses_vapor_inventory


def test_pressure_phase_transfer_and_provider_ownership_are_complete():
    audit = audit_vapor_holdup_dae_contract(_contract())

    assert audit.pressure_drop_count == 4
    assert audit.pressure_anchor_count == 1
    assert audit.pressure_ownership_consistent
    assert audit.phase_transfer_count == 15
    assert audit.phase_transfer_registry_consistent
    assert audit.phase_transfer_cancellation_passed
    assert audit.total_component_conservation_passed
    assert audit.provider_ownership_complete
    assert not audit.fallback_permitted


def test_vapor_volume_declaration_rejects_missing_or_nonpositive_volume():
    column = build_column_topology()
    missing = {volume: 10.0 for volume in column.volume_ids[:-1]}
    nonpositive = {volume: 10.0 for volume in column.volume_ids}
    nonpositive[column.feed_volume] = 0.0

    with pytest.raises(ValueError, match="must explicitly declare"):
        build_vapor_holdup_topology(column=column)
    with pytest.raises(ValueError, match="one positive finite value"):
        build_vapor_holdup_topology(
            column=column,
            vapor_volume_ft3=missing,
        )
    with pytest.raises(ValueError, match="one positive finite value"):
        build_vapor_holdup_topology(
            column=column,
            vapor_volume_ft3=nonpositive,
        )


def test_audit_rejects_an_independent_vapor_composition_variable():
    contract = _contract()
    bad = replace(
        contract,
        algebraic_variables=(
            *contract.algebraic_variables,
            SolveVariable("y[feed_tray,Propane]", "vapor_composition", "feed_tray"),
        ),
    )
    audit = audit_vapor_holdup_dae_contract(bad)

    assert audit.independent_vapor_composition_variables == (
        "y[feed_tray,Propane]",
    )
    assert not audit.pass_gate


def test_audit_rejects_missing_vapor_balance_ownership():
    contract = _contract()
    target = "vapor_component_balance[feed_tray,Propane]"
    bad = replace(
        contract,
        rows=tuple(row for row in contract.rows if row.name != target),
    )
    audit = audit_vapor_holdup_dae_contract(bad)

    assert "NV[feed_tray,Propane]" in audit.unowned_vapor_states
    assert not audit.pass_gate


def test_audit_rejects_missing_phase_transfer_unknown():
    contract = _contract()
    target = "M_VL[feed_tray,Propane]"
    bad = replace(
        contract,
        algebraic_variables=tuple(
            variable
            for variable in contract.algebraic_variables
            if variable.name != target
        ),
    )
    audit = audit_vapor_holdup_dae_contract(bad)

    assert target in audit.unregistered_solve_dependencies
    assert not audit.phase_transfer_registry_consistent
    assert not audit.pass_gate


def test_audit_rejects_duplicate_pressure_owner_and_liquid_only_energy():
    contract = _contract()
    duplicate = replace(
        contract,
        physical_ownership=(
            *contract.physical_ownership,
            PhysicalOwnership("pressure", "profile", "prescribed_profile"),
        ),
    )
    liquid_only = replace(
        contract,
        total_internal_energy_storage="U_total[j]=U_L[j]; U_L=NL*(hL-P*vL)",
    )

    duplicate_audit = audit_vapor_holdup_dae_contract(duplicate)
    liquid_only_audit = audit_vapor_holdup_dae_contract(liquid_only)
    assert duplicate_audit.duplicate_ownership_quantities == ("pressure",)
    assert not duplicate_audit.pass_gate
    assert not liquid_only_audit.total_energy_storage_includes_both_phases
    assert not liquid_only_audit.pass_gate
