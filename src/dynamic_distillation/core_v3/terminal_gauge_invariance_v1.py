"""Terminal inventory gauge transformations for Core V3 zero-rate audits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerNumericalSpec,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS


@dataclass(frozen=True)
class TerminalGaugeAssessment:
    provider_repeatability_inf_norm: float
    invariance_limit: float
    perturbation_difference_inf_norms: Mapping[str, float]
    composition_difference_inf_norms: Mapping[str, float]
    bottom_specific_energy_difference: Mapping[str, float]
    pass_gate: bool


def scale_terminal_gauge_coordinates(
    numerical: InitializerNumericalSpec,
    coordinates: Sequence[float],
    *,
    terminal: str,
    factor: float,
) -> np.ndarray:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    inventory_reference = np.asarray(numerical.inventory_reference_lbmol, dtype=float)
    component_count = inventory_reference.shape[1]
    state_count = inventory_reference.size + len(VOLUME_IDS) - 1
    full_coordinate_count = np.asarray(
        numerical.objective_center, dtype=float
    ).size
    algebraic_count = full_coordinate_count - 2 * state_count
    expected = state_count + algebraic_count
    if (
        point.shape != (expected,)
        or terminal not in {"reflux_drum", "combined_reboiler_sump"}
        or not np.isfinite(factor)
        or factor <= 0.0
    ):
        raise ValueError("terminal gauge transformation inputs are invalid")
    result = point.copy()
    volume_index = 0 if terminal == "reflux_drum" else len(VOLUME_IDS) - 1
    start = volume_index * component_count
    result[start : start + component_count] += np.log(float(factor))
    if terminal == "combined_reboiler_sump":
        lower_reference = np.asarray(
            numerical.lower_internal_energy_reference_BTU, dtype=float
        )
        lower_scale = np.asarray(
            numerical.lower_internal_energy_scale_BTU, dtype=float
        )
        energy_index = inventory_reference.size + len(VOLUME_IDS) - 2
        current_energy = (
            lower_reference[-1] + point[energy_index] * lower_scale[-1]
        )
        result[energy_index] = (
            float(factor) * current_energy - lower_reference[-1]
        ) / lower_scale[-1]
    return result


def assess_terminal_gauge_invariance(
    baseline_dae: Sequence[float],
    repeated_baseline_dae: Sequence[float],
    perturbed_dae: Mapping[str, Sequence[float]],
    composition_differences: Mapping[str, float],
    bottom_specific_energy_differences: Mapping[str, float],
    *,
    absolute_floor: float = 1.0e-10,
    repeatability_multiplier: float = 10.0,
) -> TerminalGaugeAssessment:
    baseline = np.asarray(baseline_dae, dtype=float)
    repeated = np.asarray(repeated_baseline_dae, dtype=float)
    if baseline.shape != repeated.shape or baseline.ndim != 1:
        raise ValueError("terminal gauge residual vectors are invalid")
    repeatability = float(np.max(np.abs(repeated - baseline)))
    limit = max(float(absolute_floor), float(repeatability_multiplier) * repeatability)
    differences = {
        name: float(np.max(np.abs(np.asarray(values, dtype=float) - baseline)))
        for name, values in perturbed_dae.items()
    }
    composition = {name: float(value) for name, value in composition_differences.items()}
    specific_energy = {
        name: float(value)
        for name, value in bottom_specific_energy_differences.items()
    }
    finite = all(
        np.isfinite(value)
        for value in (
            repeatability,
            limit,
            *differences.values(),
            *composition.values(),
            *specific_energy.values(),
        )
    )
    passed = bool(
        finite
        and differences
        and max(differences.values()) <= limit
        and max(composition.values(), default=0.0) <= 1.0e-12
        and max(specific_energy.values(), default=0.0) <= 1.0e-10
    )
    return TerminalGaugeAssessment(
        provider_repeatability_inf_norm=repeatability,
        invariance_limit=limit,
        perturbation_difference_inf_norms=differences,
        composition_difference_inf_norms=composition,
        bottom_specific_energy_difference=specific_energy,
        pass_gate=passed,
    )


__all__ = [
    "TerminalGaugeAssessment",
    "assess_terminal_gauge_invariance",
    "scale_terminal_gauge_coordinates",
]
