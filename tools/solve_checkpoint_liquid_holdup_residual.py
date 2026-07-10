#!/usr/bin/env python
"""
Solve internal liquid holdup totals in a native checkpoint against live RHS.

This is a narrow initializer diagnostic: it adjusts only internal tray liquid
totals, preserves liquid compositions, and leaves top/bottom stages unchanged.
The objective is the live internal tray total material residual from column_rhs.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import numpy as np
from scipy.optimize import least_squares

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_rhs_v1 import column_rhs  # noqa: E402
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    build_inputs_for_runner,
    load_native_checkpoint_initial_state,
    read_native_checkpoint,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _resolve_path(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (_PROJECT_ROOT / p).resolve()


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _layout_from_doc(doc: Dict[str, Any]) -> StateVectorLayout:
    return StateVectorLayout(
        n_stages=int(doc["n_stages"]),
        n_components=int(doc["n_components"]),
        include_top=bool(doc.get("include_top", True)),
        include_bottom=bool(doc.get("include_bottom", True)),
        include_vapor=bool(doc.get("include_vapor", True)),
        include_temperature=bool(doc.get("include_temperature", False)),
        include_energy=bool(doc.get("include_energy", False)),
    )


def _inputs_with_checkpoint_memory(inputs: Any, memory: Dict[str, Any], *, zero_temperature_target: bool) -> Any:
    p_prev = memory.get("last_P_hyd")
    if p_prev is None:
        p_prev = memory.get("last_P_diag")
    kwargs: Dict[str, Any] = {
        "P_tray_prev": p_prev,
        "T_tray_prev_F": memory.get("last_T_tray"),
        "K_tray_prev": memory.get("last_K_tray"),
        "HL_prev": memory.get("last_HL"),
        "HV_prev": memory.get("last_HV"),
        "Zfac_prev": memory.get("last_Zfac"),
        "Z_overall_prev": memory.get("last_z_overall"),
        "V_out_prev_lbmolph": memory.get("last_V_out"),
        "dT_tray_target_F_per_s": None if zero_temperature_target else memory.get("last_dT_tray"),
        "rhoL_tray_lbmol_ft3": memory.get("last_rhoL"),
        "tray_thermo_prev": memory.get("last_tray_thermo_packet"),
        "condenser_duty_prev": memory.get("last_condenser_duty_packet"),
        "bottom_sump_cp_prev": memory.get("last_bottom_sump_cp_packet"),
        "energy_balance_resid_prev_BTUps_tray": memory.get("last_energy_resid_tray"),
        "phase_energy_damping_min_prev_tray": memory.get("last_phase_energy_damping_min"),
        "tray_temp_pressure_slope_prev_F_per_psi": memory.get("last_tray_temp_pressure_slope"),
        "tray_bubble_target_prev_F": memory.get("last_tray_bubble_target_F"),
        "reb_T_prev": memory.get("last_reb_T"),
        "reb_x_prev": memory.get("last_reb_x"),
        "reb_y_prev": memory.get("last_reb_y"),
        "reb_beta_prev": memory.get("last_reb_beta"),
        "top_drum_pressure_T_prev_F": memory.get("last_top_drum_pressure_T"),
    }
    kwargs["feed_stage_flash_prev"] = (
        memory.get("last_feed_stage_flash_packet")
        if bool(getattr(inputs, "flash_feed_at_stage_conditions", False))
        else None
    )
    return replace(inputs, **kwargs)


def _with_internal_ml(layout: StateVectorLayout, y_base: np.ndarray, ml_target: np.ndarray) -> np.ndarray:
    y = np.asarray(y_base, dtype=float).copy()
    u = layout.unpack(y)
    tray_l = np.asarray(u["tray_L"], dtype=float).reshape((layout.n_stages, layout.n_components)).copy()
    old_ml = np.sum(tray_l, axis=1)
    for i in range(1, int(layout.n_stages) - 1):
        if old_ml[i] > 0.0 and np.isfinite(ml_target[i]) and ml_target[i] > 0.0:
            tray_l[i, :] *= float(ml_target[i]) / float(old_ml[i])
    y[layout.slices()["tray_L"]] = tray_l.reshape((-1,))
    return y


def _internal_total_residual_lbmolph(layout: StateVectorLayout, dydt: np.ndarray) -> np.ndarray:
    du = layout.unpack(np.asarray(dydt, dtype=float))
    d_l = np.asarray(du["tray_L"], dtype=float).reshape((layout.n_stages, layout.n_components))
    d_v = np.asarray(du["tray_V"], dtype=float).reshape((layout.n_stages, layout.n_components))
    total = np.sum(d_l + d_v, axis=1) * 3600.0
    return total[1:-1].copy()


def main() -> int:
    ap = argparse.ArgumentParser(description="Solve native checkpoint internal liquid holdups against material residual.")
    ap.add_argument("--excel", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--thermo", choices=["stub", "table", "table-pool", "dwsim", "clapeyron"], default="table")
    ap.add_argument("--thermo-table", default="cache/thermo_table.json")
    ap.add_argument("--condenser-duty-mode", default="total-condense")
    ap.add_argument("--no-equilibrium", dest="enable_equilibrium_relaxation", action="store_false")
    ap.set_defaults(enable_equilibrium_relaxation=True)
    ap.add_argument("--no-flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_false")
    ap.add_argument("--flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_true")
    ap.set_defaults(flash_feed_at_stage_conditions=False)
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--vapor-flow-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--vapor-flow-zero-temperature-target", action="store_true")
    ap.add_argument("--lower-scale", type=float, default=0.35)
    ap.add_argument("--upper-scale", type=float, default=3.0)
    ap.add_argument("--residual-scale-lbmolph", type=float, default=500.0)
    ap.add_argument("--regularization", type=float, default=0.02)
    ap.add_argument("--max-nfev", type=int, default=80)
    args = ap.parse_args()

    excel_path = _resolve_path(args.excel)
    checkpoint_path = _resolve_path(args.checkpoint)
    output_path = _resolve_path(args.output)
    checkpoint_raw = read_native_checkpoint(checkpoint_path)
    metadata = dict(checkpoint_raw.get("metadata") or {})
    arrays = dict(checkpoint_raw.get("arrays") or {})
    layout_doc = metadata.get("layout") if isinstance(metadata.get("layout"), dict) else {}
    layout = _layout_from_doc(layout_doc)

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    thermo_table_path: Optional[Path] = None
    if str(args.thermo).lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(args.thermo_table)
    cfg = RunnerConfig(
        excel_path=str(excel_path),
        runtime_mode="hydraulic",
        thermo_mode=str(args.thermo),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        include_temperature=bool(layout.include_temperature),
        include_energy=bool(layout.include_energy),
        condenser_duty_mode=str(args.condenser_duty_mode),
        enable_equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
        flash_feed_at_stage_conditions=bool(args.flash_feed_at_stage_conditions),
        vapor_holdup_relaxation_sec=float(args.vapor_holdup_relaxation_sec),
        vapor_flow_relaxation_sec=float(args.vapor_flow_relaxation_sec),
        write_logs=False,
    )
    inputs, provider = build_inputs_for_runner(case, col, cfg)
    try:
        y0, checkpoint_info, checkpoint_memory = load_native_checkpoint_initial_state(
            path=checkpoint_path,
            layout=layout,
            col=col,
        )
        inputs = _inputs_with_checkpoint_memory(
            inputs,
            checkpoint_memory,
            zero_temperature_target=bool(args.vapor_flow_zero_temperature_target),
        )
        inputs = replace(
            inputs,
            equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
            flash_feed_at_stage_conditions=bool(args.flash_feed_at_stage_conditions),
            vapor_holdup_relaxation_sec=float(args.vapor_holdup_relaxation_sec),
            vapor_flow_relaxation_sec=float(args.vapor_flow_relaxation_sec),
        )
        u0 = layout.unpack(y0)
        tray_l0 = np.asarray(u0["tray_L"], dtype=float).reshape((layout.n_stages, layout.n_components))
        ml0 = np.sum(tray_l0, axis=1)
        internal = slice(1, int(layout.n_stages) - 1)
        z0 = np.zeros(int(layout.n_stages) - 2, dtype=float)
        lo = np.full_like(z0, math.log(max(float(args.lower_scale), 1.0e-6)))
        hi = np.full_like(z0, math.log(max(float(args.upper_scale), float(args.lower_scale) + 1.0e-6)))
        scale = max(float(args.residual_scale_lbmolph), 1.0)
        reg = max(float(args.regularization), 0.0)

        def eval_resid(z: np.ndarray) -> np.ndarray:
            ml = ml0.copy()
            ml[internal] = ml0[internal] * np.exp(np.asarray(z, dtype=float))
            y = _with_internal_ml(layout, y0, ml)
            dydt, _diag = column_rhs(0.0, y, col, layout, inputs)
            material = _internal_total_residual_lbmolph(layout, dydt) / scale
            if reg > 0.0:
                return np.concatenate([material, reg * np.asarray(z, dtype=float)])
            return material

        r0 = eval_resid(z0)
        result = least_squares(
            eval_resid,
            z0,
            bounds=(lo, hi),
            method="trf",
            max_nfev=max(int(args.max_nfev), 1),
            x_scale="jac",
        )
        ml_final = ml0.copy()
        ml_final[internal] = ml0[internal] * np.exp(result.x)
        y_final = _with_internal_ml(layout, y0, ml_final)
        dydt_final, _diag_final = column_rhs(0.0, y_final, col, layout, inputs)
        rmat_final = _internal_total_residual_lbmolph(layout, dydt_final)
        rmat_initial = r0[: int(layout.n_stages) - 2] * scale

        arrays["final_state"] = y_final.copy()
        metadata["liquid_holdup_residual_solve"] = {
            "schema": "dynamic_distillation.liquid_holdup_residual_solve.v1",
            "source_checkpoint": str(checkpoint_path),
            "created_at": _timestamp_tag(),
            "checkpoint_source_run_id": checkpoint_info.get("source_run_id", ""),
            "success": bool(result.success),
            "status": int(result.status),
            "message": str(result.message),
            "nfev": int(result.nfev),
            "cost": float(result.cost),
            "initial_max_abs_internal_residual_lbmolph": float(np.max(np.abs(rmat_initial))),
            "final_max_abs_internal_residual_lbmolph": float(np.max(np.abs(rmat_final))),
            "max_abs_internal_ML_delta_lbmol": float(np.max(np.abs(ml_final[internal] - ml0[internal]))),
            "lower_scale": float(args.lower_scale),
            "upper_scale": float(args.upper_scale),
            "regularization": float(reg),
        }
        metadata["array_keys"] = sorted(arrays.keys())
        arrays["metadata_json"] = np.asarray(json.dumps(metadata, indent=2, sort_keys=True, default=_json_default))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(output_path, **arrays)

        print("Solved checkpoint liquid holdups")
        print(f"Input: {checkpoint_path}")
        print(f"Output: {output_path}")
        print(f"success: {bool(result.success)} status={int(result.status)} nfev={int(result.nfev)}")
        print(f"initial max |internal dM| lbmol/h: {float(np.max(np.abs(rmat_initial))):.6g}")
        print(f"final max |internal dM| lbmol/h: {float(np.max(np.abs(rmat_final))):.6g}")
        print(f"max |internal ML delta| lbmol: {float(np.max(np.abs(ml_final[internal] - ml0[internal]))):.6g}")
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
