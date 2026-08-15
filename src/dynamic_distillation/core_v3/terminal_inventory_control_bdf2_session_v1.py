"""Reusable worker-session lifecycle for production controlled BDF2 runs."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Sequence

import numpy as np

from .persistent_parallel_colored_jacobian_v1 import (
    PersistentParallelColoredJacobian,
)
from .terminal_inventory_control_bdf2_parallel_v1 import (
    TerminalInventoryControlBDF2ParallelStepSolvers,
)
from .terminal_inventory_control_bdf2_trajectory_v1 import (
    run_terminal_inventory_control_bdf2_trajectory,
)


@dataclass(frozen=True)
class ProductionSessionSegmentEvidence:
    name: str
    wall_seconds: float
    completed_without_exception: bool


@dataclass(frozen=True)
class ProductionSessionTiming:
    startup_wall_seconds: float
    trajectory_wall_seconds: float
    shutdown_wall_seconds: float | None
    total_wall_seconds: float | None


class TerminalInventoryControlBDF2ProductionSession:
    """Keep one qualified parallel backend alive across trajectory segments."""

    def __init__(
        self,
        executor_builder: Callable[[], Any],
        worker_evaluator: Callable[[Any], Any],
        *,
        pattern: Sequence[Sequence[bool]],
        step: float,
        worker_count: int,
        startup_probe: Callable[..., int] | None = None,
        startup_probe_args: Sequence[Any] = (),
        require_all_workers: bool = True,
        require_all_startup_workers: bool = False,
    ) -> None:
        structure = np.asarray(pattern, dtype=bool)
        if structure.ndim != 2:
            raise ValueError("production session Jacobian pattern must be a matrix")
        if not np.isfinite(step) or float(step) <= 0.0:
            raise ValueError("production session Jacobian step must be positive")
        if int(worker_count) <= 0:
            raise ValueError("production session worker count must be positive")
        if not callable(executor_builder) or not callable(worker_evaluator):
            raise TypeError(
                "production session executor and evaluator must be callable"
            )
        if startup_probe is not None and not callable(startup_probe):
            raise TypeError("production session startup probe must be callable")

        self._executor_builder = executor_builder
        self._worker_evaluator = worker_evaluator
        self._pattern = structure.copy()
        self._step = float(step)
        self._worker_count = int(worker_count)
        self._startup_probe = startup_probe
        self._startup_probe_args = tuple(startup_probe_args)
        self._require_all_workers = bool(require_all_workers)
        self._require_all_startup_workers = bool(require_all_startup_workers)

        self._state = "new"
        self._executor: Any | None = None
        self._jacobians: PersistentParallelColoredJacobian | None = None
        self._backend: TerminalInventoryControlBDF2ParallelStepSolvers | None = None
        self._startup_process_ids: tuple[int, ...] = ()
        self._startup_wall_seconds = 0.0
        self._shutdown_wall_seconds: float | None = None
        self._session_started: float | None = None
        self._total_wall_seconds: float | None = None
        self._used_trajectory_names: set[str] = set()
        self._segments: list[ProductionSessionSegmentEvidence] = []

    @property
    def state(self) -> str:
        return self._state

    @property
    def startup_process_ids(self) -> tuple[int, ...]:
        return self._startup_process_ids

    @property
    def segments(self) -> tuple[ProductionSessionSegmentEvidence, ...]:
        return tuple(self._segments)

    @property
    def jacobians(self) -> PersistentParallelColoredJacobian:
        if self._state != "started" or self._jacobians is None:
            raise RuntimeError("production session has not started")
        return self._jacobians

    @property
    def backend(self) -> TerminalInventoryControlBDF2ParallelStepSolvers:
        if self._state != "started" or self._backend is None:
            raise RuntimeError("production session has not started")
        return self._backend

    @property
    def timing(self) -> ProductionSessionTiming:
        return ProductionSessionTiming(
            startup_wall_seconds=float(self._startup_wall_seconds),
            trajectory_wall_seconds=float(
                sum(item.wall_seconds for item in self._segments)
            ),
            shutdown_wall_seconds=self._shutdown_wall_seconds,
            total_wall_seconds=self._total_wall_seconds,
        )

    def start(self) -> TerminalInventoryControlBDF2ProductionSession:
        if self._state == "started":
            return self
        if self._state == "closed":
            raise RuntimeError("closed production session cannot be restarted")

        self._session_started = time.perf_counter()
        startup_started = time.perf_counter()
        executor = self._executor_builder()
        self._executor = executor
        try:
            if self._startup_probe is not None:
                futures = [
                    executor.submit(self._startup_probe, *self._startup_probe_args)
                    for _ in range(self._worker_count)
                ]
                process_ids = tuple(
                    sorted({int(future.result()) for future in futures})
                )
                if (
                    self._require_all_startup_workers
                    and len(process_ids) != self._worker_count
                ):
                    raise RuntimeError(
                        "production session startup did not reach every worker"
                    )
                self._startup_process_ids = process_ids
            self._jacobians = PersistentParallelColoredJacobian(
                executor,
                self._worker_evaluator,
                pattern=self._pattern,
                step=self._step,
                worker_count=self._worker_count,
                require_all_workers=self._require_all_workers,
            )
            self._backend = TerminalInventoryControlBDF2ParallelStepSolvers(
                self._jacobians
            )
            self._startup_wall_seconds = time.perf_counter() - startup_started
            self._state = "started"
            return self
        except BaseException:
            shutdown_started = time.perf_counter()
            executor.shutdown(wait=True, cancel_futures=True)
            self._shutdown_wall_seconds = time.perf_counter() - shutdown_started
            self._total_wall_seconds = time.perf_counter() - self._session_started
            self._state = "closed"
            raise

    def run_trajectory(self, **kwargs: Any) -> Any:
        if self._state != "started":
            raise RuntimeError("production session must be started before use")
        if "step_solver_backend" in kwargs:
            raise ValueError("production session owns the step solver backend")
        name = str(kwargs.get("name", "")).strip()
        if not name:
            raise ValueError("production session trajectory name is required")
        if name in self._used_trajectory_names:
            raise ValueError("production session trajectory name must be unique")

        self._used_trajectory_names.add(name)
        started = time.perf_counter()
        completed = False
        try:
            result = run_terminal_inventory_control_bdf2_trajectory(
                **kwargs,
                step_solver_backend=self.backend,
            )
            completed = True
            return result
        finally:
            self._segments.append(
                ProductionSessionSegmentEvidence(
                    name=name,
                    wall_seconds=time.perf_counter() - started,
                    completed_without_exception=completed,
                )
            )

    def close(self) -> None:
        if self._state == "closed":
            return
        if self._state == "new":
            self._state = "closed"
            self._shutdown_wall_seconds = 0.0
            self._total_wall_seconds = 0.0
            return

        shutdown_started = time.perf_counter()
        try:
            assert self._executor is not None
            self._executor.shutdown(wait=True, cancel_futures=True)
        finally:
            self._shutdown_wall_seconds = time.perf_counter() - shutdown_started
            assert self._session_started is not None
            self._total_wall_seconds = time.perf_counter() - self._session_started
            self._state = "closed"

    def __enter__(self) -> TerminalInventoryControlBDF2ProductionSession:
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False


__all__ = [
    "ProductionSessionSegmentEvidence",
    "ProductionSessionTiming",
    "TerminalInventoryControlBDF2ProductionSession",
]
