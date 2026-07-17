import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_k_state_drift.py"
_SPEC = spec_from_file_location("audit_k_state_drift", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

audit_profile = _MODULE.audit_profile


def test_audit_profile_reports_k_delta_trend_and_gate_failure(tmp_path):
    profile = tmp_path / "profile.csv"
    fields = [
        "time_s",
        "node_type",
        "stage",
        "K_state_A",
        "K_thermo_A",
        "K_state_over_K_thermo_A",
        "x_A",
        "y_A",
        "y_target_A",
        "y_eq_A",
    ]
    rows = [
        {
            "time_s": "0",
            "node_type": "stage",
            "stage": "2",
            "K_state_A": "1.1",
            "K_thermo_A": "1.0",
            "K_state_over_K_thermo_A": "1.1",
            "x_A": "0.4",
            "y_A": "0.44",
            "y_target_A": "0.4",
            "y_eq_A": "0.4",
        },
        {
            "time_s": "10",
            "node_type": "stage",
            "stage": "2",
            "K_state_A": "2.0",
            "K_thermo_A": "1.0",
            "K_state_over_K_thermo_A": "2.0",
            "x_A": "0.4",
            "y_A": "0.8",
            "y_target_A": "0.4",
            "y_eq_A": "0.4",
        },
    ]
    with profile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(
        profile,
        max_final_abs_delta=0.5,
        max_positive_abs_delta_trend=0.25,
    )

    assert report["passed"] is False
    assert report["summary"]["final_max_abs_K_state_minus_K_thermo"] == pytest.approx(1.0)
    assert report["summary"]["positive_abs_delta_trend_from_min"] == pytest.approx(0.9)
    assert report["summary"]["final_worst_delta_stage_1based"] == 2
    assert report["summary"]["final_worst_delta_component"] == "A"


def test_normalized_y_target_gate_ignores_raw_k_normalization_difference(tmp_path):
    profile = tmp_path / "normalized_profile.csv"
    fields = [
        "time_s",
        "node_type",
        "stage",
        "K_state_A",
        "K_thermo_A",
        "K_state_over_K_thermo_A",
        "x_A",
        "y_A",
        "y_target_A",
        "y_eq_A",
    ]
    rows = [
        {
            "time_s": str(t),
            "node_type": "stage",
            "stage": "19",
            "K_state_A": "1.1",
            "K_thermo_A": "2.0",
            "K_state_over_K_thermo_A": "0.55",
            "x_A": "0.4",
            "y_A": "0.44",
            "y_target_A": "0.44",
            "y_eq_A": "0.44",
        }
        for t in (0, 10)
    ]
    with profile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(
        profile,
        max_final_abs_y_delta=1.0e-9,
        max_peak_abs_y_delta=1.0e-9,
        max_positive_abs_y_delta_trend=1.0e-9,
    )

    assert report["passed"] is True
    assert report["summary"]["final_max_abs_y_minus_y_target"] == pytest.approx(0.0)
    assert report["summary"]["final_max_abs_K_state_minus_K_thermo"] == pytest.approx(0.9)
