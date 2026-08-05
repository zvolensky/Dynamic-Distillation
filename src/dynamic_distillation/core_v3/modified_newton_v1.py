"""Deterministic modified-Newton solve with one Jacobian factorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np
from scipy.linalg import LinAlgWarning, lu_factor, lu_solve
import warnings


@dataclass(frozen=True)
class ModifiedNewtonSettings:
    residual_tolerance: float = 1.0e-8
    max_iterations: int = 12
    line_search_fractions: tuple[float, ...] = (1.0, 0.5, 0.25, 0.125)
    armijo_fraction: float = 1.0e-4
    condition_limit: float = 1.0e8


@dataclass(frozen=True)
class ModifiedNewtonOutcome:
    success: bool
    message: str
    iterations: int
    residual_evaluations: int
    jacobian_evaluations: int
    linear_solves: int
    accepted_steps: int
    rejected_line_search_steps: int
    rejected_bound_steps: int
    initial_coordinates: np.ndarray
    final_coordinates: np.ndarray
    initial_residual_inf_norm: float
    final_residual_inf_norm: float
    jacobian: np.ndarray | None
    jacobian_rank: int | None
    jacobian_condition: float | None
    final_evaluation: Any


def _residual(evaluation: Any) -> np.ndarray:
    values = np.asarray(evaluation.scaled, dtype=float).reshape((-1,))
    if values.size == 0 or np.any(~np.isfinite(values)):
        raise ValueError("modified-Newton residual must be finite and nonempty")
    return values


def _validate_settings(settings: ModifiedNewtonSettings) -> None:
    fractions = np.asarray(settings.line_search_fractions, dtype=float)
    if (
        not np.isfinite(settings.residual_tolerance)
        or settings.residual_tolerance <= 0.0
        or settings.max_iterations <= 0
        or fractions.size == 0
        or np.any(~np.isfinite(fractions))
        or np.any((fractions <= 0.0) | (fractions > 1.0))
        or np.any(np.diff(fractions) >= 0.0)
        or not 0.0 < settings.armijo_fraction < 1.0
        or not np.isfinite(settings.condition_limit)
        or settings.condition_limit <= 1.0
    ):
        raise ValueError("modified-Newton settings are invalid")


def solve_modified_newton(
    objective: Callable[[np.ndarray, str], Any],
    jacobian_builder: Callable[[np.ndarray, str], np.ndarray],
    initial_coordinates: Sequence[float],
    settings: ModifiedNewtonSettings,
    *,
    lower_bounds: Sequence[float] | None = None,
    upper_bounds: Sequence[float] | None = None,
    name: str,
) -> ModifiedNewtonOutcome:
    """Solve with one frozen Jacobian and residual-only line searches."""
    _validate_settings(settings)
    initial = np.asarray(initial_coordinates, dtype=float).reshape((-1,))
    if initial.size == 0 or np.any(~np.isfinite(initial)):
        raise ValueError("modified-Newton initial coordinates are invalid")
    lower = (
        np.full(initial.shape, -np.inf)
        if lower_bounds is None
        else np.asarray(lower_bounds, dtype=float).reshape((-1,))
    )
    upper = (
        np.full(initial.shape, np.inf)
        if upper_bounds is None
        else np.asarray(upper_bounds, dtype=float).reshape((-1,))
    )
    if (
        lower.shape != initial.shape
        or upper.shape != initial.shape
        or np.any(lower >= upper)
        or np.any(initial < lower)
        or np.any(initial > upper)
    ):
        raise ValueError("modified-Newton bounds are invalid")

    point = initial.copy()
    evaluation = objective(point, f"{name}:initial")
    residual = _residual(evaluation)
    residual_evaluations = 1
    initial_norm = float(np.max(np.abs(residual)))
    if initial_norm < settings.residual_tolerance:
        return ModifiedNewtonOutcome(
            success=True,
            message="initial residual satisfies tolerance",
            iterations=0,
            residual_evaluations=residual_evaluations,
            jacobian_evaluations=0,
            linear_solves=0,
            accepted_steps=0,
            rejected_line_search_steps=0,
            rejected_bound_steps=0,
            initial_coordinates=initial,
            final_coordinates=point,
            initial_residual_inf_norm=initial_norm,
            final_residual_inf_norm=initial_norm,
            jacobian=None,
            jacobian_rank=None,
            jacobian_condition=None,
            final_evaluation=evaluation,
        )

    jacobian = np.asarray(
        jacobian_builder(point, f"{name}:frozen_jacobian"), dtype=float
    )
    if jacobian.shape != (residual.size, point.size) or jacobian.shape[0] != jacobian.shape[1]:
        raise ValueError("modified-Newton Jacobian must be square and match the residual")
    if np.any(~np.isfinite(jacobian)):
        raise ValueError("modified-Newton Jacobian must be finite")
    singular = np.linalg.svd(jacobian, compute_uv=False)
    tolerance = max(jacobian.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    if rank != point.size or condition >= settings.condition_limit:
        return ModifiedNewtonOutcome(
            success=False,
            message="frozen Jacobian failed rank or condition gate",
            iterations=0,
            residual_evaluations=residual_evaluations,
            jacobian_evaluations=1,
            linear_solves=0,
            accepted_steps=0,
            rejected_line_search_steps=0,
            rejected_bound_steps=0,
            initial_coordinates=initial,
            final_coordinates=point,
            initial_residual_inf_norm=initial_norm,
            final_residual_inf_norm=initial_norm,
            jacobian=jacobian,
            jacobian_rank=rank,
            jacobian_condition=condition,
            final_evaluation=evaluation,
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error", LinAlgWarning)
        factor = lu_factor(jacobian, check_finite=False)

    accepted_steps = 0
    rejected_line_search_steps = 0
    rejected_bound_steps = 0
    linear_solves = 0
    for iteration in range(1, settings.max_iterations + 1):
        correction = lu_solve(factor, -residual, check_finite=False)
        linear_solves += 1
        if np.any(~np.isfinite(correction)):
            break
        current_norm = float(np.max(np.abs(residual)))
        accepted = False
        for search_index, fraction in enumerate(settings.line_search_fractions):
            candidate = point + float(fraction) * correction
            if np.any(candidate < lower) or np.any(candidate > upper):
                rejected_bound_steps += 1
                continue
            trial = objective(
                candidate, f"{name}:iteration_{iteration}:line_{search_index}"
            )
            trial_residual = _residual(trial)
            residual_evaluations += 1
            trial_norm = float(np.max(np.abs(trial_residual)))
            if trial_norm <= (1.0 - settings.armijo_fraction * float(fraction)) * current_norm:
                point = candidate
                evaluation = trial
                residual = trial_residual
                accepted_steps += 1
                accepted = True
                break
            rejected_line_search_steps += 1
        if not accepted:
            return ModifiedNewtonOutcome(
                success=False,
                message="line search failed with frozen Jacobian",
                iterations=iteration,
                residual_evaluations=residual_evaluations,
                jacobian_evaluations=1,
                linear_solves=linear_solves,
                accepted_steps=accepted_steps,
                rejected_line_search_steps=rejected_line_search_steps,
                rejected_bound_steps=rejected_bound_steps,
                initial_coordinates=initial,
                final_coordinates=point,
                initial_residual_inf_norm=initial_norm,
                final_residual_inf_norm=float(np.max(np.abs(residual))),
                jacobian=jacobian,
                jacobian_rank=rank,
                jacobian_condition=condition,
                final_evaluation=evaluation,
            )
        final_norm = float(np.max(np.abs(residual)))
        if final_norm < settings.residual_tolerance:
            return ModifiedNewtonOutcome(
                success=True,
                message="modified Newton converged",
                iterations=iteration,
                residual_evaluations=residual_evaluations,
                jacobian_evaluations=1,
                linear_solves=linear_solves,
                accepted_steps=accepted_steps,
                rejected_line_search_steps=rejected_line_search_steps,
                rejected_bound_steps=rejected_bound_steps,
                initial_coordinates=initial,
                final_coordinates=point,
                initial_residual_inf_norm=initial_norm,
                final_residual_inf_norm=final_norm,
                jacobian=jacobian,
                jacobian_rank=rank,
                jacobian_condition=condition,
                final_evaluation=evaluation,
            )
    return ModifiedNewtonOutcome(
        success=False,
        message="modified Newton exhausted its frozen iteration budget",
        iterations=settings.max_iterations,
        residual_evaluations=residual_evaluations,
        jacobian_evaluations=1,
        linear_solves=linear_solves,
        accepted_steps=accepted_steps,
        rejected_line_search_steps=rejected_line_search_steps,
        rejected_bound_steps=rejected_bound_steps,
        initial_coordinates=initial,
        final_coordinates=point,
        initial_residual_inf_norm=initial_norm,
        final_residual_inf_norm=float(np.max(np.abs(residual))),
        jacobian=jacobian,
        jacobian_rank=rank,
        jacobian_condition=condition,
        final_evaluation=evaluation,
    )


__all__ = [
    "ModifiedNewtonOutcome",
    "ModifiedNewtonSettings",
    "solve_modified_newton",
]
