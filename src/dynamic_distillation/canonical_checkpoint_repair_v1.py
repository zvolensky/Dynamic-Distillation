"""Canonical live-property mapping for the one-shot DD-070 repair."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    ConservativeNodeTarget,
)
from dynamic_distillation.terminal_energy_volume_audit_v1 import (
    EnergyVolumeRegionAudit,
    EnergyVolumeRegionInput,
    audit_energy_volume_region,
)


@dataclass(frozen=True)
class CanonicalSourceInput:
    node_id: str
    position_1based: int
    component_inventory_lbmol: np.ndarray
    region: EnergyVolumeRegionInput
    canonical_fixed_volume_ft3: float
    topology: str


@dataclass(frozen=True)
class CanonicalSourceMapping:
    node_id: str
    position_1based: int
    component_inventory_lbmol: np.ndarray
    stored_internal_energy_BTU: float
    canonical_internal_energy_BTU: float
    mapping_energy_change_BTU: float
    prior_fixed_volume_ft3: float
    canonical_fixed_volume_ft3: float
    occupied_phase_volume_ft3: float
    prior_volume_mismatch_relative: float
    canonical_volume_mismatch_relative: float
    stored_enthalpy_mismatch_relative: float | None
    liquid_moles_lbmol: float
    vapor_moles_lbmol: float
    temperature_F: float
    pressure_psia: float
    topology: str
    audit: EnergyVolumeRegionAudit


@dataclass(frozen=True)
class CanonicalTargetMapping:
    target: ConservativeNodeTarget
    source_node_ids: tuple[str, ...]
    stored_internal_energy_BTU: float
    canonical_internal_energy_BTU: float
    mapping_energy_change_BTU: float
    occupied_phase_volume_ft3: float
    canonical_fixed_volume_ft3: float
    canonical_volume_mismatch_relative: float
    topology: str


def canonicalize_source_node(
    *,
    provider: Any,
    source: CanonicalSourceInput,
) -> CanonicalSourceMapping:
    """Replace serialized energy with live-property phase internal energy."""
    audit = audit_energy_volume_region(
        provider=provider,
        region=source.region,
    )
    canonical_volume = float(source.canonical_fixed_volume_ft3)
    if not np.isfinite(canonical_volume) or canonical_volume <= 0.0:
        raise ValueError(f"{source.node_id} canonical volume must be positive")
    occupied_volume = float(audit.reconstructed_total_volume_ft3)
    canonical_volume_mismatch = abs(
        canonical_volume - occupied_volume
    ) / max(canonical_volume, 1.0e-12)
    canonical_u = float(audit.phase_sum_internal_energy_BTU)
    stored_u = float(source.region.mapped_internal_energy_BTU)
    return CanonicalSourceMapping(
        node_id=str(source.node_id),
        position_1based=int(source.position_1based),
        component_inventory_lbmol=np.asarray(
            source.component_inventory_lbmol,
            dtype=float,
        ).copy(),
        stored_internal_energy_BTU=stored_u,
        canonical_internal_energy_BTU=canonical_u,
        mapping_energy_change_BTU=float(canonical_u - stored_u),
        prior_fixed_volume_ft3=float(source.region.fixed_total_volume_ft3),
        canonical_fixed_volume_ft3=canonical_volume,
        occupied_phase_volume_ft3=occupied_volume,
        prior_volume_mismatch_relative=float(
            audit.volume_reconstruction_relative
        ),
        canonical_volume_mismatch_relative=float(
            canonical_volume_mismatch
        ),
        stored_enthalpy_mismatch_relative=(
            None
            if audit.stored_vs_reconstructed_enthalpy_relative is None
            else float(audit.stored_vs_reconstructed_enthalpy_relative)
        ),
        liquid_moles_lbmol=float(audit.liquid_moles_lbmol),
        vapor_moles_lbmol=float(audit.vapor_moles_lbmol),
        temperature_F=float(source.region.temperature_F),
        pressure_psia=float(source.region.pressure_psia),
        topology=str(source.topology),
        audit=audit,
    )


def combine_canonical_sources(
    *,
    node_id: str,
    position_1based: int,
    sources: Sequence[CanonicalSourceMapping],
    topology: str,
) -> CanonicalTargetMapping:
    """Combine explicit source owners into one DD-070 conserved node."""
    members = tuple(sources)
    if not members:
        raise ValueError("canonical target requires at least one source")
    component_count = int(members[0].component_inventory_lbmol.size)
    components = np.zeros(component_count, dtype=float)
    stored_u = 0.0
    canonical_u = 0.0
    occupied_volume = 0.0
    fixed_volume = 0.0
    liquid_moles = 0.0
    vapor_moles = 0.0
    weighted_temperature = 0.0
    weighted_pressure = 0.0
    total_weight = 0.0
    for member in members:
        member_components = np.asarray(
            member.component_inventory_lbmol,
            dtype=float,
        ).reshape((component_count,))
        weight = float(np.sum(member_components))
        components += member_components
        stored_u += float(member.stored_internal_energy_BTU)
        canonical_u += float(member.canonical_internal_energy_BTU)
        occupied_volume += float(member.occupied_phase_volume_ft3)
        fixed_volume += float(member.canonical_fixed_volume_ft3)
        liquid_moles += float(member.liquid_moles_lbmol)
        vapor_moles += float(member.vapor_moles_lbmol)
        if weight > 0.0:
            weighted_temperature += weight * float(member.temperature_F)
            weighted_pressure += weight * float(member.pressure_psia)
            total_weight += weight
    if total_weight <= 0.0:
        raise ValueError(f"{node_id} has no canonical component inventory")
    total_moles = float(np.sum(components))
    beta = vapor_moles / max(liquid_moles + vapor_moles, 1.0e-12)
    target = ConservativeNodeTarget(
        node_id=str(node_id),
        position_1based=int(position_1based),
        total_component_inventory_lbmol=components,
        total_internal_energy_BTU=float(canonical_u),
        fixed_total_volume_ft3=float(fixed_volume),
        initial_temperature_F=float(
            weighted_temperature / total_weight
        ),
        initial_pressure_psia=float(weighted_pressure / total_weight),
        initial_beta_vapor=float(np.clip(beta, 1.0e-8, 1.0 - 1.0e-8)),
    )
    return CanonicalTargetMapping(
        target=target,
        source_node_ids=tuple(str(member.node_id) for member in members),
        stored_internal_energy_BTU=float(stored_u),
        canonical_internal_energy_BTU=float(canonical_u),
        mapping_energy_change_BTU=float(canonical_u - stored_u),
        occupied_phase_volume_ft3=float(occupied_volume),
        canonical_fixed_volume_ft3=float(fixed_volume),
        canonical_volume_mismatch_relative=abs(
            fixed_volume - occupied_volume
        )
        / max(abs(fixed_volume), 1.0e-12),
        topology=str(topology),
    )


def direct_canonical_target(
    *,
    mapping: CanonicalSourceMapping,
) -> CanonicalTargetMapping:
    total_moles = float(np.sum(mapping.component_inventory_lbmol))
    beta = mapping.vapor_moles_lbmol / max(total_moles, 1.0e-12)
    target = ConservativeNodeTarget(
        node_id=str(mapping.node_id),
        position_1based=int(mapping.position_1based),
        total_component_inventory_lbmol=np.asarray(
            mapping.component_inventory_lbmol,
            dtype=float,
        ).copy(),
        total_internal_energy_BTU=float(
            mapping.canonical_internal_energy_BTU
        ),
        fixed_total_volume_ft3=float(
            mapping.canonical_fixed_volume_ft3
        ),
        initial_temperature_F=float(mapping.temperature_F),
        initial_pressure_psia=float(mapping.pressure_psia),
        initial_beta_vapor=float(np.clip(beta, 1.0e-8, 1.0 - 1.0e-8)),
    )
    return CanonicalTargetMapping(
        target=target,
        source_node_ids=(str(mapping.node_id),),
        stored_internal_energy_BTU=float(
            mapping.stored_internal_energy_BTU
        ),
        canonical_internal_energy_BTU=float(
            mapping.canonical_internal_energy_BTU
        ),
        mapping_energy_change_BTU=float(mapping.mapping_energy_change_BTU),
        occupied_phase_volume_ft3=float(
            mapping.occupied_phase_volume_ft3
        ),
        canonical_fixed_volume_ft3=float(
            mapping.canonical_fixed_volume_ft3
        ),
        canonical_volume_mismatch_relative=float(
            mapping.canonical_volume_mismatch_relative
        ),
        topology=str(mapping.topology),
    )
