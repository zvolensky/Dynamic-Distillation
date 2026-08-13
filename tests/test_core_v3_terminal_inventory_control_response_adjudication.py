from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import adjudicate_core_v3_terminal_inventory_control_short_trajectory as dd189  # noqa: E402


def _source():
    return json.loads((ROOT / dd189.DD188_RESULT).read_text(encoding="utf-8"))


def test_dd189_accepts_exact_dd188_failure_pattern():
    dd189._validate_source(_source())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("pass_gate", True), "preserved formal failure"),
        (("decision", "authorize"), "preserved formal failure"),
    ],
)
def test_dd189_rejects_reclassified_source(mutation, message):
    source = deepcopy(_source())
    source[mutation[0]] = mutation[1]
    with pytest.raises(RuntimeError, match=message):
        dd189._validate_source(source)


def test_dd189_rejects_an_additional_shared_failure():
    source = deepcopy(_source())
    source["shared_time_refinement"]["comparisons"][-1]["gates"]["product"] = False
    with pytest.raises(RuntimeError, match="signed-total only"):
        dd189._validate_source(source)
