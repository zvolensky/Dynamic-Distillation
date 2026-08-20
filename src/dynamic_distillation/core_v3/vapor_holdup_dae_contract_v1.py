"""Property-free structural contract for the Core V3 vapor-holdup successor.

The accepted Core V3 V1 contracts remain reduced-order historical artifacts.
This module starts a separately versioned equilibrium-stage architecture with
conserved resident liquid and vapor component inventories. It performs no
property evaluation, residual evaluation, nonlinear solve, or integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix

from .dynamic_dae_contract_v1 import DAERow, SolveVariable
from .provider_governed_registry_v1 import (
    ColumnTopology,
    DEFAULT_TOPOLOGY,
)
from .structural_rank_v1 import structural_rank_fast


CONTRACT_NAME = "Core V3 - Conserved Vapor-Holdup DAE Successor"
CONTRACT_VERSION = "core-v3-vapor-holdup-dae-successor-v1"
TOP_PRESSURE_PARAMETER = "P_anchor[reflux_drum]"


@dataclass(frozen=True)
class PhysicalOwnership:
    quantity: str
    owner: str
    equation_family: str


@dataclass(frozen=True)
class PropertyAuthority:
    quantity: str
    provider_interface: str
    basis: str
    fallback_permitted: bool = False


@dataclass(frozen=True)
class PhaseTransferContribution:
    transfer: str
    phase: str
    coefficient: int


@dataclass(frozen=True)
class VaporHoldupTopology:
    column: ColumnTopology
    vapor_control_volume_ids: tuple[str, ...]
    vapor_volume_ft3_by_volume: tuple[tuple[str, float], ...]
    pressure_anchor_volume: str
    pressure_owner: str
    vapor_volume_model: str
    terminal_vapor_boundaries: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class VaporHoldupDAEContract:
    name: str
    version: str
    component_names: tuple[str, ...]
    topology: VaporHoldupTopology
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]
    physical_ownership: tuple[PhysicalOwnership, ...]
    property_authorities: tuple[PropertyAuthority, ...]
    phase_transfer_contributions: tuple[PhaseTransferContribution, ...]
    total_internal_energy_storage: str
    vapor_composition_definition: str
    implicit_endpoint_coupling: str
    property_evaluation_attempted: bool = False
    mass_matrix_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class VaporHoldupDAEAudit:
    volume_count: int
    component_count: int
    state_coordinate_count: int
    liquid_state_count: int
    vapor_state_count: int
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
    missing_vapor_volume_declarations: tuple[str, ...]
    extra_vapor_volume_declarations: tuple[str, ...]
    nonpositive_vapor_volume_parameters: tuple[str, ...]
    missing_ownership_quantities: tuple[str, ...]
    duplicate_ownership_quantities: tuple[str, ...]
    independent_vapor_composition_variables: tuple[str, ...]
    unowned_vapor_states: tuple[str, ...]
    vapor_balance_count: int
    liquid_balance_count: int
    equilibrium_count: int
    vapor_volume_eos_count: int
    pressure_drop_count: int
    pressure_anchor_count: int
    phase_transfer_count: int
    phase_transfer_registry_consistent: bool
    energy_balance_count: int
    francis_count: int
    phase_transfer_cancellation_passed: bool
    liquid_transport_cancellation_passed: bool
    vapor_transport_cancellation_passed: bool
    total_component_conservation_passed: bool
    total_energy_storage_includes_both_phases: bool
    every_energy_row_uses_vapor_inventory: bool
    pressure_ownership_consistent: bool
    provider_ownership_complete: bool
    fallback_permitted: bool
    preparation_only: bool
    pass_gate: bool


REQUIRED_OWNERSHIP_QUANTITIES = (
    "liquid_component_inventory",
    "vapor_component_inventory",
    "liquid_composition",
    "vapor_composition",
    "vapor_volume",
    "pressure",
    "phase_transfer",
    "liquid_internal_energy",
    "vapor_internal_energy",
    "terminal_vapor_boundaries",
)

REQUIRED_PROPERTY_QUANTITIES = (
    "phase_fugacity",
    "liquid_density",
    "vapor_compressibility_factor",
    "liquid_phase_enthalpy",
    "vapor_phase_enthalpy",
)


def _validated_components(component_names: Sequence[str]) -> tuple[str, ...]:
    components = tuple(str(value).strip() for value in component_names)
    if len(components) < 2:
        raise ValueError("vapor-holdup architecture requires at least two components")
    if any(not component for component in components):
        raise ValueError("component names must be nonempty")
    if len(set(components)) != len(components):
        raise ValueError("component names must be unique")
    return components


def _inventory_coordinates(
    phase: str,
    components: tuple[str, ...],
    volume: str,
) -> tuple[str, ...]:
    return tuple(f"N{phase}[{volume},{component}]" for component in components)


def _rate_coordinates(
    phase: str,
    components: tuple[str, ...],
    volume: str,
) -> tuple[str, ...]:
    return tuple(
        f"dN{phase}[{volume},{component}]/dt" for component in components
    )


def _phase_transfer_coordinates(
    components: tuple[str, ...], volume: str
) -> tuple[str, ...]:
    return tuple(f"M_VL[{volume},{component}]" for component in components)


def build_vapor_holdup_topology(
    *,
    column: ColumnTopology | None = None,
    vapor_volume_ft3: Mapping[str, float] | None = None,
) -> VaporHoldupTopology:
    """Declare resident vapor storage and pressure ownership for every volume."""
    column = DEFAULT_TOPOLOGY if column is None else column
    volume_ids = tuple(column.volume_ids)
    if len(volume_ids) < 5 or len(set(volume_ids)) != len(volume_ids):
        raise ValueError("column topology requires at least five unique volumes")
    if vapor_volume_ft3 is None:
        raise ValueError(
            "vapor_volume_ft3 must explicitly declare every physical volume"
        )
    volumes = {
        str(volume): float(value) for volume, value in vapor_volume_ft3.items()
    }
    missing = tuple(volume for volume in volume_ids if volume not in volumes)
    extra = tuple(sorted(set(volumes) - set(volume_ids)))
    nonpositive = tuple(
        volume
        for volume in volume_ids
        if volume in volumes
        and (not np.isfinite(volumes[volume]) or volumes[volume] <= 0.0)
    )
    if missing or extra or nonpositive:
        raise ValueError(
            "vapor volume declaration must contain one positive finite value "
            f"per physical volume; missing={missing}, extra={extra}, "
            f"nonpositive={nonpositive}"
        )
    return VaporHoldupTopology(
        column=column,
        vapor_control_volume_ids=volume_ids,
        vapor_volume_ft3_by_volume=tuple(
            (volume, volumes[volume]) for volume in volume_ids
        ),
        pressure_anchor_volume=column.top_volume,
        pressure_owner="vapor_inventory_eos_plus_interstage_pressure_drop",
        vapor_volume_model="shell_volume_minus_liquid_displacement",
        terminal_vapor_boundaries=(
            (
                "total_condenser_condensation",
                column.top_volume,
                "closed_total_condenser_no_external_vapor_product",
            ),
            (
                "reboiler_boilup",
                column.bottom_volume,
                "closed_reboiler_no_external_vapor_feed",
            ),
        ),
    )


def _physical_ownership() -> tuple[PhysicalOwnership, ...]:
    return (
        PhysicalOwnership("liquid_component_inventory", "NL", "liquid_component_balance"),
        PhysicalOwnership("vapor_component_inventory", "NV", "vapor_component_balance"),
        PhysicalOwnership("liquid_composition", "normalize(NL)", "derived_state"),
        PhysicalOwnership("vapor_composition", "normalize(NV)", "derived_state"),
        PhysicalOwnership("vapor_volume", "vapor_volume_eos", "vapor_volume_eos"),
        PhysicalOwnership("pressure", "P", "eos_pressure_drop_and_top_anchor"),
        PhysicalOwnership("phase_transfer", "M_VL", "equal_and_opposite_phase_balances"),
        PhysicalOwnership("liquid_internal_energy", "UL", "total_energy_balance"),
        PhysicalOwnership("vapor_internal_energy", "UV", "total_energy_balance"),
        PhysicalOwnership(
            "terminal_vapor_boundaries",
            "top_condensation_and_bottom_boilup",
            "terminal_phase_transfer",
        ),
    )


def _property_authorities() -> tuple[PropertyAuthority, ...]:
    return (
        PropertyAuthority(
            "phase_fugacity",
            "direct_imposed_phase_fugacity",
            "same endpoint T/P with x=normalize(NL), y=normalize(NV)",
        ),
        PropertyAuthority(
            "liquid_density",
            "declared_liquid_density",
            "endpoint T/P/x",
        ),
        PropertyAuthority(
            "vapor_compressibility_factor",
            "declared_vapor_compressibility_factor",
            "endpoint T/P/y",
        ),
        PropertyAuthority(
            "liquid_phase_enthalpy",
            "declared_phase_enthalpy",
            "endpoint liquid T/P/x",
        ),
        PropertyAuthority(
            "vapor_phase_enthalpy",
            "declared_phase_enthalpy",
            "endpoint vapor T/P/y",
        ),
    )


def build_vapor_holdup_dae_contract(
    component_names: Sequence[str],
    *,
    topology: VaporHoldupTopology | None = None,
    vapor_volume_ft3: Mapping[str, float] | None = None,
    product_flow_parameters: tuple[str, str] = ("D_fixed", "B_fixed"),
) -> VaporHoldupDAEContract:
    """Build the property-free implicit equilibrium-stage ownership ledger."""
    components = _validated_components(component_names)
    if topology is not None and vapor_volume_ft3 is not None:
        raise ValueError("provide topology or vapor_volume_ft3, not both")
    vh_topology = (
        build_vapor_holdup_topology(vapor_volume_ft3=vapor_volume_ft3)
        if topology is None
        else topology
    )
    column = vh_topology.column
    volumes = column.volume_ids
    if vh_topology.vapor_control_volume_ids != volumes:
        raise ValueError("every physical volume must own resident vapor inventory")
    if len(product_flow_parameters) != 2 or not all(product_flow_parameters):
        raise ValueError("top and bottom product-flow parameters are required")

    liquid_states = tuple(
        name
        for volume in volumes
        for name in _inventory_coordinates("L", components, volume)
    )
    vapor_states = tuple(
        name
        for volume in volumes
        for name in _inventory_coordinates("V", components, volume)
    )
    liquid_rates = tuple(
        SolveVariable(name, "liquid_component_inventory_rate", volume)
        for volume in volumes
        for name in _rate_coordinates("L", components, volume)
    )
    vapor_rates = tuple(
        SolveVariable(name, "vapor_component_inventory_rate", volume)
        for volume in volumes
        for name in _rate_coordinates("V", components, volume)
    )
    phase_transfer = tuple(
        SolveVariable(name, "interphase_component_transfer", volume)
        for volume in volumes
        for name in _phase_transfer_coordinates(components, volume)
    )
    temperatures = tuple(
        SolveVariable(f"T[{volume}]", "temperature", volume) for volume in volumes
    )
    pressures = tuple(
        SolveVariable(f"P[{volume}]", "algebraic_pressure", volume)
        for volume in volumes
    )
    liquid_flows = tuple(
        SolveVariable(f"L[{volume}]", "francis_liquid_flow", volume)
        for volume in column.hydraulic_volume_ids
    )
    vapor_flows = tuple(
        SolveVariable(symbol, "pressure_driven_vapor_flow", source)
        for source, _destination, symbol in column.vapor_links
    )
    condenser_duty = (
        SolveVariable("Q_C", "solved_condenser_duty", column.top_volume),
    )
    algebraic = (
        *phase_transfer,
        *temperatures,
        *pressures,
        *liquid_flows,
        *vapor_flows,
        *condenser_duty,
    )

    liquid_rate_by_volume = {
        volume: _rate_coordinates("L", components, volume) for volume in volumes
    }
    vapor_rate_by_volume = {
        volume: _rate_coordinates("V", components, volume) for volume in volumes
    }
    liquid_state_by_volume = {
        volume: _inventory_coordinates("L", components, volume) for volume in volumes
    }
    vapor_state_by_volume = {
        volume: _inventory_coordinates("V", components, volume) for volume in volumes
    }
    transfer_by_volume = {
        volume: _phase_transfer_coordinates(components, volume) for volume in volumes
    }
    solved_liquid_flows = {variable.name for variable in liquid_flows}
    rows: list[DAERow] = []
    transfer_contributions: list[PhaseTransferContribution] = []

    for volume in volumes:
        for component_index, component in enumerate(components):
            liquid_dependencies = [
                liquid_rate_by_volume[volume][component_index],
                transfer_by_volume[volume][component_index],
            ]
            liquid_states_used = list(liquid_state_by_volume[volume])
            for source, destination, symbol in column.liquid_links:
                if volume not in (source, destination):
                    continue
                if symbol in solved_liquid_flows:
                    liquid_dependencies.append(symbol)
                liquid_states_used.extend(liquid_state_by_volume[source])
            rows.append(
                DAERow(
                    f"liquid_component_balance[{volume},{component}]",
                    "liquid_component_balance",
                    volume,
                    tuple(dict.fromkeys(liquid_dependencies)),
                    tuple(dict.fromkeys(liquid_states_used)),
                )
            )
            transfer_contributions.append(
                PhaseTransferContribution(
                    transfer_by_volume[volume][component_index], "liquid", 1
                )
            )

            vapor_dependencies = [
                vapor_rate_by_volume[volume][component_index],
                transfer_by_volume[volume][component_index],
            ]
            vapor_states_used = list(vapor_state_by_volume[volume])
            for source, destination, symbol in column.vapor_links:
                if volume not in (source, destination):
                    continue
                vapor_dependencies.append(symbol)
                vapor_states_used.extend(vapor_state_by_volume[source])
            rows.append(
                DAERow(
                    f"vapor_component_balance[{volume},{component}]",
                    "vapor_component_balance",
                    volume,
                    tuple(dict.fromkeys(vapor_dependencies)),
                    tuple(dict.fromkeys(vapor_states_used)),
                )
            )
            transfer_contributions.append(
                PhaseTransferContribution(
                    transfer_by_volume[volume][component_index], "vapor", -1
                )
            )

        endpoint_rates = (
            *liquid_rate_by_volume[volume],
            *vapor_rate_by_volume[volume],
        )
        phase_states = (
            *liquid_state_by_volume[volume],
            *vapor_state_by_volume[volume],
        )
        for component in components:
            rows.append(
                DAERow(
                    f"phase_fugacity[{volume},{component}]",
                    "full_phase_equilibrium",
                    volume,
                    (*endpoint_rates, f"T[{volume}]", f"P[{volume}]"),
                    phase_states,
                )
            )
        rows.append(
            DAERow(
                f"vapor_volume_eos[{volume}]",
                "vapor_volume_eos",
                volume,
                (*endpoint_rates, f"T[{volume}]", f"P[{volume}]"),
                phase_states,
            )
        )

        energy_dependencies = [
            *endpoint_rates,
            f"T[{volume}]",
            f"P[{volume}]",
        ]
        energy_states = list(phase_states)
        for source, destination, symbol in (
            *column.liquid_links,
            *column.vapor_links,
        ):
            if volume not in (source, destination):
                continue
            if symbol == "R":
                energy_states.extend(liquid_state_by_volume[source])
            else:
                energy_dependencies.append(symbol)
            energy_dependencies.extend((f"T[{source}]", f"P[{source}]"))
            energy_states.extend(liquid_state_by_volume[source])
            energy_states.extend(vapor_state_by_volume[source])
        if volume == column.top_volume:
            energy_dependencies.append("Q_C")
        rows.append(
            DAERow(
                f"total_energy_balance[{volume}]",
                "total_energy_balance",
                volume,
                tuple(dict.fromkeys(energy_dependencies)),
                tuple(dict.fromkeys(energy_states)),
            )
        )

    for volume in column.hydraulic_volume_ids:
        rows.append(
            DAERow(
                f"francis_hydraulics[{volume}]",
                "francis_hydraulics",
                volume,
                (
                    f"L[{volume}]",
                    *liquid_rate_by_volume[volume],
                    f"T[{volume}]",
                    f"P[{volume}]",
                ),
                liquid_state_by_volume[volume],
            )
        )

    for source, destination, symbol in column.vapor_links:
        rows.append(
            DAERow(
                f"vapor_pressure_drop[{source}->{destination}]",
                "vapor_pressure_drop",
                source,
                (
                    symbol,
                    *vapor_rate_by_volume[source],
                    f"T[{source}]",
                    f"P[{source}]",
                    f"P[{destination}]",
                ),
                vapor_state_by_volume[source],
            )
        )
    rows.append(
        DAERow(
            f"pressure_anchor[{vh_topology.pressure_anchor_volume}]",
            "pressure_anchor",
            vh_topology.pressure_anchor_volume,
            (f"P[{vh_topology.pressure_anchor_volume}]",),
            (),
        )
    )

    fixed_parameters = (
        *product_flow_parameters,
        "R_fixed",
        "Q_R_fixed",
        "feed_liquid_component_rates",
        "feed_vapor_component_rates",
        "feed_liquid_enthalpy_rate",
        "feed_vapor_enthalpy_rate",
        TOP_PRESSURE_PARAMETER,
        "liquid_hydraulic_geometry",
        "vapor_pressure_drop_geometry",
        *(
            f"vapor_volume_ft3[{volume}]"
            for volume, _value in vh_topology.vapor_volume_ft3_by_volume
        ),
        *(
            f"terminal_vapor_boundary[{name}]"
            for name, _volume, _mode in vh_topology.terminal_vapor_boundaries
        ),
    )
    return VaporHoldupDAEContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        component_names=components,
        topology=vh_topology,
        state_coordinates=(*liquid_states, *vapor_states),
        derivative_variables=(*liquid_rates, *vapor_rates),
        algebraic_variables=algebraic,
        rows=tuple(rows),
        fixed_parameters=fixed_parameters,
        physical_ownership=_physical_ownership(),
        property_authorities=_property_authorities(),
        phase_transfer_contributions=tuple(transfer_contributions),
        total_internal_energy_storage=(
            "U_total[j]=U_L[j]+U_V[j]; "
            "U_L=NL*(hL-P*vL), U_V=NV*(hV-P*vV)"
        ),
        vapor_composition_definition="y[j,k]=NV[j,k]/sum_k(NV[j,k])",
        implicit_endpoint_coupling=(
            "algebraic equilibrium, EOS, hydraulics, pressure drop, and energy "
            "rows depend on positive endpoint inventories reconstructed from "
            "the registered liquid and vapor inventory rates"
        ),
    )


def _incidence(
    contract: VaporHoldupDAEContract,
) -> tuple[csr_matrix, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    solve_names = tuple(variable.name for variable in variables)
    solve_index = {name: index for index, name in enumerate(solve_names)}
    state_names = tuple(contract.state_coordinates)
    state_set = set(state_names)
    matrix = np.zeros((len(contract.rows), len(solve_names)), dtype=np.int8)
    unregistered_solve: set[str] = set()
    unregistered_state: set[str] = set()
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in solve_index:
                matrix[row_index, solve_index[dependency]] = 1
            else:
                unregistered_solve.add(dependency)
        for dependency in row.state_dependencies:
            if dependency not in state_set:
                unregistered_state.add(dependency)
    return (
        csr_matrix(matrix),
        solve_names,
        tuple(sorted(unregistered_solve)),
        tuple(sorted(unregistered_state)),
    )


def audit_vapor_holdup_dae_contract(
    contract: VaporHoldupDAEContract,
) -> VaporHoldupDAEAudit:
    matrix, solve_names, unregistered_solve, unregistered_state = _incidence(contract)
    volumes = contract.topology.column.volume_ids
    components = contract.component_names
    column_counts = np.asarray(matrix.sum(axis=0)).ravel()
    row_counts = np.asarray(matrix.sum(axis=1)).ravel()
    zero_columns = tuple(
        name
        for name, count in zip(solve_names, column_counts, strict=True)
        if not count
    )
    zero_rows = tuple(
        row.name
        for row, count in zip(contract.rows, row_counts, strict=True)
        if not count
    )
    rank = structural_rank_fast(matrix)
    expected = 3 * len(volumes) * len(components) + 4 * len(volumes) - 2

    declared_volumes = tuple(contract.topology.vapor_control_volume_ids)
    volume_parameters = dict(contract.topology.vapor_volume_ft3_by_volume)
    missing_volumes = tuple(volume for volume in volumes if volume not in declared_volumes)
    extra_volumes = tuple(sorted(set(declared_volumes) - set(volumes)))
    nonpositive_parameters = tuple(
        volume
        for volume in volumes
        if volume not in volume_parameters
        or not np.isfinite(volume_parameters[volume])
        or volume_parameters[volume] <= 0.0
    )

    ownership_names = tuple(item.quantity for item in contract.physical_ownership)
    missing_ownership = tuple(
        quantity for quantity in REQUIRED_OWNERSHIP_QUANTITIES if quantity not in ownership_names
    )
    duplicate_ownership = tuple(
        sorted({quantity for quantity in ownership_names if ownership_names.count(quantity) > 1})
    )
    independent_y = tuple(
        variable.name
        for variable in contract.algebraic_variables
        if variable.name.startswith("y[") or variable.block == "vapor_composition"
    )

    row_by_name = {row.name: row for row in contract.rows}
    unowned_vapor_states: list[str] = []
    for volume in volumes:
        for component in components:
            state = f"NV[{volume},{component}]"
            derivative = f"dNV[{volume},{component}]/dt"
            balance = row_by_name.get(f"vapor_component_balance[{volume},{component}]")
            if (
                state not in contract.state_coordinates
                or derivative not in solve_names
                or balance is None
                or derivative not in balance.solve_dependencies
                or state not in balance.state_dependencies
            ):
                unowned_vapor_states.append(state)

    transfer_totals: dict[str, int] = {}
    transfer_phases: dict[str, set[str]] = {}
    for contribution in contract.phase_transfer_contributions:
        transfer_totals[contribution.transfer] = (
            transfer_totals.get(contribution.transfer, 0) + contribution.coefficient
        )
        transfer_phases.setdefault(contribution.transfer, set()).add(contribution.phase)
    transfer_cancellation = bool(transfer_totals) and all(
        coefficient == 0 and transfer_phases[name] == {"liquid", "vapor"}
        for name, coefficient in transfer_totals.items()
    )
    phase_transfer_variables = tuple(
        variable.name
        for variable in contract.algebraic_variables
        if variable.block == "interphase_component_transfer"
    )
    transfer_registry_consistent = bool(
        len(phase_transfer_variables) == len(volumes) * len(components)
        and set(phase_transfer_variables) == set(transfer_totals)
    )

    liquid_transport = {
        symbol: (-1, 1) for _source, _destination, symbol in contract.topology.column.liquid_links
    }
    vapor_transport = {
        symbol: (-1, 1) for _source, _destination, symbol in contract.topology.column.vapor_links
    }
    liquid_cancellation = all(sum(coefficients) == 0 for coefficients in liquid_transport.values())
    vapor_cancellation = all(sum(coefficients) == 0 for coefficients in vapor_transport.values())

    energy_rows = tuple(row for row in contract.rows if row.block == "total_energy_balance")
    energy_storage_both = all(
        token in contract.total_internal_energy_storage
        for token in ("U_L", "U_V", "NL", "NV")
    )
    energy_uses_vapor = len(energy_rows) == len(volumes) and all(
        all(f"NV[{row.owner},{component}]" in row.state_dependencies for component in components)
        for row in energy_rows
    )

    pressure_rows = tuple(row for row in contract.rows if row.block == "vapor_pressure_drop")
    eos_rows = tuple(row for row in contract.rows if row.block == "vapor_volume_eos")
    anchor_rows = tuple(row for row in contract.rows if row.block == "pressure_anchor")
    pressure_consistent = bool(
        len(eos_rows) == len(volumes)
        and len(pressure_rows) == len(contract.topology.column.vapor_links)
        and len(anchor_rows) == 1
        and anchor_rows[0].owner == contract.topology.pressure_anchor_volume
        and contract.topology.pressure_owner
        == "vapor_inventory_eos_plus_interstage_pressure_drop"
        and contract.topology.vapor_volume_model
        == "shell_volume_minus_liquid_displacement"
    )

    authority_names = tuple(item.quantity for item in contract.property_authorities)
    provider_complete = all(
        authority_names.count(quantity) == 1 for quantity in REQUIRED_PROPERTY_QUANTITIES
    )
    fallback = any(item.fallback_permitted for item in contract.property_authorities)
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.mass_matrix_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )

    def count(block: str) -> int:
        return sum(row.block == block for row in contract.rows)

    solve_count = len(solve_names)
    row_count = len(contract.rows)
    total_conservation = bool(
        liquid_cancellation and vapor_cancellation and transfer_cancellation
    )
    pass_gate = bool(
        solve_count == row_count == expected
        and rank == expected
        and not zero_columns
        and not zero_rows
        and not unregistered_solve
        and not unregistered_state
        and not missing_volumes
        and not extra_volumes
        and not nonpositive_parameters
        and not missing_ownership
        and not duplicate_ownership
        and not independent_y
        and not unowned_vapor_states
        and count("liquid_component_balance") == len(volumes) * len(components)
        and count("vapor_component_balance") == len(volumes) * len(components)
        and count("full_phase_equilibrium") == len(volumes) * len(components)
        and transfer_registry_consistent
        and count("vapor_volume_eos") == len(volumes)
        and count("vapor_pressure_drop") == len(contract.topology.column.vapor_links)
        and count("pressure_anchor") == 1
        and count("total_energy_balance") == len(volumes)
        and count("francis_hydraulics") == len(contract.topology.column.hydraulic_volume_ids)
        and total_conservation
        and energy_storage_both
        and energy_uses_vapor
        and pressure_consistent
        and provider_complete
        and not fallback
        and preparation_only
    )
    return VaporHoldupDAEAudit(
        volume_count=len(volumes),
        component_count=len(components),
        state_coordinate_count=len(contract.state_coordinates),
        liquid_state_count=sum(name.startswith("NL[") for name in contract.state_coordinates),
        vapor_state_count=sum(name.startswith("NV[") for name in contract.state_coordinates),
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
        missing_vapor_volume_declarations=missing_volumes,
        extra_vapor_volume_declarations=extra_volumes,
        nonpositive_vapor_volume_parameters=nonpositive_parameters,
        missing_ownership_quantities=missing_ownership,
        duplicate_ownership_quantities=duplicate_ownership,
        independent_vapor_composition_variables=independent_y,
        unowned_vapor_states=tuple(unowned_vapor_states),
        vapor_balance_count=count("vapor_component_balance"),
        liquid_balance_count=count("liquid_component_balance"),
        equilibrium_count=count("full_phase_equilibrium"),
        vapor_volume_eos_count=count("vapor_volume_eos"),
        pressure_drop_count=count("vapor_pressure_drop"),
        pressure_anchor_count=count("pressure_anchor"),
        phase_transfer_count=len(phase_transfer_variables),
        phase_transfer_registry_consistent=transfer_registry_consistent,
        energy_balance_count=count("total_energy_balance"),
        francis_count=count("francis_hydraulics"),
        phase_transfer_cancellation_passed=transfer_cancellation,
        liquid_transport_cancellation_passed=liquid_cancellation,
        vapor_transport_cancellation_passed=vapor_cancellation,
        total_component_conservation_passed=total_conservation,
        total_energy_storage_includes_both_phases=energy_storage_both,
        every_energy_row_uses_vapor_inventory=energy_uses_vapor,
        pressure_ownership_consistent=pressure_consistent,
        provider_ownership_complete=provider_complete,
        fallback_permitted=fallback,
        preparation_only=preparation_only,
        pass_gate=pass_gate,
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "PhysicalOwnership",
    "PropertyAuthority",
    "TOP_PRESSURE_PARAMETER",
    "VaporHoldupDAEAudit",
    "VaporHoldupDAEContract",
    "VaporHoldupTopology",
    "audit_vapor_holdup_dae_contract",
    "build_vapor_holdup_dae_contract",
    "build_vapor_holdup_topology",
]
