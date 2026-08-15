import numpy as np

from tools import run_core_v3_full_c3c4_stationary_hold_step as dd234


def test_dd234_contract_freezes_one_full_and_two_half_steps(tmp_path):
    payload = dd234.prepare(
        tmp_path / "dd234_contract.json",
        tmp_path / "dd234_contract.md",
    )

    assert payload["steps"] == {
        "full_seconds": 0.25,
        "half_seconds": 0.125,
        "sequence": ["full", "half_1", "half_2"],
        "adopted_startup_candidate": "full",
    }
    assert payload["required_rank"] == 162
    assert len(payload["solver"]["x_scale"]) == 162
    assert payload["solver"]["jacobian_mode"] == "colored"
    assert not payload["property_evaluation_attempted"]
    assert not payload["nonlinear_solve_attempted"]
    assert not payload["timestep_attempted"]
    assert not payload["dynamic_integration_attempted"]


def test_dd234_rank_condition_uses_the_frozen_coordinate_scale():
    matrix = np.diag((2.0, 3.0))
    rank, condition = dd234._rank_condition(matrix, np.asarray((0.5, 2.0)))

    assert rank == 2
    assert np.isclose(condition, 6.0)


def test_dd234_settings_reconstruct_array_x_scale():
    payload = {
        "solver": {
            "method": "trf",
            "ftol": 1.0e-12,
            "xtol": 1.0e-12,
            "gtol": 1.0e-12,
            "max_nfev": 20,
            "x_scale": [1.0, 2.0],
            "jacobian_step": 1.0e-5,
            "jacobian_mode": "colored",
        }
    }

    settings = dd234._settings(payload)

    assert np.array_equal(settings.x_scale, np.asarray((1.0, 2.0)))
