"""
column_rhs_v1.py

Dynamic Distillation - Right-Hand Side (RHS) function for column ODE integration.

PURPOSE
-------
Compute time derivatives (dy/dt) for the distillation column state vector.
Implements mass and energy balances for all stages, hydraulic dynamics, 
thermo diagnostics, and optional equilibrium relaxation.

INPUTS
------
t : float
    Current simulation time (s).
y : np.ndarray
    State vector (packed by StateVectorLayout): component holdups,
    optional vapor holdups, optional temperatures, optional energy holdups.
column_inputs : ColumnInputs
    Boundary conditions: reflux/boilup rates, distillate/bottoms rates,
    feed conditions, optional thermo provider.
column_spec : ColumnSpec
    Column geometry and specifications (stages, components, feeds, etc.).
layout : StateVectorLayout
    Describes how state vector is packed/unpacked.
thermo_provider : Optional[ThermoProvider]
    Optional provider for flash calculations and diagnostics.

OUTPUTS
-------
dy : np.ndarray
    Time derivatives matching the shape of state vector y.
diag : Dict[str, Any]
    Diagnostic outputs for logging/monitoring:
        - Pressures (P_spec, P_diag), compositions (x, y)
        - Thermo properties (K, HL, HV, Z) when available
        - Flow rates, holdups, etc.

DEPENDENCIES
------------
from dynamic_distillation.column_spec_builder_v1 : ColumnSpec, ColumnGeometry
from dynamic_distillation.state_vector_layout_v1 : StateVectorLayout
from dynamic_distillation.thermo_model_v1 : ThermoModel, ConstantCpThermo
from dynamic_distillation.stage_thermo_v1 : flash_TP_full_F_psia
from dynamic_distillation.stage_hydraulics_francis_v1 : compute_francis_weir_liquid_outflow

ASSUMPTIONS & CONSTRAINTS
--------------------------
- State vector y is already unpacked; caller manages layout
- All stage pressures must be positive; column_spec.P_psia is spec/operating pressure
- Thermo provider (if used) must support simultaneous multi-stage flash calls
- Energy balance requires consistent reference temperature (T_ref) across modules
- Stage index 0 = condenser; Stage N-1 = reboiler (may have zero vapor)

SIDE EFFECTS / STATE MUTATIONS
-------------------------------
- Modifies diag dict in-place (caller owns dict; this module populates it)
- Does not modify y, column_spec, layout, or column_inputs
- Calls to thermo_provider may cache thermo results (cached state internal to provider)

PERFORMANCE NOTES
-----------------
- Typical cost per RHS call: 0.1–1 ms (depends on stage count, thermo mode)
- Main bottleneck: Thermo provider flash calls (can be 10-50 ms if full calculations)
- When thermo throttled (e.g., --thermo-every N): intermediate steps ~0.1 ms
- Pressure diagnostic (Module 8A) uses PV equation of state: fast, no flash needed
- Energy balance (Option B1): adds ~5% overhead vs. temperature-only

ERROR HANDLING
--------------
- Raises ColumnRHSError if:
    * Invalid state vector size (shape mismatch with layout)
    * Invalid composition (NaN, negative, or non-normalized)
    * Invalid pressures (≤0 psia)
    * Required thermo provider unavailable when equilibrium_relaxation=True
    * Hydraulics computation fails (e.g., zero/negative densities)

VERSION / COMPATIBILITY
-----------------------
v1.0 (current):
    - Explicit Euler time-stepping compatible
    - Backward compatible with legacy temperature-state energy (layout.include_temperature)
    - Module 8B (equilibrium relaxation) optional; defaults to disabled
    - Module 8A (real-gas Z) optional; defaults to Z=1.0

NOTES / KEY FEATURES
--------------------
Created: 2026-01-11 (America/New_York)
Updated: 2026-01-12 16:40 (America/New_York)

- Mass balances on component holdups (liquid + optional vapor)
- Optional energy balances:
    * Legacy temperature-state energy (layout.include_temperature)
    * Option B1 enthalpy-holdup energy (layout.include_energy)
- Pressure diagnostic derived from vapor holdup + volume model (Module 8A):
    * Supports real-gas Z when available: P = n Z R T / V
- Optional thermo diagnostics hook: K, HL, HV via thermo_provider (Module 7)
- Optional relaxed equilibrium closure using K (Module 8B):
    * Applies internal interphase relaxation driving vapor composition 
      toward y_eq computed from K and x
    * Time constant tau_eq_sec (seconds); defaults to 10 s if not specified

EXAMPLE USAGE
-------------
    layout = StateVectorLayout(n_stages=20, n_components=3, 
                               include_vapor=True, include_temperature=True)
    y0 = layout.pack_state(ML, MV, T, ...)
    
    inputs = ColumnInputs(reflux_lbmolph=50.0, boilup_lbmolph=60.0,
                          volume_model=VolumeModel.TOTAL)
    
    dy, diag = column_rhs(t=0.0, y=y0, column_inputs=inputs, 
                          column_spec=col_spec, layout=layout,
                          thermo_provider=provider)
    
    print(f"dML/dt = {diag['dML_dt']}")
    print(f"P_diagnostic = {diag['P_psia_diag']}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any

import numpy as np

from dynamic_distillation.column_spec_builder_v1 import ColumnSpec, ColumnGeometry
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

    condenser_alpha: Optional[float] = None
    clamp_alpha: bool = True
    # Condenser duty handling:
    #   "total-condense" = compute duty by condensing all stage-2 vapor (current behavior)
    #   "specified"      = use specified/overridden condenser duty directly
    condenser_duty_mode: str = "total-condense"
    condenser_duty_btu_per_h: Optional[float] = None
    # Optional duty trim applied on top of computed total-condense duty.
    condenser_duty_trim_btu_per_h: Optional[float] = None

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
    # Optional fixed condenser pressure drop (psi), applied stage 2 -> stage 1
    # in hydraulic pressure-profile mode.
    condenser_pressure_drop_psi: Optional[float] = None
    # Vapor-space volume for reflux drum / top accumulator pressure state.
    # If not provided, stage-1 vapor volume from volume_model is used.
    top_drum_vapor_volume_ft3: Optional[float] = None
    # Optional total reflux-drum volume for dynamic vapor-space update:
    # V_vap = V_total - V_liq(top holdup, rho_liq).
    top_drum_total_volume_ft3: Optional[float] = None
    # Vapor flow model
    # "profile" = use Excel V profile (or feed-adjusted profile)
    # "energy"  = compute V_out from energy balance with dT/dt target
    vapor_flow_model: str = "profile"
    dry_tray_K: float = 1.0
    vapor_holdup_relaxation_sec: Optional[float] = None
    component_mw_lbm_per_lbmol: Optional[np.ndarray] = None
    P_tray_prev: Optional[np.ndarray] = None
    vapor_flow_relaxation_sec: Optional[float] = None
    V_out_prev_lbmolph: Optional[np.ndarray] = None
    dT_tray_target_F_per_s: Optional[np.ndarray] = None
    thermo_refresh_dT_F: Optional[float] = None
    thermo_refresh_dP_psia: Optional[float] = None
    thermo_refresh_dx: Optional[float] = None
    T_tray_prev_F: Optional[np.ndarray] = None
    Z_overall_prev: Optional[np.ndarray] = None
    # Clamp for stage N-1 vapor flow as a ratio of boilup in energy mode.
    reboiler_neighbor_vflow_hi_ratio: float = 1.02
    reboiler_neighbor_vflow_lo_ratio: float = 0.98
    # When True and thermo_provider is available, split feed with a TP flash
    # at feed-stage pressure instead of using stream vapor_fraction directly.
    flash_feed_at_stage_conditions: bool = True

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
    total_condenser: bool = True,
    max_abs_h_btu_per_lbmol: float = 1.0e6,
    no_liquid_holdup_mask: Optional[np.ndarray] = None,
    no_vapor_holdup_mask: Optional[np.ndarray] = None,
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

    # For a total condenser with no vapor outflow from stage 1, condenser duty
    # is applied to liquid energy (condensed phase), not vapor energy holdup.
    if bool(total_condenser):
        dEL[0] += float(Q_cond_BTUph) / 3600.0
    else:
        dEV[0] += float(Q_cond_BTUph) / 3600.0
    dEL[-1] += float(Q_reb_BTUph) / 3600.0

    if no_liquid_holdup_mask is not None:
        try:
            ml_mask = np.asarray(no_liquid_holdup_mask, dtype=bool).reshape((N,))
            dEL[ml_mask] = 0.0
        except Exception:
            pass
    if no_vapor_holdup_mask is not None:
        try:
            mv_mask = np.asarray(no_vapor_holdup_mask, dtype=bool).reshape((N,))
            dEV[mv_mask] = 0.0
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

    reflux = inputs.boundary.reflux_lbmolph
    boilup = inputs.boundary.boilup_lbmolph
    if reflux is None:
        reflux = float(col.L_lbmolph[0])
    reflux_s = float(reflux) / 3600.0

    D = _draw_from_stream(col, "Top", Nc)
    B = _draw_from_stream(col, "Bottom", Nc)
    D = _override_draw_total_lbmolph(D, inputs.boundary.distillate_lbmolph, prefer_liquid=True)
    B = _override_draw_total_lbmolph(B, inputs.boundary.bottoms_lbmolph, prefer_liquid=True)

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
    duty_btu_ph = _resolve_reboiler_duty_btu_per_h(col=col, inputs=inputs)
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

    feed_stage0, Fk_L, Fk_V = _feed_component_rates_lbmolps(
        col,
        Nc,
        thermo_provider=inputs.thermo_provider,
        P_tray_psia=inputs.P_tray_prev,
        flash_feed_at_stage_conditions=bool(inputs.flash_feed_at_stage_conditions),
    )
    Ft_L = float(np.sum(Fk_L))
    Ft_V = float(np.sum(Fk_V))
    Ft_feed = Ft_L + Ft_V
    feed_vf_effective = (Ft_V / Ft_feed) if Ft_feed > 1e-300 else np.nan

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

    vflow_diag = None
    # Vapor flows via energy balance (dynamic closure).
    if (inputs.vapor_flow_model or "").strip().lower() == "energy":
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
                hL_in = thermo.h_liq_btu_per_lbmol(T_L_in, P_tray_energy[i], x_in[i, :])
                hL_out = thermo.h_liq_btu_per_lbmol(float(T_tray_for_v[i]), P_tray_energy[i], x_tray[i, :])

            if HV_cache is not None:
                if i < (N - 1):
                    hV_in = float(HV_cache[i + 1])
                else:
                    hV_in = float(HV_cache[i])
                hV_out = float(HV_cache[i])
            else:
                hV_in = thermo.h_vap_btu_per_lbmol(T_V_in, P_tray_energy[i], y_in_i)
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
            )

            Q_i = 0.0
            if i == 0:
                Q_i += float(_get_condenser_duty_btu_per_h(col)) / 3600.0
            if i == (N - 1):
                Q_i += float(duty_btu_ph) / 3600.0

            use_provider_cp = (
                inputs.thermo_provider is not None
                and hasattr(inputs.thermo_provider, "cp_liq_vap_btu_per_lbmolF")
            )
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
                        float(T_tray_for_v[i]), float(P_tray_energy[i]), z_for_cp
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
            numer = (
                L_in[i] * (hL_in - hL_out)
                + V_in_i * (hV_in - hL_out)
                + q_feed
                - ft_feed_i * hL_out
                + Q_i
                - dE_target
            )

            vflow_denom[i] = float(denom)
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
                V_hi = min(V_hi, vflow_reb_neighbor_up_ratio * float(boilup_s))
                if float(boilup_s) > layout.epsilon_lbmol:
                    V_lo = max(V_lo, vflow_reb_neighbor_down_ratio * float(boilup_s))

            vflow_limit_hi[i] = float(V_hi) * 3600.0
            vflow_limit_lo[i] = float(V_lo) * 3600.0
            clamped = False
            if V_calc > V_hi:
                V_calc = V_hi
                clamped = True
            elif V_calc < V_lo:
                V_calc = V_lo
                clamped = True
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
            "vflow_relax_alpha": vflow_alpha,
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

    P_tray_hyd = None
    P_top_drum_psia = None
    V_top_drum_vapor_ft3 = None
    V_top_drum_liquid_ft3 = None
    rho_top_drum_liquid_lbmol_ft3 = None
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
                z_top = float(Z_for_p[0]) if np.size(Z_for_p) > 0 else 1.0
                top_vap_vol_ft3 = None
                top_liq_vol_ft3 = None
                rho_top_liq = None
                top_total_vol_ft3 = None
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
                        top_vap_vol_ft3 = float(top_total_vol_ft3) - float(top_liq_vol_ft3)
                        if top_vap_vol_ft3 < 1e-3:
                            top_vap_vol_ft3 = 1e-3
                    elif inputs.top_drum_vapor_volume_ft3 is not None:
                        try:
                            v_try = float(inputs.top_drum_vapor_volume_ft3)
                            if np.isfinite(v_try) and v_try > 0.0:
                                top_vap_vol_ft3 = min(v_try, float(top_total_vol_ft3))
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
                    P_top_drum_psia = _compute_top_drum_pressure_psia(
                        top_V=np.asarray(top_V, dtype=float).reshape((Nc,)),
                        top_T_F=float(T_tray_for_p[0]),
                        Z_top=float(z_top),
                        top_vapor_volume_ft3=float(top_vap_vol_ft3),
                    )
                    if P_top_drum_psia is not None and np.isfinite(float(P_top_drum_psia)) and float(P_top_drum_psia) > 0.0:
                        top_anchor_from_holdup = float(P_top_drum_psia)

            top_anchor_psia = inputs.pressure_top_anchor_psia
            if top_anchor_psia is None and top_anchor_from_holdup is not None:
                top_anchor_psia = float(top_anchor_from_holdup)

            P_tray_hyd = _pressure_profile_hydraulic_psia(
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
            )

    # Condenser mass split:
    # duty drives how much stage-2 vapor is condensed into top liquid holdup
    # versus carried into top vapor holdup.
    V_condensed_in_lbmolps = float(V_in[0]) if N > 0 else 0.0
    V_to_top_drum_lbmolps = 0.0
    V_condensed_top_lbmolps = 0.0
    Q_cond_mass_used_BTUph = None
    Q_cond_total_req_BTUph = None
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
    x_cond_diag = None
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
        x_condL = _safe_comp_from_holdup(tray_L[0, :], fallback=y_in[0, :], eps=layout.epsilon_lbmol)
        x_cond_diag = np.asarray(x_condL, dtype=float).reshape((Nc,))
        L_cond_to_top_lbmolps = max(
            0.0,
            float(V_condensed_in_lbmolps) + float(V_condensed_top_lbmolps),
        )
        if feed_stage0 == 0:
            L_cond_to_top_lbmolps += float(np.sum(feedL0 + feedV0))

        d_top_L += float(L_cond_to_top_lbmolps) * x_condL
        d_top_V += float(V_to_top_drum_lbmolps) * y_in[0, :]
        d_top_V -= float(V_condensed_top_lbmolps) * y_topV

        # Reflux withdrawal (liquid to stage 2) and distillate draw come from the drum.
        d_top_L -= L_out[0] * x_topL
        if D.has_component_breakdown:
            d_top_L -= D.comp_L
            d_top_V -= D.comp_V
        else:
            d_top_L -= D.total_L * x_topL
            d_top_V -= D.total_V * y_topV

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

        # Sump is liquid-only holdup; do not couple reboiler boilup to the sump.
        # Bottoms draw is taken from the sump only.
        # (Boilup is handled on the reboiler stage via tray balances.)

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
    if vflow_diag is not None:
        for k, v in vflow_diag.items():
            diag[k] = v

    ML_key = "ML_tot_tray" if "ML_tot_tray" in u else ("ML_tot" if "ML_tot" in u else None)
    MV_key = "MV_tot_tray" if "MV_tot_tray" in u else ("MV_tot" if "MV_tot" in u else None)
    if ML_key is None or MV_key is None:
        raise ColumnRHSError("layout.unpack(y) must provide tray total holdups (ML_tot_tray/MV_tot_tray or ML_tot/MV_tot).")

    diag["ML_tot_tray"] = np.asarray(u[ML_key], dtype=float).copy()
    diag["MV_tot_tray"] = np.asarray(u[MV_key], dtype=float).copy()
    diag["x_tray"] = x_tray.copy()
    diag["y_tray"] = y_tray.copy()
    if P_tray_hyd is not None:
        try:
            diag["P_psia_hyd"] = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
        except Exception:
            pass
    if P_top_drum_psia is not None and np.isfinite(float(P_top_drum_psia)):
        diag["P_top_drum_psia"] = np.array([float(P_top_drum_psia)], dtype=float)
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
    if Q_cond_mass_used_BTUph is not None and np.isfinite(float(Q_cond_mass_used_BTUph)):
        diag["Q_cond_mass_used_BTUph"] = np.array([float(Q_cond_mass_used_BTUph)], dtype=float)
    if Q_cond_total_req_BTUph is not None and np.isfinite(float(Q_cond_total_req_BTUph)):
        diag["Q_cond_mass_total_req_BTUph"] = np.array([float(Q_cond_total_req_BTUph)], dtype=float)
    diag["Q_cond_mass_mode_total_condense"] = np.array(
        [1.0 if str(condenser_mass_mode) == "total-condense" else 0.0], dtype=float
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
        if P_tray_hyd is not None:
            try:
                P_tray = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
            except Exception:
                pass

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
                T_prev = np.asarray(inputs.T_tray_prev_F, dtype=float).reshape((N,))
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
                P_prev = np.asarray(inputs.P_tray_prev, dtype=float).reshape((N,))
            except Exception:
                P_prev = None

        Z_prev = None
        if inputs.Z_overall_prev is not None:
            try:
                Z_prev = np.asarray(inputs.Z_overall_prev, dtype=float).reshape((N, Nc))
            except Exception:
                Z_prev = None

        flash_skipped = np.zeros(N, dtype=float)
        flash_refreshed = np.zeros(N, dtype=float)

        for i in range(N):
            gate_active = False
            gate_pass = True
            if dT_thresh is not None:
                gate_active = True
                try:
                    if T_prev is None or not (np.isfinite(T_prev[i]) and np.isfinite(T_tray[i])):
                        gate_pass = False
                    else:
                        gate_pass = gate_pass and (abs(float(T_tray[i]) - float(T_prev[i])) < dT_thresh)
                except Exception:
                    gate_pass = False

            if dP_thresh is not None:
                gate_active = True
                try:
                    if P_prev is None or not (np.isfinite(P_prev[i]) and np.isfinite(P_tray[i])):
                        gate_pass = False
                    else:
                        gate_pass = gate_pass and (abs(float(P_tray[i]) - float(P_prev[i])) < dP_thresh)
                except Exception:
                    gate_pass = False

            if dX_thresh is not None:
                gate_active = True
                try:
                    if Z_prev is None:
                        gate_pass = False
                    else:
                        dz = np.asarray(Z_overall[i, :] - Z_prev[i, :], dtype=float)
                        if not np.all(np.isfinite(dz)):
                            gate_pass = False
                        else:
                            gate_pass = gate_pass and (float(np.max(np.abs(dz))) < dX_thresh)
                except Exception:
                    gate_pass = False

            if gate_active and gate_pass:
                flash_skipped[i] = 1.0
                continue
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
                flash_refreshed[i] = 1.0
            except Exception:
                # If flash fails, keep previous values (seeded below) and continue.
                pass

        thermo_cache = (Z_overall, K_tray, HL, HV, Zfac_tray)

        # Module 8A: if Z provided, upgrade pressure diagnostic
        diag["Z_tray"] = Zfac_tray
        diag["P_psia_diag"] = _pressure_diagnostic_psia(col, diag["MV_tot_tray"], inputs.volume_model, Z_factor=Zfac_tray)
        diag["thermo_flash_skipped"] = flash_skipped
        diag["thermo_flash_refreshed"] = flash_refreshed

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

        for i in range(N):
            z_i = np.asarray(_Z_overall[i, :], dtype=float).reshape((Nc,))
            zsum = float(np.sum(z_i))
            if (not np.isfinite(zsum)) or zsum <= 1e-300:
                z_i = np.asarray(x_tray[i, :], dtype=float).reshape((Nc,))
                zsum = float(np.sum(z_i))
            z_i = z_i / max(zsum, 1e-300)

            K_i = np.asarray(K_tray[i, :], dtype=float).reshape((Nc,))
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

        Mtot_col = Mtot.reshape((N, 1))
        V_target = beta_eq.reshape((N, 1)) * Mtot_col * y_eq
        transfer = (V_target - tray_V) / float(tau)  # (N,Nc) lbmol/s

        # No interphase transfer on total-condenser tray (stage 1).
        transfer[0, :] = 0.0
        # No interphase transfer on no-holdup reboiler stage.
        if reboiler_no_holdup and N > 0:
            transfer[-1, :] = 0.0

        dydt[sl["tray_V"]] += transfer.reshape(-1)
        dydt[sl["tray_L"]] -= transfer.reshape(-1)

        diag["x_eq_tray"] = x_eq
        diag["y_eq_tray"] = y_eq
        diag["beta_eq_tray"] = beta_eq.reshape((N,))
        diag["eq_transfer_lbmolps_tray"] = transfer
        diag["eq_phase_change_lbmolps_tray"] = np.sum(transfer, axis=1).reshape((N,))

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

        Qc_BTUph, Qc_calc_BTUph, T_cond_bubble_F, condenser_duty_mode = _resolve_condenser_duty_btu_per_h(
            col=col,
            inputs=inputs,
            N=N,
            tray_T_F=T_tray_q,
            P_tray_psia=P_tray_q,
            V_in_lbmolps=V_in,
            y_in=y_in,
            epsilon_lbmol=float(layout.epsilon_lbmol),
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
            total_condenser=bool(condenser_is_total),
            max_abs_h_btu_per_lbmol=1.0e6,
            no_liquid_holdup_mask=no_liquid_holdup,
            no_vapor_holdup_mask=no_vapor_holdup,
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
        bot_T = float(u["bottom_T_f"][0]) if layout.include_bottom and "bottom_T_f" in u else None

        P_tray = np.asarray(col.P_psia, dtype=float).reshape(N) if hasattr(col, "P_psia") else diag["P_psia_diag"].reshape(N)
        if P_tray_hyd is not None:
            try:
                P_tray = np.asarray(P_tray_hyd, dtype=float).reshape((N,))
            except Exception:
                pass

        Qc_BTUph, Qc_calc_BTUph, T_cond_bubble_F, condenser_duty_mode = _resolve_condenser_duty_btu_per_h(
            col=col,
            inputs=inputs,
            N=N,
            tray_T_F=np.asarray(tray_T, dtype=float).reshape((N,)),
            P_tray_psia=np.asarray(P_tray, dtype=float).reshape((N,)),
            V_in_lbmolps=V_in,
            y_in=y_in,
            epsilon_lbmol=float(layout.epsilon_lbmol),
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
        use_provider_cp = (
            inputs.thermo_provider is not None
            and hasattr(inputs.thermo_provider, "cp_liq_vap_btu_per_lbmolF")
        )

        # Optional provider-based phase enthalpies at current tray conditions.
        # This removes a large inconsistency when include_temperature=True and a
        # thermo provider is active, but inputs.thermo is a simple Cp model.
        hL_stage_provider = None
        hV_stage_provider = None
        if inputs.thermo_provider is not None:
            hL_try = np.full(N, np.nan, dtype=float)
            hV_try = np.full(N, np.nan, dtype=float)
            for j in range(N):
                try:
                    fres_L = flash_TP_full_F_psia(
                        inputs.thermo_provider,
                        float(tray_T[j]),
                        float(P_tray[j]),
                        x_tray[j, :],
                        n_components=Nc,
                    )
                    hL_try[j] = float(getattr(fres_L, "HL_BTU_lbmol"))
                except Exception:
                    pass
                try:
                    fres_V = flash_TP_full_F_psia(
                        inputs.thermo_provider,
                        float(tray_T[j]),
                        float(P_tray[j]),
                        y_tray[j, :],
                        n_components=Nc,
                    )
                    hV_try[j] = float(getattr(fres_V, "HV_BTU_lbmol"))
                except Exception:
                    pass
            if np.any(np.isfinite(hL_try)):
                hL_stage_provider = hL_try
            if np.any(np.isfinite(hV_try)):
                hV_stage_provider = hV_try

        for i in range(N):
            # No-holdup reboiler stage has no tray energy state to integrate.
            # Keep the tray-T state bounded by relaxing it to reboiler flash temperature.
            if reboiler_no_holdup and i == (N - 1):
                if "T_reb" in locals() and T_reb is not None:
                    tau_reb_T_sec = 1.0
                    dT_tray[i] = (float(T_reb) - float(tray_T[i])) / max(tau_reb_T_sec, 1e-6)
                else:
                    dT_tray[i] = 0.0
                continue

            # Stage 1 total-condenser temperature closure:
            # relax tray-1 temperature to condenser bubble point (from stage-2
            # vapor composition at condenser pressure), rather than forcing a
            # fixed condenser duty into the tray temperature ODE.
            if i == 0 and str(condenser_duty_mode) == "total-condense" and T_cond_bubble_F is not None and np.isfinite(float(T_cond_bubble_F)):
                tau_cond_T_sec = 1.0
                dT_tray[i] = (float(T_cond_bubble_F) - float(tray_T[i])) / max(tau_cond_T_sec, 1e-6)
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
            )

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
                if (diag["ML_tot_tray"][i] + diag["MV_tot_tray"][i]) <= layout.epsilon_lbmol:
                    dT_tray[i] = 0.0
                    continue
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
    if thermo_provider is not None:
        try:
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
) -> Tuple[float, Optional[float], Optional[float], str]:
    """
    Resolve condenser duty for the current RHS call.

    Returns:
      (Q_used_BTUph, Q_calc_BTUph_or_None, T_cond_bubble_F_or_None, mode_norm)
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
    q_trim = 0.0
    q_trim_raw = getattr(inputs, "condenser_duty_trim_btu_per_h", None)
    if q_trim_raw is not None:
        try:
            q_try = float(q_trim_raw)
            if np.isfinite(q_try):
                q_trim = float(q_try)
        except Exception:
            q_trim = 0.0

    if mode == "total-condense" and inputs.thermo_provider is not None and N > 0:
        src_i = 1 if N > 1 else 0
        try:
            q_try, t_try = _compute_total_condenser_duty_btu_per_h(
                thermo_provider=inputs.thermo_provider,
                V_vapor_in_lbmolps=float(V_in_lbmolps[0]),
                y_vapor_in=np.asarray(y_in[0, :], dtype=float),
                T_vapor_in_F=float(tray_T_F[src_i]),
                P_vapor_in_psia=float(P_tray_psia[src_i]),
                P_condenser_psia=float(P_tray_psia[0]),
                T_guess_F=float(tray_T_F[0]),
                epsilon_lbmol=float(epsilon_lbmol),
            )
            if q_try is not None and np.isfinite(float(q_try)):
                q_calc = float(q_try)
                q_used = float(q_try)
            if t_try is not None and np.isfinite(float(t_try)):
                t_bub = float(t_try)
        except Exception:
            pass

    if mode == "total-condense":
        q_used = float(q_used) + float(q_trim)

    return float(q_used), q_calc, t_bub, mode


def _compute_total_condenser_duty_btu_per_h(
    *,
    thermo_provider: Any,
    V_vapor_in_lbmolps: float,
    y_vapor_in: np.ndarray,
    T_vapor_in_F: float,
    P_vapor_in_psia: float,
    P_condenser_psia: float,
    T_guess_F: float,
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

    try:
        T_bub_F, fres_bub = _bubble_point_T_F(
            thermo_provider=thermo_provider,
            P_psia=P_cond,
            x=x_cond,
            T_guess_F=T_guess,
        )
    except Exception:
        return None, None

    hL_cond = getattr(fres_bub, "HL_BTU_lbmol", None)
    if hL_cond is None or (not np.isfinite(float(hL_cond))):
        hL_cond = getattr(fres_bub, "HL", None)
    if hL_cond is None or (not np.isfinite(float(hL_cond))):
        try:
            fres_liq = flash_TP_full_F_psia(
                thermo_provider,
                float(T_bub_F),
                float(P_cond),
                x_cond,
                n_components=x_cond.size,
            )
            hL_cond = getattr(fres_liq, "HL_BTU_lbmol", None)
            if hL_cond is None or (not np.isfinite(float(hL_cond))):
                hL_cond = getattr(fres_liq, "HL", None)
        except Exception:
            hL_cond = None
    if hL_cond is None or (not np.isfinite(float(hL_cond))):
        return None, float(T_bub_F)

    try:
        fres_vin = flash_TP_full_F_psia(
            thermo_provider,
            float(T_in),
            float(P_vin),
            y,
            n_components=y.size,
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


def _compute_top_drum_pressure_psia(
    *,
    top_V: np.ndarray,
    top_T_F: float,
    Z_top: float,
    top_vapor_volume_ft3: float,
) -> Optional[float]:
    MV_top = float(np.sum(np.asarray(top_V, dtype=float).reshape((-1,))))
    if (not np.isfinite(MV_top)) or MV_top < 0.0:
        return None
    T_R = float(top_T_F) + 459.67
    if (not np.isfinite(T_R)) or T_R <= 0.0:
        return None
    Z = float(Z_top)
    if (not np.isfinite(Z)) or Z <= 0.0:
        Z = 1.0
    V = float(top_vapor_volume_ft3)
    if (not np.isfinite(V)) or V <= 0.0:
        return None
    R = 10.7316  # (psia*ft3)/(lbmol*R)
    P = MV_top * Z * R * T_R / V
    if (not np.isfinite(P)) or P <= 0.0:
        return None
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
) -> Tuple[float, float, float, Optional[float], Optional[float], str]:
    """
    Compute condenser mass split for stage-2 vapor:
      - V_cond_in: incoming vapor condensed to liquid (lbmol/s)
      - V_to_top: incoming vapor not condensed, sent to top vapor holdup (lbmol/s)
      - V_cond_top: top-vapor holdup condensed to liquid (lbmol/s)

    Returns:
      (V_cond_in, V_to_top, V_cond_top, Q_used_BTUph_or_None, Q_total_req_BTUph_or_None, mode_norm)
    """
    mode = _normalize_condenser_duty_mode(getattr(inputs, "condenser_duty_mode", None))
    V_in0 = float(np.asarray(V_in_lbmolps, dtype=float).reshape((-1,))[0])
    if (not np.isfinite(V_in0)) or V_in0 <= float(epsilon_lbmol):
        return 0.0, 0.0, 0.0, None, None, mode

    # Resolve duty exactly as used by the energy closure (including total-condense trim).
    N = int(len(tray_T_F))
    try:
        Q_used_BTUph, Q_calc_BTUph, _t_bub, mode = _resolve_condenser_duty_btu_per_h(
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
    elif inputs.thermo_provider is not None:
        try:
            src_i = 1 if N > 1 else 0
            q_req, _t_bub = _compute_total_condenser_duty_btu_per_h(
                thermo_provider=inputs.thermo_provider,
                V_vapor_in_lbmolps=float(V_in0),
                y_vapor_in=np.asarray(y_in[0, :], dtype=float),
                T_vapor_in_F=float(tray_T_F[src_i]),
                P_vapor_in_psia=float(P_tray_psia[src_i]),
                P_condenser_psia=float(P_tray_psia[0]),
                T_guess_F=float(tray_T_F[0]),
                epsilon_lbmol=float(epsilon_lbmol),
            )
            if q_req is not None and np.isfinite(float(q_req)):
                Q_total_req = float(q_req)
        except Exception:
            Q_total_req = None

    # If latent information is unavailable, preserve prior behavior (full condensation).
    if Q_total_req is None or (not np.isfinite(float(Q_total_req))) or float(Q_total_req) >= -1e-12:
        return float(V_in0), 0.0, 0.0, float(Q_used_BTUph), Q_total_req, mode

    latent_BTU_per_lbmol = (-float(Q_total_req)) / max(float(V_in0) * 3600.0, 1e-12)
    if (not np.isfinite(latent_BTU_per_lbmol)) or latent_BTU_per_lbmol <= 1e-12:
        return float(V_in0), 0.0, 0.0, float(Q_used_BTUph), Q_total_req, mode

    Q_remove_BTUph = max(-float(Q_used_BTUph), 0.0)
    cond_capacity_lbmolps = Q_remove_BTUph / latent_BTU_per_lbmol / 3600.0
    if (not np.isfinite(cond_capacity_lbmolps)) or cond_capacity_lbmolps <= 0.0:
        return 0.0, float(V_in0), 0.0, float(Q_used_BTUph), Q_total_req, mode

    V_cond_in = min(float(V_in0), float(cond_capacity_lbmolps))
    rem_capacity = max(float(cond_capacity_lbmolps) - float(V_cond_in), 0.0)

    MV_top = float(np.sum(np.asarray(top_V, dtype=float).reshape((-1,))))
    MV_top = max(MV_top, 0.0)
    V_cond_top = min(float(rem_capacity), float(MV_top))
    V_to_top = max(float(V_in0) - float(V_cond_in), 0.0)
    return float(V_cond_in), float(V_to_top), float(V_cond_top), float(Q_used_BTUph), Q_total_req, mode


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
) -> np.ndarray:
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
        elif i == 1 and cond_dp_fixed > 0.0:
            # Optional explicit condenser pressure drop from stage 2 to stage 1.
            dp_psia = float(cond_dp_fixed)
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
            if np.isfinite(dp_stage_cap) and dp_stage_cap > 0.0:
                dp_psia = min(dp_psia, dp_stage_cap)
        dp_raw[i] = float(max(dp_psia, 0.0))

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

    for i in range(N - 1, 0, -1):
        if i == 1 and cond_dp_fixed > 0.0:
            dp_psia = float(cond_dp_fixed)
        else:
            dp_psia = float(dp_raw[i]) * float(drop_scale)
        P[i - 1] = max(float(P[i]) - dp_psia, p_floor)

    return P


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

    # Keep bubble-point solve within provider table bounds when available.
    t_bounds = _thermo_provider_temperature_bounds_F(thermo_provider)
    if t_bounds is not None:
        t_lo, t_hi = t_bounds
        T_min_F = max(float(T_min_F), float(t_lo))
        T_max_F = min(float(T_max_F), float(t_hi))

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
    T_guess_F = float(T_guess_F)

    # Degenerate bound window: return clipped guess.
    if (not np.isfinite(float(T_min_F))) or (not np.isfinite(float(T_max_F))) or float(T_max_F) <= float(T_min_F):
        T_use = float(T_guess_F)
        f_use, beta_use, fres_use = eval_f(T_use)
        _ = (f_use, beta_use)
        return float(T_use), fres_use

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
        if abs(f_m) < 1e-8:
            return T_m, fres_mid
        if f_a * f_m < 0.0:
            T_b, f_b = T_m, f_m
        else:
            T_a, f_a = T_m, f_m
    return 0.5 * (T_a + T_b), fres_mid
