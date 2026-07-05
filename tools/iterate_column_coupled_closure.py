#!/usr/bin/env python
"""
Iterate the coupled column initialization closure tool with audit feedback.

This is a conservative driver around reconcile_column_vapor_closure_seed.py and
column_initialization_residual_audit.py. It keeps each candidate workbook and
audit artifact so a failed initialization attempt remains diagnosable.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _run(cmd: List[str]) -> None:
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with code {proc.returncode}: {' '.join(cmd)}")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_ledger(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Iterate coupled profile closure with residual-audit feedback.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--stem", default="coupled_closure")
    ap.add_argument("--iterations", type=int, default=6)
    ap.add_argument("--initial-blend", type=float, default=0.05)
    ap.add_argument("--min-blend", type=float, default=0.005)
    ap.add_argument("--max-blend", type=float, default=0.15)
    ap.add_argument("--improve-tol", type=float, default=1.0e-4)
    ap.add_argument("--thermo", default="clapeyron")
    ap.add_argument("--clapeyron-model", default="PR")
    ap.add_argument("--runtime-mode", default="parity")
    ap.add_argument("--no-equilibrium", action="store_true")
    ap.add_argument("--no-flash-feed-at-stage-conditions", action="store_true")
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--use-excel-vapor-holdup", action="store_true")
    args = ap.parse_args()

    out_dir = _resolve(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    current = _resolve(args.input)
    blend = min(max(float(args.initial_blend), float(args.min_blend)), float(args.max_blend))
    best_metric = float("inf")
    best_workbook = current
    rows: List[Dict[str, Any]] = []
    ledger = out_dir / "iteration_summary.csv"

    py = sys.executable
    reconcile = PROJECT_ROOT / "tools" / "reconcile_column_vapor_closure_seed.py"
    audit = PROJECT_ROOT / "tools" / "column_initialization_residual_audit.py"

    baseline_dir = out_dir / "audit_baseline"
    baseline_cmd = [
        py,
        str(audit),
        "--excel",
        str(current),
        "--thermo",
        str(args.thermo),
        "--clapeyron-model",
        str(args.clapeyron_model),
        "--runtime-mode",
        str(args.runtime_mode),
        "--vapor-holdup-relaxation-sec",
        str(float(args.vapor_holdup_relaxation_sec)),
        "--output-dir",
        str(baseline_dir),
    ]
    if bool(args.no_equilibrium):
        baseline_cmd.append("--no-equilibrium")
    if bool(args.no_flash_feed_at_stage_conditions):
        baseline_cmd.append("--no-flash-feed-at-stage-conditions")
    if bool(args.use_excel_vapor_holdup):
        baseline_cmd.append("--use-excel-vapor-holdup")
    _run(baseline_cmd)
    baseline_summary = _load_json(baseline_dir / "summary.json")
    best_metric = float(baseline_summary["max_relative_rate_per_s"])

    for it in range(1, max(int(args.iterations), 1) + 1):
        candidate = out_dir / f"{args.stem}_iter{it:02d}_blend{blend:.4f}.xlsx"
        summary_json = candidate.with_suffix(".closure_summary.json")
        audit_dir = out_dir / f"audit_iter{it:02d}"

        cmd = [
            py,
            str(reconcile),
            "--input",
            str(current),
            "--output",
            str(candidate),
            "--thermo",
            str(args.thermo),
            "--clapeyron-model",
            str(args.clapeyron_model),
            "--runtime-mode",
            str(args.runtime_mode),
            "--vapor-holdup-relaxation-sec",
            str(float(args.vapor_holdup_relaxation_sec)),
            "--method",
            "coupled",
            "--blend",
            str(blend),
            "--summary-json",
            str(summary_json),
        ]
        if bool(args.no_equilibrium):
            cmd.append("--no-equilibrium")
        if bool(args.no_flash_feed_at_stage_conditions):
            cmd.append("--no-flash-feed-at-stage-conditions")
        if bool(args.use_excel_vapor_holdup):
            cmd.append("--use-excel-vapor-holdup")
        _run(cmd)

        audit_cmd = [
            py,
            str(audit),
            "--excel",
            str(candidate),
            "--thermo",
            str(args.thermo),
            "--clapeyron-model",
            str(args.clapeyron_model),
            "--runtime-mode",
            str(args.runtime_mode),
            "--vapor-holdup-relaxation-sec",
            str(float(args.vapor_holdup_relaxation_sec)),
            "--output-dir",
            str(audit_dir),
        ]
        if bool(args.no_equilibrium):
            audit_cmd.append("--no-equilibrium")
        if bool(args.no_flash_feed_at_stage_conditions):
            audit_cmd.append("--no-flash-feed-at-stage-conditions")
        if bool(args.use_excel_vapor_holdup):
            audit_cmd.append("--use-excel-vapor-holdup")
        _run(audit_cmd)

        closure = _load_json(summary_json)
        audit_summary = _load_json(audit_dir / "summary.json")
        metric = float(audit_summary["max_relative_rate_per_s"])
        gate_pass = bool(audit_summary["gate_pass"])
        improved = metric < best_metric * (1.0 - float(args.improve_tol))
        row = {
            "iteration": it,
            "blend": blend,
            "candidate": str(candidate),
            "audit_dir": str(audit_dir),
            "gate_pass": gate_pass,
            "max_relative_rate_per_s": metric,
            "max_abs_tray_total_rate_lbmolph": float(audit_summary["max_abs_tray_total_rate_lbmolph"]),
            "max_abs_tray_V_rate_before_lbmolps": float(closure["max_abs_tray_V_rate_before_lbmolps"]),
            "max_abs_tray_V_rate_after_lbmolps": float(closure["max_abs_tray_V_rate_after_lbmolps"]),
            "max_abs_delta_x": float(closure["max_abs_delta_x"]),
            "max_abs_delta_y": float(closure["max_abs_delta_y"]),
            "accepted_as_current": improved,
        }
        rows.append(row)
        _write_ledger(ledger, rows)
        result = {
            "input": str(_resolve(args.input)),
            "best_workbook": None if best_workbook is None else str(best_workbook),
            "best_metric": best_metric,
            "iterations_run": len(rows),
            "ledger": str(ledger),
            "last_candidate": str(candidate),
            "last_metric": metric,
        }
        (out_dir / "iteration_summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if improved:
            best_metric = metric
            best_workbook = candidate
            current = candidate
            blend = min(float(args.max_blend), blend * 1.25)
        else:
            blend = max(float(args.min_blend), blend * 0.5)

        print(
            f"iter={it} metric={metric:.8g} gate={gate_pass} "
            f"improved={improved} next_blend={blend:.5g}"
        )
        if gate_pass:
            break

    _write_ledger(ledger, rows)

    result = {
        "input": str(_resolve(args.input)),
        "best_workbook": None if best_workbook is None else str(best_workbook),
        "best_metric": best_metric,
        "iterations_run": len(rows),
        "ledger": str(ledger),
    }
    (out_dir / "iteration_summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Best workbook: {best_workbook}")
    print(f"Best metric: {best_metric:.8g}")
    print(f"Ledger: {ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
