from types import SimpleNamespace

import numpy as np
import pytest

from dynamic_distillation.core_v3.captured_modified_newton_v1 import (
    solve_captured_modified_newton,
)
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings


SETTINGS = ModifiedNewtonSettings(
    residual_tolerance=1.0e-8,
    max_iterations=4,
    line_search_fractions=(1.0, 0.5, 0.25, 0.125),
    armijo_fraction=1.0e-4,
    condition_limit=1.0e8,
)


def _linear_objective(point, _state_id):
    values = np.asarray(point, dtype=float)
    return SimpleNamespace(scaled=values.copy(), solve_coordinates=values.copy())


def test_captured_solver_records_success_identity():
    result = solve_captured_modified_newton(
        _linear_objective,
        lambda _point, _state_id: np.eye(2),
        [1.0, -2.0],
        SETTINGS,
        name="success",
    )

    assert result.success
    assert result.message == "captured modified Newton converged"
    assert result.iterations == 1
    assert result.jacobian_evaluations == 1
    assert result.linear_solves == 1
    assert result.accepted_steps == 1
    assert result.final_residual_inf_norm == 0.0
    assert result.final_residual_vs_evaluation_max_abs == 0.0
    assert result.final_coordinates_vs_evaluation_max_abs == 0.0
    capture = result.iteration_captures[0]
    assert len(capture.trials) == 1
    assert capture.trials[0].armijo_accepted
    assert capture.trials[0].state_id == "success:iteration_1:line_0"


def test_captured_solver_records_complete_line_search_failure():
    result = solve_captured_modified_newton(
        _linear_objective,
        lambda _point, _state_id: np.asarray([[-1.0]]),
        [1.0],
        SETTINGS,
        name="failure",
    )

    assert not result.success
    assert result.message == "line search failed with frozen Jacobian"
    assert result.iterations == 1
    assert result.residual_evaluations == 5
    assert result.rejected_line_search_steps == 4
    assert result.final_residual_inf_norm == 1.0
    capture = result.iteration_captures[0]
    assert np.array_equal(capture.coordinates_before, [1.0])
    assert np.array_equal(capture.residual_before, [1.0])
    assert np.array_equal(capture.correction, [1.0])
    assert [trial.fraction for trial in capture.trials] == [1.0, 0.5, 0.25, 0.125]
    assert [trial.residual_inf_norm for trial in capture.trials] == [2.0, 1.5, 1.25, 1.125]
    assert not any(trial.armijo_accepted for trial in capture.trials)


def test_captured_solver_copies_shared_buffers_and_detects_aliasing():
    shared_residual = np.zeros(1)
    shared_evaluation = SimpleNamespace(
        scaled=shared_residual,
        solve_coordinates=np.zeros(1),
    )

    def objective(point, _state_id):
        shared_residual[:] = point
        shared_evaluation.solve_coordinates[:] = point
        return shared_evaluation

    result = solve_captured_modified_newton(
        objective,
        lambda _point, _state_id: np.asarray([[-1.0]]),
        [1.0],
        SETTINGS,
        name="alias",
    )

    assert np.array_equal(result.initial_residual, [1.0])
    assert np.array_equal(result.final_residual, [1.0])
    assert np.array_equal(
        [trial.residual[0] for trial in result.iteration_captures[0].trials],
        [2.0, 1.5, 1.25, 1.125],
    )
    assert np.isclose(result.final_residual_vs_evaluation_max_abs, 0.125)
    assert np.isclose(result.final_coordinates_vs_evaluation_max_abs, 0.125)
    with pytest.raises(ValueError):
        result.final_residual[0] = 99.0


def test_captured_solver_records_bound_rejections_without_evaluation():
    def boundary_objective(point, _state_id):
        values = np.asarray(point, dtype=float)
        return SimpleNamespace(
            scaled=values - 0.75,
            solve_coordinates=values.copy(),
        )

    result = solve_captured_modified_newton(
        boundary_objective,
        lambda _point, _state_id: np.asarray([[0.25]]),
        [1.0],
        SETTINGS,
        lower_bounds=[0.75],
        upper_bounds=[2.0],
        name="bounds",
    )

    assert result.success
    assert result.rejected_bound_steps == 2
    trials = result.iteration_captures[0].trials
    assert [trial.within_bounds for trial in trials] == [False, False, True]
    assert trials[0].state_id is None and trials[0].residual is None
    assert trials[1].state_id is None and trials[1].residual is None
    assert trials[2].armijo_accepted


def test_captured_solver_preserves_rank_failure_evidence():
    result = solve_captured_modified_newton(
        _linear_objective,
        lambda _point, _state_id: np.zeros((2, 2)),
        [1.0, 1.0],
        SETTINGS,
        name="rank",
    )

    assert not result.success
    assert result.message == "frozen Jacobian failed rank or condition gate"
    assert result.jacobian_rank == 0
    assert np.isinf(result.jacobian_condition)
    assert result.iteration_captures == ()
    assert result.final_residual_vs_evaluation_max_abs == 0.0
