"""Backward-Euler kernel for the conserved-N/U algebraic-pressure DAE."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    ConservedNUPressureDAEContract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_numerical_v1 import (
    ConservedNUPressureEvaluation,
    nu_pressure_variable_names,
)
from dynamic_distillation.core_v3.implicit_step_v1 import ImplicitStepSettings
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_numerical_v1 import (
    evaluate_conserved_nu_pressure_residual,
)


@dataclass(frozen=True)
class ConservedNUBackwardEulerEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    previous_inventory_lbmol: np.ndarray
    endpoint_inventory_lbmol: np.ndarray
    component_rate_lbmolph: np.ndarray
    previous_top_internal_energy_BTU: float
    endpoint_top_internal_energy_BTU: float
    previous_lower_internal_energy_BTU: np.ndarray
    endpoint_lower_internal_energy_BTU: np.ndarray
    internal_energy_rate_BTUph: np.ndarray
    solve_coordinates: np.ndarray
    dae_evaluation: ConservedNUPressureEvaluation


@dataclass(frozen=True)
class ConservedNUImplicitStepOutcome:
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None
    wall_clock_sec: float
    final_coordinates: np.ndarray
    final_scaled_residual_inf_norm: float
    evaluation: ConservedNUBackwardEulerEvaluation


@dataclass(frozen=True)
class ConservedNUStepJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]
    color_count: int


def _state_to_rate_name(name: str) -> str | None:
    if name.startswith("N["):
        return f"d{name}/dt"
    if name.startswith("U["):
        return f"d{name}/dt"
    return None


def conserved_nu_step_pattern(contract: ConservedNUPressureDAEContract) -> np.ndarray:
    names = nu_pressure_variable_names(contract)
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


def _energy_row_index(
    contract: ConservedNUPressureDAEContract, volume: str
) -> int:
    return next(
        index
        for index, row in enumerate(contract.rows)
        if row.block == "energy_balance" and row.owner == volume
    )


def evaluate_conserved_nu_backward_euler_residual(
    contract: ConservedNUPressureDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    previous_inventory_lbmol: Sequence[Sequence[float]],
    previous_top_internal_energy_BTU: float,
    previous_lower_internal_energy_BTU: Sequence[float],
    component_rate_scale_lbmolph: float,
    energy_rate_scales_BTUph: Sequence[float],
    solve_coordinates: Sequence[float],
    step_seconds: float,
    fixed_steady_scales: Sequence[float],
    storage_scales_BTU: Sequence[float],
    numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> ConservedNUBackwardEulerEvaluation:
    if not np.isfinite(step_seconds) or step_seconds <= 0.0:
        raise ValueError("conserved-N/U backward-Euler step must be positive")
    if not np.isfinite(component_rate_scale_lbmolph) or component_rate_scale_lbmolph <= 0.0:
        raise ValueError("component-rate scale must be positive")
    previous_inventory = np.asarray(previous_inventory_lbmol, dtype=float)
    expected_inventory = (len(VOLUME_IDS), len(spec.component_names))
    if previous_inventory.shape != expected_inventory or np.any(previous_inventory <= 0.0):
        raise ValueError("previous component inventory is invalid")
    previous_lower_u = np.asarray(previous_lower_internal_energy_BTU, dtype=float)
    energy_scales = np.asarray(energy_rate_scales_BTUph, dtype=float)
    lower_count = len(VOLUME_IDS) - 1
    if (
        previous_lower_u.shape != (lower_count,)
        or energy_scales.shape != (lower_count,)
        or np.any(~np.isfinite(previous_lower_u))
        or np.any(energy_scales <= 0.0)
        or not np.isfinite(previous_top_internal_energy_BTU)
    ):
        raise ValueError("previous energy state or scale is invalid")
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("conserved-N/U step coordinates are invalid")

    component_count = previous_inventory.size
    energy_start = component_count
    energy_stop = energy_start + lower_count
    step_hours = float(step_seconds) / 3600.0
    nominal_component_rate = (
        point[:component_count].reshape(expected_inventory)
        * float(component_rate_scale_lbmolph)
    )
    exponent = step_hours * nominal_component_rate / previous_inventory
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        endpoint_inventory = previous_inventory * np.exp(exponent)
    if np.any(~np.isfinite(endpoint_inventory)) or np.any(endpoint_inventory <= 0.0):
        raise ValueError("endpoint component inventory is not physical")
    component_rate = (endpoint_inventory - previous_inventory) / step_hours
    actual_component_coordinates = (
        component_rate.reshape((-1,)) / float(component_rate_scale_lbmolph)
    )
    lower_energy_coordinates = point[energy_start:energy_stop]
    lower_energy_rate = lower_energy_coordinates * energy_scales
    endpoint_lower_u = previous_lower_u + step_hours * lower_energy_rate
    evaluation_coordinates = point.copy()
    evaluation_coordinates[:component_count] = actual_component_coordinates
    dae = evaluate_conserved_nu_pressure_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=endpoint_inventory,
        lower_internal_energy_BTU=endpoint_lower_u,
        top_storage_gradient_BTU_lbmol=np.zeros(len(spec.component_names)),
        energy_rate_scales_BTUph=energy_scales,
        solve_coordinates=evaluation_coordinates,
        fixed_steady_scales=fixed_steady_scales,
        storage_scales_BTU=storage_scales_BTU,
        numerical=numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    endpoint_top_u = float(dae.live_internal_energy_BTU[0])
    top_energy_rate = (
        endpoint_top_u - float(previous_top_internal_energy_BTU)
    ) / step_hours
    raw = np.asarray(dae.raw, dtype=float).copy()
    raw[_energy_row_index(contract, VOLUME_IDS[0])] += top_energy_rate
    return ConservedNUBackwardEulerEvaluation(
        raw=raw,
        scaled=raw / dae.scales,
        row_names=dae.row_names,
        previous_inventory_lbmol=previous_inventory.copy(),
        endpoint_inventory_lbmol=endpoint_inventory,
        component_rate_lbmolph=component_rate,
        previous_top_internal_energy_BTU=float(previous_top_internal_energy_BTU),
        endpoint_top_internal_energy_BTU=endpoint_top_u,
        previous_lower_internal_energy_BTU=previous_lower_u.copy(),
        endpoint_lower_internal_energy_BTU=endpoint_lower_u,
        internal_energy_rate_BTUph=np.concatenate(
            (np.asarray((top_energy_rate,)), lower_energy_rate)
        ),
        solve_coordinates=evaluation_coordinates,
        dae_evaluation=dae,
    )


def solve_conserved_nu_backward_euler_step(
    contract: ConservedNUPressureDAEContract,
    objective: Callable[[np.ndarray, str], ConservedNUBackwardEulerEvaluation],
    initial_coordinates: Sequence[float],
    settings: ImplicitStepSettings,
    *,
    name: str,
) -> ConservedNUImplicitStepOutcome:
    initial = np.asarray(initial_coordinates, dtype=float).reshape((-1,))
    pattern = conserved_nu_step_pattern(contract)

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

    started = time.perf_counter()
    result = least_squares(
        residual,
        initial,
        jac=jacobian,
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=settings.x_scale,
    )
    elapsed = time.perf_counter() - started
    endpoint = objective(result.x, f"{name}:solve:endpoint")
    return ConservedNUImplicitStepOutcome(
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


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def audit_conserved_nu_step_jacobian(
    contract: ConservedNUPressureDAEContract,
    objective: Callable[[np.ndarray, str], ConservedNUBackwardEulerEvaluation],
    point: Sequence[float],
    *,
    step: float,
    coupling_tolerance: float,
) -> ConservedNUStepJacobianAudit:
    pattern = conserved_nu_step_pattern(contract)
    matrix, groups = colored_central_difference_jacobian(
        lambda candidate, state_id: objective(candidate, state_id).scaled,
        point,
        pattern=pattern,
        step=step,
        state_id=f"dd115:endpoint_jacobian:{step:g}",
    )
    rank, condition, singular = _rank_condition(matrix)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    names = nu_pressure_variable_names(contract)
    unexpected = tuple(
        f"{contract.rows[row].name} <- {names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    return ConservedNUStepJacobianAudit(
        step=float(step),
        matrix=matrix,
        rank=rank,
        condition=condition,
        singular_values=singular,
        zero_rows=tuple(
            contract.rows[index].name
            for index in np.flatnonzero(row_norm <= coupling_tolerance)
        ),
        zero_columns=tuple(
            names[index]
            for index in np.flatnonzero(column_norm <= coupling_tolerance)
        ),
        unexpected_couplings=unexpected,
        color_count=len(groups),
    )


__all__ = [
    "ConservedNUBackwardEulerEvaluation",
    "ConservedNUImplicitStepOutcome",
    "ConservedNUStepJacobianAudit",
    "audit_conserved_nu_step_jacobian",
    "conserved_nu_step_pattern",
    "evaluate_conserved_nu_backward_euler_residual",
    "solve_conserved_nu_backward_euler_step",
]
