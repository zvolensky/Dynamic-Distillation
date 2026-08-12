from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_physical_short_trajectory as dd177  # noqa: E402


def test_dd177_frozen_grid_has_eight_shared_times():
    coarse = dd177._step_count(dd177.DURATION_SEC, dd177.COARSE_DT_SEC)
    refined = dd177._step_count(dd177.DURATION_SEC, dd177.REFINED_DT_SEC)
    pairs = dd177._shared_step_pairs(coarse, refined)

    assert coarse == 8
    assert refined == 16
    assert pairs[0] == (1, 2)
    assert pairs[-1] == (8, 16)
    assert len(pairs) == 8


def test_dd177_rejects_incompatible_trajectory_grids():
    with pytest.raises(ValueError, match="two steps per coarse step"):
        dd177._shared_step_pairs(8, 15)


def test_dd177_accepts_preserved_dd175_failure_pattern():
    result = json.loads((ROOT / dd177.DD175_RESULT).read_text(encoding="utf-8"))
    dd177._validate_source(result)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("pass_gate", True), "preserved formal failure"),
        (("decision", "authorize"), "stop decision changed"),
    ],
)
def test_dd177_rejects_changed_dd175_authorization(mutation, message):
    result = json.loads((ROOT / dd177.DD175_RESULT).read_text(encoding="utf-8"))
    altered = deepcopy(result)
    altered[mutation[0]] = mutation[1]
    with pytest.raises(RuntimeError, match=message):
        dd177._validate_source(altered)


def test_dd177_rejects_an_additional_dd175_refinement_failure():
    result = json.loads((ROOT / dd177.DD175_RESULT).read_text(encoding="utf-8"))
    altered = deepcopy(result)
    altered["refinement_gates"]["rate"] = False
    with pytest.raises(RuntimeError, match="fail only legacy inventory"):
        dd177._validate_source(altered)
