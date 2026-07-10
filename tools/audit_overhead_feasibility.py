#!/usr/bin/env python
"""
Audit whether a dynamic run has enough overhead condensate for its top draws.

The audit is intentionally generic over tray count. It uses logged top-boundary
rates from column_summary plus per-stage vapor-flow diagnostics from
column_profile when available.
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


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return sum(vals) / len(vals) if vals else math.nan


def _field(row: Dict[str, str], name: str) -> float:
    return _finite_float(row.get(name), math.nan)


def _last_window_rows(rows: List[Dict[str, str]], final_window_s: float) -> List[Dict[str, str]]:
    times = [_field(r, "time_s") for r in rows]
    finite_times = [t for t in times if math.isfinite(t)]
    if not finite_times:
        return []
    final_t = max(finite_times)
    start_t = final_t - max(float(final_window_s), 0.0)
    return [r for r in rows if _field(r, "time_s") >= start_t - 1.0e-9]


def _final_summary(rows: List[Dict[str, str]], final_window_s: float) -> Dict[str, Any]:
    if not rows:
        return {}
    final = rows[-1]
    window = _last_window_rows(rows, final_window_s)

    condensate = _field(final, "V_condensed_in_lbmolph")
    if not math.isfinite(condensate):
        condensate = _field(final, "top_L_cond_in_lbmolph")
    reflux = _field(final, "top_L_reflux_out_lbmolph")
    distillate = _field(final, "top_L_distillate_out_lbmolph")
    demand = reflux + distillate if math.isfinite(reflux) and math.isfinite(distillate) else math.nan

    mean_condensate = _mean(
        _field(r, "V_condensed_in_lbmolph")
        if math.isfinite(_field(r, "V_condensed_in_lbmolph"))
        else _field(r, "top_L_cond_in_lbmolph")
        for r in window
    )
    mean_reflux = _mean(_field(r, "top_L_reflux_out_lbmolph") for r in window)
    mean_distillate = _mean(_field(r, "top_L_distillate_out_lbmolph") for r in window)
    mean_demand = mean_reflux + mean_distillate if math.isfinite(mean_reflux) and math.isfinite(mean_distillate) else math.nan

    return {
        "time_s": _field(final, "time_s"),
        "condensate_lbmolph": condensate,
        "reflux_lbmolph": reflux,
        "distillate_lbmolph": distillate,
        "top_draw_demand_lbmolph": demand,
        "condensate_minus_reflux_lbmolph": condensate - reflux
        if math.isfinite(condensate) and math.isfinite(reflux)
        else math.nan,
        "condensate_minus_top_draws_lbmolph": condensate - demand
        if math.isfinite(condensate) and math.isfinite(demand)
        else math.nan,
        "reflux_to_distillate_ratio": reflux / distillate
        if math.isfinite(reflux) and math.isfinite(distillate) and abs(distillate) > 1.0e-300
        else math.nan,
        "top_level_pv": _field(final, "Top_level_ctrl_pv"),
        "top_level_sp": _field(final, "Top_level_ctrl_sp"),
        "top_drum_pressure_psia": _field(final, "P_top_drum_psia"),
        "top_drum_pressure_raw_psia": _field(final, "P_top_drum_psia_raw"),
        "q_cond_used_BTUph": _field(final, "Q_cond_used_BTUph"),
        "q_cond_calc_BTUph": _field(final, "Q_cond_calc_BTUph"),
        "mean_window_s": float(final_window_s),
        "mean_condensate_lbmolph": mean_condensate,
        "mean_reflux_lbmolph": mean_reflux,
        "mean_distillate_lbmolph": mean_distillate,
        "mean_top_draw_demand_lbmolph": mean_demand,
        "mean_condensate_minus_reflux_lbmolph": mean_condensate - mean_reflux
        if math.isfinite(mean_condensate) and math.isfinite(mean_reflux)
        else math.nan,
        "mean_condensate_minus_top_draws_lbmolph": mean_condensate - mean_demand
        if math.isfinite(mean_condensate) and math.isfinite(mean_demand)
        else math.nan,
        "mean_reflux_to_distillate_ratio": mean_reflux / mean_distillate
        if math.isfinite(mean_reflux) and math.isfinite(mean_distillate) and abs(mean_distillate) > 1.0e-300
        else math.nan,
    }


def _stage_number(row: Dict[str, str]) -> Optional[int]:
    stage = _finite_float(row.get("stage"), math.nan)
    if not math.isfinite(stage):
        return None
    return int(round(stage))


def _profile_summary(rows: List[Dict[str, str]], final_window_s: float) -> Dict[str, Any]:
    stage_rows = [r for r in rows if str(r.get("node_type", "")).lower() == "stage"]
    if not stage_rows:
        return {}

    final_t = max(_field(r, "time_s") for r in stage_rows if math.isfinite(_field(r, "time_s")))
    final_rows = [r for r in stage_rows if abs(_field(r, "time_s") - final_t) <= 1.0e-9]
    final_by_stage = {s: r for r in final_rows if (s := _stage_number(r)) is not None}
    if not final_by_stage:
        return {}

    top_stage = min(final_by_stage)
    bottom_stage = max(final_by_stage)
    vapor_stages = [
        (s, _field(r, "V_out_lbmolph"))
        for s, r in final_by_stage.items()
        if math.isfinite(_field(r, "V_out_lbmolph"))
    ]
    top_vapor = _field(final_by_stage[top_stage], "V_out_lbmolph")
    bottom_vapor = _field(final_by_stage[bottom_stage], "V_out_lbmolph")
    finite_vapor = [(s, v) for s, v in vapor_stages if math.isfinite(v)]
    positive_vapor = [(s, v) for s, v in sorted(finite_vapor) if v > 1.0e-9]
    overhead_stage = positive_vapor[0][0] if positive_vapor else math.nan
    overhead_vapor = positive_vapor[0][1] if positive_vapor else math.nan

    largest_drop: Dict[str, float] = {
        "from_stage": math.nan,
        "to_stage": math.nan,
        "delta_lbmolph": math.nan,
    }
    by_stage = dict(finite_vapor)
    for upper_stage in sorted(by_stage):
        lower_stage = upper_stage + 1
        if lower_stage not in by_stage:
            continue
        v_upper = by_stage[upper_stage]
        v_lower = by_stage[lower_stage]
        if v_upper <= 1.0e-9 or v_lower <= 1.0e-9:
            continue
        delta = v_lower - v_upper
        if not math.isfinite(largest_drop["delta_lbmolph"]) or delta > largest_drop["delta_lbmolph"]:
            largest_drop = {
                "from_stage": float(lower_stage),
                "to_stage": float(upper_stage),
                "delta_lbmolph": float(delta),
            }

    window = [r for r in stage_rows if _field(r, "time_s") >= final_t - max(float(final_window_s), 0.0) - 1.0e-9]
    clamp_rows = [r for r in window if _field(r, "vflow_energy_clamped") > 0.5]

    return {
        "final_time_s": final_t,
        "top_stage": top_stage,
        "bottom_stage": bottom_stage,
        "top_stage_v_out_lbmolph": top_vapor,
        "bottom_stage_v_out_lbmolph": bottom_vapor,
        "overhead_vapor_stage": overhead_stage,
        "overhead_vapor_to_condenser_lbmolph": overhead_vapor,
        "overhead_vapor_fraction_of_bottom": overhead_vapor / bottom_vapor
        if math.isfinite(overhead_vapor) and math.isfinite(bottom_vapor) and abs(bottom_vapor) > 1.0e-300
        else math.nan,
        "top_vapor_fraction_of_bottom": top_vapor / bottom_vapor
        if math.isfinite(top_vapor) and math.isfinite(bottom_vapor) and abs(bottom_vapor) > 1.0e-300
        else math.nan,
        "largest_adjacent_vapor_drop": largest_drop,
        "vflow_clamped_rows_in_final_window": len(clamp_rows),
        "vflow_rows_in_final_window": len(window),
        "vflow_clamped_fraction_in_final_window": len(clamp_rows) / len(window) if window else math.nan,
    }


def audit_overhead_feasibility(
    summary_rows: List[Dict[str, str]],
    *,
    profile_rows: Optional[List[Dict[str, str]]] = None,
    final_window_s: float = 300.0,
    reference_reflux_lbmolph: Optional[float] = None,
    reference_distillate_lbmolph: Optional[float] = None,
) -> Dict[str, Any]:
    final = _final_summary(summary_rows, final_window_s)
    profile = _profile_summary(profile_rows or [], final_window_s)

    ref_reflux = float(reference_reflux_lbmolph) if reference_reflux_lbmolph is not None else math.nan
    ref_dist = float(reference_distillate_lbmolph) if reference_distillate_lbmolph is not None else math.nan
    ref_overhead = ref_reflux + ref_dist if math.isfinite(ref_reflux) and math.isfinite(ref_dist) else math.nan
    condensate = float(final.get("condensate_lbmolph", math.nan))
    mean_condensate = float(final.get("mean_condensate_lbmolph", math.nan))

    diagnosis = "unknown"
    if math.isfinite(final.get("condensate_minus_reflux_lbmolph", math.nan)) and final["condensate_minus_reflux_lbmolph"] < 0.0:
        diagnosis = "top_starved_before_distillate"
    elif math.isfinite(final.get("condensate_minus_top_draws_lbmolph", math.nan)) and final["condensate_minus_top_draws_lbmolph"] < 0.0:
        diagnosis = "top_starved_after_reflux_and_distillate"
    elif math.isfinite(ref_overhead) and math.isfinite(condensate) and condensate < 0.9 * ref_overhead:
        diagnosis = "overhead_vapor_below_reference"
    else:
        diagnosis = "top_overhead_feasible_at_final_time"

    return {
        "diagnosis": diagnosis,
        "final_window_s": float(final_window_s),
        "final_top_boundary": final,
        "profile": profile,
        "reference": {
            "reflux_lbmolph": ref_reflux,
            "distillate_lbmolph": ref_dist,
            "overhead_condensate_demand_lbmolph": ref_overhead,
            "final_condensate_fraction_of_reference": condensate / ref_overhead
            if math.isfinite(condensate) and math.isfinite(ref_overhead) and abs(ref_overhead) > 1.0e-300
            else math.nan,
            "mean_condensate_fraction_of_reference": mean_condensate / ref_overhead
            if math.isfinite(mean_condensate) and math.isfinite(ref_overhead) and abs(ref_overhead) > 1.0e-300
            else math.nan,
        },
    }


def _fmt(value: Any) -> str:
    val = _finite_float(value, math.nan)
    if not math.isfinite(val):
        return "nan"
    return f"{val:.6g}"


def write_markdown(path: Path, report: Dict[str, Any], *, summary_path: Path, profile_path: Optional[Path]) -> None:
    final = report.get("final_top_boundary", {})
    profile = report.get("profile", {})
    ref = report.get("reference", {})

    lines = [
        "# Overhead Feasibility Audit",
        "",
        f"Summary CSV: `{summary_path}`",
        f"Profile CSV: `{profile_path}`" if profile_path is not None else "Profile CSV: `not provided`",
        f"Diagnosis: `{report.get('diagnosis', 'unknown')}`",
        "",
        "## Top Boundary",
        "",
        "| Metric | Final | Final-window mean |",
        "|---|---:|---:|",
    ]
    metric_pairs = (
        ("condensate_lbmolph", "mean_condensate_lbmolph"),
        ("reflux_lbmolph", "mean_reflux_lbmolph"),
        ("distillate_lbmolph", "mean_distillate_lbmolph"),
        ("top_draw_demand_lbmolph", "mean_top_draw_demand_lbmolph"),
        ("condensate_minus_reflux_lbmolph", "mean_condensate_minus_reflux_lbmolph"),
        ("condensate_minus_top_draws_lbmolph", "mean_condensate_minus_top_draws_lbmolph"),
        ("reflux_to_distillate_ratio", "mean_reflux_to_distillate_ratio"),
    )
    for final_key, mean_key in metric_pairs:
        lines.append(f"| `{final_key}` | {_fmt(final.get(final_key))} | {_fmt(final.get(mean_key))} |")

    lines.extend(
        [
            "",
            "## Reference",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| `reference_reflux_lbmolph` | {_fmt(ref.get('reflux_lbmolph'))} |",
            f"| `reference_distillate_lbmolph` | {_fmt(ref.get('distillate_lbmolph'))} |",
            f"| `reference_overhead_condensate_demand_lbmolph` | {_fmt(ref.get('overhead_condensate_demand_lbmolph'))} |",
            f"| `final_condensate_fraction_of_reference` | {_fmt(ref.get('final_condensate_fraction_of_reference'))} |",
            f"| `mean_condensate_fraction_of_reference` | {_fmt(ref.get('mean_condensate_fraction_of_reference'))} |",
            "",
            "## Vapor Profile",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| `top_stage` | {_fmt(profile.get('top_stage'))} |",
            f"| `bottom_stage` | {_fmt(profile.get('bottom_stage'))} |",
            f"| `top_stage_v_out_lbmolph` | {_fmt(profile.get('top_stage_v_out_lbmolph'))} |",
            f"| `bottom_stage_v_out_lbmolph` | {_fmt(profile.get('bottom_stage_v_out_lbmolph'))} |",
            f"| `overhead_vapor_stage` | {_fmt(profile.get('overhead_vapor_stage'))} |",
            f"| `overhead_vapor_to_condenser_lbmolph` | {_fmt(profile.get('overhead_vapor_to_condenser_lbmolph'))} |",
            f"| `overhead_vapor_fraction_of_bottom` | {_fmt(profile.get('overhead_vapor_fraction_of_bottom'))} |",
            f"| `top_vapor_fraction_of_bottom` | {_fmt(profile.get('top_vapor_fraction_of_bottom'))} |",
            f"| `vflow_clamped_fraction_in_final_window` | {_fmt(profile.get('vflow_clamped_fraction_in_final_window'))} |",
        ]
    )
    drop = profile.get("largest_adjacent_vapor_drop", {}) or {}
    lines.append(
        f"| `largest_adjacent_vapor_drop_lbmolph` | {_fmt(drop.get('delta_lbmolph'))} "
        f"from stage {_fmt(drop.get('from_stage'))} to {_fmt(drop.get('to_stage'))} |"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Audit overhead condensate feasibility from dynamic run logs.")
    ap.add_argument("--summary-csv", required=True)
    ap.add_argument("--profile-csv", default=None)
    ap.add_argument("--final-window-s", type=float, default=300.0)
    ap.add_argument("--reference-reflux-lbmolph", type=float, default=None)
    ap.add_argument("--reference-distillate-lbmolph", type=float, default=None)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args(argv)

    summary_path = _resolve(args.summary_csv)
    profile_path = _resolve(args.profile_csv) if args.profile_csv else None
    report = audit_overhead_feasibility(
        _read_csv(summary_path),
        profile_rows=_read_csv(profile_path) if profile_path is not None else None,
        final_window_s=float(args.final_window_s),
        reference_reflux_lbmolph=args.reference_reflux_lbmolph,
        reference_distillate_lbmolph=args.reference_distillate_lbmolph,
    )

    if args.output_json:
        out_json = _resolve(args.output_json)
        out_json.write_text(json.dumps(report, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, allow_nan=True))

    if args.output_md:
        write_markdown(_resolve(args.output_md), report, summary_path=summary_path, profile_path=profile_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
