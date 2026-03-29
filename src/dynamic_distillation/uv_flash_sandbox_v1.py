"""
uv_flash_sandbox_v1.py

Isolated UV-flash prototype runner for the mini8 sandbox.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from dynamic_distillation.column_rhs_v1 import _bubble_point_T_F, _vapor_outflow_hydraulic_lbmolps
from dynamic_distillation.column_spec_builder_v1 import ColumnSpec, StreamSpecNormalized, build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.stage_hydraulics_francis_v1 import compute_francis_weir_liquid_outflow
from dynamic_distillation.stage_thermo_v1 import flash_TP_full_F_psia
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1
from dynamic_distillation.thermo_surrogate_v1 import TabularThermoProviderV1
from dynamic_distillation.thermo_table_pool_v1 import ParallelTabularThermoProviderV1
from dynamic_distillation.uv_flash_stage_v1 import (
    UvFlashStageGuess,
    UvFlashStageResult,
    UvStageReferenceState,
    _internal_energy_from_enthalpy_BTU_lbmol,
    _provider_vapor_z_factor,
    _vapor_molar_volume_ft3_lbmol,
    initialize_uv_stage_state_from_tp_profile,
    solve_uv_flash_stage,
)


def _timestamp_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _normalize_comp(z: Sequence[float]) -> np.ndarray:
    arr = np.asarray(z, dtype=float).reshape((-1,))
    s = float(np.sum(arr))
    if (not np.isfinite(s)) or s <= 0.0:
        raise ValueError("composition sum must be > 0")
    return arr / s


def _label_for_component(name: str) -> str:
    return "".join(ch for ch in str(name) if ch.isalnum()).lower()


def _float_or_nan(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return float("nan")
    return out if np.isfinite(out) else float("nan")


def _time_key(value: Any) -> float:
    return round(_float_or_nan(value), 9)


def _nanmax_abs_or_nan(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size <= 0:
        return float("nan")
    if not np.any(np.isfinite(arr)):
        return float("nan")
    return float(np.nanmax(np.abs(arr)))


def _stream_comp_vector(col: ColumnSpec, stream: StreamSpecNormalized) -> np.ndarray:
    comp_dict = stream.component_molar_flows_lbmolph or {}
    vals = []
    for cname in col.components_excel:
        val = comp_dict.get(cname)
        if val is None:
            for key, raw in comp_dict.items():
                if str(key).strip().lower() == str(cname).strip().lower():
                    val = raw
                    break
        vals.append(0.0 if val is None else float(val))
    arr = np.asarray(vals, dtype=float)
    if np.sum(arr) <= 0.0:
        total = float(stream.total_molar_flow_lbmolph or 0.0)
        if total > 0.0:
            return np.full(col.n_components, total / float(col.n_components), dtype=float)
        raise ValueError(f"stream '{stream.name}' has no usable component molar flows")
    return arr


@dataclass(frozen=True)
class _StageBoundaryState:
    T_F: float
    P_psia: float
    x_liq: np.ndarray
    hL_BTU_lbmol: float
    y_vap: np.ndarray
    hV_BTU_lbmol: float


@dataclass(frozen=True)
class _LiquidNodeReference:
    stage_label: int
    node_type: str
    T_F: float
    P_psia: float
    initial_component_holdup_lbmol: np.ndarray
    initial_hL_BTU_lbmol: float
    initial_total_internal_energy_BTU: float = float("nan")


@dataclass(frozen=True)
class _LiquidNodeState:
    stage_label: int
    node_type: str
    T_F: float
    P_psia: float
    total_component_holdup_lbmol: np.ndarray
    total_moles_lbmol: float
    x_liq: np.ndarray
    hL_BTU_lbmol: float
    u_total_BTU: float = float("nan")


@dataclass(frozen=True)
class _FeedTerm:
    stage_active_idx: int
    component_rates_lbmolps: np.ndarray
    enthalpy_rate_BTUps: float


@dataclass(frozen=True)
class _VaporFlowClosure:
    used_lbmolps: np.ndarray
    raw_lbmolps: np.ndarray
    dp_psia: np.ndarray
    h_ow_ft: np.ndarray
    clamped_flag: np.ndarray


@dataclass(frozen=True)
class _LiquidFlowClosure:
    used_lbmolps: np.ndarray
    raw_lbmolph: np.ndarray
    h_ow_ft: np.ndarray
    clamped_flag: np.ndarray


@dataclass(frozen=True)
class UvMini8PrototypeSpec:
    excel_path: str
    component_names: List[str]
    n_total_stages: int
    active_stage0: np.ndarray
    active_stage1: np.ndarray
    fixed_total_volume_ft3: np.ndarray
    initial_total_component_holdup_lbmol: np.ndarray
    initial_total_internal_energy_BTU: np.ndarray
    initial_guesses: List[UvFlashStageGuess]
    top_stage_boundary: _StageBoundaryState
    bottom_stage_boundary: _StageBoundaryState
    top_node_reference: _LiquidNodeReference
    bottom_node_reference: _LiquidNodeReference
    feed_term: Optional[_FeedTerm]
    L_lbmolps: np.ndarray
    V_lbmolps: np.ndarray
    distillate_total_lbmolps: float
    bottoms_total_lbmolps: float
    dry_tray_K: float
    conductance_nominal_hi_ratio: float
    liquid_hydraulic_tau_sec: float
    geometry: Any
    component_mw_lbm_per_lbmol: Optional[np.ndarray]
    initial_liquid_moles_lbmol: Optional[np.ndarray] = None
    q_stage_BTUps: Optional[np.ndarray] = None
    condenser_duty_BTUps: float = 0.0
    condenser_to_top_nominal_lbmolps: float = 0.0
    condenser_to_top_tau_sec: float = 1.0
    reboiler_to_bottom_nominal_lbmolps: float = 0.0
    reboiler_to_bottom_tau_sec: float = 1.0
    fixed_beta_per_stage: Optional[np.ndarray] = None
    condenser_is_total: bool = False
    condenser_pressure_drop_psi: float = 0.0
    reboiler_is_partial: bool = True
    reboiler_pressure_rise_psi: float = 0.0


def _spec_float(specs: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key not in specs:
            continue
        try:
            val = float(specs[key])
        except Exception:
            continue
        if np.isfinite(val):
            return float(val)
    return None


def _stream_or_stage_tp(col: ColumnSpec, stream_name: str, fallback_stage0: int) -> tuple[float, float]:
    stream = col.streams.get(stream_name)
    T_F = float(col.T_f[fallback_stage0])
    P_psia = float(col.P_psia[fallback_stage0])
    if stream is not None:
        if stream.temperature_f is not None:
            T_F = float(stream.temperature_f)
        if stream.pressure_psia is not None:
            P_psia = float(stream.pressure_psia)
    return float(T_F), float(P_psia)


def _stream_total_lbmolps(col: ColumnSpec, stream_name: str, fallback_lbmolps: float) -> float:
    stream = col.streams.get(stream_name)
    if stream is None or stream.total_molar_flow_lbmolph is None:
        return float(fallback_lbmolps)
    try:
        total = float(stream.total_molar_flow_lbmolph) / 3600.0
    except Exception:
        return float(fallback_lbmolps)
    if not np.isfinite(total) or total < 0.0:
        return float(fallback_lbmolps)
    return float(total)


def _stage_boundary_state(provider: Any, col: ColumnSpec, stage0: int) -> _StageBoundaryState:
    x_liq = _normalize_comp(col.x0[stage0, :])
    y_vap = _normalize_comp(col.y0[stage0, :])
    T_F = float(col.T_f[stage0])
    P_psia = float(col.P_psia[stage0])
    hL = provider.phase_enthalpy_BTU_lbmol("liquid", T_F, P_psia, x_liq.tolist())
    hV = provider.phase_enthalpy_BTU_lbmol("vapor", T_F, P_psia, y_vap.tolist())
    return _StageBoundaryState(
        T_F=float(T_F),
        P_psia=float(P_psia),
        x_liq=x_liq.copy(),
        hL_BTU_lbmol=float(hL),
        y_vap=y_vap.copy(),
        hV_BTU_lbmol=float(hV),
    )


def _liquid_node_reference(
    *,
    provider: Any,
    col: ColumnSpec,
    stream_name: str,
    fallback_stage0: int,
    stage_label: int,
    node_type: str,
    holdup_keys: Sequence[str],
    fallback_comp: Sequence[float],
) -> _LiquidNodeReference:
    specs = getattr(col, "specs_raw", {}) or {}
    total_holdup = None
    for key in holdup_keys:
        total_holdup = _spec_float(specs, key)
        if total_holdup is not None:
            break
    if total_holdup is None or total_holdup < 0.0:
        raise ValueError(f"missing holdup spec for {node_type}")

    stream = col.streams.get(stream_name)
    if stream is not None:
        base_comp = _stream_comp_vector(col, stream)
    else:
        base_comp = np.asarray(fallback_comp, dtype=float).reshape((-1,))
    x_liq = _normalize_comp(base_comp)
    T_F, P_psia = _stream_or_stage_tp(col, stream_name, fallback_stage0)
    hL = provider.phase_enthalpy_BTU_lbmol("liquid", T_F, P_psia, x_liq.tolist())
    rhoL = provider.liquid_density_lbmol_ft3(T_F, P_psia, x_liq.tolist())
    vL = 0.0 if rhoL is None else 1.0 / max(float(rhoL), 1.0e-12)
    uL = _internal_energy_from_enthalpy_BTU_lbmol(float(hL), float(P_psia), float(vL))
    return _LiquidNodeReference(
        stage_label=int(stage_label),
        node_type=str(node_type),
        T_F=float(T_F),
        P_psia=float(P_psia),
        initial_component_holdup_lbmol=float(total_holdup) * x_liq,
        initial_hL_BTU_lbmol=float(hL),
        initial_total_internal_energy_BTU=float(total_holdup) * float(uL),
    )


def _make_feed_term(provider: Any, col: ColumnSpec, active_stage0: np.ndarray) -> Optional[_FeedTerm]:
    feed = col.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        return None

    feed_stage0 = int(feed.stage_1based) - 1
    matches = np.where(active_stage0 == feed_stage0)[0]
    if matches.size <= 0:
        return None
    active_idx = int(matches[0])

    comp_rates_lbmolph = _stream_comp_vector(col, feed)
    comp_rates_lbmolps = np.asarray(comp_rates_lbmolph, dtype=float) / 3600.0
    z_feed = _normalize_comp(comp_rates_lbmolph)
    T_feed = float(feed.temperature_f if feed.temperature_f is not None else col.T_f[feed_stage0])
    P_feed = float(feed.pressure_psia if feed.pressure_psia is not None else col.P_psia[feed_stage0])
    vap_frac = 0.0 if feed.vapor_fraction is None else float(feed.vapor_fraction)
    vap_frac = float(np.clip(vap_frac, 0.0, 1.0))
    hL = provider.phase_enthalpy_BTU_lbmol("liquid", T_feed, P_feed, z_feed.tolist())
    hV = provider.phase_enthalpy_BTU_lbmol("vapor", T_feed, P_feed, z_feed.tolist())
    h_feed = (1.0 - vap_frac) * float(hL) + vap_frac * float(hV)
    enthalpy_rate_BTUps = float(np.sum(comp_rates_lbmolps)) * float(h_feed)
    return _FeedTerm(
        stage_active_idx=active_idx,
        component_rates_lbmolps=comp_rates_lbmolps.copy(),
        enthalpy_rate_BTUps=float(enthalpy_rate_BTUps),
    )


def build_mini8_uv_prototype_spec(
    *,
    excel_path: str,
    provider: Any,
    conductance_nominal_hi_ratio: Optional[float] = None,
) -> UvMini8PrototypeSpec:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)
    if int(col.n_stages) < 4:
        raise ValueError("UV mini-column prototype requires at least 4 stages")
    if col.M_L_lbmol is None:
        raise ValueError("mini8 UV prototype requires Liquid Holdup (lbmol) in Initial Conditions")
    if col.geometry is None or col.geometry.vapor_volume_ft3_per_stage is None:
        raise ValueError("mini8 UV prototype requires stage geometry with vapor volume")

    condenser_type = str(getattr(getattr(col, "duties", None), "condenser_type", "") or "").strip().lower()
    total_condenser = ("total" in condenser_type) if condenser_type else True
    partial_reboiler = True
    active_start = 1 if total_condenser else 0
    active_stop = int(col.n_stages) - 1 if partial_reboiler else int(col.n_stages)
    active_stage0 = np.arange(active_start, active_stop, dtype=int)
    distillate_total_lbmolps = _stream_total_lbmolps(
        col,
        "Distillate",
        fallback_lbmolps=max((float(col.V_lbmolph[1]) - float(col.L_lbmolph[0])) / 3600.0, 0.0),
    )
    bottoms_total_lbmolps = _stream_total_lbmolps(
        col,
        "Bottom",
        fallback_lbmolps=max(float(col.streams.get("Bottom").total_molar_flow_lbmolph or 0.0) / 3600.0, 0.0)
        if col.streams.get("Bottom") is not None
        else 0.0,
    )
    top_stage_init_liq = max(float(col.L_lbmolph[0]) / 3600.0 + float(distillate_total_lbmolps), 1.0)
    bottom_stage_init_liq = max(float(bottoms_total_lbmolps), 1.0)
    refs: List[UvStageReferenceState] = []
    guesses: List[UvFlashStageGuess] = []
    for stage0 in active_stage0:
        liquid_holdup_lbmol = float(col.M_L_lbmol[stage0])
        if liquid_holdup_lbmol <= 1.0e-12:
            if stage0 == 0:
                liquid_holdup_lbmol = float(top_stage_init_liq)
            elif stage0 == (int(col.n_stages) - 1):
                liquid_holdup_lbmol = float(bottom_stage_init_liq)
            else:
                liquid_holdup_lbmol = 1.0
        ref = initialize_uv_stage_state_from_tp_profile(
            provider,
            T_F=float(col.T_f[stage0]),
            P_psia=float(col.P_psia[stage0]),
            x_liq=col.x0[stage0, :],
            y_vap=col.y0[stage0, :],
            liquid_holdup_lbmol=float(liquid_holdup_lbmol),
            vapor_volume_ft3=(
                0.0
                if (stage0 == 0 and total_condenser)
                else float(col.geometry.vapor_volume_ft3_per_stage[stage0])
            ),
        )
        refs.append(ref)
        guesses.append(ref.initial_guess)

    specs = getattr(col, "specs_raw", {}) or {}
    nominal_hi = conductance_nominal_hi_ratio
    if nominal_hi is None:
        nominal_hi = _spec_float(
            specs,
            "Conductance Vapor Flow Nominal Hi Ratio",
            "Conductance Vflow Nominal Hi Ratio",
        )
    if nominal_hi is None or (not np.isfinite(float(nominal_hi))) or float(nominal_hi) <= 0.0:
        nominal_hi = 1.25

    dry_tray_k = _spec_float(specs, "Dry Tray K")
    if dry_tray_k is None or (not np.isfinite(float(dry_tray_k))) or float(dry_tray_k) <= 0.0:
        dry_tray_k = 1.0
    liquid_hydraulic_tau_sec = _spec_float(
        specs,
        "Hydraulic Time Constant (sec)",
        "Stage time constant [tau] (sec)",
    )
    if liquid_hydraulic_tau_sec is None or (not np.isfinite(float(liquid_hydraulic_tau_sec))) or float(liquid_hydraulic_tau_sec) <= 0.0:
        liquid_hydraulic_tau_sec = float(getattr(col, "tau_eq_sec", 10.0) or 10.0)
    if (not np.isfinite(float(liquid_hydraulic_tau_sec))) or float(liquid_hydraulic_tau_sec) <= 0.0:
        liquid_hydraulic_tau_sec = 10.0

    q_stage = np.zeros(int(col.n_stages), dtype=float)
    q_cond_btu_per_h = getattr(getattr(col, "duties", None), "q_cond_btu_per_h", None)
    q_reb_btu_per_h = getattr(getattr(col, "duties", None), "q_reb_btu_per_h", None)
    condenser_duty_BTUps = 0.0
    if q_cond_btu_per_h is not None and np.isfinite(float(q_cond_btu_per_h)):
        condenser_duty_BTUps = float(q_cond_btu_per_h) / 3600.0
    if (not total_condenser) and q_cond_btu_per_h is not None and np.isfinite(float(q_cond_btu_per_h)):
        q_stage[0] = float(q_cond_btu_per_h) / 3600.0
    if q_reb_btu_per_h is not None and np.isfinite(float(q_reb_btu_per_h)):
        q_stage[-1] = float(q_reb_btu_per_h) / 3600.0

    condenser_to_top_nominal_lbmolps = max(float(col.L_lbmolph[0]) / 3600.0, 1.0e-9)
    reboiler_to_bottom_nominal_lbmolps = max(
        _stream_total_lbmolps(
            col,
            "Bottom",
            fallback_lbmolps=max(float(col.streams.get("Bottom").total_molar_flow_lbmolph or 0.0) / 3600.0, 0.0)
            if col.streams.get("Bottom") is not None
            else 0.0,
        ),
        1.0e-9,
    )
    condenser_to_top_tau_sec = 1.0
    fixed_beta_per_stage = np.full(int(col.n_stages), np.nan, dtype=float)
    condenser_pressure_drop_psi = max(float(col.P_psia[1] - col.P_psia[0]), 0.0) if int(col.n_stages) > 1 else 0.0
    reboiler_pressure_rise_psi = (
        max(float(col.P_psia[-1] - col.P_psia[-2]), 0.0)
        if int(col.n_stages) > 1
        else 0.0
    )

    top_node_reference = _liquid_node_reference(
        provider=provider,
        col=col,
        stream_name="Distillate",
        fallback_stage0=0,
        stage_label=0,
        node_type="distillate_drum",
        holdup_keys=("Top Accumulator Holdup (lbmol)", "Top Drum Holdup (lbmol)"),
        fallback_comp=col.x0[0, :],
    )
    bottom_node_reference = _liquid_node_reference(
        provider=provider,
        col=col,
        stream_name="Bottom",
        fallback_stage0=int(col.n_stages) - 1,
        stage_label=int(col.n_stages) + 1,
        node_type="bottoms_sump",
        holdup_keys=("Bottom Holdup (lbmol)", "Bottom Sump Holdup (lbmol)"),
        fallback_comp=col.x0[int(col.n_stages) - 1, :],
    )
    reboiler_to_bottom_tau_sec = max(
        float(np.sum(bottom_node_reference.initial_component_holdup_lbmol)) / reboiler_to_bottom_nominal_lbmolps,
        1.0,
    )

    mw_components = None
    if hasattr(provider, "component_mw_lbm_per_lbmol"):
        try:
            mw_try = provider.component_mw_lbm_per_lbmol()
            if mw_try is not None:
                mw_arr = np.asarray(mw_try, dtype=float).reshape((int(col.n_components),))
                if np.all(np.isfinite(mw_arr)) and np.all(mw_arr > 0.0):
                    mw_components = mw_arr.copy()
        except Exception:
            mw_components = None

    return UvMini8PrototypeSpec(
        excel_path=str(excel_path),
        component_names=list(col.components_excel),
        n_total_stages=int(col.n_stages),
        active_stage0=active_stage0.copy(),
        active_stage1=(active_stage0 + 1).copy(),
        fixed_total_volume_ft3=np.asarray([ref.total_volume_ft3 for ref in refs], dtype=float),
        initial_total_component_holdup_lbmol=np.asarray(
            [ref.total_component_holdup_lbmol for ref in refs],
            dtype=float,
        ),
        initial_total_internal_energy_BTU=np.asarray(
            [ref.total_internal_energy_BTU for ref in refs],
            dtype=float,
        ),
        initial_guesses=list(guesses),
        top_stage_boundary=_stage_boundary_state(provider, col, stage0=0),
        bottom_stage_boundary=_stage_boundary_state(provider, col, stage0=int(col.n_stages) - 1),
        top_node_reference=top_node_reference,
        bottom_node_reference=bottom_node_reference,
        feed_term=_make_feed_term(provider, col, active_stage0),
        L_lbmolps=np.asarray(col.L_lbmolph, dtype=float) / 3600.0,
        V_lbmolps=np.asarray(col.V_lbmolph, dtype=float) / 3600.0,
        distillate_total_lbmolps=float(distillate_total_lbmolps),
        bottoms_total_lbmolps=float(bottoms_total_lbmolps),
        dry_tray_K=float(dry_tray_k),
        conductance_nominal_hi_ratio=float(nominal_hi),
        liquid_hydraulic_tau_sec=float(liquid_hydraulic_tau_sec),
        geometry=col.geometry,
        component_mw_lbm_per_lbmol=mw_components,
        initial_liquid_moles_lbmol=np.asarray([ref.liquid_moles_lbmol for ref in refs], dtype=float),
        q_stage_BTUps=q_stage.copy(),
        condenser_duty_BTUps=float(condenser_duty_BTUps),
        condenser_to_top_nominal_lbmolps=float(condenser_to_top_nominal_lbmolps),
        condenser_to_top_tau_sec=float(condenser_to_top_tau_sec),
        reboiler_to_bottom_nominal_lbmolps=float(reboiler_to_bottom_nominal_lbmolps),
        reboiler_to_bottom_tau_sec=float(reboiler_to_bottom_tau_sec),
        fixed_beta_per_stage=fixed_beta_per_stage.copy(),
        condenser_is_total=bool(total_condenser),
        condenser_pressure_drop_psi=float(condenser_pressure_drop_psi),
        reboiler_is_partial=bool(partial_reboiler),
        reboiler_pressure_rise_psi=float(reboiler_pressure_rise_psi),
    )


def _pack_state(
    n_total_lbmol: np.ndarray,
    u_total_BTU: np.ndarray,
    top_liquid_lbmol: np.ndarray,
    bottom_liquid_lbmol: np.ndarray,
    top_u_total_BTU: float,
    bottom_u_total_BTU: float,
) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(n_total_lbmol, dtype=float).reshape((-1,)),
            np.asarray(u_total_BTU, dtype=float).reshape((-1,)),
            np.asarray(top_liquid_lbmol, dtype=float).reshape((-1,)),
            np.asarray(bottom_liquid_lbmol, dtype=float).reshape((-1,)),
            np.asarray([top_u_total_BTU], dtype=float).reshape((-1,)),
            np.asarray([bottom_u_total_BTU], dtype=float).reshape((-1,)),
        ],
        axis=0,
    )


def _unpack_state(
    y: np.ndarray,
    *,
    n_active: int,
    n_components: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float]:
    y_arr = np.asarray(y, dtype=float).reshape((-1,))
    n_comp_states = int(n_active) * int(n_components)
    expected = n_comp_states + int(n_active) + 2 * int(n_components) + 2
    if y_arr.size != expected:
        raise ValueError("state size mismatch for UV mini8 prototype")
    idx = 0
    n_total = y_arr[idx : idx + n_comp_states].reshape((int(n_active), int(n_components))).copy()
    idx += n_comp_states
    u_total = y_arr[idx : idx + int(n_active)].reshape((int(n_active),)).copy()
    idx += int(n_active)
    top_liquid = y_arr[idx : idx + int(n_components)].reshape((int(n_components),)).copy()
    idx += int(n_components)
    bottom_liquid = y_arr[idx : idx + int(n_components)].reshape((int(n_components),)).copy()
    idx += int(n_components)
    top_u_total = float(y_arr[idx])
    idx += 1
    bottom_u_total = float(y_arr[idx])
    return n_total, u_total, top_liquid, bottom_liquid, top_u_total, bottom_u_total


def _evaluate_stage_results(
    *,
    provider: Any,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    seeds: Sequence[UvFlashStageGuess],
) -> List[UvFlashStageResult]:
    n_active = int(spec.active_stage0.size)
    n_total, u_total, _top_liquid, _bottom_liquid, _top_u_total, _bottom_u_total = _unpack_state(
        y,
        n_active=n_active,
        n_components=len(spec.component_names),
    )
    out: List[UvFlashStageResult] = []
    for idx in range(0, n_active):
        n_stage = np.asarray(n_total[idx, :], dtype=float)
        n_stage = np.where(np.isfinite(n_stage), n_stage, 0.0)
        n_stage = np.clip(n_stage, 1.0e-12, None)
        m_tot = float(np.sum(n_stage))
        z_stage = n_stage / m_tot
        u_spec = float(u_total[idx]) / max(m_tot, 1.0e-12)
        guess = seeds[idx] if idx < len(seeds) else None
        stage0 = int(spec.active_stage0[idx])
        beta_fixed = None
        beta_mode = "free"
        if spec.fixed_beta_per_stage is not None:
            try:
                beta_try = float(np.asarray(spec.fixed_beta_per_stage, dtype=float).reshape((int(spec.n_total_stages),))[stage0])
                if np.isfinite(beta_try):
                    beta_fixed = float(np.clip(beta_try, 0.0, 1.0))
                    beta_mode = "fixed"
            except Exception:
                beta_fixed = None
                beta_mode = "free"
        v_spec = float(spec.fixed_total_volume_ft3[idx]) / max(m_tot, 1.0e-12)
        if (
            beta_mode == "fixed"
            and beta_fixed is not None
            and abs(float(beta_fixed)) <= 1.0e-12
            and spec.initial_liquid_moles_lbmol is not None
        ):
            try:
                m_ref = float(np.asarray(spec.initial_liquid_moles_lbmol, dtype=float).reshape((int(spec.n_total_stages),))[stage0])
                if np.isfinite(m_ref) and m_ref > 1.0e-12:
                    v_spec = float(spec.fixed_total_volume_ft3[idx]) / float(m_ref)
            except Exception:
                pass
        res = solve_uv_flash_stage(
            provider,
            z_overall=z_stage,
            u_target_BTU_lbmol=u_spec,
            v_target_ft3_lbmol=v_spec,
            guess=guess,
            beta_mode=beta_mode,
            beta_fixed=beta_fixed,
        )
        out.append(res)
    return out


def _liquid_internal_energy_from_tp(
    provider: Any,
    *,
    T_F: float,
    P_psia: float,
    x_liq: np.ndarray,
) -> tuple[float, float]:
    hL = float(provider.phase_enthalpy_BTU_lbmol("liquid", float(T_F), float(P_psia), x_liq.tolist()))
    rhoL = provider.liquid_density_lbmol_ft3(float(T_F), float(P_psia), x_liq.tolist())
    vL = 0.0 if rhoL is None else 1.0 / max(float(rhoL), 1.0e-12)
    uL = _internal_energy_from_enthalpy_BTU_lbmol(float(hL), float(P_psia), float(vL))
    return float(uL), float(hL)


def _solve_liquid_node_temperature(
    *,
    provider: Any,
    ref: _LiquidNodeReference,
    x_liq: np.ndarray,
    u_target_BTU_lbmol: float,
) -> tuple[float, float, float]:
    t_lo = max(float(ref.T_F) - 80.0, 40.0)
    t_hi = min(float(ref.T_F) + 80.0, 400.0)
    T_now = float(np.clip(float(ref.T_F), t_lo, t_hi))
    best_T = float(T_now)
    best_u = float("nan")
    best_h = float(ref.initial_hL_BTU_lbmol)
    best_err = float("inf")
    for _ in range(12):
        try:
            u_now, h_now = _liquid_internal_energy_from_tp(
                provider,
                T_F=float(T_now),
                P_psia=float(ref.P_psia),
                x_liq=x_liq,
            )
        except Exception:
            break
        resid = float(u_now) - float(u_target_BTU_lbmol)
        if abs(resid) < best_err:
            best_err = abs(resid)
            best_T = float(T_now)
            best_u = float(u_now)
            best_h = float(h_now)
        if abs(resid) <= 1.0e-6:
            return float(T_now), float(u_now), float(h_now)
        cpL = None
        if hasattr(provider, "cp_liq_vap_btu_per_lbmolF"):
            try:
                cpL, _cpV = provider.cp_liq_vap_btu_per_lbmolF(float(T_now), float(ref.P_psia), x_liq.tolist())
            except Exception:
                cpL = None
        du_dT = float(cpL) if cpL is not None and np.isfinite(float(cpL)) and abs(float(cpL)) > 1.0e-6 else float("nan")
        if not np.isfinite(du_dT):
            try:
                u_hi, _h_hi = _liquid_internal_energy_from_tp(
                    provider,
                    T_F=float(min(T_now + 1.0, t_hi)),
                    P_psia=float(ref.P_psia),
                    x_liq=x_liq,
                )
                du_dT = float(u_hi - u_now) / max(min(T_now + 1.0, t_hi) - T_now, 1.0e-6)
            except Exception:
                du_dT = float("nan")
        if not np.isfinite(du_dT) or abs(du_dT) <= 1.0e-9:
            break
        step = float(resid) / float(du_dT)
        step = float(np.clip(step, -20.0, 20.0))
        T_new = float(np.clip(T_now - step, t_lo, t_hi))
        if abs(T_new - T_now) <= 1.0e-6:
            break
        T_now = float(T_new)
    if np.isfinite(best_err):
        return float(best_T), float(best_u), float(best_h)
    m_ref = max(float(np.sum(ref.initial_component_holdup_lbmol)), 1.0e-12)
    u_ref = float(ref.initial_total_internal_energy_BTU) / m_ref
    return float(ref.T_F), float(u_ref), float(ref.initial_hL_BTU_lbmol)


def _evaluate_liquid_node_state(
    *,
    provider: Any,
    ref: _LiquidNodeReference,
    holdup_lbmol: np.ndarray,
    u_total_BTU: float,
) -> _LiquidNodeState:
    holdup = np.asarray(holdup_lbmol, dtype=float).reshape((-1,))
    holdup = np.where(np.isfinite(holdup), holdup, 0.0)
    holdup = np.clip(holdup, 1.0e-12, None)
    total = float(np.sum(holdup))
    x_liq = holdup / max(total, 1.0e-12)
    u_spec = float(u_total_BTU) / max(total, 1.0e-12) if np.isfinite(float(u_total_BTU)) else float("nan")
    if np.isfinite(u_spec):
        T_F, uL, hL = _solve_liquid_node_temperature(
            provider=provider,
            ref=ref,
            x_liq=x_liq,
            u_target_BTU_lbmol=float(u_spec),
        )
        u_total = float(total) * float(uL)
    else:
        T_F = float(ref.T_F)
        try:
            uL, hL = _liquid_internal_energy_from_tp(provider, T_F=T_F, P_psia=float(ref.P_psia), x_liq=x_liq)
        except Exception:
            hL = float(ref.initial_hL_BTU_lbmol)
            uL = float(ref.initial_total_internal_energy_BTU) / max(float(np.sum(ref.initial_component_holdup_lbmol)), 1.0e-12)
        u_total = float(total) * float(uL)
    return _LiquidNodeState(
        stage_label=int(ref.stage_label),
        node_type=str(ref.node_type),
        T_F=float(T_F),
        P_psia=float(ref.P_psia),
        total_component_holdup_lbmol=holdup.copy(),
        total_moles_lbmol=float(total),
        x_liq=x_liq.copy(),
        hL_BTU_lbmol=float(hL),
        u_total_BTU=float(u_total),
    )


def _evaluate_total_condenser_state(
    *,
    provider: Any,
    spec: UvMini8PrototypeSpec,
    stage2_result: UvFlashStageResult,
    top_node: Optional[_LiquidNodeState] = None,
) -> UvFlashStageResult:
    p_cond = max(float(stage2_result.P_psia) - float(spec.condenser_pressure_drop_psi), 1.0)
    y_in = _normalize_comp(np.asarray(stage2_result.y, dtype=float))
    t_bub, fres = _bubble_point_T_F(
        thermo_provider=provider,
        P_psia=float(p_cond),
        x=y_in,
        T_guess_F=float(stage2_result.T_F),
    )
    x_cond = y_in.copy()
    if top_node is not None and np.isfinite(float(top_node.T_F)):
        t_cond = float(top_node.T_F)
    else:
        t_cond = float(spec.top_node_reference.T_F) if np.isfinite(float(spec.top_node_reference.T_F)) else float(t_bub)
    hL = provider.phase_enthalpy_BTU_lbmol("liquid", float(t_cond), float(p_cond), x_cond.tolist())
    if hL is None:
        hL = float(getattr(fres, "HL_BTU_lbmol"))
    hV = provider.phase_enthalpy_BTU_lbmol("vapor", float(t_cond), float(p_cond), y_in.tolist())
    if hV is None:
        hV = float(getattr(fres, "HV_BTU_lbmol"))
    rhoL = provider.liquid_density_lbmol_ft3(float(t_cond), float(p_cond), x_cond.tolist())
    if rhoL is None:
        raise RuntimeError("total condenser density lookup failed")
    vL = 1.0 / max(float(rhoL), 1.0e-12)
    z_vap = _provider_vapor_z_factor(
        provider,
        T_F=float(t_cond),
        P_psia=float(p_cond),
        y=y_in,
        flash_Z=getattr(fres, "Z", None),
    )
    vV = _vapor_molar_volume_ft3_lbmol(float(t_cond), float(p_cond), float(z_vap))
    uL = _internal_energy_from_enthalpy_BTU_lbmol(float(hL), float(p_cond), float(vL))
    uV = _internal_energy_from_enthalpy_BTU_lbmol(float(hV), float(p_cond), float(vV))
    K = np.asarray(y_in / np.maximum(x_cond, 1.0e-12), dtype=float).reshape((-1,))
    return UvFlashStageResult(
        T_F=float(t_cond),
        P_psia=float(p_cond),
        beta_vapor=0.0,
        x=x_cond.copy(),
        y=np.zeros_like(y_in),
        K=K.copy(),
        HL_BTU_lbmol=float(hL),
        HV_BTU_lbmol=float(hV),
        uL_BTU_lbmol=float(uL),
        uV_BTU_lbmol=float(uV),
        vL_ft3_lbmol=float(vL),
        vV_ft3_lbmol=float(vV),
        Z_vapor=float(z_vap),
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )


def _evaluate_partial_reboiler_state(
    *,
    provider: Any,
    spec: UvMini8PrototypeSpec,
    stage_above_result: UvFlashStageResult,
    bottom_node: _LiquidNodeState,
) -> UvFlashStageResult:
    p_reb = (
        float(bottom_node.P_psia)
        if np.isfinite(float(bottom_node.P_psia)) and float(bottom_node.P_psia) > 0.0
        else max(float(stage_above_result.P_psia) + float(spec.reboiler_pressure_rise_psi), 1.0)
    )
    t_reb = float(bottom_node.T_F) if np.isfinite(float(bottom_node.T_F)) else float(spec.bottom_node_reference.T_F)
    z_liq = _normalize_comp(np.asarray(bottom_node.x_liq, dtype=float))
    fres = flash_TP_full_F_psia(
        provider,
        float(t_reb),
        float(p_reb),
        z_liq.tolist(),
        n_components=z_liq.size,
    )
    x_reb = z_liq.copy()
    y_reb = _normalize_comp(np.asarray(fres.y, dtype=float)) if np.sum(np.asarray(fres.y, dtype=float)) > 0.0 else z_liq.copy()
    hL = provider.phase_enthalpy_BTU_lbmol("liquid", float(t_reb), float(p_reb), x_reb.tolist())
    if hL is None:
        hL = float(fres.HL_BTU_lbmol)
    hV = provider.phase_enthalpy_BTU_lbmol("vapor", float(t_reb), float(p_reb), y_reb.tolist())
    if hV is None:
        hV = float(fres.HV_BTU_lbmol)
    rhoL = provider.liquid_density_lbmol_ft3(float(t_reb), float(p_reb), x_reb.tolist())
    if rhoL is None:
        rhoL = provider.liquid_density_lbmol_ft3(
            float(spec.bottom_stage_boundary.T_F),
            float(spec.bottom_stage_boundary.P_psia),
            np.asarray(spec.bottom_stage_boundary.x_liq, dtype=float).tolist(),
        )
    if rhoL is None:
        raise RuntimeError("partial reboiler density lookup failed")
    vL = 1.0 / max(float(rhoL), 1.0e-12)
    z_vap = _provider_vapor_z_factor(
        provider,
        T_F=float(t_reb),
        P_psia=float(p_reb),
        y=y_reb,
        flash_Z=getattr(fres, "Z", None),
    )
    vV = _vapor_molar_volume_ft3_lbmol(float(t_reb), float(p_reb), float(z_vap))
    uL = _internal_energy_from_enthalpy_BTU_lbmol(float(hL), float(p_reb), float(vL))
    uV = _internal_energy_from_enthalpy_BTU_lbmol(float(hV), float(p_reb), float(vV))
    K = np.asarray(y_reb / np.maximum(x_reb, 1.0e-12), dtype=float).reshape((-1,))
    return UvFlashStageResult(
        T_F=float(t_reb),
        P_psia=float(p_reb),
        beta_vapor=0.0,
        x=x_reb.copy(),
        y=y_reb.copy(),
        K=K.copy(),
        HL_BTU_lbmol=float(hL),
        HV_BTU_lbmol=float(hV),
        uL_BTU_lbmol=float(uL),
        uV_BTU_lbmol=float(uV),
        vL_ft3_lbmol=float(vL),
        vV_ft3_lbmol=float(vV),
        Z_vapor=float(z_vap),
        residual_u_BTU_lbmol=0.0,
        residual_v_ft3_lbmol=0.0,
        residual_beta=0.0,
        converged=True,
        iterations=1,
    )


def _compute_liquid_flow_closure(
    *,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    stage_results: Sequence[UvFlashStageResult],
    l_prev_lbmolps: Optional[np.ndarray],
) -> _LiquidFlowClosure:
    N = int(spec.n_total_stages)
    geom = spec.geometry
    weir_h = getattr(geom, "weir_height_in_per_stage", None)
    weir_L = getattr(geom, "weir_length_ft_per_stage", None)
    active_area = getattr(geom, "active_area_ft2_per_stage", None)
    if weir_h is None or weir_L is None or active_area is None:
        raise ValueError("liquid hydraulic closure requires weir height, weir length, and active area geometry")
    c_fac = getattr(geom, "hydraulic_c_factor_per_stage", None)

    n_total, _u_total, _top_liquid, _bottom_liquid, _top_u_total, _bottom_u_total = _unpack_state(
        y,
        n_active=int(spec.active_stage0.size),
        n_components=len(spec.component_names),
    )

    ML_stage = np.zeros(N, dtype=float)
    liquid_vol_stage = np.zeros(N, dtype=float)
    rhoL_stage = np.full(N, np.nan, dtype=float)
    for idx, stage0 in enumerate(spec.active_stage0):
        res = stage_results[idx]
        total_stage = float(np.sum(n_total[idx, :]))
        liquid_moles = max(0.0, 1.0 - float(res.beta_vapor)) * total_stage
        ML_stage[stage0] = float(liquid_moles)
        rhoL_stage[stage0] = 1.0 / max(float(res.vL_ft3_lbmol), 1.0e-12)
        liquid_vol_stage[stage0] = float(liquid_moles) * float(res.vL_ft3_lbmol)

    hyd = compute_francis_weir_liquid_outflow(
        ML_lbmol=ML_stage,
        rhoL_lbmol_ft3=rhoL_stage,
        active_area_ft2=np.asarray(active_area, dtype=float).reshape((N,)),
        weir_height_in=np.asarray(weir_h, dtype=float).reshape((N,)),
        weir_length_ft=np.asarray(weir_L, dtype=float).reshape((N,)),
        c_multiplier=(
            None
            if c_fac is None
            else np.asarray(c_fac, dtype=float).reshape((N,))
        ),
    )

    L_raw_lbmolph = np.asarray(hyd.ML_lbmolph, dtype=float).reshape((N,))
    L_raw_lbmolph = np.where(~np.isfinite(L_raw_lbmolph) | (L_raw_lbmolph < 0.0), 0.0, L_raw_lbmolph)
    h_ow = np.asarray(hyd.h_ow, dtype=float).reshape((N,))
    h_ow = np.where(~np.isfinite(h_ow) | (h_ow < 0.0), 0.0, h_ow)
    try:
        area = np.asarray(active_area, dtype=float).reshape((N,))
        valid_area = np.isfinite(area) & (area > 0.0)
        h_ow[valid_area] = np.maximum(h_ow[valid_area], liquid_vol_stage[valid_area] / area[valid_area])
    except Exception:
        pass

    tau_cond = max(float(spec.condenser_to_top_tau_sec), 1.0e-6)
    tau_reb = max(float(spec.reboiler_to_bottom_tau_sec), 1.0e-6)
    L_raw_lbmolph[0] = max(float(spec.L_lbmolps[0]) * 3600.0, 0.0)
    if bool(spec.reboiler_is_partial):
        L_raw_lbmolph[-1] = max(float(spec.reboiler_to_bottom_nominal_lbmolps) * 3600.0, 0.0)
    else:
        L_raw_lbmolph[-1] = max(float(ML_stage[-1]) / tau_reb * 3600.0, 0.0)

    L_used = np.asarray(spec.L_lbmolps, dtype=float).reshape((N,)).copy()
    L_used[0] = float(spec.condenser_to_top_nominal_lbmolps)
    L_used[-1] = float(spec.reboiler_to_bottom_nominal_lbmolps)
    l_prev = np.asarray(l_prev_lbmolps, dtype=float).reshape((N,)).copy() if l_prev_lbmolps is not None else L_used.copy()
    l_prev = np.where(~np.isfinite(l_prev) | (l_prev < 0.0), 0.0, l_prev)
    clamped = np.full(N, np.nan, dtype=float)
    prev_up_ratio = 1.2
    prev_down_ratio = 0.8
    nominal_hi_ratio = 1.5

    for i in range(0, N):
        l_calc = max(float(L_raw_lbmolph[i]) / 3600.0, 0.0)
        l_prev_i = max(float(l_prev[i]), 0.0)
        if i == 0:
            l_nom_i = max(float(spec.L_lbmolps[0]), 0.0)
        elif i == (N - 1):
            l_nom_i = max(float(spec.reboiler_to_bottom_nominal_lbmolps), 0.0)
        else:
            l_nom_i = max(float(spec.L_lbmolps[i]), 0.0)
        if l_prev_i > 1.0e-12 and l_nom_i > 1.0e-12:
            l_hi = min(prev_up_ratio * l_prev_i, nominal_hi_ratio * l_nom_i)
            l_lo = min(prev_down_ratio * l_prev_i, prev_down_ratio * l_nom_i)
        elif l_nom_i > 1.0e-12:
            l_hi = nominal_hi_ratio * l_nom_i
            l_lo = 0.0
        else:
            l_hi = prev_up_ratio * l_prev_i
            l_lo = 0.0
        if l_hi < l_lo:
            l_hi = l_lo
        clamped_i = (l_calc > l_hi) or (l_calc < l_lo)
        L_used[i] = min(max(l_calc, l_lo), l_hi)
        clamped[i] = 1.0 if clamped_i else 0.0

    return _LiquidFlowClosure(
        used_lbmolps=L_used.copy(),
        raw_lbmolph=L_raw_lbmolph.copy(),
        h_ow_ft=h_ow.copy(),
        clamped_flag=clamped.copy(),
    )


def _compute_holdup_tau_liquid_flow_closure(
    *,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    stage_results: Sequence[UvFlashStageResult],
    l_prev_lbmolps: Optional[np.ndarray],
) -> _LiquidFlowClosure:
    """
    Generic liquid holdup-over-tau closure.

    This is a partitioned approximation. It uses tray liquid holdup divided by
    a hydraulic time constant to generate tray liquid outflow while keeping the
    rest of the UV sandbox architecture unchanged.
    """
    N = int(spec.n_total_stages)
    n_total, _u_total, _top_liquid, _bottom_liquid, _top_u_total, _bottom_u_total = _unpack_state(
        y,
        n_active=int(spec.active_stage0.size),
        n_components=len(spec.component_names),
    )
    tau_htc = max(float(spec.liquid_hydraulic_tau_sec), 1.0e-6)
    ML_stage = np.zeros(N, dtype=float)
    h_ow = np.zeros(N, dtype=float)
    area = None
    geom = spec.geometry
    if getattr(geom, "active_area_ft2_per_stage", None) is not None:
        try:
            area = np.asarray(geom.active_area_ft2_per_stage, dtype=float).reshape((N,))
            area = np.where(~np.isfinite(area) | (area <= 0.0), np.nan, area)
        except Exception:
            area = None

    for idx, stage0 in enumerate(spec.active_stage0):
        res = stage_results[idx]
        total_stage = float(np.sum(n_total[idx, :]))
        liquid_moles = max(0.0, 1.0 - float(res.beta_vapor)) * total_stage
        ML_stage[stage0] = float(liquid_moles)
        if area is not None and np.isfinite(area[stage0]) and area[stage0] > 0.0:
            liquid_vol = float(liquid_moles) * float(res.vL_ft3_lbmol)
            if np.isfinite(liquid_vol) and liquid_vol >= 0.0:
                h_ow[stage0] = float(liquid_vol) / float(area[stage0])

    L_raw_lbmolph = np.zeros(N, dtype=float)
    for i in range(N):
        L_raw_lbmolph[i] = max(float(ML_stage[i]) / float(tau_htc) * 3600.0, 0.0)

    L_raw_lbmolph[0] = max(float(spec.condenser_to_top_nominal_lbmolps) * 3600.0, 0.0)
    L_raw_lbmolph[-1] = max(float(spec.reboiler_to_bottom_nominal_lbmolps) * 3600.0, 0.0)

    L_used = np.asarray(spec.L_lbmolps, dtype=float).reshape((N,)).copy()
    L_used[0] = float(spec.condenser_to_top_nominal_lbmolps)
    L_used[-1] = float(spec.reboiler_to_bottom_nominal_lbmolps)
    l_prev = np.asarray(l_prev_lbmolps, dtype=float).reshape((N,)).copy() if l_prev_lbmolps is not None else L_used.copy()
    l_prev = np.where(~np.isfinite(l_prev) | (l_prev < 0.0), 0.0, l_prev)

    clamped = np.full(N, np.nan, dtype=float)
    prev_up_ratio = 1.2
    prev_down_ratio = 0.8
    nominal_hi_ratio = 1.5

    for i in range(N):
        l_calc = max(float(L_raw_lbmolph[i]) / 3600.0, 0.0)
        l_prev_i = max(float(l_prev[i]), 0.0)
        if i == 0:
            l_nom_i = max(float(spec.condenser_to_top_nominal_lbmolps), 0.0)
        elif i == (N - 1):
            l_nom_i = max(float(spec.reboiler_to_bottom_nominal_lbmolps), 0.0)
        else:
            l_nom_i = max(float(spec.L_lbmolps[i]), 0.0)
        if l_prev_i > 1.0e-12 and l_nom_i > 1.0e-12:
            l_hi = min(prev_up_ratio * l_prev_i, nominal_hi_ratio * l_nom_i)
            l_lo = min(prev_down_ratio * l_prev_i, prev_down_ratio * l_nom_i)
        elif l_nom_i > 1.0e-12:
            l_hi = nominal_hi_ratio * l_nom_i
            l_lo = 0.0
        else:
            l_hi = prev_up_ratio * l_prev_i
            l_lo = 0.0
        if l_hi < l_lo:
            l_hi = l_lo
        clamped_i = (l_calc > l_hi) or (l_calc < l_lo)
        L_used[i] = min(max(l_calc, l_lo), l_hi)
        clamped[i] = 1.0 if clamped_i else 0.0

    return _LiquidFlowClosure(
        used_lbmolps=L_used.copy(),
        raw_lbmolph=L_raw_lbmolph.copy(),
        h_ow_ft=h_ow.copy(),
        clamped_flag=clamped.copy(),
    )


def _compute_vapor_flow_closure(
    *,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    stage_results: Sequence[UvFlashStageResult],
    condenser_state: Optional[UvFlashStageResult],
    reboiler_state: Optional[UvFlashStageResult],
    top_node: _LiquidNodeState,
    bottom_node: _LiquidNodeState,
    v_prev_lbmolps: Optional[np.ndarray],
    liquid_flow: Optional[_LiquidFlowClosure],
) -> _VaporFlowClosure:
    N = int(spec.n_total_stages)
    Nc = len(spec.component_names)
    geom = spec.geometry
    n_total, _u_total, _top_liquid, _bottom_liquid, _top_u_total, _bottom_u_total = _unpack_state(
        y,
        n_active=int(spec.active_stage0.size),
        n_components=Nc,
    )

    T_full = np.full(N, np.nan, dtype=float)
    P_full = np.full(N, np.nan, dtype=float)
    x_full = np.zeros((N, Nc), dtype=float)
    y_full = np.zeros((N, Nc), dtype=float)
    Z_full = np.ones(N, dtype=float)
    rhoL_full = np.full(N, np.nan, dtype=float)
    h_ow = np.zeros(N, dtype=float)

    if getattr(geom, "active_area_ft2_per_stage", None) is not None:
        area = np.asarray(geom.active_area_ft2_per_stage, dtype=float).reshape((N,))
    else:
        area = np.asarray(geom.area_ft2_per_stage, dtype=float).reshape((N,))
    area = np.where(~np.isfinite(area) | (area <= 0.0), np.nan, area)

    for idx, stage0 in enumerate(spec.active_stage0):
        res = stage_results[idx]
        T_full[stage0] = float(res.T_F)
        P_full[stage0] = float(res.P_psia)
        x_full[stage0, :] = np.asarray(res.x, dtype=float).copy()
        y_full[stage0, :] = np.asarray(res.y, dtype=float).copy()
        Z_full[stage0] = float(res.Z_vapor) if np.isfinite(float(res.Z_vapor)) and float(res.Z_vapor) > 0.0 else 1.0
        rhoL_full[stage0] = 1.0 / max(float(res.vL_ft3_lbmol), 1.0e-12)
        if np.isfinite(area[stage0]) and area[stage0] > 0.0:
            total_stage = float(np.sum(n_total[idx, :]))
            liquid_moles = max(0.0, 1.0 - float(res.beta_vapor)) * total_stage
            liquid_vol = liquid_moles * float(res.vL_ft3_lbmol)
            if np.isfinite(liquid_vol) and liquid_vol >= 0.0:
                h_ow[stage0] = float(liquid_vol) / float(area[stage0])
    if condenser_state is not None:
        T_full[0] = float(condenser_state.T_F)
        P_full[0] = float(condenser_state.P_psia)
        x_full[0, :] = np.asarray(condenser_state.x, dtype=float).copy()
        y_full[0, :] = np.asarray(condenser_state.y, dtype=float).copy()
        Z_full[0] = float(condenser_state.Z_vapor) if np.isfinite(float(condenser_state.Z_vapor)) and float(condenser_state.Z_vapor) > 0.0 else 1.0
        rhoL_full[0] = 1.0 / max(float(condenser_state.vL_ft3_lbmol), 1.0e-12)
    if reboiler_state is not None:
        T_full[-1] = float(reboiler_state.T_F)
        P_full[-1] = float(reboiler_state.P_psia)
        x_full[-1, :] = np.asarray(reboiler_state.x, dtype=float).copy()
        y_full[-1, :] = np.asarray(reboiler_state.y, dtype=float).copy()
        Z_full[-1] = float(reboiler_state.Z_vapor) if np.isfinite(float(reboiler_state.Z_vapor)) and float(reboiler_state.Z_vapor) > 0.0 else 1.0
        rhoL_full[-1] = 1.0 / max(float(reboiler_state.vL_ft3_lbmol), 1.0e-12)
    if liquid_flow is not None:
        try:
            h_ow = np.asarray(liquid_flow.h_ow_ft, dtype=float).reshape((N,))
            h_ow = np.where(~np.isfinite(h_ow) | (h_ow < 0.0), 0.0, h_ow)
        except Exception:
            pass

    T_full = np.where(np.isfinite(T_full), T_full, np.linspace(
        float(condenser_state.T_F if condenser_state is not None else stage_results[0].T_F),
        float(reboiler_state.T_F if reboiler_state is not None else stage_results[-1].T_F),
        N,
    ))
    P_full = np.where(np.isfinite(P_full), P_full, np.linspace(
        float(condenser_state.P_psia if condenser_state is not None else stage_results[0].P_psia),
        float(reboiler_state.P_psia if reboiler_state is not None else stage_results[-1].P_psia),
        N,
    ))
    Z_full = np.where(~np.isfinite(Z_full) | (Z_full <= 0.0), 1.0, Z_full)
    rhoL_full = np.where(~np.isfinite(rhoL_full) | (rhoL_full <= 0.0), np.nan, rhoL_full)

    boilup = float(spec.V_lbmolps[-1])
    if reboiler_state is not None and spec.q_stage_BTUps is not None:
        try:
            q_reb = float(np.asarray(spec.q_stage_BTUps, dtype=float).reshape((N,))[-1])
        except Exception:
            q_reb = float("nan")
        latent = float(reboiler_state.HV_BTU_lbmol) - float(reboiler_state.HL_BTU_lbmol)
        if np.isfinite(q_reb) and q_reb > 0.0 and np.isfinite(latent) and latent > 1.0e-6:
            boilup = max(float(q_reb) / float(latent), 0.0)

    V_raw = _vapor_outflow_hydraulic_lbmolps(
        P_profile_psia=P_full,
        T_F=T_full,
        y_tray=y_full,
        x_tray=x_full,
        Z_vap=Z_full,
        geom=geom,
        h_ow_ft=h_ow,
        rhoL_lbmol_ft3=rhoL_full,
        mw_components=spec.component_mw_lbm_per_lbmol,
        dry_tray_K=float(spec.dry_tray_K),
    )
    V_raw = np.asarray(V_raw, dtype=float).reshape((N,))
    V_raw = np.where(~np.isfinite(V_raw) | (V_raw < 0.0), 0.0, V_raw)
    V_raw[0] = 0.0
    V_raw[-1] = float(boilup)

    V_used = np.asarray(spec.V_lbmolps, dtype=float).reshape((N,)).copy()
    V_used[0] = 0.0
    V_used[-1] = float(boilup)
    v_prev = np.asarray(v_prev_lbmolps, dtype=float).reshape((N,)).copy() if v_prev_lbmolps is not None else V_used.copy()
    v_prev = np.where(~np.isfinite(v_prev) | (v_prev < 0.0), 0.0, v_prev)

    dp_psia = np.full(N, np.nan, dtype=float)
    clamped = np.full(N, np.nan, dtype=float)
    prev_up_ratio = 1.2
    prev_down_ratio = 0.8
    reb_neighbor_up = 1.02
    reb_neighbor_down = 0.98

    for i in range(1, N - 1):
        if np.isfinite(P_full[i]) and np.isfinite(P_full[i - 1]):
            dp_psia[i] = float(P_full[i] - P_full[i - 1])

    for i in range(N - 2, 0, -1):
        v_calc = max(float(V_raw[i]), 0.0)
        v_prev_i = max(float(v_prev[i]), 0.0)
        v_nom_i = max(float(spec.V_lbmolps[i]), 0.0)
        if v_prev_i > 1.0e-12 and v_nom_i > 1.0e-12:
            v_hi = min(prev_up_ratio * v_prev_i, float(spec.conductance_nominal_hi_ratio) * v_nom_i)
            v_lo = min(prev_down_ratio * v_prev_i, prev_down_ratio * v_nom_i)
        elif v_nom_i > 1.0e-12:
            v_hi = float(spec.conductance_nominal_hi_ratio) * v_nom_i
            v_lo = 0.0
        else:
            v_hi = max(prev_up_ratio * v_prev_i, boilup)
            v_lo = 0.0

        if i == (N - 2):
            v_hi = min(v_hi, reb_neighbor_up * boilup)
            if boilup > 1.0e-12:
                v_lo = max(v_lo, reb_neighbor_down * boilup)

        if v_hi < v_lo:
            v_hi = v_lo

        clamped_i = (v_calc > v_hi) or (v_calc < v_lo)
        V_used[i] = min(max(v_calc, v_lo), v_hi)
        clamped[i] = 1.0 if clamped_i else 0.0

    return _VaporFlowClosure(
        used_lbmolps=V_used.copy(),
        raw_lbmolps=V_raw.copy(),
        dp_psia=dp_psia.copy(),
        h_ow_ft=h_ow.copy(),
        clamped_flag=clamped.copy(),
    )


def _compute_rhs(
    *,
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    stage_results: Sequence[UvFlashStageResult],
    condenser_state: Optional[UvFlashStageResult],
    reboiler_state: Optional[UvFlashStageResult],
    top_node: _LiquidNodeState,
    bottom_node: _LiquidNodeState,
    liquid_flow: _LiquidFlowClosure,
    vapor_flow: _VaporFlowClosure,
) -> np.ndarray:
    n_active = int(spec.active_stage0.size)
    n_components = len(spec.component_names)
    n_total, _u_total, _top_liquid, _bottom_liquid, _top_u_total, _bottom_u_total = _unpack_state(
        y,
        n_active=n_active,
        n_components=n_components,
    )
    q_stage = (
        np.asarray(spec.q_stage_BTUps, dtype=float).reshape((int(spec.n_total_stages),))
        if spec.q_stage_BTUps is not None
        else np.zeros(int(spec.n_total_stages), dtype=float)
    )

    dn = np.zeros_like(n_total, dtype=float)
    dU = np.zeros(n_active, dtype=float)
    last_active_stage0 = int(spec.active_stage0[-1]) if n_active > 0 else -1
    bottom_stage0 = int(spec.n_total_stages) - 1

    for idx, stage0 in enumerate(spec.active_stage0):
        if int(stage0) == 1:
            x_in = top_node.x_liq
            hL_in = float(top_node.hL_BTU_lbmol)
        else:
            x_in = np.asarray(stage_results[idx - 1].x, dtype=float)
            hL_in = float(stage_results[idx - 1].HL_BTU_lbmol)

        if int(stage0) == last_active_stage0 and last_active_stage0 < bottom_stage0 and reboiler_state is not None:
            y_in = np.asarray(reboiler_state.y, dtype=float)
            hV_in = float(reboiler_state.HV_BTU_lbmol)
        elif int(stage0) == bottom_stage0:
            y_in = np.zeros(n_components, dtype=float)
            hV_in = 0.0
        else:
            y_in = np.asarray(stage_results[idx + 1].y, dtype=float)
            hV_in = float(stage_results[idx + 1].HV_BTU_lbmol)

        x_now = np.asarray(stage_results[idx].x, dtype=float)
        y_now = np.asarray(stage_results[idx].y, dtype=float)
        hL_now = float(stage_results[idx].HL_BTU_lbmol)
        hV_now = float(stage_results[idx].HV_BTU_lbmol)

        if int(stage0) == 1:
            L_in = float(spec.L_lbmolps[0])
        else:
            L_in = float(liquid_flow.used_lbmolps[stage0 - 1])

        L_out = float(liquid_flow.used_lbmolps[stage0])
        V_in = 0.0 if int(stage0) == (int(spec.n_total_stages) - 1) else float(vapor_flow.used_lbmolps[stage0 + 1])
        V_out = float(vapor_flow.used_lbmolps[stage0])

        dn[idx, :] = L_in * x_in + V_in * y_in - L_out * x_now - V_out * y_now
        dU[idx] = L_in * hL_in + V_in * hV_in - L_out * hL_now - V_out * hV_now + float(q_stage[int(stage0)])

    if spec.feed_term is not None:
        i_feed = int(spec.feed_term.stage_active_idx)
        dn[i_feed, :] += np.asarray(spec.feed_term.component_rates_lbmolps, dtype=float)
        dU[i_feed] += float(spec.feed_term.enthalpy_rate_BTUps)

    cond_liq = np.asarray(
        condenser_state.x if condenser_state is not None else stage_results[0].x,
        dtype=float,
    )
    cond_in = float(vapor_flow.used_lbmolps[1]) if int(spec.n_total_stages) > 1 else 0.0
    cond_hL = float(condenser_state.HL_BTU_lbmol) if condenser_state is not None else float(stage_results[0].HL_BTU_lbmol)
    d_top = (
        float(cond_in) * cond_liq
        - float(liquid_flow.used_lbmolps[0] + spec.distillate_total_lbmolps) * top_node.x_liq
    )
    d_top_u = (
        float(cond_in) * float(cond_hL)
        - float(liquid_flow.used_lbmolps[0] + spec.distillate_total_lbmolps) * float(top_node.hL_BTU_lbmol)
    )
    d_top_u += float(spec.condenser_duty_BTUps)
    bottom_vapor = (
        float(vapor_flow.used_lbmolps[-1]) * np.asarray(reboiler_state.y, dtype=float)
        if reboiler_state is not None
        else 0.0
    )
    bottom_vapor_h = float(reboiler_state.HV_BTU_lbmol) if reboiler_state is not None else 0.0
    d_bottom = (
        float(liquid_flow.used_lbmolps[last_active_stage0]) * np.asarray(stage_results[-1].x, dtype=float)
        - float(spec.bottoms_total_lbmolps) * bottom_node.x_liq
        - bottom_vapor
    )
    d_bottom_u = (
        float(liquid_flow.used_lbmolps[last_active_stage0]) * float(stage_results[-1].HL_BTU_lbmol)
        - float(spec.bottoms_total_lbmolps) * float(bottom_node.hL_BTU_lbmol)
        - float(vapor_flow.used_lbmolps[-1]) * float(bottom_vapor_h)
    )
    if bool(spec.reboiler_is_partial) and spec.q_stage_BTUps is not None:
        d_bottom_u += float(q_stage[-1])

    return _pack_state(dn, dU, d_top, d_bottom, d_top_u, d_bottom_u)


def _make_summary_row(
    *,
    time_s: float,
    stage_results: Sequence[UvFlashStageResult],
    condenser_state: Optional[UvFlashStageResult],
    reboiler_state: Optional[UvFlashStageResult],
    dydt: Optional[np.ndarray],
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    top_node: _LiquidNodeState,
    bottom_node: _LiquidNodeState,
    liquid_flow: _LiquidFlowClosure,
    vapor_flow: _VaporFlowClosure,
) -> Dict[str, float | int]:
    n_active = int(spec.active_stage0.size)
    n_total, u_total, _top_liquid, _bottom_liquid, top_u_total, bottom_u_total = _unpack_state(
        y,
        n_active=n_active,
        n_components=len(spec.component_names),
    )
    row: Dict[str, float | int] = {
        "time_s": float(time_s),
        "max_abs_residual_u_BTU_lbmol": float(
            np.max([abs(float(r.residual_u_BTU_lbmol)) for r in stage_results]) if stage_results else np.nan
        ),
        "max_abs_residual_v_ft3_lbmol": float(
            np.max([abs(float(r.residual_v_ft3_lbmol)) for r in stage_results]) if stage_results else np.nan
        ),
        "max_abs_residual_beta": float(
            np.max([abs(float(r.residual_beta)) for r in stage_results]) if stage_results else np.nan
        ),
        "min_stage_converged_flag": int(min((1 if r.converged else 0) for r in stage_results)) if stage_results else 0,
        "Distillate_L_lbmol": float(top_node.total_moles_lbmol),
        "Bottoms_L_lbmol": float(bottom_node.total_moles_lbmol),
        "max_abs_lflow_raw_lbmolph": float(_nanmax_abs_or_nan(liquid_flow.raw_lbmolph)),
        "max_abs_lflow_used_lbmolph": float(_nanmax_abs_or_nan(liquid_flow.used_lbmolps) * 3600.0),
        "max_abs_vflow_raw_lbmolph": float(_nanmax_abs_or_nan(vapor_flow.raw_lbmolps) * 3600.0),
        "max_abs_vflow_used_lbmolph": float(_nanmax_abs_or_nan(vapor_flow.used_lbmolps) * 3600.0),
        "max_abs_vflow_dp_psia": float(_nanmax_abs_or_nan(vapor_flow.dp_psia)),
    }
    if dydt is not None:
        dn, dU, dtop, dbottom, dtop_u, dbottom_u = _unpack_state(
            dydt,
            n_active=n_active,
            n_components=len(spec.component_names),
        )
        row["max_abs_dn_lbmolps"] = float(np.max(np.abs(dn)))
        row["max_abs_dU_BTUps"] = float(np.max(np.abs(dU)))
        row["max_abs_dtop_lbmolps"] = float(np.max(np.abs(dtop)))
        row["max_abs_dbottom_lbmolps"] = float(np.max(np.abs(dbottom)))
        row["abs_dtop_u_BTUps"] = float(abs(dtop_u))
        row["abs_dbottom_u_BTUps"] = float(abs(dbottom_u))
    else:
        row["max_abs_dn_lbmolps"] = float("nan")
        row["max_abs_dU_BTUps"] = float("nan")
        row["max_abs_dtop_lbmolps"] = float("nan")
        row["max_abs_dbottom_lbmolps"] = float("nan")
        row["abs_dtop_u_BTUps"] = float("nan")
        row["abs_dbottom_u_BTUps"] = float("nan")

    row["Distillate_u_total_BTU"] = float(top_u_total)
    row["Bottoms_u_total_BTU"] = float(bottom_u_total)

    if condenser_state is not None:
        row["stage_1_m_total_lbmol"] = float("nan")
        row["stage_1_u_total_BTU"] = float("nan")
        row["stage_1_T_F"] = float(condenser_state.T_F)
        row["stage_1_P_psia"] = float(condenser_state.P_psia)
        row["stage_1_beta"] = float(condenser_state.beta_vapor)
        row["stage_1_V_out_lbmolph"] = 0.0

    if reboiler_state is not None:
        stage_n = int(spec.n_total_stages)
        row[f"stage_{stage_n}_m_total_lbmol"] = float("nan")
        row[f"stage_{stage_n}_u_total_BTU"] = float("nan")
        row[f"stage_{stage_n}_T_F"] = float(reboiler_state.T_F)
        row[f"stage_{stage_n}_P_psia"] = float(reboiler_state.P_psia)
        row[f"stage_{stage_n}_beta"] = float(reboiler_state.beta_vapor)
        row[f"stage_{stage_n}_V_out_lbmolph"] = float(vapor_flow.used_lbmolps[-1] * 3600.0)

    for idx, stage1 in enumerate(spec.active_stage1):
        m_tot = float(np.sum(n_total[idx, :]))
        row[f"stage_{int(stage1)}_m_total_lbmol"] = m_tot
        row[f"stage_{int(stage1)}_u_total_BTU"] = float(u_total[idx])
        row[f"stage_{int(stage1)}_T_F"] = float(stage_results[idx].T_F)
        row[f"stage_{int(stage1)}_P_psia"] = float(stage_results[idx].P_psia)
        row[f"stage_{int(stage1)}_beta"] = float(stage_results[idx].beta_vapor)
        row[f"stage_{int(stage1)}_V_out_lbmolph"] = float(vapor_flow.used_lbmolps[int(stage1) - 1] * 3600.0)
    return row


def _append_profile_rows(
    *,
    rows: List[Dict[str, Any]],
    time_s: float,
    stage_results: Sequence[UvFlashStageResult],
    condenser_state: Optional[UvFlashStageResult],
    reboiler_state: Optional[UvFlashStageResult],
    spec: UvMini8PrototypeSpec,
    y: np.ndarray,
    top_node: _LiquidNodeState,
    bottom_node: _LiquidNodeState,
    liquid_flow: _LiquidFlowClosure,
    vapor_flow: _VaporFlowClosure,
) -> None:
    n_active = int(spec.active_stage0.size)
    n_total, u_total, _top_liquid, _bottom_liquid, top_u_total, bottom_u_total = _unpack_state(
        y,
        n_active=n_active,
        n_components=len(spec.component_names),
    )

    top_row: Dict[str, Any] = {
        "time_s": float(time_s),
        "stage": int(top_node.stage_label),
        "node_type": str(top_node.node_type),
        "m_total_lbmol": float(top_node.total_moles_lbmol),
        "u_total_BTU": float(top_u_total),
        "fixed_volume_ft3": float("nan"),
        "T_F": float(top_node.T_F),
        "P_psia": float(top_node.P_psia),
        "beta_vapor": 0.0,
        "L_out_lbmolph": float(liquid_flow.used_lbmolps[0] * 3600.0),
        "L_out_raw_lbmolph": float(liquid_flow.used_lbmolps[0] * 3600.0),
        "lflow_clamped_flag": float("nan"),
        "V_out_lbmolph": float("nan"),
        "V_out_raw_lbmolph": float("nan"),
        "vflow_dp_psia": float("nan"),
        "h_ow_ft": float("nan"),
        "converged_flag": 1,
    }
    for j, cname in enumerate(spec.component_names):
        label = _label_for_component(cname)
        top_row[f"x_{label}"] = float(top_node.x_liq[j])
        top_row[f"n_total_{label}_lbmol"] = float(top_node.total_component_holdup_lbmol[j])
    rows.append(top_row)

    if condenser_state is not None:
        cond_row: Dict[str, Any] = {
            "time_s": float(time_s),
            "stage": 1,
            "node_type": "stage",
            "m_total_lbmol": float("nan"),
            "u_total_BTU": float("nan"),
            "fixed_volume_ft3": float("nan"),
            "T_F": float(condenser_state.T_F),
            "P_psia": float(condenser_state.P_psia),
            "beta_vapor": float(condenser_state.beta_vapor),
            "L_out_lbmolph": float(liquid_flow.used_lbmolps[0] * 3600.0),
            "L_out_raw_lbmolph": float(liquid_flow.raw_lbmolph[0]),
            "lflow_clamped_flag": float(liquid_flow.clamped_flag[0]),
            "HL_BTU_lbmol": float(condenser_state.HL_BTU_lbmol),
            "HV_BTU_lbmol": float(condenser_state.HV_BTU_lbmol),
            "uL_BTU_lbmol": float(condenser_state.uL_BTU_lbmol),
            "uV_BTU_lbmol": float(condenser_state.uV_BTU_lbmol),
            "vL_ft3_lbmol": float(condenser_state.vL_ft3_lbmol),
            "vV_ft3_lbmol": float(condenser_state.vV_ft3_lbmol),
            "residual_u_BTU_lbmol": float(condenser_state.residual_u_BTU_lbmol),
            "residual_v_ft3_lbmol": float(condenser_state.residual_v_ft3_lbmol),
            "residual_beta": float(condenser_state.residual_beta),
            "converged_flag": int(1 if condenser_state.converged else 0),
            "V_out_lbmolph": 0.0,
            "V_out_raw_lbmolph": 0.0,
            "vflow_dp_psia": float(vapor_flow.dp_psia[0]),
            "h_ow_ft": float(vapor_flow.h_ow_ft[0]),
            "vflow_clamped_flag": float(vapor_flow.clamped_flag[0]) if np.isfinite(float(vapor_flow.clamped_flag[0])) else float("nan"),
        }
        for j, cname in enumerate(spec.component_names):
            label = _label_for_component(cname)
            cond_row[f"x_{label}"] = float(condenser_state.x[j])
        rows.append(cond_row)

    for idx, stage1 in enumerate(spec.active_stage1):
        stage0 = int(stage1) - 1
        row: Dict[str, Any] = {
            "time_s": float(time_s),
            "stage": int(stage1),
            "node_type": "stage",
            "m_total_lbmol": float(np.sum(n_total[idx, :])),
            "u_total_BTU": float(u_total[idx]),
            "fixed_volume_ft3": float(spec.fixed_total_volume_ft3[idx]),
            "T_F": float(stage_results[idx].T_F),
            "P_psia": float(stage_results[idx].P_psia),
            "beta_vapor": float(stage_results[idx].beta_vapor),
            "L_out_lbmolph": float(liquid_flow.used_lbmolps[stage0] * 3600.0),
            "L_out_raw_lbmolph": float(liquid_flow.raw_lbmolph[stage0]),
            "lflow_clamped_flag": float(liquid_flow.clamped_flag[stage0]),
            "HL_BTU_lbmol": float(stage_results[idx].HL_BTU_lbmol),
            "HV_BTU_lbmol": float(stage_results[idx].HV_BTU_lbmol),
            "uL_BTU_lbmol": float(stage_results[idx].uL_BTU_lbmol),
            "uV_BTU_lbmol": float(stage_results[idx].uV_BTU_lbmol),
            "vL_ft3_lbmol": float(stage_results[idx].vL_ft3_lbmol),
            "vV_ft3_lbmol": float(stage_results[idx].vV_ft3_lbmol),
            "residual_u_BTU_lbmol": float(stage_results[idx].residual_u_BTU_lbmol),
            "residual_v_ft3_lbmol": float(stage_results[idx].residual_v_ft3_lbmol),
            "residual_beta": float(stage_results[idx].residual_beta),
            "converged_flag": int(1 if stage_results[idx].converged else 0),
            "V_out_lbmolph": float(vapor_flow.used_lbmolps[stage0] * 3600.0),
            "V_out_raw_lbmolph": float(vapor_flow.raw_lbmolps[stage0] * 3600.0),
            "vflow_dp_psia": float(vapor_flow.dp_psia[stage0]),
            "h_ow_ft": float(vapor_flow.h_ow_ft[stage0]),
            "vflow_clamped_flag": float(vapor_flow.clamped_flag[stage0]),
        }
        for j, cname in enumerate(spec.component_names):
            label = _label_for_component(cname)
            row[f"x_{label}"] = float(stage_results[idx].x[j])
            row[f"y_{label}"] = float(stage_results[idx].y[j])
            row[f"n_total_{label}_lbmol"] = float(n_total[idx, j])
        rows.append(row)

    if reboiler_state is not None:
        reb_row: Dict[str, Any] = {
            "time_s": float(time_s),
            "stage": int(spec.n_total_stages),
            "node_type": "stage",
            "m_total_lbmol": float("nan"),
            "u_total_BTU": float("nan"),
            "fixed_volume_ft3": float("nan"),
            "T_F": float(reboiler_state.T_F),
            "P_psia": float(reboiler_state.P_psia),
            "beta_vapor": float(reboiler_state.beta_vapor),
            "L_out_lbmolph": float(liquid_flow.used_lbmolps[-1] * 3600.0),
            "L_out_raw_lbmolph": float(liquid_flow.raw_lbmolph[-1]),
            "lflow_clamped_flag": float(liquid_flow.clamped_flag[-1]),
            "HL_BTU_lbmol": float(reboiler_state.HL_BTU_lbmol),
            "HV_BTU_lbmol": float(reboiler_state.HV_BTU_lbmol),
            "uL_BTU_lbmol": float(reboiler_state.uL_BTU_lbmol),
            "uV_BTU_lbmol": float(reboiler_state.uV_BTU_lbmol),
            "vL_ft3_lbmol": float(reboiler_state.vL_ft3_lbmol),
            "vV_ft3_lbmol": float(reboiler_state.vV_ft3_lbmol),
            "residual_u_BTU_lbmol": float(reboiler_state.residual_u_BTU_lbmol),
            "residual_v_ft3_lbmol": float(reboiler_state.residual_v_ft3_lbmol),
            "residual_beta": float(reboiler_state.residual_beta),
            "converged_flag": int(1 if reboiler_state.converged else 0),
            "V_out_lbmolph": float(vapor_flow.used_lbmolps[-1] * 3600.0),
            "V_out_raw_lbmolph": float(vapor_flow.raw_lbmolps[-1] * 3600.0),
            "vflow_dp_psia": float(vapor_flow.dp_psia[-1]),
            "h_ow_ft": float(vapor_flow.h_ow_ft[-1]),
            "vflow_clamped_flag": float(vapor_flow.clamped_flag[-1]) if np.isfinite(float(vapor_flow.clamped_flag[-1])) else float("nan"),
        }
        for j, cname in enumerate(spec.component_names):
            label = _label_for_component(cname)
            reb_row[f"x_{label}"] = float(reboiler_state.x[j])
            reb_row[f"y_{label}"] = float(reboiler_state.y[j])
        rows.append(reb_row)

    bottom_row: Dict[str, Any] = {
        "time_s": float(time_s),
        "stage": int(bottom_node.stage_label),
        "node_type": str(bottom_node.node_type),
        "m_total_lbmol": float(bottom_node.total_moles_lbmol),
        "u_total_BTU": float(bottom_u_total),
        "fixed_volume_ft3": float("nan"),
        "T_F": float(bottom_node.T_F),
        "P_psia": float(bottom_node.P_psia),
        "beta_vapor": 0.0,
        "L_out_lbmolph": float("nan"),
        "L_out_raw_lbmolph": float("nan"),
        "lflow_clamped_flag": float("nan"),
        "V_out_lbmolph": float("nan"),
        "V_out_raw_lbmolph": float("nan"),
        "vflow_dp_psia": float("nan"),
        "h_ow_ft": float("nan"),
        "converged_flag": 1,
    }
    for j, cname in enumerate(spec.component_names):
        label = _label_for_component(cname)
        bottom_row[f"x_{label}"] = float(bottom_node.x_liq[j])
        bottom_row[f"n_total_{label}_lbmol"] = float(bottom_node.total_component_holdup_lbmol[j])
    rows.append(bottom_row)


def _write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(str(key))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _read_csv_rows(path: str) -> List[Dict[str, str]]:
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _component_values_from_row(
    row: Dict[str, Any],
    *,
    node_type: str,
    phase_prefix: str,
    is_reference: bool,
) -> Dict[str, float]:
    node = str(node_type).strip().lower()
    prefix = f"{phase_prefix}_"
    out: Dict[str, float] = {}
    for key, raw in row.items():
        if key is None:
            continue
        key_s = str(key)
        if node == "stage":
            if not key_s.startswith(prefix):
                continue
            if key_s.startswith("Distillate_x_") or key_s.startswith("Bottoms_x_"):
                continue
            suffix = key_s[len(prefix) :]
        elif node == "distillate_drum":
            dist_prefix = f"Distillate_{phase_prefix}_"
            if not is_reference and key_s.startswith(prefix):
                suffix = key_s[len(prefix) :]
            elif key_s.startswith(dist_prefix):
                suffix = key_s[len(dist_prefix) :]
            else:
                continue
        elif node == "bottoms_sump":
            bot_prefix = f"Bottoms_{phase_prefix}_"
            if not is_reference and key_s.startswith(prefix):
                suffix = key_s[len(prefix) :]
            elif key_s.startswith(bot_prefix):
                suffix = key_s[len(bot_prefix) :]
            else:
                continue
        else:
            continue
        out[_label_for_component(suffix)] = _float_or_nan(raw)
    return out


def compare_uv_run_to_reference(
    *,
    uv_profile_csv: str,
    reference_profile_csv: str,
    out_dir: str,
    run_id: str,
) -> Dict[str, str]:
    uv_rows = _read_csv_rows(uv_profile_csv)
    ref_rows = _read_csv_rows(reference_profile_csv)
    ref_index: Dict[tuple[float, int, str], Dict[str, str]] = {}
    for row in ref_rows:
        key = (
            _time_key(row.get("time_s")),
            int(_float_or_nan(row.get("stage"))),
            str(row.get("node_type", "")).strip().lower(),
        )
        ref_index[key] = row

    detail_rows: List[Dict[str, Any]] = []
    metrics: Dict[tuple[int, str, str], List[float]] = {}
    for row in uv_rows:
        node_type = str(row.get("node_type", "")).strip().lower()
        key = (
            _time_key(row.get("time_s")),
            int(_float_or_nan(row.get("stage"))),
            node_type,
        )
        ref_row = ref_index.get(key)
        if ref_row is None:
            continue

        compare_map: List[tuple[str, float, float]] = []
        if node_type == "stage":
            compare_map.append(("T_F", _float_or_nan(row.get("T_F")), _float_or_nan(ref_row.get("T_F"))))
        elif node_type == "distillate_drum":
            compare_map.append(("m_total_lbmol", _float_or_nan(row.get("m_total_lbmol")), _float_or_nan(ref_row.get("Distillate_L_lbmol"))))
        elif node_type == "bottoms_sump":
            compare_map.append(("m_total_lbmol", _float_or_nan(row.get("m_total_lbmol")), _float_or_nan(ref_row.get("Bottoms_L_lbmol"))))

        uv_x = _component_values_from_row(row, node_type=node_type, phase_prefix="x", is_reference=False)
        ref_x = _component_values_from_row(ref_row, node_type=node_type, phase_prefix="x", is_reference=True)
        for comp_key, uv_val in uv_x.items():
            if comp_key in ref_x:
                compare_map.append((f"x_{comp_key}", float(uv_val), float(ref_x[comp_key])))

        if node_type == "stage":
            uv_y = _component_values_from_row(row, node_type=node_type, phase_prefix="y", is_reference=False)
            ref_y = _component_values_from_row(ref_row, node_type=node_type, phase_prefix="y", is_reference=True)
            for comp_key, uv_val in uv_y.items():
                if comp_key in ref_y:
                    compare_map.append((f"y_{comp_key}", float(uv_val), float(ref_y[comp_key])))

        for variable, uv_val, ref_val in compare_map:
            if (not np.isfinite(float(uv_val))) or (not np.isfinite(float(ref_val))):
                continue
            diff = abs(float(uv_val) - float(ref_val))
            detail_rows.append(
                {
                    "time_s": float(key[0]),
                    "stage": int(key[1]),
                    "node_type": str(node_type),
                    "variable": str(variable),
                    "uv_value": float(uv_val),
                    "ref_value": float(ref_val),
                    "abs_diff": float(diff),
                }
            )
            metrics.setdefault((int(key[1]), str(node_type), str(variable)), []).append(float(diff))

    metric_rows: List[Dict[str, Any]] = []
    for (stage, node_type, variable), values in sorted(metrics.items()):
        arr = np.asarray(values, dtype=float)
        metric_rows.append(
            {
                "stage": int(stage),
                "node_type": str(node_type),
                "variable": str(variable),
                "count": int(arr.size),
                "max_abs_diff": float(np.max(arr)),
                "mean_abs_diff": float(np.mean(arr)),
                "rmse": float(np.sqrt(np.mean(arr * arr))),
            }
        )

    out_root = Path(out_dir)
    detail_path = out_root / f"uv_flash_compare_detail_{run_id}.csv"
    metrics_path = out_root / f"uv_flash_compare_metrics_{run_id}.csv"
    _write_csv(detail_path, detail_rows)
    _write_csv(metrics_path, metric_rows)
    return {
        "detail_csv": str(detail_path),
        "metrics_csv": str(metrics_path),
    }


def run_mini8_uv_flash_prototype(
    *,
    excel_path: str,
    n_steps: Optional[int] = None,
    dt_sec: Optional[float] = None,
    logs_dir: Optional[str] = None,
    write_csv: bool = True,
    thermo_mode: str = "auto",
    thermo_table_path: str = r"cache\thermo_table.json",
    thermo_pool_workers: Optional[int] = None,
    thermo_pool_chunk_size: int = 4,
    liquid_flow_mode: str = "francis",
    vapor_flow_mode: str = "conductance",
    conductance_nominal_hi_ratio: Optional[float] = None,
    reference_profile_csv: Optional[str] = None,
) -> Dict[str, Any]:
    case = load_case_from_excel(excel_path)
    col = build_column_spec_from_case(case)
    provider, thermo_mode_used = _build_provider(
        col,
        thermo_mode=thermo_mode,
        thermo_table_path=thermo_table_path,
        thermo_pool_workers=thermo_pool_workers,
        thermo_pool_chunk_size=thermo_pool_chunk_size,
    )
    try:
        spec = build_mini8_uv_prototype_spec(
            excel_path=excel_path,
            provider=provider,
            conductance_nominal_hi_ratio=conductance_nominal_hi_ratio,
        )

        dt = float(dt_sec) if dt_sec is not None else float(col.sim.dt_sec)
        n_steps_eff = int(n_steps) if n_steps is not None else max(int(round(float(col.sim.t_final_sec) / max(dt, 1.0e-12))), 1)
        if n_steps_eff < 1:
            n_steps_eff = 1

        y = _pack_state(
            spec.initial_total_component_holdup_lbmol,
            spec.initial_total_internal_energy_BTU,
            spec.top_node_reference.initial_component_holdup_lbmol,
            spec.bottom_node_reference.initial_component_holdup_lbmol,
            float(spec.top_node_reference.initial_total_internal_energy_BTU),
            float(spec.bottom_node_reference.initial_total_internal_energy_BTU),
        )
        l_nominal = np.asarray(spec.L_lbmolps, dtype=float).copy()
        if l_nominal.size > 0:
            l_nominal[0] = float(spec.condenser_to_top_nominal_lbmolps)
            l_nominal[-1] = float(spec.reboiler_to_bottom_nominal_lbmolps)
        seeds: List[UvFlashStageGuess] = list(spec.initial_guesses)
        summary_rows: List[Dict[str, Any]] = []
        profile_rows: List[Dict[str, Any]] = []
        last_results: List[UvFlashStageResult] = []
        liquid_flow_last = _LiquidFlowClosure(
            used_lbmolps=l_nominal.copy(),
            raw_lbmolph=l_nominal.copy() * 3600.0,
            h_ow_ft=np.zeros(int(spec.n_total_stages), dtype=float),
            clamped_flag=np.full(int(spec.n_total_stages), np.nan, dtype=float),
        )
        vapor_flow_last = _VaporFlowClosure(
            used_lbmolps=np.asarray(spec.V_lbmolps, dtype=float).copy(),
            raw_lbmolps=np.asarray(spec.V_lbmolps, dtype=float).copy(),
            dp_psia=np.full(int(spec.n_total_stages), np.nan, dtype=float),
            h_ow_ft=np.zeros(int(spec.n_total_stages), dtype=float),
            clamped_flag=np.full(int(spec.n_total_stages), np.nan, dtype=float),
        )

        compare_outputs: Dict[str, str] = {}
        liquid_flow_mode_norm = str(liquid_flow_mode or "francis").strip().lower()
        vapor_flow_mode_norm = str(vapor_flow_mode or "conductance").strip().lower()
        if liquid_flow_mode_norm not in ("profile", "francis", "holdup-tau"):
            raise ValueError("liquid_flow_mode must be 'profile', 'francis', or 'holdup-tau'")
        if vapor_flow_mode_norm not in ("profile", "conductance"):
            raise ValueError("vapor_flow_mode must be 'profile' or 'conductance'")

        l_prev = l_nominal.copy()
        v_prev = np.asarray(spec.V_lbmolps, dtype=float).copy()
        for step in range(n_steps_eff + 1):
            t_s = float(step) * float(dt)
            stage_results = _evaluate_stage_results(provider=provider, spec=spec, y=y, seeds=seeds)
            last_results = list(stage_results)
            _n_total, _u_total, top_liquid, bottom_liquid, top_u_total, bottom_u_total = _unpack_state(
                y,
                n_active=int(spec.active_stage0.size),
                n_components=len(spec.component_names),
            )
            top_node = _evaluate_liquid_node_state(
                provider=provider,
                ref=spec.top_node_reference,
                holdup_lbmol=top_liquid,
                u_total_BTU=float(top_u_total),
            )
            bottom_node = _evaluate_liquid_node_state(
                provider=provider,
                ref=spec.bottom_node_reference,
                holdup_lbmol=bottom_liquid,
                u_total_BTU=float(bottom_u_total),
            )
            condenser_state = (
                _evaluate_total_condenser_state(
                    provider=provider,
                    spec=spec,
                    stage2_result=stage_results[0],
                    top_node=top_node,
                )
                if bool(spec.condenser_is_total) and stage_results
                else None
            )
            reboiler_state = (
                _evaluate_partial_reboiler_state(
                    provider=provider,
                    spec=spec,
                    stage_above_result=stage_results[-1],
                    bottom_node=bottom_node,
                )
                if bool(spec.reboiler_is_partial) and stage_results and int(spec.active_stage0[-1]) < (int(spec.n_total_stages) - 1)
                else None
            )

            if liquid_flow_mode_norm == "francis":
                liquid_flow = _compute_liquid_flow_closure(
                    spec=spec,
                    y=y,
                    stage_results=stage_results,
                    l_prev_lbmolps=l_prev,
                )
            elif liquid_flow_mode_norm == "holdup-tau":
                liquid_flow = _compute_holdup_tau_liquid_flow_closure(
                    spec=spec,
                    y=y,
                    stage_results=stage_results,
                    l_prev_lbmolps=l_prev,
                )
            else:
                liquid_flow = _LiquidFlowClosure(
                    used_lbmolps=l_nominal.copy(),
                    raw_lbmolph=l_nominal.copy() * 3600.0,
                    h_ow_ft=np.zeros(int(spec.n_total_stages), dtype=float),
                    clamped_flag=np.full(int(spec.n_total_stages), np.nan, dtype=float),
                )

            if vapor_flow_mode_norm == "conductance":
                vapor_flow = _compute_vapor_flow_closure(
                    spec=spec,
                    y=y,
                    stage_results=stage_results,
                    condenser_state=condenser_state,
                    reboiler_state=reboiler_state,
                    top_node=top_node,
                    bottom_node=bottom_node,
                    v_prev_lbmolps=v_prev,
                    liquid_flow=liquid_flow,
                )
            else:
                vapor_flow = _VaporFlowClosure(
                    used_lbmolps=np.asarray(spec.V_lbmolps, dtype=float).copy(),
                    raw_lbmolps=np.asarray(spec.V_lbmolps, dtype=float).copy(),
                    dp_psia=np.full(int(spec.n_total_stages), np.nan, dtype=float),
                    h_ow_ft=np.zeros(int(spec.n_total_stages), dtype=float),
                    clamped_flag=np.full(int(spec.n_total_stages), np.nan, dtype=float),
                )
            liquid_flow_last = liquid_flow
            vapor_flow_last = vapor_flow
            dydt = None if step >= n_steps_eff else _compute_rhs(
                spec=spec,
                y=y,
                stage_results=stage_results,
                condenser_state=condenser_state,
                reboiler_state=reboiler_state,
                top_node=top_node,
                bottom_node=bottom_node,
                liquid_flow=liquid_flow,
                vapor_flow=vapor_flow,
            )
            summary_rows.append(
                _make_summary_row(
                    time_s=t_s,
                    stage_results=stage_results,
                    condenser_state=condenser_state,
                    reboiler_state=reboiler_state,
                    dydt=dydt,
                    spec=spec,
                    y=y,
                    top_node=top_node,
                    bottom_node=bottom_node,
                    liquid_flow=liquid_flow,
                    vapor_flow=vapor_flow,
                )
            )
            _append_profile_rows(
                rows=profile_rows,
                time_s=t_s,
                stage_results=stage_results,
                condenser_state=condenser_state,
                reboiler_state=reboiler_state,
                spec=spec,
                y=y,
                top_node=top_node,
                bottom_node=bottom_node,
                liquid_flow=liquid_flow,
                vapor_flow=vapor_flow,
            )
            if step >= n_steps_eff:
                break

            y = y + float(dt) * np.asarray(dydt, dtype=float)
            n_block, u_block, top_block, bottom_block, top_u_block, bottom_u_block = _unpack_state(
                y,
                n_active=int(spec.active_stage0.size),
                n_components=len(spec.component_names),
            )
            n_block = np.where(np.isfinite(n_block), n_block, 1.0e-12)
            n_block = np.clip(n_block, 1.0e-12, None)
            top_block = np.where(np.isfinite(top_block), top_block, 1.0e-12)
            top_block = np.clip(top_block, 1.0e-12, None)
            bottom_block = np.where(np.isfinite(bottom_block), bottom_block, 1.0e-12)
            bottom_block = np.clip(bottom_block, 1.0e-12, None)
            if not np.isfinite(float(top_u_block)):
                top_u_block = float(spec.top_node_reference.initial_total_internal_energy_BTU)
            if not np.isfinite(float(bottom_u_block)):
                bottom_u_block = float(spec.bottom_node_reference.initial_total_internal_energy_BTU)
            y = _pack_state(n_block, u_block, top_block, bottom_block, float(top_u_block), float(bottom_u_block))
            seeds = [
                UvFlashStageGuess(
                    T_F=float(r.T_F),
                    P_psia=float(r.P_psia),
                    beta_vapor=float(r.beta_vapor),
                )
                for r in stage_results
            ]
            l_prev = np.asarray(liquid_flow.used_lbmolps, dtype=float).copy()
            v_prev = np.asarray(vapor_flow.used_lbmolps, dtype=float).copy()

        logs_root = Path(logs_dir) if logs_dir is not None else Path("sandbox") / "mini8" / "runs"
        run_id = _timestamp_tag()
        summary_path = logs_root / f"uv_flash_summary_{run_id}.csv"
        profile_path = logs_root / f"uv_flash_profile_{run_id}.csv"
        if write_csv:
            _write_csv(summary_path, summary_rows)
            _write_csv(profile_path, profile_rows)
            if reference_profile_csv:
                compare_outputs = compare_uv_run_to_reference(
                    uv_profile_csv=str(profile_path),
                    reference_profile_csv=str(reference_profile_csv),
                    out_dir=str(logs_root),
                    run_id=str(run_id),
                )

        return {
            "run_id": str(run_id),
            "excel_path": str(excel_path),
            "thermo_mode": str(thermo_mode_used),
            "n_steps": int(n_steps_eff),
            "dt_sec": float(dt),
            "liquid_flow_mode": str(liquid_flow_mode_norm),
            "vapor_flow_mode": str(vapor_flow_mode_norm),
            "summary_csv": str(summary_path) if write_csv else "",
            "profile_csv": str(profile_path) if write_csv else "",
            "compare_detail_csv": compare_outputs.get("detail_csv", ""),
            "compare_metrics_csv": compare_outputs.get("metrics_csv", ""),
            "summary_rows": summary_rows,
            "profile_rows": profile_rows,
            "last_results": last_results,
            "last_liquid_flow": liquid_flow_last,
            "last_vapor_flow": vapor_flow_last,
        }
    finally:
        if hasattr(provider, "close") and callable(getattr(provider, "close")):
            try:
                provider.close()
            except Exception:
                pass


def _build_provider(
    col: ColumnSpec,
    *,
    thermo_mode: str,
    thermo_table_path: str,
    thermo_pool_workers: Optional[int],
    thermo_pool_chunk_size: int,
) -> tuple[Any, str]:
    mode = str(thermo_mode or "auto").strip().lower()
    if mode == "auto":
        mode = "table" if Path(str(thermo_table_path)).exists() else "dwsim"

    if mode == "dwsim":
        return ThermoProviderV1(
            component_names_excel=col.components_excel,
            component_ids_dwsim=col.components_dwsim,
            silence_backend_console=True,
        ), str(mode)

    if mode == "table":
        return TabularThermoProviderV1.from_json(
            str(thermo_table_path),
            expected_component_names_excel=col.components_excel,
            expected_component_ids_dwsim=col.components_dwsim,
        ), str(mode)

    if mode == "table-pool":
        return ParallelTabularThermoProviderV1(
            table_path=str(thermo_table_path),
            expected_component_names_excel=col.components_excel,
            expected_component_ids_dwsim=col.components_dwsim,
            max_workers=thermo_pool_workers,
            chunk_size=thermo_pool_chunk_size,
        ), str(mode)

    raise ValueError("thermo_mode must be one of: auto, dwsim, table, table-pool")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the isolated mini8 UV-flash sandbox prototype.")
    p.add_argument(
        "--excel",
        dest="excel_path",
        default=r"sandbox/mini8/input/distillation_column_template_8stage.xlsx",
        help="Path to the sandbox workbook.",
    )
    p.add_argument("--n-steps", dest="n_steps", type=int, default=None, help="Number of explicit Euler steps.")
    p.add_argument("--dt", dest="dt_sec", type=float, default=None, help="Timestep in seconds.")
    p.add_argument(
        "--logs-dir",
        dest="logs_dir",
        default=None,
        help="Directory for CSV outputs. Defaults to sandbox/mini8/runs.",
    )
    p.add_argument(
        "--thermo",
        dest="thermo_mode",
        choices=["auto", "dwsim", "table", "table-pool"],
        default="auto",
        help="Thermo provider for the UV prototype.",
    )
    p.add_argument(
        "--thermo-table",
        dest="thermo_table_path",
        default=r"cache\thermo_table.json",
        help="Tabular thermo JSON path used by table/table-pool modes.",
    )
    p.add_argument("--thermo-pool-workers", dest="thermo_pool_workers", type=int, default=None)
    p.add_argument("--thermo-pool-chunk-size", dest="thermo_pool_chunk_size", type=int, default=4)
    p.add_argument(
        "--liquid-flow-mode",
        dest="liquid_flow_mode",
        choices=["profile", "francis", "holdup-tau"],
        default="francis",
        help="Internal liquid-flow closure for the UV sandbox.",
    )
    p.add_argument(
        "--vapor-flow-mode",
        dest="vapor_flow_mode",
        choices=["profile", "conductance"],
        default="conductance",
        help="Internal vapor-flow closure for the UV sandbox.",
    )
    p.add_argument(
        "--conductance-nominal-hi-ratio",
        dest="conductance_nominal_hi_ratio",
        type=float,
        default=None,
        help="Nominal-profile ceiling ratio for conductance vapor flow.",
    )
    p.add_argument(
        "--compare-ref-profile",
        dest="reference_profile_csv",
        default=None,
        help="Optional reference profile CSV for UV-vs-reference comparison output.",
    )
    p.add_argument("--no-write-csv", dest="write_csv", action="store_false")
    p.set_defaults(write_csv=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    out = run_mini8_uv_flash_prototype(
        excel_path=str(args.excel_path),
        n_steps=args.n_steps,
        dt_sec=args.dt_sec,
        logs_dir=args.logs_dir,
        write_csv=bool(args.write_csv),
        thermo_mode=str(args.thermo_mode),
        thermo_table_path=str(args.thermo_table_path),
        thermo_pool_workers=args.thermo_pool_workers,
        thermo_pool_chunk_size=int(args.thermo_pool_chunk_size),
        liquid_flow_mode=str(args.liquid_flow_mode),
        vapor_flow_mode=str(args.vapor_flow_mode),
        conductance_nominal_hi_ratio=args.conductance_nominal_hi_ratio,
        reference_profile_csv=args.reference_profile_csv,
    )
    last_results: Sequence[UvFlashStageResult] = out.get("last_results", [])
    max_ru = max((abs(float(r.residual_u_BTU_lbmol)) for r in last_results), default=float("nan"))
    max_rv = max((abs(float(r.residual_v_ft3_lbmol)) for r in last_results), default=float("nan"))
    max_rb = max((abs(float(r.residual_beta)) for r in last_results), default=float("nan"))
    print(
        f"[UV mini8] run_id={out['run_id']}  thermo={out['thermo_mode']}  "
        f"lflow={out['liquid_flow_mode']}  vflow={out['vapor_flow_mode']}  "
        f"steps={int(out['n_steps'])}  dt={float(out['dt_sec']):.3g}s  "
        f"max|ru|={max_ru:.3g}  max|rv|={max_rv:.3g}  max|rb|={max_rb:.3g}"
    )
    if out.get("summary_csv"):
        print(f"[UV mini8] summary_csv={out['summary_csv']}")
    if out.get("profile_csv"):
        print(f"[UV mini8] profile_csv={out['profile_csv']}")
    if out.get("compare_metrics_csv"):
        print(f"[UV mini8] compare_metrics_csv={out['compare_metrics_csv']}")
    if out.get("compare_detail_csv"):
        print(f"[UV mini8] compare_detail_csv={out['compare_detail_csv']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
