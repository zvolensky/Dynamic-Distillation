"""
column_rhs_v1.py

Dynamic Distillation - Column RHS (v1)

Updated: 2026-01-12 16:40 (America/New_York)

Notes
-----
- Mass balances on component holdups (liquid + optional vapor)
- Optional energy balances:
    * Legacy temperature-state energy (layout.include_temperature)
    * Option B1 enthalpy-holdup energy (layout.include_energy)
- Pressure diagnostic derived from vapor holdup + volume model
    * Module 8A: supports real-gas Z when available: P = n Z R T / V
- Module 7: Optional thermo diagnostics hook (K, HL, HV) via thermo_provider
- Module 8B: Optional relaxed equilibrium closure using K:
    * When enabled, applies an internal interphase relaxation term that drives
      vapor composition toward y_eq computed from K and x.
    * Time constant is tau_eq_sec (seconds). If ColumnInputs.tau_eq_sec is None,
      we fall back to ColumnSpec.tau_eq_sec when available, else default 10 s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any

import numpy as np

from dynamic_distillation.column_spec_builder_v1 import ColumnSpec
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.thermo_model_v1 import ThermoModel, ConstantCpThermo
from dynamic_distillation.stage_thermo_v1 import flash_TP_full_F_psia
from dynamic_distillation.stage_hydraulics_francis_v1 import compute_francis_weir_liquid_outflow


class ColumnRHSError(RuntimeError):
    """Raised when RHS evaluation fails."""


@dataclass(frozen=True)
class BoundaryFlows:
    reflux_lbmolph: Optional[float] = None
    boilup_lbmolph: Optional[float] = None


@dataclass(frozen=True)
class VolumeModel:
    vapor_volume_ft3_per_stage: Optional[np.ndarray] = None
    default_vapor_volume_ft3: float = 1.0


@dataclass(frozen=True)
class ColumnInputs:
    boundary: BoundaryFlows = BoundaryFlows()
    volume_model: VolumeModel = VolumeModel()

    condenser_alpha: Optional[float] = None
    clamp_alpha: bool = True

    # Legacy temperature-state energy model (only used when layout.include_temperature=True)
    thermo: Optional[ThermoModel] = None

    # Module 7: optional thermo diagnostics hook
    thermo_provider: Optional[Any] = None
    compute_thermo_diag: bool = False

    # Module 8B: equilibrium relaxation using K
    equilibrium_relaxation: bool = False
    tau_eq_sec: Optional[float] = None   # <-- changed: allow None so we can fall back to ColumnSpec

    # Reboiler handling
    # reboiler_mode:
    #   "specified" = use boundary.boilup_lbmolph or ColumnSpec.V_lbmolph[-1]
    #   "duty"      = compute boilup from reboiler duty (requires thermo_provider)
    #   "auto"      = duty if available else specified
    reboiler_mode: str = "auto"
    reboiler_equilibrium: bool = True

    # Optional: cached liquid density per stage (lbmol/ft3) for hydraulics throttling
    rhoL_tray_lbmol_ft3: Optional[np.ndarray] = None

    # Optional: cached thermo results for fallback on flash failure
    K_tray_prev: Optional[np.ndarray] = None
    HL_prev: Optional[np.ndarray] = None
    HV_prev: Optional[np.ndarray] = None
    Zfac_prev: Optional[np.ndarray] = None

    # Reboiler flash cache (used when duty flash fails)
    reb_T_prev: Optional[float] = None
    reb_x_prev: Optional[np.ndarray] = None
    reb_y_prev: Optional[np.ndarray] = None
    reb_beta_prev: Optional[float] = None


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
) -> tuple[np.ndarray, np.ndarray]:
    N = ML_tot.size
    hL = EL_BTU / np.maximum(ML_tot, epsilon_lbmol)
    hV = EV_BTU / np.maximum(MV_tot, epsilon_lbmol)

    dEL = np.zeros(N, dtype=float)
    dEV = np.zeros(N, dtype=float)

    for i in range(N):
        Lin = 0.0 if i == 0 else float(L_out[i - 1])
        hin = hL[i] if i == 0 else hL[i - 1]
        dEL[i] += Lin * hin
        dEL[i] -= float(L_out[i]) * hL[i]

    for i in range(N):
        Vin = 0.0 if i == (N - 1) else float(V_out[i + 1])
        hin = hV[i] if i == (N - 1) else hV[i + 1]
        dEV[i] += Vin * hin
        dEV[i] -= float(V_out[i]) * hV[i]

    dEV[0] += float(Q_cond_BTUph) / 3600.0
    dEL[-1] += float(Q_reb_BTUph) / 3600.0
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
    # If an explicit Feed stream is present, the steady-state internal L/V profiles loaded
    # from Excel/ChemSep typically already include the feed effect (step changes at the feed stage).
    # If we ALSO add feed as an explicit source term, we double-count it and create artificial
    # accumulation (exactly what you observed at the feed stage).
    #
    # Therefore:
    # - If Feed exists (and has non-zero total), we build internally-consistent L/V profiles
    #   from boundary flows + the explicit feed.
    # - Otherwise we fall back to the Excel-provided internal profiles.
    L_out_profile = np.asarray(col.L_lbmolph, dtype=float) / 3600.0
    V_out_profile = np.asarray(col.V_lbmolph, dtype=float) / 3600.0
    if L_out_profile.shape != (N,) or V_out_profile.shape != (N,):
        raise ColumnRHSError("ColumnSpec L/V flow arrays must have shape (n_stages,)")

    reflux = inputs.boundary.reflux_lbmolph
    boilup = inputs.boundary.boilup_lbmolph
    if reflux is None:
        reflux = float(col.L_lbmolph[0])
    reflux_s = float(reflux) / 3600.0

    D = _draw_from_stream(col, "Top", Nc)
    B = _draw_from_stream(col, "Bottom", Nc)

    alpha = _infer_condenser_alpha(col, inputs)
    if inputs.clamp_alpha:
        alpha = float(np.clip(alpha, 0.0, 1.0))

    if y_tray is None:
        raise ColumnRHSError("Vapor holdup required (layout.include_vapor=True).")

    x_topL = _safe_comp_from_holdup(top_L, fallback=x_tray[0, :], eps=layout.epsilon_lbmol)
    y_topV = _safe_comp_from_holdup(top_V, fallback=y_tray[0, :], eps=layout.epsilon_lbmol)
    x_botL = _safe_comp_from_holdup(bottom_L, fallback=x_tray[-1, :], eps=layout.epsilon_lbmol)
    y_botV = _safe_comp_from_holdup(bottom_V, fallback=y_tray[-1, :], eps=layout.epsilon_lbmol)

    # Reboiler stage uses the tray-20 (stage N) composition/temperature.
    # The bottom sump is a separate liquid holdup used only for bottoms draw.
    x_reb_source = x_tray[-1, :]
    y_reb_source = y_tray[-1, :]
    if reboiler_no_holdup and N > 1:
        x_reb_source = x_tray[-2, :]
        y_reb_source = y_tray[-2, :]
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
    duty_btu_ph = _get_reboiler_duty_btu_per_h(col)
    use_duty = False
    if reboiler_mode == "duty":
        use_duty = True
    elif reboiler_mode == "auto":
        use_duty = (boilup is None) and (duty_btu_ph > 0.0)

    boilup_from_duty_lbmolph = None
    y_reb_eq = None
    fres_reb = None
    K_reb = None

    # Reboiler temperature tied to bottom tray (stage N), not sump.
    T_reb = None
    if "tray_T_f" in u:
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

        # Solve reboiler temperature by bubble point when equilibrium is requested
        if inputs.reboiler_equilibrium:
            try:
                T_reb, fres_reb = _bubble_point_T_F(
                    thermo_provider=inputs.thermo_provider,
                    P_psia=P_bot,
                    x=z_bot,
                    T_guess_F=T_reb,
                )
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
                    fres_reb = flash_TP_full_F_psia(
                        inputs.thermo_provider,
                        float(T_reb),
                        float(P_bot),
                        z_bot,
                        n_components=Nc,
                    )
                delta_h = float(fres_reb.HV_BTU_lbmol) - float(fres_reb.HL_BTU_lbmol)
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

    feed_stage0, Fk_L, Fk_V = _feed_component_rates_lbmolps(col, Nc)
    Ft_L = float(np.sum(Fk_L))
    Ft_V = float(np.sum(Fk_V))

    if feed_stage0 is not None and (Ft_L > 0.0 or Ft_V > 0.0):
        L_out = np.zeros(N, dtype=float)
        V_out = np.zeros(N, dtype=float)

        # Liquid: seed at top with reflux; add feed liquid at the feed stage.
        L_out[0] = reflux_s
        for i in range(1, N):
            L_out[i] = L_out[i - 1] + (Ft_L if i == feed_stage0 else 0.0)

        # Vapor: seed at bottom with boilup; add feed vapor at the feed stage.
        V_out[-1] = boilup_s
        for i in range(N - 2, -1, -1):
            V_out[i] = V_out[i + 1] + (Ft_V if i == feed_stage0 else 0.0)
    else:
        L_out = L_out_profile
        V_out = V_out_profile

    # Optional stage hydraulics: compute liquid outflow via Francis weir if geometry is available.
    rhoL_tray = None
    h_ow_ft = None
    L_out_hyd_lbmolph = None
    geom = getattr(col, "geometry", None)
    if geom is not None:
        weir_h = getattr(geom, "weir_height_in_per_stage", None)
        weir_L = getattr(geom, "weir_length_ft_per_stage", None)
        active_area = getattr(geom, "active_area_ft2_per_stage", None)
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
                    hyd = compute_francis_weir_liquid_outflow(
                        ML_lbmol=ML_tray,
                        rhoL_lbmol_ft3=rhoL_tray,
                        active_area_ft2=np.asarray(active_area, dtype=float).reshape((N,)),
                        weir_height_in=np.asarray(weir_h, dtype=float).reshape((N,)),
                        weir_length_ft=np.asarray(weir_L, dtype=float).reshape((N,)),
                    )
                    L_out_hyd_lbmolph = np.asarray(hyd.ML_lbmolph, dtype=float).reshape((N,))
                    h_ow_ft = np.asarray(hyd.h_ow, dtype=float).reshape((N,))
                    L_out_hyd = L_out_hyd_lbmolph / 3600.0
                    valid = (
                        np.isfinite(L_out_hyd)
                        & np.isfinite(weir_L)
                        & (np.asarray(weir_L, dtype=float) > 0.0)
                        & np.isfinite(active_area)
                        & (np.asarray(active_area, dtype=float) > 0.0)
                        & np.isfinite(weir_h)
                        & (np.asarray(weir_h, dtype=float) >= 0.0)
                        & np.isfinite(rhoL_tray)
                        & (rhoL_tray > 0.0)
                    )
                    # Apply to internal stages (stage 2..N-1); stage 1 (index 0) and reboiler (index N-1) excluded.
                    for i in range(1, N - 1):
                        if valid[i]:
                            L_out[i] = float(L_out_hyd[i])
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

    # Use top accumulator composition for condenser/reflux duties.
    if layout.include_top:
        tray_L = tray_L.copy()
        tray_L[0, :] = np.asarray(top_L, dtype=float).copy() if top_L is not None else tray_L[0, :]
        x_tray[0, :] = x_topL

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

    reb_cache_out = None
    if reboiler_no_holdup and N > 0:
        z_in = x_in[-1, :].copy()
        L_in_reb = float(L_in[-1])
        V_out_reb = float(boilup_s)
        y_out = y_reb_eq if y_reb_eq is not None else y_rebV
        x_out = z_in.copy()
        reboiler_flash_done = False
        reboiler_flash_used_cache = False

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
                    reboiler_flash_used_cache = True
                    T_reb = reb_T_prev
                    x_out = reb_x_prev.copy()
                    y_out = reb_y_prev.copy()
                    V_out_reb = max(reb_beta_prev * L_in_reb, 0.0)
                    boilup_s = V_out_reb
                    L_out_reb = max(L_in_reb - V_out_reb, 0.0)
                    y_reb_eq = y_out.copy()
                    reboiler_flash_done = True
            except Exception:
                reboiler_flash_used_cache = False
                reboiler_flash_done = False

        if (not reboiler_flash_done) and inputs.thermo_provider is not None and duty_btu_ph != 0.0 and L_in_reb > layout.epsilon_lbmol:
            # Flash after adding reboiler duty to the incoming liquid enthalpy.
            if "tray_T_f" in u and N > 1:
                T_in = float(np.asarray(u["tray_T_f"], dtype=float).reshape((N,))[-2])
            elif hasattr(col, "T_f") and N > 1:
                T_in = float(np.asarray(col.T_f, dtype=float).reshape((N,))[-2])
            else:
                T_in = float(T_reb)
            try:
                fres_in = flash_TP_full_F_psia(
                    inputs.thermo_provider,
                    float(T_in),
                    float(P_bot),
                    z_in,
                    n_components=Nc,
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
                fres_tmp = flash_TP_full_F_psia(
                    inputs.thermo_provider,
                    float(T_reb),
                    float(P_bot),
                    z_in,
                    n_components=Nc,
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

    V_in = np.zeros(N, dtype=float)
    y_in = np.zeros((N, Nc), dtype=float)
    for i in range(N):
        if i == N - 1:
            V_in[i] = boilup_s
            y_in[i, :] = y_reb_eq if y_reb_eq is not None else y_rebV
        else:
            V_in[i] = V_out[i + 1]
            y_in[i, :] = y_tray[i + 1, :]

    d_tray_L = np.zeros((N, Nc), dtype=float)
    d_tray_V = np.zeros((N, Nc), dtype=float)

    for i in range(N):
        for k in range(Nc):
            feedL = Fk_L[k] if (feed_stage0 == i) else 0.0
            feedV = Fk_V[k] if (feed_stage0 == i) else 0.0

            d_tray_L[i, k] = (
                L_in[i] * x_in[i, k]
                + feedL
                - L_out[i] * x_tray[i, k]
            )

            d_tray_V[i, k] = (
                V_in[i] * y_in[i, k]
                + feedV
                - V_out[i] * y_tray[i, k]
            )

    # Reboiler phase change at the bottom stage (stage N).
    # Converts liquid to vapor at the specified boilup rate.
    if N > 0 and (not reboiler_no_holdup):
        d_tray_L[-1, :] -= boilup_s * x_rebL
        d_tray_V[-1, :] += boilup_s * x_rebL
        d_tray_V[-1, :] -= boilup_s * y_rebV
    if reboiler_no_holdup and N > 0:
        d_tray_L[-1, :] = 0.0
        d_tray_V[-1, :] = 0.0

    d_top_L = d_top_V = None
    if layout.include_top:
        if top_L is None or top_V is None:
            raise ColumnRHSError("layout.include_top=True requires top_L and top_V states.")

        d_top_L = np.zeros(Nc, dtype=float)
        d_top_V = np.zeros(Nc, dtype=float)

        # Stage 1 condenser (index 0): total condenser + liquid drum.
        # All incoming vapor (and any vapor feed at stage 0) is condensed into the drum.
        feedL0 = Fk_L if (feed_stage0 == 0) else 0.0
        feedV0 = Fk_V if (feed_stage0 == 0) else 0.0

        d_top_L += V_in[0] * y_in[0, :]
        if feed_stage0 == 0:
            d_top_L += feedL0 + feedV0

        # Reflux withdrawal (liquid to stage 2) and distillate draw come from the drum.
        d_top_L -= L_out[0] * x_topL
        if D.has_component_breakdown:
            d_top_L -= D.comp_L
            d_top_V -= D.comp_V
        else:
            d_top_L -= D.total_L * x_topL
            d_top_V -= D.total_V * y_topV

        # Condenser has no vapor holdup; remove incoming vapor from tray vapor state.
        d_tray_V[0, :] -= V_in[0] * y_in[0, :]
        if feed_stage0 == 0:
            d_tray_V[0, :] -= feedV0

        # Tie condenser tray liquid holdup to the drum holdup for consistency.
        d_tray_L[0, :] = d_top_L
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

        # Sump is liquid-only holdup; do not couple reboiler boilup to the sump.
        # Bottoms draw is taken from the sump only.
        # (Boilup is handled on the reboiler stage via tray balances.)

    dydt = np.zeros(layout.n_states(), dtype=float)
    sl = _layout_slices(layout)

    if layout.include_top:
        dydt[sl["top_L"]] = d_top_L
        dydt[sl["top_V"]] = d_top_V

    dydt[sl["tray_L"]] = d_tray_L.reshape(-1)
    dydt[sl["tray_V"]] = d_tray_V.reshape(-1)

    if layout.include_bottom:
        dydt[sl["bottom_L"]] = d_bottom_L
        dydt[sl["bottom_V"]] = d_bottom_V

    diag: Dict[str, np.ndarray] = {}

    ML_key = "ML_tot_tray" if "ML_tot_tray" in u else ("ML_tot" if "ML_tot" in u else None)
    MV_key = "MV_tot_tray" if "MV_tot_tray" in u else ("MV_tot" if "MV_tot" in u else None)
    if ML_key is None or MV_key is None:
        raise ColumnRHSError("layout.unpack(y) must provide tray total holdups (ML_tot_tray/MV_tot_tray or ML_tot/MV_tot).")

    diag["ML_tot_tray"] = np.asarray(u[ML_key], dtype=float).copy()
    diag["MV_tot_tray"] = np.asarray(u[MV_key], dtype=float).copy()
    diag["x_tray"] = x_tray.copy()
    diag["y_tray"] = y_tray.copy()
    try:
        mass_resid = np.sum(d_tray_L + d_tray_V, axis=1)
        diag["mass_balance_resid_lbmolps_tray"] = np.asarray(mass_resid, dtype=float).reshape((N,))
    except Exception:
        pass
    try:
        diag["L_out_lbmolph"] = np.asarray(L_out, dtype=float).reshape((N,)) * 3600.0
    except Exception:
        pass
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
    if layout.include_top and top_L is not None:
        diag["ML_tot_tray"][0] = float(np.sum(top_L))
        diag["x_tray"][0, :] = x_topL

    # Base pressure diagnostic (Z defaults to 1)
    diag["P_psia_diag"] = _pressure_diagnostic_psia(col, diag["MV_tot_tray"], inputs.volume_model)

    # -----------------------
    # Thermo block used by Module 7/8A diagnostics and Module 8B equilibrium closure
    # -----------------------
    thermo_cache = None  # (Z_overall, K_tray, HL, HV, Zfac_tray)
    do_thermo = (inputs.thermo_provider is not None) and (inputs.compute_thermo_diag or inputs.equilibrium_relaxation)
    if do_thermo:
        # Temperature for diagnostics
        if "tray_T_f" in u:
            T_tray = np.asarray(u["tray_T_f"], dtype=float).reshape((N,))
        elif hasattr(col, "T_f"):
            T_tray = np.asarray(col.T_f, dtype=float).reshape((N,))
        else:
            T_tray = np.full(N, 100.0, dtype=float)

        # Pressure for diagnostics: prefer column spec if available
        if hasattr(col, "P_psia"):
            P_tray = np.asarray(col.P_psia, dtype=float).reshape((N,))
        else:
            P_tray = np.asarray(diag["P_psia_diag"], dtype=float).reshape((N,))

        # overall z per stage (liquid + vapor holdup)
        Z_overall = np.zeros((N, Nc), dtype=float)
        for i in range(N):
            z = tray_L[i, :].copy()
            if tray_V is not None:
                z = z + tray_V[i, :]
            s = float(np.sum(z))
            if s <= layout.epsilon_lbmol:
                z = x_tray[i, :].copy()
                s = float(np.sum(z))
            Z_overall[i, :] = z / max(s, 1e-300)

        K_tray = (
            np.asarray(inputs.K_tray_prev, dtype=float).reshape((N, Nc)).copy()
            if inputs.K_tray_prev is not None
            else np.ones((N, Nc), dtype=float)
        )
        HL = (
            np.asarray(inputs.HL_prev, dtype=float).reshape((N,)).copy()
            if inputs.HL_prev is not None
            else np.zeros(N, dtype=float)
        )
        HV = (
            np.asarray(inputs.HV_prev, dtype=float).reshape((N,)).copy()
            if inputs.HV_prev is not None
            else np.zeros(N, dtype=float)
        )
        Zfac_tray = (
            np.asarray(inputs.Zfac_prev, dtype=float).reshape((N,)).copy()
            if inputs.Zfac_prev is not None
            else np.ones(N, dtype=float)
        )

        for i in range(N):
            try:
                fres = flash_TP_full_F_psia(
                    inputs.thermo_provider,
                    float(T_tray[i]),
                    float(P_tray[i]),
                    Z_overall[i, :],
                    n_components=Nc,
                )
                K_tray[i, :] = fres.K
                HL[i] = fres.HL_BTU_lbmol
                HV[i] = fres.HV_BTU_lbmol
                if getattr(fres, "Z", None) is not None:
                    Zfac_tray[i] = float(fres.Z)
            except Exception:
                # If flash fails, keep previous values (seeded below) and continue.
                pass

        thermo_cache = (Z_overall, K_tray, HL, HV, Zfac_tray)

        # Module 8A: if Z provided, upgrade pressure diagnostic
        diag["Z_tray"] = Zfac_tray
        diag["P_psia_diag"] = _pressure_diagnostic_psia(col, diag["MV_tot_tray"], inputs.volume_model, Z_factor=Zfac_tray)

        # Module 7 diagnostics output
    if inputs.compute_thermo_diag:
        diag["z_overall_tray"] = Z_overall
        diag["K_tray"] = K_tray
        diag["HL_BTU_lbmol_tray"] = HL
        diag["HV_BTU_lbmol_tray"] = HV

    # -----------------------
    # Module 8B: relaxed equilibrium closure using K
    # -----------------------
    if inputs.equilibrium_relaxation:
        if inputs.thermo_provider is None:
            raise ColumnRHSError("equilibrium_relaxation=True requires thermo_provider.")

        if thermo_cache is None:
            raise ColumnRHSError("equilibrium_relaxation=True requires thermo calculation (thermo_provider).")

        # tau precedence: ColumnInputs overrides ColumnSpec; otherwise default 10 s
        tau = inputs.tau_eq_sec
        if tau is None:
            tau = getattr(col, "tau_eq_sec", 10.0)
        tau = float(tau)

        if not np.isfinite(tau) or tau <= 0.0:
            raise ColumnRHSError("tau_eq_sec must be finite and > 0 when equilibrium_relaxation is enabled.")

        _Z_overall, K_tray, _HL, _HV, _Zfac = thermo_cache

        # y_eq = normalize(K * x)
        y_eq_raw = K_tray * x_tray
        row_sums = np.sum(y_eq_raw, axis=1, keepdims=True)
        safe_sums = np.where(row_sums <= 1e-300, 1.0, row_sums)
        y_eq = y_eq_raw / safe_sums

        bad = (row_sums[:, 0] <= 1e-300)
        if np.any(bad):
            y_eq[bad, :] = y_tray[bad, :]

        MV = diag["MV_tot_tray"].reshape((N, 1))
        transfer = (MV / tau) * (y_eq - y_tray)  # (N,Nc) lbmol/s, sums to 0 per stage

        dydt[sl["tray_V"]] += transfer.reshape(-1)
        dydt[sl["tray_L"]] -= transfer.reshape(-1)

        diag["y_eq_tray"] = y_eq
        diag["eq_transfer_lbmolps_tray"] = transfer

    # -----------------------
    # Option B1 energy holdup
    # -----------------------
    if bool(getattr(layout, "include_energy", False)):
        if "tray_EL_BTU" not in u:
            raise ColumnRHSError("layout.include_energy=True requires tray_EL_BTU in layout.unpack(y).")
        if layout.include_vapor and ("tray_EV_BTU" not in u):
            raise ColumnRHSError("layout.include_energy=True and include_vapor=True requires tray_EV_BTU in layout.unpack(y).")

        EL = np.asarray(u["tray_EL_BTU"], dtype=float).reshape((N,))
        EV = np.asarray(u["tray_EV_BTU"], dtype=float).reshape((N,)) if layout.include_vapor else np.zeros(N, dtype=float)

        Qc_BTUph = 0.0
        Qr_BTUph = 0.0
        specs = getattr(col, "specs", None) or {}
        if isinstance(specs, dict):
            if "Condenser Duty (Btu/h)" in specs:
                Qc_BTUph = float(specs["Condenser Duty (Btu/h)"])
            if "Reboiler Duty (Btu/h)" in specs:
                Qr_BTUph = float(specs["Reboiler Duty (Btu/h)"])

        if hasattr(col, "duties"):
            if getattr(col.duties, "q_cond_btu_per_h", None) is not None and Qc_BTUph == 0.0:
                Qc_BTUph = float(col.duties.q_cond_btu_per_h)
            if getattr(col.duties, "q_reb_btu_per_h", None) is not None and Qr_BTUph == 0.0:
                Qr_BTUph = float(col.duties.q_reb_btu_per_h)

        dEL, dEV = _energy_derivatives_b1(
            L_out=L_out,
            V_out=V_out,
            ML_tot=diag["ML_tot_tray"],
            MV_tot=diag["MV_tot_tray"],
            EL_BTU=EL,
            EV_BTU=EV,
            Q_cond_BTUph=Qc_BTUph,
            Q_reb_BTUph=Qr_BTUph,
            epsilon_lbmol=layout.epsilon_lbmol,
        )

        dydt[sl["tray_EL_BTU"]] = dEL
        if layout.include_vapor:
            dydt[sl["tray_EV_BTU"]] = dEV

        diag["dEL_BTU_per_s"] = dEL.copy()
        diag["dEV_BTU_per_s"] = dEV.copy()
        try:
            diag["energy_balance_resid_BTUps_tray"] = (dEL + dEV).copy()
        except Exception:
            pass

    # -----------------------
    # Legacy temperature-state energy balance (kept intact)
    # -----------------------
    if bool(getattr(layout, "include_temperature", False)):
        thermo = inputs.thermo
        if thermo is None:
            thermo = ConstantCpThermo(
                cp_liq_components=np.full(Nc, 30.0, dtype=float),
                cp_vap_components=np.full(Nc, 20.0, dtype=float),
                tref_f=60.0,
            )

        tray_T = u["tray_T_f"].reshape(N)
        top_T = float(u["top_T_f"][0]) if layout.include_top and "top_T_f" in u else None
        bot_T = float(u["bottom_T_f"][0]) if layout.include_bottom and "bottom_T_f" in u else None

        P_tray = np.asarray(col.P_psia, dtype=float).reshape(N) if hasattr(col, "P_psia") else diag["P_psia_diag"].reshape(N)

        Qc_BTUph = _get_condenser_duty_btu_per_h(col)
        Qr_BTUph = _get_reboiler_duty_btu_per_h(col)

        dT_tray = np.zeros(N, dtype=float)
        use_provider_cp = (
            inputs.thermo_provider is not None
            and hasattr(inputs.thermo_provider, "cp_liq_vap_btu_per_lbmolF")
        )

        for i in range(N):
            T_L_in = top_T if (i == 0 and top_T is not None) else (tray_T[i - 1] if i > 0 else tray_T[i])
            if i == N - 1:
                if "T_reb" in locals() and T_reb is not None:
                    T_V_in = float(T_reb)
                else:
                    T_V_in = bot_T if bot_T is not None else tray_T[i]
            else:
                T_V_in = tray_T[i + 1] if i < N - 1 else tray_T[i]

            hL_in = thermo.h_liq_btu_per_lbmol(T_L_in, P_tray[i], x_in[i, :])
            hV_in = thermo.h_vap_btu_per_lbmol(T_V_in, P_tray[i], y_in[i, :])

            hL_out = thermo.h_liq_btu_per_lbmol(tray_T[i], P_tray[i], x_tray[i, :])
            hV_out = thermo.h_vap_btu_per_lbmol(tray_T[i], P_tray[i], y_tray[i, :])

            q_feed = 0.0
            if feed_stage0 == i:
                sF = col.streams.get("Feed")
                T_feed = float(sF.temperature_f) if (sF is not None and sF.temperature_f is not None) else float(tray_T[i])
                z_feed = _safe_feed_comp(col, i)
                hF_L = thermo.h_liq_btu_per_lbmol(T_feed, P_tray[i], z_feed)
                hF_V = thermo.h_vap_btu_per_lbmol(T_feed, P_tray[i], z_feed)
                q_feed = float(np.sum(Fk_L)) * hF_L + float(np.sum(Fk_V)) * hF_V

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

            if use_provider_cp:
                z_for_cp = tray_L[i, :].copy()
                if tray_V is not None:
                    z_for_cp = z_for_cp + tray_V[i, :]
                s = float(np.sum(z_for_cp))
                if s <= layout.epsilon_lbmol:
                    z_for_cp = x_tray[i, :].copy()
                    s = float(np.sum(z_for_cp))
                z_for_cp = z_for_cp / max(s, 1e-300)
                try:
                    cpL, cpV = inputs.thermo_provider.cp_liq_vap_btu_per_lbmolF(
                        tray_T[i], P_tray[i], z_for_cp
                    )
                except Exception:
                    cpL = cpV = None
            else:
                cpL = cpV = None

            if cpL is None or cpV is None:
                cpL = thermo.cp_liq_btu_per_lbmolF(tray_T[i], P_tray[i], x_tray[i, :])
                cpV = thermo.cp_vap_btu_per_lbmolF(tray_T[i], P_tray[i], y_tray[i, :])

            C = diag["ML_tot_tray"][i] * cpL + diag["MV_tot_tray"][i] * cpV
            if C <= 0.0:
                raise ColumnRHSError("Non-positive tray heat capacity encountered.")

            dT_tray[i] = dE / C

        dydt[sl["tray_T_f"]] = dT_tray
        diag["dT_tray_F_per_s"] = dT_tray.copy()

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
                    try:
                        cp_sump, _cpv = inputs.thermo_provider.cp_liq_vap_btu_per_lbmolF(
                            float(T_sump_use), P_bot, x_sump
                        )
                    except Exception:
                        cp_sump = None
                else:
                    cp_sump = None
                if cp_sump is None:
                    cp_sump = thermo.cp_liq_btu_per_lbmolF(float(T_sump_use), P_bot, x_sump)

                dE_sump = 0.0
                dE_sump += float(L_out[-1]) * h_in
                dE_sump -= float(B.total_L) * h_sump

                C = max(M_sump * cp_sump, 1e-12)
                dT_sump = dE_sump / C

                # If thermo_provider available, relax sump temperature to flash/bubble-point value.
                if inputs.thermo_provider is not None:
                    try:
                        T_eq, _ = _bubble_point_T_F(
                            thermo_provider=inputs.thermo_provider,
                            P_psia=P_bot,
                            x=x_sump,
                            T_guess_F=T_sump_use,
                        )
                        tau_sump = 1.0  # seconds, fast relaxation toward equilibrium
                        dT_sump = (float(T_eq) - float(T_sump_use)) / max(tau_sump, 1e-6)
                    except Exception:
                        pass
            else:
                dT_sump = 0.0

            dydt[sl["bottom_T_f"]] = dT_sump
            diag["dT_sump_F_per_s"] = float(dT_sump)

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
        comp = np.zeros(Nc, dtype=float)
        for k, cname in enumerate(col.components_excel):
            v = s.component_molar_flows_lbmolph.get(cname)
            comp[k] = 0.0 if v is None else float(v) / 3600.0
        comp_L = (1.0 - vf) * comp
        comp_V = vf * comp
        return Draw(total_L, total_V, comp_L, comp_V, True)

    return Draw(total_L, total_V, np.zeros(Nc), np.zeros(Nc), False)


def _safe_comp_from_holdup(holdup: Optional[np.ndarray], fallback: np.ndarray, eps: float) -> np.ndarray:
    if holdup is None:
        return np.asarray(fallback, dtype=float).copy()
    h = np.asarray(holdup, dtype=float).copy()
    tot = float(np.sum(h))
    if tot <= eps:
        return np.asarray(fallback, dtype=float).copy()
    return h / tot


def _feed_component_rates_lbmolps(col: ColumnSpec, Nc: int) -> Tuple[Optional[int], np.ndarray, np.ndarray]:
    s = col.streams.get("Feed")
    if s is None or s.stage_1based is None or s.total_molar_flow_lbmolph is None:
        return None, np.zeros(Nc), np.zeros(Nc)

    stage0 = int(s.stage_1based) - 1
    Ft = float(s.total_molar_flow_lbmolph) / 3600.0
    vf = float(s.vapor_fraction) if s.vapor_fraction is not None else 0.0
    vf = float(np.clip(vf, 0.0, 1.0))

    if s.component_molar_flows_lbmolph:
        Fk = np.zeros(Nc, dtype=float)
        for k, cname in enumerate(col.components_excel):
            v = s.component_molar_flows_lbmolph.get(cname)
            Fk[k] = 0.0 if v is None else float(v) / 3600.0
    else:
        z = np.asarray(col.x0[stage0, :], dtype=float).copy()
        z = z / max(float(np.sum(z)), 1e-300)
        Fk = Ft * z

    return stage0, (1.0 - vf) * Fk, vf * Fk


def _safe_feed_comp(col: ColumnSpec, stage0: int) -> np.ndarray:
    return np.asarray(col.x0[stage0, :], dtype=float).copy()


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


def _bubble_point_T_F(
    *,
    thermo_provider: Any,
    P_psia: float,
    x: np.ndarray,
    T_guess_F: Optional[float] = None,
    T_min_F: float = 50.0,
    T_max_F: float = 600.0,
    max_iter: int = 40,
    beta_target: float = 1e-6,
) -> Tuple[float, Any]:
    """
    Solve for bubble point temperature (F) at fixed pressure and liquid composition.
    Uses TP flash to evaluate K(T) and solves sum(K*x) = 1 by bisection.
    Returns (T_F, flash_result).
    """
    x = np.asarray(x, dtype=float).reshape((-1,))
    x = x / max(float(np.sum(x)), 1e-300)

    def eval_f(T_F: float):
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
        return fval, beta, fres

    # Initial guess
    if T_guess_F is None or not np.isfinite(T_guess_F):
        T_guess_F = 200.0

    # Coarse scan to find a sign change bracket
    n_scan = 21
    Ts = np.linspace(T_min_F, T_max_F, n_scan)
    fs = []
    fres_list = []
    for T in Ts:
        f, beta, fres = eval_f(float(T))
        fs.append(f)
        fres_list.append(fres)

    # Find sign-change intervals; pick the one closest to T_guess.
    # Track any exact roots to avoid snapping to endpoints.
    bracket = None
    best_dist = float("inf")
    exact_roots = []
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
        # No sign change; return the temperature with smallest |f|,
        # breaking ties by proximity to the initial guess.
        candidates = []
        for T, f, fres in zip(Ts, fs, fres_list):
            candidates.append((abs(float(f)), abs(float(T) - float(T_guess_F)), float(T), fres))
        candidates.sort(key=lambda r: (r[0], r[1]))
        _fabs, _d, T_best, fres_best = candidates[0]
        return float(T_best), fres_best

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
        if abs(f_m) < 1e-8:
            return T_m, fres_mid
        if f_a * f_m < 0.0:
            T_b, f_b = T_m, f_m
        else:
            T_a, f_a = T_m, f_m
    return 0.5 * (T_a + T_b), fres_mid
