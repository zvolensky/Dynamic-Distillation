"""
Analyze paired DWSIM PR and Clapeyron PR comparison outputs.

The runner wrapper measures timing and captures raw logs. This script compares
the final summary row and final profile rows between two backends in an existing
comparison directory, so expensive cases can be inspected without rerunning.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return out


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_last_row(path: Path) -> dict[str, str]:
    rows = _read_csv(path)
    return dict(rows[-1]) if rows else {}


def _load_report(report_dir: Path) -> dict[str, dict[str, Any]]:
    path = report_dir / "pr_backend_comparison_report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for result in payload.get("results", []):
        if isinstance(result, dict):
            backend = str(result.get("backend", "")).strip().lower()
            if backend:
                out[backend] = result
    return out


def _profile_path(result: dict[str, Any]) -> Path | None:
    run_id = str(result.get("run_id") or "")
    logs_dir = Path(str(result.get("logs_dir") or ""))
    if run_id and logs_dir:
        candidate = logs_dir / f"column_profile_{run_id}.csv"
        if candidate.exists():
            return candidate
    matches = sorted(logs_dir.glob("column_profile_*.csv"), key=lambda p: p.stat().st_mtime)
    return matches[-1] if matches else None


def _final_profile_rows(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows = _read_csv(path)
    times = [_to_float(row.get("time_s")) for row in rows]
    finite_times = [value for value in times if value is not None]
    if not finite_times:
        return {}
    final_time = max(finite_times)
    final_rows = []
    for row in rows:
        time_s = _to_float(row.get("time_s"))
        if time_s is not None and abs(time_s - final_time) <= 1.0e-9:
            final_rows.append(row)
    return {
        (str(row.get("stage", "")), str(row.get("node_type", ""))): row
        for row in final_rows
    }


def _compare_summary(
    left: dict[str, str],
    right: dict[str, str],
    keys: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in keys:
        lval = _to_float(left.get(key))
        rval = _to_float(right.get(key))
        if lval is None or rval is None:
            continue
        delta = rval - lval
        rows.append(
            {
                "metric": key,
                "dwsim_pr": lval,
                "clapeyron_pr": rval,
                "delta_clapeyron_minus_dwsim": delta,
                "abs_delta": abs(delta),
                "relative_delta": delta / lval if abs(lval) > 1.0e-12 else "",
            }
        )
    return rows


def _compare_profiles(
    left_rows: dict[tuple[str, str], dict[str, str]],
    right_rows: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, Any]]:
    common_nodes = sorted(set(left_rows) & set(right_rows), key=lambda x: (int(x[0]) if x[0].isdigit() else 9999, x[1]))
    if not common_nodes:
        return []

    common_columns = set.intersection(*(set(left_rows[node]) & set(right_rows[node]) for node in common_nodes))
    ignore = {"wall_clock_iso", "wall_elapsed_s", "time_s", "stage", "node_type"}
    numeric_columns = []
    for col in sorted(common_columns - ignore):
        has_numeric_pair = False
        for node in common_nodes:
            if _to_float(left_rows[node].get(col)) is not None and _to_float(right_rows[node].get(col)) is not None:
                has_numeric_pair = True
                break
        if has_numeric_pair:
            numeric_columns.append(col)

    rows: list[dict[str, Any]] = []
    for col in numeric_columns:
        max_abs = -1.0
        max_row: dict[str, Any] | None = None
        sum_abs = 0.0
        count = 0
        for node in common_nodes:
            lval = _to_float(left_rows[node].get(col))
            rval = _to_float(right_rows[node].get(col))
            if lval is None or rval is None:
                continue
            delta = rval - lval
            abs_delta = abs(delta)
            sum_abs += abs_delta
            count += 1
            if abs_delta > max_abs:
                max_abs = abs_delta
                max_row = {
                    "metric": col,
                    "stage": node[0],
                    "node_type": node[1],
                    "dwsim_pr": lval,
                    "clapeyron_pr": rval,
                    "delta_clapeyron_minus_dwsim": delta,
                    "abs_delta": abs_delta,
                    "relative_delta": delta / lval if abs(lval) > 1.0e-12 else "",
                    "mean_abs_delta": "",
                    "n_pairs": count,
                }
        if max_row is not None:
            max_row["mean_abs_delta"] = sum_abs / count if count else ""
            max_row["n_pairs"] = count
            rows.append(max_row)
    return sorted(rows, key=lambda row: float(row["abs_delta"]), reverse=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "metric",
        "stage",
        "node_type",
        "dwsim_pr",
        "clapeyron_pr",
        "delta_clapeyron_minus_dwsim",
        "abs_delta",
        "relative_delta",
        "mean_abs_delta",
        "n_pairs",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a PR backend comparison directory.")
    parser.add_argument("report_dir")
    parser.add_argument("--left", default="dwsim-pr")
    parser.add_argument("--right", default="clapeyron-pr")
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args(argv)

    report_dir = Path(args.report_dir)
    results = _load_report(report_dir)
    left = results[str(args.left).lower()]
    right = results[str(args.right).lower()]

    left_summary_path = Path(str(left.get("summary_path") or ""))
    right_summary_path = Path(str(right.get("summary_path") or ""))
    summary_keys = [
        "time_s",
        "P_top_drum_psia",
        "P_top_ctrl_pv_psia",
        "xD_comp_pv",
        "xB_comp_pv",
        "Reflux_cmd_lbmolph",
        "D_lbmolph",
        "B_lbmolph",
        "steady_state_score",
        "ss_max_rel_state_rate_per_s",
        "ss_max_mv_rate_per_s",
    ]
    summary_rows = _compare_summary(
        _read_last_row(left_summary_path),
        _read_last_row(right_summary_path),
        summary_keys,
    )

    left_profile_path = _profile_path(left)
    right_profile_path = _profile_path(right)
    profile_rows: list[dict[str, Any]] = []
    if left_profile_path and right_profile_path:
        profile_rows = _compare_profiles(
            _final_profile_rows(left_profile_path),
            _final_profile_rows(right_profile_path),
        )

    summary_csv = report_dir / "pr_backend_summary_deltas.csv"
    profile_csv = report_dir / "pr_backend_profile_deltas.csv"
    _write_csv(summary_csv, summary_rows)
    _write_csv(profile_csv, profile_rows)

    payload = {
        "left": str(args.left).lower(),
        "right": str(args.right).lower(),
        "summary_deltas": summary_rows,
        "profile_delta_top": profile_rows[: int(args.top)],
        "summary_delta_csv": str(summary_csv),
        "profile_delta_csv": str(profile_csv),
    }
    json_path = report_dir / "pr_backend_analysis_report.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[analyze] wrote {json_path}")
    print(f"[analyze] wrote {summary_csv}")
    print(f"[analyze] wrote {profile_csv}")
    for row in summary_rows:
        print(
            "[summary] "
            f"{row['metric']}: dwsim={row['dwsim_pr']:.8g} "
            f"clapeyron={row['clapeyron_pr']:.8g} "
            f"delta={row['delta_clapeyron_minus_dwsim']:.8g}"
        )
    print("[profile] largest final-row deltas:")
    for row in profile_rows[: int(args.top)]:
        print(
            f"  {row['metric']} stage={row['stage']} {row['node_type']}: "
            f"dwsim={row['dwsim_pr']:.8g} clapeyron={row['clapeyron_pr']:.8g} "
            f"delta={row['delta_clapeyron_minus_dwsim']:.8g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
