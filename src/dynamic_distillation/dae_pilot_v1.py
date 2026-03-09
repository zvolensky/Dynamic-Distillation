"""
dae_pilot_v1.py

Pilot utilities for transitioning the column model toward a simultaneous DAE
formulation.

This module does not solve the DAE by itself. It provides:
1. A compact algebraic-state layout (tray pressure + vapor outflow).
2. Residual evaluation for a semi-explicit index-1 pilot form:
   F_diff = ydot - f(t, y, z)
   F_alg  = z - g(t, y, z)
3. Finite-difference Jacobian helpers for conditioning diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Optional

import numpy as np

from dynamic_distillation.column_rhs_v1 import column_rhs


ArrayLike = np.ndarray


@dataclass(frozen=True)
class DaePilotLayout:
    """Index helpers for flattened algebraic vector z = [P(1..N), V(1..N)]."""

    n_stages: int

    @property
    def z_size(self) -> int:
        return 2 * int(self.n_stages)

    @property
    def p_slice(self) -> slice:
        return slice(0, int(self.n_stages))

    @property
    def v_slice(self) -> slice:
        return slice(int(self.n_stages), 2 * int(self.n_stages))

    def split(self, z: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
        z_arr = np.asarray(z, dtype=float).reshape((-1,))
        if z_arr.size != self.z_size:
            raise ValueError(f"Expected z size {self.z_size}, got {z_arr.size}")
        p = np.asarray(z_arr[self.p_slice], dtype=float).copy()
        v = np.asarray(z_arr[self.v_slice], dtype=float).copy()
        return p, v

    def join(self, p: ArrayLike, v: ArrayLike) -> np.ndarray:
        p_arr = np.asarray(p, dtype=float).reshape((self.n_stages,))
        v_arr = np.asarray(v, dtype=float).reshape((self.n_stages,))
        return np.concatenate([p_arr, v_arr], axis=0)


@dataclass(frozen=True)
class DaePilotResidual:
    """Structured residual output for diagnostics and solver integration."""

    diff: np.ndarray
    alg_pressure: np.ndarray
    alg_vapor: np.ndarray
    full: np.ndarray
    dydt_rhs: np.ndarray
    pressure_rhs: np.ndarray
    vapor_rhs: np.ndarray
    diag: Dict[str, np.ndarray]


def _as_stage_vector(diag: Dict[str, np.ndarray], key: str, n_stages: int) -> Optional[np.ndarray]:
    if key not in diag:
        return None
    try:
        arr = np.asarray(diag[key], dtype=float).reshape((n_stages,))
    except Exception:
        return None
    return arr


def _pressure_from_diag(diag: Dict[str, np.ndarray], n_stages: int) -> np.ndarray:
    p_hyd = _as_stage_vector(diag, "P_psia_hyd", n_stages)
    if p_hyd is not None:
        return p_hyd
    p_diag = _as_stage_vector(diag, "P_psia_diag", n_stages)
    if p_diag is not None:
        return p_diag
    return np.full(n_stages, np.nan, dtype=float)


def _vapor_from_diag(diag: Dict[str, np.ndarray], n_stages: int) -> np.ndarray:
    v = _as_stage_vector(diag, "V_out_lbmolph", n_stages)
    if v is None:
        return np.full(n_stages, np.nan, dtype=float)
    return v


def default_algebraic_seed(
    *,
    n_stages: int,
    diag: Optional[Dict[str, np.ndarray]] = None,
    p_fallback_psia: Optional[ArrayLike] = None,
    v_fallback_lbmolph: Optional[ArrayLike] = None,
) -> np.ndarray:
    """Build an initial z guess using diag values, then profile fallbacks."""
    layout = DaePilotLayout(n_stages=int(n_stages))
    p = None
    v = None
    if diag is not None:
        p = _pressure_from_diag(diag, int(n_stages))
        v = _vapor_from_diag(diag, int(n_stages))

    if p is None or p.size != int(n_stages):
        p = np.full(int(n_stages), np.nan, dtype=float)
    if v is None or v.size != int(n_stages):
        v = np.full(int(n_stages), np.nan, dtype=float)

    if p_fallback_psia is not None:
        p_fb = np.asarray(p_fallback_psia, dtype=float).reshape((int(n_stages),))
        p = np.where(np.isfinite(p), p, p_fb)
    if v_fallback_lbmolph is not None:
        v_fb = np.asarray(v_fallback_lbmolph, dtype=float).reshape((int(n_stages),))
        v = np.where(np.isfinite(v), v, v_fb)

    return layout.join(p, v)


def evaluate_pilot_residual(
    *,
    t_s: float,
    y: ArrayLike,
    ydot: ArrayLike,
    z: ArrayLike,
    col: Any,
    layout: Any,
    inputs: Any,
    rhs_func: Callable[..., tuple[np.ndarray, Dict[str, np.ndarray]]] = column_rhs,
) -> DaePilotResidual:
    """
    Evaluate pilot DAE residual at a single (t, y, ydot, z) point.

    The algebraic unknowns z are injected through `P_tray_prev` and
    `V_out_prev_lbmolph` so existing pressure/vapor closure logic can be reused.
    """
    n_stages = int(getattr(col, "n_stages", 0))
    if n_stages <= 0:
        raise ValueError("Column spec must provide n_stages > 0")

    z_layout = DaePilotLayout(n_stages=n_stages)
    z_p, z_v = z_layout.split(np.asarray(z, dtype=float))

    y_arr = np.asarray(y, dtype=float).reshape((-1,))
    ydot_arr = np.asarray(ydot, dtype=float).reshape((-1,))
    if y_arr.size != ydot_arr.size:
        raise ValueError(f"y and ydot size mismatch: {y_arr.size} vs {ydot_arr.size}")

    inputs_eval = replace(inputs, P_tray_prev=z_p, V_out_prev_lbmolph=z_v)
    dydt_rhs, diag = rhs_func(float(t_s), y_arr, col, layout, inputs=inputs_eval)
    dydt_rhs = np.asarray(dydt_rhs, dtype=float).reshape((-1,))

    p_rhs = _pressure_from_diag(diag, n_stages)
    v_rhs = _vapor_from_diag(diag, n_stages)

    diff_resid = ydot_arr - dydt_rhs
    alg_p_resid = z_p - p_rhs
    alg_v_resid = z_v - v_rhs
    full_resid = np.concatenate([diff_resid, alg_p_resid, alg_v_resid], axis=0)

    return DaePilotResidual(
        diff=diff_resid,
        alg_pressure=alg_p_resid,
        alg_vapor=alg_v_resid,
        full=full_resid,
        dydt_rhs=dydt_rhs,
        pressure_rhs=p_rhs,
        vapor_rhs=v_rhs,
        diag=diag,
    )


def finite_difference_jacobian(
    func: Callable[[np.ndarray], np.ndarray],
    x: ArrayLike,
    *,
    rel_step: float = 1.0e-6,
    abs_step: float = 1.0e-8,
) -> np.ndarray:
    """Dense forward-difference Jacobian for diagnostic use."""
    x0 = np.asarray(x, dtype=float).reshape((-1,))
    f0 = np.asarray(func(x0), dtype=float).reshape((-1,))
    m = int(f0.size)
    n = int(x0.size)
    J = np.zeros((m, n), dtype=float)

    for j in range(n):
        xj = np.asarray(x0, dtype=float).copy()
        scale = max(abs(float(x0[j])) * float(rel_step), float(abs_step))
        if not np.isfinite(scale) or scale <= 0.0:
            scale = float(abs_step)
        xj[j] = float(xj[j]) + float(scale)
        fj = np.asarray(func(xj), dtype=float).reshape((-1,))
        if fj.size != m:
            raise ValueError("Jacobian function output size changed during perturbation")
        J[:, j] = (fj - f0) / float(scale)
    return J


def inf_norm(arr: ArrayLike) -> float:
    """Infinity norm with NaN-safe fallback."""
    a = np.asarray(arr, dtype=float).reshape((-1,))
    if a.size == 0:
        return 0.0
    finite = a[np.isfinite(a)]
    if finite.size == 0:
        return float("nan")
    return float(np.max(np.abs(finite)))

