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

    # Tray mole fractions should match the ColumnSpec inputs closely.
    # Expect tiny floating-point error because totals are re-summed from component holdups.
    max_x_abs_err = float(np.max(np.abs(u["x_tray"] - col.x0)))
    max_y_abs_err = float(np.max(np.abs(u["y_tray"] - col.y0)))

    assert max_x_abs_err < 1e-6
    assert max_y_abs_err < 1e-6