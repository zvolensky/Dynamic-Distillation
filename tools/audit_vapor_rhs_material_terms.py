#!/usr/bin/env python
"""
Audit RHS vapor material terms from profile CSV diagnostics.

This reads a profile CSV generated with `tray_V_*_lbmolps_*` columns and ranks
the vapor component state rates by the live RHS decomposition at one logged
time. It does not recompute thermo or call the RHS.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TERM_COLUMNS = {
    "transport_in": "tray_V_transport_in_lbmolps_",
    "transport_out": "tray_V_transport_out_lbmolps_",
    "feed": "tray_V_feed_lbmolps_",
    "terminal_adjust": "tray_V_terminal_adjust_lbmolps_",
    "holdup_relax": "tray_V_holdup_relax_lbmolps_",
    "equilibrium_transfer": "tray_V_equilibrium_transfer_lbmolps_",
}


def _finite_float(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def _read_csv(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _component_labels(row: Dict[str, str]) -> List[str]:
    labels: List[str] = []
    prefix = "tray_V_final_rhs_lbmolps_"
    for key in row.keys():
        if key.startswith(prefix):
            labels.append(key[len(prefix) :])
    if labels:
        return sorted(labels)
    for key in row.keys():
        if key.startswith("y_") and not key.startswith("y_eq_") and not key.startswith("y_target_"):
            labels.append(key[2:])
    return sorted(labels)


def _stage_rows(rows: List[Dict[str, str]], time_s: float) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        if str(row.get("node_type", "")).strip().lower() != "stage":
            continue
        t = _finite_float(row.get("time_s"))
        if math.isfinite(t) and abs(t - float(time_s)) <= 1.0e-9:
            out.append(row)
    return sorted(out, key=lambda r: int(round(_finite_float(r.get("stage")))))


def _infer_time(rows: List[Dict[str, str]]) -> float:
    times = sorted(
        {
            _finite_float(r.get("time_s"))
            for r in rows
            if str(r.get("node_type", "")).strip().lower() == "stage"
            and math.isfinite(_finite_float(r.get("time_s")))
        }
    )
    if not times:
        raise ValueError("No stage rows with finite time_s")
    return float(times[-1])


def _dominant_term(terms: Dict[str, float]) -> tuple[str, float]:
    finite = {k: v for k, v in terms.items() if math.isfinite(v)}
    if not finite:
        return "", math.nan
    key = max(finite, key=lambda k: abs(float(finite[k])))
    return key, float(finite[key])


def audit_profile(
    profile_csv: str | Path,
    *,
    time_s: Optional[float] = None,
    denom_floor_lbmol: float = 1.0,
    top_n: int = 12,
) -> Dict[str, Any]:
    rows_all = _read_csv(profile_csv)
    if time_s is None:
        time_s = _infer_time(rows_all)
    rows = _stage_rows(rows_all, float(time_s))
    if not rows:
        raise ValueError("No stage rows at requested time")
    labels = _component_labels(rows[0])
    if not labels:
        raise ValueError("No component labels found")
    floor = max(float(denom_floor_lbmol), 0.0)

    records: List[Dict[str, Any]] = []
    stage_records: List[Dict[str, Any]] = []
    max_stage = max(int(round(_finite_float(r.get("stage")))) for r in rows)

    for row in rows:
        stage = int(round(_finite_float(row.get("stage"))))
        mv = _finite_float(row.get("MV_lbmol"))
        if not math.isfinite(mv):
            mv = 0.0
        stage_abs_final = 0.0
        stage_abs_terms: Dict[str, float] = {name: 0.0 for name in TERM_COLUMNS}
        for label in labels:
            y = _finite_float(row.get(f"y_{label}"))
            inv = max(mv * y, 0.0) if math.isfinite(y) else 0.0
            final_rhs = _finite_float(row.get(f"tray_V_final_rhs_lbmolps_{label}"))
            pre_rhs = _finite_float(row.get(f"tray_V_pre_equilibrium_rhs_lbmolps_{label}"))
            terms = {
                name: _finite_float(row.get(f"{prefix}{label}"))
                for name, prefix in TERM_COLUMNS.items()
            }
            dominant_name, dominant_value = _dominant_term(terms)
            denom = max(abs(inv) + floor, 1.0e-300)
            rel = abs(final_rhs) / denom if math.isfinite(final_rhs) else math.nan
            records.append(
                {
                    "stage_1based": stage,
                    "component": label,
                    "inventory_lbmol": inv,
                    "final_rhs_lbmolps": final_rhs,
                    "pre_equilibrium_rhs_lbmolps": pre_rhs,
                    "relative_rhs_per_s": rel,
                    "dominant_term": dominant_name,
                    "dominant_term_lbmolps": dominant_value,
                    **{f"{name}_lbmolps": value for name, value in terms.items()},
                }
            )
            if math.isfinite(final_rhs):
                stage_abs_final = max(stage_abs_final, abs(final_rhs))
            for name, value in terms.items():
                if math.isfinite(value):
                    stage_abs_terms[name] = max(float(stage_abs_terms[name]), abs(float(value)))

        dominant_stage_name, dominant_stage_value = _dominant_term(stage_abs_terms)
        stage_records.append(
            {
                "stage_1based": stage,
                "max_abs_final_rhs_lbmolps": stage_abs_final,
                "dominant_stage_term": dominant_stage_name,
                "dominant_stage_term_abs_lbmolps": dominant_stage_value,
            }
        )

    records.sort(
        key=lambda r: (
            abs(float(r["relative_rhs_per_s"]))
            if math.isfinite(float(r.get("relative_rhs_per_s", math.nan)))
            else -math.inf
        ),
        reverse=True,
    )
    stage_records.sort(key=lambda r: abs(float(r["max_abs_final_rhs_lbmolps"])), reverse=True)
    interior_records = [r for r in records if 1 < int(r["stage_1based"]) < max_stage]
    finite_rel = [abs(float(r["relative_rhs_per_s"])) for r in records if math.isfinite(float(r["relative_rhs_per_s"]))]
    finite_rel_int = [
        abs(float(r["relative_rhs_per_s"]))
        for r in interior_records
        if math.isfinite(float(r["relative_rhs_per_s"]))
    ]

    return {
        "profile_csv": str(Path(profile_csv).resolve()),
        "time_s": float(time_s),
        "denom_floor_lbmol": float(floor),
        "component_labels": labels,
        "summary": {
            "n_stages": len(rows),
            "max_relative_rhs_per_s": max(finite_rel) if finite_rel else math.nan,
            "max_relative_rhs_per_s_interior": max(finite_rel_int) if finite_rel_int else math.nan,
            "max_abs_final_rhs_lbmolps": max(
                abs(float(r["final_rhs_lbmolps"]))
                for r in records
                if math.isfinite(float(r["final_rhs_lbmolps"]))
            ),
        },
        "top_component_terms": records[: max(int(top_n), 1)],
        "top_interior_component_terms": interior_records[: max(int(top_n), 1)],
        "top_stage_terms": stage_records[: max(int(top_n), 1)],
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
            vals.append(_fmt(val) if isinstance(val, (float, int)) else str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return lines


def write_markdown(report: Dict[str, Any], path: str | Path) -> None:
    lines: List[str] = []
    lines.append("# Vapor RHS Material Terms Audit")
    lines.append("")
    lines.append(f"Profile: `{report['profile_csv']}`")
    lines.append(f"Time: `{_fmt(report['time_s'])}` s")
    lines.append("")
    lines.append("## Summary")
    lines.extend(
        _table(
            [report["summary"]],
            [
                "n_stages",
                "max_relative_rhs_per_s",
                "max_relative_rhs_per_s_interior",
                "max_abs_final_rhs_lbmolps",
            ],
        )
    )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.")
    lines.append("- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.")
    lines.append("- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.")
    lines.append("")
    lines.append("## Top Component Terms")
    fields = [
        "stage_1based",
        "component",
        "relative_rhs_per_s",
        "final_rhs_lbmolps",
        "pre_equilibrium_rhs_lbmolps",
        "dominant_term",
        "dominant_term_lbmolps",
        "transport_in_lbmolps",
        "transport_out_lbmolps",
        "equilibrium_transfer_lbmolps",
        "terminal_adjust_lbmolps",
    ]
    lines.extend(_table(report["top_component_terms"], fields))
    lines.append("")
    lines.append("## Top Interior Component Terms")
    lines.extend(_table(report["top_interior_component_terms"], fields))
    lines.append("")
    lines.append("## Top Stage Terms")
    lines.extend(
        _table(
            report["top_stage_terms"],
            [
                "stage_1based",
                "max_abs_final_rhs_lbmolps",
                "dominant_stage_term",
                "dominant_stage_term_abs_lbmolps",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit live RHS vapor material terms from a profile CSV.")
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--time-s", type=float, default=None)
    ap.add_argument("--denom-floor-lbmol", type=float, default=1.0)
    ap.add_argument("--top-n", type=int, default=12)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args()

    report = audit_profile(
        args.profile_csv,
        time_s=args.time_s,
        denom_floor_lbmol=float(args.denom_floor_lbmol),
        top_n=int(args.top_n),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md)

    summary = report["summary"]
    print(f"Audited {summary['n_stages']} stages at t={report['time_s']} s")
    print(f"max relative RHS = {_fmt(summary['max_relative_rhs_per_s'])} 1/s")
    print(f"max interior relative RHS = {_fmt(summary['max_relative_rhs_per_s_interior'])} 1/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
