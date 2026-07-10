#!/usr/bin/env python
"""
Audit conflict between vapor material transport and equilibrium transfer.

This read-only diagnostic uses profile CSV columns written by
dynamic_run_scaffold_v1.py. It ranks explicit tray vapor component rows where
the pre-equilibrium transport RHS would require an equilibrium target that is
far from the logged `y_target`.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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
        if key.startswith("tray_V_pre_equilibrium_rhs_lbmolps_"):
            labels.append(key[len("tray_V_pre_equilibrium_rhs_lbmolps_") :])
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


def _ratio(value: float, denom: float) -> float:
    if not math.isfinite(value) or not math.isfinite(denom) or abs(denom) <= 1.0e-300:
        return math.nan
    return value / denom


def _classify_stage(stage: int, max_stage: int) -> str:
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
        raise ValueError("No component labels found")

    max_stage = max(int(round(_finite_float(r.get("stage")))) for r in rows)
    tau_default = float(equilibrium_tau_sec)
    if not math.isfinite(tau_default) or tau_default <= 0.0:
        raise ValueError("equilibrium_tau_sec must be positive")

    records: List[Dict[str, Any]] = []
    stage_records: Dict[int, Dict[str, Any]] = {}

    for row in rows:
        stage = int(round(_finite_float(row.get("stage"))))
        mv = _finite_float(row.get("MV_lbmol"))
        if not math.isfinite(mv) or mv <= 0.0:
            mv = math.nan
        stage_kind = _classify_stage(stage, max_stage)
        stage_abs_conflict = 0.0
        stage_abs_final = 0.0

        for label in labels:
            y = _finite_float(row.get(f"y_{label}"))
            y_target = _finite_float(row.get(f"y_target_{label}"))
            pre = _finite_float(row.get(f"tray_V_pre_equilibrium_rhs_lbmolps_{label}"))
            final = _finite_float(row.get(f"tray_V_final_rhs_lbmolps_{label}"))
            eq = _finite_float(row.get(f"tray_V_equilibrium_transfer_lbmolps_{label}"))
            transport_in = _finite_float(row.get(f"tray_V_transport_in_lbmolps_{label}"))
            transport_out = _finite_float(row.get(f"tray_V_transport_out_lbmolps_{label}"))

            inferred_tau = math.nan
            if (
                math.isfinite(mv)
                and math.isfinite(y)
                and math.isfinite(y_target)
                and math.isfinite(eq)
                and abs(eq) > 1.0e-300
            ):
                inferred_tau = _ratio(mv * (y_target - y), eq)
            tau = inferred_tau if math.isfinite(inferred_tau) and inferred_tau > 0.0 else tau_default

            required_y_target = math.nan
            required_target_delta = math.nan
            required_shift_from_y = math.nan
            feasible_component = math.nan
            if math.isfinite(mv) and math.isfinite(y) and math.isfinite(pre):
                required_shift_from_y = -pre * tau / mv
                required_y_target = y + required_shift_from_y
                feasible_component = 1.0 if 0.0 <= required_y_target <= 1.0 else 0.0
                if math.isfinite(y_target):
                    required_target_delta = required_y_target - y_target

            cancellation_coverage = -_ratio(eq, pre)
            damping = (
                1.0
                if math.isfinite(eq) and math.isfinite(pre) and abs(pre) > 1.0e-300 and (eq * pre) < 0.0
                else 0.0
            )
            fighting = (
                1.0
                if math.isfinite(eq) and math.isfinite(pre) and abs(pre) > 1.0e-300 and (eq * pre) > 0.0
                else 0.0
            )
            conflict_score = abs(required_target_delta) if math.isfinite(required_target_delta) else math.nan
            final_abs = abs(final) if math.isfinite(final) else math.nan

            if math.isfinite(conflict_score):
                stage_abs_conflict = max(stage_abs_conflict, conflict_score)
            if math.isfinite(final_abs):
                stage_abs_final = max(stage_abs_final, final_abs)

            records.append(
                {
                    "stage_1based": stage,
                    "stage_kind": stage_kind,
                    "component": label,
                    "MV_lbmol": mv,
                    "y": y,
                    "y_target": y_target,
                    "required_y_target_to_cancel_pre_rhs": required_y_target,
                    "required_target_delta": required_target_delta,
                    "required_shift_from_y": required_shift_from_y,
                    "required_target_component_feasible": feasible_component,
                    "inferred_tau_sec": inferred_tau,
                    "tau_used_sec": tau,
                    "pre_equilibrium_rhs_lbmolps": pre,
                    "equilibrium_transfer_lbmolps": eq,
                    "final_rhs_lbmolps": final,
                    "cancellation_coverage": cancellation_coverage,
                    "equilibrium_damps_transport": damping,
                    "equilibrium_fights_transport": fighting,
                    "transport_in_lbmolps": transport_in,
                    "transport_out_lbmolps": transport_out,
                    "conflict_score": conflict_score,
                }
            )

        stage_records[stage] = {
            "stage_1based": stage,
            "stage_kind": stage_kind,
            "max_abs_required_target_delta": stage_abs_conflict,
            "max_abs_final_rhs_lbmolps": stage_abs_final,
        }

    records.sort(
        key=lambda r: (
            abs(float(r["final_rhs_lbmolps"])) if math.isfinite(float(r.get("final_rhs_lbmolps", math.nan))) else -math.inf,
            abs(float(r["conflict_score"])) if math.isfinite(float(r.get("conflict_score", math.nan))) else -math.inf,
        ),
        reverse=True,
    )
    conflict_records = sorted(
        records,
        key=lambda r: abs(float(r["conflict_score"]))
        if math.isfinite(float(r.get("conflict_score", math.nan)))
        else -math.inf,
        reverse=True,
    )
    interior_records = [r for r in records if r["stage_kind"] == "interior"]
    interior_conflicts = [r for r in conflict_records if r["stage_kind"] == "interior"]
    stages_sorted = sorted(
        stage_records.values(),
        key=lambda r: abs(float(r["max_abs_final_rhs_lbmolps"])),
        reverse=True,
    )
    feasible = [
        float(r["required_target_component_feasible"])
        for r in records
        if math.isfinite(float(r.get("required_target_component_feasible", math.nan)))
    ]
    coverage_vals = [
        float(r["cancellation_coverage"])
        for r in records
        if math.isfinite(float(r.get("cancellation_coverage", math.nan)))
    ]

    return {
        "profile_csv": str(Path(profile_csv).resolve()),
        "time_s": float(time_s),
        "equilibrium_tau_sec_default": tau_default,
        "component_labels": labels,
        "summary": {
            "n_stages": len(rows),
            "n_components": len(labels),
            "max_abs_final_rhs_lbmolps": _max_abs_or_nan(
                float(r["final_rhs_lbmolps"]) for r in records
            ),
            "max_abs_required_target_delta": _max_abs_or_nan(
                float(r["conflict_score"]) for r in records
            ),
            "fraction_required_components_feasible": sum(feasible) / len(feasible) if feasible else math.nan,
            "median_cancellation_coverage": _median(coverage_vals),
        },
        "top_final_rhs_conflicts": records[: max(int(top_n), 1)],
        "top_required_target_conflicts": conflict_records[: max(int(top_n), 1)],
        "top_interior_final_rhs_conflicts": interior_records[: max(int(top_n), 1)],
        "top_interior_required_target_conflicts": interior_conflicts[: max(int(top_n), 1)],
        "top_stage_conflicts": stages_sorted[: max(int(top_n), 1)],
    }


def _median(values: List[float]) -> float:
    finite = sorted(v for v in values if math.isfinite(v))
    if not finite:
        return math.nan
    mid = len(finite) // 2
    if len(finite) % 2:
        return float(finite[mid])
    return float(0.5 * (finite[mid - 1] + finite[mid]))


def _max_abs_or_nan(values: Iterable[float]) -> float:
    finite = [abs(float(v)) for v in values if math.isfinite(float(v))]
    return max(finite) if finite else math.nan


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
        "final_rhs_lbmolps",
        "pre_equilibrium_rhs_lbmolps",
        "equilibrium_transfer_lbmolps",
        "cancellation_coverage",
        "y",
        "y_target",
        "required_y_target_to_cancel_pre_rhs",
        "required_target_delta",
        "required_target_component_feasible",
    ]
    lines: List[str] = [
        "# Vapor Transport / Equilibrium Conflict Audit",
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
                "max_abs_final_rhs_lbmolps",
                "max_abs_required_target_delta",
                "fraction_required_components_feasible",
                "median_cancellation_coverage",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.",
            "- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.",
            "- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.",
            "",
            "## Top Final RHS Conflicts",
        ]
    )
    lines.extend(_table(report["top_final_rhs_conflicts"], fields))
    lines.append("")
    lines.append("## Top Required Target Conflicts")
    lines.extend(_table(report["top_required_target_conflicts"], fields))
    lines.append("")
    lines.append("## Top Interior Final RHS Conflicts")
    lines.extend(_table(report["top_interior_final_rhs_conflicts"], fields))
    lines.append("")
    lines.append("## Top Stage Conflicts")
    lines.extend(
        _table(
            report["top_stage_conflicts"],
            [
                "stage_1based",
                "stage_kind",
                "max_abs_required_target_delta",
                "max_abs_final_rhs_lbmolps",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit vapor transport/equilibrium target conflicts from profile CSV.")
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
