"""Physical volume mapping for the Core V3 vapor-holdup successor."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any, Mapping, Sequence

import numpy as np

from .provider_governed_registry_v1 import ColumnTopology


@dataclass(frozen=True)
class VaporControlVolumeGeometry:
    volume_id: str
    source_stage_1based: int
    geometry_kind: str
    gross_capacity_ft3: float
    fixed_vapor_extension_ft3: float
    liquid_displacement_active: bool
    provenance: str


@dataclass(frozen=True)
class VaporGeometryAudit:
    volume_count: int
    expected_volume_count: int
    volume_ids: tuple[str, ...]
    source_stages_1based: tuple[int, ...]
    missing_volume_ids: tuple[str, ...]
    duplicate_volume_ids: tuple[str, ...]
    invalid_source_stages: tuple[int, ...]
    nonpositive_capacities: tuple[str, ...]
    liquid_displacement_missing: tuple[str, ...]
    top_geometry_kind: str
    bottom_geometry_kind: str
    tray_volume_count: int
    terminal_volume_count: int
    pass_gate: bool


@dataclass(frozen=True)
class FreeVaporVolumeEvaluation:
    volume_ids: tuple[str, ...]
    gross_capacity_ft3: np.ndarray
    liquid_volume_ft3: np.ndarray
    free_vapor_volume_ft3: np.ndarray


def _required_positive(specs: Mapping[str, Any], key: str) -> float:
    value = specs.get(key)
    if value is None:
        raise ValueError(f"missing required geometry specification: {key}")
    number = float(value)
    if not np.isfinite(number) or number <= 0.0:
        raise ValueError(f"geometry specification must be positive: {key}")
    return number


def horizontal_drum_capacity_ft3(
    diameter_ft: float,
    tangent_length_ft: float,
) -> float:
    diameter = float(diameter_ft)
    length = float(tangent_length_ft)
    if (
        not np.isfinite(diameter)
        or not np.isfinite(length)
        or diameter <= 0.0
        or length <= 0.0
    ):
        raise ValueError("horizontal drum dimensions must be positive and finite")
    radius = 0.5 * diameter
    return pi * radius * radius * length + 4.0 * pi * radius**3 / 3.0


def vertical_cylinder_capacity_ft3(
    diameter_ft: float,
    height_ft: float,
) -> float:
    diameter = float(diameter_ft)
    height = float(height_ft)
    if (
        not np.isfinite(diameter)
        or not np.isfinite(height)
        or diameter <= 0.0
        or height <= 0.0
    ):
        raise ValueError("vertical vessel dimensions must be positive and finite")
    return 0.25 * pi * diameter * diameter * height


def build_column_vapor_geometry(
    column: Any,
    specs: Mapping[str, Any],
    topology: ColumnTopology,
) -> tuple[VaporControlVolumeGeometry, ...]:
    """Map workbook geometry to the generated column topology."""
    stage_count = int(column.n_stages)
    if stage_count != len(topology.volume_ids):
        raise ValueError("source stage count and generated topology do not match")
    source_geometry = getattr(column, "geometry", None)
    if source_geometry is None:
        raise ValueError("column has no declared stage geometry")
    area = np.asarray(source_geometry.area_ft2_per_stage, dtype=float)
    spacing = np.asarray(source_geometry.tray_spacing_ft_per_stage, dtype=float)
    declared_vapor = np.asarray(
        source_geometry.vapor_volume_ft3_per_stage,
        dtype=float,
    )
    expected_shape = (stage_count,)
    if (
        area.shape != expected_shape
        or spacing.shape != expected_shape
        or declared_vapor.shape != expected_shape
        or np.any(~np.isfinite(area))
        or np.any(~np.isfinite(spacing))
        or np.any(~np.isfinite(declared_vapor))
        or np.any(area <= 0.0)
        or np.any(spacing <= 0.0)
        or np.any(declared_vapor <= 0.0)
    ):
        raise ValueError("stage area, spacing, or declared vapor volume is invalid")

    top_total = specs.get("Top Drum Total Volume (ft3)")
    if top_total is None:
        top_total = horizontal_drum_capacity_ft3(
            _required_positive(specs, "Top Drum Diameter (ft)"),
            _required_positive(specs, "Top Drum Length (ft)"),
        )
        top_provenance = "diameter+tangent_length+two_hemispherical_heads"
    else:
        top_total = float(top_total)
        top_provenance = "Top Drum Total Volume (ft3)"
    if not np.isfinite(top_total) or top_total <= 0.0:
        raise ValueError("top drum total capacity is invalid")

    sump_total = specs.get("Bottom Sump Total Volume (ft3)")
    if sump_total is None:
        sump_total = vertical_cylinder_capacity_ft3(
            _required_positive(specs, "Bottom Sump Diameter (ft)"),
            _required_positive(specs, "Bottom Sump Height (ft)"),
        )
        sump_provenance = "diameter+height vertical cylinder"
    else:
        sump_total = float(sump_total)
        sump_provenance = "Bottom Sump Total Volume (ft3)"
    if not np.isfinite(sump_total) or sump_total <= 0.0:
        raise ValueError("bottom sump total capacity is invalid")

    records: list[VaporControlVolumeGeometry] = [
        VaporControlVolumeGeometry(
            volume_id=topology.top_volume,
            source_stage_1based=1,
            geometry_kind="horizontal_drum_two_hemispherical_heads",
            gross_capacity_ft3=float(top_total),
            fixed_vapor_extension_ft3=0.0,
            liquid_displacement_active=True,
            provenance=top_provenance,
        )
    ]
    for stage0, volume in enumerate(topology.volume_ids[1:-1], start=1):
        records.append(
            VaporControlVolumeGeometry(
                volume_id=volume,
                source_stage_1based=stage0 + 1,
                geometry_kind="tray_bay_cylindrical_shell",
                gross_capacity_ft3=float(area[stage0] * spacing[stage0]),
                fixed_vapor_extension_ft3=0.0,
                liquid_displacement_active=True,
                provenance="stage area times tray spacing",
            )
        )
    bottom_extension = float(declared_vapor[-1])
    records.append(
        VaporControlVolumeGeometry(
            volume_id=topology.bottom_volume,
            source_stage_1based=stage_count,
            geometry_kind="combined_vertical_sump_and_reboiler_vapor_space",
            gross_capacity_ft3=float(sump_total + bottom_extension),
            fixed_vapor_extension_ft3=bottom_extension,
            liquid_displacement_active=True,
            provenance=f"{sump_provenance} + stage-{stage_count} vapor extension",
        )
    )
    return tuple(records)


def audit_vapor_geometry(
    geometry: Sequence[VaporControlVolumeGeometry],
    topology: ColumnTopology,
) -> VaporGeometryAudit:
    records = tuple(geometry)
    volume_ids = tuple(record.volume_id for record in records)
    stages = tuple(record.source_stage_1based for record in records)
    duplicate = tuple(
        sorted({volume for volume in volume_ids if volume_ids.count(volume) > 1})
    )
    missing = tuple(
        volume for volume in topology.volume_ids if volume not in volume_ids
    )
    invalid_stages = tuple(
        stage
        for stage in stages
        if stage < 1 or stage > len(topology.volume_ids)
    )
    nonpositive = tuple(
        record.volume_id
        for record in records
        if not np.isfinite(record.gross_capacity_ft3)
        or record.gross_capacity_ft3 <= 0.0
        or not np.isfinite(record.fixed_vapor_extension_ft3)
        or record.fixed_vapor_extension_ft3 < 0.0
    )
    no_displacement = tuple(
        record.volume_id for record in records if not record.liquid_displacement_active
    )
    top_kind = next(
        (
            record.geometry_kind
            for record in records
            if record.volume_id == topology.top_volume
        ),
        "missing",
    )
    bottom_kind = next(
        (
            record.geometry_kind
            for record in records
            if record.volume_id == topology.bottom_volume
        ),
        "missing",
    )
    tray_count = sum(record.geometry_kind == "tray_bay_cylindrical_shell" for record in records)
    terminal_count = len(records) - tray_count
    expected = len(topology.volume_ids)
    passed = bool(
        len(records) == expected
        and volume_ids == topology.volume_ids
        and stages == tuple(range(1, expected + 1))
        and not duplicate
        and not missing
        and not invalid_stages
        and not nonpositive
        and not no_displacement
        and top_kind == "horizontal_drum_two_hemispherical_heads"
        and bottom_kind == "combined_vertical_sump_and_reboiler_vapor_space"
        and tray_count == expected - 2
        and terminal_count == 2
    )
    return VaporGeometryAudit(
        volume_count=len(records),
        expected_volume_count=expected,
        volume_ids=volume_ids,
        source_stages_1based=stages,
        missing_volume_ids=missing,
        duplicate_volume_ids=duplicate,
        invalid_source_stages=invalid_stages,
        nonpositive_capacities=nonpositive,
        liquid_displacement_missing=no_displacement,
        top_geometry_kind=top_kind,
        bottom_geometry_kind=bottom_kind,
        tray_volume_count=tray_count,
        terminal_volume_count=terminal_count,
        pass_gate=passed,
    )


def evaluate_free_vapor_volume(
    geometry: Sequence[VaporControlVolumeGeometry],
    liquid_component_inventory_lbmol: Sequence[Sequence[float]],
    liquid_density_lbmol_ft3: Sequence[float],
) -> FreeVaporVolumeEvaluation:
    records = tuple(geometry)
    inventory = np.asarray(liquid_component_inventory_lbmol, dtype=float)
    density = np.asarray(liquid_density_lbmol_ft3, dtype=float)
    if inventory.ndim != 2 or inventory.shape[0] != len(records):
        raise ValueError("liquid component inventory has the wrong shape")
    if density.shape != (len(records),):
        raise ValueError("liquid density has the wrong shape")
    if (
        np.any(~np.isfinite(inventory))
        or np.any(inventory <= 0.0)
        or np.any(~np.isfinite(density))
        or np.any(density <= 0.0)
    ):
        raise ValueError("liquid inventory and density must be positive and finite")
    gross = np.asarray([record.gross_capacity_ft3 for record in records])
    liquid = np.sum(inventory, axis=1) / density
    free = gross - liquid
    if np.any(~np.isfinite(free)) or np.any(free <= 0.0):
        offenders = tuple(
            records[index].volume_id
            for index in np.flatnonzero(~np.isfinite(free) | (free <= 0.0))
        )
        raise ValueError(f"liquid inventory overfills vapor control volume: {offenders}")
    return FreeVaporVolumeEvaluation(
        volume_ids=tuple(record.volume_id for record in records),
        gross_capacity_ft3=gross,
        liquid_volume_ft3=liquid,
        free_vapor_volume_ft3=free,
    )


def gross_capacity_mapping(
    geometry: Sequence[VaporControlVolumeGeometry],
) -> dict[str, float]:
    return {
        record.volume_id: float(record.gross_capacity_ft3) for record in geometry
    }


__all__ = [
    "FreeVaporVolumeEvaluation",
    "VaporControlVolumeGeometry",
    "VaporGeometryAudit",
    "audit_vapor_geometry",
    "build_column_vapor_geometry",
    "evaluate_free_vapor_volume",
    "gross_capacity_mapping",
    "horizontal_drum_capacity_ft3",
    "vertical_cylinder_capacity_ft3",
]
