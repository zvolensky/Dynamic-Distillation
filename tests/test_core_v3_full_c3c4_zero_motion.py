from pathlib import Path

import numpy as np

from tools import audit_core_v3_full_c3c4_zero_motion as dd233


def test_dd233_contract_freezes_full_controlled_bdf2_audit(tmp_path):
    payload = dd233.prepare(
        tmp_path / "dd233_contract.json",
        tmp_path / "dd233_contract.md",
    )

    assert payload["required_rank"] == 162
    assert len(payload["root_solve_coordinates"]) == 162
    assert len(payload["coordinate_scale"]) == 162
    assert len(payload["sentinel_indices"]) >= 12
    assert payload["provider_routing"]["declared_liquid_density"].startswith(
        "aligned_pr"
    )
    assert not payload["property_evaluation_attempted"]
    assert not payload["residual_evaluation_attempted"]
    assert not payload["jacobian_evaluation_attempted"]
    assert not payload["nonlinear_solve_attempted"]
    assert not payload["timestep_attempted"]
    assert not payload["dynamic_integration_attempted"]


def test_dd233_adapts_only_accepted_stationary_coordinate_scales():
    handoff = dd233._load(dd233.DD232)
    root_contract = dd233._load(dd233.DD231_CONTRACT)
    model_contract = dd233._load(Path(root_contract["source_model_contract"]))
    spec = dd233.dd223.dd222._spec(
        model_contract["source_mapping"],
        float(model_contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    controlled = dd233._controlled_contract(spec, handoff)
    stationary = np.asarray(dd233._load(dd233.DD230)["coordinate_scale"])
    scale = dd233._adapted_coordinate_scale(spec, controlled, stationary)

    assert np.array_equal(scale[:62], np.ones(62))
    assert np.all(scale[62:] > 0.0)
    assert scale.shape == (162,)


def test_dd233_direct_column_helper_matches_linear_derivative():
    matrix = np.asarray(((2.0, -1.0), (0.5, 3.0)))

    def objective(point, _state_id):
        return matrix @ point

    column = dd233._direct_column(
        objective,
        np.asarray((0.25, -0.75)),
        1,
        step=1.0e-5,
        state_id="test",
    )

    assert np.allclose(column, matrix[:, 1], rtol=0.0, atol=5.0e-11)
