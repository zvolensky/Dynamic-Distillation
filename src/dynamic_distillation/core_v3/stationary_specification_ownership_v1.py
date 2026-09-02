"""General stationary degree-of-freedom ownership transformations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from .vapor_holdup_stationary_residual_v1 import stationary_structural_pattern


@dataclass(frozen=True)
class FixedBottomsSolvedReboilerTrial:
    base_coordinates: np.ndarray
    balance_inputs: Any
    coordinate_index: int
    fixed_bottoms_lbmolph: float
    reboiler_duty_BTUph: float


def _bottoms_coordinate_index(contract: Any) -> int:
    bottom = contract.topology.column.bottom_volume
    matches = [
        index
        for index, variable in enumerate(contract.variables)
        if str(variable.block) == "terminal_level_product_flow"
        and str(variable.owner) == bottom
    ]
    if len(matches) != 1:
        raise ValueError("stationary contract requires one bottom product-flow coordinate")
    return matches[0]


def _bottom_energy_row_index(contract: Any) -> int:
    bottom = contract.topology.column.bottom_volume
    matches = [
        index
        for index, row in enumerate(contract.rows)
        if str(row.block) == "total_energy_balance" and str(row.owner) == bottom
    ]
    if len(matches) != 1:
        raise ValueError("stationary contract requires one bottom energy row")
    return matches[0]


def fixed_bottoms_solved_reboiler_trial(
    contract: Any,
    reference: Any,
    balance_inputs: Any,
    coordinates: Sequence[float],
    *,
    fixed_bottoms_lbmolph: float,
) -> FixedBottomsSolvedReboilerTrial:
    """Fix bottoms flow and reuse its coordinate to solve positive reboiler duty."""
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    fixed_bottoms = float(fixed_bottoms_lbmolph)
    reference_bottoms = float(reference.bottoms_lbmolph)
    reference_duty = float(balance_inputs.reboiler_duty_BTUph)
    if (
        point.shape != (len(contract.variables),)
        or np.any(~np.isfinite(point))
        or not np.isfinite(fixed_bottoms)
        or fixed_bottoms <= 0.0
        or not np.isfinite(reference_bottoms)
        or reference_bottoms <= 0.0
        or not np.isfinite(reference_duty)
        or reference_duty <= 0.0
    ):
        raise ValueError("fixed-bottoms / solved-duty stationary trial is invalid")
    coordinate_index = _bottoms_coordinate_index(contract)
    base_coordinates = point.copy()
    base_coordinates[coordinate_index] = np.log(fixed_bottoms / reference_bottoms)
    reboiler_duty = reference_duty * np.exp(point[coordinate_index])
    live_inputs = replace(
        balance_inputs,
        bottoms_lbmolph=fixed_bottoms,
        reboiler_duty_BTUph=float(reboiler_duty),
    )
    return FixedBottomsSolvedReboilerTrial(
        base_coordinates=base_coordinates,
        balance_inputs=live_inputs,
        coordinate_index=coordinate_index,
        fixed_bottoms_lbmolph=fixed_bottoms,
        reboiler_duty_BTUph=float(reboiler_duty),
    )


def fixed_bottoms_solved_reboiler_pattern(
    contract: Any,
    *,
    base_pattern: np.ndarray | None = None,
) -> np.ndarray:
    """Replace bottom-flow column ownership with bottom-energy duty ownership."""
    pattern = (
        stationary_structural_pattern(contract).copy()
        if base_pattern is None
        else np.asarray(base_pattern, dtype=bool).copy()
    )
    size = len(contract.variables)
    if pattern.shape != (size, size):
        raise ValueError("stationary structural pattern has the wrong shape")
    coordinate_index = _bottoms_coordinate_index(contract)
    energy_row_index = _bottom_energy_row_index(contract)
    pattern[:, coordinate_index] = False
    pattern[energy_row_index, coordinate_index] = True
    return pattern


def specification_aware_variable_names(contract: Any) -> tuple[str, ...]:
    """Return the variable ledger after the bottom-product/duty ownership swap."""
    names = [str(variable.name) for variable in contract.variables]
    names[_bottoms_coordinate_index(contract)] = "Q_R"
    return tuple(names)


__all__ = [
    "FixedBottomsSolvedReboilerTrial",
    "fixed_bottoms_solved_reboiler_pattern",
    "fixed_bottoms_solved_reboiler_trial",
    "specification_aware_variable_names",
]
