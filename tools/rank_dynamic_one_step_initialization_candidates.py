#!/usr/bin/env python
"""
Rank completed one-step initialization candidate runs.

This is the bounded-search harness for the dynamic one-step objective. It does
not launch new simulations; it scores existing run directories and reports the
best candidate under the same objective used for future optimizer loops.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from score_dynamic_one_step_initialization import score_run
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as tools.*
    from tools.score_dynamic_one_step_initialization import score_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _latest_matching(run_dir: Path, pattern: str) -> Path:
    matches = sorted(run_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"{run_dir} has no {pattern}")
    return matches[0].resolve()


def _candidate_paths(run_dir: str | Path) -> tuple[Path, Path]:
    root = _resolve(run_dir)
    if root.is_file():
        raise ValueError("candidate must be a run directory, not a file")
    return _latest_matching(root, "column_summary_*.csv"), _latest_matching(root, "column_profile_*.csv")


def _finite(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def rank_candidates(
    candidate_dirs: List[str | Path],
    *,
    baseline_dir: Optional[str | Path] = None,
    max_time_s: Optional[float] = 0.2,
    profile_final_time_s: Optional[float] = 0.2,
    equilibrium_tau_sec: float = 0.5,
    refs: Optional[Dict[str, float]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    for raw_dir in candidate_dirs:
        label = Path(str(raw_dir)).name
        try:
            summary_csv, profile_csv = _candidate_paths(raw_dir)
            score = score_run(
                summary_csv,
                profile_csv,
                max_time_s=max_time_s,
                profile_final_time_s=profile_final_time_s,
                equilibrium_tau_sec=equilibrium_tau_sec,
                refs=refs,
                weights=weights,
            )
            records.append(
                {
                    "label": label,
                    "run_dir": str(_resolve(raw_dir)),
                    "summary_csv": str(summary_csv),
                    "profile_csv": str(profile_csv),
                    "objective": _finite(score["objective"]),
                    "metrics": score["metrics"],
                    "terms": score["terms"],
                    "coverage": score["coverage"],
                    "scorable": True,
                    "error": "",
                }
            )
        except Exception as exc:
            records.append(
                {
                    "label": label,
                    "run_dir": str(_resolve(raw_dir)),
                    "summary_csv": "",
                    "profile_csv": "",
                    "objective": math.inf,
                    "metrics": {},
                    "terms": {},
                    "coverage": {},
                    "scorable": False,
                    "error": str(exc),
                }
            )
    records.sort(key=lambda r: (_finite(r.get("objective")) if bool(r.get("scorable")) else math.inf, r["label"]))

    baseline_record = None
    if baseline_dir is not None:
        baseline_resolved = str(_resolve(baseline_dir))
        for rec in records:
            if rec["run_dir"] == baseline_resolved:
                baseline_record = rec
                break
        if baseline_record is None:
            summary_csv, profile_csv = _candidate_paths(baseline_dir)
            score = score_run(
                summary_csv,
                profile_csv,
                max_time_s=max_time_s,
                profile_final_time_s=profile_final_time_s,
                equilibrium_tau_sec=equilibrium_tau_sec,
                refs=refs,
                weights=weights,
            )
            baseline_record = {
                "label": Path(str(baseline_dir)).name,
                "run_dir": baseline_resolved,
                "summary_csv": str(summary_csv),
                "profile_csv": str(profile_csv),
                "objective": _finite(score["objective"]),
                "metrics": score["metrics"],
                "terms": score["terms"],
                "coverage": score["coverage"],
            }

    scorable_records = [r for r in records if bool(r.get("scorable")) and math.isfinite(_finite(r.get("objective")))]
    best = scorable_records[0] if scorable_records else None
    improvement_vs_baseline = math.nan
    best_beats_baseline = None
    if best is not None and baseline_record is not None:
        b = _finite(baseline_record.get("objective"))
        x = _finite(best.get("objective"))
        if math.isfinite(b) and math.isfinite(x):
            improvement_vs_baseline = b - x
            best_beats_baseline = bool(x < b)

    return {
        "max_time_s": max_time_s,
        "profile_final_time_s": profile_final_time_s,
        "equilibrium_tau_sec": equilibrium_tau_sec,
        "baseline": baseline_record,
        "best": best,
        "best_beats_baseline": best_beats_baseline,
        "objective_improvement_vs_baseline": improvement_vs_baseline,
        "candidates": records,
        "n_scorable": len(scorable_records),
        "n_unscorable": len(records) - len(scorable_records),
    }


def _parse_key_float(raw: str) -> tuple[str, float]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected KEY=VALUE")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("key cannot be empty")
    try:
        val = float(value)
    except Exception as exc:
        raise argparse.ArgumentTypeError("value must be finite") from exc
    if not math.isfinite(val):
        raise argparse.ArgumentTypeError("value must be finite")
    return key, val


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
    lines: List[str] = ["# Dynamic One-Step Candidate Ranking", ""]
    best = report.get("best")
    if best:
        lines.append(f"Best: `{best['label']}` objective `{_fmt(best['objective'])}`")
    if report.get("baseline"):
        lines.append(
            "Baseline: `{}` objective `{}`".format(
                report["baseline"]["label"], _fmt(report["baseline"]["objective"])
            )
        )
        lines.append(f"Best beats baseline: `{report.get('best_beats_baseline')}`")
        lines.append(f"Objective improvement vs baseline: `{_fmt(report.get('objective_improvement_vs_baseline'))}`")
    lines.append("")
    rows = []
    for rec in report["candidates"]:
        metrics = rec["metrics"]
        coverage = rec["coverage"]
        rows.append(
            {
                "label": rec["label"],
                "scorable": rec.get("scorable"),
                "objective": rec["objective"],
                "dynamic_score": metrics.get("dynamic_score"),
                "rel_rate_per_s": metrics.get("rel_rate_per_s"),
                "vapor_rhs_lbmolps": metrics.get("vapor_rhs_lbmolps"),
                "overcoverage": metrics.get("overcoverage"),
                "y_drift": metrics.get("y_drift"),
                "median_coverage": coverage.get("median_cancellation_coverage"),
                "error": rec.get("error", ""),
            }
        )
    lines.extend(
        _table(
            rows,
            [
                "label",
                "scorable",
                "objective",
                "dynamic_score",
                "rel_rate_per_s",
                "vapor_rhs_lbmolps",
                "overcoverage",
                "y_drift",
                "median_coverage",
                "error",
            ],
        )
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank completed one-step initialization candidate runs.")
    ap.add_argument("--candidate-dir", action="append", required=True, help="Run directory with column_summary/profile CSVs.")
    ap.add_argument("--baseline-dir", default=None, help="Optional baseline run directory for improvement check.")
    ap.add_argument("--max-time-s", type=float, default=0.2)
    ap.add_argument("--profile-final-time-s", type=float, default=0.2)
    ap.add_argument("--equilibrium-tau-sec", type=float, default=0.5)
    ap.add_argument("--ref", action="append", type=_parse_key_float, default=[])
    ap.add_argument("--weight", action="append", type=_parse_key_float, default=[])
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args()

    report = rank_candidates(
        args.candidate_dir,
        baseline_dir=args.baseline_dir,
        max_time_s=args.max_time_s,
        profile_final_time_s=args.profile_final_time_s,
        equilibrium_tau_sec=float(args.equilibrium_tau_sec),
        refs=dict(args.ref or []),
        weights=dict(args.weight or []),
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
