from pathlib import Path
import sys

import numpy as np


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step as dd198


def test_dd198_reconstructs_saved_coordinates_from_controller_memory():
    report = {
        "rate_coordinates": [[1.0, 2.0], [3.0, 4.0]],
        "controller_memory": [0.3, -0.1],
        "algebraic_coordinates": [5.0, 6.0],
        "product_log_ratio": [0.01, -0.02],
    }

    result = dd198._coordinates(report, np.asarray((0.1, 0.0)), 0.125)

    assert np.allclose(
        result,
        np.asarray((1.0, 2.0, 3.0, 4.0, 1.6, -0.8, 5.0, 6.0, 0.01, -0.02)),
    )


def test_dd198_rank_condition_detects_full_rank():
    rank, condition = dd198._rank_condition(np.diag((1.0, 2.0, 4.0)))

    assert rank == 3
    assert condition == 4.0
