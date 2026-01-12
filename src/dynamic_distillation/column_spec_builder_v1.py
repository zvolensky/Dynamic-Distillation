"""
column_spec_builder_v1.py

Dynamic Distillation - ColumnSpec builder

Created: 2026-01-11  (America/New_York)
Updated: 2026-01-11 18:xx (America/New_York)

Purpose
-------
Convert CaseData (loaded from Excel) into a model-ready ColumnSpec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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

    # Module 8B: equilibrium relaxation time constant (seconds)
    tau_eq_sec: float = 10.0


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
        streams=streams_norm,
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
                vapor_fraction=_to_float(stream_obj.get("Vapour Fraction") or stream_obj.get("vapor_fraction")),
                total_molar_flow_lbmolph=_to_float(stream_obj.get("Total Molar Flow (lbmol/h)") or stream_obj.get("total_molar_flow_lbmolph")),
                component_molar_flows_lbmolph=stream_obj.get("Component Mole Flows (lbmol/h)") or stream_obj.get("component_molar_flows_lbmolph"),
            )
    return out


def _to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(float(x))
    except Exception:
        return None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None