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
  - flash_TP_full_F_psia(T_F, P_psia, z) -> (x, y, K, HL, HV[, Z])
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
# 1. Console silencing (unit-test friendly, plus .NET/native suppression)
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


class _DotNetConsoleSilencer:
    """Silence System.Console (works when pythonnet/.NET is involved)."""
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._Console = None
        self._TextWriter = None
        self._old_out = None
        self._old_err = None

    def __enter__(self):
        if not self.enabled:
            return self
        try:
            from System import Console  # type: ignore
            from System.IO import TextWriter  # type: ignore
            self._Console = Console
            self._TextWriter = TextWriter
            self._old_out = Console.Out
            self._old_err = Console.Error
            Console.SetOut(TextWriter.Null)
            Console.SetError(TextWriter.Null)
        except Exception:
            # If pythonnet isn't loaded yet or System isn't available, ignore.
            self._Console = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.enabled:
            return False
        try:
            if self._Console is not None:
                self._Console.SetOut(self._old_out)
                self._Console.SetError(self._old_err)
        except Exception:
            pass
        return False


class _FdSilencer:
    """Silence OS-level stdout/stderr (best-effort; helps for native DLL prints)."""
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._devnull = None
        self._stdout_fd = None
        self._stderr_fd = None

    def __enter__(self):
        if not self.enabled:
            return self
        try:
            self._devnull = open(os.devnull, "w")
            self._stdout_fd = os.dup(1)
            self._stderr_fd = os.dup(2)
            os.dup2(self._devnull.fileno(), 1)
            os.dup2(self._devnull.fileno(), 2)
        except Exception:
            # Some environments may not support dup/dup2 cleanly; ignore.
            self._devnull = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.enabled:
            return False
        try:
            if self._stdout_fd is not None:
                os.dup2(self._stdout_fd, 1)
                os.close(self._stdout_fd)
            if self._stderr_fd is not None:
                os.dup2(self._stderr_fd, 2)
                os.close(self._stderr_fd)
        except Exception:
            pass
        try:
            if self._devnull is not None:
                self._devnull.close()
        except Exception:
            pass
        return False


@contextlib.contextmanager
def _silence_console(enabled: bool = True):
    """
    Best-effort silencing for:
      - Python stdout/stderr (sys)
      - .NET Console.Out/Error (pythonnet)
      - OS-level FD 1/2 (native prints)
    Still returns a capture object for Python-level prints (useful for tests).
    """
    if not enabled:
        yield ConsoleCapture(io.StringIO(), io.StringIO())
        return

    old_out, old_err = sys.stdout, sys.stderr
    cap_out, cap_err = io.StringIO(), io.StringIO()

    with _FdSilencer(True), _DotNetConsoleSilencer(True):
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
M3_PER_FT3 = 0.028316846592
MOL_PER_LBMOL = 453.59237

def F_to_K(T_F: float) -> float:
    return (T_F - 32.0) * 5.0 / 9.0 + 273.15


def _mol_m3_to_lbmol_ft3(rho_mol_m3: float) -> float:
    # mol/m3 -> mol/ft3 -> lbmol/ft3
    return float(rho_mol_m3) * M3_PER_FT3 / MOL_PER_LBMOL


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


def _flash_TP_F_psia(T_F: float, P_psia: float, z):
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

    # Optional: compute vapor-phase compressibility factor Z for diagnostics.
    # DWSIM's PTFlash does not return Z directly, but we can recover it from
    # vapor density if available: Z = P / (rho_molar * R * T).
    Zfac = None
    try:
        # Try a direct Z property first (name varies by DWSIM build).
        for _pname in ("compressibilityfactor", "compressibility factor", "z", "Z"):
            try:
                _zv = _dtlc.CalcProp(_prop_package, _pname, "Mole", "Vapor", _carray, T_K, P_Pa, y_array)
                _z = float(_zv[0])
                if np.isfinite(_z) and _z > 0.0:
                    Zfac = float(_z)
                    break
            except Exception:
                continue

        if Zfac is None:
            # Try to get a molar density (basis='Mole'). Some builds return kmol/m3.
            _rv = _dtlc.CalcProp(_prop_package, "density", "Mole", "Vapor", _carray, T_K, P_Pa, y_array)
            _rho = float(_rv[0])
            if np.isfinite(_rho) and _rho > 0.0:
                # Heuristic unit normalization:
                # Ideal gas molar density here is O(10^2-10^3) mol/m3, or O(10^-1) kmol/m3.
                _rho_mol_m3 = _rho * 1000.0 if _rho < 50.0 else _rho
                R_SI = 8.314462618  # Pa*m3/(mol*K)
                _z = float(P_Pa) / (_rho_mol_m3 * R_SI * float(T_K))
                if np.isfinite(_z) and 0.02 < _z < 10.0:
                    Zfac = float(_z)

        if Zfac is None:
            # Fallback: use mass density + molecular weight if exposed by CalcProp.
            _rv = _dtlc.CalcProp(_prop_package, "density", "Mass", "Vapor", _carray, T_K, P_Pa, y_array)
            _rho_mass = float(_rv[0])  # kg/m3 (typical)
            if np.isfinite(_rho_mass) and _rho_mass > 0.0:
                _mw = None
                for _mwname in ("molecularweight", "molecular weight", "mw"):
                    try:
                        _mv = _dtlc.CalcProp(_prop_package, _mwname, "Mole", "Vapor", _carray, T_K, P_Pa, y_array)
                        _mw = float(_mv[0])
                        break
                    except Exception:
                        continue
                if _mw is not None and np.isfinite(_mw) and _mw > 0.0:
                    # Heuristic: if MW looks like kg/kmol (e.g., 44), convert to kg/mol.
                    _mw_kg_per_mol = _mw / 1000.0 if _mw > 1.0 else _mw
                    R_SI = 8.314462618
                    _z = float(P_Pa) * _mw_kg_per_mol / (_rho_mass * R_SI * float(T_K))
                    if np.isfinite(_z) and 0.02 < _z < 10.0:
                        Zfac = float(_z)
    except Exception:
        Zfac = None

    if Zfac is None:
        return x, y, K, HL_BTU_lbmol, HV_BTU_lbmol
    return x, y, K, HL_BTU_lbmol, HV_BTU_lbmol, float(Zfac)


def liquid_density_lbmol_ft3(T_F: float, P_psia: float, x) -> Optional[float]:
    """Compute liquid molar density (lbmol/ft^3) using DWSIM CalcProp."""
    _init_dwsim()
    from System import Array  # type: ignore

    T_K = F_to_K(T_F)
    P_Pa = float(P_psia) * PSIA_TO_PA

    x = np.asarray(x, dtype=float).ravel()
    if x.size != len(_component_ids):
        raise ValueError(f"x must be length {len(_component_ids)}; got {x.size}")
    if x.sum() <= 0:
        raise ValueError("x must have a positive sum")
    x = x / x.sum()

    x_array = Array[float](list(x))

    # Try molar density directly
    try:
        _rv = _dtlc.CalcProp(_prop_package, "density", "Mole", "Liquid", _carray, T_K, P_Pa, x_array)
        _rho = float(_rv[0])
        if np.isfinite(_rho) and _rho > 0.0:
            _rho_mol_m3 = _rho * 1000.0 if _rho < 50.0 else _rho
            return _mol_m3_to_lbmol_ft3(_rho_mol_m3)
    except Exception:
        pass

    # Fallback: use mass density + molecular weight
    try:
        _rv = _dtlc.CalcProp(_prop_package, "density", "Mass", "Liquid", _carray, T_K, P_Pa, x_array)
        _rho_mass = float(_rv[0])  # kg/m3 (typical)
        if np.isfinite(_rho_mass) and _rho_mass > 0.0:
            _mw = None
            for _mwname in ("molecularweight", "molecular weight", "mw"):
                try:
                    _mv = _dtlc.CalcProp(_prop_package, _mwname, "Mole", "Liquid", _carray, T_K, P_Pa, x_array)
                    _mw = float(_mv[0])
                    break
                except Exception:
                    continue
            if _mw is not None and np.isfinite(_mw) and _mw > 0.0:
                _mw_kg_per_mol = _mw / 1000.0 if _mw > 1.0 else _mw
                _rho_mol_m3 = _rho_mass / _mw_kg_per_mol
                if np.isfinite(_rho_mol_m3) and _rho_mol_m3 > 0.0:
                    return _mol_m3_to_lbmol_ft3(_rho_mol_m3)
    except Exception:
        pass

    return None


def component_mw_lbm_per_lbmol(T_F: float = 60.0, P_psia: float = 14.7) -> Optional[np.ndarray]:
    """Return component molecular weights (lbm/lbmol) using DWSIM CalcProp."""
    _init_dwsim()
    from System import Array, String  # type: ignore

    if not _component_ids:
        raise RuntimeError("Call set_component_ids([...]) before requesting component MWs.")

    T_K = F_to_K(T_F)
    P_Pa = float(P_psia) * PSIA_TO_PA

    n = len(_component_ids)
    _carray = Array[String](_component_ids)
    mw = np.full(n, np.nan, dtype=float)

    for i in range(n):
        z = np.zeros(n, dtype=float)
        z[i] = 1.0
        z_array = Array[float](list(z))

        val = None
        for _mwname in ("molecularweight", "molecular weight", "mw"):
            try:
                _mv = _dtlc.CalcProp(_prop_package, _mwname, "Mole", "Liquid", _carray, T_K, P_Pa, z_array)
                val = float(_mv[0])
                break
            except Exception:
                continue
        if val is None or (not np.isfinite(val)) or val <= 0.0:
            return None

        # Heuristic: if MW looks like kg/mol (< 1), convert to kg/kmol.
        if val < 1.0:
            val = val * 1000.0

        mw[i] = float(val)

    if not np.all(np.isfinite(mw)):
        return None
    return mw


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
    "component_mw_lbm_per_lbmol",
    "silence_console",
]
