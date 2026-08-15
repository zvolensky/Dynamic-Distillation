"""Frozen Core V3 steady-root campaign definitions and execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    BubbleSolveSettings,
    NumericalReference,
    OperatingSpec,
    PhysicalState,
    alr_coordinates,
    audit_colored_numerical_jacobian,
    audit_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    encode_state,
    evaluate_residual,
    normalize_composition,
    solve_local_bubble,
    structural_pattern,
)


@dataclass(frozen=True)
class SteadyRootSettings:
    method: str = "trf"
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 500
    x_scale: float = 1.0
    jacobian_mode: str = "uncolored"
    solve_jacobian_step: float = 1.0e-5
    endpoint_jacobian_steps: tuple[float, float] = (1.0e-5, 5.0e-6)
    jacobian_coupling_tolerance: float = 1.0e-7
    jacobian_condition_hard_stop: float = 1.0e8
    singular_value_relative_stability_tolerance: float = 0.25
    residual_inf_tolerance: float = 1.0e-8
    fugacity_residual_tolerance: float = 1.0e-10
    common_root_tolerance: float = 1.0e-7
    component_conservation_tolerance: float = 1.0e-12
    energy_conservation_tolerance: float = 1.0e-10
    bubble_residual_tolerance: float = 1.0e-10
    independent_pr_temperature_tolerance_F: float = 1.0e-3
    independent_pr_composition_tolerance: float = 1.0e-6
    tp_flash_vapor_fraction_tolerance: float = 1.0e-3
    tp_flash_internal_tolerance: float = 1.0e-12
    active_bound_tolerance: float = 1.0e-6
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
    condenser_duty_min_abs_ratio: float = 0.1
    condenser_duty_max_abs_ratio: float = 3.0


@dataclass(frozen=True)
class CampaignDefinition:
    lower_bounds: np.ndarray
    upper_bounds: np.ndarray
    starts: Mapping[str, np.ndarray]
    fixed_residual_scales: np.ndarray
    physical_comparison_scales: np.ndarray


def _vector(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=float).reshape((-1,))


def _composition_coordinate_bounds(
    reference_composition: np.ndarray,
    floor: float,
) -> tuple[np.ndarray, np.ndarray]:
    component_count = int(reference_composition.size)
    maximum = 1.0 - (component_count - 1) * float(floor)
    minimum_alr = float(np.log(float(floor) / maximum))
    maximum_alr = float(np.log(maximum / float(floor)))
    reference_alr = alr_coordinates(reference_composition)
    return (
        np.full(component_count - 1, minimum_alr) - reference_alr,
        np.full(component_count - 1, maximum_alr) - reference_alr,
    )


def physical_bounds(
    spec: OperatingSpec,
    reference: NumericalReference,
    settings: SteadyRootSettings,
) -> tuple[np.ndarray, np.ndarray]:
    layout = coordinate_layout(spec)
    lower = np.empty(len(layout.names), dtype=float)
    upper = np.empty(len(layout.names), dtype=float)

    amount_lower = np.asarray(reference.liquid_moles_lbmol, dtype=float).copy()
    amount_upper = amount_lower.copy()
    amount_lower[0] = (
        settings.terminal_amount_min_ratio
        * float(spec.terminal_liquid_targets_lbmol[0])
    )
    amount_upper[0] = (
        settings.terminal_amount_max_ratio
        * float(spec.terminal_liquid_targets_lbmol[0])
    )
    amount_lower[-1] = (
        settings.terminal_amount_min_ratio
        * float(spec.terminal_liquid_targets_lbmol[1])
    )
    amount_upper[-1] = (
        settings.terminal_amount_max_ratio
        * float(spec.terminal_liquid_targets_lbmol[1])
    )
    amount_lower[1:-1] *= settings.interior_amount_min_ratio
    amount_upper[1:-1] *= settings.interior_amount_max_ratio
    lower[layout.liquid_moles] = np.log(
        amount_lower / reference.liquid_moles_lbmol
    )
    upper[layout.liquid_moles] = np.log(
        amount_upper / reference.liquid_moles_lbmol
    )

    offset = layout.liquid_alr.start
    for composition in reference.liquid_mole_fraction:
        lo, hi = _composition_coordinate_bounds(
            np.asarray(composition, dtype=float),
            settings.composition_floor,
        )
        lower[offset : offset + lo.size] = lo
        upper[offset : offset + hi.size] = hi
        offset += lo.size

    lower[layout.temperature] = (
        settings.temperature_min_F - reference.temperature_F
    ) / float(spec.temperature_scale_F)
    upper[layout.temperature] = (
        settings.temperature_max_F - reference.temperature_F
    ) / float(spec.temperature_scale_F)

    offset = layout.vapor_alr.start
    for composition in reference.vapor_mole_fraction:
        lo, hi = _composition_coordinate_bounds(
            np.asarray(composition, dtype=float),
            settings.composition_floor,
        )
        lower[offset : offset + lo.size] = lo
        upper[offset : offset + hi.size] = hi
        offset += lo.size

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

    lo, hi = _composition_coordinate_bounds(
        np.asarray(reference.bubble_vapor_mole_fraction, dtype=float),
        settings.composition_floor,
    )
    lower[layout.bubble_alr] = lo
    upper[layout.bubble_alr] = hi

    duty_abs = abs(float(reference.condenser_duty_reference_BTUph))
    duty_lower = -settings.condenser_duty_max_abs_ratio * duty_abs
    duty_upper = -settings.condenser_duty_min_abs_ratio * duty_abs
    duty_reference = float(reference.condenser_duty_reference_BTUph)
    duty_scale = float(reference.condenser_duty_scale_BTUph)
    lower[layout.condenser_duty] = (
        duty_lower - duty_reference
    ) / duty_scale
    upper[layout.condenser_duty] = (
        duty_upper - duty_reference
    ) / duty_scale

    if (
        lower.shape != (len(layout.names),)
        or upper.shape != (len(layout.names),)
        or np.any(~np.isfinite(lower))
        or np.any(~np.isfinite(upper))
        or np.any(lower >= upper)
    ):
        raise RuntimeError("Core V3 steady-root bounds are invalid")
    return lower, upper


def _direct_vapor_estimate(
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: np.ndarray,
    state_id: str,
    caller: str,
) -> np.ndarray:
    phi_liquid = call_audit.direct_phase_fugacity(
        provider,
        phase="liquid",
        temperature_F=temperature_F,
        pressure_psia=pressure_psia,
        composition=liquid_x,
        quantity="bubble_temperature_and_incipient_vapor",
        caller=caller,
        state_id=state_id,
        evaluation_kind="preparation",
    )
    phi_vapor = call_audit.direct_phase_fugacity(
        provider,
        phase="vapor",
        temperature_F=temperature_F,
        pressure_psia=pressure_psia,
        composition=liquid_x,
        quantity="bubble_temperature_and_incipient_vapor",
        caller=caller,
        state_id=state_id,
        evaluation_kind="preparation",
    )
    return normalize_composition(liquid_x * phi_liquid / phi_vapor)


def independent_smooth_start(
    spec: OperatingSpec,
    reference: NumericalReference,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    bubble_settings: BubbleSolveSettings = BubbleSolveSettings(),
) -> tuple[np.ndarray, dict[str, Any]]:
    """Construct a fully distinct smooth seed without balance solving."""
    state_id = "independent_smooth_topology_seed"
    topology = spec.topology
    volumes = topology.volume_ids
    feed_x = normalize_composition(spec.feed_component_lbmolph)
    canonical_x = np.asarray(reference.liquid_mole_fraction, dtype=float)
    top_alr = (
        0.72 * alr_coordinates(canonical_x[0])
        + 0.28 * alr_coordinates(feed_x)
        + np.linspace(0.08, -0.04, len(spec.component_names) - 1)
    )
    bottom_alr = (
        0.72 * alr_coordinates(canonical_x[-1])
        + 0.28 * alr_coordinates(feed_x)
        + np.linspace(-0.05, 0.07, len(spec.component_names) - 1)
    )
    position = np.linspace(0.0, 1.0, len(volumes))
    liquid_x = np.asarray(
        [
            normalize_composition(
                np.append(np.exp((1.0 - fraction) * top_alr + fraction * bottom_alr), 1.0)
            )
            for fraction in position
        ],
        dtype=float,
    )

    bubble_guess = _direct_vapor_estimate(
        provider,
        call_audit,
        temperature_F=float(reference.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=liquid_x[0],
        state_id=state_id,
        caller="independent_drum_bubble_guess",
    )
    bubble = solve_local_bubble(
        provider,
        call_audit,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=liquid_x[0],
        temperature_guess_F=float(reference.temperature_F[0]),
        vapor_guess=bubble_guess,
        state_id=state_id,
        evaluation_kind="preparation",
        settings=bubble_settings,
    )
    if not bubble.success or bubble.residual_inf_norm >= 1.0e-10:
        raise RuntimeError("independent Core V3 bubble reconstruction failed")

    bottom_temperature = min(
        245.0,
        max(float(reference.temperature_F[-1]), bubble.temperature_F + 35.0),
    )
    temperature = (
        (1.0 - position) * float(bubble.temperature_F)
        + position * bottom_temperature
    )
    vapor_y = np.asarray(
        [
            _direct_vapor_estimate(
                provider,
                call_audit,
                temperature_F=float(temperature[index]),
                pressure_psia=float(spec.pressure_psia[index]),
                liquid_x=liquid_x[index],
                state_id=state_id,
                caller=f"independent_column_vapor_guess[{volumes[index]}]",
            )
            for index in range(1, len(volumes))
        ],
        dtype=float,
    )

    liquid_moles = np.asarray(reference.liquid_moles_lbmol, dtype=float).copy()
    liquid_moles[0] = float(spec.terminal_liquid_targets_lbmol[0])
    liquid_moles[-1] = float(spec.terminal_liquid_targets_lbmol[1])
    interior_count = len(topology.hydraulic_volume_ids)
    liquid_moles[1:-1] *= 0.97 + 0.15 * np.sin(
        np.arange(1, interior_count + 1, dtype=float)
    )
    liquid_flows = np.exp(
        np.mean(np.log(reference.hydraulic_liquid_flow_lbmolph))
    ) * (
        0.97
        + 0.10 * np.sin(np.arange(1, interior_count + 1, dtype=float) + 0.4)
    )
    vapor_count = len(topology.vapor_links)
    vapor_flows = np.exp(
        np.mean(np.log(reference.vapor_flow_lbmolph))
    ) * (
        1.01
        + 0.08 * np.cos(np.arange(1, vapor_count + 1, dtype=float) + 0.2)
    )
    feed_total = float(np.sum(spec.feed_component_lbmolph))
    distillate = 0.46 * feed_total
    bottoms = 0.54 * feed_total

    provisional = PhysicalState(
        liquid_moles_lbmol=liquid_moles,
        liquid_mole_fraction=liquid_x,
        temperature_F=temperature,
        vapor_mole_fraction=vapor_y,
        hydraulic_liquid_flow_lbmolph=liquid_flows,
        vapor_flow_lbmolph=vapor_flows,
        distillate_lbmolph=distillate,
        bottoms_lbmolph=bottoms,
        bubble_vapor_mole_fraction=bubble.vapor_mole_fraction,
        condenser_duty_BTUph=reference.condenser_duty_reference_BTUph,
    )
    h_liquid = call_audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=float(temperature[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        composition=liquid_x[0],
        caller="independent_condenser_duty_reconstruction",
        state_id=state_id,
        evaluation_kind="preparation",
    )
    h_vapor = call_audit.phase_enthalpy(
        provider,
        phase="vapor",
        temperature_F=float(temperature[1]),
        pressure_psia=float(spec.pressure_psia[1]),
        composition=vapor_y[0],
        caller="independent_condenser_duty_reconstruction",
        state_id=state_id,
        evaluation_kind="preparation",
    )
    duty = (
        (float(spec.reflux_lbmolph) + distillate) * h_liquid
        - vapor_flows[-1] * h_vapor
    )
    if not np.isfinite(duty) or duty >= 0.0:
        raise RuntimeError("independent Core V3 condenser duty is not negative")
    state = PhysicalState(
        **{**provisional.__dict__, "condenser_duty_BTUph": float(duty)}
    )
    point = encode_state(spec, reference, state)
    metadata = {
        "construction": (
            "fully distinct topology-scaled smooth ALR profile; deterministic "
            "positive amounts and flows; local direct-fugacity drum bubble; "
            "independent condenser-energy duty reconstruction"
        ),
        "drum_liquid_mole_fraction": liquid_x[0].tolist(),
        "bubble_temperature_F": float(bubble.temperature_F),
        "bubble_vapor_mole_fraction": (
            bubble.vapor_mole_fraction.tolist()
        ),
        "bubble_residual_inf_norm": float(bubble.residual_inf_norm),
        "condenser_duty_BTUph": float(duty),
        "full_residual_used": False,
        "partial_root_solve_used": False,
        "balance_back_calculation_used": False,
        "continuation_used": False,
        "endpoint_from_other_start_used": False,
        "dd088_root_or_status_used": False,
        "chemsep_acceptance_truth_used": False,
    }
    return point, metadata


def physical_vector_and_scales(
    spec: OperatingSpec,
    reference: NumericalReference,
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
            state.bubble_vapor_mole_fraction,
            [state.condenser_duty_BTUph],
        )
    )
    scales = np.concatenate(
        (
            np.maximum(reference.liquid_moles_lbmol, 1.0),
            np.ones(state.liquid_mole_fraction.size),
            np.full(state.temperature_F.size, spec.temperature_scale_F),
            np.ones(state.vapor_mole_fraction.size),
            np.maximum(reference.hydraulic_liquid_flow_lbmolph, 1.0),
            np.maximum(reference.vapor_flow_lbmolph, 1.0),
            [
                max(reference.distillate_lbmolph, 1.0),
                max(reference.bottoms_lbmolph, 1.0),
            ],
            np.ones(state.bubble_vapor_mole_fraction.size),
            [max(abs(reference.condenser_duty_reference_BTUph), 1.0)],
        )
    )
    return values, scales


def prepare_campaign(
    spec: OperatingSpec,
    reference: NumericalReference,
    provider: Any,
    call_audit: ProviderCallAudit,
    settings: SteadyRootSettings,
    *,
    canonical: Sequence[float],
    perturbation: Sequence[float],
    fixed_residual_scales: Sequence[float],
) -> tuple[CampaignDefinition, dict[str, Any]]:
    independent, metadata = independent_smooth_start(
        spec,
        reference,
        provider,
        call_audit,
    )
    lower, upper = physical_bounds(spec, reference, settings)
    starts = {
        "canonical_core_v3_seed": _vector(canonical),
        "deterministic_dd092_perturbation": _vector(perturbation),
        "independent_smooth_five_volume_seed": independent,
    }
    dimension = len(coordinate_layout(spec).names)
    for name, point in starts.items():
        if point.shape != (dimension,):
            raise RuntimeError(
                f"Core V3 start {name!r} is not length {dimension}"
            )
        if np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"Core V3 start {name!r} is outside bounds")
    scales = physical_vector_and_scales(spec, reference, starts[
        "canonical_core_v3_seed"
    ])[1]
    return (
        CampaignDefinition(
            lower_bounds=lower,
            upper_bounds=upper,
            starts=starts,
            fixed_residual_scales=_vector(fixed_residual_scales),
            physical_comparison_scales=scales,
        ),
        metadata,
    )


def central_difference_jacobian(
    spec: OperatingSpec,
    reference: NumericalReference,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    state_id: str,
    step: float,
) -> np.ndarray:
    point = _vector(coordinates)
    dimension = point.size
    matrix = np.empty((dimension, dimension), dtype=float)
    for column in range(dimension):
        delta = np.zeros(dimension, dtype=float)
        delta[column] = float(step)
        plus = evaluate_residual(
            spec,
            reference,
            provider,
            call_audit,
            point + delta,
            fixed_scales=fixed_scales,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled
        minus = evaluate_residual(
            spec,
            reference,
            provider,
            call_audit,
            point - delta,
            fixed_scales=fixed_scales,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    return matrix


def block_norms(evaluation: Any, *, scaled: bool = True) -> dict[str, float]:
    source = evaluation.scaled if scaled else evaluation.raw
    result: dict[str, float] = {}
    for block in dict.fromkeys(row.block for row in evaluation.rows):
        indices = [
            index
            for index, row in enumerate(evaluation.rows)
            if row.block == block
        ]
        result[block] = float(np.max(np.abs(source[indices])))
    return result


def movement_by_family(
    spec: OperatingSpec,
    initial: Sequence[float],
    final: Sequence[float],
) -> dict[str, float]:
    layout = coordinate_layout(spec)
    delta = np.abs(_vector(final) - _vector(initial))
    return {
        "liquid_moles": float(np.max(delta[layout.liquid_moles])),
        "liquid_composition": float(np.max(delta[layout.liquid_alr])),
        "temperature": float(np.max(delta[layout.temperature])),
        "column_vapor_composition": float(np.max(delta[layout.vapor_alr])),
        "liquid_flow": float(np.max(delta[layout.liquid_flows])),
        "vapor_flow": float(np.max(delta[layout.vapor_flows])),
        "products": float(
            np.max(delta[[layout.distillate, layout.bottoms]])
        ),
        "bubble_vapor_composition": float(
            np.max(delta[layout.bubble_alr])
        ),
        "condenser_duty": float(delta[layout.condenser_duty]),
    }


def execute_start(
    spec: OperatingSpec,
    reference: NumericalReference,
    provider: Any,
    *,
    name: str,
    initial: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    fixed_scales: Sequence[float],
    settings: SteadyRootSettings,
) -> dict[str, Any]:
    """Execute one frozen start. The DD-093 contract tool controls authorization."""
    audit = ProviderCallAudit()
    point0 = _vector(initial)
    lower = _vector(lower_bounds)
    upper = _vector(upper_bounds)
    if settings.jacobian_mode not in {"uncolored", "colored"}:
        raise ValueError(f"unsupported steady-root Jacobian mode {settings.jacobian_mode!r}")
    initial_evaluation = evaluate_residual(
        spec,
        reference,
        provider,
        audit,
        point0,
        fixed_scales=fixed_scales,
        state_id=name,
        evaluation_kind="residual",
    )

    def objective(point: np.ndarray) -> np.ndarray:
        return evaluate_residual(
            spec,
            reference,
            provider,
            audit,
            point,
            fixed_scales=fixed_scales,
            state_id=name,
            evaluation_kind="residual",
        ).scaled

    def jacobian(point: np.ndarray) -> np.ndarray:
        if settings.jacobian_mode == "uncolored":
            return central_difference_jacobian(
                spec,
                reference,
                provider,
                audit,
                point,
                fixed_scales=fixed_scales,
                state_id=name,
                step=settings.solve_jacobian_step,
            )

        def colored_objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
            return evaluate_residual(
                spec,
                reference,
                provider,
                audit,
                candidate,
                fixed_scales=fixed_scales,
                state_id=state_id,
                evaluation_kind="jacobian",
            ).scaled

        matrix, _groups = colored_central_difference_jacobian(
            colored_objective,
            point,
            pattern=structural_pattern(spec),
            step=settings.solve_jacobian_step,
            state_id=name,
        )
        return matrix

    started = time.perf_counter()
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
    wall_clock = float(time.perf_counter() - started)
    endpoint = evaluate_residual(
        spec,
        reference,
        provider,
        audit,
        result.x,
        fixed_scales=fixed_scales,
        state_id=name,
        evaluation_kind="residual",
    )
    if settings.jacobian_mode == "colored":
        jacobians = [
            audit_colored_numerical_jacobian(
                spec,
                reference,
                provider,
                audit,
                result.x,
                fixed_scales=fixed_scales,
                state_id=name,
                step=step,
                coupling_tolerance=settings.jacobian_coupling_tolerance,
            )[0]
            for step in settings.endpoint_jacobian_steps
        ]
    else:
        jacobians = [
            audit_numerical_jacobian(
                spec,
                reference,
                provider,
                audit,
                result.x,
                fixed_scales=fixed_scales,
                state_id=name,
                step=step,
                coupling_tolerance=settings.jacobian_coupling_tolerance,
            )
            for step in settings.endpoint_jacobian_steps
        ]
    distance = np.minimum(result.x - lower, upper - result.x)
    state = endpoint.state
    topology = spec.topology
    heights = np.asarray(
        [
            endpoint.properties.liquid_height_ft[
                topology.volume_ids.index(volume)
            ]
            for volume in topology.hydraulic_volume_ids
        ],
        dtype=float,
    )
    spacings = np.asarray(
        [
            geometry.tray_spacing_ft
            for geometry in spec.hydraulic_geometry
        ],
        dtype=float,
    )
    residence_times = 3600.0 * np.asarray(
        (
            state.liquid_moles_lbmol[0]
            / (float(spec.reflux_lbmolph) + state.distillate_lbmolph),
            *(
                state.liquid_moles_lbmol[
                    topology.volume_ids.index(volume)
                ]
                / state.hydraulic_liquid_flow_lbmolph[index]
                for index, volume in enumerate(topology.hydraulic_volume_ids)
            ),
            state.liquid_moles_lbmol[-1] / state.bottoms_lbmolph,
        ),
        dtype=float,
    )
    return {
        "name": name,
        "success_flag": bool(result.success),
        "status": int(result.status),
        "termination_reason": str(result.message),
        "nfev": int(result.nfev),
        "njev": None if result.njev is None else int(result.njev),
        "wall_clock_sec": wall_clock,
        "initial_coordinates": point0.copy(),
        "final_coordinates": result.x.copy(),
        "initial_block_norms": block_norms(initial_evaluation),
        "final_block_norms": block_norms(endpoint),
        "final_raw_block_norms": block_norms(endpoint, scaled=False),
        "movement_by_coordinate_family": movement_by_family(
            spec, point0, result.x
        ),
        "minimum_transformed_bound_distance": float(np.min(distance)),
        "active_bound_indices": np.flatnonzero(
            distance <= settings.active_bound_tolerance
        ),
        "liquid_heights_ft": heights,
        "tray_spacings_ft": spacings,
        "residence_times_sec": residence_times,
        "endpoint_evaluation": endpoint,
        "endpoint_jacobians": jacobians,
        "provider_provenance": audit.report(),
    }


def pairwise_root_agreement(
    spec: OperatingSpec,
    reference: NumericalReference,
    endpoints: Mapping[str, Sequence[float]],
    physical_scales: Sequence[float],
) -> dict[str, float]:
    names = tuple(endpoints)
    scales = _vector(physical_scales)
    physical = {
        name: physical_vector_and_scales(
            spec, reference, endpoints[name]
        )[0]
        for name in names
    }
    result: dict[str, float] = {}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            denominator = np.maximum(
                np.maximum(np.abs(physical[left]), np.abs(physical[right])),
                scales,
            )
            result[f"{left}__vs__{right}"] = float(
                np.max(
                    np.abs(physical[left] - physical[right]) / denominator
                )
            )
    return result


__all__ = [
    "CampaignDefinition",
    "SteadyRootSettings",
    "block_norms",
    "central_difference_jacobian",
    "execute_start",
    "independent_smooth_start",
    "movement_by_family",
    "pairwise_root_agreement",
    "physical_bounds",
    "physical_vector_and_scales",
    "prepare_campaign",
]
