from tools import audit_core_v3_vapor_holdup_terminal_control_contract as dd263


def test_dd263_uses_actual_c3c4_workbook_geometry_and_passes():
    report = dd263.build_report()

    geometry = report["geometry"]
    audit = report["actual_c3c4_audit"]
    assert geometry["drum_diameter_ft"] == 12.1
    assert geometry["drum_tangent_length_ft"] == 36.3
    assert geometry["sump_diameter_ft"] == 18.1759
    assert geometry["sump_height_ft"] == 12.0
    assert audit["solve_variable_count"] == 262
    assert audit["structural_rank"] == 262
    assert audit["pass_gate"]
    assert report["two_component_generic_audit"]["pass_gate"]
    assert not report["property_evaluation_attempted"]
    assert not report["dynamic_integration_attempted"]
    assert report["pass_gate"]
