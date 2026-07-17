"""
Energy-only conservative redistribution probe for a frozen checkpoint.

This diagnostic keeps every node's component inventory and fixed volume
unchanged. It imposes a nondecreasing top-to-bottom pressure profile, then
redistributes node internal energy while preserving whole-column energy.
Hydraulic equations are deliberately excluded from this first feasibility
layer.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    FrozenCheckpointBridge,
    LocalClosureAudit,
    TerminalClosureAudit,
)
from dynamic_distillation.uv_flash_stage_v1 import _residual_for_state


@dataclass(frozen=True)
class ConservativeNodeTarget:
    node_id: str
    position_1based: int
    total_component_inventory_lbmol: np.ndarray
    total_internal_energy_BTU: float
    fixed_total_volume_ft3: float
    initial_temperature_F: float
    initial_pressure_psia: float
    initial_beta_vapor: float


@dataclass(frozen=True)
class FixedPressureNodeClosure:
    node_id: str
    position_1based: int
    pressure_psia: float
    temperature_F: float
    beta_vapor: float
    implied_internal_energy_BTU: float
    internal_energy_change_BTU: float
    volume_relative_residual: float
    equilibrium_beta_residual: float
    component_relative_residual: float
    converged: bool
    function_evaluations: int
    active_bound_count: int


@dataclass(frozen=True)
class EnergyOnlyRedistributionResult:
    nodes: tuple[FixedPressureNodeClosure, ...]
    initial_pressure_psia: np.ndarray
    isotonic_pressure_psia: np.ndarray
    final_pressure_psia: np.ndarray
    maximum_pressure_change_psi: float
    pressure_rms_change_psi: float
    maximum_temperature_change_F: float
    temperature_rms_change_F: float
    uniform_pressure_shift_psi: float
    minimum_pressure_increment_psi: float
    pressure_ordering_pass: bool
    all_node_closures_converged: bool
    component_conservation_abs_max_lbmol: float
    total_internal_energy_before_BTU: float
    total_internal_energy_after_BTU: float
    total_internal_energy_error_BTU: float
    total_internal_energy_relative_error: float
    energy_moved_BTU: float
    energy_l1_change_BTU: float
    energy_l1_fraction_of_inventory: float
    maximum_node_energy_change_BTU: float
    maximum_node_specific_energy_change_BTU_lbmol: float
    root_bracket_psi: Optional[tuple[float, float]]
    root_converged: bool
    profile_evaluations: int
    pressure_energy_feasibility_pass: bool
    classification: str


def weighted_isotonic_nondecreasing(
    values: Sequence[float],
    *,
    weights: Optional[Sequence[float]] = None,
    minimum_increment: float = 0.0,
) -> np.ndarray:
    """Return the weighted least-squares nondecreasing projection."""
    y = np.asarray(values, dtype=float).reshape((-1,))
    if y.size == 0:
        return y.copy()
    if not np.all(np.isfinite(y)):
        raise ValueError("isotonic values must be finite")
    increment = float(minimum_increment)
    if not np.isfinite(increment) or increment < 0.0:
        raise ValueError("minimum_increment must be finite and nonnegative")

    if weights is None:
        w = np.ones(y.size, dtype=float)
    else:
        w = np.asarray(weights, dtype=float).reshape((y.size,))
    if not np.all(np.isfinite(w)) or np.any(w <= 0.0):
        raise ValueError("isotonic weights must be finite and positive")

    transformed = y - increment * np.arange(y.size, dtype=float)
    blocks: list[dict[str, float | int]] = []
    for idx, (value, weight) in enumerate(zip(transformed, w)):
        blocks.append(
            {
                "start": int(idx),
                "end": int(idx),
                "weight": float(weight),
                "mean": float(value),
            }
        )
        while len(blocks) >= 2 and float(blocks[-2]["mean"]) > float(blocks[-1]["mean"]):
            right = blocks.pop()
            left = blocks.pop()
            total_weight = float(left["weight"]) + float(right["weight"])
            mean = (
                float(left["weight"]) * float(left["mean"])
                + float(right["weight"]) * float(right["mean"])
            ) / total_weight
            blocks.append(
                {
                    "start": int(left["start"]),
                    "end": int(right["end"]),
                    "weight": total_weight,
                    "mean": float(mean),
                }
            )

    projected = np.empty(y.size, dtype=float)
    for block in blocks:
        projected[int(block["start"]) : int(block["end"]) + 1] = float(block["mean"])
    return projected + increment * np.arange(y.size, dtype=float)


def build_energy_only_targets(
    *,
    bridge: FrozenCheckpointBridge,
    local: LocalClosureAudit,
    terminal: TerminalClosureAudit,
) -> tuple[ConservativeNodeTarget, ...]:
    """Build top, interior, and bottom physical nodes in column order."""
    terminal_by_id = {
        str(row.assembly_id): row for row in terminal.assemblies
    }
    if "top_terminal" not in terminal_by_id or "bottom_terminal" not in terminal_by_id:
        raise ValueError("both terminal UV assemblies are required")
    if len(local.stages) != int(bridge.stage_total_components_lbmol.shape[0]):
        raise ValueError("local closure stage count does not match checkpoint bridge")

    targets: list[ConservativeNodeTarget] = []
    top = terminal_by_id["top_terminal"]
    targets.append(
        ConservativeNodeTarget(
            node_id="top_terminal",
            position_1based=1,
            total_component_inventory_lbmol=np.asarray(
                top.target.total_component_inventory_lbmol,
                dtype=float,
            ).copy(),
            total_internal_energy_BTU=float(top.target.total_internal_energy_BTU),
            fixed_total_volume_ft3=float(top.target.fixed_total_volume_ft3),
            initial_temperature_F=float(top.result.T_F),
            initial_pressure_psia=float(top.result.P_psia),
            initial_beta_vapor=float(top.result.beta_vapor),
        )
    )
    for idx, row in enumerate(local.stages):
        targets.append(
            ConservativeNodeTarget(
                node_id=f"tray_{int(row.stage_1based)}",
                position_1based=int(idx + 2),
                total_component_inventory_lbmol=np.asarray(
                    bridge.stage_total_components_lbmol[idx, :],
                    dtype=float,
                ).copy(),
                total_internal_energy_BTU=float(
                    bridge.stage_total_internal_energy_BTU[idx]
                ),
                fixed_total_volume_ft3=float(
                    bridge.spec.fixed_total_volume_ft3[idx]
                ),
                initial_temperature_F=float(row.result.T_F),
                initial_pressure_psia=float(row.result.P_psia),
                initial_beta_vapor=float(row.result.beta_vapor),
            )
        )
    bottom = terminal_by_id["bottom_terminal"]
    targets.append(
        ConservativeNodeTarget(
            node_id="bottom_terminal",
            position_1based=len(targets) + 1,
            total_component_inventory_lbmol=np.asarray(
                bottom.target.total_component_inventory_lbmol,
                dtype=float,
            ).copy(),
            total_internal_energy_BTU=float(bottom.target.total_internal_energy_BTU),
            fixed_total_volume_ft3=float(bottom.target.fixed_total_volume_ft3),
            initial_temperature_F=float(bottom.result.T_F),
            initial_pressure_psia=float(bottom.result.P_psia),
            initial_beta_vapor=float(bottom.result.beta_vapor),
        )
    )
    return tuple(targets)


def solve_fixed_pressure_node(
    *,
    provider: Any,
    target: ConservativeNodeTarget,
    pressure_psia: float,
) -> FixedPressureNodeClosure:
    """Close volume and phase equilibrium at fixed N, V, and pressure."""
    components = np.asarray(
        target.total_component_inventory_lbmol,
        dtype=float,
    ).reshape((-1,))
    total_moles = float(np.sum(components))
    if total_moles <= 1.0e-12:
        raise ValueError(f"{target.node_id} has no physical component inventory")
    if float(target.fixed_total_volume_ft3) <= 0.0:
        raise ValueError(f"{target.node_id} has no physical fixed volume")
    pressure = float(pressure_psia)
    if not np.isfinite(pressure) or pressure <= 1.0 or pressure >= 1000.0:
        raise ValueError("fixed pressure must lie strictly between 1 and 1000 psia")

    z = components / total_moles
    u_reference = float(target.total_internal_energy_BTU) / total_moles
    v_target = float(target.fixed_total_volume_ft3) / total_moles
    v_scale = max(abs(v_target), 1.0e-9)
    lower = np.asarray([-200.0, 1.0e-8], dtype=float)
    upper = np.asarray([1000.0, 1.0 - 1.0e-8], dtype=float)

    def raw_state(x_trial: np.ndarray):
        x_full = np.asarray([x_trial[0], pressure, x_trial[1]], dtype=float)
        return _residual_for_state(
            provider,
            z_overall=z,
            u_target_BTU_lbmol=u_reference,
            v_target_ft3_lbmol=v_target,
            x_vec=x_full,
            beta_mode="free",
            beta_fixed=None,
        )

    def objective(x_trial: np.ndarray) -> np.ndarray:
        raw, _state, _beta = raw_state(x_trial)
        return np.asarray([raw[1] / v_scale, raw[2]], dtype=float)

    beta0 = float(np.clip(target.initial_beta_vapor, 1.0e-6, 1.0 - 1.0e-6))
    starts = (
        np.asarray([target.initial_temperature_F, beta0], dtype=float),
        np.asarray([target.initial_temperature_F - 20.0, beta0], dtype=float),
        np.asarray([target.initial_temperature_F + 20.0, beta0], dtype=float),
        np.asarray([target.initial_temperature_F, 0.5], dtype=float),
    )
    best = None
    best_norm = float("inf")
    total_nfev = 0
    for start in starts:
        clipped = np.minimum(np.maximum(start, lower + 1.0e-9), upper - 1.0e-9)
        solved = least_squares(
            objective,
            clipped,
            bounds=(lower, upper),
            method="trf",
            x_scale="jac",
            ftol=1.0e-11,
            xtol=1.0e-11,
            gtol=1.0e-11,
            max_nfev=120,
        )
        total_nfev += int(solved.nfev)
        norm = float(np.linalg.norm(objective(solved.x), ord=np.inf))
        if np.isfinite(norm) and norm < best_norm:
            best = solved
            best_norm = norm
        if best_norm < 1.0e-8:
            break
    if best is None:
        raise RuntimeError(f"{target.node_id} fixed-pressure closure has no finite candidate")

    raw, state, beta = raw_state(np.asarray(best.x, dtype=float))
    implied_specific_u = u_reference + float(raw[0])
    implied_u = total_moles * implied_specific_u
    reconstructed = (
        (1.0 - float(beta)) * np.asarray(state.x, dtype=float)
        + float(beta) * np.asarray(state.y, dtype=float)
    )
    component_relative = float(
        np.max(np.abs(reconstructed - z) / np.maximum(np.abs(z), 1.0e-12))
    )
    bound_margin = np.minimum(np.asarray(best.x) - lower, upper - np.asarray(best.x))
    active_bounds = int(
        np.sum(
            bound_margin
            <= 1.0e-7 * np.maximum(np.abs(np.asarray(best.x, dtype=float)), 1.0)
        )
    )
    volume_relative = abs(float(raw[1])) / v_scale
    beta_residual = abs(float(raw[2]))
    converged = bool(
        best.success
        and volume_relative < 1.0e-7
        and beta_residual < 1.0e-6
        and component_relative < 1.0e-7
        and active_bounds == 0
    )
    return FixedPressureNodeClosure(
        node_id=str(target.node_id),
        position_1based=int(target.position_1based),
        pressure_psia=pressure,
        temperature_F=float(best.x[0]),
        beta_vapor=float(beta),
        implied_internal_energy_BTU=float(implied_u),
        internal_energy_change_BTU=float(
            implied_u - float(target.total_internal_energy_BTU)
        ),
        volume_relative_residual=float(volume_relative),
        equilibrium_beta_residual=float(beta_residual),
        component_relative_residual=float(component_relative),
        converged=bool(converged),
        function_evaluations=int(total_nfev),
        active_bound_count=int(active_bounds),
    )


def solve_energy_only_pressure_ordering(
    *,
    provider: Any,
    targets: Sequence[ConservativeNodeTarget],
    minimum_pressure_increment_psi: float = 0.01,
) -> EnergyOnlyRedistributionResult:
    """Find an ordered pressure profile with exact global energy conservation."""
    node_targets = tuple(targets)
    if len(node_targets) < 2:
        raise ValueError("at least two physical nodes are required")
    initial_pressure = np.asarray(
        [node.initial_pressure_psia for node in node_targets],
        dtype=float,
    )
    inventories = np.asarray(
        [np.sum(node.total_component_inventory_lbmol) for node in node_targets],
        dtype=float,
    )
    if np.any(inventories <= 0.0):
        raise ValueError("all conservative nodes must have positive inventory")
    isotonic_pressure = weighted_isotonic_nondecreasing(
        initial_pressure,
        weights=inventories,
        minimum_increment=float(minimum_pressure_increment_psi),
    )
    total_u_before = float(
        sum(float(node.total_internal_energy_BTU) for node in node_targets)
    )
    component_before = np.sum(
        np.vstack(
            [
                np.asarray(node.total_component_inventory_lbmol, dtype=float)
                for node in node_targets
            ]
        ),
        axis=0,
    )

    cache: Dict[float, tuple[float, tuple[FixedPressureNodeClosure, ...]]] = {}
    failed_cache: set[float] = set()

    def evaluate_shift(
        shift: float,
    ) -> tuple[float, tuple[FixedPressureNodeClosure, ...]]:
        key = float(np.round(float(shift), 12))
        if key in cache:
            return cache[key]
        if key in failed_cache:
            raise RuntimeError("pressure profile previously failed node closure")
        final_pressure = isotonic_pressure + float(shift)
        if float(np.min(final_pressure)) <= 1.0 or float(np.max(final_pressure)) >= 1000.0:
            raise ValueError("shifted pressure profile lies outside solver bounds")
        nearest_rows = None
        if cache:
            nearest_key = min(cache, key=lambda cached_shift: abs(cached_shift - key))
            nearest_rows = cache[nearest_key][1]
        rows_list: list[FixedPressureNodeClosure] = []
        for idx, (node, pressure) in enumerate(zip(node_targets, final_pressure)):
            seeded_node = node
            if nearest_rows is not None:
                seeded_node = replace(
                    node,
                    initial_temperature_F=float(nearest_rows[idx].temperature_F),
                    initial_beta_vapor=float(nearest_rows[idx].beta_vapor),
                )
            rows_list.append(
                solve_fixed_pressure_node(
                    provider=provider,
                    target=seeded_node,
                    pressure_psia=float(pressure),
                )
            )
        rows = tuple(rows_list)
        failed = [row.node_id for row in rows if not row.converged]
        if failed:
            failed_cache.add(key)
            raise RuntimeError(
                "fixed-pressure node closure failed for: "
                + ", ".join(failed)
            )
        energy_error = (
            float(sum(row.implied_internal_energy_BTU for row in rows))
            - total_u_before
        )
        cache[key] = (float(energy_error), rows)
        return cache[key]

    minimum_shift = float(1.000001 - np.min(isotonic_pressure))
    maximum_shift = float(999.999999 - np.max(isotonic_pressure))
    magnitudes = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 320.0)
    evaluated: Dict[float, float] = {}
    best_rows: tuple[FixedPressureNodeClosure, ...] = ()
    best_shift = 0.0
    best_abs_error = float("inf")
    bracket: Optional[tuple[float, float]] = None

    for magnitude in magnitudes:
        candidates = (0.0,) if magnitude == 0.0 else (-magnitude, magnitude)
        for shift in candidates:
            if shift <= minimum_shift or shift >= maximum_shift or shift in evaluated:
                continue
            try:
                energy_error, rows = evaluate_shift(float(shift))
            except (RuntimeError, ValueError):
                continue
            evaluated[float(shift)] = float(energy_error)
            if abs(float(energy_error)) < best_abs_error:
                best_abs_error = abs(float(energy_error))
                best_shift = float(shift)
                best_rows = rows
        ordered = sorted(evaluated.items())
        for (left_shift, left_error), (right_shift, right_error) in zip(
            ordered[:-1],
            ordered[1:],
        ):
            if left_error == 0.0:
                bracket = (float(left_shift), float(left_shift))
                break
            if right_error == 0.0 or left_error * right_error < 0.0:
                bracket = (float(left_shift), float(right_shift))
                break
        if bracket is not None:
            break

    root_converged = False
    if bracket is not None:
        if bracket[0] == bracket[1]:
            best_shift = float(bracket[0])
            exact_error, best_rows = evaluate_shift(best_shift)
            root_converged = bool(
                abs(exact_error) / max(abs(total_u_before), 1.0) < 1.0e-8
            )
        else:
            left, right = map(float, bracket)
            left_error = float(evaluated[left])
            right_error = float(evaluated[right])
            energy_tolerance = 1.0e-8 * max(abs(total_u_before), 1.0)
            for _ in range(20):
                if abs(left_error) <= energy_tolerance:
                    best_shift = left
                    _error, best_rows = evaluate_shift(left)
                    root_converged = True
                    break
                if abs(right_error) <= energy_tolerance:
                    best_shift = right
                    _error, best_rows = evaluate_shift(right)
                    root_converged = True
                    break

                secant = (
                    left * right_error - right * left_error
                ) / (right_error - left_error)
                span = right - left
                secant = float(
                    np.clip(secant, left + 0.05 * span, right - 0.05 * span)
                )
                trial_candidates = (
                    secant,
                    0.5 * (left + right),
                    0.75 * left + 0.25 * right,
                    0.25 * left + 0.75 * right,
                )
                trial = None
                trial_error = None
                trial_rows = None
                for candidate in trial_candidates:
                    try:
                        candidate_error, candidate_rows = evaluate_shift(
                            float(candidate)
                        )
                    except (RuntimeError, ValueError):
                        continue
                    trial = float(candidate)
                    trial_error = float(candidate_error)
                    trial_rows = candidate_rows
                    break
                if trial is None or trial_error is None or trial_rows is None:
                    break

                if abs(trial_error) < best_abs_error:
                    best_abs_error = abs(trial_error)
                    best_shift = trial
                    best_rows = trial_rows
                if abs(trial_error) <= energy_tolerance:
                    best_shift = trial
                    best_rows = trial_rows
                    root_converged = True
                    break
                if left_error * trial_error <= 0.0:
                    right = trial
                    right_error = trial_error
                else:
                    left = trial
                    left_error = trial_error
                if abs(right - left) <= 1.0e-8:
                    root_converged = bool(
                        best_abs_error
                        / max(abs(total_u_before), 1.0)
                        < 1.0e-8
                    )
                    break

    if not best_rows:
        raise RuntimeError("no pressure profile produced valid node closures")

    final_pressure = isotonic_pressure + best_shift
    pressure_changes = final_pressure - initial_pressure
    total_u_after = float(
        sum(row.implied_internal_energy_BTU for row in best_rows)
    )
    energy_error = total_u_after - total_u_before
    energy_scale = max(abs(total_u_before), 1.0)
    energy_relative = abs(energy_error) / energy_scale
    changes = np.asarray(
        [row.internal_energy_change_BTU for row in best_rows],
        dtype=float,
    )
    initial_u = np.asarray(
        [node.total_internal_energy_BTU for node in node_targets],
        dtype=float,
    )
    specific_changes = np.abs(changes) / inventories
    temperature_changes = np.asarray(
        [
            row.temperature_F - node.initial_temperature_F
            for row, node in zip(best_rows, node_targets)
        ],
        dtype=float,
    )
    component_after = component_before.copy()
    component_error = float(np.max(np.abs(component_after - component_before)))
    pressure_diffs = np.diff(final_pressure)
    ordering_pass = bool(
        np.all(
            pressure_diffs
            >= float(minimum_pressure_increment_psi) - 1.0e-8
        )
    )
    all_nodes_converged = all(row.converged for row in best_rows)
    feasibility_pass = bool(
        root_converged
        and all_nodes_converged
        and ordering_pass
        and component_error <= 1.0e-10
        and energy_relative < 1.0e-8
    )
    if feasibility_pass:
        classification = "energy_only_pressure_ordering_feasible"
    elif not root_converged:
        classification = "energy_conservation_root_unbracketed"
    elif not all_nodes_converged:
        classification = "fixed_pressure_node_closure_failed"
    else:
        classification = "energy_only_pressure_ordering_infeasible"

    return EnergyOnlyRedistributionResult(
        nodes=best_rows,
        initial_pressure_psia=initial_pressure,
        isotonic_pressure_psia=isotonic_pressure,
        final_pressure_psia=np.asarray(final_pressure, dtype=float),
        maximum_pressure_change_psi=float(
            np.max(np.abs(pressure_changes))
        ),
        pressure_rms_change_psi=float(
            np.sqrt(np.mean(np.square(pressure_changes)))
        ),
        maximum_temperature_change_F=float(
            np.max(np.abs(temperature_changes))
        ),
        temperature_rms_change_F=float(
            np.sqrt(np.mean(np.square(temperature_changes)))
        ),
        uniform_pressure_shift_psi=float(best_shift),
        minimum_pressure_increment_psi=float(minimum_pressure_increment_psi),
        pressure_ordering_pass=bool(ordering_pass),
        all_node_closures_converged=bool(all_nodes_converged),
        component_conservation_abs_max_lbmol=float(component_error),
        total_internal_energy_before_BTU=float(total_u_before),
        total_internal_energy_after_BTU=float(total_u_after),
        total_internal_energy_error_BTU=float(energy_error),
        total_internal_energy_relative_error=float(energy_relative),
        energy_moved_BTU=float(0.5 * np.sum(np.abs(changes))),
        energy_l1_change_BTU=float(np.sum(np.abs(changes))),
        energy_l1_fraction_of_inventory=float(
            np.sum(np.abs(changes)) / max(np.sum(np.abs(initial_u)), 1.0)
        ),
        maximum_node_energy_change_BTU=float(np.max(np.abs(changes))),
        maximum_node_specific_energy_change_BTU_lbmol=float(
            np.max(specific_changes)
        ),
        root_bracket_psi=bracket,
        root_converged=bool(root_converged),
        profile_evaluations=int(len(cache)),
        pressure_energy_feasibility_pass=bool(feasibility_pass),
        classification=str(classification),
    )
