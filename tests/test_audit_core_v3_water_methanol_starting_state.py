from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_water_methanol_starting_state as audit
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


def test_water_methanol_stream_aliases_are_resolved_without_mutation():
    case = load_case_from_excel(str(audit.ROOT / audit.DEFAULT_WORKBOOK))
    column = build_column_spec_from_case(case)

    roles = audit.resolve_stream_roles(column)

    assert {role: stream.name for role, stream in roles.items()} == {
        "feed": "Feed1",
        "distillate": "Top",
        "bottoms": "Bottom",
    }
    assert "Feed" not in column.streams
    assert "Distillate" not in column.streams


def test_live_water_methanol_starting_state_is_usable_but_not_steady():
    report = audit.build_report()

    assert report["classification"] == "usable_starting_state_not_steady"
    assert report["pass_gate"]
    assert report["decision"] == "ready_for_stationary_jacobian_audit"
    assert report["components"] == ["Water", "Methanol"]
    assert report["stream_names"] == {
        "feed": "Feed1",
        "distillate": "Top",
        "bottoms": "Bottom",
    }
    assert report["stage_count"] == 10
    assert report["feed_stage_1based"] == 8
    assert report["dynamic_dimension"] == 98
    assert report["stationary_dimension"] == 100
    assert report["physical_checks"]["minimum_free_vapor_volume_ft3"] > 0.0
    assert report["physical_checks"]["maximum_relative_eos_residual"] < 1.0e-12
    assert report["provider_calls"]["governing_residual"] == 60
    assert not report["provider_calls"]["fallback_attempted"]
    adjustments = report["source_adjustments"]
    assert adjustments["bottom_bubble_residual_inf_norm"] < 1.0e-10
    assert len(adjustments["bottom_bubble_vapor_mole_fraction"]) == len(
        report["components"]
    )
    assert np.isclose(sum(adjustments["bottom_bubble_vapor_mole_fraction"]), 1.0)
    assert adjustments["bottom_temperature_change_F"] > 1.0
    assert report["starting_residual"]["scaled_inf_norm"] > 1.0e-3
    assert np.allclose(
        report["physical_checks"]["terminal_inventory_residual_lbmol"],
        [0.0, 0.0],
        rtol=0.0,
        atol=1.0e-12,
    )
    assert not report["nonlinear_solve_attempted"]
    assert not report["jacobian_evaluated"]
    assert not report["timestep_attempted"]
