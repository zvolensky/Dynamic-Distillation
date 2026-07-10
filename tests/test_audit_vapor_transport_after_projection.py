import csv

import pytest

from tools.audit_vapor_transport_after_projection import audit_profile


def test_audit_profile_ranks_vapor_drift_and_k_mismatch(tmp_path):
    path = tmp_path / "profile.csv"
    fields = [
        "time_s",
        "node_type",
        "stage",
        "MV_lbmol",
        "V_out_lbmolph",
        "eq_phase_change_lbmolps_tray",
        "eq_target_vapor_delta_lbmol_tray",
        "stage_mass_balance_resid_lbmolps",
        "x_A",
        "x_B",
        "x_eq_A",
        "x_eq_B",
        "y_A",
        "y_B",
        "y_target_A",
        "y_target_B",
        "y_eq_A",
        "y_eq_B",
        "K_state_over_K_eq_relax_A",
        "K_state_over_K_eq_relax_B",
    ]
    rows = [
        {
            "time_s": "0.0",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "1",
            "V_out_lbmolph": "0",
            "eq_phase_change_lbmolps_tray": "0",
            "eq_target_vapor_delta_lbmol_tray": "0",
            "stage_mass_balance_resid_lbmolps": "0",
            "x_A": "0.5",
            "x_B": "0.5",
            "x_eq_A": "0.5",
            "x_eq_B": "0.5",
            "y_A": "0.8",
            "y_B": "0.2",
            "y_target_A": "0.8",
            "y_target_B": "0.2",
            "y_eq_A": "0.8",
            "y_eq_B": "0.2",
            "K_state_over_K_eq_relax_A": "1.0",
            "K_state_over_K_eq_relax_B": "1.0",
        },
        {
            "time_s": "0.0",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "2",
            "V_out_lbmolph": "100",
            "eq_phase_change_lbmolps_tray": "0",
            "eq_target_vapor_delta_lbmol_tray": "0",
            "stage_mass_balance_resid_lbmolps": "0",
            "x_A": "0.4",
            "x_B": "0.6",
            "x_eq_A": "0.4",
            "x_eq_B": "0.6",
            "y_A": "0.7",
            "y_B": "0.3",
            "y_target_A": "0.7",
            "y_target_B": "0.3",
            "y_eq_A": "0.7",
            "y_eq_B": "0.3",
            "K_state_over_K_eq_relax_A": "1.0",
            "K_state_over_K_eq_relax_B": "1.0",
        },
        {
            "time_s": "1.0",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "1",
            "V_out_lbmolph": "0",
            "eq_phase_change_lbmolps_tray": "0",
            "eq_target_vapor_delta_lbmol_tray": "0",
            "stage_mass_balance_resid_lbmolps": "0",
            "x_A": "0.5",
            "x_B": "0.5",
            "x_eq_A": "0.5",
            "x_eq_B": "0.5",
            "y_A": "0.78",
            "y_B": "0.22",
            "y_target_A": "0.8",
            "y_target_B": "0.2",
            "y_eq_A": "0.8",
            "y_eq_B": "0.2",
            "K_state_over_K_eq_relax_A": "0.9",
            "K_state_over_K_eq_relax_B": "1.1",
        },
        {
            "time_s": "1.0",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "2",
            "V_out_lbmolph": "120",
            "eq_phase_change_lbmolps_tray": "0",
            "eq_target_vapor_delta_lbmol_tray": "0",
            "stage_mass_balance_resid_lbmolps": "0",
            "x_A": "0.4",
            "x_B": "0.6",
            "x_eq_A": "0.5",
            "x_eq_B": "0.5",
            "y_A": "0.65",
            "y_B": "0.35",
            "y_target_A": "0.7",
            "y_target_B": "0.3",
            "y_eq_A": "0.7",
            "y_eq_B": "0.3",
            "K_state_over_K_eq_relax_A": "0.5",
            "K_state_over_K_eq_relax_B": "2.0",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(path, initial_time_s=0.0, final_time_s=1.0, top_n=4)

    assert report["summary"]["n_stages"] == 2
    assert report["summary"]["max_abs_y_gap_final"] == pytest.approx(0.05)
    assert report["summary"]["max_abs_dy_dt_per_s"] == pytest.approx(0.05)
    assert report["top_stage_rankings"][0]["stage_1based"] == 2
    assert report["top_component_rankings"][0]["stage_1based"] == 2
    assert report["top_component_rankings"][0]["component"] in {"A", "B"}
    assert report["top_interface_rankings"][0]["vapor_source_stage_1based"] == 2
    assert report["summary"]["max_abs_ln_x_over_x_eq"] > 0.0
