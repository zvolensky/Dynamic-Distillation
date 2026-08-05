"""Serializable task construction and deterministic assembly for colored Jacobians."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups


@dataclass(frozen=True)
class ColoredCentralDifferenceTask:
    order: int
    color: int
    sign: int
    coordinates: tuple[float, ...]
    state_id: str


@dataclass(frozen=True)
class ColoredCentralDifferenceResult:
    order: int
    residual: tuple[float, ...]


def build_colored_central_difference_tasks(
    point: Sequence[float],
    *,
    pattern: Sequence[Sequence[bool]],
    step: float,
    state_id: str,
) -> tuple[
    tuple[ColoredCentralDifferenceTask, ...],
    tuple[tuple[int, ...], ...],
]:
    coordinates = np.asarray(point, dtype=float).reshape((-1,))
    structure = np.asarray(pattern, dtype=bool)
    if structure.ndim != 2 or structure.shape[1] != coordinates.size:
        raise ValueError("Jacobian pattern does not match solve coordinates")
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("Jacobian step must be positive")

    groups = greedy_column_groups(structure)
    tasks: list[ColoredCentralDifferenceTask] = []
    for color, group in enumerate(groups):
        rows_per_column = [np.flatnonzero(structure[:, column]) for column in group]
        occupied = np.concatenate(rows_per_column)
        if np.unique(occupied).size != occupied.size:
            raise RuntimeError("colored Jacobian group contains a row conflict")
        delta = np.zeros_like(coordinates)
        delta[list(group)] = float(step)
        for sign, suffix in ((1, "plus"), (-1, "minus")):
            trial = coordinates + float(sign) * delta
            tasks.append(
                ColoredCentralDifferenceTask(
                    order=len(tasks),
                    color=int(color),
                    sign=int(sign),
                    coordinates=tuple(float(value) for value in trial),
                    state_id=f"{state_id}:color_{color}:{suffix}",
                )
            )
    return tuple(tasks), groups


def assemble_colored_central_difference_jacobian(
    tasks: Sequence[ColoredCentralDifferenceTask],
    results: Sequence[ColoredCentralDifferenceResult],
    *,
    pattern: Sequence[Sequence[bool]],
    step: float,
) -> np.ndarray:
    structure = np.asarray(pattern, dtype=bool)
    if structure.ndim != 2:
        raise ValueError("Jacobian pattern must be a matrix")
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("Jacobian step must be positive")

    groups = greedy_column_groups(structure)
    expected_count = 2 * len(groups)
    if len(tasks) != expected_count or len(results) != expected_count:
        raise ValueError("colored Jacobian task/result count is incomplete")
    task_by_order = {int(task.order): task for task in tasks}
    result_by_order = {int(result.order): result for result in results}
    expected_orders = set(range(expected_count))
    if set(task_by_order) != expected_orders or set(result_by_order) != expected_orders:
        raise ValueError("colored Jacobian task/result orders are incomplete or duplicated")

    matrix = np.zeros(structure.shape, dtype=float)
    for color, group in enumerate(groups):
        plus_task = task_by_order[2 * color]
        minus_task = task_by_order[2 * color + 1]
        if (
            plus_task.color != color
            or plus_task.sign != 1
            or minus_task.color != color
            or minus_task.sign != -1
        ):
            raise ValueError("colored Jacobian task metadata is inconsistent")
        plus = np.asarray(result_by_order[plus_task.order].residual, dtype=float)
        minus = np.asarray(result_by_order[minus_task.order].residual, dtype=float)
        if plus.shape != (structure.shape[0],) or minus.shape != (structure.shape[0],):
            raise ValueError("objective row count does not match Jacobian pattern")
        difference = (plus - minus) / (2.0 * float(step))
        for column in group:
            rows = np.flatnonzero(structure[:, column])
            matrix[rows, column] = difference[rows]
    return matrix


__all__ = [
    "ColoredCentralDifferenceResult",
    "ColoredCentralDifferenceTask",
    "assemble_colored_central_difference_jacobian",
    "build_colored_central_difference_tasks",
]
