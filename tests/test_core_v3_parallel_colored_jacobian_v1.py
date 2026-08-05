import numpy as np
import pytest

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
