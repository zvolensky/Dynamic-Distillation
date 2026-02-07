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

    thermo_mode: str = "stub"  # 'stub' or 'dwsim'
    thermo_every_n_steps: int = 1  # 1=every step

    reflux_lbmolph: Optional[float] = None
    boilup_lbmolph: Optional[float] = None

    logs_dir: str = "logs"
    write_logs: bool = True


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


def build_inputs_for_runner(case: CaseData, col: ColumnSpec, cfg: RunnerConfig) -> Tuple[ColumnInputs, Any]:
    thermo_mode = (cfg.thermo_mode or "").strip().lower()

    if thermo_mode == "dwsim":
        from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1

        prov = ThermoProviderV1(
            component_names_excel=col.components_excel,
            component_ids_dwsim=col.components_dwsim,
            silence_backend_console=True,
        )
    elif thermo_mode == "stub":
        Nc = int(col.n_components)
        if Nc == 1:
            K = np.array([1.0], dtype=float)
        else:
            K = 2.0 ** (1.0 - np.arange(Nc, dtype=float) / float(Nc - 1))
        prov = StubThermoProvider(K=K, Z=1.0)
    else:
        raise ValueError(f"Unsupported thermo_mode: {thermo_mode!r} (use 'stub' or 'dwsim')")

    boundary = _infer_boundary_flows(case, col, cfg)
    vol = _build_volume_model(col, default_vapor_volume_ft3=1.0)

    inputs = ColumnInputs(
        boundary=boundary,
        volume_model=vol,
        thermo_provider=prov,
        compute_thermo_diag=True,
        equilibrium_relaxation=bool(cfg.enable_equilibrium_relaxation),
        tau_eq_sec=getattr(col, "tau_eq_sec", None),
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

    # One thermo pass at t=0 to get Z_tray (if available)
    init_inputs = replace(inputs, equilibrium_relaxation=False)
    _dydt0, diag0 = column_rhs(0.0, y, col, layout, inputs=init_inputs)

    N = col.n_stages
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

    # Apply to tray vapor component holdups using current vapor fractions
    u = layout.unpack(y)
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
    if "T_reb_F" in diag:
        try:
            T_reb_diag = float(np.asarray(diag["T_reb_F"]).reshape((-1,))[0])
            if np.isfinite(T_reb_diag):
                T = np.asarray(T, dtype=float).copy()
                T[-1] = float(T_reb_diag)
        except Exception:
            pass
    T_distillate = None
    if layout.include_top and "top_T_f" in u:
        try:
            T_distillate = float(u["top_T_f"][0])
        except Exception:
            T_distillate = None
    if T_distillate is None:
        T_distillate = float(T[0])
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
            "P_psia_diag": float(P_diag[i]) if np.isfinite(P_diag[i]) else np.nan,
            "L_out_hyd_lbmolph": float(L_out_hyd[i]) if L_out_hyd is not None and np.isfinite(L_out_hyd[i]) else np.nan,
            "h_ow_ft": float(h_ow[i]) if h_ow is not None and np.isfinite(h_ow[i]) else np.nan,
            "ML_lbmol": float(ML[i]),
            "MV_lbmol": float(MV[i]),
            "stage_mass_balance_resid_lbmolps": float(mass_resid[i]) if mass_resid is not None and np.isfinite(mass_resid[i]) else np.nan,
            "stage_energy_balance_resid_BTUps": float(energy_resid[i]) if energy_resid is not None and np.isfinite(energy_resid[i]) else np.nan,
            "reflux_ratio": _stage_value(i1, 1, reflux_ratio),
            # New: stream flow columns placed on their stages
            "F_lbmolph": _stage_value(i1, feed_tag.stage_1based, feed_tag.flow_lbmolph),
            "D_lbmolph": _stage_value(i1, dist_tag.stage_1based, dist_tag.flow_lbmolph),
            "B_lbmolph": _stage_value(i1, bots_tag.stage_1based, bots_tag.flow_lbmolph),
            "Distillate_L_lbmol": _stage_value(i1, 1 if layout.include_top else None, top_L_total),
            "Bottoms_L_lbmol": _stage_value(i1, N if layout.include_bottom else None, bottom_L_total),
            "T_Distillate_F": _stage_value(i1, 1 if layout.include_top else None, T_distillate),
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
    if "T_reb_F" in diag:
        try:
            T_reb_diag = float(np.asarray(diag["T_reb_F"]).reshape((-1,))[0])
            if np.isfinite(T_reb_diag):
                T = np.asarray(T, dtype=float).copy()
                T[-1] = float(T_reb_diag)
        except Exception:
            pass
    T_distillate = None
    if layout.include_top and "top_T_f" in u:
        try:
            T_distillate = float(u["top_T_f"][0])
        except Exception:
            T_distillate = None
    if T_distillate is None:
        T_distillate = float(T[0])

    if "P_psia_diag" in diag:
        P_diag = np.asarray(diag["P_psia_diag"], dtype=float).reshape((N,))
    else:
        P_diag = _pressure_diag_psia(col, volume_model, T, MV, Z)

    if N >= 1 and np.isfinite(P_spec[0]):
        P_diag[0] = float(P_spec[0])

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
    T_reboiler = float(T[-1])

    out: Dict[str, Any] = {
        "wall_clock_iso": wall_clock_iso,
        "wall_elapsed_s": float(wall_elapsed_s),
        "time_s": float(t_s),
        "P_top_psia": float(P_spec[0]) if np.isfinite(P_spec[0]) else float(P_diag[0]),
        "P_top_psia_diag": float(P_diag[0]) if np.isfinite(P_diag[0]) else np.nan,
        "P_top_psia_spec": float(P_spec[0]) if np.isfinite(P_spec[0]) else np.nan,
        "P_bot_psia": float(P_spec[-1]) if np.isfinite(P_spec[-1]) else float(P_diag[-1]),
        "P_bot_psia_diag": float(P_diag[-1]) if np.isfinite(P_diag[-1]) else np.nan,
        "P_bot_psia_spec": float(P_spec[-1]) if np.isfinite(P_spec[-1]) else np.nan,
        "T_top_F": float(T[0]),
        "T_Distillate_F": float(T_distillate) if T_distillate is not None else np.nan,
        # New: overall stream flow scalars
        "F_lbmolph": float(feed_tag.flow_lbmolph) if feed_tag.flow_lbmolph is not None else np.nan,
        "D_lbmolph": float(dist_tag.flow_lbmolph) if dist_tag.flow_lbmolph is not None else np.nan,
        "B_lbmolph": float(bots_tag.flow_lbmolph) if bots_tag.flow_lbmolph is not None else np.nan,
        "Distillate_L_lbmol": float(top_L_total) if top_L_total is not None else np.nan,
        "Bottoms_L_lbmol": float(bottom_L_total) if bottom_L_total is not None else np.nan,
        "T_sump_F": float(T_sump) if T_sump is not None else np.nan,
        "T_Reboiler_F": float(T_reboiler),
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
    case = load_case_from_excel(cfg.excel_path)
    col = build_column_spec_from_case(case)

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

    base_inputs, thermo_provider = build_inputs_for_runner(case, col, cfg)

    # Initial conditions from ColumnSpec
    y = layout.pack_y0(col)

    # Make MV consistent with P_spec at t=0 (uses Z from one initial thermo pass)
    y = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y,
        inputs=base_inputs,
        include_temperature=bool(cfg.include_temperature),
    )

    # Resolve streams for logging placement
    feed_tag, dist_tag, bots_tag = _resolve_logging_streams(case, col)

    tag = _timestamp_tag()
    logs_dir = Path(cfg.logs_dir)
    if not logs_dir.is_absolute():
        logs_dir = Path.cwd() / logs_dir
    if cfg.write_logs:
        _ensure_dir(logs_dir)

    profile_path = logs_dir / f"column_profile_{tag}.csv"
    summary_path = logs_dir / f"column_summary_{tag}.csv"

    profile_file = None
    summary_file = None

    start_perf = time.perf_counter()
    t_s = 0.0

    last_Z_tray: Optional[np.ndarray] = None
    last_y_eq: Optional[np.ndarray] = None
    last_P_diag: Optional[np.ndarray] = None
    last_rhoL: Optional[np.ndarray] = None
    last_K_tray: Optional[np.ndarray] = None
    last_HL: Optional[np.ndarray] = None
    last_HV: Optional[np.ndarray] = None
    last_Zfac: Optional[np.ndarray] = None
    last_diag: Optional[Dict[str, np.ndarray]] = None
    last_reb_T: Optional[float] = None
    last_reb_x: Optional[np.ndarray] = None
    last_reb_y: Optional[np.ndarray] = None
    last_reb_beta: Optional[float] = None

    try:
        if cfg.write_logs:
            profile_file = profile_path.open("w", newline="", encoding="utf-8")
            summary_file = summary_path.open("w", newline="", encoding="utf-8")

        profile_writer = None
        summary_writer = None
        profile_header_written = False
        summary_header_written = False

        for step in range(int(cfg.n_steps) + 1):
            do_thermo = (step % thermo_every) == 0

            if do_thermo:
                inputs = ColumnInputs(
                    boundary=base_inputs.boundary,
                    volume_model=base_inputs.volume_model,
                    thermo=base_inputs.thermo,
                    thermo_provider=base_inputs.thermo_provider,
                    compute_thermo_diag=base_inputs.compute_thermo_diag,
                    equilibrium_relaxation=base_inputs.equilibrium_relaxation,
                    tau_eq_sec=base_inputs.tau_eq_sec,
                    condenser_alpha=base_inputs.condenser_alpha,
                    clamp_alpha=base_inputs.clamp_alpha,
                    reboiler_mode=base_inputs.reboiler_mode,
                    reboiler_equilibrium=base_inputs.reboiler_equilibrium,
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
                    boundary=base_inputs.boundary,
                    volume_model=base_inputs.volume_model,
                    thermo=None,
                    thermo_provider=None,
                    compute_thermo_diag=False,
                    equilibrium_relaxation=False,
                    tau_eq_sec=base_inputs.tau_eq_sec,
                    rhoL_tray_lbmol_ft3=last_rhoL,
                    reb_T_prev=last_reb_T,
                    reb_x_prev=last_reb_x,
                    reb_y_prev=last_reb_y,
                    reb_beta_prev=last_reb_beta,
                )

            dydt, diag = column_rhs(t_s, y, col, layout, inputs=inputs)

            # Cache and carry forward thermo diagnostics so intermediate log rows don't show NaNs
            if do_thermo:
                if "Z_tray" in diag:
                    last_Z_tray = np.asarray(diag["Z_tray"], dtype=float).copy()
                if "y_eq_tray" in diag:
                    last_y_eq = np.asarray(diag["y_eq_tray"], dtype=float).copy()
                if "P_psia_diag" in diag:
                    last_P_diag = np.asarray(diag["P_psia_diag"], dtype=float).copy()
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
                last_diag = diag
            else:
                if last_Z_tray is not None:
                    diag["Z_tray"] = last_Z_tray
                if last_y_eq is not None:
                    diag["y_eq_tray"] = last_y_eq
                if last_P_diag is not None:
                    diag["P_psia_diag"] = last_P_diag
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
                        dist_tag=dist_tag,
                        bots_tag=bots_tag,
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
                        dist_tag=dist_tag,
                        bots_tag=bots_tag,
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

    p.add_argument("--thermo", dest="thermo_mode", choices=["stub", "dwsim"], default="stub")

    # Thermo throttling
    p.add_argument("--thermo-every", dest="thermo_every_n_steps", type=int, default=1)

    # Boundary overrides
    p.add_argument("--reflux", dest="reflux_lbmolph", type=float, default=None)
    p.add_argument("--boilup", dest="boilup_lbmolph", type=float, default=None)

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
        reflux_lbmolph=args.reflux_lbmolph,
        boilup_lbmolph=args.boilup_lbmolph,
        logs_dir=str(args.logs_dir),
        write_logs=bool(args.write_logs),
    )

    out = run_smoke_simulation(cfg)
    if out.get("profile_csv"):
        print(f"Wrote: {out['profile_csv']}")
    if out.get("summary_csv"):
        print(f"Wrote: {out['summary_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
