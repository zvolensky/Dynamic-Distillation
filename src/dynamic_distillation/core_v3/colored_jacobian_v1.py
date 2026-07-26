"""Deterministic structural coloring for central-difference Jacobians."""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    DynamicDAEContract,
)


def contract_sparsity_pattern(
    contract: DynamicDAEContract,
    *,
    include_state_rate_dependencies: bool = False,
) -> tuple[np.ndarray, tuple[str, ...]]:
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    names = tuple(variable.name for variable in variables)
    index = {name: position for position, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            pattern[row_index, index[dependency]] = True
        if include_state_rate_dependencies:
            for dependency in row.state_dependencies:
                rate_name = f"d{dependency}/dt"
                if rate_name in index:
                    pattern[row_index, index[rate_name]] = True
    return pattern, names


def greedy_column_groups(pattern: Sequence[Sequence[bool]]) -> tuple[tuple[int, ...], ...]:
    structure = np.asarray(pattern, dtype=bool)
    if structure.ndim != 2 or structure.shape[1] == 0:
        raise ValueError("Jacobian sparsity pattern must be a nonempty matrix")
    conflicts = (structure.T.astype(int) @ structure.astype(int)) > 0
    np.fill_diagonal(conflicts, False)
    degrees = np.sum(conflicts, axis=1)
    order = sorted(range(structure.shape[1]), key=lambda column: (-degrees[column], column))
    colors = np.full(structure.shape[1], -1, dtype=int)
    for column in order:
        unavailable = {
            int(colors[neighbor])
            for neighbor in np.flatnonzero(conflicts[column])
            if colors[neighbor] >= 0
        }
        color = 0
        while color in unavailable:
            color += 1
        colors[column] = color
    return tuple(
        tuple(int(column) for column in np.flatnonzero(colors == color))
        for color in range(int(np.max(colors)) + 1)
    )


def colored_central_difference_jacobian(
    objective: Callable[[np.ndarray, str], np.ndarray],
    point: Sequence[float],
    *,
    pattern: Sequence[Sequence[bool]],
    step: float,
    state_id: str,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    coordinates = np.asarray(point, dtype=float).reshape((-1,))
    structure = np.asarray(pattern, dtype=bool)
    if structure.ndim != 2 or structure.shape[1] != coordinates.size:
        raise ValueError("Jacobian pattern does not match solve coordinates")
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("Jacobian step must be positive")
    groups = greedy_column_groups(structure)
    matrix = np.zeros(structure.shape, dtype=float)
    for color, group in enumerate(groups):
        rows_per_column = [np.flatnonzero(structure[:, column]) for column in group]
        occupied = np.concatenate(rows_per_column)
        if np.unique(occupied).size != occupied.size:
            raise RuntimeError("colored Jacobian group contains a row conflict")
        delta = np.zeros_like(coordinates)
        delta[list(group)] = float(step)
        plus = np.asarray(
            objective(coordinates + delta, f"{state_id}:color_{color}:plus"),
            dtype=float,
        ).reshape((-1,))
        minus = np.asarray(
            objective(coordinates - delta, f"{state_id}:color_{color}:minus"),
            dtype=float,
        ).reshape((-1,))
        if plus.size != structure.shape[0] or minus.size != structure.shape[0]:
            raise ValueError("objective row count does not match Jacobian pattern")
        difference = (plus - minus) / (2.0 * float(step))
        for column, rows in zip(group, rows_per_column, strict=True):
            matrix[rows, column] = difference[rows]
    return matrix, groups


__all__ = [
    "colored_central_difference_jacobian",
    "contract_sparsity_pattern",
    "greedy_column_groups",
]
