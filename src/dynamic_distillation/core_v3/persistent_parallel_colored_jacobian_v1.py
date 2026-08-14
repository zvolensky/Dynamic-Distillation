"""Persistent-worker coordination for deterministic colored Jacobians."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .parallel_colored_jacobian_v1 import (
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


@dataclass(frozen=True)
class PersistentParallelJacobianEvidence:
    method: str
    root_epoch: str
    state_id: str
    color_count: int
    task_count: int
    worker_ids: tuple[int, ...]
    basis_rebuilds: int
    logical_provider_calls: int
    provider_pass: bool
    fallback_attempted: bool


class PersistentParallelColoredJacobian:
    """Build colored Jacobians while a caller-owned worker pool stays alive."""

    def __init__(
        self,
        executor: Any,
        worker_evaluator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        *,
        pattern: Sequence[Sequence[bool]],
        step: float,
        worker_count: int,
        require_all_workers: bool = True,
    ) -> None:
        structure = np.asarray(pattern, dtype=bool)
        if structure.ndim != 2:
            raise ValueError("parallel Jacobian pattern must be a matrix")
        if not np.isfinite(step) or step <= 0.0:
            raise ValueError("parallel Jacobian step must be positive")
        if int(worker_count) <= 0:
            raise ValueError("parallel Jacobian worker count must be positive")
        self._executor = executor
        self._worker_evaluator = worker_evaluator
        self._pattern = structure.copy()
        self._step = float(step)
        self._worker_count = int(worker_count)
        self._require_all_workers = bool(require_all_workers)
        self._seen_roots: set[str] = set()
        self._evidence: list[PersistentParallelJacobianEvidence] = []

    @property
    def evidence(self) -> tuple[PersistentParallelJacobianEvidence, ...]:
        return tuple(self._evidence)

    @property
    def root_count(self) -> int:
        return len(self._seen_roots)

    @property
    def logical_provider_calls(self) -> int:
        return int(sum(item.logical_provider_calls for item in self._evidence))

    def build(
        self,
        point: Sequence[float],
        state_id: str,
        *,
        method: str,
        root_epoch: str,
        work_basis: Mapping[str, Any],
    ) -> np.ndarray:
        method_name = str(method)
        epoch = str(root_epoch)
        tasks, groups = build_colored_central_difference_tasks(
            point,
            pattern=self._pattern,
            step=self._step,
            state_id=str(state_id),
        )
        work = [
            {
                "task": task,
                "method": method_name,
                "root_epoch": epoch,
                **dict(work_basis),
            }
            for task in tasks
        ]
        raw = list(self._executor.map(self._worker_evaluator, work, chunksize=1))
        if len(raw) != len(tasks):
            raise RuntimeError("parallel Jacobian worker result count is incomplete")
        if any(str(item.get("method")) != method_name for item in raw):
            raise RuntimeError("parallel Jacobian worker method is inconsistent")
        if any(str(item.get("root_epoch")) != epoch for item in raw):
            raise RuntimeError("parallel Jacobian worker root epoch is inconsistent")
        worker_ids = tuple(sorted({int(item["process_id"]) for item in raw}))
        if self._require_all_workers and len(worker_ids) != self._worker_count:
            raise RuntimeError("parallel Jacobian did not use every configured worker")
        rebuilds = int(sum(bool(item["basis_rebuilt"]) for item in raw))
        expected_rebuilds = 0 if epoch in self._seen_roots else self._worker_count
        if rebuilds != expected_rebuilds:
            raise RuntimeError(
                "parallel Jacobian worker basis rebuild count is inconsistent"
            )
        provider_pass = all(bool(item["provider_pass"]) for item in raw)
        fallback_attempted = any(bool(item["fallback_attempted"]) for item in raw)
        if not provider_pass or fallback_attempted:
            raise RuntimeError("parallel Jacobian provider ownership failed")
        matrix = assemble_colored_central_difference_jacobian(
            tasks,
            [
                ColoredCentralDifferenceResult(
                    order=int(item["order"]),
                    residual=tuple(float(value) for value in item["residual"]),
                )
                for item in raw
            ],
            pattern=self._pattern,
            step=self._step,
        )
        self._seen_roots.add(epoch)
        self._evidence.append(
            PersistentParallelJacobianEvidence(
                method=method_name,
                root_epoch=epoch,
                state_id=str(state_id),
                color_count=len(groups),
                task_count=len(raw),
                worker_ids=worker_ids,
                basis_rebuilds=rebuilds,
                logical_provider_calls=int(
                    sum(int(item["logical_provider_calls"]) for item in raw)
                ),
                provider_pass=provider_pass,
                fallback_attempted=fallback_attempted,
            )
        )
        return matrix


__all__ = [
    "PersistentParallelColoredJacobian",
    "PersistentParallelJacobianEvidence",
]
