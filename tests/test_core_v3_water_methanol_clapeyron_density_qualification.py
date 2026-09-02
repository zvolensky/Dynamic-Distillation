from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import qualify_core_v3_water_methanol_clapeyron_density as qualification


def test_saved_clapeyron_density_qualification_selects_a_passing_model():
    report = json.loads(
        (qualification.ROOT / qualification.DEFAULT_JSON).read_text(encoding="utf-8")
    )

    assert report["classification"] == "clapeyron_density_model_qualified"
    assert report["pass_gate"]
    assert report["selected_density_model"] in qualification.MODELS
    selected = next(
        result
        for result in report["model_results"]
        if result["model"] == report["selected_density_model"]
    )
    assert selected["pass_gate"]
    assert selected["state_count"] == 20
    assert selected["maximum_absolute_relative_density_delta"] <= 0.10
    assert selected["maximum_derivative_relative_change"] <= 1.0e-5
    assert selected["maximum_repeatability_absolute_delta"] <= 1.0e-12
    assert not report["nonlinear_solve_attempted"]
    assert not report["timestep_attempted"]
    assert not report["workbook_modified"]
