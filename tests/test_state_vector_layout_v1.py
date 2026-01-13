"""
tests/test_state_vector_layout_v1.py

Updated: 2026-01-12  (America/New_York)

Rationale
---------
If a stage has essentially zero vapor holdup (e.g., condenser stage 0 in the template),
the vapor composition y is physically undefined. The unpack() convention in
StateVectorLayout is to return a row of zeros for such stages.

Therefore, we only require y_tray to match ColumnSpec.y0 on stages where MV_tot_tray
is meaningfully > 0.
"""

from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout

import numpy as np


def test_state_vector_layout_pack_unpack_roundtrip_template():
    case = load_case_from_excel("distillation_column_template.xlsx")
    col = build_column_spec_from_case(case)

    layout = StateVectorLayout(
        n_stages=col.n_stages,
        n_components=col.n_components,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        epsilon_lbmol=1e-8,
    )

    y0 = layout.pack_y0(col)
    assert y0.size == layout.n_states()

    u = layout.unpack(y0)

    # Basic shapes
    assert u["tray_L"].shape == (col.n_stages, col.n_components)
    assert u["tray_V"].shape == (col.n_stages, col.n_components)
    assert u["x_tray"].shape == (col.n_stages, col.n_components)
    assert u["y_tray"].shape == (col.n_stages, col.n_components)

    # x should always round-trip (liquid holdup is always present)
    max_x_abs_err = float(np.max(np.abs(u["x_tray"] - col.x0)))
    assert max_x_abs_err < 1e-6

    # y is only meaningful on stages with non-trivial vapor holdup
    mv = u["MV_tot_tray"]
    mask = mv > 1e-10  # effectively "has vapor"

    if np.any(mask):
        max_y_abs_err = float(np.max(np.abs(u["y_tray"][mask] - col.y0[mask])))
        assert max_y_abs_err < 1e-6

    # For stages with ~zero vapor holdup, y_tray is conventionally all zeros
    if np.any(~mask):
        assert float(np.max(np.abs(u["y_tray"][~mask]))) < 1e-12
