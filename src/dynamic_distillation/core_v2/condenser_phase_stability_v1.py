"""Condenser outlet phase-stability diagnostics for Core V2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
)


@dataclass(frozen=True)
class CondenserPhaseStateAudit:
    outlet_temperature_F: float
    outlet_pressure_psia: float
    outlet_overall_composition: np.ndarray
    equilibrium_K: np.ndarray
    vapor_fraction: float
    phase_classification: str
    inlet_vapor_enthalpy_BTU_lbmol: float
    condenser_duty_per_mole_BTU_lbmol: float
    target_outlet_enthalpy_BTU_lbmol: float
    imposed_liquid_enthalpy_BTU_lbmol: float
    enthalpy_error_BTU_lbmol: float
    stable_single_liquid: bool


def rachford_rice_vapor_fraction(
    K: Sequence[float],
    overall_composition: Sequence[float],
) -> float:
    """Return the bounded Rachford-Rice vapor fraction without projection."""
    k = np.asarray(K, dtype=float).reshape((-1,))
    z = normalize_composition(overall_composition)
    if k.shape != z.shape or np.any(~np.isfinite(k)) or np.any(k <= 0.0):
        raise ValueError("invalid K values for condenser phase audit")

    def residual(beta: float) -> float:
        denominator = 1.0 + float(beta) * (k - 1.0)
        if np.any(denominator <= 0.0):
            raise ValueError("invalid Rachford-Rice denominator")
        return float(np.sum(z * (k - 1.0) / denominator))

    at_liquid = residual(0.0)
    at_vapor = residual(1.0)
    if at_liquid <= 0.0:
        return 0.0
    if at_vapor >= 0.0:
        return 1.0
    lower = 0.0
    upper = 1.0
    for _ in range(100):
        midpoint = 0.5 * (lower + upper)
        value = residual(midpoint)
        if abs(value) <= 1.0e-14:
            return midpoint
        if value > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return 0.5 * (lower + upper)


def audit_fixed_duty_condenser_outlet(
    provider: Any,
    *,
    inlet_temperature_F: float,
    inlet_pressure_psia: float,
    inlet_vapor_composition: Sequence[float],
    outlet_temperature_F: float,
    outlet_pressure_psia: float,
    outlet_overall_composition: Sequence[float],
    overhead_vapor_flow_lbmolph: float,
    condenser_duty_BTUph: float,
    phase_fraction_tolerance: float = 1.0e-8,
) -> CondenserPhaseStateAudit:
    """Audit the imposed liquid outlet against a live TP phase calculation."""
    if not np.isfinite(overhead_vapor_flow_lbmolph) or overhead_vapor_flow_lbmolph <= 0:
        raise ValueError("overhead vapor flow must be finite and positive")
    z = normalize_composition(outlet_overall_composition)
    inlet_y = normalize_composition(inlet_vapor_composition)
    flash = provider.flash_TP_full(
        float(outlet_temperature_F),
        float(outlet_pressure_psia),
        z.tolist(),
    )
    K = np.asarray(flash.K, dtype=float).reshape(z.shape)
    beta = rachford_rice_vapor_fraction(K, z)
    tolerance = float(phase_fraction_tolerance)
    if beta <= tolerance:
        classification = "liquid"
    elif beta >= 1.0 - tolerance:
        classification = "vapor"
    else:
        classification = "two_phase"
    inlet_hv = float(
        provider.phase_enthalpy_BTU_lbmol(
            "vapor",
            float(inlet_temperature_F),
            float(inlet_pressure_psia),
            inlet_y.tolist(),
        )
    )
    duty_per_mole = float(condenser_duty_BTUph) / float(
        overhead_vapor_flow_lbmolph
    )
    target_h = inlet_hv + duty_per_mole
    imposed_hl = float(
        provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            float(outlet_temperature_F),
            float(outlet_pressure_psia),
            z.tolist(),
        )
    )
    return CondenserPhaseStateAudit(
        outlet_temperature_F=float(outlet_temperature_F),
        outlet_pressure_psia=float(outlet_pressure_psia),
        outlet_overall_composition=z,
        equilibrium_K=K,
        vapor_fraction=float(beta),
        phase_classification=classification,
        inlet_vapor_enthalpy_BTU_lbmol=inlet_hv,
        condenser_duty_per_mole_BTU_lbmol=duty_per_mole,
        target_outlet_enthalpy_BTU_lbmol=target_h,
        imposed_liquid_enthalpy_BTU_lbmol=imposed_hl,
        enthalpy_error_BTU_lbmol=float(imposed_hl - target_h),
        stable_single_liquid=bool(classification == "liquid"),
    )


__all__ = [
    "CondenserPhaseStateAudit",
    "audit_fixed_duty_condenser_outlet",
    "rachford_rice_vapor_fraction",
]
