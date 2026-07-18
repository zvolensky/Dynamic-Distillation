"""Reduced-column feasibility study for the conserved steady-state equations.

The reduction keeps the direct residual unchanged and samples five physical
roles from a larger column: reflux drum, rectifying tray, feed tray, stripping
tray, and combined reboiler/sump. It is a bounded architecture decision test,
not a tray-count continuation scheme.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix

from dynamic_distillation.column_spec_builder_v1 import (
    ColumnGeometry,
    ColumnGeometrySection,
    ColumnSpec,
)
from dynamic_distillation.direct_steady_state_continuation_v1 import (
    ContinuationStage,
    SmoothPhysicalCoordinates,
    finite_difference_stage_jacobian,
    stage_structural_pattern,
)
from dynamic_distillation.direct_steady_state_registry_v1 import (
    RegistryStructureAudit,
    audit_registry_structure,
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
)
from dynamic_distillation.direct_steady_state_residual_v1 import (
    DirectResidualEvaluation,
    DirectSteadyStateProblem,
    NumericalJacobianAudit,
    audit_numerical_jacobian,
    build_chemsep_guess,
    build_direct_steady_state_problem,
    evaluate_direct_steady_state_residual,
)


REDUCED_FEASIBILITY_SCHEMA = "dd075-reduced-column-feasibility-v1"
REDUCED_STAGE_COUNT = 5
REDUCED_TOP_STAGE = 1
REDUCED_BOTTOM_STAGE = REDUCED_STAGE_COUNT
REDUCED_FEED_STAGE = (REDUCED_STAGE_COUNT + 1) // 2
REDUCED_ACTIVE_STAGE_IDS = tuple(range(REDUCED_TOP_STAGE + 1, REDUCED_BOTTOM_STAGE))


@dataclass(frozen=True)
class ReducedColumnMapping:
    source_stage_1based: tuple[int, ...]
    reduced_stage_1based: tuple[int, ...]
    role_by_reduced_stage: tuple[str, ...]


@dataclass(frozen=True)
class ReducedFeasibilityCase:
    source_column: ColumnSpec
    column: ColumnSpec
    mapping: ReducedColumnMapping
    problem: DirectSteadyStateProblem
    structure: RegistryStructureAudit


@dataclass(frozen=True)
class FixedSolverSettings:
    residual_tolerance: float = 1.0e-7
    condition_limit: float = 1.0e12
    root_agreement_tolerance: float = 1.0e-4
    trust_region_max_nfev: int = 160
    pseudo_transient_max_iterations: int = 80
    pseudo_time_initial: float = 0.1
    pseudo_time_minimum: float = 1.0e-7
    pseudo_time_maximum: float = 1.0e6
    pseudo_time_growth: float = 1.5
    pseudo_time_reduction: float = 0.25
    pseudo_transient_line_search_steps: int = 8


@dataclass(frozen=True)
class ReducedSolveAttempt:
    method: str
    seed_name: str
    solver_success: bool
    accepted: bool
    iterations: int
    function_evaluations: int
    final_scaled_inf_norm: float
    final_scaled_l2_norm: float
    numerical_rank: int
    numerical_nullity: int
    condition_estimate: float
    positive_ordered_pressure: bool
    positive_flows: bool
    component_conservation_pass: bool
    energy_conservation_pass: bool
    safeguards_used: tuple[str, ...]
    coordinate_saturation: tuple[str, ...]
    block_maxima: tuple[tuple[str, float], ...]
    dominant_residuals: tuple[dict[str, Any], ...]
    final_vector: np.ndarray
    reason: str


@dataclass(frozen=True)
class ReducedFeasibilityStudy:
    schema_id: str
    mapping: ReducedColumnMapping
    structure: RegistryStructureAudit
    initial_numerical_audits: tuple[tuple[str, NumericalJacobianAudit], ...]
    numerical_gate_pass: bool
    attempts: tuple[ReducedSolveAttempt, ...]
    root_agreement_max_scaled_difference: float
    accepted: bool
    classification: str
    decision: str


def _sample(array: Any, indices: np.ndarray) -> Any:
    if array is None:
        return None
    values = np.asarray(array)
    return values[indices].copy()


def select_reduced_source_stages(column: ColumnSpec) -> ReducedColumnMapping:
    """Select source stages by physical role without case-specific tray IDs."""
    if int(column.n_stages) < REDUCED_STAGE_COUNT:
        raise ValueError("the source column must have at least five stages")
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("the source column requires a staged Feed stream")

    last_index = int(column.n_stages) - 1
    feed_index = int(feed.stage_1based) - 1
    if feed_index <= 1 or feed_index >= last_index - 1:
        raise ValueError(
            "the reduced study requires source trays on both sides of the feed"
        )
    rectifying_index = max(1, feed_index // 2)
    stripping_index = min(
        last_index - 1,
        feed_index + max(1, (last_index - feed_index) // 2),
    )
    selected = (0, rectifying_index, feed_index, stripping_index, last_index)
    if len(set(selected)) != REDUCED_STAGE_COUNT:
        raise ValueError("the source profile cannot define five distinct physical roles")
    return ReducedColumnMapping(
        source_stage_1based=tuple(index + 1 for index in selected),
        reduced_stage_1based=tuple(range(1, REDUCED_STAGE_COUNT + 1)),
        role_by_reduced_stage=(
            "reflux_drum",
            "rectifying_tray",
            "feed_tray",
            "stripping_tray",
            "combined_reboiler_sump",
        ),
    )


def _reduce_geometry(
    geometry: ColumnGeometry,
    source_indices: np.ndarray,
) -> ColumnGeometry:
    array_names = (
        "diameter_ft_per_stage",
        "tray_spacing_ft_per_stage",
        "gas_void_frac_per_stage",
        "area_ft2_per_stage",
        "vapor_volume_ft3_per_stage",
        "weir_height_in_per_stage",
        "weir_length_ft_per_stage",
        "active_area_frac_per_stage",
        "active_area_ft2_per_stage",
        "hydraulic_c_factor_per_stage",
    )
    arrays = {
        name: _sample(getattr(geometry, name), source_indices)
        for name in array_names
    }
    sections: list[ColumnGeometrySection] = []
    for reduced_index in range(REDUCED_STAGE_COUNT):
        sections.append(
            ColumnGeometrySection(
                start_stage_1based=reduced_index + 1,
                end_stage_1based=reduced_index + 1,
                diameter_ft=float(arrays["diameter_ft_per_stage"][reduced_index]),
                tray_spacing_ft=float(
                    arrays["tray_spacing_ft_per_stage"][reduced_index]
                ),
                gas_void_frac=float(
                    arrays["gas_void_frac_per_stage"][reduced_index]
                ),
                weir_height_in=(
                    None
                    if arrays["weir_height_in_per_stage"] is None
                    else float(arrays["weir_height_in_per_stage"][reduced_index])
                ),
                weir_length_ft=(
                    None
                    if arrays["weir_length_ft_per_stage"] is None
                    else float(arrays["weir_length_ft_per_stage"][reduced_index])
                ),
                active_area_frac=(
                    None
                    if arrays["active_area_frac_per_stage"] is None
                    else float(arrays["active_area_frac_per_stage"][reduced_index])
                ),
                hydraulic_c_factor=(
                    None
                    if arrays["hydraulic_c_factor_per_stage"] is None
                    else float(
                        arrays["hydraulic_c_factor_per_stage"][reduced_index]
                    )
                ),
            )
        )
    return ColumnGeometry(sections=sections, **arrays)


def _reduce_memory_state(
    memory_state: Mapping[str, np.ndarray] | None,
    source_indices: np.ndarray,
    source_stage_count: int,
) -> dict[str, np.ndarray] | None:
    if memory_state is None:
        return None
    result: dict[str, np.ndarray] = {}
    for name, value in memory_state.items():
        array = np.asarray(value)
        result[name] = (
            array[source_indices].copy()
            if array.ndim >= 1 and array.shape[0] == source_stage_count
            else array.copy()
        )
    return result


def reduce_column_to_five_volumes(
    column: ColumnSpec,
) -> tuple[ColumnSpec, ReducedColumnMapping]:
    """Return a five-stage specification sampled from the source physical roles."""
    if column.geometry is None:
        raise ValueError("the reduced study requires explicit source geometry")
    mapping = select_reduced_source_stages(column)
    source_indices = (
        np.asarray(mapping.source_stage_1based, dtype=int) - 1
    )

    reduced_streams = {}
    for name, stream in column.streams.items():
        if name == "Feed":
            reduced_stage = REDUCED_FEED_STAGE
        elif name == "Distillate":
            reduced_stage = REDUCED_TOP_STAGE
        elif name == "Bottom":
            reduced_stage = REDUCED_BOTTOM_STAGE
        elif stream.stage_1based is None:
            reduced_stage = None
        else:
            source_index = int(stream.stage_1based) - 1
            reduced_stage = (
                int(np.argmin(np.abs(source_indices - source_index))) + 1
            )
        reduced_streams[name] = replace(
            stream,
            stage_1based=reduced_stage,
        )

    reduced_specs = dict(column.specs_raw)
    reduced_specs["Reduced Feasibility Source Stage Count"] = int(column.n_stages)
    reduced_specs["Reduced Feasibility Stage Count"] = REDUCED_STAGE_COUNT
    reduced = replace(
        column,
        n_stages=REDUCED_STAGE_COUNT,
        stage_1based=np.arange(1, REDUCED_STAGE_COUNT + 1, dtype=int),
        T_f=_sample(column.T_f, source_indices),
        P_psia=_sample(column.P_psia, source_indices),
        V_lbmolph=_sample(column.V_lbmolph, source_indices),
        L_lbmolph=_sample(column.L_lbmolph, source_indices),
        M_L_lbmol=_sample(column.M_L_lbmol, source_indices),
        M_V_lbmol=_sample(column.M_V_lbmol, source_indices),
        y0=_sample(column.y0, source_indices),
        x0=_sample(column.x0, source_indices),
        tray_EL0_BTU=_sample(column.tray_EL0_BTU, source_indices),
        tray_EV0_BTU=_sample(column.tray_EV0_BTU, source_indices),
        streams=reduced_streams,
        specs_raw=reduced_specs,
        memory_state=_reduce_memory_state(
            column.memory_state, source_indices, int(column.n_stages)
        ),
        geometry=_reduce_geometry(column.geometry, source_indices),
    )
    return reduced, mapping


def build_reduced_feasibility_case(
    *,
    column: ColumnSpec,
    provider: Any,
    bottoms_light_key_target: float = 0.04717,
) -> ReducedFeasibilityCase:
    reduced, mapping = reduce_column_to_five_volumes(column)
    registry = combine_reboiler_and_sump_registry(
        build_direct_steady_state_registry(
            component_names=reduced.components_excel,
            active_stage_ids=REDUCED_ACTIVE_STAGE_IDS,
        )
    )
    structure = audit_registry_structure(registry)
    expected_size = 15 * int(reduced.n_components) + 26
    if (
        structure.unknown_count != expected_size
        or structure.residual_count != expected_size
    ):
        raise RuntimeError(
            "the reduced registry does not match the five-volume equation count"
        )
    problem = build_direct_steady_state_problem(
        registry=registry,
        column=reduced,
        provider=provider,
        bottoms_light_key_target=bottoms_light_key_target,
    )
    return ReducedFeasibilityCase(
        source_column=column,
        column=reduced,
        mapping=mapping,
        problem=problem,
        structure=structure,
    )


def _full_stage(problem: DirectSteadyStateProblem) -> ContinuationStage:
    unknowns = tuple(range(len(problem.registry.unknowns)))
    residuals = tuple(range(len(problem.registry.residuals)))
    return ContinuationStage(
        number=1,
        name="full_reduced_system",
        unknown_indices=unknowns,
        residual_indices=residuals,
        new_unknown_indices=unknowns,
        new_residual_indices=residuals,
        anchor_unknown_by_residual=(),
        anchor_sign_by_residual=(),
    )


def build_reduced_perturbed_guess(
    problem: DirectSteadyStateProblem,
    base_vector: Sequence[float],
) -> np.ndarray:
    """Create the second fixed seed in smooth physical coordinates."""
    base = np.asarray(base_vector, dtype=float)
    evaluation = evaluate_direct_steady_state_residual(problem, base)
    stage = _full_stage(problem)
    coordinates = SmoothPhysicalCoordinates(
        problem, base, evaluation.variable_scales
    )
    perturbation = 2.0e-3 * np.sin(
        np.arange(1, len(stage.unknown_indices) + 1, dtype=float)
    )
    return coordinates.decode(perturbation, stage.unknown_indices)


def _rank_condition(matrix: csr_matrix | np.ndarray) -> tuple[int, float]:
    dense = matrix.toarray() if isinstance(matrix, csr_matrix) else np.asarray(matrix)
    singular = np.linalg.svd(dense, compute_uv=False)
    rank = int(np.linalg.matrix_rank(dense))
    condition = float(
        np.inf
        if singular.size == 0 or singular[-1] == 0.0
        else singular[0] / singular[-1]
    )
    return rank, condition


def _block_maxima(
    evaluation: DirectResidualEvaluation,
    fixed_scales: np.ndarray,
) -> tuple[tuple[str, float], ...]:
    values: dict[str, float] = {}
    scaled = evaluation.raw / fixed_scales
    for index, row in enumerate(evaluation.rows):
        values[row.block] = max(
            values.get(row.block, 0.0), abs(float(scaled[index]))
        )
    return tuple(sorted(values.items()))


def _dominant_residuals(
    evaluation: DirectResidualEvaluation,
    fixed_scales: np.ndarray,
) -> tuple[dict[str, Any], ...]:
    scaled = evaluation.raw / fixed_scales
    order = np.argsort(np.abs(scaled))[::-1][:12]
    return tuple(
        {
            "name": evaluation.rows[index].name,
            "block": evaluation.rows[index].block,
            "owner": evaluation.rows[index].owner,
            "scaled_value": float(scaled[index]),
            "raw_value": float(evaluation.raw[index]),
            "units": evaluation.rows[index].units,
        }
        for index in order
    )


def _physical_gate(
    problem: DirectSteadyStateProblem,
    vector: np.ndarray,
) -> tuple[bool, bool]:
    values = {
        entry.name: float(vector[index])
        for index, entry in enumerate(problem.registry.unknowns)
    }
    nodes_top_to_bottom = (
        "reflux_drum",
        *(f"tray_{stage}" for stage in problem.registry.active_stage_ids),
        "partial_reboiler",
    )
    pressures = np.asarray(
        [values[f"P[{node}]"] for node in nodes_top_to_bottom],
        dtype=float,
    )
    ordered_pressure = bool(
        np.all(np.isfinite(pressures))
        and np.all(pressures > 0.0)
        and np.all(np.diff(pressures) > 0.0)
    )
    flow_names = tuple(
        entry.name
        for entry in problem.registry.unknowns
        if entry.name.startswith(("L_out[", "V_out["))
        or entry.name in {"D", "B"}
    )
    positive_flows = bool(
        all(np.isfinite(values[name]) and values[name] > 0.0 for name in flow_names)
    )
    return ordered_pressure, positive_flows


def _attempt_result(
    *,
    problem: DirectSteadyStateProblem,
    method: str,
    seed_name: str,
    solver_success: bool,
    iterations: int,
    function_evaluations: int,
    coordinates: SmoothPhysicalCoordinates,
    solver_coordinates: np.ndarray,
    fixed_scales: np.ndarray,
    pattern: csr_matrix,
    settings: FixedSolverSettings,
    reason: str,
) -> ReducedSolveAttempt:
    stage = _full_stage(problem)
    vector = coordinates.decode(solver_coordinates, stage.unknown_indices)
    evaluation = evaluate_direct_steady_state_residual(problem, vector)

    def residual(value: np.ndarray) -> np.ndarray:
        physical = coordinates.decode(value, stage.unknown_indices)
        return evaluate_direct_steady_state_residual(problem, physical).raw / fixed_scales

    jacobian = finite_difference_stage_jacobian(
        residual, solver_coordinates, pattern
    )
    rank, condition = _rank_condition(jacobian)
    pressure_pass, flow_pass = _physical_gate(problem, vector)
    saturation = coordinates.saturated(
        solver_coordinates, stage.unknown_indices
    )
    scaled = evaluation.raw / fixed_scales
    accepted = bool(
        solver_success
        and float(np.max(np.abs(scaled))) < settings.residual_tolerance
        and rank == len(problem.registry.unknowns)
        and condition < settings.condition_limit
        and pressure_pass
        and flow_pass
        and evaluation.conservation.component_pass
        and evaluation.conservation.energy_pass
        and evaluation.conservation.internal_energy_pairing_pass
        and not evaluation.safeguards_used
        and not saturation
    )
    gate_reason = (
        "accepted"
        if accepted
        else (
            f"solver_success={solver_success}; "
            f"scaled_inf={np.max(np.abs(scaled)):.3e}; "
            f"rank={rank}/{len(problem.registry.unknowns)}; "
            f"condition={condition:.3e}; "
            f"ordered_pressure={pressure_pass}; positive_flows={flow_pass}; "
            f"component_conservation={evaluation.conservation.component_pass}; "
            f"energy_conservation={evaluation.conservation.energy_pass}; "
            f"safeguards={len(evaluation.safeguards_used)}; "
            f"saturation={len(saturation)}; solver={reason}"
        )
    )
    return ReducedSolveAttempt(
        method=method,
        seed_name=seed_name,
        solver_success=bool(solver_success),
        accepted=accepted,
        iterations=int(iterations),
        function_evaluations=int(function_evaluations),
        final_scaled_inf_norm=float(np.max(np.abs(scaled))),
        final_scaled_l2_norm=float(np.linalg.norm(scaled)),
        numerical_rank=rank,
        numerical_nullity=len(problem.registry.unknowns) - rank,
        condition_estimate=condition,
        positive_ordered_pressure=pressure_pass,
        positive_flows=flow_pass,
        component_conservation_pass=bool(
            evaluation.conservation.component_pass
        ),
        energy_conservation_pass=bool(evaluation.conservation.energy_pass),
        safeguards_used=evaluation.safeguards_used,
        coordinate_saturation=saturation,
        block_maxima=_block_maxima(evaluation, fixed_scales),
        dominant_residuals=_dominant_residuals(evaluation, fixed_scales),
        final_vector=vector,
        reason=gate_reason,
    )


def solve_reduced_trust_region(
    problem: DirectSteadyStateProblem,
    initial_vector: Sequence[float],
    *,
    seed_name: str,
    fixed_scales: Sequence[float],
    settings: FixedSolverSettings,
) -> ReducedSolveAttempt:
    stage = _full_stage(problem)
    initial = np.asarray(initial_vector, dtype=float)
    initial_evaluation = evaluate_direct_steady_state_residual(problem, initial)
    coordinates = SmoothPhysicalCoordinates(
        problem, initial, initial_evaluation.variable_scales
    )
    solver_initial = coordinates.encode(initial, stage.unknown_indices)
    lower, upper = coordinates.bounds(stage.unknown_indices)
    scales = np.asarray(fixed_scales, dtype=float)
    pattern = stage_structural_pattern(problem, stage)

    def residual(value: np.ndarray) -> np.ndarray:
        physical = coordinates.decode(value, stage.unknown_indices)
        return evaluate_direct_steady_state_residual(problem, physical).raw / scales

    def jacobian(value: np.ndarray) -> csr_matrix:
        return finite_difference_stage_jacobian(residual, value, pattern)

    solved = least_squares(
        residual,
        solver_initial,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        tr_solver="lsmr",
        x_scale="jac",
        ftol=1.0e-11,
        xtol=1.0e-11,
        gtol=1.0e-11,
        max_nfev=int(settings.trust_region_max_nfev),
    )
    return _attempt_result(
        problem=problem,
        method="trust_region",
        seed_name=seed_name,
        solver_success=bool(solved.success),
        iterations=int(solved.njev or 0),
        function_evaluations=int(solved.nfev),
        coordinates=coordinates,
        solver_coordinates=np.asarray(solved.x, dtype=float),
        fixed_scales=scales,
        pattern=pattern,
        settings=settings,
        reason=str(solved.message),
    )


def solve_reduced_pseudo_transient(
    problem: DirectSteadyStateProblem,
    initial_vector: Sequence[float],
    *,
    seed_name: str,
    fixed_scales: Sequence[float],
    settings: FixedSolverSettings,
) -> ReducedSolveAttempt:
    """Apply a full-system pseudo-transient Newton method in smooth coordinates."""
    stage = _full_stage(problem)
    initial = np.asarray(initial_vector, dtype=float)
    initial_evaluation = evaluate_direct_steady_state_residual(problem, initial)
    coordinates = SmoothPhysicalCoordinates(
        problem, initial, initial_evaluation.variable_scales
    )
    current = coordinates.encode(initial, stage.unknown_indices)
    lower, upper = coordinates.bounds(stage.unknown_indices)
    scales = np.asarray(fixed_scales, dtype=float)
    pattern = stage_structural_pattern(problem, stage)
    pseudo_time = float(settings.pseudo_time_initial)
    function_evaluations = 0
    message = "maximum pseudo-transient iterations reached"
    solver_success = False

    def residual(value: np.ndarray) -> np.ndarray:
        nonlocal function_evaluations
        function_evaluations += 1
        physical = coordinates.decode(value, stage.unknown_indices)
        return evaluate_direct_steady_state_residual(problem, physical).raw / scales

    iterations = 0
    for iterations in range(1, settings.pseudo_transient_max_iterations + 1):
        base = residual(current)
        if float(np.max(np.abs(base))) < settings.residual_tolerance:
            solver_success = True
            message = "physical residual tolerance reached"
            break
        jacobian = finite_difference_stage_jacobian(
            residual, current, pattern
        ).toarray()
        regularized = jacobian + np.eye(jacobian.shape[0]) / pseudo_time
        try:
            step = np.linalg.solve(regularized, -base)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(regularized, -base, rcond=None)[0]

        accepted_step = False
        for line_search_index in range(
            settings.pseudo_transient_line_search_steps
        ):
            fraction = 0.5**line_search_index
            candidate = current + fraction * step
            if np.any(candidate <= lower) or np.any(candidate >= upper):
                continue
            try:
                trial = residual(candidate)
            except Exception:
                continue
            if np.linalg.norm(trial) < np.linalg.norm(base):
                current = candidate
                accepted_step = True
                pseudo_time = min(
                    settings.pseudo_time_maximum,
                    pseudo_time * settings.pseudo_time_growth,
                )
                break
        if not accepted_step:
            pseudo_time *= settings.pseudo_time_reduction
            if pseudo_time < settings.pseudo_time_minimum:
                message = "minimum pseudo-time reached without a decreasing step"
                break
    else:
        iterations = settings.pseudo_transient_max_iterations

    if not solver_success:
        try:
            solver_success = bool(
                np.max(np.abs(residual(current))) < settings.residual_tolerance
            )
            if solver_success:
                message = "physical residual tolerance reached"
        except Exception:
            solver_success = False
    return _attempt_result(
        problem=problem,
        method="pseudo_transient",
        seed_name=seed_name,
        solver_success=solver_success,
        iterations=iterations,
        function_evaluations=function_evaluations,
        coordinates=coordinates,
        solver_coordinates=current,
        fixed_scales=scales,
        pattern=pattern,
        settings=settings,
        reason=message,
    )


def _root_agreement(
    attempts: Sequence[ReducedSolveAttempt],
    variable_scales: np.ndarray,
) -> float:
    accepted = [attempt for attempt in attempts if attempt.accepted]
    if len(accepted) < 2:
        return float("inf")
    maximum = 0.0
    for left_index, left in enumerate(accepted):
        for right in accepted[left_index + 1 :]:
            delta = np.abs(left.final_vector - right.final_vector) / np.maximum(
                variable_scales, 1.0e-30
            )
            maximum = max(maximum, float(np.max(delta)))
    return maximum


def run_reduced_feasibility_study(
    case: ReducedFeasibilityCase,
    *,
    settings: FixedSolverSettings = FixedSolverSettings(),
) -> ReducedFeasibilityStudy:
    """Run the one permitted reduced study without adaptive recipe changes."""
    problem = case.problem
    chemsep = build_chemsep_guess(problem)
    perturbed = build_reduced_perturbed_guess(problem, chemsep)
    seed_vectors = (("chemsep", chemsep), ("perturbed_chemsep", perturbed))
    base = evaluate_direct_steady_state_residual(problem, chemsep)
    initial_audits: list[tuple[str, NumericalJacobianAudit]] = []
    for seed_name, vector in seed_vectors:
        initial_audits.append(
            (
                seed_name,
                audit_numerical_jacobian(
                    problem, vector, step_factor=1.0, mode="colored"
                ),
            )
        )
        initial_audits.append(
            (
                f"{seed_name}_half_step",
                audit_numerical_jacobian(
                    problem, vector, step_factor=0.5, mode="colored"
                ),
            )
        )
    size = len(problem.registry.unknowns)
    numerical_gate = bool(
        case.structure.pass_gate
        and all(
            audit.rank == size
            and audit.condition_estimate < settings.condition_limit
            and not audit.near_zero_rows
            and not audit.near_zero_columns
            for _, audit in initial_audits
        )
    )
    attempts: list[ReducedSolveAttempt] = []
    if numerical_gate:
        for seed_name, vector in seed_vectors:
            attempts.append(
                solve_reduced_trust_region(
                    problem,
                    vector,
                    seed_name=seed_name,
                    fixed_scales=base.residual_scales,
                    settings=settings,
                )
            )
        for seed_name, vector in seed_vectors:
            attempts.append(
                solve_reduced_pseudo_transient(
                    problem,
                    vector,
                    seed_name=seed_name,
                    fixed_scales=base.residual_scales,
                    settings=settings,
                )
            )

    agreement = _root_agreement(attempts, base.variable_scales)
    methods = {attempt.method for attempt in attempts if attempt.accepted}
    accepted = bool(
        numerical_gate
        and len(attempts) == 4
        and all(attempt.accepted for attempt in attempts)
        and methods == {"trust_region", "pseudo_transient"}
        and agreement < settings.root_agreement_tolerance
    )
    if accepted:
        classification = "reduced_feasibility_pass_full_ptc_authorized"
        decision = (
            "The five-volume conserved system reaches the same physical root "
            "from both seeds with both fixed solvers. Full-system "
            "pseudo-transient development is authorized."
        )
    elif not numerical_gate:
        classification = "reduced_feasibility_structural_or_numerical_gate_failed"
        decision = (
            "The five-volume direct system failed its rank/conditioning gate. "
            "Retire the present conserved formulation; do not start a "
            "full-system pseudo-transient program."
        )
    else:
        classification = "reduced_feasibility_solve_gate_failed"
        decision = (
            "The five-volume direct system did not pass both fixed solvers "
            "from both predefined seeds without safeguards. Retire the present "
            "conserved formulation; do not add topology or tuning variants."
        )
    return ReducedFeasibilityStudy(
        schema_id=REDUCED_FEASIBILITY_SCHEMA,
        mapping=case.mapping,
        structure=case.structure,
        initial_numerical_audits=tuple(initial_audits),
        numerical_gate_pass=numerical_gate,
        attempts=tuple(attempts),
        root_agreement_max_scaled_difference=agreement,
        accepted=accepted,
        classification=classification,
        decision=decision,
    )
