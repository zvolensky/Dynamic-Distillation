import csv

import pytest

from tools.audit_vapor_inventory_rate import audit_profile


def test_audit_vapor_inventory_rate_ranks_fd_rate_and_convective_estimate(tmp_path):
    path = tmp_path / "profile.csv"
    rows = [
        {
            "time_s": "0.0",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "10",
            "V_out_lbmolph": "100",
            "y_A": "0.8",
            "y_B": "0.2",
            "stage_mass_balance_resid_lbmolps": "0",
            "eq_phase_change_lbmolps_tray": "0",
        },
        {
            "time_s": "0.0",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "10",
            "V_out_lbmolph": "200",
            "y_A": "0.6",
            "y_B": "0.4",
            "stage_mass_balance_resid_lbmolps": "0",
            "eq_phase_change_lbmolps_tray": "0",
        },
        {
            "time_s": "1.0",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "10",
            "V_out_lbmolph": "100",
            "y_A": "0.7",
            "y_B": "0.3",
            "stage_mass_balance_resid_lbmolps": "0.1",
            "eq_phase_change_lbmolps_tray": "0.2",
        },
        {
            "time_s": "1.0",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "10",
            "V_out_lbmolph": "200",
            "y_A": "0.6",
            "y_B": "0.4",
            "stage_mass_balance_resid_lbmolps": "0",
            "eq_phase_change_lbmolps_tray": "0",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(path, initial_time_s=0.0, final_time_s=1.0, top_n=4)

    assert report["summary"]["n_stages"] == 2
    assert report["summary"]["max_abs_relative_inventory_rate_per_s"] == pytest.approx(1.0 / 4.0)
    top = report["top_component_rates"][0]
    assert top["stage_1based"] == 1
    assert top["component"] == "B"
    assert top["dn_dt_lbmolps"] == pytest.approx(1.0)
    assert top["convective_lbmolps_est"] == pytest.approx((200.0 * 0.4 - 100.0 * 0.3) / 3600.0)
