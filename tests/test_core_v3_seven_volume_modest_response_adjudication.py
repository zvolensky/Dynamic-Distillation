from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import adjudicate_core_v3_seven_volume_modest_response as dd179  # noqa: E402


def test_dd179_response_metrics_compare_actual_with_duration_scaled_expected():
    metrics = dd179._response_metrics(
        {
            "total_inventory_change_lbmol": 2.0000002,
            "expected_total_inventory_change_lbmol": 2.0,
            "component_inventory_identity_max_abs_lbmol": 1.0e-10,
        }
    )

    assert metrics["absolute_response_error_lbmol"] == pytest.approx(2.0e-7)
    assert metrics["relative_response_error"] == pytest.approx(1.0e-7)
    assert metrics["actual_to_expected_ratio"] == pytest.approx(1.0000001)


def test_dd179_rejects_nonpositive_expected_response():
    with pytest.raises(ValueError, match="must be positive"):
        dd179._response_metrics(
            {
                "total_inventory_change_lbmol": 0.0,
                "expected_total_inventory_change_lbmol": 0.0,
                "component_inventory_identity_max_abs_lbmol": 0.0,
            }
        )


def test_dd179_accepts_dd178_single_response_ceiling_failure():
    result = json.loads((ROOT / dd179.DD178_RESULT).read_text(encoding="utf-8"))
    dd179._validate_source(result)


def test_dd179_rejects_an_additional_response_failure():
    result = json.loads((ROOT / dd179.DD178_RESULT).read_text(encoding="utf-8"))
    altered = deepcopy(result)
    altered["response_gates"]["coarse"]["monotone"] = False
    with pytest.raises(RuntimeError, match="fail only the inherited bounded gate"):
        dd179._validate_source(altered)
