from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    Unknown,
    build_column_topology,
)
from dynamic_distillation.core_v3.stationary_closure_audit_v1 import (
    aggregate_residual_block_gradient,
    eos_required_vapor_component_inventory,
    find_active_coordinate_bounds,
    linearized_closure_correction,
    stationary_energy_closure,
)
from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (
    VaporHoldupBalanceInputs,
    evaluate_two_phase_transport,
)


def test_active_bounds_are_discovered_from_the_variable_ledger():
    variables = (
        Unknown("inventory[stage,component_a]", "vapor_component_inventory", "stage"),
        Unknown("temperature[stage]", "temperature", "stage"),
        Unknown("flow[stage]", "pressure_driven_vapor_flow", "link"),
    )
    findings = find_active_coordinate_bounds(
        variables,
        [2.0, 0.0, -3.0],
        [-2.0, -1.0, -3.0],
        [2.0, 1.0, 3.0],
    )

    assert [(item.index, item.block, item.side) for item in findings] == [
        (0, "vapor_component_inventory", "upper"),
        (2, "pressure_driven_vapor_flow", "lower"),
    ]


def test_eos_required_inventory_preserves_arbitrary_composition():
    inventory = np.array([[1.0, 2.0, 3.0], [4.0, 1.0, 5.0]])
    required = eos_required_vapor_component_inventory(
        inventory,
        free_vapor_volume_ft3=[20.0, 30.0],
        vapor_molar_volume_ft3_lbmol=[2.0, 3.0],
    )

    assert np.allclose(np.sum(required, axis=1), [10.0, 10.0])
    assert np.allclose(
        required / np.sum(required, axis=1, keepdims=True),
        inventory / np.sum(inventory, axis=1, keepdims=True),
    )


def test_energy_ledger_matches_generic_transport_for_every_volume():
    topology = build_column_topology(
        rectifying_volume_count=1,
        stripping_volume_count=1,
    )
    inputs = VaporHoldupBalanceInputs(
        topology=topology,
        feed_component_lbmolph=np.array([2.0, 3.0, 5.0]),
        feed_enthalpy_BTUph=900.0,
        reflux_lbmolph=4.0,
        distillate_lbmolph=2.0,
        bottoms_lbmolph=8.0,
        condenser_duty_BTUph=-700.0,
        reboiler_duty_BTUph=1100.0,
    )
    endpoint = SimpleNamespace(
        hydraulic_liquid_flow_lbmolph=np.array([8.0, 9.0, 10.0]),
        vapor_flow_lbmolph=np.array([7.0, 6.0, 5.0, 4.0]),
        condenser_duty_BTUph=-650.0,
        distillate_lbmolph=2.5,
        bottoms_lbmolph=7.5,
    )
    properties = SimpleNamespace(
        liquid_enthalpy_BTU_lbmol=np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
        vapor_enthalpy_BTU_lbmol=np.array([60.0, 70.0, 80.0, 90.0, 100.0]),
    )
    live_inputs = VaporHoldupBalanceInputs(
        topology=topology,
        feed_component_lbmolph=inputs.feed_component_lbmolph,
        feed_enthalpy_BTUph=inputs.feed_enthalpy_BTUph,
        reflux_lbmolph=inputs.reflux_lbmolph,
        distillate_lbmolph=endpoint.distillate_lbmolph,
        bottoms_lbmolph=endpoint.bottoms_lbmolph,
        condenser_duty_BTUph=endpoint.condenser_duty_BTUph,
        reboiler_duty_BTUph=inputs.reboiler_duty_BTUph,
    )
    composition = np.full((len(topology.volume_ids), 3), 1.0 / 3.0)
    transport = evaluate_two_phase_transport(
        live_inputs,
        composition,
        composition,
        endpoint.hydraulic_liquid_flow_lbmolph,
        endpoint.vapor_flow_lbmolph,
        properties.liquid_enthalpy_BTU_lbmol,
        properties.vapor_enthalpy_BTU_lbmol,
    )

    rows = stationary_energy_closure(topology, endpoint, properties, inputs)
    expected = transport.liquid_energy_transport_BTUph + transport.vapor_energy_transport_BTUph

    assert tuple(row.volume_id for row in rows) == topology.volume_ids
    assert np.allclose([row.net_energy_transport_BTUph for row in rows], expected)
    assert np.allclose([row.stationary_energy_residual_BTUph for row in rows], -expected)
    assert all(row.contributions for row in rows)


def test_linearized_closure_reports_coordinated_bound_conflicts():
    variables = (
        Unknown("state[a]", "inventory", "a"),
        Unknown("state[b]", "temperature", "b"),
    )
    result = linearized_closure_correction(
        variables,
        coordinates=[0.0, 0.0],
        lower_bounds=[-1.0, -3.0],
        upper_bounds=[1.0, 3.0],
        scaled_residual=[-2.0, -4.0],
        scaled_jacobian=[[1.0, 0.0], [0.0, 2.0]],
    )

    assert result.rank == 2
    assert result.condition == 2.0
    assert np.isclose(result.maximum_feasible_step_fraction, 0.5)
    assert result.predicted_residual_inf_norm < 1.0e-12
    assert result.movements[0].bound_violation
    assert not result.movements[1].bound_violation
    assert np.allclose([item.correction for item in result.movements], [2.0, 2.0])


def test_raw_residual_block_gradient_uses_each_row_scale():
    rows = (
        SimpleNamespace(block="energy"),
        SimpleNamespace(block="material"),
        SimpleNamespace(block="energy"),
    )
    gradient = aggregate_residual_block_gradient(
        rows,
        scaled_jacobian=[[1.0, 2.0], [9.0, 9.0], [3.0, 4.0]],
        residual_scales=[10.0, 20.0, 30.0],
        block="energy",
    )

    assert np.allclose(gradient, [100.0, 140.0])
