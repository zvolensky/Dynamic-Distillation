"""Variable-ledger bounds for one vapor-holdup implicit step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VaporHoldupImplicitStepBoundSettings:
    inventory_log_increment_limit: float = 0.01
    phase_transfer_coordinate_limit: float = 0.1
    temperature_coordinate_limit: float = 0.1
    pressure_coordinate_limit: float = 0.1
    flow_log_increment_limit: float = 0.01
    condenser_duty_log_increment_limit: float = 0.01


def vapor_holdup_implicit_step_coordinate_bounds(
    contract: Any,
    settings: VaporHoldupImplicitStepBoundSettings | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Build symmetric local bounds from declared variable blocks."""
    options = settings or VaporHoldupImplicitStepBoundSettings()
    limits = {
        "liquid_component_inventory_rate": options.inventory_log_increment_limit,
        "vapor_component_inventory_rate": options.inventory_log_increment_limit,
        "interphase_component_transfer": options.phase_transfer_coordinate_limit,
        "temperature": options.temperature_coordinate_limit,
        "algebraic_pressure": options.pressure_coordinate_limit,
        "francis_liquid_flow": options.flow_log_increment_limit,
        "pressure_driven_vapor_flow": options.flow_log_increment_limit,
        "solved_condenser_duty": options.condenser_duty_log_increment_limit,
    }
    values = np.asarray(tuple(limits.values()), dtype=float)
    if np.any(~np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("implicit-step coordinate limits must be positive and finite")
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    lower = np.empty(len(variables), dtype=float)
    upper = np.empty(len(variables), dtype=float)
    for index, variable in enumerate(variables):
        block = str(variable.block)
        if block not in limits:
            raise RuntimeError(f"no implicit-step bound rule for {block!r}")
        limit = float(limits[block])
        lower[index], upper[index] = -limit, limit
    return lower, upper


__all__ = [
    "VaporHoldupImplicitStepBoundSettings",
    "vapor_holdup_implicit_step_coordinate_bounds",
]
