"""
dynamic_run_scaffold_v1.py

Dynamic Distillation - Simulation Runner and CLI

PURPOSE
-------
Execute end-to-end dynamic column runs: case load/build/validation,
state initialization/startup conditioning, controller updates, time
integration (explicit/stiff-implicit), diagnostics/logging, and
experiment-ledger registration.

INPUTS
------
RunnerConfig (main runtime configuration), including:
- case/log settings: excel_path, n_steps, dt_sec, log_every_n_steps, logs_dir
- model toggles: include_temperature, include_energy, equilibrium relaxation
- thermo settings: thermo_mode (stub/dwsim/table/table-pool), refresh cadence,
  optional refresh thresholds, thermo table/cache/pool settings
- boundary/control overrides: reflux/boilup, duty modes, level/pressure/
  composition controller options, PSV options, top-drum volume settings

OUTPUTS
-------
run_smoke_simulation(cfg) returns a dict with run artifacts and runtime state,
including summary/profile CSV paths, validation status, final state/time,
last diagnostics, and startup initialization diagnostics.

CLI (`python -m dynamic_distillation.dynamic_run_scaffold_v1`) parses
arguments into RunnerConfig and writes CSV outputs when logging is enabled.

KEY DEPENDENCIES
----------------
- excel_case_loader_v1 / column_spec_builder_v1 / excel_case_validator_v1
- state_vector_layout_v1 / column_rhs_v1
- thermo_provider_v1 / thermo_surrogate_v1 / thermo_table_pool_v1
- experiment_ledger_v1 (duplicate-command guard + ledger refresh)

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Default integrator is explicit Euler; optional stiff solvers are available
  when SciPy is installed.
- Excel case must be loadable and pass blocking validation checks.
- Thermo mode and required assets must be consistent (e.g., table path).
- This runner prioritizes diagnostic transparency and workflow reproducibility.

NOTES / CURRENT BEHAVIOR
------------------------
- Supports startup thermo-consistent conditioning and top-drum startup steadying.
- Supports pressure, level, distillate-composition, and bottoms-composition PI loops.
- Supports top-drum PSV vent diagnostics and mass-closure diagnostics.
- Auto-registers logged runs and rebuilds experiment ledger artifacts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import csv
import datetime as _dt
import time

import numpy as np
try:
    from scipy.integrate import solve_ivp as _solve_ivp
except Exception:  # pragma: no cover - optional dependency
    _solve_ivp = None

from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel, CaseData
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case, ColumnSpec
from dynamic_distillation.excel_case_validator_v1 import validate_loaded_case, print_validation_report
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.column_rhs_v1 import (
    BoundaryFlows,
    ColumnInputs,
    VolumeModel,
    column_rhs,
)
from dynamic_distillation.dae_pilot_v1 import (
    default_algebraic_seed,
    evaluate_pilot_residual,
    finite_difference_jacobian,
    inf_norm,
)
from dynamic_distillation.experiment_ledger_v1 import (
    append_run_registry_entry,
    compose_cli_command,
    compose_cli_command_identity,
    find_exact_command_matches,
    rebuild_experiment_ledger,
)


# -------------------------
# Small helpers
# -------------------------


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _normalize_comp(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=float).reshape((-1,))
    s = float(np.sum(z))
    if not np.isfinite(s) or s <= 0.0:
        n = z.size
        return np.full(n, 1.0 / max(n, 1), dtype=float)
    return z / s


def _get_first_mapping_value(d: Dict[str, Any], keys: Sequence[str]) -> Optional[Any]:
    for k in keys:
        if k in d:
            return d[k]
    return None


def _as_float(x: Any) -> Optional[float]:
    try:
        v = float(x)
        return v
    except Exception:
        return None


def _as_int(x: Any) -> Optional[int]:
    try:
        return int(float(x))
    except Exception:
        return None


def _mapping_scalar(d: Dict[str, Any], key: str, default: float = np.nan) -> float:
    """Best-effort extraction of a scalar float from a mapping entry."""
    if key not in d:
        return float(default)
    try:
        val = float(np.asarray(d[key], dtype=float).reshape((-1,))[0])
        return float(val)
    except Exception:
        return float(default)


def _linear_trend_slope_per_s(times_s: Sequence[float], values: Sequence[float]) -> float:
    """Least-squares slope estimate d(value)/dt over a time window."""
    if len(times_s) != len(values):
        return float("nan")
    if len(times_s) < 2:
        return float("nan")
    t = np.asarray(times_s, dtype=float).reshape((-1,))
    v = np.asarray(values, dtype=float).reshape((-1,))
    mask = np.isfinite(t) & np.isfinite(v)
    if np.sum(mask) < 2:
        return float("nan")
    t = t[mask]
    v = v[mask]
    if t.size < 2:
        return float("nan")
    t0 = t - float(np.mean(t))
    v0 = v - float(np.mean(v))
    denom = float(np.dot(t0, t0))
    if denom <= 1e-18:
        dt = float(t[-1] - t[0])
        if abs(dt) <= 1e-18:
            return float("nan")
        return float((v[-1] - v[0]) / dt)
    return float(np.dot(t0, v0) / denom)


def _max_rel_inventory_rate_per_s(
    layout: StateVectorLayout,
    y: np.ndarray,
    dydt: np.ndarray,
    *,
    denom_floor_lbmol: float = 1.0,
) -> float:
    """
    Maximum relative rate |dM/dt|/(|M|+denom_floor) over inventory states.
    """
    floor = float(denom_floor_lbmol)
    if (not np.isfinite(floor)) or floor < 0.0:
        floor = 1.0
    u = layout.unpack(np.asarray(y, dtype=float).reshape((-1,)))
    ud = layout.unpack(np.asarray(dydt, dtype=float).reshape((-1,)))
    keys = ("tray_L", "tray_V", "top_L", "top_V", "bottom_L", "bottom_V")
    max_rel = np.nan
    for key in keys:
        if key not in u or key not in ud:
            continue
        try:
            x = np.asarray(u[key], dtype=float).reshape((-1,))
            dx = np.asarray(ud[key], dtype=float).reshape((-1,))
        except Exception:
            continue
        n = min(x.size, dx.size)
        if n <= 0:
            continue
        x = x[:n]
        dx = dx[:n]
        denom = np.abs(x) + float(floor)
        rel = np.abs(dx) / np.maximum(denom, 1e-300)
        rel_f = rel[np.isfinite(rel)]
        if rel_f.size <= 0:
            continue
        cand = float(np.max(rel_f))
        if (not np.isfinite(max_rel)) or cand > max_rel:
            max_rel = cand
    return float(max_rel)


def _max_rel_inventory_fd_rate_per_s(
    layout: StateVectorLayout,
    y_prev: np.ndarray,
    y_now: np.ndarray,
    *,
    dt_sec: float,
    denom_floor_lbmol: float = 1.0,
) -> float:
    """
    Maximum relative inventory rate estimated by finite differences:
    |(x_now-x_prev)/dt| / (|x_now| + denom_floor).
    """
    try:
        dt = float(dt_sec)
    except Exception:
        return float("nan")
    if (not np.isfinite(dt)) or dt <= 0.0:
        return float("nan")

    floor = float(denom_floor_lbmol)
    if (not np.isfinite(floor)) or floor < 0.0:
        floor = 1.0

    u_prev = layout.unpack(np.asarray(y_prev, dtype=float).reshape((-1,)))
    u_now = layout.unpack(np.asarray(y_now, dtype=float).reshape((-1,)))
    keys = ("tray_L", "tray_V", "top_L", "top_V", "bottom_L", "bottom_V")
    max_rel = np.nan
    for key in keys:
        if key not in u_prev or key not in u_now:
            continue
        try:
            x0 = np.asarray(u_prev[key], dtype=float).reshape((-1,))
            x1 = np.asarray(u_now[key], dtype=float).reshape((-1,))
        except Exception:
            continue
        n = min(x0.size, x1.size)
        if n <= 0:
            continue
        x0 = x0[:n]
        x1 = x1[:n]
        rate = (x1 - x0) / dt
        denom = np.abs(x1) + float(floor)
        rel = np.abs(rate) / np.maximum(denom, 1e-300)
        rel_f = rel[np.isfinite(rel)]
        if rel_f.size <= 0:
            continue
        cand = float(np.max(rel_f))
        if (not np.isfinite(max_rel)) or cand > max_rel:
            max_rel = cand
    return float(max_rel)


def _max_abs_temperature_fd_rate_per_s(
    layout: StateVectorLayout,
    y_prev: np.ndarray,
    y_now: np.ndarray,
    *,
    dt_sec: float,
) -> float:
    """Maximum absolute finite-difference tray temperature rate (F/s)."""
    try:
        dt = float(dt_sec)
    except Exception:
        return float("nan")
    if (not np.isfinite(dt)) or dt <= 0.0:
        return float("nan")

    u_prev = layout.unpack(np.asarray(y_prev, dtype=float).reshape((-1,)))
    u_now = layout.unpack(np.asarray(y_now, dtype=float).reshape((-1,)))
    # Steady-state criterion is defined on tray temperatures only.
    keys = ("tray_T_f",)
    max_rate = np.nan
    for key in keys:
        if key not in u_prev or key not in u_now:
            continue
        try:
            t0 = np.asarray(u_prev[key], dtype=float).reshape((-1,))
            t1 = np.asarray(u_now[key], dtype=float).reshape((-1,))
        except Exception:
            continue
        n = min(t0.size, t1.size)
        if n <= 0:
            continue
        rate = np.abs((t1[:n] - t0[:n]) / dt)
        rate_f = rate[np.isfinite(rate)]
        if rate_f.size <= 0:
            continue
        cand = float(np.max(rate_f))
        if (not np.isfinite(max_rate)) or cand > max_rate:
            max_rate = cand
    return float(max_rate)


# -------------------------
# Stream extraction for logs
# -------------------------


@dataclass(frozen=True)
class StreamTag:
    name: str
    flow_lbmolph: Optional[float]
    stage_1based: Optional[int]


@dataclass
class PIController:
    kc: float
    ti_sec: float
    bias: float
    out_min: float
    out_max: float
    integ: float = 0.0


def _as_bool(x: Any) -> Optional[bool]:
    if isinstance(x, bool):
        return x
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return None


def _pi_update(
    controller: PIController,
    *,
    pv: float,
    sp: float,
    dt_sec: float,
    out_min: Optional[float] = None,
    out_max: Optional[float] = None,
) -> float:
    """
    One-step PI with anti-windup (conditional integration).
    """
    e = float(pv) - float(sp)
    if not np.isfinite(e):
        e = 0.0
    if not np.isfinite(controller.kc):
        controller.kc = 0.0
    if not np.isfinite(controller.ti_sec) or controller.ti_sec <= 0.0:
        controller.ti_sec = 1e12
    if not np.isfinite(controller.integ):
        controller.integ = 0.0

    umin = float(controller.out_min if out_min is None else out_min)
    umax = float(controller.out_max if out_max is None else out_max)
    if not np.isfinite(umin):
        umin = float(controller.out_min)
    if not np.isfinite(umax):
        umax = float(controller.out_max)
    if umax < umin:
        umax = umin

    # Tentative unclamped output
    i_next = controller.integ + e * float(dt_sec) / max(float(controller.ti_sec), 1e-9)
    u_unclamped = float(controller.bias) + float(controller.kc) * (e + i_next)
    u = float(np.clip(u_unclamped, umin, umax))

    # Anti-windup: accept integrator update only when output is unsaturated,
    # or integration would move the output back toward the unsaturated region.
    # This must account for gain sign (reverse-acting loops use negative Kc).
    sat_hi = u_unclamped > umax + 1e-12
    sat_lo = u_unclamped < umin - 1e-12
    du_from_int = float(controller.kc) * float(e)
    allow_int = (not sat_hi and not sat_lo) or (sat_hi and du_from_int < 0.0) or (sat_lo and du_from_int > 0.0)
    if allow_int:
        controller.integ = float(i_next)
        u = float(np.clip(float(controller.bias) + float(controller.kc) * (e + controller.integ), umin, umax))
    return u


def _pressure_resid_gain_scale(
    *,
    resid_abs_btups: Optional[float],
    resid_ref_btups: Optional[float],
    min_gain: float = 0.25,
) -> float:
    """
    Map a pressure-loop energy residual magnitude to a PI gain scale in [min_gain, 1].
    """
    if resid_ref_btups is None:
        return 1.0
    try:
        ref = float(resid_ref_btups)
    except Exception:
        return 1.0
    if (not np.isfinite(ref)) or ref <= 0.0:
        return 1.0

    try:
        resid = float(resid_abs_btups) if resid_abs_btups is not None else np.nan
    except Exception:
        resid = np.nan
    if (not np.isfinite(resid)) or resid <= 0.0:
        return 1.0

    g_min = float(np.clip(float(min_gain), 0.0, 1.0))
    g = 1.0 / (1.0 + (resid / ref))
    if not np.isfinite(g):
        return 1.0
    return float(np.clip(g, g_min, 1.0))


def _apply_slew_limit(
    *,
    cmd: float,
    prev_cmd: Optional[float],
    rate_limit_per_s: Optional[float],
    dt_sec: float,
) -> float:
    """
    Symmetric rate limiter: |cmd - prev_cmd| <= rate_limit_per_s * dt_sec.
    """
    try:
        u = float(cmd)
    except Exception:
        return cmd
    if not np.isfinite(u):
        return u
    if prev_cmd is None or rate_limit_per_s is None:
        return u
    try:
        u_prev = float(prev_cmd)
        r = float(rate_limit_per_s)
        dt = float(dt_sec)
    except Exception:
        return u
    if (not np.isfinite(u_prev)) or (not np.isfinite(r)) or (not np.isfinite(dt)):
        return u
    if r <= 0.0 or dt <= 0.0:
        return u
    du_max = abs(r) * dt
    return float(np.clip(u, u_prev - du_max, u_prev + du_max))


def _extract_stream_from_obj_or_dict(obj: Any) -> Tuple[Optional[float], Optional[int]]:
    """
    Extract (total_molar_flow_lbmolph, stage_1based) from either:
      - an object with attributes
      - a dict with known keys
    """
    if obj is None:
        return (None, None)

    # object-like
    flow = None
    stage = None
    for attr in ("total_molar_flow_lbmolph", "flow_lbmolph", "flow", "TotalMolarFlow"):
        if hasattr(obj, attr):
            flow = _as_float(getattr(obj, attr))
            if flow is not None:
                break
    for attr in ("stage_1based", "stage", "Stage", "StageNumber"):
        if hasattr(obj, attr):
            stage = _as_int(getattr(obj, attr))
            if stage is not None:
                break

    # dict-like
    if isinstance(obj, dict):
        flow = flow if flow is not None else _as_float(
            _get_first_mapping_value(
                obj,
                (
                    "total_molar_flow_lbmolph",
                    "Total Molar Flow (lbmol/h)",
                    "Total Flow (lbmol/h)",
                    "flow_lbmolph",
                    "flow",
                ),
            )
        )
        stage = stage if stage is not None else _as_int(
            _get_first_mapping_value(
                obj,
                (
                    "stage_1based",
                    "Stage (1-based)",
                    "Stage",
                    "stage",
                ),
            )
        )

    return (flow, stage)


def _lookup_named_stream(
    *,
    col: ColumnSpec,
    case: CaseData,
    aliases: Sequence[str],
) -> StreamTag:
    """
    Find a stream by name (case-insensitive match against aliases).
    Searches ColumnSpec.streams first, then CaseData.streams.
    Returns StreamTag(name, flow_lbmolph, stage_1based).
    """
    alias_lc = [str(a).strip().lower() for a in aliases if str(a).strip()]
    alias_clean = [''.join(ch for ch in a if ch.isalnum()) for a in alias_lc]
    if not alias_lc:
        return StreamTag(name=str(aliases[0]) if aliases else "stream", flow_lbmolph=None, stage_1based=None)

    def match(nm: str) -> bool:

        nmlc = str(nm).strip().lower()

        def _clean(s: str) -> str:
            # Keep only [a-z0-9] to make comparisons robust to spaces, dashes, etc.
            return ''.join(ch for ch in s.lower() if ch.isalnum())

        nmc = _clean(nmlc)

        # 1) Exact match (strict) on both raw and cleaned forms
        if nmlc in alias_lc or nmc in alias_clean:
            return True

        # 2) Relaxed matching ONLY for non-trivial aliases.
        # Short aliases (e.g. "D", "B") must be exact; otherwise they can match "FeeD", "Bottoms", etc.
        for a_raw, a_clean in zip(alias_lc, alias_clean):
            if len(a_clean) < 3:
                continue
            if nmc.startswith(a_clean):
                return True
        for a_raw, a_clean in zip(alias_lc, alias_clean):
            if len(a_clean) < 3:
                continue
            if a_clean in nmc:
                return True
        return False

    # 1) ColumnSpec.streams
    streams = getattr(col, "streams", None)
    if isinstance(streams, dict):
        for nm, obj in streams.items():
            if match(str(nm)):
                f, st = _extract_stream_from_obj_or_dict(obj)
                return StreamTag(name=str(nm), flow_lbmolph=f, stage_1based=st)

    # 2) CaseData.streams
    streams2 = getattr(case, "streams", None)
    if isinstance(streams2, dict):
        for nm, obj in streams2.items():
            if match(str(nm)):
                f, st = _extract_stream_from_obj_or_dict(obj)
                return StreamTag(name=str(nm), flow_lbmolph=f, stage_1based=st)

    return StreamTag(name=str(aliases[0]), flow_lbmolph=None, stage_1based=None)


def _lookup_spec_int(col: ColumnSpec, keys: Sequence[str]) -> Optional[int]:
    d = getattr(col, "specs_raw", None)
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d:
            v = _as_int(d[k])
            if v is not None:
                return v
    return None


def _stage_value(i_1based: int, target_stage_1based: Optional[int], value: Optional[float]) -> float:
    """
    Returns value on the target stage, else 0.0.
    If target stage exists but value missing -> NaN (signals incomplete stream spec).
    """
    if target_stage_1based is None:
        return 0.0
    if int(i_1based) != int(target_stage_1based):
        return 0.0
    return float(value) if value is not None else float("nan")


# -------------------------
# Thermo provider stub
# -------------------------


class StubThermoProvider:
    """Deterministic stub provider.

    stage_thermo_v1.flash_TP_full_F_psia() accepts tuple/list:
      (x, y, K, HL, HV) or (x, y, K, HL, HV, Z)
    """

    def __init__(self, K: Sequence[float], Z: float = 1.0):
        self._K = np.asarray(K, dtype=float).ravel()
        self._Z = float(Z)

    def flash_TP_full_F_psia(self, T_F: float, P_psia: float, z: List[float]):
        z_arr = _normalize_comp(np.asarray(z, dtype=float))
        K = self._K.copy()
        x = z_arr
        y = _normalize_comp(K * x)
        HL = 0.0
        HV = 0.0
        return (x.tolist(), y.tolist(), K.tolist(), HL, HV, float(self._Z))

    def flash_TP_full(self, T_F: float, P_psia: float, z: List[float]):
        return self.flash_TP_full_F_psia(T_F, P_psia, z)

    def liquid_density_lbmol_ft3(self, T_F: float, P_psia: float, x: List[float]) -> float:
        # Simple stub: constant density to keep hydraulics running in stub mode.
        return 1.0

    def cp_liq_vap_btu_per_lbmolF(self, T_F: float, P_psia: float, z: List[float]):
        # Simple stub: constant Cp values to keep energy balance running in stub mode.
        return (30.0, 20.0)


# -------------------------
# Runner config
# -------------------------


@dataclass(frozen=True)
class RunnerConfig:
    excel_path: str
    n_steps: int = 600
    dt_sec: Optional[float] = None
    log_every_n_steps: Optional[int] = None
    runtime_mode: str = "legacy"  # legacy | parity | calibration | hydraulic
    integrator: str = "explicit-euler"  # explicit-euler | bdf | radau | ida
    integrator_rtol: float = 1.0e-3
    integrator_atol: float = 1.0e-6
    integrator_max_step_sec: Optional[float] = None
    integrator_substep_sec: Optional[float] = None
    integrator_max_rhs_evals_per_step: Optional[int] = 24
    integrator_step_wall_limit_sec: Optional[float] = 15.0
    ida_max_iter: int = 8
    ida_relax: float = 1.0

    include_temperature: bool = True
    include_energy: bool = False
    enable_equilibrium_relaxation: bool = True
    equilibrium_relaxation_mode: str = "auto"  # auto | phase-holdup | composition-only

    thermo_mode: str = "stub"  # 'stub', 'dwsim', 'table', or 'table-pool'
    thermo_every_n_steps: int = 1  # 1=every step
    thermo_refresh_dT_F: Optional[float] = None
    thermo_refresh_dP_psia: Optional[float] = None
    thermo_refresh_dx: Optional[float] = None
    thermo_table_path: Optional[str] = None
    thermo_pool_workers: Optional[int] = None
    thermo_pool_chunk_size: int = 4
    thermo_pool_task_timeout_sec: Optional[float] = None
    reboiler_neighbor_vflow_hi_ratio: Optional[float] = None
    reboiler_neighbor_vflow_lo_ratio: Optional[float] = None
    vapor_holdup_relaxation_sec: Optional[float] = None
    hydraulic_pressure_relaxation_sec: Optional[float] = None
    top_drum_pressure_temperature_relaxation_sec: Optional[float] = None
    vapor_flow_relaxation_sec: Optional[float] = None
    conductance_vflow_nominal_hi_ratio: Optional[float] = None
    # Optional smooth-clamp width (lbmol/h) used only for stiff integrator RHS
    # regularization in hydraulic vapor-flow closures.
    # None -> auto (small default in stiff hydraulic runs), <=0 disables.
    stiff_vflow_smooth_clamp_lbmolph: Optional[float] = None
    pv_inner_max_iter: int = 1
    pv_inner_p_tol_psia: Optional[float] = 0.05
    pv_inner_v_tol_lbmolph: Optional[float] = 25.0
    enable_dae_pilot_algebraic_solve: bool = False
    dae_pilot_max_iter: int = 3
    dae_pilot_p_tol_psia: Optional[float] = 0.05
    dae_pilot_v_tol_lbmolph: Optional[float] = 25.0
    dae_pilot_jac_rel_step: float = 1.0e-6
    dae_pilot_line_search_max: int = 4
    enable_liquid_hydraulic_override: Optional[bool] = None
    liquid_hydraulic_override_alpha: Optional[float] = None

    reflux_lbmolph: Optional[float] = None
    boilup_lbmolph: Optional[float] = None
    condenser_duty_mode: str = "total-condense"
    condenser_duty_btu_per_h: Optional[float] = None
    condenser_duty_trim_btu_per_h: Optional[float] = None
    condenser_pressure_drop_psi: Optional[float] = None
    top_drum_vapor_volume_ft3: Optional[float] = None
    top_drum_total_volume_ft3: Optional[float] = None
    enforce_top_drum_pressure_gate: bool = True
    top_drum_pressure_gate_soft_psi: Optional[float] = 0.25
    enforce_top_pressure_ordering: bool = True
    top_pressure_ordering_margin_psi: float = 0.0
    enable_top_psv: bool = False
    top_psv_setpoint_psia: Optional[float] = None
    top_psv_gain_lbmolps_per_psi: Optional[float] = None
    top_psv_max_vent_lbmolps: Optional[float] = None
    enable_level_control: bool = False
    top_level_sp_lbmol: Optional[float] = None
    bottom_level_sp_lbmol: Optional[float] = None
    top_level_kc: Optional[float] = None
    top_level_ti_sec: Optional[float] = None
    bottom_level_kc: Optional[float] = None
    bottom_level_ti_sec: Optional[float] = None
    enable_pressure_control: bool = False
    pressure_control_mv: str = "auto"  # auto|condenser-duty|top-anchor
    allow_coupled_pressure_duty: bool = False
    top_pressure_sp_psia: Optional[float] = None
    top_pressure_kc: Optional[float] = None
    top_pressure_ti_sec: Optional[float] = None
    top_pressure_pv_filter_tau_sec: Optional[float] = None
    top_pressure_mv_slew_limit_per_s: Optional[float] = None
    top_pressure_resid_ref_btups: Optional[float] = None
    top_pressure_resid_min_gain: float = 0.25
    condenser_duty_min_btu_per_h: Optional[float] = None
    condenser_duty_max_btu_per_h: Optional[float] = None
    top_pressure_anchor_min_psia: Optional[float] = None
    top_pressure_anchor_max_psia: Optional[float] = None
    enable_distillate_composition_control: bool = False
    distillate_composition_component: str = "C4"
    distillate_composition_sp_molfrac: Optional[float] = None
    distillate_composition_kc: Optional[float] = None
    distillate_composition_ti_sec: Optional[float] = None
    reflux_cmd_min_lbmolph: Optional[float] = None
    reflux_cmd_max_lbmolph: Optional[float] = None
    enable_reflux_feasibility_cap: bool = True
    reflux_ratio_min: Optional[float] = None
    reflux_ratio_max: Optional[float] = None
    enable_bottoms_composition_control: bool = False
    bottoms_composition_component: str = "C5"
    bottoms_composition_sp_molfrac: Optional[float] = None
    bottoms_composition_kc: Optional[float] = None
    bottoms_composition_ti_sec: Optional[float] = None
    bottoms_composition_mv: str = "boilup"  # boilup|reboiler-duty
    boilup_cmd_min_lbmolph: Optional[float] = None
    boilup_cmd_max_lbmolph: Optional[float] = None
    reboiler_duty_cmd_min_btu_per_h: Optional[float] = None
    reboiler_duty_cmd_max_btu_per_h: Optional[float] = None
    reboiler_duty_btu_per_h: Optional[float] = None

    logs_dir: str = "logs"
    write_logs: bool = True
    use_excel_vapor_holdup: bool = False
    enable_startup_thermo_conditioning: bool = True
    startup_thermo_conditioning_iters: int = 2
    startup_thermo_conditioning_relaxation: float = 1.0
    enable_startup_hydraulic_sequence: bool = False
    startup_sequence_energy_on_sec: float = 30.0
    startup_sequence_liquid_on_sec: float = 120.0
    startup_sequence_liquid_ramp_sec: float = 180.0
    startup_sequence_mass_resid_gate_lbmolph: Optional[float] = 250.0
    startup_sequence_liquid_backoff_sec: Optional[float] = None

    # Runtime steady-state detector (diagnostic-only)
    enable_steady_state_detection: bool = True
    steady_state_window_sec: float = 30.0
    steady_state_min_time_sec: float = 60.0
    steady_state_rel_state_rate_tol_per_s: Optional[float] = 3.0e-3
    steady_state_kpi_slope_tol_per_s: Optional[float] = 1.0e-4
    steady_state_mv_rate_tol_per_s: Optional[float] = 20.0
    steady_state_temp_rate_tol_F_per_s: Optional[float] = 0.15
    steady_state_sp_error_tol: Optional[float] = 0.02
    steady_state_require_sp: bool = False
    steady_state_rate_denom_floor_lbmol: float = 1.0


# -------------------------
# Boundary + volume model
# -------------------------


def _case_stream_lookup(case: CaseData, name: str) -> Optional[Dict[str, Any]]:
    if not getattr(case, "streams", None) or not isinstance(case.streams, dict):
        return None
    target = name.strip().lower()
    for k, v in case.streams.items():
        if str(k).strip().lower() == target:
            return v if isinstance(v, dict) else None
    return None


def _stream_total_flow_lbmolph(stream: Dict[str, Any]) -> Optional[float]:
    for key in (
        "Total Molar Flow (lbmol/h)",
        "total molar flow (lbmol/h)",
        "total_molar_flow_lbmolph",
        "Total Flow (lbmol/h)",
    ):
        if key in stream:
            try:
                return float(stream[key])
            except Exception:
                return None
    return None


def _infer_boundary_flows(case: CaseData, col: ColumnSpec, cfg: RunnerConfig) -> BoundaryFlows:
    reflux = cfg.reflux_lbmolph
    boilup = cfg.boilup_lbmolph

    if reflux is None:
        s = _case_stream_lookup(case, "Reflux")
        if s is not None:
            reflux = _stream_total_flow_lbmolph(s)

    if boilup is None:
        s = _case_stream_lookup(case, "Boilup")
        if s is not None:
            boilup = _stream_total_flow_lbmolph(s)

    if reflux is None:
        reflux = float(col.L_lbmolph[0])
    if boilup is None:
        boilup = float(col.V_lbmolph[-1])

    return BoundaryFlows(reflux_lbmolph=float(reflux), boilup_lbmolph=float(boilup))


def _build_volume_model(col: ColumnSpec, default_vapor_volume_ft3: float = 1.0) -> VolumeModel:
    vv = None

    # Prefer geometry container
    geom = getattr(col, "geometry", None)
    if geom is not None:
        vv = getattr(geom, "vapor_volume_ft3_per_stage", None)

    # Fallback
    if vv is None:
        vv = getattr(col, "vapor_volume_ft3_per_stage", None)

    if vv is not None:
        vv = np.asarray(vv, dtype=float).reshape((col.n_stages,)).copy()

    return VolumeModel(vapor_volume_ft3_per_stage=vv, default_vapor_volume_ft3=float(default_vapor_volume_ft3))


def _normalize_spec_key(key: str) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _spec_get(specs: Dict[str, Any], key: str, *aliases: str) -> Any:
    if key in specs:
        return specs[key]

    norm_map = {_normalize_spec_key(k): v for k, v in specs.items()}

    norm = _normalize_spec_key(key)
    if norm:
        if norm in norm_map:
            return norm_map[norm]

    for alias in aliases:
        if alias in specs:
            return specs[alias]
        alias_norm = _normalize_spec_key(alias)
        if alias_norm and alias_norm in norm_map:
            return norm_map[alias_norm]
    return None


def _spec_float(specs: Dict[str, Any], key: str, *aliases: str) -> Optional[float]:
    v_raw = _spec_get(specs, key, *aliases)
    if v_raw is None:
        return None
    try:
        v = float(v_raw)
        if not np.isfinite(v):
            return None
        return v
    except Exception:
        return None


def _clip_unit(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except Exception:
        v = float(default)
    if not np.isfinite(v):
        v = float(default)
    return float(np.clip(v, 0.0, 1.0))


def _normalize_runtime_mode(mode: Any, default: str = "legacy") -> str:
    m = str(mode).strip().lower() if mode is not None else str(default).strip().lower()
    if m in ("legacy", "parity", "calibration", "hydraulic"):
        return m
    return str(default).strip().lower()


def _normalize_integrator_mode(mode: Any, default: str = "explicit-euler") -> str:
    m = str(mode).strip().lower().replace("_", "-") if mode is not None else str(default).strip().lower()
    if m in ("explicit", "euler", "explicit-euler"):
        return "explicit-euler"
    if m in ("bdf",):
        return "bdf"
    if m in ("radau",):
        return "radau"
    if m in ("ida", "dae", "simultaneous-dae"):
        return "ida"
    return str(default).strip().lower()


def _normalize_equilibrium_relaxation_mode(mode: Any, default: str = "phase-holdup") -> str:
    m = str(mode).strip().lower().replace("_", "-") if mode is not None else str(default).strip().lower()
    if m in ("", "auto"):
        return str(default).strip().lower()
    if m in ("phase-holdup", "phase", "legacy"):
        return "phase-holdup"
    if m in ("composition-only", "composition", "comp-only", "y-only"):
        return "composition-only"
    return str(default).strip().lower()


def _effective_hydraulic_ida_profile(
    cfg: RunnerConfig,
    *,
    runtime_mode: str,
    integrator_mode: str,
) -> Dict[str, Any]:
    """
    Resolve effective IDA/DAE pilot settings.

    For hydraulic+IDA, apply tuned defaults when legacy defaults are still in
    place, while preserving explicit user overrides.
    """
    try:
        ida_max_iter = int(getattr(cfg, "ida_max_iter", 8))
    except Exception:
        ida_max_iter = 8
    ida_max_iter = max(1, ida_max_iter)

    try:
        dae_pilot_max_iter = int(getattr(cfg, "dae_pilot_max_iter", 3))
    except Exception:
        dae_pilot_max_iter = 3
    dae_pilot_max_iter = max(1, dae_pilot_max_iter)

    dae_pilot_enabled = bool(getattr(cfg, "enable_dae_pilot_algebraic_solve", False))
    dae_pilot_p_tol = getattr(cfg, "dae_pilot_p_tol_psia", None)
    dae_pilot_v_tol = getattr(cfg, "dae_pilot_v_tol_lbmolph", None)
    defaults_applied: List[str] = []

    is_hyd_ida = (
        str(runtime_mode).strip().lower() == "hydraulic"
        and str(integrator_mode).strip().lower() == "ida"
    )
    if is_hyd_ida:
        if not bool(dae_pilot_enabled):
            dae_pilot_enabled = True
            defaults_applied.append("enable_dae_pilot_algebraic_solve=True")
        if int(ida_max_iter) == 8:
            ida_max_iter = 12
            defaults_applied.append("ida_max_iter=12")
        v_try = np.nan
        try:
            if dae_pilot_v_tol is not None:
                v_try = float(dae_pilot_v_tol)
        except Exception:
            v_try = np.nan
        if (dae_pilot_v_tol is None) or ((not np.isfinite(v_try)) or abs(float(v_try) - 25.0) <= 1.0e-12):
            dae_pilot_v_tol = 100.0
            defaults_applied.append("dae_pilot_v_tol_lbmolph=100")

    return {
        "ida_max_iter": int(ida_max_iter),
        "dae_pilot_enabled": bool(dae_pilot_enabled),
        "dae_pilot_max_iter": int(dae_pilot_max_iter),
        "dae_pilot_p_tol_psia": dae_pilot_p_tol,
        "dae_pilot_v_tol_lbmolph": dae_pilot_v_tol,
        "defaults_applied": list(defaults_applied),
    }


def _resolve_startup_hydraulic_sequence_step(
    *,
    t_s: float,
    dt_sec: float,
    base_inputs: ColumnInputs,
    enable_sequence: bool,
    energy_on_sec: float,
    liquid_on_sec: float,
    liquid_ramp_sec: float,
    liquid_resid_gate_lbmolph: Optional[float],
    liquid_backoff_sec: Optional[float],
    liquid_alpha_state: float,
    last_mass_resid_max_lbmolph: Optional[float],
) -> Tuple[str, str, float, str]:
    """
    Runtime startup sequencing:
      1) pressure-only (hydraulic pressure + profile vapor/liquid traffic)
      2) pressure+energy vapor
      3) residual-gated liquid hydraulics ramp
    """
    p_base = str(base_inputs.pressure_model or "spec").strip().lower()
    if p_base not in ("spec", "hydraulic"):
        p_base = "spec"
    v_base = str(base_inputs.vapor_flow_model or "profile").strip().lower()
    if v_base not in ("profile", "energy", "conductance"):
        v_base = "profile"

    liq_enabled = bool(base_inputs.enable_liquid_hydraulic_override)
    liq_alpha_max = _clip_unit(getattr(base_inputs, "liquid_hydraulic_override_alpha", 1.0), default=1.0)
    if (not liq_enabled) or liq_alpha_max <= 0.0:
        liq_enabled = False
        liq_alpha_max = 0.0

    alpha = _clip_unit(liquid_alpha_state, default=liq_alpha_max)
    if (not enable_sequence) or p_base != "hydraulic":
        return p_base, v_base, liq_alpha_max, "base"

    t_now = max(float(t_s), 0.0)
    dt = max(float(dt_sec), 0.0)
    t_energy = max(float(energy_on_sec), 0.0)
    t_liq = max(float(liquid_on_sec), float(t_energy))
    t_ramp = max(float(liquid_ramp_sec), 1e-9)

    p_eff = "hydraulic"
    v_eff = v_base
    if v_base in ("energy", "conductance") and t_now < t_energy:
        v_eff = "profile"

    if (not liq_enabled) or liq_alpha_max <= 0.0:
        alpha = 0.0
    elif t_now < t_liq:
        alpha = 0.0
    else:
        a_time = float(np.clip((t_now - t_liq) / t_ramp, 0.0, 1.0)) * liq_alpha_max
        gate = None
        if liquid_resid_gate_lbmolph is not None:
            try:
                gate_try = float(liquid_resid_gate_lbmolph)
            except Exception:
                gate_try = np.nan
            if np.isfinite(gate_try) and gate_try > 0.0:
                gate = gate_try
        resid = np.nan
        if last_mass_resid_max_lbmolph is not None:
            try:
                resid = float(last_mass_resid_max_lbmolph)
            except Exception:
                resid = np.nan
        above_gate = bool(gate is not None and np.isfinite(resid) and resid > float(gate))
        if above_gate:
            tau_back = liquid_backoff_sec
            if tau_back is None:
                tau_back = 0.5 * t_ramp
            try:
                tau_back = float(tau_back)
            except Exception:
                tau_back = 0.5 * t_ramp
            tau_back = max(tau_back, 1e-9)
            alpha = max(0.0, alpha - (dt / tau_back) * liq_alpha_max)
        else:
            if alpha < a_time:
                alpha = min(a_time, alpha + (dt / t_ramp) * liq_alpha_max)
            else:
                alpha = min(alpha, liq_alpha_max)

    if t_now < t_energy:
        phase = "pressure_only"
    elif t_now < t_liq:
        phase = "pressure_energy"
    else:
        phase = "pressure_energy_liquid_ramp"
    return p_eff, v_eff, _clip_unit(alpha, default=0.0), phase


def build_inputs_for_runner(case: CaseData, col: ColumnSpec, cfg: RunnerConfig) -> Tuple[ColumnInputs, Any]:
    thermo_mode = (cfg.thermo_mode or "").strip().lower()

    if thermo_mode == "dwsim":
        from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1

        prov = ThermoProviderV1(
            component_names_excel=col.components_excel,
            component_ids_dwsim=col.components_dwsim,
            silence_backend_console=True,
        )
    elif thermo_mode == "table":
        if not cfg.thermo_table_path:
            raise ValueError("thermo_mode='table' requires RunnerConfig.thermo_table_path")
        from dynamic_distillation.thermo_surrogate_v1 import TabularThermoProviderV1

        prov = TabularThermoProviderV1.from_json(
            str(cfg.thermo_table_path),
            expected_component_names_excel=col.components_excel,
            expected_component_ids_dwsim=col.components_dwsim,
        )
    elif thermo_mode == "table-pool":
        if not cfg.thermo_table_path:
            raise ValueError("thermo_mode='table-pool' requires RunnerConfig.thermo_table_path")
        from dynamic_distillation.thermo_table_pool_v1 import ParallelTabularThermoProviderV1

        prov = ParallelTabularThermoProviderV1(
            table_path=str(cfg.thermo_table_path),
            expected_component_names_excel=col.components_excel,
            expected_component_ids_dwsim=col.components_dwsim,
            max_workers=cfg.thermo_pool_workers,
            chunk_size=int(cfg.thermo_pool_chunk_size),
            task_timeout_sec=cfg.thermo_pool_task_timeout_sec,
        )
    elif thermo_mode == "stub":
        Nc = int(col.n_components)
        if Nc == 1:
            K = np.array([1.0], dtype=float)
        else:
            K = 2.0 ** (1.0 - np.arange(Nc, dtype=float) / float(Nc - 1))
        prov = StubThermoProvider(K=K, Z=1.0)
    else:
        raise ValueError(
            f"Unsupported thermo_mode: {thermo_mode!r} "
            "(use 'stub', 'dwsim', 'table', or 'table-pool')"
        )

    boundary = _infer_boundary_flows(case, col, cfg)
    vol = _build_volume_model(col, default_vapor_volume_ft3=1.0)

    specs = getattr(col, "specs_raw", None) or {}
    pressure_model = str(_spec_get(specs, "Pressure Model") or "").strip().lower()
    if not pressure_model:
        pressure_model = "hydraulic" if col.geometry is not None else "spec"
    if pressure_model not in ("spec", "hydraulic"):
        pressure_model = "spec"

    vapor_flow_model = str(_spec_get(specs, "Vapor Flow Model") or "").strip().lower()
    if not vapor_flow_model:
        vapor_flow_model = "energy" if pressure_model == "hydraulic" else "profile"
    if vapor_flow_model not in ("profile", "energy", "conductance"):
        vapor_flow_model = "profile"

    runtime_mode = _normalize_runtime_mode(getattr(cfg, "runtime_mode", None), default="legacy")
    if runtime_mode in ("parity", "calibration"):
        pressure_model = "spec"
        vapor_flow_model = "profile"
    elif runtime_mode == "hydraulic":
        pressure_model = "hydraulic"
        vapor_flow_model = "energy"

    eq_mode_default = "composition-only" if runtime_mode == "hydraulic" else "phase-holdup"
    eq_mode_spec = _spec_get(
        specs,
        "Equilibrium Relaxation Mode",
        "Equilibrium Mode",
        "Equilibrium Transfer Mode",
    )
    eq_mode = _normalize_equilibrium_relaxation_mode(
        cfg.equilibrium_relaxation_mode if cfg.equilibrium_relaxation_mode is not None else eq_mode_spec,
        default=eq_mode_default,
    )
    # If CLI left mode at default "auto", fall back to spec/default behavior.
    if str(getattr(cfg, "equilibrium_relaxation_mode", "auto")).strip().lower() in ("", "auto"):
        eq_mode = _normalize_equilibrium_relaxation_mode(eq_mode_spec, default=eq_mode_default)

    coupled_hydraulic_energy = (pressure_model == "hydraulic") and (vapor_flow_model == "energy")

    dry_tray_k = _spec_float(specs, "Dry Tray K")
    if dry_tray_k is None or not np.isfinite(dry_tray_k):
        dry_tray_k = 1.0

    tau_v = _spec_float(specs, "Vapor Holdup Relaxation (sec)")
    if tau_v is None:
        tau_v = _spec_float(specs, "Stage time constant [tau] (sec)")
    if cfg.vapor_holdup_relaxation_sec is not None:
        tau_v = float(cfg.vapor_holdup_relaxation_sec)
    if tau_v is not None and (not np.isfinite(tau_v) or tau_v <= 0.0):
        tau_v = None
    if tau_v is None and coupled_hydraulic_energy:
        # Stabilizing default for explicit integration under hydraulic/energy coupling.
        tau_v = 10.0

    tau_p_hyd = _spec_float(
        specs,
        "Hydraulic Pressure Relaxation (sec)",
        "Pressure Relaxation (sec)",
        "Hydraulic Pressure Tau (sec)",
    )
    if cfg.hydraulic_pressure_relaxation_sec is not None:
        tau_p_hyd = float(cfg.hydraulic_pressure_relaxation_sec)
    if tau_p_hyd is not None and (not np.isfinite(tau_p_hyd) or tau_p_hyd <= 0.0):
        tau_p_hyd = None
    if tau_p_hyd is None:
        # Backward-compatible default behavior: share vapor-holdup timescale.
        tau_p_hyd = tau_v

    tau_top_pT = _spec_float(
        specs,
        "Top Drum Pressure Temperature Relaxation (sec)",
        "Top Drum Pressure Temperature Tau (sec)",
    )
    if cfg.top_drum_pressure_temperature_relaxation_sec is not None:
        tau_top_pT = float(cfg.top_drum_pressure_temperature_relaxation_sec)
    if tau_top_pT is not None and (not np.isfinite(tau_top_pT)):
        tau_top_pT = None

    tau_vflow = _spec_float(specs, "Vapor Flow Relaxation (sec)")
    if cfg.vapor_flow_relaxation_sec is not None:
        tau_vflow = float(cfg.vapor_flow_relaxation_sec)
    if tau_vflow is not None and (not np.isfinite(tau_vflow) or tau_vflow <= 0.0):
        tau_vflow = None

    conductance_vflow_nominal_hi_ratio = _spec_float(
        specs,
        "Conductance Vapor Nominal Hi Ratio",
        "Conductance Vflow Nominal Hi Ratio",
        "Conductance Vapor Profile Hi Ratio",
    )
    if cfg.conductance_vflow_nominal_hi_ratio is not None:
        conductance_vflow_nominal_hi_ratio = float(cfg.conductance_vflow_nominal_hi_ratio)
    if (
        conductance_vflow_nominal_hi_ratio is not None
        and (not np.isfinite(conductance_vflow_nominal_hi_ratio) or conductance_vflow_nominal_hi_ratio <= 0.0)
    ):
        conductance_vflow_nominal_hi_ratio = None

    reb_nbr_hi = _spec_float(
        specs,
        "Reboiler Neighbor Vapor Hi Ratio",
        "Reboiler Neighbor Vflow Hi Ratio",
    )
    reb_nbr_lo = _spec_float(
        specs,
        "Reboiler Neighbor Vapor Lo Ratio",
        "Reboiler Neighbor Vflow Lo Ratio",
    )
    if cfg.reboiler_neighbor_vflow_hi_ratio is not None:
        reb_nbr_hi = float(cfg.reboiler_neighbor_vflow_hi_ratio)
    if cfg.reboiler_neighbor_vflow_lo_ratio is not None:
        reb_nbr_lo = float(cfg.reboiler_neighbor_vflow_lo_ratio)
    if reb_nbr_hi is not None and (not np.isfinite(reb_nbr_hi) or reb_nbr_hi <= 0.0):
        reb_nbr_hi = None
    if reb_nbr_lo is not None and (not np.isfinite(reb_nbr_lo) or reb_nbr_lo <= 0.0):
        reb_nbr_lo = None

    thermo_refresh_dT = _spec_float(
        specs,
        "Thermo Refresh dT (F)",
        "Thermo Refresh Delta T (F)",
        "Thermo Refresh Delta (F)",
        "Thermo Refresh \u0394T (F)",
    )
    thermo_refresh_dP = _spec_float(
        specs,
        "Thermo Refresh dP (psia)",
        "Thermo Refresh Delta P (psia)",
    )
    thermo_refresh_dX = _spec_float(
        specs,
        "Thermo Refresh dX",
        "Thermo Refresh Delta X",
    )

    if cfg.thermo_refresh_dT_F is not None:
        thermo_refresh_dT = float(cfg.thermo_refresh_dT_F)
    if cfg.thermo_refresh_dP_psia is not None:
        thermo_refresh_dP = float(cfg.thermo_refresh_dP_psia)
    if cfg.thermo_refresh_dx is not None:
        thermo_refresh_dX = float(cfg.thermo_refresh_dx)

    if thermo_refresh_dT is not None and (not np.isfinite(thermo_refresh_dT) or thermo_refresh_dT <= 0.0):
        thermo_refresh_dT = None
    if thermo_refresh_dP is not None and (not np.isfinite(thermo_refresh_dP) or thermo_refresh_dP <= 0.0):
        thermo_refresh_dP = None
    if thermo_refresh_dX is not None and (not np.isfinite(thermo_refresh_dX) or thermo_refresh_dX <= 0.0):
        thermo_refresh_dX = None
    if (
        coupled_hydraulic_energy
        and cfg.thermo_refresh_dT_F is None
        and cfg.thermo_refresh_dP_psia is None
        and cfg.thermo_refresh_dx is None
    ):
        # Avoid thermo/controller dead-band aliasing during steady-state approach.
        thermo_refresh_dT = None
        thermo_refresh_dP = None
        thermo_refresh_dX = None

    condenser_dp_psi = cfg.condenser_pressure_drop_psi
    if condenser_dp_psi is None:
        condenser_dp_psi = _spec_float(
            specs,
            "Condenser Pressure Drop (psi)",
            "Condenser Pressure Drop (psia)",
            "Condenser dP (psi)",
            "Condenser dP (psia)",
            "Condenser Delta P (psi)",
            "Condenser Delta P (psia)",
        )
    if condenser_dp_psi is not None and (not np.isfinite(condenser_dp_psi) or condenser_dp_psi < 0.0):
        condenser_dp_psi = None

    enable_top_psv = bool(cfg.enable_top_psv)
    if not enable_top_psv:
        b_psv = _as_bool(
            _spec_get(
                specs,
                "Enable Top PSV",
                "Top PSV Enabled",
                "Top Drum PSV Enabled",
                "Distillate Drum PSV Enabled",
                "Enable PSV",
            )
        )
        if b_psv is not None:
            enable_top_psv = bool(b_psv)
    top_psv_setpoint_psia = cfg.top_psv_setpoint_psia
    if top_psv_setpoint_psia is None:
        top_psv_setpoint_psia = _spec_float(
            specs,
            "Top PSV SP (psia)",
            "Top PSV Setpoint (psia)",
            "Top Drum PSV SP (psia)",
            "Top Drum PSV Setpoint (psia)",
            "Distillate Drum PSV SP (psia)",
            "Distillate Drum PSV Setpoint (psia)",
        )
    if top_psv_setpoint_psia is not None and (
        (not np.isfinite(top_psv_setpoint_psia)) or top_psv_setpoint_psia <= 0.0
    ):
        top_psv_setpoint_psia = None

    top_psv_gain_lbmolps_per_psi = cfg.top_psv_gain_lbmolps_per_psi
    if top_psv_gain_lbmolps_per_psi is None:
        top_psv_gain_lbmolps_per_psi = _spec_float(
            specs,
            "Top PSV Gain (lbmol/s/psi)",
            "Top PSV Gain (lbmolps/psi)",
            "Top Drum PSV Gain (lbmol/s/psi)",
            "Distillate Drum PSV Gain (lbmol/s/psi)",
        )
    if top_psv_gain_lbmolps_per_psi is not None and (
        (not np.isfinite(top_psv_gain_lbmolps_per_psi)) or top_psv_gain_lbmolps_per_psi <= 0.0
    ):
        top_psv_gain_lbmolps_per_psi = None

    top_psv_max_vent_lbmolps = cfg.top_psv_max_vent_lbmolps
    if top_psv_max_vent_lbmolps is None:
        top_psv_max_vent_lbmolps = _spec_float(
            specs,
            "Top PSV Max Vent (lbmol/s)",
            "Top PSV Max (lbmol/s)",
            "Top Drum PSV Max Vent (lbmol/s)",
            "Distillate Drum PSV Max Vent (lbmol/s)",
        )
    if top_psv_max_vent_lbmolps is not None and (
        (not np.isfinite(top_psv_max_vent_lbmolps)) or top_psv_max_vent_lbmolps < 0.0
    ):
        top_psv_max_vent_lbmolps = None

    overhead_line_vapor_volume_ft3 = _spec_float(
        specs,
        "Overhead Vapor Line Volume (ft3)",
        "Overhead Vapour Line Volume (ft3)",
        "Overhead Line Vapor Volume (ft3)",
        "Overhead Line Volume (ft3)",
    )
    if (
        overhead_line_vapor_volume_ft3 is not None
        and ((not np.isfinite(overhead_line_vapor_volume_ft3)) or overhead_line_vapor_volume_ft3 < 0.0)
    ):
        overhead_line_vapor_volume_ft3 = None

    condenser_vapor_volume_ft3 = _spec_float(
        specs,
        "Condenser Vapor Volume (ft3)",
        "Condenser Vapour Volume (ft3)",
        "Condenser Vapor Space (ft3)",
        "Condenser Vapour Space (ft3)",
    )
    if (
        condenser_vapor_volume_ft3 is not None
        and ((not np.isfinite(condenser_vapor_volume_ft3)) or condenser_vapor_volume_ft3 < 0.0)
    ):
        condenser_vapor_volume_ft3 = None

    overhead_vapor_adders_ft3 = 0.0
    if overhead_line_vapor_volume_ft3 is not None:
        overhead_vapor_adders_ft3 += float(overhead_line_vapor_volume_ft3)
    if condenser_vapor_volume_ft3 is not None:
        overhead_vapor_adders_ft3 += float(condenser_vapor_volume_ft3)
    condenser_type_txt = str(
        _spec_get(specs, "Condenser Type")
        or getattr(getattr(col, "duties", None), "condenser_type", "")
        or ""
    ).strip().lower()
    is_total_condenser = condenser_type_txt.startswith("total")

    top_drum_total_volume_ft3 = cfg.top_drum_total_volume_ft3
    if top_drum_total_volume_ft3 is None:
        top_drum_total_volume_ft3 = _spec_float(
            specs,
            "Top Drum Total Volume (ft3)",
            "Top Accumulator Total Volume (ft3)",
            "Reflux Drum Total Volume (ft3)",
            "Distillate Drum Total Volume (ft3)",
            "Top Drum Volume (ft3)",
            "Reflux Drum Volume (ft3)",
            "Distillate Drum Volume (ft3)",
        )
    if top_drum_total_volume_ft3 is None:
        d_ft = _spec_float(
            specs,
            "Top Drum Diameter (ft)",
            "Top Accumulator Diameter (ft)",
            "Reflux Drum Diameter (ft)",
            "Distillate Drum Diameter (ft)",
            "Top Drum ID (ft)",
            "Reflux Drum ID (ft)",
            "Distillate Drum ID (ft)",
        )
        l_ft = _spec_float(
            specs,
            "Top Drum Length (ft)",
            "Top Accumulator Length (ft)",
            "Reflux Drum Length (ft)",
            "Distillate Drum Length (ft)",
        )
        if d_ft is not None and l_ft is not None and d_ft > 0.0 and l_ft > 0.0:
            top_drum_total_volume_ft3 = float(np.pi * 0.25 * float(d_ft) * float(d_ft) * float(l_ft))

    top_drum_vapor_volume_ft3 = cfg.top_drum_vapor_volume_ft3
    if top_drum_vapor_volume_ft3 is None:
        top_drum_vapor_volume_ft3 = _spec_float(
            specs,
            "Top Drum Vapor Volume (ft3)",
            "Top Accumulator Vapor Volume (ft3)",
            "Reflux Drum Vapor Volume (ft3)",
            "Distillate Drum Vapor Volume (ft3)",
            "Top Vapor Volume (ft3)",
        )
    if top_drum_vapor_volume_ft3 is None:
        if top_drum_total_volume_ft3 is not None and np.isfinite(top_drum_total_volume_ft3) and top_drum_total_volume_ft3 > 0.0:
            top_liq_frac = _spec_float(
                specs,
                "Top Drum Liquid Fraction (-)",
                "Top Drum Liquid Volume Fraction",
                "Top Drum Liquid Fraction",
                "Top Accumulator Liquid Volume Fraction",
                "Top Accumulator Liquid Fraction",
                "Reflux Drum Liquid Volume Fraction",
                "Reflux Drum Liquid Fraction",
                "Distillate Drum Liquid Volume Fraction",
                "Distillate Drum Liquid Fraction",
                "Top Drum Fill Fraction",
                "Reflux Drum Fill Fraction",
                "Distillate Drum Fill Fraction",
            )
            if top_liq_frac is not None and top_liq_frac > 1.0 and top_liq_frac <= 100.0:
                top_liq_frac = float(top_liq_frac) / 100.0
            if top_liq_frac is not None and (top_liq_frac < 0.0 or top_liq_frac > 1.0):
                top_liq_frac = None

            top_liq_vol_ft3 = None
            if top_liq_frac is not None:
                top_liq_vol_ft3 = float(top_liq_frac) * float(top_drum_total_volume_ft3)
            else:
                top_holdup_lbmol = _spec_float(
                    specs,
                    "Top Accumulator Holdup (lbmol)",
                    "Top Drum Holdup (lbmol)",
                    "Reflux Drum Holdup (lbmol)",
                )
                if (
                    top_holdup_lbmol is not None
                    and top_holdup_lbmol > 0.0
                    and hasattr(prov, "liquid_density_lbmol_ft3")
                    and hasattr(col, "x0")
                    and hasattr(col, "T_f")
                    and hasattr(col, "P_psia")
                ):
                    try:
                        x_top = np.asarray(getattr(col, "x0"), dtype=float).reshape((col.n_stages, col.n_components))[0, :]
                        T_top = float(np.asarray(getattr(col, "T_f"), dtype=float).reshape((col.n_stages,))[0])
                        P_top = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((col.n_stages,))[0])
                        rho_top = float(prov.liquid_density_lbmol_ft3(T_top, P_top, x_top))
                        if np.isfinite(rho_top) and rho_top > 1e-12:
                            top_liq_vol_ft3 = float(top_holdup_lbmol) / float(rho_top)
                    except Exception:
                        top_liq_vol_ft3 = None

            if top_liq_vol_ft3 is None or (not np.isfinite(top_liq_vol_ft3)):
                # If only geometry is provided, default to half-full.
                top_liq_vol_ft3 = 0.5 * float(top_drum_total_volume_ft3)
            top_liq_vol_ft3 = float(np.clip(top_liq_vol_ft3, 0.0, float(top_drum_total_volume_ft3)))
            top_drum_vapor_volume_ft3 = float(top_drum_total_volume_ft3) - float(top_liq_vol_ft3)
    if (
        top_drum_total_volume_ft3 is None
        and top_drum_vapor_volume_ft3 is not None
        and np.isfinite(top_drum_vapor_volume_ft3)
        and top_drum_vapor_volume_ft3 > 0.0
    ):
        top_liq_frac = _spec_float(
            specs,
            "Top Drum Liquid Fraction (-)",
            "Top Drum Liquid Volume Fraction",
            "Top Drum Liquid Fraction",
            "Top Accumulator Liquid Volume Fraction",
            "Top Accumulator Liquid Fraction",
            "Reflux Drum Liquid Volume Fraction",
            "Reflux Drum Liquid Fraction",
            "Distillate Drum Liquid Volume Fraction",
            "Distillate Drum Liquid Fraction",
            "Top Drum Fill Fraction",
            "Reflux Drum Fill Fraction",
            "Distillate Drum Fill Fraction",
        )
        if top_liq_frac is not None and top_liq_frac > 1.0 and top_liq_frac <= 100.0:
            top_liq_frac = float(top_liq_frac) / 100.0
        if top_liq_frac is not None and 0.0 <= float(top_liq_frac) < 1.0:
            try:
                top_drum_total_volume_ft3 = float(top_drum_vapor_volume_ft3) / max(1.0 - float(top_liq_frac), 1e-12)
            except Exception:
                top_drum_total_volume_ft3 = None
        elif (
            hasattr(prov, "liquid_density_lbmol_ft3")
            and hasattr(col, "x0")
            and hasattr(col, "T_f")
            and hasattr(col, "P_psia")
        ):
            # Infer total drum volume from initial liquid holdup + explicit initial vapor volume.
            top_holdup_lbmol = _spec_float(
                specs,
                "Top Accumulator Holdup (lbmol)",
                "Top Drum Holdup (lbmol)",
                "Reflux Drum Holdup (lbmol)",
            )
            if top_holdup_lbmol is not None and top_holdup_lbmol >= 0.0:
                try:
                    x_top = np.asarray(getattr(col, "x0"), dtype=float).reshape((col.n_stages, col.n_components))[0, :]
                    T_top = float(np.asarray(getattr(col, "T_f"), dtype=float).reshape((col.n_stages,))[0])
                    P_top = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((col.n_stages,))[0])
                    rho_top = float(prov.liquid_density_lbmol_ft3(T_top, P_top, x_top))
                    if np.isfinite(rho_top) and rho_top > 1e-12:
                        top_liq_vol_ft3 = float(top_holdup_lbmol) / float(rho_top)
                        total_try = float(top_drum_vapor_volume_ft3) + max(float(top_liq_vol_ft3), 0.0)
                        if np.isfinite(total_try) and total_try > float(top_drum_vapor_volume_ft3):
                            top_drum_total_volume_ft3 = total_try
                except Exception:
                    top_drum_total_volume_ft3 = None

    if top_drum_vapor_volume_ft3 is None:
        try:
            vv = _vapor_volume_ft3_per_stage(vol, int(col.n_stages))
            top_drum_vapor_volume_ft3 = float(vv[0])
        except Exception:
            top_drum_vapor_volume_ft3 = None
    if (
        top_drum_total_volume_ft3 is None
        and top_drum_vapor_volume_ft3 is not None
        and np.isfinite(top_drum_vapor_volume_ft3)
        and top_drum_vapor_volume_ft3 > 0.0
        and hasattr(prov, "liquid_density_lbmol_ft3")
        and hasattr(col, "x0")
        and hasattr(col, "T_f")
        and hasattr(col, "P_psia")
    ):
        top_holdup_lbmol = _spec_float(
            specs,
            "Top Accumulator Holdup (lbmol)",
            "Top Drum Holdup (lbmol)",
            "Reflux Drum Holdup (lbmol)",
        )
        if top_holdup_lbmol is not None and top_holdup_lbmol >= 0.0:
            try:
                x_top = np.asarray(getattr(col, "x0"), dtype=float).reshape((col.n_stages, col.n_components))[0, :]
                T_top = float(np.asarray(getattr(col, "T_f"), dtype=float).reshape((col.n_stages,))[0])
                P_top = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((col.n_stages,))[0])
                rho_top = float(prov.liquid_density_lbmol_ft3(T_top, P_top, x_top))
                if np.isfinite(rho_top) and rho_top > 1e-12:
                    top_liq_vol_ft3 = float(top_holdup_lbmol) / float(rho_top)
                    total_try = float(top_drum_vapor_volume_ft3) + max(float(top_liq_vol_ft3), 0.0)
                    if np.isfinite(total_try) and total_try > float(top_drum_vapor_volume_ft3):
                        top_drum_total_volume_ft3 = total_try
            except Exception:
                top_drum_total_volume_ft3 = None
    if top_drum_vapor_volume_ft3 is not None and (
        (not np.isfinite(top_drum_vapor_volume_ft3)) or top_drum_vapor_volume_ft3 <= 0.0
    ):
        top_drum_vapor_volume_ft3 = None
    if top_drum_total_volume_ft3 is not None and (
        (not np.isfinite(top_drum_total_volume_ft3)) or top_drum_total_volume_ft3 <= 0.0
    ):
        top_drum_total_volume_ft3 = None
    if overhead_vapor_adders_ft3 > 0.0:
        if is_total_condenser:
            # For total condensers, pressure-side vapor capacitance is overhead
            # line + condenser space; downstream drum vapor is decoupled.
            top_drum_total_volume_ft3 = None
            top_drum_vapor_volume_ft3 = float(overhead_vapor_adders_ft3)
        else:
            # For non-total condenser representations, add vapor-only capacitance
            # on top of any drum-derived vapor-space volume.
            if top_drum_total_volume_ft3 is not None:
                top_drum_total_volume_ft3 = float(top_drum_total_volume_ft3) + float(overhead_vapor_adders_ft3)
            if top_drum_vapor_volume_ft3 is not None:
                top_drum_vapor_volume_ft3 = float(top_drum_vapor_volume_ft3) + float(overhead_vapor_adders_ft3)
            elif top_drum_total_volume_ft3 is None:
                top_drum_vapor_volume_ft3 = float(overhead_vapor_adders_ft3)
    if (
        top_drum_total_volume_ft3 is not None
        and top_drum_vapor_volume_ft3 is not None
        and top_drum_vapor_volume_ft3 > top_drum_total_volume_ft3
    ):
        top_drum_vapor_volume_ft3 = float(top_drum_total_volume_ft3)

    mw_components = None
    if hasattr(prov, "component_mw_lbm_per_lbmol"):
        try:
            mw_raw = prov.component_mw_lbm_per_lbmol()
            if mw_raw is not None:
                mw_try = np.asarray(mw_raw, dtype=float).reshape((col.n_components,))
                if np.all(np.isfinite(mw_try)) and np.all(mw_try > 0.0):
                    mw_components = mw_try
        except Exception:
            mw_components = None

    top_pressure_ordering_margin_psi = 0.0
    try:
        top_pressure_ordering_margin_psi = float(cfg.top_pressure_ordering_margin_psi)
    except Exception:
        top_pressure_ordering_margin_psi = 0.0
    if (not np.isfinite(top_pressure_ordering_margin_psi)) or top_pressure_ordering_margin_psi < 0.0:
        top_pressure_ordering_margin_psi = 0.0

    liq_hyd_override_enable = _as_bool(
        _spec_get(
            specs,
            "Enable Liquid Hydraulic Override",
            "Enable Liquid Hydraulics Override",
            "Liquid Hydraulic Override Enabled",
            "Liquid Hydraulics Enabled",
        )
    )
    if cfg.enable_liquid_hydraulic_override is not None:
        liq_hyd_override_enable = bool(cfg.enable_liquid_hydraulic_override)
    if liq_hyd_override_enable is None:
        liq_hyd_override_enable = True

    liq_hyd_override_alpha = cfg.liquid_hydraulic_override_alpha
    if liq_hyd_override_alpha is None:
        liq_hyd_override_alpha = _spec_float(
            specs,
            "Liquid Hydraulic Override Alpha",
            "Liquid Hydraulics Override Alpha",
            "Liquid Hydraulic Blend",
            "Liquid Hydraulics Blend",
            "Liquid Hydraulics Alpha",
        )
    liq_hyd_override_alpha = _clip_unit(liq_hyd_override_alpha, default=1.0)

    if runtime_mode in ("parity", "calibration"):
        liq_hyd_override_enable = False
        liq_hyd_override_alpha = 0.0
    elif runtime_mode == "hydraulic":
        liq_hyd_override_enable = True

    inputs = ColumnInputs(
        boundary=boundary,
        volume_model=vol,
        condenser_duty_mode=str(cfg.condenser_duty_mode),
        condenser_duty_btu_per_h=(float(cfg.condenser_duty_btu_per_h) if cfg.condenser_duty_btu_per_h is not None else None),
        condenser_duty_trim_btu_per_h=(
            float(cfg.condenser_duty_trim_btu_per_h)
            if cfg.condenser_duty_trim_btu_per_h is not None
            else None
        ),
        thermo_provider=prov,
        compute_thermo_diag=True,
        equilibrium_relaxation=bool(cfg.enable_equilibrium_relaxation),
        equilibrium_relaxation_mode=str(eq_mode),
        tau_eq_sec=getattr(col, "tau_eq_sec", None),
        reboiler_duty_btu_per_h=(float(cfg.reboiler_duty_btu_per_h) if cfg.reboiler_duty_btu_per_h is not None else None),
        pressure_model=str(pressure_model),
        pressure_top_anchor_psia=None,
        condenser_pressure_drop_psi=(float(condenser_dp_psi) if condenser_dp_psi is not None else None),
        top_drum_vapor_volume_ft3=(
            float(top_drum_vapor_volume_ft3)
            if top_drum_vapor_volume_ft3 is not None
            else None
        ),
        top_drum_total_volume_ft3=(
            float(top_drum_total_volume_ft3)
            if top_drum_total_volume_ft3 is not None
            else None
        ),
        enforce_top_drum_pressure_gate=bool(cfg.enforce_top_drum_pressure_gate),
        top_drum_pressure_gate_soft_psi=(
            float(cfg.top_drum_pressure_gate_soft_psi)
            if cfg.top_drum_pressure_gate_soft_psi is not None
            else None
        ),
        enable_top_drum_psv=bool(enable_top_psv),
        top_drum_psv_setpoint_psia=(
            float(top_psv_setpoint_psia)
            if top_psv_setpoint_psia is not None
            else None
        ),
        top_drum_psv_gain_lbmolps_per_psi=(
            float(top_psv_gain_lbmolps_per_psi)
            if top_psv_gain_lbmolps_per_psi is not None
            else None
        ),
        top_drum_psv_max_vent_lbmolps=(
            float(top_psv_max_vent_lbmolps)
            if top_psv_max_vent_lbmolps is not None
            else None
        ),
        vapor_flow_model=str(vapor_flow_model),
        dry_tray_K=float(dry_tray_k),
        vapor_holdup_relaxation_sec=(float(tau_v) if tau_v is not None else None),
        hydraulic_pressure_relaxation_sec=(float(tau_p_hyd) if tau_p_hyd is not None else None),
        top_drum_pressure_temperature_relaxation_sec=(
            float(tau_top_pT) if tau_top_pT is not None else None
        ),
        vapor_flow_relaxation_sec=(float(tau_vflow) if tau_vflow is not None else None),
        conductance_vflow_nominal_hi_ratio=(
            float(conductance_vflow_nominal_hi_ratio)
            if conductance_vflow_nominal_hi_ratio is not None
            else None
        ),
        enforce_top_pressure_ordering=bool(cfg.enforce_top_pressure_ordering),
        top_pressure_ordering_margin_psi=float(top_pressure_ordering_margin_psi),
        reboiler_neighbor_vflow_hi_ratio=(float(reb_nbr_hi) if reb_nbr_hi is not None else 1.20),
        reboiler_neighbor_vflow_lo_ratio=(float(reb_nbr_lo) if reb_nbr_lo is not None else 0.80),
        thermo_refresh_dT_F=(float(thermo_refresh_dT) if thermo_refresh_dT is not None else None),
        thermo_refresh_dP_psia=(float(thermo_refresh_dP) if thermo_refresh_dP is not None else None),
        thermo_refresh_dx=(float(thermo_refresh_dX) if thermo_refresh_dX is not None else None),
        enable_liquid_hydraulic_override=bool(liq_hyd_override_enable),
        liquid_hydraulic_override_alpha=float(liq_hyd_override_alpha),
        component_mw_lbm_per_lbmol=mw_components,
    )
    return inputs, prov


# -------------------------
# State utilities
# -------------------------


def _clamp_nonnegative_holdups(y: np.ndarray, layout: StateVectorLayout) -> np.ndarray:
    y = np.asarray(y, dtype=float).copy()
    sl = layout.slices()

    y[sl["tray_L"]] = np.clip(y[sl["tray_L"]], 0.0, None)
    if layout.include_vapor:
        y[sl["tray_V"]] = np.clip(y[sl["tray_V"]], 0.0, None)

    if layout.include_top:
        y[sl["top_L"]] = np.clip(y[sl["top_L"]], 0.0, None)
        if layout.include_vapor:
            y[sl["top_V"]] = np.clip(y[sl["top_V"]], 0.0, None)

    if layout.include_bottom:
        y[sl["bottom_L"]] = np.clip(y[sl["bottom_L"]], 0.0, None)
        if layout.include_vapor:
            y[sl["bottom_V"]] = np.clip(y[sl["bottom_V"]], 0.0, None)

    return y


def _clip_temperature_states_to_provider_bounds(
    y: np.ndarray,
    layout: StateVectorLayout,
    thermo_provider: Optional[Any],
) -> np.ndarray:
    """
    Clip temperature states to provider table bounds when available.
    """
    if thermo_provider is None:
        return y
    t_grid = getattr(thermo_provider, "T_grid_F", None)
    if t_grid is None:
        return y
    try:
        g = np.asarray(t_grid, dtype=float).reshape((-1,))
    except Exception:
        return y
    if g.size < 2 or (not np.all(np.isfinite(g))):
        return y
    t_min = float(np.min(g))
    t_max = float(np.max(g))
    if (not np.isfinite(t_min)) or (not np.isfinite(t_max)) or (t_max <= t_min):
        return y

    y_new = np.asarray(y, dtype=float).copy()
    sl = layout.slices()
    if "tray_T_f" in sl:
        y_new[sl["tray_T_f"]] = np.clip(y_new[sl["tray_T_f"]], t_min, t_max)
    if "bottom_T_f" in sl:
        y_new[sl["bottom_T_f"]] = np.clip(y_new[sl["bottom_T_f"]], t_min, t_max)
    return y_new


def _integrate_one_step(
    *,
    t_s: float,
    y: np.ndarray,
    dt_sec: float,
    rhs_eval: Any,
    layout: StateVectorLayout,
    thermo_provider: Optional[Any],
    integrator_mode: str,
    rtol: Optional[float],
    atol: Optional[float],
    max_step_sec: Optional[float],
    substep_sec: Optional[float],
    max_rhs_evals_per_step: Optional[int],
    step_wall_limit_sec: Optional[float],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    y0 = np.asarray(y, dtype=float).reshape((-1,))
    dt = float(dt_sec)
    if dt <= 0.0:
        raise ValueError("dt_sec must be > 0")

    mode = _normalize_integrator_mode(integrator_mode, default="explicit-euler")
    info: Dict[str, Any] = {
        "requested_mode": str(mode),
        "used_mode": str(mode),
        "fallback_used": False,
        "fallback_reason": "",
        "nfev": np.nan,
        "njev": np.nan,
        "nlu": np.nan,
        "status": np.nan,
        "message": "",
        "n_substeps": np.nan,
    }
    step_t0 = time.perf_counter()
    rhs_eval_count = 0

    def _project_state(y_in: np.ndarray) -> np.ndarray:
        y_out = _clamp_nonnegative_holdups(np.asarray(y_in, dtype=float), layout)
        y_out = _clip_temperature_states_to_provider_bounds(y_out, layout, thermo_provider)
        return y_out

    y0 = _project_state(y0)

    def _explicit_step(reason: str = "") -> Tuple[np.ndarray, Dict[str, Any]]:
        nonlocal rhs_eval_count
        rhs_eval_count += 1
        dydt, _diag = rhs_eval(float(t_s), y0)
        y1 = y0 + dt * np.asarray(dydt, dtype=float).reshape((-1,))
        y1 = _project_state(y1)
        if reason:
            info["used_mode"] = "explicit-euler"
            info["fallback_used"] = True
            info["fallback_reason"] = str(reason)
        info["nfev"] = float(rhs_eval_count)
        return y1, info

    if mode == "explicit-euler":
        return _explicit_step()

    if _solve_ivp is None:
        return _explicit_step("SciPy solve_ivp unavailable")

    method = "BDF" if mode == "bdf" else "Radau"

    try:
        rtol_use = float(rtol) if rtol is not None else 1.0e-3
    except Exception:
        rtol_use = 1.0e-3
    if (not np.isfinite(rtol_use)) or rtol_use <= 0.0:
        rtol_use = 1.0e-3

    try:
        atol_use = float(atol) if atol is not None else 1.0e-6
    except Exception:
        atol_use = 1.0e-6
    if (not np.isfinite(atol_use)) or atol_use <= 0.0:
        atol_use = 1.0e-6

    max_step_use = float("inf")
    if max_step_sec is not None:
        try:
            ms = float(max_step_sec)
        except Exception:
            ms = np.nan
        if np.isfinite(ms) and ms > 0.0:
            max_step_use = min(float(ms), float(dt))

    sub_dt = float(dt)
    if substep_sec is not None:
        try:
            sub_try = float(substep_sec)
        except Exception:
            sub_try = np.nan
        if np.isfinite(sub_try) and sub_try > 0.0:
            sub_dt = min(float(dt), float(sub_try))
    n_substeps = max(1, int(np.ceil(float(dt) / max(float(sub_dt), 1.0e-12))))
    info["n_substeps"] = float(n_substeps)

    max_rhs = None
    if max_rhs_evals_per_step is not None:
        try:
            max_rhs_try = int(max_rhs_evals_per_step)
        except Exception:
            max_rhs_try = 0
        if max_rhs_try > 0:
            max_rhs = int(max_rhs_try)

    wall_limit = None
    if step_wall_limit_sec is not None:
        try:
            wall_try = float(step_wall_limit_sec)
        except Exception:
            wall_try = np.nan
        if np.isfinite(wall_try) and wall_try > 0.0:
            wall_limit = float(wall_try)

    def _rhs_ivp(t_eval: float, y_eval: np.ndarray) -> np.ndarray:
        nonlocal rhs_eval_count
        rhs_eval_count += 1
        if max_rhs is not None and rhs_eval_count > int(max_rhs):
            raise RuntimeError(f"max RHS evals exceeded ({int(max_rhs)})")
        if wall_limit is not None and (time.perf_counter() - step_t0) > float(wall_limit):
            raise RuntimeError(f"step wall-time limit exceeded ({float(wall_limit):.3g}s)")
        y_rhs = np.asarray(y_eval, dtype=float).reshape((-1,))
        if not np.all(np.isfinite(y_rhs)):
            raise RuntimeError("non-finite state encountered in stiff substep")
        dydt, _diag = rhs_eval(float(t_eval), y_rhs)
        dydt_out = np.asarray(dydt, dtype=float).reshape((-1,))
        if not np.all(np.isfinite(dydt_out)):
            raise RuntimeError("non-finite derivative encountered in stiff substep")
        return dydt_out

    y_curr = np.asarray(y0, dtype=float).reshape((-1,))
    t_curr = float(t_s)
    nfev_total = 0.0
    njev_total = 0.0
    nlu_total = 0.0
    status_last = 0.0
    msg_last = ""

    for k in range(n_substeps):
        t_next = float(min(float(t_s) + float(dt), t_curr + float(sub_dt)))
        dt_k = float(t_next - t_curr)
        if dt_k <= 0.0:
            continue
        max_step_k = min(float(max_step_use), float(dt_k))
        try:
            sol = _solve_ivp(
                fun=_rhs_ivp,
                t_span=(float(t_curr), float(t_next)),
                y0=np.asarray(y_curr, dtype=float).reshape((-1,)),
                method=method,
                t_eval=[float(t_next)],
                rtol=float(rtol_use),
                atol=float(atol_use),
                max_step=float(max_step_k),
                vectorized=False,
            )
        except Exception as exc:
            return _explicit_step(f"{method} integrator exception (substep {k+1}/{n_substeps}): {exc}")

        nfev_total += float(getattr(sol, "nfev", 0.0))
        njev_total += float(getattr(sol, "njev", 0.0))
        nlu_total += float(getattr(sol, "nlu", 0.0))
        status_last = float(getattr(sol, "status", np.nan))
        msg_last = str(getattr(sol, "message", ""))

        y_sol = getattr(sol, "y", None)
        if (
            (not bool(getattr(sol, "success", False)))
            or y_sol is None
            or np.asarray(y_sol).ndim != 2
            or np.asarray(y_sol).shape[1] < 1
        ):
            msg = str(getattr(sol, "message", "")).strip()
            if not msg:
                msg = f"{method} integrator failed at substep {k+1}/{n_substeps}"
            return _explicit_step(msg)

        y_next = np.asarray(y_sol, dtype=float)[:, -1].reshape((-1,))
        if not np.all(np.isfinite(y_next)):
            return _explicit_step(f"{method} produced non-finite state at substep {k+1}/{n_substeps}")
        y_curr = _project_state(y_next)
        t_curr = float(t_next)

    info["nfev"] = float(nfev_total)
    info["njev"] = float(njev_total)
    info["nlu"] = float(nlu_total)
    info["status"] = float(status_last)
    info["message"] = str(msg_last)
    return y_curr, info


def _integrate_one_step_ida(
    *,
    t_s: float,
    y: np.ndarray,
    dt_sec: float,
    rhs_eval: Any,
    layout: StateVectorLayout,
    thermo_provider: Optional[Any],
    substep_sec: Optional[float],
    max_iter: Optional[int],
    relax: Optional[float],
    rtol: Optional[float],
    atol: Optional[float],
    max_rhs_evals_per_step: Optional[int],
    step_wall_limit_sec: Optional[float],
    alg_p_tol_psia: Optional[float] = None,
    alg_v_tol_lbmolph: Optional[float] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Pilot simultaneous-DAE stepper (IDA-style fixed-point implicit Euler).

    For each substep it solves:
      y_{k+1} = y_k + dt * f(t_{k+1}, y_{k+1})
    by fixed-point iteration. When rhs_eval includes DAE algebraic closure
    (e.g., pilot Newton solve for P/V), this yields a lightweight
    simultaneous differential+algebraic step without SciPy solve_ivp.
    """
    y0 = np.asarray(y, dtype=float).reshape((-1,))
    dt = float(dt_sec)
    if dt <= 0.0:
        raise ValueError("dt_sec must be > 0")

    info: Dict[str, Any] = {
        "requested_mode": "ida",
        "used_mode": "ida",
        "fallback_used": False,
        "fallback_reason": "",
        "nfev": np.nan,
        "njev": np.nan,
        "nlu": np.nan,
        "status": np.nan,
        "message": "",
        "n_substeps": np.nan,
        "ida_iter_max": np.nan,
        "ida_iter_mean": np.nan,
        "ida_converged": 0.0,
        "ida_last_err": np.nan,
        "ida_alg_p_inf_psia": np.nan,
        "ida_alg_v_inf_lbmolph": np.nan,
        "ida_alg_weighted": np.nan,
        "ida_alg_converged": np.nan,
        "ida_resid_energy_btups": np.nan,
    }
    step_t0 = time.perf_counter()

    def _project_state(y_in: np.ndarray) -> np.ndarray:
        y_out = _clamp_nonnegative_holdups(np.asarray(y_in, dtype=float), layout)
        y_out = _clip_temperature_states_to_provider_bounds(y_out, layout, thermo_provider)
        return y_out

    y0 = _project_state(y0)

    try:
        n_iter = int(max_iter) if max_iter is not None else 8
    except Exception:
        n_iter = 8
    n_iter = max(1, n_iter)

    try:
        relax_use = float(relax) if relax is not None else 1.0
    except Exception:
        relax_use = 1.0
    if (not np.isfinite(relax_use)) or relax_use <= 0.0:
        relax_use = 1.0
    if relax_use > 1.0:
        relax_use = 1.0

    try:
        rtol_use = float(rtol) if rtol is not None else 1.0e-3
    except Exception:
        rtol_use = 1.0e-3
    if (not np.isfinite(rtol_use)) or rtol_use <= 0.0:
        rtol_use = 1.0e-3

    try:
        atol_use = float(atol) if atol is not None else 1.0e-6
    except Exception:
        atol_use = 1.0e-6
    if (not np.isfinite(atol_use)) or atol_use <= 0.0:
        atol_use = 1.0e-6

    try:
        alg_p_tol_use = float(alg_p_tol_psia) if alg_p_tol_psia is not None else 0.05
    except Exception:
        alg_p_tol_use = 0.05
    if (not np.isfinite(alg_p_tol_use)) or alg_p_tol_use <= 0.0:
        alg_p_tol_use = 0.05

    try:
        alg_v_tol_use = float(alg_v_tol_lbmolph) if alg_v_tol_lbmolph is not None else 25.0
    except Exception:
        alg_v_tol_use = 25.0
    if (not np.isfinite(alg_v_tol_use)) or alg_v_tol_use <= 0.0:
        alg_v_tol_use = 25.0

    sub_dt = float(dt)
    if substep_sec is not None:
        try:
            sub_try = float(substep_sec)
        except Exception:
            sub_try = np.nan
        if np.isfinite(sub_try) and sub_try > 0.0:
            sub_dt = min(float(dt), float(sub_try))
    n_substeps = max(1, int(np.ceil(float(dt) / max(float(sub_dt), 1.0e-12))))
    info["n_substeps"] = float(n_substeps)

    max_rhs = None
    if max_rhs_evals_per_step is not None:
        try:
            max_rhs_try = int(max_rhs_evals_per_step)
        except Exception:
            max_rhs_try = 0
        if max_rhs_try > 0:
            max_rhs = int(max_rhs_try)

    wall_limit = None
    if step_wall_limit_sec is not None:
        try:
            wall_try = float(step_wall_limit_sec)
        except Exception:
            wall_try = np.nan
        if np.isfinite(wall_try) and wall_try > 0.0:
            wall_limit = float(wall_try)

    rhs_eval_count = 0
    iter_counts: List[int] = []
    last_err = float("nan")
    last_alg_p = float("nan")
    last_alg_v = float("nan")
    last_alg_weighted = float("nan")
    last_energy_resid = float("nan")
    converged_all = True

    def _rhs(t_eval: float, y_eval: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        nonlocal rhs_eval_count
        rhs_eval_count += 1
        if max_rhs is not None and rhs_eval_count > int(max_rhs):
            raise RuntimeError(f"max RHS evals exceeded ({int(max_rhs)})")
        if wall_limit is not None and (time.perf_counter() - step_t0) > float(wall_limit):
            raise RuntimeError(f"step wall-time limit exceeded ({float(wall_limit):.3g}s)")
        dydt, diag = rhs_eval(float(t_eval), np.asarray(y_eval, dtype=float).reshape((-1,)))
        dydt_out = np.asarray(dydt, dtype=float).reshape((-1,))
        if not np.all(np.isfinite(dydt_out)):
            raise RuntimeError("non-finite derivative in ida fixed-point step")
        diag_out = dict(diag) if isinstance(diag, dict) else {}
        return dydt_out, diag_out

    y_curr = np.asarray(y0, dtype=float).reshape((-1,))
    t_curr = float(t_s)
    fallback_reason = ""

    try:
        for k in range(n_substeps):
            t_next = float(min(float(t_s) + float(dt), t_curr + float(sub_dt)))
            dt_k = float(t_next - t_curr)
            if dt_k <= 0.0:
                continue

            # Explicit predictor from current state.
            dydt_pred, _diag_pred = _rhs(float(t_curr), y_curr)
            y_guess = _project_state(y_curr + float(dt_k) * dydt_pred)

            converged = False
            it_used = 0
            for it in range(n_iter):
                it_used = int(it + 1)
                dydt_it, diag_it = _rhs(float(t_next), y_guess)
                y_impl = _project_state(y_curr + float(dt_k) * dydt_it)
                y_new = _project_state(y_guess + float(relax_use) * (y_impl - y_guess))

                dy = np.asarray(y_new, dtype=float) - np.asarray(y_guess, dtype=float)
                scale = float(atol_use) + float(rtol_use) * np.maximum(
                    np.abs(np.asarray(y_new, dtype=float)),
                    np.abs(np.asarray(y_guess, dtype=float)),
                )
                scale = np.where(scale > 1.0e-14, scale, 1.0e-14)
                err = float(np.max(np.abs(dy) / scale)) if dy.size > 0 else 0.0
                last_err = err

                alg_p_inf = abs(_mapping_scalar(diag_it, "dae_pilot_alg_p_inf_psia"))
                alg_v_inf = abs(_mapping_scalar(diag_it, "dae_pilot_alg_v_inf_lbmolph"))
                resid_energy = abs(_mapping_scalar(diag_it, "resid_energy_btups"))

                terms: List[float] = []
                if np.isfinite(alg_p_inf):
                    last_alg_p = float(alg_p_inf)
                    terms.append(float(alg_p_inf) / float(alg_p_tol_use))
                if np.isfinite(alg_v_inf):
                    last_alg_v = float(alg_v_inf)
                    terms.append(float(alg_v_inf) / float(alg_v_tol_use))
                if np.isfinite(resid_energy):
                    last_energy_resid = float(resid_energy)
                alg_weighted = float(np.max(np.asarray(terms, dtype=float))) if terms else float("nan")
                if np.isfinite(alg_weighted):
                    last_alg_weighted = float(alg_weighted)
                alg_ok = (not np.isfinite(alg_weighted)) or (alg_weighted <= 1.0)

                y_guess = y_new
                if np.isfinite(err) and err <= 1.0 and bool(alg_ok):
                    converged = True
                    break

            iter_counts.append(int(it_used))
            if not converged:
                converged_all = False
                fallback_reason = (
                    f"IDA fixed-point did not converge at substep {k+1}/{n_substeps} "
                    f"(iters={it_used}, err={last_err:.3g}, alg={last_alg_weighted:.3g})"
                )
                break

            y_curr = np.asarray(y_guess, dtype=float).reshape((-1,))
            t_curr = float(t_next)
    except Exception as exc:
        converged_all = False
        fallback_reason = str(exc)

    if not converged_all:
        # Step-level explicit fallback from original y0.
        try:
            dydt_fb, _diag_fb = _rhs(float(t_s), y0)
            y_fb = _project_state(y0 + float(dt) * np.asarray(dydt_fb, dtype=float).reshape((-1,)))
        except Exception:
            y_fb = _project_state(np.asarray(y0, dtype=float))
        info["used_mode"] = "explicit-euler"
        info["fallback_used"] = True
        info["fallback_reason"] = str(fallback_reason or "ida step failed")
        info["nfev"] = float(rhs_eval_count)
        if iter_counts:
            info["ida_iter_max"] = float(np.max(np.asarray(iter_counts, dtype=float)))
            info["ida_iter_mean"] = float(np.mean(np.asarray(iter_counts, dtype=float)))
        info["ida_converged"] = 0.0
        info["ida_last_err"] = float(last_err)
        info["ida_alg_p_inf_psia"] = float(last_alg_p)
        info["ida_alg_v_inf_lbmolph"] = float(last_alg_v)
        info["ida_alg_weighted"] = float(last_alg_weighted)
        info["ida_alg_converged"] = (
            1.0 if ((not np.isfinite(last_alg_weighted)) or (last_alg_weighted <= 1.0)) else 0.0
        )
        info["ida_resid_energy_btups"] = float(last_energy_resid)
        return y_fb, info

    info["nfev"] = float(rhs_eval_count)
    if iter_counts:
        info["ida_iter_max"] = float(np.max(np.asarray(iter_counts, dtype=float)))
        info["ida_iter_mean"] = float(np.mean(np.asarray(iter_counts, dtype=float)))
    info["ida_converged"] = 1.0
    info["ida_last_err"] = float(last_err)
    info["ida_alg_p_inf_psia"] = float(last_alg_p)
    info["ida_alg_v_inf_lbmolph"] = float(last_alg_v)
    info["ida_alg_weighted"] = float(last_alg_weighted)
    info["ida_alg_converged"] = (
        1.0 if ((not np.isfinite(last_alg_weighted)) or (last_alg_weighted <= 1.0)) else 0.0
    )
    info["ida_resid_energy_btups"] = float(last_energy_resid)
    return y_curr, info


def _clear_initial_tray_vapor_holdup(y: np.ndarray, layout: StateVectorLayout) -> np.ndarray:
    """Clear initial tray vapor holdup states before pressure-based MV initialization."""
    if not layout.include_vapor:
        return y
    y_new = np.asarray(y, dtype=float).copy()
    sl = layout.slices()
    y_new[sl["tray_V"]] = 0.0
    return y_new


def _tray_temperature_F(col: ColumnSpec, layout: StateVectorLayout, y: np.ndarray, include_temperature: bool) -> np.ndarray:
    N = col.n_stages
    if include_temperature:
        u = layout.unpack(y)
        if "tray_T_f" in u:
            return np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
    return np.asarray(getattr(col, "T_f", np.full(N, np.nan, dtype=float)), dtype=float).reshape((N,))


def _total_inventory_lbmol(layout: StateVectorLayout, y: np.ndarray) -> float:
    """Total molar inventory over all holdup states (lbmol)."""
    u = layout.unpack(np.asarray(y, dtype=float))
    total = 0.0
    # When a separate top drum state is present, tray-1 liquid/vapor are tied to
    # that same inventory in the RHS. Exclude tray-1 from global totals to avoid
    # double counting in mass-closure diagnostics.
    has_top_drum = bool(getattr(layout, "include_top", False)) and ("top_L" in u)
    for key in ("tray_L", "tray_V", "top_L", "top_V", "bottom_L", "bottom_V"):
        if key not in u:
            continue
        try:
            arr = np.asarray(u[key], dtype=float)
            if has_top_drum and key in ("tray_L", "tray_V") and arr.ndim == 2 and arr.shape[0] > 0:
                arr = arr[1:, :]
            total += float(np.nansum(arr))
        except Exception:
            pass
    return float(total)


def _total_inventory_rate_lbmolps(layout: StateVectorLayout, dydt: np.ndarray) -> float:
    """Total inventory time derivative over molar holdup states (lbmol/s)."""
    ud = layout.unpack(np.asarray(dydt, dtype=float))
    total = 0.0
    has_top_drum = bool(getattr(layout, "include_top", False)) and ("top_L" in ud)
    for key in ("tray_L", "tray_V", "top_L", "top_V", "bottom_L", "bottom_V"):
        if key not in ud:
            continue
        try:
            arr = np.asarray(ud[key], dtype=float)
            if has_top_drum and key in ("tray_L", "tray_V") and arr.ndim == 2 and arr.shape[0] > 0:
                arr = arr[1:, :]
            total += float(np.nansum(arr))
        except Exception:
            pass
    return float(total)


def _vapor_volume_ft3_per_stage(vol: VolumeModel, N: int) -> np.ndarray:
    if vol.vapor_volume_ft3_per_stage is not None:
        V = np.asarray(vol.vapor_volume_ft3_per_stage, dtype=float).reshape((N,))
    else:
        V = np.full(N, float(vol.default_vapor_volume_ft3), dtype=float)
    V = np.where(~np.isfinite(V) | (V <= 0.0), 1.0, V)
    return V


def _pressure_diag_psia(
    col: ColumnSpec,
    vol: VolumeModel,
    T_F: np.ndarray,
    MV_tot_tray: np.ndarray,
    Z_tray: np.ndarray,
) -> np.ndarray:
    N = col.n_stages
    MV = np.asarray(MV_tot_tray, dtype=float).reshape((N,))
    Z = np.asarray(Z_tray, dtype=float).reshape((N,))
    Z = np.where(~np.isfinite(Z) | (Z <= 0.0), 1.0, Z)

    V = _vapor_volume_ft3_per_stage(vol, N)

    R = 10.7316  # (psia*ft3)/(lbmol*R)
    T_R = np.asarray(T_F, dtype=float).reshape((N,)) + 459.67
    T_R = np.where(~np.isfinite(T_R) | (T_R <= 1e-6), 559.67, T_R)

    P = MV * Z * R * T_R / V
    P = np.where(np.isfinite(P), P, np.nan)

    # Condenser stage pin to spec, if present
    try:
        P_spec0 = float(np.asarray(getattr(col, "P_psia", [np.nan]), dtype=float).reshape((-1,))[0])
        if np.isfinite(P_spec0):
            P[0] = P_spec0
    except Exception:
        pass

    return P


def _as_stage_vector(
    arr: Optional[np.ndarray],
    n_stages: int,
    *,
    positive_only: bool = False,
) -> Optional[np.ndarray]:
    if arr is None:
        return None
    try:
        out = np.asarray(arr, dtype=float).reshape((int(n_stages),)).copy()
    except Exception:
        return None
    if out.size != int(n_stages):
        return None
    valid = np.isfinite(out)
    if positive_only:
        valid = valid & (out > 0.0)
    if not np.any(valid):
        return None
    return out


def _diag_stage_vector(
    diag: Dict[str, np.ndarray],
    key: str,
    n_stages: int,
    *,
    positive_only: bool = False,
) -> Optional[np.ndarray]:
    if key not in diag:
        return None
    return _as_stage_vector(diag.get(key), n_stages, positive_only=positive_only)


def _max_abs_delta(a: Optional[np.ndarray], b: Optional[np.ndarray], *, positive_only: bool = False) -> float:
    if a is None or b is None:
        return float("nan")
    try:
        aa = np.asarray(a, dtype=float).reshape((-1,))
        bb = np.asarray(b, dtype=float).reshape((-1,))
    except Exception:
        return float("nan")
    if aa.size != bb.size or aa.size == 0:
        return float("nan")
    mask = np.isfinite(aa) & np.isfinite(bb)
    if positive_only:
        mask = mask & (aa > 0.0) & (bb > 0.0)
    if not np.any(mask):
        return float("nan")
    return float(np.max(np.abs(aa[mask] - bb[mask])))


def _column_rhs_with_inner_pv_coupling(
    *,
    t_s: float,
    y: np.ndarray,
    col: ColumnSpec,
    layout: StateVectorLayout,
    inputs: ColumnInputs,
    max_iter: int,
    p_tol_psia: Optional[float],
    v_tol_lbmolph: Optional[float],
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Fixed-point inner coupling for pressure and vapor flow within one timestep.

    This iterates RHS evaluation by feeding the newly computed tray pressure and
    vapor outflow back as `P_tray_prev` and `V_out_prev_lbmolph` before the next
    inner pass. It is intentionally lightweight and keeps the outer integrator
    explicit.
    """
    try:
        n_iter_req = int(max_iter)
    except Exception:
        n_iter_req = 1
    n_iter_req = max(n_iter_req, 1)

    if p_tol_psia is not None:
        try:
            p_tol_psia = float(p_tol_psia)
        except Exception:
            p_tol_psia = None
        if p_tol_psia is not None and ((not np.isfinite(p_tol_psia)) or p_tol_psia <= 0.0):
            p_tol_psia = None
    if v_tol_lbmolph is not None:
        try:
            v_tol_lbmolph = float(v_tol_lbmolph)
        except Exception:
            v_tol_lbmolph = None
        if v_tol_lbmolph is not None and ((not np.isfinite(v_tol_lbmolph)) or v_tol_lbmolph <= 0.0):
            v_tol_lbmolph = None

    n_stages = int(getattr(col, "n_stages", 0))
    inputs_iter = inputs
    p_prev = _as_stage_vector(inputs.P_tray_prev, n_stages, positive_only=True)
    v_prev = _as_stage_vector(inputs.V_out_prev_lbmolph, n_stages, positive_only=False)

    converged = False
    dp_last = float("nan")
    dv_last = float("nan")
    iter_count = 0
    dydt = np.zeros_like(np.asarray(y, dtype=float))
    diag: Dict[str, np.ndarray] = {}

    for it in range(n_iter_req):
        dydt, diag = column_rhs(t_s, y, col, layout, inputs=inputs_iter)
        iter_count = int(it + 1)

        p_next = _diag_stage_vector(diag, "P_psia_hyd", n_stages, positive_only=True)
        if p_next is None:
            p_next = _diag_stage_vector(diag, "P_psia_diag", n_stages, positive_only=True)
        v_next = _diag_stage_vector(diag, "V_out_lbmolph", n_stages, positive_only=False)

        dp_last = _max_abs_delta(p_next, p_prev, positive_only=True)
        dv_last = _max_abs_delta(v_next, v_prev, positive_only=False)

        if it >= 1:
            p_ok = True if p_tol_psia is None else (np.isfinite(dp_last) and dp_last <= float(p_tol_psia))
            v_ok = True if v_tol_lbmolph is None else (np.isfinite(dv_last) and dv_last <= float(v_tol_lbmolph))
            if p_ok and v_ok:
                converged = True
                break

        if it >= (n_iter_req - 1):
            break

        updates: Dict[str, Any] = {}
        if p_next is not None:
            updates["P_tray_prev"] = np.asarray(p_next, dtype=float).copy()
            p_prev = np.asarray(p_next, dtype=float).copy()
        if v_next is not None:
            updates["V_out_prev_lbmolph"] = np.asarray(v_next, dtype=float).copy()
            v_prev = np.asarray(v_next, dtype=float).copy()
        z_next = _diag_stage_vector(diag, "Z_tray", n_stages, positive_only=True)
        if z_next is not None:
            updates["Zfac_prev"] = np.asarray(z_next, dtype=float).copy()
        if "T_top_drum_pressure_used_F" in diag:
            try:
                top_t = float(np.asarray(diag["T_top_drum_pressure_used_F"], dtype=float).reshape((-1,))[0])
                if np.isfinite(top_t):
                    updates["top_drum_pressure_T_prev_F"] = float(top_t)
            except Exception:
                pass
        if not updates:
            break
        inputs_iter = replace(inputs_iter, **updates)

    diag["pv_inner_iter_count"] = np.array([float(iter_count)], dtype=float)
    diag["pv_inner_converged"] = np.array([1.0 if converged else 0.0], dtype=float)
    diag["pv_inner_dp_max_psia"] = np.array([float(dp_last)], dtype=float)
    diag["pv_inner_dv_max_lbmolph"] = np.array([float(dv_last)], dtype=float)
    return dydt, diag


def _solve_dae_pilot_algebraic(
    *,
    t_s: float,
    y: np.ndarray,
    col: ColumnSpec,
    layout: StateVectorLayout,
    inputs: ColumnInputs,
    max_iter: int,
    p_tol_psia: Optional[float],
    v_tol_lbmolph: Optional[float],
    jac_rel_step: float,
    line_search_max: int,
    rhs_func: Optional[Any] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Pilot simultaneous algebraic solve for z=[P_tray, V_out].

    Differential update remains explicit in time. Within a timestep, this
    routine iterates algebraic consistency using finite-difference Newton
    updates on:
      r_p = z_p - P_rhs(t, y, z)
      r_v = z_v - V_rhs(t, y, z)
    """
    rhs_callable = rhs_func if rhs_func is not None else column_rhs
    y_arr = np.asarray(y, dtype=float).reshape((-1,))
    n_stages = int(getattr(col, "n_stages", 0))
    if n_stages <= 0:
        dydt, diag = rhs_callable(float(t_s), y_arr, col, layout, inputs=inputs)
        return np.asarray(dydt, dtype=float).reshape((-1,)), dict(diag)

    try:
        n_iter = max(1, int(max_iter))
    except Exception:
        n_iter = 1
    try:
        ls_max = max(1, int(line_search_max))
    except Exception:
        ls_max = 1

    def _norm_tol(val: Optional[float]) -> Optional[float]:
        if val is None:
            return None
        try:
            v = float(val)
        except Exception:
            return None
        if not np.isfinite(v) or v <= 0.0:
            return None
        return v

    p_tol = _norm_tol(p_tol_psia)
    v_tol = _norm_tol(v_tol_lbmolph)
    try:
        jac_rel = float(jac_rel_step)
    except Exception:
        jac_rel = 1.0e-6
    if (not np.isfinite(jac_rel)) or jac_rel <= 0.0:
        jac_rel = 1.0e-6

    p_fallback = None
    if hasattr(col, "P_psia"):
        try:
            p_fallback = np.asarray(getattr(col, "P_psia"), dtype=float).reshape((n_stages,))
        except Exception:
            p_fallback = None
    if p_fallback is None:
        p_fallback = np.full(n_stages, 200.0, dtype=float)

    v_fallback = None
    if hasattr(col, "V_lbmolph"):
        try:
            v_fallback = np.asarray(getattr(col, "V_lbmolph"), dtype=float).reshape((n_stages,))
        except Exception:
            v_fallback = None
    if v_fallback is None:
        v_fallback = np.zeros(n_stages, dtype=float)

    seed_diag: Dict[str, np.ndarray] = {}
    if inputs.P_tray_prev is not None:
        try:
            seed_diag["P_psia_hyd"] = np.asarray(inputs.P_tray_prev, dtype=float).reshape((n_stages,))
        except Exception:
            pass
    if inputs.V_out_prev_lbmolph is not None:
        try:
            seed_diag["V_out_lbmolph"] = np.asarray(inputs.V_out_prev_lbmolph, dtype=float).reshape((n_stages,))
        except Exception:
            pass
    z_seed = default_algebraic_seed(
        n_stages=n_stages,
        diag=(seed_diag if seed_diag else None),
        p_fallback_psia=p_fallback,
        v_fallback_lbmolph=v_fallback,
    )
    z_work = np.asarray(z_seed, dtype=float).copy()

    def _alg_residual(z_trial: np.ndarray) -> np.ndarray:
        rr = evaluate_pilot_residual(
            t_s=float(t_s),
            y=y_arr,
            ydot=np.zeros_like(y_arr),
            z=np.asarray(z_trial, dtype=float),
            col=col,
            layout=layout,
            inputs=inputs,
            rhs_func=rhs_callable,
        )
        return np.concatenate([rr.alg_pressure, rr.alg_vapor], axis=0)

    converged = False
    iter_count = 0
    final_rr = None
    alg_p_inf = float("nan")
    alg_v_inf = float("nan")
    alg_full_inf = float("nan")
    failed = False

    try:
        for it in range(n_iter):
            rr = evaluate_pilot_residual(
                t_s=float(t_s),
                y=y_arr,
                ydot=np.zeros_like(y_arr),
                z=z_work,
                col=col,
                layout=layout,
                inputs=inputs,
                rhs_func=rhs_callable,
            )
            iter_count = int(it + 1)
            alg_vec = np.concatenate([rr.alg_pressure, rr.alg_vapor], axis=0)
            alg_p_inf = inf_norm(rr.alg_pressure)
            alg_v_inf = inf_norm(rr.alg_vapor)
            alg_full_inf = inf_norm(alg_vec)
            final_rr = rr

            p_ok = True if p_tol is None else (np.isfinite(alg_p_inf) and alg_p_inf <= float(p_tol))
            v_ok = True if v_tol is None else (np.isfinite(alg_v_inf) and alg_v_inf <= float(v_tol))
            if p_ok and v_ok:
                converged = True
                break
            if it >= (n_iter - 1):
                break

            J = finite_difference_jacobian(_alg_residual, z_work, rel_step=jac_rel)
            if J.shape[0] != alg_vec.size or J.shape[1] != z_work.size:
                failed = True
                break
            if (not np.all(np.isfinite(J))) or (not np.all(np.isfinite(alg_vec))):
                failed = True
                break
            delta, *_ = np.linalg.lstsq(J, -alg_vec, rcond=None)
            delta = np.asarray(delta, dtype=float).reshape((z_work.size,))
            if not np.all(np.isfinite(delta)):
                failed = True
                break

            base_norm = inf_norm(alg_vec)
            accepted = False
            alpha = 1.0
            for _ls in range(ls_max):
                z_try = z_work + float(alpha) * delta
                alg_try = _alg_residual(z_try)
                n_try = inf_norm(alg_try)
                if np.isfinite(n_try) and ((not np.isfinite(base_norm)) or n_try <= base_norm):
                    z_work = np.asarray(z_try, dtype=float)
                    accepted = True
                    break
                alpha *= 0.5
            if not accepted:
                failed = True
                break

        if final_rr is None:
            final_rr = evaluate_pilot_residual(
                t_s=float(t_s),
                y=y_arr,
                ydot=np.zeros_like(y_arr),
                z=z_work,
                col=col,
                layout=layout,
                inputs=inputs,
                rhs_func=rhs_callable,
            )

        rr_consistent = evaluate_pilot_residual(
            t_s=float(t_s),
            y=y_arr,
            ydot=np.asarray(final_rr.dydt_rhs, dtype=float),
            z=z_work,
            col=col,
            layout=layout,
            inputs=inputs,
            rhs_func=rhs_callable,
        )
        dydt_out = np.asarray(rr_consistent.dydt_rhs, dtype=float).reshape((-1,))
        diag_out = dict(rr_consistent.diag)
    except Exception:
        failed = True
        dydt_out, diag_fallback = rhs_callable(float(t_s), y_arr, col, layout, inputs=inputs)
        dydt_out = np.asarray(dydt_out, dtype=float).reshape((-1,))
        diag_out = dict(diag_fallback)

    z_update_inf = inf_norm(np.asarray(z_work, dtype=float) - np.asarray(z_seed, dtype=float))
    diag_out["dae_pilot_enabled"] = np.array([1.0], dtype=float)
    diag_out["dae_pilot_iter_count"] = np.array([float(iter_count)], dtype=float)
    diag_out["dae_pilot_converged"] = np.array([1.0 if converged else 0.0], dtype=float)
    diag_out["dae_pilot_failed"] = np.array([1.0 if failed else 0.0], dtype=float)
    diag_out["dae_pilot_alg_p_inf_psia"] = np.array([float(alg_p_inf)], dtype=float)
    diag_out["dae_pilot_alg_v_inf_lbmolph"] = np.array([float(alg_v_inf)], dtype=float)
    diag_out["dae_pilot_alg_full_inf"] = np.array([float(alg_full_inf)], dtype=float)
    diag_out["dae_pilot_z_update_inf"] = np.array([float(z_update_inf)], dtype=float)
    return dydt_out, diag_out


def _initialize_vapor_holdup_from_spec_pressure(
    *,
    col: ColumnSpec,
    layout: StateVectorLayout,
    y: np.ndarray,
    inputs: ColumnInputs,
    include_temperature: bool,
) -> np.ndarray:
    """Initialize tray vapor holdup MV from P_spec using PV=nZRT/V.

    Done once at t=0 so PV diagnostic pressure starts near specified pressure profile.
    Stage index 0 (condenser) left as MV=0.
    """
    if not layout.include_vapor:
        return y

    P_spec = getattr(col, "P_psia", None)
    if P_spec is None:
        return y
    P_spec = np.asarray(P_spec, dtype=float).reshape((col.n_stages,))

    N = col.n_stages
    Z0 = None
    if inputs.Zfac_prev is not None:
        try:
            Z0 = np.asarray(inputs.Zfac_prev, dtype=float).reshape((N,))
        except Exception:
            Z0 = None
    if Z0 is None:
        # One thermo pass at t=0 to get Z_tray (if available)
        init_inputs = replace(inputs, equilibrium_relaxation=False)
        _dydt0, diag0 = column_rhs(0.0, y, col, layout, inputs=init_inputs)
        Z0 = np.asarray(diag0.get("Z_tray", np.ones(N, dtype=float)), dtype=float).reshape((N,))
    Z0 = np.where(~np.isfinite(Z0) | (Z0 <= 0.0), 1.0, Z0)

    T_F = _tray_temperature_F(col, layout, y, include_temperature)
    T_R = T_F + 459.67
    T_R = np.where(~np.isfinite(T_R) | (T_R <= 1e-6), 559.67, T_R)

    V = _vapor_volume_ft3_per_stage(inputs.volume_model, N)

    R = 10.7316  # (psia*ft3)/(lbmol*R)

    MV_target = np.zeros(N, dtype=float)
    for i in range(N):
        if i == 0:
            MV_target[i] = 0.0
            continue
        Pi = float(P_spec[i])
        if not np.isfinite(Pi) or Pi <= 0.0:
            MV_target[i] = np.nan
            continue
        MV_target[i] = Pi * V[i] / (Z0[i] * R * T_R[i])

    u = layout.unpack(y)

    # Apply to tray vapor component holdups using vapor composition from col.y0
    # (fallback to current y state if col.y0 is unavailable).
    try:
        yfrac = np.asarray(getattr(col, "y0"), dtype=float).reshape((N, col.n_components))
        for i in range(N):
            yfrac[i, :] = _normalize_comp(np.where(np.isfinite(yfrac[i, :]), yfrac[i, :], 0.0))
    except Exception:
        yfrac = np.asarray(u["y_tray"], dtype=float).reshape((N, col.n_components))
        yfrac = np.where(np.isfinite(yfrac), yfrac, 0.0)

    tray_V = np.asarray(u["tray_V"], dtype=float).reshape((N, col.n_components)).copy()
    for i in range(N):
        if i == 0:
            tray_V[i, :] = 0.0
            continue
        if not np.isfinite(MV_target[i]) or MV_target[i] < 0.0:
            continue
        tray_V[i, :] = float(MV_target[i]) * _normalize_comp(yfrac[i, :])

    sl = layout.slices()
    y_new = np.asarray(y, dtype=float).copy()
    y_new[sl["tray_V"]] = tray_V.ravel(order="C")
    if layout.include_energy and ("tray_EV_BTU" in sl):
        try:
            tray_EV_prev = np.asarray(u["tray_EV_BTU"], dtype=float).reshape((N,))
            MV_prev = np.sum(np.asarray(u["tray_V"], dtype=float).reshape((N, col.n_components)), axis=1)
            hV_prev = tray_EV_prev / np.maximum(MV_prev, float(layout.epsilon_lbmol))
            hV_prev = np.where(np.isfinite(hV_prev), hV_prev, T_F)

            MV_new = np.sum(np.asarray(tray_V, dtype=float), axis=1)
            tray_EV_new = hV_prev * MV_new
            tray_EV_new = np.where(np.isfinite(tray_EV_new), tray_EV_new, 0.0)
            tray_EV_new[MV_new <= float(layout.epsilon_lbmol)] = 0.0
            y_new[sl["tray_EV_BTU"]] = tray_EV_new
        except Exception:
            pass

    # Optional top-drum vapor initialization from top pressure specification.
    if layout.include_top and layout.include_vapor and ("top_V" in sl):
        top_vol = inputs.top_drum_vapor_volume_ft3
        top_total_vol = inputs.top_drum_total_volume_ft3
        if top_total_vol is not None and np.isfinite(float(top_total_vol)) and float(top_total_vol) > 0.0:
            rho_top = None
            if inputs.thermo_provider is not None and hasattr(inputs.thermo_provider, "liquid_density_lbmol_ft3"):
                try:
                    x_top = np.asarray(u["top_L"], dtype=float).reshape((col.n_components,))
                    x_top = _normalize_comp(np.where(np.isfinite(x_top), x_top, 0.0))
                    rho_try = float(
                        inputs.thermo_provider.liquid_density_lbmol_ft3(
                            float(T_F[0]),
                            float(P_spec[0]) if np.isfinite(float(P_spec[0])) else 200.0,
                            x_top,
                        )
                    )
                    if np.isfinite(rho_try) and rho_try > 1e-12:
                        rho_top = rho_try
                except Exception:
                    rho_top = None
            if rho_top is not None:
                try:
                    m_top = float(np.sum(np.asarray(u["top_L"], dtype=float).reshape((col.n_components,))))
                    liq_vol = max(m_top / float(rho_top), 0.0)
                    liq_vol = float(np.clip(liq_vol, 0.0, float(top_total_vol)))
                    top_vol = float(top_total_vol) - liq_vol
                    if top_vol < 1e-3:
                        top_vol = 1e-3
                except Exception:
                    top_vol = inputs.top_drum_vapor_volume_ft3
        if top_vol is None:
            try:
                top_vol = float(V[0])
            except Exception:
                top_vol = None
        if top_vol is not None and np.isfinite(float(top_vol)) and float(top_vol) > 0.0:
            p_top = float(P_spec[0]) if np.isfinite(float(P_spec[0])) and float(P_spec[0]) > 0.0 else np.nan
            if np.isfinite(p_top):
                # Keep top-drum initialization on the same ideal-gas Z basis
                # used by dynamic top-drum pressure diagnostics.
                z_top = 1.0
                mv_top = p_top * float(top_vol) / max(z_top * R * T_R[0], 1e-12)
                mv_top = max(float(mv_top), 0.0)
                top_y_src_idx = 1 if N > 1 else 0
                top_y = _normalize_comp(yfrac[top_y_src_idx, :])
                y_new[sl["top_V"]] = (mv_top * top_y).reshape((-1,))
    return y_new


def _initialize_thermo_consistent_state(
    *,
    col: ColumnSpec,
    layout: StateVectorLayout,
    y: np.ndarray,
    inputs: ColumnInputs,
    include_temperature: bool,
    max_iter: int = 2,
    relaxation: float = 1.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Startup conditioning of tray phase compositions (and optional energy states)
    using thermo-equilibrium targets at tray T/P.

    This keeps stage holdup totals fixed while projecting x/y toward x_eq/y_eq,
    then reapplies pressure-consistent vapor-holdup initialization.
    """
    info: Dict[str, Any] = {
        "attempted": False,
        "success": False,
        "n_iter": 0,
        "max_dx": np.nan,
        "max_dy": np.nan,
        "eq_phase_change_init_lbmolps": np.nan,
        "eq_phase_change_final_lbmolps": np.nan,
    }
    if (not layout.include_vapor) or (inputs.thermo_provider is None):
        return np.asarray(y, dtype=float), info

    try:
        n_iter = max(1, int(max_iter))
    except Exception:
        n_iter = 1
    try:
        lam = float(relaxation)
    except Exception:
        lam = 1.0
    lam = float(np.clip(lam, 0.0, 1.0))
    if lam <= 0.0:
        return np.asarray(y, dtype=float), info

    N = int(col.n_stages)
    Nc = int(col.n_components)
    sl = layout.slices()
    y_work = np.asarray(y, dtype=float).copy()
    info["attempted"] = True

    dx_max = 0.0
    dy_max = 0.0
    eq_init = np.nan

    for it in range(n_iter):
        eval_inputs = replace(inputs, compute_thermo_diag=True, equilibrium_relaxation=True)
        try:
            _dydt, diag = column_rhs(0.0, y_work, col, layout, inputs=eval_inputs)
        except Exception:
            break

        x_eq_raw = diag.get("x_eq_tray", None)
        y_eq_raw = diag.get("y_eq_tray", None)
        if x_eq_raw is None or y_eq_raw is None:
            break
        try:
            x_eq = np.asarray(x_eq_raw, dtype=float).reshape((N, Nc))
            y_eq = np.asarray(y_eq_raw, dtype=float).reshape((N, Nc))
        except Exception:
            break

        if np.isnan(eq_init):
            try:
                eq_rate = np.asarray(diag.get("eq_phase_change_lbmolps_tray"), dtype=float).reshape((N,))
                if np.any(np.isfinite(eq_rate)):
                    eq_init = float(np.nanmax(np.abs(eq_rate)))
            except Exception:
                pass

        u = layout.unpack(y_work)
        tray_L = np.asarray(u["tray_L"], dtype=float).reshape((N, Nc))
        tray_V = np.asarray(u["tray_V"], dtype=float).reshape((N, Nc))
        ML_tot = np.sum(tray_L, axis=1).reshape((N,))
        MV_tot = np.sum(tray_V, axis=1).reshape((N,))
        x_old = np.asarray(u["x_tray"], dtype=float).reshape((N, Nc))
        y_old = np.asarray(u["y_tray"], dtype=float).reshape((N, Nc))

        x_new_frac = np.zeros((N, Nc), dtype=float)
        y_new_frac = np.zeros((N, Nc), dtype=float)
        for i in range(N):
            x_tgt = np.where(np.isfinite(x_eq[i, :]), x_eq[i, :], x_old[i, :])
            y_tgt = np.where(np.isfinite(y_eq[i, :]), y_eq[i, :], y_old[i, :])
            x_new_frac[i, :] = _normalize_comp((1.0 - lam) * x_old[i, :] + lam * x_tgt)
            y_new_frac[i, :] = _normalize_comp((1.0 - lam) * y_old[i, :] + lam * y_tgt)

        tray_L_new = ML_tot[:, None] * x_new_frac
        tray_V_new = MV_tot[:, None] * y_new_frac
        if N > 0:
            tray_V_new[0, :] = 0.0

        y_new = y_work.copy()
        y_new[sl["tray_L"]] = tray_L_new.ravel(order="C")
        y_new[sl["tray_V"]] = tray_V_new.ravel(order="C")

        # Align boundary holdup compositions with neighboring tray targets
        # while preserving boundary total inventories.
        if layout.include_top and ("top_L" in sl):
            top_L_vec = np.asarray(u.get("top_L", np.zeros(Nc, dtype=float)), dtype=float).reshape((Nc,))
            m_top_L = max(float(np.sum(top_L_vec)), 0.0)
            y_new[sl["top_L"]] = m_top_L * x_new_frac[0, :]
            if layout.include_vapor and ("top_V" in sl):
                top_V_vec = np.asarray(u.get("top_V", np.zeros(Nc, dtype=float)), dtype=float).reshape((Nc,))
                m_top_V = max(float(np.sum(top_V_vec)), 0.0)
                src = 1 if N > 1 else 0
                y_new[sl["top_V"]] = m_top_V * y_new_frac[src, :]
        if layout.include_bottom and ("bottom_L" in sl):
            bot_L_vec = np.asarray(u.get("bottom_L", np.zeros(Nc, dtype=float)), dtype=float).reshape((Nc,))
            m_bot_L = max(float(np.sum(bot_L_vec)), 0.0)
            y_new[sl["bottom_L"]] = m_bot_L * x_new_frac[-1, :]
            if layout.include_vapor and ("bottom_V" in sl):
                bot_V_vec = np.asarray(u.get("bottom_V", np.zeros(Nc, dtype=float)), dtype=float).reshape((Nc,))
                m_bot_V = max(float(np.sum(bot_V_vec)), 0.0)
                y_new[sl["bottom_V"]] = m_bot_V * y_new_frac[-1, :]

        y_new = _clamp_nonnegative_holdups(y_new, layout)
        y_new = _clip_temperature_states_to_provider_bounds(y_new, layout, inputs.thermo_provider)

        z_seed = None
        if "Z_tray" in diag:
            try:
                z_seed = np.asarray(diag["Z_tray"], dtype=float).reshape((N,))
            except Exception:
                z_seed = None
        init_inputs = replace(inputs, Zfac_prev=z_seed) if z_seed is not None else inputs
        y_new = _initialize_vapor_holdup_from_spec_pressure(
            col=col,
            layout=layout,
            y=y_new,
            inputs=init_inputs,
            include_temperature=include_temperature,
        )

        if bool(getattr(layout, "include_energy", False)):
            try:
                u_energy = layout.unpack(y_new)
                if ("tray_EL_BTU" in sl) and ("HL_BTU_lbmol_tray" in diag):
                    HL = np.asarray(diag["HL_BTU_lbmol_tray"], dtype=float).reshape((N,))
                    HL = np.where(np.isfinite(HL), HL, 0.0)
                    ML_now = np.asarray(u_energy["ML_tot_tray"], dtype=float).reshape((N,))
                    y_new[sl["tray_EL_BTU"]] = ML_now * HL
                if ("tray_EV_BTU" in sl) and ("HV_BTU_lbmol_tray" in diag):
                    HV = np.asarray(diag["HV_BTU_lbmol_tray"], dtype=float).reshape((N,))
                    HV = np.where(np.isfinite(HV), HV, 0.0)
                    MV_now = np.asarray(u_energy["MV_tot_tray"], dtype=float).reshape((N,))
                    y_new[sl["tray_EV_BTU"]] = MV_now * HV
            except Exception:
                pass

        try:
            u_after = layout.unpack(y_new)
            x_after = np.asarray(u_after["x_tray"], dtype=float).reshape((N, Nc))
            y_after = np.asarray(u_after["y_tray"], dtype=float).reshape((N, Nc))
            dx = float(np.nanmax(np.abs(x_after - x_old)))
            dy = float(np.nanmax(np.abs(y_after - y_old)))
            if np.isfinite(dx):
                dx_max = max(dx_max, dx)
            if np.isfinite(dy):
                dy_max = max(dy_max, dy)
        except Exception:
            pass

        y_work = y_new
        info["n_iter"] = int(it + 1)

    eq_final = np.nan
    try:
        eval_inputs = replace(inputs, compute_thermo_diag=True, equilibrium_relaxation=True)
        _dydt_f, diag_f = column_rhs(0.0, y_work, col, layout, inputs=eval_inputs)
        if "eq_phase_change_lbmolps_tray" in diag_f:
            eq_rate_f = np.asarray(diag_f["eq_phase_change_lbmolps_tray"], dtype=float).reshape((N,))
            if np.any(np.isfinite(eq_rate_f)):
                eq_final = float(np.nanmax(np.abs(eq_rate_f)))
    except Exception:
        pass

    info["max_dx"] = float(dx_max) if np.isfinite(dx_max) else np.nan
    info["max_dy"] = float(dy_max) if np.isfinite(dy_max) else np.nan
    info["eq_phase_change_init_lbmolps"] = float(eq_init) if np.isfinite(eq_init) else np.nan
    info["eq_phase_change_final_lbmolps"] = float(eq_final) if np.isfinite(eq_final) else np.nan

    success = bool(info["n_iter"] > 0)
    if np.isfinite(eq_init) and np.isfinite(eq_final):
        success = success and (float(eq_final) <= float(eq_init) + 1e-12)
    info["success"] = bool(success)
    return y_work, info


def _initialize_top_drum_dynamic_steady(
    *,
    col: ColumnSpec,
    layout: StateVectorLayout,
    y: np.ndarray,
    inputs: ColumnInputs,
    max_iter: int = 6,
    tol_lbmolps: float = 1e-6,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Best-effort startup trim for top-drum holdups.

    Adjust top liquid/vapor total holdups at t=0 (holding compositions fixed)
    to reduce top-drum accumulation residuals computed by RHS:
      d(top_L_total)/dt and d(top_V_total)/dt.
    """
    info: Dict[str, Any] = {
        "attempted": False,
        "success": False,
        "n_iter": 0,
        "pressure_coupled": False,
        "d_top_L_init_lbmolps": np.nan,
        "d_top_V_init_lbmolps": np.nan,
        "d_top_L_final_lbmolps": np.nan,
        "d_top_V_final_lbmolps": np.nan,
    }

    sl = layout.slices()
    if (not layout.include_top) or (not layout.include_vapor):
        return np.asarray(y, dtype=float), info
    if ("top_L" not in sl) or ("top_V" not in sl):
        return np.asarray(y, dtype=float), info

    y_work = np.asarray(y, dtype=float).copy()
    try:
        u0 = layout.unpack(y_work)
    except Exception:
        return y_work, info

    top_L0 = np.asarray(u0.get("top_L", []), dtype=float).reshape((-1,))
    top_V0 = np.asarray(u0.get("top_V", []), dtype=float).reshape((-1,))
    Nc = int(getattr(col, "n_components", 0))
    Ns = int(getattr(col, "n_stages", 0))
    if top_L0.size != Nc or top_V0.size != Nc or Nc <= 0:
        return y_work, info

    x_top = _normalize_comp(np.where(np.isfinite(top_L0), top_L0, 0.0))
    if np.sum(np.where(np.isfinite(top_V0), top_V0, 0.0)) > float(layout.epsilon_lbmol):
        y_top = _normalize_comp(np.where(np.isfinite(top_V0), top_V0, 0.0))
    else:
        y_tray = np.asarray(u0.get("y_tray", []), dtype=float)
        if y_tray.size == (Ns * Nc):
            y_tray = y_tray.reshape((Ns, Nc))
            src = 1 if Ns > 1 else 0
            y_top = _normalize_comp(np.where(np.isfinite(y_tray[src, :]), y_tray[src, :], 0.0))
        else:
            y_top = x_top.copy()

    p_target = None
    try:
        p0 = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[0])
        if np.isfinite(p0) and p0 > 0.0:
            p_target = float(p0)
    except Exception:
        p_target = None

    try:
        t_top_f = float(np.asarray(u0.get("tray_T_f"), dtype=float).reshape((Ns,))[0])
    except Exception:
        try:
            t_top_f = float(np.asarray(getattr(col, "T_f"), dtype=float).reshape((Ns,))[0])
        except Exception:
            t_top_f = 100.0
    if (not np.isfinite(t_top_f)):
        t_top_f = 100.0

    # Keep startup top-drum pressure coupling on ideal-gas Z basis for
    # consistency with dynamic top-drum pressure diagnostics.
    z_top = 1.0

    rho_top = None
    if inputs.rhoL_tray_lbmol_ft3 is not None:
        try:
            rho_try = float(np.asarray(inputs.rhoL_tray_lbmol_ft3, dtype=float).reshape((Ns,))[0])
            if np.isfinite(rho_try) and rho_try > 1e-12:
                rho_top = float(rho_try)
        except Exception:
            rho_top = None
    if rho_top is None and inputs.thermo_provider is not None and hasattr(inputs.thermo_provider, "liquid_density_lbmol_ft3"):
        try:
            p_for_rho = float(p_target) if p_target is not None else 200.0
            rho_try = float(inputs.thermo_provider.liquid_density_lbmol_ft3(float(t_top_f), p_for_rho, x_top))
            if np.isfinite(rho_try) and rho_try > 1e-12:
                rho_top = float(rho_try)
        except Exception:
            rho_top = None

    top_total_vol = None
    if inputs.top_drum_total_volume_ft3 is not None:
        try:
            vtot = float(inputs.top_drum_total_volume_ft3)
            if np.isfinite(vtot) and vtot > 0.0:
                top_total_vol = float(vtot)
        except Exception:
            top_total_vol = None

    top_vap_fixed = None
    if inputs.top_drum_vapor_volume_ft3 is not None:
        try:
            vv = float(inputs.top_drum_vapor_volume_ft3)
            if np.isfinite(vv) and vv > 0.0:
                top_vap_fixed = float(vv)
        except Exception:
            top_vap_fixed = None
    if top_vap_fixed is None:
        try:
            vv = _vapor_volume_ft3_per_stage(inputs.volume_model, Ns)
            top_vap_fixed = float(vv[0])
        except Exception:
            top_vap_fixed = None

    def _top_vapor_volume_for_mL(mL: float) -> Optional[float]:
        if top_total_vol is not None and rho_top is not None:
            liq_vol = float(np.clip(float(mL) / max(float(rho_top), 1e-12), 0.0, float(top_total_vol)))
            return max(float(top_total_vol) - liq_vol, 1e-3)
        if top_vap_fixed is not None and np.isfinite(top_vap_fixed) and top_vap_fixed > 0.0:
            return max(float(top_vap_fixed), 1e-3)
        return None

    def _mV_anchor_from_mL(mL: float) -> Optional[float]:
        if p_target is None:
            return None
        vap_vol = _top_vapor_volume_for_mL(mL)
        if vap_vol is None:
            return None
        T_R = float(t_top_f) + 459.67
        if (not np.isfinite(T_R)) or T_R <= 0.0:
            return None
        Z = float(z_top) if np.isfinite(float(z_top)) and float(z_top) > 0.0 else 1.0
        R = 10.7316
        mv = float(p_target) * float(vap_vol) / max(float(Z) * float(R) * float(T_R), 1e-12)
        if not np.isfinite(mv):
            return None
        return max(float(mv), 0.0)

    pressure_coupled = _mV_anchor_from_mL(float(np.sum(top_L0))) is not None
    info["pressure_coupled"] = bool(pressure_coupled)

    def _pack_top_totals(base_y: np.ndarray, mL: float, mV: float) -> np.ndarray:
        y_new = np.asarray(base_y, dtype=float).copy()
        mL_eff = max(float(mL), 0.0)
        mV_eff = max(float(mV), 0.0)
        if pressure_coupled:
            mv_anchor = _mV_anchor_from_mL(mL_eff)
            if mv_anchor is not None:
                mV_eff = float(mv_anchor)
        y_new[sl["top_L"]] = mL_eff * x_top
        y_new[sl["top_V"]] = mV_eff * y_top
        return y_new

    def _residual(mL: float, mV: float) -> Tuple[Optional[np.ndarray], np.ndarray]:
        y_try = _pack_top_totals(y_work, mL, mV)
        try:
            dydt, _diag = column_rhs(0.0, y_try, col, layout, inputs=inputs)
            dL = float(np.sum(np.asarray(dydt[sl["top_L"]], dtype=float).reshape((-1,))))
            dV = float(np.sum(np.asarray(dydt[sl["top_V"]], dtype=float).reshape((-1,))))
            if np.isfinite(dL) and np.isfinite(dV):
                return np.array([dL, dV], dtype=float), y_try
        except Exception:
            pass
        return None, y_try

    mL = max(float(np.sum(top_L0)), 0.0)
    mV = max(float(np.sum(top_V0)), 0.0)
    if pressure_coupled:
        mv_anchor0 = _mV_anchor_from_mL(mL)
        if mv_anchor0 is not None:
            mV = float(mv_anchor0)

    f, y_best = _residual(mL, mV)
    if f is None:
        return y_work, info

    info["attempted"] = True
    info["d_top_L_init_lbmolps"] = float(f[0])
    info["d_top_V_init_lbmolps"] = float(f[1])
    best_norm = float(np.linalg.norm(f))
    f_best = f.copy()

    var_idx = [0] if pressure_coupled else [0, 1]
    for it in range(int(max_iter)):
        info["n_iter"] = int(it + 1)
        if np.max(np.abs(f_best)) <= float(tol_lbmolps):
            info["success"] = True
            break

        J = np.zeros((2, len(var_idx)), dtype=float)
        valid = np.zeros(len(var_idx), dtype=bool)
        for jj, var in enumerate(var_idx):
            base = mL if var == 0 else mV
            dvar = max(0.05 * max(abs(base), 1.0), 1.0e-3)
            mL_p = mL + (dvar if var == 0 else 0.0)
            mV_p = mV + (dvar if var == 1 else 0.0)
            f_p, _ = _residual(mL_p, mV_p)
            if f_p is None:
                continue
            J[:, jj] = (f_p - f_best) / dvar
            valid[jj] = True

        if not np.any(valid):
            break
        J_use = J[:, valid]
        try:
            delta_use, *_ = np.linalg.lstsq(J_use, -f_best, rcond=None)
        except Exception:
            break

        delta = np.zeros(2, dtype=float)
        for jj, var in enumerate(var_idx):
            if valid[jj]:
                delta[var] = float(np.asarray(delta_use, dtype=float).reshape((-1,))[int(np.sum(valid[:jj]))])

        max_dL = max(0.5 * max(mL, 1.0), 1.0)
        max_dV = max(0.5 * max(mV, 1.0), 1.0)
        delta[0] = float(np.clip(delta[0], -max_dL, max_dL))
        delta[1] = float(np.clip(delta[1], -max_dV, max_dV))

        improved = False
        for fac in (1.0, 0.5, 0.25, 0.1):
            mL_try = max(mL + fac * float(delta[0]), 0.0)
            mV_try = max(mV + fac * float(delta[1]), 0.0)
            f_try, y_try = _residual(mL_try, mV_try)
            if f_try is None:
                continue
            n_try = float(np.linalg.norm(f_try))
            if n_try + 1e-12 < best_norm:
                mL = float(mL_try)
                mV = float(np.sum(np.asarray(y_try[sl["top_V"]], dtype=float).reshape((-1,))))
                f_best = f_try.copy()
                y_best = y_try.copy()
                best_norm = n_try
                improved = True
                break
        if not improved:
            break

    info["d_top_L_final_lbmolps"] = float(f_best[0])
    info["d_top_V_final_lbmolps"] = float(f_best[1])
    if np.max(np.abs(f_best)) <= float(tol_lbmolps):
        info["success"] = True
    return y_best, info


# -------------------------
# Logging row writers
# -------------------------


def _resolve_logging_streams(case: CaseData, col: ColumnSpec) -> Tuple[StreamTag, StreamTag, StreamTag]:
    """
    Resolve feed, distillate, bottoms for logging purposes.

    - Feed: prefers named stream "Feed" (or alias); if no stage in stream, tries specs_raw.
    - Distillate: prefers named stream "Distillate"; default stage=1 if missing.
    - Bottoms: prefers named stream "Bottoms"; default stage=N if missing.
    """
    N = col.n_stages

    feed = _lookup_named_stream(col=col, case=case, aliases=("Feed",))
    dist = _lookup_named_stream(col=col, case=case, aliases=("Distillate", "Dist", "Overhead", "D"))
    bots = _lookup_named_stream(col=col, case=case, aliases=("Bottoms", "Bottom", "B"))

    # Feed stage fallback from specs_raw
    if feed.stage_1based is None:
        feed_stage = _lookup_spec_int(col, ("Feed Stage", "Feed stage", "Feed Stage (1-based)"))
        feed = StreamTag(name=feed.name, flow_lbmolph=feed.flow_lbmolph, stage_1based=feed_stage)

    # Distillate/bottoms defaults
    if dist.stage_1based is None:
        dist = StreamTag(name=dist.name, flow_lbmolph=dist.flow_lbmolph, stage_1based=1)
    if bots.stage_1based is None:
        bots = StreamTag(name=bots.name, flow_lbmolph=bots.flow_lbmolph, stage_1based=N)

    # Clamp stages into [1, N]
    def clamp(tag: StreamTag) -> StreamTag:
        st = tag.stage_1based
        if st is None:
            return tag
        if 1 <= int(st) <= N:
            return StreamTag(name=tag.name, flow_lbmolph=tag.flow_lbmolph, stage_1based=int(st))
        return StreamTag(name=tag.name, flow_lbmolph=tag.flow_lbmolph, stage_1based=None)

    return clamp(feed), clamp(dist), clamp(bots)


def _infer_condenser_duty_bias_btu_per_h(col: ColumnSpec) -> float:
    specs = getattr(col, "specs_raw", None) or {}
    q = _spec_float(specs, "Condenser Duty (Btu/h)")
    if q is None:
        try:
            duties = getattr(col, "duties", None)
            if duties is not None and getattr(duties, "q_cond_btu_per_h", None) is not None:
                q = float(getattr(duties, "q_cond_btu_per_h"))
        except Exception:
            q = None
    if q is None or (not np.isfinite(float(q))):
        q = -5.0e7
    q = float(q)
    if q > 0.0:
        q = -abs(q)
    return q


def _build_pressure_controller(
    *,
    col: ColumnSpec,
    cfg: RunnerConfig,
) -> Tuple[bool, Optional[PIController], Optional[float], str, Optional[str]]:
    specs = getattr(col, "specs_raw", None) or {}
    enabled = bool(cfg.enable_pressure_control)
    if not enabled:
        b = _as_bool(_spec_get(specs, "Enable Pressure Control", "Pressure Control Enabled"))
        enabled = bool(b) if b is not None else False
    if not enabled:
        return False, None, None, "off", None

    sp = cfg.top_pressure_sp_psia
    if sp is None:
        sp = _spec_float(specs, "Top Pressure SP (psia)", "Condenser Pressure SP (psia)")
    if sp is None:
        try:
            p_ctrl_idx = 0
            sp = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[p_ctrl_idx])
        except Exception:
            sp = None
    if sp is None or (not np.isfinite(float(sp))) or float(sp) <= 0.0:
        return False, None, None, "off", None

    pressure_mode_note: Optional[str] = None
    mv_mode = str(cfg.pressure_control_mv or "auto").strip().lower().replace("_", "-")
    if mv_mode in ("", "auto"):
        mv_mode = str(_spec_get(specs, "Pressure Control MV", "Pressure Controller MV", "Pressure MV") or "auto").strip().lower().replace("_", "-")
    if mv_mode in ("", "auto"):
        if str(cfg.condenser_duty_mode or "").strip().lower() == "total-condense":
            mv_mode = "top-anchor"
        else:
            mv_mode = "condenser-duty"
    if mv_mode in ("duty", "cond-duty", "condenser-duty", "condenserduty"):
        mv_mode = "condenser-duty"
    elif mv_mode in ("top-anchor", "pressure-anchor", "p-anchor", "toppressure"):
        mv_mode = "top-anchor"
    else:
        mv_mode = "top-anchor"

    # Avoid hidden pressure/composition coupling by default:
    # condenser-duty MV with total-condense drives condenser mass-split authority.
    if (
        mv_mode == "condenser-duty"
        and str(cfg.condenser_duty_mode or "").strip().lower() == "total-condense"
        and (not bool(getattr(cfg, "allow_coupled_pressure_duty", False)))
    ):
        mv_mode = "top-anchor"
        pressure_mode_note = (
            "pressure-control-mv=condenser-duty with condenser-duty-mode=total-condense "
            "was auto-switched to top-anchor; use --allow-coupled-pressure-duty to keep coupled duty control."
        )

    kc = cfg.top_pressure_kc
    if kc is None:
        kc = _spec_float(specs, "Top Pressure Kc", "Pressure Controller Kc")
    if kc is None:
        kc = -0.5 if mv_mode == "top-anchor" else -5.0e5

    ti = cfg.top_pressure_ti_sec
    if ti is None:
        ti = _spec_float(specs, "Top Pressure Ti (sec)", "Pressure Controller Ti (sec)")
    if ti is None:
        ti = 120.0

    if mv_mode == "condenser-duty":
        q_bias = float(cfg.condenser_duty_btu_per_h) if cfg.condenser_duty_btu_per_h is not None else _infer_condenser_duty_bias_btu_per_h(col)
        q_min = cfg.condenser_duty_min_btu_per_h
        q_max = cfg.condenser_duty_max_btu_per_h

        if q_min is None:
            q_min = -3.0 * max(abs(q_bias), 1.0)
        if q_max is None:
            q_max = 0.0
        q_min = float(q_min)
        q_max = float(q_max)
        if q_min > q_max:
            q_min, q_max = q_max, q_min

        ctrl = PIController(
            kc=float(kc),
            ti_sec=float(ti),
            bias=float(q_bias),
            out_min=float(q_min),
            out_max=float(q_max),
            integ=0.0,
        )
        return True, ctrl, float(sp), mv_mode, pressure_mode_note

    # top-anchor pressure control mode
    p_ctrl_idx = 0
    try:
        p_bias = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[p_ctrl_idx])
    except Exception:
        p_bias = float(sp)
    if not np.isfinite(p_bias) or p_bias <= 0.0:
        p_bias = float(sp)

    p_min = cfg.top_pressure_anchor_min_psia
    p_max = cfg.top_pressure_anchor_max_psia
    if p_min is None:
        p_min = max(1.0, 0.5 * float(sp))
    if p_max is None:
        p_max = max(1.5 * float(sp), float(sp) + 20.0)
    p_min = float(p_min)
    p_max = float(p_max)
    if p_min > p_max:
        p_min, p_max = p_max, p_min

    ctrl = PIController(
        kc=float(kc),
        ti_sec=float(ti),
        bias=float(p_bias),
        out_min=float(p_min),
        out_max=float(p_max),
        integ=0.0,
    )
    return True, ctrl, float(sp), mv_mode, pressure_mode_note


def _build_level_controllers(
    *,
    col: ColumnSpec,
    cfg: RunnerConfig,
    layout: StateVectorLayout,
    y0: np.ndarray,
    dist_tag: StreamTag,
    bots_tag: StreamTag,
) -> Tuple[bool, Optional[PIController], Optional[PIController], Optional[float], Optional[float]]:
    specs = getattr(col, "specs_raw", None) or {}
    enabled = bool(cfg.enable_level_control)
    if not enabled:
        b = _as_bool(_spec_get(specs, "Enable Level Control", "Level Control Enabled"))
        enabled = bool(b) if b is not None else False
    if not enabled:
        return False, None, None, None, None

    u0 = layout.unpack(np.asarray(y0, dtype=float))
    top0 = float(np.sum(u0["top_L"])) if (layout.include_top and "top_L" in u0) else None
    bot0 = float(np.sum(u0["bottom_L"])) if (layout.include_bottom and "bottom_L" in u0) else None

    sp_top = cfg.top_level_sp_lbmol
    if sp_top is None:
        sp_top = _spec_float(specs, "Top Level SP (lbmol)", "Top Drum Level SP (lbmol)", "Reflux Drum Level SP (lbmol)")
    if sp_top is None and top0 is not None:
        sp_top = float(top0)

    sp_bot = cfg.bottom_level_sp_lbmol
    if sp_bot is None:
        sp_bot = _spec_float(specs, "Bottom Level SP (lbmol)", "Bottom Sump Level SP (lbmol)")
    if sp_bot is None and bot0 is not None:
        sp_bot = float(bot0)

    d_bias = float(dist_tag.flow_lbmolph) if dist_tag.flow_lbmolph is not None else 0.0
    b_bias = float(bots_tag.flow_lbmolph) if bots_tag.flow_lbmolph is not None else 0.0

    top_kc = cfg.top_level_kc
    if top_kc is None:
        top_kc = _spec_float(specs, "Top Level Kc", "Top Level Controller Kc")
    if top_kc is None:
        top_kc = 8.0

    top_ti = cfg.top_level_ti_sec
    if top_ti is None:
        top_ti = _spec_float(specs, "Top Level Ti (sec)", "Top Level Controller Ti (sec)")
    if top_ti is None:
        top_ti = 120.0

    bot_kc = cfg.bottom_level_kc
    if bot_kc is None:
        bot_kc = _spec_float(specs, "Bottom Level Kc", "Bottom Level Controller Kc")
    if bot_kc is None:
        bot_kc = 8.0

    bot_ti = cfg.bottom_level_ti_sec
    if bot_ti is None:
        bot_ti = _spec_float(specs, "Bottom Level Ti (sec)", "Bottom Level Controller Ti (sec)")
    if bot_ti is None:
        bot_ti = 120.0

    d_hi = max(2.5 * max(d_bias, 1.0), d_bias + 5000.0)
    b_hi = max(2.5 * max(b_bias, 1.0), b_bias + 5000.0)

    if sp_top is None or sp_bot is None:
        return False, None, None, None, None

    top_ctrl = PIController(
        kc=float(top_kc),
        ti_sec=float(top_ti),
        bias=float(d_bias),
        out_min=0.0,
        out_max=float(d_hi),
        integ=0.0,
    )
    bot_ctrl = PIController(
        kc=float(bot_kc),
        ti_sec=float(bot_ti),
        bias=float(b_bias),
        out_min=0.0,
        out_max=float(b_hi),
        integ=0.0,
    )
    return True, top_ctrl, bot_ctrl, (float(sp_top) if sp_top is not None else None), (float(sp_bot) if sp_bot is not None else None)


def _component_index_by_name(col: ColumnSpec, token: str) -> Optional[int]:
    tok = _normalize_spec_key(token)
    if not tok:
        return None

    excel_names = list(getattr(col, "components_excel", []) or [])
    dwsim_names = list(getattr(col, "components_dwsim", []) or [])
    n_comp = int(getattr(col, "n_components", len(excel_names)))

    def _aliases_for(i: int) -> List[str]:
        out: List[str] = []
        if i < len(excel_names):
            out.append(_normalize_spec_key(excel_names[i]))
        if i < len(dwsim_names):
            out.append(_normalize_spec_key(dwsim_names[i]))
        for v in list(out):
            if len(v) >= 3 and v.startswith("c") and "h" in v:
                h_pos = v.find("h")
                cnum = v[1:h_pos]
                if cnum.isdigit():
                    out.append(f"c{int(cnum)}")
        return [a for a in out if a]

    all_aliases = [_aliases_for(i) for i in range(n_comp)]
    for i, aliases in enumerate(all_aliases):
        if tok in aliases:
            return i

    carbon_alias = {
        "c1": ("methane",),
        "c2": ("ethane",),
        "c3": ("propane",),
        "c4": ("butane",),
        "c5": ("pentane",),
        "c6": ("hexane",),
        "c7": ("heptane",),
        "c8": ("octane",),
    }
    if tok in carbon_alias:
        hints = tuple(_normalize_spec_key(v) for v in carbon_alias[tok])
        for i, aliases in enumerate(all_aliases):
            for a in aliases:
                for h in hints:
                    if h and h in a:
                        return i

    for i, aliases in enumerate(all_aliases):
        for a in aliases:
            if len(tok) >= 2 and (a.startswith(tok) or tok in a):
                return i
    return None


def _build_distillate_composition_controller(
    *,
    col: ColumnSpec,
    cfg: RunnerConfig,
    boundary: BoundaryFlows,
    dist_tag: StreamTag,
) -> Tuple[bool, Optional[PIController], Optional[float], Optional[int], Optional[str]]:
    specs = getattr(col, "specs_raw", None) or {}
    enabled = bool(cfg.enable_distillate_composition_control)
    if (not enabled) and (cfg.distillate_composition_sp_molfrac is not None):
        enabled = True
    if not enabled:
        b = _as_bool(
            _spec_get(
                specs,
                "Enable Distillate Composition Control",
                "Distillate Composition Control Enabled",
            )
        )
        enabled = bool(b) if b is not None else False
    if not enabled:
        return False, None, None, None, None

    comp_name = str(cfg.distillate_composition_component or "").strip()
    if not comp_name:
        comp_name = str(
            _spec_get(
                specs,
                "Distillate Composition Component",
                "Distillate Controller Component",
            )
            or "C4"
        ).strip()

    comp_idx = _component_index_by_name(col, comp_name)
    if comp_idx is None:
        return False, None, None, None, None

    sp = cfg.distillate_composition_sp_molfrac
    if sp is None:
        sp = _spec_float(
            specs,
            "Distillate Composition SP",
            "Distillate C4 SP",
            "Distillate x SP",
        )
    if sp is None:
        return False, None, None, None, None
    sp = float(sp)
    if (not np.isfinite(sp)) or sp < 0.0 or sp > 1.0:
        return False, None, None, None, None

    kc = cfg.distillate_composition_kc
    if kc is None:
        kc = _spec_float(specs, "Distillate Composition Kc", "Distillate Controller Kc")
    if kc is None:
        kc = 1.0e4

    ti = cfg.distillate_composition_ti_sec
    if ti is None:
        ti = _spec_float(specs, "Distillate Composition Ti (sec)", "Distillate Controller Ti (sec)")
    if ti is None:
        ti = 240.0

    l_bias = float(boundary.reflux_lbmolph) if boundary.reflux_lbmolph is not None else np.nan
    d_bias = float(dist_tag.flow_lbmolph) if dist_tag.flow_lbmolph is not None else np.nan
    if (not np.isfinite(l_bias)) or l_bias < 0.0:
        l_bias = float(np.asarray(getattr(col, "L_lbmolph"), dtype=float).reshape((-1,))[0])

    l_min = cfg.reflux_cmd_min_lbmolph
    l_max = cfg.reflux_cmd_max_lbmolph

    # Backward-compatible fallback: if only ratio clamps are provided, map them
    # to reflux-flow clamps around current distillate flow.
    if l_min is None and cfg.reflux_ratio_min is not None and np.isfinite(d_bias) and d_bias > 0.0:
        l_min = float(cfg.reflux_ratio_min) * float(d_bias)
    if l_max is None and cfg.reflux_ratio_max is not None and np.isfinite(d_bias) and d_bias > 0.0:
        l_max = float(cfg.reflux_ratio_max) * float(d_bias)

    if l_min is None:
        l_min = _spec_float(
            specs,
            "Reflux Flow Min (lbmol/h)",
            "Distillate Composition Reflux Min (lbmol/h)",
        )
    if l_max is None:
        l_max = _spec_float(
            specs,
            "Reflux Flow Max (lbmol/h)",
            "Distillate Composition Reflux Max (lbmol/h)",
        )

    if l_min is None:
        l_min = 0.0
    if l_max is None:
        l_max = max(2.5 * max(float(l_bias), 1.0), float(l_bias) + 5000.0)
    l_min = float(l_min)
    l_max = float(l_max)
    if l_min > l_max:
        l_min, l_max = l_max, l_min

    ctrl = PIController(
        kc=float(kc),
        ti_sec=float(ti),
        bias=float(l_bias),
        out_min=float(l_min),
        out_max=float(l_max),
        integ=0.0,
    )

    comp_label = None
    try:
        comp_label = str(list(getattr(col, "components_excel", []))[int(comp_idx)])
    except Exception:
        comp_label = str(comp_name)
    return True, ctrl, float(sp), int(comp_idx), comp_label


def _build_bottoms_composition_controller(
    *,
    col: ColumnSpec,
    cfg: RunnerConfig,
    boundary: BoundaryFlows,
) -> Tuple[bool, Optional[str], Optional[PIController], Optional[float], Optional[int], Optional[str]]:
    specs = getattr(col, "specs_raw", None) or {}
    enabled = bool(cfg.enable_bottoms_composition_control)
    if (not enabled) and (cfg.bottoms_composition_sp_molfrac is not None):
        enabled = True
    if not enabled:
        b = _as_bool(
            _spec_get(
                specs,
                "Enable Bottoms Composition Control",
                "Bottoms Composition Control Enabled",
            )
        )
        enabled = bool(b) if b is not None else False
    if not enabled:
        return False, None, None, None, None, None

    comp_name = str(cfg.bottoms_composition_component or "").strip()
    if not comp_name:
        comp_name = str(
            _spec_get(
                specs,
                "Bottoms Composition Component",
                "Bottoms Controller Component",
            )
            or "C5"
        ).strip()

    comp_idx = _component_index_by_name(col, comp_name)
    if comp_idx is None:
        return False, None, None, None, None, None

    sp = cfg.bottoms_composition_sp_molfrac
    if sp is None:
        sp = _spec_float(
            specs,
            "Bottoms Composition SP",
            "Bottoms C5 SP",
            "Bottoms x SP",
        )
    if sp is None:
        return False, None, None, None, None, None
    sp = float(sp)
    if (not np.isfinite(sp)) or sp < 0.0 or sp > 1.0:
        return False, None, None, None, None, None

    mv_raw = str(cfg.bottoms_composition_mv or "").strip()
    if not mv_raw:
        mv_raw = str(
            _spec_get(
                specs,
                "Bottoms Composition MV",
                "Bottoms Controller MV",
            )
            or "boilup"
        ).strip()
    mv_norm = mv_raw.lower().replace("_", "-").replace(" ", "")
    if mv_norm in ("duty", "reboilerduty", "reboiler-duty", "qreb", "reboilerq"):
        mv_mode = "reboiler-duty"
    else:
        mv_mode = "boilup"

    kc = cfg.bottoms_composition_kc
    if kc is None:
        kc = _spec_float(specs, "Bottoms Composition Kc", "Bottoms Controller Kc")

    ti = cfg.bottoms_composition_ti_sec
    if ti is None:
        ti = _spec_float(specs, "Bottoms Composition Ti (sec)", "Bottoms Controller Ti (sec)")
    if ti is None:
        ti = 240.0

    if mv_mode == "reboiler-duty":
        q_bias = cfg.reboiler_duty_btu_per_h
        if q_bias is None:
            q_bias = _spec_float(specs, "Reboiler Duty (Btu/h)")
        if q_bias is None:
            try:
                q_bias = float(getattr(getattr(col, "duties", None), "q_reb_btu_per_h"))
            except Exception:
                q_bias = None
        if q_bias is None or (not np.isfinite(float(q_bias))):
            q_bias = 0.0
        q_bias = float(q_bias)

        if kc is None:
            # Preserve rough authority of legacy boilup-MV default by converting
            # with an estimated latent heat near the design point.
            v_bias = float(boundary.boilup_lbmolph) if boundary.boilup_lbmolph is not None else np.nan
            if (not np.isfinite(v_bias)) or v_bias <= 0.0:
                try:
                    v_bias = float(np.asarray(getattr(col, "V_lbmolph"), dtype=float).reshape((-1,))[-1])
                except Exception:
                    v_bias = np.nan
            latent_est = q_bias / max(v_bias, 1.0) if np.isfinite(v_bias) and v_bias > 0.0 else 15000.0
            kc = -1.0e4 * float(latent_est)

        q_min = cfg.reboiler_duty_cmd_min_btu_per_h
        q_max = cfg.reboiler_duty_cmd_max_btu_per_h
        if q_min is None:
            q_min = _spec_float(
                specs,
                "Reboiler Duty Min (Btu/h)",
                "Bottoms Composition Reboiler Duty Min (Btu/h)",
            )
        if q_max is None:
            q_max = _spec_float(
                specs,
                "Reboiler Duty Max (Btu/h)",
                "Bottoms Composition Reboiler Duty Max (Btu/h)",
            )
        if q_min is None:
            q_min = 0.0
        if q_max is None:
            q_max = max(2.5 * max(float(q_bias), 1.0), float(q_bias) + 5.0e7)
        q_min = float(q_min)
        q_max = float(q_max)
        if q_min > q_max:
            q_min, q_max = q_max, q_min

        ctrl = PIController(
            kc=float(kc),
            ti_sec=float(ti),
            bias=float(q_bias),
            out_min=float(q_min),
            out_max=float(q_max),
            integ=0.0,
        )
    else:
        if kc is None:
            kc = -1.0e4
        v_bias = float(boundary.boilup_lbmolph) if boundary.boilup_lbmolph is not None else np.nan
        if (not np.isfinite(v_bias)) or v_bias < 0.0:
            v_bias = float(np.asarray(getattr(col, "V_lbmolph"), dtype=float).reshape((-1,))[-1])

        v_min = cfg.boilup_cmd_min_lbmolph
        v_max = cfg.boilup_cmd_max_lbmolph
        if v_min is None:
            v_min = _spec_float(
                specs,
                "Boilup Flow Min (lbmol/h)",
                "Bottoms Composition Boilup Min (lbmol/h)",
            )
        if v_max is None:
            v_max = _spec_float(
                specs,
                "Boilup Flow Max (lbmol/h)",
                "Bottoms Composition Boilup Max (lbmol/h)",
            )
        if v_min is None:
            v_min = 0.0
        if v_max is None:
            v_max = max(2.5 * max(float(v_bias), 1.0), float(v_bias) + 5000.0)
        v_min = float(v_min)
        v_max = float(v_max)
        if v_min > v_max:
            v_min, v_max = v_max, v_min

        ctrl = PIController(
            kc=float(kc),
            ti_sec=float(ti),
            bias=float(v_bias),
            out_min=float(v_min),
            out_max=float(v_max),
            integ=0.0,
        )

    comp_label = None
    try:
        comp_label = str(list(getattr(col, "components_excel", []))[int(comp_idx)])
    except Exception:
        comp_label = str(comp_name)
    return True, mv_mode, ctrl, float(sp), int(comp_idx), comp_label


def _profile_rows(
    t_s: float,
    case: CaseData,
    col: ColumnSpec,
    layout: StateVectorLayout,
    y: np.ndarray,
    diag: Dict[str, np.ndarray],
    *,
    include_temperature: bool,
    volume_model: VolumeModel,
    wall_clock_iso: str,
    wall_elapsed_s: float,
    feed_tag: StreamTag,
    dist_tag: StreamTag,
    bots_tag: StreamTag,
) -> List[Dict[str, Any]]:
    u = layout.unpack(y)
    N = col.n_stages
    Nc = col.n_components

    def _comp_suffix(name: str) -> str:
        out = "".join(ch if ch.isalnum() else "_" for ch in str(name).strip())
        out = out.strip("_")
        return out or "comp"

    comp_labels = [_comp_suffix(nm) for nm in getattr(col, "components_excel", [f"c{i+1}" for i in range(Nc)])]

    x = diag.get("x_tray", u["x_tray"])
    yv = diag.get("y_tray", u["y_tray"])
    ML = u["ML_tot_tray"]
    MV = u["MV_tot_tray"]
    top_L_total = float(np.sum(u["top_L"])) if (layout.include_top and "top_L" in u) else None
    top_x = None
    bottom_L_total = float(np.sum(u["bottom_L"])) if (layout.include_bottom and "bottom_L" in u) else None
    bottom_x = None
    if layout.include_top and "top_L" in u:
        denom = max(float(np.sum(u["top_L"])), 1e-300)
        top_x = np.asarray(u["top_L"], dtype=float).reshape((Nc,)) / denom
    if layout.include_bottom and "bottom_L" in u:
        denom = max(float(np.sum(u["bottom_L"])), 1e-300)
        bottom_x = np.asarray(u["bottom_L"], dtype=float).reshape((Nc,)) / denom

    P_spec = np.asarray(getattr(col, "P_psia", np.full(N, np.nan, dtype=float)), dtype=float).reshape((N,))

    Z_raw = diag.get("Z_tray", np.full(N, np.nan, dtype=float))
    Z = np.asarray(Z_raw, dtype=float).reshape((N,))
    Z = np.where(~np.isfinite(Z) | (Z <= 0.0), 1.0, Z)
    P_hyd = None
    if "P_psia_hyd" in diag:
        try:
            P_hyd = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((N,))
        except Exception:
            P_hyd = None
    L_out_hyd = None
    if "L_out_hyd_lbmolph" in diag:
        try:
            L_out_hyd = np.asarray(diag["L_out_hyd_lbmolph"], dtype=float).reshape((N,))
        except Exception:
            L_out_hyd = None
    h_ow = None
    if "h_ow_ft" in diag:
        try:
            h_ow = np.asarray(diag["h_ow_ft"], dtype=float).reshape((N,))
        except Exception:
            h_ow = None
    V_out_calc = None
    if "V_out_lbmolph" in diag:
        try:
            V_out_calc = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))
        except Exception:
            V_out_calc = None
    vflow_ok = None
    vflow_denom = None
    vflow_calc = None
    vflow_used = None
    vflow_alpha = None
    if "vflow_energy_ok" in diag:
        try:
            vflow_ok = np.asarray(diag["vflow_energy_ok"], dtype=float).reshape((N,))
        except Exception:
            vflow_ok = None
    if "vflow_energy_denom_BTU_per_lbmol" in diag:
        try:
            vflow_denom = np.asarray(diag["vflow_energy_denom_BTU_per_lbmol"], dtype=float).reshape((N,))
        except Exception:
            vflow_denom = None
    if "vflow_energy_calc_lbmolph" in diag:
        try:
            vflow_calc = np.asarray(diag["vflow_energy_calc_lbmolph"], dtype=float).reshape((N,))
        except Exception:
            vflow_calc = None
    if "vflow_energy_used_lbmolph" in diag:
        try:
            vflow_used = np.asarray(diag["vflow_energy_used_lbmolph"], dtype=float).reshape((N,))
        except Exception:
            vflow_used = None
    if "vflow_relax_alpha" in diag:
        try:
            vflow_alpha = np.asarray(diag["vflow_relax_alpha"], dtype=float).reshape((N,))
        except Exception:
            vflow_alpha = None
    mass_resid = None
    if "mass_balance_resid_lbmolps_tray" in diag:
        try:
            mass_resid = np.asarray(diag["mass_balance_resid_lbmolps_tray"], dtype=float).reshape((N,))
        except Exception:
            mass_resid = None
    energy_resid = None
    if "energy_balance_resid_BTUps_tray" in diag:
        try:
            energy_resid = np.asarray(diag["energy_balance_resid_BTUps_tray"], dtype=float).reshape((N,))
        except Exception:
            energy_resid = None
    HL_tray = None
    HV_tray = None
    K_state_tray = None
    K_thermo_tray = None
    K_ratio_tray = None
    if "HL_BTU_lbmol_tray" in diag:
        try:
            HL_tray = np.asarray(diag["HL_BTU_lbmol_tray"], dtype=float).reshape((N,))
        except Exception:
            HL_tray = None
    if "HV_BTU_lbmol_tray" in diag:
        try:
            HV_tray = np.asarray(diag["HV_BTU_lbmol_tray"], dtype=float).reshape((N,))
        except Exception:
            HV_tray = None
    if "K_state_y_over_x_tray" in diag:
        try:
            K_state_tray = np.asarray(diag["K_state_y_over_x_tray"], dtype=float).reshape((N, Nc))
        except Exception:
            K_state_tray = None
    if "K_tray" in diag:
        try:
            K_thermo_tray = np.asarray(diag["K_tray"], dtype=float).reshape((N, Nc))
        except Exception:
            K_thermo_tray = None
    if "K_state_over_K_thermo_tray" in diag:
        try:
            K_ratio_tray = np.asarray(diag["K_state_over_K_thermo_tray"], dtype=float).reshape((N, Nc))
        except Exception:
            K_ratio_tray = None
    L_out_used = None
    reflux_ratio = None
    if "L_out_lbmolph" in diag:
        try:
            L_out_used = np.asarray(diag["L_out_lbmolph"], dtype=float).reshape((N,))
        except Exception:
            L_out_used = None
    if L_out_used is not None and dist_tag.flow_lbmolph is not None:
        try:
            D_flow = float(dist_tag.flow_lbmolph)
            if np.isfinite(D_flow) and D_flow > 0.0 and np.isfinite(L_out_used[0]):
                reflux_ratio = float(L_out_used[0]) / D_flow
        except Exception:
            reflux_ratio = None

    T = _tray_temperature_F(col, layout, y, include_temperature)
    # Condenser/distillate temperature is stage-1 tray temperature.
    T_distillate = float(T[0])
    Q_cond_calc_BTUph = np.nan
    if "Q_cond_calc_BTUph" in diag:
        try:
            Q_cond_calc_BTUph = float(np.asarray(diag["Q_cond_calc_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_calc_BTUph = np.nan
    Q_cond_used_BTUph = np.nan
    if "Q_cond_used_BTUph" in diag:
        try:
            Q_cond_used_BTUph = float(np.asarray(diag["Q_cond_used_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_used_BTUph = np.nan
    Q_reb_used_BTUph = np.nan
    if "Q_reb_used_BTUph" in diag:
        try:
            Q_reb_used_BTUph = float(np.asarray(diag["Q_reb_used_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_reb_used_BTUph = np.nan
    Q_cond_cmd_BTUph = np.nan
    if "Q_cond_cmd_BTUph" in diag:
        try:
            Q_cond_cmd_BTUph = float(np.asarray(diag["Q_cond_cmd_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_cmd_BTUph = np.nan
    P_top_drum_psia = np.nan
    if "P_top_drum_psia" in diag:
        try:
            P_top_drum_psia = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_drum_psia = np.nan
    V_condensed_in_lbmolph = np.nan
    if "V_condensed_in_lbmolph" in diag:
        try:
            V_condensed_in_lbmolph = float(np.asarray(diag["V_condensed_in_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_condensed_in_lbmolph = np.nan
    V_to_top_drum_lbmolph = np.nan
    if "V_to_top_drum_lbmolph" in diag:
        try:
            V_to_top_drum_lbmolph = float(np.asarray(diag["V_to_top_drum_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_to_top_drum_lbmolph = np.nan
    dP_stage2_to_top_drum_psia = np.nan
    if "dP_stage2_to_top_drum_psia" in diag:
        try:
            dP_stage2_to_top_drum_psia = float(
                np.asarray(diag["dP_stage2_to_top_drum_psia"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            dP_stage2_to_top_drum_psia = np.nan
    V_to_top_drum_pressure_gate_scale = np.nan
    if "V_to_top_drum_pressure_gate_scale" in diag:
        try:
            V_to_top_drum_pressure_gate_scale = float(
                np.asarray(diag["V_to_top_drum_pressure_gate_scale"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            V_to_top_drum_pressure_gate_scale = np.nan
    V_to_top_drum_blocked_lbmolph = np.nan
    if "V_to_top_drum_blocked_lbmolph" in diag:
        try:
            V_to_top_drum_blocked_lbmolph = float(
                np.asarray(diag["V_to_top_drum_blocked_lbmolph"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            V_to_top_drum_blocked_lbmolph = np.nan
    V_condensed_top_lbmolph = np.nan
    if "V_condensed_top_lbmolph" in diag:
        try:
            V_condensed_top_lbmolph = float(np.asarray(diag["V_condensed_top_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_condensed_top_lbmolph = np.nan
    V_psv_top_lbmolph = np.nan
    if "V_psv_top_lbmolph" in diag:
        try:
            V_psv_top_lbmolph = float(np.asarray(diag["V_psv_top_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_psv_top_lbmolph = np.nan
    PSV_open_flag = np.nan
    if "PSV_open_flag" in diag:
        try:
            PSV_open_flag = float(np.asarray(diag["PSV_open_flag"], dtype=float).reshape((-1,))[0])
        except Exception:
            PSV_open_flag = np.nan
    PSV_setpoint_psia = np.nan
    if "PSV_setpoint_psia" in diag:
        try:
            PSV_setpoint_psia = float(np.asarray(diag["PSV_setpoint_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            PSV_setpoint_psia = np.nan
    PSV_pv_psia = np.nan
    if "PSV_pv_psia" in diag:
        try:
            PSV_pv_psia = float(np.asarray(diag["PSV_pv_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            PSV_pv_psia = np.nan
    V_top_drum_vapor_ft3 = np.nan
    if "V_top_drum_vapor_ft3" in diag:
        try:
            V_top_drum_vapor_ft3 = float(np.asarray(diag["V_top_drum_vapor_ft3"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_top_drum_vapor_ft3 = np.nan
    V_top_drum_liquid_ft3 = np.nan
    if "V_top_drum_liquid_ft3" in diag:
        try:
            V_top_drum_liquid_ft3 = float(np.asarray(diag["V_top_drum_liquid_ft3"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_top_drum_liquid_ft3 = np.nan
    rho_top_drum_liq_lbmol_ft3 = np.nan
    if "rho_top_drum_liq_lbmol_ft3" in diag:
        try:
            rho_top_drum_liq_lbmol_ft3 = float(np.asarray(diag["rho_top_drum_liq_lbmol_ft3"], dtype=float).reshape((-1,))[0])
        except Exception:
            rho_top_drum_liq_lbmol_ft3 = np.nan
    Q_reb_cmd_BTUph = np.nan
    if "Q_reb_cmd_BTUph" in diag:
        try:
            Q_reb_cmd_BTUph = float(np.asarray(diag["Q_reb_cmd_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_reb_cmd_BTUph = np.nan
    P_top_anchor_cmd_psia = np.nan
    if "P_top_anchor_cmd_psia" in diag:
        try:
            P_top_anchor_cmd_psia = float(np.asarray(diag["P_top_anchor_cmd_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_anchor_cmd_psia = np.nan
    P_top_ctrl_pv_raw_psia = np.nan
    if "P_top_ctrl_pv_raw_psia" in diag:
        try:
            P_top_ctrl_pv_raw_psia = float(np.asarray(diag["P_top_ctrl_pv_raw_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_ctrl_pv_raw_psia = np.nan
    P_top_ctrl_pv_filt_psia = np.nan
    if "P_top_ctrl_pv_filt_psia" in diag:
        try:
            P_top_ctrl_pv_filt_psia = float(np.asarray(diag["P_top_ctrl_pv_filt_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_ctrl_pv_filt_psia = np.nan
    P_top_ctrl_gain_scale = np.nan
    if "P_top_ctrl_gain_scale" in diag:
        try:
            P_top_ctrl_gain_scale = float(np.asarray(diag["P_top_ctrl_gain_scale"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_ctrl_gain_scale = np.nan
    P_top_ctrl_energy_resid_abs_BTUps = np.nan
    if "P_top_ctrl_energy_resid_abs_BTUps" in diag:
        try:
            P_top_ctrl_energy_resid_abs_BTUps = float(
                np.asarray(diag["P_top_ctrl_energy_resid_abs_BTUps"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            P_top_ctrl_energy_resid_abs_BTUps = np.nan
    xD_comp_sp = np.nan
    if "xD_comp_sp" in diag:
        try:
            xD_comp_sp = float(np.asarray(diag["xD_comp_sp"], dtype=float).reshape((-1,))[0])
        except Exception:
            xD_comp_sp = np.nan
    xD_comp_pv = np.nan
    if "xD_comp_pv" in diag:
        try:
            xD_comp_pv = float(np.asarray(diag["xD_comp_pv"], dtype=float).reshape((-1,))[0])
        except Exception:
            xD_comp_pv = np.nan
    RR_comp_cmd = np.nan
    if "RR_comp_cmd" in diag:
        try:
            RR_comp_cmd = float(np.asarray(diag["RR_comp_cmd"], dtype=float).reshape((-1,))[0])
        except Exception:
            RR_comp_cmd = np.nan
    Reflux_cmd_lbmolph = np.nan
    if "Reflux_cmd_lbmolph" in diag:
        try:
            Reflux_cmd_lbmolph = float(np.asarray(diag["Reflux_cmd_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Reflux_cmd_lbmolph = np.nan
    xB_comp_sp = np.nan
    if "xB_comp_sp" in diag:
        try:
            xB_comp_sp = float(np.asarray(diag["xB_comp_sp"], dtype=float).reshape((-1,))[0])
        except Exception:
            xB_comp_sp = np.nan
    xB_comp_pv = np.nan
    if "xB_comp_pv" in diag:
        try:
            xB_comp_pv = float(np.asarray(diag["xB_comp_pv"], dtype=float).reshape((-1,))[0])
        except Exception:
            xB_comp_pv = np.nan
    Boilup_cmd_lbmolph = np.nan
    if "Boilup_cmd_lbmolph" in diag:
        try:
            Boilup_cmd_lbmolph = float(np.asarray(diag["Boilup_cmd_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Boilup_cmd_lbmolph = np.nan
    M_total_lbmol = np.nan
    if "M_total_lbmol" in diag:
        try:
            M_total_lbmol = float(np.asarray(diag["M_total_lbmol"], dtype=float).reshape((-1,))[0])
        except Exception:
            M_total_lbmol = np.nan
    dM_total_dt_lbmolph = np.nan
    if "dM_total_dt_lbmolph" in diag:
        try:
            dM_total_dt_lbmolph = float(np.asarray(diag["dM_total_dt_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            dM_total_dt_lbmolph = np.nan
    net_F_minus_D_minus_B_lbmolph = np.nan
    if "net_F_minus_D_minus_B_lbmolph" in diag:
        try:
            net_F_minus_D_minus_B_lbmolph = float(np.asarray(diag["net_F_minus_D_minus_B_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            net_F_minus_D_minus_B_lbmolph = np.nan
    global_mass_closure_error_lbmolph = np.nan
    if "global_mass_closure_error_lbmolph" in diag:
        try:
            global_mass_closure_error_lbmolph = float(np.asarray(diag["global_mass_closure_error_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            global_mass_closure_error_lbmolph = np.nan
    global_mass_closure_cum_lbmol = np.nan
    if "global_mass_closure_cum_lbmol" in diag:
        try:
            global_mass_closure_cum_lbmol = float(np.asarray(diag["global_mass_closure_cum_lbmol"], dtype=float).reshape((-1,))[0])
        except Exception:
            global_mass_closure_cum_lbmol = np.nan
    stage_mass_resid_sum_lbmolps = np.nan
    if "stage_mass_resid_sum_lbmolps" in diag:
        try:
            stage_mass_resid_sum_lbmolps = float(np.asarray(diag["stage_mass_resid_sum_lbmolps"], dtype=float).reshape((-1,))[0])
        except Exception:
            stage_mass_resid_sum_lbmolps = np.nan
    pv_inner_iter_count = np.nan
    if "pv_inner_iter_count" in diag:
        try:
            pv_inner_iter_count = float(np.asarray(diag["pv_inner_iter_count"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_iter_count = np.nan
    pv_inner_converged = np.nan
    if "pv_inner_converged" in diag:
        try:
            pv_inner_converged = float(np.asarray(diag["pv_inner_converged"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_converged = np.nan
    pv_inner_dp_max_psia = np.nan
    if "pv_inner_dp_max_psia" in diag:
        try:
            pv_inner_dp_max_psia = float(np.asarray(diag["pv_inner_dp_max_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_dp_max_psia = np.nan
    pv_inner_dv_max_lbmolph = np.nan
    if "pv_inner_dv_max_lbmolph" in diag:
        try:
            pv_inner_dv_max_lbmolph = float(np.asarray(diag["pv_inner_dv_max_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_dv_max_lbmolph = np.nan
    T_sump = None
    if layout.include_bottom and "bottom_T_f" in u:
        try:
            T_sump = float(u["bottom_T_f"][0])
        except Exception:
            T_sump = None

    # Prefer diag-provided P_psia_diag if present; else compute from PV
    if "P_psia_diag" in diag:
        P_diag = np.asarray(diag["P_psia_diag"], dtype=float).reshape((N,))
    else:
        P_diag = _pressure_diag_psia(col, volume_model, T, MV, Z)

    # Condenser stage report pin
    if N >= 1:
        try:
            if np.isfinite(P_spec[0]):
                P_diag[0] = float(P_spec[0])
        except Exception:
            pass

    rows: List[Dict[str, Any]] = []
    for i in range(N):
        i1 = int(i + 1)

        r: Dict[str, Any] = {
            "wall_clock_iso": wall_clock_iso,
            "wall_elapsed_s": float(wall_elapsed_s),
            "time_s": float(t_s),
            "stage": i1,
            "node_type": "stage",
            "T_F": float(T[i]),
            "P_psia_hyd": float(P_hyd[i]) if P_hyd is not None and np.isfinite(P_hyd[i]) else np.nan,
            "L_out_used_lbmolph": (
                float(L_out_used[i]) if L_out_used is not None and np.isfinite(L_out_used[i]) else np.nan
            ),
            "L_out_hyd_lbmolph": float(L_out_hyd[i]) if L_out_hyd is not None and np.isfinite(L_out_hyd[i]) else np.nan,
            "V_out_lbmolph": float(V_out_calc[i]) if V_out_calc is not None and np.isfinite(V_out_calc[i]) else np.nan,
            "vflow_energy_ok": float(vflow_ok[i]) if vflow_ok is not None and np.isfinite(vflow_ok[i]) else np.nan,
            "vflow_energy_denom_BTU_per_lbmol": float(vflow_denom[i]) if vflow_denom is not None and np.isfinite(vflow_denom[i]) else np.nan,
            "vflow_energy_calc_lbmolph": float(vflow_calc[i]) if vflow_calc is not None and np.isfinite(vflow_calc[i]) else np.nan,
            "vflow_energy_used_lbmolph": float(vflow_used[i]) if vflow_used is not None and np.isfinite(vflow_used[i]) else np.nan,
            "vflow_relax_alpha": float(vflow_alpha[i]) if vflow_alpha is not None and np.isfinite(vflow_alpha[i]) else np.nan,
            "h_ow_ft": float(h_ow[i]) if h_ow is not None and np.isfinite(h_ow[i]) else np.nan,
            "ML_lbmol": float(ML[i]),
            "MV_lbmol": float(MV[i]),
            "stage_mass_balance_resid_lbmolps": float(mass_resid[i]) if mass_resid is not None and np.isfinite(mass_resid[i]) else np.nan,
            "stage_energy_balance_resid_BTUps": float(energy_resid[i]) if energy_resid is not None and np.isfinite(energy_resid[i]) else np.nan,
            "HL_BTU_lbmol_tray": float(HL_tray[i]) if HL_tray is not None and np.isfinite(HL_tray[i]) else np.nan,
            "HV_BTU_lbmol_tray": float(HV_tray[i]) if HV_tray is not None and np.isfinite(HV_tray[i]) else np.nan,
            "reflux_ratio": _stage_value(i1, 1, reflux_ratio),
            # New: stream flow columns placed on their stages
            "F_lbmolph": _stage_value(i1, feed_tag.stage_1based, feed_tag.flow_lbmolph),
            "D_lbmolph": _stage_value(i1, dist_tag.stage_1based, dist_tag.flow_lbmolph),
            "B_lbmolph": _stage_value(i1, bots_tag.stage_1based, bots_tag.flow_lbmolph),
            "Distillate_L_lbmol": _stage_value(i1, 1 if layout.include_top else None, top_L_total),
            "Bottoms_L_lbmol": _stage_value(i1, N if layout.include_bottom else None, bottom_L_total),
            "T_Distillate_F": _stage_value(i1, 1, T_distillate),
            "Q_cond_calc_BTUph": _stage_value(i1, 1, Q_cond_calc_BTUph),
            "Q_cond_used_BTUph": _stage_value(i1, 1, Q_cond_used_BTUph),
            "Q_reb_used_BTUph": _stage_value(i1, N, Q_reb_used_BTUph),
            "Q_cond_cmd_BTUph": _stage_value(i1, 1, Q_cond_cmd_BTUph),
            "P_top_drum_psia": _stage_value(i1, 1, P_top_drum_psia),
            "V_condensed_in_lbmolph": _stage_value(i1, 1, V_condensed_in_lbmolph),
            "V_to_top_drum_lbmolph": _stage_value(i1, 1, V_to_top_drum_lbmolph),
            "dP_stage2_to_top_drum_psia": _stage_value(i1, 1, dP_stage2_to_top_drum_psia),
            "V_to_top_drum_pressure_gate_scale": _stage_value(i1, 1, V_to_top_drum_pressure_gate_scale),
            "V_to_top_drum_blocked_lbmolph": _stage_value(i1, 1, V_to_top_drum_blocked_lbmolph),
            "V_condensed_top_lbmolph": _stage_value(i1, 1, V_condensed_top_lbmolph),
            "V_psv_top_lbmolph": _stage_value(i1, 1, V_psv_top_lbmolph),
            "PSV_open_flag": _stage_value(i1, 1, PSV_open_flag),
            "PSV_setpoint_psia": _stage_value(i1, 1, PSV_setpoint_psia),
            "PSV_pv_psia": _stage_value(i1, 1, PSV_pv_psia),
            "V_top_drum_vapor_ft3": _stage_value(i1, 1, V_top_drum_vapor_ft3),
            "V_top_drum_liquid_ft3": _stage_value(i1, 1, V_top_drum_liquid_ft3),
            "rho_top_drum_liq_lbmol_ft3": _stage_value(i1, 1, rho_top_drum_liq_lbmol_ft3),
            "Q_reb_cmd_BTUph": _stage_value(i1, N, Q_reb_cmd_BTUph),
            "P_top_anchor_cmd_psia": _stage_value(i1, 1, P_top_anchor_cmd_psia),
            "xD_comp_sp": _stage_value(i1, 1, xD_comp_sp),
            "xD_comp_pv": _stage_value(i1, 1, xD_comp_pv),
            "RR_comp_cmd": _stage_value(i1, 1, RR_comp_cmd),
            "Reflux_cmd_lbmolph": _stage_value(i1, 1, Reflux_cmd_lbmolph),
            "xB_comp_sp": _stage_value(i1, N, xB_comp_sp),
            "xB_comp_pv": _stage_value(i1, N, xB_comp_pv),
            "Boilup_cmd_lbmolph": _stage_value(i1, N, Boilup_cmd_lbmolph),
            "M_total_lbmol": _stage_value(i1, 1, M_total_lbmol),
            "dM_total_dt_lbmolph": _stage_value(i1, 1, dM_total_dt_lbmolph),
            "net_F_minus_D_minus_B_lbmolph": _stage_value(i1, 1, net_F_minus_D_minus_B_lbmolph),
            "global_mass_closure_error_lbmolph": _stage_value(i1, 1, global_mass_closure_error_lbmolph),
            "global_mass_closure_cum_lbmol": _stage_value(i1, 1, global_mass_closure_cum_lbmol),
            "stage_mass_resid_sum_lbmolps": _stage_value(i1, 1, stage_mass_resid_sum_lbmolps),
            "T_sump_F": _stage_value(i1, N if layout.include_bottom else None, T_sump),
        }

        for k in range(Nc):
            label = comp_labels[k]
            r[f"x_{label}"] = float(x[i, k])
            r[f"y_{label}"] = float(yv[i, k])
            r[f"K_state_{label}"] = (
                float(K_state_tray[i, k])
                if K_state_tray is not None and np.isfinite(K_state_tray[i, k])
                else np.nan
            )
            r[f"K_thermo_{label}"] = (
                float(K_thermo_tray[i, k])
                if K_thermo_tray is not None and np.isfinite(K_thermo_tray[i, k])
                else np.nan
            )
            r[f"K_state_over_K_thermo_{label}"] = (
                float(K_ratio_tray[i, k])
                if K_ratio_tray is not None and np.isfinite(K_ratio_tray[i, k])
                else np.nan
            )
            if top_x is not None:
                r[f"Distillate_x_{label}"] = _stage_value(i1, 1, float(top_x[k]))
            if bottom_x is not None:
                r[f"Bottoms_x_{label}"] = _stage_value(i1, N, float(bottom_x[k]))

        rows.append(r)

    if rows:
        drum_fields = {
            "D_lbmolph",
            "Distillate_L_lbmol",
            "T_Distillate_F",
            "Q_cond_calc_BTUph",
            "Q_cond_used_BTUph",
            "Q_cond_cmd_BTUph",
            "P_top_drum_psia",
            "V_condensed_in_lbmolph",
            "V_to_top_drum_lbmolph",
            "dP_stage2_to_top_drum_psia",
            "V_to_top_drum_pressure_gate_scale",
            "V_to_top_drum_blocked_lbmolph",
            "V_condensed_top_lbmolph",
            "V_psv_top_lbmolph",
            "PSV_open_flag",
            "PSV_setpoint_psia",
            "PSV_pv_psia",
            "V_top_drum_vapor_ft3",
            "V_top_drum_liquid_ft3",
            "rho_top_drum_liq_lbmol_ft3",
            "P_top_anchor_cmd_psia",
            "xD_comp_sp",
            "xD_comp_pv",
            "RR_comp_cmd",
            "Reflux_cmd_lbmolph",
        }
        sump_fields = {
            "B_lbmolph",
            "Bottoms_L_lbmol",
            "Q_reb_used_BTUph",
            "Q_reb_cmd_BTUph",
            "xB_comp_sp",
            "xB_comp_pv",
            "Boilup_cmd_lbmolph",
            "T_sump_F",
        }
        for label in comp_labels:
            drum_fields.add(f"Distillate_x_{label}")
            sump_fields.add(f"Bottoms_x_{label}")

        moved_fields = set(drum_fields) | set(sump_fields)
        top_stage_row = dict(rows[0])
        bottom_stage_row = dict(rows[-1])

        for r in rows:
            for key in moved_fields:
                if key in r:
                    r[key] = np.nan
        drum_row = {k: np.nan for k in top_stage_row.keys()}
        sump_row = {k: np.nan for k in top_stage_row.keys()}

        drum_row["wall_clock_iso"] = wall_clock_iso
        drum_row["wall_elapsed_s"] = float(wall_elapsed_s)
        drum_row["time_s"] = float(t_s)
        drum_row["stage"] = 0
        drum_row["node_type"] = "distillate_drum"
        for key in drum_fields:
            if key in top_stage_row:
                drum_row[key] = top_stage_row.get(key, np.nan)

        sump_row["wall_clock_iso"] = wall_clock_iso
        sump_row["wall_elapsed_s"] = float(wall_elapsed_s)
        sump_row["time_s"] = float(t_s)
        sump_row["stage"] = int(N + 1)
        sump_row["node_type"] = "bottoms_sump"
        for key in sump_fields:
            if key in bottom_stage_row:
                sump_row[key] = bottom_stage_row.get(key, np.nan)

        # Distillate and bottoms draws are inventories on drum/sump unit rows.
        drum_row["D_lbmolph"] = float(dist_tag.flow_lbmolph) if dist_tag.flow_lbmolph is not None else np.nan
        sump_row["B_lbmolph"] = float(bots_tag.flow_lbmolph) if bots_tag.flow_lbmolph is not None else np.nan

        rows = [drum_row, *rows, sump_row]

    return rows


def _summary_row(
    t_s: float,
    case: CaseData,
    col: ColumnSpec,
    layout: StateVectorLayout,
    y: np.ndarray,
    diag: Dict[str, np.ndarray],
    *,
    include_temperature: bool,
    volume_model: VolumeModel,
    wall_clock_iso: str,
    wall_elapsed_s: float,
    feed_tag: StreamTag,
    dist_tag: StreamTag,
    bots_tag: StreamTag,
    integrator_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    u = layout.unpack(y)
    N = col.n_stages
    Nc = col.n_components

    def _comp_suffix(name: str) -> str:
        out = "".join(ch if ch.isalnum() else "_" for ch in str(name).strip())
        out = out.strip("_")
        return out or "comp"

    comp_labels = [_comp_suffix(nm) for nm in getattr(col, "components_excel", [f"c{i+1}" for i in range(Nc)])]

    x = diag.get("x_tray", u["x_tray"])
    yv = diag.get("y_tray", u["y_tray"])
    MV = u["MV_tot_tray"]

    P_spec = np.asarray(getattr(col, "P_psia", np.full(N, np.nan, dtype=float)), dtype=float).reshape((N,))

    Z_raw = diag.get("Z_tray", np.full(N, np.nan, dtype=float))
    Z = np.asarray(Z_raw, dtype=float).reshape((N,))
    Z = np.where(~np.isfinite(Z) | (Z <= 0.0), 1.0, Z)

    T = _tray_temperature_F(col, layout, y, include_temperature)
    # Condenser/distillate temperature is stage-1 tray temperature.
    T_distillate = float(T[0])
    Q_cond_calc_BTUph = np.nan
    if "Q_cond_calc_BTUph" in diag:
        try:
            Q_cond_calc_BTUph = float(np.asarray(diag["Q_cond_calc_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_calc_BTUph = np.nan
    Q_cond_used_BTUph = np.nan
    if "Q_cond_used_BTUph" in diag:
        try:
            Q_cond_used_BTUph = float(np.asarray(diag["Q_cond_used_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_used_BTUph = np.nan
    Q_reb_used_BTUph = np.nan
    if "Q_reb_used_BTUph" in diag:
        try:
            Q_reb_used_BTUph = float(np.asarray(diag["Q_reb_used_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_reb_used_BTUph = np.nan
    Q_cond_cmd_BTUph = np.nan
    if "Q_cond_cmd_BTUph" in diag:
        try:
            Q_cond_cmd_BTUph = float(np.asarray(diag["Q_cond_cmd_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_cmd_BTUph = np.nan
    P_top_drum_psia = np.nan
    if "P_top_drum_psia" in diag:
        try:
            P_top_drum_psia = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_drum_psia = np.nan
    V_condensed_in_lbmolph = np.nan
    if "V_condensed_in_lbmolph" in diag:
        try:
            V_condensed_in_lbmolph = float(np.asarray(diag["V_condensed_in_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_condensed_in_lbmolph = np.nan
    V_to_top_drum_lbmolph = np.nan
    if "V_to_top_drum_lbmolph" in diag:
        try:
            V_to_top_drum_lbmolph = float(np.asarray(diag["V_to_top_drum_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_to_top_drum_lbmolph = np.nan
    dP_stage2_to_top_drum_psia = np.nan
    if "dP_stage2_to_top_drum_psia" in diag:
        try:
            dP_stage2_to_top_drum_psia = float(
                np.asarray(diag["dP_stage2_to_top_drum_psia"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            dP_stage2_to_top_drum_psia = np.nan
    V_to_top_drum_pressure_gate_scale = np.nan
    if "V_to_top_drum_pressure_gate_scale" in diag:
        try:
            V_to_top_drum_pressure_gate_scale = float(
                np.asarray(diag["V_to_top_drum_pressure_gate_scale"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            V_to_top_drum_pressure_gate_scale = np.nan
    V_to_top_drum_blocked_lbmolph = np.nan
    if "V_to_top_drum_blocked_lbmolph" in diag:
        try:
            V_to_top_drum_blocked_lbmolph = float(
                np.asarray(diag["V_to_top_drum_blocked_lbmolph"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            V_to_top_drum_blocked_lbmolph = np.nan
    V_condensed_top_lbmolph = np.nan
    if "V_condensed_top_lbmolph" in diag:
        try:
            V_condensed_top_lbmolph = float(np.asarray(diag["V_condensed_top_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_condensed_top_lbmolph = np.nan
    V_psv_top_lbmolph = np.nan
    if "V_psv_top_lbmolph" in diag:
        try:
            V_psv_top_lbmolph = float(np.asarray(diag["V_psv_top_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_psv_top_lbmolph = np.nan
    PSV_open_flag = np.nan
    if "PSV_open_flag" in diag:
        try:
            PSV_open_flag = float(np.asarray(diag["PSV_open_flag"], dtype=float).reshape((-1,))[0])
        except Exception:
            PSV_open_flag = np.nan
    PSV_setpoint_psia = np.nan
    if "PSV_setpoint_psia" in diag:
        try:
            PSV_setpoint_psia = float(np.asarray(diag["PSV_setpoint_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            PSV_setpoint_psia = np.nan
    PSV_pv_psia = np.nan
    if "PSV_pv_psia" in diag:
        try:
            PSV_pv_psia = float(np.asarray(diag["PSV_pv_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            PSV_pv_psia = np.nan
    V_top_drum_vapor_ft3 = np.nan
    if "V_top_drum_vapor_ft3" in diag:
        try:
            V_top_drum_vapor_ft3 = float(np.asarray(diag["V_top_drum_vapor_ft3"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_top_drum_vapor_ft3 = np.nan
    V_top_drum_liquid_ft3 = np.nan
    if "V_top_drum_liquid_ft3" in diag:
        try:
            V_top_drum_liquid_ft3 = float(np.asarray(diag["V_top_drum_liquid_ft3"], dtype=float).reshape((-1,))[0])
        except Exception:
            V_top_drum_liquid_ft3 = np.nan
    rho_top_drum_liq_lbmol_ft3 = np.nan
    if "rho_top_drum_liq_lbmol_ft3" in diag:
        try:
            rho_top_drum_liq_lbmol_ft3 = float(np.asarray(diag["rho_top_drum_liq_lbmol_ft3"], dtype=float).reshape((-1,))[0])
        except Exception:
            rho_top_drum_liq_lbmol_ft3 = np.nan
    Q_reb_cmd_BTUph = np.nan
    if "Q_reb_cmd_BTUph" in diag:
        try:
            Q_reb_cmd_BTUph = float(np.asarray(diag["Q_reb_cmd_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_reb_cmd_BTUph = np.nan
    P_top_anchor_cmd_psia = np.nan
    if "P_top_anchor_cmd_psia" in diag:
        try:
            P_top_anchor_cmd_psia = float(np.asarray(diag["P_top_anchor_cmd_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_anchor_cmd_psia = np.nan
    P_top_ctrl_pv_raw_psia = np.nan
    if "P_top_ctrl_pv_raw_psia" in diag:
        try:
            P_top_ctrl_pv_raw_psia = float(np.asarray(diag["P_top_ctrl_pv_raw_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_ctrl_pv_raw_psia = np.nan
    P_top_ctrl_pv_filt_psia = np.nan
    if "P_top_ctrl_pv_filt_psia" in diag:
        try:
            P_top_ctrl_pv_filt_psia = float(np.asarray(diag["P_top_ctrl_pv_filt_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_ctrl_pv_filt_psia = np.nan
    P_top_ctrl_gain_scale = np.nan
    if "P_top_ctrl_gain_scale" in diag:
        try:
            P_top_ctrl_gain_scale = float(np.asarray(diag["P_top_ctrl_gain_scale"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_ctrl_gain_scale = np.nan
    P_top_ctrl_energy_resid_abs_BTUps = np.nan
    if "P_top_ctrl_energy_resid_abs_BTUps" in diag:
        try:
            P_top_ctrl_energy_resid_abs_BTUps = float(
                np.asarray(diag["P_top_ctrl_energy_resid_abs_BTUps"], dtype=float).reshape((-1,))[0]
            )
        except Exception:
            P_top_ctrl_energy_resid_abs_BTUps = np.nan
    xD_comp_sp = np.nan
    if "xD_comp_sp" in diag:
        try:
            xD_comp_sp = float(np.asarray(diag["xD_comp_sp"], dtype=float).reshape((-1,))[0])
        except Exception:
            xD_comp_sp = np.nan
    xD_comp_pv = np.nan
    if "xD_comp_pv" in diag:
        try:
            xD_comp_pv = float(np.asarray(diag["xD_comp_pv"], dtype=float).reshape((-1,))[0])
        except Exception:
            xD_comp_pv = np.nan
    RR_comp_cmd = np.nan
    if "RR_comp_cmd" in diag:
        try:
            RR_comp_cmd = float(np.asarray(diag["RR_comp_cmd"], dtype=float).reshape((-1,))[0])
        except Exception:
            RR_comp_cmd = np.nan
    Reflux_cmd_lbmolph = np.nan
    if "Reflux_cmd_lbmolph" in diag:
        try:
            Reflux_cmd_lbmolph = float(np.asarray(diag["Reflux_cmd_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Reflux_cmd_lbmolph = np.nan
    xB_comp_sp = np.nan
    if "xB_comp_sp" in diag:
        try:
            xB_comp_sp = float(np.asarray(diag["xB_comp_sp"], dtype=float).reshape((-1,))[0])
        except Exception:
            xB_comp_sp = np.nan
    xB_comp_pv = np.nan
    if "xB_comp_pv" in diag:
        try:
            xB_comp_pv = float(np.asarray(diag["xB_comp_pv"], dtype=float).reshape((-1,))[0])
        except Exception:
            xB_comp_pv = np.nan
    Boilup_cmd_lbmolph = np.nan
    if "Boilup_cmd_lbmolph" in diag:
        try:
            Boilup_cmd_lbmolph = float(np.asarray(diag["Boilup_cmd_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Boilup_cmd_lbmolph = np.nan
    M_total_lbmol = np.nan
    if "M_total_lbmol" in diag:
        try:
            M_total_lbmol = float(np.asarray(diag["M_total_lbmol"], dtype=float).reshape((-1,))[0])
        except Exception:
            M_total_lbmol = np.nan
    dM_total_dt_lbmolph = np.nan
    if "dM_total_dt_lbmolph" in diag:
        try:
            dM_total_dt_lbmolph = float(np.asarray(diag["dM_total_dt_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            dM_total_dt_lbmolph = np.nan
    net_F_minus_D_minus_B_lbmolph = np.nan
    if "net_F_minus_D_minus_B_lbmolph" in diag:
        try:
            net_F_minus_D_minus_B_lbmolph = float(np.asarray(diag["net_F_minus_D_minus_B_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            net_F_minus_D_minus_B_lbmolph = np.nan
    global_mass_closure_error_lbmolph = np.nan
    if "global_mass_closure_error_lbmolph" in diag:
        try:
            global_mass_closure_error_lbmolph = float(np.asarray(diag["global_mass_closure_error_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            global_mass_closure_error_lbmolph = np.nan
    global_mass_closure_cum_lbmol = np.nan
    if "global_mass_closure_cum_lbmol" in diag:
        try:
            global_mass_closure_cum_lbmol = float(np.asarray(diag["global_mass_closure_cum_lbmol"], dtype=float).reshape((-1,))[0])
        except Exception:
            global_mass_closure_cum_lbmol = np.nan
    stage_mass_resid_sum_lbmolps = np.nan
    if "stage_mass_resid_sum_lbmolps" in diag:
        try:
            stage_mass_resid_sum_lbmolps = float(np.asarray(diag["stage_mass_resid_sum_lbmolps"], dtype=float).reshape((-1,))[0])
        except Exception:
            stage_mass_resid_sum_lbmolps = np.nan
    pv_inner_iter_count = np.nan
    if "pv_inner_iter_count" in diag:
        try:
            pv_inner_iter_count = float(np.asarray(diag["pv_inner_iter_count"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_iter_count = np.nan
    pv_inner_converged = np.nan
    if "pv_inner_converged" in diag:
        try:
            pv_inner_converged = float(np.asarray(diag["pv_inner_converged"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_converged = np.nan
    pv_inner_dp_max_psia = np.nan
    if "pv_inner_dp_max_psia" in diag:
        try:
            pv_inner_dp_max_psia = float(np.asarray(diag["pv_inner_dp_max_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_dp_max_psia = np.nan
    pv_inner_dv_max_lbmolph = np.nan
    if "pv_inner_dv_max_lbmolph" in diag:
        try:
            pv_inner_dv_max_lbmolph = float(np.asarray(diag["pv_inner_dv_max_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            pv_inner_dv_max_lbmolph = np.nan
    K_state_over_K_thermo_max_abs = np.nan
    K_state_minus_K_thermo_max_abs = np.nan
    if "K_state_over_K_thermo_tray" in diag:
        try:
            k_ratio = np.asarray(diag["K_state_over_K_thermo_tray"], dtype=float).reshape((N, Nc))
            k_ratio_f = k_ratio[np.isfinite(k_ratio)]
            if k_ratio_f.size > 0:
                K_state_over_K_thermo_max_abs = float(np.max(np.abs(k_ratio_f)))
        except Exception:
            K_state_over_K_thermo_max_abs = np.nan
    if "K_state_minus_K_thermo_tray" in diag:
        try:
            k_delta = np.asarray(diag["K_state_minus_K_thermo_tray"], dtype=float).reshape((N, Nc))
            k_delta_f = k_delta[np.isfinite(k_delta)]
            if k_delta_f.size > 0:
                K_state_minus_K_thermo_max_abs = float(np.max(np.abs(k_delta_f)))
        except Exception:
            K_state_minus_K_thermo_max_abs = np.nan
    steady_state_enabled = _mapping_scalar(diag, "steady_state_enabled")
    steady_state_flag = _mapping_scalar(diag, "steady_state_flag")
    steady_state_score = _mapping_scalar(diag, "steady_state_score")
    steady_state_active_criteria = _mapping_scalar(diag, "steady_state_active_criteria")
    ss_max_rel_state_rate_per_s = _mapping_scalar(diag, "ss_max_rel_state_rate_per_s")
    ss_max_kpi_slope_per_s = _mapping_scalar(diag, "ss_max_kpi_slope_per_s")
    ss_max_mv_rate_per_s = _mapping_scalar(diag, "ss_max_mv_rate_per_s")
    ss_max_temp_rate_F_per_s = _mapping_scalar(diag, "ss_max_temp_rate_F_per_s")
    ss_max_sp_error = _mapping_scalar(diag, "ss_max_sp_error")
    ss_window_samples = _mapping_scalar(diag, "ss_window_samples")
    ss_window_sec = _mapping_scalar(diag, "ss_window_sec")
    ss_min_time_sec = _mapping_scalar(diag, "ss_min_time_sec")
    ss_tol_rel_state_rate_per_s = _mapping_scalar(diag, "ss_tol_rel_state_rate_per_s")
    ss_tol_kpi_slope_per_s = _mapping_scalar(diag, "ss_tol_kpi_slope_per_s")
    ss_tol_mv_rate_per_s = _mapping_scalar(diag, "ss_tol_mv_rate_per_s")
    ss_tol_temp_rate_F_per_s = _mapping_scalar(diag, "ss_tol_temp_rate_F_per_s")
    ss_tol_sp_error = _mapping_scalar(diag, "ss_tol_sp_error")
    ss_require_sp = _mapping_scalar(diag, "ss_require_sp")

    integ = dict(integrator_info) if isinstance(integrator_info, dict) else {}
    integrator_requested_mode = str(integ.get("requested_mode", "")).strip()
    integrator_used_mode = str(integ.get("used_mode", "")).strip()
    integrator_fallback_reason = str(integ.get("fallback_reason", "")).strip()
    if not integrator_requested_mode:
        integrator_requested_mode = ""
    if not integrator_used_mode:
        integrator_used_mode = ""
    if not integrator_fallback_reason:
        integrator_fallback_reason = ""
    integrator_fallback_used = float("nan")
    if "fallback_used" in integ:
        integrator_fallback_used = 1.0 if bool(integ.get("fallback_used", False)) else 0.0
    integrator_nfev = _mapping_scalar(integ, "nfev")
    ida_iter_max = _mapping_scalar(integ, "ida_iter_max")
    ida_iter_mean = _mapping_scalar(integ, "ida_iter_mean")
    ida_converged = _mapping_scalar(integ, "ida_converged")
    ida_last_err = _mapping_scalar(integ, "ida_last_err")
    ida_alg_p_inf_psia = _mapping_scalar(integ, "ida_alg_p_inf_psia")
    ida_alg_v_inf_lbmolph = _mapping_scalar(integ, "ida_alg_v_inf_lbmolph")
    ida_alg_weighted = _mapping_scalar(integ, "ida_alg_weighted")
    ida_alg_converged = _mapping_scalar(integ, "ida_alg_converged")
    ida_resid_energy_btups = _mapping_scalar(integ, "ida_resid_energy_btups")

    if "P_psia_diag" in diag:
        P_diag = np.asarray(diag["P_psia_diag"], dtype=float).reshape((N,))
    else:
        P_diag = _pressure_diag_psia(col, volume_model, T, MV, Z)

    if N >= 1 and np.isfinite(P_spec[0]):
        P_diag[0] = float(P_spec[0])

    p_ctrl_idx = 0
    P_top_meas = float(P_diag[p_ctrl_idx])
    has_ctrl_pv = False
    if "P_top_ctrl_pv_psia" in diag:
        try:
            p_ctrl = float(np.asarray(diag["P_top_ctrl_pv_psia"], dtype=float).reshape((-1,))[0])
            if np.isfinite(p_ctrl) and p_ctrl > 0.0:
                P_top_meas = float(p_ctrl)
                has_ctrl_pv = True
        except Exception:
            pass
    has_top_drum_pv = False
    if (not has_ctrl_pv) and "P_top_drum_psia" in diag:
        try:
            p_top_drum = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
            if np.isfinite(p_top_drum) and p_top_drum > 0.0:
                P_top_meas = float(p_top_drum)
                has_top_drum_pv = True
        except Exception:
            pass
    if (not has_ctrl_pv) and (not has_top_drum_pv) and "P_psia_hyd" in diag:
        try:
            p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((N,))
            if np.isfinite(float(p_h[p_ctrl_idx])) and float(p_h[p_ctrl_idx]) > 0.0:
                P_top_meas = float(p_h[p_ctrl_idx])
        except Exception:
            pass

    top_L_total = float(np.sum(u["top_L"])) if (layout.include_top and "top_L" in u) else None
    top_x = None
    bottom_L_total = float(np.sum(u["bottom_L"])) if (layout.include_bottom and "bottom_L" in u) else None
    bottom_x = None
    if layout.include_top and "top_L" in u:
        denom = max(float(np.sum(u["top_L"])), 1e-300)
        top_x = np.asarray(u["top_L"], dtype=float).reshape((Nc,)) / denom
    if layout.include_bottom and "bottom_L" in u:
        denom = max(float(np.sum(u["bottom_L"])), 1e-300)
        bottom_x = np.asarray(u["bottom_L"], dtype=float).reshape((Nc,)) / denom

    T_sump = None
    if layout.include_bottom and "bottom_T_f" in u:
        try:
            T_sump = float(u["bottom_T_f"][0])
        except Exception:
            T_sump = None

    out: Dict[str, Any] = {
        "wall_clock_iso": wall_clock_iso,
        "wall_elapsed_s": float(wall_elapsed_s),
        "time_s": float(t_s),
        "P_top_psia": float(P_top_meas) if np.isfinite(P_top_meas) else (float(P_spec[0]) if np.isfinite(P_spec[0]) else float(P_diag[0])),
        "P_top_psia_spec": float(P_spec[0]) if np.isfinite(P_spec[0]) else np.nan,
        "P_top_ctrl_pv_psia": float(P_top_meas),
        "P_bot_psia": float(P_spec[-1]) if np.isfinite(P_spec[-1]) else float(P_diag[-1]),
        "P_bot_psia_spec": float(P_spec[-1]) if np.isfinite(P_spec[-1]) else np.nan,
        "T_Distillate_F": float(T_distillate) if T_distillate is not None else np.nan,
        "Q_cond_calc_BTUph": float(Q_cond_calc_BTUph) if np.isfinite(Q_cond_calc_BTUph) else np.nan,
        "Q_cond_used_BTUph": float(Q_cond_used_BTUph) if np.isfinite(Q_cond_used_BTUph) else np.nan,
        "Q_reb_used_BTUph": float(Q_reb_used_BTUph) if np.isfinite(Q_reb_used_BTUph) else np.nan,
        "Q_cond_cmd_BTUph": float(Q_cond_cmd_BTUph) if np.isfinite(Q_cond_cmd_BTUph) else np.nan,
        "P_top_drum_psia": float(P_top_drum_psia) if np.isfinite(P_top_drum_psia) else np.nan,
        "V_condensed_in_lbmolph": float(V_condensed_in_lbmolph) if np.isfinite(V_condensed_in_lbmolph) else np.nan,
        "V_to_top_drum_lbmolph": float(V_to_top_drum_lbmolph) if np.isfinite(V_to_top_drum_lbmolph) else np.nan,
        "dP_stage2_to_top_drum_psia": (
            float(dP_stage2_to_top_drum_psia) if np.isfinite(dP_stage2_to_top_drum_psia) else np.nan
        ),
        "V_to_top_drum_pressure_gate_scale": (
            float(V_to_top_drum_pressure_gate_scale) if np.isfinite(V_to_top_drum_pressure_gate_scale) else np.nan
        ),
        "V_to_top_drum_blocked_lbmolph": (
            float(V_to_top_drum_blocked_lbmolph) if np.isfinite(V_to_top_drum_blocked_lbmolph) else np.nan
        ),
        "V_condensed_top_lbmolph": float(V_condensed_top_lbmolph) if np.isfinite(V_condensed_top_lbmolph) else np.nan,
        "V_psv_top_lbmolph": float(V_psv_top_lbmolph) if np.isfinite(V_psv_top_lbmolph) else np.nan,
        "PSV_open_flag": float(PSV_open_flag) if np.isfinite(PSV_open_flag) else np.nan,
        "PSV_setpoint_psia": float(PSV_setpoint_psia) if np.isfinite(PSV_setpoint_psia) else np.nan,
        "PSV_pv_psia": float(PSV_pv_psia) if np.isfinite(PSV_pv_psia) else np.nan,
        "V_top_drum_vapor_ft3": float(V_top_drum_vapor_ft3) if np.isfinite(V_top_drum_vapor_ft3) else np.nan,
        "V_top_drum_liquid_ft3": float(V_top_drum_liquid_ft3) if np.isfinite(V_top_drum_liquid_ft3) else np.nan,
        "rho_top_drum_liq_lbmol_ft3": float(rho_top_drum_liq_lbmol_ft3) if np.isfinite(rho_top_drum_liq_lbmol_ft3) else np.nan,
        "Q_reb_cmd_BTUph": float(Q_reb_cmd_BTUph) if np.isfinite(Q_reb_cmd_BTUph) else np.nan,
        "P_top_anchor_cmd_psia": float(P_top_anchor_cmd_psia) if np.isfinite(P_top_anchor_cmd_psia) else np.nan,
        "P_top_ctrl_pv_raw_psia": float(P_top_ctrl_pv_raw_psia) if np.isfinite(P_top_ctrl_pv_raw_psia) else np.nan,
        "P_top_ctrl_pv_filt_psia": float(P_top_ctrl_pv_filt_psia) if np.isfinite(P_top_ctrl_pv_filt_psia) else np.nan,
        "P_top_ctrl_gain_scale": float(P_top_ctrl_gain_scale) if np.isfinite(P_top_ctrl_gain_scale) else np.nan,
        "P_top_ctrl_energy_resid_abs_BTUps": (
            float(P_top_ctrl_energy_resid_abs_BTUps) if np.isfinite(P_top_ctrl_energy_resid_abs_BTUps) else np.nan
        ),
        "xD_comp_sp": float(xD_comp_sp) if np.isfinite(xD_comp_sp) else np.nan,
        "xD_comp_pv": float(xD_comp_pv) if np.isfinite(xD_comp_pv) else np.nan,
        "RR_comp_cmd": float(RR_comp_cmd) if np.isfinite(RR_comp_cmd) else np.nan,
        "Reflux_cmd_lbmolph": float(Reflux_cmd_lbmolph) if np.isfinite(Reflux_cmd_lbmolph) else np.nan,
        "xB_comp_sp": float(xB_comp_sp) if np.isfinite(xB_comp_sp) else np.nan,
        "xB_comp_pv": float(xB_comp_pv) if np.isfinite(xB_comp_pv) else np.nan,
        "Boilup_cmd_lbmolph": float(Boilup_cmd_lbmolph) if np.isfinite(Boilup_cmd_lbmolph) else np.nan,
        "M_total_lbmol": float(M_total_lbmol) if np.isfinite(M_total_lbmol) else np.nan,
        "dM_total_dt_lbmolph": float(dM_total_dt_lbmolph) if np.isfinite(dM_total_dt_lbmolph) else np.nan,
        "net_F_minus_D_minus_B_lbmolph": float(net_F_minus_D_minus_B_lbmolph) if np.isfinite(net_F_minus_D_minus_B_lbmolph) else np.nan,
        "global_mass_closure_error_lbmolph": float(global_mass_closure_error_lbmolph) if np.isfinite(global_mass_closure_error_lbmolph) else np.nan,
        "global_mass_closure_cum_lbmol": float(global_mass_closure_cum_lbmol) if np.isfinite(global_mass_closure_cum_lbmol) else np.nan,
        "stage_mass_resid_sum_lbmolps": float(stage_mass_resid_sum_lbmolps) if np.isfinite(stage_mass_resid_sum_lbmolps) else np.nan,
        "pv_inner_iter_count": float(pv_inner_iter_count) if np.isfinite(pv_inner_iter_count) else np.nan,
        "pv_inner_converged": float(pv_inner_converged) if np.isfinite(pv_inner_converged) else np.nan,
        "pv_inner_dp_max_psia": float(pv_inner_dp_max_psia) if np.isfinite(pv_inner_dp_max_psia) else np.nan,
        "pv_inner_dv_max_lbmolph": float(pv_inner_dv_max_lbmolph) if np.isfinite(pv_inner_dv_max_lbmolph) else np.nan,
        "K_state_over_K_thermo_max_abs": (
            float(K_state_over_K_thermo_max_abs) if np.isfinite(K_state_over_K_thermo_max_abs) else np.nan
        ),
        "K_state_minus_K_thermo_max_abs": (
            float(K_state_minus_K_thermo_max_abs) if np.isfinite(K_state_minus_K_thermo_max_abs) else np.nan
        ),
        "steady_state_enabled": float(steady_state_enabled) if np.isfinite(steady_state_enabled) else np.nan,
        "steady_state_flag": float(steady_state_flag) if np.isfinite(steady_state_flag) else np.nan,
        "steady_state_score": float(steady_state_score) if np.isfinite(steady_state_score) else np.nan,
        "steady_state_active_criteria": (
            float(steady_state_active_criteria) if np.isfinite(steady_state_active_criteria) else np.nan
        ),
        "ss_max_rel_state_rate_per_s": (
            float(ss_max_rel_state_rate_per_s) if np.isfinite(ss_max_rel_state_rate_per_s) else np.nan
        ),
        "ss_max_kpi_slope_per_s": float(ss_max_kpi_slope_per_s) if np.isfinite(ss_max_kpi_slope_per_s) else np.nan,
        "ss_max_mv_rate_per_s": float(ss_max_mv_rate_per_s) if np.isfinite(ss_max_mv_rate_per_s) else np.nan,
        "ss_max_temp_rate_F_per_s": (
            float(ss_max_temp_rate_F_per_s) if np.isfinite(ss_max_temp_rate_F_per_s) else np.nan
        ),
        "ss_max_sp_error": float(ss_max_sp_error) if np.isfinite(ss_max_sp_error) else np.nan,
        "ss_window_samples": float(ss_window_samples) if np.isfinite(ss_window_samples) else np.nan,
        "ss_window_sec": float(ss_window_sec) if np.isfinite(ss_window_sec) else np.nan,
        "ss_min_time_sec": float(ss_min_time_sec) if np.isfinite(ss_min_time_sec) else np.nan,
        "ss_tol_rel_state_rate_per_s": (
            float(ss_tol_rel_state_rate_per_s) if np.isfinite(ss_tol_rel_state_rate_per_s) else np.nan
        ),
        "ss_tol_kpi_slope_per_s": (
            float(ss_tol_kpi_slope_per_s) if np.isfinite(ss_tol_kpi_slope_per_s) else np.nan
        ),
        "ss_tol_mv_rate_per_s": float(ss_tol_mv_rate_per_s) if np.isfinite(ss_tol_mv_rate_per_s) else np.nan,
        "ss_tol_temp_rate_F_per_s": (
            float(ss_tol_temp_rate_F_per_s) if np.isfinite(ss_tol_temp_rate_F_per_s) else np.nan
        ),
        "ss_tol_sp_error": float(ss_tol_sp_error) if np.isfinite(ss_tol_sp_error) else np.nan,
        "ss_require_sp": float(ss_require_sp) if np.isfinite(ss_require_sp) else np.nan,
        "integrator_requested_mode": str(integrator_requested_mode),
        "integrator_used_mode": str(integrator_used_mode),
        "integrator_fallback_used": (
            float(integrator_fallback_used) if np.isfinite(integrator_fallback_used) else np.nan
        ),
        "integrator_fallback_reason": str(integrator_fallback_reason),
        "integrator_nfev": float(integrator_nfev) if np.isfinite(integrator_nfev) else np.nan,
        "ida_iter_max": float(ida_iter_max) if np.isfinite(ida_iter_max) else np.nan,
        "ida_iter_mean": float(ida_iter_mean) if np.isfinite(ida_iter_mean) else np.nan,
        "ida_converged": float(ida_converged) if np.isfinite(ida_converged) else np.nan,
        "ida_last_err": float(ida_last_err) if np.isfinite(ida_last_err) else np.nan,
        "ida_alg_p_inf_psia": float(ida_alg_p_inf_psia) if np.isfinite(ida_alg_p_inf_psia) else np.nan,
        "ida_alg_v_inf_lbmolph": float(ida_alg_v_inf_lbmolph) if np.isfinite(ida_alg_v_inf_lbmolph) else np.nan,
        "ida_alg_weighted": float(ida_alg_weighted) if np.isfinite(ida_alg_weighted) else np.nan,
        "ida_alg_converged": float(ida_alg_converged) if np.isfinite(ida_alg_converged) else np.nan,
        "ida_resid_energy_btups": float(ida_resid_energy_btups) if np.isfinite(ida_resid_energy_btups) else np.nan,
        # New: overall stream flow scalars
        "F_lbmolph": float(feed_tag.flow_lbmolph) if feed_tag.flow_lbmolph is not None else np.nan,
        "D_lbmolph": float(dist_tag.flow_lbmolph) if dist_tag.flow_lbmolph is not None else np.nan,
        "B_lbmolph": float(bots_tag.flow_lbmolph) if bots_tag.flow_lbmolph is not None else np.nan,
        "Distillate_L_lbmol": float(top_L_total) if top_L_total is not None else np.nan,
        "Bottoms_L_lbmol": float(bottom_L_total) if bottom_L_total is not None else np.nan,
        "T_sump_F": float(T_sump) if T_sump is not None else np.nan,
    }

    for k in range(Nc):
        label = comp_labels[k]
        out[f"x_Distillate_{label}"] = float(x[0, k])
        out[f"y_Distillate_{label}"] = float(yv[0, k])
        out[f"x_Bottoms_{label}"] = float(x[-1, k])
        out[f"y_Bottoms_{label}"] = float(yv[-1, k])
        if top_x is not None:
            out[f"Distillate_x_{label}"] = float(top_x[k])
        if bottom_x is not None:
            out[f"Bottoms_x_{label}"] = float(bottom_x[k])

    return out


# -------------------------
# Runner
# -------------------------


def run_smoke_simulation(cfg: RunnerConfig) -> Dict[str, Any]:
    milestone_t0 = time.perf_counter()

    def _milestone(label: str) -> None:
        wall = time.perf_counter() - milestone_t0
        clock = _dt.datetime.now().isoformat(timespec="seconds")
        print(f"[Milestone] {label}  wall={wall:8.2f} s  clock={clock}")

    _milestone("start")
    try:
        case = load_case_from_excel(cfg.excel_path)
        _milestone("loaded case from Excel")
    except Exception as exc:
        print("[Validation] FAIL  errors=1  warnings=0")
        print(f"[Validation][Error] Failed to load Excel case: {exc}")
        raise

    try:
        col = build_column_spec_from_case(case)
        _milestone("built column spec")
    except Exception as exc:
        print("[Validation] FAIL  errors=1  warnings=0")
        print(f"[Validation][Error] Failed to build column spec: {exc}")
        raise

    validation = validate_loaded_case(case, col)
    print_validation_report(validation)
    _milestone("validated Excel input")
    if not validation.ok:
        raise ValueError("Excel input validation failed. See [Validation][Error] lines above.")

    dt = float(cfg.dt_sec) if cfg.dt_sec is not None else float(col.sim.dt_sec)
    if dt <= 0.0:
        raise ValueError("dt_sec must be > 0")

    log_every = int(cfg.log_every_n_steps) if cfg.log_every_n_steps is not None else int(col.sim.log_every_n_steps)
    if log_every <= 0:
        raise ValueError("log_every_n_steps must be > 0")

    thermo_every = int(cfg.thermo_every_n_steps)
    if thermo_every <= 0:
        thermo_every = 1

    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=bool(cfg.include_temperature),
        include_energy=bool(cfg.include_energy),
    )
    _milestone("built state vector layout")

    base_inputs, thermo_provider = build_inputs_for_runner(case, col, cfg)
    _milestone("built inputs and thermo provider")
    runtime_mode = _normalize_runtime_mode(getattr(cfg, "runtime_mode", None), default="legacy")
    integrator_mode = _normalize_integrator_mode(getattr(cfg, "integrator", None), default="explicit-euler")
    eff_ida = _effective_hydraulic_ida_profile(
        cfg,
        runtime_mode=str(runtime_mode),
        integrator_mode=str(integrator_mode),
    )
    ida_max_iter_eff = int(eff_ida.get("ida_max_iter", getattr(cfg, "ida_max_iter", 8)))
    dae_pilot_enabled_eff = bool(
        eff_ida.get("dae_pilot_enabled", getattr(cfg, "enable_dae_pilot_algebraic_solve", False))
    )
    dae_pilot_max_iter_eff = int(eff_ida.get("dae_pilot_max_iter", getattr(cfg, "dae_pilot_max_iter", 3)))
    dae_pilot_p_tol_eff = eff_ida.get("dae_pilot_p_tol_psia", getattr(cfg, "dae_pilot_p_tol_psia", None))
    dae_pilot_v_tol_eff = eff_ida.get("dae_pilot_v_tol_lbmolph", getattr(cfg, "dae_pilot_v_tol_lbmolph", None))
    ida_defaults_applied = list(eff_ida.get("defaults_applied", []))

    startup_sequence_enabled = bool(cfg.enable_startup_hydraulic_sequence)
    if runtime_mode in ("parity", "calibration", "hydraulic"):
        if startup_sequence_enabled:
            print(
                f"[Init] runtime_mode={runtime_mode} disables startup hydraulic sequencing; using direct mode behavior."
            )
        startup_sequence_enabled = False
    if runtime_mode in ("parity", "calibration", "hydraulic"):
        print(f"[Init] Runtime mode active: {runtime_mode}")
    if ida_defaults_applied:
        print("[Init] Applied hydraulic+ida defaults: " + ", ".join(str(x) for x in ida_defaults_applied))
    if integrator_mode != "explicit-euler":
        rhs_cap_txt = (
            str(int(cfg.integrator_max_rhs_evals_per_step))
            if cfg.integrator_max_rhs_evals_per_step is not None
            else "off"
        )
        substep_txt = (
            f"{float(cfg.integrator_substep_sec):.3g}s"
            if cfg.integrator_substep_sec is not None
            else "off"
        )
        wall_cap_txt = (
            f"{float(cfg.integrator_step_wall_limit_sec):.3g}s"
            if cfg.integrator_step_wall_limit_sec is not None
            else "off"
        )
        smooth_cfg = getattr(cfg, "stiff_vflow_smooth_clamp_lbmolph", None)
        if smooth_cfg is None:
            smooth_txt = "auto"
        else:
            try:
                smooth_try = float(smooth_cfg)
            except Exception:
                smooth_try = 0.0
            if np.isfinite(smooth_try) and smooth_try > 0.0:
                smooth_txt = f"{smooth_try:.3g} lbmol/h"
            else:
                smooth_txt = "off"
        if integrator_mode in ("bdf", "radau") and _solve_ivp is None:
            print(
                f"[Warn] integrator={integrator_mode} requested but SciPy is unavailable; "
                "falling back to explicit-euler."
            )
        elif integrator_mode == "ida":
            ida_dae_p_txt = "off"
            ida_dae_v_txt = "off"
            try:
                p_tol_try = float(dae_pilot_p_tol_eff) if dae_pilot_p_tol_eff is not None else np.nan
            except Exception:
                p_tol_try = np.nan
            try:
                v_tol_try = float(dae_pilot_v_tol_eff) if dae_pilot_v_tol_eff is not None else np.nan
            except Exception:
                v_tol_try = np.nan
            if np.isfinite(p_tol_try):
                ida_dae_p_txt = f"{p_tol_try:.3g}"
            if np.isfinite(v_tol_try):
                ida_dae_v_txt = f"{v_tol_try:.3g}"
            print(
                "[Init] Integrator active: "
                f"{integrator_mode}  rtol={float(cfg.integrator_rtol):.3g}  "
                f"atol={float(cfg.integrator_atol):.3g}  "
                f"substep={substep_txt}  "
                f"max_rhs={rhs_cap_txt}  wall_cap={wall_cap_txt}  "
                f"ida_max_iter={int(ida_max_iter_eff)}  "
                f"ida_relax={float(getattr(cfg, 'ida_relax', 1.0)):.3g}  "
                f"dae_pilot={'on' if bool(dae_pilot_enabled_eff) else 'off'}  "
                f"dae_p_tol={ida_dae_p_txt}  dae_v_tol={ida_dae_v_txt}  "
                f"stiff_vflow_smooth={smooth_txt}"
            )
        else:
            print(
                "[Init] Integrator active: "
                f"{integrator_mode}  rtol={float(cfg.integrator_rtol):.3g}  "
                f"atol={float(cfg.integrator_atol):.3g}  "
                f"substep={substep_txt}  "
                f"max_rhs={rhs_cap_txt}  wall_cap={wall_cap_txt}  "
                f"stiff_vflow_smooth={smooth_txt}"
            )
    if (
        str(base_inputs.pressure_model).strip().lower() == "hydraulic"
        and str(base_inputs.vapor_flow_model).strip().lower() == "energy"
        and str(base_inputs.condenser_duty_mode).strip().lower() == "total-condense"
    ):
        print(
            "[Warn] hydraulic+energy with condenser-duty-mode=total-condense can be stiff; "
            "consider condenser-duty-mode=specified while approaching steady state."
        )
    if startup_sequence_enabled:
        print(
            "[Init] Startup hydraulic sequencing enabled  "
            f"energy_on={float(cfg.startup_sequence_energy_on_sec):.3g}s  "
            f"liquid_on={float(cfg.startup_sequence_liquid_on_sec):.3g}s  "
            f"liquid_ramp={float(cfg.startup_sequence_liquid_ramp_sec):.3g}s  "
            f"resid_gate={float(cfg.startup_sequence_mass_resid_gate_lbmolph) if cfg.startup_sequence_mass_resid_gate_lbmolph is not None else float('nan'):.3g} lbmol/h"
        )

    last_Z_tray: Optional[np.ndarray] = None
    last_y_eq: Optional[np.ndarray] = None
    last_P_diag: Optional[np.ndarray] = None
    last_P_hyd: Optional[np.ndarray] = None
    last_V_out: Optional[np.ndarray] = None
    last_dT_tray: Optional[np.ndarray] = None
    last_rhoL: Optional[np.ndarray] = None
    last_K_tray: Optional[np.ndarray] = None
    last_HL: Optional[np.ndarray] = None
    last_HV: Optional[np.ndarray] = None
    last_Zfac: Optional[np.ndarray] = None
    last_z_overall: Optional[np.ndarray] = None
    last_diag: Optional[Dict[str, np.ndarray]] = None
    last_reb_T: Optional[float] = None
    last_reb_x: Optional[np.ndarray] = None
    last_reb_y: Optional[np.ndarray] = None
    last_reb_beta: Optional[float] = None
    last_T_tray: Optional[np.ndarray] = None
    last_top_drum_pressure_T: Optional[float] = None
    last_mass_resid_max_lbmolph: Optional[float] = None
    seq_liquid_alpha_state = _clip_unit(base_inputs.liquid_hydraulic_override_alpha, default=1.0)
    if not bool(base_inputs.enable_liquid_hydraulic_override):
        seq_liquid_alpha_state = 0.0

    # Initial conditions from ColumnSpec
    y = layout.pack_y0(col)
    if not bool(cfg.use_excel_vapor_holdup):
        y = _clear_initial_tray_vapor_holdup(y, layout)
    _milestone("packed initial state")

    # Make MV consistent with P_spec at t=0 (uses ideal-gas Z seed at startup).
    init_inputs = base_inputs
    y = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y,
        inputs=init_inputs,
        include_temperature=bool(cfg.include_temperature),
    )
    thermo_init_info = {
        "attempted": False,
        "success": False,
        "n_iter": 0,
        "max_dx": np.nan,
        "max_dy": np.nan,
        "eq_phase_change_init_lbmolps": np.nan,
        "eq_phase_change_final_lbmolps": np.nan,
    }
    if bool(cfg.enable_startup_thermo_conditioning):
        y, thermo_init_info = _initialize_thermo_consistent_state(
            col=col,
            layout=layout,
            y=y,
            inputs=init_inputs,
            include_temperature=bool(cfg.include_temperature),
            max_iter=int(cfg.startup_thermo_conditioning_iters),
            relaxation=float(cfg.startup_thermo_conditioning_relaxation),
        )
        if bool(thermo_init_info.get("attempted", False)):
            eq0 = float(thermo_init_info.get("eq_phase_change_init_lbmolps", np.nan))
            eqf = float(thermo_init_info.get("eq_phase_change_final_lbmolps", np.nan))
            mdx = float(thermo_init_info.get("max_dx", np.nan))
            mdy = float(thermo_init_info.get("max_dy", np.nan))
            nit = int(thermo_init_info.get("n_iter", 0))
            print(
                "[Init] Thermo startup conditioning  "
                f"eq_phase: {eq0:+.6g}->{eqf:+.6g} lbmol/s  "
                f"max_dx={mdx:.3g}  max_dy={mdy:.3g}  "
                f"iters={nit}  success={bool(thermo_init_info.get('success', False))}"
            )
    y, top_drum_init_info = _initialize_top_drum_dynamic_steady(
        col=col,
        layout=layout,
        y=y,
        inputs=init_inputs,
    )
    if bool(top_drum_init_info.get("attempted", False)):
        dL0 = float(top_drum_init_info.get("d_top_L_init_lbmolps", np.nan))
        dV0 = float(top_drum_init_info.get("d_top_V_init_lbmolps", np.nan))
        dLf = float(top_drum_init_info.get("d_top_L_final_lbmolps", np.nan))
        dVf = float(top_drum_init_info.get("d_top_V_final_lbmolps", np.nan))
        iters = int(top_drum_init_info.get("n_iter", 0))
        print(
            "[Init] Top-drum startup steadying  "
            f"dL: {dL0:+.6g}->{dLf:+.6g} lbmol/s  "
            f"dV: {dV0:+.6g}->{dVf:+.6g} lbmol/s  "
            f"iters={iters}  success={bool(top_drum_init_info.get('success', False))}"
        )
    _milestone("initialized vapor holdup from spec pressure")

    # Resolve streams for logging placement
    feed_tag, dist_tag, bots_tag = _resolve_logging_streams(case, col)
    _milestone("resolved logging stream placement")
    level_control_enabled, top_level_ctrl, bot_level_ctrl, top_level_sp, bot_level_sp = _build_level_controllers(
        col=col,
        cfg=cfg,
        layout=layout,
        y0=y,
        dist_tag=dist_tag,
        bots_tag=bots_tag,
    )
    if level_control_enabled:
        print(
            "[Control] Level control enabled  "
            f"top_SP={float(top_level_sp):.3f} lbmol  bottom_SP={float(bot_level_sp):.3f} lbmol"
        )
    (
        pressure_control_enabled,
        top_pressure_ctrl,
        top_pressure_sp,
        pressure_control_mv,
        pressure_mode_note,
    ) = _build_pressure_controller(
        col=col,
        cfg=cfg,
    )
    top_pressure_resid_ref_btups = cfg.top_pressure_resid_ref_btups
    top_pressure_resid_ref_auto = False
    if top_pressure_resid_ref_btups is None:
        specs = getattr(col, "specs_raw", None) or {}
        top_pressure_resid_ref_btups = _spec_float(
            specs,
            "Top Pressure Resid Ref (BTU/s)",
            "Top Pressure Resid Ref (Btu/s)",
            "Top Pressure Residual Ref (BTU/s)",
            "Top Pressure Residual Reference (BTU/s)",
        )
    if top_pressure_resid_ref_btups is None:
        if (
            str(base_inputs.pressure_model).strip().lower() == "hydraulic"
            and str(base_inputs.vapor_flow_model).strip().lower() == "energy"
        ):
            top_pressure_resid_ref_btups = 250.0
            top_pressure_resid_ref_auto = True
    if top_pressure_resid_ref_btups is not None:
        try:
            top_pressure_resid_ref_btups = float(top_pressure_resid_ref_btups)
            if (not np.isfinite(top_pressure_resid_ref_btups)) or top_pressure_resid_ref_btups <= 0.0:
                top_pressure_resid_ref_btups = None
                top_pressure_resid_ref_auto = False
        except Exception:
            top_pressure_resid_ref_btups = None
            top_pressure_resid_ref_auto = False
    if pressure_control_enabled and top_pressure_ctrl is not None and top_pressure_sp is not None:
        if pressure_mode_note:
            print(f"[Warn] {pressure_mode_note}")
        pv_tau_txt = "off"
        if cfg.top_pressure_pv_filter_tau_sec is not None and np.isfinite(float(cfg.top_pressure_pv_filter_tau_sec)):
            pv_tau_txt = f"{float(cfg.top_pressure_pv_filter_tau_sec):.3g}s"
        mv_slew_txt = "off"
        if cfg.top_pressure_mv_slew_limit_per_s is not None and np.isfinite(float(cfg.top_pressure_mv_slew_limit_per_s)):
            mv_slew_txt = f"{float(cfg.top_pressure_mv_slew_limit_per_s):.3g}/s"
        resid_ref_txt = "off"
        if top_pressure_resid_ref_btups is not None and np.isfinite(float(top_pressure_resid_ref_btups)):
            resid_ref_txt = f"{float(top_pressure_resid_ref_btups):.3g} BTU/s"
            if top_pressure_resid_ref_auto:
                resid_ref_txt += " (auto)"
        print(
            "[Control] Pressure control enabled  "
            f"MV={str(pressure_control_mv)}  "
            f"top_P_SP={float(top_pressure_sp):.3f} psia  "
            f"Kc={float(top_pressure_ctrl.kc):.3g}  Ti={float(top_pressure_ctrl.ti_sec):.3g} s  "
            f"PV_tau={pv_tau_txt}  "
            f"MV_slew={mv_slew_txt}  "
            f"resid_ref={resid_ref_txt}  "
            f"resid_min_gain={float(cfg.top_pressure_resid_min_gain):.3g}"
        )
    comp_control_enabled, dist_comp_ctrl, dist_comp_sp, dist_comp_idx, dist_comp_name = _build_distillate_composition_controller(
        col=col,
        cfg=cfg,
        boundary=base_inputs.boundary,
        dist_tag=dist_tag,
    )
    if comp_control_enabled and dist_comp_ctrl is not None and dist_comp_sp is not None and dist_comp_idx is not None:
        print(
            "[Control] Distillate composition control enabled  "
            f"component={str(dist_comp_name)}  "
            f"x_SP={float(dist_comp_sp):.6f}  "
            f"Kc={float(dist_comp_ctrl.kc):.3g}  Ti={float(dist_comp_ctrl.ti_sec):.3g} s  "
            f"MV=reflux_lbmolph  limits=({float(dist_comp_ctrl.out_min):.3f}, {float(dist_comp_ctrl.out_max):.3f})"
        )
        if not bool(getattr(cfg, "enable_reflux_feasibility_cap", True)):
            print("[Control] Distillate reflux feasibility cap disabled")
    (
        bot_comp_control_enabled,
        bot_comp_mv_mode,
        bot_comp_ctrl,
        bot_comp_sp,
        bot_comp_idx,
        bot_comp_name,
    ) = _build_bottoms_composition_controller(
        col=col,
        cfg=cfg,
        boundary=base_inputs.boundary,
    )
    if bot_comp_control_enabled and bot_comp_ctrl is not None and bot_comp_sp is not None and bot_comp_idx is not None:
        mv_label = "boilup_lbmolph" if str(bot_comp_mv_mode) != "reboiler-duty" else "reboiler_duty_btuph"
        print(
            "[Control] Bottoms composition control enabled  "
            f"component={str(bot_comp_name)}  "
            f"x_SP={float(bot_comp_sp):.6f}  "
            f"Kc={float(bot_comp_ctrl.kc):.3g}  Ti={float(bot_comp_ctrl.ti_sec):.3g} s  "
            f"MV={mv_label}  limits=({float(bot_comp_ctrl.out_min):.3f}, {float(bot_comp_ctrl.out_max):.3f})"
        )

    last_top_pressure_pv_psia: Optional[float] = None
    last_top_pressure_pv_filt_psia: Optional[float] = None
    last_top_energy_resid_abs_btups: Optional[float] = None
    last_pressure_mv_cmd: Optional[float] = None
    try:
        p_ctrl_idx = 0
        p0 = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[p_ctrl_idx])
        if np.isfinite(p0) and p0 > 0.0:
            last_top_pressure_pv_psia = p0
            last_top_pressure_pv_filt_psia = p0
    except Exception:
        pass
    if pressure_control_enabled and top_pressure_ctrl is not None:
        try:
            last_pressure_mv_cmd = float(top_pressure_ctrl.bias)
        except Exception:
            last_pressure_mv_cmd = None

    tag = _timestamp_tag()
    logs_dir = Path(cfg.logs_dir)
    if not logs_dir.is_absolute():
        logs_dir = Path.cwd() / logs_dir
    if cfg.write_logs:
        _ensure_dir(logs_dir)
        _milestone(f"ensured logs directory: {logs_dir}")

    profile_path = logs_dir / f"column_profile_{tag}.csv"
    summary_path = logs_dir / f"column_summary_{tag}.csv"

    profile_file = None
    summary_file = None

    start_perf = time.perf_counter()
    t_s = 0.0
    global_mass_closure_cum_lbmol = 0.0
    integrator_fallback_count = 0
    last_step_integrator_info: Dict[str, Any] = {"requested_mode": str(integrator_mode)}
    steady_state_status_last: Dict[str, float] = {
        "steady_state_flag": np.nan,
        "steady_state_score": np.nan,
        "ss_max_rel_state_rate_per_s": np.nan,
        "ss_max_kpi_slope_per_s": np.nan,
        "ss_max_mv_rate_per_s": np.nan,
        "ss_max_temp_rate_F_per_s": np.nan,
        "ss_max_sp_error": np.nan,
    }

    ss_enabled = bool(getattr(cfg, "enable_steady_state_detection", True))
    try:
        ss_window_sec = float(getattr(cfg, "steady_state_window_sec", 30.0))
    except Exception:
        ss_window_sec = 30.0
    if (not np.isfinite(ss_window_sec)) or ss_window_sec <= 0.0:
        ss_window_sec = max(float(dt), 1e-9)
    try:
        ss_min_time_sec = float(getattr(cfg, "steady_state_min_time_sec", 60.0))
    except Exception:
        ss_min_time_sec = 60.0
    if (not np.isfinite(ss_min_time_sec)) or ss_min_time_sec < 0.0:
        ss_min_time_sec = 0.0
    try:
        ss_rate_floor_lbmol = float(getattr(cfg, "steady_state_rate_denom_floor_lbmol", 1.0))
    except Exception:
        ss_rate_floor_lbmol = 1.0
    if (not np.isfinite(ss_rate_floor_lbmol)) or ss_rate_floor_lbmol < 0.0:
        ss_rate_floor_lbmol = 1.0

    def _tol_or_none(v: Any) -> Optional[float]:
        try:
            x = float(v)
        except Exception:
            return None
        if (not np.isfinite(x)) or x <= 0.0:
            return None
        return float(x)

    ss_tol_rel = _tol_or_none(getattr(cfg, "steady_state_rel_state_rate_tol_per_s", None))
    ss_tol_kpi = _tol_or_none(getattr(cfg, "steady_state_kpi_slope_tol_per_s", None))
    ss_tol_mv = _tol_or_none(getattr(cfg, "steady_state_mv_rate_tol_per_s", None))
    ss_tol_temp = _tol_or_none(getattr(cfg, "steady_state_temp_rate_tol_F_per_s", None))
    ss_tol_sp = _tol_or_none(getattr(cfg, "steady_state_sp_error_tol", None))
    ss_require_sp = bool(getattr(cfg, "steady_state_require_sp", False))

    ss_hist: deque = deque()
    ss_prev_t_s: Optional[float] = None
    ss_prev_y: Optional[np.ndarray] = None
    if ss_enabled:
        print(
            "[Init] Steady-state detector enabled  "
            f"window={float(ss_window_sec):.3g}s  "
            f"min_time={float(ss_min_time_sec):.3g}s  "
            f"tol_rel={float(ss_tol_rel) if ss_tol_rel is not None else float('nan'):.3g}/s  "
            f"tol_kpi={float(ss_tol_kpi) if ss_tol_kpi is not None else float('nan'):.3g}/s  "
            f"tol_mv={float(ss_tol_mv) if ss_tol_mv is not None else float('nan'):.3g}/s  "
            f"tol_T={float(ss_tol_temp) if ss_tol_temp is not None else float('nan'):.3g}F/s  "
            f"tol_sp={float(ss_tol_sp) if ss_tol_sp is not None else float('nan'):.3g}  "
            f"require_sp={'on' if ss_require_sp else 'off'}"
        )

    try:
        if cfg.write_logs:
            profile_file = profile_path.open("w", newline="", encoding="utf-8")
            summary_file = summary_path.open("w", newline="", encoding="utf-8")
            _milestone("opened log files")

        profile_writer = None
        summary_writer = None
        profile_header_written = False
        summary_header_written = False

        # Visual separator between startup milestones and runtime progress output.
        print()

        for step in range(int(cfg.n_steps) + 1):
            step_boundary = base_inputs.boundary
            step_dist_tag = dist_tag
            step_bots_tag = bots_tag
            step_condenser_duty_mode = str(base_inputs.condenser_duty_mode)
            step_condenser_duty_btu_per_h = (
                float(base_inputs.condenser_duty_btu_per_h)
                if base_inputs.condenser_duty_btu_per_h is not None
                else None
            )
            step_condenser_duty_trim_btu_per_h: Optional[float] = (
                float(base_inputs.condenser_duty_trim_btu_per_h)
                if base_inputs.condenser_duty_trim_btu_per_h is not None
                else None
            )
            step_condenser_duty_cmd_btu_per_h: Optional[float] = None
            step_reboiler_mode = str(base_inputs.reboiler_mode)
            step_reboiler_duty_btu_per_h: Optional[float] = (
                float(base_inputs.reboiler_duty_btu_per_h)
                if base_inputs.reboiler_duty_btu_per_h is not None
                else None
            )
            step_reboiler_duty_trim_btu_per_h: Optional[float] = (
                float(base_inputs.reboiler_duty_trim_btu_per_h)
                if base_inputs.reboiler_duty_trim_btu_per_h is not None
                else None
            )
            step_reboiler_duty_cmd_btu_per_h: Optional[float] = None
            step_pressure_top_anchor_psia: Optional[float] = (
                float(base_inputs.pressure_top_anchor_psia)
                if base_inputs.pressure_top_anchor_psia is not None
                else None
            )
            step_pressure_top_anchor_cmd_psia: Optional[float] = None
            step_distillate_comp_pv: Optional[float] = None
            step_distillate_comp_sp: Optional[float] = None
            step_reflux_ratio_cmd: Optional[float] = None
            step_reflux_cmd_lbmolph: Optional[float] = None
            step_bottoms_comp_pv: Optional[float] = None
            step_bottoms_comp_sp: Optional[float] = None
            step_boilup_cmd_lbmolph: Optional[float] = None
            step_pressure_ctrl_pv_raw_psia: Optional[float] = None
            step_pressure_ctrl_pv_filt_psia: Optional[float] = None
            step_pressure_ctrl_gain_scale: Optional[float] = None
            step_pressure_ctrl_energy_resid_abs_btups: Optional[float] = None
            controllers_active = step > 0
            if (
                level_control_enabled
                and top_level_ctrl is not None
                and bot_level_ctrl is not None
                and top_level_sp is not None
                and bot_level_sp is not None
            ):
                u_now = layout.unpack(y)
                top_level_pv = float(np.sum(np.asarray(u_now.get("top_L", []), dtype=float)))
                bot_level_pv = float(np.sum(np.asarray(u_now.get("bottom_L", []), dtype=float)))
                if controllers_active:
                    dist_cmd = _pi_update(
                        top_level_ctrl,
                        pv=top_level_pv,
                        sp=float(top_level_sp),
                        dt_sec=float(dt),
                    )
                    bot_cmd = _pi_update(
                        bot_level_ctrl,
                        pv=bot_level_pv,
                        sp=float(bot_level_sp),
                        dt_sec=float(dt),
                    )
                else:
                    if step_boundary.distillate_lbmolph is not None:
                        dist_cmd = float(step_boundary.distillate_lbmolph)
                    else:
                        dist_cmd = float(dist_tag.flow_lbmolph)
                    if step_boundary.bottoms_lbmolph is not None:
                        bot_cmd = float(step_boundary.bottoms_lbmolph)
                    else:
                        bot_cmd = float(bots_tag.flow_lbmolph)
                step_boundary = BoundaryFlows(
                    reflux_lbmolph=base_inputs.boundary.reflux_lbmolph,
                    boilup_lbmolph=base_inputs.boundary.boilup_lbmolph,
                    distillate_lbmolph=float(dist_cmd),
                    bottoms_lbmolph=float(bot_cmd),
                )
                step_dist_tag = StreamTag(
                    name=dist_tag.name,
                    flow_lbmolph=float(dist_cmd),
                    stage_1based=dist_tag.stage_1based,
                )
                step_bots_tag = StreamTag(
                    name=bots_tag.name,
                    flow_lbmolph=float(bot_cmd),
                    stage_1based=bots_tag.stage_1based,
                )
            if (
                comp_control_enabled
                and dist_comp_ctrl is not None
                and dist_comp_sp is not None
                and dist_comp_idx is not None
            ):
                u_now = layout.unpack(y)
                top_liq = np.asarray(u_now.get("top_L", []), dtype=float).reshape((-1,))
                xD_pv = np.nan
                top_total = np.nan
                if top_liq.size == int(col.n_components):
                    top_total = float(np.sum(top_liq))
                    if np.isfinite(top_total) and top_total > 0.0:
                        xD_vec = top_liq / max(top_total, 1e-300)
                        xD_pv = float(xD_vec[int(dist_comp_idx)])

                # Reflux feasibility clamp:
                # keep reflux bounded by condenser liquid generation plus a limited
                # drawdown of reflux-drum inventory so composition control cannot
                # starve top holdup and force distillate draw to zero.
                d_cmd_lbmolph = np.nan
                if step_boundary.distillate_lbmolph is not None:
                    d_cmd_lbmolph = float(step_boundary.distillate_lbmolph)
                elif step_dist_tag.flow_lbmolph is not None:
                    d_cmd_lbmolph = float(step_dist_tag.flow_lbmolph)
                elif dist_tag.flow_lbmolph is not None:
                    d_cmd_lbmolph = float(dist_tag.flow_lbmolph)
                if (not np.isfinite(d_cmd_lbmolph)) or d_cmd_lbmolph < 0.0:
                    d_cmd_lbmolph = 0.0

                vin0_est_lbmolph = np.nan
                try:
                    if last_V_out is not None:
                        vprev = np.asarray(last_V_out, dtype=float).reshape((-1,))
                        if vprev.size > 1 and np.isfinite(float(vprev[1])):
                            vin0_est_lbmolph = float(vprev[1])
                        elif vprev.size > 0 and np.isfinite(float(vprev[0])):
                            vin0_est_lbmolph = float(vprev[0])
                except Exception:
                    vin0_est_lbmolph = np.nan
                if (not np.isfinite(vin0_est_lbmolph)) and int(getattr(col, "n_stages", 0)) > 1:
                    try:
                        vprof = np.asarray(getattr(col, "V_lbmolph"), dtype=float).reshape((-1,))
                        if vprof.size > 1 and np.isfinite(float(vprof[1])):
                            vin0_est_lbmolph = float(vprof[1])
                    except Exception:
                        vin0_est_lbmolph = np.nan
                if (not np.isfinite(vin0_est_lbmolph)) or vin0_est_lbmolph < 0.0:
                    vin0_est_lbmolph = 0.0

                reflux_max_feasible = float(dist_comp_ctrl.out_max)
                if bool(getattr(cfg, "enable_reflux_feasibility_cap", True)):
                    if np.isfinite(top_total):
                        # Keep top inventory moving toward its level setpoint so the
                        # composition loop cannot pin operation at D=0 while draining
                        # (or holding low) reflux-drum holdup.
                        top_sp = float(top_level_sp) if top_level_sp is not None and np.isfinite(float(top_level_sp)) else top_total
                        recover_tau_sec = 120.0
                        if top_level_ctrl is not None and np.isfinite(float(top_level_ctrl.ti_sec)):
                            recover_tau_sec = max(float(top_level_ctrl.ti_sec), 30.0)
                        desired_dM_top_lbmolph = (float(top_sp) - float(top_total)) * 3600.0 / max(recover_tau_sec, 1e-9)
                        sustainable_lbmolph = float(vin0_est_lbmolph) - float(d_cmd_lbmolph)
                        reflux_max_feasible = min(
                            float(dist_comp_ctrl.out_max),
                            max(0.0, sustainable_lbmolph - desired_dM_top_lbmolph),
                        )
                    reflux_max_feasible = max(float(dist_comp_ctrl.out_min), float(reflux_max_feasible))

                if controllers_active:
                    reflux_cmd = _pi_update(
                        dist_comp_ctrl,
                        pv=float(xD_pv),
                        sp=float(dist_comp_sp),
                        dt_sec=float(dt),
                        out_max=float(reflux_max_feasible),
                    )
                else:
                    if step_boundary.reflux_lbmolph is not None:
                        reflux_cmd = float(step_boundary.reflux_lbmolph)
                    else:
                        reflux_cmd = float(reflux_tag.flow_lbmolph)
                step_boundary = BoundaryFlows(
                    reflux_lbmolph=float(reflux_cmd),
                    boilup_lbmolph=step_boundary.boilup_lbmolph,
                    distillate_lbmolph=step_boundary.distillate_lbmolph,
                    bottoms_lbmolph=step_boundary.bottoms_lbmolph,
                )
                step_reflux_cmd_lbmolph = float(reflux_cmd)
                d_for_ratio = np.nan
                if step_boundary.distillate_lbmolph is not None:
                    d_for_ratio = float(step_boundary.distillate_lbmolph)
                elif step_dist_tag.flow_lbmolph is not None:
                    d_for_ratio = float(step_dist_tag.flow_lbmolph)
                elif dist_tag.flow_lbmolph is not None:
                    d_for_ratio = float(dist_tag.flow_lbmolph)
                step_distillate_comp_pv = float(xD_pv) if np.isfinite(xD_pv) else np.nan
                step_distillate_comp_sp = float(dist_comp_sp)
                if np.isfinite(d_for_ratio) and d_for_ratio > 0.0:
                    step_reflux_ratio_cmd = float(reflux_cmd) / float(d_for_ratio)
            if (
                bot_comp_control_enabled
                and bot_comp_ctrl is not None
                and bot_comp_sp is not None
                and bot_comp_idx is not None
            ):
                u_now = layout.unpack(y)
                bot_liq = np.asarray(u_now.get("bottom_L", []), dtype=float).reshape((-1,))
                xB_pv = np.nan
                if bot_liq.size == int(col.n_components):
                    bot_total = float(np.sum(bot_liq))
                    if np.isfinite(bot_total) and bot_total > 0.0:
                        xB_vec = bot_liq / max(bot_total, 1e-300)
                        xB_pv = float(xB_vec[int(bot_comp_idx)])
                if controllers_active:
                    boilup_cmd = _pi_update(
                        bot_comp_ctrl,
                        pv=float(xB_pv),
                        sp=float(bot_comp_sp),
                        dt_sec=float(dt),
                    )
                elif str(bot_comp_mv_mode) == "reboiler-duty":
                    if step_reboiler_duty_btu_per_h is not None:
                        boilup_cmd = float(step_reboiler_duty_btu_per_h)
                    else:
                        boilup_cmd = float(bot_comp_ctrl.bias)
                else:
                    if step_boundary.boilup_lbmolph is not None:
                        boilup_cmd = float(step_boundary.boilup_lbmolph)
                    else:
                        boilup_cmd = float(boilup_tag.flow_lbmolph)
                if str(bot_comp_mv_mode) == "reboiler-duty":
                    step_reboiler_mode = "duty"
                    step_reboiler_duty_btu_per_h = float(boilup_cmd)
                    step_reboiler_duty_cmd_btu_per_h = float(boilup_cmd)
                else:
                    step_boundary = BoundaryFlows(
                        reflux_lbmolph=step_boundary.reflux_lbmolph,
                        boilup_lbmolph=float(boilup_cmd),
                        distillate_lbmolph=step_boundary.distillate_lbmolph,
                        bottoms_lbmolph=step_boundary.bottoms_lbmolph,
                    )
                    step_boilup_cmd_lbmolph = float(boilup_cmd)
                step_bottoms_comp_pv = float(xB_pv) if np.isfinite(xB_pv) else np.nan
                step_bottoms_comp_sp = float(bot_comp_sp)

            if pressure_control_enabled and top_pressure_ctrl is not None and top_pressure_sp is not None:
                p_ctrl_idx = 0
                pv_raw = None
                if last_top_pressure_pv_psia is not None:
                    try:
                        pv_try = float(last_top_pressure_pv_psia)
                        if np.isfinite(pv_try) and pv_try > 0.0:
                            pv_raw = pv_try
                    except Exception:
                        pv_raw = None
                if pv_raw is None:
                    try:
                        pv_raw = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[p_ctrl_idx])
                    except Exception:
                        pv_raw = float(top_pressure_sp)
                step_pressure_ctrl_pv_raw_psia = float(pv_raw)

                pv = float(pv_raw)
                pv_tau = cfg.top_pressure_pv_filter_tau_sec
                if (
                    pv_tau is not None
                    and np.isfinite(float(pv_tau))
                    and float(pv_tau) > 0.0
                ):
                    if last_top_pressure_pv_filt_psia is None or (not np.isfinite(float(last_top_pressure_pv_filt_psia))):
                        pv = float(pv_raw)
                    else:
                        alpha = float(dt) / (float(pv_tau) + float(dt))
                        alpha = float(np.clip(alpha, 0.0, 1.0))
                        pv = float(last_top_pressure_pv_filt_psia) + alpha * (float(pv_raw) - float(last_top_pressure_pv_filt_psia))
                last_top_pressure_pv_filt_psia = float(pv)
                step_pressure_ctrl_pv_filt_psia = float(pv)

                gain_scale = _pressure_resid_gain_scale(
                    resid_abs_btups=last_top_energy_resid_abs_btups,
                    resid_ref_btups=top_pressure_resid_ref_btups,
                    min_gain=float(cfg.top_pressure_resid_min_gain),
                )
                step_pressure_ctrl_gain_scale = float(gain_scale)
                if last_top_energy_resid_abs_btups is not None and np.isfinite(float(last_top_energy_resid_abs_btups)):
                    step_pressure_ctrl_energy_resid_abs_btups = float(last_top_energy_resid_abs_btups)

                if controllers_active:
                    if gain_scale < (1.0 - 1e-12):
                        damped_ctrl = PIController(
                            kc=float(top_pressure_ctrl.kc) * float(gain_scale),
                            ti_sec=float(top_pressure_ctrl.ti_sec),
                            bias=float(top_pressure_ctrl.bias),
                            out_min=float(top_pressure_ctrl.out_min),
                            out_max=float(top_pressure_ctrl.out_max),
                            integ=float(top_pressure_ctrl.integ),
                        )
                        q_cmd = _pi_update(
                            damped_ctrl,
                            pv=float(pv),
                            sp=float(top_pressure_sp),
                            dt_sec=float(dt),
                        )
                        # Keep integrator continuity in the primary controller state.
                        top_pressure_ctrl.integ = float(damped_ctrl.integ)
                    else:
                        q_cmd = _pi_update(
                            top_pressure_ctrl,
                            pv=float(pv),
                            sp=float(top_pressure_sp),
                            dt_sec=float(dt),
                        )
                elif str(pressure_control_mv) == "top-anchor":
                    if step_pressure_top_anchor_psia is not None:
                        q_cmd = float(step_pressure_top_anchor_psia)
                    else:
                        q_cmd = float(top_pressure_ctrl.bias)
                elif step_condenser_duty_btu_per_h is not None:
                    q_cmd = float(step_condenser_duty_btu_per_h)
                else:
                    q_cmd = float(top_pressure_ctrl.bias)

                if controllers_active:
                    q_cmd = _apply_slew_limit(
                        cmd=float(q_cmd),
                        prev_cmd=last_pressure_mv_cmd,
                        rate_limit_per_s=cfg.top_pressure_mv_slew_limit_per_s,
                        dt_sec=float(dt),
                    )
                last_pressure_mv_cmd = float(q_cmd)

                if str(pressure_control_mv) == "top-anchor":
                    step_pressure_top_anchor_cmd_psia = float(q_cmd)
                    step_pressure_top_anchor_psia = float(q_cmd)
                else:
                    step_condenser_duty_cmd_btu_per_h = float(q_cmd)
                    if controllers_active and str(step_condenser_duty_mode).strip().lower() == "total-condense":
                        # Keep total-condense closure and apply PI as a duty trim.
                        ctrl_trim = float(q_cmd) - float(top_pressure_ctrl.bias)
                        base_trim = float(step_condenser_duty_trim_btu_per_h) if step_condenser_duty_trim_btu_per_h is not None else 0.0
                        step_condenser_duty_trim_btu_per_h = base_trim + ctrl_trim
                    else:
                        step_condenser_duty_mode = "specified"
                        step_condenser_duty_btu_per_h = float(q_cmd)

            pressure_model_step, vapor_flow_model_step, seq_liquid_alpha_state, seq_phase = (
                _resolve_startup_hydraulic_sequence_step(
                    t_s=float(t_s),
                    dt_sec=float(dt),
                    base_inputs=base_inputs,
                    enable_sequence=bool(startup_sequence_enabled),
                    energy_on_sec=float(cfg.startup_sequence_energy_on_sec),
                    liquid_on_sec=float(cfg.startup_sequence_liquid_on_sec),
                    liquid_ramp_sec=float(cfg.startup_sequence_liquid_ramp_sec),
                    liquid_resid_gate_lbmolph=cfg.startup_sequence_mass_resid_gate_lbmolph,
                    liquid_backoff_sec=cfg.startup_sequence_liquid_backoff_sec,
                    liquid_alpha_state=float(seq_liquid_alpha_state),
                    last_mass_resid_max_lbmolph=last_mass_resid_max_lbmolph,
                )
            )

            do_thermo = (step % thermo_every) == 0
            refresh_by_state = (
                (base_inputs.thermo_refresh_dT_F is not None)
                or (base_inputs.thermo_refresh_dP_psia is not None)
                or (base_inputs.thermo_refresh_dx is not None)
            )
            if refresh_by_state:
                thermo_event = False
                missing_history = False
                try:
                    N = int(col.n_stages)
                    Nc = int(col.n_components)
                    u_probe = layout.unpack(y)
                    T_now = _tray_temperature_F(
                        col,
                        layout,
                        y,
                        include_temperature=bool(cfg.include_temperature),
                    )

                    if base_inputs.thermo_refresh_dT_F is not None:
                        if last_T_tray is None:
                            missing_history = True
                        else:
                            dT_max = float(np.nanmax(np.abs(np.asarray(T_now, dtype=float) - np.asarray(last_T_tray, dtype=float))))
                            if np.isfinite(dT_max) and dT_max >= float(base_inputs.thermo_refresh_dT_F):
                                thermo_event = True

                    if base_inputs.thermo_refresh_dP_psia is not None:
                        P_prev = last_P_hyd if last_P_hyd is not None else last_P_diag
                        if P_prev is None:
                            missing_history = True
                        else:
                            MV_now = np.asarray(u_probe["MV_tot_tray"], dtype=float).reshape((N,))
                            Z_for_p = (
                                np.asarray(last_Zfac, dtype=float).reshape((N,))
                                if last_Zfac is not None
                                else np.ones(N, dtype=float)
                            )
                            P_now = _pressure_diag_psia(
                                col,
                                base_inputs.volume_model,
                                np.asarray(T_now, dtype=float).reshape((N,)),
                                MV_now,
                                Z_for_p,
                            )
                            dP_max = float(
                                np.nanmax(
                                    np.abs(
                                        np.asarray(P_now, dtype=float).reshape((N,))
                                        - np.asarray(P_prev, dtype=float).reshape((N,))
                                    )
                                )
                            )
                            if np.isfinite(dP_max) and dP_max >= float(base_inputs.thermo_refresh_dP_psia):
                                thermo_event = True

                    if base_inputs.thermo_refresh_dx is not None:
                        if last_z_overall is None:
                            missing_history = True
                        else:
                            tray_L_now = np.asarray(u_probe["tray_L"], dtype=float).reshape((N, Nc))
                            tray_V_now = np.asarray(u_probe["tray_V"], dtype=float).reshape((N, Nc))
                            x_now = np.asarray(u_probe["x_tray"], dtype=float).reshape((N, Nc))
                            z_now = np.zeros((N, Nc), dtype=float)
                            for i in range(N):
                                z_i = tray_L_now[i, :] + tray_V_now[i, :]
                                s_i = float(np.sum(z_i))
                                if (not np.isfinite(s_i)) or s_i <= 1e-300:
                                    z_i = x_now[i, :]
                                    s_i = float(np.sum(z_i))
                                z_now[i, :] = z_i / max(s_i, 1e-300)
                            dx_max = float(
                                np.nanmax(
                                    np.abs(
                                        np.asarray(z_now, dtype=float).reshape((N, Nc))
                                        - np.asarray(last_z_overall, dtype=float).reshape((N, Nc))
                                    )
                                )
                            )
                            if np.isfinite(dx_max) and dx_max >= float(base_inputs.thermo_refresh_dx):
                                thermo_event = True
                except Exception:
                    missing_history = True

                if missing_history:
                    do_thermo = True
                else:
                    do_thermo = bool(do_thermo or thermo_event)
            if (not do_thermo) and bool(base_inputs.equilibrium_relaxation) and (last_K_tray is None):
                # Equilibrium relaxation on skipped-thermo steps needs cached K.
                do_thermo = True

            if do_thermo:
                inputs = ColumnInputs(
                    boundary=step_boundary,
                    volume_model=base_inputs.volume_model,
                    thermo=base_inputs.thermo,
                    thermo_provider=base_inputs.thermo_provider,
                    compute_thermo_diag=base_inputs.compute_thermo_diag,
                    equilibrium_relaxation=base_inputs.equilibrium_relaxation,
                    equilibrium_relaxation_mode=base_inputs.equilibrium_relaxation_mode,
                    tau_eq_sec=base_inputs.tau_eq_sec,
                    condenser_alpha=base_inputs.condenser_alpha,
                    clamp_alpha=base_inputs.clamp_alpha,
                    condenser_duty_mode=str(step_condenser_duty_mode),
                    condenser_duty_btu_per_h=(
                        float(step_condenser_duty_btu_per_h)
                        if step_condenser_duty_btu_per_h is not None
                        else None
                    ),
                    condenser_duty_trim_btu_per_h=(
                        float(step_condenser_duty_trim_btu_per_h)
                        if step_condenser_duty_trim_btu_per_h is not None
                        else None
                    ),
                    reboiler_mode=str(step_reboiler_mode),
                    reboiler_duty_btu_per_h=(
                        float(step_reboiler_duty_btu_per_h)
                        if step_reboiler_duty_btu_per_h is not None
                        else None
                    ),
                    reboiler_duty_trim_btu_per_h=(
                        float(step_reboiler_duty_trim_btu_per_h)
                        if step_reboiler_duty_trim_btu_per_h is not None
                        else None
                    ),
                    reboiler_equilibrium=base_inputs.reboiler_equilibrium,
                    pressure_model=str(pressure_model_step),
                    pressure_top_anchor_psia=(
                        float(step_pressure_top_anchor_psia)
                        if step_pressure_top_anchor_psia is not None
                        else None
                    ),
                    condenser_pressure_drop_psi=base_inputs.condenser_pressure_drop_psi,
                    top_drum_vapor_volume_ft3=base_inputs.top_drum_vapor_volume_ft3,
                    top_drum_total_volume_ft3=base_inputs.top_drum_total_volume_ft3,
                    enforce_top_drum_pressure_gate=base_inputs.enforce_top_drum_pressure_gate,
                    top_drum_pressure_gate_soft_psi=base_inputs.top_drum_pressure_gate_soft_psi,
                    enforce_top_pressure_ordering=base_inputs.enforce_top_pressure_ordering,
                    top_pressure_ordering_margin_psi=base_inputs.top_pressure_ordering_margin_psi,
                    enable_top_drum_psv=base_inputs.enable_top_drum_psv,
                    top_drum_psv_setpoint_psia=base_inputs.top_drum_psv_setpoint_psia,
                    top_drum_psv_gain_lbmolps_per_psi=base_inputs.top_drum_psv_gain_lbmolps_per_psi,
                    top_drum_psv_max_vent_lbmolps=base_inputs.top_drum_psv_max_vent_lbmolps,
                    vapor_flow_model=str(vapor_flow_model_step),
                    dry_tray_K=base_inputs.dry_tray_K,
                    vapor_holdup_relaxation_sec=base_inputs.vapor_holdup_relaxation_sec,
                    hydraulic_pressure_relaxation_sec=base_inputs.hydraulic_pressure_relaxation_sec,
                    top_drum_pressure_temperature_relaxation_sec=(
                        base_inputs.top_drum_pressure_temperature_relaxation_sec
                    ),
                    top_drum_pressure_T_prev_F=last_top_drum_pressure_T,
                    vapor_flow_relaxation_sec=base_inputs.vapor_flow_relaxation_sec,
                    conductance_vflow_nominal_hi_ratio=(
                        base_inputs.conductance_vflow_nominal_hi_ratio
                    ),
                    reboiler_neighbor_vflow_hi_ratio=base_inputs.reboiler_neighbor_vflow_hi_ratio,
                    reboiler_neighbor_vflow_lo_ratio=base_inputs.reboiler_neighbor_vflow_lo_ratio,
                    thermo_refresh_dT_F=base_inputs.thermo_refresh_dT_F,
                    thermo_refresh_dP_psia=base_inputs.thermo_refresh_dP_psia,
                    thermo_refresh_dx=base_inputs.thermo_refresh_dx,
                    enable_liquid_hydraulic_override=base_inputs.enable_liquid_hydraulic_override,
                    liquid_hydraulic_override_alpha=float(seq_liquid_alpha_state),
                    component_mw_lbm_per_lbmol=base_inputs.component_mw_lbm_per_lbmol,
                    P_tray_prev=last_P_hyd if last_P_hyd is not None else last_P_diag,
                    V_out_prev_lbmolph=last_V_out,
                    dT_tray_target_F_per_s=last_dT_tray,
                    T_tray_prev_F=last_T_tray,
                    Z_overall_prev=last_z_overall,
                    rhoL_tray_lbmol_ft3=last_rhoL,
                    K_tray_prev=last_K_tray,
                    HL_prev=last_HL,
                    HV_prev=last_HV,
                    Zfac_prev=last_Zfac,
                    reb_T_prev=last_reb_T,
                    reb_x_prev=last_reb_x,
                    reb_y_prev=last_reb_y,
                    reb_beta_prev=last_reb_beta,
                )
            else:
                # Skip thermo calls on intermediate steps
                inputs = ColumnInputs(
                    boundary=step_boundary,
                    volume_model=base_inputs.volume_model,
                    thermo=None,
                    thermo_provider=None,
                    compute_thermo_diag=False,
                    equilibrium_relaxation=base_inputs.equilibrium_relaxation,
                    equilibrium_relaxation_mode=base_inputs.equilibrium_relaxation_mode,
                    tau_eq_sec=base_inputs.tau_eq_sec,
                    condenser_duty_mode=str(step_condenser_duty_mode),
                    condenser_duty_btu_per_h=(
                        float(step_condenser_duty_btu_per_h)
                        if step_condenser_duty_btu_per_h is not None
                        else None
                    ),
                    condenser_duty_trim_btu_per_h=(
                        float(step_condenser_duty_trim_btu_per_h)
                        if step_condenser_duty_trim_btu_per_h is not None
                        else None
                    ),
                    reboiler_mode=str(step_reboiler_mode),
                    reboiler_duty_btu_per_h=(
                        float(step_reboiler_duty_btu_per_h)
                        if step_reboiler_duty_btu_per_h is not None
                        else None
                    ),
                    reboiler_duty_trim_btu_per_h=(
                        float(step_reboiler_duty_trim_btu_per_h)
                        if step_reboiler_duty_trim_btu_per_h is not None
                        else None
                    ),
                    pressure_model=str(pressure_model_step),
                    pressure_top_anchor_psia=(
                        float(step_pressure_top_anchor_psia)
                        if step_pressure_top_anchor_psia is not None
                        else None
                    ),
                    condenser_pressure_drop_psi=base_inputs.condenser_pressure_drop_psi,
                    top_drum_vapor_volume_ft3=base_inputs.top_drum_vapor_volume_ft3,
                    top_drum_total_volume_ft3=base_inputs.top_drum_total_volume_ft3,
                    enforce_top_drum_pressure_gate=base_inputs.enforce_top_drum_pressure_gate,
                    top_drum_pressure_gate_soft_psi=base_inputs.top_drum_pressure_gate_soft_psi,
                    enforce_top_pressure_ordering=base_inputs.enforce_top_pressure_ordering,
                    top_pressure_ordering_margin_psi=base_inputs.top_pressure_ordering_margin_psi,
                    enable_top_drum_psv=base_inputs.enable_top_drum_psv,
                    top_drum_psv_setpoint_psia=base_inputs.top_drum_psv_setpoint_psia,
                    top_drum_psv_gain_lbmolps_per_psi=base_inputs.top_drum_psv_gain_lbmolps_per_psi,
                    top_drum_psv_max_vent_lbmolps=base_inputs.top_drum_psv_max_vent_lbmolps,
                    # Do not run energy-based V closure without live thermo refresh.
                    # Pressure-conductance closure does not require fresh thermo.
                    vapor_flow_model=(
                        "profile"
                        if str(vapor_flow_model_step).strip().lower() == "energy"
                        else str(vapor_flow_model_step)
                    ),
                    dry_tray_K=base_inputs.dry_tray_K,
                    vapor_holdup_relaxation_sec=base_inputs.vapor_holdup_relaxation_sec,
                    hydraulic_pressure_relaxation_sec=base_inputs.hydraulic_pressure_relaxation_sec,
                    top_drum_pressure_temperature_relaxation_sec=(
                        base_inputs.top_drum_pressure_temperature_relaxation_sec
                    ),
                    top_drum_pressure_T_prev_F=last_top_drum_pressure_T,
                    vapor_flow_relaxation_sec=base_inputs.vapor_flow_relaxation_sec,
                    conductance_vflow_nominal_hi_ratio=(
                        base_inputs.conductance_vflow_nominal_hi_ratio
                    ),
                    reboiler_neighbor_vflow_hi_ratio=base_inputs.reboiler_neighbor_vflow_hi_ratio,
                    reboiler_neighbor_vflow_lo_ratio=base_inputs.reboiler_neighbor_vflow_lo_ratio,
                    thermo_refresh_dT_F=base_inputs.thermo_refresh_dT_F,
                    thermo_refresh_dP_psia=base_inputs.thermo_refresh_dP_psia,
                    thermo_refresh_dx=base_inputs.thermo_refresh_dx,
                    enable_liquid_hydraulic_override=base_inputs.enable_liquid_hydraulic_override,
                    liquid_hydraulic_override_alpha=float(seq_liquid_alpha_state),
                    component_mw_lbm_per_lbmol=base_inputs.component_mw_lbm_per_lbmol,
                    P_tray_prev=last_P_hyd if last_P_hyd is not None else last_P_diag,
                    V_out_prev_lbmolph=last_V_out,
                    dT_tray_target_F_per_s=last_dT_tray,
                    T_tray_prev_F=last_T_tray,
                    Z_overall_prev=last_z_overall,
                    rhoL_tray_lbmol_ft3=last_rhoL,
                    K_tray_prev=last_K_tray,
                    HL_prev=last_HL,
                    HV_prev=last_HV,
                    Zfac_prev=last_Zfac,
                    reb_T_prev=last_reb_T,
                    reb_x_prev=last_reb_x,
                    reb_y_prev=last_reb_y,
                    reb_beta_prev=last_reb_beta,
                )

            dae_pilot_enabled = bool(dae_pilot_enabled_eff)
            pressure_model_eval = str(getattr(inputs, "pressure_model", "")).strip().lower()
            vapor_model_eval = str(getattr(inputs, "vapor_flow_model", "")).strip().lower()
            dae_pilot_active = bool(
                dae_pilot_enabled
                and pressure_model_eval == "hydraulic"
                and vapor_model_eval in ("energy", "conductance")
            )
            inputs_rhs = inputs
            if str(integrator_mode).strip().lower() != "explicit-euler":
                smooth_cfg_lbmolph = getattr(cfg, "stiff_vflow_smooth_clamp_lbmolph", None)
                smooth_eps_lbmolps = 0.0
                if smooth_cfg_lbmolph is None:
                    if pressure_model_eval == "hydraulic" and vapor_model_eval in ("energy", "conductance"):
                        # Small smoothing width to remove hard derivative kinks
                        # at vapor-flow clamps for stiff substep Jacobians.
                        smooth_eps_lbmolps = 5.0 / 3600.0
                else:
                    try:
                        smooth_try_lbmolph = float(smooth_cfg_lbmolph)
                    except Exception:
                        smooth_try_lbmolph = 0.0
                    if np.isfinite(smooth_try_lbmolph) and smooth_try_lbmolph > 0.0:
                        smooth_eps_lbmolps = float(smooth_try_lbmolph) / 3600.0
                if smooth_eps_lbmolps > 0.0:
                    try:
                        inputs_rhs = replace(
                            inputs_rhs,
                            vflow_smooth_clamp_epsilon_lbmolps=float(smooth_eps_lbmolps),
                        )
                    except Exception:
                        pass
            pv_inner_iters = int(getattr(cfg, "pv_inner_max_iter", 1))
            if pressure_model_eval != "hydraulic":
                pv_inner_iters = 1
            if vapor_model_eval not in ("energy", "conductance"):
                pv_inner_iters = 1
            dae_outer_once_for_stiff = bool(
                dae_pilot_active and str(integrator_mode).strip().lower() in ("bdf", "radau")
            )

            def _eval_pv_rhs(
                t_eval_s: float,
                y_eval: np.ndarray,
                eval_inputs: ColumnInputs,
            ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
                dydt_eval, diag_eval = _column_rhs_with_inner_pv_coupling(
                    t_s=float(t_eval_s),
                    y=np.asarray(y_eval, dtype=float),
                    col=col,
                    layout=layout,
                    inputs=eval_inputs,
                    max_iter=int(pv_inner_iters),
                    p_tol_psia=getattr(cfg, "pv_inner_p_tol_psia", None),
                    v_tol_lbmolph=getattr(cfg, "pv_inner_v_tol_lbmolph", None),
                )
                return np.asarray(dydt_eval, dtype=float).reshape((-1,)), dict(diag_eval)

            if dae_outer_once_for_stiff:
                # Run full DAE algebraic Newton once per outer step for diagnostics
                # and for a better initial algebraic seed.
                dydt, diag = _solve_dae_pilot_algebraic(
                    t_s=float(t_s),
                    y=np.asarray(y, dtype=float),
                    col=col,
                    layout=layout,
                    inputs=inputs_rhs,
                    max_iter=int(dae_pilot_max_iter_eff),
                    p_tol_psia=dae_pilot_p_tol_eff,
                    v_tol_lbmolph=dae_pilot_v_tol_eff,
                    jac_rel_step=float(getattr(cfg, "dae_pilot_jac_rel_step", 1.0e-6)),
                    line_search_max=int(getattr(cfg, "dae_pilot_line_search_max", 4)),
                )
                diag["dae_pilot_stiff_outer_only"] = np.array([1.0], dtype=float)

                # Feed solved algebraic quantities into stiff substeps.
                try:
                    rhs_updates: Dict[str, Any] = {}
                    p_seed = _diag_stage_vector(diag, "P_psia_hyd", col.n_stages, positive_only=True)
                    if p_seed is None:
                        p_seed = _diag_stage_vector(diag, "P_psia_diag", col.n_stages, positive_only=True)
                    if p_seed is not None:
                        rhs_updates["P_tray_prev"] = np.asarray(p_seed, dtype=float).copy()
                    v_seed = _diag_stage_vector(diag, "V_out_lbmolph", col.n_stages, positive_only=False)
                    if v_seed is not None:
                        rhs_updates["V_out_prev_lbmolph"] = np.asarray(v_seed, dtype=float).copy()
                    z_seed = _diag_stage_vector(diag, "Z_tray", col.n_stages, positive_only=True)
                    if z_seed is not None:
                        rhs_updates["Zfac_prev"] = np.asarray(z_seed, dtype=float).copy()
                    if "T_top_drum_pressure_used_F" in diag:
                        try:
                            t_top_used = float(np.asarray(diag["T_top_drum_pressure_used_F"], dtype=float).reshape((-1,))[0])
                            if np.isfinite(t_top_used):
                                rhs_updates["top_drum_pressure_T_prev_F"] = float(t_top_used)
                        except Exception:
                            pass
                    if rhs_updates:
                        inputs_rhs = replace(inputs_rhs, **rhs_updates)
                except Exception:
                    pass

                if do_thermo:
                    try:
                        # Avoid repeated thermo flashes during implicit substeps.
                        inputs_rhs = replace(
                            inputs_rhs,
                            thermo=None,
                            thermo_provider=None,
                            compute_thermo_diag=False,
                            equilibrium_relaxation=False,
                        )
                    except Exception:
                        pass

                def _eval_step_rhs(t_eval_s: float, y_eval: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
                    dydt_eval, diag_eval = column_rhs(
                        float(t_eval_s),
                        np.asarray(y_eval, dtype=float),
                        col,
                        layout,
                        inputs=inputs_rhs,
                    )
                    dydt_eval = np.asarray(dydt_eval, dtype=float).reshape((-1,))
                    diag_eval = dict(diag_eval)
                    diag_eval["dae_pilot_enabled"] = np.array([1.0], dtype=float)
                    diag_eval["dae_pilot_iter_count"] = np.array([0.0], dtype=float)
                    diag_eval["dae_pilot_converged"] = np.array([0.0], dtype=float)
                    diag_eval["dae_pilot_failed"] = np.array([0.0], dtype=float)
                    diag_eval["dae_pilot_stiff_outer_only"] = np.array([1.0], dtype=float)
                    return dydt_eval, diag_eval
            else:
                def _eval_step_rhs(t_eval_s: float, y_eval: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
                    if dae_pilot_active:
                        dydt_eval, diag_eval = _solve_dae_pilot_algebraic(
                            t_s=float(t_eval_s),
                            y=np.asarray(y_eval, dtype=float),
                            col=col,
                            layout=layout,
                            inputs=inputs_rhs,
                            max_iter=int(dae_pilot_max_iter_eff),
                            p_tol_psia=dae_pilot_p_tol_eff,
                            v_tol_lbmolph=dae_pilot_v_tol_eff,
                            jac_rel_step=float(getattr(cfg, "dae_pilot_jac_rel_step", 1.0e-6)),
                            line_search_max=int(getattr(cfg, "dae_pilot_line_search_max", 4)),
                        )
                        return np.asarray(dydt_eval, dtype=float).reshape((-1,)), dict(diag_eval)

                    dydt_eval, diag_eval = _eval_pv_rhs(float(t_eval_s), np.asarray(y_eval, dtype=float), inputs_rhs)
                    if dae_pilot_enabled:
                        diag_eval["dae_pilot_enabled"] = np.array([1.0], dtype=float)
                        diag_eval["dae_pilot_iter_count"] = np.array([0.0], dtype=float)
                        diag_eval["dae_pilot_converged"] = np.array([0.0], dtype=float)
                        diag_eval["dae_pilot_failed"] = np.array([0.0], dtype=float)
                    return dydt_eval, diag_eval

                dydt, diag = _eval_step_rhs(float(t_s), y)
                if integrator_mode != "explicit-euler" and do_thermo:
                    try:
                        # Freeze thermo flashes during implicit substeps so a stiff step
                        # does not repeatedly invoke full tray flashes.
                        inputs_rhs = replace(
                            inputs_rhs,
                            thermo=None,
                            thermo_provider=None,
                            compute_thermo_diag=False,
                            equilibrium_relaxation=False,
                        )
                    except Exception:
                        pass
            if (
                step_condenser_duty_cmd_btu_per_h is not None
                and np.isfinite(float(step_condenser_duty_cmd_btu_per_h))
            ):
                diag["Q_cond_cmd_BTUph"] = np.array([float(step_condenser_duty_cmd_btu_per_h)], dtype=float)
            elif step_condenser_duty_btu_per_h is not None and np.isfinite(float(step_condenser_duty_btu_per_h)):
                diag["Q_cond_cmd_BTUph"] = np.array([float(step_condenser_duty_btu_per_h)], dtype=float)
            if step_pressure_ctrl_pv_raw_psia is not None and np.isfinite(float(step_pressure_ctrl_pv_raw_psia)):
                diag["P_top_ctrl_pv_raw_psia"] = np.array([float(step_pressure_ctrl_pv_raw_psia)], dtype=float)
            if step_pressure_ctrl_pv_filt_psia is not None and np.isfinite(float(step_pressure_ctrl_pv_filt_psia)):
                diag["P_top_ctrl_pv_filt_psia"] = np.array([float(step_pressure_ctrl_pv_filt_psia)], dtype=float)
            if step_pressure_ctrl_gain_scale is not None and np.isfinite(float(step_pressure_ctrl_gain_scale)):
                diag["P_top_ctrl_gain_scale"] = np.array([float(step_pressure_ctrl_gain_scale)], dtype=float)
            if (
                step_pressure_ctrl_energy_resid_abs_btups is not None
                and np.isfinite(float(step_pressure_ctrl_energy_resid_abs_btups))
            ):
                diag["P_top_ctrl_energy_resid_abs_BTUps"] = np.array(
                    [float(step_pressure_ctrl_energy_resid_abs_btups)],
                    dtype=float,
                )
            if (
                step_pressure_top_anchor_cmd_psia is not None
                and np.isfinite(float(step_pressure_top_anchor_cmd_psia))
            ):
                diag["P_top_anchor_cmd_psia"] = np.array([float(step_pressure_top_anchor_cmd_psia)], dtype=float)
            if step_distillate_comp_sp is not None and np.isfinite(float(step_distillate_comp_sp)):
                diag["xD_comp_sp"] = np.array([float(step_distillate_comp_sp)], dtype=float)
            if step_distillate_comp_pv is not None and np.isfinite(float(step_distillate_comp_pv)):
                diag["xD_comp_pv"] = np.array([float(step_distillate_comp_pv)], dtype=float)
            if step_reflux_ratio_cmd is not None and np.isfinite(float(step_reflux_ratio_cmd)):
                diag["RR_comp_cmd"] = np.array([float(step_reflux_ratio_cmd)], dtype=float)
            if step_reflux_cmd_lbmolph is not None and np.isfinite(float(step_reflux_cmd_lbmolph)):
                diag["Reflux_cmd_lbmolph"] = np.array([float(step_reflux_cmd_lbmolph)], dtype=float)
            if step_bottoms_comp_sp is not None and np.isfinite(float(step_bottoms_comp_sp)):
                diag["xB_comp_sp"] = np.array([float(step_bottoms_comp_sp)], dtype=float)
            if step_bottoms_comp_pv is not None and np.isfinite(float(step_bottoms_comp_pv)):
                diag["xB_comp_pv"] = np.array([float(step_bottoms_comp_pv)], dtype=float)
            if step_boilup_cmd_lbmolph is not None and np.isfinite(float(step_boilup_cmd_lbmolph)):
                diag["Boilup_cmd_lbmolph"] = np.array([float(step_boilup_cmd_lbmolph)], dtype=float)
            if (
                step_reboiler_duty_cmd_btu_per_h is not None
                and np.isfinite(float(step_reboiler_duty_cmd_btu_per_h))
            ):
                diag["Q_reb_cmd_BTUph"] = np.array([float(step_reboiler_duty_cmd_btu_per_h)], dtype=float)
            seq_phase_id = {
                "base": 0.0,
                "pressure_only": 1.0,
                "pressure_energy": 2.0,
                "pressure_energy_liquid_ramp": 3.0,
            }.get(str(seq_phase), 0.0)
            diag["startup_sequence_enabled"] = np.array(
                [1.0 if bool(startup_sequence_enabled) else 0.0],
                dtype=float,
            )
            diag["startup_sequence_phase_id"] = np.array([float(seq_phase_id)], dtype=float)
            diag["startup_sequence_pressure_hydraulic"] = np.array(
                [1.0 if str(pressure_model_step).strip().lower() == "hydraulic" else 0.0],
                dtype=float,
            )
            diag["startup_sequence_vapor_energy"] = np.array(
                [1.0 if str(vapor_flow_model_step).strip().lower() == "energy" else 0.0],
                dtype=float,
            )
            diag["startup_sequence_liquid_alpha_cmd"] = np.array([float(seq_liquid_alpha_state)], dtype=float)
            gate_val = cfg.startup_sequence_mass_resid_gate_lbmolph
            diag["startup_sequence_mass_resid_gate_lbmolph"] = np.array(
                [
                    float(gate_val)
                    if gate_val is not None and np.isfinite(float(gate_val))
                    else np.nan
                ],
                dtype=float,
            )
            diag["startup_sequence_mass_resid_max_prev_lbmolph"] = np.array(
                [
                    float(last_mass_resid_max_lbmolph)
                    if last_mass_resid_max_lbmolph is not None and np.isfinite(float(last_mass_resid_max_lbmolph))
                    else np.nan
                ],
                dtype=float,
            )
            try:
                mr_now = np.asarray(diag.get("mass_balance_resid_lbmolps_tray"), dtype=float).reshape((-1,))
                if mr_now.size > 0 and np.any(np.isfinite(mr_now)):
                    last_mass_resid_max_lbmolph = float(np.nanmax(np.abs(mr_now)) * 3600.0)
                    diag["startup_sequence_mass_resid_max_now_lbmolph"] = np.array(
                        [float(last_mass_resid_max_lbmolph)],
                        dtype=float,
                    )
                else:
                    last_mass_resid_max_lbmolph = None
            except Exception:
                last_mass_resid_max_lbmolph = None

            # Global mass-closure diagnostics (diagnostic-only; no correction).
            try:
                m_total_lbmol = _total_inventory_lbmol(layout, y)
                dM_total_dt_lbmolps = _total_inventory_rate_lbmolps(layout, dydt)
                dM_total_dt_lbmolph = float(dM_total_dt_lbmolps) * 3600.0

                F_flow = float(feed_tag.flow_lbmolph) if feed_tag.flow_lbmolph is not None else np.nan
                D_flow = np.nan
                B_flow = np.nan
                if step_boundary.distillate_lbmolph is not None:
                    D_flow = float(step_boundary.distillate_lbmolph)
                elif step_dist_tag.flow_lbmolph is not None:
                    D_flow = float(step_dist_tag.flow_lbmolph)
                if step_boundary.bottoms_lbmolph is not None:
                    B_flow = float(step_boundary.bottoms_lbmolph)
                elif step_bots_tag.flow_lbmolph is not None:
                    B_flow = float(step_bots_tag.flow_lbmolph)

                net_in_minus_out_lbmolph = np.nan
                if np.isfinite(F_flow) and np.isfinite(D_flow) and np.isfinite(B_flow):
                    net_in_minus_out_lbmolph = float(F_flow - D_flow - B_flow)

                closure_error_lbmolph = np.nan
                if np.isfinite(dM_total_dt_lbmolph) and np.isfinite(net_in_minus_out_lbmolph):
                    closure_error_lbmolph = float(dM_total_dt_lbmolph - net_in_minus_out_lbmolph)
                    if step > 0 and np.isfinite(closure_error_lbmolph):
                        global_mass_closure_cum_lbmol += float(closure_error_lbmolph) * float(dt) / 3600.0

                stage_mass_resid_sum_lbmolps = np.nan
                if "mass_balance_resid_lbmolps_tray" in diag:
                    try:
                        mr = np.asarray(diag["mass_balance_resid_lbmolps_tray"], dtype=float).reshape((-1,))
                        if mr.size > 0:
                            stage_mass_resid_sum_lbmolps = float(np.nansum(mr))
                    except Exception:
                        stage_mass_resid_sum_lbmolps = np.nan

                diag["M_total_lbmol"] = np.array([float(m_total_lbmol)], dtype=float)
                diag["dM_total_dt_lbmolps"] = np.array([float(dM_total_dt_lbmolps)], dtype=float)
                diag["dM_total_dt_lbmolph"] = np.array([float(dM_total_dt_lbmolph)], dtype=float)
                diag["net_F_minus_D_minus_B_lbmolph"] = np.array([float(net_in_minus_out_lbmolph)], dtype=float)
                diag["global_mass_closure_error_lbmolph"] = np.array([float(closure_error_lbmolph)], dtype=float)
                diag["global_mass_closure_cum_lbmol"] = np.array([float(global_mass_closure_cum_lbmol)], dtype=float)
                diag["stage_mass_resid_sum_lbmolps"] = np.array([float(stage_mass_resid_sum_lbmolps)], dtype=float)
            except Exception:
                pass

            # Pressure-controller PV source.
            # For top-anchor MV, use tray-top hydraulic pressure as the primary PV
            # so the controller acts on the pressure state it actually manipulates.
            p_ctrl_idx = 0
            p_top_pv = None
            pressure_mv_mode = str(pressure_control_mv or "").strip().lower()
            if pressure_mv_mode == "top-anchor":
                if "P_psia_hyd" in diag:
                    try:
                        p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((col.n_stages,))
                        if np.isfinite(float(p_h[p_ctrl_idx])) and float(p_h[p_ctrl_idx]) > 0.0:
                            p_top_pv = float(p_h[p_ctrl_idx])
                    except Exception:
                        p_top_pv = None
                if p_top_pv is None and "P_psia_diag" in diag:
                    try:
                        p_d = np.asarray(diag["P_psia_diag"], dtype=float).reshape((col.n_stages,))
                        if np.isfinite(float(p_d[p_ctrl_idx])) and float(p_d[p_ctrl_idx]) > 0.0:
                            p_top_pv = float(p_d[p_ctrl_idx])
                    except Exception:
                        p_top_pv = None
                if p_top_pv is None and "P_top_drum_psia" in diag:
                    try:
                        p_top = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
                        if np.isfinite(p_top) and p_top > 0.0:
                            p_top_pv = float(p_top)
                    except Exception:
                        p_top_pv = None
            else:
                if "P_top_drum_psia" in diag:
                    try:
                        p_top = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
                        if np.isfinite(p_top) and p_top > 0.0:
                            p_top_pv = float(p_top)
                    except Exception:
                        p_top_pv = None
                if p_top_pv is None and "P_psia_hyd" in diag:
                    try:
                        p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((col.n_stages,))
                        if np.isfinite(float(p_h[p_ctrl_idx])) and float(p_h[p_ctrl_idx]) > 0.0:
                            p_top_pv = float(p_h[p_ctrl_idx])
                    except Exception:
                        p_top_pv = None
                if p_top_pv is None and "P_psia_diag" in diag:
                    try:
                        p_d = np.asarray(diag["P_psia_diag"], dtype=float).reshape((col.n_stages,))
                        if np.isfinite(float(p_d[p_ctrl_idx])) and float(p_d[p_ctrl_idx]) > 0.0:
                            p_top_pv = float(p_d[p_ctrl_idx])
                    except Exception:
                        p_top_pv = None
            if p_top_pv is not None:
                last_top_pressure_pv_psia = float(p_top_pv)
                diag["P_top_ctrl_pv_psia"] = np.array([float(p_top_pv)], dtype=float)
            if "T_top_drum_pressure_used_F" in diag:
                try:
                    t_top_p = float(np.asarray(diag["T_top_drum_pressure_used_F"], dtype=float).reshape((-1,))[0])
                    if np.isfinite(t_top_p):
                        last_top_drum_pressure_T = float(t_top_p)
                except Exception:
                    pass
            last_top_energy_resid_abs_btups = None
            if "energy_balance_resid_BTUps_tray" in diag:
                try:
                    er = np.asarray(diag["energy_balance_resid_BTUps_tray"], dtype=float).reshape((col.n_stages,))
                    if er.size > 0:
                        finite_idx = np.where(np.isfinite(er))[0]
                        if finite_idx.size > 0:
                            last_top_energy_resid_abs_btups = abs(float(er[int(finite_idx[0])]))
                except Exception:
                    last_top_energy_resid_abs_btups = None

            # Steady-state detector (diagnostic-only).
            if ss_enabled:
                max_rel_state_rate = np.nan
                dt_ss = np.nan
                if ss_prev_t_s is not None and ss_prev_y is not None:
                    try:
                        dt_ss = float(t_s) - float(ss_prev_t_s)
                    except Exception:
                        dt_ss = np.nan
                if np.isfinite(dt_ss) and float(dt_ss) > 0.0 and ss_prev_y is not None:
                    max_rel_state_rate = _max_rel_inventory_fd_rate_per_s(
                        layout,
                        ss_prev_y,
                        y,
                        dt_sec=float(dt_ss),
                        denom_floor_lbmol=float(ss_rate_floor_lbmol),
                    )
                # Startup fallback for very first sample when finite-difference rate is unavailable.
                if not np.isfinite(max_rel_state_rate):
                    max_rel_state_rate = _max_rel_inventory_rate_per_s(
                        layout,
                        y,
                        dydt,
                        denom_floor_lbmol=float(ss_rate_floor_lbmol),
                    )
                max_temp_rate = np.nan
                if np.isfinite(dt_ss) and float(dt_ss) > 0.0 and ss_prev_y is not None:
                    max_temp_rate = _max_abs_temperature_fd_rate_per_s(
                        layout,
                        ss_prev_y,
                        y,
                        dt_sec=float(dt_ss),
                    )
                # Startup fallback when FD estimate is unavailable.
                if not np.isfinite(max_temp_rate) and "dT_tray_F_per_s" in diag:
                    try:
                        dT_vec = np.asarray(diag["dT_tray_F_per_s"], dtype=float).reshape((-1,))
                        dT_f = np.abs(dT_vec[np.isfinite(dT_vec)])
                        if dT_f.size > 0:
                            max_temp_rate = float(np.max(dT_f))
                    except Exception:
                        max_temp_rate = np.nan

                u_now = layout.unpack(y)
                xD_now = np.nan
                if dist_comp_idx is not None and "top_L" in u_now:
                    try:
                        top_L = np.asarray(u_now["top_L"], dtype=float).reshape((-1,))
                        top_tot = float(np.sum(top_L))
                        if np.isfinite(top_tot) and top_tot > 1e-300:
                            xD_now = float(top_L[int(dist_comp_idx)] / top_tot)
                    except Exception:
                        xD_now = np.nan
                xB_now = np.nan
                if bot_comp_idx is not None and "bottom_L" in u_now:
                    try:
                        bot_L = np.asarray(u_now["bottom_L"], dtype=float).reshape((-1,))
                        bot_tot = float(np.sum(bot_L))
                        if np.isfinite(bot_tot) and bot_tot > 1e-300:
                            xB_now = float(bot_L[int(bot_comp_idx)] / bot_tot)
                    except Exception:
                        xB_now = np.nan

                p_top_now = np.nan
                if p_top_pv is not None and np.isfinite(float(p_top_pv)):
                    p_top_now = float(p_top_pv)
                elif "P_top_drum_psia" in diag:
                    p_top_now = _mapping_scalar(diag, "P_top_drum_psia")
                elif "P_psia_hyd" in diag:
                    try:
                        p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((col.n_stages,))
                        p_top_now = float(p_h[0])
                    except Exception:
                        p_top_now = np.nan

                reflux_now = np.nan
                if step_boundary.reflux_lbmolph is not None:
                    reflux_now = float(step_boundary.reflux_lbmolph)
                boilup_now = np.nan
                if step_boundary.boilup_lbmolph is not None:
                    boilup_now = float(step_boundary.boilup_lbmolph)

                ss_hist.append(
                    {
                        "t": float(t_s),
                        "xD": float(xD_now),
                        "xB": float(xB_now),
                        "P_top": float(p_top_now),
                        "reflux": float(reflux_now),
                        "boilup": float(boilup_now),
                    }
                )
                while ss_hist and (float(t_s) - float(ss_hist[0]["t"]) > float(ss_window_sec)):
                    ss_hist.popleft()

                hist_t = [float(h["t"]) for h in ss_hist]
                xD_slope = _linear_trend_slope_per_s(hist_t, [float(h["xD"]) for h in ss_hist])
                xB_slope = _linear_trend_slope_per_s(hist_t, [float(h["xB"]) for h in ss_hist])
                P_top_slope = _linear_trend_slope_per_s(hist_t, [float(h["P_top"]) for h in ss_hist])
                reflux_rate = _linear_trend_slope_per_s(hist_t, [float(h["reflux"]) for h in ss_hist])
                boilup_rate = _linear_trend_slope_per_s(hist_t, [float(h["boilup"]) for h in ss_hist])

                kpi_slopes = []
                for v in (xD_slope, xB_slope):
                    if np.isfinite(v):
                        kpi_slopes.append(abs(float(v)))
                max_kpi_slope = float(np.max(kpi_slopes)) if kpi_slopes else np.nan

                mv_rates = []
                for v in (reflux_rate, boilup_rate):
                    if np.isfinite(v):
                        mv_rates.append(abs(float(v)))
                max_mv_rate = float(np.max(mv_rates)) if mv_rates else np.nan

                sp_errs = []
                if np.isfinite(xD_now) and step_distillate_comp_sp is not None and np.isfinite(float(step_distillate_comp_sp)):
                    sp_errs.append(abs(float(xD_now) - float(step_distillate_comp_sp)))
                if np.isfinite(xB_now) and step_bottoms_comp_sp is not None and np.isfinite(float(step_bottoms_comp_sp)):
                    sp_errs.append(abs(float(xB_now) - float(step_bottoms_comp_sp)))
                max_sp_err = float(np.max(sp_errs)) if sp_errs else np.nan

                ss_active_criteria = 0
                ss_pass = True
                ss_ratios: List[float] = []

                def _apply_criterion(metric: float, tol: Optional[float], *, require_metric: bool = True) -> None:
                    nonlocal ss_active_criteria, ss_pass, ss_ratios
                    if tol is None:
                        return
                    if require_metric and (not np.isfinite(metric)):
                        ss_active_criteria += 1
                        ss_pass = False
                        return
                    if not np.isfinite(metric):
                        return
                    ss_active_criteria += 1
                    ss_ratios.append(float(metric) / float(tol))
                    if float(metric) > float(tol):
                        ss_pass = False

                _apply_criterion(float(max_rel_state_rate), ss_tol_rel, require_metric=True)
                _apply_criterion(float(max_temp_rate), ss_tol_temp, require_metric=True)
                _apply_criterion(float(max_kpi_slope), ss_tol_kpi, require_metric=False)
                _apply_criterion(float(max_mv_rate), ss_tol_mv, require_metric=False)
                if ss_require_sp:
                    _apply_criterion(float(max_sp_err), ss_tol_sp, require_metric=True)

                ss_score = float(np.max(ss_ratios)) if ss_ratios else np.nan
                if float(t_s) < float(ss_min_time_sec):
                    ss_flag = 0.0
                elif ss_active_criteria <= 0:
                    ss_flag = np.nan
                else:
                    ss_flag = 1.0 if ss_pass else 0.0

                diag["steady_state_enabled"] = np.array([1.0], dtype=float)
                diag["steady_state_flag"] = np.array([float(ss_flag)], dtype=float)
                diag["steady_state_score"] = np.array([float(ss_score)], dtype=float)
                diag["steady_state_active_criteria"] = np.array([float(ss_active_criteria)], dtype=float)
                diag["ss_max_rel_state_rate_per_s"] = np.array([float(max_rel_state_rate)], dtype=float)
                diag["ss_max_kpi_slope_per_s"] = np.array([float(max_kpi_slope)], dtype=float)
                diag["ss_max_mv_rate_per_s"] = np.array([float(max_mv_rate)], dtype=float)
                diag["ss_max_temp_rate_F_per_s"] = np.array([float(max_temp_rate)], dtype=float)
                diag["ss_max_sp_error"] = np.array([float(max_sp_err)], dtype=float)
                diag["ss_window_samples"] = np.array([float(len(ss_hist))], dtype=float)
                diag["ss_window_sec"] = np.array([float(ss_window_sec)], dtype=float)
                diag["ss_min_time_sec"] = np.array([float(ss_min_time_sec)], dtype=float)
                diag["ss_tol_rel_state_rate_per_s"] = np.array(
                    [float(ss_tol_rel) if ss_tol_rel is not None else np.nan],
                    dtype=float,
                )
                diag["ss_tol_kpi_slope_per_s"] = np.array(
                    [float(ss_tol_kpi) if ss_tol_kpi is not None else np.nan],
                    dtype=float,
                )
                diag["ss_tol_mv_rate_per_s"] = np.array(
                    [float(ss_tol_mv) if ss_tol_mv is not None else np.nan],
                    dtype=float,
                )
                diag["ss_tol_temp_rate_F_per_s"] = np.array(
                    [float(ss_tol_temp) if ss_tol_temp is not None else np.nan],
                    dtype=float,
                )
                diag["ss_tol_sp_error"] = np.array(
                    [float(ss_tol_sp) if ss_tol_sp is not None else np.nan],
                    dtype=float,
                )
                diag["ss_require_sp"] = np.array([1.0 if bool(ss_require_sp) else 0.0], dtype=float)
                diag["ss_xD_slope_per_s"] = np.array([float(xD_slope)], dtype=float)
                diag["ss_xB_slope_per_s"] = np.array([float(xB_slope)], dtype=float)
                diag["ss_P_top_slope_per_s"] = np.array([float(P_top_slope)], dtype=float)
                diag["ss_reflux_rate_per_s"] = np.array([float(reflux_rate)], dtype=float)
                diag["ss_boilup_rate_per_s"] = np.array([float(boilup_rate)], dtype=float)

                steady_state_status_last = {
                    "steady_state_flag": float(ss_flag),
                    "steady_state_score": float(ss_score),
                    "ss_max_rel_state_rate_per_s": float(max_rel_state_rate),
                    "ss_max_kpi_slope_per_s": float(max_kpi_slope),
                    "ss_max_mv_rate_per_s": float(max_mv_rate),
                    "ss_max_temp_rate_F_per_s": float(max_temp_rate),
                    "ss_max_sp_error": float(max_sp_err),
                }
                ss_prev_t_s = float(t_s)
                ss_prev_y = np.asarray(y, dtype=float).copy()
            else:
                diag["steady_state_enabled"] = np.array([0.0], dtype=float)
                diag["steady_state_flag"] = np.array([np.nan], dtype=float)
                diag["steady_state_score"] = np.array([np.nan], dtype=float)

            # Cache and carry forward thermo diagnostics so intermediate log rows don't show NaNs
            if do_thermo:
                if "Z_tray" in diag:
                    last_Z_tray = np.asarray(diag["Z_tray"], dtype=float).copy()
                if "y_eq_tray" in diag:
                    last_y_eq = np.asarray(diag["y_eq_tray"], dtype=float).copy()
                if "P_psia_diag" in diag:
                    last_P_diag = np.asarray(diag["P_psia_diag"], dtype=float).copy()
                if "P_psia_hyd" in diag:
                    try:
                        last_P_hyd = np.asarray(diag["P_psia_hyd"], dtype=float).copy()
                    except Exception:
                        pass
                if "V_out_lbmolph" in diag:
                    try:
                        last_V_out = np.asarray(diag["V_out_lbmolph"], dtype=float).copy()
                    except Exception:
                        pass
                if "dT_tray_F_per_s" in diag:
                    try:
                        last_dT_tray = np.asarray(diag["dT_tray_F_per_s"], dtype=float).copy()
                    except Exception:
                        pass
                if "rhoL_tray_lbmol_ft3" in diag:
                    last_rhoL = np.asarray(diag["rhoL_tray_lbmol_ft3"], dtype=float).copy()
                if "K_tray" in diag:
                    last_K_tray = np.asarray(diag["K_tray"], dtype=float).copy()
                if "HL_BTU_lbmol_tray" in diag:
                    last_HL = np.asarray(diag["HL_BTU_lbmol_tray"], dtype=float).copy()
                if "HV_BTU_lbmol_tray" in diag:
                    last_HV = np.asarray(diag["HV_BTU_lbmol_tray"], dtype=float).copy()
                if "Z_tray" in diag:
                    last_Zfac = np.asarray(diag["Z_tray"], dtype=float).copy()
                if "z_overall_tray" in diag:
                    try:
                        last_z_overall = np.asarray(diag["z_overall_tray"], dtype=float).copy()
                    except Exception:
                        pass
                if "reb_T_F" in diag:
                    try:
                        last_reb_T = float(np.asarray(diag["reb_T_F"]).reshape((-1,))[0])
                    except Exception:
                        pass
                if "reb_beta" in diag:
                    try:
                        last_reb_beta = float(np.asarray(diag["reb_beta"]).reshape((-1,))[0])
                    except Exception:
                        pass
                if "reb_x" in diag:
                    try:
                        last_reb_x = np.asarray(diag["reb_x"], dtype=float).reshape((col.n_components,)).copy()
                    except Exception:
                        pass
                if "reb_y" in diag:
                    try:
                        last_reb_y = np.asarray(diag["reb_y"], dtype=float).reshape((col.n_components,)).copy()
                    except Exception:
                        pass
                try:
                    last_T_tray = _tray_temperature_F(col, layout, y, include_temperature=bool(cfg.include_temperature)).copy()
                except Exception:
                    pass
                last_diag = diag
            else:
                if last_Z_tray is not None:
                    diag["Z_tray"] = last_Z_tray
                if last_y_eq is not None:
                    diag["y_eq_tray"] = last_y_eq
                if last_P_diag is not None:
                    diag["P_psia_diag"] = last_P_diag
                if last_P_hyd is not None:
                    diag["P_psia_hyd"] = last_P_hyd
                if last_rhoL is not None:
                    diag["rhoL_tray_lbmol_ft3"] = last_rhoL

            # Log / print at cadence
            if (step % log_every) == 0:
                wall_elapsed_s = time.perf_counter() - start_perf
                wall_clock_iso = _dt.datetime.now().isoformat(timespec="seconds")
                sim_per_wall = (t_s / wall_elapsed_s) if wall_elapsed_s > 1e-12 else float("inf")

                progress_msg = (
                    f"[Progress] step={step:6d}  sim_t={t_s:10.2f} s  wall={wall_elapsed_s:10.2f} s  "
                    f"sim/wall={sim_per_wall:8.3f}"
                )
                if ss_enabled:
                    ss_flag = _mapping_scalar(diag, "steady_state_flag")
                    ss_score = _mapping_scalar(diag, "steady_state_score")
                    ss_rel = _mapping_scalar(diag, "ss_max_rel_state_rate_per_s")
                    ss_kpi = _mapping_scalar(diag, "ss_max_kpi_slope_per_s")
                    ss_mv = _mapping_scalar(diag, "ss_max_mv_rate_per_s")
                    ss_sp = _mapping_scalar(diag, "ss_max_sp_error")
                    if np.isfinite(ss_flag):
                        ss_flag_txt = str(int(round(float(ss_flag))))
                    else:
                        ss_flag_txt = "?"
                    progress_msg += f"  SS={ss_flag_txt}"
                    if np.isfinite(ss_score):
                        progress_msg += f"  score={float(ss_score):.2f}"
                    if np.isfinite(ss_rel):
                        progress_msg += f"  rel={float(ss_rel):.3g}/s"
                    if np.isfinite(ss_kpi):
                        progress_msg += f"  kpi={float(ss_kpi):.3g}/s"
                    if np.isfinite(ss_mv):
                        progress_msg += f"  mv={float(ss_mv):.3g}/s"
                    if np.isfinite(ss_sp):
                        progress_msg += f"  sp={float(ss_sp):.3g}"

                print(progress_msg)

                if cfg.write_logs:
                    prow = _profile_rows(
                        t_s,
                        case,
                        col,
                        layout,
                        y,
                        diag,
                        include_temperature=cfg.include_temperature,
                        volume_model=base_inputs.volume_model,
                        wall_clock_iso=wall_clock_iso,
                        wall_elapsed_s=wall_elapsed_s,
                        feed_tag=feed_tag,
                        dist_tag=step_dist_tag,
                        bots_tag=step_bots_tag,
                    )
                    srow = _summary_row(
                        t_s,
                        case,
                        col,
                        layout,
                        y,
                        diag,
                        include_temperature=cfg.include_temperature,
                        volume_model=base_inputs.volume_model,
                        wall_clock_iso=wall_clock_iso,
                        wall_elapsed_s=wall_elapsed_s,
                        feed_tag=feed_tag,
                        dist_tag=step_dist_tag,
                        bots_tag=step_bots_tag,
                        integrator_info=last_step_integrator_info,
                    )

                    if not profile_header_written:
                        profile_writer = csv.DictWriter(profile_file, fieldnames=list(prow[0].keys()))
                        profile_writer.writeheader()
                        profile_header_written = True
                    for r in prow:
                        profile_writer.writerow(r)
                    if profile_file is not None:
                        profile_file.write("\n")

                    if not summary_header_written:
                        summary_writer = csv.DictWriter(summary_file, fieldnames=list(srow.keys()))
                        summary_writer.writeheader()
                        summary_header_written = True
                    summary_writer.writerow(srow)

            if step == int(cfg.n_steps):
                break

            y_before_step = np.asarray(y, dtype=float).copy()
            if str(integrator_mode).strip().lower() == "ida":
                y, step_integrator_info = _integrate_one_step_ida(
                    t_s=float(t_s),
                    y=y,
                    dt_sec=float(dt),
                    rhs_eval=_eval_step_rhs,
                    layout=layout,
                    thermo_provider=thermo_provider,
                    substep_sec=getattr(cfg, "integrator_substep_sec", None),
                    max_iter=int(ida_max_iter_eff),
                    relax=getattr(cfg, "ida_relax", None),
                    rtol=getattr(cfg, "integrator_rtol", None),
                    atol=getattr(cfg, "integrator_atol", None),
                    max_rhs_evals_per_step=getattr(cfg, "integrator_max_rhs_evals_per_step", None),
                    step_wall_limit_sec=getattr(cfg, "integrator_step_wall_limit_sec", None),
                    alg_p_tol_psia=dae_pilot_p_tol_eff,
                    alg_v_tol_lbmolph=dae_pilot_v_tol_eff,
                )
            else:
                y, step_integrator_info = _integrate_one_step(
                    t_s=float(t_s),
                    y=y,
                    dt_sec=float(dt),
                    rhs_eval=_eval_step_rhs,
                    layout=layout,
                    thermo_provider=thermo_provider,
                    integrator_mode=integrator_mode,
                    rtol=getattr(cfg, "integrator_rtol", None),
                    atol=getattr(cfg, "integrator_atol", None),
                    max_step_sec=getattr(cfg, "integrator_max_step_sec", None),
                    substep_sec=getattr(cfg, "integrator_substep_sec", None),
                    max_rhs_evals_per_step=getattr(cfg, "integrator_max_rhs_evals_per_step", None),
                    step_wall_limit_sec=getattr(cfg, "integrator_step_wall_limit_sec", None),
                )
            if bool(step_integrator_info.get("fallback_used", False)) and bool(dae_outer_once_for_stiff):
                # If stiff solve falls back, preserve DAE-outer-step consistency by
                # advancing with the outer DAE-consistent derivative.
                y = y_before_step + float(dt) * np.asarray(dydt, dtype=float).reshape((-1,))
                y = _clamp_nonnegative_holdups(y, layout)
                y = _clip_temperature_states_to_provider_bounds(y, layout, thermo_provider)
                step_integrator_info["fallback_reason"] = (
                    str(step_integrator_info.get("fallback_reason", "")).strip()
                    + " | advanced with outer DAE dydt"
                ).strip(" |")
            last_step_integrator_info = dict(step_integrator_info) if isinstance(step_integrator_info, dict) else {}
            if bool(step_integrator_info.get("fallback_used", False)):
                integrator_fallback_count += 1
                if integrator_fallback_count <= 3 or (integrator_fallback_count % 20) == 0:
                    msg = str(step_integrator_info.get("fallback_reason", "")).strip()
                    if not msg:
                        msg = "unknown reason"
                    print(
                        "[Warn] Integrator fallback "
                        f"({integrator_mode}->explicit-euler) at step={int(step)} "
                        f"t={float(t_s):.2f}s: {msg}"
                    )
            t_s += dt

    finally:
        if profile_file is not None:
            profile_file.close()
        if summary_file is not None:
            summary_file.close()

    if ss_enabled:
        ssf = float(steady_state_status_last.get("steady_state_flag", np.nan))
        verdict = "UNKNOWN"
        if np.isfinite(ssf):
            verdict = "PASS" if int(round(ssf)) == 1 else "FAIL"
        sscore = float(steady_state_status_last.get("steady_state_score", np.nan))
        srel = float(steady_state_status_last.get("ss_max_rel_state_rate_per_s", np.nan))
        skpi = float(steady_state_status_last.get("ss_max_kpi_slope_per_s", np.nan))
        smv = float(steady_state_status_last.get("ss_max_mv_rate_per_s", np.nan))
        ssp = float(steady_state_status_last.get("ss_max_sp_error", np.nan))
        stemp = float(steady_state_status_last.get("ss_max_temp_rate_F_per_s", np.nan))
        print(
            "[SteadyState] "
            f"{verdict}  score={sscore:.3g}  rel={srel:.3g}/s  "
            f"kpi={skpi:.3g}/s  mv={smv:.3g}/s  dT={stemp:.3g}F/s  sp={ssp:.3g}"
        )

    return {
        "excel_path": str(Path(cfg.excel_path).resolve()),
        "logs_dir": str(logs_dir),
        "runtime_mode": str(runtime_mode),
        "integrator_mode": str(integrator_mode),
        "effective_ida_max_iter": int(ida_max_iter_eff),
        "effective_dae_pilot_enabled": bool(dae_pilot_enabled_eff),
        "effective_dae_pilot_max_iter": int(dae_pilot_max_iter_eff),
        "effective_dae_pilot_p_tol_psia": (
            float(_as_float(dae_pilot_p_tol_eff))
            if _as_float(dae_pilot_p_tol_eff) is not None
            else np.nan
        ),
        "effective_dae_pilot_v_tol_lbmolph": (
            float(_as_float(dae_pilot_v_tol_eff))
            if _as_float(dae_pilot_v_tol_eff) is not None
            else np.nan
        ),
        "effective_hydraulic_ida_defaults_applied": list(ida_defaults_applied),
        "integrator_fallback_count": int(integrator_fallback_count),
        "profile_csv": str(profile_path) if cfg.write_logs else None,
        "summary_csv": str(summary_path) if cfg.write_logs else None,
        "validation": {
            "ok": bool(validation.ok),
            "errors": list(validation.errors),
            "warnings": list(validation.warnings),
        },
        "final_time_s": float(t_s),
        "final_state": y,
        "thermo_provider": thermo_provider,
        "layout": layout,
        "inputs": base_inputs,
        "column": col,
        "last_diag": last_diag,
        "steady_state_status_final": dict(steady_state_status_last),
        "startup_thermo_init_info": thermo_init_info,
        "startup_top_drum_init_info": top_drum_init_info,
    }


# -------------------------
# CLI
# -------------------------


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Dynamic distillation smoke-test runner")

    p.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    p.add_argument(
        "--runtime-mode",
        dest="runtime_mode",
        choices=["legacy", "parity", "calibration", "hydraulic"],
        default="parity",
        help=(
            "Runner behavior mode: "
            "parity=Pressure(spec)+Vapor(profile)+LiquidHydraulics(off), "
            "calibration=same closures as parity with explicit parity-check intent, "
            "hydraulic=Pressure(hydraulic)+Vapor(energy)+LiquidHydraulics(on), "
            "legacy=use existing spec-driven behavior."
        ),
    )

    # Backward-compatible steps flag + alias
    p.add_argument("--n-steps", dest="n_steps", type=int, default=600)
    p.add_argument("--steps", dest="n_steps", type=int, default=None)

    p.add_argument("--dt", dest="dt_sec", type=float, default=None)
    p.add_argument("--log-every", dest="log_every_n_steps", type=int, default=None)
    p.add_argument(
        "--integrator",
        dest="integrator",
        choices=["explicit-euler", "bdf", "radau", "ida"],
        default="explicit-euler",
        help=(
            "Time integrator mode. explicit-euler keeps legacy behavior. "
            "bdf/radau use SciPy solve_ivp stiff methods and fall back to explicit-euler "
            "if SciPy is unavailable or a step solve fails. "
            "ida uses an implicit fixed-point DAE pilot stepper."
        ),
    )
    p.add_argument(
        "--integrator-rtol",
        dest="integrator_rtol",
        type=float,
        default=1.0e-3,
        help="Relative tolerance for stiff integrators and IDA fixed-point scaling.",
    )
    p.add_argument(
        "--integrator-atol",
        dest="integrator_atol",
        type=float,
        default=1.0e-6,
        help="Absolute tolerance for stiff integrators and IDA fixed-point scaling.",
    )
    p.add_argument(
        "--integrator-max-step-sec",
        dest="integrator_max_step_sec",
        type=float,
        default=None,
        help="Optional max internal substep size (s) for stiff integrators.",
    )
    p.add_argument(
        "--integrator-substep-sec",
        dest="integrator_substep_sec",
        type=float,
        default=None,
        help=(
            "Split each outer dt into fixed stiff substeps of this size (s). "
            "Useful when stiff solvers struggle on the full outer step."
        ),
    )
    p.add_argument(
        "--integrator-max-rhs-evals-per-step",
        dest="integrator_max_rhs_evals_per_step",
        type=int,
        default=24,
        help=(
            "Maximum RHS evaluations allowed inside one stiff integrator step. "
            "If exceeded, that step falls back to explicit Euler."
        ),
    )
    p.add_argument(
        "--integrator-step-wall-limit-sec",
        dest="integrator_step_wall_limit_sec",
        type=float,
        default=15.0,
        help=(
            "Per-step wall-time cap for stiff integrators. "
            "If exceeded, that step falls back to explicit Euler."
        ),
    )
    p.add_argument(
        "--ida-max-iter",
        dest="ida_max_iter",
        type=int,
        default=8,
        help="Maximum fixed-point iterations per IDA substep.",
    )
    p.add_argument(
        "--ida-relax",
        dest="ida_relax",
        type=float,
        default=1.0,
        help="Relaxation factor (0,1] for IDA fixed-point updates.",
    )

    # Backward-compatible temperature/energy flags
    p.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    p.add_argument("--no-temp", dest="include_temperature", action="store_false")
    p.add_argument("--include-energy", dest="include_energy", action="store_true")
    p.add_argument("--energy", dest="include_energy", action="store_true")

    # Backward-compatible equilibrium flags
    p.add_argument("--no-equilibrium", dest="enable_equilibrium_relaxation", action="store_false")
    p.add_argument("--no-eq", dest="enable_equilibrium_relaxation", action="store_false")
    p.add_argument(
        "--equilibrium-relaxation-mode",
        "--eq-mode",
        dest="equilibrium_relaxation_mode",
        choices=["auto", "phase-holdup", "composition-only"],
        default="auto",
        help=(
            "Equilibrium-relaxation transfer target: "
            "phase-holdup=legacy flash phase split, "
            "composition-only=relax vapor composition at fixed MV."
        ),
    )

    p.add_argument(
        "--thermo",
        dest="thermo_mode",
        choices=["stub", "dwsim", "table", "table-pool"],
        default="stub",
    )

    # Thermo throttling
    p.add_argument("--thermo-every", dest="thermo_every_n_steps", type=int, default=1)
    p.add_argument("--thermo-refresh-dt", dest="thermo_refresh_dT_F", type=float, default=None)
    p.add_argument("--thermo-refresh-dp", dest="thermo_refresh_dP_psia", type=float, default=None)
    p.add_argument("--thermo-refresh-dx", dest="thermo_refresh_dx", type=float, default=None)
    p.add_argument("--thermo-table", dest="thermo_table_path", default=None)
    p.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=None)
    p.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    p.add_argument("--thermo-pool-timeout-sec", dest="thermo_pool_task_timeout_sec", type=float, default=None)
    p.add_argument("--reb-neighbor-vflow-hi-ratio", dest="reboiler_neighbor_vflow_hi_ratio", type=float, default=None)
    p.add_argument("--reb-neighbor-vflow-lo-ratio", dest="reboiler_neighbor_vflow_lo_ratio", type=float, default=None)
    p.add_argument("--use-excel-vapor-holdup", dest="use_excel_vapor_holdup", action="store_true")
    p.add_argument("--vapor-holdup-relaxation-sec", dest="vapor_holdup_relaxation_sec", type=float, default=None)
    p.add_argument(
        "--hydraulic-pressure-relaxation-sec",
        dest="hydraulic_pressure_relaxation_sec",
        type=float,
        default=None,
    )
    p.add_argument(
        "--top-drum-pressure-temperature-relaxation-sec",
        dest="top_drum_pressure_temperature_relaxation_sec",
        type=float,
        default=None,
    )
    p.add_argument("--vapor-flow-relaxation-sec", dest="vapor_flow_relaxation_sec", type=float, default=None)
    p.add_argument(
        "--conductance-vflow-nominal-hi-ratio",
        dest="conductance_vflow_nominal_hi_ratio",
        type=float,
        default=None,
        help=(
            "Conductance-mode clamp: max internal vapor outflow as ratio of "
            "nominal profile V (e.g., 1.5)."
        ),
    )
    p.add_argument(
        "--stiff-vflow-smooth-clamp-lbmolph",
        dest="stiff_vflow_smooth_clamp_lbmolph",
        type=float,
        default=None,
        help=(
            "Optional smooth-clamp width (lbmol/h) for hydraulic vapor-flow limits "
            "during stiff RHS evaluation. "
            "None uses an automatic small value in stiff hydraulic mode; <=0 disables."
        ),
    )
    p.add_argument(
        "--pv-inner-max-iter",
        dest="pv_inner_max_iter",
        type=int,
        default=1,
        help=(
            "Inner fixed-point iterations per timestep for pressure-vapor coupling "
            "(applied only when pressure=hydraulic and vapor-flow=energy/conductance)."
        ),
    )
    p.add_argument(
        "--pv-inner-p-tol-psia",
        dest="pv_inner_p_tol_psia",
        type=float,
        default=0.05,
        help="Convergence tolerance for inner pressure iteration (psia).",
    )
    p.add_argument(
        "--pv-inner-v-tol-lbmolph",
        dest="pv_inner_v_tol_lbmolph",
        type=float,
        default=25.0,
        help="Convergence tolerance for inner vapor-flow iteration (lbmol/h).",
    )
    p.add_argument(
        "--enable-dae-pilot-algebraic-solve",
        dest="enable_dae_pilot_algebraic_solve",
        action="store_true",
        help=(
            "Enable pilot algebraic Newton solve for z=[P_tray, V_out] per timestep "
            "when pressure=hydraulic and vapor-flow model is energy/conductance."
        ),
    )
    p.add_argument(
        "--dae-pilot-max-iter",
        dest="dae_pilot_max_iter",
        type=int,
        default=3,
        help="Maximum Newton iterations for pilot algebraic solve.",
    )
    p.add_argument(
        "--dae-pilot-p-tol-psia",
        dest="dae_pilot_p_tol_psia",
        type=float,
        default=0.05,
        help="Pressure algebraic residual tolerance (psia).",
    )
    p.add_argument(
        "--dae-pilot-v-tol-lbmolph",
        dest="dae_pilot_v_tol_lbmolph",
        type=float,
        default=25.0,
        help="Vapor-flow algebraic residual tolerance (lbmol/h).",
    )
    p.add_argument(
        "--dae-pilot-jac-rel-step",
        dest="dae_pilot_jac_rel_step",
        type=float,
        default=1.0e-6,
        help="Relative finite-difference step for pilot Jacobian.",
    )
    p.add_argument(
        "--dae-pilot-line-search-max",
        dest="dae_pilot_line_search_max",
        type=int,
        default=4,
        help="Maximum backtracking line-search trials per Newton update.",
    )
    p.add_argument(
        "--disable-startup-thermo-conditioning",
        dest="enable_startup_thermo_conditioning",
        action="store_false",
        help="Disable startup thermo-consistent state conditioning.",
    )
    p.add_argument(
        "--startup-thermo-conditioning-iters",
        dest="startup_thermo_conditioning_iters",
        type=int,
        default=2,
    )
    p.add_argument(
        "--startup-thermo-conditioning-relax",
        dest="startup_thermo_conditioning_relaxation",
        type=float,
        default=1.0,
    )
    p.add_argument(
        "--enable-liquid-hydraulic-override",
        dest="enable_liquid_hydraulic_override",
        action="store_true",
        help="Force-enable internal liquid hydraulic downflow override.",
    )
    p.add_argument(
        "--disable-liquid-hydraulic-override",
        dest="enable_liquid_hydraulic_override",
        action="store_false",
        help="Disable internal liquid hydraulic downflow override (profile-only internal L).",
    )
    p.set_defaults(enable_liquid_hydraulic_override=None)
    p.add_argument(
        "--liquid-hydraulic-override-alpha",
        dest="liquid_hydraulic_override_alpha",
        type=float,
        default=None,
        help="Blend for internal liquid hydraulics override: 0=profile, 1=full hydraulic.",
    )
    p.add_argument(
        "--enable-startup-hydraulic-sequence",
        dest="enable_startup_hydraulic_sequence",
        action="store_true",
        help=(
            "Startup sequence: pressure-only first, then energy vapor closure, "
            "then residual-gated liquid-hydraulic ramp."
        ),
    )
    p.add_argument(
        "--startup-sequence-energy-on-sec",
        dest="startup_sequence_energy_on_sec",
        type=float,
        default=30.0,
        help="Sequence time (s) to allow vapor_flow_model=energy.",
    )
    p.add_argument(
        "--startup-sequence-liquid-on-sec",
        dest="startup_sequence_liquid_on_sec",
        type=float,
        default=120.0,
        help="Sequence time (s) to begin liquid-hydraulic override ramp.",
    )
    p.add_argument(
        "--startup-sequence-liquid-ramp-sec",
        dest="startup_sequence_liquid_ramp_sec",
        type=float,
        default=180.0,
        help="Ramp timescale (s) for liquid-hydraulic override alpha.",
    )
    p.add_argument(
        "--startup-sequence-mass-resid-gate-lbmolph",
        dest="startup_sequence_mass_resid_gate_lbmolph",
        type=float,
        default=250.0,
        help="If max tray mass residual exceeds this, liquid-hydraulic alpha is paused/backed off.",
    )
    p.add_argument(
        "--startup-sequence-liquid-backoff-sec",
        dest="startup_sequence_liquid_backoff_sec",
        type=float,
        default=None,
        help="Optional backoff timescale (s) when residual-gate is exceeded.",
    )
    p.add_argument(
        "--disable-steady-state-detection",
        dest="enable_steady_state_detection",
        action="store_false",
        help="Disable runtime steady-state detector diagnostics.",
    )
    p.add_argument("--steady-state-window-sec", dest="steady_state_window_sec", type=float, default=30.0)
    p.add_argument("--steady-state-min-time-sec", dest="steady_state_min_time_sec", type=float, default=60.0)
    p.add_argument(
        "--steady-state-rel-rate-tol-per-s",
        dest="steady_state_rel_state_rate_tol_per_s",
        type=float,
        default=3.0e-3,
        help="Tolerance on max relative inventory rate |dM/dt|/(|M|+floor) [1/s].",
    )
    p.add_argument(
        "--steady-state-kpi-slope-tol-per-s",
        dest="steady_state_kpi_slope_tol_per_s",
        type=float,
        default=1.0e-4,
        help="Tolerance on KPI slope magnitude (distillate/bottoms composition) [1/s].",
    )
    p.add_argument(
        "--steady-state-mv-rate-tol-per-s",
        dest="steady_state_mv_rate_tol_per_s",
        type=float,
        default=20.0,
        help="Tolerance on manipulated-variable rate (reflux/boilup) [lbmol/h/s].",
    )
    p.add_argument(
        "--steady-state-temp-rate-tol-fps",
        dest="steady_state_temp_rate_tol_F_per_s",
        type=float,
        default=0.15,
        help="Tolerance on max tray temperature rate [F/s].",
    )
    p.add_argument(
        "--steady-state-sp-error-tol",
        dest="steady_state_sp_error_tol",
        type=float,
        default=0.02,
        help="Tolerance on max composition setpoint error (mole fraction).",
    )
    p.add_argument(
        "--steady-state-require-sp",
        dest="steady_state_require_sp",
        action="store_true",
        help="Require composition setpoint error criterion for SS=1.",
    )
    p.add_argument(
        "--steady-state-rate-denom-floor-lbmol",
        dest="steady_state_rate_denom_floor_lbmol",
        type=float,
        default=1.0,
        help="Denominator floor used in relative inventory-rate metric (lbmol).",
    )

    # Boundary overrides
    p.add_argument("--reflux", dest="reflux_lbmolph", type=float, default=None)
    p.add_argument("--boilup", dest="boilup_lbmolph", type=float, default=None)
    p.add_argument(
        "--condenser-duty-mode",
        dest="condenser_duty_mode",
        choices=["total-condense", "specified"],
        default="total-condense",
    )
    p.add_argument("--condenser-duty-btuph", dest="condenser_duty_btu_per_h", type=float, default=None)
    p.add_argument(
        "--condenser-duty-trim-btuph",
        dest="condenser_duty_trim_btu_per_h",
        type=float,
        default=None,
    )
    p.add_argument("--enable-level-control", dest="enable_level_control", action="store_true")
    p.add_argument("--top-level-sp", dest="top_level_sp_lbmol", type=float, default=None)
    p.add_argument("--bottom-level-sp", dest="bottom_level_sp_lbmol", type=float, default=None)
    p.add_argument("--top-level-kc", dest="top_level_kc", type=float, default=None)
    p.add_argument("--top-level-ti", dest="top_level_ti_sec", type=float, default=None)
    p.add_argument("--bottom-level-kc", dest="bottom_level_kc", type=float, default=None)
    p.add_argument("--bottom-level-ti", dest="bottom_level_ti_sec", type=float, default=None)
    p.add_argument("--enable-pressure-control", dest="enable_pressure_control", action="store_true")
    p.add_argument(
        "--pressure-control-mv",
        dest="pressure_control_mv",
        choices=["auto", "condenser-duty", "top-anchor"],
        default="auto",
    )
    p.add_argument(
        "--allow-coupled-pressure-duty",
        dest="allow_coupled_pressure_duty",
        action="store_true",
        help=(
            "Allow pressure-control-mv=condenser-duty to remain coupled with "
            "condenser-duty-mode=total-condense. Default behavior auto-switches to top-anchor."
        ),
    )
    p.add_argument("--top-pressure-sp", dest="top_pressure_sp_psia", type=float, default=None)
    p.add_argument("--top-pressure-kc", dest="top_pressure_kc", type=float, default=None)
    p.add_argument("--top-pressure-ti", dest="top_pressure_ti_sec", type=float, default=None)
    p.add_argument("--top-pressure-pv-filter-tau-sec", dest="top_pressure_pv_filter_tau_sec", type=float, default=None)
    p.add_argument("--top-pressure-mv-slew-limit-per-s", dest="top_pressure_mv_slew_limit_per_s", type=float, default=None)
    p.add_argument("--top-pressure-resid-ref-btups", dest="top_pressure_resid_ref_btups", type=float, default=None)
    p.add_argument("--top-pressure-resid-min-gain", dest="top_pressure_resid_min_gain", type=float, default=0.25)
    p.add_argument("--top-pressure-anchor-min", dest="top_pressure_anchor_min_psia", type=float, default=None)
    p.add_argument("--top-pressure-anchor-max", dest="top_pressure_anchor_max_psia", type=float, default=None)
    p.add_argument("--condenser-duty-min-btuph", dest="condenser_duty_min_btu_per_h", type=float, default=None)
    p.add_argument("--condenser-duty-max-btuph", dest="condenser_duty_max_btu_per_h", type=float, default=None)
    p.add_argument("--condenser-pressure-drop-psi", dest="condenser_pressure_drop_psi", type=float, default=None)
    p.add_argument("--top-drum-vapor-volume-ft3", dest="top_drum_vapor_volume_ft3", type=float, default=None)
    p.add_argument("--top-drum-total-volume-ft3", dest="top_drum_total_volume_ft3", type=float, default=None)
    p.add_argument(
        "--disable-top-drum-pressure-gate",
        dest="enforce_top_drum_pressure_gate",
        action="store_false",
        help="Disable pressure-direction gating on stage-2 to top-drum vapor slip.",
    )
    p.add_argument(
        "--top-drum-pressure-gate-soft-psi",
        dest="top_drum_pressure_gate_soft_psi",
        type=float,
        default=0.25,
        help="Soft transition width (psi) for top-drum pressure gate; <=0 gives hard gating.",
    )
    p.add_argument(
        "--disable-top-pressure-ordering",
        dest="enforce_top_pressure_ordering",
        action="store_false",
        help="Disable top-end pressure ordering enforcement (stage-1 pressure >= top-drum pressure).",
    )
    p.add_argument(
        "--top-pressure-ordering-margin-psi",
        dest="top_pressure_ordering_margin_psi",
        type=float,
        default=0.0,
        help="Minimum margin (psi) enforced for stage-1 pressure above top-drum pressure.",
    )
    p.add_argument("--enable-top-psv", dest="enable_top_psv", action="store_true")
    p.add_argument("--top-psv-sp", dest="top_psv_setpoint_psia", type=float, default=None)
    p.add_argument(
        "--top-psv-gain-lbmolps-psi",
        dest="top_psv_gain_lbmolps_per_psi",
        type=float,
        default=None,
    )
    p.add_argument("--top-psv-max-lbmolps", dest="top_psv_max_vent_lbmolps", type=float, default=None)
    p.add_argument("--enable-distillate-composition-control", dest="enable_distillate_composition_control", action="store_true")
    p.add_argument("--distillate-comp-component", dest="distillate_composition_component", default="C4")
    p.add_argument("--distillate-comp-sp", dest="distillate_composition_sp_molfrac", type=float, default=None)
    p.add_argument("--distillate-comp-kc", dest="distillate_composition_kc", type=float, default=None)
    p.add_argument("--distillate-comp-ti", dest="distillate_composition_ti_sec", type=float, default=None)
    p.add_argument("--reflux-cmd-min", dest="reflux_cmd_min_lbmolph", type=float, default=None)
    p.add_argument("--reflux-cmd-max", dest="reflux_cmd_max_lbmolph", type=float, default=None)
    p.add_argument(
        "--disable-reflux-feasibility-cap",
        dest="enable_reflux_feasibility_cap",
        action="store_false",
        help="Disable reflux max-feasibility cap in distillate composition control.",
    )
    p.add_argument("--enable-bottoms-composition-control", dest="enable_bottoms_composition_control", action="store_true")
    p.add_argument("--bottoms-comp-component", dest="bottoms_composition_component", default="C5")
    p.add_argument("--bottoms-comp-sp", dest="bottoms_composition_sp_molfrac", type=float, default=None)
    p.add_argument("--bottoms-comp-kc", dest="bottoms_composition_kc", type=float, default=None)
    p.add_argument("--bottoms-comp-ti", dest="bottoms_composition_ti_sec", type=float, default=None)
    p.add_argument(
        "--bottoms-comp-mv",
        dest="bottoms_composition_mv",
        choices=["boilup", "reboiler-duty"],
        default="boilup",
    )
    p.add_argument("--boilup-cmd-min", dest="boilup_cmd_min_lbmolph", type=float, default=None)
    p.add_argument("--boilup-cmd-max", dest="boilup_cmd_max_lbmolph", type=float, default=None)
    p.add_argument("--reboiler-duty-cmd-min-btuph", dest="reboiler_duty_cmd_min_btu_per_h", type=float, default=None)
    p.add_argument("--reboiler-duty-cmd-max-btuph", dest="reboiler_duty_cmd_max_btu_per_h", type=float, default=None)
    p.add_argument("--reboiler-duty-btuph", dest="reboiler_duty_btu_per_h", type=float, default=None)
    # Backward-compatible aliases. These are converted to flow clamps using
    # current distillate flow if reflux-cmd min/max are not provided.
    p.add_argument("--reflux-ratio-min", dest="reflux_ratio_min", type=float, default=None)
    p.add_argument("--reflux-ratio-max", dest="reflux_ratio_max", type=float, default=None)

    p.add_argument("--logs-dir", dest="logs_dir", default="logs")
    p.add_argument("--no-write-logs", dest="write_logs", action="store_false")
    p.add_argument("--no-logs", dest="write_logs", action="store_false")
    p.add_argument(
        "--allow-repeat-command",
        dest="allow_repeat_command",
        action="store_true",
        help=(
            "Allow running even when this exact CLI command already exists in "
            "docs/experiment_ledger.csv."
        ),
    )

    raw_argv: List[str] = list(argv) if argv is not None else list(sys.argv[1:])
    args = p.parse_args(raw_argv)

    if args.n_steps is None:
        args.n_steps = 600

    module_name = "dynamic_distillation.dynamic_run_scaffold_v1"
    project_root = Path(__file__).resolve().parents[2]
    ledger_csv = project_root / "docs" / "experiment_ledger.csv"
    candidate_cmd = compose_cli_command(module_name, raw_argv)
    candidate_identity = compose_cli_command_identity(module_name, raw_argv)
    cmd_matches = find_exact_command_matches(
        ledger_csv_path=ledger_csv,
        module_name=module_name,
        argv=raw_argv,
    )
    if cmd_matches and (not bool(args.allow_repeat_command)):
        n_ok = sum(1 for m in cmd_matches if str(m.status).lower() == "ok")
        n_not_ok = len(cmd_matches) - n_ok
        print("[Abort] Exact command already exists in experiment ledger.")
        print(f"Candidate: {candidate_cmd}")
        print(f"Identity:  {candidate_identity}")
        print(f"Matches: total={len(cmd_matches)}, ok={n_ok}, not_ok={n_not_ok}")
        print("Recent matching runs:")
        for m in cmd_matches[:8]:
            p_txt = m.P_top_pv_psia_final if m.P_top_pv_psia_final else "NA"
            xd_txt = m.xD_pv_final if m.xD_pv_final else "NA"
            xb_txt = m.xB_pv_final if m.xB_pv_final else "NA"
            print(
                f"  - run_id={m.run_id} status={m.status} t_final={m.t_final_s} "
                f"P_top={p_txt} xD={xd_txt} xB={xb_txt} src={m.command_source}"
            )
        print("Pass --allow-repeat-command to run this command again intentionally.")
        return 2
    if cmd_matches and bool(args.allow_repeat_command):
        print(f"[Warn] Repeating known command (matches={len(cmd_matches)}).")

    cfg = RunnerConfig(
        excel_path=str(args.excel_path),
        n_steps=int(args.n_steps),
        dt_sec=args.dt_sec,
        log_every_n_steps=args.log_every_n_steps,
        runtime_mode=str(args.runtime_mode),
        integrator=str(args.integrator),
        integrator_rtol=float(args.integrator_rtol),
        integrator_atol=float(args.integrator_atol),
        integrator_max_step_sec=args.integrator_max_step_sec,
        integrator_substep_sec=args.integrator_substep_sec,
        integrator_max_rhs_evals_per_step=args.integrator_max_rhs_evals_per_step,
        integrator_step_wall_limit_sec=args.integrator_step_wall_limit_sec,
        ida_max_iter=args.ida_max_iter,
        ida_relax=args.ida_relax,
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        enable_equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
        equilibrium_relaxation_mode=str(args.equilibrium_relaxation_mode),
        thermo_mode=str(args.thermo_mode),
        thermo_every_n_steps=int(args.thermo_every_n_steps),
        thermo_refresh_dT_F=args.thermo_refresh_dT_F,
        thermo_refresh_dP_psia=args.thermo_refresh_dP_psia,
        thermo_refresh_dx=args.thermo_refresh_dx,
        thermo_table_path=args.thermo_table_path,
        thermo_pool_workers=args.thermo_pool_workers,
        thermo_pool_chunk_size=args.thermo_pool_chunk_size,
        thermo_pool_task_timeout_sec=args.thermo_pool_task_timeout_sec,
        reboiler_neighbor_vflow_hi_ratio=args.reboiler_neighbor_vflow_hi_ratio,
        reboiler_neighbor_vflow_lo_ratio=args.reboiler_neighbor_vflow_lo_ratio,
        vapor_holdup_relaxation_sec=args.vapor_holdup_relaxation_sec,
        hydraulic_pressure_relaxation_sec=args.hydraulic_pressure_relaxation_sec,
        top_drum_pressure_temperature_relaxation_sec=args.top_drum_pressure_temperature_relaxation_sec,
        vapor_flow_relaxation_sec=args.vapor_flow_relaxation_sec,
        conductance_vflow_nominal_hi_ratio=args.conductance_vflow_nominal_hi_ratio,
        stiff_vflow_smooth_clamp_lbmolph=args.stiff_vflow_smooth_clamp_lbmolph,
        pv_inner_max_iter=int(args.pv_inner_max_iter),
        pv_inner_p_tol_psia=args.pv_inner_p_tol_psia,
        pv_inner_v_tol_lbmolph=args.pv_inner_v_tol_lbmolph,
        enable_dae_pilot_algebraic_solve=bool(args.enable_dae_pilot_algebraic_solve),
        dae_pilot_max_iter=int(args.dae_pilot_max_iter),
        dae_pilot_p_tol_psia=args.dae_pilot_p_tol_psia,
        dae_pilot_v_tol_lbmolph=args.dae_pilot_v_tol_lbmolph,
        dae_pilot_jac_rel_step=float(args.dae_pilot_jac_rel_step),
        dae_pilot_line_search_max=int(args.dae_pilot_line_search_max),
        enable_liquid_hydraulic_override=args.enable_liquid_hydraulic_override,
        liquid_hydraulic_override_alpha=args.liquid_hydraulic_override_alpha,
        reflux_lbmolph=args.reflux_lbmolph,
        boilup_lbmolph=args.boilup_lbmolph,
        condenser_duty_mode=str(args.condenser_duty_mode),
        condenser_duty_btu_per_h=args.condenser_duty_btu_per_h,
        condenser_duty_trim_btu_per_h=args.condenser_duty_trim_btu_per_h,
        enable_level_control=bool(args.enable_level_control),
        top_level_sp_lbmol=args.top_level_sp_lbmol,
        bottom_level_sp_lbmol=args.bottom_level_sp_lbmol,
        top_level_kc=args.top_level_kc,
        top_level_ti_sec=args.top_level_ti_sec,
        bottom_level_kc=args.bottom_level_kc,
        bottom_level_ti_sec=args.bottom_level_ti_sec,
        enable_pressure_control=bool(args.enable_pressure_control),
        pressure_control_mv=str(args.pressure_control_mv),
        allow_coupled_pressure_duty=bool(args.allow_coupled_pressure_duty),
        top_pressure_sp_psia=args.top_pressure_sp_psia,
        top_pressure_kc=args.top_pressure_kc,
        top_pressure_ti_sec=args.top_pressure_ti_sec,
        top_pressure_pv_filter_tau_sec=args.top_pressure_pv_filter_tau_sec,
        top_pressure_mv_slew_limit_per_s=args.top_pressure_mv_slew_limit_per_s,
        top_pressure_resid_ref_btups=args.top_pressure_resid_ref_btups,
        top_pressure_resid_min_gain=float(args.top_pressure_resid_min_gain),
        top_pressure_anchor_min_psia=args.top_pressure_anchor_min_psia,
        top_pressure_anchor_max_psia=args.top_pressure_anchor_max_psia,
        condenser_duty_min_btu_per_h=args.condenser_duty_min_btu_per_h,
        condenser_duty_max_btu_per_h=args.condenser_duty_max_btu_per_h,
        condenser_pressure_drop_psi=args.condenser_pressure_drop_psi,
        top_drum_vapor_volume_ft3=args.top_drum_vapor_volume_ft3,
        top_drum_total_volume_ft3=args.top_drum_total_volume_ft3,
        enforce_top_drum_pressure_gate=bool(args.enforce_top_drum_pressure_gate),
        top_drum_pressure_gate_soft_psi=args.top_drum_pressure_gate_soft_psi,
        enforce_top_pressure_ordering=bool(args.enforce_top_pressure_ordering),
        top_pressure_ordering_margin_psi=float(args.top_pressure_ordering_margin_psi),
        enable_top_psv=bool(args.enable_top_psv),
        top_psv_setpoint_psia=args.top_psv_setpoint_psia,
        top_psv_gain_lbmolps_per_psi=args.top_psv_gain_lbmolps_per_psi,
        top_psv_max_vent_lbmolps=args.top_psv_max_vent_lbmolps,
        enable_distillate_composition_control=bool(args.enable_distillate_composition_control),
        distillate_composition_component=str(args.distillate_composition_component),
        distillate_composition_sp_molfrac=args.distillate_composition_sp_molfrac,
        distillate_composition_kc=args.distillate_composition_kc,
        distillate_composition_ti_sec=args.distillate_composition_ti_sec,
        reflux_cmd_min_lbmolph=args.reflux_cmd_min_lbmolph,
        reflux_cmd_max_lbmolph=args.reflux_cmd_max_lbmolph,
        enable_reflux_feasibility_cap=bool(args.enable_reflux_feasibility_cap),
        reflux_ratio_min=args.reflux_ratio_min,
        reflux_ratio_max=args.reflux_ratio_max,
        enable_bottoms_composition_control=bool(args.enable_bottoms_composition_control),
        bottoms_composition_component=str(args.bottoms_composition_component),
        bottoms_composition_sp_molfrac=args.bottoms_composition_sp_molfrac,
        bottoms_composition_kc=args.bottoms_composition_kc,
        bottoms_composition_ti_sec=args.bottoms_composition_ti_sec,
        bottoms_composition_mv=str(args.bottoms_composition_mv),
        boilup_cmd_min_lbmolph=args.boilup_cmd_min_lbmolph,
        boilup_cmd_max_lbmolph=args.boilup_cmd_max_lbmolph,
        reboiler_duty_cmd_min_btu_per_h=args.reboiler_duty_cmd_min_btu_per_h,
        reboiler_duty_cmd_max_btu_per_h=args.reboiler_duty_cmd_max_btu_per_h,
        reboiler_duty_btu_per_h=args.reboiler_duty_btu_per_h,
        logs_dir=str(args.logs_dir),
        write_logs=bool(args.write_logs),
        use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
        enable_startup_thermo_conditioning=bool(args.enable_startup_thermo_conditioning),
        startup_thermo_conditioning_iters=int(args.startup_thermo_conditioning_iters),
        startup_thermo_conditioning_relaxation=float(args.startup_thermo_conditioning_relaxation),
        enable_startup_hydraulic_sequence=bool(args.enable_startup_hydraulic_sequence),
        startup_sequence_energy_on_sec=float(args.startup_sequence_energy_on_sec),
        startup_sequence_liquid_on_sec=float(args.startup_sequence_liquid_on_sec),
        startup_sequence_liquid_ramp_sec=float(args.startup_sequence_liquid_ramp_sec),
        startup_sequence_mass_resid_gate_lbmolph=args.startup_sequence_mass_resid_gate_lbmolph,
        startup_sequence_liquid_backoff_sec=args.startup_sequence_liquid_backoff_sec,
        enable_steady_state_detection=bool(args.enable_steady_state_detection),
        steady_state_window_sec=float(args.steady_state_window_sec),
        steady_state_min_time_sec=float(args.steady_state_min_time_sec),
        steady_state_rel_state_rate_tol_per_s=args.steady_state_rel_state_rate_tol_per_s,
        steady_state_kpi_slope_tol_per_s=args.steady_state_kpi_slope_tol_per_s,
        steady_state_mv_rate_tol_per_s=args.steady_state_mv_rate_tol_per_s,
        steady_state_temp_rate_tol_F_per_s=args.steady_state_temp_rate_tol_F_per_s,
        steady_state_sp_error_tol=args.steady_state_sp_error_tol,
        steady_state_require_sp=bool(args.steady_state_require_sp),
        steady_state_rate_denom_floor_lbmol=float(args.steady_state_rate_denom_floor_lbmol),
    )

    out = run_smoke_simulation(cfg)
    try:
        fallback_n = int(out.get("integrator_fallback_count", 0))
    except Exception:
        fallback_n = 0
    if fallback_n > 0:
        print(f"[Info] Integrator fallback count (to explicit-euler): {fallback_n}")

    # Auto-register exact CLI command and refresh experiment ledger after each
    # run that produces log files.
    if out.get("summary_csv"):
        try:
            append_run_registry_entry(
                logs_dir=Path(str(out.get("logs_dir", cfg.logs_dir))),
                module_name=module_name,
                argv=raw_argv,
                summary_csv_path=out.get("summary_csv"),
                profile_csv_path=out.get("profile_csv"),
            )
            rebuild_experiment_ledger(project_root=project_root)
        except Exception as exc:
            print(f"[Warn] Failed to update experiment ledger: {exc}")

    if out.get("profile_csv"):
        print(f"Wrote: {out['profile_csv']}")
    if out.get("summary_csv"):
        print(f"Wrote: {out['summary_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
