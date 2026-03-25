"""
test_column_rhs_v1.py

Dynamic Distillation - Column RHS Unit Tests

PURPOSE
-------
Exercise `column_rhs_v1` derivative and diagnostic behavior across mass,
pressure, thermo, condenser/reboiler, and controller-facing signal paths.

SCOPE
-----
- ColumnInputs/BoundaryFlows handling and helper utilities
- Condenser/reboiler closures, hydraulics, feed handling, and diagnostics
- Regression checks for optional model features and edge cases

KEY DEPENDENCIES
----------------
- dynamic_distillation.column_rhs_v1
- ColumnSpec fixtures and StateVectorLayout
- numpy/math test utilities
"""


import numpy as np
import pytest

import dynamic_distillation.column_rhs_v1 as rhs_module
from dynamic_distillation.column_spec_builder_v1 import (
    ColumnSpec,
    ColumnGeometry,
    ColumnGeometrySection,
    HeatDuties,
    SimulationSettings,
    StreamSpecNormalized,
)
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.column_rhs_v1 import (
    column_rhs,
    ColumnInputs,
    BoundaryFlows,
    _feed_component_rates_lbmolps,
    _feed_enthalpy_rate_btu_per_s,
    _bubble_point_T_F,
    _condenser_mass_split_from_duty,
    _compute_top_drum_pressure_psia,
    _pressure_profile_hydraulic_psia,
    _resolve_condenser_duty_btu_per_h,
)
from dynamic_distillation.thermo_model_v1 import ConstantCpThermo
from dynamic_distillation.stage_hydraulics_francis_v1 import compute_francis_weir_liquid_outflow

import math


def _make_tiny_column() -> ColumnSpec:
    N, Nc = 2, 2
    x0 = np.array([[0.8, 0.2], [0.3, 0.7]], dtype=float)
    y0 = np.array([[0.9, 0.1], [0.4, 0.6]], dtype=float)

    streams = {}

    return ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 2, "Number of Components": 2, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 210.0], dtype=float),
        V_lbmolph=np.array([10.0, 10.0], dtype=float),
        L_lbmolph=np.array([10.0, 10.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams=streams,
    )


def test_rhs_shapes_and_no_crash():
    col = _make_tiny_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=True, include_bottom=True, include_vapor=True)
    y0 = layout.pack_y0(col)

    dydt, diag = column_rhs(0.0, y0, col, layout, inputs=ColumnInputs())
    assert dydt.shape == y0.shape
    assert "P_psia_diag" in diag
    assert diag["P_psia_diag"].shape == (2,)


def test_rhs_zero_flows_gives_zero_derivatives():
    col = _make_tiny_column()

    col2 = ColumnSpec(**{**col.__dict__,
        "V_lbmolph": np.array([0.0, 0.0], dtype=float),
        "L_lbmolph": np.array([0.0, 0.0], dtype=float),
    })

    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=True, include_bottom=True, include_vapor=True)
    y0 = layout.pack_y0(col2)

    inputs = ColumnInputs(boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0))
    dydt, _ = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    assert float(np.max(np.abs(dydt))) < 1e-12


def test_energy_enabled_adds_temperature_derivatives():
    col = _make_tiny_column()

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=True,
        include_vapor=True,
        include_temperature=True,
    )
    y0 = layout.pack_y0(col)

    thermo = ConstantCpThermo(
        cp_liq_components=np.array([30.0, 25.0]),
        cp_vap_components=np.array([20.0, 18.0]),
        tref_f=60.0,
    )
    dydt, diag = column_rhs(0.0, y0, col, layout, inputs=ColumnInputs(thermo=thermo))

    # Temperature derivative slices must exist and be finite
    sl = layout.slices()
    dT = dydt[sl["tray_T_f"]]
    assert dT.shape == (2,)
    assert np.all(np.isfinite(dT))
    assert "dT_tray_F_per_s" in diag


def test_condenser_temperature_closure_is_reference_invariant():
    col = _make_tiny_column()

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=True,
    )
    y0 = layout.pack_y0(col)

    class FlatThermo:
        def h_liq_btu_per_lbmol(self, T_f, P_psia, x):
            return 100.0

        def h_vap_btu_per_lbmol(self, T_f, P_psia, y):
            return 100.0

        def cp_liq_btu_per_lbmolF(self, T_f, P_psia, x):
            return 25.0

        def cp_vap_btu_per_lbmolF(self, T_f, P_psia, y):
            return 20.0

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=6.0, boilup_lbmolph=10.0),
        thermo=FlatThermo(),
    )
    dydt, _diag = column_rhs(0.0, y0, col, layout, inputs=inputs)

    sl = layout.slices()
    dT = dydt[sl["tray_T_f"]].reshape((2,))

    # With identical stream enthalpies and zero duties, condenser temperature
    # should not change due only to holdup redistribution.
    assert abs(float(dT[0])) < 1e-12


def test_total_condenser_top_drum_balance():
    col = _make_tiny_column()

    col2 = ColumnSpec(**{**col.__dict__,
        "V_lbmolph": np.array([12.0, 12.0], dtype=float),
        "L_lbmolph": np.array([6.0, 6.0], dtype=float),
        "streams": {},
    })
    object.__setattr__(col2, "top_L0_lbmol", np.array([4.0, 1.0], dtype=float))

    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=True, include_bottom=True, include_vapor=True)
    y0 = layout.pack_y0(col2)

    inputs = ColumnInputs(boundary=BoundaryFlows(reflux_lbmolph=6.0, boilup_lbmolph=12.0))
    dydt, _ = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    sl = layout.slices()
    top_L = y0[sl["top_L"]]
    x_topL = top_L / max(float(np.sum(top_L)), 1e-300)

    u0 = layout.unpack(y0)
    y_in0 = u0["y_tray"][1, :]
    x_cond0 = u0["x_tray"][0, :]

    reflux_s = 6.0 / 3600.0
    boilup_s = 12.0 / 3600.0

    # Condensed liquid first fills condenser tray state and is then transferred
    # to reflux-drum liquid with condenser-tray composition.
    expected_d_top = boilup_s * x_cond0 - reflux_s * x_topL
    d_top = dydt[sl["top_L"]].reshape((2,))
    assert np.allclose(d_top, expected_d_top, atol=1e-12)

    d_tray_L = dydt[sl["tray_L"]].reshape((2, 2))
    expected_d_cond = boilup_s * (y_in0 - x_cond0)
    assert np.allclose(d_tray_L[0, :], expected_d_cond, atol=1e-12)


def test_top_drum_psv_relief_removes_vapor_and_reports_diagnostics():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 0.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()

    y0[sl["top_L"]] = np.array([1.0, 0.0], dtype=float)
    y0[sl["top_V"]] = np.array([10.0, 0.0], dtype=float)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        pressure_model="spec",
        top_drum_vapor_volume_ft3=240.5,
        enable_top_drum_psv=True,
        top_drum_psv_setpoint_psia=200.0,
        top_drum_psv_gain_lbmolps_per_psi=0.1,
        top_drum_psv_max_vent_lbmolps=0.2,
    )
    dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)
    d_top_V = np.asarray(dydt[sl["top_V"]], dtype=float).reshape((2,))

    # With no feed/condensation/draw terms active, top-vapor derivative should be
    # exactly the PSV vent term.
    assert np.allclose(d_top_V, np.array([-0.2, 0.0], dtype=float), atol=1e-12)
    assert "V_psv_top_lbmolph" in diag
    assert "PSV_open_flag" in diag
    assert "PSV_setpoint_psia" in diag
    assert "PSV_pv_psia" in diag
    assert abs(float(np.asarray(diag["V_psv_top_lbmolph"], dtype=float).reshape((-1,))[0]) - 720.0) < 1e-9
    assert float(np.asarray(diag["PSV_open_flag"], dtype=float).reshape((-1,))[0]) == 1.0
    assert abs(float(np.asarray(diag["PSV_setpoint_psia"], dtype=float).reshape((-1,))[0]) - 200.0) < 1e-12
    assert float(np.asarray(diag["PSV_pv_psia"], dtype=float).reshape((-1,))[0]) > 200.0


def test_hydraulics_uses_thermo_density():
    # 3-stage, 1-component column with weir hydraulics enabled.
    N, Nc = 3, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    diam_ft = np.full(N, 2.0, dtype=float)
    spacing_ft = np.full(N, 1.0, dtype=float)
    void_frac = np.full(N, 0.5, dtype=float)
    area_ft2 = math.pi * (0.5 * diam_ft) ** 2
    vapor_vol = area_ft2 * spacing_ft * void_frac

    weir_h_in = np.full(N, 6.0, dtype=float)
    weir_L_ft = np.full(N, 1.0, dtype=float)
    aaf = np.full(N, 1.0, dtype=float)
    active_area_ft2 = area_ft2 * aaf

    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=6.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=diam_ft,
        tray_spacing_ft_per_stage=spacing_ft,
        gas_void_frac_per_stage=void_frac,
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=vapor_vol,
        weir_height_in_per_stage=weir_h_in,
        weir_length_ft_per_stage=weir_L_ft,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area_ft2,
    )

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([4.0, 4.0, 4.0], dtype=float),
        M_V_lbmol=np.array([0.0, 0.0, 0.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
        geometry=geom,
    )

    class DensityThermo:
        def __init__(self, mapping):
            self.mapping = mapping

        def liquid_density_lbmol_ft3(self, T_F, P_psia, x):
            return float(self.mapping[round(float(T_F), 3)])

    thermo = DensityThermo({100.0: 1.0, 110.0: 2.0, 120.0: 3.0})

    layout = StateVectorLayout(n_stages=N, n_components=Nc, include_top=False, include_bottom=False, include_vapor=True)
    y0_state = layout.pack_y0(col)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=thermo,
        reboiler_mode="specified",
        reboiler_equilibrium=False,
    )
    dydt, _ = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    sl = layout.slices()
    d_tray_L = dydt[sl["tray_L"]].reshape((N, Nc))

    # Expected weir outflow for stage 2 uses rho=2.0 (from thermo by T=110F).
    rho_arr = np.array([1.0, 2.0, 3.0], dtype=float)
    ML_tray = np.array([4.0, 4.0, 4.0], dtype=float)
    hyd = compute_francis_weir_liquid_outflow(
        ML_lbmol=ML_tray,
        rhoL_lbmol_ft3=rho_arr,
        active_area_ft2=active_area_ft2,
        weir_height_in=weir_h_in,
        weir_length_ft=weir_L_ft,
    )
    expected_L_out_s = float(hyd.ML_lbmolph[1]) / 3600.0

    # With zero reflux, L_in at stage 2 is 0, so dML/dt = -L_out.
    assert np.isclose(-float(d_tray_L[1, 0]), expected_L_out_s, rtol=1e-6, atol=1e-12)


def test_huang_htc_liquid_hydraulics_uses_holdup_over_tau():
    N, Nc = 3, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    diam_ft = np.full(N, 2.0, dtype=float)
    spacing_ft = np.full(N, 1.0, dtype=float)
    void_frac = np.full(N, 0.5, dtype=float)
    area_ft2 = math.pi * (0.5 * diam_ft) ** 2
    vapor_vol = area_ft2 * spacing_ft * void_frac
    weir_h_in = np.full(N, 6.0, dtype=float)
    weir_L_ft = np.full(N, 1.0, dtype=float)
    aaf = np.full(N, 1.0, dtype=float)
    active_area_ft2 = area_ft2 * aaf

    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=6.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=diam_ft,
        tray_spacing_ft_per_stage=spacing_ft,
        gas_void_frac_per_stage=void_frac,
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=vapor_vol,
        weir_height_in_per_stage=weir_h_in,
        weir_length_ft_per_stage=weir_L_ft,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area_ft2,
    )

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([4.0, 4.0, 4.0], dtype=float),
        M_V_lbmol=np.array([0.0, 0.0, 0.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
        geometry=geom,
    )

    layout = StateVectorLayout(n_stages=N, n_components=Nc, include_top=False, include_bottom=False, include_vapor=True)
    y0_state = layout.pack_y0(col)
    tau_htc_sec = 8.0

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        liquid_hydraulic_model="huang-htc",
        liquid_hydraulic_htc_sec=tau_htc_sec,
        reboiler_mode="specified",
        reboiler_equilibrium=False,
    )
    dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    sl = layout.slices()
    d_tray_L = dydt[sl["tray_L"]].reshape((N, Nc))
    expected_internal_l_out_s = 4.0 / tau_htc_sec

    assert np.isclose(-float(d_tray_L[1, 0]), expected_internal_l_out_s, rtol=1e-9, atol=1e-12)
    assert float(np.asarray(diag["liquid_hydraulic_model_huang_htc"], dtype=float).reshape((-1,))[0]) == 1.0
    assert np.isclose(
        float(np.asarray(diag["L_out_hyd_lbmolph"], dtype=float).reshape((N,))[1]),
        expected_internal_l_out_s * 3600.0,
        rtol=1e-9,
        atol=1e-9,
    )


def test_hydraulic_pressure_relaxation_blends_with_previous_profile(monkeypatch):
    N, Nc = 3, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    area_ft2 = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area_ft2,
    )

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 205.0, 210.0], dtype=float),
        V_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([4.0, 4.0, 4.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
        geometry=geom,
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    p_raw = np.array([230.0, 220.0, 210.0], dtype=float)

    def _fake_pressure_profile(**_kwargs):
        return p_raw.copy()

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        pressure_model="hydraulic",
        vapor_holdup_relaxation_sec=4.0,
        P_tray_prev=np.array([200.0, 200.0, 200.0], dtype=float),
    )
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    p_used = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((N,))
    p_logged_raw = np.asarray(diag["P_psia_hyd_raw"], dtype=float).reshape((N,))
    alpha = float(np.asarray(diag["P_psia_hyd_relax_alpha"], dtype=float).reshape((-1,))[0])

    # Open-loop hydraulic pressure blending preserves the bottom anchor while
    # low-passing tray-to-tray increments.
    expected = np.array([215.0, 212.5, 210.0], dtype=float)
    assert np.allclose(p_logged_raw, p_raw, atol=1e-12)
    assert np.isclose(alpha, 0.25, atol=1e-12)
    assert np.allclose(p_used, expected, atol=1e-12)


def test_hydraulic_pressure_relaxation_preserves_explicit_top_anchor(monkeypatch):
    N, Nc = 3, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    area_ft2 = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area_ft2,
    )

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 205.0, 210.0], dtype=float),
        V_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([4.0, 4.0, 4.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
        geometry=geom,
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    p_raw = np.array([230.0, 220.0, 210.0], dtype=float)

    def _fake_pressure_profile(**_kwargs):
        return p_raw.copy()

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        pressure_model="hydraulic",
        pressure_top_anchor_psia=230.0,
        vapor_holdup_relaxation_sec=4.0,
        P_tray_prev=np.array([200.0, 200.0, 200.0], dtype=float),
    )
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    p_used = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((N,))
    expected = np.array([230.0, 227.5, 225.0], dtype=float)
    assert np.allclose(p_used, expected, atol=1e-12)


def test_hydraulic_pressure_profile_respects_top_floor():
    N, Nc = 5, 1
    diam_ft = np.full(N, 2.0, dtype=float)
    spacing_ft = np.full(N, 1.0, dtype=float)
    void_frac = np.full(N, 0.5, dtype=float)
    area_ft2 = np.full(N, 1.0, dtype=float)
    vapor_vol = area_ft2 * spacing_ft * void_frac
    weir_h_in = np.zeros(N, dtype=float)
    weir_L_ft = np.full(N, 1.0, dtype=float)
    aaf = np.full(N, 1.0, dtype=float)
    active_area_ft2 = np.full(N, 1.0, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=diam_ft,
        tray_spacing_ft_per_stage=spacing_ft,
        gas_void_frac_per_stage=void_frac,
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=vapor_vol,
        weir_height_in_per_stage=weir_h_in,
        weir_length_ft_per_stage=weir_L_ft,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area_ft2,
    )
    T_F = np.full(N, 120.0, dtype=float)
    V_in_lbmolps = np.array([0.0, 600.0, 600.0, 600.0, 600.0], dtype=float)
    y_tray = np.ones((N, Nc), dtype=float)
    x_tray = np.ones((N, Nc), dtype=float)
    Z_vap = np.ones(N, dtype=float)

    P = _pressure_profile_hydraulic_psia(
        P_bottom_psia=200.0,
        T_F=T_F,
        V_in_lbmolps=V_in_lbmolps,
        y_tray=y_tray,
        x_tray=x_tray,
        Z_vap=Z_vap,
        geom=geom,
        h_ow_ft=None,
        rhoL_lbmol_ft3=None,
        mw_components=np.array([44.0], dtype=float),
        dry_tray_K=500.0,
        P_top_spec_psia=200.0,
        min_pressure_psia=14.7,
        max_dp_per_stage_psia=50.0,
    )

    assert P.shape == (N,)
    # Top-floor policy is max(min_pressure, 0.5 * P_top_spec) = 100 psia.
    assert float(np.min(P)) >= 100.0 - 1e-9
    # Pressure should increase from top to bottom.
    assert np.all(np.diff(P) >= -1e-9)


def test_hydraulic_pressure_profile_can_use_top_anchor():
    N, Nc = 5, 1
    diam_ft = np.full(N, 2.0, dtype=float)
    spacing_ft = np.full(N, 1.0, dtype=float)
    void_frac = np.full(N, 0.5, dtype=float)
    area_ft2 = np.full(N, 1.0, dtype=float)
    vapor_vol = area_ft2 * spacing_ft * void_frac
    weir_h_in = np.zeros(N, dtype=float)
    weir_L_ft = np.full(N, 1.0, dtype=float)
    aaf = np.full(N, 1.0, dtype=float)
    active_area_ft2 = np.full(N, 1.0, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=diam_ft,
        tray_spacing_ft_per_stage=spacing_ft,
        gas_void_frac_per_stage=void_frac,
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=vapor_vol,
        weir_height_in_per_stage=weir_h_in,
        weir_length_ft_per_stage=weir_L_ft,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area_ft2,
    )

    T_F = np.full(N, 120.0, dtype=float)
    V_in_lbmolps = np.array([0.0, 2.0, 2.0, 2.0, 2.0], dtype=float)
    y_tray = np.ones((N, Nc), dtype=float)
    x_tray = np.ones((N, Nc), dtype=float)
    Z_vap = np.ones(N, dtype=float)

    P = _pressure_profile_hydraulic_psia(
        P_bottom_psia=230.0,
        T_F=T_F,
        V_in_lbmolps=V_in_lbmolps,
        y_tray=y_tray,
        x_tray=x_tray,
        Z_vap=Z_vap,
        geom=geom,
        h_ow_ft=None,
        rhoL_lbmol_ft3=None,
        mw_components=np.array([44.0], dtype=float),
        dry_tray_K=5.0,
        P_top_spec_psia=220.0,
        P_top_anchor_psia=220.0,
        min_pressure_psia=14.7,
        max_dp_per_stage_psia=50.0,
    )

    assert P.shape == (N,)
    # Top should track requested anchor (within numerical tolerance).
    assert abs(float(P[0]) - 220.0) < 1e-6
    # Pressure should increase from top to bottom.
    assert np.all(np.diff(P) >= -1e-9)


def test_total_condense_mode_applies_duty_trim_even_without_provider():
    col = _make_tiny_column()
    N = int(col.n_stages)
    Nc = int(col.n_components)
    tray_T = np.asarray(col.T_f, dtype=float).reshape((N,))
    P_tray = np.asarray(col.P_psia, dtype=float).reshape((N,))
    V_in = np.zeros(N, dtype=float)
    y_in = np.full((N, Nc), 1.0 / max(Nc, 1), dtype=float)

    q_used, q_calc, t_bub, mode = _resolve_condenser_duty_btu_per_h(
        col=col,
        inputs=ColumnInputs(
            condenser_duty_mode="total-condense",
            condenser_duty_btu_per_h=-100.0,
            condenser_duty_trim_btu_per_h=-25.0,
            thermo_provider=None,
        ),
        N=N,
        tray_T_F=tray_T,
        P_tray_psia=P_tray,
        V_in_lbmolps=V_in,
        y_in=y_in,
        epsilon_lbmol=1e-12,
    )

    assert mode == "total-condense"
    assert q_calc is None
    assert t_bub is None
    assert abs(float(q_used) + 125.0) < 1e-12


def test_specified_mode_ignores_duty_trim():
    col = _make_tiny_column()
    N = int(col.n_stages)
    Nc = int(col.n_components)
    tray_T = np.asarray(col.T_f, dtype=float).reshape((N,))
    P_tray = np.asarray(col.P_psia, dtype=float).reshape((N,))
    V_in = np.zeros(N, dtype=float)
    y_in = np.full((N, Nc), 1.0 / max(Nc, 1), dtype=float)

    q_used, q_calc, t_bub, mode = _resolve_condenser_duty_btu_per_h(
        col=col,
        inputs=ColumnInputs(
            condenser_duty_mode="specified",
            condenser_duty_btu_per_h=-100.0,
            condenser_duty_trim_btu_per_h=-25.0,
            thermo_provider=None,
        ),
        N=N,
        tray_T_F=tray_T,
        P_tray_psia=P_tray,
        V_in_lbmolps=V_in,
        y_in=y_in,
        epsilon_lbmol=1e-12,
    )

    assert mode == "specified"
    assert q_calc is None
    assert t_bub is None
    assert abs(float(q_used) + 100.0) < 1e-12


def test_total_condense_mass_split_responds_to_positive_trim(monkeypatch):
    col = _make_tiny_column()
    N = int(col.n_stages)
    Nc = int(col.n_components)
    tray_T = np.asarray(col.T_f, dtype=float).reshape((N,))
    P_tray = np.asarray(col.P_psia, dtype=float).reshape((N,))
    V_in = np.array([1.0, 0.0], dtype=float)
    y_in = np.full((N, Nc), 1.0 / max(Nc, 1), dtype=float)
    top_V = np.array([0.2, 0.2], dtype=float)

    def _fake_total_cond_duty(**kwargs):
        # Full condensation of 1 lbmol/s requires -3600 BTU/h here.
        return -3600.0, 100.0

    monkeypatch.setattr(rhs_module, "_compute_total_condenser_duty_btu_per_h", _fake_total_cond_duty)

    v_cond_in, v_to_top, v_cond_top, q_used, q_req, mode = _condenser_mass_split_from_duty(
        col=col,
        inputs=ColumnInputs(
            condenser_duty_mode="total-condense",
            condenser_duty_btu_per_h=-100.0,
            condenser_duty_trim_btu_per_h=+1800.0,  # less cooling than full-condense requirement
            thermo_provider=object(),
        ),
        tray_T_F=tray_T,
        P_tray_psia=P_tray,
        V_in_lbmolps=V_in,
        y_in=y_in,
        top_V=top_V,
        epsilon_lbmol=1e-12,
    )

    assert mode == "total-condense"
    assert abs(float(q_req) + 3600.0) < 1e-12
    assert abs(float(q_used) + 1800.0) < 1e-12
    # Strict total condenser: no vapor slip to the top drum.
    assert abs(float(v_cond_in) - 1.0) < 1e-12
    assert abs(float(v_to_top) - 0.0) < 1e-12
    assert abs(float(v_cond_top) - 0.0) < 1e-12


def test_total_condense_mass_split_can_condense_top_vapor_with_extra_duty(monkeypatch):
    col = _make_tiny_column()
    N = int(col.n_stages)
    Nc = int(col.n_components)
    tray_T = np.asarray(col.T_f, dtype=float).reshape((N,))
    P_tray = np.asarray(col.P_psia, dtype=float).reshape((N,))
    V_in = np.array([1.0, 0.0], dtype=float)
    y_in = np.full((N, Nc), 1.0 / max(Nc, 1), dtype=float)
    top_V = np.array([0.2, 0.2], dtype=float)  # 0.4 lbmol in top vapor holdup

    def _fake_total_cond_duty(**kwargs):
        return -3600.0, 100.0

    monkeypatch.setattr(rhs_module, "_compute_total_condenser_duty_btu_per_h", _fake_total_cond_duty)

    v_cond_in, v_to_top, v_cond_top, q_used, q_req, mode = _condenser_mass_split_from_duty(
        col=col,
        inputs=ColumnInputs(
            condenser_duty_mode="total-condense",
            condenser_duty_btu_per_h=-100.0,
            condenser_duty_trim_btu_per_h=-1800.0,  # extra cooling beyond full-condense requirement
            thermo_provider=object(),
        ),
        tray_T_F=tray_T,
        P_tray_psia=P_tray,
        V_in_lbmolps=V_in,
        y_in=y_in,
        top_V=top_V,
        epsilon_lbmol=1e-12,
    )

    assert mode == "total-condense"
    assert abs(float(q_req) + 3600.0) < 1e-12
    assert abs(float(q_used) + 5400.0) < 1e-12
    assert abs(float(v_cond_in) - 1.0) < 1e-12
    assert abs(float(v_to_top) - 0.0) < 1e-12
    assert abs(float(v_cond_top) - 0.0) < 1e-12


def test_top_drum_pressure_gate_blocks_reverse_vapor_slip(monkeypatch):
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),  # 1 lbmol/s vapor from stage 2 to condenser
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([10.0, 0.0], dtype=float)  # high top-vapor holdup -> high drum pressure

    def _fake_total_cond_duty(**_kwargs):
        # Full condensation of 1 lbmol/s requires -3600 BTU/h.
        return -3600.0, 100.0

    monkeypatch.setattr(rhs_module, "_compute_total_condenser_duty_btu_per_h", _fake_total_cond_duty)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=-1800.0,  # 50% condense capacity before pressure gate
        thermo_provider=object(),
        pressure_model="spec",
        top_drum_vapor_volume_ft3=1.0,
        enforce_top_drum_pressure_gate=True,
        top_drum_pressure_gate_soft_psi=None,  # hard gate for deterministic behavior
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    v_to_top_lbmolph = float(np.asarray(diag["V_to_top_drum_lbmolph"], dtype=float).reshape((-1,))[0])
    v_cond_in_lbmolph = float(np.asarray(diag["V_condensed_in_lbmolph"], dtype=float).reshape((-1,))[0])
    v_blocked_lbmolph = float(np.asarray(diag["V_to_top_drum_blocked_lbmolph"], dtype=float).reshape((-1,))[0])
    dp_drive = float(np.asarray(diag["dP_stage2_to_top_drum_psia"], dtype=float).reshape((-1,))[0])
    gate_scale = float(np.asarray(diag["V_to_top_drum_pressure_gate_scale"], dtype=float).reshape((-1,))[0])

    assert np.isfinite(dp_drive)
    assert dp_drive < 0.0
    assert abs(gate_scale - 0.0) < 1e-12
    assert abs(v_to_top_lbmolph - 0.0) < 1e-9
    assert abs(v_cond_in_lbmolph - 3600.0) < 1e-6
    assert abs(v_blocked_lbmolph - 1800.0) < 1e-6


def test_top_drum_pressure_gate_conductance_reduces_stage2_vapor_outflow(monkeypatch):
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),  # 1 lbmol/s vapor from stage 2 to condenser
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([10.0, 0.0], dtype=float)  # high top-vapor holdup -> high drum pressure

    def _fake_total_cond_duty(**_kwargs):
        # Full condensation of 1 lbmol/s requires -3600 BTU/h.
        return -3600.0, 100.0

    monkeypatch.setattr(rhs_module, "_compute_total_condenser_duty_btu_per_h", _fake_total_cond_duty)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=-1800.0,  # 50% condense capacity before pressure gate
        thermo_provider=object(),
        pressure_model="spec",
        vapor_flow_model="conductance",
        top_drum_vapor_volume_ft3=1.0,
        enforce_top_drum_pressure_gate=True,
        top_drum_pressure_gate_soft_psi=None,  # hard gate for deterministic behavior
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    v_to_top_lbmolph = float(np.asarray(diag["V_to_top_drum_lbmolph"], dtype=float).reshape((-1,))[0])
    v_cond_in_lbmolph = float(np.asarray(diag["V_condensed_in_lbmolph"], dtype=float).reshape((-1,))[0])
    v_blocked_lbmolph = float(np.asarray(diag["V_to_top_drum_blocked_lbmolph"], dtype=float).reshape((-1,))[0])
    v_out_stage2_lbmolph = float(np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((-1,))[1])
    dp_drive = float(np.asarray(diag["dP_stage2_to_top_drum_psia"], dtype=float).reshape((-1,))[0])
    gate_scale = float(np.asarray(diag["V_to_top_drum_pressure_gate_scale"], dtype=float).reshape((-1,))[0])

    assert np.isfinite(dp_drive)
    assert dp_drive < 0.0
    assert abs(gate_scale - 0.0) < 1e-12
    assert abs(v_to_top_lbmolph - 0.0) < 1e-9
    # Blocked flow is now applied at stage-2 outflow in conductance mode.
    assert abs(v_cond_in_lbmolph - 1800.0) < 1e-6
    assert abs(v_blocked_lbmolph - 1800.0) < 1e-6
    assert abs(v_out_stage2_lbmolph - 1800.0) < 1e-6


def test_top_drum_pressure_gate_huang_profile_reduces_stage2_vapor_outflow(monkeypatch):
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([10.0, 0.0], dtype=float)

    def _fake_total_cond_duty(**_kwargs):
        return -3600.0, 100.0

    monkeypatch.setattr(rhs_module, "_compute_total_condenser_duty_btu_per_h", _fake_total_cond_duty)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=-1800.0,
        thermo_provider=object(),
        pressure_model="hydraulic",
        vapor_flow_model="profile",
        liquid_hydraulic_model="huang-htc",
        top_drum_vapor_volume_ft3=1.0,
        enforce_top_drum_pressure_gate=True,
        top_drum_pressure_gate_soft_psi=None,
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    v_to_top_lbmolph = float(np.asarray(diag["V_to_top_drum_lbmolph"], dtype=float).reshape((-1,))[0])
    v_cond_in_lbmolph = float(np.asarray(diag["V_condensed_in_lbmolph"], dtype=float).reshape((-1,))[0])
    v_blocked_lbmolph = float(np.asarray(diag["V_to_top_drum_blocked_lbmolph"], dtype=float).reshape((-1,))[0])
    v_out_stage2_lbmolph = float(np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((-1,))[1])
    dp_drive = float(np.asarray(diag["dP_stage2_to_top_drum_psia"], dtype=float).reshape((-1,))[0])
    gate_scale = float(np.asarray(diag["V_to_top_drum_pressure_gate_scale"], dtype=float).reshape((-1,))[0])

    assert np.isfinite(dp_drive)
    assert dp_drive < 0.0
    assert abs(gate_scale - 0.0) < 1e-12
    assert abs(v_to_top_lbmolph - 0.0) < 1e-9
    assert abs(v_cond_in_lbmolph - 1800.0) < 1e-6
    assert abs(v_blocked_lbmolph - 1800.0) < 1e-6
    assert abs(v_out_stage2_lbmolph - 1800.0) < 1e-6


def test_hydraulic_top_pressure_ordering_prevents_stage1_below_drum_with_top_anchor(monkeypatch):
    col = _make_tiny_column()
    N = col.n_stages
    area = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area,
    )
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "geometry": geom,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    # Large top-vapor holdup to force high drum pressure.
    y0[sl["top_V"]] = np.array([20.0, 0.0], dtype=float)

    def _fake_pressure_profile(**_kwargs):
        # Deliberately returns stage-1 below likely drum pressure.
        return np.array([150.0, 152.0], dtype=float)

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        pressure_model="hydraulic",
        pressure_top_anchor_psia=150.0,
        condenser_pressure_drop_psi=2.0,
        top_drum_vapor_volume_ft3=1.0,
        enforce_top_pressure_ordering=True,
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((2,))
    p_drum = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
    p_lift = float(np.asarray(diag["P_top_ordering_lift_psia"], dtype=float).reshape((-1,))[0])

    assert p_lift > 0.0
    assert p_h[0] >= p_drum - 1e-12
    assert abs((p_h[1] - p_h[0]) - 2.0) < 1e-9


def test_hydraulic_open_loop_skips_top_pressure_ordering_lift(monkeypatch):
    col = _make_tiny_column()
    N = col.n_stages
    area = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area,
    )
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "geometry": geom,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([20.0, 0.0], dtype=float)

    def _fake_pressure_profile(**_kwargs):
        return np.array([150.0, 152.0], dtype=float)

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        pressure_model="hydraulic",
        condenser_pressure_drop_psi=2.0,
        top_drum_vapor_volume_ft3=1.0,
        enforce_top_pressure_ordering=True,
        enforce_top_drum_pressure_continuity=False,
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((2,))
    assert "P_top_ordering_lift_psia" not in diag
    assert np.allclose(p_h, np.array([150.0, 152.0], dtype=float))


def test_hydraulic_can_anchor_top_profile_to_top_drum_pressure(monkeypatch):
    col = _make_tiny_column()
    N = col.n_stages
    area = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area,
    )
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "geometry": geom,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([20.0, 0.0], dtype=float)

    recorded_anchors = []

    def _fake_pressure_profile(**kwargs):
        recorded_anchors.append(kwargs.get("P_top_anchor_psia"))
        p_top = float(kwargs.get("P_top_anchor_psia"))
        return np.array([p_top, p_top + 2.0], dtype=float)

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)
    monkeypatch.setattr(rhs_module, "_compute_top_drum_pressure_psia", lambda **_kwargs: 180.0)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        pressure_model="hydraulic",
        condenser_pressure_drop_psi=2.0,
        top_drum_vapor_volume_ft3=1.0,
        hydraulic_use_top_drum_pressure_as_anchor=True,
        enforce_top_pressure_ordering=False,
        enforce_top_drum_pressure_continuity=False,
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((2,))
    p_drum = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])

    assert recorded_anchors == [180.0]
    assert p_drum == pytest.approx(180.0)
    assert p_h[0] == pytest.approx(180.0)
    assert p_h[1] == pytest.approx(182.0)


def test_top_drum_pressure_uses_thermo_vapor_z_factor_when_available():
    class ConstZProvider:
        def vapor_z_factor_F_psia(self, T_F, P_psia, y):
            return 0.8

    top_V = np.array([3.0, 1.0], dtype=float)
    P, z_eval, mv = _compute_top_drum_pressure_psia(
        top_V=top_V,
        top_T_F=120.0,
        Z_top=1.0,
        top_vapor_volume_ft3=100.0,
        thermo_provider=ConstZProvider(),
        y_top=np.array([0.75, 0.25], dtype=float),
        P_seed_psia=200.0,
        return_details=True,
    )

    P_ideal = float(np.sum(top_V)) * 10.7316 * (120.0 + 459.67) / 100.0
    assert P == pytest.approx(0.8 * P_ideal, rel=1e-5, abs=1e-4)
    assert z_eval == pytest.approx(0.8)
    assert mv == pytest.approx(4.0)


def test_top_drum_pressure_falls_back_to_supplied_z_without_provider():
    top_V = np.array([2.0, 1.0], dtype=float)
    P, z_eval, mv = _compute_top_drum_pressure_psia(
        top_V=top_V,
        top_T_F=100.0,
        Z_top=0.9,
        top_vapor_volume_ft3=120.0,
        thermo_provider=None,
        y_top=np.array([0.6, 0.4], dtype=float),
        return_details=True,
    )

    expected = float(np.sum(top_V)) * 0.9 * 10.7316 * (100.0 + 459.67) / 120.0
    assert P == pytest.approx(expected)
    assert z_eval == pytest.approx(0.9)
    assert mv == pytest.approx(3.0)


def test_huang_uses_free_hydraulic_pressure_profile_with_uniform_top_drum_continuity_shift(monkeypatch):
    col = _make_tiny_column()
    N = col.n_stages
    area = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area,
    )
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "geometry": geom,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([20.0, 0.0], dtype=float)

    recorded_anchors = []

    def _fake_pressure_profile(**kwargs):
        recorded_anchors.append(kwargs.get("P_top_anchor_psia"))
        if kwargs.get("P_top_anchor_psia") is None:
            return np.array([150.0, 152.0], dtype=float)
        return np.array([160.0, 162.0], dtype=float)

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)
    monkeypatch.setattr(rhs_module, "_compute_top_drum_pressure_psia", lambda **_kwargs: 200.0)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        pressure_model="hydraulic",
        vapor_flow_model="profile",
        liquid_hydraulic_model="huang-htc",
        condenser_pressure_drop_psi=2.0,
        top_drum_vapor_volume_ft3=1.0,
        enforce_top_pressure_ordering=False,
        top_drum_pressure_gate_soft_psi=None,
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    p_drum_used = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])
    p_drum_raw = float(np.asarray(diag["P_top_drum_psia_raw"], dtype=float).reshape((-1,))[0])
    p_top_free = float(np.asarray(diag["huang_top_anchor_free_psia"], dtype=float).reshape((-1,))[0])
    p_shift = float(np.asarray(diag["huang_top_pressure_continuity_shift_psia"], dtype=float).reshape((-1,))[0])
    anchor_weight = float(np.asarray(diag["huang_top_anchor_weight"], dtype=float).reshape((-1,))[0])
    gate_scale = float(np.asarray(diag["huang_top_anchor_gate_scale"], dtype=float).reshape((-1,))[0])
    p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((2,))

    assert recorded_anchors[0] is None
    assert len(recorded_anchors) == 1
    assert p_drum_raw == pytest.approx(200.0)
    assert p_top_free == pytest.approx(150.0)
    assert p_shift == pytest.approx(50.0)
    assert np.allclose(p_h, np.array([200.0, 202.0], dtype=float))
    assert np.isnan(gate_scale)
    assert np.isnan(anchor_weight)
    assert p_drum_used == pytest.approx(200.0)


def test_huang_skips_top_drum_continuity_shift_for_small_pressure_gap(monkeypatch):
    col = _make_tiny_column()
    N = col.n_stages
    area = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area,
    )
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "geometry": geom,
            "V_lbmolph": np.array([0.0, 3600.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([20.0, 0.0], dtype=float)

    def _fake_pressure_profile(**kwargs):
        if kwargs.get("P_top_anchor_psia") is None:
            return np.array([150.0, 152.0], dtype=float)
        return np.array([160.0, 162.0], dtype=float)

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)
    monkeypatch.setattr(rhs_module, "_compute_top_drum_pressure_psia", lambda **_kwargs: 150.4)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        pressure_model="hydraulic",
        vapor_flow_model="profile",
        liquid_hydraulic_model="huang-htc",
        top_drum_vapor_volume_ft3=1.0,
        enforce_top_pressure_ordering=False,
        top_drum_pressure_gate_soft_psi=None,
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    p_h = np.asarray(diag["P_psia_hyd"], dtype=float).reshape((2,))

    assert np.allclose(p_h, np.array([150.0, 152.0], dtype=float))
    assert "huang_top_pressure_continuity_shift_psia" not in diag


def test_huang_top_drum_vapor_relaxation_condenses_excess_vapor(monkeypatch):
    col = _make_tiny_column()
    N = col.n_stages
    area = np.ones(N, dtype=float)
    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=np.full(N, 2.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(N, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(N, 0.5, dtype=float),
        area_ft2_per_stage=area,
        vapor_volume_ft3_per_stage=np.full(N, 1.0, dtype=float),
        weir_height_in_per_stage=np.zeros(N, dtype=float),
        weir_length_ft_per_stage=np.full(N, 1.0, dtype=float),
        active_area_frac_per_stage=np.full(N, 1.0, dtype=float),
        active_area_ft2_per_stage=area,
    )
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "geometry": geom,
            "V_lbmolph": np.array([0.0, 0.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {},
        }
    )
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([20.0, 0.0], dtype=float)
    y0[sl["top_L"]] = np.array([1.0, 0.0], dtype=float)

    def _fake_pressure_profile(**kwargs):
        if kwargs.get("P_top_anchor_psia") is None:
            return np.array([150.0, 152.0], dtype=float)
        return np.array([162.5, 164.5], dtype=float)

    monkeypatch.setattr(rhs_module, "_pressure_profile_hydraulic_psia", _fake_pressure_profile)
    monkeypatch.setattr(rhs_module, "_compute_top_drum_pressure_psia", lambda **_kwargs: 200.0)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        pressure_model="hydraulic",
        vapor_flow_model="profile",
        liquid_hydraulic_model="huang-htc",
        pressure_top_anchor_psia=162.5,
        top_drum_vapor_volume_ft3=1.0,
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=0.0,
        hydraulic_pressure_relaxation_sec=10.0,
        enforce_top_pressure_ordering=False,
        top_drum_pressure_gate_soft_psi=None,
    )
    dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    d_top_L = np.asarray(dydt[sl["top_L"]], dtype=float).reshape((2,))
    d_top_V = np.asarray(dydt[sl["top_V"]], dtype=float).reshape((2,))
    dmv = float(np.asarray(diag["huang_top_drum_vapor_relax_dmv_lbmolps"], dtype=float).reshape((-1,))[0])
    p_target = float(np.asarray(diag["huang_top_drum_vapor_relax_target_psia"], dtype=float).reshape((-1,))[0])

    assert p_target == pytest.approx(150.0)
    assert dmv < 0.0
    assert np.sum(d_top_V) == pytest.approx(dmv)
    assert np.sum(d_top_L) == pytest.approx(-dmv)
    assert d_top_V[0] < 0.0
    assert d_top_L[0] > 0.0


def test_top_drum_pressure_uses_lagged_stage1_temperature():
    col = _make_tiny_column()
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=True,
    )
    y0 = layout.pack_y0(col)
    sl = layout.slices()

    tray_T = y0[sl["tray_T_f"]].reshape((2,)).copy()
    tray_T[0] = 300.0
    y0[sl["tray_T_f"]] = tray_T
    y0[sl["top_V"]] = np.array([10.0, 0.0], dtype=float)

    inputs = ColumnInputs(
        pressure_model="spec",
        top_drum_vapor_volume_ft3=100.0,
        top_drum_pressure_temperature_relaxation_sec=10.0,
        vapor_holdup_relaxation_sec=10.0,
        T_tray_prev_F=np.array([100.0, 120.0], dtype=float),
    )
    _dydt, diag = column_rhs(0.0, y0, col, layout, inputs=inputs)

    t_raw = float(np.asarray(diag["T_top_drum_pressure_raw_F"], dtype=float).reshape((-1,))[0])
    t_used = float(np.asarray(diag["T_top_drum_pressure_used_F"], dtype=float).reshape((-1,))[0])
    alpha = float(np.asarray(diag["T_top_drum_pressure_relax_alpha"], dtype=float).reshape((-1,))[0])
    p_top = float(np.asarray(diag["P_top_drum_psia"], dtype=float).reshape((-1,))[0])

    assert abs(t_raw - 300.0) < 1e-12
    assert abs(alpha - 0.1) < 1e-12
    assert abs(t_used - 120.0) < 1e-12

    expected_p = 10.0 * 10.7316 * (t_used + 459.67) / 100.0
    assert abs(p_top - expected_p) < 1e-9


def test_top_drum_pressure_temperature_lag_uses_filtered_memory_state():
    col = _make_tiny_column()
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=True,
        include_bottom=False,
        include_vapor=True,
        include_temperature=True,
    )
    y0 = layout.pack_y0(col)
    sl = layout.slices()
    y0[sl["top_V"]] = np.array([10.0, 0.0], dtype=float)

    y_step1 = y0.copy()
    tray_T1 = y_step1[sl["tray_T_f"]].reshape((2,)).copy()
    tray_T1[0] = 300.0
    y_step1[sl["tray_T_f"]] = tray_T1
    inputs1 = ColumnInputs(
        pressure_model="spec",
        top_drum_vapor_volume_ft3=100.0,
        top_drum_pressure_temperature_relaxation_sec=10.0,
        top_drum_pressure_T_prev_F=100.0,
        T_tray_prev_F=np.array([100.0, 120.0], dtype=float),
    )
    _dydt1, diag1 = column_rhs(0.0, y_step1, col, layout, inputs=inputs1)
    t_used_1 = float(np.asarray(diag1["T_top_drum_pressure_used_F"], dtype=float).reshape((-1,))[0])
    assert abs(t_used_1 - 120.0) < 1e-12

    y_step2 = y0.copy()
    tray_T2 = y_step2[sl["tray_T_f"]].reshape((2,)).copy()
    tray_T2[0] = 100.0
    y_step2[sl["tray_T_f"]] = tray_T2
    inputs2 = ColumnInputs(
        pressure_model="spec",
        top_drum_vapor_volume_ft3=100.0,
        top_drum_pressure_temperature_relaxation_sec=10.0,
        top_drum_pressure_T_prev_F=t_used_1,
        T_tray_prev_F=np.array([300.0, 120.0], dtype=float),
    )
    _dydt2, diag2 = column_rhs(0.0, y_step2, col, layout, inputs=inputs2)
    t_used_2 = float(np.asarray(diag2["T_top_drum_pressure_used_F"], dtype=float).reshape((-1,))[0])

    assert abs(t_used_2 - 118.0) < 1e-12
    assert t_used_2 < 150.0


def test_temperature_uses_provider_cp():
    # Verify Cp from thermo provider is used in temperature energy balance.
    N, Nc = 2, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 2, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 210.0], dtype=float),
        V_lbmolph=np.array([0.0, 0.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([10.0, 10.0], dtype=float),
        M_V_lbmol=np.array([0.0, 0.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    class CpThermo:
        def cp_liq_vap_btu_per_lbmolF(self, T_F, P_psia, z):
            return (100.0, 0.0)  # high Cp to drive small dT

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=True,
    )
    y0_state = layout.pack_y0(col)

    inputs = ColumnInputs(thermo_provider=CpThermo())
    dydt, _ = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    sl = layout.slices()
    dT = dydt[sl["tray_T_f"]]

    # With very large Cp, temperature change should be near zero.
    assert np.all(np.abs(dT) < 1e-6)


def test_vapor_flow_energy_relaxation():
    # Energy-driven vapor flow should relax toward the computed value.
    N, Nc = 3, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([10.0, 10.0, 10.0], dtype=float),
        L_lbmolph=np.array([10.0, 10.0, 10.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    class CpThermo:
        def cp_liq_btu_per_lbmolF(self, T_F, P_psia, x):
            return 100.0

        def cp_vap_btu_per_lbmolF(self, T_F, P_psia, y):
            return 0.0

        def h_liq_btu_per_lbmol(self, T_F, P_psia, x):
            return 0.0

        def h_vap_btu_per_lbmol(self, T_F, P_psia, y):
            return 1000.0

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=10.0, boilup_lbmolph=10.0),
        vapor_flow_model="energy",
        vapor_flow_relaxation_sec=10.0,
        V_out_prev_lbmolph=np.array([0.0, 3600.0, 0.0], dtype=float),  # 1 lbmol/s at stage 2
        dT_tray_target_F_per_s=np.array([0.0, 1000.0, 0.0], dtype=float),  # force G -> negative
        thermo=CpThermo(),
    )

    _dydt, diag = column_rhs(1.0, y0_state, col, layout, inputs=inputs)
    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))

    # alpha = dt/tau = 0.1, so V_out = 0.9 * V_prev = 3240 lbmol/h at stage 2
    assert np.isclose(v_out[1], 3240.0, rtol=1e-3, atol=1.0)


def test_vapor_flow_energy_uses_fixed_liquid_outflow_balance():
    # Verify energy vapor closure solves with fixed L_out using the
    # reference-invariant latent-enthalpy form:
    # V_out = [L_in*(hL_in-hL_out) + V_in*(hV_in-hL_out) - dE_target] / (hV_out-hL_out)
    N, Nc = 3, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([90.0, 100.0, 110.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 2000.0, 3600.0], dtype=float),
        L_lbmolph=np.array([0.0, 3600.0, 3600.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    class LinearH:
        def cp_liq_btu_per_lbmolF(self, T_F, P_psia, x):
            return 0.0

        def cp_vap_btu_per_lbmolF(self, T_F, P_psia, y):
            return 0.0

        def h_liq_btu_per_lbmol(self, T_F, P_psia, x):
            return float(T_F)

        def h_vap_btu_per_lbmol(self, T_F, P_psia, y):
            return 2.2 * float(T_F)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=7200.0, boilup_lbmolph=3600.0),
        vapor_flow_model="energy",
        thermo=LinearH(),
        dT_tray_target_F_per_s=np.zeros(N, dtype=float),
        # Keep clamp headroom above the analytical target so this test exercises
        # the closure equation itself rather than clamp behavior.
        V_out_prev_lbmolph=np.array([0.0, 4000.0, 0.0], dtype=float),
    )

    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)
    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))

    # Stage 2 expected values (lbmol/s):
    # L_in=7200/3600=2, V_in=3600/3600=1, L_out=3600/3600=1
    # hL_in=90, hL_out=100, hV_in=242, hV_out=220, dE_target=0
    # V_out = [2*(90-100) + 1*(242-100)] / (220-100) = 1.016666.. lbmol/s = 3660 lbmol/h
    assert np.isclose(v_out[1], 3660.0, rtol=1e-6, atol=1e-6)


def test_vapor_flow_energy_prefers_provider_enthalpies_when_available():
    N, Nc = 3, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([90.0, 100.0, 110.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 2000.0, 3600.0], dtype=float),
        L_lbmolph=np.array([0.0, 3600.0, 3600.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    class FallbackThermo:
        def cp_liq_btu_per_lbmolF(self, T_F, P_psia, x):
            return 0.0

        def cp_vap_btu_per_lbmolF(self, T_F, P_psia, y):
            return 0.0

        def h_liq_btu_per_lbmol(self, T_F, P_psia, x):
            return float(T_F)

        def h_vap_btu_per_lbmol(self, T_F, P_psia, y):
            return 2.2 * float(T_F)

    class ProviderThermo:
        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            z = np.asarray(z, dtype=float).reshape((-1,))
            x = z.copy()
            y = z.copy()
            K = np.ones_like(z)
            return (x, y, K, float(T_F) + 100.0, 3.0 * float(T_F) + 100.0)

        def cp_liq_vap_btu_per_lbmolF(self, T_F, P_psia, x, y):
            return (0.0, 0.0)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=7200.0, boilup_lbmolph=3600.0),
        vapor_flow_model="energy",
        thermo=FallbackThermo(),
        thermo_provider=ProviderThermo(),
        dT_tray_target_F_per_s=np.zeros(N, dtype=float),
        V_out_prev_lbmolph=np.array([0.0, 4000.0, 0.0], dtype=float),
    )

    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)
    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))

    # Stage 2 provider-based values (lbmol/s):
    # hL_in=190, hL_out=200, hV_in=430, hV_out=400, dE_target=0
    # V_out = [2*(190-200) + 1*(430-200)] / (400-200) = 1.05 lbmol/s = 3780 lbmol/h
    # Fallback thermo alone would give 3660 lbmol/h, so this distinguishes the paths.
    assert np.isclose(v_out[1], 3780.0, rtol=1e-6, atol=1e-6)


def test_vapor_flow_energy_reboiler_neighbor_guard_caps_stage_above_reboiler():
    # Stage above reboiler should be constrained close to boilup to prevent
    # unphysical lower-column vapor-flow growth.
    N, Nc = 4, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3, 4], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 4, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 100.0, 100.0, 500.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 3000.0, 3000.0, 3600.0], dtype=float),
        L_lbmolph=np.array([0.0, 3000.0, 3000.0, 3000.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    class StrongDrivingH:
        def cp_liq_btu_per_lbmolF(self, T_F, P_psia, x):
            return 0.0

        def cp_vap_btu_per_lbmolF(self, T_F, P_psia, y):
            return 0.0

        def h_liq_btu_per_lbmol(self, T_F, P_psia, x):
            return 0.0

        def h_vap_btu_per_lbmol(self, T_F, P_psia, y):
            return 10.0 * float(T_F)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=3000.0, boilup_lbmolph=3600.0),
        vapor_flow_model="energy",
        thermo=StrongDrivingH(),
        dT_tray_target_F_per_s=np.zeros(N, dtype=float),
    )

    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)
    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))

    # Reboiler-neighbor guard defaults to +/-20% around boilup for stage N-1.
    # boilup = 3600 lbmol/h => upper cap = 4320 lbmol/h.
    assert np.isclose(v_out[2], 4320.0, rtol=1e-9, atol=1e-9)


def test_vapor_flow_energy_reboiler_neighbor_guard_is_configurable():
    # User-provided guard ratios should override defaults.
    N, Nc = 4, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3, 4], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 4, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 100.0, 100.0, 500.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 3000.0, 3000.0, 3600.0], dtype=float),
        L_lbmolph=np.array([0.0, 3000.0, 3000.0, 3000.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    class StrongDrivingH:
        def cp_liq_btu_per_lbmolF(self, T_F, P_psia, x):
            return 0.0

        def cp_vap_btu_per_lbmolF(self, T_F, P_psia, y):
            return 0.0

        def h_liq_btu_per_lbmol(self, T_F, P_psia, x):
            return 0.0

        def h_vap_btu_per_lbmol(self, T_F, P_psia, y):
            return 10.0 * float(T_F)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=3000.0, boilup_lbmolph=3600.0),
        vapor_flow_model="energy",
        thermo=StrongDrivingH(),
        dT_tray_target_F_per_s=np.zeros(N, dtype=float),
        reboiler_neighbor_vflow_hi_ratio=1.01,
        reboiler_neighbor_vflow_lo_ratio=0.99,
    )

    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)
    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))

    # Custom guard is +/-1% around boilup for stage N-1.
    # boilup = 3600 lbmol/h => upper cap = 3636 lbmol/h.
    assert np.isclose(v_out[2], 3636.0, rtol=1e-9, atol=1e-9)


def test_feed_present_keeps_input_vapor_profile():
    # Internal V profile from Excel/ChemSep should be used as-is even with a liquid feed.
    N, Nc = 4, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3, 4], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 4, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0, 130.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0, 200.0], dtype=float),
        # Deliberate feed-stage step in V profile (stage 2 << stage 3)
        V_lbmolph=np.array([0.0, 1000.0, 3000.0, 3000.0], dtype=float),
        L_lbmolph=np.array([2000.0, 2000.0, 3000.0, 3000.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={
            "Feed": StreamSpecNormalized(
                name="Feed",
                stage_1based=3,
                temperature_f=120.0,
                vapor_fraction=0.0,
                total_molar_flow_lbmolph=100.0,
                component_molar_flows_lbmolph={"A": 100.0},
            )
        },
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=ColumnInputs())

    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))
    # Stage 2 must retain the input-profile value (1000), not be rebuilt from bottom boilup.
    assert np.isclose(v_out[1], 1000.0, rtol=1e-12, atol=1e-12)
    # Stage 3/feed stage profile value is also preserved.
    assert np.isclose(v_out[2], 3000.0, rtol=1e-12, atol=1e-12)


def test_feed_stage_not_pinned_in_energy_vapor_flow_model():
    # With vapor_flow_model="energy", feed stage vapor flow should be solved
    # dynamically (not hard-pinned to the input profile).
    N, Nc = 4, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3, 4], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 4, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0, 130.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 1000.0, 3000.0, 3000.0], dtype=float),
        L_lbmolph=np.array([2000.0, 2000.0, 3000.0, 3000.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={
            "Feed": StreamSpecNormalized(
                name="Feed",
                stage_1based=3,
                temperature_f=120.0,
                vapor_fraction=0.0,
                total_molar_flow_lbmolph=100.0,
                component_molar_flows_lbmolph={"A": 100.0},
            )
        },
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    class LinearH:
        def cp_liq_btu_per_lbmolF(self, T_F, P_psia, x):
            return 1.0

        def cp_vap_btu_per_lbmolF(self, T_F, P_psia, y):
            return 1.0

        def h_liq_btu_per_lbmol(self, T_F, P_psia, x):
            return float(T_F)

        def h_vap_btu_per_lbmol(self, T_F, P_psia, y):
            return 2.5 * float(T_F)

    inputs = ColumnInputs(vapor_flow_model="energy", thermo=LinearH())
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)
    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))

    # Feed stage (stage 3 / index 2) should be free to deviate from profile.
    assert not np.isclose(v_out[2], 3000.0, rtol=1e-6, atol=1e-6)


def test_vapor_flow_conductance_responds_to_pressure_gradient():
    N, Nc = 4, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    diam_ft = np.full(N, 2.0, dtype=float)
    spacing_ft = np.full(N, 1.0, dtype=float)
    void_frac = np.full(N, 0.5, dtype=float)
    area_ft2 = math.pi * (0.5 * diam_ft) ** 2
    vapor_vol = area_ft2 * spacing_ft * void_frac
    weir_h_in = np.zeros(N, dtype=float)
    weir_L_ft = np.full(N, 1.0, dtype=float)
    aaf = np.full(N, 1.0, dtype=float)
    active_area_ft2 = area_ft2 * aaf

    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=diam_ft,
        tray_spacing_ft_per_stage=spacing_ft,
        gas_void_frac_per_stage=void_frac,
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=vapor_vol,
        weir_height_in_per_stage=weir_h_in,
        weir_length_ft_per_stage=weir_L_ft,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area_ft2,
    )

    def _make_column(P_profile_psia: np.ndarray) -> ColumnSpec:
        return ColumnSpec(
            excel_path="<unit-test>",
            components_excel=["A"],
            components_dwsim=["A"],
            n_components=Nc,
            n_stages=N,
            stage_1based=np.array([1, 2, 3, 4], dtype=int),
            sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
            duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
            specs_raw={"Number of Stages": 4, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
            T_f=np.array([100.0, 110.0, 120.0, 130.0], dtype=float),
            P_psia=np.asarray(P_profile_psia, dtype=float),
            V_lbmolph=np.array([0.0, 0.0, 0.0, 3600.0], dtype=float),
            L_lbmolph=np.array([0.0, 0.0, 0.0, 0.0], dtype=float),
            M_L_lbmol=np.array([2.0, 2.0, 2.0, 2.0], dtype=float),
            M_V_lbmol=np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
            y0=y0,
            x0=x0,
            streams={},
            geometry=geom,
        )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        vapor_flow_model="conductance",
        reboiler_neighbor_vflow_hi_ratio=10.0,
        reboiler_neighbor_vflow_lo_ratio=1.0e-9,
    )

    col_hi_dp = _make_column(np.array([200.0, 210.0, 220.0, 230.0], dtype=float))
    y_hi_dp = layout.pack_y0(col_hi_dp)
    _dydt_hi, diag_hi = column_rhs(0.0, y_hi_dp, col_hi_dp, layout, inputs=inputs)
    v_hi = np.asarray(diag_hi["V_out_lbmolph"], dtype=float).reshape((N,))

    col_lo_dp = _make_column(np.array([200.0, 200.0, 200.0, 230.0], dtype=float))
    y_lo_dp = layout.pack_y0(col_lo_dp)
    _dydt_lo, diag_lo = column_rhs(0.0, y_lo_dp, col_lo_dp, layout, inputs=inputs)
    v_lo = np.asarray(diag_lo["V_out_lbmolph"], dtype=float).reshape((N,))

    # Internal vapor flow should increase with available tray-to-tray pressure drop.
    assert v_hi[1] > v_lo[1] + 1.0e-9
    assert v_hi[2] > v_lo[2] + 1.0e-9


def test_vapor_flow_conductance_caps_to_nominal_when_prev_is_high():
    N, Nc = 4, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    diam_ft = np.full(N, 2.0, dtype=float)
    spacing_ft = np.full(N, 1.0, dtype=float)
    void_frac = np.full(N, 0.5, dtype=float)
    area_ft2 = math.pi * (0.5 * diam_ft) ** 2
    vapor_vol = area_ft2 * spacing_ft * void_frac
    weir_h_in = np.zeros(N, dtype=float)
    weir_L_ft = np.full(N, 1.0, dtype=float)
    aaf = np.full(N, 1.0, dtype=float)
    active_area_ft2 = area_ft2 * aaf

    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=diam_ft,
        tray_spacing_ft_per_stage=spacing_ft,
        gas_void_frac_per_stage=void_frac,
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=vapor_vol,
        weir_height_in_per_stage=weir_h_in,
        weir_length_ft_per_stage=weir_L_ft,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area_ft2,
    )

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3, 4], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 4, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0, 130.0], dtype=float),
        # Large tray-to-tray pressure gradients to drive high raw conductance flow.
        P_psia=np.array([200.0, 260.0, 320.0, 380.0], dtype=float),
        # Nominal internal profile used by conductance clamp.
        V_lbmolph=np.array([0.0, 1000.0, 1200.0, 3600.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0, 0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([2.0, 2.0, 2.0, 2.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
        geometry=geom,
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        vapor_flow_model="conductance",
        # Start from very large prior-step internal vapor flow; clamp should still
        # enforce nominal-profile ceilings.
        V_out_prev_lbmolph=np.array([0.0, 20000.0, 22000.0, 3600.0], dtype=float),
        reboiler_neighbor_vflow_hi_ratio=10.0,
        reboiler_neighbor_vflow_lo_ratio=1.0e-9,
    )
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)
    v_out = np.asarray(diag["V_out_lbmolph"], dtype=float).reshape((N,))

    assert v_out[1] <= (1.5 * 1000.0 + 1.0e-9)
    assert v_out[2] <= (1.5 * 1200.0 + 1.0e-9)


def test_vapor_flow_conductance_soft_clamp_reports_eps_and_preserves_limits():
    N, Nc = 4, 1
    x0 = np.ones((N, Nc), dtype=float)
    y0 = np.ones((N, Nc), dtype=float)

    diam_ft = np.full(N, 2.0, dtype=float)
    spacing_ft = np.full(N, 1.0, dtype=float)
    void_frac = np.full(N, 0.5, dtype=float)
    area_ft2 = math.pi * (0.5 * diam_ft) ** 2
    vapor_vol = area_ft2 * spacing_ft * void_frac
    weir_h_in = np.zeros(N, dtype=float)
    weir_L_ft = np.full(N, 1.0, dtype=float)
    aaf = np.full(N, 1.0, dtype=float)
    active_area_ft2 = area_ft2 * aaf

    geom = ColumnGeometry(
        sections=[
            ColumnGeometrySection(
                start_stage_1based=1,
                end_stage_1based=N,
                diameter_ft=2.0,
                tray_spacing_ft=1.0,
                gas_void_frac=0.5,
                weir_height_in=0.0,
                weir_length_ft=1.0,
                active_area_frac=1.0,
            )
        ],
        diameter_ft_per_stage=diam_ft,
        tray_spacing_ft_per_stage=spacing_ft,
        gas_void_frac_per_stage=void_frac,
        area_ft2_per_stage=area_ft2,
        vapor_volume_ft3_per_stage=vapor_vol,
        weir_height_in_per_stage=weir_h_in,
        weir_length_ft_per_stage=weir_L_ft,
        active_area_frac_per_stage=aaf,
        active_area_ft2_per_stage=active_area_ft2,
    )

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A"],
        components_dwsim=["A"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3, 4], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 4, "Number of Components": 1, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0, 130.0], dtype=float),
        P_psia=np.array([200.0, 260.0, 320.0, 380.0], dtype=float),
        V_lbmolph=np.array([0.0, 1000.0, 1200.0, 3600.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0, 0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([2.0, 2.0, 2.0, 2.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
        geometry=geom,
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    hard_inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        vapor_flow_model="conductance",
        V_out_prev_lbmolph=np.array([0.0, 20000.0, 22000.0, 3600.0], dtype=float),
        reboiler_neighbor_vflow_hi_ratio=10.0,
        reboiler_neighbor_vflow_lo_ratio=1.0e-9,
        vflow_smooth_clamp_epsilon_lbmolps=None,
    )
    _dydt_hard, diag_hard = column_rhs(0.0, y0_state, col, layout, inputs=hard_inputs)
    v_hard = np.asarray(diag_hard["V_out_lbmolph"], dtype=float).reshape((N,))

    smooth_eps_lbmolph = 50.0
    smooth_inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=3600.0),
        vapor_flow_model="conductance",
        V_out_prev_lbmolph=np.array([0.0, 20000.0, 22000.0, 3600.0], dtype=float),
        reboiler_neighbor_vflow_hi_ratio=10.0,
        reboiler_neighbor_vflow_lo_ratio=1.0e-9,
        vflow_smooth_clamp_epsilon_lbmolps=smooth_eps_lbmolph / 3600.0,
    )
    _dydt_smooth, diag_smooth = column_rhs(0.0, y0_state, col, layout, inputs=smooth_inputs)
    v_smooth = np.asarray(diag_smooth["V_out_lbmolph"], dtype=float).reshape((N,))

    eps_logged = float(np.asarray(diag_smooth["vflow_smooth_clamp_eps_lbmolph"], dtype=float).reshape((-1,))[0])
    assert np.isclose(eps_logged, smooth_eps_lbmolph, atol=1e-12)
    assert np.all(np.isfinite(v_smooth[1:3]))
    # Soft clamp should preserve nominal ceilings while removing hard derivative kinks.
    assert v_smooth[1] <= (1.5 * 1000.0 + 1.0e-6)
    assert v_smooth[2] <= (1.5 * 1200.0 + 1.0e-6)
    assert np.allclose(v_smooth[1:3], v_hard[1:3], atol=5.0)


def test_feed_split_can_use_tp_flash_when_provider_available():
    # Stream vapor_fraction is 0, but thermo flash should provide non-zero effective feed vapor split.
    N, Nc = 3, 2
    x0 = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]], dtype=float)
    y0 = x0.copy()

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 2, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 120.0, 130.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 1000.0, 1000.0], dtype=float),
        L_lbmolph=np.array([1000.0, 1000.0, 1000.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={
            "Feed": StreamSpecNormalized(
                name="Feed",
                stage_1based=2,
                temperature_f=120.0,
                vapor_fraction=0.0,
                total_molar_flow_lbmolph=100.0,
                component_molar_flows_lbmolph={"A": 50.0, "B": 50.0},
            )
        },
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)

    class FeedFlashProvider:
        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            # K = [2, 0.5] gives an intermediate beta for z=[0.5,0.5].
            K = np.array([2.0, 0.5], dtype=float)
            x = np.array([0.33, 0.67], dtype=float)
            y = np.array([0.67, 0.33], dtype=float)
            return (x, y, K, -5000.0, 500.0)

    inputs = ColumnInputs(thermo_provider=FeedFlashProvider(), flash_feed_at_stage_conditions=True)
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    vf_eff = float(np.asarray(diag["feed_vf_effective"], dtype=float).reshape((-1,))[0])
    # Should not remain at stream vapor_fraction=0.0 if flash split is used.
    assert vf_eff > 0.0
    assert vf_eff < 1.0


def test_feed_component_mapping_is_case_insensitive():
    N, Nc = 3, 3
    x0 = np.array([[0.3, 0.5, 0.2], [0.3, 0.5, 0.2], [0.3, 0.5, 0.2]], dtype=float)
    y0 = x0.copy()

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["n-Propane", "n-Butane", "n-Pentane"],
        components_dwsim=["Propane", "N-butane", "N-pentane"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 3, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 120.0, 130.0], dtype=float),
        P_psia=np.array([200.0, 200.0, 200.0], dtype=float),
        V_lbmolph=np.array([0.0, 1000.0, 1000.0], dtype=float),
        L_lbmolph=np.array([1000.0, 1000.0, 1000.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={
            "Feed": StreamSpecNormalized(
                name="Feed",
                stage_1based=2,
                temperature_f=100.0,
                vapor_fraction=0.0,
                total_molar_flow_lbmolph=60.0,
                component_molar_flows_lbmolph={
                    "n-Propane": 10.0,
                    "n-Butane": 20.0,
                    "N-Pentane": 30.0,  # differs in case from components_excel
                },
            )
        },
    )

    stage0, Fk_L, Fk_V = _feed_component_rates_lbmolps(
        col,
        Nc,
        thermo_provider=None,
        flash_feed_at_stage_conditions=False,
    )
    assert stage0 == 1
    assert np.isclose(float(np.sum(Fk_L + Fk_V)) * 3600.0, 60.0, atol=1e-12)
    assert np.isclose(float(Fk_L[2]) * 3600.0, 30.0, atol=1e-12)


def test_feed_enthalpy_rate_uses_provider_flash_when_available():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "streams": {
                "Feed": StreamSpecNormalized(
                    name="Feed",
                    stage_1based=1,
                    temperature_f=200.0,
                    vapor_fraction=0.5,
                    total_molar_flow_lbmolph=0.0,
                    component_molar_flows_lbmolph={},
                )
            },
        }
    )

    class ThermoFallback:
        def h_liq_btu_per_lbmol(self, T_f, P_psia, x):
            return 1.0

        def h_vap_btu_per_lbmol(self, T_f, P_psia, y):
            return 2.0

    class Provider:
        def __init__(self):
            self.calls = 0

        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            self.calls += 1
            return ([0.5, 0.5], [0.5, 0.5], [1.0, 1.0], 111.0, 222.0, 1.0)

    q = _feed_enthalpy_rate_btu_per_s(
        feed_stage0=0,
        stage0=0,
        col=col2,
        Nc=2,
        Fk_L=np.array([1.0, 0.0], dtype=float),
        Fk_V=np.array([0.0, 2.0], dtype=float),
        T_stage_F=100.0,
        P_stage_psia=200.0,
        thermo=ThermoFallback(),
        thermo_provider=(prov := Provider()),
        epsilon_lbmol=1e-12,
    )

    assert prov.calls == 1
    assert np.isclose(float(q), 555.0, atol=1e-12)


def test_feed_enthalpy_rate_fallback_uses_phase_compositions_from_split():
    col = _make_tiny_column()

    class ThermoPhaseAware:
        def h_liq_btu_per_lbmol(self, T_f, P_psia, x):
            xx = np.asarray(x, dtype=float)
            return 1000.0 * float(xx[0]) + 2000.0 * float(xx[1])

        def h_vap_btu_per_lbmol(self, T_f, P_psia, y):
            yy = np.asarray(y, dtype=float)
            return 3000.0 * float(yy[0]) + 4000.0 * float(yy[1])

    q = _feed_enthalpy_rate_btu_per_s(
        feed_stage0=1,
        stage0=1,
        col=col,
        Nc=2,
        Fk_L=np.array([2.0, 0.0], dtype=float),
        Fk_V=np.array([0.0, 3.0], dtype=float),
        T_stage_F=120.0,
        P_stage_psia=210.0,
        thermo=ThermoPhaseAware(),
        thermo_provider=None,
        epsilon_lbmol=1e-12,
    )

    # x_feed=[1,0], y_feed=[0,1] -> q = 2*1000 + 3*4000 = 14000 BTU/s
    assert np.isclose(float(q), 14000.0, atol=1e-9)


def test_thermo_stage_refresh_skips_when_dt_dp_dx_all_below_threshold():
    N, Nc = 3, 2
    x0 = np.array([[0.8, 0.2], [0.5, 0.5], [0.2, 0.8]], dtype=float)
    y0 = x0.copy()

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 2, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 120.0, 140.0], dtype=float),
        P_psia=np.array([200.0, 210.0, 220.0], dtype=float),
        V_lbmolph=np.array([0.0, 1000.0, 1200.0], dtype=float),
        L_lbmolph=np.array([900.0, 1000.0, 1100.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)
    u0 = layout.unpack(y0_state)
    z_prev = np.asarray(u0["x_tray"], dtype=float).copy()

    class CountingProvider:
        def __init__(self):
            self.calls = 0

        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            self.calls += 1
            return (
                [0.5, 0.5],
                [0.5, 0.5],
                [1.0, 1.0],
                -100.0,
                100.0,
                1.0,
            )

    prov = CountingProvider()

    inputs = ColumnInputs(
        thermo_provider=prov,
        compute_thermo_diag=True,
        reboiler_equilibrium=False,
        K_tray_prev=np.ones((N, Nc), dtype=float),
        HL_prev=np.full(N, -10.0, dtype=float),
        HV_prev=np.full(N, 10.0, dtype=float),
        Zfac_prev=np.ones(N, dtype=float),
        T_tray_prev_F=np.array([100.0, 120.0, 140.0], dtype=float),
        P_tray_prev=np.array([200.0, 210.0, 220.0], dtype=float),
        Z_overall_prev=z_prev,
        thermo_refresh_dT_F=1e-3,
        thermo_refresh_dP_psia=1e-3,
        thermo_refresh_dx=1e-6,
    )
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    assert prov.calls == 0
    skipped = np.asarray(diag["thermo_flash_skipped"], dtype=float).reshape((N,))
    refreshed = np.asarray(diag["thermo_flash_refreshed"], dtype=float).reshape((N,))
    assert np.all(skipped == 1.0)
    assert np.all(refreshed == 0.0)


def test_thermo_stage_refresh_updates_only_stage_exceeding_threshold():
    N, Nc = 3, 2
    x0 = np.array([[0.8, 0.2], [0.5, 0.5], [0.2, 0.8]], dtype=float)
    y0 = x0.copy()

    col = ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 2, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 120.0, 140.0], dtype=float),
        P_psia=np.array([200.0, 210.0, 220.0], dtype=float),
        V_lbmolph=np.array([0.0, 1000.0, 1200.0], dtype=float),
        L_lbmolph=np.array([900.0, 1000.0, 1100.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )

    layout = StateVectorLayout(
        n_stages=N,
        n_components=Nc,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
    )
    y0_state = layout.pack_y0(col)
    u0 = layout.unpack(y0_state)
    z_prev = np.asarray(u0["x_tray"], dtype=float).copy()

    class TaggedProvider:
        def __init__(self):
            self.calls = 0

        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            self.calls += 1
            return (
                [0.6, 0.4],
                [0.4, 0.6],
                [2.0, 0.5],
                -200.0,
                200.0,
                0.9,
            )

    prov = TaggedProvider()
    K_prev = np.ones((N, Nc), dtype=float)
    P_prev = np.array([200.0, 210.0, 220.0], dtype=float)
    # Force only stage 2 (index 1) to exceed dP threshold.
    P_prev[1] = 200.0

    inputs = ColumnInputs(
        thermo_provider=prov,
        compute_thermo_diag=True,
        reboiler_equilibrium=False,
        K_tray_prev=K_prev.copy(),
        HL_prev=np.full(N, -10.0, dtype=float),
        HV_prev=np.full(N, 10.0, dtype=float),
        Zfac_prev=np.ones(N, dtype=float),
        T_tray_prev_F=np.array([100.0, 120.0, 140.0], dtype=float),
        P_tray_prev=P_prev,
        Z_overall_prev=z_prev,
        thermo_refresh_dT_F=1e-3,
        thermo_refresh_dP_psia=1.0,
        thermo_refresh_dx=1e-6,
    )
    _dydt, diag = column_rhs(0.0, y0_state, col, layout, inputs=inputs)

    assert prov.calls == 1
    skipped = np.asarray(diag["thermo_flash_skipped"], dtype=float).reshape((N,))
    refreshed = np.asarray(diag["thermo_flash_refreshed"], dtype=float).reshape((N,))
    assert np.allclose(skipped, np.array([1.0, 0.0, 1.0], dtype=float))
    assert np.allclose(refreshed, np.array([0.0, 1.0, 0.0], dtype=float))

    K = np.asarray(diag["K_tray"], dtype=float).reshape((N, Nc))
    # Only refreshed stage should change from previous K=1.
    assert np.allclose(K[0, :], np.array([1.0, 1.0]))
    assert np.allclose(K[2, :], np.array([1.0, 1.0]))
    assert np.allclose(K[1, :], np.array([2.0, 0.5]))


def test_include_energy_total_condenser_routes_duty_to_liquid_energy():
    col = _make_tiny_column()
    specs = dict(col.specs_raw)
    specs["Condenser Duty (Btu/h)"] = -3600.0  # -1 BTU/s
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 0.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "M_V_lbmol": np.array([0.0, 0.0], dtype=float),
            "specs_raw": specs,
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=True,
    )
    y0 = layout.pack_y0(col2)

    inputs = ColumnInputs(boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0))
    dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    sl = layout.slices()
    dEL = dydt[sl["tray_EL_BTU"]].reshape((2,))
    dEV = dydt[sl["tray_EV_BTU"]].reshape((2,))

    # Total-condenser duty should not be injected into vapor-energy state.
    assert np.all(np.isfinite(dEL))
    assert np.all(np.isfinite(dEV))
    assert abs(float(dEL[0]) + 1.0) < 1e-12
    assert abs(float(dEV[0])) < 1e-12
    assert "dEL_BTU_per_s" in diag
    assert "dEV_BTU_per_s" in diag


def test_include_energy_reports_scalar_energy_residual_diagnostic():
    col = _make_tiny_column()
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=True,
    )
    y0 = layout.pack_y0(col)
    _dydt, diag = column_rhs(0.0, y0, col, layout, inputs=ColumnInputs())

    assert "energy_balance_resid_BTUps_tray" in diag
    assert "resid_energy_btups" in diag
    resid_scalar = float(np.asarray(diag["resid_energy_btups"], dtype=float).reshape((-1,))[0])
    assert np.isfinite(resid_scalar)
    assert resid_scalar >= 0.0


def test_enthalpy_state_follower_uses_energy_state_mismatch_to_drive_temperature():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 0.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
        }
    )
    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=True,
        include_energy=True,
    )
    y0 = layout.pack_y0(col2, thermo=ConstantCpThermo(
        cp_liq_components=np.full(2, 1.0, dtype=float),
        cp_vap_components=np.full(2, 1.0, dtype=float),
        tref_f=0.0,
    ))
    sl = layout.slices()
    tray_EL = np.asarray(y0[sl["tray_EL_BTU"]], dtype=float).reshape((2,)).copy()
    tray_EL[0] += 60.0
    y0[sl["tray_EL_BTU"]] = tray_EL

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo=ConstantCpThermo(
            cp_liq_components=np.full(2, 1.0, dtype=float),
            cp_vap_components=np.full(2, 1.0, dtype=float),
            tref_f=0.0,
        ),
        pressure_model="hydraulic",
        vapor_flow_model="energy",
        dry_tray_K=0.0,
        hydraulic_energy_temperature_mode="enthalpy-state-follower",
        hydraulic_energy_temperature_follow_tau_sec=1.0,
        hydraulic_energy_temperature_resid_frac=0.0,
    )

    dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    dT = np.asarray(dydt[sl["tray_T_f"]], dtype=float).reshape((2,))
    T_target = np.asarray(diag["T_enthalpy_state_target_F_tray"], dtype=float).reshape((2,))
    e_mismatch = np.asarray(diag["E_enthalpy_state_mismatch_BTU_tray"], dtype=float).reshape((2,))
    dT_corr = np.asarray(diag["T_enthalpy_state_correction_F_per_s_tray"], dtype=float).reshape((2,))

    assert e_mismatch[0] > 0.0
    assert dT[0] >= 0.0
    assert dT_corr[0] >= 0.0
    assert dT_corr[0] <= 5.0


def test_include_energy_stays_finite_with_tiny_vapor_holdup_and_huge_ev():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "M_V_lbmol": np.array([0.0, 1.0e-16], dtype=float),
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=True,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()

    tray_V = y0[sl["tray_V"]].reshape((2, 2)).copy()
    tray_V[1, :] = 1.0e-20
    y0[sl["tray_V"]] = tray_V.ravel(order="C")

    tray_EV = y0[sl["tray_EV_BTU"]].reshape((2,)).copy()
    tray_EV[1] = 1.0e300
    y0[sl["tray_EV_BTU"]] = tray_EV

    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=ColumnInputs())
    dEV = np.asarray(diag["dEV_BTU_per_s"], dtype=float).reshape((2,))
    dEL = np.asarray(diag["dEL_BTU_per_s"], dtype=float).reshape((2,))

    assert np.all(np.isfinite(dEV))
    assert np.all(np.isfinite(dEL))
    assert float(np.max(np.abs(dEV))) < 1.0e8


def test_include_energy_uses_specified_condenser_duty_override():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 0.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "M_V_lbmol": np.array([0.0, 0.0], dtype=float),
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=True,
    )
    y0 = layout.pack_y0(col2)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=-7200.0,  # -2 BTU/s
    )
    dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    sl = layout.slices()
    dEL = dydt[sl["tray_EL_BTU"]].reshape((2,))
    dEV = dydt[sl["tray_EV_BTU"]].reshape((2,))

    assert abs(float(dEL[0]) + 2.0) < 1e-12
    assert abs(float(dEV[0])) < 1e-12
    assert "Q_cond_used_BTUph" in diag
    assert abs(float(np.asarray(diag["Q_cond_used_BTUph"], dtype=float).reshape((-1,))[0]) + 7200.0) < 1e-12
    assert "Q_cond_calc_BTUph" not in diag


def test_include_energy_adds_feed_enthalpy_only_on_feed_stage():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 0.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "streams": {
                "Feed": StreamSpecNormalized(
                    name="Feed",
                    stage_1based=2,  # stage index 1
                    temperature_f=120.0,
                    vapor_fraction=0.0,
                    total_molar_flow_lbmolph=3600.0,  # 1 lbmol/s
                    component_molar_flows_lbmolph={"A": 3600.0, "B": 0.0},
                )
            },
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=False,
        include_energy=True,
    )
    y0 = layout.pack_y0(col2)

    class FlatThermo:
        def h_liq_btu_per_lbmol(self, T_f, P_psia, x):
            return 10.0

        def h_vap_btu_per_lbmol(self, T_f, P_psia, y):
            return 20.0

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo=FlatThermo(),
    )
    dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    sl = layout.slices()
    dEL = dydt[sl["tray_EL_BTU"]].reshape((2,))
    dEV = dydt[sl["tray_EV_BTU"]].reshape((2,))

    # Feed liquid enthalpy source is 1 lbmol/s * 10 BTU/lbmol = 10 BTU/s at stage 2 only.
    assert abs(float(dEL[0])) < 1e-12
    assert abs(float(dEL[1]) - 10.0) < 1e-12
    assert np.max(np.abs(dEV)) < 1e-12

    assert "Q_feed_BTUps_tray" in diag
    q_feed = np.asarray(diag["Q_feed_BTUps_tray"], dtype=float).reshape((2,))
    assert np.allclose(q_feed, np.array([0.0, 10.0], dtype=float), atol=1e-12)


def test_temperature_stage1_uses_specified_condenser_duty_without_bubble_closure():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            "V_lbmolph": np.array([0.0, 0.0], dtype=float),
            "L_lbmolph": np.array([0.0, 0.0], dtype=float),
            "M_V_lbmol": np.array([0.0, 0.0], dtype=float),
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
        include_temperature=True,
        include_energy=False,
    )
    y0 = layout.pack_y0(col2)

    thermo = ConstantCpThermo(
        cp_liq_components=np.array([30.0, 25.0]),
        cp_vap_components=np.array([20.0, 18.0]),
        tref_f=60.0,
    )
    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo=thermo,
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=-7200.0,
    )
    dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)

    sl = layout.slices()
    dT = np.asarray(dydt[sl["tray_T_f"]], dtype=float).reshape((2,))

    assert float(dT[0]) < -1e-4
    assert "Q_cond_used_BTUph" in diag
    assert abs(float(np.asarray(diag["Q_cond_used_BTUph"], dtype=float).reshape((-1,))[0]) + 7200.0) < 1e-12


def test_bubble_point_no_bracket_returns_clipped_guess_not_scan_node():
    class NoBracketProvider:
        T_grid_F = np.array([95.0, 120.0, 150.0], dtype=float)

        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            z = np.asarray(z, dtype=float).reshape((-1,))
            z = z / max(float(np.sum(z)), 1e-300)
            K = np.full_like(z, 0.75)  # single-phase side: no RR sign change
            return z, z, K, -1000.0, -500.0

    provider = NoBracketProvider()
    x = np.array([0.8, 0.2], dtype=float)
    T, _fres = _bubble_point_T_F(
        thermo_provider=provider,
        P_psia=220.0,
        x=x,
        T_guess_F=113.2,
        T_min_F=50.0,
        T_max_F=600.0,
    )

    assert abs(float(T) - 113.2) < 1e-9


def test_bubble_point_respects_provider_temperature_bounds():
    class NoBracketProvider:
        T_grid_F = np.array([95.0, 120.0, 150.0], dtype=float)

        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            z = np.asarray(z, dtype=float).reshape((-1,))
            z = z / max(float(np.sum(z)), 1e-300)
            K = np.full_like(z, 0.75)
            return z, z, K, -1000.0, -500.0

    provider = NoBracketProvider()
    x = np.array([0.7, 0.3], dtype=float)
    T_low, _ = _bubble_point_T_F(
        thermo_provider=provider,
        P_psia=220.0,
        x=x,
        T_guess_F=70.0,
        T_min_F=50.0,
        T_max_F=600.0,
    )
    T_high, _ = _bubble_point_T_F(
        thermo_provider=provider,
        P_psia=220.0,
        x=x,
        T_guess_F=180.0,
        T_min_F=50.0,
        T_max_F=600.0,
    )

    assert abs(float(T_low) - 95.0) < 1e-9
    assert abs(float(T_high) - 150.0) < 1e-9


def test_no_holdup_reboiler_sump_temperature_uses_energy_balance_not_bubblepoint_relaxation():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            # Trigger no-holdup reboiler mode on stage N.
            "M_L_lbmol": np.array([5.0, 0.0], dtype=float),
            "streams": {},
        }
    )
    object.__setattr__(col2, "bottom_L0_lbmol", np.array([4.0, 1.0], dtype=float))

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=True,
        include_vapor=True,
        include_temperature=True,
        include_energy=False,
    )
    y0 = layout.pack_y0(col2)

    class FlatKProvider:
        # Constant K => bubble-point fallback would return ~T_guess and force dT_sump ~ 0
        # if bubblepoint relaxation were incorrectly applied.
        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            z = np.asarray(z, dtype=float).reshape((-1,))
            z = z / max(float(np.sum(z)), 1e-300)
            K = np.full_like(z, 0.8)
            return z, z, K, -1000.0, -500.0

    thermo = ConstantCpThermo(
        cp_liq_components=np.array([30.0, 25.0]),
        cp_vap_components=np.array([20.0, 18.0]),
        tref_f=60.0,
    )

    base_inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=20.0, boilup_lbmolph=10.0, bottoms_lbmolph=5.0),
        thermo=thermo,
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=0.0,
    )
    _dydt_base, diag_base = column_rhs(0.0, y0, col2, layout, inputs=base_inputs)
    dT_base = float(diag_base["dT_sump_F_per_s"])

    prov_inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=20.0, boilup_lbmolph=10.0, bottoms_lbmolph=5.0),
        thermo=thermo,
        thermo_provider=FlatKProvider(),
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=0.0,
    )
    _dydt_prov, diag_prov = column_rhs(0.0, y0, col2, layout, inputs=prov_inputs)
    dT_prov = float(diag_prov["dT_sump_F_per_s"])

    # Provider presence can slightly perturb reboiler flash composition, but sump
    # dT should remain energy-driven (nonzero, same sign, similar magnitude) and
    # not collapse to a bubblepoint-relaxation target.
    assert np.isfinite(dT_base)
    assert np.isfinite(dT_prov)
    assert abs(dT_prov) > 1e-4
    assert np.sign(dT_base) == np.sign(dT_prov)
    rel = abs(dT_base - dT_prov) / max(abs(dT_base), 1e-12)
    assert rel < 0.2


def test_no_holdup_reboiler_duty_flash_not_frozen_by_cached_state():
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            # Trigger no-holdup reboiler mode on stage N.
            "M_L_lbmol": np.array([5.0, 0.0], dtype=float),
            "streams": {},
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=True,
        include_vapor=True,
        include_temperature=True,
        include_energy=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    tray_T0 = np.asarray(y0[sl["tray_T_f"]], dtype=float).reshape((2,)).copy()
    tray_T0[0] = 150.0
    tray_T0[1] = 150.0
    y0[sl["tray_T_f"]] = tray_T0

    class LinearEnthalpyProvider:
        # Simple monotonic enthalpy model for deterministic duty-flash behavior.
        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            z = np.asarray(z, dtype=float).reshape((-1,))
            z = z / max(float(np.sum(z)), 1e-300)
            K = np.full_like(z, 0.5)
            HL = float(T_F)
            HV = float(T_F) + 100.0
            return z, z, K, HL, HV

    provider = LinearEnthalpyProvider()

    base_inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=7200.0, boilup_lbmolph=None, bottoms_lbmolph=0.0),
        thermo_provider=provider,
        reboiler_mode="duty",
        reboiler_duty_btu_per_h=36000.0,  # +10 BTU/s
        reboiler_equilibrium=False,
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=0.0,
    )
    _dydt1, diag1 = column_rhs(0.0, y0, col2, layout, inputs=base_inputs)
    T_reb_1 = float(np.asarray(diag1["reb_T_F"], dtype=float).reshape((-1,))[0])
    beta_1 = float(np.asarray(diag1["reb_beta"], dtype=float).reshape((-1,))[0])
    x_1 = np.asarray(diag1["reb_x"], dtype=float).reshape((2,))
    y_1 = np.asarray(diag1["reb_y"], dtype=float).reshape((2,))

    y1 = y0.copy()
    tray_T1 = np.asarray(y1[sl["tray_T_f"]], dtype=float).reshape((2,)).copy()
    tray_T1[0] = 250.0  # raise stage-N-1 inlet temperature significantly
    y1[sl["tray_T_f"]] = tray_T1

    inputs_step2 = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=7200.0, boilup_lbmolph=None, bottoms_lbmolph=0.0),
        thermo_provider=provider,
        reboiler_mode="duty",
        reboiler_duty_btu_per_h=36000.0,
        reboiler_equilibrium=False,
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=0.0,
        reb_T_prev=float(T_reb_1),
        reb_x_prev=x_1.copy(),
        reb_y_prev=y_1.copy(),
        reb_beta_prev=float(beta_1),
    )
    _dydt2, diag2 = column_rhs(1.0, y1, col2, layout, inputs=inputs_step2)
    T_reb_2 = float(np.asarray(diag2["reb_T_F"], dtype=float).reshape((-1,))[0])
    flash_ok_2 = float(np.asarray(diag2["reb_flash_ok"], dtype=float).reshape((-1,))[0])

    # Cached state is allowed as a seed, but duty flash must re-solve from the
    # updated inlet each step (i.e., no frozen reboiler temperature).
    assert np.isfinite(T_reb_1)
    assert np.isfinite(T_reb_2)
    assert T_reb_2 > (T_reb_1 + 20.0)
    assert flash_ok_2 >= 0.5


def test_no_holdup_reboiler_skips_bubblepoint_temperature_closure(monkeypatch):
    col = _make_tiny_column()
    col2 = ColumnSpec(
        **{
            **col.__dict__,
            # Trigger no-holdup reboiler mode on stage N.
            "M_L_lbmol": np.array([5.0, 0.0], dtype=float),
            "streams": {},
        }
    )

    layout = StateVectorLayout(
        n_stages=2,
        n_components=2,
        include_top=False,
        include_bottom=True,
        include_vapor=True,
        include_temperature=True,
        include_energy=False,
    )
    y0 = layout.pack_y0(col2)
    sl = layout.slices()
    tray_T = np.asarray(y0[sl["tray_T_f"]], dtype=float).reshape((2,)).copy()
    tray_T[1] = 220.0
    y0[sl["tray_T_f"]] = tray_T

    class FlatProvider:
        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            z = np.asarray(z, dtype=float).reshape((-1,))
            z = z / max(float(np.sum(z)), 1e-300)
            K = np.full_like(z, 0.7)
            return z, z, K, -1000.0, -500.0

    bubble_calls = {"n": 0}

    def _fake_bubble_point_T_F(**kwargs):
        bubble_calls["n"] += 1

        class _Res:
            y = np.asarray(kwargs.get("x", [0.5, 0.5]), dtype=float)
            K = np.ones_like(y, dtype=float)

        return 168.0, _Res()

    monkeypatch.setattr(rhs_module, "_bubble_point_T_F", _fake_bubble_point_T_F)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=7200.0, boilup_lbmolph=11743.5, bottoms_lbmolph=0.0),
        thermo_provider=FlatProvider(),
        reboiler_mode="auto",
        reboiler_equilibrium=True,  # should be ignored for no-holdup mode
        condenser_duty_mode="specified",
        condenser_duty_btu_per_h=0.0,
    )
    _dydt, diag = column_rhs(0.0, y0, col2, layout, inputs=inputs)
    T_reb = float(np.asarray(diag["reb_T_F"], dtype=float).reshape((-1,))[0])

    # No-holdup reboiler should not run bubble-point closure.
    assert bubble_calls["n"] == 0
    assert abs(T_reb - 220.0) < 1e-9


def test_hydraulic_pressure_profile_applies_fixed_condenser_pressure_drop():
    n = 3
    area = math.pi * (10.0 * 0.5) ** 2
    geom = ColumnGeometry(
        sections=[ColumnGeometrySection(start_stage_1based=1, end_stage_1based=3, diameter_ft=10.0, tray_spacing_ft=1.0, gas_void_frac=0.7)],
        diameter_ft_per_stage=np.full(n, 10.0, dtype=float),
        tray_spacing_ft_per_stage=np.full(n, 1.0, dtype=float),
        gas_void_frac_per_stage=np.full(n, 0.7, dtype=float),
        area_ft2_per_stage=np.full(n, area, dtype=float),
        vapor_volume_ft3_per_stage=np.full(n, area * 0.7, dtype=float),
        active_area_frac_per_stage=np.full(n, 0.7, dtype=float),
        active_area_ft2_per_stage=np.full(n, area * 0.7, dtype=float),
    )

    T_F = np.array([120.0, 130.0, 140.0], dtype=float)
    V_in = np.zeros(n, dtype=float)
    y = np.full((n, 2), 0.5, dtype=float)
    x = np.full((n, 2), 0.5, dtype=float)
    Z = np.ones(n, dtype=float)

    p_no_drop = _pressure_profile_hydraulic_psia(
        P_bottom_psia=232.0,
        T_F=T_F,
        V_in_lbmolps=V_in,
        y_tray=y,
        x_tray=x,
        Z_vap=Z,
        geom=geom,
        h_ow_ft=np.zeros(n, dtype=float),
        rhoL_lbmol_ft3=None,
        mw_components=None,
        dry_tray_K=0.0,
        condenser_pressure_drop_psi=None,
    )
    p_with_drop = _pressure_profile_hydraulic_psia(
        P_bottom_psia=232.0,
        T_F=T_F,
        V_in_lbmolps=V_in,
        y_tray=y,
        x_tray=x,
        Z_vap=Z,
        geom=geom,
        h_ow_ft=np.zeros(n, dtype=float),
        rhoL_lbmol_ft3=None,
        mw_components=None,
        dry_tray_K=0.0,
        condenser_pressure_drop_psi=2.0,
    )

    assert abs(float(p_no_drop[1]) - float(p_no_drop[0])) < 1e-12
    assert abs((float(p_with_drop[1]) - float(p_with_drop[0])) - 2.0) < 1e-9
