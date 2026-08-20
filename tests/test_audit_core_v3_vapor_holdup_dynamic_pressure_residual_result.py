from __future__ import annotations

import json

from tools import audit_core_v3_vapor_holdup_dynamic_pressure_residual as dd273


def test_dd273_saved_result_passes_every_gate_without_a_solve():
    report = json.loads((dd273.ROOT / dd273.RESULT).read_text(encoding="utf-8"))

    assert report["pass_gate"]
    assert all(report["gates"].values())
    assert all(item["rank"] == 262 for item in report["jacobian_steps"])
    assert report["predictor_scaled_residual_inf_norm"] < 0.1
    assert report["duty_row_derivative_error"] < 1.0e-8
    assert not report["nonlinear_solve_attempted"]
    assert not report["timestep_attempted"]
