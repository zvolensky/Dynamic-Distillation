#!/usr/bin/env python
"""
Run and verify the accepted Gani/ChemSep source-topology material parity case.

This is a narrow regression check. It proves that the ChemSep source-topology
material profile is still steady under the model's source-equivalent mode. It
does not validate explicit boundary vessels, vapor holdup, hydraulics, energy,
or dynamic disturbance behavior.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _as_float(row: Dict[str, Any], key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, default))
    except Exception:
        return default


def _read_last_summary(summary_path: Path) -> Dict[str, Any]:
    with summary_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"summary CSV is empty: {summary_path}")
    return rows[-1]


def _latest_summary(logs_dir: Path) -> Path:
    matches = sorted(logs_dir.glob("column_summary_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"no column_summary_*.csv found in {logs_dir}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Gani source-topology material parity.")
    parser.add_argument("--excel", default="validation_gani_1986_debutanizer_chemsep_source_topology.xlsx")
    parser.add_argument("--logs-dir", default=None)
    parser.add_argument("--n-steps", type=int, default=300)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--log-every", type=int, default=20)
    parser.add_argument("--max-score", type=float, default=1.0e-3)
    parser.add_argument("--max-rel-rate", type=float, default=1.0e-5)
    parser.add_argument("--max-temp-rate", type=float, default=1.0e-6)
    parser.add_argument("--skip-run", action="store_true", help="Only check the latest summary in --logs-dir.")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    if not excel_path.is_absolute():
        excel_path = PROJECT_ROOT / excel_path
    if not excel_path.exists():
        raise FileNotFoundError(f"workbook not found: {excel_path}")

    if args.logs_dir:
        logs_dir = Path(args.logs_dir)
        if not logs_dir.is_absolute():
            logs_dir = PROJECT_ROOT / logs_dir
    else:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        logs_dir = PROJECT_ROOT / "logs" / f"gani_source_topology_parity_check_{stamp}"
    logs_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_run:
        cmd = [
            sys.executable,
            "-m",
            "dynamic_distillation.dynamic_run_scaffold_v1",
            "--excel",
            str(excel_path),
            "--thermo",
            "clapeyron",
            "--clapeyron-model",
            "PR",
            "--runtime-mode",
            "parity",
            "--disable-boundary-states",
            "--disable-vapor-states",
            "--no-equilibrium",
            "--vapor-holdup-relaxation-sec",
            "0",
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
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)

    summary_path = _latest_summary(logs_dir)
    last = _read_last_summary(summary_path)

    steady_flag = _as_float(last, "steady_state_flag", 0.0)
    score = _as_float(last, "steady_state_score")
    rel_rate = _as_float(last, "ss_max_rel_state_rate_per_s")
    temp_rate = abs(_as_float(last, "ss_max_temp_rate_F_per_s", 0.0))

    ok = (
        steady_flag >= 0.5
        and score <= float(args.max_score)
        and rel_rate <= float(args.max_rel_rate)
        and temp_rate <= float(args.max_temp_rate)
    )

    print(f"summary: {summary_path}")
    print(f"steady_state_flag: {steady_flag:g}")
    print(f"steady_state_score: {score:.8g}  threshold={float(args.max_score):.8g}")
    print(f"ss_max_rel_state_rate_per_s: {rel_rate:.8g}  threshold={float(args.max_rel_rate):.8g}")
    print(f"ss_max_temp_rate_F_per_s: {temp_rate:.8g}  threshold={float(args.max_temp_rate):.8g}")
    print("result: PASS" if ok else "result: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
