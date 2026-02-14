import numpy as np

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
    assert abs(float(v_cond_in) - 0.5) < 1e-12
    assert abs(float(v_to_top) - 0.5) < 1e-12
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
    assert abs(float(v_cond_top) - 0.4) < 1e-12


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

    # Reboiler-neighbor guard is +/-2% around boilup for stage N-1.
    # boilup = 3600 lbmol/h => upper cap = 3672 lbmol/h.
    assert np.isclose(v_out[2], 3672.0, rtol=1e-9, atol=1e-9)


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
