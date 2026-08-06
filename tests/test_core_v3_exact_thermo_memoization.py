from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import benchmark_core_v3_exact_thermo_memoization as dd156


class _Delegate:
    def __init__(self):
        self.calls = 0

    def phase_fugacity_coefficients(self, phase, temperature, pressure, composition):
        self.calls += 1
        return np.asarray(composition, dtype=float) + 1.0


def test_exact_memo_reuses_only_identical_state_and_returns_copy():
    delegate = _Delegate()
    provider = dd156._ExactMemoProvider(delegate, enabled=True)
    first = provider.phase_fugacity_coefficients("vapor", 100.0, 20.0, [0.4, 0.6])
    first[0] = -99.0
    second = provider.phase_fugacity_coefficients("vapor", 100.0, 20.0, [0.4, 0.6])
    provider.phase_fugacity_coefficients("vapor", 100.0 + 1.0e-12, 20.0, [0.4, 0.6])
    assert delegate.calls == 2
    assert second[0] == 1.4
    assert provider.snapshot()["methods"]["fugacity"] == {
        "hits": 1,
        "misses": 2,
        "cache_entries": 2,
    }


def test_passthrough_records_misses_without_caching():
    delegate = _Delegate()
    provider = dd156._ExactMemoProvider(delegate, enabled=False)
    for _ in range(2):
        provider.phase_fugacity_coefficients("liquid", 100.0, 20.0, [0.4, 0.6])
    assert delegate.calls == 2
    assert provider.snapshot()["methods"]["fugacity"] == {
        "hits": 0,
        "misses": 2,
        "cache_entries": 0,
    }


def test_aggregate_snapshots_sums_worker_counts():
    empty = {
        name: {"hits": 0, "misses": 0, "cache_entries": 0}
        for name in dd156._ExactMemoProvider._METHODS
    }
    left = {"process_id": 1, "snapshot": {"methods": {k: dict(v) for k, v in empty.items()}}}
    right = {"process_id": 2, "snapshot": {"methods": {k: dict(v) for k, v in empty.items()}}}
    left["snapshot"]["methods"]["enthalpy"] = {"hits": 3, "misses": 1, "cache_entries": 1}
    right["snapshot"]["methods"]["enthalpy"] = {"hits": 2, "misses": 2, "cache_entries": 2}
    out = dd156._aggregate_snapshots([left, right])
    assert out["hits"] == 5
    assert out["misses"] == 3
    assert out["calls"] == 8
    assert out["process_ids"] == [1, 2]


def test_classification_requires_speed_and_hit_fraction():
    passed = dd156._classify(
        baseline_wall_sec=3.0,
        warm_wall_sec=1.0,
        warm_hit_fraction=0.75,
        speedup_minimum=1.5,
        hit_fraction_minimum=0.5,
    )
    failed = dd156._classify(
        baseline_wall_sec=3.0,
        warm_wall_sec=2.5,
        warm_hit_fraction=0.75,
        speedup_minimum=1.5,
        hit_fraction_minimum=0.5,
    )
    assert passed["memoization_effective"] is True
    assert failed["memoization_effective"] is False
