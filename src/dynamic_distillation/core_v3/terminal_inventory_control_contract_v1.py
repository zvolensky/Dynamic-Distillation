"""Structural terminal-inventory control contract for the Core V3 DAE.

This module changes equation ownership only. It performs no property
evaluation, nonlinear solve, controller execution, or integration.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.sparse import csr_matrix

from .structural_rank_v1 import structural_rank_fast

from .dynamic_dae_contract_v1 import (
    DAERow,
    DynamicDAEContract,
    SolveVariable,
    audit_dynamic_dae_contract,
)


CONTRACT_NAME = "Core V3 - Terminal Inventory Controlled Dynamic DAE Contract"
CONTRACT_VERSION = "core-v3-terminal-inventory-control-contract-v1"


@dataclass(frozen=True)
class TerminalVesselGeometry:
    top_diameter_ft: float
    top_tangent_length_ft: float
    top_head_shape: str
    bottom_diameter_ft: float
    bottom_height_ft: float


@dataclass(frozen=True)
class TerminalPIParameters:
    top_kc: float
    top_ti_sec: float
    bottom_kc: float
    bottom_ti_sec: float
    product_rate_ratio_bounds: tuple[float, float]


@dataclass(frozen=True)
class TerminalInventoryControlContract:
    name: str
    version: str
    base: DynamicDAEContract
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]
    product_output_variables: tuple[str, str]
    geometry: TerminalVesselGeometry
    controllers: TerminalPIParameters
    measurement_definition: str
    controller_definition: str
    property_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    controller_execution_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class TerminalInventoryControlAudit:
    component_count: int
    volume_count: int
    state_coordinate_count: int
    derivative_variable_count: int
    algebraic_variable_count: int
    solve_variable_count: int
    row_count: int
    expected_count: int
    structural_rank: int
    structural_nullity: int
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    duplicate_variable_names: tuple[str, ...]
    unregistered_solve_dependencies: tuple[str, ...]
    unregistered_state_dependencies: tuple[str, ...]
    controller_state_count: int
    controller_rate_count: int
    controller_output_count: int
    controller_row_count: int
    boundary_rows_own_live_product_outputs: bool
    fixed_product_parameters_removed: bool
    interior_rows_without_controller_dependencies: bool
    geometry_valid: bool
    controller_parameters_valid: bool
    base_contract_passed: bool
    preparation_only: bool
    pass_gate: bool


def _memory_state(volume: str) -> str:
    return f"I_level[{volume}]"


def _memory_rate(volume: str) -> str:
    return f"dI_level[{volume}]/dt"


def _product_output(volume: str, top_volume: str) -> str:
    return "log_D_level_output" if volume == top_volume else "log_B_level_output"


def _terminal_inventory_states(
    base: DynamicDAEContract, volume: str
) -> tuple[str, ...]:
    return tuple(f"N[{volume},{component}]" for component in base.component_names)


def _add_product_output_dependency(
    row: DAERow,
    *,
    top_volume: str,
    bottom_volume: str,
) -> DAERow:
    if row.block not in {"component_balance", "energy_balance"}:
        return row
    if row.owner == top_volume:
        output = _product_output(top_volume, top_volume)
    elif row.owner == bottom_volume:
        output = _product_output(bottom_volume, top_volume)
    else:
        return row
    return replace(
        row,
        solve_dependencies=tuple(dict.fromkeys((*row.solve_dependencies, output))),
    )


def build_terminal_inventory_control_contract(
    base: DynamicDAEContract,
    *,
    geometry: TerminalVesselGeometry,
    controllers: TerminalPIParameters,
) -> TerminalInventoryControlContract:
    """Add generic geometry-based terminal PI ownership to a dynamic DAE."""

    top = base.topology.top_volume
    bottom = base.topology.bottom_volume
    terminals = (top, bottom)
    controller_states = tuple(_memory_state(volume) for volume in terminals)
    controller_rates = tuple(
        SolveVariable(
            _memory_rate(volume),
            "terminal_level_controller_integrator_rate",
            volume,
        )
        for volume in terminals
    )
    product_outputs = tuple(
        SolveVariable(
            _product_output(volume, top),
            "terminal_level_controller_output",
            volume,
        )
        for volume in terminals
    )
    physical_rows = tuple(
        _add_product_output_dependency(
            row,
            top_volume=top,
            bottom_volume=bottom,
        )
        for row in base.rows
    )
    controller_rows: list[DAERow] = []
    for volume in terminals:
        state_dependencies = (
            *_terminal_inventory_states(base, volume),
            _memory_state(volume),
        )
        temperature = f"T[{volume}]"
        controller_rows.extend(
            (
                DAERow(
                    name=f"level_integrator[{volume}]",
                    block="terminal_level_controller_integrator",
                    owner=volume,
                    solve_dependencies=(_memory_rate(volume), temperature),
                    state_dependencies=state_dependencies,
                ),
                DAERow(
                    name=f"level_output[{volume}]",
                    block="terminal_level_controller_output",
                    owner=volume,
                    solve_dependencies=(
                        _product_output(volume, top),
                        temperature,
                    ),
                    state_dependencies=state_dependencies,
                ),
            )
        )
    fixed_parameters = tuple(
        value
        for value in base.fixed_parameters
        if value not in set(base.product_flow_parameters)
    )
    fixed_parameters = (
        *fixed_parameters,
        "terminal_level_geometry",
        "terminal_level_setpoints",
        "terminal_pi_parameters",
        "terminal_product_reference_rates",
    )
    return TerminalInventoryControlContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        base=base,
        state_coordinates=(*base.state_coordinates, *controller_states),
        derivative_variables=(*base.derivative_variables, *controller_rates),
        algebraic_variables=(*base.algebraic_variables, *product_outputs),
        rows=(*physical_rows, *controller_rows),
        fixed_parameters=fixed_parameters,
        product_output_variables=tuple(variable.name for variable in product_outputs),
        geometry=geometry,
        controllers=controllers,
        measurement_definition=(
            "Terminal liquid amount is converted to liquid volume with the live "
            "provider molar density. Top level uses a horizontal cylindrical "
            "vessel with two hemispherical heads; bottom level uses a vertical "
            "cylindrical sump. Both measurements are normalized level fractions."
        ),
        controller_definition=(
            "At each terminal, dI/dt=(Kc/Ti)*(level-level_setpoint) and "
            "log(product/reference)=I+Kc*(level-level_setpoint). The positive "
            "product draw uses the live terminal liquid composition."
        ),
    )


def _incidence(
    contract: TerminalInventoryControlContract,
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


def audit_terminal_inventory_control_contract(
    contract: TerminalInventoryControlContract,
) -> TerminalInventoryControlAudit:
    matrix, names = _incidence(contract)
    state_names = tuple(contract.state_coordinates)
    solve_dependencies = {
        dependency for row in contract.rows for dependency in row.solve_dependencies
    }
    state_dependencies = {
        dependency for row in contract.rows for dependency in row.state_dependencies
    }
    duplicate_names = tuple(sorted({name for name in names if names.count(name) > 1}))
    unregistered_solve = tuple(sorted(solve_dependencies - set(names)))
    unregistered_state = tuple(sorted(state_dependencies - set(state_names)))
    row_counts = np.asarray(matrix.getnnz(axis=1)).reshape((-1,))
    column_counts = np.asarray(matrix.getnnz(axis=0)).reshape((-1,))
    rank = structural_rank_fast(matrix)
    expected = len(contract.base.rows) + 4
    top = contract.base.topology.top_volume
    bottom = contract.base.topology.bottom_volume
    terminals = (top, bottom)
    controller_states = tuple(
        name
        for name in state_names
        if name in {_memory_state(volume) for volume in terminals}
    )
    controller_rates = tuple(
        variable
        for variable in contract.derivative_variables
        if variable.block == "terminal_level_controller_integrator_rate"
    )
    controller_outputs = tuple(
        variable
        for variable in contract.algebraic_variables
        if variable.block == "terminal_level_controller_output"
    )
    controller_rows = tuple(
        row
        for row in contract.rows
        if row.block.startswith("terminal_level_controller_")
    )
    boundary_ownership = all(
        _product_output(volume, top) in row.solve_dependencies
        for volume in terminals
        for row in contract.rows
        if row.owner == volume and row.block in {"component_balance", "energy_balance"}
    )
    interior_clean = all(
        not any(
            dependency in contract.product_output_variables
            or dependency.startswith("dI_level[")
            for dependency in row.solve_dependencies
        )
        for row in contract.rows
        if row.owner not in terminals
    )
    fixed_product_removed = not any(
        parameter in contract.fixed_parameters
        for parameter in contract.base.product_flow_parameters
    )
    geometry = contract.geometry
    geometry_valid = bool(
        geometry.top_head_shape == "two_hemispherical"
        and geometry.top_diameter_ft > 0.0
        and geometry.top_tangent_length_ft > 0.0
        and geometry.bottom_diameter_ft > 0.0
        and geometry.bottom_height_ft > 0.0
    )
    tuning = contract.controllers
    controller_parameters_valid = bool(
        tuning.top_kc > 0.0
        and tuning.top_ti_sec > 0.0
        and tuning.bottom_kc > 0.0
        and tuning.bottom_ti_sec > 0.0
        and 0.0 < tuning.product_rate_ratio_bounds[0] < 1.0
        and tuning.product_rate_ratio_bounds[1] > 1.0
    )
    base_passed = audit_dynamic_dae_contract(contract.base).pass_gate
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.controller_execution_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    pass_gate = bool(
        len(names) == len(contract.rows) == expected
        and rank == expected
        and not np.any(row_counts == 0)
        and not np.any(column_counts == 0)
        and not duplicate_names
        and not unregistered_solve
        and not unregistered_state
        and len(controller_states) == 2
        and len(controller_rates) == 2
        and len(controller_outputs) == 2
        and len(controller_rows) == 4
        and boundary_ownership
        and fixed_product_removed
        and interior_clean
        and geometry_valid
        and controller_parameters_valid
        and base_passed
        and preparation_only
    )
    return TerminalInventoryControlAudit(
        component_count=len(contract.base.component_names),
        volume_count=len(contract.base.topology.volume_ids),
        state_coordinate_count=len(state_names),
        derivative_variable_count=len(contract.derivative_variables),
        algebraic_variable_count=len(contract.algebraic_variables),
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        expected_count=expected,
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        zero_rows=tuple(
            contract.rows[index].name for index in np.flatnonzero(row_counts == 0)
        ),
        zero_columns=tuple(
            names[index] for index in np.flatnonzero(column_counts == 0)
        ),
        duplicate_variable_names=duplicate_names,
        unregistered_solve_dependencies=unregistered_solve,
        unregistered_state_dependencies=unregistered_state,
        controller_state_count=len(controller_states),
        controller_rate_count=len(controller_rates),
        controller_output_count=len(controller_outputs),
        controller_row_count=len(controller_rows),
        boundary_rows_own_live_product_outputs=boundary_ownership,
        fixed_product_parameters_removed=fixed_product_removed,
        interior_rows_without_controller_dependencies=interior_clean,
        geometry_valid=geometry_valid,
        controller_parameters_valid=controller_parameters_valid,
        base_contract_passed=base_passed,
        preparation_only=preparation_only,
        pass_gate=pass_gate,
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "TerminalInventoryControlAudit",
    "TerminalInventoryControlContract",
    "TerminalPIParameters",
    "TerminalVesselGeometry",
    "audit_terminal_inventory_control_contract",
    "build_terminal_inventory_control_contract",
]
