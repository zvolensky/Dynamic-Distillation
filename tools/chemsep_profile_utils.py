#!/usr/bin/env python
"""
Utilities for parsing ChemSep result workbooks (.xls) used in reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import xlrd  # type: ignore
except Exception as exc:  # pragma: no cover - import guard
    xlrd = None
    _XLRD_IMPORT_ERROR = exc
else:
    _XLRD_IMPORT_ERROR = None


@dataclass(frozen=True)
class ChemSepTrayProfile:
    stage_1based: np.ndarray
    temperature_F: np.ndarray
    pressure_psia: np.ndarray
    liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    x_liq: np.ndarray
    y_vap: np.ndarray
    component_labels: List[str]


def _norm(s: object) -> str:
    txt = "" if s is None else str(s)
    return "".join(ch for ch in txt.strip().lower() if ch.isalnum())


def _to_float(v: object) -> Optional[float]:
    if isinstance(v, (int, float)):
        out = float(v)
        return out if np.isfinite(out) else None
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        out = float(s)
    except Exception:
        return None
    return out if np.isfinite(out) else None


def _to_int(v: object) -> Optional[int]:
    f = _to_float(v)
    if f is None:
        return None
    return int(round(f))


def _find_profile_header_row(sheet, start_col_1based: int = 2) -> Tuple[int, List[str]]:
    """
    Find the row that looks like:
      [blank, 'Stage', <comp1>, <comp2>, ...]
    Returns: (row_idx_0based, component_labels)
    """
    col0 = int(start_col_1based - 1)
    for r in range(sheet.nrows):
        st = _norm(sheet.cell_value(r, col0))
        if st != "stage":
            continue
        labels: List[str] = []
        c = col0 + 1
        while c < sheet.ncols:
            raw = sheet.cell_value(r, c)
            txt = "" if raw is None else str(raw).strip()
            if not txt:
                break
            labels.append(txt)
            c += 1
        if labels:
            return r, labels
    raise ValueError(f"Could not find Stage/component header row in sheet '{sheet.name}'")


def _parse_composition_profile_sheet(sheet) -> Tuple[np.ndarray, List[str], np.ndarray]:
    """
    Parse sheets like:
      - Liquid x composition profiles
      - Vapour y composition profiles

    Returns:
      stage_1based (N,)
      component_labels (Nc list)
      values (N,Nc)
    """
    hdr_row, comp_labels = _find_profile_header_row(sheet, start_col_1based=2)
    col_stage = 1  # 0-based
    col_first_comp = 2  # 0-based
    rows_stage: List[int] = []
    rows_vals: List[List[float]] = []
    started = False

    for r in range(hdr_row + 1, sheet.nrows):
        stage = _to_int(sheet.cell_value(r, col_stage))
        if stage is None:
            if started:
                break
            continue
        started = True
        vals: List[float] = []
        ok_row = True
        for j in range(len(comp_labels)):
            fv = _to_float(sheet.cell_value(r, col_first_comp + j))
            if fv is None:
                ok_row = False
                break
            vals.append(float(fv))
        if not ok_row:
            break
        rows_stage.append(int(stage))
        rows_vals.append(vals)

    if not rows_stage:
        raise ValueError(f"No stage rows parsed from composition sheet '{sheet.name}'")
    return np.asarray(rows_stage, dtype=int), list(comp_labels), np.asarray(rows_vals, dtype=float)


def _parse_tp_flow_sheet(sheet) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse first stage block from 'T_P_Flow profiles':
      [blank, stage, T, P, L, V, ...]
    """
    col_stage = 1
    col_t = 2
    col_p = 3
    col_l = 4
    col_v = 5

    stage: List[int] = []
    temp: List[float] = []
    pres: List[float] = []
    liq: List[float] = []
    vap: List[float] = []

    started = False
    prev_stage: Optional[int] = None
    for r in range(sheet.nrows):
        s = _to_int(sheet.cell_value(r, col_stage))
        t = _to_float(sheet.cell_value(r, col_t))
        p = _to_float(sheet.cell_value(r, col_p))
        if s is None or t is None or p is None:
            if started:
                # finish first contiguous stage table
                break
            continue

        if prev_stage is not None and int(s) <= int(prev_stage):
            # second table starts later with stage reset to 1
            break

        started = True
        prev_stage = int(s)
        stage.append(int(s))
        temp.append(float(t))
        pres.append(float(p))
        lv = _to_float(sheet.cell_value(r, col_l))
        vv = _to_float(sheet.cell_value(r, col_v))
        liq.append(np.nan if lv is None else float(lv))
        vap.append(np.nan if vv is None else float(vv))

    if not stage:
        raise ValueError(f"No stage profile rows parsed from sheet '{sheet.name}'")
    return (
        np.asarray(stage, dtype=int),
        np.asarray(temp, dtype=float),
        np.asarray(pres, dtype=float),
        np.asarray(liq, dtype=float),
        np.asarray(vap, dtype=float),
    )


def parse_chemsep_results_xls(path: str) -> ChemSepTrayProfile:
    if xlrd is None:
        raise RuntimeError(
            f"xlrd is required to parse '{path}' (.xls). Import error: {_XLRD_IMPORT_ERROR}"
        )

    wb = xlrd.open_workbook(path)
    sh_tp = wb.sheet_by_name("T_P_Flow profiles")
    sh_x = wb.sheet_by_name("Liquid x composition profiles")
    sh_y = wb.sheet_by_name("Vapour y composition profiles")

    st_tp, T_F, P_psia, L_lbmolph, V_lbmolph = _parse_tp_flow_sheet(sh_tp)
    st_x, comp_labels_x, x = _parse_composition_profile_sheet(sh_x)
    st_y, comp_labels_y, y = _parse_composition_profile_sheet(sh_y)

    if len(comp_labels_x) != len(comp_labels_y):
        raise ValueError(
            f"Component label mismatch between x/y sheets: {comp_labels_x} vs {comp_labels_y}"
        )
    for a, b in zip(comp_labels_x, comp_labels_y):
        if _norm(a) != _norm(b):
            raise ValueError(f"Component label mismatch between x/y sheets: '{a}' vs '{b}'")

    # Align stages to common intersection, preserving ascending stage order.
    set_tp = set(st_tp.tolist())
    set_x = set(st_x.tolist())
    set_y = set(st_y.tolist())
    common = sorted(set_tp.intersection(set_x).intersection(set_y))
    if not common:
        raise ValueError("No common stages across T/P, x, and y profiles")

    idx_tp = {int(s): i for i, s in enumerate(st_tp.tolist())}
    idx_x = {int(s): i for i, s in enumerate(st_x.tolist())}
    idx_y = {int(s): i for i, s in enumerate(st_y.tolist())}

    out_stage: List[int] = []
    out_T: List[float] = []
    out_P: List[float] = []
    out_L: List[float] = []
    out_V: List[float] = []
    out_x: List[np.ndarray] = []
    out_y: List[np.ndarray] = []

    for s in common:
        it = idx_tp[int(s)]
        ix = idx_x[int(s)]
        iy = idx_y[int(s)]
        out_stage.append(int(s))
        out_T.append(float(T_F[it]))
        out_P.append(float(P_psia[it]))
        out_L.append(float(L_lbmolph[it]))
        out_V.append(float(V_lbmolph[it]))
        out_x.append(np.asarray(x[ix, :], dtype=float))
        out_y.append(np.asarray(y[iy, :], dtype=float))

    return ChemSepTrayProfile(
        stage_1based=np.asarray(out_stage, dtype=int),
        temperature_F=np.asarray(out_T, dtype=float),
        pressure_psia=np.asarray(out_P, dtype=float),
        liquid_flow_lbmolph=np.asarray(out_L, dtype=float),
        vapor_flow_lbmolph=np.asarray(out_V, dtype=float),
        x_liq=np.vstack(out_x).astype(float),
        y_vap=np.vstack(out_y).astype(float),
        component_labels=list(comp_labels_x),
    )


_CHEMSEP_ALIAS_TO_DWSIM = {
    "c3h8": "Propane",
    "propane": "Propane",
    "npropane": "Propane",
    "c4h10": "N-butane",
    "nbutane": "N-butane",
    "butane": "N-butane",
    "c5h12": "N-pentane",
    "npentane": "N-pentane",
    "pentane": "N-pentane",
}


def canonicalize_chemsep_label_to_dwsim_id(label: str) -> str:
    from dynamic_distillation.compound_registry_v1 import canonicalize_to_dwsim_id

    key = _norm(label)
    if key in _CHEMSEP_ALIAS_TO_DWSIM:
        return canonicalize_to_dwsim_id(_CHEMSEP_ALIAS_TO_DWSIM[key])
    return canonicalize_to_dwsim_id(label)


def build_case_component_index_from_chemsep_labels(
    *,
    chemsep_component_labels: Sequence[str],
    case_components_dwsim: Sequence[str],
) -> List[int]:
    """
    Returns list of length Nc_case where each element is the source ChemSep
    component column index to use for that case component.
    """
    from dynamic_distillation.compound_registry_v1 import canonicalize_to_dwsim_id

    chem_ids = [canonicalize_chemsep_label_to_dwsim_id(v) for v in chemsep_component_labels]
    case_ids = [canonicalize_to_dwsim_id(v) for v in case_components_dwsim]

    out: List[int] = []
    for cid in case_ids:
        if cid not in chem_ids:
            raise ValueError(
                f"ChemSep components {chemsep_component_labels} do not include required case component '{cid}'"
            )
        out.append(int(chem_ids.index(cid)))
    return out


def reorder_profile_components_to_case_order(
    *,
    arr_stage_by_comp: np.ndarray,
    case_from_chemsep_index: Sequence[int],
) -> np.ndarray:
    arr = np.asarray(arr_stage_by_comp, dtype=float)
    idx = np.asarray(case_from_chemsep_index, dtype=int).reshape((-1,))
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D array [stage,comp], got shape {arr.shape}")
    return arr[:, idx]


def normalize_rows(arr: np.ndarray, eps: float = 1e-300) -> np.ndarray:
    a = np.asarray(arr, dtype=float).copy()
    rs = np.sum(a, axis=1, keepdims=True)
    rs = np.where(np.isfinite(rs) & (rs > eps), rs, 1.0)
    return a / rs
