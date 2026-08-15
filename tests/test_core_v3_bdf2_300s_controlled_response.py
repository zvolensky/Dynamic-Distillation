from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "adjudicate_core_v3_bdf2_300s_controlled_response.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd219_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _limits():
    return {
        "duration_seconds": 300.0,
        "time_tolerance_seconds": 1.0e-12,
        "minimum_sample_count": 5,
        "maximum_inventory_excursion_lbmol": 1.0,
        "minimum_peak_time_seconds": 200.0,
        "maximum_peak_time_seconds": 290.0,
        "minimum_consecutive_final_declines": 2,
        "minimum_peak_minus_final_lbmol": 1.0e-4,
        "monotonic_tolerance": 1.0e-9,
        "minimum_level_fraction": 0.0,
        "maximum_level_fraction": 1.0,
    }


def _step(index, time_seconds, total, bottoms, distillate):
    return {
        "index": index,
        "time_seconds": time_seconds,
        "inventory_lbmol": [[total]],
        "bottoms_lbmolph": bottoms,
        "distillate_lbmolph": distillate,
        "level_fraction": [0.5, 0.5],
    }


def test_controlled_response_accepts_late_peak_and_final_correction():
    samples = (
        _step(1, 0.25, 10.0, 4.0, 3.0),
        _step(400, 100.0, 10.2, 4.1, 2.9),
        _step(1000, 250.0, 10.4, 4.2, 2.8),
        _step(1100, 275.0, 10.3, 4.3, 2.7),
        _step(1200, 300.0, 10.2, 4.4, 2.6),
    )

    assessment = _module()._analyze(samples, _limits())

    assert assessment["pass_gate"]
    assert assessment["metrics"]["consecutive_final_declines"] == 2


def test_controlled_response_rejects_unbounded_or_uncorrected_inventory():
    samples = (
        _step(1, 0.25, 10.0, 4.0, 3.0),
        _step(400, 100.0, 10.5, 4.1, 2.9),
        _step(800, 200.0, 11.0, 4.2, 2.8),
        _step(1000, 250.0, 11.5, 4.3, 2.7),
        _step(1200, 300.0, 12.0, 4.4, 2.6),
    )

    assessment = _module()._analyze(samples, _limits())

    assert not assessment["gates"]["bounded_inventory"]
    assert not assessment["gates"]["corrective_decline"]
    assert not assessment["pass_gate"]


def test_controlled_response_rejects_wrong_terminal_action_direction():
    samples = (
        _step(1, 0.25, 10.0, 4.0, 3.0),
        _step(400, 100.0, 10.2, 4.1, 2.9),
        _step(1000, 250.0, 10.4, 4.2, 2.8),
        _step(1100, 275.0, 10.3, 4.1, 2.9),
        _step(1200, 300.0, 10.2, 4.0, 3.0),
    )

    assessment = _module()._analyze(samples, _limits())

    assert not assessment["gates"]["bottoms_action"]
    assert not assessment["gates"]["distillate_action"]
