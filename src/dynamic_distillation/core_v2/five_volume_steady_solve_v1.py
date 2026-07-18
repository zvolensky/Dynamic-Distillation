"""Fixed three-start steady-root campaign for the DD-082 Gate C decision."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v2.five_volume_residual_gate_v1 import (
    DIRECT_VOLUME_IDS,
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    FiveVolumeOperatingSpec,
    FiveVolumeReference,
    FiveVolumeResidualEvaluation,
    FiveVolumeState,
    NumericalJacobianAudit,
    audit_five_volume_jacobian,
    colored_finite_difference_jacobian,
    decode_direct_coordinates,
    direct_coordinate_layout,
    encode_direct_state,
    evaluate_five_volume_residual,
    perturbation_coordinates,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    OneVolumeConservedState,
    OneVolumeSpec,
    _liquid_properties,
    solve_one_volume_closure,
    vapor_from_logits,
    vapor_logits,
)


@dataclass(frozen=True)
class FixedSteadySolveSettings:
    residual_tolerance: float = 1.0e-8
    root_agreement_tolerance: float = 1.0e-7
    condition_limit: float = 1.0e8
    component_conservation_tolerance: float = 1.0e-12
    energy_conservation_tolerance: float = 1.0e-10
    jacobian_step: float = 1.0e-5
    jacobian_check_steps: tuple[float, float] = (1.0e-5, 5.0e-6)
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 300
    inventory_ratio_bounds: tuple[float, float] = (0.02, 50.0)
    energy_coordinate_bounds: tuple[float, float] = (-5.0, 5.0)
    temperature_bounds_F: tuple[float, float] = (80.0, 300.0)
    vapor_logit_delta_bounds: tuple[float, float] = (-8.0, 8.0)
    flow_ratio_bounds: tuple[float, float] = (0.05, 20.0)
    bound_activity_tolerance: float = 1.0e-6
    smooth_seed_over_weir_head_ft: float = 0.35


@dataclass(frozen=True)
class CoordinateBounds:
    lower: np.ndarray
    upper: np.ndarray


@dataclass(frozen=True)
class SolveAttempt:
    start_name: str
    initial_coordinates: np.ndarray
    final_coordinates: np.ndarray
    solver_success: bool
    solver_status: int
    solver_message: str
    iterations: int
    function_evaluations: int
    jacobian_evaluations: int
    optimality: float
    cost: float
    wall_clock_sec: float
    evaluation: FiveVolumeResidualEvaluation | None
    jacobian_audits: tuple[NumericalJacobianAudit, ...]
    active_bounds: tuple[str, ...]
    movement_by_block: Mapping[str, Mapping[str, float]]
    normalized_physical_movement_max: float
    property_call_counters: Mapping[str, Mapping[str, float | int]]
    accepted: bool
    failure_reason: str


@dataclass(frozen=True)
class SteadySolveCampaign:
    settings: FixedSteadySolveSettings
    fixed_residual_scales: np.ndarray
    bounds: CoordinateBounds
    starts: Mapping[str, np.ndarray]
    smooth_seed_metadata: Mapping[str, Any]
    attempts: tuple[SolveAttempt, ...]
    pairwise_root_agreement: Mapping[str, float]
    maximum_root_disagreement: float
    accepted: bool
    classification: str
    decision: str


def build_coordinate_bounds(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    settings: FixedSteadySolveSettings,
) -> CoordinateBounds:
    layout = direct_coordinate_layout(spec)
    lower = np.full(len(layout.names), -np.inf, dtype=float)
    upper = np.full(len(layout.names), np.inf, dtype=float)
    lower[layout.component_inventory] = np.log(
        float(settings.inventory_ratio_bounds[0])
    )
    upper[layout.component_inventory] = np.log(
        float(settings.inventory_ratio_bounds[1])
    )
    lower[layout.internal_energy] = float(settings.energy_coordinate_bounds[0])
    upper[layout.internal_energy] = float(settings.energy_coordinate_bounds[1])
    temperature_reference = np.asarray(reference.temperature_F, dtype=float)
    lower[layout.temperature] = (
        float(settings.temperature_bounds_F[0]) - temperature_reference
    ) / float(spec.temperature_scale_F)
    upper[layout.temperature] = (
        float(settings.temperature_bounds_F[1]) - temperature_reference
    ) / float(spec.temperature_scale_F)
    lower[layout.vapor_logits] = float(
        settings.vapor_logit_delta_bounds[0]
    )
    upper[layout.vapor_logits] = float(
        settings.vapor_logit_delta_bounds[1]
    )
    flow_lower = np.log(float(settings.flow_ratio_bounds[0]))
    flow_upper = np.log(float(settings.flow_ratio_bounds[1]))
    lower[layout.hydraulic_flows] = flow_lower
    upper[layout.hydraulic_flows] = flow_upper
    lower[layout.distillate] = flow_lower
    upper[layout.distillate] = flow_upper
    lower[layout.bottoms] = flow_lower
    upper[layout.bottoms] = flow_upper
    if np.any(~np.isfinite(lower)) or np.any(~np.isfinite(upper)):
        raise RuntimeError("DD-082 requires finite transformed-coordinate bounds")
    if np.any(lower >= upper):
        raise RuntimeError("DD-082 coordinate bounds are inconsistent")
    return CoordinateBounds(lower=lower, upper=upper)


def _interpolate_composition(
    top: np.ndarray,
    bottom: np.ndarray,
    fraction: float,
) -> np.ndarray:
    top_logits = np.log(top[:-1] / top[-1])
    bottom_logits = np.log(bottom[:-1] / bottom[-1])
    return vapor_from_logits(
        (1.0 - float(fraction)) * top_logits
        + float(fraction) * bottom_logits
    )


def build_independent_smooth_profile_start(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    provider: Any,
    settings: FixedSteadySolveSettings,
) -> tuple[np.ndarray, Mapping[str, Any]]:
    """Build the predeclared non-mini8-interior DD-082 start."""
    component_count = len(spec.component_names)
    fractions = np.linspace(0.0, 1.0, len(DIRECT_VOLUME_IDS))
    reference_state = decode_direct_coordinates(
        spec,
        reference,
        np.zeros(len(direct_coordinate_layout(spec).names), dtype=float),
    )
    top_x = reference_state.liquid_mole_fraction[0]
    bottom_x = reference_state.liquid_mole_fraction[-1]
    liquid_x = np.asarray(
        [
            _interpolate_composition(top_x, bottom_x, fraction)
            for fraction in fractions
        ],
        dtype=float,
    )
    temperature = (
        (1.0 - fractions) * float(reference.temperature_F[0])
        + fractions * float(reference.temperature_F[-1])
    )
    liquid_moles = np.empty(len(DIRECT_VOLUME_IDS), dtype=float)
    liquid_moles[0] = float(spec.terminal_liquid_targets_lbmol[0])
    liquid_moles[-1] = float(spec.terminal_liquid_targets_lbmol[1])
    internal_energy = np.empty(len(DIRECT_VOLUME_IDS), dtype=float)
    vapor = np.empty(
        (len(EQUILIBRIUM_VOLUME_IDS), component_count),
        dtype=float,
    )
    hydraulic_flow = np.empty(len(HYDRAULIC_VOLUME_IDS), dtype=float)
    component_mw = provider.component_mw_lbm_per_lbmol()
    if component_mw is None:
        raise RuntimeError("smooth seed requires live component molecular weights")
    local_closures: dict[str, Mapping[str, float | bool]] = {}
    for volume_index, volume in enumerate(DIRECT_VOLUME_IDS):
        h_liquid, u_liquid, density = _liquid_properties(
            provider,
            temperature_F=float(temperature[volume_index]),
            pressure_psia=float(spec.pressure_psia[volume_index]),
            liquid_mole_fraction=liquid_x[volume_index],
        )
        if volume in HYDRAULIC_VOLUME_IDS:
            hydraulic_index = HYDRAULIC_VOLUME_IDS.index(volume)
            geometry = spec.hydraulic_geometry[hydraulic_index]
            weir_height = float(geometry.weir_height_in) / 12.0
            maximum_head = 0.5 * (
                float(geometry.tray_spacing_ft) - weir_height
            )
            target_head = min(
                float(settings.smooth_seed_over_weir_head_ft),
                maximum_head,
            )
            if target_head <= 0.0:
                raise RuntimeError("smooth seed geometry has no positive head range")
            liquid_height = weir_height + target_head
            liquid_moles[volume_index] = (
                float(density)
                * float(geometry.active_area_ft2)
                * liquid_height
            )
        internal_energy[volume_index] = (
            liquid_moles[volume_index] * float(u_liquid)
        )
        if volume not in EQUILIBRIUM_VOLUME_IDS:
            continue
        vapor_index = EQUILIBRIUM_VOLUME_IDS.index(volume)
        geometry = (
            spec.hydraulic_geometry[
                HYDRAULIC_VOLUME_IDS.index(volume)
            ]
            if volume in HYDRAULIC_VOLUME_IDS
            else spec.hydraulic_geometry[-1]
        )
        local_spec = OneVolumeSpec(
            component_names=spec.component_names,
            pressure_psia=float(spec.pressure_psia[volume_index]),
            temperature_reference_F=float(temperature[volume_index]),
            temperature_scale_F=float(spec.temperature_scale_F),
            energy_scale_BTU=max(abs(internal_energy[volume_index]), 1.0),
            geometry=geometry,
            component_mw_lbm_per_lbmol=np.asarray(component_mw, dtype=float),
        )
        closure = solve_one_volume_closure(
            local_spec,
            OneVolumeConservedState(
                component_inventory_lbmol=(
                    liquid_moles[volume_index] * liquid_x[volume_index]
                ),
                internal_energy_BTU=float(internal_energy[volume_index]),
            ),
            provider,
            initial_temperature_F=float(temperature[volume_index]),
            initial_vapor_mole_fraction=reference.vapor_mole_fraction[
                vapor_index
            ],
        )
        if (
            not closure.converged
            or closure.active_bounds
            or closure.clipping_or_projection_used
        ):
            raise RuntimeError(
                f"smooth seed local closure failed for {volume}"
            )
        vapor[vapor_index] = closure.vapor_mole_fraction
        local_closures[volume] = {
            "temperature_F": float(closure.temperature_F),
            "residual_max": float(np.max(np.abs(closure.residual))),
            "converged": bool(closure.converged),
        }
        if volume in HYDRAULIC_VOLUME_IDS:
            hydraulic_flow[HYDRAULIC_VOLUME_IDS.index(volume)] = float(
                closure.francis_flow_lbmolph
            )

    feed_total = float(np.sum(spec.feed_component_lbmolph))
    denominator = float(top_x[0] - bottom_x[0])
    if abs(denominator) <= 1.0e-12:
        raise RuntimeError("terminal compositions cannot define smooth-seed products")
    distillate = (
        float(spec.feed_component_lbmolph[0]) - feed_total * bottom_x[0]
    ) / denominator
    bottoms = feed_total - distillate
    if distillate <= 0.0 or bottoms <= 0.0:
        raise RuntimeError("smooth-seed terminal product estimate is non-physical")
    state = FiveVolumeState(
        component_inventory_lbmol=liquid_moles[:, None] * liquid_x,
        internal_energy_BTU=internal_energy,
        temperature_F=temperature,
        liquid_moles_lbmol=liquid_moles,
        liquid_mole_fraction=liquid_x,
        vapor_mole_fraction=vapor,
        hydraulic_liquid_flow_lbmolph=hydraulic_flow,
        distillate_lbmolph=float(distillate),
        bottoms_lbmolph=float(bottoms),
    )
    coordinates = encode_direct_state(spec, reference, state)
    return coordinates, {
        "construction": (
            "terminal ALR-composition interpolation, linear terminal "
            "temperature interpolation, live-density tray inventories at a "
            "fixed positive over-weir head, live DWSIM internal energy and "
            "equilibrium closure, and live Francis flows"
        ),
        "used_mini8_internal_profile": False,
        "fractions": [float(value) for value in fractions],
        "temperature_F": [float(value) for value in temperature],
        "liquid_moles_lbmol": [float(value) for value in liquid_moles],
        "liquid_mole_fraction": [
            [float(value) for value in row] for row in liquid_x
        ],
        "vapor_mole_fraction": [
            [float(value) for value in row] for row in vapor
        ],
        "hydraulic_liquid_flow_lbmolph": [
            float(value) for value in hydraulic_flow
        ],
        "distillate_lbmolph": float(distillate),
        "bottoms_lbmolph": float(bottoms),
        "local_closures": local_closures,
    }


def _active_bounds(
    coordinates: np.ndarray,
    bounds: CoordinateBounds,
    names: Sequence[str],
    tolerance: float,
) -> tuple[str, ...]:
    active: list[str] = []
    for index, name in enumerate(names):
        span = float(bounds.upper[index] - bounds.lower[index])
        threshold = float(tolerance) * max(span, 1.0)
        if (
            coordinates[index] - bounds.lower[index] <= threshold
            or bounds.upper[index] - coordinates[index] <= threshold
        ):
            active.append(name)
    return tuple(active)


def _movement_by_block(
    layout,
    initial: np.ndarray,
    final: np.ndarray,
) -> Mapping[str, Mapping[str, float]]:
    definitions = {
        "component_inventory": layout.component_inventory,
        "internal_energy": layout.internal_energy,
        "temperature": layout.temperature,
        "vapor_composition": layout.vapor_logits,
        "liquid_flow": layout.hydraulic_flows,
        "product_flow": np.asarray([layout.distillate, layout.bottoms]),
    }
    result: dict[str, Mapping[str, float]] = {}
    for name, selector in definitions.items():
        movement = np.asarray(final[selector] - initial[selector], dtype=float)
        result[name] = {
            "coordinate_max_abs": float(np.max(np.abs(movement))),
            "coordinate_rms": float(np.sqrt(np.mean(movement**2))),
        }
    return result


def _physical_vector_and_scale(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    state: FiveVolumeState,
) -> tuple[np.ndarray, np.ndarray]:
    values = np.concatenate(
        (
            state.component_inventory_lbmol.reshape((-1,)),
            state.internal_energy_BTU,
            state.temperature_F,
            state.vapor_mole_fraction.reshape((-1,)),
            state.hydraulic_liquid_flow_lbmolph,
            np.asarray([state.distillate_lbmolph, state.bottoms_lbmolph]),
        )
    )
    scales = np.concatenate(
        (
            np.maximum(
                np.asarray(
                    reference.component_inventory_lbmol,
                    dtype=float,
                ).reshape((-1,)),
                1.0e-6,
            ),
            np.maximum(np.abs(reference.internal_energy_BTU), 1.0),
            np.full(len(DIRECT_VOLUME_IDS), float(spec.temperature_scale_F)),
            np.ones(
                len(EQUILIBRIUM_VOLUME_IDS) * len(spec.component_names),
                dtype=float,
            ),
            np.maximum(reference.hydraulic_liquid_flow_lbmolph, 1.0),
            np.asarray(
                [
                    max(float(reference.distillate_lbmolph), 1.0),
                    max(float(reference.bottoms_lbmolph), 1.0),
                ]
            ),
        )
    )
    return values, scales


def normalized_physical_difference(
    first_values: np.ndarray,
    second_values: np.ndarray,
    scales: np.ndarray,
) -> float:
    denominator = np.maximum(
        np.maximum(np.abs(first_values), np.abs(second_values)),
        scales,
    )
    return float(np.max(np.abs(first_values - second_values) / denominator))


def _solve_attempt(
    *,
    start_name: str,
    initial: np.ndarray,
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    provider: Any,
    fixed_scales: np.ndarray,
    bounds: CoordinateBounds,
    settings: FixedSteadySolveSettings,
) -> SolveAttempt:
    layout = direct_coordinate_layout(spec)
    started = time.perf_counter()
    provider.reset_call_counters()
    try:
        solution = least_squares(
            lambda point: evaluate_five_volume_residual(
                spec,
                reference,
                provider,
                point,
                fixed_scales=fixed_scales,
            ).scaled,
            np.asarray(initial, dtype=float),
            jac=lambda point: colored_finite_difference_jacobian(
                spec,
                reference,
                provider,
                point,
                fixed_scales=fixed_scales,
                step=float(settings.jacobian_step),
            ),
            bounds=(bounds.lower, bounds.upper),
            method="trf",
            ftol=float(settings.ftol),
            xtol=float(settings.xtol),
            gtol=float(settings.gtol),
            x_scale="jac",
            loss="linear",
            max_nfev=int(settings.max_nfev),
            verbose=0,
        )
        final = np.asarray(solution.x, dtype=float)
        evaluation = evaluate_five_volume_residual(
            spec,
            reference,
            provider,
            final,
            fixed_scales=fixed_scales,
        )
        jacobians = tuple(
            audit_five_volume_jacobian(
                spec,
                reference,
                provider,
                final,
                fixed_scales=fixed_scales,
                step=step,
            )
            for step in settings.jacobian_check_steps
        )
        active = _active_bounds(
            final,
            bounds,
            layout.names,
            settings.bound_activity_tolerance,
        )
        initial_state = decode_direct_coordinates(
            spec,
            reference,
            initial,
        )
        final_values, physical_scales = _physical_vector_and_scale(
            spec,
            reference,
            evaluation.state,
        )
        initial_values, _ = _physical_vector_and_scale(
            spec,
            reference,
            initial_state,
        )
        physical_movement = normalized_physical_difference(
            final_values,
            initial_values,
            physical_scales,
        )
        heights_physical = all(
            evaluation.properties.liquid_height_ft[
                DIRECT_VOLUME_IDS.index(volume)
            ]
            < spec.hydraulic_geometry[index].tray_spacing_ft
            for index, volume in enumerate(HYDRAULIC_VOLUME_IDS)
        )
        accepted = bool(
            solution.success
            and np.max(np.abs(evaluation.scaled))
            < settings.residual_tolerance
            and evaluation.component_telescoping_relative_error
            < settings.component_conservation_tolerance
            and evaluation.energy_telescoping_relative_error
            < settings.energy_conservation_tolerance
            and np.all(evaluation.state.component_inventory_lbmol > 0.0)
            and np.all(evaluation.state.liquid_mole_fraction > 0.0)
            and np.all(evaluation.state.vapor_mole_fraction > 0.0)
            and np.all(
                evaluation.state.hydraulic_liquid_flow_lbmolph > 0.0
            )
            and np.all(np.isfinite(evaluation.raw))
            and heights_physical
            and not evaluation.clipping_or_projection_used
            and not evaluation.property_fallback_used
            and not active
            and all(
                audit.rank == final.size
                and audit.condition < settings.condition_limit
                and not audit.zero_rows
                and not audit.zero_columns
                and not audit.unexpected_couplings
                for audit in jacobians
            )
        )
        if accepted:
            reason = "accepted"
        elif not solution.success:
            reason = "solver did not report convergence"
        elif np.max(np.abs(evaluation.scaled)) >= settings.residual_tolerance:
            reason = "scaled residual remained above tolerance"
        elif active:
            reason = "one or more transformed-coordinate bounds are active"
        elif not heights_physical:
            reason = "one or more tray liquid heights exceed spacing"
        else:
            reason = "one or more physical, conservation, rank, or property gates failed"
        return SolveAttempt(
            start_name=start_name,
            initial_coordinates=np.asarray(initial, dtype=float),
            final_coordinates=final,
            solver_success=bool(solution.success),
            solver_status=int(solution.status),
            solver_message=str(solution.message),
            iterations=int(solution.njev or 0),
            function_evaluations=int(solution.nfev),
            jacobian_evaluations=int(solution.njev or 0),
            optimality=float(solution.optimality),
            cost=float(solution.cost),
            wall_clock_sec=float(time.perf_counter() - started),
            evaluation=evaluation,
            jacobian_audits=jacobians,
            active_bounds=active,
            movement_by_block=_movement_by_block(
                layout,
                np.asarray(initial, dtype=float),
                final,
            ),
            normalized_physical_movement_max=physical_movement,
            property_call_counters=provider.get_call_counters(),
            accepted=accepted,
            failure_reason=reason,
        )
    except Exception as exc:
        return SolveAttempt(
            start_name=start_name,
            initial_coordinates=np.asarray(initial, dtype=float),
            final_coordinates=np.asarray(initial, dtype=float),
            solver_success=False,
            solver_status=-1,
            solver_message=f"{type(exc).__name__}: {exc}",
            iterations=0,
            function_evaluations=0,
            jacobian_evaluations=0,
            optimality=float("inf"),
            cost=float("inf"),
            wall_clock_sec=float(time.perf_counter() - started),
            evaluation=None,
            jacobian_audits=(),
            active_bounds=(),
            movement_by_block={},
            normalized_physical_movement_max=float("inf"),
            property_call_counters=provider.get_call_counters(),
            accepted=False,
            failure_reason="property or solver evaluation raised an exception",
        )


def run_fixed_steady_solve_campaign(
    *,
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    provider: Any,
    settings: FixedSteadySolveSettings | None = None,
) -> SteadySolveCampaign:
    selected = FixedSteadySolveSettings() if settings is None else settings
    bounds = build_coordinate_bounds(spec, reference, selected)
    predefined = perturbation_coordinates(spec)
    smooth, smooth_metadata = build_independent_smooth_profile_start(
        spec,
        reference,
        provider,
        selected,
    )
    starts = {
        "canonical_mini8_derived": predefined["canonical_mini8_derived"],
        "bounded_deterministic_perturbation": predefined[
            "combined_bounded_perturbation"
        ],
        "independent_smooth_profile": smooth,
    }
    for name, point in starts.items():
        if np.any(point <= bounds.lower) or np.any(point >= bounds.upper):
            raise RuntimeError(f"predeclared DD-082 start {name} is outside bounds")
    canonical = evaluate_five_volume_residual(
        spec,
        reference,
        provider,
        starts["canonical_mini8_derived"],
    )
    fixed_scales = canonical.scales.copy()
    attempts = tuple(
        _solve_attempt(
            start_name=name,
            initial=point,
            spec=spec,
            reference=reference,
            provider=provider,
            fixed_scales=fixed_scales,
            bounds=bounds,
            settings=selected,
        )
        for name, point in starts.items()
    )
    pairwise: dict[str, float] = {}
    for first_index, first in enumerate(attempts):
        for second in attempts[first_index + 1 :]:
            key = f"{first.start_name} vs {second.start_name}"
            if first.evaluation is None or second.evaluation is None:
                pairwise[key] = float("inf")
                continue
            first_values, scales = _physical_vector_and_scale(
                spec,
                reference,
                first.evaluation.state,
            )
            second_values, _ = _physical_vector_and_scale(
                spec,
                reference,
                second.evaluation.state,
            )
            pairwise[key] = normalized_physical_difference(
                first_values,
                second_values,
                scales,
            )
    maximum_disagreement = max(pairwise.values(), default=float("inf"))
    accepted = bool(
        all(attempt.accepted for attempt in attempts)
        and maximum_disagreement < selected.root_agreement_tolerance
    )
    return SteadySolveCampaign(
        settings=selected,
        fixed_residual_scales=fixed_scales,
        bounds=bounds,
        starts=starts,
        smooth_seed_metadata=smooth_metadata,
        attempts=attempts,
        pairwise_root_agreement=pairwise,
        maximum_root_disagreement=float(maximum_disagreement),
        accepted=accepted,
        classification=(
            "dd082_five_volume_steady_root_accepted"
            if accepted
            else "dd082_five_volume_steady_root_failed"
        ),
        decision=(
            "authorize_five_volume_dynamic_gate"
            if accepted
            else "stop_gate_c_and_retire_this_operating_specification"
        ),
    )


__all__ = [
    "CoordinateBounds",
    "FixedSteadySolveSettings",
    "SolveAttempt",
    "SteadySolveCampaign",
    "build_coordinate_bounds",
    "build_independent_smooth_profile_start",
    "normalized_physical_difference",
    "run_fixed_steady_solve_campaign",
]
