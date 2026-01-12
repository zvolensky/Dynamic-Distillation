"""
column_rhs_v1.py

Dynamic Distillation - Column RHS (v1)

Updated: 2026-01-11  (America/New_York)

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

    x_tray = u["x_tray"]
    y_tray = u.get("y_tray", None)

    top_L = u.get("top_L", None)
    top_V = u.get("top_V", None)
    bottom_L = u.get("bottom_L", None)
    bottom_V = u.get("bottom_V", None)

    # flows (lbmol/s)
    L_out = np.asarray(col.L_lbmolph, dtype=float) / 3600.0
    V_out = np.asarray(col.V_lbmolph, dtype=float) / 3600.0
    if L_out.shape != (N,) or V_out.shape != (N,):
        raise ColumnRHSError("ColumnSpec L/V flow arrays must have shape (n_stages,)")

    reflux = inputs.boundary.reflux_lbmolph
    boilup = inputs.boundary.boilup_lbmolph
    if reflux is None:
        reflux = float(col.L_lbmolph[0])
    if boilup is None:
        boilup = float(col.V_lbmolph[-1])
    reflux_s = float(reflux) / 3600.0
    boilup_s = float(boilup) / 3600.0

    feed_stage0, Fk_L, Fk_V = _feed_component_rates_lbmolps(col, Nc)
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

    # inlets
    L_in = np.zeros(N, dtype=float)
    x_in = np.zeros((N, Nc), dtype=float)
    for i in range(N):
        if i == 0:
            L_in[i] = reflux_s
            x_in[i, :] = x_topL
        else:
            L_in[i] = L_out[i - 1]
            x_in[i, :] = x_tray[i - 1, :]

    V_in = np.zeros(N, dtype=float)
    y_in = np.zeros((N, Nc), dtype=float)
    for i in range(N):
        if i == N - 1:
            V_in[i] = boilup_s
            y_in[i, :] = y_botV
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
                + V_in[i] * y_in[i, k]
                + feedL
                - L_out[i] * x_tray[i, k]
                - V_out[i] * y_tray[i, k]
            )

            d_tray_V[i, k] = (
                V_in[i] * y_in[i, k]
                + feedV
                - V_out[i] * y_tray[i, k]
            )

    d_top_L = d_top_V = None
    if layout.include_top:
        if top_L is None or top_V is None:
            raise ColumnRHSError("layout.include_top=True requires top_L and top_V states.")

        d_top_L = np.zeros(Nc, dtype=float)
        d_top_V = np.zeros(Nc, dtype=float)

        V_to_cond = V_out[0]
        y_toptray = y_tray[0, :]

        d_top_L += alpha * V_to_cond * y_toptray
        d_top_V += (1.0 - alpha) * V_to_cond * y_toptray

        d_top_L -= reflux_s * x_topL

        if D.has_component_breakdown:
            d_top_L -= D.comp_L
            d_top_V -= D.comp_V
        else:
            d_top_L -= D.total_L * x_topL
            d_top_V -= D.total_V * y_topV

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

        d_bottom_L -= boilup_s * x_botL
        d_bottom_V += boilup_s * x_botL
        d_bottom_V -= boilup_s * y_botV

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

        K_tray = np.zeros((N, Nc), dtype=float)
        HL = np.zeros(N, dtype=float)
        HV = np.zeros(N, dtype=float)
        Zfac_tray = np.ones(N, dtype=float)

        for i in range(N):
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

        dT_tray = np.zeros(N, dtype=float)

        for i in range(N):
            T_L_in = top_T if (i == 0 and top_T is not None) else (tray_T[i - 1] if i > 0 else tray_T[i])
            T_V_in = bot_T if (i == N - 1 and bot_T is not None) else (tray_T[i + 1] if i < N - 1 else tray_T[i])

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

            cpL = thermo.cp_liq_btu_per_lbmolF(tray_T[i], P_tray[i], x_tray[i, :])
            cpV = thermo.cp_vap_btu_per_lbmolF(tray_T[i], P_tray[i], y_tray[i, :])

            C = diag["ML_tot_tray"][i] * cpL + diag["MV_tot_tray"][i] * cpV
            if C <= 0.0:
                raise ColumnRHSError("Non-positive tray heat capacity encountered.")

            dT_tray[i] = dE / C

        dydt[sl["tray_T_f"]] = dT_tray
        diag["dT_tray_F_per_s"] = dT_tray.copy()

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
    s = col.streams.get(stream_name)
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