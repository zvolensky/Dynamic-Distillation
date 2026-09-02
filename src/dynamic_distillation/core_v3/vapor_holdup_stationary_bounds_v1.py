"""General physical coordinate bounds for the vapor-holdup stationary model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VaporHoldupStationaryBoundSettings:
    composition_floor: float = 1.0e-10
    phase_total_min_ratio: float = 0.1
    phase_total_max_ratio: float = 10.0
    phase_transfer_coordinate_limit: float = 5.0
    temperature_coordinate_limit: float = 5.0
    pressure_coordinate_limit: float = 20.0
    internal_flow_min_ratio: float = 0.2
    internal_flow_max_ratio: float = 5.0
    terminal_ratio_min: float = 0.5
    terminal_ratio_max: float = 1.5


def _inventory_coordinate_bounds(
    reference_inventory: np.ndarray,
    settings: VaporHoldupStationaryBoundSettings,
) -> tuple[np.ndarray, np.ndarray]:
    inventory = np.asarray(reference_inventory, dtype=float)
    if inventory.ndim != 2 or np.any(~np.isfinite(inventory)) or np.any(inventory <= 0.0):
        raise ValueError("reference phase inventory must be positive, finite, and two-dimensional")
    component_count = inventory.shape[1]
    floor = float(settings.composition_floor)
    maximum_fraction = 1.0 - (component_count - 1) * floor
    totals = np.sum(inventory, axis=1, keepdims=True)
    minimum = totals * float(settings.phase_total_min_ratio) * floor
    maximum = totals * float(settings.phase_total_max_ratio) * maximum_fraction
    return (
        np.log(np.broadcast_to(minimum, inventory.shape) / inventory).reshape((-1,)),
        np.log(np.broadcast_to(maximum, inventory.shape) / inventory).reshape((-1,)),
    )


def vapor_holdup_stationary_coordinate_bounds(
    contract: Any,
    reference: Any,
    settings: VaporHoldupStationaryBoundSettings | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Build bounds from phase totals and variable blocks, never chemical names."""
    options = settings or VaporHoldupStationaryBoundSettings()
    scalar_values = np.asarray(
        [
            options.composition_floor,
            options.phase_total_min_ratio,
            options.phase_total_max_ratio,
            options.phase_transfer_coordinate_limit,
            options.temperature_coordinate_limit,
            options.pressure_coordinate_limit,
            options.internal_flow_min_ratio,
            options.internal_flow_max_ratio,
            options.terminal_ratio_min,
            options.terminal_ratio_max,
        ],
        dtype=float,
    )
    if np.any(~np.isfinite(scalar_values)) or np.any(scalar_values <= 0.0):
        raise ValueError("stationary bound settings must be positive and finite")
    if not 0.0 < options.composition_floor < 0.5:
        raise ValueError("composition floor must lie between zero and one half")
    if options.phase_total_min_ratio >= options.phase_total_max_ratio:
        raise ValueError("phase-total bound ratios are reversed")
    if options.internal_flow_min_ratio >= options.internal_flow_max_ratio:
        raise ValueError("internal-flow bound ratios are reversed")
    if options.terminal_ratio_min >= options.terminal_ratio_max:
        raise ValueError("terminal bound ratios are reversed")

    variables = tuple(contract.variables)
    lower = np.empty(len(variables), dtype=float)
    upper = np.empty(len(variables), dtype=float)
    inventory_bounds = {
        "liquid_component_inventory": _inventory_coordinate_bounds(
            reference.liquid_component_inventory_lbmol,
            options,
        ),
        "vapor_component_inventory": _inventory_coordinate_bounds(
            reference.vapor_component_inventory_lbmol,
            options,
        ),
    }
    inventory_cursors = {block: 0 for block in inventory_bounds}
    for index, variable in enumerate(variables):
        block = str(variable.block)
        if block in inventory_bounds:
            block_lower, block_upper = inventory_bounds[block]
            cursor = inventory_cursors[block]
            if cursor >= block_lower.size:
                raise RuntimeError(f"too many variables in inventory block {block!r}")
            lower[index] = block_lower[cursor]
            upper[index] = block_upper[cursor]
            inventory_cursors[block] += 1
        elif block == "interphase_component_transfer":
            limit = float(options.phase_transfer_coordinate_limit)
            lower[index], upper[index] = -limit, limit
        elif block == "temperature":
            limit = float(options.temperature_coordinate_limit)
            lower[index], upper[index] = -limit, limit
        elif block == "pressure":
            limit = float(options.pressure_coordinate_limit)
            lower[index], upper[index] = -limit, limit
        elif block in {"francis_liquid_flow", "pressure_driven_vapor_flow"}:
            lower[index] = np.log(float(options.internal_flow_min_ratio))
            upper[index] = np.log(float(options.internal_flow_max_ratio))
        elif block in {"solved_condenser_duty", "terminal_level_product_flow"}:
            lower[index] = np.log(float(options.terminal_ratio_min))
            upper[index] = np.log(float(options.terminal_ratio_max))
        else:
            raise RuntimeError(f"no stationary bound rule for {block!r}")

    for block, cursor in inventory_cursors.items():
        expected = inventory_bounds[block][0].size
        if cursor != expected:
            raise RuntimeError(f"inventory block {block!r} has {cursor} variables; expected {expected}")
    if (
        np.any(~np.isfinite(lower))
        or np.any(~np.isfinite(upper))
        or np.any(lower >= upper)
        or np.any(0.0 < lower)
        or np.any(0.0 > upper)
    ):
        raise RuntimeError("stationary coordinate bounds are invalid at the reference state")
    return lower, upper


__all__ = [
    "VaporHoldupStationaryBoundSettings",
    "vapor_holdup_stationary_coordinate_bounds",
]
