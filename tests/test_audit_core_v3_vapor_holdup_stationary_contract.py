from __future__ import annotations

from tools import audit_core_v3_vapor_holdup_stationary_contract as dd242


def test_dd242_saved_artifact_matches_report():
    generated = dd242.build_report()
    saved = dd242._load_saved_for_test()

    assert saved["schema_id"] == generated["schema_id"]
    assert saved["implementation_sha256"] == generated["implementation_sha256"]
    assert saved["tests_sha256"] == generated["tests_sha256"]
    assert saved["pass_gate"]
    assert saved["full_c3c4_topology"]["audit"]["variable_count"] == 260
    assert saved["full_c3c4_topology"]["audit"]["structural_rank"] == 260
