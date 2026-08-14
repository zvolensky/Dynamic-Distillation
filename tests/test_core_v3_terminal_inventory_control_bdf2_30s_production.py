from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "run_core_v3_terminal_inventory_control_bdf2_30s_production.py"


def _module():
    spec = importlib.util.spec_from_file_location("dd209_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_basis_summary_requires_exactly_one_rebuild_per_worker_per_root() -> None:
    module = _module()
    evidence = [
        {"root_epoch": "root-a", "basis_rebuilds": 4},
        {"root_epoch": "root-a", "basis_rebuilds": 0},
        {"root_epoch": "root-b", "basis_rebuilds": 4},
    ]
    summary = module._basis_summary(evidence, 4)
    assert summary["pass"]
    assert summary["root_count"] == 2


def test_basis_summary_rejects_extra_rebuild() -> None:
    module = _module()
    evidence = [
        {"root_epoch": "root-a", "basis_rebuilds": 4},
        {"root_epoch": "root-a", "basis_rebuilds": 1},
    ]
    assert not module._basis_summary(evidence, 4)["pass"]


def test_response_gates_accept_conservative_monotone_paths() -> None:
    module = _module()
    coarse = {
        "total_inventory_change_lbmol": 1.0,
        "expected_total_inventory_change_lbmol": 1.0,
        "total_inventory_strictly_increasing": True,
        "total_inventory_relative_error": 0.0,
        "component_inventory_identity_max_abs_lbmol": 0.0,
    }
    refined = dict(coarse)
    limits = {
        "integrated_response_relative_error": 1.0e-6,
        "global_component_inventory_identity_lbmol": 1.0e-6,
        "external_flow_explanation_lbmol": 1.0e-10,
        "response_relative_cross_grid": 1.0e-5,
    }
    cross, gates = module._response_gates(coarse, refined, limits)
    assert all(gates.values())
    assert cross["unexplained_difference_lbmol"] == 0.0


def test_response_gates_reject_nonmonotone_path() -> None:
    module = _module()
    coarse = {
        "total_inventory_change_lbmol": 1.0,
        "expected_total_inventory_change_lbmol": 1.0,
        "total_inventory_strictly_increasing": False,
        "total_inventory_relative_error": 0.0,
        "component_inventory_identity_max_abs_lbmol": 0.0,
    }
    refined = dict(coarse, total_inventory_strictly_increasing=True)
    limits = {
        "integrated_response_relative_error": 1.0e-6,
        "global_component_inventory_identity_lbmol": 1.0e-6,
        "external_flow_explanation_lbmol": 1.0e-10,
        "response_relative_cross_grid": 1.0e-5,
    }
    _, gates = module._response_gates(coarse, refined, limits)
    assert not gates["coarse"]
