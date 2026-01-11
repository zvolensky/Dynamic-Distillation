# src/dynamic_distillation/state_vector_layout_v1.py
"""
state_vector_layout_v1.py

Created: 2026-01-11  (America/New_York)
Updated: 2026-01-11  (America/New_York)

Purpose
-------
Canonical packing/unpacking for the ODE state vector y.

Supports:
- Tray liquid component holdup states (always)
- Optional tray vapor component holdup states
- Optional boundary holdup states (top/bottom)
- Optional temperature states (legacy): tray_T_f + top_T_f + bottom_T_f
- Optional energy holdup states (Module 6, Option B1):
    tray_EL_BTU[i] = ML[i] * hL[i]   (Btu)
    tray_EV_BTU[i] = MV[i] * hV[i]   (Btu)

Compatibility
-------------
Your ColumnSpec currently uses:
  - M_L_lbmol (N,)
  - M_V_lbmol (N,)
and tests expect:
  - include_temperature kwarg
  - totals exposed as ML_tot_tray / MV_tot_tray

This module supports those names (and also supports legacy ML0_lbmol/MV0_lbmol if present).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np


def _get_first_attr(obj, names: list[str]):
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    raise AttributeError(f"Object missing required attributes; tried: {names}")


@dataclass(frozen=True)
class StateVectorLayout:
    n_stages: int
    n_components: int

    include_top: bool = True
    include_bottom: bool = True
    include_vapor: bool = True

    # Legacy temperature-state energy option (your tests rely on this existing)
    include_temperature: bool = False

    # Module 6 Option B1
    include_energy: bool = False

    epsilon_lbmol: float = 1e-8

    def __post_init__(self):
        if self.n_stages <= 0:
            raise ValueError("n_stages must be > 0")
        if self.n_components <= 0:
            raise ValueError("n_components must be > 0")
        if self.epsilon_lbmol <= 0:
            raise ValueError("epsilon_lbmol must be > 0")

    def slices(self) -> Dict[str, slice]:
        """
        Deterministic slices for y.

        Order:
          tray_L (N*Nc)
          tray_V (N*Nc) [if include_vapor]
          top_L (Nc) [if include_top]
          top_V (Nc) [if include_top and include_vapor]
          bottom_L (Nc) [if include_bottom]
          bottom_V (Nc) [if include_bottom and include_vapor]
          tray_T_f (N) [if include_temperature]
          top_T_f (1) [if include_temperature and include_top]
          bottom_T_f (1) [if include_temperature and include_bottom]
          tray_EL_BTU (N) [if include_energy]
          tray_EV_BTU (N) [if include_energy and include_vapor]
        """
        N = self.n_stages
        Nc = self.n_components

        sl: Dict[str, slice] = {}
        idx = 0

        sl["tray_L"] = slice(idx, idx + N * Nc); idx += N * Nc

        if self.include_vapor:
            sl["tray_V"] = slice(idx, idx + N * Nc); idx += N * Nc

        if self.include_top:
            sl["top_L"] = slice(idx, idx + Nc); idx += Nc
            if self.include_vapor:
                sl["top_V"] = slice(idx, idx + Nc); idx += Nc

        if self.include_bottom:
            sl["bottom_L"] = slice(idx, idx + Nc); idx += Nc
            if self.include_vapor:
                sl["bottom_V"] = slice(idx, idx + Nc); idx += Nc

        if self.include_temperature:
            sl["tray_T_f"] = slice(idx, idx + N); idx += N
            if self.include_top:
                sl["top_T_f"] = slice(idx, idx + 1); idx += 1
            if self.include_bottom:
                sl["bottom_T_f"] = slice(idx, idx + 1); idx += 1

        if self.include_energy:
            sl["tray_EL_BTU"] = slice(idx, idx + N); idx += N
            if self.include_vapor:
                sl["tray_EV_BTU"] = slice(idx, idx + N); idx += N

        return sl

    def n_states(self) -> int:
        sl = self.slices()
        return max(s.stop for s in sl.values()) if sl else 0

    @staticmethod
    def _safe_norm_rows(mat: np.ndarray, eps: float) -> np.ndarray:
        s = mat.sum(axis=1, keepdims=True)
        s = np.where(s <= eps, 1.0, s)
        return mat / s

    @staticmethod
    def _safe_norm_vec(vec: np.ndarray, eps: float) -> np.ndarray:
        s = float(np.sum(vec))
        if s <= eps:
            return np.ones_like(vec) / float(vec.size)
        return vec / s

    def pack_y0(self, col, thermo: Optional[object] = None) -> np.ndarray:
        """
        Pack initial conditions from ColumnSpec-like object.

        Uses ColumnSpec naming (preferred):
          - M_L_lbmol (N,)
          - M_V_lbmol (N,)
          - x0 (N,Nc)
          - y0 (N,Nc)

        Legacy supported:
          - ML0_lbmol / MV0_lbmol
        """
        N = self.n_stages
        Nc = self.n_components
        sl = self.slices()

        y = np.zeros(self.n_states(), dtype=float)

        ML0 = np.asarray(
            _get_first_attr(col, ["M_L_lbmol", "ML0_lbmol"]),
            dtype=float
        ).reshape((N,))

        MV0 = np.asarray(
            _get_first_attr(col, ["M_V_lbmol", "MV0_lbmol"]),
            dtype=float
        ).reshape((N,))

        x0 = np.asarray(_get_first_attr(col, ["x0"]), dtype=float).reshape((N, Nc))
        y0v = np.asarray(_get_first_attr(col, ["y0"]), dtype=float).reshape((N, Nc))

        # Component holdup states
        tray_L = ML0[:, None] * x0
        y[sl["tray_L"]] = tray_L.ravel()

        if self.include_vapor:
            tray_V = MV0[:, None] * y0v
            y[sl["tray_V"]] = tray_V.ravel()

        # Boundary holdups: tiny eps allocations (doesn't affect tray states)
        if self.include_top:
            topL = self.epsilon_lbmol * self._safe_norm_vec(tray_L[0, :].copy(), self.epsilon_lbmol)
            y[sl["top_L"]] = topL
            if self.include_vapor:
                topV_base = (MV0[0] * y0v[0, :]).copy()
                topV = self.epsilon_lbmol * self._safe_norm_vec(topV_base, self.epsilon_lbmol)
                y[sl["top_V"]] = topV

        if self.include_bottom:
            botL = self.epsilon_lbmol * self._safe_norm_vec(tray_L[-1, :].copy(), self.epsilon_lbmol)
            y[sl["bottom_L"]] = botL
            if self.include_vapor:
                botV_base = (MV0[-1] * y0v[-1, :]).copy()
                botV = self.epsilon_lbmol * self._safe_norm_vec(botV_base, self.epsilon_lbmol)
                y[sl["bottom_V"]] = botV

        # Legacy temperature states (if enabled)
        if self.include_temperature:
            # Prefer col.T_f if present, else col.T0_F, else 100F
            if hasattr(col, "T_f"):
                Ttray = np.asarray(col.T_f, dtype=float).reshape((N,))
            elif hasattr(col, "T0_F"):
                Ttray = np.asarray(col.T0_F, dtype=float).reshape((N,))
            else:
                Ttray = np.full(N, 100.0, dtype=float)

            y[sl["tray_T_f"]] = Ttray

            if self.include_top and "top_T_f" in sl:
                y[sl["top_T_f"]] = np.array([float(Ttray[0])], dtype=float)
            if self.include_bottom and "bottom_T_f" in sl:
                y[sl["bottom_T_f"]] = np.array([float(Ttray[-1])], dtype=float)

        # Module 6 Option B1: energy holdup states
        if self.include_energy:
            # Defaults if missing
            if hasattr(col, "T0_F"):
                T0 = np.asarray(col.T0_F, dtype=float).reshape((N,))
            elif hasattr(col, "T_f"):
                T0 = np.asarray(col.T_f, dtype=float).reshape((N,))
            else:
                T0 = np.full(N, 100.0, dtype=float)

            if hasattr(col, "P0_psia"):
                P0 = np.asarray(col.P0_psia, dtype=float).reshape((N,))
            elif hasattr(col, "P_psia"):
                P0 = np.asarray(col.P_psia, dtype=float).reshape((N,))
            else:
                P0 = np.full(N, 200.0, dtype=float)

            EL = np.zeros(N, dtype=float)
            EV = np.zeros(N, dtype=float)

            for i in range(N):
                ML = max(float(ML0[i]), self.epsilon_lbmol)
                MV = max(float(MV0[i]), self.epsilon_lbmol)

                # overall z based on phase holdups
                z = tray_L[i, :].copy()
                if self.include_vapor:
                    z = z + (MV0[i] * y0v[i, :])
                z = self._safe_norm_vec(z, self.epsilon_lbmol)

                if thermo is not None and hasattr(thermo, "flash_TP_full"):
                    fres = thermo.flash_TP_full(float(T0[i]), float(P0[i]), z)
                    hL = float(fres.HL_BTU_lbmol)
                    hV = float(fres.HV_BTU_lbmol)
                else:
                    # safe placeholder: nonzero enthalpies
                    hL = float(T0[i])
                    hV = float(T0[i])

                EL[i] = ML * hL
                EV[i] = MV * hV

            y[sl["tray_EL_BTU"]] = EL
            if self.include_vapor and "tray_EV_BTU" in sl:
                y[sl["tray_EV_BTU"]] = EV

        return y

    def unpack(self, y: np.ndarray) -> Dict[str, np.ndarray]:
        N = self.n_stages
        Nc = self.n_components
        sl = self.slices()

        y = np.asarray(y, dtype=float).ravel()
        if y.size != self.n_states():
            raise ValueError(f"y has size {y.size}, expected {self.n_states()}")

        out: Dict[str, np.ndarray] = {}

        tray_L = y[sl["tray_L"]].reshape((N, Nc)).copy()
        out["tray_L"] = tray_L

        if self.include_vapor:
            tray_V = y[sl["tray_V"]].reshape((N, Nc)).copy()
            out["tray_V"] = tray_V

        if self.include_top:
            out["top_L"] = y[sl["top_L"]].reshape((Nc,)).copy()
            if self.include_vapor:
                out["top_V"] = y[sl["top_V"]].reshape((Nc,)).copy()

        if self.include_bottom:
            out["bottom_L"] = y[sl["bottom_L"]].reshape((Nc,)).copy()
            if self.include_vapor:
                out["bottom_V"] = y[sl["bottom_V"]].reshape((Nc,)).copy()

        # Derived mole fractions
        out["x_tray"] = self._safe_norm_rows(np.clip(tray_L, 0.0, None), self.epsilon_lbmol)
        if self.include_vapor:
            out["y_tray"] = self._safe_norm_rows(np.clip(out["tray_V"], 0.0, None), self.epsilon_lbmol)

        # Totals (compat keys expected by existing code/tests)
        out["ML_tot_tray"] = tray_L.sum(axis=1).copy()
        if self.include_vapor:
            out["MV_tot_tray"] = out["tray_V"].sum(axis=1).copy()

        # Temperature states (legacy)
        if self.include_temperature:
            out["tray_T_f"] = y[sl["tray_T_f"]].reshape((N,)).copy()
            if self.include_top and "top_T_f" in sl:
                out["top_T_f"] = y[sl["top_T_f"]].reshape((1,)).copy()
            if self.include_bottom and "bottom_T_f" in sl:
                out["bottom_T_f"] = y[sl["bottom_T_f"]].reshape((1,)).copy()

        # Energy holdup states
        if self.include_energy:
            out["tray_EL_BTU"] = y[sl["tray_EL_BTU"]].reshape((N,)).copy()
            if self.include_vapor and "tray_EV_BTU" in sl:
                out["tray_EV_BTU"] = y[sl["tray_EV_BTU"]].reshape((N,)).copy()

        return out