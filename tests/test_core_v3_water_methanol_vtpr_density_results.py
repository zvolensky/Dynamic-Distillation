from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTING_REPORT = (
    ROOT / "logs/core_v3_water_methanol_vtpr_density_starting_state_20260831.json"
)
JACOBIAN_REPORT = (
    ROOT
    / "logs/core_v3_water_methanol_vtpr_density_stationary_jacobian_20260831.json"
)
ROOT_REPORT = (
    ROOT / "logs/core_v3_water_methanol_vtpr_density_stationary_root_20260831.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_vtpr_density_starting_state_passes_without_provider_fallback():
    report = _load(STARTING_REPORT)

    assert report["classification"] == "usable_starting_state_not_steady"
    assert report["pass_gate"]
    assert report["bulk_provider"] == "dwsim"
    assert report["liquid_density_provider"] == "clapeyron_vtpr"
    assert report["density_model"] == "VTPR"
    assert report["physical_checks"]["minimum_free_vapor_volume_ft3"] > 0.0
    assert not report["provider_calls"]["fallback_attempted"]


def test_vtpr_density_jacobian_is_full_rank_and_step_stable():
    report = _load(JACOBIAN_REPORT)

    assert report["classification"] == "stationary_jacobian_passed"
    assert report["pass_gate"]
    assert report["liquid_density_provider"] == "clapeyron_vtpr"
    assert all(step["rank"] == 100 for step in report["step_results"])
    assert all(step["condition"] < 1.0e8 for step in report["step_results"])
    assert report["matrix_relative_frobenius_change"] < 0.05
    assert report["spectrum_relative_change"] < 0.25
    assert not report["provider_fallback_attempted"]


def test_single_vtpr_density_solve_is_preserved_as_rejected_evidence():
    repaired = _load(ROOT_REPORT)
    original = _load(ROOT / "logs/core_v3_water_methanol_stationary_root_20260831.json")

    assert repaired["classification"] == "stationary_root_rejected"
    assert not repaired["pass_gate"]
    assert repaired["decision"] == "stop_stationary_nonlinear_work"
    assert repaired["solver"]["success"]
    assert repaired["liquid_density_provider"] == "clapeyron_vtpr"
    assert repaired["scaled_residual_inf_norm"] < original["scaled_residual_inf_norm"]
    assert repaired["scaled_residual_inf_norm"] > 1.0e-8
    assert repaired["endpoint"]["physical_pass"]
    assert repaired["endpoint"]["minimum_bound_distance"] < 1.0e-8
    assert repaired["conservation_pass"]
    assert repaired["provider"]["interface_provider_identities"] == {
        "declared_liquid_density": "clapeyron_vtpr"
    }
    assert not repaired["provider"]["fallback_attempted"]
    assert not repaired["retry_attempted"]
    assert not repaired["continuation_attempted"]
    assert not repaired["timestep_attempted"]
