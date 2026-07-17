"""
uv_flash_stage_v1.py

Stage-level UV-flash utilities for sandbox prototyping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np

from dynamic_distillation.stage_thermo_v1 import flash_TP_full_F_psia as _stage_flash_TP_full_F_psia


BTU_PER_PSI_FT3 = (6894.7572931783 * 0.028316846592) / 1055.05585262
R_GAS_PSIA_FT3_PER_LBMOL_R = 10.7316


class UvFlashStageError(RuntimeError):
    """Raised when the UV-flash stage solve fails."""


@dataclass(frozen=True)
class UvFlashStageGuess:
    T_F: float
    P_psia: float
    beta_vapor: float = 0.5


@dataclass(frozen=True)
class UvFlashStageResult:
    T_F: float
    P_psia: float
    beta_vapor: float
    x: np.ndarray
    y: np.ndarray
    K: np.ndarray
    HL_BTU_lbmol: float
    HV_BTU_lbmol: float
    uL_BTU_lbmol: float
    uV_BTU_lbmol: float
    vL_ft3_lbmol: float
    vV_ft3_lbmol: float
    Z_vapor: float
    residual_u_BTU_lbmol: float
    residual_v_ft3_lbmol: float
    residual_beta: float
    converged: bool
    iterations: int
    projection_count: int = 0
    accepted_projection_count: int = 0


@dataclass(frozen=True)
class UvStageReferenceState:
    total_component_holdup_lbmol: np.ndarray
    total_internal_energy_BTU: float
    total_volume_ft3: float
    total_moles_lbmol: float
    liquid_moles_lbmol: float
    vapor_moles_lbmol: float
    z_overall: np.ndarray
    initial_guess: UvFlashStageGuess


@dataclass(frozen=True)
class _TpStageState:
    x: np.ndarray
    y: np.ndarray
    K: np.ndarray
    HL_BTU_lbmol: float
    HV_BTU_lbmol: float
    uL_BTU_lbmol: float
    uV_BTU_lbmol: float
    vL_ft3_lbmol: float
    vV_ft3_lbmol: float
    Z_vapor: float
    beta_eq: float


def _normalize_comp(z: Sequence[float]) -> np.ndarray:
    arr = np.asarray(z, dtype=float).reshape((-1,))
    s = float(np.sum(arr))
    if (not np.isfinite(s)) or s <= 0.0:
        raise ValueError("composition sum must be > 0")
    return arr / s


def _vapor_molar_volume_ft3_lbmol(T_F: float, P_psia: float, Z_vapor: float) -> float:
    T_R = float(T_F) + 459.67
    P = float(P_psia)
    Z = float(Z_vapor)
    if (not np.isfinite(T_R)) or T_R <= 1.0e-9:
        raise ValueError("temperature must be finite and > -459.67 F")
    if (not np.isfinite(P)) or P <= 1.0e-12:
        raise ValueError("pressure must be finite and > 0")
    if (not np.isfinite(Z)) or Z <= 1.0e-12:
        raise ValueError("Z must be finite and > 0")
    return float(Z * R_GAS_PSIA_FT3_PER_LBMOL_R * T_R / P)


def _internal_energy_from_enthalpy_BTU_lbmol(h_BTU_lbmol: float, P_psia: float, v_ft3_lbmol: float) -> float:
    return float(h_BTU_lbmol) - float(P_psia) * float(v_ft3_lbmol) * BTU_PER_PSI_FT3


def _rr_beta_from_K_z(K: Sequence[float], z: Sequence[float], tol: float = 1.0e-12, max_iter: int = 80) -> float:
    K_arr = np.asarray(K, dtype=float).reshape((-1,))
    z_arr = _normalize_comp(z)
    if K_arr.size != z_arr.size:
        raise ValueError("K and z must have the same length")

    K_arr = np.where(~np.isfinite(K_arr) | (K_arr <= 1.0e-12), 1.0e-12, K_arr)

    def f(beta: float) -> float:
        denom = 1.0 + beta * (K_arr - 1.0)
        denom = np.where(np.abs(denom) < 1.0e-12, 1.0e-12, denom)
        return float(np.sum(z_arr * (K_arr - 1.0) / denom))

    f0 = f(0.0)
    f1 = f(1.0)
    if (not np.isfinite(f0)) or (not np.isfinite(f1)):
        return 0.5
    if f0 <= 0.0 and f1 <= 0.0:
        return 0.0
    if f0 >= 0.0 and f1 >= 0.0:
        return 1.0

    lo = 0.0
    hi = 1.0
    flo = f0
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
    return float(0.5 * (lo + hi))


def _provider_vapor_z_factor(
    provider: Any,
    *,
    T_F: float,
    P_psia: float,
    y: np.ndarray,
    flash_Z: Optional[float],
) -> float:
    if flash_Z is not None:
        try:
            zf = float(flash_Z)
            if np.isfinite(zf) and zf > 0.0:
                return zf
        except Exception:
            pass

    for attr in ("vapor_z_factor_F_psia", "vapor_z_factor"):
        if not hasattr(provider, attr):
            continue
        fn = getattr(provider, attr)
        if not callable(fn):
            continue
        try:
            zf = float(fn(float(T_F), float(P_psia), np.asarray(y, dtype=float).tolist()))
            if np.isfinite(zf) and zf > 0.0:
                return zf
        except Exception:
            continue

    return 1.0


def _evaluate_tp_stage_state(
    provider: Any,
    *,
    T_F: float,
    P_psia: float,
    z_overall: np.ndarray,
) -> _TpStageState:
    flash = _stage_flash_TP_full_F_psia(
        provider,
        float(T_F),
        float(P_psia),
        np.asarray(z_overall, dtype=float).tolist(),
        n_components=int(z_overall.size),
    )

    rhoL = provider.liquid_density_lbmol_ft3(float(T_F), float(P_psia), flash.x.tolist())
    if rhoL is None:
        raise UvFlashStageError("liquid density lookup failed during UV flash evaluation")
    rhoL_f = float(rhoL)
    if (not np.isfinite(rhoL_f)) or rhoL_f <= 1.0e-12:
        raise UvFlashStageError("liquid density lookup returned non-physical value")

    vL = 1.0 / rhoL_f
    Z_vapor = _provider_vapor_z_factor(
        provider,
        T_F=float(T_F),
        P_psia=float(P_psia),
        y=np.asarray(flash.y, dtype=float),
        flash_Z=flash.Z,
    )
    vV = _vapor_molar_volume_ft3_lbmol(float(T_F), float(P_psia), Z_vapor)
    beta_eq = _rr_beta_from_K_z(flash.K, z_overall)
    uL = _internal_energy_from_enthalpy_BTU_lbmol(flash.HL_BTU_lbmol, float(P_psia), vL)
    uV = _internal_energy_from_enthalpy_BTU_lbmol(flash.HV_BTU_lbmol, float(P_psia), vV)

    return _TpStageState(
        x=np.asarray(flash.x, dtype=float).copy(),
        y=np.asarray(flash.y, dtype=float).copy(),
        K=np.asarray(flash.K, dtype=float).copy(),
        HL_BTU_lbmol=float(flash.HL_BTU_lbmol),
        HV_BTU_lbmol=float(flash.HV_BTU_lbmol),
        uL_BTU_lbmol=float(uL),
        uV_BTU_lbmol=float(uV),
        vL_ft3_lbmol=float(vL),
        vV_ft3_lbmol=float(vV),
        Z_vapor=float(Z_vapor),
        beta_eq=float(beta_eq),
    )


def _clip_trial_vector(x_vec: np.ndarray, *, beta_mode: str) -> np.ndarray:
    x_out = np.asarray(x_vec, dtype=float).copy()
    x_out[0] = float(np.clip(x_out[0], -200.0, 1000.0))
    x_out[1] = float(np.clip(x_out[1], 1.0, 1000.0))
    if beta_mode == "free" and x_out.size >= 3:
        x_out[2] = float(np.clip(x_out[2], 1.0e-8, 1.0 - 1.0e-8))
    return x_out


def _residual_for_state(
    provider: Any,
    *,
    z_overall: np.ndarray,
    u_target_BTU_lbmol: float,
    v_target_ft3_lbmol: float,
    x_vec: np.ndarray,
    beta_mode: str,
    beta_fixed: Optional[float],
) -> tuple[np.ndarray, _TpStageState, float]:
    T_F = float(x_vec[0])
    P_psia = float(x_vec[1])
    stage_state = _evaluate_tp_stage_state(
        provider,
        T_F=T_F,
        P_psia=P_psia,
        z_overall=z_overall,
    )

    beta = float(stage_state.beta_eq) if beta_mode == "free" else float(beta_fixed)
    if beta_mode == "free" and x_vec.size >= 3:
        beta = float(x_vec[2])
    beta = float(np.clip(beta, 0.0, 1.0))

    u_mix = (1.0 - beta) * stage_state.uL_BTU_lbmol + beta * stage_state.uV_BTU_lbmol
    v_mix = (1.0 - beta) * stage_state.vL_ft3_lbmol + beta * stage_state.vV_ft3_lbmol

    if beta_mode == "free":
        residual = np.array(
            [
                float(u_mix - u_target_BTU_lbmol),
                float(v_mix - v_target_ft3_lbmol),
                float(beta - stage_state.beta_eq),
            ],
            dtype=float,
        )
    else:
        residual = np.array(
            [
                float(u_mix - u_target_BTU_lbmol),
                float(v_mix - v_target_ft3_lbmol),
            ],
            dtype=float,
        )

    return residual, stage_state, beta


def solve_uv_flash_stage(
    provider: Any,
    *,
    z_overall: Sequence[float],
    u_target_BTU_lbmol: float,
    v_target_ft3_lbmol: float,
    guess: Optional[UvFlashStageGuess] = None,
    beta_mode: str = "free",
    beta_fixed: Optional[float] = None,
    max_iter: int = 12,
    tol_u_BTU_lbmol: float = 1.0e-6,
    tol_v_ft3_lbmol: float = 1.0e-9,
    tol_beta: float = 1.0e-9,
    jac_rel_step: float = 1.0e-6,
) -> UvFlashStageResult:
    z_norm = _normalize_comp(z_overall)

    mode = str(beta_mode or "free").strip().lower()
    if mode not in ("free", "fixed"):
        raise ValueError("beta_mode must be 'free' or 'fixed'")
    if mode == "fixed":
        if beta_fixed is None:
            raise ValueError("beta_fixed is required when beta_mode='fixed'")
        beta_fixed = float(np.clip(float(beta_fixed), 0.0, 1.0))

    if guess is None:
        guess = UvFlashStageGuess(T_F=100.0, P_psia=200.0, beta_vapor=0.5 if mode == "free" else float(beta_fixed))

    x_vec = np.array(
        [float(guess.T_F), float(guess.P_psia)] + ([float(guess.beta_vapor)] if mode == "free" else []),
        dtype=float,
    )
    projection_count = 0

    def _project(x_in: np.ndarray) -> np.ndarray:
        nonlocal projection_count
        projected = _clip_trial_vector(x_in, beta_mode=mode)
        if not np.array_equal(np.asarray(x_in, dtype=float), projected, equal_nan=True):
            projection_count += 1
        return projected

    x_initial = np.asarray(x_vec, dtype=float).copy()
    x_vec = _project(x_vec)
    accepted_projection_count = int(
        not np.array_equal(x_initial, x_vec, equal_nan=True)
    )

    last_state: Optional[_TpStageState] = None
    last_beta = float(beta_fixed) if mode == "fixed" else float(guess.beta_vapor)
    last_residual = np.full(3 if mode == "free" else 2, np.nan, dtype=float)

    for it in range(1, max(1, int(max_iter)) + 1):
        residual, stage_state, beta = _residual_for_state(
            provider,
            z_overall=z_norm,
            u_target_BTU_lbmol=float(u_target_BTU_lbmol),
            v_target_ft3_lbmol=float(v_target_ft3_lbmol),
            x_vec=x_vec,
            beta_mode=mode,
            beta_fixed=beta_fixed,
        )
        last_state = stage_state
        last_beta = beta
        last_residual = residual.copy()

        conv_u = abs(float(residual[0])) <= float(tol_u_BTU_lbmol)
        conv_v = abs(float(residual[1])) <= float(tol_v_ft3_lbmol)
        conv_beta = True if mode != "free" else abs(float(residual[2])) <= float(tol_beta)
        if conv_u and conv_v and conv_beta:
            return UvFlashStageResult(
                T_F=float(x_vec[0]),
                P_psia=float(x_vec[1]),
                beta_vapor=float(last_beta),
                x=stage_state.x.copy(),
                y=stage_state.y.copy(),
                K=stage_state.K.copy(),
                HL_BTU_lbmol=float(stage_state.HL_BTU_lbmol),
                HV_BTU_lbmol=float(stage_state.HV_BTU_lbmol),
                uL_BTU_lbmol=float(stage_state.uL_BTU_lbmol),
                uV_BTU_lbmol=float(stage_state.uV_BTU_lbmol),
                vL_ft3_lbmol=float(stage_state.vL_ft3_lbmol),
                vV_ft3_lbmol=float(stage_state.vV_ft3_lbmol),
                Z_vapor=float(stage_state.Z_vapor),
                residual_u_BTU_lbmol=float(residual[0]),
                residual_v_ft3_lbmol=float(residual[1]),
                residual_beta=(0.0 if mode != "free" else float(residual[2])),
                converged=True,
                iterations=int(it),
                projection_count=int(projection_count),
                accepted_projection_count=int(accepted_projection_count),
            )

        J = np.zeros((residual.size, x_vec.size), dtype=float)
        for j in range(x_vec.size):
            x_pert = x_vec.copy()
            step = max(abs(float(x_vec[j])) * float(jac_rel_step), 1.0e-6)
            x_pert[j] = float(x_pert[j]) + float(step)
            x_pert = _project(x_pert)
            res_pert, _state_pert, _beta_pert = _residual_for_state(
                provider,
                z_overall=z_norm,
                u_target_BTU_lbmol=float(u_target_BTU_lbmol),
                v_target_ft3_lbmol=float(v_target_ft3_lbmol),
                x_vec=x_pert,
                beta_mode=mode,
                beta_fixed=beta_fixed,
            )
            J[:, j] = (res_pert - residual) / max(float(x_pert[j] - x_vec[j]), 1.0e-12)

        if (not np.all(np.isfinite(J))) or (not np.all(np.isfinite(residual))):
            break

        try:
            delta, *_ = np.linalg.lstsq(J, -residual, rcond=None)
        except Exception as exc:
            raise UvFlashStageError(f"UV flash linear solve failed: {exc}") from exc
        delta = np.asarray(delta, dtype=float).reshape((x_vec.size,))
        if not np.all(np.isfinite(delta)):
            break

        base_norm = float(np.max(np.abs(residual)))
        accepted = False
        alpha = 1.0
        for _ in range(8):
            x_unprojected = x_vec + alpha * delta
            x_try = _project(x_unprojected)
            trial_was_projected = not np.array_equal(
                np.asarray(x_unprojected, dtype=float),
                x_try,
                equal_nan=True,
            )
            res_try, _state_try, _beta_try = _residual_for_state(
                provider,
                z_overall=z_norm,
                u_target_BTU_lbmol=float(u_target_BTU_lbmol),
                v_target_ft3_lbmol=float(v_target_ft3_lbmol),
                x_vec=x_try,
                beta_mode=mode,
                beta_fixed=beta_fixed,
            )
            try_norm = float(np.max(np.abs(res_try)))
            if np.isfinite(try_norm) and try_norm <= base_norm:
                x_vec = x_try
                if trial_was_projected:
                    accepted_projection_count += 1
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            break

    if last_state is None:
        raise UvFlashStageError("UV flash failed before producing a valid TP state")

    return UvFlashStageResult(
        T_F=float(x_vec[0]),
        P_psia=float(x_vec[1]),
        beta_vapor=float(last_beta),
        x=last_state.x.copy(),
        y=last_state.y.copy(),
        K=last_state.K.copy(),
        HL_BTU_lbmol=float(last_state.HL_BTU_lbmol),
        HV_BTU_lbmol=float(last_state.HV_BTU_lbmol),
        uL_BTU_lbmol=float(last_state.uL_BTU_lbmol),
        uV_BTU_lbmol=float(last_state.uV_BTU_lbmol),
        vL_ft3_lbmol=float(last_state.vL_ft3_lbmol),
        vV_ft3_lbmol=float(last_state.vV_ft3_lbmol),
        Z_vapor=float(last_state.Z_vapor),
        residual_u_BTU_lbmol=float(last_residual[0]),
        residual_v_ft3_lbmol=float(last_residual[1]),
        residual_beta=(0.0 if mode != "free" else float(last_residual[2])),
        converged=False,
        iterations=int(max_iter),
        projection_count=int(projection_count),
        accepted_projection_count=int(accepted_projection_count),
    )


def initialize_uv_stage_state_from_tp_profile(
    provider: Any,
    *,
    T_F: float,
    P_psia: float,
    x_liq: Sequence[float],
    y_vap: Sequence[float],
    liquid_holdup_lbmol: float,
    vapor_volume_ft3: float,
) -> UvStageReferenceState:
    x_norm = _normalize_comp(x_liq)
    y_norm = _normalize_comp(y_vap)
    liquid_moles = max(float(liquid_holdup_lbmol), 0.0)
    vapor_vol = max(float(vapor_volume_ft3), 0.0)

    hL = float(provider.phase_enthalpy_BTU_lbmol("liquid", float(T_F), float(P_psia), x_norm.tolist()))
    hV = float(provider.phase_enthalpy_BTU_lbmol("vapor", float(T_F), float(P_psia), y_norm.tolist()))

    rhoL = provider.liquid_density_lbmol_ft3(float(T_F), float(P_psia), x_norm.tolist())
    if rhoL is None:
        raise UvFlashStageError("liquid density lookup failed during UV initialization")
    rhoL_f = float(rhoL)
    if (not np.isfinite(rhoL_f)) or rhoL_f <= 1.0e-12:
        raise UvFlashStageError("liquid density lookup returned non-physical value during UV initialization")

    Z_vap = _provider_vapor_z_factor(
        provider,
        T_F=float(T_F),
        P_psia=float(P_psia),
        y=y_norm,
        flash_Z=None,
    )

    vL = 1.0 / rhoL_f
    vV = _vapor_molar_volume_ft3_lbmol(float(T_F), float(P_psia), float(Z_vap))
    vapor_moles = vapor_vol / max(vV, 1.0e-12)

    uL = _internal_energy_from_enthalpy_BTU_lbmol(hL, float(P_psia), vL)
    uV = _internal_energy_from_enthalpy_BTU_lbmol(hV, float(P_psia), vV)

    total_component_holdup = liquid_moles * x_norm + vapor_moles * y_norm
    total_moles = float(np.sum(total_component_holdup))
    if total_moles <= 0.0:
        raise UvFlashStageError("UV initialization produced zero total holdup")

    total_internal_energy = liquid_moles * uL + vapor_moles * uV
    total_volume = liquid_moles * vL + vapor_moles * vV
    z_overall = total_component_holdup / total_moles
    beta_guess = vapor_moles / total_moles

    return UvStageReferenceState(
        total_component_holdup_lbmol=total_component_holdup.astype(float).copy(),
        total_internal_energy_BTU=float(total_internal_energy),
        total_volume_ft3=float(total_volume),
        total_moles_lbmol=float(total_moles),
        liquid_moles_lbmol=float(liquid_moles),
        vapor_moles_lbmol=float(vapor_moles),
        z_overall=z_overall.astype(float).copy(),
        initial_guess=UvFlashStageGuess(
            T_F=float(T_F),
            P_psia=float(P_psia),
            beta_vapor=float(np.clip(beta_guess, 1.0e-8, 1.0 - 1.0e-8)),
        ),
    )
