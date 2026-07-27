"""Frozen least-squares root kernel for the Core V3 zero-rate residual."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)


@dataclass(frozen=True)
class ZeroRateRootSettings:
    method: str = "trf"
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 80
    x_scale: float = 1.0
    jacobian_step: float = 1.0e-5


@dataclass(frozen=True)
class ZeroRateRootOutcome:
    success: bool
    status: int
    message: str
    residual_evaluations: int
    jacobian_evaluations: int
    final_coordinates: np.ndarray
    final_residual: np.ndarray
    cost: float
    optimality: float


def solve_zero_rate_root(
    objective: Callable[[np.ndarray, str], np.ndarray],
    start: Sequence[float],
    *,
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    pattern: Sequence[Sequence[bool]],
    settings: ZeroRateRootSettings,
    state_id: str,
) -> ZeroRateRootOutcome:
    point = np.asarray(start, dtype=float).reshape((-1,))
    lower = np.asarray(lower_bounds, dtype=float).reshape((-1,))
    upper = np.asarray(upper_bounds, dtype=float).reshape((-1,))
    structure = np.asarray(pattern, dtype=bool)
    if settings.method != "trf":
        raise ValueError("zero-rate root permits only least_squares(method='trf')")
    if (
        point.shape != lower.shape
        or point.shape != upper.shape
        or structure.shape[1] != point.size
        or np.any(~np.isfinite(point))
        or np.any(lower >= upper)
        or np.any(point <= lower)
        or np.any(point >= upper)
        or not np.isfinite(settings.jacobian_step)
        or settings.jacobian_step <= 0.0
    ):
        raise ValueError("zero-rate root numerical inputs are invalid")
    calls = {"residual": 0, "jacobian": 0}

    def residual(candidate: np.ndarray) -> np.ndarray:
        calls["residual"] += 1
        return np.asarray(
            objective(candidate, f"{state_id}:residual:{calls['residual']}"),
            dtype=float,
        )

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        calls["jacobian"] += 1
        matrix, _ = colored_central_difference_jacobian(
            objective,
            candidate,
            pattern=structure,
            step=settings.jacobian_step,
            state_id=f"{state_id}:jacobian:{calls['jacobian']}",
        )
        return matrix

    result = least_squares(
        residual,
        point,
        jac=jacobian,
        bounds=(lower, upper),
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=settings.x_scale,
    )
    final = np.asarray(result.x, dtype=float)
    final_residual = residual(final)
    return ZeroRateRootOutcome(
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        residual_evaluations=calls["residual"],
        jacobian_evaluations=calls["jacobian"],
        final_coordinates=final,
        final_residual=final_residual,
        cost=float(result.cost),
        optimality=float(result.optimality),
    )


__all__ = [
    "ZeroRateRootOutcome",
    "ZeroRateRootSettings",
    "solve_zero_rate_root",
]
