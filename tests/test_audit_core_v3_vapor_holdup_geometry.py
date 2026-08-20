from tools import audit_core_v3_vapor_holdup_geometry as dd237


def test_dd237_actual_c3c4_geometry_maps_and_retains_full_rank():
    report = dd237.build_report()

    assert report["stage_count"] == 20
    assert report["feed_stage_1based"] == 12
    assert report["geometry_audit"]["volume_count"] == 20
    assert report["geometry_audit"]["pass_gate"]
    assert report["structural_audit"]["solve_variable_count"] == 258
    assert report["structural_audit"]["structural_rank"] == 258
    assert report["capacity_summary_ft3"]["top_drum"] > 0.0
    assert report["capacity_summary_ft3"]["bottom_combined"] > 0.0
    assert not report["endpoint_free_volume_evaluated"]
    assert not report["property_evaluation_attempted"]
    assert report["pass_gate"]
