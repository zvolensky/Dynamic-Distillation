from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_terminal_control_thirty_second_bound_corrected as dd271


def test_dd271_saved_result_passes_every_frozen_gate():
    report = json.loads((dd271.ROOT / dd271.RESULT).read_text(encoding="utf-8"))
    final = report["nominal_endpoints"][-1]

    assert report["classification"].endswith("bound_corrected_passed")
    assert report["pass_gate"]
    assert all(report["gates"].values())
    assert len(report["nominal_endpoints"]) == 120
    assert len(report["new_endpoint_reports"]) == 96
    assert final["time_sec"] == 30.0
    assert final["scaled_residual_inf_norm"] < 1.0e-8
    assert final["jacobian_rank"] == 262
    assert final["physical_pass"]
    assert report["controller_aware_refinement_unexplained_max_abs_lbmol"] < 1.0e-6
    assert report["logical_provider_calls"] < 750_000
    assert not report["retry_attempted"]
    assert not report["tuning_change_attempted"]
