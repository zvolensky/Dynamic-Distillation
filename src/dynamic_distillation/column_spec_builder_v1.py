"""
column_spec_builder_v1.py

Dynamic Distillation - Column Specification Builder

PURPOSE
-------
Transform loader CaseData into validated immutable ColumnSpec used by runner
and RHS. Handles stage profiles, streams normalization, duties, simulation
settings, optional geometry expansion, and consistency checks.

INPUTS
------
build_column_spec_from_case(case):
- CaseData from excel_case_loader_v1
- specifications dict, initial-condition profiles, optional stream data

OUTPUTS
-------
ColumnSpec dataclass with:
- dimensions/components
- tray initial profiles and compositions
- stream definitions and feed stage
- optional geometry model
- simulation and duty defaults
- normalized specs_raw dictionary

KEY DEPENDENCIES
----------------
- numpy/pandas
- excel_case_loader_v1.CaseData

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Stage indices must be contiguous 1..N.
- Composition matrices must align with component count.
- Geometry expansion requires valid section bounds and dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import math

import numpy as np
import pandas as pd


class ColumnSpecError(RuntimeError):
    """Raised when CaseData cannot be converted into a valid ColumnSpec."""


@dataclass(frozen=True)
class StreamSpecNormalized:
    name: str
    stage_1based: Optional[int] = None
    pressure_psia: Optional[float] = None
    temperature_f: Optional[float] = None
    vapor_fraction: Optional[float] = None
    total_molar_flow_lbmolph: Optional[float] = None
    component_molar_flows_lbmolph: Optional[Dict[str, float]] = None


@dataclass(frozen=True)
class SimulationSettings:
    dt_sec: float
    t_final_sec: float
    log_every_n_steps: int


@dataclass(frozen=True)
class HeatDuties:
    condenser_type: Optional[str]
    q_cond_btu_per_h: Optional[float]
    q_reb_btu_per_h: Optional[float]


@dataclass(frozen=True)
class ColumnGeometrySection:
    start_stage_1based: int
    end_stage_1based: int
    diameter_ft: float
    tray_spacing_ft: float
    gas_void_frac: float = 1.0
    weir_height_in: Optional[float] = None
    weir_length_ft: Optional[float] = None
    active_area_frac: Optional[float] = None
    hydraulic_c_factor: Optional[float] = None


@dataclass(frozen=True)
class ColumnGeometry:
    sections: List[ColumnGeometrySection]
    diameter_ft_per_stage: np.ndarray
    tray_spacing_ft_per_stage: np.ndarray
    gas_void_frac_per_stage: np.ndarray
    area_ft2_per_stage: np.ndarray
    vapor_volume_ft3_per_stage: np.ndarray
    weir_height_in_per_stage: Optional[np.ndarray] = None
    weir_length_ft_per_stage: Optional[np.ndarray] = None
    active_area_frac_per_stage: Optional[np.ndarray] = None
    active_area_ft2_per_stage: Optional[np.ndarray] = None
    hydraulic_c_factor_per_stage: Optional[np.ndarray] = None


@dataclass(frozen=True)
class ColumnSpec:
    excel_path: str

    components_excel: List[str]
    components_dwsim: List[str]
    n_components: int

    n_stages: int
    stage_1based: np.ndarray

    sim: SimulationSettings
    duties: HeatDuties

    specs_raw: Dict[str, Any]

    T_f: np.ndarray
    P_psia: np.ndarray
    V_lbmolph: np.ndarray
    L_lbmolph: np.ndarray
    M_L_lbmol: Optional[np.ndarray]
    M_V_lbmol: Optional[np.ndarray]
    y0: np.ndarray
    x0: np.ndarray

    streams: Dict[str, StreamSpecNormalized]
    top_L0_lbmol: Optional[np.ndarray] = None
    top_V0_lbmol: Optional[np.ndarray] = None
    bottom_L0_lbmol: Optional[np.ndarray] = None
    bottom_V0_lbmol: Optional[np.ndarray] = None
    tray_EL0_BTU: Optional[np.ndarray] = None
    tray_EV0_BTU: Optional[np.ndarray] = None
    controller_state: Optional[Dict[str, float]] = None

    # Optional expanded geometry (used for vapor volume diagnostics)
    geometry: Optional[ColumnGeometry] = None

    # Module 8B: equilibrium relaxation time constant (seconds)
    tau_eq_sec: float = 10.0


def _coerce_void_fraction(gv: float) -> float:
    """Accept either fraction (0..1] or percent (0..100]."""
    gv = float(gv)
    if gv <= 0.0:
        return gv
    if gv <= 1.0:
        return gv
    if gv <= 100.0:
        return gv / 100.0
    return gv


def _coerce_fraction(val: float) -> float:
    """Accept either fraction (0..1] or percent (0..100]."""
    return _coerce_void_fraction(val)


def _build_geometry_from_specs(specs_raw: Dict[str, Any], n_stages: int) -> Optional[ColumnGeometry]:
    sections_raw = specs_raw.get("Geometry Sections", None)
    if not sections_raw:
        return None
    if not isinstance(sections_raw, list):
        raise ColumnSpecError("Geometry Sections must be a list of rows (dicts).")

    sections: List[ColumnGeometrySection] = []
    for row in sections_raw:
        if not isinstance(row, dict):
            raise ColumnSpecError("Geometry Sections rows must be dict-like.")

        try:
            ss = int(float(row.get("start_stage_1based")))
            es = int(float(row.get("end_stage_1based")))
            d = float(row.get("diameter_ft"))
            sp = float(row.get("tray_spacing_ft"))
            gv = float(row.get("gas_void_frac", 1.0))
            wh = row.get("weir_height_in", None)
            wl = row.get("weir_length_ft", None)
            aa = row.get("active_area_frac", None)
            cf = row.get("hydraulic_c_factor", row.get("system_factor", None))
        except Exception as exc:
            raise ColumnSpecError("Geometry Sections row contains invalid values.") from exc

        gv = _coerce_void_fraction(gv)
        wh = None if wh is None else float(wh)
        wl = None if wl is None else float(wl)
        aa = None if aa is None else _coerce_fraction(float(aa))
        cf = None if cf is None else float(cf)
        if wh is not None and (not np.isfinite(wh) or wh < 0.0):
            raise ColumnSpecError("Geometry: weir height (in) must be >= 0 if provided.")
        if wl is not None and (not np.isfinite(wl) or wl <= 0.0):
            raise ColumnSpecError("Geometry: weir length (ft) must be > 0 if provided.")
        if aa is not None and (not np.isfinite(aa) or aa <= 0.0 or aa > 1.0):
            raise ColumnSpecError("Geometry: active area fraction must be in (0, 1] if provided.")
        if cf is not None and (not np.isfinite(cf) or cf <= 0.0):
            raise ColumnSpecError("Geometry: hydraulic/system factor must be > 0 if provided.")

        sections.append(
            ColumnGeometrySection(
                start_stage_1based=ss,
                end_stage_1based=es,
                diameter_ft=d,
                tray_spacing_ft=sp,
                gas_void_frac=gv,
                weir_height_in=wh,
                weir_length_ft=wl,
                active_area_frac=aa,
                hydraulic_c_factor=cf,
            )
        )

    N = int(n_stages)
    diam = np.full(N, np.nan, dtype=float)
    spacing = np.full(N, np.nan, dtype=float)
    void = np.full(N, np.nan, dtype=float)
    weir_h = np.full(N, np.nan, dtype=float)
    weir_L = np.full(N, np.nan, dtype=float)
    aaf = np.full(N, np.nan, dtype=float)
    cfac = np.full(N, np.nan, dtype=float)

    for s in sections:
        if s.start_stage_1based < 1 or s.end_stage_1based > N or s.end_stage_1based < s.start_stage_1based:
            raise ColumnSpecError("Geometry section stage bounds are invalid.")

        if (not np.isfinite(s.diameter_ft)) or s.diameter_ft <= 0.0:
            raise ColumnSpecError("Geometry: diameter (ft) must be > 0.")
        if (not np.isfinite(s.tray_spacing_ft)) or s.tray_spacing_ft <= 0.0:
            raise ColumnSpecError("Geometry: tray spacing (ft) must be > 0.")
        if (not np.isfinite(s.gas_void_frac)) or s.gas_void_frac <= 0.0 or s.gas_void_frac > 1.0:
            raise ColumnSpecError("Geometry: gas void fraction must be in (0, 1].")

        i0 = s.start_stage_1based - 1
        i1 = s.end_stage_1based
        diam[i0:i1] = float(s.diameter_ft)
        spacing[i0:i1] = float(s.tray_spacing_ft)
        void[i0:i1] = float(s.gas_void_frac)
        if s.weir_height_in is not None:
            weir_h[i0:i1] = float(s.weir_height_in)
        if s.weir_length_ft is not None:
            weir_L[i0:i1] = float(s.weir_length_ft)
        if s.active_area_frac is not None:
            aaf[i0:i1] = float(s.active_area_frac)
        if s.hydraulic_c_factor is not None:
            cfac[i0:i1] = float(s.hydraulic_c_factor)

    # Fill gaps:
    # - If Stage 1 missing (common, condenser), back-fill from Stage 2 / first defined stage.
    # - Forward-fill any internal gaps using previous defined value.
    if np.all(~np.isfinite(diam)):
        raise ColumnSpecError("Geometry sections did not provide any usable stage coverage.")

    # Find first finite index
    first = int(np.argmax(np.isfinite(diam)))

    for arr in (diam, spacing, void, weir_h, weir_L, aaf, cfac):
        # Back-fill leading NaNs with first finite value
        for i in range(0, first):
            arr[i] = arr[first]
        # Forward-fill remaining NaNs
        for i in range(first + 1, N):
            if not np.isfinite(arr[i]):
                arr[i] = arr[i - 1]

    # Default hydraulic factor to 1.0 when absent.
    cfac = np.where(np.isfinite(cfac) & (cfac > 0.0), cfac, 1.0)

    # Derived geometry
    area = math.pi * (0.5 * diam) ** 2
    v_stage = area * spacing * void
    active_area = area * aaf

    return ColumnGeometry(
        sections=sections,
        diameter_ft_per_stage=diam,
        tray_spacing_ft_per_stage=spacing,
        gas_void_frac_per_stage=void,
        area_ft2_per_stage=area,
        vapor_volume_ft3_per_stage=v_stage,
        weir_height_in_per_stage=weir_h,
        weir_length_ft_per_stage=weir_L,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area,
        hydraulic_c_factor_per_stage=cfac,
    )


def build_column_spec_from_case(case: Any) -> ColumnSpec:
    excel_path = getattr(case, "excel_path", None) or getattr(case, "path", None) or "<unknown>"
    excel_path = str(excel_path)

    specs_raw: Dict[str, Any] = dict(getattr(case, "specs", {}) or {})
    comps_excel: List[str] = list(getattr(case, "components", []) or [])

    comps_dwsim = getattr(case, "component_ids_dwsim", None)
    if comps_dwsim is None:
        comps_dwsim = comps_excel
    comps_dwsim = list(comps_dwsim)

    if not comps_excel:
        raise ColumnSpecError("CaseData has no components.")
    if len(comps_excel) != len(comps_dwsim):
        raise ColumnSpecError(
            f"components_excel length {len(comps_excel)} != components_dwsim length {len(comps_dwsim)}"
        )

    n_components = len(comps_excel)

    ic_df: pd.DataFrame = getattr(case, "initial_conditions", None)
    if ic_df is None or not isinstance(ic_df, pd.DataFrame):
        raise ColumnSpecError("CaseData.initial_conditions must be a pandas DataFrame.")

    n_stages = _req_int(specs_raw, "Number of Stages")
    ncomp_spec = _req_int(specs_raw, "Number of Components")
    if ncomp_spec != n_components:
        raise ColumnSpecError(
            f"Specs Number of Components={ncomp_spec} but found {n_components} component names in Excel."
        )

    if "Stage" not in ic_df.columns:
        raise ColumnSpecError("Initial Conditions missing required column 'Stage'.")

    stage_1based = ic_df["Stage"].to_numpy()
    if len(stage_1based) != n_stages:
        raise ColumnSpecError(
            f"Initial Conditions has {len(stage_1based)} rows but Number of Stages={n_stages}."
        )

    try:
        stage_int = stage_1based.astype(int)
    except Exception as exc:
        raise ColumnSpecError("Initial Conditions 'Stage' column is not integer-like.") from exc

    expected = np.arange(1, n_stages + 1, dtype=int)
    if not np.array_equal(stage_int, expected):
        raise ColumnSpecError(
            "Initial Conditions 'Stage' must be 1..N in order.\n"
            f"Expected: {expected.tolist()}\n"
            f"Found:    {stage_int.tolist()}"
        )

    # Required IC columns
    T_f = _req_float_col(ic_df, "Temperature (F)", n_stages)
    P_psia = _req_float_col(ic_df, "Pressure (psia)", n_stages)
    V_lbmolph = _req_float_col(ic_df, "Vapor Flow (lbmol/h)", n_stages)
    L_lbmolph = _req_float_col(ic_df, "Liquid Flow (lbmol/h)", n_stages)

    M_L_lbmol = _opt_float_col(ic_df, "Liquid Holdup (lbmol)", n_stages)
    M_V_lbmol = _opt_float_col(ic_df, "Vapor Holdup (lbmol)", n_stages)

    y0 = _read_comp_matrix(ic_df, prefix="Vapor Composition Component ", n_stages=n_stages, n_components=n_components)
    x0 = _read_comp_matrix(ic_df, prefix="Liquid Composition Component ", n_stages=n_stages, n_components=n_components)

    _validate_mole_frac_sums(y0, "y0 (vapor)", tol=5e-6)
    _validate_mole_frac_sums(x0, "x0 (liquid)", tol=5e-6)

    # Simulation settings
    dt = _req_float(specs_raw, "Timestep (sec)")
    sim_len_min = _req_float(specs_raw, "Simulation Length (min)")
    t_final_sec = sim_len_min * 60.0
    log_every = _req_int(specs_raw, "Log Frequency (timesteps)")
    if log_every <= 0:
        raise ColumnSpecError("Log Frequency (timesteps) must be > 0.")
    sim = SimulationSettings(dt_sec=float(dt), t_final_sec=float(t_final_sec), log_every_n_steps=int(log_every))

    # Duties
    condenser_type = _opt_str(specs_raw, "Condenser Type")
    q_cond = _opt_float(specs_raw, "Condenser Duty (Btu/h)")
    q_reb = _opt_float(specs_raw, "Reboiler Duty (Btu/h)")
    duties = HeatDuties(condenser_type=condenser_type, q_cond_btu_per_h=q_cond, q_reb_btu_per_h=q_reb)

    # Module 8B: tau from Excel (optional, defaults to 10)
    tau = _opt_float(specs_raw, "Stage time constant [tau] (sec)")
    if tau is None:
        tau = 10.0
    if (not np.isfinite(float(tau))) or float(tau) <= 0.0:
        raise ColumnSpecError("Stage time constant [tau] (sec) must be > 0 if provided.")

    # Geometry (optional)
    geometry = _build_geometry_from_specs(specs_raw, n_stages)

    boundary_state_raw = getattr(case, "boundary_state", {}) or {}
    top_L0 = top_V0 = bottom_L0 = bottom_V0 = None
    for key in ("top_L", "top_V", "bottom_L", "bottom_V"):
        vals = boundary_state_raw.get(key)
        if vals is None:
            continue
        arr = np.asarray(vals, dtype=float).reshape((-1,))
        if arr.size != n_components:
            raise ColumnSpecError(f"Boundary State '{key}' length {arr.size} != expected {n_components}.")
        if np.any(~np.isfinite(arr)) or np.any(arr < 0.0):
            raise ColumnSpecError(f"Boundary State '{key}' contains invalid values.")
        if key == "top_L":
            top_L0 = arr.copy()
        elif key == "top_V":
            top_V0 = arr.copy()
        elif key == "bottom_L":
            bottom_L0 = arr.copy()
        elif key == "bottom_V":
            bottom_V0 = arr.copy()

    energy_state_raw = getattr(case, "energy_state", {}) or {}
    tray_EL0 = tray_EV0 = None
    vals = energy_state_raw.get("tray_EL_BTU")
    if vals is not None:
        arr = np.asarray(vals, dtype=float).reshape((-1,))
        if arr.size != n_stages:
            raise ColumnSpecError(f"Energy State 'tray_EL_BTU' length {arr.size} != expected {n_stages}.")
        if np.any(~np.isfinite(arr)):
            raise ColumnSpecError("Energy State 'tray_EL_BTU' contains invalid values.")
        tray_EL0 = arr.copy()
    vals = energy_state_raw.get("tray_EV_BTU")
    if vals is not None:
        arr = np.asarray(vals, dtype=float).reshape((-1,))
        if arr.size != n_stages:
            raise ColumnSpecError(f"Energy State 'tray_EV_BTU' length {arr.size} != expected {n_stages}.")
        if np.any(~np.isfinite(arr)):
            raise ColumnSpecError("Energy State 'tray_EV_BTU' contains invalid values.")
        tray_EV0 = arr.copy()

    controller_state_raw = getattr(case, "controller_state", {}) or {}
    controller_state: Dict[str, float] = {}
    for key, val in controller_state_raw.items():
        try:
            fv = float(val)
        except Exception:
            continue
        if np.isfinite(fv):
            controller_state[str(key)] = fv

    streams_in = getattr(case, "streams", {}) or {}
    streams_norm = _normalize_streams(streams_in)

    return ColumnSpec(
        excel_path=excel_path,
        components_excel=comps_excel,
        components_dwsim=comps_dwsim,
        n_components=n_components,
        n_stages=n_stages,
        stage_1based=stage_int.astype(int),
        sim=sim,
        duties=duties,
        specs_raw=specs_raw,
        T_f=T_f,
        P_psia=P_psia,
        V_lbmolph=V_lbmolph,
        L_lbmolph=L_lbmolph,
        M_L_lbmol=M_L_lbmol,
        M_V_lbmol=M_V_lbmol,
        y0=y0,
        x0=x0,
        top_L0_lbmol=top_L0,
        top_V0_lbmol=top_V0,
        bottom_L0_lbmol=bottom_L0,
        bottom_V0_lbmol=bottom_V0,
        tray_EL0_BTU=tray_EL0,
        tray_EV0_BTU=tray_EV0,
        controller_state=(controller_state or None),
        streams=streams_norm,
        geometry=geometry,
        tau_eq_sec=float(tau),
    )


# -------------------------
# Helpers
# -------------------------

def _req_int(specs: Dict[str, Any], key: str) -> int:
    if key not in specs:
        raise ColumnSpecError(f"Missing required spec: '{key}'")
    try:
        return int(float(specs[key]))
    except Exception as exc:
        raise ColumnSpecError(f"Spec '{key}' must be integer-like. Got: {specs[key]!r}") from exc


def _req_float(specs: Dict[str, Any], key: str) -> float:
    if key not in specs:
        raise ColumnSpecError(f"Missing required spec: '{key}'")
    try:
        return float(specs[key])
    except Exception as exc:
        raise ColumnSpecError(f"Spec '{key}' must be float-like. Got: {specs[key]!r}") from exc


def _opt_float(specs: Dict[str, Any], key: str) -> Optional[float]:
    if key not in specs:
        return None
    v = specs[key]
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _opt_str(specs: Dict[str, Any], key: str) -> Optional[str]:
    if key not in specs:
        return None
    v = specs[key]
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _req_float_col(df: pd.DataFrame, col: str, n: int) -> np.ndarray:
    if col not in df.columns:
        raise ColumnSpecError(f"Initial Conditions missing required column '{col}'.")
    arr = df[col].to_numpy(dtype=float)
    if len(arr) != n:
        raise ColumnSpecError(f"Column '{col}' length {len(arr)} != expected {n}.")
    if np.any(np.isnan(arr)):
        raise ColumnSpecError(f"Column '{col}' contains NaN values.")
    return arr


def _opt_float_col(df: pd.DataFrame, col: str, n: int) -> Optional[np.ndarray]:
    if col not in df.columns:
        return None
    try:
        arr = df[col].to_numpy(dtype=float)
    except Exception:
        return None
    if len(arr) != n:
        raise ColumnSpecError(f"Optional column '{col}' length {len(arr)} != expected {n}.")
    if np.all(np.isnan(arr)):
        return None
    return arr


def _read_comp_matrix(df: pd.DataFrame, prefix: str, n_stages: int, n_components: int) -> np.ndarray:
    cols = [f"{prefix}{i}" for i in range(1, n_components + 1)]
    for c in cols:
        if c not in df.columns:
            raise ColumnSpecError(f"Initial Conditions missing composition column '{c}'")
    mat = df[cols].to_numpy(dtype=float)
    if mat.shape != (n_stages, n_components):
        raise ColumnSpecError(f"Composition matrix shape {mat.shape} != expected {(n_stages, n_components)}")
    if np.any(np.isnan(mat)):
        raise ColumnSpecError("Composition matrix contains NaN values.")
    return mat


def _validate_mole_frac_sums(mat: np.ndarray, label: str, tol: float = 1e-6) -> None:
    s = np.sum(mat, axis=1)
    if np.any(np.abs(s - 1.0) > tol):
        bad = np.where(np.abs(s - 1.0) > tol)[0]
        raise ColumnSpecError(f"{label}: row sums not ~1.0 within {tol}. Bad rows: {bad.tolist()}")


def _normalize_streams(streams_in: Any) -> Dict[str, StreamSpecNormalized]:
    out: Dict[str, StreamSpecNormalized] = {}
    if not isinstance(streams_in, dict):
        return out

    for name, stream_obj in streams_in.items():
        if stream_obj is None:
            continue

        if isinstance(stream_obj, dict):
            out[name] = StreamSpecNormalized(
                name=name,
                stage_1based=_to_int(stream_obj.get("Stage") or stream_obj.get("stage_1based")),
                pressure_psia=_to_float(stream_obj.get("Pressure (psia)") or stream_obj.get("pressure_psia")),
                temperature_f=_to_float(stream_obj.get("Temperature (F)") or stream_obj.get("temperature_f")),
                vapor_fraction=_to_float(_get_first_key(stream_obj, ["Vapour Fraction", "Vapour fraction", "Vapor Fraction", "Vapor fraction", "vapour_fraction", "vapor_fraction"])),
                total_molar_flow_lbmolph=_to_float(
                    _get_first_key(stream_obj, ["Total Molar Flow (lbmol/h)", "Total molar flow (lbmol/h)", "total_molar_flow_lbmolph"])
                ),
                component_molar_flows_lbmolph=stream_obj.get("Component Mole Flows (lbmol/h)")
                or stream_obj.get("component_molar_flows_lbmolph"),
            )
    return out


def _to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(float(x))
    except Exception:
        return None



def _get_first_key(d: Dict[str, Any], keys: Sequence[str]) -> Any:
    """Return d[k] for the first key present in d (even if the value is 0.0 / False)."""
    for k in keys:
        if k in d:
            return d[k]
    return None

def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None
