"""
stage_thermo_v1.py

Dynamic Distillation - Stage Thermo Adapter

PURPOSE
-------
Standardize thermo-provider flash responses into a single StageFlashResult
structure consumed by RHS logic.

INPUTS
------
flash_TP_full_F_psia(provider, T_F, P_psia, z, n_components):
- provider implementing flash_TP_full_F_psia or flash_TP_full
- stage conditions and composition

OUTPUTS
-------
StageFlashResult:
- x, y, K
- HL_BTU_lbmol, HV_BTU_lbmol
- optional Z

KEY DEPENDENCIES
----------------
- numpy
- provider interface from thermo_provider_v1 (or compatible adapter)

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Returned compositions are normalized defensively.
- Adapter accepts tuple/list/object provider return styles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np


@dataclass(frozen=True)
class StageFlashResult:
    """
    Standardized flash results for one stage.

    Units:
      HL_BTU_lbmol, HV_BTU_lbmol: Btu/lbmol
    """
    x: np.ndarray                 # (Nc,) liquid composition
    y: np.ndarray                 # (Nc,) vapor composition
    K: np.ndarray                 # (Nc,) K-values (y/x)
    HL_BTU_lbmol: float           # liquid molar enthalpy
    HV_BTU_lbmol: float           # vapor molar enthalpy

    # Module 8A: optional real-gas Z-factor
    Z: Optional[float] = None

    # Placeholder for later
    beta_vapor: Optional[float] = None


def _as_1d_float_array(v: Sequence[float], n: int) -> np.ndarray:
    a = np.asarray(v, dtype=float).reshape((-1,))
    if a.size != n:
        raise ValueError(f"Expected length {n}, got {a.size}")
    return a


def _normalize_comp(a: np.ndarray) -> np.ndarray:
    s = float(np.sum(a))
    if s <= 0.0:
        return a
    return a / max(s, 1e-300)


def flash_TP_full_F_psia(
    provider: Any,
    T_F: float,
    P_psia: float,
    z: Sequence[float],
    n_components: int,
) -> StageFlashResult:
    """
    Call a provider flash and normalize/standardize outputs.

    Returns:
      StageFlashResult with optional Z-factor (None if not supplied).
    """
    z_arr = np.asarray(z, dtype=float).reshape((-1,))
    if z_arr.size != n_components:
        raise ValueError(f"Expected z length {n_components}, got {z_arr.size}")

    z_arr = _normalize_comp(z_arr)

    # Preferred method
    if hasattr(provider, "flash_TP_full_F_psia") and callable(getattr(provider, "flash_TP_full_F_psia")):
        res = provider.flash_TP_full_F_psia(float(T_F), float(P_psia), z_arr.tolist())

        if not isinstance(res, (tuple, list)):
            raise RuntimeError("flash_TP_full_F_psia() must return a tuple/list.")

        Zfac: Optional[float] = None
        if len(res) == 5:
            x, y, K, HL, HV = res
        elif len(res) == 6:
            x, y, K, HL, HV, Zfac = res
        else:
            raise RuntimeError("flash_TP_full_F_psia() must return 5 or 6 values.")

        x = _normalize_comp(_as_1d_float_array(x, n_components))
        y = _normalize_comp(_as_1d_float_array(y, n_components))
        K = _as_1d_float_array(K, n_components)

        return StageFlashResult(
            x=x,
            y=y,
            K=K,
            HL_BTU_lbmol=float(HL),
            HV_BTU_lbmol=float(HV),
            Z=(float(Zfac) if Zfac is not None else None),
        )

    # Alternate method name
    if hasattr(provider, "flash_TP_full") and callable(getattr(provider, "flash_TP_full")):
        res = provider.flash_TP_full(float(T_F), float(P_psia), z_arr.tolist())

        # tuple/list return
        if isinstance(res, (tuple, list)):
            Zfac: Optional[float] = None
            if len(res) == 5:
                x, y, K, HL, HV = res
            elif len(res) == 6:
                x, y, K, HL, HV, Zfac = res
            else:
                raise RuntimeError("flash_TP_full() must return 5 or 6 values.")

            x = _normalize_comp(_as_1d_float_array(x, n_components))
            y = _normalize_comp(_as_1d_float_array(y, n_components))
            K = _as_1d_float_array(K, n_components)

            return StageFlashResult(
                x=x,
                y=y,
                K=K,
                HL_BTU_lbmol=float(HL),
                HV_BTU_lbmol=float(HV),
                Z=(float(Zfac) if Zfac is not None else None),
            )

        # object-like return
        x = _normalize_comp(_as_1d_float_array(getattr(res, "x"), n_components))
        y = _normalize_comp(_as_1d_float_array(getattr(res, "y"), n_components))
        K = _as_1d_float_array(getattr(res, "K"), n_components)
        HL = float(getattr(res, "HL_BTU_lbmol"))
        HV = float(getattr(res, "HV_BTU_lbmol"))

        Zfac = None
        for attr in ("Z", "Z_factor", "Zfac", "z_factor"):
            if hasattr(res, attr):
                try:
                    Zfac = float(getattr(res, attr))
                    break
                except Exception:
                    pass

        return StageFlashResult(
            x=x,
            y=y,
            K=K,
            HL_BTU_lbmol=HL,
            HV_BTU_lbmol=HV,
            Z=Zfac,
        )

    raise RuntimeError(
        "Thermo provider does not implement flash_TP_full_F_psia() or flash_TP_full()."
    )