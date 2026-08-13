from pathlib import Path
import sys

import numpy as np


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import adjudicate_core_v3_terminal_inventory_control_bdf2_refinement_response as dd201


def test_dd201_expected_total_history_obeys_be_and_bdf2():
    result = dd201._expected_total_history(10.0, (2.0, 3.0, -1.0), 3600.0)

    assert result[1] == 12.0
    assert np.isclose(3.0 * result[2] - 4.0 * result[1] + result[0], 6.0)
    assert np.isclose(3.0 * result[3] - 4.0 * result[2] + result[1], -2.0)
