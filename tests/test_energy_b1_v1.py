# tests/test_energy_b1_v1.py
"""
Header:
  Created: 2026-01-11 15:xx (America/New_York)
Purpose:
  Smoke tests for Module 6 Option B1 energy holdup states.
"""

from __future__ import annotations

import numpy as np

from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout


class _TinyCol:
    def __init__(self):
        self.n_stages = 2
        self.n_components = 2
        self.ML0_lbmol = np.array([5.0, 6.0], dtype=float)
        self.MV0_lbmol = np.array([1.0, 2.0], dtype=float)
        self.x0 = np.array([[0.8, 0.2], [0.3, 0.7]], dtype=float)
        self.y0 = np.array([[0.9, 0.1], [0.4, 0.6]], dtype=float)
        self.T0_F = np.array([100.0, 120.0], dtype=float)
        self.P0_psia = np.array([200.0, 210.0], dtype=float)
        self.specs = {"Condenser Duty (Btu/h)": -1000.0, "Reboiler Duty (Btu/h)": 2000.0}


def test_layout_energy_pack_unpack_shapes():
    col = _TinyCol()
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_energy=True,
    )
    y0 = layout.pack_y0(col)
    u = layout.unpack(y0)

    assert u["tray_EL_BTU"].shape == (2,)
    assert u["tray_EV_BTU"].shape == (2,)
    assert np.all(u["tray_EL_BTU"] != 0.0)
    assert np.all(u["tray_EV_BTU"] != 0.0)
