"""
Francis Weir hydraulics (US customary)

Implements:
    Q(ft^3/s) = 3.33 * Lw(ft) * h_ow(ft)^(3/2)
Molar flow:
    ML_out(lbmol/h) = Q * rho_L(lbmol/ft^3) * 3600
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
    weir_height_in: np.ndarray,
    weir_length_ft: np.ndarray,
    eps_h_ft: float = 1e-6,
) -> FrancisHydraulicsResult:
    n = len(ML_lbmol)
    h_ow = np.zeros(n)
    ML_out = np.zeros(n)

    for i in range(1, n - 1):  # stages 2..N-1 (exclude condenser and reboiler)
        rho = rhoL_lbmol_ft3[i]
        if rho <= 0.0:
            raise ValueError(f"Invalid rhoL at stage {i+1}")

        A = active_area_ft2[i]
        V = ML_lbmol[i] / rho
        h_total = V / A
        h_w = weir_height_in[i] / INCHES_PER_FOOT
        h = max(h_total - h_w, eps_h_ft)

        Q_ft3_s = FRANCIS_C * weir_length_ft[i] * h ** 1.5
        ML_out[i] = Q_ft3_s * rho * SEC_PER_HOUR
        h_ow[i] = h

    return FrancisHydraulicsResult(h_ow=h_ow, ML_lbmolph=ML_out)
