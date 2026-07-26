"""Structural contract for the Core V3 pressure-enabled implicit DAE."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    contract_sparsity_pattern,
    greedy_column_groups,
)
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import DAERow, SolveVariable
from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    PressureLayerContract,
    TOP_PRESSURE_PARAMETER,
    build_pressure_layer_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    VAPOR_LINKS,
    VOLUME_IDS,
)


CONTRACT_NAME = "Core V3 - Pressure-Enabled Implicit DAE Contract"
CONTRACT_VERSION = "core-v3-pressure-implicit-dae-contract-v1"
TERMINAL_BOTTOM_VOLUME = "combined_reboiler_sump"


@dataclass(frozen=True)
class PressureLinkOwnership:
    source: str
    destination: str
    vapor_flow: str
    role: str
    includes_liquid_head: bool


@dataclass(frozen=True)
class PressureImplicitDAEContract:
    name: str
    version: str
    pressure_contract: PressureLayerContract
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    pressure_link_ownership: tuple[PressureLinkOwnership, ...]
    endpoint_inventory_map: str
    energy_storage: str
    index_claim: str
    property_evaluation_attempted: bool = False
    mass_matrix_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class PressureImplicitDAEAudit:
    state_coordinate_count: int
    derivative_variable_count: int
    algebraic_variable_count: int
    solve_variable_count: int
    row_count: int
    structural_rank: int
    structural_nullity: int
    zero_solve_columns: tuple[str, ...]
    zero_rows: tuple[str, ...]
    unregistered_solve_dependencies: tuple[str, ...]
    unregistered_state_dependencies: tuple[str, ...]
    pressure_variable_count: int
    pressure_rate_variable_count: int
    pressure_drop_row_count: int
    terminal_dry_only_link_count: int
    tray_liquid_head_link_count: int
    terminal_pressure_rate_couplings: tuple[str, ...]
    tray_pressure_rate_coupling_count: int
    color_count: int
    color_groups: tuple[tuple[int, ...], ...]
    color_conflict_free: bool
    component_conservation_inherited: bool
    energy_conservation_inherited: bool
    top_pressure_anchor_present: bool
    fixed_product_rates_present: bool
    controller_rows: tuple[str, ...]
    profile_dependencies: tuple[str, ...]
    cap_or_relaxation_dependencies: tuple[str, ...]
    explicit_vapor_inventory_present: bool
    preparation_only: bool
    pass_gate: bool


def _terminal_pressure_row_name() -> str:
    for source, destination, _vapor_flow in VAPOR_LINKS:
        if source == TERMINAL_BOTTOM_VOLUME:
            return f"vapor_pressure_drop[{source}->{destination}]"
    raise RuntimeError("terminal reboiler/sump vapor link is not registered")


def build_pressure_implicit_dae_contract(
    component_names: Sequence[str],
) -> PressureImplicitDAEContract:
    pressure = build_pressure_layer_contract(component_names)
    terminal_row_name = _terminal_pressure_row_name()
    rows = tuple(
        replace(row, state_dependencies=())
        if row.name == terminal_row_name
        else row
        for row in pressure.rows
    )
    pressure = replace(
        pressure,
        rows=rows,
        pressure_reconstruction=(
            "P[reflux_drum] is fixed; four lower pressures are simultaneous "
            "algebraic unknowns. The terminal reboiler/sump return uses dry "
            "resistance only; three physical tray links use dry resistance "
            "plus liquid head."
        ),
    )
    link_ownership = tuple(
        PressureLinkOwnership(
            source=source,
            destination=destination,
            vapor_flow=vapor_flow,
            role=(
                "terminal_reboiler_return"
                if source == TERMINAL_BOTTOM_VOLUME
                else "physical_tray_link"
            ),
            includes_liquid_head=source != TERMINAL_BOTTOM_VOLUME,
        )
        for source, destination, vapor_flow in VAPOR_LINKS
    )
    return PressureImplicitDAEContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        pressure_contract=pressure,
        state_coordinates=pressure.base_contract.state_coordinates,
        derivative_variables=pressure.derivative_variables,
        algebraic_variables=pressure.algebraic_variables,
        rows=rows,
        pressure_link_ownership=link_ownership,
        endpoint_inventory_map=(
            "N_next = N_prev * exp(dt * nominal_rate / N_prev); physical "
            "inventory rates are recomputed from the exact endpoint difference"
        ),
        energy_storage=(
            "U_next = NL_next * (hL(T_next,P_next,x_next) - "
            "P_next/rhoL(T_next,P_next,x_next)); energy rows use the exact "
            "backward-Euler storage difference"
        ),
        index_claim=(
            "property-free square implicit-index-1 candidate; numerical index "
            "and leading-Jacobian acceptance remain unclaimed"
        ),
    )


def _dependency_audit(
    contract: PressureImplicitDAEContract,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    solve_names = {
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    }
    state_names = set(contract.state_coordinates)
    unregistered_solve = {
        dependency
        for row in contract.rows
        for dependency in row.solve_dependencies
        if dependency not in solve_names
    }
    unregistered_state = {
        dependency
        for row in contract.rows
        for dependency in row.state_dependencies
        if dependency not in state_names
    }
    return tuple(sorted(unregistered_solve)), tuple(sorted(unregistered_state))


def audit_pressure_implicit_dae_contract(
    contract: PressureImplicitDAEContract,
) -> PressureImplicitDAEAudit:
    pattern, names = contract_sparsity_pattern(
        contract.pressure_contract,
        include_state_rate_dependencies=True,
    )
    sparse = csr_matrix(pattern)
    rank = int(structural_rank(sparse))
    column_counts = np.asarray(sparse.sum(axis=0)).ravel()
    row_counts = np.asarray(sparse.sum(axis=1)).ravel()
    zero_columns = tuple(
        name for name, count in zip(names, column_counts, strict=True) if not count
    )
    zero_rows = tuple(
        row.name
        for row, count in zip(contract.rows, row_counts, strict=True)
        if not count
    )
    unregistered_solve, unregistered_state = _dependency_audit(contract)
    groups = greedy_column_groups(pattern)
    color_conflict_free = True
    for group in groups:
        occupied = np.concatenate(
            [np.flatnonzero(pattern[:, column]) for column in group]
        )
        if np.unique(occupied).size != occupied.size:
            color_conflict_free = False
            break

    pressure_rows = tuple(
        row for row in contract.rows if row.block == "vapor_pressure_drop"
    )
    terminal_row_name = _terminal_pressure_row_name()
    terminal_row = next(row for row in pressure_rows if row.name == terminal_row_name)
    terminal_rate_couplings = tuple(
        names[column]
        for column in np.flatnonzero(
            pattern[contract.rows.index(terminal_row)]
        )
        if names[column].startswith("dN[")
    )
    tray_pressure_rate_coupling_count = sum(
        1
        for row in pressure_rows
        if row.name != terminal_row_name
        for dependency in row.state_dependencies
        if f"d{dependency}/dt" in names
    )
    terminal_dry = tuple(
        link
        for link in contract.pressure_link_ownership
        if link.role == "terminal_reboiler_return" and not link.includes_liquid_head
    )
    tray_head = tuple(
        link
        for link in contract.pressure_link_ownership
        if link.role == "physical_tray_link" and link.includes_liquid_head
    )
    pressure_variables = tuple(
        variable
        for variable in contract.algebraic_variables
        if variable.block == "algebraic_pressure"
    )
    pressure_rate_variables = tuple(
        variable
        for variable in contract.derivative_variables
        if variable.name.startswith("dP[")
    )
    base = contract.pressure_contract.base_contract
    component_conservation = (
        sum(row.block == "component_balance" for row in contract.rows)
        == len(VOLUME_IDS) * len(base.component_names)
    )
    energy_conservation = (
        sum(row.block == "energy_balance" for row in contract.rows)
        == len(VOLUME_IDS)
        and any(variable.name == "Q_C" for variable in contract.algebraic_variables)
    )
    controller_rows = tuple(
        row.name for row in contract.rows if "controller" in row.block.lower()
    )
    dependencies = tuple(
        dependency
        for row in contract.rows
        for dependency in (*row.solve_dependencies, *row.state_dependencies)
    )
    profiles = tuple(
        sorted({value for value in dependencies if "profile" in value.lower()})
    )
    caps = tuple(
        sorted(
            {
                value
                for value in dependencies
                if any(
                    token in value.lower()
                    for token in ("cap", "relax", "previous")
                )
            }
        )
    )
    explicit_vapor_inventory = any(
        name.startswith("NV[") for name in contract.state_coordinates
    )
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.mass_matrix_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    expected = 10 * len(base.component_names) + 12
    fixed_product_rates = all(
        parameter in contract.pressure_contract.fixed_parameters
        for parameter in ("D_dd094_root", "B_dd094_root")
    )
    pass_gate = bool(
        len(names) == len(contract.rows) == expected
        and rank == expected
        and not zero_columns
        and not zero_rows
        and not unregistered_solve
        and not unregistered_state
        and len(contract.state_coordinates) == len(contract.derivative_variables)
        and len(pressure_variables) == len(VOLUME_IDS) - 1
        and not pressure_rate_variables
        and len(pressure_rows) == len(VAPOR_LINKS)
        and len(terminal_dry) == 1
        and len(tray_head) == len(VAPOR_LINKS) - 1
        and not terminal_row.state_dependencies
        and not terminal_rate_couplings
        and tray_pressure_rate_coupling_count
        == (len(VAPOR_LINKS) - 1) * len(base.component_names)
        and color_conflict_free
        and len(groups) < len(names)
        and component_conservation
        and energy_conservation
        and TOP_PRESSURE_PARAMETER in contract.pressure_contract.fixed_parameters
        and fixed_product_rates
        and not controller_rows
        and not profiles
        and not caps
        and not explicit_vapor_inventory
        and preparation_only
    )
    return PressureImplicitDAEAudit(
        state_coordinate_count=len(contract.state_coordinates),
        derivative_variable_count=len(contract.derivative_variables),
        algebraic_variable_count=len(contract.algebraic_variables),
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        zero_solve_columns=zero_columns,
        zero_rows=zero_rows,
        unregistered_solve_dependencies=unregistered_solve,
        unregistered_state_dependencies=unregistered_state,
        pressure_variable_count=len(pressure_variables),
        pressure_rate_variable_count=len(pressure_rate_variables),
        pressure_drop_row_count=len(pressure_rows),
        terminal_dry_only_link_count=len(terminal_dry),
        tray_liquid_head_link_count=len(tray_head),
        terminal_pressure_rate_couplings=terminal_rate_couplings,
        tray_pressure_rate_coupling_count=tray_pressure_rate_coupling_count,
        color_count=len(groups),
        color_groups=groups,
        color_conflict_free=color_conflict_free,
        component_conservation_inherited=component_conservation,
        energy_conservation_inherited=energy_conservation,
        top_pressure_anchor_present=(
            TOP_PRESSURE_PARAMETER in contract.pressure_contract.fixed_parameters
        ),
        fixed_product_rates_present=fixed_product_rates,
        controller_rows=controller_rows,
        profile_dependencies=profiles,
        cap_or_relaxation_dependencies=caps,
        explicit_vapor_inventory_present=explicit_vapor_inventory,
        preparation_only=preparation_only,
        pass_gate=pass_gate,
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "PressureImplicitDAEAudit",
    "PressureImplicitDAEContract",
    "PressureLinkOwnership",
    "TERMINAL_BOTTOM_VOLUME",
    "audit_pressure_implicit_dae_contract",
    "build_pressure_implicit_dae_contract",
]
