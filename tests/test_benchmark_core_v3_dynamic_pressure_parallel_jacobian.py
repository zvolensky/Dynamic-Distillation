from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import benchmark_core_v3_dynamic_pressure_parallel_jacobian as benchmark


def test_predicted_point_forwards_controller_history(monkeypatch) -> None:
    captured = {}

    def fake_builder(contract, **kwargs):
        captured["contract"] = contract
        captured.update(kwargs)
        return np.asarray([1.0, 2.0])

    monkeypatch.setattr(
        benchmark.dd274,
        "controlled_implicit_initial_coordinates",
        fake_builder,
    )
    prior = SimpleNamespace(
        controller_rate_per_sec=np.asarray([0.1, -0.2]),
        product_log_ratio=np.asarray([0.03, -0.04]),
    )
    result = benchmark._predicted_point(
        {"contract": "contract"},
        np.asarray([4.0, 5.0]),
        prior,
        0.25,
    )

    assert np.array_equal(result, np.asarray([1.0, 2.0]))
    assert captured["contract"] == "contract"
    assert captured["timestep_sec"] == 0.25
    assert np.array_equal(captured["previous_coordinates"], np.asarray([4.0, 5.0]))
    assert np.array_equal(captured["controller_rates_per_sec"], prior.controller_rate_per_sec)
    assert np.array_equal(captured["product_log_ratios_previous"], prior.product_log_ratio)
