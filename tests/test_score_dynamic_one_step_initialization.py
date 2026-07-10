import csv

import pytest

from tools.score_dynamic_one_step_initialization import score_run


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_score_dynamic_one_step_initialization_combines_dynamic_and_profile_terms(tmp_path):
    summary = tmp_path / "summary.csv"
    profile = tmp_path / "profile.csv"
    _write_csv(
        summary,
        [
            {
                "time_s": "0.0",
                "steady_state_score": "9",
                "ss_max_rel_state_rate_per_s": "0.09",
                "ss_max_temp_rate_F_per_s": "0.9",
            },
            {
                "time_s": "0.2",
                "steady_state_score": "2",
                "ss_max_rel_state_rate_per_s": "0.02",
                "ss_max_temp_rate_F_per_s": "0.1",
            },
        ],
    )
    _write_csv(
        profile,
        [
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "1",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "2",
                "MV_lbmol": "10",
                "y_A": "0.40",
                "y_target_A": "0.35",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "1.0",
                "tray_V_equilibrium_transfer_lbmolps_A": "-1.0",
                "tray_V_final_rhs_lbmolps_A": "0.0",
            },
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "3",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "1",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "2",
                "MV_lbmol": "10",
                "y_A": "0.42",
                "y_target_A": "0.37",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "1.0",
                "tray_V_equilibrium_transfer_lbmolps_A": "-1.0",
                "tray_V_final_rhs_lbmolps_A": "0.0",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "3",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
        ],
    )

    report = score_run(
        summary,
        profile,
        max_time_s=0.2,
        refs={
            "dynamic_score": 1,
            "rel_rate_per_s": 0.01,
            "temp_rate_F_per_s": 0.1,
            "vapor_rhs_lbmolps": 0.1,
            "coverage_error": 1,
            "overcoverage": 1,
            "y_drift": 0.01,
        },
        weights={
            "dynamic_score": 1,
            "rel_rate_per_s": 1,
            "temp_rate_F_per_s": 1,
            "vapor_rhs_lbmolps": 1,
            "coverage_error": 1,
            "overcoverage": 1,
            "y_drift": 1,
        },
    )

    assert report["metrics"]["dynamic_score"] == pytest.approx(2.0)
    assert report["metrics"]["rel_rate_per_s"] == pytest.approx(0.02)
    assert report["metrics"]["coverage_error"] == pytest.approx(0.0)
    assert report["metrics"]["y_drift"] == pytest.approx(0.02)
    assert report["terms"]["dynamic_score"] == pytest.approx(2.0)
    assert report["terms"]["rel_rate_per_s"] == pytest.approx(2.0)
    assert report["terms"]["y_drift"] == pytest.approx(2.0)


def test_score_dynamic_one_step_initialization_penalizes_overcoverage(tmp_path):
    summary = tmp_path / "summary.csv"
    profile = tmp_path / "profile.csv"
    _write_csv(
        summary,
        [
            {
                "time_s": "0.2",
                "steady_state_score": "1",
                "ss_max_rel_state_rate_per_s": "0.01",
                "ss_max_temp_rate_F_per_s": "0.1",
            }
        ],
    )
    _write_csv(
        profile,
        [
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "1",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "2",
                "MV_lbmol": "4",
                "y_A": "0.5",
                "y_target_A": "0.6",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.4",
                "tray_V_equilibrium_transfer_lbmolps_A": "0.8",
                "tray_V_final_rhs_lbmolps_A": "1.2",
            },
            {
                "time_s": "0.0",
                "node_type": "stage",
                "stage": "3",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "1",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "2",
                "MV_lbmol": "4",
                "y_A": "0.5",
                "y_target_A": "0.6",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.4",
                "tray_V_equilibrium_transfer_lbmolps_A": "0.8",
                "tray_V_final_rhs_lbmolps_A": "1.2",
            },
            {
                "time_s": "0.2",
                "node_type": "stage",
                "stage": "3",
                "MV_lbmol": "1",
                "y_A": "0.5",
                "y_target_A": "0.5",
                "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
                "tray_V_equilibrium_transfer_lbmolps_A": "0",
                "tray_V_final_rhs_lbmolps_A": "0",
            },
        ],
    )

    report = score_run(summary, profile)

    assert report["metrics"]["overcoverage"] == pytest.approx(0.0)
    assert report["metrics"]["coverage_error"] == pytest.approx(3.0)
    assert report["top_vapor_conflicts"][0]["equilibrium_fights_transport"] == pytest.approx(1.0)
