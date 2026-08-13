from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_terminal_inventory_control_finer_parallel_trajectory as dd193  # noqa: E402


def _sources():
    return tuple(
        json.loads((ROOT / path).read_text(encoding="utf-8"))
        for path in (dd193.DD190_RESULT, dd193.DD191_RESULT, dd193.DD192_RESULT)
    )


def test_dd193_accepts_exact_source_boundary():
    dd193._validate_sources(*_sources())


def test_dd193_rejects_an_additional_dd190_failure():
    dd190, dd191, dd192 = _sources()
    dd190 = deepcopy(dd190)
    dd190["campaign_gates"]["provider"] = False
    with pytest.raises(RuntimeError, match="shared-time refinement only"):
        dd193._validate_sources(dd190, dd191, dd192)


def test_dd193_rejects_lost_parallel_authorization():
    dd190, dd191, dd192 = _sources()
    dd192 = deepcopy(dd192)
    dd192["pass_gate"] = False
    with pytest.raises(RuntimeError, match="parallel authorization"):
        dd193._validate_sources(dd190, dd191, dd192)


def test_dd193_finer_grid_is_exact_two_to_one_refinement():
    assert dd193.DURATION_SEC / dd193.COARSE_DT_SEC == 80
    assert dd193.DURATION_SEC / dd193.REFINED_DT_SEC == 160
    assert dd193.COARSE_DT_SEC / dd193.REFINED_DT_SEC == 2
