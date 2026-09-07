#!/usr/bin/env python
"""
Audit time-resolved K-state drift from a profile CSV.

This read-only diagnostic gates normalized vapor equilibrium consistency using
the physically comparable quantities y and y_target. Raw y/x versus thermo K
is retained as historical context, but is not a valid equilibrium gate unless
sum(K*x) is one.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


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
    for key in row:
        if not key.startswith("K_state_"):
            continue
        if key.startswith("K_state_over_") or key.startswith("K_state_minus_"):
            continue
        label = key[len("K_state_") :]
        if f"K_thermo_{label}" in row:
            labels.append(label)
    return sorted(labels)


def _parse_csv_floats(value: Optional[str]) -> Optional[set[float]]:
    if value is None or not str(value).strip():
        return None
    out: set[float] = set()
    for item in str(value).split(","):
        item = item.strip()
        if item:
            out.add(float(item))
    return out


def _parse_csv_ints(value: Optional[str]) -> Optional[set[int]]:
    if value is None or not str(value).strip():
        return None
    out: set[int] = set()
    for item in str(value).split(","):
        item = item.strip()
        if item:
            out.add(int(item))
    return out


def _allowed_time(t: float, allowed: Optional[set[float]], tol: float = 1.0e-6) -> bool:
    if allowed is None:
        return True
    return any(abs(float(t) - float(v)) <= tol for v in allowed)


def _max_or_nan(values: Iterable[float]) -> float:
    finite = [float(v) for v in values if math.isfinite(float(v))]
    return max(finite) if finite else math.nan


def _min_or_nan(values: Iterable[float]) -> float:
    finite = [float(v) for v in values if math.isfinite(float(v))]
    return min(finite) if finite else math.nan


def _top(records: List[Dict[str, Any]], key: str, n: int) -> List[Dict[str, Any]]:
    return sorted(
        records,
        key=lambda r: abs(float(r.get(key, math.nan)))
        if math.isfinite(float(r.get(key, math.nan)))
        else -math.inf,
        reverse=True,
    )[: max(int(n), 0)]


def audit_profile(
    profile_csv: str | Path,
    *,
    stages: Optional[Sequence[int]] = None,
    times: Optional[Sequence[float]] = None,
    top_n: int = 20,
    max_final_abs_delta: Optional[float] = None,
    max_peak_abs_delta: Optional[float] = None,
    max_final_abs_ln_ratio: Optional[float] = None,
    max_positive_abs_delta_trend: Optional[float] = None,
    max_final_abs_y_delta: Optional[float] = None,
    max_peak_abs_y_delta: Optional[float] = None,
    max_positive_abs_y_delta_trend: Optional[float] = None,
    include_terminal_stages: bool = False,
) -> Dict[str, Any]:
    rows_all = _read_csv(profile_csv)
    stage_filter = set(int(s) for s in stages) if stages else None
    time_filter = set(float(t) for t in times) if times else None
    all_stage_ids = sorted(
        {
            int(round(_finite_float(r.get("stage"))))
            for r in rows_all
            if str(r.get("node_type", "")).strip().lower() == "stage"
            and math.isfinite(_finite_float(r.get("stage")))
        }
    )
    default_terminal_ids = (
        {all_stage_ids[0], all_stage_ids[-1]}
        if stage_filter is None and not include_terminal_stages and len(all_stage_ids) >= 3
        else set()
    )
    rows = [
        r
        for r in rows_all
        if str(r.get("node_type", "")).strip().lower() == "stage"
        and math.isfinite(_finite_float(r.get("time_s")))
        and math.isfinite(_finite_float(r.get("stage")))
        and (stage_filter is None or int(round(_finite_float(r.get("stage")))) in stage_filter)
        and int(round(_finite_float(r.get("stage")))) not in default_terminal_ids
        and _allowed_time(_finite_float(r.get("time_s")), time_filter)
    ]
    if not rows:
        raise ValueError("No matching stage rows found")
    labels = _component_labels(rows[0])
    if not labels:
        raise ValueError("No K_state/K_thermo component columns found")

    records: List[Dict[str, Any]] = []
    summary_by_time: Dict[float, Dict[str, Any]] = {}
    for row in rows:
        t = float(_finite_float(row.get("time_s")))
        stage = int(round(_finite_float(row.get("stage"))))
        for label in labels:
            k_state = _finite_float(row.get(f"K_state_{label}"))
            k_thermo = _finite_float(row.get(f"K_thermo_{label}"))
            ratio = _finite_float(row.get(f"K_state_over_K_thermo_{label}"))
            if not math.isfinite(ratio) and math.isfinite(k_state) and math.isfinite(k_thermo) and abs(k_thermo) > 1.0e-300:
                ratio = k_state / k_thermo
            delta = k_state - k_thermo if math.isfinite(k_state) and math.isfinite(k_thermo) else math.nan
            abs_delta = abs(delta) if math.isfinite(delta) else math.nan
            abs_ln_ratio = abs(math.log(abs(ratio))) if math.isfinite(ratio) and abs(ratio) > 1.0e-300 else math.nan
            y = _finite_float(row.get(f"y_{label}"))
            y_target = _finite_float(row.get(f"y_target_{label}"))
            y_delta = (
                y - y_target
                if math.isfinite(k_state) and math.isfinite(y) and math.isfinite(y_target)
                else math.nan
            )
            abs_y_delta = abs(y_delta) if math.isfinite(y_delta) else math.nan
            rec = {
                "time_s": t,
                "stage_1based": stage,
                "component": label,
                "K_state": k_state,
                "K_thermo": k_thermo,
                "K_state_over_K_thermo": ratio,
                "K_state_minus_K_thermo": delta,
                "abs_K_state_minus_K_thermo": abs_delta,
                "abs_ln_K_state_over_K_thermo": abs_ln_ratio,
                "x": _finite_float(row.get(f"x_{label}")),
                "y": y,
                "y_target": y_target,
                "y_minus_y_target": y_delta,
                "abs_y_minus_y_target": abs_y_delta,
                "y_eq": _finite_float(row.get(f"y_eq_{label}")),
            }
            records.append(rec)

            item = summary_by_time.setdefault(
                t,
                {
                    "time_s": t,
                    "max_abs_K_state_minus_K_thermo": math.nan,
                    "max_abs_ln_K_state_over_K_thermo": math.nan,
                    "worst_delta_stage_1based": math.nan,
                    "worst_delta_component": "",
                    "worst_ln_stage_1based": math.nan,
                    "worst_ln_component": "",
                    "max_abs_y_minus_y_target": math.nan,
                    "worst_y_stage_1based": math.nan,
                    "worst_y_component": "",
                },
            )
            if math.isfinite(abs_delta) and (
                not math.isfinite(float(item["max_abs_K_state_minus_K_thermo"]))
                or abs_delta > float(item["max_abs_K_state_minus_K_thermo"])
            ):
                item["max_abs_K_state_minus_K_thermo"] = abs_delta
                item["worst_delta_stage_1based"] = stage
                item["worst_delta_component"] = label
            if math.isfinite(abs_ln_ratio) and (
                not math.isfinite(float(item["max_abs_ln_K_state_over_K_thermo"]))
                or abs_ln_ratio > float(item["max_abs_ln_K_state_over_K_thermo"])
            ):
                item["max_abs_ln_K_state_over_K_thermo"] = abs_ln_ratio
                item["worst_ln_stage_1based"] = stage
                item["worst_ln_component"] = label
            if math.isfinite(abs_y_delta) and (
                not math.isfinite(float(item["max_abs_y_minus_y_target"]))
                or abs_y_delta > float(item["max_abs_y_minus_y_target"])
            ):
                item["max_abs_y_minus_y_target"] = abs_y_delta
                item["worst_y_stage_1based"] = stage
                item["worst_y_component"] = label

    times_sorted = sorted(summary_by_time)
    summary_rows = [summary_by_time[t] for t in times_sorted]
    final_summary = summary_rows[-1]
    delta_series = [float(r["max_abs_K_state_minus_K_thermo"]) for r in summary_rows]
    ln_series = [float(r["max_abs_ln_K_state_over_K_thermo"]) for r in summary_rows]
    final_abs_delta = float(final_summary["max_abs_K_state_minus_K_thermo"])
    first_abs_delta = float(summary_rows[0]["max_abs_K_state_minus_K_thermo"])
    min_abs_delta = _min_or_nan(delta_series)
    trend_from_first = final_abs_delta - first_abs_delta if math.isfinite(final_abs_delta) and math.isfinite(first_abs_delta) else math.nan
    trend_from_min = final_abs_delta - min_abs_delta if math.isfinite(final_abs_delta) and math.isfinite(min_abs_delta) else math.nan
    y_delta_series = [float(r["max_abs_y_minus_y_target"]) for r in summary_rows]
    final_abs_y_delta = float(final_summary["max_abs_y_minus_y_target"])
    first_abs_y_delta = float(summary_rows[0]["max_abs_y_minus_y_target"])
    min_abs_y_delta = _min_or_nan(y_delta_series)
    y_trend_from_first = (
        final_abs_y_delta - first_abs_y_delta
        if math.isfinite(final_abs_y_delta) and math.isfinite(first_abs_y_delta)
        else math.nan
    )
    y_trend_from_min = (
        final_abs_y_delta - min_abs_y_delta
        if math.isfinite(final_abs_y_delta) and math.isfinite(min_abs_y_delta)
        else math.nan
    )

    checks: List[Dict[str, Any]] = []

    def add_check(name: str, value: float, limit: Optional[float]) -> None:
        if limit is None:
            return
        checks.append(
            {
                "name": name,
                "value": value,
                "limit": float(limit),
                "passed": bool(math.isfinite(value) and value <= float(limit)),
            }
        )

    add_check("final absolute K delta", final_abs_delta, max_final_abs_delta)
    add_check("peak absolute K delta", _max_or_nan(delta_series), max_peak_abs_delta)
    add_check("final absolute ln(K_state/K_thermo)", float(final_summary["max_abs_ln_K_state_over_K_thermo"]), max_final_abs_ln_ratio)
    add_check("positive absolute K delta trend from run minimum", trend_from_min, max_positive_abs_delta_trend)
    add_check("final absolute y-y_target", final_abs_y_delta, max_final_abs_y_delta)
    add_check("peak absolute y-y_target", _max_or_nan(y_delta_series), max_peak_abs_y_delta)
    add_check(
        "positive absolute y-y_target trend from run minimum",
        y_trend_from_min,
        max_positive_abs_y_delta_trend,
    )

    return {
        "profile_csv": str(Path(profile_csv).resolve()),
        "stages": sorted(stage_filter) if stage_filter else ("all" if include_terminal_stages else "interior"),
        "times": times_sorted,
        "component_labels": labels,
        "passed": all(bool(c["passed"]) for c in checks) if checks else None,
        "checks": checks,
        "summary": {
            "n_stage_rows": len(rows),
            "n_component_records": len(records),
            "first_time_s": times_sorted[0],
            "final_time_s": times_sorted[-1],
            "first_max_abs_K_state_minus_K_thermo": first_abs_delta,
            "min_max_abs_K_state_minus_K_thermo": min_abs_delta,
            "final_max_abs_K_state_minus_K_thermo": final_abs_delta,
            "peak_max_abs_K_state_minus_K_thermo": _max_or_nan(delta_series),
            "final_max_abs_ln_K_state_over_K_thermo": float(final_summary["max_abs_ln_K_state_over_K_thermo"]),
            "peak_max_abs_ln_K_state_over_K_thermo": _max_or_nan(ln_series),
            "positive_abs_delta_trend_from_first": trend_from_first,
            "positive_abs_delta_trend_from_min": trend_from_min,
            "final_worst_delta_stage_1based": final_summary["worst_delta_stage_1based"],
            "final_worst_delta_component": final_summary["worst_delta_component"],
            "final_worst_ln_stage_1based": final_summary["worst_ln_stage_1based"],
            "final_worst_ln_component": final_summary["worst_ln_component"],
            "first_max_abs_y_minus_y_target": first_abs_y_delta,
            "min_max_abs_y_minus_y_target": min_abs_y_delta,
            "final_max_abs_y_minus_y_target": final_abs_y_delta,
            "peak_max_abs_y_minus_y_target": _max_or_nan(y_delta_series),
            "positive_abs_y_delta_trend_from_first": y_trend_from_first,
            "positive_abs_y_delta_trend_from_min": y_trend_from_min,
            "final_worst_y_stage_1based": final_summary["worst_y_stage_1based"],
            "final_worst_y_component": final_summary["worst_y_component"],
        },
        "summary_by_time": summary_rows,
        "top_abs_delta_records": _top(records, "abs_K_state_minus_K_thermo", top_n),
        "top_abs_ln_ratio_records": _top(records, "abs_ln_K_state_over_K_thermo", top_n),
        "top_abs_y_delta_records": _top(records, "abs_y_minus_y_target", top_n),
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
    out = ["| " + " | ".join(fields) + " |", "|" + "|".join("---" for _ in fields) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_fmt(row.get(f)) if isinstance(row.get(f), (int, float)) else str(row.get(f, "")) for f in fields) + " |")
    return out


def write_markdown(report: Dict[str, Any], path: str | Path) -> None:
    lines = [
        "# Normalized Equilibrium-Target Drift Audit",
        "",
        f"Profile: `{report['profile_csv']}`",
        "",
        "## Gate",
    ]
    if report["checks"]:
        lines.append("| Check | Value | Limit | Result |")
        lines.append("|---|---:|---:|---|")
        for check in report["checks"]:
            lines.append(
                f"| {check['name']} | {_fmt(check['value'])} | {_fmt(check['limit'])} | {'PASS' if check['passed'] else 'FAIL'} |"
            )
    else:
        lines.append("No gate limits were supplied.")
    lines.extend(["", "## Summary"])
    lines.extend(
        _table(
            [report["summary"]],
            [
                "first_time_s",
                "final_time_s",
                "first_max_abs_y_minus_y_target",
                "min_max_abs_y_minus_y_target",
                "final_max_abs_y_minus_y_target",
                "peak_max_abs_y_minus_y_target",
                "positive_abs_y_delta_trend_from_min",
                "final_worst_y_stage_1based",
                "final_worst_y_component",
            ],
        )
    )
    lines.extend(["", "## Raw K Context (Not a Normalized Equilibrium Gate)"])
    lines.extend(
        _table(
            [report["summary"]],
            [
                "first_time_s",
                "final_time_s",
                "first_max_abs_K_state_minus_K_thermo",
                "min_max_abs_K_state_minus_K_thermo",
                "final_max_abs_K_state_minus_K_thermo",
                "peak_max_abs_K_state_minus_K_thermo",
                "final_max_abs_ln_K_state_over_K_thermo",
                "positive_abs_delta_trend_from_min",
                "final_worst_delta_stage_1based",
                "final_worst_delta_component",
            ],
        )
    )
    lines.extend(["", "## Summary By Time"])
    lines.extend(
        _table(
            report["summary_by_time"],
            [
                "time_s",
                "max_abs_K_state_minus_K_thermo",
                "max_abs_ln_K_state_over_K_thermo",
                "max_abs_y_minus_y_target",
                "worst_delta_stage_1based",
                "worst_delta_component",
                "worst_ln_stage_1based",
                "worst_ln_component",
                "worst_y_stage_1based",
                "worst_y_component",
            ],
        )
    )
    lines.extend(["", "## Top Normalized Vapor-Target Differences"])
    lines.extend(
        _table(
            report["top_abs_y_delta_records"],
            [
                "time_s",
                "stage_1based",
                "component",
                "y",
                "y_target",
                "y_minus_y_target",
                "abs_y_minus_y_target",
                "x",
                "K_state",
                "K_thermo",
            ],
        )
    )
    lines.extend(["", "## Top Absolute K Delta Records"])
    lines.extend(
        _table(
            report["top_abs_delta_records"],
            [
                "time_s",
                "stage_1based",
                "component",
                "K_state",
                "K_thermo",
                "K_state_minus_K_thermo",
                "abs_K_state_minus_K_thermo",
                "K_state_over_K_thermo",
                "x",
                "y",
                "y_target",
            ],
        )
    )
    lines.extend(["", "## Top Absolute ln Ratio Records"])
    lines.extend(
        _table(
            report["top_abs_ln_ratio_records"],
            [
                "time_s",
                "stage_1based",
                "component",
                "K_state",
                "K_thermo",
                "K_state_over_K_thermo",
                "abs_ln_K_state_over_K_thermo",
                "x",
                "y",
                "y_target",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit normalized equilibrium-target drift from a profile CSV.")
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--stages", default=None)
    ap.add_argument("--times", default=None)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--max-final-abs-delta", type=float, default=None)
    ap.add_argument("--max-peak-abs-delta", type=float, default=None)
    ap.add_argument("--max-final-abs-ln-ratio", type=float, default=None)
    ap.add_argument("--max-positive-abs-delta-trend", type=float, default=None)
    ap.add_argument("--max-final-abs-y-delta", type=float, default=None)
    ap.add_argument("--max-peak-abs-y-delta", type=float, default=None)
    ap.add_argument("--max-positive-abs-y-delta-trend", type=float, default=None)
    ap.add_argument(
        "--include-terminal-stages",
        action="store_true",
        help="Include top and bottom terminal states; default audit scope is generic interior stages.",
    )
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args()

    report = audit_profile(
        args.profile_csv,
        stages=sorted(_parse_csv_ints(args.stages) or []),
        times=sorted(_parse_csv_floats(args.times) or []),
        top_n=int(args.top_n),
        max_final_abs_delta=args.max_final_abs_delta,
        max_peak_abs_delta=args.max_peak_abs_delta,
        max_final_abs_ln_ratio=args.max_final_abs_ln_ratio,
        max_positive_abs_delta_trend=args.max_positive_abs_delta_trend,
        max_final_abs_y_delta=args.max_final_abs_y_delta,
        max_peak_abs_y_delta=args.max_peak_abs_y_delta,
        max_positive_abs_y_delta_trend=args.max_positive_abs_y_delta_trend,
        include_terminal_stages=bool(args.include_terminal_stages),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md)

    summary = report["summary"]
    print(f"Audited normalized equilibrium-target drift through t={_fmt(summary['final_time_s'])} s")
    print(f"final max |y-y_target| = {_fmt(summary['final_max_abs_y_minus_y_target'])}")
    print(f"y-target trend from minimum = {_fmt(summary['positive_abs_y_delta_trend_from_min'])}")
    print(
        "raw K context max |y/x-K_thermo| = "
        f"{_fmt(summary['final_max_abs_K_state_minus_K_thermo'])}"
    )
    if report["passed"] is not None:
        print("PASS" if report["passed"] else "FAIL")
        return 0 if report["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
