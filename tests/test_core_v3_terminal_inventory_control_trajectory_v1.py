from types import SimpleNamespace

import numpy as np
import pytest

import dynamic_distillation.core_v3.terminal_inventory_control_trajectory_v1 as trajectory


def _run(monkeypatch, *, success=True, duration=0.75, step=0.25):
    calls = []

    def fake_solve(*args, **kwargs):
        calls.append(kwargs)
        index = len(calls)
        prior_inventory = np.asarray(kwargs["previous_inventory_lbmol"])
        prior_memory = np.asarray(kwargs["previous_controller_memory"])
        endpoint = SimpleNamespace(
            endpoint_inventory_lbmol=prior_inventory + 0.01,
            endpoint_controller_memory=prior_memory + 0.001,
            control_evaluation=SimpleNamespace(
                base=SimpleNamespace(physical_state=f"state-{index}")
            ),
        )
        return SimpleNamespace(
            success=bool(success),
            evaluation=endpoint,
            final_coordinates=np.full(4, float(index)),
        )

    monkeypatch.setattr(
        trajectory,
        "solve_terminal_inventory_control_backward_euler_step",
        fake_solve,
    )
    result = trajectory.run_terminal_inventory_control_trajectory(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        "state-0",
        SimpleNamespace(),
        SimpleNamespace(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=np.zeros(2),
        level_setpoints=SimpleNamespace(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(3),
        product_reference_lbmolph=(10.0, 20.0),
        step_seconds=step,
        duration_seconds=duration,
        settings=SimpleNamespace(),
        name="test",
    )
    return calls, result


def test_trajectory_chains_inventory_memory_state_and_coordinates(monkeypatch):
    calls, result = _run(monkeypatch)

    assert result.completed
    assert result.completed_steps == result.requested_steps == 3
    assert np.allclose(calls[1]["previous_inventory_lbmol"], 1.01)
    assert np.allclose(calls[1]["previous_controller_memory"], 0.001)
    assert np.allclose(calls[1]["initial_solve_coordinates"], 1.0)
    assert calls[1]["product_reference_lbmolph"].tolist() == [10.0, 20.0]
    assert result.steps[-1].time_seconds == 0.75


def test_trajectory_stops_after_first_failed_root(monkeypatch):
    calls, result = _run(monkeypatch, success=False)

    assert not result.completed
    assert result.completed_steps == 1
    assert len(calls) == 1


def test_trajectory_accepts_an_explicit_step_solver(monkeypatch):
    sentinel_calls = []

    def sentinel(*args, **kwargs):
        sentinel_calls.append(kwargs["name"])
        inventory = np.asarray(kwargs["previous_inventory_lbmol"])
        memory = np.asarray(kwargs["previous_controller_memory"])
        return SimpleNamespace(
            success=True,
            evaluation=SimpleNamespace(
                endpoint_inventory_lbmol=inventory,
                endpoint_controller_memory=memory,
                control_evaluation=SimpleNamespace(
                    base=SimpleNamespace(physical_state="state-1")
                ),
            ),
            final_coordinates=np.zeros(4),
        )

    monkeypatch.setattr(
        trajectory,
        "solve_terminal_inventory_control_backward_euler_step",
        lambda *args, **kwargs: pytest.fail("default solver was called"),
    )
    result = trajectory.run_terminal_inventory_control_trajectory(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        "state-0",
        SimpleNamespace(),
        SimpleNamespace(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=np.zeros(2),
        level_setpoints=SimpleNamespace(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(3),
        product_reference_lbmolph=(10.0, 20.0),
        step_seconds=0.25,
        duration_seconds=0.25,
        settings=SimpleNamespace(),
        name="test",
        step_solver=sentinel,
    )

    assert result.completed
    assert sentinel_calls == ["test:step_1"]


def test_trajectory_stops_before_a_root_when_deadline_has_passed(monkeypatch):
    calls, result = _run(monkeypatch, duration=0.25, step=0.25)
    assert calls

    def forbidden(*args, **kwargs):
        pytest.fail("deadline-stopped trajectory called its solver")

    result = trajectory.run_terminal_inventory_control_trajectory(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        "state-0",
        SimpleNamespace(),
        SimpleNamespace(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=np.zeros(2),
        level_setpoints=SimpleNamespace(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(3),
        product_reference_lbmolph=(10.0, 20.0),
        step_seconds=0.25,
        duration_seconds=0.25,
        settings=SimpleNamespace(),
        name="deadline",
        step_solver=forbidden,
        deadline_monotonic=0.0,
    )

    assert not result.completed
    assert result.completed_steps == 0
    assert result.stop_reason == "deadline"


@pytest.mark.parametrize(("duration", "step"), [(0.0, 0.25), (1.0, 0.0), (1.0, 0.3)])
def test_trajectory_rejects_invalid_time_grid(monkeypatch, duration, step):
    with pytest.raises(ValueError):
        _run(monkeypatch, duration=duration, step=step)
