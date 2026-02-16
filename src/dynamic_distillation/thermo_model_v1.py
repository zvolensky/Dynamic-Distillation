"""
thermo_model_v1.py

Dynamic Distillation - Thermo Model Interface and Placeholder

PURPOSE
-------
Define a minimal thermo model interface (as Protocol) and provide a simple
plug-compatible placeholder implementation (ConstantCpThermo). Intended for
scaffolding energy balances; later replaced with rigorous PR-based backend.

INPUTS
------
ThermoModel (Protocol) methods:
    h_liq_btu_per_lbmol(T_f, P_psia, x) : float
    h_vap_btu_per_lbmol(T_f, P_psia, y) : float
    cp_liq_btu_per_lbmolF(T_f, P_psia, x) : float
    cp_vap_btu_per_lbmolF(T_f, P_psia, y) : float
    z_factor(T_f, P_psia, y) : float

OUTPUTS
-------
Implement the ThermoModel protocol with appropriate methods

DEPENDENCIES
------------
(None - standard library only)

ASSUMPTIONS & CONSTRAINTS
--------------------------
- ConstantCpThermo is a PLACEHOLDER only (not physically rigorous)
  * Constant heat capacity assumption; ignores T-dependence, pressure-dependence
  * Ideal gas assumption; no phase-specific non-ideality
  * Linear enthalpy: h = cp * (T - T_ref)
- ThermoModel Protocol is provider interface; implementations may be more rigorous
- Component molar weights provided separately (not in this module)

SIDE EFFECTS / STATE MUTATIONS
-------------------------------
- No state modifications; all operations pure (deterministic)
- No file I/O or external calls

PERFORMANCE NOTES
-----------------
- Enthalpy/Cp calculation: O(N_components) = negligible (< 0.01 ms)
- No expensive operations

ERROR HANDLING
--------------
- ConstantCpThermo assumes cp_i provided as non-negative scalars
- Returns float (Btu/lbmol); caller must validate sign and magnitude

VERSION / COMPATIBILITY
-----------------------
v1.0 (current):
    - ConstantCpThermo fixed; no future changes
    - Protocol interface stable; new providers must implement all methods

NOTES / KEY FEATURES
--------------------
Created: 2026-01-11 (America/New_York)

Units (project convention):
    Temperature: °F
    Pressure: psia
    Enthalpy: Btu/lbmol
    Heat Capacity: Btu/(lbmol·°F)

- ConstantCpThermo: Placeholder implementation
  * h = cp_mix * (T - T_ref)
  * cp_mix = sum(z_i * cp_i)
  * Not physically rigorous; for plumbing validation only
  
- Z-factor hook included for future high-pressure real-gas support

EXAMPLE USAGE
-------------
    from dynamic_distillation.thermo_model_v1 import ConstantCpThermo
    import numpy as np
    
    # Create placeholder thermo
    cp_i = {"Propane": 20.0, "n-Butane": 25.0, "n-Pentane": 30.0}  # Btu/(lbmol·°F)
    thermo = ConstantCpThermo(
        component_names=["Propane", "n-Butane", "n-Pentane"],
        cp_liq=np.array([20.0, 25.0, 30.0]),
        cp_vap=np.array([18.0, 22.0, 27.0]),
        T_ref_F=32.0
    )
    
    # Compute enthalpy
    x = np.array([0.3, 0.5, 0.2])  # Liquid composition
    h_liq = thermo.h_liq_btu_per_lbmol(T_f=120.0, P_psia=150.0, x=x)
    print(f"Liquid enthalpy @ 120°F: {h_liq} Btu/lbmol")
    
    # Compute heat capacity
    cp_liq = thermo.cp_liq_btu_per_lbmolF(T_f=120.0, P_psia=150.0, x=x)
    print(f"Liquid Cp: {cp_liq} Btu/(lbmol·°F)")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class ThermoModel(Protocol):
    def h_liq_btu_per_lbmol(self, T_f: float, P_psia: float, x: np.ndarray) -> float: ...
    def h_vap_btu_per_lbmol(self, T_f: float, P_psia: float, y: np.ndarray) -> float: ...
    def cp_liq_btu_per_lbmolF(self, T_f: float, P_psia: float, x: np.ndarray) -> float: ...
    def cp_vap_btu_per_lbmolF(self, T_f: float, P_psia: float, y: np.ndarray) -> float: ...
    def z_factor(self, T_f: float, P_psia: float, y: np.ndarray) -> float: ...


@dataclass(frozen=True)
class ConstantCpThermo:
    """
    Placeholder thermo:
      h = cp_mix * (T - Tref)
      cp_mix = sum(z_i * cp_i)

    This is NOT physically rigorous.
    It exists to get the energy-balance plumbing correct.
    """
    cp_liq_components: np.ndarray  # (Nc,) Btu/(lbmol*F)
    cp_vap_components: np.ndarray  # (Nc,) Btu/(lbmol*F)
    tref_f: float = 60.0

    def _cp_mix(self, z: np.ndarray, cps: np.ndarray) -> float:
        z = np.asarray(z, dtype=float)
        cps = np.asarray(cps, dtype=float)
        if z.ndim != 1 or cps.ndim != 1 or z.size != cps.size:
            raise ValueError("Composition and cp arrays must be 1-D and same length.")
        return float(np.dot(z, cps))

    def cp_liq_btu_per_lbmolF(self, T_f: float, P_psia: float, x: np.ndarray) -> float:
        return self._cp_mix(x, self.cp_liq_components)

    def cp_vap_btu_per_lbmolF(self, T_f: float, P_psia: float, y: np.ndarray) -> float:
        return self._cp_mix(y, self.cp_vap_components)

    def h_liq_btu_per_lbmol(self, T_f: float, P_psia: float, x: np.ndarray) -> float:
        cp = self.cp_liq_btu_per_lbmolF(T_f, P_psia, x)
        return cp * (float(T_f) - self.tref_f)

    def h_vap_btu_per_lbmol(self, T_f: float, P_psia: float, y: np.ndarray) -> float:
        cp = self.cp_vap_btu_per_lbmolF(T_f, P_psia, y)
        return cp * (float(T_f) - self.tref_f)

    def z_factor(self, T_f: float, P_psia: float, y: np.ndarray) -> float:
        # Placeholder: ideal-gas Z=1.0
        # Later: PR/SRK/DWSIM EOS here.
        return 1.0
