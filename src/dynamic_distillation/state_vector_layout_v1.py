# src/dynamic_distillation/state_vector_layout_v1.py
"""
state_vector_layout_v1.py

Created: 2026-01-11  (America/New_York)
Updated: 2026-01-13  (America/New_York)

Purpose
-------
Canonical packing/unpacking for the ODE state vector y.

Supports:
- Tray liquid component holdup states (always)
- Optional tray vapor component holdup states
- Optional boundary holdup states (top/bottom)
- Optional temperature states (legacy): tray_T_f + bottom_T_f
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

    # Legacy temperature-state option (tests rely on this existing)
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
          bottom_T_f (1) [if include_temperature and include_bottom]
          tray_EL_BTU (N) [if include_energy]
          tray_EV_BTU (N) [if include_energy and include_vapor]
        """
        N = self.n_stages
        Nc = self.n_components

        sl: Dict[str, slice] = {}
        idx = 0

        sl["tray_L"] = slice(idx, idx + N * Nc)
        idx += N * Nc

        if self.include_vapor:
            sl["tray_V"] = slice(idx, idx + N * Nc)
            idx += N * Nc

        if self.include_top:
            sl["top_L"] = slice(idx, idx + Nc)
            idx += Nc
            if self.include_vapor:
                sl["top_V"] = slice(idx, idx + Nc)
                idx += Nc

        if self.include_bottom:
            sl["bottom_L"] = slice(idx, idx + Nc)
            idx += Nc
            if self.include_vapor:
                sl["bottom_V"] = slice(idx, idx + Nc)
                idx += Nc

        if self.include_temperature:
            sl["tray_T_f"] = slice(idx, idx + N)
            idx += N
            if self.include_bottom:
                sl["bottom_T_f"] = slice(idx, idx + 1)
                idx += 1

        if self.include_energy:
            sl["tray_EL_BTU"] = slice(idx, idx + N)
            idx += N
            if self.include_vapor:
                sl["tray_EV_BTU"] = slice(idx, idx + N)
                idx += N

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
        Pack initial conditions from a ColumnSpec-like object.

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

        ML0 = np.asarray(_get_first_attr(col, ["M_L_lbmol", "ML0_lbmol"]), dtype=float).reshape((N,))

        # Vapor holdup input is optional in the Excel template.
        # If absent/invalid, start from zero vapor holdup and let startup initialization
        # (e.g., pressure-based MV initialization) set a consistent profile.
        MV_raw = _get_first_attr(col, ["M_V_lbmol", "MV0_lbmol"])
        try:
            MV0 = np.asarray(MV_raw, dtype=float).reshape((N,))
        except Exception:
            MV0 = np.zeros(N, dtype=float)
        MV0 = np.where(np.isfinite(MV0), MV0, 0.0)

        x0 = np.asarray(_get_first_attr(col, ["x0"]), dtype=float).reshape((N, Nc))
        y0v = np.asarray(_get_first_attr(col, ["y0"]), dtype=float).reshape((N, Nc))

        tray_L = ML0[:, None] * x0
        y[sl["tray_L"]] = tray_L.ravel(order="C")

        if self.include_vapor:
            tray_V = MV0[:, None] * y0v
            y[sl["tray_V"]] = tray_V.ravel(order="C")

        # Boundary holdups: tiny eps allocations (doesn't affect tray states)
        if self.include_top:
            topL = None
            top_total = None
            distillate_z = None

            def _norm_key(s: str) -> str:
                return "".join(ch for ch in s.lower() if ch.isalnum())

            def _stream_comp_dict(stream_obj) -> Optional[dict]:
                if stream_obj is None:
                    return None
                if hasattr(stream_obj, "component_molar_flows_lbmolph"):
                    return getattr(stream_obj, "component_molar_flows_lbmolph")
                if isinstance(stream_obj, dict):
                    return stream_obj.get("Component Mole Flows (lbmol/h)") or stream_obj.get("component_molar_flows_lbmolph")
                return None

            def _norm_comp_key(s: str) -> str:
                return "".join(ch for ch in str(s).lower() if ch.isalnum())

            def _comp_val(comp_dict: dict, comp_name: str) -> Optional[float]:
                if not isinstance(comp_dict, dict):
                    return None
                norm_map = {_norm_comp_key(k): float(v) for k, v in comp_dict.items()}
                key = _norm_comp_key(comp_name)
                if key in norm_map:
                    return norm_map[key]
                try:
                    from dynamic_distillation.compound_registry_v1 import canonicalize_to_dwsim_id
                    canon = canonicalize_to_dwsim_id(comp_name)
                    key2 = _norm_comp_key(canon)
                    return norm_map.get(key2)
                except Exception:
                    return None

            # Prefer distillate stream composition for initial top drum composition
            streams = getattr(col, "streams", None)
            if isinstance(streams, dict):
                best = None
                best_score = 0
                for nm, sobj in streams.items():
                    key = _norm_key(str(nm))
                    if not key or "feed" in key or "bottom" in key:
                        continue
                    score = 0
                    if "distillate" in key:
                        score = 3
                    elif key.startswith("dist") or "dist" in key:
                        score = 2
                    elif "top" in key:
                        score = 1
                    if score > best_score:
                        best_score = score
                        best = sobj
                if best is not None:
                    comp_dict = _stream_comp_dict(best)
                    if isinstance(comp_dict, dict):
                        vals = []
                        for cname in getattr(col, "components_excel", []):
                            v = _comp_val(comp_dict, cname)
                            vals.append(0.0 if v is None else float(v))
                        tot = float(np.sum(vals))
                        if tot > 0.0:
                            distillate_z = np.asarray(vals, dtype=float) / tot

            # Optional user input: component holdup vector or total holdup (lbmol)
            if hasattr(col, "top_L0_lbmol"):
                raw = getattr(col, "top_L0_lbmol")
                try:
                    arr = np.asarray(raw, dtype=float).reshape((-1,))
                    if arr.size == Nc:
                        topL = arr.copy()
                    elif arr.size == 1:
                        top_total = float(arr[0])
                except Exception:
                    pass

            if topL is None:
                specs = getattr(col, "specs_raw", None)
                if isinstance(specs, dict):
                    for key in ("Top Accumulator Holdup (lbmol)", "Top Drum Holdup (lbmol)"):
                        v = specs.get(key)
                        if v is not None:
                            try:
                                top_total = float(v)
                                break
                            except Exception:
                                pass

            if topL is None and top_total is not None and np.isfinite(top_total) and top_total > 0.0:
                base = distillate_z if distillate_z is not None else tray_L[0, :].copy()
                topL = float(top_total) * self._safe_norm_vec(base, self.epsilon_lbmol)

            if topL is None:
                base = distillate_z if distillate_z is not None else tray_L[0, :].copy()
                topL = self.epsilon_lbmol * self._safe_norm_vec(base, self.epsilon_lbmol)

            y[sl["top_L"]] = topL
            if self.include_vapor:
                topV_base = (MV0[0] * y0v[0, :]).copy()
                topV = self.epsilon_lbmol * self._safe_norm_vec(topV_base, self.epsilon_lbmol)
                y[sl["top_V"]] = topV

        if self.include_bottom:
            botL = None
            bot_total = None
            bottoms_z = None

            def _norm_key(s: str) -> str:
                return "".join(ch for ch in s.lower() if ch.isalnum())

            def _stream_comp_dict(stream_obj) -> Optional[dict]:
                if stream_obj is None:
                    return None
                if hasattr(stream_obj, "component_molar_flows_lbmolph"):
                    return getattr(stream_obj, "component_molar_flows_lbmolph")
                if isinstance(stream_obj, dict):
                    return stream_obj.get("Component Mole Flows (lbmol/h)") or stream_obj.get("component_molar_flows_lbmolph")
                return None

            def _norm_comp_key(s: str) -> str:
                return "".join(ch for ch in str(s).lower() if ch.isalnum())

            def _comp_val(comp_dict: dict, comp_name: str) -> Optional[float]:
                if not isinstance(comp_dict, dict):
                    return None
                norm_map = {_norm_comp_key(k): float(v) for k, v in comp_dict.items()}
                key = _norm_comp_key(comp_name)
                if key in norm_map:
                    return norm_map[key]
                try:
                    from dynamic_distillation.compound_registry_v1 import canonicalize_to_dwsim_id
                    canon = canonicalize_to_dwsim_id(comp_name)
                    key2 = _norm_comp_key(canon)
                    return norm_map.get(key2)
                except Exception:
                    return None

            # Prefer bottoms stream composition for initial sump composition
            streams = getattr(col, "streams", None)
            if isinstance(streams, dict):
                best = None
                best_score = 0
                for nm, sobj in streams.items():
                    key = _norm_key(str(nm))
                    if not key or "feed" in key or "dist" in key or "top" in key:
                        continue
                    score = 0
                    if "bottoms" in key:
                        score = 3
                    elif key.startswith("bot") or "bottom" in key:
                        score = 2
                    elif "sump" in key:
                        score = 1
                    if score > best_score:
                        best_score = score
                        best = sobj
                if best is not None:
                    comp_dict = _stream_comp_dict(best)
                    if isinstance(comp_dict, dict):
                        vals = []
                        for cname in getattr(col, "components_excel", []):
                            v = _comp_val(comp_dict, cname)
                            vals.append(0.0 if v is None else float(v))
                        tot = float(np.sum(vals))
                        if tot > 0.0:
                            bottoms_z = np.asarray(vals, dtype=float) / tot

            if hasattr(col, "bottom_L0_lbmol"):
                raw = getattr(col, "bottom_L0_lbmol")
                try:
                    arr = np.asarray(raw, dtype=float).reshape((-1,))
                    if arr.size == Nc:
                        botL = arr.copy()
                    elif arr.size == 1:
                        bot_total = float(arr[0])
                except Exception:
                    pass

            if botL is None:
                specs = getattr(col, "specs_raw", None)
                if isinstance(specs, dict):
                    for key in ("Bottom Holdup (lbmol)", "Bottom Sump Holdup (lbmol)"):
                        v = specs.get(key)
                        if v is not None:
                            try:
                                bot_total = float(v)
                                break
                            except Exception:
                                pass

            if botL is None and bot_total is not None and np.isfinite(bot_total) and bot_total > 0.0:
                base = bottoms_z if bottoms_z is not None else tray_L[-1, :].copy()
                botL = float(bot_total) * self._safe_norm_vec(base, self.epsilon_lbmol)

            if botL is None:
                base = bottoms_z if bottoms_z is not None else tray_L[-1, :].copy()
                botL = self.epsilon_lbmol * self._safe_norm_vec(base, self.epsilon_lbmol)

            y[sl["bottom_L"]] = botL
            if self.include_vapor:
                botV_base = (MV0[-1] * y0v[-1, :]).copy()
                botV = self.epsilon_lbmol * self._safe_norm_vec(botV_base, self.epsilon_lbmol)
                y[sl["bottom_V"]] = botV

        # Temperature states (if enabled)
        if self.include_temperature:
            if hasattr(col, "T_f"):
                Ttray = np.asarray(col.T_f, dtype=float).reshape((N,))
            elif hasattr(col, "T0_F"):
                Ttray = np.asarray(col.T0_F, dtype=float).reshape((N,))
            else:
                Ttray = np.full(N, 100.0, dtype=float)

            y[sl["tray_T_f"]] = Ttray
            if self.include_bottom and "bottom_T_f" in sl:
                bot_T = float(Ttray[-1])
                streams = getattr(col, "streams", None)
                if isinstance(streams, dict):
                    for nm, sobj in streams.items():
                        if nm is None:
                            continue
                        key = "".join(ch for ch in str(nm).lower() if ch.isalnum())
                        if "bottom" in key or key.startswith("bot") or "sump" in key:
                            if hasattr(sobj, "temperature_f") and getattr(sobj, "temperature_f") is not None:
                                try:
                                    bot_T = float(getattr(sobj, "temperature_f"))
                                except Exception:
                                    pass
                            break
                y[sl["bottom_T_f"]] = np.array([float(bot_T)], dtype=float)

        # Energy holdup states (Module 6 Option B1)
        if self.include_energy:
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

                z = tray_L[i, :].copy()
                if self.include_vapor:
                    z = z + (MV0[i] * y0v[i, :])
                z = self._safe_norm_vec(z, self.epsilon_lbmol)

                if thermo is not None and hasattr(thermo, "flash_TP_full"):
                    fres = thermo.flash_TP_full(float(T0[i]), float(P0[i]), z)
                    hL = float(fres.HL_BTU_lbmol)
                    hV = float(fres.HV_BTU_lbmol)
                else:
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

        out["x_tray"] = self._safe_norm_rows(np.clip(tray_L, 0.0, None), self.epsilon_lbmol)
        if self.include_vapor:
            out["y_tray"] = self._safe_norm_rows(np.clip(out["tray_V"], 0.0, None), self.epsilon_lbmol)

        out["ML_tot_tray"] = tray_L.sum(axis=1).copy()
        if self.include_vapor:
            out["MV_tot_tray"] = out["tray_V"].sum(axis=1).copy()

        if self.include_temperature:
            out["tray_T_f"] = y[sl["tray_T_f"]].reshape((N,)).copy()
            if self.include_bottom and "bottom_T_f" in sl:
                out["bottom_T_f"] = y[sl["bottom_T_f"]].reshape((1,)).copy()

        if self.include_energy:
            out["tray_EL_BTU"] = y[sl["tray_EL_BTU"]].reshape((N,)).copy()
            if self.include_vapor and "tray_EV_BTU" in sl:
                out["tray_EV_BTU"] = y[sl["tray_EV_BTU"]].reshape((N,)).copy()

        return out
