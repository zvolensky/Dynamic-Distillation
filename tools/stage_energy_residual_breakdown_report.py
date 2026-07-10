#!/usr/bin/env python
"""
Stage-by-stage energy residual breakdown report at t=0.

Purpose
-------
Quantify tray energy-rate terms used by the B1 energy-holdup model and show
where large rates originate, including an estimated feed-enthalpy term that is
not part of the current B1 tray-energy derivative.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from dynamic_distillation.column_rhs_v1 import (  # noqa: E402
    ColumnInputs,
    _feed_component_rates_lbmolps,
    _feed_enthalpy_rate_btu_per_s,
    column_rhs,
)
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.dynamic_run_scaffold_v1 import (  # noqa: E402
    RunnerConfig,
    _clear_initial_tray_vapor_holdup,
    _initialize_vapor_holdup_from_spec_pressure,
    build_inputs_for_runner,
    load_native_checkpoint_initial_state,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout  # noqa: E402
from dynamic_distillation.thermo_model_v1 import ConstantCpThermo  # noqa: E402


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_path(project_root: Path, raw: str) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def _as_float(x: Any, default: float = math.nan) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    return v if np.isfinite(v) else default


def _diag_vec(diag: Dict[str, Any], key: str, n: int, fill: float = math.nan) -> np.ndarray:
    if key not in diag:
        return np.full(n, fill, dtype=float)
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((n,))
        return arr
    except Exception:
        return np.full(n, fill, dtype=float)


def _diag_scalar(diag: Dict[str, Any], key: str) -> float:
    if key not in diag:
        return math.nan
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((-1,))
        if arr.size == 0:
            return math.nan
        return _as_float(arr[0], default=math.nan)
    except Exception:
        return math.nan


def _scenario_inputs(base_inputs: ColumnInputs, scenario: str) -> ColumnInputs:
    key = str(scenario).strip().lower()
    if key in ("default", "default_from_case"):
        return base_inputs
    if key == "spec_profile_no_feed_flash":
        return replace(
            base_inputs,
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=False,
        )
    if key == "spec_profile_with_feed_flash":
        return replace(
            base_inputs,
            pressure_model="spec",
            vapor_flow_model="profile",
            flash_feed_at_stage_conditions=True,
        )
    if key == "hydraulic_energy_no_feed_flash":
        return replace(
            base_inputs,
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=False,
        )
    if key == "hydraulic_energy_with_feed_flash":
        return replace(
            base_inputs,
            pressure_model="hydraulic",
            vapor_flow_model="energy",
            flash_feed_at_stage_conditions=True,
        )
    raise ValueError(
        f"Unknown scenario '{scenario}'. "
        "Use one of: default, spec_profile_no_feed_flash, "
        "spec_profile_with_feed_flash, hydraulic_energy_no_feed_flash, "
        "hydraulic_energy_with_feed_flash."
    )


def _build_initial_state(
    *,
    col: Any,
    layout: StateVectorLayout,
    inputs: ColumnInputs,
    include_temperature: bool,
    use_excel_vapor_holdup: bool,
) -> np.ndarray:
    y = layout.pack_y0(col)
    if not bool(use_excel_vapor_holdup):
        y = _clear_initial_tray_vapor_holdup(y, layout)
    y = _initialize_vapor_holdup_from_spec_pressure(
        col=col,
        layout=layout,
        y=y,
        inputs=inputs,
        include_temperature=bool(include_temperature),
        preserve_tray_vapor_holdup=bool(use_excel_vapor_holdup),
    )
    return np.asarray(y, dtype=float)


def _inputs_with_checkpoint_memory(
    *,
    inputs: ColumnInputs,
    memory: Dict[str, Any],
    vapor_flow_zero_temperature_target: bool,
) -> ColumnInputs:
    if not memory:
        return inputs
    p_prev = memory.get("last_P_hyd")
    if p_prev is None:
        p_prev = memory.get("last_P_diag")
    kwargs: Dict[str, Any] = {
        "P_tray_prev": p_prev,
        "T_tray_prev_F": memory.get("last_T_tray"),
        "K_tray_prev": memory.get("last_K_tray"),
        "HL_prev": memory.get("last_HL"),
        "HV_prev": memory.get("last_HV"),
        "Zfac_prev": memory.get("last_Zfac"),
        "Z_overall_prev": memory.get("last_z_overall"),
        "V_out_prev_lbmolph": memory.get("last_V_out"),
        "dT_tray_target_F_per_s": (
            None if bool(vapor_flow_zero_temperature_target) else memory.get("last_dT_tray")
        ),
        "rhoL_tray_lbmol_ft3": memory.get("last_rhoL"),
        "tray_thermo_prev": memory.get("last_tray_thermo_packet"),
        "condenser_duty_prev": memory.get("last_condenser_duty_packet"),
        "bottom_sump_cp_prev": memory.get("last_bottom_sump_cp_packet"),
        "energy_balance_resid_prev_BTUps_tray": memory.get("last_energy_resid_tray"),
        "phase_energy_damping_min_prev_tray": memory.get("last_phase_energy_damping_min"),
        "tray_temp_pressure_slope_prev_F_per_psi": memory.get("last_tray_temp_pressure_slope"),
        "tray_bubble_target_prev_F": memory.get("last_tray_bubble_target_F"),
        "reb_T_prev": memory.get("last_reb_T"),
        "reb_x_prev": memory.get("last_reb_x"),
        "reb_y_prev": memory.get("last_reb_y"),
        "reb_beta_prev": memory.get("last_reb_beta"),
        "top_drum_pressure_T_prev_F": memory.get("last_top_drum_pressure_T"),
    }
    if bool(getattr(inputs, "flash_feed_at_stage_conditions", False)):
        kwargs["feed_stage_flash_prev"] = memory.get("last_feed_stage_flash_packet")
    else:
        kwargs["feed_stage_flash_prev"] = None
    return replace(inputs, **kwargs)


def _safe_specific_h(energy: np.ndarray, holdup: np.ndarray, max_abs_h: float = 1.0e6) -> np.ndarray:
    den = np.maximum(np.asarray(holdup, dtype=float), 1e-8)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        h = np.asarray(energy, dtype=float) / den
    h = np.nan_to_num(h, nan=0.0, posinf=max_abs_h, neginf=-max_abs_h)
    h = np.clip(h, -max_abs_h, max_abs_h)
    return h


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate stage energy residual breakdown report at t=0.")
    ap.add_argument("--excel", dest="excel_path", default="distillation_column_template.xlsx")
    ap.add_argument(
        "--init-from-checkpoint",
        default=None,
        help="Load a native .npz checkpoint state before the t=0 energy breakdown.",
    )
    ap.add_argument("--thermo", dest="thermo_mode", choices=["stub", "table", "table-pool", "dwsim"], default="table-pool")
    ap.add_argument("--thermo-table", dest="thermo_table_path", default="cache/thermo_table.json")
    ap.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=6)
    ap.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    ap.add_argument("--runtime-mode", choices=["legacy", "parity", "calibration", "hydraulic"], default="parity")
    ap.add_argument("--condenser-duty-mode", default="total-condense")
    ap.add_argument(
        "--scenario",
        dest="scenario",
        default="default",
        help=(
            "default | spec_profile_no_feed_flash | spec_profile_with_feed_flash | "
            "hydraulic_energy_no_feed_flash | hydraulic_energy_with_feed_flash"
        ),
    )
    ap.add_argument("--no-temperature", dest="include_temperature", action="store_false")
    ap.add_argument("--use-excel-vapor-holdup", dest="use_excel_vapor_holdup", action="store_true")
    ap.add_argument("--include-energy", dest="include_energy", action="store_true")
    ap.add_argument("--no-equilibrium", dest="enable_equilibrium_relaxation", action="store_false")
    ap.set_defaults(enable_equilibrium_relaxation=True)
    ap.add_argument("--no-flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_false")
    ap.add_argument("--flash-feed-at-stage-conditions", dest="flash_feed_at_stage_conditions", action="store_true")
    ap.set_defaults(flash_feed_at_stage_conditions=None)
    ap.add_argument("--vapor-holdup-relaxation-sec", type=float, default=None)
    ap.add_argument("--vapor-flow-relaxation-sec", type=float, default=None)
    ap.add_argument(
        "--vapor-flow-zero-temperature-target",
        action="store_true",
        help="Do not restore checkpoint dT/dt target memory into the energy vapor-flow closure.",
    )
    ap.add_argument("--output-csv", dest="output_csv", default=None)
    ap.add_argument("--output-summary", dest="output_summary", default=None)
    ap.set_defaults(include_temperature=True, include_energy=True)
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    excel_path = _resolve_path(project_root, str(args.excel_path))
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel case file not found: {excel_path}")
    checkpoint_path: Optional[Path] = None
    if args.init_from_checkpoint:
        checkpoint_path = _resolve_path(project_root, str(args.init_from_checkpoint))
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Native checkpoint file not found: {checkpoint_path}")

    thermo_table_path: Optional[Path] = None
    if str(args.thermo_mode).lower() in ("table", "table-pool"):
        thermo_table_path = _resolve_path(project_root, str(args.thermo_table_path))
        if not thermo_table_path.exists():
            raise FileNotFoundError(f"Thermo table file not found: {thermo_table_path}")

    case = load_case_from_excel(str(excel_path))
    col = build_column_spec_from_case(case)
    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=bool(args.include_temperature),
        include_energy=True,
    )

    cfg = RunnerConfig(
        excel_path=str(excel_path),
        runtime_mode=str(args.runtime_mode),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=(None if thermo_table_path is None else str(thermo_table_path)),
        thermo_pool_workers=args.thermo_pool_workers,
        thermo_pool_chunk_size=max(int(args.thermo_pool_chunk_size), 1),
        include_temperature=bool(args.include_temperature),
        include_energy=True,
        condenser_duty_mode=str(args.condenser_duty_mode),
        enable_equilibrium_relaxation=bool(args.enable_equilibrium_relaxation),
        flash_feed_at_stage_conditions=args.flash_feed_at_stage_conditions,
        vapor_holdup_relaxation_sec=args.vapor_holdup_relaxation_sec,
        vapor_flow_relaxation_sec=args.vapor_flow_relaxation_sec,
        write_logs=False,
    )

    base_inputs, provider = build_inputs_for_runner(case, col, cfg)
    try:
        inputs = _scenario_inputs(base_inputs, str(args.scenario))
        checkpoint_info: Dict[str, Any] = {}
        initial_state_source = "excel"
        if checkpoint_path is not None:
            y0, checkpoint_info, checkpoint_memory = load_native_checkpoint_initial_state(
                path=checkpoint_path,
                layout=layout,
                col=col,
            )
            inputs = _inputs_with_checkpoint_memory(
                inputs=inputs,
                memory=checkpoint_memory,
                vapor_flow_zero_temperature_target=bool(args.vapor_flow_zero_temperature_target),
            )
            initial_state_source = "native_checkpoint"
        else:
            y0 = _build_initial_state(
                col=col,
                layout=layout,
                inputs=inputs,
                include_temperature=bool(args.include_temperature),
                use_excel_vapor_holdup=bool(args.use_excel_vapor_holdup),
            )

        # Evaluate RHS once at initial state.
        dydt, diag = column_rhs(0.0, y0, col, layout, inputs)
        u0 = layout.unpack(y0)
        du = layout.unpack(np.asarray(dydt, dtype=float))
        N = int(col.n_stages)
        Nc = int(col.n_components)
        eps = float(layout.epsilon_lbmol)

        ML = np.asarray(diag.get("ML_tot_tray", u0.get("ML_tot_tray")), dtype=float).reshape((N,))
        MV = np.asarray(diag.get("MV_tot_tray", u0.get("MV_tot_tray")), dtype=float).reshape((N,))
        EL = np.asarray(u0["tray_EL_BTU"], dtype=float).reshape((N,))
        EV = np.asarray(u0["tray_EV_BTU"], dtype=float).reshape((N,))
        hL = _safe_specific_h(EL, ML)
        hV = _safe_specific_h(EV, MV)

        L_out = _diag_vec(diag, "L_out_lbmolph", N, fill=0.0) / 3600.0
        V_out = _diag_vec(diag, "V_out_lbmolph", N, fill=0.0) / 3600.0

        # Build incoming L/V from outgoing neighbors using model convention.
        L_in = np.zeros(N, dtype=float)
        V_in = np.zeros(N, dtype=float)
        if N > 1:
            L_in[1:] = L_out[:-1]
            V_in[:-1] = V_out[1:]
        if N > 0:
            V_in[-1] = V_out[-1]  # boilup boundary

        # Phase-by-phase energy terms exactly following _energy_derivatives_b1.
        dEL_in = np.zeros(N, dtype=float)
        dEL_out = np.zeros(N, dtype=float)
        dEV_in = np.zeros(N, dtype=float)
        dEV_out = np.zeros(N, dtype=float)
        for i in range(N):
            lin = 0.0 if i == 0 else float(L_out[i - 1])
            hlin = float(hL[i]) if i == 0 else float(hL[i - 1])
            dEL_in[i] = lin * hlin
            dEL_out[i] = -float(L_out[i]) * float(hL[i])

            vin = 0.0 if i == (N - 1) else float(V_out[i + 1])
            hvin = float(hV[i]) if i == (N - 1) else float(hV[i + 1])
            dEV_in[i] = vin * hvin
            dEV_out[i] = -float(V_out[i]) * float(hV[i])

        Qc_BTUph = _diag_scalar(diag, "Q_cond_used_BTUph")
        Qr_BTUph = _diag_scalar(diag, "Q_reb_used_BTUph")
        cond_total_flag = _diag_scalar(diag, "Q_cond_mode_total_condense")
        condenser_is_total = bool(np.isfinite(cond_total_flag) and float(cond_total_flag) >= 0.5)

        dEL_duty = np.zeros(N, dtype=float)
        dEV_duty = np.zeros(N, dtype=float)
        if N > 0 and np.isfinite(Qc_BTUph):
            if condenser_is_total:
                dEL_duty[0] += float(Qc_BTUph) / 3600.0
            else:
                dEV_duty[0] += float(Qc_BTUph) / 3600.0
        if N > 0 and np.isfinite(Qr_BTUph):
            dEL_duty[-1] += float(Qr_BTUph) / 3600.0

        # Apply same masks as _energy_derivatives_b1.
        no_liq = ML <= eps
        no_vap = MV <= eps
        dEL_in[no_liq] = 0.0
        dEL_out[no_liq] = 0.0
        dEL_duty[no_liq] = 0.0
        dEV_in[no_vap] = 0.0
        dEV_out[no_vap] = 0.0
        dEV_duty[no_vap] = 0.0

        # Reboiler no-holdup override in column_rhs.
        reboiler_no_holdup = False
        try:
            M_spec = np.asarray(col.M_L_lbmol, dtype=float).reshape((N,))
            reboiler_no_holdup = bool(float(M_spec[-1]) <= eps)
        except Exception:
            reboiler_no_holdup = bool(float(ML[-1]) <= eps)
        if reboiler_no_holdup and N > 0:
            dEL_in[-1] = 0.0
            dEL_out[-1] = 0.0
            dEL_duty[-1] = 0.0
            dEV_in[-1] = 0.0
            dEV_out[-1] = 0.0
            dEV_duty[-1] = 0.0

        model_term_sum = dEL_in + dEL_out + dEL_duty + dEV_in + dEV_out + dEV_duty
        dEL_model = np.asarray(du["tray_EL_BTU"], dtype=float).reshape((N,))
        dEV_model = np.asarray(du["tray_EV_BTU"], dtype=float).reshape((N,))
        model_total = dEL_model + dEV_model
        closure_err = model_total - model_term_sum

        # Estimate omitted feed-enthalpy source term using helper.
        P_feed = _diag_vec(diag, "P_psia_hyd", N)
        if not np.all(np.isfinite(P_feed)):
            P_feed = np.asarray(col.P_psia, dtype=float).reshape((N,))
        feed_stage0, Fk_L, Fk_V = _feed_component_rates_lbmolps(
            col=col,
            Nc=Nc,
            thermo_provider=getattr(inputs, "thermo_provider", None),
            P_tray_psia=P_feed,
            flash_feed_at_stage_conditions=bool(getattr(inputs, "flash_feed_at_stage_conditions", True)),
        )
        if "tray_T_f" in u0:
            T_feed_ref = np.asarray(u0["tray_T_f"], dtype=float).reshape((N,))
        else:
            T_feed_ref = np.asarray(col.T_f, dtype=float).reshape((N,))

        thermo_ref = inputs.thermo
        if thermo_ref is None:
            thermo_ref = ConstantCpThermo(
                cp_liq_components=np.full(Nc, 30.0, dtype=float),
                cp_vap_components=np.full(Nc, 20.0, dtype=float),
                tref_f=60.0,
            )
        feed_q = np.zeros(N, dtype=float)
        for i in range(N):
            feed_q[i] = float(
                _feed_enthalpy_rate_btu_per_s(
                    feed_stage0=feed_stage0,
                    stage0=i,
                    col=col,
                    Nc=Nc,
                    Fk_L=Fk_L,
                    Fk_V=Fk_V,
                    T_stage_F=float(T_feed_ref[i]),
                    P_stage_psia=float(P_feed[i]),
                    thermo=thermo_ref,
                    thermo_provider=getattr(inputs, "thermo_provider", None),
                    epsilon_lbmol=eps,
                    flash_feed_at_stage_conditions=bool(getattr(inputs, "flash_feed_at_stage_conditions", True)),
                )
            )

        dT = _diag_vec(diag, "dT_tray_F_per_s", N)
        energy_resid_diag = _diag_vec(diag, "energy_balance_resid_BTUps_tray", N)
        dML_model = np.sum(np.asarray(du["tray_L"], dtype=float).reshape((N, Nc)), axis=1)
        dMV_model = (
            np.sum(np.asarray(du["tray_V"], dtype=float).reshape((N, Nc)), axis=1)
            if "tray_V" in du
            else np.zeros(N, dtype=float)
        )
        q_feed_diag = _diag_vec(diag, "Q_feed_BTUps_tray", N)
        temp_energy_dE = _diag_vec(diag, "temp_energy_dE_BTUps_tray", N)
        temp_energy_L_in = _diag_vec(diag, "temp_energy_L_in_term_BTUps_tray", N)
        temp_energy_V_in = _diag_vec(diag, "temp_energy_V_in_term_BTUps_tray", N)
        temp_energy_feed = _diag_vec(diag, "temp_energy_feed_ref_term_BTUps_tray", N)
        temp_energy_duty = _diag_vec(diag, "temp_energy_duty_term_BTUps_tray", N)
        temp_energy_V_out = _diag_vec(diag, "temp_energy_V_out_term_BTUps_tray", N)
        temp_energy_P_used = _diag_vec(diag, "temp_energy_P_used_psia_tray", N)
        temp_energy_h_ref = _diag_vec(diag, "temp_energy_hL_out_BTU_per_lbmol_tray", N)
        vflow_energy_resid = _diag_vec(diag, "vflow_energy_resid_after_used_BTUps", N)
        vflow_energy_calc = _diag_vec(diag, "vflow_energy_calc_lbmolph", N)
        vflow_energy_used = _diag_vec(diag, "vflow_energy_used_lbmolph", N)
        vflow_energy_clamped = _diag_vec(diag, "vflow_energy_clamped", N)
        vflow_energy_L_in = _diag_vec(diag, "vflow_energy_L_in_term_BTUps", N)
        vflow_energy_V_in = _diag_vec(diag, "vflow_energy_V_in_term_BTUps", N)
        vflow_energy_feed = _diag_vec(diag, "vflow_energy_feed_ref_term_BTUps", N)
        vflow_energy_duty = _diag_vec(diag, "vflow_energy_duty_term_BTUps", N)
        vflow_energy_target = _diag_vec(diag, "vflow_energy_dE_target_BTUps", N)
        vflow_energy_P_used = _diag_vec(diag, "vflow_energy_P_used_psia", N)

        rows: List[Dict[str, Any]] = []
        for i in range(N):
            dM_total_i = float(dML_model[i] + dMV_model[i])
            ref_adjusted_i = float(model_total[i] - float(temp_energy_h_ref[i]) * dM_total_i)
            rows.append(
                {
                    "stage_1based": int(i + 1),
                    "dE_model_total_BTUps": float(model_total[i]),
                    "dML_model_lbmolps": float(dML_model[i]),
                    "dMV_model_lbmolps": float(dMV_model[i]),
                    "dM_total_model_lbmolps": dM_total_i,
                    "dEL_model_BTUps": float(dEL_model[i]),
                    "dEV_model_BTUps": float(dEV_model[i]),
                    "energy_balance_resid_diag_BTUps": float(energy_resid_diag[i]),
                    "dEL_in_BTUps": float(dEL_in[i]),
                    "dEL_out_BTUps": float(dEL_out[i]),
                    "dEL_duty_BTUps": float(dEL_duty[i]),
                    "dEV_in_BTUps": float(dEV_in[i]),
                    "dEV_out_BTUps": float(dEV_out[i]),
                    "dEV_duty_BTUps": float(dEV_duty[i]),
                    "model_term_sum_BTUps": float(model_term_sum[i]),
                    "closure_error_BTUps": float(closure_err[i]),
                    "feed_enthalpy_est_BTUps": float(feed_q[i]),
                    "feed_enthalpy_diag_BTUps": float(q_feed_diag[i]),
                    "dE_model_plus_feed_BTUps": float(model_total[i] + feed_q[i]),
                    "energy_state_ref_adjusted_BTUps": ref_adjusted_i,
                    "energy_state_ref_adjusted_minus_temp_BTUps": float(ref_adjusted_i - temp_energy_dE[i]),
                    "temp_energy_dE_BTUps": float(temp_energy_dE[i]),
                    "temp_energy_minus_energy_state_BTUps": float(temp_energy_dE[i] - model_total[i]),
                    "temp_energy_L_in_ref_BTUps": float(temp_energy_L_in[i]),
                    "temp_energy_V_in_ref_BTUps": float(temp_energy_V_in[i]),
                    "temp_energy_feed_ref_BTUps": float(temp_energy_feed[i]),
                    "temp_energy_duty_BTUps": float(temp_energy_duty[i]),
                    "temp_energy_V_out_ref_BTUps": float(temp_energy_V_out[i]),
                    "temp_energy_P_used_psia": float(temp_energy_P_used[i]),
                    "vflow_energy_resid_after_used_BTUps": float(vflow_energy_resid[i]),
                    "vflow_energy_calc_lbmolph": float(vflow_energy_calc[i]),
                    "vflow_energy_used_lbmolph": float(vflow_energy_used[i]),
                    "vflow_energy_calc_minus_used_lbmolph": float(vflow_energy_calc[i] - vflow_energy_used[i]),
                    "vflow_energy_clamped": float(vflow_energy_clamped[i]),
                    "vflow_energy_L_in_ref_BTUps": float(vflow_energy_L_in[i]),
                    "vflow_energy_V_in_ref_BTUps": float(vflow_energy_V_in[i]),
                    "vflow_energy_feed_ref_BTUps": float(vflow_energy_feed[i]),
                    "vflow_energy_duty_BTUps": float(vflow_energy_duty[i]),
                    "vflow_energy_dE_target_BTUps": float(vflow_energy_target[i]),
                    "vflow_energy_P_used_psia": float(vflow_energy_P_used[i]),
                    "L_out_lbmolph": float(L_out[i] * 3600.0),
                    "V_out_lbmolph": float(V_out[i] * 3600.0),
                    "ML_lbmol": float(ML[i]),
                    "MV_lbmol": float(MV[i]),
                    "hL_BTU_per_lbmol": float(hL[i]),
                    "hV_BTU_per_lbmol": float(hV[i]),
                    "dT_tray_F_per_s": float(dT[i]),
                }
            )

        if args.output_csv:
            out_csv = _resolve_path(project_root, str(args.output_csv))
        else:
            out_csv = project_root / "logs" / f"stage_energy_breakdown_{_timestamp_tag()}.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        fields = list(rows[0].keys()) if rows else []
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow(r)

        abs_idx = np.argsort(-np.abs(model_total))
        top_lines: List[str] = []
        for j in abs_idx[: min(10, N)]:
            top_lines.append(
                f"  stage {int(j + 1):2d}: dE={float(model_total[j]): .3f} BTU/s, "
                f"(L={float(dEL_in[j] + dEL_out[j]): .3f}, "
                f"V={float(dEV_in[j] + dEV_out[j]): .3f}, "
                f"duty={float(dEL_duty[j] + dEV_duty[j]): .3f}, "
                f"feed_est={float(feed_q[j]): .3f})"
            )
        temp_gap = temp_energy_dE - model_total
        dM_total_model = dML_model + dMV_model
        energy_state_ref_adjusted = model_total - temp_energy_h_ref * dM_total_model
        ref_adjusted_gap = energy_state_ref_adjusted - temp_energy_dE
        temp_gap_idx = np.argsort(-np.abs(temp_gap))
        temp_gap_lines: List[str] = []
        for j in temp_gap_idx[: min(10, N)]:
            temp_gap_lines.append(
                f"  stage {int(j + 1):2d}: temp_minus_energy_state={float(temp_gap[j]): .3f} BTU/s, "
                f"temp_dE={float(temp_energy_dE[j]): .3f}, energy_state_dE={float(model_total[j]): .3f}"
            )
        ref_gap_idx = np.argsort(-np.abs(ref_adjusted_gap))
        ref_gap_lines: List[str] = []
        for j in ref_gap_idx[: min(10, N)]:
            ref_gap_lines.append(
                f"  stage {int(j + 1):2d}: ref_adjusted_minus_temp={float(ref_adjusted_gap[j]): .3f} BTU/s, "
                f"ref_adjusted={float(energy_state_ref_adjusted[j]): .3f}, "
                f"temp_dE={float(temp_energy_dE[j]): .3f}, dM={float(dM_total_model[j]): .6f} lbmol/s"
            )
        vflow_resid_idx = np.argsort(-np.abs(vflow_energy_resid))
        vflow_lines: List[str] = []
        for j in vflow_resid_idx[: min(10, N)]:
            vflow_lines.append(
                f"  stage {int(j + 1):2d}: vflow_resid={float(vflow_energy_resid[j]): .3f} BTU/s, "
                f"V_calc-used={float(vflow_energy_calc[j] - vflow_energy_used[j]): .3f} lbmol/h, "
                f"clamped={float(vflow_energy_clamped[j]):.0f}"
            )

        if args.output_summary:
            out_txt = _resolve_path(project_root, str(args.output_summary))
        else:
            out_txt = project_root / "logs" / f"stage_energy_summary_{_timestamp_tag()}.txt"
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        summary_lines = [
            "Stage Energy Residual Breakdown Report",
            f"excel: {excel_path}",
            f"initial_state_source: {initial_state_source}",
            f"native_checkpoint: {'' if checkpoint_path is None else checkpoint_path}",
            f"checkpoint_restored_memory_keys: {', '.join(checkpoint_info.get('restored_memory_keys', []))}",
            f"thermo_mode: {str(args.thermo_mode).lower()}",
            f"runtime_mode: {str(args.runtime_mode)}",
            f"scenario: {str(args.scenario)}",
            f"pressure_model: {getattr(inputs, 'pressure_model', None)}",
            f"vapor_flow_model: {getattr(inputs, 'vapor_flow_model', None)}",
            f"flash_feed_at_stage_conditions: {bool(getattr(inputs, 'flash_feed_at_stage_conditions', True))}",
            f"equilibrium_relaxation: {bool(getattr(inputs, 'equilibrium_relaxation', False))}",
            f"vapor_flow_zero_temperature_target: {bool(args.vapor_flow_zero_temperature_target)}",
            f"vapor_flow_relaxation_sec: {getattr(inputs, 'vapor_flow_relaxation_sec', None)}",
            f"include_temperature: {bool(args.include_temperature)}",
            f"include_energy: True",
            "",
            f"feed_stage_1based: {'' if feed_stage0 is None else int(feed_stage0 + 1)}",
            f"feed_total_lbmolph: {float(np.sum(Fk_L + Fk_V) * 3600.0):.6f}",
            f"Q_cond_used_BTUph: {float(Qc_BTUph) if np.isfinite(Qc_BTUph) else float('nan')}",
            f"Q_reb_used_BTUph: {float(Qr_BTUph) if np.isfinite(Qr_BTUph) else float('nan')}",
            "",
            f"max_abs_dE_model_BTUps: {float(np.nanmax(np.abs(model_total))):.6f}",
            f"rms_dE_model_BTUps: {float(np.sqrt(np.nanmean(np.square(model_total)))):.6f}",
            f"worst_stage_1based: {int(np.nanargmax(np.abs(model_total)) + 1)}",
            f"max_abs_feed_enthalpy_est_BTUps: {float(np.nanmax(np.abs(feed_q))):.6f}",
            f"worst_feed_stage_1based: {int(np.nanargmax(np.abs(feed_q)) + 1)}",
            f"max_abs_closure_error_BTUps: {float(np.nanmax(np.abs(closure_err))):.6g}",
            f"max_abs_temp_minus_energy_state_BTUps: {float(np.nanmax(np.abs(temp_gap))):.6f}",
            f"max_abs_energy_state_ref_adjusted_minus_temp_BTUps: {float(np.nanmax(np.abs(ref_adjusted_gap))):.6f}",
            f"max_abs_vflow_energy_resid_after_used_BTUps: {float(np.nanmax(np.abs(vflow_energy_resid))):.6f}",
            "",
            "Top stages by |dE_model|:",
            *top_lines,
            "",
            "Top stages by |temperature-state minus energy-state dE|:",
            *temp_gap_lines,
            "",
            "Top stages by |reference-adjusted energy-state minus temperature-state dE|:",
            *ref_gap_lines,
            "",
            "Top stages by |vflow energy residual after used V|:",
            *vflow_lines,
            "",
            f"csv: {out_csv}",
        ]
        with out_txt.open("w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(summary_lines) + "\n")

        print("\n".join(summary_lines))
        print(f"summary: {out_txt}")
        return 0
    finally:
        if provider is not None and hasattr(provider, "close"):
            try:
                provider.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
