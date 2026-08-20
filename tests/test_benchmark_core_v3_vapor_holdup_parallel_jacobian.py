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


def test_dd251_saved_result_qualifies_exact_parallel_jacobian():
    saved = json.loads((dd251.ROOT / dd251.RESULT).read_text(encoding="utf-8"))

    assert saved["pass_gate"]
    assert all(saved["gates"].values())
    assert saved["serial"]["matrix_sha256"] == saved["parallel"]["matrix_sha256"]
    assert saved["comparison"]["matrix_max_abs_difference"] == 0.0
    assert saved["serial"]["rank"] == saved["parallel"]["rank"] == 258
    assert saved["comparison"]["speedup"] > 1.0
    assert not saved["nonlinear_solve_attempted"]
    assert not saved["state_advance_attempted"]
