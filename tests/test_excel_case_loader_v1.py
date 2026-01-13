# test_excel_case_loader_v1.py
# Last updated: 2026-01-11 15:xx ET

from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


def test_load_case_from_excel_smoke():
    c = load_case_from_excel("distillation_column_template.xlsx")
    assert len(c.components) == 3
    assert c.component_ids_dwsim == ["Propane", "N-butane", "N-pentane"]
    assert "Number of Stages" in c.specs
    # Geometry table is optional. If present, loader should parse and normalize void fraction.
    assert "Geometry Sections" in c.specs
    secs = c.specs["Geometry Sections"]
    if secs is not None:
        assert isinstance(secs, list)
        assert len(secs) >= 1
        # The (newer) template uses 0.75 (fraction) and also 75 (percent); loader normalizes both.
        if len(secs) >= 2:
            assert abs(float(secs[0]["gas_void_frac"]) - 0.75) < 1e-12
            assert abs(float(secs[1]["gas_void_frac"]) - 0.75) < 1e-12
    assert c.initial_conditions is not None