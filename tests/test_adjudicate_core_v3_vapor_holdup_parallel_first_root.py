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


def test_dd253_saved_result_accepts_exact_work_and_worker_evidence():
    saved = json.loads((dd253.ROOT / dd253.RESULT).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert all(saved["gates"].values())
    assert saved["worker_count_each"] == [8, 8, 8, 8, 8, 8]
    assert saved["serial_logical_work"] == saved["parallel_logical_work"]
    assert saved["logical_work_difference"] == 0
    assert saved["property_calls"] == 0
    assert not saved["rerun_attempted"]
