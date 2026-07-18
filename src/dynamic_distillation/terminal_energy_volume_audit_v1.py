"""Deterministic energy, volume, and scaling checks for conserved nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np

from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    ConservativeNodeTarget,
)
from dynamic_distillation.least_movement_redistribution_v1 import (
    MovementScales,
)
from dynamic_distillation.uv_flash_stage_v1 import (
    BTU_PER_PSI_FT3,
    _internal_energy_from_enthalpy_BTU_lbmol,
    _provider_vapor_z_factor,
    _vapor_molar_volume_ft3_lbmol,
)


@dataclass(frozen=True)
class EnergyVolumeRegionInput:
    region_id: str
    category: str
    source_blocks: tuple[str, ...]
    temperature_F: float
    pressure_psia: float
    liquid_inventory_lbmol: np.ndarray
    vapor_inventory_lbmol: np.ndarray
    fixed_total_volume_ft3: float
    mapped_internal_energy_BTU: float
    mapped_energy_basis: str
    stored_enthalpy_BTU: Optional[float] = None


@dataclass(frozen=True)
class EnergyVolumeRegionAudit:
    region_id: str
    category: str
    source_blocks: tuple[str, ...]
    mapped_energy_basis: str
    temperature_F: float
    pressure_psia: float
    liquid_moles_lbmol: float
    vapor_moles_lbmol: float
    stored_enthalpy_BTU: Optional[float]
    reconstructed_liquid_enthalpy_BTU: float
    reconstructed_vapor_enthalpy_BTU: float
    reconstructed_enthalpy_BTU: float
    fixed_total_volume_ft3: float
    reconstructed_liquid_volume_ft3: float
    reconstructed_vapor_volume_ft3: float
    reconstructed_total_volume_ft3: float
    fixed_volume_pv_BTU: float
    phase_volume_pv_BTU: float
    mapped_internal_energy_BTU: float
    stored_h_minus_fixed_pv_BTU: Optional[float]
    reconstructed_h_minus_fixed_pv_BTU: float
    phase_sum_internal_energy_BTU: float
    mapped_minus_expected_internal_energy_BTU: float
    stored_vs_reconstructed_enthalpy_relative: Optional[float]
    mapped_vs_expected_internal_energy_relative: float
    enthalpy_round_trip_relative: float
    volume_reconstruction_relative: float
    phase_aggregation_relative: float
    enthalpy_round_trip_pass: bool
    stored_enthalpy_basis_pass: bool
    mapped_internal_energy_basis_pass: bool
    volume_reconstruction_pass: bool
    phase_aggregation_pass: bool


@dataclass(frozen=True)
class PlaceholderInvarianceAudit:
    region_id: str
    raw_component_inventory_abs_lbmol: float
    raw_stored_enthalpy_abs_BTU: float
    mapped_internal_energy_abs_BTU: float
    mapped_volume_abs_ft3: float
    component_tolerance_lbmol: float
    enthalpy_tolerance_BTU: float
    pass_gate: bool


@dataclass(frozen=True)
class EnergyScalingRow:
    node_id: str
    category: str
    total_inventory_lbmol: float
    absolute_internal_energy_BTU: float
    energy_scale_BTU: float
    normalized_l2_cost_for_test_move: float
    cost_relative_to_median_interior: float


@dataclass(frozen=True)
class EnergyScalingAudit:
    test_move_BTU: float
    neutrality_cost_ratio_limit: float
    rows: tuple[EnergyScalingRow, ...]
    minimum_cost: float
    maximum_cost: float
    maximum_to_minimum_cost_ratio: float
    median_interior_cost: float
    terminal_to_interior_cost_ratio_min: float
    terminal_to_interior_cost_ratio_max: float
    pass_gate: bool


def _normalized_inventory(values: Sequence[float]) -> tuple[float, np.ndarray]:
    arr = np.asarray(values, dtype=float).reshape((-1,))
    if not np.all(np.isfinite(arr)) or np.any(arr < 0.0):
        raise ValueError("phase inventory must be finite and nonnegative")
    total = float(np.sum(arr))
    if total <= 1.0e-12:
        return 0.0, np.full(arr.size, 1.0 / max(arr.size, 1), dtype=float)
    return total, arr / total


def audit_energy_volume_region(
    *,
    provider: Any,
    region: EnergyVolumeRegionInput,
    round_trip_relative_tolerance: float = 1.0e-10,
    stored_enthalpy_relative_tolerance: float = 1.0e-6,
    mapped_energy_relative_tolerance: float = 1.0e-10,
    volume_relative_tolerance: float = 1.0e-8,
    phase_aggregation_relative_tolerance: float = 1.0e-10,
) -> EnergyVolumeRegionAudit:
    """Reconstruct H, U, PV, and phase volume for one conserved node."""
    pressure = float(region.pressure_psia)
    temperature = float(region.temperature_F)
    fixed_volume = float(region.fixed_total_volume_ft3)
    if not np.isfinite(pressure) or pressure <= 0.0:
        raise ValueError("pressure must be finite and positive")
    if not np.isfinite(temperature) or temperature <= -459.67:
        raise ValueError("temperature must be finite and above absolute zero")
    if not np.isfinite(fixed_volume) or fixed_volume < 0.0:
        raise ValueError("fixed volume must be finite and nonnegative")

    liquid_moles, x_liquid = _normalized_inventory(
        region.liquid_inventory_lbmol
    )
    vapor_moles, y_vapor = _normalized_inventory(region.vapor_inventory_lbmol)

    h_liquid_total = 0.0
    h_vapor_total = 0.0
    liquid_volume = 0.0
    vapor_volume = 0.0
    liquid_u = 0.0
    vapor_u = 0.0

    if liquid_moles > 0.0:
        h_liquid_molar = float(
            provider.phase_enthalpy_BTU_lbmol(
                "liquid",
                temperature,
                pressure,
                x_liquid.tolist(),
            )
        )
        density = provider.liquid_density_lbmol_ft3(
            temperature,
            pressure,
            x_liquid.tolist(),
        )
        if density is None or not np.isfinite(float(density)) or float(density) <= 0.0:
            raise ValueError(f"{region.region_id} liquid density is unavailable")
        liquid_molar_volume = 1.0 / float(density)
        liquid_volume = liquid_moles * liquid_molar_volume
        h_liquid_total = liquid_moles * h_liquid_molar
        liquid_u = liquid_moles * _internal_energy_from_enthalpy_BTU_lbmol(
            h_liquid_molar,
            pressure,
            liquid_molar_volume,
        )

    if vapor_moles > 0.0:
        h_vapor_molar = float(
            provider.phase_enthalpy_BTU_lbmol(
                "vapor",
                temperature,
                pressure,
                y_vapor.tolist(),
            )
        )
        z_vapor = _provider_vapor_z_factor(
            provider,
            T_F=temperature,
            P_psia=pressure,
            y=y_vapor,
            flash_Z=None,
        )
        vapor_molar_volume = _vapor_molar_volume_ft3_lbmol(
            temperature,
            pressure,
            z_vapor,
        )
        vapor_volume = vapor_moles * vapor_molar_volume
        h_vapor_total = vapor_moles * h_vapor_molar
        vapor_u = vapor_moles * _internal_energy_from_enthalpy_BTU_lbmol(
            h_vapor_molar,
            pressure,
            vapor_molar_volume,
        )

    reconstructed_h = float(h_liquid_total + h_vapor_total)
    reconstructed_volume = float(liquid_volume + vapor_volume)
    fixed_pv = pressure * fixed_volume * BTU_PER_PSI_FT3
    phase_pv = pressure * reconstructed_volume * BTU_PER_PSI_FT3
    reconstructed_u_fixed = reconstructed_h - fixed_pv
    phase_sum_u = float(liquid_u + vapor_u)
    phase_combined_u = reconstructed_h - phase_pv

    stored_h = (
        None
        if region.stored_enthalpy_BTU is None
        else float(region.stored_enthalpy_BTU)
    )
    stored_u_fixed = None if stored_h is None else stored_h - fixed_pv
    if region.mapped_energy_basis == "stored_enthalpy_minus_fixed_pv":
        if stored_u_fixed is None:
            raise ValueError(
                f"{region.region_id} requires stored enthalpy for its energy basis"
            )
        expected_mapped_u = float(stored_u_fixed)
    elif region.mapped_energy_basis == "phase_property_sum":
        expected_mapped_u = float(phase_sum_u)
    elif region.mapped_energy_basis == "eliminated_placeholder":
        expected_mapped_u = 0.0
    else:
        raise ValueError(
            f"unknown mapped energy basis: {region.mapped_energy_basis}"
        )

    round_trip_h = reconstructed_u_fixed + fixed_pv
    round_trip_relative = abs(round_trip_h - reconstructed_h) / max(
        abs(reconstructed_h),
        1.0,
    )
    stored_h_relative = (
        None
        if stored_h is None
        else abs(stored_h - reconstructed_h) / max(abs(stored_h), 1.0)
    )
    mapped_difference = float(
        region.mapped_internal_energy_BTU - expected_mapped_u
    )
    mapped_relative = abs(mapped_difference) / max(
        abs(expected_mapped_u),
        1.0,
    )
    volume_relative = abs(fixed_volume - reconstructed_volume) / max(
        abs(fixed_volume),
        1.0e-12,
    )
    phase_aggregation_relative = abs(phase_sum_u - phase_combined_u) / max(
        abs(phase_sum_u),
        1.0,
    )

    return EnergyVolumeRegionAudit(
        region_id=str(region.region_id),
        category=str(region.category),
        source_blocks=tuple(str(item) for item in region.source_blocks),
        mapped_energy_basis=str(region.mapped_energy_basis),
        temperature_F=temperature,
        pressure_psia=pressure,
        liquid_moles_lbmol=float(liquid_moles),
        vapor_moles_lbmol=float(vapor_moles),
        stored_enthalpy_BTU=stored_h,
        reconstructed_liquid_enthalpy_BTU=float(h_liquid_total),
        reconstructed_vapor_enthalpy_BTU=float(h_vapor_total),
        reconstructed_enthalpy_BTU=float(reconstructed_h),
        fixed_total_volume_ft3=fixed_volume,
        reconstructed_liquid_volume_ft3=float(liquid_volume),
        reconstructed_vapor_volume_ft3=float(vapor_volume),
        reconstructed_total_volume_ft3=float(reconstructed_volume),
        fixed_volume_pv_BTU=float(fixed_pv),
        phase_volume_pv_BTU=float(phase_pv),
        mapped_internal_energy_BTU=float(region.mapped_internal_energy_BTU),
        stored_h_minus_fixed_pv_BTU=(
            None if stored_u_fixed is None else float(stored_u_fixed)
        ),
        reconstructed_h_minus_fixed_pv_BTU=float(reconstructed_u_fixed),
        phase_sum_internal_energy_BTU=float(phase_sum_u),
        mapped_minus_expected_internal_energy_BTU=float(mapped_difference),
        stored_vs_reconstructed_enthalpy_relative=(
            None if stored_h_relative is None else float(stored_h_relative)
        ),
        mapped_vs_expected_internal_energy_relative=float(mapped_relative),
        enthalpy_round_trip_relative=float(round_trip_relative),
        volume_reconstruction_relative=float(volume_relative),
        phase_aggregation_relative=float(phase_aggregation_relative),
        enthalpy_round_trip_pass=bool(
            round_trip_relative < float(round_trip_relative_tolerance)
        ),
        stored_enthalpy_basis_pass=bool(
            stored_h_relative is None
            or stored_h_relative < float(stored_enthalpy_relative_tolerance)
        ),
        mapped_internal_energy_basis_pass=bool(
            mapped_relative < float(mapped_energy_relative_tolerance)
        ),
        volume_reconstruction_pass=bool(
            volume_relative < float(volume_relative_tolerance)
        ),
        phase_aggregation_pass=bool(
            phase_aggregation_relative
            < float(phase_aggregation_relative_tolerance)
        ),
    )


def audit_empty_placeholder_invariance(
    *,
    region_id: str,
    raw_component_inventory_lbmol: Sequence[float],
    raw_stored_enthalpy_BTU: float,
    mapped_internal_energy_BTU: float,
    mapped_volume_ft3: float,
    component_tolerance_lbmol: float = 1.0e-10,
    enthalpy_tolerance_BTU: float = 1.0e-6,
) -> PlaceholderInvarianceAudit:
    component_abs = float(
        np.sum(np.abs(np.asarray(raw_component_inventory_lbmol, dtype=float)))
    )
    raw_h_abs = abs(float(raw_stored_enthalpy_BTU))
    mapped_u_abs = abs(float(mapped_internal_energy_BTU))
    mapped_v_abs = abs(float(mapped_volume_ft3))
    passed = bool(
        component_abs <= float(component_tolerance_lbmol)
        and raw_h_abs <= float(enthalpy_tolerance_BTU)
        and mapped_u_abs <= float(enthalpy_tolerance_BTU)
        and mapped_v_abs <= 1.0e-12
    )
    return PlaceholderInvarianceAudit(
        region_id=str(region_id),
        raw_component_inventory_abs_lbmol=component_abs,
        raw_stored_enthalpy_abs_BTU=raw_h_abs,
        mapped_internal_energy_abs_BTU=mapped_u_abs,
        mapped_volume_abs_ft3=mapped_v_abs,
        component_tolerance_lbmol=float(component_tolerance_lbmol),
        enthalpy_tolerance_BTU=float(enthalpy_tolerance_BTU),
        pass_gate=passed,
    )


def audit_energy_scaling(
    *,
    targets: Sequence[ConservativeNodeTarget],
    scales: MovementScales,
    test_move_BTU: float = 1000.0,
    neutrality_cost_ratio_limit: float = 10.0,
) -> EnergyScalingAudit:
    """Report how local energy normalization prices one physical BTU move."""
    nodes = tuple(targets)
    energy_scale = np.asarray(scales.energy_BTU, dtype=float).reshape(
        (len(nodes),)
    )
    if np.any(~np.isfinite(energy_scale)) or np.any(energy_scale <= 0.0):
        raise ValueError("energy movement scales must be finite and positive")
    test_move = float(test_move_BTU)
    costs = np.square(test_move / energy_scale)
    interior_mask = np.asarray(
        [not str(node.node_id).endswith("_terminal") for node in nodes],
        dtype=bool,
    )
    terminal_mask = ~interior_mask
    if not np.any(interior_mask) or not np.any(terminal_mask):
        raise ValueError("scaling audit requires terminal and interior nodes")
    median_interior = float(np.median(costs[interior_mask]))
    rows = tuple(
        EnergyScalingRow(
            node_id=str(node.node_id),
            category=(
                "terminal"
                if str(node.node_id).endswith("_terminal")
                else "interior"
            ),
            total_inventory_lbmol=float(
                np.sum(node.total_component_inventory_lbmol)
            ),
            absolute_internal_energy_BTU=abs(
                float(node.total_internal_energy_BTU)
            ),
            energy_scale_BTU=float(energy_scale[idx]),
            normalized_l2_cost_for_test_move=float(costs[idx]),
            cost_relative_to_median_interior=float(
                costs[idx] / max(median_interior, 1.0e-300)
            ),
        )
        for idx, node in enumerate(nodes)
    )
    minimum = float(np.min(costs))
    maximum = float(np.max(costs))
    ratio = maximum / max(minimum, 1.0e-300)
    terminal_relative = costs[terminal_mask] / max(
        median_interior,
        1.0e-300,
    )
    return EnergyScalingAudit(
        test_move_BTU=test_move,
        neutrality_cost_ratio_limit=float(neutrality_cost_ratio_limit),
        rows=rows,
        minimum_cost=minimum,
        maximum_cost=maximum,
        maximum_to_minimum_cost_ratio=float(ratio),
        median_interior_cost=median_interior,
        terminal_to_interior_cost_ratio_min=float(np.min(terminal_relative)),
        terminal_to_interior_cost_ratio_max=float(np.max(terminal_relative)),
        pass_gate=bool(ratio <= float(neutrality_cost_ratio_limit)),
    )
