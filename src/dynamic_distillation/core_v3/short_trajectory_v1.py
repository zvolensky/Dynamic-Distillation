"""Bounded open-loop trajectory orchestration for Core V3."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Sequence

import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    DynamicDAEContract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    BackwardEulerEvaluation,
    ImplicitSolveOutcome,
    ImplicitStepSettings,
    solve_backward_euler_step,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


@dataclass(frozen=True)
class TrajectoryStep:
    index: int
    time_seconds: float
    outcome: ImplicitSolveOutcome


@dataclass(frozen=True)
class ShortTrajectoryResult:
    name: str
    step_seconds: float
    duration_seconds: float
    requested_steps: int
    completed_steps: int
    completed: bool
    initial_inventory_lbmol: np.ndarray
    initial_algebraic_coordinates: np.ndarray
    steps: tuple[TrajectoryStep, ...]

    @property
    def endpoint_evaluation(self) -> BackwardEulerEvaluation:
        if not self.steps:
            raise RuntimeError("trajectory has no endpoint")
        evaluation = self.steps[-1].outcome.evaluation
        if not isinstance(evaluation, BackwardEulerEvaluation):
            raise TypeError("trajectory endpoint is not a backward-Euler state")
        return evaluation


def scale_feed_throughput(spec: OperatingSpec, factor: float) -> OperatingSpec:
    if not np.isfinite(factor) or factor <= 0.0:
        raise ValueError("feed-throughput factor must be positive and finite")
    return replace(
        spec,
        feed_component_lbmolph=(
            np.asarray(spec.feed_component_lbmolph, dtype=float) * float(factor)
        ),
        feed_enthalpy_BTUph=float(spec.feed_enthalpy_BTUph) * float(factor),
    )


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


def run_short_trajectory(
    contract: DynamicDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    initial_state: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    fixed_steady_scales: Sequence[float],
    step_seconds: float,
    duration_seconds: float,
    settings: ImplicitStepSettings,
    name: str,
    step_solver: Callable[..., ImplicitSolveOutcome] = solve_backward_euler_step,
) -> ShortTrajectoryResult:
    requested = _step_count(duration_seconds, step_seconds)
    initial_inventory = inventory_from_state(initial_state)
    initial_algebraic = dynamic_algebraic_coordinates(
        spec, reference, initial_state
    )
    inventory = initial_inventory.copy()
    algebraic = initial_algebraic.copy()
    template = initial_state
    records: list[TrajectoryStep] = []
    for index in range(1, requested + 1):
        outcome = step_solver(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=inventory,
            initial_algebraic_coordinates=algebraic,
            fixed_steady_scales=fixed_steady_scales,
            step_seconds=step_seconds,
            settings=settings,
            name=f"{name}:step_{index}",
        )
        records.append(
            TrajectoryStep(
                index=index,
                time_seconds=float(index) * float(step_seconds),
                outcome=outcome,
            )
        )
        if not outcome.success:
            break
        evaluation = outcome.evaluation
        if not isinstance(evaluation, BackwardEulerEvaluation):
            raise TypeError("trajectory solver returned a non-step evaluation")
        inventory = evaluation.endpoint_inventory_lbmol.copy()
        algebraic = evaluation.algebraic_coordinates.copy()
        template = evaluation.dynamic_evaluation.physical_state
    return ShortTrajectoryResult(
        name=str(name),
        step_seconds=float(step_seconds),
        duration_seconds=float(duration_seconds),
        requested_steps=requested,
        completed_steps=len(records),
        completed=len(records) == requested and all(
            record.outcome.success for record in records
        ),
        initial_inventory_lbmol=initial_inventory,
        initial_algebraic_coordinates=initial_algebraic,
        steps=tuple(records),
    )


__all__ = [
    "ShortTrajectoryResult",
    "TrajectoryStep",
    "run_short_trajectory",
    "scale_feed_throughput",
]
