"""
thermo_step_coordinator_v1.py

Dynamic Distillation - Step Thermo Coordinator Helpers

PURPOSE
-------
Host step-scoped thermo orchestration helpers that can be shared by RHS call
sites. This first cut focuses on tray-state TP refresh so `column_rhs_v1.py`
does not have to own the full batch/scalar refresh block inline.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

import numpy as np


@dataclass(frozen=True)
class TrayThermoRefreshResult:
    packet: Any
    flash_skipped: np.ndarray
    flash_refreshed: np.ndarray
    source_code: np.ndarray
    flash_failed: np.ndarray
    phase_count: np.ndarray
    degenerate_two_phase_unit_K_quarantined: np.ndarray
    refresh_indices: tuple[int, ...]
    batch_used: bool


@dataclass(frozen=True)
class TemperatureStateEnthalpyRefreshResult:
    hL_stage_provider: Optional[np.ndarray]
    hV_stage_provider: Optional[np.ndarray]


@dataclass(frozen=True)
class EnergyVaporFlowEnthalpyRefreshResult:
    hL_stage_provider: Optional[np.ndarray]
    hV_stage_provider: Optional[np.ndarray]
    packet: Optional[Any]


def _parse_batch_flash_row(fres: Any, *, n_components: int):
    if isinstance(fres, (tuple, list)):
        phase_count_i = None
        if len(fres) == 5:
            x_i, y_i, K_i, HL_i, HV_i = fres
            Z_i = None
            cpL_i = None
            cpV_i = None
        elif len(fres) == 6:
            x_i, y_i, K_i, HL_i, HV_i, Z_i = fres
            cpL_i = None
            cpV_i = None
        elif len(fres) == 7:
            x_i, y_i, K_i, HL_i, HV_i, Z_i, cpL_i = fres
            cpV_i = None
        elif len(fres) == 8:
            x_i, y_i, K_i, HL_i, HV_i, Z_i, cpL_i, cpV_i = fres
        elif len(fres) == 9:
            x_i, y_i, K_i, HL_i, HV_i, Z_i, cpL_i, cpV_i, phase_count_i = fres
        else:
            raise RuntimeError("flash_TP_full_batch tuple rows must be length 5, 6, 7, 8, or 9")
        return (
            np.asarray(x_i, dtype=float).reshape((n_components,)),
            np.asarray(y_i, dtype=float).reshape((n_components,)),
            np.asarray(K_i, dtype=float).reshape((n_components,)),
            float(HL_i),
            float(HV_i),
            (None if Z_i is None else float(Z_i)),
            (None if cpL_i is None else float(cpL_i)),
            (None if cpV_i is None else float(cpV_i)),
            (None if phase_count_i is None else float(phase_count_i)),
        )

    K_i = np.asarray(getattr(fres, "K"), dtype=float).reshape((n_components,))
    HL_i = getattr(fres, "HL_BTU_lbmol", None)
    if HL_i is None:
        HL_i = getattr(fres, "HL")
    HV_i = getattr(fres, "HV_BTU_lbmol", None)
    if HV_i is None:
        HV_i = getattr(fres, "HV")

    Z_i = None
    for attr in ("Z", "Z_factor", "Zfac", "z_factor"):
        if hasattr(fres, attr):
            try:
                Z_i = float(getattr(fres, attr))
                break
            except Exception:
                pass

    cpL_i = None
    for attr in ("cpL_BTU_lbmolF", "cpL", "cp_liq_BTU_lbmolF"):
        if hasattr(fres, attr):
            try:
                cpL_i = float(getattr(fres, attr))
                break
            except Exception:
                pass

    cpV_i = None
    for attr in ("cpV_BTU_lbmolF", "cpV", "cp_vap_BTU_lbmolF"):
        if hasattr(fres, attr):
            try:
                cpV_i = float(getattr(fres, attr))
                break
            except Exception:
                pass

    return (
        np.asarray(getattr(fres, "x"), dtype=float).reshape((n_components,)),
        np.asarray(getattr(fres, "y"), dtype=float).reshape((n_components,)),
        K_i,
        float(HL_i),
        float(HV_i),
        Z_i,
        cpL_i,
        cpV_i,
        (None if not hasattr(fres, "phase_count") else float(getattr(fres, "phase_count"))),
    )


def _thermo_call_context(provider: Any, category: Optional[str]):
    category_fn = getattr(provider, "thermo_call_category", None)
    if not category or not callable(category_fn):
        return nullcontext()
    try:
        return category_fn(category)
    except Exception:
        return nullcontext()


def _is_unit_k_packet(K: Any, *, atol: float = 1.0e-9) -> bool:
    try:
        row = np.asarray(K, dtype=float).reshape((-1,))
    except Exception:
        return False
    finite = row[np.isfinite(row)]
    return bool(finite.size and float(np.max(np.abs(finite - 1.0))) <= float(atol))


def _can_quarantine_to_existing_packet(packet: Any, stage_index0: int, *, n_components: int) -> bool:
    try:
        k_prev = np.asarray(packet.K_tray[stage_index0, :], dtype=float).reshape((n_components,))
        hL_prev = float(packet.HL[stage_index0])
        hV_prev = float(packet.HV[stage_index0])
    except Exception:
        return False
    return bool(
        np.all(np.isfinite(k_prev))
        and not _is_unit_k_packet(k_prev)
        and np.isfinite(hL_prev)
        and np.isfinite(hV_prev)
    )


def refresh_tray_tp_packet(
    *,
    packet: Any,
    provider: Any,
    T_tray_F: Sequence[float],
    P_tray_psia: Sequence[float],
    z_overall_tray: np.ndarray,
    n_stages: int,
    n_components: int,
    dT_thresh_F: Optional[float],
    dP_thresh_psia: Optional[float],
    dX_thresh: Optional[float],
    T_prev_F: Optional[Sequence[float]],
    P_prev_psia: Optional[Sequence[float]],
    z_prev: Optional[np.ndarray],
    ensure_packet_equilibrium_arrays: Callable[..., None],
    flash_stage_fn: Callable[..., Any],
    batch_flash_fn: Optional[Callable[..., Any]] = None,
    thermo_call_category: Optional[str] = "main_tray_refresh",
    trace_fn: Optional[Callable[[Any, str], None]] = None,
    trace_context: Any = None,
) -> TrayThermoRefreshResult:
    T_tray = np.asarray(T_tray_F, dtype=float).reshape((n_stages,))
    P_tray = np.asarray(P_tray_psia, dtype=float).reshape((n_stages,))
    Z_overall = np.asarray(z_overall_tray, dtype=float).reshape((n_stages, n_components))
    flash_skipped = np.zeros(n_stages, dtype=float)
    flash_refreshed = np.zeros(n_stages, dtype=float)
    source_code = np.zeros(n_stages, dtype=float)
    flash_failed = np.zeros(n_stages, dtype=float)
    phase_count = np.full(n_stages, np.nan, dtype=float)
    quarantined = np.zeros(n_stages, dtype=float)
    refresh_indices: list[int] = []

    def _trace(msg: str) -> None:
        if callable(trace_fn):
            trace_fn(trace_context, msg)

    for i in range(n_stages):
        gate_active = False
        gate_pass = True

        if dT_thresh_F is not None:
            gate_active = True
            try:
                if T_prev_F is None or not (np.isfinite(T_prev_F[i]) and np.isfinite(T_tray[i])):
                    gate_pass = False
                else:
                    gate_pass = gate_pass and (abs(float(T_tray[i]) - float(T_prev_F[i])) < float(dT_thresh_F))
            except Exception:
                gate_pass = False

        if dP_thresh_psia is not None:
            gate_active = True
            try:
                if P_prev_psia is None or not (np.isfinite(P_prev_psia[i]) and np.isfinite(P_tray[i])):
                    gate_pass = False
                else:
                    gate_pass = gate_pass and (abs(float(P_tray[i]) - float(P_prev_psia[i])) < float(dP_thresh_psia))
            except Exception:
                gate_pass = False

        if dX_thresh is not None:
            gate_active = True
            try:
                if z_prev is None:
                    gate_pass = False
                else:
                    dz = np.asarray(Z_overall[i, :] - z_prev[i, :], dtype=float)
                    if not np.all(np.isfinite(dz)):
                        gate_pass = False
                    else:
                        gate_pass = gate_pass and (float(np.max(np.abs(dz))) < float(dX_thresh))
            except Exception:
                gate_pass = False

        if gate_active and gate_pass:
            flash_skipped[i] = 1.0
            source_code[i] = 1.0
            continue
        refresh_indices.append(i)

    batch_used = False
    if refresh_indices:
        ensure_packet_equilibrium_arrays(packet, n_stages=n_stages, n_components=n_components)
        batch_fn = batch_flash_fn if callable(batch_flash_fn) else getattr(provider, "flash_TP_full_batch", None)
        if callable(batch_fn):
            try:
                T_req = [float(T_tray[i]) for i in refresh_indices]
                P_req = [float(P_tray[i]) for i in refresh_indices]
                z_req = [np.asarray(Z_overall[i, :], dtype=float).tolist() for i in refresh_indices]
                with _thermo_call_context(provider, thermo_call_category):
                    fres_batch = batch_fn(T_req, P_req, z_req)
                if len(fres_batch) != len(refresh_indices):
                    raise RuntimeError(
                        "flash_TP_full_batch returned length "
                        f"{len(fres_batch)}; expected {len(refresh_indices)}"
                    )
                parsed_rows = [
                    _parse_batch_flash_row(fres, n_components=n_components)
                    for fres in fres_batch
                ]
                for pos, i in enumerate(refresh_indices):
                    x_i, y_i, K_i, HL_i, HV_i, Z_i, cpL_i, cpV_i, phase_count_i = parsed_rows[pos]
                    if phase_count_i is None:
                        phase_count_fn = getattr(provider, "flash_cached_phase_count_F_psia", None)
                        if callable(phase_count_fn):
                            try:
                                phase_count_i = phase_count_fn(float(T_tray[i]), float(P_tray[i]), Z_overall[i, :])
                            except Exception:
                                phase_count_i = None
                    if phase_count_i is not None:
                        phase_count[i] = float(phase_count_i)
                    if (
                        _is_unit_k_packet(K_i)
                        and _can_quarantine_to_existing_packet(packet, i, n_components=n_components)
                    ):
                        quarantined[i] = 1.0
                    else:
                        packet.x_eq[i, :] = x_i
                        packet.y_eq[i, :] = y_i
                        packet.K_tray[i, :] = K_i
                        packet.HL[i] = HL_i
                        packet.HV[i] = HV_i
                        if Z_i is not None:
                            packet.Zfac_tray[i] = float(Z_i)
                        if cpL_i is not None:
                            if packet.cpL_tray is None:
                                packet.cpL_BTU_lbmolF_tray = np.full(n_stages, np.nan, dtype=float)
                            packet.cpL_tray[i] = float(cpL_i)
                        if cpV_i is not None:
                            if packet.cpV_tray is None:
                                packet.cpV_BTU_lbmolF_tray = np.full(n_stages, np.nan, dtype=float)
                            packet.cpV_tray[i] = float(cpV_i)
                    flash_refreshed[i] = 1.0
                    source_code[i] = 2.0
                batch_used = True
            except Exception:
                batch_used = False

        if not batch_used:
            for i in refresh_indices:
                try:
                    _trace(
                        f"main_flash stage={int(i + 1)}/{int(n_stages)} start T_F={float(T_tray[i]):.3f} "
                        f"P_psia={float(P_tray[i]):.3f}"
                    )
                    fres = flash_stage_fn(
                        provider,
                        i,
                        float(T_tray[i]),
                        float(P_tray[i]),
                        Z_overall[i, :],
                        n_components=n_components,
                        thermo_call_category=thermo_call_category,
                    )
                    phase_count_i = getattr(fres, "phase_count", None)
                    if phase_count_i is not None:
                        phase_count[i] = float(phase_count_i)
                    K_i = np.asarray(fres.K, dtype=float).reshape((n_components,))
                    if (
                        _is_unit_k_packet(K_i)
                        and _can_quarantine_to_existing_packet(packet, i, n_components=n_components)
                    ):
                        quarantined[i] = 1.0
                    else:
                        packet.x_eq[i, :] = np.asarray(fres.x, dtype=float).reshape((n_components,))
                        packet.y_eq[i, :] = np.asarray(fres.y, dtype=float).reshape((n_components,))
                        packet.K_tray[i, :] = K_i
                        packet.HL[i] = fres.HL_BTU_lbmol
                        packet.HV[i] = fres.HV_BTU_lbmol
                        if getattr(fres, "Z", None) is not None:
                            packet.Zfac_tray[i] = float(fres.Z)
                        cpL_i = getattr(fres, "cpL_BTU_lbmolF", None)
                        if cpL_i is not None:
                            if packet.cpL_tray is None:
                                packet.cpL_BTU_lbmolF_tray = np.full(n_stages, np.nan, dtype=float)
                            packet.cpL_tray[i] = float(cpL_i)
                        cpV_i = getattr(fres, "cpV_BTU_lbmolF", None)
                        if cpV_i is not None:
                            if packet.cpV_tray is None:
                                packet.cpV_BTU_lbmolF_tray = np.full(n_stages, np.nan, dtype=float)
                            packet.cpV_tray[i] = float(cpV_i)
                    flash_refreshed[i] = 1.0
                    source_code[i] = 3.0
                    _trace(f"main_flash stage={int(i + 1)}/{int(n_stages)} done")
                except Exception as exc:
                    flash_failed[i] = 1.0
                    source_code[i] = -1.0
                    _trace(
                        f"main_flash stage={int(i + 1)}/{int(n_stages)} failed; retaining cached thermo state; "
                        f"error={type(exc).__name__}: {exc}"
                    )

    return TrayThermoRefreshResult(
        packet=packet,
        flash_skipped=flash_skipped,
        flash_refreshed=flash_refreshed,
        source_code=source_code,
        flash_failed=flash_failed,
        phase_count=phase_count,
        degenerate_two_phase_unit_K_quarantined=quarantined,
        refresh_indices=tuple(refresh_indices),
        batch_used=bool(batch_used),
    )


def refresh_temperature_state_phase_enthalpies(
    *,
    provider: Any,
    thermo_packet: Any,
    previous_packet: Any,
    energy_vapor_flow_packet: Any,
    tray_T_F: Sequence[float],
    P_tray_psia: Sequence[float],
    x_tray: np.ndarray,
    y_tray: np.ndarray,
    n_stages: int,
    n_components: int,
    packet_phase_tol_liq: float,
    packet_phase_tol_vap: float,
    packet_dT_tol_F: float,
    packet_dP_tol_psia: float,
    packet_phase_enthalpy_first_match_fn: Callable[..., Optional[float]],
    packet_phase_enthalpy_if_compatible_fn: Callable[..., Optional[float]],
    flash_stage_fn: Callable[..., Any],
    trace_fn: Optional[Callable[[Any, str], None]] = None,
    trace_context: Any = None,
) -> TemperatureStateEnthalpyRefreshResult:
    if provider is None:
        return TemperatureStateEnthalpyRefreshResult(
            hL_stage_provider=None,
            hV_stage_provider=None,
        )

    T_arr = np.asarray(tray_T_F, dtype=float).reshape((n_stages,))
    P_arr = np.asarray(P_tray_psia, dtype=float).reshape((n_stages,))
    x_arr = np.asarray(x_tray, dtype=float).reshape((n_stages, n_components))
    y_arr = np.asarray(y_tray, dtype=float).reshape((n_stages, n_components))
    hL_try = np.full(n_stages, np.nan, dtype=float)
    hV_try = np.full(n_stages, np.nan, dtype=float)

    def _trace(msg: str) -> None:
        if callable(trace_fn):
            trace_fn(trace_context, msg)

    _trace("temperature_state provider enthalpy refresh start")
    for j in range(n_stages):
        reused_hL = packet_phase_enthalpy_if_compatible_fn(
            energy_vapor_flow_packet,
            stage_index0=j,
            T_F=float(T_arr[j]),
            P_psia=float(P_arr[j]),
            phase_composition=x_arr[j, :],
            phase="liquid",
            max_abs_dx=packet_phase_tol_liq,
            max_abs_dT_F=packet_dT_tol_F,
            max_abs_dP_psia=packet_dP_tol_psia,
        )
        used_energy_packet = reused_hL is not None and np.isfinite(float(reused_hL))
        if reused_hL is None or (not np.isfinite(float(reused_hL))):
            reused_hL = packet_phase_enthalpy_first_match_fn(
                [thermo_packet, previous_packet],
                stage_index0=j,
                T_F=float(T_arr[j]),
                P_psia=float(P_arr[j]),
                phase_composition=x_arr[j, :],
                phase="liquid",
                max_abs_dx=packet_phase_tol_liq,
                max_abs_dT_F=packet_dT_tol_F,
                max_abs_dP_psia=packet_dP_tol_psia,
            )
        if reused_hL is not None and np.isfinite(float(reused_hL)):
            hL_try[j] = float(reused_hL)
            if used_energy_packet:
                _trace(f"temperature_state hL_flash stage={int(j + 1)}/{int(n_stages)} reused energy packet")
            else:
                _trace(f"temperature_state hL_flash stage={int(j + 1)}/{int(n_stages)} reused packet")
        else:
            try:
                _trace(f"temperature_state hL_flash stage={int(j + 1)}/{int(n_stages)} start")
                if hasattr(provider, "set_debug_trace_context"):
                    provider.set_debug_trace_context(
                        f"{str(getattr(trace_context, 'thermo_stage_trace_label', '') or '').strip()}:"
                        f"temperature_state:hL_flash:stage={int(j + 1)}"
                    )
                fres_L = flash_stage_fn(
                    provider,
                    j,
                    float(T_arr[j]),
                    float(P_arr[j]),
                    x_arr[j, :],
                    n_components=n_components,
                    thermo_call_category="temperature_state_enthalpy_refresh",
                )
                hL_try[j] = float(getattr(fres_L, "HL_BTU_lbmol"))
                _trace(f"temperature_state hL_flash stage={int(j + 1)}/{int(n_stages)} done")
            except Exception:
                pass
            finally:
                if hasattr(provider, "set_debug_trace_context"):
                    provider.set_debug_trace_context("")

        reused_hV = packet_phase_enthalpy_if_compatible_fn(
            energy_vapor_flow_packet,
            stage_index0=j,
            T_F=float(T_arr[j]),
            P_psia=float(P_arr[j]),
            phase_composition=y_arr[j, :],
            phase="vapor",
            max_abs_dx=packet_phase_tol_vap,
            max_abs_dT_F=packet_dT_tol_F,
            max_abs_dP_psia=packet_dP_tol_psia,
        )
        used_energy_packet = reused_hV is not None and np.isfinite(float(reused_hV))
        if used_energy_packet:
            hV_try[j] = float(reused_hV)
            _trace(f"temperature_state hV_flash stage={int(j + 1)}/{int(n_stages)} reused energy packet")
            continue

        reused_hV = packet_phase_enthalpy_first_match_fn(
            [thermo_packet, previous_packet],
            stage_index0=j,
            T_F=float(T_arr[j]),
            P_psia=float(P_arr[j]),
            phase_composition=y_arr[j, :],
            phase="vapor",
            max_abs_dx=packet_phase_tol_vap,
            max_abs_dT_F=packet_dT_tol_F,
            max_abs_dP_psia=packet_dP_tol_psia,
        )
        if reused_hV is not None and np.isfinite(float(reused_hV)):
            hV_try[j] = float(reused_hV)
            _trace(f"temperature_state hV_flash stage={int(j + 1)}/{int(n_stages)} reused packet")
        else:
            try:
                _trace(f"temperature_state hV_flash stage={int(j + 1)}/{int(n_stages)} start")
                if hasattr(provider, "set_debug_trace_context"):
                    provider.set_debug_trace_context(
                        f"{str(getattr(trace_context, 'thermo_stage_trace_label', '') or '').strip()}:"
                        f"temperature_state:hV_flash:stage={int(j + 1)}"
                    )
                fres_V = flash_stage_fn(
                    provider,
                    j,
                    float(T_arr[j]),
                    float(P_arr[j]),
                    y_arr[j, :],
                    n_components=n_components,
                    thermo_call_category="temperature_state_enthalpy_refresh",
                )
                hV_try[j] = float(getattr(fres_V, "HV_BTU_lbmol"))
                _trace(f"temperature_state hV_flash stage={int(j + 1)}/{int(n_stages)} done")
            except Exception:
                pass
            finally:
                if hasattr(provider, "set_debug_trace_context"):
                    provider.set_debug_trace_context("")

    _trace("temperature_state provider enthalpy refresh complete")
    return TemperatureStateEnthalpyRefreshResult(
        hL_stage_provider=(hL_try if np.any(np.isfinite(hL_try)) else None),
        hV_stage_provider=(hV_try if np.any(np.isfinite(hV_try)) else None),
    )


def refresh_energy_vapor_flow_phase_enthalpies(
    *,
    provider: Any,
    current_packet: Any,
    previous_packet: Any,
    tray_T_F: Sequence[float],
    P_tray_psia: Sequence[float],
    x_tray: np.ndarray,
    y_tray: np.ndarray,
    n_stages: int,
    n_components: int,
    packet_phase_tol_liq: float,
    packet_phase_tol_vap: float,
    packet_dT_tol_F: float,
    packet_dP_tol_psia: float,
    packet_phase_enthalpy_if_compatible_fn: Callable[..., Optional[float]],
    flash_stage_fn: Callable[..., Any],
    packet_factory: Callable[..., Any],
    force_liquid_refresh_indices: Optional[Sequence[int]] = None,
    trace_fn: Optional[Callable[[Any, str], None]] = None,
    trace_context: Any = None,
) -> EnergyVaporFlowEnthalpyRefreshResult:
    if provider is None:
        return EnergyVaporFlowEnthalpyRefreshResult(
            hL_stage_provider=None,
            hV_stage_provider=None,
            packet=None,
        )

    T_arr = np.asarray(tray_T_F, dtype=float).reshape((n_stages,))
    P_arr = np.asarray(P_tray_psia, dtype=float).reshape((n_stages,))
    x_arr = np.asarray(x_tray, dtype=float).reshape((n_stages, n_components))
    y_arr = np.asarray(y_tray, dtype=float).reshape((n_stages, n_components))
    hL_try = np.full(n_stages, np.nan, dtype=float)
    hV_try = np.full(n_stages, np.nan, dtype=float)
    pending_liq: list[int] = []
    pending_vap: list[int] = []
    batch_fn = getattr(provider, "flash_TP_full_batch", None)
    force_liq = set()
    if force_liquid_refresh_indices is not None:
        try:
            force_liq = {int(i) for i in force_liquid_refresh_indices if 0 <= int(i) < n_stages}
        except Exception:
            force_liq = set()

    def _trace(msg: str) -> None:
        if callable(trace_fn):
            trace_fn(trace_context, msg)

    for j in range(n_stages):
        reused_hL = None
        if j not in force_liq:
            reused_hL = packet_phase_enthalpy_if_compatible_fn(
                current_packet,
                stage_index0=j,
                T_F=float(T_arr[j]),
                P_psia=float(P_arr[j]),
                phase_composition=x_arr[j, :],
                phase="liquid",
                max_abs_dx=packet_phase_tol_liq,
                max_abs_dT_F=packet_dT_tol_F,
                max_abs_dP_psia=packet_dP_tol_psia,
            )
            if reused_hL is None or not np.isfinite(float(reused_hL)):
                reused_hL = packet_phase_enthalpy_if_compatible_fn(
                    previous_packet,
                    stage_index0=j,
                    T_F=float(T_arr[j]),
                    P_psia=float(P_arr[j]),
                    phase_composition=x_arr[j, :],
                    phase="liquid",
                    max_abs_dx=packet_phase_tol_liq,
                    max_abs_dT_F=packet_dT_tol_F,
                    max_abs_dP_psia=packet_dP_tol_psia,
                )
        if reused_hL is not None and np.isfinite(float(reused_hL)):
            hL_try[j] = float(reused_hL)
            _trace(f"energy_vapor_flow hL_flash stage={int(j + 1)}/{int(n_stages)} reused packet")
        else:
            pending_liq.append(j)

        reused_hV = packet_phase_enthalpy_if_compatible_fn(
            current_packet,
            stage_index0=j,
            T_F=float(T_arr[j]),
            P_psia=float(P_arr[j]),
            phase_composition=y_arr[j, :],
            phase="vapor",
            max_abs_dx=packet_phase_tol_vap,
            max_abs_dT_F=packet_dT_tol_F,
            max_abs_dP_psia=packet_dP_tol_psia,
        )
        if reused_hV is None or not np.isfinite(float(reused_hV)):
            reused_hV = packet_phase_enthalpy_if_compatible_fn(
                previous_packet,
                stage_index0=j,
                T_F=float(T_arr[j]),
                P_psia=float(P_arr[j]),
                phase_composition=y_arr[j, :],
                phase="vapor",
                max_abs_dx=packet_phase_tol_vap,
                max_abs_dT_F=packet_dT_tol_F,
                max_abs_dP_psia=packet_dP_tol_psia,
            )
        if reused_hV is not None and np.isfinite(float(reused_hV)):
            hV_try[j] = float(reused_hV)
            _trace(f"energy_vapor_flow hV_flash stage={int(j + 1)}/{int(n_stages)} reused packet")
        else:
            pending_vap.append(j)

    forced_scalar_liq = [j for j in pending_liq if j in force_liq]
    if forced_scalar_liq:
        pending_liq = [j for j in pending_liq if j not in force_liq]

    if callable(batch_fn) and pending_liq:
        try:
            with _thermo_call_context(provider, "energy_vapor_flow_enthalpy_refresh"):
                fres_batch = batch_fn(
                    [float(T_arr[j]) for j in pending_liq],
                    [float(P_arr[j]) for j in pending_liq],
                    [np.asarray(x_arr[j, :], dtype=float).tolist() for j in pending_liq],
                )
            if len(fres_batch) != len(pending_liq):
                raise RuntimeError(
                    "flash_TP_full_batch returned length "
                    f"{len(fres_batch)}; expected {len(pending_liq)}"
                )
            for pos, j in enumerate(pending_liq):
                _x, _y, _K, HL_i, _HV, _Z, _cpL, _cpV, _phase_count = _parse_batch_flash_row(
                    fres_batch[pos],
                    n_components=n_components,
                )
                _ = (_x, _y, _K, _HV, _Z, _cpL, _cpV, _phase_count)
                hL_try[j] = float(HL_i)
                _trace(f"energy_vapor_flow hL_flash stage={int(j + 1)}/{int(n_stages)} batch")
            pending_liq = []
        except Exception:
            pass

    if callable(batch_fn) and pending_vap:
        try:
            with _thermo_call_context(provider, "energy_vapor_flow_enthalpy_refresh"):
                fres_batch = batch_fn(
                    [float(T_arr[j]) for j in pending_vap],
                    [float(P_arr[j]) for j in pending_vap],
                    [np.asarray(y_arr[j, :], dtype=float).tolist() for j in pending_vap],
                )
            if len(fres_batch) != len(pending_vap):
                raise RuntimeError(
                    "flash_TP_full_batch returned length "
                    f"{len(fres_batch)}; expected {len(pending_vap)}"
                )
            for pos, j in enumerate(pending_vap):
                _x, _y, _K, _HL, HV_i, _Z, _cpL, _cpV, _phase_count = _parse_batch_flash_row(
                    fres_batch[pos],
                    n_components=n_components,
                )
                _ = (_x, _y, _K, _HL, _Z, _cpL, _cpV, _phase_count)
                hV_try[j] = float(HV_i)
                _trace(f"energy_vapor_flow hV_flash stage={int(j + 1)}/{int(n_stages)} batch")
            pending_vap = []
        except Exception:
            pass

    for j in [*forced_scalar_liq, *pending_liq]:
        try:
            fres_L = flash_stage_fn(
                provider,
                j,
                float(T_arr[j]),
                float(P_arr[j]),
                x_arr[j, :],
                n_components=n_components,
                thermo_call_category="energy_vapor_flow_enthalpy_refresh",
            )
            hL_try[j] = float(getattr(fres_L, "HL_BTU_lbmol"))
            _trace(f"energy_vapor_flow hL_flash stage={int(j + 1)}/{int(n_stages)} done")
        except Exception:
            pass

    for j in pending_vap:
        try:
            fres_V = flash_stage_fn(
                provider,
                j,
                float(T_arr[j]),
                float(P_arr[j]),
                y_arr[j, :],
                n_components=n_components,
                thermo_call_category="energy_vapor_flow_enthalpy_refresh",
            )
            hV_try[j] = float(getattr(fres_V, "HV_BTU_lbmol"))
            _trace(f"energy_vapor_flow hV_flash stage={int(j + 1)}/{int(n_stages)} done")
        except Exception:
            pass

    hL_out = hL_try if np.any(np.isfinite(hL_try)) else None
    hV_out = hV_try if np.any(np.isfinite(hV_try)) else None
    packet = None
    if hL_out is not None or hV_out is not None:
        packet = packet_factory(
            z_overall_tray=np.asarray(x_arr, dtype=float).reshape((n_stages, n_components)).copy(),
            K_tray=np.full((n_stages, n_components), np.nan, dtype=float),
            HL_BTU_lbmol_tray=np.asarray(hL_try, dtype=float).reshape((n_stages,)).copy(),
            HV_BTU_lbmol_tray=np.asarray(hV_try, dtype=float).reshape((n_stages,)).copy(),
            Z_tray=np.full(n_stages, np.nan, dtype=float),
            T_tray_F=np.asarray(T_arr, dtype=float).reshape((n_stages,)).copy(),
            P_tray_psia=np.asarray(P_arr, dtype=float).reshape((n_stages,)).copy(),
            x_equilibrium_tray=np.asarray(x_arr, dtype=float).reshape((n_stages, n_components)).copy(),
            y_equilibrium_tray=np.asarray(y_arr, dtype=float).reshape((n_stages, n_components)).copy(),
        )
    return EnergyVaporFlowEnthalpyRefreshResult(
        hL_stage_provider=hL_out,
        hV_stage_provider=hV_out,
        packet=packet,
    )
