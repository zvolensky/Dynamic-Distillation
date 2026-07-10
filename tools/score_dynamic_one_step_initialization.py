#!/usr/bin/env python
"""
Score a one-step dynamic initialization launch.

This tool combines dynamic summary metrics with profile-level vapor diagnostics
so candidate initializers can be ranked by the launch behavior they actually
produce, not by a static t=0 residual alone.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from audit_vapor_transport_equilibrium_conflict import audit_profile as audit_conflict_profile
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as tools.*
    from tools.audit_vapor_transport_equilibrium_conflict import audit_profile as audit_conflict_profile


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


def _rows_in_window(rows: Iterable[Dict[str, str]], max_time_s: Optional[float]) -> List[Dict[str, str]]:
    out = [r for r in rows if math.isfinite(_time(r))]
    if max_time_s is None:
        return out
    return [r for r in out if _time(r) <= float(max_time_s) + 1.0e-9]


def _last_row(rows: Iterable[Dict[str, str]], max_time_s: Optional[float]) -> Dict[str, str]:
    window = _rows_in_window(rows, max_time_s)
    if not window:
        raise ValueError("no finite summary rows in requested time window")
    return max(window, key=_time)


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
        t = _time(row)
        if math.isfinite(t) and abs(t - float(time_s)) <= 1.0e-9:
            out.append(row)
    return sorted(out, key=lambda r: int(round(_finite_float(r.get("stage")))))


def _infer_profile_times(rows: List[Dict[str, str]], final_time_s: Optional[float]) -> tuple[float, float]:
    times = sorted(
        {
            _time(r)
            for r in rows
            if str(r.get("node_type", "")).strip().lower() == "stage" and math.isfinite(_time(r))
        }
    )
    if len(times) < 2:
        raise ValueError("profile must contain at least two stage times")
    t0 = float(times[0])
    if final_time_s is not None:
        candidates = [t for t in times if t <= float(final_time_s) + 1.0e-9]
        if not candidates:
            raise ValueError("profile has no stage rows at or before final_time_s")
        return t0, float(candidates[-1])
    return t0, float(times[-1])


def _max_profile_y_drift(
    rows: List[Dict[str, str]],
    *,
    initial_time_s: float,
    final_time_s: float,
    interior_only: bool,
) -> Dict[str, Any]:
    rows0 = _stage_rows(rows, initial_time_s)
    rows1 = _stage_rows(rows, final_time_s)
    if not rows0 or not rows1:
        raise ValueError("missing profile rows at requested initial/final times")
    by0 = {int(round(_finite_float(r.get("stage")))): r for r in rows0}
    by1 = {int(round(_finite_float(r.get("stage")))): r for r in rows1}
    stages = sorted(set(by0) & set(by1))
    if not stages:
        raise ValueError("no common stages between initial and final profile rows")
    labels = _component_labels(rows1[0])
    if not labels:
        raise ValueError("profile has no y_* component columns")
    max_stage = max(stages)
    records: List[Dict[str, Any]] = []
    for stage in stages:
        if interior_only and not (1 < stage < max_stage):
            continue
        r0 = by0[stage]
        r1 = by1[stage]
        for label in labels:
            y0 = _finite_float(r0.get(f"y_{label}"))
            y1 = _finite_float(r1.get(f"y_{label}"))
            if not (math.isfinite(y0) and math.isfinite(y1)):
                continue
            records.append(
                {
                    "stage_1based": stage,
                    "component": label,
                    "y_initial": y0,
                    "y_final": y1,
                    "abs_y_drift": abs(y1 - y0),
                }
            )
    records.sort(key=lambda r: float(r["abs_y_drift"]), reverse=True)
    return {
        "max_abs_y_drift": float(records[0]["abs_y_drift"]) if records else math.nan,
        "top_y_drift": records[:12],
    }


def _median(values: Iterable[float]) -> float:
    finite = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not finite:
        return math.nan
    mid = len(finite) // 2
    if len(finite) % 2:
        return finite[mid]
    return 0.5 * (finite[mid - 1] + finite[mid])


def _coverage_metrics(conflict_report: Dict[str, Any], *, interior_only: bool) -> Dict[str, float]:
    records = conflict_report["top_final_rhs_conflicts"]
    if interior_only:
        records = [r for r in records if r.get("stage_kind") == "interior"]
    coverage = [
        float(r["cancellation_coverage"])
        for r in records
        if math.isfinite(_finite_float(r.get("cancellation_coverage")))
    ]
    errors = [abs(c - 1.0) for c in coverage]
    over = [max(c - 1.0, 0.0) for c in coverage]
    under = [max(1.0 - c, 0.0) for c in coverage]
    return {
        "median_abs_cancellation_coverage_error": _median(errors),
        "max_cancellation_overcoverage": max(over) if over else math.nan,
        "max_cancellation_undercoverage": max(under) if under else math.nan,
        "median_cancellation_coverage": _median(coverage),
    }


def _term(value: float, ref: float, weight: float) -> float:
    if not math.isfinite(value):
        return math.inf
    denom = max(abs(float(ref)), 1.0e-300)
    return float(weight) * abs(float(value)) / denom


def score_run(
    summary_csv: str | Path,
    profile_csv: str | Path,
    *,
    max_time_s: Optional[float] = None,
    profile_final_time_s: Optional[float] = None,
    equilibrium_tau_sec: float = 0.5,
    interior_only: bool = True,
    refs: Optional[Dict[str, float]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    refs = {
        "dynamic_score": 1.0,
        "rel_rate_per_s": 0.01,
        "temp_rate_F_per_s": 0.1,
        "vapor_rhs_lbmolps": 0.1,
        "coverage_error": 1.0,
        "overcoverage": 1.0,
        "y_drift": 0.01,
        **(refs or {}),
    }
    weights = {
        "dynamic_score": 1.0,
        "rel_rate_per_s": 1.0,
        "temp_rate_F_per_s": 0.5,
        "vapor_rhs_lbmolps": 1.0,
        "coverage_error": 0.5,
        "overcoverage": 0.5,
        "y_drift": 0.5,
        **(weights or {}),
    }
    summary_rows = _read_csv(summary_csv)
    final_summary = _last_row(summary_rows, max_time_s)
    final_time_s = _time(final_summary)
    if profile_final_time_s is not None:
        final_time_s = float(profile_final_time_s)

    profile_rows = _read_csv(profile_csv)
    profile_t0, profile_t1 = _infer_profile_times(profile_rows, final_time_s)
    conflict = audit_conflict_profile(
        profile_csv,
        time_s=profile_t1,
        equilibrium_tau_sec=equilibrium_tau_sec,
        top_n=1_000_000,
    )
    coverage = _coverage_metrics(conflict, interior_only=interior_only)
    drift = _max_profile_y_drift(
        profile_rows,
        initial_time_s=profile_t0,
        final_time_s=profile_t1,
        interior_only=interior_only,
    )

    metrics = {
        "dynamic_score": _finite_float(final_summary.get("steady_state_score")),
        "rel_rate_per_s": _finite_float(final_summary.get("ss_max_rel_state_rate_per_s")),
        "temp_rate_F_per_s": _finite_float(final_summary.get("ss_max_temp_rate_F_per_s")),
        "vapor_rhs_lbmolps": _finite_float(conflict["summary"].get("max_abs_final_rhs_lbmolps")),
        "coverage_error": _finite_float(coverage.get("median_abs_cancellation_coverage_error")),
        "overcoverage": _finite_float(coverage.get("max_cancellation_overcoverage")),
        "y_drift": _finite_float(drift.get("max_abs_y_drift")),
    }
    terms = {
        name: _term(metrics[name], refs[name], weights[name])
        for name in metrics
    }
    finite_terms = [v for v in terms.values() if math.isfinite(v)]
    objective = math.sqrt(sum(v * v for v in finite_terms)) if len(finite_terms) == len(terms) else math.inf

    return {
        "summary_csv": str(Path(summary_csv).resolve()),
        "profile_csv": str(Path(profile_csv).resolve()),
        "summary_time_s": _time(final_summary),
        "profile_initial_time_s": profile_t0,
        "profile_final_time_s": profile_t1,
        "interior_only": bool(interior_only),
        "objective": float(objective),
        "metrics": metrics,
        "terms": terms,
        "refs": refs,
        "weights": weights,
        "coverage": coverage,
        "drift": drift,
        "top_vapor_conflicts": conflict["top_interior_final_rhs_conflicts" if interior_only else "top_final_rhs_conflicts"][:12],
    }


def _parse_key_float(raw: str) -> tuple[str, float]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected KEY=VALUE")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("key cannot be empty")
    val = _finite_float(value)
    if not math.isfinite(val):
        raise argparse.ArgumentTypeError("value must be finite")
    return key, val


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
    lines: List[str] = [
        "# Dynamic One-Step Initialization Score",
        "",
        f"Summary: `{report['summary_csv']}`",
        f"Profile: `{report['profile_csv']}`",
        f"Objective: `{_fmt(report['objective'])}`",
        "",
        "## Terms",
    ]
    term_rows = [
        {
            "metric": name,
            "value": report["metrics"][name],
            "ref": report["refs"][name],
            "weight": report["weights"][name],
            "term": report["terms"][name],
        }
        for name in report["metrics"]
    ]
    lines.extend(_table(term_rows, ["metric", "value", "ref", "weight", "term"]))
    lines.append("")
    lines.append("## Coverage")
    lines.extend(_table([report["coverage"]], list(report["coverage"].keys())))
    lines.append("")
    lines.append("## Top Vapor Conflicts")
    lines.extend(
        _table(
            report["top_vapor_conflicts"],
            [
                "stage_1based",
                "stage_kind",
                "component",
                "final_rhs_lbmolps",
                "pre_equilibrium_rhs_lbmolps",
                "equilibrium_transfer_lbmolps",
                "cancellation_coverage",
                "required_target_delta",
            ],
        )
    )
    lines.append("")
    lines.append("## Top Vapor Composition Drift")
    lines.extend(_table(report["drift"]["top_y_drift"], ["stage_1based", "component", "y_initial", "y_final", "abs_y_drift"]))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Score a one-step dynamic initialization launch.")
    ap.add_argument("--summary-csv", required=True)
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--max-time-s", type=float, default=None)
    ap.add_argument("--profile-final-time-s", type=float, default=None)
    ap.add_argument("--equilibrium-tau-sec", type=float, default=0.5)
    ap.add_argument("--include-terminal-stages", action="store_true")
    ap.add_argument("--ref", action="append", type=_parse_key_float, default=[])
    ap.add_argument("--weight", action="append", type=_parse_key_float, default=[])
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args()

    report = score_run(
        args.summary_csv,
        args.profile_csv,
        max_time_s=args.max_time_s,
        profile_final_time_s=args.profile_final_time_s,
        equilibrium_tau_sec=float(args.equilibrium_tau_sec),
        interior_only=not bool(args.include_terminal_stages),
        refs=dict(args.ref or []),
        weights=dict(args.weight or []),
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
