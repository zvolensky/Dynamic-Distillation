"""Generic total-reboiler boundary replacement for stationary Core V3."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from .vapor_holdup_stationary_residual_v1 import stationary_structural_pattern


def _ledger(
    contract: Any,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, int]]:
    bottom = str(contract.topology.column.bottom_volume)
    row_indices = tuple(
        index
        for index, row in enumerate(contract.rows)
        if str(row.block) == "full_phase_equilibrium" and str(row.owner) == bottom
    )
    local_variables = tuple(
        index
        for index, variable in enumerate(contract.variables)
        if str(variable.owner) == bottom
        and str(variable.block)
        in {"liquid_component_inventory", "vapor_component_inventory"}
    )
    component_count = len(contract.component_names)
    if len(row_indices) != component_count or len(local_variables) != 2 * component_count:
        raise ValueError("total-reboiler row/variable ledger is incomplete")
    adjacent = tuple(
        destination
        for source, destination, _symbol in contract.topology.column.vapor_links
        if str(source) == bottom
    )
    if len(adjacent) != 1:
        raise ValueError("total reboiler requires one adjacent column volume")
    names = tuple(str(variable.name) for variable in contract.variables)
    temperature_variables = (
        names.index(f"T[{bottom}]"), names.index(f"T[{adjacent[0]}]")
    )
    return row_indices, local_variables, temperature_variables


def total_reboiler_structural_pattern(
    contract: Any, *, base_pattern: np.ndarray | None = None
) -> np.ndarray:
    """Replace bottom equilibrium dependencies with the no-separation boundary."""
    pattern = (
        stationary_structural_pattern(contract)
        if base_pattern is None
        else np.asarray(base_pattern, dtype=bool).copy()
    )
    if pattern.shape != (len(contract.rows), len(contract.variables)):
        raise ValueError("stationary structural pattern has the wrong shape")
    row_indices, local_variables, temperature_variables = _ledger(contract)
    for row_index in row_indices[:-1]:
        pattern[row_index, :] = False
        pattern[row_index, local_variables] = True
    pattern[row_indices[-1], :] = False
    pattern[row_indices[-1], temperature_variables] = True
    return pattern


def apply_total_reboiler_boundary(
    contract: Any,
    base_evaluation: Any,
    *,
    temperature_scale_F: float,
) -> Any:
    """Enforce no separation and an isothermal total-reboiler connection."""
    endpoint = base_evaluation.endpoint
    liquid_inventory = np.asarray(
        endpoint.liquid_component_inventory_lbmol, dtype=float
    )
    vapor_inventory = np.asarray(
        endpoint.vapor_component_inventory_lbmol, dtype=float
    )
    if (
        liquid_inventory.ndim != 2
        or vapor_inventory.shape != liquid_inventory.shape
        or liquid_inventory.shape[1] != len(contract.component_names)
        or np.any(liquid_inventory <= 0.0)
        or np.any(vapor_inventory <= 0.0)
    ):
        raise ValueError("total-reboiler inventories are invalid")
    liquid_x = liquid_inventory[-1] / np.sum(liquid_inventory[-1])
    vapor_y = vapor_inventory[-1] / np.sum(vapor_inventory[-1])
    if not np.isfinite(temperature_scale_F) or temperature_scale_F <= 0.0:
        raise ValueError("total-reboiler temperature scale must be positive")
    composition_residual = np.log(
        (vapor_y[:-1] / vapor_y[-1]) / (liquid_x[:-1] / liquid_x[-1])
    )
    bottom = str(contract.topology.column.bottom_volume)
    adjacent = next(
        destination
        for source, destination, _symbol in contract.topology.column.vapor_links
        if str(source) == bottom
    )
    volumes = tuple(str(value) for value in contract.topology.column.volume_ids)
    temperature_residual = float(endpoint.temperature_F[volumes.index(bottom)]) - float(
        endpoint.temperature_F[volumes.index(str(adjacent))]
    )

    raw = np.asarray(base_evaluation.raw, dtype=float).copy()
    scales = np.asarray(base_evaluation.scales, dtype=float).copy()
    row_names = list(base_evaluation.row_names)
    row_indices, _local_variables, _temperature_variables = _ledger(contract)
    for component_index, row_index in enumerate(row_indices[:-1]):
        raw[row_index] = composition_residual[component_index]
        scales[row_index] = 1.0
        row_names[row_index] = (
            f"total_reboiler_no_separation[{bottom},"
            f"{contract.component_names[component_index]}]"
        )
    raw[row_indices[-1]] = temperature_residual
    scales[row_indices[-1]] = float(temperature_scale_F)
    row_names[row_indices[-1]] = f"total_reboiler_isothermal[{bottom},{adjacent}]"
    fugacity = np.asarray(base_evaluation.fugacity_residual, dtype=float).copy()
    fugacity[-1, :-1] = composition_residual
    fugacity[-1, -1] = temperature_residual / float(temperature_scale_F)
    return replace(
        base_evaluation,
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        row_names=tuple(row_names),
        fugacity_residual=fugacity,
    )


__all__ = [
    "apply_total_reboiler_boundary",
    "total_reboiler_structural_pattern",
]
