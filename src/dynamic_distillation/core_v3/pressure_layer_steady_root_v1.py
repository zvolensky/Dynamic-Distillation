"""Bounded steady-root solver for the Core V3 algebraic pressure layer."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
    greedy_column_groups,
)
from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    PressureLayerContract,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLayerEvaluation,
    PressureNumericalSpec,
    evaluate_pressure_layer_residual,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


@dataclass(frozen=True)
class PressureRootSettings:
    method: str = "trf"
    ftol: float = 1.0e-11
    xtol: float = 1.0e-11
    gtol: float = 1.0e-11
    max_nfev: int = 200
    x_scale: float = 1.0
    jacobian_step: float = 1.0e-5


@dataclass(frozen=True)
class AlgebraicJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]


@dataclass(frozen=True)
class PressureRootOutcome:
    start_name: str
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None
    wall_clock_sec: float
    initial_coordinates: np.ndarray
    final_coordinates: np.ndarray
    final_scaled_residual_inf_norm: float
    final_evaluation: PressureLayerEvaluation
    active_lower_bounds: tuple[str, ...]
    active_upper_bounds: tuple[str, ...]
    color_groups: tuple[tuple[int, ...], ...]


def algebraic_sparsity_pattern(
    contract: PressureLayerContract,
) -> tuple[np.ndarray, tuple[str, ...]]:
    all_variables = (*contract.derivative_variables, *contract.algebraic_variables)
    all_names = tuple(variable.name for variable in all_variables)
    index = {name: column for column, name in enumerate(all_names)}
    pattern = np.zeros((len(contract.rows), len(all_names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            pattern[row_index, index[dependency]] = True
    derivative_count = len(contract.derivative_variables)
    return pattern[:, derivative_count:], all_names[derivative_count:]


def _evaluate_algebraic_point(
    contract: PressureLayerContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> PressureLayerEvaluation:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    base_count = len(contract.base_contract.algebraic_variables)
    if point.shape != (len(contract.algebraic_variables),):
        raise ValueError("pressure-root algebraic coordinate shape is invalid")
    return evaluate_pressure_layer_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory_lbmol,
        rate_coordinates=np.zeros(len(contract.derivative_variables)),
        base_algebraic_coordinates=point[:base_count],
        pressure_coordinates=point[base_count:],
        storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
        fixed_steady_scales=fixed_steady_scales,
        numerical=numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )


def solve_pressure_layer_root(
    contract: PressureLayerContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    start_name: str,
    initial_coordinates: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    inventory_lbmol: Sequence[Sequence[float]],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    numerical: PressureNumericalSpec,
    settings: PressureRootSettings = PressureRootSettings(),
    active_bound_tolerance: float = 1.0e-6,
) -> PressureRootOutcome:
    initial = np.asarray(initial_coordinates, dtype=float).reshape((-1,))
    lower = np.asarray(lower_bounds, dtype=float).reshape((-1,))
    upper = np.asarray(upper_bounds, dtype=float).reshape((-1,))
    if (
        initial.shape != lower.shape
        or initial.shape != upper.shape
        or initial.size != len(contract.algebraic_variables)
        or np.any(~np.isfinite(initial))
        or np.any(lower >= upper)
        or np.any(initial <= lower)
        or np.any(initial >= upper)
    ):
        raise ValueError("pressure-root start or bounds are invalid")
    pattern, _names = algebraic_sparsity_pattern(contract)

    def objective(point: np.ndarray, state_id: str) -> np.ndarray:
        return _evaluate_algebraic_point(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            coordinates=point,
            storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
            fixed_steady_scales=fixed_steady_scales,
            numerical=numerical,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled

    def residual(point: np.ndarray) -> np.ndarray:
        return objective(point, f"dd103:{start_name}:residual")

    color_groups = greedy_column_groups(pattern)

    def jacobian(point: np.ndarray) -> np.ndarray:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=settings.jacobian_step,
            state_id=f"dd103:{start_name}:jacobian",
        )
        if groups != color_groups:
            raise RuntimeError("pressure-root coloring changed during solve")
        return matrix

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
    endpoint = _evaluate_algebraic_point(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory_lbmol,
        coordinates=result.x,
        storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
        fixed_steady_scales=fixed_steady_scales,
        numerical=numerical,
        state_id=f"dd103:{start_name}:endpoint",
        evaluation_kind="residual",
    )
    names = tuple(variable.name for variable in contract.algebraic_variables)
    lower_distance = np.asarray(result.x) - lower
    upper_distance = upper - np.asarray(result.x)
    return PressureRootOutcome(
        start_name=str(start_name),
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
        njev=None if result.njev is None else int(result.njev),
        wall_clock_sec=float(elapsed),
        initial_coordinates=initial.copy(),
        final_coordinates=np.asarray(result.x, dtype=float),
        final_scaled_residual_inf_norm=float(np.max(np.abs(endpoint.scaled))),
        final_evaluation=endpoint,
        active_lower_bounds=tuple(
            names[index]
            for index in np.flatnonzero(lower_distance <= active_bound_tolerance)
        ),
        active_upper_bounds=tuple(
            names[index]
            for index in np.flatnonzero(upper_distance <= active_bound_tolerance)
        ),
        color_groups=color_groups,
    )


def _rank_condition_singular(
    matrix: np.ndarray,
) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def audit_algebraic_jacobian(
    contract: PressureLayerContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    numerical: PressureNumericalSpec,
    step: float,
    coupling_tolerance: float,
    state_id: str,
) -> AlgebraicJacobianAudit:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    pattern, names = algebraic_sparsity_pattern(contract)
    matrix = np.empty(pattern.shape, dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = _evaluate_algebraic_point(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            coordinates=point + delta,
            storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
            fixed_steady_scales=fixed_steady_scales,
            numerical=numerical,
            state_id=f"{state_id}:{column}:plus",
            evaluation_kind="jacobian",
        ).scaled
        minus = _evaluate_algebraic_point(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            coordinates=point - delta,
            storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
            fixed_steady_scales=fixed_steady_scales,
            numerical=numerical,
            state_id=f"{state_id}:{column}:minus",
            evaluation_kind="jacobian",
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    unexpected = tuple(
        f"{contract.rows[row].name} <- {names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    rank, condition, singular = _rank_condition_singular(matrix)
    return AlgebraicJacobianAudit(
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
    )


__all__ = [
    "AlgebraicJacobianAudit",
    "PressureRootOutcome",
    "PressureRootSettings",
    "algebraic_sparsity_pattern",
    "audit_algebraic_jacobian",
    "solve_pressure_layer_root",
]
