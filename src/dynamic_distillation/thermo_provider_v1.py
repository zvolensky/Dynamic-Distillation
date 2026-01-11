# src/dynamic_distillation/thermo_provider_v1.py
"""
thermo_provider_v1.py

Header:
  Created: 2026-01-11 15:xx (America/New_York)
  Purpose: Thermo provider that the column model calls.
           DWSIM primary via pr_flash_backend_v1; no hard-wired compounds.

Notes:
  - Case provides Excel component names (for logging + fallback).
  - Compound registry maps Excel names -> DWSIM compound IDs.
  - This provider pushes both lists into the backend.
  - Z-factor integration is planned later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from . import pr_flash_backend_v1 as backend


@dataclass(frozen=True)
class FlashResult:
    x: np.ndarray               # (Nc,)
    y: np.ndarray               # (Nc,)
    K: np.ndarray               # (Nc,)
    HL_BTU_lbmol: float
    HV_BTU_lbmol: float
    cpL_BTU_lbmolF: Optional[float] = None
    cpV_BTU_lbmolF: Optional[float] = None


class ThermoProviderV1:
    """
    Thermo provider for the dynamic column model.

    Public method:
      flash_TP_full(T_F, P_psia, z) -> FlashResult
    """

    def __init__(
        self,
        component_names_excel: Sequence[str],
        component_ids_dwsim: Sequence[str],
        cp_dt_F: float = 1.0,
        silence_backend_console: bool = True,
    ):
        self.component_names_excel = [str(s) for s in component_names_excel]
        self.component_ids_dwsim = [str(s) for s in component_ids_dwsim]
        self.cp_dt_F = float(cp_dt_F)
        self.silence_backend_console = bool(silence_backend_console)

        if not self.component_names_excel:
            raise ValueError("component_names_excel must be non-empty")
        if len(self.component_ids_dwsim) != len(self.component_names_excel):
            raise ValueError("Excel names and DWSIM IDs must be the same length")

        self._configured = False

    def configure_backend(self) -> None:
        """Push component mapping into backend (idempotent)."""
        if self._configured:
            return
        backend.set_component_ids(list(self.component_ids_dwsim))
        backend.set_component_names(list(self.component_names_excel))
        self._configured = True

    @staticmethod
    def _normalize_z(z: Sequence[float], n: int) -> np.ndarray:
        zz = np.asarray(z, dtype=float).ravel()
        if zz.size != n:
            raise ValueError(f"z must have length {n}; got {zz.size}")
        s = float(zz.sum())
        if not np.isfinite(s) or s <= 0.0:
            raise ValueError("z must have a finite positive sum")
        return zz / s

    def flash_TP_full(self, T_F: float, P_psia: float, z: Sequence[float]) -> FlashResult:
        """Full TP flash: x,y,K plus liquid/vapor molar enthalpies."""
        self.configure_backend()
        Nc = len(self.component_ids_dwsim)
        z_norm = self._normalize_z(z, Nc)

        with backend.silence_console(self.silence_backend_console):
            x, y, K, HL, HV = backend.flash_TP_full_F_psia(float(T_F), float(P_psia), z_norm)

        cpL, cpV = self._cp_from_backend(float(T_F), float(P_psia), z_norm)

        return FlashResult(
            x=np.asarray(x, dtype=float),
            y=np.asarray(y, dtype=float),
            K=np.asarray(K, dtype=float),
            HL_BTU_lbmol=float(HL),
            HV_BTU_lbmol=float(HV),
            cpL_BTU_lbmolF=cpL,
            cpV_BTU_lbmolF=cpV,
        )

    def _cp_from_backend(self, T_F: float, P_psia: float, z_norm: np.ndarray) -> Tuple[Optional[float], Optional[float]]:
        """Prefer backend coefficients; fall back to finite difference."""
        # Preferred path: backend.get_thermo_coefficients (already does one finite diff)
        try:
            with backend.silence_console(self.silence_backend_console):
                coeffs, _ = backend.get_thermo_coefficients(T_F, P_psia, z_norm, perturbation_dt=self.cp_dt_F)
            cpL = float(coeffs["HL_B"])
            cpV = float(coeffs["HV_B"])
            if np.isfinite(cpL) and np.isfinite(cpV):
                return cpL, cpV
        except Exception:
            pass

        # Fallback path: do finite difference directly
        try:
            dt = float(self.cp_dt_F)
            if dt <= 0:
                return None, None
            with backend.silence_console(self.silence_backend_console):
                _x0, _y0, _K0, HL0, HV0 = backend.flash_TP_full_F_psia(T_F, P_psia, z_norm)
                _x1, _y1, _K1, HL1, HV1 = backend.flash_TP_full_F_psia(T_F + dt, P_psia, z_norm)
            cpL = (float(HL1) - float(HL0)) / dt
            cpV = (float(HV1) - float(HV0)) / dt
            if np.isfinite(cpL) and np.isfinite(cpV):
                return cpL, cpV
        except Exception:
            return None, None

        return None, None