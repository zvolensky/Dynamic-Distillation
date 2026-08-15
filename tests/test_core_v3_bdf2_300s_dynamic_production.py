from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "run_core_v3_bdf2_300s_dynamic_production.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd218_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dd218_is_one_five_minute_dynamic_path():
    assert _module()._integration() == {
        "duration_seconds": 300.0,
        "step_seconds": 0.25,
        "steps": 1200,
        "name": "dd218_dynamic_300s",
    }


def test_compact_evidence_keeps_first_five_second_samples_and_final():
    steps = [{"index": index, "value": index} for index in range(1, 46)]

    compact = _module()._compact_steps(steps, 20)

    assert [item["index"] for item in compact] == [1, 20, 40, 45]


def test_compact_evidence_rejects_invalid_interval():
    with pytest.raises(ValueError, match="interval must be positive"):
        _module()._compact_steps([{"index": 1}], 0)


def test_dd218_freezes_session_timing_and_compact_evidence_sources():
    implementation = _module().IMPLEMENTATION

    assert (
        "src/dynamic_distillation/core_v3/production_session_timing_policy_v1.py"
        in implementation
    )
    assert (
        "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_session_v1.py"
        in implementation
    )
