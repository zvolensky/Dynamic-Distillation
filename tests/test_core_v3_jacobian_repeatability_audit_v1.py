import numpy as np
import pytest

from dynamic_distillation.core_v3.jacobian_repeatability_audit_v1 import (
    compare_jacobians,
    jacobian_repeatability,
    relative_spectrum_change,
)


def test_compare_jacobians_identifies_changed_entry():
    left = np.eye(2)
    right = left.copy()
    right[1, 0] = 0.25

    result = compare_jacobians(left, right, ["r0", "r1"], ["c0", "c1"])

    assert result.max_abs_difference == 0.25
    assert result.worst_row_name == "r1"
    assert result.worst_column_name == "c0"
    assert np.isclose(result.relative_frobenius_difference, 0.25 / np.sqrt(2.0))


def test_repeatability_reports_worst_pair_and_labels():
    base = np.eye(2)
    middle = base.copy()
    middle[0, 1] = 0.1
    far = base.copy()
    far[0, 1] = -0.2

    result = jacobian_repeatability(
        [base, middle, far], ["mass", "energy"], ["flow", "temperature"]
    )

    assert result.sample_count == 3
    assert result.max_abs_spread == pytest.approx(0.3)
    assert result.worst_sample_pair == (1, 2)
    assert result.worst_row_name == "mass"
    assert result.worst_column_name == "temperature"


def test_repeatability_accepts_identical_matrices():
    matrix = np.array([[1.0, 2.0], [3.0, 4.0]])
    result = jacobian_repeatability(
        [matrix, matrix.copy()], ["a", "b"], ["x", "y"]
    )
    assert result.max_abs_spread == 0.0
    assert result.max_relative_frobenius_difference == 0.0


def test_relative_spectrum_change_uses_each_reference_value():
    assert relative_spectrum_change([10.0, 2.0], [11.0, 1.5]) == pytest.approx(0.25)


@pytest.mark.parametrize(
    "samples,rows,columns",
    [
        ([np.eye(2)], ["a", "b"], ["x", "y"]),
        ([np.eye(2), np.eye(3)], ["a", "b"], ["x", "y"]),
        ([np.eye(2), np.eye(2)], ["a", "a"], ["x", "y"]),
        ([np.eye(2), np.array([[1.0, np.nan], [0.0, 1.0]])], ["a", "b"], ["x", "y"]),
    ],
)
def test_repeatability_rejects_invalid_inputs(samples, rows, columns):
    with pytest.raises(ValueError):
        jacobian_repeatability(samples, rows, columns)
