from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "run_core_v3_terminal_inventory_control_bdf2_worker_scaling.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd210_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _matrix(value: float, *, state_id: str = "state") -> dict:
    return {
        "method": "bdf2",
        "root_epoch": "root",
        "state_id": state_id,
        "matrix": np.asarray([[value, 0.0], [0.0, value]]),
    }


def test_matrix_comparison_accepts_exact_matrices() -> None:
    module = _module()
    comparison = module._matrix_comparison([_matrix(1.0)], [_matrix(1.0)])
    assert comparison["metadata_equal"]
    assert comparison["maximum_absolute_difference"] == 0.0


def test_matrix_comparison_measures_difference() -> None:
    module = _module()
    comparison = module._matrix_comparison([_matrix(1.0)], [_matrix(1.25)])
    assert comparison["metadata_equal"]
    assert comparison["maximum_absolute_difference"] == 0.25


def test_matrix_comparison_rejects_metadata_difference() -> None:
    module = _module()
    comparison = module._matrix_comparison(
        [_matrix(1.0)], [_matrix(1.0, state_id="other")]
    )
    assert not comparison["metadata_equal"]


def test_matrix_comparison_rejects_count_difference() -> None:
    module = _module()
    comparison = module._matrix_comparison([_matrix(1.0)], [])
    assert not comparison["metadata_equal"]
    assert np.isinf(comparison["maximum_absolute_difference"])
