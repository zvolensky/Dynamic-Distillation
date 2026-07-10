import csv

import pytest

from tools.audit_vapor_rhs_material_terms import audit_profile


def test_audit_vapor_rhs_material_terms_ranks_dominant_term(tmp_path):
    path = tmp_path / "profile.csv"
    rows = [
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "10",
            "y_A": "0.8",
            "y_B": "0.2",
            "tray_V_transport_in_lbmolps_A": "0.0",
            "tray_V_transport_out_lbmolps_A": "-0.1",
            "tray_V_feed_lbmolps_A": "0.0",
            "tray_V_terminal_adjust_lbmolps_A": "0.0",
            "tray_V_holdup_relax_lbmolps_A": "0.0",
            "tray_V_equilibrium_transfer_lbmolps_A": "0.0",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "-0.1",
            "tray_V_final_rhs_lbmolps_A": "-0.1",
            "tray_V_transport_in_lbmolps_B": "0.0",
            "tray_V_transport_out_lbmolps_B": "-0.2",
            "tray_V_feed_lbmolps_B": "0.0",
            "tray_V_terminal_adjust_lbmolps_B": "0.0",
            "tray_V_holdup_relax_lbmolps_B": "0.0",
            "tray_V_equilibrium_transfer_lbmolps_B": "0.0",
            "tray_V_pre_equilibrium_rhs_lbmolps_B": "-0.2",
            "tray_V_final_rhs_lbmolps_B": "-0.2",
        },
        {
            "time_s": "0.2",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "4",
            "y_A": "0.25",
            "y_B": "0.75",
            "tray_V_transport_in_lbmolps_A": "0.7",
            "tray_V_transport_out_lbmolps_A": "-0.1",
            "tray_V_feed_lbmolps_A": "0.0",
            "tray_V_terminal_adjust_lbmolps_A": "0.0",
            "tray_V_holdup_relax_lbmolps_A": "0.0",
            "tray_V_equilibrium_transfer_lbmolps_A": "-0.05",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.6",
            "tray_V_final_rhs_lbmolps_A": "0.55",
            "tray_V_transport_in_lbmolps_B": "0.1",
            "tray_V_transport_out_lbmolps_B": "-0.05",
            "tray_V_feed_lbmolps_B": "0.0",
            "tray_V_terminal_adjust_lbmolps_B": "0.0",
            "tray_V_holdup_relax_lbmolps_B": "0.0",
            "tray_V_equilibrium_transfer_lbmolps_B": "0.0",
            "tray_V_pre_equilibrium_rhs_lbmolps_B": "0.05",
            "tray_V_final_rhs_lbmolps_B": "0.05",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(path, time_s=0.2, top_n=3)

    assert report["summary"]["n_stages"] == 2
    top = report["top_component_terms"][0]
    assert top["stage_1based"] == 2
    assert top["component"] == "A"
    assert top["dominant_term"] == "transport_in"
    assert top["final_rhs_lbmolps"] == pytest.approx(0.55)
    assert top["relative_rhs_per_s"] == pytest.approx(0.55 / 2.0)
