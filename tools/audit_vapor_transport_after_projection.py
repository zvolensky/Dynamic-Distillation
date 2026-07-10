#!/usr/bin/env python
"""
Audit first-step vapor composition drift after an initialization projection.

This tool reads profile CSV logs only. It does not recompute thermo or call the
RHS. The goal is to answer whether a projected vapor state stays near the live
equilibrium target during the first logged step, and which generic transport
interfaces appear to pull it away.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


def _finite_float(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def _read_csv(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _stage(row: Dict[str, str]) -> int:
    return int(round(_finite_float(row.get("stage"))))


def _time(row: Dict[str, str]) -> float:
    return _finite_float(row.get("time_s"))


def _component_labels(row: Dict[str, str]) -> List[str]:
    labels: List[str] = []
    for key in row.keys():
        if key.startswith("y_") and not key.startswith("y_eq_") and not key.startswith("y_target_"):
            labels.append(key[2:])
    return sorted(labels)


def _arr(row: Dict[str, str], prefix: str, labels: Iterable[str]) -> np.ndarray:
    return np.asarray([_finite_float(row.get(f"{prefix}{label}")) for label in labels], dtype=float)


def _norm(vec: np.ndarray, fallback: Optional[np.ndarray] = None) -> np.ndarray:
    arr = np.asarray(vec, dtype=float).reshape((-1,))
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.clip(arr, 0.0, None)
    s = float(np.sum(arr))
    if s <= 1.0e-300:
        if fallback is not None:
            fb = np.asarray(fallback, dtype=float).reshape((-1,))
            fb = np.where(np.isfinite(fb), fb, 0.0)
            fb = np.clip(fb, 0.0, None)
            sf = float(np.sum(fb))
            if sf > 1.0e-300:
                return fb / sf
        return np.full(arr.shape, 1.0 / max(arr.size, 1), dtype=float)
    return arr / s


def _stage_rows(rows: List[Dict[str, str]], time_s: float) -> List[Dict[str, str]]:
    out = [
        r
        for r in rows
        if str(r.get("node_type", "")).strip().lower() == "stage"
        and math.isfinite(_time(r))
        and abs(_time(r) - float(time_s)) <= 1.0e-9
    ]
    return sorted(out, key=_stage)


def _infer_initial_final_times(rows: List[Dict[str, str]]) -> Tuple[float, float]:
    times = sorted(
        {
            _time(r)
            for r in rows
            if str(r.get("node_type", "")).strip().lower() == "stage" and math.isfinite(_time(r))
        }
    )
    if len(times) < 2:
        raise ValueError("Need at least two logged stage times")
    return float(times[0]), float(times[1])


def _dominant_component(labels: List[str], values: np.ndarray) -> Tuple[str, float]:
    vals = np.asarray(values, dtype=float).reshape((-1,))
    finite = np.where(np.isfinite(vals), np.abs(vals), -math.inf)
    if finite.size == 0 or not np.isfinite(float(np.max(finite))):
        return "", math.nan
    idx = int(np.argmax(finite))
    return labels[idx], float(vals[idx])


def audit_profile(
    profile_csv: str | Path,
    *,
    initial_time_s: Optional[float] = None,
    final_time_s: Optional[float] = None,
    top_n: int = 12,
) -> Dict[str, Any]:
    rows_all = _read_csv(profile_csv)
    if initial_time_s is None or final_time_s is None:
        t0, t1 = _infer_initial_final_times(rows_all)
        if initial_time_s is None:
            initial_time_s = t0
        if final_time_s is None:
            final_time_s = t1
    rows0 = _stage_rows(rows_all, float(initial_time_s))
    rows1 = _stage_rows(rows_all, float(final_time_s))
    if not rows0 or not rows1:
        raise ValueError("Missing stage rows at requested initial/final times")
    by_stage0 = {_stage(r): r for r in rows0}
    by_stage1 = {_stage(r): r for r in rows1}
    common_stages = sorted(set(by_stage0) & set(by_stage1))
    labels = _component_labels(rows1[0])
    if not labels:
        raise ValueError("No component y_* columns found")
    dt = float(final_time_s) - float(initial_time_s)
    if not math.isfinite(dt) or dt <= 0.0:
        raise ValueError("final time must be greater than initial time")

    stage_records: List[Dict[str, Any]] = []
    component_records: List[Dict[str, Any]] = []
    interface_records: List[Dict[str, Any]] = []

    for st in common_stages:
        r0 = by_stage0[st]
        r1 = by_stage1[st]
        y0 = _norm(_arr(r0, "y_", labels))
        y1 = _norm(_arr(r1, "y_", labels), fallback=y0)
        yt0 = _norm(_arr(r0, "y_target_", labels), fallback=y0)
        yt1 = _norm(_arr(r1, "y_target_", labels), fallback=yt0)
        yeq1 = _norm(_arr(r1, "y_eq_", labels), fallback=yt1)
        x1 = _norm(_arr(r1, "x_", labels))
        xeq1 = _norm(_arr(r1, "x_eq_", labels), fallback=x1)

        dy = y1 - y0
        drift_rate = dy / dt
        gap1 = y1 - yt1
        gap0 = y0 - yt0
        gap_growth = np.abs(gap1) - np.abs(gap0)

        k_ratio = _arr(r1, "K_state_over_K_eq_relax_", labels)
        ln_k = np.full_like(k_ratio, np.nan, dtype=float)
        valid_k = np.isfinite(k_ratio) & (k_ratio > 0.0)
        ln_k[valid_k] = np.log(k_ratio[valid_k])
        ln_y_over_y_eq = np.full_like(y1, np.nan, dtype=float)
        valid_y_eq = np.isfinite(y1) & np.isfinite(yeq1) & (y1 > 0.0) & (yeq1 > 0.0)
        ln_y_over_y_eq[valid_y_eq] = np.log(y1[valid_y_eq] / yeq1[valid_y_eq])
        ln_x_over_x_eq = np.full_like(x1, np.nan, dtype=float)
        valid_x_eq = np.isfinite(x1) & np.isfinite(xeq1) & (x1 > 0.0) & (xeq1 > 0.0)
        ln_x_over_x_eq[valid_x_eq] = np.log(x1[valid_x_eq] / xeq1[valid_x_eq])
        ln_k_from_xy = ln_y_over_y_eq - ln_x_over_x_eq
        finite_y_basis = np.abs(ln_y_over_y_eq[np.isfinite(ln_y_over_y_eq)])
        finite_x_basis = np.abs(ln_x_over_x_eq[np.isfinite(ln_x_over_x_eq)])

        dom_gap_label, dom_gap_value = _dominant_component(labels, gap1)
        dom_drift_label, dom_drift_value = _dominant_component(labels, drift_rate)
        dom_k_label, dom_k_value = _dominant_component(labels, ln_k)
        dom_x_label, dom_x_value = _dominant_component(labels, ln_x_over_x_eq)
        dom_y_basis_label, dom_y_basis_value = _dominant_component(labels, ln_y_over_y_eq)

        v_out = _finite_float(r1.get("V_out_lbmolph"))
        v_in = math.nan
        if (st + 1) in by_stage1:
            v_in = _finite_float(by_stage1[st + 1].get("V_out_lbmolph"))
        elif st == max(common_stages):
            v_in = v_out
        mv = _finite_float(r1.get("MV_lbmol"))
        eq_phase = _finite_float(r1.get("eq_phase_change_lbmolps_tray"))
        eq_target_delta = _finite_float(r1.get("eq_target_vapor_delta_lbmol_tray"))
        mass_resid = _finite_float(r1.get("stage_mass_balance_resid_lbmolps"))

        finite_ln = np.abs(ln_k[np.isfinite(ln_k)])
        max_ln_k = float(np.max(finite_ln)) if finite_ln.size else math.nan
        stage_records.append(
            {
                "stage_1based": st,
                "MV_lbmol": mv,
                "V_in_lbmolph_est": v_in,
                "V_out_lbmolph": v_out,
                "V_in_minus_out_lbmolph_est": (
                    v_in - v_out if math.isfinite(v_in) and math.isfinite(v_out) else math.nan
                ),
                "eq_phase_change_lbmolps": eq_phase,
                "eq_target_vapor_delta_lbmol": eq_target_delta,
                "stage_mass_balance_resid_lbmolps": mass_resid,
                "max_abs_y_gap_final": float(np.nanmax(np.abs(gap1))),
                "max_abs_y_gap_initial": float(np.nanmax(np.abs(gap0))),
                "max_abs_y_gap_growth": float(np.nanmax(gap_growth)),
                "max_abs_dy_dt_per_s": float(np.nanmax(np.abs(drift_rate))),
                "max_abs_ln_K_state_over_K_eq": max_ln_k,
                "max_abs_ln_y_over_y_eq": float(np.max(finite_y_basis)) if finite_y_basis.size else math.nan,
                "max_abs_ln_x_over_x_eq": float(np.max(finite_x_basis)) if finite_x_basis.size else math.nan,
                "dominant_y_gap_component": dom_gap_label,
                "dominant_y_gap": dom_gap_value,
                "dominant_y_drift_component": dom_drift_label,
                "dominant_y_drift_per_s": dom_drift_value,
                "dominant_ln_K_component": dom_k_label,
                "dominant_ln_K_state_over_K_eq": dom_k_value,
                "dominant_ln_x_component": dom_x_label,
                "dominant_ln_x_over_x_eq": dom_x_value,
                "dominant_ln_y_basis_component": dom_y_basis_label,
                "dominant_ln_y_over_y_eq": dom_y_basis_value,
            }
        )

        for idx, label in enumerate(labels):
            y_in = math.nan
            if (st + 1) in by_stage1:
                y_in = _norm(_arr(by_stage1[st + 1], "y_", labels))[idx]
            elif st == max(common_stages):
                y_in = y1[idx]
            convective_pull = (y_in - y1[idx]) if math.isfinite(float(y_in)) else math.nan
            component_records.append(
                {
                    "stage_1based": st,
                    "component": label,
                    "x_final": float(x1[idx]),
                    "x_eq_final": float(xeq1[idx]),
                    "y_initial": float(y0[idx]),
                    "y_final": float(y1[idx]),
                    "y_target_initial": float(yt0[idx]),
                    "y_target_final": float(yt1[idx]),
                    "y_eq_final": float(yeq1[idx]),
                    "y_gap_initial": float(gap0[idx]),
                    "y_gap_final": float(gap1[idx]),
                    "abs_y_gap_growth": float(abs(gap1[idx]) - abs(gap0[idx])),
                    "dy_dt_per_s": float(drift_rate[idx]),
                    "K_state_over_K_eq_relax": float(k_ratio[idx]) if np.isfinite(k_ratio[idx]) else math.nan,
                    "ln_K_state_over_K_eq_relax": float(ln_k[idx]) if np.isfinite(ln_k[idx]) else math.nan,
                    "ln_y_over_y_eq": float(ln_y_over_y_eq[idx]) if np.isfinite(ln_y_over_y_eq[idx]) else math.nan,
                    "ln_x_over_x_eq": float(ln_x_over_x_eq[idx]) if np.isfinite(ln_x_over_x_eq[idx]) else math.nan,
                    "ln_K_from_yx_basis": float(ln_k_from_xy[idx]) if np.isfinite(ln_k_from_xy[idx]) else math.nan,
                    "estimated_y_in_from_below": float(y_in) if math.isfinite(float(y_in)) else math.nan,
                    "estimated_convective_pull_y_in_minus_y": float(convective_pull)
                    if math.isfinite(float(convective_pull))
                    else math.nan,
                }
            )

    for st in common_stages:
        if (st + 1) not in by_stage1:
            continue
        src = by_stage1[st + 1]
        rec = by_stage1[st]
        y_src = _norm(_arr(src, "y_", labels))
        y_rec = _norm(_arr(rec, "y_", labels))
        y_delta = y_src - y_rec
        label, value = _dominant_component(labels, y_delta)
        interface_records.append(
            {
                "vapor_source_stage_1based": st + 1,
                "vapor_receiver_stage_1based": st,
                "V_source_lbmolph": _finite_float(src.get("V_out_lbmolph")),
                "max_abs_y_source_minus_receiver": float(np.nanmax(np.abs(y_delta))),
                "dominant_component": label,
                "dominant_y_source_minus_receiver": value,
            }
        )

    stage_records.sort(
        key=lambda r: (
            float(r["max_abs_ln_K_state_over_K_eq"])
            if math.isfinite(float(r.get("max_abs_ln_K_state_over_K_eq", math.nan)))
            else -math.inf
        ),
        reverse=True,
    )
    component_records.sort(
        key=lambda r: (
            abs(float(r["ln_K_state_over_K_eq_relax"]))
            if math.isfinite(float(r.get("ln_K_state_over_K_eq_relax", math.nan)))
            else -math.inf,
            abs(float(r["y_gap_final"]))
            if math.isfinite(float(r.get("y_gap_final", math.nan)))
            else -math.inf,
        ),
        reverse=True,
    )
    interface_records.sort(key=lambda r: float(r["max_abs_y_source_minus_receiver"]), reverse=True)

    interior_components = [r for r in component_records if 1 < int(r["stage_1based"]) < max(common_stages)]
    finite_ln_x = [
        abs(float(r["ln_x_over_x_eq"]))
        for r in component_records
        if math.isfinite(float(r.get("ln_x_over_x_eq", math.nan)))
    ]
    finite_ln_y = [
        abs(float(r["ln_y_over_y_eq"]))
        for r in component_records
        if math.isfinite(float(r.get("ln_y_over_y_eq", math.nan)))
    ]
    return {
        "profile_csv": str(Path(profile_csv).resolve()),
        "initial_time_s": float(initial_time_s),
        "final_time_s": float(final_time_s),
        "dt_s": dt,
        "component_labels": labels,
        "summary": {
            "n_stages": len(common_stages),
            "max_abs_y_gap_final": float(max(abs(float(r["y_gap_final"])) for r in component_records)),
            "max_abs_y_gap_final_interior": float(
                max(abs(float(r["y_gap_final"])) for r in interior_components)
            )
            if interior_components
            else math.nan,
            "max_abs_ln_K_state_over_K_eq": float(
                max(
                    abs(float(r["ln_K_state_over_K_eq_relax"]))
                    for r in component_records
                    if math.isfinite(float(r["ln_K_state_over_K_eq_relax"]))
                )
            ),
            "max_abs_ln_x_over_x_eq": float(max(finite_ln_x)) if finite_ln_x else math.nan,
            "max_abs_ln_y_over_y_eq": float(max(finite_ln_y)) if finite_ln_y else math.nan,
            "max_abs_dy_dt_per_s": float(max(abs(float(r["dy_dt_per_s"])) for r in component_records)),
        },
        "top_stage_rankings": stage_records[: max(int(top_n), 1)],
        "top_component_rankings": component_records[: max(int(top_n), 1)],
        "top_interior_component_rankings": interior_components[: max(int(top_n), 1)],
        "top_interface_rankings": interface_records[: max(int(top_n), 1)],
    }


def _fmt(value: Any) -> str:
    try:
        v = float(value)
    except Exception:
        return ""
    if not math.isfinite(v):
        return ""
    return f"{v:.6g}"


def _table(rows: List[Dict[str, Any]], fields: List[str]) -> List[str]:
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join(["---"] * len(fields)) + "|"]
    for row in rows:
        vals = []
        for field in fields:
            val = row.get(field, "")
            vals.append(_fmt(val) if isinstance(val, (float, int, np.floating, np.integer)) else str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return lines


def write_markdown(report: Dict[str, Any], path: str | Path) -> None:
    lines: List[str] = []
    lines.append("# Vapor Transport After Projection Audit")
    lines.append("")
    lines.append(f"Profile: `{report['profile_csv']}`")
    lines.append(f"Window: `{_fmt(report['initial_time_s'])}` to `{_fmt(report['final_time_s'])}` s")
    lines.append("")
    lines.append("## Summary")
    lines.extend(
        _table(
            [report["summary"]],
            [
                "n_stages",
                "max_abs_y_gap_final",
                "max_abs_y_gap_final_interior",
                "max_abs_ln_K_state_over_K_eq",
                "max_abs_ln_x_over_x_eq",
                "max_abs_ln_y_over_y_eq",
                "max_abs_dy_dt_per_s",
            ],
        )
    )
    lines.append("")
    lines.append("## Interpretation")
    summary = report["summary"]
    lines.append(
        "- If `max_abs_y_gap_final_interior` is small while `max_abs_ln_K_state_over_K_eq` is large, "
        "the remaining K mismatch is not mainly vapor composition drift; inspect liquid composition, K basis, or material transport."
    )
    if float(summary.get("max_abs_y_gap_final_interior", math.nan)) < 0.01:
        lines.append("- Interior vapor composition remains close to the live target after the first step.")
    lines.append("")
    lines.append("## Top K-State Stages")
    lines.extend(
        _table(
            report["top_stage_rankings"],
            [
                "stage_1based",
                "max_abs_ln_K_state_over_K_eq",
                "max_abs_y_gap_final",
                "max_abs_dy_dt_per_s",
                "V_in_minus_out_lbmolph_est",
                "eq_phase_change_lbmolps",
                "dominant_ln_K_component",
                "dominant_ln_K_state_over_K_eq",
                "dominant_ln_x_component",
                "dominant_ln_x_over_x_eq",
            ],
        )
    )
    lines.append("")
    lines.append("## Top Component K Mismatches")
    lines.extend(
        _table(
            report["top_component_rankings"],
            [
                "stage_1based",
                "component",
                "ln_K_state_over_K_eq_relax",
                "ln_x_over_x_eq",
                "ln_y_over_y_eq",
                "y_gap_final",
                "dy_dt_per_s",
                "estimated_convective_pull_y_in_minus_y",
            ],
        )
    )
    lines.append("")
    lines.append("## Top Interior Component K Mismatches")
    lines.extend(
        _table(
            report["top_interior_component_rankings"],
            [
                "stage_1based",
                "component",
                "ln_K_state_over_K_eq_relax",
                "ln_x_over_x_eq",
                "ln_y_over_y_eq",
                "y_gap_final",
                "dy_dt_per_s",
                "estimated_convective_pull_y_in_minus_y",
            ],
        )
    )
    lines.append("")
    lines.append("## Top Vapor Composition Interfaces")
    lines.extend(
        _table(
            report["top_interface_rankings"],
            [
                "vapor_source_stage_1based",
                "vapor_receiver_stage_1based",
                "V_source_lbmolph",
                "max_abs_y_source_minus_receiver",
                "dominant_component",
                "dominant_y_source_minus_receiver",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit first-step vapor transport after projection.")
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--initial-time-s", type=float, default=None)
    ap.add_argument("--final-time-s", type=float, default=None)
    ap.add_argument("--top-n", type=int, default=12)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args()

    report = audit_profile(
        args.profile_csv,
        initial_time_s=args.initial_time_s,
        final_time_s=args.final_time_s,
        top_n=int(args.top_n),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md)

    summary = report["summary"]
    print(f"Audited {summary['n_stages']} stages from t={report['initial_time_s']} to {report['final_time_s']} s")
    print(f"max |y-y_target| interior = {_fmt(summary['max_abs_y_gap_final_interior'])}")
    print(f"max |ln(K_state/K_eq)| = {_fmt(summary['max_abs_ln_K_state_over_K_eq'])}")
    print(f"max |dy/dt| = {_fmt(summary['max_abs_dy_dt_per_s'])} 1/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
