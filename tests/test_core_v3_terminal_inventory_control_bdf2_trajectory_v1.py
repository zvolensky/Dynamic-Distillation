from types import SimpleNamespace

import numpy as np
import pytest

import dynamic_distillation.core_v3.terminal_inventory_control_bdf2_trajectory_v1 as trajectory


def _evaluation(value, *, bdf2=False):
    inventory = np.full((2, 2), value, dtype=float)
    common = dict(
        control_evaluation=SimpleNamespace(
            base=SimpleNamespace(physical_state=object())
        )
    )
    if bdf2:
        return SimpleNamespace(
            **common,
            kinematics=SimpleNamespace(
                endpoint_inventory_lbmol=inventory,
                endpoint_internal_energy_BTU=np.asarray((value, value)),
                endpoint_controller_memory=np.asarray((value, value)),
            ),
        )
    return SimpleNamespace(
        **common,
        endpoint_inventory_lbmol=inventory,
        previous_internal_energy_BTU=np.asarray((value - 1.0, value - 1.0)),
        endpoint_internal_energy_BTU=np.asarray((value, value)),
        endpoint_controller_memory=np.asarray((value, value)),
    )


def test_dd199_trajectory_uses_one_be_startup_then_bdf2(monkeypatch):
    calls = []

    def fake_be(*args, **kwargs):
        calls.append(("be", kwargs["step_seconds"]))
        return SimpleNamespace(
            success=True, evaluation=_evaluation(2.0), final_coordinates=np.zeros(4)
        )

    def fake_bdf2(*args, **kwargs):
        calls.append(("bdf2", kwargs["history"].current_inventory_lbmol.copy()))
        value = 2.0 + sum(kind == "bdf2" for kind, _detail in calls)
        return SimpleNamespace(
            success=True,
            evaluation=_evaluation(value, bdf2=True),
            final_coordinates=np.zeros(4),
        )

    monkeypatch.setattr(
        trajectory, "solve_terminal_inventory_control_backward_euler_step", fake_be
    )
    monkeypatch.setattr(
        trajectory, "solve_terminal_inventory_control_bdf2_step", fake_bdf2
    )
    monkeypatch.setattr(
        trajectory, "component_rate_scales", lambda *args: np.ones((2, 2))
    )

    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        SimpleNamespace(base=object()),
        object(),
        object(),
        object(),
        object(),
        object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        duration_seconds=0.5,
        step_seconds=0.125,
        settings=object(),
        name="dd199_test",
    )

    assert result.completed
    assert result.stop_reason is None
    assert result.duration_seconds == 0.5
    assert result.endpoint_outcome is result.records[-1].outcome
    assert [record.method for record in result.records] == [
        "backward_euler",
        "bdf2",
        "bdf2",
        "bdf2",
    ]
    assert calls[0] == ("be", 0.125)


def test_dd199_trajectory_rejects_nonintegral_or_single_step_duration():
    common = dict(
        contract=object(),
        spec=object(),
        reference=object(),
        initial_template=object(),
        provider=object(),
        call_audit=object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        settings=object(),
        name="bad",
    )
    for duration, step in ((0.1, 0.1), (0.3, 0.2)):
        try:
            trajectory.run_terminal_inventory_control_bdf2_trajectory(
                **common, duration_seconds=duration, step_seconds=step
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid BDF2 trajectory grid was accepted")


def test_dd203_trajectory_accepts_explicit_startup_and_bdf2_solvers(monkeypatch):
    calls = []

    def startup(*args, **kwargs):
        calls.append(("startup", kwargs["name"]))
        return SimpleNamespace(
            success=True,
            evaluation=_evaluation(2.0),
            final_coordinates=np.zeros(4),
        )

    def bdf2(*args, **kwargs):
        calls.append(("bdf2", kwargs["name"]))
        return SimpleNamespace(
            success=True,
            evaluation=_evaluation(3.0, bdf2=True),
            final_coordinates=np.zeros(4),
        )

    monkeypatch.setattr(
        trajectory,
        "solve_terminal_inventory_control_backward_euler_step",
        lambda *args, **kwargs: pytest.fail("default startup solver was called"),
    )
    monkeypatch.setattr(
        trajectory,
        "solve_terminal_inventory_control_bdf2_step",
        lambda *args, **kwargs: pytest.fail("default BDF2 solver was called"),
    )
    monkeypatch.setattr(
        trajectory, "component_rate_scales", lambda *args: np.ones((2, 2))
    )

    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        SimpleNamespace(base=object()),
        object(),
        object(),
        object(),
        object(),
        object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        duration_seconds=0.375,
        step_seconds=0.125,
        settings=object(),
        name="dd203_test",
        startup_step_solver=startup,
        bdf2_step_solver=bdf2,
    )

    assert result.completed
    assert calls == [
        ("startup", "dd203_test:startup"),
        ("bdf2", "dd203_test:bdf2_2"),
        ("bdf2", "dd203_test:bdf2_3"),
    ]


def test_dd203_trajectory_stops_before_startup_after_deadline():
    def forbidden(*args, **kwargs):
        pytest.fail("deadline-stopped BDF2 trajectory called a solver")

    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        object(),
        object(),
        object(),
        object(),
        object(),
        object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        duration_seconds=0.25,
        step_seconds=0.125,
        settings=object(),
        name="deadline",
        startup_step_solver=forbidden,
        bdf2_step_solver=forbidden,
        deadline_monotonic=0.0,
    )

    assert not result.completed
    assert result.completed_steps == 0
    assert result.stop_reason == "deadline"
    with pytest.raises(RuntimeError, match="has no endpoint"):
        _ = result.endpoint_outcome


def test_dd203_trajectory_reports_startup_root_failure():
    failed = SimpleNamespace(success=False)

    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        object(),
        object(),
        object(),
        object(),
        object(),
        object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        duration_seconds=0.25,
        step_seconds=0.125,
        settings=object(),
        name="failure",
        startup_step_solver=lambda *args, **kwargs: failed,
    )

    assert not result.completed
    assert result.completed_steps == 1
    assert result.stop_reason == "root_failure"


def test_dd203_trajectory_stops_between_startup_and_bdf2_after_deadline(
    monkeypatch,
):
    clock = iter((0.0, 2.0))
    monkeypatch.setattr(trajectory.time, "perf_counter", lambda: next(clock))

    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        SimpleNamespace(base=object()),
        object(),
        object(),
        object(),
        object(),
        object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        duration_seconds=0.25,
        step_seconds=0.125,
        settings=object(),
        name="deadline_after_startup",
        startup_step_solver=lambda *args, **kwargs: SimpleNamespace(
            success=True,
            evaluation=_evaluation(2.0),
            final_coordinates=np.zeros(4),
        ),
        bdf2_step_solver=lambda *args, **kwargs: pytest.fail(
            "deadline-stopped trajectory called the BDF2 solver"
        ),
        deadline_monotonic=1.0,
    )

    assert not result.completed
    assert result.completed_steps == 1
    assert result.stop_reason == "deadline"
    assert result.records[0].method == "backward_euler"


def test_dd203_trajectory_reports_bdf2_root_failure(monkeypatch):
    monkeypatch.setattr(
        trajectory, "component_rate_scales", lambda *args: np.ones((2, 2))
    )

    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        SimpleNamespace(base=object()),
        object(),
        object(),
        object(),
        object(),
        object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        duration_seconds=0.25,
        step_seconds=0.125,
        settings=object(),
        name="bdf2_failure",
        startup_step_solver=lambda *args, **kwargs: SimpleNamespace(
            success=True,
            evaluation=_evaluation(2.0),
            final_coordinates=np.zeros(4),
        ),
        bdf2_step_solver=lambda *args, **kwargs: SimpleNamespace(success=False),
    )

    assert not result.completed
    assert result.completed_steps == 2
    assert result.stop_reason == "root_failure"
    assert result.records[-1].method == "bdf2"


def test_production_step_solver_backend_routes_both_methods(monkeypatch):
    calls = []

    class Backend:
        def startup_step_solver(self, *args, **kwargs):
            calls.append(("backward_euler", kwargs["name"]))
            return SimpleNamespace(
                success=True,
                evaluation=_evaluation(2.0),
                final_coordinates=np.zeros(4),
            )

        def bdf2_step_solver(self, *args, **kwargs):
            calls.append(("bdf2", kwargs["name"]))
            return SimpleNamespace(
                success=True,
                evaluation=_evaluation(3.0, bdf2=True),
                final_coordinates=np.zeros(4),
            )

    monkeypatch.setattr(
        trajectory, "component_rate_scales", lambda *args: np.ones((2, 2))
    )
    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        SimpleNamespace(base=object()),
        object(),
        object(),
        object(),
        object(),
        object(),
        initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0),
        level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4),
        fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0),
        duration_seconds=0.25,
        step_seconds=0.125,
        settings=object(),
        name="production_backend",
        step_solver_backend=Backend(),
    )

    assert result.completed
    assert [kind for kind, _name in calls] == ["backward_euler", "bdf2"]
    assert calls[0][1] == "production_backend:startup"
    assert calls[1][1] == "production_backend:bdf2_2"


def test_production_step_solver_backend_rejects_individual_override():
    with pytest.raises(ValueError, match="cannot combine"):
        trajectory.run_terminal_inventory_control_bdf2_trajectory(
            object(),
            object(),
            object(),
            object(),
            object(),
            object(),
            initial_inventory_lbmol=np.ones((2, 2)),
            initial_controller_memory=(0.0, 0.0),
            level_setpoints=object(),
            initial_solve_coordinates=np.zeros(4),
            fixed_steady_scales=np.ones(2),
            product_reference_lbmolph=(1.0, 1.0),
            duration_seconds=0.25,
            step_seconds=0.125,
            settings=object(),
            name="invalid_backend",
            step_solver_backend=object(),
            startup_step_solver=lambda *args, **kwargs: None,
        )
