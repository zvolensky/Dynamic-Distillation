from types import SimpleNamespace

import numpy as np

from dynamic_distillation.core_v3.controlled_terminal_trajectory_v1 import (
    run_controlled_terminal_trajectory,
)
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings


def _evaluation(
    point,
    target,
    previous_inventory,
    previous_top_u,
    previous_lower_u,
    previous_memory,
):
    step = np.asarray(point, dtype=float)
    return SimpleNamespace(
        scaled=step - float(target),
        base=SimpleNamespace(
            endpoint_inventory_lbmol=np.asarray(previous_inventory) + 0.01,
            endpoint_top_internal_energy_BTU=float(previous_top_u) + 1.0,
            endpoint_lower_internal_energy_BTU=np.asarray(previous_lower_u) + 1.0,
        ),
        endpoint_controller_memory=np.asarray(previous_memory) - 0.01,
    )


def _basis():
    seen = []

    def objective_factory(inventory, top_u, lower_u, memory, seconds):
        seen.append((inventory.copy(), top_u, lower_u.copy(), memory.copy(), seconds))
        target = len(seen)

        def objective(point, _state_id):
            return _evaluation(point, target, inventory, top_u, lower_u, memory)

        return objective

    def jacobian_factory(_objective):
        return lambda point, state_id: np.eye(np.asarray(point).size)

    return seen, objective_factory, jacobian_factory


def test_dd134_trajectory_chains_endpoints_with_one_jacobian_per_step():
    seen, objective_factory, jacobian_factory = _basis()
    result = run_controlled_terminal_trajectory(
        objective_factory,
        jacobian_factory,
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_top_internal_energy_BTU=10.0,
        initial_lower_internal_energy_BTU=np.ones(2),
        initial_controller_memory=np.zeros(2),
        initial_coordinates=np.zeros(3),
        lower_bounds=np.full(3, -10.0),
        upper_bounds=np.full(3, 10.0),
        step_seconds=1.0,
        duration_seconds=3.0,
        settings=ModifiedNewtonSettings(),
        name="chain",
    )

    assert result.completed
    assert result.completed_steps == result.requested_steps == 3
    assert len(seen) == 3
    assert np.allclose(seen[1][0], seen[0][0] + 0.01)
    assert seen[1][1] == seen[0][1] + 1.0
    assert np.allclose(seen[1][3], seen[0][3] - 0.01)
    assert all(step.outcome.jacobian_evaluations == 1 for step in result.steps)


def test_trajectory_step_jacobian_factory_receives_advancing_state():
    seen, objective_factory, _jacobian_factory = _basis()
    jacobian_states = []

    def unused_factory(_objective):
        raise AssertionError("legacy Jacobian factory must not be used")

    def step_factory(objective, inventory, top_u, lower_u, memory, seconds):
        jacobian_states.append(
            (
                inventory.copy(),
                float(top_u),
                lower_u.copy(),
                memory.copy(),
                float(seconds),
            )
        )
        return lambda point, state_id: np.eye(np.asarray(point).size)

    result = run_controlled_terminal_trajectory(
        objective_factory,
        unused_factory,
        step_jacobian_factory=step_factory,
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_top_internal_energy_BTU=10.0,
        initial_lower_internal_energy_BTU=np.ones(2),
        initial_controller_memory=np.zeros(2),
        initial_coordinates=np.zeros(3),
        lower_bounds=np.full(3, -10.0),
        upper_bounds=np.full(3, 10.0),
        step_seconds=1.0,
        duration_seconds=3.0,
        settings=ModifiedNewtonSettings(),
        name="step-hook",
    )

    assert result.completed
    assert len(jacobian_states) == 3
    assert np.array_equal(jacobian_states[0][0], seen[0][0])
    assert np.array_equal(jacobian_states[1][0], seen[1][0])
    assert jacobian_states[1][1] == jacobian_states[0][1] + 1.0
    assert np.allclose(jacobian_states[1][3], jacobian_states[0][3] - 0.01)
    assert all(item[4] == 1.0 for item in jacobian_states)


def test_dd134_trajectory_stops_at_first_failed_root():
    seen, objective_factory, _jacobian_factory = _basis()

    def singular_factory(_objective):
        return lambda point, state_id: np.zeros((np.asarray(point).size,) * 2)

    result = run_controlled_terminal_trajectory(
        objective_factory,
        singular_factory,
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_top_internal_energy_BTU=10.0,
        initial_lower_internal_energy_BTU=np.ones(2),
        initial_controller_memory=np.zeros(2),
        initial_coordinates=np.zeros(3),
        lower_bounds=np.full(3, -10.0),
        upper_bounds=np.full(3, 10.0),
        step_seconds=0.5,
        duration_seconds=2.0,
        settings=ModifiedNewtonSettings(),
        name="fail",
    )

    assert not result.completed
    assert result.completed_steps == 1
    assert len(seen) == 1


def test_dd134_trajectory_rejects_invalid_time_grids():
    _seen, objective_factory, jacobian_factory = _basis()
    common = dict(
        objective_factory=objective_factory,
        jacobian_factory=jacobian_factory,
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_top_internal_energy_BTU=10.0,
        initial_lower_internal_energy_BTU=np.ones(2),
        initial_controller_memory=np.zeros(2),
        initial_coordinates=np.zeros(3),
        lower_bounds=np.full(3, -10.0),
        upper_bounds=np.full(3, 10.0),
        settings=ModifiedNewtonSettings(),
        name="invalid",
    )
    for step, duration in ((0.0, 1.0), (1.0, 0.0), (0.6, 1.0)):
        try:
            run_controlled_terminal_trajectory(
                **common, step_seconds=step, duration_seconds=duration
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid controlled trajectory grid was accepted")
