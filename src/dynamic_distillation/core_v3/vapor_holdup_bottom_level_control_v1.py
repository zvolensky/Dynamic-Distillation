"""Bottom-sump PI level control for the vapor-holdup model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from .dynamic_dae_contract_v1 import DAERow, SolveVariable
from .provider_call_audit_v1 import ProviderCallAudit
from .structural_rank_v1 import structural_rank_fast
from .vapor_holdup_dae_contract_v1 import (
    VaporHoldupDAEContract,
    audit_vapor_holdup_dae_contract,
)
from .vapor_holdup_implicit_residual_v1 import (
    VaporHoldupImplicitEvaluation,
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
)
from .vapor_holdup_implicit_step_bounds_v1 import (
    vapor_holdup_implicit_step_coordinate_bounds,
)
from .vapor_holdup_terminal_control_contract_v1 import (
    BOTTOM_OUTPUT,
    VaporHoldupTerminalGeometry,
    terminal_level_fractions,
)


INTEGRAL_STATE = "I_level[reboiler_sump]"
INTEGRAL_RATE = "dI_level[reboiler_sump]/dt"


@dataclass(frozen=True)
class BottomLevelControllerSpecification:
    setpoint_fraction: float
    kc: float
    ti_sec: float


@dataclass(frozen=True)
class VaporHoldupBottomLevelControlContract:
    base: VaporHoldupDAEContract
    geometry: VaporHoldupTerminalGeometry
    controller: BottomLevelControllerSpecification
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]


@dataclass(frozen=True)
class VaporHoldupBottomLevelControlEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    coordinates: np.ndarray
    level_fraction: np.ndarray
    bottom_level_error: float
    controller_rate_per_sec: float
    controller_memory_previous: float
    controller_memory_endpoint: float
    bottoms_log_ratio: float
    bottoms_command_lbmolph: float
    bottoms_actuator_multiplier: float
    distillate_lbmolph: float
    bottoms_lbmolph: float
    base: VaporHoldupImplicitEvaluation


def build_vapor_holdup_bottom_level_control_contract(
    base: VaporHoldupDAEContract,
    *,
    geometry: VaporHoldupTerminalGeometry,
    controller: BottomLevelControllerSpecification,
) -> VaporHoldupBottomLevelControlContract:
    """Add only a bottom-sump level loop; distillate flow remains fixed."""
    if not 0.0 < float(controller.setpoint_fraction) < 1.0:
        raise ValueError("bottom level setpoint must be between zero and one")
    if not np.isfinite(controller.kc) or float(controller.kc) <= 0.0:
        raise ValueError("bottom controller gain must be positive and finite")
    if not np.isfinite(controller.ti_sec) or float(controller.ti_sec) <= 0.0:
        raise ValueError("bottom controller integral time must be positive and finite")
    bottom = base.topology.column.bottom_volume
    level_dependencies = tuple(
        variable.name
        for variable in base.derivative_variables
        if variable.block == "liquid_component_inventory_rate"
        and variable.owner == bottom
    ) + (f"T[{bottom}]", f"P[{bottom}]")
    physical_rows = tuple(
        replace(
            row,
            solve_dependencies=tuple(
                dict.fromkeys((*row.solve_dependencies, BOTTOM_OUTPUT))
            ),
        )
        if row.owner == bottom
        and row.block in {"liquid_component_balance", "total_energy_balance"}
        else row
        for row in base.rows
    )
    state_dependencies = (
        *(f"NL[{bottom},{component}]" for component in base.component_names),
        INTEGRAL_STATE,
    )
    controller_rows = (
        DAERow(
            name=f"level_integrator[{bottom}]",
            block="bottom_level_controller_integrator",
            owner=bottom,
            solve_dependencies=(INTEGRAL_RATE, *level_dependencies),
            state_dependencies=state_dependencies,
        ),
        DAERow(
            name=f"level_output[{bottom}]",
            block="bottom_level_controller_output",
            owner=bottom,
            solve_dependencies=(BOTTOM_OUTPUT, INTEGRAL_RATE, *level_dependencies),
            state_dependencies=state_dependencies,
        ),
    )
    return VaporHoldupBottomLevelControlContract(
        base=base,
        geometry=geometry,
        controller=controller,
        state_coordinates=(*base.state_coordinates, INTEGRAL_STATE),
        derivative_variables=(
            *base.derivative_variables,
            SolveVariable(
                INTEGRAL_RATE,
                "bottom_level_controller_integrator_rate",
                bottom,
            ),
        ),
        algebraic_variables=(
            *base.algebraic_variables,
            SolveVariable(BOTTOM_OUTPUT, "bottom_level_controller_output", bottom),
        ),
        rows=(*physical_rows, *controller_rows),
        fixed_parameters=(
            *base.fixed_parameters,
            "bottoms_reference",
            "bottom_level_setpoint_fraction",
            "bottom_level_controller_tuning",
            "terminal_vessel_geometry_from_workbook",
        ),
    )


def bottom_level_control_variable_names(
    contract: VaporHoldupBottomLevelControlContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )


def bottom_level_control_pattern(
    contract: VaporHoldupBottomLevelControlContract,
) -> np.ndarray:
    names = bottom_level_control_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            column = index.get(dependency)
            if column is not None:
                pattern[row_index, column] = True
    return pattern


def audit_vapor_holdup_bottom_level_control_contract(
    contract: VaporHoldupBottomLevelControlContract,
) -> dict[str, Any]:
    pattern = bottom_level_control_pattern(contract)
    dimension = len(contract.rows)
    rank = structural_rank_fast(pattern)
    names = bottom_level_control_variable_names(contract)
    base_pass = audit_vapor_holdup_dae_contract(contract.base).pass_gate
    passed = bool(
        base_pass
        and pattern.shape == (dimension, dimension)
        and rank == dimension
        and np.all(np.any(pattern, axis=0))
        and np.all(np.any(pattern, axis=1))
        and len(names) == len(set(names))
    )
    return {
        "dimension": dimension,
        "structural_rank": int(rank),
        "base_contract_passed": bool(base_pass),
        "pass_gate": passed,
    }


def _split_coordinates(
    contract: VaporHoldupBottomLevelControlContract,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, float, float]:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("bottom-level controlled coordinates are invalid")
    rate_count = len(contract.base.derivative_variables)
    algebraic_count = len(contract.base.algebraic_variables)
    base_coordinates = np.concatenate(
        (point[:rate_count], point[rate_count + 1 : rate_count + 1 + algebraic_count])
    )
    return base_coordinates, float(point[rate_count]), float(point[-1])


def bottom_level_control_initial_coordinates(
    contract: VaporHoldupBottomLevelControlContract,
    *,
    controller_rate_per_sec: float,
    timestep_sec: float,
    previous_coordinates: Sequence[float] | None = None,
    bottoms_log_ratio_previous: float = 0.0,
) -> np.ndarray:
    rate = float(controller_rate_per_sec)
    timestep = float(timestep_sec)
    if not np.isfinite(rate) or not np.isfinite(timestep) or timestep <= 0.0:
        raise ValueError("invalid bottom controller predictor")
    if previous_coordinates is None:
        point = np.zeros(len(contract.rows), dtype=float)
    else:
        point = np.asarray(previous_coordinates, dtype=float).reshape((-1,)).copy()
        if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
            raise ValueError("previous bottom-level coordinates are invalid")
    rate_index = len(contract.base.derivative_variables)
    point[rate_index] = rate
    point[-1] = float(bottoms_log_ratio_previous) + timestep * rate
    return point


def bottom_level_control_bounds(
    contract: VaporHoldupBottomLevelControlContract,
) -> tuple[np.ndarray, np.ndarray]:
    """Embed base local bounds plus broad numerical guards for the PI variables."""
    base_lower, base_upper = vapor_holdup_implicit_step_coordinate_bounds(contract.base)
    base_rate_count = len(contract.base.derivative_variables)
    lower = np.empty(len(contract.rows), dtype=float)
    upper = np.empty(len(contract.rows), dtype=float)
    lower[:base_rate_count] = base_lower[:base_rate_count]
    upper[:base_rate_count] = base_upper[:base_rate_count]
    lower[base_rate_count], upper[base_rate_count] = -0.01, 0.01
    lower[base_rate_count + 1 : -1] = base_lower[base_rate_count:]
    upper[base_rate_count + 1 : -1] = base_upper[base_rate_count:]
    lower[-1], upper[-1] = -np.log(10.0), np.log(10.0)
    return lower, upper


def evaluate_vapor_holdup_bottom_level_control_residual(
    contract: VaporHoldupBottomLevelControlContract,
    geometry: Sequence[Any],
    reference: VaporHoldupImplicitReference,
    balance_inputs: Any,
    hydraulic_geometry: Sequence[Any],
    numerical: VaporHoldupImplicitNumericalSpec,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    controller_memory_previous: float,
    bottoms_actuator_multiplier: float = 1.0,
    state_id: str,
    evaluation_kind: str,
) -> VaporHoldupBottomLevelControlEvaluation:
    base_coordinates, controller_rate, bottoms_log = _split_coordinates(
        contract, coordinates
    )
    timestep = float(numerical.timestep_sec)
    memory_previous = float(controller_memory_previous)
    memory_endpoint = memory_previous + timestep * controller_rate
    actuator_multiplier = float(bottoms_actuator_multiplier)
    if not np.isfinite(actuator_multiplier) or actuator_multiplier <= 0.0:
        raise ValueError("bottoms actuator multiplier must be positive and finite")
    bottoms_command = float(balance_inputs.bottoms_lbmolph) * np.exp(bottoms_log)
    bottoms = bottoms_command * actuator_multiplier
    if not np.isfinite(bottoms) or bottoms <= 0.0:
        raise RuntimeError("bottom controller produced a nonphysical bottoms rate")
    live_inputs = replace(balance_inputs, bottoms_lbmolph=float(bottoms))
    base = evaluate_vapor_holdup_implicit_residual(
        contract.base,
        geometry,
        reference,
        live_inputs,
        hydraulic_geometry,
        numerical,
        provider,
        call_audit,
        base_coordinates,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    levels = terminal_level_fractions(
        base.endpoint.liquid_component_inventory_lbmol,
        base.properties.liquid_density_lbmol_ft3,
        contract.geometry,
    )
    error = float(levels[1] - contract.controller.setpoint_fraction)
    controller_raw = np.asarray(
        (
            contract.controller.ti_sec * controller_rate - contract.controller.kc * error,
            bottoms_log - memory_endpoint - contract.controller.kc * error,
        ),
        dtype=float,
    )
    raw = np.concatenate((base.raw, controller_raw))
    scaled = np.concatenate((base.scaled, controller_raw))
    return VaporHoldupBottomLevelControlEvaluation(
        raw=raw,
        scaled=scaled,
        row_names=tuple(row.name for row in contract.rows),
        variable_names=bottom_level_control_variable_names(contract),
        coordinates=np.asarray(coordinates, dtype=float).copy(),
        level_fraction=levels,
        bottom_level_error=error,
        controller_rate_per_sec=controller_rate,
        controller_memory_previous=memory_previous,
        controller_memory_endpoint=memory_endpoint,
        bottoms_log_ratio=bottoms_log,
        bottoms_command_lbmolph=float(bottoms_command),
        bottoms_actuator_multiplier=actuator_multiplier,
        distillate_lbmolph=float(balance_inputs.distillate_lbmolph),
        bottoms_lbmolph=float(bottoms),
        base=base,
    )


__all__ = [
    "BottomLevelControllerSpecification",
    "VaporHoldupBottomLevelControlContract",
    "VaporHoldupBottomLevelControlEvaluation",
    "audit_vapor_holdup_bottom_level_control_contract",
    "bottom_level_control_bounds",
    "bottom_level_control_initial_coordinates",
    "bottom_level_control_pattern",
    "bottom_level_control_variable_names",
    "build_vapor_holdup_bottom_level_control_contract",
    "evaluate_vapor_holdup_bottom_level_control_residual",
]
