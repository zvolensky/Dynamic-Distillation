"""Generic prescribed-pressure row replacement for Core V3 stationary audits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .vapor_holdup_stationary_residual_v1 import stationary_structural_pattern


PRESSURE_ROW_BLOCKS = frozenset(("vapor_pressure_drop", "pressure_anchor"))


@dataclass(frozen=True)
class PrescribedPressureStationaryEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    row_names: tuple[str, ...]
    pressure_target_residual_psia: np.ndarray
    base: Any


def _pressure_ledger(contract: Any) -> tuple[tuple[int, ...], tuple[int, ...]]:
    volumes = tuple(contract.topology.column.volume_ids)
    row_indices = tuple(
        index
        for index, row in enumerate(contract.rows)
        if str(row.block) in PRESSURE_ROW_BLOCKS
    )
    variable_names = tuple(str(variable.name) for variable in contract.variables)
    variable_indices = tuple(variable_names.index(f"P[{volume}]") for volume in volumes)
    if len(row_indices) != len(volumes) or len(set(variable_indices)) != len(volumes):
        raise ValueError("stationary pressure row/variable ledger is incomplete")
    return row_indices, variable_indices


def prescribed_pressure_structural_pattern(contract: Any) -> np.ndarray:
    """Return the stationary pattern with one target row per pressure variable."""
    pattern = stationary_structural_pattern(contract).copy()
    row_indices, variable_indices = _pressure_ledger(contract)
    for row_index, variable_index in zip(row_indices, variable_indices):
        pattern[row_index, :] = False
        pattern[row_index, variable_index] = True
    return pattern


def apply_prescribed_pressure_targets(
    contract: Any,
    base_evaluation: Any,
    target_pressure_psia: Sequence[float],
    *,
    residual_scale_psia: float,
) -> PrescribedPressureStationaryEvaluation:
    """Replace free-pressure rows without changing any other governing equation."""
    target = np.asarray(target_pressure_psia, dtype=float).reshape((-1,))
    volumes = tuple(contract.topology.column.volume_ids)
    pressure = np.asarray(base_evaluation.endpoint.pressure_psia, dtype=float)
    if (
        target.shape != (len(volumes),)
        or pressure.shape != target.shape
        or np.any(~np.isfinite(target))
        or np.any(target <= 0.0)
        or not np.isfinite(residual_scale_psia)
        or residual_scale_psia <= 0.0
    ):
        raise ValueError("prescribed pressure target or scale is invalid")
    raw = np.asarray(base_evaluation.raw, dtype=float).copy()
    scales = np.asarray(base_evaluation.scales, dtype=float).copy()
    row_names = list(base_evaluation.row_names)
    row_indices, _variable_indices = _pressure_ledger(contract)
    residual = pressure - target
    for volume_index, row_index in enumerate(row_indices):
        raw[row_index] = residual[volume_index]
        scales[row_index] = float(residual_scale_psia)
        row_names[row_index] = f"prescribed_pressure[{volumes[volume_index]}]"
    return PrescribedPressureStationaryEvaluation(
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        row_names=tuple(row_names),
        pressure_target_residual_psia=residual,
        base=base_evaluation,
    )


__all__ = [
    "PRESSURE_ROW_BLOCKS",
    "PrescribedPressureStationaryEvaluation",
    "apply_prescribed_pressure_targets",
    "prescribed_pressure_structural_pattern",
]
