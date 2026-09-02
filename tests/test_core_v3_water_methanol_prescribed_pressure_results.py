from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / "logs" / name).read_text(encoding="utf-8"))


def test_bulk_thermo_qualification_keeps_only_compatible_ranked_providers():
    report = _load("core_v3_water_methanol_bulk_thermo_qualification_20260901.json")

    assert report["pass_gate"]
    assert report["selected_for_prescribed_pressure_gate"] == "dwsim_unifac"
    assert report["ranking"] == [
        "dwsim_unifac",
        "dwsim_modfac",
        "dwsim_nrtl",
        "clapeyron_vtpr",
    ]
    candidates = {item["identity"]: item for item in report["candidates"]}
    assert not candidates["clapeyron_unifac"]["core_bulk_interface_compatible"]
    assert not candidates["clapeyron_nrtl"]["core_bulk_interface_compatible"]
    assert candidates["clapeyron_vtpr"]["maximum_interior_abs_log_fugacity_residual"] > 1.0


def test_prescribed_pressure_root_closes_but_does_not_match_chemsep_products():
    report = _load("core_v3_water_methanol_prescribed_pressure_root_20260901.json")
    workbook = Path(report["workbook"])

    assert report["pass_gate"]
    assert report["classification"] == "stationary_root_accepted"
    assert report["mode"] == "prescribed_pressure_stationary_parity"
    assert report["stationary_equation_score"] < 1.0e-8
    assert report["jacobian"]["rank"] == report["jacobian"]["dimension"] == 100
    assert report["jacobian"]["condition"] < 1.0e8
    assert np.allclose(
        [row["pressure_psia"] for row in report["tray_profiles"]],
        np.linspace(14.7, 17.7, 10),
        rtol=0.0,
        atol=1.0e-8,
    )
    assert abs(report["chemsep_comparison"]["distillate_flow_difference_lbmolph"]) > 1000.0
    assert abs(report["chemsep_comparison"]["bottoms_flow_difference_lbmolph"]) > 1000.0
    assert report["raw_maxima"]["free_pressure_equation_mismatch_psia"] > 0.5
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == report["workbook_sha256"]


def test_specification_aware_root_matches_flow_specs_and_solves_both_duties():
    report = _load("core_v3_water_methanol_specification_aware_root_20260901.json")
    workbook = Path(report["workbook"])

    assert report["pass_gate"]
    assert report["classification"] == "stationary_root_accepted"
    assert report["mode"] == "prescribed_pressure_fixed_bottoms_solved_reboiler_duty"
    assert report["stationary_equation_score"] < 1.0e-8
    assert report["jacobian"]["rank"] == report["jacobian"]["dimension"] == 100
    assert report["jacobian"]["condition"] < 1.0e8
    assert np.isclose(
        report["specification_ownership"]["reflux_ratio"],
        2.0,
        rtol=0.0,
        atol=3.0e-6,
    )
    assert abs(report["chemsep_comparison"]["distillate_flow_difference_lbmolph"]) < 1.0e-8
    assert abs(report["chemsep_comparison"]["bottoms_flow_difference_lbmolph"]) < 1.0e-8
    assert report["specification_ownership"]["variable_names"][-1] == "Q_R"
    assert abs(report["chemsep_comparison"]["top_liquid_mole_fraction_difference"][0]) > 0.01
    assert abs(report["chemsep_comparison"]["reboiler_duty_difference_BTUph"]) > 1.0e7
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == report["workbook_sha256"]


def test_chemsep_reconciled_root_matches_boundary_thermo_and_products():
    report = _load("core_v3_water_methanol_chemsep_reconciled_root_20260901.json")
    workbook = Path(report["workbook"])

    assert report["pass_gate"]
    assert report["classification"] == "stationary_root_accepted"
    assert report["pressure_mode"] == "chemsep_constant"
    assert report["reboiler_type"] == "total"
    assert report["stationary_equation_score"] < 1.0e-8
    assert report["jacobian"]["rank"] == report["jacobian"]["dimension"] == 100
    assert report["jacobian"]["condition"] < 1.0e8
    assert np.allclose(
        [row["pressure_psia"] for row in report["tray_profiles"]],
        14.6959,
        rtol=0.0,
        atol=1.0e-10,
    )
    assert report["fugacity_calibration"]["maximum_abs_log_residual_after"] < 3.0e-4
    assert report["enthalpy_calibration"]["maximum_abs_liquid_fit_error_BTU_lbmol"] < 5.0
    assert report["enthalpy_calibration"]["maximum_abs_vapor_fit_error_BTU_lbmol"] < 1.0
    assert abs(report["chemsep_comparison"]["distillate_flow_difference_lbmolph"]) < 1.0e-8
    assert abs(report["chemsep_comparison"]["bottoms_flow_difference_lbmolph"]) < 1.0e-8
    assert abs(report["chemsep_comparison"]["top_liquid_mole_fraction_difference"][0]) < 1.0e-5
    assert abs(report["chemsep_comparison"]["bottom_liquid_mole_fraction_difference"][0]) < 1.0e-5
    assert abs(report["chemsep_comparison"]["top_temperature_difference_F"]) < 0.01
    assert abs(report["chemsep_comparison"]["bottom_temperature_difference_F"]) < 0.01
    assert abs(report["chemsep_comparison"]["condenser_duty_difference_BTUph"]) < 1.0e5
    assert abs(report["chemsep_comparison"]["reboiler_duty_difference_BTUph"]) < 1.0e5
    assert np.allclose(
        report["tray_profiles"][-1]["liquid_mole_fraction"],
        report["tray_profiles"][-1]["vapor_mole_fraction"],
        rtol=0.0,
        atol=1.0e-12,
    )
    assert np.isclose(
        report["tray_profiles"][-1]["temperature_F"],
        report["tray_profiles"][-2]["temperature_F"],
        rtol=0.0,
        atol=1.0e-12,
    )
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == report["workbook_sha256"]


def test_design_calibrated_hydraulic_root_solves_nonzero_tray_pressure_drop():
    report = _load(
        "core_v3_water_methanol_design_calibrated_hydraulic_root_20260901.json"
    )
    workbook = Path(report["workbook"])
    pressures = np.asarray(
        [row["pressure_psia"] for row in report["tray_profiles"]], dtype=float
    )
    hydraulics = report["pressure_hydraulics"]
    calibration = hydraulics["coefficient_calibration"]

    assert report["pass_gate"]
    assert report["classification"] == "stationary_root_accepted"
    assert report["mode"] == "hydraulic_pressure_fixed_bottoms_solved_reboiler_duty"
    assert report["pressure_mode"] == "hydraulic_free"
    assert report["specification_ownership"]["pressure_target_psia"] is None
    assert report["stationary_equation_score"] < 1.0e-8
    assert report["jacobian"]["rank"] == report["jacobian"]["dimension"] == 100
    assert report["jacobian"]["condition"] < 1.0e8
    assert calibration["enabled"]
    assert calibration["original_dry_tray_coefficient"] == 40.0
    assert 13.0 < calibration["inferred_dry_tray_coefficient"] < 14.0
    assert np.isclose(pressures[0], 14.7, rtol=0.0, atol=1.0e-10)
    assert np.all(np.diff(pressures) > 0.0)
    assert np.isclose(pressures[-1], 17.671024176461057, rtol=0.0, atol=1.0e-8)
    assert np.isclose(
        hydraulics["final_total_pressure_drop_psia"],
        pressures[-1] - pressures[0],
        rtol=0.0,
        atol=1.0e-10,
    )
    assert np.isclose(
        sum(hydraulics["final_liquid_head_drop_psia"])
        + sum(hydraulics["final_dry_tray_drop_psia"]),
        hydraulics["final_total_pressure_drop_psia"],
        rtol=0.0,
        atol=1.0e-10,
    )
    assert report["raw_maxima"]["free_pressure_equation_mismatch_psia"] < 1.0e-10
    assert np.allclose(
        report["tray_profiles"][-1]["liquid_mole_fraction"],
        report["tray_profiles"][-1]["vapor_mole_fraction"],
        rtol=0.0,
        atol=1.0e-12,
    )
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == report["workbook_sha256"]
