from __future__ import annotations

from contextlib import contextmanager

import numpy as np

from dynamic_distillation import column_rhs_v1 as rhs_module
from dynamic_distillation.thermo_step_coordinator_v1 import (
    refresh_energy_vapor_flow_phase_enthalpies,
    refresh_temperature_state_phase_enthalpies,
    refresh_tray_tp_packet,
)


def test_refresh_tray_tp_packet_skips_all_when_states_match_thresholds():
    n_stages = 3
    n_components = 2
    z = np.array([[0.8, 0.2], [0.5, 0.5], [0.2, 0.8]], dtype=float)
    packet = rhs_module.TrayThermoPacket(
        z_overall_tray=z.copy(),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.full(n_stages, -10.0, dtype=float),
        HV_BTU_lbmol_tray=np.full(n_stages, 10.0, dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
        T_tray_F=np.array([100.0, 120.0, 140.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0, 220.0], dtype=float),
    )

    class Provider:
        def flash_TP_full_batch(self, *args, **kwargs):
            raise AssertionError("batch flash should not be called when all stages are skipped")

    result = refresh_tray_tp_packet(
        packet=packet,
        provider=Provider(),
        T_tray_F=np.array([100.0, 120.0, 140.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0, 220.0], dtype=float),
        z_overall_tray=z,
        n_stages=n_stages,
        n_components=n_components,
        dT_thresh_F=1.0e-3,
        dP_thresh_psia=1.0e-3,
        dX_thresh=1.0e-8,
        T_prev_F=np.array([100.0, 120.0, 140.0], dtype=float),
        P_prev_psia=np.array([200.0, 210.0, 220.0], dtype=float),
        z_prev=z.copy(),
        ensure_packet_equilibrium_arrays=rhs_module._ensure_packet_equilibrium_arrays,
        flash_stage_fn=rhs_module._flash_TP_full_stage_F_psia,
    )

    assert result.batch_used is False
    assert result.refresh_indices == ()
    assert np.allclose(result.flash_skipped, np.ones(n_stages, dtype=float))
    assert np.allclose(result.flash_refreshed, np.zeros(n_stages, dtype=float))


def test_refresh_tray_tp_packet_uses_batch_backend_when_available():
    n_stages = 3
    n_components = 2
    z = np.array([[0.8, 0.2], [0.5, 0.5], [0.2, 0.8]], dtype=float)
    packet = rhs_module.TrayThermoPacket(
        z_overall_tray=z.copy(),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.full(n_stages, -10.0, dtype=float),
        HV_BTU_lbmol_tray=np.full(n_stages, 10.0, dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
    )

    class Provider:
        def __init__(self):
            self.calls = 0

        def flash_TP_full_batch(self, T_req, P_req, z_req):
            self.calls += 1
            assert len(T_req) == 1
            assert len(P_req) == 1
            assert len(z_req) == 1
            return [
                (
                    [0.6, 0.4],
                    [0.4, 0.6],
                    [2.0, 0.5],
                    -200.0,
                    200.0,
                    0.9,
                )
            ]

    provider = Provider()
    scalar_calls = []

    def _unexpected_scalar(*args, **kwargs):
        scalar_calls.append((args, kwargs))
        raise AssertionError("scalar flash path should not be used when batch succeeds")

    result = refresh_tray_tp_packet(
        packet=packet,
        provider=provider,
        T_tray_F=np.array([100.0, 120.0, 140.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0, 220.0], dtype=float),
        z_overall_tray=z,
        n_stages=n_stages,
        n_components=n_components,
        dT_thresh_F=1.0e-3,
        dP_thresh_psia=1.0,
        dX_thresh=1.0e-8,
        T_prev_F=np.array([100.0, 120.0, 140.0], dtype=float),
        P_prev_psia=np.array([200.0, 200.0, 220.0], dtype=float),
        z_prev=z.copy(),
        ensure_packet_equilibrium_arrays=rhs_module._ensure_packet_equilibrium_arrays,
        flash_stage_fn=_unexpected_scalar,
    )

    assert provider.calls == 1
    assert scalar_calls == []
    assert result.batch_used is True
    assert result.refresh_indices == (1,)
    assert np.allclose(result.flash_skipped, np.array([1.0, 0.0, 1.0], dtype=float))
    assert np.allclose(result.flash_refreshed, np.array([0.0, 1.0, 0.0], dtype=float))
    assert np.allclose(result.packet.K_tray[1, :], np.array([2.0, 0.5], dtype=float))
    assert result.packet.HL[1] == -200.0
    assert result.packet.HV[1] == 200.0
    assert result.packet.Zfac_tray[1] == 0.9


def test_refresh_tray_tp_packet_quarantines_degenerate_two_phase_unit_k_batch_result():
    n_stages = 1
    n_components = 2
    z = np.array([[0.55, 0.45]], dtype=float)
    packet = rhs_module.TrayThermoPacket(
        z_overall_tray=z.copy(),
        K_tray=np.array([[2.0, 0.5]], dtype=float),
        HL_BTU_lbmol_tray=np.array([-120.0], dtype=float),
        HV_BTU_lbmol_tray=np.array([220.0], dtype=float),
        Z_tray=np.array([0.8], dtype=float),
        x_equilibrium_tray=np.array([[0.7, 0.3]], dtype=float),
        y_equilibrium_tray=np.array([[0.4, 0.6]], dtype=float),
    )

    class Provider:
        def flash_TP_full_batch(self, T_req, P_req, z_req):
            return [
                (
                    [0.55, 0.45],
                    [0.55, 0.45],
                    [1.0, 1.0],
                    -999.0,
                    999.0,
                    0.95,
                    12.0,
                    20.0,
                )
            ]

        def flash_cached_phase_count_F_psia(self, T_F, P_psia, z_row):
            return 2.0

    result = refresh_tray_tp_packet(
        packet=packet,
        provider=Provider(),
        T_tray_F=np.array([120.0], dtype=float),
        P_tray_psia=np.array([210.0], dtype=float),
        z_overall_tray=z,
        n_stages=n_stages,
        n_components=n_components,
        dT_thresh_F=None,
        dP_thresh_psia=None,
        dX_thresh=None,
        T_prev_F=None,
        P_prev_psia=None,
        z_prev=None,
        ensure_packet_equilibrium_arrays=rhs_module._ensure_packet_equilibrium_arrays,
        flash_stage_fn=rhs_module._flash_TP_full_stage_F_psia,
    )

    assert result.batch_used is True
    assert np.allclose(result.flash_refreshed, np.ones(1, dtype=float))
    assert np.allclose(result.phase_count, np.array([2.0], dtype=float))
    assert np.allclose(result.degenerate_two_phase_unit_K_quarantined, np.ones(1, dtype=float))
    assert np.allclose(result.packet.K_tray[0, :], np.array([2.0, 0.5], dtype=float))
    assert result.packet.HL[0] == -120.0
    assert result.packet.HV[0] == 220.0


def test_refresh_tray_tp_packet_batch_preserves_cp_arrays_when_available():
    n_stages = 1
    n_components = 2
    z = np.array([[0.8, 0.2]], dtype=float)
    packet = rhs_module.TrayThermoPacket(
        z_overall_tray=z.copy(),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.full(n_stages, -10.0, dtype=float),
        HV_BTU_lbmol_tray=np.full(n_stages, 10.0, dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
    )

    class Provider:
        def flash_TP_full_batch(self, T_req, P_req, z_req):
            return [
                (
                    [0.6, 0.4],
                    [0.4, 0.6],
                    [2.0, 0.5],
                    -200.0,
                    200.0,
                    0.9,
                    12.3,
                    45.6,
                )
            ]

    result = refresh_tray_tp_packet(
        packet=packet,
        provider=Provider(),
        T_tray_F=np.array([120.0], dtype=float),
        P_tray_psia=np.array([210.0], dtype=float),
        z_overall_tray=z,
        n_stages=n_stages,
        n_components=n_components,
        dT_thresh_F=None,
        dP_thresh_psia=None,
        dX_thresh=None,
        T_prev_F=None,
        P_prev_psia=None,
        z_prev=None,
        ensure_packet_equilibrium_arrays=rhs_module._ensure_packet_equilibrium_arrays,
        flash_stage_fn=rhs_module._flash_TP_full_stage_F_psia,
    )

    assert result.batch_used is True
    assert result.packet.cpL_tray is not None
    assert result.packet.cpV_tray is not None
    assert result.packet.cpL_tray[0] == 12.3
    assert result.packet.cpV_tray[0] == 45.6


def test_refresh_tray_tp_packet_batch_uses_requested_thermo_category():
    n_stages = 1
    n_components = 2
    z = np.array([[0.8, 0.2]], dtype=float)
    packet = rhs_module.TrayThermoPacket(
        z_overall_tray=z.copy(),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.full(n_stages, -10.0, dtype=float),
        HV_BTU_lbmol_tray=np.full(n_stages, 10.0, dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
    )

    class Provider:
        def __init__(self):
            self.active_category = None
            self.batch_categories = []

        @contextmanager
        def thermo_call_category(self, category):
            prev = self.active_category
            self.active_category = str(category)
            try:
                yield
            finally:
                self.active_category = prev

        def flash_TP_full_batch(self, T_req, P_req, z_req):
            self.batch_categories.append(self.active_category)
            return [
                (
                    [0.6, 0.4],
                    [0.4, 0.6],
                    [2.0, 0.5],
                    -200.0,
                    200.0,
                    0.9,
                )
            ]

    provider = Provider()

    result = refresh_tray_tp_packet(
        packet=packet,
        provider=provider,
        T_tray_F=np.array([120.0], dtype=float),
        P_tray_psia=np.array([210.0], dtype=float),
        z_overall_tray=z,
        n_stages=n_stages,
        n_components=n_components,
        dT_thresh_F=None,
        dP_thresh_psia=None,
        dX_thresh=None,
        T_prev_F=None,
        P_prev_psia=None,
        z_prev=None,
        ensure_packet_equilibrium_arrays=rhs_module._ensure_packet_equilibrium_arrays,
        flash_stage_fn=rhs_module._flash_TP_full_stage_F_psia,
        thermo_call_category="startup_vapor_holdup_tray_refresh",
    )

    assert result.batch_used is True
    assert provider.batch_categories == ["startup_vapor_holdup_tray_refresh"]


def test_refresh_temperature_state_phase_enthalpies_reuses_energy_packet_for_vapor():
    n_stages = 2
    n_components = 2
    thermo_packet = rhs_module.TrayThermoPacket(
        z_overall_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.array([-100.0, -120.0], dtype=float),
        HV_BTU_lbmol_tray=np.array([100.0, 120.0], dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
        T_tray_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        y_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
    )
    energy_packet = rhs_module.TrayThermoPacket(
        z_overall_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.array([-90.0, -110.0], dtype=float),
        HV_BTU_lbmol_tray=np.array([150.0, 175.0], dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
        T_tray_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        y_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
    )

    scalar_calls = []

    def _unexpected_flash(*args, **kwargs):
        scalar_calls.append((args, kwargs))
        raise AssertionError("temperature-state enthalpy refresh should reuse packets here")

    result = refresh_temperature_state_phase_enthalpies(
        provider=object(),
        thermo_packet=thermo_packet,
        previous_packet=None,
        energy_vapor_flow_packet=energy_packet,
        tray_T_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        y_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        n_stages=n_stages,
        n_components=n_components,
        packet_phase_tol_liq=1.0e-6,
        packet_phase_tol_vap=1.0e-6,
        packet_dT_tol_F=1.0e-6,
        packet_dP_tol_psia=1.0e-6,
        packet_phase_enthalpy_first_match_fn=rhs_module._packet_phase_enthalpy_first_match,
        packet_phase_enthalpy_if_compatible_fn=rhs_module._packet_phase_enthalpy_if_compatible,
        flash_stage_fn=_unexpected_flash,
    )

    assert scalar_calls == []
    assert np.allclose(result.hL_stage_provider, np.array([-100.0, -120.0], dtype=float))
    assert np.allclose(result.hV_stage_provider, np.array([150.0, 175.0], dtype=float))


def test_refresh_temperature_state_phase_enthalpies_reuses_energy_packet_for_liquid_and_vapor():
    n_stages = 2
    n_components = 2
    energy_packet = rhs_module.TrayThermoPacket(
        z_overall_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.array([-90.0, -110.0], dtype=float),
        HV_BTU_lbmol_tray=np.array([150.0, 175.0], dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
        T_tray_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        y_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
    )

    scalar_calls = []

    def _unexpected_flash(*args, **kwargs):
        scalar_calls.append((args, kwargs))
        raise AssertionError("temperature-state enthalpy refresh should reuse the energy packet here")

    result = refresh_temperature_state_phase_enthalpies(
        provider=object(),
        thermo_packet=None,
        previous_packet=None,
        energy_vapor_flow_packet=energy_packet,
        tray_T_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        y_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        n_stages=n_stages,
        n_components=n_components,
        packet_phase_tol_liq=1.0e-6,
        packet_phase_tol_vap=1.0e-6,
        packet_dT_tol_F=1.0e-6,
        packet_dP_tol_psia=1.0e-6,
        packet_phase_enthalpy_first_match_fn=rhs_module._packet_phase_enthalpy_first_match,
        packet_phase_enthalpy_if_compatible_fn=rhs_module._packet_phase_enthalpy_if_compatible,
        flash_stage_fn=_unexpected_flash,
    )

    assert scalar_calls == []
    assert np.allclose(result.hL_stage_provider, np.array([-90.0, -110.0], dtype=float))
    assert np.allclose(result.hV_stage_provider, np.array([150.0, 175.0], dtype=float))


def test_refresh_energy_vapor_flow_phase_enthalpies_uses_batch_backend():
    n_stages = 2
    n_components = 1

    class Provider:
        def __init__(self):
            self.batch_calls = []

        def flash_TP_full_batch(self, T_req, P_req, z_req):
            self.batch_calls.append((list(T_req), list(P_req), [list(z) for z in z_req]))
            if len(self.batch_calls) == 1:
                return [
                    ([1.0], [1.0], [1.0], 150.0, 250.0, 1.0),
                    ([1.0], [1.0], [1.0], 175.0, 275.0, 1.0),
                ]
            return [
                ([1.0], [1.0], [1.0], 160.0, 260.0, 1.0),
                ([1.0], [1.0], [1.0], 185.0, 285.0, 1.0),
            ]

    scalar_calls = []

    def _unexpected_scalar(*args, **kwargs):
        scalar_calls.append((args, kwargs))
        raise AssertionError("energy vapor-flow helper should use batch path here")

    result = refresh_energy_vapor_flow_phase_enthalpies(
        provider=Provider(),
        current_packet=None,
        previous_packet=None,
        tray_T_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_tray=np.array([[1.0], [1.0]], dtype=float),
        y_tray=np.array([[1.0], [1.0]], dtype=float),
        n_stages=n_stages,
        n_components=n_components,
        packet_phase_tol_liq=1.0e-6,
        packet_phase_tol_vap=1.0e-6,
        packet_dT_tol_F=1.0e-6,
        packet_dP_tol_psia=1.0e-6,
        packet_phase_enthalpy_if_compatible_fn=rhs_module._packet_phase_enthalpy_if_compatible,
        flash_stage_fn=_unexpected_scalar,
        packet_factory=rhs_module.TrayThermoPacket,
    )

    assert scalar_calls == []
    assert np.allclose(result.hL_stage_provider, np.array([150.0, 175.0], dtype=float))
    assert np.allclose(result.hV_stage_provider, np.array([260.0, 285.0], dtype=float))
    assert result.packet is not None


def test_refresh_energy_vapor_flow_phase_enthalpies_batch_uses_category():
    n_stages = 1
    n_components = 1

    class Provider:
        def __init__(self):
            self.active_category = None
            self.batch_categories = []

        @contextmanager
        def thermo_call_category(self, category):
            prev = self.active_category
            self.active_category = str(category)
            try:
                yield
            finally:
                self.active_category = prev

        def flash_TP_full_batch(self, T_req, P_req, z_req):
            self.batch_categories.append(self.active_category)
            return [([1.0], [1.0], [1.0], 150.0, 250.0, 1.0)]

    provider = Provider()

    result = refresh_energy_vapor_flow_phase_enthalpies(
        provider=provider,
        current_packet=None,
        previous_packet=None,
        tray_T_F=np.array([100.0], dtype=float),
        P_tray_psia=np.array([200.0], dtype=float),
        x_tray=np.array([[1.0]], dtype=float),
        y_tray=np.array([[1.0]], dtype=float),
        n_stages=n_stages,
        n_components=n_components,
        packet_phase_tol_liq=1.0e-6,
        packet_phase_tol_vap=1.0e-6,
        packet_dT_tol_F=1.0e-6,
        packet_dP_tol_psia=1.0e-6,
        packet_phase_enthalpy_if_compatible_fn=rhs_module._packet_phase_enthalpy_if_compatible,
        flash_stage_fn=rhs_module._flash_TP_full_stage_F_psia,
        packet_factory=rhs_module.TrayThermoPacket,
    )

    assert result.hL_stage_provider is not None
    assert result.hV_stage_provider is not None
    assert result.packet is not None
    assert result.packet.HL[0] == 150.0
    assert result.packet.HV[0] == 250.0
    assert provider.batch_categories == [
        "energy_vapor_flow_enthalpy_refresh",
        "energy_vapor_flow_enthalpy_refresh",
    ]


def test_refresh_energy_vapor_flow_phase_enthalpies_reuses_current_packet_before_flashing():
    n_stages = 2
    n_components = 2
    current_packet = rhs_module.TrayThermoPacket(
        z_overall_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        K_tray=np.ones((n_stages, n_components), dtype=float),
        HL_BTU_lbmol_tray=np.array([-90.0, -110.0], dtype=float),
        HV_BTU_lbmol_tray=np.array([150.0, 175.0], dtype=float),
        Z_tray=np.ones(n_stages, dtype=float),
        T_tray_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        y_equilibrium_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
    )

    scalar_calls = []

    def _unexpected_scalar(*args, **kwargs):
        scalar_calls.append((args, kwargs))
        raise AssertionError("energy vapor-flow helper should reuse the current packet here")

    result = refresh_energy_vapor_flow_phase_enthalpies(
        provider=object(),
        current_packet=current_packet,
        previous_packet=None,
        tray_T_F=np.array([100.0, 120.0], dtype=float),
        P_tray_psia=np.array([200.0, 210.0], dtype=float),
        x_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        y_tray=np.array([[0.8, 0.2], [0.5, 0.5]], dtype=float),
        n_stages=n_stages,
        n_components=n_components,
        packet_phase_tol_liq=1.0e-6,
        packet_phase_tol_vap=1.0e-6,
        packet_dT_tol_F=1.0e-6,
        packet_dP_tol_psia=1.0e-6,
        packet_phase_enthalpy_if_compatible_fn=rhs_module._packet_phase_enthalpy_if_compatible,
        flash_stage_fn=_unexpected_scalar,
        packet_factory=rhs_module.TrayThermoPacket,
    )

    assert scalar_calls == []
    assert np.allclose(result.hL_stage_provider, np.array([-90.0, -110.0], dtype=float))
    assert np.allclose(result.hV_stage_provider, np.array([150.0, 175.0], dtype=float))
