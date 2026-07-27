"""Static physical-equivalence adjudication for the frozen DD-112 endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    VOLUME_IDS,
)


REPLACEABLE_GATES = frozenset(("common_solution",))


@dataclass(frozen=True)
class DD112PhysicalEquivalenceAdjudication:
    source_failed_gates: tuple[str, ...]
    unexpected_source_failures: tuple[str, ...]
    metrics: Mapping[str, float]
    limits: Mapping[str, float]
    metric_gates: Mapping[str, bool]
    preserved_gates: Mapping[str, bool]
    compositions_physical: bool
    canonical_start: str
    pass_gate: bool


def _array(record: Mapping[str, Any], key: str) -> np.ndarray:
    value = np.asarray(record[key], dtype=float)
    if np.any(~np.isfinite(value)):
        raise ValueError(f"DD-113 requires finite {key}")
    return value


def _max_scaled_difference(
    left: Sequence[float], right: Sequence[float], scale: Sequence[float] | float
) -> float:
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    scale_array = np.asarray(scale, dtype=float)
    if left_array.shape != right_array.shape or np.any(scale_array <= 0.0):
        raise ValueError("DD-113 comparison shape or scale is invalid")
    return float(np.max(np.abs(left_array - right_array) / scale_array))


def _composition_from_offset(
    reference: Sequence[float], offset: Sequence[float]
) -> np.ndarray:
    reference_array = np.asarray(reference, dtype=float)
    offset_array = np.asarray(offset, dtype=float)
    if (
        reference_array.ndim != 1
        or offset_array.shape != (reference_array.size - 1,)
        or np.any(reference_array <= 0.0)
        or not np.isclose(np.sum(reference_array), 1.0, atol=1.0e-10)
    ):
        raise ValueError("DD-113 composition reference or offset is invalid")
    alr = np.log(reference_array[:-1] / reference_array[-1]) + offset_array
    logits = np.concatenate((alr, np.zeros(1, dtype=float)))
    weights = np.exp(logits - np.max(logits))
    return weights / np.sum(weights)


def _coordinate_values(
    record: Mapping[str, Any], names: Sequence[str], selected: Sequence[str]
) -> np.ndarray:
    coordinates = _array(record, "final_coordinates")
    if coordinates.shape != (len(names),):
        raise ValueError("DD-113 coordinate ledger is incomplete")
    lookup = {name: coordinates[index] for index, name in enumerate(names)}
    try:
        return np.asarray([lookup[name] for name in selected], dtype=float)
    except KeyError as exc:
        raise ValueError(f"DD-113 missing coordinate {exc.args[0]}") from exc


def _vapor_compositions(
    record: Mapping[str, Any], contract: Mapping[str, Any]
) -> tuple[np.ndarray, np.ndarray]:
    components = tuple(str(item) for item in contract["source_mapping"]["component_names"])
    names = tuple(str(item) for item in contract["variable_names"])
    reference = contract["reference"]
    vapor_rows = []
    for volume, row in zip(
        EQUILIBRIUM_VOLUME_IDS, reference["vapor_mole_fraction"], strict=True
    ):
        selected = tuple(f"y[{volume},{component}]" for component in components[:-1])
        vapor_rows.append(
            _composition_from_offset(row, _coordinate_values(record, names, selected))
        )
    bubble_selected = tuple(
        f"y_bubble[reflux_drum,{component}]" for component in components[:-1]
    )
    bubble = _composition_from_offset(
        reference["bubble_vapor_mole_fraction"],
        _coordinate_values(record, names, bubble_selected),
    )
    return np.asarray(vapor_rows), bubble


def adjudicate_dd112_physical_equivalence(
    result: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    limits: Mapping[str, float],
    material_rate_scale_lbmolph: float,
    energy_rate_scale_BTUph: float,
    pressure_scale_psia: float,
) -> DD112PhysicalEquivalenceAdjudication:
    if result.get("schema_id") != "dd112-core-v3-conserved-nu-pressure-initializer-result-v1":
        raise ValueError("DD-113 requires the frozen DD-112 result schema")
    if contract.get("schema_id") != "dd112-core-v3-conserved-nu-pressure-initializer-contract-v1":
        raise ValueError("DD-113 requires the frozen DD-112 contract schema")
    starts = result.get("starts", ())
    if len(starts) != 2:
        raise ValueError("DD-113 requires exactly two DD-112 endpoints")
    if min(material_rate_scale_lbmolph, energy_rate_scale_BTUph, pressure_scale_psia) <= 0.0:
        raise ValueError("DD-113 physical scales must be positive")

    source_gates = {str(key): bool(value) for key, value in result["gates"].items()}
    source_failed = tuple(sorted(key for key, value in source_gates.items() if not value))
    unexpected = tuple(sorted(set(source_failed) - REPLACEABLE_GATES))
    if not REPLACEABLE_GATES.issubset(source_gates):
        raise ValueError("DD-112 result lacks the replaceable common-solution gate")
    preserved = {
        key: value for key, value in source_gates.items() if key not in REPLACEABLE_GATES
    }

    left, right = starts
    inventory_reference = np.asarray(contract["inventory_reference_lbmol"], dtype=float)
    left_inventory = _array(left, "inventory_lbmol")
    right_inventory = _array(right, "inventory_lbmol")
    if left_inventory.shape != inventory_reference.shape or np.any(inventory_reference <= 0.0):
        raise ValueError("DD-113 inventory reference is invalid")
    left_x = left_inventory / np.sum(left_inventory, axis=1, keepdims=True)
    right_x = right_inventory / np.sum(right_inventory, axis=1, keepdims=True)
    left_y, left_bubble = _vapor_compositions(left, contract)
    right_y, right_bubble = _vapor_compositions(right, contract)

    metrics = {
        "objective_abs_difference": abs(float(left["final_objective"]) - float(right["final_objective"])),
        "inventory_scaled_difference": _max_scaled_difference(left_inventory, right_inventory, inventory_reference),
        "liquid_composition_abs_difference": float(np.max(np.abs(left_x - right_x))),
        "lower_internal_energy_scaled_difference": _max_scaled_difference(
            _array(left, "lower_internal_energy_BTU"),
            _array(right, "lower_internal_energy_BTU"),
            contract["lower_internal_energy_scale_BTU"],
        ),
        "component_rate_scaled_difference": _max_scaled_difference(
            _array(left, "component_rate_lbmolph"),
            _array(right, "component_rate_lbmolph"),
            material_rate_scale_lbmolph,
        ),
        "internal_energy_rate_scaled_difference": _max_scaled_difference(
            _array(left, "internal_energy_rate_BTUph"),
            _array(right, "internal_energy_rate_BTUph"),
            energy_rate_scale_BTUph,
        ),
        "pressure_scaled_difference": _max_scaled_difference(
            _array(left, "pressure_psia"), _array(right, "pressure_psia"), pressure_scale_psia
        ),
        "temperature_abs_difference_F": float(
            np.max(np.abs(_array(left, "temperature_F") - _array(right, "temperature_F")))
        ),
        "vapor_composition_abs_difference": float(np.max(np.abs(left_y - right_y))),
        "bubble_composition_abs_difference": float(np.max(np.abs(left_bubble - right_bubble))),
        "liquid_flow_scaled_difference": _max_scaled_difference(
            _array(left, "liquid_flow_lbmolph"),
            _array(right, "liquid_flow_lbmolph"),
            material_rate_scale_lbmolph,
        ),
        "vapor_flow_scaled_difference": _max_scaled_difference(
            _array(left, "vapor_flow_lbmolph"),
            _array(right, "vapor_flow_lbmolph"),
            material_rate_scale_lbmolph,
        ),
        "distillate_scaled_difference": abs(float(left["distillate_lbmolph"]) - float(right["distillate_lbmolph"])) / material_rate_scale_lbmolph,
        "bottoms_scaled_difference": abs(float(left["bottoms_lbmolph"]) - float(right["bottoms_lbmolph"])) / material_rate_scale_lbmolph,
        "condenser_duty_scaled_difference": abs(float(left["condenser_duty_BTUph"]) - float(right["condenser_duty_BTUph"])) / energy_rate_scale_BTUph,
    }
    if set(metrics) != set(limits):
        raise ValueError("DD-113 metric limits do not match the physical ledger")
    metric_gates = {key: value < float(limits[key]) for key, value in metrics.items()}
    compositions = (left_x, right_x, left_y, right_y, left_bubble, right_bubble)
    compositions_physical = all(
        np.all(value > 0.0) and np.allclose(np.sum(value, axis=-1), 1.0, atol=1.0e-12)
        for value in compositions
    )
    canonical = min(
        starts,
        key=lambda item: (float(item["final_objective"]), str(item["name"])),
    )["name"]
    passed = (
        source_failed == ("common_solution",)
        and not unexpected
        and all(preserved.values())
        and all(metric_gates.values())
        and compositions_physical
    )
    return DD112PhysicalEquivalenceAdjudication(
        source_failed_gates=source_failed,
        unexpected_source_failures=unexpected,
        metrics=metrics,
        limits={key: float(value) for key, value in limits.items()},
        metric_gates=metric_gates,
        preserved_gates=preserved,
        compositions_physical=bool(compositions_physical),
        canonical_start=str(canonical),
        pass_gate=bool(passed),
    )


__all__ = [
    "DD112PhysicalEquivalenceAdjudication",
    "REPLACEABLE_GATES",
    "adjudicate_dd112_physical_equivalence",
]
