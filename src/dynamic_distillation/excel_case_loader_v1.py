"""
excel_case_loader_v1.py

Dynamic Distillation - Excel Case Loader

PURPOSE
-------
Load workbook input data into immutable CaseData for downstream model build.
Parses recognized specification keys, initial-condition profiles, optional
components sheet, optional stream data, and optional geometry sections.

INPUTS
------
load_case_from_excel(excel_path):
- Excel `.xlsx` path (or file-picker selection when path omitted)
- Expected workbook structure:
  - required sheets: Specifications, Initial Conditions
  - optional sheets: Components, Streams

OUTPUTS
-------
CaseData dataclass:
- excel_path
- components (Excel labels)
- component_ids_dwsim (canonicalized IDs)
- specs (recognized spec keys)
- initial_conditions DataFrame
- streams dict (best-effort parse)

KEY DEPENDENCIES
----------------
- pandas/openpyxl
- compound_registry_v1.canonicalize_components

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Loader keeps recognized specification keys; free-form rows are not preserved.
- Streams parsing is best-effort and may return empty dict on malformed input.
- Component count and required IC columns are validated during load.

NOTES
-----
- Geometry section parsing supports diameter/spacing plus optional weir/active-area fields.
- Reflux-drum geometry aliases are normalized into canonical spec keys.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from dynamic_distillation.compound_registry_v1 import canonicalize_components

__all__ = ["CaseData", "pick_excel_file", "load_case_from_excel"]


@dataclass(frozen=True)
class CaseData:
    excel_path: str
    components: List[str]               # names as entered in Excel
    component_ids_dwsim: List[str]      # canonical names used by thermo/flash
    specs: Dict[str, Any]
    initial_conditions: pd.DataFrame
    boundary_state: Dict[str, List[float]]
    energy_state: Dict[str, List[float]]
    controller_state: Dict[str, float]
    memory_state: Dict[str, List[float]] = field(default_factory=dict)
    streams: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _norm_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    return str(x).strip()


def _norm_spec_label(x: Any) -> str:
    """Normalize spec labels for tolerant matching: trim and collapse whitespace."""
    return " ".join(_norm_str(x).split()).lower()


def _get_spec_value(specs_df: pd.DataFrame, label: str) -> Optional[Any]:
    """
    Specs sheet is read with header=None.
    We expect label in column 0, value in column 1 (but tolerate extra columns).
    """
    target = _norm_spec_label(label)
    for i in range(len(specs_df)):
        k = _norm_spec_label(specs_df.iloc[i, 0])
        if k == target:
            # choose last non-empty value across columns 1..end
            last = None
            for j in range(1, specs_df.shape[1]):
                v = specs_df.iloc[i, j]
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                s = _norm_str(v)
                if s:
                    last = v
            return last
    return None


def _get_required_int(specs_df: pd.DataFrame, label: str) -> int:
    v = _get_spec_value(specs_df, label)
    if v is None or (isinstance(v, str) and not v.strip()):
        raise ValueError(f"Specifications: missing required '{label}'")
    try:
        return int(float(v))
    except Exception as exc:
        raise ValueError(f"Specifications: '{label}' must be an integer") from exc


def _get_optional_float(specs_df: pd.DataFrame, label: str) -> Optional[float]:
    v = _get_spec_value(specs_df, label)
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _get_optional_str(specs_df: pd.DataFrame, label: str) -> Optional[str]:
    v = _get_spec_value(specs_df, label)
    s = _norm_str(v)
    return s if s else None


def _get_optional_bool(specs_df: pd.DataFrame, label: str) -> Optional[bool]:
    v = _get_spec_value(specs_df, label)
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    s = _norm_str(v).strip().lower()
    if not s:
        return None
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return None


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


def _try_read_boundary_state_sheet(p: Path, comp_names: List[str]) -> Dict[str, List[float]]:
    """Parse optional Boundary State sheet for restart holdups."""
    try:
        df = pd.read_excel(p, sheet_name="Boundary State")
    except Exception:
        return {}
    if df is None or df.empty:
        return {}

    nc = int(len(comp_names))
    if nc <= 0:
        return {}

    def _norm_token(s: Any) -> str:
        return "".join(ch for ch in _norm_str(s).lower() if ch.isalnum())

    state_col = None
    for c in df.columns:
        if _norm_token(c) in {"state", "boundary", "boundarystate"}:
            state_col = c
            break
    if state_col is None:
        state_col = df.columns[0]

    norm_cols = {_norm_token(c): c for c in df.columns}
    comp_cols: List[str] = []
    non_state_cols = [c for c in df.columns if c != state_col]
    for i, comp_name in enumerate(comp_names, start=1):
        found = None
        for cand in (f"Component {i}", f"Comp {i}", str(comp_name)):
            key = _norm_token(cand)
            if key in norm_cols:
                found = norm_cols[key]
                break
        if found is None:
            if len(non_state_cols) >= nc:
                comp_cols = list(non_state_cols[:nc])
                break
            return {}
        comp_cols.append(found)
    if len(comp_cols) != nc:
        return {}

    aliases = {
        "topl": "top_L",
        "topliquid": "top_L",
        "topliquidholdup": "top_L",
        "topdrumliquid": "top_L",
        "topv": "top_V",
        "topvapor": "top_V",
        "topvapour": "top_V",
        "topvaporholdup": "top_V",
        "bottoml": "bottom_L",
        "bottomliquid": "bottom_L",
        "bottomsliquid": "bottom_L",
        "sumpliquid": "bottom_L",
        "bottomv": "bottom_V",
        "bottomvapor": "bottom_V",
        "bottomvapour": "bottom_V",
        "sumpvapor": "bottom_V",
    }

    out: Dict[str, List[float]] = {}
    for _, row in df.iterrows():
        label = aliases.get(_norm_token(row.get(state_col)))
        if label is None:
            continue
        vals: List[float] = []
        ok = True
        for c in comp_cols:
            try:
                fv = float(row.get(c))
            except Exception:
                ok = False
                break
            if not pd.notna(fv):
                ok = False
                break
            vals.append(fv)
        if ok and len(vals) == nc:
            out[label] = vals
    return out


def _try_read_energy_state_sheet(p: Path, n_stages: int) -> Dict[str, List[float]]:
    """Parse optional Energy State sheet for tray EL/EV restart values."""
    try:
        df = pd.read_excel(p, sheet_name="Energy State")
    except Exception:
        return {}
    if df is None or df.empty or n_stages <= 0:
        return {}

    def _norm_token(s: Any) -> str:
        return "".join(ch for ch in _norm_str(s).lower() if ch.isalnum())

    norm_cols = {_norm_token(c): c for c in df.columns}
    stage_col = None
    for key in ("stage", "tray", "stage1based"):
        if key in norm_cols:
            stage_col = norm_cols[key]
            break
    if stage_col is None:
        return {}

    def _find_col(*candidates: str) -> Optional[str]:
        for cand in candidates:
            key = _norm_token(cand)
            if key in norm_cols:
                return norm_cols[key]
        return None

    col_el = _find_col("Tray EL (BTU)", "EL (BTU)", "tray_EL_BTU")
    col_ev = _find_col("Tray EV (BTU)", "EV (BTU)", "tray_EV_BTU")
    out: Dict[str, List[float]] = {}

    if col_el is not None:
        arr = [np.nan] * int(n_stages)
        for _, row in df.iterrows():
            try:
                i = int(float(row.get(stage_col))) - 1
                v = float(row.get(col_el))
            except Exception:
                continue
            if 0 <= i < n_stages and pd.notna(v):
                arr[i] = v
        if all(np.isfinite(arr)):
            out["tray_EL_BTU"] = [float(v) for v in arr]

    if col_ev is not None:
        arr = [np.nan] * int(n_stages)
        for _, row in df.iterrows():
            try:
                i = int(float(row.get(stage_col))) - 1
                v = float(row.get(col_ev))
            except Exception:
                continue
            if 0 <= i < n_stages and pd.notna(v):
                arr[i] = v
        if all(np.isfinite(arr)):
            out["tray_EV_BTU"] = [float(v) for v in arr]

    return out


def _try_read_controller_state_sheet(p: Path) -> Dict[str, float]:
    """Parse optional Controller State sheet for PI-memory restart values."""
    try:
        df = pd.read_excel(p, sheet_name="Controller State")
    except Exception:
        return {}
    if df is None or df.empty:
        return {}

    def _norm_token(s: Any) -> str:
        return "".join(ch for ch in _norm_str(s).lower() if ch.isalnum())

    norm_cols = {_norm_token(c): c for c in df.columns}
    ctrl_col = None
    value_col = None
    for key in ("controller", "state", "tag", "name"):
        if key in norm_cols:
            ctrl_col = norm_cols[key]
            break
    for key in ("value", "integral", "integ", "statevalue"):
        if key in norm_cols:
            value_col = norm_cols[key]
            break
    if ctrl_col is None or value_col is None:
        return {}

    aliases = {
        "toplevelinteg": "top_level_integ",
        "toplevelcontrollerinteg": "top_level_integ",
        "bottomlevelinteg": "bottom_level_integ",
        "bottomlevelcontrollerinteg": "bottom_level_integ",
        "toppressureinteg": "top_pressure_integ",
        "toppressurecontrollerinteg": "top_pressure_integ",
        "toppressurepvfiltpsia": "top_pressure_pv_filt_psia",
        "toppressuremvcmdbtuph": "top_pressure_mv_cmd_btuph",
        "toppressuremvcmdbtuperh": "top_pressure_mv_cmd_btuph",
        "toppressureresidabsbtups": "top_pressure_resid_abs_btups",
        "toppressureenergyresidabsbtups": "top_pressure_resid_abs_btups",
        "topdrumpressuretprevf": "top_drum_pressure_T_prev_F",
        "distillatecmdlbmolph": "distillate_cmd_lbmolph",
        "bottomscmdlbmolph": "bottoms_cmd_lbmolph",
        "refluxcmdlbmolph": "reflux_cmd_lbmolph",
        "boilupcmdlbmolph": "boilup_cmd_lbmolph",
        "distillatecompinteg": "distillate_comp_integ",
        "distillatecompositioninteg": "distillate_comp_integ",
        "bottomscompinteg": "bottoms_comp_integ",
        "bottomscompositioninteg": "bottoms_comp_integ",
    }

    out: Dict[str, float] = {}
    for _, row in df.iterrows():
        key = aliases.get(_norm_token(row.get(ctrl_col)))
        if key is None:
            continue
        try:
            val = float(row.get(value_col))
        except Exception:
            continue
        if np.isfinite(val):
            out[key] = float(val)
    return out


def _try_read_dynamic_memory_sheet(p: Path, n_stages: int) -> Dict[str, List[float]]:
    """Parse optional Dynamic Memory sheet for previous tray T/P profiles."""
    try:
        df = pd.read_excel(p, sheet_name="Dynamic Memory")
    except Exception:
        return {}
    if df is None or df.empty or n_stages <= 0:
        return {}

    def _norm_token(s: Any) -> str:
        return "".join(ch for ch in _norm_str(s).lower() if ch.isalnum())

    norm_cols = {_norm_token(c): c for c in df.columns}
    stage_col = None
    for key in ("stage", "tray", "stage1based"):
        if key in norm_cols:
            stage_col = norm_cols[key]
            break
    if stage_col is None:
        return {}

    def _find_col(*candidates: str) -> Optional[str]:
        for cand in candidates:
            key = _norm_token(cand)
            if key in norm_cols:
                return norm_cols[key]
        return None

    col_p = _find_col("Prev Tray Pressure (psia)", "P_tray_prev_psia", "Prev Pressure (psia)")
    col_t = _find_col("Prev Tray Temperature (F)", "T_tray_prev_F", "Prev Temperature (F)")

    out: Dict[str, List[float]] = {}
    if col_p is not None:
        arr = [np.nan] * int(n_stages)
        for _, row in df.iterrows():
            try:
                i = int(float(row.get(stage_col))) - 1
                v = float(row.get(col_p))
            except Exception:
                continue
            if 0 <= i < n_stages and pd.notna(v):
                arr[i] = v
        if all(np.isfinite(arr)):
            out["P_tray_prev_psia"] = [float(v) for v in arr]
    if col_t is not None:
        arr = [np.nan] * int(n_stages)
        for _, row in df.iterrows():
            try:
                i = int(float(row.get(stage_col))) - 1
                v = float(row.get(col_t))
            except Exception:
                continue
            if 0 <= i < n_stages and pd.notna(v):
                arr[i] = v
        if all(np.isfinite(arr)):
            out["T_tray_prev_F"] = [float(v) for v in arr]
    return out


def _read_stage_geometry_sections(specs_df: pd.DataFrame) -> Optional[List[Dict[str, Any]]]:
    """Parse optional stage geometry table from the Specifications sheet.

    Expected headers (case-insensitive; can be offset by a label in col 0):
      Start Stage | End Stage | Diameter (ft) | Tray Spacing (ft) | Gas Void Fraction

    Rows below the header are read until 'Start Stage' is blank.

    Returns a list of dicts or None if the table is not found.
    """
    n_rows = len(specs_df)
    n_cols = specs_df.shape[1]

    def cell(r: int, c: int) -> str:
        try:
            return _norm_str(specs_df.iloc[r, c])
        except Exception:
            return ""

    def has_tokens(s: str, *tokens: str) -> bool:
        ss = s.strip().lower()
        return all(tok in ss for tok in tokens)

    header_row = None
    col_start = col_end = col_diam = col_space = col_void = None
    col_weir_h = col_weir_L = col_active = col_sys = None

    # Find header row containing both "Start Stage" and "End Stage"
    for r in range(n_rows):
        start_c = None
        end_c = None
        for c in range(min(n_cols, 60)):
            s = cell(r, c)
            if start_c is None and has_tokens(s, "start", "stage"):
                start_c = c
            if end_c is None and has_tokens(s, "end", "stage"):
                end_c = c
        if start_c is not None and end_c is not None:
            header_row = r
            col_start, col_end = start_c, end_c
            for c in range(min(n_cols, 60)):
                h = cell(r, c).lower()
                if col_diam is None and "diam" in h:
                    col_diam = c
                if col_space is None and "spacing" in h:
                    col_space = c
                if col_void is None and ("void" in h or ("gas" in h and "frac" in h)):
                    col_void = c
                if col_weir_h is None and "weir" in h and "height" in h:
                    col_weir_h = c
                if col_weir_L is None and "weir" in h and "length" in h:
                    col_weir_L = c
                if col_active is None and "active" in h and "area" in h:
                    col_active = c
                if col_sys is None and (
                    ("system" in h and "factor" in h)
                    or ("hydraulic" in h and "factor" in h)
                ):
                    col_sys = c
            break

    if header_row is None or col_diam is None or col_space is None:
        return None

    sections: List[Dict[str, Any]] = []
    for r in range(header_row + 1, n_rows):
        v_start = specs_df.iloc[r, col_start]
        if v_start is None or (isinstance(v_start, float) and pd.isna(v_start)) or (
            isinstance(v_start, str) and not v_start.strip()
        ):
            break

        v_end = specs_df.iloc[r, col_end]
        v_d = specs_df.iloc[r, col_diam]
        v_s = specs_df.iloc[r, col_space]
        v_v = specs_df.iloc[r, col_void] if col_void is not None else None
        v_wh = specs_df.iloc[r, col_weir_h] if col_weir_h is not None else None
        v_wl = specs_df.iloc[r, col_weir_L] if col_weir_L is not None else None
        v_aa = specs_df.iloc[r, col_active] if col_active is not None else None
        v_cf = specs_df.iloc[r, col_sys] if col_sys is not None else None

        try:
            start_stage = int(float(v_start))
            end_stage = int(float(v_end))
            diameter_ft = float(v_d)
            tray_spacing_ft = float(v_s)
            gas_void = 1.0
            if v_v is not None and not (isinstance(v_v, float) and pd.isna(v_v)) and not (
                isinstance(v_v, str) and not v_v.strip()
            ):
                gas_void = _coerce_void_fraction(float(v_v))
            weir_height_in = None
            if v_wh is not None and not (isinstance(v_wh, float) and pd.isna(v_wh)) and not (
                isinstance(v_wh, str) and not v_wh.strip()
            ):
                weir_height_in = float(v_wh)
            weir_length_ft = None
            if v_wl is not None and not (isinstance(v_wl, float) and pd.isna(v_wl)) and not (
                isinstance(v_wl, str) and not v_wl.strip()
            ):
                weir_length_ft = float(v_wl)
            active_area_frac = None
            if v_aa is not None and not (isinstance(v_aa, float) and pd.isna(v_aa)) and not (
                isinstance(v_aa, str) and not v_aa.strip()
            ):
                active_area_frac = _coerce_void_fraction(float(v_aa))
            hydraulic_c_factor = None
            if v_cf is not None and not (isinstance(v_cf, float) and pd.isna(v_cf)) and not (
                isinstance(v_cf, str) and not v_cf.strip()
            ):
                hydraulic_c_factor = float(v_cf)
        except Exception:
            break

        sections.append(
            {
                "start_stage_1based": start_stage,
                "end_stage_1based": end_stage,
                "diameter_ft": diameter_ft,
                "tray_spacing_ft": tray_spacing_ft,
                "gas_void_frac": gas_void,
                "weir_height_in": weir_height_in,
                "weir_length_ft": weir_length_ft,
                "active_area_frac": active_area_frac,
                "hydraulic_c_factor": hydraulic_c_factor,
            }
        )

    return sections if sections else None


def _try_read_components_sheet(xls_path: Path) -> Optional[List[str]]:
    """Return list of component names from 'Components' sheet, or None if sheet missing."""
    try:
        comp_df = pd.read_excel(xls_path, sheet_name="Components", header=None)
    except Exception:
        return None

    # Find a header row containing "Component Name" or "Component"
    header_row = None
    for r in range(min(20, len(comp_df))):
        if _norm_str(comp_df.iloc[r, 0]).lower() in {"component name", "component"}:
            header_row = r
            break

    if header_row is None:
        vals = [_norm_str(comp_df.iloc[r, 0]) for r in range(len(comp_df))]
        vals = [v for v in vals if v]
        return vals if vals else None

    names: List[str] = []
    for r in range(header_row + 1, len(comp_df)):
        v = _norm_str(comp_df.iloc[r, 0])
        if v:
            names.append(v)

    return names if names else None


def _get_component_names_from_specs(specs_df: pd.DataFrame) -> List[str]:
    """Fallback: find the row labeled 'Component Name' and read across columns 1..end."""
    for i in range(len(specs_df)):
        if _norm_str(specs_df.iloc[i, 0]).lower() == "component name":
            names: List[str] = []
            for j in range(1, specs_df.shape[1]):
                v = specs_df.iloc[i, j]
                s = _norm_str(v)
                if s:
                    names.append(s)
            if not names:
                break
            return names
    raise ValueError("Specifications: could not find component names (no Components sheet and no 'Component Name' row).")


def _parse_streams_sheet(streams_df: pd.DataFrame, component_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Streams sheet (header=None) layout (template):
    - Find header row where first cell is 'Stream'
    - Parse scalar rows until 'Mole flows (lbmol/h)'
    - Parse component mole flow block
    """
    header_row = None
    for i in range(len(streams_df)):
        if _norm_str(streams_df.iloc[i, 0]).lower() == "stream":
            header_row = i
            break
    if header_row is None:
        raise ValueError("Streams sheet: could not find 'Stream' header row")

    stream_names = [_norm_str(streams_df.iloc[header_row, j]) for j in range(1, streams_df.shape[1])]
    col_map = {j: stream_names[j - 1] for j in range(1, streams_df.shape[1]) if stream_names[j - 1]}
    streams: Dict[str, Dict[str, Any]] = {name: {} for name in col_map.values()}

    def _row_label(i: int) -> str:
        return _norm_str(streams_df.iloc[i, 0])

    # Parse scalar rows
    for i in range(header_row + 1, len(streams_df)):
        label = _row_label(i)
        if not label:
            continue
        if label.lower().startswith("mole flows"):
            break
        if label.lower() in {
            "stage",
            "pressure (psia)",
            "vapour fraction",
            "temperature (f)",
            "total molar flow (lbmol/h)",
        }:
            for j, sname in col_map.items():
                v = streams_df.iloc[i, j]
                if v is None or pd.isna(v):
                    continue
                streams[sname][label] = int(float(v)) if label.lower() == "stage" else float(v)

    # Find "Mole flows (lbmol/h)" row
    mf_row = None
    for i in range(header_row + 1, len(streams_df)):
        if _row_label(i).lower() == "mole flows (lbmol/h)":
            mf_row = i
            break

    if mf_row is not None:
        comp_flows: Dict[str, Dict[str, float]] = {sname: {} for sname in streams.keys()}
        for i in range(mf_row + 1, len(streams_df)):
            comp = _row_label(i)
            if not comp or comp.lower() == "nan":
                continue

            comp_key = comp  # keep whatever Excel used in this sheet

            for j, sname in col_map.items():
                v = streams_df.iloc[i, j]
                if v is None or pd.isna(v):
                    continue
                comp_flows[sname][comp_key] = float(v)

        for sname in streams.keys():
            streams[sname]["Component Mole Flows (lbmol/h)"] = comp_flows[sname]

    return streams


def pick_excel_file(initial_dir: Optional[str] = None) -> str:
    """
    Windows file picker (tkinter).
    Returns selected path or raises RuntimeError if cancelled.
    """
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        initialdir=initial_dir or str(Path.cwd()),
        title="Select distillation case Excel file",
        filetypes=[("Excel files", "*.xlsx")],
    )

    root.destroy()

    if not file_path:
        raise RuntimeError("No Excel file selected.")
    return file_path


def load_case_from_excel(excel_path: Optional[str] = None) -> CaseData:
    """
    Load a case from Excel (.xlsx). If excel_path is None, pops a file picker.
    """
    if excel_path is None:
        excel_path = pick_excel_file()

    p = Path(excel_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Excel file not found: {p}")
    if p.suffix.lower() != ".xlsx":
        raise ValueError(f"Expected a .xlsx file, got: {p.name}")

    specs_df = pd.read_excel(p, sheet_name="Specifications", header=None)
    init_df = pd.read_excel(p, sheet_name="Initial Conditions")

    # Specs
    specs: Dict[str, Any] = {}

    def _first_optional_float(labels: list[str]) -> Optional[float]:
        for lab in labels:
            v = _get_optional_float(specs_df, lab)
            if v is not None:
                return v
        return None
    specs["Number of Stages"] = _get_required_int(specs_df, "Number of Stages")
    specs["Number of Components"] = _get_required_int(specs_df, "Number of Components")
    specs["Condenser Type"] = _get_optional_str(specs_df, "Condenser Type")
    specs["Condenser Duty Mode"] = _get_optional_str(specs_df, "Condenser Duty Mode")
    specs["Condenser Duty (Btu/h)"] = _get_optional_float(specs_df, "Condenser Duty (Btu/h)")
    specs["Reboiler Duty (Btu/h)"] = _get_optional_float(specs_df, "Reboiler Duty (Btu/h)")
    specs["Simulation Length (min)"] = _get_optional_float(specs_df, "Simulation Length (min)")
    specs["Timestep (sec)"] = _get_optional_float(specs_df, "Timestep (sec)")
    specs["Log Frequency (timesteps)"] = _get_required_int(specs_df, "Log Frequency (timesteps)")
    specs["Top Accumulator Holdup (lbmol)"] = _get_optional_float(specs_df, "Top Accumulator Holdup (lbmol)")
    specs["Bottom Holdup (lbmol)"] = _first_optional_float(
        [
            "Bottom Holdup (lbmol)",
            "Bottom Sump Holdup (lbmol)",
            "Bottom Level Holdup (lbmol)",
        ]
    )
    specs["Pressure Model"] = _get_optional_str(specs_df, "Pressure Model")
    specs["Vapor Flow Model"] = _get_optional_str(specs_df, "Vapor Flow Model")
    specs["Runtime Mode"] = _get_optional_str(specs_df, "Runtime Mode")
    specs["Thermo Mode"] = _get_optional_str(specs_df, "Thermo Mode")
    specs["Thermo Table"] = _get_optional_str(specs_df, "Thermo Table")
    specs["Include Energy"] = _get_optional_bool(specs_df, "Include Energy")

    # Optional reflux-drum geometry to infer top vapor-space volume.
    specs["Top Drum Vapor Volume (ft3)"] = _first_optional_float(
        [
            "Top Drum Vapor Volume (ft3)",
            "Top Accumulator Vapor Volume (ft3)",
            "Reflux Drum Vapor Volume (ft3)",
            "Distillate Drum Vapor Volume (ft3)",
            "Top Vapor Volume (ft3)",
        ]
    )
    specs["Top Drum Total Volume (ft3)"] = _first_optional_float(
        [
            "Top Drum Total Volume (ft3)",
            "Top Accumulator Total Volume (ft3)",
            "Reflux Drum Total Volume (ft3)",
            "Distillate Drum Total Volume (ft3)",
            "Top Drum Volume (ft3)",
            "Reflux Drum Volume (ft3)",
            "Distillate Drum Volume (ft3)",
        ]
    )
    specs["Top Drum Diameter (ft)"] = _first_optional_float(
        [
            "Top Drum Diameter (ft)",
            "Top Accumulator Diameter (ft)",
            "Reflux Drum Diameter (ft)",
            "Distillate Drum Diameter (ft)",
            "Top Drum ID (ft)",
            "Reflux Drum ID (ft)",
            "Distillate Drum ID (ft)",
        ]
    )
    specs["Top Drum Length (ft)"] = _first_optional_float(
        [
            "Top Drum Length (ft)",
            "Top Accumulator Length (ft)",
            "Reflux Drum Length (ft)",
            "Distillate Drum Length (ft)",
        ]
    )
    top_liq_frac = _first_optional_float(
        [
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
        ]
    )
    if top_liq_frac is not None and top_liq_frac > 1.0 and top_liq_frac <= 100.0:
        top_liq_frac = float(top_liq_frac) / 100.0
    if top_liq_frac is not None and (top_liq_frac < 0.0 or top_liq_frac > 1.0):
        top_liq_frac = None
    specs["Top Drum Liquid Fraction (-)"] = top_liq_frac
    # Optional overhead vapor-space adders used to augment top-end capacitance.
    specs["Overhead Vapor Line Volume (ft3)"] = _first_optional_float(
        [
            "Overhead Vapor Line Volume (ft3)",
            "Overhead Vapour Line Volume (ft3)",
            "Overhead Line Vapor Volume (ft3)",
            "Overhead Line Volume (ft3)",
        ]
    )
    specs["Condenser Vapor Volume (ft3)"] = _first_optional_float(
        [
            "Condenser Vapor Volume (ft3)",
            "Condenser Vapour Volume (ft3)",
            "Condenser Vapor Space (ft3)",
            "Condenser Vapour Space (ft3)",
        ]
    )
    # Optional bottom-sump geometry for true-level control.
    specs["Bottom Sump Total Volume (ft3)"] = _first_optional_float(
        [
            "Bottom Sump Total Volume (ft3)",
            "Bottom Sump Volume (ft3)",
            "Bottom Total Volume (ft3)",
            "Bottom Vessel Total Volume (ft3)",
            "Bottom Vessel Volume (ft3)",
            "Bottom Drum Total Volume (ft3)",
            "Bottom Drum Volume (ft3)",
        ]
    )
    specs["Bottom Sump Diameter (ft)"] = _first_optional_float(
        [
            "Bottom Sump Diameter (ft)",
            "Bottom Sump ID (ft)",
            "Bottom Vessel Diameter (ft)",
            "Bottom Vessel ID (ft)",
            "Bottom Drum Diameter (ft)",
            "Bottom Drum ID (ft)",
        ]
    )
    specs["Bottom Sump Height (ft)"] = _first_optional_float(
        [
            "Bottom Sump Height (ft)",
            "Bottom Sump height (ft)",
            "Bottom Sump Length (ft)",
            "Bottom Vessel Height (ft)",
            "Bottom Vessel Length (ft)",
            "Bottom Drum Height (ft)",
            "Bottom Drum Length (ft)",
        ]
    )
    bottom_liq_frac = _first_optional_float(
        [
            "Bottom Sump Liquid Volume Fraction",
            "Bottom Sump Liquid Fraction",
            "Bottom Sump Fill Fraction",
            "Bottom Liquid Volume Fraction",
            "Bottom Liquid Fraction",
            "Bottom Fill Fraction",
        ]
    )
    if bottom_liq_frac is not None and bottom_liq_frac > 1.0 and bottom_liq_frac <= 100.0:
        bottom_liq_frac = float(bottom_liq_frac) / 100.0
    if bottom_liq_frac is not None and (bottom_liq_frac < 0.0 or bottom_liq_frac > 1.0):
        bottom_liq_frac = None
    specs["Bottom Sump Liquid Fraction (-)"] = bottom_liq_frac

    # Module 8B: tau (optional)
    specs["Stage time constant [tau] (sec)"] = _get_optional_float(specs_df, "Stage time constant [tau] (sec)")
    specs["Dry Tray K"] = _get_optional_float(specs_df, "Dry Tray K")
    specs["Vapor Holdup Relaxation (sec)"] = _get_optional_float(specs_df, "Vapor Holdup Relaxation (sec)")
    specs["Vapor Flow Relaxation (sec)"] = _get_optional_float(specs_df, "Vapor Flow Relaxation (sec)")
    cond_dp = _get_optional_float(specs_df, "Condenser Pressure Drop (psi)")
    if cond_dp is None:
        cond_dp = _get_optional_float(specs_df, "Condenser Pressure Drop (psia)")
    specs["Condenser Pressure Drop (psi)"] = cond_dp
    reb_nbr_hi = _get_optional_float(specs_df, "Reboiler Neighbor Vapor Hi Ratio")
    if reb_nbr_hi is None:
        reb_nbr_hi = _get_optional_float(specs_df, "Reboiler Neighbor Vflow Hi Ratio")
    specs["Reboiler Neighbor Vapor Hi Ratio"] = reb_nbr_hi
    reb_nbr_lo = _get_optional_float(specs_df, "Reboiler Neighbor Vapor Lo Ratio")
    if reb_nbr_lo is None:
        reb_nbr_lo = _get_optional_float(specs_df, "Reboiler Neighbor Vflow Lo Ratio")
    specs["Reboiler Neighbor Vapor Lo Ratio"] = reb_nbr_lo
    thermo_refresh = _get_optional_float(specs_df, "Thermo Refresh dT (F)")
    if thermo_refresh is None:
        thermo_refresh = _get_optional_float(specs_df, "Thermo Refresh Delta T (F)")
    if thermo_refresh is None:
        thermo_refresh = _get_optional_float(specs_df, "Thermo Refresh Delta (F)")
    if thermo_refresh is None:
        thermo_refresh = _get_optional_float(specs_df, "Thermo Refresh \u0394T (F)")
    specs["Thermo Refresh dT (F)"] = thermo_refresh
    thermo_refresh_dp = _get_optional_float(specs_df, "Thermo Refresh dP (psia)")
    if thermo_refresh_dp is None:
        thermo_refresh_dp = _get_optional_float(specs_df, "Thermo Refresh Delta P (psia)")
    specs["Thermo Refresh dP (psia)"] = thermo_refresh_dp
    thermo_refresh_dx = _get_optional_float(specs_df, "Thermo Refresh dX")
    if thermo_refresh_dx is None:
        thermo_refresh_dx = _get_optional_float(specs_df, "Thermo Refresh Delta X")
    specs["Thermo Refresh dX"] = thermo_refresh_dx
    specs["Equilibrium Relaxation Mode"] = _get_optional_str(specs_df, "Equilibrium Relaxation Mode")
    specs["Equilibrium Tau (sec)"] = _get_optional_float(specs_df, "Equilibrium Tau (sec)")
    specs["Equilibrium Energy Damping Gain"] = _get_optional_float(specs_df, "Equilibrium Energy Damping Gain")
    specs["Equilibrium Relaxation Live PR"] = _get_optional_bool(specs_df, "Equilibrium Relaxation Live PR")
    specs["Hydraulic Energy Temperature Follow Tau (sec)"] = _get_optional_float(
        specs_df, "Hydraulic Energy Temperature Follow Tau (sec)"
    )
    specs["Enable Level Control"] = _get_optional_bool(specs_df, "Enable Level Control")
    specs["Top Level PV Mode"] = _get_optional_str(specs_df, "Top Level PV Mode")
    specs["Top Level SP Frac"] = _get_optional_float(specs_df, "Top Level SP Frac")
    specs["Top Level Kc"] = _get_optional_float(specs_df, "Top Level Kc")
    specs["Top Level Ti (sec)"] = _get_optional_float(specs_df, "Top Level Ti (sec)")
    specs["Bottom Level PV Mode"] = _get_optional_str(specs_df, "Bottom Level PV Mode")
    specs["Bottom Level SP (lbmol)"] = _get_optional_float(specs_df, "Bottom Level SP (lbmol)")
    specs["Bottom Level SP Frac"] = _get_optional_float(specs_df, "Bottom Level SP Frac")
    specs["Bottom Level Kc"] = _get_optional_float(specs_df, "Bottom Level Kc")
    specs["Bottom Level Ti (sec)"] = _get_optional_float(specs_df, "Bottom Level Ti (sec)")
    specs["Enable Pressure Control"] = _get_optional_bool(specs_df, "Enable Pressure Control")
    specs["Pressure Control MV"] = _get_optional_str(specs_df, "Pressure Control MV")
    specs["Top Pressure SP (psia)"] = _get_optional_float(specs_df, "Top Pressure SP (psia)")
    specs["Top Pressure Kc"] = _get_optional_float(specs_df, "Top Pressure Kc")
    specs["Top Pressure Ti (sec)"] = _get_optional_float(specs_df, "Top Pressure Ti (sec)")
    specs["Enable Distillate Composition Control"] = _get_optional_bool(
        specs_df, "Enable Distillate Composition Control"
    )
    specs["Distillate Composition Component"] = _get_optional_str(specs_df, "Distillate Composition Component")
    specs["Distillate Composition Kc"] = _get_optional_float(specs_df, "Distillate Composition Kc")
    specs["Distillate Composition Ti (sec)"] = _get_optional_float(specs_df, "Distillate Composition Ti (sec)")
    specs["Distillate Composition Reflux Min (lbmol/h)"] = _get_optional_float(
        specs_df, "Distillate Composition Reflux Min (lbmol/h)"
    )
    specs["Distillate Composition Reflux Max (lbmol/h)"] = _get_optional_float(
        specs_df, "Distillate Composition Reflux Max (lbmol/h)"
    )
    # Optional composition-control setpoints.
    # These keys are consumed by runner/controller wiring when CLI overrides
    # are not provided.
    dist_x_sp = _first_optional_float(
        [
            "Distillate Composition SP",
            "Distillate C4 SP",
            "Distillate x SP",
        ]
    )
    specs["Distillate Composition SP"] = dist_x_sp
    bot_x_sp = _first_optional_float(
        [
            "Bottoms Composition SP",
            "Bottoms C5 SP",
            "Bottoms x SP",
        ]
    )
    specs["Bottoms Composition SP"] = bot_x_sp

    # Geometry (optional): stage geometry sections for vapor volume estimation
    specs["Geometry Sections"] = _read_stage_geometry_sections(specs_df)

    # Components (prefer Components sheet)
    comp_names = _try_read_components_sheet(p)
    if not comp_names:
        comp_names = _get_component_names_from_specs(specs_df)

    if len(comp_names) != specs["Number of Components"]:
        raise ValueError(
            f"Specifications: expected {specs['Number of Components']} components, found {len(comp_names)}: {comp_names}"
        )

    component_ids_dwsim = canonicalize_components(comp_names)

    # Validate IC minimum columns
    required_cols = [
        "Stage",
        "Temperature (F)",
        "Pressure (psia)",
        "Vapor Flow (lbmol/h)",
        "Liquid Flow (lbmol/h)",
    ]
    for c in required_cols:
        if c not in init_df.columns:
            raise ValueError(f"Initial Conditions: missing required column '{c}'")

    # Validate composition columns exist (template convention)
    nc = len(comp_names)
    for i in range(1, nc + 1):
        lc = f"Liquid Composition Component {i}"
        vc = f"Vapor Composition Component {i}"
        if lc not in init_df.columns:
            raise ValueError(f"Initial Conditions: missing required column '{lc}'")
        if vc not in init_df.columns:
            raise ValueError(f"Initial Conditions: missing required column '{vc}'")

    # Streams (best effort)
    streams: Dict[str, Dict[str, Any]] = {}
    try:
        streams_df = pd.read_excel(p, sheet_name="Streams", header=None)
        streams = _parse_streams_sheet(streams_df, comp_names)
    except Exception:
        streams = {}
    boundary_state = _try_read_boundary_state_sheet(p, comp_names)
    energy_state = _try_read_energy_state_sheet(p, int(specs["Number of Stages"]))
    controller_state = _try_read_controller_state_sheet(p)
    memory_state = _try_read_dynamic_memory_sheet(p, int(specs["Number of Stages"]))

    return CaseData(
        excel_path=str(p),
        components=comp_names,
        component_ids_dwsim=component_ids_dwsim,
        specs=specs,
        initial_conditions=init_df,
        boundary_state=boundary_state,
        energy_state=energy_state,
        controller_state=controller_state,
        memory_state=memory_state,
        streams=streams,
    )
