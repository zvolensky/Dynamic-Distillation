from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import benchmark_core_v3_pool_renewal_cadence as dd154


def test_projection_balances_aging_and_pool_overhead():
    common = dict(
        coarse_roots=4,
        refined_roots=4,
        fresh_coarse_sec=1.0,
        fresh_refined_sec=1.0,
        coarse_slope_sec_per_root=0.1,
        refined_slope_sec_per_root=0.1,
        pool_lifecycle_overhead_sec=2.0,
        fixed_non_jacobian_sec=3.0,
    )
    often = dd154._project(2, **common)
    never = dd154._project(8, **common)
    assert often["pool_count"] == 4
    assert never["pool_count"] == 1
    assert often["jacobian_sec"] < never["jacobian_sec"]
    assert often["pool_lifecycle_sec"] > never["pool_lifecycle_sec"]


def test_projection_calibration_is_additive():
    common = dict(
        coarse_roots=2,
        refined_roots=2,
        fresh_coarse_sec=1.0,
        fresh_refined_sec=1.0,
        coarse_slope_sec_per_root=0.0,
        refined_slope_sec_per_root=0.0,
        pool_lifecycle_overhead_sec=2.0,
        fixed_non_jacobian_sec=3.0,
    )
    base = dd154._project(4, **common)
    shifted = dd154._project(4, calibration_sec=5.0, **common)
    assert shifted["projected_total_sec"] == base["projected_total_sec"] + 5.0


def test_select_returns_minimum_projected_total():
    selected = dd154._select(
        [
            {"cadence_roots": 60, "projected_total_sec": 20.0},
            {"cadence_roots": 120, "projected_total_sec": 15.0},
            {"cadence_roots": 240, "projected_total_sec": 17.0},
        ]
    )
    assert selected["cadence_roots"] == 120
