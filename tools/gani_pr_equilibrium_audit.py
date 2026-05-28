#!/usr/bin/env python
"""
Gani debutanizer PR equilibrium audit.

This focused diagnostic compares the workbook's seeded tray x/y/T/P/energy
state with live Clapeyron PR flashes.  It is intended to answer whether the
initial Gani profile is already far from PR equilibrium before dynamic
integration starts.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import RunnerConfig, build_inputs_for_runner  # noqa: E402
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402


def _tag() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve(raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _norm(v: Sequence[float]) -> np.ndarray:
    a = np.asarray(v, dtype=float).reshape((-1,))
    a = np.where(np.isfinite(a) & (a > 0.0), a, 0.0)
    s = float(np.sum(a))
    if s <= 0.0:
        return np.full_like(a, 1.0 / max(a.size, 1), dtype=float)
    return a / s


def _safe_div(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    out = np.full_like(np.asarray(num, dtype=float), np.nan, dtype=float)
    mask = np.asarray(den, dtype=float) > 1.0e-14
    out[mask] = np.asarray(num, dtype=float)[mask] / np.asarray(den, dtype=float)[mask]
    return out


def _rr_beta_from_k_z(k_values: np.ndarray, z_values: np.ndarray) -> float:
    k = np.asarray(k_values, dtype=float).reshape((-1,))
    z = _norm(z_values)

    def rr(beta: float) -> float:
        den = 1.0 + beta * (k - 1.0)
        if np.any(den <= 0.0):
            return math.nan
        return float(np.sum(z * (k - 1.0) / den))

    f0 = rr(0.0)
    f1 = rr(1.0)
    if not (np.isfinite(f0) and np.isfinite(f1)):
        return math.nan
    if f0 <= 0.0:
        return 0.0
    if f1 >= 0.0:
        return 1.0
    lo = 0.0
    hi = 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        fm = rr(mid)
        if not np.isfinite(fm):
            return math.nan
        if fm > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _finite_max_abs(a: np.ndarray) -> float:
    arr = np.asarray(a, dtype=float).reshape((-1,))
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return math.nan
    return float(np.max(np.abs(arr)))


def _float_attr(obj: Any, name: str, default: float = math.nan) -> float:
    try:
        return float(getattr(obj, name))
    except Exception:
        return default


def _array_value_or_nan(obj: Any, name: str, index0: int) -> float:
    if not hasattr(obj, name):
        return math.nan
    try:
        arr = np.asarray(getattr(obj, name), dtype=float)
    except Exception:
        return math.nan
    if arr.ndim == 0 or arr.size <= int(index0):
        return math.nan
    try:
        return float(arr.reshape((-1,))[int(index0)])
    except Exception:
        return math.nan


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit Gani workbook seeded profile against Clapeyron PR.")
    ap.add_argument("--excel", default="validation_gani_1986_debutanizer.xlsx")
    ap.add_argument("--clapeyron-model", default="PR")
    ap.add_argument("--output-csv", default=None)
    ap.add_argument("--output-summary", default=None)
    args = ap.parse_args()

    excel_path = _resolve(args.excel)
    out_csv = _resolve(args.output_csv) if args.output_csv else PROJECT_ROOT / "logs" / f"gani_pr_equilibrium_audit_{_tag()}.csv"
    out_summary = (
        _resolve(args.output_summary)
        if args.output_summary
        else PROJECT_ROOT / "logs" / f"gani_pr_equilibrium_audit_{_tag()}.md"
    )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_summary.parent.mkdir(parents=True, exist_ok=True)

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    cfg = RunnerConfig(
        excel_path=str(excel_path),
        thermo_mode="clapeyron",
        clapeyron_model=str(args.clapeyron_model),
        runtime_mode="parity",
        include_temperature=True,
        include_energy=True,
        write_logs=False,
    )
    inputs, provider = build_inputs_for_runner(case, col, cfg)
    _ = inputs

    components = [str(v) for v in getattr(col, "components_excel", [])]
    rows: list[dict[str, Any]] = []
    for i in range(int(col.n_stages)):
        stage = i + 1
        x_seed = _norm(col.x0[i, :])
        y_seed = _norm(col.y0[i, :])
        ml = float(np.sum(np.asarray(col.M_L_lbmol[i], dtype=float)))
        mv = float(np.sum(np.asarray(col.M_V_lbmol[i], dtype=float)))
        z_seed = _norm(ml * x_seed + mv * y_seed)
        t_f = float(col.T_f[i])
        p_psia = float(col.P_psia[i])

        flash_x = provider.flash_TP_full(t_f, p_psia, x_seed.tolist())
        flash_z = provider.flash_TP_full(t_f, p_psia, z_seed.tolist())
        k_pr = np.asarray(flash_x.K, dtype=float)
        k_state = _safe_div(y_seed, x_seed)
        k_ratio = _safe_div(k_state, k_pr)
        beta_z = _rr_beta_from_k_z(np.asarray(flash_z.K, dtype=float), z_seed)
        h_l_state = math.nan
        h_v_state = math.nan
        e_l = _array_value_or_nan(col, "tray_EL0_BTU", i)
        e_v = _array_value_or_nan(col, "tray_EV0_BTU", i)
        if np.isfinite(e_l) and ml > 1.0e-12:
            h_l_state = e_l / ml
        if np.isfinite(e_v) and mv > 1.0e-12:
            h_v_state = e_v / mv

        for k, comp in enumerate(components):
            rows.append(
                {
                    "stage_1based": stage,
                    "component": comp,
                    "T_F": t_f,
                    "P_psia": p_psia,
                    "x_seed": float(x_seed[k]),
                    "y_seed": float(y_seed[k]),
                    "z_seed": float(z_seed[k]),
                    "K_state_y_over_x": float(k_state[k]),
                    "K_PR_at_seed_x": float(k_pr[k]),
                    "K_state_over_K_PR": float(k_ratio[k]),
                    "flash_x_liq": float(np.asarray(flash_x.x, dtype=float)[k]),
                    "flash_y_vap": float(np.asarray(flash_x.y, dtype=float)[k]),
                    "abs_y_seed_minus_PR_y": abs(float(y_seed[k] - np.asarray(flash_x.y, dtype=float)[k])),
                    "bubble_sum_xK_minus_1": float(np.sum(x_seed * k_pr) - 1.0),
                    "dew_sum_y_over_K_minus_1": float(np.sum(y_seed / np.maximum(k_pr, 1.0e-300)) - 1.0),
                    "beta_PR_from_seed_z": float(beta_z),
                    "HL_state_BTU_lbmol": h_l_state,
                    "HL_PR_BTU_lbmol": float(flash_x.HL_BTU_lbmol),
                    "HL_state_minus_PR": h_l_state - float(flash_x.HL_BTU_lbmol),
                    "HV_state_BTU_lbmol": h_v_state,
                    "HV_PR_BTU_lbmol": float(flash_x.HV_BTU_lbmol),
                    "HV_state_minus_PR": h_v_state - float(flash_x.HV_BTU_lbmol),
                    "Z_PR": _float_attr(flash_x, "Z"),
                }
            )

    fieldnames = list(rows[0].keys()) if rows else []
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ratios = np.asarray([r["K_state_over_K_PR"] for r in rows], dtype=float)
    ydiff = np.asarray([r["abs_y_seed_minus_PR_y"] for r in rows], dtype=float)
    bubble = np.asarray([r["bubble_sum_xK_minus_1"] for r in rows], dtype=float)
    dew = np.asarray([r["dew_sum_y_over_K_minus_1"] for r in rows], dtype=float)
    hl_diff = np.asarray([r["HL_state_minus_PR"] for r in rows], dtype=float)
    hv_diff = np.asarray([r["HV_state_minus_PR"] for r in rows], dtype=float)

    worst_ratio_rows = sorted(
        [r for r in rows if np.isfinite(float(r["K_state_over_K_PR"])) and float(r["K_state_over_K_PR"]) > 0.0],
        key=lambda r: abs(math.log(float(r["K_state_over_K_PR"]))),
        reverse=True,
    )[:12]
    worst_y_rows = sorted(rows, key=lambda r: float(r["abs_y_seed_minus_PR_y"]), reverse=True)[:12]

    lines: list[str] = []
    lines.append("# Gani PR Equilibrium Audit")
    lines.append("")
    lines.append(f"- Excel: `{excel_path.name}`")
    lines.append(f"- Thermo: Clapeyron `{args.clapeyron_model}`")
    lines.append(f"- Stages: `{col.n_stages}`")
    lines.append(f"- Components: {', '.join(components)}")
    lines.append(f"- CSV: `{out_csv}`")
    lines.append("")
    lines.append("## Headline Metrics")
    lines.append("")
    lines.append(f"- max `abs(log(K_state/K_PR))`: `{_finite_max_abs(np.log(np.maximum(ratios, 1.0e-300))):.6g}`")
    lines.append(f"- max `abs(y_seed - y_PR_at_seed_x)`: `{_finite_max_abs(ydiff):.6g}`")
    lines.append(f"- max `abs(sum(x*K_PR)-1)`: `{_finite_max_abs(bubble):.6g}`")
    lines.append(f"- max `abs(sum(y/K_PR)-1)`: `{_finite_max_abs(dew):.6g}`")
    lines.append(f"- max `abs(HL_state-HL_PR)`: `{_finite_max_abs(hl_diff):.6g} Btu/lbmol`")
    lines.append(f"- max `abs(HV_state-HV_PR)`: `{_finite_max_abs(hv_diff):.6g} Btu/lbmol`")
    lines.append("")
    lines.append("## Worst K-Ratio Rows")
    lines.append("")
    for r in worst_ratio_rows:
        lines.append(
            f"- stage {r['stage_1based']:2d} {r['component']}: "
            f"K_state/K_PR=`{float(r['K_state_over_K_PR']):.6g}`, "
            f"K_state=`{float(r['K_state_y_over_x']):.6g}`, "
            f"K_PR=`{float(r['K_PR_at_seed_x']):.6g}`"
        )
    lines.append("")
    lines.append("## Worst Vapor-Composition Rows")
    lines.append("")
    for r in worst_y_rows:
        lines.append(
            f"- stage {r['stage_1based']:2d} {r['component']}: "
            f"|y_seed-y_PR|=`{float(r['abs_y_seed_minus_PR_y']):.6g}`, "
            f"y_seed=`{float(r['y_seed']):.6g}`, "
            f"y_PR=`{float(r['flash_y_vap']):.6g}`"
        )
    lines.append("")
    out_summary.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
