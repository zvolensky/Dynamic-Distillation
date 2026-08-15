from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import analyze_core_v3_dd223_conditioning as dd226


def test_dd226_coordinate_family_labels_are_generic():
    assert dd226._family("log_NL[feed_tray]") == "liquid_inventory"
    assert dd226._family("x_alr[rectifying_volume_1,Propane]") == "liquid_composition"
    assert dd226._family("log_V_12_to_11") == "vapor_flow"
    assert dd226._family("q_Q_C") == "condenser_duty"


def test_dd226_equilibration_detects_a_pure_scaling_problem():
    matrix = np.diag([1.0e6, 1.0, 1.0e-6])

    result = dd226._equilibrated_condition(matrix)

    assert result["condition"] < 1.01


def test_dd226_step_comparison_identifies_the_changed_entry():
    first = np.eye(2)
    second = first.copy()
    second[1, 0] = 2.0

    result = dd226._step_comparison(first, second, ["a", "b"], ["r1", "r2"])

    assert result["maximum_difference_coordinate"] == "a"
    assert result["maximum_difference_residual"] == "r2"
    assert result["maximum_entry_difference"] == 2.0
