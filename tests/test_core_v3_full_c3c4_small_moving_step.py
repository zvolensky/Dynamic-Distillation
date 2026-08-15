import numpy as np
import pytest

from tools import run_core_v3_full_c3c4_small_moving_step as dd235


def test_dd235_contract_reuses_the_accepted_small_disturbance(tmp_path):
    payload = dd235.prepare(
        tmp_path / "dd235_contract.json",
        tmp_path / "dd235_contract.md",
    )

    assert payload["disturbance"]["feed_multiplier"] == 1.001
    assert payload["disturbance"]["feed_enthalpy_multiplier"] == 1.001
    assert not payload["disturbance"]["feed_composition_changed"]
    assert not payload["disturbance"]["feed_specific_enthalpy_changed"]
    assert np.isclose(
        payload["disturbance"]["total_rate_increment_lbmolph"], 7.142974
    )
    assert payload["steps"]["full_seconds"] == 0.25
    assert payload["steps"]["half_seconds"] == 0.125
    assert payload["required_rank"] == 162
    assert not payload["property_evaluation_attempted"]
    assert not payload["timestep_attempted"]
    assert not payload["disturbance_attempted"]
    assert not payload["trajectory_attempted"]


def test_dd235_path_response_matches_constant_external_rate():
    class State:
        liquid_mole_fraction = np.asarray(((0.8, 0.2), (0.1, 0.9)))

    class Base:
        physical_state = State()

    class Control:
        base = Base()

    class Evaluation:
        endpoint_inventory_lbmol = np.asarray(((1.1, 2.2), (3.3, 4.4)))
        distillate_lbmolph = 2.0
        bottoms_lbmolph = 3.0
        control_evaluation = Control()

    class Spec:
        feed_component_lbmolph = np.asarray((10.0, 20.0))

    initial = np.asarray(((1.0, 2.0), (3.0, 4.0)))
    result = dd235._path_response(initial, [Evaluation()], [1.0], Spec())

    assert np.allclose(result["component_inventory_change_lbmol"], (0.4, 0.6))
    assert result["total_inventory_change_lbmol"] == pytest.approx(1.0)
