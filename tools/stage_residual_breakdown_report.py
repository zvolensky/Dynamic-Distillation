#!/usr/bin/env python
"""
Stage-by-stage residual breakdown report at t=0.

Purpose
-------
Generate a per-stage report showing where tray inventory residuals come from
at initialization: convective net flow, feed source, and remaining terms.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_rhs_v1 import (  # noqa: E402
    ColumnInputs,
    _feed_component_rates_lbmolps,
    column_rhs,
)
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _initialize_vapor_holdup_from_spec_pressure,
    build_inputs_for_runner,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_path(project_root: Path, raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def _as_float(x: Any, default: float = math.nan) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    return v if np.isfinite(v) else default


def _diag_vec(diag: Dict[str, Any], key: str, n: int) -> np.ndarray:
    if key not in diag:
        return np.full(n, np.nan, dtype=float)
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((n,))
        return arr
    except Exception:
        return np.full(n, np.nan, dtype=float)


def _diag_scalar(diag: Dict[str, Any], key: str) -> float:
    if key not in diag:
        return math.nan
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((-1,))
        if arr.size == 0:
            return math.nan
        return _as_float(arr[0], default=math.nan)
    except Exception:
        return math.nan


def _scenario_inputs(base_inputs: ColumnInputs, scenario: str) -> ColumnInputs:
    key = str(scenario).strip().lower()
    if key in ("default", "default_from_case"):
        return base_inputs
    if key == "spec_profile_no_feed_flash":
        return replace(
            base_inputs,
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=False,
        )
    if key == "spec_profile_with_feed_flash":
        return replace(
            base_inputs,
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=True,
        )
    if key == "hydraulic_energy_no_feed_flash":
        return replace(
            base_inputs,
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=False,
        )
    if key == "hydraulic_energy_with_feed_flash":
        return replace(
            base_inputs,
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=True,
        )
    raise ValueError(
        f"Unknown scenario '{scenario}'. "
        "Use one of: default, spec_profile_no_feed_flash, "
        "spec_profile_with_feed_flash, hydraulic_energy_no_feed_flash, "
        "hydraulic_energy_with_feed_flash."
    )


def _build_initial_state(
    *,
    col: Any,
    layout: StateVectorLayout,
    inputs: ColumnInputs,
    include_temperature: bool,
    use_excel_vapor_holdup: bool,
) -> np.ndarray:
    y = layout.pack_y0(col)
    if not bool(use_excel_vapor_holdup):
        y = _clear_initial_tray_vapor_holdup(y, layout)
    y = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y,
        inputs=inputs,
        include_temperature=bool(include_temperature),
        preserve_tray_vapor_holdup=bool(use_excel_vapor_holdup),
    )
    return np.asarray(y, dtype=float)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate stage residual breakdown report at t=0.")
    ap.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    ap.add_argument(
        "--thermo",
        dest="thermo_mode",
        choices=["stub", "relative-volatility", "simple-rv", "constant-alpha", "table", "table-pool", "dwsim"],
        default="table-pool",
    )
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=6)
    ap.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    ap.add_argument(
        "--scenario",
        dest="scenario",
        default="default",
        help=(
            "default | spec_profile_no_feed_flash | spec_profile_with_feed_flash | "
            "hydraulic_energy_no_feed_flash | hydraulic_energy_with_feed_flash"
        ),
    )
    ap.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    ap.add_argument("--include-energy", dest="include_energy", action="store_true")
    ap.add_argument("--no-energy", dest="include_energy", action="store_false")
    ap.set_defaults(include_temperature=True, include_energy=False)
    ap.add_argument("--use-excel-vapor-holdup", dest="use_excel_vapor_holdup", action="store_true")
    ap.add_argument("--output-csv", dest="output_csv", default=None)
    ap.add_argument("--output-summary", dest="output_summary", default=None)
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    excel_path = _resolve_path(project_root, str(args.excel_path))
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel case file not found: {excel_path}")

    thermo_table_path: Optional[Path] = None
    if str(args.thermo_mode).lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(project_root, str(args.thermo_table_path))
        if not thermo_table_path.exists():
            raise FileNotFoundError(f"Thermo table file not found: {thermo_table_path}")

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
    )

    cfg = RunnerConfig(
        excel_path=str(excel_path),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        thermo_pool_workers=args.thermo_pool_workers,
        thermo_pool_chunk_size=max(int(args.thermo_pool_chunk_size), 1),
        include_temperature=bool(args.include_temperature),
        include_energy=bool(args.include_energy),
        write_logs=False,
    )

    base_inputs, provider = build_inputs_for_runner(case, col, cfg)
    try:
        inputs = _scenario_inputs(base_inputs, str(args.scenario))
        y0 = _build_initial_state(
            col=col,
            layout=layout,
            inputs=inputs,
            include_temperature=bool(args.include_temperature),
            use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
        )

        dydt, diag = column_rhs(0.0, y0, col, layout, inputs)
        du = layout.unpack(np.asarray(dydt, dtype=float))
        N = int(col.n_stages)
        Nc = int(col.n_components)

        d_tray_L = np.asarray(du["tray_L"], dtype=float).reshape((N, Nc))
        d_tray_V = np.asarray(du["tray_V"], dtype=float).reshape((N, Nc))
        d_liq = np.sum(d_tray_L, axis=1) * 3600.0
        d_vap = np.sum(d_tray_V, axis=1) * 3600.0
        d_total = d_liq + d_vap

        L_out = _diag_vec(diag, "L_out_lbmolph", N)
        V_out = _diag_vec(diag, "V_out_lbmolph", N)
        L_in = np.zeros(N, dtype=float)
        V_in = np.zeros(N, dtype=float)
        if N > 1:
            L_in[1:] = L_out[:-1]
            V_in[:-1] = V_out[1:]
        if N > 0:
            # Reboiler boilup enters bottom tray.
            V_in[-1] = V_out[-1]

        conv_net = (L_in - L_out) + (V_in - V_out)

        P_for_feed = None
        if np.all(np.isfinite(_diag_vec(diag, "P_psia_hyd", N))):
            P_for_feed = _diag_vec(diag, "P_psia_hyd", N)
        elif hasattr(col, "P_psia"):
            P_for_feed = np.asarray(col.P_psia, dtype=float).reshape((N,))
        feed_stage0, Fk_L, Fk_V = _feed_component_rates_lbmolps(
            col=col,
            Nc=Nc,
            thermo_provider=getattr(inputs, "thermo_provider", None),
            P_tray_psia=P_for_feed,
            flash_feed_at_stage_conditions=bool(getattr(inputs, "flash_feed_at_stage_conditions", True)),
        )
        feed_liq_stage = np.zeros(N, dtype=float)
        feed_vap_stage = np.zeros(N, dtype=float)
        if feed_stage0 is not None and (0 <= int(feed_stage0) < N):
            feed_liq_stage[int(feed_stage0)] = float(np.sum(Fk_L) * 3600.0)
            feed_vap_stage[int(feed_stage0)] = float(np.sum(Fk_V) * 3600.0)
        feed_total_stage = feed_liq_stage + feed_vap_stage

        other_terms = d_total - (conv_net + feed_total_stage)

        dT = _diag_vec(diag, "dT_tray_F_per_s", N)
        mb_diag = _diag_vec(diag, "mass_balance_resid_lbmolps_tray", N) * 3600.0

        comp_total = (d_tray_L + d_tray_V) * 3600.0
        comp_idx = np.argmax(np.abs(comp_total), axis=1)
        comp_rate = np.array([comp_total[i, int(comp_idx[i])] for i in range(N)], dtype=float)
        comp_name = [str(col.components_excel[int(comp_idx[i])]) for i in range(N)]

        rows: List[Dict[str, Any]] = []
        for i in range(N):
            rows.append(
                {
                    "stage_1based": int(i + 1),
                    "dM_tray_lbmolph": float(d_total[i]),
                    "dM_liq_lbmolph": float(d_liq[i]),
                    "dM_vap_lbmolph": float(d_vap[i]),
                    "mass_balance_resid_diag_lbmolph": float(mb_diag[i]),
                    "L_in_lbmolph": float(L_in[i]),
                    "L_out_lbmolph": float(L_out[i]),
                    "V_in_lbmolph": float(V_in[i]),
                    "V_out_lbmolph": float(V_out[i]),
                    "convective_net_lbmolph": float(conv_net[i]),
                    "feed_liq_lbmolph": float(feed_liq_stage[i]),
                    "feed_vap_lbmolph": float(feed_vap_stage[i]),
                    "feed_total_lbmolph": float(feed_total_stage[i]),
                    "other_terms_lbmolph": float(other_terms[i]),
                    "dT_tray_F_per_s": float(dT[i]),
                    "max_component_name": str(comp_name[i]),
                    "max_component_rate_lbmolph": float(comp_rate[i]),
                }
            )

        top_rate = 0.0
        if "top_L" in du:
            top_rate += float(np.sum(np.asarray(du["top_L"], dtype=float))) * 3600.0
        if "top_V" in du:
            top_rate += float(np.sum(np.asarray(du["top_V"], dtype=float))) * 3600.0
        bottom_rate = 0.0
        if "bottom_L" in du:
            bottom_rate += float(np.sum(np.asarray(du["bottom_L"], dtype=float))) * 3600.0
        if "bottom_V" in du:
            bottom_rate += float(np.sum(np.asarray(du["bottom_V"], dtype=float))) * 3600.0
        total_state_rate = float(np.sum(d_total) + top_rate + bottom_rate)
        gmc = _diag_scalar(diag, "global_mass_closure_error_lbmolph")
        feed_vf_eff = _diag_scalar(diag, "feed_vf_effective")

        abs_idx = np.argsort(-np.abs(d_total))
        top_lines: List[str] = []
        for j in abs_idx[: min(10, N)]:
            top_lines.append(
                f"  stage {int(j + 1):2d}: dM={float(d_total[j]): .3f} lbmol/h, "
                f"conv={float(conv_net[j]): .3f}, feed={float(feed_total_stage[j]): .3f}, "
                f"other={float(other_terms[j]): .3f}"
            )

        if args.output_csv:
            out_csv = _resolve_path(project_root, str(args.output_csv))
        else:
            out_csv = project_root / "logs" / f"stage_residual_breakdown_{_timestamp_tag()}.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        fields = list(rows[0].keys()) if rows else []
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow(r)

        if args.output_summary:
            out_txt = _resolve_path(project_root, str(args.output_summary))
        else:
            out_txt = project_root / "logs" / f"stage_residual_summary_{_timestamp_tag()}.txt"
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        summary_lines = [
            "Stage Residual Breakdown Report",
            f"excel: {excel_path}",
            f"thermo_mode: {str(args.thermo_mode).lower()}",
            f"scenario: {str(args.scenario)}",
            f"pressure_model: {getattr(inputs, 'pressure_model', None)}",
            f"vapor_flow_model: {getattr(inputs, 'vapor_flow_model', None)}",
            f"flash_feed_at_stage_conditions: {bool(getattr(inputs, 'flash_feed_at_stage_conditions', True))}",
            f"include_temperature: {bool(args.include_temperature)}",
            f"include_energy: {bool(args.include_energy)}",
            "",
            f"feed_stage_1based: {'' if feed_stage0 is None else int(feed_stage0 + 1)}",
            f"feed_total_lbmolph: {float(np.sum(feed_total_stage)):.6f}",
            f"feed_vf_effective: {float(feed_vf_eff) if np.isfinite(feed_vf_eff) else float('nan')}",
            "",
            f"max_abs_tray_residual_lbmolph: {float(np.max(np.abs(d_total))):.6f}",
            f"rms_tray_residual_lbmolph: {float(np.sqrt(np.mean(np.square(d_total)))):.6f}",
            f"worst_stage_1based: {int(np.argmax(np.abs(d_total)) + 1)}",
            f"top_pool_rate_lbmolph: {float(top_rate):.6f}",
            f"bottom_pool_rate_lbmolph: {float(bottom_rate):.6f}",
            f"total_state_inventory_rate_lbmolph: {float(total_state_rate):.6f}",
            f"global_mass_closure_error_lbmolph: {float(gmc) if np.isfinite(gmc) else float('nan')}",
            "",
            "Top stages by |dM_tray|:",
            *top_lines,
            "",
            f"csv: {out_csv}",
        ]
        with out_txt.open("w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(summary_lines) + "\n")

        print("\n".join(summary_lines))
        print(f"summary: {out_txt}")
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
