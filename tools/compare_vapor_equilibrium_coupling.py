#!/usr/bin/env python
"""
Compare runtime vapor/equilibrium/energy coupling between two profile CSV logs.

This is a diagnostic comparison tool. It ranks where a candidate run worsens
relative to a baseline run for the same logged time, stages, and components.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import vapor_equilibrium_coupling_audit as audit


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _abs(value: Any) -> float:
    return abs(float(value)) if _finite(value) else math.nan


def _float_or_nan(value: Any) -> float:
    return float(value) if _finite(value) else math.nan


def _ratio(candidate_abs: float, baseline_abs: float) -> float:
    if not (math.isfinite(candidate_abs) and math.isfinite(baseline_abs)):
        return math.nan
    if baseline_abs <= 1.0e-12:
        return math.inf if candidate_abs > 1.0e-12 else 1.0
    return candidate_abs / baseline_abs


def _selected_rows(path: str | Path, *, time_s: Optional[float]) -> Tuple[List[Dict[str, str]], float]:
    rows = audit._stage_rows(audit._read_csv(path), time_s=time_s)
    if not rows:
        raise ValueError(f"No stage rows found in {path}")
    return rows, audit._time(rows[0])


def _by_key(records: Iterable[Dict[str, Any]], fields: Tuple[str, ...]) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
    out: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for record in records:
        key = tuple(record.get(field) for field in fields)
        if all(value is not None for value in key):
            out[key] = record
    return out


def _compare_scalar_records(
    baseline_records: Iterable[Dict[str, Any]],
    candidate_records: Iterable[Dict[str, Any]],
    *,
    key_fields: Tuple[str, ...],
    metric_field: str,
    label: str,
    top_n: int,
    context_fields: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    baseline_by_key = _by_key(baseline_records, key_fields)
    candidate_by_key = _by_key(candidate_records, key_fields)
    rows: List[Dict[str, Any]] = []
    for key, candidate in candidate_by_key.items():
        baseline = baseline_by_key.get(key)
        if baseline is None:
            continue
        baseline_abs = _abs(baseline.get(metric_field))
        candidate_abs = _abs(candidate.get(metric_field))
        if not math.isfinite(candidate_abs):
            continue
        out_row = {
            **{field: value for field, value in zip(key_fields, key)},
            "baseline": baseline.get(metric_field),
            "candidate": candidate.get(metric_field),
            "baseline_abs": baseline_abs,
            "candidate_abs": candidate_abs,
            "abs_worsening": candidate_abs - baseline_abs if math.isfinite(baseline_abs) else math.nan,
            "abs_ratio": _ratio(candidate_abs, baseline_abs),
        }
        for field in context_fields:
            out_row[f"baseline_{field}"] = baseline.get(field)
            out_row[f"candidate_{field}"] = candidate.get(field)
        rows.append(out_row)
    rows.sort(
        key=lambda r: (
            float(r["abs_worsening"]) if math.isfinite(float(r.get("abs_worsening", math.nan))) else -math.inf,
            float(r["candidate_abs"]) if math.isfinite(float(r.get("candidate_abs", math.nan))) else -math.inf,
        ),
        reverse=True,
    )
    worst = rows[0] if rows else {}
    improved = sum(1 for row in rows if math.isfinite(float(row["abs_worsening"])) and float(row["abs_worsening"]) < 0.0)
    worsened = sum(1 for row in rows if math.isfinite(float(row["abs_worsening"])) and float(row["abs_worsening"]) > 0.0)
    return {
        "label": label,
        "metric_field": metric_field,
        "n_compared": len(rows),
        "n_worsened": worsened,
        "n_improved": improved,
        "worst": worst,
        "top_worsening": rows[:top_n],
    }


def _component_vapor_closure_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        labels = audit._component_labels(row)
        if not labels:
            continue
        x = audit._arr(row, "x_", labels)
        y = audit._arr(row, "y_", labels)
        k = audit._arr(row, "K_thermo_", labels)
        valid = (x == x) & (y == y) & (k == k) & (k > 0.0)
        if not valid.any():
            continue
        valid_labels = [label for label, keep in zip(labels, valid) if bool(keep)]
        y_norm = audit._norm(y[valid])
        y_from_kx = audit._norm(k[valid] * x[valid])
        for label, y_value, target_value in zip(valid_labels, y_norm, y_from_kx):
            if not (math.isfinite(float(y_value)) and math.isfinite(float(target_value))):
                continue
            out.append(
                {
                    "time_s": audit._time(row),
                    "stage_1based": audit._stage(row),
                    "component": label,
                    "y": float(y_value),
                    "normalized_Kx": float(target_value),
                    "y_minus_normalized_Kx": float(y_value - target_value),
                }
            )
    return out


def _bubble_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    return audit._bubble_dew_records(rows)


def _unit_k_records(rows: List[Dict[str, str]], *, atol: float = 1.0e-9) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        labels = audit._component_labels(row)
        if not labels:
            continue
        k = audit._arr(row, "K_thermo_", labels)
        finite = k[np.isfinite(k)]
        if finite.size == 0:
            continue
        max_abs_k_minus_one = float(np.max(np.abs(finite - 1.0)))
        max_abs_ln_k = float(np.max(np.abs(np.log(np.maximum(finite, 1.0e-300)))))
        out.append(
            {
                "time_s": audit._time(row),
                "stage_1based": audit._stage(row),
                "thermo_unit_K_flag": 1.0 if max_abs_k_minus_one <= float(atol) else 0.0,
                "max_abs_K_thermo_minus_1": max_abs_k_minus_one,
                "max_abs_ln_K_thermo": max_abs_ln_k,
                "thermo_flash_source_code": _float_or_nan(row.get("thermo_flash_source_code")),
                "thermo_flash_failed": _float_or_nan(row.get("thermo_flash_failed")),
                "thermo_flash_phase_count": _float_or_nan(row.get("thermo_flash_phase_count")),
                "thermo_unit_K_refreshed_flag": _float_or_nan(row.get("thermo_unit_K_refreshed_flag")),
                "thermo_unit_K_retained_flag": _float_or_nan(row.get("thermo_unit_K_retained_flag")),
                "thermo_degenerate_two_phase_unit_K_flag": _float_or_nan(
                    row.get("thermo_degenerate_two_phase_unit_K_flag")
                ),
                "thermo_degenerate_two_phase_unit_K_quarantined": _float_or_nan(
                    row.get("thermo_degenerate_two_phase_unit_K_quarantined")
                ),
            }
        )
    return out


def _dominant_family(sections: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    family_map = {
        "k_state_vs_thermo": "equilibrium mismatch",
        "thermo_unit_k_packet": "thermo unit-K/fallback anomaly",
        "vapor_y_vs_normalized_kx": "equilibrium mismatch",
        "bubble_residual": "equilibrium mismatch",
        "dew_residual": "equilibrium mismatch",
        "vapor_flow_calc_used": "vapor-flow inconsistency",
        "temperature_rate": "energy inconsistency",
        "energy_residual": "energy inconsistency",
        "vflow_energy_numer": "energy/vapor-flow equation inconsistency",
        "vflow_energy_L_in_term": "energy/vapor-flow equation inconsistency",
        "vflow_energy_V_in_term": "energy/vapor-flow equation inconsistency",
        "vflow_energy_dE_target": "energy/vapor-flow equation inconsistency",
        "vflow_energy_feed_ref_term": "energy/vapor-flow equation inconsistency",
        "vflow_energy_duty_term": "energy/vapor-flow equation inconsistency",
        "pressure_from_holdup": "pressure/vapor-holdup mismatch",
    }
    scores: Dict[str, float] = {}
    evidence: Dict[str, List[str]] = {}
    for name, section in sections.items():
        worst = section.get("worst") or {}
        worsening = worst.get("abs_worsening")
        if not _finite(worsening) or float(worsening) <= 0.0:
            continue
        family = family_map.get(name, "other")
        scores[family] = scores.get(family, 0.0) + float(worsening)
        evidence.setdefault(family, []).append(name)
    if not scores:
        return {"family": "no clear worsening", "score": 0.0, "evidence_sections": []}
    family, score = max(scores.items(), key=lambda item: item[1])
    return {"family": family, "score": score, "evidence_sections": evidence.get(family, [])}


def compare_profiles(
    baseline_profile_csv: str | Path,
    candidate_profile_csv: str | Path,
    *,
    time_s: Optional[float] = None,
    top_n: int = 8,
) -> Dict[str, Any]:
    baseline_path = _resolve(baseline_profile_csv)
    candidate_path = _resolve(candidate_profile_csv)
    baseline_rows, baseline_time = _selected_rows(baseline_path, time_s=time_s)
    candidate_rows, candidate_time = _selected_rows(candidate_path, time_s=time_s)

    sections = {
        "k_state_vs_thermo": _compare_scalar_records(
            audit._k_state_thermo_records(baseline_rows),
            audit._k_state_thermo_records(candidate_rows),
            key_fields=("stage_1based", "component"),
            metric_field="ln_K_ratio",
            label="K-state vs K-thermo",
            top_n=top_n,
        ),
        "vapor_y_vs_normalized_kx": _compare_scalar_records(
            _component_vapor_closure_records(baseline_rows),
            _component_vapor_closure_records(candidate_rows),
            key_fields=("stage_1based", "component"),
            metric_field="y_minus_normalized_Kx",
            label="vapor y vs normalized(Kx)",
            top_n=top_n,
        ),
        "thermo_unit_k_packet": _compare_scalar_records(
            _unit_k_records(baseline_rows),
            _unit_k_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="thermo_unit_K_flag",
            label="thermo unit-K packet flag",
            top_n=top_n,
            context_fields=(
                "max_abs_K_thermo_minus_1",
                "max_abs_ln_K_thermo",
                "thermo_flash_source_code",
                "thermo_flash_failed",
                "thermo_flash_phase_count",
                "thermo_unit_K_refreshed_flag",
                "thermo_unit_K_retained_flag",
                "thermo_degenerate_two_phase_unit_K_flag",
                "thermo_degenerate_two_phase_unit_K_quarantined",
            ),
        ),
        "bubble_residual": _compare_scalar_records(
            _bubble_records(baseline_rows),
            _bubble_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="bubble_residual",
            label="bubble residual sum(Kx)-1",
            top_n=top_n,
        ),
        "dew_residual": _compare_scalar_records(
            _bubble_records(baseline_rows),
            _bubble_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="dew_residual",
            label="dew residual sum(y/K)-1",
            top_n=top_n,
        ),
        "energy_residual": _compare_scalar_records(
            audit._energy_records(baseline_rows),
            audit._energy_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="energy_residual_BTUps",
            label="energy residual",
            top_n=top_n,
        ),
        "temperature_rate": _compare_scalar_records(
            audit._energy_records(baseline_rows),
            audit._energy_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="dT_energy_raw_F_per_s",
            label="raw temperature rate",
            top_n=top_n,
        ),
        "vapor_flow_calc_used": _compare_scalar_records(
            audit._vapor_flow_records(baseline_rows),
            audit._vapor_flow_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="V_calc_minus_used_lbmolph",
            label="V_calc - V_used",
            top_n=top_n,
            context_fields=(
                "vflow_energy_clamped",
                "vflow_energy_limit_hi_lbmolph",
                "vflow_energy_limit_lo_lbmolph",
                "vflow_relax_alpha",
                "implied_V_prev_lbmolph",
                "V_calc_minus_implied_prev_lbmolph",
                "hydraulic_dp_used_psia",
                "hydraulic_dp_raw_psia",
            ),
        ),
        "vflow_energy_numer": _compare_scalar_records(
            audit._vapor_flow_records(baseline_rows),
            audit._vapor_flow_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="vflow_energy_numer_BTUps",
            label="energy vapor-flow numerator",
            top_n=top_n,
            context_fields=(
                "vflow_energy_denom_BTU_per_lbmol",
                "V_calc_lbmolph",
                "V_used_lbmolph",
            ),
        ),
        "vflow_energy_L_in_term": _compare_scalar_records(
            audit._vapor_flow_records(baseline_rows),
            audit._vapor_flow_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="vflow_energy_L_in_term_BTUps",
            label="energy vapor-flow liquid-in term",
            top_n=top_n,
            context_fields=(
                "vflow_energy_L_in_lbmolph",
                "vflow_energy_hL_in_BTU_per_lbmol",
                "vflow_energy_hL_out_BTU_per_lbmol",
                "vflow_energy_hL_in_minus_hL_out_BTU_per_lbmol",
            ),
        ),
        "vflow_energy_V_in_term": _compare_scalar_records(
            audit._vapor_flow_records(baseline_rows),
            audit._vapor_flow_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="vflow_energy_V_in_term_BTUps",
            label="energy vapor-flow vapor-in term",
            top_n=top_n,
            context_fields=(
                "vflow_energy_V_in_lbmolph",
                "vflow_energy_hV_in_BTU_per_lbmol",
                "vflow_energy_hL_out_BTU_per_lbmol",
                "vflow_energy_hV_in_minus_hL_out_BTU_per_lbmol",
            ),
        ),
        "vflow_energy_dE_target": _compare_scalar_records(
            audit._vapor_flow_records(baseline_rows),
            audit._vapor_flow_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="vflow_energy_dE_target_BTUps",
            label="energy vapor-flow dE target",
            top_n=top_n,
            context_fields=("vflow_energy_heat_capacity_BTU_per_F",),
        ),
        "vflow_energy_feed_ref_term": _compare_scalar_records(
            audit._vapor_flow_records(baseline_rows),
            audit._vapor_flow_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="vflow_energy_feed_ref_term_BTUps",
            label="energy vapor-flow feed reference term",
            top_n=top_n,
        ),
        "vflow_energy_duty_term": _compare_scalar_records(
            audit._vapor_flow_records(baseline_rows),
            audit._vapor_flow_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="vflow_energy_duty_term_BTUps",
            label="energy vapor-flow duty term",
            top_n=top_n,
        ),
        "pressure_from_holdup": _compare_scalar_records(
            audit._pressure_holdup_records(baseline_rows),
            audit._pressure_holdup_records(candidate_rows),
            key_fields=("stage_1based",),
            metric_field="P_error_psia",
            label="P_from_vapor_holdup - P_state",
            top_n=top_n,
        ),
    }

    return {
        "baseline_profile_csv": str(baseline_path),
        "candidate_profile_csv": str(candidate_path),
        "requested_time_s": time_s,
        "baseline_time_s": baseline_time,
        "candidate_time_s": candidate_time,
        "n_baseline_stage_rows": len(baseline_rows),
        "n_candidate_stage_rows": len(candidate_rows),
        "sections": sections,
        "dominant_failure_family": _dominant_family(sections),
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}" if math.isfinite(value) else "nan"
    return str(value)


def _md(value: Any) -> str:
    return _fmt(value).replace("|", "\\|")


def _write_record_table(lines: List[str], rows: List[Dict[str, Any]]) -> None:
    if not rows:
        lines.append("No comparable finite records.")
        lines.append("")
        return
    fields = list(rows[0].keys())
    lines.append("| " + " | ".join(_md(field) for field in fields) + " |")
    lines.append("|" + "|".join("---" for _ in fields) + "|")
    for row in rows:
        lines.append("| " + " | ".join(_md(row.get(field, "")) for field in fields) + " |")
    lines.append("")


def write_markdown(path: str | Path, report: Dict[str, Any]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# Baseline vs Candidate Vapor/Equilibrium Coupling Comparison")
    lines.append("")
    lines.append(f"Baseline: `{report['baseline_profile_csv']}`")
    lines.append(f"Candidate: `{report['candidate_profile_csv']}`")
    lines.append(f"Baseline time: `{_fmt(report['baseline_time_s'])} s`")
    lines.append(f"Candidate time: `{_fmt(report['candidate_time_s'])} s`")
    lines.append("")
    dom = report["dominant_failure_family"]
    lines.append("## Bottom Line")
    lines.append("")
    lines.append(f"Dominant worsening family: `{dom['family']}`")
    lines.append(f"Evidence sections: `{', '.join(dom.get('evidence_sections') or [])}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Section | Compared | Worsened | Improved | Worst worsening | Worst ratio |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for name, section in report["sections"].items():
        worst = section.get("worst") or {}
        lines.append(
            f"| {_md(name)} | {_md(section.get('n_compared'))} | {_md(section.get('n_worsened'))} | "
            f"{_md(section.get('n_improved'))} | {_md(worst.get('abs_worsening', math.nan))} | "
            f"{_md(worst.get('abs_ratio', math.nan))} |"
        )
    lines.append("")
    lines.append("## Worst Worsening Records")
    lines.append("")
    for name, section in report["sections"].items():
        lines.append(f"### {section['label']}")
        lines.append("")
        _write_record_table(lines, section.get("top_worsening") or [])
    out.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Compare coupling diagnostics for baseline and candidate profile CSVs.")
    ap.add_argument("--baseline-profile-csv", required=True)
    ap.add_argument("--candidate-profile-csv", required=True)
    ap.add_argument("--time-s", type=float, default=None)
    ap.add_argument("--top-n", type=int, default=8)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args(argv)

    report = compare_profiles(
        args.baseline_profile_csv,
        args.candidate_profile_csv,
        time_s=args.time_s,
        top_n=max(1, int(args.top_n)),
    )
    if args.output_json:
        out_json = _resolve(args.output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        write_markdown(args.output_md, report)

    dom = report["dominant_failure_family"]
    print(f"Compared t={_fmt(report['baseline_time_s'])} s baseline to t={_fmt(report['candidate_time_s'])} s candidate")
    print(f"Dominant worsening family: {dom['family']}")
    for name, section in report["sections"].items():
        worst = section.get("worst") or {}
        print(
            f"{name}: worst worsening={_fmt(worst.get('abs_worsening', math.nan))}, "
            f"ratio={_fmt(worst.get('abs_ratio', math.nan))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
