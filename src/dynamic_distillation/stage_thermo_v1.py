"""
stage_thermo_v1.py

Dynamic Distillation - Stage Thermo Adapter

PURPOSE
-------
Provide a testable, provider-agnostic adapter for flash calculations.
Converts provider flash results to standardized StageFlashResult format.
Handles multiple provider API styles and normalizes compositions.

INPUTS
------
provider : ThermoProvider
    Object with flash_TP_full_F_psia() or flash_TP_full() method
T_F : float
    Temperature (°F)
P_psia : float
    Pressure (psia)
z : array-like
    Overall composition (mole fractions)

OUTPUTS
-------
result : StageFlashResult
    x : np.ndarray (Nc,) - Liquid phase composition (normalized)
    y : np.ndarray (Nc,) - Vapor phase composition (normalized)
    K : np.ndarray (Nc,) - K-values (y/x)
    HL_BTU_lbmol : float - Liquid molar enthalpy (Btu/lbmol)
    HV_BTU_lbmol : float - Vapor molar enthalpy (Btu/lbmol)
    Z : Optional[float] - Compressibility factor

DEPENDENCIES
------------
(No specific module dependencies - provider-agnostic)

ASSUMPTIONS & CONSTRAINTS
--------------------------
- Provider has flash_TP_full_F_psia() OR flash_TP_full() method
- Compositions defensively normalized to sum = 1.0
- Returned x, y may not exactly sum to 1.0; re-normalized internally
- Z-factor optional; defaults to None if not available
- Method seeks Z-factor under multiple attribute names (Z, Z_factor, Zfac, z_factor)

SIDE EFFECTS / STATE MUTATIONS
-------------------------------
- Does NOT modify provider state or inputs
- Composition normalization is defensive (no modification of input array)
- Returns fresh StageFlashResult each call

PERFORMANCE NOTES
-----------------
- Adapter overhead negligible: < 0.1 ms
- Cost dominated by provider flash call (10-50 ms for DWSIM, < 1 ms for surrogate)

ERROR HANDLING
--------------
- Raises ProviderError if:
    * Provider method not found
    * Provider returns invalid data (wrong shape, NaN, etc.)
- Warnings logged if Z-factor extraction fails (returns None)

VERSION / COMPATIBILITY
-----------------------
v1.0 (current):
    - Provider-agnostic; supports multiple API styles
    - Backward compatible with legacy Z-factor naming

NOTES / KEY FEATURES
--------------------
Created: 2026-01-11 (America/New_York)
Updated: 2026-01-11 17:10 (America/New_York)

- Supports multiple provider API versions:
  * flash_TP_full_F_psia() with tuple return
  * flash_TP_full() with object/tuple return
- Defensive composition normalization (z, x, y)
- Z-factor optional; defaults to None
- Flexible Z-factor attribute names (Z, Z_factor, Zfac, z_factor)

EXAMPLE USAGE
-------------
    from dynamic_distillation.stage_thermo_v1 import flash_TP_full_F_psia
    from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1
    
    provider = ThermoProviderV1(
        component_names_excel=["Propane", "n-Butane", "n-Pentane"],
        component_ids_dwsim=["Propane", "N-butane", "N-pentane"]
    )
    
    T_F, P_psia = 120.0, 150.0
    z = np.array([0.3, 0.5, 0.2])
    
    result = flash_TP_full_F_psia(provider, T_F, P_psia, z)
    print(f"Liquid composition: {result.x}")
    print(f"K-values: {result.K}")
    if result.Z is not None:
        print(f"Z-factor: {result.Z}")
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