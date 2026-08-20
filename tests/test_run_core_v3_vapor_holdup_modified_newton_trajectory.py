from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_modified_newton_trajectory as dd255


def test_dd255_saved_contract_freezes_one_jacobian_per_root():
    saved = json.loads((dd255.ROOT / dd255.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["method"]["fresh_jacobians_per_root"] == 1
    assert saved["method"]["parallel_workers"] == 0
    assert saved["trajectory"]["steps_per_path"] == 4
    assert saved["limits"]["logical_provider_call_ratio"] == 0.30
    assert saved["limits"]["trajectory_wall_ratio"] == 0.65
