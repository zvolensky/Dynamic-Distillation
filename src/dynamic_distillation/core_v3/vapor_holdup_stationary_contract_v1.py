"""Structural contract for a stationary vapor-holdup initializer.

The stationary initializer solves resident liquid and vapor inventories directly.
Top and bottom product rates are algebraic variables so the terminal liquid
inventories can be fixed by explicit level targets. This module is property-free
and performs no residual evaluation or nonlinear solve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.sparse import csr_matrix

from .dynamic_dae_contract_v1 import DAERow, SolveVariable
from .structural_rank_v1 import structural_rank_fast
from .vapor_holdup_dae_contract_v1 import VaporHoldupTopology


CONTRACT_NAME = "Core V3 - Stationary Conserved Vapor-Holdup Initializer"
CONTRACT_VERSION = "core-v3-vapor-holdup-stationary-initializer-v1"


@dataclass(frozen=True)
class VaporHoldupStationaryContract:
    name: str
    version: str
    component_names: tuple[str, ...]
    topology: VaporHoldupTopology
    variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]
    property_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class VaporHoldupStationaryAudit:
    volume_count: int
    component_count: int
    variable_count: int
    row_count: int
    structural_rank: int
    structural_nullity: int
    zero_columns: tuple[str, ...]
    zero_rows: tuple[str, ...]
    unregistered_dependencies: tuple[str, ...]
    liquid_balance_count: int
    vapor_balance_count: int
    equilibrium_count: int
    eos_count: int
    energy_count: int
    francis_count: int
    pressure_drop_count: int
    pressure_anchor_count: int
    terminal_inventory_target_count: int
    product_flow_variable_count: int
    fixed_product_flow_parameters: tuple[str, ...]
    preparation_only: bool
    pass_gate: bool


def _components(values: Sequence[str]) -> tuple[str, ...]:
    result = tuple(str(value).strip() for value in values)
    if len(result) < 2 or any(not value for value in result):
        raise ValueError("stationary vapor-holdup contract requires components")
    if len(set(result)) != len(result):
        raise ValueError("component names must be unique")
    return result


def _inventory(phase: str, volume: str, components: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"N{phase}[{volume},{component}]" for component in components)


def _transfer(volume: str, components: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"M_VL[{volume},{component}]" for component in components)


def build_vapor_holdup_stationary_contract(
    component_names: Sequence[str],
    *,
    topology: VaporHoldupTopology,
) -> VaporHoldupStationaryContract:
    """Build the square steady initializer with terminal inventory targets."""
    components = _components(component_names)
    column = topology.column
    volumes = tuple(column.volume_ids)
    if topology.vapor_control_volume_ids != volumes:
        raise ValueError("every stationary volume must own resident vapor")

    liquid_inventory = tuple(
        SolveVariable(name, "liquid_component_inventory", volume)
        for volume in volumes
        for name in _inventory("L", volume, components)
    )
    vapor_inventory = tuple(
        SolveVariable(name, "vapor_component_inventory", volume)
        for volume in volumes
        for name in _inventory("V", volume, components)
    )
    phase_transfer = tuple(
        SolveVariable(name, "interphase_component_transfer", volume)
        for volume in volumes
        for name in _transfer(volume, components)
    )
    temperatures = tuple(
        SolveVariable(f"T[{volume}]", "temperature", volume) for volume in volumes
    )
    pressures = tuple(
        SolveVariable(f"P[{volume}]", "pressure", volume) for volume in volumes
    )
    liquid_flows = tuple(
        SolveVariable(f"L[{volume}]", "francis_liquid_flow", volume)
        for volume in column.hydraulic_volume_ids
    )
    vapor_flows = tuple(
        SolveVariable(symbol, "pressure_driven_vapor_flow", source)
        for source, _destination, symbol in column.vapor_links
    )
    duties_and_products = (
        SolveVariable("Q_C", "solved_condenser_duty", column.top_volume),
        SolveVariable("D", "terminal_level_product_flow", column.top_volume),
        SolveVariable("B", "terminal_level_product_flow", column.bottom_volume),
    )
    variables = (
        *liquid_inventory,
        *vapor_inventory,
        *phase_transfer,
        *temperatures,
        *pressures,
        *liquid_flows,
        *vapor_flows,
        *duties_and_products,
    )

    liquid_by_volume = {
        volume: _inventory("L", volume, components) for volume in volumes
    }
    vapor_by_volume = {
        volume: _inventory("V", volume, components) for volume in volumes
    }
    transfer_by_volume = {
        volume: _transfer(volume, components) for volume in volumes
    }
    solved_liquid_flows = {variable.name for variable in liquid_flows}
    rows: list[DAERow] = []

    for volume in volumes:
        for component_index, component in enumerate(components):
            liquid_dependencies = [transfer_by_volume[volume][component_index]]
            liquid_dependencies.extend(liquid_by_volume[volume])
            for source, destination, symbol in column.liquid_links:
                if volume not in (source, destination):
                    continue
                liquid_dependencies.extend(liquid_by_volume[source])
                if symbol in solved_liquid_flows:
                    liquid_dependencies.append(symbol)
            if volume == column.top_volume:
                liquid_dependencies.append("D")
            if volume == column.bottom_volume:
                liquid_dependencies.append("B")
            rows.append(
                DAERow(
                    f"liquid_component_balance[{volume},{component}]",
                    "liquid_component_balance",
                    volume,
                    tuple(dict.fromkeys(liquid_dependencies)),
                    (),
                )
            )

            vapor_dependencies = [transfer_by_volume[volume][component_index]]
            vapor_dependencies.extend(vapor_by_volume[volume])
            for source, destination, symbol in column.vapor_links:
                if volume not in (source, destination):
                    continue
                vapor_dependencies.extend(vapor_by_volume[source])
                vapor_dependencies.append(symbol)
            rows.append(
                DAERow(
                    f"vapor_component_balance[{volume},{component}]",
                    "vapor_component_balance",
                    volume,
                    tuple(dict.fromkeys(vapor_dependencies)),
                    (),
                )
            )

        local_phases = (*liquid_by_volume[volume], *vapor_by_volume[volume])
        for component in components:
            rows.append(
                DAERow(
                    f"phase_fugacity[{volume},{component}]",
                    "full_phase_equilibrium",
                    volume,
                    (*local_phases, f"T[{volume}]", f"P[{volume}]"),
                    (),
                )
            )
        rows.append(
            DAERow(
                f"vapor_volume_eos[{volume}]",
                "vapor_volume_eos",
                volume,
                (*local_phases, f"T[{volume}]", f"P[{volume}]"),
                (),
            )
        )

        energy_dependencies = [*local_phases, f"T[{volume}]", f"P[{volume}]"]
        for source, destination, symbol in (*column.liquid_links, *column.vapor_links):
            if volume not in (source, destination):
                continue
            energy_dependencies.extend(liquid_by_volume[source])
            energy_dependencies.extend(vapor_by_volume[source])
            energy_dependencies.extend((f"T[{source}]", f"P[{source}]"))
            if symbol != "R":
                energy_dependencies.append(symbol)
        if volume == column.top_volume:
            energy_dependencies.extend(("Q_C", "D"))
        if volume == column.bottom_volume:
            energy_dependencies.append("B")
        rows.append(
            DAERow(
                f"total_energy_balance[{volume}]",
                "total_energy_balance",
                volume,
                tuple(dict.fromkeys(energy_dependencies)),
                (),
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
                    *liquid_by_volume[volume],
                    f"T[{volume}]",
                    f"P[{volume}]",
                ),
                (),
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
                    *liquid_by_volume[source],
                    *vapor_by_volume[source],
                    f"T[{source}]",
                    f"P[{source}]",
                    f"P[{destination}]",
                ),
                (),
            )
        )
    rows.append(
        DAERow(
            f"pressure_anchor[{topology.pressure_anchor_volume}]",
            "pressure_anchor",
            topology.pressure_anchor_volume,
            (f"P[{topology.pressure_anchor_volume}]",),
            (),
        )
    )
    for terminal, target_name in (
        (column.top_volume, "top_liquid_inventory_target"),
        (column.bottom_volume, "bottom_liquid_inventory_target"),
    ):
        rows.append(
            DAERow(
                f"{target_name}[{terminal}]",
                "terminal_liquid_inventory_target",
                terminal,
                liquid_by_volume[terminal],
                (),
            )
        )

    fixed_parameters = (
        "R_fixed",
        "Q_R_fixed",
        "feed_component_rates",
        "feed_enthalpy_rate",
        "P_anchor",
        "top_liquid_inventory_target",
        "bottom_liquid_inventory_target",
        "liquid_hydraulic_geometry",
        "vapor_pressure_drop_geometry",
        *(f"vapor_volume_ft3[{volume}]" for volume in volumes),
    )
    return VaporHoldupStationaryContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        component_names=components,
        topology=topology,
        variables=variables,
        rows=tuple(rows),
        fixed_parameters=fixed_parameters,
    )


def stationary_sparsity_pattern(
    contract: VaporHoldupStationaryContract,
) -> tuple[csr_matrix, tuple[str, ...], tuple[str, ...]]:
    names = tuple(variable.name for variable in contract.variables)
    index = {name: position for position, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    unknown: set[str] = set()
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                pattern[row_index, index[dependency]] = 1
            else:
                unknown.add(dependency)
    return csr_matrix(pattern), names, tuple(sorted(unknown))


def audit_vapor_holdup_stationary_contract(
    contract: VaporHoldupStationaryContract,
) -> VaporHoldupStationaryAudit:
    pattern, names, unknown = stationary_sparsity_pattern(contract)
    column_counts = np.asarray(pattern.sum(axis=0)).ravel()
    row_counts = np.asarray(pattern.sum(axis=1)).ravel()
    zero_columns = tuple(
        name for name, count in zip(names, column_counts, strict=True) if count == 0
    )
    zero_rows = tuple(
        row.name
        for row, count in zip(contract.rows, row_counts, strict=True)
        if count == 0
    )
    rank = structural_rank_fast(pattern)

    def count(block: str) -> int:
        return sum(row.block == block for row in contract.rows)

    volume_count = len(contract.topology.column.volume_ids)
    component_count = len(contract.component_names)
    expected = 3 * volume_count * component_count + 4 * volume_count
    fixed_products = tuple(
        name
        for name in contract.fixed_parameters
        if name in {"D", "B", "D_fixed", "B_fixed"}
    )
    product_count = sum(
        variable.block == "terminal_level_product_flow" for variable in contract.variables
    )
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    passed = bool(
        len(contract.variables) == len(contract.rows) == expected
        and rank == expected
        and not zero_columns
        and not zero_rows
        and not unknown
        and count("liquid_component_balance") == volume_count * component_count
        and count("vapor_component_balance") == volume_count * component_count
        and count("full_phase_equilibrium") == volume_count * component_count
        and count("vapor_volume_eos") == volume_count
        and count("total_energy_balance") == volume_count
        and count("francis_hydraulics")
        == len(contract.topology.column.hydraulic_volume_ids)
        and count("vapor_pressure_drop") == len(contract.topology.column.vapor_links)
        and count("pressure_anchor") == 1
        and count("terminal_liquid_inventory_target") == 2
        and product_count == 2
        and not fixed_products
        and preparation_only
    )
    return VaporHoldupStationaryAudit(
        volume_count=volume_count,
        component_count=component_count,
        variable_count=len(contract.variables),
        row_count=len(contract.rows),
        structural_rank=rank,
        structural_nullity=len(contract.variables) - rank,
        zero_columns=zero_columns,
        zero_rows=zero_rows,
        unregistered_dependencies=unknown,
        liquid_balance_count=count("liquid_component_balance"),
        vapor_balance_count=count("vapor_component_balance"),
        equilibrium_count=count("full_phase_equilibrium"),
        eos_count=count("vapor_volume_eos"),
        energy_count=count("total_energy_balance"),
        francis_count=count("francis_hydraulics"),
        pressure_drop_count=count("vapor_pressure_drop"),
        pressure_anchor_count=count("pressure_anchor"),
        terminal_inventory_target_count=count("terminal_liquid_inventory_target"),
        product_flow_variable_count=product_count,
        fixed_product_flow_parameters=fixed_products,
        preparation_only=preparation_only,
        pass_gate=passed,
    )


__all__ = [
    "VaporHoldupStationaryAudit",
    "VaporHoldupStationaryContract",
    "audit_vapor_holdup_stationary_contract",
    "build_vapor_holdup_stationary_contract",
    "stationary_sparsity_pattern",
]
