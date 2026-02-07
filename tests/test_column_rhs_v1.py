import numpy as np

from dynamic_distillation.column_spec_builder_v1 import (
    ColumnSpec,
    ColumnGeometry,
    ColumnGeometrySection,
    HeatDuties,
    SimulationSettings,
)
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.column_rhs_v1 import column_rhs, ColumnInputs, BoundaryFlows
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

    reflux_s = 6.0 / 3600.0
    boilup_s = 12.0 / 3600.0

    expected_d_top = boilup_s * y_in0 - reflux_s * x_topL
    d_top = dydt[sl["top_L"]].reshape((2,))
    assert np.allclose(d_top, expected_d_top, atol=1e-12)

    d_tray_L = dydt[sl["tray_L"]].reshape((2, 2))
    assert np.allclose(d_tray_L[0, :], d_top, atol=1e-12)


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
