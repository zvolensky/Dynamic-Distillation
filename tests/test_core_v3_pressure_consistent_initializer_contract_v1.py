from dataclasses import replace

from dynamic_distillation.core_v3.pressure_consistent_initializer_contract_v1 import (
    TERMINAL_VOLUMES,
    audit_pressure_consistent_initializer_contract,
    build_pressure_consistent_initializer_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS


COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def _contract():
    return build_pressure_consistent_initializer_contract(COMPONENTS)


def test_dd106_initializer_has_full_row_rank_and_full_rank_kkt_pattern():
    audit = audit_pressure_consistent_initializer_contract(_contract())

    assert audit.state_variable_count == 15
    assert audit.derivative_variable_count == 15
    assert audit.algebraic_variable_count == 27
    assert audit.primal_variable_count == 57
    assert audit.equality_constraint_count == 48
    assert audit.equality_structural_rank == 48
    assert audit.feasible_manifold_dimension == 9
    assert audit.kkt_dimension == audit.kkt_structural_rank == 105
    assert audit.kkt_structural_nullity == 0
    assert audit.pass_gate


def test_dd106_preserves_all_pressure_dae_rows_as_exact_constraints():
    contract = _contract()
    audit = audit_pressure_consistent_initializer_contract(contract)
    dae_names = tuple(row.name for row in contract.pressure_dae.rows)

    assert tuple(row.name for row in contract.constraints[:42]) == dae_names
    assert audit.dae_constraint_count == 42
    assert audit.exact_dae_constraints_inherited


def test_dd106_global_component_constraints_cover_every_volume():
    contract = _contract()
    rows = tuple(
        row
        for row in contract.constraints
        if row.block == "global_component_inventory"
    )

    assert len(rows) == len(COMPONENTS)
    for row, component in zip(rows, COMPONENTS, strict=True):
        assert set(row.dependencies) == {
            f"N[{volume},{component}]" for volume in VOLUME_IDS
        }


def test_dd106_energy_constraint_uses_all_inventories_temperatures_and_pressures():
    contract = _contract()
    row = next(
        row for row in contract.constraints if row.block == "global_stored_energy"
    )

    assert set(contract.pressure_dae.state_coordinates) <= set(row.dependencies)
    assert {
        variable.name
        for variable in contract.algebraic_variables
        if variable.block in {"temperature", "algebraic_pressure"}
    } <= set(row.dependencies)


def test_dd106_terminal_constraints_preserve_level_not_composition():
    contract = _contract()
    audit = audit_pressure_consistent_initializer_contract(contract)
    rows = tuple(
        row
        for row in contract.constraints
        if row.block == "terminal_total_inventory"
    )

    assert {row.owner for row in rows} == set(TERMINAL_VOLUMES)
    assert all(len(row.dependencies) == len(COMPONENTS) for row in rows)
    assert audit.terminal_total_not_component_lock_passed


def test_dd106_objective_covers_every_primal_without_relaxing_constraints():
    contract = _contract()
    audit = audit_pressure_consistent_initializer_contract(contract)

    assert {term.block for term in contract.selection_objective} == {
        "inventory_rate_norm",
        "state_movement_norm",
        "algebraic_movement_norm",
    }
    assert not audit.objective_uncovered_variables
    assert "exact equality constraints" in contract.state_parameterization


def test_dd106_has_no_timestep_solver_or_property_execution():
    contract = _contract()
    audit = audit_pressure_consistent_initializer_contract(contract)

    assert audit.no_timestep_dependency
    assert audit.preparation_only
    assert not contract.property_evaluation_attempted
    assert not contract.nonlinear_solve_attempted
    assert not contract.dynamic_integration_attempted


def test_dd106_rejects_missing_global_component_constraint():
    contract = _contract()
    constraints = tuple(
        row
        for row in contract.constraints
        if row.name != f"global_component_inventory[{COMPONENTS[0]}]"
    )
    audit = audit_pressure_consistent_initializer_contract(
        replace(contract, constraints=constraints)
    )

    assert not audit.global_component_coverage_passed
    assert not audit.pass_gate


def test_dd106_rejects_component_locked_terminal_inventory():
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
    audit = audit_pressure_consistent_initializer_contract(
        replace(contract, constraints=constraints)
    )

    assert not audit.terminal_total_not_component_lock_passed
    assert not audit.pass_gate
