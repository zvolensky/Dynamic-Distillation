"""
thermo_model_v1.py

Dynamic Distillation - Thermo model interface (v1)

Created: 2026-01-11  (America/New_York)

Purpose
-------
Provide a minimal thermo/enthalpy API for energy balance scaffolding.

Notes
-----
- This is intentionally simple and "plug-compatible" with future PR/DWSIM thermo.
- Includes a z_factor() hook for later high-pressure non-ideality.

Units (convention for this project, v1)
---------------------------------------
- Temperature: degF
- Pressure: psia
- Enthalpy: Btu/lbmol
- Heat capacity: Btu/(lbmol*F)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class ThermoModel(Protocol):
    def h_liq_btu_per_lbmol(self, T_f: float, P_psia: float, x: np.ndarray) -> float: ...
    def h_vap_btu_per_lbmol(self, T_f: float, P_psia: float, y: np.ndarray) -> float: ...
    def cp_liq_btu_per_lbmolF(self, T_f: float, P_psia: float, x: np.ndarray) -> float: ...
    def cp_vap_btu_per_lbmolF(self, T_f: float, P_psia: float, y: np.ndarray) -> float: ...
    def z_factor(self, T_f: float, P_psia: float, y: np.ndarray) -> float: ...


@dataclass(frozen=True)
class ConstantCpThermo:
    """
    Placeholder thermo:
      h = cp_mix * (T - Tref)
      cp_mix = sum(z_i * cp_i)

    This is NOT physically rigorous.
    It exists to get the energy-balance plumbing correct.
    """
    cp_liq_components: np.ndarray  # (Nc,) Btu/(lbmol*F)
    cp_vap_components: np.ndarray  # (Nc,) Btu/(lbmol*F)
    tref_f: float = 60.0

    def _cp_mix(self, z: np.ndarray, cps: np.ndarray) -> float:
        z = np.asarray(z, dtype=float)
        cps = np.asarray(cps, dtype=float)
        if z.ndim != 1 or cps.ndim != 1 or z.size != cps.size:
            raise ValueError("Composition and cp arrays must be 1-D and same length.")
        return float(np.dot(z, cps))

    def cp_liq_btu_per_lbmolF(self, T_f: float, P_psia: float, x: np.ndarray) -> float:
        return self._cp_mix(x, self.cp_liq_components)

    def cp_vap_btu_per_lbmolF(self, T_f: float, P_psia: float, y: np.ndarray) -> float:
        return self._cp_mix(y, self.cp_vap_components)

    def h_liq_btu_per_lbmol(self, T_f: float, P_psia: float, x: np.ndarray) -> float:
        cp = self.cp_liq_btu_per_lbmolF(T_f, P_psia, x)
        return cp * (float(T_f) - self.tref_f)

    def h_vap_btu_per_lbmol(self, T_f: float, P_psia: float, y: np.ndarray) -> float:
        cp = self.cp_vap_btu_per_lbmolF(T_f, P_psia, y)
        return cp * (float(T_f) - self.tref_f)

    def z_factor(self, T_f: float, P_psia: float, y: np.ndarray) -> float:
        # Placeholder: ideal-gas Z=1.0
        # Later: PR/SRK/DWSIM EOS here.
        return 1.0
