#!/usr/bin/env python
"""
Audit first-step vapor inventory rates from logged profile CSV files.

This is a read-only diagnostic. It compares two logged profile times and ranks
the vapor component inventories whose finite-difference rates dominate the
steady-state detector. It also estimates the vapor convective contribution from
the neighboring vapor stream so material-transport defects can be separated
from equilibrium-projection defects.
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


def _time(row: Dict[str, str]) -> float:
    return _finite_float(row.get("time_s"))


def _stage(row: Dict[str, str]) -> int:
    return int(round(_finite_float(row.get("stage"))))


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
    total = float(np.sum(arr))
    if total > 1.0e-300:
        return arr / total
    if fallback is not None:
        fb = np.asarray(fallback, dtype=float).reshape((-1,))
        fb = np.where(np.isfinite(fb), fb, 0.0)
        fb = np.clip(fb, 0.0, None)
        fb_total = float(np.sum(fb))
        if fb_total > 1.0e-300:
            return fb / fb_total
    return np.full(arr.shape, 1.0 / max(arr.size, 1), dtype=float)


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


def audit_profile(
    profile_csv: str | Path,
    *,
    initial_time_s: Optional[float] = None,
    final_time_s: Optional[float] = None,
    denom_floor_lbmol: float = 1.0,
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
    stages = sorted(set(by_stage0) & set(by_stage1))
    labels = _component_labels(rows1[0])
    if not labels:
        raise ValueError("No component y_* columns found")

    dt = float(final_time_s) - float(initial_time_s)
    if not math.isfinite(dt) or dt <= 0.0:
        raise ValueError("final time must be greater than initial time")

    records: List[Dict[str, Any]] = []
    stage_records: List[Dict[str, Any]] = []
    floor = max(float(denom_floor_lbmol), 0.0)

    for st in stages:
        r0 = by_stage0[st]
        r1 = by_stage1[st]
        y0 = _norm(_arr(r0, "y_", labels))
        y1 = _norm(_arr(r1, "y_", labels), fallback=y0)
        mv0 = _finite_float(r0.get("MV_lbmol"))
        mv1 = _finite_float(r1.get("MV_lbmol"))
        if not math.isfinite(mv0):
            mv0 = 0.0
        if not math.isfinite(mv1):
            mv1 = 0.0

        n0 = mv0 * y0
        n1 = mv1 * y1
        dn_dt = (n1 - n0) / dt
        rel = np.abs(dn_dt) / (np.abs(n1) + floor)

        v_out = _finite_float(r1.get("V_out_lbmolph"))
        y_in = y1
        v_in = v_out
        if (st + 1) in by_stage1:
            src = by_stage1[st + 1]
            v_in = _finite_float(src.get("V_out_lbmolph"))
            y_in = _norm(_arr(src, "y_", labels), fallback=y1)
        convective_lbmolps = np.full_like(y1, math.nan, dtype=float)
        if math.isfinite(v_in) and math.isfinite(v_out):
            convective_lbmolps = ((v_in * y_in) - (v_out * y1)) / 3600.0
        unaccounted_lbmolps = dn_dt - convective_lbmolps
        y_jump_from_source = y_in - y1

        stage_records.append(
            {
                "stage_1based": st,
                "MV_initial_lbmol": float(mv0),
                "MV_final_lbmol": float(mv1),
                "V_in_lbmolph_est": float(v_in) if math.isfinite(v_in) else math.nan,
                "V_out_lbmolph": float(v_out) if math.isfinite(v_out) else math.nan,
                "max_abs_relative_inventory_rate_per_s": float(np.nanmax(rel)),
                "max_abs_dn_dt_lbmolps": float(np.nanmax(np.abs(dn_dt))),
                "max_abs_convective_lbmolps_est": float(np.nanmax(np.abs(convective_lbmolps))),
                "max_abs_unaccounted_lbmolps_est": float(np.nanmax(np.abs(unaccounted_lbmolps))),
                "stage_mass_balance_resid_lbmolps": _finite_float(r1.get("stage_mass_balance_resid_lbmolps")),
                "eq_phase_change_lbmolps_tray": _finite_float(r1.get("eq_phase_change_lbmolps_tray")),
            }
        )

        for idx, label in enumerate(labels):
            records.append(
                {
                    "stage_1based": st,
                    "component": label,
                    "MV_initial_lbmol": float(mv0),
                    "MV_final_lbmol": float(mv1),
                    "y_initial": float(y0[idx]),
                    "y_final": float(y1[idx]),
                    "vapor_inventory_initial_lbmol": float(n0[idx]),
                    "vapor_inventory_final_lbmol": float(n1[idx]),
                    "dn_dt_lbmolps": float(dn_dt[idx]),
                    "relative_inventory_rate_per_s": float(rel[idx]),
                    "V_in_lbmolph_est": float(v_in) if math.isfinite(v_in) else math.nan,
                    "V_out_lbmolph": float(v_out) if math.isfinite(v_out) else math.nan,
                    "y_in_from_below_est": float(y_in[idx]),
                    "y_in_minus_y": float(y_jump_from_source[idx]),
                    "convective_lbmolps_est": float(convective_lbmolps[idx])
                    if math.isfinite(float(convective_lbmolps[idx]))
                    else math.nan,
                    "unaccounted_lbmolps_est": float(unaccounted_lbmolps[idx])
                    if math.isfinite(float(unaccounted_lbmolps[idx]))
                    else math.nan,
                }
            )

    records.sort(key=lambda r: abs(float(r["relative_inventory_rate_per_s"])), reverse=True)
    stage_records.sort(key=lambda r: abs(float(r["max_abs_relative_inventory_rate_per_s"])), reverse=True)
    interior_records = [r for r in records if 1 < int(r["stage_1based"]) < max(stages)]

    return {
        "profile_csv": str(Path(profile_csv).resolve()),
        "initial_time_s": float(initial_time_s),
        "final_time_s": float(final_time_s),
        "dt_s": float(dt),
        "denom_floor_lbmol": float(floor),
        "component_labels": labels,
        "summary": {
            "n_stages": len(stages),
            "max_abs_relative_inventory_rate_per_s": float(
                max(abs(float(r["relative_inventory_rate_per_s"])) for r in records)
            ),
            "max_abs_relative_inventory_rate_per_s_interior": float(
                max(abs(float(r["relative_inventory_rate_per_s"])) for r in interior_records)
            )
            if interior_records
            else math.nan,
            "max_abs_dn_dt_lbmolps": float(max(abs(float(r["dn_dt_lbmolps"])) for r in records)),
            "max_abs_convective_lbmolps_est": float(
                max(
                    abs(float(r["convective_lbmolps_est"]))
                    for r in records
                    if math.isfinite(float(r["convective_lbmolps_est"]))
                )
            ),
            "max_abs_unaccounted_lbmolps_est": float(
                max(
                    abs(float(r["unaccounted_lbmolps_est"]))
                    for r in records
                    if math.isfinite(float(r["unaccounted_lbmolps_est"]))
                )
            ),
        },
        "top_component_rates": records[: max(int(top_n), 1)],
        "top_interior_component_rates": interior_records[: max(int(top_n), 1)],
        "top_stage_rates": stage_records[: max(int(top_n), 1)],
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
    lines.append("# Vapor Inventory Rate Audit")
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
                "max_abs_relative_inventory_rate_per_s",
                "max_abs_relative_inventory_rate_per_s_interior",
                "max_abs_dn_dt_lbmolps",
                "max_abs_convective_lbmolps_est",
                "max_abs_unaccounted_lbmolps_est",
            ],
        )
    )
    lines.append("")
    lines.append("## Interpretation")
    lines.append(
        "- The relative inventory rate is the same finite-difference family used by the dynamic smoke detector."
    )
    lines.append(
        "- Large estimated convective terms indicate startup motion driven by adjacent vapor composition/flow mismatch."
    )
    lines.append(
        "- Large unaccounted terms indicate effects outside simple vapor convection, such as phase transfer, total vapor holdup changes, or boundary coupling."
    )
    lines.append("")
    lines.append("## Top Component Rates")
    lines.extend(
        _table(
            report["top_component_rates"],
            [
                "stage_1based",
                "component",
                "relative_inventory_rate_per_s",
                "dn_dt_lbmolps",
                "convective_lbmolps_est",
                "unaccounted_lbmolps_est",
                "MV_final_lbmol",
                "V_in_lbmolph_est",
                "V_out_lbmolph",
                "y_in_minus_y",
            ],
        )
    )
    lines.append("")
    lines.append("## Top Interior Component Rates")
    lines.extend(
        _table(
            report["top_interior_component_rates"],
            [
                "stage_1based",
                "component",
                "relative_inventory_rate_per_s",
                "dn_dt_lbmolps",
                "convective_lbmolps_est",
                "unaccounted_lbmolps_est",
                "MV_final_lbmol",
                "V_in_lbmolph_est",
                "V_out_lbmolph",
                "y_in_minus_y",
            ],
        )
    )
    lines.append("")
    lines.append("## Top Stage Rates")
    lines.extend(
        _table(
            report["top_stage_rates"],
            [
                "stage_1based",
                "max_abs_relative_inventory_rate_per_s",
                "max_abs_dn_dt_lbmolps",
                "max_abs_convective_lbmolps_est",
                "max_abs_unaccounted_lbmolps_est",
                "stage_mass_balance_resid_lbmolps",
                "eq_phase_change_lbmolps_tray",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit first-step vapor inventory rates from a profile CSV.")
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--initial-time-s", type=float, default=None)
    ap.add_argument("--final-time-s", type=float, default=None)
    ap.add_argument("--denom-floor-lbmol", type=float, default=1.0)
    ap.add_argument("--top-n", type=int, default=12)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args()

    report = audit_profile(
        args.profile_csv,
        initial_time_s=args.initial_time_s,
        final_time_s=args.final_time_s,
        denom_floor_lbmol=float(args.denom_floor_lbmol),
        top_n=int(args.top_n),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md)

    summary = report["summary"]
    print(f"Audited {summary['n_stages']} stages from t={report['initial_time_s']} to {report['final_time_s']} s")
    print(f"max relative vapor inventory rate = {_fmt(summary['max_abs_relative_inventory_rate_per_s'])} 1/s")
    print(f"max estimated convective term = {_fmt(summary['max_abs_convective_lbmolps_est'])} lbmol/s")
    print(f"max estimated unaccounted term = {_fmt(summary['max_abs_unaccounted_lbmolps_est'])} lbmol/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
