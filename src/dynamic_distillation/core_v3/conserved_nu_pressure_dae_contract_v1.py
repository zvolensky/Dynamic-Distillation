"""Structural conserved-N/U DAE contract with algebraic pressure.

This property-free module makes internal energy an independent conserved state
and registers one constitutive liquid-storage equation per physical volume.
It performs no provider evaluation, nonlinear solve, or integration.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import DAERow, SolveVariable
from dynamic_distillation.core_v3.pressure_implicit_dae_contract_v1 import (
    PressureLinkOwnership,
    build_pressure_implicit_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    VAPOR_LINKS,
    VOLUME_IDS,
)


CONTRACT_NAME = "Core V3 - Conserved N/U Algebraic-Pressure DAE Contract"
CONTRACT_VERSION = "core-v3-conserved-nu-pressure-dae-contract-v1"
TOP_VOLUME = VOLUME_IDS[0]


@dataclass(frozen=True)
class ConservedNUPressureDAEContract:
    name: str
    version: str
    component_names: tuple[str, ...]
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    pressure_link_ownership: tuple[PressureLinkOwnership, ...]
    storage_property_quantities: tuple[str, ...]
    storage_definition: str
    energy_balance_definition: str
    pressure_definition: str
    index_claim: str
    property_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class ConservedNUPressureDAEAudit:
    component_count: int
    component_inventory_state_count: int
    internal_energy_state_count: int
    state_coordinate_count: int
    component_rate_count: int
    internal_energy_rate_count: int
    derivative_variable_count: int
    algebraic_variable_count: int
    solve_variable_count: int
    row_count: int
    expected_count: int
    structural_rank: int
    structural_nullity: int
    zero_solve_columns: tuple[str, ...]
    zero_rows: tuple[str, ...]
    duplicate_variable_names: tuple[str, ...]
    unregistered_solve_dependencies: tuple[str, ...]
    unregistered_state_dependencies: tuple[str, ...]
    component_balance_count: int
    energy_balance_count: int
    storage_closure_count: int
    pressure_drop_count: int
    energy_rows_use_valid_storage_rates: bool
    storage_rows_cover_all_independent_energy_volumes: bool
    storage_rows_use_live_lower_pressure: bool
    top_pressure_remains_parameter: bool
    pressure_rate_count: int
    explicit_vapor_inventory_present: bool
    component_conservation_passed: bool
    energy_conservation_passed: bool
    single_vapor_flow_owner_passed: bool
    storage_property_ownership_passed: bool
    controller_rows: tuple[str, ...]
    profile_dependencies: tuple[str, ...]
    cap_or_relaxation_dependencies: tuple[str, ...]
    preparation_only: bool
    pass_gate: bool


def _internal_energy_state(volume: str) -> str:
    return f"U[{volume}]"


def _internal_energy_rate(volume: str) -> str:
    return f"dU[{volume}]/dt"


def _replace_energy_rate(row: DAERow) -> DAERow:
    if row.owner == TOP_VOLUME:
        return row
    dependencies = tuple(
        dependency
        for dependency in row.solve_dependencies
        if not dependency.startswith("dN[")
    )
    return replace(
        row,
        solve_dependencies=(_internal_energy_rate(row.owner), *dependencies),
    )


def build_conserved_nu_pressure_dae_contract(
    component_names: Sequence[str],
) -> ConservedNUPressureDAEContract:
    pressure = build_pressure_implicit_dae_contract(component_names)
    components = pressure.pressure_contract.base_contract.component_names
    energy_state_volumes = VOLUME_IDS[1:]
    energy_states = tuple(
        _internal_energy_state(volume) for volume in energy_state_volumes
    )
    energy_rates = tuple(
        SolveVariable(
            _internal_energy_rate(volume),
            "internal_energy_rate",
            volume,
        )
        for volume in energy_state_volumes
    )
    physical_rows = tuple(
        _replace_energy_rate(row) if row.block == "energy_balance" else row
        for row in pressure.rows
    )
    storage_rows = tuple(
        DAERow(
            name=f"liquid_internal_energy_storage[{volume}]",
            block="liquid_internal_energy_storage",
            owner=volume,
            solve_dependencies=tuple(
                dependency
                for dependency in (f"T[{volume}]", f"P[{volume}]")
                if not (volume == TOP_VOLUME and dependency.startswith("P["))
            ),
            state_dependencies=(
                *(f"N[{volume},{component}]" for component in components),
                _internal_energy_state(volume),
            ),
        )
        for volume in energy_state_volumes
    )
    return ConservedNUPressureDAEContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        component_names=components,
        state_coordinates=(*pressure.state_coordinates, *energy_states),
        derivative_variables=(*pressure.derivative_variables, *energy_rates),
        algebraic_variables=pressure.algebraic_variables,
        rows=(*physical_rows, *storage_rows),
        pressure_link_ownership=pressure.pressure_link_ownership,
        storage_property_quantities=("phase_enthalpy", "liquid_density"),
        storage_definition=(
            "For each lower pressure-owning volume, U[j] = NL[j] * "
            "(hL(T[j],P[j],x[j]) - P[j]/rhoL(T[j],P[j],x[j])). "
            "Top U is derived on its fixed-pressure bubble manifold."
        ),
        energy_balance_definition=(
            "Lower dU[j]/dt equals the exact enthalpy-flow balance. The top "
            "energy balance uses the exact fixed-pressure saturation-manifold "
            "dU_top/dN gradient; no timestep or moving-pressure gradient is used."
        ),
        pressure_definition=pressure.pressure_contract.pressure_reconstruction,
        index_claim=(
            "property-free square implicit-index-1 candidate; live leading-"
            "Jacobian and constraint-manifold rank remain unclaimed"
        ),
    )


def _incidence(
    contract: ConservedNUPressureDAEContract,
) -> tuple[csr_matrix, tuple[str, ...]]:
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    matrix = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                matrix[row_index, index[dependency]] = 1
    return csr_matrix(matrix), names


def audit_conserved_nu_pressure_dae_contract(
    contract: ConservedNUPressureDAEContract,
) -> ConservedNUPressureDAEAudit:
    matrix, names = _incidence(contract)
    state_names = tuple(contract.state_coordinates)
    solve_known = set(names)
    state_known = set(state_names)
    solve_dependencies = {
        dependency for row in contract.rows for dependency in row.solve_dependencies
    }
    state_dependencies = {
        dependency for row in contract.rows for dependency in row.state_dependencies
    }
    unregistered_solve = tuple(sorted(solve_dependencies - solve_known))
    unregistered_state = tuple(sorted(state_dependencies - state_known))
    duplicate_names = tuple(
        sorted({name for name in names if names.count(name) > 1})
    )
    row_counts = np.asarray(matrix.getnnz(axis=1)).reshape((-1,))
    column_counts = np.asarray(matrix.getnnz(axis=0)).reshape((-1,))
    rank = int(structural_rank(matrix))

    component_states = tuple(name for name in state_names if name.startswith("N["))
    energy_states = tuple(name for name in state_names if name.startswith("U["))
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
    pressure_rates = tuple(
        variable
        for variable in contract.derivative_variables
        if variable.name.startswith("dP[")
    )
    component_rows = tuple(row for row in contract.rows if row.block == "component_balance")
    energy_rows = tuple(row for row in contract.rows if row.block == "energy_balance")
    storage_rows = tuple(
        row for row in contract.rows if row.block == "liquid_internal_energy_storage"
    )
    pressure_rows = tuple(row for row in contract.rows if row.block == "vapor_pressure_drop")
    energy_rate_names = {variable.name for variable in energy_rates}
    energy_rate_ownership = len(energy_rows) == len(VOLUME_IDS) and all(
        (
            row.owner == TOP_VOLUME
            and {
                dependency
                for dependency in row.solve_dependencies
                if dependency.startswith("dN[")
            }
            == {
                f"dN[{TOP_VOLUME},{component}]/dt"
                for component in contract.component_names
            }
            and not any(
                dependency.startswith("dU[")
                for dependency in row.solve_dependencies
            )
        )
        or (
            row.owner != TOP_VOLUME
            and {
                dependency
                for dependency in row.solve_dependencies
                if dependency.startswith("d")
            }
            == {_internal_energy_rate(row.owner)}
            and _internal_energy_rate(row.owner) in energy_rate_names
        )
        for row in energy_rows
    )
    storage_coverage = (
        {row.owner for row in storage_rows} == set(VOLUME_IDS[1:])
        and {row.state_dependencies[-1] for row in storage_rows} == set(energy_states)
    )
    storage_lower_pressure = all(
        row.owner != TOP_VOLUME and f"P[{row.owner}]" in row.solve_dependencies
        for row in storage_rows
    )
    top_pressure_parameter = (
        not any(variable.name == f"P[{TOP_VOLUME}]" for variable in contract.algebraic_variables)
        and all(
            any(variable.name == f"P[{volume}]" for variable in contract.algebraic_variables)
            for volume in VOLUME_IDS[1:]
        )
    )
    all_dependencies = tuple(
        dependency
        for row in contract.rows
        for dependency in (*row.solve_dependencies, *row.state_dependencies)
    )
    controllers = tuple(row.name for row in contract.rows if "controller" in row.block)
    profiles = tuple(sorted({item for item in all_dependencies if "profile" in item.lower()}))
    caps = tuple(
        sorted(
            {
                item
                for item in all_dependencies
                if any(token in item.lower() for token in ("cap", "relax", "previous"))
            }
        )
    )
    explicit_vapor_inventory = any(name.startswith("NV[") for name in state_names)
    component_conservation = (
        len(component_rows) == len(VOLUME_IDS) * len(contract.component_names)
        and all(any(dependency.startswith("dN[") for dependency in row.solve_dependencies) for row in component_rows)
    )
    energy_conservation = (
        len(energy_rows) == len(VOLUME_IDS)
        and energy_rate_ownership
        and any(variable.name == "Q_C" for variable in contract.algebraic_variables)
    )
    vapor_owner = (
        sum(variable.block == "energy_owned_vapor_flow" for variable in contract.algebraic_variables)
        == len(VAPOR_LINKS)
    )
    storage_properties = contract.storage_property_quantities == (
        "phase_enthalpy",
        "liquid_density",
    )
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    expected = 10 * len(contract.component_names) + 16
    pass_gate = bool(
        len(names) == len(contract.rows) == expected
        and rank == expected
        and not np.any(row_counts == 0)
        and not np.any(column_counts == 0)
        and not duplicate_names
        and not unregistered_solve
        and not unregistered_state
        and len(component_states) == len(VOLUME_IDS) * len(contract.component_names)
        and len(energy_states) == len(VOLUME_IDS) - 1
        and len(component_rates) == len(component_states)
        and len(energy_rates) == len(energy_states)
        and energy_rate_ownership
        and storage_coverage
        and storage_lower_pressure
        and top_pressure_parameter
        and not pressure_rates
        and not explicit_vapor_inventory
        and component_conservation
        and energy_conservation
        and vapor_owner
        and storage_properties
        and not controllers
        and not profiles
        and not caps
        and preparation_only
    )
    return ConservedNUPressureDAEAudit(
        component_count=len(contract.component_names),
        component_inventory_state_count=len(component_states),
        internal_energy_state_count=len(energy_states),
        state_coordinate_count=len(state_names),
        component_rate_count=len(component_rates),
        internal_energy_rate_count=len(energy_rates),
        derivative_variable_count=len(contract.derivative_variables),
        algebraic_variable_count=len(contract.algebraic_variables),
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        expected_count=expected,
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        zero_solve_columns=tuple(names[index] for index in np.flatnonzero(column_counts == 0)),
        zero_rows=tuple(contract.rows[index].name for index in np.flatnonzero(row_counts == 0)),
        duplicate_variable_names=duplicate_names,
        unregistered_solve_dependencies=unregistered_solve,
        unregistered_state_dependencies=unregistered_state,
        component_balance_count=len(component_rows),
        energy_balance_count=len(energy_rows),
        storage_closure_count=len(storage_rows),
        pressure_drop_count=len(pressure_rows),
        energy_rows_use_valid_storage_rates=energy_rate_ownership,
        storage_rows_cover_all_independent_energy_volumes=storage_coverage,
        storage_rows_use_live_lower_pressure=storage_lower_pressure,
        top_pressure_remains_parameter=top_pressure_parameter,
        pressure_rate_count=len(pressure_rates),
        explicit_vapor_inventory_present=explicit_vapor_inventory,
        component_conservation_passed=component_conservation,
        energy_conservation_passed=energy_conservation,
        single_vapor_flow_owner_passed=vapor_owner,
        storage_property_ownership_passed=storage_properties,
        controller_rows=controllers,
        profile_dependencies=profiles,
        cap_or_relaxation_dependencies=caps,
        preparation_only=preparation_only,
        pass_gate=pass_gate,
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "ConservedNUPressureDAEAudit",
    "ConservedNUPressureDAEContract",
    "audit_conserved_nu_pressure_dae_contract",
    "build_conserved_nu_pressure_dae_contract",
]
