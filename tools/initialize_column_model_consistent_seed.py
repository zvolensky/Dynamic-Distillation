#!/usr/bin/env python
"""
Run a repeatable model-consistent column initialization workflow.

This tool orchestrates the residual audit and bounded initialization optimizer
as one named pipeline. It treats an imported steady-state workbook as a guess,
generates audited candidate seeds, and copies the selected candidate to the
requested output path.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _load_summary(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite_float(value: Any, default: float = math.inf) -> float:
    try:
        v = float(value)
    except Exception:
        return default
    return v if math.isfinite(v) else default


def _candidate_sort_key(summary: Dict[str, Any], *, selection: str) -> tuple[float, ...]:
    gate_penalty = 0.0 if bool(summary.get("gate_pass", False)) else 1.0
    max_rel = _finite_float(summary.get("max_relative_rate_per_s"))
    max_total = _finite_float(summary.get("max_abs_tray_total_rate_lbmolph"))
    max_abs = _finite_float(summary.get("max_abs_rate_per_s"))
    if selection == "balanced":
        return (gate_penalty, max_rel + (max_total / 100000.0), max_rel, max_total, max_abs)
    if selection == "tray-total":
        return (gate_penalty, max_total, max_rel, max_abs)
    return (gate_penalty, max_rel, max_total, max_abs)


def _choose_best(candidates: List[Dict[str, Any]], *, selection: str) -> Dict[str, Any]:
    if not candidates:
        raise ValueError("No initialization candidates were produced.")
    return min(candidates, key=lambda row: _candidate_sort_key(row["audit_summary"], selection=selection))


def _run(cmd: Sequence[str], *, dry_run: bool) -> None:
    print(" ".join(str(part) for part in cmd), flush=True)
    if dry_run:
        return
    subprocess.run(list(cmd), cwd=str(PROJECT_ROOT), check=True)


def _common_audit_cmd(args: argparse.Namespace, *, excel: Path, output_dir: Path) -> List[str]:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "column_initialization_residual_audit.py"),
        "--excel",
        str(excel),
        "--thermo",
        str(args.thermo),
        "--runtime-mode",
        str(args.runtime_mode),
        "--condenser-duty-mode",
        str(args.condenser_duty_mode),
        "--vapor-holdup-relaxation-sec",
        str(float(args.vapor_holdup_relaxation_sec)),
        "--output-dir",
        str(output_dir),
    ]
    if bool(args.include_energy):
        cmd.append("--include-energy")
    if bool(args.use_excel_vapor_holdup):
        cmd.append("--use-excel-vapor-holdup")
    if bool(args.no_equilibrium):
        cmd.append("--no-equilibrium")
    if bool(args.no_flash_feed_at_stage_conditions):
        cmd.append("--no-flash-feed-at-stage-conditions")
    return cmd


def _optimizer_base_cmd(args: argparse.Namespace, *, input_path: Path, output_path: Path, audit_dir: Path) -> List[str]:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "optimize_column_initialization_residual.py"),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--stages",
        str(args.stages),
        "--residual-stages",
        str(args.residual_stages),
        "--thermo",
        str(args.thermo),
        "--runtime-mode",
        str(args.runtime_mode),
        "--condenser-duty-mode",
        str(args.condenser_duty_mode),
        "--max-nfev",
        str(int(args.max_nfev)),
        "--max-wall-sec",
        str(float(args.max_wall_sec)),
        "--max-logit-delta",
        str(float(args.max_logit_delta)),
        "--max-flow-log-delta",
        str(float(args.max_flow_log_delta)),
        "--max-energy-rel-delta",
        str(float(args.max_energy_rel_delta)),
        "--profile-penalty",
        str(float(args.profile_penalty)),
        "--profile-continuity-penalty",
        str(float(args.profile_continuity_penalty)),
        "--flow-penalty",
        str(float(args.flow_penalty)),
        "--flow-continuity-penalty",
        str(float(args.flow_continuity_penalty)),
        "--energy-penalty",
        str(float(args.energy_penalty)),
        "--energy-continuity-penalty",
        str(float(args.energy_continuity_penalty)),
        "--tray-total-penalty",
        str(float(args.tray_total_penalty)),
        "--tray-v-residual-weight",
        str(float(args.tray_v_residual_weight)),
        "--tray-l-residual-weight",
        str(float(args.tray_l_residual_weight)),
        "--top-l-residual-weight",
        str(float(args.top_l_residual_weight)),
        "--bottom-l-residual-weight",
        str(float(args.bottom_l_residual_weight)),
        "--bottom-boundary-balance-weight",
        str(float(args.bottom_boundary_balance_weight)),
        "--bottom-boundary-total-weight",
        str(float(args.bottom_boundary_total_weight)),
        "--bottom-vapor-interface-weight",
        str(float(args.bottom_vapor_interface_weight)),
        "--audit-output-dir",
        str(audit_dir),
    ]
    if bool(args.include_energy):
        cmd.append("--include-energy")
    if bool(args.use_excel_vapor_holdup):
        cmd.append("--use-excel-vapor-holdup")
    if bool(args.no_equilibrium):
        cmd.append("--no-equilibrium")
    if bool(args.no_flash_feed_at_stage_conditions):
        cmd.append("--no-flash-feed-at-stage-conditions")
    return cmd


def _candidate_cmd(
    args: argparse.Namespace,
    *,
    name: str,
    input_path: Path,
    output_path: Path,
    audit_dir: Path,
) -> List[str]:
    cmd = _optimizer_base_cmd(args, input_path=input_path, output_path=output_path, audit_dir=audit_dir)
    if name == "coupled-vle-topL":
        cmd.extend(
            [
                "--residual-state-blocks",
                "tray_V,tray_L,top_L",
                "--residual-energy-blocks",
                "tray_EV_BTU,tray_EL_BTU",
                "--vary-vapor",
                "--vary-vapor-flow",
                "--vary-liquid",
                "--vary-tray-energy",
                "--vary-top-liquid",
            ]
        )
        return cmd
    if name == "coupled-flows-boundary":
        cmd.extend(
            [
                "--residual-state-blocks",
                "tray_V,tray_L,top_L,bottom_L",
                "--residual-energy-blocks",
                "tray_EV_BTU,tray_EL_BTU",
                "--vary-vapor",
                "--vary-vapor-flow",
                "--vary-liquid",
                "--vary-liquid-flow",
                "--vary-tray-energy",
                "--vary-top-liquid",
                "--vary-bottom-liquid",
                "--chemsep-product-specs",
                "--reflux-ratio",
                str(float(args.reflux_ratio)),
                "--vary-boilup",
                "--boundary-penalty",
                str(float(args.boundary_penalty)),
            ]
        )
        return cmd
    if name == "bottom-boundary-balanced":
        cmd.extend(
            [
                "--residual-state-blocks",
                "tray_V,tray_L,top_L,bottom_L",
                "--residual-energy-blocks",
                "tray_EV_BTU,tray_EL_BTU",
                "--vary-vapor",
                "--vary-vapor-flow",
                "--vary-liquid",
                "--vary-liquid-flow",
                "--vary-tray-energy",
                "--vary-top-liquid",
                "--vary-bottom-liquid",
                "--chemsep-product-specs",
                "--reflux-ratio",
                str(float(args.reflux_ratio)),
                "--vary-boilup",
                "--vary-bottoms",
                "--boundary-penalty",
                str(float(args.boundary_penalty)),
            ]
        )
        return cmd
    raise ValueError(f"Unknown candidate: {name}")


def _write_markdown(path: Path, summary: Dict[str, Any]) -> None:
    lines = [
        "# Model-Consistent Initialization Summary",
        "",
        f"- Input: `{summary['input']}`",
        f"- Selected output: `{summary['selected_output']}`",
        f"- Selection mode: `{summary['selection']}`",
        f"- Gate pass: `{summary['selected']['audit_summary'].get('gate_pass')}`",
        f"- Worst relative rate: `{_finite_float(summary['selected']['audit_summary'].get('max_relative_rate_per_s')):.8g} 1/s`",
        f"- Max tray total residual: `{_finite_float(summary['selected']['audit_summary'].get('max_abs_tray_total_rate_lbmolph')):.8g} lbmol/h`",
        "",
        "## Candidates",
        "",
        "| Candidate | Gate | Max rel 1/s | Max tray total lbmol/h | Workbook |",
        "|---|---:|---:|---:|---|",
    ]
    for row in summary["candidates"]:
        audit = row["audit_summary"]
        lines.append(
            f"| `{row['name']}` | `{audit.get('gate_pass')}` | "
            f"{_finite_float(audit.get('max_relative_rate_per_s')):.8g} | "
            f"{_finite_float(audit.get('max_abs_tray_total_rate_lbmolph')):.8g} | "
            f"`{row['workbook']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the model-consistent column initialization workflow.")
    ap.add_argument("--input", required=True, help="Imported/guessed seed workbook.")
    ap.add_argument("--output", required=True, help="Final selected initialized workbook.")
    ap.add_argument("--work-dir", default=None, help="Directory for candidate workbooks and audits.")
    ap.add_argument("--stages", default="interior")
    ap.add_argument("--residual-stages", default=None)
    ap.add_argument("--candidates", default="coupled-vle-topL,coupled-flows-boundary")
    ap.add_argument("--selection", choices=["max-rate", "balanced", "tray-total"], default="max-rate")
    ap.add_argument("--thermo", default="table")
    ap.add_argument("--runtime-mode", default="hydraulic")
    ap.add_argument("--condenser-duty-mode", default="total-condense")
    ap.add_argument("--include-energy", action="store_true", default=True)
    ap.add_argument("--no-energy", dest="include_energy", action="store_false")
    ap.add_argument("--use-excel-vapor-holdup", action="store_true", default=True)
    ap.add_argument("--no-equilibrium", action="store_true", default=True)
    ap.add_argument("--enable-equilibrium", dest="no_equilibrium", action="store_false")
    ap.add_argument("--no-flash-feed-at-stage-conditions", action="store_true", default=True)
    ap.add_argument("--flash-feed-at-stage-conditions", dest="no_flash_feed_at_stage_conditions", action="store_false")
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=0.0)
    ap.add_argument("--max-nfev", type=int, default=20)
    ap.add_argument("--max-wall-sec", type=float, default=0.0)
    ap.add_argument("--max-logit-delta", type=float, default=0.25)
    ap.add_argument("--max-flow-log-delta", type=float, default=0.12)
    ap.add_argument("--max-energy-rel-delta", type=float, default=0.15)
    ap.add_argument("--profile-penalty", type=float, default=0.02)
    ap.add_argument("--profile-continuity-penalty", type=float, default=0.05)
    ap.add_argument("--flow-penalty", type=float, default=0.02)
    ap.add_argument("--flow-continuity-penalty", type=float, default=0.05)
    ap.add_argument("--boundary-penalty", type=float, default=0.02)
    ap.add_argument("--energy-penalty", type=float, default=0.02)
    ap.add_argument("--energy-continuity-penalty", type=float, default=0.02)
    ap.add_argument("--tray-total-penalty", type=float, default=0.25)
    ap.add_argument("--tray-v-residual-weight", type=float, default=1.0)
    ap.add_argument("--tray-l-residual-weight", type=float, default=1.0)
    ap.add_argument("--top-l-residual-weight", type=float, default=1.0)
    ap.add_argument("--bottom-l-residual-weight", type=float, default=1.0)
    ap.add_argument("--bottom-boundary-balance-weight", type=float, default=0.0)
    ap.add_argument("--bottom-boundary-total-weight", type=float, default=0.0)
    ap.add_argument("--bottom-vapor-interface-weight", type=float, default=0.0)
    ap.add_argument("--reflux-ratio", type=float, default=2.5)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.residual_stages is None:
        args.residual_stages = args.stages

    input_path = _resolve(args.input)
    output_path = _resolve(args.output)
    if not input_path.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_path}")
    work_dir = _resolve(args.work_dir) if args.work_dir else (
        PROJECT_ROOT / "logs" / "model_consistent_initialization" / _tag()
    )
    work_dir.mkdir(parents=True, exist_ok=True)

    baseline_audit_dir = work_dir / "baseline_audit"
    _run(_common_audit_cmd(args, excel=input_path, output_dir=baseline_audit_dir), dry_run=bool(args.dry_run))

    candidate_names = [name.strip() for name in str(args.candidates).split(",") if name.strip()]
    candidates: List[Dict[str, Any]] = []
    for name in candidate_names:
        candidate_workbook = work_dir / f"{name}.xlsx"
        candidate_audit_dir = work_dir / f"{name}_audit"
        cmd = _candidate_cmd(
            args,
            name=name,
            input_path=input_path,
            output_path=candidate_workbook,
            audit_dir=candidate_audit_dir,
        )
        _run(cmd, dry_run=bool(args.dry_run))
        if bool(args.dry_run):
            continue
        audit_summary = _load_summary(candidate_audit_dir / "summary.json")
        optimizer_summary = _load_summary(candidate_workbook.with_suffix(".optimizer_summary.json"))
        candidates.append(
            {
                "name": name,
                "workbook": str(candidate_workbook),
                "audit_dir": str(candidate_audit_dir),
                "audit_summary": audit_summary,
                "optimizer_summary": optimizer_summary,
            }
        )

    if bool(args.dry_run):
        return 0

    baseline_summary = _load_summary(baseline_audit_dir / "summary.json")
    selected = _choose_best(candidates, selection=str(args.selection))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_resolve(selected["workbook"]), output_path)

    summary = {
        "input": str(input_path),
        "selected_output": str(output_path),
        "work_dir": str(work_dir),
        "selection": str(args.selection),
        "baseline_audit": baseline_summary,
        "selected": selected,
        "candidates": candidates,
    }
    summary_json = output_path.with_suffix(".initializer_summary.json")
    summary_md = output_path.with_suffix(".initializer_summary.md")
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(summary_md, summary)

    audit = selected["audit_summary"]
    print("Model-consistent initialization workflow complete")
    print(f"Selected: {selected['name']}")
    print(f"Output: {output_path}")
    print(f"Gate pass: {audit.get('gate_pass')}")
    print(f"Max relative state rate: {_finite_float(audit.get('max_relative_rate_per_s')):.8g} 1/s")
    print(f"Max tray total residual: {_finite_float(audit.get('max_abs_tray_total_rate_lbmolph')):.8g} lbmol/h")
    print(f"Summary: {summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
