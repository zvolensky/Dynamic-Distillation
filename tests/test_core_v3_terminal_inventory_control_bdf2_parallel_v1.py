from types import SimpleNamespace

import numpy as np

from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_parallel_v1 import (
    controlled_bdf2_history_payload,
    physical_state_payload,
)


def test_parallel_physical_state_payload_is_complete_and_serializable():
    state = SimpleNamespace(
        liquid_moles_lbmol=np.ones(2),
        liquid_mole_fraction=np.asarray(((0.2, 0.8),)),
        temperature_F=np.asarray((100.0,)),
        vapor_mole_fraction=np.asarray(((0.3, 0.7),)),
        hydraulic_liquid_flow_lbmolph=np.asarray((10.0,)),
        vapor_flow_lbmolph=np.asarray((20.0,)),
        distillate_lbmolph=3.0,
        bottoms_lbmolph=4.0,
        bubble_vapor_mole_fraction=np.asarray((0.4, 0.6)),
        condenser_duty_BTUph=-5.0,
    )

    payload = physical_state_payload(state)

    assert payload["liquid_moles_lbmol"] == [1.0, 1.0]
    assert payload["bubble_vapor_mole_fraction"] == [0.4, 0.6]
    assert payload["condenser_duty_BTUph"] == -5.0


def test_parallel_bdf2_history_payload_preserves_both_levels():
    history = SimpleNamespace(
        step_seconds=0.125,
        current_inventory_lbmol=np.asarray(((2.0, 3.0),)),
        prior_inventory_lbmol=np.asarray(((1.0, 2.0),)),
        current_internal_energy_BTU=np.asarray((20.0,)),
        prior_internal_energy_BTU=np.asarray((10.0,)),
        current_controller_memory=np.asarray((0.2, 0.3)),
        prior_controller_memory=np.asarray((0.1, 0.2)),
    )

    payload = controlled_bdf2_history_payload(history)

    assert payload["step_seconds"] == 0.125
    assert payload["current_inventory_lbmol"] == [[2.0, 3.0]]
    assert payload["prior_inventory_lbmol"] == [[1.0, 2.0]]
    assert payload["current_controller_memory"] == [0.2, 0.3]
