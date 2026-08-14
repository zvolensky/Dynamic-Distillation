import numpy as np
import pytest

from dynamic_distillation.core_v3.persistent_parallel_colored_jacobian_v1 import (
    PersistentParallelColoredJacobian,
)


class _InlineExecutor:
    def map(self, function, work, chunksize=1):
        assert chunksize == 1
        return [function(item) for item in work]


def _worker_evaluator():
    seen: set[tuple[int, str]] = set()

    def evaluate(work):
        task = work["task"]
        worker_id = 100 + int(task.order)
        key = (worker_id, str(work["root_epoch"]))
        rebuilt = key not in seen
        seen.add(key)
        point = np.asarray(task.coordinates)
        return {
            "order": task.order,
            "residual": [point[0] ** 2, point[1] ** 2],
            "process_id": worker_id,
            "method": work["method"],
            "root_epoch": work["root_epoch"],
            "basis_rebuilt": rebuilt,
            "logical_provider_calls": 7,
            "provider_pass": True,
            "fallback_attempted": False,
        }

    return evaluate


def test_persistent_parallel_jacobian_is_exact_and_tracks_root_basis():
    backend = PersistentParallelColoredJacobian(
        _InlineExecutor(),
        _worker_evaluator(),
        pattern=np.eye(2, dtype=bool),
        step=1.0e-5,
        worker_count=2,
    )

    first = backend.build(
        [2.0, 3.0],
        "root:jacobian_1",
        method="bdf2",
        root_epoch="root",
        work_basis={"marker": 1},
    )
    second = backend.build(
        [2.0, 3.0],
        "root:jacobian_2",
        method="bdf2",
        root_epoch="root",
        work_basis={"marker": 1},
    )

    assert np.allclose(first, np.diag((4.0, 6.0)), rtol=0.0, atol=1e-9)
    assert np.array_equal(first, second)
    assert backend.root_count == 1
    assert backend.logical_provider_calls == 28
    assert [item.basis_rebuilds for item in backend.evidence] == [2, 0]
    assert all(item.worker_ids == (100, 101) for item in backend.evidence)


def test_persistent_parallel_jacobian_rejects_missing_worker():
    def one_worker(work):
        task = work["task"]
        point = np.asarray(task.coordinates)
        return {
            "order": task.order,
            "residual": point.tolist(),
            "process_id": 100,
            "method": work["method"],
            "root_epoch": work["root_epoch"],
            "basis_rebuilt": task.order == 0,
            "logical_provider_calls": 1,
            "provider_pass": True,
            "fallback_attempted": False,
        }

    backend = PersistentParallelColoredJacobian(
        _InlineExecutor(),
        one_worker,
        pattern=np.eye(2, dtype=bool),
        step=1.0e-5,
        worker_count=2,
    )

    with pytest.raises(RuntimeError, match="every configured worker"):
        backend.build(
            [1.0, 1.0],
            "root:jacobian",
            method="backward_euler",
            root_epoch="root",
            work_basis={},
        )


def test_persistent_parallel_jacobian_rejects_provider_failure():
    evaluate = _worker_evaluator()

    def failing(work):
        result = evaluate(work)
        result["fallback_attempted"] = True
        return result

    backend = PersistentParallelColoredJacobian(
        _InlineExecutor(),
        failing,
        pattern=np.eye(2, dtype=bool),
        step=1.0e-5,
        worker_count=2,
    )

    with pytest.raises(RuntimeError, match="provider ownership"):
        backend.build(
            [1.0, 1.0],
            "root:jacobian",
            method="bdf2",
            root_epoch="root",
            work_basis={},
        )
