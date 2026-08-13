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


@pytest.mark.parametrize(("duration", "step"), [(0.0, 0.25), (1.0, 0.0), (1.0, 0.3)])
def test_trajectory_rejects_invalid_time_grid(monkeypatch, duration, step):
    with pytest.raises(ValueError):
        _run(monkeypatch, duration=duration, step=step)
