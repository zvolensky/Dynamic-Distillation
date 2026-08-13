import numpy as np
import pytest

from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_kinematics_v1 import (
    bdf2_derivative,
    bdf2_endpoint_from_derivative,
    build_controlled_bdf2_history,
    evaluate_controlled_bdf2_kinematics,
)


def _history(*, volumes=7, components=3, step=0.125):
    inventory = np.arange(1, volumes * components + 1, dtype=float).reshape(
        volumes, components
    )
    energy = np.linspace(-8.0e7, -2.0e7, volumes)
    return build_controlled_bdf2_history(
        step_seconds=step,
        current_inventory_lbmol=inventory,
        prior_inventory_lbmol=inventory,
        current_internal_energy_BTU=energy,
        prior_internal_energy_BTU=energy,
        current_controller_memory=(0.2, -0.3),
        prior_controller_memory=(0.2, -0.3),
    )


def test_dd196_stationary_history_is_an_exact_zero_rate_identity():
    history = _history()
    result = evaluate_controlled_bdf2_kinematics(
        history,
        nominal_component_rate_lbmolph=np.zeros((7, 3)),
        component_rate_scales_lbmolph=np.ones((7, 3)),
        endpoint_internal_energy_BTU=history.current_internal_energy_BTU,
        controller_rate_per_sec=(0.0, 0.0),
        step_seconds=0.125,
    )

    assert np.array_equal(
        result.endpoint_inventory_lbmol, history.current_inventory_lbmol
    )
    assert np.array_equal(result.component_rate_lbmolph, np.zeros((7, 3)))
    assert np.array_equal(result.component_rate_coordinates, np.zeros((7, 3)))
    assert np.array_equal(result.energy_storage_rate_BTUph, np.zeros(7))
    assert np.array_equal(
        result.endpoint_controller_memory, history.current_controller_memory
    )
    assert np.array_equal(result.controller_rate_per_sec, np.zeros(2))


def test_dd196_bdf2_derivative_is_exact_for_linear_and_quadratic_history():
    dt = 0.25
    linear_slope = np.asarray([2.0, -3.0])
    linear = bdf2_derivative(
        linear_slope * dt,
        np.zeros(2),
        -linear_slope * dt,
        step=dt,
    )
    quadratic = bdf2_derivative(
        np.full(2, dt**2),
        np.zeros(2),
        np.full(2, dt**2),
        step=dt,
    )

    assert np.allclose(linear, linear_slope, rtol=0.0, atol=1.0e-15)
    assert np.allclose(quadratic, 2.0 * dt, rtol=0.0, atol=1.0e-15)


def test_dd196_controller_endpoint_map_reproduces_its_requested_rate():
    current = np.asarray([0.4, -0.2])
    prior = np.asarray([0.35, -0.1])
    requested = np.asarray([0.03, -0.04])
    endpoint = bdf2_endpoint_from_derivative(
        requested, current, prior, step=0.125
    )

    assert np.allclose(
        bdf2_derivative(endpoint, current, prior, step=0.125),
        requested,
        rtol=0.0,
        atol=5.0e-16,
    )


def test_dd196_positive_inventory_map_reports_the_effective_bdf2_rate():
    history = _history(volumes=2, components=2, step=1.0)
    nominal = np.asarray([[10.0, -5.0], [2.0, -1.0]])
    scales = np.full((2, 2), 20.0)
    result = evaluate_controlled_bdf2_kinematics(
        history,
        nominal_component_rate_lbmolph=nominal,
        component_rate_scales_lbmolph=scales,
        endpoint_internal_energy_BTU=history.current_internal_energy_BTU,
        controller_rate_per_sec=(0.01, -0.02),
        step_seconds=1.0,
    )
    expected_endpoint = history.current_inventory_lbmol * np.exp(
        nominal / history.current_inventory_lbmol / 3600.0
    )
    expected_rate = (
        3.0 * expected_endpoint
        - 4.0 * history.current_inventory_lbmol
        + history.prior_inventory_lbmol
    ) / (2.0 / 3600.0)

    assert np.all(result.endpoint_inventory_lbmol > 0.0)
    assert np.allclose(result.endpoint_inventory_lbmol, expected_endpoint)
    assert np.allclose(result.component_rate_lbmolph, expected_rate)
    assert np.allclose(result.component_rate_coordinates, expected_rate / scales)


def test_dd196_generic_eight_volume_four_component_shape():
    history = _history(volumes=8, components=4, step=0.5)
    result = evaluate_controlled_bdf2_kinematics(
        history,
        nominal_component_rate_lbmolph=np.zeros((8, 4)),
        component_rate_scales_lbmolph=np.ones((8, 4)),
        endpoint_internal_energy_BTU=history.current_internal_energy_BTU,
        controller_rate_per_sec=(0.0, 0.0),
        step_seconds=0.5,
    )

    assert result.endpoint_inventory_lbmol.shape == (8, 4)
    assert result.energy_storage_rate_BTUph.shape == (8,)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"step_seconds": 0.0}, "positive"),
        ({"prior_inventory_lbmol": np.ones((6, 3))}, "matching positive"),
        ({"current_controller_memory": (0.0,)}, "two memories"),
    ],
)
def test_dd196_rejects_invalid_history(mutation, message):
    values = {
        "step_seconds": 0.125,
        "current_inventory_lbmol": np.ones((7, 3)),
        "prior_inventory_lbmol": np.ones((7, 3)),
        "current_internal_energy_BTU": np.ones(7),
        "prior_internal_energy_BTU": np.ones(7),
        "current_controller_memory": (0.0, 0.0),
        "prior_controller_memory": (0.0, 0.0),
    }
    values.update(mutation)

    with pytest.raises(ValueError, match=message):
        build_controlled_bdf2_history(**values)


def test_dd196_rejects_a_timestep_change_after_history_creation():
    history = _history(step=0.125)

    with pytest.raises(ValueError, match="does not match"):
        evaluate_controlled_bdf2_kinematics(
            history,
            nominal_component_rate_lbmolph=np.zeros((7, 3)),
            component_rate_scales_lbmolph=np.ones((7, 3)),
            endpoint_internal_energy_BTU=history.current_internal_energy_BTU,
            controller_rate_per_sec=(0.0, 0.0),
            step_seconds=0.25,
        )


def test_dd196_history_owns_copies_of_mutable_inputs():
    history = _history()
    original = history.current_inventory_lbmol.copy()
    source = history.current_inventory_lbmol.copy()
    rebuilt = build_controlled_bdf2_history(
        step_seconds=history.step_seconds,
        current_inventory_lbmol=source,
        prior_inventory_lbmol=history.prior_inventory_lbmol,
        current_internal_energy_BTU=history.current_internal_energy_BTU,
        prior_internal_energy_BTU=history.prior_internal_energy_BTU,
        current_controller_memory=history.current_controller_memory,
        prior_controller_memory=history.prior_controller_memory,
    )
    source[:] = -1.0

    assert np.array_equal(rebuilt.current_inventory_lbmol, original)
