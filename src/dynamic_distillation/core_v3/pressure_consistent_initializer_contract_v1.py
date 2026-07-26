"""Structural contract for pressure-consistent Core V3 initialization.

The initializer is an equality-constrained minimum-rate/minimum-movement
problem. This module registers ownership and incidence only; it performs no
property evaluation, nonlinear solve, or dynamic integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.sparse import bmat, csr_matrix, diags
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import SolveVariable
from dynamic_distillation.core_v3.pressure_implicit_dae_contract_v1 import (
    PressureImplicitDAEContract,
    build_pressure_implicit_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS


CONTRACT_NAME = "Core V3 - Pressure-Consistent Initializer Contract"
CONTRACT_VERSION = "core-v3-pressure-consistent-initializer-contract-v1"
TERMINAL_VOLUMES = ("reflux_drum", "combined_reboiler_sump")


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
class PressureConsistentInitializerContract:
    name: str
    version: str
    pressure_dae: PressureImplicitDAEContract
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
class PressureConsistentInitializerAudit:
    state_variable_count: int
    derivative_variable_count: int
    algebraic_variable_count: int
    primal_variable_count: int
    dae_constraint_count: int
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
    global_energy_coverage_passed: bool
    terminal_total_not_component_lock_passed: bool
    exact_dae_constraints_inherited: bool
    no_timestep_dependency: bool
    preparation_only: bool
    pass_gate: bool


def _owner_from_inventory_name(name: str) -> str:
    if not name.startswith("N[") or not name.endswith("]"):
        raise ValueError(f"invalid inventory coordinate {name!r}")
    return name[2:-1].split(",", maxsplit=1)[0]


def _initializer_constraints(
    pressure_dae: PressureImplicitDAEContract,
) -> tuple[InitializerConstraint, ...]:
    components = pressure_dae.pressure_contract.base_contract.component_names
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
    energy_dependencies = (
        *pressure_dae.state_coordinates,
        *(
            variable.name
            for variable in pressure_dae.algebraic_variables
            if variable.block in {"temperature", "algebraic_pressure"}
        ),
    )
    constraints.append(
        InitializerConstraint(
            name="global_stored_energy",
            block="global_stored_energy",
            owner="whole_column",
            dependencies=tuple(dict.fromkeys(energy_dependencies)),
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


def build_pressure_consistent_initializer_contract(
    component_names: Sequence[str],
) -> PressureConsistentInitializerContract:
    pressure_dae = build_pressure_implicit_dae_contract(component_names)
    states = tuple(
        SolveVariable(name, "component_inventory", _owner_from_inventory_name(name))
        for name in pressure_dae.state_coordinates
    )
    derivatives = pressure_dae.derivative_variables
    algebraic = pressure_dae.algebraic_variables
    objective = (
        SelectionObjectiveTerm(
            name="minimum_scaled_inventory_rate",
            block="inventory_rate_norm",
            dependencies=tuple(variable.name for variable in derivatives),
            purpose="prefer the cleanest dynamically admissible start",
        ),
        SelectionObjectiveTerm(
            name="minimum_scaled_inventory_redistribution",
            block="state_movement_norm",
            dependencies=tuple(variable.name for variable in states),
            purpose="keep the conserved state near DD-094",
        ),
        SelectionObjectiveTerm(
            name="minimum_scaled_algebraic_movement",
            block="algebraic_movement_norm",
            dependencies=tuple(variable.name for variable in algebraic),
            purpose="select a unique nearby algebraic state without relaxing equations",
        ),
    )
    return PressureConsistentInitializerContract(
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
            "sum_j U_liquid(N[j,:],T[j],P[j]) equals the exact DD-094 stored-energy total"
        ),
        terminal_inventory_reference=(
            "The reflux-drum and combined-reboiler/sump total molar inventories "
            "equal their DD-094 values; terminal compositions remain free"
        ),
        state_parameterization=(
            "strictly positive component inventories; conservation and terminal "
            "ownership are exact equality constraints, not penalty residuals"
        ),
        solve_form=(
            "one equality-constrained normalized quadratic minimization over N, "
            "dN/dt, and algebraic z; all 42 DAE rows remain exact constraints"
        ),
    )


def _incidence(
    contract: PressureConsistentInitializerContract,
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


def audit_pressure_consistent_initializer_contract(
    contract: PressureConsistentInitializerContract,
) -> PressureConsistentInitializerAudit:
    matrix, names = _incidence(contract)
    known = set(names)
    dependencies = {
        dependency
        for row in contract.constraints
        for dependency in row.dependencies
    }
    unregistered = tuple(sorted(dependencies - known))
    duplicate_names = tuple(
        sorted({name for name in names if names.count(name) > 1})
    )
    column_counts = np.asarray(matrix.getnnz(axis=0)).reshape((-1,))
    row_counts = np.asarray(matrix.getnnz(axis=1)).reshape((-1,))
    equality_rank = int(structural_rank(matrix))
    objective_dependencies = {
        dependency
        for term in contract.selection_objective
        for dependency in term.dependencies
    }
    uncovered = tuple(sorted(known - objective_dependencies))

    # A positive diagonal objective Hessian plus a full-row-rank equality
    # Jacobian is the frozen structural KKT candidate for the later live audit.
    hessian = diags(np.ones(len(names), dtype=np.int8), format="csr")
    zero = csr_matrix((len(contract.constraints), len(contract.constraints)))
    kkt = bmat(((hessian, matrix.transpose()), (matrix, zero)), format="csr")
    kkt_rank = int(structural_rank(kkt))

    components = contract.pressure_dae.pressure_contract.base_contract.component_names
    component_rows = tuple(
        row for row in contract.constraints if row.block == "global_component_inventory"
    )
    energy_rows = tuple(
        row for row in contract.constraints if row.block == "global_stored_energy"
    )
    terminal_rows = tuple(
        row for row in contract.constraints if row.block == "terminal_total_inventory"
    )
    component_coverage = len(component_rows) == len(components) and all(
        set(row.dependencies)
        == {f"N[{volume},{component}]" for volume in VOLUME_IDS}
        for row, component in zip(component_rows, components, strict=True)
    )
    expected_energy_dependencies = set(contract.pressure_dae.state_coordinates) | {
        variable.name
        for variable in contract.algebraic_variables
        if variable.block in {"temperature", "algebraic_pressure"}
    }
    energy_coverage = (
        len(energy_rows) == 1
        and set(energy_rows[0].dependencies) == expected_energy_dependencies
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
    no_timestep = not any(
        token in value.lower()
        for value in (
            contract.state_parameterization,
            contract.solve_form,
            *(row.name for row in contract.constraints),
        )
        for token in (
            "timestep",
            "step_seconds",
            "backward_euler",
            "backward-euler",
        )
    )
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    expected_constraints = dae_count + len(components) + 1 + len(TERMINAL_VOLUMES)
    feasible_dimension = len(names) - equality_rank
    pass_gate = bool(
        len(contract.state_variables) == len(VOLUME_IDS) * len(components)
        and len(contract.derivative_variables) == len(contract.state_variables)
        and len(contract.algebraic_variables) == 27
        and len(contract.constraints) == expected_constraints
        and equality_rank == len(contract.constraints)
        and feasible_dimension == 9
        and kkt.shape[0] == kkt_rank
        and not np.any(column_counts == 0)
        and not np.any(row_counts == 0)
        and not duplicate_names
        and not unregistered
        and not uncovered
        and component_coverage
        and energy_coverage
        and terminal_total_only
        and exact_dae
        and no_timestep
        and preparation_only
    )
    return PressureConsistentInitializerAudit(
        state_variable_count=len(contract.state_variables),
        derivative_variable_count=len(contract.derivative_variables),
        algebraic_variable_count=len(contract.algebraic_variables),
        primal_variable_count=len(names),
        dae_constraint_count=dae_count,
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
        duplicate_variable_names=duplicate_names,
        unregistered_dependencies=unregistered,
        objective_uncovered_variables=uncovered,
        global_component_coverage_passed=component_coverage,
        global_energy_coverage_passed=energy_coverage,
        terminal_total_not_component_lock_passed=terminal_total_only,
        exact_dae_constraints_inherited=exact_dae,
        no_timestep_dependency=no_timestep,
        preparation_only=preparation_only,
        pass_gate=pass_gate,
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "TERMINAL_VOLUMES",
    "InitializerConstraint",
    "PressureConsistentInitializerAudit",
    "PressureConsistentInitializerContract",
    "SelectionObjectiveTerm",
    "audit_pressure_consistent_initializer_contract",
    "build_pressure_consistent_initializer_contract",
]
