from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import adjudicate_core_v3_terminal_inventory_control_parallel_first_root as dd192  # noqa: E402


def _source():
    return json.loads((ROOT / dd192.DD191_RESULT).read_text(encoding="utf-8"))


def test_dd192_accepts_exact_dd191_failure_pattern():
    dd192._validate_source(_source())


def test_dd192_rejects_an_additional_failed_gate():
    source = deepcopy(_source())
    source["gates"]["parallel_speed"] = False
    with pytest.raises(RuntimeError, match="worker-participation only"):
        dd192._validate_source(source)


def test_dd192_rejects_missing_actual_worker():
    source = deepcopy(_source())
    source["provider"]["workers"][0]["worker_ids"].pop()
    with pytest.raises(RuntimeError, match="did not use four workers"):
        dd192._validate_source(source)


def test_dd192_rejects_changed_worker_membership():
    source = deepcopy(_source())
    source["provider"]["workers"][1]["worker_ids"][-1] += 1
    with pytest.raises(RuntimeError, match="membership changed"):
        dd192._validate_source(source)


def test_dd192_rejects_nonidentical_endpoint():
    source = deepcopy(_source())
    source["outcome_comparison"]["maximum_numeric_difference"] = 1.0e-14
    with pytest.raises(RuntimeError, match="not exactly equivalent"):
        dd192._validate_source(source)
