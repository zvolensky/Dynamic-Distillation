"""Static applicability adjudication for the frozen DD-109 result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
)


REPLACEABLE_GATES = frozenset(
    ("finite_physical_state", "positive_pressure_and_geometry_terms")
)


@dataclass(frozen=True)
class DD109GateAdjudication:
    source_failed_gates: tuple[str, ...]
    unexpected_source_failures: tuple[str, ...]
    applicable_volume_indices: tuple[int, ...]
    terminal_sentinel_indices: tuple[int, ...]
    liquid_head_link_mask: tuple[bool, ...]
    replacement_gates: Mapping[str, bool]
    final_gates: Mapping[str, bool]
    pass_gate: bool


def _array(record: Mapping[str, Any], key: str) -> np.ndarray:
    return np.asarray(record[key], dtype=float)


def adjudicate_dd109_physical_gates(
    result: Mapping[str, Any],
    pressure_link_geometry: Sequence[Mapping[str, Any]],
) -> DD109GateAdjudication:
    if result.get("schema_id") != "dd109-core-v3-conserved-nu-pressure-numerical-result-v1":
        raise ValueError("DD-110 requires the frozen DD-109 result schema")
    source_gates = {str(key): bool(value) for key, value in result["gates"].items()}
    source_failed = tuple(sorted(key for key, value in source_gates.items() if not value))
    unexpected = tuple(sorted(set(source_failed) - REPLACEABLE_GATES))
    if not REPLACEABLE_GATES.issubset(source_gates):
        raise ValueError("DD-109 result lacks the replaceable physical gates")

    applicable = tuple(VOLUME_IDS.index(volume) for volume in HYDRAULIC_VOLUME_IDS)
    terminal = tuple(index for index in range(len(VOLUME_IDS)) if index not in applicable)
    link_mask = tuple(bool(item["include_liquid_head"]) for item in pressure_link_geometry)
    if len(link_mask) != len(VOLUME_IDS) - 1:
        raise ValueError("DD-110 pressure-link geometry is incomplete")
    applicable_index = np.asarray(applicable, dtype=int)
    terminal_index = np.asarray(terminal, dtype=int)
    link_index = np.asarray(link_mask, dtype=bool)

    finite_common_fields = (
        "pressure_psia",
        "temperature_F",
        "liquid_moles_lbmol",
        "liquid_mole_fraction",
        "vapor_mole_fraction",
        "hydraulic_liquid_flow_lbmolph",
        "vapor_flow_lbmolph",
        "liquid_density_lbmol_ft3",
        "over_weir_head_ft",
        "liquid_head_drop_psia",
        "dry_tray_drop_psia",
        "vapor_compressibility_factor",
        "live_internal_energy_BTU",
    )
    finite_applicable = True
    positive_geometry = True
    terminal_sentinels = True
    for record in result["states"]:
        heights = _array(record, "liquid_height_ft")
        liquid_head = _array(record, "liquid_head_drop_psia")
        over_weir = _array(record, "over_weir_head_ft")
        finite_applicable &= (
            all(np.all(np.isfinite(_array(record, field))) for field in finite_common_fields)
            and np.all(np.isfinite(heights[applicable_index]))
            and np.isfinite(float(record["distillate_lbmolph"]))
            and np.isfinite(float(record["bottoms_lbmolph"]))
            and np.isfinite(float(record["condenser_duty_BTUph"]))
        )
        terminal_sentinels &= bool(np.all(np.isnan(heights[terminal_index])))
        positive_geometry &= bool(
            np.all(_array(record, "liquid_density_lbmol_ft3") > 0.0)
            and np.all(heights[applicable_index] > 0.0)
            and np.all(over_weir[link_index] > 0.0)
            and np.all(liquid_head[link_index] > 0.0)
            and np.all(np.abs(liquid_head[~link_index]) <= 1.0e-14)
            and np.all(_array(record, "dry_tray_drop_psia") > 0.0)
            and np.all(_array(record, "vapor_compressibility_factor") > 0.0)
        )

    replacement = {
        "finite_physical_state": bool(finite_applicable),
        "positive_pressure_and_geometry_terms": bool(positive_geometry),
        "terminal_height_sentinels": bool(terminal_sentinels),
    }
    final = dict(source_gates)
    final.update(replacement)
    passed = not unexpected and all(final.values())
    return DD109GateAdjudication(
        source_failed_gates=source_failed,
        unexpected_source_failures=unexpected,
        applicable_volume_indices=applicable,
        terminal_sentinel_indices=terminal,
        liquid_head_link_mask=link_mask,
        replacement_gates=replacement,
        final_gates=final,
        pass_gate=bool(passed),
    )


__all__ = [
    "DD109GateAdjudication",
    "REPLACEABLE_GATES",
    "adjudicate_dd109_physical_gates",
]
