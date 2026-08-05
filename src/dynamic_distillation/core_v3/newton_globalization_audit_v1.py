"""Static line-search diagnostics for a supplied Newton linearization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np
from scipy.linalg import LinAlgWarning, lu_factor, lu_solve
import warnings


@dataclass(frozen=True)
class NewtonLineSearchCandidate:
    fraction: float
    within_bounds: bool
    residual_inf_norm: float | None
    armijo_limit: float
    armijo_accepted: bool


@dataclass(frozen=True)
class NewtonCorrectionProbe:
    current_residual_inf_norm: float
    jacobian_rank: int
    jacobian_condition: float
    correction_inf_norm: float | None
    candidates: tuple[NewtonLineSearchCandidate, ...]

    @property
    def accepted_fractions(self) -> tuple[float, ...]:
        return tuple(
            candidate.fraction
            for candidate in self.candidates
            if candidate.armijo_accepted
        )

    @property
    def best_residual_inf_norm(self) -> float | None:
        values = tuple(
            candidate.residual_inf_norm
            for candidate in self.candidates
            if candidate.residual_inf_norm is not None
        )
        return None if not values else float(min(values))


def _scaled(evaluation: Any) -> np.ndarray:
    values = np.asarray(evaluation.scaled, dtype=float).reshape((-1,))
    if values.size == 0 or np.any(~np.isfinite(values)):
        raise ValueError("Newton globalization residual must be finite and nonempty")
    return values


def probe_newton_correction(
    objective: Callable[[np.ndarray, str], Any],
    *,
    point: Sequence[float],
    residual: Sequence[float],
    jacobian: Sequence[Sequence[float]],
    line_search_fractions: Sequence[float],
    armijo_fraction: float,
    lower_bounds: Sequence[float] | None = None,
    upper_bounds: Sequence[float] | None = None,
    condition_limit: float = 1.0e8,
    name: str,
) -> NewtonCorrectionProbe:
    """Evaluate every frozen line-search fraction without accepting a state."""
    coordinates = np.asarray(point, dtype=float).reshape((-1,))
    values = np.asarray(residual, dtype=float).reshape((-1,))
    matrix = np.asarray(jacobian, dtype=float)
    fractions = np.asarray(line_search_fractions, dtype=float).reshape((-1,))
    lower = (
        np.full(coordinates.shape, -np.inf)
        if lower_bounds is None
        else np.asarray(lower_bounds, dtype=float).reshape((-1,))
    )
    upper = (
        np.full(coordinates.shape, np.inf)
        if upper_bounds is None
        else np.asarray(upper_bounds, dtype=float).reshape((-1,))
    )
    if (
        coordinates.size == 0
        or values.shape != coordinates.shape
        or matrix.shape != (coordinates.size, coordinates.size)
        or lower.shape != coordinates.shape
        or upper.shape != coordinates.shape
        or np.any(~np.isfinite(coordinates))
        or np.any(~np.isfinite(values))
        or np.any(~np.isfinite(matrix))
        or np.any(lower >= upper)
        or np.any(coordinates < lower)
        or np.any(coordinates > upper)
        or fractions.size == 0
        or np.any(~np.isfinite(fractions))
        or np.any((fractions <= 0.0) | (fractions > 1.0))
        or not 0.0 < armijo_fraction < 1.0
        or not np.isfinite(condition_limit)
        or condition_limit <= 1.0
    ):
        raise ValueError("Newton globalization probe inputs are invalid")

    singular_values = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular_values[0]
    rank = int(np.count_nonzero(singular_values > tolerance))
    condition = float(
        np.inf
        if singular_values[-1] <= tolerance
        else singular_values[0] / singular_values[-1]
    )
    current_norm = float(np.max(np.abs(values)))
    if rank != coordinates.size or condition >= condition_limit:
        return NewtonCorrectionProbe(
            current_residual_inf_norm=current_norm,
            jacobian_rank=rank,
            jacobian_condition=condition,
            correction_inf_norm=None,
            candidates=(),
        )

    with warnings.catch_warnings():
        warnings.simplefilter("error", LinAlgWarning)
        factor = lu_factor(matrix, check_finite=False)
    correction = lu_solve(factor, -values, check_finite=False)
    if np.any(~np.isfinite(correction)):
        raise ValueError("Newton globalization correction must be finite")

    candidates: list[NewtonLineSearchCandidate] = []
    for index, fraction in enumerate(fractions):
        trial_point = coordinates + float(fraction) * correction
        within_bounds = bool(
            np.all(trial_point >= lower) and np.all(trial_point <= upper)
        )
        armijo_limit = float(
            (1.0 - armijo_fraction * float(fraction)) * current_norm
        )
        if within_bounds:
            trial = objective(trial_point, f"{name}:line_{index}")
            trial_norm = float(np.max(np.abs(_scaled(trial))))
            accepted = bool(trial_norm <= armijo_limit)
        else:
            trial_norm = None
            accepted = False
        candidates.append(
            NewtonLineSearchCandidate(
                fraction=float(fraction),
                within_bounds=within_bounds,
                residual_inf_norm=trial_norm,
                armijo_limit=armijo_limit,
                armijo_accepted=accepted,
            )
        )
    return NewtonCorrectionProbe(
        current_residual_inf_norm=current_norm,
        jacobian_rank=rank,
        jacobian_condition=condition,
        correction_inf_norm=float(np.max(np.abs(correction))),
        candidates=tuple(candidates),
    )


__all__ = [
    "NewtonCorrectionProbe",
    "NewtonLineSearchCandidate",
    "probe_newton_correction",
]
