#!/usr/bin/env python
"""
Audit vapor material-transport pulses from profile CSV diagnostics.

This is a read-only diagnostic. It uses logged live RHS transport terms and
stage profiles to separate large vapor component rates into:

- vapor traffic magnitude,
- upstream/downstream vapor composition mismatch,
- local vapor inventory scale,
- and non-transport source/sink terms.
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
        if key.startswith("tray_V_final_rhs_lbmolps_"):
            labels.append(key.removeprefix("tray_V_final_rhs_lbmolps_"))
    if labels:
        return sorted(labels)
    for key in row.keys():
        if key.startswith("y_") and not key.startswith("y_eq_") and not key.startswith("y_target_"):
            labels.append(key[2:])
    return sorted(labels)


def _stage(row: Dict[str, str]) -> int:
    return int(round(_finite_float(row.get("stage"))))


def _stage_rows(rows: List[Dict[str, str]], time_s: float) -> List[Dict[str, str]]:
    out = []
    for row in rows:
        if str(row.get("node_type", "")).strip().lower() != "stage":
            continue
        t = _finite_float(row.get("time_s"))
        if math.isfinite(t) and abs(t - float(time_s)) <= 1.0e-9:
            out.append(row)
    return sorted(out, key=_stage)


def _infer_time(rows: List[Dict[str, str]]) -> float:
    times = sorted(
        {
            _finite_float(row.get("time_s"))
            for row in rows
            if str(row.get("node_type", "")).strip().lower() == "stage"
            and math.isfinite(_finite_float(row.get("time_s")))
        }
    )
    if not times:
        raise ValueError("No stage rows with finite time_s")
    return float(times[-1])


def _transport_driver(
    *,
    transport_in: float,
    transport_out: float,
    flow_term: float,
    gradient_term: float,
) -> str:
    if not math.isfinite(transport_in) or not math.isfinite(transport_out):
        return "unknown"
    if math.isfinite(gradient_term) and abs(gradient_term) >= 0.5 * max(abs(transport_in), abs(transport_out), 1e-300):
        return "composition_gradient"
    if math.isfinite(flow_term) and abs(flow_term) >= 0.5 * max(abs(transport_in), abs(transport_out), 1e-300):
        return "flow_magnitude"
    if abs(transport_in + transport_out) >= 0.25 * max(abs(transport_in), abs(transport_out), 1e-300):
        return "net_transport"
    return "mixed"


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
    by_stage = {_stage(row): row for row in rows}
    stages = sorted(by_stage)
    labels = _component_labels(rows[0])
    if not labels:
        raise ValueError("No component labels found")
    floor = max(float(denom_floor_lbmol), 0.0)

    records: List[Dict[str, Any]] = []
    stage_records: List[Dict[str, Any]] = []

    for st in stages:
        row = by_stage[st]
        src = by_stage.get(st + 1)
        mv = _finite_float(row.get("MV_lbmol"))
        if not math.isfinite(mv):
            mv = 0.0
        v_out = _finite_float(row.get("V_out_lbmolph"))
        v_in = _finite_float(row.get("vflow_energy_V_in_lbmolph"))
        if not math.isfinite(v_in) and src is not None:
            v_in = _finite_float(src.get("V_out_lbmolph"))
        max_rel = 0.0
        max_final = 0.0
        stage_driver_counts: Dict[str, int] = {}

        for label in labels:
            y = _finite_float(row.get(f"y_{label}"))
            y_src = _finite_float(src.get(f"y_{label}")) if src is not None else y
            tin = _finite_float(row.get(f"tray_V_transport_in_lbmolps_{label}"))
            tout = _finite_float(row.get(f"tray_V_transport_out_lbmolps_{label}"))
            final_rhs = _finite_float(row.get(f"tray_V_final_rhs_lbmolps_{label}"))
            pre_rhs = _finite_float(row.get(f"tray_V_pre_equilibrium_rhs_lbmolps_{label}"))
            eq = _finite_float(row.get(f"tray_V_equilibrium_transfer_lbmolps_{label}"))
            inv = max(mv * y, 0.0) if math.isfinite(y) else 0.0
            rel = abs(final_rhs) / max(abs(inv) + floor, 1.0e-300) if math.isfinite(final_rhs) else math.nan

            flow_term = math.nan
            gradient_term = math.nan
            if math.isfinite(v_in) and math.isfinite(v_out) and math.isfinite(y) and math.isfinite(y_src):
                common_flow = min(abs(v_in), abs(v_out))
                flow_term = ((v_in - v_out) * y) / 3600.0
                gradient_term = common_flow * (y_src - y) / 3600.0

            driver = _transport_driver(
                transport_in=tin,
                transport_out=tout,
                flow_term=flow_term,
                gradient_term=gradient_term,
            )
            stage_driver_counts[driver] = stage_driver_counts.get(driver, 0) + 1
            if math.isfinite(rel):
                max_rel = max(max_rel, abs(rel))
            if math.isfinite(final_rhs):
                max_final = max(max_final, abs(final_rhs))

            records.append(
                {
                    "stage_1based": st,
                    "component": label,
                    "MV_lbmol": mv,
                    "component_inventory_lbmol": inv,
                    "V_in_lbmolph_est": v_in,
                    "V_out_lbmolph": v_out,
                    "V_in_minus_out_lbmolph_est": (
                        v_in - v_out if math.isfinite(v_in) and math.isfinite(v_out) else math.nan
                    ),
                    "y_upstream_est": y_src,
                    "y_stage": y,
                    "y_upstream_minus_stage": (
                        y_src - y if math.isfinite(y_src) and math.isfinite(y) else math.nan
                    ),
                    "transport_in_lbmolps": tin,
                    "transport_out_lbmolps": tout,
                    "net_transport_lbmolps": (
                        tin + tout if math.isfinite(tin) and math.isfinite(tout) else math.nan
                    ),
                    "transport_flow_term_est_lbmolps": flow_term,
                    "transport_gradient_term_est_lbmolps": gradient_term,
                    "pre_equilibrium_rhs_lbmolps": pre_rhs,
                    "equilibrium_transfer_lbmolps": eq,
                    "final_rhs_lbmolps": final_rhs,
                    "relative_rhs_per_s": rel,
                    "transport_driver": driver,
                    "eq_cancellation_coverage": (
                        -eq / pre_rhs
                        if math.isfinite(eq) and math.isfinite(pre_rhs) and abs(pre_rhs) > 1.0e-300
                        else math.nan
                    ),
                }
            )

        dominant_driver = max(stage_driver_counts, key=stage_driver_counts.get) if stage_driver_counts else "unknown"
        stage_records.append(
            {
                "stage_1based": st,
                "MV_lbmol": mv,
                "V_in_lbmolph_est": v_in,
                "V_out_lbmolph": v_out,
                "V_in_minus_out_lbmolph_est": (
                    v_in - v_out if math.isfinite(v_in) and math.isfinite(v_out) else math.nan
                ),
                "max_abs_relative_rhs_per_s": max_rel,
                "max_abs_final_rhs_lbmolps": max_final,
                "dominant_transport_driver": dominant_driver,
                "eq_component_transfer_guard_scale_tray": _finite_float(
                    row.get("eq_component_transfer_guard_scale_tray")
                ),
                "eq_component_transfer_guard_limit_lbmolps_tray": _finite_float(
                    row.get("eq_component_transfer_guard_limit_lbmolps_tray")
                ),
            }
        )

    records.sort(
        key=lambda r: abs(float(r["relative_rhs_per_s"]))
        if math.isfinite(float(r.get("relative_rhs_per_s", math.nan)))
        else -math.inf,
        reverse=True,
    )
    stage_records.sort(key=lambda r: abs(float(r["max_abs_relative_rhs_per_s"])), reverse=True)
    interior_records = [r for r in records if min(stages) < int(r["stage_1based"]) < max(stages)]

    finite_rel = [abs(float(r["relative_rhs_per_s"])) for r in records if math.isfinite(float(r["relative_rhs_per_s"]))]
    finite_final = [abs(float(r["final_rhs_lbmolps"])) for r in records if math.isfinite(float(r["final_rhs_lbmolps"]))]
    driver_counts: Dict[str, int] = {}
    for row in records:
        driver = str(row.get("transport_driver", "unknown"))
        driver_counts[driver] = driver_counts.get(driver, 0) + 1

    return {
        "profile_csv": str(Path(profile_csv).resolve()),
        "time_s": float(time_s),
        "denom_floor_lbmol": float(floor),
        "component_labels": labels,
        "summary": {
            "n_stages": len(stages),
            "max_relative_rhs_per_s": max(finite_rel) if finite_rel else math.nan,
            "max_abs_final_rhs_lbmolps": max(finite_final) if finite_final else math.nan,
            "transport_driver_counts": driver_counts,
        },
        "top_component_transport_pulses": records[: max(int(top_n), 1)],
        "top_interior_component_transport_pulses": interior_records[: max(int(top_n), 1)],
        "top_stage_transport_pulses": stage_records[: max(int(top_n), 1)],
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
    lines.append("# Vapor Transport Pulse Audit")
    lines.append("")
    lines.append(f"Profile: `{report['profile_csv']}`")
    lines.append(f"Time: `{_fmt(report['time_s'])}` s")
    lines.append("")
    lines.append("## Summary")
    summary = report["summary"]
    lines.extend(
        _table(
            [
                {
                    "n_stages": summary["n_stages"],
                    "max_relative_rhs_per_s": summary["max_relative_rhs_per_s"],
                    "max_abs_final_rhs_lbmolps": summary["max_abs_final_rhs_lbmolps"],
                    "transport_driver_counts": summary["transport_driver_counts"],
                }
            ],
            ["n_stages", "max_relative_rhs_per_s", "max_abs_final_rhs_lbmolps", "transport_driver_counts"],
        )
    )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- `composition_gradient` means the vapor entering from the upstream stage has a different composition than the receiving stage.")
    lines.append("- `flow_magnitude` means the in/out vapor rates differ enough to explain the component pulse.")
    lines.append("- `relative_rhs_per_s` scales the live component RHS by local vapor component inventory plus the configured floor.")
    lines.append("")
    fields = [
        "stage_1based",
        "component",
        "relative_rhs_per_s",
        "final_rhs_lbmolps",
        "pre_equilibrium_rhs_lbmolps",
        "equilibrium_transfer_lbmolps",
        "eq_cancellation_coverage",
        "transport_driver",
        "V_in_lbmolph_est",
        "V_out_lbmolph",
        "y_upstream_minus_stage",
        "transport_gradient_term_est_lbmolps",
        "transport_flow_term_est_lbmolps",
    ]
    lines.append("## Top Component Transport Pulses")
    lines.extend(_table(report["top_component_transport_pulses"], fields))
    lines.append("")
    lines.append("## Top Interior Component Transport Pulses")
    lines.extend(_table(report["top_interior_component_transport_pulses"], fields))
    lines.append("")
    lines.append("## Top Stage Transport Pulses")
    lines.extend(
        _table(
            report["top_stage_transport_pulses"],
            [
                "stage_1based",
                "max_abs_relative_rhs_per_s",
                "max_abs_final_rhs_lbmolps",
                "dominant_transport_driver",
                "V_in_lbmolph_est",
                "V_out_lbmolph",
                "V_in_minus_out_lbmolph_est",
                "eq_component_transfer_guard_scale_tray",
                "eq_component_transfer_guard_limit_lbmolps_tray",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit vapor material-transport pulses from profile CSV diagnostics.")
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
    print(f"Audited {report['summary']['n_stages']} stages at t={_fmt(report['time_s'])} s")
    print(f"max relative RHS = {_fmt(report['summary']['max_relative_rhs_per_s'])} 1/s")
    print(f"driver counts = {report['summary']['transport_driver_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
