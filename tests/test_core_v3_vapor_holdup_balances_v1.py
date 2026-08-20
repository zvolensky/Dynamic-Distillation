from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (
    VaporHoldupBalanceInputs,
    evaluate_two_phase_balances,
    evaluate_two_phase_transport,
    stationary_phase_transfer_from_vapor_transport,
)


def _case():
    topology = build_column_topology(
        rectifying_volume_count=1,
        stripping_volume_count=1,
    )
    volume_count = len(topology.volume_ids)
    x = np.tile([0.6, 0.4], (volume_count, 1))
    y = np.tile([0.8, 0.2], (volume_count, 1))
    inputs = VaporHoldupBalanceInputs(
        topology=topology,
        feed_component_lbmolph=np.asarray([6.0, 4.0]),
        feed_enthalpy_BTUph=1000.0,
        reflux_lbmolph=3.0,
        distillate_lbmolph=4.0,
        bottoms_lbmolph=6.0,
        condenser_duty_BTUph=-400.0,
        reboiler_duty_BTUph=600.0,
    )
    transport = evaluate_two_phase_transport(
        inputs,
        x,
        y,
        np.full(len(topology.hydraulic_volume_ids), 10.0),
        np.full(len(topology.vapor_links), 7.0),
        np.linspace(100.0, 140.0, volume_count),
        np.linspace(300.0, 340.0, volume_count),
    )
    return inputs, transport


def test_transport_telescopes_to_external_component_and_energy_rates():
    _inputs, transport = _case()
    shape = transport.liquid_transport_lbmolph.shape
    balances = evaluate_two_phase_balances(
        transport,
        np.zeros(shape),
        np.zeros(shape),
        np.zeros(shape),
        np.zeros(shape[0]),
    )

    assert np.allclose(balances.global_component_telescoping_error_lbmolph, 0.0)
    assert abs(balances.global_energy_telescoping_error_BTUph) < 1.0e-10


def test_stationary_transfer_closes_vapor_phase_and_cancels_between_phases():
    _inputs, transport = _case()
    shape = transport.liquid_transport_lbmolph.shape
    transfer = stationary_phase_transfer_from_vapor_transport(transport)
    balances = evaluate_two_phase_balances(
        transport,
        np.zeros(shape),
        np.zeros(shape),
        transfer,
        np.zeros(shape[0]),
    )

    assert np.allclose(balances.vapor_component_residual_lbmolph, 0.0)
    assert np.allclose(balances.phase_transfer_cancellation_lbmolph, 0.0)
    assert np.allclose(
        balances.total_component_residual_lbmolph,
        -(transport.liquid_transport_lbmolph + transport.vapor_transport_lbmolph),
    )


def test_matching_phase_rates_close_both_component_balances():
    _inputs, transport = _case()
    transfer = np.full_like(transport.liquid_transport_lbmolph, 2.0)
    liquid_rate = transport.liquid_transport_lbmolph + transfer
    vapor_rate = transport.vapor_transport_lbmolph - transfer
    energy_transport = (
        transport.liquid_energy_transport_BTUph
        + transport.vapor_energy_transport_BTUph
    )
    balances = evaluate_two_phase_balances(
        transport,
        liquid_rate,
        vapor_rate,
        transfer,
        energy_transport,
    )

    assert np.allclose(balances.liquid_component_residual_lbmolph, 0.0)
    assert np.allclose(balances.vapor_component_residual_lbmolph, 0.0)
    assert np.allclose(balances.energy_residual_BTUph, 0.0)


def test_phase_transfer_sign_is_vapor_to_liquid():
    _inputs, transport = _case()
    shape = transport.liquid_transport_lbmolph.shape
    transfer = np.ones(shape)
    balances = evaluate_two_phase_balances(
        transport,
        np.zeros(shape),
        np.zeros(shape),
        transfer,
        np.zeros(shape[0]),
    )

    no_transfer = evaluate_two_phase_balances(
        transport,
        np.zeros(shape),
        np.zeros(shape),
        np.zeros(shape),
        np.zeros(shape[0]),
    )
    assert np.allclose(
        balances.liquid_component_residual_lbmolph,
        no_transfer.liquid_component_residual_lbmolph - 1.0,
    )
    assert np.allclose(
        balances.vapor_component_residual_lbmolph,
        no_transfer.vapor_component_residual_lbmolph + 1.0,
    )
