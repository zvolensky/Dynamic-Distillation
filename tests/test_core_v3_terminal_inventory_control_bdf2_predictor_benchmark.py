from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = (
    ROOT
    / "tools"
    / "run_core_v3_terminal_inventory_control_bdf2_predictor_benchmark.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("dd212_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_science_report_excludes_solver_work_fields() -> None:
    module = _module()
    report = {
        "index": 1,
        "time_seconds": 0.25,
        "method": "bdf2",
        "nfev": 9,
        "njev": 8,
        "residual_inf_norm": 1.0e-12,
        "jacobian_condition": 3.0e7,
        "inventory_lbmol": [[1.0]],
        "rate_coordinates": [[0.0]],
        "algebraic_coordinates": [0.0],
        "controller_memory": [0.0, 0.0],
        "level_fraction": [0.5, 0.5],
        "distillate_lbmolph": 1.0,
        "bottoms_lbmolph": 2.0,
        "physical": {"positive": True},
    }
    science = module._science_report(report)
    assert "nfev" not in science
    assert "njev" not in science
    assert "residual_inf_norm" not in science
    assert science["inventory_lbmol"] == [[1.0]]


def test_science_report_retains_endpoint_coordinates_and_products() -> None:
    module = _module()
    report = {
        "index": 2,
        "time_seconds": 0.5,
        "method": "bdf2",
        "inventory_lbmol": [[1.0, 2.0]],
        "rate_coordinates": [[0.1, 0.2]],
        "algebraic_coordinates": [3.0],
        "controller_memory": [4.0, 5.0],
        "level_fraction": [0.4, 0.6],
        "distillate_lbmolph": 6.0,
        "bottoms_lbmolph": 7.0,
        "physical": {"positive": True},
    }
    science = module._science_report(report)
    assert science["rate_coordinates"] == [[0.1, 0.2]]
    assert science["distillate_lbmolph"] == 6.0
    assert science["bottoms_lbmolph"] == 7.0
