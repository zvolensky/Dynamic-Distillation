from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_moving_step as dd173  # noqa: E402


def test_dd173_feed_step_preserves_composition_and_specific_enthalpy():
    source = {"feed_component_lbmolph": [2500.0, 4000.0, 643.0]}
    operating = {"feed_enthalpy_BTUph": 8.5e7, "temperature_scale_F": 100.0}
    disturbed_source, disturbed_operating = dd173._disturbed_inputs(
        source, operating, 1.001
    )

    baseline_flow = np.asarray(source["feed_component_lbmolph"], dtype=float)
    disturbed_flow = np.asarray(
        disturbed_source["feed_component_lbmolph"], dtype=float
    )
    assert np.allclose(disturbed_flow / baseline_flow, 1.001)
    assert np.allclose(
        disturbed_flow / np.sum(disturbed_flow),
        baseline_flow / np.sum(baseline_flow),
    )
    assert np.isclose(
        disturbed_operating["feed_enthalpy_BTUph"] / np.sum(disturbed_flow),
        operating["feed_enthalpy_BTUph"] / np.sum(baseline_flow),
    )
    assert source["feed_component_lbmolph"] == [2500.0, 4000.0, 643.0]
    assert operating["feed_enthalpy_BTUph"] == 8.5e7


@pytest.mark.parametrize("multiplier", [1.0, 0.999, 0.0, float("nan")])
def test_dd173_rejects_invalid_feed_multipliers(multiplier):
    with pytest.raises(ValueError, match="must exceed one"):
        dd173._disturbed_inputs(
            {"feed_component_lbmolph": [1.0, 2.0]},
            {"feed_enthalpy_BTUph": 100.0},
            multiplier,
        )
