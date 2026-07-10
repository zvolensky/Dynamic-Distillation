#!/usr/bin/env python
"""
Audit the linearized steady vapor composition implied by transport + equilibrium.

For composition-only equilibrium relaxation with fixed vapor holdup and fixed
logged vapor traffic, the explicit vapor component balance has the form

    0 = transport_in_i,k + feed_i,k - V_out_i*y_i,k
        + (MV_i*y_target_i,k - MV_i*y_i,k)/tau

This tool solves the corresponding per-stage composition target from profile
CSV diagnostics and compares it with the current vapor state and equilibrium
target. It is read-only and does not call the RHS.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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


def _component_labels(row: Dict[str, str]) -> List[str]:
    labels: List[str] = []
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


def _arr(row: Dict[str, str], prefix: str, labels: Iterable[str]) -> np.ndarray:
    return np.asarray([_finite_float(row.get(f"{prefix}{label}")) for label in labels], dtype=float)


def _stage_kind(stage: int, max_stage: int) -> str:
    if stage <= 1:
        return "top"
    if stage >= max_stage:
        return "bottom"
    return "interior"


def audit_profile(
    profile_csv: str | Path,
    *,
    time_s: Optional[float] = None,
    equilibrium_tau_sec: float = 0.5,
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
        raise ValueError("No component y_* columns found")
    tau = float(equilibrium_tau_sec)
    if not math.isfinite(tau) or tau <= 0.0:
        raise ValueError("equilibrium_tau_sec must be positive")

    max_stage = max(int(round(_finite_float(r.get("stage")))) for r in rows)
    records: List[Dict[str, Any]] = []
    stage_records: List[Dict[str, Any]] = []
    y_ss_by_stage: Dict[int, np.ndarray] = {}

    for row in rows:
        stage = int(round(_finite_float(row.get("stage"))))
        kind = _stage_kind(stage, max_stage)
        mv = _finite_float(row.get("MV_lbmol"))
        vout = _finite_float(row.get("V_out_lbmolph")) / 3600.0
        y = _normalize(_arr(row, "y_", labels))
        y_target = _normalize(_arr(row, "y_target_", labels), fallback=y)
        transport_in = _arr(row, "tray_V_transport_in_lbmolps_", labels)
        feed = _arr(row, "tray_V_feed_lbmolps_", labels)

        if not math.isfinite(mv) or mv <= 0.0 or not math.isfinite(vout) or vout < 0.0:
            y_ss = np.full(len(labels), math.nan, dtype=float)
            residual_at_y_ss = np.full(len(labels), math.nan, dtype=float)
        else:
            denom = float(vout) + float(mv) / tau
            rhs = np.where(np.isfinite(transport_in), transport_in, 0.0)
            rhs = rhs + np.where(np.isfinite(feed), feed, 0.0) + (float(mv) / tau) * y_target
            y_raw = rhs / max(denom, 1.0e-300)
            y_ss = _normalize(y_raw, fallback=y_target)
            residual_at_y_ss = rhs - denom * y_ss
        y_ss_by_stage[stage] = y_ss

        max_state_delta = float(np.nanmax(np.abs(y_ss - y))) if np.any(np.isfinite(y_ss)) else math.nan
        max_eq_delta = float(np.nanmax(np.abs(y_ss - y_target))) if np.any(np.isfinite(y_ss)) else math.nan
        stage_records.append(
            {
                "stage_1based": stage,
                "stage_kind": kind,
                "max_abs_y_ss_minus_y": max_state_delta,
                "max_abs_y_ss_minus_y_target": max_eq_delta,
            }
        )

        for idx, label in enumerate(labels):
            records.append(
                {
                    "stage_1based": stage,
                    "stage_kind": kind,
                    "component": label,
                    "MV_lbmol": mv,
                    "V_out_lbmolps": vout,
                    "y": float(y[idx]),
                    "y_target": float(y_target[idx]),
                    "y_linear_steady": float(y_ss[idx]) if math.isfinite(float(y_ss[idx])) else math.nan,
                    "y_linear_steady_minus_y": float(y_ss[idx] - y[idx])
                    if math.isfinite(float(y_ss[idx]))
                    else math.nan,
                    "y_linear_steady_minus_y_target": float(y_ss[idx] - y_target[idx])
                    if math.isfinite(float(y_ss[idx]))
                    else math.nan,
                    "residual_at_y_linear_steady_lbmolps": float(residual_at_y_ss[idx])
                    if math.isfinite(float(residual_at_y_ss[idx]))
                    else math.nan,
                    "transport_in_lbmolps": float(transport_in[idx])
                    if math.isfinite(float(transport_in[idx]))
                    else math.nan,
                    "feed_lbmolps": float(feed[idx]) if math.isfinite(float(feed[idx])) else math.nan,
                }
            )

    records.sort(
        key=lambda r: abs(float(r["y_linear_steady_minus_y"]))
        if math.isfinite(float(r.get("y_linear_steady_minus_y", math.nan)))
        else -math.inf,
        reverse=True,
    )
    stage_records.sort(
        key=lambda r: abs(float(r["max_abs_y_ss_minus_y"]))
        if math.isfinite(float(r.get("max_abs_y_ss_minus_y", math.nan)))
        else -math.inf,
        reverse=True,
    )
    interior_records = [r for r in records if r["stage_kind"] == "interior"]
    finite_state_delta = [
        abs(float(r["y_linear_steady_minus_y"]))
        for r in records
        if math.isfinite(float(r.get("y_linear_steady_minus_y", math.nan)))
    ]
    finite_eq_delta = [
        abs(float(r["y_linear_steady_minus_y_target"]))
        for r in records
        if math.isfinite(float(r.get("y_linear_steady_minus_y_target", math.nan)))
    ]
    finite_state_delta_int = [
        abs(float(r["y_linear_steady_minus_y"]))
        for r in interior_records
        if math.isfinite(float(r.get("y_linear_steady_minus_y", math.nan)))
    ]

    return {
        "profile_csv": str(Path(profile_csv).resolve()),
        "time_s": float(time_s),
        "equilibrium_tau_sec": tau,
        "component_labels": labels,
        "summary": {
            "n_stages": len(rows),
            "n_components": len(labels),
            "max_abs_y_linear_steady_minus_y": max(finite_state_delta) if finite_state_delta else math.nan,
            "max_abs_y_linear_steady_minus_y_interior": max(finite_state_delta_int)
            if finite_state_delta_int
            else math.nan,
            "max_abs_y_linear_steady_minus_y_target": max(finite_eq_delta) if finite_eq_delta else math.nan,
        },
        "top_component_deltas": records[: max(int(top_n), 1)],
        "top_interior_component_deltas": interior_records[: max(int(top_n), 1)],
        "top_stage_deltas": stage_records[: max(int(top_n), 1)],
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
    fields = [
        "stage_1based",
        "stage_kind",
        "component",
        "y",
        "y_target",
        "y_linear_steady",
        "y_linear_steady_minus_y",
        "y_linear_steady_minus_y_target",
        "transport_in_lbmolps",
        "V_out_lbmolps",
    ]
    lines = [
        "# Vapor Linear Steady Composition Audit",
        "",
        f"Profile: `{report['profile_csv']}`",
        f"Time: `{_fmt(report['time_s'])}` s",
        "",
        "## Summary",
    ]
    lines.extend(
        _table(
            [report["summary"]],
            [
                "n_stages",
                "n_components",
                "max_abs_y_linear_steady_minus_y",
                "max_abs_y_linear_steady_minus_y_interior",
                "max_abs_y_linear_steady_minus_y_target",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "- `y_linear_steady` is the vapor composition that would zero the linearized component balance using logged transport and equilibrium target terms.",
            "- If `y_linear_steady` differs from `y_target`, forcing vapor directly to equilibrium cannot also zero transport.",
            "- This is a diagnostic using fixed logged traffic and target values; it is not a full nonlinear solve.",
            "",
            "## Top Component Deltas",
        ]
    )
    lines.extend(_table(report["top_component_deltas"], fields))
    lines.append("")
    lines.append("## Top Interior Component Deltas")
    lines.extend(_table(report["top_interior_component_deltas"], fields))
    lines.append("")
    lines.append("## Top Stage Deltas")
    lines.extend(
        _table(
            report["top_stage_deltas"],
            [
                "stage_1based",
                "stage_kind",
                "max_abs_y_ss_minus_y",
                "max_abs_y_ss_minus_y_target",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit linearized steady vapor composition from profile CSV.")
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--time-s", type=float, default=None)
    ap.add_argument("--equilibrium-tau-sec", type=float, default=0.5)
    ap.add_argument("--top-n", type=int, default=12)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args()

    report = audit_profile(
        args.profile_csv,
        time_s=args.time_s,
        equilibrium_tau_sec=float(args.equilibrium_tau_sec),
        top_n=int(args.top_n),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md)
    if not args.output_json and not args.output_md:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
