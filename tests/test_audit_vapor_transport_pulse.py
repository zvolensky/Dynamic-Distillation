import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_vapor_transport_pulse.py"
_SPEC = spec_from_file_location("audit_vapor_transport_pulse", _TOOL_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
audit_profile = _MODULE.audit_profile


def test_audit_vapor_transport_pulse_identifies_composition_gradient(tmp_path):
    path = tmp_path / "profile.csv"
    fieldnames = [
        "time_s",
        "node_type",
        "stage",
        "MV_lbmol",
        "V_out_lbmolph",
        "vflow_energy_V_in_lbmolph",
        "y_A",
        "y_B",
        "tray_V_transport_in_lbmolps_A",
        "tray_V_transport_out_lbmolps_A",
        "tray_V_pre_equilibrium_rhs_lbmolps_A",
        "tray_V_equilibrium_transfer_lbmolps_A",
        "tray_V_final_rhs_lbmolps_A",
        "tray_V_transport_in_lbmolps_B",
        "tray_V_transport_out_lbmolps_B",
        "tray_V_pre_equilibrium_rhs_lbmolps_B",
        "tray_V_equilibrium_transfer_lbmolps_B",
        "tray_V_final_rhs_lbmolps_B",
        "eq_component_transfer_guard_scale_tray",
        "eq_component_transfer_guard_limit_lbmolps_tray",
    ]
    rows = [
        {
            "time_s": "10",
            "node_type": "stage",
            "stage": "1",
            "MV_lbmol": "10",
            "V_out_lbmolph": "3600",
            "vflow_energy_V_in_lbmolph": "3600",
            "y_A": "0.1",
            "y_B": "0.9",
            "tray_V_transport_in_lbmolps_A": "0.8",
            "tray_V_transport_out_lbmolps_A": "-0.1",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0.7",
            "tray_V_equilibrium_transfer_lbmolps_A": "-0.2",
            "tray_V_final_rhs_lbmolps_A": "0.5",
            "tray_V_transport_in_lbmolps_B": "0.2",
            "tray_V_transport_out_lbmolps_B": "-0.9",
            "tray_V_pre_equilibrium_rhs_lbmolps_B": "-0.7",
            "tray_V_equilibrium_transfer_lbmolps_B": "0.2",
            "tray_V_final_rhs_lbmolps_B": "-0.5",
            "eq_component_transfer_guard_scale_tray": "1",
            "eq_component_transfer_guard_limit_lbmolps_tray": "1",
        },
        {
            "time_s": "10",
            "node_type": "stage",
            "stage": "2",
            "MV_lbmol": "10",
            "V_out_lbmolph": "3600",
            "vflow_energy_V_in_lbmolph": "3600",
            "y_A": "0.8",
            "y_B": "0.2",
            "tray_V_transport_in_lbmolps_A": "0.8",
            "tray_V_transport_out_lbmolps_A": "-0.8",
            "tray_V_pre_equilibrium_rhs_lbmolps_A": "0",
            "tray_V_equilibrium_transfer_lbmolps_A": "0",
            "tray_V_final_rhs_lbmolps_A": "0",
            "tray_V_transport_in_lbmolps_B": "0.2",
            "tray_V_transport_out_lbmolps_B": "-0.2",
            "tray_V_pre_equilibrium_rhs_lbmolps_B": "0",
            "tray_V_equilibrium_transfer_lbmolps_B": "0",
            "tray_V_final_rhs_lbmolps_B": "0",
            "eq_component_transfer_guard_scale_tray": "1",
            "eq_component_transfer_guard_limit_lbmolps_tray": "1",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report = audit_profile(path, time_s=10.0, top_n=2)

    top = report["top_component_transport_pulses"][0]
    assert top["stage_1based"] == 1
    assert top["component"] == "A"
    assert top["transport_driver"] == "composition_gradient"
    assert top["transport_gradient_term_est_lbmolps"] == pytest.approx(0.7)
    assert top["relative_rhs_per_s"] == pytest.approx(0.5 / 2.0)
