import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "logs/dd239_core_v3_c3c4_two_phase_balances_20260820.json"


def test_dd239_two_phase_zero_rate_balance_audit_passes():
    payload = json.loads(RESULT.read_text(encoding="utf-8"))
    summary = payload["balance_summary"]

    assert payload["pass_gate"]
    assert summary["maximum_liquid_component_residual_lbmolph"] <= 1.0e-7
    assert summary["maximum_vapor_component_residual_lbmolph"] <= 1.0e-7
    assert summary["maximum_energy_residual_BTUph"] <= 1.0e-4
    assert summary["phase_transfer_cancellation_exact"]
    assert not payload["full_258_residual_evaluated"]
    assert not payload["nonlinear_solve_attempted"]
    assert not payload["timestep_attempted"]
    assert not payload["dynamic_integration_attempted"]
