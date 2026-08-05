"""Short controlled-terminal trajectories using one-Jacobian implicit roots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np

from dynamic_distillation.core_v3.modified_newton_v1 import (
    ModifiedNewtonOutcome,
    ModifiedNewtonSettings,
    solve_modified_newton,
)


@dataclass(frozen=True)
class ControlledTerminalTrajectoryStep:
    index: int
    time_seconds: float
    outcome: ModifiedNewtonOutcome


@dataclass(frozen=True)
class ControlledTerminalTrajectoryResult:
    name: str
    step_seconds: float
    duration_seconds: float
    requested_steps: int
    completed_steps: int
    completed: bool
    steps: tuple[ControlledTerminalTrajectoryStep, ...]

    @property
    def endpoint_outcome(self) -> ModifiedNewtonOutcome:
        if not self.steps:
            raise RuntimeError("controlled trajectory has no endpoint")
        return self.steps[-1].outcome


def _step_count(duration_seconds: float, step_seconds: float) -> int:
    if (
        not np.isfinite(duration_seconds)
        or not np.isfinite(step_seconds)
        or duration_seconds <= 0.0
        or step_seconds <= 0.0
    ):
        raise ValueError("trajectory duration and step must be positive")
    count = int(round(float(duration_seconds) / float(step_seconds)))
    if count <= 0 or not np.isclose(
        count * float(step_seconds), float(duration_seconds), atol=1.0e-12
    ):
        raise ValueError("trajectory duration must be an exact step multiple")
    return count


def run_controlled_terminal_trajectory(
    objective_factory: Callable[[np.ndarray, float, np.ndarray, np.ndarray, float], Callable],
    jacobian_factory: Callable[[Callable], Callable],
    *,
    initial_inventory_lbmol: Sequence[Sequence[float]],
    initial_top_internal_energy_BTU: float,
    initial_lower_internal_energy_BTU: Sequence[float],
    initial_controller_memory: Sequence[float],
    initial_coordinates: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    step_seconds: float,
    duration_seconds: float,
    settings: ModifiedNewtonSettings,
    name: str,
) -> ControlledTerminalTrajectoryResult:
    requested = _step_count(duration_seconds, step_seconds)
    inventory = np.asarray(initial_inventory_lbmol, dtype=float).copy()
    top_u = float(initial_top_internal_energy_BTU)
    lower_u = np.asarray(initial_lower_internal_energy_BTU, dtype=float).copy()
    memory = np.asarray(initial_controller_memory, dtype=float).copy()
    coordinates = np.asarray(initial_coordinates, dtype=float).copy()
    lower = np.asarray(lower_bounds, dtype=float)
    upper = np.asarray(upper_bounds, dtype=float)
    if (
        np.any(~np.isfinite(inventory))
        or np.any(inventory <= 0.0)
        or not np.isfinite(top_u)
        or np.any(~np.isfinite(lower_u))
        or np.any(~np.isfinite(memory))
        or coordinates.shape != lower.shape
        or coordinates.shape != upper.shape
    ):
        raise ValueError("controlled trajectory initial state is invalid")

    records: list[ControlledTerminalTrajectoryStep] = []
    for index in range(1, requested + 1):
        objective = objective_factory(
            inventory, top_u, lower_u, memory, float(step_seconds)
        )
        outcome = solve_modified_newton(
            objective,
            jacobian_factory(objective),
            coordinates,
            settings,
            lower_bounds=lower,
            upper_bounds=upper,
            name=f"{name}:step_{index}",
        )
        records.append(
            ControlledTerminalTrajectoryStep(
                index=index,
                time_seconds=float(index) * float(step_seconds),
                outcome=outcome,
            )
        )
        if not outcome.success:
            break
        evaluation = outcome.final_evaluation
        inventory = np.asarray(evaluation.base.endpoint_inventory_lbmol, dtype=float).copy()
        top_u = float(evaluation.base.endpoint_top_internal_energy_BTU)
        lower_u = np.asarray(
            evaluation.base.endpoint_lower_internal_energy_BTU, dtype=float
        ).copy()
        memory = np.asarray(evaluation.endpoint_controller_memory, dtype=float).copy()
        coordinates = np.asarray(outcome.final_coordinates, dtype=float).copy()

    completed = len(records) == requested and all(
        record.outcome.success for record in records
    )
    return ControlledTerminalTrajectoryResult(
        name=str(name),
        step_seconds=float(step_seconds),
        duration_seconds=float(duration_seconds),
        requested_steps=requested,
        completed_steps=len(records),
        completed=bool(completed),
        steps=tuple(records),
    )


__all__ = [
    "ControlledTerminalTrajectoryResult",
    "ControlledTerminalTrajectoryStep",
    "run_controlled_terminal_trajectory",
]
