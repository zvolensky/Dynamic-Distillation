from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_terminal_control_short_trajectory as dd267


def test_dd267_frozen_contract_is_pre_execution_and_complete():
    saved = json.loads((dd267.ROOT / dd267.CONTRACT).read_text(encoding="utf-8"))

    assert saved["schema_id"] == dd267.SCHEMA
    assert saved["trajectory"]["nominal_continuation_steps"] == 3
    assert saved["trajectory"]["refined_steps"] == 2
    assert saved["solver"]["expected_color_count"] == 16
    assert saved["solver"]["acceptance_basis"].startswith("residual")
    assert saved["energy_identity"]["aggregate_bound_from_scaled_residual"]
    assert not saved["property_evaluation_attempted"]
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["trajectory_attempted"]
    assert not saved["campaign_executed"]
