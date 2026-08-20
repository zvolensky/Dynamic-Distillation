from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_five_second_trajectory as dd257


def test_dd257_saved_contract_freezes_five_second_serial_path():
    saved = json.loads((dd257.ROOT / dd257.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["trajectory"]["duration_sec"] == 5.0
    assert saved["trajectory"]["step_sec"] == 0.25
    assert saved["trajectory"]["steps_per_path"] == 20
    assert saved["limits"]["rank"] == 258
    assert saved["limits"]["wall_clock_sec"] == 240.0
