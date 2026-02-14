# thermo_cache_v1.py
# Purpose: Precompute and persist per-stage thermo cache for fast startup.

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.dynamic_run_scaffold_v1 import RunnerConfig, build_inputs_for_runner
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.column_rhs_v1 import column_rhs


def _to_list(arr: np.ndarray) -> list:
    return np.asarray(arr, dtype=float).tolist()


def build_thermo_cache(
    *,
    excel_path: str,
    thermo_mode: str = "dwsim",
    out_path: Optional[str] = None,
) -> Path:
    """
    Precompute per-stage thermo cache (K, HL, HV, Z) from the Excel input.
    Returns the path of the cache file written.
    """
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)

    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=True,
        include_energy=False,
    )

    cfg = RunnerConfig(
        excel_path=str(excel_path),
        thermo_mode=str(thermo_mode),
        include_temperature=True,
        include_energy=False,
        enable_equilibrium_relaxation=False,
        write_logs=False,
    )

    inputs, _ = build_inputs_for_runner(case, col, cfg)
    y0 = layout.pack_y0(col)

    _dydt, diag = column_rhs(0.0, y0, col, layout, inputs=inputs)

    if "K_tray" not in diag or "HL_BTU_lbmol_tray" not in diag or "HV_BTU_lbmol_tray" not in diag:
        raise RuntimeError("Thermo cache build failed: missing K/HL/HV in diagnostics.")

    cache: Dict[str, Any] = {
        "format_version": 1,
        "excel_path": str(excel_path),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "n_stages": int(col.n_stages),
        "n_components": int(col.n_components),
        "components_excel": list(col.components_excel),
        "components_dwsim": list(col.components_dwsim),
        "T_tray_F": _to_list(np.asarray(col.T_f, dtype=float).reshape((col.n_stages,))),
        "P_tray_psia": _to_list(np.asarray(col.P_psia, dtype=float).reshape((col.n_stages,))),
        "K_tray": _to_list(np.asarray(diag["K_tray"], dtype=float)),
        "HL_BTU_lbmol_tray": _to_list(np.asarray(diag["HL_BTU_lbmol_tray"], dtype=float).reshape((col.n_stages,))),
        "HV_BTU_lbmol_tray": _to_list(np.asarray(diag["HV_BTU_lbmol_tray"], dtype=float).reshape((col.n_stages,))),
        "Z_tray": _to_list(np.asarray(diag.get("Z_tray", np.ones(col.n_stages, dtype=float)), dtype=float)),
    }

    if out_path is None:
        out_path = str(Path("cache") / "thermo_cache.json")
    out_path = str(Path(out_path))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=True)

    return Path(out_path)


def load_thermo_cache(path: str) -> Dict[str, Any]:
    """Load thermo cache from JSON and return a dict with numpy arrays."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Thermo cache not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    out: Dict[str, Any] = dict(data)
    for key in ("K_tray", "HL_BTU_lbmol_tray", "HV_BTU_lbmol_tray", "Z_tray", "T_tray_F", "P_tray_psia"):
        if key in out and out[key] is not None:
            out[key] = np.asarray(out[key], dtype=float)
    return out


def _cli() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Precompute thermo cache from Excel.")
    p.add_argument("--excel", dest="excel_path", required=True)
    p.add_argument("--thermo", dest="thermo_mode", choices=("stub", "dwsim"), default="dwsim")
    p.add_argument("--out", dest="out_path", default=None)

    args = p.parse_args()
    out = build_thermo_cache(excel_path=args.excel_path, thermo_mode=args.thermo_mode, out_path=args.out_path)
    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
