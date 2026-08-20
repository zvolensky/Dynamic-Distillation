from __future__ import annotations

import json

from tools import run_core_v3_vapor_holdup_parallel_first_root as dd252


def test_dd252_saved_contract_freezes_serial_parallel_first_root():
    saved = json.loads((dd252.ROOT / dd252.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["root"]["serial_root_count"] == 1
    assert saved["root"]["parallel_root_count"] == 1
    assert saved["root"]["worker_count"] == 8
    assert saved["limits"]["coordinate_absolute_difference"] == 1.0e-12
    assert saved["limits"]["parallel_solve_time_ratio"] == 0.75


def test_dd252_saved_failure_is_limited_to_accounting_gates():
    saved = json.loads((dd252.ROOT / dd252.RESULT).read_text(encoding="utf-8"))
    failed = {name for name, passed in saved["gates"].items() if not passed}

    assert not saved["pass_gate"]
    assert failed == {"process_isolation", "provider_calls"}
    assert saved["comparison"]["jacobian_max_abs_difference"] == 0.0
    assert saved["comparison"]["coordinate_max_abs_difference"] == 0.0
    assert saved["comparison"]["parallel_solve_speedup"] > 1.0
    assert not saved["state_advance_attempted"]
