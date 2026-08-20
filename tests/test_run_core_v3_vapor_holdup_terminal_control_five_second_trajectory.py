from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_terminal_control_five_second_trajectory as dd269


def test_dd269_frozen_contract_is_pre_execution_and_controller_aware():
    saved = json.loads((dd269.ROOT / dd269.CONTRACT).read_text(encoding="utf-8"))

    assert saved["schema_id"] == dd269.SCHEMA
    assert saved["trajectory"]["source_replay_steps"] == 4
    assert saved["trajectory"]["nominal_continuation_steps"] == 16
    assert saved["trajectory"]["refined_steps"] == 2
    assert saved["solver"]["expected_color_count"] == 16
    assert saved["limits"]["controller_aware_refinement_identity_lbmol"] == 1.0e-6
    assert not saved["property_evaluation_attempted"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["trajectory_attempted"]
    assert not saved["campaign_executed"]
