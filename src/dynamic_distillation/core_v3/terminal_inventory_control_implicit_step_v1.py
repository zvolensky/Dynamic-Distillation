"""Backward-Euler kernel for the Core V3 terminal-control DAE."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Sequence

import numpy as np
from scipy.optimize import least_squares

from .colored_jacobian_v1 import colored_central_difference_jacobian
from .implicit_step_v1 import (
    ImplicitStepSettings,
    component_rate_scales,
    governing_storage_vector,
)
from .provider_call_audit_v1 import ProviderCallAudit
from .provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from .terminal_inventory_control_contract_v1 import (
    TerminalInventoryControlContract,
)
from .terminal_inventory_control_numerical_v1 import (
    TerminalInventoryControlEvaluation,
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
    terminal_inventory_control_variable_names,
)


@dataclass(frozen=True)
class TerminalInventoryControlBackwardEulerEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    solve_coordinates: np.ndarray
    previous_inventory_lbmol: np.ndarray
    endpoint_inventory_lbmol: np.ndarray
    component_rate_lbmolph: np.ndarray
    rate_coordinates: np.ndarray
    algebraic_coordinates: np.ndarray
    previous_internal_energy_BTU: np.ndarray
    endpoint_internal_energy_BTU: np.ndarray
    energy_storage_rate_BTUph: np.ndarray
    previous_controller_memory: np.ndarray
    endpoint_controller_memory: np.ndarray
    controller_rate_per_sec: np.ndarray
    level_fraction: np.ndarray
    level_error: np.ndarray
    product_log_ratio: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    control_evaluation: TerminalInventoryControlEvaluation
    maximum_equilibrium_residual: float


@dataclass(frozen=True)
class TerminalInventoryControlStepOutcome:
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None
    cost: float
    optimality: float
    wall_clock_sec: float
    initial_coordinates: np.ndarray
    final_coordinates: np.ndarray
    final_residual: np.ndarray
    final_jacobian: np.ndarray
    evaluation: TerminalInventoryControlBackwardEulerEvaluation


def _state_to_rate_name(name: str) -> str | None:
    if name.startswith("N[") or name.startswith("I_level["):
        return f"d{name}/dt"
    return None


def terminal_inventory_control_step_pattern(
    contract: TerminalInventoryControlContract,
) -> np.ndarray:
    names = terminal_inventory_control_variable_names(contract)
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


def _coordinate_slices(
    contract: TerminalInventoryControlContract,
) -> tuple[slice, slice, slice, slice]:
    base_rate_count = len(contract.base.derivative_variables)
    controller_rate_stop = base_rate_count + 2
    base_algebraic_stop = controller_rate_stop + len(contract.base.algebraic_variables)
    return (
        slice(0, base_rate_count),
        slice(base_rate_count, controller_rate_stop),
        slice(controller_rate_stop, base_algebraic_stop),
        slice(base_algebraic_stop, base_algebraic_stop + 2),
    )


def _maximum_equilibrium_residual(
    contract: TerminalInventoryControlContract,
    evaluation: TerminalInventoryControlEvaluation,
) -> float:
    indices = [
        index
        for index, row in enumerate(contract.base.rows)
        if row.block in {"full_phase_equilibrium", "condenser_bubble_fugacity"}
    ]
    if not indices:
        raise RuntimeError("controlled dynamic contract has no equilibrium rows")
    return float(np.max(np.abs(evaluation.base.raw[indices])))


def evaluate_terminal_inventory_control_backward_euler_residual(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    previous_inventory_lbmol: Sequence[Sequence[float]],
    previous_internal_energy_BTU: Sequence[float],
    previous_controller_memory: Sequence[float],
    level_setpoints: TerminalLevelSetpoints,
    rate_scales_lbmolph: Sequence[Sequence[float]],
    solve_coordinates: Sequence[float],
    step_seconds: float,
    fixed_steady_scales: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> TerminalInventoryControlBackwardEulerEvaluation:
    if not np.isfinite(step_seconds) or step_seconds <= 0.0:
        raise ValueError("controlled backward-Euler step must be positive")
    previous = np.asarray(previous_inventory_lbmol, dtype=float)
    scales = np.asarray(rate_scales_lbmolph, dtype=float)
    expected = (len(spec.topology.volume_ids), len(spec.component_names))
    if previous.shape != expected or scales.shape != expected:
        raise ValueError("controlled inventory or rate-scale shape is invalid")
    if np.any(previous <= 0.0) or np.any(scales <= 0.0):
        raise ValueError("controlled inventory and rate scales must be positive")
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("controlled implicit coordinates are invalid")
    rate_slice, controller_slice, algebraic_slice, product_slice = _coordinate_slices(
        contract
    )
    nominal_rate = point[rate_slice].reshape(expected) * scales
    step_hours = float(step_seconds) / 3600.0
    exponent = step_hours * nominal_rate / previous
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        endpoint_inventory = previous * np.exp(exponent)
    if np.any(~np.isfinite(endpoint_inventory)) or np.any(endpoint_inventory <= 0.0):
        raise ValueError("controlled endpoint inventory is not physical")
    physical_rate = (endpoint_inventory - previous) / step_hours
    actual_rate_coordinates = physical_rate / scales
    previous_memory = np.asarray(previous_controller_memory, dtype=float).reshape((-1,))
    if previous_memory.shape != (2,) or np.any(~np.isfinite(previous_memory)):
        raise ValueError("previous terminal controller memory is invalid")
    controller_rates = point[controller_slice]
    endpoint_memory = previous_memory + float(step_seconds) * controller_rates
    effective = point.copy()
    effective[rate_slice] = actual_rate_coordinates.reshape((-1,))
    control = evaluate_terminal_inventory_control_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=endpoint_inventory,
        controller_memory=endpoint_memory,
        level_setpoints=level_setpoints,
        solve_coordinates=effective,
        storage_gradient_BTU_lbmol=np.zeros(expected, dtype=float),
        fixed_steady_scales=fixed_steady_scales,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    endpoint_storage = governing_storage_vector(spec, control.base, endpoint_inventory)
    previous_storage = np.asarray(previous_internal_energy_BTU, dtype=float)
    if previous_storage.shape != (len(spec.topology.volume_ids),):
        raise ValueError("previous controlled storage vector has invalid shape")
    storage_rate = (endpoint_storage - previous_storage) / step_hours
    raw = np.asarray(control.raw, dtype=float).copy()
    energy_indices = np.asarray(
        [
            index
            for index, row in enumerate(contract.base.rows)
            if row.block == "energy_balance"
        ],
        dtype=int,
    )
    if energy_indices.size != len(spec.topology.volume_ids):
        raise RuntimeError("controlled contract needs one energy row per volume")
    raw[energy_indices] += storage_rate
    residual_scales = np.concatenate(
        (np.asarray(control.base.scales, dtype=float), np.ones(4, dtype=float))
    )
    return TerminalInventoryControlBackwardEulerEvaluation(
        raw=raw,
        scaled=raw / residual_scales,
        row_names=control.row_names,
        variable_names=control.variable_names,
        solve_coordinates=effective,
        previous_inventory_lbmol=previous.copy(),
        endpoint_inventory_lbmol=endpoint_inventory,
        component_rate_lbmolph=physical_rate,
        rate_coordinates=actual_rate_coordinates,
        algebraic_coordinates=effective[algebraic_slice].copy(),
        previous_internal_energy_BTU=previous_storage.copy(),
        endpoint_internal_energy_BTU=endpoint_storage,
        energy_storage_rate_BTUph=storage_rate,
        previous_controller_memory=previous_memory.copy(),
        endpoint_controller_memory=endpoint_memory,
        controller_rate_per_sec=controller_rates.copy(),
        level_fraction=control.level_fraction.copy(),
        level_error=control.level_error.copy(),
        product_log_ratio=effective[product_slice].copy(),
        distillate_lbmolph=control.distillate_lbmolph,
        bottoms_lbmolph=control.bottoms_lbmolph,
        control_evaluation=control,
        maximum_equilibrium_residual=_maximum_equilibrium_residual(contract, control),
    )


def solve_terminal_inventory_control_backward_euler_step(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    previous_inventory_lbmol: Sequence[Sequence[float]],
    previous_controller_memory: Sequence[float],
    level_setpoints: TerminalLevelSetpoints,
    initial_solve_coordinates: Sequence[float],
    fixed_steady_scales: Sequence[float],
    step_seconds: float,
    settings: ImplicitStepSettings,
    name: str,
) -> TerminalInventoryControlStepOutcome:
    previous = np.asarray(previous_inventory_lbmol, dtype=float)
    initial = np.asarray(initial_solve_coordinates, dtype=float).reshape((-1,))
    baseline = evaluate_terminal_inventory_control_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=previous,
        controller_memory=previous_controller_memory,
        level_setpoints=level_setpoints,
        solve_coordinates=initial,
        storage_gradient_BTU_lbmol=np.zeros_like(previous),
        fixed_steady_scales=fixed_steady_scales,
        state_id=f"{name}:scale_basis",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(contract.base, baseline.base)
    previous_storage = governing_storage_vector(spec, baseline.base, previous)

    def objective(point: np.ndarray, state_id: str):
        return evaluate_terminal_inventory_control_backward_euler_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=previous,
            previous_internal_energy_BTU=previous_storage,
            previous_controller_memory=previous_controller_memory,
            level_setpoints=level_setpoints,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=point,
            step_seconds=step_seconds,
            fixed_steady_scales=fixed_steady_scales,
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        )

    pattern = terminal_inventory_control_step_pattern(contract)

    def residual(point: np.ndarray) -> np.ndarray:
        return objective(point, f"{name}:residual").scaled

    def jacobian(point: np.ndarray) -> np.ndarray:
        matrix, _groups = colored_central_difference_jacobian(
            lambda candidate, state_id: objective(candidate, state_id).scaled,
            point,
            pattern=pattern,
            step=settings.jacobian_step,
            state_id=f"{name}:jacobian",
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
    endpoint = objective(result.x, f"{name}:endpoint")
    return TerminalInventoryControlStepOutcome(
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
        njev=None if result.njev is None else int(result.njev),
        cost=float(result.cost),
        optimality=float(result.optimality),
        wall_clock_sec=float(elapsed),
        initial_coordinates=initial.copy(),
        final_coordinates=np.asarray(result.x, dtype=float).copy(),
        final_residual=np.asarray(endpoint.scaled, dtype=float).copy(),
        final_jacobian=np.asarray(result.jac, dtype=float).copy(),
        evaluation=endpoint,
    )


__all__ = [
    "TerminalInventoryControlBackwardEulerEvaluation",
    "TerminalInventoryControlStepOutcome",
    "evaluate_terminal_inventory_control_backward_euler_residual",
    "solve_terminal_inventory_control_backward_euler_step",
    "terminal_inventory_control_step_pattern",
]
