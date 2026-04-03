"""
test_excel_case_validator_v1.py

Dynamic Distillation - Preflight Validator Tests

PURPOSE
-------
Validate warning/error classification behavior of
`excel_case_validator_v1.validate_loaded_case` for nominal and perturbed
case inputs.

SCOPE
-----
- nominal pass behavior
- stream and spec perturbation warning/error checks

KEY DEPENDENCIES
----------------
- excel_case_loader_v1 / column_spec_builder_v1 / excel_case_validator_v1
"""


from dataclasses import replace
from pathlib import Path

import pandas as pd

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.excel_case_validator_v1 import validate_loaded_case


def test_validate_loaded_case_smoke():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    col = build_column_spec_from_case(case)
    report = validate_loaded_case(case, col)

    assert report.ok
    assert len(report.errors) == 0


def test_validate_loaded_case_warns_for_bad_stream_stage_and_total():
    excel = Path("distillation_column_template.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    bad_streams = dict(case.streams)
    bad_streams["BadFeed"] = {
        "Stage": 999,
        "Total Molar Flow (lbmol/h)": 100.0,
        "Component Mole Flows (lbmol/h)": {
            "n-Propane": 50.0,
        },
    }
    case_bad = replace(case, streams=bad_streams)
    col_bad = build_column_spec_from_case(case_bad)

    report = validate_loaded_case(case_bad, col_bad)
    assert report.ok
    assert any("outside valid range" in w for w in report.warnings)
    assert any("component-flow sum" in w for w in report.warnings)


def test_validate_loaded_case_errors_when_liquid_holdup_column_missing():
    excel = Path("water_methanol_template_10stage_chemsep_seed_20260401.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    ic_bad = pd.DataFrame(case.initial_conditions).drop(columns=["Liquid Holdup (lbmol)"], errors="ignore")
    case_bad = replace(case, initial_conditions=ic_bad)
    col_bad = build_column_spec_from_case(case_bad)

    report = validate_loaded_case(case_bad, col_bad)
    assert not report.ok
    assert any("Liquid Holdup (lbmol)" in e for e in report.errors)


def test_validate_loaded_case_warns_when_geometry_missing():
    excel = Path("water_methanol_template_10stage_chemsep_seed_20260401.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    specs_bad = dict(case.specs)
    specs_bad["Geometry Sections"] = []
    case_bad = replace(case, specs=specs_bad)
    col_bad = build_column_spec_from_case(case_bad)

    report = validate_loaded_case(case_bad, col_bad)
    assert any("No Geometry Sections were loaded" in w for w in report.warnings)


def test_validate_loaded_case_warns_when_boundary_holdup_specs_missing():
    excel = Path("water_methanol_template_10stage_chemsep_seed_20260401.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    specs_bad = dict(case.specs)
    specs_bad.pop("Top Accumulator Holdup (lbmol)", None)
    specs_bad.pop("Bottom Holdup (lbmol)", None)
    case_bad = replace(case, specs=specs_bad)
    col_bad = build_column_spec_from_case(case_bad)

    report = validate_loaded_case(case_bad, col_bad)
    assert any("Top Accumulator Holdup (lbmol)" in w for w in report.warnings)
    assert any("Bottom Holdup (lbmol)" in w for w in report.warnings)


def test_validate_loaded_case_warns_when_total_condenser_vapor_adders_missing():
    excel = Path("water_methanol_template_10stage_chemsep_seed_20260401.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    specs_bad = dict(case.specs)
    specs_bad.pop("Overhead Vapor Line Volume (ft3)", None)
    specs_bad.pop("Condenser Vapor Volume (ft3)", None)
    case_bad = replace(case, specs=specs_bad)
    col_bad = build_column_spec_from_case(case_bad)

    report = validate_loaded_case(case_bad, col_bad)
    assert any("top-end vapor-space adders" in w for w in report.warnings)


def test_validate_loaded_case_warns_when_hydraulic_workbook_tuning_specs_missing():
    excel = Path("water_methanol_template_10stage_chemsep_seed_20260401.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    specs_bad = dict(case.specs)
    specs_bad["Pressure Model"] = "hydraulic"
    specs_bad["Vapor Flow Model"] = "energy"
    specs_bad.pop("Stage time constant [tau] (sec)", None)
    specs_bad.pop("Condenser Pressure Drop (psi)", None)
    specs_bad.pop("Equilibrium Relaxation Mode", None)
    specs_bad.pop("Equilibrium Tau (sec)", None)
    specs_bad.pop("Equilibrium Energy Damping Gain", None)
    specs_bad.pop("Equilibrium Relaxation Live PR", None)
    case_bad = replace(case, specs=specs_bad)
    col_bad = build_column_spec_from_case(case_bad)

    report = validate_loaded_case(case_bad, col_bad)
    assert any("Hydraulic workbook is missing Stage time constant [tau] (sec)" in w for w in report.warnings)
    assert any("Hydraulic workbook is missing Condenser Pressure Drop (psi)" in w for w in report.warnings)
    assert any("Hydraulic workbook is missing Equilibrium Relaxation Mode" in w for w in report.warnings)
    assert any("Hydraulic workbook is missing Equilibrium Tau (sec)" in w for w in report.warnings)
    assert any("Hydraulic workbook is missing Equilibrium Energy Damping Gain" in w for w in report.warnings)
    assert any("Hydraulic workbook is missing Equilibrium Relaxation Live PR" in w for w in report.warnings)


def test_validate_loaded_case_does_not_warn_about_hydraulic_tuning_for_parity_workbook():
    excel = Path("water_methanol_template_10stage_chemsep_seed_20260401.xlsx")
    if not excel.exists():
        return

    case = load_case_from_excel(str(excel))
    specs_bad = dict(case.specs)
    specs_bad["Pressure Model"] = "spec"
    specs_bad["Vapor Flow Model"] = "profile"
    specs_bad.pop("Stage time constant [tau] (sec)", None)
    specs_bad.pop("Condenser Pressure Drop (psi)", None)
    specs_bad.pop("Equilibrium Relaxation Mode", None)
    specs_bad.pop("Equilibrium Tau (sec)", None)
    specs_bad.pop("Equilibrium Energy Damping Gain", None)
    specs_bad.pop("Equilibrium Relaxation Live PR", None)
    case_bad = replace(case, specs=specs_bad)
    col_bad = build_column_spec_from_case(case_bad)

    report = validate_loaded_case(case_bad, col_bad)
    assert not any("Hydraulic workbook is missing" in w for w in report.warnings)
