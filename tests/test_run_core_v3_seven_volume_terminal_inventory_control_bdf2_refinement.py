from pathlib import Path
import sys

import numpy as np


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement as dd199


def test_dd199_expected_total_history_obeys_be_then_bdf2():
    initial = np.asarray(((1.0, 2.0), (3.0, 4.0)))
    rates = [np.asarray((2.0, -1.0)), np.asarray((3.0, 4.0))]
    history = dd199._bdf2_expected_inventory_history(initial, rates, 3600.0)

    assert np.allclose(np.sum(history[1], axis=0), np.sum(initial, axis=0) + rates[0])
    assert np.allclose(
        3.0 * np.sum(history[2], axis=0)
        - 4.0 * np.sum(history[1], axis=0)
        + np.sum(history[0], axis=0),
        2.0 * rates[1],
    )


def test_dd199_rank_condition_detects_singular_matrix():
    rank, condition = dd199._rank_condition(np.asarray(((1.0, 1.0), (2.0, 2.0))))

    assert rank == 1
    assert np.isinf(condition)
