from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

from dynamic_distillation.core_v3.implicit_step_v1 import BackwardEulerEvaluation


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_parallel_short_trajectory as dd183


def _outcome(offset=0.0):
    evaluation = BackwardEulerEvaluation(
        raw=np.asarray((offset,)),
        scaled=np.asarray((offset,)),
        row_names=("row",),
        previous_inventory_lbmol=np.asarray(((1.0,),)),
        endpoint_inventory_lbmol=np.asarray(((1.0 + offset,),)),
        component_rate_lbmolph=np.asarray(((0.1 + offset,),)),
        rate_coordinates=np.asarray(((0.1 + offset,),)),
        algebraic_coordinates=np.asarray((0.2 + offset,)),
        previous_internal_energy_BTU=np.asarray((2.0,)),
        endpoint_internal_energy_BTU=np.asarray((3.0 + offset,)),
        energy_storage_rate_BTUph=np.asarray((4.0 + offset,)),
        dynamic_evaluation=None,
        maximum_bubble_residual=0.0,
    )
    return SimpleNamespace(
        success=True,
        status=3,
        message="pass",
        nfev=4,
        njev=4,
        cost=1.0 + offset,
        optimality=2.0 + offset,
        initial_coordinates=np.asarray((0.0,)),
        final_coordinates=np.asarray((1.0 + offset,)),
        final_residual=np.asarray((offset,)),
        jacobian=np.asarray(((1.0 + offset,),)),
        evaluation=evaluation,
    )


def test_trajectory_comparison_reports_exact_equal_paths():
    step = SimpleNamespace(index=1, time_seconds=0.25, outcome=_outcome())
    result = dd183._trajectory_comparison(
        SimpleNamespace(steps=(step,)), SimpleNamespace(steps=(step,))
    )
    assert result["all_metadata_equal"]
    assert all(value == 0.0 for value in result["maximum_numeric_differences"].values())


def test_trajectory_comparison_finds_endpoint_difference():
    serial = SimpleNamespace(
        steps=(SimpleNamespace(index=1, time_seconds=0.25, outcome=_outcome()),)
    )
    parallel = SimpleNamespace(
        steps=(SimpleNamespace(index=1, time_seconds=0.25, outcome=_outcome(1.0e-6)),)
    )
    result = dd183._trajectory_comparison(serial, parallel)
    assert result["all_metadata_equal"]
    assert result["maximum_numeric_differences"][
        "final_coordinate_max_abs"
    ] == pytest.approx(1.0e-6)
