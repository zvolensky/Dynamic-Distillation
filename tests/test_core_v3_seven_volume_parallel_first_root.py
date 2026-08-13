from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_parallel_first_root as dd182


def test_maximum_absolute_difference_is_shape_strict():
    assert dd182._maximum_absolute_difference((1.0, 2.0), (1.0, 2.5)) == 0.5
    with pytest.raises(ValueError, match="different shapes"):
        dd182._maximum_absolute_difference((1.0, 2.0), ((1.0, 2.0),))


def test_matrix_hash_is_shape_and_value_deterministic():
    matrix = np.asarray(((1.0, 2.0), (3.0, 4.0)))
    assert dd182._matrix_sha(matrix) == dd182._matrix_sha(matrix.copy())
    assert dd182._matrix_sha(matrix) != dd182._matrix_sha(matrix.T)
