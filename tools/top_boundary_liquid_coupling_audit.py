#!/usr/bin/env python
"""
Compare top-boundary liquid coupling between baseline and candidate runs.

This report uses the dynamic_run_scaffold_v1 column_summary CSV fields. It is
generic over component names and does not assume a specific tray count.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def _time_key(row: Dict[str, str], *, ndigits: int = 9) -> float:
    return round(_finite_float(row.get("time_s"), math.nan), ndigits)


def _rows_by_time(rows: Iterable[Dict[str, str]], max_time_s: Optional[float]) -> Dict[float, Dict[str, str]]:
    out: Dict[float, Dict[str, str]] = {}
    for row in rows:
        t = _time_key(row)
        if not math.isfinite(t):
            continue
        if max_time_s is not None and t > float(max_time_s) + 1.0e-9:
            continue
        out[t] = row
    return out


def component_names(rows: Iterable[Dict[str, str]]) -> List[str]:
    names = set()
    for row in rows:
        for field in row:
            prefix = "top_L_net_"
            suffix = "_lbmolph"
            if field.startswith(prefix) and field.endswith(suffix):
                name = field[len(prefix) : -len(suffix)]
                if name and not name.startswith("worst"):
                    names.add(name)
    return sorted(names)


def _ratio(candidate: float, baseline: float) -> float:
    if not math.isfinite(candidate) or not math.isfinite(baseline):
        return math.nan
    return abs(candidate) / max(abs(baseline), 1.0e-300)


def _field(row: Dict[str, str], name: str) -> float:
    return _finite_float(row.get(name), math.nan)


def _record(
    *,
    time_s: float,
    component: str,
    field: str,
    baseline: float,
    candidate: float,
) -> Dict[str, Any]:
    return {
        "time_s": float(time_s),
        "component": component,
        "field": field,
        "baseline": baseline,
        "candidate": candidate,
        "abs_baseline": abs(baseline) if math.isfinite(baseline) else math.nan,
        "abs_candidate": abs(candidate) if math.isfinite(candidate) else math.nan,
        "abs_delta": abs(candidate) - abs(baseline)
        if math.isfinite(candidate) and math.isfinite(baseline)
        else math.nan,
        "ratio": _ratio(candidate, baseline),
    }


def compare_top_liquid(
    baseline_rows: List[Dict[str, str]],
    candidate_rows: List[Dict[str, str]],
    *,
    max_time_s: Optional[float] = None,
    top_n: int = 10,
) -> Dict[str, Any]:
    base_by_time = _rows_by_time(baseline_rows, max_time_s)
    cand_by_time = _rows_by_time(candidate_rows, max_time_s)
    times = sorted(set(base_by_time).intersection(cand_by_time))
    comps = sorted(set(component_names(baseline_rows)).union(component_names(candidate_rows)))

    component_records: List[Dict[str, Any]] = []
    composition_records: List[Dict[str, Any]] = []
    for t in times:
        brow = base_by_time[t]
        crow = cand_by_time[t]
        for comp in comps:
            component_records.append(
                _record(
                    time_s=t,
                    component=comp,
                    field="top_L_net_component_lbmolph",
                    baseline=_field(brow, f"top_L_net_{comp}_lbmolph"),
                    candidate=_field(crow, f"top_L_net_{comp}_lbmolph"),
                )
            )
            composition_records.append(
                _record(
                    time_s=t,
                    component=comp,
                    field="top_L_cond_x_minus_drum_x",
                    baseline=_field(brow, f"top_L_cond_x_minus_drum_x_{comp}"),
                    candidate=_field(crow, f"top_L_cond_x_minus_drum_x_{comp}"),
                )
            )

    total_records = [
        _record(
            time_s=t,
            component="total",
            field="top_L_net_lbmolph",
            baseline=_field(base_by_time[t], "top_L_net_lbmolph"),
            candidate=_field(cand_by_time[t], "top_L_net_lbmolph"),
        )
        for t in times
    ]

    worst_component_records = [
        _record(
            time_s=t,
            component="worst",
            field="top_L_net_worst_abs_lbmolph",
            baseline=_field(base_by_time[t], "top_L_net_worst_abs_lbmolph"),
            candidate=_field(cand_by_time[t], "top_L_net_worst_abs_lbmolph"),
        )
        for t in times
    ]

    def top(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        finite = [r for r in records if math.isfinite(float(r["abs_delta"]))]
        finite.sort(key=lambda r: (float(r["abs_delta"]), float(r["abs_candidate"])), reverse=True)
        return finite[: max(int(top_n), 0)]

    final_time = times[-1] if times else math.nan
    final_base = base_by_time.get(final_time, {})
    final_cand = cand_by_time.get(final_time, {})

    return {
        "compared_times": times,
        "components": comps,
        "final_time_s": final_time,
        "final_baseline": {
            "top_L_net_lbmolph": _field(final_base, "top_L_net_lbmolph"),
            "top_L_net_worst_component_1based": _field(final_base, "top_L_net_worst_component_1based"),
            "top_L_net_worst_abs_lbmolph": _field(final_base, "top_L_net_worst_abs_lbmolph"),
            "V_condensed_in_lbmolph": _field(final_base, "V_condensed_in_lbmolph"),
            "top_L_reflux_out_lbmolph": _field(final_base, "top_L_reflux_out_lbmolph"),
            "top_L_distillate_out_lbmolph": _field(final_base, "top_L_distillate_out_lbmolph"),
        },
        "final_candidate": {
            "top_L_net_lbmolph": _field(final_cand, "top_L_net_lbmolph"),
            "top_L_net_worst_component_1based": _field(final_cand, "top_L_net_worst_component_1based"),
            "top_L_net_worst_abs_lbmolph": _field(final_cand, "top_L_net_worst_abs_lbmolph"),
            "V_condensed_in_lbmolph": _field(final_cand, "V_condensed_in_lbmolph"),
            "top_L_reflux_out_lbmolph": _field(final_cand, "top_L_reflux_out_lbmolph"),
            "top_L_distillate_out_lbmolph": _field(final_cand, "top_L_distillate_out_lbmolph"),
        },
        "worst_component_net_worsenings": top(component_records),
        "worst_total_net_worsenings": top(total_records),
        "worst_worst-component_worsenings": top(worst_component_records),
        "worst_condensed_vs_drum_x_worsenings": top(composition_records),
    }


def _fmt(value: Any) -> str:
    val = _finite_float(value, math.nan)
    if not math.isfinite(val):
        return "nan"
    return f"{val:.6g}"


def write_markdown(path: Path, report: Dict[str, Any], *, baseline_path: Path, candidate_path: Path) -> None:
    lines: List[str] = []
    lines.append("# Top Boundary Liquid Coupling Audit")
    lines.append("")
    lines.append(f"Baseline: `{baseline_path}`")
    lines.append(f"Candidate: `{candidate_path}`")
    lines.append(f"Final compared time: `{_fmt(report.get('final_time_s'))} s`")
    lines.append("")
    lines.append("## Final Summary")
    lines.append("")
    lines.append("| Metric | Baseline | Candidate |")
    lines.append("|---|---:|---:|")
    for key in (
        "top_L_net_lbmolph",
        "top_L_net_worst_component_1based",
        "top_L_net_worst_abs_lbmolph",
        "V_condensed_in_lbmolph",
        "top_L_reflux_out_lbmolph",
        "top_L_distillate_out_lbmolph",
    ):
        lines.append(
            f"| `{key}` | {_fmt(report['final_baseline'].get(key))} | {_fmt(report['final_candidate'].get(key))} |"
        )

    sections = (
        ("Worst Component Net Worsenings", "worst_component_net_worsenings"),
        ("Worst Total Net Worsenings", "worst_total_net_worsenings"),
        ("Worst Worst-Component Worsenings", "worst_worst-component_worsenings"),
        ("Worst Condensed-vs-Drum Composition Worsenings", "worst_condensed_vs_drum_x_worsenings"),
    )
    for title, key in sections:
        records = report.get(key) or []
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |")
        lines.append("|---:|---|---|---:|---:|---:|---:|")
        for r in records:
            lines.append(
                "| {time_s:.6g} | {component} | `{field}` | {ratio:.6g} | {abs_delta:.6g} | {candidate:.6g} | {baseline:.6g} |".format(
                    **r
                )
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Audit top-boundary liquid coupling from summary CSV logs.")
    ap.add_argument("--baseline-summary", required=True)
    ap.add_argument("--candidate-summary", required=True)
    ap.add_argument("--max-time-s", type=float, default=None)
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args(argv)

    baseline_path = _resolve(args.baseline_summary)
    candidate_path = _resolve(args.candidate_summary)
    report = compare_top_liquid(
        _read_csv(baseline_path),
        _read_csv(candidate_path),
        max_time_s=args.max_time_s,
        top_n=args.top_n,
    )
    full_report = {
        "baseline_summary": str(baseline_path),
        "candidate_summary": str(candidate_path),
        **report,
    }
    if args.output_json:
        out_json = _resolve(args.output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(full_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        out_md = _resolve(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(out_md, full_report, baseline_path=baseline_path, candidate_path=candidate_path)

    print(f"Compared {len(report['compared_times'])} times across {len(report['components'])} components")
    if report["worst_component_net_worsenings"]:
        worst = report["worst_component_net_worsenings"][0]
        print(
            "Worst component net worsening: "
            f"t={worst['time_s']:.6g}s component={worst['component']} "
            f"delta={worst['abs_delta']:.6g} lbmol/h"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
