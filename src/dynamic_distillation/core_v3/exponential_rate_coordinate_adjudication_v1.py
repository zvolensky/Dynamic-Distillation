"""Static nominal-to-actual rate mapping for exponential inventory steps."""

from __future__ import annotations

from typing import Sequence

import numpy as np


def actual_component_rate_coordinates(
    nominal_coordinates: Sequence[float],
    previous_inventory_lbmol: Sequence[Sequence[float]],
    *,
    component_rate_scale_lbmolph: float,
    step_seconds: float,
) -> np.ndarray:
    previous = np.asarray(previous_inventory_lbmol, dtype=float)
    nominal = np.asarray(nominal_coordinates, dtype=float).reshape((-1,))
    if (
        previous.ndim != 2
        or previous.size != nominal.size
        or np.any(~np.isfinite(previous))
        or np.any(previous <= 0.0)
        or np.any(~np.isfinite(nominal))
        or not np.isfinite(component_rate_scale_lbmolph)
        or component_rate_scale_lbmolph <= 0.0
        or not np.isfinite(step_seconds)
        or step_seconds <= 0.0
    ):
        raise ValueError("exponential rate-coordinate inputs are invalid")
    step_hours = float(step_seconds) / 3600.0
    nominal_rate = nominal.reshape(previous.shape) * float(
        component_rate_scale_lbmolph
    )
    endpoint = previous * np.exp(step_hours * nominal_rate / previous)
    actual_rate = (endpoint - previous) / step_hours
    return actual_rate.reshape((-1,)) / float(component_rate_scale_lbmolph)


__all__ = ["actual_component_rate_coordinates"]
