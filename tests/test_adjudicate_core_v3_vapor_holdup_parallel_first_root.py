from __future__ import annotations

import json

from tools import adjudicate_core_v3_vapor_holdup_parallel_first_root as dd253


def test_dd253_saved_contract_is_zero_call_and_accounting_only():
    saved = json.loads((dd253.ROOT / dd253.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["adjudication"]["property_calls"] == 0
    assert not saved["adjudication"]["rerun"]
    assert saved["adjudication"]["required_worker_count"] == 8
    assert saved["adjudication"]["required_work_difference"] == 0
