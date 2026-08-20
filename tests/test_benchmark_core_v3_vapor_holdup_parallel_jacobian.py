from __future__ import annotations

import json

from tools import benchmark_core_v3_vapor_holdup_parallel_jacobian as dd251


def test_dd251_saved_contract_freezes_exact_parallel_matrix_benchmark():
    saved = json.loads((dd251.ROOT / dd251.CONTRACT).read_text(encoding="utf-8"))

    assert not saved["campaign_executed"]
    assert saved["benchmark"]["matrix_shape"] == [258, 258]
    assert saved["benchmark"]["color_count"] == 28
    assert saved["benchmark"]["task_count"] == 56
    assert saved["benchmark"]["worker_count"] == 8
    assert saved["benchmark"]["parallel_time_ratio_limit"] == 0.75
