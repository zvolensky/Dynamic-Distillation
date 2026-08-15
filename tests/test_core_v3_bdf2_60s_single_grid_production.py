from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "run_core_v3_bdf2_60s_single_grid_production.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd217_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dd217_is_one_qualified_60_second_grid():
    integration = _module()._integration()

    assert integration == {
        "duration_seconds": 60.0,
        "step_seconds": 0.25,
        "steps": 240,
        "name": "dd217_production_60s",
    }


def test_dd217_timing_policy_gates_segment_and_complete_session():
    module = _module()
    limits = module._timing_limits(
        {
            "integration": module._integration(),
            "timing_limits": {
                "startup_wall_sec": 10.0,
                "segment_wall_sec": 180.0,
                "active_wall_sec": 180.0,
                "shutdown_wall_sec": 30.0,
                "total_wall_sec": 225.0,
                "unattributed_wall_sec": 1.0,
                "identity_tolerance_sec": 1.0e-6,
            },
        }
    )

    assert limits.segment_limits[0].name == "dd217_production_60s"
    assert limits.segment_limits[0].maximum_wall_seconds == 180.0
    assert limits.maximum_total_wall_seconds == 225.0


def test_dd217_freezes_timing_policy_and_reusable_session_sources():
    implementation = _module().IMPLEMENTATION

    assert (
        "src/dynamic_distillation/core_v3/production_session_timing_policy_v1.py"
        in implementation
    )
    assert (
        "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_session_v1.py"
        in implementation
    )
