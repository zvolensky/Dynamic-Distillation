from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_physical_longer_trajectory as dd180  # noqa: E402


def test_dd180_frozen_grid_has_one_hundred_twenty_shared_times():
    coarse = dd180.dd178.dd177._step_count(
        dd180.DURATION_SEC, dd180.COARSE_DT_SEC
    )
    refined = dd180.dd178.dd177._step_count(
        dd180.DURATION_SEC, dd180.REFINED_DT_SEC
    )
    pairs = dd180.dd178.dd177._shared_step_pairs(coarse, refined)

    assert coarse == 120
    assert refined == 240
    assert pairs[0] == (1, 2)
    assert pairs[-1] == (120, 240)
    assert len(pairs) == 120


def test_dd180_accepts_the_frozen_dd179_authorization():
    result = json.loads((ROOT / dd180.DD179_RESULT).read_text(encoding="utf-8"))
    dd180._validate_authorization(result)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pass_gate", False, "passing DD-179"),
        ("decision", "stop", "did not authorize"),
        ("source_dd178_formal_failure_preserved", False, "not preserved"),
        ("model_call_count", 1, "zero-call"),
    ],
)
def test_dd180_rejects_changed_dd179_authorization(field, value, message):
    result = json.loads((ROOT / dd180.DD179_RESULT).read_text(encoding="utf-8"))
    altered = deepcopy(result)
    altered[field] = value
    with pytest.raises(RuntimeError, match=message):
        dd180._validate_authorization(altered)


def test_duration_response_gates_use_expected_flow_not_absolute_ceiling():
    response = {
        name: {
            "total_inventory_change_lbmol": actual,
            "expected_total_inventory_change_lbmol": 0.06,
            "component_inventory_identity_max_abs_lbmol": 1.0e-10,
        }
        for name, actual in (("coarse", 0.060000001), ("refined", 0.06))
    }
    metrics, gates, cross_grid = dd180._duration_response_gates(
        response,
        {"coarse": True, "refined": True},
        {
            "relative_actual_expected_response_error": 1.0e-6,
            "global_component_inventory_identity_lbmol": 1.0e-6,
        },
    )

    assert metrics["coarse"]["actual_total_inventory_change_lbmol"] > 0.01
    assert all(all(values.values()) for values in gates.values())
    assert cross_grid == pytest.approx(1.0e-9)
