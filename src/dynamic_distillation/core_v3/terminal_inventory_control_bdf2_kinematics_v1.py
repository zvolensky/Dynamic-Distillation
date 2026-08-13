"""Property-free constant-step BDF2 kinematics for controlled Core V3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class ControlledBDF2History:
    step_seconds: float
    current_inventory_lbmol: np.ndarray
    prior_inventory_lbmol: np.ndarray
    current_internal_energy_BTU: np.ndarray
    prior_internal_energy_BTU: np.ndarray
    current_controller_memory: np.ndarray
    prior_controller_memory: np.ndarray


@dataclass(frozen=True)
class ControlledBDF2Kinematics:
    endpoint_inventory_lbmol: np.ndarray
    component_rate_lbmolph: np.ndarray
    component_rate_coordinates: np.ndarray
    endpoint_internal_energy_BTU: np.ndarray
    energy_storage_rate_BTUph: np.ndarray
    endpoint_controller_memory: np.ndarray
    controller_rate_per_sec: np.ndarray
    step_seconds: float


def _finite_array(values: Sequence[float], *, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if np.any(~np.isfinite(result)):
        raise ValueError(f"{name} must be finite")
    return result


def _positive_step(step_seconds: float, *, name: str) -> float:
    result = float(step_seconds)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return result


def bdf2_derivative(
    endpoint: Sequence[float],
    current: Sequence[float],
    prior: Sequence[float],
    *,
    step: float,
) -> np.ndarray:
    """Return the constant-step BDF2 derivative at the endpoint."""
    endpoint_values = _finite_array(endpoint, name="BDF2 endpoint")
    current_values = _finite_array(current, name="BDF2 current history")
    prior_values = _finite_array(prior, name="BDF2 prior history")
    if endpoint_values.shape != current_values.shape or endpoint_values.shape != prior_values.shape:
        raise ValueError("BDF2 endpoint and history shapes must match")
    interval = _positive_step(step, name="BDF2 step")
    return (
        3.0 * (endpoint_values - current_values)
        - (current_values - prior_values)
    ) / (2.0 * interval)


def bdf2_endpoint_from_derivative(
    derivative: Sequence[float],
    current: Sequence[float],
    prior: Sequence[float],
    *,
    step: float,
) -> np.ndarray:
    """Invert the constant-step BDF2 derivative for the endpoint value."""
    rate = _finite_array(derivative, name="BDF2 derivative")
    current_values = _finite_array(current, name="BDF2 current history")
    prior_values = _finite_array(prior, name="BDF2 prior history")
    if rate.shape != current_values.shape or rate.shape != prior_values.shape:
        raise ValueError("BDF2 derivative and history shapes must match")
    interval = _positive_step(step, name="BDF2 step")
    return current_values + (
        2.0 * interval * rate + current_values - prior_values
    ) / 3.0


def build_controlled_bdf2_history(
    *,
    step_seconds: float,
    current_inventory_lbmol: Sequence[Sequence[float]],
    prior_inventory_lbmol: Sequence[Sequence[float]],
    current_internal_energy_BTU: Sequence[float],
    prior_internal_energy_BTU: Sequence[float],
    current_controller_memory: Sequence[float],
    prior_controller_memory: Sequence[float],
) -> ControlledBDF2History:
    step_value = _positive_step(step_seconds, name="BDF2 history step")
    current_inventory = _finite_array(
        current_inventory_lbmol, name="current inventory history"
    )
    prior_inventory = _finite_array(
        prior_inventory_lbmol, name="prior inventory history"
    )
    if (
        current_inventory.ndim != 2
        or prior_inventory.shape != current_inventory.shape
        or np.any(current_inventory <= 0.0)
        or np.any(prior_inventory <= 0.0)
    ):
        raise ValueError("BDF2 inventory history must be matching positive matrices")
    current_energy = _finite_array(
        current_internal_energy_BTU, name="current energy history"
    ).reshape((-1,))
    prior_energy = _finite_array(
        prior_internal_energy_BTU, name="prior energy history"
    ).reshape((-1,))
    if current_energy.shape != (current_inventory.shape[0],) or prior_energy.shape != current_energy.shape:
        raise ValueError("BDF2 energy history must have one value per volume")
    current_memory = _finite_array(
        current_controller_memory, name="current controller history"
    ).reshape((-1,))
    prior_memory = _finite_array(
        prior_controller_memory, name="prior controller history"
    ).reshape((-1,))
    if current_memory.shape != (2,) or prior_memory.shape != (2,):
        raise ValueError("BDF2 controller history must contain two memories")
    return ControlledBDF2History(
        step_seconds=step_value,
        current_inventory_lbmol=current_inventory.copy(),
        prior_inventory_lbmol=prior_inventory.copy(),
        current_internal_energy_BTU=current_energy.copy(),
        prior_internal_energy_BTU=prior_energy.copy(),
        current_controller_memory=current_memory.copy(),
        prior_controller_memory=prior_memory.copy(),
    )


def evaluate_controlled_bdf2_kinematics(
    history: ControlledBDF2History,
    *,
    nominal_component_rate_lbmolph: Sequence[Sequence[float]],
    component_rate_scales_lbmolph: Sequence[Sequence[float]],
    endpoint_internal_energy_BTU: Sequence[float],
    controller_rate_per_sec: Sequence[float],
    step_seconds: float,
) -> ControlledBDF2Kinematics:
    """Map trial rates and fixed history into one physical BDF2 endpoint."""
    step_value = _positive_step(step_seconds, name="BDF2 evaluation step")
    if not np.isclose(
        step_value,
        history.step_seconds,
        rtol=0.0,
        atol=max(1.0e-15, abs(history.step_seconds) * 1.0e-14),
    ):
        raise ValueError("BDF2 evaluation step does not match the fixed history step")
    current = history.current_inventory_lbmol
    nominal_rate = _finite_array(
        nominal_component_rate_lbmolph, name="nominal component rate"
    )
    rate_scales = _finite_array(
        component_rate_scales_lbmolph, name="component rate scales"
    )
    if nominal_rate.shape != current.shape or rate_scales.shape != current.shape:
        raise ValueError("BDF2 component rates and scales must match inventory history")
    if np.any(rate_scales <= 0.0):
        raise ValueError("BDF2 component rate scales must be positive")
    step_hours = step_value / 3600.0
    exponent = step_hours * nominal_rate / current
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        endpoint_inventory = current * np.exp(exponent)
    if np.any(~np.isfinite(endpoint_inventory)) or np.any(endpoint_inventory <= 0.0):
        raise ValueError("BDF2 endpoint inventory is not physical")
    component_rate = bdf2_derivative(
        endpoint_inventory,
        current,
        history.prior_inventory_lbmol,
        step=step_hours,
    )
    endpoint_energy = _finite_array(
        endpoint_internal_energy_BTU, name="endpoint internal energy"
    ).reshape((-1,))
    if endpoint_energy.shape != history.current_internal_energy_BTU.shape:
        raise ValueError("BDF2 endpoint energy must have one value per volume")
    energy_rate = bdf2_derivative(
        endpoint_energy,
        history.current_internal_energy_BTU,
        history.prior_internal_energy_BTU,
        step=step_hours,
    )
    controller_rate = _finite_array(
        controller_rate_per_sec, name="controller rate"
    ).reshape((-1,))
    if controller_rate.shape != (2,):
        raise ValueError("BDF2 controller rate must contain two values")
    endpoint_memory = bdf2_endpoint_from_derivative(
        controller_rate,
        history.current_controller_memory,
        history.prior_controller_memory,
        step=step_value,
    )
    reproduced_controller_rate = bdf2_derivative(
        endpoint_memory,
        history.current_controller_memory,
        history.prior_controller_memory,
        step=step_value,
    )
    return ControlledBDF2Kinematics(
        endpoint_inventory_lbmol=endpoint_inventory,
        component_rate_lbmolph=component_rate,
        component_rate_coordinates=component_rate / rate_scales,
        endpoint_internal_energy_BTU=endpoint_energy.copy(),
        energy_storage_rate_BTUph=energy_rate,
        endpoint_controller_memory=endpoint_memory,
        controller_rate_per_sec=reproduced_controller_rate,
        step_seconds=step_value,
    )


__all__ = [
    "ControlledBDF2History",
    "ControlledBDF2Kinematics",
    "bdf2_derivative",
    "bdf2_endpoint_from_derivative",
    "build_controlled_bdf2_history",
    "evaluate_controlled_bdf2_kinematics",
]
