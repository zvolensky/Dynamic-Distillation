import numpy as np
import pytest

from dynamic_distillation.core_v3.residual_replay_audit_v1 import (
    residual_replay_spread,
)


def test_replay_spread_identifies_worst_row():
    result = residual_replay_spread(
        [[1.0, 2.0, 3.0], [1.0 + 1.0e-12, 2.1, 2.95], [1.0, 1.9, 3.02]],
        ["a", "b", "c"],
    )

    assert result.sample_count == 3
    assert result.row_count == 3
    assert result.worst_row_index == 1
    assert result.worst_row_name == "b"
    assert np.isclose(result.max_abs_spread, 0.2)
    assert np.isclose(result.worst_row_minimum, 1.9)
    assert np.isclose(result.worst_row_maximum, 2.1)


def test_replay_spread_accepts_identical_samples():
    result = residual_replay_spread([[1.0, -2.0], [1.0, -2.0]], ["x", "y"])
    assert result.max_abs_spread == 0.0
    assert result.worst_row_name == "x"


@pytest.mark.parametrize(
    "samples,names",
    [
        ([[1.0]], ["x"]),
        ([[1.0], [2.0]], ["x", "y"]),
        ([[1.0], [float("nan")]], ["x"]),
        ([[1.0, 2.0], [1.0, 2.0]], ["x", "x"]),
    ],
)
def test_replay_spread_rejects_invalid_inputs(samples, names):
    with pytest.raises(ValueError):
        residual_replay_spread(samples, names)
