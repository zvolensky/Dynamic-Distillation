# test_excel_case_loader_v1.py
# Last updated: 2026-01-11 15:xx ET

from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


def test_load_case_from_excel_smoke():
    c = load_case_from_excel("distillation_column_template.xlsx")
    assert len(c.components) == 3
    assert c.component_ids_dwsim == ["Propane", "N-butane", "N-pentane"]
    assert "Number of Stages" in c.specs
    assert c.initial_conditions is not None
