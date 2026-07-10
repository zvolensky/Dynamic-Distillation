#!/usr/bin/env python
"""
Compare initialization candidates against a baseline dynamic smoke run.

The residual audit is a necessary t=0 consistency check, but it is not enough
to accept an initialized workbook. This tool gates candidates using the summary
CSV files written by dynamic_run_scaffold_v1.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]


MetricSummary = Dict[str, float]
CandidateReport = Dict[str, Any]


DEFAULT_SCORE_FIELD = "steady_state_score"
DEFAULT_REL_RATE_FIELD = "ss_max_rel_state_rate_per_s"
DEFAULT_TEMP_RATE_FIELD = "ss_max_temp_rate_F_per_s"


FAILURE_BREAKDOWN_FIELDS = (
    (
        "dynamic score",
        "final_score",
        "steady_state_score",
        "Overall dynamic gate score at the final evaluated row.",
    ),
    (
        "relative state rate",
        "final_rel_rate_per_s",
        "ss_max_rel_state_rate_per_s",
        "Largest normalized state derivative at the final evaluated row.",
    ),
    (
        "temperature rate",
        "final_temp_rate_F_per_s",
        "ss_max_temp_rate_F_per_s",
        "Largest absolute temperature derivative at the final evaluated row.",
    ),
    (
        "top liquid component net",
        "final_top_L_net_worst_abs_lbmolph",
        "top_L_net_worst_abs_lbmolph",
        "Largest top liquid component imbalance at the final evaluated row.",
    ),
    (
        "top liquid total net",
        "final_top_L_net_lbmolph",
        "top_L_net_lbmolph",
        "Total top liquid net imbalance at the final evaluated row.",
    ),
    (
        "K-state minus K-thermo",
        "final_K_state_minus_K_thermo_max_abs",
        "K_state_minus_K_thermo_max_abs",
        "Largest absolute K-state/K-thermo mismatch at the final evaluated row.",
    ),
    (
        "K-state over K-thermo",
        "final_K_state_over_K_thermo_max_abs",
        "K_state_over_K_thermo_max_abs",
        "Largest K-state/K-thermo ratio diagnostic at the final evaluated row.",
    ),
    (
        "pressure/vapor-flow inner solve",
        "final_pv_inner_dv_max_lbmolph",
        "pv_inner_dv_max_lbmolph",
        "Largest vapor-flow correction requested by the inner pressure/vapor solve.",
    ),
    (
        "pressure inner solve",
        "final_pv_inner_dp_max_psia",
        "pv_inner_dp_max_psia",
        "Largest pressure correction requested by the inner pressure/vapor solve.",
    ),
)


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _finite_float(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _read_summary_csv(path: str | Path) -> List[Dict[str, str]]:
    resolved = _resolve(path)
    with resolved.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _row_time_s(row: Dict[str, str]) -> float:
    return _finite_float(row.get("time_s"), math.nan)


def _rows_in_window(rows: List[Dict[str, str]], max_time_s: Optional[float]) -> List[Dict[str, str]]:
    finite_rows = [r for r in rows if math.isfinite(_row_time_s(r))]
    if max_time_s is None:
        return finite_rows
    return [r for r in finite_rows if _row_time_s(r) <= float(max_time_s) + 1.0e-9]


def _last_row(rows: List[Dict[str, str]]) -> Dict[str, str]:
    if not rows:
        raise ValueError("summary CSV has no finite time rows")
    return max(rows, key=_row_time_s)


def _max_field(rows: Iterable[Dict[str, str]], field: str) -> float:
    vals = [_finite_float(r.get(field), math.nan) for r in rows]
    vals = [v for v in vals if math.isfinite(v)]
    return max(vals) if vals else math.nan


def _field(row: Dict[str, str], field: str) -> float:
    return _finite_float(row.get(field), math.nan)


def summarize_run(
    rows: List[Dict[str, str]],
    *,
    max_time_s: Optional[float] = None,
    score_field: str = DEFAULT_SCORE_FIELD,
    rel_rate_field: str = DEFAULT_REL_RATE_FIELD,
    temp_rate_field: str = DEFAULT_TEMP_RATE_FIELD,
    endpoint_fields: Iterable[str] = (),
    summary_ratio_fields: Iterable[str] = (),
) -> MetricSummary:
    window_rows = _rows_in_window(rows, max_time_s)
    final = _last_row(window_rows)
    summary: MetricSummary = {
        "final_time_s": _row_time_s(final),
        "final_score": _field(final, score_field),
        "peak_score": _max_field(window_rows, score_field),
        "final_rel_rate_per_s": _field(final, rel_rate_field),
        "peak_rel_rate_per_s": _max_field(window_rows, rel_rate_field),
        "final_temp_rate_F_per_s": _field(final, temp_rate_field),
        "peak_temp_rate_F_per_s": _max_field(window_rows, temp_rate_field),
    }
    for field in endpoint_fields:
        summary[f"final_{field}"] = _field(final, field)
    for field in summary_ratio_fields:
        summary[f"final_{field}"] = _field(final, field)
        summary[f"peak_{field}"] = _max_field(window_rows, field)
    return summary


def _summary_fields_for_breakdown(rows: List[Dict[str, str]]) -> List[str]:
    fields: List[str] = []
    if rows:
        available = set(rows[0])
    else:
        available = set()
    for _name, _summary_key, csv_field, _description in FAILURE_BREAKDOWN_FIELDS:
        if csv_field in available:
            fields.append(csv_field)
    return fields


def _ratio(candidate: float, baseline: float) -> float:
    if not math.isfinite(candidate) or not math.isfinite(baseline):
        return math.nan
    denom = max(abs(baseline), 1.0e-300)
    return abs(candidate) / denom


def _add_ratio_check(
    checks: List[Dict[str, Any]],
    *,
    name: str,
    candidate: MetricSummary,
    baseline: MetricSummary,
    metric: str,
    limit: float,
) -> None:
    cand = float(candidate.get(metric, math.nan))
    base = float(baseline.get(metric, math.nan))
    value = _ratio(cand, base)
    checks.append(
        {
            "name": name,
            "metric": metric,
            "candidate": cand,
            "baseline": base,
            "value": value,
            "limit": float(limit),
            "passed": bool(math.isfinite(value) and value <= float(limit)),
        }
    )


def _add_absolute_drift_check(
    checks: List[Dict[str, Any]],
    *,
    name: str,
    candidate: MetricSummary,
    baseline: MetricSummary,
    metric: str,
    limit: float,
) -> None:
    cand = float(candidate.get(metric, math.nan))
    base = float(baseline.get(metric, math.nan))
    value = abs(cand - base) if math.isfinite(cand) and math.isfinite(base) else math.nan
    checks.append(
        {
            "name": name,
            "metric": metric,
            "candidate": cand,
            "baseline": base,
            "value": value,
            "limit": float(limit),
            "passed": bool(math.isfinite(value) and value <= float(limit)),
        }
    )


def failure_breakdown(
    baseline: MetricSummary,
    candidate: MetricSummary,
    *,
    top_n: int = 8,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for name, metric, source_field, description in FAILURE_BREAKDOWN_FIELDS:
        cand = float(candidate.get(metric, math.nan))
        base = float(baseline.get(metric, math.nan))
        if not (math.isfinite(cand) and math.isfinite(base)):
            continue
        ratio = _ratio(cand, base)
        delta = abs(cand) - abs(base)
        records.append(
            {
                "name": name,
                "metric": metric,
                "source_field": source_field,
                "description": description,
                "candidate": cand,
                "baseline": base,
                "abs_candidate": abs(cand),
                "abs_baseline": abs(base),
                "abs_delta": delta,
                "ratio": ratio,
            }
        )
    records.sort(
        key=lambda r: (
            0 if math.isfinite(float(r["abs_delta"])) and float(r["abs_delta"]) > 0.0 else 1,
            -float(r["abs_delta"]) if math.isfinite(float(r["abs_delta"])) else 0.0,
            -float(r["ratio"]) if math.isfinite(float(r["ratio"])) else 0.0,
        )
    )
    return records[: max(int(top_n), 0)]


def evaluate_candidate(
    baseline: MetricSummary,
    candidate: MetricSummary,
    *,
    max_final_score_ratio: float = 1.0,
    max_peak_score_ratio: float = 1.0,
    max_final_rel_rate_ratio: float = 1.0,
    max_peak_rel_rate_ratio: float = 1.0,
    max_final_temp_rate_ratio: Optional[float] = None,
    endpoint_drift_limits: Optional[Dict[str, float]] = None,
    summary_ratio_limits: Optional[Dict[str, float]] = None,
) -> CandidateReport:
    checks: List[Dict[str, Any]] = []
    _add_ratio_check(
        checks,
        name="final score ratio",
        candidate=candidate,
        baseline=baseline,
        metric="final_score",
        limit=max_final_score_ratio,
    )
    _add_ratio_check(
        checks,
        name="peak score ratio",
        candidate=candidate,
        baseline=baseline,
        metric="peak_score",
        limit=max_peak_score_ratio,
    )
    _add_ratio_check(
        checks,
        name="final relative state-rate ratio",
        candidate=candidate,
        baseline=baseline,
        metric="final_rel_rate_per_s",
        limit=max_final_rel_rate_ratio,
    )
    _add_ratio_check(
        checks,
        name="peak relative state-rate ratio",
        candidate=candidate,
        baseline=baseline,
        metric="peak_rel_rate_per_s",
        limit=max_peak_rel_rate_ratio,
    )
    if max_final_temp_rate_ratio is not None:
        _add_ratio_check(
            checks,
            name="final temperature-rate ratio",
            candidate=candidate,
            baseline=baseline,
            metric="final_temp_rate_F_per_s",
            limit=float(max_final_temp_rate_ratio),
        )
    for field, limit in (endpoint_drift_limits or {}).items():
        _add_absolute_drift_check(
            checks,
            name=f"{field} final absolute drift",
            candidate=candidate,
            baseline=baseline,
            metric=f"final_{field}",
            limit=float(limit),
        )
    for field, limit in (summary_ratio_limits or {}).items():
        _add_ratio_check(
            checks,
            name=f"{field} final ratio",
            candidate=candidate,
            baseline=baseline,
            metric=f"final_{field}",
            limit=float(limit),
        )
        _add_ratio_check(
            checks,
            name=f"{field} peak ratio",
            candidate=candidate,
            baseline=baseline,
            metric=f"peak_{field}",
            limit=float(limit),
        )
    passed = all(bool(c["passed"]) for c in checks)
    return {"passed": passed, "checks": checks}


def _parse_endpoint_limit(raw: str) -> tuple[str, float]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("endpoint drift limits must be FIELD=LIMIT")
    field, value = raw.split("=", 1)
    field = field.strip()
    if not field:
        raise argparse.ArgumentTypeError("endpoint drift field cannot be empty")
    limit = _finite_float(value, math.nan)
    if not math.isfinite(limit) or limit < 0.0:
        raise argparse.ArgumentTypeError("endpoint drift limit must be a nonnegative finite number")
    return field, limit


def _parse_ratio_limit(raw: str) -> tuple[str, float]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("summary ratio limits must be FIELD=LIMIT")
    field, value = raw.split("=", 1)
    field = field.strip()
    if not field:
        raise argparse.ArgumentTypeError("summary ratio field cannot be empty")
    limit = _finite_float(value, math.nan)
    if not math.isfinite(limit) or limit < 0.0:
        raise argparse.ArgumentTypeError("summary ratio limit must be a nonnegative finite number")
    return field, limit


def _write_markdown(path: Path, report: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Initialization Dynamic Gate")
    lines.append("")
    lines.append(f"Baseline: `{report['baseline_path']}`")
    lines.append("")
    for cand in report["candidates"]:
        status = "PASS" if cand["passed"] else "FAIL"
        lines.append(f"## {cand['label']}: {status}")
        lines.append("")
        lines.append("| Check | Value | Limit | Candidate | Baseline | Result |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for check in cand["checks"]:
            result = "PASS" if check["passed"] else "FAIL"
            lines.append(
                "| {name} | {value:.6g} | {limit:.6g} | {candidate:.6g} | {baseline:.6g} | {result} |".format(
                    **check,
                    result=result,
                )
            )
        lines.append("")
        breakdown = cand.get("failure_breakdown") or []
        if breakdown:
            lines.append("### Failure Breakdown")
            lines.append("")
            lines.append("| Family | Ratio | Abs delta | Candidate | Baseline | Field |")
            lines.append("|---|---:|---:|---:|---:|---|")
            for item in breakdown:
                lines.append(
                    "| {name} | {ratio:.6g} | {abs_delta:.6g} | {candidate:.6g} | {baseline:.6g} | `{source_field}` |".format(
                        **item
                    )
                )
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Gate initialization candidates against a baseline dynamic run.")
    ap.add_argument("--baseline-summary", required=True, help="Baseline column_summary CSV.")
    ap.add_argument("--candidate-summary", action="append", required=True, help="Candidate column_summary CSV.")
    ap.add_argument("--candidate-label", action="append", default=None, help="Optional label matching --candidate-summary order.")
    ap.add_argument("--max-time-s", type=float, default=None, help="Only evaluate rows up to this simulation time.")
    ap.add_argument("--max-final-score-ratio", type=float, default=1.0)
    ap.add_argument("--max-peak-score-ratio", type=float, default=1.0)
    ap.add_argument("--max-final-rel-rate-ratio", type=float, default=1.0)
    ap.add_argument("--max-peak-rel-rate-ratio", type=float, default=1.0)
    ap.add_argument("--max-final-temp-rate-ratio", type=float, default=None)
    ap.add_argument(
        "--endpoint-drift-limit",
        action="append",
        type=_parse_endpoint_limit,
        default=[],
        help="Absolute final endpoint drift limit, e.g. P_top_drum_psia=0.5. Repeatable.",
    )
    ap.add_argument(
        "--summary-ratio-limit",
        action="append",
        type=_parse_ratio_limit,
        default=[],
        help="Final and peak candidate/baseline ratio limit for a summary CSV field, e.g. pv_inner_dv_max_lbmolph=1.0. Repeatable.",
    )
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    ap.add_argument("--failure-breakdown-top-n", type=int, default=8)
    args = ap.parse_args(argv)

    endpoint_limits = dict(args.endpoint_drift_limit or [])
    endpoint_fields = sorted(endpoint_limits)
    summary_ratio_limits = dict(args.summary_ratio_limit or [])
    summary_ratio_fields = sorted(summary_ratio_limits)

    baseline_path = _resolve(args.baseline_summary)
    baseline_rows = _read_summary_csv(baseline_path)
    breakdown_fields = _summary_fields_for_breakdown(baseline_rows)
    baseline_summary = summarize_run(
        baseline_rows,
        max_time_s=args.max_time_s,
        endpoint_fields=endpoint_fields,
        summary_ratio_fields=sorted(set(summary_ratio_fields).union(breakdown_fields)),
    )

    labels = list(args.candidate_label or [])
    if labels and len(labels) != len(args.candidate_summary):
        ap.error("--candidate-label must be supplied once per --candidate-summary when used")

    candidates: List[CandidateReport] = []
    for idx, raw_path in enumerate(args.candidate_summary):
        path = _resolve(raw_path)
        label = labels[idx] if labels else path.parent.name or path.name
        candidate_rows = _read_summary_csv(path)
        candidate_breakdown_fields = _summary_fields_for_breakdown(candidate_rows)
        all_summary_ratio_fields = sorted(
            set(summary_ratio_fields).union(breakdown_fields).union(candidate_breakdown_fields)
        )
        candidate_summary = summarize_run(
            candidate_rows,
            max_time_s=args.max_time_s,
            endpoint_fields=endpoint_fields,
            summary_ratio_fields=all_summary_ratio_fields,
        )
        report = evaluate_candidate(
            baseline_summary,
            candidate_summary,
            max_final_score_ratio=args.max_final_score_ratio,
            max_peak_score_ratio=args.max_peak_score_ratio,
            max_final_rel_rate_ratio=args.max_final_rel_rate_ratio,
            max_peak_rel_rate_ratio=args.max_peak_rel_rate_ratio,
            max_final_temp_rate_ratio=args.max_final_temp_rate_ratio,
            endpoint_drift_limits=endpoint_limits,
            summary_ratio_limits=summary_ratio_limits,
        )
        report.update(
            {
                "label": label,
                "summary_path": str(path),
                "summary": candidate_summary,
                "failure_breakdown": failure_breakdown(
                    baseline_summary,
                    candidate_summary,
                    top_n=args.failure_breakdown_top_n,
                ),
            }
        )
        candidates.append(report)

    full_report = {
        "passed": all(bool(c["passed"]) for c in candidates),
        "baseline_path": str(baseline_path),
        "baseline_summary": baseline_summary,
        "candidates": candidates,
    }

    if args.output_json:
        out_json = _resolve(args.output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(full_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        out_md = _resolve(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        _write_markdown(out_md, full_report)

    for cand in candidates:
        status = "PASS" if cand["passed"] else "FAIL"
        print(f"{cand['label']}: {status}")
        for check in cand["checks"]:
            result = "PASS" if check["passed"] else "FAIL"
            print(
                "  {name}: value={value:.6g} limit={limit:.6g} candidate={candidate:.6g} baseline={baseline:.6g} {result}".format(
                    **check,
                    result=result,
                )
            )
        if cand.get("failure_breakdown"):
            print("  Failure breakdown:")
            for item in cand["failure_breakdown"]:
                print(
                    "    {name}: ratio={ratio:.6g} abs_delta={abs_delta:.6g} candidate={candidate:.6g} baseline={baseline:.6g} field={source_field}".format(
                        **item
                    )
                )

    return 0 if full_report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
