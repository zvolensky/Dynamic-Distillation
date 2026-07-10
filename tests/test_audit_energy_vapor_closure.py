from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_energy_vapor_closure.py"
_SPEC = spec_from_file_location("audit_energy_vapor_closure", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

audit_profile = _MODULE.audit_profile
interface_records = _MODULE.interface_records


def _row(**updates):
    base = {
        "time_s": "40",
        "stage": "2",
        "node_type": "stage",
        "T_F": "160",
        "P_psia_hyd": "110",
        "vflow_energy_P_used_psia": "108",
        "vflow_energy_pressure_basis_code": "1",
        "P_from_vapor_holdup_psia": "112",
        "HV_BTU_lbmol_tray": "-3800",
        "V_out_lbmolph": "101",
        "vflow_energy_calc_lbmolph": "120",
        "vflow_energy_used_lbmolph": "100",
        "vflow_energy_clamped": "0",
        "vflow_energy_limit_hi_lbmolph": "200",
        "vflow_energy_limit_lo_lbmolph": "50",
        "vflow_energy_hV_in_BTU_per_lbmol": "-3900",
        "vflow_energy_hV_out_BTU_per_lbmol": "-3800",
        "vflow_energy_hL_in_source_code": "2",
        "vflow_energy_hL_out_source_code": "2",
        "vflow_energy_hV_in_source_code": "2",
        "vflow_energy_hV_out_source_code": "2",
        "vflow_energy_hV_in_minus_hL_out_BTU_per_lbmol": "500",
        "dT_energy_raw_F_per_s": "0.7",
        "stage_energy_balance_resid_BTUps": "70",
        "vflow_energy_heat_capacity_BTU_per_F": "100",
        "vflow_energy_L_in_term_BTUps": "10",
        "vflow_energy_V_in_term_BTUps": "40",
        "vflow_energy_feed_ref_term_BTUps": "0",
        "vflow_energy_duty_term_BTUps": "0",
        "vflow_energy_dE_target_BTUps": "5",
        "vflow_energy_dT_target_F_per_s": "0.05",
        "vflow_energy_resid_after_used_BTUps": "10",
        "vflow_energy_predicted_dT_from_used_F_per_s": "0.6",
        "vflow_energy_numer_BTUps": "45",
        "vflow_energy_L_in_lbmolph": "80",
        "vflow_energy_V_in_lbmolph": "90",
        "vflow_energy_hL_in_BTU_per_lbmol": "-4500",
        "vflow_energy_hL_out_BTU_per_lbmol": "-4400",
        "temp_energy_dE_BTUps": "25",
        "temp_energy_L_in_term_BTUps": "11",
        "temp_energy_V_in_term_BTUps": "41",
        "temp_energy_feed_ref_term_BTUps": "1",
        "temp_energy_duty_term_BTUps": "2",
        "temp_energy_V_out_term_BTUps": "29",
        "temp_energy_L_in_lbmolph": "81",
        "temp_energy_V_in_lbmolph": "91",
        "temp_energy_V_out_lbmolph": "101",
        "temp_energy_hL_in_BTU_per_lbmol": "-4501",
        "temp_energy_hL_out_BTU_per_lbmol": "-4401",
        "temp_energy_hV_in_BTU_per_lbmol": "-3901",
        "temp_energy_hV_out_BTU_per_lbmol": "-3801",
        "x_A": "0.5",
        "y_A": "0.7",
        "y_eq_A": "0.6",
        "y_target_A": "0.65",
        "K_state_A": "1.4",
        "K_thermo_A": "1.2",
        "K_eq_relax_A": "1.0",
    }
    base.update(updates)
    return base


def test_interface_records_report_generic_adjacent_vapor_stream_context():
    rows = [
        _row(stage="1", T_F="150", P_psia_hyd="100", HV_BTU_lbmol_tray="-4000"),
        _row(stage="2", T_F="160", P_psia_hyd="110", HV_BTU_lbmol_tray="-3800"),
    ]

    records = interface_records(rows)
    rec = [r for r in records if r["vapor_source_stage_1based"] == 2][0]

    assert rec["vapor_receiver_stage_1based"] == 1
    assert rec["V_calc_minus_used_lbmolph"] == pytest.approx(20.0)
    assert rec["relative_V_calc_minus_used"] == pytest.approx(0.2)
    assert rec["vflow_energy_P_used_minus_source_P_psia"] == pytest.approx(-2.0)
    assert rec["vflow_energy_pressure_basis_code"] == pytest.approx(1.0)
    assert rec["source_minus_receiver_P_psia"] == pytest.approx(10.0)
    assert rec["source_minus_receiver_HV_BTU_per_lbmol"] == pytest.approx(200.0)


def test_audit_profile_ranks_flow_energy_and_k_mismatch():
    rows = [
        _row(
            stage="1",
            dT_energy_raw_F_per_s="0.1",
            vflow_energy_predicted_dT_from_used_F_per_s="0.1",
            temp_energy_dE_BTUps="10",
            HV_BTU_lbmol_tray="-4000",
        ),
        _row(stage="2"),
    ]

    report = audit_profile(rows, time_s=40, top_n=2)

    assert report["n_stage_rows"] == 2
    assert report["interface_vapor_flow_consistency"]["max_abs_V_calc_minus_used_lbmolph"] == pytest.approx(20.0)
    assert report["interface_vapor_flow_consistency"]["max_abs_vflow_energy_P_used_minus_source_P_psia"] == pytest.approx(2.0)
    assert report["energy_term_breakdown"]["max_abs_dT_energy_raw_F_per_s"] == pytest.approx(0.7)
    assert report["energy_term_breakdown"]["max_abs_dT_raw_minus_vflow_predicted_F_per_s"] == pytest.approx(0.1)
    assert report["energy_term_breakdown"]["max_abs_temp_energy_dE_minus_vflow_resid_BTUps"] == pytest.approx(15.0)
    assert report["energy_term_breakdown"]["worst_temperature_vflow_residual_gap"]["stage_1based"] == 2
    assert report["energy_term_breakdown"]["worst_temperature_rate"]["dominant_energy_term"] == (
        "stage_energy_balance_resid_BTUps"
    )
    assert report["energy_term_breakdown"]["worst_temperature_equation_gap"]["stage_1based"] == 2
    assert report["vapor_equilibrium_consistency"]["max_abs_y_state_minus_y_eq"] == pytest.approx(0.1)
    assert report["vapor_equilibrium_consistency"]["max_abs_y_state_minus_y_target"] == pytest.approx(0.05)
    assert report["vapor_equilibrium_consistency"]["max_abs_y_state_minus_y_target_interior"] == pytest.approx(0.05)
    assert report["vapor_equilibrium_consistency"]["top_y_target_mismatch"][0]["component"] == "A"
    assert report["vapor_equilibrium_consistency"]["max_abs_ln_K_state_over_K_eq_relax"] == pytest.approx(
        __import__("math").log(1.4)
    )
    assert "temperature-rate spike" in report["diagnostic_interpretation"]["dominant_families"]


def test_audit_profile_selects_nearest_time_and_stage_rows_only():
    rows = [
        _row(time_s="0", stage="0", node_type="top"),
        _row(time_s="0", stage="1", dT_energy_raw_F_per_s="0.2"),
        _row(time_s="20", stage="1", dT_energy_raw_F_per_s="0.9"),
    ]

    report = audit_profile(rows, time_s=19)

    assert report["time_s"] == pytest.approx(20.0)
    assert report["n_stage_rows"] == 1
    assert report["energy_term_breakdown"]["max_abs_dT_energy_raw_F_per_s"] == pytest.approx(0.9)
