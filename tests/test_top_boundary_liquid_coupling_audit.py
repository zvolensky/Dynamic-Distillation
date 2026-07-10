from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "top_boundary_liquid_coupling_audit.py"
_SPEC = spec_from_file_location("top_boundary_liquid_coupling_audit", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

component_names = _MODULE.component_names
compare_top_liquid = _MODULE.compare_top_liquid


def test_component_names_are_inferred_from_top_liquid_net_fields():
    rows = [
        {
            "top_L_net_n_Propane_lbmolph": "1",
            "top_L_net_n_Butane_lbmolph": "2",
            "top_L_net_worst_abs_lbmolph": "2",
        }
    ]

    assert component_names(rows) == ["n_Butane", "n_Propane"]


def test_compare_top_liquid_ranks_component_net_worsening():
    baseline = [
        {
            "time_s": "0",
            "top_L_net_lbmolph": "10",
            "top_L_net_worst_component_1based": "1",
            "top_L_net_worst_abs_lbmolph": "8",
            "V_condensed_in_lbmolph": "100",
            "top_L_reflux_out_lbmolph": "60",
            "top_L_distillate_out_lbmolph": "40",
            "top_L_net_n_Propane_lbmolph": "8",
            "top_L_net_n_Butane_lbmolph": "2",
            "top_L_cond_x_minus_drum_x_n_Propane": "0.01",
            "top_L_cond_x_minus_drum_x_n_Butane": "0.02",
        }
    ]
    candidate = [
        {
            "time_s": "0",
            "top_L_net_lbmolph": "25",
            "top_L_net_worst_component_1based": "2",
            "top_L_net_worst_abs_lbmolph": "80",
            "V_condensed_in_lbmolph": "120",
            "top_L_reflux_out_lbmolph": "60",
            "top_L_distillate_out_lbmolph": "40",
            "top_L_net_n_Propane_lbmolph": "10",
            "top_L_net_n_Butane_lbmolph": "80",
            "top_L_cond_x_minus_drum_x_n_Propane": "0.02",
            "top_L_cond_x_minus_drum_x_n_Butane": "0.15",
        }
    ]

    report = compare_top_liquid(baseline, candidate, top_n=2)

    worst = report["worst_component_net_worsenings"][0]
    assert worst["component"] == "n_Butane"
    assert worst["abs_delta"] == pytest.approx(78.0)
    assert report["final_candidate"]["top_L_net_worst_abs_lbmolph"] == pytest.approx(80.0)
    assert report["worst_condensed_vs_drum_x_worsenings"][0]["component"] == "n_Butane"


def test_compare_top_liquid_honors_max_time_window():
    baseline = [
        {"time_s": "0", "top_L_net_n_Propane_lbmolph": "1"},
        {"time_s": "10", "top_L_net_n_Propane_lbmolph": "1"},
    ]
    candidate = [
        {"time_s": "0", "top_L_net_n_Propane_lbmolph": "2"},
        {"time_s": "10", "top_L_net_n_Propane_lbmolph": "99"},
    ]

    report = compare_top_liquid(baseline, candidate, max_time_s=0, top_n=1)

    assert report["compared_times"] == [0.0]
    assert report["worst_component_net_worsenings"][0]["candidate"] == pytest.approx(2.0)
