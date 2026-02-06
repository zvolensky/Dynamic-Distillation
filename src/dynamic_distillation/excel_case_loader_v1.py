# excel_case_loader_v1.py
# Last updated: 2026-01-12 21:29 ET
#
# Responsibilities:
# - Load a distillation "case" from an Excel .xlsx file matching the provided template format
# - Provide a file-picker option (Windows-friendly)
# - Validate and canonicalize component names against DWSIM compound list (fail-fast)
#
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from dynamic_distillation.compound_registry_v1 import canonicalize_components

__all__ = ["CaseData", "pick_excel_file", "load_case_from_excel"]


@dataclass(frozen=True)
class CaseData:
    excel_path: str
    components: List[str]               # names as entered in Excel
    component_ids_dwsim: List[str]      # canonical names used by thermo/flash
    specs: Dict[str, Any]
    initial_conditions: pd.DataFrame
    streams: Dict[str, Dict[str, Any]]


def _norm_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    return str(x).strip()


def _get_spec_value(specs_df: pd.DataFrame, label: str) -> Optional[Any]:
    """
    Specs sheet is read with header=None.
    We expect label in column 0, value in column 1 (but tolerate extra columns).
    """
    target = label.strip().lower()
    for i in range(len(specs_df)):
        k = _norm_str(specs_df.iloc[i, 0]).lower()
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
        except Exception:
            break

        sections.append(
            {
                "start_stage_1based": start_stage,
                "end_stage_1based": end_stage,
                "diameter_ft": diameter_ft,
                "tray_spacing_ft": tray_spacing_ft,
                "gas_void_frac": gas_void,
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
    specs["Number of Stages"] = _get_required_int(specs_df, "Number of Stages")
    specs["Number of Components"] = _get_required_int(specs_df, "Number of Components")
    specs["Condenser Type"] = _get_optional_str(specs_df, "Condenser Type")
    specs["Condenser Duty (Btu/h)"] = _get_optional_float(specs_df, "Condenser Duty (Btu/h)")
    specs["Reboiler Duty (Btu/h)"] = _get_optional_float(specs_df, "Reboiler Duty (Btu/h)")
    specs["Simulation Length (min)"] = _get_optional_float(specs_df, "Simulation Length (min)")
    specs["Timestep (sec)"] = _get_optional_float(specs_df, "Timestep (sec)")
    specs["Log Frequency (timesteps)"] = _get_required_int(specs_df, "Log Frequency (timesteps)")
    specs["Top Accumulator Holdup (lbmol)"] = _get_optional_float(specs_df, "Top Accumulator Holdup (lbmol)")
    specs["Bottom Holdup (lbmol)"] = _get_optional_float(specs_df, "Bottom Holdup (lbmol)")

    # Module 8B: tau (optional)
    specs["Stage time constant [tau] (sec)"] = _get_optional_float(specs_df, "Stage time constant [tau] (sec)")

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

    return CaseData(
        excel_path=str(p),
        components=comp_names,
        component_ids_dwsim=component_ids_dwsim,
        specs=specs,
        initial_conditions=init_df,
        streams=streams,
    )
