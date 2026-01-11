# src/dynamic_distillation/pr_flash_backend_v1.py
"""
pr_flash_backend_v1.py

Peng–Robinson TP flash wrapper using the DWSIM Thermodynamics Library (DTL).

Header:
  Created: 2026-01-11 15:xx (America/New_York)
  Updated: 2026-01-11  (America/New_York)

Purpose
-------
Canonical PR flash backend for Dynamic_DistillationII.

Design requirements
-------------------
- MUST NOT hard-wire any compounds.
- Component selection is always driven by the simulation case:
    * DWSIM IDs (for DWSIM primary)
    * Excel names (for thermo-python fallback)

Public API (stable)
-------------------
  - ZArray
  - set_component_ids([...])                    # DWSIM IDs
  - set_component_names([...])                  # thermo IDs / names for fallback
  - pr_flash_TP_F_psia(T_F, P_psia, z) -> (K, HL, HV)
  - flash_TP_full_F_psia(T_F, P_psia, z) -> (x, y, K, HL, HV)
  - get_thermo_coefficients(T_F, P_psia, z, perturbation_dt=1.0)
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from typing import Tuple, Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# 1. Console silencing (unit-test friendly)
# ---------------------------------------------------------------------------

class ConsoleCapture:
    """Capture object for stdout/stderr."""
    def __init__(self, stdout_io: io.StringIO, stderr_io: io.StringIO):
        self.stdout = stdout_io
        self.stderr = stderr_io

    def __getitem__(self, idx: int):
        return (self.stdout, self.stderr)[idx]

    def __iter__(self):
        yield self.stdout
        yield self.stderr

    def __len__(self):
        return 2

    @property
    def stdout_text(self) -> str:
        return self.stdout.getvalue()

    @property
    def stderr_text(self) -> str:
        return self.stderr.getvalue()


@contextlib.contextmanager
def _silence_console(enabled: bool = True):
    if not enabled:
        yield ConsoleCapture(io.StringIO(), io.StringIO())
        return

    old_out, old_err = sys.stdout, sys.stderr
    cap_out, cap_err = io.StringIO(), io.StringIO()
    try:
        sys.stdout, sys.stderr = cap_out, cap_err
        yield ConsoleCapture(cap_out, cap_err)
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def silence_console(enabled: bool = True):
    return _silence_console(enabled)


# ---------------------------------------------------------------------------
# 2. Basic helpers
# ---------------------------------------------------------------------------

class ZArray(np.ndarray):
    """Helper subclass just to preserve older interface."""
    def __new__(cls, input_array):
        return np.asarray(input_array, dtype=float).view(cls)

    def __eq__(self, other):
        return np.allclose(self, other)

    def as_np(self) -> np.ndarray:
        return np.asarray(self, dtype=float)


# Unit conversions
PSIA_TO_PA = 6894.7572931783

# DWSIM CalcProp enthalpy in J/mol -> BTU/lbmol
J_PER_MOL_TO_BTU_PER_LBMOL = 0.4299226139294927

def F_to_K(T_F: float) -> float:
    return (T_F - 32.0) * 5.0 / 9.0 + 273.15


# ---------------------------------------------------------------------------
# 3. DWSIM Thermodynamics integration (pythonnet + DTL)
# ---------------------------------------------------------------------------

DWSIM_DTL_PATH_DEFAULT = r"C:\Users\Thoma\DWSIM\DTL"

# IMPORTANT: no hardwired compounds
_component_ids: List[str] = []                # DWSIM IDs (required for DWSIM primary)
_component_names: Optional[List[str]] = None  # Excel/thermo IDs (required for thermo fallback)

_dwsim_initialized = False
_dtlc = None
_prop_package = None
_carray = None


def set_component_ids(component_ids: List[str]) -> None:
    """
    Set the DWSIM compound IDs used in subsequent flash calls.

    This is REQUIRED for DWSIM primary operation.
    """
    global _component_ids, _dwsim_initialized, _carray, _dtlc, _prop_package
    if not component_ids or not all(isinstance(s, str) and s.strip() for s in component_ids):
        raise ValueError("component_ids must be a non-empty list of non-empty strings")
    _component_ids = [s.strip() for s in component_ids]

    # force rebuild on next call
    _dwsim_initialized = False
    _carray = None
    _dtlc = None
    _prop_package = None


def set_component_names(component_names: Optional[List[str]]) -> None:
    """
    Set human-readable component names for thermo-python fallback.

    If DWSIM is unavailable, fallback requires this list and it MUST match len(component_ids).
    """
    global _component_names
    if component_names is None:
        _component_names = None
        return
    if not component_names or not all(isinstance(s, str) and s.strip() for s in component_names):
        raise ValueError("component_names must be a non-empty list of non-empty strings")
    _component_names = [s.strip() for s in component_names]


def _init_dwsim():
    """Lazy-initialize DWSIM Standalone Thermodynamics Library (DTL)."""
    global _dwsim_initialized, _dtlc, _prop_package, _carray

    if _dwsim_initialized:
        return

    if not _component_ids:
        raise RuntimeError(
            "DWSIM backend not configured: component IDs are empty. "
            "Call set_component_ids([...]) before flashing."
        )

    dtl_path = os.environ.get("DWSIM_DTL_PATH", DWSIM_DTL_PATH_DEFAULT)
    dtl_path = os.path.abspath(dtl_path)

    try:
        import clr  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pythonnet is required to use DWSIM flash.\n"
            "Install it with:  python -m pip install pythonnet"
        ) from exc

    dll_candidates = [
        "DWSIM.Thermodynamics.StandaloneLibrary.dll",
        "DWSIM.Thermodynamics.dll",
    ]

    loaded = False
    for dll in dll_candidates:
        full_path = os.path.join(dtl_path, dll)
        if os.path.exists(full_path):
            clr.AddReference(full_path)
            loaded = True
            break

    if not loaded:
        raise RuntimeError(
            f"Could not find a DWSIM thermo DLL in '{dtl_path}'. "
            "Set DWSIM_DTL_PATH to the folder containing the DLLs."
        )

    interfaces_dll = os.path.join(dtl_path, "DWSIM.Interfaces.dll")
    if os.path.exists(interfaces_dll):
        clr.AddReference(interfaces_dll)

    from System import Array, String  # type: ignore

    try:
        from DWSIM.Thermodynamics import PropertyPackages, CalculatorInterface  # type: ignore
    except Exception:
        from DWSIM.Thermodynamics.PropertyPackages import PropertyPackages  # type: ignore
        from DWSIM.Thermodynamics import CalculatorInterface  # type: ignore

    _dtlc = CalculatorInterface.Calculator()
    _dtlc.Initialize()

    _prop_package = PropertyPackages.PengRobinsonPropertyPackage(True)
    _dtlc.TransferCompounds(_prop_package)

    _carray = Array[String](_component_ids)
    _dwsim_initialized = True


def _flash_TP_F_psia(T_F: float, P_psia: float, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Perform a TP flash with DWSIM at T_F [°F], P_psia [psia]."""
    _init_dwsim()
    from System import Array  # type: ignore
    global _dtlc, _prop_package, _carray

    T_K = F_to_K(T_F)
    P_Pa = float(P_psia) * PSIA_TO_PA

    z = np.asarray(z, dtype=float).ravel()
    if z.size != len(_component_ids):
        raise ValueError(f"z must be length {len(_component_ids)}; got {z.size}")
    if z.sum() <= 0:
        raise ValueError("z must have a positive sum")
    z = z / z.sum()

    comparray = Array[float](list(z))

    # spec=0 means T & P specified
    result = _dtlc.PTFlash(_prop_package, 0, P_Pa, T_K, _carray, comparray)

    n_rows = result.GetLength(0)
    n_cols = result.GetLength(1)
    if n_rows < 2:
        raise RuntimeError("Unexpected PTFlash result shape from DWSIM (rows < 2).")

    phase_names = [str(result[0, j]) for j in range(n_cols)]
    n_comp = n_rows - 2
    if n_comp != len(_component_ids):
        raise RuntimeError(f"Expected {len(_component_ids)} components, got {n_comp}. Check IDs.")

    comp_fracs = np.zeros((n_comp, n_cols), dtype=float)
    for i in range(n_comp):
        for j in range(n_cols):
            comp_fracs[i, j] = float(result[2 + i, j])

    vap_col = None
    liq_col = None
    for j, name in enumerate(phase_names):
        lname = name.lower()
        if "vapor" in lname or "vapour" in lname:
            vap_col = j
        elif "liquid" in lname and liq_col is None:
            liq_col = j

    # Conservative defaults if phase names aren’t clear
    if vap_col is None and n_cols >= 1:
        vap_col = 0
    if liq_col is None and n_cols >= 2:
        liq_col = 1

    # Single phase fallback
    if vap_col is None or liq_col is None or vap_col == liq_col:
        x = z.copy()
        y = z.copy()
        K = np.ones_like(z)
        y_array = Array[float](list(y))
        h_vals = _dtlc.CalcProp(_prop_package, "enthalpy", "Mole", "Vapor", _carray, T_K, P_Pa, y_array)
        H_BTU_lbmol = float(h_vals[0]) * J_PER_MOL_TO_BTU_PER_LBMOL
        return x, y, K, H_BTU_lbmol, H_BTU_lbmol

    x = comp_fracs[:, liq_col].copy()
    y = comp_fracs[:, vap_col].copy()

    x_sum = x.sum()
    y_sum = y.sum()
    if x_sum <= 0.0 or y_sum <= 0.0:
        raise RuntimeError("PTFlash returned invalid phase compositions (sum <= 0).")

    x /= x_sum
    y /= y_sum

    K = np.ones_like(y)
    mask = x > 1e-12
    K[mask] = y[mask] / x[mask]

    x_array = Array[float](list(x))
    y_array = Array[float](list(y))

    hL_vals = _dtlc.CalcProp(_prop_package, "enthalpy", "Mole", "Liquid", _carray, T_K, P_Pa, x_array)
    hV_vals = _dtlc.CalcProp(_prop_package, "enthalpy", "Mole", "Vapor", _carray, T_K, P_Pa, y_array)

    HL_BTU_lbmol = float(hL_vals[0]) * J_PER_MOL_TO_BTU_PER_LBMOL
    HV_BTU_lbmol = float(hV_vals[0]) * J_PER_MOL_TO_BTU_PER_LBMOL

    return x, y, K, HL_BTU_lbmol, HV_BTU_lbmol


def _flash_TP_F_psia_thermo(T_F: float, P_psia: float, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """
    Fallback TP flash using the `thermo` Python library (PR EOS).

    REQUIREMENTS:
      - set_component_names([...]) MUST be called
      - len(component_names) MUST match len(z)
      - component_names must be resolvable by thermo's ChemicalConstantsPackage.from_IDs
    """
    try:
        from thermo import ChemicalConstantsPackage, PRMIX, CEOSGas, CEOSLiquid, FlashVL  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "DWSIM flash is unavailable and `thermo` fallback could not be imported. "
            "Install `thermo` or configure DWSIM."
        ) from exc

    z_arr = ZArray(z).as_np().ravel()
    if z_arr.sum() <= 0:
        raise ValueError("z must have a positive sum")
    z_arr = z_arr / z_arr.sum()

    if _component_names is None:
        raise RuntimeError(
            "thermo fallback requires component names. "
            "Call set_component_names([...]) before flashing."
        )

    comps = list(_component_names)
    if len(comps) != len(z_arr):
        raise RuntimeError(
            f"thermo fallback component name list length {len(comps)} "
            f"does not match z length {len(z_arr)}."
        )

    # thermo expects identifiers it can resolve (names/CAS/InChI/etc)
    try:
        const = ChemicalConstantsPackage.from_IDs(comps)
    except Exception as exc:
        raise RuntimeError(
            "thermo fallback could not resolve one or more component names/IDs. "
            "Use names/IDs compatible with thermo (or rely on DWSIM primary)."
        ) from exc

    eos = PRMIX(Tcs=const.Tcs, Pcs=const.Pcs, omegas=const.omegas)
    gas = CEOSGas(eos)
    liq = CEOSLiquid(eos)
    flasher = FlashVL(const, gas=gas, liquids=[liq])

    T_K = F_to_K(T_F)
    P_Pa = float(P_psia) * PSIA_TO_PA

    res = flasher.flash(T=T_K, P=P_Pa, zs=z_arr.tolist())

    # Extract phase compositions and enthalpies if available
    if res.gas is None:
        y = z_arr.copy()
        HV_BTU_lbmol = 0.0
    else:
        y = np.asarray(res.gas.zs, dtype=float)
        # res.gas.H() is J/mol in thermo; convert to Btu/lbmol
        HV_BTU_lbmol = float(res.gas.H()) * J_PER_MOL_TO_BTU_PER_LBMOL

    if res.liquid0 is None:
        x = z_arr.copy()
        HL_BTU_lbmol = 0.0
    else:
        x = np.asarray(res.liquid0.zs, dtype=float)
        HL_BTU_lbmol = float(res.liquid0.H()) * J_PER_MOL_TO_BTU_PER_LBMOL

    x = np.clip(x, 1e-20, None)
    y = np.clip(y, 1e-20, None)
    x = x / x.sum()
    y = y / y.sum()

    K = y / x
    return x, y, K, float(HL_BTU_lbmol), float(HV_BTU_lbmol)


# ---------------------------------------------------------------------------
# 4. Public API
# ---------------------------------------------------------------------------

def pr_flash_TP_F_psia(T_F: float, P_psia: float, z) -> Tuple[np.ndarray, float, float]:
    _, _, K, HL, HV = flash_TP_full_F_psia(T_F, P_psia, z)
    return K, HL, HV


def flash_TP_full_F_psia(T_F: float, P_psia: float, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """
    Return full TP flash results: (x, y, K, HL, HV).

    Behavior:
      - DWSIM primary
      - thermo fallback only if DWSIM is unavailable
      - NO hardwired compounds; configuration is required.
    """
    try:
        return _flash_TP_F_psia(T_F, P_psia, z)
    except (ImportError, ModuleNotFoundError):
        return _flash_TP_F_psia_thermo(T_F, P_psia, z)
    except RuntimeError as exc:
        msg = str(exc)
        # If DWSIM isn't configured/available, attempt thermo fallback
        if "pythonnet" in msg or "DWSIM" in msg or "thermo DLL" in msg or "not configured" in msg:
            return _flash_TP_F_psia_thermo(T_F, P_psia, z)
        raise


def get_thermo_coefficients(
    T_F: float,
    P_psia: float,
    z,
    perturbation_dt: float = 1.0
) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """
    Compute K(T) and enthalpy(T) coefficients around a reference temperature.
    """
    x0, y0, K0, HL0, HV0 = flash_TP_full_F_psia(T_F, P_psia, z)
    _, _, K1, HL1, HV1 = flash_TP_full_F_psia(T_F + perturbation_dt, P_psia, z)

    # Temperature in Rankine
    T0_R = T_F + 459.67
    T1_R = T_F + perturbation_dt + 459.67

    invT0 = 1.0 / T0_R
    invT1 = 1.0 / T1_R
    if abs(invT1 - invT0) < 1e-12:
        raise ValueError("perturbation_dt too small to compute K(T) coefficients.")

    lnK0 = np.log(K0)
    lnK1 = np.log(K1)

    slope = (lnK1 - lnK0) / (invT1 - invT0)
    B_k = -slope
    A_k = lnK0 + B_k * invT0

    B_hl = (HL1 - HL0) / perturbation_dt
    A_hl = HL0 - B_hl * T_F

    B_hv = (HV1 - HV0) / perturbation_dt
    A_hv = HV0 - B_hv * T_F

    coeffs = {
        "K_A": A_k,
        "K_B": B_k,
        "HL_A": A_hl,
        "HL_B": B_hl,
        "HV_A": A_hv,
        "HV_B": B_hv,
    }

    props = {
        "x": x0,
        "y": y0,
        "HL": HL0,
        "HV": HV0,
    }

    return coeffs, props


__all__ = [
    "ZArray",
    "set_component_ids",
    "set_component_names",
    "pr_flash_TP_F_psia",
    "flash_TP_full_F_psia",
    "get_thermo_coefficients",
    "silence_console",
]
