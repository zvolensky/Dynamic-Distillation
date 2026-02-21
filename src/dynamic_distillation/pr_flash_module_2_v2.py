"""
pr_flash_module_2_v2.py

Dynamic Distillation - Alternate PR Flash Adapter

PURPOSE
-------
Maintain an alternate/legacy DWSIM flash wrapper used for compatibility and
backend experimentation scenarios.

INPUTS
------
- component configuration
- TP flash requests (T, P, z)

OUTPUTS
-------
- K values, phase enthalpies, and optional phase compositions/Z diagnostics

KEY DEPENDENCIES
----------------
- pythonnet + DWSIM thermodynamics bindings

ASSUMPTIONS & CONSTRAINTS
-------------------------
- API surface intentionally overlaps with pr_flash_backend_v1 where feasible.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from typing import Tuple, Dict, List

import numpy as np


# ---------------------------------------------------------------------------
# 1. Console silencing (unit-test friendly)
#
# Some unit tests expect a private context manager `_silence_console` that
# yields a subscriptable capture object where capture[0] is stdout and
# capture[1] is stderr (both `io.StringIO`).
#
# We also provide a public alias `silence_console`.
# ---------------------------------------------------------------------------

class ConsoleCapture:
    """Capture object for stdout/stderr.

    Behaves like a 2-tuple (stdout_io, stderr_io) *and* exposes convenience
    properties used by different unit tests.
    """

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
    """Redirect Python-level stdout/stderr to StringIO while in the context.

    Yields:
        ConsoleCapture (subscriptable; capture[0] is stdout, capture[1] is stderr)
    """
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
    """Public alias for `_silence_console` (kept for readability)."""
    return _silence_console(enabled)

# ---------------------------------------------------------------------------
# 1. Basic helpers
# ---------------------------------------------------------------------------

class ZArray(np.ndarray):
    """Small helper subclass just to preserve the old interface."""
    def __new__(cls, input_array):
        return np.asarray(input_array, dtype=float).view(cls)

    def __eq__(self, other):
        return np.allclose(self, other)


# Unit conversions
PSIA_TO_PA = 6894.7572931783
PA_TO_PSIA = 1.0 / PSIA_TO_PA

# DWSIM/DTL returns enthalpy in SI units per mole.
# Convert J/mol -> BTU/lbmol
J_PER_MOL_TO_BTU_PER_LBMOL = 0.4299226139294927  # 0.00094781712 * 453.59237

def F_to_K(T_F: float) -> float:
    """Fahrenheit to Kelvin."""
    return (T_F - 32.0) * 5.0 / 9.0 + 273.15


# ---------------------------------------------------------------------------
# 2. DWSIM Thermodynamics integration (pythonnet + DTL)
# ---------------------------------------------------------------------------

DWSIM_DTL_PATH_DEFAULT = r"C:\\Users\\Thoma\\DWSIM\\DTL"

# Default component IDs as known by DWSIM's compound database.
# NOTE: these must match DWSIM internal IDs exactly.
_component_ids: List[str] = ["Propane", "N-butane", "N-pentane"]
# Optional: human-readable names to use with the thermo-python fallback
# (preferred over _component_ids when set)
_component_names: List[str] | None = None

# Internal globals for DWSIM objects
_dwsim_initialized = False
_dtlc = None               # CalculatorInterface.Calculator
_prop_package = None       # PengRobinsonPropertyPackage
_carray = None             # Array[String] of component IDs

def set_component_ids(component_ids: List[str]) -> None:
    """Override the DWSIM component IDs used in subsequent flash calls.

    This resets internal initialization so the next flash call re-initializes
    the DWSIM calculator with the new IDs.

    Example:
        set_component_ids(["Propane", "Isobutane", "N-pentane"])
    """
    global _component_ids, _dwsim_initialized, _carray
    if not component_ids or not all(isinstance(s, str) and s.strip() for s in component_ids):
        raise ValueError("component_ids must be a non-empty list of non-empty strings")
    _component_ids = [s.strip() for s in component_ids]
    # Force DWSIM re-init next time
    _dwsim_initialized = False
    _carray = None
    # Also clear cached objects (safe; will be rebuilt)
    try:
        globals()['_dtlc'] = None
        globals()['_prop_package'] = None
    except Exception:
        pass
def set_component_names(component_names: List[str] | None) -> None:
    """Set human-readable component names for the thermo fallback.

    This does not affect DWSIM initialization; it only changes which IDs/names
    are passed into the `thermo` library when DWSIM is unavailable.

    Pass None to clear.
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

    # Resolve DTL path
    dtl_path = os.environ.get("DWSIM_DTL_PATH", DWSIM_DTL_PATH_DEFAULT)
    dtl_path = os.path.abspath(dtl_path)

    try:
        import clr  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pythonnet is required to use pr_flash_module_2 with DWSIM.\n"
            "Install it with:  pip install pythonnet"
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
            f"Could not find any DWSIM thermo DLL in '{dtl_path}'. "
            "Expected one of: "
            "DWSIM.Thermodynamics.StandaloneLibrary.dll, "
            "DWSIM.Thermodynamics.dll"
        )

    interfaces_dll = os.path.join(dtl_path, "DWSIM.Interfaces.dll")
    if os.path.exists(interfaces_dll):
        clr.AddReference(interfaces_dll)

    from System import Array, String  # type: ignore

    # DWSIM pythonnet surface varies. Support the two common import styles:
    #   A) from DWSIM.Thermodynamics import PropertyPackages, CalculatorInterface
    #   B) from DWSIM.Thermodynamics.PropertyPackages import PropertyPackages
    #      from DWSIM.Thermodynamics import CalculatorInterface
    try:
        from DWSIM.Thermodynamics import PropertyPackages, CalculatorInterface  # type: ignore
    except Exception:
        from DWSIM.Thermodynamics.PropertyPackages import PropertyPackages  # type: ignore
        from DWSIM.Thermodynamics import CalculatorInterface  # type: ignore

    _dtlc = CalculatorInterface.Calculator()
    _dtlc.Initialize()

    _prop_package = PropertyPackages.PengRobinsonPropertyPackage(True)
    _dtlc.TransferCompounds(_prop_package)

    # Build component ID array for flash calls
    _carray = Array[String](_component_ids)

    _dwsim_initialized = True


# ---------------------------------------------------------------------------
# 3. Core flash helper
# ---------------------------------------------------------------------------

def _flash_TP_F_psia(T_F: float, P_psia: float, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Perform a TP flash with DWSIM at T_F [°F], P_psia [psia]."""
    _init_dwsim()

    from System import Array  # type: ignore
    global _dtlc, _prop_package, _carray

    T_K = F_to_K(T_F)
    P_Pa = float(P_psia) * PSIA_TO_PA

    z = np.asarray(z, dtype=float).ravel()
    if z.size != len(_component_ids):
        raise ValueError(
            f"z must be length {len(_component_ids)} to match component IDs {_component_ids}. Got size={z.size}"
        )
    if z.sum() <= 0:
        raise ValueError("z must have a positive sum")
    z = z / z.sum()

    comparray = Array[float](list(z))

    # spec = 0 means T & P specified (per DTL examples)
    result = _dtlc.PTFlash(_prop_package, 0, P_Pa, T_K, _carray, comparray)

    n_rows = result.GetLength(0)
    n_cols = result.GetLength(1)

    if n_rows < 2:
        raise RuntimeError("Unexpected PTFlash result shape from DWSIM (rows < 2).")

    phase_names = [str(result[0, j]) for j in range(n_cols)]

    n_comp = n_rows - 2
    if n_comp != len(_component_ids):
        raise RuntimeError(
            f"Expected {len(_component_ids)} components in PTFlash result, got {n_comp}. "
            "Check component IDs."
        )

    comp_fracs = np.zeros((n_comp, n_cols), dtype=float)
    for i in range(n_comp):
        for j in range(n_cols):
            comp_fracs[i, j] = float(result[2 + i, j])

    # Identify vapor and liquid phases. Fallback to column 0=vapor, 1=liquid.
    vap_col = None
    liq_col = None
    for j, name in enumerate(phase_names):
        lname = name.lower()
        if "vapor" in lname or "vapour" in lname:
            vap_col = j
        elif "liquid" in lname:
            if liq_col is None:
                liq_col = j

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
        h_vals = _dtlc.CalcProp(_prop_package, "enthalpy", "Mole", "Vapor",
                                _carray, T_K, P_Pa, y_array)
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

    hL_vals = _dtlc.CalcProp(_prop_package, "enthalpy", "Mole", "Liquid",
                             _carray, T_K, P_Pa, x_array)
    hV_vals = _dtlc.CalcProp(_prop_package, "enthalpy", "Mole", "Vapor",
                             _carray, T_K, P_Pa, y_array)

    HL_BTU_lbmol = float(hL_vals[0]) * J_PER_MOL_TO_BTU_PER_LBMOL
    HV_BTU_lbmol = float(hV_vals[0]) * J_PER_MOL_TO_BTU_PER_LBMOL

    return x, y, K, HL_BTU_lbmol, HV_BTU_lbmol


def _flash_TP_F_psia_thermo(T_F: float, P_psia: float, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Fallback TP flash using the `thermo` Python library (PR EOS).

    This is used when DWSIM (pythonnet + assemblies) isn't available.
    It is deliberately lightweight and only meant to keep the dynamic scaffold
    running; it is *not* intended as a perfect replacement for DWSIM.
    """
    # Import inside the function so unit tests that monkeypatch sys.modules
    # for DWSIM don't require `thermo`.
    try:
        from thermo import ChemicalConstantsPackage, PRMIX, CEOSGas, CEOSLiquid, FlashVL  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "DWSIM flash is unavailable and `thermo` fallback could not be imported. "
            "Install the `thermo` package or configure DWSIM."
        ) from exc

    z_arr = ZArray(z).as_np()

    # Prefer explicit names (set_component_names) for the thermo fallback.
    comps = list(_component_names) if _component_names else list(_component_ids or [])
    if comps and len(comps) != len(z_arr):
        comps = []
    if not comps:
        # Safe default for this project; override by calling set_component_ids([...]).
        comps = ["n-Propane", "n-Butane", "n-Pentane"]
        if len(comps) != len(z_arr):
            raise ValueError(
                f"Component list length ({len(comps)}) does not match z length ({len(z_arr)}). "
                "Call set_component_ids([...]) with the correct component IDs/names."
            )

    const = ChemicalConstantsPackage.from_IDs(comps)
    eos_kwargs = dict(Tcs=const.Tcs, Pcs=const.Pcs, omegas=const.omegas)
    eos = PRMIX(**eos_kwargs)
    gas = CEOSGas(eos)
    liq = CEOSLiquid(eos)
    flasher = FlashVL(const, gas=gas, liquids=[liq])

    T_K = F_to_K(T_F)
    P_Pa = float(P_psia) * PSIA_TO_PA
    res = flasher.flash(T=T_K, P=P_Pa, zs=z_arr.tolist())

    # If single-phase, fake the missing phase as equal composition (K=1).
    if res.VF is None:
        VF = 0.0
    else:
        VF = float(res.VF)

    if res.gas is None:
        y = z_arr.copy()
        HV_BTU_lbmol = float(res.H()) if hasattr(res, "H") else 0.0
    else:
        y = np.asarray(res.gas.zs, dtype=float)
        HV_BTU_lbmol = float(res.gas.H()) / 1055.056 * 453.59237  # J/mol -> BTU/lbmol

    if res.liquid0 is None:
        x = z_arr.copy()
        HL_BTU_lbmol = float(res.H()) if hasattr(res, "H") else 0.0
    else:
        x = np.asarray(res.liquid0.zs, dtype=float)
        HL_BTU_lbmol = float(res.liquid0.H()) / 1055.056 * 453.59237  # J/mol -> BTU/lbmol

    # Guard against zeros
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
    """Return (K, HL, HV) for a TP flash at T_F [°F], P_psia [psia]."""
    _, _, K, HL, HV = flash_TP_full_F_psia(T_F, P_psia, z)
    return K, HL, HV


def flash_TP_full_F_psia(T_F: float, P_psia: float, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Return full TP flash results: (x, y, K, HL, HV)."""
    try:
        return _flash_TP_F_psia(T_F, P_psia, z)
    except (ImportError, ModuleNotFoundError) as exc:
        # No DWSIM surface available -> thermo fallback
        return _flash_TP_F_psia_thermo(T_F, P_psia, z)
    except RuntimeError as exc:
        # DWSIM initialization errors often surface as RuntimeError in user setups
        msg = str(exc)
        if "DWSIM" in msg or "pythonnet" in msg or "PropertyPackages" in msg:
            return _flash_TP_F_psia_thermo(T_F, P_psia, z)
        raise


def get_thermo_coefficients(
    T_F: float,
    P_psia: float,
    z,
    perturbation_dt: float = 1.0
) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """Compute K(T) and enthalpy(T) coefficients around a reference temperature."""
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
        'K_A': A_k,
        'K_B': B_k,
        'HL_A': A_hl,
        'HL_B': B_hl,
        'HV_A': A_hv,
        'HV_B': B_hv,
    }

    props = {
        'x': x0,
        'y': y0,
        'HL': HL0,
        'HV': HV0,
    }

    return coeffs, props


__all__ = [
    "ZArray",
    "set_component_ids",
    "pr_flash_TP_F_psia",
    "flash_TP_full_F_psia",
    "get_thermo_coefficients",
]
