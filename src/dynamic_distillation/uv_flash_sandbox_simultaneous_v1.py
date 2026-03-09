"""
uv_flash_sandbox_simultaneous_v1.py

Mini8 UV-flash sandbox with a column-wide simultaneous algebraic solve for
stage thermo states and internal L/V traffic.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from dynamic_distillation.dae_pilot_v1 import finite_difference_jacobian, inf_norm
from dynamic_distillation.uv_flash_sandbox_v1 import (
    _LiquidFlowClosure,
    _LiquidNodeReference,
    _LiquidNodeState,
    _VaporFlowClosure,
    UvMini8PrototypeSpec,
    _append_profile_rows,
    _build_provider,
    _compute_liquid_flow_closure,
    _compute_rhs,
    _compute_vapor_flow_closure,
    _evaluate_partial_reboiler_state,
    _evaluate_total_condenser_state,
    _liquid_internal_energy_from_tp,
    _make_summary_row,
    _pack_state,
    _timestamp_tag,
    _unpack_state,
    _write_csv,
    build_mini8_uv_prototype_spec,
    compare_uv_run_to_reference,
)
from dynamic_distillation.uv_flash_stage_v1 import (
    UvFlashStageGuess,
    UvFlashStageResult,
    _residual_for_state,
)
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


@dataclass(frozen=True)
class SimultaneousMini8Layout:
    n_active: int
    n_total_stages: int

    @property
    def z_size(self) -> int:
        return 3 * int(self.n_active) + 2 + 2 * int(self.n_total_stages)

    @property
    def stage_t_slice(self) -> slice:
        return slice(0, int(self.n_active))

    @property
    def stage_p_slice(self) -> slice:
        start = self.stage_t_slice.stop
        return slice(start, start + int(self.n_active))

    @property
    def stage_beta_slice(self) -> slice:
        start = self.stage_p_slice.stop
        return slice(start, start + int(self.n_active))

    @property
    def top_t_idx(self) -> int:
        return int(self.stage_beta_slice.stop)

    @property
    def bottom_t_idx(self) -> int:
        return int(self.stage_beta_slice.stop) + 1

    @property
    def liquid_slice(self) -> slice:
        start = self.bottom_t_idx + 1
        return slice(start, start + int(self.n_total_stages))

    @property
    def vapor_slice(self) -> slice:
        start = self.liquid_slice.stop
        return slice(start, start + int(self.n_total_stages))

    def split(
        self,
        z: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float, np.ndarray, np.ndarray]:
        arr = np.asarray(z, dtype=float).reshape((-1,))
        if arr.size != self.z_size:
            raise ValueError(f"Expected z size {self.z_size}, got {arr.size}")
        return (
            np.asarray(arr[self.stage_t_slice], dtype=float).copy(),
            np.asarray(arr[self.stage_p_slice], dtype=float).copy(),
            np.asarray(arr[self.stage_beta_slice], dtype=float).copy(),
            float(arr[self.top_t_idx]),
            float(arr[self.bottom_t_idx]),
            np.asarray(arr[self.liquid_slice], dtype=float).copy(),
            np.asarray(arr[self.vapor_slice], dtype=float).copy(),
        )

    def join(
        self,
        stage_t: np.ndarray,
        stage_p: np.ndarray,
        stage_beta: np.ndarray,
        top_t: float,
        bottom_t: float,
        liquid: np.ndarray,
        vapor: np.ndarray,
    ) -> np.ndarray:
        return np.concatenate(
            [
                np.asarray(stage_t, dtype=float).reshape((int(self.n_active),)),
                np.asarray(stage_p, dtype=float).reshape((int(self.n_active),)),
                np.asarray(stage_beta, dtype=float).reshape((int(self.n_active),)),
                np.asarray([top_t, bottom_t], dtype=float),
                np.asarray(liquid, dtype=float).reshape((int(self.n_total_stages),)),
                np.asarray(vapor, dtype=float).reshape((int(self.n_total_stages),)),
            ],
            axis=0,
        )

    def clip(self, z: np.ndarray) -> np.ndarray:
        stage_t, stage_p, stage_beta, top_t, bottom_t, liquid, vapor = self.split(z)
        stage_t = np.clip(stage_t, -200.0, 1000.0)
        stage_p = np.clip(stage_p, 1.0, 1000.0)
        stage_beta = np.clip(stage_beta, 1.0e-8, 1.0 - 1.0e-8)
        top_t = float(np.clip(top_t, 40.0, 400.0))
        bottom_t = float(np.clip(bottom_t, 40.0, 500.0))
        liquid = np.clip(np.where(np.isfinite(liquid), liquid, 0.0), 0.0, None)
        vapor = np.clip(np.where(np.isfinite(vapor), vapor, 0.0), 0.0, None)
        return self.join(stage_t, stage_p, stage_beta, top_t, bottom_t, liquid, vapor)


@dataclass(frozen=True)
class SimultaneousMini8Evaluation:
    residual: np.ndarray
    raw_residual: np.ndarray
    stage_results: List[UvFlashStageResult]
    condenser_state: Optional[UvFlashStageResult]
    reboiler_state: Optional[UvFlashStageResult]
    top_node: _LiquidNodeState
    bottom_node: _LiquidNodeState
    liquid_flow: _LiquidFlowClosure
    vapor_flow: _VaporFlowClosure
    diag: Dict[str, np.ndarray]


@dataclass(frozen=True)
class SimultaneousSolveResult:
    z: np.ndarray
    evaluation: SimultaneousMini8Evaluation
    converged: bool
    failed: bool
    iterations: int
    accepted_alpha: float
    relaxed_accept: bool
    vapor_target_relax: float


def _safe_scale(values: np.ndarray, floor: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape((-1,))
    out = np.abs(arr)
    out = np.where(np.isfinite(out) & (out > float(floor)), out, float(floor))
    return out


def _flow_scale_from_nominal(flow: np.ndarray, floor: float = 1.0e-3) -> np.ndarray:
    return _safe_scale(np.asarray(flow, dtype=float).reshape((-1,)), float(floor))


def _scale_residual_blocks(
    *,
    stage_raw: Sequence[np.ndarray],
    stage_results: Sequence[UvFlashStageResult],
    spec: UvMini8PrototypeSpec,
    top_energy_raw: float,
    bottom_energy_raw: float,
    top_energy_state_BTU: float,
    bottom_energy_state_BTU: float,
    liquid_raw: np.ndarray,
    vapor_raw: np.ndarray,
) -> tuple[List[np.ndarray], Dict[str, np.ndarray]]:
    stage_scaled: List[np.ndarray] = []
    stage_u_scale = []
    stage_v_scale = []
    stage_beta_scale = []
    for idx, raw in enumerate(stage_raw):
        raw_vec = np.asarray(raw, dtype=float).reshape((3,))
        res = stage_results[idx]
        u_scale = max(
            abs(float(res.HV_BTU_lbmol) - float(res.HL_BTU_lbmol)),
            abs(float(res.uV_BTU_lbmol) - float(res.uL_BTU_lbmol)),
            1.0,
        )
        v_scale = max(abs(float(res.vV_ft3_lbmol)), abs(float(res.vL_ft3_lbmol)), 1.0e-6)
        beta_scale = 1.0
        stage_u_scale.append(u_scale)
        stage_v_scale.append(v_scale)
        stage_beta_scale.append(beta_scale)
        stage_scaled.append(
            np.asarray(
                [
                    raw_vec[0] / float(u_scale),
                    raw_vec[1] / float(v_scale),
                    raw_vec[2] / float(beta_scale),
                ],
                dtype=float,
            )
        )

    node_energy_scale = np.asarray(
        [
            max(abs(float(top_energy_state_BTU)), abs(float(top_energy_raw)), 1.0e3),
            max(abs(float(bottom_energy_state_BTU)), abs(float(bottom_energy_raw)), 1.0e3),
        ],
        dtype=float,
    )
    node_energy_scaled = np.asarray([top_energy_raw, bottom_energy_raw], dtype=float) / node_energy_scale

    liquid_scale = _flow_scale_from_nominal(np.asarray(spec.L_lbmolps, dtype=float), floor=1.0e-3)
    if liquid_scale.size > 0:
        liquid_scale[0] = max(float(liquid_scale[0]), abs(float(spec.condenser_to_top_nominal_lbmolps)), 1.0e-3)
        liquid_scale[-1] = max(float(liquid_scale[-1]), abs(float(spec.reboiler_to_bottom_nominal_lbmolps)), 1.0e-3)
    vapor_scale = _flow_scale_from_nominal(np.asarray(spec.V_lbmolps, dtype=float), floor=1.0e-3)
    if vapor_scale.size > 0:
        vapor_scale[-1] = max(float(vapor_scale[-1]), 1.0e-3)

    liquid_scaled = np.asarray(liquid_raw, dtype=float).reshape((-1,)) / liquid_scale
    vapor_scaled = np.asarray(vapor_raw, dtype=float).reshape((-1,)) / vapor_scale

    scale_diag = {
        "simul_stage_u_scale": np.asarray(stage_u_scale, dtype=float),
        "simul_stage_v_scale": np.asarray(stage_v_scale, dtype=float),
        "simul_stage_beta_scale": np.asarray(stage_beta_scale, dtype=float),
        "simul_node_energy_scale_BTU": node_energy_scale.copy(),
        "simul_lflow_scale_lbmolps": liquid_scale.copy(),
        "simul_vflow_scale_lbmolps": vapor_scale.copy(),
        "simul_stage_scaled_inf": np.asarray(
            [max((inf_norm(chunk) for chunk in stage_scaled), default=0.0)],
            dtype=float,
        ),
        "simul_node_energy_scaled_inf": np.asarray([inf_norm(node_energy_scaled)], dtype=float),
        "simul_lflow_scaled_inf": np.asarray([inf_norm(liquid_scaled)], dtype=float),
        "simul_vflow_scaled_inf": np.asarray([inf_norm(vapor_scaled)], dtype=float),
    }
    return stage_scaled + [node_energy_scaled, liquid_scaled, vapor_scaled], scale_diag


def _evaluate_liquid_node_trial(
    *,
    provider: Any,
    ref: _LiquidNodeReference,
    holdup_lbmol: np.ndarray,
    T_F: float,
) -> _LiquidNodeState:
    holdup = np.asarray(holdup_lbmol, dtype=float).reshape((-1,))
    holdup = np.where(np.isfinite(holdup), holdup, 0.0)
    holdup = np.clip(holdup, 1.0e-12, None)
    total = float(np.sum(holdup))
    x_liq = holdup / max(total, 1.0e-12)
    uL, hL = _liquid_internal_energy_from_tp(
        provider,
        T_F=float(T_F),
        P_psia=float(ref.P_psia),
        x_liq=x_liq,
    )
    return _LiquidNodeState(
        stage_label=int(ref.stage_label),
        node_type=str(ref.node_type),
        T_F=float(T_F),
        P_psia=float(ref.P_psia),
        total_component_holdup_lbmol=holdup.copy(),
        total_moles_lbmol=float(total),
        x_liq=x_liq.copy(),
        hL_BTU_lbmol=float(hL),
        u_total_BTU=float(total) * float(uL),
    )


def default_algebraic_seed(*, spec: UvMini8PrototypeSpec) -> np.ndarray:
    layout = SimultaneousMini8Layout(
        n_active=int(spec.active_stage0.size),
        n_total_stages=int(spec.n_total_stages),
    )
    stage_t = np.asarray([float(g.T_F) for g in spec.initial_guesses], dtype=float)
    stage_p = np.asarray([float(g.P_psia) for g in spec.initial_guesses], dtype=float)
    stage_beta = np.asarray([float(g.beta_vapor) for g in spec.initial_guesses], dtype=float)
    liquid = np.asarray(spec.L_lbmolps, dtype=float).reshape((int(spec.n_total_stages),)).copy()
    if liquid.size > 0:
        liquid[0] = float(spec.condenser_to_top_nominal_lbmolps)
        liquid[-1] = float(spec.reboiler_to_bottom_nominal_lbmolps)
    vapor = np.asarray(spec.V_lbmolps, dtype=float).reshape((int(spec.n_total_stages),)).copy()
    top_t = float(spec.top_node_reference.T_F)
    bottom_t = float(spec.bottom_node_reference.T_F)
    return layout.clip(layout.join(stage_t, stage_p, stage_beta, top_t, bottom_t, liquid, vapor))


def _clip_newton_delta(
    *,
    delta: np.ndarray,
    z_ref: np.ndarray,
    spec: UvMini8PrototypeSpec,
) -> np.ndarray:
    layout = SimultaneousMini8Layout(
        n_active=int(spec.active_stage0.size),
        n_total_stages=int(spec.n_total_stages),
    )
    d_t, d_p, d_beta, d_top_t, d_bottom_t, d_l, d_v = layout.split(delta)
    _rt, _rp, _rb, _rtt, _rbt, _rl, _rv = layout.split(z_ref)
    d_t = np.clip(d_t, -10.0, 10.0)
    d_p = np.clip(d_p, -5.0, 5.0)
    d_beta = np.clip(d_beta, -0.05, 0.05)
    d_top_t = float(np.clip(d_top_t, -5.0, 5.0))
    d_bottom_t = float(np.clip(d_bottom_t, -5.0, 5.0))
    l_scale = _flow_scale_from_nominal(np.asarray(spec.L_lbmolps, dtype=float), floor=1.0e-3)
    if l_scale.size > 0:
        l_scale[0] = max(float(l_scale[0]), abs(float(spec.condenser_to_top_nominal_lbmolps)), 1.0e-3)
        l_scale[-1] = max(float(l_scale[-1]), abs(float(spec.reboiler_to_bottom_nominal_lbmolps)), 1.0e-3)
    v_scale = _flow_scale_from_nominal(np.asarray(spec.V_lbmolps, dtype=float), floor=1.0e-3)
    d_l = np.clip(d_l, -0.2 * l_scale, 0.2 * l_scale)
    d_v = np.clip(d_v, -0.2 * v_scale, 0.2 * v_scale)
    return layout.join(d_t, d_p, d_beta, d_top_t, d_bottom_t, d_l, d_v)


def _blend_next_seed(
    *,
    z_prev: np.ndarray,
    z_new: np.ndarray,
    spec: UvMini8PrototypeSpec,
    stage_relax: float,
    node_temp_relax: float,
    flow_relax: float,
) -> np.ndarray:
    layout = SimultaneousMini8Layout(
        n_active=int(spec.active_stage0.size),
        n_total_stages=int(spec.n_total_stages),
    )
    p_t, p_p, p_b, p_top_t, p_bottom_t, p_l, p_v = layout.split(z_prev)
    n_t, n_p, n_b, n_top_t, n_bottom_t, n_l, n_v = layout.split(z_new)
    a_stage = float(np.clip(stage_relax, 0.0, 1.0))
    a_node = float(np.clip(node_temp_relax, 0.0, 1.0))
    a_flow = float(np.clip(flow_relax, 0.0, 1.0))
    return layout.clip(
        layout.join(
            (1.0 - a_stage) * p_t + a_stage * n_t,
            (1.0 - a_stage) * p_p + a_stage * n_p,
            (1.0 - a_stage) * p_b + a_stage * n_b,
            (1.0 - a_node) * float(p_top_t) + a_node * float(n_top_t),
            (1.0 - a_node) * float(p_bottom_t) + a_node * float(n_bottom_t),
            (1.0 - a_flow) * p_l + a_flow * n_l,
            (1.0 - a_flow) * p_v + a_flow * n_v,
        )
    )


def _blend_flow_target(
    *,
    anchor: np.ndarray,
    raw: np.ndarray,
    relax: float,
) -> np.ndarray:
    a = float(np.clip(relax, 0.0, 1.0))
    anchor_arr = np.asarray(anchor, dtype=float).reshape((-1,))
    raw_arr = np.asarray(raw, dtype=float).reshape((-1,))
    return (1.0 - a) * anchor_arr + a * raw_arr


def _adapt_vapor_target_relax(
    *,
    current_relax: float,
    solve: SimultaneousSolveResult,
    min_relax: float,
    max_relax: float,
    allow_increase: bool = True,
) -> float:
    relax = float(np.clip(current_relax, float(min_relax), float(max_relax)))
    diag = getattr(solve.evaluation, "diag", {}) or {}
    try:
        vflow_scaled_inf = float(
            np.asarray(diag.get("simul_vflow_scaled_inf", np.asarray([np.nan], dtype=float)), dtype=float).reshape((-1,))[0]
        )
    except Exception:
        vflow_scaled_inf = float("nan")
    try:
        stage_scaled_inf = float(
            np.asarray(diag.get("simul_stage_scaled_inf", np.asarray([np.nan], dtype=float)), dtype=float).reshape((-1,))[0]
        )
    except Exception:
        stage_scaled_inf = float("nan")

    if bool(solve.failed):
        return float(np.clip(relax * 0.5, float(min_relax), float(max_relax)))
    if np.isfinite(vflow_scaled_inf) and vflow_scaled_inf > 5.0:
        return float(np.clip(relax * 0.7, float(min_relax), float(max_relax)))
    if np.isfinite(vflow_scaled_inf) and vflow_scaled_inf > 2.0:
        return float(np.clip(relax * 0.85, float(min_relax), float(max_relax)))
    if bool(allow_increase) and bool(solve.converged) and float(solve.accepted_alpha) >= 0.25:
        return float(np.clip(relax * 1.2, float(min_relax), float(max_relax)))
    if (
        bool(allow_increase)
        and
        np.isfinite(vflow_scaled_inf)
        and np.isfinite(stage_scaled_inf)
        and vflow_scaled_inf <= 1.0
        and vflow_scaled_inf <= max(1.25 * stage_scaled_inf, 0.5)
        and float(solve.accepted_alpha) >= 0.25
    ):
        return float(np.clip(relax * 1.15, float(min_relax), float(max_relax)))
    return float(np.clip(relax, float(min_relax), float(max_relax)))


def _adapt_simultaneous_dt(
    *,
    current_dt: float,
    solve: SimultaneousSolveResult,
    dt_min: float,
    dt_max: float,
    good_step_streak: int,
    grow_streak_required: int,
) -> tuple[float, int]:
    dt_now = float(np.clip(current_dt, float(dt_min), float(dt_max)))
    streak = max(int(good_step_streak), 0)
    alg_inf = float(inf_norm(solve.evaluation.residual))

    good_step = bool(solve.converged) and np.isfinite(alg_inf) and alg_inf <= 1.0e-6 and float(solve.accepted_alpha) >= 0.25
    if good_step:
        streak += 1
    else:
        streak = 0

    if bool(solve.failed) or (not bool(solve.converged)) or (np.isfinite(alg_inf) and alg_inf > 0.5):
        return float(np.clip(dt_now * 0.5, float(dt_min), float(dt_max))), streak
    if np.isfinite(alg_inf) and alg_inf > 0.1:
        return float(np.clip(dt_now * 0.8, float(dt_min), float(dt_max))), streak
    if streak >= max(int(grow_streak_required), 1):
        return float(np.clip(dt_now * 1.2, float(dt_min), float(dt_max))), streak
    return float(np.clip(dt_now, float(dt_min), float(dt_max))), streak


def _sanitize_trial_state(
    *,
    y_trial: np.ndarray,
    spec: UvMini8PrototypeSpec,
) -> np.ndarray:
    n_block, u_block, top_block, bottom_block, top_u_block, bottom_u_block = _unpack_state(
        y_trial,
        n_active=int(spec.active_stage0.size),
        n_components=len(spec.component_names),
    )
    n_block = np.clip(np.where(np.isfinite(n_block), n_block, 1.0e-12), 1.0e-12, None)
    top_block = np.clip(np.where(np.isfinite(top_block), top_block, 1.0e-12), 1.0e-12, None)
    bottom_block = np.clip(np.where(np.isfinite(bottom_block), bottom_block, 1.0e-12), 1.0e-12, None)
    if not np.all(np.isfinite(u_block)):
        u_block = np.where(np.isfinite(u_block), u_block, 0.0)
    if not np.isfinite(float(top_u_block)):
        top_u_block = float(spec.top_node_reference.initial_total_internal_energy_BTU)
    if not np.isfinite(float(bottom_u_block)):
        bottom_u_block = float(spec.bottom_node_reference.initial_total_internal_energy_BTU)
    return _pack_state(
        n_block,
        u_block,
        top_block,
        bottom_block,
        float(top_u_block),
        float(bottom_u_block),
    )


def _attempt_preview_step(
    *,
    provider: Any,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    dydt: np.ndarray,
    z_seed: np.ndarray,
    dt_use: float,
    dt_min: float,
    max_iter: int,
    residual_tol: float,
    jac_rel_step: float,
    line_search_max: int,
    liquid_target_relax: float,
    vapor_target_relax: float,
    vapor_target_relax_min: float,
    state_relax_min: float = 0.125,
) -> tuple[bool, np.ndarray, Optional[SimultaneousSolveResult], float, float]:
    dt_try = float(dt_use)
    dt_floor = float(max(dt_min, 1.0e-12))
    state_floor = float(np.clip(state_relax_min, 1.0e-4, 1.0))
    last_preview: Optional[SimultaneousSolveResult] = None
    while dt_try > 0.0:
        state_relax = 1.0
        while state_relax >= state_floor - 1.0e-12:
            y_trial = _sanitize_trial_state(
                y_trial=np.asarray(y, dtype=float) + float(state_relax) * float(dt_try) * np.asarray(dydt, dtype=float),
                spec=spec,
            )
            preview_solve = solve_simultaneous_algebraic_state(
                provider=provider,
                spec=spec,
                y=y_trial,
                z_seed=z_seed,
                max_iter=int(max_iter),
                residual_tol=float(residual_tol),
                jac_rel_step=float(jac_rel_step),
                line_search_max=int(line_search_max),
                liquid_target_relax=float(liquid_target_relax),
                vapor_target_relax=float(vapor_target_relax),
                vapor_target_relax_min=float(vapor_target_relax_min),
            )
            last_preview = preview_solve
            preview_alg_inf = float(inf_norm(preview_solve.evaluation.residual))
            preview_bad = bool(preview_solve.failed) or (not np.isfinite(preview_alg_inf)) or preview_alg_inf > 1.0
            if not preview_bad:
                return True, y_trial, preview_solve, float(dt_try), float(state_relax)
            state_relax *= 0.5
        if dt_try > dt_floor + 1.0e-12:
            dt_try = float(max(float(dt_try) * 0.5, dt_floor))
            continue
        break
    return False, np.asarray(y, dtype=float).copy(), last_preview, float(dt_try), 0.0


def evaluate_simultaneous_algebraic_state(
    *,
    provider: Any,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    z: np.ndarray,
    z_anchor: Optional[np.ndarray] = None,
    liquid_target_relax: float = 1.0,
    vapor_target_relax: float = 1.0,
) -> SimultaneousMini8Evaluation:
    layout = SimultaneousMini8Layout(
        n_active=int(spec.active_stage0.size),
        n_total_stages=int(spec.n_total_stages),
    )
    z_work = layout.clip(z)
    stage_t, stage_p, stage_beta, top_t, bottom_t, liquid_trial, vapor_trial = layout.split(z_work)
    if z_anchor is None:
        liquid_anchor = np.asarray(liquid_trial, dtype=float).copy()
        vapor_anchor = np.asarray(vapor_trial, dtype=float).copy()
    else:
        _at, _ap, _ab, _att, _abt, liquid_anchor, vapor_anchor = layout.split(layout.clip(z_anchor))

    n_total, u_total, top_liquid, bottom_liquid, top_u_total, bottom_u_total = _unpack_state(
        y,
        n_active=int(spec.active_stage0.size),
        n_components=len(spec.component_names),
    )

    top_node = _evaluate_liquid_node_trial(
        provider=provider,
        ref=spec.top_node_reference,
        holdup_lbmol=top_liquid,
        T_F=float(top_t),
    )
    bottom_node = _evaluate_liquid_node_trial(
        provider=provider,
        ref=spec.bottom_node_reference,
        holdup_lbmol=bottom_liquid,
        T_F=float(bottom_t),
    )

    stage_results: List[UvFlashStageResult] = []
    stage_raw_residuals: List[np.ndarray] = []
    for idx, stage0 in enumerate(spec.active_stage0):
        n_stage = np.asarray(n_total[idx, :], dtype=float)
        n_stage = np.where(np.isfinite(n_stage), n_stage, 0.0)
        n_stage = np.clip(n_stage, 1.0e-12, None)
        m_tot = float(np.sum(n_stage))
        z_stage = n_stage / max(m_tot, 1.0e-12)
        u_target = float(u_total[idx]) / max(m_tot, 1.0e-12)
        v_target = float(spec.fixed_total_volume_ft3[idx]) / max(m_tot, 1.0e-12)
        resid_vec, stage_state, _ = _residual_for_state(
            provider,
            z_overall=z_stage,
            u_target_BTU_lbmol=float(u_target),
            v_target_ft3_lbmol=float(v_target),
            x_vec=np.asarray([stage_t[idx], stage_p[idx], stage_beta[idx]], dtype=float),
            beta_mode="free",
            beta_fixed=None,
        )
        stage_results.append(
            UvFlashStageResult(
                T_F=float(stage_t[idx]),
                P_psia=float(stage_p[idx]),
                beta_vapor=float(stage_beta[idx]),
                x=np.asarray(stage_state.x, dtype=float).copy(),
                y=np.asarray(stage_state.y, dtype=float).copy(),
                K=np.asarray(stage_state.K, dtype=float).copy(),
                HL_BTU_lbmol=float(stage_state.HL_BTU_lbmol),
                HV_BTU_lbmol=float(stage_state.HV_BTU_lbmol),
                uL_BTU_lbmol=float(stage_state.uL_BTU_lbmol),
                uV_BTU_lbmol=float(stage_state.uV_BTU_lbmol),
                vL_ft3_lbmol=float(stage_state.vL_ft3_lbmol),
                vV_ft3_lbmol=float(stage_state.vV_ft3_lbmol),
                Z_vapor=float(stage_state.Z_vapor),
                residual_u_BTU_lbmol=float(resid_vec[0]),
                residual_v_ft3_lbmol=float(resid_vec[1]),
                residual_beta=float(resid_vec[2]),
                converged=bool(np.all(np.isfinite(resid_vec)) and np.max(np.abs(resid_vec)) <= 1.0e-6),
                iterations=1,
            )
        )
        stage_raw_residuals.append(np.asarray(resid_vec, dtype=float).reshape((3,)))

    condenser_state = (
        _evaluate_total_condenser_state(
            provider=provider,
            spec=spec,
            stage2_result=stage_results[0],
            top_node=top_node,
        )
        if bool(spec.condenser_is_total) and stage_results
        else None
    )
    reboiler_state = (
        _evaluate_partial_reboiler_state(
            provider=provider,
            spec=spec,
            stage_above_result=stage_results[-1],
            bottom_node=bottom_node,
        )
        if bool(spec.reboiler_is_partial) and stage_results
        else None
    )

    top_energy_resid = float(top_node.u_total_BTU) - float(top_u_total)
    bottom_energy_resid = float(bottom_node.u_total_BTU) - float(bottom_u_total)
    liquid_closure = _compute_liquid_flow_closure(
        spec=spec,
        y=y,
        stage_results=stage_results,
        l_prev_lbmolps=np.asarray(liquid_trial, dtype=float),
    )
    vapor_closure = _compute_vapor_flow_closure(
        spec=spec,
        y=y,
        stage_results=stage_results,
        condenser_state=condenser_state,
        reboiler_state=reboiler_state,
        top_node=top_node,
        bottom_node=bottom_node,
        v_prev_lbmolps=np.asarray(vapor_trial, dtype=float),
        liquid_flow=liquid_closure,
    )

    liquid_raw = np.asarray(liquid_closure.raw_lbmolph, dtype=float) / 3600.0
    vapor_raw = np.asarray(vapor_closure.raw_lbmolps, dtype=float)
    liquid_target = _blend_flow_target(
        anchor=np.asarray(liquid_anchor, dtype=float),
        raw=np.asarray(liquid_raw, dtype=float),
        relax=float(liquid_target_relax),
    )
    vapor_target = _blend_flow_target(
        anchor=np.asarray(vapor_anchor, dtype=float),
        raw=np.asarray(vapor_raw, dtype=float),
        relax=float(vapor_target_relax),
    )
    liquid_raw_resid = np.asarray(liquid_trial, dtype=float) - liquid_target
    vapor_raw_resid = np.asarray(vapor_trial, dtype=float) - vapor_target

    scaled_chunks, scale_diag = _scale_residual_blocks(
        stage_raw=stage_raw_residuals,
        stage_results=stage_results,
        spec=spec,
        top_energy_raw=float(top_energy_resid),
        bottom_energy_raw=float(bottom_energy_resid),
        top_energy_state_BTU=float(top_u_total),
        bottom_energy_state_BTU=float(bottom_u_total),
        liquid_raw=liquid_raw_resid,
        vapor_raw=vapor_raw_resid,
    )
    raw_chunks: List[np.ndarray] = list(stage_raw_residuals)
    raw_chunks.append(np.asarray([top_energy_resid, bottom_energy_resid], dtype=float))
    raw_chunks.append(np.asarray(liquid_raw_resid, dtype=float))
    raw_chunks.append(np.asarray(vapor_raw_resid, dtype=float))

    liquid_flow = _LiquidFlowClosure(
        used_lbmolps=np.asarray(liquid_trial, dtype=float).copy(),
        raw_lbmolph=np.asarray(liquid_closure.raw_lbmolph, dtype=float).copy(),
        h_ow_ft=np.asarray(liquid_closure.h_ow_ft, dtype=float).copy(),
        clamped_flag=np.asarray(liquid_closure.clamped_flag, dtype=float).copy(),
    )
    vapor_flow = _VaporFlowClosure(
        used_lbmolps=np.asarray(vapor_trial, dtype=float).copy(),
        raw_lbmolps=np.asarray(vapor_closure.raw_lbmolps, dtype=float).copy(),
        dp_psia=np.asarray(vapor_closure.dp_psia, dtype=float).copy(),
        h_ow_ft=np.asarray(vapor_closure.h_ow_ft, dtype=float).copy(),
        clamped_flag=np.asarray(vapor_closure.clamped_flag, dtype=float).copy(),
    )

    diag = {
        "simul_stage_resid_u": np.asarray([float(r.residual_u_BTU_lbmol) for r in stage_results], dtype=float),
        "simul_stage_resid_v": np.asarray([float(r.residual_v_ft3_lbmol) for r in stage_results], dtype=float),
        "simul_stage_resid_beta": np.asarray([float(r.residual_beta) for r in stage_results], dtype=float),
        "simul_top_energy_resid_BTU": np.asarray([float(top_energy_resid)], dtype=float),
        "simul_bottom_energy_resid_BTU": np.asarray([float(bottom_energy_resid)], dtype=float),
        "simul_lflow_inf_lbmolps": np.asarray([inf_norm(np.asarray(liquid_raw_resid, dtype=float))], dtype=float),
        "simul_vflow_inf_lbmolps": np.asarray([inf_norm(np.asarray(vapor_raw_resid, dtype=float))], dtype=float),
        "simul_lflow_target_inf_lbmolps": np.asarray([inf_norm(np.asarray(liquid_target - liquid_anchor, dtype=float))], dtype=float),
        "simul_vflow_target_inf_lbmolps": np.asarray([inf_norm(np.asarray(vapor_target - vapor_anchor, dtype=float))], dtype=float),
        "simul_lflow_raw_gap_inf_lbmolps": np.asarray([inf_norm(np.asarray(liquid_raw - liquid_anchor, dtype=float))], dtype=float),
        "simul_vflow_raw_gap_inf_lbmolps": np.asarray([inf_norm(np.asarray(vapor_raw - vapor_anchor, dtype=float))], dtype=float),
        "simul_raw_alg_inf": np.asarray([inf_norm(np.concatenate(raw_chunks, axis=0))], dtype=float),
        "simul_scaled_alg_inf": np.asarray([inf_norm(np.concatenate(scaled_chunks, axis=0))], dtype=float),
    }
    diag.update(scale_diag)

    return SimultaneousMini8Evaluation(
        residual=np.concatenate(scaled_chunks, axis=0),
        raw_residual=np.concatenate(raw_chunks, axis=0),
        stage_results=stage_results,
        condenser_state=condenser_state,
        reboiler_state=reboiler_state,
        top_node=top_node,
        bottom_node=bottom_node,
        liquid_flow=liquid_flow,
        vapor_flow=vapor_flow,
        diag=diag,
    )


def solve_simultaneous_algebraic_state(
    *,
    provider: Any,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    z_seed: np.ndarray,
    max_iter: int = 8,
    residual_tol: float = 1.0e-6,
    jac_rel_step: float = 1.0e-6,
    line_search_max: int = 6,
    liquid_target_relax: float = 1.0,
    vapor_target_relax: float = 0.25,
    vapor_target_relax_min: float = 0.05,
) -> SimultaneousSolveResult:
    layout = SimultaneousMini8Layout(
        n_active=int(spec.active_stage0.size),
        n_total_stages=int(spec.n_total_stages),
    )
    z_work = layout.clip(z_seed)
    anchor_z = np.asarray(z_work, dtype=float).copy()
    vapor_relax_local = float(np.clip(vapor_target_relax, vapor_target_relax_min, 1.0))
    last_eval = evaluate_simultaneous_algebraic_state(
        provider=provider,
        spec=spec,
        y=y,
        z=z_work,
        z_anchor=anchor_z,
        liquid_target_relax=float(liquid_target_relax),
        vapor_target_relax=float(vapor_relax_local),
    )
    converged = False
    failed = False
    iterations = 0
    accepted_alpha = 0.0
    relaxed_accept = False

    def _residual_fn(z_vec: np.ndarray) -> np.ndarray:
            z_try = layout.clip(z_vec)
            return evaluate_simultaneous_algebraic_state(
                provider=provider,
                spec=spec,
                y=y,
                z=z_try,
                z_anchor=anchor_z,
                liquid_target_relax=float(liquid_target_relax),
                vapor_target_relax=float(vapor_relax_local),
            ).residual

    for iter_idx in range(max(1, int(max_iter))):
        iterations = iter_idx + 1
        resid = np.asarray(last_eval.residual, dtype=float).reshape((-1,))
        resid_inf = inf_norm(resid)
        if np.isfinite(resid_inf) and resid_inf <= float(residual_tol):
            converged = True
            break
        if not np.all(np.isfinite(resid)):
            failed = True
            break
        try:
            J = finite_difference_jacobian(_residual_fn, z_work, rel_step=float(jac_rel_step))
            if J.shape != (resid.size, z_work.size) or (not np.all(np.isfinite(J))):
                failed = True
                break
            delta, *_ = np.linalg.lstsq(J, -resid, rcond=None)
            delta = np.asarray(delta, dtype=float).reshape((z_work.size,))
            if not np.all(np.isfinite(delta)):
                failed = True
                break
            delta = _clip_newton_delta(delta=delta, z_ref=z_work, spec=spec)
        except Exception:
            failed = True
            break

        base_norm = inf_norm(resid)
        accepted = False
        alpha = 1.0
        best_try_eval = None
        best_try_z = None
        best_try_norm = float("inf")
        best_try_alpha = 0.0
        accepted_alpha = 0.0
        relaxed_accept = False
        for _ in range(max(1, int(line_search_max))):
            z_try = layout.clip(z_work + float(alpha) * delta)
            eval_try = evaluate_simultaneous_algebraic_state(
                provider=provider,
                spec=spec,
                y=y,
                z=z_try,
                z_anchor=anchor_z,
                liquid_target_relax=float(liquid_target_relax),
                vapor_target_relax=float(vapor_relax_local),
            )
            try_norm = inf_norm(eval_try.residual)
            if np.isfinite(try_norm) and try_norm < best_try_norm:
                best_try_norm = float(try_norm)
                best_try_eval = eval_try
                best_try_z = z_try
                best_try_alpha = float(alpha)
            if np.isfinite(try_norm) and ((not np.isfinite(base_norm)) or try_norm <= base_norm):
                z_work = z_try
                last_eval = eval_try
                accepted = True
                accepted_alpha = float(alpha)
                break
            alpha *= 0.5
        if not accepted:
            if best_try_eval is not None and np.isfinite(best_try_norm) and best_try_norm <= max(float(base_norm) * 1.05, float(base_norm) + 1.0e-6):
                z_work = np.asarray(best_try_z, dtype=float)
                last_eval = best_try_eval
                accepted_alpha = float(best_try_alpha)
                relaxed_accept = True
            else:
                try:
                    vflow_scaled_inf = float(
                        np.asarray(
                            last_eval.diag.get("simul_vflow_scaled_inf", np.asarray([np.nan], dtype=float)),
                            dtype=float,
                        ).reshape((-1,))[0]
                    )
                except Exception:
                    vflow_scaled_inf = float("nan")
                if np.isfinite(vflow_scaled_inf) and vflow_scaled_inf > 1.0 and vapor_relax_local > float(vapor_target_relax_min) + 1.0e-12:
                    vapor_relax_local = float(np.clip(vapor_relax_local * 0.7, vapor_target_relax_min, 1.0))
                    last_eval = evaluate_simultaneous_algebraic_state(
                        provider=provider,
                        spec=spec,
                        y=y,
                        z=z_work,
                        z_anchor=anchor_z,
                        liquid_target_relax=float(liquid_target_relax),
                        vapor_target_relax=float(vapor_relax_local),
                    )
                    continue
                failed = True
                break

        try:
            vflow_scaled_inf_after = float(
                np.asarray(
                    last_eval.diag.get("simul_vflow_scaled_inf", np.asarray([np.nan], dtype=float)),
                    dtype=float,
                ).reshape((-1,))[0]
            )
        except Exception:
            vflow_scaled_inf_after = float("nan")
        if (
            np.isfinite(vflow_scaled_inf_after)
            and vflow_scaled_inf_after > 1.0
            and vapor_relax_local > float(vapor_target_relax_min) + 1.0e-12
            and (float(accepted_alpha) <= 0.125 or bool(relaxed_accept))
        ):
            vapor_relax_local = float(np.clip(vapor_relax_local * 0.85, vapor_target_relax_min, 1.0))
            last_eval = evaluate_simultaneous_algebraic_state(
                provider=provider,
                spec=spec,
                y=y,
                z=z_work,
                z_anchor=anchor_z,
                liquid_target_relax=float(liquid_target_relax),
                vapor_target_relax=float(vapor_relax_local),
            )

    if not converged and not failed:
        resid_inf = inf_norm(last_eval.residual)
        converged = bool(np.isfinite(resid_inf) and resid_inf <= float(residual_tol))

    return SimultaneousSolveResult(
        z=np.asarray(z_work, dtype=float).copy(),
        evaluation=last_eval,
        converged=bool(converged),
        failed=bool(failed),
        iterations=int(iterations),
        accepted_alpha=float(accepted_alpha),
        relaxed_accept=bool(relaxed_accept),
        vapor_target_relax=float(vapor_relax_local),
    )


def run_mini8_uv_flash_simultaneous_prototype(
    *,
    excel_path: str,
    n_steps: Optional[int] = None,
    dt_sec: Optional[float] = None,
    logs_dir: Optional[str] = None,
    write_csv: bool = True,
    thermo_mode: str = "auto",
    thermo_table_path: str = r"cache\thermo_table.json",
    thermo_pool_workers: Optional[int] = None,
    thermo_pool_chunk_size: int = 4,
    reference_profile_csv: Optional[str] = None,
    max_iter: int = 8,
    residual_tol: float = 1.0e-6,
    jac_rel_step: float = 1.0e-6,
    line_search_max: int = 6,
    stage_seed_relax: float = 0.9,
    node_temp_seed_relax: float = 0.8,
    flow_seed_relax: float = 0.25,
    liquid_target_relax: float = 1.0,
    vapor_target_relax: float = 0.25,
    adaptive_vapor_target: bool = True,
    vapor_target_relax_min: float = 0.05,
    vapor_target_relax_max: float = 1.0,
    vapor_reopen_streak_required: int = 3,
    adaptive_dt: bool = True,
    dt_min_sec: Optional[float] = None,
    dt_max_sec: Optional[float] = None,
    dt_grow_streak_required: int = 2,
    max_total_steps: int = 500,
) -> Dict[str, Any]:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)
    provider, thermo_mode_used = _build_provider(
        col,
        thermo_mode=thermo_mode,
        thermo_table_path=thermo_table_path,
        thermo_pool_workers=thermo_pool_workers,
        thermo_pool_chunk_size=thermo_pool_chunk_size,
    )
    try:
        spec = build_mini8_uv_prototype_spec(excel_path=excel_path, provider=provider)
        dt_base = float(dt_sec) if dt_sec is not None else float(col.sim.dt_sec)
        n_steps_eff = int(n_steps) if n_steps is not None else max(
            int(round(float(col.sim.t_final_sec) / max(dt_base, 1.0e-12))),
            1,
        )
        if n_steps_eff < 1:
            n_steps_eff = 1
        t_final = float(n_steps_eff) * float(dt_base)
        dt_curr = float(dt_base)
        dt_min_eff = float(dt_min_sec) if dt_min_sec is not None else max(float(dt_base) * 0.03125, 1.0e-4)
        dt_max_eff = float(dt_max_sec) if dt_max_sec is not None else float(dt_base)
        dt_curr = float(np.clip(dt_curr, dt_min_eff, dt_max_eff))

        y = _pack_state(
            spec.initial_total_component_holdup_lbmol,
            spec.initial_total_internal_energy_BTU,
            spec.top_node_reference.initial_component_holdup_lbmol,
            spec.bottom_node_reference.initial_component_holdup_lbmol,
            float(spec.top_node_reference.initial_total_internal_energy_BTU),
            float(spec.bottom_node_reference.initial_total_internal_energy_BTU),
        )
        z = default_algebraic_seed(spec=spec)

        summary_rows: List[Dict[str, Any]] = []
        profile_rows: List[Dict[str, Any]] = []
        compare_outputs: Dict[str, str] = {}
        last_eval: Optional[SimultaneousMini8Evaluation] = None
        last_solve: Optional[SimultaneousSolveResult] = None
        vapor_target_relax_curr = float(np.clip(vapor_target_relax, vapor_target_relax_min, vapor_target_relax_max))
        good_vapor_step_streak = 0
        good_dt_step_streak = 0
        prefetched_solve: Optional[SimultaneousSolveResult] = None
        last_state_update_relax = 1.0
        t_s = 0.0
        step = 0
        while True:
            z_seed_in = np.asarray(z, dtype=float).copy()
            if prefetched_solve is not None:
                solve = prefetched_solve
                prefetched_solve = None
            else:
                solve = solve_simultaneous_algebraic_state(
                    provider=provider,
                    spec=spec,
                    y=y,
                    z_seed=z_seed_in,
                    max_iter=int(max_iter),
                    residual_tol=float(residual_tol),
                    jac_rel_step=float(jac_rel_step),
                    line_search_max=int(line_search_max),
                    liquid_target_relax=float(liquid_target_relax),
                    vapor_target_relax=float(vapor_target_relax_curr),
                    vapor_target_relax_min=float(vapor_target_relax_min),
                )
            last_eval = solve.evaluation
            last_solve = solve

            dydt = None
            if step < n_steps_eff:
                dydt = _compute_rhs(
                    spec=spec,
                    y=y,
                    stage_results=last_eval.stage_results,
                    condenser_state=last_eval.condenser_state,
                    reboiler_state=last_eval.reboiler_state,
                    top_node=last_eval.top_node,
                    bottom_node=last_eval.bottom_node,
                    liquid_flow=last_eval.liquid_flow,
                    vapor_flow=last_eval.vapor_flow,
                )

            row = _make_summary_row(
                time_s=t_s,
                stage_results=last_eval.stage_results,
                condenser_state=last_eval.condenser_state,
                reboiler_state=last_eval.reboiler_state,
                dydt=dydt,
                spec=spec,
                y=y,
                top_node=last_eval.top_node,
                bottom_node=last_eval.bottom_node,
                liquid_flow=last_eval.liquid_flow,
                vapor_flow=last_eval.vapor_flow,
            )
            row["simultaneous_enabled"] = 1
            row["simultaneous_iter_count"] = int(solve.iterations)
            row["simultaneous_converged"] = int(1 if solve.converged else 0)
            row["simultaneous_failed"] = int(1 if solve.failed else 0)
            row["simultaneous_alg_inf"] = float(inf_norm(solve.evaluation.residual))
            row["simultaneous_raw_alg_inf"] = float(inf_norm(solve.evaluation.raw_residual))
            row["simultaneous_accept_alpha"] = float(solve.accepted_alpha)
            row["simultaneous_relaxed_accept"] = int(1 if solve.relaxed_accept else 0)
            row["simul_stage_scaled_inf"] = float(
                np.asarray(last_eval.diag.get("simul_stage_scaled_inf", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simul_node_energy_scaled_inf"] = float(
                np.asarray(last_eval.diag.get("simul_node_energy_scaled_inf", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simul_lflow_scaled_inf"] = float(
                np.asarray(last_eval.diag.get("simul_lflow_scaled_inf", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simul_vflow_scaled_inf"] = float(
                np.asarray(last_eval.diag.get("simul_vflow_scaled_inf", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simul_lflow_target_inf_lbmolps"] = float(
                np.asarray(last_eval.diag.get("simul_lflow_target_inf_lbmolps", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simul_vflow_target_inf_lbmolps"] = float(
                np.asarray(last_eval.diag.get("simul_vflow_target_inf_lbmolps", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simul_lflow_raw_gap_inf_lbmolps"] = float(
                np.asarray(last_eval.diag.get("simul_lflow_raw_gap_inf_lbmolps", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simul_vflow_raw_gap_inf_lbmolps"] = float(
                np.asarray(last_eval.diag.get("simul_vflow_raw_gap_inf_lbmolps", np.asarray([np.nan], dtype=float)), dtype=float)[0]
            )
            row["simultaneous_vapor_target_relax"] = float(solve.vapor_target_relax)
            row["simultaneous_good_vapor_step_streak"] = int(good_vapor_step_streak)
            row["simultaneous_dt_sec"] = float(dt_curr)
            row["simultaneous_state_update_relax"] = float(last_state_update_relax)
            row["simultaneous_t_final_sec"] = float(t_final)
            row["simultaneous_abort_flag"] = int(1 if solve.failed else 0)
            summary_rows.append(row)

            _append_profile_rows(
                rows=profile_rows,
                time_s=t_s,
                stage_results=last_eval.stage_results,
                condenser_state=last_eval.condenser_state,
                reboiler_state=last_eval.reboiler_state,
                spec=spec,
                y=y,
                top_node=last_eval.top_node,
                bottom_node=last_eval.bottom_node,
                liquid_flow=last_eval.liquid_flow,
                vapor_flow=last_eval.vapor_flow,
            )
            if t_s >= float(t_final) - 1.0e-12:
                break
            if bool(solve.failed) or (not np.isfinite(float(inf_norm(solve.evaluation.residual)))):
                break

            z = _blend_next_seed(
                z_prev=z_seed_in,
                z_new=np.asarray(solve.z, dtype=float),
                spec=spec,
                stage_relax=float(stage_seed_relax),
                node_temp_relax=float(node_temp_seed_relax),
                flow_relax=float(flow_seed_relax),
            )
            if bool(adaptive_vapor_target):
                try:
                    vflow_scaled_inf_now = float(
                        np.asarray(
                            last_eval.diag.get("simul_vflow_scaled_inf", np.asarray([np.nan], dtype=float)),
                            dtype=float,
                        ).reshape((-1,))[0]
                    )
                except Exception:
                    vflow_scaled_inf_now = float("nan")
                if bool(solve.converged) and np.isfinite(vflow_scaled_inf_now) and vflow_scaled_inf_now <= 1.0:
                    good_vapor_step_streak += 1
                else:
                    good_vapor_step_streak = 0
                vapor_target_relax_curr = _adapt_vapor_target_relax(
                    current_relax=float(solve.vapor_target_relax),
                    solve=solve,
                    min_relax=float(vapor_target_relax_min),
                    max_relax=float(vapor_target_relax_max),
                    allow_increase=bool(good_vapor_step_streak >= max(int(vapor_reopen_streak_required), 1)),
                )

            if bool(adaptive_dt):
                dt_curr, good_dt_step_streak = _adapt_simultaneous_dt(
                    current_dt=float(dt_curr),
                    solve=solve,
                    dt_min=float(dt_min_eff),
                    dt_max=float(dt_max_eff),
                    good_step_streak=int(good_dt_step_streak),
                    grow_streak_required=int(dt_grow_streak_required),
                )
            dt_use = float(min(dt_curr, max(float(t_final) - float(t_s), 0.0)))
            if dt_use <= 0.0:
                break
            preview_seed = np.asarray(z, dtype=float).copy()
            accepted_step, y_trial, preview_solve, dt_used, state_update_relax = _attempt_preview_step(
                provider=provider,
                spec=spec,
                y=y,
                dydt=np.asarray(dydt, dtype=float),
                z_seed=preview_seed,
                dt_use=float(dt_use),
                dt_min=float(dt_min_eff),
                max_iter=int(max_iter),
                residual_tol=float(residual_tol),
                jac_rel_step=float(jac_rel_step),
                line_search_max=int(line_search_max),
                liquid_target_relax=float(liquid_target_relax),
                vapor_target_relax=float(vapor_target_relax_curr),
                vapor_target_relax_min=float(vapor_target_relax_min),
            )
            if accepted_step and preview_solve is not None:
                y = np.asarray(y_trial, dtype=float).copy()
                prefetched_solve = preview_solve
                t_s = float(t_s) + float(dt_used)
                step += 1
                dt_curr = float(np.clip(dt_used, dt_min_eff, dt_max_eff))
                last_state_update_relax = float(state_update_relax)
            else:
                dt_curr = float(np.clip(dt_used, dt_min_eff, dt_max_eff))
            if not accepted_step or step >= int(max_total_steps):
                break

        logs_root = Path(logs_dir) if logs_dir is not None else Path("sandbox") / "mini8" / "runs"
        run_id = _timestamp_tag()
        summary_path = logs_root / f"uv_flash_simul_summary_{run_id}.csv"
        profile_path = logs_root / f"uv_flash_simul_profile_{run_id}.csv"
        if write_csv:
            _write_csv(summary_path, summary_rows)
            _write_csv(profile_path, profile_rows)
            if reference_profile_csv:
                compare_outputs = compare_uv_run_to_reference(
                    uv_profile_csv=str(profile_path),
                    reference_profile_csv=str(reference_profile_csv),
                    out_dir=str(logs_root),
                    run_id=f"simul_{run_id}",
                )

        return {
            "run_id": str(run_id),
            "excel_path": str(excel_path),
            "thermo_mode": str(thermo_mode_used),
            "n_steps": int(step),
            "dt_sec": float(dt_base),
            "t_final_sec": float(t_final),
            "summary_csv": str(summary_path) if write_csv else "",
            "profile_csv": str(profile_path) if write_csv else "",
            "compare_detail_csv": compare_outputs.get("detail_csv", ""),
            "compare_metrics_csv": compare_outputs.get("metrics_csv", ""),
            "summary_rows": summary_rows,
            "profile_rows": profile_rows,
            "last_evaluation": last_eval,
            "last_solve": last_solve,
        }
    finally:
        if hasattr(provider, "close") and callable(getattr(provider, "close")):
            try:
                provider.close()
            except Exception:
                pass


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the simultaneous mini8 UV-flash sandbox prototype.")
    p.add_argument(
        "--excel",
        dest="excel_path",
        default=r"sandbox/mini8/input/distillation_column_template_8stage.xlsx",
        help="Path to the sandbox workbook.",
    )
    p.add_argument("--n-steps", dest="n_steps", type=int, default=5)
    p.add_argument("--dt", dest="dt_sec", type=float, default=None)
    p.add_argument("--logs-dir", dest="logs_dir", default=None)
    p.add_argument(
        "--thermo",
        dest="thermo_mode",
        choices=["auto", "dwsim", "table", "table-pool"],
        default="auto",
    )
    p.add_argument("--thermo-table", dest="thermo_table_path", default=r"cache\thermo_table.json")
    p.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=None)
    p.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    p.add_argument("--compare-ref-profile", dest="reference_profile_csv", default=None)
    p.add_argument("--max-iter", dest="max_iter", type=int, default=8)
    p.add_argument("--residual-tol", dest="residual_tol", type=float, default=1.0e-6)
    p.add_argument("--jac-rel-step", dest="jac_rel_step", type=float, default=1.0e-6)
    p.add_argument("--line-search-max", dest="line_search_max", type=int, default=6)
    p.add_argument("--stage-seed-relax", dest="stage_seed_relax", type=float, default=0.9)
    p.add_argument("--node-temp-seed-relax", dest="node_temp_seed_relax", type=float, default=0.8)
    p.add_argument("--flow-seed-relax", dest="flow_seed_relax", type=float, default=0.25)
    p.add_argument("--liquid-target-relax", dest="liquid_target_relax", type=float, default=1.0)
    p.add_argument("--vapor-target-relax", dest="vapor_target_relax", type=float, default=0.25)
    p.add_argument("--adaptive-vapor-target", dest="adaptive_vapor_target", action="store_true")
    p.add_argument("--no-adaptive-vapor-target", dest="adaptive_vapor_target", action="store_false")
    p.add_argument("--vapor-target-relax-min", dest="vapor_target_relax_min", type=float, default=0.05)
    p.add_argument("--vapor-target-relax-max", dest="vapor_target_relax_max", type=float, default=1.0)
    p.add_argument("--vapor-reopen-streak-required", dest="vapor_reopen_streak_required", type=int, default=3)
    p.add_argument("--adaptive-dt", dest="adaptive_dt", action="store_true")
    p.add_argument("--no-adaptive-dt", dest="adaptive_dt", action="store_false")
    p.add_argument("--dt-min", dest="dt_min_sec", type=float, default=None)
    p.add_argument("--dt-max", dest="dt_max_sec", type=float, default=None)
    p.add_argument("--dt-grow-streak-required", dest="dt_grow_streak_required", type=int, default=2)
    p.add_argument("--max-total-steps", dest="max_total_steps", type=int, default=500)
    p.add_argument("--no-write-csv", dest="write_csv", action="store_false")
    p.set_defaults(write_csv=True, adaptive_vapor_target=True, adaptive_dt=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    out = run_mini8_uv_flash_simultaneous_prototype(
        excel_path=str(args.excel_path),
        n_steps=args.n_steps,
        dt_sec=args.dt_sec,
        logs_dir=args.logs_dir,
        write_csv=bool(args.write_csv),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=str(args.thermo_table_path),
        thermo_pool_workers=args.thermo_pool_workers,
        thermo_pool_chunk_size=int(args.thermo_pool_chunk_size),
        reference_profile_csv=args.reference_profile_csv,
        max_iter=int(args.max_iter),
        residual_tol=float(args.residual_tol),
        jac_rel_step=float(args.jac_rel_step),
        line_search_max=int(args.line_search_max),
        stage_seed_relax=float(args.stage_seed_relax),
        node_temp_seed_relax=float(args.node_temp_seed_relax),
        flow_seed_relax=float(args.flow_seed_relax),
        liquid_target_relax=float(args.liquid_target_relax),
        vapor_target_relax=float(args.vapor_target_relax),
        adaptive_vapor_target=bool(args.adaptive_vapor_target),
        vapor_target_relax_min=float(args.vapor_target_relax_min),
        vapor_target_relax_max=float(args.vapor_target_relax_max),
        vapor_reopen_streak_required=int(args.vapor_reopen_streak_required),
        adaptive_dt=bool(args.adaptive_dt),
        dt_min_sec=args.dt_min_sec,
        dt_max_sec=args.dt_max_sec,
        dt_grow_streak_required=int(args.dt_grow_streak_required),
        max_total_steps=int(args.max_total_steps),
    )
    last_solve = out.get("last_solve")
    if last_solve is not None:
        print(
            "simultaneous mini8:",
            f"run_id={out['run_id']}",
            f"iters={int(last_solve.iterations)}",
            f"converged={int(1 if last_solve.converged else 0)}",
            f"failed={int(1 if last_solve.failed else 0)}",
            f"alg_inf={inf_norm(last_solve.evaluation.residual):.6g}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
