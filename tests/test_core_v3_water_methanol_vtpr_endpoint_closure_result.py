from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "logs/core_v3_water_methanol_vtpr_endpoint_closure_20260831.json"


def test_saved_endpoint_closure_uses_generic_logic_and_stops_before_resolve():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["classification"] == "active_bound_has_only_marginal_local_descent"
    assert report["pass_gate"]
    assert not report["component_specific_logic"]
    assert report["outward_local_descent_detected"]
    assert not report["bound_materially_limits_local_descent"]
    assert report["relative_outward_least_squares_cost_improvement"] < 1.0e-3
    assert report["energy_closure"]["material_residuals_same_sign"]
    assert report["energy_closure"]["material_residual_relative_spread"] < 0.02
    assert abs(report["energy_closure"]["global_external_energy_rate_BTUph"]) > 1.0e7
    assert report["decision"] == (
        "investigate_generic_energy_closure_before_any_second_solve"
    )
    assert not report["nonlinear_solve_attempted"]
    assert not report["bounds_changed"]
    assert not report["equations_changed"]
    assert not report["timestep_attempted"]
