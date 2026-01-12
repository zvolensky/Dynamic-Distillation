import numpy as np

from dynamic_distillation.column_spec_builder_v1 import ColumnSpec, HeatDuties, SimulationSettings
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.column_rhs_v1 import column_rhs, ColumnInputs, VolumeModel


class _ThermoProviderWithZ:
    """Fake provider: returns a constant Z-factor to test real-gas pressure diagnostics."""

    def __init__(self, Z: float = 0.8):
        self.Z = float(Z)

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        z = np.asarray(z, dtype=float)
        z = z / max(float(z.sum()), 1e-300)
        x = z.copy()
        y = z.copy()
        K = np.ones_like(z)
        HL = -1000.0
        HV = 500.0
        return x.tolist(), y.tolist(), K.tolist(), HL, HV, self.Z


def _make_tiny_column() -> ColumnSpec:
    N, Nc = 2, 2
    x0 = np.array([[0.8, 0.2], [0.3, 0.7]], dtype=float)
    y0 = np.array([[0.9, 0.1], [0.4, 0.6]], dtype=float)

    return ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 2, "Number of Components": 2, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
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


def test_pressure_diagnostic_uses_Z_when_available():
    col = _make_tiny_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=True, include_bottom=True, include_vapor=True)

    y0 = layout.pack_y0(col)

    provider = _ThermoProviderWithZ(Z=0.8)
    inputs = ColumnInputs(
        thermo_provider=provider,
        compute_thermo_diag=True,
        volume_model=VolumeModel(default_vapor_volume_ft3=1.0),
    )

    _dydt, diag = column_rhs(0.0, y0, col, layout, inputs=inputs)

    assert "Z_tray" in diag
    assert np.allclose(diag["Z_tray"], np.array([0.8, 0.8], dtype=float))

    # Expected: P = n Z R T / V (tray diagnostic uses MV holdup and col.T_f)
    R = 10.7316
    T_R = col.T_f + 459.67
    MV = col.M_V_lbmol
    P_expected = MV * 0.8 * R * T_R / 1.0

    assert np.allclose(diag["P_psia_diag"], P_expected)