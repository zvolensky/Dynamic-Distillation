"""Structural contract for conserved-N/U pressure-consistent initialization.

The initializer selects one point on an exact conservation and DAE manifold.
This module registers ownership and incidence only; it performs no property
evaluation, nonlinear solve, timestep, or dynamic integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.sparse import bmat, csr_matrix, diags
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    ConservedNUPressureDAEContract,
    build_conserved_nu_pressure_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import SolveVariable
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS


CONTRACT_NAME = "Core V3 - Conserved N/U Pressure Initializer Contract"
CONTRACT_VERSION = "core-v3-conserved-nu-pressure-initializer-contract-v1"
TOP_VOLUME = VOLUME_IDS[0]
TERMINAL_VOLUMES = (VOLUME_IDS[0], VOLUME_IDS[-1])


@dataclass(frozen=True)
class InitializerConstraint:
    name: str
    block: str
    owner: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class SelectionObjectiveTerm:
    name: str
    block: str
    dependencies: tuple[str, ...]
    purpose: str


@dataclass(frozen=True)
class ConservedNUPressureInitializerContract:
    name: str
    version: str
    pressure_dae: ConservedNUPressureDAEContract
    state_variables: tuple[SolveVariable, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    constraints: tuple[InitializerConstraint, ...]
    selection_objective: tuple[SelectionObjectiveTerm, ...]
    component_inventory_reference: str
    stored_energy_reference: str
    terminal_inventory_reference: str
    state_parameterization: str
    solve_form: str
    property_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class ConservedNUPressureInitializerAudit:
    state_variable_count: int
    component_inventory_state_count: int
    internal_energy_state_count: int
    derivative_variable_count: int
    component_rate_count: int
    internal_energy_rate_count: int
    algebraic_variable_count: int
    primal_variable_count: int
    dae_constraint_count: int
    storage_closure_count: int
    component_inventory_constraint_count: int
    stored_energy_constraint_count: int
    terminal_inventory_constraint_count: int
    equality_constraint_count: int
    equality_structural_rank: int
    feasible_manifold_dimension: int
    kkt_dimension: int
    kkt_structural_rank: int
    kkt_structural_nullity: int
    zero_primal_columns: tuple[str, ...]
    zero_constraint_rows: tuple[str, ...]
    duplicate_variable_names: tuple[str, ...]
    unregistered_dependencies: tuple[str, ...]
    objective_uncovered_variables: tuple[str, ...]
    global_component_coverage_passed: bool
    global_energy_ownership_passed: bool
    terminal_total_not_component_lock_passed: bool
    exact_dae_constraints_inherited: bool
    corrected_internal_energy_ownership_passed: bool
    no_timestep_dependency: bool
    preparation_only: bool
    pass_gate: bool


def _state_variable(name: str) -> SolveVariable:
    owner = name[2:-1].split(",", maxsplit=1)[0]
    block = "component_inventory" if name.startswith("N[") else "internal_energy"
    return SolveVariable(name, block, owner)


def _initializer_constraints(
    pressure_dae: ConservedNUPressureDAEContract,
) -> tuple[InitializerConstraint, ...]:
    components = pressure_dae.component_names
    constraints = [
        InitializerConstraint(
            name=row.name,
            block=row.block,
            owner=row.owner,
            dependencies=tuple(
                dict.fromkeys((*row.state_dependencies, *row.solve_dependencies))
            ),
        )
        for row in pressure_dae.rows
    ]
    constraints.extend(
        InitializerConstraint(
            name=f"global_component_inventory[{component}]",
            block="global_component_inventory",
            owner="whole_column",
            dependencies=tuple(
                f"N[{volume},{component}]" for volume in VOLUME_IDS
            ),
        )
        for component in components
    )
    constraints.append(
        InitializerConstraint(
            name="global_stored_energy",
            block="global_stored_energy",
            owner="whole_column",
            dependencies=(
                *(f"N[{TOP_VOLUME},{component}]" for component in components),
                f"T[{TOP_VOLUME}]",
                *(f"U[{volume}]" for volume in VOLUME_IDS[1:]),
            ),
        )
    )
    constraints.extend(
        InitializerConstraint(
            name=f"terminal_total_inventory[{volume}]",
            block="terminal_total_inventory",
            owner=volume,
            dependencies=tuple(
                f"N[{volume},{component}]" for component in components
            ),
        )
        for volume in TERMINAL_VOLUMES
    )
    return tuple(constraints)


def build_conserved_nu_pressure_initializer_contract(
    component_names: Sequence[str],
) -> ConservedNUPressureInitializerContract:
    pressure_dae = build_conserved_nu_pressure_dae_contract(component_names)
    states = tuple(_state_variable(name) for name in pressure_dae.state_coordinates)
    derivatives = pressure_dae.derivative_variables
    algebraic = pressure_dae.algebraic_variables
    objective = (
        SelectionObjectiveTerm(
            name="minimum_scaled_conserved_rate",
            block="conserved_rate_norm",
            dependencies=tuple(variable.name for variable in derivatives),
            purpose="prefer the cleanest dynamically admissible start",
        ),
        SelectionObjectiveTerm(
            name="minimum_scaled_conserved_state_movement",
            block="conserved_state_movement_norm",
            dependencies=tuple(variable.name for variable in states),
            purpose="keep component and energy storage near the accepted reference",
        ),
        SelectionObjectiveTerm(
            name="minimum_scaled_algebraic_movement",
            block="algebraic_movement_norm",
            dependencies=tuple(variable.name for variable in algebraic),
            purpose="select one nearby pressure-consistent algebraic state",
        ),
    )
    return ConservedNUPressureInitializerContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        pressure_dae=pressure_dae,
        state_variables=states,
        derivative_variables=derivatives,
        algebraic_variables=algebraic,
        constraints=_initializer_constraints(pressure_dae),
        selection_objective=objective,
        component_inventory_reference=(
            "For each component, sum_j N[j,k] equals the DD-094 whole-column total"
        ),
        stored_energy_reference=(
            "U_top(N_top,T_top,P_top fixed) plus the four independent lower U[j] "
            "states equals the exact DD-094 whole-column stored energy"
        ),
        terminal_inventory_reference=(
            "The reflux-drum and combined-reboiler/sump total molar inventories "
            "equal their DD-094 values; terminal compositions remain free"
        ),
        state_parameterization=(
            "strictly positive component inventories plus four bounded affine "
            "lower internal-energy states; conservation, storage, DAE, and "
            "terminal ownership are exact equality constraints"
        ),
        solve_form=(
            "one equality-constrained normalized quadratic selection over N, "
            "four lower U, dN/dt, four lower dU/dt, and algebraic z; all 46 "
            "conserved-N/U pressure DAE rows remain exact constraints"
        ),
    )


def _incidence(
    contract: ConservedNUPressureInitializerContract,
) -> tuple[csr_matrix, tuple[str, ...]]:
    variables = (
        *contract.state_variables,
        *contract.derivative_variables,
        *contract.algebraic_variables,
    )
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    matrix = np.zeros((len(contract.constraints), len(names)), dtype=np.int8)
    for row_index, row in enumerate(contract.constraints):
        for dependency in row.dependencies:
            if dependency in index:
                matrix[row_index, index[dependency]] = 1
    return csr_matrix(matrix), names


def audit_conserved_nu_pressure_initializer_contract(
    contract: ConservedNUPressureInitializerContract,
) -> ConservedNUPressureInitializerAudit:
    matrix, names = _incidence(contract)
    known = set(names)
    dependencies = {
        dependency for row in contract.constraints for dependency in row.dependencies
    }
    unregistered = tuple(sorted(dependencies - known))
    duplicates = tuple(sorted({name for name in names if names.count(name) > 1}))
    column_counts = np.asarray(matrix.getnnz(axis=0)).reshape((-1,))
    row_counts = np.asarray(matrix.getnnz(axis=1)).reshape((-1,))
    equality_rank = int(structural_rank(matrix))
    objective_dependencies = {
        dependency
        for term in contract.selection_objective
        for dependency in term.dependencies
    }
    uncovered = tuple(sorted(known - objective_dependencies))
    hessian = diags(np.ones(len(names), dtype=np.int8), format="csr")
    zero = csr_matrix((len(contract.constraints), len(contract.constraints)))
    kkt = bmat(((hessian, matrix.transpose()), (matrix, zero)), format="csr")
    kkt_rank = int(structural_rank(kkt))

    components = contract.pressure_dae.component_names
    component_states = tuple(
        variable for variable in contract.state_variables if variable.block == "component_inventory"
    )
    energy_states = tuple(
        variable for variable in contract.state_variables if variable.block == "internal_energy"
    )
    component_rates = tuple(
        variable
        for variable in contract.derivative_variables
        if variable.block == "component_inventory_rate"
    )
    energy_rates = tuple(
        variable
        for variable in contract.derivative_variables
        if variable.block == "internal_energy_rate"
    )
    component_rows = tuple(
        row for row in contract.constraints if row.block == "global_component_inventory"
    )
    energy_rows = tuple(
        row for row in contract.constraints if row.block == "global_stored_energy"
    )
    terminal_rows = tuple(
        row for row in contract.constraints if row.block == "terminal_total_inventory"
    )
    storage_rows = tuple(
        row
        for row in contract.constraints
        if row.block == "liquid_internal_energy_storage"
    )
    component_coverage = len(component_rows) == len(components) and all(
        set(row.dependencies)
        == {f"N[{volume},{component}]" for volume in VOLUME_IDS}
        for row, component in zip(component_rows, components, strict=True)
    )
    expected_energy = {
        *(f"N[{TOP_VOLUME},{component}]" for component in components),
        f"T[{TOP_VOLUME}]",
        *(f"U[{volume}]" for volume in VOLUME_IDS[1:]),
    }
    energy_ownership = (
        len(energy_rows) == 1 and set(energy_rows[0].dependencies) == expected_energy
    )
    terminal_total_only = len(terminal_rows) == len(TERMINAL_VOLUMES) and all(
        row.owner in TERMINAL_VOLUMES
        and len(row.dependencies) == len(components)
        and not any(component in row.name for component in components)
        for row in terminal_rows
    )
    dae_count = len(contract.pressure_dae.rows)
    exact_dae = tuple(row.name for row in contract.constraints[:dae_count]) == tuple(
        row.name for row in contract.pressure_dae.rows
    )
    corrected_energy = (
        {variable.name for variable in energy_states}
        == {f"U[{volume}]" for volume in VOLUME_IDS[1:]}
        and {variable.name for variable in energy_rates}
        == {f"dU[{volume}]/dt" for volume in VOLUME_IDS[1:]}
        and len(storage_rows) == len(VOLUME_IDS) - 1
        and not any(variable.name == f"U[{TOP_VOLUME}]" for variable in contract.state_variables)
    )
    no_timestep = not any(
        token in value.lower()
        for value in (
            contract.state_parameterization,
            contract.solve_form,
            *(row.name for row in contract.constraints),
        )
        for token in ("timestep", "step_seconds", "backward_euler", "backward-euler")
    )
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    feasible_dimension = len(names) - equality_rank
    expected_constraints = dae_count + len(components) + 1 + len(TERMINAL_VOLUMES)
    expected_dimension = 4 * len(components) + 1
    pass_gate = bool(
        len(contract.state_variables) == 5 * len(components) + 4
        and len(contract.derivative_variables) == len(contract.state_variables)
        and len(contract.constraints) == expected_constraints
        and equality_rank == len(contract.constraints)
        and feasible_dimension == expected_dimension
        and kkt.shape[0] == kkt_rank
        and not np.any(column_counts == 0)
        and not np.any(row_counts == 0)
        and not duplicates
        and not unregistered
        and not uncovered
        and len(component_states) == 5 * len(components)
        and len(component_rates) == len(component_states)
        and component_coverage
        and energy_ownership
        and terminal_total_only
        and exact_dae
        and corrected_energy
        and no_timestep
        and preparation_only
    )
    return ConservedNUPressureInitializerAudit(
        state_variable_count=len(contract.state_variables),
        component_inventory_state_count=len(component_states),
        internal_energy_state_count=len(energy_states),
        derivative_variable_count=len(contract.derivative_variables),
        component_rate_count=len(component_rates),
        internal_energy_rate_count=len(energy_rates),
        algebraic_variable_count=len(contract.algebraic_variables),
        primal_variable_count=len(names),
        dae_constraint_count=dae_count,
        storage_closure_count=len(storage_rows),
        component_inventory_constraint_count=len(component_rows),
        stored_energy_constraint_count=len(energy_rows),
        terminal_inventory_constraint_count=len(terminal_rows),
        equality_constraint_count=len(contract.constraints),
        equality_structural_rank=equality_rank,
        feasible_manifold_dimension=feasible_dimension,
        kkt_dimension=kkt.shape[0],
        kkt_structural_rank=kkt_rank,
        kkt_structural_nullity=kkt.shape[0] - kkt_rank,
        zero_primal_columns=tuple(
            names[index] for index in np.flatnonzero(column_counts == 0)
        ),
        zero_constraint_rows=tuple(
            contract.constraints[index].name
            for index in np.flatnonzero(row_counts == 0)
        ),
        duplicate_variable_names=duplicates,
        unregistered_dependencies=unregistered,
        objective_uncovered_variables=uncovered,
        global_component_coverage_passed=component_coverage,
        global_energy_ownership_passed=energy_ownership,
        terminal_total_not_component_lock_passed=terminal_total_only,
        exact_dae_constraints_inherited=exact_dae,
        corrected_internal_energy_ownership_passed=corrected_energy,
        no_timestep_dependency=no_timestep,
        preparation_only=preparation_only,
        pass_gate=pass_gate,
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "TERMINAL_VOLUMES",
    "ConservedNUPressureInitializerAudit",
    "ConservedNUPressureInitializerContract",
    "InitializerConstraint",
    "SelectionObjectiveTerm",
    "audit_conserved_nu_pressure_initializer_contract",
    "build_conserved_nu_pressure_initializer_contract",
]
