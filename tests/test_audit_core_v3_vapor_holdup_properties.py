import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "logs/dd238_core_v3_c3c4_vapor_holdup_properties_20260820.json"


def test_dd238_live_vapor_holdup_property_audit_passes():
    payload = json.loads(RESULT.read_text(encoding="utf-8"))

    assert payload["pass_gate"]
    assert payload["property_audit"]["pass_gate"]
    assert payload["provider_routing"]["pass_gate"]
    assert payload["property_audit"]["provider_call_count"] == 80
    assert payload["property_audit"]["maximum_relative_eos_residual"] <= 1.0e-12
    assert payload["inventory_summary"]["total_vapor_moles_lbmol"] > 0.0
    assert not payload["full_two_phase_dae_residual_evaluated"]
    assert not payload["nonlinear_solve_attempted"]
    assert not payload["timestep_attempted"]
    assert not payload["dynamic_integration_attempted"]
