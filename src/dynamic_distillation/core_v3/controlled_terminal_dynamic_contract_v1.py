"""Structural Core V3 dynamic contract with terminal level controllers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    ConservedNUPressureDAEContract,
    build_conserved_nu_pressure_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import DAERow, SolveVariable
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS


CONTRACT_NAME = "Core V3 - Controlled-Terminal Dynamic DAE Contract"
CONTRACT_VERSION = "core-v3-controlled-terminal-dynamic-contract-v1"
DRUM = VOLUME_IDS[0]
SUMP = VOLUME_IDS[-1]


@dataclass(frozen=True)
class TerminalGeometry:
    drum_diameter_ft: float
    drum_tangent_length_ft: float
    drum_head_shape: str
    sump_diameter_ft: float
    sump_height_ft: float


@dataclass(frozen=True)
class LevelControllerSpecification:
    drum_kc: float
    drum_ti_sec: float
    sump_kc: float
    sump_ti_sec: float
    product_rate_ratio_bounds: tuple[float, float]


@dataclass(frozen=True)
class ControlledTerminalDynamicContract:
    name: str
    version: str
    base: ConservedNUPressureDAEContract
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    geometry: TerminalGeometry
    controllers: LevelControllerSpecification
    level_definition: str
    controller_definition: str
    property_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class ControlledTerminalDynamicAudit:
    component_count: int
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
    boundary_rows_own_product_outputs: bool
    geometry_valid: bool
    tuning_valid: bool
    inherited_conservation: bool
    preparation_only: bool
    pass_gate: bool


def _integral_state(volume: str) -> str:
    return f"I_level[{volume}]"


def _integral_rate(volume: str) -> str:
    return f"dI_level[{volume}]/dt"


def _product_output(volume: str) -> str:
    return "log_D_level_output" if volume == DRUM else "log_B_level_output"


def _level_solve_dependencies(
    base: ConservedNUPressureDAEContract, volume: str
) -> tuple[str, ...]:
    dependencies = [
        variable.name
        for variable in base.derivative_variables
        if variable.block == "component_inventory_rate" and variable.owner == volume
    ]
    dependencies.append(f"T[{volume}]")
    if volume != DRUM:
        dependencies.append(f"P[{volume}]")
    return tuple(dependencies)


def _add_product_output(row: DAERow) -> DAERow:
    if row.owner == DRUM and row.block in {"component_balance", "energy_balance"}:
        return replace(row, solve_dependencies=(*row.solve_dependencies, _product_output(DRUM)))
    if row.owner == SUMP and row.block in {"component_balance", "energy_balance"}:
        return replace(row, solve_dependencies=(*row.solve_dependencies, _product_output(SUMP)))
    return row


def build_controlled_terminal_dynamic_contract(
    component_names: Sequence[str],
    *,
    geometry: TerminalGeometry,
    controllers: LevelControllerSpecification,
) -> ControlledTerminalDynamicContract:
    base = build_conserved_nu_pressure_dae_contract(component_names)
    controller_states = (_integral_state(DRUM), _integral_state(SUMP))
    controller_rates = tuple(
        SolveVariable(_integral_rate(volume), "level_controller_integrator_rate", volume)
        for volume in (DRUM, SUMP)
    )
    product_outputs = tuple(
        SolveVariable(_product_output(volume), "terminal_level_controller_output", volume)
        for volume in (DRUM, SUMP)
    )
    physical_rows = tuple(_add_product_output(row) for row in base.rows)
    controller_rows: list[DAERow] = []
    for volume in (DRUM, SUMP):
        level_dependencies = _level_solve_dependencies(base, volume)
        state_dependencies = (
            *(f"N[{volume},{component}]" for component in base.component_names),
            _integral_state(volume),
        )
        controller_rows.extend(
            (
                DAERow(
                    name=f"level_integrator[{volume}]",
                    block="level_controller_integrator",
                    owner=volume,
                    solve_dependencies=(_integral_rate(volume), *level_dependencies),
                    state_dependencies=state_dependencies,
                ),
                DAERow(
                    name=f"level_output[{volume}]",
                    block="level_controller_output",
                    owner=volume,
                    solve_dependencies=(
                        _product_output(volume),
                        _integral_rate(volume),
                        *level_dependencies,
                    ),
                    state_dependencies=state_dependencies,
                ),
            )
        )
    return ControlledTerminalDynamicContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        base=base,
        state_coordinates=(*base.state_coordinates, *controller_states),
        derivative_variables=(*base.derivative_variables, *controller_rates),
        algebraic_variables=(*base.algebraic_variables, *product_outputs),
        rows=(*physical_rows, *controller_rows),
        geometry=geometry,
        controllers=controllers,
        level_definition=(
            "Liquid volume is total component inventory divided by live DWSIM "
            "liquid molar density. Drum height uses a horizontal cylinder with "
            "two hemispherical heads; sump height uses a vertical cylinder."
        ),
        controller_definition=(
            "For each terminal, dI/dt=(Kc/Ti)*(level-level_setpoint) and "
            "log(product/reference)=I+Kc*(level-level_setpoint). Controller "
            "memory is initialized from the DD-122 steady product output."
        ),
    )


def _incidence(contract: ControlledTerminalDynamicContract):
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    matrix = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                matrix[row_index, index[dependency]] = 1
    return csr_matrix(matrix), names


def audit_controlled_terminal_dynamic_contract(
    contract: ControlledTerminalDynamicContract,
) -> ControlledTerminalDynamicAudit:
    matrix, names = _incidence(contract)
    state_names = tuple(contract.state_coordinates)
    solve_dependencies = {item for row in contract.rows for item in row.solve_dependencies}
    state_dependencies = {item for row in contract.rows for item in row.state_dependencies}
    duplicate_names = tuple(sorted({name for name in names if names.count(name) > 1}))
    unregistered_solve = tuple(sorted(solve_dependencies - set(names)))
    unregistered_state = tuple(sorted(state_dependencies - set(state_names)))
    row_counts = np.asarray(matrix.getnnz(axis=1)).reshape((-1,))
    column_counts = np.asarray(matrix.getnnz(axis=0)).reshape((-1,))
    rank = int(structural_rank(matrix))
    expected = 10 * len(contract.base.component_names) + 20
    controller_states = tuple(name for name in state_names if name.startswith("I_level["))
    controller_rates = tuple(
        variable for variable in contract.derivative_variables
        if variable.block == "level_controller_integrator_rate"
    )
    controller_outputs = tuple(
        variable for variable in contract.algebraic_variables
        if variable.block == "terminal_level_controller_output"
    )
    controller_rows = tuple(row for row in contract.rows if row.block.startswith("level_controller_"))
    top_boundary = tuple(
        row for row in contract.rows
        if row.owner == DRUM and row.block in {"component_balance", "energy_balance"}
    )
    bottom_boundary = tuple(
        row for row in contract.rows
        if row.owner == SUMP and row.block in {"component_balance", "energy_balance"}
    )
    boundary_ownership = bool(
        top_boundary and bottom_boundary
        and all(_product_output(DRUM) in row.solve_dependencies for row in top_boundary)
        and all(_product_output(SUMP) in row.solve_dependencies for row in bottom_boundary)
    )
    geometry = contract.geometry
    geometry_valid = bool(
        geometry.drum_head_shape == "two_hemispherical"
        and geometry.drum_diameter_ft > 0.0
        and geometry.drum_tangent_length_ft > 0.0
        and geometry.sump_diameter_ft > 0.0
        and geometry.sump_height_ft > 0.0
    )
    tuning = contract.controllers
    tuning_valid = bool(
        tuning.drum_kc > 0.0
        and tuning.drum_ti_sec > 0.0
        and tuning.sump_kc > 0.0
        and tuning.sump_ti_sec > 0.0
        and 0.0 < tuning.product_rate_ratio_bounds[0] < 1.0
        and tuning.product_rate_ratio_bounds[1] > 1.0
    )
    preparation_only = not any(
        (contract.property_evaluation_attempted, contract.nonlinear_solve_attempted, contract.dynamic_integration_attempted)
    )
    passed = bool(
        len(names) == len(contract.rows) == expected
        and rank == expected
        and not np.any(row_counts == 0)
        and not np.any(column_counts == 0)
        and not duplicate_names
        and not unregistered_solve
        and not unregistered_state
        and len(controller_states) == len(controller_rates) == len(controller_outputs) == 2
        and len(controller_rows) == 4
        and boundary_ownership
        and geometry_valid
        and tuning_valid
        and preparation_only
    )
    return ControlledTerminalDynamicAudit(
        component_count=len(contract.base.component_names),
        state_coordinate_count=len(state_names),
        derivative_variable_count=len(contract.derivative_variables),
        algebraic_variable_count=len(contract.algebraic_variables),
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        expected_count=expected,
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        zero_rows=tuple(contract.rows[index].name for index in np.flatnonzero(row_counts == 0)),
        zero_columns=tuple(names[index] for index in np.flatnonzero(column_counts == 0)),
        duplicate_variable_names=duplicate_names,
        unregistered_solve_dependencies=unregistered_solve,
        unregistered_state_dependencies=unregistered_state,
        controller_state_count=len(controller_states),
        controller_rate_count=len(controller_rates),
        controller_output_count=len(controller_outputs),
        controller_row_count=len(controller_rows),
        boundary_rows_own_product_outputs=boundary_ownership,
        geometry_valid=geometry_valid,
        tuning_valid=tuning_valid,
        inherited_conservation=True,
        preparation_only=preparation_only,
        pass_gate=passed,
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "ControlledTerminalDynamicAudit",
    "ControlledTerminalDynamicContract",
    "LevelControllerSpecification",
    "TerminalGeometry",
    "audit_controlled_terminal_dynamic_contract",
    "build_controlled_terminal_dynamic_contract",
]
