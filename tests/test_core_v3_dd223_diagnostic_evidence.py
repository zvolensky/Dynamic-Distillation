from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_dd223_diagnostic_evidence as dd224


def test_dd224_identifies_the_exact_saved_evidence_gap_without_live_work():
    result = dd224.run()

    assert result["pass_gate"]
    assert not result["static_localization_possible"]
    assert result["read_only_endpoint_replay_possible"]
    assert result["decision"] == "authorize_one_frozen_read_only_endpoint_replay_contract"
    assert all(
        item["jacobian_spectra_saved"]
        and not item["complete_jacobian_matrices_saved"]
        and not item["complete_residual_vector_saved"]
        for item in result["starts"].values()
    )
    assert result["model_calls"] == result["provider_calls"] == 0
    assert result["solver_calls"] == result["timestep_calls"] == 0


def test_dd224_does_not_change_dd223_classification_or_decision():
    result = dd224.run()

    assert result["source_classification_preserved"] == "full_c3c4_stationary_root_failed"
    assert result["source_decision_preserved"] == "stop_full_c3c4_root_path_without_retry"
    assert result["required_replay_scope"]["nonlinear_solve"] is False
    assert result["required_replay_scope"]["dynamic_integration"] is False
