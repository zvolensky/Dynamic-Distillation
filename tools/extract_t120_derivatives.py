from __future__ import annotations

import argparse
import csv
import datetime as dt
from dataclasses import replace
from pathlib import Path

import numpy as np

from dynamic_distillation.column_rhs_v1 import BoundaryFlows, column_rhs
from dynamic_distillation.dynamic_run_scaffold_v1 import RunnerConfig, run_smoke_simulation


def _to_float(val: object, default: float = np.nan) -> float:
    try:
        return float(val)
    except Exception:
        return float(default)


def _last_summary_row(summary_csv: Path) -> dict[str, str]:
    with summary_csv.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows found in summary CSV: {summary_csv}")
    return rows[-1]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run a dynamic case, then evaluate RHS derivatives at final time/state "
            "and emit derivative CSV artifacts."
        )
    )
    p.add_argument("--excel", default="distillation_column_template.xlsx", help="Excel case path.")
    p.add_argument(
        "--runtime-mode",
        default="hydraulic",
        choices=["legacy", "parity", "hydraulic"],
        help="Runtime behavior mode.",
    )
    p.add_argument("--n-steps", type=int, default=600, help="Number of outer integration steps.")
    p.add_argument("--dt", type=float, default=0.2, help="Outer step size in seconds.")
    p.add_argument("--log-every", type=int, default=5, help="Log cadence in steps.")
    p.add_argument(
        "--thermo",
        default="table-pool",
        choices=["stub", "dwsim", "table", "table-pool"],
        help="Thermo provider mode.",
    )
    p.add_argument(
        "--thermo-table",
        default="cache/thermo_table.json",
        help="Thermo table JSON path (for table/table-pool).",
    )
    p.add_argument(
        "--thermo-pool-workers",
        type=int,
        default=6,
        help="Worker count for table-pool mode.",
    )
    p.add_argument(
        "--eq-mode",
        default="composition-only",
        choices=["auto", "composition-only", "phase-holdup"],
        help="Equilibrium relaxation mode override.",
    )
    p.add_argument(
        "--include-energy",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include energy states in simulation.",
    )
    p.add_argument(
        "--disable-distillate-composition-control",
        action="store_true",
        help="Disable distillate composition controller.",
    )
    p.add_argument(
        "--disable-bottoms-composition-control",
        action="store_true",
        help="Disable bottoms composition controller.",
    )
    p.add_argument(
        "--distillate-comp-sp",
        type=float,
        default=None,
        help="Distillate composition setpoint (if controller enabled).",
    )
    p.add_argument(
        "--bottoms-comp-sp",
        type=float,
        default=None,
        help="Bottoms composition setpoint (if controller enabled).",
    )
    p.add_argument(
        "--allow-repeat-command",
        action="store_true",
        help="Allow rerunning duplicate command identity.",
    )
    p.add_argument(
        "--summary-csv",
        default=None,
        help=(
            "If provided, skip simulation and compute finish-time finite-difference "
            "rates from an existing summary CSV."
        ),
    )
    p.add_argument(
        "--profile-csv",
        default=None,
        help="Optional profile CSV for stage-level finish finite-difference rates.",
    )
    p.add_argument(
        "--fd-window-sec",
        type=float,
        default=5.0,
        help="Finite-difference window in seconds for log-based derivative mode.",
    )
    return p.parse_args()


def _time_from_row(row: dict[str, str]) -> float:
    for key in ("time_s", "t_s", "t"):
        if key in row:
            return _to_float(row.get(key), np.nan)
    return np.nan


def _rows_from_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _find_prev_index(times: list[float], t_last: float, window_sec: float) -> int:
    target = float(t_last) - max(float(window_sec), 0.0)
    idx = -1
    for i, t in enumerate(times):
        if np.isfinite(t) and t <= target:
            idx = i
    if idx < 0:
        idx = max(0, len(times) - 2)
    return idx


def _run_fd_from_logs(summary_csv: Path, profile_csv: Path | None, window_sec: float) -> int:
    rows = _rows_from_csv(summary_csv)
    if len(rows) < 2:
        raise RuntimeError(f"Need >=2 rows for finite differences: {summary_csv}")

    times = [_time_from_row(r) for r in rows]
    i1 = len(rows) - 1
    i0 = _find_prev_index(times, times[i1], window_sec)
    r0 = rows[i0]
    r1 = rows[i1]
    t0 = _time_from_row(r0)
    t1 = _time_from_row(r1)
    dt_s = float(t1 - t0)
    if (not np.isfinite(dt_s)) or dt_s <= 0.0:
        raise RuntimeError(f"Invalid finite-difference dt from summary rows: dt={dt_s}")

    def _rate(key: str) -> tuple[float, float, float]:
        v0 = _to_float(r0.get(key), np.nan)
        v1 = _to_float(r1.get(key), np.nan)
        dvdt = (v1 - v0) / dt_s if np.isfinite(v0) and np.isfinite(v1) else np.nan
        return v0, v1, dvdt

    fields = [
        "Distillate_x_n_Propane",
        "Distillate_x_n_Butane",
        "Distillate_x_n_Pentane",
        "Bottoms_x_n_Propane",
        "Bottoms_x_n_Butane",
        "Bottoms_x_n_Pentane",
        "P_top_psia",
        "P_bot_psia",
        "M_total_lbmol",
    ]

    logs = Path("logs")
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_out = logs / f"derivatives_summary_finish_fd_{stamp}.csv"
    with summary_out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_prev_s", "t_last_s", "field", "value_prev", "value_last", "d_dt_per_s"])
        for key in fields:
            v0, v1, dvdt = _rate(key)
            w.writerow([t0, t1, key, v0, v1, dvdt])

    print(f"Finite-difference finish rates from summary: t_prev={t0:.6f}s t_last={t1:.6f}s dt={dt_s:.6f}s")
    for key in fields:
        _v0, v1, dvdt = _rate(key)
        print(f"{key}: value_last={v1:+.6e}, d/dt={dvdt:+.6e} per s")
    print(f"Wrote: {summary_out}")

    if profile_csv is not None:
        prow = _rows_from_csv(profile_csv)
        stage_rows = [r for r in prow if str(r.get("node_type", "")).strip().lower() == "stage"]
        if len(stage_rows) >= 2:
            by_stage: dict[int, dict[float, dict[str, str]]] = {}
            for r in stage_rows:
                s = int(_to_float(r.get("stage"), np.nan))
                t = _time_from_row(r)
                if (not np.isfinite(float(s))) or (not np.isfinite(t)):
                    continue
                by_stage.setdefault(s, {})[float(t)] = r

            stage_out = logs / f"derivatives_stage_totals_finish_fd_{stamp}.csv"
            with stage_out.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["t_prev_s", "t_last_s", "stage", "dML_dt_lbmolps", "dMV_dt_lbmolps", "dT_dt_Fps"])
                for s in sorted(by_stage.keys()):
                    m = by_stage[s]
                    if (t0 not in m) or (t1 not in m):
                        continue
                    a = m[t0]
                    b = m[t1]
                    ml0 = _to_float(a.get("ML_lbmol"), np.nan)
                    ml1 = _to_float(b.get("ML_lbmol"), np.nan)
                    mv0 = _to_float(a.get("MV_lbmol"), np.nan)
                    mv1 = _to_float(b.get("MV_lbmol"), np.nan)
                    tt0 = _to_float(a.get("T_F"), np.nan)
                    tt1 = _to_float(b.get("T_F"), np.nan)
                    dml = (ml1 - ml0) / dt_s if np.isfinite(ml0) and np.isfinite(ml1) else np.nan
                    dmv = (mv1 - mv0) / dt_s if np.isfinite(mv0) and np.isfinite(mv1) else np.nan
                    dtt = (tt1 - tt0) / dt_s if np.isfinite(tt0) and np.isfinite(tt1) else np.nan
                    w.writerow([t0, t1, s, dml, dmv, dtt])
            print(f"Wrote: {stage_out}")
    return 0


def main() -> int:
    args = _parse_args()

    if args.summary_csv:
        summary_path = Path(str(args.summary_csv))
        profile_path = Path(str(args.profile_csv)) if args.profile_csv else None
        return _run_fd_from_logs(summary_path, profile_path, float(args.fd_window_sec))

    dist_ctrl_enabled = not bool(args.disable_distillate_composition_control)
    bot_ctrl_enabled = not bool(args.disable_bottoms_composition_control)
    dist_sp = None if not dist_ctrl_enabled else args.distillate_comp_sp
    bot_sp = None if not bot_ctrl_enabled else args.bottoms_comp_sp

    cfg = RunnerConfig(
        excel_path=str(args.excel),
        runtime_mode=str(args.runtime_mode),
        n_steps=int(args.n_steps),
        dt_sec=float(args.dt),
        log_every_n_steps=int(args.log_every),
        include_energy=bool(args.include_energy),
        thermo_mode=str(args.thermo),
        thermo_table_path=str(args.thermo_table),
        thermo_pool_workers=int(args.thermo_pool_workers),
        enable_distillate_composition_control=bool(dist_ctrl_enabled),
        enable_bottoms_composition_control=bool(bot_ctrl_enabled),
        distillate_composition_sp_molfrac=(float(dist_sp) if dist_sp is not None else None),
        bottoms_composition_sp_molfrac=(float(bot_sp) if bot_sp is not None else None),
        equilibrium_relaxation_mode=str(args.eq_mode),
    )

    res = run_smoke_simulation(cfg)
    final_time_s = float(res["final_time_s"])
    y = np.asarray(res["final_state"], dtype=float).reshape((-1,))
    col = res["column"]
    layout = res["layout"]
    base_inputs = res["inputs"]
    last_diag = res.get("last_diag") or {}

    summary_csv = Path(str(res["summary_csv"]))
    last = _last_summary_row(summary_csv)

    boundary = BoundaryFlows(
        reflux_lbmolph=_to_float(last.get("Reflux_cmd_lbmolph")),
        boilup_lbmolph=_to_float(last.get("Boilup_cmd_lbmolph")),
        distillate_lbmolph=_to_float(last.get("D_lbmolph")),
        bottoms_lbmolph=_to_float(last.get("B_lbmolph")),
    )
    inputs = replace(base_inputs, boundary=boundary)

    if "K_tray" in last_diag:
        inputs = replace(inputs, K_tray_prev=np.asarray(last_diag["K_tray"], dtype=float))
    if "HL_BTU_lbmol_tray" in last_diag:
        inputs = replace(inputs, HL_prev=np.asarray(last_diag["HL_BTU_lbmol_tray"], dtype=float))
    if "HV_BTU_lbmol_tray" in last_diag:
        inputs = replace(inputs, HV_prev=np.asarray(last_diag["HV_BTU_lbmol_tray"], dtype=float))
    if "Z_tray" in last_diag:
        inputs = replace(inputs, Zfac_prev=np.asarray(last_diag["Z_tray"], dtype=float))
    if "z_overall_tray" in last_diag:
        inputs = replace(inputs, Z_overall_prev=np.asarray(last_diag["z_overall_tray"], dtype=float))
    if "rhoL_tray_lbmol_ft3" in last_diag:
        inputs = replace(inputs, rhoL_tray_lbmol_ft3=np.asarray(last_diag["rhoL_tray_lbmol_ft3"], dtype=float))
    if "dT_tray_F_per_s" in last_diag:
        inputs = replace(inputs, dT_tray_target_F_per_s=np.asarray(last_diag["dT_tray_F_per_s"], dtype=float))
    if "P_psia_hyd" in last_diag:
        inputs = replace(inputs, P_tray_prev=np.asarray(last_diag["P_psia_hyd"], dtype=float))
    if "V_out_lbmolph" in last_diag:
        inputs = replace(inputs, V_out_prev_lbmolph=np.asarray(last_diag["V_out_lbmolph"], dtype=float))
    if "T_tray_F" in last_diag:
        inputs = replace(inputs, T_tray_prev_F=np.asarray(last_diag["T_tray_F"], dtype=float))
    if "T_top_drum_pressure_used_F" in last_diag:
        t_prev = np.asarray(last_diag["T_top_drum_pressure_used_F"], dtype=float).reshape((-1,))
        if t_prev.size > 0 and np.isfinite(float(t_prev[0])):
            inputs = replace(inputs, top_drum_pressure_T_prev_F=float(t_prev[0]))

    dydt, _diag = column_rhs(final_time_s, y, col, layout, inputs=inputs)
    ud = layout.unpack(np.asarray(dydt, dtype=float).reshape((-1,)))

    n_stages = int(col.n_stages)
    n_comp = int(col.n_components)
    comp_names = list(getattr(col, "components_excel", []) or [])
    if not comp_names:
        comp_names = [f"Comp{i+1}" for i in range(n_comp)]
    comp_labels = [str(x) for x in comp_names]

    tray_L_dot = np.asarray(ud["tray_L"], dtype=float).reshape((n_stages, n_comp))
    tray_V_dot = np.asarray(ud["tray_V"], dtype=float).reshape((n_stages, n_comp))
    tray_ML_dot = np.sum(tray_L_dot, axis=1)
    tray_MV_dot = np.sum(tray_V_dot, axis=1)

    if "tray_T_f" in ud:
        tray_T_dot = np.asarray(ud["tray_T_f"], dtype=float).reshape((n_stages,))
    else:
        tray_T_dot = np.full((n_stages,), np.nan, dtype=float)

    top_L_dot = np.asarray(ud.get("top_L", np.full((n_comp,), np.nan)), dtype=float).reshape((-1,))
    top_V_dot = np.asarray(ud.get("top_V", np.full((n_comp,), np.nan)), dtype=float).reshape((-1,))
    bottom_L_dot = np.asarray(ud.get("bottom_L", np.full((n_comp,), np.nan)), dtype=float).reshape((-1,))

    logs = Path("logs")
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    stage_totals_csv = logs / f"derivatives_stage_totals_{stamp}.csv"
    with stage_totals_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "stage", "dML_dt_lbmolps", "dMV_dt_lbmolps", "dT_dt_Fps"])
        for i in range(n_stages):
            w.writerow(
                [
                    final_time_s,
                    i + 1,
                    float(tray_ML_dot[i]),
                    float(tray_MV_dot[i]),
                    float(tray_T_dot[i]),
                ]
            )

    stage_component_csv = logs / f"derivatives_stage_component_{stamp}.csv"
    with stage_component_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "stage", "component", "dL_dt_lbmolps", "dV_dt_lbmolps"])
        for i in range(n_stages):
            for k, lbl in enumerate(comp_labels):
                w.writerow([final_time_s, i + 1, lbl, float(tray_L_dot[i, k]), float(tray_V_dot[i, k])])

    boundary_state_csv = logs / f"derivatives_boundary_states_{stamp}.csv"
    with boundary_state_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "state", "component", "dM_dt_lbmolps"])
        for k, lbl in enumerate(comp_labels):
            w.writerow([final_time_s, "top_L", lbl, float(top_L_dot[k]) if k < top_L_dot.size else np.nan])
            w.writerow([final_time_s, "top_V", lbl, float(top_V_dot[k]) if k < top_V_dot.size else np.nan])
            w.writerow([final_time_s, "bottom_L", lbl, float(bottom_L_dot[k]) if k < bottom_L_dot.size else np.nan])

    print(f"t_final_s={final_time_s:.6f}")
    print("Stage | dML/dt (lbmol/s) | dMV/dt (lbmol/s) | dT/dt (F/s)")
    for i in range(n_stages):
        print(f"{i + 1:>5} | {tray_ML_dot[i]:>16.6f} | {tray_MV_dot[i]:>16.6f} | {tray_T_dot[i]:>11.6f}")

    print("Boundary-state derivatives (lbmol/s)")
    for k, lbl in enumerate(comp_labels):
        tl = float(top_L_dot[k]) if k < top_L_dot.size else np.nan
        tv = float(top_V_dot[k]) if k < top_V_dot.size else np.nan
        bl = float(bottom_L_dot[k]) if k < bottom_L_dot.size else np.nan
        print(f"{lbl}: d(top_L)/dt={tl:+.6f}, d(top_V)/dt={tv:+.6f}, d(bottom_L)/dt={bl:+.6f}")

    print(f"Wrote: {stage_totals_csv}")
    print(f"Wrote: {stage_component_csv}")
    print(f"Wrote: {boundary_state_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
