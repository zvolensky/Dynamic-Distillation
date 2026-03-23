"""
test_module8b_equilibrium_relaxation.py

Dynamic Distillation - Module 8B Equilibrium Relaxation Tests

PURPOSE
-------
Verify equilibrium-relaxation behavior in RHS using deterministic fake
K-value providers and zero-flow baseline fixtures.

SCOPE
-----
- relaxation source term activation and expected directional behavior
- compatibility with minimal column fixtures and boundary settings

KEY DEPENDENCIES
----------------
- column_rhs_v1 / StateVectorLayout / ColumnSpec fixtures
- numpy
"""


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


def _make_zero_flow_column_3stage() -> ColumnSpec:
    N, Nc = 3, 2
    x0 = np.array([[0.8, 0.2], [0.6, 0.4], [0.3, 0.7]], dtype=float)
    y0 = np.array([[0.9, 0.1], [0.7, 0.3], [0.4, 0.6]], dtype=float)

    return ColumnSpec(
        excel_path="<unit-test>",
        components_excel=["A", "B"],
        components_dwsim=["A", "B"],
        n_components=Nc,
        n_stages=N,
        stage_1based=np.array([1, 2, 3], dtype=int),
        sim=SimulationSettings(dt_sec=1.0, t_final_sec=10.0, log_every_n_steps=1),
        duties=HeatDuties(condenser_type="Total", q_cond_btu_per_h=0.0, q_reb_btu_per_h=0.0),
        specs_raw={"Number of Stages": 3, "Number of Components": 2, "Timestep (sec)": 1.0, "Simulation Length (min)": 0.1, "Log Frequency (timesteps)": 1},
        T_f=np.array([100.0, 110.0, 120.0], dtype=float),
        P_psia=np.array([200.0, 205.0, 210.0], dtype=float),
        V_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        L_lbmolph=np.array([0.0, 0.0, 0.0], dtype=float),
        M_L_lbmol=np.array([5.0, 5.0, 5.0], dtype=float),
        M_V_lbmol=np.array([1.0, 0.2, 1.0], dtype=float),
        y0=y0,
        x0=x0,
        streams={},
    )


def test_equilibrium_relaxation_relaxes_to_flash_targets_with_net_phase_change():
    col = _make_zero_flow_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
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

    # Transfer is equal-and-opposite between phases per component.
    assert np.allclose(dL + dV, 0.0, atol=1e-12)
    transfer = np.asarray(diag["eq_transfer_lbmolps_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    assert np.allclose(dV, transfer, atol=1e-12)
    assert np.allclose(dL, -transfer, atol=1e-12)

    # Net phase change is allowed and expected from flash-target relaxation.
    phase_change = np.asarray(diag["eq_phase_change_lbmolps_tray"], dtype=float).reshape((col.n_stages,))
    assert np.any(np.abs(phase_change) > 1e-12)

    # Diagnostics present
    assert "x_eq_tray" in diag
    assert "y_eq_tray" in diag
    assert "beta_eq_tray" in diag
    assert "eq_transfer_lbmolps_tray" in diag
    dml_transport = np.asarray(diag["dMLdt_transport_lbmolps_tray"], dtype=float).reshape((col.n_stages,))
    dml_phase = np.asarray(diag["dMLdt_phase_relax_lbmolps_tray"], dtype=float).reshape((col.n_stages,))
    dml_total = np.asarray(diag["dMLdt_total_lbmolps_tray"], dtype=float).reshape((col.n_stages,))
    assert np.allclose(dml_transport + dml_phase, dml_total, atol=1e-12)
    assert np.allclose(dml_phase, -phase_change, atol=1e-12)


def test_equilibrium_relaxation_composition_only_mode_keeps_net_phase_change_near_zero():
    col = _make_zero_flow_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
    y0_vec = layout.pack_y0(col)

    K = np.array([2.0, 0.5], dtype=float)
    provider = _ThermoProviderWithK(K=K)

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="composition-only",
        tau_eq_sec=10.0,
    )

    dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)
    sl = layout.slices()
    dL = dydt[sl["tray_L"]].reshape((col.n_stages, col.n_components))
    dV = dydt[sl["tray_V"]].reshape((col.n_stages, col.n_components))
    assert np.allclose(dL + dV, 0.0, atol=1e-12)

    phase_change = np.asarray(diag["eq_phase_change_lbmolps_tray"], dtype=float).reshape((col.n_stages,))
    assert np.allclose(phase_change, 0.0, atol=1e-12)
    mode_flag = float(np.asarray(diag["eq_relaxation_mode_comp_only"], dtype=float).reshape((-1,))[0])
    assert mode_flag == 1.0


def test_equilibrium_relaxation_uses_cached_k_without_live_thermo_provider():
    col = _make_zero_flow_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
    y0_vec = layout.pack_y0(col)

    K_prev = np.array([[2.0, 0.5], [2.0, 0.5]], dtype=float)
    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=None,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="composition-only",
        tau_eq_sec=10.0,
        K_tray_prev=K_prev,
        HL_prev=np.zeros(2, dtype=float),
        HV_prev=np.zeros(2, dtype=float),
        Zfac_prev=np.ones(2, dtype=float),
    )

    dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)
    assert np.all(np.isfinite(dydt))
    assert "eq_transfer_lbmolps_tray" in diag
    assert "K_tray" in diag
    cache_flag = float(np.asarray(diag["thermo_flash_cached_only"], dtype=float).reshape((-1,))[0])
    assert cache_flag == 1.0


def test_phase_holdup_guard_softens_near_empty_vapor_target():
    col = _make_zero_flow_column_3stage()
    layout = StateVectorLayout(n_stages=3, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
    y0_vec = layout.pack_y0(col)

    K = np.array([0.02, 0.01], dtype=float)
    provider = _ThermoProviderWithK(K=K)

    inputs_plain = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="phase-holdup",
        equilibrium_phase_holdup_guard_lbmol=0.0,
        tau_eq_sec=10.0,
    )
    _dydt_plain, diag_plain = column_rhs(0.0, y0_vec, col, layout, inputs=inputs_plain)

    inputs_guard = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="phase-holdup",
        equilibrium_phase_holdup_guard_lbmol=1.0,
        tau_eq_sec=10.0,
    )
    _dydt_guard, diag_guard = column_rhs(0.0, y0_vec, col, layout, inputs=inputs_guard)

    target_plain = np.asarray(diag_plain["eq_target_vapor_lbmol_tray"], dtype=float).reshape((3, 2))
    target_guard = np.asarray(diag_guard["eq_target_vapor_lbmol_tray"], dtype=float).reshape((3, 2))
    weight_guard = np.asarray(diag_guard["eq_phase_holdup_guard_weight_tray"], dtype=float).reshape((3,))

    # Middle tray starts with a small vapor holdup; guard should soften collapse.
    assert np.sum(target_guard[1, :]) > np.sum(target_plain[1, :])
    assert 0.0 < float(weight_guard[1]) < 1.0
