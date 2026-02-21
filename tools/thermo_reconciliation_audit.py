#!/usr/bin/env python
"""
Thermo reconciliation audit against ChemSep tray profiles.

This tool compares:
1) Excel case tray profiles vs ChemSep profiles.
2) Thermo flash predictions at ChemSep tray (T, P, x) vs ChemSep vapor y.

Output:
  - Stage-by-stage CSV under logs/ (default)
  - Console summary with worst mismatches
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

# Allow direct "python tools/..." usage without requiring external PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.dynamic_run_scaffold_v1 import RunnerConfig, build_inputs_for_runner
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel

try:
    from chemsep_profile_utils import (
        build_case_component_index_from_chemsep_labels,
        normalize_rows,
        parse_chemsep_results_xls,
        reorder_profile_components_to_case_order,
    )
except Exception:
    from tools.chemsep_profile_utils import (
        build_case_component_index_from_chemsep_labels,
        normalize_rows,
        parse_chemsep_results_xls,
        reorder_profile_components_to_case_order,
    )


@dataclass(frozen=True)
class StageComparison:
    stage_1based: int
    dT_F: float
    dP_psia: float
    dL_lbmolph: float
    dV_lbmolph: float
    max_abs_dx: float
    max_abs_dy_ic: float
    max_abs_dy_eq: float
    l1_dy_eq: float
    mean_rel_K_err: float
    max_rel_K_err: float


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_path(project_root: Path, raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def _safe_divide(num: np.ndarray, den: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    den_use = np.where(np.abs(den) > eps, den, np.nan)
    out = num / den_use
    return np.asarray(out, dtype=float)


def _as_float(x: Any, default: float = math.nan) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    return v if np.isfinite(v) else default


def _comp_suffix(name: str) -> str:
    raw = str(name).strip().lower()
    out = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    return out if out else "comp"


def _top_worst(items: Sequence[StageComparison], n: int = 5) -> List[StageComparison]:
    return sorted(items, key=lambda r: float(r.max_abs_dy_eq), reverse=True)[: max(int(n), 1)]


def _mean_or_nan(arr: np.ndarray) -> float:
    a = np.asarray(arr, dtype=float).reshape((-1,))
    good = a[np.isfinite(a)]
    if good.size == 0:
        return math.nan
    return float(np.mean(good))


def _max_or_nan(arr: np.ndarray) -> float:
    a = np.asarray(arr, dtype=float).reshape((-1,))
    good = a[np.isfinite(a)]
    if good.size == 0:
        return math.nan
    return float(np.max(good))


def _build_provider(
    *,
    case: Any,
    col: Any,
    excel_path: str,
    thermo_mode: str,
    thermo_table_path: Optional[str],
    thermo_pool_workers: Optional[int],
    thermo_pool_chunk_size: int,
) -> Any:
    cfg = RunnerConfig(
        excel_path=str(excel_path),
        thermo_mode=str(thermo_mode),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        thermo_pool_workers=thermo_pool_workers,
        thermo_pool_chunk_size=max(int(thermo_pool_chunk_size), 1),
        write_logs=False,
    )
    _inputs, provider = build_inputs_for_runner(case, col, cfg)
    return provider


def main() -> int:
    ap = argparse.ArgumentParser(description="ChemSep thermo reconciliation audit.")
    ap.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    ap.add_argument("--chemsep-xls", dest="chemsep_xls", required=True)
    ap.add_argument("--thermo", dest="thermo_mode", choices=["table", "table-pool", "dwsim"], default="table")
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=None)
    ap.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    ap.add_argument("--output-csv", dest="output_csv", default=None)
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    excel_path = _resolve_path(project_root, str(args.excel_path))
    chemsep_path = _resolve_path(project_root, str(args.chemsep_xls))
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel case file not found: {excel_path}")
    if not chemsep_path.exists():
        raise FileNotFoundError(f"ChemSep workbook not found: {chemsep_path}")

    thermo_table_path: Optional[Path] = None
    if str(args.thermo_mode).lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(project_root, str(args.thermo_table_path))
        if not thermo_table_path.exists():
            raise FileNotFoundError(f"Thermo table file not found: {thermo_table_path}")

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    chem = parse_chemsep_results_xls(str(chemsep_path))

    case_from_chem_idx = build_case_component_index_from_chemsep_labels(
        chemsep_component_labels=chem.component_labels,
        case_components_dwsim=col.components_dwsim,
    )
    x_cs_case = reorder_profile_components_to_case_order(
        arr_stage_by_comp=chem.x_liq,
        case_from_chemsep_index=case_from_chem_idx,
    )
    y_cs_case = reorder_profile_components_to_case_order(
        arr_stage_by_comp=chem.y_vap,
        case_from_chemsep_index=case_from_chem_idx,
    )
    x_cs_case = normalize_rows(x_cs_case)
    y_cs_case = normalize_rows(y_cs_case)

    stage_case = np.asarray(col.stage_1based, dtype=int).reshape((-1,))
    stage_cs = np.asarray(chem.stage_1based, dtype=int).reshape((-1,))
    common_stages = sorted(set(stage_case.tolist()).intersection(stage_cs.tolist()))
    if not common_stages:
        raise ValueError("No common stage numbers between case and ChemSep profiles")

    idx_case = {int(s): i for i, s in enumerate(stage_case.tolist())}
    idx_cs = {int(s): i for i, s in enumerate(stage_cs.tolist())}

    N = len(common_stages)
    Nc = int(col.n_components)
    T_case = np.zeros(N, dtype=float)
    P_case = np.zeros(N, dtype=float)
    L_case = np.zeros(N, dtype=float)
    V_case = np.zeros(N, dtype=float)
    x_case = np.zeros((N, Nc), dtype=float)
    y_case = np.zeros((N, Nc), dtype=float)
    T_cs = np.zeros(N, dtype=float)
    P_cs = np.zeros(N, dtype=float)
    L_cs = np.zeros(N, dtype=float)
    V_cs = np.zeros(N, dtype=float)
    x_cs = np.zeros((N, Nc), dtype=float)
    y_cs = np.zeros((N, Nc), dtype=float)

    for k, s in enumerate(common_stages):
        i_case = idx_case[int(s)]
        i_cs = idx_cs[int(s)]
        T_case[k] = float(np.asarray(col.T_f, dtype=float).reshape((-1,))[i_case])
        P_case[k] = float(np.asarray(col.P_psia, dtype=float).reshape((-1,))[i_case])
        L_case[k] = float(np.asarray(col.L_lbmolph, dtype=float).reshape((-1,))[i_case])
        V_case[k] = float(np.asarray(col.V_lbmolph, dtype=float).reshape((-1,))[i_case])
        x_case[k, :] = np.asarray(col.x0, dtype=float).reshape((col.n_stages, Nc))[i_case, :]
        y_case[k, :] = np.asarray(col.y0, dtype=float).reshape((col.n_stages, Nc))[i_case, :]
        T_cs[k] = float(np.asarray(chem.temperature_F, dtype=float).reshape((-1,))[i_cs])
        P_cs[k] = float(np.asarray(chem.pressure_psia, dtype=float).reshape((-1,))[i_cs])
        L_cs[k] = float(np.asarray(chem.liquid_flow_lbmolph, dtype=float).reshape((-1,))[i_cs])
        V_cs[k] = float(np.asarray(chem.vapor_flow_lbmolph, dtype=float).reshape((-1,))[i_cs])
        x_cs[k, :] = np.asarray(x_cs_case, dtype=float).reshape((len(stage_cs), Nc))[i_cs, :]
        y_cs[k, :] = np.asarray(y_cs_case, dtype=float).reshape((len(stage_cs), Nc))[i_cs, :]

    provider = None
    try:
        provider = _build_provider(
            case=case,
            col=col,
            excel_path=str(excel_path),
            thermo_mode=str(args.thermo_mode),
            thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
            thermo_pool_workers=args.thermo_pool_workers,
            thermo_pool_chunk_size=int(args.thermo_pool_chunk_size),
        )

        if hasattr(provider, "flash_TP_full_batch"):
            flashes = provider.flash_TP_full_batch(
                T_cs.tolist(),
                P_cs.tolist(),
                x_cs.tolist(),
            )
        else:
            flashes = [provider.flash_TP_full(float(T_cs[i]), float(P_cs[i]), x_cs[i, :].tolist()) for i in range(N)]

        y_eq = np.zeros((N, Nc), dtype=float)
        K_eq = np.zeros((N, Nc), dtype=float)
        for i, fres in enumerate(flashes):
            y_eq[i, :] = np.asarray(getattr(fres, "y", np.full(Nc, np.nan)), dtype=float).reshape((Nc,))
            K_eq[i, :] = np.asarray(getattr(fres, "K", np.full(Nc, np.nan)), dtype=float).reshape((Nc,))
        y_eq = normalize_rows(np.where(np.isfinite(y_eq), y_eq, 0.0))

        dy_eq = y_eq - y_cs
        dy_ic = y_case - y_cs
        dx = x_case - x_cs
        K_cs = _safe_divide(y_cs, x_cs, eps=1e-10)
        rel_K = np.abs(_safe_divide(K_eq - K_cs, np.abs(K_cs), eps=1e-10))

        rows: List[Dict[str, Any]] = []
        stage_metrics: List[StageComparison] = []
        comp_keys = [_comp_suffix(c) for c in col.components_excel]
        for i, s in enumerate(common_stages):
            row: Dict[str, Any] = {
                "stage_1based": int(s),
                "T_case_F": float(T_case[i]),
                "T_chemsep_F": float(T_cs[i]),
                "dT_F": float(T_case[i] - T_cs[i]),
                "P_case_psia": float(P_case[i]),
                "P_chemsep_psia": float(P_cs[i]),
                "dP_psia": float(P_case[i] - P_cs[i]),
                "L_case_lbmolph": float(L_case[i]),
                "L_chemsep_lbmolph": float(L_cs[i]),
                "dL_lbmolph": float(L_case[i] - L_cs[i]),
                "V_case_lbmolph": float(V_case[i]),
                "V_chemsep_lbmolph": float(V_cs[i]),
                "dV_lbmolph": float(V_case[i] - V_cs[i]),
                "max_abs_dx": float(np.max(np.abs(dx[i, :]))),
                "max_abs_dy_ic": float(np.max(np.abs(dy_ic[i, :]))),
                "max_abs_dy_eq": float(np.max(np.abs(dy_eq[i, :]))),
                "l1_dy_eq": float(np.sum(np.abs(dy_eq[i, :]))),
                "mean_rel_K_err": _mean_or_nan(rel_K[i, :]),
                "max_rel_K_err": _max_or_nan(rel_K[i, :]),
            }

            for j, ck in enumerate(comp_keys):
                row[f"x_case_{ck}"] = float(x_case[i, j])
                row[f"x_chemsep_{ck}"] = float(x_cs[i, j])
                row[f"y_case_{ck}"] = float(y_case[i, j])
                row[f"y_chemsep_{ck}"] = float(y_cs[i, j])
                row[f"y_eq_{ck}"] = float(y_eq[i, j])
                row[f"abs_dy_eq_{ck}"] = float(abs(dy_eq[i, j]))
                row[f"K_chemsep_{ck}"] = float(K_cs[i, j]) if np.isfinite(K_cs[i, j]) else math.nan
                row[f"K_eq_{ck}"] = float(K_eq[i, j]) if np.isfinite(K_eq[i, j]) else math.nan
                row[f"rel_K_err_{ck}"] = float(rel_K[i, j]) if np.isfinite(rel_K[i, j]) else math.nan

            rows.append(row)
            stage_metrics.append(
                StageComparison(
                    stage_1based=int(s),
                    dT_F=float(row["dT_F"]),
                    dP_psia=float(row["dP_psia"]),
                    dL_lbmolph=float(row["dL_lbmolph"]),
                    dV_lbmolph=float(row["dV_lbmolph"]),
                    max_abs_dx=float(row["max_abs_dx"]),
                    max_abs_dy_ic=float(row["max_abs_dy_ic"]),
                    max_abs_dy_eq=float(row["max_abs_dy_eq"]),
                    l1_dy_eq=float(row["l1_dy_eq"]),
                    mean_rel_K_err=float(row["mean_rel_K_err"]),
                    max_rel_K_err=float(row["max_rel_K_err"]),
                )
            )

        if args.output_csv:
            out_csv = _resolve_path(project_root, str(args.output_csv))
        else:
            out_csv = project_root / "logs" / f"thermo_reconciliation_audit_{_timestamp_tag()}.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)

        fields = list(rows[0].keys()) if rows else []
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow(row)

        dT = T_case - T_cs
        dP = P_case - P_cs
        dL = L_case - L_cs
        dV = V_case - V_cs

        print("Thermo reconciliation audit")
        print(f"Excel case: {excel_path}")
        print(f"ChemSep xls: {chemsep_path}")
        print(f"Thermo mode: {str(args.thermo_mode).lower()}")
        print(f"Stages compared: {len(common_stages)}")
        print("")
        print("Profile agreement (Excel case vs ChemSep):")
        print(f"  max |dT| = {_max_or_nan(np.abs(dT)):.6g} F")
        print(f"  max |dP| = {_max_or_nan(np.abs(dP)):.6g} psia")
        print(f"  max |dL| = {_max_or_nan(np.abs(dL)):.6g} lbmol/h")
        print(f"  max |dV| = {_max_or_nan(np.abs(dV)):.6g} lbmol/h")
        print(f"  max |dx| = {_max_or_nan(np.abs(dx)):.6g}")
        print(f"  max |dy_ic| = {_max_or_nan(np.abs(dy_ic)):.6g}")
        print("")
        print("Thermo agreement at ChemSep tray states (flash(T,P,x)):")
        print(f"  max |dy_eq| = {_max_or_nan(np.abs(dy_eq)):.6g}")
        print(f"  mean |dy_eq| = {_mean_or_nan(np.abs(dy_eq)):.6g}")
        print(f"  max relative K error = {_max_or_nan(rel_K):.6g}")
        print(f"  mean relative K error = {_mean_or_nan(rel_K):.6g}")
        print("")
        print("Worst stages by max |dy_eq|:")
        for rec in _top_worst(stage_metrics, n=5):
            print(
                f"  stage {int(rec.stage_1based):2d}: "
                f"max|dy_eq|={float(rec.max_abs_dy_eq):.6g}  "
                f"l1|dy_eq|={float(rec.l1_dy_eq):.6g}  "
                f"max relK err={float(rec.max_rel_K_err):.6g}"
            )
        print("")
        print(f"Wrote: {out_csv}")
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
