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
from dynamic_distillation.column_rhs_v1 import (
    BoundaryFlows,
    ColumnInputs,
    _limit_equilibrium_component_transfer_by_transport,
    _transport_balanced_phase_transfer,
    column_rhs,
)


class _ThermoProviderWithK:
    def __init__(self, K):
        self._K = np.asarray(K, dtype=float)

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        z = np.asarray(z, dtype=float)
        Nc = z.size
        K = self._K.reshape((Nc,))
        # Return 6-tuple so stage_thermo_v1 can pass through optional Z
        return z.tolist(), z.tolist(), K.tolist(), 0.0, 0.0, 1.0


class _DirectAlphaThermoProvider:
    uses_direct_vapor_equilibrium = True
    uses_liquid_composition_for_equilibrium = True

    def __init__(self, alpha):
        self.alpha = np.asarray(alpha, dtype=float)

    def equilibrium_y_K_from_x(self, x):
        x = np.asarray(x, dtype=float).reshape((-1,))
        x = x / max(float(np.sum(x)), 1e-300)
        y_raw = self.alpha * x
        denom = max(float(np.sum(y_raw)), 1e-300)
        return y_raw / denom, self.alpha / denom

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        x = np.asarray(z, dtype=float).reshape((-1,))
        y, K = self.equilibrium_y_K_from_x(x)
        return x.tolist(), y.tolist(), K.tolist(), 0.0, 0.0, 1.0


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
    col = _make_zero_flow_column_3stage()
    layout = StateVectorLayout(n_stages=3, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
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


def test_equilibrium_component_transfer_guard_limits_transport_overshoot():
    col = _make_zero_flow_column_3stage()
    col = ColumnSpec(
        **{
            **col.__dict__,
            "M_V_lbmol": np.array([1.0, 10.0, 1.0], dtype=float),
            "V_lbmolph": np.array([0.0, 3600.0, 3600.0], dtype=float),
            "y0": np.array(
                [
                    [0.5, 0.5],
                    [0.50, 0.50],
                    [0.51, 0.49],
                ],
                dtype=float,
            ),
            "x0": np.array(
                [
                    [0.5, 0.5],
                    [0.50, 0.50],
                    [0.51, 0.49],
                ],
                dtype=float,
            ),
        }
    )
    layout = StateVectorLayout(n_stages=3, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
    y0_vec = layout.pack_y0(col)

    class StrongShiftProvider:
        uses_direct_vapor_equilibrium = True
        uses_liquid_composition_for_equilibrium = True

        def equilibrium_y_K_from_x(self, x):
            return np.array([0.9, 0.1], dtype=float), np.array([1.8, 0.2], dtype=float)

        def flash_TP_full_F_psia(self, T_F, P_psia, z):
            return [0.5, 0.5], [0.9, 0.1], [1.8, 0.2], 0.0, 0.0, 1.0

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=StrongShiftProvider(),
        equilibrium_relaxation_thermo_provider=StrongShiftProvider(),
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="composition-only",
        tau_eq_sec=1.0,
        equilibrium_component_transfer_max_cancel_multiplier=1.5,
        equilibrium_component_transfer_floor_lbmolps=0.0,
    )

    _dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)

    pre = np.asarray(diag["tray_V_pre_equilibrium_rhs_lbmolps"], dtype=float).reshape((3, 2))
    transfer = np.asarray(diag["eq_transfer_lbmolps_tray"], dtype=float).reshape((3, 2))
    scale = np.asarray(diag["eq_component_transfer_guard_scale_tray"], dtype=float).reshape((3,))

    # Middle tray has a small transport residual but a large equilibrium target
    # shift. The component guard should scale the whole row so no component
    # exceeds 1.5x the local pre-equilibrium material motion.
    assert float(scale[1]) < 1.0
    assert np.all(np.abs(transfer[1, :]) <= 1.5 * np.abs(pre[1, :]) + 1.0e-12)


def test_composition_exponential_relaxation_applies_exact_bounded_split_step():
    col = _make_zero_flow_column_3stage()
    layout = StateVectorLayout(
        n_stages=3,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
    )
    y0_vec = layout.pack_y0(col)
    provider = _DirectAlphaThermoProvider([2.0, 0.5])
    dt = 0.2
    tau = 0.5
    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="composition-exponential",
        equilibrium_step_dt_sec=dt,
        tau_eq_sec=tau,
        equilibrium_component_transfer_max_cancel_multiplier=1.0,
    )

    dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)
    sl = layout.slices()
    tray_V0 = y0_vec[sl["tray_V"]].reshape((3, 2))
    tray_L0 = y0_vec[sl["tray_L"]].reshape((3, 2))
    dV = dydt[sl["tray_V"]].reshape((3, 2))
    dL = dydt[sl["tray_L"]].reshape((3, 2))
    y_target = np.asarray(diag["y_target_tray"], dtype=float).reshape((3, 2))
    alpha = 1.0 - np.exp(-dt / tau)

    middle_total = float(np.sum(tray_V0[1, :]))
    expected_middle = (1.0 - alpha) * tray_V0[1, :] + alpha * middle_total * y_target[1, :]
    actual_middle = tray_V0[1, :] + dt * dV[1, :]

    assert np.allclose(actual_middle, expected_middle, atol=1.0e-12)
    assert np.all(actual_middle >= 0.0)
    assert np.isclose(np.sum(actual_middle), middle_total, atol=1.0e-12)
    assert np.allclose(dL + dV, 0.0, atol=1.0e-12)
    assert np.isclose(float(np.asarray(diag["eq_exponential_alpha"]).reshape((-1,))[0]), alpha)
    assert float(np.asarray(diag["eq_exponential_split_active"]).reshape((-1,))[0]) == 1.0
    assert np.all(tray_L0[1, :] + dt * dL[1, :] >= 0.0)


def test_transport_balanced_phase_transfer_cancels_only_active_tray_vapor_totals():
    pre = np.array(
        [
            [1.0, -0.5],
            [-0.3, -0.2],
            [0.4, 0.6],
        ],
        dtype=float,
    )
    y_eq = np.array(
        [
            [0.7, 0.3],
            [0.8, 0.2],
            [0.6, 0.4],
        ],
        dtype=float,
    )
    y_current = np.array(
        [
            [0.5, 0.5],
            [0.25, 0.75],
            [0.4, 0.6],
        ],
        dtype=float,
    )

    transfer, required = _transport_balanced_phase_transfer(
        pre,
        vaporization_composition=y_eq,
        current_vapor_composition=y_current,
        active_trays=np.array([False, True, True]),
    )

    assert np.allclose(required, [0.0, 0.5, -1.0])
    assert np.allclose(transfer[0, :], 0.0)
    assert np.allclose(transfer[1, :], 0.5 * y_eq[1, :])
    assert np.allclose(transfer[2, :], -1.0 * y_current[2, :])
    assert np.allclose(np.sum(pre + transfer, axis=1)[1:], 0.0)


def test_transport_balanced_phase_transfer_is_opt_in_and_reports_closure():
    col = _make_zero_flow_column_3stage()
    col.V_lbmolph[:] = np.array([0.0, 360.0, 0.0], dtype=float)
    layout = StateVectorLayout(
        n_stages=3,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
    )
    y0_vec = layout.pack_y0(col)
    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=_DirectAlphaThermoProvider([2.0, 0.5]),
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="composition-exponential",
        equilibrium_transport_balanced_phase_transfer=True,
        equilibrium_step_dt_sec=0.2,
        tau_eq_sec=0.5,
    )

    dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)
    sl = layout.slices()
    dL = dydt[sl["tray_L"]].reshape((3, 2))
    dV = dydt[sl["tray_V"]].reshape((3, 2))
    residual = np.asarray(
        diag["eq_transport_balance_residual_lbmolps_tray"], dtype=float
    ).reshape((3,))
    required = np.asarray(
        diag["eq_transport_balance_required_lbmolps_tray"], dtype=float
    ).reshape((3,))
    phase_change = np.asarray(
        diag["eq_phase_change_lbmolps_tray"], dtype=float
    ).reshape((3,))

    assert float(np.asarray(diag["eq_transport_balance_active"]).reshape((-1,))[0]) == 1.0
    assert np.isclose(residual[1], 0.0, atol=1.0e-12)
    assert np.isclose(np.sum(dV[1, :]), 0.0, atol=1.0e-12)
    assert np.isclose(phase_change[1], required[1], atol=1.0e-12)
    assert np.isclose(np.sum(dL[1, :] + dV[1, :]), -required[1], atol=1.0e-12)


def test_phase_exponential_relaxation_changes_phase_total_without_changing_total_inventory():
    col = _make_zero_flow_column_3stage()
    layout = StateVectorLayout(
        n_stages=3,
        n_components=2,
        include_top=False,
        include_bottom=False,
        include_vapor=True,
    )
    y0_vec = layout.pack_y0(col)
    provider = _ThermoProviderWithK([2.0, 0.5])
    dt = 0.2
    tau = 0.5
    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="phase-exponential",
        equilibrium_step_dt_sec=dt,
        tau_eq_sec=tau,
    )

    dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)
    sl = layout.slices()
    tray_V0 = y0_vec[sl["tray_V"]].reshape((3, 2))
    tray_L0 = y0_vec[sl["tray_L"]].reshape((3, 2))
    dV = dydt[sl["tray_V"]].reshape((3, 2))
    dL = dydt[sl["tray_L"]].reshape((3, 2))
    target = np.asarray(diag["eq_target_vapor_lbmol_tray"], dtype=float).reshape((3, 2))

    actual_middle = tray_V0[1, :] + dt * dV[1, :]

    assert np.linalg.norm(actual_middle - target[1, :]) < np.linalg.norm(tray_V0[1, :] - target[1, :])
    assert not np.isclose(np.sum(actual_middle), np.sum(tray_V0[1, :]), atol=1.0e-12)
    assert np.allclose(dL + dV, 0.0, atol=1.0e-12)
    assert np.all(tray_L0[1, :] + dt * dL[1, :] >= 0.0)
    assert np.all(actual_middle >= 0.0)
    assert float(np.asarray(diag["eq_exponential_split_active"]).reshape((-1,))[0]) == 1.0


def test_equilibrium_component_transfer_guard_limits_same_direction_amplification():
    transfer = np.array(
        [
            [-3.0, 1.0],
            [-3.0, 1.0],
        ],
        dtype=float,
    )
    pre = np.array(
        [
            [-1.0, 1.0],
            [1.0, -1.0],
        ],
        dtype=float,
    )

    adjusted, scale, limit = _limit_equilibrium_component_transfer_by_transport(
        transfer,
        pre,
        max_cancel_multiplier=1.5,
        floor_lbmolps=0.0,
    )

    assert np.allclose(adjusted[0, :], [-0.5, 1.0 / 6.0])
    assert np.isclose(scale[0], 1.0 / 6.0)
    assert np.isclose(limit[0], 0.5)
    assert np.allclose(adjusted[1, :], [-1.5, 0.5])
    assert np.isclose(scale[1], 0.5)
    assert np.isclose(limit[1], 1.5)


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


def test_equilibrium_relaxation_can_override_flash_k_with_selective_provider():
    col = _make_zero_flow_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
    y0_vec = layout.pack_y0(col)

    provider_table = _ThermoProviderWithK(np.array([2.0, 0.5], dtype=float))
    provider_live = _ThermoProviderWithK(np.array([1.2, 0.9], dtype=float))

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider_table,
        equilibrium_relaxation_thermo_provider=provider_live,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        tau_eq_sec=10.0,
    )

    _dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)

    k_main = np.asarray(diag["K_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    k_relax = np.asarray(diag["K_eq_relax_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    override_flag = float(np.asarray(diag["eq_relax_thermo_override_active"], dtype=float).reshape((-1,))[0])

    assert np.allclose(k_main, np.array([[2.0, 0.5], [2.0, 0.5]], dtype=float))
    assert np.allclose(k_relax, np.array([[1.2, 0.9], [1.2, 0.9]], dtype=float))
    assert override_flag == 1.0


def test_direct_vapor_equilibrium_provider_bypasses_rr_split():
    col = _make_zero_flow_column()
    layout = StateVectorLayout(n_stages=2, n_components=2, include_top=False, include_bottom=False, include_vapor=True)
    y0_vec = layout.pack_y0(col)
    provider = _DirectAlphaThermoProvider([2.0, 1.0])

    inputs = ColumnInputs(
        boundary=BoundaryFlows(reflux_lbmolph=0.0, boilup_lbmolph=0.0),
        thermo_provider=provider,
        equilibrium_relaxation_thermo_provider=provider,
        compute_thermo_diag=False,
        equilibrium_relaxation=True,
        equilibrium_relaxation_mode="phase-holdup",
        tau_eq_sec=10.0,
    )

    _dydt, diag = column_rhs(0.0, y0_vec, col, layout, inputs=inputs)

    x_eq = np.asarray(diag["x_eq_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    y_eq = np.asarray(diag["y_eq_tray"], dtype=float).reshape((col.n_stages, col.n_components))
    beta_eq = np.asarray(diag["beta_eq_tray"], dtype=float).reshape((col.n_stages,))
    target_v = np.asarray(diag["eq_target_vapor_lbmol_tray"], dtype=float).reshape((col.n_stages, col.n_components))

    expected_y = np.vstack([provider.equilibrium_y_K_from_x(row)[0] for row in col.x0])
    assert np.allclose(x_eq, col.x0, atol=1e-12)
    assert np.allclose(y_eq, expected_y, atol=1e-12)
    assert np.allclose(beta_eq, col.M_V_lbmol / (col.M_L_lbmol + col.M_V_lbmol), atol=1e-12)
    assert np.allclose(np.sum(target_v, axis=1), col.M_V_lbmol, atol=1e-12)


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
