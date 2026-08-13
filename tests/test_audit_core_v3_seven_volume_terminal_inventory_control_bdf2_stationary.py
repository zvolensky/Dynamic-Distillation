from pathlib import Path
import sys

import numpy as np


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import audit_core_v3_seven_volume_terminal_inventory_control_bdf2_stationary as dd197


def test_dd197_dense_central_jacobian_is_exact_for_linear_system():
    matrix = np.asarray(((2.0, -1.0), (0.5, 3.0)))

    def objective(point, _state_id):
        return matrix @ point

    result = dd197._dense_central_jacobian(
        objective,
        np.asarray((0.25, -0.75)),
        step=1.0e-5,
        state_id="dd197_test",
    )

    assert np.allclose(result, matrix, rtol=0.0, atol=5.0e-11)


def test_dd197_matrix_audit_reports_rank_and_unexpected_coupling():
    matrix = np.asarray(((2.0, 1.0), (0.0, 3.0)))
    pattern = np.asarray(((True, False), (False, True)))

    result = dd197._matrix_audit(matrix, pattern, 1.0e-12)

    assert result["rank"] == 2
    assert result["unexpected_couplings"] == 1
    assert result["zero_rows"] == []
    assert result["zero_columns"] == []
