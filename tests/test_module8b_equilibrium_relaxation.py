import numpy as np

from dynamic_distillation.column_spec_builder_v1 import ColumnSpec, HeatDuties, SimulationSettings
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.column_rhs_v1 import column_rhs, ColumnInputs, BoundaryFlows


class _ThermoProviderWithK:
    def __init__(self, K):
        self._K = np.asarray(K, dtype=float)

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        z = np.asarray(z, dtype=float)
        Nc = z.size
        K = self._K.reshape((Nc,))
        # Return 6-tuple so stage_thermo_v1 can pass through optional Z
        return z.tolist(), z.tolist(), K.tolist(), 0.0, 0.0, 1.0


def _make_zero_flow_column() -> ColumnSpec:
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
        specs_raw={"Number of Stages": 2, "Number of Components": 2, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 210.0], dtype=float),
        V_lbmolph=np.array([0.0, 0.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )


def test_equilibrium_relaxation_adds_equal_and_opposite_transfer_terms():
    col = _make_zero_flow_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=True, include_bottom=True, include_vapor=True)
    y0_vec = layout.pack_y0(col)

    K = np.array([2.0, 0.5], dtype=float)
    provider = _ThermoProviderWithK(K=K)

    tau = 10.0
    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        tau_eq_sec=tau,
    )

    dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)

    sl = layout.slices()
    dL = dydt[sl["tray_L"]].reshape((col.n_stages, col.n_components))
    dV = dydt[sl["tray_V"]].reshape((col.n_stages, col.n_components))

    # expected transfer = (MV/tau) * (y_eq - y)
    x = col.x0
    y = col.y0
    y_eq_raw = (K[None, :] * x)
    y_eq = y_eq_raw / np.sum(y_eq_raw, axis=1, keepdims=True)
    MV = col.M_V_lbmol.reshape((col.n_stages, 1))
    expected = (MV / tau) * (y_eq - y)

    assert np.allclose(dV, expected, atol=1e-12)
    assert np.allclose(dL, -expected, atol=1e-12)

    # Each phase total should be unchanged by the transfer (sums to ~0 per stage)
    assert np.allclose(np.sum(dV, axis=1), 0.0, atol=1e-12)
    assert np.allclose(np.sum(dL, axis=1), 0.0, atol=1e-12)

    # Diagnostics present
    assert "y_eq_tray" in diag
    assert "eq_transfer_lbmolps_tray" in diag
