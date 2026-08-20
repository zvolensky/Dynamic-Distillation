from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_terminal_control_five_second_trajectory as dd269


def test_dd269_saved_five_second_controlled_trajectory_passes():
    saved = json.loads((dd269.ROOT / dd269.RESULT).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert len(saved["nominal_endpoints"]) == 20
    assert len(saved["refined_endpoints"]) == 2
    assert len(saved["new_endpoint_reports"]) == 18
    assert all(saved["gates"].values())
    assert saved["logical_provider_calls"] == 101160
    assert saved["nominal_endpoints"][-1]["scaled_residual_inf_norm"] < 1.0e-8
    assert saved["nominal_endpoints"][-1]["distillate_lbmolph"] < 2519.6082684395155
    assert saved["nominal_endpoints"][-1]["bottoms_lbmolph"] > 4625.003901595657
    assert (
        saved["controller_aware_refinement_unexplained_max_abs_lbmol"]
        < 1.0e-6
    )
