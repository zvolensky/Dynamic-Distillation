from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_smaller_moving_step as dd175  # noqa: E402


def test_dd175_uses_quarter_second_full_and_eighth_second_half_steps():
    assert dd175.FULL_DT_SEC == pytest.approx(0.25)
    assert dd175.HALF_DT_SEC == pytest.approx(0.125)
    assert 2.0 * dd175.HALF_DT_SEC == pytest.approx(dd175.FULL_DT_SEC)


def test_dd175_accepts_the_frozen_dd174_authorization():
    result = json.loads((ROOT / dd175.DD174_RESULT).read_text(encoding="utf-8"))
    dd175._validate_authorization(result)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pass_gate", False, "passing DD-174"),
        ("decision", "stop_moving_dynamic_path", "did not authorize"),
        ("source_dd173_formal_failure_preserved", False, "not preserved"),
        ("model_call_count", 1, "zero-call"),
    ],
)
def test_dd175_rejects_invalid_dd174_authorization(field, value, message):
    result = json.loads((ROOT / dd175.DD174_RESULT).read_text(encoding="utf-8"))
    altered = deepcopy(result)
    altered[field] = value
    with pytest.raises(RuntimeError, match=message):
        dd175._validate_authorization(altered)
