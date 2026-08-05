from dataclasses import dataclass

import numpy as np

from dynamic_distillation.core_v3.modified_newton_v1 import (
    ModifiedNewtonSettings,
    solve_modified_newton,
)


@dataclass(frozen=True)
class Evaluation:
    scaled: np.ndarray


def test_modified_newton_solves_linear_system_with_one_jacobian():
    matrix = np.asarray(((4.0, 1.0), (1.0, 3.0)))
    target = np.asarray((1.0, 2.0))
    counts = {"residual": 0, "jacobian": 0}

    def objective(point, _state_id):
        counts["residual"] += 1
        return Evaluation(matrix @ point - target)

    def jacobian(_point, _state_id):
        counts["jacobian"] += 1
        return matrix

    outcome = solve_modified_newton(
        objective,
        jacobian,
        np.zeros(2),
        ModifiedNewtonSettings(),
        name="linear",
    )

    assert outcome.success
    assert np.allclose(outcome.final_coordinates, np.linalg.solve(matrix, target))
    assert outcome.jacobian_evaluations == counts["jacobian"] == 1
    assert outcome.residual_evaluations == counts["residual"] == 2
    assert outcome.linear_solves == 1


def test_modified_newton_reuses_factorization_for_mild_nonlinearity():
    counts = {"jacobian": 0}

    def objective(point, _state_id):
        return Evaluation(np.asarray((point[0] + 0.05 * point[0] ** 2 - 1.0,)))

    def jacobian(point, _state_id):
        counts["jacobian"] += 1
        return np.asarray(((1.0 + 0.1 * point[0],),))

    outcome = solve_modified_newton(
        objective,
        jacobian,
        (0.0,),
        ModifiedNewtonSettings(max_iterations=8),
        name="nonlinear",
    )

    assert outcome.success
    assert outcome.iterations > 1
    assert outcome.jacobian_evaluations == counts["jacobian"] == 1
    assert outcome.final_residual_inf_norm < 1.0e-8


def test_modified_newton_rejects_bound_violations_without_clipping():
    visited = []

    def objective(point, _state_id):
        visited.append(float(point[0]))
        return Evaluation(np.asarray((point[0] - 0.8,)))

    outcome = solve_modified_newton(
        objective,
        lambda _point, _state_id: np.asarray(((0.1,),)),
        (0.0,),
        ModifiedNewtonSettings(max_iterations=3),
        lower_bounds=(-1.0,),
        upper_bounds=(1.0,),
        name="bounds",
    )

    assert outcome.rejected_bound_steps > 0
    assert all(-1.0 <= value <= 1.0 for value in visited)
    assert not any(np.isclose(value, candidate) for value in visited for candidate in (2.0, 4.0, 8.0))


def test_modified_newton_stops_on_singular_frozen_jacobian():
    outcome = solve_modified_newton(
        lambda point, _state_id: Evaluation(point - 1.0),
        lambda _point, _state_id: np.zeros((2, 2)),
        np.zeros(2),
        ModifiedNewtonSettings(),
        name="singular",
    )

    assert not outcome.success
    assert outcome.jacobian_rank == 0
    assert outcome.linear_solves == 0
    assert outcome.residual_evaluations == 1


def test_modified_newton_returns_without_jacobian_at_an_existing_root():
    outcome = solve_modified_newton(
        lambda point, _state_id: Evaluation(point.copy()),
        lambda _point, _state_id: (_ for _ in ()).throw(AssertionError()),
        np.zeros(2),
        ModifiedNewtonSettings(),
        name="root",
    )

    assert outcome.success
    assert outcome.jacobian_evaluations == 0
    assert outcome.iterations == 0
