"""Property-free comparisons for repeated finite-difference Jacobians."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class JacobianComparison:
    row_count: int
    column_count: int
    max_abs_difference: float
    relative_frobenius_difference: float
    worst_row_index: int
    worst_row_name: str
    worst_column_index: int
    worst_column_name: str


@dataclass(frozen=True)
class JacobianRepeatability:
    sample_count: int
    row_count: int
    column_count: int
    max_abs_spread: float
    max_relative_frobenius_difference: float
    worst_sample_pair: tuple[int, int]
    worst_row_index: int
    worst_row_name: str
    worst_column_index: int
    worst_column_name: str


def _matrix(
    value: Sequence[Sequence[float]],
    row_names: Sequence[str],
    column_names: Sequence[str],
) -> tuple[np.ndarray, tuple[str, ...], tuple[str, ...]]:
    matrix = np.asarray(value, dtype=float)
    rows = tuple(str(name) for name in row_names)
    columns = tuple(str(name) for name in column_names)
    if (
        matrix.ndim != 2
        or matrix.shape != (len(rows), len(columns))
        or matrix.size == 0
        or len(set(rows)) != len(rows)
        or len(set(columns)) != len(columns)
        or np.any(~np.isfinite(matrix))
    ):
        raise ValueError("Jacobian matrix or labels are invalid")
    return matrix, rows, columns


def compare_jacobians(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
    row_names: Sequence[str],
    column_names: Sequence[str],
) -> JacobianComparison:
    """Compare two labeled Jacobians without invoking the model or provider."""
    first, rows, columns = _matrix(left, row_names, column_names)
    second, _, _ = _matrix(right, rows, columns)
    difference = np.abs(first - second)
    flat_index = int(np.argmax(difference))
    row_index, column_index = np.unravel_index(flat_index, difference.shape)
    denominator = max(float(np.linalg.norm(first)), np.finfo(float).tiny)
    return JacobianComparison(
        row_count=int(first.shape[0]),
        column_count=int(first.shape[1]),
        max_abs_difference=float(difference[row_index, column_index]),
        relative_frobenius_difference=float(
            np.linalg.norm(first - second) / denominator
        ),
        worst_row_index=int(row_index),
        worst_row_name=rows[row_index],
        worst_column_index=int(column_index),
        worst_column_name=columns[column_index],
    )


def jacobian_repeatability(
    samples: Sequence[Sequence[Sequence[float]]],
    row_names: Sequence[str],
    column_names: Sequence[str],
) -> JacobianRepeatability:
    """Return the worst pairwise difference across complete Jacobian samples."""
    if len(samples) < 2:
        raise ValueError("at least two Jacobian samples are required")
    matrices = [_matrix(sample, row_names, column_names)[0] for sample in samples]
    rows = tuple(str(name) for name in row_names)
    columns = tuple(str(name) for name in column_names)
    worst_pair = (0, 1)
    worst_comparison = compare_jacobians(
        matrices[0], matrices[1], rows, columns
    )
    max_relative = worst_comparison.relative_frobenius_difference
    max_absolute = worst_comparison.max_abs_difference
    for left_index in range(len(matrices)):
        for right_index in range(left_index + 1, len(matrices)):
            comparison = compare_jacobians(
                matrices[left_index], matrices[right_index], rows, columns
            )
            max_relative = max(
                max_relative, comparison.relative_frobenius_difference
            )
            if comparison.max_abs_difference > max_absolute:
                max_absolute = comparison.max_abs_difference
                worst_pair = (left_index, right_index)
                worst_comparison = comparison
    return JacobianRepeatability(
        sample_count=len(matrices),
        row_count=int(matrices[0].shape[0]),
        column_count=int(matrices[0].shape[1]),
        max_abs_spread=float(max_absolute),
        max_relative_frobenius_difference=float(max_relative),
        worst_sample_pair=worst_pair,
        worst_row_index=worst_comparison.worst_row_index,
        worst_row_name=worst_comparison.worst_row_name,
        worst_column_index=worst_comparison.worst_column_index,
        worst_column_name=worst_comparison.worst_column_name,
    )


def relative_spectrum_change(
    left: Sequence[float], right: Sequence[float]
) -> float:
    """Return the largest elementwise relative singular-value change."""
    first = np.asarray(left, dtype=float).reshape((-1,))
    second = np.asarray(right, dtype=float).reshape((-1,))
    if (
        first.size == 0
        or first.shape != second.shape
        or np.any(~np.isfinite(first))
        or np.any(~np.isfinite(second))
    ):
        raise ValueError("singular-value spectra are invalid")
    denominator = np.maximum(np.abs(first), np.finfo(float).tiny)
    return float(np.max(np.abs(first - second) / denominator))


__all__ = [
    "JacobianComparison",
    "JacobianRepeatability",
    "compare_jacobians",
    "jacobian_repeatability",
    "relative_spectrum_change",
]
