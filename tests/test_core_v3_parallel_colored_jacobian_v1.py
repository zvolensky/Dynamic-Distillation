import numpy as np
import pytest

from dynamic_distillation.core_v3.captured_modified_newton_v1 import (
    solve_captured_modified_newton,
)
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


def _fixture():
    matrix = np.asarray(
        (
            (2.0, 0.0, -1.0, 0.0),
            (0.0, 3.0, 0.0, 4.0),
            (5.0, 0.0, 6.0, 0.0),
            (0.0, -2.0, 0.0, 7.0),
        )
    )
    point = np.asarray((0.2, -0.3, 0.4, 0.7))
    return matrix, point, matrix != 0.0


def test_parallel_colored_tasks_assemble_linear_jacobian_in_any_result_order():
    matrix, point, pattern = _fixture()
    tasks, groups = build_colored_central_difference_tasks(
        point,
        pattern=pattern,
        step=1.0e-5,
        state_id="fixture",
    )
    results = [
        ColoredCentralDifferenceResult(
            order=task.order,
            residual=tuple(matrix @ np.asarray(task.coordinates)),
        )
        for task in reversed(tasks)
    ]
    assembled = assemble_colored_central_difference_jacobian(
        tasks,
        results,
        pattern=pattern,
        step=1.0e-5,
    )
    assert len(groups) == 2
    assert [task.sign for task in tasks] == [1, -1, 1, -1]
    assert np.allclose(assembled, matrix, atol=1.0e-10, rtol=0.0)


def test_parallel_colored_assembly_rejects_missing_result():
    matrix, point, pattern = _fixture()
    tasks, _groups = build_colored_central_difference_tasks(
        point,
        pattern=pattern,
        step=1.0e-5,
        state_id="fixture",
    )
    results = [
        ColoredCentralDifferenceResult(
            order=task.order,
            residual=tuple(matrix @ np.asarray(task.coordinates)),
        )
        for task in tasks[:-1]
    ]
    with pytest.raises(ValueError, match="count is incomplete"):
        assemble_colored_central_difference_jacobian(
            tasks,
            results,
            pattern=pattern,
            step=1.0e-5,
        )


def test_parallel_colored_tasks_validate_step_and_shape():
    _matrix, point, pattern = _fixture()
    with pytest.raises(ValueError, match="positive"):
        build_colored_central_difference_tasks(
            point,
            pattern=pattern,
            step=0.0,
            state_id="fixture",
        )
    with pytest.raises(ValueError, match="does not match"):
        build_colored_central_difference_tasks(
            point,
            pattern=np.ones((4, 3), dtype=bool),
            step=1.0e-5,
            state_id="fixture",
        )


def test_parallel_assembly_is_captured_solver_equivalent():
    matrix = np.asarray(((3.0, 1.0), (1.0, 2.0)))
    target = np.asarray((1.0, -0.5))
    pattern = matrix != 0.0

    class Evaluation:
        def __init__(self, point):
            self.solve_coordinates = np.asarray(point, dtype=float)
            self.scaled = matrix @ self.solve_coordinates - target

    def objective(point, _state_id):
        return Evaluation(point)

    def parallel_builder(point, state_id):
        tasks, _groups = build_colored_central_difference_tasks(
            point,
            pattern=pattern,
            step=1.0e-5,
            state_id=state_id,
        )
        results = [
            ColoredCentralDifferenceResult(
                order=task.order,
                residual=tuple(objective(task.coordinates, task.state_id).scaled),
            )
            for task in reversed(tasks)
        ]
        return assemble_colored_central_difference_jacobian(
            tasks,
            results,
            pattern=pattern,
            step=1.0e-5,
        )

    def serial_builder(point, state_id):
        assembled, _groups = colored_central_difference_jacobian(
            lambda trial, trial_id: objective(trial, trial_id).scaled,
            point,
            pattern=pattern,
            step=1.0e-5,
            state_id=state_id,
        )
        return assembled

    settings = ModifiedNewtonSettings(
        residual_tolerance=1.0e-12,
        max_iterations=3,
        line_search_fractions=(1.0, 0.5, 0.25, 0.125),
        armijo_fraction=1.0e-4,
        condition_limit=1.0e8,
    )
    serial = solve_captured_modified_newton(
        objective,
        serial_builder,
        (0.0, 0.0),
        settings,
        name="serial",
    )
    parallel = solve_captured_modified_newton(
        objective,
        parallel_builder,
        (0.0, 0.0),
        settings,
        name="parallel",
    )
    assert serial.success and parallel.success
    assert np.array_equal(serial.frozen_jacobian, parallel.frozen_jacobian)
    assert np.array_equal(serial.final_coordinates, parallel.final_coordinates)
    assert np.array_equal(serial.final_residual, parallel.final_residual)
