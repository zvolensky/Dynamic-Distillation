#!/usr/bin/env python
"""
Profile one column_rhs call using the current C3/C4 initialization recipe.

This script intentionally mirrors the liquid-energy reconciler's setup path:
load workbook, build runtime inputs, apply optional top-vapor packing and
condenser-duty matching, then evaluate exactly one RHS call.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import time

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dynamic_distillation.column_rhs_v1 import BoundaryFlows, column_rhs  # noqa: E402
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _initialize_vapor_holdup_from_spec_pressure,
    _mapping_scalar,
    _pack_top_drum_vapor_to_pressure,
    build_inputs_for_runner,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _stream_total(col: object, key: str) -> float:
    def norm(s: object) -> str:
        return "".join(ch for ch in str(s).strip().lower() if ch.isalnum())

    streams = getattr(col, "streams", {}) or {}
    for name, stream in streams.items():
        n = norm(name)
        if key == "distillate" and ("distillate" in n or n.startswith("top")):
            total = getattr(stream, "total_molar_flow_lbmolph", None)
        elif key == "bottoms" and "bottom" in n:
            total = getattr(stream, "total_molar_flow_lbmolph", None)
        else:
            continue
        if total is not None:
            try:
                return float(total)
            except Exception:
                return 0.0
    return 0.0


def build_profile_case(args: argparse.Namespace) -> tuple[object, StateVectorLayout, object, np.ndarray]:
    excel_path = _resolve(args.input)
    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=int(col.n_stages),
        n_components=int(col.n_components),
        include_top=bool(args.include_boundary_states),
        include_bottom=bool(args.include_boundary_states),
        include_vapor=True,
        include_temperature=True,
        include_energy=True,
    )
    cfg = RunnerConfig(
        excel_path=str(excel_path),
        runtime_mode=str(args.runtime_mode),
        include_temperature=True,
        include_energy=True,
        include_boundary_states=bool(args.include_boundary_states),
        include_vapor_states=True,
        thermo_mode=str(args.thermo),
        clapeyron_model=str(args.clapeyron_model),
        thermo_table_path=str(args.thermo_table),
        condenser_duty_mode=str(args.condenser_duty_mode),
        condenser_duty_btu_per_h=args.condenser_duty_btuph,
        enable_equilibrium_relaxation=not bool(args.no_equilibrium),
        equilibrium_relaxation_mode=str(args.equilibrium_relaxation_mode),
        equilibrium_tau_sec=args.equilibrium_tau_sec,
        flash_feed_at_stage_conditions=(False if bool(args.no_flash_feed_at_stage_conditions) else None),
        vapor_holdup_relaxation_sec=float(args.vapor_holdup_relaxation_sec),
        write_logs=False,
    )
    inputs, _provider = build_inputs_for_runner(case, col, cfg)
    inputs = replace(
        inputs,
        feed_stage_flash_prev=None,
        feed_stage_flash_reuse_dT_F=0.0,
        feed_stage_flash_reuse_dP_psia=0.0,
        feed_stage_flash_reuse_dx=0.0,
    )
    if args.reflux_lbmolph is not None:
        b0 = inputs.boundary
        inputs = replace(
            inputs,
            boundary=BoundaryFlows(
                reflux_lbmolph=float(args.reflux_lbmolph),
                boilup_lbmolph=float(getattr(b0, "boilup_lbmolph", 0.0) or 0.0),
                distillate_lbmolph=float(_stream_total(col, "distillate")),
                bottoms_lbmolph=float(_stream_total(col, "bottoms")),
            ),
        )
    y0 = layout.pack_y0(col)
    if not bool(args.use_excel_vapor_holdup):
        y0 = _clear_initial_tray_vapor_holdup(y0, layout)
    y0 = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y0,
        inputs=inputs,
        include_temperature=True,
        preserve_tray_vapor_holdup=bool(args.use_excel_vapor_holdup),
    )
    if bool(args.init_pack_top_drum_vapor_to_pressure):
        p_target = args.init_top_drum_vapor_pressure_psia
        if p_target is None:
            p_target = args.top_pressure_sp_psia
        y0, info = _pack_top_drum_vapor_to_pressure(
            y=np.asarray(y0, dtype=float),
            col=col,
            layout=layout,
            inputs=inputs,
            target_pressure_psia=p_target,
        )
        print(
            "top_vapor_pack "
            f"applied={bool(info.get('applied', False))} "
            f"reason={info.get('reason', '')} "
            f"P={info.get('raw_pressure_initial_psia', np.nan):.6g}->{info.get('raw_pressure_final_psia', np.nan):.6g}",
            flush=True,
        )
    if bool(args.init_match_condenser_duty):
        p_match = args.top_pressure_sp_psia
        if p_match is None:
            p_match = float(np.asarray(getattr(col, "P_psia"), dtype=float).reshape((-1,))[0])
        match_inputs = replace(
            inputs,
            condenser_duty_mode="total-condense",
            condenser_duty_btu_per_h=None,
            condenser_duty_trim_btu_per_h=None,
            pressure_top_anchor_psia=float(p_match),
            condenser_duty_prev=None,
        )
        _dydt_match, diag_match = column_rhs(0.0, np.asarray(y0, dtype=float), col, layout, match_inputs)
        q_match = _mapping_scalar(diag_match, "Q_cond_calc_BTUph")
        if not np.isfinite(float(q_match)):
            q_match = _mapping_scalar(diag_match, "Q_cond_used_BTUph")
        if np.isfinite(float(q_match)) and float(q_match) < 0.0:
            inputs = replace(inputs, condenser_duty_btu_per_h=float(q_match), condenser_duty_trim_btu_per_h=0.0)
            print(f"matched_condenser_duty_BTUph={float(q_match):.8g}", flush=True)
    inputs = replace(
        inputs,
        enable_liquid_hydraulic_override=bool(args.enable_liquid_hydraulic_override),
        liquid_hydraulic_model=str(args.liquid_hydraulic_model),
        liquid_hydraulic_override_alpha=float(args.liquid_hydraulic_override_alpha),
        liquid_hydraulic_override_alpha_per_stage=None,
    )
    return col, layout, inputs, np.asarray(y0, dtype=float)


def main() -> int:
    ap = argparse.ArgumentParser(description="Profile a single column_rhs call.")
    ap.add_argument("--input", default="logs/c3c4_initializer_profile_coeff_trial1_20260601.xlsx")
    ap.add_argument("--runtime-mode", default="hydraulic")
    ap.add_argument("--thermo", default="table")
    ap.add_argument("--clapeyron-model", default="PR")
    ap.add_argument("--thermo-table", default="cache/thermo_table.json")
    ap.add_argument("--include-boundary-states", action="store_true", default=True)
    ap.add_argument("--no-boundary-states", dest="include_boundary_states", action="store_false")
    ap.add_argument("--use-excel-vapor-holdup", action="store_true")
    ap.add_argument("--no-equilibrium", action="store_true")
    ap.add_argument("--equilibrium-relaxation-mode", default="composition-only")
    ap.add_argument("--equilibrium-tau-sec", type=float, default=0.5)
    ap.add_argument("--no-flash-feed-at-stage-conditions", action="store_true")
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--condenser-duty-mode", default="total-condense")
    ap.add_argument("--condenser-duty-btuph", type=float, default=None)
    ap.add_argument("--init-pack-top-drum-vapor-to-pressure", action="store_true")
    ap.add_argument("--init-top-drum-vapor-pressure-psia", type=float, default=None)
    ap.add_argument("--init-match-condenser-duty", action="store_true")
    ap.add_argument("--top-pressure-sp", dest="top_pressure_sp_psia", type=float, default=222.62)
    ap.add_argument("--reflux", dest="reflux_lbmolph", type=float, default=5701.145898904781)
    ap.add_argument("--enable-liquid-hydraulic-override", action="store_true")
    ap.add_argument("--liquid-hydraulic-model", default="francis")
    ap.add_argument("--liquid-hydraulic-override-alpha", type=float, default=1.0)
    args = ap.parse_args()

    t0 = time.perf_counter()
    col, layout, inputs, y0 = build_profile_case(args)
    print(f"build_profile_case_wall_sec={time.perf_counter() - t0:.6g}", flush=True)
    t1 = time.perf_counter()
    dydt, diag = column_rhs(0.0, np.asarray(y0, dtype=float), col, layout, inputs)
    dt = time.perf_counter() - t1
    du = layout.unpack(np.asarray(dydt, dtype=float))
    n = int(col.n_stages)
    nc = int(col.n_components)
    dml = np.sum(np.asarray(du["tray_L"], dtype=float).reshape((n, nc)), axis=1)
    print(f"column_rhs_wall_sec={dt:.6g}", flush=True)
    print(f"max_abs_dML_lbmolps={float(np.max(np.abs(dml))):.8g}", flush=True)
    print(f"diag_keys={len(diag)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
