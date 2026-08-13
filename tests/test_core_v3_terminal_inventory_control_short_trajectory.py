from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_terminal_inventory_control_short_trajectory as dd188  # noqa: E402


def test_dd188_grid_has_eight_shared_times():
    coarse = dd188.dd177._step_count(dd188.DURATION_SEC, dd188.COARSE_DT_SEC)
    refined = dd188.dd177._step_count(dd188.DURATION_SEC, dd188.REFINED_DT_SEC)
    pairs = dd188.dd177._shared_step_pairs(coarse, refined)

    assert coarse == 8
    assert refined == 16
    assert pairs[0] == (1, 2)
    assert pairs[-1] == (8, 16)


def test_dd188_accepts_preserved_dd187_authorization():
    result = json.loads((ROOT / dd188.DD187_RESULT).read_text(encoding="utf-8"))
    dd188._validate_source(result)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pass_gate", False, "accepted DD-187"),
        ("decision", "stop", "accepted DD-187"),
        ("controller_tuning_attempted", True, "tuning status"),
    ],
)
def test_dd188_rejects_changed_source(field, value, message):
    result = json.loads((ROOT / dd188.DD187_RESULT).read_text(encoding="utf-8"))
    altered = deepcopy(result)
    altered[field] = value
    with pytest.raises(RuntimeError, match=message):
        dd188._validate_source(altered)
