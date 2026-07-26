from dataclasses import replace

from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    TERMINAL_VOLUMES,
    audit_conserved_nu_pressure_initializer_contract,
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS


COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def _contract():
    return build_conserved_nu_pressure_initializer_contract(COMPONENTS)


def test_dd111_initializer_constraint_and_kkt_ledgers_are_full_rank():
    audit = audit_conserved_nu_pressure_initializer_contract(_contract())

    assert audit.state_variable_count == 19
    assert audit.derivative_variable_count == 19
    assert audit.algebraic_variable_count == 27
    assert audit.primal_variable_count == 65
    assert audit.equality_constraint_count == audit.equality_structural_rank == 52
    assert audit.feasible_manifold_dimension == 13
    assert audit.kkt_dimension == audit.kkt_structural_rank == 117
    assert audit.kkt_structural_nullity == 0
    assert audit.pass_gate


def test_dd111_preserves_all_46_conserved_pressure_dae_rows():
    contract = _contract()
    audit = audit_conserved_nu_pressure_initializer_contract(contract)

    assert audit.dae_constraint_count == 46
    assert audit.storage_closure_count == 4
    assert tuple(row.name for row in contract.constraints[:46]) == tuple(
        row.name for row in contract.pressure_dae.rows
    )
    assert audit.exact_dae_constraints_inherited


def test_dd111_owns_only_four_lower_internal_energy_states_and_rates():
    contract = _contract()
    audit = audit_conserved_nu_pressure_initializer_contract(contract)

    assert audit.internal_energy_state_count == audit.internal_energy_rate_count == 4
    assert {variable.name for variable in contract.state_variables if variable.block == "internal_energy"} == {
        f"U[{volume}]" for volume in VOLUME_IDS[1:]
    }
    assert not any(variable.name == f"U[{VOLUME_IDS[0]}]" for variable in contract.state_variables)
    assert audit.corrected_internal_energy_ownership_passed


def test_dd111_global_energy_uses_derived_top_and_independent_lower_u():
    contract = _contract()
    row = next(row for row in contract.constraints if row.block == "global_stored_energy")

    assert set(row.dependencies) == {
        *(f"N[{VOLUME_IDS[0]},{component}]" for component in COMPONENTS),
        f"T[{VOLUME_IDS[0]}]",
        *(f"U[{volume}]" for volume in VOLUME_IDS[1:]),
    }


def test_dd111_component_and_terminal_constraints_preserve_global_ownership():
    contract = _contract()
    audit = audit_conserved_nu_pressure_initializer_contract(contract)
    component_rows = tuple(
        row for row in contract.constraints if row.block == "global_component_inventory"
    )
    terminal_rows = tuple(
        row for row in contract.constraints if row.block == "terminal_total_inventory"
    )

    assert len(component_rows) == len(COMPONENTS)
    assert audit.global_component_coverage_passed
    assert {row.owner for row in terminal_rows} == set(TERMINAL_VOLUMES)
    assert audit.terminal_total_not_component_lock_passed


def test_dd111_objective_covers_every_primal_without_relaxing_constraints():
    contract = _contract()
    audit = audit_conserved_nu_pressure_initializer_contract(contract)

    assert {term.block for term in contract.selection_objective} == {
        "conserved_rate_norm",
        "conserved_state_movement_norm",
        "algebraic_movement_norm",
    }
    assert not audit.objective_uncovered_variables
    assert "exact equality constraints" in contract.state_parameterization


def test_dd111_is_generic_for_two_components():
    audit = audit_conserved_nu_pressure_initializer_contract(
        build_conserved_nu_pressure_initializer_contract(("light", "heavy"))
    )

    assert audit.primal_variable_count == 50
    assert audit.equality_constraint_count == audit.equality_structural_rank == 41
    assert audit.feasible_manifold_dimension == 9
    assert audit.kkt_dimension == audit.kkt_structural_rank == 91
    assert audit.pass_gate


def test_dd111_has_no_timestep_property_solve_or_integration():
    contract = _contract()
    audit = audit_conserved_nu_pressure_initializer_contract(contract)

    assert audit.no_timestep_dependency
    assert audit.preparation_only
    assert not contract.property_evaluation_attempted
    assert not contract.nonlinear_solve_attempted
    assert not contract.dynamic_integration_attempted


def test_dd111_rejects_missing_lower_energy_state_in_global_energy():
    contract = _contract()
    constraints = tuple(
        replace(
            row,
            dependencies=tuple(
                item for item in row.dependencies if item != f"U[{VOLUME_IDS[-1]}]"
            ),
        )
        if row.block == "global_stored_energy"
        else row
        for row in contract.constraints
    )
    audit = audit_conserved_nu_pressure_initializer_contract(
        replace(contract, constraints=constraints)
    )

    assert not audit.global_energy_ownership_passed
    assert not audit.pass_gate


def test_dd111_rejects_component_locked_terminal_inventory():
    contract = _contract()
    constraints = tuple(
        replace(
            row,
            name=f"terminal_component_inventory[{row.owner},{COMPONENTS[0]}]",
            dependencies=(f"N[{row.owner},{COMPONENTS[0]}]",),
        )
        if row.block == "terminal_total_inventory" and row.owner == TERMINAL_VOLUMES[0]
        else row
        for row in contract.constraints
    )
    audit = audit_conserved_nu_pressure_initializer_contract(
        replace(contract, constraints=constraints)
    )

    assert not audit.terminal_total_not_component_lock_passed
    assert not audit.pass_gate
