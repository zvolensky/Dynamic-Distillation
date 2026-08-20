from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_terminal_control_thirty_second_bound_corrected as dd271


def test_dd271_frozen_contract_is_pre_execution_and_controller_aware():
    saved = json.loads((dd271.ROOT / dd271.CONTRACT).read_text(encoding="utf-8"))

    assert saved["schema_id"] == dd271.SCHEMA
    assert saved["trajectory"]["source_replay_steps"] == 26
    assert saved["trajectory"]["nominal_continuation_steps"] == 94
    assert saved["trajectory"]["nominal_final_time_sec"] == 30.0
    assert saved["trajectory"]["refined_steps"] == 2
    assert saved["corrected_product_bounds"]["rate_ratio"] == [0.25, 2.0]
    assert saved["corrected_product_bounds"]["all_other_bounds_unchanged"]
    assert saved["solver"]["expected_color_count"] == 16
    assert saved["limits"]["controller_aware_refinement_identity_lbmol"] == 1.0e-6
    assert not saved["property_evaluation_attempted"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["trajectory_attempted"]
    assert not saved["campaign_executed"]
