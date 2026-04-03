from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.excel_case_validator_v1 import validate_loaded_case


STARTUP_MILESTONE_ORDER = [
    "start",
    "loaded case from Excel",
    "built column spec",
    "validated Excel input",
    "built state vector layout",
    "built inputs and thermo provider",
    "packed initial state",
    "initialized vapor holdup from spec pressure",
    "initialized cached tray bubble-point targets",
    "resolved logging stream placement",
    "ensured logs directory",
    "opened log files",
]


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    try:
        arr = np.asarray(value)
    except Exception:
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]
    if arr.ndim == 0:
        try:
            return [arr.item()]
        except Exception:
            return [value]
    try:
        return arr.reshape((-1,)).tolist()
    except Exception:
        try:
            return list(value)
        except Exception:
            return [value]


def _coerce_local_timestamp(value: Any) -> Optional[dt.datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _latest_matching_file(
    logs_dir: Path,
    pattern: str,
    *,
    started_after_local: Any = None,
) -> Optional[Path]:
    matches = sorted(logs_dir.glob(pattern))
    started_after_dt = _coerce_local_timestamp(started_after_local)
    if started_after_dt is not None:
        filtered = []
        for path in matches:
            try:
                modified_dt = dt.datetime.fromtimestamp(path.stat().st_mtime)
            except Exception:
                continue
            if modified_dt >= started_after_dt:
                filtered.append(path)
        matches = filtered
    return matches[-1] if matches else None


def read_run_metadata(logs_dir: Path, *, started_after_local: Any = None) -> Dict[str, Any]:
    path = _latest_matching_file(logs_dir, "run_metadata_*.json", started_after_local=started_after_local)
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_summary_df(logs_dir: Path, *, started_after_local: Any = None) -> pd.DataFrame:
    path = _latest_matching_file(logs_dir, "column_summary_*.csv", started_after_local=started_after_local)
    if path is None or (not path.exists()):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def read_profile_df(logs_dir: Path, *, started_after_local: Any = None) -> pd.DataFrame:
    path = _latest_matching_file(logs_dir, "column_profile_*.csv", started_after_local=started_after_local)
    if path is None or (not path.exists()):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def latest_summary_row(summary_df: pd.DataFrame) -> Dict[str, Any]:
    if summary_df.empty:
        return {}
    return summary_df.iloc[-1].to_dict()


def latest_stage_snapshot(profile_df: pd.DataFrame) -> pd.DataFrame:
    if profile_df.empty or "time_s" not in profile_df.columns:
        return pd.DataFrame()
    t_final = profile_df["time_s"].max()
    out = profile_df.loc[profile_df["time_s"] == t_final].copy()
    if "stage" in out.columns:
        out = out.sort_values(["stage", "node_type"], kind="stable")
    return out


def extract_warning_lines(log_path: Path, *, limit: int = 20) -> List[str]:
    if not log_path.exists():
        return []
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    interesting = []
    for line in lines:
        txt = str(line).strip()
        if not txt:
            continue
        upper = txt.upper()
        if "[WARN]" in upper or "[ABORT]" in upper or "[ERROR]" in upper or "TRACEBACK" in upper:
            interesting.append(txt)
    return interesting[-limit:]


def tail_lines(path: Path, *, limit: int = 50) -> List[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    return lines[-limit:]


def read_runner_phase(stdout_log: Path) -> Dict[str, Any]:
    """
    Best-effort interpretation of runner stdout so the UI can distinguish:
    - startup / initialization in progress
    - integration running
    - completed or idle-with-no-logs
    """
    if not stdout_log.exists():
        return {
            "phase": "idle",
            "message": "Waiting for runner output...",
            "integration_started": False,
            "startup_in_progress": False,
            "latest_milestone": "",
            "latest_progress": "",
            "startup_progress_fraction": 0.0,
            "startup_milestones_completed": [],
            "startup_recent_lines": [],
        }
    try:
        lines = stdout_log.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return {
            "phase": "unknown",
            "message": "Unable to read runner output.",
            "integration_started": False,
            "startup_in_progress": False,
            "latest_milestone": "",
            "latest_progress": "",
            "startup_progress_fraction": 0.0,
            "startup_milestones_completed": [],
            "startup_recent_lines": [],
        }
    lines = [str(x).strip() for x in lines if str(x).strip()]
    if not lines:
        return {
            "phase": "startup",
            "message": "Startup in progress. Waiting for initialization logs...",
            "integration_started": False,
            "startup_in_progress": True,
            "latest_milestone": "",
            "latest_progress": "",
            "startup_progress_fraction": 0.0,
            "startup_milestones_completed": [],
            "startup_recent_lines": [],
        }

    progress_lines = [ln for ln in lines if ln.startswith("[Progress]")]
    milestone_lines = [ln for ln in lines if ln.startswith("[Milestone]")]
    init_lines = [ln for ln in lines if ln.startswith("[Init]")]
    startup_recent_lines = [ln for ln in lines if ln.startswith("[Milestone]") or ln.startswith("[Init]")]
    startup_recent_lines = startup_recent_lines[-8:]

    latest_progress = progress_lines[-1] if progress_lines else ""
    latest_milestone = (milestone_lines[-1] if milestone_lines else (init_lines[-1] if init_lines else ""))
    milestone_labels = []
    for ln in milestone_lines:
        text = re.sub(r"^\[Milestone\]\s*", "", ln).strip()
        text = re.sub(r"\s+wall=.*$", "", text).strip()
        milestone_labels.append(text)
    milestones_completed = []
    seen = set()
    for label in STARTUP_MILESTONE_ORDER:
        if label in milestone_labels and label not in seen:
            milestones_completed.append(label)
            seen.add(label)
    progress_fraction = 0.0
    if STARTUP_MILESTONE_ORDER:
        progress_fraction = min(len(milestones_completed) / float(len(STARTUP_MILESTONE_ORDER)), 1.0)

    if progress_lines:
        step_match = re.search(r"step=\s*(\d+)", latest_progress)
        sim_match = re.search(r"sim_t=\s*([0-9.+-]+)", latest_progress)
        step_txt = step_match.group(1) if step_match else "?"
        sim_txt = sim_match.group(1) if sim_match else "?"
        return {
            "phase": "integration",
            "message": f"Integration running. Latest logged step {step_txt} at sim_t={sim_txt} s.",
            "integration_started": True,
            "startup_in_progress": False,
            "latest_milestone": latest_milestone,
            "latest_progress": latest_progress,
            "startup_progress_fraction": 1.0,
            "startup_milestones_completed": milestones_completed,
            "startup_recent_lines": startup_recent_lines,
        }

    if milestone_lines or init_lines:
        stage_txt = latest_milestone or "startup initialization"
        return {
            "phase": "startup",
            "message": f"Startup in progress. Latest step: {stage_txt}",
            "integration_started": False,
            "startup_in_progress": True,
            "latest_milestone": latest_milestone,
            "latest_progress": "",
            "startup_progress_fraction": progress_fraction,
            "startup_milestones_completed": milestones_completed,
            "startup_recent_lines": startup_recent_lines,
        }

    return {
        "phase": "unknown",
        "message": "Runner output detected, but phase could not be identified yet.",
        "integration_started": False,
        "startup_in_progress": False,
        "latest_milestone": "",
        "latest_progress": "",
        "startup_progress_fraction": 0.0,
        "startup_milestones_completed": [],
        "startup_recent_lines": [],
    }


def load_column_overview(excel_path: Path) -> Dict[str, Any]:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)
    streams = dict(getattr(col, "streams", {}) or {})
    case_streams = dict(getattr(case, "streams", {}) or {})
    feed_stage = None
    if "Feed" in streams:
        try:
            feed_stage = int(getattr(streams["Feed"], "stage_1based", None) or 0)
        except Exception:
            feed_stage = None
    feed_stream_raw = dict(case_streams.get("Feed", {}) or {})
    x0 = np.asarray(getattr(col, "x0", []), dtype=float)
    y0 = np.asarray(getattr(col, "y0", []), dtype=float)
    top_liq_comp = _as_list(x0[0, :]) if x0.ndim == 2 and x0.shape[0] > 0 else []
    bot_liq_comp = _as_list(x0[-1, :]) if x0.ndim == 2 and x0.shape[0] > 0 else []
    top_vap_comp = _as_list(y0[0, :]) if y0.ndim == 2 and y0.shape[0] > 0 else []
    bot_vap_comp = _as_list(y0[-1, :]) if y0.ndim == 2 and y0.shape[0] > 0 else []
    specs_raw = dict(getattr(col, "specs_raw", {}) or {})
    top_total_volume_ft3 = getattr(col, "top_drum_total_volume_ft3", None)
    bottom_total_volume_ft3 = getattr(col, "bottom_sump_total_volume_ft3", None)
    if top_total_volume_ft3 is None:
        try:
            d_ft = float(specs_raw.get("Top Drum Diameter (ft)"))
            l_ft = float(specs_raw.get("Top Drum Length (ft)"))
            if np.isfinite(d_ft) and d_ft > 0.0 and np.isfinite(l_ft) and l_ft > 0.0:
                top_total_volume_ft3 = float(np.pi * 0.25 * d_ft * d_ft * l_ft)
        except Exception:
            top_total_volume_ft3 = None
    if bottom_total_volume_ft3 is None:
        try:
            d_ft = float(specs_raw.get("Bottom Sump Diameter (ft)"))
            h_ft = float(specs_raw.get("Bottom Sump Height (ft)"))
            if np.isfinite(d_ft) and d_ft > 0.0 and np.isfinite(h_ft) and h_ft > 0.0:
                bottom_total_volume_ft3 = float(np.pi * 0.25 * d_ft * d_ft * h_ft)
        except Exception:
            bottom_total_volume_ft3 = None
    return {
        "n_stages": int(col.n_stages),
        "n_components": int(col.n_components),
        "component_names": _as_list(getattr(col, "component_names", [])),
        "specs_raw": specs_raw,
        "feed_stage_1based": feed_stage,
        "feed_stream": {
            "stage_1based": feed_stream_raw.get("Stage"),
            "pressure_psia": feed_stream_raw.get("Pressure (psia)"),
            "temperature_F": feed_stream_raw.get("Temperature (F)"),
            "flow_lbmolph": feed_stream_raw.get("Total molar flow (lbmol/h)"),
        },
        "top_total_volume_ft3": top_total_volume_ft3,
        "bottom_total_volume_ft3": bottom_total_volume_ft3,
        "pressure_profile_psia": _as_list(getattr(col, "P_psia", [])),
        "initial_temperature_profile_F": _as_list(getattr(col, "T_f", [])),
        "initial_liquid_flow_profile_lbmolph": _as_list(getattr(col, "L_lbmolph", [])),
        "initial_vapor_flow_profile_lbmolph": _as_list(getattr(col, "V_lbmolph", [])),
        "initial_top_pressure_psia": float(np.asarray(getattr(col, "P_psia", [np.nan]), dtype=float).reshape((-1,))[0]),
        "initial_bottom_pressure_psia": float(np.asarray(getattr(col, "P_psia", [np.nan]), dtype=float).reshape((-1,))[-1]),
        "initial_top_temperature_F": float(np.asarray(getattr(col, "T_f", [np.nan]), dtype=float).reshape((-1,))[0]),
        "initial_bottom_temperature_F": float(np.asarray(getattr(col, "T_f", [np.nan]), dtype=float).reshape((-1,))[-1]),
        "initial_top_liquid_comp": top_liq_comp,
        "initial_bottom_liquid_comp": bot_liq_comp,
        "initial_top_vapor_comp": top_vap_comp,
        "initial_bottom_vapor_comp": bot_vap_comp,
        "initial_condenser_duty_btuph": getattr(getattr(col, "duties", None), "q_cond_btu_per_h", None),
        "initial_reboiler_duty_btuph": getattr(getattr(col, "duties", None), "q_reb_btu_per_h", None),
        "top_level_pv_mode": str(specs_raw.get("Top Level PV Mode") or "").strip().lower(),
        "bottom_level_pv_mode": str(specs_raw.get("Bottom Level PV Mode") or "").strip().lower(),
        "initial_top_level_frac": specs_raw.get("Top Drum Liquid Fraction (-)"),
        "initial_bottom_level_frac": specs_raw.get("Bottom Sump Liquid Fraction (-)"),
    }


def validate_excel_input(excel_path: Path) -> Dict[str, Any]:
    try:
        case = load_case_from_excel(excel_path)
    except Exception as exc:
        return {
            "ok": False,
            "errors": [f"Excel load failed: {exc}"],
            "warnings": [],
        }
    try:
        col = build_column_spec_from_case(case)
    except Exception as exc:
        return {
            "ok": False,
            "errors": [f"Column build failed: {exc}"],
            "warnings": [],
        }
    try:
        report = validate_loaded_case(case, col)
    except Exception as exc:
        return {
            "ok": False,
            "errors": [f"Validation failed unexpectedly: {exc}"],
            "warnings": [],
        }
    return {
        "ok": bool(report.ok),
        "errors": list(report.errors),
        "warnings": list(report.warnings),
    }


def compact_stage_table(
    snapshot: pd.DataFrame,
    *,
    component_names: List[str],
    pressure_profile_psia: Optional[List[Any]] = None,
) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame()
    cols = [
        "stage",
        "T_F",
        "P_psia_hyd",
        "ML_lbmol",
        "MV_lbmol",
        "L_out_used_lbmolph",
        "V_out_lbmolph",
    ]
    for comp in component_names:
        cols.extend([f"x_{comp}", f"y_{comp}"])
    keep = [c for c in cols if c in snapshot.columns]
    out = snapshot[keep].copy()
    if "P_psia_hyd" in out.columns and pressure_profile_psia:
        prof = list(pressure_profile_psia)
        if prof:
            def _fallback_pressure(row: pd.Series) -> Any:
                val = row.get("P_psia_hyd")
                try:
                    if pd.notna(val):
                        return val
                except Exception:
                    pass
                try:
                    idx = int(row.get("stage", 0)) - 1
                except Exception:
                    return val
                if 0 <= idx < len(prof):
                    return prof[idx]
                return val
            out["P_psia_hyd"] = out.apply(_fallback_pressure, axis=1)
    rename = {
        "P_psia_hyd": "P_psia",
        "L_out_used_lbmolph": "L_out_lbmolph",
    }
    return out.rename(columns=rename)
