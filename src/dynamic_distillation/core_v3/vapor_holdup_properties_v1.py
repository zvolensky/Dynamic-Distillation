"""Live property reconstruction for the Core V3 vapor-holdup successor."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    GAS_CONSTANT_PSIA_FT3_LBMOL_R,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    FreeVaporVolumeEvaluation,
    VaporControlVolumeGeometry,
    evaluate_free_vapor_volume,
)
from dynamic_distillation.uv_flash_stage_v1 import BTU_PER_PSI_FT3


@dataclass(frozen=True)
class VaporHoldupPropertyEvaluation:
    volume_ids: tuple[str, ...]
    liquid_density_lbmol_ft3: np.ndarray
    vapor_compressibility_factor: np.ndarray
    liquid_enthalpy_BTU_lbmol: np.ndarray
    vapor_enthalpy_BTU_lbmol: np.ndarray
    liquid_molar_volume_ft3_lbmol: np.ndarray
    vapor_molar_volume_ft3_lbmol: np.ndarray
    liquid_internal_energy_BTU_lbmol: np.ndarray
    vapor_internal_energy_BTU_lbmol: np.ndarray
    liquid_stored_energy_BTU: np.ndarray
    vapor_stored_energy_BTU: np.ndarray
    total_stored_energy_BTU: np.ndarray
    vapor_moles_lbmol: np.ndarray
    vapor_component_inventory_lbmol: np.ndarray
    free_volume: FreeVaporVolumeEvaluation
    eos_volume_residual_ft3: np.ndarray
    eos_relative_residual: np.ndarray
    provider_record_start: int
    provider_record_end: int


@dataclass(frozen=True)
class VaporHoldupPropertyAudit:
    volume_count: int
    provider_call_count: int
    expected_provider_call_count: int
    maximum_absolute_eos_residual_ft3: float
    maximum_relative_eos_residual: float
    minimum_free_vapor_volume_ft3: float
    minimum_vapor_moles_lbmol: float
    minimum_liquid_density_lbmol_ft3: float
    minimum_vapor_compressibility_factor: float
    all_energy_terms_finite: bool
    exact_property_call_ledger: bool
    governing_evaluation_kinds_only: bool
    provider_fallback_attempted: bool
    pass_gate: bool


def _state_array(
    values: Sequence[float] | Sequence[Sequence[float]],
    *,
    name: str,
    shape: tuple[int, ...],
) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != shape:
        raise ValueError(f"{name} has shape {result.shape}; expected {shape}")
    if np.any(~np.isfinite(result)):
        raise ValueError(f"{name} must be finite")
    return result


def _validate_composition(values: np.ndarray, *, name: str) -> None:
    if np.any(values <= 0.0):
        raise ValueError(f"{name} must be strictly positive")
    totals = np.sum(values, axis=1)
    if not np.allclose(totals, 1.0, rtol=0.0, atol=1.0e-10):
        raise ValueError(f"{name} rows must sum to one")


def evaluate_vapor_holdup_properties(
    geometry: Sequence[VaporControlVolumeGeometry],
    liquid_component_inventory_lbmol: Sequence[Sequence[float]],
    liquid_mole_fraction: Sequence[Sequence[float]],
    vapor_mole_fraction: Sequence[Sequence[float]],
    temperature_F: Sequence[float],
    pressure_psia: Sequence[float],
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    state_id: str,
    evaluation_kind: str = "residual",
) -> VaporHoldupPropertyEvaluation:
    """Reconstruct resident vapor inventory and two-phase stored energy."""
    records = tuple(geometry)
    volume_count = len(records)
    if volume_count == 0:
        raise ValueError("vapor-holdup property evaluation requires physical volumes")
    inventory = np.asarray(liquid_component_inventory_lbmol, dtype=float)
    if inventory.ndim != 2:
        raise ValueError("liquid component inventory must be a two-dimensional array")
    component_count = inventory.shape[1]
    expected_composition_shape = (volume_count, component_count)
    inventory = _state_array(
        inventory,
        name="liquid component inventory",
        shape=expected_composition_shape,
    )
    liquid_x = _state_array(
        liquid_mole_fraction,
        name="liquid mole fraction",
        shape=expected_composition_shape,
    )
    vapor_y = _state_array(
        vapor_mole_fraction,
        name="vapor mole fraction",
        shape=expected_composition_shape,
    )
    temperature = _state_array(
        temperature_F,
        name="temperature",
        shape=(volume_count,),
    )
    pressure = _state_array(
        pressure_psia,
        name="pressure",
        shape=(volume_count,),
    )
    if np.any(inventory <= 0.0):
        raise ValueError("liquid component inventory must be strictly positive")
    _validate_composition(liquid_x, name="liquid mole fraction")
    _validate_composition(vapor_y, name="vapor mole fraction")
    inventory_x = inventory / np.sum(inventory, axis=1, keepdims=True)
    if not np.allclose(inventory_x, liquid_x, rtol=0.0, atol=1.0e-10):
        raise ValueError("liquid inventory composition disagrees with liquid mole fraction")
    if np.any(temperature <= -459.67):
        raise ValueError("temperature must be above absolute zero")
    if np.any(pressure <= 0.0):
        raise ValueError("pressure must be positive")
    if evaluation_kind not in {"residual", "jacobian"}:
        raise ValueError("live vapor-holdup properties are residual/Jacobian only")

    density = np.empty(volume_count, dtype=float)
    compressibility = np.empty(volume_count, dtype=float)
    liquid_enthalpy = np.empty(volume_count, dtype=float)
    vapor_enthalpy = np.empty(volume_count, dtype=float)
    record_start = call_audit.record_count
    for index, record in enumerate(records):
        caller = f"vapor_holdup_properties[{record.volume_id}]"
        point_id = f"{state_id}:{record.volume_id}"
        density[index] = call_audit.liquid_density(
            provider,
            temperature_F=float(temperature[index]),
            pressure_psia=float(pressure[index]),
            composition=liquid_x[index],
            caller=caller,
            state_id=point_id,
            evaluation_kind=evaluation_kind,
        )
        compressibility[index] = call_audit.vapor_compressibility_factor(
            provider,
            temperature_F=float(temperature[index]),
            pressure_psia=float(pressure[index]),
            composition=vapor_y[index],
            caller=caller,
            state_id=point_id,
            evaluation_kind=evaluation_kind,
        )
        liquid_enthalpy[index] = call_audit.phase_enthalpy(
            provider,
            phase="liquid",
            temperature_F=float(temperature[index]),
            pressure_psia=float(pressure[index]),
            composition=liquid_x[index],
            caller=caller,
            state_id=point_id,
            evaluation_kind=evaluation_kind,
        )
        vapor_enthalpy[index] = call_audit.phase_enthalpy(
            provider,
            phase="vapor",
            temperature_F=float(temperature[index]),
            pressure_psia=float(pressure[index]),
            composition=vapor_y[index],
            caller=caller,
            state_id=point_id,
            evaluation_kind=evaluation_kind,
        )
    record_end = call_audit.record_count

    free_volume = evaluate_free_vapor_volume(records, inventory, density)
    temperature_R = temperature + 459.67
    liquid_molar_volume = 1.0 / density
    vapor_molar_volume = (
        compressibility
        * GAS_CONSTANT_PSIA_FT3_LBMOL_R
        * temperature_R
        / pressure
    )
    vapor_moles = free_volume.free_vapor_volume_ft3 / vapor_molar_volume
    vapor_inventory = vapor_moles[:, np.newaxis] * vapor_y
    eos_reconstructed_volume = vapor_moles * vapor_molar_volume
    eos_residual = free_volume.free_vapor_volume_ft3 - eos_reconstructed_volume
    eos_relative = eos_residual / free_volume.free_vapor_volume_ft3

    liquid_internal_energy = liquid_enthalpy - (
        pressure * liquid_molar_volume * BTU_PER_PSI_FT3
    )
    vapor_internal_energy = vapor_enthalpy - (
        pressure * vapor_molar_volume * BTU_PER_PSI_FT3
    )
    liquid_total_moles = np.sum(inventory, axis=1)
    liquid_energy = liquid_total_moles * liquid_internal_energy
    vapor_energy = vapor_moles * vapor_internal_energy
    total_energy = liquid_energy + vapor_energy
    physical_arrays = (
        vapor_molar_volume,
        vapor_moles,
        vapor_inventory,
        liquid_internal_energy,
        vapor_internal_energy,
        liquid_energy,
        vapor_energy,
        total_energy,
        eos_residual,
        eos_relative,
    )
    if any(np.any(~np.isfinite(values)) for values in physical_arrays):
        raise RuntimeError("vapor-holdup property reconstruction is non-finite")
    if np.any(vapor_molar_volume <= 0.0) or np.any(vapor_inventory <= 0.0):
        raise RuntimeError("vapor-holdup property reconstruction is non-physical")

    return VaporHoldupPropertyEvaluation(
        volume_ids=tuple(record.volume_id for record in records),
        liquid_density_lbmol_ft3=density,
        vapor_compressibility_factor=compressibility,
        liquid_enthalpy_BTU_lbmol=liquid_enthalpy,
        vapor_enthalpy_BTU_lbmol=vapor_enthalpy,
        liquid_molar_volume_ft3_lbmol=liquid_molar_volume,
        vapor_molar_volume_ft3_lbmol=vapor_molar_volume,
        liquid_internal_energy_BTU_lbmol=liquid_internal_energy,
        vapor_internal_energy_BTU_lbmol=vapor_internal_energy,
        liquid_stored_energy_BTU=liquid_energy,
        vapor_stored_energy_BTU=vapor_energy,
        total_stored_energy_BTU=total_energy,
        vapor_moles_lbmol=vapor_moles,
        vapor_component_inventory_lbmol=vapor_inventory,
        free_volume=free_volume,
        eos_volume_residual_ft3=eos_residual,
        eos_relative_residual=eos_relative,
        provider_record_start=record_start,
        provider_record_end=record_end,
    )


def evaluate_vapor_holdup_trial_properties(
    geometry: Sequence[VaporControlVolumeGeometry],
    liquid_component_inventory_lbmol: Sequence[Sequence[float]],
    vapor_component_inventory_lbmol: Sequence[Sequence[float]],
    temperature_F: Sequence[float],
    pressure_psia: Sequence[float],
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    state_id: str,
    evaluation_kind: str = "residual",
) -> VaporHoldupPropertyEvaluation:
    """Evaluate a trial two-phase state without reconstructing its vapor amount."""
    liquid_inventory = np.asarray(liquid_component_inventory_lbmol, dtype=float)
    vapor_inventory = np.asarray(vapor_component_inventory_lbmol, dtype=float)
    if liquid_inventory.ndim != 2 or vapor_inventory.shape != liquid_inventory.shape:
        raise ValueError("liquid and vapor component inventories must share a 2-D shape")
    if (
        np.any(~np.isfinite(liquid_inventory))
        or np.any(~np.isfinite(vapor_inventory))
        or np.any(liquid_inventory <= 0.0)
        or np.any(vapor_inventory <= 0.0)
    ):
        raise ValueError("trial phase inventories must be positive and finite")
    liquid_x = liquid_inventory / np.sum(liquid_inventory, axis=1, keepdims=True)
    vapor_y = vapor_inventory / np.sum(vapor_inventory, axis=1, keepdims=True)
    base = evaluate_vapor_holdup_properties(
        geometry,
        liquid_inventory,
        liquid_x,
        vapor_y,
        temperature_F,
        pressure_psia,
        provider,
        call_audit,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    vapor_moles = np.sum(vapor_inventory, axis=1)
    reconstructed_volume = vapor_moles * base.vapor_molar_volume_ft3_lbmol
    eos_residual = base.free_volume.free_vapor_volume_ft3 - reconstructed_volume
    eos_relative = eos_residual / base.free_volume.free_vapor_volume_ft3
    vapor_energy = vapor_moles * base.vapor_internal_energy_BTU_lbmol
    return replace(
        base,
        vapor_moles_lbmol=vapor_moles,
        vapor_component_inventory_lbmol=vapor_inventory.copy(),
        vapor_stored_energy_BTU=vapor_energy,
        total_stored_energy_BTU=base.liquid_stored_energy_BTU + vapor_energy,
        eos_volume_residual_ft3=eos_residual,
        eos_relative_residual=eos_relative,
    )


def audit_vapor_holdup_properties(
    evaluation: VaporHoldupPropertyEvaluation,
    call_audit: ProviderCallAudit,
    *,
    eos_relative_tolerance: float = 1.0e-12,
) -> VaporHoldupPropertyAudit:
    volume_count = len(evaluation.volume_ids)
    start = int(evaluation.provider_record_start)
    end = int(evaluation.provider_record_end)
    records = call_audit.records[start:end]
    expected_calls = 4 * volume_count
    expected_quantities = {
        "liquid_density": volume_count,
        "vapor_compressibility_factor": volume_count,
        "phase_enthalpy": 2 * volume_count,
    }
    actual_quantities = {
        quantity: sum(record.quantity == quantity for record in records)
        for quantity in expected_quantities
    }
    exact_ledger = bool(
        len(records) == expected_calls
        and actual_quantities == expected_quantities
        and start >= 0
        and end <= call_audit.record_count
    )
    governing_only = bool(
        records
        and all(record.evaluation_kind in {"residual", "jacobian"} for record in records)
    )
    energy_finite = bool(
        np.all(np.isfinite(evaluation.liquid_internal_energy_BTU_lbmol))
        and np.all(np.isfinite(evaluation.vapor_internal_energy_BTU_lbmol))
        and np.all(np.isfinite(evaluation.liquid_stored_energy_BTU))
        and np.all(np.isfinite(evaluation.vapor_stored_energy_BTU))
        and np.all(np.isfinite(evaluation.total_stored_energy_BTU))
    )
    maximum_absolute_eos = float(
        np.max(np.abs(evaluation.eos_volume_residual_ft3))
    )
    maximum_relative_eos = float(
        np.max(np.abs(evaluation.eos_relative_residual))
    )
    minimum_free = float(np.min(evaluation.free_volume.free_vapor_volume_ft3))
    minimum_vapor = float(np.min(evaluation.vapor_moles_lbmol))
    minimum_density = float(np.min(evaluation.liquid_density_lbmol_ft3))
    minimum_z = float(np.min(evaluation.vapor_compressibility_factor))
    passed = bool(
        volume_count > 0
        and exact_ledger
        and governing_only
        and not call_audit.fallback_attempted
        and energy_finite
        and minimum_free > 0.0
        and minimum_vapor > 0.0
        and minimum_density > 0.0
        and minimum_z > 0.0
        and maximum_relative_eos <= float(eos_relative_tolerance)
    )
    return VaporHoldupPropertyAudit(
        volume_count=volume_count,
        provider_call_count=len(records),
        expected_provider_call_count=expected_calls,
        maximum_absolute_eos_residual_ft3=maximum_absolute_eos,
        maximum_relative_eos_residual=maximum_relative_eos,
        minimum_free_vapor_volume_ft3=minimum_free,
        minimum_vapor_moles_lbmol=minimum_vapor,
        minimum_liquid_density_lbmol_ft3=minimum_density,
        minimum_vapor_compressibility_factor=minimum_z,
        all_energy_terms_finite=energy_finite,
        exact_property_call_ledger=exact_ledger,
        governing_evaluation_kinds_only=governing_only,
        provider_fallback_attempted=bool(call_audit.fallback_attempted),
        pass_gate=passed,
    )


__all__ = [
    "VaporHoldupPropertyAudit",
    "VaporHoldupPropertyEvaluation",
    "audit_vapor_holdup_properties",
    "evaluate_vapor_holdup_properties",
    "evaluate_vapor_holdup_trial_properties",
]
