from tools import audit_core_v3_vapor_holdup_dae_contract as dd236


def test_dd236_report_passes_development_and_full_column_structures():
    report = dd236.build_report()
    development = report["development_topology"]["audit"]
    full = report["full_c3c4_topology"]["audit"]

    assert development["solve_variable_count"] == 63
    assert development["structural_rank"] == 63
    assert full["volume_count"] == 20
    assert full["solve_variable_count"] == 258
    assert full["structural_rank"] == 258
    assert report["physical_geometry_required_before_live_properties"]
    assert not report["historical_core_v3_modified"]
    assert not report["property_evaluation_attempted"]
    assert not report["nonlinear_solve_attempted"]
    assert not report["timestep_attempted"]
    assert report["pass_gate"]
