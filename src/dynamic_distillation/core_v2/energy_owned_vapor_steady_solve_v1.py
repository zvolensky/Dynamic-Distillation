"""Frozen DD-085 steady-root campaign for the energy-owned vapor model."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedOperatingSpec,
    EnergyOwnedReference,
    ResidualEvaluation,
    audit_numerical_jacobian,
    audit_points,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
)
from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
    vapor_logits,
)


@dataclass(frozen=True)
class SteadySolveSettings:
    method: str = "trf"
    jacobian_step: float = 1.0e-5
    endpoint_jacobian_steps: tuple[float, float] = (1.0e-5, 5.0e-6)
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 500
    x_scale: float = 1.0
    residual_inf_tolerance: float = 1.0e-8
    root_agreement_tolerance: float = 1.0e-7
    active_bound_tolerance: float = 1.0e-6
    component_conservation_tolerance: float = 1.0e-12
    energy_conservation_tolerance: float = 1.0e-10
    jacobian_condition_hard_stop: float = 1.0e8
    jacobian_coupling_tolerance: float = 1.0e-7
    composition_floor: float = 1.0e-10
    temperature_min_F: float = 110.0
    temperature_max_F: float = 260.0
    terminal_amount_min_ratio: float = 0.8
    terminal_amount_max_ratio: float = 1.2
    interior_amount_min_ratio: float = 0.2
    interior_amount_max_ratio: float = 2.0
    internal_flow_min_ratio: float = 0.1
    internal_flow_max_ratio: float = 5.0
    product_feed_min_ratio: float = 1.0e-4
    product_feed_max_ratio: float = 1.05


@dataclass(frozen=True)
class CampaignDefinition:
    lower_bounds: np.ndarray
    upper_bounds: np.ndarray
    starts: Mapping[str, np.ndarray]
    fixed_residual_scales: np.ndarray
    physical_comparison_scales: np.ndarray


def _as_vector(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=float).reshape((-1,))


def encode_state(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    *,
    liquid_moles_lbmol: Sequence[float],
    liquid_mole_fraction: Sequence[Sequence[float]],
    temperature_F: Sequence[float],
    vapor_mole_fraction: Sequence[Sequence[float]],
    hydraulic_liquid_flow_lbmolph: Sequence[float],
    vapor_flow_lbmolph: Sequence[float],
    distillate_lbmolph: float,
    bottoms_lbmolph: float,
) -> np.ndarray:
    """Encode a physical state using the unchanged DD-084 transforms."""
    layout = coordinate_layout(spec)
    point = np.empty(len(layout.names), dtype=float)
    liquid_moles = _as_vector(liquid_moles_lbmol)
    liquid_x = np.asarray(liquid_mole_fraction, dtype=float)
    temperature = _as_vector(temperature_F)
    vapor_y = np.asarray(vapor_mole_fraction, dtype=float)
    liquid_flow = _as_vector(hydraulic_liquid_flow_lbmolph)
    vapor_flow = _as_vector(vapor_flow_lbmolph)
    if (
        liquid_moles.shape != np.asarray(reference.liquid_moles_lbmol).shape
        or liquid_x.shape != np.asarray(reference.liquid_mole_fraction).shape
        or temperature.shape != np.asarray(reference.temperature_F).shape
        or vapor_y.shape != np.asarray(reference.vapor_mole_fraction).shape
        or liquid_flow.shape
        != np.asarray(reference.hydraulic_liquid_flow_lbmolph).shape
        or vapor_flow.shape != np.asarray(reference.vapor_flow_lbmolph).shape
    ):
        raise ValueError("DD-085 physical state shape is invalid")
    positive = (
        liquid_moles,
        liquid_x,
        vapor_y,
        liquid_flow,
        vapor_flow,
        np.asarray([distillate_lbmolph, bottoms_lbmolph], dtype=float),
    )
    if any(np.any(~np.isfinite(values)) or np.any(values <= 0) for values in positive):
        raise ValueError("DD-085 physical state must be finite and positive")

    point[layout.liquid_moles] = np.log(
        liquid_moles / np.asarray(reference.liquid_moles_lbmol, dtype=float)
    )
    point[layout.liquid_logits] = np.concatenate(
        [
            vapor_logits(normalize_composition(values))
            - vapor_logits(normalize_composition(reference_values))
            for values, reference_values in zip(
                liquid_x,
                reference.liquid_mole_fraction,
            )
        ]
    )
    point[layout.temperature] = (
        temperature - np.asarray(reference.temperature_F, dtype=float)
    ) / float(spec.temperature_scale_F)
    point[layout.vapor_logits] = np.concatenate(
        [
            vapor_logits(normalize_composition(values))
            - vapor_logits(normalize_composition(reference_values))
            for values, reference_values in zip(
                vapor_y,
                reference.vapor_mole_fraction,
            )
        ]
    )
    point[layout.liquid_flows] = np.log(
        liquid_flow
        / np.asarray(reference.hydraulic_liquid_flow_lbmolph, dtype=float)
    )
    point[layout.vapor_flows] = np.log(
        vapor_flow / np.asarray(reference.vapor_flow_lbmolph, dtype=float)
    )
    point[layout.distillate] = np.log(
        float(distillate_lbmolph) / float(reference.distillate_lbmolph)
    )
    point[layout.bottoms] = np.log(
        float(bottoms_lbmolph) / float(reference.bottoms_lbmolph)
    )
    return point


def physical_bounds(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    settings: SteadySolveSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert the frozen DD-085 physical bounds to DD-084 coordinates."""
    layout = coordinate_layout(spec)
    lower = np.full(len(layout.names), -np.inf, dtype=float)
    upper = np.full(len(layout.names), np.inf, dtype=float)

    reference_moles = np.asarray(reference.liquid_moles_lbmol, dtype=float)
    lower_moles = settings.interior_amount_min_ratio * reference_moles
    upper_moles = settings.interior_amount_max_ratio * reference_moles
    lower_moles[[0, -1]] = settings.terminal_amount_min_ratio * np.asarray(
        spec.terminal_liquid_targets_lbmol,
        dtype=float,
    )
    upper_moles[[0, -1]] = settings.terminal_amount_max_ratio * np.asarray(
        spec.terminal_liquid_targets_lbmol,
        dtype=float,
    )
    lower[layout.liquid_moles] = np.log(lower_moles / reference_moles)
    upper[layout.liquid_moles] = np.log(upper_moles / reference_moles)

    component_count = len(spec.component_names)
    floor = float(settings.composition_floor)
    maximum = 1.0 - (component_count - 1) * floor
    alr_min = float(np.log(floor / maximum))
    alr_max = float(np.log(maximum / floor))
    liquid_reference_alr = np.concatenate(
        [vapor_logits(values) for values in reference.liquid_mole_fraction]
    )
    vapor_reference_alr = np.concatenate(
        [vapor_logits(values) for values in reference.vapor_mole_fraction]
    )
    lower[layout.liquid_logits] = alr_min - liquid_reference_alr
    upper[layout.liquid_logits] = alr_max - liquid_reference_alr
    lower[layout.vapor_logits] = alr_min - vapor_reference_alr
    upper[layout.vapor_logits] = alr_max - vapor_reference_alr

    reference_temperature = np.asarray(reference.temperature_F, dtype=float)
    lower[layout.temperature] = (
        settings.temperature_min_F - reference_temperature
    ) / float(spec.temperature_scale_F)
    upper[layout.temperature] = (
        settings.temperature_max_F - reference_temperature
    ) / float(spec.temperature_scale_F)
    lower[layout.liquid_flows] = np.log(settings.internal_flow_min_ratio)
    upper[layout.liquid_flows] = np.log(settings.internal_flow_max_ratio)
    lower[layout.vapor_flows] = np.log(settings.internal_flow_min_ratio)
    upper[layout.vapor_flows] = np.log(settings.internal_flow_max_ratio)

    feed_total = float(np.sum(spec.feed_component_lbmolph))
    product_min = settings.product_feed_min_ratio * feed_total
    product_max = settings.product_feed_max_ratio * feed_total
    lower[layout.distillate] = np.log(
        product_min / float(reference.distillate_lbmolph)
    )
    upper[layout.distillate] = np.log(
        product_max / float(reference.distillate_lbmolph)
    )
    lower[layout.bottoms] = np.log(
        product_min / float(reference.bottoms_lbmolph)
    )
    upper[layout.bottoms] = np.log(
        product_max / float(reference.bottoms_lbmolph)
    )
    if (
        np.any(~np.isfinite(lower))
        or np.any(~np.isfinite(upper))
        or np.any(lower >= upper)
    ):
        raise RuntimeError("DD-085 transformed bounds are invalid")
    return lower, upper


def independent_smooth_start(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    provider: Any,
) -> np.ndarray:
    """Build the frozen independent seed without solving or back-calculation."""
    position = np.linspace(0.0, 1.0, len(VOLUME_IDS))
    temperature = (
        (1.0 - position) * float(reference.temperature_F[0])
        + position * float(reference.temperature_F[-1])
    )
    endpoint_alr = np.asarray(
        (
            vapor_logits(reference.liquid_mole_fraction[0]),
            vapor_logits(reference.liquid_mole_fraction[-1]),
        ),
        dtype=float,
    )
    liquid_x = np.asarray(
        [
            normalize_composition(
                np.concatenate(
                    (
                        np.exp(
                            (1.0 - fraction) * endpoint_alr[0]
                            + fraction * endpoint_alr[1]
                        ),
                        [1.0],
                    )
                )
            )
            for fraction in position
        ],
        dtype=float,
    )
    interior_amount = float(
        np.exp(np.mean(np.log(reference.liquid_moles_lbmol[1:-1])))
    )
    liquid_moles = np.full(len(VOLUME_IDS), interior_amount, dtype=float)
    liquid_moles[0] = float(spec.terminal_liquid_targets_lbmol[0])
    liquid_moles[-1] = float(spec.terminal_liquid_targets_lbmol[1])

    vapor_y = []
    for volume in EQUILIBRIUM_VOLUME_IDS:
        index = VOLUME_IDS.index(volume)
        x = liquid_x[index]
        phi_liquid = np.asarray(
            provider.phase_fugacity_coefficients(
                "liquid",
                float(temperature[index]),
                float(spec.pressure_psia[index]),
                x.tolist(),
            ),
            dtype=float,
        )
        phi_vapor = np.asarray(
            provider.phase_fugacity_coefficients(
                "vapor",
                float(temperature[index]),
                float(spec.pressure_psia[index]),
                x.tolist(),
            ),
            dtype=float,
        )
        vapor_y.append(normalize_composition(x * phi_liquid / phi_vapor))

    liquid_magnitude = float(
        np.exp(np.mean(np.log(reference.hydraulic_liquid_flow_lbmolph)))
    )
    vapor_magnitude = float(
        np.exp(np.mean(np.log(reference.vapor_flow_lbmolph)))
    )
    feed_total = float(np.sum(spec.feed_component_lbmolph))
    return encode_state(
        spec,
        reference,
        liquid_moles_lbmol=liquid_moles,
        liquid_mole_fraction=liquid_x,
        temperature_F=temperature,
        vapor_mole_fraction=np.asarray(vapor_y, dtype=float),
        hydraulic_liquid_flow_lbmolph=np.full(3, liquid_magnitude),
        vapor_flow_lbmolph=np.full(4, vapor_magnitude),
        distillate_lbmolph=0.5 * feed_total,
        bottoms_lbmolph=0.5 * feed_total,
    )


def physical_vector_and_scales(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    state = decode_coordinates(spec, reference, coordinates)
    values = np.concatenate(
        (
            state.liquid_moles_lbmol,
            state.liquid_mole_fraction.reshape((-1,)),
            state.temperature_F,
            state.vapor_mole_fraction.reshape((-1,)),
            state.hydraulic_liquid_flow_lbmolph,
            state.vapor_flow_lbmolph,
            [state.distillate_lbmolph, state.bottoms_lbmolph],
        )
    )
    scales = np.concatenate(
        (
            np.maximum(np.asarray(reference.liquid_moles_lbmol), 1.0),
            np.ones(state.liquid_mole_fraction.size),
            np.full(state.temperature_F.size, float(spec.temperature_scale_F)),
            np.ones(state.vapor_mole_fraction.size),
            np.maximum(reference.hydraulic_liquid_flow_lbmolph, 1.0),
            np.maximum(reference.vapor_flow_lbmolph, 1.0),
            [
                max(float(reference.distillate_lbmolph), 1.0),
                max(float(reference.bottoms_lbmolph), 1.0),
            ],
        )
    )
    return values, scales


def prepare_campaign(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    provider: Any,
    settings: SteadySolveSettings,
) -> CampaignDefinition:
    points = audit_points(spec)
    canonical = points["canonical_role_mapped_seed"].copy()
    perturbation = points["deterministic_combined_perturbation"].copy()
    smooth = independent_smooth_start(spec, reference, provider)
    lower, upper = physical_bounds(spec, reference, settings)
    starts = {
        "canonical_role_mapped_seed": canonical,
        "deterministic_combined_perturbation": perturbation,
        "independent_smooth_physical_seed": smooth,
    }
    for name, point in starts.items():
        if np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"DD-085 start {name!r} is outside frozen bounds")
    canonical_evaluation = evaluate_residual(spec, reference, provider, canonical)
    _, physical_scales = physical_vector_and_scales(spec, reference, canonical)
    return CampaignDefinition(
        lower_bounds=lower,
        upper_bounds=upper,
        starts=starts,
        fixed_residual_scales=canonical_evaluation.scales.copy(),
        physical_comparison_scales=physical_scales,
    )


def central_difference_jacobian(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
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


def block_norms(evaluation: ResidualEvaluation) -> dict[str, float]:
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
    return {
        "liquid_moles": float(np.max(delta[layout.liquid_moles])),
        "liquid_composition": float(np.max(delta[layout.liquid_logits])),
        "temperature": float(np.max(delta[layout.temperature])),
        "vapor_composition": float(np.max(delta[layout.vapor_logits])),
        "liquid_flow": float(np.max(delta[layout.liquid_flows])),
        "vapor_flow": float(np.max(delta[layout.vapor_flows])),
        "products": float(
            max(delta[layout.distillate], delta[layout.bottoms])
        ),
    }


def execute_start(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    provider: Any,
    *,
    name: str,
    initial: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    fixed_scales: Sequence[float],
    settings: SteadySolveSettings,
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
    singular_values = [
        np.linalg.svd(audit.matrix, compute_uv=False) for audit in jacobians
    ]
    distance = np.minimum(result.x - lower, upper - result.x)
    state = endpoint.state
    properties = endpoint.properties
    heights = np.asarray(
        [
            properties.liquid_height_ft[VOLUME_IDS.index(volume)]
            for volume in HYDRAULIC_VOLUME_IDS
        ],
        dtype=float,
    )
    spacings = np.asarray(
        [geometry.tray_spacing_ft for geometry in spec.hydraulic_geometry],
        dtype=float,
    )
    temperature_ordered = bool(np.all(np.diff(state.temperature_F) > 0.0))
    composition_floor_pass = bool(
        np.all(state.liquid_mole_fraction >= settings.composition_floor)
        and np.all(state.vapor_mole_fraction >= settings.composition_floor)
    )
    normalized_compositions = bool(
        np.allclose(np.sum(state.liquid_mole_fraction, axis=1), 1.0, atol=1e-12)
        and np.allclose(np.sum(state.vapor_mole_fraction, axis=1), 1.0, atol=1e-12)
    )
    jacobian_pass = bool(
        all(
            audit.rank == result.x.size
            and audit.condition < settings.jacobian_condition_hard_stop
            and not audit.zero_rows
            and not audit.zero_columns
            and not audit.unexpected_couplings
            for audit in jacobians
        )
    )
    no_active_bound = bool(np.min(distance) > settings.active_bound_tolerance)
    physical_pass = bool(
        np.all(np.isfinite(endpoint.raw))
        and np.all(state.liquid_moles_lbmol > 0.0)
        and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(state.vapor_flow_lbmolph > 0.0)
        and state.distillate_lbmolph > 0.0
        and state.bottoms_lbmolph > 0.0
        and composition_floor_pass
        and normalized_compositions
        and temperature_ordered
        and np.all(heights < spacings)
        and not endpoint.clipping_or_projection_used
        and not endpoint.property_fallback_used
    )
    residual_pass = bool(
        np.max(np.abs(endpoint.scaled)) < settings.residual_inf_tolerance
    )
    conservation_pass = bool(
        endpoint.component_telescoping_relative_error
        < settings.component_conservation_tolerance
        and endpoint.energy_telescoping_relative_error
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
        "endpoint_singular_values": singular_values,
        "liquid_heights_ft": heights,
        "tray_spacings_ft": spacings,
        "residence_times_sec": residence_times,
        "residual_pass": residual_pass,
        "jacobian_pass": jacobian_pass,
        "conservation_pass": conservation_pass,
        "physical_pass": physical_pass,
        "no_active_bound": no_active_bound,
        "start_pass": bool(
            residual_pass
            and jacobian_pass
            and conservation_pass
            and physical_pass
            and no_active_bound
        ),
    }


def pairwise_root_agreement(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
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
    "CampaignDefinition",
    "SteadySolveSettings",
    "block_norms",
    "central_difference_jacobian",
    "encode_state",
    "execute_start",
    "independent_smooth_start",
    "movement_by_family",
    "pairwise_root_agreement",
    "physical_bounds",
    "physical_vector_and_scales",
    "prepare_campaign",
]
