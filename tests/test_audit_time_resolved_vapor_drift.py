import csv
import math
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_time_resolved_vapor_drift.py"
_SPEC = spec_from_file_location("audit_time_resolved_vapor_drift", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

audit_profile = _MODULE.audit_profile


def test_audit_profile_merges_boundary_diagnostics_and_computes_stage_metrics(tmp_path):
    profile = tmp_path / "profile.csv"
    fields = [
        "time_s",
        "node_type",
        "stage",
        "MV_lbmol",
        "V_condensed_in_lbmolph",
        "P_top_drum_psia",
        "V_to_top_drum_lbmolph",
        "V_to_top_drum_pressure_gate_scale",
        "stage_energy_balance_resid_BTUps",
        "tray_effective_heat_capacity_BTU_per_F",
        "dT_energy_raw_F_per_s",
        "y_n_Butane",
        "y_target_n_Butane",
        "K_state_over_K_thermo_n_Butane",
        "tray_V_final_rhs_lbmolps_n_Butane",
        "tray_V_pre_equilibrium_rhs_lbmolps_n_Butane",
        "tray_V_transport_in_lbmolps_n_Butane",
        "tray_V_transport_out_lbmolps_n_Butane",
        "tray_V_feed_lbmolps_n_Butane",
        "tray_V_terminal_adjust_lbmolps_n_Butane",
        "tray_V_holdup_relax_lbmolps_n_Butane",
        "tray_V_equilibrium_transfer_lbmolps_n_Butane",
    ]
    rows = [
        {
            "time_s": "10",
            "node_type": "distillate_drum",
            "V_condensed_in_lbmolph": "1234",
            "P_top_drum_psia": "222.5",
            "V_to_top_drum_lbmolph": "0",
        },
        {
            "time_s": "10",
            "node_type": "stage",
            "stage": "12",
            "MV_lbmol": "50",
            "stage_energy_balance_resid_BTUps": "12",
            "tray_effective_heat_capacity_BTU_per_F": "3",
            "dT_energy_raw_F_per_s": "0.25",
            "y_n_Butane": "0.2",
            "y_target_n_Butane": "0.15",
            "K_state_over_K_thermo_n_Butane": str(math.e),
            "tray_V_final_rhs_lbmolps_n_Butane": "0.33",
            "tray_V_pre_equilibrium_rhs_lbmolps_n_Butane": "0.5",
            "tray_V_transport_in_lbmolps_n_Butane": "0.1",
            "tray_V_transport_out_lbmolps_n_Butane": "-0.2",
            "tray_V_equilibrium_transfer_lbmolps_n_Butane": "-0.4",
        },
        {
            "time_s": "20",
            "node_type": "stage",
            "stage": "19",
            "MV_lbmol": "50",
            "y_n_Butane": "0.2",
            "y_target_n_Butane": "0.2",
            "K_state_over_K_thermo_n_Butane": "1",
            "tray_V_final_rhs_lbmolps_n_Butane": "9.0",
        },
    ]
    with profile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(profile, stages=[12], times=[10], top_n=1)

    assert report["stages"] == [12]
    assert report["times"] == [10.0]
    assert len(report["summary_by_time"]) == 1
    assert report["summary_by_time"][0]["worst_stage_1based"] == 12
    assert report["summary_by_time"][0]["V_condensed_in_lbmolph"] == pytest.approx(1234.0)
    assert report["summary_by_stage_time"][0]["max_abs_energy_resid_over_heat_capacity_F_per_s"] == pytest.approx(4.0)
    assert report["summary_by_stage_time"][0]["max_abs_ln_K_state_over_K_thermo"] == pytest.approx(1.0)

    record = report["top_component_records"][0]
    assert record["stage_1based"] == 12
    assert record["component"] == "n_Butane"
    assert record["abs_y_minus_target"] == pytest.approx(0.05)
    assert record["relative_rhs_per_s"] == pytest.approx(0.33 / 11.0)
    assert record["dominant_term"] == "equilibrium_transfer"
    assert record["V_condensed_in_lbmolph"] == pytest.approx(1234.0)
