#!/usr/bin/env python
"""Audit generic feed-bearing stage balances from a dynamic profile CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _finite_float(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _read_rows(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _stage_rows(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in rows:
        if str(row.get("node_type", "")).strip().lower() != "stage":
            continue
        if not math.isfinite(_finite_float(row.get("stage"))):
            continue
        if not math.isfinite(_finite_float(row.get("time_s"))):
            continue
        out.append(row)
    return out


def _component_labels(rows: List[Dict[str, str]]) -> List[str]:
    if not rows:
        return []
    labels = []
    prefix = "x_"
    for key in rows[0].keys():
        if key.startswith(prefix):
            labels.append(key.removeprefix(prefix))
    return sorted(set(labels))


def _infer_feed_stage(rows: List[Dict[str, str]]) -> int:
    counts: Dict[int, int] = {}
    for row in rows:
        stage = _finite_float(row.get("feed_stage_1based"))
        if math.isfinite(stage):
            counts[int(round(stage))] = counts.get(int(round(stage)), 0) + 1
    if counts:
        return max(counts.items(), key=lambda kv: kv[1])[0]

    feed_by_stage: Dict[int, float] = {}
    for row in rows:
        stage = int(round(_finite_float(row.get("stage"))))
        val = abs(_finite_float(row.get("dMLdt_feed_lbmolps"), 0.0))
        feed_by_stage[stage] = max(feed_by_stage.get(stage, 0.0), val)
    if feed_by_stage and max(feed_by_stage.values()) > 0.0:
        return max(feed_by_stage.items(), key=lambda kv: kv[1])[0]
    raise ValueError("could not infer feed stage from feed_stage_1based or dMLdt_feed_lbmolps")


def _max_abs(rows: List[Dict[str, str]], field: str) -> Tuple[float, float]:
    best = (math.nan, math.nan)
    for row in rows:
        val = _finite_float(row.get(field))
        if not math.isfinite(val):
            continue
        cur = abs(val)
        if not math.isfinite(best[0]) or cur > best[0]:
            best = (cur, _finite_float(row.get("time_s")))
    return best


def _min_value(rows: List[Dict[str, str]], field: str) -> Tuple[float, float]:
    best = (math.nan, math.nan)
    for row in rows:
        val = _finite_float(row.get(field))
        if not math.isfinite(val):
            continue
        if not math.isfinite(best[0]) or val < best[0]:
            best = (val, _finite_float(row.get("time_s")))
    return best


def _max_step(rows: List[Dict[str, str]], field: str) -> Tuple[float, float, float, float]:
    best = (math.nan, math.nan, math.nan, math.nan)
    for prev, cur in zip(rows, rows[1:]):
        a = _finite_float(prev.get(field))
        b = _finite_float(cur.get(field))
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        step = abs(b - a)
        if not math.isfinite(best[0]) or step > best[0]:
            best = (step, _finite_float(cur.get("time_s")), a, b)
    return best


def _first_bad_time(summary_rows: List[Dict[str, str]], score_limit: float) -> float:
    for row in sorted(summary_rows, key=lambda r: _finite_float(r.get("time_s"))):
        score = _finite_float(row.get("steady_state_score"))
        if math.isfinite(score) and score > float(score_limit):
            return _finite_float(row.get("time_s"))
    return math.nan


def audit_profile(
    profile_rows: List[Dict[str, str]],
    *,
    summary_rows: Optional[List[Dict[str, str]]] = None,
    start_s: Optional[float] = None,
    end_s: Optional[float] = None,
    score_limit: float = 10.0,
    update_fraction_limit: float = 0.25,
    denominator_floor_lbmol: float = 1.0,
) -> Dict[str, Any]:
    stages = _stage_rows(profile_rows)
    if not stages:
        raise ValueError("profile CSV contains no stage rows")

    feed_stage = _infer_feed_stage(stages)
    feed_rows = [
        r
        for r in stages
        if int(round(_finite_float(r.get("stage")))) == feed_stage
        and (start_s is None or _finite_float(r.get("time_s")) >= float(start_s))
        and (end_s is None or _finite_float(r.get("time_s")) <= float(end_s))
    ]
    feed_rows = sorted(feed_rows, key=lambda r: _finite_float(r.get("time_s")))
    if not feed_rows:
        raise ValueError("no feed-stage rows remain after time filtering")

    summary_rows = list(summary_rows or [])
    if start_s is not None or end_s is not None:
        summary_rows = [
            r
            for r in summary_rows
            if (start_s is None or _finite_float(r.get("time_s")) >= float(start_s))
            and (end_s is None or _finite_float(r.get("time_s")) <= float(end_s))
        ]

    min_ml, min_ml_time = _min_value(feed_rows, "ML_lbmol")
    max_dml_abs, max_dml_time = _max_abs(feed_rows, "dMLdt_total_lbmolps")
    split_step, split_step_time, split_before, split_after = _max_step(feed_rows, "feed_effective_vapor_fraction")
    flash_flag_step, flash_flag_step_time, flash_flag_before, flash_flag_after = _max_step(
        feed_rows, "feed_flash_at_stage_conditions"
    )

    liquid_records = []
    worst_update_fraction = math.nan
    worst_update_time = math.nan
    for row in feed_rows:
        d_total = _finite_float(row.get("dMLdt_total_lbmolps"))
        d_transport = _finite_float(row.get("dMLdt_transport_lbmolps"), 0.0)
        d_phase = _finite_float(row.get("dMLdt_phase_relax_lbmolps"), 0.0)
        d_feed = _finite_float(row.get("dMLdt_feed_lbmolps"), 0.0)
        d_feed_total = _finite_float(row.get("feed_liquid_rate_lbmolps"))
        l_in = _finite_float(row.get("vflow_energy_L_in_lbmolph"))
        l_out = _finite_float(row.get("L_out_used_lbmolph"))
        l_out_hyd = _finite_float(row.get("L_out_hyd_lbmolph"))
        l_out_hyd_delta = (
            l_out - l_out_hyd if math.isfinite(l_out) and math.isfinite(l_out_hyd) else math.nan
        )
        l_out_hyd_ratio = (
            l_out / l_out_hyd
            if math.isfinite(l_out) and math.isfinite(l_out_hyd) and abs(l_out_hyd) > 1e-300
            else math.nan
        )
        pre_phase_from_flows = math.nan
        if math.isfinite(l_in) and math.isfinite(l_out):
            pre_phase_from_flows = (l_in - l_out) / 3600.0
            if math.isfinite(d_feed_total):
                pre_phase_from_flows += d_feed_total
            else:
                pre_phase_from_flows += d_feed
        closure = d_total - (d_transport + d_phase) if math.isfinite(d_total) else math.nan
        feed_resid = d_feed - d_feed_total if math.isfinite(d_feed_total) else math.nan
        pre_phase_resid = d_transport - pre_phase_from_flows if math.isfinite(pre_phase_from_flows) else math.nan
        liquid_records.append(
            {
                "time_s": _finite_float(row.get("time_s")),
                "ML_lbmol": _finite_float(row.get("ML_lbmol")),
                "dMLdt_total_lbmolps": d_total,
                "dMLdt_transport_lbmolps": d_transport,
                "dMLdt_phase_relax_lbmolps": d_phase,
                "dMLdt_feed_lbmolps": d_feed,
                "feed_liquid_rate_lbmolps": d_feed_total,
                "L_in_lbmolph": l_in,
                "L_out_used_lbmolph": l_out,
                "L_out_hyd_lbmolph": l_out_hyd,
                "L_out_used_minus_hyd_lbmolph": l_out_hyd_delta,
                "L_out_used_over_hyd": l_out_hyd_ratio,
                "liquid_total_closure_resid_lbmolps": closure,
                "feed_liquid_resid_lbmolps": feed_resid,
                "pre_phase_from_flows_lbmolps": pre_phase_from_flows,
                "pre_phase_flow_resid_lbmolps": pre_phase_resid,
                "feed_effective_vapor_fraction": _finite_float(row.get("feed_effective_vapor_fraction")),
                "feed_flash_at_stage_conditions": _finite_float(row.get("feed_flash_at_stage_conditions")),
            }
        )

    for prev, cur in zip(feed_rows, feed_rows[1:]):
        dt = _finite_float(cur.get("time_s")) - _finite_float(prev.get("time_s"))
        ml = _finite_float(prev.get("ML_lbmol"))
        dml = _finite_float(prev.get("dMLdt_total_lbmolps"))
        if math.isfinite(dt) and dt > 0.0 and math.isfinite(ml) and math.isfinite(dml):
            frac = abs(dml) * dt / max(abs(ml), float(denominator_floor_lbmol))
            if not math.isfinite(worst_update_fraction) or frac > worst_update_fraction:
                worst_update_fraction = frac
                worst_update_time = _finite_float(prev.get("time_s"))

    energy_records = []
    for row in feed_rows:
        vfeed = _finite_float(row.get("vflow_energy_feed_ref_term_BTUps"))
        tfeed = _finite_float(row.get("temp_energy_feed_ref_term_BTUps"))
        vp = _finite_float(row.get("vflow_energy_P_used_psia"))
        tp = _finite_float(row.get("temp_energy_P_used_psia"))
        energy_records.append(
            {
                "time_s": _finite_float(row.get("time_s")),
                "vflow_energy_feed_ref_term_BTUps": vfeed,
                "temp_energy_feed_ref_term_BTUps": tfeed,
                "feed_energy_term_delta_BTUps": (
                    tfeed - vfeed if math.isfinite(tfeed) and math.isfinite(vfeed) else math.nan
                ),
                "vflow_energy_resid_after_used_BTUps": _finite_float(
                    row.get("vflow_energy_resid_after_used_BTUps")
                ),
                "stage_energy_balance_resid_BTUps": _finite_float(row.get("stage_energy_balance_resid_BTUps")),
                "dT_energy_raw_F_per_s": _finite_float(row.get("dT_energy_raw_F_per_s")),
                "vflow_energy_P_used_psia": vp,
                "temp_energy_P_used_psia": tp,
                "pressure_basis_delta_psia": tp - vp if math.isfinite(tp) and math.isfinite(vp) else math.nan,
            }
        )

    components = _component_labels(feed_rows)
    component_records = []
    for comp in components:
        fields = {
            "x": f"x_{comp}",
            "y": f"y_{comp}",
            "x_eq": f"x_eq_{comp}",
            "y_eq": f"y_eq_{comp}",
            "K_state": f"K_state_{comp}",
            "K_thermo": f"K_thermo_{comp}",
            "v_feed": f"tray_V_feed_lbmolps_{comp}",
            "v_in": f"tray_V_transport_in_lbmolps_{comp}",
            "v_out": f"tray_V_transport_out_lbmolps_{comp}",
            "v_eq": f"tray_V_equilibrium_transfer_lbmolps_{comp}",
            "v_pre": f"tray_V_pre_equilibrium_rhs_lbmolps_{comp}",
            "v_final": f"tray_V_final_rhs_lbmolps_{comp}",
        }
        comp_step, comp_step_time, comp_before, comp_after = _max_step(feed_rows, fields["x"])
        pre_abs, pre_time = _max_abs(feed_rows, fields["v_pre"])
        final_abs, final_time = _max_abs(feed_rows, fields["v_final"])
        eq_abs, eq_time = _max_abs(feed_rows, fields["v_eq"])
        k_delta_abs = math.nan
        k_delta_time = math.nan
        for row in feed_rows:
            ks = _finite_float(row.get(fields["K_state"]))
            kt = _finite_float(row.get(fields["K_thermo"]))
            if math.isfinite(ks) and math.isfinite(kt):
                delta = abs(ks - kt)
                if not math.isfinite(k_delta_abs) or delta > k_delta_abs:
                    k_delta_abs = delta
                    k_delta_time = _finite_float(row.get("time_s"))
        component_records.append(
            {
                "component": comp,
                "max_liquid_composition_step": comp_step,
                "max_liquid_composition_step_time_s": comp_step_time,
                "liquid_composition_before": comp_before,
                "liquid_composition_after": comp_after,
                "max_abs_vapor_pre_equilibrium_rhs_lbmolps": pre_abs,
                "max_abs_vapor_pre_equilibrium_rhs_time_s": pre_time,
                "max_abs_vapor_final_rhs_lbmolps": final_abs,
                "max_abs_vapor_final_rhs_time_s": final_time,
                "max_abs_equilibrium_transfer_lbmolps": eq_abs,
                "max_abs_equilibrium_transfer_time_s": eq_time,
                "max_abs_K_state_minus_K_thermo": k_delta_abs,
                "max_abs_K_state_minus_K_thermo_time_s": k_delta_time,
            }
        )

    max_liq_closure, max_liq_closure_time = _max_from_records(
        liquid_records, "liquid_total_closure_resid_lbmolps"
    )
    max_feed_resid, max_feed_resid_time = _max_from_records(liquid_records, "feed_liquid_resid_lbmolps")
    max_pre_phase_resid, max_pre_phase_resid_time = _max_from_records(
        liquid_records, "pre_phase_flow_resid_lbmolps"
    )
    max_hyd_delta, max_hyd_delta_time = _max_from_records(liquid_records, "L_out_used_minus_hyd_lbmolph")
    max_energy_delta, max_energy_delta_time = _max_from_records(energy_records, "feed_energy_term_delta_BTUps")
    max_pressure_delta, max_pressure_delta_time = _max_from_records(energy_records, "pressure_basis_delta_psia")
    max_energy_resid, max_energy_resid_time = _max_from_records(energy_records, "stage_energy_balance_resid_BTUps")
    max_dT_raw, max_dT_raw_time = _max_from_records(energy_records, "dT_energy_raw_F_per_s")

    first_bad = _first_bad_time(summary_rows, score_limit) if summary_rows else math.nan
    final_score = math.nan
    peak_score = math.nan
    if summary_rows:
        ordered = sorted(summary_rows, key=lambda r: _finite_float(r.get("time_s")))
        final_score = _finite_float(ordered[-1].get("steady_state_score"))
        scores = [_finite_float(r.get("steady_state_score")) for r in ordered]
        scores = [s for s in scores if math.isfinite(s)]
        peak_score = max(scores) if scores else math.nan

    return {
        "feed_stage_1based": feed_stage,
        "time_start_s": _finite_float(feed_rows[0].get("time_s")),
        "time_end_s": _finite_float(feed_rows[-1].get("time_s")),
        "n_feed_stage_rows": len(feed_rows),
        "summary": {
            "min_ML_lbmol": min_ml,
            "min_ML_time_s": min_ml_time,
            "max_abs_dMLdt_total_lbmolps": max_dml_abs,
            "max_abs_dMLdt_total_time_s": max_dml_time,
            "max_feed_vapor_fraction_step": split_step,
            "max_feed_vapor_fraction_step_time_s": split_step_time,
            "feed_vapor_fraction_before": split_before,
            "feed_vapor_fraction_after": split_after,
            "max_feed_flash_flag_step": flash_flag_step,
            "max_feed_flash_flag_step_time_s": flash_flag_step_time,
            "feed_flash_flag_before": flash_flag_before,
            "feed_flash_flag_after": flash_flag_after,
            "worst_inventory_update_fraction": worst_update_fraction,
            "worst_inventory_update_fraction_time_s": worst_update_time,
            "max_abs_liquid_total_closure_resid_lbmolps": max_liq_closure,
            "max_abs_liquid_total_closure_resid_time_s": max_liq_closure_time,
            "max_abs_feed_liquid_resid_lbmolps": max_feed_resid,
            "max_abs_feed_liquid_resid_time_s": max_feed_resid_time,
            "max_abs_pre_phase_flow_resid_lbmolps": max_pre_phase_resid,
            "max_abs_pre_phase_flow_resid_time_s": max_pre_phase_resid_time,
            "max_abs_L_out_used_minus_hyd_lbmolph": max_hyd_delta,
            "max_abs_L_out_used_minus_hyd_time_s": max_hyd_delta_time,
            "max_abs_feed_energy_term_delta_BTUps": max_energy_delta,
            "max_abs_feed_energy_term_delta_time_s": max_energy_delta_time,
            "max_abs_pressure_basis_delta_psia": max_pressure_delta,
            "max_abs_pressure_basis_delta_time_s": max_pressure_delta_time,
            "max_abs_stage_energy_balance_resid_BTUps": max_energy_resid,
            "max_abs_stage_energy_balance_resid_time_s": max_energy_resid_time,
            "max_abs_dT_energy_raw_F_per_s": max_dT_raw,
            "max_abs_dT_energy_raw_time_s": max_dT_raw_time,
            "first_score_above_limit_time_s": first_bad,
            "score_limit": float(score_limit),
            "peak_score": peak_score,
            "final_score": final_score,
        },
        "top_components_by_liquid_composition_step": sorted(
            component_records,
            key=lambda r: (
                -r["max_liquid_composition_step"]
                if math.isfinite(float(r["max_liquid_composition_step"]))
                else math.inf
            ),
        ),
        "top_components_by_vapor_rhs": sorted(
            component_records,
            key=lambda r: (
                -r["max_abs_vapor_final_rhs_lbmolps"]
                if math.isfinite(float(r["max_abs_vapor_final_rhs_lbmolps"]))
                else math.inf
            ),
        ),
        "liquid_records": liquid_records,
        "energy_records": energy_records,
        "component_records": component_records,
    }


def _max_from_records(records: List[Dict[str, Any]], field: str) -> Tuple[float, float]:
    best = (math.nan, math.nan)
    for rec in records:
        val = _finite_float(rec.get(field))
        if not math.isfinite(val):
            continue
        cur = abs(val)
        if not math.isfinite(best[0]) or cur > best[0]:
            best = (cur, _finite_float(rec.get("time_s")))
    return best


def _fmt(value: Any, digits: int = 6) -> str:
    try:
        f = float(value)
    except Exception:
        return str(value)
    if not math.isfinite(f):
        return "nan"
    return f"{f:.{digits}g}"


def write_markdown(report: Dict[str, Any], path: str | Path, *, profile_csv: str | Path) -> None:
    s = report["summary"]
    lines = [
        "# Feed Stage Equation Audit",
        "",
        f"Profile: `{Path(profile_csv).resolve()}`",
        "",
        "## Summary",
        "",
        "| Check | Value |",
        "|---|---:|",
        f"| feed stage, 1-based | {report['feed_stage_1based']} |",
        f"| time window, s | {_fmt(report['time_start_s'])} to {_fmt(report['time_end_s'])} |",
        f"| feed-stage rows | {report['n_feed_stage_rows']} |",
        f"| min liquid inventory, lbmol | {_fmt(s['min_ML_lbmol'])} at {_fmt(s['min_ML_time_s'])} s |",
        f"| max feed vapor-fraction step | {_fmt(s['max_feed_vapor_fraction_step'])} at {_fmt(s['max_feed_vapor_fraction_step_time_s'])} s |",
        f"| worst inventory update fraction | {_fmt(s['worst_inventory_update_fraction'])} at {_fmt(s['worst_inventory_update_fraction_time_s'])} s |",
        f"| max liquid closure residual, lbmol/s | {_fmt(s['max_abs_liquid_total_closure_resid_lbmolps'])} |",
        f"| max feed-liquid residual, lbmol/s | {_fmt(s['max_abs_feed_liquid_resid_lbmolps'])} |",
        f"| max pre-phase flow residual, lbmol/s | {_fmt(s['max_abs_pre_phase_flow_resid_lbmolps'])} |",
        f"| max `L_out_used - L_out_hyd`, lbmol/h | {_fmt(s['max_abs_L_out_used_minus_hyd_lbmolph'])} at {_fmt(s['max_abs_L_out_used_minus_hyd_time_s'])} s |",
        f"| max feed energy term delta, BTU/s | {_fmt(s['max_abs_feed_energy_term_delta_BTUps'])} |",
        f"| max pressure-basis delta, psi | {_fmt(s['max_abs_pressure_basis_delta_psia'])} |",
        f"| max stage energy residual, BTU/s | {_fmt(s['max_abs_stage_energy_balance_resid_BTUps'])} |",
        f"| max raw dT, F/s | {_fmt(s['max_abs_dT_energy_raw_F_per_s'])} |",
        f"| first score above {_fmt(s['score_limit'])} | {_fmt(s['first_score_above_limit_time_s'])} s |",
        f"| peak score | {_fmt(s['peak_score'])} |",
        f"| final score | {_fmt(s['final_score'])} |",
        "",
        "## Interpretation",
        "",
        "- This audit is keyed to the generic feed-bearing stage inferred from `feed_stage_1based`.",
        "- `liquid_total_closure_resid` checks `dMLdt_total - (pre_phase_liquid + phase_relax)`.",
        "- `feed_liquid_resid` checks whether the liquid feed source equals the reported feed liquid rate.",
        "- `pre_phase_flow_resid` compares the pre-equilibrium liquid derivative against logged liquid in/out traffic plus feed.",
        "- `L_out_used - L_out_hyd` shows whether the marched liquid traffic follows the hydraulic candidate or a profile/blended flow.",
        "- Large feed vapor-fraction steps plus low liquid inventory identify timestep-sensitive composition updates.",
        "",
        "## Liquid Balance Samples",
        "",
        "| time_s | ML_lbmol | feed_vf | dMLdt_total | feed_L | L_out_used | L_out_hyd | used-hyd | liquid_closure | pre_phase_flow_resid |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rec in _representative_records(report["liquid_records"]):
        lines.append(
            "| "
            + " | ".join(
                [
                    _fmt(rec["time_s"]),
                    _fmt(rec["ML_lbmol"]),
                    _fmt(rec["feed_effective_vapor_fraction"]),
                    _fmt(rec["dMLdt_total_lbmolps"]),
                    _fmt(rec["feed_liquid_rate_lbmolps"]),
                    _fmt(rec["L_out_used_lbmolph"]),
                    _fmt(rec["L_out_hyd_lbmolph"]),
                    _fmt(rec["L_out_used_minus_hyd_lbmolph"]),
                    _fmt(rec["liquid_total_closure_resid_lbmolps"]),
                    _fmt(rec["pre_phase_flow_resid_lbmolps"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Energy Basis Samples",
            "",
            "| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for rec in _representative_records(report["energy_records"]):
        lines.append(
            "| "
            + " | ".join(
                [
                    _fmt(rec["time_s"]),
                    _fmt(rec["feed_energy_term_delta_BTUps"]),
                    _fmt(rec["pressure_basis_delta_psia"]),
                    _fmt(rec["stage_energy_balance_resid_BTUps"]),
                    _fmt(rec["dT_energy_raw_F_per_s"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Components By Liquid Composition Step",
            "",
            "| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for rec in report["top_components_by_liquid_composition_step"][:10]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rec["component"]),
                    _fmt(rec["max_liquid_composition_step"]),
                    _fmt(rec["max_liquid_composition_step_time_s"]),
                    _fmt(rec["liquid_composition_before"]),
                    _fmt(rec["liquid_composition_after"]),
                    _fmt(rec["max_abs_vapor_final_rhs_lbmolps"]),
                    _fmt(rec["max_abs_equilibrium_transfer_lbmolps"]),
                    _fmt(rec["max_abs_K_state_minus_K_thermo"]),
                ]
            )
            + " |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _representative_records(records: List[Dict[str, Any]], max_rows: int = 12) -> List[Dict[str, Any]]:
    if len(records) <= max_rows:
        return records
    idxs = {0, len(records) - 1}
    for frac in (0.25, 0.5, 0.75):
        idxs.add(int(round((len(records) - 1) * frac)))
    for key in ("ML_lbmol", "dMLdt_total_lbmolps", "feed_effective_vapor_fraction"):
        vals = []
        for i, rec in enumerate(records):
            v = _finite_float(rec.get(key))
            if math.isfinite(v):
                vals.append((abs(v), i))
        if vals:
            idxs.add(max(vals)[1])
            idxs.add(min(vals)[1])
    return [records[i] for i in sorted(i for i in idxs if 0 <= i < len(records))][:max_rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-csv", required=True)
    parser.add_argument("--summary-csv", default=None)
    parser.add_argument("--start-s", type=float, default=None)
    parser.add_argument("--end-s", type=float, default=None)
    parser.add_argument("--score-limit", type=float, default=10.0)
    parser.add_argument("--update-fraction-limit", type=float, default=0.25)
    parser.add_argument("--denominator-floor-lbmol", type=float, default=1.0)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    args = parser.parse_args()

    profile_rows = _read_rows(args.profile_csv)
    summary_rows = _read_rows(args.summary_csv) if args.summary_csv else None
    report = audit_profile(
        profile_rows,
        summary_rows=summary_rows,
        start_s=args.start_s,
        end_s=args.end_s,
        score_limit=float(args.score_limit),
        update_fraction_limit=float(args.update_fraction_limit),
        denominator_floor_lbmol=float(args.denominator_floor_lbmol),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md, profile_csv=args.profile_csv)
    if not args.output_json and not args.output_md:
        print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "Audited feed stage "
        f"{report['feed_stage_1based']}; "
        f"rows={report['n_feed_stage_rows']}; "
        f"min_ML={_fmt(report['summary']['min_ML_lbmol'])}; "
        f"max_feed_vf_step={_fmt(report['summary']['max_feed_vapor_fraction_step'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
