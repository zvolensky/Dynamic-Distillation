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
import shlex
import shutil
import subprocess
import sys
import time
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


def _safe_case_name(value: str | None, fallback: str) -> str:
    raw = str(value or fallback or "case").strip()
    out = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in raw)
    out = "_".join(part for part in out.split("_") if part)
    return out or "case"


def _git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PROJECT_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unavailable"
    if result.returncode != 0:
        return "unavailable"
    return str(result.stdout or "").strip() or "unavailable"


def _powershell_quote_arg(value: Any) -> str:
    text = str(value)
    if text == "":
        return "''"
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._/:\\")
    if all(ch in safe_chars for ch in text):
        return text
    return "'" + text.replace("'", "''") + "'"


def _powershell_command_text(cmd: Sequence[Any]) -> str:
    return " ".join(_powershell_quote_arg(part) for part in cmd)


class InitializerExecutionLog:
    def __init__(
        self,
        path: Path,
        *,
        input_path: Path,
        output_path: Path,
        case_name: str,
        args: argparse.Namespace,
    ) -> None:
        self.path = path
        self.case_name = case_name
        self.started = time.perf_counter()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self._write("INITIALIZER EXECUTION LOG")
        self._write(f"start_iso={_dt.datetime.now().isoformat(timespec='seconds')}")
        self._write(f"case_name={case_name}")
        self._write(f"input={input_path}")
        self._write(f"output={output_path}")
        self._write(f"git_commit={_git_commit_hash()}")
        self._write(
            "runtime_config="
            + json.dumps(
                {
                    "thermo": args.thermo,
                    "runtime_mode": args.runtime_mode,
                    "condenser_duty_mode": args.condenser_duty_mode,
                    "include_energy": bool(args.include_energy),
                    "use_excel_vapor_holdup": bool(args.use_excel_vapor_holdup),
                    "no_equilibrium": bool(args.no_equilibrium),
                    "no_flash_feed_at_stage_conditions": bool(args.no_flash_feed_at_stage_conditions),
                    "selection": args.selection,
                    "candidates": args.candidates,
                },
                sort_keys=True,
            )
        )
        self._write("")

    def _write(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(text + "\n")

    def milestone(self, name: str, status: str, **metrics: Any) -> None:
        now = _dt.datetime.now().isoformat(timespec="seconds")
        elapsed = time.perf_counter() - self.started
        parts = [
            f"[{now} | elapsed={elapsed:.3f}s | {status} | milestone={name}",
        ]
        for key, value in metrics.items():
            if value is None:
                continue
            parts.append(f"{key}={value}")
        self._write(" | ".join(parts) + "]")

    def command(self, label: str, cmd: Sequence[str]) -> None:
        self.milestone(label, "COMMAND", command=_powershell_command_text(cmd))

    def close(self, status: str, **metrics: Any) -> None:
        self.milestone("final_decision", status, **metrics)
        self._write(f"end_iso={_dt.datetime.now().isoformat(timespec='seconds')}")


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


def _run(
    cmd: Sequence[str],
    *,
    dry_run: bool,
    log: InitializerExecutionLog | None = None,
    label: str = "command",
    allow_failure: bool = False,
) -> int:
    print(_powershell_command_text(cmd), flush=True)
    if log is not None:
        log.command(label, cmd)
    if dry_run:
        return 0
    result = subprocess.run(list(cmd), cwd=str(PROJECT_ROOT), check=False)
    if result.returncode != 0:
        if log is not None:
            log.milestone(label, "FAIL", returncode=result.returncode)
        if not bool(allow_failure):
            raise subprocess.CalledProcessError(result.returncode, list(cmd))
        return int(result.returncode)
    if log is not None:
        log.milestone(label, "OK", returncode=result.returncode)
    return int(result.returncode)


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


def _dynamic_run_cmd(
    args: argparse.Namespace,
    *,
    excel: Path,
    logs_dir: Path,
    init_checkpoint: Path | None = None,
) -> List[str]:
    cmd = [
        sys.executable,
        "-m",
        "dynamic_distillation.dynamic_run_scaffold_v1",
        "--excel",
        str(excel),
        "--runtime-mode",
        str(args.runtime_mode),
        "--thermo",
        str(args.thermo),
        "--condenser-duty-mode",
        str(args.condenser_duty_mode),
        "--n-steps",
        str(int(args.dynamic_gate_n_steps)),
        "--dt",
        str(float(args.dynamic_gate_dt)),
        "--log-every",
        str(int(args.dynamic_gate_log_every)),
        "--logs-dir",
        str(logs_dir),
        "--allow-repeat-command",
    ]
    if init_checkpoint is not None:
        cmd.extend(["--init-from-checkpoint", str(init_checkpoint)])
    if bool(args.include_energy):
        cmd.append("--include-energy")
    if bool(args.use_excel_vapor_holdup):
        cmd.append("--use-excel-vapor-holdup")
    if bool(args.no_equilibrium):
        cmd.append("--no-equilibrium")
    if bool(args.no_flash_feed_at_stage_conditions):
        cmd.append("--no-flash-feed-at-stage-conditions")
    extra_args = list(args.dynamic_run_extra_arg or [])
    if str(getattr(args, "dynamic_run_extra_args", "") or "").strip():
        extra_args.extend(shlex.split(str(args.dynamic_run_extra_args)))
    for extra in extra_args:
        cmd.append(str(extra))
    return cmd


def _latest_summary_csv(logs_dir: Path) -> Path:
    matches = sorted(logs_dir.glob("column_summary_*.csv"), key=lambda p: p.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"No column_summary_*.csv found in {logs_dir}")
    return matches[-1]


def _latest_run_metadata_json(logs_dir: Path) -> Path:
    matches = sorted(logs_dir.rglob("run_metadata_*.json"), key=lambda p: p.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"No run_metadata_*.json found in {logs_dir}")
    return matches[-1]


def _dynamic_run_artifacts(logs_dir: Path) -> Dict[str, Any]:
    artifacts: Dict[str, Any] = {
        "logs_dir": str(logs_dir),
        "run_metadata_json": "",
        "summary_csv": "",
        "profile_csv": "",
        "restart_workbook": "",
        "native_checkpoint": "",
        "native_checkpoint_exists": False,
        "restart_workbook_exists": False,
    }
    try:
        metadata_path = _latest_run_metadata_json(logs_dir)
    except FileNotFoundError:
        return artifacts
    artifacts["run_metadata_json"] = str(metadata_path)
    try:
        doc = _load_summary(metadata_path)
    except Exception as exc:
        artifacts["metadata_error"] = str(exc)
        return artifacts
    for key in ("summary_csv", "profile_csv", "restart_workbook", "native_checkpoint"):
        value = str(doc.get(key, "") or "")
        artifacts[key] = value
        if key in ("restart_workbook", "native_checkpoint"):
            artifacts[f"{key}_exists"] = bool(value and Path(value).exists())
    artifacts["run_id"] = str(doc.get("run_id", "") or "")
    artifacts["status"] = str(doc.get("status", "") or "")
    artifacts["final_time_s"] = doc.get("final_time_s")
    return artifacts


def _dynamic_gate_eval_cmd(
    args: argparse.Namespace,
    *,
    baseline_summary: Path,
    candidate_summary: Path,
    candidate_label: str,
    output_json: Path,
    output_md: Path,
) -> List[str]:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "evaluate_initialization_dynamic_gate.py"),
        "--baseline-summary",
        str(baseline_summary),
        "--candidate-summary",
        str(candidate_summary),
        "--candidate-label",
        str(candidate_label),
        "--max-final-score-ratio",
        str(float(args.dynamic_gate_max_final_score_ratio)),
        "--max-peak-score-ratio",
        str(float(args.dynamic_gate_max_peak_score_ratio)),
        "--max-final-rel-rate-ratio",
        str(float(args.dynamic_gate_max_final_rel_rate_ratio)),
        "--max-peak-rel-rate-ratio",
        str(float(args.dynamic_gate_max_peak_rel_rate_ratio)),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]
    if args.dynamic_gate_max_time_s is not None:
        cmd.extend(["--max-time-s", str(float(args.dynamic_gate_max_time_s))])
    if args.dynamic_gate_max_final_temp_rate_ratio is not None:
        cmd.extend(["--max-final-temp-rate-ratio", str(float(args.dynamic_gate_max_final_temp_rate_ratio))])
    for raw in args.dynamic_gate_endpoint_drift_limit or []:
        cmd.extend(["--endpoint-drift-limit", str(raw)])
    for raw in args.dynamic_gate_summary_ratio_limit or []:
        cmd.extend(["--summary-ratio-limit", str(raw)])
    return cmd


def _checkpoint_reload_gate_eval_cmd(
    args: argparse.Namespace,
    *,
    baseline_summary: Path,
    reload_summary: Path,
    output_json: Path,
    output_md: Path,
) -> List[str]:
    limit = float(args.checkpoint_reload_gate_max_ratio)
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "evaluate_initialization_dynamic_gate.py"),
        "--baseline-summary",
        str(baseline_summary),
        "--candidate-summary",
        str(reload_summary),
        "--candidate-label",
        "checkpoint_reload",
        "--max-final-score-ratio",
        str(limit),
        "--max-peak-score-ratio",
        str(limit),
        "--max-final-rel-rate-ratio",
        str(limit),
        "--max-peak-rel-rate-ratio",
        str(limit),
        "--max-final-temp-rate-ratio",
        str(limit),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]
    if args.checkpoint_reload_gate_max_time_s is not None:
        cmd.extend(["--max-time-s", str(float(args.checkpoint_reload_gate_max_time_s))])
    return cmd


def _first_failed_dynamic_check(dynamic_gate_report: Dict[str, Any]) -> Dict[str, Any] | None:
    for candidate in dynamic_gate_report.get("candidates") or []:
        for check in candidate.get("checks") or []:
            if not bool(check.get("passed", False)):
                return check
    return None


def _clean_usable_assessment(
    *,
    selected_audit: Dict[str, Any],
    dynamic_gate_report: Dict[str, Any],
    dynamic_gate_enabled: bool,
) -> Dict[str, Any]:
    residual_gate_pass = bool(selected_audit.get("gate_pass", False))
    dynamic_gate_pass = bool(dynamic_gate_report.get("passed", False)) if dynamic_gate_enabled else None
    assessment: Dict[str, Any] = {
        "usable": False,
        "basis": "residual_and_dynamic_gate" if dynamic_gate_enabled else "residual_gate_only",
        "reason": "",
        "residual_gate_pass": residual_gate_pass,
        "dynamic_gate_enabled": bool(dynamic_gate_enabled),
        "dynamic_gate_pass": dynamic_gate_pass,
    }
    if not residual_gate_pass:
        assessment["reason"] = "residual gate failed"
        return assessment
    if not dynamic_gate_enabled:
        assessment.update(
            {
                "usable": True,
                "reason": "residual gate passed; dynamic gate was not run",
                "dynamic_gate_required_for_final_acceptance": True,
            }
        )
        return assessment
    if dynamic_gate_pass:
        assessment.update({"usable": True, "reason": "residual and dynamic gates passed"})
        return assessment
    failed = _first_failed_dynamic_check(dynamic_gate_report)
    if failed is not None:
        name = failed.get("name") or failed.get("metric") or "unnamed_check"
        assessment["reason"] = f"dynamic gate failed: {name}"
        assessment["failed_dynamic_check"] = failed
    else:
        assessment["reason"] = "dynamic gate failed"
    return assessment


def _accepted_artifact_summary(
    *,
    clean_assessment: Dict[str, Any],
    selected_workbook: Path,
    output_workbook: Path,
    dynamic_artifacts: Dict[str, Any],
) -> Dict[str, Any]:
    native_checkpoint = str(dynamic_artifacts.get("native_checkpoint", "") or "")
    native_checkpoint_exists = bool(dynamic_artifacts.get("native_checkpoint_exists", False))
    workbook_exists = bool(output_workbook.exists())
    if bool(clean_assessment.get("usable", False)) and native_checkpoint_exists:
        return {
            "status": "accepted",
            "preferred_kind": "native_checkpoint",
            "preferred_path": native_checkpoint,
            "reason": "clean usable assessment passed and native checkpoint exists",
            "native_checkpoint": native_checkpoint,
            "native_checkpoint_exists": native_checkpoint_exists,
            "workbook": str(output_workbook),
            "workbook_exists": workbook_exists,
            "selected_workbook": str(selected_workbook),
        }
    if bool(clean_assessment.get("usable", False)):
        return {
            "status": "provisional",
            "preferred_kind": "workbook",
            "preferred_path": str(output_workbook),
            "reason": "clean usable assessment passed but no native checkpoint was found",
            "native_checkpoint": native_checkpoint,
            "native_checkpoint_exists": native_checkpoint_exists,
            "workbook": str(output_workbook),
            "workbook_exists": workbook_exists,
            "selected_workbook": str(selected_workbook),
        }
    return {
        "status": "diagnostic_only",
        "preferred_kind": "workbook",
        "preferred_path": str(output_workbook),
        "reason": str(clean_assessment.get("reason", "") or "clean usable assessment failed"),
        "native_checkpoint": native_checkpoint,
        "native_checkpoint_exists": native_checkpoint_exists,
        "workbook": str(output_workbook),
        "workbook_exists": workbook_exists,
        "selected_workbook": str(selected_workbook),
    }


def _accepted_artifact_run_command(
    args: argparse.Namespace,
    *,
    output_workbook: Path,
    accepted_artifact: Dict[str, Any],
    logs_dir: Path,
) -> List[str]:
    checkpoint = str(accepted_artifact.get("native_checkpoint", "") or "")
    checkpoint_path = Path(checkpoint) if checkpoint else None
    use_checkpoint = (
        str(accepted_artifact.get("preferred_kind", "")) == "native_checkpoint"
        and bool(accepted_artifact.get("native_checkpoint_exists", False))
        and checkpoint_path is not None
    )
    return _dynamic_run_cmd(
        args,
        excel=output_workbook,
        logs_dir=logs_dir,
        init_checkpoint=checkpoint_path if use_checkpoint else None,
    )


def _final_status(
    *,
    dynamic_gate_enabled: bool,
    clean_assessment: Dict[str, Any],
    residual_gate_pass: bool,
    checkpoint_reload_gate_enabled: bool,
    checkpoint_reload_gate_report: Dict[str, Any],
) -> str:
    if dynamic_gate_enabled:
        status = "ACCEPTED_DYNAMIC_GATE" if bool(clean_assessment.get("usable", False)) else "REJECTED_DYNAMIC_GATE"
    else:
        status = "ACCEPTED_RESIDUAL_GATE" if bool(residual_gate_pass) else "REJECTED_RESIDUAL_GATE"
    if bool(checkpoint_reload_gate_enabled) and checkpoint_reload_gate_report.get("passed") is False:
        status = "REJECTED_CHECKPOINT_RELOAD_GATE"
    return status


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
        "--vflow-energy-closure-weight",
        str(float(args.vflow_energy_closure_weight)),
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
        f"- Execution log: `{summary.get('execution_log', '')}`",
        f"- Selection mode: `{summary['selection']}`",
        f"- Gate pass: `{summary['selected']['audit_summary'].get('gate_pass')}`",
        f"- Clean usable assessment: `usable={summary.get('clean_usable_assessment', {}).get('usable')}; "
        f"basis={summary.get('clean_usable_assessment', {}).get('basis')}; "
        f"reason={summary.get('clean_usable_assessment', {}).get('reason')}`",
        f"- Accepted artifact: `status={summary.get('accepted_artifact', {}).get('status')}; "
        f"kind={summary.get('accepted_artifact', {}).get('preferred_kind')}; "
        f"path={summary.get('accepted_artifact', {}).get('preferred_path')}`",
        f"- Checkpoint reload gate: `enabled={summary.get('checkpoint_reload_gate', {}).get('enabled')}; "
        f"passed={summary.get('checkpoint_reload_gate', {}).get('passed')}; "
        f"reason={summary.get('checkpoint_reload_gate', {}).get('reason')}`",
        f"- Worst relative rate: `{_finite_float(summary['selected']['audit_summary'].get('max_relative_rate_per_s')):.8g} 1/s`",
        f"- Max tray total residual: `{_finite_float(summary['selected']['audit_summary'].get('max_abs_tray_total_rate_lbmolph')):.8g} lbmol/h`",
        "",
        "## Restart Command",
        "",
        "```powershell",
        str(summary.get("accepted_artifact_run_command_text", "")),
        "```",
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
    ap.add_argument("--case-name", default=None, help="Case name used for the initializer execution log.")
    ap.add_argument("--log-dir", default=None, help="Directory for initializer_<case>_<timestamp>.log; defaults to work-dir.")
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
    ap.add_argument("--vflow-energy-closure-weight", type=float, default=0.0)
    ap.add_argument("--reflux-ratio", type=float, default=2.5)
    ap.add_argument("--enable-dynamic-gate", action="store_true", help="Run baseline/candidate dynamic smoke tests and evaluate the dynamic gate.")
    ap.add_argument("--dynamic-gate-baseline-summary", default=None, help="Existing baseline column_summary CSV. If provided, skip the baseline dynamic run.")
    ap.add_argument("--dynamic-gate-n-steps", type=int, default=300)
    ap.add_argument("--dynamic-gate-dt", type=float, default=0.2)
    ap.add_argument("--dynamic-gate-log-every", type=int, default=25)
    ap.add_argument("--dynamic-gate-max-time-s", type=float, default=None)
    ap.add_argument("--dynamic-gate-max-final-score-ratio", type=float, default=1.0)
    ap.add_argument("--dynamic-gate-max-peak-score-ratio", type=float, default=1.0)
    ap.add_argument("--dynamic-gate-max-final-rel-rate-ratio", type=float, default=1.0)
    ap.add_argument("--dynamic-gate-max-peak-rel-rate-ratio", type=float, default=1.0)
    ap.add_argument("--dynamic-gate-max-final-temp-rate-ratio", type=float, default=None)
    ap.add_argument("--dynamic-gate-endpoint-drift-limit", action="append", default=[])
    ap.add_argument("--dynamic-gate-summary-ratio-limit", action="append", default=[])
    ap.add_argument(
        "--enable-checkpoint-reload-gate",
        action="store_true",
        help="After an accepted dynamic gate with a native checkpoint, reload that checkpoint and run a parity smoke gate.",
    )
    ap.add_argument("--checkpoint-reload-gate-max-ratio", type=float, default=1.1)
    ap.add_argument("--checkpoint-reload-gate-max-time-s", type=float, default=None)
    ap.add_argument(
        "--dynamic-run-extra-arg",
        action="append",
        default=[],
        help="Extra argument passed through to each dynamic_run_scaffold invocation. Use --dynamic-run-extra-arg=--flag for flag-like values.",
    )
    ap.add_argument(
        "--dynamic-run-extra-args",
        default="",
        help="Quoted string of extra arguments passed to each dynamic_run_scaffold invocation.",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.residual_stages is None:
        args.residual_stages = args.stages

    input_path = _resolve(args.input)
    output_path = _resolve(args.output)
    case_name = _safe_case_name(args.case_name, input_path.stem)
    if not input_path.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_path}")
    work_dir = _resolve(args.work_dir) if args.work_dir else (
        PROJECT_ROOT / "logs" / "model_consistent_initialization" / _tag()
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    log_dir = _resolve(args.log_dir) if args.log_dir else work_dir
    execution_log = InitializerExecutionLog(
        log_dir / f"initializer_{case_name}_{_tag()}.log",
        input_path=input_path,
        output_path=output_path,
        case_name=case_name,
        args=args,
    )
    execution_log.milestone(
        "seed_ingestion_validation",
        "OK",
        input_exists=True,
        input_size_bytes=input_path.stat().st_size,
    )
    execution_log.milestone(
        "state_vector_construction",
        "PENDING_EXTERNAL_TOOL",
        note="state is constructed by residual audit and optimizer tools",
    )

    baseline_audit_dir = work_dir / "baseline_audit"
    _run(
        _common_audit_cmd(args, excel=input_path, output_dir=baseline_audit_dir),
        dry_run=bool(args.dry_run),
        log=execution_log,
        label="initial_residual_audit_command",
    )
    if not bool(args.dry_run):
        baseline_summary = _load_summary(baseline_audit_dir / "summary.json")
        execution_log.milestone(
            "initial_residual_evaluation",
            "OK",
            gate_pass=baseline_summary.get("gate_pass"),
            max_relative_rate_per_s=_finite_float(baseline_summary.get("max_relative_rate_per_s")),
            max_abs_tray_total_rate_lbmolph=_finite_float(baseline_summary.get("max_abs_tray_total_rate_lbmolph")),
            worst_block=baseline_summary.get("worst_block"),
            worst_stage=baseline_summary.get("worst_stage_1based"),
            worst_component=baseline_summary.get("worst_component_name"),
        )

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
        _run(cmd, dry_run=bool(args.dry_run), log=execution_log, label=f"candidate_{name}_solve_command")
        if bool(args.dry_run):
            continue
        audit_summary = _load_summary(candidate_audit_dir / "summary.json")
        optimizer_summary = _load_summary(candidate_workbook.with_suffix(".optimizer_summary.json"))
        execution_log.milestone(
            "residual_based_solve_iterations",
            "OK",
            candidate=name,
            least_squares_success=optimizer_summary.get("least_squares_success"),
            nfev=optimizer_summary.get("nfev"),
            objective_initial=optimizer_summary.get("objective_initial"),
            objective_final=optimizer_summary.get("objective_final"),
        )
        execution_log.milestone(
            "physical_constraint_enforcement",
            "OK",
            candidate=name,
            max_logit_delta=args.max_logit_delta,
            max_flow_log_delta=args.max_flow_log_delta,
            max_energy_rel_delta=args.max_energy_rel_delta,
        )
        execution_log.milestone(
            "candidate_reaudit",
            "OK",
            candidate=name,
            gate_pass=audit_summary.get("gate_pass"),
            max_relative_rate_per_s=_finite_float(audit_summary.get("max_relative_rate_per_s")),
            max_abs_tray_total_rate_lbmolph=_finite_float(audit_summary.get("max_abs_tray_total_rate_lbmolph")),
            worst_block=audit_summary.get("worst_block"),
            worst_stage=audit_summary.get("worst_stage_1based"),
            worst_component=audit_summary.get("worst_component_name"),
        )
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
        execution_log.close("DRY_RUN", log_path=execution_log.path)
        return 0

    selected = _choose_best(candidates, selection=str(args.selection))
    selected_audit = selected["audit_summary"]
    baseline_rel = _finite_float(baseline_summary.get("max_relative_rate_per_s"))
    selected_rel = _finite_float(selected_audit.get("max_relative_rate_per_s"))
    baseline_total = _finite_float(baseline_summary.get("max_abs_tray_total_rate_lbmolph"))
    selected_total = _finite_float(selected_audit.get("max_abs_tray_total_rate_lbmolph"))
    execution_log.milestone(
        "coupling_diagnostics_summary",
        "OK",
        selected=selected["name"],
        max_relative_rate_per_s=selected_rel,
        max_abs_tray_total_rate_lbmolph=selected_total,
        note="coupling detail available in residual audit and optimizer summaries",
    )
    execution_log.milestone(
        "baseline_vs_candidate_comparison",
        "OK",
        selected=selected["name"],
        baseline_max_relative_rate_per_s=baseline_rel,
        selected_max_relative_rate_per_s=selected_rel,
        baseline_max_abs_tray_total_rate_lbmolph=baseline_total,
        selected_max_abs_tray_total_rate_lbmolph=selected_total,
        relative_rate_delta=selected_rel - baseline_rel,
        tray_total_delta=selected_total - baseline_total,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_resolve(selected["workbook"]), output_path)
    execution_log.milestone(
        "serialization",
        "OK",
        selected_workbook=selected["workbook"],
        output_workbook=output_path,
        output_size_bytes=output_path.stat().st_size,
    )

    dynamic_gate_report: Dict[str, Any] = {
        "enabled": bool(args.enable_dynamic_gate),
        "passed": None,
        "reason": "disabled",
    }
    candidate_dynamic_artifacts: Dict[str, Any] = {}
    candidate_dynamic_summary_path: Path | None = None
    if bool(args.enable_dynamic_gate):
        dynamic_dir = work_dir / "dynamic_gate"
        dynamic_dir.mkdir(parents=True, exist_ok=True)
        if args.dynamic_gate_baseline_summary:
            baseline_dynamic_summary = _resolve(args.dynamic_gate_baseline_summary)
            execution_log.milestone(
                "dynamic_baseline_smoke",
                "REUSED",
                summary_csv=baseline_dynamic_summary,
            )
        else:
            baseline_dynamic_dir = dynamic_dir / "baseline"
            _run(
                _dynamic_run_cmd(args, excel=input_path, logs_dir=baseline_dynamic_dir),
                dry_run=False,
                log=execution_log,
                label="dynamic_baseline_smoke_command",
            )
            baseline_dynamic_summary = _latest_summary_csv(baseline_dynamic_dir)
            execution_log.milestone("dynamic_baseline_smoke", "OK", summary_csv=baseline_dynamic_summary)

        candidate_dynamic_dir = dynamic_dir / str(selected["name"])
        _run(
            _dynamic_run_cmd(args, excel=output_path, logs_dir=candidate_dynamic_dir),
            dry_run=False,
            log=execution_log,
            label="dynamic_candidate_smoke_command",
        )
        candidate_dynamic_summary = _latest_summary_csv(candidate_dynamic_dir)
        candidate_dynamic_summary_path = candidate_dynamic_summary
        candidate_dynamic_artifacts = _dynamic_run_artifacts(candidate_dynamic_dir)
        execution_log.milestone(
            "dynamic_candidate_smoke",
            "OK",
            candidate=selected["name"],
            summary_csv=candidate_dynamic_summary,
            run_metadata_json=candidate_dynamic_artifacts.get("run_metadata_json"),
            native_checkpoint=candidate_dynamic_artifacts.get("native_checkpoint"),
            native_checkpoint_exists=candidate_dynamic_artifacts.get("native_checkpoint_exists"),
        )

        dynamic_gate_json = dynamic_dir / "dynamic_gate_report.json"
        dynamic_gate_md = dynamic_dir / "dynamic_gate_report.md"
        _run(
            _dynamic_gate_eval_cmd(
                args,
                baseline_summary=baseline_dynamic_summary,
                candidate_summary=candidate_dynamic_summary,
                candidate_label=str(selected["name"]),
                output_json=dynamic_gate_json,
                output_md=dynamic_gate_md,
            ),
            dry_run=False,
            log=execution_log,
            label="dynamic_gate_evaluation_command",
            allow_failure=True,
        )
        dynamic_gate_report = _load_summary(dynamic_gate_json)
        dynamic_gate_report.update(
            {
                "enabled": True,
                "baseline_summary_csv": str(baseline_dynamic_summary),
                "candidate_summary_csv": str(candidate_dynamic_summary),
                "report_json": str(dynamic_gate_json),
                "report_md": str(dynamic_gate_md),
                "candidate_run_artifacts": candidate_dynamic_artifacts,
            }
        )
        first_candidate = (dynamic_gate_report.get("candidates") or [{}])[0]
        execution_log.milestone(
            "dynamic_acceptance_gate",
            "PASS" if bool(dynamic_gate_report.get("passed", False)) else "FAIL",
            report_json=dynamic_gate_json,
            report_md=dynamic_gate_md,
            candidate=selected["name"],
            final_score=(first_candidate.get("summary") or {}).get("final_score"),
            peak_score=(first_candidate.get("summary") or {}).get("peak_score"),
            final_rel_rate_per_s=(first_candidate.get("summary") or {}).get("final_rel_rate_per_s"),
            peak_rel_rate_per_s=(first_candidate.get("summary") or {}).get("peak_rel_rate_per_s"),
        )
    else:
        execution_log.milestone("dynamic_acceptance_gate", "SKIPPED", reason="enable_dynamic_gate_false")

    clean_assessment = _clean_usable_assessment(
        selected_audit=selected_audit,
        dynamic_gate_report=dynamic_gate_report,
        dynamic_gate_enabled=bool(args.enable_dynamic_gate),
    )
    execution_log.milestone(
        "clean_usable_assessment",
        "USABLE" if bool(clean_assessment.get("usable", False)) else "NOT_USABLE",
        usable=clean_assessment.get("usable"),
        basis=clean_assessment.get("basis"),
        reason=clean_assessment.get("reason"),
        residual_gate_pass=clean_assessment.get("residual_gate_pass"),
        dynamic_gate_enabled=clean_assessment.get("dynamic_gate_enabled"),
        dynamic_gate_pass=clean_assessment.get("dynamic_gate_pass"),
    )
    accepted_artifact = _accepted_artifact_summary(
        clean_assessment=clean_assessment,
        selected_workbook=_resolve(selected["workbook"]),
        output_workbook=output_path,
        dynamic_artifacts=candidate_dynamic_artifacts,
    )
    execution_log.milestone(
        "accepted_artifact_selection",
        str(accepted_artifact.get("status", "")).upper(),
        preferred_kind=accepted_artifact.get("preferred_kind"),
        preferred_path=accepted_artifact.get("preferred_path"),
        native_checkpoint_exists=accepted_artifact.get("native_checkpoint_exists"),
        reason=accepted_artifact.get("reason"),
    )
    checkpoint_reload_gate_report: Dict[str, Any] = {
        "enabled": bool(args.enable_checkpoint_reload_gate),
        "passed": None,
        "reason": "disabled",
    }
    if bool(args.enable_checkpoint_reload_gate):
        checkpoint_path_raw = str(accepted_artifact.get("native_checkpoint", "") or "")
        accepted_native_checkpoint = (
            str(accepted_artifact.get("status", "")) == "accepted"
            and str(accepted_artifact.get("preferred_kind", "")) == "native_checkpoint"
            and bool(accepted_artifact.get("native_checkpoint_exists", False))
        )
        if not bool(clean_assessment.get("usable", False)):
            checkpoint_reload_gate_report.update(
                {"passed": None, "reason": "skipped because candidate is not clean usable"}
            )
            execution_log.milestone(
                "checkpoint_reload_gate",
                "SKIPPED",
                reason=checkpoint_reload_gate_report.get("reason"),
            )
        elif not accepted_native_checkpoint:
            checkpoint_reload_gate_report.update(
                {"passed": False, "reason": "native checkpoint not available"}
            )
            execution_log.milestone(
                "checkpoint_reload_gate",
                "FAIL",
                reason=checkpoint_reload_gate_report.get("reason"),
            )
        elif candidate_dynamic_summary_path is None:
            checkpoint_reload_gate_report.update(
                {"passed": False, "reason": "candidate dynamic summary not available"}
            )
            execution_log.milestone(
                "checkpoint_reload_gate",
                "FAIL",
                reason=checkpoint_reload_gate_report.get("reason"),
            )
        else:
            checkpoint_reload_dir = work_dir / "dynamic_gate" / "checkpoint_reload"
            checkpoint_reload_checkpoint = _resolve(checkpoint_path_raw)
            _run(
                _dynamic_run_cmd(
                    args,
                    excel=output_path,
                    logs_dir=checkpoint_reload_dir,
                    init_checkpoint=checkpoint_reload_checkpoint,
                ),
                dry_run=False,
                log=execution_log,
                label="checkpoint_reload_smoke_command",
            )
            checkpoint_reload_summary = _latest_summary_csv(checkpoint_reload_dir)
            checkpoint_reload_artifacts = _dynamic_run_artifacts(checkpoint_reload_dir)
            checkpoint_reload_json = checkpoint_reload_dir / "checkpoint_reload_gate_report.json"
            checkpoint_reload_md = checkpoint_reload_dir / "checkpoint_reload_gate_report.md"
            _run(
                _checkpoint_reload_gate_eval_cmd(
                    args,
                    baseline_summary=candidate_dynamic_summary_path,
                    reload_summary=checkpoint_reload_summary,
                    output_json=checkpoint_reload_json,
                    output_md=checkpoint_reload_md,
                ),
                dry_run=False,
                log=execution_log,
                label="checkpoint_reload_gate_evaluation_command",
                allow_failure=True,
            )
            checkpoint_reload_gate_report = _load_summary(checkpoint_reload_json)
            checkpoint_reload_gate_report.update(
                {
                    "enabled": True,
                    "candidate_summary_csv": str(candidate_dynamic_summary_path),
                    "reload_summary_csv": str(checkpoint_reload_summary),
                    "reload_run_artifacts": checkpoint_reload_artifacts,
                    "report_json": str(checkpoint_reload_json),
                    "report_md": str(checkpoint_reload_md),
                    "native_checkpoint": checkpoint_path_raw,
                }
            )
            execution_log.milestone(
                "checkpoint_reload_gate",
                "PASS" if bool(checkpoint_reload_gate_report.get("passed", False)) else "FAIL",
                report_json=checkpoint_reload_json,
                report_md=checkpoint_reload_md,
                native_checkpoint=checkpoint_path_raw,
                reload_summary_csv=checkpoint_reload_summary,
            )
        if checkpoint_reload_gate_report.get("passed") is False:
            accepted_artifact["status"] = "checkpoint_reload_failed"
            accepted_artifact["reason"] = str(
                checkpoint_reload_gate_report.get("reason", "") or "checkpoint reload gate failed"
            )
    accepted_artifact_run_command = _accepted_artifact_run_command(
        args,
        output_workbook=output_path,
        accepted_artifact=accepted_artifact,
        logs_dir=work_dir / "accepted_artifact_restart",
    )
    accepted_artifact_run_command_text = _powershell_command_text(accepted_artifact_run_command)

    summary = {
        "input": str(input_path),
        "selected_output": str(output_path),
        "work_dir": str(work_dir),
        "execution_log": str(execution_log.path),
        "selection": str(args.selection),
        "baseline_audit": baseline_summary,
        "selected": selected,
        "candidates": candidates,
        "dynamic_gate": dynamic_gate_report,
        "clean_usable_assessment": clean_assessment,
        "accepted_artifact": accepted_artifact,
        "checkpoint_reload_gate": checkpoint_reload_gate_report,
        "accepted_artifact_run_command": accepted_artifact_run_command,
        "accepted_artifact_run_command_text": accepted_artifact_run_command_text,
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
    print(
        "Clean usable: "
        f"{clean_assessment.get('usable')} "
        f"({clean_assessment.get('basis')}: {clean_assessment.get('reason')})"
    )
    print(
        "Accepted artifact: "
        f"{accepted_artifact.get('status')} "
        f"{accepted_artifact.get('preferred_kind')} "
        f"{accepted_artifact.get('preferred_path')}"
    )
    print(
        "Checkpoint reload gate: "
        f"{checkpoint_reload_gate_report.get('passed')} "
        f"({checkpoint_reload_gate_report.get('reason')})"
    )
    print(f"Restart command: {accepted_artifact_run_command_text}")
    print(f"Summary: {summary_md}")
    print(f"Execution log: {execution_log.path}")
    final_status = _final_status(
        dynamic_gate_enabled=bool(args.enable_dynamic_gate),
        clean_assessment=clean_assessment,
        residual_gate_pass=bool(audit.get("gate_pass", False)),
        checkpoint_reload_gate_enabled=bool(args.enable_checkpoint_reload_gate),
        checkpoint_reload_gate_report=checkpoint_reload_gate_report,
    )
    execution_log.close(
        final_status,
        selected=selected["name"],
        gate_pass=audit.get("gate_pass"),
        usable=clean_assessment.get("usable"),
        assessment_basis=clean_assessment.get("basis"),
        assessment_reason=clean_assessment.get("reason"),
        accepted_artifact_status=accepted_artifact.get("status"),
        accepted_artifact_kind=accepted_artifact.get("preferred_kind"),
        accepted_artifact_path=accepted_artifact.get("preferred_path"),
        checkpoint_reload_gate_pass=checkpoint_reload_gate_report.get("passed"),
        accepted_artifact_run_command=accepted_artifact_run_command_text,
        output=output_path,
        summary=summary_md,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
