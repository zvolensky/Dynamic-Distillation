"""Backward-Euler kernel for the controlled-terminal conserved Core V3 DAE."""

from __future__ import annotations

from dataclasses import dataclass, replace
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.conserved_nu_implicit_step_v1 import (
    ConservedNUBackwardEulerEvaluation,
    evaluate_conserved_nu_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_dynamic_contract_v1 import (
    ControlledTerminalDynamicContract,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    controlled_terminal_zero_time_variable_names,
    terminal_level_fractions,
)
from dynamic_distillation.core_v3.implicit_step_v1 import ImplicitStepSettings
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


@dataclass(frozen=True)
class ControlledTerminalBackwardEulerEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    solve_coordinates: np.ndarray
    previous_controller_memory: np.ndarray
    endpoint_controller_memory: np.ndarray
    controller_rate_per_sec: np.ndarray
    level_fraction: np.ndarray
    level_error: np.ndarray
    product_log_ratio: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    base: ConservedNUBackwardEulerEvaluation


@dataclass(frozen=True)
class ControlledTerminalImplicitStepOutcome:
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None
    wall_clock_sec: float
    final_coordinates: np.ndarray
    final_scaled_residual_inf_norm: float
    evaluation: ControlledTerminalBackwardEulerEvaluation


def _state_to_rate_name(name: str) -> str | None:
    if name.startswith("N[") or name.startswith("U["):
        return f"d{name}/dt"
    if name.startswith("I_level["):
        return f"d{name}/dt"
    return None


def controlled_terminal_step_pattern(
    contract: ControlledTerminalDynamicContract,
) -> np.ndarray:
    names = controlled_terminal_zero_time_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        dependencies = set(row.solve_dependencies)
        dependencies.update(
            mapped
            for state in row.state_dependencies
            if (mapped := _state_to_rate_name(state)) is not None
        )
        for dependency in dependencies:
            if dependency in index:
                pattern[row_index, index[dependency]] = True
    return pattern


def _split_coordinates(
    contract: ControlledTerminalDynamicContract,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("controlled-terminal step coordinates are invalid")
    base_rate_count = len(contract.base.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    controller_start = base_rate_count
    algebraic_start = controller_start + 2
    product_start = algebraic_start + base_algebraic_count
    base = np.concatenate(
        (point[:base_rate_count], point[algebraic_start:product_start])
    )
    return base, point[controller_start:algebraic_start], point[product_start:]


def evaluate_controlled_terminal_backward_euler_residual(
    contract: ControlledTerminalDynamicContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    previous_inventory_lbmol: Sequence[Sequence[float]],
    previous_top_internal_energy_BTU: float,
    previous_lower_internal_energy_BTU: Sequence[float],
    previous_controller_memory: Sequence[float],
    level_setpoints: TerminalLevelSetpoints,
    component_rate_scale_lbmolph: float,
    energy_rate_scales_BTUph: Sequence[float],
    solve_coordinates: Sequence[float],
    step_seconds: float,
    fixed_steady_scales: Sequence[float],
    storage_scales_BTU: Sequence[float],
    pressure_numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> ControlledTerminalBackwardEulerEvaluation:
    if not np.isfinite(step_seconds) or step_seconds <= 0.0:
        raise ValueError("controlled-terminal backward-Euler step must be positive")
    base_coordinates, controller_rates, product_logs = _split_coordinates(
        contract, solve_coordinates
    )
    previous_memory = np.asarray(previous_controller_memory, dtype=float).reshape((-1,))
    if previous_memory.shape != (2,) or np.any(~np.isfinite(previous_memory)):
        raise ValueError("previous controller memory is invalid")
    products = np.asarray(
        (
            float(template.distillate_lbmolph) * np.exp(product_logs[0]),
            float(template.bottoms_lbmolph) * np.exp(product_logs[1]),
        ),
        dtype=float,
    )
    if np.any(~np.isfinite(products)) or np.any(products <= 0.0):
        raise ValueError("controlled-terminal product output is invalid")
    live_template = replace(
        template,
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
    )
    base = evaluate_conserved_nu_backward_euler_residual(
        contract.base,
        spec,
        reference,
        live_template,
        provider,
        call_audit,
        previous_inventory_lbmol=previous_inventory_lbmol,
        previous_top_internal_energy_BTU=previous_top_internal_energy_BTU,
        previous_lower_internal_energy_BTU=previous_lower_internal_energy_BTU,
        component_rate_scale_lbmolph=component_rate_scale_lbmolph,
        energy_rate_scales_BTUph=energy_rate_scales_BTUph,
        solve_coordinates=base_coordinates,
        step_seconds=step_seconds,
        fixed_steady_scales=fixed_steady_scales,
        storage_scales_BTU=storage_scales_BTU,
        numerical=pressure_numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    properties = (
        base.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
        .properties
    )
    levels = terminal_level_fractions(
        base.endpoint_inventory_lbmol,
        properties.liquid_density_lbmol_ft3,
        contract.geometry,
    )
    setpoints = np.asarray(
        (level_setpoints.drum_fraction, level_setpoints.sump_fraction), dtype=float
    )
    if np.any(~np.isfinite(setpoints)) or np.any((setpoints <= 0.0) | (setpoints >= 1.0)):
        raise ValueError("terminal level setpoints are invalid")
    errors = levels - setpoints
    endpoint_memory = previous_memory + float(step_seconds) * controller_rates
    gains = np.asarray((contract.controllers.drum_kc, contract.controllers.sump_kc))
    times = np.asarray((contract.controllers.drum_ti_sec, contract.controllers.sump_ti_sec))
    controller_raw = np.asarray(
        (
            times[0] * controller_rates[0] - gains[0] * errors[0],
            product_logs[0] - endpoint_memory[0] - gains[0] * errors[0],
            times[1] * controller_rates[1] - gains[1] * errors[1],
            product_logs[1] - endpoint_memory[1] - gains[1] * errors[1],
        ),
        dtype=float,
    )
    raw = np.concatenate((base.raw, controller_raw))
    scaled = np.concatenate((base.scaled, controller_raw))
    point = np.asarray(solve_coordinates, dtype=float).copy()
    base_rate_count = len(contract.base.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    algebraic_start = base_rate_count + 2
    point[:base_rate_count] = base.solve_coordinates[:base_rate_count]
    point[algebraic_start:algebraic_start + base_algebraic_count] = (
        base.solve_coordinates[base_rate_count:]
    )
    return ControlledTerminalBackwardEulerEvaluation(
        raw=raw,
        scaled=scaled,
        row_names=tuple(row.name for row in contract.rows),
        variable_names=controlled_terminal_zero_time_variable_names(contract),
        solve_coordinates=point,
        previous_controller_memory=previous_memory.copy(),
        endpoint_controller_memory=endpoint_memory,
        controller_rate_per_sec=controller_rates.copy(),
        level_fraction=levels,
        level_error=errors,
        product_log_ratio=product_logs.copy(),
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
        base=base,
    )


def solve_controlled_terminal_backward_euler_step(
    contract: ControlledTerminalDynamicContract,
    objective: Callable[[np.ndarray, str], ControlledTerminalBackwardEulerEvaluation],
    initial_coordinates: Sequence[float],
    settings: ImplicitStepSettings,
    *,
    name: str,
) -> ControlledTerminalImplicitStepOutcome:
    initial = np.asarray(initial_coordinates, dtype=float).reshape((-1,))
    pattern = controlled_terminal_step_pattern(contract)

    def residual(point: np.ndarray) -> np.ndarray:
        return objective(point, f"{name}:solve:residual").scaled

    def jacobian(point: np.ndarray) -> np.ndarray:
        matrix, _groups = colored_central_difference_jacobian(
            lambda candidate, state_id: objective(candidate, state_id).scaled,
            point,
            pattern=pattern,
            step=settings.jacobian_step,
            state_id=f"{name}:solve:jacobian",
        )
        return matrix

    lower = np.full(initial.shape, -np.inf)
    upper = np.full(initial.shape, np.inf)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    lower[-2:] = np.log(product_low)
    upper[-2:] = np.log(product_high)
    started = time.perf_counter()
    result = least_squares(
        residual,
        initial,
        jac=jacobian,
        bounds=(lower, upper),
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=settings.x_scale,
    )
    elapsed = time.perf_counter() - started
    endpoint = objective(result.x, f"{name}:solve:endpoint")
    return ControlledTerminalImplicitStepOutcome(
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
        njev=None if result.njev is None else int(result.njev),
        wall_clock_sec=float(elapsed),
        final_coordinates=np.asarray(result.x, dtype=float),
        final_scaled_residual_inf_norm=float(np.max(np.abs(endpoint.scaled))),
        evaluation=endpoint,
    )


__all__ = [
    "ControlledTerminalBackwardEulerEvaluation",
    "ControlledTerminalImplicitStepOutcome",
    "controlled_terminal_step_pattern",
    "evaluate_controlled_terminal_backward_euler_residual",
    "solve_controlled_terminal_backward_euler_step",
]
