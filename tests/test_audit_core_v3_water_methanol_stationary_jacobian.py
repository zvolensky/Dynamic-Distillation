from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_water_methanol_stationary_jacobian as audit


def test_saved_water_methanol_jacobian_passes_numerical_gate():
    report = json.loads((audit.ROOT / audit.DEFAULT_JSON).read_text(encoding="utf-8"))

    assert report["classification"] == "stationary_jacobian_passed"
    assert report["pass_gate"]
    assert report["decision"] == "authorize_one_bounded_stationary_solve"
    assert report["dimension"] == 100
    assert report["color_count"] == 22
    assert all(step["rank"] == 100 for step in report["step_results"])
    assert all(step["condition"] < 1.0e8 for step in report["step_results"])
    assert all(not step["zero_rows"] for step in report["step_results"])
    assert all(not step["zero_columns"] for step in report["step_results"])
    assert report["matrix_relative_frobenius_change"] < 0.05
    assert report["spectrum_relative_change"] < 0.25
    assert all(item["pass_gate"] for item in report["sentinel_columns"])
    assert not report["provider_fallback_attempted"]
    assert not report["nonlinear_solve_attempted"]
    assert not report["timestep_attempted"]
