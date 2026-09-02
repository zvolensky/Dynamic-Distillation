from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEASIBILITY_REPORT = (
    ROOT
    / "logs/core_v3_water_methanol_vtpr_phase_total_bound_feasibility_20260831.json"
)
ROOT_REPORT = (
    ROOT / "logs/core_v3_water_methanol_vtpr_phase_total_stationary_root_20260831.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase_total_bounds_contain_the_stable_linearized_closure():
    report = _load(FEASIBILITY_REPORT)

    assert report["classification"] == "linearized_full_closure_within_generic_bounds"
    assert report["pass_gate"]
    assert report["bound_policy"] == "phase_total"
    assert not report["component_specific_logic"]
    assert report["derivative_gate_pass"]
    assert not report["coordinated_bound_conflict"]
    assert all(item["bound_violation_count"] == 0 for item in report["step_results"])
    assert report["matrix_relative_change"] < 0.05
    assert report["correction_relative_change"] < 0.05
    assert report["decision"] == "authorize_one_bounded_stationary_solve"


def test_phase_total_bound_stationary_root_is_accepted():
    report = _load(ROOT_REPORT)

    assert report["classification"] == "stationary_root_accepted"
    assert report["pass_gate"]
    assert report["decision"] == "ready_for_zero_time_dynamic_handoff_audit"
    assert report["density_model"] == "VTPR"
    assert report["bound_policy"] == "phase_total"
    assert report["scaled_residual_inf_norm"] < 1.0e-8
    assert report["raw_block_maxima"]["energy_balance_BTUph"] < 1.0e-3
    assert report["endpoint_jacobian"]["pass_gate"]
    assert all(item["rank"] == 100 for item in report["endpoint_jacobian"]["steps"])
    assert report["endpoint"]["minimum_bound_distance"] > 1.0e-6
    assert report["endpoint"]["physical_pass"]
    assert report["conservation_pass"]
    assert report["provider"]["pass"]
    assert not report["provider"]["fallback_attempted"]
    assert not report["retry_attempted"]
    assert not report["continuation_attempted"]
    assert not report["timestep_attempted"]
