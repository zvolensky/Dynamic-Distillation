"""Constant-step BDF2 residual assembly for controlled Core V3."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy.optimize import least_squares

from .colored_jacobian_v1 import colored_central_difference_jacobian
from .implicit_step_v1 import ImplicitStepSettings
from .implicit_step_v1 import governing_storage_vector
from .provider_call_audit_v1 import ProviderCallAudit
from .provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from .terminal_inventory_control_bdf2_kinematics_v1 import (
    ControlledBDF2History,
    ControlledBDF2Kinematics,
    evaluate_controlled_bdf2_kinematics,
)
from .terminal_inventory_control_contract_v1 import TerminalInventoryControlContract
from .terminal_inventory_control_implicit_step_v1 import (
    _coordinate_slices,
    _maximum_equilibrium_residual,
    terminal_inventory_control_step_pattern,
)
from .terminal_inventory_control_numerical_v1 import (
    TerminalInventoryControlEvaluation,
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
)


@dataclass(frozen=True)
class TerminalInventoryControlBDF2Evaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    solve_coordinates: np.ndarray
    history: ControlledBDF2History
    kinematics: ControlledBDF2Kinematics
    algebraic_coordinates: np.ndarray
    level_fraction: np.ndarray
    level_error: np.ndarray
    product_log_ratio: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    control_evaluation: TerminalInventoryControlEvaluation
    maximum_equilibrium_residual: float


@dataclass(frozen=True)
class TerminalInventoryControlBDF2StepOutcome:
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None
    cost: float
    optimality: float
    wall_clock_sec: float
    initial_coordinates: np.ndarray
    final_coordinates: np.ndarray
    final_residual: np.ndarray
    final_jacobian: np.ndarray
    evaluation: TerminalInventoryControlBDF2Evaluation


def evaluate_terminal_inventory_control_bdf2_residual(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    history: ControlledBDF2History,
    level_setpoints: TerminalLevelSetpoints,
    rate_scales_lbmolph: Sequence[Sequence[float]],
    solve_coordinates: Sequence[float],
    step_seconds: float,
    fixed_steady_scales: Sequence[float],
    product_reference_lbmolph: Sequence[float] | None = None,
    state_id: str,
    evaluation_kind: str,
) -> TerminalInventoryControlBDF2Evaluation:
    """Evaluate one controlled BDF2 residual without owning a nonlinear solve."""
    expected = (len(spec.topology.volume_ids), len(spec.component_names))
    if history.current_inventory_lbmol.shape != expected:
        raise ValueError("BDF2 history does not match the operating topology")
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("controlled BDF2 solve coordinates are invalid")
    scales = np.asarray(rate_scales_lbmolph, dtype=float)
    if scales.shape != expected or np.any(~np.isfinite(scales)) or np.any(scales <= 0.0):
        raise ValueError("controlled BDF2 rate scales are invalid")
    rate_slice, controller_slice, algebraic_slice, product_slice = _coordinate_slices(
        contract
    )
    nominal_rate = point[rate_slice].reshape(expected) * scales
    controller_rate = point[controller_slice]
    preliminary = evaluate_controlled_bdf2_kinematics(
        history,
        nominal_component_rate_lbmolph=nominal_rate,
        component_rate_scales_lbmolph=scales,
        endpoint_internal_energy_BTU=history.current_internal_energy_BTU,
        controller_rate_per_sec=controller_rate,
        step_seconds=step_seconds,
    )
    effective = point.copy()
    effective[rate_slice] = preliminary.component_rate_coordinates.reshape((-1,))
    control = evaluate_terminal_inventory_control_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=preliminary.endpoint_inventory_lbmol,
        controller_memory=preliminary.endpoint_controller_memory,
        level_setpoints=level_setpoints,
        solve_coordinates=effective,
        storage_gradient_BTU_lbmol=np.zeros(expected, dtype=float),
        fixed_steady_scales=fixed_steady_scales,
        product_reference_lbmolph=product_reference_lbmolph,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    endpoint_storage = governing_storage_vector(
        spec, control.base, preliminary.endpoint_inventory_lbmol
    )
    kinematics = evaluate_controlled_bdf2_kinematics(
        history,
        nominal_component_rate_lbmolph=nominal_rate,
        component_rate_scales_lbmolph=scales,
        endpoint_internal_energy_BTU=endpoint_storage,
        controller_rate_per_sec=controller_rate,
        step_seconds=step_seconds,
    )
    raw = np.asarray(control.raw, dtype=float).copy()
    energy_indices = np.asarray(
        [
            index
            for index, row in enumerate(contract.base.rows)
            if row.block == "energy_balance"
        ],
        dtype=int,
    )
    if energy_indices.size != expected[0]:
        raise RuntimeError("controlled BDF2 contract needs one energy row per volume")
    raw[energy_indices] += kinematics.energy_storage_rate_BTUph
    residual_scales = np.concatenate(
        (np.asarray(control.base.scales, dtype=float), np.ones(4, dtype=float))
    )
    return TerminalInventoryControlBDF2Evaluation(
        raw=raw,
        scaled=raw / residual_scales,
        row_names=control.row_names,
        variable_names=control.variable_names,
        solve_coordinates=effective,
        history=history,
        kinematics=kinematics,
        algebraic_coordinates=effective[algebraic_slice].copy(),
        level_fraction=control.level_fraction.copy(),
        level_error=control.level_error.copy(),
        product_log_ratio=effective[product_slice].copy(),
        distillate_lbmolph=control.distillate_lbmolph,
        bottoms_lbmolph=control.bottoms_lbmolph,
        control_evaluation=control,
        maximum_equilibrium_residual=_maximum_equilibrium_residual(contract, control),
    )


def solve_terminal_inventory_control_bdf2_step(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    history: ControlledBDF2History,
    level_setpoints: TerminalLevelSetpoints,
    rate_scales_lbmolph: Sequence[Sequence[float]],
    initial_solve_coordinates: Sequence[float],
    fixed_steady_scales: Sequence[float],
    product_reference_lbmolph: Sequence[float] | None = None,
    step_seconds: float,
    settings: ImplicitStepSettings,
    name: str,
    jacobian_builder: Callable[
        [Callable[[np.ndarray, str], np.ndarray], np.ndarray, str], np.ndarray
    ]
    | None = None,
) -> TerminalInventoryControlBDF2StepOutcome:
    """Solve one fixed-history BDF2 endpoint without accepting it as a state."""
    initial = np.asarray(initial_solve_coordinates, dtype=float).reshape((-1,))
    if initial.shape != (len(contract.rows),) or np.any(~np.isfinite(initial)):
        raise ValueError("controlled BDF2 initial coordinates are invalid")

    def objective(point: np.ndarray, state_id: str):
        return evaluate_terminal_inventory_control_bdf2_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            history=history,
            level_setpoints=level_setpoints,
            rate_scales_lbmolph=rate_scales_lbmolph,
            solve_coordinates=point,
            step_seconds=step_seconds,
            fixed_steady_scales=fixed_steady_scales,
            product_reference_lbmolph=product_reference_lbmolph,
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        )

    pattern = terminal_inventory_control_step_pattern(contract)

    def residual(point: np.ndarray) -> np.ndarray:
        return objective(point, f"{name}:residual").scaled

    def jacobian(point: np.ndarray) -> np.ndarray:
        scaled_objective = (
            lambda candidate, state_id: objective(candidate, state_id).scaled
        )
        if jacobian_builder is not None:
            return np.asarray(
                jacobian_builder(scaled_objective, point.copy(), f"{name}:jacobian"),
                dtype=float,
            )
        matrix, _groups = colored_central_difference_jacobian(
            scaled_objective,
            point,
            pattern=pattern,
            step=settings.jacobian_step,
            state_id=f"{name}:jacobian",
        )
        return matrix

    lower = np.full(initial.shape, -np.inf)
    upper = np.full(initial.shape, np.inf)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    lower[-2:] = np.log(product_low)
    upper[-2:] = np.log(product_high)
    started = time.perf_counter()
    result = least_squares(
        residual,
        initial,
        jac=jacobian,
        bounds=(lower, upper),
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=settings.x_scale,
    )
    elapsed = time.perf_counter() - started
    endpoint = objective(result.x, f"{name}:endpoint")
    return TerminalInventoryControlBDF2StepOutcome(
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
        njev=None if result.njev is None else int(result.njev),
        cost=float(result.cost),
        optimality=float(result.optimality),
        wall_clock_sec=float(elapsed),
        initial_coordinates=initial.copy(),
        final_coordinates=np.asarray(result.x, dtype=float).copy(),
        final_residual=np.asarray(result.fun, dtype=float).copy(),
        final_jacobian=np.asarray(result.jac, dtype=float).copy(),
        evaluation=endpoint,
    )


__all__ = [
    "TerminalInventoryControlBDF2Evaluation",
    "TerminalInventoryControlBDF2StepOutcome",
    "evaluate_terminal_inventory_control_bdf2_residual",
    "solve_terminal_inventory_control_bdf2_step",
]
