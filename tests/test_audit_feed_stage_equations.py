from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_feed_stage_equations.py"
_SPEC = spec_from_file_location("audit_feed_stage_equations", _TOOL_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _row(time_s: float, stage: int, **kwargs):
    row = {
        "time_s": str(time_s),
        "stage": str(stage),
        "node_type": "stage",
        "feed_stage_1based": "3",
        "ML_lbmol": "10",
        "dMLdt_total_lbmolps": "0",
        "dMLdt_transport_lbmolps": "-1",
        "dMLdt_phase_relax_lbmolps": "0",
        "dMLdt_feed_lbmolps": "1",
        "feed_liquid_rate_lbmolps": "1",
        "feed_vapor_rate_lbmolps": "0",
        "feed_total_rate_lbmolps": "1",
        "feed_effective_vapor_fraction": "0",
        "feed_flash_at_stage_conditions": "1",
        "vflow_energy_L_in_lbmolph": "3600",
        "L_out_used_lbmolph": "7200",
        "vflow_energy_feed_ref_term_BTUps": "10",
        "temp_energy_feed_ref_term_BTUps": "10",
        "vflow_energy_P_used_psia": "100",
        "temp_energy_P_used_psia": "100",
        "stage_energy_balance_resid_BTUps": "0",
        "dT_energy_raw_F_per_s": "0",
        "x_A": "0.5",
        "y_A": "0.5",
        "x_eq_A": "0.5",
        "y_eq_A": "0.5",
        "K_state_A": "1",
        "K_thermo_A": "1",
        "tray_V_feed_lbmolps_A": "0",
        "tray_V_transport_in_lbmolps_A": "0",
        "tray_V_transport_out_lbmolps_A": "0",
        "tray_V_equilibrium_transfer_lbmolps_A": "0",
        "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
        "tray_V_final_rhs_lbmolps_A": "0",
    }
    row.update({k: str(v) for k, v in kwargs.items()})
    return row


def test_audit_infers_feed_stage_and_reports_split_jump():
    rows = [
        _row(0, 2, feed_stage_1based="3"),
        _row(0, 3, ML_lbmol=20, dMLdt_total_lbmolps=0, x_A=0.2),
        _row(1, 2, feed_stage_1based="3"),
        _row(
            1,
            3,
            ML_lbmol=1,
            dMLdt_total_lbmolps=-1,
            dMLdt_transport_lbmolps=-1.5,
            dMLdt_feed_lbmolps=0.5,
            feed_liquid_rate_lbmolps=0.5,
            feed_vapor_rate_lbmolps=0.5,
            feed_effective_vapor_fraction=0.5,
            x_A=0.9,
            tray_V_final_rhs_lbmolps_A=2.0,
        ),
    ]
    summary_rows = [
        {"time_s": "0", "steady_state_score": "1"},
        {"time_s": "1", "steady_state_score": "20"},
    ]

    report = _MOD.audit_profile(rows, summary_rows=summary_rows, score_limit=10)

    assert report["feed_stage_1based"] == 3
    assert report["summary"]["max_feed_vapor_fraction_step"] == 0.5
    assert report["summary"]["min_ML_lbmol"] == 1.0
    assert report["summary"]["first_score_above_limit_time_s"] == 1.0
    assert report["top_components_by_liquid_composition_step"][0]["component"] == "A"
    assert report["top_components_by_liquid_composition_step"][0]["max_liquid_composition_step"] == 0.7


def test_audit_reports_liquid_closure_and_energy_basis_mismatch():
    rows = [
        _row(0, 4, feed_stage_1based="4", dMLdt_total_lbmolps=-1.0),
        _row(
            1,
            4,
            feed_stage_1based="4",
            dMLdt_total_lbmolps=-0.9,
            dMLdt_transport_lbmolps=-1.0,
            dMLdt_phase_relax_lbmolps=0.1,
            dMLdt_feed_lbmolps=0.5,
            feed_liquid_rate_lbmolps=0.4,
            temp_energy_feed_ref_term_BTUps=15,
            vflow_energy_feed_ref_term_BTUps=10,
            temp_energy_P_used_psia=105,
            vflow_energy_P_used_psia=100,
        ),
    ]

    report = _MOD.audit_profile(rows)
    summary = report["summary"]

    assert summary["max_abs_liquid_total_closure_resid_lbmolps"] == 0.0
    assert summary["max_abs_feed_liquid_resid_lbmolps"] == pytest.approx(0.1)
    assert summary["max_abs_feed_energy_term_delta_BTUps"] == 5.0
    assert summary["max_abs_pressure_basis_delta_psia"] == 5.0
