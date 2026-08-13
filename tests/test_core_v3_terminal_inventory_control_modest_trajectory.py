from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_terminal_inventory_control_modest_trajectory as dd190  # noqa: E402


def _sources():
    dd188 = json.loads((ROOT / dd190.DD188_RESULT).read_text(encoding="utf-8"))
    dd189 = json.loads((ROOT / dd190.DD189_RESULT).read_text(encoding="utf-8"))
    return dd188, dd189


def test_dd190_grid_has_forty_shared_times():
    coarse = dd190.dd188.dd177._step_count(dd190.DURATION_SEC, dd190.COARSE_DT_SEC)
    refined = dd190.dd188.dd177._step_count(dd190.DURATION_SEC, dd190.REFINED_DT_SEC)
    pairs = dd190.dd188.dd177._shared_step_pairs(coarse, refined)

    assert coarse == 40
    assert refined == 80
    assert pairs[0] == (1, 2)
    assert pairs[-1] == (40, 80)


def test_dd190_accepts_preserved_sources():
    dd190._validate_sources(*_sources())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pass_gate", False, "accepted DD-189"),
        ("decision", "stop", "accepted DD-189"),
        ("dd188_rerun", True, "preservation status"),
    ],
)
def test_dd190_rejects_changed_policy_source(field, value, message):
    dd188, dd189 = _sources()
    altered = deepcopy(dd189)
    altered[field] = value
    with pytest.raises(RuntimeError, match=message):
        dd190._validate_sources(dd188, altered)
