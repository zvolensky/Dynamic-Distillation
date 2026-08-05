import numpy as np
import pytest

from dynamic_distillation.core_v3.exponential_rate_coordinate_adjudication_v1 import (
    actual_component_rate_coordinates,
)


def test_actual_rate_coordinates_reproduce_exponential_endpoint():
    previous = np.asarray([[10.0, 20.0], [30.0, 40.0]])
    nominal = np.asarray([0.1, -0.2, 0.3, -0.4])
    scale = 100.0
    seconds = 2.0

    actual = actual_component_rate_coordinates(
        nominal,
        previous,
        component_rate_scale_lbmolph=scale,
        step_seconds=seconds,
    )
    hours = seconds / 3600.0
    endpoint_from_nominal = previous * np.exp(
        hours * nominal.reshape(previous.shape) * scale / previous
    )
    endpoint_from_actual = previous + hours * actual.reshape(previous.shape) * scale

    assert np.allclose(endpoint_from_actual, endpoint_from_nominal, rtol=0.0, atol=1e-14)
    assert not np.array_equal(actual, nominal)


def test_zero_nominal_rate_remains_zero():
    actual = actual_component_rate_coordinates(
        [0.0, 0.0],
        [[1.0, 2.0]],
        component_rate_scale_lbmolph=10.0,
        step_seconds=1.0,
    )
    assert np.array_equal(actual, [0.0, 0.0])


@pytest.mark.parametrize(
    "nominal,previous,scale,seconds",
    [
        ([0.0], [[0.0]], 1.0, 1.0),
        ([0.0, 1.0], [[1.0]], 1.0, 1.0),
        ([0.0], [[1.0]], 0.0, 1.0),
        ([0.0], [[1.0]], 1.0, 0.0),
    ],
)
def test_actual_rate_coordinates_reject_invalid_inputs(
    nominal, previous, scale, seconds
):
    with pytest.raises(ValueError):
        actual_component_rate_coordinates(
            nominal,
            previous,
            component_rate_scale_lbmolph=scale,
            step_seconds=seconds,
        )
