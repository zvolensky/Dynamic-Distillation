"""
thermo_relative_volatility_provider_v1.py

Dynamic Distillation - Simple Relative Volatility Thermo Provider

PURPOSE
-------
Provide a deterministic, dependency-free thermo backend for validation cases
where column dynamics and energy-balance plumbing are the focus rather than
rigorous phase-equilibrium thermodynamics.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import time
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from dynamic_distillation.thermo_provider_v1 import FlashResult


@dataclass(frozen=True)
class RelativeVolatilityDefaults:
    alpha_light: float = 1.6
    tref_F: float = 60.0
    normal_boiling_F_light: float = 180.0
    normal_boiling_F_heavy: float = 230.0
    cp_liq_light: float = 35.0
    cp_liq_heavy: float = 42.0
    cp_vap_light: float = 24.0
    cp_vap_heavy: float = 28.0
    latent_light: float = 7800.0
    latent_heavy: float = 8800.0
    mw_light: float = 58.12
    mw_heavy: float = 72.15
    liquid_density_lbmol_ft3: float = 1.0


class RelativeVolatilityThermoProviderV1:
    """Constant-alpha VLE with simple Cp/latent-heat enthalpy surfaces."""

    def __init__(
        self,
        component_names_excel: Sequence[str],
        component_ids_dwsim: Optional[Sequence[str]] = None,
        *,
        alpha_light: float = 1.6,
        relative_volatility: Optional[Sequence[float]] = None,
        defaults: RelativeVolatilityDefaults = RelativeVolatilityDefaults(),
    ):
        self.component_names_excel = [str(s) for s in component_names_excel]
        self.component_ids_dwsim = [str(s) for s in (component_ids_dwsim or component_names_excel)]
        self.defaults = defaults
        self.uses_liquid_composition_for_equilibrium = True
        self.uses_direct_vapor_equilibrium = True
        self._thermo_call_counters: Dict[str, Dict[str, float | int]] = defaultdict(dict)
        self._thermo_call_category_stack: list[str] = []
        n = len(self.component_names_excel)
        if n <= 0:
            raise ValueError("RelativeVolatilityThermoProviderV1 requires at least one component.")

        if relative_volatility is None:
            if n == 1:
                rv = np.ones(1, dtype=float)
            else:
                rv = np.linspace(float(alpha_light), 1.0, n, dtype=float)
        else:
            rv = np.asarray(relative_volatility, dtype=float).reshape((-1,))
            if rv.size != n:
                raise ValueError("relative_volatility length must match the component count.")
        if np.any(~np.isfinite(rv)) or np.any(rv <= 0.0):
            raise ValueError("relative_volatility values must be finite and positive.")
        self.relative_volatility = rv.astype(float)

        self._nbp_F = self._profile(defaults.normal_boiling_F_light, defaults.normal_boiling_F_heavy, n)
        self._cpL = self._profile(defaults.cp_liq_light, defaults.cp_liq_heavy, n)
        self._cpV = self._profile(defaults.cp_vap_light, defaults.cp_vap_heavy, n)
        self._latent = self._profile(defaults.latent_light, defaults.latent_heavy, n)
        self._mw = self._profile(defaults.mw_light, defaults.mw_heavy, n)

    @staticmethod
    def _profile(first: float, last: float, n: int) -> np.ndarray:
        if n == 1:
            return np.array([float(first)], dtype=float)
        return np.linspace(float(first), float(last), int(n), dtype=float)

    @staticmethod
    def _normalize(z: Sequence[float], n: int) -> np.ndarray:
        arr = np.asarray(z, dtype=float).reshape((-1,))
        if arr.size != n:
            raise ValueError(f"Composition length {arr.size} does not match expected component count {n}.")
        arr = np.clip(arr, 0.0, None)
        s = float(np.sum(arr))
        if not np.isfinite(s) or s <= 0.0:
            return np.full(n, 1.0 / float(n), dtype=float)
        return arr / s

    def _record_call_counter(self, metric: str, amount: float | int = 1, *, category: Optional[str] = None) -> None:
        cat = str(category or (self._thermo_call_category_stack[-1] if self._thermo_call_category_stack else "uncategorized"))
        bucket = self._thermo_call_counters.setdefault(cat, {})
        if str(metric).endswith("_sec"):
            bucket[metric] = float(bucket.get(metric, 0.0)) + float(amount)
        else:
            bucket[metric] = int(bucket.get(metric, 0)) + int(amount)

    def get_call_counters(self) -> Dict[str, Dict[str, float | int]]:
        return {cat: dict(metrics) for cat, metrics in self._thermo_call_counters.items()}

    @contextmanager
    def thermo_call_category(self, category: Optional[str]):
        self._thermo_call_category_stack.append(str(category or "uncategorized"))
        try:
            yield
        finally:
            if self._thermo_call_category_stack:
                self._thermo_call_category_stack.pop()

    def _flash_arrays(self, T_F: float, P_psia: float, z: Sequence[float]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float, float, float, float]:
        _ = float(P_psia)
        n = len(self.relative_volatility)
        x = self._normalize(z, n)
        y, K = self.equilibrium_y_K_from_x(x)
        HL = self.phase_enthalpy_BTU_lbmol("liquid", float(T_F), float(P_psia), x)
        HV = self.phase_enthalpy_BTU_lbmol("vapor", float(T_F), float(P_psia), y)
        cpL, cpV = self.cp_liq_vap_btu_per_lbmolF(float(T_F), float(P_psia), x)
        return x, y, K.astype(float), float(HL), float(HV), 1.0, float(cpL), float(cpV)

    def equilibrium_y_K_from_x(self, x: Sequence[float]) -> Tuple[np.ndarray, np.ndarray]:
        n = len(self.relative_volatility)
        x_norm = self._normalize(x, n)
        y_raw = self.relative_volatility * x_norm
        denom = max(float(np.sum(y_raw)), 1.0e-300)
        y = y_raw / denom
        K = self.relative_volatility / denom
        return y.astype(float), K.astype(float)

    def flash_TP_full_F_psia(self, T_F: float, P_psia: float, z: Sequence[float]):
        t0 = time.perf_counter()
        self._record_call_counter("flash_requests", 1)
        x, y, K, HL, HV, Z, _cpL, _cpV = self._flash_arrays(T_F, P_psia, z)
        self._record_call_counter("wall_sec", time.perf_counter() - t0)
        return x, y, K, HL, HV, Z

    def flash_TP_full_stage_F_psia(self, stage_index0: int, T_F: float, P_psia: float, z: Sequence[float]):
        _ = int(stage_index0)
        return self.flash_TP_full_F_psia(T_F, P_psia, z)

    def flash_TP_full(self, T_F: float, P_psia: float, z: Sequence[float]) -> FlashResult:
        x, y, K, HL, HV, Z, cpL, cpV = self._flash_arrays(T_F, P_psia, z)
        return FlashResult(
            x=x,
            y=y,
            K=K,
            HL_BTU_lbmol=HL,
            HV_BTU_lbmol=HV,
            Z=Z,
            cpL_BTU_lbmolF=cpL,
            cpV_BTU_lbmolF=cpV,
        )

    def flash_TP_full_batch(self, T_rows: Sequence[float], P_rows: Sequence[float], z_rows: Sequence[Sequence[float]]):
        if len(T_rows) != len(P_rows) or len(T_rows) != len(z_rows):
            raise ValueError("flash_TP_full_batch requires equal-length T, P, and z row collections.")
        return [self.flash_TP_full(float(T), float(P), z) for T, P, z in zip(T_rows, P_rows, z_rows)]

    def cp_liq_vap_btu_per_lbmolF(self, T_F: float, P_psia: float, z: Sequence[float]) -> Tuple[float, float]:
        _ = (float(T_F), float(P_psia))
        comp = self._normalize(z, len(self.relative_volatility))
        return float(np.dot(comp, self._cpL)), float(np.dot(comp, self._cpV))

    def phase_enthalpy_BTU_lbmol(self, phase: str, T_F: float, P_psia: float, comp: Sequence[float]) -> float:
        _ = float(P_psia)
        z = self._normalize(comp, len(self.relative_volatility))
        dT = float(T_F) - float(self.defaults.tref_F)
        phase_norm = str(phase or "").strip().lower()
        if phase_norm.startswith("v"):
            return float(np.dot(z, self._latent + self._cpV * dT))
        return float(np.dot(z, self._cpL * dT))

    def liquid_density_lbmol_ft3(self, T_F: float, P_psia: float, x: Sequence[float]) -> float:
        _ = (float(T_F), float(P_psia), self._normalize(x, len(self.relative_volatility)))
        return float(self.defaults.liquid_density_lbmol_ft3)

    def vapor_z_factor_F_psia(self, T_F: float, P_psia: float, y: Sequence[float]) -> float:
        _ = (float(T_F), float(P_psia), self._normalize(y, len(self.relative_volatility)))
        return 1.0

    def bubble_point_temperature_F_psia(self, P_psia: float, x: Sequence[float]) -> float:
        _ = float(P_psia)
        comp = self._normalize(x, len(self.relative_volatility))
        return float(np.dot(comp, self._nbp_F))

    def component_mw_lbm_per_lbmol(self) -> np.ndarray:
        return self._mw.copy()
