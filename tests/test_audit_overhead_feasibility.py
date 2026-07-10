from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_overhead_feasibility.py"
_SPEC = spec_from_file_location("audit_overhead_feasibility", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

audit_overhead_feasibility = _MODULE.audit_overhead_feasibility


def test_audit_flags_top_starved_before_distillate():
    summary_rows = [
        {
            "time_s": "0",
            "V_condensed_in_lbmolph": "100",
            "top_L_reflux_out_lbmolph": "120",
            "top_L_distillate_out_lbmolph": "10",
        }
    ]

    report = audit_overhead_feasibility(
        summary_rows,
        reference_reflux_lbmolph=120.0,
        reference_distillate_lbmolph=30.0,
    )

    assert report["diagnosis"] == "top_starved_before_distillate"
    final = report["final_top_boundary"]
    assert final["condensate_minus_reflux_lbmolph"] == pytest.approx(-20.0)
    assert report["reference"]["final_condensate_fraction_of_reference"] == pytest.approx(100.0 / 150.0)


def test_profile_summary_reports_vapor_drop_and_clamp_fraction():
    summary_rows = [
        {
            "time_s": "10",
            "V_condensed_in_lbmolph": "90",
            "top_L_reflux_out_lbmolph": "60",
            "top_L_distillate_out_lbmolph": "20",
        }
    ]
    profile_rows = [
        {
            "time_s": "10",
            "node_type": "stage",
            "stage": "1",
            "V_out_lbmolph": "0",
            "vflow_energy_clamped": "0",
        },
        {
            "time_s": "10",
            "node_type": "stage",
            "stage": "2",
            "V_out_lbmolph": "140",
            "vflow_energy_clamped": "1",
        },
        {
            "time_s": "10",
            "node_type": "stage",
            "stage": "3",
            "V_out_lbmolph": "200",
            "vflow_energy_clamped": "0",
        },
    ]

    report = audit_overhead_feasibility(summary_rows, profile_rows=profile_rows)
    profile = report["profile"]

    assert profile["top_stage"] == 1
    assert profile["bottom_stage"] == 3
    assert profile["overhead_vapor_stage"] == 2
    assert profile["overhead_vapor_to_condenser_lbmolph"] == pytest.approx(140.0)
    assert profile["overhead_vapor_fraction_of_bottom"] == pytest.approx(0.7)
    assert profile["top_vapor_fraction_of_bottom"] == pytest.approx(0.0)
    assert profile["vflow_clamped_fraction_in_final_window"] == pytest.approx(1.0 / 3.0)
    assert profile["largest_adjacent_vapor_drop"]["from_stage"] == pytest.approx(3.0)
    assert profile["largest_adjacent_vapor_drop"]["to_stage"] == pytest.approx(2.0)
    assert profile["largest_adjacent_vapor_drop"]["delta_lbmolph"] == pytest.approx(60.0)
