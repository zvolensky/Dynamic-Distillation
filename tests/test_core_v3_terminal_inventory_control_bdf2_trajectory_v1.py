from types import SimpleNamespace

import numpy as np

import dynamic_distillation.core_v3.terminal_inventory_control_bdf2_trajectory_v1 as trajectory


def _evaluation(value, *, bdf2=False):
    inventory = np.full((2, 2), value, dtype=float)
    common = dict(
        control_evaluation=SimpleNamespace(base=SimpleNamespace(physical_state=object()))
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
        return SimpleNamespace(success=True, evaluation=_evaluation(2.0), final_coordinates=np.zeros(4))

    def fake_bdf2(*args, **kwargs):
        calls.append(("bdf2", kwargs["history"].current_inventory_lbmol.copy()))
        value = 2.0 + sum(kind == "bdf2" for kind, _detail in calls)
        return SimpleNamespace(success=True, evaluation=_evaluation(value, bdf2=True), final_coordinates=np.zeros(4))

    monkeypatch.setattr(trajectory, "solve_terminal_inventory_control_backward_euler_step", fake_be)
    monkeypatch.setattr(trajectory, "solve_terminal_inventory_control_bdf2_step", fake_bdf2)
    monkeypatch.setattr(trajectory, "component_rate_scales", lambda *args: np.ones((2, 2)))

    result = trajectory.run_terminal_inventory_control_bdf2_trajectory(
        SimpleNamespace(base=object()), object(), object(), object(), object(), object(),
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
    assert [record.method for record in result.records] == ["backward_euler", "bdf2", "bdf2", "bdf2"]
    assert calls[0] == ("be", 0.125)


def test_dd199_trajectory_rejects_nonintegral_or_single_step_duration():
    common = dict(
        contract=object(), spec=object(), reference=object(), initial_template=object(),
        provider=object(), call_audit=object(), initial_inventory_lbmol=np.ones((2, 2)),
        initial_controller_memory=(0.0, 0.0), level_setpoints=object(),
        initial_solve_coordinates=np.zeros(4), fixed_steady_scales=np.ones(2),
        product_reference_lbmolph=(1.0, 1.0), settings=object(), name="bad",
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
