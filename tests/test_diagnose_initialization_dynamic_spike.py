from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "diagnose_initialization_dynamic_spike.py"
_SPEC = spec_from_file_location("diagnose_initialization_dynamic_spike", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

find_worst_summary_time = _MODULE.find_worst_summary_time
summary_deltas = _MODULE.summary_deltas
profile_deltas = _MODULE.profile_deltas


def test_find_worst_summary_time_uses_score_and_relative_rate_ratios():
    baseline = [
        {"time_s": "10", "steady_state_score": "2", "ss_max_rel_state_rate_per_s": "0.1"},
        {"time_s": "20", "steady_state_score": "2", "ss_max_rel_state_rate_per_s": "0.1"},
    ]
    candidate = [
        {"time_s": "10", "steady_state_score": "3", "ss_max_rel_state_rate_per_s": "0.2"},
        {"time_s": "20", "steady_state_score": "4", "ss_max_rel_state_rate_per_s": "0.5"},
    ]

    assert find_worst_summary_time(baseline, candidate) == pytest.approx(20.0)


def test_summary_deltas_reports_candidate_worst_state_metadata():
    baseline = [
        {"time_s": "10", "steady_state_score": "2", "ss_max_rel_state_rate_per_s": "0.1"},
    ]
    candidate = [
        {
            "time_s": "10",
            "steady_state_score": "4",
            "ss_max_rel_state_rate_per_s": "0.2",
            "ss_rel_state_rate_state_key": "tray_V",
            "ss_rel_state_rate_stage_1based": "4",
            "ss_rel_state_rate_component_name": "n-Butane",
        },
    ]

    report = summary_deltas(baseline, candidate, time_s=10, fields=["steady_state_score"])

    assert report["candidate_worst_state_key"] == "tray_V"
    assert report["candidate_worst_state_stage_1based"] == "4"
    assert report["fields"][0]["ratio"] == pytest.approx(2.0)


def test_profile_deltas_discovers_stages_without_hard_coded_stage_ids():
    baseline = [
        {"time_s": "10", "node_type": "stage", "stage": "2", "V_out_lbmolph": "100", "MV_lbmol": "10"},
        {"time_s": "10", "node_type": "stage", "stage": "7", "V_out_lbmolph": "100", "MV_lbmol": "10"},
    ]
    candidate = [
        {"time_s": "10", "node_type": "stage", "stage": "2", "V_out_lbmolph": "105", "MV_lbmol": "10"},
        {"time_s": "10", "node_type": "stage", "stage": "7", "V_out_lbmolph": "250", "MV_lbmol": "9"},
    ]

    report = profile_deltas(baseline, candidate, time_s=10, fields=["V_out_lbmolph", "MV_lbmol"], top_n=1)

    assert report[0]["stage_1based"] == 7
    assert report[0]["fields"][0]["field"] == "V_out_lbmolph"
