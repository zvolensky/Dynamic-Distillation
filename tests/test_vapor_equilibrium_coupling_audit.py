from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "vapor_equilibrium_coupling_audit.py"
_SPEC = spec_from_file_location("vapor_equilibrium_coupling_audit", _TOOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

audit_profile = _MODULE.audit_profile


def _row(**updates):
    base = {
        "time_s": "10",
        "stage": "1",
        "node_type": "stage",
        "x_A": "0.5",
        "x_B": "0.5",
        "y_A": "0.8",
        "y_B": "0.2",
        "K_state_A": "1.6",
        "K_state_B": "0.4",
        "K_thermo_A": "1.2",
        "K_thermo_B": "0.8",
        "stage_energy_balance_resid_BTUps": "20",
        "dT_energy_raw_F_per_s": "0.2",
        "tray_effective_heat_capacity_BTU_per_F": "100",
        "P_psia_hyd": "100",
        "P_from_vapor_holdup_psia": "105",
        "MV_lbmol": "2",
        "tray_vapor_volume_ft3": "100",
        "Z_tray": "0.9",
        "vflow_energy_calc_lbmolph": "120",
        "vflow_energy_used_lbmolph": "100",
        "hydraulic_dp_used_psia": "2",
        "hydraulic_dp_raw_psia": "2.1",
    }
    base.update(updates)
    return base


def test_audit_profile_reports_k_mismatch_and_vapor_closure():
    report = audit_profile([_row()], time_s=10)

    assert report["n_stage_rows"] == 1
    assert report["k_state_vs_thermo"]["max_abs_ln_K_ratio"] == pytest.approx(abs(__import__("math").log(0.5)))
    assert report["vapor_composition_closure"]["max_abs_sum_y_error"] == pytest.approx(0.0)
    assert report["vapor_composition_closure"]["max_abs_y_minus_normalized_Kx"] == pytest.approx(0.2)


def test_audit_profile_reports_bubble_dew_energy_and_flow_sensitivity():
    report = audit_profile([_row(vflow_relax_alpha="0.25")], time_s=10)

    assert report["bubble_dew_consistency"]["max_abs_bubble_residual"] == pytest.approx(0.0)
    assert report["bubble_dew_consistency"]["max_abs_dew_residual"] == pytest.approx(abs((0.8 / 1.2 + 0.2 / 0.8) - 1.0))
    assert report["energy_consistency"]["max_abs_energy_residual_BTUps"] == pytest.approx(20.0)
    assert report["energy_consistency"]["max_abs_dT_energy_raw_F_per_s"] == pytest.approx(0.2)
    assert report["vapor_flow_sensitivity"]["max_abs_V_calc_minus_used_lbmolph"] == pytest.approx(20.0)
    assert report["vapor_flow_sensitivity"]["max_abs_estimated_dVdP_lbmolph_per_psia"] == pytest.approx(60.0)
    worst = report["vapor_flow_sensitivity"]["worst_V_calc_minus_used"]
    assert worst["implied_V_prev_lbmolph"] == pytest.approx((100.0 - 0.25 * 120.0) / 0.75)
    assert worst["V_calc_minus_implied_prev_lbmolph"] == pytest.approx(120.0 - ((100.0 - 0.25 * 120.0) / 0.75))


def test_audit_profile_selects_nearest_time_and_stage_rows_only():
    rows = [
        _row(time_s="0", stage="0", node_type="distillate_drum"),
        _row(time_s="0", stage="1", dT_energy_raw_F_per_s="0.1"),
        _row(time_s="20", stage="1", dT_energy_raw_F_per_s="0.8"),
    ]

    report = audit_profile(rows, time_s=19)

    assert report["time_s"] == pytest.approx(20.0)
    assert report["n_stage_rows"] == 1
    assert report["energy_consistency"]["max_abs_dT_energy_raw_F_per_s"] == pytest.approx(0.8)


def test_pressure_holdup_consistency_reports_state_vs_implied_pressure():
    report = audit_profile([_row()], time_s=10)

    assert report["pressure_holdup_consistency"]["available"] is True
    assert report["pressure_holdup_consistency"]["max_abs_P_error_psia"] == pytest.approx(5.0)
    assert report["pressure_holdup_consistency"]["max_abs_relative_P_error"] == pytest.approx(0.05)


def test_pressure_holdup_consistency_skips_dry_rows():
    row = _row(MV_lbmol="0", P_psia_hyd="100", P_from_vapor_holdup_psia="0")

    report = audit_profile([row], time_s=10)

    assert report["pressure_holdup_consistency"]["available"] is False
    assert "meaningful vapor holdup" in report["pressure_holdup_consistency"]["reason"]


def test_pressure_holdup_consistency_is_unavailable_without_profile_columns():
    row = _row()
    for key in ["P_from_vapor_holdup_psia", "tray_vapor_volume_ft3", "Z_tray"]:
        row.pop(key, None)

    report = audit_profile([row], time_s=10)

    assert report["pressure_holdup_consistency"]["available"] is False
    assert "profile CSV" in report["pressure_holdup_consistency"]["reason"]
