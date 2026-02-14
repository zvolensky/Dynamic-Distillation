from dataclasses import replace
from pathlib import Path

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
