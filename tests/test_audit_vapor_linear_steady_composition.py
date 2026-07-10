import csv

import pytest

from tools.audit_vapor_linear_steady_composition import audit_profile


def test_audit_vapor_linear_steady_composition_solves_logged_balance(tmp_path):
    path = tmp_path / "profile.csv"
    rows = [
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "1",
            "V_out_lbmolph": "0",
            "y_A": "1.0",
            "y_B": "0.0",
            "y_target_A": "1.0",
            "y_target_B": "0.0",
            "tray_V_transport_in_lbmolps_A": "0",
            "tray_V_transport_in_lbmolps_B": "0",
            "tray_V_feed_lbmolps_A": "0",
            "tray_V_feed_lbmolps_B": "0",
        },
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "10",
            "V_out_lbmolph": "7200",
            "y_A": "0.4",
            "y_B": "0.6",
            "y_target_A": "0.5",
            "y_target_B": "0.5",
            "tray_V_transport_in_lbmolps_A": "1.0",
            "tray_V_transport_in_lbmolps_B": "1.0",
            "tray_V_feed_lbmolps_A": "0",
            "tray_V_feed_lbmolps_B": "0",
        },
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "3",
            "MV_lbmol": "1",
            "V_out_lbmolph": "0",
            "y_A": "1.0",
            "y_B": "0.0",
            "y_target_A": "1.0",
            "y_target_B": "0.0",
            "tray_V_transport_in_lbmolps_A": "0",
            "tray_V_transport_in_lbmolps_B": "0",
            "tray_V_feed_lbmolps_A": "0",
            "tray_V_feed_lbmolps_B": "0",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(path, time_s=0.2, equilibrium_tau_sec=0.5)

    top = report["top_interior_component_deltas"][0]
    assert top["stage_1based"] == 2
    assert top["component"] == "A"
    assert top["y_linear_steady"] == pytest.approx(0.5)
    assert top["y_linear_steady_minus_y"] == pytest.approx(0.1)
    assert report["summary"]["max_abs_y_linear_steady_minus_y_interior"] == pytest.approx(0.1)
