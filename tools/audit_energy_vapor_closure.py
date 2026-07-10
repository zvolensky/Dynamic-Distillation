#!/usr/bin/env python
"""
Audit energy/vapor-flow closure from column profile CSV logs.

This is a read-only RHS diagnostic. It ranks whether the vapor flow, vapor
enthalpy, pressure/holdup state, equilibrium state, and energy terms reported
by column_rhs are mutually consistent at each generic vapor-flow interface.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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


def _stage_rows(rows: Iterable[Dict[str, str]], *, time_s: Optional[float] = None) -> List[Dict[str, str]]:
    stage_rows = [r for r in rows if str(r.get("node_type", "")).strip().lower() == "stage"]
    if time_s is None:
        return stage_rows
    times = sorted({_time(r) for r in stage_rows if math.isfinite(_time(r))})
    if not times:
        return []
    selected = min(times, key=lambda t: abs(t - float(time_s)))
    return [r for r in stage_rows if abs(_time(r) - selected) <= 1.0e-9]


def _component_labels(row: Dict[str, str]) -> List[str]:
    labels: List[str] = []
    for key in row:
        if key.startswith("x_") and not key.startswith("x_eq_"):
            label = key[2:]
            if f"y_{label}" in row:
                labels.append(label)
    return sorted(set(labels))


def _rel_gap(a: float, b: float) -> float:
    if not (math.isfinite(a) and math.isfinite(b)):
        return math.nan
    return (a - b) / max(abs(b), 1.0e-300)


def _max_abs(records: List[Dict[str, Any]], field: str) -> float:
    finite = [abs(float(r[field])) for r in records if math.isfinite(_finite_float(r.get(field)))]
    return max(finite) if finite else math.nan


def _worst(records: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
    finite = [r for r in records if math.isfinite(_finite_float(r.get(field)))]
    if not finite:
        return {}
    return max(finite, key=lambda r: abs(float(r[field])))


def _top(records: List[Dict[str, Any]], field: str, top_n: int) -> List[Dict[str, Any]]:
    finite = [r for r in records if math.isfinite(_finite_float(r.get(field)))]
    finite.sort(key=lambda r: abs(float(r[field])), reverse=True)
    return finite[: max(int(top_n), 0)]


def _interior_records(records: List[Dict[str, Any]], n_stages: int) -> List[Dict[str, Any]]:
    if n_stages <= 2:
        return records
    out: List[Dict[str, Any]] = []
    for record in records:
        stage = _finite_float(record.get("stage_1based"))
        if math.isfinite(stage) and 1.0 < stage < float(n_stages):
            out.append(record)
    return out


def interface_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Return one record per vapor-out interface reported on a stage row."""
    by_stage = {_stage(row): row for row in rows if math.isfinite(_finite_float(row.get("stage")))}
    out: List[Dict[str, Any]] = []
    for source_stage in sorted(by_stage):
        row = by_stage[source_stage]
        receiver = by_stage.get(source_stage - 1)
        v_calc = _finite_float(row.get("vflow_energy_calc_lbmolph"))
        v_used = _finite_float(row.get("vflow_energy_used_lbmolph"))
        v_out = _finite_float(row.get("V_out_lbmolph"))
        v_gap = v_calc - v_used if math.isfinite(v_calc) and math.isfinite(v_used) else math.nan
        source_hv = _finite_float(row.get("HV_BTU_lbmol_tray"))
        receiver_hv = _finite_float(receiver.get("HV_BTU_lbmol_tray")) if receiver else math.nan
        source_p = _finite_float(row.get("P_psia_hyd"))
        p_used_energy = _finite_float(row.get("vflow_energy_P_used_psia"))
        receiver_p = _finite_float(receiver.get("P_psia_hyd")) if receiver else math.nan
        source_t = _finite_float(row.get("T_F"))
        receiver_t = _finite_float(receiver.get("T_F")) if receiver else math.nan
        dp_pair = source_p - receiver_p if math.isfinite(source_p) and math.isfinite(receiver_p) else math.nan
        dt_pair = source_t - receiver_t if math.isfinite(source_t) and math.isfinite(receiver_t) else math.nan
        h_pair_gap = source_hv - receiver_hv if math.isfinite(source_hv) and math.isfinite(receiver_hv) else math.nan
        h_used_gap = _finite_float(row.get("vflow_energy_hV_in_minus_hL_out_BTU_per_lbmol"))
        dtemp = _finite_float(row.get("dT_energy_raw_F_per_s"))
        receiver_dtemp = _finite_float(receiver.get("dT_energy_raw_F_per_s")) if receiver else math.nan
        p_from_holdup = _finite_float(row.get("P_from_vapor_holdup_psia"))
        p_holdup_error = p_from_holdup - source_p if math.isfinite(p_from_holdup) and math.isfinite(source_p) else math.nan
        p_energy_gap = p_used_energy - source_p if math.isfinite(p_used_energy) and math.isfinite(source_p) else math.nan
        score = 0.0
        score += abs(_rel_gap(v_calc, v_used)) if math.isfinite(_rel_gap(v_calc, v_used)) else 0.0
        score += abs(dtemp) if math.isfinite(dtemp) else 0.0
        score += abs(receiver_dtemp) if math.isfinite(receiver_dtemp) else 0.0
        score += abs(h_pair_gap) / 10000.0 if math.isfinite(h_pair_gap) else 0.0
        score += abs(p_holdup_error) / 10.0 if math.isfinite(p_holdup_error) else 0.0
        out.append(
            {
                "time_s": _time(row),
                "vapor_source_stage_1based": source_stage,
                "vapor_receiver_stage_1based": source_stage - 1 if receiver else math.nan,
                "V_calc_lbmolph": v_calc,
                "V_used_lbmolph": v_used,
                "V_out_lbmolph": v_out,
                "V_calc_minus_used_lbmolph": v_gap,
                "relative_V_calc_minus_used": _rel_gap(v_calc, v_used),
                "vflow_energy_clamped": _finite_float(row.get("vflow_energy_clamped")),
                "vflow_energy_limit_hi_lbmolph": _finite_float(row.get("vflow_energy_limit_hi_lbmolph")),
                "vflow_energy_limit_lo_lbmolph": _finite_float(row.get("vflow_energy_limit_lo_lbmolph")),
                "source_P_psia": source_p,
                "vflow_energy_P_used_psia": p_used_energy,
                "vflow_energy_P_used_minus_source_P_psia": p_energy_gap,
                "vflow_energy_pressure_basis_code": _finite_float(row.get("vflow_energy_pressure_basis_code")),
                "receiver_P_psia": receiver_p,
                "source_minus_receiver_P_psia": dp_pair,
                "source_T_F": source_t,
                "receiver_T_F": receiver_t,
                "source_minus_receiver_T_F": dt_pair,
                "source_HV_BTU_per_lbmol": source_hv,
                "receiver_HV_BTU_per_lbmol": receiver_hv,
                "source_minus_receiver_HV_BTU_per_lbmol": h_pair_gap,
                "vflow_energy_hV_in_BTU_per_lbmol": _finite_float(row.get("vflow_energy_hV_in_BTU_per_lbmol")),
                "vflow_energy_hV_out_BTU_per_lbmol": _finite_float(row.get("vflow_energy_hV_out_BTU_per_lbmol")),
                "vflow_energy_hV_in_minus_hL_out_BTU_per_lbmol": h_used_gap,
                "vflow_energy_hL_in_source_code": _finite_float(row.get("vflow_energy_hL_in_source_code")),
                "vflow_energy_hL_out_source_code": _finite_float(row.get("vflow_energy_hL_out_source_code")),
                "vflow_energy_hV_in_source_code": _finite_float(row.get("vflow_energy_hV_in_source_code")),
                "vflow_energy_hV_out_source_code": _finite_float(row.get("vflow_energy_hV_out_source_code")),
                "source_dT_energy_raw_F_per_s": dtemp,
                "receiver_dT_energy_raw_F_per_s": receiver_dtemp,
                "source_P_from_vapor_holdup_psia": p_from_holdup,
                "source_P_from_holdup_minus_P_psia": p_holdup_error,
                "interface_inconsistency_score": score,
            }
        )
    return out


def k_closure_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        for label in _component_labels(row):
            k_state = _finite_float(row.get(f"K_state_{label}"))
            k_thermo = _finite_float(row.get(f"K_thermo_{label}"))
            k_eq_relax = _finite_float(row.get(f"K_eq_relax_{label}"))
            x = _finite_float(row.get(f"x_{label}"))
            y = _finite_float(row.get(f"y_{label}"))
            y_eq = _finite_float(row.get(f"y_eq_{label}"))
            y_target = _finite_float(row.get(f"y_target_{label}"))
            ln_ratio = math.log(k_state / k_thermo) if k_state > 0.0 and k_thermo > 0.0 else math.nan
            ln_eq_ratio = math.log(k_state / k_eq_relax) if k_state > 0.0 and k_eq_relax > 0.0 else math.nan
            y_gap = y - y_eq if math.isfinite(y) and math.isfinite(y_eq) else math.nan
            y_target_gap = y - y_target if math.isfinite(y) and math.isfinite(y_target) else math.nan
            out.append(
                {
                    "time_s": _time(row),
                    "stage_1based": _stage(row),
                    "component": label,
                    "x_state": x,
                    "y_state": y,
                    "y_eq": y_eq,
                    "y_target": y_target,
                    "K_state": k_state,
                    "K_thermo": k_thermo,
                    "K_eq_relax": k_eq_relax,
                    "ln_K_state_over_K_thermo": ln_ratio,
                    "ln_K_state_over_K_eq_relax": ln_eq_ratio,
                    "y_state_minus_y_eq": y_gap,
                    "y_state_minus_y_target": y_target_gap,
                }
            )
    return out


def energy_term_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    fields = [
        "vflow_energy_L_in_term_BTUps",
        "vflow_energy_V_in_term_BTUps",
        "vflow_energy_feed_ref_term_BTUps",
        "vflow_energy_duty_term_BTUps",
        "vflow_energy_dE_target_BTUps",
        "vflow_energy_resid_after_used_BTUps",
        "vflow_energy_numer_BTUps",
        "stage_energy_balance_resid_BTUps",
    ]
    out: List[Dict[str, Any]] = []
    for row in rows:
        terms = {field: _finite_float(row.get(field)) for field in fields}
        finite_terms = {field: value for field, value in terms.items() if math.isfinite(value)}
        dominant_field = ""
        dominant_value = math.nan
        if finite_terms:
            dominant_field, dominant_value = max(finite_terms.items(), key=lambda item: abs(item[1]))
        heat_capacity = _finite_float(row.get("vflow_energy_heat_capacity_BTU_per_F"))
        dtemp = _finite_float(row.get("dT_energy_raw_F_per_s"))
        dtemp_target = _finite_float(row.get("vflow_energy_dT_target_F_per_s"))
        dtemp_pred = _finite_float(row.get("vflow_energy_predicted_dT_from_used_F_per_s"))
        dtemp_gap = dtemp - dtemp_pred if math.isfinite(dtemp) and math.isfinite(dtemp_pred) else math.nan
        resid = _finite_float(row.get("stage_energy_balance_resid_BTUps"))
        temp_dE = _finite_float(row.get("temp_energy_dE_BTUps"))
        vflow_resid = _finite_float(row.get("vflow_energy_resid_after_used_BTUps"))
        temp_vflow_gap = temp_dE - vflow_resid if math.isfinite(temp_dE) and math.isfinite(vflow_resid) else math.nan
        out.append(
            {
                "time_s": _time(row),
                "stage_1based": _stage(row),
                "dT_energy_raw_F_per_s": dtemp,
                "vflow_energy_dT_target_F_per_s": dtemp_target,
                "vflow_energy_predicted_dT_from_used_F_per_s": dtemp_pred,
                "dT_raw_minus_vflow_predicted_F_per_s": dtemp_gap,
                "temp_energy_dE_BTUps": temp_dE,
                "temp_energy_dE_minus_vflow_resid_BTUps": temp_vflow_gap,
                "temp_energy_L_in_term_BTUps": _finite_float(row.get("temp_energy_L_in_term_BTUps")),
                "temp_energy_V_in_term_BTUps": _finite_float(row.get("temp_energy_V_in_term_BTUps")),
                "temp_energy_feed_ref_term_BTUps": _finite_float(row.get("temp_energy_feed_ref_term_BTUps")),
                "temp_energy_duty_term_BTUps": _finite_float(row.get("temp_energy_duty_term_BTUps")),
                "temp_energy_V_out_term_BTUps": _finite_float(row.get("temp_energy_V_out_term_BTUps")),
                "stage_energy_balance_resid_BTUps": resid,
                "stage_energy_resid_over_heat_capacity_F_per_s": resid / heat_capacity
                if math.isfinite(resid) and math.isfinite(heat_capacity) and abs(heat_capacity) > 1.0e-300
                else math.nan,
                "dominant_energy_term": dominant_field,
                "dominant_energy_term_BTUps": dominant_value,
                **terms,
                "vflow_energy_heat_capacity_BTU_per_F": heat_capacity,
                "vflow_energy_L_in_lbmolph": _finite_float(row.get("vflow_energy_L_in_lbmolph")),
                "vflow_energy_V_in_lbmolph": _finite_float(row.get("vflow_energy_V_in_lbmolph")),
                "vflow_energy_hL_in_BTU_per_lbmol": _finite_float(row.get("vflow_energy_hL_in_BTU_per_lbmol")),
                "vflow_energy_hL_out_BTU_per_lbmol": _finite_float(row.get("vflow_energy_hL_out_BTU_per_lbmol")),
                "vflow_energy_hV_in_BTU_per_lbmol": _finite_float(row.get("vflow_energy_hV_in_BTU_per_lbmol")),
                "vflow_energy_hV_out_BTU_per_lbmol": _finite_float(row.get("vflow_energy_hV_out_BTU_per_lbmol")),
                "temp_energy_L_in_lbmolph": _finite_float(row.get("temp_energy_L_in_lbmolph")),
                "temp_energy_V_in_lbmolph": _finite_float(row.get("temp_energy_V_in_lbmolph")),
                "temp_energy_V_out_lbmolph": _finite_float(row.get("temp_energy_V_out_lbmolph")),
                "temp_energy_hL_in_BTU_per_lbmol": _finite_float(row.get("temp_energy_hL_in_BTU_per_lbmol")),
                "temp_energy_hL_out_BTU_per_lbmol": _finite_float(row.get("temp_energy_hL_out_BTU_per_lbmol")),
                "temp_energy_hV_in_BTU_per_lbmol": _finite_float(row.get("temp_energy_hV_in_BTU_per_lbmol")),
                "temp_energy_hV_out_BTU_per_lbmol": _finite_float(row.get("temp_energy_hV_out_BTU_per_lbmol")),
            }
        )
    return out


def audit_profile(rows: List[Dict[str, str]], *, time_s: Optional[float] = None, top_n: int = 10) -> Dict[str, Any]:
    selected = _stage_rows(rows, time_s=time_s)
    if not selected:
        raise ValueError("No stage rows found in profile CSV")
    selected_time = _time(selected[0])
    interfaces = interface_records(selected)
    k_records = k_closure_records(selected)
    k_records_interior = _interior_records(k_records, len(selected))
    energy_records = energy_term_records(selected)
    return {
        "time_s": selected_time,
        "n_stage_rows": len(selected),
        "interface_vapor_flow_consistency": {
            "max_abs_V_calc_minus_used_lbmolph": _max_abs(interfaces, "V_calc_minus_used_lbmolph"),
            "max_abs_relative_V_calc_minus_used": _max_abs(interfaces, "relative_V_calc_minus_used"),
            "max_abs_source_minus_receiver_HV_BTU_per_lbmol": _max_abs(
                interfaces, "source_minus_receiver_HV_BTU_per_lbmol"
            ),
            "max_abs_source_P_from_holdup_minus_P_psia": _max_abs(
                interfaces, "source_P_from_holdup_minus_P_psia"
            ),
            "max_abs_vflow_energy_P_used_minus_source_P_psia": _max_abs(
                interfaces, "vflow_energy_P_used_minus_source_P_psia"
            ),
            "worst_composite_interface": _worst(interfaces, "interface_inconsistency_score"),
            "top_composite_interfaces": _top(interfaces, "interface_inconsistency_score", top_n),
            "top_V_calc_minus_used": _top(interfaces, "V_calc_minus_used_lbmolph", top_n),
        },
        "vapor_equilibrium_consistency": {
            "max_abs_ln_K_state_over_K_thermo": _max_abs(k_records, "ln_K_state_over_K_thermo"),
            "max_abs_ln_K_state_over_K_eq_relax": _max_abs(k_records, "ln_K_state_over_K_eq_relax"),
            "max_abs_y_state_minus_y_eq": _max_abs(k_records, "y_state_minus_y_eq"),
            "max_abs_y_state_minus_y_target": _max_abs(k_records, "y_state_minus_y_target"),
            "max_abs_y_state_minus_y_target_interior": _max_abs(k_records_interior, "y_state_minus_y_target"),
            "top_K_mismatch": _top(k_records, "ln_K_state_over_K_thermo", top_n),
            "top_K_eq_relax_mismatch": _top(k_records, "ln_K_state_over_K_eq_relax", top_n),
            "top_y_mismatch": _top(k_records, "y_state_minus_y_eq", top_n),
            "top_y_target_mismatch": _top(k_records, "y_state_minus_y_target", top_n),
            "top_y_target_mismatch_interior": _top(k_records_interior, "y_state_minus_y_target", top_n),
        },
        "energy_term_breakdown": {
            "max_abs_dT_energy_raw_F_per_s": _max_abs(energy_records, "dT_energy_raw_F_per_s"),
            "max_abs_energy_resid_over_heat_capacity_F_per_s": _max_abs(
                energy_records, "stage_energy_resid_over_heat_capacity_F_per_s"
            ),
            "max_abs_dT_raw_minus_vflow_predicted_F_per_s": _max_abs(
                energy_records, "dT_raw_minus_vflow_predicted_F_per_s"
            ),
            "max_abs_temp_energy_dE_minus_vflow_resid_BTUps": _max_abs(
                energy_records, "temp_energy_dE_minus_vflow_resid_BTUps"
            ),
            "worst_temperature_rate": _worst(energy_records, "dT_energy_raw_F_per_s"),
            "worst_temperature_equation_gap": _worst(energy_records, "dT_raw_minus_vflow_predicted_F_per_s"),
            "worst_temperature_vflow_residual_gap": _worst(
                energy_records, "temp_energy_dE_minus_vflow_resid_BTUps"
            ),
            "worst_energy_resid_over_heat_capacity": _worst(
                energy_records, "stage_energy_resid_over_heat_capacity_F_per_s"
            ),
            "top_temperature_rates": _top(energy_records, "dT_energy_raw_F_per_s", top_n),
            "top_temperature_equation_gaps": _top(energy_records, "dT_raw_minus_vflow_predicted_F_per_s", top_n),
            "top_temperature_vflow_residual_gaps": _top(
                energy_records, "temp_energy_dE_minus_vflow_resid_BTUps", top_n
            ),
        },
        "diagnostic_interpretation": _interpret(interfaces, k_records, energy_records, n_stages=len(selected)),
    }


def _interpret(
    interfaces: List[Dict[str, Any]],
    k_records: List[Dict[str, Any]],
    energy_records: List[Dict[str, Any]],
    *,
    n_stages: int,
) -> Dict[str, Any]:
    worst_interface = _worst(interfaces, "interface_inconsistency_score")
    worst_dtemp = _worst(energy_records, "dT_energy_raw_F_per_s")
    worst_dtemp_gap = _worst(energy_records, "dT_raw_minus_vflow_predicted_F_per_s")
    worst_k = _worst(k_records, "ln_K_state_over_K_thermo")
    worst_k_eq = _worst(k_records, "ln_K_state_over_K_eq_relax")
    worst_y_target = _worst(_interior_records(k_records, n_stages), "y_state_minus_y_target")
    families: List[str] = []
    if worst_interface and abs(_finite_float(worst_interface.get("relative_V_calc_minus_used"))) > 0.02:
        families.append("vapor-flow calc/used mismatch")
    if worst_interface and abs(_finite_float(worst_interface.get("source_minus_receiver_HV_BTU_per_lbmol"))) > 50.0:
        families.append("adjacent vapor enthalpy discontinuity")
    if worst_interface and abs(_finite_float(worst_interface.get("vflow_energy_P_used_minus_source_P_psia"))) > 1.0:
        families.append("energy closure pressure basis differs from logged hydraulic pressure")
    if worst_dtemp and abs(_finite_float(worst_dtemp.get("dT_energy_raw_F_per_s"))) > 0.15:
        families.append("temperature-rate spike")
    if worst_dtemp_gap and abs(_finite_float(worst_dtemp_gap.get("dT_raw_minus_vflow_predicted_F_per_s"))) > 0.10:
        families.append("vapor-flow/temperature energy equation mismatch")
    if worst_k_eq and abs(_finite_float(worst_k_eq.get("ln_K_state_over_K_eq_relax"))) > 0.1:
        families.append("equilibrium K-state mismatch")
    elif worst_k and abs(_finite_float(worst_k.get("ln_K_state_over_K_thermo"))) > 0.1:
        families.append("equilibrium K-state mismatch")
    if worst_y_target and abs(_finite_float(worst_y_target.get("y_state_minus_y_target"))) > 0.05:
        families.append("vapor composition target mismatch")
    if not families:
        families.append("no dominant inconsistency above built-in diagnostic thresholds")
    return {
        "dominant_families": families,
        "read_only_note": (
            "This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure."
        ),
    }


def _fmt(value: Any) -> str:
    val = _finite_float(value)
    return f"{val:.6g}" if math.isfinite(val) else "nan"


def _md(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return _fmt(value)
    return str(value).replace("|", "\\|")


def _write_table(lines: List[str], records: List[Dict[str, Any]], fields: List[str]) -> None:
    if not records:
        lines.append("No finite records.")
        lines.append("")
        return
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("|" + "|".join("---:" for _ in fields) + "|")
    for record in records:
        lines.append("| " + " | ".join(_md(record.get(field, "")) for field in fields) + " |")
    lines.append("")


def write_markdown(path: Path, report: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Energy/Vapor Closure Audit")
    lines.append("")
    lines.append(f"Profile: `{report.get('profile_csv', '')}`")
    lines.append(f"Time: `{_fmt(report['time_s'])} s`")
    lines.append(f"Stage rows: `{report['n_stage_rows']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    summary_rows = [
        (
            "max |V_calc - V_used| lbmol/h",
            report["interface_vapor_flow_consistency"]["max_abs_V_calc_minus_used_lbmolph"],
        ),
        (
            "max |relative V gap|",
            report["interface_vapor_flow_consistency"]["max_abs_relative_V_calc_minus_used"],
        ),
        (
            "max |adjacent vapor enthalpy gap| BTU/lbmol",
            report["interface_vapor_flow_consistency"]["max_abs_source_minus_receiver_HV_BTU_per_lbmol"],
        ),
        (
            "max |P_from_holdup - P| psia",
            report["interface_vapor_flow_consistency"]["max_abs_source_P_from_holdup_minus_P_psia"],
        ),
        (
            "max |energy P used - logged P| psia",
            report["interface_vapor_flow_consistency"]["max_abs_vflow_energy_P_used_minus_source_P_psia"],
        ),
        (
            "max |ln(K_state/K_thermo)|",
            report["vapor_equilibrium_consistency"]["max_abs_ln_K_state_over_K_thermo"],
        ),
        (
            "max |ln(K_state/K_eq_relax)|",
            report["vapor_equilibrium_consistency"]["max_abs_ln_K_state_over_K_eq_relax"],
        ),
        (
            "max |y_state - y_eq|",
            report["vapor_equilibrium_consistency"]["max_abs_y_state_minus_y_eq"],
        ),
        (
            "max |y_state - y_target|",
            report["vapor_equilibrium_consistency"]["max_abs_y_state_minus_y_target"],
        ),
        (
            "max |y_state - y_target| interior",
            report["vapor_equilibrium_consistency"]["max_abs_y_state_minus_y_target_interior"],
        ),
        (
            "max |dT_energy_raw| F/s",
            report["energy_term_breakdown"]["max_abs_dT_energy_raw_F_per_s"],
        ),
        (
            "max |energy residual / heat capacity| F/s",
            report["energy_term_breakdown"]["max_abs_energy_resid_over_heat_capacity_F_per_s"],
        ),
        (
            "max |dT raw - vapor-flow predicted dT| F/s",
            report["energy_term_breakdown"]["max_abs_dT_raw_minus_vflow_predicted_F_per_s"],
        ),
        (
            "max |temp dE - vapor-flow residual| BTU/s",
            report["energy_term_breakdown"]["max_abs_temp_energy_dE_minus_vflow_resid_BTUps"],
        ),
    ]
    lines.append("| Check | Value |")
    lines.append("|---|---:|")
    for label, value in summary_rows:
        lines.append(f"| {_md(label)} | {_md(value)} |")
    lines.append("")
    lines.append("## Diagnostic Interpretation")
    lines.append("")
    for family in report["diagnostic_interpretation"]["dominant_families"]:
        lines.append(f"- {family}")
    lines.append("")
    lines.append(report["diagnostic_interpretation"]["read_only_note"])
    lines.append("")
    lines.append("## Top Composite Interfaces")
    lines.append("")
    _write_table(
        lines,
        report["interface_vapor_flow_consistency"]["top_composite_interfaces"],
        [
            "vapor_source_stage_1based",
            "vapor_receiver_stage_1based",
            "interface_inconsistency_score",
            "V_calc_minus_used_lbmolph",
            "relative_V_calc_minus_used",
            "vflow_energy_P_used_minus_source_P_psia",
            "vflow_energy_pressure_basis_code",
            "source_minus_receiver_HV_BTU_per_lbmol",
            "vflow_energy_hV_in_source_code",
            "vflow_energy_hV_out_source_code",
            "source_dT_energy_raw_F_per_s",
            "receiver_dT_energy_raw_F_per_s",
        ],
    )
    lines.append("## Worst Temperature Rates")
    lines.append("")
    _write_table(
        lines,
        report["energy_term_breakdown"]["top_temperature_rates"],
        [
            "stage_1based",
            "dT_energy_raw_F_per_s",
            "vflow_energy_predicted_dT_from_used_F_per_s",
            "dT_raw_minus_vflow_predicted_F_per_s",
            "stage_energy_balance_resid_BTUps",
            "stage_energy_resid_over_heat_capacity_F_per_s",
            "dominant_energy_term",
            "dominant_energy_term_BTUps",
        ],
    )
    lines.append("## Worst Temperature Equation Gaps")
    lines.append("")
    _write_table(
        lines,
        report["energy_term_breakdown"]["top_temperature_equation_gaps"],
        [
            "stage_1based",
            "dT_raw_minus_vflow_predicted_F_per_s",
            "dT_energy_raw_F_per_s",
            "vflow_energy_predicted_dT_from_used_F_per_s",
            "vflow_energy_dT_target_F_per_s",
            "vflow_energy_resid_after_used_BTUps",
        ],
    )
    lines.append("## Worst Temperature/Vapor-Flow Term Gaps")
    lines.append("")
    _write_table(
        lines,
        report["energy_term_breakdown"]["top_temperature_vflow_residual_gaps"],
        [
            "stage_1based",
            "temp_energy_dE_minus_vflow_resid_BTUps",
            "temp_energy_dE_BTUps",
            "vflow_energy_resid_after_used_BTUps",
            "temp_energy_L_in_term_BTUps",
            "vflow_energy_L_in_term_BTUps",
            "temp_energy_V_in_term_BTUps",
            "vflow_energy_V_in_term_BTUps",
            "temp_energy_V_out_term_BTUps",
            "vflow_energy_numer_BTUps",
        ],
    )
    lines.append("## Top K Mismatches")
    lines.append("")
    _write_table(
        lines,
        report["vapor_equilibrium_consistency"]["top_K_mismatch"],
        ["stage_1based", "component", "ln_K_state_over_K_thermo", "K_state", "K_thermo", "y_state", "y_eq"],
    )
    lines.append("## Top K Eq-Relax Mismatches")
    lines.append("")
    _write_table(
        lines,
        report["vapor_equilibrium_consistency"]["top_K_eq_relax_mismatch"],
        ["stage_1based", "component", "ln_K_state_over_K_eq_relax", "K_state", "K_eq_relax", "y_state", "y_eq"],
    )
    lines.append("## Top Vapor Target Mismatches")
    lines.append("")
    _write_table(
        lines,
        report["vapor_equilibrium_consistency"]["top_y_target_mismatch"],
        ["stage_1based", "component", "y_state_minus_y_target", "y_state", "y_target", "y_eq"],
    )
    lines.append("## Top Interior Vapor Target Mismatches")
    lines.append("")
    _write_table(
        lines,
        report["vapor_equilibrium_consistency"]["top_y_target_mismatch_interior"],
        ["stage_1based", "component", "y_state_minus_y_target", "y_state", "y_target", "y_eq"],
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Audit energy/vapor-flow closure from a column profile CSV.")
    ap.add_argument("--profile-csv", required=True)
    ap.add_argument("--time-s", type=float, default=None, help="Audit nearest logged time.")
    ap.add_argument("--top-n", type=int, default=10)
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default=None)
    args = ap.parse_args(argv)

    profile_path = _resolve(args.profile_csv)
    report = audit_profile(_read_csv(profile_path), time_s=args.time_s, top_n=args.top_n)
    report["profile_csv"] = str(profile_path)

    if args.output_json:
        out_json = _resolve(args.output_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        out_md = _resolve(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(out_md, report)

    print(f"Audited {report['n_stage_rows']} stage rows at t={_fmt(report['time_s'])} s")
    print(
        "max |V_calc-V_used| lbmol/h = "
        f"{_fmt(report['interface_vapor_flow_consistency']['max_abs_V_calc_minus_used_lbmolph'])}"
    )
    print(
        "max |dT_energy_raw| F/s = "
        f"{_fmt(report['energy_term_breakdown']['max_abs_dT_energy_raw_F_per_s'])}"
    )
    print(
        "dominant families = "
        + ", ".join(report["diagnostic_interpretation"]["dominant_families"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
