"""
Read-only checkpoint bridge for frozen conserved-state closure diagnostics.

The bridge converts the runtime tray state into conserved component totals and
internal energy, then evaluates the existing UV/flow sandbox without changing
the production RHS.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.dynamic_run_scaffold_v1 import (
    load_native_checkpoint_initial_state,
    read_native_checkpoint,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.uv_flash_sandbox_simultaneous_v1 import (
    SimultaneousMini8Layout,
    SimultaneousSolveResult,
    default_algebraic_seed,
    solve_simultaneous_algebraic_state,
)
from dynamic_distillation.uv_flash_sandbox_v1 import (
    UvMini8PrototypeSpec,
    _liquid_internal_energy_from_tp,
    _pack_state,
    _unpack_state,
    build_mini8_uv_prototype_spec,
)
from dynamic_distillation.uv_flash_stage_v1 import (
    BTU_PER_PSI_FT3,
    UvFlashStageGuess,
    UvFlashStageResult,
    _residual_for_state,
    solve_uv_flash_stage,
)


@dataclass(frozen=True)
class FrozenCheckpointBridge:
    excel_path: str
    checkpoint_path: str
    checkpoint_run_id: str
    checkpoint_time_s: float
    spec: UvMini8PrototypeSpec
    y_conserved: np.ndarray
    z_seed: np.ndarray
    stage_total_components_lbmol: np.ndarray
    stage_total_internal_energy_BTU: np.ndarray
    stage_pressure_guess_psia: np.ndarray
    stage_temperature_guess_F: np.ndarray
    stage_beta_guess: np.ndarray
    terminal_mapping_complete: bool
    mapping_notes: tuple[str, ...]


@dataclass(frozen=True)
class LocalClosureStage:
    stage_1based: int
    result: UvFlashStageResult
    component_relative_residual: float
    energy_relative_residual: float
    volume_relative_residual: float
    equilibrium_beta_residual: float
    liquid_moles_lbmol: float
    vapor_moles_lbmol: float


@dataclass(frozen=True)
class LocalClosureAudit:
    stages: tuple[LocalClosureStage, ...]
    converged: bool
    component_relative_max: float
    energy_relative_max: float
    volume_relative_max: float
    equilibrium_beta_max: float
    negative_phase_count: int
    projection_count: int
    attempted_projection_count: int
    fugacity_residual_available: bool
    strict_gate_pass: bool


@dataclass(frozen=True)
class HydraulicClosureAudit:
    nominal: SimultaneousSolveResult
    perturbations: tuple[SimultaneousSolveResult, ...]
    liquid_flow_scaled_residual: float
    vapor_flow_scaled_residual: float
    pressure_drop_scaled_residual: float
    local_vs_global_pressure_max_psi: float
    active_liquid_limiter_count: int
    active_vapor_limiter_count: int
    projection_count: int
    attempted_projection_count: int
    perturbations_run: bool
    perturbation_pressure_spread_max_psi: float
    perturbation_flow_relative_spread_max: float
    strict_gate_pass: bool


def checkpoint_phase_state_to_conserved_totals(
    *,
    unpacked: Dict[str, np.ndarray],
    active_stage0: Sequence[int],
    pressure_psia: Sequence[float],
    fixed_total_volume_ft3: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Map phase inventories and enthalpy inventories to total N and total U."""
    active = np.asarray(active_stage0, dtype=int).reshape((-1,))
    tray_l = np.asarray(unpacked["tray_L"], dtype=float)
    tray_v = np.asarray(unpacked["tray_V"], dtype=float)
    tray_el = np.asarray(unpacked["tray_EL_BTU"], dtype=float).reshape((-1,))
    tray_ev = np.asarray(unpacked["tray_EV_BTU"], dtype=float).reshape((-1,))
    pressure = np.asarray(pressure_psia, dtype=float).reshape((-1,))
    volume = np.asarray(fixed_total_volume_ft3, dtype=float).reshape((active.size,))

    totals = tray_l[active, :] + tray_v[active, :]
    enthalpy_inventory = tray_el[active] + tray_ev[active]
    internal_energy = enthalpy_inventory - pressure[active] * volume * BTU_PER_PSI_FT3
    return np.asarray(totals, dtype=float), np.asarray(internal_energy, dtype=float)


def _scalar_array(arrays: Dict[str, np.ndarray], key: str, default: float) -> float:
    if key not in arrays:
        return float(default)
    arr = np.asarray(arrays[key], dtype=float).reshape((-1,))
    if arr.size <= 0 or not np.isfinite(arr[-1]):
        return float(default)
    return float(arr[-1])


def _array_or_default(
    arrays: Dict[str, np.ndarray],
    key: str,
    *,
    shape: tuple[int, ...],
    default: np.ndarray,
) -> np.ndarray:
    if key not in arrays:
        return np.asarray(default, dtype=float).reshape(shape).copy()
    arr = np.asarray(arrays[key], dtype=float)
    if arr.size != int(np.prod(shape)) or not np.all(np.isfinite(arr)):
        return np.asarray(default, dtype=float).reshape(shape).copy()
    return arr.reshape(shape).copy()


def _layout_from_checkpoint(metadata: Dict[str, Any], *, n_stages: int, n_components: int) -> StateVectorLayout:
    doc = metadata.get("layout") if isinstance(metadata.get("layout"), dict) else {}
    return StateVectorLayout(
        n_stages=int(n_stages),
        n_components=int(n_components),
        include_top=bool(doc.get("include_top", True)),
        include_bottom=bool(doc.get("include_bottom", True)),
        include_vapor=bool(doc.get("include_vapor", True)),
        include_temperature=bool(doc.get("include_temperature", True)),
        include_energy=bool(doc.get("include_energy", True)),
    )


def build_frozen_checkpoint_bridge(
    *,
    excel_path: str,
    checkpoint_path: str,
    provider: Any,
) -> FrozenCheckpointBridge:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)
    checkpoint = read_native_checkpoint(checkpoint_path)
    metadata = dict(checkpoint.get("metadata") or {})
    arrays = dict(checkpoint.get("arrays") or {})
    layout = _layout_from_checkpoint(
        metadata,
        n_stages=int(col.n_stages),
        n_components=int(col.n_components),
    )
    if not (layout.include_vapor and layout.include_temperature and layout.include_energy):
        raise ValueError("Frozen UV bridge requires checkpoint vapor, temperature, and energy states.")

    state, _info, memory = load_native_checkpoint_initial_state(
        path=checkpoint_path,
        layout=layout,
        col=col,
    )
    unpacked = layout.unpack(state)
    spec = build_mini8_uv_prototype_spec(excel_path=excel_path, provider=provider)

    pressure_full = _array_or_default(
        arrays,
        "diag__P_psia_hyd",
        shape=(int(col.n_stages),),
        default=np.asarray(memory.get("last_P_hyd", col.P_psia), dtype=float),
    )
    temperature_full = np.asarray(unpacked["tray_T_f"], dtype=float).reshape((int(col.n_stages),))
    n_total, u_total = checkpoint_phase_state_to_conserved_totals(
        unpacked=unpacked,
        active_stage0=spec.active_stage0,
        pressure_psia=pressure_full,
        fixed_total_volume_ft3=spec.fixed_total_volume_ft3,
    )

    tray_l = np.asarray(unpacked["tray_L"], dtype=float)
    tray_v = np.asarray(unpacked["tray_V"], dtype=float)
    active = np.asarray(spec.active_stage0, dtype=int)
    phase_total = np.sum(tray_l[active, :] + tray_v[active, :], axis=1)
    beta = np.sum(tray_v[active, :], axis=1) / np.maximum(phase_total, 1.0e-12)
    beta = np.clip(beta, 1.0e-8, 1.0 - 1.0e-8)

    liquid = _array_or_default(
        arrays,
        "diag__L_out_lbmolph",
        shape=(int(col.n_stages),),
        default=np.asarray(spec.L_lbmolps, dtype=float) * 3600.0,
    ) / 3600.0
    vapor = _array_or_default(
        arrays,
        "diag__V_out_lbmolph",
        shape=(int(col.n_stages),),
        default=np.asarray(spec.V_lbmolps, dtype=float) * 3600.0,
    ) / 3600.0

    top_liquid = np.asarray(unpacked["top_L"], dtype=float).copy()
    bottom_liquid = np.asarray(unpacked["bottom_L"], dtype=float).copy()
    top_t = _scalar_array(
        arrays,
        "diag__T_top_drum_pressure_used_F",
        float(temperature_full[0]),
    )
    bottom_t = float(np.asarray(unpacked.get("bottom_T_f", [temperature_full[-1]]), dtype=float).reshape((-1,))[0])
    top_p = _scalar_array(arrays, "diag__P_top_drum_psia", float(pressure_full[0]))
    bottom_p = float(pressure_full[-1])

    top_u_molar, _ = _liquid_internal_energy_from_tp(
        provider,
        T_F=top_t,
        P_psia=top_p,
        x_liq=top_liquid / max(float(np.sum(top_liquid)), 1.0e-12),
    )
    bottom_u_molar, _ = _liquid_internal_energy_from_tp(
        provider,
        T_F=bottom_t,
        P_psia=bottom_p,
        x_liq=bottom_liquid / max(float(np.sum(bottom_liquid)), 1.0e-12),
    )
    top_u = float(np.sum(top_liquid)) * float(top_u_molar)
    bottom_u = float(np.sum(bottom_liquid)) * float(bottom_u_molar)

    q_stage = np.asarray(spec.q_stage_BTUps, dtype=float).copy()
    q_stage[-1] = _scalar_array(
        arrays,
        "diag__Q_reb_used_BTUph",
        float(q_stage[-1]) * 3600.0,
    ) / 3600.0
    spec = replace(
        spec,
        initial_total_component_holdup_lbmol=n_total.copy(),
        initial_total_internal_energy_BTU=u_total.copy(),
        initial_guesses=[
            UvFlashStageGuess(
                T_F=float(temperature_full[stage0]),
                P_psia=float(pressure_full[stage0]),
                beta_vapor=float(beta[idx]),
            )
            for idx, stage0 in enumerate(active)
        ],
        L_lbmolps=liquid.copy(),
        V_lbmolps=vapor.copy(),
        condenser_duty_BTUps=_scalar_array(
            arrays,
            "diag__Q_cond_used_BTUph",
            float(spec.condenser_duty_BTUps) * 3600.0,
        )
        / 3600.0,
        q_stage_BTUps=q_stage,
        top_node_reference=replace(spec.top_node_reference, P_psia=float(top_p)),
        bottom_node_reference=replace(spec.bottom_node_reference, P_psia=float(bottom_p)),
    )

    y_conserved = _pack_state(
        n_total,
        u_total,
        top_liquid,
        bottom_liquid,
        top_u,
        bottom_u,
    )
    algebraic_layout = SimultaneousMini8Layout(
        n_active=int(active.size),
        n_total_stages=int(col.n_stages),
    )
    z_default = default_algebraic_seed(spec=spec)
    _dt, _dp, _db, _dtt, _dbt, _dl, _dv = algebraic_layout.split(z_default)
    z_seed = algebraic_layout.join(
        temperature_full[active],
        pressure_full[active],
        beta,
        top_t,
        bottom_t,
        liquid,
        vapor,
    )

    top_vapor = float(np.sum(np.asarray(unpacked.get("top_V", 0.0), dtype=float)))
    bottom_vapor = float(np.sum(np.asarray(unpacked.get("bottom_V", 0.0), dtype=float)))
    terminal_stage_inventory = float(
        np.sum(tray_l[[0, int(col.n_stages) - 1], :])
        + np.sum(tray_v[[0, int(col.n_stages) - 1], :])
    )
    notes = (
        "Interior tray totals and U are frozen; checkpoint liquid/vapor splits are guesses only.",
        "Top and bottom vessel nodes use checkpoint liquid inventory and reconstructed liquid internal energy.",
        "The current sandbox represents terminal equipment algebraically and does not conserve virtual terminal-stage inventory.",
        f"Excluded terminal-stage inventory is {terminal_stage_inventory:.9g} lbmol; "
        f"top-vessel vapor={top_vapor:.9g} lbmol and bottom-vessel vapor={bottom_vapor:.9g} lbmol.",
    )
    return FrozenCheckpointBridge(
        excel_path=str(Path(excel_path).resolve()),
        checkpoint_path=str(Path(checkpoint_path).resolve()),
        checkpoint_run_id=str(metadata.get("run_id", "")),
        checkpoint_time_s=float(metadata.get("final_time_s", np.nan)),
        spec=spec,
        y_conserved=y_conserved,
        z_seed=np.asarray(z_seed, dtype=float),
        stage_total_components_lbmol=n_total,
        stage_total_internal_energy_BTU=u_total,
        stage_pressure_guess_psia=pressure_full[active],
        stage_temperature_guess_F=temperature_full[active],
        stage_beta_guess=beta,
        terminal_mapping_complete=False,
        mapping_notes=notes,
    )


def run_local_closure_audit(
    *,
    bridge: FrozenCheckpointBridge,
    provider: Any,
) -> LocalClosureAudit:
    spec = bridge.spec
    n_total, u_total, _top, _bottom, _top_u, _bottom_u = _unpack_state(
        bridge.y_conserved,
        n_active=int(spec.active_stage0.size),
        n_components=len(spec.component_names),
    )
    rows: List[LocalClosureStage] = []
    for idx, stage1 in enumerate(spec.active_stage1):
        n_stage = np.asarray(n_total[idx, :], dtype=float)
        total = float(np.sum(n_stage))
        z = n_stage / max(total, 1.0e-12)
        u_target = float(u_total[idx]) / max(total, 1.0e-12)
        v_target = float(spec.fixed_total_volume_ft3[idx]) / max(total, 1.0e-12)
        result = solve_uv_flash_stage(
            provider,
            z_overall=z,
            u_target_BTU_lbmol=u_target,
            v_target_ft3_lbmol=v_target,
            guess=spec.initial_guesses[idx],
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
                guess=spec.initial_guesses[idx],
            )
        beta = float(result.beta_vapor)
        reconstructed = (1.0 - beta) * np.asarray(result.x) + beta * np.asarray(result.y)
        comp_rel = float(
            np.max(np.abs(reconstructed - z) / np.maximum(np.abs(z), 1.0e-12))
        )
        rows.append(
            LocalClosureStage(
                stage_1based=int(stage1),
                result=result,
                component_relative_residual=comp_rel,
                energy_relative_residual=abs(float(result.residual_u_BTU_lbmol))
                / max(abs(u_target), 1.0),
                volume_relative_residual=abs(float(result.residual_v_ft3_lbmol))
                / max(abs(v_target), 1.0e-12),
                equilibrium_beta_residual=abs(float(result.residual_beta)),
                liquid_moles_lbmol=max(1.0 - beta, 0.0) * total,
                vapor_moles_lbmol=max(beta, 0.0) * total,
            )
        )

    comp_max = max((r.component_relative_residual for r in rows), default=np.inf)
    energy_max = max((r.energy_relative_residual for r in rows), default=np.inf)
    volume_max = max((r.volume_relative_residual for r in rows), default=np.inf)
    eq_max = max((r.equilibrium_beta_residual for r in rows), default=np.inf)
    negative_count = sum(
        int(r.liquid_moles_lbmol < 0.0) + int(r.vapor_moles_lbmol < 0.0)
        for r in rows
    )
    projection_count = sum(int(r.result.accepted_projection_count) for r in rows)
    attempted_projection_count = sum(int(r.result.projection_count) for r in rows)
    converged = bool(rows) and all(bool(r.result.converged) for r in rows)
    # The provider protocol does not expose phase fugacity coefficients, so the
    # strict reviewer gate remains unverified even if TP-flash closure succeeds.
    fugacity_available = False
    strict_pass = bool(
        converged
        and comp_max < 1.0e-8
        and energy_max < 1.0e-7
        and volume_max < 1.0e-7
        and eq_max < 1.0e-6
        and negative_count == 0
        and projection_count == 0
        and fugacity_available
    )
    return LocalClosureAudit(
        stages=tuple(rows),
        converged=converged,
        component_relative_max=float(comp_max),
        energy_relative_max=float(energy_max),
        volume_relative_max=float(volume_max),
        equilibrium_beta_max=float(eq_max),
        negative_phase_count=int(negative_count),
        projection_count=int(projection_count),
        attempted_projection_count=int(attempted_projection_count),
        fugacity_residual_available=bool(fugacity_available),
        strict_gate_pass=bool(strict_pass),
    )


def _solve_scaled_local_uv(
    *,
    provider: Any,
    z: np.ndarray,
    u_target: float,
    v_target: float,
    guess: UvFlashStageGuess,
) -> UvFlashStageResult:
    """Retry a failed local Newton solve with explicitly scaled bounded residuals."""
    u_scale = max(abs(float(u_target)), 1.0)
    v_scale = max(abs(float(v_target)), 1.0e-9)
    lower = np.asarray([-200.0, 1.0, 1.0e-8], dtype=float)
    upper = np.asarray([1000.0, 1000.0, 1.0 - 1.0e-8], dtype=float)

    def objective(x_vec: np.ndarray) -> np.ndarray:
        raw, _state, _beta = _residual_for_state(
            provider,
            z_overall=np.asarray(z, dtype=float),
            u_target_BTU_lbmol=float(u_target),
            v_target_ft3_lbmol=float(v_target),
            x_vec=np.asarray(x_vec, dtype=float),
            beta_mode="free",
            beta_fixed=None,
        )
        return np.asarray(
            [raw[0] / u_scale, raw[1] / v_scale, raw[2]],
            dtype=float,
        )

    starts = [
        np.asarray([guess.T_F, guess.P_psia, guess.beta_vapor], dtype=float),
        np.asarray([guess.T_F, 0.9 * guess.P_psia, max(0.5 * guess.beta_vapor, 1.0e-4)], dtype=float),
        np.asarray([guess.T_F, 1.1 * guess.P_psia, min(1.5 * guess.beta_vapor, 0.95)], dtype=float),
        np.asarray([guess.T_F, guess.P_psia, 0.5], dtype=float),
    ]
    best = None
    best_norm = float("inf")
    total_nfev = 0
    for start in starts:
        start = np.minimum(np.maximum(start, lower + 1.0e-9), upper - 1.0e-9)
        solved = least_squares(
            objective,
            start,
            bounds=(lower, upper),
            method="trf",
            x_scale="jac",
            ftol=1.0e-12,
            xtol=1.0e-12,
            gtol=1.0e-12,
            max_nfev=200,
        )
        total_nfev += int(solved.nfev)
        norm = float(np.linalg.norm(objective(solved.x), ord=np.inf))
        if np.isfinite(norm) and norm < best_norm:
            best = solved
            best_norm = norm
    if best is None:
        raise RuntimeError("Scaled local UV retry did not produce a finite candidate.")

    raw, state, beta = _residual_for_state(
        provider,
        z_overall=np.asarray(z, dtype=float),
        u_target_BTU_lbmol=float(u_target),
        v_target_ft3_lbmol=float(v_target),
        x_vec=np.asarray(best.x, dtype=float),
        beta_mode="free",
        beta_fixed=None,
    )
    bound_margin = np.minimum(np.asarray(best.x) - lower, upper - np.asarray(best.x))
    active_bounds = int(np.sum(bound_margin <= 1.0e-7 * np.maximum(np.abs(best.x), 1.0)))
    converged = bool(
        abs(float(raw[0])) / u_scale < 1.0e-7
        and abs(float(raw[1])) / v_scale < 1.0e-7
        and abs(float(raw[2])) < 1.0e-6
        and active_bounds == 0
    )
    return UvFlashStageResult(
        T_F=float(best.x[0]),
        P_psia=float(best.x[1]),
        beta_vapor=float(beta),
        x=np.asarray(state.x, dtype=float).copy(),
        y=np.asarray(state.y, dtype=float).copy(),
        K=np.asarray(state.K, dtype=float).copy(),
        HL_BTU_lbmol=float(state.HL_BTU_lbmol),
        HV_BTU_lbmol=float(state.HV_BTU_lbmol),
        uL_BTU_lbmol=float(state.uL_BTU_lbmol),
        uV_BTU_lbmol=float(state.uV_BTU_lbmol),
        vL_ft3_lbmol=float(state.vL_ft3_lbmol),
        vV_ft3_lbmol=float(state.vV_ft3_lbmol),
        Z_vapor=float(state.Z_vapor),
        residual_u_BTU_lbmol=float(raw[0]),
        residual_v_ft3_lbmol=float(raw[1]),
        residual_beta=float(raw[2]),
        converged=bool(converged),
        iterations=int(total_nfev),
        projection_count=int(active_bounds),
        accepted_projection_count=int(active_bounds),
    )


def _diag_scalar(result: SimultaneousSolveResult, key: str) -> float:
    arr = np.asarray(result.evaluation.diag.get(key, [np.nan]), dtype=float).reshape((-1,))
    return float(arr[0]) if arr.size else float("nan")


def _active_limiter_count(values: Iterable[float]) -> int:
    arr = np.asarray(list(values), dtype=float).reshape((-1,))
    return int(np.sum(np.isfinite(arr) & (arr > 0.5)))


def _perturb_seed(bridge: FrozenCheckpointBridge, factor: float) -> np.ndarray:
    spec = bridge.spec
    layout = SimultaneousMini8Layout(
        n_active=int(spec.active_stage0.size),
        n_total_stages=int(spec.n_total_stages),
    )
    t, p, beta, top_t, bottom_t, liquid, vapor = layout.split(bridge.z_seed)
    return layout.join(t, factor * p, beta, top_t, bottom_t, factor * liquid, factor * vapor)


def run_hydraulic_closure_audit(
    *,
    bridge: FrozenCheckpointBridge,
    provider: Any,
    local: LocalClosureAudit,
    max_iter: int = 12,
    run_perturbations: bool = True,
) -> HydraulicClosureAudit:
    solve_kwargs = dict(
        provider=provider,
        spec=bridge.spec,
        y=bridge.y_conserved,
        max_iter=int(max_iter),
        residual_tol=1.0e-7,
        liquid_target_relax=1.0,
        vapor_target_relax=1.0,
        vapor_target_relax_min=1.0,
        vapor_regularization_weight=0.0,
    )
    nominal = solve_simultaneous_algebraic_state(z_seed=bridge.z_seed, **solve_kwargs)
    perturbations: List[SimultaneousSolveResult] = []
    if run_perturbations:
        for factor in (0.9, 1.1):
            perturbations.append(
                solve_simultaneous_algebraic_state(
                    z_seed=_perturb_seed(bridge, factor),
                    **solve_kwargs,
                )
            )

    liquid_scaled = _diag_scalar(nominal, "simul_lflow_scaled_inf")
    vapor_scaled = _diag_scalar(nominal, "simul_vflow_scaled_inf")
    layout = SimultaneousMini8Layout(
        n_active=int(bridge.spec.active_stage0.size),
        n_total_stages=int(bridge.spec.n_total_stages),
    )
    _t, p_global, _b, _tt, _bt, l_global, v_global = layout.split(nominal.z)
    p_local = np.asarray([row.result.P_psia for row in local.stages], dtype=float)
    p_mismatch = float(np.max(np.abs(p_global - p_local))) if p_local.size else float("inf")
    l_limit = _active_limiter_count(nominal.evaluation.liquid_flow.clamped_flag)
    v_limit = _active_limiter_count(nominal.evaluation.vapor_flow.clamped_flag)

    pressure_spread = 0.0 if run_perturbations else float("nan")
    flow_spread = 0.0 if run_perturbations else float("nan")
    all_solutions = [nominal] + perturbations
    for candidate in all_solutions[1:]:
        _ct, cp, _cb, _ctt, _cbt, cl, cv = layout.split(candidate.z)
        pressure_spread = max(pressure_spread, float(np.max(np.abs(cp - p_global))))
        flow_spread = max(
            flow_spread,
            float(
                np.max(
                    np.abs(np.concatenate([cl - l_global, cv - v_global]))
                    / np.maximum(np.abs(np.concatenate([l_global, v_global])), 1.0e-9)
                )
            ),
        )
    projections = int(sum(int(result.accepted_projection_count) for result in all_solutions))
    attempted_projections = int(sum(int(result.projection_count) for result in all_solutions))
    robust = bool(
        run_perturbations
        and all(result.converged and not result.failed for result in perturbations)
        and pressure_spread < 0.1
        and flow_spread < 1.0e-4
    )
    strict_pass = bool(
        nominal.converged
        and not nominal.failed
        and liquid_scaled < 1.0e-5
        and vapor_scaled < 1.0e-5
        and p_mismatch < 0.1
        and l_limit == 0
        and v_limit == 0
        and projections == 0
        and robust
        and bridge.terminal_mapping_complete
    )
    return HydraulicClosureAudit(
        nominal=nominal,
        perturbations=tuple(perturbations),
        liquid_flow_scaled_residual=float(liquid_scaled),
        vapor_flow_scaled_residual=float(vapor_scaled),
        pressure_drop_scaled_residual=float(vapor_scaled),
        local_vs_global_pressure_max_psi=float(p_mismatch),
        active_liquid_limiter_count=int(l_limit),
        active_vapor_limiter_count=int(v_limit),
        projection_count=int(projections),
        attempted_projection_count=int(attempted_projections),
        perturbations_run=bool(run_perturbations),
        perturbation_pressure_spread_max_psi=float(pressure_spread),
        perturbation_flow_relative_spread_max=float(flow_spread),
        strict_gate_pass=bool(strict_pass),
    )


def classify_frozen_closure(
    *,
    bridge: FrozenCheckpointBridge,
    local: LocalClosureAudit,
    hydraulic: Optional[HydraulicClosureAudit],
) -> str:
    local_numerical_pass = bool(
        local.converged
        and local.component_relative_max < 1.0e-8
        and local.energy_relative_max < 1.0e-7
        and local.volume_relative_max < 1.0e-7
        and local.equilibrium_beta_max < 1.0e-6
        and local.negative_phase_count == 0
        and local.projection_count == 0
    )
    if not local_numerical_pass:
        return "local_uv_failed"
    if hydraulic is None or not hydraulic.strict_gate_pass:
        return "local_uv_passed_global_hydraulics_failed_or_unverified"
    if not bridge.terminal_mapping_complete:
        return "interior_closure_passed_terminal_mapping_incomplete"
    return "frozen_closure_passed"
