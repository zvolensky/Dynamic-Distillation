"""Property-free comparisons for repeated residual-vector evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class ResidualReplaySpread:
    sample_count: int
    row_count: int
    max_abs_spread: float
    worst_row_index: int
    worst_row_name: str
    worst_row_minimum: float
    worst_row_maximum: float


def residual_replay_spread(
    samples: Sequence[Sequence[float]],
    row_names: Sequence[str],
) -> ResidualReplaySpread:
    """Return the largest row-wise peak-to-peak spread across residual samples."""
    matrix = np.asarray(samples, dtype=float)
    names = tuple(str(name) for name in row_names)
    if (
        matrix.ndim != 2
        or matrix.shape[0] < 2
        or matrix.shape[1] == 0
        or matrix.shape[1] != len(names)
        or len(set(names)) != len(names)
        or np.any(~np.isfinite(matrix))
    ):
        raise ValueError("residual replay samples or row names are invalid")
    spread = np.ptp(matrix, axis=0)
    index = int(np.argmax(spread))
    return ResidualReplaySpread(
        sample_count=int(matrix.shape[0]),
        row_count=int(matrix.shape[1]),
        max_abs_spread=float(spread[index]),
        worst_row_index=index,
        worst_row_name=names[index],
        worst_row_minimum=float(np.min(matrix[:, index])),
        worst_row_maximum=float(np.max(matrix[:, index])),
    )


__all__ = ["ResidualReplaySpread", "residual_replay_spread"]
