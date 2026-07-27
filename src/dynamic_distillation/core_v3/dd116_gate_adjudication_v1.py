"""Static representation adjudication for the frozen DD-116 result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


REPLACEABLE_GATES = frozenset(("physical_reproduction",))


@dataclass(frozen=True)
class DD116GateAdjudication:
    source_failed_gates: tuple[str, ...]
    unexpected_source_failures: tuple[str, ...]
    physical_field_maximum: float
    pressure_field_maximum_psia: float
    temperature_field_maximum_F: float
    endpoint_inventory_reconstruction_maximum: float
    effective_rate_reconstruction_maximum: float
    coordinate_mismatch_reconstruction_maximum: float
    replacement_gates: Mapping[str, bool]
    final_gates: Mapping[str, bool]
    pass_gate: bool


def adjudicate_dd116_representation_gate(
    dd116_contract: Mapping[str, Any],
    dd116_result: Mapping[str, Any],
    dd115_contract: Mapping[str, Any],
    dd115_result: Mapping[str, Any],
) -> DD116GateAdjudication:
    if dd116_result.get("schema_id") != "dd116-core-v3-initializer-handoff-term-audit-result-v1":
        raise ValueError("DD-117 requires the frozen DD-116 result schema")
    source_gates = {str(key): bool(value) for key, value in dd116_result["gates"].items()}
    source_failed = tuple(sorted(key for key, value in source_gates.items() if not value))
    unexpected = tuple(sorted(set(source_failed) - REPLACEABLE_GATES))

    physical_fields = (
        "liquid_flow_reproduction",
        "vapor_flow_reproduction",
        "distillate_reproduction",
        "bottoms_reproduction",
        "condenser_duty_reproduction",
    )
    physical_maximum = max(
        snapshot["metrics"][field]
        for snapshot in dd116_result["snapshots"].values()
        for field in physical_fields
    )
    pressure_maximum = max(
        snapshot["metrics"]["pressure_reproduction_psia"]
        for snapshot in dd116_result["snapshots"].values()
    )
    temperature_maximum = max(
        snapshot["metrics"]["temperature_reproduction_F"]
        for snapshot in dd116_result["snapshots"].values()
    )

    rate_scale = float(dd116_contract["material_rate_scale_lbmolph"])
    previous_inventory = np.asarray(dd115_contract["previous_inventory_lbmol"], dtype=float)
    inventory_error = 0.0
    rate_error = 0.0
    mismatch_error = 0.0
    for outcome_name, snapshot_name in (("half1", "half_step"), ("half2", "refined_one_second")):
        outcome = dd115_result["outcomes"][outcome_name]
        step_hours = 0.5 / 3600.0
        nominal_rate = (
            np.asarray(outcome["final_coordinates"][: previous_inventory.size], dtype=float)
            .reshape(previous_inventory.shape)
            * rate_scale
        )
        reconstructed_inventory = previous_inventory * np.exp(
            step_hours * nominal_rate / previous_inventory
        )
        saved_inventory = np.asarray(outcome["inventory_lbmol"], dtype=float)
        reconstructed_rate = (reconstructed_inventory - previous_inventory) / step_hours
        saved_rate = np.asarray(outcome["component_rate_lbmolph"], dtype=float)
        direct_coordinate_mismatch = float(np.max(np.abs(nominal_rate - saved_rate)) / rate_scale)
        reported_coordinate_mismatch = float(
            dd116_result["snapshots"][snapshot_name]["metrics"]["component_coordinate_reproduction"]
        )
        inventory_error = max(
            inventory_error,
            float(
                np.max(
                    np.abs(reconstructed_inventory - saved_inventory)
                    / np.maximum(np.abs(saved_inventory), 1.0)
                )
            ),
        )
        rate_error = max(
            rate_error,
            float(np.max(np.abs(reconstructed_rate - saved_rate)) / rate_scale),
        )
        mismatch_error = max(
            mismatch_error,
            abs(direct_coordinate_mismatch - reported_coordinate_mismatch),
        )
        previous_inventory = saved_inventory

    replacement = {
        "physical_reproduction": bool(
            physical_maximum < dd116_contract["physical_reproduction_limit"]
            and pressure_maximum < dd116_contract["pressure_reproduction_limit_psia"]
            and temperature_maximum < dd116_contract["temperature_reproduction_limit_F"]
            and inventory_error < 1.0e-12
            and rate_error < 1.0e-12
            and mismatch_error < 1.0e-12
        ),
        "nominal_effective_rate_representation_proven": bool(
            inventory_error < 1.0e-12
            and rate_error < 1.0e-12
            and mismatch_error < 1.0e-12
        ),
    }
    final = dict(source_gates)
    final["physical_reproduction"] = replacement["physical_reproduction"]
    final["nominal_effective_rate_representation_proven"] = replacement[
        "nominal_effective_rate_representation_proven"
    ]
    passed = not unexpected and all(final.values())
    return DD116GateAdjudication(
        source_failed_gates=source_failed,
        unexpected_source_failures=unexpected,
        physical_field_maximum=float(physical_maximum),
        pressure_field_maximum_psia=float(pressure_maximum),
        temperature_field_maximum_F=float(temperature_maximum),
        endpoint_inventory_reconstruction_maximum=float(inventory_error),
        effective_rate_reconstruction_maximum=float(rate_error),
        coordinate_mismatch_reconstruction_maximum=float(mismatch_error),
        replacement_gates=replacement,
        final_gates=final,
        pass_gate=bool(passed),
    )


__all__ = [
    "DD116GateAdjudication",
    "REPLACEABLE_GATES",
    "adjudicate_dd116_representation_gate",
]
