"""
stage_hydraulics_francis_v1.py

Dynamic Distillation - Francis-Weir Tray Hydraulics

PURPOSE
-------
Compute tray liquid outflow from tray holdup and geometry using a
Francis-weir formulation. Used by hydraulic pressure/flow closures.

INPUTS
------
compute_francis_weir_liquid_outflow(...):
- stage liquid holdup
- liquid density
- active area
- weir height and weir length
- optional numerical floor/epsilon controls

OUTPUTS
-------
FrancisHydraulicsResult:
- per-stage over-weir head
- per-stage liquid outflow (lbmol/h)

KEY DEPENDENCIES
----------------
- numpy

ASSUMPTIONS & CONSTRAINTS
-------------------------
- Inputs must be physically meaningful (positive geometry/density where used).
- Internal guards prevent non-physical negative flows.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass

FRANCIS_C = 3.33  # US customary
INCHES_PER_FOOT = 12.0
SEC_PER_HOUR = 3600.0


@dataclass
class FrancisHydraulicsResult:
    h_ow: np.ndarray
    ML_lbmolph: np.ndarray


def compute_francis_weir_liquid_outflow(
    *,
    ML_lbmol: np.ndarray,
    rhoL_lbmol_ft3: np.ndarray,
    active_area_ft2: np.ndarray,
    holdup_area_ft2: np.ndarray | None = None,
    weir_height_in: np.ndarray,
    weir_length_ft: np.ndarray,
    c_multiplier: np.ndarray | None = None,
    eps_h_ft: float = 1e-6,
) -> FrancisHydraulicsResult:
    n = len(ML_lbmol)
    h_ow = np.zeros(n)
    ML_out = np.zeros(n)

    c_arr = np.ones(n, dtype=float)
    if c_multiplier is not None:
        c_arr = np.asarray(c_multiplier, dtype=float).reshape((n,))
    holdup_area_arr = np.asarray(active_area_ft2, dtype=float).reshape((n,))
    if holdup_area_ft2 is not None:
        holdup_area_arr = np.asarray(holdup_area_ft2, dtype=float).reshape((n,))

    for i in range(1, n - 1):  # stages 2..N-1 (exclude condenser and reboiler)
        rho = rhoL_lbmol_ft3[i]
        if rho <= 0.0:
            raise ValueError(f"Invalid rhoL at stage {i+1}")
        c = c_arr[i]
        if (not np.isfinite(c)) or c <= 0.0:
            raise ValueError(f"Invalid hydraulic C multiplier at stage {i+1}")

        A = active_area_ft2[i]
        A_hold = holdup_area_arr[i]
        if A_hold <= 0.0:
            raise ValueError(f"Invalid hydraulic holdup area at stage {i+1}")
        V = ML_lbmol[i] / rho
        h_total = V / A_hold
        h_w = weir_height_in[i] / INCHES_PER_FOOT
        h = max(h_total - h_w, eps_h_ft)

        Q_ft3_s = FRANCIS_C * c * weir_length_ft[i] * h ** 1.5
        ML_out[i] = Q_ft3_s * rho * SEC_PER_HOUR
        h_ow[i] = h

    return FrancisHydraulicsResult(h_ow=h_ow, ML_lbmolph=ML_out)
