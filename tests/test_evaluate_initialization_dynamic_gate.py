from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "evaluate_initialization_dynamic_gate.py"
_SPEC = spec_from_file_location("evaluate_initialization_dynamic_gate", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

summarize_run = _MODULE.summarize_run
evaluate_candidate = _MODULE.evaluate_candidate
_parse_ratio_limit = _MODULE._parse_ratio_limit


def test_summarize_run_uses_final_row_and_peak_values_in_window():
    rows = [
        {"time_s": "0", "steady_state_score": "3", "ss_max_rel_state_rate_per_s": "0.1", "ss_max_temp_rate_F_per_s": "0.2", "P_top_drum_psia": "170"},
        {"time_s": "10", "steady_state_score": "5", "ss_max_rel_state_rate_per_s": "0.3", "ss_max_temp_rate_F_per_s": "0.4", "P_top_drum_psia": "171"},
        {"time_s": "20", "steady_state_score": "4", "ss_max_rel_state_rate_per_s": "0.2", "ss_max_temp_rate_F_per_s": "0.6", "P_top_drum_psia": "172"},
    ]

    summary = summarize_run(rows, max_time_s=10, endpoint_fields=["P_top_drum_psia"])

    assert summary["final_time_s"] == pytest.approx(10.0)
    assert summary["final_score"] == pytest.approx(5.0)
    assert summary["peak_score"] == pytest.approx(5.0)
    assert summary["peak_rel_rate_per_s"] == pytest.approx(0.3)
    assert summary["final_P_top_drum_psia"] == pytest.approx(171.0)


def test_summarize_run_adds_requested_summary_ratio_fields():
    rows = [
        {"time_s": "0", "steady_state_score": "3", "ss_max_rel_state_rate_per_s": "0.1", "ss_max_temp_rate_F_per_s": "0.2", "pv_inner_dv_max_lbmolph": "2"},
        {"time_s": "10", "steady_state_score": "5", "ss_max_rel_state_rate_per_s": "0.3", "ss_max_temp_rate_F_per_s": "0.4", "pv_inner_dv_max_lbmolph": "7"},
    ]

    summary = summarize_run(rows, summary_ratio_fields=["pv_inner_dv_max_lbmolph"])

    assert summary["final_pv_inner_dv_max_lbmolph"] == pytest.approx(7.0)
    assert summary["peak_pv_inner_dv_max_lbmolph"] == pytest.approx(7.0)


def test_evaluate_candidate_fails_when_static_candidate_is_dynamically_worse():
    baseline = {
        "final_score": 1.0,
        "peak_score": 2.0,
        "final_rel_rate_per_s": 0.01,
        "peak_rel_rate_per_s": 0.02,
        "final_temp_rate_F_per_s": 0.2,
        "final_P_top_drum_psia": 171.0,
    }
    candidate = {
        "final_score": 1.2,
        "peak_score": 1.5,
        "final_rel_rate_per_s": 0.009,
        "peak_rel_rate_per_s": 0.015,
        "final_temp_rate_F_per_s": 0.3,
        "final_P_top_drum_psia": 174.0,
    }

    report = evaluate_candidate(
        baseline,
        candidate,
        endpoint_drift_limits={"P_top_drum_psia": 0.5},
    )

    assert report["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "final score ratio" in failed
    assert "P_top_drum_psia final absolute drift" in failed


def test_evaluate_candidate_passes_when_all_limits_are_met():
    baseline = {
        "final_score": 2.0,
        "peak_score": 4.0,
        "final_rel_rate_per_s": 0.02,
        "peak_rel_rate_per_s": 0.05,
        "final_temp_rate_F_per_s": 0.4,
        "final_T_sump_F": 220.0,
    }
    candidate = {
        "final_score": 1.5,
        "peak_score": 3.0,
        "final_rel_rate_per_s": 0.015,
        "peak_rel_rate_per_s": 0.04,
        "final_temp_rate_F_per_s": 0.35,
        "final_T_sump_F": 220.2,
    }

    report = evaluate_candidate(
        baseline,
        candidate,
        max_final_temp_rate_ratio=1.0,
        endpoint_drift_limits={"T_sump_F": 0.5},
    )

    assert report["passed"] is True


def test_evaluate_candidate_checks_requested_summary_ratio_limits():
    baseline = {
        "final_score": 1.0,
        "peak_score": 1.0,
        "final_rel_rate_per_s": 0.01,
        "peak_rel_rate_per_s": 0.01,
        "final_pv_inner_dv_max_lbmolph": 2.0,
        "peak_pv_inner_dv_max_lbmolph": 3.0,
    }
    candidate = {
        "final_score": 1.0,
        "peak_score": 1.0,
        "final_rel_rate_per_s": 0.01,
        "peak_rel_rate_per_s": 0.01,
        "final_pv_inner_dv_max_lbmolph": 2.5,
        "peak_pv_inner_dv_max_lbmolph": 7.0,
    }

    report = evaluate_candidate(
        baseline,
        candidate,
        summary_ratio_limits={"pv_inner_dv_max_lbmolph": 1.5},
    )

    assert report["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "pv_inner_dv_max_lbmolph peak ratio" in failed


def test_parse_ratio_limit_requires_field_and_nonnegative_limit():
    assert _parse_ratio_limit("K_state_over_K_thermo_max_abs=1.1") == ("K_state_over_K_thermo_max_abs", 1.1)
    with pytest.raises(Exception):
        _parse_ratio_limit("K_state_over_K_thermo_max_abs=-1")
