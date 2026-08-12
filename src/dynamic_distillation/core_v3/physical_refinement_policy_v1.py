"""Physical-scale inventory refinement policy for Core V3 dynamics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class InventoryRefinementLimits:
    maximum_absolute_component_difference_lbmol: float
    maximum_state_relative_difference_with_1_lbmol_floor: float
    maximum_volume_holdup_relative_component_difference: float
    component_difference_l1_lbmol: float
    absolute_signed_total_inventory_difference_lbmol: float

    def __post_init__(self) -> None:
        values = np.asarray(tuple(self.__dict__.values()), dtype=float)
        if np.any(~np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError("inventory refinement limits must be finite and positive")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> InventoryRefinementLimits:
        return cls(
            maximum_absolute_component_difference_lbmol=float(
                values["maximum_absolute_component_difference_lbmol"]
            ),
            maximum_state_relative_difference_with_1_lbmol_floor=float(
                values["maximum_state_relative_difference_with_1_lbmol_floor"]
            ),
            maximum_volume_holdup_relative_component_difference=float(
                values["maximum_volume_holdup_relative_component_difference"]
            ),
            component_difference_l1_lbmol=float(
                values["component_difference_l1_lbmol"]
            ),
            absolute_signed_total_inventory_difference_lbmol=float(
                values["absolute_signed_total_inventory_difference_lbmol"]
            ),
        )


@dataclass(frozen=True)
class InventoryRefinementAssessment:
    metrics: Mapping[str, float | tuple[int, int]]
    gates: Mapping[str, bool]
    legacy_unfloored_relative_diagnostic: float
    pass_gate: bool


def _inventory_array(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or np.any(~np.isfinite(array)) or np.any(array <= 0.0):
        raise ValueError(f"{name} inventory must be a finite positive matrix")
    return array


def assess_inventory_refinement(
    initial_inventory_lbmol: Any,
    coarse_inventory_lbmol: Any,
    refined_inventory_lbmol: Any,
    limits: InventoryRefinementLimits,
) -> InventoryRefinementAssessment:
    """Assess same-horizon coarse/refined endpoints on physical inventory scales.

    The raw component-relative maximum is retained only as a diagnostic because
    dividing by a trace component can turn negligible absolute error into a
    campaign veto. Acceptance is based on declared physical scales instead.
    """

    initial = _inventory_array(initial_inventory_lbmol, "initial")
    coarse = _inventory_array(coarse_inventory_lbmol, "coarse")
    refined = _inventory_array(refined_inventory_lbmol, "refined")
    if coarse.shape != initial.shape or refined.shape != initial.shape:
        raise ValueError("inventory refinement matrices must have identical shapes")

    difference = coarse - refined
    absolute = np.abs(difference)
    state_scale = np.maximum(initial, 1.0)
    volume_scale = np.sum(initial, axis=1)[:, None]
    state_relative = absolute / state_scale
    volume_relative = absolute / volume_scale

    absolute_index = np.unravel_index(int(np.argmax(absolute)), absolute.shape)
    state_index = np.unravel_index(int(np.argmax(state_relative)), absolute.shape)
    volume_index = np.unravel_index(int(np.argmax(volume_relative)), absolute.shape)
    signed_total = float(np.sum(difference))
    metrics: dict[str, float | tuple[int, int]] = {
        "maximum_absolute_component_difference_lbmol": float(
            absolute[absolute_index]
        ),
        "maximum_absolute_component_index": tuple(int(item) for item in absolute_index),
        "maximum_state_relative_difference_with_1_lbmol_floor": float(
            state_relative[state_index]
        ),
        "maximum_state_relative_index": tuple(int(item) for item in state_index),
        "maximum_volume_holdup_relative_component_difference": float(
            volume_relative[volume_index]
        ),
        "maximum_volume_relative_index": tuple(int(item) for item in volume_index),
        "component_difference_l1_lbmol": float(np.sum(absolute)),
        "signed_total_inventory_difference_lbmol": signed_total,
        "absolute_signed_total_inventory_difference_lbmol": abs(signed_total),
    }
    gates = {
        "absolute_component": metrics[
            "maximum_absolute_component_difference_lbmol"
        ]
        < limits.maximum_absolute_component_difference_lbmol,
        "state_relative_with_floor": metrics[
            "maximum_state_relative_difference_with_1_lbmol_floor"
        ]
        < limits.maximum_state_relative_difference_with_1_lbmol_floor,
        "volume_holdup_relative": metrics[
            "maximum_volume_holdup_relative_component_difference"
        ]
        < limits.maximum_volume_holdup_relative_component_difference,
        "component_l1": metrics["component_difference_l1_lbmol"]
        < limits.component_difference_l1_lbmol,
        "signed_total": metrics[
            "absolute_signed_total_inventory_difference_lbmol"
        ]
        < limits.absolute_signed_total_inventory_difference_lbmol,
    }
    legacy_diagnostic = float(np.max(absolute / initial))
    return InventoryRefinementAssessment(
        metrics=metrics,
        gates=gates,
        legacy_unfloored_relative_diagnostic=legacy_diagnostic,
        pass_gate=all(gates.values()),
    )
