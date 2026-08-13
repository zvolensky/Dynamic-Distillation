from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import benchmark_core_v3_seven_volume_parallel_jacobian as dd181


def _result_fixture():
    return {
        "wall_clock_sec": 15.0,
        "paths": {"duration_seconds": 3.0},
        "coarse": {
            "steps": [
                {"wall_clock_sec": 1.0},
                {"wall_clock_sec": 1.1},
                {"wall_clock_sec": 0.9},
            ]
        },
        "refined": {
            "steps": [
                {"wall_clock_sec": 1.5},
                {"wall_clock_sec": 1.5},
                {"wall_clock_sec": 1.5},
                {"wall_clock_sec": 1.5},
                {"wall_clock_sec": 1.5},
                {"wall_clock_sec": 1.5},
            ]
        },
        "provider": {
            "total_calls": 100,
            "counts": [
                {"evaluation_kind": "jacobian", "count": 80},
                {"evaluation_kind": "residual", "count": 20},
            ],
        },
        "exact_state_memoization": {"hits": 75, "misses": 25},
    }


def test_dd180_runtime_accounting_separates_production_and_validation_work():
    accounting = dd181.dd180_runtime_accounting(_result_fixture())
    assert accounting["coarse_step_wall_sec"] == pytest.approx(3.0)
    assert accounting["refined_step_wall_sec"] == pytest.approx(9.0)
    assert accounting["non_step_overhead_sec"] == pytest.approx(3.0)
    assert accounting["production_wall_per_simulated_second"] == pytest.approx(1.0)
    assert accounting["production_simulated_to_wall_ratio"] == pytest.approx(1.0)
    assert accounting["jacobian_logical_call_fraction"] == pytest.approx(0.8)


def test_dd180_runtime_accounting_rejects_no_hidden_mutation():
    source = _result_fixture()
    before = deepcopy(source)
    dd181.dd180_runtime_accounting(source)
    assert source == before
