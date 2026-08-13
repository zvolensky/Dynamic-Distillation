"""Short trajectories for the Core V3 terminal inventory-control DAE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np

from dynamic_distillation.core_v3.implicit_step_v1 import ImplicitStepSettings
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (
    TerminalInventoryControlContract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (
    TerminalInventoryControlStepOutcome,
    solve_terminal_inventory_control_backward_euler_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (
    TerminalLevelSetpoints,
)


@dataclass(frozen=True)
class TerminalInventoryControlTrajectoryStep:
    index: int
    time_seconds: float
    outcome: TerminalInventoryControlStepOutcome


@dataclass(frozen=True)
class TerminalInventoryControlTrajectoryResult:
    name: str
    step_seconds: float
    duration_seconds: float
    requested_steps: int
    completed_steps: int
    completed: bool
    steps: tuple[TerminalInventoryControlTrajectoryStep, ...]

    @property
    def endpoint_outcome(self) -> TerminalInventoryControlStepOutcome:
        if not self.steps:
            raise RuntimeError("terminal-control trajectory has no endpoint")
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


def run_terminal_inventory_control_trajectory(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    initial_template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    initial_inventory_lbmol: Sequence[Sequence[float]],
    initial_controller_memory: Sequence[float],
    level_setpoints: TerminalLevelSetpoints,
    initial_solve_coordinates: Sequence[float],
    fixed_steady_scales: Sequence[float],
    product_reference_lbmolph: Sequence[float],
    step_seconds: float,
    duration_seconds: float,
    settings: ImplicitStepSettings,
    name: str,
    step_solver: Callable[..., TerminalInventoryControlStepOutcome] | None = None,
) -> TerminalInventoryControlTrajectoryResult:
    requested = _step_count(duration_seconds, step_seconds)
    inventory = np.asarray(initial_inventory_lbmol, dtype=float).copy()
    memory = np.asarray(initial_controller_memory, dtype=float).copy()
    coordinates = np.asarray(initial_solve_coordinates, dtype=float).copy()
    product_reference = np.asarray(product_reference_lbmolph, dtype=float).copy()
    template = initial_template
    if (
        inventory.ndim != 2
        or np.any(~np.isfinite(inventory))
        or np.any(inventory <= 0.0)
        or memory.shape != (2,)
        or np.any(~np.isfinite(memory))
        or np.any(~np.isfinite(coordinates))
        or product_reference.shape != (2,)
        or np.any(~np.isfinite(product_reference))
        or np.any(product_reference <= 0.0)
    ):
        raise ValueError("terminal-control trajectory initial state is invalid")

    records: list[TerminalInventoryControlTrajectoryStep] = []
    solver = step_solver or solve_terminal_inventory_control_backward_euler_step
    for index in range(1, requested + 1):
        outcome = solver(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=inventory,
            previous_controller_memory=memory,
            level_setpoints=level_setpoints,
            initial_solve_coordinates=coordinates,
            fixed_steady_scales=fixed_steady_scales,
            product_reference_lbmolph=product_reference,
            step_seconds=step_seconds,
            settings=settings,
            name=f"{name}:step_{index}",
        )
        records.append(
            TerminalInventoryControlTrajectoryStep(
                index=index,
                time_seconds=float(index) * float(step_seconds),
                outcome=outcome,
            )
        )
        if not outcome.success:
            break
        evaluation = outcome.evaluation
        inventory = evaluation.endpoint_inventory_lbmol.copy()
        memory = evaluation.endpoint_controller_memory.copy()
        coordinates = outcome.final_coordinates.copy()
        template = evaluation.control_evaluation.base.physical_state

    completed = len(records) == requested and all(
        record.outcome.success for record in records
    )
    return TerminalInventoryControlTrajectoryResult(
        name=str(name),
        step_seconds=float(step_seconds),
        duration_seconds=float(duration_seconds),
        requested_steps=requested,
        completed_steps=len(records),
        completed=bool(completed),
        steps=tuple(records),
    )


__all__ = [
    "TerminalInventoryControlTrajectoryResult",
    "TerminalInventoryControlTrajectoryStep",
    "run_terminal_inventory_control_trajectory",
]
