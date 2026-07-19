"""Frozen DD-088 steady-root campaign for the saturated-liquid condenser."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v2.condenser_saturated_liquid_numerical_gate_v1 import (
    BubbleSeedSettings,
    CondenserNumericalReference,
    audit_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
    phase_stability_diagnostics,
    solve_local_bubble_seed,
)
from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedOperatingSpec,
)
from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v2.energy_owned_vapor_steady_solve_v1 import (
    CampaignDefinition,
    SteadySolveSettings,
    encode_state,
    physical_bounds as base_physical_bounds,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
    vapor_from_logits,
    vapor_logits,
)


@dataclass(frozen=True)
class CondenserSteadySolveSettings(SteadySolveSettings):
    condenser_duty_min_abs_ratio: float = 0.1
    condenser_duty_max_abs_ratio: float = 3.0
    bubble_residual_tolerance: float = 1.0e-8
    bubble_sum_tolerance: float = 1.0e-4
    bubble_vapor_fraction_tolerance: float = 1.0e-3
    bubble_composition_tolerance: float = 1.0e-5


def _as_vector(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=float).reshape((-1,))


def encode_condenser_state(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    *,
    liquid_moles_lbmol: Sequence[float],
    liquid_mole_fraction: Sequence[Sequence[float]],
    temperature_F: Sequence[float],
    vapor_mole_fraction: Sequence[Sequence[float]],
    hydraulic_liquid_flow_lbmolph: Sequence[float],
    vapor_flow_lbmolph: Sequence[float],
    distillate_lbmolph: float,
    bottoms_lbmolph: float,
    bubble_vapor_mole_fraction: Sequence[float],
    condenser_duty_BTUph: float,
) -> np.ndarray:
    base = encode_state(
        spec,
        reference.base,
        liquid_moles_lbmol=liquid_moles_lbmol,
        liquid_mole_fraction=liquid_mole_fraction,
        temperature_F=temperature_F,
        vapor_mole_fraction=vapor_mole_fraction,
        hydraulic_liquid_flow_lbmolph=hydraulic_liquid_flow_lbmolph,
        vapor_flow_lbmolph=vapor_flow_lbmolph,
        distillate_lbmolph=distillate_lbmolph,
        bottoms_lbmolph=bottoms_lbmolph,
    )
    bubble = normalize_composition(bubble_vapor_mole_fraction)
    bubble_offset = (
        vapor_logits(bubble)
        - vapor_logits(reference.bubble_vapor_mole_fraction)
    )
    q_c = (
        float(condenser_duty_BTUph)
        - float(reference.condenser_duty_reference_BTUph)
    ) / float(reference.condenser_duty_scale_BTUph)
    return np.concatenate((base, bubble_offset, np.asarray([q_c])))


def physical_bounds(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    settings: CondenserSteadySolveSettings,
) -> tuple[np.ndarray, np.ndarray]:
    base_lower, base_upper = base_physical_bounds(
        spec,
        reference.base,
        settings,
    )
    layout = coordinate_layout(spec)
    lower = np.empty(len(layout.names), dtype=float)
    upper = np.empty(len(layout.names), dtype=float)
    lower[layout.base] = base_lower
    upper[layout.base] = base_upper

    component_count = len(spec.component_names)
    floor = float(settings.composition_floor)
    maximum = 1.0 - (component_count - 1) * floor
    alr_min = float(np.log(floor / maximum))
    alr_max = float(np.log(maximum / floor))
    bubble_reference_alr = vapor_logits(
        reference.bubble_vapor_mole_fraction
    )
    lower[layout.bubble_logits] = alr_min - bubble_reference_alr
    upper[layout.bubble_logits] = alr_max - bubble_reference_alr

    duty_abs = abs(float(reference.condenser_duty_reference_BTUph))
    duty_lower = -float(settings.condenser_duty_max_abs_ratio) * duty_abs
    duty_upper = -float(settings.condenser_duty_min_abs_ratio) * duty_abs
    scale = float(reference.condenser_duty_scale_BTUph)
    duty_reference = float(reference.condenser_duty_reference_BTUph)
    lower[layout.condenser_duty] = (duty_lower - duty_reference) / scale
    upper[layout.condenser_duty] = (duty_upper - duty_reference) / scale
    if (
        np.any(~np.isfinite(lower))
        or np.any(~np.isfinite(upper))
        or np.any(lower >= upper)
    ):
        raise RuntimeError("DD-088 transformed bounds are invalid")
    return lower, upper


def _phase_vapor_estimate(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: np.ndarray,
) -> np.ndarray:
    phi_liquid = np.asarray(
        provider.phase_fugacity_coefficients(
            "liquid",
            float(temperature_F),
            float(pressure_psia),
            liquid_x.tolist(),
        ),
        dtype=float,
    )
    phi_vapor = np.asarray(
        provider.phase_fugacity_coefficients(
            "vapor",
            float(temperature_F),
            float(pressure_psia),
            liquid_x.tolist(),
        ),
        dtype=float,
    )
    return normalize_composition(liquid_x * phi_liquid / phi_vapor)


def independent_smooth_phase_stable_start(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    provider: Any,
    *,
    bubble_settings: BubbleSeedSettings = BubbleSeedSettings(),
) -> tuple[np.ndarray, dict[str, Any]]:
    """Build an independent smooth seed without any column-balance solve."""
    canonical_x = np.asarray(
        reference.base.liquid_mole_fraction,
        dtype=float,
    )
    rectifying_alr = vapor_logits(canonical_x[1])
    feed_alr = vapor_logits(canonical_x[2])
    extrapolated_drum_alr = 2.0 * rectifying_alr - feed_alr
    independent_drum_alr = 0.5 * (
        vapor_logits(canonical_x[0]) + extrapolated_drum_alr
    )
    independent_drum_x = vapor_from_logits(independent_drum_alr)
    bottom_alr = vapor_logits(canonical_x[-1])
    position = np.linspace(0.0, 1.0, len(VOLUME_IDS))
    liquid_x = np.asarray(
        [
            vapor_from_logits(
                (1.0 - fraction) * independent_drum_alr
                + fraction * bottom_alr
            )
            for fraction in position
        ],
        dtype=float,
    )

    initial_vapor = _phase_vapor_estimate(
        provider,
        temperature_F=float(reference.base.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=independent_drum_x,
    )
    bubble = solve_local_bubble_seed(
        provider,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=independent_drum_x,
        temperature_guess_F=float(reference.base.temperature_F[0]),
        vapor_guess=initial_vapor,
        settings=bubble_settings,
    )
    if not bubble.success or bubble.residual_inf_norm > 1.0e-10:
        raise RuntimeError("DD-088 independent bubble seed did not converge")

    temperature = (
        (1.0 - position) * float(bubble.temperature_F)
        + position * float(reference.base.temperature_F[-1])
    )
    vapor_y = []
    for volume in EQUILIBRIUM_VOLUME_IDS:
        index = VOLUME_IDS.index(volume)
        vapor_y.append(
            _phase_vapor_estimate(
                provider,
                temperature_F=float(temperature[index]),
                pressure_psia=float(spec.pressure_psia[index]),
                liquid_x=liquid_x[index],
            )
        )

    interior_amount = float(
        np.exp(np.mean(np.log(reference.base.liquid_moles_lbmol[1:-1])))
    )
    liquid_moles = np.full(len(VOLUME_IDS), interior_amount, dtype=float)
    liquid_moles[0] = float(spec.terminal_liquid_targets_lbmol[0])
    liquid_moles[-1] = float(spec.terminal_liquid_targets_lbmol[1])
    liquid_flow = float(
        np.exp(
            np.mean(
                np.log(reference.base.hydraulic_liquid_flow_lbmolph)
            )
        )
    )
    vapor_flow = float(
        np.exp(np.mean(np.log(reference.base.vapor_flow_lbmolph)))
    )
    feed_total = float(np.sum(spec.feed_component_lbmolph))
    distillate = 0.5 * feed_total
    bottoms = 0.5 * feed_total

    h_liquid = float(
        provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            float(bubble.temperature_F),
            float(spec.pressure_psia[0]),
            independent_drum_x.tolist(),
        )
    )
    h_vapor_top = float(
        provider.phase_enthalpy_BTU_lbmol(
            "vapor",
            float(temperature[1]),
            float(spec.pressure_psia[1]),
            np.asarray(vapor_y[0], dtype=float).tolist(),
        )
    )
    condenser_duty = (
        (float(spec.reflux_lbmolph) + distillate) * h_liquid
        - vapor_flow * h_vapor_top
    )
    if not np.isfinite(condenser_duty) or condenser_duty >= 0.0:
        raise RuntimeError("DD-088 independent seed duty is not negative")

    point = encode_condenser_state(
        spec,
        reference,
        liquid_moles_lbmol=liquid_moles,
        liquid_mole_fraction=liquid_x,
        temperature_F=temperature,
        vapor_mole_fraction=np.asarray(vapor_y),
        hydraulic_liquid_flow_lbmolph=np.full(3, liquid_flow),
        vapor_flow_lbmolph=np.full(4, vapor_flow),
        distillate_lbmolph=distillate,
        bottoms_lbmolph=bottoms,
        bubble_vapor_mole_fraction=bubble.vapor_mole_fraction,
        condenser_duty_BTUph=condenser_duty,
    )
    diagnostic = phase_stability_diagnostics(
        provider,
        temperature_F=float(bubble.temperature_F),
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=independent_drum_x,
        bubble_y=bubble.vapor_mole_fraction,
    )
    metadata = {
        "construction": (
            "fixed 50% ALR blend of canonical drum and upper-column "
            "rectifying/feed extrapolation, smooth ALR interpolation to "
            "bottom, local bubble solve, energy duty reconstruction"
        ),
        "canonical_to_extrapolated_drum_alr_blend": 0.5,
        "drum_liquid_mole_fraction": independent_drum_x,
        "bubble_temperature_F": float(bubble.temperature_F),
        "bubble_vapor_mole_fraction": bubble.vapor_mole_fraction.copy(),
        "bubble_residual_inf_norm": float(bubble.residual_inf_norm),
        "condenser_duty_BTUph": float(condenser_duty),
        "phase_diagnostic": diagnostic,
        "partial_column_solve_used": False,
        "balance_back_calculation_used": False,
        "dd085_root_used": False,
    }
    return point, metadata


def prepare_campaign(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    provider: Any,
    settings: CondenserSteadySolveSettings,
    *,
    canonical: Sequence[float],
    perturbation: Sequence[float],
    fixed_residual_scales: Sequence[float],
) -> tuple[CampaignDefinition, dict[str, Any]]:
    smooth, metadata = independent_smooth_phase_stable_start(
        spec,
        reference,
        provider,
    )
    lower, upper = physical_bounds(spec, reference, settings)
    starts = {
        "canonical_saturated_liquid_seed": _as_vector(canonical),
        "deterministic_dd087_perturbation": _as_vector(perturbation),
        "independent_smooth_phase_stable_seed": smooth,
    }
    for name, point in starts.items():
        if point.shape != lower.shape:
            raise RuntimeError(f"DD-088 start {name!r} has invalid size")
        if np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"DD-088 start {name!r} is outside frozen bounds")
    _, physical_scales = physical_vector_and_scales(
        spec,
        reference,
        starts["canonical_saturated_liquid_seed"],
    )
    definition = CampaignDefinition(
        lower_bounds=lower,
        upper_bounds=upper,
        starts=starts,
        fixed_residual_scales=_as_vector(fixed_residual_scales),
        physical_comparison_scales=physical_scales,
    )
    return definition, metadata


def physical_vector_and_scales(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    state, condenser = decode_coordinates(spec, reference, coordinates)
    values = np.concatenate(
        (
            state.liquid_moles_lbmol,
            state.liquid_mole_fraction.reshape((-1,)),
            state.temperature_F,
            state.vapor_mole_fraction.reshape((-1,)),
            state.hydraulic_liquid_flow_lbmolph,
            state.vapor_flow_lbmolph,
            [state.distillate_lbmolph, state.bottoms_lbmolph],
            condenser.bubble_vapor_mole_fraction,
            [condenser.condenser_duty_BTUph],
        )
    )
    scales = np.concatenate(
        (
            np.maximum(reference.base.liquid_moles_lbmol, 1.0),
            np.ones(state.liquid_mole_fraction.size),
            np.full(state.temperature_F.size, float(spec.temperature_scale_F)),
            np.ones(state.vapor_mole_fraction.size),
            np.maximum(reference.base.hydraulic_liquid_flow_lbmolph, 1.0),
            np.maximum(reference.base.vapor_flow_lbmolph, 1.0),
            [
                max(float(reference.base.distillate_lbmolph), 1.0),
                max(float(reference.base.bottoms_lbmolph), 1.0),
            ],
            np.ones(condenser.bubble_vapor_mole_fraction.size),
            [max(abs(reference.condenser_duty_reference_BTUph), 1.0)],
        )
    )
    return values, scales


def central_difference_jacobian(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    step: float,
) -> np.ndarray:
    point = _as_vector(coordinates)
    matrix = np.empty((point.size, point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = evaluate_residual(
            spec,
            reference,
            provider,
            point + delta,
            fixed_scales=fixed_scales,
        ).scaled
        minus = evaluate_residual(
            spec,
            reference,
            provider,
            point - delta,
            fixed_scales=fixed_scales,
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    return matrix


def block_norms(evaluation: Any) -> dict[str, float]:
    values: dict[str, float] = {}
    for block in dict.fromkeys(row.block for row in evaluation.rows):
        indices = [
            index
            for index, row in enumerate(evaluation.rows)
            if row.block == block
        ]
        values[block] = float(np.max(np.abs(evaluation.scaled[indices])))
    return values


def movement_by_family(
    spec: EnergyOwnedOperatingSpec,
    initial: Sequence[float],
    final: Sequence[float],
) -> dict[str, float]:
    layout = coordinate_layout(spec)
    delta = np.abs(_as_vector(final) - _as_vector(initial))
    base_layout = layout
    return {
        "liquid_moles": float(np.max(delta[0:5])),
        "liquid_composition": float(np.max(delta[5:15])),
        "temperature": float(np.max(delta[15:20])),
        "column_vapor_composition": float(np.max(delta[20:28])),
        "liquid_flow": float(np.max(delta[28:31])),
        "vapor_flow": float(np.max(delta[31:35])),
        "products": float(np.max(delta[35:37])),
        "bubble_vapor_composition": float(
            np.max(delta[base_layout.bubble_logits])
        ),
        "condenser_duty": float(delta[base_layout.condenser_duty]),
    }


def _phase_pass(
    diagnostics: Mapping[str, Any],
    settings: CondenserSteadySolveSettings,
) -> bool:
    return bool(
        abs(float(diagnostics["bubble_sum_xK_minus_one"]))
        <= settings.bubble_sum_tolerance
        and float(diagnostics["vapor_fraction"])
        <= settings.bubble_vapor_fraction_tolerance
        and float(diagnostics["bubble_y_minus_Kx_max_abs"])
        <= settings.bubble_composition_tolerance
    )


def execute_start(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    provider: Any,
    *,
    name: str,
    initial: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    fixed_scales: Sequence[float],
    settings: CondenserSteadySolveSettings,
) -> dict[str, Any]:
    point0 = _as_vector(initial)
    lower = _as_vector(lower_bounds)
    upper = _as_vector(upper_bounds)
    initial_evaluation = evaluate_residual(
        spec,
        reference,
        provider,
        point0,
        fixed_scales=fixed_scales,
    )
    started = time.perf_counter()

    def objective(point: np.ndarray) -> np.ndarray:
        return evaluate_residual(
            spec,
            reference,
            provider,
            point,
            fixed_scales=fixed_scales,
        ).scaled

    def jacobian(point: np.ndarray) -> np.ndarray:
        return central_difference_jacobian(
            spec,
            reference,
            provider,
            point,
            fixed_scales=fixed_scales,
            step=settings.jacobian_step,
        )

    result = least_squares(
        objective,
        point0,
        jac=jacobian,
        bounds=(lower, upper),
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=settings.x_scale,
    )
    wall_clock_sec = float(time.perf_counter() - started)
    endpoint = evaluate_residual(
        spec,
        reference,
        provider,
        result.x,
        fixed_scales=fixed_scales,
    )
    jacobians = [
        audit_numerical_jacobian(
            spec,
            reference,
            provider,
            result.x,
            fixed_scales=fixed_scales,
            step=step,
            coupling_tolerance=settings.jacobian_coupling_tolerance,
        )
        for step in settings.endpoint_jacobian_steps
    ]
    distance = np.minimum(result.x - lower, upper - result.x)
    state = endpoint.base.state
    properties = endpoint.base.properties
    condenser = endpoint.condenser
    heights = np.asarray(
        [
            properties.liquid_height_ft[VOLUME_IDS.index(volume)]
            for volume in HYDRAULIC_VOLUME_IDS
        ]
    )
    spacings = np.asarray(
        [geometry.tray_spacing_ft for geometry in spec.hydraulic_geometry]
    )
    phase = phase_stability_diagnostics(
        provider,
        temperature_F=float(state.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=state.liquid_mole_fraction[0],
        bubble_y=condenser.bubble_vapor_mole_fraction,
    )
    bubble_norm = block_norms(endpoint)["condenser_saturated_liquid"]
    composition_floor_pass = bool(
        np.all(state.liquid_mole_fraction >= settings.composition_floor)
        and np.all(state.vapor_mole_fraction >= settings.composition_floor)
        and np.all(
            condenser.bubble_vapor_mole_fraction >= settings.composition_floor
        )
    )
    normalized = bool(
        np.allclose(np.sum(state.liquid_mole_fraction, axis=1), 1.0, atol=1e-12)
        and np.allclose(np.sum(state.vapor_mole_fraction, axis=1), 1.0, atol=1e-12)
        and np.isclose(
            np.sum(condenser.bubble_vapor_mole_fraction),
            1.0,
            atol=1e-12,
        )
    )
    jacobian_pass = bool(
        all(
            audit.rank == 40
            and audit.condition < settings.jacobian_condition_hard_stop
            and audit.bubble_rank == 3
            and not audit.zero_rows
            and not audit.zero_columns
            and not audit.unexpected_couplings
            and not audit.bubble_zero_rows
            and not audit.bubble_zero_columns
            for audit in jacobians
        )
    )
    phase_pass = bool(
        bubble_norm < settings.bubble_residual_tolerance
        and _phase_pass(phase, settings)
    )
    no_active_bound = bool(
        np.min(distance) > settings.active_bound_tolerance
    )
    physical_pass = bool(
        np.all(np.isfinite(endpoint.raw))
        and np.all(np.isfinite(properties.liquid_enthalpy_BTU_lbmol))
        and np.all(np.isfinite(properties.vapor_enthalpy_BTU_lbmol[1:]))
        and np.all(np.isfinite(properties.liquid_density_lbmol_ft3))
        and np.all(properties.liquid_density_lbmol_ft3 > 0.0)
        and np.all(state.liquid_moles_lbmol > 0.0)
        and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(state.vapor_flow_lbmolph > 0.0)
        and state.distillate_lbmolph > 0.0
        and state.bottoms_lbmolph > 0.0
        and condenser.condenser_duty_BTUph < 0.0
        and composition_floor_pass
        and normalized
        and np.all(np.diff(state.temperature_F) > 0.0)
        and np.all(heights < spacings)
        and not endpoint.base.clipping_or_projection_used
        and not endpoint.base.property_fallback_used
    )
    residual_pass = bool(
        np.max(np.abs(endpoint.scaled)) < settings.residual_inf_tolerance
    )
    conservation_pass = bool(
        endpoint.base.component_telescoping_relative_error
        < settings.component_conservation_tolerance
        and endpoint.base.energy_telescoping_relative_error
        < settings.energy_conservation_tolerance
    )
    residence_times = np.asarray(
        (
            state.liquid_moles_lbmol[0]
            / (float(spec.reflux_lbmolph) + state.distillate_lbmolph),
            state.liquid_moles_lbmol[1]
            / state.hydraulic_liquid_flow_lbmolph[0],
            state.liquid_moles_lbmol[2]
            / state.hydraulic_liquid_flow_lbmolph[1],
            state.liquid_moles_lbmol[3]
            / state.hydraulic_liquid_flow_lbmolph[2],
            state.liquid_moles_lbmol[4] / state.bottoms_lbmolph,
        )
    ) * 3600.0
    return {
        "name": name,
        "success_flag": bool(result.success),
        "status": int(result.status),
        "termination_reason": str(result.message),
        "nfev": int(result.nfev),
        "njev": None if result.njev is None else int(result.njev),
        "wall_clock_sec": wall_clock_sec,
        "initial_coordinates": point0,
        "final_coordinates": result.x.copy(),
        "initial_residual_inf_norm": float(
            np.max(np.abs(initial_evaluation.scaled))
        ),
        "final_residual_inf_norm": float(np.max(np.abs(endpoint.scaled))),
        "initial_block_norms": block_norms(initial_evaluation),
        "final_block_norms": block_norms(endpoint),
        "movement_by_coordinate_family": movement_by_family(
            spec,
            point0,
            result.x,
        ),
        "minimum_transformed_bound_distance": float(np.min(distance)),
        "active_bound_indices": np.flatnonzero(
            distance <= settings.active_bound_tolerance
        ),
        "endpoint_evaluation": endpoint,
        "endpoint_jacobians": jacobians,
        "phase_diagnostic": phase,
        "liquid_heights_ft": heights,
        "tray_spacings_ft": spacings,
        "residence_times_sec": residence_times,
        "residual_pass": residual_pass,
        "jacobian_pass": jacobian_pass,
        "conservation_pass": conservation_pass,
        "phase_pass": phase_pass,
        "physical_pass": physical_pass,
        "no_active_bound": no_active_bound,
        "start_pass": bool(
            result.success
            and residual_pass
            and jacobian_pass
            and conservation_pass
            and phase_pass
            and physical_pass
            and no_active_bound
        ),
    }


def pairwise_root_agreement(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    endpoints: Mapping[str, Sequence[float]],
    physical_scales: Sequence[float],
) -> dict[str, float]:
    names = tuple(endpoints)
    scales = _as_vector(physical_scales)
    physical = {
        name: physical_vector_and_scales(
            spec,
            reference,
            endpoints[name],
        )[0]
        for name in names
    }
    comparisons: dict[str, float] = {}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            denominator = np.maximum(
                np.maximum(np.abs(physical[left]), np.abs(physical[right])),
                scales,
            )
            comparisons[f"{left}__vs__{right}"] = float(
                np.max(np.abs(physical[left] - physical[right]) / denominator)
            )
    return comparisons


__all__ = [
    "CondenserSteadySolveSettings",
    "block_norms",
    "central_difference_jacobian",
    "encode_condenser_state",
    "execute_start",
    "independent_smooth_phase_stable_start",
    "movement_by_family",
    "pairwise_root_agreement",
    "physical_bounds",
    "physical_vector_and_scales",
    "prepare_campaign",
]
