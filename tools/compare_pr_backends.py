"""
Compare PR-style live thermo backends on the same runner case.

This script is intentionally small and operational: it launches the normal
dynamic runner once per backend, then summarizes elapsed wall time, final
summary-row metrics, startup timing, and thermo call counters.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_csv_last_row(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return dict(rows[-1]) if rows else {}


def _to_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if out != out:
        return None
    return out


def _counter_totals(counters: dict[str, Any]) -> dict[str, float]:
    totals = {
        "flash_requests": 0.0,
        "backend_flash_equivalents": 0.0,
        "batch_flash_requests": 0.0,
        "batch_flash_rows": 0.0,
        "cp_requests": 0.0,
        "wall_sec": 0.0,
        "cp_wall_sec": 0.0,
        "liquid_density_requests": 0.0,
        "liquid_density_wall_sec": 0.0,
    }
    for metrics in counters.values():
        if not isinstance(metrics, dict):
            continue
        for key in totals:
            val = _to_float(metrics.get(key))
            if val is not None:
                totals[key] += val
    return totals


def _backend_args(backend: str) -> list[str]:
    key = str(backend).strip().lower()
    if key in {"dwsim-pr", "dwsim"}:
        return ["--thermo", "dwsim", "--dwsim-property-package", "pr"]
    if key in {"clapeyron-pr", "clapeyron"}:
        return ["--thermo", "clapeyron", "--clapeyron-model", "PR"]
    if key in {"clapeyron-pr-dwsim", "clapeyron-dwsim-pr", "clapeyron-aligned-pr"}:
        return [
            "--thermo",
            "clapeyron",
            "--clapeyron-model",
            "PR",
            "--clapeyron-pr-parameter-source",
            "dwsim",
        ]
    raise ValueError(f"Unsupported backend {backend!r}; use dwsim-pr, clapeyron-pr, or clapeyron-pr-dwsim")


def _run_case(
    *,
    backend: str,
    args: argparse.Namespace,
    repo_root: Path,
    report_dir: Path,
) -> dict[str, Any]:
    label = str(backend).strip().lower()
    logs_dir = report_dir / f"logs_{label.replace('-', '_')}"
    logs_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "dynamic_distillation.dynamic_run_scaffold_v1",
        "--excel",
        str(args.excel),
        "--runtime-mode",
        str(args.runtime_mode),
        *_backend_args(label),
        "--n-steps",
        str(int(args.n_steps)),
        "--dt",
        str(float(args.dt)),
        "--log-every",
        str(int(args.log_every)),
        "--logs-dir",
        str(logs_dir),
        "--allow-repeat-command",
    ]
    if bool(args.fast_startup):
        cmd.append("--fast-startup")
    if bool(args.include_energy):
        cmd.append("--include-energy")

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(repo_root), text=True, capture_output=True, check=False)
    elapsed = time.perf_counter() - t0

    metadata_files = sorted(logs_dir.glob("run_metadata_*.json"), key=lambda p: p.stat().st_mtime)
    metadata_path = metadata_files[-1] if metadata_files else None
    metadata: dict[str, Any] = {}
    if metadata_path is not None:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    run_id = str(metadata.get("run_id") or (metadata_path.stem.replace("run_metadata_", "") if metadata_path else ""))

    summary_path = None
    if run_id:
        candidate = logs_dir / f"column_summary_{run_id}.csv"
        if candidate.exists():
            summary_path = candidate
    if summary_path is None:
        summaries = sorted(logs_dir.glob("column_summary_*.csv"), key=lambda p: p.stat().st_mtime)
        summary_path = summaries[-1] if summaries else None
    summary_last = _read_csv_last_row(summary_path) if summary_path else {}

    counters = metadata.get("thermo_call_counters", {})
    counter_totals = _counter_totals(counters if isinstance(counters, dict) else {})
    startup_timing = metadata.get("startup_timing_sec", {})

    result = {
        "backend": label,
        "returncode": int(proc.returncode),
        "elapsed_wall_sec_measured": elapsed,
        "run_id": run_id,
        "logs_dir": str(logs_dir),
        "metadata_path": str(metadata_path) if metadata_path else "",
        "summary_path": str(summary_path) if summary_path else "",
        "command": subprocess.list2cmdline(cmd),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-40:]),
        "startup_timing_sec": startup_timing if isinstance(startup_timing, dict) else {},
        "thermo_counter_totals": counter_totals,
        "final": {},
    }
    for key in (
        "time_s",
        "wall_elapsed_s",
        "P_top_drum_psia",
        "P_top_ctrl_pv_psia",
        "xD_comp_pv",
        "xD_comp_sp",
        "xB_comp_pv",
        "xB_comp_sp",
        "Reflux_cmd_lbmolph",
        "D_lbmolph",
        "B_lbmolph",
        "steady_state_score",
        "ss_max_rel_state_rate_per_s",
        "ss_max_mv_rate_per_s",
    ):
        if key in summary_last:
            result["final"][key] = _to_float(summary_last.get(key))
    return result


def _write_reports(report_dir: Path, results: list[dict[str, Any]]) -> tuple[Path, Path]:
    json_path = report_dir / "pr_backend_comparison_report.json"
    csv_path = report_dir / "pr_backend_comparison_summary.csv"
    payload = {"results": results}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    fields = [
        "backend",
        "returncode",
        "run_id",
        "elapsed_wall_sec_measured",
        "final.time_s",
        "final.wall_elapsed_s",
        "final.P_top_drum_psia",
        "final.xD_comp_pv",
        "final.steady_state_score",
        "thermo.flash_requests",
        "thermo.backend_flash_equivalents",
        "thermo.batch_flash_rows",
        "thermo.wall_sec",
        "thermo.cp_wall_sec",
        "metadata_path",
        "summary_path",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for result in results:
            final = result.get("final", {})
            thermo = result.get("thermo_counter_totals", {})
            row = {
                "backend": result.get("backend"),
                "returncode": result.get("returncode"),
                "run_id": result.get("run_id"),
                "elapsed_wall_sec_measured": result.get("elapsed_wall_sec_measured"),
                "final.time_s": final.get("time_s"),
                "final.wall_elapsed_s": final.get("wall_elapsed_s"),
                "final.P_top_drum_psia": final.get("P_top_drum_psia"),
                "final.xD_comp_pv": final.get("xD_comp_pv"),
                "final.steady_state_score": final.get("steady_state_score"),
                "thermo.flash_requests": thermo.get("flash_requests"),
                "thermo.backend_flash_equivalents": thermo.get("backend_flash_equivalents"),
                "thermo.batch_flash_rows": thermo.get("batch_flash_rows"),
                "thermo.wall_sec": thermo.get("wall_sec"),
                "thermo.cp_wall_sec": thermo.get("cp_wall_sec"),
                "metadata_path": result.get("metadata_path"),
                "summary_path": result.get("summary_path"),
            }
            writer.writerow(row)
    return json_path, csv_path


def main(argv: list[str] | None = None) -> int:
    repo_root = _repo_root()
    parser = argparse.ArgumentParser(description="Compare DWSIM PR and Clapeyron PR on the same runner case.")
    parser.add_argument("--excel", default="distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx")
    parser.add_argument("--runtime-mode", default="parity", choices=["parity", "hydraulic", "calibration", "legacy"])
    parser.add_argument("--backends", nargs="+", default=["dwsim-pr", "clapeyron-pr"])
    parser.add_argument("--n-steps", type=int, default=1)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--log-every", type=int, default=1)
    parser.add_argument("--fast-startup", action="store_true")
    parser.add_argument("--include-energy", action="store_true")
    parser.add_argument("--report-dir", default="")
    args = parser.parse_args(argv)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    report_dir = Path(args.report_dir) if args.report_dir else repo_root / "logs" / f"pr_backend_comparison_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for backend in args.backends:
        print(f"[compare] running backend={backend}", flush=True)
        result = _run_case(backend=backend, args=args, repo_root=repo_root, report_dir=report_dir)
        results.append(result)
        print(
            f"[compare] backend={backend} returncode={result['returncode']} "
            f"elapsed={float(result['elapsed_wall_sec_measured']):.2f}s "
            f"run_id={result.get('run_id')}",
            flush=True,
        )
    json_path, csv_path = _write_reports(report_dir, results)
    print(f"[compare] wrote {json_path}")
    print(f"[compare] wrote {csv_path}")
    return 0 if all(int(r.get("returncode", 1)) == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
