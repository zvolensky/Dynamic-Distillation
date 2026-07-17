"""
thermo_clapeyron_provider_v1.py

Dynamic Distillation - Optional Clapeyron.jl Thermo Provider

PURPOSE
-------
Provide a Python-facing thermo provider backed by `pyclapeyron` while matching
the existing runtime-facing provider surface used by the runner and RHS.

CURRENT SCOPE
-------------
This first version keeps the adapter intentionally conservative:
- lazy optional import of `pyclapeyron`
- TP flash via `tp_flash(model, p, T, n)`
- batch TP flash via provider-managed scalar loop
- phase enthalpy / Cp / liquid density helpers
- bubble-point temperature and vapor Z-factor helpers

The implementation is deliberately narrow and defensive so the factory can
select Clapeyron without requiring the rest of the codebase to know anything
about Julia or `pyclapeyron` specifics.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import time
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np


_PA_PER_PSIA = 6894.757293168
_K_PER_F_DELTA = 5.0 / 9.0
_K_OFFSET_FROM_F = 459.67
_J_PER_BTU = 1055.05585262
_MOL_PER_LBMOL = 453.59237
_M3_PER_FT3 = 0.028316846592

_J_PER_MOL_TO_BTU_PER_LBMOL = _MOL_PER_LBMOL / _J_PER_BTU
_J_PER_MOLK_TO_BTU_PER_LBMOLF = _J_PER_MOL_TO_BTU_PER_LBMOL * _K_PER_F_DELTA
_MOL_PER_M3_TO_LBMOL_PER_FT3 = _M3_PER_FT3 / _MOL_PER_LBMOL


@dataclass(frozen=True)
class ClapeyronFlashResult:
    x: np.ndarray
    y: np.ndarray
    K: np.ndarray
    HL_BTU_lbmol: float
    HV_BTU_lbmol: float
    Z: Optional[float] = None
    cpL_BTU_lbmolF: Optional[float] = None
    cpV_BTU_lbmolF: Optional[float] = None
    phase_count: Optional[int] = None


def _f_to_k(T_F: float) -> float:
    return (float(T_F) + _K_OFFSET_FROM_F) * _K_PER_F_DELTA


def _k_to_f(T_K: float) -> float:
    return float(T_K) / _K_PER_F_DELTA - _K_OFFSET_FROM_F


def _psia_to_pa(P_psia: float) -> float:
    return float(P_psia) * _PA_PER_PSIA


def _normalize_comp(z: Sequence[float], n: int) -> np.ndarray:
    arr = np.asarray(z, dtype=float).reshape((-1,))
    if arr.size != int(n):
        raise ValueError(f"Expected composition length {int(n)}, got {arr.size}")
    s = float(np.sum(arr))
    if not np.isfinite(s) or s <= 0.0:
        raise ValueError("Composition vector must have positive finite sum")
    return arr / s


def _reshape_phase_rows(arr: Any, *, n_components: int) -> np.ndarray:
    raw = np.asarray(arr, dtype=float)
    if raw.ndim == 1:
        if raw.size != int(n_components):
            raise ValueError("Single-phase result does not match component count")
        return raw.reshape((1, int(n_components)))
    if raw.ndim != 2:
        raise ValueError("Phase result must be one- or two-dimensional")
    if raw.shape[1] == int(n_components):
        return raw.copy()
    if raw.shape[0] == int(n_components):
        return raw.T.copy()
    raise ValueError("Could not infer phase/component orientation from flash result")


def _phase_totals_from_phase_moles(phase_moles: np.ndarray) -> np.ndarray:
    totals = np.sum(np.asarray(phase_moles, dtype=float), axis=1)
    if totals.ndim != 1:
        totals = np.asarray(totals, dtype=float).reshape((-1,))
    return totals


class ThermoClapeyronProviderV1:
    def __init__(
        self,
        component_names_excel: Sequence[str],
        component_ids_dwsim: Sequence[str],
        *,
        model_name: str = "PR",
        ideal_model_name: Optional[str] = None,
        model_kwargs: Optional[dict[str, Any]] = None,
        flash_cache_size: int = 256,
    ):
        self.component_names_excel = [str(s) for s in component_names_excel]
        self.component_ids_dwsim = [str(s) for s in component_ids_dwsim]
        self.model_name = str(model_name or "PR")
        self.ideal_model_name = None if ideal_model_name in (None, "") else str(ideal_model_name)
        self.model_kwargs = dict(model_kwargs or {})
        try:
            cache_size = int(flash_cache_size)
        except Exception:
            cache_size = 256
        self.flash_cache_size = max(cache_size, 0)
        self.debug_trace_hook = None
        self.debug_trace_context = ""
        # Prefer the shared TP-flash bubble-point path in the runtime helpers.
        # Direct bubble-temperature calls remain available, but the flash-based
        # path has been more stable for long dynamic runs.
        self.prefer_flash_bubble_point_solver = True
        self._thermo_call_category_stack: list[str] = []
        self._thermo_call_counters: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._flash_cache: "OrderedDict[tuple[Any, ...], ClapeyronFlashResult]" = OrderedDict()
        self._liquid_density_cache: "OrderedDict[tuple[Any, ...], Optional[float]]" = OrderedDict()
        self._module = None
        self._model = None
        self._jl_tp_flash2_batch_full_helper = None
        self._jl_tp_flash2_batch_no_cp_helper = None
        # Keep the Julia tp_flash2 batch helper as an experimental seam until
        # its cold-start compile cost is low enough to beat the stable scalar
        # batch path in fresh-process benchmark runs.
        self.enable_julia_tp_flash2_batch_helper = False

    def _load_module(self):
        if self._module is None:
            try:
                self._module = importlib.import_module("pyclapeyron")
            except Exception as exc:
                raise RuntimeError(
                    "thermo_mode='clapeyron' requires the optional 'pyclapeyron' package."
                ) from exc
        return self._module

    def _build_model(self):
        if self._model is not None:
            return self._model
        module = self._load_module()
        ctor = getattr(module, self.model_name, None)
        if not callable(ctor):
            raise RuntimeError(
                f"pyclapeyron does not expose a callable model constructor named {self.model_name!r}"
            )
        kwargs = dict(self.model_kwargs)
        if self.ideal_model_name:
            ideal_ctor = getattr(module, self.ideal_model_name, None)
            if not callable(ideal_ctor):
                raise RuntimeError(
                    f"pyclapeyron does not expose an ideal-model constructor named {self.ideal_model_name!r}"
                )
            kwargs.setdefault("idealmodel", ideal_ctor)
        self._model = ctor(list(self.component_names_excel), **kwargs)
        return self._model

    def validate_backend_available(self) -> None:
        """
        Build the Clapeyron model once so missing optional dependencies or
        invalid model names fail during startup instead of inside RHS fallbacks.
        """
        self._build_model()

    def _get_julia_tp_flash2_batch_helper(self, *, include_cp: bool):
        if not bool(getattr(self, "enable_julia_tp_flash2_batch_helper", False)):
            return None
        helper_attr = "_jl_tp_flash2_batch_full_helper" if include_cp else "_jl_tp_flash2_batch_no_cp_helper"
        helper_cached = getattr(self, helper_attr, None)
        if helper_cached is not None:
            return helper_cached

        module = self._load_module()
        jl = getattr(module, "jl", None)
        if jl is None or not callable(getattr(jl, "seval", None)):
            return None

        if include_cp:
            helper_expr = r'''
function ddii_tp_flash2_batch_full(model, P_vec, T_vec, Z_mat)
    nrows = length(T_vec)
    nc = size(Z_mat, 2)
    xs = Matrix{Float64}(undef, nrows, nc)
    ys = Matrix{Float64}(undef, nrows, nc)
    Ks = Matrix{Float64}(undef, nrows, nc)
    HLs = Vector{Float64}(undef, nrows)
    HVs = Vector{Float64}(undef, nrows)
    Zs = Vector{Float64}(undef, nrows)
    cpLs = Vector{Float64}(undef, nrows)
    cpVs = Vector{Float64}(undef, nrows)
    for i in 1:nrows
        z = vec(Z_mat[i, :])
        st = Clapeyron.tp_flash2(model, P_vec[i], T_vec[i], z)
        comps = st.compositions
        nph = length(comps)
        if nph == 1
            liq_i = 1
            vap_i = 1
            x = vec(comps[1])
            y = vec(comps[1])
        else
            zfacs = [Clapeyron.compressibility_factor(model, st, j) for j in 1:nph]
            vap_i = argmax(zfacs)
            liq_i = argmin(zfacs)
            x = vec(comps[liq_i])
            y = vec(comps[vap_i])
        end
        x ./= sum(x)
        y ./= sum(y)
        xs[i, :] .= x
        ys[i, :] .= y
        Ks[i, :] .= y ./ x
        HLs[i] = Clapeyron.enthalpy(model, st, liq_i)
        HVs[i] = Clapeyron.enthalpy(model, st, vap_i)
        Zs[i] = Clapeyron.compressibility_factor(model, st, vap_i)
        cpLs[i] = Clapeyron.isobaric_heat_capacity(model, st, liq_i)
        cpVs[i] = Clapeyron.isobaric_heat_capacity(model, st, vap_i)
    end
    return xs, ys, Ks, HLs, HVs, Zs, cpLs, cpVs
end
ddii_tp_flash2_batch_full
'''
        else:
            helper_expr = r'''
function ddii_tp_flash2_batch_no_cp(model, P_vec, T_vec, Z_mat)
    nrows = length(T_vec)
    nc = size(Z_mat, 2)
    xs = Matrix{Float64}(undef, nrows, nc)
    ys = Matrix{Float64}(undef, nrows, nc)
    Ks = Matrix{Float64}(undef, nrows, nc)
    HLs = Vector{Float64}(undef, nrows)
    HVs = Vector{Float64}(undef, nrows)
    Zs = Vector{Float64}(undef, nrows)
    for i in 1:nrows
        z = vec(Z_mat[i, :])
        st = Clapeyron.tp_flash2(model, P_vec[i], T_vec[i], z)
        comps = st.compositions
        nph = length(comps)
        if nph == 1
            liq_i = 1
            vap_i = 1
            x = vec(comps[1])
            y = vec(comps[1])
        else
            zfacs = [Clapeyron.compressibility_factor(model, st, j) for j in 1:nph]
            vap_i = argmax(zfacs)
            liq_i = argmin(zfacs)
            x = vec(comps[liq_i])
            y = vec(comps[vap_i])
        end
        x ./= sum(x)
        y ./= sum(y)
        xs[i, :] .= x
        ys[i, :] .= y
        Ks[i, :] .= y ./ x
        HLs[i] = Clapeyron.enthalpy(model, st, liq_i)
        HVs[i] = Clapeyron.enthalpy(model, st, vap_i)
        Zs[i] = Clapeyron.compressibility_factor(model, st, vap_i)
    end
    return xs, ys, Ks, HLs, HVs, Zs
end
ddii_tp_flash2_batch_no_cp
'''
        try:
            helper = jl.seval(helper_expr)
        except Exception:
            helper = None
        setattr(self, helper_attr, helper)
        return helper

    def set_debug_trace_context(self, context: Optional[str]) -> None:
        self.debug_trace_context = str(context or "")

    def reset_call_counters(self) -> None:
        self._thermo_call_counters = defaultdict(dict)
        self._thermo_call_category_stack = []
        self._flash_cache.clear()
        self._liquid_density_cache.clear()

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
        if amt == 0.0:
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
        self._thermo_call_category_stack.append(cat)
        try:
            yield
        finally:
            if self._thermo_call_category_stack:
                self._thermo_call_category_stack.pop()

    def _call_module_fn(self, fn_name: str, *args, **kwargs):
        module = self._load_module()
        fn = getattr(module, fn_name, None)
        if not callable(fn):
            raise RuntimeError(f"pyclapeyron does not expose callable {fn_name!r}")
        return fn(*args, **kwargs)

    def _call_property_with_phase(self, fn_name: str, *, phase_name: str, comp: np.ndarray, p_pa: float, T_K: float):
        attempts = (
            {"phase": str(phase_name)},
            {"phase": str(phase_name).lower()},
            {"phase": "vapour" if str(phase_name).lower() == "vapor" else str(phase_name).lower()},
            {},
        )
        last_exc = None
        for extra_kwargs in attempts:
            try:
                return self._call_module_fn(fn_name, self._build_model(), p_pa, T_K, comp, **extra_kwargs)
            except TypeError as exc:
                last_exc = exc
                continue
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Could not evaluate {fn_name!r} for phase {phase_name!r}")

    def _phase_z_factor(self, comp: np.ndarray, *, phase_name: str, p_pa: float, T_K: float) -> Optional[float]:
        try:
            zfac = self._call_property_with_phase(
                "compressibility_factor",
                phase_name=phase_name,
                comp=comp,
                p_pa=p_pa,
                T_K=T_K,
            )
        except Exception:
            return None
        try:
            val = float(zfac)
        except Exception:
            return None
        return val if np.isfinite(val) and val > 0.0 else None

    def _copy_flash_result(self, fres: ClapeyronFlashResult) -> ClapeyronFlashResult:
        return ClapeyronFlashResult(
            x=np.asarray(fres.x, dtype=float).reshape((-1,)).copy(),
            y=np.asarray(fres.y, dtype=float).reshape((-1,)).copy(),
            K=np.asarray(fres.K, dtype=float).reshape((-1,)).copy(),
            HL_BTU_lbmol=float(fres.HL_BTU_lbmol),
            HV_BTU_lbmol=float(fres.HV_BTU_lbmol),
            Z=(None if fres.Z is None else float(fres.Z)),
            cpL_BTU_lbmolF=(None if fres.cpL_BTU_lbmolF is None else float(fres.cpL_BTU_lbmolF)),
            cpV_BTU_lbmolF=(None if fres.cpV_BTU_lbmolF is None else float(fres.cpV_BTU_lbmolF)),
            phase_count=fres.phase_count,
        )

    def _flash_cache_key(self, *, T_F: float, P_psia: float, z_norm: np.ndarray) -> tuple[Any, ...]:
        return (
            float(T_F),
            float(P_psia),
            tuple(float(v) for v in np.asarray(z_norm, dtype=float).reshape((-1,))),
        )

    def _get_cached_flash_result(self, key: tuple[Any, ...]) -> Optional[ClapeyronFlashResult]:
        if self.flash_cache_size <= 0:
            return None
        fres = self._flash_cache.get(key)
        if fres is None:
            return None
        self._flash_cache.move_to_end(key)
        self._record_call_counter("flash_cache_hits", 1)
        return self._copy_flash_result(fres)

    def _store_cached_flash_result(self, key: tuple[Any, ...], fres: ClapeyronFlashResult) -> None:
        if self.flash_cache_size <= 0:
            return
        self._flash_cache[key] = self._copy_flash_result(fres)
        self._flash_cache.move_to_end(key)
        while len(self._flash_cache) > self.flash_cache_size:
            self._flash_cache.popitem(last=False)

    def flash_cached_phase_count_F_psia(self, T_F: float, P_psia: float, z: Sequence[float]) -> Optional[float]:
        z_norm = _normalize_comp(z, len(self.component_names_excel))
        cache_key = self._flash_cache_key(T_F=float(T_F), P_psia=float(P_psia), z_norm=z_norm)
        cached = self._get_cached_flash_result(cache_key)
        if cached is None or cached.phase_count is None:
            return None
        try:
            return float(cached.phase_count)
        except Exception:
            return None
            self._record_call_counter("flash_cache_evictions", 1)

    def _get_cached_liquid_density(self, key: tuple[Any, ...]) -> Tuple[bool, Optional[float]]:
        if self.flash_cache_size <= 0:
            return False, None
        if key not in self._liquid_density_cache:
            return False, None
        rho = self._liquid_density_cache[key]
        self._liquid_density_cache.move_to_end(key)
        self._record_call_counter("liquid_density_cache_hits", 1)
        if rho is None:
            return True, None
        return True, float(rho)

    def _store_cached_liquid_density(self, key: tuple[Any, ...], rho: Optional[float]) -> None:
        if self.flash_cache_size <= 0:
            return
        self._liquid_density_cache[key] = (None if rho is None else float(rho))
        self._liquid_density_cache.move_to_end(key)
        while len(self._liquid_density_cache) > self.flash_cache_size:
            self._liquid_density_cache.popitem(last=False)
            self._record_call_counter("liquid_density_cache_evictions", 1)

    def _phase_enthalpy_btu_lbmol(self, comp: np.ndarray, *, phase_name: str, p_pa: float, T_K: float) -> float:
        h = self._call_property_with_phase(
            "enthalpy",
            phase_name=phase_name,
            comp=comp,
            p_pa=p_pa,
            T_K=T_K,
        )
        return float(h) * _J_PER_MOL_TO_BTU_PER_LBMOL

    def _phase_cp_btu_lbmolF(self, comp: np.ndarray, *, phase_name: str, p_pa: float, T_K: float) -> Optional[float]:
        try:
            cp = self._call_property_with_phase(
                "isobaric_heat_capacity",
                phase_name=phase_name,
                comp=comp,
                p_pa=p_pa,
                T_K=T_K,
            )
        except Exception:
            return None
        try:
            cp_f = float(cp) * _J_PER_MOLK_TO_BTU_PER_LBMOLF
        except Exception:
            return None
        return cp_f if np.isfinite(cp_f) else None

    def _phase_volume_m3_per_mol(self, comp: np.ndarray, *, phase_name: str, p_pa: float, T_K: float) -> Optional[float]:
        try:
            V = self._call_property_with_phase(
                "volume",
                phase_name=phase_name,
                comp=comp,
                p_pa=p_pa,
                T_K=T_K,
            )
        except Exception:
            return None
        try:
            V_f = float(V)
        except Exception:
            return None
        return V_f if np.isfinite(V_f) and V_f > 0.0 else None

    def _split_flash_phases(
        self,
        phase_compositions: np.ndarray,
        phase_moles: np.ndarray,
        *,
        p_pa: float,
        T_K: float,
    ) -> Tuple[np.ndarray, np.ndarray, Optional[float], int]:
        phase_compositions = np.asarray(phase_compositions, dtype=float)
        phase_moles = np.asarray(phase_moles, dtype=float)
        if phase_compositions.shape != phase_moles.shape:
            raise ValueError("Flash phase compositions and phase moles must have matching shapes")

        totals = _phase_totals_from_phase_moles(phase_moles)
        total_scale = max(1.0, float(np.sum(np.abs(totals))))
        active_tol = np.finfo(float).eps * total_scale
        active = np.flatnonzero(np.isfinite(totals) & (totals > active_tol))
        if active.size == 0:
            raise RuntimeError("Clapeyron TP flash returned no active phase")
        if active.size == 1:
            z = _normalize_comp(phase_compositions[int(active[0]), :], phase_compositions.shape[1])
            zfac = self._phase_z_factor(z, phase_name="vapor", p_pa=p_pa, T_K=T_K)
            return z.copy(), z.copy(), zfac, 1

        zfacs = []
        for i in active:
            zf = self._phase_z_factor(
                _normalize_comp(phase_compositions[i, :], phase_compositions.shape[1]),
                phase_name="vapor",
                p_pa=p_pa,
                T_K=T_K,
            )
            zfacs.append(np.nan if zf is None else float(zf))
        z_arr = np.asarray(zfacs, dtype=float)
        if np.all(np.isfinite(z_arr)):
            vap_pos = int(np.argmax(z_arr))
            liq_pos = int(np.argmin(z_arr))
        else:
            active_totals = totals[active]
            vap_pos = int(np.argmax(active_totals))
            liq_pos = int(np.argmin(active_totals))
        vap_i = int(active[vap_pos])
        liq_i = int(active[liq_pos])
        x = _normalize_comp(phase_compositions[liq_i, :], phase_compositions.shape[1])
        y = _normalize_comp(phase_compositions[vap_i, :], phase_compositions.shape[1])
        zfac = z_arr[vap_pos] if 0 <= vap_pos < z_arr.size and np.isfinite(z_arr[vap_pos]) else None
        return x, y, (None if zfac is None else float(zfac)), int(active.size)

    @staticmethod
    def _require_exposed_equilibrium_pair(phase_count: int) -> None:
        if int(phase_count) < 2:
            raise RuntimeError(
                "Clapeyron TP flash returned one active phase and did not expose the "
                "incipient-phase K-values required by the dynamic model"
            )

    def _enrich_flash_result_with_cp(
        self,
        fres: ClapeyronFlashResult,
        *,
        p_pa: float,
        T_K: float,
    ) -> ClapeyronFlashResult:
        if fres.cpL_BTU_lbmolF is not None and fres.cpV_BTU_lbmolF is not None:
            return self._copy_flash_result(fres)

        self._record_call_counter("cp_requests", 1)
        t0 = time.perf_counter()
        cpL = self._phase_cp_btu_lbmolF(
            np.asarray(fres.x, dtype=float).reshape((-1,)),
            phase_name="liquid",
            p_pa=p_pa,
            T_K=T_K,
        )
        cpV = self._phase_cp_btu_lbmolF(
            np.asarray(fres.y, dtype=float).reshape((-1,)),
            phase_name="vapor",
            p_pa=p_pa,
            T_K=T_K,
        )
        self._record_call_counter("cp_wall_sec", float(time.perf_counter() - t0))
        return ClapeyronFlashResult(
            x=np.asarray(fres.x, dtype=float).reshape((-1,)).copy(),
            y=np.asarray(fres.y, dtype=float).reshape((-1,)).copy(),
            K=np.asarray(fres.K, dtype=float).reshape((-1,)).copy(),
            HL_BTU_lbmol=float(fres.HL_BTU_lbmol),
            HV_BTU_lbmol=float(fres.HV_BTU_lbmol),
            Z=(None if fres.Z is None else float(fres.Z)),
            cpL_BTU_lbmolF=cpL,
            cpV_BTU_lbmolF=cpV,
            phase_count=fres.phase_count,
        )

    def _flash_impl(
        self,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
        *,
        include_cp: bool = True,
    ) -> ClapeyronFlashResult:
        z_norm = _normalize_comp(z, len(self.component_names_excel))
        cache_key = self._flash_cache_key(T_F=float(T_F), P_psia=float(P_psia), z_norm=z_norm)
        cached = self._get_cached_flash_result(cache_key)
        if cached is not None:
            if not include_cp:
                return cached
            enriched = self._enrich_flash_result_with_cp(
                cached,
                p_pa=_psia_to_pa(float(P_psia)),
                T_K=_f_to_k(float(T_F)),
            )
            self._store_cached_flash_result(cache_key, enriched)
            return self._copy_flash_result(enriched)

        self._record_call_counter("flash_cache_misses", 1)
        model = self._build_model()
        T_K = _f_to_k(float(T_F))
        p_pa = _psia_to_pa(float(P_psia))
        n_vec = np.asarray(z_norm, dtype=float)

        self._record_call_counter("flash_requests", 1)
        self._record_call_counter("backend_flash_equivalents", 1)
        t0 = time.perf_counter()
        flash_out = self._call_module_fn("tp_flash", model, p_pa, T_K, n_vec)
        self._record_call_counter("wall_sec", float(time.perf_counter() - t0))

        if hasattr(flash_out, "compositions") and hasattr(flash_out, "fractions"):
            phase_compositions = _reshape_phase_rows(flash_out.compositions, n_components=z_norm.size)
            fractions = np.asarray(flash_out.fractions, dtype=float).reshape((-1, 1))
            phase_moles = phase_compositions * fractions
        elif isinstance(flash_out, (tuple, list)) and len(flash_out) >= 2:
            phase_compositions = _reshape_phase_rows(flash_out[0], n_components=z_norm.size)
            phase_moles = _reshape_phase_rows(flash_out[1], n_components=z_norm.size)
        else:
            raise RuntimeError("pyclapeyron tp_flash did not return a recognized flash result")

        x, y, zfac, phase_count = self._split_flash_phases(
            phase_compositions,
            phase_moles,
            p_pa=p_pa,
            T_K=T_K,
        )
        self._require_exposed_equilibrium_pair(phase_count)
        K = np.divide(y, np.maximum(x, 1.0e-300))
        HL = self._phase_enthalpy_btu_lbmol(x, phase_name="liquid", p_pa=p_pa, T_K=T_K)
        HV = self._phase_enthalpy_btu_lbmol(y, phase_name="vapor", p_pa=p_pa, T_K=T_K)
        fres = ClapeyronFlashResult(
            x=x,
            y=y,
            K=K,
            HL_BTU_lbmol=float(HL),
            HV_BTU_lbmol=float(HV),
            Z=(float(zfac) if zfac is not None else None),
            cpL_BTU_lbmolF=None,
            cpV_BTU_lbmolF=None,
            phase_count=int(phase_count),
        )
        if include_cp:
            fres = self._enrich_flash_result_with_cp(fres, p_pa=p_pa, T_K=T_K)
        self._store_cached_flash_result(cache_key, fres)
        return self._copy_flash_result(fres)

    def _flash_equilibrium_impl(
        self,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, Optional[float]]:
        z_norm = _normalize_comp(z, len(self.component_names_excel))
        cache_key = self._flash_cache_key(T_F=float(T_F), P_psia=float(P_psia), z_norm=z_norm)
        cached = self._get_cached_flash_result(cache_key)
        if cached is not None:
            return (
                np.asarray(cached.x, dtype=float).reshape((-1,)).copy(),
                np.asarray(cached.y, dtype=float).reshape((-1,)).copy(),
                np.asarray(cached.K, dtype=float).reshape((-1,)).copy(),
                (None if cached.Z is None else float(cached.Z)),
            )
        self._record_call_counter("flash_cache_misses", 1)
        model = self._build_model()
        T_K = _f_to_k(float(T_F))
        p_pa = _psia_to_pa(float(P_psia))
        n_vec = np.asarray(z_norm, dtype=float)

        self._record_call_counter("flash_requests", 1)
        self._record_call_counter("backend_flash_equivalents", 1)
        self._record_call_counter("equilibrium_only_flash_requests", 1)
        t0 = time.perf_counter()
        flash_out = self._call_module_fn("tp_flash", model, p_pa, T_K, n_vec)

        if hasattr(flash_out, "compositions") and hasattr(flash_out, "fractions"):
            phase_compositions = _reshape_phase_rows(flash_out.compositions, n_components=z_norm.size)
            fractions = np.asarray(flash_out.fractions, dtype=float).reshape((-1, 1))
            phase_moles = phase_compositions * fractions
        elif isinstance(flash_out, (tuple, list)) and len(flash_out) >= 2:
            phase_compositions = _reshape_phase_rows(flash_out[0], n_components=z_norm.size)
            phase_moles = _reshape_phase_rows(flash_out[1], n_components=z_norm.size)
        else:
            raise RuntimeError("pyclapeyron tp_flash did not return a recognized flash result")

        x, y, zfac, phase_count = self._split_flash_phases(
            phase_compositions,
            phase_moles,
            p_pa=p_pa,
            T_K=T_K,
        )
        self._require_exposed_equilibrium_pair(phase_count)
        K = np.divide(y, np.maximum(x, 1.0e-300))
        self._record_call_counter("wall_sec", float(time.perf_counter() - t0))
        return (
            np.asarray(x, dtype=float).reshape((-1,)).copy(),
            np.asarray(y, dtype=float).reshape((-1,)).copy(),
            np.asarray(K, dtype=float).reshape((-1,)).copy(),
            (None if zfac is None else float(zfac)),
        )

    def flash_TP_full_F_psia(self, T_F: float, P_psia: float, z: Sequence[float]):
        fres = self._flash_impl(float(T_F), float(P_psia), z, include_cp=True)
        return (
            fres.x.copy(),
            fres.y.copy(),
            fres.K.copy(),
            float(fres.HL_BTU_lbmol),
            float(fres.HV_BTU_lbmol),
            (None if fres.Z is None else float(fres.Z)),
        )

    def flash_TP_full_stage_F_psia(
        self,
        stage_index0: int,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
    ):
        _ = int(stage_index0)
        return self.flash_TP_full_F_psia(float(T_F), float(P_psia), z)

    def flash_TP_full_F_psia_no_cp(self, T_F: float, P_psia: float, z: Sequence[float]):
        fres = self._flash_impl(float(T_F), float(P_psia), z, include_cp=False)
        return (
            fres.x.copy(),
            fres.y.copy(),
            fres.K.copy(),
            float(fres.HL_BTU_lbmol),
            float(fres.HV_BTU_lbmol),
            (None if fres.Z is None else float(fres.Z)),
        )

    def flash_TP_full_stage_F_psia_no_cp(
        self,
        stage_index0: int,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
    ):
        _ = int(stage_index0)
        return self.flash_TP_full_F_psia_no_cp(float(T_F), float(P_psia), z)

    def flash_TP_full(self, T_F: float, P_psia: float, z: Sequence[float]) -> ClapeyronFlashResult:
        return self._flash_impl(float(T_F), float(P_psia), z, include_cp=True)

    def flash_TP_equilibrium_F_psia(
        self,
        T_F: float,
        P_psia: float,
        z: Sequence[float],
    ):
        return self._flash_equilibrium_impl(float(T_F), float(P_psia), z)

    def flash_TP_equilibrium_batch_F_psia(
        self,
        T_rows_F: Sequence[float],
        P_rows_psia: Sequence[float],
        z_rows: Sequence[Sequence[float]],
    ):
        T_list = [float(v) for v in T_rows_F]
        P_list = [float(v) for v in P_rows_psia]
        z_list = [list(row) for row in z_rows]
        if not (len(T_list) == len(P_list) == len(z_list)):
            raise ValueError("flash_TP_equilibrium_batch_F_psia requires equal-length T, P, and z row collections")

        self._record_call_counter("batch_flash_requests", 1)
        self._record_call_counter("batch_flash_rows", len(T_list))
        self._record_call_counter("equilibrium_only_batch_flash_requests", 1)
        out = []
        for T_F, P_psia, z in zip(T_list, P_list, z_list):
            out.append(self._flash_equilibrium_impl(float(T_F), float(P_psia), z))
        return out

    def flash_TP_full_batch(
        self,
        T_rows_F: Sequence[float],
        P_rows_psia: Sequence[float],
        z_rows: Sequence[Sequence[float]],
    ):
        T_list = [float(v) for v in T_rows_F]
        P_list = [float(v) for v in P_rows_psia]
        z_list = [list(row) for row in z_rows]
        if not (len(T_list) == len(P_list) == len(z_list)):
            raise ValueError("flash_TP_full_batch requires equal-length T, P, and z row collections")

        self._record_call_counter("batch_flash_requests", 1)
        self._record_call_counter("batch_flash_rows", len(T_list))
        out = [None] * len(T_list)
        enrich_indices: list[int] = []
        enrich_keys: list[tuple[Any, ...]] = []
        enrich_T_F: list[float] = []
        enrich_P_psia: list[float] = []
        enrich_cached: list[ClapeyronFlashResult] = []
        miss_indices: list[int] = []
        miss_keys: list[tuple[Any, ...]] = []
        miss_T_F: list[float] = []
        miss_P_psia: list[float] = []
        miss_z_norm: list[np.ndarray] = []

        for idx, (T_F, P_psia, z) in enumerate(zip(T_list, P_list, z_list)):
            z_norm = _normalize_comp(z, len(self.component_names_excel))
            cache_key = self._flash_cache_key(T_F=float(T_F), P_psia=float(P_psia), z_norm=z_norm)
            cached = self._get_cached_flash_result(cache_key)
            if cached is not None and cached.cpL_BTU_lbmolF is not None and cached.cpV_BTU_lbmolF is not None:
                out[idx] = (
                    cached.x.copy(),
                    cached.y.copy(),
                    cached.K.copy(),
                    float(cached.HL_BTU_lbmol),
                    float(cached.HV_BTU_lbmol),
                    (None if cached.Z is None else float(cached.Z)),
                    float(cached.cpL_BTU_lbmolF),
                    float(cached.cpV_BTU_lbmolF),
                )
                continue
            if cached is not None:
                enrich_indices.append(idx)
                enrich_keys.append(cache_key)
                enrich_T_F.append(float(T_F))
                enrich_P_psia.append(float(P_psia))
                enrich_cached.append(cached)
                continue
            miss_indices.append(idx)
            miss_keys.append(cache_key)
            miss_T_F.append(float(T_F))
            miss_P_psia.append(float(P_psia))
            miss_z_norm.append(np.asarray(z_norm, dtype=float).reshape((-1,)).copy())

        for idx, cache_key, T_F, P_psia, cached in zip(
            enrich_indices,
            enrich_keys,
            enrich_T_F,
            enrich_P_psia,
            enrich_cached,
        ):
            enriched = self._enrich_flash_result_with_cp(
                cached,
                p_pa=_psia_to_pa(float(P_psia)),
                T_K=_f_to_k(float(T_F)),
            )
            self._store_cached_flash_result(cache_key, enriched)
            out[idx] = (
                enriched.x.copy(),
                enriched.y.copy(),
                enriched.K.copy(),
                float(enriched.HL_BTU_lbmol),
                float(enriched.HV_BTU_lbmol),
                (None if enriched.Z is None else float(enriched.Z)),
                float(enriched.cpL_BTU_lbmolF),
                float(enriched.cpV_BTU_lbmolF),
            )

        helper = self._get_julia_tp_flash2_batch_helper(include_cp=True)
        helper_ok = False
        if helper is not None and miss_indices:
            try:
                self._record_call_counter("flash_cache_misses", len(miss_indices))
                self._record_call_counter("flash_requests", len(miss_indices))
                self._record_call_counter("backend_flash_equivalents", len(miss_indices))
                t0 = time.perf_counter()
                xs, ys, Ks, HLs, HVs, Zs, cpLs, cpVs = helper(
                    self._build_model(),
                    np.asarray([_psia_to_pa(v) for v in miss_P_psia], dtype=float),
                    np.asarray([_f_to_k(v) for v in miss_T_F], dtype=float),
                    np.asarray(miss_z_norm, dtype=float),
                )
                self._record_call_counter("wall_sec", float(time.perf_counter() - t0))
                xs = np.asarray(xs, dtype=float)
                ys = np.asarray(ys, dtype=float)
                Ks = np.asarray(Ks, dtype=float)
                HLs = np.asarray(HLs, dtype=float)
                HVs = np.asarray(HVs, dtype=float)
                Zs = np.asarray(Zs, dtype=float)
                cpLs = np.asarray(cpLs, dtype=float)
                cpVs = np.asarray(cpVs, dtype=float)
                for pos, idx in enumerate(miss_indices):
                    fres = ClapeyronFlashResult(
                        x=np.asarray(xs[pos, :], dtype=float).reshape((-1,)).copy(),
                        y=np.asarray(ys[pos, :], dtype=float).reshape((-1,)).copy(),
                        K=np.asarray(Ks[pos, :], dtype=float).reshape((-1,)).copy(),
                        HL_BTU_lbmol=float(HLs[pos]) * _J_PER_MOL_TO_BTU_PER_LBMOL,
                        HV_BTU_lbmol=float(HVs[pos]) * _J_PER_MOL_TO_BTU_PER_LBMOL,
                        Z=float(Zs[pos]),
                        cpL_BTU_lbmolF=float(cpLs[pos]) * _J_PER_MOLK_TO_BTU_PER_LBMOLF,
                        cpV_BTU_lbmolF=float(cpVs[pos]) * _J_PER_MOLK_TO_BTU_PER_LBMOLF,
                        phase_count=None,
                    )
                    self._store_cached_flash_result(miss_keys[pos], fres)
                    out[idx] = (
                        fres.x.copy(),
                        fres.y.copy(),
                        fres.K.copy(),
                        float(fres.HL_BTU_lbmol),
                        float(fres.HV_BTU_lbmol),
                        (None if fres.Z is None else float(fres.Z)),
                        float(fres.cpL_BTU_lbmolF),
                        float(fres.cpV_BTU_lbmolF),
                    )
                helper_ok = True
            except Exception:
                helper_ok = False

        if miss_indices and not helper_ok:
            for idx, T_F, P_psia, z in zip(miss_indices, miss_T_F, miss_P_psia, miss_z_norm):
                fres = self._flash_impl(float(T_F), float(P_psia), z, include_cp=True)
                out[idx] = (
                    fres.x.copy(),
                    fres.y.copy(),
                    fres.K.copy(),
                    float(fres.HL_BTU_lbmol),
                    float(fres.HV_BTU_lbmol),
                    (None if fres.Z is None else float(fres.Z)),
                    float(fres.cpL_BTU_lbmolF),
                    float(fres.cpV_BTU_lbmolF),
                )
        return out

    def flash_TP_full_batch_no_cp(
        self,
        T_rows_F: Sequence[float],
        P_rows_psia: Sequence[float],
        z_rows: Sequence[Sequence[float]],
    ):
        T_list = [float(v) for v in T_rows_F]
        P_list = [float(v) for v in P_rows_psia]
        z_list = [list(row) for row in z_rows]
        if not (len(T_list) == len(P_list) == len(z_list)):
            raise ValueError("flash_TP_full_batch_no_cp requires equal-length T, P, and z row collections")

        self._record_call_counter("batch_flash_requests", 1)
        self._record_call_counter("batch_flash_rows", len(T_list))
        out = [None] * len(T_list)
        miss_indices: list[int] = []
        miss_keys: list[tuple[Any, ...]] = []
        miss_T_F: list[float] = []
        miss_P_psia: list[float] = []
        miss_z_norm: list[np.ndarray] = []

        for idx, (T_F, P_psia, z) in enumerate(zip(T_list, P_list, z_list)):
            z_norm = _normalize_comp(z, len(self.component_names_excel))
            cache_key = self._flash_cache_key(T_F=float(T_F), P_psia=float(P_psia), z_norm=z_norm)
            cached = self._get_cached_flash_result(cache_key)
            if cached is not None:
                out[idx] = (
                    cached.x.copy(),
                    cached.y.copy(),
                    cached.K.copy(),
                    float(cached.HL_BTU_lbmol),
                    float(cached.HV_BTU_lbmol),
                    (None if cached.Z is None else float(cached.Z)),
                )
                continue
            miss_indices.append(idx)
            miss_keys.append(cache_key)
            miss_T_F.append(float(T_F))
            miss_P_psia.append(float(P_psia))
            miss_z_norm.append(np.asarray(z_norm, dtype=float).reshape((-1,)).copy())

        helper = self._get_julia_tp_flash2_batch_helper(include_cp=False)
        helper_ok = False
        if helper is not None and miss_indices:
            try:
                self._record_call_counter("flash_cache_misses", len(miss_indices))
                self._record_call_counter("flash_requests", len(miss_indices))
                self._record_call_counter("backend_flash_equivalents", len(miss_indices))
                t0 = time.perf_counter()
                xs, ys, Ks, HLs, HVs, Zs = helper(
                    self._build_model(),
                    np.asarray([_psia_to_pa(v) for v in miss_P_psia], dtype=float),
                    np.asarray([_f_to_k(v) for v in miss_T_F], dtype=float),
                    np.asarray(miss_z_norm, dtype=float),
                )
                self._record_call_counter("wall_sec", float(time.perf_counter() - t0))
                xs = np.asarray(xs, dtype=float)
                ys = np.asarray(ys, dtype=float)
                Ks = np.asarray(Ks, dtype=float)
                HLs = np.asarray(HLs, dtype=float)
                HVs = np.asarray(HVs, dtype=float)
                Zs = np.asarray(Zs, dtype=float)
                for pos, idx in enumerate(miss_indices):
                    fres = ClapeyronFlashResult(
                        x=np.asarray(xs[pos, :], dtype=float).reshape((-1,)).copy(),
                        y=np.asarray(ys[pos, :], dtype=float).reshape((-1,)).copy(),
                        K=np.asarray(Ks[pos, :], dtype=float).reshape((-1,)).copy(),
                        HL_BTU_lbmol=float(HLs[pos]) * _J_PER_MOL_TO_BTU_PER_LBMOL,
                        HV_BTU_lbmol=float(HVs[pos]) * _J_PER_MOL_TO_BTU_PER_LBMOL,
                        Z=float(Zs[pos]),
                        cpL_BTU_lbmolF=None,
                        cpV_BTU_lbmolF=None,
                    )
                    self._store_cached_flash_result(miss_keys[pos], fres)
                    out[idx] = (
                        fres.x.copy(),
                        fres.y.copy(),
                        fres.K.copy(),
                        float(fres.HL_BTU_lbmol),
                        float(fres.HV_BTU_lbmol),
                        (None if fres.Z is None else float(fres.Z)),
                    )
                helper_ok = True
            except Exception:
                helper_ok = False

        if miss_indices and not helper_ok:
            for idx, T_F, P_psia, z in zip(miss_indices, miss_T_F, miss_P_psia, miss_z_norm):
                fres = self._flash_impl(float(T_F), float(P_psia), z, include_cp=False)
                out[idx] = (
                    fres.x.copy(),
                    fres.y.copy(),
                    fres.K.copy(),
                    float(fres.HL_BTU_lbmol),
                    float(fres.HV_BTU_lbmol),
                    (None if fres.Z is None else float(fres.Z)),
                )
        return out

    def warm_startup_kernels(
        self,
        *,
        density_state: Optional[tuple[float, float, Sequence[float]]] = None,
        flash_rows: Optional[Sequence[tuple[float, float, Sequence[float]]]] = None,
    ) -> Dict[str, float | int | bool]:
        density_ready = False
        flash_ready = False
        flash_row_count = 0

        if density_state is not None:
            T_F, P_psia, x = density_state
            _ = self.liquid_density_lbmol_ft3(float(T_F), float(P_psia), x)
            density_ready = True

        if flash_rows:
            T_rows = []
            P_rows = []
            z_rows = []
            for T_F, P_psia, z in flash_rows:
                T_rows.append(float(T_F))
                P_rows.append(float(P_psia))
                z_rows.append(list(z))
            if T_rows:
                _ = self.flash_TP_full_batch_no_cp(T_rows, P_rows, z_rows)
                flash_ready = True
                flash_row_count = len(T_rows)

        return {
            "density_ready": bool(density_ready),
            "flash_ready": bool(flash_ready),
            "flash_rows": int(flash_row_count),
        }

    def cp_liq_vap_btu_per_lbmolF(self, T_F: float, P_psia: float, z: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
        fres = self._flash_impl(float(T_F), float(P_psia), z, include_cp=True)
        return fres.cpL_BTU_lbmolF, fres.cpV_BTU_lbmolF

    def liquid_density_lbmol_ft3(self, T_F: float, P_psia: float, x: Sequence[float]) -> Optional[float]:
        x_norm = _normalize_comp(x, len(self.component_names_excel))
        cache_key = self._flash_cache_key(T_F=float(T_F), P_psia=float(P_psia), z_norm=x_norm)
        cache_hit, rho_cached = self._get_cached_liquid_density(cache_key)
        if cache_hit:
            return rho_cached
        self._record_call_counter("liquid_density_cache_misses", 1)
        T_K = _f_to_k(float(T_F))
        p_pa = _psia_to_pa(float(P_psia))
        self._record_call_counter("liquid_density_requests", 1)
        t0 = time.perf_counter()
        V = self._phase_volume_m3_per_mol(x_norm, phase_name="liquid", p_pa=p_pa, T_K=T_K)
        self._record_call_counter("liquid_density_wall_sec", float(time.perf_counter() - t0))
        if V is None or not np.isfinite(float(V)) or float(V) <= 0.0:
            self._store_cached_liquid_density(cache_key, None)
            return None
        rho = (1.0 / float(V)) * _MOL_PER_M3_TO_LBMOL_PER_FT3
        rho_out = float(rho) if np.isfinite(rho) and rho > 0.0 else None
        self._store_cached_liquid_density(cache_key, rho_out)
        return rho_out

    def phase_enthalpy_BTU_lbmol(
        self,
        phase: str,
        T_F: float,
        P_psia: float,
        comp: Sequence[float],
    ) -> float:
        comp_norm = _normalize_comp(comp, len(self.component_names_excel))
        return self._phase_enthalpy_btu_lbmol(
            comp_norm,
            phase_name=str(phase or "unknown"),
            p_pa=_psia_to_pa(float(P_psia)),
            T_K=_f_to_k(float(T_F)),
        )

    def vapor_z_factor_F_psia(
        self,
        T_F: float,
        P_psia: float,
        y: Sequence[float],
    ) -> Optional[float]:
        y_norm = _normalize_comp(y, len(self.component_names_excel))
        return self._phase_z_factor(
            y_norm,
            phase_name="vapor",
            p_pa=_psia_to_pa(float(P_psia)),
            T_K=_f_to_k(float(T_F)),
        )

    def bubble_point_temperature_F_psia(
        self,
        P_psia: float,
        x: Sequence[float],
    ) -> Optional[float]:
        x_norm = _normalize_comp(x, len(self.component_names_excel))
        try:
            out = self._call_module_fn("bubble_temperature", self._build_model(), _psia_to_pa(float(P_psia)), x_norm)
        except Exception:
            return None
        if isinstance(out, (tuple, list)) and len(out) >= 1:
            T_K = out[0]
        else:
            T_K = out
        try:
            return _k_to_f(float(T_K))
        except Exception:
            return None
