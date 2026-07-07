#!/usr/bin/env python
"""
Audit runtime vapor/equilibrium/energy coupling from column profile CSV logs.

This is a diagnostic module, not an initializer. It inspects whether the
dynamic state, thermo K-values, vapor composition, energy residuals, and
vapor-flow diagnostics are mutually consistent during a run.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve(raw: str | Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (PROJECT_ROOT / p).resolve()


def _finite_float(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _read_csv(path: str | Path) -> List[Dict[str, str]]:
    with _resolve(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _time(row: Dict[str, str]) -> float:
    return _finite_float(row.get("time_s"))


def _stage(row: Dict[str, str]) -> int:
    return int(round(_finite_float(row.get("stage"))))


def _component_labels(row: Dict[str, str]) -> List[str]:
    labels: List[str] = []
    for key in row:
        if key.startswith("x_") and not key.startswith("x_eq_"):
            label = key[2:]
            if f"y_{label}" in row:
                labels.append(label)
    return sorted(set(labels))


def _stage_rows(rows: Iterable[Dict[str, str]], *, time_s: Optional[float] = None) -> List[Dict[str, str]]:
    stage_rows = [r for r in rows if str(r.get("node_type", "")).strip().lower() == "stage"]
    if time_s is None:
        return stage_rows
    times = sorted({_time(r) for r in stage_rows if math.isfinite(_time(r))})
    if not times:
        return []
    selected = min(times, key=lambda t: abs(t - float(time_s)))
    return [r for r in stage_rows if abs(_time(r) - selected) <= 1.0e-9]


def _arr(row: Dict[str, str], prefix: str, labels: Iterable[str]) -> np.ndarray:
    return np.array([_finite_float(row.get(f"{prefix}{label}")) for label in labels], dtype=float)


def _norm(v: np.ndarray) -> np.ndarray:
    arr = np.asarray(v, dtype=float)
    arr = np.where(np.isfinite(arr), arr, 0.0)
    arr = np.clip(arr, 0.0, None)
    total = float(np.sum(arr))
    if total <= 1.0e-300:
        return np.full_like(arr, np.nan, dtype=float)
    return arr / total


def _worst_record(records: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
    finite = [r for r in records if math.isfinite(float(r.get(field, math.nan)))]
    if not finite:
        return {}
    return max(finite, key=lambda r: abs(float(r[field])))


def _max_abs(records: List[Dict[str, Any]], field: str) -> float:
    worst = _worst_record(records, field)
    return abs(float(worst[field])) if worst else math.nan


def _k_state_thermo_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        for label in _component_labels(row):
            k_state = _finite_float(row.get(f"K_state_{label}"))
            k_thermo = _finite_float(row.get(f"K_thermo_{label}"))
            if not (math.isfinite(k_state) and math.isfinite(k_thermo) and k_state > 0.0 and k_thermo > 0.0):
                continue
            out.append(
                {
                    "time_s": _time(row),
                    "stage_1based": _stage(row),
                    "component": label,
                    "K_state": k_state,
                    "K_thermo": k_thermo,
                    "ln_K_ratio": math.log(k_state / k_thermo),
                    "K_ratio": k_state / k_thermo,
                }
            )
    return out


def _vapor_closure_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        labels = _component_labels(row)
        if not labels:
            continue
        x = _arr(row, "x_", labels)
        y = _arr(row, "y_", labels)
        k = _arr(row, "K_thermo_", labels)
        valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(k) & (k > 0.0)
        if not np.any(valid):
            continue
        x_valid = x[valid]
        y_valid = y[valid]
        k_valid = k[valid]
        y_from_kx = _norm(k_valid * x_valid)
        y_norm = _norm(y_valid)
        diff = np.abs(y_norm - y_from_kx)
        if not np.any(np.isfinite(diff)):
            continue
        worst_idx = int(np.nanargmax(diff))
        valid_labels = [label for label, keep in zip(labels, valid) if bool(keep)]
        out.append(
            {
                "time_s": _time(row),
                "stage_1based": _stage(row),
                "sum_y_error": float(np.nansum(y_valid) - 1.0),
                "max_abs_y_minus_normalized_Kx": float(diff[worst_idx]),
                "worst_component": valid_labels[worst_idx],
                "y": float(y_norm[worst_idx]),
                "normalized_Kx": float(y_from_kx[worst_idx]),
            }
        )
    return out


def _bubble_dew_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        labels = _component_labels(row)
        if not labels:
            continue
        x = _arr(row, "x_", labels)
        y = _arr(row, "y_", labels)
        k = _arr(row, "K_thermo_", labels)
        valid_k = np.isfinite(k) & (k > 0.0)
        x_mask = valid_k & np.isfinite(x)
        y_mask = valid_k & np.isfinite(y)
        bubble_terms = k[x_mask] * x[x_mask]
        dew_terms = y[y_mask] / k[y_mask]
        x_sum = float(np.sum(x[x_mask])) if np.any(x_mask) else math.nan
        y_sum = float(np.sum(y[y_mask])) if np.any(y_mask) else math.nan
        if not (math.isfinite(x_sum) and x_sum > 1.0e-9):
            bubble_terms = np.array([], dtype=float)
        if not (math.isfinite(y_sum) and y_sum > 1.0e-9):
            dew_terms = np.array([], dtype=float)
        bubble = float(np.sum(bubble_terms) - 1.0) if bubble_terms.size else math.nan
        dew = float(np.sum(dew_terms) - 1.0) if dew_terms.size else math.nan
        out.append(
            {
                "time_s": _time(row),
                "stage_1based": _stage(row),
                "bubble_residual": bubble,
                "dew_residual": dew,
            }
        )
    return out


def _energy_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        resid = _finite_float(row.get("stage_energy_balance_resid_BTUps"))
        dtdt = _finite_float(row.get("dT_energy_raw_F_per_s"))
        heat_cap = _finite_float(row.get("tray_effective_heat_capacity_BTU_per_F"))
        rel = math.nan
        if math.isfinite(resid) and math.isfinite(heat_cap) and abs(heat_cap) > 1.0e-300:
            rel = resid / heat_cap
        if math.isfinite(resid) or math.isfinite(dtdt):
            out.append(
                {
                    "time_s": _time(row),
                    "stage_1based": _stage(row),
                    "energy_residual_BTUps": resid,
                    "dT_energy_raw_F_per_s": dtdt,
                    "energy_residual_over_heat_capacity_F_per_s": rel,
                }
            )
    return out


def _vapor_flow_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        v_used = _finite_float(row.get("vflow_energy_used_lbmolph"))
        v_calc = _finite_float(row.get("vflow_energy_calc_lbmolph"))
        v_clamped = _finite_float(row.get("vflow_energy_clamped"))
        v_limit_hi = _finite_float(row.get("vflow_energy_limit_hi_lbmolph"))
        v_limit_lo = _finite_float(row.get("vflow_energy_limit_lo_lbmolph"))
        v_relax_alpha = _finite_float(row.get("vflow_relax_alpha"))
        dp = _finite_float(row.get("hydraulic_dp_used_psia"))
        raw_dp = _finite_float(row.get("hydraulic_dp_raw_psia"))
        l_in_term = _finite_float(row.get("vflow_energy_L_in_term_BTUps"))
        v_in_term = _finite_float(row.get("vflow_energy_V_in_term_BTUps"))
        feed_ref_term = _finite_float(row.get("vflow_energy_feed_ref_term_BTUps"))
        duty_term = _finite_float(row.get("vflow_energy_duty_term_BTUps"))
        de_target = _finite_float(row.get("vflow_energy_dE_target_BTUps"))
        numer = _finite_float(row.get("vflow_energy_numer_BTUps"))
        heat_capacity = _finite_float(row.get("vflow_energy_heat_capacity_BTU_per_F"))
        l_in = _finite_float(row.get("vflow_energy_L_in_lbmolph"))
        v_in = _finite_float(row.get("vflow_energy_V_in_lbmolph"))
        h_l_in = _finite_float(row.get("vflow_energy_hL_in_BTU_per_lbmol"))
        h_l_out = _finite_float(row.get("vflow_energy_hL_out_BTU_per_lbmol"))
        h_v_in = _finite_float(row.get("vflow_energy_hV_in_BTU_per_lbmol"))
        h_v_out = _finite_float(row.get("vflow_energy_hV_out_BTU_per_lbmol"))
        h_l_delta = _finite_float(row.get("vflow_energy_hL_in_minus_hL_out_BTU_per_lbmol"))
        h_v_delta = _finite_float(row.get("vflow_energy_hV_in_minus_hL_out_BTU_per_lbmol"))
        sensitivity = math.nan
        if math.isfinite(v_calc) and math.isfinite(dp) and abs(dp) > 1.0e-12:
            sensitivity = v_calc / dp
        implied_prev = math.nan
        relax_gap = math.nan
        if (
            math.isfinite(v_calc)
            and math.isfinite(v_used)
            and math.isfinite(v_relax_alpha)
            and v_relax_alpha >= 0.0
            and v_relax_alpha < 1.0
        ):
            implied_prev = (v_used - v_relax_alpha * v_calc) / (1.0 - v_relax_alpha)
            relax_gap = v_calc - implied_prev
        if math.isfinite(v_used) or math.isfinite(v_calc) or math.isfinite(dp):
            out.append(
                {
                    "time_s": _time(row),
                    "stage_1based": _stage(row),
                    "V_used_lbmolph": v_used,
                    "V_calc_lbmolph": v_calc,
                    "V_calc_minus_used_lbmolph": v_calc - v_used if math.isfinite(v_calc) and math.isfinite(v_used) else math.nan,
                    "vflow_energy_clamped": v_clamped,
                    "vflow_energy_limit_hi_lbmolph": v_limit_hi,
                    "vflow_energy_limit_lo_lbmolph": v_limit_lo,
                    "vflow_relax_alpha": v_relax_alpha,
                    "implied_V_prev_lbmolph": implied_prev,
                    "V_calc_minus_implied_prev_lbmolph": relax_gap,
                    "hydraulic_dp_used_psia": dp,
                    "hydraulic_dp_raw_psia": raw_dp,
                    "estimated_dVdP_lbmolph_per_psia": sensitivity,
                    "vflow_energy_L_in_term_BTUps": l_in_term,
                    "vflow_energy_V_in_term_BTUps": v_in_term,
                    "vflow_energy_feed_ref_term_BTUps": feed_ref_term,
                    "vflow_energy_duty_term_BTUps": duty_term,
                    "vflow_energy_dE_target_BTUps": de_target,
                    "vflow_energy_numer_BTUps": numer,
                    "vflow_energy_heat_capacity_BTU_per_F": heat_capacity,
                    "vflow_energy_L_in_lbmolph": l_in,
                    "vflow_energy_V_in_lbmolph": v_in,
                    "vflow_energy_hL_in_BTU_per_lbmol": h_l_in,
                    "vflow_energy_hL_out_BTU_per_lbmol": h_l_out,
                    "vflow_energy_hV_in_BTU_per_lbmol": h_v_in,
                    "vflow_energy_hV_out_BTU_per_lbmol": h_v_out,
                    "vflow_energy_hL_in_minus_hL_out_BTU_per_lbmol": h_l_delta,
                    "vflow_energy_hV_in_minus_hL_out_BTU_per_lbmol": h_v_delta,
                    "negative_or_zero_flow": bool(math.isfinite(v_used) and v_used <= 0.0),
                }
            )
    return out


def _pressure_holdup_records(rows: List[Dict[str, str]], *, min_vapor_holdup_lbmol: float = 1.0e-9) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        p_state = _finite_float(row.get("P_psia_hyd"))
        p_from = _finite_float(row.get("P_from_vapor_holdup_psia"))
        mv = _finite_float(row.get("MV_lbmol"))
        volume = _finite_float(row.get("tray_vapor_volume_ft3"))
        z = _finite_float(row.get("Z_tray"))
        if not (math.isfinite(p_state) and math.isfinite(p_from)):
            continue
        if not (math.isfinite(mv) and mv > float(min_vapor_holdup_lbmol)):
            continue
        diff = p_from - p_state
        rel = diff / max(abs(p_state), 1.0e-300)
        out.append(
            {
                "time_s": _time(row),
                "stage_1based": _stage(row),
                "P_state_psia": p_state,
                "P_from_vapor_holdup_psia": p_from,
                "P_error_psia": diff,
                "relative_P_error": rel,
                "MV_lbmol": mv,
                "tray_vapor_volume_ft3": volume,
                "Z_tray": z,
            }
        )
    return out


def audit_profile(rows: List[Dict[str, str]], *, time_s: Optional[float] = None) -> Dict[str, Any]:
    selected_rows = _stage_rows(rows, time_s=time_s)
    if not selected_rows:
        raise ValueError("No stage rows found in profile CSV")

    selected_time = _time(selected_rows[0])
    k_records = _k_state_thermo_records(selected_rows)
    vapor_records = _vapor_closure_records(selected_rows)
    bubble_dew_records = _bubble_dew_records(selected_rows)
    energy_records = _energy_records(selected_rows)
    flow_records = _vapor_flow_records(selected_rows)
    pressure_records = _pressure_holdup_records(selected_rows)

    pressure_holdup_status: Dict[str, Any]
    if pressure_records:
        pressure_holdup_status = {
            "available": True,
            "n_records": len(pressure_records),
            "max_abs_P_error_psia": _max_abs(pressure_records, "P_error_psia"),
            "worst_P_error": _worst_record(pressure_records, "P_error_psia"),
            "max_abs_relative_P_error": _max_abs(pressure_records, "relative_P_error"),
            "worst_relative_P_error": _worst_record(pressure_records, "relative_P_error"),
        }
    else:
        has_columns = any("P_from_vapor_holdup_psia" in r and "tray_vapor_volume_ft3" in r and "Z_tray" in r for r in selected_rows)
        pressure_holdup_status = {
            "available": False,
            "reason": (
                "no finite rows with meaningful vapor holdup"
                if has_columns
                else "profile CSV does not include tray vapor volume/Z data needed to compute P_from_vapor_holdup"
            ),
        }

    return {
        "time_s": selected_time,
        "n_stage_rows": len(selected_rows),
        "k_state_vs_thermo": {
            "max_abs_ln_K_ratio": _max_abs(k_records, "ln_K_ratio"),
            "worst": _worst_record(k_records, "ln_K_ratio"),
        },
        "vapor_composition_closure": {
            "max_abs_sum_y_error": _max_abs(vapor_records, "sum_y_error"),
            "max_abs_y_minus_normalized_Kx": _max_abs(vapor_records, "max_abs_y_minus_normalized_Kx"),
            "worst_y_minus_normalized_Kx": _worst_record(vapor_records, "max_abs_y_minus_normalized_Kx"),
            "worst_sum_y_error": _worst_record(vapor_records, "sum_y_error"),
        },
        "bubble_dew_consistency": {
            "max_abs_bubble_residual": _max_abs(bubble_dew_records, "bubble_residual"),
            "worst_bubble": _worst_record(bubble_dew_records, "bubble_residual"),
            "max_abs_dew_residual": _max_abs(bubble_dew_records, "dew_residual"),
            "worst_dew": _worst_record(bubble_dew_records, "dew_residual"),
        },
        "pressure_holdup_consistency": pressure_holdup_status,
        "energy_consistency": {
            "max_abs_energy_residual_BTUps": _max_abs(energy_records, "energy_residual_BTUps"),
            "worst_energy_residual": _worst_record(energy_records, "energy_residual_BTUps"),
            "max_abs_dT_energy_raw_F_per_s": _max_abs(energy_records, "dT_energy_raw_F_per_s"),
            "worst_dT_energy_raw": _worst_record(energy_records, "dT_energy_raw_F_per_s"),
        },
        "vapor_flow_sensitivity": {
            "max_abs_V_calc_minus_used_lbmolph": _max_abs(flow_records, "V_calc_minus_used_lbmolph"),
            "worst_V_calc_minus_used": _worst_record(flow_records, "V_calc_minus_used_lbmolph"),
            "max_abs_estimated_dVdP_lbmolph_per_psia": _max_abs(flow_records, "estimated_dVdP_lbmolph_per_psia"),
            "worst_estimated_dVdP": _worst_record(flow_records, "estimated_dVdP_lbmolph_per_psia"),
            "negative_or_zero_flow_count": sum(1 for r in flow_records if bool(r.get("negative_or_zero_flow"))),
        },
    }


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}" if math.isfinite(value) else "nan"
    return str(value)


def _md(value: Any) -> str:
    return _fmt(value).replace("|", "\\|")


def _write_markdown(path: Path, report: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Vapor/Equilibrium/Energy Coupling Audit")
    lines.append("")
    lines.append(f"Profile: `{report['profile_csv']}`")
    lines.append(f"Time: `{_fmt(float(report['time_s']))} s`")
    lines.append(f"Stage rows: `{report['n_stage_rows']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    rows = [
        ("max |ln(K_state/K_thermo)|", report["k_state_vs_thermo"]["max_abs_ln_K_ratio"]),
        ("max |sum(y)-1|", report["vapor_composition_closure"]["max_abs_sum_y_error"]),
        ("max |y-normalized(Kx)|", report["vapor_composition_closure"]["max_abs_y_minus_normalized_Kx"]),
        ("max |sum(Kx)-1|", report["bubble_dew_consistency"]["max_abs_bubble_residual"]),
        ("max |sum(y/K)-1|", report["bubble_dew_consistency"]["max_abs_dew_residual"]),
        (
            "max |P_from_vapor_holdup-P_state| psia",
            report["pressure_holdup_consistency"].get("max_abs_P_error_psia", math.nan),
        ),
        (
            "max |relative pressure error|",
            report["pressure_holdup_consistency"].get("max_abs_relative_P_error", math.nan),
        ),
        ("max |energy residual| BTU/s", report["energy_consistency"]["max_abs_energy_residual_BTUps"]),
        ("max |raw dT/dt| F/s", report["energy_consistency"]["max_abs_dT_energy_raw_F_per_s"]),
        ("max |V_calc-V_used| lbmol/h", report["vapor_flow_sensitivity"]["max_abs_V_calc_minus_used_lbmolph"]),
        ("max |estimated dV/dP| lbmol/h/psi", report["vapor_flow_sensitivity"]["max_abs_estimated_dVdP_lbmolph_per_psia"]),
    ]
    lines.append("| Check | Value |")
    lines.append("|---|---:|")
    for label, value in rows:
        lines.append(f"| {_md(label)} | {_md(value)} |")
    lines.append("")
    lines.append("## Worst Records")
    lines.append("")
    for title, section, key in [
        ("K-State vs K-Thermo", "k_state_vs_thermo", "worst"),
        ("Vapor y vs normalized(Kx)", "vapor_composition_closure", "worst_y_minus_normalized_Kx"),
        ("Bubble Residual", "bubble_dew_consistency", "worst_bubble"),
        ("Dew Residual", "bubble_dew_consistency", "worst_dew"),
        ("Pressure From Vapor Holdup", "pressure_holdup_consistency", "worst_P_error"),
        ("Relative Pressure From Vapor Holdup", "pressure_holdup_consistency", "worst_relative_P_error"),
        ("Energy Residual", "energy_consistency", "worst_energy_residual"),
        ("Temperature Rate", "energy_consistency", "worst_dT_energy_raw"),
        ("Vapor Flow Calc-Used", "vapor_flow_sensitivity", "worst_V_calc_minus_used"),
        ("Vapor Flow Sensitivity", "vapor_flow_sensitivity", "worst_estimated_dVdP"),
    ]:
        record = report[section].get(key) or {}
        lines.append(f"### {title}")
        lines.append("")
        if not record:
            lines.append("No finite record.")
            lines.append("")
            continue
        lines.append("| Field | Value |")
        lines.append("|---|---:|")
        for field, value in record.items():
            lines.append(f"| {_md(field)} | {_md(value)} |")
        lines.append("")
    ph = report["pressure_holdup_consistency"]
    lines.append("## Pressure Holdup Consistency")
    lines.append("")
    lines.append(f"Available: `{ph.get('available')}`")
    lines.append("")
    if ph.get("available"):
        lines.append(f"Records: `{ph.get('n_records')}`")
    else:
        lines.append(str(ph.get("reason", "")))
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Audit vapor/equilibrium/energy coupling from a column profile CSV.")
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--time-s", type=float, default=None, help="Audit nearest logged time. Defaults to all profile rows.")
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args(argv)

    profile_path = _resolve(args.profile_csv)
    report = audit_profile(_read_csv(profile_path), time_s=args.time_s)
    report["profile_csv"] = str(profile_path)

    if args.output_json:
        out_json = _resolve(args.output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        out_md = _resolve(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        _write_markdown(out_md, report)

    print(f"Audited {report['n_stage_rows']} stage rows at t={_fmt(float(report['time_s']))} s")
    print(f"max |ln(K_state/K_thermo)| = {_fmt(report['k_state_vs_thermo']['max_abs_ln_K_ratio'])}")
    print(
        "max |y-normalized(Kx)| = "
        f"{_fmt(report['vapor_composition_closure']['max_abs_y_minus_normalized_Kx'])}"
    )
    print(f"max |raw dT/dt| F/s = {_fmt(report['energy_consistency']['max_abs_dT_energy_raw_F_per_s'])}")
    print(
        "max |V_calc-V_used| lbmol/h = "
        f"{_fmt(report['vapor_flow_sensitivity']['max_abs_V_calc_minus_used_lbmolph'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
