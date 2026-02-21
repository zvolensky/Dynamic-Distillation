"""
test_excel_case_loader_v1.py

Dynamic Distillation - Excel Loader Tests

PURPOSE
-------
Verify that `excel_case_loader_v1` reads template inputs into expected case
structures and preserves recognized spec keys used downstream.

SCOPE
-----
- component canonicalization and base shape checks
- presence/parse behavior for optional thermo/geometry/drum keys

KEY DEPENDENCIES
----------------
- excel_case_loader_v1
"""


from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


def test_load_case_from_excel_smoke():
    c = load_case_from_excel("distillation_column_template.xlsx")
    assert len(c.components) == 3
    assert c.component_ids_dwsim == ["Propane", "N-butane", "N-pentane"]
    assert "Number of Stages" in c.specs
    # Thermo refresh threshold is optional but should be parsed when present.
    assert "Thermo Refresh dT (F)" in c.specs
    # Reboiler-neighbor vapor guard ratios are optional but should be parsed when present.
    assert "Reboiler Neighbor Vapor Hi Ratio" in c.specs
    assert "Reboiler Neighbor Vapor Lo Ratio" in c.specs
    # Stage-level thermo refresh thresholds are optional but should be parsed when present.
    assert "Thermo Refresh dP (psia)" in c.specs
    assert "Thermo Refresh dX" in c.specs
    assert "Condenser Pressure Drop (psi)" in c.specs
    # Reflux-drum geometry/vapor-volume fields should always exist in specs map.
    assert "Top Drum Vapor Volume (ft3)" in c.specs
    assert "Top Drum Total Volume (ft3)" in c.specs
    assert "Top Drum Diameter (ft)" in c.specs
    assert "Top Drum Length (ft)" in c.specs
    assert "Top Drum Liquid Fraction (-)" in c.specs
    if c.specs["Thermo Refresh dT (F)"] is not None:
        assert float(c.specs["Thermo Refresh dT (F)"]) > 0.0
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
