from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import audit_core_v3_dd223_endpoint_replay as dd225


def test_dd225_contract_is_read_only_and_freezes_both_endpoints(tmp_path):
    contract = dd225.prepare(tmp_path / "dd225_contract.json")

    assert set(contract["endpoints"]) == {
        "source_mapped_seed",
        "independent_smooth_topology_seed",
    }
    assert contract["dimension"] == 160
    assert contract["jacobian"]["steps"] == [1.0e-5, 5.0e-6]
    assert contract["provider_calls_during_preparation"] == 0
    assert not contract["nonlinear_solve_attempted"]
    assert not contract["state_changed"]
    assert not contract["timestep_attempted"]
    assert not contract["dynamic_integration_attempted"]


def test_dd225_jacobian_payload_preserves_complete_matrix_and_svd():
    matrix = np.asarray([[3.0, 0.0], [0.0, 2.0]])
    item = type(
        "Audit",
        (),
        {
            "step": 1.0e-5,
            "matrix": matrix,
            "rank": 2,
            "condition": 1.5,
            "zero_rows": (),
            "zero_columns": (),
            "unexpected_couplings": (),
            "bubble_matrix": np.eye(1),
            "bubble_rank": 1,
            "bubble_singular_values": np.ones(1),
        },
    )()

    payload = dd225._jacobian_payload(item)

    assert np.array(payload["matrix"]).shape == (2, 2)
    assert np.array(payload["left_singular_vectors"]).shape == (2, 2)
    assert np.array(payload["right_singular_vectors_transposed"]).shape == (2, 2)
    assert payload["singular_values"] == [3.0, 2.0]
