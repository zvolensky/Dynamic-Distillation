from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_water_methanol_rejected_root as diagnostic
import audit_core_v3_water_methanol_density_derivatives as density_diagnostic
import run_core_v3_water_methanol_stationary_root as stationary_root


def test_single_stationary_solve_is_preserved_as_rejected_evidence():
    report = json.loads(
        (stationary_root.ROOT / stationary_root.DEFAULT_JSON).read_text(encoding="utf-8")
    )

    assert report["classification"] == "stationary_root_rejected"
    assert not report["pass_gate"]
    assert report["decision"] == "stop_stationary_nonlinear_work"
    assert report["solver"]["success"]
    assert report["scaled_residual_inf_norm"] > 1.0e-8
    assert report["endpoint"]["physical_pass"]
    assert report["endpoint"]["minimum_bound_distance"] > 1.0e-6
    assert report["conservation_pass"]
    assert not report["provider"]["fallback_attempted"]
    assert not report["retry_attempted"]
    assert not report["continuation_attempted"]
    assert not report["timestep_attempted"]


def test_rejected_candidate_diagnostic_identifies_unreliable_derivatives():
    report = json.loads(
        (diagnostic.ROOT / diagnostic.DEFAULT_JSON).read_text(encoding="utf-8")
    )

    assert report["classification"] == "rejected_candidate_derivatives_unreliable"
    assert report["pass_gate"]
    assert not report["derivative_gate_pass"]
    assert all(item["rank"] == 100 for item in report["step_results"])
    assert max(item["condition"] for item in report["step_results"]) > 1.0e8
    assert report["matrix_relative_frobenius_change"] > 0.05
    assert not report["provider_fallback_attempted"]
    assert not report["nonlinear_solve_attempted"]
    assert not report["retry_attempted"]
    assert not report["timestep_attempted"]


def test_property_diagnostic_isolates_liquid_density_derivative_noise():
    report = json.loads(
        (density_diagnostic.ROOT / density_diagnostic.DEFAULT_JSON).read_text(
            encoding="utf-8"
        )
    )

    assert report["classification"] == "liquid_density_derivative_noise_isolated"
    assert report["pass_gate"]
    assert report["maximum_density_derivative_relative_change"] > 0.1
    assert report["maximum_enthalpy_or_fugacity_derivative_relative_change"] < 1.0e-5
    assert not report["provider_fallback_attempted"]
    assert not report["nonlinear_solve_attempted"]
    assert not report["retry_attempted"]
    assert not report["timestep_attempted"]
