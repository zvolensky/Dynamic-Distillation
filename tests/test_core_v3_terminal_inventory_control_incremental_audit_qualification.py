from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_terminal_inventory_control_incremental_audit_qualification as dd194  # noqa: E402


def _source():
    return json.loads((ROOT / dd194.DD193_RESULT).read_text(encoding="utf-8"))


def test_dd194_accepts_exact_dd193_efficiency_stop():
    dd194._validate_source(_source())


def test_dd194_rejects_a_scientific_interpretation_of_dd193():
    source = deepcopy(_source())
    source["scientific_gates"] = {"shared_time_refinement": False}
    with pytest.raises(RuntimeError, match="non-classification"):
        dd194._validate_source(source)


def test_dd194_rejects_a_changed_scaling_diagnosis():
    source = deepcopy(_source())
    source["diagnosis"]["category"] = "thermodynamic_failure"
    with pytest.raises(RuntimeError, match="diagnosis changed"):
        dd194._validate_source(source)


def test_dd194_grid_is_bounded_to_two_seconds():
    assert dd194.DURATION_SEC == 2.0
    assert dd194.DURATION_SEC / dd194.dd193.COARSE_DT_SEC == 16
    assert dd194.DURATION_SEC / dd194.dd193.REFINED_DT_SEC == 32
