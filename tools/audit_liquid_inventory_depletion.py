#!/usr/bin/env python
"""Audit tray liquid inventory depletion from a dynamic profile CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


COMPONENT_PREFIX = "x_"


def _finite_float(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _read_rows(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _stage_rows(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in rows:
        if str(row.get("node_type", "")).strip().lower() != "stage":
            continue
        if not math.isfinite(_finite_float(row.get("stage"))):
            continue
        if not math.isfinite(_finite_float(row.get("time_s"))):
            continue
        out.append(row)
    return out


def _component_fields(rows: List[Dict[str, str]]) -> List[str]:
    if not rows:
        return []
    fields = rows[0].keys()
    return sorted(f for f in fields if f.startswith(COMPONENT_PREFIX))


def _infer_min_dt_s(rows: List[Dict[str, str]]) -> float:
    times = sorted({_finite_float(r.get("time_s")) for r in rows})
    deltas = [
        b - a
        for a, b in zip(times, times[1:])
        if math.isfinite(a) and math.isfinite(b) and b > a
    ]
    return min(deltas) if deltas else math.nan


def audit_profile(
    rows: List[Dict[str, str]],
    *,
    min_liquid_lbmol: float = 1.0,
    update_fraction_limit: float = 0.25,
    denominator_floor_lbmol: float = 1.0,
    include_terminal_stages: bool = False,
) -> Dict[str, Any]:
    stage_rows = _stage_rows(rows)
    if not stage_rows:
        raise ValueError("profile CSV contains no stage rows with finite time/stage")

    min_dt_s = _infer_min_dt_s(stage_rows)
    component_fields = _component_fields(stage_rows)
    by_stage: Dict[int, List[Dict[str, str]]] = {}
    for row in stage_rows:
        stage = int(round(_finite_float(row.get("stage"))))
        by_stage.setdefault(stage, []).append(row)

    records: List[Dict[str, Any]] = []
    stage_numbers = sorted(by_stage)
    terminal_stages = {stage_numbers[0], stage_numbers[-1]} if len(stage_numbers) >= 2 else set()

    for stage, items in sorted(by_stage.items()):
        if (not include_terminal_stages) and stage in terminal_stages:
            continue
        items = sorted(items, key=lambda r: _finite_float(r.get("time_s")))
        min_row = min(items, key=lambda r: _finite_float(r.get("ML_lbmol"), math.inf))
        min_ml = _finite_float(min_row.get("ML_lbmol"))
        min_time = _finite_float(min_row.get("time_s"))
        worst_update_fraction = math.nan
        worst_update_time = math.nan
        worst_dml = math.nan
        worst_time_to_empty = math.nan
        worst_comp_step = 0.0
        worst_comp_step_time = math.nan
        worst_comp_step_component = ""

        for prev, cur in zip(items, items[1:]):
            t_prev = _finite_float(prev.get("time_s"))
            t_cur = _finite_float(cur.get("time_s"))
            dt = t_cur - t_prev
            if not (math.isfinite(dt) and dt > 0.0):
                dt = min_dt_s
            ml = _finite_float(prev.get("ML_lbmol"))
            dml = _finite_float(prev.get("dMLdt_total_lbmolps"))
            if math.isfinite(ml) and math.isfinite(dml) and math.isfinite(dt):
                update_fraction = abs(dml) * dt / max(abs(ml), float(denominator_floor_lbmol))
                if not math.isfinite(worst_update_fraction) or update_fraction > worst_update_fraction:
                    worst_update_fraction = update_fraction
                    worst_update_time = t_prev
                    worst_dml = dml
                    if dml < 0.0:
                        worst_time_to_empty = ml / abs(dml) if ml > 0.0 else 0.0
                    else:
                        worst_time_to_empty = math.inf
            for field in component_fields:
                a = _finite_float(prev.get(field))
                b = _finite_float(cur.get(field))
                if math.isfinite(a) and math.isfinite(b):
                    step = abs(b - a)
                    if step > worst_comp_step:
                        worst_comp_step = step
                        worst_comp_step_time = t_cur
                        worst_comp_step_component = field.removeprefix(COMPONENT_PREFIX)

        records.append(
            {
                "stage_1based": stage,
                "min_ML_lbmol": min_ml,
                "min_ML_time_s": min_time,
                "below_min_liquid": bool(math.isfinite(min_ml) and min_ml < float(min_liquid_lbmol)),
                "worst_update_fraction": worst_update_fraction,
                "worst_update_time_s": worst_update_time,
                "worst_dMLdt_total_lbmolps": worst_dml,
                "worst_time_to_empty_s": worst_time_to_empty,
                "update_fraction_exceeds_limit": bool(
                    math.isfinite(worst_update_fraction)
                    and worst_update_fraction > float(update_fraction_limit)
                ),
                "worst_composition_step": worst_comp_step,
                "worst_composition_step_time_s": worst_comp_step_time,
                "worst_composition_step_component": worst_comp_step_component,
            }
        )

    risky = [
        r
        for r in records
        if r["below_min_liquid"] or r["update_fraction_exceeds_limit"]
    ]
    top_by_inventory = sorted(records, key=lambda r: r["min_ML_lbmol"])[:10]
    top_by_update = sorted(
        records,
        key=lambda r: (
            -r["worst_update_fraction"]
            if math.isfinite(float(r["worst_update_fraction"]))
            else math.inf
        ),
    )[:10]
    top_by_composition_step = sorted(records, key=lambda r: -float(r["worst_composition_step"]))[:10]

    return {
        "n_stage_rows": len(stage_rows),
        "n_stages": len(by_stage),
        "min_dt_s": min_dt_s,
        "min_liquid_limit_lbmol": float(min_liquid_lbmol),
        "update_fraction_limit": float(update_fraction_limit),
        "denominator_floor_lbmol": float(denominator_floor_lbmol),
        "include_terminal_stages": bool(include_terminal_stages),
        "passed": not risky,
        "risk_count": len(risky),
        "top_by_low_inventory": top_by_inventory,
        "top_by_update_fraction": top_by_update,
        "top_by_composition_step": top_by_composition_step,
        "stage_records": records,
    }


def _fmt(value: Any, digits: int = 6) -> str:
    try:
        f = float(value)
    except Exception:
        return str(value)
    if not math.isfinite(f):
        return "nan"
    return f"{f:.{digits}g}"


def write_markdown(report: Dict[str, Any], path: str | Path, *, profile_csv: str | Path) -> None:
    lines = [
        "# Liquid Inventory Depletion Audit",
        "",
        f"Profile: `{Path(profile_csv).resolve()}`",
        "",
        "## Summary",
        "",
        "| Check | Value |",
        "|---|---:|",
        f"| stages | {report['n_stages']} |",
        f"| stage rows | {report['n_stage_rows']} |",
        f"| minimum logged dt, s | {_fmt(report['min_dt_s'])} |",
        f"| minimum liquid limit, lbmol | {_fmt(report['min_liquid_limit_lbmol'])} |",
        f"| update fraction limit | {_fmt(report['update_fraction_limit'])} |",
        f"| risky stages | {report['risk_count']} |",
        f"| passed | {report['passed']} |",
        "",
        "## Interpretation",
        "",
        "- `min_ML_lbmol` flags trays that approach an empty liquid state.",
        "- `worst_update_fraction` estimates how large one logged liquid-inventory update is relative to the available liquid inventory.",
        "- A low inventory plus a large update fraction can make explicit composition updates snap even when broader residual metrics look acceptable.",
        "",
        "## Lowest Inventories",
        "",
        "| stage_1based | min_ML_lbmol | time_s | below_limit | worst_update_fraction | worst_time_to_empty_s | worst_composition_step | component |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in report["top_by_low_inventory"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r["stage_1based"]),
                    _fmt(r["min_ML_lbmol"]),
                    _fmt(r["min_ML_time_s"]),
                    str(r["below_min_liquid"]),
                    _fmt(r["worst_update_fraction"]),
                    _fmt(r["worst_time_to_empty_s"]),
                    _fmt(r["worst_composition_step"]),
                    str(r["worst_composition_step_component"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Largest Inventory Update Fractions",
            "",
            "| stage_1based | worst_update_fraction | time_s | dMLdt_total_lbmolps | min_ML_lbmol | update_limit_exceeded |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in report["top_by_update_fraction"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r["stage_1based"]),
                    _fmt(r["worst_update_fraction"]),
                    _fmt(r["worst_update_time_s"]),
                    _fmt(r["worst_dMLdt_total_lbmolps"]),
                    _fmt(r["min_ML_lbmol"]),
                    str(r["update_fraction_exceeds_limit"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Largest Composition Steps",
            "",
            "| stage_1based | composition_step | time_s | component | min_ML_lbmol |",
            "|---:|---:|---:|---|---:|",
        ]
    )
    for r in report["top_by_composition_step"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r["stage_1based"]),
                    _fmt(r["worst_composition_step"]),
                    _fmt(r["worst_composition_step_time_s"]),
                    str(r["worst_composition_step_component"]),
                    _fmt(r["min_ML_lbmol"]),
                ]
            )
            + " |"
        )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-csv", required=True)
    parser.add_argument("--min-liquid-lbmol", type=float, default=1.0)
    parser.add_argument("--update-fraction-limit", type=float, default=0.25)
    parser.add_argument("--denominator-floor-lbmol", type=float, default=1.0)
    parser.add_argument(
        "--include-terminal-stages",
        action="store_true",
        help="Include top and bottom terminal stages in the pass/fail assessment.",
    )
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    args = parser.parse_args()

    rows = _read_rows(args.profile_csv)
    report = audit_profile(
        rows,
        min_liquid_lbmol=args.min_liquid_lbmol,
        update_fraction_limit=args.update_fraction_limit,
        denominator_floor_lbmol=args.denominator_floor_lbmol,
        include_terminal_stages=bool(args.include_terminal_stages),
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md, profile_csv=args.profile_csv)
    if not args.output_json and not args.output_md:
        print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "Audited "
        f"{report['n_stages']} stages; "
        f"risky stages={report['risk_count']}; "
        f"passed={report['passed']}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
