"""Saved-endpoint comparison helpers for the Core V3 zero-time audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class SavedEndpointComparison:
    metrics: Mapping[str, float]
    limits: Mapping[str, float]
    gates: Mapping[str, bool]
    pass_gate: bool


def _array(record: Mapping[str, Any], key: str) -> np.ndarray:
    value = np.asarray(record[key], dtype=float)
    if np.any(~np.isfinite(value)):
        raise ValueError(f"DD-114 requires finite {key}")
    return value


def _scaled(
    left: Sequence[float], right: Sequence[float], scale: Sequence[float] | float
) -> float:
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    scale_array = np.asarray(scale, dtype=float)
    if left_array.shape != right_array.shape or np.any(scale_array <= 0.0):
        raise ValueError("DD-114 endpoint shape or scale is invalid")
    return float(np.max(np.abs(left_array - right_array) / scale_array))


def compare_saved_initializer_endpoint(
    saved: Mapping[str, Any],
    fresh: Mapping[str, Any],
    *,
    inventory_scale_lbmol: Sequence[Sequence[float]],
    lower_energy_scale_BTU: Sequence[float],
    material_rate_scale_lbmolph: float,
    energy_rate_scale_BTUph: float,
    pressure_scale_psia: float,
    limits: Mapping[str, float],
) -> SavedEndpointComparison:
    if min(material_rate_scale_lbmolph, energy_rate_scale_BTUph, pressure_scale_psia) <= 0.0:
        raise ValueError("DD-114 comparison scales must be positive")
    metrics = {
        "inventory_scaled_difference": _scaled(
            _array(saved, "inventory_lbmol"),
            _array(fresh, "inventory_lbmol"),
            inventory_scale_lbmol,
        ),
        "lower_internal_energy_scaled_difference": _scaled(
            _array(saved, "lower_internal_energy_BTU"),
            _array(fresh, "lower_internal_energy_BTU"),
            lower_energy_scale_BTU,
        ),
        "component_rate_scaled_difference": _scaled(
            _array(saved, "component_rate_lbmolph"),
            _array(fresh, "component_rate_lbmolph"),
            material_rate_scale_lbmolph,
        ),
        "internal_energy_rate_scaled_difference": _scaled(
            _array(saved, "internal_energy_rate_BTUph"),
            _array(fresh, "internal_energy_rate_BTUph"),
            energy_rate_scale_BTUph,
        ),
        "pressure_scaled_difference": _scaled(
            _array(saved, "pressure_psia"),
            _array(fresh, "pressure_psia"),
            pressure_scale_psia,
        ),
        "temperature_abs_difference_F": float(
            np.max(
                np.abs(
                    _array(saved, "temperature_F") - _array(fresh, "temperature_F")
                )
            )
        ),
        "liquid_flow_scaled_difference": _scaled(
            _array(saved, "liquid_flow_lbmolph"),
            _array(fresh, "liquid_flow_lbmolph"),
            material_rate_scale_lbmolph,
        ),
        "vapor_flow_scaled_difference": _scaled(
            _array(saved, "vapor_flow_lbmolph"),
            _array(fresh, "vapor_flow_lbmolph"),
            material_rate_scale_lbmolph,
        ),
        "distillate_scaled_difference": abs(
            float(saved["distillate_lbmolph"])
            - float(fresh["distillate_lbmolph"])
        )
        / material_rate_scale_lbmolph,
        "bottoms_scaled_difference": abs(
            float(saved["bottoms_lbmolph"]) - float(fresh["bottoms_lbmolph"])
        )
        / material_rate_scale_lbmolph,
        "condenser_duty_scaled_difference": abs(
            float(saved["condenser_duty_BTUph"])
            - float(fresh["condenser_duty_BTUph"])
        )
        / energy_rate_scale_BTUph,
    }
    if set(metrics) != set(limits):
        raise ValueError("DD-114 limits do not match the endpoint ledger")
    gates = {key: value < float(limits[key]) for key, value in metrics.items()}
    return SavedEndpointComparison(
        metrics=metrics,
        limits={key: float(value) for key, value in limits.items()},
        gates=gates,
        pass_gate=bool(all(gates.values())),
    )


__all__ = ["SavedEndpointComparison", "compare_saved_initializer_endpoint"]
