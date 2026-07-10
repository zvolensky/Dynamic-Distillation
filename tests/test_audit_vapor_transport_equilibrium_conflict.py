import csv

import pytest

from tools.audit_vapor_transport_equilibrium_conflict import audit_profile


def test_audit_vapor_transport_equilibrium_conflict_ranks_required_target_delta(tmp_path):
    path = tmp_path / "profile.csv"
    rows = [
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "1.0",
            "y_A": "0.5",
            "y_target_A": "0.5",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.0",
            "tray_V_equilibrium_transfer_lbmolps_A": "0.0",
            "tray_V_final_rhs_lbmolps_A": "0.0",
            "tray_V_transport_in_lbmolps_A": "0.0",
            "tray_V_transport_out_lbmolps_A": "0.0",
        },
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "10.0",
            "y_A": "0.40",
            "y_target_A": "0.35",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "1.0",
            "tray_V_equilibrium_transfer_lbmolps_A": "-1.0",
            "tray_V_final_rhs_lbmolps_A": "0.8",
            "tray_V_transport_in_lbmolps_A": "1.2",
            "tray_V_transport_out_lbmolps_A": "-0.2",
        },
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "3",
            "MV_lbmol": "8.0",
            "y_A": "0.20",
            "y_target_A": "0.19",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.05",
            "tray_V_equilibrium_transfer_lbmolps_A": "-0.01",
            "tray_V_final_rhs_lbmolps_A": "0.04",
            "tray_V_transport_in_lbmolps_A": "0.10",
            "tray_V_transport_out_lbmolps_A": "-0.05",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(path, time_s=0.2, equilibrium_tau_sec=0.5, top_n=2)

    assert report["summary"]["n_stages"] == 3
    top = report["top_interior_final_rhs_conflicts"][0]
    assert top["stage_1based"] == 2
    assert top["component"] == "A"
    assert top["cancellation_coverage"] == pytest.approx(1.0)
    assert top["required_y_target_to_cancel_pre_rhs"] == pytest.approx(0.35)
    assert top["required_target_delta"] == pytest.approx(0.0)


def test_audit_vapor_transport_equilibrium_conflict_detects_fighting_transfer(tmp_path):
    path = tmp_path / "profile.csv"
    rows = [
        {
            "time_s": "1.0",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "1.0",
            "y_A": "0.5",
            "y_target_A": "0.5",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.0",
            "tray_V_equilibrium_transfer_lbmolps_A": "0.0",
            "tray_V_final_rhs_lbmolps_A": "0.0",
        },
        {
            "time_s": "1.0",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "4.0",
            "y_A": "0.5",
            "y_target_A": "0.6",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.4",
            "tray_V_equilibrium_transfer_lbmolps_A": "0.8",
            "tray_V_final_rhs_lbmolps_A": "1.2",
        },
        {
            "time_s": "1.0",
            "node_type": "stage",
            "stage": "3",
            "MV_lbmol": "1.0",
            "y_A": "0.5",
            "y_target_A": "0.5",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.0",
            "tray_V_equilibrium_transfer_lbmolps_A": "0.0",
            "tray_V_final_rhs_lbmolps_A": "0.0",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(path, time_s=1.0, equilibrium_tau_sec=0.5)
    top = report["top_interior_final_rhs_conflicts"][0]

    assert top["equilibrium_fights_transport"] == pytest.approx(1.0)
    assert top["cancellation_coverage"] == pytest.approx(-2.0)
    assert top["required_y_target_to_cancel_pre_rhs"] == pytest.approx(0.45)
    assert top["required_target_delta"] == pytest.approx(-0.15)
