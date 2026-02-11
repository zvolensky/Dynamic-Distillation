"""dynamic_run_scaffold_v1.py

Created: 2026-01-11 (America/New_York)
Updated: 2026-01-13 (America/New_York)

Smoke-test runner for the dynamic distillation model.

Key features
------------
- Explicit Euler time integration (development scaffold only).
- Backward-compatible CLI:
    * --n-steps (original) and --steps (alias)
    * --no-temperature (original) and --no-temp (alias)
    * --include-energy (original) and --energy (alias)
    * --no-equilibrium (original) and --no-eq (alias)
    * --no-write-logs (original) and --no-logs (alias)
- Optional thermo throttling: --thermo-every N (1 = every step).
- Optional boundary overrides: --reflux, --boilup (lbmol/h).
- Terminal progress: simulation time and wall time.
- Log files include wall_clock_iso and wall_elapsed_s.
- Between thermo refreshes, carries forward last computed Z (and y_eq if present)
  so intermediate log rows do not show NaNs.
- Initializes tray vapor holdup MV from the specified pressure profile when
  possible (P = n Z R T / V), so the initial PV diagnostic pressure starts
  near the spec.

New in this update
------------------
- Adds CSV columns for feed/distillate/bottoms flow rates (lbmol/h):
    * Profile CSV: F_lbmolph, D_lbmolph, B_lbmolph (nonzero only on their stages)
    * Summary CSV: F_lbmolph, D_lbmolph, B_lbmolph (overall scalars)

Notes
-----
- ColumnSpec.P_psia is treated as the operating/spec pressure profile.
- P_psia_diag is a *diagnostic* PV pressure implied by the vapor holdup states.
- Model stage index 0 is the condenser; it may have MV=0.
  For reporting clarity, we pin P_psia_diag[0] to P_spec[0] if available.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import csv
import datetime as _dt
import time

import numpy as np

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


def _pi_update(controller: PIController, *, pv: float, sp: float, dt_sec: float) -> float:
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

    # Tentative unclamped output
    i_next = controller.integ + e * float(dt_sec) / max(float(controller.ti_sec), 1e-9)
    u_unclamped = float(controller.bias) + float(controller.kc) * (e + i_next)
    u = float(np.clip(u_unclamped, float(controller.out_min), float(controller.out_max)))

    # Anti-windup: accept integrator update only when output is unsaturated
    # or error would move output back toward unsaturated region.
    sat_hi = u_unclamped > float(controller.out_max) + 1e-12
    sat_lo = u_unclamped < float(controller.out_min) - 1e-12
    allow_int = (not sat_hi and not sat_lo) or (sat_hi and e < 0.0) or (sat_lo and e > 0.0)
    if allow_int:
        controller.integ = float(i_next)
        u = float(np.clip(float(controller.bias) + float(controller.kc) * (e + controller.integ), float(controller.out_min), float(controller.out_max)))
    return u


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

    include_temperature: bool = True
    include_energy: bool = False
    enable_equilibrium_relaxation: bool = True

    thermo_mode: str = "stub"  # 'stub', 'dwsim', or 'table'
    thermo_every_n_steps: int = 1  # 1=every step
    thermo_refresh_dT_F: Optional[float] = None
    thermo_refresh_dP_psia: Optional[float] = None
    thermo_refresh_dx: Optional[float] = None
    thermo_table_path: Optional[str] = None
    reboiler_neighbor_vflow_hi_ratio: Optional[float] = None
    reboiler_neighbor_vflow_lo_ratio: Optional[float] = None

    reflux_lbmolph: Optional[float] = None
    boilup_lbmolph: Optional[float] = None
    condenser_duty_mode: str = "total-condense"
    condenser_duty_btu_per_h: Optional[float] = None
    condenser_duty_trim_btu_per_h: Optional[float] = None
    enable_level_control: bool = False
    top_level_sp_lbmol: Optional[float] = None
    bottom_level_sp_lbmol: Optional[float] = None
    top_level_kc: Optional[float] = None
    top_level_ti_sec: Optional[float] = None
    bottom_level_kc: Optional[float] = None
    bottom_level_ti_sec: Optional[float] = None
    enable_pressure_control: bool = False
    pressure_control_mv: str = "auto"  # auto|condenser-duty|top-anchor
    top_pressure_sp_psia: Optional[float] = None
    top_pressure_kc: Optional[float] = None
    top_pressure_ti_sec: Optional[float] = None
    condenser_duty_min_btu_per_h: Optional[float] = None
    condenser_duty_max_btu_per_h: Optional[float] = None
    top_pressure_anchor_min_psia: Optional[float] = None
    top_pressure_anchor_max_psia: Optional[float] = None

    logs_dir: str = "logs"
    write_logs: bool = True
    thermo_cache_path: Optional[str] = None
    use_excel_vapor_holdup: bool = False


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
    elif thermo_mode == "stub":
        Nc = int(col.n_components)
        if Nc == 1:
            K = np.array([1.0], dtype=float)
        else:
            K = 2.0 ** (1.0 - np.arange(Nc, dtype=float) / float(Nc - 1))
        prov = StubThermoProvider(K=K, Z=1.0)
    else:
        raise ValueError(f"Unsupported thermo_mode: {thermo_mode!r} (use 'stub', 'dwsim', or 'table')")

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
    if vapor_flow_model not in ("profile", "energy"):
        vapor_flow_model = "profile"

    dry_tray_k = _spec_float(specs, "Dry Tray K")
    if dry_tray_k is None or not np.isfinite(dry_tray_k):
        dry_tray_k = 1.0

    tau_v = _spec_float(specs, "Vapor Holdup Relaxation (sec)")
    if tau_v is None:
        tau_v = _spec_float(specs, "Stage time constant [tau] (sec)")
    if tau_v is not None and (not np.isfinite(tau_v) or tau_v <= 0.0):
        tau_v = None

    tau_vflow = _spec_float(specs, "Vapor Flow Relaxation (sec)")
    if tau_vflow is not None and (not np.isfinite(tau_vflow) or tau_vflow <= 0.0):
        tau_vflow = None

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
        tau_eq_sec=getattr(col, "tau_eq_sec", None),
        pressure_model=str(pressure_model),
        pressure_top_anchor_psia=None,
        vapor_flow_model=str(vapor_flow_model),
        dry_tray_K=float(dry_tray_k),
        vapor_holdup_relaxation_sec=(float(tau_v) if tau_v is not None else None),
        vapor_flow_relaxation_sec=(float(tau_vflow) if tau_vflow is not None else None),
        reboiler_neighbor_vflow_hi_ratio=(float(reb_nbr_hi) if reb_nbr_hi is not None else 1.02),
        reboiler_neighbor_vflow_lo_ratio=(float(reb_nbr_lo) if reb_nbr_lo is not None else 0.98),
        thermo_refresh_dT_F=(float(thermo_refresh_dT) if thermo_refresh_dT is not None else None),
        thermo_refresh_dP_psia=(float(thermo_refresh_dP) if thermo_refresh_dP is not None else None),
        thermo_refresh_dx=(float(thermo_refresh_dX) if thermo_refresh_dX is not None else None),
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
    return y_new


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
) -> Tuple[bool, Optional[PIController], Optional[float], str]:
    specs = getattr(col, "specs_raw", None) or {}
    enabled = bool(cfg.enable_pressure_control)
    if not enabled:
        b = _as_bool(_spec_get(specs, "Enable Pressure Control", "Pressure Control Enabled"))
        enabled = bool(b) if b is not None else False
    if not enabled:
        return False, None, None, "off"

    sp = cfg.top_pressure_sp_psia
    if sp is None:
        sp = _spec_float(specs, "Top Pressure SP (psia)", "Condenser Pressure SP (psia)")
    if sp is None:
        try:
            p_ctrl_idx = 1 if int(getattr(col, "n_stages", 1)) > 1 else 0
            sp = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[p_ctrl_idx])
        except Exception:
            sp = None
    if sp is None or (not np.isfinite(float(sp))) or float(sp) <= 0.0:
        return False, None, None, "off"

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
        return True, ctrl, float(sp), mv_mode

    # top-anchor pressure control mode
    p_ctrl_idx = 1 if int(getattr(col, "n_stages", 1)) > 1 else 0
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
    return True, ctrl, float(sp), mv_mode


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
    reflux_ratio = None
    if "L_out_lbmolph" in diag and dist_tag.flow_lbmolph is not None:
        try:
            L_out_lbmolph = np.asarray(diag["L_out_lbmolph"], dtype=float).reshape((N,))
            D_flow = float(dist_tag.flow_lbmolph)
            if np.isfinite(D_flow) and D_flow > 0.0 and np.isfinite(L_out_lbmolph[0]):
                reflux_ratio = float(L_out_lbmolph[0]) / D_flow
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
    Q_cond_cmd_BTUph = np.nan
    if "Q_cond_cmd_BTUph" in diag:
        try:
            Q_cond_cmd_BTUph = float(np.asarray(diag["Q_cond_cmd_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_cmd_BTUph = np.nan
    P_top_anchor_cmd_psia = np.nan
    if "P_top_anchor_cmd_psia" in diag:
        try:
            P_top_anchor_cmd_psia = float(np.asarray(diag["P_top_anchor_cmd_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_anchor_cmd_psia = np.nan
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
            "T_F": float(T[i]),
            "P_psia_hyd": float(P_hyd[i]) if P_hyd is not None and np.isfinite(P_hyd[i]) else np.nan,
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
            "Q_cond_cmd_BTUph": _stage_value(i1, 1, Q_cond_cmd_BTUph),
            "P_top_anchor_cmd_psia": _stage_value(i1, 1, P_top_anchor_cmd_psia),
            "T_sump_F": _stage_value(i1, N if layout.include_bottom else None, T_sump),
        }

        for k in range(Nc):
            label = comp_labels[k]
            r[f"x_{label}"] = float(x[i, k])
            r[f"y_{label}"] = float(yv[i, k])
            if top_x is not None:
                r[f"Distillate_x_{label}"] = _stage_value(i1, 1, float(top_x[k]))
            if bottom_x is not None:
                r[f"Bottoms_x_{label}"] = _stage_value(i1, N, float(bottom_x[k]))

        rows.append(r)

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
    Q_cond_cmd_BTUph = np.nan
    if "Q_cond_cmd_BTUph" in diag:
        try:
            Q_cond_cmd_BTUph = float(np.asarray(diag["Q_cond_cmd_BTUph"], dtype=float).reshape((-1,))[0])
        except Exception:
            Q_cond_cmd_BTUph = np.nan
    P_top_anchor_cmd_psia = np.nan
    if "P_top_anchor_cmd_psia" in diag:
        try:
            P_top_anchor_cmd_psia = float(np.asarray(diag["P_top_anchor_cmd_psia"], dtype=float).reshape((-1,))[0])
        except Exception:
            P_top_anchor_cmd_psia = np.nan

    if "P_psia_diag" in diag:
        P_diag = np.asarray(diag["P_psia_diag"], dtype=float).reshape((N,))
    else:
        P_diag = _pressure_diag_psia(col, volume_model, T, MV, Z)

    if N >= 1 and np.isfinite(P_spec[0]):
        P_diag[0] = float(P_spec[0])

    p_ctrl_idx = 1 if N > 1 else 0
    P_top_meas = float(P_diag[p_ctrl_idx])
    if "P_psia_hyd" in diag:
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
        "P_top_psia": float(P_spec[0]) if np.isfinite(P_spec[0]) else float(P_diag[0]),
        "P_top_psia_spec": float(P_spec[0]) if np.isfinite(P_spec[0]) else np.nan,
        "P_top_ctrl_pv_psia": float(P_top_meas),
        "P_bot_psia": float(P_spec[-1]) if np.isfinite(P_spec[-1]) else float(P_diag[-1]),
        "P_bot_psia_spec": float(P_spec[-1]) if np.isfinite(P_spec[-1]) else np.nan,
        "T_Distillate_F": float(T_distillate) if T_distillate is not None else np.nan,
        "Q_cond_calc_BTUph": float(Q_cond_calc_BTUph) if np.isfinite(Q_cond_calc_BTUph) else np.nan,
        "Q_cond_used_BTUph": float(Q_cond_used_BTUph) if np.isfinite(Q_cond_used_BTUph) else np.nan,
        "Q_cond_cmd_BTUph": float(Q_cond_cmd_BTUph) if np.isfinite(Q_cond_cmd_BTUph) else np.nan,
        "P_top_anchor_cmd_psia": float(P_top_anchor_cmd_psia) if np.isfinite(P_top_anchor_cmd_psia) else np.nan,
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

    cache = None
    if cfg.thermo_cache_path:
        try:
            from dynamic_distillation.thermo_cache_v1 import load_thermo_cache

            cache = load_thermo_cache(cfg.thermo_cache_path)
            _milestone(f"loaded thermo cache: {cfg.thermo_cache_path}")
        except Exception as exc:
            print(f"[Warn] Failed to load thermo cache: {exc}")
            cache = None

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

    cache_loaded = False
    if cache is not None:
        try:
            if int(cache.get("n_stages", col.n_stages)) != col.n_stages:
                raise ValueError("cache n_stages mismatch")
            if int(cache.get("n_components", col.n_components)) != col.n_components:
                raise ValueError("cache n_components mismatch")
            last_K_tray = np.asarray(cache.get("K_tray"), dtype=float).reshape((col.n_stages, col.n_components))
            last_HL = np.asarray(cache.get("HL_BTU_lbmol_tray"), dtype=float).reshape((col.n_stages,))
            last_HV = np.asarray(cache.get("HV_BTU_lbmol_tray"), dtype=float).reshape((col.n_stages,))
            last_Zfac = np.asarray(cache.get("Z_tray"), dtype=float).reshape((col.n_stages,))
            last_Z_tray = last_Zfac.copy()
            last_T_tray = np.asarray(cache.get("T_tray_F"), dtype=float).reshape((col.n_stages,))
            cache_loaded = True
        except Exception as exc:
            print(f"[Warn] Ignoring thermo cache due to mismatch: {exc}")
            cache_loaded = False
    # Initial conditions from ColumnSpec
    y = layout.pack_y0(col)
    if not bool(cfg.use_excel_vapor_holdup):
        y = _clear_initial_tray_vapor_holdup(y, layout)
    _milestone("packed initial state")

    # Make MV consistent with P_spec at t=0 (uses Z from one initial thermo pass)
    init_inputs = base_inputs
    if cache_loaded and last_Zfac is not None:
        init_inputs = replace(base_inputs, Zfac_prev=last_Zfac)

    y = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y,
        inputs=init_inputs,
        include_temperature=bool(cfg.include_temperature),
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
    pressure_control_enabled, top_pressure_ctrl, top_pressure_sp, pressure_control_mv = _build_pressure_controller(
        col=col,
        cfg=cfg,
    )
    if pressure_control_enabled and top_pressure_ctrl is not None and top_pressure_sp is not None:
        print(
            "[Control] Pressure control enabled  "
            f"MV={str(pressure_control_mv)}  "
            f"top_P_SP={float(top_pressure_sp):.3f} psia  "
            f"Kc={float(top_pressure_ctrl.kc):.3g}  Ti={float(top_pressure_ctrl.ti_sec):.3g} s"
        )

    last_top_pressure_pv_psia: Optional[float] = None
    try:
        p_ctrl_idx = 1 if int(getattr(col, "n_stages", 1)) > 1 else 0
        p0 = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[p_ctrl_idx])
        if np.isfinite(p0) and p0 > 0.0:
            last_top_pressure_pv_psia = p0
    except Exception:
        pass

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
            step_pressure_top_anchor_psia: Optional[float] = (
                float(base_inputs.pressure_top_anchor_psia)
                if base_inputs.pressure_top_anchor_psia is not None
                else None
            )
            step_pressure_top_anchor_cmd_psia: Optional[float] = None
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
                dt_ctrl = float(dt) if step > 0 else 0.0
                dist_cmd = _pi_update(
                    top_level_ctrl,
                    pv=top_level_pv,
                    sp=float(top_level_sp),
                    dt_sec=dt_ctrl,
                )
                bot_cmd = _pi_update(
                    bot_level_ctrl,
                    pv=bot_level_pv,
                    sp=float(bot_level_sp),
                    dt_sec=dt_ctrl,
                )
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

            if pressure_control_enabled and top_pressure_ctrl is not None and top_pressure_sp is not None:
                p_ctrl_idx = 1 if int(getattr(col, "n_stages", 1)) > 1 else 0
                pv = None
                if last_top_pressure_pv_psia is not None:
                    try:
                        pv_try = float(last_top_pressure_pv_psia)
                        if np.isfinite(pv_try) and pv_try > 0.0:
                            pv = pv_try
                    except Exception:
                        pv = None
                if pv is None:
                    try:
                        pv = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[p_ctrl_idx])
                    except Exception:
                        pv = float(top_pressure_sp)
                dt_ctrl = float(dt) if step > 0 else 0.0
                q_cmd = _pi_update(
                    top_pressure_ctrl,
                    pv=float(pv),
                    sp=float(top_pressure_sp),
                    dt_sec=dt_ctrl,
                )
                if str(pressure_control_mv) == "top-anchor":
                    step_pressure_top_anchor_cmd_psia = float(q_cmd)
                    step_pressure_top_anchor_psia = float(q_cmd)
                else:
                    step_condenser_duty_cmd_btu_per_h = float(q_cmd)
                    if str(step_condenser_duty_mode).strip().lower() == "total-condense":
                        # Keep total-condense closure and apply PI as a duty trim.
                        ctrl_trim = float(q_cmd) - float(top_pressure_ctrl.bias)
                        base_trim = float(step_condenser_duty_trim_btu_per_h) if step_condenser_duty_trim_btu_per_h is not None else 0.0
                        step_condenser_duty_trim_btu_per_h = base_trim + ctrl_trim
                    else:
                        step_condenser_duty_mode = "specified"
                        step_condenser_duty_btu_per_h = float(q_cmd)

            do_thermo = (step % thermo_every) == 0
            if cache_loaded and step == 0:
                do_thermo = False
            if base_inputs.thermo_refresh_dT_F is not None:
                if last_T_tray is None:
                    do_thermo = True
                else:
                    try:
                        T_now = _tray_temperature_F(
                            col,
                            layout,
                            y,
                            include_temperature=bool(cfg.include_temperature),
                        )
                        dT_max = float(np.nanmax(np.abs(T_now - last_T_tray)))
                        do_thermo = bool(np.isfinite(dT_max) and dT_max >= float(base_inputs.thermo_refresh_dT_F))
                    except Exception:
                        do_thermo = True

            if do_thermo:
                inputs = ColumnInputs(
                    boundary=step_boundary,
                    volume_model=base_inputs.volume_model,
                    thermo=base_inputs.thermo,
                    thermo_provider=base_inputs.thermo_provider,
                    compute_thermo_diag=base_inputs.compute_thermo_diag,
                    equilibrium_relaxation=base_inputs.equilibrium_relaxation,
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
                    reboiler_mode=base_inputs.reboiler_mode,
                    reboiler_equilibrium=base_inputs.reboiler_equilibrium,
                    pressure_model=base_inputs.pressure_model,
                    pressure_top_anchor_psia=(
                        float(step_pressure_top_anchor_psia)
                        if step_pressure_top_anchor_psia is not None
                        else None
                    ),
                    vapor_flow_model=base_inputs.vapor_flow_model,
                    dry_tray_K=base_inputs.dry_tray_K,
                    vapor_holdup_relaxation_sec=base_inputs.vapor_holdup_relaxation_sec,
                    vapor_flow_relaxation_sec=base_inputs.vapor_flow_relaxation_sec,
                    reboiler_neighbor_vflow_hi_ratio=base_inputs.reboiler_neighbor_vflow_hi_ratio,
                    reboiler_neighbor_vflow_lo_ratio=base_inputs.reboiler_neighbor_vflow_lo_ratio,
                    thermo_refresh_dT_F=base_inputs.thermo_refresh_dT_F,
                    thermo_refresh_dP_psia=base_inputs.thermo_refresh_dP_psia,
                    thermo_refresh_dx=base_inputs.thermo_refresh_dx,
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
                    equilibrium_relaxation=False,
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
                    pressure_model=base_inputs.pressure_model,
                    pressure_top_anchor_psia=(
                        float(step_pressure_top_anchor_psia)
                        if step_pressure_top_anchor_psia is not None
                        else None
                    ),
                    # Do not run energy-based V closure without live thermo refresh.
                    vapor_flow_model="profile",
                    dry_tray_K=base_inputs.dry_tray_K,
                    vapor_holdup_relaxation_sec=base_inputs.vapor_holdup_relaxation_sec,
                    vapor_flow_relaxation_sec=base_inputs.vapor_flow_relaxation_sec,
                    reboiler_neighbor_vflow_hi_ratio=base_inputs.reboiler_neighbor_vflow_hi_ratio,
                    reboiler_neighbor_vflow_lo_ratio=base_inputs.reboiler_neighbor_vflow_lo_ratio,
                    thermo_refresh_dT_F=base_inputs.thermo_refresh_dT_F,
                    thermo_refresh_dP_psia=base_inputs.thermo_refresh_dP_psia,
                    thermo_refresh_dx=base_inputs.thermo_refresh_dx,
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

            dydt, diag = column_rhs(t_s, y, col, layout, inputs=inputs)
            if (
                step_condenser_duty_cmd_btu_per_h is not None
                and np.isfinite(float(step_condenser_duty_cmd_btu_per_h))
            ):
                diag["Q_cond_cmd_BTUph"] = np.array([float(step_condenser_duty_cmd_btu_per_h)], dtype=float)
            elif step_condenser_duty_btu_per_h is not None and np.isfinite(float(step_condenser_duty_btu_per_h)):
                diag["Q_cond_cmd_BTUph"] = np.array([float(step_condenser_duty_btu_per_h)], dtype=float)
            if (
                step_pressure_top_anchor_cmd_psia is not None
                and np.isfinite(float(step_pressure_top_anchor_cmd_psia))
            ):
                diag["P_top_anchor_cmd_psia"] = np.array([float(step_pressure_top_anchor_cmd_psia)], dtype=float)

            # Pressure-controller PV source (prefer hydraulic top pressure).
            p_ctrl_idx = 1 if int(getattr(col, "n_stages", 1)) > 1 else 0
            p_top_pv = None
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
            if p_top_pv is not None:
                last_top_pressure_pv_psia = float(p_top_pv)
                diag["P_top_ctrl_pv_psia"] = np.array([float(p_top_pv)], dtype=float)

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

                print(
                    f"[Progress] step={step:6d}  sim_t={t_s:10.2f} s  wall={wall_elapsed_s:10.2f} s  "
                    f"sim/wall={sim_per_wall:8.3f}"
                )

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

            y = y + dt * dydt
            y = _clamp_nonnegative_holdups(y, layout)
            y = _clip_temperature_states_to_provider_bounds(y, layout, thermo_provider)
            t_s += dt

    finally:
        if profile_file is not None:
            profile_file.close()
        if summary_file is not None:
            summary_file.close()

    return {
        "excel_path": str(Path(cfg.excel_path).resolve()),
        "logs_dir": str(logs_dir),
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
    }


# -------------------------
# CLI
# -------------------------


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Dynamic distillation smoke-test runner")

    p.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")

    # Backward-compatible steps flag + alias
    p.add_argument("--n-steps", dest="n_steps", type=int, default=600)
    p.add_argument("--steps", dest="n_steps", type=int, default=None)

    p.add_argument("--dt", dest="dt_sec", type=float, default=None)
    p.add_argument("--log-every", dest="log_every_n_steps", type=int, default=None)

    # Backward-compatible temperature/energy flags
    p.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    p.add_argument("--no-temp", dest="include_temperature", action="store_false")
    p.add_argument("--include-energy", dest="include_energy", action="store_true")
    p.add_argument("--energy", dest="include_energy", action="store_true")

    # Backward-compatible equilibrium flags
    p.add_argument("--no-equilibrium", dest="enable_equilibrium_relaxation", action="store_false")
    p.add_argument("--no-eq", dest="enable_equilibrium_relaxation", action="store_false")

    p.add_argument("--thermo", dest="thermo_mode", choices=["stub", "dwsim", "table"], default="stub")

    # Thermo throttling
    p.add_argument("--thermo-every", dest="thermo_every_n_steps", type=int, default=1)
    p.add_argument("--thermo-refresh-dt", dest="thermo_refresh_dT_F", type=float, default=None)
    p.add_argument("--thermo-refresh-dp", dest="thermo_refresh_dP_psia", type=float, default=None)
    p.add_argument("--thermo-refresh-dx", dest="thermo_refresh_dx", type=float, default=None)
    p.add_argument("--thermo-table", dest="thermo_table_path", default=None)
    p.add_argument("--thermo-cache", dest="thermo_cache_path", default=None)
    p.add_argument("--reb-neighbor-vflow-hi-ratio", dest="reboiler_neighbor_vflow_hi_ratio", type=float, default=None)
    p.add_argument("--reb-neighbor-vflow-lo-ratio", dest="reboiler_neighbor_vflow_lo_ratio", type=float, default=None)
    p.add_argument("--use-excel-vapor-holdup", dest="use_excel_vapor_holdup", action="store_true")

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
    p.add_argument("--top-pressure-sp", dest="top_pressure_sp_psia", type=float, default=None)
    p.add_argument("--top-pressure-kc", dest="top_pressure_kc", type=float, default=None)
    p.add_argument("--top-pressure-ti", dest="top_pressure_ti_sec", type=float, default=None)
    p.add_argument("--top-pressure-anchor-min", dest="top_pressure_anchor_min_psia", type=float, default=None)
    p.add_argument("--top-pressure-anchor-max", dest="top_pressure_anchor_max_psia", type=float, default=None)
    p.add_argument("--condenser-duty-min-btuph", dest="condenser_duty_min_btu_per_h", type=float, default=None)
    p.add_argument("--condenser-duty-max-btuph", dest="condenser_duty_max_btu_per_h", type=float, default=None)

    p.add_argument("--logs-dir", dest="logs_dir", default="logs")
    p.add_argument("--no-write-logs", dest="write_logs", action="store_false")
    p.add_argument("--no-logs", dest="write_logs", action="store_false")

    args = p.parse_args(argv)

    if args.n_steps is None:
        args.n_steps = 600

    cfg = RunnerConfig(
        excel_path=str(args.excel_path),
        n_steps=int(args.n_steps),
        dt_sec=args.dt_sec,
        log_every_n_steps=args.log_every_n_steps,
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        enable_equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
        thermo_mode=str(args.thermo_mode),
        thermo_every_n_steps=int(args.thermo_every_n_steps),
        thermo_refresh_dT_F=args.thermo_refresh_dT_F,
        thermo_refresh_dP_psia=args.thermo_refresh_dP_psia,
        thermo_refresh_dx=args.thermo_refresh_dx,
        thermo_table_path=args.thermo_table_path,
        reboiler_neighbor_vflow_hi_ratio=args.reboiler_neighbor_vflow_hi_ratio,
        reboiler_neighbor_vflow_lo_ratio=args.reboiler_neighbor_vflow_lo_ratio,
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
        top_pressure_sp_psia=args.top_pressure_sp_psia,
        top_pressure_kc=args.top_pressure_kc,
        top_pressure_ti_sec=args.top_pressure_ti_sec,
        top_pressure_anchor_min_psia=args.top_pressure_anchor_min_psia,
        top_pressure_anchor_max_psia=args.top_pressure_anchor_max_psia,
        condenser_duty_min_btu_per_h=args.condenser_duty_min_btu_per_h,
        condenser_duty_max_btu_per_h=args.condenser_duty_max_btu_per_h,
        logs_dir=str(args.logs_dir),
        write_logs=bool(args.write_logs),
        thermo_cache_path=args.thermo_cache_path,
        use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
    )

    out = run_smoke_simulation(cfg)
    if out.get("profile_csv"):
        print(f"Wrote: {out['profile_csv']}")
    if out.get("summary_csv"):
        print(f"Wrote: {out['summary_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
