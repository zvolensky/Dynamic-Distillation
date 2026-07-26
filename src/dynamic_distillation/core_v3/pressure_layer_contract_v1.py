"""Structural contract for the first Core V3 algebraic pressure layer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    DAERow,
    DynamicDAEContract,
    SolveVariable,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    VAPOR_LINKS,
    VOLUME_IDS,
)


CONTRACT_NAME = "Core V3 - Algebraic Pressure and Vapor-Flow Layer"
CONTRACT_VERSION = "core-v3-pressure-layer-contract-v1"
TOP_PRESSURE_PARAMETER = "P[reflux_drum]_fixed"


@dataclass(frozen=True)
class PressureLayerContract:
    name: str
    version: str
    base_contract: DynamicDAEContract
    pressure_variables: tuple[SolveVariable, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]
    pressure_drop_property_quantities: tuple[str, ...]
    pressure_reconstruction: str
    property_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class PressureLayerAudit:
    solve_variable_count: int
    row_count: int
    expected_count: int
    structural_rank: int
    structural_nullity: int
    pressure_variable_count: int
    pressure_drop_row_count: int
    vapor_flow_variable_count: int
    zero_solve_columns: tuple[str, ...]
    zero_rows: tuple[str, ...]
    unregistered_dependencies: tuple[str, ...]
    prescribed_interior_pressure_parameters: tuple[str, ...]
    top_pressure_anchor_present: bool
    ordered_pressure_gate_declared: bool
    pressure_drop_property_quantities: tuple[str, ...]
    component_conservation_inherited: bool
    energy_conservation_inherited: bool
    controller_rows: tuple[str, ...]
    profile_dependencies: tuple[str, ...]
    cap_or_relaxation_dependencies: tuple[str, ...]
    explicit_vapor_inventory_present: bool
    preparation_only: bool
    pass_gate: bool


def _pressure_name(volume: str) -> str:
    return f"P[{volume}]"


def _coordinate_volume(name: str, prefix: str) -> str | None:
    marker = f"{prefix}["
    if not name.startswith(marker) or not name.endswith("]"):
        return None
    return name[len(marker) : -1].split(",", maxsplit=1)[0]


def _augment_base_row(row: DAERow, unknown_pressures: set[str]) -> DAERow:
    dependencies = list(row.solve_dependencies)
    pressure_volumes: list[str] = []
    if row.block == "energy_balance":
        for dependency in row.solve_dependencies:
            volume = _coordinate_volume(dependency, "T")
            if volume is not None:
                pressure_volumes.append(volume)
    elif row.block in {"full_phase_equilibrium", "francis_hydraulics"}:
        pressure_volumes.append(row.owner)
    for volume in pressure_volumes:
        pressure = _pressure_name(volume)
        if pressure in unknown_pressures:
            dependencies.append(pressure)
    return replace(row, solve_dependencies=tuple(dict.fromkeys(dependencies)))


def build_pressure_layer_contract(
    component_names: Sequence[str],
) -> PressureLayerContract:
    base = build_dynamic_dae_contract(component_names)
    pressure_variables = tuple(
        SolveVariable(_pressure_name(volume), "algebraic_pressure", volume)
        for volume in VOLUME_IDS[1:]
    )
    unknown_pressures = {variable.name for variable in pressure_variables}
    rows = [
        _augment_base_row(row, unknown_pressures)
        for row in base.rows
    ]
    independent_components = base.component_names[:-1]
    for source, destination, vapor_symbol in VAPOR_LINKS:
        dependencies = [vapor_symbol, _pressure_name(source)]
        destination_pressure = _pressure_name(destination)
        if destination_pressure in unknown_pressures:
            dependencies.append(destination_pressure)
        dependencies.append(f"T[{source}]")
        dependencies.extend(
            f"y[{source},{component}]" for component in independent_components
        )
        rows.append(
            DAERow(
                name=f"vapor_pressure_drop[{source}->{destination}]",
                block="vapor_pressure_drop",
                owner=source,
                solve_dependencies=tuple(dependencies),
                state_dependencies=tuple(
                    f"N[{source},{component}]" for component in base.component_names
                ),
            )
        )
    fixed_parameters = tuple(
        parameter
        for parameter in base.fixed_parameters
        if parameter != "ordered_pressure_profile"
    ) + (
        TOP_PRESSURE_PARAMETER,
        "dry_tray_pressure_drop_coefficient",
        "active_tray_area",
        "component_molecular_weights",
        "ordered_positive_pressure_gate",
    )
    return PressureLayerContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        base_contract=base,
        pressure_variables=pressure_variables,
        derivative_variables=base.derivative_variables,
        algebraic_variables=(*base.algebraic_variables, *pressure_variables),
        rows=tuple(rows),
        fixed_parameters=fixed_parameters,
        pressure_drop_property_quantities=(
            "declared_liquid_density",
            "declared_vapor_compressibility_factor",
        ),
        pressure_reconstruction=(
            "P[reflux_drum] is fixed; the four lower-volume pressures are "
            "simultaneous algebraic unknowns constrained by four uncapped "
            "dry-tray-plus-liquid-head pressure-drop equations"
        ),
    )


def audit_pressure_layer_contract(
    contract: PressureLayerContract,
) -> PressureLayerAudit:
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    matrix = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    unregistered = set()
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                matrix[row_index, index[dependency]] = 1
            else:
                unregistered.add(dependency)
    sparse = csr_matrix(matrix)
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
    rank = int(structural_rank(sparse))
    pressure_rows = tuple(
        row for row in contract.rows if row.block == "vapor_pressure_drop"
    )
    vapor_variables = tuple(
        variable
        for variable in contract.algebraic_variables
        if variable.block == "energy_owned_vapor_flow"
    )
    prescribed_interior = tuple(
        parameter
        for parameter in contract.fixed_parameters
        if parameter.startswith("P[") and parameter != TOP_PRESSURE_PARAMETER
    )
    controller_rows = tuple(
        row.name for row in contract.rows if "controller" in row.block
    )
    all_dependencies = tuple(
        dependency
        for row in contract.rows
        for dependency in (*row.solve_dependencies, *row.state_dependencies)
    )
    profiles = tuple(
        sorted({value for value in all_dependencies if "profile" in value.lower()})
    )
    caps = tuple(
        sorted(
            {
                value
                for value in all_dependencies
                if any(token in value.lower() for token in ("cap", "relax", "previous"))
            }
        )
    )
    explicit_vapor_inventory = any(
        name.startswith("NV[") for name in contract.base_contract.state_coordinates
    )
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    expected = 10 * len(contract.base_contract.component_names) + 12
    base_rows = contract.base_contract.rows
    component_conservation = sum(
        row.block == "component_balance" for row in base_rows
    ) == len(VOLUME_IDS) * len(contract.base_contract.component_names)
    energy_conservation = (
        sum(row.block == "energy_balance" for row in base_rows) == len(VOLUME_IDS)
        and any(variable.name == "Q_C" for variable in contract.algebraic_variables)
    )
    pass_gate = bool(
        len(names) == len(contract.rows) == expected
        and rank == expected
        and not zero_columns
        and not zero_rows
        and not unregistered
        and len(contract.pressure_variables) == len(VOLUME_IDS) - 1
        and len(pressure_rows) == len(VAPOR_LINKS)
        and len(vapor_variables) == len(VAPOR_LINKS)
        and not prescribed_interior
        and TOP_PRESSURE_PARAMETER in contract.fixed_parameters
        and "ordered_positive_pressure_gate" in contract.fixed_parameters
        and contract.pressure_drop_property_quantities
        == (
            "declared_liquid_density",
            "declared_vapor_compressibility_factor",
        )
        and component_conservation
        and energy_conservation
        and not controller_rows
        and not profiles
        and not caps
        and not explicit_vapor_inventory
        and preparation_only
    )
    return PressureLayerAudit(
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        expected_count=expected,
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        pressure_variable_count=len(contract.pressure_variables),
        pressure_drop_row_count=len(pressure_rows),
        vapor_flow_variable_count=len(vapor_variables),
        zero_solve_columns=zero_columns,
        zero_rows=zero_rows,
        unregistered_dependencies=tuple(sorted(unregistered)),
        prescribed_interior_pressure_parameters=prescribed_interior,
        top_pressure_anchor_present=TOP_PRESSURE_PARAMETER
        in contract.fixed_parameters,
        ordered_pressure_gate_declared="ordered_positive_pressure_gate"
        in contract.fixed_parameters,
        pressure_drop_property_quantities=contract.pressure_drop_property_quantities,
        component_conservation_inherited=component_conservation,
        energy_conservation_inherited=energy_conservation,
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
    "PressureLayerAudit",
    "PressureLayerContract",
    "TOP_PRESSURE_PARAMETER",
    "audit_pressure_layer_contract",
    "build_pressure_layer_contract",
]
