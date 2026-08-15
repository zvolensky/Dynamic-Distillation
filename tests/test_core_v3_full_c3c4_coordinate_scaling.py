from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import design_core_v3_full_c3c4_coordinate_scaling as dd230


def test_dd230_scale_uses_all_matrices_and_normalizes_geometric_mean():
    first = np.diag([1.0, 100.0])
    second = np.diag([4.0, 25.0])

    scale = dd230.design_scale([first, second])

    assert np.isclose(np.exp(np.mean(np.log(scale))), 1.0)
    assert np.all(scale > 0.0)


def test_dd230_saved_design_uses_zero_live_calls():
    report = dd230.run()

    assert report["pass_gate"]
    assert report["provider_calls"] == 0
    assert report["solver_calls"] == 0
    assert report["timestep_calls"] == 0
    assert len(report["coordinate_scale"]) == 160
