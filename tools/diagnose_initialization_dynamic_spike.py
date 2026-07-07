#!/usr/bin/env python
"""
Diagnose why an initialization candidate fails a dynamic smoke run.

This compares the summary/profile CSVs from two dynamic_run_scaffold_v1.py runs.
It is deliberately generic: stages are discovered from the CSV rows, and only
top/bottom endpoint fields are treated as named boundaries.
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


SUMMARY_FIELDS = [
    "steady_state_score",
    "ss_max_rel_state_rate_per_s",
    "ss_max_temp_rate_F_per_s",
    "pv_inner_dv_max_lbmolph",
    "pv_inner_dp_max_psia",
    "K_state_over_K_thermo_max_abs",
    "P_top_drum_psia",
    "Q_cond_calc_BTUph",
    "V_condensed_in_lbmolph",
    "top_L_net_lbmolph",
    "stage_mass_resid_sum_lbmolps",
    "T_sump_F",
]

PROFILE_FIELDS = [
    "V_out_lbmolph",
    "vflow_energy_calc_lbmolph",
    "vflow_energy_used_lbmolph",
    "hydraulic_dp_used_psia",
    "MV_lbmol",
    "ML_lbmol",
    "stage_mass_balance_resid_lbmolps",
    "stage_energy_balance_resid_BTUps",
    "dT_energy_raw_F_per_s",
    "T_F",
    "P_psia_hyd",
]

PROFILE_FIELD_PREFIXES = (
    "K_state_over_K_thermo_",
    "K_state_minus_K_thermo_",
    "x_",
    "y_",
    "y_target_",
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


def _read_csv(path: str | Path) -> List[Dict[str, str]]:
    resolved = _resolve(path)
    with resolved.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _time(row: Dict[str, str]) -> float:
    return _finite_float(row.get("time_s"), math.nan)


def _nearest_row(rows: List[Dict[str, str]], target_time_s: float) -> Dict[str, str]:
    finite_rows = [r for r in rows if math.isfinite(_time(r))]
    if not finite_rows:
        raise ValueError("CSV has no finite time rows")
    return min(finite_rows, key=lambda r: abs(_time(r) - float(target_time_s)))


def _ratio(candidate: float, baseline: float) -> float:
    if not math.isfinite(candidate) or not math.isfinite(baseline):
        return math.nan
    return abs(candidate) / max(abs(baseline), 1.0e-300)


def _summary_row_score(base_row: Dict[str, str], cand_row: Dict[str, str]) -> float:
    score_ratio = _ratio(
        _finite_float(cand_row.get("steady_state_score")),
        _finite_float(base_row.get("steady_state_score")),
    )
    rel_ratio = _ratio(
        _finite_float(cand_row.get("ss_max_rel_state_rate_per_s")),
        _finite_float(base_row.get("ss_max_rel_state_rate_per_s")),
    )
    ratios = [v for v in [score_ratio, rel_ratio] if math.isfinite(v)]
    return max(ratios) if ratios else math.nan


def find_worst_summary_time(
    baseline_rows: List[Dict[str, str]],
    candidate_rows: List[Dict[str, str]],
    *,
    start_time_s: Optional[float] = None,
    end_time_s: Optional[float] = None,
) -> float:
    best_time = math.nan
    best_score = -math.inf
    for cand_row in candidate_rows:
        t = _time(cand_row)
        if not math.isfinite(t):
            continue
        if start_time_s is not None and t < float(start_time_s) - 1.0e-9:
            continue
        if end_time_s is not None and t > float(end_time_s) + 1.0e-9:
            continue
        base_row = _nearest_row(baseline_rows, t)
        score = _summary_row_score(base_row, cand_row)
        if math.isfinite(score) and score > best_score:
            best_score = score
            best_time = t
    if not math.isfinite(best_time):
        raise ValueError("No comparable summary rows found in the requested time window")
    return best_time


def _field_delta(base_row: Dict[str, str], cand_row: Dict[str, str], field: str) -> Dict[str, Any]:
    base = _finite_float(base_row.get(field))
    cand = _finite_float(cand_row.get(field))
    diff = cand - base if math.isfinite(base) and math.isfinite(cand) else math.nan
    return {
        "field": field,
        "baseline": base,
        "candidate": cand,
        "difference": diff,
        "ratio": _ratio(cand, base),
    }


def _deviation_score(row: Dict[str, Any]) -> float:
    ratio = float(row.get("ratio", math.nan))
    diff = float(row.get("difference", math.nan))
    if math.isfinite(ratio) and ratio > 0.0:
        return max(ratio, 1.0 / ratio)
    if math.isfinite(diff):
        return abs(diff)
    return 0.0


def _meaningful_delta(row: Dict[str, Any]) -> bool:
    base = float(row.get("baseline", math.nan))
    cand = float(row.get("candidate", math.nan))
    diff = float(row.get("difference", math.nan))
    if not math.isfinite(diff):
        return False
    if math.isfinite(base) and math.isfinite(cand):
        if abs(base) < 1.0e-12 and abs(cand) < 1.0e-12 and abs(diff) < 1.0e-12:
            return False
    return True


def summary_deltas(
    baseline_rows: List[Dict[str, str]],
    candidate_rows: List[Dict[str, str]],
    *,
    time_s: float,
    fields: Iterable[str] = SUMMARY_FIELDS,
) -> Dict[str, Any]:
    base_row = _nearest_row(baseline_rows, time_s)
    cand_row = _nearest_row(candidate_rows, time_s)
    out = {
        "time_s": _time(cand_row),
        "baseline_time_s": _time(base_row),
        "candidate_worst_state_key": cand_row.get("ss_rel_state_rate_state_key", ""),
        "candidate_worst_state_stage_1based": cand_row.get("ss_rel_state_rate_stage_1based", ""),
        "candidate_worst_state_component": cand_row.get("ss_rel_state_rate_component_name", ""),
        "fields": [],
    }
    for field in fields:
        if field in base_row or field in cand_row:
            out["fields"].append(_field_delta(base_row, cand_row, field))
    out["fields"].sort(key=_deviation_score, reverse=True)
    return out


def _profile_rows_at(rows: List[Dict[str, str]], target_time_s: float) -> Dict[int, Dict[str, str]]:
    finite_times = sorted({_time(r) for r in rows if math.isfinite(_time(r))})
    if not finite_times:
        raise ValueError("profile CSV has no finite time rows")
    t = min(finite_times, key=lambda value: abs(value - float(target_time_s)))
    out: Dict[int, Dict[str, str]] = {}
    for row in rows:
        if abs(_time(row) - t) > 1.0e-9:
            continue
        if str(row.get("node_type", "")).strip().lower() != "stage":
            continue
        stage = int(round(_finite_float(row.get("stage"))))
        out[stage] = row
    return out


def _profile_fields(rows: Iterable[Dict[str, str]], requested: Iterable[str]) -> List[str]:
    fields = list(dict.fromkeys(requested))
    seen = set(fields)
    for row in rows:
        for field in row:
            if field in seen:
                continue
            if any(field.startswith(prefix) for prefix in PROFILE_FIELD_PREFIXES):
                fields.append(field)
                seen.add(field)
    return fields


def profile_deltas(
    baseline_rows: List[Dict[str, str]],
    candidate_rows: List[Dict[str, str]],
    *,
    time_s: float,
    fields: Iterable[str] = PROFILE_FIELDS,
    top_n: int = 8,
) -> List[Dict[str, Any]]:
    base_by_stage = _profile_rows_at(baseline_rows, time_s)
    cand_by_stage = _profile_rows_at(candidate_rows, time_s)
    expanded_fields = _profile_fields(list(base_by_stage.values()) + list(cand_by_stage.values()), fields)
    out: List[Dict[str, Any]] = []
    for stage in sorted(set(base_by_stage) & set(cand_by_stage)):
        field_rows = [_field_delta(base_by_stage[stage], cand_by_stage[stage], f) for f in expanded_fields]
        field_rows = [r for r in field_rows if _meaningful_delta(r)]
        field_rows.sort(key=_deviation_score, reverse=True)
        severity = max((_deviation_score(r) for r in field_rows), default=0.0)
        out.append({"stage_1based": stage, "severity": severity, "fields": field_rows[:5]})
    out.sort(key=lambda r: float(r["severity"]), reverse=True)
    return out[: int(top_n)]


def diagnose(
    *,
    baseline_summary: str | Path,
    candidate_summary: str | Path,
    baseline_profile: Optional[str | Path] = None,
    candidate_profile: Optional[str | Path] = None,
    start_time_s: Optional[float] = None,
    end_time_s: Optional[float] = None,
    top_n: int = 8,
) -> Dict[str, Any]:
    base_summary_rows = _read_csv(baseline_summary)
    cand_summary_rows = _read_csv(candidate_summary)
    worst_time = find_worst_summary_time(
        base_summary_rows,
        cand_summary_rows,
        start_time_s=start_time_s,
        end_time_s=end_time_s,
    )
    report: Dict[str, Any] = {
        "baseline_summary": str(_resolve(baseline_summary)),
        "candidate_summary": str(_resolve(candidate_summary)),
        "worst_time_s": worst_time,
        "summary": summary_deltas(base_summary_rows, cand_summary_rows, time_s=worst_time),
    }
    if baseline_profile and candidate_profile:
        report["baseline_profile"] = str(_resolve(baseline_profile))
        report["candidate_profile"] = str(_resolve(candidate_profile))
        report["profile"] = profile_deltas(
            _read_csv(baseline_profile),
            _read_csv(candidate_profile),
            time_s=worst_time,
            top_n=top_n,
        )
    return report


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        if math.isfinite(value):
            return f"{value:.6g}"
        return "nan"
    return str(value)


def _write_markdown(path: Path, report: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Initialization Dynamic Spike Diagnosis")
    lines.append("")
    lines.append(f"Worst time: `{_fmt(float(report['worst_time_s']))} s`")
    lines.append("")
    summary = report["summary"]
    lines.append(
        "Worst candidate state-rate row: "
        f"`{summary.get('candidate_worst_state_key')}` "
        f"stage `{summary.get('candidate_worst_state_stage_1based')}` "
        f"component `{summary.get('candidate_worst_state_component')}`"
    )
    lines.append("")
    lines.append("## Summary Drivers")
    lines.append("")
    lines.append("| Field | Baseline | Candidate | Difference | Ratio |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in summary["fields"][:12]:
        lines.append(
            f"| {row['field']} | {_fmt(row['baseline'])} | {_fmt(row['candidate'])} | "
            f"{_fmt(row['difference'])} | {_fmt(row['ratio'])} |"
        )
    if report.get("profile"):
        lines.append("")
        lines.append("## Profile Drivers")
        lines.append("")
        for stage in report["profile"]:
            lines.append(f"### Stage {stage['stage_1based']}")
            lines.append("")
            lines.append("| Field | Baseline | Candidate | Difference | Ratio |")
            lines.append("|---|---:|---:|---:|---:|")
            for row in stage["fields"]:
                lines.append(
                    f"| {row['field']} | {_fmt(row['baseline'])} | {_fmt(row['candidate'])} | "
                    f"{_fmt(row['difference'])} | {_fmt(row['ratio'])} |"
                )
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Diagnose a dynamic initialization candidate spike.")
    ap.add_argument("--baseline-summary", required=True)
    ap.add_argument("--candidate-summary", required=True)
    ap.add_argument("--baseline-profile", default=None)
    ap.add_argument("--candidate-profile", default=None)
    ap.add_argument("--start-time-s", type=float, default=None)
    ap.add_argument("--end-time-s", type=float, default=None)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args(argv)

    report = diagnose(
        baseline_summary=args.baseline_summary,
        candidate_summary=args.candidate_summary,
        baseline_profile=args.baseline_profile,
        candidate_profile=args.candidate_profile,
        start_time_s=args.start_time_s,
        end_time_s=args.end_time_s,
        top_n=args.top,
    )

    if args.output_json:
        out_json = _resolve(args.output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        out_md = _resolve(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        _write_markdown(out_md, report)

    print(f"Worst time: {_fmt(float(report['worst_time_s']))} s")
    summary = report["summary"]
    print(
        "Worst state-rate row: "
        f"{summary.get('candidate_worst_state_key')} "
        f"stage={summary.get('candidate_worst_state_stage_1based')} "
        f"component={summary.get('candidate_worst_state_component')}"
    )
    for row in summary["fields"][:8]:
        print(
            f"  {row['field']}: baseline={_fmt(row['baseline'])} "
            f"candidate={_fmt(row['candidate'])} ratio={_fmt(row['ratio'])} diff={_fmt(row['difference'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
