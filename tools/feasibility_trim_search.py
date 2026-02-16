#!/usr/bin/env python
"""
Feasibility trim search for distillate/bottoms composition targets.

Purpose
-------
Determine whether the current dynamic model can reach a pair of composition
targets with fixed manipulated variables (no active PI loops).

Method
------
- Multi-start search over fixed reflux and boilup.
- For each candidate, run the dynamic model to settle.
- Evaluate final xD/xB mismatch and rank candidates by objective score.

Outputs
-------
- CSV of all candidate evaluations (default: logs/feasibility_trim_search_*.csv)
- Console summary of best candidates and feasibility verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import contextlib
import csv
import datetime as _dt
import io
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from dynamic_distillation.excel_case_loader_v1 import CaseData, load_case_from_excel
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case, ColumnSpec
from dynamic_distillation.dynamic_run_scaffold_v1 import (
    RunnerConfig,
    _component_index_by_name,
    run_smoke_simulation,
)
from dynamic_distillation.experiment_ledger_v1 import (
    append_run_registry_entry,
    rebuild_experiment_ledger,
)


@dataclass(frozen=True)
class Candidate:
    run_index: int
    source: str
    reflux_lbmolph: float
    boilup_lbmolph: float


@dataclass
class EvalResult:
    run_index: int
    source: str
    reflux_lbmolph: float
    boilup_lbmolph: float
    ok: bool
    error: str
    xD: float
    xB: float
    xD_sp: float
    xB_sp: float
    xD_err_abs: float
    xB_err_abs: float
    P_top_psia: float
    P_top_sp_psia: float
    P_top_err_abs: float
    dM_total_dt_lbmolph: float
    global_mass_closure_error_lbmolph: float
    score: float
    feasible: bool
    elapsed_wall_s: float


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_float(x: Any, default: float = math.nan) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    if not np.isfinite(v):
        return default
    return v


def _spec_float(specs: Dict[str, Any], keys: Sequence[str]) -> Optional[float]:
    for k in keys:
        if k not in specs:
            continue
        v = _safe_float(specs.get(k), default=math.nan)
        if np.isfinite(v):
            return float(v)
    return None


def _norm_key(s: Any) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _stream_dict_by_alias(case: CaseData, aliases: Sequence[str]) -> Optional[Dict[str, Any]]:
    streams = getattr(case, "streams", None)
    if not isinstance(streams, dict):
        return None
    alias_norm = {_norm_key(a) for a in aliases}
    for k, v in streams.items():
        if _norm_key(k) in alias_norm and isinstance(v, dict):
            return v
    return None


def _stream_total_lbmolph(stream: Dict[str, Any]) -> Optional[float]:
    for k in (
        "Total Molar Flow (lbmol/h)",
        "total molar flow (lbmol/h)",
        "total_molar_flow_lbmolph",
        "Total Flow (lbmol/h)",
    ):
        if k in stream:
            v = _safe_float(stream.get(k), default=math.nan)
            if np.isfinite(v) and v > 0.0:
                return float(v)
    return None


def _stream_component_fraction(
    *,
    case: CaseData,
    col: ColumnSpec,
    comp_idx: int,
    stream_aliases: Sequence[str],
) -> Optional[float]:
    stream = _stream_dict_by_alias(case, stream_aliases)
    if stream is None:
        return None
    cmap = stream.get("Component Mole Flows (lbmol/h)")
    if not isinstance(cmap, dict):
        return None
    cname = ""
    try:
        cname = str(np.asarray(getattr(col, "components_excel"), dtype=object).reshape((-1,))[int(comp_idx)])
    except Exception:
        return None
    target = _norm_key(cname)
    if not target:
        return None

    total = _stream_total_lbmolph(stream)
    if total is None or total <= 0.0:
        total = 0.0
        for _k, _v in cmap.items():
            vv = _safe_float(_v, default=math.nan)
            if np.isfinite(vv) and vv > 0.0:
                total += float(vv)
    if total <= 0.0:
        return None

    comp_flow = None
    for k, v in cmap.items():
        if _norm_key(k) == target:
            vv = _safe_float(v, default=math.nan)
            if np.isfinite(vv) and vv >= 0.0:
                comp_flow = float(vv)
                break
    if comp_flow is None:
        # Soft fallback (substring alias match)
        for k, v in cmap.items():
            nk = _norm_key(k)
            if target in nk or nk in target:
                vv = _safe_float(v, default=math.nan)
                if np.isfinite(vv) and vv >= 0.0:
                    comp_flow = float(vv)
                    break
    if comp_flow is None:
        return None
    return float(comp_flow) / float(total)


def _normalized_comp_from_holdup(holdup: Optional[np.ndarray], fallback: np.ndarray) -> np.ndarray:
    if holdup is None:
        z = np.asarray(fallback, dtype=float).reshape((-1,))
        s = float(np.sum(z))
        return z / max(s, 1e-300)
    h = np.asarray(holdup, dtype=float).reshape((-1,))
    s = float(np.sum(h))
    if (not np.isfinite(s)) or s <= 1e-300:
        z = np.asarray(fallback, dtype=float).reshape((-1,))
        s2 = float(np.sum(z))
        return z / max(s2, 1e-300)
    return h / s


def _extract_p_top(diag: Dict[str, np.ndarray], col: ColumnSpec) -> float:
    try:
        if "P_top_drum_psia" in diag:
            v = _safe_float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
            if np.isfinite(v) and v > 0.0:
                return float(v)
        if "P_psia_hyd" in diag:
            p = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((col.n_stages,))
            v = _safe_float(p[0])
            if np.isfinite(v) and v > 0.0:
                return float(v)
        if "P_psia_diag" in diag:
            p = np.asarray(diag["P_psia_diag"], dtype=float).reshape((col.n_stages,))
            v = _safe_float(p[0])
            if np.isfinite(v) and v > 0.0:
                return float(v)
    except Exception:
        pass
    try:
        p_spec = np.asarray(col.P_psia, dtype=float).reshape((col.n_stages,))
        return _safe_float(p_spec[0])
    except Exception:
        return math.nan


def _extract_objective_state(
    *,
    out: Dict[str, Any],
    idx_dist: int,
    idx_bottom: int,
) -> Tuple[float, float, float, float, float]:
    layout = out["layout"]
    y = np.asarray(out["final_state"], dtype=float)
    u = layout.unpack(y)
    col = out["column"]

    x_tray = np.asarray(u["x_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    top_L = u.get("top_L", None)
    bottom_L = u.get("bottom_L", None)

    xD_vec = _normalized_comp_from_holdup(top_L, x_tray[0, :])
    xB_vec = _normalized_comp_from_holdup(bottom_L, x_tray[-1, :])
    xD = float(xD_vec[idx_dist]) if 0 <= idx_dist < xD_vec.size else math.nan
    xB = float(xB_vec[idx_bottom]) if 0 <= idx_bottom < xB_vec.size else math.nan

    diag = out.get("last_diag", {}) or {}
    p_top = _extract_p_top(diag, col)
    p_top_sp = math.nan
    try:
        p_arr = np.asarray(col.P_psia, dtype=float).reshape((col.n_stages,))
        p_top_sp = _safe_float(p_arr[0])
    except Exception:
        pass

    dM = math.nan
    if "dM_total_dt_lbmolph" in diag:
        try:
            dM = _safe_float(np.asarray(diag["dM_total_dt_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            dM = math.nan

    gmc = math.nan
    if "global_mass_closure_error_lbmolph" in diag:
        try:
            gmc = _safe_float(np.asarray(diag["global_mass_closure_error_lbmolph"], dtype=float).reshape((-1,))[0])
        except Exception:
            gmc = math.nan

    return xD, xB, p_top, p_top_sp, dM, gmc


def _build_candidates(
    *,
    rng: np.random.Generator,
    n_random: int,
    reflux_min: float,
    reflux_max: float,
    boilup_min: float,
    boilup_max: float,
    reflux_baseline: float,
    boilup_baseline: float,
) -> List[Candidate]:
    out: List[Candidate] = []
    out.append(
        Candidate(
            run_index=1,
            source="baseline",
            reflux_lbmolph=float(reflux_baseline),
            boilup_lbmolph=float(boilup_baseline),
        )
    )

    idx = 2
    for _ in range(int(max(n_random, 0))):
        r = float(rng.uniform(float(reflux_min), float(reflux_max)))
        b = float(rng.uniform(float(boilup_min), float(boilup_max)))
        out.append(
            Candidate(
                run_index=idx,
                source="random",
                reflux_lbmolph=r,
                boilup_lbmolph=b,
            )
        )
        idx += 1
    return out


def _candidate_score(
    *,
    xD_err_abs: float,
    xB_err_abs: float,
    p_top_err_abs: float,
    p_top_sp: float,
    dM_total_dt_lbmolph: float,
    pressure_weight: float,
    inventory_weight: float,
) -> float:
    score = float(xD_err_abs) + float(xB_err_abs)
    if np.isfinite(p_top_err_abs) and np.isfinite(p_top_sp) and p_top_sp > 0.0:
        score += float(pressure_weight) * (float(p_top_err_abs) / float(p_top_sp))
    if np.isfinite(dM_total_dt_lbmolph):
        score += float(inventory_weight) * (abs(float(dM_total_dt_lbmolph)) / 1000.0)
    return float(score)


def _resolve_component_index(col: ColumnSpec, name: str) -> int:
    idx = _component_index_by_name(col, name)
    if idx is not None:
        return int(idx)
    # Strict fallback.
    comps = [str(c) for c in getattr(col, "components_excel", [])]
    for i, c in enumerate(comps):
        if c.strip().lower() == str(name).strip().lower():
            return int(i)
    raise ValueError(f"Could not resolve component index for '{name}'.")


def _run_candidate(
    *,
    cand: Candidate,
    base_cfg: RunnerConfig,
    idx_dist: int,
    idx_bottom: int,
    xD_sp: float,
    xB_sp: float,
    tol_xd: float,
    tol_xb: float,
    pressure_weight: float,
    inventory_weight: float,
    suppress_runner_output: bool,
) -> EvalResult:
    cfg = RunnerConfig(
        **{
            **base_cfg.__dict__,
            "reflux_lbmolph": float(cand.reflux_lbmolph),
            "boilup_lbmolph": float(cand.boilup_lbmolph),
            "enable_level_control": False,
            "enable_distillate_composition_control": False,
            "enable_bottoms_composition_control": False,
            "write_logs": False,
        }
    )

    t0 = _dt.datetime.now()
    try:
        if suppress_runner_output:
            with contextlib.redirect_stdout(io.StringIO()):
                out = run_smoke_simulation(cfg)
        else:
            out = run_smoke_simulation(cfg)
        xD, xB, p_top, p_top_sp, dM, gmc = _extract_objective_state(
            out=out,
            idx_dist=idx_dist,
            idx_bottom=idx_bottom,
        )
        xD_err = abs(float(xD) - float(xD_sp)) if np.isfinite(xD) else math.inf
        xB_err = abs(float(xB) - float(xB_sp)) if np.isfinite(xB) else math.inf
        p_err = abs(float(p_top) - float(p_top_sp)) if np.isfinite(p_top) and np.isfinite(p_top_sp) else math.nan
        score = _candidate_score(
            xD_err_abs=xD_err,
            xB_err_abs=xB_err,
            p_top_err_abs=p_err,
            p_top_sp=p_top_sp,
            dM_total_dt_lbmolph=dM,
            pressure_weight=pressure_weight,
            inventory_weight=inventory_weight,
        )
        feasible = bool(np.isfinite(xD_err) and np.isfinite(xB_err) and xD_err <= tol_xd and xB_err <= tol_xb)
        elapsed = (_dt.datetime.now() - t0).total_seconds()
        return EvalResult(
            run_index=cand.run_index,
            source=cand.source,
            reflux_lbmolph=float(cand.reflux_lbmolph),
            boilup_lbmolph=float(cand.boilup_lbmolph),
            ok=True,
            error="",
            xD=float(xD),
            xB=float(xB),
            xD_sp=float(xD_sp),
            xB_sp=float(xB_sp),
            xD_err_abs=float(xD_err),
            xB_err_abs=float(xB_err),
            P_top_psia=float(p_top),
            P_top_sp_psia=float(p_top_sp),
            P_top_err_abs=float(p_err) if np.isfinite(p_err) else math.nan,
            dM_total_dt_lbmolph=float(dM),
            global_mass_closure_error_lbmolph=float(gmc),
            score=float(score),
            feasible=bool(feasible),
            elapsed_wall_s=float(elapsed),
        )
    except Exception as exc:
        elapsed = (_dt.datetime.now() - t0).total_seconds()
        return EvalResult(
            run_index=cand.run_index,
            source=cand.source,
            reflux_lbmolph=float(cand.reflux_lbmolph),
            boilup_lbmolph=float(cand.boilup_lbmolph),
            ok=False,
            error=str(exc),
            xD=math.nan,
            xB=math.nan,
            xD_sp=float(xD_sp),
            xB_sp=float(xB_sp),
            xD_err_abs=math.inf,
            xB_err_abs=math.inf,
            P_top_psia=math.nan,
            P_top_sp_psia=math.nan,
            P_top_err_abs=math.nan,
            dM_total_dt_lbmolph=math.nan,
            global_mass_closure_error_lbmolph=math.nan,
            score=1.0e12,
            feasible=False,
            elapsed_wall_s=float(elapsed),
        )


def _write_results_csv(path: Path, rows: Sequence[EvalResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_index",
        "source",
        "reflux_lbmolph",
        "boilup_lbmolph",
        "ok",
        "error",
        "xD",
        "xB",
        "xD_sp",
        "xB_sp",
        "xD_err_abs",
        "xB_err_abs",
        "P_top_psia",
        "P_top_sp_psia",
        "P_top_err_abs",
        "dM_total_dt_lbmolph",
        "global_mass_closure_error_lbmolph",
        "score",
        "feasible",
        "elapsed_wall_s",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r.__dict__)


def _default_output_path(project_root: Path) -> Path:
    tag = _timestamp_tag()
    return project_root / "logs" / f"feasibility_trim_search_{tag}.csv"


def main() -> int:
    ap = argparse.ArgumentParser(description="Feasibility trim search (fixed-MV, no PI loops).")
    ap.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    ap.add_argument("--thermo", dest="thermo_mode", choices=["stub", "dwsim", "table"], default="table")
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--thermo-cache", dest="thermo_cache_path", default=None)
    ap.add_argument("--thermo-every", dest="thermo_every_n_steps", type=int, default=1)
    ap.add_argument("--include-energy", dest="include_energy", action="store_true")
    ap.add_argument("--no-equilibrium", dest="enable_equilibrium_relaxation", action="store_false")
    ap.set_defaults(enable_equilibrium_relaxation=True)
    ap.add_argument("--n-steps", dest="n_steps", type=int, default=1200)
    ap.add_argument("--dt", dest="dt_sec", type=float, default=0.2)
    ap.add_argument("--log-every", dest="log_every_n_steps", type=int, default=200)

    ap.add_argument("--distillate-comp-component", dest="dist_comp", default="C4")
    ap.add_argument("--bottoms-comp-component", dest="bot_comp", default="C5")
    ap.add_argument("--xD-sp", dest="xD_sp", type=float, default=None)
    ap.add_argument("--xB-sp", dest="xB_sp", type=float, default=None)
    ap.add_argument("--tol-xd", dest="tol_xd", type=float, default=0.002)
    ap.add_argument("--tol-xb", dest="tol_xb", type=float, default=0.002)

    ap.add_argument("--reflux-min", dest="reflux_min", type=float, default=None)
    ap.add_argument("--reflux-max", dest="reflux_max", type=float, default=None)
    ap.add_argument("--boilup-min", dest="boilup_min", type=float, default=None)
    ap.add_argument("--boilup-max", dest="boilup_max", type=float, default=None)
    ap.add_argument("--n-random", dest="n_random", type=int, default=24)
    ap.add_argument("--seed", dest="seed", type=int, default=42)

    ap.add_argument("--pressure-weight", dest="pressure_weight", type=float, default=0.05)
    ap.add_argument("--inventory-weight", dest="inventory_weight", type=float, default=0.02)
    ap.add_argument(
        "--enforce-top-pressure",
        dest="enforce_top_pressure",
        action="store_true",
        help="Enable top-pressure PI control during feasibility runs.",
    )
    ap.add_argument(
        "--pressure-control-mv",
        dest="pressure_control_mv",
        choices=["top-anchor", "condenser-duty"],
        default="top-anchor",
        help="Pressure controller MV used when --enforce-top-pressure is set.",
    )
    ap.add_argument("--top-pressure-sp", dest="top_pressure_sp", type=float, default=None)
    ap.add_argument("--top-pressure-kc", dest="top_pressure_kc", type=float, default=None)
    ap.add_argument("--top-pressure-ti", dest="top_pressure_ti", type=float, default=None)
    ap.add_argument("--top-pressure-anchor-min", dest="top_pressure_anchor_min", type=float, default=None)
    ap.add_argument("--top-pressure-anchor-max", dest="top_pressure_anchor_max", type=float, default=None)
    ap.add_argument("--condenser-duty-btuph", dest="condenser_duty_btu_per_h", type=float, default=None)
    ap.add_argument("--condenser-duty-min-btuph", dest="condenser_duty_min_btu_per_h", type=float, default=None)
    ap.add_argument("--condenser-duty-max-btuph", dest="condenser_duty_max_btu_per_h", type=float, default=None)
    ap.add_argument("--output-csv", dest="output_csv", default=None)
    ap.add_argument("--show-top", dest="show_top", type=int, default=10)
    ap.add_argument("--verbose-runs", dest="verbose_runs", action="store_true")

    raw_argv: List[str] = list(sys.argv[1:])
    args = ap.parse_args(raw_argv)

    project_root = Path(__file__).resolve().parents[1]
    excel_path = Path(args.excel_path)
    if not excel_path.is_absolute():
        excel_path = (project_root / excel_path).resolve()

    if str(args.thermo_mode).lower() == "table":
        tpath = Path(str(args.thermo_table_path or ""))
        if not tpath.is_absolute():
            tpath = (project_root / tpath).resolve()
        if not tpath.exists():
            raise FileNotFoundError(f"Thermo table not found: {tpath}")
        thermo_table_path = str(tpath)
    else:
        thermo_table_path = args.thermo_table_path

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    specs = getattr(col, "specs_raw", None) or {}

    idx_dist = _resolve_component_index(col, str(args.dist_comp))
    idx_bot = _resolve_component_index(col, str(args.bot_comp))

    xD_sp = args.xD_sp
    if xD_sp is None:
        xD_sp = _spec_float(specs, ("Distillate Composition SP", "Distillate C4 SP", "Distillate x SP"))
    if xD_sp is None:
        xD_sp = _stream_component_fraction(
            case=case,
            col=col,
            comp_idx=idx_dist,
            stream_aliases=("Distillate", "Top", "Overhead"),
        )
    if xD_sp is None:
        raise ValueError("Could not resolve xD setpoint. Pass --xD-sp explicitly.")

    xB_sp = args.xB_sp
    if xB_sp is None:
        xB_sp = _spec_float(specs, ("Bottoms Composition SP", "Bottoms C5 SP", "Bottoms x SP"))
    if xB_sp is None:
        xB_sp = _stream_component_fraction(
            case=case,
            col=col,
            comp_idx=idx_bot,
            stream_aliases=("Bottom", "Bottoms", "Bot"),
        )
    if xB_sp is None:
        raise ValueError("Could not resolve xB setpoint. Pass --xB-sp explicitly.")

    reflux_baseline = _safe_float(np.asarray(col.L_lbmolph, dtype=float).reshape((-1,))[0])
    boilup_baseline = _safe_float(np.asarray(col.V_lbmolph, dtype=float).reshape((-1,))[-1])
    if not np.isfinite(reflux_baseline) or reflux_baseline <= 0.0:
        reflux_baseline = 3000.0
    if not np.isfinite(boilup_baseline) or boilup_baseline <= 0.0:
        boilup_baseline = 5000.0

    reflux_min = float(args.reflux_min) if args.reflux_min is not None else max(0.25 * reflux_baseline, 100.0)
    reflux_max = float(args.reflux_max) if args.reflux_max is not None else max(2.5 * reflux_baseline, reflux_min + 500.0)
    boilup_min = float(args.boilup_min) if args.boilup_min is not None else max(0.25 * boilup_baseline, 100.0)
    boilup_max = float(args.boilup_max) if args.boilup_max is not None else max(2.5 * boilup_baseline, boilup_min + 500.0)
    if reflux_max <= reflux_min:
        reflux_max = reflux_min + 1.0
    if boilup_max <= boilup_min:
        boilup_max = boilup_min + 1.0

    p_top_sp_default = math.nan
    try:
        p_arr = np.asarray(col.P_psia, dtype=float).reshape((col.n_stages,))
        p_top_sp_default = _safe_float(p_arr[0])
    except Exception:
        p_top_sp_default = math.nan
    p_top_sp = float(args.top_pressure_sp) if args.top_pressure_sp is not None else p_top_sp_default
    if args.enforce_top_pressure and (not np.isfinite(p_top_sp) or p_top_sp <= 0.0):
        raise ValueError("Top pressure SP is required for --enforce-top-pressure.")

    pressure_mv_mode = str(args.pressure_control_mv).strip().lower().replace("_", "-")

    # Choose pressure PI defaults consistent with runner behavior.
    top_pressure_kc = args.top_pressure_kc
    if top_pressure_kc is None:
        top_pressure_kc = -1.0 if pressure_mv_mode == "top-anchor" else -5.0e5
    top_pressure_ti = args.top_pressure_ti
    if top_pressure_ti is None:
        top_pressure_ti = 60.0 if pressure_mv_mode == "top-anchor" else 120.0

    p_anchor_min = args.top_pressure_anchor_min
    p_anchor_max = args.top_pressure_anchor_max
    if args.enforce_top_pressure and pressure_mv_mode == "top-anchor" and p_anchor_min is None and np.isfinite(p_top_sp):
        p_anchor_min = float(p_top_sp) - 40.0
    if args.enforce_top_pressure and pressure_mv_mode == "top-anchor" and p_anchor_max is None and np.isfinite(p_top_sp):
        p_anchor_max = float(p_top_sp) + 40.0
    if p_anchor_min is not None and p_anchor_max is not None and float(p_anchor_max) < float(p_anchor_min):
        p_anchor_min, p_anchor_max = p_anchor_max, p_anchor_min

    use_pressure = bool(args.enforce_top_pressure)
    condenser_duty_mode = "total-condense"
    if use_pressure and pressure_mv_mode == "condenser-duty":
        condenser_duty_mode = "specified"

    base_cfg = RunnerConfig(
        excel_path=str(excel_path),
        n_steps=int(args.n_steps),
        dt_sec=float(args.dt_sec) if args.dt_sec is not None else None,
        log_every_n_steps=int(args.log_every_n_steps) if args.log_every_n_steps is not None else None,
        include_temperature=True,
        include_energy=bool(args.include_energy),
        enable_equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
        thermo_mode=str(args.thermo_mode),
        thermo_every_n_steps=max(int(args.thermo_every_n_steps), 1),
        thermo_table_path=thermo_table_path,
        thermo_cache_path=args.thermo_cache_path,
        reflux_lbmolph=float(reflux_baseline),
        boilup_lbmolph=float(boilup_baseline),
        condenser_duty_mode=str(condenser_duty_mode),
        condenser_duty_btu_per_h=(
            float(args.condenser_duty_btu_per_h) if args.condenser_duty_btu_per_h is not None else None
        ),
        condenser_duty_min_btu_per_h=(
            float(args.condenser_duty_min_btu_per_h) if args.condenser_duty_min_btu_per_h is not None else None
        ),
        condenser_duty_max_btu_per_h=(
            float(args.condenser_duty_max_btu_per_h) if args.condenser_duty_max_btu_per_h is not None else None
        ),
        enable_level_control=False,
        enable_pressure_control=bool(use_pressure),
        pressure_control_mv=str(pressure_mv_mode) if bool(use_pressure) else "auto",
        top_pressure_sp_psia=float(p_top_sp) if bool(use_pressure) else None,
        top_pressure_kc=float(top_pressure_kc) if bool(use_pressure) else None,
        top_pressure_ti_sec=float(top_pressure_ti) if bool(use_pressure) else None,
        top_pressure_anchor_min_psia=(
            float(p_anchor_min) if (p_anchor_min is not None and pressure_mv_mode == "top-anchor") else None
        ),
        top_pressure_anchor_max_psia=(
            float(p_anchor_max) if (p_anchor_max is not None and pressure_mv_mode == "top-anchor") else None
        ),
        enable_distillate_composition_control=False,
        enable_bottoms_composition_control=False,
        write_logs=False,
        logs_dir=str(project_root / "logs"),
    )

    rng = np.random.default_rng(int(args.seed))
    candidates = _build_candidates(
        rng=rng,
        n_random=int(args.n_random),
        reflux_min=float(reflux_min),
        reflux_max=float(reflux_max),
        boilup_min=float(boilup_min),
        boilup_max=float(boilup_max),
        reflux_baseline=float(reflux_baseline),
        boilup_baseline=float(boilup_baseline),
    )

    print("Feasibility trim search")
    print(f"Excel: {excel_path}")
    print(f"Thermo: {args.thermo_mode}")
    print(f"Targets: xD({args.dist_comp})={xD_sp:.8f}, xB({args.bot_comp})={xB_sp:.8f}")
    if args.enforce_top_pressure:
        if pressure_mv_mode == "top-anchor":
            print(
                f"Pressure constraint: on ({pressure_mv_mode} PI), SP={p_top_sp:.4f} psia, "
                f"Kc={float(top_pressure_kc):.4g}, Ti={float(top_pressure_ti):.4g} s, "
                f"anchor=[{float(p_anchor_min):.3f}, {float(p_anchor_max):.3f}]"
            )
        else:
            qbias_txt = (
                f"{float(args.condenser_duty_btu_per_h):.6g}"
                if args.condenser_duty_btu_per_h is not None
                else "auto"
            )
            qmin_txt = (
                f"{float(args.condenser_duty_min_btu_per_h):.6g}"
                if args.condenser_duty_min_btu_per_h is not None
                else "auto"
            )
            qmax_txt = (
                f"{float(args.condenser_duty_max_btu_per_h):.6g}"
                if args.condenser_duty_max_btu_per_h is not None
                else "auto"
            )
            print(
                f"Pressure constraint: on ({pressure_mv_mode} PI), SP={p_top_sp:.4f} psia, "
                f"Kc={float(top_pressure_kc):.4g}, Ti={float(top_pressure_ti):.4g} s, "
                f"condenser-duty-mode={condenser_duty_mode}, "
                f"Qbias={qbias_txt}, Qmin={qmin_txt}, Qmax={qmax_txt}"
            )
    else:
        print("Pressure constraint: off")
    print(
        f"Bounds: reflux=[{reflux_min:.3f}, {reflux_max:.3f}] lbmol/h, "
        f"boilup=[{boilup_min:.3f}, {boilup_max:.3f}] lbmol/h"
    )
    print(f"Candidates: {len(candidates)} (baseline + {int(args.n_random)} random)")

    results: List[EvalResult] = []
    for c in candidates:
        print(
            f"[{c.run_index:03d}/{len(candidates):03d}] "
            f"source={c.source} reflux={c.reflux_lbmolph:.2f} boilup={c.boilup_lbmolph:.2f}"
        )
        r = _run_candidate(
            cand=c,
            base_cfg=base_cfg,
            idx_dist=idx_dist,
            idx_bottom=idx_bot,
            xD_sp=float(xD_sp),
            xB_sp=float(xB_sp),
            tol_xd=float(args.tol_xd),
            tol_xb=float(args.tol_xb),
            pressure_weight=float(args.pressure_weight),
            inventory_weight=float(args.inventory_weight),
            suppress_runner_output=(not bool(args.verbose_runs)),
        )
        results.append(r)
        if r.ok:
            print(
                f"      ok score={r.score:.6f} "
                f"|xD-sp|={r.xD_err_abs:.6f} |xB-sp|={r.xB_err_abs:.6f} "
                f"P_top={r.P_top_psia:.3f}"
            )
        else:
            print(f"      fail error={r.error}")

    good = [r for r in results if r.ok]
    good_sorted = sorted(good, key=lambda x: x.score)

    output_csv = Path(str(args.output_csv)) if args.output_csv else _default_output_path(project_root)
    if not output_csv.is_absolute():
        output_csv = (project_root / output_csv).resolve()
    _write_results_csv(output_csv, sorted(results, key=lambda x: x.run_index))
    try:
        append_run_registry_entry(
            logs_dir=(project_root / "logs"),
            module_name="tools/feasibility_trim_search.py",
            argv=raw_argv,
            summary_csv_path=str(output_csv),
            profile_csv_path=None,
        )
        rebuild_experiment_ledger(project_root=project_root)
    except Exception as exc:
        print(f"[Warn] Failed to update experiment ledger: {exc}")

    print("")
    print(f"Wrote: {output_csv}")
    print(f"Successful runs: {len(good)}/{len(results)}")
    if not good_sorted:
        print("No successful candidate runs. Cannot assess feasibility.")
        return 1

    n_show = max(1, int(args.show_top))
    print(f"Top {min(n_show, len(good_sorted))} candidates:")
    for r in good_sorted[:n_show]:
        print(
            f"  run={r.run_index:03d} source={r.source} "
            f"reflux={r.reflux_lbmolph:.2f} boilup={r.boilup_lbmolph:.2f} "
            f"score={r.score:.6f} xD={r.xD:.6f} xB={r.xB:.6f} "
            f"|dxD|={r.xD_err_abs:.6f} |dxB|={r.xB_err_abs:.6f} feasible={r.feasible}"
        )

    feasible = [r for r in good_sorted if r.feasible]
    if feasible:
        best = feasible[0]
        print("")
        print("Feasibility verdict: FEASIBLE under tested search space.")
        print(
            f"Best feasible: reflux={best.reflux_lbmolph:.3f}, boilup={best.boilup_lbmolph:.3f}, "
            f"xD={best.xD:.6f}, xB={best.xB:.6f}, score={best.score:.6f}"
        )
        return 0

    best = good_sorted[0]
    print("")
    print("Feasibility verdict: NOT demonstrated under tested search space.")
    print(
        f"Best found: reflux={best.reflux_lbmolph:.3f}, boilup={best.boilup_lbmolph:.3f}, "
        f"xD={best.xD:.6f}, xB={best.xB:.6f}, "
        f"|dxD|={best.xD_err_abs:.6f}, |dxB|={best.xB_err_abs:.6f}"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
