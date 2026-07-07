"""
column_rhs_v1.py

Dynamic Distillation - ODE Right-Hand Side

PURPOSE
-------
Evaluate state derivatives and diagnostics for tray/top/bottom dynamics.
Implements mass balances, optional energy balances, pressure/hydraulics,
thermo-refresh/caching logic, equilibrium relaxation, and draw handling.

INPUTS
------
column_rhs(t, y, col, layout, inputs):
- t: simulation time
- y: packed state vector
- col: ColumnSpec
- layout: StateVectorLayout
- inputs: ColumnInputs (boundary flows, thermo provider/mode, pressure model,
  vapor-flow model, condenser/reboiler options, cached thermo/hydraulic seeds)

OUTPUTS
-------
- dydt: packed derivative vector
- diag: diagnostics dictionary (flows, pressure, thermo, closure residuals,
  controller-facing and condenser/top-drum signals)

KEY DEPENDENCIES
----------------
- column_spec_builder_v1 / state_vector_layout_v1
- stage_thermo_v1 / thermo_model_v1
- stage_hydraulics_francis_v1

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Layout and ColumnSpec dimensions must be consistent.
- Thermo-dependent closures require valid provider data or cached fallbacks.
- Multiple optional submodels are gated by ColumnInputs flags.

NOTES
-----
- Supports batch thermo refresh path when provider exposes flash_TP_full_batch.
- Includes top-drum PSV vent terms and detailed mass/energy closure diagnostics.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import time
from typing import Dict, Optional, Tuple, Any

import numpy as np

from dynamic_distillation.column_spec_builder_v1 import ColumnSpec, ColumnGeometry
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.thermo_model_v1 import ThermoModel, ConstantCpThermo
from dynamic_distillation.thermo_step_coordinator_v1 import (
    refresh_energy_vapor_flow_phase_enthalpies,
    refresh_temperature_state_phase_enthalpies,
    refresh_tray_tp_packet,
)
from dynamic_distillation.stage_thermo_v1 import flash_TP_full_F_psia
from dynamic_distillation.stage_hydraulics_francis_v1 import compute_francis_weir_liquid_outflow


class ColumnRHSError(RuntimeError):
    """Raised when RHS evaluation fails."""


@dataclass
class TrayThermoPacket:
    z_overall_tray: np.ndarray
    K_tray: np.ndarray
    HL_BTU_lbmol_tray: np.ndarray
    HV_BTU_lbmol_tray: np.ndarray
    Z_tray: np.ndarray
    cpL_BTU_lbmolF_tray: Optional[np.ndarray] = None
    cpV_BTU_lbmolF_tray: Optional[np.ndarray] = None
    T_tray_F: Optional[np.ndarray] = None
    P_tray_psia: Optional[np.ndarray] = None
    x_equilibrium_tray: Optional[np.ndarray] = None
    y_equilibrium_tray: Optional[np.ndarray] = None

    @property
    def z_overall(self) -> np.ndarray:
        return self.z_overall_tray

    @property
    def HL(self) -> np.ndarray:
        return self.HL_BTU_lbmol_tray

    @property
    def HV(self) -> np.ndarray:
        return self.HV_BTU_lbmol_tray

    @property
    def Zfac_tray(self) -> np.ndarray:
        return self.Z_tray

    @property
    def cpL_tray(self) -> Optional[np.ndarray]:
        return self.cpL_BTU_lbmolF_tray

    @property
    def cpV_tray(self) -> Optional[np.ndarray]:
        return self.cpV_BTU_lbmolF_tray

    @property
    def x_eq(self) -> Optional[np.ndarray]:
        return self.x_equilibrium_tray

    @property
    def y_eq(self) -> Optional[np.ndarray]:
        return self.y_equilibrium_tray

    @property
    def T_state(self) -> Optional[np.ndarray]:
        return self.T_tray_F

    @property
    def P_state(self) -> Optional[np.ndarray]:
        return self.P_tray_psia


@dataclass
class CondenserDutyPacket:
    q_calc_BTUph: Optional[float]
    T_bubble_F: Optional[float]
    mode: str
    V_vapor_in_lbmolps: float
    T_vapor_in_F: float
    P_vapor_in_psia: float
    P_condenser_psia: float
    y_vapor_in: np.ndarray
    hL_cond_BTU_lbmol: Optional[float] = None


@dataclass
class FeedStageFlashPacket:
    stage0: int
    T_feed_F: float
    P_feed_psia: float
    z_feed: np.ndarray
    Fk_L_lbmolps: np.ndarray
    Fk_V_lbmolps: np.ndarray
    hL_BTU_lbmol: Optional[float] = None
    hV_BTU_lbmol: Optional[float] = None


@dataclass
class BottomSumpCpPacket:
    T_sump_F: float
    P_sump_psia: float
    x_sump: np.ndarray
    cpL_BTU_lbmolF: float


def _seed_tray_thermo_packet(
    *,
    N: int,
    Nc: int,
    z_overall_tray: np.ndarray,
    tray_thermo_prev: Optional[TrayThermoPacket],
    K_tray_prev: Optional[np.ndarray],
    HL_prev: Optional[np.ndarray],
    HV_prev: Optional[np.ndarray],
    Zfac_prev: Optional[np.ndarray],
) -> TrayThermoPacket:
    if tray_thermo_prev is not None:
        try:
            return TrayThermoPacket(
                z_overall_tray=np.asarray(z_overall_tray, dtype=float).reshape((N, Nc)).copy(),
                K_tray=np.asarray(tray_thermo_prev.K_tray, dtype=float).reshape((N, Nc)).copy(),
                HL_BTU_lbmol_tray=np.asarray(tray_thermo_prev.HL, dtype=float).reshape((N,)).copy(),
                HV_BTU_lbmol_tray=np.asarray(tray_thermo_prev.HV, dtype=float).reshape((N,)).copy(),
                Z_tray=np.asarray(tray_thermo_prev.Zfac_tray, dtype=float).reshape((N,)).copy(),
                cpL_BTU_lbmolF_tray=(
                    None
                    if tray_thermo_prev.cpL_tray is None
                    else np.asarray(tray_thermo_prev.cpL_tray, dtype=float).reshape((N,)).copy()
                ),
                cpV_BTU_lbmolF_tray=(
                    None
                    if tray_thermo_prev.cpV_tray is None
                    else np.asarray(tray_thermo_prev.cpV_tray, dtype=float).reshape((N,)).copy()
                ),
                T_tray_F=(
                    None
                    if tray_thermo_prev.T_state is None
                    else np.asarray(tray_thermo_prev.T_state, dtype=float).reshape((N,)).copy()
                ),
                P_tray_psia=(
                    None
                    if tray_thermo_prev.P_state is None
                    else np.asarray(tray_thermo_prev.P_state, dtype=float).reshape((N,)).copy()
                ),
                x_equilibrium_tray=(
                    None
                    if tray_thermo_prev.x_eq is None
                    else np.asarray(tray_thermo_prev.x_eq, dtype=float).reshape((N, Nc)).copy()
                ),
                y_equilibrium_tray=(
                    None
                    if tray_thermo_prev.y_eq is None
                    else np.asarray(tray_thermo_prev.y_eq, dtype=float).reshape((N, Nc)).copy()
                ),
            )
        except Exception:
            pass
    return TrayThermoPacket(
        z_overall_tray=np.asarray(z_overall_tray, dtype=float).reshape((N, Nc)).copy(),
        K_tray=(
            np.asarray(K_tray_prev, dtype=float).reshape((N, Nc)).copy()
            if K_tray_prev is not None
            else np.ones((N, Nc), dtype=float)
        ),
        HL_BTU_lbmol_tray=(
            np.asarray(HL_prev, dtype=float).reshape((N,)).copy()
            if HL_prev is not None
            else np.zeros(N, dtype=float)
        ),
        HV_BTU_lbmol_tray=(
            np.asarray(HV_prev, dtype=float).reshape((N,)).copy()
            if HV_prev is not None
            else np.zeros(N, dtype=float)
        ),
        Z_tray=(
            np.asarray(Zfac_prev, dtype=float).reshape((N,)).copy()
            if Zfac_prev is not None
            else np.ones(N, dtype=float)
        ),
        cpL_BTU_lbmolF_tray=None,
        cpV_BTU_lbmolF_tray=None,
    )


def _ensure_packet_equilibrium_arrays(packet: TrayThermoPacket, *, n_stages: int, n_components: int) -> None:
    if packet.x_eq is None:
        packet.x_equilibrium_tray = np.full((n_stages, n_components), np.nan, dtype=float)
    if packet.y_eq is None:
        packet.y_equilibrium_tray = np.full((n_stages, n_components), np.nan, dtype=float)


def _build_current_tray_thermo_refresh(
    *,
    col: ColumnSpec,
    layout: StateVectorLayout,
    inputs: ColumnInputs,
    u: dict[str, Any],
    diag: Optional[dict[str, np.ndarray]],
    tray_L: np.ndarray,
    tray_V: Optional[np.ndarray],
    x_tray: np.ndarray,
    P_tray_hyd: Optional[np.ndarray],
    n_stages: int,
    n_components: int,
):
    if inputs.thermo_provider is None:
        return None

    if "tray_T_f" in u:
        T_tray = np.asarray(u["tray_T_f"], dtype=float).reshape((n_stages,))
    elif hasattr(col, "T_f"):
        T_tray = np.asarray(col.T_f, dtype=float).reshape((n_stages,))
    else:
        T_tray = np.full(n_stages, 100.0, dtype=float)

    if hasattr(col, "P_psia"):
        P_tray = np.asarray(col.P_psia, dtype=float).reshape((n_stages,))
    elif diag is not None and "P_psia_diag" in diag:
        P_tray = np.asarray(diag["P_psia_diag"], dtype=float).reshape((n_stages,))
    else:
        P_tray = np.full(n_stages, 200.0, dtype=float)
    if P_tray_hyd is not None:
        try:
            P_tray = np.asarray(P_tray_hyd, dtype=float).reshape((n_stages,))
        except Exception:
            pass

    Z_overall = np.zeros((n_stages, n_components), dtype=float)
    for i in range(n_stages):
        z = tray_L[i, :].copy()
        if tray_V is not None:
            z = z + tray_V[i, :]
        s = float(np.sum(z))
        if s <= layout.epsilon_lbmol:
            z = x_tray[i, :].copy()
            s = float(np.sum(z))
        Z_overall[i, :] = z / max(s, 1e-300)

    thermo_packet = _seed_tray_thermo_packet(
        N=n_stages,
        Nc=n_components,
        z_overall_tray=Z_overall,
        tray_thermo_prev=inputs.tray_thermo_prev,
        K_tray_prev=inputs.K_tray_prev,
        HL_prev=inputs.HL_prev,
        HV_prev=inputs.HV_prev,
        Zfac_prev=inputs.Zfac_prev,
    )
    thermo_packet.T_tray_F = np.asarray(T_tray, dtype=float).reshape((n_stages,)).copy()
    thermo_packet.P_tray_psia = np.asarray(P_tray, dtype=float).reshape((n_stages,)).copy()

    dT_thresh = inputs.thermo_refresh_dT_F
    if dT_thresh is not None:
        try:
            dT_thresh = float(dT_thresh)
        except Exception:
            dT_thresh = None
    if dT_thresh is not None and (not np.isfinite(dT_thresh) or dT_thresh <= 0.0):
        dT_thresh = None

    T_prev = None
    if inputs.T_tray_prev_F is not None:
        try:
            T_prev = np.asarray(inputs.T_tray_prev_F, dtype=float).reshape((n_stages,))
        except Exception:
            T_prev = None
    if T_prev is None and inputs.tray_thermo_prev is not None and inputs.tray_thermo_prev.T_state is not None:
        try:
            T_prev = np.asarray(inputs.tray_thermo_prev.T_state, dtype=float).reshape((n_stages,))
        except Exception:
            T_prev = None

    dP_thresh = inputs.thermo_refresh_dP_psia
    if dP_thresh is not None:
        try:
            dP_thresh = float(dP_thresh)
        except Exception:
            dP_thresh = None
    if dP_thresh is not None and (not np.isfinite(dP_thresh) or dP_thresh <= 0.0):
        dP_thresh = None

    dX_thresh = inputs.thermo_refresh_dx
    if dX_thresh is not None:
        try:
            dX_thresh = float(dX_thresh)
        except Exception:
            dX_thresh = None
    if dX_thresh is not None and (not np.isfinite(dX_thresh) or dX_thresh <= 0.0):
        dX_thresh = None

    P_prev = None
    if inputs.P_tray_prev is not None:
        try:
            P_prev = np.asarray(inputs.P_tray_prev, dtype=float).reshape((n_stages,))
        except Exception:
            P_prev = None
    if P_prev is None and inputs.tray_thermo_prev is not None and inputs.tray_thermo_prev.P_state is not None:
        try:
            P_prev = np.asarray(inputs.tray_thermo_prev.P_state, dtype=float).reshape((n_stages,))
        except Exception:
            P_prev = None

    Z_prev = None
    if inputs.Z_overall_prev is not None:
        try:
            Z_prev = np.asarray(inputs.Z_overall_prev, dtype=float).reshape((n_stages, n_components))
        except Exception:
            Z_prev = None
    if Z_prev is None and inputs.tray_thermo_prev is not None:
        try:
            Z_prev = np.asarray(inputs.tray_thermo_prev.z_overall, dtype=float).reshape((n_stages, n_components))
        except Exception:
            Z_prev = None

    return refresh_tray_tp_packet(
        packet=thermo_packet,
        provider=inputs.thermo_provider,
        T_tray_F=T_tray,
        P_tray_psia=P_tray,
        z_overall_tray=Z_overall,
        n_stages=n_stages,
        n_components=n_components,
        dT_thresh_F=dT_thresh,
        dP_thresh_psia=dP_thresh,
        dX_thresh=dX_thresh,
        T_prev_F=T_prev,
        P_prev_psia=P_prev,
        z_prev=Z_prev,
        ensure_packet_equilibrium_arrays=_ensure_packet_equilibrium_arrays,
        flash_stage_fn=_flash_TP_full_stage_F_psia,
        trace_fn=_trace_stage_thermo,
        trace_context=inputs,
    )


def _compatible_feed_stage_flash_packet(
    *,
    packet: Optional[FeedStageFlashPacket],
    stage0: int,
    T_feed_F: float,
    P_feed_psia: float,
    z_feed: np.ndarray,
    n_components: int,
    max_abs_dT_F: float,
    max_abs_dP_psia: float,
    max_abs_dx: float,
) -> tuple[Optional[FeedStageFlashPacket], Optional[float], Optional[float], Optional[float]]:
    if packet is None or int(getattr(packet, "stage0", -999999)) != int(stage0):
        return None, None, None, None
    try:
        z_prev = np.asarray(packet.z_feed, dtype=float).reshape((n_components,))
        T_prev = float(packet.T_feed_F)
        P_prev = float(packet.P_feed_psia)
        dx_val = float(np.nanmax(np.abs(np.asarray(z_feed, dtype=float).reshape((n_components,)) - z_prev)))
    except Exception:
        return None, None, None, None
    dT_val = abs(float(T_feed_F) - T_prev)
    dP_val = abs(float(P_feed_psia) - P_prev)
    if (
        np.isfinite(T_prev)
        and np.isfinite(P_prev)
        and np.isfinite(dx_val)
        and dT_val <= float(max_abs_dT_F)
        and dP_val <= float(max_abs_dP_psia)
        and dx_val <= float(max_abs_dx)
    ):
        return packet, float(dT_val), float(dP_val), float(dx_val)
    return None, float(dT_val), float(dP_val), float(dx_val)


def _compatible_bottom_sump_cp_packet(
    packet: Optional[BottomSumpCpPacket],
    *,
    T_sump_F: float,
    P_sump_psia: float,
    x_sump: np.ndarray,
    n_components: int,
    max_abs_dT_F: float,
    max_abs_dP_psia: float,
    max_abs_dx: float,
) -> tuple[Optional[BottomSumpCpPacket], Optional[float], Optional[float], Optional[float]]:
    if packet is None:
        return None, None, None, None
    try:
        x_prev = np.asarray(packet.x_sump, dtype=float).reshape((n_components,))
        x_now = np.asarray(x_sump, dtype=float).reshape((n_components,))
        T_prev = float(packet.T_sump_F)
        P_prev = float(packet.P_sump_psia)
        cp_prev = float(packet.cpL_BTU_lbmolF)
        dx_val = float(np.nanmax(np.abs(x_now - x_prev)))
    except Exception:
        return None, None, None, None
    dT_val = abs(float(T_sump_F) - T_prev)
    dP_val = abs(float(P_sump_psia) - P_prev)
    if (
        np.isfinite(T_prev)
        and np.isfinite(P_prev)
        and np.isfinite(cp_prev)
        and np.isfinite(dx_val)
        and dT_val <= float(max_abs_dT_F)
        and dP_val <= float(max_abs_dP_psia)
        and dx_val <= float(max_abs_dx)
    ):
        return packet, float(dT_val), float(dP_val), float(dx_val)
    return None, float(dT_val), float(dP_val), float(dx_val)


def _packet_phase_enthalpy_if_compatible(
    packet: Optional[TrayThermoPacket],
    *,
    stage_index0: int,
    T_F: Optional[float] = None,
    P_psia: Optional[float] = None,
    phase_composition: np.ndarray,
    phase: str,
    max_abs_dx: float,
    max_abs_dT_F: Optional[float] = None,
    max_abs_dP_psia: Optional[float] = None,
) -> Optional[float]:
    if packet is None or (not np.isfinite(float(max_abs_dx))) or float(max_abs_dx) < 0.0:
        return None
    ref = packet.x_eq if str(phase).strip().lower() == "liquid" else packet.y_eq
    if ref is None:
        return None
    try:
        ref_i = np.asarray(ref, dtype=float).reshape((ref.shape[0], ref.shape[1]))[int(stage_index0), :]
        z_i = np.asarray(phase_composition, dtype=float).reshape((ref_i.size,))
    except Exception:
        return None
    if ref_i.size != z_i.size or not (np.all(np.isfinite(ref_i)) and np.all(np.isfinite(z_i))):
        return None
    if T_F is not None and max_abs_dT_F is not None:
        try:
            if packet.T_state is None:
                return None
            T_ref = float(np.asarray(packet.T_state, dtype=float).reshape((-1,))[int(stage_index0)])
            if (not np.isfinite(T_ref)) or abs(float(T_F) - T_ref) > float(max_abs_dT_F):
                return None
        except Exception:
            return None
    if P_psia is not None and max_abs_dP_psia is not None:
        try:
            if packet.P_state is None:
                return None
            P_ref = float(np.asarray(packet.P_state, dtype=float).reshape((-1,))[int(stage_index0)])
            if (not np.isfinite(P_ref)) or abs(float(P_psia) - P_ref) > float(max_abs_dP_psia):
                return None
        except Exception:
            return None
    if float(np.max(np.abs(ref_i - z_i))) > float(max_abs_dx):
        return None
    if str(phase).strip().lower() == "liquid":
        try:
            return float(np.asarray(packet.HL, dtype=float).reshape((-1,))[int(stage_index0)])
        except Exception:
            return None
    try:
        return float(np.asarray(packet.HV, dtype=float).reshape((-1,))[int(stage_index0)])
    except Exception:
        return None


def _packet_phase_enthalpy_first_match(
    packets: list[Optional[TrayThermoPacket]],
    *,
    stage_index0: int,
    T_F: Optional[float] = None,
    P_psia: Optional[float] = None,
    phase_composition: np.ndarray,
    phase: str,
    max_abs_dx: float,
    max_abs_dT_F: Optional[float] = None,
    max_abs_dP_psia: Optional[float] = None,
) -> Optional[float]:
    for packet in packets:
        h = _packet_phase_enthalpy_if_compatible(
            packet,
            stage_index0=stage_index0,
            T_F=T_F,
            P_psia=P_psia,
            phase_composition=phase_composition,
            phase=phase,
            max_abs_dx=max_abs_dx,
            max_abs_dT_F=max_abs_dT_F,
            max_abs_dP_psia=max_abs_dP_psia,
        )
        if h is not None and np.isfinite(float(h)):
            return float(h)
    return None


def _packet_phase_cp_from_packets(
    current_packet: Optional[TrayThermoPacket],
    previous_packet: Optional[TrayThermoPacket],
    *,
    stage_index0: int,
    phase: str,
    max_abs_dx: float,
    max_abs_dP_psia: float,
    min_abs_dT_F: float = 0.1,
) -> Optional[float]:
    if current_packet is None or previous_packet is None:
        return None
    phase_norm = str(phase).strip().lower()
    if phase_norm == "vapor":
        comp_curr = current_packet.y_eq
        comp_prev = previous_packet.y_eq
        h_curr_all = current_packet.HV
        h_prev_all = previous_packet.HV
    else:
        comp_curr = current_packet.x_eq
        comp_prev = previous_packet.x_eq
        h_curr_all = current_packet.HL
        h_prev_all = previous_packet.HL

    T_curr_all = current_packet.T_state
    T_prev_all = previous_packet.T_state
    P_curr_all = current_packet.P_state
    P_prev_all = previous_packet.P_state
    if (
        comp_curr is None
        or comp_prev is None
        or h_curr_all is None
        or h_prev_all is None
        or T_curr_all is None
        or T_prev_all is None
        or P_curr_all is None
        or P_prev_all is None
    ):
        return None
    try:
        comp_curr_i = np.asarray(comp_curr[stage_index0], dtype=float).reshape((-1,))
        comp_prev_i = np.asarray(comp_prev[stage_index0], dtype=float).reshape((-1,))
        h_curr = float(np.asarray(h_curr_all, dtype=float).reshape((-1,))[stage_index0])
        h_prev = float(np.asarray(h_prev_all, dtype=float).reshape((-1,))[stage_index0])
        T_curr = float(np.asarray(T_curr_all, dtype=float).reshape((-1,))[stage_index0])
        T_prev = float(np.asarray(T_prev_all, dtype=float).reshape((-1,))[stage_index0])
        P_curr = float(np.asarray(P_curr_all, dtype=float).reshape((-1,))[stage_index0])
        P_prev = float(np.asarray(P_prev_all, dtype=float).reshape((-1,))[stage_index0])
    except Exception:
        return None
    if (
        (not np.all(np.isfinite(comp_curr_i)))
        or (not np.all(np.isfinite(comp_prev_i)))
        or (not np.isfinite(h_curr))
        or (not np.isfinite(h_prev))
        or (not np.isfinite(T_curr))
        or (not np.isfinite(T_prev))
        or (not np.isfinite(P_curr))
        or (not np.isfinite(P_prev))
    ):
        return None
    if comp_curr_i.size != comp_prev_i.size or comp_curr_i.size == 0:
        return None
    if np.max(np.abs(comp_curr_i - comp_prev_i)) > float(max_abs_dx):
        return None
    if abs(P_curr - P_prev) > float(max_abs_dP_psia):
        return None
    dT = float(T_curr - T_prev)
    if abs(dT) < float(min_abs_dT_F):
        return None
    cp_est = float((h_curr - h_prev) / dT)
    if (not np.isfinite(cp_est)) or cp_est <= 1.0e-9:
        return None
    return cp_est


def _phase_cp_from_current_enthalpy_and_packet(
    previous_packet: Optional[TrayThermoPacket],
    *,
    stage_index0: int,
    current_enthalpy_btu_per_lbmol: float,
    current_T_F: float,
    current_P_psia: float,
    current_phase_composition: np.ndarray,
    phase: str,
    max_abs_dx: float,
    max_abs_dP_psia: float,
    min_abs_dT_F: float = 0.1,
) -> Optional[float]:
    if previous_packet is None:
        return None
    phase_norm = str(phase).strip().lower()
    if phase_norm == "vapor":
        comp_prev = previous_packet.y_eq
        h_prev_all = previous_packet.HV
    else:
        comp_prev = previous_packet.x_eq
        h_prev_all = previous_packet.HL
    T_prev_all = previous_packet.T_state
    P_prev_all = previous_packet.P_state
    if comp_prev is None or h_prev_all is None or T_prev_all is None or P_prev_all is None:
        return None
    try:
        comp_prev_i = np.asarray(comp_prev[stage_index0], dtype=float).reshape((-1,))
        h_prev = float(np.asarray(h_prev_all, dtype=float).reshape((-1,))[stage_index0])
        T_prev = float(np.asarray(T_prev_all, dtype=float).reshape((-1,))[stage_index0])
        P_prev = float(np.asarray(P_prev_all, dtype=float).reshape((-1,))[stage_index0])
        comp_curr = np.asarray(current_phase_composition, dtype=float).reshape((-1,))
        h_curr = float(current_enthalpy_btu_per_lbmol)
        T_curr = float(current_T_F)
        P_curr = float(current_P_psia)
    except Exception:
        return None
    if (
        comp_curr.size != comp_prev_i.size
        or comp_curr.size == 0
        or (not np.all(np.isfinite(comp_curr)))
        or (not np.all(np.isfinite(comp_prev_i)))
        or (not np.isfinite(h_prev))
        or (not np.isfinite(h_curr))
        or (not np.isfinite(T_prev))
        or (not np.isfinite(T_curr))
        or (not np.isfinite(P_prev))
        or (not np.isfinite(P_curr))
    ):
        return None
    if np.max(np.abs(comp_curr - comp_prev_i)) > float(max_abs_dx):
        return None
    if abs(P_curr - P_prev) > float(max_abs_dP_psia):
        return None
    dT = float(T_curr - T_prev)
    if abs(dT) < float(min_abs_dT_F):
        return None
    cp_est = float((h_curr - h_prev) / dT)
    if (not np.isfinite(cp_est)) or cp_est <= 1.0e-9:
        return None
    return cp_est


def _packet_cp_if_compatible(
    packet: Optional[TrayThermoPacket],
    *,
    stage_index0: int,
    T_F: float,
    P_psia: float,
    z_overall: np.ndarray,
    phase: str,
    max_abs_dx: float,
    max_abs_dT_F: Optional[float] = None,
    max_abs_dP_psia: Optional[float] = None,
) -> Optional[float]:
    if packet is None:
        return None
    cp_arr = packet.cpV_tray if str(phase).strip().lower() == "vapor" else packet.cpL_tray
    if cp_arr is None or packet.z_overall is None:
        return None
    try:
        cp_val = float(np.asarray(cp_arr, dtype=float).reshape((-1,))[int(stage_index0)])
        z_ref = np.asarray(packet.z_overall, dtype=float).reshape((packet.z_overall.shape[0], packet.z_overall.shape[1]))[
            int(stage_index0), :
        ]
        z_now = np.asarray(z_overall, dtype=float).reshape((z_ref.size,))
    except Exception:
        return None
    if (not np.isfinite(cp_val)) or (not np.all(np.isfinite(z_ref))) or (not np.all(np.isfinite(z_now))):
        return None
    if float(np.max(np.abs(z_ref - z_now))) > float(max_abs_dx):
        return None
    if max_abs_dT_F is not None:
        try:
            if packet.T_state is None:
                return None
            T_ref = float(np.asarray(packet.T_state, dtype=float).reshape((-1,))[int(stage_index0)])
            if (not np.isfinite(T_ref)) or abs(float(T_F) - T_ref) > float(max_abs_dT_F):
                return None
        except Exception:
            return None
    if max_abs_dP_psia is not None:
        try:
            if packet.P_state is None:
                return None
            P_ref = float(np.asarray(packet.P_state, dtype=float).reshape((-1,))[int(stage_index0)])
            if (not np.isfinite(P_ref)) or abs(float(P_psia) - P_ref) > float(max_abs_dP_psia):
                return None
        except Exception:
            return None
    return cp_val


def _phase_reuse_dx_tol(inputs: Any, phase: str) -> float:
    phase_norm = str(phase).strip().lower()
    if phase_norm == "vapor":
        try:
            vapor_tol = getattr(inputs, "thermo_packet_vapor_reuse_dx", None)
            if vapor_tol is not None:
                vapor_tol = float(vapor_tol)
                if np.isfinite(vapor_tol) and vapor_tol >= 0.0:
                    return float(vapor_tol)
        except Exception:
            pass
    try:
        base_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dx", 0.0) or 0.0)
        if np.isfinite(base_tol) and base_tol >= 0.0:
            return float(base_tol)
    except Exception:
        pass
    return 0.0


def _flash_TP_full_stage_F_psia(
    provider: Any,
    stage_index0: Optional[int],
    T_F: float,
    P_psia: float,
    z: np.ndarray | list[float],
    *,
    n_components: int,
    thermo_call_category: Optional[str] = None,
):
    with _thermo_provider_category(provider, thermo_call_category):
        return flash_TP_full_F_psia(
            provider,
            float(T_F),
            float(P_psia),
            z,
            n_components=n_components,
            stage_index0=stage_index0,
        )


def _thermo_provider_category(provider: Any, category: Optional[str]):
    if provider is None:
        return nullcontext()
    fn = getattr(provider, "thermo_call_category", None)
    if callable(fn):
        try:
            return fn(category)
        except Exception:
            return nullcontext()
    return nullcontext()


def _record_thermo_provider_counter(
    provider: Any,
    metric: str,
    amount: float = 1,
    *,
    category: Optional[str] = None,
) -> None:
    if provider is None:
        return
    fn = getattr(provider, "_record_call_counter", None)
    if not callable(fn):
        return
    try:
        fn(metric, amount, category=category)
    except Exception:
        pass


def _provider_cp_liq_vap_btu_per_lbmolF(
    provider: Any,
    T_F: float,
    P_psia: float,
    z: np.ndarray | list[float],
    *,
    thermo_call_category: Optional[str] = None,
):
    with _thermo_provider_category(provider, thermo_call_category):
        return provider.cp_liq_vap_btu_per_lbmolF(float(T_F), float(P_psia), z)


@dataclass(frozen=True)
class BoundaryFlows:
    reflux_lbmolph: Optional[float] = None
    boilup_lbmolph: Optional[float] = None
    distillate_lbmolph: Optional[float] = None
    bottoms_lbmolph: Optional[float] = None


@dataclass(frozen=True)
class VolumeModel:
    vapor_volume_ft3_per_stage: Optional[np.ndarray] = None
    default_vapor_volume_ft3: float = 1.0


@dataclass(frozen=True)
class ColumnInputs:
    boundary: BoundaryFlows = BoundaryFlows()
    volume_model: VolumeModel = VolumeModel()
    # Runtime behavior mode passed through from the runner. The RHS uses this
    # only for modes that alter boundary topology, such as total reflux startup.
    runtime_mode: str = "legacy"

    condenser_alpha: Optional[float] = None
    clamp_alpha: bool = True
    # Condenser duty handling:
    #   "total-condense" = compute duty by condensing all stage-2 vapor (current behavior)
    #   "specified"      = use specified/overridden condenser duty directly
    condenser_duty_mode: str = "total-condense"
    condenser_duty_btu_per_h: Optional[float] = None
    # Optional duty trim applied on top of computed total-condense duty.
    condenser_duty_trim_btu_per_h: Optional[float] = None
    # When True, total-condense mode may still allow duty-limited vapor slip
    # to the top drum. This is used for explicitly coupled condenser-duty
    # pressure-control runs so the MV has real mass-split authority instead of
    # acting only as an energy trim on a forced full-condensation split.
    condenser_duty_partial_condense_if_limited: bool = False
    # When False, skip the live thermo-based total-condenser duty solve and
    # use the specified/base condenser duty path instead.
    enable_live_total_condenser_duty: bool = True
    # Optional previous-step total-condenser solve for conservative reuse
    # when the inlet vapor state is effectively unchanged.
    condenser_duty_prev: Optional[CondenserDutyPacket] = None
    condenser_duty_reuse_dT_F: float = 0.5
    condenser_duty_reuse_dP_psia: float = 0.25
    condenser_duty_reuse_dx: float = 0.01
    condenser_duty_reuse_dV_rel: float = 0.02
    # Bubble-state reuse is narrower than full-packet reuse: it only carries
    # forward the condenser bubble point / condensed-liquid enthalpy while
    # still recomputing the current vapor enthalpy. Allowing a larger pressure
    # window here can avoid expensive pressure-only bubble-point resolves
    # without reusing the full prior duty solve.
    condenser_duty_bubble_state_reuse_dP_psia: float = 50.0

    # Legacy temperature-state energy model (only used when layout.include_temperature=True)
    thermo: Optional[ThermoModel] = None
    enable_legacy_temperature_state: bool = True

    # Module 7: optional thermo diagnostics hook
    thermo_provider: Optional[Any] = None
    # Optional live-thermo override used only for the equilibrium-relaxation
    # flash target. This keeps the main thermo path/caching unchanged while
    # allowing a selective PR check in the phase-relaxation driver.
    equilibrium_relaxation_thermo_provider: Optional[Any] = None
    compute_thermo_diag: bool = False

    # Module 8B: equilibrium relaxation using K
    equilibrium_relaxation: bool = False
    tau_eq_sec: Optional[float] = None   # <-- changed: allow None so we can fall back to ColumnSpec
    equilibrium_tau_ramp_initial_sec: Optional[float] = None
    equilibrium_tau_ramp_final_sec: Optional[float] = None
    equilibrium_tau_ramp_decay_sec: Optional[float] = None
    # Equilibrium transfer target:
    #   "phase-holdup"     = relax vapor holdup toward flash phase split (legacy)
    #   "composition-only" = relax only vapor composition at fixed MV_tot
    equilibrium_relaxation_mode: str = "phase-holdup"
    # Smoothly back off phase-holdup relaxation on near-empty vapor trays.
    # When current and flash-target vapor holdups are both small relative to
    # this guard, the target blends toward current tray vapor inventory
    # instead of collapsing abruptly to the flash phase split.
    equilibrium_phase_holdup_guard_lbmol: float = 0.0
    # Optional previous-step tray energy-balance residuals (BTU/s) used to
    # damp phase-holdup relaxation on the next step without introducing a
    # same-step circular dependency.
    energy_balance_resid_prev_BTUps_tray: Optional[np.ndarray] = None
    # Sensitivity for energy-aware damping of phase-holdup relaxation.
    # Zero disables this path.
    equilibrium_energy_damping_gain: float = 0.0
    # Optional scalar damping applied to the tray temperature derivative in
    # hydraulic+energy runs to keep the temperature path from competing too
    # aggressively with the energy-based vapor-flow closure.
    hydraulic_energy_temperature_damping: float = 1.0
    # Optional hydraulic+energy tray temperature mode.
    # "legacy" uses the historical dE/C path.
    # "bubble-point-follower" relaxes temperature toward the liquid
    # bubble-point target at current pressure/composition plus a small residual
    # correction term.
    # "pressure-correction-follower" uses a damped dE/C term plus an
    # immediate pressure-tracking correction based on dP over a short
    # follower timescale, avoiding explicit bubble-point solves.
    # "enthalpy-state-follower" uses the tray EL/EV holdup states as the
    # thermal truth and relaxes temperature toward the state-implied
    # mixed-enthalpy target, avoiding a second direct dE/C solve.
    hydraulic_energy_temperature_mode: str = "legacy"
    hydraulic_energy_temperature_follow_tau_sec: float = 0.5
    hydraulic_energy_temperature_resid_frac: float = 0.01
    hydraulic_energy_temperature_pressure_slope_F_per_psi: float = 2.0
    tray_temp_pressure_slope_prev_F_per_psi: Optional[np.ndarray] = None
    tray_bubble_target_prev_F: Optional[np.ndarray] = None
    # Optional previous-step monotone minimum damping by tray for below-feed
    # phase-holdup ratcheting.
    phase_energy_damping_min_prev_tray: Optional[np.ndarray] = None
    # Low-holdup phase-transfer stabilization. These guards only act on the
    # equilibrium relaxation source term and are intended to keep nearly dry
    # trays from vaporizing or condensing phase inventory faster than the tray
    # can physically support.
    equilibrium_phase_rate_liquid_guard_lbmol: float = 1.0
    equilibrium_phase_rate_vapor_guard_lbmol: float = 1.0
    equilibrium_phase_rate_max_frac_per_tau: float = 0.5
    # Low-holdup temperature stabilization for hydraulic+energy runs. When a
    # tray's thermal mass collapses, floor the effective heat capacity and cap
    # the legacy dE/C temperature derivative so one explicit step cannot send
    # the tray temperature nonphysical.
    hydraulic_energy_temperature_holdup_guard_lbmol: float = 1.0
    hydraulic_energy_temperature_min_heat_capacity_BTU_per_F: float = 25.0
    hydraulic_energy_temperature_max_dT_rate_F_per_s: float = 10.0

    # Reboiler handling
    # reboiler_mode:
    #   "specified" = use boundary.boilup_lbmolph or ColumnSpec.V_lbmolph[-1]
    #   "duty"      = compute boilup from reboiler duty (requires thermo_provider)
    #   "auto"      = duty if available else specified
    reboiler_mode: str = "auto"
    # Optional reboiler duty override / trim used when reboiler_mode resolves to duty.
    reboiler_duty_btu_per_h: Optional[float] = None
    reboiler_duty_trim_btu_per_h: Optional[float] = None
    reboiler_equilibrium: bool = True

    # Pressure model
    # "spec"      = use ColumnSpec.P_psia
    # "hydraulic" = compute from vapor flow + geometry (anchored at bottom)
    pressure_model: str = "spec"
    # Optional top-pressure anchor (psia) for hydraulic profile control.
    pressure_top_anchor_psia: Optional[float] = None
    # When True, and no explicit top anchor is provided, use the current
    # top-drum pressure state as the hydraulic top anchor. This is intended
    # for condenser-duty pressure-control runs where the controlled drum PV
    # should remain hydraulically coupled to the tray-pressure profile.
    hydraulic_use_top_drum_pressure_as_anchor: bool = False
    # Optional fixed condenser pressure drop (psi), applied stage 2 -> stage 1
    # in hydraulic pressure-profile mode.
    condenser_pressure_drop_psi: Optional[float] = None
    # Vapor-space volume for reflux drum / top accumulator pressure state.
    # If not provided, stage-1 vapor volume from volume_model is used.
    top_drum_vapor_volume_ft3: Optional[float] = None
    # Optional additional vapor-only capacitance (e.g. condenser shell + overhead
    # line) that is added on top of any dynamic drum headspace.
    top_drum_extra_vapor_volume_ft3: Optional[float] = None
    # Optional total reflux-drum volume for dynamic vapor-space update:
    # V_vap = V_total - V_liq(top holdup, rho_liq).
    top_drum_total_volume_ft3: Optional[float] = None
    # Optional total bottom-sump volume for scaffold-side level calculations.
    bottom_sump_total_volume_ft3: Optional[float] = None
    # Optional top-drum PSV relief model:
    # V_psv = clamp(gain * max(P_top_drum - setpoint, 0), 0, max_vent)
    enable_top_drum_psv: bool = False
    top_drum_psv_setpoint_psia: Optional[float] = None
    top_drum_psv_gain_lbmolps_per_psi: Optional[float] = None
    top_drum_psv_max_vent_lbmolps: Optional[float] = None
    # Enforce forward pressure driving force on stage-2 -> top-drum vapor slip.
    # If enabled, uncondensed slip to top vapor is smoothly reduced as
    # (P_stage2 - P_top_drum - condenser_dp) approaches/below zero.
    enforce_top_drum_pressure_gate: bool = True
    # Soft transition width (psi) for the pressure gate. If None or <=0, use
    # a hard gate at zero driving force.
    top_drum_pressure_gate_soft_psi: Optional[float] = 0.25
    # Optional low-pass timescale (sec) for hydraulic tray pressure updates.
    # If None, vapor_holdup_relaxation_sec is reused for backward compatibility.
    hydraulic_pressure_relaxation_sec: Optional[float] = None
    # Optional low-pass timescale (sec) on stage-1 temperature used for
    # ideal-gas top-drum pressure. Default 5 s damps startup temperature shocks.
    # Set <=0 to disable this specific smoothing path.
    top_drum_pressure_temperature_relaxation_sec: Optional[float] = 5.0
    # Optional previous filtered top-drum pressure temperature (F). When
    # provided, this is used as the lag state instead of previous tray-1 T.
    top_drum_pressure_T_prev_F: Optional[float] = None
    # Enforce physically ordered top-end pressures after hydraulic solve:
    # condenser tray pressure should not fall below top-drum pressure.
    enforce_top_pressure_ordering: bool = True
    # Optional minimum margin for P_stage1 - P_top_drum (psi).
    top_pressure_ordering_margin_psi: float = 0.0
    # Generic free-pressure path: keep tray-to-tray hydraulic pressure on its
    # own profile when there is no explicit top anchor, but prevent the top tray
    # and reflux drum from drifting arbitrarily far apart.
    enforce_top_drum_pressure_continuity: bool = False
    top_drum_pressure_continuity_max_gap_psi: float = 1.0
    # Vapor flow model
    # "profile" = use Excel V profile (or feed-adjusted profile)
    # "energy"  = compute V_out from energy balance with dT/dt target
    # "conductance" = compute V_out from tray-to-tray pressure conductance
    vapor_flow_model: str = "profile"
    # Initialization-only homotopy for dynamic vapor closures. When set and
    # vapor_flow_model is dynamic, the active vapor traffic is blended as:
    #   (1-beta) * profile_flow + beta * dynamic_flow.
    vapor_flow_homotopy_beta: Optional[float] = None
    # Diagnostic-only: freeze explicit tray vapor derivatives after transport
    # assembly to test profile-flow parity closure without changing normal runs.
    debug_freeze_tray_vapor_derivatives: bool = False
    # Diagnostic-only: force reflux composition entering stage 2 to match the
    # vapor composition being condensed into the top boundary. This isolates
    # reflux-loop composition closure from the rest of the upper-column balance.
    debug_override_reflux_composition: bool = False
    # Diagnostic/initialization-only: override the computed top-drum pressure
    # used by hydraulic boundary logic. This is intended for clamped physical
    # settle probes; accepted restart states must still pass unclamped audits.
    debug_clamp_top_drum_pressure_psia: Optional[float] = None
    debug_clamp_top_drum_pressure_duration_sec: Optional[float] = None
    # Total-reflux startup ramp. In total-reflux mode the active boilup and
    # reboiler duty are multiplied by this first-order factor:
    #   min + (1-min) * (1 - exp(-t/tau)).
    total_reflux_startup_ramp_tau_sec: Optional[float] = None
    total_reflux_startup_min_ramp_fraction: float = 0.0
    total_reflux_scale_reflux_with_startup_factor: bool = False
    total_reflux_boundary_ramp_duration_sec: Optional[float] = None
    dry_tray_K: float = 1.0
    vapor_holdup_relaxation_sec: Optional[float] = None
    component_mw_lbm_per_lbmol: Optional[np.ndarray] = None
    P_tray_prev: Optional[np.ndarray] = None
    vapor_flow_relaxation_sec: Optional[float] = None
    # Conductance-mode vapor-flow nominal-profile high clamp ratio.
    # If None, default internal value is used.
    conductance_vflow_nominal_hi_ratio: Optional[float] = None
    # Optional smooth clamp width (lbmol/s) for internal vapor-flow limiters.
    # <=0 or None keeps legacy hard min/max clipping.
    vflow_smooth_clamp_epsilon_lbmolps: Optional[float] = None
    # When False, energy vapor-flow closure uses the lightweight thermo Cp model
    # instead of live provider Cp. Provider enthalpies are still used when
    # available. This keeps hydraulic/energy runs from paying for a full live
    # Cp flash path on every tray update.
    energy_vapor_flow_use_provider_cp: bool = False
    V_out_prev_lbmolph: Optional[np.ndarray] = None
    dT_tray_target_F_per_s: Optional[np.ndarray] = None
    thermo_refresh_dT_F: Optional[float] = None
    thermo_refresh_dP_psia: Optional[float] = None
    thermo_refresh_dx: Optional[float] = None
    T_tray_prev_F: Optional[np.ndarray] = None
    Z_overall_prev: Optional[np.ndarray] = None
    # Conservative composition tolerance for reusing same-step main-flash
    # liquid/vapor enthalpies in downstream helper paths.
    thermo_packet_phase_reuse_dx: float = 5.0e-3
    # Vapor compositions tend to move more than liquid compositions in live
    # tray updates, so allow a looser vapor-side match before forcing a reflash.
    thermo_packet_vapor_reuse_dx: Optional[float] = 3.0e-2
    thermo_packet_phase_reuse_dT_F: float = 1.0
    thermo_packet_phase_reuse_dP_psia: float = 0.5
    # Clamp for stage N-1 vapor flow as a ratio of boilup in energy mode.
    # Wider defaults reduce hard-clip lock-in while still preventing blow-up.
    reboiler_neighbor_vflow_hi_ratio: float = 1.20
    reboiler_neighbor_vflow_lo_ratio: float = 0.80
    # When True and thermo_provider is available, split feed with a TP flash
    # at feed-stage pressure instead of using stream vapor_fraction directly.
    flash_feed_at_stage_conditions: bool = True
    # Optional previous feed flash packet for conservative reuse when the
    # feed state and feed-stage pressure are effectively unchanged.
    feed_stage_flash_prev: Optional[FeedStageFlashPacket] = None
    feed_stage_flash_reuse_dT_F: float = 0.5
    feed_stage_flash_reuse_dP_psia: float = 2.5
    feed_stage_flash_reuse_dx: float = 1.0e-6
    bottom_sump_cp_prev: Optional[BottomSumpCpPacket] = None
    bottom_sump_cp_reuse_dT_F: float = 0.5
    bottom_sump_cp_reuse_dP_psia: float = 5.0
    bottom_sump_cp_reuse_dx: float = 1.0e-5
    # Internal liquid hydraulics override for stages 2..N-1.
    # When disabled, internal liquid downflow stays on the profile values.
    enable_liquid_hydraulic_override: bool = True
    # Blend between profile and hydraulic internal liquid downflow:
    # 0.0 = profile-only, 1.0 = full hydraulic override.
    liquid_hydraulic_override_alpha: float = 1.0
    # Optional per-stage hydraulic blend override. When provided, this takes
    # precedence over the scalar alpha for the corresponding stages.
    liquid_hydraulic_override_alpha_per_stage: Optional[np.ndarray] = None
    # Internal liquid hydraulics model:
    # "francis" = Francis weir outflow based on tray holdup and geometry
    liquid_hydraulic_model: str = "francis"
    liquid_hydraulic_htc_sec: Optional[float] = None

    # Optional: cached liquid density per stage (lbmol/ft3) for hydraulics throttling
    rhoL_tray_lbmol_ft3: Optional[np.ndarray] = None

    # Optional: cached thermo results for fallback on flash failure
    tray_thermo_prev: Optional[TrayThermoPacket] = None
    K_tray_prev: Optional[np.ndarray] = None
    HL_prev: Optional[np.ndarray] = None
    HV_prev: Optional[np.ndarray] = None
    Zfac_prev: Optional[np.ndarray] = None

    # Reboiler flash cache (used when duty flash fails)
    reb_T_prev: Optional[float] = None
    reb_x_prev: Optional[np.ndarray] = None
    reb_y_prev: Optional[np.ndarray] = None
    reb_beta_prev: Optional[float] = None
    # Optional runner-supplied progress hook for deep startup diagnostics.
    progress_hook: Optional[Any] = None
    trace_stage_thermo: bool = False
    thermo_stage_trace_label: Optional[str] = None


def _finite_positive_or_zero(value: Any) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if (not np.isfinite(v)) or v <= 0.0:
        return 0.0
    return v


def _trace_stage_thermo(inputs: ColumnInputs, message: str) -> None:
    if not bool(getattr(inputs, "trace_stage_thermo", False)):
        return
    hook = getattr(inputs, "progress_hook", None)
    if not callable(hook):
        return
    label = str(getattr(inputs, "thermo_stage_trace_label", "") or "").strip()
    text = str(message)
    if label:
        text = f"[ThermoTrace][{label}] {text}"
    else:
        text = f"[ThermoTrace] {text}"
    try:
        hook(text)
    except Exception:
        pass


def _softplus_scaled(x: float, eps: float) -> float:
    """
    Stable softplus approximation of max(x, 0) with width eps.
    """
    eps_f = _finite_positive_or_zero(eps)
    if eps_f <= 0.0:
        return max(float(x), 0.0)
    z = float(x) / eps_f
    if z > 50.0:
        return float(x)
    if z < -50.0:
        return 0.0
    return eps_f * float(np.log1p(np.exp(-abs(z))) + max(z, 0.0))


def _pressure_gate_scale(dp_psia: float, gate_soft_psi: Optional[float]) -> float:
    """Smooth or hard pressure-gate scale in [0, 1] from driving force."""
    try:
        dp = float(dp_psia)
    except Exception:
        dp = np.nan
    if not np.isfinite(dp):
        return float("nan")
    if gate_soft_psi is None:
        return 1.0 if dp > 0.0 else 0.0
    try:
        gate_soft = float(gate_soft_psi)
    except Exception:
        gate_soft = np.nan
    if np.isfinite(gate_soft) and gate_soft > 1.0e-12:
        return float(np.clip(0.5 * (1.0 + np.tanh(dp / gate_soft)), 0.0, 1.0))
    return 1.0 if dp > 0.0 else 0.0


def _smooth_max_scalar(a: float, b: float, eps: float) -> float:
    eps_f = _finite_positive_or_zero(eps)
    if eps_f <= 0.0:
        return max(float(a), float(b))
    da = float(a) - float(b)
    return 0.5 * (float(a) + float(b) + float(np.sqrt(da * da + eps_f * eps_f)))


def _smooth_min_scalar(a: float, b: float, eps: float) -> float:
    eps_f = _finite_positive_or_zero(eps)
    if eps_f <= 0.0:
        return min(float(a), float(b))
    da = float(a) - float(b)
    return 0.5 * (float(a) + float(b) - float(np.sqrt(da * da + eps_f * eps_f)))


def _smooth_clip_scalar(v: float, lo: float, hi: float, eps: float) -> float:
    lo_f = float(min(lo, hi))
    hi_f = float(max(lo, hi))
    eps_f = _finite_positive_or_zero(eps)
    if eps_f <= 0.0:
        return float(np.clip(float(v), lo_f, hi_f))
    # lo + relu(v-lo) - relu(v-hi), with relu replaced by softplus.
    return float(
        lo_f
        + _softplus_scaled(float(v) - lo_f, eps_f)
        - _softplus_scaled(float(v) - hi_f, eps_f)
    )


def _layout_slices(layout: StateVectorLayout) -> Dict[str, slice]:
    if hasattr(layout, "slices") and callable(getattr(layout, "slices")):
        return layout.slices()
    if hasattr(layout, "_build_slices") and callable(getattr(layout, "_build_slices")):
        sl = layout._build_slices()
        if "__n_states__" in sl:
            sl = dict(sl)
            sl.pop("__n_states__", None)
        return sl
    raise ColumnRHSError("StateVectorLayout does not expose slices() or _build_slices().")


def _limit_equilibrium_phase_transfer_rates(
    transfer_lbmolps: np.ndarray,
    *,
    ML_tot_lbmol: np.ndarray,
    MV_tot_lbmol: np.ndarray,
    tau_sec: float,
    liquid_guard_lbmol: float = 0.0,
    vapor_guard_lbmol: float = 0.0,
    max_frac_per_tau: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Scale equilibrium phase-transfer rows so near-dry trays cannot vaporize or
    condense phase inventory faster than a guarded fraction of available
    holdup per tau.
    """
    transfer = np.asarray(transfer_lbmolps, dtype=float)
    if transfer.ndim != 2:
        raise ValueError("transfer_lbmolps must be a 2D array")
    n_stages = transfer.shape[0]
    ML = np.asarray(ML_tot_lbmol, dtype=float).reshape((n_stages,))
    MV = np.asarray(MV_tot_lbmol, dtype=float).reshape((n_stages,))
    adjusted = transfer.copy()
    scale = np.ones(n_stages, dtype=float)
    limit = np.full(n_stages, np.nan, dtype=float)

    try:
        tau = float(tau_sec)
    except Exception:
        tau = np.nan
    try:
        frac = float(max_frac_per_tau)
    except Exception:
        frac = np.nan
    if (not np.isfinite(tau)) or tau <= 0.0 or (not np.isfinite(frac)) or frac <= 0.0:
        return adjusted, scale, limit

    liq_guard = max(float(liquid_guard_lbmol), 0.0) if np.isfinite(liquid_guard_lbmol) else 0.0
    vap_guard = max(float(vapor_guard_lbmol), 0.0) if np.isfinite(vapor_guard_lbmol) else 0.0

    net_transfer = np.sum(adjusted, axis=1).reshape((n_stages,))
    for i in range(n_stages):
        net_i = float(net_transfer[i])
        if (not np.isfinite(net_i)) or abs(net_i) <= 1.0e-15:
            continue
        if net_i > 0.0:
            available = max(float(ML[i]) - liq_guard, 0.0)
        else:
            available = max(float(MV[i]) - vap_guard, 0.0)
        limit_i = float(frac) * float(available) / float(tau)
        limit[i] = limit_i
        if abs(net_i) <= limit_i + 1.0e-15:
            continue
        if limit_i <= 0.0:
            adjusted[i, :] = 0.0
            scale[i] = 0.0
            continue
        fac = float(limit_i / abs(net_i))
        adjusted[i, :] = adjusted[i, :] * fac
        scale[i] = fac

    return adjusted, scale, limit


def _stabilize_low_holdup_temperature_rate(
    *,
    dE_BTU_per_s: float,
    heat_capacity_BTU_per_F: float,
    liquid_holdup_lbmol: float,
    vapor_holdup_lbmol: float,
    holdup_guard_lbmol: float = 0.0,
    min_heat_capacity_BTU_per_F: float = 0.0,
    max_abs_rate_F_per_s: Optional[float] = None,
) -> tuple[float, float, float]:
    """
    Return a stabilized tray temperature derivative for low-holdup states.

    Returns `(dT_use, effective_heat_capacity, guard_active_flag)`.
    """
    dE = float(dE_BTU_per_s)
    C = float(heat_capacity_BTU_per_F)
    ML = max(float(liquid_holdup_lbmol), 0.0)
    MV = max(float(vapor_holdup_lbmol), 0.0)
    guard = max(float(holdup_guard_lbmol), 0.0) if np.isfinite(holdup_guard_lbmol) else 0.0
    min_C = max(float(min_heat_capacity_BTU_per_F), 0.0) if np.isfinite(min_heat_capacity_BTU_per_F) else 0.0
    max_rate = None
    if max_abs_rate_F_per_s is not None and np.isfinite(float(max_abs_rate_F_per_s)):
        max_rate = max(float(max_abs_rate_F_per_s), 0.0)

    low_holdup = (guard > 0.0) and ((ML <= guard) or ((ML + MV) <= guard))
    if (not np.isfinite(C)) or C <= 0.0:
        if low_holdup or min_C > 0.0:
            C = max(min_C, 1.0e-12)
        else:
            raise ColumnRHSError("Non-positive tray heat capacity encountered.")

    guard_active = False
    C_eff = C
    if low_holdup and min_C > 0.0 and C_eff < min_C:
        C_eff = min_C
        guard_active = True

    dT_use = float(dE / C_eff)
    if low_holdup and max_rate is not None and max_rate > 0.0:
        dT_clipped = float(np.clip(dT_use, -max_rate, max_rate))
        if dT_clipped != dT_use:
            guard_active = True
        dT_use = dT_clipped

    return dT_use, float(C_eff), float(1.0 if guard_active else 0.0)


def _energy_derivatives_b1(
    *,
    L_out: np.ndarray,
    V_out: np.ndarray,
    ML_tot: np.ndarray,
    MV_tot: np.ndarray,
    EL_BTU: np.ndarray,
    EV_BTU: np.ndarray,
    Q_cond_BTUph: float,
    Q_reb_BTUph: float,
    epsilon_lbmol: float,
    Q_feed_BTUps: Optional[np.ndarray] = None,
    total_condenser: bool = True,
    max_abs_h_btu_per_lbmol: float = 1.0e6,
    no_liquid_holdup_mask: Optional[np.ndarray] = None,
    no_vapor_holdup_mask: Optional[np.ndarray] = None,
    top_boundary_liquid_h_BTU_lbmol: Optional[float] = None,
    condenser_boundary_owns_duty: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    N = ML_tot.size
    ML_den = np.maximum(np.asarray(ML_tot, dtype=float), float(epsilon_lbmol))
    MV_den = np.maximum(np.asarray(MV_tot, dtype=float), float(epsilon_lbmol))

    # Protect specific-enthalpy reconstruction from exploding when energy states
    # drift while phase holdup approaches zero.
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        hL = np.asarray(EL_BTU, dtype=float) / ML_den
        hV = np.asarray(EV_BTU, dtype=float) / MV_den
    hL = np.nan_to_num(hL, nan=0.0, posinf=float(max_abs_h_btu_per_lbmol), neginf=-float(max_abs_h_btu_per_lbmol))
    hV = np.nan_to_num(hV, nan=0.0, posinf=float(max_abs_h_btu_per_lbmol), neginf=-float(max_abs_h_btu_per_lbmol))
    hL = np.clip(hL, -float(max_abs_h_btu_per_lbmol), float(max_abs_h_btu_per_lbmol))
    hV = np.clip(hV, -float(max_abs_h_btu_per_lbmol), float(max_abs_h_btu_per_lbmol))
    hL_transport = hL.copy()
    if bool(total_condenser) and top_boundary_liquid_h_BTU_lbmol is not None:
        try:
            h_top = float(top_boundary_liquid_h_BTU_lbmol)
            if np.isfinite(h_top):
                hL_transport[0] = float(np.clip(h_top, -float(max_abs_h_btu_per_lbmol), float(max_abs_h_btu_per_lbmol)))
        except Exception:
            pass

    dEL = np.zeros(N, dtype=float)
    dEV = np.zeros(N, dtype=float)

    for i in range(N):
        Lin = 0.0 if i == 0 else float(L_out[i - 1])
        hin = hL_transport[i] if i == 0 else hL_transport[i - 1]
        dEL[i] += Lin * hin
        dEL[i] -= float(L_out[i]) * hL_transport[i]

    for i in range(N):
        Vin = 0.0 if i == (N - 1) else float(V_out[i + 1])
        hin = hV[i] if i == (N - 1) else hV[i + 1]
        dEV[i] += Vin * hin
        dEV[i] -= float(V_out[i]) * hV[i]

    # For a total condenser with no vapor outflow from stage 1, condenser duty
    # is applied to liquid energy (condensed phase), not vapor energy holdup.
    if bool(total_condenser) and not bool(condenser_boundary_owns_duty):
        dEL[0] += float(Q_cond_BTUph) / 3600.0
    else:
        if not bool(total_condenser):
            dEV[0] += float(Q_cond_BTUph) / 3600.0
    dEL[-1] += float(Q_reb_BTUph) / 3600.0

    liq_mask = np.zeros(N, dtype=bool)
    vap_mask = np.zeros(N, dtype=bool)
    if no_liquid_holdup_mask is not None:
        try:
            liq_mask = np.asarray(no_liquid_holdup_mask, dtype=bool).reshape((N,))
            dEL[liq_mask] = 0.0
        except Exception:
            pass
    if no_vapor_holdup_mask is not None:
        try:
            vap_mask = np.asarray(no_vapor_holdup_mask, dtype=bool).reshape((N,))
            dEV[vap_mask] = 0.0
        except Exception:
            pass

    # Feed enthalpy is an external source and should only be applied at feed stages.
    # Prefer depositing into liquid energy unless the stage has no liquid holdup.
    if Q_feed_BTUps is not None:
        try:
            qf = np.asarray(Q_feed_BTUps, dtype=float).reshape((N,))
            qf = np.where(np.isfinite(qf), qf, 0.0)
            for i in range(N):
                if liq_mask[i] and vap_mask[i]:
                    continue
                if (not liq_mask[i]):
                    dEL[i] += float(qf[i])
                elif (not vap_mask[i]):
                    dEV[i] += float(qf[i])
        except Exception:
            pass
    return dEL, dEV


def column_rhs(
    t: float,
    y: np.ndarray,
    col: ColumnSpec,
    layout: StateVectorLayout,
    inputs: Optional[ColumnInputs] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    if inputs is None:
        inputs = ColumnInputs()

    u = layout.unpack(y)
    N = col.n_stages
    Nc = col.n_components

    tray_L = u["tray_L"]
    tray_V = u.get("tray_V", None)

    x_tray = u["x_tray"].copy()
    y_tray = u.get("y_tray", None)
    if y_tray is not None:
        y_tray = y_tray.copy()
    algebraic_vapor_state = y_tray is None

    hyd_energy_mode = (
        str(getattr(inputs, "pressure_model", "")).strip().lower() == "hydraulic"
        and str(getattr(inputs, "vapor_flow_model", "")).strip().lower() == "energy"
    )
    temp_mode = str(getattr(inputs, "hydraulic_energy_temperature_mode", "legacy") or "legacy").strip().lower()

    top_L = u.get("top_L", None)
    top_V = u.get("top_V", None)
    bottom_L = u.get("bottom_L", None)
    bottom_V = u.get("bottom_V", None)

    # If a stage has ~zero liquid holdup, provide a consistent fallback composition
    # so downstream flashes do not receive a zero-composition vector.
    ML_tot_stage = np.sum(tray_L, axis=1).reshape((N,))
    for i in range(N):
        if ML_tot_stage[i] <= layout.epsilon_lbmol:
            x_tray[i, :] = _fallback_comp_stage(col, i, Nc)
    reboiler_no_holdup = False
    if getattr(col, "M_L_lbmol", None) is not None:
        try:
            M_spec = np.asarray(col.M_L_lbmol, dtype=float).reshape((N,))
            reboiler_no_holdup = float(M_spec[-1]) <= layout.epsilon_lbmol
        except Exception:
            reboiler_no_holdup = False
    if not reboiler_no_holdup:
        try:
            reboiler_no_holdup = float(ML_tot_stage[-1]) <= layout.epsilon_lbmol
        except Exception:
            reboiler_no_holdup = False

    # flows (lbmol/s)
    # NOTE:
    # Internal L/V profiles from Excel/ChemSep are treated as source-of-truth.
    # They already include feed-stage effects (including flashing and non-equimolar behavior).
    # Feed still enters explicitly through component source terms (Fk_L/Fk_V) in mass/energy balances.
    L_out_profile = np.asarray(col.L_lbmolph, dtype=float) / 3600.0
    V_out_profile = np.asarray(col.V_lbmolph, dtype=float) / 3600.0
    if L_out_profile.shape != (N,) or V_out_profile.shape != (N,):
        raise ColumnRHSError("ColumnSpec L/V flow arrays must have shape (n_stages,)")

    runtime_mode = str(getattr(inputs, "runtime_mode", "legacy") or "legacy").strip().lower().replace("_", "-")
    total_reflux_mode = runtime_mode in {"total-reflux", "totalreflux"}
    total_reflux_startup_factor = 1.0
    total_reflux_boundary_external_scale = 0.0 if total_reflux_mode else 1.0
    total_reflux_boundary_closed_fraction = 1.0 if total_reflux_mode else 0.0
    total_reflux_tau_raw = getattr(inputs, "total_reflux_startup_ramp_tau_sec", None)
    total_reflux_tau = None
    if total_reflux_mode and total_reflux_tau_raw is not None:
        try:
            total_reflux_tau_try = float(total_reflux_tau_raw)
            if np.isfinite(total_reflux_tau_try) and total_reflux_tau_try > 0.0:
                total_reflux_tau = float(total_reflux_tau_try)
        except Exception:
            total_reflux_tau = None
    if total_reflux_tau is not None:
        try:
            t_use = max(float(t), 0.0)
        except Exception:
            t_use = 0.0
        try:
            min_frac = float(getattr(inputs, "total_reflux_startup_min_ramp_fraction", 0.0))
        except Exception:
            min_frac = 0.0
        if not np.isfinite(min_frac):
            min_frac = 0.0
        min_frac = float(np.clip(min_frac, 0.0, 1.0))
        total_reflux_startup_factor = float(
            min_frac + (1.0 - min_frac) * (1.0 - np.exp(-float(t_use) / float(total_reflux_tau)))
        )
    boundary_ramp_raw = getattr(inputs, "total_reflux_boundary_ramp_duration_sec", None)
    if total_reflux_mode and boundary_ramp_raw is not None:
        try:
            boundary_ramp = float(boundary_ramp_raw)
            if np.isfinite(boundary_ramp) and boundary_ramp > 0.0:
                try:
                    t_use = max(float(t), 0.0)
                except Exception:
                    t_use = 0.0
                total_reflux_boundary_closed_fraction = float(np.clip(float(t_use) / float(boundary_ramp), 0.0, 1.0))
                total_reflux_boundary_external_scale = 1.0 - float(total_reflux_boundary_closed_fraction)
        except Exception:
            total_reflux_boundary_external_scale = 0.0
            total_reflux_boundary_closed_fraction = 1.0

    reflux = inputs.boundary.reflux_lbmolph
    boilup = inputs.boundary.boilup_lbmolph
    if reflux is None:
        reflux = float(col.L_lbmolph[0])
    reflux_s = float(reflux) / 3600.0
    total_reflux_nominal_s = float(reflux_s)

    D = _draw_from_stream(col, "Top", Nc)
    B = _draw_from_stream(col, "Bottom", Nc)
    D = _override_draw_total_lbmolph(D, inputs.boundary.distillate_lbmolph, prefer_liquid=True)
    B = _override_draw_total_lbmolph(B, inputs.boundary.bottoms_lbmolph, prefer_liquid=True)
    if total_reflux_mode:
        D = _scale_draw(D, total_reflux_boundary_external_scale)
        B = _scale_draw(B, total_reflux_boundary_external_scale)

    alpha = _infer_condenser_alpha(col, inputs)
    if inputs.clamp_alpha:
        alpha = float(np.clip(alpha, 0.0, 1.0))

    if y_tray is None:
        eq_fn = getattr(getattr(inputs, "thermo_provider", None), "equilibrium_y_K_from_x", None)
        if callable(eq_fn):
            rows = []
            for i in range(N):
                yi, _Ki = eq_fn(x_tray[i, :])
                rows.append(np.asarray(yi, dtype=float).reshape((Nc,)))
            y_tray = np.vstack(rows)
        else:
            y_tray = np.asarray(getattr(col, "y0"), dtype=float).reshape((N, Nc)).copy()
        tray_V = np.zeros((N, Nc), dtype=float)

    x_topL = _safe_comp_from_holdup(top_L, fallback=x_tray[0, :], eps=layout.epsilon_lbmol)
    y_topV = _safe_comp_from_holdup(top_V, fallback=y_tray[0, :], eps=layout.epsilon_lbmol)
    x_botL = _safe_comp_from_holdup(bottom_L, fallback=x_tray[-1, :], eps=layout.epsilon_lbmol)
    y_botV = _safe_comp_from_holdup(bottom_V, fallback=y_tray[-1, :], eps=layout.epsilon_lbmol)

    # With an explicit bottom sump, the reboiler should draw liquid from the
    # sump inventory rather than directly from the bottom tray. Preserve the
    # old tray-fed behavior only for the no-holdup reboiler mode, which does
    # not yet model an explicit sump-to-reboiler circulation rate.
    reboiler_feed_from_sump = bool(
        layout.include_bottom
        and (bottom_L is not None)
        and (not reboiler_no_holdup)
    )

    x_reb_source = x_tray[-1, :]
    y_reb_source = y_tray[-1, :]
    if reboiler_no_holdup and N > 1:
        x_reb_source = x_tray[-2, :]
        y_reb_source = y_tray[-2, :]
    if reboiler_feed_from_sump:
        x_rebL = _safe_comp_from_holdup(bottom_L, fallback=x_botL, eps=layout.epsilon_lbmol)
    else:
        x_rebL = _safe_comp_from_holdup(tray_L[-1, :], fallback=x_reb_source, eps=layout.epsilon_lbmol)
    y_rebV = _safe_comp_from_holdup(tray_V[-1, :], fallback=y_reb_source, eps=layout.epsilon_lbmol)

    # Sump temperature (if available)
    T_sump = None
    if "bottom_T_f" in u:
        try:
            T_sump = float(u["bottom_T_f"][0])
        except Exception:
            T_sump = None
    if T_sump is None:
        if "tray_T_f" in u:
            T_sump = float(np.asarray(u["tray_T_f"], dtype=float).reshape((N,))[-1])
        elif hasattr(col, "T_f"):
            T_sump = float(np.asarray(col.T_f, dtype=float).reshape((N,))[-1])
        else:
            T_sump = 100.0

    # Reboiler / boilup handling (thermosiphon: duty -> boilup)
    reboiler_mode = (inputs.reboiler_mode or "auto").strip().lower()
    duty_btu_ph = _resolve_reboiler_duty_btu_per_h(col=col, inputs=inputs)
    if total_reflux_mode:
        duty_btu_ph = float(duty_btu_ph) * float(total_reflux_startup_factor)
    use_duty = False
    if reboiler_mode == "duty":
        use_duty = True
    elif reboiler_mode == "auto":
        use_duty = (boilup is None) and (duty_btu_ph > 0.0)

    boilup_from_duty_lbmolph = None
    reboiler_latent_heat_btu_per_lbmol = np.nan
    y_reb_eq = None
    fres_reb = None
    K_reb = None

    # Reboiler temperature should follow the sump when the reboiler is fed
    # from the explicit bottom holdup.
    T_reb = float(T_sump) if reboiler_feed_from_sump else None
    if T_reb is None and "tray_T_f" in u:
        try:
            T_reb = float(np.asarray(u["tray_T_f"], dtype=float).reshape((N,))[-1])
        except Exception:
            T_reb = None
    if T_reb is None:
        T_reb = float(T_sump)

    if hasattr(col, "P_psia"):
        P_bot = float(np.asarray(col.P_psia, dtype=float).reshape((N,))[-1])
    else:
        P_bot = float(col.P_psia[-1]) if hasattr(col, "P_psia") else 200.0

    if inputs.thermo_provider is not None:

        z_bot = np.asarray(x_rebL, dtype=float).reshape((Nc,))

        # Solve reboiler temperature by bubble point when equilibrium is requested.
        # Skip this for no-holdup reboiler mode: stage-N is modeled as a flow-through
        # flash node, not a holdup equilibrium stage.
        if inputs.reboiler_equilibrium and (not reboiler_no_holdup):
            try:
                _trace_stage_thermo(inputs, f"reboiler bubble-point solve start T_guess_F={float(T_reb):.3f} P_psia={float(P_bot):.3f}")
                with _thermo_provider_category(inputs.thermo_provider, "reboiler_bubble_point"):
                    T_reb, fres_reb = _bubble_point_T_F(
                        thermo_provider=inputs.thermo_provider,
                        P_psia=P_bot,
                        x=z_bot,
                        T_guess_F=T_reb,
                        thermo_call_category="reboiler_bubble_point_helper_flash",
                    )
                _trace_stage_thermo(inputs, f"reboiler bubble-point solve done T_F={float(T_reb):.3f}")
                y_reb_eq = np.asarray(fres_reb.y, dtype=float).reshape((Nc,))
            except Exception:
                fres_reb = None
        else:
            fres_reb = None
        if fres_reb is not None and getattr(fres_reb, "K", None) is not None:
            try:
                K_reb = np.asarray(fres_reb.K, dtype=float).reshape((Nc,))
            except Exception:
                K_reb = None

        # For duty -> boilup, use latent heat from flash at reboiler temperature
        if use_duty:
            try:
                if fres_reb is None:
                    with _thermo_provider_category(inputs.thermo_provider, "reboiler_duty_helper_flash"):
                        fres_reb = flash_TP_full_F_psia(
                            inputs.thermo_provider,
                            float(T_reb),
                            float(P_bot),
                            z_bot,
                            n_components=Nc,
                        )
                delta_h = float(fres_reb.HV_BTU_lbmol) - float(fres_reb.HL_BTU_lbmol)
                reboiler_latent_heat_btu_per_lbmol = float(delta_h)
                if np.isfinite(delta_h) and delta_h > 1e-9:
                    boilup_from_duty_lbmolph = float(duty_btu_ph) / delta_h
            except Exception:
                pass
    if y_reb_eq is not None:
        y_rebV = np.asarray(y_reb_eq, dtype=float).reshape((Nc,))

    if boilup is None:
        if boilup_from_duty_lbmolph is not None and boilup_from_duty_lbmolph > 0.0:
            boilup = float(boilup_from_duty_lbmolph)
        else:
            boilup = float(col.V_lbmolph[-1])
    boilup_s = float(boilup) / 3600.0
    if total_reflux_mode:
        boilup_s = float(boilup_s) * float(total_reflux_startup_factor)

    feed_stage0, Fk_L, Fk_V = _feed_component_rates_lbmolps(
        col,
        Nc,
        thermo_provider=inputs.thermo_provider,
        P_tray_psia=inputs.P_tray_prev,
        flash_feed_at_stage_conditions=bool(inputs.flash_feed_at_stage_conditions),
        feed_stage_flash_prev=inputs.feed_stage_flash_prev,
        feed_stage_flash_reuse_dT_F=float(inputs.feed_stage_flash_reuse_dT_F),
        feed_stage_flash_reuse_dP_psia=float(inputs.feed_stage_flash_reuse_dP_psia),
        feed_stage_flash_reuse_dx=float(inputs.feed_stage_flash_reuse_dx),
        trace_hook=(inputs.progress_hook if bool(getattr(inputs, "trace_stage_thermo", False)) else None),
        trace_label=(
            getattr(inputs, "thermo_stage_trace_label", None)
            if bool(getattr(inputs, "trace_stage_thermo", False))
            else None
        ),
    )
    if total_reflux_mode:
        Fk_L = np.asarray(Fk_L, dtype=float) * float(total_reflux_boundary_external_scale)
        Fk_V = np.asarray(Fk_V, dtype=float) * float(total_reflux_boundary_external_scale)
        if float(total_reflux_boundary_external_scale) <= 1.0e-14:
            feed_stage0 = None
    Ft_L = float(np.sum(Fk_L))
    Ft_V = float(np.sum(Fk_V))
    Ft_feed = Ft_L + Ft_V
    feed_vf_effective = (Ft_V / Ft_feed) if Ft_feed > 1e-300 else np.nan

    L_out = L_out_profile
    V_out = V_out_profile

    # Optional stage hydraulics: compute internal liquid outflow from either a
    # Francis-weir closure or a validation/source linear holdup lag.
    rhoL_tray = None
    h_ow_ft = None
    L_out_hyd_lbmolph = None
    hydraulic_l_override_alpha = 1.0
    hydraulic_l_override_alpha_stage = None
    liquid_hydraulic_model = str(getattr(inputs, "liquid_hydraulic_model", "francis") or "francis").strip().lower()
    if liquid_hydraulic_model in {"linear", "linear_holdup", "linear-holdup", "skogestad", "skogestad-linear"}:
        liquid_hydraulic_model = "linear-holdup"
    elif liquid_hydraulic_model != "francis":
        liquid_hydraulic_model = "francis"
    if liquid_hydraulic_model == "linear-holdup":
        try:
            hydraulic_l_override_alpha = float(inputs.liquid_hydraulic_override_alpha)
        except Exception:
            hydraulic_l_override_alpha = 1.0
        if not np.isfinite(hydraulic_l_override_alpha):
            hydraulic_l_override_alpha = 1.0
        hydraulic_l_override_alpha = float(np.clip(hydraulic_l_override_alpha, 0.0, 1.0))
        if not bool(inputs.enable_liquid_hydraulic_override):
            hydraulic_l_override_alpha = 0.0
        tau_l = getattr(inputs, "liquid_hydraulic_htc_sec", None)
        try:
            tau_l = float(tau_l) if tau_l is not None else np.nan
        except Exception:
            tau_l = np.nan
        if hydraulic_l_override_alpha > 0.0 and np.isfinite(tau_l) and tau_l > 0.0:
            ML_tray = np.sum(tray_L, axis=1).reshape((N,))
            L_out_hyd = np.asarray(L_out_profile, dtype=float).reshape((N,)).copy()
            L_out_hyd_lbmolph = L_out_hyd * 3600.0
            for i in range(1, N - 1):
                L_dyn = float(L_out_profile[i]) + (float(ML_tray[i]) - float(M_spec[i])) / float(tau_l)
                L_dyn = max(float(L_dyn), 0.0)
                L_out_hyd[i] = L_dyn
                L_out_hyd_lbmolph[i] = L_dyn * 3600.0
                if hydraulic_l_override_alpha >= 1.0:
                    L_out[i] = L_dyn
                else:
                    L_out[i] = (
                        (1.0 - float(hydraulic_l_override_alpha)) * float(L_out[i])
                        + float(hydraulic_l_override_alpha) * L_dyn
                    )
    geom = getattr(col, "geometry", None)
    if liquid_hydraulic_model == "francis" and geom is not None:
        weir_h = getattr(geom, "weir_height_in_per_stage", None)
        weir_L = getattr(geom, "weir_length_ft_per_stage", None)
        active_area = getattr(geom, "active_area_ft2_per_stage", None)
        holdup_area = getattr(geom, "area_ft2_per_stage", None)
        c_fac = getattr(geom, "hydraulic_c_factor_per_stage", None)
        if weir_h is not None and weir_L is not None and active_area is not None:
            rho_arr = None
            if inputs.rhoL_tray_lbmol_ft3 is not None:
                try:
                    rho_arr = np.asarray(inputs.rhoL_tray_lbmol_ft3, dtype=float).reshape((N,))
                except Exception:
                    rho_arr = None
            if rho_arr is None and inputs.thermo_provider is not None and hasattr(inputs.thermo_provider, "liquid_density_lbmol_ft3"):
                # Compute stage liquid density from thermo (composition, T, P)
                if "tray_T_f" in u:
                    T_tray = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
                elif hasattr(col, "T_f"):
                    T_tray = np.asarray(col.T_f, dtype=float).reshape((N,))
                else:
                    T_tray = np.full(N, 100.0, dtype=float)
                if hasattr(col, "P_psia"):
                    P_tray = np.asarray(col.P_psia, dtype=float).reshape((N,))
                else:
                    P_tray = np.full(N, 200.0, dtype=float)
                rho_arr = np.full(N, np.nan, dtype=float)
                for i in range(N):
                    try:
                        with _thermo_provider_category(inputs.thermo_provider, "liquid_density_lookup"):
                            rho_arr[i] = float(
                                inputs.thermo_provider.liquid_density_lbmol_ft3(
                                    float(T_tray[i]), float(P_tray[i]), x_tray[i, :]
                                )
                            )
                    except Exception:
                        rho_arr[i] = np.nan
            if rho_arr is None or not np.all(np.isfinite(rho_arr)):
                # Fallback to constant if thermo density unavailable
                rhoL = _get_liquid_density_lbmol_ft3(col, default=1.0)
                rho_arr = np.full(N, float(rhoL), dtype=float)

            rhoL_tray = np.asarray(rho_arr, dtype=float).reshape((N,)) if rho_arr is not None else None

            if rhoL_tray is not None and np.isfinite(np.nanmin(rhoL_tray)) and np.nanmin(rhoL_tray) > 0.0:
                ML_tray = np.sum(tray_L, axis=1).reshape((N,))
                try:
                    active_area_arr = np.asarray(active_area, dtype=float).reshape((N,))
                    if holdup_area is not None:
                        holdup_area_arr = np.asarray(holdup_area, dtype=float).reshape((N,))
                    else:
                        holdup_area_arr = active_area_arr
                    weir_h_arr = np.asarray(weir_h, dtype=float).reshape((N,))
                    hyd = compute_francis_weir_liquid_outflow(
                        ML_lbmol=ML_tray,
                        rhoL_lbmol_ft3=rhoL_tray,
                        active_area_ft2=active_area_arr,
                        holdup_area_ft2=holdup_area_arr,
                        weir_height_in=weir_h_arr,
                        weir_length_ft=np.asarray(weir_L, dtype=float).reshape((N,)),
                        c_multiplier=(
                            None
                            if c_fac is None
                            else np.asarray(c_fac, dtype=float).reshape((N,))
                        ),
                    )
                    L_out_hyd_lbmolph = np.asarray(hyd.ML_lbmolph, dtype=float).reshape((N,))
                    h_ow_ft = np.asarray(hyd.h_ow, dtype=float).reshape((N,))
                    L_out_hyd = np.asarray(L_out_hyd_lbmolph, dtype=float).reshape((N,)) / 3600.0
                    if c_fac is None:
                        c_fac_valid = np.ones(N, dtype=bool)
                    else:
                        try:
                            c_arr = np.asarray(c_fac, dtype=float).reshape((N,))
                            c_fac_valid = np.isfinite(c_arr) & (c_arr > 0.0)
                        except Exception:
                            c_fac_valid = np.zeros(N, dtype=bool)
                    valid = (
                        np.isfinite(L_out_hyd)
                        & np.isfinite(weir_L)
                        & (np.asarray(weir_L, dtype=float) > 0.0)
                        & np.isfinite(active_area)
                        & (np.asarray(active_area, dtype=float) > 0.0)
                        & c_fac_valid
                        & np.isfinite(weir_h)
                        & (np.asarray(weir_h, dtype=float) >= 0.0)
                        & np.isfinite(rhoL_tray)
                        & (rhoL_tray > 0.0)
                    )
                    try:
                        hydraulic_l_override_alpha = float(inputs.liquid_hydraulic_override_alpha)
                    except Exception:
                        hydraulic_l_override_alpha = 1.0
                    if (not np.isfinite(hydraulic_l_override_alpha)):
                        hydraulic_l_override_alpha = 1.0
                    hydraulic_l_override_alpha = float(np.clip(hydraulic_l_override_alpha, 0.0, 1.0))
                    if not bool(inputs.enable_liquid_hydraulic_override):
                        hydraulic_l_override_alpha = 0.0
                    alpha_stage_raw = getattr(inputs, "liquid_hydraulic_override_alpha_per_stage", None)
                    if alpha_stage_raw is not None:
                        try:
                            alpha_stage = np.asarray(alpha_stage_raw, dtype=float).reshape((N,))
                            alpha_stage = np.clip(alpha_stage, 0.0, 1.0)
                            if not bool(inputs.enable_liquid_hydraulic_override):
                                alpha_stage = np.zeros((N,), dtype=float)
                            hydraulic_l_override_alpha_stage = alpha_stage
                        except Exception:
                            hydraulic_l_override_alpha_stage = None
                    # Apply to internal stages (stage 2..N-1); stage 1 (index 0) and reboiler (index N-1) excluded.
                    for i in range(1, N - 1):
                        alpha_i = hydraulic_l_override_alpha
                        if hydraulic_l_override_alpha_stage is not None and np.isfinite(hydraulic_l_override_alpha_stage[i]):
                            alpha_i = float(hydraulic_l_override_alpha_stage[i])
                        if valid[i] and alpha_i > 0.0:
                            if alpha_i >= 1.0:
                                L_out[i] = float(L_out_hyd[i])
                            else:
                                L_profile_i = float(L_out[i])
                                L_hyd_i = float(L_out_hyd[i])
                                L_out[i] = (
                                    (1.0 - float(alpha_i)) * L_profile_i
                                    + float(alpha_i) * L_hyd_i
                                )
                except Exception:
                    pass

    # Enforce boundary flow endpoints even when using the Excel-provided profiles.
    # Convention: Stage 1 (index 0) is the condenser.
    # - Reflux is the liquid leaving the condenser down to Stage 2.
    # - Boilup is the vapor entering the bottom stage.
    # - A total condenser has no vapor leaving upward from Stage 1.
    L_out = np.asarray(L_out, dtype=float).reshape((N,))
    V_out = np.asarray(V_out, dtype=float).reshape((N,))
    L_out[0] = reflux_s
    V_out[-1] = boilup_s
    V_out[0] = 0.0

    # With a separate reflux drum, reflux composition to stage 2 comes from the
    # top accumulator, while stage-1 (condenser) liquid state remains independent.

    # inlets
    L_in = np.zeros(N, dtype=float)
    x_in = np.zeros((N, Nc), dtype=float)
    for i in range(N):
        if i == 0:
            # condenser has no liquid inflow from above
            L_in[i] = 0.0
            x_in[i, :] = x_tray[i, :]
        else:
            # liquid enters stage i from stage i-1 above (condenser reflux for i==1)
            L_in[i] = L_out[i - 1]
            if layout.include_top and i == 1:
                x_in[i, :] = x_topL
            else:
                x_in[i, :] = x_tray[i - 1, :]

    debug_reflux_overridden = False
    debug_reflux_target_stage = -1
    debug_reflux_orig_comp2 = np.nan
    debug_reflux_target_comp2 = np.nan
    debug_reflux_comp2_delta = np.nan
    debug_reflux_target_delta_max = 0.0
    if (
        bool(getattr(inputs, "debug_override_reflux_composition", False))
        and layout.include_top
        and N > 1
        and Nc > 0
    ):
        reflux_target = _safe_comp_from_holdup(
            np.asarray(y_tray[1, :], dtype=float).reshape((Nc,)),
            fallback=x_in[1, :],
            eps=layout.epsilon_lbmol,
        )
        old_reflux_x = np.asarray(x_in[1, :], dtype=float).reshape((Nc,)).copy()
        x_in[1, :] = reflux_target
        debug_reflux_overridden = True
        debug_reflux_target_stage = 2
        debug_reflux_orig_comp2 = float(old_reflux_x[1]) if Nc > 1 else float(old_reflux_x[0])
        debug_reflux_target_comp2 = float(reflux_target[1]) if Nc > 1 else float(reflux_target[0])
        debug_reflux_comp2_delta = float(debug_reflux_target_comp2 - debug_reflux_orig_comp2)
        debug_reflux_target_delta_max = float(np.max(np.abs(reflux_target - old_reflux_x)))

    reb_cache_out = None
    if reboiler_no_holdup and N > 0:
        z_in = x_in[-1, :].copy()
        L_in_reb = float(L_in[-1])
        V_out_reb = float(boilup_s)
        y_out = y_reb_eq if y_reb_eq is not None else y_rebV
        x_out = z_in.copy()
        reboiler_flash_done = False
        reboiler_flash_used_cache = False

        reb_cache_valid = False
        reb_beta_prev = 0.0
        if (
            inputs.reb_T_prev is not None
            and inputs.reb_x_prev is not None
            and inputs.reb_y_prev is not None
            and inputs.reb_beta_prev is not None
        ):
            try:
                reb_T_prev = float(inputs.reb_T_prev)
                reb_x_prev = np.asarray(inputs.reb_x_prev, dtype=float).reshape((Nc,))
                reb_y_prev = np.asarray(inputs.reb_y_prev, dtype=float).reshape((Nc,))
                reb_beta_prev = float(inputs.reb_beta_prev)
                if np.isfinite(reb_T_prev) and np.all(np.isfinite(reb_x_prev)) and np.all(np.isfinite(reb_y_prev)):
                    if reb_beta_prev < 0.0:
                        reb_beta_prev = 0.0
                    reb_cache_valid = True
                    # Use cached state as a seed/fallback only.
                    # Do not short-circuit duty flash in no-holdup mode; that can
                    # freeze reboiler temperature and decouple it from current
                    # inlet enthalpy + duty.
                    T_reb = reb_T_prev
                    x_out = reb_x_prev.copy()
                    y_out = reb_y_prev.copy()
                    try:
                        denom_k = np.where(np.abs(reb_x_prev) > 1.0e-12, reb_x_prev, np.nan)
                        K_reb_cache = reb_y_prev / denom_k
                        if np.all(np.isfinite(K_reb_cache)):
                            K_reb = np.asarray(K_reb_cache, dtype=float).reshape((Nc,))
                    except Exception:
                        pass
            except Exception:
                reb_cache_valid = False
                reboiler_flash_done = False

        # For no-duty operation, keep cache as a seed only; re-evaluate from
        # current inlet state each step so the no-holdup reboiler cannot freeze.

        if (
            (not reboiler_flash_done)
            and use_duty
            and inputs.thermo_provider is not None
            and duty_btu_ph != 0.0
            and L_in_reb > layout.epsilon_lbmol
        ):
            # Flash after adding reboiler duty to the incoming liquid enthalpy.
            if "tray_T_f" in u and N > 1:
                T_in = float(np.asarray(u["tray_T_f"], dtype=float).reshape((N,))[-2])
            elif hasattr(col, "T_f") and N > 1:
                T_in = float(np.asarray(col.T_f, dtype=float).reshape((N,))[-2])
            else:
                T_in = float(T_reb)
            try:
                fres_in = _flash_TP_full_stage_F_psia(
                    inputs.thermo_provider,
                    N - 2,
                    float(T_in),
                    float(P_bot),
                    z_in,
                    n_components=Nc,
                    thermo_call_category="reboiler_duty_helper_flash",
                )
                H_in = float(fres_in.HL_BTU_lbmol)
                T_reb_new, beta, x_out, y_out, K_reb_new, _HL, _HV = _reboiler_flash_after_duty(
                    thermo_provider=inputs.thermo_provider,
                    P_psia=float(P_bot),
                    z=z_in,
                    T_in_F=float(T_in),
                    H_in_BTU_lbmol=float(H_in),
                    Q_btu_per_h=float(duty_btu_ph),
                    L_in_lbmolps=float(L_in_reb),
                )
                T_reb = float(T_reb_new)
                K_reb = np.asarray(K_reb_new, dtype=float).reshape((Nc,))
                y_reb_eq = np.asarray(y_out, dtype=float).reshape((Nc,))
                V_out_reb = max(float(beta) * L_in_reb, 0.0)
                boilup_s = V_out_reb
                L_out_reb = max(L_in_reb - V_out_reb, 0.0)
                reboiler_flash_done = True
            except Exception:
                pass

        if (not reboiler_flash_done) and inputs.thermo_provider is not None and K_reb is None:
            try:
                fres_tmp = _flash_TP_full_stage_F_psia(
                    inputs.thermo_provider,
                    N - 1,
                    float(T_reb),
                    float(P_bot),
                    z_in,
                    n_components=Nc,
                    thermo_call_category="reboiler_equilibrium_helper_flash",
                )
                if getattr(fres_tmp, "K", None) is not None:
                    K_reb = np.asarray(fres_tmp.K, dtype=float).reshape((Nc,))
            except Exception:
                K_reb = None

        if reboiler_flash_done:
            pass
        elif K_reb is not None and L_in_reb > layout.epsilon_lbmol:
            beta = max(V_out_reb / L_in_reb, 0.0)
            beta_max = np.inf
            mask = K_reb < (1.0 - 1e-12)
            if np.any(mask):
                beta_max = float(np.min(1.0 / (1.0 - K_reb[mask])))
            beta_use = beta
            if np.isfinite(beta_max) and beta_max > 0.0:
                beta_use = min(beta_use, 0.999 * beta_max)
            V_out_reb = beta_use * L_in_reb
            L_out_reb = max(L_in_reb - V_out_reb, 0.0)

            denom = 1.0 + beta_use * (K_reb - 1.0)
            denom = np.where(np.abs(denom) < 1e-12, np.sign(denom) * 1e-12 + (denom == 0) * 1e-12, denom)
            x_out = z_in / denom
            x_out = np.clip(x_out, 0.0, None)
            s = float(np.sum(x_out))
            if not np.isfinite(s) or s <= layout.epsilon_lbmol:
                x_out = z_in.copy()
            else:
                x_out = x_out / s

            y_out = K_reb * x_out
            sy = float(np.sum(y_out))
            if not np.isfinite(sy) or sy <= layout.epsilon_lbmol:
                y_out = y_reb_eq if y_reb_eq is not None else y_rebV
            else:
                y_out = y_out / sy
        else:
            L_out_reb = max(L_in_reb - V_out_reb, 0.0)
            if L_out_reb > 0.0:
                x_out = (L_in_reb * z_in - V_out_reb * y_out) / L_out_reb
                x_out = np.clip(x_out, 0.0, None)
                s = float(np.sum(x_out))
                if not np.isfinite(s) or s <= layout.epsilon_lbmol:
                    x_out = z_in.copy()
                else:
                    x_out = x_out / s
            else:
                x_out = z_in.copy()

        x_tray[-1, :] = x_out
        y_tray[-1, :] = y_out
        L_out[-1] = L_out_reb
        V_out[-1] = V_out_reb

        beta_out = float(V_out_reb / L_in_reb) if L_in_reb > layout.epsilon_lbmol else 0.0
        reb_cache_out = {
            "reb_T_F": float(T_reb),
            "reb_x": x_out.copy(),
            "reb_y": y_out.copy(),
            "reb_beta": float(beta_out),
            "reb_flash_ok": float(1.0 if reboiler_flash_done and not reboiler_flash_used_cache else 0.0),
            "reb_flash_used_cache": float(1.0 if reboiler_flash_used_cache else 0.0),
        }

    vflow_diag = None
    vflow_model = (inputs.vapor_flow_model or "").strip().lower()

    # Vapor flows via tray-to-tray pressure conductance.
    if vflow_model == "conductance":
        alpha_v = None
        if inputs.vapor_flow_relaxation_sec is not None:
            try:
                tau_vflow = float(inputs.vapor_flow_relaxation_sec)
            except Exception:
                tau_vflow = None
            if tau_vflow is not None and np.isfinite(tau_vflow) and tau_vflow > 0.0:
                dt = getattr(getattr(col, "sim", None), "dt_sec", None)
                try:
                    dt = float(dt)
                except Exception:
                    dt = None
                if dt is not None and np.isfinite(dt) and dt > 0.0:
                    alpha_v = min(dt / tau_vflow, 1.0)

        vflow_ok = np.full(N, np.nan, dtype=float)
        vflow_denom = np.full(N, np.nan, dtype=float)
        vflow_calc = np.full(N, np.nan, dtype=float)
        vflow_used = np.full(N, np.nan, dtype=float)
        vflow_clamped = np.full(N, np.nan, dtype=float)
        vflow_limit_hi = np.full(N, np.nan, dtype=float)
        vflow_limit_lo = np.full(N, np.nan, dtype=float)
        vflow_L_in_term = np.full(N, np.nan, dtype=float)
        vflow_V_in_term = np.full(N, np.nan, dtype=float)
        vflow_feed_ref_term = np.full(N, np.nan, dtype=float)
        vflow_duty_term = np.full(N, np.nan, dtype=float)
        vflow_dE_target = np.full(N, np.nan, dtype=float)
        vflow_numer = np.full(N, np.nan, dtype=float)
        vflow_heat_capacity = np.full(N, np.nan, dtype=float)
        vflow_L_in = np.full(N, np.nan, dtype=float)
        vflow_V_in = np.full(N, np.nan, dtype=float)
        vflow_hL_in = np.full(N, np.nan, dtype=float)
        vflow_hL_out = np.full(N, np.nan, dtype=float)
        vflow_hV_in = np.full(N, np.nan, dtype=float)
        vflow_hV_out = np.full(N, np.nan, dtype=float)
        vflow_hL_in_minus_hL_out = np.full(N, np.nan, dtype=float)
        vflow_hV_in_minus_hL_out = np.full(N, np.nan, dtype=float)
        vflow_alpha = np.full(N, np.nan, dtype=float)
        if alpha_v is not None:
            vflow_alpha[1 : max(N - 1, 1)] = float(alpha_v)

        V_prev = None
        if inputs.V_out_prev_lbmolph is not None:
            try:
                V_prev = np.asarray(inputs.V_out_prev_lbmolph, dtype=float).reshape((N,)) / 3600.0
            except Exception:
                V_prev = None
        if V_prev is None:
            V_prev = V_out.copy()

        V_out[0] = 0.0
        V_out[-1] = boilup_s

        if inputs.P_tray_prev is not None:
            try:
                P_tray_cond = np.asarray(inputs.P_tray_prev, dtype=float).reshape((N,))
            except Exception:
                P_tray_cond = np.asarray(getattr(col, "P_psia", np.full(N, 200.0)), dtype=float).reshape((N,))
        else:
            P_tray_cond = np.asarray(getattr(col, "P_psia", np.full(N, 200.0)), dtype=float).reshape((N,))
        if not np.all(np.isfinite(P_tray_cond)):
            P_tray_cond = np.asarray(getattr(col, "P_psia", np.full(N, 200.0)), dtype=float).reshape((N,))
        P_tray_cond = np.where(~np.isfinite(P_tray_cond) | (P_tray_cond <= 0.0), 200.0, P_tray_cond)

        if "tray_T_f" in u:
            T_tray_for_v = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
        elif hasattr(col, "T_f"):
            T_tray_for_v = np.asarray(col.T_f, dtype=float).reshape((N,))
        else:
            T_tray_for_v = np.full(N, 100.0, dtype=float)

        if inputs.Zfac_prev is not None:
            try:
                Z_for_v = np.asarray(inputs.Zfac_prev, dtype=float).reshape((N,))
            except Exception:
                Z_for_v = np.ones(N, dtype=float)
        else:
            Z_for_v = np.ones(N, dtype=float)
        Z_for_v = np.where(~np.isfinite(Z_for_v) | (Z_for_v <= 0.0), 1.0, Z_for_v)

        V_calc_all = None
        geom = getattr(col, "geometry", None)
        if geom is not None:
            try:
                V_calc_all = _vapor_outflow_hydraulic_lbmolps(
                    P_profile_psia=P_tray_cond,
                    T_F=T_tray_for_v,
                    y_tray=y_tray,
                    x_tray=x_tray,
                    Z_vap=Z_for_v,
                    geom=geom,
                    h_ow_ft=h_ow_ft,
                    rhoL_lbmol_ft3=rhoL_tray,
                    mw_components=inputs.component_mw_lbm_per_lbmol,
                    dry_tray_K=float(inputs.dry_tray_K),
                )
            except Exception:
                V_calc_all = None
        if V_calc_all is None:
            V_calc_all = np.asarray(V_out_profile, dtype=float).reshape((N,)).copy()
        else:
            V_calc_all = np.asarray(V_calc_all, dtype=float).reshape((N,))
        V_calc_all = np.where(~np.isfinite(V_calc_all) | (V_calc_all < 0.0), 0.0, V_calc_all)
        V_calc_all[0] = 0.0
        V_calc_all[-1] = boilup_s

        # Conservative hard limits prevent single-step numerical spikes.
        vflow_prev_up_ratio = 1.2
        vflow_prev_down_ratio = 0.8
        vflow_nominal_abs_ratio = 1.5
        try:
            v_nom_cfg = inputs.conductance_vflow_nominal_hi_ratio
            if v_nom_cfg is not None:
                v_nom_cfg = float(v_nom_cfg)
                if np.isfinite(v_nom_cfg) and v_nom_cfg > 0.0:
                    vflow_nominal_abs_ratio = v_nom_cfg
        except Exception:
            pass
        # Keep the stage above the reboiler tightly coupled to boilup.
        # This suppresses slow upward drift in lower-column vapor rates.
        vflow_reb_neighbor_up_ratio = 1.02
        vflow_reb_neighbor_down_ratio = 0.98
        vflow_smooth_eps_lbmolps = _finite_positive_or_zero(
            getattr(inputs, "vflow_smooth_clamp_epsilon_lbmolps", None)
        )
        try:
            up_cfg = float(inputs.reboiler_neighbor_vflow_hi_ratio)
            if np.isfinite(up_cfg) and up_cfg > 0.0:
                vflow_reb_neighbor_up_ratio = up_cfg
        except Exception:
            pass
        try:
            dn_cfg = float(inputs.reboiler_neighbor_vflow_lo_ratio)
            if np.isfinite(dn_cfg) and dn_cfg > 0.0:
                vflow_reb_neighbor_down_ratio = dn_cfg
        except Exception:
            pass
        if vflow_reb_neighbor_down_ratio > vflow_reb_neighbor_up_ratio:
            vflow_reb_neighbor_down_ratio = vflow_reb_neighbor_up_ratio

        vflow_dp = np.full(N, np.nan, dtype=float)
        for i in range(1, N - 1):
            if np.isfinite(P_tray_cond[i]) and np.isfinite(P_tray_cond[i - 1]):
                vflow_dp[i] = float(P_tray_cond[i] - P_tray_cond[i - 1])

        for i in range(N - 2, 0, -1):
            V_calc = float(V_calc_all[i])
            ok = bool(np.isfinite(V_calc) and (V_calc >= 0.0))
            if not ok:
                V_calc = float(V_prev[i]) if V_prev is not None else float(V_out[i])
            if not np.isfinite(V_calc) or V_calc < 0.0:
                V_calc = 0.0
                ok = False

            # Hard clamp relative to previous and nominal profile values.
            # For conductance closure, enforce a nominal-profile ceiling to
            # prevent long-horizon drift from ratcheting V_out upward.
            V_prev_i = max(float(V_prev[i]), 0.0)
            V_nom_i = max(float(V_out_profile[i]), 0.0)

            V_hi_prev = vflow_prev_up_ratio * V_prev_i
            if V_nom_i > layout.epsilon_lbmol:
                V_hi_nom = vflow_nominal_abs_ratio * V_nom_i
                if V_prev_i > layout.epsilon_lbmol:
                    if vflow_smooth_eps_lbmolps > 0.0:
                        V_hi = _smooth_min_scalar(V_hi_prev, V_hi_nom, vflow_smooth_eps_lbmolps)
                    else:
                        V_hi = min(V_hi_prev, V_hi_nom)
                else:
                    V_hi = V_hi_nom
            else:
                # If no reliable nominal is available, fall back to previous-step
                # growth limit and keep a conservative boilup floor.
                if vflow_smooth_eps_lbmolps > 0.0:
                    V_hi = _smooth_max_scalar(V_hi_prev, float(boilup_s), vflow_smooth_eps_lbmolps)
                else:
                    V_hi = max(V_hi_prev, float(boilup_s))
            V_hi = max(float(V_hi), 0.0)
            V_lo = 0.0
            if V_prev_i > layout.epsilon_lbmol and V_nom_i > layout.epsilon_lbmol:
                V_lo = min(vflow_prev_down_ratio * V_prev_i, vflow_prev_down_ratio * V_nom_i)

            # Reboiler-neighbor guard: keep tray N-1 near reboiler boilup to
            # avoid non-physical long-horizon growth in lower-section vapor flow.
            if i == (N - 2):
                V_hi_reb = vflow_reb_neighbor_up_ratio * float(boilup_s)
                if vflow_smooth_eps_lbmolps > 0.0:
                    V_hi = _smooth_min_scalar(V_hi, V_hi_reb, vflow_smooth_eps_lbmolps)
                else:
                    V_hi = min(V_hi, V_hi_reb)
                if float(boilup_s) > layout.epsilon_lbmol:
                    V_lo_reb = vflow_reb_neighbor_down_ratio * float(boilup_s)
                    if vflow_smooth_eps_lbmolps > 0.0:
                        V_lo = _smooth_max_scalar(V_lo, V_lo_reb, vflow_smooth_eps_lbmolps)
                    else:
                        V_lo = max(V_lo, V_lo_reb)

            if V_hi < V_lo:
                V_hi = V_lo

            vflow_limit_hi[i] = float(V_hi) * 3600.0
            vflow_limit_lo[i] = float(V_lo) * 3600.0
            V_calc_raw = float(V_calc)
            clamped = bool((V_calc_raw > V_hi) or (V_calc_raw < V_lo))
            if vflow_smooth_eps_lbmolps > 0.0:
                V_calc = _smooth_clip_scalar(V_calc_raw, V_lo, V_hi, vflow_smooth_eps_lbmolps)
            else:
                if V_calc_raw > V_hi:
                    V_calc = V_hi
                elif V_calc_raw < V_lo:
                    V_calc = V_lo
            vflow_clamped[i] = 1.0 if clamped else 0.0

            vflow_ok[i] = 1.0 if ok else 0.0
            vflow_calc[i] = float(V_calc) * 3600.0

            if alpha_v is not None and V_prev is not None:
                V_out[i] = float(V_prev[i] + alpha_v * (V_calc - V_prev[i]))
            else:
                V_out[i] = float(V_calc)
            vflow_used[i] = float(V_out[i]) * 3600.0

        # Keep legacy vflow_energy_* diagnostics populated for backward compatibility
        # even when using conductance closure.
        vflow_diag = {
            "vflow_energy_ok": vflow_ok,
            "vflow_energy_denom_BTU_per_lbmol": vflow_denom,
            "vflow_energy_calc_lbmolph": vflow_calc,
            "vflow_energy_used_lbmolph": vflow_used,
            "vflow_energy_clamped": vflow_clamped,
            "vflow_energy_limit_hi_lbmolph": vflow_limit_hi,
            "vflow_energy_limit_lo_lbmolph": vflow_limit_lo,
            "vflow_conductance_dp_psia": vflow_dp,
            "vflow_relax_alpha": vflow_alpha,
            "vflow_smooth_clamp_eps_lbmolph": np.array(
                [float(vflow_smooth_eps_lbmolps) * 3600.0],
                dtype=float,
            ),
        }

    need_temperature_provider_packet = bool(getattr(layout, "include_temperature", False)) and bool(
        getattr(inputs, "enable_legacy_temperature_state", True)
    )
    do_thermo = (inputs.thermo_provider is not None) and (
        inputs.compute_thermo_diag or inputs.equilibrium_relaxation or need_temperature_provider_packet
    )
    thermo_packet: Optional[TrayThermoPacket] = None
    thermo_refresh_result = None
    energy_vapor_flow_packet: Optional[TrayThermoPacket] = None

    # Vapor flows via energy balance (dynamic closure).
    if vflow_model == "energy":
        HL_cache = None
        HV_cache = None
        if inputs.HL_prev is not None:
            try:
                HL_cache = np.asarray(inputs.HL_prev, dtype=float).reshape((N,))
            except Exception:
                HL_cache = None
        if inputs.HV_prev is not None:
            try:
                HV_cache = np.asarray(inputs.HV_prev, dtype=float).reshape((N,))
            except Exception:
                HV_cache = None
        if "tray_T_f" in u:
            T_tray_for_v = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
        elif hasattr(col, "T_f"):
            T_tray_for_v = np.asarray(col.T_f, dtype=float).reshape((N,))
        else:
            T_tray_for_v = np.full(N, 100.0, dtype=float)

        if inputs.P_tray_prev is not None:
            try:
                P_tray_energy = np.asarray(inputs.P_tray_prev, dtype=float).reshape((N,))
            except Exception:
                P_tray_energy = np.asarray(getattr(col, "P_psia", np.full(N, 200.0)), dtype=float).reshape((N,))
        else:
            P_tray_energy = np.asarray(getattr(col, "P_psia", np.full(N, 200.0)), dtype=float).reshape((N,))

        thermo = inputs.thermo
        if thermo is None:
            thermo = ConstantCpThermo(
                cp_liq_components=np.full(Nc, 30.0, dtype=float),
                cp_vap_components=np.full(Nc, 20.0, dtype=float),
                tref_f=60.0,
            )

        # When a thermo provider is available, prefer provider enthalpies for
        # the energy-mode vapor-flow solve. Falling back to the simplified Cp
        # model here can materially distort startup vapor-flow parity even when
        # pressure and composition states come from a ChemSep-aligned seed.
        hL_stage_provider = None
        hV_stage_provider = None
        if inputs.thermo_provider is not None:
            if do_thermo and thermo_refresh_result is None:
                thermo_refresh_result = _build_current_tray_thermo_refresh(
                    col=col,
                    layout=layout,
                    inputs=inputs,
                    u=u,
                    diag=None,
                    tray_L=tray_L,
                    tray_V=tray_V,
                    x_tray=x_tray,
                    P_tray_hyd=None,
                    n_stages=N,
                    n_components=Nc,
                )
                if thermo_refresh_result is not None:
                    thermo_packet = thermo_refresh_result.packet
            packet_phase_tol_liq = _phase_reuse_dx_tol(inputs, "liquid")
            packet_phase_tol_vap = _phase_reuse_dx_tol(inputs, "vapor")
            packet_dT_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dT_F", 0.0) or 0.0)
            packet_dP_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dP_psia", 0.0) or 0.0)
            energy_refresh = refresh_energy_vapor_flow_phase_enthalpies(
                provider=inputs.thermo_provider,
                current_packet=thermo_packet,
                previous_packet=inputs.tray_thermo_prev,
                tray_T_F=T_tray_for_v,
                P_tray_psia=P_tray_energy,
                x_tray=x_tray,
                y_tray=y_tray,
                n_stages=N,
                n_components=Nc,
                packet_phase_tol_liq=packet_phase_tol_liq,
                packet_phase_tol_vap=packet_phase_tol_vap,
                packet_dT_tol_F=packet_dT_tol,
                packet_dP_tol_psia=packet_dP_tol,
                packet_phase_enthalpy_if_compatible_fn=_packet_phase_enthalpy_if_compatible,
                flash_stage_fn=_flash_TP_full_stage_F_psia,
                packet_factory=TrayThermoPacket,
                trace_fn=_trace_stage_thermo,
                trace_context=inputs,
            )
            hL_stage_provider = energy_refresh.hL_stage_provider
            hV_stage_provider = energy_refresh.hV_stage_provider
            energy_vapor_flow_packet = energy_refresh.packet

        dT_target = inputs.dT_tray_target_F_per_s
        if dT_target is None:
            dT_target = np.zeros(N, dtype=float)
        else:
            try:
                dT_target = np.asarray(dT_target, dtype=float).reshape((N,))
            except Exception:
                dT_target = np.zeros(N, dtype=float)

        alpha_v = None
        if inputs.vapor_flow_relaxation_sec is not None:
            try:
                tau_vflow = float(inputs.vapor_flow_relaxation_sec)
            except Exception:
                tau_vflow = None
            if tau_vflow is not None and np.isfinite(tau_vflow) and tau_vflow > 0.0:
                dt = getattr(getattr(col, "sim", None), "dt_sec", None)
                try:
                    dt = float(dt)
                except Exception:
                    dt = None
                if dt is not None and np.isfinite(dt) and dt > 0.0:
                    alpha_v = min(dt / tau_vflow, 1.0)
        vflow_ok = np.full(N, np.nan, dtype=float)
        vflow_denom = np.full(N, np.nan, dtype=float)
        vflow_calc = np.full(N, np.nan, dtype=float)
        vflow_used = np.full(N, np.nan, dtype=float)
        vflow_clamped = np.full(N, np.nan, dtype=float)
        vflow_limit_hi = np.full(N, np.nan, dtype=float)
        vflow_limit_lo = np.full(N, np.nan, dtype=float)
        vflow_L_in_term = np.full(N, np.nan, dtype=float)
        vflow_V_in_term = np.full(N, np.nan, dtype=float)
        vflow_feed_ref_term = np.full(N, np.nan, dtype=float)
        vflow_duty_term = np.full(N, np.nan, dtype=float)
        vflow_dE_target = np.full(N, np.nan, dtype=float)
        vflow_numer = np.full(N, np.nan, dtype=float)
        vflow_heat_capacity = np.full(N, np.nan, dtype=float)
        vflow_L_in = np.full(N, np.nan, dtype=float)
        vflow_V_in = np.full(N, np.nan, dtype=float)
        vflow_hL_in = np.full(N, np.nan, dtype=float)
        vflow_hL_out = np.full(N, np.nan, dtype=float)
        vflow_hV_in = np.full(N, np.nan, dtype=float)
        vflow_hV_out = np.full(N, np.nan, dtype=float)
        vflow_hL_in_minus_hL_out = np.full(N, np.nan, dtype=float)
        vflow_hV_in_minus_hL_out = np.full(N, np.nan, dtype=float)
        vflow_alpha = np.full(N, np.nan, dtype=float)
        if alpha_v is not None:
            vflow_alpha[1 : max(N - 1, 1)] = float(alpha_v)

        V_prev = None
        if inputs.V_out_prev_lbmolph is not None:
            try:
                V_prev = np.asarray(inputs.V_out_prev_lbmolph, dtype=float).reshape((N,)) / 3600.0
            except Exception:
                V_prev = None
        if V_prev is None:
            V_prev = V_out.copy()

        # Boundary conditions
        V_out[0] = 0.0
        V_out[-1] = boilup_s

        # March upward: use known V_out[i+1] as V_in for stage i.
        # Conservative hard limits prevent single-step numerical spikes.
        vflow_prev_up_ratio = 1.2
        vflow_prev_down_ratio = 0.8
        vflow_nominal_abs_ratio = 1.5
        # Keep the stage above the reboiler tightly coupled to boilup.
        # This suppresses slow upward drift in lower-column vapor rates.
        vflow_reb_neighbor_up_ratio = 1.02
        vflow_reb_neighbor_down_ratio = 0.98
        vflow_smooth_eps_lbmolps = _finite_positive_or_zero(
            getattr(inputs, "vflow_smooth_clamp_epsilon_lbmolps", None)
        )
        try:
            up_cfg = float(inputs.reboiler_neighbor_vflow_hi_ratio)
            if np.isfinite(up_cfg) and up_cfg > 0.0:
                vflow_reb_neighbor_up_ratio = up_cfg
        except Exception:
            pass
        try:
            dn_cfg = float(inputs.reboiler_neighbor_vflow_lo_ratio)
            if np.isfinite(dn_cfg) and dn_cfg > 0.0:
                vflow_reb_neighbor_down_ratio = dn_cfg
        except Exception:
            pass
        if vflow_reb_neighbor_down_ratio > vflow_reb_neighbor_up_ratio:
            vflow_reb_neighbor_down_ratio = vflow_reb_neighbor_up_ratio
        min_latent_abs = 100.0  # BTU/lbmol minimum |hV_out-hL_out| for stable division
        for i in range(N - 2, 0, -1):
            V_in_i = float(V_out[i + 1])
            y_in_i = y_tray[i + 1, :]

            T_L_in = float(T_tray_for_v[i - 1]) if i > 0 else float(T_tray_for_v[i])
            if i == (N - 1):
                T_V_in = float(T_reb) if ("T_reb" in locals() and T_reb is not None) else float(T_tray_for_v[i])
            else:
                T_V_in = float(T_tray_for_v[i + 1])

            if HL_cache is not None:
                if i > 0:
                    hL_in = float(HL_cache[i - 1])
                else:
                    hL_in = float(HL_cache[i])
                hL_out = float(HL_cache[i])
            else:
                hL_in = None
                if hL_stage_provider is not None:
                    src_i = i if i == 0 else (i - 1)
                    if 0 <= src_i < N and np.isfinite(hL_stage_provider[src_i]):
                        hL_in = float(hL_stage_provider[src_i])
                if hL_in is None:
                    hL_in = thermo.h_liq_btu_per_lbmol(T_L_in, P_tray_energy[i], x_in[i, :])

                hL_out = None
                if hL_stage_provider is not None and np.isfinite(hL_stage_provider[i]):
                    hL_out = float(hL_stage_provider[i])
                if hL_out is None:
                    hL_out = thermo.h_liq_btu_per_lbmol(float(T_tray_for_v[i]), P_tray_energy[i], x_tray[i, :])

            if HV_cache is not None:
                if i < (N - 1):
                    hV_in = float(HV_cache[i + 1])
                else:
                    hV_in = float(HV_cache[i])
                hV_out = float(HV_cache[i])
            else:
                hV_in = None
                if hV_stage_provider is not None:
                    src_i = i if i == (N - 1) else (i + 1)
                    if 0 <= src_i < N and np.isfinite(hV_stage_provider[src_i]):
                        hV_in = float(hV_stage_provider[src_i])
                if hV_in is None:
                    hV_in = thermo.h_vap_btu_per_lbmol(T_V_in, P_tray_energy[i], y_in_i)

                hV_out = None
                if hV_stage_provider is not None and np.isfinite(hV_stage_provider[i]):
                    hV_out = float(hV_stage_provider[i])
                if hV_out is None:
                    hV_out = thermo.h_vap_btu_per_lbmol(float(T_tray_for_v[i]), P_tray_energy[i], y_tray[i, :])

            q_feed = _feed_enthalpy_rate_btu_per_s(
                feed_stage0=feed_stage0,
                stage0=i,
                col=col,
                Nc=Nc,
                Fk_L=Fk_L,
                Fk_V=Fk_V,
                T_stage_F=float(T_tray_for_v[i]),
                P_stage_psia=float(P_tray_energy[i]),
                thermo=thermo,
                thermo_provider=inputs.thermo_provider,
                epsilon_lbmol=float(layout.epsilon_lbmol),
                feed_stage_flash_prev=inputs.feed_stage_flash_prev,
                feed_stage_flash_reuse_dT_F=float(inputs.feed_stage_flash_reuse_dT_F),
                feed_stage_flash_reuse_dP_psia=float(inputs.feed_stage_flash_reuse_dP_psia),
                feed_stage_flash_reuse_dx=float(inputs.feed_stage_flash_reuse_dx),
            )

            Q_i = 0.0
            if i == 0:
                Q_i += float(_get_condenser_duty_btu_per_h(col)) / 3600.0
            if i == (N - 1):
                Q_i += float(duty_btu_ph) / 3600.0

            use_provider_cp = bool(getattr(inputs, "energy_vapor_flow_use_provider_cp", False)) and (
                inputs.thermo_provider is not None
                and hasattr(inputs.thermo_provider, "cp_liq_vap_btu_per_lbmolF")
            )
            packet_phase_tol_liq = _phase_reuse_dx_tol(inputs, "liquid")
            packet_phase_tol_vap = _phase_reuse_dx_tol(inputs, "vapor")
            packet_dx_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dx", 0.0) or 0.0)
            packet_dT_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dT_F", 0.0) or 0.0)
            packet_dP_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dP_psia", 0.0) or 0.0)
            if use_provider_cp:
                cpL = None
                if hL_stage_provider is not None and np.isfinite(hL_stage_provider[i]):
                    cpL = _phase_cp_from_current_enthalpy_and_packet(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        current_enthalpy_btu_per_lbmol=float(hL_stage_provider[i]),
                        current_T_F=float(T_tray_for_v[i]),
                        current_P_psia=float(P_tray_energy[i]),
                        current_phase_composition=x_tray[i, :],
                        phase="liquid",
                        max_abs_dx=packet_phase_tol_liq,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                cpV = None
                if hV_stage_provider is not None and np.isfinite(hV_stage_provider[i]):
                    cpV = _phase_cp_from_current_enthalpy_and_packet(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        current_enthalpy_btu_per_lbmol=float(hV_stage_provider[i]),
                        current_T_F=float(T_tray_for_v[i]),
                        current_P_psia=float(P_tray_energy[i]),
                        current_phase_composition=y_tray[i, :],
                        phase="vapor",
                        max_abs_dx=packet_phase_tol_vap,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                z_for_cp = tray_L[i, :].copy()
                if tray_V is not None:
                    z_for_cp = z_for_cp + tray_V[i, :]
                s = float(np.sum(z_for_cp))
                if s <= layout.epsilon_lbmol:
                    z_for_cp = x_tray[i, :].copy()
                    s = float(np.sum(z_for_cp))
                z_for_cp = z_for_cp / max(s, 1e-300)
                if cpL is None:
                    cpL = _packet_cp_if_compatible(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        T_F=float(T_tray_for_v[i]),
                        P_psia=float(P_tray_energy[i]),
                        z_overall=z_for_cp,
                        phase="liquid",
                        max_abs_dx=packet_dx_tol,
                        max_abs_dT_F=packet_dT_tol,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                if cpV is None:
                    cpV = _packet_cp_if_compatible(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        T_F=float(T_tray_for_v[i]),
                        P_psia=float(P_tray_energy[i]),
                        z_overall=z_for_cp,
                        phase="vapor",
                        max_abs_dx=packet_dx_tol,
                        max_abs_dT_F=packet_dT_tol,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                if cpL is None or cpV is None:
                    try:
                        cpL, cpV = _provider_cp_liq_vap_btu_per_lbmolF(
                            inputs.thermo_provider,
                            float(T_tray_for_v[i]),
                            float(P_tray_energy[i]),
                            z_for_cp,
                            thermo_call_category="energy_vapor_flow_cp_lookup",
                        )
                    except Exception:
                        cpL = cpV = None
            else:
                cpL = cpV = None
            if cpL is None or cpV is None:
                cpL = thermo.cp_liq_btu_per_lbmolF(float(T_tray_for_v[i]), P_tray_energy[i], x_tray[i, :])
                cpV = thermo.cp_vap_btu_per_lbmolF(float(T_tray_for_v[i]), P_tray_energy[i], y_tray[i, :])

            ML_tot = float(np.sum(tray_L[i, :]))
            MV_tot = float(np.sum(tray_V[i, :])) if tray_V is not None else 0.0
            C = ML_tot * cpL + MV_tot * cpV
            dE_target = float(C) * float(dT_target[i])

            # Solve V_out from a reference-invariant tray energy relation with fixed L_out.
            #
            # Using dE_target = C*dT directly with absolute enthalpies is not datum-invariant.
            # Rewriting around hL_out gives:
            #   dE_target = L_in*(hL_in-hL_out) + V_in*(hV_in-hL_out)
            #            + F_L*(hF_L-hL_out) + F_V*(hF_V-hL_out) + Q
            #            - V_out*(hV_out-hL_out)
            # so:
            #   V_out = [ ... - dE_target ] / (hV_out - hL_out)
            denom = float(hV_out - hL_out)
            ft_feed_i = (Ft_L + Ft_V) if (feed_stage0 == i) else 0.0
            L_in_term = L_in[i] * (hL_in - hL_out)
            V_in_term = V_in_i * (hV_in - hL_out)
            feed_ref_term = q_feed - ft_feed_i * hL_out
            numer = L_in_term + V_in_term + feed_ref_term + Q_i - dE_target

            vflow_denom[i] = float(denom)
            vflow_L_in_term[i] = float(L_in_term)
            vflow_V_in_term[i] = float(V_in_term)
            vflow_feed_ref_term[i] = float(feed_ref_term)
            vflow_duty_term[i] = float(Q_i)
            vflow_dE_target[i] = float(dE_target)
            vflow_numer[i] = float(numer)
            vflow_heat_capacity[i] = float(C)
            vflow_L_in[i] = float(L_in[i])
            vflow_V_in[i] = float(V_in_i)
            vflow_hL_in[i] = float(hL_in)
            vflow_hL_out[i] = float(hL_out)
            vflow_hV_in[i] = float(hV_in)
            vflow_hV_out[i] = float(hV_out)
            vflow_hL_in_minus_hL_out[i] = float(hL_in - hL_out)
            vflow_hV_in_minus_hL_out[i] = float(hV_in - hL_out)
            ok = bool(np.isfinite(denom) and (abs(denom) > min_latent_abs))

            if not ok:
                V_calc = float(V_prev[i]) if V_prev is not None else float(V_out[i])
            else:
                V_calc = numer / denom
            if not np.isfinite(V_calc):
                ok = False

            if not np.isfinite(V_calc) or V_calc < 0.0:
                V_calc = 0.0
                ok = False

            # Hard clamp relative to previous and nominal profile values.
            # This keeps startup transients from exploding internal vapor rates.
            V_prev_i = max(float(V_prev[i]), 0.0)
            V_nom_i = max(float(V_out_profile[i]), 0.0)

            if vflow_smooth_eps_lbmolps > 0.0:
                V_hi = _smooth_max_scalar(
                    _smooth_max_scalar(
                        vflow_prev_up_ratio * V_prev_i,
                        vflow_nominal_abs_ratio * V_nom_i,
                        vflow_smooth_eps_lbmolps,
                    ),
                    float(boilup_s),
                    vflow_smooth_eps_lbmolps,
                )
            else:
                V_hi = max(
                    vflow_prev_up_ratio * V_prev_i,
                    vflow_nominal_abs_ratio * V_nom_i,
                    float(boilup_s),
                )
            V_lo = 0.0
            if V_prev_i > layout.epsilon_lbmol and V_nom_i > layout.epsilon_lbmol:
                V_lo = min(vflow_prev_down_ratio * V_prev_i, vflow_prev_down_ratio * V_nom_i)

            # Reboiler-neighbor guard: keep tray N-1 near reboiler boilup to
            # avoid non-physical long-horizon growth in lower-section vapor flow.
            if i == (N - 2):
                V_hi_reb = vflow_reb_neighbor_up_ratio * float(boilup_s)
                if vflow_smooth_eps_lbmolps > 0.0:
                    V_hi = _smooth_min_scalar(V_hi, V_hi_reb, vflow_smooth_eps_lbmolps)
                else:
                    V_hi = min(V_hi, V_hi_reb)
                if float(boilup_s) > layout.epsilon_lbmol:
                    V_lo_reb = vflow_reb_neighbor_down_ratio * float(boilup_s)
                    if vflow_smooth_eps_lbmolps > 0.0:
                        V_lo = _smooth_max_scalar(V_lo, V_lo_reb, vflow_smooth_eps_lbmolps)
                    else:
                        V_lo = max(V_lo, V_lo_reb)

            if V_hi < V_lo:
                V_hi = V_lo

            vflow_limit_hi[i] = float(V_hi) * 3600.0
            vflow_limit_lo[i] = float(V_lo) * 3600.0
            V_calc_raw = float(V_calc)
            clamped = bool((V_calc_raw > V_hi) or (V_calc_raw < V_lo))
            if vflow_smooth_eps_lbmolps > 0.0:
                V_calc = _smooth_clip_scalar(V_calc_raw, V_lo, V_hi, vflow_smooth_eps_lbmolps)
            else:
                if V_calc_raw > V_hi:
                    V_calc = V_hi
                elif V_calc_raw < V_lo:
                    V_calc = V_lo
            vflow_clamped[i] = 1.0 if clamped else 0.0

            vflow_ok[i] = 1.0 if ok else 0.0
            vflow_calc[i] = float(V_calc) * 3600.0

            if alpha_v is not None and V_prev is not None:
                V_out[i] = float(V_prev[i] + alpha_v * (V_calc - V_prev[i]))
            else:
                V_out[i] = float(V_calc)
            vflow_used[i] = float(V_out[i]) * 3600.0

        vflow_diag = {
            "vflow_energy_ok": vflow_ok,
            "vflow_energy_denom_BTU_per_lbmol": vflow_denom,
            "vflow_energy_calc_lbmolph": vflow_calc,
            "vflow_energy_used_lbmolph": vflow_used,
            "vflow_energy_clamped": vflow_clamped,
            "vflow_energy_limit_hi_lbmolph": vflow_limit_hi,
            "vflow_energy_limit_lo_lbmolph": vflow_limit_lo,
            "vflow_energy_L_in_term_BTUps": vflow_L_in_term,
            "vflow_energy_V_in_term_BTUps": vflow_V_in_term,
            "vflow_energy_feed_ref_term_BTUps": vflow_feed_ref_term,
            "vflow_energy_duty_term_BTUps": vflow_duty_term,
            "vflow_energy_dE_target_BTUps": vflow_dE_target,
            "vflow_energy_numer_BTUps": vflow_numer,
            "vflow_energy_heat_capacity_BTU_per_F": vflow_heat_capacity,
            "vflow_energy_L_in_lbmolph": vflow_L_in * 3600.0,
            "vflow_energy_V_in_lbmolph": vflow_V_in * 3600.0,
            "vflow_energy_hL_in_BTU_per_lbmol": vflow_hL_in,
            "vflow_energy_hL_out_BTU_per_lbmol": vflow_hL_out,
            "vflow_energy_hV_in_BTU_per_lbmol": vflow_hV_in,
            "vflow_energy_hV_out_BTU_per_lbmol": vflow_hV_out,
            "vflow_energy_hL_in_minus_hL_out_BTU_per_lbmol": vflow_hL_in_minus_hL_out,
            "vflow_energy_hV_in_minus_hL_out_BTU_per_lbmol": vflow_hV_in_minus_hL_out,
            "vflow_relax_alpha": vflow_alpha,
            "vflow_smooth_clamp_eps_lbmolph": np.array(
                [float(vflow_smooth_eps_lbmolps) * 3600.0],
                dtype=float,
            ),
        }
        if N >= 2:
            reb_neighbor_idx = N - 2
            vflow_diag["reboiler_neighbor_stage_1based"] = np.array([float(reb_neighbor_idx + 1)], dtype=float)
            vflow_diag["reboiler_neighbor_vflow_calc_lbmolph"] = np.array(
                [float(vflow_calc[reb_neighbor_idx])],
                dtype=float,
            )
            vflow_diag["reboiler_neighbor_vflow_used_lbmolph"] = np.array(
                [float(vflow_used[reb_neighbor_idx])],
                dtype=float,
            )
            vflow_diag["reboiler_neighbor_vflow_limit_hi_lbmolph"] = np.array(
                [float(vflow_limit_hi[reb_neighbor_idx])],
                dtype=float,
            )
            vflow_diag["reboiler_neighbor_vflow_limit_lo_lbmolph"] = np.array(
                [float(vflow_limit_lo[reb_neighbor_idx])],
                dtype=float,
            )
            vflow_diag["reboiler_neighbor_vflow_clamped_flag"] = np.array(
                [float(vflow_clamped[reb_neighbor_idx])],
                dtype=float,
            )

    vapor_homotopy_beta_used = np.nan
    vapor_homotopy_delta_lbmolph = np.full(N, np.nan, dtype=float)
    vapor_homotopy_active = False
    if vflow_model in ("energy", "conductance") and getattr(inputs, "vapor_flow_homotopy_beta", None) is not None:
        try:
            beta_try = float(inputs.vapor_flow_homotopy_beta)
        except Exception:
            beta_try = np.nan
        if np.isfinite(beta_try):
            beta = float(np.clip(beta_try, 0.0, 1.0))
            V_dynamic = np.asarray(V_out, dtype=float).reshape((N,)).copy()
            V_profile = np.asarray(V_out_profile, dtype=float).reshape((N,)).copy()
            V_blended = (1.0 - beta) * V_profile + beta * V_dynamic
            V_blended[0] = V_dynamic[0]
            V_blended[-1] = V_dynamic[-1]
            V_out[:] = np.where(np.isfinite(V_blended) & (V_blended >= 0.0), V_blended, V_dynamic)
            vapor_homotopy_beta_used = beta
            vapor_homotopy_active = True
            vapor_homotopy_delta_lbmolph = (V_dynamic - V_profile) * 3600.0
            if vflow_diag is None:
                vflow_diag = {}
            vflow_diag["vflow_homotopy_beta"] = np.array([float(beta)], dtype=float)
            vflow_diag["vflow_homotopy_active"] = np.array([1.0], dtype=float)
            vflow_diag["vflow_homotopy_dynamic_minus_profile_lbmolph"] = (
                np.asarray(vapor_homotopy_delta_lbmolph, dtype=float).reshape((N,))
            )
            vflow_diag["vflow_homotopy_used_lbmolph"] = np.asarray(V_out, dtype=float).reshape((N,)) * 3600.0

    V_in = np.zeros(N, dtype=float)
    y_in = np.zeros((N, Nc), dtype=float)
    for i in range(N):
        if i == N - 1:
            V_in[i] = boilup_s
            y_in[i, :] = y_reb_eq if y_reb_eq is not None else y_rebV
        else:
            V_in[i] = V_out[i + 1]
            y_in[i, :] = y_tray[i + 1, :]

    P_tray_hyd = None
    P_tray_hyd_raw = None
    P_tray_hyd_relax_alpha = None
    top_pressure_ordering_lift_psia = 0.0
    P_top_drum_psia = None
    P_top_drum_psia_raw = np.nan
    V_top_drum_vapor_ft3 = None
    V_top_drum_liquid_ft3 = None
    rho_top_drum_liquid_lbmol_ft3 = None
    top_drum_pressure_T_raw_F = np.nan
    top_drum_pressure_T_used_F = np.nan
    top_drum_pressure_T_relax_alpha = np.nan
    top_drum_pressure_Z = np.nan
    top_drum_MV_lbmol = np.nan
    debug_top_drum_pressure_clamp_active = False
    debug_top_drum_pressure_clamp_raw_psia = np.nan
    debug_top_drum_pressure_clamp_psia = np.nan
    debug_p_clamp_raw = getattr(inputs, "debug_clamp_top_drum_pressure_psia", None)
    debug_p_clamp_psia = None
    debug_p_clamp_duration_raw = getattr(inputs, "debug_clamp_top_drum_pressure_duration_sec", None)
    debug_p_clamp_allowed = True
    if debug_p_clamp_duration_raw is not None:
        try:
            clamp_duration = float(debug_p_clamp_duration_raw)
            debug_p_clamp_allowed = bool(
                np.isfinite(clamp_duration)
                and clamp_duration > 0.0
                and float(t) <= float(clamp_duration)
            )
        except Exception:
            debug_p_clamp_allowed = True
    if debug_p_clamp_raw is not None and debug_p_clamp_allowed:
        try:
            debug_p_try = float(debug_p_clamp_raw)
            if np.isfinite(debug_p_try) and debug_p_try > 0.0:
                debug_p_clamp_psia = float(debug_p_try)
        except Exception:
            debug_p_clamp_psia = None
    p_hyd_details_pending: Optional[Dict[str, np.ndarray]] = None
    if (inputs.pressure_model or "").strip().lower() == "hydraulic":
        geom = getattr(col, "geometry", None)
        if geom is not None:
            if "tray_T_f" in u:
                T_tray_for_p = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
            elif hasattr(col, "T_f"):
                T_tray_for_p = np.asarray(col.T_f, dtype=float).reshape((N,))
            else:
                T_tray_for_p = np.full(N, 100.0, dtype=float)

            if hasattr(col, "P_psia"):
                P_profile = np.asarray(col.P_psia, dtype=float).reshape((N,))
                P_anchor = float(np.asarray(col.P_psia, dtype=float).reshape((N,))[-1])
                P_top_spec = float(P_profile[0]) if np.isfinite(float(P_profile[0])) else None
            else:
                P_anchor = float(200.0)
                P_top_spec = None

            Z_for_p = (
                np.asarray(inputs.Zfac_prev, dtype=float).reshape((N,))
                if inputs.Zfac_prev is not None
                else np.ones(N, dtype=float)
            )

            # Dynamic top pressure state from reflux-drum vapor holdup.
            top_anchor_from_holdup = None
            if layout.include_top and top_V is not None:
                # Top-drum pressure state uses an ideal-gas Z basis for
                # robustness; tray Z estimates can be noisy during fast startup.
                z_top = 1.0
                top_vap_vol_ft3 = None
                top_liq_vol_ft3 = None
                rho_top_liq = None
                top_total_vol_ft3 = None
                top_extra_vap_vol_ft3 = 0.0
                if inputs.top_drum_extra_vapor_volume_ft3 is not None:
                    try:
                        vextra_try = float(inputs.top_drum_extra_vapor_volume_ft3)
                        if np.isfinite(vextra_try) and vextra_try > 0.0:
                            top_extra_vap_vol_ft3 = float(vextra_try)
                    except Exception:
                        top_extra_vap_vol_ft3 = 0.0
                if inputs.top_drum_total_volume_ft3 is not None:
                    try:
                        vtot_try = float(inputs.top_drum_total_volume_ft3)
                        if np.isfinite(vtot_try) and vtot_try > 0.0:
                            top_total_vol_ft3 = vtot_try
                    except Exception:
                        top_total_vol_ft3 = None
                if top_total_vol_ft3 is not None:
                    if inputs.rhoL_tray_lbmol_ft3 is not None:
                        try:
                            rho_arr = np.asarray(inputs.rhoL_tray_lbmol_ft3, dtype=float).reshape((N,))
                            rho_try = float(rho_arr[0])
                            if np.isfinite(rho_try) and rho_try > 1e-12:
                                rho_top_liq = rho_try
                        except Exception:
                            rho_top_liq = None
                    if rho_top_liq is None and inputs.thermo_provider is not None and hasattr(inputs.thermo_provider, "liquid_density_lbmol_ft3"):
                        try:
                            P_top_est = float(P_profile[0]) if np.isfinite(float(P_profile[0])) else 200.0
                            with _thermo_provider_category(inputs.thermo_provider, "top_drum_liquid_density_lookup"):
                                rho_try = float(
                                    inputs.thermo_provider.liquid_density_lbmol_ft3(
                                        float(T_tray_for_p[0]),
                                        float(P_top_est),
                                        np.asarray(x_topL, dtype=float).reshape((Nc,)),
                                    )
                                )
                            if np.isfinite(rho_try) and rho_try > 1e-12:
                                rho_top_liq = rho_try
                        except Exception:
                            rho_top_liq = None
                    if rho_top_liq is not None and top_L is not None:
                        try:
                            m_top_liq = float(np.sum(np.asarray(top_L, dtype=float).reshape((Nc,))))
                            if np.isfinite(m_top_liq) and m_top_liq >= 0.0:
                                top_liq_vol_ft3 = max(m_top_liq / float(rho_top_liq), 0.0)
                        except Exception:
                            top_liq_vol_ft3 = None
                    if top_liq_vol_ft3 is not None:
                        top_liq_vol_ft3 = float(np.clip(top_liq_vol_ft3, 0.0, float(top_total_vol_ft3)))
                        top_vap_vol_ft3 = float(top_total_vol_ft3) - float(top_liq_vol_ft3) + float(top_extra_vap_vol_ft3)
                        if top_vap_vol_ft3 < 1e-3:
                            top_vap_vol_ft3 = 1e-3
                    elif inputs.top_drum_vapor_volume_ft3 is not None:
                        try:
                            v_try = float(inputs.top_drum_vapor_volume_ft3)
                            if np.isfinite(v_try) and v_try > 0.0:
                                top_vap_vol_ft3 = min(v_try, float(top_total_vol_ft3)) + float(top_extra_vap_vol_ft3)
                        except Exception:
                            top_vap_vol_ft3 = None
                if inputs.top_drum_vapor_volume_ft3 is not None:
                    if top_vap_vol_ft3 is None:
                        try:
                            v_try = float(inputs.top_drum_vapor_volume_ft3)
                            if np.isfinite(v_try) and v_try > 0.0:
                                top_vap_vol_ft3 = v_try
                        except Exception:
                            top_vap_vol_ft3 = None
                if top_vap_vol_ft3 is None:
                    try:
                        if inputs.volume_model.vapor_volume_ft3_per_stage is not None:
                            vv = np.asarray(inputs.volume_model.vapor_volume_ft3_per_stage, dtype=float).reshape((N,))
                            v_try = float(vv[0])
                        else:
                            v_try = float(inputs.volume_model.default_vapor_volume_ft3)
                        if np.isfinite(v_try) and v_try > 0.0:
                            top_vap_vol_ft3 = v_try
                    except Exception:
                        top_vap_vol_ft3 = None
                if top_vap_vol_ft3 is not None:
                    V_top_drum_vapor_ft3 = float(top_vap_vol_ft3)
                    if top_liq_vol_ft3 is not None:
                        V_top_drum_liquid_ft3 = float(top_liq_vol_ft3)
                    if rho_top_liq is not None:
                        rho_top_drum_liquid_lbmol_ft3 = float(rho_top_liq)
                    top_T_raw_F = float(T_tray_for_p[0])
                    top_T_use_F, top_T_alpha = _lagged_top_drum_pressure_temperature_F(
                        top_T_raw_F=top_T_raw_F,
                        top_T_prev_used_F=inputs.top_drum_pressure_T_prev_F,
                        T_tray_prev_F=inputs.T_tray_prev_F,
                        n_stages=N,
                        dt_sec=getattr(getattr(col, "sim", None), "dt_sec", None),
                        tau_sec=inputs.top_drum_pressure_temperature_relaxation_sec,
                        tau_fallback_sec=inputs.vapor_holdup_relaxation_sec,
                    )
                    top_drum_pressure_T_raw_F = float(top_T_raw_F)
                    top_drum_pressure_T_used_F = float(top_T_use_F)
                    if top_T_alpha is not None and np.isfinite(float(top_T_alpha)):
                        top_drum_pressure_T_relax_alpha = float(top_T_alpha)
                    p_top_res = _compute_top_drum_pressure_psia(
                        top_V=np.asarray(top_V, dtype=float).reshape((Nc,)),
                        top_T_F=float(top_T_use_F),
                        Z_top=float(z_top),
                        top_vapor_volume_ft3=float(top_vap_vol_ft3),
                        thermo_provider=inputs.thermo_provider,
                        y_top=np.asarray(y_topV, dtype=float).reshape((Nc,)),
                        P_seed_psia=(float(P_profile[0]) if np.isfinite(float(P_profile[0])) else None),
                        return_details=True,
                        allow_flash_fallback_on_refine_failure=False,
                    )
                    if isinstance(p_top_res, tuple):
                        P_top_drum_psia, z_top_eval, mv_top_eval = p_top_res
                    else:
                        P_top_drum_psia = p_top_res
                        z_top_eval = None
                        mv_top_eval = None
                    if P_top_drum_psia is not None and np.isfinite(float(P_top_drum_psia)) and float(P_top_drum_psia) > 0.0:
                        P_top_drum_psia_raw = float(P_top_drum_psia)
                        top_anchor_from_holdup = float(P_top_drum_psia)
                    if z_top_eval is not None and np.isfinite(float(z_top_eval)) and float(z_top_eval) > 0.0:
                        top_drum_pressure_Z = float(z_top_eval)
                    if mv_top_eval is not None and np.isfinite(float(mv_top_eval)) and float(mv_top_eval) >= 0.0:
                        top_drum_MV_lbmol = float(mv_top_eval)

            if debug_p_clamp_psia is not None:
                if P_top_drum_psia is not None and np.isfinite(float(P_top_drum_psia)):
                    debug_top_drum_pressure_clamp_raw_psia = float(P_top_drum_psia)
                P_top_drum_psia = float(debug_p_clamp_psia)
                P_top_drum_psia_raw = (
                    float(debug_top_drum_pressure_clamp_raw_psia)
                    if np.isfinite(float(debug_top_drum_pressure_clamp_raw_psia))
                    else float(debug_p_clamp_psia)
                )
                top_anchor_from_holdup = float(debug_p_clamp_psia)
                debug_top_drum_pressure_clamp_active = True
                debug_top_drum_pressure_clamp_psia = float(debug_p_clamp_psia)

            top_anchor_psia = inputs.pressure_top_anchor_psia
            if top_anchor_psia is None and debug_top_drum_pressure_clamp_active:
                top_anchor_psia = float(P_top_drum_psia)
            if (
                top_anchor_psia is None
                and bool(getattr(inputs, "hydraulic_use_top_drum_pressure_as_anchor", False))
                and P_top_drum_psia is not None
                and np.isfinite(float(P_top_drum_psia))
                and float(P_top_drum_psia) > 0.0
            ):
                top_anchor_psia = float(P_top_drum_psia)
            P_tray_hyd_free = None
            if top_anchor_psia is None and N > 1:
                try:
                    P_hyd_free_out = _pressure_profile_hydraulic_psia(
                        P_bottom_psia=P_anchor,
                        T_F=T_tray_for_p,
                        V_in_lbmolps=V_in,
                        y_tray=y_tray,
                        x_tray=x_tray,
                        Z_vap=Z_for_p,
                        geom=geom,
                        h_ow_ft=h_ow_ft,
                        rhoL_lbmol_ft3=rhoL_tray,
                        mw_components=inputs.component_mw_lbm_per_lbmol,
                        dry_tray_K=float(inputs.dry_tray_K),
                        P_top_spec_psia=P_top_spec,
                        P_top_anchor_psia=None,
                        condenser_pressure_drop_psi=inputs.condenser_pressure_drop_psi,
                        return_details=True,
                    )
                    if isinstance(P_hyd_free_out, tuple):
                        P_tray_hyd_free, p_hyd_details = P_hyd_free_out
                        if isinstance(p_hyd_details, dict):
                            p_hyd_details_pending = dict(p_hyd_details)
                    else:
                        P_tray_hyd_free = P_hyd_free_out
                    P_tray_hyd_free = np.asarray(P_tray_hyd_free, dtype=float).reshape((N,))
                except Exception:
                    P_tray_hyd_free = None

            if top_anchor_psia is None and P_tray_hyd_free is not None:
                # In open-loop hydraulic mode, keep tray pressure on the free
                # hydraulic profile rather than scaling all tray drops to the
                # reflux-drum pressure state.
                P_tray_hyd = np.asarray(P_tray_hyd_free, dtype=float).reshape((N,))
                if (
                    bool(getattr(inputs, "enforce_top_drum_pressure_continuity", True))
                    and P_top_drum_psia is not None
                    and np.isfinite(float(P_top_drum_psia))
                    and float(P_top_drum_psia) > 0.0
                    and np.isfinite(float(P_tray_hyd[0]))
                    and float(P_tray_hyd[0]) > 0.0
                ):
                    try:
                        max_gap = float(
                            getattr(
                                inputs,
                                "top_drum_pressure_continuity_max_gap_psi",
                                1.0,
                            )
                        )
                    except Exception:
                        max_gap = 1.0
                    if (not np.isfinite(max_gap)) or max_gap < 0.0:
                        max_gap = 1.0
                    gap_top = float(P_tray_hyd[0]) - float(P_top_drum_psia)
                    if abs(float(gap_top)) > float(max_gap):
                        shift_psia = float(P_top_drum_psia) - float(P_tray_hyd[0])
                        p_shifted = np.asarray(P_tray_hyd, dtype=float) + float(shift_psia)
                        if np.all(np.isfinite(p_shifted)) and np.all(p_shifted > 1.0):
                            P_tray_hyd = p_shifted
            else:
                P_hyd_out = _pressure_profile_hydraulic_psia(
                    P_bottom_psia=P_anchor,
                    T_F=T_tray_for_p,
                    V_in_lbmolps=V_in,
                    y_tray=y_tray,
                    x_tray=x_tray,
                    Z_vap=Z_for_p,
                    geom=geom,
                    h_ow_ft=h_ow_ft,
                    rhoL_lbmol_ft3=rhoL_tray,
                    mw_components=inputs.component_mw_lbm_per_lbmol,
                    dry_tray_K=float(inputs.dry_tray_K),
                    P_top_spec_psia=P_top_spec,
                    P_top_anchor_psia=top_anchor_psia,
                    condenser_pressure_drop_psi=inputs.condenser_pressure_drop_psi,
                    return_details=True,
                )
                if isinstance(P_hyd_out, tuple):
                    P_tray_hyd, p_hyd_details = P_hyd_out
                    if isinstance(p_hyd_details, dict):
                        p_hyd_details_pending = dict(p_hyd_details)
                else:
                    P_tray_hyd = P_hyd_out
            try:
                P_tray_hyd_raw = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
            except Exception:
                P_tray_hyd_raw = None

            # Optional low-pass on hydraulic pressure to damp explicit feedback shocks.
            # Use dedicated hydraulic timescale when provided; otherwise fall back
            # to vapor holdup relaxation for compatibility.
            tau_p = inputs.hydraulic_pressure_relaxation_sec
            if tau_p is None:
                tau_p = inputs.vapor_holdup_relaxation_sec
            if P_tray_hyd_raw is not None and tau_p is not None:
                try:
                    tau_p = float(tau_p)
                except Exception:
                    tau_p = None
                if tau_p is not None and np.isfinite(tau_p) and tau_p > 0.0:
                    dt_p = getattr(getattr(col, "sim", None), "dt_sec", None)
                    try:
                        dt_p = float(dt_p)
                    except Exception:
                        dt_p = None
                    if dt_p is not None and np.isfinite(dt_p) and dt_p > 0.0:
                        alpha_p = float(np.clip(dt_p / tau_p, 0.0, 1.0))
                        P_tray_hyd_relax_alpha = alpha_p
                        P_prev = None
                        if inputs.P_tray_prev is not None:
                            try:
                                P_prev = np.asarray(inputs.P_tray_prev, dtype=float).reshape((N,))
                            except Exception:
                                P_prev = None
                        if P_prev is not None:
                            P_blend = np.asarray(P_tray_hyd_raw, dtype=float).copy()
                            d_raw = np.diff(np.asarray(P_tray_hyd_raw, dtype=float))
                            d_prev = np.diff(np.asarray(P_prev, dtype=float))
                            d_blend = np.asarray(d_raw, dtype=float).copy()
                            valid_d = np.isfinite(d_prev) & np.isfinite(d_raw)
                            d_blend[valid_d] = d_prev[valid_d] + alpha_p * (d_raw[valid_d] - d_prev[valid_d])
                            d_blend = np.where(~np.isfinite(d_blend), d_raw, d_blend)
                            # Preserve the explicit condenser drop at the
                            # top boundary when a top anchor is active.
                            # Low-passing this first differential can suppress
                            # the stage-2 -> top-drum pressure gap and nearly
                            # close the condenser pressure gate from t=0.
                            cond_dp_fixed = 0.0
                            if inputs.condenser_pressure_drop_psi is not None:
                                try:
                                    cond_try = float(inputs.condenser_pressure_drop_psi)
                                    if np.isfinite(cond_try) and cond_try > 0.0:
                                        cond_dp_fixed = float(cond_try)
                                except Exception:
                                    cond_dp_fixed = 0.0
                            if (
                                top_anchor_psia is not None
                                and cond_dp_fixed > 0.0
                                and d_blend.size > 0
                                and np.isfinite(float(d_raw[0]))
                                and float(d_raw[0]) > 0.0
                            ):
                                d_blend[0] = float(d_raw[0])
                            # Preserve an explicit top anchor when one is active.
                            # Otherwise preserve the bottom hydraulic anchor so
                            # open-loop free-pressure runs cannot walk away from
                            # the specified reboiler-side pressure boundary.
                            if top_anchor_psia is not None and (
                                np.isfinite(float(P_tray_hyd_raw[0]))
                                and float(P_tray_hyd_raw[0]) > 0.0
                            ):
                                P_blend = np.empty(N, dtype=float)
                                P_blend[0] = float(P_tray_hyd_raw[0])
                                for j in range(1, N):
                                    P_blend[j] = float(P_blend[j - 1]) + float(d_blend[j - 1])
                                bad = (~np.isfinite(P_blend)) | (P_blend <= 0.0)
                                P_blend[bad] = P_tray_hyd_raw[bad]
                            elif np.isfinite(float(P_anchor)) and float(P_anchor) > 0.0:
                                P_blend = np.empty(N, dtype=float)
                                P_blend[-1] = float(P_anchor)
                                for j in range(N - 2, -1, -1):
                                    P_blend[j] = float(P_blend[j + 1]) - float(d_blend[j])
                                bad = (~np.isfinite(P_blend)) | (P_blend <= 0.0)
                                P_blend[bad] = P_tray_hyd_raw[bad]
                            else:
                                valid = (
                                    np.isfinite(P_prev)
                                    & (P_prev > 0.0)
                                    & np.isfinite(P_tray_hyd_raw)
                                    & (P_tray_hyd_raw > 0.0)
                                )
                                P_blend[valid] = P_prev[valid] + alpha_p * (P_tray_hyd_raw[valid] - P_prev[valid])
                                bad = (~np.isfinite(P_blend)) | (P_blend <= 0.0)
                                P_blend[bad] = P_tray_hyd_raw[bad]
                            P_tray_hyd = P_blend
    if layout.include_top and top_V is not None:
        if P_top_drum_psia is None or (not np.isfinite(float(P_top_drum_psia))) or float(P_top_drum_psia) <= 0.0:
            top_vap_vol_ft3 = None
            top_liq_vol_ft3 = None
            rho_top_liq = None
            top_total_vol_ft3 = None
            top_extra_vap_vol_ft3 = 0.0
            if inputs.top_drum_extra_vapor_volume_ft3 is not None:
                try:
                    vextra_try = float(inputs.top_drum_extra_vapor_volume_ft3)
                    if np.isfinite(vextra_try) and vextra_try > 0.0:
                        top_extra_vap_vol_ft3 = float(vextra_try)
                except Exception:
                    top_extra_vap_vol_ft3 = 0.0
            if inputs.top_drum_total_volume_ft3 is not None:
                try:
                    vtot_try = float(inputs.top_drum_total_volume_ft3)
                    if np.isfinite(vtot_try) and vtot_try > 0.0:
                        top_total_vol_ft3 = vtot_try
                except Exception:
                    top_total_vol_ft3 = None
            if top_total_vol_ft3 is not None:
                if inputs.rhoL_tray_lbmol_ft3 is not None:
                    try:
                        rho_arr = np.asarray(inputs.rhoL_tray_lbmol_ft3, dtype=float).reshape((N,))
                        rho_try = float(rho_arr[0])
                        if np.isfinite(rho_try) and rho_try > 1e-12:
                            rho_top_liq = rho_try
                    except Exception:
                        rho_top_liq = None
                if rho_top_liq is None and inputs.thermo_provider is not None and hasattr(inputs.thermo_provider, "liquid_density_lbmol_ft3"):
                    try:
                        p_top_est = float(P_profile[0]) if np.isfinite(float(P_profile[0])) else 200.0
                        with _thermo_provider_category(inputs.thermo_provider, "top_drum_liquid_density_lookup"):
                            rho_try = float(
                                inputs.thermo_provider.liquid_density_lbmol_ft3(
                                    float(np.asarray(u["tray_T_f"], dtype=float).reshape((N,))[0]) if "tray_T_f" in u else float(np.asarray(col.T_f, dtype=float).reshape((N,))[0]),
                                    float(p_top_est),
                                    np.asarray(x_topL, dtype=float).reshape((Nc,)),
                                )
                            )
                        if np.isfinite(rho_try) and rho_try > 1e-12:
                            rho_top_liq = rho_try
                    except Exception:
                        rho_top_liq = None
                if rho_top_liq is not None and top_L is not None:
                    try:
                        m_top_liq = float(np.sum(np.asarray(top_L, dtype=float).reshape((Nc,))))
                        if np.isfinite(m_top_liq) and m_top_liq >= 0.0:
                            top_liq_vol_ft3 = max(m_top_liq / float(rho_top_liq), 0.0)
                    except Exception:
                        top_liq_vol_ft3 = None
                if top_liq_vol_ft3 is not None:
                    top_liq_vol_ft3 = float(np.clip(top_liq_vol_ft3, 0.0, float(top_total_vol_ft3)))
                    top_vap_vol_ft3 = float(top_total_vol_ft3) - float(top_liq_vol_ft3) + float(top_extra_vap_vol_ft3)
                    if top_vap_vol_ft3 < 1e-3:
                        top_vap_vol_ft3 = 1e-3
            if (
                top_vap_vol_ft3 is None
                and V_top_drum_vapor_ft3 is not None
                and np.isfinite(float(V_top_drum_vapor_ft3))
                and float(V_top_drum_vapor_ft3) > 0.0
            ):
                top_vap_vol_ft3 = float(V_top_drum_vapor_ft3)
            elif top_vap_vol_ft3 is None and inputs.top_drum_vapor_volume_ft3 is not None:
                try:
                    v_try = float(inputs.top_drum_vapor_volume_ft3)
                    if np.isfinite(v_try) and v_try > 0.0:
                        top_vap_vol_ft3 = v_try + float(top_extra_vap_vol_ft3)
                except Exception:
                    top_vap_vol_ft3 = None
            if top_vap_vol_ft3 is None:
                try:
                    if inputs.volume_model.vapor_volume_ft3_per_stage is not None:
                        vv = np.asarray(inputs.volume_model.vapor_volume_ft3_per_stage, dtype=float).reshape((N,))
                        v_try = float(vv[0])
                    else:
                        v_try = float(inputs.volume_model.default_vapor_volume_ft3)
                    if np.isfinite(v_try) and v_try > 0.0:
                        top_vap_vol_ft3 = v_try
                except Exception:
                    top_vap_vol_ft3 = None
            if top_vap_vol_ft3 is not None:
                z_top = 1.0
                if "tray_T_f" in u:
                    top_T_F = float(np.asarray(u["tray_T_f"], dtype=float).reshape((N,))[0])
                elif hasattr(col, "T_f"):
                    top_T_F = float(np.asarray(col.T_f, dtype=float).reshape((N,))[0])
                else:
                    top_T_F = 100.0
                top_T_use_F, top_T_alpha = _lagged_top_drum_pressure_temperature_F(
                    top_T_raw_F=float(top_T_F),
                    top_T_prev_used_F=inputs.top_drum_pressure_T_prev_F,
                    T_tray_prev_F=inputs.T_tray_prev_F,
                    n_stages=N,
                    dt_sec=getattr(getattr(col, "sim", None), "dt_sec", None),
                    tau_sec=inputs.top_drum_pressure_temperature_relaxation_sec,
                    tau_fallback_sec=inputs.vapor_holdup_relaxation_sec,
                )
                top_drum_pressure_T_raw_F = float(top_T_F)
                top_drum_pressure_T_used_F = float(top_T_use_F)
                if top_T_alpha is not None and np.isfinite(float(top_T_alpha)):
                    top_drum_pressure_T_relax_alpha = float(top_T_alpha)
                p_seed_top_psia = None
                try:
                    p_seed_top_try = float(P_profile[0])
                    if np.isfinite(p_seed_top_try) and p_seed_top_try > 0.0:
                        p_seed_top_psia = p_seed_top_try
                except Exception:
                    p_seed_top_psia = None
                if p_seed_top_psia is None:
                    try:
                        p_seed_top_try = float(np.asarray(col.P_psia, dtype=float).reshape((N,))[0])
                        if np.isfinite(p_seed_top_try) and p_seed_top_try > 0.0:
                            p_seed_top_psia = p_seed_top_try
                    except Exception:
                        p_seed_top_psia = None
                p_top_res = _compute_top_drum_pressure_psia(
                    top_V=np.asarray(top_V, dtype=float).reshape((Nc,)),
                    top_T_F=float(top_T_use_F),
                    Z_top=float(z_top),
                    top_vapor_volume_ft3=float(top_vap_vol_ft3),
                    thermo_provider=inputs.thermo_provider,
                    y_top=np.asarray(y_topV, dtype=float).reshape((Nc,)),
                    P_seed_psia=p_seed_top_psia,
                    return_details=True,
                    allow_flash_fallback_on_refine_failure=False,
                )
                if isinstance(p_top_res, tuple):
                    P_top_try, z_top_eval, mv_top_eval = p_top_res
                else:
                    P_top_try = p_top_res
                    z_top_eval = None
                    mv_top_eval = None
                if P_top_try is not None and np.isfinite(float(P_top_try)) and float(P_top_try) > 0.0:
                    P_top_drum_psia_raw = float(P_top_try)
                    P_top_drum_psia = float(P_top_try)
                    V_top_drum_vapor_ft3 = float(top_vap_vol_ft3)
                    if top_liq_vol_ft3 is not None:
                        V_top_drum_liquid_ft3 = float(top_liq_vol_ft3)
                    if rho_top_liq is not None:
                        rho_top_drum_liquid_lbmol_ft3 = float(rho_top_liq)
                if z_top_eval is not None and np.isfinite(float(z_top_eval)) and float(z_top_eval) > 0.0:
                    top_drum_pressure_Z = float(z_top_eval)
                if mv_top_eval is not None and np.isfinite(float(mv_top_eval)) and float(mv_top_eval) >= 0.0:
                    top_drum_MV_lbmol = float(mv_top_eval)

    if (
        bool(getattr(inputs, "enforce_top_pressure_ordering", True))
        and P_tray_hyd is not None
        and P_top_drum_psia is not None
        and np.isfinite(float(P_top_drum_psia))
        and float(P_top_drum_psia) > 0.0
        and N > 0
        and top_anchor_psia is not None
    ):
        try:
            p_order_margin = float(getattr(inputs, "top_pressure_ordering_margin_psi", 0.0))
        except Exception:
            p_order_margin = 0.0
        if (not np.isfinite(p_order_margin)) or p_order_margin < 0.0:
            p_order_margin = 0.0
        P_h = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
        if np.isfinite(float(P_h[0])) and float(P_h[0]) > 0.0:
            p0_min = float(P_top_drum_psia) + float(p_order_margin)
            if np.isfinite(p0_min) and float(P_h[0]) < float(p0_min):
                lift = float(p0_min) - float(P_h[0])
                P_h = np.asarray(P_h, dtype=float) + float(lift)
                P_tray_hyd = P_h
                top_pressure_ordering_lift_psia = float(lift)
                if P_tray_hyd_raw is not None:
                    try:
                        P_tray_hyd_raw = np.asarray(P_tray_hyd_raw, dtype=float).reshape((N,)) + float(lift)
                    except Exception:
                        pass

    # Condenser mass split:
    # duty drives how much stage-2 vapor is condensed into top liquid holdup
    # versus carried into top vapor holdup.
    V_condensed_in_lbmolps = float(V_in[0]) if N > 0 else 0.0
    V_to_top_drum_lbmolps = 0.0
    V_condensed_top_lbmolps = 0.0
    dP_stage2_to_top_drum_psia = np.nan
    V_to_top_drum_pressure_gate_scale = np.nan
    V_to_top_drum_blocked_lbmolps = 0.0
    Q_cond_mass_used_BTUph = None
    Q_cond_total_req_BTUph = None
    T_cond_mass_bubble_F = None
    condenser_mass_mode = _normalize_condenser_duty_mode(getattr(inputs, "condenser_duty_mode", None))
    if layout.include_top and top_V is not None and N > 0:
        if "tray_T_f" in u:
            T_tray_mass = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
        elif hasattr(col, "T_f"):
            T_tray_mass = np.asarray(col.T_f, dtype=float).reshape((N,))
        else:
            T_tray_mass = np.full(N, 100.0, dtype=float)
        if P_tray_hyd is not None:
            P_tray_mass = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
        elif hasattr(col, "P_psia"):
            P_tray_mass = np.asarray(col.P_psia, dtype=float).reshape((N,))
        else:
            P_tray_mass = np.full(N, 200.0, dtype=float)
        (
            V_condensed_in_lbmolps,
            V_to_top_drum_lbmolps,
            V_condensed_top_lbmolps,
            Q_cond_mass_used_BTUph,
            Q_cond_total_req_BTUph,
            T_cond_mass_bubble_F,
            condenser_mass_mode,
        ) = _condenser_mass_split_from_duty(
            col=col,
            inputs=inputs,
            tray_T_F=T_tray_mass,
            P_tray_psia=P_tray_mass,
            V_in_lbmolps=V_in,
            y_in=y_in,
            top_V=np.asarray(top_V, dtype=float).reshape((Nc,)),
            epsilon_lbmol=float(layout.epsilon_lbmol),
        )
        if (
            bool(getattr(inputs, "enforce_top_drum_pressure_gate", True))
            and N > 1
            and np.isfinite(float(V_to_top_drum_lbmolps))
            and float(V_to_top_drum_lbmolps) > 0.0
            and P_top_drum_psia is not None
            and np.isfinite(float(P_top_drum_psia))
            and float(P_top_drum_psia) > 0.0
            and np.isfinite(float(P_tray_mass[1]))
            and float(P_tray_mass[1]) > 0.0
        ):
            cond_dp_req = 0.0
            if inputs.condenser_pressure_drop_psi is not None:
                try:
                    cond_dp_try = float(inputs.condenser_pressure_drop_psi)
                    if np.isfinite(cond_dp_try):
                        cond_dp_req = max(cond_dp_try, 0.0)
                except Exception:
                    cond_dp_req = 0.0

            dP_stage2_to_top_drum_psia = (
                float(P_tray_mass[1]) - float(P_top_drum_psia) - float(cond_dp_req)
            )
            gate_scale = _pressure_gate_scale(
                float(dP_stage2_to_top_drum_psia),
                getattr(inputs, "top_drum_pressure_gate_soft_psi", 0.25),
            )
            gate_scale = float(np.clip(gate_scale, 0.0, 1.0))
            v_to_top_old = float(V_to_top_drum_lbmolps)
            V_to_top_drum_lbmolps = float(v_to_top_old) * gate_scale
            V_to_top_drum_pressure_gate_scale = float(gate_scale)
            blocked = max(float(v_to_top_old) - float(V_to_top_drum_lbmolps), 0.0)
            V_to_top_drum_blocked_lbmolps = float(blocked)
            if float(blocked) > float(layout.epsilon_lbmol):
                if str(vflow_model).strip().lower() == "conductance" and N > 1:
                    # In pressure-coupled modes, blocked top slip should feed
                    # back to stage-2 vapor outflow instead of creating artificial
                    # instantaneous condensation at the condenser boundary.
                    v2_old = max(float(V_out[1]), 0.0)
                    v2_new = max(v2_old - float(blocked), 0.0)
                    blocked_eff = max(v2_old - v2_new, 0.0)
                    V_out[1] = float(v2_new)
                    V_in[0] = float(v2_new)
                    V_to_top_drum_blocked_lbmolps = float(blocked_eff)
                else:
                    # No vapor holdup is modeled on the condenser tray, so blocked
                    # slip is routed into instantaneous in-condenser condensation.
                    V_condensed_in_lbmolps = float(V_condensed_in_lbmolps) + float(blocked)

    total_reflux_active = False
    total_reflux_actual_lbmolps = np.nan
    total_reflux_kickstart_lbmolps = np.nan
    total_reflux_reflux_startup_factor = 1.0
    if total_reflux_mode and layout.include_top and N > 1:
        total_reflux_active = True
        total_condensed_liquid = max(
            0.0,
            float(V_condensed_in_lbmolps) + float(V_condensed_top_lbmolps),
        )
        total_reflux_actual_lbmolps = float(total_condensed_liquid)
        total_reflux_kickstart_lbmolps = float(total_reflux_nominal_s)
        if total_condensed_liquid > float(layout.epsilon_lbmol):
            reflux_s = float(total_condensed_liquid)
        else:
            reflux_s = max(float(total_reflux_nominal_s), 0.0)
        if (
            getattr(inputs, "total_reflux_boundary_ramp_duration_sec", None) is not None
            and float(total_reflux_boundary_external_scale) > 0.0
        ):
            closed = float(total_reflux_boundary_closed_fraction)
            reflux_s = (
                float(total_reflux_boundary_external_scale) * float(total_reflux_nominal_s)
                + float(closed) * float(reflux_s)
            )
        if bool(getattr(inputs, "total_reflux_scale_reflux_with_startup_factor", False)):
            total_reflux_reflux_startup_factor = float(
                np.clip(float(total_reflux_startup_factor), 0.0, 1.0)
            )
            reflux_s = float(reflux_s) * float(total_reflux_reflux_startup_factor)
        L_out[0] = float(reflux_s)
        L_in[1] = float(reflux_s)
        x_in[1, :] = x_topL

    V_psv_top_lbmolps = 0.0
    psv_open_flag = 0.0
    psv_setpoint_psia = np.nan
    psv_pv_psia = np.nan
    if P_top_drum_psia is not None and np.isfinite(float(P_top_drum_psia)):
        psv_pv_psia = float(P_top_drum_psia)
    if layout.include_top and bool(getattr(inputs, "enable_top_drum_psv", False)):
        psv_sp_raw = getattr(inputs, "top_drum_psv_setpoint_psia", None)
        psv_gain_raw = getattr(inputs, "top_drum_psv_gain_lbmolps_per_psi", None)
        psv_max_raw = getattr(inputs, "top_drum_psv_max_vent_lbmolps", None)
        if psv_sp_raw is not None:
            try:
                psv_sp = float(psv_sp_raw)
                if np.isfinite(psv_sp) and psv_sp > 0.0:
                    psv_setpoint_psia = psv_sp
            except Exception:
                pass
        psv_gain = 0.0
        if psv_gain_raw is not None:
            try:
                psv_gain_try = float(psv_gain_raw)
                if np.isfinite(psv_gain_try) and psv_gain_try > 0.0:
                    psv_gain = psv_gain_try
            except Exception:
                psv_gain = 0.0
        psv_max_vent = None
        if psv_max_raw is not None:
            try:
                psv_max_try = float(psv_max_raw)
                if np.isfinite(psv_max_try) and psv_max_try >= 0.0:
                    psv_max_vent = psv_max_try
            except Exception:
                psv_max_vent = None
        if np.isfinite(psv_setpoint_psia) and np.isfinite(psv_pv_psia) and psv_gain > 0.0:
            p_excess = max(float(psv_pv_psia) - float(psv_setpoint_psia), 0.0)
            vent = float(psv_gain) * float(p_excess)
            if psv_max_vent is not None:
                vent = min(float(vent), float(psv_max_vent))
            V_psv_top_lbmolps = max(float(vent), 0.0)
            if V_psv_top_lbmolps > float(layout.epsilon_lbmol):
                psv_open_flag = 1.0

    d_tray_L = np.zeros((N, Nc), dtype=float)
    d_tray_V = np.zeros((N, Nc), dtype=float)
    d_tray_L_feed = np.zeros((N, Nc), dtype=float)

    for i in range(N):
        for k in range(Nc):
            feedL = Fk_L[k] if (feed_stage0 == i) else 0.0
            feedV = Fk_V[k] if (feed_stage0 == i) else 0.0

            d_tray_L[i, k] = (
                L_in[i] * x_in[i, k]
                + feedL
                - L_out[i] * x_tray[i, k]
            )
            d_tray_L_feed[i, k] = feedL

            d_tray_V[i, k] = (
                V_in[i] * y_in[i, k]
                + feedV
                - V_out[i] * y_tray[i, k]
            )

    # Reboiler phase change at the bottom end.
    # When an explicit bottom sump is present, boilup is drawn from the sump
    # and returned as vapor to the bottom tray. Otherwise preserve the legacy
    # tray-fed reboiler behavior.
    if N > 0 and (not reboiler_no_holdup):
        if not reboiler_feed_from_sump:
            d_tray_L[-1, :] -= boilup_s * x_rebL
            d_tray_V[-1, :] += boilup_s * x_rebL
            d_tray_V[-1, :] -= boilup_s * y_rebV
    if reboiler_no_holdup and N > 0:
        d_tray_L[-1, :] = 0.0
        d_tray_V[-1, :] = 0.0

    d_top_L = d_top_V = None
    x_cond_diag = None
    top_L_cond_in_comp = np.full(Nc, np.nan, dtype=float)
    top_L_reflux_out_comp = np.full(Nc, np.nan, dtype=float)
    top_L_distillate_out_comp = np.full(Nc, np.nan, dtype=float)
    top_L_net_comp = np.full(Nc, np.nan, dtype=float)
    top_L_cond_in_total = np.nan
    top_L_reflux_out_total = np.nan
    top_L_distillate_out_total = np.nan
    top_L_net_total = np.nan
    top_L_cond_x_minus_drum_x = np.full(Nc, np.nan, dtype=float)
    if layout.include_top:
        if top_L is None or top_V is None:
            raise ColumnRHSError("layout.include_top=True requires top_L and top_V states.")

        d_top_L = np.zeros(Nc, dtype=float)
        d_top_V = np.zeros(Nc, dtype=float)

        # Stage 1 condenser (index 0) and reflux drum are distinct states.
        # Incoming vapor is split by condenser-duty condensation capacity.
        # Condensed liquid first enters condenser liquid holdup, then drains to the drum.
        # Uncondensed vapor is retained in the top vapor holdup.
        feedL0 = Fk_L if (feed_stage0 == 0) else 0.0
        feedV0 = Fk_V if (feed_stage0 == 0) else 0.0
        stage1_dry_condenser = bool(
            float(ML_tot_stage[0]) <= float(layout.epsilon_lbmol)
        )
        x_condL = _safe_comp_from_holdup(tray_L[0, :], fallback=y_in[0, :], eps=layout.epsilon_lbmol)
        x_cond_diag = np.asarray(x_condL, dtype=float).reshape((Nc,))
        L_cond_to_top_lbmolps = max(
            0.0,
            float(V_condensed_in_lbmolps) + float(V_condensed_top_lbmolps),
        )
        if feed_stage0 == 0:
            L_cond_to_top_lbmolps += float(np.sum(feedL0 + feedV0))
        if stage1_dry_condenser and L_cond_to_top_lbmolps > float(layout.epsilon_lbmol):
            cond_to_top_comp = (
                float(V_condensed_in_lbmolps) * y_in[0, :]
                + float(V_condensed_top_lbmolps) * y_topV
            )
            if feed_stage0 == 0:
                cond_to_top_comp = cond_to_top_comp + feedL0 + feedV0
            x_condL = _safe_comp_from_holdup(
                cond_to_top_comp,
                fallback=y_in[0, :],
                eps=layout.epsilon_lbmol,
            )
            x_cond_diag = np.asarray(x_condL, dtype=float).reshape((Nc,))

        top_L_cond_in_comp = float(L_cond_to_top_lbmolps) * x_condL
        d_top_L += top_L_cond_in_comp
        d_top_V += float(V_to_top_drum_lbmolps) * y_in[0, :]
        d_top_V -= float(V_condensed_top_lbmolps) * y_topV

        # Reflux withdrawal (liquid to stage 2) and distillate draw come from the drum.
        top_L_reflux_out_comp = float(L_out[0]) * x_topL
        d_top_L -= top_L_reflux_out_comp
        if D.has_component_breakdown:
            top_L_distillate_out_comp = np.asarray(D.comp_L, dtype=float).reshape((Nc,))
            d_top_L -= top_L_distillate_out_comp
            d_top_V -= D.comp_V
        else:
            top_L_distillate_out_comp = float(D.total_L) * x_topL
            d_top_L -= top_L_distillate_out_comp
            d_top_V -= D.total_V * y_topV
        if V_psv_top_lbmolps > 0.0:
            d_top_V -= float(V_psv_top_lbmolps) * y_topV
        top_L_net_comp = np.asarray(d_top_L, dtype=float).reshape((Nc,)).copy()
        top_L_cond_in_total = float(np.sum(top_L_cond_in_comp))
        top_L_reflux_out_total = float(np.sum(top_L_reflux_out_comp))
        top_L_distillate_out_total = float(np.sum(top_L_distillate_out_comp))
        top_L_net_total = float(np.sum(top_L_net_comp))
        top_L_cond_x_minus_drum_x = np.asarray(x_condL, dtype=float).reshape((Nc,)) - np.asarray(
            x_topL, dtype=float
        ).reshape((Nc,))

        # Condenser tray receives condensed liquid and drains to the drum.
        d_tray_L[0, :] = 0.0
        d_tray_L[0, :] += float(V_condensed_in_lbmolps) * y_in[0, :]
        d_tray_L[0, :] += float(V_condensed_top_lbmolps) * y_topV
        d_tray_L[0, :] -= float(L_cond_to_top_lbmolps) * x_condL
        if feed_stage0 == 0:
            d_tray_L[0, :] += feedL0 + feedV0

        # Condenser tray has no vapor holdup; incoming vapor transfers to condensed/uncondensed streams.
        d_tray_V[0, :] -= V_in[0] * y_in[0, :]
        if feed_stage0 == 0:
            d_tray_V[0, :] -= feedV0
    else:
        # Stage 1 condenser (index 0): total condenser behavior.
        # Convert all incoming vapor to liquid immediately (no vapor out of the condenser).
        # This prevents vapor holdup from artificially accumulating at the condenser.
        d_tray_L[0, :] += V_in[0] * y_in[0, :]
        d_tray_V[0, :] -= V_in[0] * y_in[0, :]

        # Distillate draw is removed from condenser liquid holdup (and vapor holdup if specified).
        if D.has_component_breakdown:
            d_tray_L[0, :] -= D.comp_L
            d_tray_V[0, :] -= D.comp_V
        else:
            d_tray_L[0, :] -= D.total_L * x_tray[0, :]
            d_tray_V[0, :] -= D.total_V * y_tray[0, :]

    d_bottom_L = d_bottom_V = None
    if layout.include_bottom:
        if bottom_L is None or bottom_V is None:
            raise ColumnRHSError("layout.include_bottom=True requires bottom_L and bottom_V states.")

        d_bottom_L = np.zeros(Nc, dtype=float)
        d_bottom_V = np.zeros(Nc, dtype=float)

        L_to_bottom = L_out[-1]
        x_bottomtray = x_tray[-1, :]
        d_bottom_L += L_to_bottom * x_bottomtray

        if B.has_component_breakdown:
            d_bottom_L -= B.comp_L
            d_bottom_V -= B.comp_V
        else:
            d_bottom_L -= B.total_L * x_botL
            d_bottom_V -= B.total_V * y_botV

        # With an explicit sump-fed reboiler, boilup is withdrawn from the sump
        # liquid holdup and returned to the bottom tray as vapor.
        if reboiler_feed_from_sump:
            d_bottom_L -= boilup_s * x_rebL

    if algebraic_vapor_state:
        d_tray_L += d_tray_V
        d_tray_V[:, :] = 0.0

    # Vapor holdup relaxation: enforce ideal-gas holdup implied by computed pressure + geometry.
    tau_v = inputs.vapor_holdup_relaxation_sec
    if (tau_v is not None) and (P_tray_hyd is not None) and layout.include_vapor:
        try:
            tau_v = float(tau_v)
        except Exception:
            tau_v = None
        if tau_v is not None and np.isfinite(tau_v) and tau_v > 0.0:
            T_tray_for_mv = (
                np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
                if "tray_T_f" in u
                else np.asarray(getattr(col, "T_f", np.full(N, 100.0, dtype=float)), dtype=float).reshape((N,))
            )
            Z_mv = (
                np.asarray(inputs.Zfac_prev, dtype=float).reshape((N,))
                if inputs.Zfac_prev is not None
                else np.ones(N, dtype=float)
            )
            Z_mv = np.where(~np.isfinite(Z_mv) | (Z_mv <= 0.0), 1.0, Z_mv)

            V_ft3 = (
                np.asarray(inputs.volume_model.vapor_volume_ft3_per_stage, dtype=float).reshape((N,))
                if inputs.volume_model.vapor_volume_ft3_per_stage is not None
                else np.full(N, float(inputs.volume_model.default_vapor_volume_ft3), dtype=float)
            )
            V_ft3 = np.where(~np.isfinite(V_ft3) | (V_ft3 <= 0.0), 1.0, V_ft3)

            R = 10.7316
            T_R = T_tray_for_mv + 459.67
            T_R = np.where(~np.isfinite(T_R) | (T_R <= 0.0), 520.0, T_R)
            P_use = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
            P_use = np.where(~np.isfinite(P_use) | (P_use <= 0.0), 14.7, P_use)

            MV_target = P_use * V_ft3 / (Z_mv * R * T_R)
            MV_tot = np.sum(tray_V, axis=1).reshape((N,))
            dMV = (MV_target - MV_tot) / tau_v

            # Keep vapor-holdup relaxation mass-conserving across active trays.
            active = np.ones(N, dtype=bool)
            active[0] = False  # condenser has no vapor holdup
            if reboiler_no_holdup:
                active[-1] = False
            n_active = int(np.sum(active))
            if n_active > 0:
                dmv_sum = float(np.sum(dMV[active]))
                if np.isfinite(dmv_sum) and abs(dmv_sum) > 0.0:
                    dMV[active] -= dmv_sum / float(n_active)

            for i in range(N):
                if i == 0:
                    continue  # condenser has no vapor holdup
                if reboiler_no_holdup and i == (N - 1):
                    continue
                d_tray_V[i, :] += y_tray[i, :] * float(dMV[i])
        else:
            tau_v = None

    # When stage-1 condenser liquid holdup is zero (exchanger representation),
    # report condenser liquid composition from condensed stream diagnostics.
    if layout.include_top and x_cond_diag is not None and N > 0:
        if ML_tot_stage[0] <= float(layout.epsilon_lbmol):
            x_tray[0, :] = np.asarray(x_cond_diag, dtype=float).reshape((Nc,))

    debug_freeze_vapor_active = bool(
        getattr(inputs, "debug_freeze_tray_vapor_derivatives", False)
    ) and bool(layout.include_vapor)
    debug_max_orig_dmVdt = 0.0
    debug_max_orig_dmVdt_rel_per_s = 0.0
    debug_worst_v_stage = -1
    debug_worst_v_comp = -1
    debug_worst_v_rel_stage = -1
    debug_worst_v_rel_comp = -1
    debug_total_v_cancellation_lbmolps = 0.0
    debug_net_orig_dmVdt_lbmolps = 0.0
    if debug_freeze_vapor_active:
        orig_d_tray_V = np.asarray(d_tray_V, dtype=float).copy()
        abs_orig = np.where(np.isfinite(orig_d_tray_V), np.abs(orig_d_tray_V), 0.0)
        if abs_orig.size:
            worst_abs_idx = np.unravel_index(int(np.argmax(abs_orig)), abs_orig.shape)
            debug_max_orig_dmVdt = float(abs_orig[worst_abs_idx])
            debug_worst_v_stage = int(worst_abs_idx[0] + 1)
            debug_worst_v_comp = int(worst_abs_idx[1] + 1)
        if tray_V is not None:
            denom = np.maximum(
                np.abs(np.asarray(tray_V, dtype=float).reshape((N, Nc))),
                float(layout.epsilon_lbmol),
            )
            rel_orig = abs_orig / denom
            if rel_orig.size:
                worst_rel_idx = np.unravel_index(int(np.argmax(rel_orig)), rel_orig.shape)
                debug_max_orig_dmVdt_rel_per_s = float(rel_orig[worst_rel_idx])
                debug_worst_v_rel_stage = int(worst_rel_idx[0] + 1)
                debug_worst_v_rel_comp = int(worst_rel_idx[1] + 1)
        debug_total_v_cancellation_lbmolps = float(np.sum(abs_orig))
        debug_net_orig_dmVdt_lbmolps = float(np.sum(orig_d_tray_V))
        d_tray_V[:, :] = 0.0

    dydt = np.zeros(layout.n_states(), dtype=float)
    sl = _layout_slices(layout)

    if layout.include_top:
        dydt[sl["top_L"]] = d_top_L
        dydt[sl["top_V"]] = d_top_V

    dydt[sl["tray_L"]] = d_tray_L.reshape(-1)
    if layout.include_vapor:
        dydt[sl["tray_V"]] = d_tray_V.reshape(-1)

    if layout.include_bottom:
        dydt[sl["bottom_L"]] = d_bottom_L
        dydt[sl["bottom_V"]] = d_bottom_V

    diag: Dict[str, np.ndarray] = {}
    if p_hyd_details_pending:
        for _k, _v in p_hyd_details_pending.items():
            diag[_k] = _v
    if vflow_diag is not None:
        for k, v in vflow_diag.items():
            diag[k] = v
    if "vflow_homotopy_active" not in diag:
        diag["vflow_homotopy_active"] = np.array(
            [1.0 if vapor_homotopy_active else 0.0], dtype=float
        )
    if "vflow_homotopy_beta" not in diag:
        diag["vflow_homotopy_beta"] = np.array([float(vapor_homotopy_beta_used)], dtype=float)

    diag["debug_freeze_tray_vapor_derivatives_active"] = np.array(
        [1.0 if debug_freeze_vapor_active else 0.0], dtype=float
    )
    diag["debug_max_orig_dmVdt"] = np.array([float(debug_max_orig_dmVdt)], dtype=float)
    diag["debug_max_orig_dmVdt_rel_per_s"] = np.array(
        [float(debug_max_orig_dmVdt_rel_per_s)], dtype=float
    )
    diag["debug_worst_v_stage"] = np.array([float(debug_worst_v_stage)], dtype=float)
    diag["debug_worst_v_comp"] = np.array([float(debug_worst_v_comp)], dtype=float)
    diag["debug_worst_v_rel_stage"] = np.array([float(debug_worst_v_rel_stage)], dtype=float)
    diag["debug_worst_v_rel_comp"] = np.array([float(debug_worst_v_rel_comp)], dtype=float)
    diag["debug_total_v_cancellation_lbmolps"] = np.array(
        [float(debug_total_v_cancellation_lbmolps)], dtype=float
    )
    diag["debug_net_orig_dmVdt_lbmolps"] = np.array(
        [float(debug_net_orig_dmVdt_lbmolps)], dtype=float
    )
    diag["debug_reflux_overridden"] = np.array(
        [1.0 if debug_reflux_overridden else 0.0], dtype=float
    )
    diag["debug_reflux_target_stage"] = np.array([float(debug_reflux_target_stage)], dtype=float)
    diag["debug_reflux_orig_comp2"] = np.array([float(debug_reflux_orig_comp2)], dtype=float)
    diag["debug_reflux_target_comp2"] = np.array([float(debug_reflux_target_comp2)], dtype=float)
    diag["debug_reflux_comp2_delta"] = np.array([float(debug_reflux_comp2_delta)], dtype=float)
    diag["debug_reflux_target_delta_max"] = np.array(
        [float(debug_reflux_target_delta_max)], dtype=float
    )
    diag["top_L_cond_in_lbmolph_comp"] = np.asarray(top_L_cond_in_comp, dtype=float).reshape((Nc,)) * 3600.0
    diag["top_L_reflux_out_lbmolph_comp"] = (
        np.asarray(top_L_reflux_out_comp, dtype=float).reshape((Nc,)) * 3600.0
    )
    diag["top_L_distillate_out_lbmolph_comp"] = (
        np.asarray(top_L_distillate_out_comp, dtype=float).reshape((Nc,)) * 3600.0
    )
    diag["top_L_net_lbmolph_comp"] = np.asarray(top_L_net_comp, dtype=float).reshape((Nc,)) * 3600.0
    diag["top_L_cond_x_minus_drum_x"] = np.asarray(top_L_cond_x_minus_drum_x, dtype=float).reshape((Nc,))
    diag["top_L_cond_in_lbmolph"] = np.array([float(top_L_cond_in_total) * 3600.0], dtype=float)
    diag["top_L_reflux_out_lbmolph"] = np.array([float(top_L_reflux_out_total) * 3600.0], dtype=float)
    diag["top_L_distillate_out_lbmolph"] = np.array(
        [float(top_L_distillate_out_total) * 3600.0], dtype=float
    )
    diag["top_L_net_lbmolph"] = np.array([float(top_L_net_total) * 3600.0], dtype=float)
    try:
        top_L_abs = np.abs(np.asarray(top_L_net_comp, dtype=float).reshape((Nc,)))
        if top_L_abs.size > 0 and np.any(np.isfinite(top_L_abs)):
            top_L_worst_idx = int(np.nanargmax(top_L_abs))
            diag["top_L_net_worst_component_1based"] = np.array([float(top_L_worst_idx + 1)], dtype=float)
            diag["top_L_net_worst_lbmolph"] = np.array(
                [float(top_L_net_comp[top_L_worst_idx]) * 3600.0],
                dtype=float,
            )
            diag["top_L_net_worst_abs_lbmolph"] = np.array(
                [float(abs(top_L_net_comp[top_L_worst_idx])) * 3600.0],
                dtype=float,
            )
    except Exception:
        pass
    diag["total_reflux_mode_active"] = np.array([1.0 if total_reflux_active else 0.0], dtype=float)
    diag["total_reflux_actual_lbmolps"] = np.array([float(total_reflux_actual_lbmolps)], dtype=float)
    diag["total_reflux_kickstart_lbmolps"] = np.array([float(total_reflux_kickstart_lbmolps)], dtype=float)
    diag["total_reflux_used_lbmolps"] = np.array([float(reflux_s)], dtype=float)
    diag["total_reflux_feed_suppressed_lbmolps"] = np.array([float(Ft_feed)], dtype=float)
    diag["total_reflux_startup_factor"] = np.array([float(total_reflux_startup_factor)], dtype=float)
    diag["total_reflux_reflux_startup_factor"] = np.array(
        [float(total_reflux_reflux_startup_factor)], dtype=float
    )
    diag["total_reflux_boundary_external_scale"] = np.array(
        [float(total_reflux_boundary_external_scale)], dtype=float
    )
    diag["total_reflux_boundary_closed_fraction"] = np.array(
        [float(total_reflux_boundary_closed_fraction)], dtype=float
    )

    ML_key = "ML_tot_tray" if "ML_tot_tray" in u else ("ML_tot" if "ML_tot" in u else None)
    MV_key = "MV_tot_tray" if "MV_tot_tray" in u else ("MV_tot" if "MV_tot" in u else None)
    if ML_key is None:
        raise ColumnRHSError("layout.unpack(y) must provide tray liquid total holdup (ML_tot_tray or ML_tot).")

    diag["ML_tot_tray"] = np.asarray(u[ML_key], dtype=float).copy()
    diag["MV_tot_tray"] = (
        np.asarray(u[MV_key], dtype=float).copy()
        if MV_key is not None
        else np.zeros(N, dtype=float)
    )
    diag["x_tray"] = x_tray.copy()
    diag["y_tray"] = y_tray.copy()
    diag["reboiler_mode_duty_active"] = np.array([1.0 if use_duty else 0.0], dtype=float)
    diag["boilup_realized_lbmolph"] = np.array([float(boilup_s) * 3600.0], dtype=float)
    diag["reboiler_temperature_F"] = np.array([float(T_reb)], dtype=float)
    if boilup_from_duty_lbmolph is not None and np.isfinite(float(boilup_from_duty_lbmolph)):
        diag["boilup_from_duty_lbmolph"] = np.array([float(boilup_from_duty_lbmolph)], dtype=float)
    if np.isfinite(float(reboiler_latent_heat_btu_per_lbmol)):
        diag["reboiler_latent_heat_BTU_per_lbmol"] = np.array(
            [float(reboiler_latent_heat_btu_per_lbmol)],
            dtype=float,
        )
    try:
        x_safe = np.asarray(x_tray, dtype=float).reshape((N, Nc))
        y_safe = np.asarray(y_tray, dtype=float).reshape((N, Nc))
        K_state = np.full((N, Nc), np.nan, dtype=float)
        valid = np.isfinite(x_safe) & np.isfinite(y_safe) & (x_safe > 1.0e-12)
        if np.any(valid):
            K_state[valid] = y_safe[valid] / x_safe[valid]
        # Stage 1 under total-condenser handling has no vapor holdup state.
        if N > 0:
            mv0 = float(np.sum(np.asarray(tray_V[0, :], dtype=float)))
            if (not np.isfinite(mv0)) or (mv0 <= float(layout.epsilon_lbmol)):
                K_state[0, :] = np.nan
        diag["K_state_y_over_x_tray"] = K_state
    except Exception:
        pass

    condenser_duty_cache: Optional[Tuple[float, Optional[float], Optional[float], Optional[float], str]] = None
    condenser_duty_packet_out: Optional[CondenserDutyPacket] = None
    if (
        Q_cond_mass_used_BTUph is not None
        and np.isfinite(float(Q_cond_mass_used_BTUph))
        and (
            (Q_cond_total_req_BTUph is not None and np.isfinite(float(Q_cond_total_req_BTUph)))
            or (T_cond_mass_bubble_F is not None and np.isfinite(float(T_cond_mass_bubble_F)))
        )
        and N > 0
    ):
        if "tray_T_f" in u:
            T_tray_cond_seed = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
        elif hasattr(col, "T_f"):
            T_tray_cond_seed = np.asarray(col.T_f, dtype=float).reshape((N,))
        else:
            T_tray_cond_seed = np.full(N, 100.0, dtype=float)
        if P_tray_hyd is not None:
            try:
                P_tray_cond_seed = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
            except Exception:
                P_tray_cond_seed = np.asarray(
                    diag.get("P_psia_diag", np.full(N, 200.0, dtype=float)),
                    dtype=float,
                ).reshape((N,))
        elif hasattr(col, "P_psia"):
            P_tray_cond_seed = np.asarray(col.P_psia, dtype=float).reshape((N,))
        else:
            P_tray_cond_seed = np.asarray(
                diag.get("P_psia_diag", np.full(N, 200.0, dtype=float)),
                dtype=float,
            ).reshape((N,))
        src_i = 1 if N > 1 else 0
        condenser_duty_cache = (
            float(Q_cond_mass_used_BTUph),
            (
                float(Q_cond_total_req_BTUph)
                if Q_cond_total_req_BTUph is not None and np.isfinite(float(Q_cond_total_req_BTUph))
                else None
            ),
            (
                float(T_cond_mass_bubble_F)
                if T_cond_mass_bubble_F is not None and np.isfinite(float(T_cond_mass_bubble_F))
                else None
            ),
            None,
            str(condenser_mass_mode),
        )
        condenser_duty_packet_out = CondenserDutyPacket(
            q_calc_BTUph=(
                float(Q_cond_total_req_BTUph)
                if Q_cond_total_req_BTUph is not None and np.isfinite(float(Q_cond_total_req_BTUph))
                else None
            ),
            T_bubble_F=(
                float(T_cond_mass_bubble_F)
                if T_cond_mass_bubble_F is not None and np.isfinite(float(T_cond_mass_bubble_F))
                else None
            ),
            mode=str(condenser_mass_mode),
            V_vapor_in_lbmolps=float(V_in[0]),
            T_vapor_in_F=float(T_tray_cond_seed[src_i]),
            P_vapor_in_psia=float(P_tray_cond_seed[src_i]),
            P_condenser_psia=float(P_tray_cond_seed[0]),
            y_vapor_in=np.asarray(y_in[0, :], dtype=float).reshape((Nc,)).copy(),
            hL_cond_BTU_lbmol=None,
        )

    def _resolve_condenser_duty_cached(
        *,
        tray_T_F: np.ndarray,
        P_tray_psia: np.ndarray,
    ) -> Tuple[float, Optional[float], Optional[float], Optional[float], str]:
        nonlocal condenser_duty_cache, condenser_duty_packet_out
        tray_T_arr = np.asarray(tray_T_F, dtype=float).reshape((N,))
        P_tray_arr = np.asarray(P_tray_psia, dtype=float).reshape((N,))
        src_i = 1 if N > 1 else 0
        cache_packet_hit = None
        cache_recomputed = False
        if condenser_duty_cache is not None:
            cache_packet_hit = _condenser_duty_packet_if_compatible(
                condenser_duty_packet_out,
                mode=str(condenser_duty_cache[4]),
                V_vapor_in_lbmolps=float(V_in[0]),
                T_vapor_in_F=float(tray_T_arr[src_i]),
                P_vapor_in_psia=float(P_tray_arr[src_i]),
                P_condenser_psia=float(P_tray_arr[0]),
                y_vapor_in=np.asarray(y_in[0, :], dtype=float).reshape((Nc,)),
                max_abs_dT_F=float(getattr(inputs, "condenser_duty_reuse_dT_F", 0.0) or 0.0),
                max_abs_dP_psia=float(getattr(inputs, "condenser_duty_reuse_dP_psia", 0.0) or 0.0),
                max_abs_dx=float(getattr(inputs, "condenser_duty_reuse_dx", 0.0) or 0.0),
                max_rel_dV=float(getattr(inputs, "condenser_duty_reuse_dV_rel", 0.0) or 0.0),
            )
            if cache_packet_hit is None:
                condenser_duty_cache = None
        if condenser_duty_cache is None:
            cache_recomputed = True
            condenser_duty_cache = _resolve_condenser_duty_btu_per_h(
                col=col,
                inputs=inputs,
                N=N,
                tray_T_F=tray_T_arr,
                P_tray_psia=P_tray_arr,
                V_in_lbmolps=V_in,
                y_in=y_in,
                epsilon_lbmol=float(layout.epsilon_lbmol),
            )
        if condenser_duty_cache[3] is None and condenser_duty_cache[2] is not None:
            try:
                hL_cond = _condenser_liquid_enthalpy_BTU_lbmol(
                    thermo_provider=inputs.thermo_provider,
                    T_bubble_F=float(condenser_duty_cache[2]),
                    P_condenser_psia=float(P_tray_arr[0]),
                    x_cond=np.asarray(y_in[0, :], dtype=float).reshape((Nc,)),
                    packet=condenser_duty_packet_out,
                )
                if hL_cond is not None and np.isfinite(float(hL_cond)):
                    condenser_duty_cache = (
                        float(condenser_duty_cache[0]),
                        condenser_duty_cache[1],
                        condenser_duty_cache[2],
                        float(hL_cond),
                        str(condenser_duty_cache[4]),
                    )
            except Exception:
                pass
        packet_V_vapor_in_lbmolps = float(V_in[0])
        packet_T_vapor_in_F = float(tray_T_arr[src_i])
        packet_P_vapor_in_psia = float(P_tray_arr[src_i])
        packet_P_condenser_psia = float(P_tray_arr[0])
        packet_y_vapor_in = np.asarray(y_in[0, :], dtype=float).reshape((Nc,)).copy()
        if (not cache_recomputed) and cache_packet_hit is not None:
            packet_V_vapor_in_lbmolps = float(cache_packet_hit.V_vapor_in_lbmolps)
            packet_T_vapor_in_F = float(cache_packet_hit.T_vapor_in_F)
            packet_P_vapor_in_psia = float(cache_packet_hit.P_vapor_in_psia)
            packet_P_condenser_psia = float(cache_packet_hit.P_condenser_psia)
            packet_y_vapor_in = np.asarray(cache_packet_hit.y_vapor_in, dtype=float).reshape((Nc,)).copy()
        condenser_duty_packet_out = CondenserDutyPacket(
            q_calc_BTUph=(
                float(condenser_duty_cache[1])
                if condenser_duty_cache[1] is not None and np.isfinite(float(condenser_duty_cache[1]))
                else None
            ),
            T_bubble_F=(
                float(condenser_duty_cache[2])
                if condenser_duty_cache[2] is not None and np.isfinite(float(condenser_duty_cache[2]))
                else None
            ),
            mode=str(condenser_duty_cache[4]),
            V_vapor_in_lbmolps=packet_V_vapor_in_lbmolps,
            T_vapor_in_F=packet_T_vapor_in_F,
            P_vapor_in_psia=packet_P_vapor_in_psia,
            P_condenser_psia=packet_P_condenser_psia,
            y_vapor_in=packet_y_vapor_in,
            hL_cond_BTU_lbmol=(
                float(condenser_duty_cache[3])
                if condenser_duty_cache[3] is not None and np.isfinite(float(condenser_duty_cache[3]))
                else None
            ),
        )
        return condenser_duty_cache
    if P_tray_hyd is not None:
        try:
            diag["P_psia_hyd"] = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
        except Exception:
            pass
    if P_tray_hyd_raw is not None:
        try:
            diag["P_psia_hyd_raw"] = np.asarray(P_tray_hyd_raw, dtype=float).reshape((N,))
        except Exception:
            pass
    if P_tray_hyd_relax_alpha is not None and np.isfinite(float(P_tray_hyd_relax_alpha)):
        diag["P_psia_hyd_relax_alpha"] = np.array([float(P_tray_hyd_relax_alpha)], dtype=float)
    if np.isfinite(float(top_pressure_ordering_lift_psia)) and float(top_pressure_ordering_lift_psia) > 0.0:
        diag["P_top_ordering_lift_psia"] = np.array([float(top_pressure_ordering_lift_psia)], dtype=float)
    if P_top_drum_psia is not None and np.isfinite(float(P_top_drum_psia)):
        diag["P_top_drum_psia"] = np.array([float(P_top_drum_psia)], dtype=float)
    if np.isfinite(float(P_top_drum_psia_raw)) and float(P_top_drum_psia_raw) > 0.0:
        diag["P_top_drum_psia_raw"] = np.array([float(P_top_drum_psia_raw)], dtype=float)
    if debug_top_drum_pressure_clamp_active:
        diag["debug_top_drum_pressure_clamp_active"] = np.array([1.0], dtype=float)
        diag["debug_top_drum_pressure_clamp_psia"] = np.array(
            [float(debug_top_drum_pressure_clamp_psia)],
            dtype=float,
        )
        if np.isfinite(float(debug_top_drum_pressure_clamp_raw_psia)):
            diag["debug_top_drum_pressure_clamp_raw_psia"] = np.array(
                [float(debug_top_drum_pressure_clamp_raw_psia)],
                dtype=float,
            )
    if np.isfinite(float(top_drum_pressure_T_raw_F)):
        diag["T_top_drum_pressure_raw_F"] = np.array([float(top_drum_pressure_T_raw_F)], dtype=float)
    if np.isfinite(float(top_drum_pressure_T_used_F)):
        diag["T_top_drum_pressure_used_F"] = np.array([float(top_drum_pressure_T_used_F)], dtype=float)
    if np.isfinite(float(top_drum_pressure_T_relax_alpha)):
        diag["T_top_drum_pressure_relax_alpha"] = np.array(
            [float(top_drum_pressure_T_relax_alpha)],
            dtype=float,
        )
    if np.isfinite(float(top_drum_pressure_Z)) and float(top_drum_pressure_Z) > 0.0:
        diag["Z_top_drum_vapor"] = np.array([float(top_drum_pressure_Z)], dtype=float)
    if np.isfinite(float(top_drum_MV_lbmol)) and float(top_drum_MV_lbmol) >= 0.0:
        diag["MV_top_drum_lbmol"] = np.array([float(top_drum_MV_lbmol)], dtype=float)
    if V_top_drum_vapor_ft3 is not None and np.isfinite(float(V_top_drum_vapor_ft3)):
        diag["V_top_drum_vapor_ft3"] = np.array([float(V_top_drum_vapor_ft3)], dtype=float)
    if V_top_drum_liquid_ft3 is not None and np.isfinite(float(V_top_drum_liquid_ft3)):
        diag["V_top_drum_liquid_ft3"] = np.array([float(V_top_drum_liquid_ft3)], dtype=float)
    if rho_top_drum_liquid_lbmol_ft3 is not None and np.isfinite(float(rho_top_drum_liquid_lbmol_ft3)):
        diag["rho_top_drum_liq_lbmol_ft3"] = np.array([float(rho_top_drum_liquid_lbmol_ft3)], dtype=float)
    try:
        mass_resid = np.sum(d_tray_L + d_tray_V, axis=1)
        diag["mass_balance_resid_lbmolps_tray"] = np.asarray(mass_resid, dtype=float).reshape((N,))
    except Exception:
        pass
    try:
        diag["L_out_lbmolph"] = np.asarray(L_out, dtype=float).reshape((N,)) * 3600.0
    except Exception:
        pass
    try:
        diag["V_out_lbmolph"] = np.asarray(V_out, dtype=float).reshape((N,)) * 3600.0
    except Exception:
        pass
    diag["V_condensed_in_lbmolph"] = np.array([float(V_condensed_in_lbmolps) * 3600.0], dtype=float)
    diag["V_to_top_drum_lbmolph"] = np.array([float(V_to_top_drum_lbmolps) * 3600.0], dtype=float)
    diag["V_condensed_top_lbmolph"] = np.array([float(V_condensed_top_lbmolps) * 3600.0], dtype=float)
    diag["dP_stage2_to_top_drum_psia"] = np.array([float(dP_stage2_to_top_drum_psia)], dtype=float)
    diag["V_to_top_drum_pressure_gate_scale"] = np.array([float(V_to_top_drum_pressure_gate_scale)], dtype=float)
    diag["V_to_top_drum_blocked_lbmolph"] = np.array([float(V_to_top_drum_blocked_lbmolps) * 3600.0], dtype=float)
    diag["V_psv_top_lbmolph"] = np.array([float(V_psv_top_lbmolps) * 3600.0], dtype=float)
    diag["PSV_open_flag"] = np.array([float(psv_open_flag)], dtype=float)
    diag["PSV_setpoint_psia"] = np.array(
        [float(psv_setpoint_psia) if np.isfinite(psv_setpoint_psia) else np.nan],
        dtype=float,
    )
    diag["PSV_pv_psia"] = np.array(
        [float(psv_pv_psia) if np.isfinite(psv_pv_psia) else np.nan],
        dtype=float,
    )
    if Q_cond_mass_used_BTUph is not None and np.isfinite(float(Q_cond_mass_used_BTUph)):
        diag["Q_cond_mass_used_BTUph"] = np.array([float(Q_cond_mass_used_BTUph)], dtype=float)
    if Q_cond_total_req_BTUph is not None and np.isfinite(float(Q_cond_total_req_BTUph)):
        diag["Q_cond_mass_total_req_BTUph"] = np.array([float(Q_cond_total_req_BTUph)], dtype=float)
    diag["Q_cond_mass_mode_total_condense"] = np.array(
        [1.0 if str(condenser_mass_mode) == "total-condense" else 0.0], dtype=float
    )
    if condenser_duty_packet_out is not None:
        if (
            condenser_duty_packet_out.q_calc_BTUph is not None
            and np.isfinite(float(condenser_duty_packet_out.q_calc_BTUph))
        ):
            diag["condenser_duty_cache_q_calc_BTUph"] = np.array(
                [float(condenser_duty_packet_out.q_calc_BTUph)], dtype=float
            )
        if (
            condenser_duty_packet_out.T_bubble_F is not None
            and np.isfinite(float(condenser_duty_packet_out.T_bubble_F))
        ):
            diag["condenser_duty_cache_T_bubble_F"] = np.array(
                [float(condenser_duty_packet_out.T_bubble_F)], dtype=float
            )
        diag["condenser_duty_cache_mode_total_condense"] = np.array(
            [1.0 if str(condenser_duty_packet_out.mode).strip().lower() == "total-condense" else 0.0],
            dtype=float,
        )
        diag["condenser_duty_cache_V_vapor_in_lbmolps"] = np.array(
            [float(condenser_duty_packet_out.V_vapor_in_lbmolps)], dtype=float
        )
        diag["condenser_duty_cache_T_vapor_in_F"] = np.array(
            [float(condenser_duty_packet_out.T_vapor_in_F)], dtype=float
        )
        diag["condenser_duty_cache_P_vapor_in_psia"] = np.array(
            [float(condenser_duty_packet_out.P_vapor_in_psia)], dtype=float
        )
        diag["condenser_duty_cache_P_condenser_psia"] = np.array(
            [float(condenser_duty_packet_out.P_condenser_psia)], dtype=float
        )
        diag["condenser_duty_cache_y_vapor_in"] = np.asarray(
            condenser_duty_packet_out.y_vapor_in, dtype=float
        ).reshape((Nc,)).copy()
        if (
            condenser_duty_packet_out.hL_cond_BTU_lbmol is not None
            and np.isfinite(float(condenser_duty_packet_out.hL_cond_BTU_lbmol))
        ):
            diag["condenser_duty_cache_hL_cond_BTU_lbmol"] = np.array(
                [float(condenser_duty_packet_out.hL_cond_BTU_lbmol)],
                dtype=float,
            )
    if np.isfinite(feed_vf_effective):
        diag["feed_vf_effective"] = np.array([float(feed_vf_effective)], dtype=float)
    if rhoL_tray is not None:
        try:
            diag["rhoL_tray_lbmol_ft3"] = np.asarray(rhoL_tray, dtype=float).reshape((N,)).copy()
        except Exception:
            pass
    if L_out_hyd_lbmolph is not None:
        try:
            diag["L_out_hyd_lbmolph"] = np.asarray(L_out_hyd_lbmolph, dtype=float).reshape((N,)).copy()
        except Exception:
            pass
    if h_ow_ft is not None:
        try:
            diag["h_ow_ft"] = np.asarray(h_ow_ft, dtype=float).reshape((N,)).copy()
        except Exception:
            pass
    diag["liquid_hydraulic_override_alpha"] = np.array([float(hydraulic_l_override_alpha)], dtype=float)
    diag["liquid_hydraulic_override_enabled"] = np.array(
        [1.0 if bool(inputs.enable_liquid_hydraulic_override) else 0.0],
        dtype=float,
    )
    if hydraulic_l_override_alpha_stage is not None:
        try:
            diag["liquid_hydraulic_override_alpha_per_stage"] = np.asarray(
                hydraulic_l_override_alpha_stage,
                dtype=float,
            ).reshape((N,)).copy()
        except Exception:
            pass
    if T_sump is not None:
        diag["T_sump_F"] = np.array([float(T_sump)], dtype=float)
    if "T_reb" in locals() and T_reb is not None:
        diag["T_reb_F"] = np.array([float(T_reb)], dtype=float)
    if reb_cache_out is not None:
        try:
            diag["reb_T_F"] = np.array([float(reb_cache_out["reb_T_F"])], dtype=float)
            diag["reb_beta"] = np.array([float(reb_cache_out["reb_beta"])], dtype=float)
            diag["reb_flash_ok"] = np.array([float(reb_cache_out["reb_flash_ok"])], dtype=float)
            diag["reb_flash_used_cache"] = np.array([float(reb_cache_out["reb_flash_used_cache"])], dtype=float)
            diag["reb_x"] = np.asarray(reb_cache_out["reb_x"], dtype=float).reshape((Nc,))
            diag["reb_y"] = np.asarray(reb_cache_out["reb_y"], dtype=float).reshape((Nc,))
        except Exception:
            pass
    # Base pressure diagnostic (Z defaults to 1)
    diag["P_psia_diag"] = _pressure_diagnostic_psia(col, diag["MV_tot_tray"], inputs.volume_model)

    # -----------------------
    # Thermo block used by Module 7/8A diagnostics and Module 8B equilibrium closure
    # -----------------------
    if do_thermo:
        if thermo_refresh_result is None:
            thermo_refresh_result = _build_current_tray_thermo_refresh(
                col=col,
                layout=layout,
                inputs=inputs,
                u=u,
                diag=diag,
                tray_L=tray_L,
                tray_V=tray_V,
                x_tray=x_tray,
                P_tray_hyd=P_tray_hyd,
                n_stages=N,
                n_components=Nc,
            )
        if thermo_refresh_result is None:
            raise ColumnRHSError("thermo_provider active but current tray thermo refresh could not be prepared.")
        thermo_packet = thermo_refresh_result.packet
        flash_skipped = np.asarray(thermo_refresh_result.flash_skipped, dtype=float).reshape((N,))
        flash_refreshed = np.asarray(thermo_refresh_result.flash_refreshed, dtype=float).reshape((N,))
        thermo_source_code = np.asarray(thermo_refresh_result.source_code, dtype=float).reshape((N,))
        thermo_flash_failed = np.asarray(thermo_refresh_result.flash_failed, dtype=float).reshape((N,))
        thermo_phase_count = np.asarray(thermo_refresh_result.phase_count, dtype=float).reshape((N,))
        thermo_quarantined = np.asarray(
            thermo_refresh_result.degenerate_two_phase_unit_K_quarantined, dtype=float
        ).reshape((N,))
        batch_used = bool(thermo_refresh_result.batch_used)
        K_packet = np.asarray(thermo_packet.K_tray, dtype=float).reshape((N, Nc))
        finite_K = np.isfinite(K_packet)
        K_unit_flag = np.zeros(N, dtype=float)
        K_max_abs_minus_one = np.full(N, np.nan, dtype=float)
        for i_unit in range(N):
            row = K_packet[i_unit, finite_K[i_unit, :]]
            if row.size:
                max_abs = float(np.max(np.abs(row - 1.0)))
                K_max_abs_minus_one[i_unit] = max_abs
                K_unit_flag[i_unit] = 1.0 if max_abs <= 1.0e-9 else 0.0

        # Module 8A: if Z provided, upgrade pressure diagnostic
        diag["Z_tray"] = thermo_packet.Zfac_tray
        diag["P_psia_diag"] = _pressure_diagnostic_psia(
            col,
            diag["MV_tot_tray"],
            inputs.volume_model,
            Z_factor=thermo_packet.Zfac_tray,
        )
        diag["thermo_flash_skipped"] = flash_skipped
        diag["thermo_flash_refreshed"] = flash_refreshed
        diag["thermo_flash_source_code"] = thermo_source_code
        diag["thermo_flash_failed"] = thermo_flash_failed
        diag["thermo_flash_phase_count"] = thermo_phase_count
        diag["thermo_degenerate_two_phase_unit_K_quarantined"] = thermo_quarantined
        diag["thermo_unit_K_flag"] = K_unit_flag
        diag["thermo_max_abs_K_minus_1"] = K_max_abs_minus_one
        diag["thermo_unit_K_refreshed_flag"] = K_unit_flag * np.where(flash_refreshed > 0.5, 1.0, 0.0)
        diag["thermo_unit_K_retained_flag"] = K_unit_flag * np.where(flash_refreshed <= 0.5, 1.0, 0.0)
        diag["thermo_degenerate_two_phase_unit_K_flag"] = (
            np.maximum(K_unit_flag, thermo_quarantined)
            * np.where(flash_refreshed > 0.5, 1.0, 0.0)
            * np.where(thermo_phase_count > 1.5, 1.0, 0.0)
        )
        diag["thermo_flash_batch_used"] = np.array([1.0 if batch_used else 0.0], dtype=float)

        # Module 7 diagnostics output
    if inputs.compute_thermo_diag and thermo_packet is not None:
        diag["z_overall_tray"] = thermo_packet.z_overall.copy()
        diag["K_tray"] = thermo_packet.K_tray.copy()
        diag["HL_BTU_lbmol_tray"] = thermo_packet.HL.copy()
        diag["HV_BTU_lbmol_tray"] = thermo_packet.HV.copy()
        if thermo_packet.cpL_tray is not None:
            diag["cpL_BTU_lbmolF_tray"] = np.asarray(thermo_packet.cpL_tray, dtype=float).reshape((N,)).copy()
        if thermo_packet.cpV_tray is not None:
            diag["cpV_BTU_lbmolF_tray"] = np.asarray(thermo_packet.cpV_tray, dtype=float).reshape((N,)).copy()
        if thermo_packet.x_eq is not None:
            diag["x_eq_thermo_tray"] = thermo_packet.x_eq.copy()
        if thermo_packet.y_eq is not None:
            diag["y_eq_thermo_tray"] = thermo_packet.y_eq.copy()

    # -----------------------
    # Module 8B: relaxed equilibrium closure using K
    # -----------------------
    if inputs.equilibrium_relaxation and layout.include_vapor:
        if thermo_packet is None and inputs.K_tray_prev is not None:
            # Thermo refresh can be intentionally skipped in outer integration steps.
            # In that case, reuse cached thermo K/HL/HV and current state z for
            # equilibrium relaxation to avoid losing closure between refreshes.
            Z_fb = np.zeros((N, Nc), dtype=float)
            for i in range(N):
                z = tray_L[i, :].copy()
                if tray_V is not None:
                    z = z + tray_V[i, :]
                s = float(np.sum(z))
                if s <= layout.epsilon_lbmol:
                    z = x_tray[i, :].copy()
                    s = float(np.sum(z))
                Z_fb[i, :] = z / max(s, 1e-300)

            try:
                K_fb = np.asarray(inputs.K_tray_prev, dtype=float).reshape((N, Nc)).copy()
            except Exception:
                K_fb = None
            if K_fb is not None:
                HL_fb = (
                    np.asarray(inputs.HL_prev, dtype=float).reshape((N,)).copy()
                    if inputs.HL_prev is not None
                    else np.zeros(N, dtype=float)
                )
                HV_fb = (
                    np.asarray(inputs.HV_prev, dtype=float).reshape((N,)).copy()
                    if inputs.HV_prev is not None
                    else np.zeros(N, dtype=float)
                )
                Zfac_fb = (
                    np.asarray(inputs.Zfac_prev, dtype=float).reshape((N,)).copy()
                    if inputs.Zfac_prev is not None
                    else np.ones(N, dtype=float)
                )
                thermo_packet = TrayThermoPacket(
                    z_overall_tray=Z_fb,
                    K_tray=K_fb,
                    HL_BTU_lbmol_tray=HL_fb,
                    HV_BTU_lbmol_tray=HV_fb,
                    Z_tray=Zfac_fb,
                    cpL_BTU_lbmolF_tray=(
                        None
                        if inputs.tray_thermo_prev is None or inputs.tray_thermo_prev.cpL_tray is None
                        else np.asarray(inputs.tray_thermo_prev.cpL_tray, dtype=float).reshape((N,)).copy()
                    ),
                    cpV_BTU_lbmolF_tray=(
                        None
                        if inputs.tray_thermo_prev is None or inputs.tray_thermo_prev.cpV_tray is None
                        else np.asarray(inputs.tray_thermo_prev.cpV_tray, dtype=float).reshape((N,)).copy()
                    ),
                    x_equilibrium_tray=(
                        None
                        if inputs.tray_thermo_prev is None or inputs.tray_thermo_prev.x_eq is None
                        else np.asarray(inputs.tray_thermo_prev.x_eq, dtype=float).reshape((N, Nc)).copy()
                    ),
                    y_equilibrium_tray=(
                        None
                        if inputs.tray_thermo_prev is None or inputs.tray_thermo_prev.y_eq is None
                        else np.asarray(inputs.tray_thermo_prev.y_eq, dtype=float).reshape((N, Nc)).copy()
                    ),
                )
                diag["thermo_flash_cached_only"] = np.array([1.0], dtype=float)
                if "z_overall_tray" not in diag:
                    diag["z_overall_tray"] = thermo_packet.z_overall.copy()
                if "K_tray" not in diag:
                    diag["K_tray"] = thermo_packet.K_tray.copy()
                if "HL_BTU_lbmol_tray" not in diag:
                    diag["HL_BTU_lbmol_tray"] = thermo_packet.HL.copy()
                if "HV_BTU_lbmol_tray" not in diag:
                    diag["HV_BTU_lbmol_tray"] = thermo_packet.HV.copy()
                if "Z_tray" not in diag:
                    diag["Z_tray"] = thermo_packet.Zfac_tray.copy()
                if "cpL_BTU_lbmolF_tray" not in diag and thermo_packet.cpL_tray is not None:
                    diag["cpL_BTU_lbmolF_tray"] = np.asarray(thermo_packet.cpL_tray, dtype=float).reshape((N,)).copy()
                if "cpV_BTU_lbmolF_tray" not in diag and thermo_packet.cpV_tray is not None:
                    diag["cpV_BTU_lbmolF_tray"] = np.asarray(thermo_packet.cpV_tray, dtype=float).reshape((N,)).copy()
                if "x_eq_thermo_tray" not in diag and thermo_packet.x_eq is not None:
                    diag["x_eq_thermo_tray"] = thermo_packet.x_eq.copy()
                if "y_eq_thermo_tray" not in diag and thermo_packet.y_eq is not None:
                    diag["y_eq_thermo_tray"] = thermo_packet.y_eq.copy()

        if thermo_packet is None:
            raise ColumnRHSError(
                "equilibrium_relaxation=True requires thermo data from thermo_provider "
                "or cached K_tray_prev."
            )

        # tau precedence: ColumnInputs overrides ColumnSpec; otherwise default 10 s
        tau = inputs.tau_eq_sec
        if tau is None:
            tau = getattr(col, "tau_eq_sec", 10.0)
        tau = float(tau)
        ramp_initial = getattr(inputs, "equilibrium_tau_ramp_initial_sec", None)
        ramp_final = getattr(inputs, "equilibrium_tau_ramp_final_sec", None)
        ramp_decay = getattr(inputs, "equilibrium_tau_ramp_decay_sec", None)
        if ramp_initial is not None and ramp_final is not None and ramp_decay is not None:
            try:
                tau_i = float(ramp_initial)
                tau_f = float(ramp_final)
                tau_d = float(ramp_decay)
                if (
                    np.isfinite(tau_i)
                    and np.isfinite(tau_f)
                    and np.isfinite(tau_d)
                    and tau_i > 0.0
                    and tau_f > 0.0
                    and tau_d > 0.0
                ):
                    t_use = max(float(t), 0.0)
                    tau = float(tau_f + (tau_i - tau_f) * np.exp(-float(t_use) / float(tau_d)))
            except Exception:
                pass

        if not np.isfinite(tau) or tau <= 0.0:
            raise ColumnRHSError("tau_eq_sec must be finite and > 0 when equilibrium_relaxation is enabled.")
        diag["eq_relax_tau_effective_sec"] = np.array([float(tau)], dtype=float)

        _Z_overall = np.asarray(thermo_packet.z_overall, dtype=float).reshape((N, Nc))
        K_tray = np.asarray(thermo_packet.K_tray, dtype=float).reshape((N, Nc))
        _HL = np.asarray(thermo_packet.HL, dtype=float).reshape((N,))
        _HV = np.asarray(thermo_packet.HV, dtype=float).reshape((N,))
        _Zfac = np.asarray(thermo_packet.Zfac_tray, dtype=float).reshape((N,))
        T_relax_raw = getattr(thermo_packet, "T_tray_F", None)
        if T_relax_raw is None:
            T_relax_raw = getattr(col, "T_f", np.full(N, 100.0))
        P_relax_raw = getattr(thermo_packet, "P_tray_psia", None)
        if P_relax_raw is None:
            P_relax_raw = getattr(col, "P_psia", np.full(N, 200.0))
        T_relax = np.asarray(T_relax_raw, dtype=float).reshape((N,))
        P_relax = np.asarray(P_relax_raw, dtype=float).reshape((N,))
        K_relax = K_tray.copy()
        eq_relax_provider = getattr(inputs, "equilibrium_relaxation_thermo_provider", None)
        if eq_relax_provider is None and bool(getattr(inputs.thermo_provider, "uses_direct_vapor_equilibrium", False)):
            eq_relax_provider = inputs.thermo_provider
        if eq_relax_provider is not None:
            eq_relax_override_active = False
            eq_relax_refreshed = np.zeros(N, dtype=float)
            batch_used_eq = False
            eq_relax_comp_source = (
                x_tray
                if bool(getattr(eq_relax_provider, "uses_liquid_composition_for_equilibrium", False))
                else _Z_overall
            )
            batch_fn_eq = getattr(eq_relax_provider, "flash_TP_full_batch", None)
            if callable(batch_fn_eq):
                try:
                    T_req = [float(T_relax[i]) for i in range(N)]
                    P_req = [float(P_relax[i]) for i in range(N)]
                    z_req = [np.asarray(eq_relax_comp_source[i, :], dtype=float).tolist() for i in range(N)]
                    fres_batch_eq = batch_fn_eq(T_req, P_req, z_req)
                    if len(fres_batch_eq) != N:
                        raise RuntimeError(
                            "equilibrium_relaxation_thermo_provider batch returned length "
                            f"{len(fres_batch_eq)}; expected {N}"
                        )
                    for i, fres in enumerate(fres_batch_eq):
                        if isinstance(fres, (tuple, list)):
                            if len(fres) < 3:
                                raise RuntimeError("equilibrium-relaxation batch flash tuple must include K")
                            K_relax[i, :] = np.asarray(fres[2], dtype=float).reshape((Nc,))
                        else:
                            K_relax[i, :] = np.asarray(getattr(fres, "K"), dtype=float).reshape((Nc,))
                        eq_relax_refreshed[i] = 1.0
                    batch_used_eq = True
                    eq_relax_override_active = True
                except Exception:
                    batch_used_eq = False
                    eq_relax_override_active = False
                    eq_relax_refreshed[:] = 0.0
            else:
                batch_used_eq = False
            if not batch_used_eq:
                eq_relax_error_count = 0
                for i in range(N):
                    try:
                        _trace_stage_thermo(
                            inputs,
                            f"eq_relax_flash stage={int(i + 1)}/{int(N)} start T_F={float(T_relax[i]):.3f} P_psia={float(P_relax[i]):.3f}",
                        )
                        fres = _flash_TP_full_stage_F_psia(
                            eq_relax_provider,
                            i,
                            float(T_relax[i]),
                            float(P_relax[i]),
                            eq_relax_comp_source[i, :],
                            n_components=Nc,
                            thermo_call_category="equilibrium_relaxation_flash",
                        )
                        K_relax[i, :] = np.asarray(fres.K, dtype=float).reshape((Nc,))
                        eq_relax_refreshed[i] = 1.0
                        eq_relax_override_active = True
                        _trace_stage_thermo(
                            inputs,
                            f"eq_relax_flash stage={int(i + 1)}/{int(N)} done",
                        )
                    except Exception as exc:
                        eq_relax_error_count += 1
                        _trace_stage_thermo(
                            inputs,
                            f"eq_relax_flash stage={int(i + 1)}/{int(N)} failed; keeping base K",
                        )
                        pass
                if eq_relax_error_count:
                    diag["eq_relax_thermo_flash_error_count"] = np.array([float(eq_relax_error_count)], dtype=float)
            diag["eq_relax_thermo_override_active"] = np.array(
                [1.0 if eq_relax_override_active else 0.0], dtype=float
            )
            diag["eq_relax_thermo_flash_refreshed"] = eq_relax_refreshed
            diag["eq_relax_thermo_flash_batch_used"] = np.array([1.0 if batch_used_eq else 0.0], dtype=float)
        else:
            diag["eq_relax_thermo_override_active"] = np.array([0.0], dtype=float)
        if "K_tray" not in diag:
            diag["K_tray"] = np.asarray(K_tray, dtype=float).reshape((N, Nc)).copy()
        if "z_overall_tray" not in diag:
            diag["z_overall_tray"] = np.asarray(_Z_overall, dtype=float).reshape((N, Nc)).copy()
        _trace_stage_thermo(inputs, "post_flash entering equilibrium split construction")

        # Flash-consistent interphase relaxation:
        #   1) compute equilibrium split (beta_eq, x_eq, y_eq) from (K, z_overall)
        #   2) relax tray phase holdups toward (L*, V*) at timescale tau
        # This yields nonzero net phase change per tray while conserving each
        # component exactly.
        ML = np.asarray(diag["ML_tot_tray"], dtype=float).reshape((N,))
        MV = np.asarray(diag["MV_tot_tray"], dtype=float).reshape((N,))
        Mtot = ML + MV

        x_eq = np.zeros((N, Nc), dtype=float)
        y_eq = np.zeros((N, Nc), dtype=float)
        beta_eq = np.zeros(N, dtype=float)
        direct_vapor_eq_fn = None
        if bool(getattr(eq_relax_provider, "uses_direct_vapor_equilibrium", False)):
            candidate = getattr(eq_relax_provider, "equilibrium_y_K_from_x", None)
            if callable(candidate):
                direct_vapor_eq_fn = candidate

        for i in range(N):
            _trace_stage_thermo(inputs, f"eq_split stage={int(i + 1)}/{int(N)} start")
            if direct_vapor_eq_fn is not None:
                x_i = np.asarray(x_tray[i, :], dtype=float).reshape((Nc,))
                sx = float(np.sum(x_i))
                if (not np.isfinite(sx)) or sx <= 1e-300:
                    x_i = np.full(Nc, 1.0 / float(Nc), dtype=float)
                else:
                    x_i = np.clip(x_i / sx, 0.0, None)
                    x_i = x_i / max(float(np.sum(x_i)), 1e-300)
                try:
                    y_i, K_i = direct_vapor_eq_fn(x_i)
                    y_i = np.asarray(y_i, dtype=float).reshape((Nc,))
                    K_i = np.asarray(K_i, dtype=float).reshape((Nc,))
                except Exception:
                    y_i = np.asarray(y_tray[i, :], dtype=float).reshape((Nc,))
                    K_i = np.asarray(K_relax[i, :], dtype=float).reshape((Nc,))
                sy = float(np.sum(y_i))
                if (not np.isfinite(sy)) or sy <= 1e-300:
                    y_i = np.asarray(y_tray[i, :], dtype=float).reshape((Nc,))
                    sy = float(np.sum(y_i))
                y_i = np.clip(y_i / max(sy, 1e-300), 0.0, None)
                y_i = y_i / max(float(np.sum(y_i)), 1e-300)
                K_i = np.where(~np.isfinite(K_i) | (K_i <= 1e-12), 1e-12, K_i)
                K_relax[i, :] = K_i
                beta_eq[i] = float(MV[i] / max(Mtot[i], 1e-300))
                x_eq[i, :] = x_i
                y_eq[i, :] = y_i
                _trace_stage_thermo(inputs, f"eq_split stage={int(i + 1)}/{int(N)} done beta={float(beta_eq[i]):.5g} direct_vapor_eq=1")
                continue

            z_i = np.asarray(_Z_overall[i, :], dtype=float).reshape((Nc,))
            zsum = float(np.sum(z_i))
            if (not np.isfinite(zsum)) or zsum <= 1e-300:
                z_i = np.asarray(x_tray[i, :], dtype=float).reshape((Nc,))
                zsum = float(np.sum(z_i))
            z_i = z_i / max(zsum, 1e-300)

            K_i = np.asarray(K_relax[i, :], dtype=float).reshape((Nc,))
            K_i = np.where(~np.isfinite(K_i) | (K_i <= 1e-12), 1e-12, K_i)

            beta_i = _rachford_rice_beta(K_i, z_i)
            beta_i = float(np.clip(beta_i, 0.0, 1.0))
            beta_eq[i] = beta_i

            denom = 1.0 + beta_i * (K_i - 1.0)
            denom = np.where(np.abs(denom) < 1e-12, np.sign(denom) * 1e-12 + (denom == 0.0) * 1e-12, denom)

            x_i = np.clip(z_i / denom, 0.0, None)
            sx = float(np.sum(x_i))
            if (not np.isfinite(sx)) or sx <= 1e-300:
                x_i = np.asarray(x_tray[i, :], dtype=float).reshape((Nc,))
                sx = float(np.sum(x_i))
            x_i = x_i / max(sx, 1e-300)

            y_i = np.clip(K_i * x_i, 0.0, None)
            sy = float(np.sum(y_i))
            if (not np.isfinite(sy)) or sy <= 1e-300:
                y_i = np.asarray(y_tray[i, :], dtype=float).reshape((Nc,))
                sy = float(np.sum(y_i))
            y_i = y_i / max(sy, 1e-300)

            x_eq[i, :] = x_i
            y_eq[i, :] = y_i
            _trace_stage_thermo(inputs, f"eq_split stage={int(i + 1)}/{int(N)} done beta={float(beta_i):.5g}")

        _trace_stage_thermo(inputs, "post_flash equilibrium split construction complete")

        mode_raw = str(getattr(inputs, "equilibrium_relaxation_mode", "phase-holdup") or "phase-holdup").strip().lower()
        comp_only_mode = mode_raw in ("composition-only", "composition", "comp-only", "y-only")

        Mtot_col = Mtot.reshape((N, 1))
        phase_guard_lbmol = float(getattr(inputs, "equilibrium_phase_holdup_guard_lbmol", 0.0) or 0.0)
        if (not np.isfinite(phase_guard_lbmol)) or phase_guard_lbmol < 0.0:
            phase_guard_lbmol = 0.0
        if comp_only_mode:
            # Relax only vapor composition at fixed vapor holdup totals.
            MV_eq = MV.reshape((N, 1))
            MV_target_eff = MV.reshape((N, 1))
            y_target = y_eq.copy()
            V_target = MV.reshape((N, 1)) * y_eq
            phase_weight = np.ones(N, dtype=float)
        else:
            _trace_stage_thermo(inputs, "post_flash building phase-holdup targets")
            # Legacy behavior: relax toward flash-predicted phase split.
            MV_eq = beta_eq.reshape((N, 1)) * Mtot_col
            if phase_guard_lbmol > 0.0:
                MV_eq_tot = np.asarray(MV_eq, dtype=float).reshape((N,))
                denom = np.asarray(MV, dtype=float).reshape((N,)) + MV_eq_tot + float(phase_guard_lbmol)
                denom = np.where(np.abs(denom) > 1.0e-12, denom, float(phase_guard_lbmol))
                phase_weight = (np.asarray(MV, dtype=float).reshape((N,)) + MV_eq_tot) / denom
                # In the stripping section, soften phase-holdup relaxation on
                # strongly liquid-dominated trays so it does not overwhelm the
                # transport balance and artificially condense vapor into liquid.
                # Keep the rectifying section at the base phase-holdup weighting.
                vapor_fraction_weight = (np.asarray(MV, dtype=float).reshape((N,)) + MV_eq_tot) / np.maximum(
                    np.asarray(Mtot, dtype=float).reshape((N,)),
                    float(phase_guard_lbmol),
                )
                vapor_fraction_weight = np.clip(vapor_fraction_weight, 0.25, 1.0)
                phase_weight_cap = np.full(N, np.nan, dtype=float)
                energy_damping = np.ones(N, dtype=float)
                if feed_stage0 is not None:
                    stripping_mask = np.zeros(N, dtype=bool)
                    i_feed = int(np.clip(int(feed_stage0), 0, max(N - 1, 0)))
                    stripping_mask[i_feed:] = True
                    strip_depth = np.zeros(N, dtype=float)
                    denom_strip = max(float(N - 1 - i_feed), 1.0)
                    strip_depth[i_feed:] = np.arange(0, N - i_feed, dtype=float) / denom_strip
                    # Toward the column bottom, further back off phase-holdup
                    # relaxation so liquid-dominated trays are not repeatedly
                    # forced to condense vapor into liquid inventory.
                    strip_depth_weight = 1.0 - 0.75 * np.power(strip_depth, 1.5)
                    strip_depth_weight = np.clip(strip_depth_weight, 0.25, 1.0)
                    current_vapor_fraction = np.asarray(MV, dtype=float).reshape((N,)) / np.maximum(
                        np.asarray(Mtot, dtype=float).reshape((N,)),
                        float(phase_guard_lbmol),
                    )
                    current_vapor_fraction = np.clip(current_vapor_fraction, 0.0, 1.0)
                    # Below the feed, cap the effective phase-holdup weighting by a
                    # conservative monotone ceiling so flash-target shifts cannot
                    # suddenly re-accelerate liquid depletion on hot stripping trays.
                    stripping_cap = 0.15 + 0.60 * current_vapor_fraction * strip_depth_weight
                    stripping_cap = np.clip(stripping_cap, 0.15, 0.45)
                    prev_energy_resid = getattr(inputs, "energy_balance_resid_prev_BTUps_tray", None)
                    energy_gain = float(getattr(inputs, "equilibrium_energy_damping_gain", 0.0) or 0.0)
                    if prev_energy_resid is not None and np.isfinite(energy_gain) and energy_gain > 0.0:
                        try:
                            e_prev = np.asarray(prev_energy_resid, dtype=float).reshape((N,))
                            e_prev = np.where(np.isfinite(e_prev), np.abs(e_prev), 0.0)
                            H_inventory = (
                                np.abs(np.asarray(ML, dtype=float).reshape((N,)) * np.asarray(_HL, dtype=float).reshape((N,)))
                                + np.abs(np.asarray(MV, dtype=float).reshape((N,)) * np.asarray(_HV, dtype=float).reshape((N,)))
                            )
                            H_inventory = np.maximum(H_inventory, 1.0)
                            e_ratio = (e_prev * float(tau)) / H_inventory
                            energy_damping = np.exp(-float(energy_gain) * e_ratio)
                            energy_damping = np.clip(energy_damping, 0.25, 1.0)
                            prev_energy_damping_min = getattr(inputs, "phase_energy_damping_min_prev_tray", None)
                            if prev_energy_damping_min is not None:
                                prev_energy_damping_min = np.asarray(prev_energy_damping_min, dtype=float).reshape((N,))
                                prev_energy_damping_min = np.where(
                                    np.isfinite(prev_energy_damping_min),
                                    np.clip(prev_energy_damping_min, 0.25, 1.0),
                                    1.0,
                                )
                                energy_damping = np.where(
                                    stripping_mask,
                                    np.minimum(prev_energy_damping_min, energy_damping),
                                    energy_damping,
                                )
                            stripping_cap = stripping_cap * energy_damping
                            stripping_cap = np.clip(stripping_cap, 0.10, 0.45)
                        except Exception:
                            energy_damping = np.ones(N, dtype=float)
                    phase_weight_cap = np.where(stripping_mask, stripping_cap, phase_weight_cap)
                    phase_weight = np.where(stripping_mask, np.minimum(phase_weight, stripping_cap), phase_weight)
                phase_weight = np.clip(phase_weight, 0.0, 1.0)
                y_target = phase_weight.reshape((N, 1)) * y_eq + (1.0 - phase_weight).reshape((N, 1)) * y_tray
                y_target = np.clip(y_target, 0.0, None)
                sy_target = np.sum(y_target, axis=1, keepdims=True)
                sy_target = np.where(sy_target > 1.0e-300, sy_target, 1.0)
                y_target = y_target / sy_target
                MV_target_eff = phase_weight.reshape((N, 1)) * MV_eq + (1.0 - phase_weight).reshape((N, 1)) * MV.reshape((N, 1))
                V_target = MV_target_eff * y_target
            else:
                phase_weight = np.ones(N, dtype=float)
                y_target = y_eq.copy()
                MV_target_eff = MV_eq.copy()
                V_target = MV_eq * y_eq
        _trace_stage_thermo(inputs, "post_flash target construction complete")
        transfer = (V_target - tray_V) / float(tau)  # (N,Nc) lbmol/s
        liquid_transport_rate = np.sum(d_tray_L, axis=1).reshape((N,))
        liquid_feed_rate = np.sum(d_tray_L_feed, axis=1).reshape((N,))

        # No interphase transfer on total-condenser tray (stage 1).
        transfer[0, :] = 0.0
        # No interphase transfer on no-holdup reboiler stage.
        if reboiler_no_holdup and N > 0:
            transfer[-1, :] = 0.0
        phase_rate_scale = np.ones(N, dtype=float)
        phase_rate_limit = np.full(N, np.nan, dtype=float)
        phase_rate_liq_guard = float(getattr(inputs, "equilibrium_phase_rate_liquid_guard_lbmol", 0.0) or 0.0)
        phase_rate_vap_guard = float(getattr(inputs, "equilibrium_phase_rate_vapor_guard_lbmol", 0.0) or 0.0)
        phase_rate_frac = float(getattr(inputs, "equilibrium_phase_rate_max_frac_per_tau", 0.0) or 0.0)
        if (
            np.isfinite(phase_rate_frac)
            and phase_rate_frac > 0.0
            and (np.isfinite(phase_rate_liq_guard) or np.isfinite(phase_rate_vap_guard))
        ):
            transfer, phase_rate_scale, phase_rate_limit = _limit_equilibrium_phase_transfer_rates(
                transfer,
                ML_tot_lbmol=ML,
                MV_tot_lbmol=MV,
                tau_sec=float(tau),
                liquid_guard_lbmol=phase_rate_liq_guard,
                vapor_guard_lbmol=phase_rate_vap_guard,
                max_frac_per_tau=phase_rate_frac,
            )

        dydt[sl["tray_V"]] += transfer.reshape(-1)
        dydt[sl["tray_L"]] -= transfer.reshape(-1)
        liquid_phase_relax_rate = -np.sum(transfer, axis=1).reshape((N,))
        liquid_total_rate = liquid_transport_rate + liquid_phase_relax_rate

        diag["x_eq_tray"] = x_eq
        diag["y_eq_tray"] = y_eq
        diag["K_eq_relax_tray"] = np.asarray(K_relax, dtype=float).reshape((N, Nc))
        diag["y_target_tray"] = y_target
        diag["beta_eq_tray"] = beta_eq.reshape((N,))
        diag["eq_target_mv_total_lbmol_tray"] = np.sum(MV_target_eff, axis=1).reshape((N,))
        diag["eq_flash_mv_total_lbmol_tray"] = np.sum(MV_eq, axis=1).reshape((N,))
        diag["eq_target_vapor_lbmol_tray"] = V_target
        diag["eq_target_vapor_total_lbmol_tray"] = np.sum(V_target, axis=1).reshape((N,))
        diag["eq_target_vapor_delta_lbmol_tray"] = (
            np.sum(V_target, axis=1).reshape((N,)) - np.asarray(MV, dtype=float).reshape((N,))
        )
        diag["eq_target_vapor_fraction_tray"] = (
            np.sum(V_target, axis=1).reshape((N,)) / np.maximum(np.asarray(Mtot, dtype=float).reshape((N,)), 1.0e-12)
        )
        diag["eq_current_vapor_fraction_tray"] = (
            np.asarray(MV, dtype=float).reshape((N,)) / np.maximum(np.asarray(Mtot, dtype=float).reshape((N,)), 1.0e-12)
        )
        diag["eq_transfer_lbmolps_tray"] = transfer
        diag["eq_phase_change_lbmolps_tray"] = np.sum(transfer, axis=1).reshape((N,))
        diag["eq_relaxation_mode_comp_only"] = np.array([1.0 if comp_only_mode else 0.0], dtype=float)
        diag["eq_phase_holdup_guard_weight_tray"] = np.asarray(phase_weight, dtype=float).reshape((N,))
        diag["eq_phase_rate_guard_scale_tray"] = np.asarray(phase_rate_scale, dtype=float).reshape((N,))
        diag["eq_phase_rate_guard_limit_lbmolps_tray"] = np.asarray(phase_rate_limit, dtype=float).reshape((N,))
        if 'phase_weight_cap' in locals():
            diag["eq_phase_holdup_guard_cap_tray"] = np.asarray(phase_weight_cap, dtype=float).reshape((N,))
        if 'energy_damping' in locals():
            diag["eq_phase_energy_damping_tray"] = np.asarray(energy_damping, dtype=float).reshape((N,))
        diag["dMLdt_transport_lbmolps_tray"] = np.asarray(liquid_transport_rate, dtype=float).reshape((N,))
        diag["dMLdt_phase_relax_lbmolps_tray"] = np.asarray(liquid_phase_relax_rate, dtype=float).reshape((N,))
        diag["dMLdt_total_lbmolps_tray"] = np.asarray(liquid_total_rate, dtype=float).reshape((N,))
        diag["dMLdt_feed_lbmolps_tray"] = np.asarray(liquid_feed_rate, dtype=float).reshape((N,))
        _trace_stage_thermo(inputs, "post_flash equilibrium-relaxation diagnostics complete")

    if "K_tray" in diag and "K_state_y_over_x_tray" in diag:
        try:
            K_state = np.asarray(diag["K_state_y_over_x_tray"], dtype=float).reshape((N, Nc))
            K_thermo = np.asarray(diag["K_tray"], dtype=float).reshape((N, Nc))
            K_ratio = np.full((N, Nc), np.nan, dtype=float)
            valid = np.isfinite(K_state) & np.isfinite(K_thermo) & (np.abs(K_thermo) > 1.0e-12)
            if np.any(valid):
                K_ratio[valid] = K_state[valid] / K_thermo[valid]
            K_delta = K_state - K_thermo
            if N > 0:
                mv0 = float(np.sum(np.asarray(tray_V[0, :], dtype=float)))
                if (not np.isfinite(mv0)) or (mv0 <= float(layout.epsilon_lbmol)):
                    K_ratio[0, :] = np.nan
                    K_delta[0, :] = np.nan
            diag["K_state_over_K_thermo_tray"] = K_ratio
            diag["K_state_minus_K_thermo_tray"] = K_delta
        except Exception:
            pass

    # -----------------------
    # Option B1 energy holdup
    # -----------------------
    if bool(getattr(layout, "include_energy", False)):
        _trace_stage_thermo(inputs, "energy_holdup block start")
        if "tray_EL_BTU" not in u:
            raise ColumnRHSError("layout.include_energy=True requires tray_EL_BTU in layout.unpack(y).")
        if layout.include_vapor and ("tray_EV_BTU" not in u):
            raise ColumnRHSError("layout.include_energy=True and include_vapor=True requires tray_EV_BTU in layout.unpack(y).")

        EL = np.asarray(u["tray_EL_BTU"], dtype=float).reshape((N,))
        EV = np.asarray(u["tray_EV_BTU"], dtype=float).reshape((N,)) if layout.include_vapor else np.zeros(N, dtype=float)

        if "tray_T_f" in u:
            T_tray_q = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
        elif hasattr(col, "T_f"):
            T_tray_q = np.asarray(col.T_f, dtype=float).reshape((N,))
        else:
            T_tray_q = np.full(N, 100.0, dtype=float)

        if hasattr(col, "P_psia"):
            P_tray_q = np.asarray(col.P_psia, dtype=float).reshape((N,))
        else:
            P_tray_q = np.asarray(diag.get("P_psia_diag", np.full(N, 200.0, dtype=float)), dtype=float).reshape((N,))
        if P_tray_hyd is not None:
            try:
                P_tray_q = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
            except Exception:
                pass

        Qc_BTUph, Qc_calc_BTUph, T_cond_bubble_F, _Qc_hL_cond_BTU_lbmol, condenser_duty_mode = _resolve_condenser_duty_cached(
            tray_T_F=T_tray_q,
            P_tray_psia=P_tray_q,
        )
        Qr_BTUph = float(duty_btu_ph)

        diag["Q_cond_used_BTUph"] = np.array([float(Qc_BTUph)], dtype=float)
        diag["Q_reb_used_BTUph"] = np.array([float(Qr_BTUph)], dtype=float)
        diag["Q_cond_mode_total_condense"] = np.array(
            [1.0 if str(condenser_duty_mode) == "total-condense" else 0.0], dtype=float
        )
        if Qc_calc_BTUph is not None and np.isfinite(float(Qc_calc_BTUph)):
            diag["Q_cond_calc_BTUph"] = np.array([float(Qc_calc_BTUph)], dtype=float)
        if T_cond_bubble_F is not None and np.isfinite(float(T_cond_bubble_F)):
            diag["T_cond_bubble_F"] = np.array([float(T_cond_bubble_F)], dtype=float)

        condenser_is_total = bool(float(V_out[0]) <= float(layout.epsilon_lbmol))
        try:
            ctype = str(getattr(getattr(col, "duties", None), "condenser_type", "") or "").strip().lower()
            if ctype:
                condenser_is_total = ("total" in ctype)
        except Exception:
            pass
        no_liquid_holdup = np.asarray(diag["ML_tot_tray"], dtype=float).reshape((N,)) <= float(layout.epsilon_lbmol)
        no_vapor_holdup = np.asarray(diag["MV_tot_tray"], dtype=float).reshape((N,)) <= float(layout.epsilon_lbmol)
        condenser_boundary_owns_duty = bool(
            condenser_is_total
            and N > 0
            and bool(no_liquid_holdup[0])
        )
        top_boundary_liquid_h_BTU_lbmol = None
        if bool(condenser_boundary_owns_duty) and bool(condenser_is_total) and N > 0:
            try:
                src_i = 1 if N > 1 else 0
                mv_src = float(np.asarray(diag["MV_tot_tray"], dtype=float).reshape((N,))[src_i])
                mv_top = 0.0
                if layout.include_top and top_V is not None:
                    mv_top = float(np.sum(np.asarray(top_V, dtype=float).reshape((Nc,))))
                hV_src = np.nan
                hV_top = np.nan
                if np.isfinite(mv_src) and mv_src > float(layout.epsilon_lbmol):
                    hV_src = float(np.asarray(EV, dtype=float).reshape((N,))[src_i]) / mv_src
                if np.isfinite(mv_top) and mv_top > float(layout.epsilon_lbmol):
                    # Top vapor currently has no independent energy state; use
                    # the condenser inlet vapor enthalpy for boundary closure.
                    hV_top = hV_src
                v_from_column = float(V_condensed_in_lbmolps)
                v_from_top = float(V_condensed_top_lbmolps)
                v_total = v_from_column + v_from_top
                e_in = 0.0
                if np.isfinite(hV_src):
                    e_in += v_from_column * float(hV_src)
                if np.isfinite(hV_top):
                    e_in += v_from_top * float(hV_top)
                if np.isfinite(e_in) and np.isfinite(v_total) and v_total > float(layout.epsilon_lbmol):
                    h_from_boundary = (float(e_in) + (float(Qc_BTUph) / 3600.0)) / float(v_total)
                    if np.isfinite(h_from_boundary):
                        top_boundary_liquid_h_BTU_lbmol = float(h_from_boundary)
            except Exception:
                pass
        if (
            top_boundary_liquid_h_BTU_lbmol is None
            and _Qc_hL_cond_BTU_lbmol is not None
            and np.isfinite(float(_Qc_hL_cond_BTU_lbmol))
        ):
            top_boundary_liquid_h_BTU_lbmol = float(_Qc_hL_cond_BTU_lbmol)
        elif bool(condenser_is_total) and N > 0:
            try:
                src_i = 1 if N > 1 else 0
                v_cond_lbmolps = float(V_in[0])
                mv_src = float(np.asarray(diag["MV_tot_tray"], dtype=float).reshape((N,))[src_i])
                if (
                    np.isfinite(v_cond_lbmolps)
                    and v_cond_lbmolps > float(layout.epsilon_lbmol)
                    and np.isfinite(mv_src)
                    and mv_src > float(layout.epsilon_lbmol)
                ):
                    hV_src = float(np.asarray(EV, dtype=float).reshape((N,))[src_i]) / mv_src
                    h_from_duty = hV_src + (float(Qc_BTUph) / (float(v_cond_lbmolps) * 3600.0))
                    if np.isfinite(h_from_duty):
                        top_boundary_liquid_h_BTU_lbmol = float(h_from_duty)
            except Exception:
                pass
        if top_boundary_liquid_h_BTU_lbmol is not None:
            diag["total_condenser_reflux_hL_BTU_lbmol"] = np.array(
                [float(top_boundary_liquid_h_BTU_lbmol)],
                dtype=float,
            )
            try:
                src_i = 1 if N > 1 else 0
                mv_src = float(np.asarray(diag["MV_tot_tray"], dtype=float).reshape((N,))[src_i])
                mv_top = 0.0
                if layout.include_top and top_V is not None:
                    mv_top = float(np.sum(np.asarray(top_V, dtype=float).reshape((Nc,))))
                hV_src = np.nan
                hV_top = np.nan
                if np.isfinite(mv_src) and mv_src > float(layout.epsilon_lbmol):
                    hV_src = float(np.asarray(EV, dtype=float).reshape((N,))[src_i]) / mv_src
                if np.isfinite(mv_top) and mv_top > float(layout.epsilon_lbmol):
                    # The top vapor holdup does not currently own a separate
                    # energy state, so use the condenser inlet vapor enthalpy
                    # as the algebraic top-boundary vapor enthalpy estimate.
                    hV_top = hV_src
                h_cond = float(top_boundary_liquid_h_BTU_lbmol)
                q_boundary = float(Qc_BTUph) / 3600.0
                e_in = 0.0
                e_out = 0.0
                if np.isfinite(hV_src):
                    e_in += float(V_condensed_in_lbmolps) * float(hV_src)
                if np.isfinite(hV_top):
                    e_in += float(V_condensed_top_lbmolps) * float(hV_top)
                if np.isfinite(h_cond):
                    e_out += (
                        float(V_condensed_in_lbmolps) + float(V_condensed_top_lbmolps)
                    ) * float(h_cond)
                e_resid = float(e_in + q_boundary - e_out)
                if np.isfinite(e_resid):
                    diag["total_condenser_boundary_energy_residual_BTUps"] = np.array(
                        [float(e_resid)],
                        dtype=float,
                    )
                    scale = max(abs(float(e_in)), abs(float(q_boundary)), abs(float(e_out)), 1.0)
                    diag["total_condenser_boundary_energy_residual_rel"] = np.array(
                        [float(e_resid) / float(scale)],
                        dtype=float,
                    )
            except Exception:
                pass
        diag["total_condenser_boundary_energy_owner"] = np.array(
            [1.0 if condenser_boundary_owns_duty else 0.0],
            dtype=float,
        )

        thermo_b1 = inputs.thermo
        if thermo_b1 is None:
            thermo_b1 = ConstantCpThermo(
                cp_liq_components=np.full(Nc, 30.0, dtype=float),
                cp_vap_components=np.full(Nc, 20.0, dtype=float),
                tref_f=60.0,
            )
        q_feed_BTUps = np.zeros(N, dtype=float)
        if feed_stage0 is not None and (0 <= int(feed_stage0) < N):
            i_feed = int(feed_stage0)
            q_feed_BTUps[i_feed] = _feed_enthalpy_rate_btu_per_s(
                feed_stage0=feed_stage0,
                stage0=i_feed,
                col=col,
                Nc=Nc,
                Fk_L=Fk_L,
                Fk_V=Fk_V,
                T_stage_F=float(T_tray_q[i_feed]),
                P_stage_psia=float(P_tray_q[i_feed]),
                thermo=thermo_b1,
                thermo_provider=inputs.thermo_provider,
                epsilon_lbmol=float(layout.epsilon_lbmol),
                feed_stage_flash_prev=inputs.feed_stage_flash_prev,
                feed_stage_flash_reuse_dT_F=float(inputs.feed_stage_flash_reuse_dT_F),
                feed_stage_flash_reuse_dP_psia=float(inputs.feed_stage_flash_reuse_dP_psia),
                feed_stage_flash_reuse_dx=float(inputs.feed_stage_flash_reuse_dx),
            )
        diag["Q_feed_BTUps_tray"] = q_feed_BTUps.copy()
        dEL, dEV = _energy_derivatives_b1(
            L_out=L_out,
            V_out=V_out,
            ML_tot=diag["ML_tot_tray"],
            MV_tot=diag["MV_tot_tray"],
            EL_BTU=EL,
            EV_BTU=EV,
            Q_cond_BTUph=Qc_BTUph,
            Q_reb_BTUph=Qr_BTUph,
            Q_feed_BTUps=q_feed_BTUps,
            epsilon_lbmol=layout.epsilon_lbmol,
            total_condenser=bool(condenser_is_total),
            max_abs_h_btu_per_lbmol=1.0e6,
            no_liquid_holdup_mask=no_liquid_holdup,
            no_vapor_holdup_mask=no_vapor_holdup,
            top_boundary_liquid_h_BTU_lbmol=top_boundary_liquid_h_BTU_lbmol,
            condenser_boundary_owns_duty=condenser_boundary_owns_duty,
        )

        # Stage-N can be configured as a no-holdup reboiler flash.
        # In that mode, there is no tray energy holdup state to integrate.
        if reboiler_no_holdup and N > 0:
            dEL[-1] = 0.0
            dEV[-1] = 0.0

        dydt[sl["tray_EL_BTU"]] = dEL
        if layout.include_vapor:
            dydt[sl["tray_EV_BTU"]] = dEV

        diag["dEL_BTU_per_s"] = dEL.copy()
        diag["dEV_BTU_per_s"] = dEV.copy()
        _trace_stage_thermo(inputs, "energy_holdup derivatives complete")
        try:
            energy_resid = (dEL + dEV).copy()
            if reboiler_no_holdup and N > 0:
                energy_resid[-1] = np.nan
            no_state = (
                (np.asarray(diag["ML_tot_tray"], dtype=float).reshape((N,)) <= float(layout.epsilon_lbmol))
                & (np.asarray(diag["MV_tot_tray"], dtype=float).reshape((N,)) <= float(layout.epsilon_lbmol))
            )
            energy_resid[no_state] = np.nan
            diag["energy_balance_resid_BTUps_tray"] = energy_resid
            er_finite = np.asarray(energy_resid, dtype=float)
            er_finite = er_finite[np.isfinite(er_finite)]
            if er_finite.size > 0:
                diag["resid_energy_btups"] = np.array([float(np.max(np.abs(er_finite)))], dtype=float)
            else:
                diag["resid_energy_btups"] = np.array([np.nan], dtype=float)
        except Exception:
            pass
        _trace_stage_thermo(inputs, "energy_holdup diagnostics complete")

    # -----------------------
    # Legacy temperature-state energy balance (kept intact)
    # -----------------------
    if bool(getattr(layout, "include_temperature", False)) and bool(
        getattr(inputs, "enable_legacy_temperature_state", True)
    ):
        _trace_stage_thermo(inputs, "temperature_state block start")
        thermo = inputs.thermo
        if thermo is None:
            thermo = ConstantCpThermo(
                cp_liq_components=np.full(Nc, 30.0, dtype=float),
                cp_vap_components=np.full(Nc, 20.0, dtype=float),
                tref_f=60.0,
            )

        tray_T = u["tray_T_f"].reshape(N)
        bot_T = float(u["bottom_T_f"][0]) if layout.include_bottom and "bottom_T_f" in u else None

        P_tray = np.asarray(col.P_psia, dtype=float).reshape(N) if hasattr(col, "P_psia") else diag["P_psia_diag"].reshape(N)
        if P_tray_hyd is not None:
            try:
                P_tray = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
            except Exception:
                pass

        Qc_BTUph, Qc_calc_BTUph, T_cond_bubble_F, _Qc_hL_cond_BTU_lbmol, condenser_duty_mode = _resolve_condenser_duty_cached(
            tray_T_F=np.asarray(tray_T, dtype=float).reshape((N,)),
            P_tray_psia=np.asarray(P_tray, dtype=float).reshape((N,)),
        )
        Qr_BTUph = float(duty_btu_ph)

        diag["Q_cond_used_BTUph"] = np.array([float(Qc_BTUph)], dtype=float)
        diag["Q_reb_used_BTUph"] = np.array([float(Qr_BTUph)], dtype=float)
        diag["Q_cond_mode_total_condense"] = np.array(
            [1.0 if str(condenser_duty_mode) == "total-condense" else 0.0], dtype=float
        )
        if Qc_calc_BTUph is not None and np.isfinite(float(Qc_calc_BTUph)):
            diag["Q_cond_calc_BTUph"] = np.array([float(Qc_calc_BTUph)], dtype=float)
        if T_cond_bubble_F is not None and np.isfinite(float(T_cond_bubble_F)):
            diag["T_cond_bubble_F"] = np.array([float(T_cond_bubble_F)], dtype=float)

        dT_tray = np.zeros(N, dtype=float)
        q_phase_latent_tray = np.zeros(N, dtype=float)
        dT_energy_raw_tray = np.zeros(N, dtype=float)
        dT_mode_correction_tray = np.zeros(N, dtype=float)
        dT_phase_latent_equiv_tray = np.zeros(N, dtype=float)
        tray_heat_capacity_BTU_per_F = np.zeros(N, dtype=float)
        tray_effective_heat_capacity_BTU_per_F = np.zeros(N, dtype=float)
        tray_temperature_guard_active = np.zeros(N, dtype=float)
        tray_temperature_rate_limit_F_per_s = np.full(N, np.nan, dtype=float)
        T_bubble_target = np.full(N, np.nan, dtype=float)
        T_enthalpy_state_target = np.full(N, np.nan, dtype=float)
        E_enthalpy_state_mismatch = np.full(N, np.nan, dtype=float)
        T_enthalpy_state_correction = np.zeros(N, dtype=float)
        T_pressure_correction = np.zeros(N, dtype=float)
        T_pressure_slope_used = np.full(N, np.nan, dtype=float)
        use_provider_cp = (
            inputs.thermo_provider is not None
            and hasattr(inputs.thermo_provider, "cp_liq_vap_btu_per_lbmolF")
        )
        packet_dx_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dx", 0.0) or 0.0)
        packet_dT_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dT_F", 0.0) or 0.0)
        packet_dP_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dP_psia", 0.0) or 0.0)
        temp_guard_holdup = float(getattr(inputs, "hydraulic_energy_temperature_holdup_guard_lbmol", 0.0) or 0.0)
        temp_guard_min_C = float(
            getattr(inputs, "hydraulic_energy_temperature_min_heat_capacity_BTU_per_F", 0.0) or 0.0
        )
        temp_guard_max_rate = getattr(inputs, "hydraulic_energy_temperature_max_dT_rate_F_per_s", None)
        if temp_guard_max_rate is not None:
            try:
                temp_guard_max_rate = float(temp_guard_max_rate)
            except Exception:
                temp_guard_max_rate = None

        # Optional provider-based phase enthalpies at current tray conditions.
        # This removes a large inconsistency when include_temperature=True and a
        # thermo provider is active, but inputs.thermo is a simple Cp model.
        hL_stage_provider = None
        hV_stage_provider = None
        if inputs.thermo_provider is not None:
            packet_phase_tol_liq = _phase_reuse_dx_tol(inputs, "liquid")
            packet_phase_tol_vap = _phase_reuse_dx_tol(inputs, "vapor")
            packet_dT_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dT_F", 0.0) or 0.0)
            packet_dP_tol = float(getattr(inputs, "thermo_packet_phase_reuse_dP_psia", 0.0) or 0.0)
            temp_refresh = refresh_temperature_state_phase_enthalpies(
                provider=inputs.thermo_provider,
                thermo_packet=thermo_packet,
                previous_packet=inputs.tray_thermo_prev,
                energy_vapor_flow_packet=energy_vapor_flow_packet,
                tray_T_F=tray_T,
                P_tray_psia=P_tray,
                x_tray=x_tray,
                y_tray=y_tray,
                n_stages=N,
                n_components=Nc,
                packet_phase_tol_liq=packet_phase_tol_liq,
                packet_phase_tol_vap=packet_phase_tol_vap,
                packet_dT_tol_F=packet_dT_tol,
                packet_dP_tol_psia=packet_dP_tol,
                packet_phase_enthalpy_first_match_fn=_packet_phase_enthalpy_first_match,
                packet_phase_enthalpy_if_compatible_fn=_packet_phase_enthalpy_if_compatible,
                flash_stage_fn=_flash_TP_full_stage_F_psia,
                trace_fn=_trace_stage_thermo,
                trace_context=inputs,
            )
            hL_stage_provider = temp_refresh.hL_stage_provider
            hV_stage_provider = temp_refresh.hV_stage_provider

        for i in range(N):
            _trace_stage_thermo(inputs, f"temperature_state tray_loop stage={int(i + 1)}/{int(N)} start")
            # No-holdup reboiler stage has no tray energy state to integrate.
            # Keep the tray-T state bounded by relaxing it to reboiler flash temperature.
            if reboiler_no_holdup and i == (N - 1):
                if "T_reb" in locals() and T_reb is not None:
                    tau_reb_T_sec = 1.0
                    dT_tray[i] = (float(T_reb) - float(tray_T[i])) / max(tau_reb_T_sec, 1e-6)
                else:
                    dT_tray[i] = 0.0
                _trace_stage_thermo(inputs, f"temperature_state tray_loop stage={int(i + 1)}/{int(N)} done")
                continue

            # Stage 1 condenser-transfer temperature closure:
            # with a separate reflux drum, stage 1 acts as a small condenser
            # transfer node rather than a true tray. Keep its temperature
            # slaved to the condenser bubble point instead of integrating a
            # raw dE/C ODE on a nearly massless state.
            if (
                i == 0
                and layout.include_top
                and T_cond_bubble_F is not None
                and np.isfinite(float(T_cond_bubble_F))
            ):
                tau_cond_T_sec = 1.0
                dT_tray[i] = (float(T_cond_bubble_F) - float(tray_T[i])) / max(tau_cond_T_sec, 1e-6)
                _trace_stage_thermo(inputs, f"temperature_state tray_loop stage={int(i + 1)}/{int(N)} done")
                continue

            T_L_in = tray_T[i - 1] if i > 0 else tray_T[i]
            if i == N - 1:
                if "T_reb" in locals() and T_reb is not None:
                    T_V_in = float(T_reb)
                else:
                    T_V_in = bot_T if bot_T is not None else tray_T[i]
            else:
                T_V_in = tray_T[i + 1] if i < N - 1 else tray_T[i]

            hL_in = None
            if hL_stage_provider is not None:
                src_i = i if i == 0 else (i - 1)
                if 0 <= src_i < N and np.isfinite(hL_stage_provider[src_i]):
                    hL_in = float(hL_stage_provider[src_i])
            if hL_in is None:
                hL_in = float(thermo.h_liq_btu_per_lbmol(T_L_in, P_tray[i], x_in[i, :]))

            hV_in = None
            if hV_stage_provider is not None:
                src_i = i if i == (N - 1) else (i + 1)
                if 0 <= src_i < N and np.isfinite(hV_stage_provider[src_i]):
                    hV_in = float(hV_stage_provider[src_i])
            if hV_in is None:
                hV_in = float(thermo.h_vap_btu_per_lbmol(T_V_in, P_tray[i], y_in[i, :]))

            hL_out = None
            if hL_stage_provider is not None and np.isfinite(hL_stage_provider[i]):
                hL_out = float(hL_stage_provider[i])
            if hL_out is None:
                hL_out = float(thermo.h_liq_btu_per_lbmol(tray_T[i], P_tray[i], x_tray[i, :]))

            hV_out = None
            if hV_stage_provider is not None and np.isfinite(hV_stage_provider[i]):
                hV_out = float(hV_stage_provider[i])
            if hV_out is None:
                hV_out = float(thermo.h_vap_btu_per_lbmol(tray_T[i], P_tray[i], y_tray[i, :]))

            q_feed = _feed_enthalpy_rate_btu_per_s(
                feed_stage0=feed_stage0,
                stage0=i,
                col=col,
                Nc=Nc,
                Fk_L=Fk_L,
                Fk_V=Fk_V,
                T_stage_F=float(tray_T[i]),
                P_stage_psia=float(P_tray[i]),
                thermo=thermo,
                thermo_provider=inputs.thermo_provider,
                epsilon_lbmol=float(layout.epsilon_lbmol),
                feed_stage_flash_prev=inputs.feed_stage_flash_prev,
                feed_stage_flash_reuse_dT_F=float(inputs.feed_stage_flash_reuse_dT_F),
                feed_stage_flash_reuse_dP_psia=float(inputs.feed_stage_flash_reuse_dP_psia),
                feed_stage_flash_reuse_dx=float(inputs.feed_stage_flash_reuse_dx),
            )
            psi_phase = 0.0
            if "eq_phase_change_lbmolps_tray" in diag:
                try:
                    psi_phase = float(np.asarray(diag["eq_phase_change_lbmolps_tray"], dtype=float).reshape((N,))[i])
                    if not np.isfinite(psi_phase):
                        psi_phase = 0.0
                except Exception:
                    psi_phase = 0.0
            q_phase_latent = float(psi_phase) * float(hV_out - hL_out)

            if i == 0 and layout.include_top:
                # Condenser/top-drum temperature closure:
                # use a reference-invariant form with h_ref = hL_out so
                # liquid outflows at tray temperature do not spuriously
                # drive dT when only holdup changes.
                h_ref = hL_out
                Ft_feed_i = (Ft_L + Ft_V) if (feed_stage0 == i) else 0.0
                dE = (
                    L_in[i] * (hL_in - h_ref)
                    + V_in[i] * (hV_in - h_ref)
                    + q_feed
                    - Ft_feed_i * h_ref
                    - L_out[i] * (hL_out - h_ref)
                    - V_out[i] * (hV_out - h_ref)
                )

                # If a non-total condenser stream withdraws overhead vapor,
                # account for vapor draw enthalpy relative to h_ref.
                if D.total_V > 0.0:
                    hV_top = float(hV_out)
                    dE -= float(D.total_V) * (hV_top - h_ref)
            else:
                dE = (
                    L_in[i] * hL_in
                    + V_in[i] * hV_in
                    + q_feed
                    - L_out[i] * hL_out
                    - V_out[i] * hV_out
                )
            if i == 0:
                dE += float(Qc_BTUph) / 3600.0
            if i == (N - 1):
                dE += float(Qr_BTUph) / 3600.0
                q_phase_latent_tray[i] = float(q_phase_latent)

            if use_provider_cp:
                packet_phase_tol_liq = _phase_reuse_dx_tol(inputs, "liquid")
                packet_phase_tol_vap = _phase_reuse_dx_tol(inputs, "vapor")
                cpL = _packet_phase_cp_from_packets(
                    thermo_packet,
                    inputs.tray_thermo_prev,
                    stage_index0=i,
                    phase="liquid",
                    max_abs_dx=packet_phase_tol_liq,
                    max_abs_dP_psia=packet_dP_tol,
                    min_abs_dT_F=0.1,
                )
                cpV = _packet_phase_cp_from_packets(
                    thermo_packet,
                    inputs.tray_thermo_prev,
                    stage_index0=i,
                    phase="vapor",
                    max_abs_dx=packet_phase_tol_vap,
                    max_abs_dP_psia=packet_dP_tol,
                    min_abs_dT_F=0.1,
                )
                if cpL is None and hL_stage_provider is not None and np.isfinite(hL_stage_provider[i]):
                    cpL = _phase_cp_from_current_enthalpy_and_packet(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        current_enthalpy_btu_per_lbmol=float(hL_stage_provider[i]),
                        current_T_F=float(tray_T[i]),
                        current_P_psia=float(P_tray[i]),
                        current_phase_composition=x_tray[i, :],
                        phase="liquid",
                        max_abs_dx=packet_phase_tol_liq,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                if cpV is None and hV_stage_provider is not None and np.isfinite(hV_stage_provider[i]):
                    cpV = _phase_cp_from_current_enthalpy_and_packet(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        current_enthalpy_btu_per_lbmol=float(hV_stage_provider[i]),
                        current_T_F=float(tray_T[i]),
                        current_P_psia=float(P_tray[i]),
                        current_phase_composition=y_tray[i, :],
                        phase="vapor",
                        max_abs_dx=packet_phase_tol_vap,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                z_for_cp = tray_L[i, :].copy()
                if tray_V is not None:
                    z_for_cp = z_for_cp + tray_V[i, :]
                s = float(np.sum(z_for_cp))
                if s <= layout.epsilon_lbmol:
                    z_for_cp = x_tray[i, :].copy()
                    s = float(np.sum(z_for_cp))
                z_for_cp = z_for_cp / max(s, 1e-300)
                if cpL is None:
                    cpL = _packet_cp_if_compatible(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        T_F=float(tray_T[i]),
                        P_psia=float(P_tray[i]),
                        z_overall=z_for_cp,
                        phase="liquid",
                        max_abs_dx=packet_dx_tol,
                        max_abs_dT_F=packet_dT_tol,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                if cpV is None:
                    cpV = _packet_cp_if_compatible(
                        inputs.tray_thermo_prev,
                        stage_index0=i,
                        T_F=float(tray_T[i]),
                        P_psia=float(P_tray[i]),
                        z_overall=z_for_cp,
                        phase="vapor",
                        max_abs_dx=packet_dx_tol,
                        max_abs_dT_F=packet_dT_tol,
                        max_abs_dP_psia=packet_dP_tol,
                    )
                if cpL is None or cpV is None:
                    try:
                        cpL, cpV = _provider_cp_liq_vap_btu_per_lbmolF(
                            inputs.thermo_provider,
                            tray_T[i],
                            P_tray[i],
                            z_for_cp,
                            thermo_call_category="temperature_state_cp_lookup",
                        )
                    except Exception:
                        cpL = cpV = None
            else:
                cpL = cpV = None

            if cpL is None or cpV is None:
                cpL = thermo.cp_liq_btu_per_lbmolF(tray_T[i], P_tray[i], x_tray[i, :])
                cpV = thermo.cp_vap_btu_per_lbmolF(tray_T[i], P_tray[i], y_tray[i, :])

            C = diag["ML_tot_tray"][i] * cpL + diag["MV_tot_tray"][i] * cpV
            tray_heat_capacity_BTU_per_F[i] = float(C)
            if C <= 0.0 and (diag["ML_tot_tray"][i] + diag["MV_tot_tray"][i]) <= layout.epsilon_lbmol:
                dT_tray[i] = 0.0
                tray_effective_heat_capacity_BTU_per_F[i] = float(max(C, 0.0))
                _trace_stage_thermo(inputs, f"temperature_state tray_loop stage={int(i + 1)}/{int(N)} done")
                continue

            dT_raw = float(dE / max(C, 1.0e-12))
            dT_energy_raw_tray[i] = float(dT_raw)
            dT_phase_latent_equiv_tray[i] = float(q_phase_latent / max(C, 1.0e-12))
            dT_val, C_eff, guard_active = _stabilize_low_holdup_temperature_rate(
                dE_BTU_per_s=float(dE),
                heat_capacity_BTU_per_F=float(C),
                liquid_holdup_lbmol=float(diag["ML_tot_tray"][i]),
                vapor_holdup_lbmol=float(diag["MV_tot_tray"][i]),
                holdup_guard_lbmol=float(temp_guard_holdup),
                min_heat_capacity_BTU_per_F=float(temp_guard_min_C),
                max_abs_rate_F_per_s=temp_guard_max_rate,
            )
            tray_effective_heat_capacity_BTU_per_F[i] = float(C_eff)
            tray_temperature_guard_active[i] = float(guard_active)
            if (
                bool(guard_active)
                and temp_guard_max_rate is not None
                and np.isfinite(float(temp_guard_max_rate))
                and float(temp_guard_max_rate) > 0.0
            ):
                tray_temperature_rate_limit_F_per_s[i] = float(temp_guard_max_rate)
            if hyd_energy_mode and temp_mode == "bubble-point-follower":
                try:
                    T_target_prev = getattr(inputs, "tray_bubble_target_prev_F", None)
                    if T_target_prev is not None:
                        T_target_prev = np.asarray(T_target_prev, dtype=float).reshape((N,))
                        if np.isfinite(float(T_target_prev[i])):
                            T_bubble_target[i] = float(T_target_prev[i])
                    if np.isfinite(T_bubble_target[i]):
                        tau_T = float(getattr(inputs, "hydraulic_energy_temperature_follow_tau_sec", 0.5) or 0.5)
                        if (not np.isfinite(tau_T)) or tau_T <= 0.0:
                            tau_T = 0.5
                        resid_frac = float(getattr(inputs, "hydraulic_energy_temperature_resid_frac", 0.01) or 0.01)
                        if (not np.isfinite(resid_frac)) or resid_frac < 0.0:
                            resid_frac = 0.01
                        dT_new = (float(T_bubble_target[i]) - float(tray_T[i])) / tau_T + resid_frac * float(dE / C)
                        dT_mode_correction_tray[i] = float(dT_new - dT_energy_raw_tray[i])
                        dT_val = dT_new
                except Exception:
                    pass
            elif hyd_energy_mode and temp_mode == "enthalpy-state-follower":
                try:
                    tau_T = float(getattr(inputs, "hydraulic_energy_temperature_follow_tau_sec", 0.5) or 0.5)
                    if (not np.isfinite(tau_T)) or tau_T <= 0.0:
                        tau_T = 0.5
                    resid_frac = float(getattr(inputs, "hydraulic_energy_temperature_resid_frac", 0.0) or 0.0)
                    if (not np.isfinite(resid_frac)) or resid_frac < 0.0:
                        resid_frac = 0.0
                    if bool(getattr(layout, "include_energy", False)):
                        if "EL" in locals():
                            E_enthalpy_state_mismatch[i] = float(EL[i]) - (
                                float(diag["ML_tot_tray"][i]) * float(hL_out)
                            )
                        T_target = _tray_temperature_target_from_liquid_energy_state_F(
                            T_now_F=float(tray_T[i]),
                            ML_tot_lbmol=float(diag["ML_tot_tray"][i]),
                            EL_BTU=float(EL[i]) if "EL" in locals() else None,
                            hL_BTU_lbmol=float(hL_out),
                            cpL_BTU_lbmolF=float(cpL),
                        )
                        if T_target is not None and np.isfinite(float(T_target)):
                            T_enthalpy_state_target[i] = float(T_target)
                            dT_new = (float(T_target) - float(tray_T[i])) / float(tau_T)
                            dT_new = float(np.clip(dT_new, -5.0, 5.0))
                            T_enthalpy_state_correction[i] = float(dT_new)
                            if resid_frac > 0.0:
                                dT_new += float(resid_frac) * float(dE / C)
                            dT_mode_correction_tray[i] = float(dT_new - dT_energy_raw_tray[i])
                            dT_val = dT_new
                except Exception:
                    pass
            elif hyd_energy_mode and temp_mode == "pressure-correction-follower":
                try:
                    tau_T = float(getattr(inputs, "hydraulic_energy_temperature_follow_tau_sec", 0.5) or 0.5)
                    if (not np.isfinite(tau_T)) or tau_T <= 0.0:
                        tau_T = 0.5
                    resid_alpha = float(getattr(inputs, "hydraulic_energy_temperature_damping", 0.1) or 0.1)
                    if (not np.isfinite(resid_alpha)) or resid_alpha < 0.0:
                        resid_alpha = 0.1
                    dT_new = float(resid_alpha) * float(dE / C)
                    p_slope = float(
                        getattr(inputs, "hydraulic_energy_temperature_pressure_slope_F_per_psi", 2.0) or 2.0
                    )
                    p_slope_vec = getattr(inputs, "tray_temp_pressure_slope_prev_F_per_psi", None)
                    if p_slope_vec is not None:
                        try:
                            p_slope_arr = np.asarray(p_slope_vec, dtype=float).reshape((N,))
                            if np.isfinite(float(p_slope_arr[i])):
                                p_slope = float(p_slope_arr[i])
                        except Exception:
                            pass
                    T_pressure_slope_used[i] = float(p_slope)
                    if np.isfinite(p_slope) and abs(float(p_slope)) > 0.0 and inputs.P_tray_prev is not None:
                        P_prev_arr = np.asarray(inputs.P_tray_prev, dtype=float).reshape((N,))
                        if np.isfinite(float(P_prev_arr[i])) and np.isfinite(float(P_tray[i])):
                            dP_term = float(p_slope) * (float(P_tray[i]) - float(P_prev_arr[i])) / float(tau_T)
                            T_pressure_correction[i] = float(dP_term)
                            dT_new += float(dP_term)
                    dT_mode_correction_tray[i] = float(dT_new - dT_energy_raw_tray[i])
                    dT_val = dT_new
                except Exception:
                    pass
            elif hyd_energy_mode:
                try:
                    temp_damping = float(getattr(inputs, "hydraulic_energy_temperature_damping", 1.0) or 1.0)
                except Exception:
                    temp_damping = 1.0
                if (not np.isfinite(temp_damping)) or temp_damping < 0.0:
                    temp_damping = 1.0
                dT_new = dT_val * float(temp_damping)
                dT_mode_correction_tray[i] = float(dT_new - dT_energy_raw_tray[i])
                dT_val = dT_new
            dT_tray[i] = dT_val
            _trace_stage_thermo(inputs, f"temperature_state tray_loop stage={int(i + 1)}/{int(N)} done")

        dydt[sl["tray_T_f"]] = dT_tray
        diag["dT_tray_F_per_s"] = dT_tray.copy()
        diag["Q_phase_relax_latent_BTUps_tray"] = q_phase_latent_tray.copy()
        diag["dT_energy_raw_F_per_s_tray"] = dT_energy_raw_tray.copy()
        diag["dT_mode_correction_F_per_s_tray"] = dT_mode_correction_tray.copy()
        diag["dT_phase_latent_equiv_F_per_s_tray"] = dT_phase_latent_equiv_tray.copy()
        diag["tray_heat_capacity_BTU_per_F_tray"] = tray_heat_capacity_BTU_per_F.copy()
        diag["tray_effective_heat_capacity_BTU_per_F_tray"] = tray_effective_heat_capacity_BTU_per_F.copy()
        diag["tray_temperature_guard_active_tray"] = tray_temperature_guard_active.copy()
        diag["tray_temperature_rate_limit_F_per_s_tray"] = tray_temperature_rate_limit_F_per_s.copy()
        diag["T_bubble_target_F_tray"] = T_bubble_target.copy()
        diag["T_enthalpy_state_target_F_tray"] = T_enthalpy_state_target.copy()
        diag["E_enthalpy_state_mismatch_BTU_tray"] = E_enthalpy_state_mismatch.copy()
        diag["T_enthalpy_state_correction_F_per_s_tray"] = T_enthalpy_state_correction.copy()
        diag["T_pressure_correction_F_per_s_tray"] = T_pressure_correction.copy()
        diag["T_pressure_slope_used_F_per_psi_tray"] = T_pressure_slope_used.copy()
        _trace_stage_thermo(inputs, "temperature_state tray diagnostics complete")

        # Bottom sump temperature (separate from reboiler temperature)
        if layout.include_bottom and ("bottom_T_f" in sl) and (bottom_L is not None):
            M_sump = float(np.sum(bottom_L))
            if M_sump > 0.0:
                T_sump_use = bot_T if bot_T is not None else float(tray_T[-1])
                P_bot = float(P_tray[-1])
                x_sump = x_botL

                h_in = thermo.h_liq_btu_per_lbmol(float(tray_T[-1]), P_bot, x_tray[-1, :])
                h_sump = thermo.h_liq_btu_per_lbmol(float(T_sump_use), P_bot, x_sump)
                if use_provider_cp:
                    cp_sump = None
                    sump_cp_packet, sump_cp_dT, sump_cp_dP, sump_cp_dx = _compatible_bottom_sump_cp_packet(
                        getattr(inputs, "bottom_sump_cp_prev", None),
                        T_sump_F=float(T_sump_use),
                        P_sump_psia=P_bot,
                        x_sump=x_sump,
                        n_components=Nc,
                        max_abs_dT_F=float(getattr(inputs, "bottom_sump_cp_reuse_dT_F", 0.5) or 0.5),
                        max_abs_dP_psia=float(getattr(inputs, "bottom_sump_cp_reuse_dP_psia", 5.0) or 5.0),
                        max_abs_dx=float(getattr(inputs, "bottom_sump_cp_reuse_dx", 1.0e-5) or 1.0e-5),
                    )
                    if sump_cp_packet is not None:
                        cp_sump = float(sump_cp_packet.cpL_BTU_lbmolF)
                        _trace_stage_thermo(
                            inputs,
                            "bottom_sump_cp reused packet "
                            f"dT={float(sump_cp_dT):.3g}F "
                            f"dP={float(sump_cp_dP):.3g}psi "
                            f"dx_max={float(sump_cp_dx):.3g}",
                        )
                    try:
                        if cp_sump is None:
                            cp_sump, _cpv = _provider_cp_liq_vap_btu_per_lbmolF(
                                inputs.thermo_provider,
                                float(T_sump_use),
                                P_bot,
                                x_sump,
                                thermo_call_category="bottom_sump_cp_lookup",
                            )
                    except Exception:
                        cp_sump = None
                else:
                    cp_sump = None
                if cp_sump is None:
                    cp_sump = thermo.cp_liq_btu_per_lbmolF(float(T_sump_use), P_bot, x_sump)
                elif np.isfinite(float(cp_sump)):
                    diag["bottom_sump_cp_cache_T_F"] = np.array([float(T_sump_use)], dtype=float)
                    diag["bottom_sump_cp_cache_P_psia"] = np.array([float(P_bot)], dtype=float)
                    diag["bottom_sump_cp_cache_x"] = np.asarray(x_sump, dtype=float).reshape((Nc,)).copy()
                    diag["bottom_sump_cp_cache_cpL_BTU_lbmolF"] = np.array([float(cp_sump)], dtype=float)

                dE_sump = 0.0
                dE_sump += float(L_out[-1]) * h_in
                dE_sump -= float(B.total_L) * h_sump
                if reboiler_feed_from_sump:
                    dE_sump -= float(boilup_s) * h_sump

                C = max(M_sump * cp_sump, 1e-12)
                dT_sump = dE_sump / C

                # Optional bubble-point relaxation for sump temperature.
                # Do not apply this when using the no-holdup reboiler mode:
                # in that configuration, the sump is a separate liquid inventory
                # and should evolve from its own energy balance with incoming
                # reboiler liquid, not be forced to an equilibrium bubble-point.
                if inputs.thermo_provider is not None and (not reboiler_no_holdup):
                    try:
                        T_eq, _ = _bubble_point_T_F(
                            thermo_provider=inputs.thermo_provider,
                            P_psia=P_bot,
                            x=x_sump,
                            T_guess_F=T_sump_use,
                            thermo_call_category="temperature_state_bubble_point_helper_flash",
                        )
                        tau_sump = 1.0  # seconds, fast relaxation toward equilibrium
                        dT_sump = (float(T_eq) - float(T_sump_use)) / max(tau_sump, 1e-6)
                    except Exception:
                        pass
            else:
                dT_sump = 0.0

            dydt[sl["bottom_T_f"]] = dT_sump
            diag["dT_sump_F_per_s"] = float(dT_sump)
            _trace_stage_thermo(inputs, "temperature_state bottom sump update complete")

    _trace_stage_thermo(inputs, "column_rhs return")
    return dydt, diag


# ---------------------------
# Helpers
# ---------------------------

@dataclass(frozen=True)
class Draw:
    total_L: float
    total_V: float
    comp_L: np.ndarray
    comp_V: np.ndarray
    has_component_breakdown: bool


def _norm_comp_key(name: Any) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _component_molar_flows_vector_lbmolps(
    comp_map: Dict[str, Any],
    component_names_excel: np.ndarray,
) -> np.ndarray:
    """
    Convert a component-flow mapping (lbmol/h) to an ordered vector (lbmol/s),
    matching component names case/format-insensitively.
    """
    norm_map: Dict[str, float] = {}
    for k, v in (comp_map or {}).items():
        try:
            norm_map[_norm_comp_key(k)] = float(v)
        except Exception:
            continue

    Nc = int(len(component_names_excel))
    out = np.zeros(Nc, dtype=float)
    for i, cname in enumerate(component_names_excel):
        v = norm_map.get(_norm_comp_key(cname))
        out[i] = 0.0 if v is None else (float(v) / 3600.0)
    return out


def _draw_from_stream(col: ColumnSpec, stream_name: str, Nc: int) -> Draw:
    streams = getattr(col, "streams", {}) or {}

    def _norm_key(s: str) -> str:
        return "".join(ch for ch in str(s).lower() if ch.isalnum())

    def _pick(names: list[str]):
        for nm in names:
            if nm in streams:
                return streams.get(nm)
        # fallback: normalized match
        targets = {_norm_key(nm) for nm in names}
        for k, v in streams.items():
            if _norm_key(k) in targets:
                return v
        return None

    key = _norm_key(stream_name)
    if key in ("top", "distillate", "overhead"):
        s = _pick(["Distillate", "Top", "Overhead", "Dist"])
    elif key in ("bottom", "bottoms", "bot"):
        s = _pick(["Bottoms", "Bottom", "Bot"])
    else:
        s = streams.get(stream_name)

    if s is None or s.total_molar_flow_lbmolph is None:
        return Draw(0.0, 0.0, np.zeros(Nc), np.zeros(Nc), False)

    vf = float(s.vapor_fraction) if s.vapor_fraction is not None else 0.0
    vf = float(np.clip(vf, 0.0, 1.0))

    total = float(s.total_molar_flow_lbmolph) / 3600.0
    total_L = (1.0 - vf) * total
    total_V = vf * total

    if s.component_molar_flows_lbmolph:
        comp = _component_molar_flows_vector_lbmolps(
            s.component_molar_flows_lbmolph,
            col.components_excel,
        )
        comp_L = (1.0 - vf) * comp
        comp_V = vf * comp
        return Draw(total_L, total_V, comp_L, comp_V, True)

    return Draw(total_L, total_V, np.zeros(Nc), np.zeros(Nc), False)


def _override_draw_total_lbmolph(
    draw: Draw,
    total_lbmolph: Optional[float],
    *,
    prefer_liquid: bool = True,
) -> Draw:
    """
    Override total product draw while preserving existing phase split/composition.
    """
    if total_lbmolph is None:
        return draw
    try:
        total_s = float(total_lbmolph) / 3600.0
    except Exception:
        return draw
    if (not np.isfinite(total_s)) or total_s < 0.0:
        return draw

    old_total = float(draw.total_L + draw.total_V)
    if old_total > 1e-300:
        frac_v = float(draw.total_V) / old_total
    else:
        frac_v = 0.0 if prefer_liquid else 1.0
    frac_v = float(np.clip(frac_v, 0.0, 1.0))
    frac_l = 1.0 - frac_v

    new_total_L = float(total_s) * frac_l
    new_total_V = float(total_s) * frac_v

    if draw.has_component_breakdown:
        compL = np.asarray(draw.comp_L, dtype=float).copy()
        compV = np.asarray(draw.comp_V, dtype=float).copy()
        oldL = float(np.sum(compL))
        oldV = float(np.sum(compV))
        if oldL > 1e-300:
            compL = compL * (new_total_L / oldL)
        else:
            compL[:] = 0.0
        if oldV > 1e-300:
            compV = compV * (new_total_V / oldV)
        else:
            compV[:] = 0.0
        return Draw(new_total_L, new_total_V, compL, compV, True)

    return Draw(new_total_L, new_total_V, draw.comp_L, draw.comp_V, False)


def _scale_draw(draw: Draw, scale: float) -> Draw:
    try:
        s = float(scale)
    except Exception:
        s = 1.0
    if not np.isfinite(s):
        s = 1.0
    s = max(float(s), 0.0)
    return Draw(
        float(draw.total_L) * s,
        float(draw.total_V) * s,
        np.asarray(draw.comp_L, dtype=float) * s,
        np.asarray(draw.comp_V, dtype=float) * s,
        bool(draw.has_component_breakdown),
    )


def _safe_comp_from_holdup(holdup: Optional[np.ndarray], fallback: np.ndarray, eps: float) -> np.ndarray:
    if holdup is None:
        return np.asarray(fallback, dtype=float).copy()
    h = np.asarray(holdup, dtype=float).copy()
    tot = float(np.sum(h))
    if tot <= eps:
        return np.asarray(fallback, dtype=float).copy()
    return h / tot


def _feed_component_rates_lbmolps(
    col: ColumnSpec,
    Nc: int,
    thermo_provider: Optional[Any] = None,
    P_tray_psia: Optional[np.ndarray] = None,
    flash_feed_at_stage_conditions: bool = True,
    feed_stage_flash_prev: Optional[FeedStageFlashPacket] = None,
    feed_stage_flash_reuse_dT_F: float = 0.5,
    feed_stage_flash_reuse_dP_psia: float = 2.5,
    feed_stage_flash_reuse_dx: float = 1.0e-6,
    trace_hook: Optional[Any] = None,
    trace_label: Optional[str] = None,
) -> Tuple[Optional[int], np.ndarray, np.ndarray]:
    s = col.streams.get("Feed")
    if s is None or s.stage_1based is None or s.total_molar_flow_lbmolph is None:
        return None, np.zeros(Nc), np.zeros(Nc)

    stage0 = int(s.stage_1based) - 1
    Ft = float(s.total_molar_flow_lbmolph) / 3600.0
    vf = float(s.vapor_fraction) if s.vapor_fraction is not None else 0.0
    vf = float(np.clip(vf, 0.0, 1.0))

    if s.component_molar_flows_lbmolph:
        Fk = _component_molar_flows_vector_lbmolps(
            s.component_molar_flows_lbmolph,
            col.components_excel,
        )
    else:
        z = np.asarray(col.x0[stage0, :], dtype=float).copy()
        z = z / max(float(np.sum(z)), 1e-300)
        Fk = Ft * z

    # Optional: split feed via TP flash at feed-stage pressure for a more realistic
    # on-tray feed phase split than a fixed stream vapor fraction.
    if (
        flash_feed_at_stage_conditions
        and (thermo_provider is not None)
        and (getattr(s, "temperature_f", None) is not None)
        and np.isfinite(float(getattr(s, "temperature_f")))
    ):
        try:
            if P_tray_psia is not None:
                P_arr = np.asarray(P_tray_psia, dtype=float).reshape((-1,))
                if 0 <= stage0 < P_arr.size and np.isfinite(P_arr[stage0]) and P_arr[stage0] > 0.0:
                    P_feed = float(P_arr[stage0])
                else:
                    P_feed = None
            else:
                P_feed = None

            if P_feed is None:
                if hasattr(col, "P_psia"):
                    P_arr = np.asarray(col.P_psia, dtype=float).reshape((-1,))
                    if 0 <= stage0 < P_arr.size and np.isfinite(P_arr[stage0]) and P_arr[stage0] > 0.0:
                        P_feed = float(P_arr[stage0])
                    else:
                        P_feed = 200.0
                else:
                    P_feed = 200.0

            Ft_comp = float(np.sum(Fk))
            if np.isfinite(Ft_comp) and Ft_comp > 1e-300:
                z_feed = Fk / Ft_comp
                T_feed = float(getattr(s, "temperature_f"))
                matched_packet, dT_feed, dP_feed, dx_max = _compatible_feed_stage_flash_packet(
                    packet=feed_stage_flash_prev,
                    stage0=int(stage0),
                    T_feed_F=float(T_feed),
                    P_feed_psia=float(P_feed),
                    z_feed=z_feed,
                    n_components=Nc,
                    max_abs_dT_F=float(feed_stage_flash_reuse_dT_F),
                    max_abs_dP_psia=float(feed_stage_flash_reuse_dP_psia),
                    max_abs_dx=float(feed_stage_flash_reuse_dx),
                )
                if feed_stage_flash_prev is not None and int(getattr(feed_stage_flash_prev, "stage0", -999999)) == int(stage0):
                    try:
                        if matched_packet is not None:
                            L_prev = np.asarray(matched_packet.Fk_L_lbmolps, dtype=float).reshape((Nc,))
                            V_prev = np.asarray(matched_packet.Fk_V_lbmolps, dtype=float).reshape((Nc,))
                            if callable(trace_hook):
                                prefix = (
                                    f"[ThermoTrace][{str(trace_label).strip()}] "
                                    if str(trace_label or "").strip()
                                    else "[ThermoTrace] "
                                )
                                try:
                                    trace_hook(
                                        prefix
                                        + "feed_stage_flash reused previous packet "
                                        + f"stage={int(stage0)+1} "
                                        + f"dT_F={float(dT_feed or 0.0):.6g} "
                                        + f"dP_psia={float(dP_feed or 0.0):.6g} "
                                        + f"dx_max={float(dx_max or 0.0):.6g}"
                                    )
                                except Exception:
                                    pass
                            return stage0, L_prev.copy(), V_prev.copy()
                        if callable(trace_hook):
                            prefix = (
                                f"[ThermoTrace][{str(trace_label).strip()}] "
                                if str(trace_label or "").strip()
                                else "[ThermoTrace] "
                            )
                            try:
                                trace_hook(
                                    prefix
                                    + "feed_stage_flash cache miss "
                                    + f"stage={int(stage0)+1} "
                                    + f"dT_F={float(dT_feed or 0.0):.6g} "
                                    + f"dP_psia={float(dP_feed or 0.0):.6g} "
                                    + f"dx_max={float(dx_max or 0.0):.6g}"
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
                with _thermo_provider_category(thermo_provider, "feed_stage_flash"):
                    fres = flash_TP_full_F_psia(
                        thermo_provider,
                        T_feed,
                        float(P_feed),
                        z_feed,
                        n_components=Nc,
                    )
                K = np.asarray(fres.K, dtype=float).reshape((Nc,))
                beta = _rachford_rice_beta(K, z_feed)
                beta = float(np.clip(beta, 0.0, 1.0))

                denom = 1.0 + beta * (K - 1.0)
                denom = np.where(np.abs(denom) < 1e-12, np.sign(denom) * 1e-12 + (denom == 0) * 1e-12, denom)
                x = np.clip(z_feed / denom, 0.0, None)
                sx = float(np.sum(x))
                if not np.isfinite(sx) or sx <= 1e-300:
                    x = z_feed.copy()
                else:
                    x = x / sx
                y = np.clip(K * x, 0.0, None)
                sy = float(np.sum(y))
                if not np.isfinite(sy) or sy <= 1e-300:
                    y = z_feed.copy()
                else:
                    y = y / sy

                return stage0, (1.0 - beta) * Ft_comp * x, beta * Ft_comp * y
        except Exception:
            pass

    return stage0, (1.0 - vf) * Fk, vf * Fk


def _safe_feed_comp(col: ColumnSpec, stage0: int) -> np.ndarray:
    return np.asarray(col.x0[stage0, :], dtype=float).copy()


def _feed_enthalpy_rate_btu_per_s(
    *,
    feed_stage0: Optional[int],
    stage0: int,
    col: ColumnSpec,
    Nc: int,
    Fk_L: np.ndarray,
    Fk_V: np.ndarray,
    T_stage_F: float,
    P_stage_psia: float,
    thermo: Any,
    thermo_provider: Optional[Any],
    epsilon_lbmol: float,
    feed_stage_flash_prev: Optional[FeedStageFlashPacket] = None,
    feed_stage_flash_reuse_dT_F: float = 0.5,
    feed_stage_flash_reuse_dP_psia: float = 2.5,
    feed_stage_flash_reuse_dx: float = 1.0e-6,
) -> float:
    """
    Feed enthalpy source term (BTU/s) for stage energy balances.

    Uses the *actual* feed phase split vectors (Fk_L/Fk_V). If a thermo provider
    is available, enthalpies are taken from a TP flash at stage pressure using
    the overall feed composition implied by Fk_L + Fk_V.
    """
    if feed_stage0 != stage0:
        return 0.0

    FL = float(np.sum(Fk_L))
    FV = float(np.sum(Fk_V))
    Ft = FL + FV
    if (not np.isfinite(Ft)) or Ft <= float(epsilon_lbmol):
        return 0.0

    FkL = np.asarray(Fk_L, dtype=float).reshape((Nc,))
    FkV = np.asarray(Fk_V, dtype=float).reshape((Nc,))
    z_feed = np.clip(FkL + FkV, 0.0, None)
    sz = float(np.sum(z_feed))
    if not np.isfinite(sz) or sz <= float(epsilon_lbmol):
        z_feed = np.full(Nc, 1.0 / max(Nc, 1), dtype=float)
    else:
        z_feed = z_feed / sz

    if FL > float(epsilon_lbmol):
        x_feed = np.clip(FkL, 0.0, None)
        sx = float(np.sum(x_feed))
        x_feed = x_feed / max(sx, float(epsilon_lbmol))
    else:
        x_feed = z_feed.copy()

    if FV > float(epsilon_lbmol):
        y_feed = np.clip(FkV, 0.0, None)
        sy = float(np.sum(y_feed))
        y_feed = y_feed / max(sy, float(epsilon_lbmol))
    else:
        y_feed = z_feed.copy()

    sF = col.streams.get("Feed")
    T_feed = float(T_stage_F)
    if sF is not None and getattr(sF, "temperature_f", None) is not None:
        try:
            T_feed = float(getattr(sF, "temperature_f"))
        except Exception:
            pass
    P_feed = float(P_stage_psia) if np.isfinite(float(P_stage_psia)) and float(P_stage_psia) > 0.0 else 200.0

    hF_L = None
    hF_V = None
    matched_packet, _dT_feed, _dP_feed, _dx_feed = _compatible_feed_stage_flash_packet(
        packet=feed_stage_flash_prev,
        stage0=int(stage0),
        T_feed_F=float(T_feed),
        P_feed_psia=float(P_feed),
        z_feed=z_feed,
        n_components=Nc,
        max_abs_dT_F=float(feed_stage_flash_reuse_dT_F),
        max_abs_dP_psia=float(feed_stage_flash_reuse_dP_psia),
        max_abs_dx=float(feed_stage_flash_reuse_dx),
    )
    if matched_packet is not None:
        try:
            h_try_L = getattr(matched_packet, "hL_BTU_lbmol", None)
            if h_try_L is not None and np.isfinite(float(h_try_L)):
                hF_L = float(h_try_L)
        except Exception:
            hF_L = None
        try:
            h_try_V = getattr(matched_packet, "hV_BTU_lbmol", None)
            if h_try_V is not None and np.isfinite(float(h_try_V)):
                hF_V = float(h_try_V)
        except Exception:
            hF_V = None
    if thermo_provider is not None:
        try:
            if hF_L is None or hF_V is None:
                with _thermo_provider_category(thermo_provider, "feed_enthalpy_flash"):
                    fres = flash_TP_full_F_psia(
                        thermo_provider,
                        float(T_feed),
                        float(P_feed),
                        z_feed,
                        n_components=Nc,
                    )
                h_try_L = getattr(fres, "HL_BTU_lbmol", None)
                if h_try_L is None:
                    h_try_L = getattr(fres, "HL", None)
                h_try_V = getattr(fres, "HV_BTU_lbmol", None)
                if h_try_V is None:
                    h_try_V = getattr(fres, "HV", None)
                if h_try_L is not None and np.isfinite(float(h_try_L)):
                    hF_L = float(h_try_L)
                if h_try_V is not None and np.isfinite(float(h_try_V)):
                    hF_V = float(h_try_V)
        except Exception:
            pass

    if hF_L is None:
        hF_L = float(thermo.h_liq_btu_per_lbmol(float(T_feed), float(P_feed), x_feed))
    if hF_V is None:
        hF_V = float(thermo.h_vap_btu_per_lbmol(float(T_feed), float(P_feed), y_feed))

    return float(FL) * float(hF_L) + float(FV) * float(hF_V)


def _fallback_comp_stage(col: ColumnSpec, stage0: int, Nc: int) -> np.ndarray:
    """Fallback composition for stages with ~zero holdup."""
    try:
        base = np.asarray(col.x0[stage0, :], dtype=float).reshape((Nc,))
    except Exception:
        try:
            base = np.asarray(col.y0[stage0, :], dtype=float).reshape((Nc,))
        except Exception:
            base = np.full(Nc, 1.0 / max(Nc, 1), dtype=float)

    s = float(np.sum(base))
    if not np.isfinite(s) or s <= 0.0:
        return np.full(Nc, 1.0 / max(Nc, 1), dtype=float)
    return base / s


def _infer_condenser_alpha(col: ColumnSpec, inputs: ColumnInputs) -> float:
    if inputs.condenser_alpha is not None:
        return float(inputs.condenser_alpha)

    ctype = (col.duties.condenser_type or "").strip().lower() if hasattr(col, "duties") else ""
    if ctype == "total":
        return 1.0

    s_top = col.streams.get("Top")
    vf_top = float(s_top.vapor_fraction) if (s_top is not None and s_top.vapor_fraction is not None) else 0.0
    vf_top = float(np.clip(vf_top, 0.0, 1.0))

    if ctype == "partial":
        return 1.0 - vf_top

    return 0.95


def _get_reboiler_duty_btu_per_h(col: ColumnSpec) -> float:
    specs = getattr(col, "specs", None) or getattr(col, "specs_raw", None) or {}
    if isinstance(specs, dict):
        if "Reboiler Duty (Btu/h)" in specs and specs["Reboiler Duty (Btu/h)"] is not None:
            try:
                return float(specs["Reboiler Duty (Btu/h)"])
            except Exception:
                pass
    if hasattr(col, "duties"):
        q = getattr(col.duties, "q_reb_btu_per_h", None)
        if q is not None:
            try:
                return float(q)
            except Exception:
                pass
    return 0.0


def _resolve_reboiler_duty_btu_per_h(*, col: ColumnSpec, inputs: ColumnInputs) -> float:
    """
    Resolve reboiler duty (BTU/h) for the current RHS call.

    Priority:
      1) runtime override in ColumnInputs.reboiler_duty_btu_per_h
      2) base case value from ColumnSpec
    Then apply optional runtime trim.
    """
    q_override = getattr(inputs, "reboiler_duty_btu_per_h", None)
    q_trim_raw = getattr(inputs, "reboiler_duty_trim_btu_per_h", None)

    q_base = np.nan
    if q_override is not None:
        try:
            q_try = float(q_override)
            if np.isfinite(q_try):
                q_base = q_try
        except Exception:
            q_base = np.nan
    if not np.isfinite(q_base):
        q_base = float(_get_reboiler_duty_btu_per_h(col))

    q_trim = 0.0
    if q_trim_raw is not None:
        try:
            q_try = float(q_trim_raw)
            if np.isfinite(q_try):
                q_trim = q_try
        except Exception:
            q_trim = 0.0

    q = float(q_base) + float(q_trim)
    if not np.isfinite(q):
        return 0.0
    return float(q)


def _get_condenser_duty_btu_per_h(col: ColumnSpec) -> float:
    specs = getattr(col, "specs", None) or getattr(col, "specs_raw", None) or {}
    if isinstance(specs, dict):
        if "Condenser Duty (Btu/h)" in specs and specs["Condenser Duty (Btu/h)"] is not None:
            try:
                return float(specs["Condenser Duty (Btu/h)"])
            except Exception:
                pass
    if hasattr(col, "duties"):
        q = getattr(col.duties, "q_cond_btu_per_h", None)
        if q is not None:
            try:
                return float(q)
            except Exception:
                pass
    return 0.0


def _normalize_condenser_duty_mode(mode: Optional[str]) -> str:
    s = str(mode or "").strip().lower().replace("_", "-")
    if s in ("", "auto", "total", "total-condense", "total-condensing", "total-condenser"):
        return "total-condense"
    if s in ("specified", "spec", "fixed", "manual"):
        return "specified"
    return "total-condense"


def _condenser_duty_packet_if_compatible(
    packet: Optional[CondenserDutyPacket],
    *,
    mode: str,
    V_vapor_in_lbmolps: float,
    T_vapor_in_F: float,
    P_vapor_in_psia: float,
    P_condenser_psia: float,
    y_vapor_in: np.ndarray,
    max_abs_dT_F: float,
    max_abs_dP_psia: float,
    max_abs_dx: float,
    max_rel_dV: float,
) -> Optional[CondenserDutyPacket]:
    if packet is None:
        return None
    if str(packet.mode).strip().lower() != str(mode).strip().lower():
        return None
    try:
        y_prev = np.asarray(packet.y_vapor_in, dtype=float).reshape((-1,))
        y_curr = np.asarray(y_vapor_in, dtype=float).reshape((-1,))
    except Exception:
        return None
    if y_prev.shape != y_curr.shape:
        return None
    if (
        not np.isfinite(float(packet.V_vapor_in_lbmolps))
        or not np.isfinite(float(packet.T_vapor_in_F))
        or not np.isfinite(float(packet.P_vapor_in_psia))
        or not np.isfinite(float(packet.P_condenser_psia))
    ):
        return None
    if (
        abs(float(T_vapor_in_F) - float(packet.T_vapor_in_F)) > max(float(max_abs_dT_F), 1e-12)
        or abs(float(P_vapor_in_psia) - float(packet.P_vapor_in_psia)) > max(float(max_abs_dP_psia), 1e-12)
        or abs(float(P_condenser_psia) - float(packet.P_condenser_psia)) > max(float(max_abs_dP_psia), 1e-12)
    ):
        return None
    if float(np.nanmax(np.abs(y_curr - y_prev))) > max(float(max_abs_dx), 1e-12):
        return None
    v_scale = max(abs(float(V_vapor_in_lbmolps)), abs(float(packet.V_vapor_in_lbmolps)), 1.0e-9)
    if abs(float(V_vapor_in_lbmolps) - float(packet.V_vapor_in_lbmolps)) > max(float(max_rel_dV), 1e-12) * v_scale:
        return None
    if packet.q_calc_BTUph is None and packet.T_bubble_F is None:
        return None
    return packet


def _condenser_bubble_state_if_compatible(
    packet: Optional[CondenserDutyPacket],
    *,
    mode: str,
    P_condenser_psia: float,
    y_vapor_in: np.ndarray,
    max_abs_dP_psia: float,
    max_abs_dx: float,
) -> Optional[CondenserDutyPacket]:
    packet_hit, _reason, _detail = _condenser_bubble_state_compatibility_detail(
        packet,
        mode=mode,
        P_condenser_psia=P_condenser_psia,
        y_vapor_in=y_vapor_in,
        max_abs_dP_psia=max_abs_dP_psia,
        max_abs_dx=max_abs_dx,
    )
    return packet_hit


def _condenser_bubble_state_compatibility_detail(
    packet: Optional[CondenserDutyPacket],
    *,
    mode: str,
    P_condenser_psia: float,
    y_vapor_in: np.ndarray,
    max_abs_dP_psia: float,
    max_abs_dx: float,
) -> Tuple[Optional[CondenserDutyPacket], str, Optional[float]]:
    if packet is None:
        return None, "no_packet", None
    if str(packet.mode).strip().lower() != str(mode).strip().lower():
        return None, "mode_mismatch", None
    try:
        y_prev = np.asarray(packet.y_vapor_in, dtype=float).reshape((-1,))
        y_curr = np.asarray(y_vapor_in, dtype=float).reshape((-1,))
    except Exception:
        return None, "composition_parse_error", None
    if y_prev.shape != y_curr.shape:
        return None, "composition_shape_mismatch", None
    if not np.isfinite(float(packet.P_condenser_psia)):
        return None, "invalid_cached_pressure", None
    dP_abs = abs(float(P_condenser_psia) - float(packet.P_condenser_psia))
    if dP_abs > max(float(max_abs_dP_psia), 1e-12):
        return None, "condenser_pressure_delta", float(dP_abs)
    dx_max = float(np.nanmax(np.abs(y_curr - y_prev)))
    if dx_max > max(float(max_abs_dx), 1e-12):
        return None, "composition_delta", float(dx_max)
    if (
        (packet.T_bubble_F is None or not np.isfinite(float(packet.T_bubble_F)))
        and (packet.hL_cond_BTU_lbmol is None or not np.isfinite(float(packet.hL_cond_BTU_lbmol)))
    ):
        return None, "missing_bubble_state", None
    return packet, "hit", None


def _resolve_condenser_duty_btu_per_h(
    *,
    col: ColumnSpec,
    inputs: ColumnInputs,
    N: int,
    tray_T_F: np.ndarray,
    P_tray_psia: np.ndarray,
    V_in_lbmolps: np.ndarray,
    y_in: np.ndarray,
    epsilon_lbmol: float,
) -> Tuple[float, Optional[float], Optional[float], Optional[float], str]:
    """
    Resolve condenser duty for the current RHS call.

    Returns:
      (
          Q_used_BTUph,
          Q_calc_BTUph_or_None,
          T_cond_bubble_F_or_None,
          hL_cond_BTU_lbmol_or_None,
          mode_norm,
      )
    """
    mode = _normalize_condenser_duty_mode(getattr(inputs, "condenser_duty_mode", None))

    q_base = None
    q_override = getattr(inputs, "condenser_duty_btu_per_h", None)
    if q_override is not None:
        try:
            q_try = float(q_override)
            if np.isfinite(q_try):
                q_base = q_try
        except Exception:
            q_base = None
    if q_base is None:
        q_base = float(_get_condenser_duty_btu_per_h(col))

    q_used = float(q_base)
    q_calc = None
    t_bub = None
    hL_cond = None
    q_trim = 0.0
    q_trim_raw = getattr(inputs, "condenser_duty_trim_btu_per_h", None)
    if q_trim_raw is not None:
        try:
            q_try = float(q_trim_raw)
            if np.isfinite(q_try):
                q_trim = float(q_try)
        except Exception:
            q_trim = 0.0

    if bool(getattr(inputs, "enable_live_total_condenser_duty", True)) and inputs.thermo_provider is not None and N > 0:
        src_i = 1 if N > 1 else 0
        try:
            y_cond = np.asarray(y_in[0, :], dtype=float)
            prev_packet_all = getattr(inputs, "condenser_duty_prev", None)
            prev_packet = _condenser_duty_packet_if_compatible(
                prev_packet_all,
                mode=mode,
                V_vapor_in_lbmolps=float(V_in_lbmolps[0]),
                T_vapor_in_F=float(tray_T_F[src_i]),
                P_vapor_in_psia=float(P_tray_psia[src_i]),
                P_condenser_psia=float(P_tray_psia[0]),
                y_vapor_in=y_cond,
                max_abs_dT_F=float(getattr(inputs, "condenser_duty_reuse_dT_F", 0.0) or 0.0),
                max_abs_dP_psia=float(getattr(inputs, "condenser_duty_reuse_dP_psia", 0.0) or 0.0),
                max_abs_dx=float(getattr(inputs, "condenser_duty_reuse_dx", 0.0) or 0.0),
                max_rel_dV=float(getattr(inputs, "condenser_duty_reuse_dV_rel", 0.0) or 0.0),
            )
            if prev_packet is not None:
                _record_thermo_provider_counter(
                    inputs.thermo_provider,
                    "full_packet_hits",
                    1,
                    category="condenser_duty_reuse_diag",
                )
                q_try, t_try = _compute_total_condenser_duty_btu_per_h(
                    thermo_provider=inputs.thermo_provider,
                    V_vapor_in_lbmolps=float(V_in_lbmolps[0]),
                    y_vapor_in=y_cond,
                    T_vapor_in_F=float(tray_T_F[src_i]),
                    P_vapor_in_psia=float(P_tray_psia[src_i]),
                    P_condenser_psia=float(P_tray_psia[0]),
                    T_guess_F=float(tray_T_F[0]),
                    prev_bubble_packet=prev_packet,
                    epsilon_lbmol=float(epsilon_lbmol),
                )
                hL_cond = _condenser_liquid_enthalpy_BTU_lbmol(
                    thermo_provider=inputs.thermo_provider,
                    T_bubble_F=t_try,
                    P_condenser_psia=float(P_tray_psia[0]),
                    x_cond=y_cond,
                    packet=prev_packet,
                )
                _trace_stage_thermo(
                    inputs,
                    "condenser duty thermo solve reused previous bubble state "
                    f"T_vapor_in_F={float(tray_T_F[src_i]):.3f} P_cond_psia={float(P_tray_psia[0]):.3f}",
                )
            else:
                _record_thermo_provider_counter(
                    inputs.thermo_provider,
                    "full_packet_misses",
                    1,
                    category="condenser_duty_reuse_diag",
                )
                _trace_stage_thermo(
                    inputs,
                    "condenser duty thermo solve start "
                    f"T_vapor_in_F={float(tray_T_F[src_i]):.3f} P_cond_psia={float(P_tray_psia[0]):.3f}",
                )
                bubble_packet, bubble_reason, bubble_detail = _condenser_bubble_state_compatibility_detail(
                    prev_packet_all,
                    mode=mode,
                    P_condenser_psia=float(P_tray_psia[0]),
                    y_vapor_in=y_cond,
                    max_abs_dP_psia=max(
                        float(getattr(inputs, "condenser_duty_bubble_state_reuse_dP_psia", 0.0) or 0.0),
                        float(getattr(inputs, "condenser_duty_reuse_dP_psia", 0.0) or 0.0),
                        1.0,
                    ),
                    max_abs_dx=max(float(getattr(inputs, "condenser_duty_reuse_dx", 0.0) or 0.0), 0.02),
                )
                if bubble_packet is not None:
                    _record_thermo_provider_counter(
                        inputs.thermo_provider,
                        "bubble_state_hits",
                        1,
                        category="condenser_duty_reuse_diag",
                    )
                else:
                    _record_thermo_provider_counter(
                        inputs.thermo_provider,
                        f"bubble_state_miss_{str(bubble_reason).strip() or 'unknown'}",
                        1,
                        category="condenser_duty_reuse_diag",
                    )
                    if bubble_detail is not None and np.isfinite(float(bubble_detail)):
                        detail_metric = (
                            "bubble_state_miss_pressure_delta_abs_psia"
                            if str(bubble_reason) == "condenser_pressure_delta"
                            else "bubble_state_miss_composition_delta_abs"
                            if str(bubble_reason) == "composition_delta"
                            else None
                        )
                        if detail_metric is not None:
                            _record_thermo_provider_counter(
                                inputs.thermo_provider,
                                detail_metric,
                                float(bubble_detail),
                                category="condenser_duty_reuse_diag",
                            )
                q_try, t_try = _compute_total_condenser_duty_btu_per_h(
                    thermo_provider=inputs.thermo_provider,
                    V_vapor_in_lbmolps=float(V_in_lbmolps[0]),
                    y_vapor_in=y_cond,
                    T_vapor_in_F=float(tray_T_F[src_i]),
                    P_vapor_in_psia=float(P_tray_psia[src_i]),
                    P_condenser_psia=float(P_tray_psia[0]),
                    T_guess_F=float(tray_T_F[0]),
                    prev_bubble_packet=bubble_packet,
                    epsilon_lbmol=float(epsilon_lbmol),
                )
                hL_cond = _condenser_liquid_enthalpy_BTU_lbmol(
                    thermo_provider=inputs.thermo_provider,
                    T_bubble_F=t_try,
                    P_condenser_psia=float(P_tray_psia[0]),
                    x_cond=y_cond,
                    packet=bubble_packet,
                )
                if bubble_packet is not None:
                    _trace_stage_thermo(
                        inputs,
                        "condenser duty thermo solve reused previous bubble state "
                        f"T_bubble_F={float(bubble_packet.T_bubble_F) if bubble_packet.T_bubble_F is not None and np.isfinite(float(bubble_packet.T_bubble_F)) else float('nan'):.6g}",
                    )
                _record_thermo_provider_counter(
                    inputs.thermo_provider,
                    "fresh_solves",
                    1,
                    category="condenser_duty_reuse_diag",
                )
                _trace_stage_thermo(
                    inputs,
                    "condenser duty thermo solve done "
                    f"Q_calc_BTUph={float(q_try) if q_try is not None and np.isfinite(float(q_try)) else float('nan'):.6g} "
                    f"T_bubble_F={float(t_try) if t_try is not None and np.isfinite(float(t_try)) else float('nan'):.6g}",
                )
            if mode == "total-condense" and q_try is not None and np.isfinite(float(q_try)):
                q_calc = float(q_try)
                q_used = float(q_try)
            if t_try is not None and np.isfinite(float(t_try)):
                t_bub = float(t_try)
        except Exception:
            pass

    if mode == "total-condense":
        q_used = float(q_used) + float(q_trim)

    return float(q_used), q_calc, t_bub, hL_cond, mode


def _condenser_liquid_enthalpy_BTU_lbmol(
    *,
    thermo_provider: Any,
    T_bubble_F: Optional[float],
    P_condenser_psia: float,
    x_cond: np.ndarray,
    packet: Optional[CondenserDutyPacket] = None,
) -> Optional[float]:
    if packet is not None and packet.hL_cond_BTU_lbmol is not None:
        try:
            h_try = float(packet.hL_cond_BTU_lbmol)
            if np.isfinite(h_try):
                return h_try
        except Exception:
            pass
    if T_bubble_F is None or not np.isfinite(float(T_bubble_F)) or thermo_provider is None:
        return None
    try:
        fres_liq = _flash_TP_full_stage_F_psia(
            thermo_provider,
            0,
            float(T_bubble_F),
            float(P_condenser_psia),
            x_cond,
            n_components=np.asarray(x_cond, dtype=float).reshape((-1,)).size,
            thermo_call_category="condenser_duty_helper_flash",
        )
        hL_cond = getattr(fres_liq, "HL_BTU_lbmol", None)
        if hL_cond is None or (not np.isfinite(float(hL_cond))):
            hL_cond = getattr(fres_liq, "HL", None)
        if hL_cond is not None and np.isfinite(float(hL_cond)):
            return float(hL_cond)
    except Exception:
        return None
    return None


def _compute_total_condenser_duty_btu_per_h(
    *,
    thermo_provider: Any,
    V_vapor_in_lbmolps: float,
    y_vapor_in: np.ndarray,
    T_vapor_in_F: float,
    P_vapor_in_psia: float,
    P_condenser_psia: float,
    T_guess_F: float,
    prev_bubble_packet: Optional[CondenserDutyPacket] = None,
    epsilon_lbmol: float = 1e-12,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Compute total-condenser duty (BTU/h) by condensing incoming vapor to
    saturated liquid at bubble point.

    Returns (Q_cond_BTUph, T_bubble_F). Negative Q means heat removal.
    """
    if thermo_provider is None:
        return None, None

    y = np.asarray(y_vapor_in, dtype=float).reshape((-1,))
    y = np.where(np.isfinite(y), y, 0.0)
    sy = float(np.sum(y))
    if sy <= epsilon_lbmol:
        return 0.0, (float(T_guess_F) if np.isfinite(float(T_guess_F)) else None)
    y = y / sy

    V_in = float(V_vapor_in_lbmolps)
    if (not np.isfinite(V_in)) or V_in <= epsilon_lbmol:
        return 0.0, (float(T_guess_F) if np.isfinite(float(T_guess_F)) else None)

    P_cond = float(P_condenser_psia) if np.isfinite(float(P_condenser_psia)) and float(P_condenser_psia) > 0.0 else float(P_vapor_in_psia)
    P_vin = float(P_vapor_in_psia) if np.isfinite(float(P_vapor_in_psia)) and float(P_vapor_in_psia) > 0.0 else P_cond
    T_in = float(T_vapor_in_F) if np.isfinite(float(T_vapor_in_F)) else float(T_guess_F)
    T_guess = float(T_guess_F) if np.isfinite(float(T_guess_F)) else T_in

    # Condensed-liquid composition for a total condenser is the incoming vapor composition.
    x_cond = y.copy()

    T_bub_F = None
    fres_bub = None
    hL_cond = None
    if prev_bubble_packet is not None:
        if prev_bubble_packet.T_bubble_F is not None and np.isfinite(float(prev_bubble_packet.T_bubble_F)):
            T_bub_F = float(prev_bubble_packet.T_bubble_F)
        if prev_bubble_packet.hL_cond_BTU_lbmol is not None and np.isfinite(float(prev_bubble_packet.hL_cond_BTU_lbmol)):
            hL_cond = float(prev_bubble_packet.hL_cond_BTU_lbmol)
    prefer_flash_bubble_solver = bool(getattr(thermo_provider, "prefer_flash_bubble_point_solver", False))
    if not prefer_flash_bubble_solver:
        try:
            bubble_t_fn = getattr(thermo_provider, "bubble_point_temperature_F_psia", None)
            if callable(bubble_t_fn):
                with _thermo_provider_category(thermo_provider, "condenser_bubble_point_direct"):
                    T_try = bubble_t_fn(float(P_cond), x_cond.tolist())
                if T_try is not None and np.isfinite(float(T_try)):
                    T_bub_F = float(T_try)
        except Exception:
            T_bub_F = None

    if T_bub_F is None:
        try:
            T_bub_F, fres_bub = _bubble_point_T_F(
                thermo_provider=thermo_provider,
                P_psia=P_cond,
                x=x_cond,
                T_guess_F=T_guess,
                thermo_call_category="condenser_duty_bubble_point_helper_flash",
            )
        except Exception:
            return None, None

    if hL_cond is None and fres_bub is not None:
        hL_cond = getattr(fres_bub, "HL_BTU_lbmol", None)
        if hL_cond is None or (not np.isfinite(float(hL_cond))):
            hL_cond = getattr(fres_bub, "HL", None)
    if hL_cond is None or (not np.isfinite(float(hL_cond))):
        hL_cond = _condenser_liquid_enthalpy_BTU_lbmol(
            thermo_provider=thermo_provider,
            T_bubble_F=T_bub_F,
            P_condenser_psia=P_cond,
            x_cond=x_cond,
            packet=prev_bubble_packet,
        )
    if hL_cond is None or (not np.isfinite(float(hL_cond))):
        return None, float(T_bub_F)

    try:
        fres_vin = _flash_TP_full_stage_F_psia(
            thermo_provider,
            0,
            float(T_in),
            float(P_vin),
            y,
            n_components=y.size,
            thermo_call_category="condenser_duty_helper_flash",
        )
        hV_in = getattr(fres_vin, "HV_BTU_lbmol", None)
        if hV_in is None or (not np.isfinite(float(hV_in))):
            hV_in = getattr(fres_vin, "HV", None)
    except Exception:
        hV_in = None
    if hV_in is None or (not np.isfinite(float(hV_in))):
        return None, float(T_bub_F)

    Q_cond_BTUph = float(V_in) * (float(hL_cond) - float(hV_in)) * 3600.0
    if not np.isfinite(Q_cond_BTUph):
        return None, float(T_bub_F)
    return float(Q_cond_BTUph), float(T_bub_F)


def _lagged_top_drum_pressure_temperature_F(
    *,
    top_T_raw_F: float,
    top_T_prev_used_F: Optional[float],
    T_tray_prev_F: Optional[np.ndarray],
    n_stages: int,
    dt_sec: Optional[float],
    tau_sec: Optional[float],
    tau_fallback_sec: Optional[float],
) -> Tuple[float, Optional[float]]:
    """
    Dampen one-step stage-1 temperature shocks before they are used in the
    ideal-gas top-drum pressure calculation.

    A first-order lag is applied only when a valid previous tray temperature
    and a positive timescale are available.
    """
    try:
        T_raw = float(top_T_raw_F)
    except Exception:
        return 100.0, None
    if not np.isfinite(T_raw):
        return 100.0, None

    T_prev0 = None
    if top_T_prev_used_F is not None:
        try:
            t_prev_used_try = float(top_T_prev_used_F)
            if np.isfinite(t_prev_used_try):
                T_prev0 = t_prev_used_try
        except Exception:
            T_prev0 = None
    if T_tray_prev_F is not None:
        if T_prev0 is None:
            try:
                T_prev = np.asarray(T_tray_prev_F, dtype=float).reshape((int(n_stages),))
                T_prev0_try = float(T_prev[0])
                if np.isfinite(T_prev0_try):
                    T_prev0 = T_prev0_try
            except Exception:
                T_prev0 = None

    tau = None
    if tau_sec is not None:
        try:
            tau_try = float(tau_sec)
        except Exception:
            tau_try = np.nan
        # Explicit non-positive setting disables smoothing.
        if np.isfinite(tau_try) and tau_try <= 0.0:
            return T_raw, None
        if np.isfinite(tau_try) and tau_try > 0.0:
            tau = tau_try
    if tau is None and tau_fallback_sec is not None:
        try:
            tau_try = float(tau_fallback_sec)
        except Exception:
            tau_try = np.nan
        if np.isfinite(tau_try) and tau_try <= 0.0:
            return T_raw, None
        if np.isfinite(tau_try) and tau_try > 0.0:
            tau = tau_try
    if tau is None:
        tau = 5.0

    dt = None
    if dt_sec is not None:
        try:
            dt_try = float(dt_sec)
            if np.isfinite(dt_try) and dt_try > 0.0:
                dt = dt_try
        except Exception:
            dt = None

    if T_prev0 is None or tau is None or dt is None:
        return T_raw, None

    alpha = float(np.clip(dt / tau, 0.0, 1.0))
    T_used = float(T_prev0 + alpha * (T_raw - T_prev0))
    if not np.isfinite(T_used):
        return T_raw, alpha
    return T_used, alpha


def _compute_top_drum_pressure_psia(
    *,
    top_V: np.ndarray,
    top_T_F: float,
    Z_top: float,
    top_vapor_volume_ft3: float,
    thermo_provider: Any = None,
    y_top: Optional[np.ndarray] = None,
    P_seed_psia: Optional[float] = None,
    max_iter: int = 12,
    return_details: bool = False,
    allow_flash_fallback_on_refine_failure: bool = True,
) -> Any:
    MV_top = float(np.sum(np.asarray(top_V, dtype=float).reshape((-1,))))
    if (not np.isfinite(MV_top)) or MV_top < 0.0:
        return (None, None, MV_top) if return_details else None
    T_R = float(top_T_F) + 459.67
    if (not np.isfinite(T_R)) or T_R <= 0.0:
        return (None, None, MV_top) if return_details else None
    Z = float(Z_top)
    if (not np.isfinite(Z)) or Z <= 0.0:
        Z = 1.0
    V = float(top_vapor_volume_ft3)
    if (not np.isfinite(V)) or V <= 0.0:
        return (None, None, MV_top) if return_details else None
    R = 10.7316  # (psia*ft3)/(lbmol*R)
    P_ideal = MV_top * Z * R * T_R / V
    if (not np.isfinite(P_ideal)) or P_ideal <= 0.0:
        return (None, None, MV_top) if return_details else None

    P = float(P_ideal)
    z_eval = float(Z)
    y_use = None
    if y_top is not None:
        try:
            y_arr = np.asarray(y_top, dtype=float).reshape((-1,))
            y_sum = float(np.sum(y_arr))
            if np.all(np.isfinite(y_arr)) and y_sum > 0.0:
                y_use = y_arr / y_sum
        except Exception:
            y_use = None

    if thermo_provider is not None and y_use is not None:
        p_try = float(P_seed_psia) if P_seed_psia is not None and np.isfinite(float(P_seed_psia)) and float(P_seed_psia) > 0.0 else float(P_ideal)
        p_try = max(float(p_try), 1.0)
        z_last = None
        for _ in range(max(int(max_iter), 1)):
            z_try = None
            try:
                z_fn = getattr(thermo_provider, "vapor_z_factor_F_psia", None)
                if callable(z_fn):
                    with _thermo_provider_category(thermo_provider, "top_drum_pressure_z_refine_direct"):
                        z_try = z_fn(float(top_T_F), float(p_try), y_use.tolist())
            except Exception:
                z_try = None
            if z_try is None and allow_flash_fallback_on_refine_failure:
                try:
                    fres = _flash_TP_full_stage_F_psia(
                        thermo_provider,
                        0,
                        float(top_T_F),
                        float(p_try),
                        y_use,
                        n_components=y_use.size,
                        thermo_call_category="top_drum_pressure_z_refine_fallback_flash",
                    )
                    z_try = getattr(fres, "Z", None)
                except Exception:
                    z_try = None
            try:
                zf = float(z_try)
            except Exception:
                zf = np.nan
            if (not np.isfinite(zf)) or zf <= 0.0:
                break
            z_last = float(zf)
            p_new = float(MV_top * z_last * R * T_R / V)
            if (not np.isfinite(p_new)) or p_new <= 0.0:
                break
            if abs(float(p_new) - float(p_try)) <= max(1e-6, 1e-6 * abs(float(p_new))):
                P = float(p_new)
                z_eval = float(z_last)
                break
            p_try = 0.5 * float(p_try) + 0.5 * float(p_new)
            P = float(p_try)
            z_eval = float(z_last)

    if (not np.isfinite(P)) or P <= 0.0:
        return (None, None, MV_top) if return_details else None
    if return_details:
        return float(P), (float(z_eval) if np.isfinite(float(z_eval)) and float(z_eval) > 0.0 else None), float(MV_top)
    return float(P)


def _condenser_mass_split_from_duty(
    *,
    col: ColumnSpec,
    inputs: ColumnInputs,
    tray_T_F: np.ndarray,
    P_tray_psia: np.ndarray,
    V_in_lbmolps: np.ndarray,
    y_in: np.ndarray,
    top_V: np.ndarray,
    epsilon_lbmol: float,
) -> Tuple[float, float, float, Optional[float], Optional[float], Optional[float], str]:
    """
    Compute condenser mass split for stage-2 vapor:
      - V_cond_in: incoming vapor condensed to liquid (lbmol/s)
      - V_to_top: incoming vapor not condensed, sent to top vapor holdup (lbmol/s)
      - V_cond_top: top-vapor holdup condensed to liquid (lbmol/s)

    Returns:
      (
        V_cond_in,
        V_to_top,
        V_cond_top,
        Q_used_BTUph_or_None,
        Q_total_req_BTUph_or_None,
        T_bubble_F_or_None,
        mode_norm,
      )
    """
    mode = _normalize_condenser_duty_mode(getattr(inputs, "condenser_duty_mode", None))
    V_in0 = float(np.asarray(V_in_lbmolps, dtype=float).reshape((-1,))[0])
    if (not np.isfinite(V_in0)) or V_in0 <= float(epsilon_lbmol):
        return 0.0, 0.0, 0.0, None, None, None, mode

    # Resolve duty exactly as used by the energy closure (including total-condense trim).
    N = int(len(tray_T_F))
    try:
        Q_used_BTUph, Q_calc_BTUph, T_cond_bubble_F, _hL_cond_BTU_lbmol, mode = _resolve_condenser_duty_btu_per_h(
            col=col,
            inputs=inputs,
            N=N,
            tray_T_F=np.asarray(tray_T_F, dtype=float).reshape((N,)),
            P_tray_psia=np.asarray(P_tray_psia, dtype=float).reshape((N,)),
            V_in_lbmolps=np.asarray(V_in_lbmolps, dtype=float).reshape((N,)),
            y_in=np.asarray(y_in, dtype=float).reshape((N, -1)),
            epsilon_lbmol=float(epsilon_lbmol),
        )
    except Exception:
        Q_used_BTUph, Q_calc_BTUph = None, None
        T_cond_bubble_F = None

    if Q_used_BTUph is None or (not np.isfinite(float(Q_used_BTUph))):
        # Conservative fallback for pathological cases.
        Q_base = float(_get_condenser_duty_btu_per_h(col))
        q_override = getattr(inputs, "condenser_duty_btu_per_h", None)
        if q_override is not None:
            try:
                q_try = float(q_override)
                if np.isfinite(q_try):
                    Q_base = q_try
            except Exception:
                pass
        Q_used_BTUph = float(Q_base)

    Q_total_req = None
    if Q_calc_BTUph is not None and np.isfinite(float(Q_calc_BTUph)):
        Q_total_req = float(Q_calc_BTUph)
    elif bool(getattr(inputs, "enable_live_total_condenser_duty", True)) and inputs.thermo_provider is not None:
        try:
            src_i = 1 if N > 1 else 0
            q_req, T_cond_bubble_F_try = _compute_total_condenser_duty_btu_per_h(
                thermo_provider=inputs.thermo_provider,
                V_vapor_in_lbmolps=float(V_in0),
                y_vapor_in=np.asarray(y_in[0, :], dtype=float),
                T_vapor_in_F=float(tray_T_F[src_i]),
                P_vapor_in_psia=float(P_tray_psia[src_i]),
                P_condenser_psia=float(P_tray_psia[0]),
                T_guess_F=float(tray_T_F[0]),
                prev_bubble_packet=getattr(inputs, "condenser_duty_prev", None),
                epsilon_lbmol=float(epsilon_lbmol),
            )
            if q_req is not None and np.isfinite(float(q_req)):
                Q_total_req = float(q_req)
            if T_cond_bubble_F is None and T_cond_bubble_F_try is not None and np.isfinite(float(T_cond_bubble_F_try)):
                T_cond_bubble_F = float(T_cond_bubble_F_try)
        except Exception:
            Q_total_req = None

    # Strict total-condenser material handling:
    # all stage-2 vapor condenses to liquid, with no vapor slip to the top drum.
    # Keep Q_used/Q_total_req for diagnostics only unless the runner has
    # explicitly enabled duty-limited partial condensation for a coupled
    # condenser-duty pressure-control path.
    allow_partial_total_condense = bool(
        getattr(inputs, "condenser_duty_partial_condense_if_limited", False)
    )
    if mode == "total-condense" and (not allow_partial_total_condense):
        return float(V_in0), 0.0, 0.0, float(Q_used_BTUph), Q_total_req, T_cond_bubble_F, mode

    # If latent information is unavailable, preserve prior behavior (full condensation).
    if Q_total_req is None or (not np.isfinite(float(Q_total_req))) or float(Q_total_req) >= -1e-12:
        return float(V_in0), 0.0, 0.0, float(Q_used_BTUph), Q_total_req, T_cond_bubble_F, mode

    latent_BTU_per_lbmol = (-float(Q_total_req)) / max(float(V_in0) * 3600.0, 1e-12)
    if (not np.isfinite(latent_BTU_per_lbmol)) or latent_BTU_per_lbmol <= 1e-12:
        return float(V_in0), 0.0, 0.0, float(Q_used_BTUph), Q_total_req, T_cond_bubble_F, mode

    Q_remove_BTUph = max(-float(Q_used_BTUph), 0.0)
    cond_capacity_lbmolps = Q_remove_BTUph / latent_BTU_per_lbmol / 3600.0
    if (not np.isfinite(cond_capacity_lbmolps)) or cond_capacity_lbmolps <= 0.0:
        return 0.0, float(V_in0), 0.0, float(Q_used_BTUph), Q_total_req, T_cond_bubble_F, mode

    V_cond_in = min(float(V_in0), float(cond_capacity_lbmolps))
    rem_capacity = max(float(cond_capacity_lbmolps) - float(V_cond_in), 0.0)

    MV_top = float(np.sum(np.asarray(top_V, dtype=float).reshape((-1,))))
    MV_top = max(MV_top, 0.0)
    V_cond_top = min(float(rem_capacity), float(MV_top))
    V_to_top = max(float(V_in0) - float(V_cond_in), 0.0)
    return float(V_cond_in), float(V_to_top), float(V_cond_top), float(Q_used_BTUph), Q_total_req, T_cond_bubble_F, mode


def _pressure_diagnostic_psia(
    col: ColumnSpec,
    MV_tot_tray: np.ndarray,
    vol: VolumeModel,
    Z_factor: Optional[np.ndarray] = None,
) -> np.ndarray:
    N = col.n_stages
    MV = np.asarray(MV_tot_tray, dtype=float).reshape(N)

    if hasattr(col, "T_f"):
        T_R = (np.asarray(col.T_f, dtype=float).reshape(N) + 459.67)
    else:
        T_R = np.full(N, 100.0 + 459.67, dtype=float)

    R = 10.7316  # (psia*ft3)/(lbmol*R)

    if vol.vapor_volume_ft3_per_stage is not None:
        V = np.asarray(vol.vapor_volume_ft3_per_stage, dtype=float).reshape(N)
    else:
        V = np.full(N, float(vol.default_vapor_volume_ft3), dtype=float)
    V = np.where(V <= 0.0, 1.0, V)

    Z = np.ones(N, dtype=float) if Z_factor is None else np.asarray(Z_factor, dtype=float).reshape(N)

    return MV * Z * R * T_R / V


def _mixture_mw_lbm_per_lbmol(
    z: np.ndarray,
    mw_components: Optional[np.ndarray],
    default: float = 1.0,
) -> float:
    if mw_components is None:
        return float(default)
    mw = np.asarray(mw_components, dtype=float).reshape((-1,))
    z = np.asarray(z, dtype=float).reshape((-1,))
    if mw.size != z.size:
        return float(default)
    if not np.all(np.isfinite(mw)) or np.any(mw <= 0.0):
        return float(default)
    zsum = float(np.sum(z))
    if not np.isfinite(zsum) or zsum <= 0.0:
        return float(default)
    z = z / zsum
    return float(np.dot(z, mw))


def _pressure_profile_hydraulic_psia(
    *,
    P_bottom_psia: float,
    T_F: np.ndarray,
    V_in_lbmolps: np.ndarray,
    y_tray: np.ndarray,
    x_tray: np.ndarray,
    Z_vap: np.ndarray,
    geom: ColumnGeometry,
    h_ow_ft: Optional[np.ndarray],
    rhoL_lbmol_ft3: Optional[np.ndarray],
    mw_components: Optional[np.ndarray],
    dry_tray_K: float,
    P_top_spec_psia: Optional[float] = None,
    P_top_anchor_psia: Optional[float] = None,
    condenser_pressure_drop_psi: Optional[float] = None,
    min_pressure_psia: float = 14.7,
    max_dp_per_stage_psia: float = 5.0,
    return_details: bool = False,
) -> Any:
    N = int(len(T_F))
    P = np.full(N, np.nan, dtype=float)
    P[-1] = float(P_bottom_psia)

    area = None
    if getattr(geom, "active_area_ft2_per_stage", None) is not None:
        area = np.asarray(geom.active_area_ft2_per_stage, dtype=float).reshape((N,))
        if not np.all(np.isfinite(area)) or np.any(area <= 0.0):
            area = None
    if area is None:
        area = np.asarray(geom.area_ft2_per_stage, dtype=float).reshape((N,))
    area = np.where(~np.isfinite(area) | (area <= 0.0), 1.0, area)

    h_ow = np.zeros(N, dtype=float)
    if h_ow_ft is not None:
        try:
            h_ow = np.asarray(h_ow_ft, dtype=float).reshape((N,))
            h_ow = np.where(~np.isfinite(h_ow) | (h_ow < 0.0), 0.0, h_ow)
        except Exception:
            h_ow = np.zeros(N, dtype=float)

    rhoL_molar = None
    if rhoL_lbmol_ft3 is not None:
        try:
            rhoL_molar = np.asarray(rhoL_lbmol_ft3, dtype=float).reshape((N,))
        except Exception:
            rhoL_molar = None

    Z_use = np.asarray(Z_vap, dtype=float).reshape((N,))
    Z_use = np.where(~np.isfinite(Z_use) | (Z_use <= 0.0), 1.0, Z_use)

    R = 10.7316  # psia*ft^3/(lbmol*R)
    PSF_PER_PSIA = 144.0

    p_floor = float(min_pressure_psia) if np.isfinite(float(min_pressure_psia)) and float(min_pressure_psia) > 0.0 else 14.7
    if P_top_spec_psia is not None:
        try:
            p_top_spec = float(P_top_spec_psia)
            if np.isfinite(p_top_spec) and p_top_spec > 0.0:
                p_floor = max(p_floor, 0.5 * p_top_spec)
        except Exception:
            pass
    dp_stage_cap = float(max_dp_per_stage_psia) if np.isfinite(float(max_dp_per_stage_psia)) and float(max_dp_per_stage_psia) > 0.0 else 5.0

    # Compute raw tray-to-tray pressure drops using current local state.
    # Index i represents drop from stage i to stage i-1.
    dp_raw = np.zeros(N, dtype=float)
    dp_dry_raw = np.zeros(N, dtype=float)
    dp_liq_raw = np.zeros(N, dtype=float)
    cond_dp_fixed = 0.0
    if condenser_pressure_drop_psi is not None:
        try:
            cond_try = float(condenser_pressure_drop_psi)
            if np.isfinite(cond_try):
                cond_dp_fixed = max(cond_try, 0.0)
        except Exception:
            cond_dp_fixed = 0.0

    for i in range(N - 1, 0, -1):
        if i == (N - 1):
            # No dry/liquid drop across reboiler boundary in this tray model.
            dp_psia = 0.0
            dp_dry_i = 0.0
            dp_liq_i = 0.0
        elif i == 1 and cond_dp_fixed > 0.0:
            # Optional explicit condenser pressure drop from stage 2 to stage 1.
            dp_psia = float(cond_dp_fixed)
            dp_dry_i = 0.0
            dp_liq_i = 0.0
        else:
            P_i = float(P[i])
            if not np.isfinite(P_i) or P_i <= 0.0:
                P_i = max(float(P_bottom_psia), p_floor)

            T_R = float(T_F[i]) + 459.67
            if not np.isfinite(T_R) or T_R <= 0.0:
                T_R = 520.0

            Z_i = float(Z_use[i])
            Vdot = float(V_in_lbmolps[i]) * R * T_R / max(P_i * Z_i, 1e-12)
            v = Vdot / max(float(area[i]), 1e-12)

            mw_v = _mixture_mw_lbm_per_lbmol(y_tray[i, :], mw_components, default=1.0)
            rho_molar_v = P_i / max(Z_i * R * T_R, 1e-12)
            rho_mass_v = rho_molar_v * mw_v

            dp_dry = float(dry_tray_K) * 0.5 * rho_mass_v * v * v / PSF_PER_PSIA

            dp_liq = 0.0
            if rhoL_molar is not None and np.isfinite(rhoL_molar[i]) and rhoL_molar[i] > 0.0:
                mw_l = _mixture_mw_lbm_per_lbmol(x_tray[i, :], mw_components, default=1.0)
                rho_mass_l = float(rhoL_molar[i]) * mw_l
                dp_liq = rho_mass_l * float(h_ow[i]) / PSF_PER_PSIA

            dp_psia = max(dp_dry + dp_liq, 0.0)
            dp_dry_i = max(float(dp_dry), 0.0)
            dp_liq_i = max(float(dp_liq), 0.0)
            if np.isfinite(dp_stage_cap) and dp_stage_cap > 0.0:
                dp_psia = min(dp_psia, dp_stage_cap)
        dp_raw[i] = float(max(dp_psia, 0.0))
        dp_dry_raw[i] = float(max(dp_dry_i, 0.0))
        dp_liq_raw[i] = float(max(dp_liq_i, 0.0))

    # Determine drop scaling:
    # - with explicit top anchor, scale drops so computed top pressure tracks it
    # - otherwise keep total pressure drop physically bounded so top never collapses
    total_drop_raw = float(np.sum(dp_raw[1:]))  # ignore index 0 sentinel
    total_drop_internal_raw = float(np.sum(dp_raw[2:])) if N > 2 else 0.0
    drop_scale = 1.0
    p_top_anchor = None
    if P_top_anchor_psia is not None:
        try:
            p_try = float(P_top_anchor_psia)
            if np.isfinite(p_try) and p_try > 0.0:
                p_top_anchor = max(float(p_try), p_floor)
        except Exception:
            p_top_anchor = None
    if p_top_anchor is not None:
        target_total_drop = max(float(P_bottom_psia) - float(p_top_anchor), 0.0)
        if cond_dp_fixed > 0.0 and N > 1:
            target_internal_drop = max(target_total_drop - float(cond_dp_fixed), 0.0)
            if total_drop_internal_raw > 1e-12:
                drop_scale = target_internal_drop / total_drop_internal_raw
            else:
                drop_scale = 0.0
        else:
            if total_drop_raw > 1e-12:
                drop_scale = target_total_drop / total_drop_raw
            else:
                drop_scale = 0.0
    else:
        max_total_drop = max(float(P_bottom_psia) - p_floor, 0.0)
        if cond_dp_fixed > 0.0 and N > 1:
            max_internal_drop = max(max_total_drop - float(cond_dp_fixed), 0.0)
            if total_drop_internal_raw > max_internal_drop and total_drop_internal_raw > 1e-12:
                drop_scale = max_internal_drop / total_drop_internal_raw
        else:
            if total_drop_raw > max_total_drop and total_drop_raw > 1e-12:
                drop_scale = max_total_drop / total_drop_raw

    dp_used = np.zeros(N, dtype=float)
    for i in range(N - 1, 0, -1):
        if i == 1 and cond_dp_fixed > 0.0:
            dp_psia = float(cond_dp_fixed)
        else:
            dp_psia = float(dp_raw[i]) * float(drop_scale)
        dp_used[i] = float(max(dp_psia, 0.0))
        P[i - 1] = max(float(P[i]) - dp_psia, p_floor)

    if not bool(return_details):
        return P

    details = {
        "hydraulic_dp_raw_psia": np.asarray(dp_raw, dtype=float).reshape((N,)),
        "hydraulic_dp_dry_raw_psia": np.asarray(dp_dry_raw, dtype=float).reshape((N,)),
        "hydraulic_dp_liq_raw_psia": np.asarray(dp_liq_raw, dtype=float).reshape((N,)),
        "hydraulic_dp_used_psia": np.asarray(dp_used, dtype=float).reshape((N,)),
        "hydraulic_dp_scale": np.array([float(drop_scale)], dtype=float),
        "hydraulic_dp_total_raw_psia": np.array([float(total_drop_raw)], dtype=float),
        "hydraulic_dp_total_internal_raw_psia": np.array([float(total_drop_internal_raw)], dtype=float),
        "hydraulic_cond_dp_fixed_psia": np.array([float(cond_dp_fixed)], dtype=float),
    }
    return P, details


def _vapor_outflow_hydraulic_lbmolps(
    *,
    P_profile_psia: np.ndarray,
    T_F: np.ndarray,
    y_tray: np.ndarray,
    x_tray: np.ndarray,
    Z_vap: np.ndarray,
    geom: ColumnGeometry,
    h_ow_ft: Optional[np.ndarray],
    rhoL_lbmol_ft3: Optional[np.ndarray],
    mw_components: Optional[np.ndarray],
    dry_tray_K: float,
) -> np.ndarray:
    N = int(len(T_F))
    V_out = np.zeros(N, dtype=float)

    area = None
    if getattr(geom, "active_area_ft2_per_stage", None) is not None:
        area = np.asarray(geom.active_area_ft2_per_stage, dtype=float).reshape((N,))
        if not np.all(np.isfinite(area)) or np.any(area <= 0.0):
            area = None
    if area is None:
        area = np.asarray(geom.area_ft2_per_stage, dtype=float).reshape((N,))
    area = np.where(~np.isfinite(area) | (area <= 0.0), 1.0, area)

    h_ow = np.zeros(N, dtype=float)
    if h_ow_ft is not None:
        try:
            h_ow = np.asarray(h_ow_ft, dtype=float).reshape((N,))
            h_ow = np.where(~np.isfinite(h_ow) | (h_ow < 0.0), 0.0, h_ow)
        except Exception:
            h_ow = np.zeros(N, dtype=float)

    rhoL_molar = None
    if rhoL_lbmol_ft3 is not None:
        try:
            rhoL_molar = np.asarray(rhoL_lbmol_ft3, dtype=float).reshape((N,))
        except Exception:
            rhoL_molar = None

    Z_use = np.asarray(Z_vap, dtype=float).reshape((N,))
    Z_use = np.where(~np.isfinite(Z_use) | (Z_use <= 0.0), 1.0, Z_use)

    R = 10.7316
    PSF_PER_PSIA = 144.0

    Pp = np.asarray(P_profile_psia, dtype=float).reshape((N,))
    for i in range(1, N - 1):
        P_i = float(Pp[i])
        P_above = float(Pp[i - 1])
        if not np.isfinite(P_i) or P_i <= 0.0 or not np.isfinite(P_above) or P_above <= 0.0:
            continue

        dp_total = max(P_i - P_above, 0.0)
        if dp_total <= 0.0:
            continue

        T_R = float(T_F[i]) + 459.67
        if not np.isfinite(T_R) or T_R <= 0.0:
            T_R = 520.0
        Z_i = float(Z_use[i])

        mw_v = _mixture_mw_lbm_per_lbmol(y_tray[i, :], mw_components, default=1.0)
        rho_molar_v = P_i / max(Z_i * R * T_R, 1e-12)
        rho_mass_v = rho_molar_v * mw_v

        dp_liq = 0.0
        if rhoL_molar is not None and np.isfinite(rhoL_molar[i]) and rhoL_molar[i] > 0.0:
            mw_l = _mixture_mw_lbm_per_lbmol(x_tray[i, :], mw_components, default=1.0)
            rho_mass_l = float(rhoL_molar[i]) * mw_l
            dp_liq = rho_mass_l * float(h_ow[i]) / PSF_PER_PSIA

        dp_dry = max(dp_total - dp_liq, 0.0)
        if dp_dry <= 0.0 or dry_tray_K <= 0.0 or rho_mass_v <= 0.0:
            continue

        v = (2.0 * dp_dry * PSF_PER_PSIA / (dry_tray_K * rho_mass_v)) ** 0.5
        Vdot_ft3_s = v * float(area[i])

        V_out[i] = Vdot_ft3_s * P_i / max(Z_i * R * T_R, 1e-12)

    return V_out


def _rachford_rice_beta(K: np.ndarray, z: np.ndarray, tol: float = 1e-10, max_iter: int = 100) -> float:
    """Solve vapor fraction beta in [0,1] for given K and overall composition z."""
    K = np.asarray(K, dtype=float).reshape((-1,))
    z = np.asarray(z, dtype=float).reshape((-1,))
    z = z / max(float(np.sum(z)), 1e-300)

    def f(beta: float) -> float:
        return float(np.sum(z * (K - 1.0) / (1.0 + beta * (K - 1.0))))

    f0 = f(0.0)
    f1 = f(1.0)
    if f0 < 0.0 and f1 < 0.0:
        return 0.0
    if f0 > 0.0 and f1 > 0.0:
        return 1.0

    lo = 0.0
    hi = 1.0
    flo = f0
    fhi = f1
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) <= tol:
            return float(mid)
        if fmid * flo > 0.0:
            lo = mid
            flo = fmid
        else:
            hi = mid
            fhi = fmid
    return float(0.5 * (lo + hi))


def _reboiler_flash_after_duty(
    *,
    thermo_provider: Any,
    P_psia: float,
    z: np.ndarray,
    T_in_F: float,
    H_in_BTU_lbmol: float,
    Q_btu_per_h: float,
    L_in_lbmolps: float,
    T_min_F: float = 50.0,
    T_max_F: float = 800.0,
    n_scan: int = 21,
    max_iter: int = 40,
    thermo_call_category: Optional[str] = "reboiler_duty_solve_flash",
) -> Tuple[float, float, np.ndarray, np.ndarray, np.ndarray, float, float]:
    """
    Solve reboiler outlet temperature after adding duty to the incoming liquid enthalpy.
    Returns (T_F, beta, x, y, K, HL, HV).
    """
    z = np.asarray(z, dtype=float).reshape((-1,))
    z = z / max(float(np.sum(z)), 1e-300)

    if L_in_lbmolps <= 0.0:
        raise RuntimeError("L_in_lbmolps must be > 0 for reboiler flash.")

    H_target = float(H_in_BTU_lbmol) + float(Q_btu_per_h) / (float(L_in_lbmolps) * 3600.0)

    def eval_T(T_F: float):
        try:
            with _thermo_provider_category(thermo_provider, thermo_call_category):
                fres = flash_TP_full_F_psia(
                    thermo_provider,
                    float(T_F),
                    float(P_psia),
                    z,
                    n_components=z.size,
                )
        except Exception as exc:
            raise RuntimeError("flash failed") from exc
        K = np.asarray(fres.K, dtype=float).reshape((-1,))
        beta = _rachford_rice_beta(K, z)
        x = z / (1.0 + beta * (K - 1.0))
        x = np.clip(x, 0.0, None)
        sx = float(np.sum(x))
        if not np.isfinite(sx) or sx <= 1e-300:
            x = z.copy()
        else:
            x = x / sx
        y = K * x
        sy = float(np.sum(y))
        if not np.isfinite(sy) or sy <= 1e-300:
            y = z.copy()
        else:
            y = y / sy
        HL = float(fres.HL_BTU_lbmol)
        HV = float(fres.HV_BTU_lbmol)
        H_mix = HL + beta * (HV - HL)
        return H_mix - H_target, beta, x, y, K, HL, HV

    # Scan for bracket
    Ts = np.linspace(T_min_F, T_max_F, n_scan)
    vals = []
    for T in Ts:
        try:
            fval, beta, x, y, K, HL, HV = eval_T(float(T))
            vals.append((float(T), fval, beta, x, y, K, HL, HV))
        except Exception:
            continue

    if not vals:
        raise RuntimeError("reboiler flash failed at all scan points")

    bracket = None
    for i in range(len(vals) - 1):
        f0 = vals[i][1]
        f1 = vals[i + 1][1]
        if f0 == 0.0:
            T, _f, beta, x, y, K, HL, HV = vals[i]
            return T, beta, x, y, K, HL, HV
        if f0 * f1 < 0.0:
            bracket = (vals[i], vals[i + 1])
            break

    if bracket is None:
        # fallback: closest
        T, _f, beta, x, y, K, HL, HV = min(vals, key=lambda r: abs(r[1]))
        return T, beta, x, y, K, HL, HV

    (Tlo, flo, *_), (Thi, fhi, *_) = bracket
    lo = Tlo
    hi = Thi
    flo = float(flo)
    fhi = float(fhi)

    best = None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid, beta, x, y, K, HL, HV = eval_T(float(mid))
        best = (mid, beta, x, y, K, HL, HV)
        if abs(fmid) <= 1e-6:
            break
        if fmid * flo > 0.0:
            lo = mid
            flo = fmid
        else:
            hi = mid
            fhi = fmid

    if best is None:
        T, _f, beta, x, y, K, HL, HV = vals[0]
        return T, beta, x, y, K, HL, HV
    return best


def _get_liquid_density_lbmol_ft3(col: ColumnSpec, default: float = 1.0) -> float:
    specs = getattr(col, "specs", None) or getattr(col, "specs_raw", None) or {}
    if isinstance(specs, dict):
        for key in (
            "Liquid Density (lbmol/ft3)",
            "Liquid Density (lbmol/ft^3)",
        ):
            if key in specs and specs[key] is not None:
                try:
                    v = float(specs[key])
                    if np.isfinite(v) and v > 0.0:
                        return v
                except Exception:
                    pass
    return float(default)


def _thermo_provider_temperature_bounds_F(thermo_provider: Any) -> Optional[Tuple[float, float]]:
    """
    Return (T_min_F, T_max_F) if provider exposes a tabular temperature grid.
    """
    if thermo_provider is None:
        return None
    grid = getattr(thermo_provider, "T_grid_F", None)
    if grid is None:
        return None
    try:
        g = np.asarray(grid, dtype=float).reshape((-1,))
    except Exception:
        return None
    if g.size < 2 or (not np.all(np.isfinite(g))):
        return None
    t_min = float(np.min(g))
    t_max = float(np.max(g))
    if (not np.isfinite(t_min)) or (not np.isfinite(t_max)) or (t_max <= t_min):
        return None
    return float(t_min), float(t_max)


def _bubble_point_T_F(
    *,
    thermo_provider: Any,
    P_psia: float,
    x: np.ndarray,
    T_guess_F: Optional[float] = None,
    T_min_F: float = 50.0,
    T_max_F: float = 600.0,
    max_iter: int = 18,
    beta_target: float = 1e-6,
    beta_tol: float = 1e-4,
    temperature_tol_F: float = 0.1,
    thermo_call_category: Optional[str] = None,
) -> Tuple[float, Any]:
    """
    Solve for bubble point temperature (F) at fixed pressure and liquid composition.
    Uses TP flash to evaluate K(T) and solves sum(K*x) = 1 by bisection.
    Returns (T_F, flash_result).
    """
    x = np.asarray(x, dtype=float).reshape((-1,))
    x = x / max(float(np.sum(x)), 1e-300)

    # Keep bubble-point solve within provider table bounds when available.
    t_bounds = _thermo_provider_temperature_bounds_F(thermo_provider)
    if t_bounds is not None:
        t_lo, t_hi = t_bounds
        T_min_F = max(float(T_min_F), float(t_lo))
        T_max_F = min(float(T_max_F), float(t_hi))

    eval_cache: Dict[float, Tuple[float, float, Any]] = {}

    def eval_f(T_F: float):
        T_eval = float(T_F)
        cached = eval_cache.get(T_eval)
        if cached is not None:
            return cached
        with _thermo_provider_category(thermo_provider, thermo_call_category):
            fres = flash_TP_full_F_psia(thermo_provider, float(T_F), float(P_psia), x, n_components=x.size)
        K = np.asarray(getattr(fres, "K", None), dtype=float)
        if K.size != x.size:
            # Fallback: compute K from y/x if available
            y = np.asarray(getattr(fres, "y", None), dtype=float)
            if y.size == x.size:
                K = y / np.maximum(x, 1e-300)
            else:
                K = np.ones_like(x)
        beta = _rachford_rice_beta(K, x)
        fval = float(beta - beta_target)
        result = (fval, beta, fres)
        eval_cache[T_eval] = result
        return result

    # Initial guess
    if T_guess_F is None or not np.isfinite(T_guess_F):
        T_guess_F = 200.0
    T_guess_F = float(T_guess_F)

    # Degenerate bound window: return clipped guess.
    if (not np.isfinite(float(T_min_F))) or (not np.isfinite(float(T_max_F))) or float(T_max_F) <= float(T_min_F):
        T_use = float(T_guess_F)
        f_use, beta_use, fres_use = eval_f(T_use)
        _ = (f_use, beta_use)
        return float(T_use), fres_use

    T_guess_F = float(np.clip(float(T_guess_F), float(T_min_F), float(T_max_F)))
    f_guess, _beta_guess, fres_guess = eval_f(T_guess_F)
    if abs(float(f_guess)) <= max(float(beta_tol), 1.0e-8):
        return float(T_guess_F), fres_guess

    # Try to bracket the root locally around the current guess before falling
    # back to a full coarse scan. In dynamic marching we are usually already
    # near the prior bubble-point state, so this avoids repeated global scans.
    span = max(float(T_max_F) - float(T_min_F), 0.0)
    local_step = max(min(span / 40.0 if span > 0.0 else 0.0, 20.0), 5.0)
    bracket = None
    best_dist = float("inf")
    for scale in (1.0, 2.0, 4.0, 8.0, 16.0):
        delta = float(local_step) * float(scale)
        T_low_try = max(float(T_min_F), float(T_guess_F) - delta)
        T_high_try = min(float(T_max_F), float(T_guess_F) + delta)

        if T_low_try < float(T_guess_F):
            f_low_try, _beta_low_try, _fres_low_try = eval_f(T_low_try)
            if float(f_low_try) == 0.0:
                return float(T_low_try), _fres_low_try
            if float(f_low_try) * float(f_guess) < 0.0:
                mid = 0.5 * (float(T_low_try) + float(T_guess_F))
                dist = abs(mid - float(T_guess_F))
                if dist < best_dist:
                    best_dist = dist
                    bracket = (float(T_low_try), float(T_guess_F), float(f_low_try), float(f_guess))

        if T_high_try > float(T_guess_F):
            f_high_try, _beta_high_try, _fres_high_try = eval_f(T_high_try)
            if float(f_high_try) == 0.0:
                return float(T_high_try), _fres_high_try
            if float(f_guess) * float(f_high_try) < 0.0:
                mid = 0.5 * (float(T_guess_F) + float(T_high_try))
                dist = abs(mid - float(T_guess_F))
                if dist < best_dist:
                    best_dist = dist
                    bracket = (float(T_guess_F), float(T_high_try), float(f_guess), float(f_high_try))

        if bracket is not None:
            break

    # Coarse scan to find a sign change bracket
    if bracket is None:
        n_scan = 21
        Ts = np.linspace(T_min_F, T_max_F, n_scan)
        fs = []
        fres_list = []
        exact_roots = []
        for T in Ts:
            f, beta, fres = eval_f(float(T))
            fs.append(f)
            fres_list.append(fres)

        # Find sign-change intervals; pick the one closest to T_guess.
        # Track any exact roots to avoid snapping to endpoints.
        best_dist = float("inf")
        for i in range(len(Ts) - 1):
            f0 = fs[i]
            f1 = fs[i + 1]
            if f0 == 0.0:
                exact_roots.append((abs(float(Ts[i]) - float(T_guess_F)), float(Ts[i]), fres_list[i]))
            if f1 == 0.0:
                exact_roots.append((abs(float(Ts[i + 1]) - float(T_guess_F)), float(Ts[i + 1]), fres_list[i + 1]))
            if f0 * f1 < 0.0:
                mid = 0.5 * (Ts[i] + Ts[i + 1])
                dist = abs(mid - T_guess_F)
                if dist < best_dist:
                    best_dist = dist
                    bracket = (float(Ts[i]), float(Ts[i + 1]), f0, f1)

        if exact_roots:
            exact_roots.sort(key=lambda r: r[0])
            _d, T_root, fres_root = exact_roots[0]
            return float(T_root), fres_root

    if bracket is None:
        # No sign change: keep continuity by evaluating at the clipped guess,
        # rather than snapping to a coarse-scan node.
        T_use = float(np.clip(float(T_guess_F), float(T_min_F), float(T_max_F)))
        _f_use, _beta_use, fres_use = eval_f(T_use)
        return float(T_use), fres_use

    T_low, T_high, f_low, f_high = bracket
    f_low, _beta_low, fres_low = eval_f(T_low)
    f_high, _beta_high, fres_high = eval_f(T_high)

    # Bisection
    T_a, T_b = T_low, T_high
    f_a, f_b = f_low, f_high
    fres_mid = fres_high
    for _ in range(max_iter):
        T_m = 0.5 * (T_a + T_b)
        f_m, _beta_m, fres_mid = eval_f(T_m)
        if abs(f_m) <= max(float(beta_tol), 1.0e-8):
            return T_m, fres_mid
        if abs(float(T_b) - float(T_a)) <= max(float(temperature_tol_F), 1.0e-6):
            return T_m, fres_mid
        if f_a * f_m < 0.0:
            T_b, f_b = T_m, f_m
        else:
            T_a, f_a = T_m, f_m
    return 0.5 * (T_a + T_b), fres_mid
