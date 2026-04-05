# src/dynamic_distillation/thermo_provider_v1.py
"""
thermo_provider_v1.py

Dynamic Distillation - High-Level Thermo Provider

PURPOSE
-------
Expose stable thermo APIs (flash, Cp, density, MW helpers) to runner/RHS while
encapsulating backend setup and call conventions.

INPUTS
------
ThermoProviderV1 constructor:
- component_names_excel, component_ids_dwsim
- optional finite-difference temperature delta for Cp
- optional backend console-silencing behavior

Runtime calls:
- flash_TP_full / flash_TP_full_F_psia
- cp_liq_vap_btu_per_lbmolF
- liquid_density_lbmol_ft3
- component_mw_lbm_per_lbmol

OUTPUTS
-------
- FlashResult dataclass for flash calls
- scalar property values for Cp/density/MW utilities

KEY DEPENDENCIES
----------------
- pr_flash_backend_v1
- numpy

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Provider is configured for a fixed ordered component set.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import time
from typing import Dict, Optional, Sequence, Tuple

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
        property_package: str = "pr",
    ):
        self.component_names_excel = [str(s) for s in component_names_excel]
        self.component_ids_dwsim = [str(s) for s in component_ids_dwsim]
        self.cp_dt_F = float(cp_dt_F)
        self.silence_backend_console = bool(silence_backend_console)
        self.property_package = str(property_package or "pr")
        self._rhoL_cache: dict[tuple, float] = {}
        self._rhoL_cache_max = 2000
        self._cp_cache: dict[tuple, tuple[Optional[float], Optional[float]]] = {}
        self._cp_cache_max = 2000
        self._mw_components_cache: Optional[np.ndarray] = None
        self.debug_trace_hook = None
        self.debug_trace_context = ""
        self._thermo_call_category_stack: list[str] = []
        self._thermo_call_counters: Dict[str, Dict[str, float]] = defaultdict(dict)

    def configure_backend(self) -> None:
        backend.set_component_ids(self.component_ids_dwsim)
        backend.set_property_package(self.property_package)
        if hasattr(backend, "set_debug_trace_hook"):
            backend.set_debug_trace_hook(self.debug_trace_hook)
        if hasattr(backend, "set_debug_trace_context"):
            backend.set_debug_trace_context(self.debug_trace_context)

        # Backward-compatible name setter (tests use set_component_names)
        if hasattr(backend, "set_component_names_excel"):
            backend.set_component_names_excel(self.component_names_excel)
        elif hasattr(backend, "set_component_names"):
            backend.set_component_names(self.component_names_excel)
        else:
            # Not fatal for many backends; leave it as a no-op.
            pass

    def set_debug_trace_context(self, context: Optional[str]) -> None:
        self.debug_trace_context = str(context or "")
        if hasattr(backend, "set_debug_trace_context"):
            backend.set_debug_trace_context(self.debug_trace_context)

    def reset_call_counters(self) -> None:
        self._thermo_call_counters = defaultdict(dict)
        self._thermo_call_category_stack = []

    def get_call_counters(self) -> Dict[str, Dict[str, float | int]]:
        out: Dict[str, Dict[str, float | int]] = {}
        for category, metrics in self._thermo_call_counters.items():
            out_cat: Dict[str, float | int] = {}
            for metric, value in metrics.items():
                try:
                    val = float(value)
                except Exception:
                    continue
                if str(metric).endswith("_sec"):
                    out_cat[str(metric)] = float(val)
                else:
                    ival = int(round(val))
                    if abs(val - float(ival)) <= 1.0e-12:
                        out_cat[str(metric)] = int(ival)
                    else:
                        out_cat[str(metric)] = float(val)
            out[str(category)] = out_cat
        return out

    def _current_call_category(self) -> str:
        if self._thermo_call_category_stack:
            txt = str(self._thermo_call_category_stack[-1]).strip()
            if txt:
                return txt
        return "uncategorized"

    def _record_call_counter(self, metric: str, amount: float = 1, *, category: Optional[str] = None) -> None:
        try:
            amt = float(amount)
        except Exception:
            amt = 0.0
        if amt == 0:
            return
        cat = str(category or self._current_call_category()).strip() or "uncategorized"
        bucket = self._thermo_call_counters.setdefault(cat, {})
        bucket[str(metric)] = float(bucket.get(str(metric), 0.0)) + float(amt)

    @contextmanager
    def thermo_call_category(self, category: Optional[str]):
        cat = str(category or "").strip()
        if not cat:
            yield
            return
        prev_context = str(getattr(self, "debug_trace_context", "") or "")
        self._thermo_call_category_stack.append(cat)
        scoped_context = cat if not prev_context else f"{prev_context}:{cat}"
        self.set_debug_trace_context(scoped_context)
        try:
            yield
        finally:
            self.set_debug_trace_context(prev_context)
            if self._thermo_call_category_stack:
                self._thermo_call_category_stack.pop()


    @staticmethod
    def _normalize_z(z: Sequence[float], n: int) -> np.ndarray:
        z = np.asarray(z, dtype=float).reshape((-1,))
        if z.size != n:
            raise ValueError(f"Expected z length {n}, got {z.size}")
        s = float(np.sum(z))
        if s <= 0.0:
            raise ValueError("z sum must be > 0")
        return z / s

    def _flash_backend_only(
        self,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float, Optional[float]]:
        """
        Raw backend TP flash without Cp evaluation.

        This is the lightweight path used by stage_thermo_v1 and other tight
        tray-loop callers that only need flash outputs. Cp remains available
        through explicit cp_liq_vap_btu_per_lbmolF() calls.
        """
        self.configure_backend()
        Nc = len(self.component_ids_dwsim)
        z_norm = self._normalize_z(z, Nc)
        self._record_call_counter("flash_requests", 1)
        self._record_call_counter("backend_flash_equivalents", 1)

        t0 = time.perf_counter()
        with backend.silence_console(self.silence_backend_console):
            res = backend.flash_TP_full_F_psia(float(T_F), float(P_psia), z_norm)
        self._record_call_counter("wall_sec", float(time.perf_counter() - t0))

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

        return (
            np.asarray(x, dtype=float),
            np.asarray(y, dtype=float),
            np.asarray(K, dtype=float),
            float(HL),
            float(HV),
            (float(Zfac) if Zfac is not None else None),
        )

    def flash_TP_full_F_psia(self, T_F: float, P_psia: float, z: Sequence[float]):
        """
        Lightweight TP flash tuple for adapter callers that do not need Cp.
        """
        return self._flash_backend_only(float(T_F), float(P_psia), z)

    def flash_TP_full_stage_F_psia(
        self,
        stage_index0: int,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
    ):
        """
        Stage-aware alias for compatibility with stage_thermo_v1.

        The DWSIM backend is currently stage-agnostic, so stage_index0 is
        accepted for interface compatibility but not used in the flash itself.
        """
        _ = int(stage_index0)
        return self._flash_backend_only(float(T_F), float(P_psia), z)

    def flash_TP_full(self, T_F: float, P_psia: float, z: Sequence[float]) -> FlashResult:
        """Full TP flash: x,y,K plus liquid/vapor molar enthalpies."""
        x, y, K, HL, HV, Zfac = self._flash_backend_only(float(T_F), float(P_psia), z)
        z_norm = self._normalize_z(z, len(self.component_ids_dwsim))
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
        self._record_call_counter("cp_requests", 1)
        # Preferred path: backend.get_thermo_coefficients (already does one finite diff)
        try:
            self._record_call_counter("backend_flash_equivalents", 2)
            t0 = time.perf_counter()
            with backend.silence_console(self.silence_backend_console):
                coeffs, _ = backend.get_thermo_coefficients(T_F, P_psia, z_norm, perturbation_dt=self.cp_dt_F)
            self._record_call_counter("wall_sec", float(time.perf_counter() - t0))
            cpL = float(coeffs["HL_B"])
            cpV = float(coeffs["HV_B"])
            return cpL, cpV
        except Exception:
            pass

        # Fallback: central-ish finite diff (2 calls)
        dt = float(self.cp_dt_F)
        try:
            self._record_call_counter("backend_flash_equivalents", 2)
            t0 = time.perf_counter()
            with backend.silence_console(self.silence_backend_console):
                _x0, _y0, _K0, HL0, HV0 = backend.flash_TP_full_F_psia(T_F, P_psia, z_norm)
                _x1, _y1, _K1, HL1, HV1 = backend.flash_TP_full_F_psia(T_F + dt, P_psia, z_norm)
            self._record_call_counter("wall_sec", float(time.perf_counter() - t0))
            cpL = (float(HL1) - float(HL0)) / dt
            cpV = (float(HV1) - float(HV0)) / dt
            return cpL, cpV
        except Exception:
            return None, None

    def cp_liq_vap_btu_per_lbmolF(self, T_F: float, P_psia: float, z: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
        """Stage-dependent Cp (liquid/vapor) from thermo backend."""
        self.configure_backend()
        Nc = len(self.component_ids_dwsim)
        z_norm = self._normalize_z(z, Nc)

        key = (
            round(float(T_F), 3),
            round(float(P_psia), 3),
            tuple(float(f"{v:.8f}") for v in z_norm.tolist()),
        )
        if key in self._cp_cache:
            self._record_call_counter("cp_cache_hits", 1)
            return self._cp_cache[key]
        self._record_call_counter("cp_cache_misses", 1)

        cpL, cpV = self._cp_from_backend(float(T_F), float(P_psia), z_norm)
        self._cp_cache[key] = (cpL, cpV)
        if len(self._cp_cache) > self._cp_cache_max:
            self._cp_cache.clear()
        return cpL, cpV

    def liquid_density_lbmol_ft3(self, T_F: float, P_psia: float, x: Sequence[float]) -> Optional[float]:
        """Liquid molar density (lbmol/ft^3) from thermo backend."""
        self.configure_backend()
        Nc = len(self.component_ids_dwsim)
        x_norm = self._normalize_z(x, Nc)

        # Cache by (T,P,x) to avoid repeated backend calls.
        key = (
            round(float(T_F), 3),
            round(float(P_psia), 3),
            tuple(float(f"{v:.8f}") for v in x_norm.tolist()),
        )
        if key in self._rhoL_cache:
            self._record_call_counter("rhoL_cache_hits", 1)
            return self._rhoL_cache[key]
        self._record_call_counter("rhoL_cache_misses", 1)
        self._record_call_counter("rhoL_requests", 1)

        try:
            t0 = time.perf_counter()
            with backend.silence_console(self.silence_backend_console):
                rho = backend.liquid_density_lbmol_ft3(float(T_F), float(P_psia), x_norm)
            self._record_call_counter("wall_sec", float(time.perf_counter() - t0))
            if rho is not None:
                self._rhoL_cache[key] = float(rho)
                if len(self._rhoL_cache) > self._rhoL_cache_max:
                    self._rhoL_cache.clear()
            return rho
        except Exception:
            return None

    def phase_enthalpy_BTU_lbmol(
        self,
        phase: str,
        T_F: float,
        P_psia: float,
        comp: Sequence[float],
    ) -> float:
        """Phase molar enthalpy (BTU/lbmol) from thermo backend."""
        self.configure_backend()
        Nc = len(self.component_ids_dwsim)
        comp_norm = self._normalize_z(comp, Nc)
        with backend.silence_console(self.silence_backend_console):
            return float(
                backend.phase_enthalpy_BTU_lbmol(
                    float(T_F),
                    float(P_psia),
                    comp_norm,
                    str(phase),
                )
            )

    def vapor_z_factor_F_psia(
        self,
        T_F: float,
        P_psia: float,
        y: Sequence[float],
    ) -> Optional[float]:
        """Vapor-phase compressibility factor from thermo backend."""
        self.configure_backend()
        Nc = len(self.component_ids_dwsim)
        y_norm = self._normalize_z(y, Nc)
        with backend.silence_console(self.silence_backend_console):
            zfac = backend.vapor_z_factor_F_psia(float(T_F), float(P_psia), y_norm)
        if zfac is None:
            return None
        try:
            zf = float(zfac)
        except Exception:
            return None
        return zf if np.isfinite(zf) and zf > 0.0 else None

    def component_mw_lbm_per_lbmol(self) -> Optional[np.ndarray]:
        """Return component molecular weights (lbm/lbmol) from backend, cached."""
        if self._mw_components_cache is not None:
            return self._mw_components_cache

        self.configure_backend()
        try:
            with backend.silence_console(self.silence_backend_console):
                mw = backend.component_mw_lbm_per_lbmol(T_F=60.0, P_psia=14.7)
            if mw is None:
                return None
            mw = np.asarray(mw, dtype=float).reshape((len(self.component_ids_dwsim),))
            if not np.all(np.isfinite(mw)) or np.any(mw <= 0.0):
                return None
            self._mw_components_cache = mw
            return mw
        except Exception:
            return None
