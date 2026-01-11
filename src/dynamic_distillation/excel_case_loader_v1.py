# excel_case_loader_v1.py
# Last updated: 2026-01-11 15:xx ET
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


@dataclass(frozen=True)
class CaseData:
    excel_path: str
    components: List[str]               # names as entered in Excel
    component_ids_dwsim: List[str]      # canonical names used by thermo/flash
    specs: Dict[str, Any]
    initial_conditions: pd.DataFrame
    streams: Dict[str, Dict[str, Any]]


def _norm_str(x: Any) -> str:
    return str(x).strip() if x is not None else ""


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
        # maybe a single column of names
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
    Streams sheet (header=None) layout (your template):
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
        if not label or label.lower().startswith("mole flows"):
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

            # Allow either explicit component columns or "Component Mole Flow i" naming
            if comp in component_names:
                comp_key = comp
            else:
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

    # Specs (you can add more later; keep what you need now)
    specs: Dict[str, Any] = {}
    specs["Number of Stages"] = _get_required_int(specs_df, "Number of Stages")
    specs["Number of Components"] = _get_required_int(specs_df, "Number of Components")
    specs["Condenser Type"] = _get_optional_str(specs_df, "Condenser Type")
    specs["Condenser Duty (Btu/h)"] = _get_optional_float(specs_df, "Condenser Duty (Btu/h)")
    specs["Reboiler Duty (Btu/h)"] = _get_optional_float(specs_df, "Reboiler Duty (Btu/h)")
    specs["Simulation Length (min)"] = _get_optional_float(specs_df, "Simulation Length (min)")
    specs["Timestep (sec)"] = _get_optional_float(specs_df, "Timestep (sec)")
    specs["Log Frequency (timesteps)"] = _get_required_int(specs_df, "Log Frequency (timesteps)")

    # Components (prefer Components sheet)
    comp_names = _try_read_components_sheet(p)
    if not comp_names:
        comp_names = _get_component_names_from_specs(specs_df)

    if len(comp_names) != specs["Number of Components"]:
        raise ValueError(
            f"Specifications: expected {specs['Number of Components']} components, found {len(comp_names)}: {comp_names}"
        )

    # NEW: canonicalize and validate against DWSIM compound database (fail fast)
    component_ids_dwsim = canonicalize_components(comp_names)

    # Validate Initial Conditions minimum columns
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

    # Validate composition columns exist
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