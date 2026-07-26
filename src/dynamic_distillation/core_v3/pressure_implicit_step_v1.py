"""Exact backward-Euler kernel for the Core V3 algebraic-pressure model."""

from __future__ import annotations

from dataclasses import dataclass, replace
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
    contract_sparsity_pattern,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    DynamicImplicitEvaluation,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    ImplicitStepSettings,
    governing_storage_vector,
)
from dynamic_distillation.core_v3.pressure_implicit_dae_contract_v1 import (
    PressureImplicitDAEContract,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLayerEvaluation,
    PressureNumericalSpec,
    evaluate_pressure_layer_residual,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


@dataclass(frozen=True)
class PressureBackwardEulerEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    previous_inventory_lbmol: np.ndarray
    endpoint_inventory_lbmol: np.ndarray
    component_rate_lbmolph: np.ndarray
    previous_internal_energy_BTU: np.ndarray
    endpoint_internal_energy_BTU: np.ndarray
    energy_storage_rate_BTUph: np.ndarray
    pressure_evaluation: PressureLayerEvaluation


@dataclass(frozen=True)
class PressureImplicitStepOutcome:
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None
    wall_clock_sec: float
    final_coordinates: np.ndarray
    final_scaled_residual_inf_norm: float
    evaluation: PressureBackwardEulerEvaluation


@dataclass(frozen=True)
class PressureImplicitJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    color_count: int


def _energy_indices(contract: PressureImplicitDAEContract) -> np.ndarray:
    return np.asarray(
        [index for index, row in enumerate(contract.rows) if row.block == "energy_balance"],
        dtype=int,
    )


def evaluate_pressure_backward_euler_residual(
    contract: PressureImplicitDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    previous_inventory_lbmol: Sequence[Sequence[float]],
    previous_internal_energy_BTU: Sequence[float],
    rate_scales_lbmolph: Sequence[Sequence[float]],
    solve_coordinates: Sequence[float],
    step_seconds: float,
    fixed_steady_scales: Sequence[float],
    numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> PressureBackwardEulerEvaluation:
    if not np.isfinite(step_seconds) or step_seconds <= 0.0:
        raise ValueError("pressure backward-Euler step must be positive")
    previous = np.asarray(previous_inventory_lbmol, dtype=float)
    rate_scales = np.asarray(rate_scales_lbmolph, dtype=float)
    expected = (len(VOLUME_IDS), len(spec.component_names))
    if previous.shape != expected or rate_scales.shape != expected:
        raise ValueError("pressure-step inventory or rate-scale shape is invalid")
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (42,) or np.any(~np.isfinite(point)):
        raise ValueError("pressure-step solve coordinates are invalid")
    rate_count = len(contract.derivative_variables)
    base_count = len(contract.pressure_contract.base_contract.algebraic_variables)
    nominal_rate = point[:rate_count].reshape(expected) * rate_scales
    step_hours = float(step_seconds) / 3600.0
    endpoint_inventory = previous * np.exp(step_hours * nominal_rate / previous)
    if np.any(~np.isfinite(endpoint_inventory)) or np.any(endpoint_inventory <= 0.0):
        raise ValueError("pressure-step endpoint inventory is not physical")
    physical_rate = (endpoint_inventory - previous) / step_hours
    actual_rate_coordinates = physical_rate / rate_scales
    pressure = evaluate_pressure_layer_residual(
        contract.pressure_contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=endpoint_inventory,
        rate_coordinates=actual_rate_coordinates.reshape((-1,)),
        base_algebraic_coordinates=point[rate_count : rate_count + base_count],
        pressure_coordinates=point[rate_count + base_count :],
        storage_gradient_BTU_lbmol=np.zeros(expected, dtype=float),
        fixed_steady_scales=fixed_steady_scales,
        numerical=numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    live_spec = replace(spec, pressure_psia=pressure.pressure_psia)
    endpoint_storage = governing_storage_vector(
        live_spec, pressure.base_evaluation, endpoint_inventory
    )
    previous_storage = np.asarray(previous_internal_energy_BTU, dtype=float)
    if previous_storage.shape != (len(VOLUME_IDS),):
        raise ValueError("pressure-step previous storage shape is invalid")
    storage_rate = (endpoint_storage - previous_storage) / step_hours
    raw = np.asarray(pressure.raw, dtype=float).copy()
    indices = _energy_indices(contract)
    if indices.size != len(VOLUME_IDS):
        raise RuntimeError("pressure-step contract has invalid energy rows")
    raw[indices] += storage_rate
    return PressureBackwardEulerEvaluation(
        raw=raw,
        scaled=raw / pressure.scales,
        row_names=pressure.row_names,
        previous_inventory_lbmol=previous.copy(),
        endpoint_inventory_lbmol=endpoint_inventory,
        component_rate_lbmolph=physical_rate,
        previous_internal_energy_BTU=previous_storage.copy(),
        endpoint_internal_energy_BTU=endpoint_storage,
        energy_storage_rate_BTUph=storage_rate,
        pressure_evaluation=pressure,
    )


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return rank, condition, singular


def pressure_step_pattern(contract: PressureImplicitDAEContract) -> np.ndarray:
    pattern, _names = contract_sparsity_pattern(
        contract.pressure_contract, include_state_rate_dependencies=True
    )
    return pattern


def solve_pressure_backward_euler_step(
    contract: PressureImplicitDAEContract,
    objective: Callable[[np.ndarray, str], PressureBackwardEulerEvaluation],
    initial_coordinates: Sequence[float],
    settings: ImplicitStepSettings,
) -> PressureImplicitStepOutcome:
    initial = np.asarray(initial_coordinates, dtype=float).reshape((-1,))
    pattern = pressure_step_pattern(contract)

    def residual(point: np.ndarray) -> np.ndarray:
        return objective(point, "dd105:solve:residual").scaled

    def jacobian(point: np.ndarray) -> np.ndarray:
        matrix, _groups = colored_central_difference_jacobian(
            lambda candidate, state_id: objective(candidate, state_id).scaled,
            point,
            pattern=pattern,
            step=settings.jacobian_step,
            state_id="dd105:solve:jacobian",
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
    endpoint = objective(result.x, "dd105:solve:endpoint")
    return PressureImplicitStepOutcome(
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


def audit_pressure_step_jacobian(
    contract: PressureImplicitDAEContract,
    objective: Callable[[np.ndarray, str], PressureBackwardEulerEvaluation],
    point: Sequence[float],
    *,
    step: float,
    coupling_tolerance: float,
) -> PressureImplicitJacobianAudit:
    pattern = pressure_step_pattern(contract)
    matrix, groups = colored_central_difference_jacobian(
        lambda candidate, state_id: objective(candidate, state_id).scaled,
        point,
        pattern=pattern,
        step=step,
        state_id=f"dd105:endpoint_jacobian:{step:g}",
    )
    rank, condition, singular = _rank_condition(matrix)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    names = tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )
    return PressureImplicitJacobianAudit(
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
            names[index] for index in np.flatnonzero(column_norm <= coupling_tolerance)
        ),
        color_count=len(groups),
    )


__all__ = [
    "PressureBackwardEulerEvaluation",
    "PressureImplicitJacobianAudit",
    "PressureImplicitStepOutcome",
    "audit_pressure_step_jacobian",
    "evaluate_pressure_backward_euler_residual",
    "pressure_step_pattern",
    "solve_pressure_backward_euler_step",
]
