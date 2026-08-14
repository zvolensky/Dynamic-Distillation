from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "run_core_v3_terminal_inventory_control_bdf2_60s_production.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd213_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paths_define_frozen_60_second_refinement() -> None:
    paths = _module()._paths()
    assert paths["duration_seconds"] == 60.0
    assert paths["coarse_steps"] == 240
    assert paths["refined_steps"] == 480
    assert paths["shared_time_count"] == 240
    assert paths["shared_step_pairs_1based"][0] == [1, 2]
    assert paths["shared_step_pairs_1based"][-1] == [240, 480]


def test_paths_reject_nondivisible_grid() -> None:
    with pytest.raises(ValueError, match="coarse grid"):
        _module()._paths(60.0, 0.7, 0.1)


def test_paths_reject_nonintegral_refinement_ratio() -> None:
    with pytest.raises(ValueError, match="refinement ratio"):
        _module()._paths(60.0, 0.3, 0.2)
