"""Structural contract for the Core V3 reduced dynamic DAE.

The module registers derivative and algebraic ownership only. It performs no
property evaluation, mass-matrix evaluation, nonlinear solve, or integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from .provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    LIQUID_LINKS,
    VAPOR_LINKS,
    VOLUME_IDS,
)


CONTRACT_NAME = "Core V3 - Reduced Energy-Owned Dynamic DAE Contract"
CONTRACT_VERSION = "core-v3-dynamic-dae-contract-v1"


@dataclass(frozen=True)
class SolveVariable:
    name: str
    block: str
    owner: str


@dataclass(frozen=True)
class DAERow:
    name: str
    block: str
    owner: str
    solve_dependencies: tuple[str, ...]
    state_dependencies: tuple[str, ...]


@dataclass(frozen=True)
class DynamicDAEContract:
    component_names: tuple[str, ...]
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]
    accepted_root_artifact: str
    internal_energy_storage: str
    index_claim: str
    property_evaluation_attempted: bool = False
    mass_matrix_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class DynamicDAEAudit:
    component_count: int
    state_coordinate_count: int
    derivative_variable_count: int
    algebraic_variable_count: int
    solve_variable_count: int
    row_count: int
    expected_solve_count: int
    structural_rank: int
    structural_nullity: int
    zero_solve_columns: tuple[str, ...]
    zero_rows: tuple[str, ...]
    unregistered_solve_dependencies: tuple[str, ...]
    unregistered_state_dependencies: tuple[str, ...]
    component_balance_count: int
    energy_balance_count: int
    full_fugacity_count: int
    francis_count: int
    condenser_bubble_count: int
    vapor_link_count: int
    condenser_duty_count: int
    independent_internal_energy_coordinates: tuple[str, ...]
    temperature_derivative_variables: tuple[str, ...]
    terminal_amount_constraint_rows: tuple[str, ...]
    controller_rows: tuple[str, ...]
    profile_dependencies: tuple[str, ...]
    fixed_product_parameters_present: bool
    component_conservation_passed: bool
    energy_conservation_passed: bool
    accepted_root_declared: bool
    preparation_only: bool
    pass_gate: bool


def _validate_components(component_names: Sequence[str]) -> tuple[str, ...]:
    components = tuple(str(value).strip() for value in component_names)
    if len(components) < 2:
        raise ValueError("Core V3 requires at least two components")
    if any(not value for value in components):
        raise ValueError("component names must be nonempty")
    if len(set(components)) != len(components):
        raise ValueError("component names must be unique")
    return components


def _independent_coordinates(
    components: tuple[str, ...], prefix: str, volume: str
) -> tuple[str, ...]:
    return tuple(
        f"{prefix}[{volume},{component}]" for component in components[:-1]
    )


def _inventory_coordinates(
    components: tuple[str, ...], volume: str
) -> tuple[str, ...]:
    return tuple(f"N[{volume},{component}]" for component in components)


def build_dynamic_dae_contract(
    component_names: Sequence[str],
) -> DynamicDAEContract:
    components = _validate_components(component_names)
    states = tuple(
        name
        for volume in VOLUME_IDS
        for name in _inventory_coordinates(components, volume)
    )
    derivatives = tuple(
        SolveVariable(f"d{name}/dt", "component_inventory_rate", volume)
        for volume in VOLUME_IDS
        for name in _inventory_coordinates(components, volume)
    )

    temperatures = tuple(
        SolveVariable(f"T[{volume}]", "temperature", volume)
        for volume in VOLUME_IDS
    )
    stage_vapor = tuple(
        SolveVariable(name, "equilibrium_vapor_composition", volume)
        for volume in EQUILIBRIUM_VOLUME_IDS
        for name in _independent_coordinates(components, "y", volume)
    )
    liquid_flows = tuple(
        SolveVariable(f"L[{volume}]", "francis_liquid_flow", volume)
        for volume in HYDRAULIC_VOLUME_IDS
    )
    vapor_flows = tuple(
        SolveVariable(symbol, "energy_owned_vapor_flow", source)
        for source, _destination, symbol in VAPOR_LINKS
    )
    bubble_vapor = tuple(
        SolveVariable(
            name,
            "condenser_incipient_vapor",
            "total_condenser_reflux_drum_boundary",
        )
        for name in _independent_coordinates(
            components, "y_bubble", "reflux_drum"
        )
    )
    condenser_duty = (
        SolveVariable(
            "Q_C",
            "energy_owned_condenser_duty",
            "total_condenser_reflux_drum_boundary",
        ),
    )
    algebraic = (
        *temperatures,
        *stage_vapor,
        *liquid_flows,
        *vapor_flows,
        *bubble_vapor,
        *condenser_duty,
    )

    all_stage_y = {
        volume: _independent_coordinates(components, "y", volume)
        for volume in EQUILIBRIUM_VOLUME_IDS
    }
    derivative_by_volume = {
        volume: tuple(
            f"d{name}/dt" for name in _inventory_coordinates(components, volume)
        )
        for volume in VOLUME_IDS
    }
    l_rect, l_feed, l_strip = (entry.name for entry in liquid_flows)
    v_bottom, v_strip, v_feed, v_rect = (entry.name for entry in vapor_flows)
    flow_dependencies = {
        "reflux_drum": (v_rect,),
        "rectifying_tray": (l_rect, v_feed, v_rect),
        "feed_tray": (l_rect, l_feed, v_strip, v_feed),
        "stripping_tray": (l_feed, l_strip, v_bottom, v_strip),
        "combined_reboiler_sump": (l_strip, v_bottom),
    }
    vapor_composition_dependencies = {
        "reflux_drum": all_stage_y["rectifying_tray"],
        "rectifying_tray": (
            *all_stage_y["feed_tray"],
            *all_stage_y["rectifying_tray"],
        ),
        "feed_tray": (
            *all_stage_y["stripping_tray"],
            *all_stage_y["feed_tray"],
        ),
        "stripping_tray": (
            *all_stage_y["combined_reboiler_sump"],
            *all_stage_y["stripping_tray"],
        ),
        "combined_reboiler_sump": all_stage_y[
            "combined_reboiler_sump"
        ],
    }
    state_volume_dependencies = {
        "reflux_drum": ("reflux_drum",),
        "rectifying_tray": ("reflux_drum", "rectifying_tray"),
        "feed_tray": ("rectifying_tray", "feed_tray"),
        "stripping_tray": ("feed_tray", "stripping_tray"),
        "combined_reboiler_sump": (
            "stripping_tray",
            "combined_reboiler_sump",
        ),
    }
    energy_temperature_dependencies = {
        "reflux_drum": ("T[reflux_drum]", "T[rectifying_tray]"),
        "rectifying_tray": (
            "T[reflux_drum]",
            "T[rectifying_tray]",
            "T[feed_tray]",
        ),
        "feed_tray": (
            "T[rectifying_tray]",
            "T[feed_tray]",
            "T[stripping_tray]",
        ),
        "stripping_tray": (
            "T[feed_tray]",
            "T[stripping_tray]",
            "T[combined_reboiler_sump]",
        ),
        "combined_reboiler_sump": (
            "T[stripping_tray]",
            "T[combined_reboiler_sump]",
        ),
    }
    rows: list[DAERow] = []

    for volume in VOLUME_IDS:
        balance_states = tuple(
            state
            for dependency_volume in state_volume_dependencies[volume]
            for state in _inventory_coordinates(components, dependency_volume)
        )
        for component, derivative in zip(
            components, derivative_by_volume[volume], strict=True
        ):
            dependencies = [derivative]
            dependencies.extend(vapor_composition_dependencies[volume])
            dependencies.extend(flow_dependencies[volume])
            rows.append(
                DAERow(
                    f"component_balance[{volume},{component}]",
                    "component_balance",
                    volume,
                    tuple(dict.fromkeys(dependencies)),
                    balance_states,
                )
            )

    for volume in VOLUME_IDS:
        dependencies = [*derivative_by_volume[volume]]
        dependencies.extend(energy_temperature_dependencies[volume])
        dependencies.extend(vapor_composition_dependencies[volume])
        dependencies.extend(flow_dependencies[volume])
        if volume == "reflux_drum":
            dependencies.append("Q_C")
        rows.append(
            DAERow(
                f"energy_balance[{volume}]",
                "energy_balance",
                volume,
                tuple(dict.fromkeys(dependencies)),
                tuple(
                    state
                    for dependency_volume in state_volume_dependencies[volume]
                    for state in _inventory_coordinates(
                        components, dependency_volume
                    )
                ),
            )
        )

    for volume in EQUILIBRIUM_VOLUME_IDS:
        dependencies = (f"T[{volume}]", *all_stage_y[volume])
        for component in components:
            rows.append(
                DAERow(
                    f"full_phase_equilibrium[{volume},{component}]",
                    "full_phase_equilibrium",
                    volume,
                    dependencies,
                    _inventory_coordinates(components, volume),
                )
            )

    for volume in HYDRAULIC_VOLUME_IDS:
        rows.append(
            DAERow(
                f"francis_hydraulics[{volume}]",
                "francis_hydraulics",
                volume,
                (f"L[{volume}]", f"T[{volume}]"),
                _inventory_coordinates(components, volume),
            )
        )

    bubble_names = tuple(entry.name for entry in bubble_vapor)
    for component in components:
        rows.append(
            DAERow(
                f"condenser_bubble_fugacity[{component}]",
                "condenser_bubble_fugacity",
                "total_condenser_reflux_drum_boundary",
                ("T[reflux_drum]", *bubble_names),
                _inventory_coordinates(components, "reflux_drum"),
            )
        )

    return DynamicDAEContract(
        component_names=components,
        state_coordinates=states,
        derivative_variables=derivatives,
        algebraic_variables=algebraic,
        rows=tuple(rows),
        fixed_parameters=(
            "ordered_pressure_profile",
            "feed_rate_composition_enthalpy",
            "R",
            "D_dd094_root",
            "B_dd094_root",
            "Q_R",
            "hydraulic_geometry",
        ),
        accepted_root_artifact="logs/dd094_core_v3_steady_root_20260725.json",
        internal_energy_storage=(
            "U[j]=NL[j]*uL(T[j],P[j],x[j]); dU[j]/dt is assembled by "
            "the provider-consistent chain rule against dN[j,k]/dt"
        ),
        index_claim=(
            "structural implicit-index-1 candidate; numerical leading-"
            "Jacobian rank and consistent-derivative audits remain required"
        ),
    )


def _incidence(contract: DynamicDAEContract) -> tuple[csr_matrix, tuple[str, ...]]:
    variables = (
        *contract.derivative_variables,
        *contract.algebraic_variables,
    )
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    matrix = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                matrix[row_index, index[dependency]] = 1
    return csr_matrix(matrix), names


def audit_dynamic_dae_contract(
    contract: DynamicDAEContract,
) -> DynamicDAEAudit:
    matrix, solve_names = _incidence(contract)
    registered_solve = set(solve_names)
    registered_state = set(contract.state_coordinates)
    unregistered_solve = tuple(
        sorted(
            {
                dependency
                for row in contract.rows
                for dependency in row.solve_dependencies
                if dependency not in registered_solve
            }
        )
    )
    unregistered_state = tuple(
        sorted(
            {
                dependency
                for row in contract.rows
                for dependency in row.state_dependencies
                if dependency not in registered_state
            }
        )
    )
    column_counts = np.asarray(matrix.sum(axis=0)).ravel()
    row_counts = np.asarray(matrix.sum(axis=1)).ravel()
    zero_columns = tuple(
        name for name, count in zip(solve_names, column_counts, strict=True) if not count
    )
    zero_rows = tuple(
        row.name
        for row, count in zip(contract.rows, row_counts, strict=True)
        if not count
    )
    rank = int(structural_rank(matrix))
    expected = 10 * len(contract.component_names) + 8
    independent_u = tuple(
        name for name in contract.state_coordinates if name.startswith("U[")
    )
    temperature_derivatives = tuple(
        variable.name
        for variable in contract.derivative_variables
        if variable.name.startswith("dT[")
    )
    terminal_rows = tuple(
        row.name for row in contract.rows if row.block == "terminal_amount_specification"
    )
    controller_rows = tuple(
        row.name for row in contract.rows if "controller" in row.block
    )
    profile_dependencies = tuple(
        sorted(
            dependency
            for row in contract.rows
            for dependency in (*row.solve_dependencies, *row.state_dependencies)
            if "profile" in dependency.lower()
        )
    )
    fixed_product_parameters = {
        "D_dd094_root",
        "B_dd094_root",
    }.issubset(contract.fixed_parameters)
    internal_links = (*LIQUID_LINKS, *VAPOR_LINKS)
    stream_coefficients = {
        symbol: (-1, 1) for _source, _destination, symbol in internal_links
    }
    component_conservation = all(
        sum(coefficients) == 0
        for coefficients in stream_coefficients.values()
    )
    energy_conservation = component_conservation and "Q_C" in registered_solve
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.mass_matrix_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    solve_count = len(solve_names)
    row_count = len(contract.rows)
    pass_gate = bool(
        solve_count == row_count == expected
        and rank == expected
        and not zero_columns
        and not zero_rows
        and not unregistered_solve
        and not unregistered_state
        and not independent_u
        and not temperature_derivatives
        and not terminal_rows
        and not controller_rows
        and not profile_dependencies
        and fixed_product_parameters
        and component_conservation
        and energy_conservation
        and bool(contract.accepted_root_artifact)
        and preparation_only
    )
    count = lambda block: sum(row.block == block for row in contract.rows)
    return DynamicDAEAudit(
        component_count=len(contract.component_names),
        state_coordinate_count=len(contract.state_coordinates),
        derivative_variable_count=len(contract.derivative_variables),
        algebraic_variable_count=len(contract.algebraic_variables),
        solve_variable_count=solve_count,
        row_count=row_count,
        expected_solve_count=expected,
        structural_rank=rank,
        structural_nullity=solve_count - rank,
        zero_solve_columns=zero_columns,
        zero_rows=zero_rows,
        unregistered_solve_dependencies=unregistered_solve,
        unregistered_state_dependencies=unregistered_state,
        component_balance_count=count("component_balance"),
        energy_balance_count=count("energy_balance"),
        full_fugacity_count=count("full_phase_equilibrium"),
        francis_count=count("francis_hydraulics"),
        condenser_bubble_count=count("condenser_bubble_fugacity"),
        vapor_link_count=sum(
            variable.block == "energy_owned_vapor_flow"
            for variable in contract.algebraic_variables
        ),
        condenser_duty_count=sum(
            variable.block == "energy_owned_condenser_duty"
            for variable in contract.algebraic_variables
        ),
        independent_internal_energy_coordinates=independent_u,
        temperature_derivative_variables=temperature_derivatives,
        terminal_amount_constraint_rows=terminal_rows,
        controller_rows=controller_rows,
        profile_dependencies=profile_dependencies,
        fixed_product_parameters_present=fixed_product_parameters,
        component_conservation_passed=component_conservation,
        energy_conservation_passed=energy_conservation,
        accepted_root_declared=bool(contract.accepted_root_artifact),
        preparation_only=preparation_only,
        pass_gate=pass_gate,
    )
