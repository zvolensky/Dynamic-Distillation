"""
test_state_vector_layout_v1.py

Dynamic Distillation - State Vector Layout Tests

PURPOSE
-------
Verify pack/unpack invariants and edge-case conventions in
`state_vector_layout_v1`, especially around near-zero vapor-holdup stages.

SCOPE
-----
- roundtrip consistency against template-derived ColumnSpec
- behavior expectations for undefined vapor composition rows

KEY DEPENDENCIES
----------------
- state_vector_layout_v1
- excel_case_loader_v1 / column_spec_builder_v1
- numpy
"""


from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.column_spec_builder_v1 import (
    ColumnSpec,
    HeatDuties,
    SimulationSettings,
    StreamSpecNormalized,
    build_column_spec_from_case,
)
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

    # x is only meaningful on stages with non-trivial liquid holdup
    ml = u["ML_tot_tray"]
    mask_x = ml > 1e-10  # effectively "has liquid"

    if np.any(mask_x):
        max_x_abs_err = float(np.max(np.abs(u["x_tray"][mask_x] - col.x0[mask_x])))
        assert max_x_abs_err < 1e-6

    # For stages with ~zero liquid holdup, x_tray is conventionally all zeros
    if np.any(~mask_x):
        assert float(np.max(np.abs(u["x_tray"][~mask_x]))) < 1e-12

    # y is only meaningful on stages with non-trivial vapor holdup
    mv = u["MV_tot_tray"]
    mask = mv > 1e-10  # effectively "has vapor"

    if np.any(mask):
        max_y_abs_err = float(np.max(np.abs(u["y_tray"][mask] - col.y0[mask])))
        assert max_y_abs_err < 1e-6

    # For stages with ~zero vapor holdup, y_tray is conventionally all zeros
    if np.any(~mask):
        assert float(np.max(np.abs(u["y_tray"][~mask]))) < 1e-12


def _make_tiny_column_with_top_holdup(top_holdup_lbmol: float) -> ColumnSpec:
    N, Nc = 2, 2
    x0 = np.array([[0.2, 0.8], [0.3, 0.7]], dtype=float)
    y0 = np.array([[0.5, 0.5], [0.4, 0.6]], dtype=float)

    return ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={
            "Number of Stages": 2,
            "Number of Components": 2,
            "Timestep (sec)": 1.0,
            "Simulation Length (min)": 0.1,
            "Log Frequency (timesteps)": 1,
            "Top Accumulator Holdup (lbmol)": float(top_holdup_lbmol),
        },
        T_f=np.array([100.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 210.0], dtype=float),
        V_lbmolph=np.array([10.0, 10.0], dtype=float),
        L_lbmolph=np.array([10.0, 10.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )


def test_top_accumulator_holdup_initialization():
    top_holdup = 100.0
    col = _make_tiny_column_with_top_holdup(top_holdup)
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=True, include_bottom=True, include_vapor=True)

    y0 = layout.pack_y0(col)
    sl = layout.slices()

    top_L = y0[sl["top_L"]]
    assert abs(float(np.sum(top_L)) - top_holdup) < 1e-9

    x_top = top_L / max(float(np.sum(top_L)), 1e-300)
    assert np.allclose(x_top, col.x0[0, :], atol=1e-12)


def test_pack_y0_honors_explicit_restart_energy_state():
    col = _make_tiny_column_with_top_holdup(100.0)
    object.__setattr__(col, "tray_EL0_BTU", np.array([101.0, 102.0], dtype=float))
    object.__setattr__(col, "tray_EV0_BTU", np.array([201.0, 202.0], dtype=float))
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_energy=True,
    )

    y0 = layout.pack_y0(col)
    sl = layout.slices()

    assert np.allclose(y0[sl["tray_EL_BTU"]], np.array([101.0, 102.0], dtype=float))
    assert np.allclose(y0[sl["tray_EV_BTU"]], np.array([201.0, 202.0], dtype=float))


def test_top_accumulator_uses_distillate_composition():
    N, Nc = 2, 2
    x0 = np.array([[0.2, 0.8], [0.3, 0.7]], dtype=float)
    y0 = np.array([[0.5, 0.5], [0.4, 0.6]], dtype=float)

    dist_comp = {"A": 3.0, "B": 1.0}
    streams = {
        "Distillate": StreamSpecNormalized(
            name="Distillate",
            stage_1based=1,
            total_molar_flow_lbmolph=40.0,
            component_molar_flows_lbmolph=dist_comp,
        )
    }

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={
            "Number of Stages": 2,
            "Number of Components": 2,
            "Timestep (sec)": 1.0,
            "Simulation Length (min)": 0.1,
            "Log Frequency (timesteps)": 1,
            "Top Accumulator Holdup (lbmol)": 100.0,
        },
        T_f=np.array([100.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 210.0], dtype=float),
        V_lbmolph=np.array([10.0, 10.0], dtype=float),
        L_lbmolph=np.array([10.0, 10.0], dtype=float),
        M_L_lbmol=np.array([0.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams=streams,
    )

    layout = StateVectorLayout(n_stages=N, n_components=Nc, include_top=True, include_bottom=True, include_vapor=True)
    y_init = layout.pack_y0(col)
    sl = layout.slices()
    top_L = y_init[sl["top_L"]]

    z_top = top_L / max(float(np.sum(top_L)), 1e-300)
    assert np.allclose(z_top, np.array([0.75, 0.25], dtype=float), atol=1e-12)


def test_bottom_holdup_initialization_from_specs():
    N, Nc = 2, 2
    x0 = np.array([[0.2, 0.8], [0.3, 0.7]], dtype=float)
    y0 = np.array([[0.5, 0.5], [0.4, 0.6]], dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={
            "Number of Stages": 2,
            "Number of Components": 2,
            "Timestep (sec)": 1.0,
            "Simulation Length (min)": 0.1,
            "Log Frequency (timesteps)": 1,
            "Bottom Holdup (lbmol)": 200.0,
        },
        T_f=np.array([100.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 210.0], dtype=float),
        V_lbmolph=np.array([10.0, 10.0], dtype=float),
        L_lbmolph=np.array([10.0, 10.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(n_stages=N, n_components=Nc, include_top=True, include_bottom=True, include_vapor=True)
    y_init = layout.pack_y0(col)
    sl = layout.slices()
    bottom_L = y_init[sl["bottom_L"]]

    assert abs(float(np.sum(bottom_L)) - 200.0) < 1e-9
    z_bottom = bottom_L / max(float(np.sum(bottom_L)), 1e-300)
    assert np.allclose(z_bottom, col.x0[-1, :], atol=1e-12)


def test_pack_y0_honors_explicit_boundary_vapor_restart_state():
    N, Nc = 2, 2
    x0 = np.array([[0.2, 0.8], [0.3, 0.7]], dtype=float)
    y0 = np.array([[0.5, 0.5], [0.4, 0.6]], dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={
            "Number of Stages": 2,
            "Number of Components": 2,
            "Timestep (sec)": 1.0,
            "Simulation Length (min)": 0.1,
            "Log Frequency (timesteps)": 1,
        },
        T_f=np.array([100.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 210.0], dtype=float),
        V_lbmolph=np.array([10.0, 10.0], dtype=float),
        L_lbmolph=np.array([10.0, 10.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
        top_V0_lbmol=np.array([2.0, 3.0], dtype=float),
        bottom_V0_lbmol=np.array([4.0, 1.0], dtype=float),
    )

    layout = StateVectorLayout(n_stages=N, n_components=Nc, include_top=True, include_bottom=True, include_vapor=True)
    y_init = layout.pack_y0(col)
    sl = layout.slices()

    assert np.allclose(y_init[sl["top_V"]], np.array([2.0, 3.0], dtype=float))
    assert np.allclose(y_init[sl["bottom_V"]], np.array([4.0, 1.0], dtype=float))
