from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import adjudicate_core_v3_seven_volume_moving_step as dd174  # noqa: E402


def test_dd174_physical_metrics_use_declared_engineering_scales():
    initial = np.asarray([[2.0, 3.0], [0.5, 9.5]])
    full = initial + np.asarray([[0.2, -0.3], [0.05, -0.1]])
    refined = initial

    metrics = dd174._physical_metrics(initial, full, refined)

    assert metrics["maximum_absolute_component_difference_lbmol"] == pytest.approx(
        0.3
    )
    assert metrics["maximum_absolute_component_index"] == [0, 1]
    assert metrics[
        "maximum_state_relative_difference_with_1_lbmol_floor"
    ] == pytest.approx(0.1)
    assert metrics["maximum_volume_holdup_relative_component_difference"] == (
        pytest.approx(0.06)
    )
    assert metrics["component_difference_l1_lbmol"] == pytest.approx(0.65)
    assert metrics["signed_total_inventory_difference_lbmol"] == pytest.approx(-0.15)


@pytest.mark.parametrize(
    ("initial", "full", "refined"),
    [
        ([[1.0, 2.0]], [[1.0]], [[1.0, 2.0]]),
        ([[1.0, 0.0]], [[1.0, 2.0]], [[1.0, 2.0]]),
        ([[1.0, 2.0]], [[1.0, float("nan")]], [[1.0, 2.0]]),
    ],
)
def test_dd174_rejects_invalid_endpoint_inventories(initial, full, refined):
    with pytest.raises(ValueError, match="inventories are invalid"):
        dd174._physical_metrics(initial, full, refined)


def test_dd174_accepts_only_dd173_single_inventory_refinement_failure():
    result = json.loads(dd174.DD173_RESULT.read_text(encoding="utf-8"))
    dd174._validate_source(result)

    altered = deepcopy(result)
    altered["refinement_gates"]["algebraic"] = False
    with pytest.raises(RuntimeError, match="fail only inventory refinement"):
        dd174._validate_source(altered)
