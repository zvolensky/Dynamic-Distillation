#!/usr/bin/env python
"""
Gani 1986 / ChemSep seed reconciliation audit.

This reports the t=0 stage material and energy residuals for the current model
topology, using the same runner input construction and RHS conventions as a
dynamic run. It is intentionally diagnostic: the output is meant to identify
which stage, phase, component, or boundary mapping prevents a ChemSep seed from
being a model-equivalent steady state.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_rhs_v1 import column_rhs  # noqa: E402
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _initialize_thermo_consistent_state,
    _initialize_vapor_holdup_from_spec_pressure,
    build_inputs_for_runner,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_path(raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (_PROJECT_ROOT / p).resolve()


def _diag_vec(diag: Dict[str, Any], key: str, n: int, default: float = math.nan) -> np.ndarray:
    if key not in diag:
        return np.full(n, default, dtype=float)
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((n,))
    except Exception:
        return np.full(n, default, dtype=float)
    return arr


def _diag_scalar(diag: Dict[str, Any], key: str, default: float = math.nan) -> float:
    if key not in diag:
        return default
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((-1,))
        if arr.size == 0:
            return default
        v = float(arr[0])
    except Exception:
        return default
    return v if np.isfinite(v) else default


def _safe_norm(v: np.ndarray, fallback: Optional[np.ndarray] = None) -> np.ndarray:
    arr = np.asarray(v, dtype=float).reshape((-1,))
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.clip(arr, 0.0, None)
    s = float(np.sum(arr))
    if s > 1.0e-300:
        return arr / s
    if fallback is not None:
        return _safe_norm(np.asarray(fallback, dtype=float).reshape((-1,)))
    if arr.size <= 0:
        return arr
    return np.full(arr.size, 1.0 / float(arr.size), dtype=float)


def _matrix(diag: Dict[str, Any], key: str, shape: tuple[int, int]) -> Optional[np.ndarray]:
    if key not in diag:
        return None
    try:
        return np.asarray(diag[key], dtype=float).reshape(shape)
    except Exception:
        return None


def _build_state(col: Any, layout: StateVectorLayout, inputs: Any, args: argparse.Namespace) -> np.ndarray:
    y = layout.pack_y0(col)
    if not bool(args.use_excel_vapor_holdup):
        y = _clear_initial_tray_vapor_holdup(y, layout)
    y = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y,
        inputs=inputs,
        include_temperature=bool(args.include_temperature),
        preserve_tray_vapor_holdup=bool(args.use_excel_vapor_holdup),
    )
    if int(args.startup_thermo_conditioning_iters) > 0:
        y, _info = _initialize_thermo_consistent_state(
            col=col,
            layout=layout,
            y=y,
            inputs=inputs,
            include_temperature=bool(args.include_temperature),
            max_iter=int(args.startup_thermo_conditioning_iters),
            relaxation=float(args.startup_thermo_conditioning_relaxation),
            preserve_tray_vapor_holdup=bool(args.use_excel_vapor_holdup),
        )
    return np.asarray(y, dtype=float)


def _iter_component_rows(
    *,
    comp_names: List[str],
    stage: int,
    dL: np.ndarray,
    dV: np.ndarray,
    convL: np.ndarray,
    convV: np.ndarray,
    feedL: np.ndarray,
    feedV: np.ndarray,
    eq_transfer: Optional[np.ndarray],
) -> Iterable[Dict[str, Any]]:
    nc = len(comp_names)
    for k in range(nc):
        eq_v = float(eq_transfer[stage, k] * 3600.0) if eq_transfer is not None else math.nan
        d_l = float(dL[stage, k] * 3600.0)
        d_v = float(dV[stage, k] * 3600.0)
        conv_l = float(convL[stage, k] * 3600.0)
        conv_v = float(convV[stage, k] * 3600.0)
        feed_l = float(feedL[stage, k] * 3600.0)
        feed_v = float(feedV[stage, k] * 3600.0)
        yield {
            "stage_1based": int(stage + 1),
            "component": comp_names[k],
            "dL_rhs_lbmolph": d_l,
            "dV_rhs_lbmolph": d_v,
            "dTotal_rhs_lbmolph": d_l + d_v,
            "convective_L_lbmolph": conv_l,
            "convective_V_lbmolph": conv_v,
            "feed_L_lbmolph": feed_l,
            "feed_V_lbmolph": feed_v,
            "eq_transfer_to_V_lbmolph": eq_v,
            "unexplained_L_lbmolph": d_l - conv_l - feed_l + (eq_v if np.isfinite(eq_v) else 0.0),
            "unexplained_V_lbmolph": d_v - conv_v - feed_v - (eq_v if np.isfinite(eq_v) else 0.0),
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile the Gani/ChemSep seed against model stage balances.")
    ap.add_argument("--excel", default="validation_gani_1986_debutanizer.xlsx")
    ap.add_argument("--thermo", dest="thermo_mode", default="clapeyron", choices=["clapeyron", "dwsim", "stub"])
    ap.add_argument("--clapeyron-model", default="PR")
    ap.add_argument("--dwsim-property-package", default="pr")
    ap.add_argument("--runtime-mode", default="parity", choices=["legacy", "parity", "calibration", "hydraulic"])
    ap.add_argument("--include-energy", dest="include_energy", action="store_true")
    ap.add_argument("--no-energy", dest="include_energy", action="store_false")
    ap.set_defaults(include_energy=True)
    ap.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    ap.set_defaults(include_temperature=True)
    ap.add_argument("--disable-boundary-states", dest="include_boundary_states", action="store_false")
    ap.set_defaults(include_boundary_states=True)
    ap.add_argument("--disable-vapor-states", dest="include_vapor_states", action="store_false")
    ap.set_defaults(include_vapor_states=True)
    ap.add_argument("--use-excel-vapor-holdup", action="store_true")
    ap.add_argument("--startup-thermo-conditioning-iters", type=int, default=1)
    ap.add_argument("--startup-thermo-conditioning-relaxation", type=float, default=1.0)
    ap.add_argument("--equilibrium-relaxation-mode", default="composition-only", choices=["auto", "phase-holdup", "composition-only"])
    ap.add_argument("--no-equilibrium", dest="enable_equilibrium_relaxation", action="store_false")
    ap.set_defaults(enable_equilibrium_relaxation=True)
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--condenser-duty-mode", default="specified", choices=["total-condense", "specified"])
    ap.add_argument("--condenser-duty-btuph", type=float, default=-12269989.464019539)
    ap.add_argument("--reboiler-duty-btuph", type=float, default=None)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    excel_path = _resolve_path(args.excel)
    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=int(col.n_stages),
        n_components=int(col.n_components),
        include_top=bool(args.include_boundary_states),
        include_bottom=bool(args.include_boundary_states),
        include_vapor=bool(args.include_vapor_states),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
    )
    cfg = RunnerConfig(
        excel_path=str(excel_path),
        runtime_mode=str(args.runtime_mode),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        include_boundary_states=bool(args.include_boundary_states),
        include_vapor_states=bool(args.include_vapor_states),
        thermo_mode=str(args.thermo_mode),
        clapeyron_model=str(args.clapeyron_model),
        dwsim_property_package=str(args.dwsim_property_package),
        enable_equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
        equilibrium_relaxation_mode=str(args.equilibrium_relaxation_mode),
        vapor_holdup_relaxation_sec=float(args.vapor_holdup_relaxation_sec),
        condenser_duty_mode=str(args.condenser_duty_mode),
        condenser_duty_btu_per_h=float(args.condenser_duty_btuph),
        reboiler_duty_btu_per_h=args.reboiler_duty_btuph,
        use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
        startup_thermo_conditioning_iters=int(args.startup_thermo_conditioning_iters),
        startup_thermo_conditioning_relaxation=float(args.startup_thermo_conditioning_relaxation),
        write_logs=False,
    )

    inputs, provider = build_inputs_for_runner(case, col, cfg)
    try:
        y0 = _build_state(col, layout, inputs, args)
        eval_inputs = replace(inputs, compute_thermo_diag=True)
        dydt, diag = column_rhs(0.0, y0, col, layout, eval_inputs)
        u = layout.unpack(y0)
        du = layout.unpack(np.asarray(dydt, dtype=float))

        n = int(col.n_stages)
        nc = int(col.n_components)
        comp_names = [str(c) for c in getattr(col, "components_excel", [])] or [f"component_{i + 1}" for i in range(nc)]
        tray_L = np.asarray(u["tray_L"], dtype=float).reshape((n, nc))
        tray_V = np.asarray(u.get("tray_V", np.zeros((n, nc))), dtype=float).reshape((n, nc))
        x_tray = np.asarray(u["x_tray"], dtype=float).reshape((n, nc))
        y_tray = np.asarray(u.get("y_tray", np.zeros((n, nc))), dtype=float).reshape((n, nc))
        top_x = _safe_norm(np.asarray(u.get("top_L", x_tray[0]), dtype=float).reshape((nc,)), fallback=x_tray[0])

        dL = np.asarray(du["tray_L"], dtype=float).reshape((n, nc))
        dV = np.asarray(du.get("tray_V", np.zeros((n, nc))), dtype=float).reshape((n, nc))
        L_out = _diag_vec(diag, "L_out_lbmolph", n, 0.0) / 3600.0
        V_out = _diag_vec(diag, "V_out_lbmolph", n, 0.0) / 3600.0

        boilup_s = float(V_out[-1]) if n else 0.0
        y_reb = _matrix(diag, "y_reboiler", (1, nc))
        if y_reb is None:
            y_reb_vec = y_tray[-1].copy()
        else:
            y_reb_vec = _safe_norm(y_reb.reshape((nc,)), fallback=y_tray[-1])

        L_in = np.zeros(n, dtype=float)
        V_in = np.zeros(n, dtype=float)
        x_in = np.zeros((n, nc), dtype=float)
        y_in = np.zeros((n, nc), dtype=float)
        for i in range(n):
            if i == 0:
                x_in[i, :] = x_tray[i, :]
            else:
                L_in[i] = L_out[i - 1]
                x_in[i, :] = top_x if (bool(args.include_boundary_states) and i == 1) else x_tray[i - 1, :]
            if i == n - 1:
                V_in[i] = boilup_s
                y_in[i, :] = y_reb_vec
            else:
                V_in[i] = V_out[i + 1]
                y_in[i, :] = y_tray[i + 1, :]

        feedL = np.zeros((n, nc), dtype=float)
        feedV = np.zeros((n, nc), dtype=float)
        feed_stage = getattr(col, "feed_stage", None)
        if feed_stage is not None:
            i_feed = int(feed_stage) - 1
            if 0 <= i_feed < n:
                feed = getattr(col, "feed_component_flows_lbmolph", None)
                if feed is not None:
                    feedL[i_feed, :] = np.asarray(feed, dtype=float).reshape((nc,)) / 3600.0
                else:
                    z_feed = np.asarray(getattr(col, "z_feed", np.zeros(nc)), dtype=float).reshape((nc,))
                    f_tot = float(getattr(col, "F_lbmolph", 0.0) or 0.0)
                    feedL[i_feed, :] = f_tot * _safe_norm(z_feed) / 3600.0

        convL = L_in[:, None] * x_in - L_out[:, None] * x_tray
        convV = V_in[:, None] * y_in - V_out[:, None] * y_tray

        eq_transfer = _matrix(diag, "eq_transfer_lbmolps_tray", (n, nc))
        rows: List[Dict[str, Any]] = []
        component_rows: List[Dict[str, Any]] = []
        for i in range(n):
            dL_i = float(np.sum(dL[i, :]) * 3600.0)
            dV_i = float(np.sum(dV[i, :]) * 3600.0)
            convL_i = float(np.sum(convL[i, :]) * 3600.0)
            convV_i = float(np.sum(convV[i, :]) * 3600.0)
            feedL_i = float(np.sum(feedL[i, :]) * 3600.0)
            feedV_i = float(np.sum(feedV[i, :]) * 3600.0)
            eq_i = float(np.sum(eq_transfer[i, :]) * 3600.0) if eq_transfer is not None else math.nan
            comp_net = (dL[i, :] + dV[i, :]) * 3600.0
            worst_k = int(np.nanargmax(np.abs(comp_net))) if comp_net.size else 0
            e_model = math.nan
            if "tray_EL_BTU" in du:
                e_model = float(np.asarray(du["tray_EL_BTU"], dtype=float).reshape((n,))[i])
                if "tray_EV_BTU" in du:
                    e_model += float(np.asarray(du["tray_EV_BTU"], dtype=float).reshape((n,))[i])
            rows.append(
                {
                    "stage_1based": int(i + 1),
                    "dL_rhs_lbmolph": dL_i,
                    "dV_rhs_lbmolph": dV_i,
                    "dTotal_rhs_lbmolph": dL_i + dV_i,
                    "convective_L_lbmolph": convL_i,
                    "convective_V_lbmolph": convV_i,
                    "feed_L_lbmolph": feedL_i,
                    "feed_V_lbmolph": feedV_i,
                    "eq_transfer_to_V_lbmolph": eq_i,
                    "unexplained_total_lbmolph": (dL_i + dV_i) - (convL_i + convV_i + feedL_i + feedV_i),
                    "L_in_lbmolph": float(L_in[i] * 3600.0),
                    "L_out_lbmolph": float(L_out[i] * 3600.0),
                    "V_in_lbmolph": float(V_in[i] * 3600.0),
                    "V_out_lbmolph": float(V_out[i] * 3600.0),
                    "ML_lbmol": float(np.sum(tray_L[i, :])),
                    "MV_lbmol": float(np.sum(tray_V[i, :])),
                    "dE_rhs_BTUps": e_model,
                    "dT_F_per_s": float(_diag_vec(diag, "dT_tray_F_per_s", n, 0.0)[i]),
                    "worst_component": comp_names[worst_k],
                    "worst_component_total_rate_lbmolph": float(comp_net[worst_k]),
                }
            )
            component_rows.extend(
                _iter_component_rows(
                    comp_names=comp_names,
                    stage=i,
                    dL=dL,
                    dV=dV,
                    convL=convL,
                    convV=convV,
                    feedL=feedL,
                    feedV=feedV,
                    eq_transfer=eq_transfer,
                )
            )

        out_dir = _resolve_path(args.output_dir) if args.output_dir else (_PROJECT_ROOT / "logs" / f"gani_stage_reconciliation_{_timestamp_tag()}")
        out_dir.mkdir(parents=True, exist_ok=True)
        stage_csv = out_dir / "stage_reconciliation.csv"
        comp_csv = out_dir / "component_reconciliation.csv"
        with stage_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        with comp_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(component_rows[0].keys()))
            writer.writeheader()
            writer.writerows(component_rows)

        stage_rank = sorted(rows, key=lambda r: abs(float(r["dTotal_rhs_lbmolph"])), reverse=True)
        comp_rank = sorted(component_rows, key=lambda r: abs(float(r["dTotal_rhs_lbmolph"])), reverse=True)
        energy_rank = sorted(rows, key=lambda r: abs(float(r["dE_rhs_BTUps"])) if np.isfinite(float(r["dE_rhs_BTUps"])) else -1.0, reverse=True)
        summary = [
            "# Gani Stage Reconciliation Audit",
            "",
            f"- Excel: `{excel_path}`",
            f"- Runtime mode: `{args.runtime_mode}`",
            f"- Thermo: `{args.thermo_mode}` `{args.clapeyron_model if args.thermo_mode == 'clapeyron' else args.dwsim_property_package}`",
            f"- Boundary states: `{bool(args.include_boundary_states)}`",
            f"- Vapor states: `{bool(args.include_vapor_states)}`",
            f"- Energy states: `{bool(args.include_energy)}`",
            f"- Startup thermo conditioning iterations: `{int(args.startup_thermo_conditioning_iters)}`",
            f"- Condenser duty mode/value: `{args.condenser_duty_mode}` / `{float(args.condenser_duty_btuph):.6g} Btu/h`",
            "",
            "## Headline",
            "",
            f"- max |stage dM|: `{abs(float(stage_rank[0]['dTotal_rhs_lbmolph'])):.6g} lbmol/h` on stage `{stage_rank[0]['stage_1based']}`",
            f"- max |component dM|: `{abs(float(comp_rank[0]['dTotal_rhs_lbmolph'])):.6g} lbmol/h` on stage `{comp_rank[0]['stage_1based']}` component `{comp_rank[0]['component']}`",
            f"- max |stage dE|: `{abs(float(energy_rank[0]['dE_rhs_BTUps'])):.6g} Btu/s` on stage `{energy_rank[0]['stage_1based']}`",
            f"- top pool material rate: `{(float(np.sum(du.get('top_L', 0.0))) + float(np.sum(du.get('top_V', 0.0)))) * 3600.0 if bool(args.include_boundary_states) else float('nan'):.6g} lbmol/h`",
            f"- bottom pool material rate: `{(float(np.sum(du.get('bottom_L', 0.0))) + float(np.sum(du.get('bottom_V', 0.0)))) * 3600.0 if bool(args.include_boundary_states) else float('nan'):.6g} lbmol/h`",
            "",
            "## Worst Stage Material Residuals",
            "",
        ]
        for row in stage_rank[:10]:
            summary.append(
                f"- stage {row['stage_1based']:2d}: dM={float(row['dTotal_rhs_lbmolph']): .3f} lbmol/h "
                f"(dL={float(row['dL_rhs_lbmolph']): .3f}, dV={float(row['dV_rhs_lbmolph']): .3f}, "
                f"L {float(row['L_in_lbmolph']):.1f}->{float(row['L_out_lbmolph']):.1f}, "
                f"V {float(row['V_in_lbmolph']):.1f}->{float(row['V_out_lbmolph']):.1f}, "
                f"worst {row['worst_component']}={float(row['worst_component_total_rate_lbmolph']): .3f})"
            )
        summary.extend(["", "## Worst Component Residuals", ""])
        for row in comp_rank[:12]:
            summary.append(
                f"- stage {row['stage_1based']:2d} {row['component']}: "
                f"dTotal={float(row['dTotal_rhs_lbmolph']): .3f} lbmol/h "
                f"(dL={float(row['dL_rhs_lbmolph']): .3f}, dV={float(row['dV_rhs_lbmolph']): .3f})"
            )
        summary.extend(["", "## Worst Energy Residuals", ""])
        for row in energy_rank[:8]:
            summary.append(f"- stage {row['stage_1based']:2d}: dE={float(row['dE_rhs_BTUps']): .3f} Btu/s")
        summary.extend(["", f"- Stage CSV: `{stage_csv}`", f"- Component CSV: `{comp_csv}`"])
        summary_path = out_dir / "summary.md"
        summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
        print("\n".join(summary))
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
