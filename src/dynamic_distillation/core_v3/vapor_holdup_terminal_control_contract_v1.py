"""Structural terminal level-control contract for the vapor-holdup model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

import numpy as np
from scipy.sparse import csr_matrix

from .dynamic_dae_contract_v1 import DAERow, SolveVariable
from .structural_rank_v1 import structural_rank_fast
from .vapor_holdup_dae_contract_v1 import (
    VaporHoldupDAEContract,
    audit_vapor_holdup_dae_contract,
)
from .vapor_holdup_geometry_v1 import (
    horizontal_drum_capacity_ft3,
    vertical_cylinder_capacity_ft3,
)


CONTRACT_NAME = "Core V3 - Vapor-Holdup Terminal Level Control"
CONTRACT_VERSION = "core-v3-vapor-holdup-terminal-control-contract-v1"
TOP_OUTPUT = "log_D_level_output"
BOTTOM_OUTPUT = "log_B_level_output"


@dataclass(frozen=True)
class VaporHoldupTerminalGeometry:
    drum_diameter_ft: float
    drum_tangent_length_ft: float
    drum_head_shape: str
    drum_gross_capacity_ft3: float
    sump_diameter_ft: float
    sump_height_ft: float
    sump_gross_capacity_ft3: float
    provenance: str


@dataclass(frozen=True)
class VaporHoldupLevelControllerSpecification:
    drum_level_setpoint_fraction: float
    drum_kc: float
    drum_ti_sec: float
    sump_level_setpoint_fraction: float
    sump_kc: float
    sump_ti_sec: float
    product_rate_ratio_bounds: tuple[float, float]


@dataclass(frozen=True)
class VaporHoldupTerminalControlContract:
    name: str
    version: str
    base: VaporHoldupDAEContract
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]
    geometry: VaporHoldupTerminalGeometry
    controllers: VaporHoldupLevelControllerSpecification
    level_definition: str
    controller_definition: str
    property_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    dynamic_integration_attempted: bool = False


@dataclass(frozen=True)
class VaporHoldupTerminalControlAudit:
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
    boundary_rows_own_product_outputs: bool
    fixed_product_parameters_removed: bool
    geometry_valid: bool
    tuning_valid: bool
    base_contract_passed: bool
    preparation_only: bool
    pass_gate: bool


def _required_positive(specs: Mapping[str, Any], key: str) -> float:
    value = specs.get(key)
    if value is None:
        raise ValueError(f"missing required terminal specification: {key}")
    number = float(value)
    if not np.isfinite(number) or number <= 0.0:
        raise ValueError(f"terminal specification must be positive: {key}")
    return number


def _fraction(specs: Mapping[str, Any], key: str) -> float:
    value = _required_positive(specs, key)
    if value >= 1.0:
        raise ValueError(f"terminal level fraction must be below one: {key}")
    return value


def terminal_geometry_from_specs(
    specs: Mapping[str, Any],
) -> VaporHoldupTerminalGeometry:
    """Read terminal dimensions from the normalized Excel specification map."""
    drum_diameter = _required_positive(specs, "Top Drum Diameter (ft)")
    drum_length = _required_positive(specs, "Top Drum Length (ft)")
    sump_diameter = _required_positive(specs, "Bottom Sump Diameter (ft)")
    sump_height = _required_positive(specs, "Bottom Sump Height (ft)")
    return VaporHoldupTerminalGeometry(
        drum_diameter_ft=drum_diameter,
        drum_tangent_length_ft=drum_length,
        drum_head_shape="two_hemispherical",
        drum_gross_capacity_ft3=horizontal_drum_capacity_ft3(
            drum_diameter, drum_length
        ),
        sump_diameter_ft=sump_diameter,
        sump_height_ft=sump_height,
        sump_gross_capacity_ft3=vertical_cylinder_capacity_ft3(
            sump_diameter, sump_height
        ),
        provenance="normalized C3/C4 workbook terminal dimensions",
    )


def level_controllers_from_specs(
    specs: Mapping[str, Any],
    *,
    default_drum_ti_sec: float = 120.0,
    product_rate_ratio_bounds: tuple[float, float] = (0.25, 2.0),
) -> VaporHoldupLevelControllerSpecification:
    drum_ti = specs.get("Top Level Ti (sec)")
    if drum_ti is None:
        drum_ti = default_drum_ti_sec
    return VaporHoldupLevelControllerSpecification(
        drum_level_setpoint_fraction=_fraction(specs, "Top Level SP Frac"),
        drum_kc=_required_positive(specs, "Top Level Kc"),
        drum_ti_sec=float(drum_ti),
        sump_level_setpoint_fraction=_fraction(specs, "Bottom Level SP Frac"),
        sump_kc=_required_positive(specs, "Bottom Level Kc"),
        sump_ti_sec=_required_positive(specs, "Bottom Level Ti (sec)"),
        product_rate_ratio_bounds=tuple(float(value) for value in product_rate_ratio_bounds),
    )


def _integral_state(volume: str) -> str:
    return f"I_level[{volume}]"


def _integral_rate(volume: str) -> str:
    return f"dI_level[{volume}]/dt"


def _product_output(volume: str, top_volume: str) -> str:
    return TOP_OUTPUT if volume == top_volume else BOTTOM_OUTPUT


def _terminal_level_dependencies(
    base: VaporHoldupDAEContract, volume: str
) -> tuple[str, ...]:
    dependencies = tuple(
        variable.name
        for variable in base.derivative_variables
        if variable.block == "liquid_component_inventory_rate"
        and variable.owner == volume
    )
    return (*dependencies, f"T[{volume}]", f"P[{volume}]")


def _add_product_output(
    row: DAERow,
    *,
    top_volume: str,
    bottom_volume: str,
) -> DAERow:
    if row.owner not in (top_volume, bottom_volume):
        return row
    if row.block not in {"liquid_component_balance", "total_energy_balance"}:
        return row
    output = _product_output(row.owner, top_volume)
    return replace(
        row,
        solve_dependencies=tuple(dict.fromkeys((*row.solve_dependencies, output))),
    )


def build_vapor_holdup_terminal_control_contract(
    base: VaporHoldupDAEContract,
    *,
    geometry: VaporHoldupTerminalGeometry,
    controllers: VaporHoldupLevelControllerSpecification,
) -> VaporHoldupTerminalControlContract:
    column = base.topology.column
    top_volume = column.top_volume
    bottom_volume = column.bottom_volume
    terminals = (top_volume, bottom_volume)
    controller_states = tuple(_integral_state(volume) for volume in terminals)
    controller_rates = tuple(
        SolveVariable(
            _integral_rate(volume),
            "level_controller_integrator_rate",
            volume,
        )
        for volume in terminals
    )
    product_outputs = tuple(
        SolveVariable(
            _product_output(volume, top_volume),
            "terminal_level_controller_output",
            volume,
        )
        for volume in terminals
    )
    physical_rows = tuple(
        _add_product_output(
            row,
            top_volume=top_volume,
            bottom_volume=bottom_volume,
        )
        for row in base.rows
    )
    controller_rows: list[DAERow] = []
    for volume in terminals:
        level_dependencies = _terminal_level_dependencies(base, volume)
        state_dependencies = (
            *(
                f"NL[{volume},{component}]"
                for component in base.component_names
            ),
            _integral_state(volume),
        )
        controller_rows.extend(
            (
                DAERow(
                    name=f"level_integrator[{volume}]",
                    block="level_controller_integrator",
                    owner=volume,
                    solve_dependencies=(
                        _integral_rate(volume),
                        *level_dependencies,
                    ),
                    state_dependencies=state_dependencies,
                ),
                DAERow(
                    name=f"level_output[{volume}]",
                    block="level_controller_output",
                    owner=volume,
                    solve_dependencies=(
                        _product_output(volume, top_volume),
                        _integral_rate(volume),
                        *level_dependencies,
                    ),
                    state_dependencies=state_dependencies,
                ),
            )
        )
    fixed_parameters = tuple(
        parameter
        for parameter in base.fixed_parameters
        if parameter not in {"D_fixed", "B_fixed"}
    )
    fixed_parameters = (
        *fixed_parameters,
        "D_reference",
        "B_reference",
        "top_level_setpoint_fraction",
        "bottom_level_setpoint_fraction",
        "terminal_level_controller_tuning",
        "terminal_vessel_geometry_from_workbook",
    )
    return VaporHoldupTerminalControlContract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        base=base,
        state_coordinates=(*base.state_coordinates, *controller_states),
        derivative_variables=(*base.derivative_variables, *controller_rates),
        algebraic_variables=(*base.algebraic_variables, *product_outputs),
        rows=(*physical_rows, *controller_rows),
        fixed_parameters=fixed_parameters,
        geometry=geometry,
        controllers=controllers,
        level_definition=(
            "Terminal liquid volume equals total NL divided by live DWSIM liquid "
            "molar density. Reflux-drum level uses the workbook horizontal drum "
            "with two hemispherical heads; sump level uses the workbook vertical "
            "cylinder. Reboiler vapor extension is excluded from sump level."
        ),
        controller_definition=(
            "Each PI controller owns its terminal liquid product rate: the drum "
            "controller manipulates D and the sump controller manipulates B. "
            "Product composition is the live terminal liquid composition."
        ),
    )


def _incidence(
    contract: VaporHoldupTerminalControlContract,
) -> tuple[csr_matrix, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    state_names = set(contract.state_coordinates)
    matrix = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    unknown_solve: set[str] = set()
    unknown_state: set[str] = set()
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                matrix[row_index, index[dependency]] = 1
            else:
                unknown_solve.add(dependency)
        for dependency in row.state_dependencies:
            if dependency not in state_names:
                unknown_state.add(dependency)
    return (
        csr_matrix(matrix),
        names,
        tuple(sorted(unknown_solve)),
        tuple(sorted(unknown_state)),
    )


def audit_vapor_holdup_terminal_control_contract(
    contract: VaporHoldupTerminalControlContract,
) -> VaporHoldupTerminalControlAudit:
    matrix, names, unknown_solve, unknown_state = _incidence(contract)
    rank = structural_rank_fast(matrix)
    row_counts = np.asarray(matrix.sum(axis=1)).ravel()
    column_counts = np.asarray(matrix.sum(axis=0)).ravel()
    zero_rows = tuple(
        row.name
        for row, count in zip(contract.rows, row_counts, strict=True)
        if not count
    )
    zero_columns = tuple(
        name for name, count in zip(names, column_counts, strict=True) if not count
    )
    duplicates = tuple(sorted({name for name in names if names.count(name) > 1}))
    base_audit = audit_vapor_holdup_dae_contract(contract.base)
    top_volume = contract.base.topology.column.top_volume
    bottom_volume = contract.base.topology.column.bottom_volume
    terminal_rows = tuple(
        row
        for row in contract.rows
        if row.owner in (top_volume, bottom_volume)
        and row.block in {"liquid_component_balance", "total_energy_balance"}
    )
    boundary_ownership = bool(
        terminal_rows
        and all(
            _product_output(row.owner, top_volume) in row.solve_dependencies
            for row in terminal_rows
        )
    )
    geometry = contract.geometry
    geometry_valid = bool(
        geometry.drum_head_shape == "two_hemispherical"
        and geometry.drum_diameter_ft > 0.0
        and geometry.drum_tangent_length_ft > 0.0
        and geometry.drum_gross_capacity_ft3 > 0.0
        and geometry.sump_diameter_ft > 0.0
        and geometry.sump_height_ft > 0.0
        and geometry.sump_gross_capacity_ft3 > 0.0
        and geometry.provenance
    )
    tuning = contract.controllers
    lo, hi = tuning.product_rate_ratio_bounds
    tuning_valid = bool(
        0.0 < tuning.drum_level_setpoint_fraction < 1.0
        and tuning.drum_kc > 0.0
        and tuning.drum_ti_sec > 0.0
        and 0.0 < tuning.sump_level_setpoint_fraction < 1.0
        and tuning.sump_kc > 0.0
        and tuning.sump_ti_sec > 0.0
        and 0.0 < lo < 1.0 < hi
    )
    fixed_products_removed = bool(
        "D_fixed" not in contract.fixed_parameters
        and "B_fixed" not in contract.fixed_parameters
        and "D_reference" in contract.fixed_parameters
        and "B_reference" in contract.fixed_parameters
    )
    controller_states = tuple(
        name for name in contract.state_coordinates if name.startswith("I_level[")
    )
    controller_rates = tuple(
        variable
        for variable in contract.derivative_variables
        if variable.block == "level_controller_integrator_rate"
    )
    controller_outputs = tuple(
        variable
        for variable in contract.algebraic_variables
        if variable.block == "terminal_level_controller_output"
    )
    controller_rows = tuple(
        row for row in contract.rows if row.block.startswith("level_controller_")
    )
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    expected = base_audit.expected_solve_count + 4
    passed = bool(
        base_audit.pass_gate
        and len(names) == len(contract.rows) == expected
        and rank == expected
        and not zero_rows
        and not zero_columns
        and not duplicates
        and not unknown_solve
        and not unknown_state
        and len(controller_states) == 2
        and len(controller_rates) == 2
        and len(controller_outputs) == 2
        and len(controller_rows) == 4
        and boundary_ownership
        and fixed_products_removed
        and geometry_valid
        and tuning_valid
        and preparation_only
    )
    return VaporHoldupTerminalControlAudit(
        component_count=len(contract.base.component_names),
        volume_count=len(contract.base.topology.column.volume_ids),
        state_coordinate_count=len(contract.state_coordinates),
        derivative_variable_count=len(contract.derivative_variables),
        algebraic_variable_count=len(contract.algebraic_variables),
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        expected_count=expected,
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        zero_rows=zero_rows,
        zero_columns=zero_columns,
        duplicate_variable_names=duplicates,
        unregistered_solve_dependencies=unknown_solve,
        unregistered_state_dependencies=unknown_state,
        controller_state_count=len(controller_states),
        controller_rate_count=len(controller_rates),
        controller_output_count=len(controller_outputs),
        controller_row_count=len(controller_rows),
        boundary_rows_own_product_outputs=boundary_ownership,
        fixed_product_parameters_removed=fixed_products_removed,
        geometry_valid=geometry_valid,
        tuning_valid=tuning_valid,
        base_contract_passed=base_audit.pass_gate,
        preparation_only=preparation_only,
        pass_gate=passed,
    )


__all__ = [
    "BOTTOM_OUTPUT",
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "TOP_OUTPUT",
    "VaporHoldupLevelControllerSpecification",
    "VaporHoldupTerminalControlAudit",
    "VaporHoldupTerminalControlContract",
    "VaporHoldupTerminalGeometry",
    "audit_vapor_holdup_terminal_control_contract",
    "build_vapor_holdup_terminal_control_contract",
    "level_controllers_from_specs",
    "terminal_geometry_from_specs",
]
