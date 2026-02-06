#!/usr/bin/env python3
"""
thermo_bridge.py (plain text protocol)
Generated: 2026-01-19 (America/New_York)

Usage:
  python thermo_bridge.py thermo_request.txt thermo_response.txt

Request format (lines):
  EXCEL_PATH=...
  N=...
  NC=...
  T_F=comma,separated,list
  P_PSIA=comma,separated,list
  ZROW=comma,separated,list   (repeated N times)

Response format (lines):
  COMPONENTS_EXCEL=...
  COMPONENT_IDS_DWSIM=...
  HL=...
  HV=...
  Y_STAGE1=...
  (plus optional)
"""

from __future__ import annotations

import os
import sys
import math
from typing import List, Dict, Optional

import sys
sys.path.insert(0, r"C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\src")


def _die(msg: str, code: int = 2) -> None:
    print(f"[thermo_bridge] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _ensure_project_importable() -> None:
    src = os.environ.get("DYNAMIC_DISTILLATION_SRC", "").strip()
    if src and os.path.isdir(src) and src not in sys.path:
        sys.path.insert(0, src)


def _parse_csv_floats(s: str) -> List[float]:
    s = s.strip()
    if not s:
        return []
    parts = [p.strip() for p in s.split(",") if p.strip() != ""]
    out: List[float] = []
    for p in parts:
        out.append(float(p))
    return out


def _normalize(z: List[float], eps: float = 1e-15) -> List[float]:
    s = float(sum(z))
    if (not math.isfinite(s)) or s <= eps:
        n = len(z)
        return [1.0 / n] * n
    return [v / s for v in z]


def _read_kv_lines(path: str) -> Dict[str, List[str]]:
    d: Dict[str, List[str]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            d.setdefault(k, []).append(v)
    return d


def run(req_path: str, resp_path: str) -> None:
    _ensure_project_importable()

    from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # type: ignore
    from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1  # type: ignore

    kv = _read_kv_lines(req_path)

    def one(key: str) -> str:
        vals = kv.get(key)
        if not vals:
            _die(f"Missing required key: {key}")
        return vals[0]

    excel_path = one("EXCEL_PATH")
    N = int(float(one("N")))
    Nc = int(float(one("NC")))

    T_F = _parse_csv_floats(one("T_F"))
    P_psia = _parse_csv_floats(one("P_PSIA"))
    zrows_raw = kv.get("ZROW", [])

    if len(T_F) != N or len(P_psia) != N:
        _die(f"T_F and P_PSIA must each have length N={N}")

    if len(zrows_raw) != N:
        _die(f"Expected {N} ZROW lines, got {len(zrows_raw)}")

    zrows: List[List[float]] = []
    for i, s in enumerate(zrows_raw):
        row = _parse_csv_floats(s)
        if len(row) != Nc:
            _die(f"ZROW {i+1} must have NC={Nc} values, got {len(row)}")
        zrows.append(_normalize(row))

    case = load_case_from_excel(excel_path)
    comps_excel = list(case.components)
    comps_dwsim = list(case.component_ids_dwsim)

    if len(comps_dwsim) != Nc:
        _die(
            f"NC in request ({Nc}) does not match Excel case components ({len(comps_dwsim)}). "
            f"Fix the Scilab z matrix or use the right Excel file."
        )

    thermo = ThermoProviderV1(
        component_names_excel=comps_excel,
        component_ids_dwsim=comps_dwsim,
        cp_dt_F=1.0,
        silence_backend_console=True,
    )

    HL: List[float] = []
    HV: List[float] = []
    y_stage1: Optional[List[float]] = None

    for i in range(N):
        fres = thermo.flash_TP_full(float(T_F[i]), float(P_psia[i]), zrows[i])
        HL.append(float(fres.HL_BTU_lbmol))
        HV.append(float(fres.HV_BTU_lbmol))
        if i == 0:
            y_stage1 = [float(v) for v in fres.y]

    def fmt_list(vals: List[float]) -> str:
        return ",".join(f"{v:.10g}" for v in vals)

    out_lines: List[str] = []
    out_lines.append("COMPONENTS_EXCEL=" + ",".join(comps_excel))
    out_lines.append("COMPONENT_IDS_DWSIM=" + ",".join(comps_dwsim))
    out_lines.append("HL=" + fmt_list(HL))
    out_lines.append("HV=" + fmt_list(HV))
    if y_stage1 is not None:
        out_lines.append("Y_STAGE1=" + fmt_list(y_stage1))

    with open(resp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        _die("Usage: python thermo_bridge.py thermo_request.txt thermo_response.txt", code=2)
    run(sys.argv[1], sys.argv[2])