"""Static physical-equivalence adjudication for DD-130 and DD-132 endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    VOLUME_IDS,
)


DD130_REPLACEABLE_GATES = frozenset(("calls",))
DD132_REPLACEABLE_GATES = frozenset(("endpoint_reproduction",))
OUTCOME_NAMES = ("coarse", "half1", "half2")


@dataclass(frozen=True)
class DD132PhysicalEquivalenceAdjudication:
    dd130_failed_gates: tuple[str, ...]
    dd132_failed_gates: tuple[str, ...]
    unexpected_dd130_failures: tuple[str, ...]
    unexpected_dd132_failures: tuple[str, ...]
    metrics: Mapping[str, Mapping[str, float]]
    limits: Mapping[str, float]
    metric_gates: Mapping[str, Mapping[str, bool]]
    preserved_dd130_gates: Mapping[str, bool]
    preserved_dd132_gates: Mapping[str, bool]
    decoded_states_physical: bool
    stored_products_match_coordinates: bool
    pass_gate: bool


def _array(record: Mapping[str, Any], key: str) -> np.ndarray:
    value = np.asarray(record[key], dtype=float)
    if np.any(~np.isfinite(value)):
        raise ValueError(f"DD-133 requires finite {key}")
    return value


def _max_scaled_difference(
    left: Sequence[float], right: Sequence[float], scale: Sequence[float] | float
) -> float:
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    scale_array = np.asarray(scale, dtype=float)
    if left_array.shape != right_array.shape or np.any(scale_array <= 0.0):
        raise ValueError("DD-133 comparison shape or scale is invalid")
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
        raise ValueError("DD-133 composition reference or offset is invalid")
    alr = np.log(reference_array[:-1] / reference_array[-1]) + offset_array
    logits = np.concatenate((alr, np.zeros(1, dtype=float)))
    weights = np.exp(logits - np.max(logits))
    return weights / np.sum(weights)


def _coordinate_lookup(
    contract: Mapping[str, Any], outcome: Mapping[str, Any]
) -> dict[str, float]:
    names = tuple(str(item) for item in contract["variable_names"])
    values = _array(outcome, "final_coordinates").reshape((-1,))
    if values.shape != (len(names),) or len(set(names)) != len(names):
        raise ValueError("DD-133 coordinate ledger is incomplete")
    return dict(zip(names, values, strict=True))


def _selected(
    lookup: Mapping[str, float], names: Sequence[str]
) -> np.ndarray:
    try:
        return np.asarray([lookup[name] for name in names], dtype=float)
    except KeyError as exc:
        raise ValueError(f"DD-133 missing coordinate {exc.args[0]}") from exc


def _decoded_state(
    contract: Mapping[str, Any], outcome: Mapping[str, Any]
) -> dict[str, np.ndarray | float]:
    components = tuple(str(item) for item in contract["source_mapping"]["component_names"])
    reference = contract["reference"]
    lookup = _coordinate_lookup(contract, outcome)
    inventory = _array(outcome, "inventory_lbmol")
    expected_inventory_shape = (len(VOLUME_IDS), len(components))
    if inventory.shape != expected_inventory_shape or np.any(inventory <= 0.0):
        raise ValueError("DD-133 inventory ledger is invalid")
    liquid_moles = np.sum(inventory, axis=1)
    liquid_x = inventory / liquid_moles[:, None]

    temperature_coordinates = _selected(
        lookup, tuple(f"T[{volume}]" for volume in VOLUME_IDS)
    )
    temperature = (
        np.asarray(reference["temperature_F"], dtype=float)
        + float(contract["operating_spec"]["temperature_scale_F"])
        * temperature_coordinates
    )

    vapor_y = []
    for volume, row in zip(
        EQUILIBRIUM_VOLUME_IDS, reference["vapor_mole_fraction"], strict=True
    ):
        offsets = _selected(
            lookup,
            tuple(f"y[{volume},{component}]" for component in components[:-1]),
        )
        vapor_y.append(_composition_from_offset(row, offsets))

    liquid_names = tuple(
        name for name in contract["variable_names"] if str(name).startswith("L[")
    )
    vapor_names = tuple(
        name for name in contract["variable_names"] if str(name).startswith("V[")
    )
    liquid_flow = np.asarray(reference["hydraulic_liquid_flow_lbmolph"], dtype=float)
    vapor_flow = np.asarray(reference["vapor_flow_lbmolph"], dtype=float)
    if len(liquid_names) != liquid_flow.size or len(vapor_names) != vapor_flow.size:
        raise ValueError("DD-133 flow coordinate ledger is invalid")
    liquid_flow = liquid_flow * np.exp(_selected(lookup, liquid_names))
    vapor_flow = vapor_flow * np.exp(_selected(lookup, vapor_names))

    bubble_y = _composition_from_offset(
        reference["bubble_vapor_mole_fraction"],
        _selected(
            lookup,
            tuple(
                f"y_bubble[reflux_drum,{component}]"
                for component in components[:-1]
            ),
        ),
    )
    pressure = np.asarray(contract["pressure_reference_psia"], dtype=float).copy()
    pressure[1:] += float(contract["pressure_coordinate_scale_psia"]) * _selected(
        lookup, tuple(f"P[{volume}]" for volume in VOLUME_IDS[1:])
    )
    distillate = float(contract["accepted_root_state"]["distillate_lbmolph"]) * float(
        np.exp(lookup["log_D_level_output"])
    )
    bottoms = float(contract["accepted_root_state"]["bottoms_lbmolph"]) * float(
        np.exp(lookup["log_B_level_output"])
    )
    condenser_duty = float(reference["condenser_duty_reference_BTUph"]) + float(
        reference["condenser_duty_scale_BTUph"]
    ) * float(lookup["Q_C"])

    return {
        "inventory_lbmol": inventory,
        "liquid_moles_lbmol": liquid_moles,
        "liquid_mole_fraction": liquid_x,
        "temperature_F": temperature,
        "vapor_mole_fraction": np.asarray(vapor_y),
        "hydraulic_liquid_flow_lbmolph": liquid_flow,
        "vapor_flow_lbmolph": vapor_flow,
        "bubble_vapor_mole_fraction": bubble_y,
        "pressure_psia": pressure,
        "distillate_lbmolph": distillate,
        "bottoms_lbmolph": bottoms,
        "condenser_duty_BTUph": condenser_duty,
        "top_internal_energy_BTU": float(outcome["top_internal_energy_BTU"]),
        "lower_internal_energy_BTU": _array(outcome, "lower_internal_energy_BTU"),
        "controller_memory": _array(outcome, "controller_memory"),
        "level_fraction": _array(outcome, "level_fraction"),
    }


def _physical(state: Mapping[str, np.ndarray | float]) -> bool:
    arrays = tuple(np.asarray(value, dtype=float) for value in state.values())
    compositions = (
        np.asarray(state["liquid_mole_fraction"]),
        np.asarray(state["vapor_mole_fraction"]),
        np.asarray(state["bubble_vapor_mole_fraction"]),
    )
    return bool(
        all(np.all(np.isfinite(value)) for value in arrays)
        and np.all(np.asarray(state["inventory_lbmol"]) > 0.0)
        and all(
            np.all(value > 0.0)
            and np.allclose(np.sum(value, axis=-1), 1.0, atol=1.0e-12)
            for value in compositions
        )
        and np.all(np.asarray(state["hydraulic_liquid_flow_lbmolph"]) > 0.0)
        and np.all(np.asarray(state["vapor_flow_lbmolph"]) > 0.0)
        and float(state["distillate_lbmolph"]) > 0.0
        and float(state["bottoms_lbmolph"]) > 0.0
        and float(state["condenser_duty_BTUph"]) < 0.0
        and np.all(np.asarray(state["pressure_psia"]) > 0.0)
        and np.all(np.diff(np.asarray(state["pressure_psia"])) > 0.0)
        and np.all((np.asarray(state["level_fraction"]) > 0.0) & (np.asarray(state["level_fraction"]) < 1.0))
    )


def _outcome_metrics(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    contract: Mapping[str, Any],
    name: str,
    left_previous: Mapping[str, Any] | None,
    right_previous: Mapping[str, Any] | None,
) -> tuple[dict[str, float], bool, bool]:
    left_state = _decoded_state(contract, left)
    right_state = _decoded_state(contract, right)
    reference = contract["reference"]
    inventory_scale = np.maximum(
        np.abs(np.asarray(left_state["inventory_lbmol"], dtype=float)), 1.0
    )
    lower_energy_scale = np.maximum(
        np.abs(np.asarray(left_state["lower_internal_energy_BTU"], dtype=float)), 1.0
    )
    material_scale = float(contract["component_rate_scale_lbmolph"])
    energy_scales = np.asarray(contract["energy_rate_scales_BTUph"], dtype=float)
    duty_scale = float(reference["condenser_duty_scale_BTUph"])

    left_lookup = _coordinate_lookup(contract, left)
    right_lookup = _coordinate_lookup(contract, right)
    energy_rate_names = tuple(
        item for item in contract["variable_names"] if str(item).startswith("dU[")
    )
    controller_rate_names = tuple(
        item
        for item in contract["variable_names"]
        if str(item).startswith("dI_level[")
    )
    if len(energy_rate_names) != energy_scales.size or len(controller_rate_names) != 2:
        raise ValueError("DD-133 rate coordinate ledger is invalid")

    if name == "half2":
        if left_previous is None or right_previous is None:
            raise ValueError("DD-133 half2 requires the half1 endpoint")
        left_previous_inventory = _array(left_previous, "inventory_lbmol")
        right_previous_inventory = _array(right_previous, "inventory_lbmol")
    else:
        left_previous_inventory = np.asarray(contract["inventory_lbmol"], dtype=float)
        right_previous_inventory = left_previous_inventory
    step_hours = (1.0 if name == "coarse" else 0.5) / 3600.0
    left_component_rate = (
        np.asarray(left_state["inventory_lbmol"]) - left_previous_inventory
    ) / step_hours
    right_component_rate = (
        np.asarray(right_state["inventory_lbmol"]) - right_previous_inventory
    ) / step_hours

    metrics = {
        "inventory_relative_difference": _max_scaled_difference(
            left_state["inventory_lbmol"], right_state["inventory_lbmol"], inventory_scale
        ),
        "liquid_holdup_relative_difference": _max_scaled_difference(
            left_state["liquid_moles_lbmol"],
            right_state["liquid_moles_lbmol"],
            np.maximum(np.abs(np.asarray(left_state["liquid_moles_lbmol"])), 1.0),
        ),
        "liquid_composition_abs_difference": float(
            np.max(
                np.abs(
                    np.asarray(left_state["liquid_mole_fraction"])
                    - np.asarray(right_state["liquid_mole_fraction"])
                )
            )
        ),
        "component_rate_scaled_difference": _max_scaled_difference(
            left_component_rate, right_component_rate, material_scale
        ),
        "top_internal_energy_relative_difference": abs(
            float(left_state["top_internal_energy_BTU"])
            - float(right_state["top_internal_energy_BTU"])
        ) / max(abs(float(left_state["top_internal_energy_BTU"])), 1.0),
        "lower_internal_energy_relative_difference": _max_scaled_difference(
            left_state["lower_internal_energy_BTU"],
            right_state["lower_internal_energy_BTU"],
            lower_energy_scale,
        ),
        "lower_energy_rate_scaled_difference": _max_scaled_difference(
            _selected(left_lookup, energy_rate_names) * energy_scales,
            _selected(right_lookup, energy_rate_names) * energy_scales,
            energy_scales,
        ),
        "controller_memory_abs_difference": float(
            np.max(
                np.abs(
                    np.asarray(left_state["controller_memory"])
                    - np.asarray(right_state["controller_memory"])
                )
            )
        ),
        "controller_rate_abs_difference_per_sec": float(
            np.max(
                np.abs(
                    _selected(left_lookup, controller_rate_names)
                    - _selected(right_lookup, controller_rate_names)
                )
            )
        ),
        "level_fraction_abs_difference": float(
            np.max(
                np.abs(
                    np.asarray(left_state["level_fraction"])
                    - np.asarray(right_state["level_fraction"])
                )
            )
        ),
        "temperature_abs_difference_F": float(
            np.max(
                np.abs(
                    np.asarray(left_state["temperature_F"])
                    - np.asarray(right_state["temperature_F"])
                )
            )
        ),
        "vapor_composition_abs_difference": float(
            np.max(
                np.abs(
                    np.asarray(left_state["vapor_mole_fraction"])
                    - np.asarray(right_state["vapor_mole_fraction"])
                )
            )
        ),
        "liquid_flow_relative_difference": _max_scaled_difference(
            left_state["hydraulic_liquid_flow_lbmolph"],
            right_state["hydraulic_liquid_flow_lbmolph"],
            np.asarray(left_state["hydraulic_liquid_flow_lbmolph"]),
        ),
        "vapor_flow_relative_difference": _max_scaled_difference(
            left_state["vapor_flow_lbmolph"],
            right_state["vapor_flow_lbmolph"],
            np.asarray(left_state["vapor_flow_lbmolph"]),
        ),
        "bubble_composition_abs_difference": float(
            np.max(
                np.abs(
                    np.asarray(left_state["bubble_vapor_mole_fraction"])
                    - np.asarray(right_state["bubble_vapor_mole_fraction"])
                )
            )
        ),
        "pressure_abs_difference_psia": float(
            np.max(
                np.abs(
                    np.asarray(left_state["pressure_psia"])
                    - np.asarray(right_state["pressure_psia"])
                )
            )
        ),
        "distillate_relative_difference": abs(
            float(left_state["distillate_lbmolph"])
            - float(right_state["distillate_lbmolph"])
        ) / float(left_state["distillate_lbmolph"]),
        "bottoms_relative_difference": abs(
            float(left_state["bottoms_lbmolph"])
            - float(right_state["bottoms_lbmolph"])
        ) / float(left_state["bottoms_lbmolph"]),
        "condenser_duty_scaled_difference": abs(
            float(left_state["condenser_duty_BTUph"])
            - float(right_state["condenser_duty_BTUph"])
        ) / duty_scale,
    }
    product_match = all(
        abs(float(state[key]) - float(outcome[stored_key]))
        / max(abs(float(outcome[stored_key])), 1.0)
        < 1.0e-12
        for state, outcome in ((left_state, left), (right_state, right))
        for key, stored_key in (
            ("distillate_lbmolph", "distillate_lbmolph"),
            ("bottoms_lbmolph", "bottoms_lbmolph"),
        )
    )
    return metrics, _physical(left_state) and _physical(right_state), product_match


def adjudicate_dd132_physical_equivalence(
    dd130_result: Mapping[str, Any],
    dd132_result: Mapping[str, Any],
    dd130_contract: Mapping[str, Any],
    *,
    limits: Mapping[str, float],
) -> DD132PhysicalEquivalenceAdjudication:
    if dd130_result.get("schema_id") != "dd130-core-v3-controlled-terminal-moving-step-jsonfix-result-v1":
        raise ValueError("DD-133 requires the frozen DD-130 result schema")
    if dd132_result.get("schema_id") != "dd132-core-v3-modified-newton-live-efficiency-result-v1":
        raise ValueError("DD-133 requires the frozen DD-132 result schema")
    if dd130_contract.get("schema_id") != "dd130-core-v3-controlled-terminal-moving-step-jsonfix-contract-v1":
        raise ValueError("DD-133 requires the frozen DD-130 contract schema")
    if tuple(dd130_result.get("outcomes", {}).keys()) != OUTCOME_NAMES:
        raise ValueError("DD-133 requires the three ordered DD-130 outcomes")
    if tuple(dd132_result.get("outcomes", {}).keys()) != OUTCOME_NAMES:
        raise ValueError("DD-133 requires the three ordered DD-132 outcomes")

    dd130_gates = {str(key): bool(value) for key, value in dd130_result["gates"].items()}
    dd132_gates = {str(key): bool(value) for key, value in dd132_result["gates"].items()}
    dd130_failed = tuple(sorted(key for key, value in dd130_gates.items() if not value))
    dd132_failed = tuple(sorted(key for key, value in dd132_gates.items() if not value))
    unexpected_dd130 = tuple(sorted(set(dd130_failed) - DD130_REPLACEABLE_GATES))
    unexpected_dd132 = tuple(sorted(set(dd132_failed) - DD132_REPLACEABLE_GATES))
    preserved_dd130 = {
        key: value for key, value in dd130_gates.items() if key not in DD130_REPLACEABLE_GATES
    }
    preserved_dd132 = {
        key: value for key, value in dd132_gates.items() if key not in DD132_REPLACEABLE_GATES
    }

    metrics: dict[str, Mapping[str, float]] = {}
    metric_gates: dict[str, Mapping[str, bool]] = {}
    physical = True
    product_match = True
    for name in OUTCOME_NAMES:
        left_previous = dd130_result["outcomes"].get("half1") if name == "half2" else None
        right_previous = dd132_result["outcomes"].get("half1") if name == "half2" else None
        values, endpoint_physical, endpoint_product_match = _outcome_metrics(
            dd130_result["outcomes"][name],
            dd132_result["outcomes"][name],
            dd130_contract,
            name,
            left_previous,
            right_previous,
        )
        if set(values) != set(limits):
            raise ValueError("DD-133 metric limits do not match the physical ledger")
        metrics[name] = values
        metric_gates[name] = {
            key: value < float(limits[key]) for key, value in values.items()
        }
        physical = physical and endpoint_physical
        product_match = product_match and endpoint_product_match

    passed = (
        dd130_failed == ("calls",)
        and dd132_failed == ("endpoint_reproduction",)
        and not unexpected_dd130
        and not unexpected_dd132
        and all(preserved_dd130.values())
        and all(preserved_dd132.values())
        and all(all(gates.values()) for gates in metric_gates.values())
        and physical
        and product_match
    )
    return DD132PhysicalEquivalenceAdjudication(
        dd130_failed_gates=dd130_failed,
        dd132_failed_gates=dd132_failed,
        unexpected_dd130_failures=unexpected_dd130,
        unexpected_dd132_failures=unexpected_dd132,
        metrics=metrics,
        limits={key: float(value) for key, value in limits.items()},
        metric_gates=metric_gates,
        preserved_dd130_gates=preserved_dd130,
        preserved_dd132_gates=preserved_dd132,
        decoded_states_physical=bool(physical),
        stored_products_match_coordinates=bool(product_match),
        pass_gate=bool(passed),
    )


__all__ = [
    "DD130_REPLACEABLE_GATES",
    "DD132PhysicalEquivalenceAdjudication",
    "DD132_REPLACEABLE_GATES",
    "OUTCOME_NAMES",
    "adjudicate_dd132_physical_equivalence",
]
