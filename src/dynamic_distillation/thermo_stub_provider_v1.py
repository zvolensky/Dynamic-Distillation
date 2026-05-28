"""
thermo_stub_provider_v1.py

Dynamic Distillation - Stub Thermo Provider

PURPOSE
-------
Provide a deterministic thermo backend for smoke tests and runner modes that do
not require live or tabular thermo fidelity.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np


def _normalize_comp(z: Sequence[float]) -> np.ndarray:
    z_arr = np.asarray(z, dtype=float).reshape((-1,))
    s = float(np.sum(z_arr))
    if (not np.isfinite(s)) or s <= 0.0:
        n = int(z_arr.size)
        return np.full(n, 1.0 / max(n, 1), dtype=float)
    return z_arr / s


class StubThermoProvider:
    """Deterministic stub provider with constant K, Z, Cp, and density."""

    def __init__(self, K: Sequence[float], Z: float = 1.0):
        self._K = np.asarray(K, dtype=float).ravel()
        self._Z = float(Z)

    def flash_TP_full_F_psia(self, T_F: float, P_psia: float, z: List[float]):
        z_arr = _normalize_comp(z)
        K = self._K.copy()
        x = z_arr
        y = _normalize_comp(K * x)
        HL = 0.0
        HV = 0.0
        return (x.tolist(), y.tolist(), K.tolist(), HL, HV, float(self._Z))

    def flash_TP_full(self, T_F: float, P_psia: float, z: List[float]):
        return self.flash_TP_full_F_psia(T_F, P_psia, z)

    def liquid_density_lbmol_ft3(self, T_F: float, P_psia: float, x: List[float]) -> float:
        return 1.0

    def cp_liq_vap_btu_per_lbmolF(self, T_F: float, P_psia: float, z: List[float]):
        return (30.0, 20.0)
