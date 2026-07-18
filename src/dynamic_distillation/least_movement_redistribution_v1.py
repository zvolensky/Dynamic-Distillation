"""
Sequential least-movement N+U redistribution without hydraulic equations.

The solver minimizes normalized component-inventory and internal-energy
movement from a checkpoint. Whole-column component and energy totals are hard
linear constraints. Local UV closure is reevaluated nonlinearly after each
sequential pressure-ordering subproblem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize

from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    ConservativeNodeTarget,
    FixedPressureNodeClosure,
    solve_fixed_pressure_node,
)
from dynamic_distillation.frozen_checkpoint_closure_v1 import _solve_scaled_local_uv
from dynamic_distillation.uv_flash_stage_v1 import (
    UvFlashStageGuess,
    UvFlashStageResult,
    solve_uv_flash_stage,
)


@dataclass(frozen=True)
class MovementScales:
    component_lbmol: np.ndarray
    energy_BTU: np.ndarray


@dataclass(frozen=True)
class RedistributedNodeState:
    node_id: str
    position_1based: int
    component_inventory_lbmol: np.ndarray
    internal_energy_BTU: float
    closure: UvFlashStageResult
    component_relative_residual: float
    energy_relative_residual: float
    volume_relative_residual: float
    equilibrium_beta_residual: float
    active_bound_count: int


@dataclass(frozen=True)
class LeastMovementIteration:
    iteration: int
    objective: float
    component_objective: float
    energy_objective: float
    maximum_pressure_order_violation_psi: float
    minimum_pressure_increment_psi: float
    step_norm: float
    accepted_step_fraction: float
    subproblem_success: bool
    subproblem_iterations: int
    first_order_optimality_norm: float
    active_linear_constraint_count: int
    uv_solves: int
    termination_reason: str


@dataclass(frozen=True)
class RedistributionPatternDiagnostics:
    material_move_L1_lbmol: float
    material_move_L1_by_component_lbmol: np.ndarray
    energy_move_L1_BTU: float
    component_donor_lbmol: np.ndarray
    component_receiver_lbmol: np.ndarray
    energy_donor_BTU: float
    energy_receiver_BTU: float
    component_sign_reversals: np.ndarray
    energy_sign_reversals: int
    maximum_scaled_component_change: float
    maximum_scaled_energy_change: float
    terminal_component_abs_fraction: float
    terminal_energy_abs_fraction: float
    maximum_pressure_change_psi: float
    pressure_rms_change_psi: float


@dataclass(frozen=True)
class LeastMovementRedistributionResult:
    nodes: tuple[RedistributedNodeState, ...]
    iterations: tuple[LeastMovementIteration, ...]
    normalized_component_change: np.ndarray
    normalized_energy_change: np.ndarray
    component_change_lbmol: np.ndarray
    energy_change_BTU: np.ndarray
    objective: float
    component_objective: float
    energy_objective: float
    component_conservation_error_lbmol: np.ndarray
    component_conservation_relative_max: float
    energy_conservation_error_BTU: float
    energy_conservation_relative: float
    minimum_pressure_increment_psi: float
    maximum_pressure_order_violation_psi: float
    pressure_ordering_pass: bool
    all_local_closures_pass: bool
    active_bound_count: int
    first_order_optimality_norm: float
    constraint_violation_norm: float
    total_uv_solves: int
    optimizer_termination_reason: str
    diagnostics: RedistributionPatternDiagnostics
    converged: bool
    classification: str


@dataclass(frozen=True)
class MultiStartAssessment:
    start_names: tuple[str, ...]
    successful_start_names: tuple[str, ...]
    objective_values: np.ndarray
    minimum_objective: float
    maximum_objective: float
    relative_objective_spread: float
    required_relative_spread: float
    reproducible_minimum_pass: bool
    best_start_name: Optional[str]


class _MovementLayout:
    def __init__(self, n_nodes: int, n_components: int):
        self.n_nodes = int(n_nodes)
        self.n_components = int(n_components)
        self.n_component_values = self.n_nodes * self.n_components
        self.size = self.n_component_values + self.n_nodes

    def join(self, q_component: np.ndarray, q_energy: np.ndarray) -> np.ndarray:
        return np.concatenate(
            [
                np.asarray(q_component, dtype=float).reshape((-1,)),
                np.asarray(q_energy, dtype=float).reshape((-1,)),
            ]
        )

    def split(self, q: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
        arr = np.asarray(q, dtype=float).reshape((self.size,))
        return (
            arr[: self.n_component_values].reshape(
                (self.n_nodes, self.n_components)
            ),
            arr[self.n_component_values :].reshape((self.n_nodes,)),
        )


def build_movement_scales(
    targets: Sequence[ConservativeNodeTarget],
    *,
    scale_mode: str = "local-relative",
    component_fraction_floor: float = 1.0e-3,
    component_absolute_floor_lbmol: float = 1.0e-6,
    energy_per_mole_scale_BTU_lbmol: float = 1000.0,
    energy_absolute_floor_BTU: float = 1000.0,
) -> MovementScales:
    nodes = tuple(targets)
    n0 = np.vstack(
        [
            np.asarray(node.total_component_inventory_lbmol, dtype=float)
            for node in nodes
        ]
    )
    total_node = np.sum(n0, axis=1)
    u0 = np.asarray(
        [node.total_internal_energy_BTU for node in nodes],
        dtype=float,
    )
    mode = str(scale_mode).strip().lower()
    if mode == "local-relative":
        component_scale = np.maximum(
            n0,
            float(component_fraction_floor) * total_node[:, None],
        )
        component_scale = np.maximum(
            component_scale,
            float(component_absolute_floor_lbmol),
        )
        energy_scale = np.maximum(
            np.abs(u0),
            total_node * float(energy_per_mole_scale_BTU_lbmol),
        )
        energy_scale = np.maximum(
            energy_scale,
            float(energy_absolute_floor_BTU),
        )
    elif mode == "column-common":
        component_column = np.maximum(
            np.sum(n0, axis=0),
            float(component_absolute_floor_lbmol),
        )
        component_scale = np.tile(component_column, (n0.shape[0], 1))
        energy_column = max(
            abs(float(np.sum(u0))),
            float(np.sum(total_node))
            * float(energy_per_mole_scale_BTU_lbmol),
            float(energy_absolute_floor_BTU),
        )
        energy_scale = np.full(n0.shape[0], energy_column, dtype=float)
    else:
        raise ValueError(
            "scale_mode must be 'local-relative' or 'column-common'"
        )
    return MovementScales(
        component_lbmol=np.asarray(component_scale, dtype=float),
        energy_BTU=np.asarray(energy_scale, dtype=float),
    )


def conservative_random_start(
    *,
    targets: Sequence[ConservativeNodeTarget],
    scales: MovementScales,
    relative_magnitude: float,
    seed: int,
) -> np.ndarray:
    """Build a globally conservative randomized normalized movement vector."""
    nodes = tuple(targets)
    n0 = np.vstack(
        [
            np.asarray(node.total_component_inventory_lbmol, dtype=float)
            for node in nodes
        ]
    )
    layout = _MovementLayout(n0.shape[0], n0.shape[1])
    rng = np.random.default_rng(int(seed))
    delta_n = (
        float(relative_magnitude)
        * np.asarray(scales.component_lbmol, dtype=float)
        * rng.normal(size=n0.shape)
    )
    delta_n -= np.mean(delta_n, axis=0, keepdims=True)
    delta_u = (
        float(relative_magnitude)
        * np.asarray(scales.energy_BTU, dtype=float)
        * rng.normal(size=n0.shape[0])
    )
    delta_u -= float(np.mean(delta_u))

    alpha = 1.0
    negative = delta_n < 0.0
    if np.any(negative):
        alpha = min(
            alpha,
            float(
                np.min(
                    0.8
                    * n0[negative]
                    / np.maximum(-delta_n[negative], 1.0e-300)
                )
            ),
        )
    alpha = float(np.clip(alpha, 0.0, 1.0))
    delta_n *= alpha
    delta_u *= alpha
    return layout.join(
        delta_n / np.asarray(scales.component_lbmol, dtype=float),
        delta_u / np.asarray(scales.energy_BTU, dtype=float),
    )


def normalized_movement_from_absolute_state(
    *,
    targets: Sequence[ConservativeNodeTarget],
    scales: MovementScales,
    component_inventory_lbmol: np.ndarray,
    internal_energy_BTU: Sequence[float],
) -> np.ndarray:
    nodes = tuple(targets)
    n0 = np.vstack(
        [
            np.asarray(node.total_component_inventory_lbmol, dtype=float)
            for node in nodes
        ]
    )
    u0 = np.asarray(
        [node.total_internal_energy_BTU for node in nodes],
        dtype=float,
    )
    n_values = np.asarray(component_inventory_lbmol, dtype=float).reshape(n0.shape)
    u_values = np.asarray(internal_energy_BTU, dtype=float).reshape(u0.shape)
    layout = _MovementLayout(n0.shape[0], n0.shape[1])
    return layout.join(
        (n_values - n0) / np.asarray(scales.component_lbmol, dtype=float),
        (u_values - u0) / np.asarray(scales.energy_BTU, dtype=float),
    )


def build_energy_only_pressure_profile_start(
    *,
    provider: Any,
    targets: Sequence[ConservativeNodeTarget],
    base_pressure_psia: Sequence[float],
    scales: Optional[MovementScales] = None,
) -> tuple[np.ndarray, tuple[FixedPressureNodeClosure, ...]]:
    """Build a globally energy-conservative fixed-N start for an ordered profile."""
    nodes = tuple(targets)
    base_pressure = np.asarray(base_pressure_psia, dtype=float).reshape(
        (len(nodes),)
    )
    if np.any(np.diff(base_pressure) < 0.0):
        raise ValueError("base pressure profile must be nondecreasing")
    if scales is None:
        scales = build_movement_scales(nodes)
    total_u = float(
        sum(float(node.total_internal_energy_BTU) for node in nodes)
    )
    cache: dict[
        float,
        tuple[float, tuple[FixedPressureNodeClosure, ...]],
    ] = {}

    def evaluate(shift: float):
        key = float(np.round(float(shift), 12))
        if key in cache:
            return cache[key]
        pressures = base_pressure + float(shift)
        if np.min(pressures) <= 1.0 or np.max(pressures) >= 1000.0:
            raise ValueError("shifted linear pressure profile exceeds bounds")
        rows = tuple(
            solve_fixed_pressure_node(
                provider=provider,
                target=node,
                pressure_psia=float(pressure),
            )
            for node, pressure in zip(nodes, pressures)
        )
        if not all(row.converged for row in rows):
            raise RuntimeError("linear pressure start failed fixed-pressure closure")
        error = float(
            sum(row.implied_internal_energy_BTU for row in rows) - total_u
        )
        cache[key] = (error, rows)
        return cache[key]

    evaluated: dict[float, float] = {}
    bracket = None
    for magnitude in (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0):
        candidates = (0.0,) if magnitude == 0.0 else (-magnitude, magnitude)
        for shift in candidates:
            try:
                error, _rows = evaluate(float(shift))
            except (RuntimeError, ValueError):
                continue
            evaluated[float(shift)] = float(error)
        ordered = sorted(evaluated.items())
        for (left, f_left), (right, f_right) in zip(ordered[:-1], ordered[1:]):
            if f_left == 0.0:
                bracket = (left, left)
                break
            if f_right == 0.0 or f_left * f_right < 0.0:
                bracket = (left, right)
                break
        if bracket is not None:
            break
    if bracket is None:
        raise RuntimeError("linear pressure start could not bracket global energy")

    if bracket[0] == bracket[1]:
        shift = float(bracket[0])
        error, rows = evaluate(shift)
    else:
        left, right = map(float, bracket)
        f_left = float(evaluated[left])
        f_right = float(evaluated[right])
        rows = ()
        error = float("inf")
        shift = 0.5 * (left + right)
        for _ in range(30):
            secant_candidate = (
                left * f_right - right * f_left
            ) / (f_right - f_left)
            secant_candidate = float(
                np.clip(
                    secant_candidate,
                    left + 0.05 * (right - left),
                    right - 0.05 * (right - left),
                )
            )
            trial_shifts = [secant_candidate]
            trial_shifts.extend(
                left + fraction * (right - left)
                for fraction in (
                    0.5,
                    0.25,
                    0.75,
                    0.125,
                    0.375,
                    0.625,
                    0.875,
                    0.05,
                    0.95,
                )
            )
            feasible = []
            for trial_shift in trial_shifts:
                try:
                    trial_error, trial_rows = evaluate(float(trial_shift))
                except (RuntimeError, ValueError):
                    continue
                feasible.append(
                    (
                        abs(float(trial_error)),
                        float(trial_shift),
                        float(trial_error),
                        trial_rows,
                    )
                )
            if not feasible:
                raise RuntimeError(
                    "linear pressure start has no feasible closure inside "
                    "the global-energy bracket"
                )
            _absolute_error, candidate, error, candidate_rows = min(
                feasible,
                key=lambda item: item[0],
            )
            shift = candidate
            rows = candidate_rows
            if abs(error) / max(abs(total_u), 1.0) < 1.0e-8:
                break
            if f_left * error <= 0.0:
                right = candidate
                f_right = error
            else:
                left = candidate
                f_left = error
        if not rows or abs(error) / max(abs(total_u), 1.0) >= 1.0e-8:
            raise RuntimeError("linear pressure start did not conserve global energy")

    n_values = np.vstack(
        [
            np.asarray(node.total_component_inventory_lbmol, dtype=float)
            for node in nodes
        ]
    )
    u_values = np.asarray(
        [row.implied_internal_energy_BTU for row in rows],
        dtype=float,
    )
    q = normalized_movement_from_absolute_state(
        targets=nodes,
        scales=scales,
        component_inventory_lbmol=n_values,
        internal_energy_BTU=u_values,
    )
    return q, rows


def assess_multistart_results(
    *,
    results: Sequence[tuple[str, LeastMovementRedistributionResult]],
    required_relative_spread: float = 1.0e-4,
) -> MultiStartAssessment:
    named = tuple(results)
    successful = tuple(
        (name, result)
        for name, result in named
        if bool(result.converged) and np.isfinite(float(result.objective))
    )
    objectives = np.asarray(
        [float(result.objective) for _name, result in successful],
        dtype=float,
    )
    if objectives.size:
        minimum = float(np.min(objectives))
        maximum = float(np.max(objectives))
        spread = (maximum - minimum) / max(abs(minimum), 1.0)
        best_index = int(np.argmin(objectives))
        best_name: Optional[str] = str(successful[best_index][0])
    else:
        minimum = float("inf")
        maximum = float("inf")
        spread = float("inf")
        best_name = None
    reproducible = bool(
        objectives.size >= 2
        and spread < float(required_relative_spread)
    )
    return MultiStartAssessment(
        start_names=tuple(str(name) for name, _result in named),
        successful_start_names=tuple(
            str(name) for name, _result in successful
        ),
        objective_values=objectives,
        minimum_objective=float(minimum),
        maximum_objective=float(maximum),
        relative_objective_spread=float(spread),
        required_relative_spread=float(required_relative_spread),
        reproducible_minimum_pass=bool(reproducible),
        best_start_name=best_name,
    )


def _solve_node(
    *,
    provider: Any,
    target: ConservativeNodeTarget,
    component_inventory_lbmol: np.ndarray,
    internal_energy_BTU: float,
    guess: UvFlashStageGuess,
) -> RedistributedNodeState:
    inventory = np.asarray(component_inventory_lbmol, dtype=float).reshape((-1,))
    total = float(np.sum(inventory))
    if total <= 1.0e-10 or np.any(inventory <= 0.0):
        raise ValueError(f"{target.node_id} has nonpositive component inventory")
    z = inventory / total
    u_target = float(internal_energy_BTU) / total
    v_target = float(target.fixed_total_volume_ft3) / total
    result = solve_uv_flash_stage(
        provider,
        z_overall=z,
        u_target_BTU_lbmol=u_target,
        v_target_ft3_lbmol=v_target,
        guess=guess,
        beta_mode="free",
        max_iter=20,
        tol_u_BTU_lbmol=max(abs(u_target) * 1.0e-9, 1.0e-7),
        tol_v_ft3_lbmol=max(abs(v_target) * 1.0e-9, 1.0e-11),
        tol_beta=1.0e-9,
    )
    if not result.converged:
        result = _solve_scaled_local_uv(
            provider=provider,
            z=z,
            u_target=u_target,
            v_target=v_target,
            guess=guess,
        )
    beta = float(result.beta_vapor)
    reconstructed = (
        (1.0 - beta) * np.asarray(result.x, dtype=float)
        + beta * np.asarray(result.y, dtype=float)
    )
    component_relative = float(
        np.max(np.abs(reconstructed - z) / np.maximum(np.abs(z), 1.0e-12))
    )
    energy_relative = abs(float(result.residual_u_BTU_lbmol)) / max(
        abs(u_target),
        1.0,
    )
    volume_relative = abs(float(result.residual_v_ft3_lbmol)) / max(
        abs(v_target),
        1.0e-12,
    )
    active_bounds = int(
        result.T_F <= -200.0 + 1.0e-6
        or result.T_F >= 1000.0 - 1.0e-6
    ) + int(
        result.P_psia <= 1.0 + 1.0e-6
        or result.P_psia >= 1000.0 - 1.0e-6
    ) + int(
        result.beta_vapor <= 1.0e-8 + 1.0e-8
        or result.beta_vapor >= 1.0 - 2.0e-8
    )
    return RedistributedNodeState(
        node_id=str(target.node_id),
        position_1based=int(target.position_1based),
        component_inventory_lbmol=inventory.copy(),
        internal_energy_BTU=float(internal_energy_BTU),
        closure=result,
        component_relative_residual=float(component_relative),
        energy_relative_residual=float(energy_relative),
        volume_relative_residual=float(volume_relative),
        equilibrium_beta_residual=abs(float(result.residual_beta)),
        active_bound_count=int(active_bounds),
    )


def _absolute_state(
    *,
    q: np.ndarray,
    layout: _MovementLayout,
    n0: np.ndarray,
    u0: np.ndarray,
    scales: MovementScales,
) -> tuple[np.ndarray, np.ndarray]:
    qn, qu = layout.split(q)
    return (
        n0 + np.asarray(scales.component_lbmol, dtype=float) * qn,
        u0 + np.asarray(scales.energy_BTU, dtype=float) * qu,
    )


def _evaluate_state(
    *,
    provider: Any,
    targets: tuple[ConservativeNodeTarget, ...],
    q: np.ndarray,
    layout: _MovementLayout,
    n0: np.ndarray,
    u0: np.ndarray,
    scales: MovementScales,
    guesses: Optional[Sequence[UvFlashStageGuess]] = None,
) -> tuple[tuple[RedistributedNodeState, ...], int]:
    n_values, u_values = _absolute_state(
        q=q,
        layout=layout,
        n0=n0,
        u0=u0,
        scales=scales,
    )
    if guesses is None:
        guesses = tuple(
            UvFlashStageGuess(
                T_F=float(node.initial_temperature_F),
                P_psia=float(node.initial_pressure_psia),
                beta_vapor=float(node.initial_beta_vapor),
            )
            for node in targets
        )
    rows = tuple(
        _solve_node(
            provider=provider,
            target=node,
            component_inventory_lbmol=n_values[idx, :],
            internal_energy_BTU=float(u_values[idx]),
            guess=guesses[idx],
        )
        for idx, node in enumerate(targets)
    )
    return rows, len(rows)


def _pressure_sensitivities(
    *,
    provider: Any,
    targets: tuple[ConservativeNodeTarget, ...],
    q: np.ndarray,
    rows: tuple[RedistributedNodeState, ...],
    layout: _MovementLayout,
    n0: np.ndarray,
    u0: np.ndarray,
    scales: MovementScales,
    relative_step: float,
) -> tuple[np.ndarray, int]:
    n_values, u_values = _absolute_state(
        q=q,
        layout=layout,
        n0=n0,
        u0=u0,
        scales=scales,
    )
    sensitivities = np.zeros(
        (layout.n_nodes, layout.n_components + 1),
        dtype=float,
    )
    uv_solves = 0
    for idx, (target, base_row) in enumerate(zip(targets, rows)):
        base_pressure = float(base_row.closure.P_psia)
        base_guess = UvFlashStageGuess(
            T_F=float(base_row.closure.T_F),
            P_psia=base_pressure,
            beta_vapor=float(base_row.closure.beta_vapor),
        )
        for comp in range(layout.n_components):
            step_q = float(relative_step)
            perturbed_n = n_values[idx, :].copy()
            perturbed_n[comp] += (
                float(scales.component_lbmol[idx, comp]) * step_q
            )
            trial = _solve_node(
                provider=provider,
                target=target,
                component_inventory_lbmol=perturbed_n,
                internal_energy_BTU=float(u_values[idx]),
                guess=base_guess,
            )
            uv_solves += 1
            sensitivities[idx, comp] = (
                float(trial.closure.P_psia) - base_pressure
            ) / step_q
        perturbed_u = float(
            u_values[idx] + float(scales.energy_BTU[idx]) * relative_step
        )
        trial_u = _solve_node(
            provider=provider,
            target=target,
            component_inventory_lbmol=n_values[idx, :],
            internal_energy_BTU=perturbed_u,
            guess=base_guess,
        )
        uv_solves += 1
        sensitivities[idx, -1] = (
            float(trial_u.closure.P_psia) - base_pressure
        ) / float(relative_step)
    return sensitivities, uv_solves


def _objective_parts(q: np.ndarray, layout: _MovementLayout) -> tuple[float, float, float]:
    qn, qu = layout.split(q)
    jn = float(np.sum(np.square(qn)))
    ju = float(np.sum(np.square(qu)))
    return jn + ju, jn, ju


def _conservation_matrix(
    *,
    layout: _MovementLayout,
    scales: MovementScales,
) -> np.ndarray:
    matrix = np.zeros(
        (layout.n_components + 1, layout.size),
        dtype=float,
    )
    for node in range(layout.n_nodes):
        for comp in range(layout.n_components):
            matrix[
                comp,
                node * layout.n_components + comp,
            ] = float(scales.component_lbmol[node, comp])
        matrix[
            -1,
            layout.n_component_values + node,
        ] = float(scales.energy_BTU[node])
    return matrix


def _pressure_linear_constraint(
    *,
    layout: _MovementLayout,
    q_current: np.ndarray,
    pressures: np.ndarray,
    sensitivities: np.ndarray,
    minimum_pressure_increment_psi: float,
) -> LinearConstraint:
    matrix = np.zeros((layout.n_nodes - 1, layout.size), dtype=float)
    lower = np.zeros(layout.n_nodes - 1, dtype=float)
    for idx in range(layout.n_nodes - 1):
        for comp in range(layout.n_components):
            matrix[idx, (idx + 1) * layout.n_components + comp] = (
                sensitivities[idx + 1, comp]
            )
            matrix[idx, idx * layout.n_components + comp] = (
                -sensitivities[idx, comp]
            )
        matrix[idx, layout.n_component_values + idx + 1] = (
            sensitivities[idx + 1, -1]
        )
        matrix[idx, layout.n_component_values + idx] = (
            -sensitivities[idx, -1]
        )
        lower[idx] = (
            float(minimum_pressure_increment_psi)
            - float(pressures[idx + 1] - pressures[idx])
            + float(matrix[idx, :] @ q_current)
        )
    return LinearConstraint(matrix, lower, np.full(lower.size, np.inf))


def _movement_bounds(
    *,
    layout: _MovementLayout,
    n0: np.ndarray,
    scales: MovementScales,
    maximum_scaled_movement: float,
) -> Bounds:
    lower_n = -(n0 - 1.0e-10) / np.asarray(scales.component_lbmol, dtype=float)
    lower_n = np.maximum(lower_n, -float(maximum_scaled_movement))
    upper_n = np.full_like(lower_n, float(maximum_scaled_movement))
    lower_u = np.full(layout.n_nodes, -float(maximum_scaled_movement))
    upper_u = np.full(layout.n_nodes, float(maximum_scaled_movement))
    return Bounds(
        layout.join(lower_n, lower_u),
        layout.join(upper_n, upper_u),
    )


def _first_order_optimality(
    *,
    q: np.ndarray,
    equality_matrix: np.ndarray,
    pressure_constraint: LinearConstraint,
    bounds: Bounds,
    active_tolerance: float = 1.0e-7,
) -> tuple[float, int]:
    gradient = 2.0 * np.asarray(q, dtype=float)
    rows = [np.asarray(equality_matrix, dtype=float)]
    pressure_values = np.asarray(pressure_constraint.A @ q, dtype=float)
    pressure_lower = np.asarray(pressure_constraint.lb, dtype=float)
    active_pressure = np.where(
        pressure_values - pressure_lower <= active_tolerance
    )[0]
    if active_pressure.size:
        rows.append(np.asarray(pressure_constraint.A, dtype=float)[active_pressure, :])
    lower_active = np.where(
        np.asarray(q) - np.asarray(bounds.lb) <= active_tolerance
    )[0]
    upper_active = np.where(
        np.asarray(bounds.ub) - np.asarray(q) <= active_tolerance
    )[0]
    bound_rows = []
    for idx in lower_active:
        row = np.zeros(q.size, dtype=float)
        row[idx] = 1.0
        bound_rows.append(row)
    for idx in upper_active:
        row = np.zeros(q.size, dtype=float)
        row[idx] = 1.0
        bound_rows.append(row)
    if bound_rows:
        rows.append(np.vstack(bound_rows))
    active_matrix = np.vstack(rows)
    multipliers, *_ = np.linalg.lstsq(
        active_matrix.T,
        -gradient,
        rcond=None,
    )
    stationarity = gradient + active_matrix.T @ multipliers
    return (
        float(np.linalg.norm(stationarity, ord=np.inf)),
        int(active_pressure.size + len(bound_rows)),
    )


def _sign_reversals(values: np.ndarray, tolerance: float = 1.0e-12) -> int:
    signs = np.sign(np.asarray(values, dtype=float))
    signs = signs[np.abs(np.asarray(values, dtype=float)) > tolerance]
    if signs.size <= 1:
        return 0
    return int(np.sum(signs[1:] != signs[:-1]))


def solve_least_movement_redistribution(
    *,
    provider: Any,
    targets: Sequence[ConservativeNodeTarget],
    movement_scales: Optional[MovementScales] = None,
    initial_normalized_movement: Optional[Sequence[float]] = None,
    minimum_pressure_increment_psi: float = 0.01,
    maximum_outer_iterations: int = 8,
    sensitivity_relative_step: float = 1.0e-4,
    maximum_scaled_movement: float = 10.0,
) -> LeastMovementRedistributionResult:
    """Run the sequential normalized-L2 N+U redistribution solve."""
    nodes = tuple(targets)
    if len(nodes) < 2:
        raise ValueError("least-movement solve requires at least two nodes")
    n0 = np.vstack(
        [
            np.asarray(node.total_component_inventory_lbmol, dtype=float)
            for node in nodes
        ]
    )
    u0 = np.asarray(
        [node.total_internal_energy_BTU for node in nodes],
        dtype=float,
    )
    layout = _MovementLayout(n0.shape[0], n0.shape[1])
    scales = (
        build_movement_scales(nodes)
        if movement_scales is None
        else movement_scales
    )
    component_scale = np.asarray(scales.component_lbmol, dtype=float)
    energy_scale = np.asarray(scales.energy_BTU, dtype=float)
    if component_scale.shape != n0.shape:
        raise ValueError(
            "movement component scales do not match target shape"
        )
    if energy_scale.shape != u0.shape:
        raise ValueError("movement energy scales do not match target shape")
    if (
        np.any(~np.isfinite(component_scale))
        or np.any(component_scale <= 0.0)
        or np.any(~np.isfinite(energy_scale))
        or np.any(energy_scale <= 0.0)
    ):
        raise ValueError("movement scales must be finite and positive")
    q = (
        np.zeros(layout.size, dtype=float)
        if initial_normalized_movement is None
        else np.asarray(initial_normalized_movement, dtype=float).reshape(
            (layout.size,)
        )
    )
    equality_matrix = _conservation_matrix(layout=layout, scales=scales)
    conservation_initial = equality_matrix @ q
    if np.linalg.norm(conservation_initial, ord=np.inf) > 1.0e-7:
        correction = equality_matrix.T @ np.linalg.solve(
            equality_matrix @ equality_matrix.T,
            conservation_initial,
        )
        q = q - correction
    bounds = _movement_bounds(
        layout=layout,
        n0=n0,
        scales=scales,
        maximum_scaled_movement=maximum_scaled_movement,
    )
    q = np.minimum(np.maximum(q, bounds.lb + 1.0e-10), bounds.ub - 1.0e-10)

    rows, uv_count = _evaluate_state(
        provider=provider,
        targets=nodes,
        q=q,
        layout=layout,
        n0=n0,
        u0=u0,
        scales=scales,
    )
    total_uv_solves = int(uv_count)
    history: list[LeastMovementIteration] = []
    last_optimality = float("inf")
    termination = "maximum outer iterations reached"

    for outer in range(1, int(maximum_outer_iterations) + 1):
        pressures = np.asarray(
            [row.closure.P_psia for row in rows],
            dtype=float,
        )
        violation = float(
            np.max(
                np.maximum(
                    float(minimum_pressure_increment_psi)
                    - np.diff(pressures),
                    0.0,
                )
            )
        )
        sensitivities, sensitivity_solves = _pressure_sensitivities(
            provider=provider,
            targets=nodes,
            q=q,
            rows=rows,
            layout=layout,
            n0=n0,
            u0=u0,
            scales=scales,
            relative_step=float(sensitivity_relative_step),
        )
        total_uv_solves += int(sensitivity_solves)
        pressure_constraint = _pressure_linear_constraint(
            layout=layout,
            q_current=q,
            pressures=pressures,
            sensitivities=sensitivities,
            minimum_pressure_increment_psi=float(
                minimum_pressure_increment_psi
            ),
        )
        constraints = (
            LinearConstraint(
                equality_matrix,
                np.zeros(equality_matrix.shape[0]),
                np.zeros(equality_matrix.shape[0]),
            ),
            pressure_constraint,
        )
        solved = minimize(
            lambda candidate: float(np.dot(candidate, candidate)),
            q,
            jac=lambda candidate: 2.0 * np.asarray(candidate, dtype=float),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={
                "ftol": 1.0e-12,
                "maxiter": 500,
                "disp": False,
            },
        )
        target_q = np.asarray(solved.x, dtype=float)
        step = target_q - q
        step_norm = float(np.linalg.norm(step))
        last_optimality, active_linear = _first_order_optimality(
            q=target_q,
            equality_matrix=equality_matrix,
            pressure_constraint=pressure_constraint,
            bounds=bounds,
        )
        if step_norm < 1.0e-7 and violation <= 1.0e-6:
            objective, jn, ju = _objective_parts(q, layout)
            history.append(
                LeastMovementIteration(
                    iteration=int(outer),
                    objective=objective,
                    component_objective=jn,
                    energy_objective=ju,
                    maximum_pressure_order_violation_psi=violation,
                    minimum_pressure_increment_psi=float(np.min(np.diff(pressures))),
                    step_norm=step_norm,
                    accepted_step_fraction=0.0,
                    subproblem_success=bool(solved.success),
                    subproblem_iterations=int(getattr(solved, "nit", 0)),
                    first_order_optimality_norm=last_optimality,
                    active_linear_constraint_count=active_linear,
                    uv_solves=int(sensitivity_solves),
                    termination_reason="ordered stationary point",
                )
            )
            termination = "ordered stationary point"
            break

        guesses = tuple(
            UvFlashStageGuess(
                T_F=float(row.closure.T_F),
                P_psia=float(row.closure.P_psia),
                beta_vapor=float(row.closure.beta_vapor),
            )
            for row in rows
        )
        current_objective = float(np.dot(q, q))
        candidates = []
        line_uv_solves = 0
        for alpha in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
            trial_q = q + float(alpha) * step
            try:
                trial_rows, trial_count = _evaluate_state(
                    provider=provider,
                    targets=nodes,
                    q=trial_q,
                    layout=layout,
                    n0=n0,
                    u0=u0,
                    scales=scales,
                    guesses=guesses,
                )
            except (RuntimeError, ValueError):
                continue
            line_uv_solves += int(trial_count)
            trial_pressures = np.asarray(
                [row.closure.P_psia for row in trial_rows],
                dtype=float,
            )
            trial_violation = float(
                np.max(
                    np.maximum(
                        float(minimum_pressure_increment_psi)
                        - np.diff(trial_pressures),
                        0.0,
                    )
                )
            )
            trial_objective = float(np.dot(trial_q, trial_q))
            candidates.append(
                (
                    trial_violation,
                    trial_objective,
                    -float(alpha),
                    trial_q,
                    trial_rows,
                    float(alpha),
                )
            )
        total_uv_solves += int(line_uv_solves)
        if not candidates:
            termination = "all nonlinear line-search candidates failed local UV closure"
            break

        if violation > 1.0e-6:
            improving = [
                item
                for item in candidates
                if item[0] < violation - max(1.0e-6, 1.0e-4 * violation)
            ]
            selected = min(improving or candidates, key=lambda item: item[:3])
            if selected[0] >= violation:
                termination = "pressure-order violation did not improve"
                break
        else:
            feasible = [
                item
                for item in candidates
                if item[0] <= 1.0e-6
                and item[1] < current_objective - 1.0e-10
            ]
            if not feasible:
                termination = "no feasible objective-reducing nonlinear step"
                break
            selected = min(feasible, key=lambda item: (item[1], item[2]))

        q = np.asarray(selected[3], dtype=float)
        rows = tuple(selected[4])
        accepted_alpha = float(selected[5])
        objective, jn, ju = _objective_parts(q, layout)
        new_pressures = np.asarray(
            [row.closure.P_psia for row in rows],
            dtype=float,
        )
        new_violation = float(
            np.max(
                np.maximum(
                    float(minimum_pressure_increment_psi)
                    - np.diff(new_pressures),
                    0.0,
                )
            )
        )
        history.append(
            LeastMovementIteration(
                iteration=int(outer),
                objective=objective,
                component_objective=jn,
                energy_objective=ju,
                maximum_pressure_order_violation_psi=new_violation,
                minimum_pressure_increment_psi=float(np.min(np.diff(new_pressures))),
                step_norm=step_norm,
                accepted_step_fraction=accepted_alpha,
                subproblem_success=bool(solved.success),
                subproblem_iterations=int(getattr(solved, "nit", 0)),
                first_order_optimality_norm=last_optimality,
                active_linear_constraint_count=active_linear,
                uv_solves=int(sensitivity_solves + line_uv_solves),
                termination_reason=str(solved.message),
            )
        )

    n_final, u_final = _absolute_state(
        q=q,
        layout=layout,
        n0=n0,
        u0=u0,
        scales=scales,
    )
    qn, qu = layout.split(q)
    delta_n = n_final - n0
    delta_u = u_final - u0
    component_error = np.sum(delta_n, axis=0)
    energy_error = float(np.sum(delta_u))
    component_totals = np.sum(n0, axis=0)
    component_relative = float(
        np.max(
            np.abs(component_error)
            / np.maximum(np.abs(component_totals), 1.0)
        )
    )
    energy_relative = abs(energy_error) / max(float(np.sum(np.abs(u0))), 1.0)
    pressures = np.asarray([row.closure.P_psia for row in rows], dtype=float)
    initial_pressures = np.asarray(
        [node.initial_pressure_psia for node in nodes],
        dtype=float,
    )
    pressure_violation = float(
        np.max(
            np.maximum(
                float(minimum_pressure_increment_psi) - np.diff(pressures),
                0.0,
            )
        )
    )
    pressure_pass = bool(pressure_violation <= 1.0e-6)
    local_pass = bool(
        all(row.closure.converged for row in rows)
        and max(row.component_relative_residual for row in rows) < 1.0e-8
        and max(row.energy_relative_residual for row in rows) < 1.0e-7
        and max(row.volume_relative_residual for row in rows) < 1.0e-7
        and max(row.equilibrium_beta_residual for row in rows) < 1.0e-6
    )
    active_bounds = int(sum(row.active_bound_count for row in rows))
    objective, jn, ju = _objective_parts(q, layout)
    component_abs = np.sum(np.abs(delta_n), axis=0)
    energy_abs = float(np.sum(np.abs(delta_u)))
    terminal_indices = (0, len(nodes) - 1)
    terminal_component_abs = float(
        np.sum(np.abs(delta_n[list(terminal_indices), :]))
    )
    terminal_energy_abs = float(
        np.sum(np.abs(delta_u[list(terminal_indices)]))
    )
    diagnostics = RedistributionPatternDiagnostics(
        material_move_L1_lbmol=float(0.5 * np.sum(component_abs)),
        material_move_L1_by_component_lbmol=0.5 * component_abs,
        energy_move_L1_BTU=float(0.5 * energy_abs),
        component_donor_lbmol=-np.sum(np.minimum(delta_n, 0.0), axis=0),
        component_receiver_lbmol=np.sum(np.maximum(delta_n, 0.0), axis=0),
        energy_donor_BTU=float(-np.sum(np.minimum(delta_u, 0.0))),
        energy_receiver_BTU=float(np.sum(np.maximum(delta_u, 0.0))),
        component_sign_reversals=np.asarray(
            [
                _sign_reversals(delta_n[:, comp])
                for comp in range(layout.n_components)
            ],
            dtype=int,
        ),
        energy_sign_reversals=_sign_reversals(delta_u),
        maximum_scaled_component_change=float(np.max(np.abs(qn))),
        maximum_scaled_energy_change=float(np.max(np.abs(qu))),
        terminal_component_abs_fraction=(
            terminal_component_abs / max(float(np.sum(component_abs)), 1.0e-300)
        ),
        terminal_energy_abs_fraction=(
            terminal_energy_abs / max(energy_abs, 1.0e-300)
        ),
        maximum_pressure_change_psi=float(
            np.max(np.abs(pressures - initial_pressures))
        ),
        pressure_rms_change_psi=float(
            np.sqrt(np.mean(np.square(pressures - initial_pressures)))
        ),
    )
    constraint_norm = max(
        component_relative,
        energy_relative,
        pressure_violation,
        max(row.component_relative_residual for row in rows),
        max(row.energy_relative_residual for row in rows),
        max(row.volume_relative_residual for row in rows),
        max(row.equilibrium_beta_residual for row in rows),
    )
    if len(history) >= 2:
        objective_stability = abs(
            float(history[-1].objective) - float(history[-2].objective)
        ) / max(abs(float(history[-1].objective)), 1.0)
    elif termination == "ordered stationary point":
        objective_stability = 0.0
    else:
        objective_stability = float("inf")
    converged = bool(
        pressure_pass
        and local_pass
        and component_relative < 1.0e-10
        and energy_relative < 1.0e-8
        and active_bounds == 0
        and last_optimality < 1.0e-6
        and objective_stability < 1.0e-6
    )
    if converged and termination == "maximum outer iterations reached":
        termination = (
            "maximum outer iterations reached; accepted by stationary "
            "physical and objective gates"
        )
    classification = (
        "least_movement_local_manifold_converged"
        if converged
        else "least_movement_local_manifold_unresolved"
    )
    return LeastMovementRedistributionResult(
        nodes=rows,
        iterations=tuple(history),
        normalized_component_change=qn.copy(),
        normalized_energy_change=qu.copy(),
        component_change_lbmol=delta_n.copy(),
        energy_change_BTU=delta_u.copy(),
        objective=float(objective),
        component_objective=float(jn),
        energy_objective=float(ju),
        component_conservation_error_lbmol=component_error.copy(),
        component_conservation_relative_max=float(component_relative),
        energy_conservation_error_BTU=float(energy_error),
        energy_conservation_relative=float(energy_relative),
        minimum_pressure_increment_psi=float(np.min(np.diff(pressures))),
        maximum_pressure_order_violation_psi=float(pressure_violation),
        pressure_ordering_pass=bool(pressure_pass),
        all_local_closures_pass=bool(local_pass),
        active_bound_count=int(active_bounds),
        first_order_optimality_norm=float(last_optimality),
        constraint_violation_norm=float(constraint_norm),
        total_uv_solves=int(total_uv_solves),
        optimizer_termination_reason=str(termination),
        diagnostics=diagnostics,
        converged=bool(converged),
        classification=str(classification),
    )
