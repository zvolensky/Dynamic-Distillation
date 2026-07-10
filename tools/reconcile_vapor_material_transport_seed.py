#!/usr/bin/env python
"""
Diagnostic vapor material-transport reconciliation.

This tool starts from the same projected initialization state used by the
one-step C3/C4 probes, then solves only tray vapor composition logits to reduce
the live RHS tray vapor material terms. Tray vapor holdup totals are preserved.

The output is an experimental restart workbook plus a JSON summary. It is not an
accepted initializer unless the normal residual and dynamic gates pass.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
from scipy.optimize import least_squares

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dynamic_distillation.column_rhs_v1 import column_rhs  # noqa: E402
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _initialize_tray_liquid_composition_from_equilibrium,
    _initialize_tray_vapor_composition_from_equilibrium,
    _initialize_vapor_holdup_from_spec_pressure,
    build_inputs_for_runner,
    write_restart_workbook_from_run_result,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _normalize(v: np.ndarray, fallback: Optional[np.ndarray] = None) -> np.ndarray:
    arr = np.asarray(v, dtype=float).reshape((-1,))
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.clip(arr, 0.0, None)
    s = float(np.sum(arr))
    if s > 1.0e-300:
        return arr / s
    if fallback is not None:
        return _normalize(fallback)
    return np.full(arr.size, 1.0 / float(max(arr.size, 1)), dtype=float)


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = np.asarray(logits, dtype=float).reshape((-1,))
    z = z - float(np.max(z))
    e = np.exp(np.clip(z, -60.0, 60.0))
    return e / max(float(np.sum(e)), 1.0e-300)


def _logit(comp: np.ndarray) -> np.ndarray:
    return np.log(np.clip(_normalize(comp), 1.0e-12, 1.0))


def _stage_indices(n_stages: int, scope: str) -> List[int]:
    s = str(scope or "interior").strip().lower()
    if s == "all":
        return list(range(int(n_stages)))
    if s == "interior":
        return [i for i in range(int(n_stages)) if 0 < i < int(n_stages) - 1]
    out: List[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo = max(int(a), 1)
            hi = min(int(b), int(n_stages))
            out.extend(range(lo - 1, hi))
        else:
            idx = int(part) - 1
            if 0 <= idx < int(n_stages):
                out.append(idx)
    return sorted(set(out))


def _build_context(args: argparse.Namespace) -> tuple[Any, StateVectorLayout, Any, np.ndarray, Any]:
    excel_path = _resolve(args.excel)
    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=int(col.n_stages),
        n_components=int(col.n_components),
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
    )
    cfg = RunnerConfig(
        excel_path=str(excel_path),
        runtime_mode=str(args.runtime_mode),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        include_boundary_states=True,
        include_vapor_states=True,
        thermo_mode=str(args.thermo),
        clapeyron_model=str(args.clapeyron_model),
        enable_equilibrium_relaxation=True,
        equilibrium_relaxation_mode=str(args.equilibrium_relaxation_mode),
        equilibrium_tau_sec=float(args.equilibrium_tau_sec),
        flash_feed_at_stage_conditions=not bool(args.no_flash_feed_at_stage_conditions),
        vapor_holdup_relaxation_sec=float(args.vapor_holdup_relaxation_sec),
        vapor_flow_relaxation_sec=float(args.vapor_flow_relaxation_sec),
        vapor_flow_zero_temperature_target=bool(args.vapor_flow_zero_temperature_target),
        use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
        enable_pressure_control=bool(args.enable_pressure_control),
        pressure_control_mv=str(args.pressure_control_mv),
        top_pressure_sp_psia=float(args.top_pressure_sp),
        top_pressure_anchor_min_psia=float(args.top_pressure_anchor_min),
        top_pressure_anchor_max_psia=float(args.top_pressure_anchor_max),
        dynamic_vflow_nominal_hi_ratio=float(args.dynamic_vflow_nominal_hi_ratio),
        write_logs=False,
    )
    inputs, provider = build_inputs_for_runner(case, col, cfg)
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
    if bool(args.align_tray_liquid_to_equilibrium):
        y, _info_liq = _initialize_tray_liquid_composition_from_equilibrium(
            col=col,
            layout=layout,
            y=np.asarray(y, dtype=float),
            inputs=inputs,
            blend=float(args.tray_liquid_equilibrium_blend),
            scope=str(args.tray_liquid_equilibrium_scope),
        )
    if bool(args.align_tray_vapor_to_equilibrium):
        y, _info_vap = _initialize_tray_vapor_composition_from_equilibrium(
            col=col,
            layout=layout,
            y=np.asarray(y, dtype=float),
            inputs=inputs,
            blend=float(args.tray_vapor_equilibrium_blend),
        )
    return col, layout, inputs, np.asarray(y, dtype=float), provider


def _apply_logits(
    y: np.ndarray,
    *,
    layout: StateVectorLayout,
    stage_indices: Iterable[int],
    logits_flat: np.ndarray,
) -> np.ndarray:
    u = layout.unpack(np.asarray(y, dtype=float))
    tray_v = np.asarray(u["tray_V"], dtype=float).reshape((layout.n_stages, layout.n_components)).copy()
    totals = np.sum(np.where(np.isfinite(tray_v), tray_v, 0.0), axis=1)
    z = np.asarray(logits_flat, dtype=float).reshape((len(list(stage_indices)), layout.n_components))
    y_new = np.asarray(y, dtype=float).copy()
    tray_v_new = tray_v.copy()
    for row, i in enumerate(stage_indices):
        total = float(totals[int(i)])
        if (not np.isfinite(total)) or total <= 0.0:
            continue
        tray_v_new[int(i), :] = total * _softmax(z[row, :])
    sl = layout.slices()
    y_new[sl["tray_V"]] = tray_v_new.reshape((-1,))
    return y_new


def _rhs_metrics(
    y: np.ndarray,
    *,
    col: Any,
    layout: StateVectorLayout,
    inputs: Any,
    denom_floor_lbmol: float,
    stage_indices: List[int],
) -> tuple[np.ndarray, Dict[str, Any]]:
    dydt, diag = column_rhs(0.0, np.asarray(y, dtype=float), col, layout, inputs)
    u = layout.unpack(np.asarray(y, dtype=float))
    tray_v = np.asarray(u["tray_V"], dtype=float).reshape((layout.n_stages, layout.n_components))
    if "tray_V_final_rhs_lbmolps" in diag:
        rhs = np.asarray(diag["tray_V_final_rhs_lbmolps"], dtype=float).reshape((layout.n_stages, layout.n_components))
    else:
        du = layout.unpack(np.asarray(dydt, dtype=float))
        rhs = np.asarray(du["tray_V"], dtype=float).reshape((layout.n_stages, layout.n_components))
    denom = np.abs(tray_v) + max(float(denom_floor_lbmol), 0.0)
    rel = rhs / np.maximum(denom, 1.0e-300)
    subset = rel[np.asarray(stage_indices, dtype=int), :]
    abs_subset = np.abs(subset[np.isfinite(subset)])
    max_rel = float(np.max(abs_subset)) if abs_subset.size else math.nan
    return subset.reshape((-1,)), {
        "dydt": np.asarray(dydt, dtype=float),
        "diag": diag,
        "rhs": rhs,
        "max_relative_rhs_per_s": max_rel,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Solve a diagnostic vapor material-transport reconciliation.")
    ap.add_argument("--excel", required=True)
    ap.add_argument("--output-excel", required=True)
    ap.add_argument("--summary-json", required=True)
    ap.add_argument("--runtime-mode", default="hydraulic")
    ap.add_argument("--thermo", default="clapeyron")
    ap.add_argument("--clapeyron-model", default="PR")
    ap.add_argument("--include-temperature", action="store_true", default=True)
    ap.add_argument("--include-energy", action="store_true", default=True)
    ap.add_argument("--equilibrium-relaxation-mode", default="composition-only")
    ap.add_argument("--equilibrium-tau-sec", type=float, default=0.5)
    ap.add_argument("--no-flash-feed-at-stage-conditions", action="store_true")
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--vapor-flow-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--vapor-flow-zero-temperature-target", action="store_true")
    ap.add_argument("--use-excel-vapor-holdup", action="store_true")
    ap.add_argument("--enable-pressure-control", action="store_true")
    ap.add_argument("--pressure-control-mv", default="top-anchor")
    ap.add_argument("--top-pressure-sp", type=float, default=222.62)
    ap.add_argument("--top-pressure-anchor-min", type=float, default=222.62)
    ap.add_argument("--top-pressure-anchor-max", type=float, default=222.62)
    ap.add_argument("--dynamic-vflow-nominal-hi-ratio", type=float, default=1.05)
    ap.add_argument("--align-tray-liquid-to-equilibrium", action="store_true")
    ap.add_argument("--tray-liquid-equilibrium-blend", type=float, default=1.0)
    ap.add_argument("--tray-liquid-equilibrium-scope", default="interior")
    ap.add_argument("--align-tray-vapor-to-equilibrium", action="store_true")
    ap.add_argument("--tray-vapor-equilibrium-blend", type=float, default=1.0)
    ap.add_argument("--solve-scope", default="interior")
    ap.add_argument("--denom-floor-lbmol", type=float, default=1.0)
    ap.add_argument("--regularization-weight", type=float, default=0.03)
    ap.add_argument("--max-nfev", type=int, default=20)
    args = ap.parse_args()

    provider = None
    try:
        col, layout, inputs, y_seed, provider = _build_context(args)
        stage_indices = _stage_indices(int(col.n_stages), str(args.solve_scope))
        if not stage_indices:
            raise ValueError("solve scope selected no stages")
        u_seed = layout.unpack(y_seed)
        tray_v_seed = np.asarray(u_seed["tray_V"], dtype=float).reshape((layout.n_stages, layout.n_components))
        yfrac_seed = np.asarray(u_seed["y_tray"], dtype=float).reshape((layout.n_stages, layout.n_components))
        logits0 = np.vstack([_logit(yfrac_seed[i, :]) for i in stage_indices]).reshape((-1,))
        rhs0, metric0 = _rhs_metrics(
            y_seed,
            col=col,
            layout=layout,
            inputs=inputs,
            denom_floor_lbmol=float(args.denom_floor_lbmol),
            stage_indices=stage_indices,
        )

        reg_weight = max(float(args.regularization_weight), 0.0)

        def objective(logits_flat: np.ndarray) -> np.ndarray:
            y_trial = _apply_logits(
                y_seed,
                layout=layout,
                stage_indices=stage_indices,
                logits_flat=np.asarray(logits_flat, dtype=float),
            )
            r, _metric = _rhs_metrics(
                y_trial,
                col=col,
                layout=layout,
                inputs=inputs,
                denom_floor_lbmol=float(args.denom_floor_lbmol),
                stage_indices=stage_indices,
            )
            if reg_weight > 0.0:
                r = np.concatenate([r, reg_weight * (np.asarray(logits_flat, dtype=float) - logits0)])
            return np.asarray(r, dtype=float)

        res = least_squares(
            objective,
            logits0,
            method="trf",
            max_nfev=max(int(args.max_nfev), 1),
            x_scale="jac",
        )
        y_opt = _apply_logits(y_seed, layout=layout, stage_indices=stage_indices, logits_flat=res.x)
        rhs1, metric1 = _rhs_metrics(
            y_opt,
            col=col,
            layout=layout,
            inputs=inputs,
            denom_floor_lbmol=float(args.denom_floor_lbmol),
            stage_indices=stage_indices,
        )
        u_opt = layout.unpack(y_opt)
        yfrac_opt = np.asarray(u_opt["y_tray"], dtype=float).reshape((layout.n_stages, layout.n_components))
        drift = np.max(np.abs(yfrac_opt[np.asarray(stage_indices), :] - yfrac_seed[np.asarray(stage_indices), :]))

        out_excel = _resolve(args.output_excel)
        fake_result = {
            "final_state": np.asarray(y_opt, dtype=float),
            "layout": layout,
            "column": col,
            "last_diag": metric1["diag"],
            "excel_path": str(_resolve(args.excel)),
            "final_time_s": 0.0,
        }
        write_restart_workbook_from_run_result(
            run_result=fake_result,
            output_excel_path=str(out_excel),
            template_excel_path=str(_resolve(args.excel)),
        )

        summary = {
            "input_excel": str(_resolve(args.excel)),
            "output_excel": str(out_excel),
            "solve_scope": str(args.solve_scope),
            "n_solved_stages": len(stage_indices),
            "stage_indices_1based": [int(i + 1) for i in stage_indices],
            "max_relative_rhs_before_per_s": float(metric0["max_relative_rhs_per_s"]),
            "max_relative_rhs_after_per_s": float(metric1["max_relative_rhs_per_s"]),
            "max_vapor_composition_drift": float(drift),
            "least_squares": {
                "success": bool(res.success),
                "status": int(res.status),
                "message": str(res.message),
                "cost": float(res.cost),
                "optimality": float(res.optimality),
                "nfev": int(res.nfev),
            },
        }
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
