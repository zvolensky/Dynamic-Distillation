# src/dynamic_distillation/thermo_provider_v1.py
"""
thermo_provider_v1.py

Header:
  Created: 2026-01-11 15:xx (America/New_York)
  Updated: 2026-01-11 16:58 (America/New_York)
  Purpose: Thermo provider that the column model calls.
           DWSIM primary via pr_flash_backend_v1; no hard-wired compounds.

Notes:
  - Case provides Excel component names (for logging + fallback).
  - Compound registry maps Excel names -> DWSIM compound IDs.
  - This provider pushes both lists into the backend.
  - Z-factor is optional; when unavailable we default diagnostics to Z=1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from dynamic_distillation import pr_flash_backend_v1 as backend


@dataclass(frozen=True)
class FlashResult:
    x: np.ndarray               # (Nc,)
    y: np.ndarray               # (Nc,)
    K: np.ndarray               # (Nc,)
    HL_BTU_lbmol: float
    HV_BTU_lbmol: float
    Z: Optional[float] = None
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

    def configure_backend(self) -> None:
        backend.set_component_ids(self.component_ids_dwsim)

        # Backward-compatible name setter (tests use set_component_names)
        if hasattr(backend, "set_component_names_excel"):
            backend.set_component_names_excel(self.component_names_excel)
        elif hasattr(backend, "set_component_names"):
            backend.set_component_names(self.component_names_excel)
        else:
            # Not fatal for many backends; leave it as a no-op.
            pass


    @staticmethod
    def _normalize_z(z: Sequence[float], n: int) -> np.ndarray:
        z = np.asarray(z, dtype=float).reshape((-1,))
        if z.size != n:
            raise ValueError(f"Expected z length {n}, got {z.size}")
        s = float(np.sum(z))
        if s <= 0.0:
            raise ValueError("z sum must be > 0")
        return z / s

    def flash_TP_full(self, T_F: float, P_psia: float, z: Sequence[float]) -> FlashResult:
        """Full TP flash: x,y,K plus liquid/vapor molar enthalpies."""
        self.configure_backend()
        Nc = len(self.component_ids_dwsim)
        z_norm = self._normalize_z(z, Nc)

        with backend.silence_console(self.silence_backend_console):
            res = backend.flash_TP_full_F_psia(float(T_F), float(P_psia), z_norm)

        Zfac: Optional[float] = None
        if isinstance(res, (tuple, list)):
            if len(res) == 5:
                x, y, K, HL, HV = res
            elif len(res) == 6:
                x, y, K, HL, HV, Zfac = res
            else:
                raise RuntimeError("backend.flash_TP_full_F_psia must return 5 or 6 values")
        else:
            raise RuntimeError("backend.flash_TP_full_F_psia must return a tuple/list")

        cpL, cpV = self._cp_from_backend(float(T_F), float(P_psia), z_norm)

        return FlashResult(
            x=np.asarray(x, dtype=float),
            y=np.asarray(y, dtype=float),
            K=np.asarray(K, dtype=float),
            HL_BTU_lbmol=float(HL),
            HV_BTU_lbmol=float(HV),
            Z=(float(Zfac) if Zfac is not None else None),
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
            return cpL, cpV
        except Exception:
            pass

        # Fallback: central-ish finite diff (2 calls)
        dt = float(self.cp_dt_F)
        try:
            with backend.silence_console(self.silence_backend_console):
                _x0, _y0, _K0, HL0, HV0 = backend.flash_TP_full_F_psia(T_F, P_psia, z_norm)
                _x1, _y1, _K1, HL1, HV1 = backend.flash_TP_full_F_psia(T_F + dt, P_psia, z_norm)
            cpL = (float(HL1) - float(HL0)) / dt
            cpV = (float(HV1) - float(HV0)) / dt
            return cpL, cpV
        except Exception:
            return None, None