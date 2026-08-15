import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "run_core_v3_bdf2_reusable_session_proof.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd215_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dd215_paths_are_two_second_two_to_one_grids():
    paths = _module()._paths()

    assert paths["duration_seconds"] == 2.0
    assert paths["coarse_steps"] == 8
    assert paths["refined_steps"] == 16
    assert paths["shared_time_count"] == 8
    assert paths["shared_step_pairs_1based"][-1] == [8, 16]


def test_dd215_paths_reject_nondivisible_duration():
    with pytest.raises(ValueError, match="does not divide duration"):
        _module()._paths(duration_seconds=2.1)


def test_dd215_implementation_freezes_reusable_session_source():
    assert (
        "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_session_v1.py"
        in _module().IMPLEMENTATION
    )
