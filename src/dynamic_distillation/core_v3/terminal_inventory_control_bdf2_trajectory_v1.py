"""Constant-step controlled BDF2 trajectory with one backward-Euler startup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .implicit_step_v1 import ImplicitStepSettings, component_rate_scales
from .provider_call_audit_v1 import ProviderCallAudit
from .provider_governed_residual_v1 import NumericalReference, OperatingSpec, PhysicalState
from .terminal_inventory_control_bdf2_kinematics_v1 import build_controlled_bdf2_history
from .terminal_inventory_control_bdf2_residual_v1 import (
    TerminalInventoryControlBDF2StepOutcome,
    solve_terminal_inventory_control_bdf2_step,
)
from .terminal_inventory_control_contract_v1 import TerminalInventoryControlContract
from .terminal_inventory_control_implicit_step_v1 import (
    TerminalInventoryControlStepOutcome,
    solve_terminal_inventory_control_backward_euler_step,
)
from .terminal_inventory_control_numerical_v1 import TerminalLevelSetpoints


@dataclass(frozen=True)
class TerminalInventoryControlBDF2TrajectoryRecord:
    index: int
    time_seconds: float
    method: str
    outcome: TerminalInventoryControlStepOutcome | TerminalInventoryControlBDF2StepOutcome


@dataclass(frozen=True)
class TerminalInventoryControlBDF2TrajectoryResult:
    name: str
    step_seconds: float
    requested_steps: int
    completed_steps: int
    completed: bool
    records: tuple[TerminalInventoryControlBDF2TrajectoryRecord, ...]


def _accepted_inventory(evaluation: Any) -> np.ndarray:
    if hasattr(evaluation, "kinematics"):
        return evaluation.kinematics.endpoint_inventory_lbmol
    return evaluation.endpoint_inventory_lbmol


def _accepted_storage(evaluation: Any) -> np.ndarray:
    if hasattr(evaluation, "kinematics"):
        return evaluation.kinematics.endpoint_internal_energy_BTU
    return evaluation.endpoint_internal_energy_BTU


def _accepted_memory(evaluation: Any) -> np.ndarray:
    if hasattr(evaluation, "kinematics"):
        return evaluation.kinematics.endpoint_controller_memory
    return evaluation.endpoint_controller_memory


def run_terminal_inventory_control_bdf2_trajectory(
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
    product_reference_lbmolph: Sequence[float] | None,
    duration_seconds: float,
    step_seconds: float,
    settings: ImplicitStepSettings,
    name: str,
) -> TerminalInventoryControlBDF2TrajectoryResult:
    """Run one BE startup followed by fixed-step BDF2 roots."""
    duration = float(duration_seconds)
    step = float(step_seconds)
    if not np.isfinite(duration) or not np.isfinite(step) or duration <= 0.0 or step <= 0.0:
        raise ValueError("controlled BDF2 trajectory duration and step must be positive")
    requested = int(round(duration / step))
    if requested < 2 or not np.isclose(requested * step, duration, rtol=0.0, atol=1e-12):
        raise ValueError("controlled BDF2 trajectory needs at least two constant steps")

    initial_inventory = np.asarray(initial_inventory_lbmol, dtype=float)
    initial_memory = np.asarray(initial_controller_memory, dtype=float)
    initial_coordinates = np.asarray(initial_solve_coordinates, dtype=float)
    records: list[TerminalInventoryControlBDF2TrajectoryRecord] = []
    startup = solve_terminal_inventory_control_backward_euler_step(
        contract,
        spec,
        reference,
        initial_template,
        provider,
        call_audit,
        previous_inventory_lbmol=initial_inventory,
        previous_controller_memory=initial_memory,
        level_setpoints=level_setpoints,
        initial_solve_coordinates=initial_coordinates,
        fixed_steady_scales=fixed_steady_scales,
        product_reference_lbmolph=product_reference_lbmolph,
        step_seconds=step,
        settings=settings,
        name=f"{name}:startup",
    )
    records.append(TerminalInventoryControlBDF2TrajectoryRecord(1, step, "backward_euler", startup))
    if not startup.success:
        return TerminalInventoryControlBDF2TrajectoryResult(name, step, requested, 1, False, tuple(records))

    prior_inventory = initial_inventory
    prior_storage = startup.evaluation.previous_internal_energy_BTU
    prior_memory = initial_memory
    current = startup.evaluation
    current_coordinates = startup.final_coordinates

    for index in range(2, requested + 1):
        history = build_controlled_bdf2_history(
            step_seconds=step,
            current_inventory_lbmol=_accepted_inventory(current),
            prior_inventory_lbmol=prior_inventory,
            current_internal_energy_BTU=_accepted_storage(current),
            prior_internal_energy_BTU=prior_storage,
            current_controller_memory=_accepted_memory(current),
            prior_controller_memory=prior_memory,
        )
        rates = component_rate_scales(contract.base, current.control_evaluation.base)
        outcome = solve_terminal_inventory_control_bdf2_step(
            contract,
            spec,
            reference,
            current.control_evaluation.base.physical_state,
            provider,
            call_audit,
            history=history,
            level_setpoints=level_setpoints,
            rate_scales_lbmolph=rates,
            initial_solve_coordinates=current_coordinates,
            fixed_steady_scales=fixed_steady_scales,
            product_reference_lbmolph=product_reference_lbmolph,
            step_seconds=step,
            settings=settings,
            name=f"{name}:bdf2_{index}",
        )
        records.append(
            TerminalInventoryControlBDF2TrajectoryRecord(index, index * step, "bdf2", outcome)
        )
        if not outcome.success:
            break
        prior_inventory = _accepted_inventory(current)
        prior_storage = _accepted_storage(current)
        prior_memory = _accepted_memory(current)
        current = outcome.evaluation
        current_coordinates = outcome.final_coordinates

    completed = len(records) == requested and all(record.outcome.success for record in records)
    return TerminalInventoryControlBDF2TrajectoryResult(
        name=name,
        step_seconds=step,
        requested_steps=requested,
        completed_steps=len(records),
        completed=completed,
        records=tuple(records),
    )


__all__ = [
    "TerminalInventoryControlBDF2TrajectoryRecord",
    "TerminalInventoryControlBDF2TrajectoryResult",
    "_accepted_inventory",
    "_accepted_memory",
    "_accepted_storage",
    "run_terminal_inventory_control_bdf2_trajectory",
]
