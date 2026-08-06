"""Modified Newton with immutable in-process globalization evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence
import warnings

import numpy as np
from scipy.linalg import LinAlgWarning, lu_factor, lu_solve

from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings


def _immutable(values: Any) -> np.ndarray:
    result = np.asarray(values, dtype=float).copy()
    result.setflags(write=False)
    return result


def _residual(evaluation: Any) -> np.ndarray:
    values = np.asarray(evaluation.scaled, dtype=float).reshape((-1,))
    if values.size == 0 or np.any(~np.isfinite(values)):
        raise ValueError("captured modified-Newton residual must be finite and nonempty")
    return _immutable(values)


def _evaluation_coordinates(evaluation: Any, shape: tuple[int, ...]) -> np.ndarray | None:
    values = getattr(evaluation, "solve_coordinates", None)
    if values is None:
        values = getattr(evaluation, "coordinates", None)
    if values is None:
        return None
    point = np.asarray(values, dtype=float).reshape((-1,))
    if point.shape != shape or np.any(~np.isfinite(point)):
        raise ValueError("captured evaluation coordinates are invalid")
    return _immutable(point)


@dataclass(frozen=True)
class CapturedLineSearchTrial:
    iteration: int
    search_index: int
    fraction: float
    state_id: str | None
    coordinates: np.ndarray
    within_bounds: bool
    residual: np.ndarray | None
    residual_inf_norm: float | None
    armijo_limit: float
    armijo_accepted: bool
    evaluation_coordinates: np.ndarray | None


@dataclass(frozen=True)
class CapturedNewtonIteration:
    iteration: int
    coordinates_before: np.ndarray
    residual_before: np.ndarray
    residual_inf_norm_before: float
    correction: np.ndarray
    trials: tuple[CapturedLineSearchTrial, ...]


@dataclass(frozen=True)
class CapturedModifiedNewtonOutcome:
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
    initial_residual: np.ndarray
    frozen_jacobian: np.ndarray | None
    jacobian_rank: int | None
    jacobian_condition: float | None
    iteration_captures: tuple[CapturedNewtonIteration, ...]
    final_coordinates: np.ndarray
    final_residual: np.ndarray
    final_evaluation_residual_at_return: np.ndarray
    final_evaluation_coordinates_at_return: np.ndarray | None
    final_residual_vs_evaluation_max_abs: float
    final_coordinates_vs_evaluation_max_abs: float | None
    final_evaluation: Any

    @property
    def initial_residual_inf_norm(self) -> float:
        return float(np.max(np.abs(self.initial_residual)))

    @property
    def final_residual_inf_norm(self) -> float:
        return float(np.max(np.abs(self.final_residual)))


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
        raise ValueError("captured modified-Newton settings are invalid")


def _outcome(
    *,
    success: bool,
    message: str,
    iterations: int,
    residual_evaluations: int,
    jacobian_evaluations: int,
    linear_solves: int,
    accepted_steps: int,
    rejected_line_search_steps: int,
    rejected_bound_steps: int,
    initial_coordinates: np.ndarray,
    initial_residual: np.ndarray,
    frozen_jacobian: np.ndarray | None,
    jacobian_rank: int | None,
    jacobian_condition: float | None,
    iteration_captures: Sequence[CapturedNewtonIteration],
    final_coordinates: np.ndarray,
    final_residual: np.ndarray,
    final_evaluation: Any,
) -> CapturedModifiedNewtonOutcome:
    evaluation_residual = _residual(final_evaluation)
    evaluation_coordinates = _evaluation_coordinates(
        final_evaluation, final_coordinates.shape
    )
    residual_identity = float(
        np.max(np.abs(np.asarray(final_residual) - evaluation_residual))
    )
    coordinate_identity = (
        None
        if evaluation_coordinates is None
        else float(
            np.max(
                np.abs(np.asarray(final_coordinates) - evaluation_coordinates)
            )
        )
    )
    return CapturedModifiedNewtonOutcome(
        success=bool(success),
        message=str(message),
        iterations=int(iterations),
        residual_evaluations=int(residual_evaluations),
        jacobian_evaluations=int(jacobian_evaluations),
        linear_solves=int(linear_solves),
        accepted_steps=int(accepted_steps),
        rejected_line_search_steps=int(rejected_line_search_steps),
        rejected_bound_steps=int(rejected_bound_steps),
        initial_coordinates=_immutable(initial_coordinates),
        initial_residual=_immutable(initial_residual),
        frozen_jacobian=(
            None if frozen_jacobian is None else _immutable(frozen_jacobian)
        ),
        jacobian_rank=jacobian_rank,
        jacobian_condition=jacobian_condition,
        iteration_captures=tuple(iteration_captures),
        final_coordinates=_immutable(final_coordinates),
        final_residual=_immutable(final_residual),
        final_evaluation_residual_at_return=evaluation_residual,
        final_evaluation_coordinates_at_return=evaluation_coordinates,
        final_residual_vs_evaluation_max_abs=residual_identity,
        final_coordinates_vs_evaluation_max_abs=coordinate_identity,
        final_evaluation=final_evaluation,
    )


def solve_captured_modified_newton(
    objective: Callable[[np.ndarray, str], Any],
    jacobian_builder: Callable[[np.ndarray, str], np.ndarray],
    initial_coordinates: Sequence[float],
    settings: ModifiedNewtonSettings,
    *,
    lower_bounds: Sequence[float] | None = None,
    upper_bounds: Sequence[float] | None = None,
    name: str,
) -> CapturedModifiedNewtonOutcome:
    """Solve with one frozen Jacobian while preserving every globalization trial."""
    _validate_settings(settings)
    initial = np.asarray(initial_coordinates, dtype=float).reshape((-1,)).copy()
    if initial.size == 0 or np.any(~np.isfinite(initial)):
        raise ValueError("captured modified-Newton initial coordinates are invalid")
    lower = (
        np.full(initial.shape, -np.inf)
        if lower_bounds is None
        else np.asarray(lower_bounds, dtype=float).reshape((-1,)).copy()
    )
    upper = (
        np.full(initial.shape, np.inf)
        if upper_bounds is None
        else np.asarray(upper_bounds, dtype=float).reshape((-1,)).copy()
    )
    if (
        lower.shape != initial.shape
        or upper.shape != initial.shape
        or np.any(lower >= upper)
        or np.any(initial < lower)
        or np.any(initial > upper)
    ):
        raise ValueError("captured modified-Newton bounds are invalid")

    point = initial.copy()
    evaluation = objective(point.copy(), f"{name}:initial")
    residual = _residual(evaluation)
    initial_residual = _immutable(residual)
    residual_evaluations = 1
    current_norm = float(np.max(np.abs(residual)))
    if current_norm < settings.residual_tolerance:
        return _outcome(
            success=True,
            message="initial residual satisfies tolerance",
            iterations=0,
            residual_evaluations=1,
            jacobian_evaluations=0,
            linear_solves=0,
            accepted_steps=0,
            rejected_line_search_steps=0,
            rejected_bound_steps=0,
            initial_coordinates=initial,
            initial_residual=initial_residual,
            frozen_jacobian=None,
            jacobian_rank=None,
            jacobian_condition=None,
            iteration_captures=(),
            final_coordinates=point,
            final_residual=residual,
            final_evaluation=evaluation,
        )

    jacobian = np.asarray(
        jacobian_builder(point.copy(), f"{name}:frozen_jacobian"), dtype=float
    ).copy()
    if jacobian.shape != (residual.size, point.size) or jacobian.shape[0] != jacobian.shape[1]:
        raise ValueError("captured modified-Newton Jacobian must be square")
    if np.any(~np.isfinite(jacobian)):
        raise ValueError("captured modified-Newton Jacobian must be finite")
    singular = np.linalg.svd(jacobian, compute_uv=False)
    tolerance = max(jacobian.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    if rank != point.size or condition >= settings.condition_limit:
        return _outcome(
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
            initial_residual=initial_residual,
            frozen_jacobian=jacobian,
            jacobian_rank=rank,
            jacobian_condition=condition,
            iteration_captures=(),
            final_coordinates=point,
            final_residual=residual,
            final_evaluation=evaluation,
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error", LinAlgWarning)
        factor = lu_factor(jacobian, check_finite=False)

    captures: list[CapturedNewtonIteration] = []
    accepted_steps = 0
    rejected_line_search_steps = 0
    rejected_bound_steps = 0
    linear_solves = 0
    for iteration in range(1, settings.max_iterations + 1):
        correction = lu_solve(factor, -np.asarray(residual), check_finite=False)
        linear_solves += 1
        if np.any(~np.isfinite(correction)):
            captures.append(
                CapturedNewtonIteration(
                    iteration=iteration,
                    coordinates_before=_immutable(point),
                    residual_before=_immutable(residual),
                    residual_inf_norm_before=float(np.max(np.abs(residual))),
                    correction=_immutable(correction),
                    trials=(),
                )
            )
            return _outcome(
                success=False,
                message="nonfinite frozen-Jacobian correction",
                iterations=iteration,
                residual_evaluations=residual_evaluations,
                jacobian_evaluations=1,
                linear_solves=linear_solves,
                accepted_steps=accepted_steps,
                rejected_line_search_steps=rejected_line_search_steps,
                rejected_bound_steps=rejected_bound_steps,
                initial_coordinates=initial,
                initial_residual=initial_residual,
                frozen_jacobian=jacobian,
                jacobian_rank=rank,
                jacobian_condition=condition,
                iteration_captures=captures,
                final_coordinates=point,
                final_residual=residual,
                final_evaluation=evaluation,
            )
        norm_before = float(np.max(np.abs(residual)))
        trials: list[CapturedLineSearchTrial] = []
        accepted_trial: tuple[np.ndarray, Any, np.ndarray] | None = None
        for search_index, fraction in enumerate(settings.line_search_fractions):
            candidate = point + float(fraction) * correction
            within_bounds = bool(
                np.all(candidate >= lower) and np.all(candidate <= upper)
            )
            armijo_limit = float(
                (1.0 - settings.armijo_fraction * float(fraction)) * norm_before
            )
            state_id = (
                f"{name}:iteration_{iteration}:line_{search_index}"
                if within_bounds
                else None
            )
            if within_bounds:
                trial_evaluation = objective(candidate.copy(), state_id)
                trial_residual = _residual(trial_evaluation)
                residual_evaluations += 1
                trial_norm = float(np.max(np.abs(trial_residual)))
                accepted = bool(trial_norm <= armijo_limit)
                evaluation_coordinates = _evaluation_coordinates(
                    trial_evaluation, candidate.shape
                )
            else:
                trial_evaluation = None
                trial_residual = None
                trial_norm = None
                accepted = False
                evaluation_coordinates = None
                rejected_bound_steps += 1
            trials.append(
                CapturedLineSearchTrial(
                    iteration=iteration,
                    search_index=search_index,
                    fraction=float(fraction),
                    state_id=state_id,
                    coordinates=_immutable(candidate),
                    within_bounds=within_bounds,
                    residual=(
                        None
                        if trial_residual is None
                        else _immutable(trial_residual)
                    ),
                    residual_inf_norm=trial_norm,
                    armijo_limit=armijo_limit,
                    armijo_accepted=accepted,
                    evaluation_coordinates=evaluation_coordinates,
                )
            )
            if accepted:
                accepted_trial = (
                    candidate.copy(),
                    trial_evaluation,
                    _immutable(trial_residual),
                )
                break
            if within_bounds:
                rejected_line_search_steps += 1
        captures.append(
            CapturedNewtonIteration(
                iteration=iteration,
                coordinates_before=_immutable(point),
                residual_before=_immutable(residual),
                residual_inf_norm_before=norm_before,
                correction=_immutable(correction),
                trials=tuple(trials),
            )
        )
        if accepted_trial is None:
            return _outcome(
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
                initial_residual=initial_residual,
                frozen_jacobian=jacobian,
                jacobian_rank=rank,
                jacobian_condition=condition,
                iteration_captures=captures,
                final_coordinates=point,
                final_residual=residual,
                final_evaluation=evaluation,
            )
        point, evaluation, residual = accepted_trial
        accepted_steps += 1
        if float(np.max(np.abs(residual))) < settings.residual_tolerance:
            return _outcome(
                success=True,
                message="captured modified Newton converged",
                iterations=iteration,
                residual_evaluations=residual_evaluations,
                jacobian_evaluations=1,
                linear_solves=linear_solves,
                accepted_steps=accepted_steps,
                rejected_line_search_steps=rejected_line_search_steps,
                rejected_bound_steps=rejected_bound_steps,
                initial_coordinates=initial,
                initial_residual=initial_residual,
                frozen_jacobian=jacobian,
                jacobian_rank=rank,
                jacobian_condition=condition,
                iteration_captures=captures,
                final_coordinates=point,
                final_residual=residual,
                final_evaluation=evaluation,
            )
    return _outcome(
        success=False,
        message="captured modified Newton exhausted its frozen iteration budget",
        iterations=settings.max_iterations,
        residual_evaluations=residual_evaluations,
        jacobian_evaluations=1,
        linear_solves=linear_solves,
        accepted_steps=accepted_steps,
        rejected_line_search_steps=rejected_line_search_steps,
        rejected_bound_steps=rejected_bound_steps,
        initial_coordinates=initial,
        initial_residual=initial_residual,
        frozen_jacobian=jacobian,
        jacobian_rank=rank,
        jacobian_condition=condition,
        iteration_captures=captures,
        final_coordinates=point,
        final_residual=residual,
        final_evaluation=evaluation,
    )


__all__ = [
    "CapturedLineSearchTrial",
    "CapturedModifiedNewtonOutcome",
    "CapturedNewtonIteration",
    "solve_captured_modified_newton",
]
