from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import benchmark_core_v3_dynamic_pressure_parallel_trajectory as benchmark


def _evaluation(offset: float = 0.0):
    endpoint = SimpleNamespace(
        liquid_component_inventory_lbmol=np.asarray([[1.0 + offset]]),
        vapor_component_inventory_lbmol=np.asarray([[2.0]]),
        liquid_component_rate_lbmolph=np.asarray([[2.5]]),
        vapor_component_rate_lbmolph=np.asarray([[2.75]]),
        phase_transfer_lbmolph=np.asarray([[3.0]]),
        temperature_F=np.asarray([4.0]),
        pressure_psia=np.asarray([5.0]),
        hydraulic_liquid_flow_lbmolph=np.asarray([6.0]),
        vapor_flow_lbmolph=np.asarray([7.0]),
        condenser_duty_BTUph=-8.0,
    )
    return SimpleNamespace(
        base=SimpleNamespace(endpoint=endpoint),
        controller_memory_endpoint=np.asarray([9.0]),
        controller_rate_per_sec=np.asarray([10.0]),
        product_log_ratio=np.asarray([11.0]),
        scaled=np.asarray([12.0]),
    )


def test_maximum_endpoint_difference_reports_largest_block() -> None:
    maximum, blocks = benchmark._maximum_endpoint_difference(
        _evaluation(), _evaluation(0.25)
    )

    assert maximum == 0.25
    assert blocks["liquid_inventory"] == 0.25
    assert blocks["pressure"] == 0.0


def test_accepted_requires_all_scientific_gates() -> None:
    report = {
        "scipy_success": True,
        "scaled_residual_inf_norm": 1.0e-12,
        "jacobian_rank": 262,
        "jacobian_condition": 1.0e7,
        "physical_pass": True,
    }
    assert benchmark._accepted(report, 262)
    report["physical_pass"] = False
    assert not benchmark._accepted(report, 262)
