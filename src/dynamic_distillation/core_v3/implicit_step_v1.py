"""Backward-Euler step kernel for the reduced Core V3 dynamic DAE."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    DynamicDAEContract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    DynamicImplicitEvaluation,
    dynamic_algebraic_coordinates,
    evaluate_dynamic_implicit_residual,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    VOLUME_IDS,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
    solve_local_bubble,
)
from dynamic_distillation.uv_flash_stage_v1 import BTU_PER_PSI_FT3


@dataclass(frozen=True)
class ImplicitStepSettings:
    method: str = "trf"
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 40
    x_scale: float = 1.0
    jacobian_step: float = 1.0e-5


@dataclass(frozen=True)
class BackwardEulerEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    previous_inventory_lbmol: np.ndarray
    endpoint_inventory_lbmol: np.ndarray
    component_rate_lbmolph: np.ndarray
    rate_coordinates: np.ndarray
    algebraic_coordinates: np.ndarray
    previous_internal_energy_BTU: np.ndarray
    endpoint_internal_energy_BTU: np.ndarray
    energy_storage_rate_BTUph: np.ndarray
    dynamic_evaluation: DynamicImplicitEvaluation
    maximum_bubble_residual: float


@dataclass(frozen=True)
class ImplicitSolveOutcome:
    name: str
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
    jacobian: np.ndarray
    evaluation: BackwardEulerEvaluation | DynamicImplicitEvaluation


def _energy_row_indices(contract: DynamicDAEContract) -> np.ndarray:
    return np.asarray(
        [
            index
            for index, row in enumerate(contract.rows)
            if row.block == "energy_balance"
        ],
        dtype=int,
    )


def component_rate_scales(
    contract: DynamicDAEContract,
    evaluation: DynamicImplicitEvaluation,
) -> np.ndarray:
    indices = np.asarray(
        [
            index
            for index, row in enumerate(contract.rows)
            if row.block == "component_balance"
        ],
        dtype=int,
    )
    expected = len(VOLUME_IDS) * len(evaluation.physical_state.liquid_mole_fraction[0])
    if indices.size != expected:
        raise RuntimeError("component-rate scale count does not match inventory")
    scales = np.asarray(evaluation.scales[indices], dtype=float).reshape(
        (len(VOLUME_IDS), -1)
    )
    if np.any(~np.isfinite(scales)) or np.any(scales <= 0.0):
        raise ValueError("component-rate scales must be positive and finite")
    return scales


def saturated_storage_vector(
    spec: OperatingSpec,
    state: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    inventory_lbmol: Sequence[Sequence[float]],
    *,
    state_id: str,
    evaluation_kind: str,
) -> tuple[np.ndarray, float]:
    inventory = np.asarray(inventory_lbmol, dtype=float)
    expected = (len(VOLUME_IDS), len(spec.component_names))
    if inventory.shape != expected or np.any(inventory <= 0.0):
        raise ValueError("storage inventory must be positive with model shape")
    vapor_guesses = (
        np.asarray(state.bubble_vapor_mole_fraction, dtype=float),
        *(
            np.asarray(row, dtype=float)
            for row in np.asarray(state.vapor_mole_fraction, dtype=float)
        ),
    )
    storage = np.empty(len(VOLUME_IDS), dtype=float)
    maximum_bubble = 0.0
    for volume_index, volume in enumerate(VOLUME_IDS):
        total = float(np.sum(inventory[volume_index]))
        liquid_x = inventory[volume_index] / total
        bubble = solve_local_bubble(
            provider,
            call_audit,
            pressure_psia=float(spec.pressure_psia[volume_index]),
            liquid_x=liquid_x,
            temperature_guess_F=float(state.temperature_F[volume_index]),
            vapor_guess=vapor_guesses[volume_index],
            state_id=f"{state_id}:{volume}",
            evaluation_kind=evaluation_kind,
            governing=True,
        )
        if not bubble.success or bubble.residual_inf_norm >= 1.0e-10:
            raise RuntimeError("governing storage bubble reconstruction failed")
        enthalpy = call_audit.phase_enthalpy(
            provider,
            phase="liquid",
            temperature_F=bubble.temperature_F,
            pressure_psia=float(spec.pressure_psia[volume_index]),
            composition=liquid_x,
            caller=f"implicit_energy_storage[{volume}]",
            state_id=f"{state_id}:{volume}",
            evaluation_kind=evaluation_kind,
        )
        density = call_audit.liquid_density(
            provider,
            temperature_F=bubble.temperature_F,
            pressure_psia=float(spec.pressure_psia[volume_index]),
            composition=liquid_x,
            caller=f"implicit_energy_storage[{volume}]",
            state_id=f"{state_id}:{volume}",
            evaluation_kind=evaluation_kind,
        )
        internal_energy = float(enthalpy) - (
            float(spec.pressure_psia[volume_index])
            * (1.0 / float(density))
            * BTU_PER_PSI_FT3
        )
        storage[volume_index] = total * internal_energy
        maximum_bubble = max(maximum_bubble, float(bubble.residual_inf_norm))
    return storage, maximum_bubble


def zero_rate_evaluation(
    contract: DynamicDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    algebraic_coordinates: Sequence[float],
    fixed_steady_scales: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> DynamicImplicitEvaluation:
    return evaluate_dynamic_implicit_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory_lbmol,
        rate_coordinates=np.zeros(len(contract.derivative_variables)),
        algebraic_coordinates=algebraic_coordinates,
        storage_gradient_BTU_lbmol=np.zeros(
            (len(VOLUME_IDS), len(spec.component_names)), dtype=float
        ),
        fixed_steady_scales=fixed_steady_scales,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )


def evaluate_backward_euler_residual(
    contract: DynamicDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    previous_inventory_lbmol: Sequence[Sequence[float]],
    previous_internal_energy_BTU: Sequence[float],
    rate_scales_lbmolph: Sequence[Sequence[float]],
    solve_coordinates: Sequence[float],
    step_seconds: float,
    fixed_steady_scales: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> BackwardEulerEvaluation:
    if not np.isfinite(step_seconds) or step_seconds <= 0.0:
        raise ValueError("backward-Euler step must be positive")
    previous = np.asarray(previous_inventory_lbmol, dtype=float)
    scales = np.asarray(rate_scales_lbmolph, dtype=float)
    expected = (len(VOLUME_IDS), len(spec.component_names))
    if previous.shape != expected or scales.shape != expected:
        raise ValueError("inventory or rate-scale shape is invalid")
    if np.any(previous <= 0.0) or np.any(scales <= 0.0):
        raise ValueError("inventory and rate scales must be positive")
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    rate_count = len(contract.derivative_variables)
    expected_coordinates = rate_count + len(contract.algebraic_variables)
    if point.size != expected_coordinates or np.any(~np.isfinite(point)):
        raise ValueError("implicit solve coordinates are invalid")
    nominal_rate = point[:rate_count].reshape(expected) * scales
    step_hours = float(step_seconds) / 3600.0
    exponent = step_hours * nominal_rate / previous
    with np.errstate(over="raise", invalid="raise", under="ignore"):
        endpoint_inventory = previous * np.exp(exponent)
    if np.any(~np.isfinite(endpoint_inventory)) or np.any(endpoint_inventory <= 0.0):
        raise ValueError("implicit endpoint inventory is not physical")
    physical_rate = (endpoint_inventory - previous) / step_hours
    actual_rate_coordinates = physical_rate / scales
    algebraic = point[rate_count:]
    dynamic = evaluate_dynamic_implicit_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=endpoint_inventory,
        rate_coordinates=actual_rate_coordinates.reshape((-1,)),
        algebraic_coordinates=algebraic,
        storage_gradient_BTU_lbmol=np.zeros(expected, dtype=float),
        fixed_steady_scales=fixed_steady_scales,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    endpoint_storage, bubble = saturated_storage_vector(
        spec,
        dynamic.physical_state,
        provider,
        call_audit,
        endpoint_inventory,
        state_id=f"{state_id}:storage",
        evaluation_kind=evaluation_kind,
    )
    previous_storage = np.asarray(previous_internal_energy_BTU, dtype=float)
    if previous_storage.shape != (len(VOLUME_IDS),):
        raise ValueError("previous storage vector has invalid shape")
    storage_rate = (endpoint_storage - previous_storage) / step_hours
    raw = np.asarray(dynamic.raw, dtype=float).copy()
    energy_indices = _energy_row_indices(contract)
    if energy_indices.size != len(VOLUME_IDS):
        raise RuntimeError("dynamic contract must contain one energy row per volume")
    raw[energy_indices] += storage_rate
    return BackwardEulerEvaluation(
        raw=raw,
        scaled=raw / dynamic.scales,
        row_names=dynamic.row_names,
        previous_inventory_lbmol=previous.copy(),
        endpoint_inventory_lbmol=endpoint_inventory,
        component_rate_lbmolph=physical_rate,
        rate_coordinates=actual_rate_coordinates,
        algebraic_coordinates=algebraic.copy(),
        previous_internal_energy_BTU=previous_storage.copy(),
        endpoint_internal_energy_BTU=endpoint_storage,
        energy_storage_rate_BTUph=storage_rate,
        dynamic_evaluation=dynamic,
        maximum_bubble_residual=float(bubble),
    )


def central_difference_jacobian(
    objective: Callable[[np.ndarray, str], np.ndarray],
    point: Sequence[float],
    *,
    step: float,
    state_id: str,
) -> np.ndarray:
    coordinates = np.asarray(point, dtype=float).reshape((-1,))
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("Jacobian step must be positive")
    baseline = np.asarray(
        objective(coordinates, f"{state_id}:baseline"), dtype=float
    ).reshape((-1,))
    matrix = np.empty((baseline.size, coordinates.size), dtype=float)
    for column in range(coordinates.size):
        delta = np.zeros_like(coordinates)
        delta[column] = float(step)
        plus = np.asarray(
            objective(coordinates + delta, f"{state_id}:{column}:plus"),
            dtype=float,
        )
        minus = np.asarray(
            objective(coordinates - delta, f"{state_id}:{column}:minus"),
            dtype=float,
        )
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    return matrix


def _least_squares(
    name: str,
    initial: np.ndarray,
    objective: Callable[[np.ndarray, str], np.ndarray],
    endpoint: Callable[[np.ndarray], BackwardEulerEvaluation | DynamicImplicitEvaluation],
    settings: ImplicitStepSettings,
) -> ImplicitSolveOutcome:
    def residual(point: np.ndarray) -> np.ndarray:
        return objective(point, f"{name}:residual")

    def jacobian(point: np.ndarray) -> np.ndarray:
        return central_difference_jacobian(
            objective,
            point,
            step=settings.jacobian_step,
            state_id=f"{name}:jacobian",
        )

    started = time.perf_counter()
    result = least_squares(
        residual,
        np.asarray(initial, dtype=float),
        jac=jacobian,
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=settings.x_scale,
    )
    wall_clock = float(time.perf_counter() - started)
    final_evaluation = endpoint(result.x)
    return ImplicitSolveOutcome(
        name=name,
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
        njev=None if result.njev is None else int(result.njev),
        cost=float(result.cost),
        optimality=float(result.optimality),
        wall_clock_sec=wall_clock,
        initial_coordinates=np.asarray(initial, dtype=float).copy(),
        final_coordinates=np.asarray(result.x, dtype=float).copy(),
        final_residual=np.asarray(final_evaluation.scaled, dtype=float).copy(),
        jacobian=np.asarray(result.jac, dtype=float).copy(),
        evaluation=final_evaluation,
    )


def solve_zero_rate_algebraic(
    contract: DynamicDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    initial_algebraic_coordinates: Sequence[float],
    fixed_steady_scales: Sequence[float],
    settings: ImplicitStepSettings,
    name: str,
) -> ImplicitSolveOutcome:
    initial = np.asarray(initial_algebraic_coordinates, dtype=float).reshape((-1,))

    def evaluate(point: np.ndarray, state_id: str) -> np.ndarray:
        return zero_rate_evaluation(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            algebraic_coordinates=point,
            fixed_steady_scales=fixed_steady_scales,
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        ).scaled

    def endpoint(point: np.ndarray) -> DynamicImplicitEvaluation:
        return zero_rate_evaluation(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            algebraic_coordinates=point,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{name}:endpoint",
            evaluation_kind="residual",
        )

    return _least_squares(name, initial, evaluate, endpoint, settings)


def solve_backward_euler_step(
    contract: DynamicDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    previous_inventory_lbmol: Sequence[Sequence[float]],
    initial_algebraic_coordinates: Sequence[float] | None = None,
    fixed_steady_scales: Sequence[float],
    step_seconds: float,
    settings: ImplicitStepSettings,
    name: str,
) -> ImplicitSolveOutcome:
    previous = np.asarray(previous_inventory_lbmol, dtype=float)
    algebraic = (
        dynamic_algebraic_coordinates(spec, reference, template)
        if initial_algebraic_coordinates is None
        else np.asarray(initial_algebraic_coordinates, dtype=float)
    )
    baseline = zero_rate_evaluation(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=previous,
        algebraic_coordinates=algebraic,
        fixed_steady_scales=fixed_steady_scales,
        state_id=f"{name}:scale_basis",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(contract, baseline)
    previous_storage, _ = saturated_storage_vector(
        spec,
        template,
        provider,
        call_audit,
        previous,
        state_id=f"{name}:previous_storage",
        evaluation_kind="residual",
    )
    initial = np.concatenate(
        (np.zeros(len(contract.derivative_variables), dtype=float), algebraic)
    )

    def evaluate(point: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_backward_euler_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=previous,
            previous_internal_energy_BTU=previous_storage,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=point,
            step_seconds=step_seconds,
            fixed_steady_scales=fixed_steady_scales,
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        ).scaled

    def endpoint(point: np.ndarray) -> BackwardEulerEvaluation:
        return evaluate_backward_euler_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=previous,
            previous_internal_energy_BTU=previous_storage,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=point,
            step_seconds=step_seconds,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{name}:endpoint",
            evaluation_kind="residual",
        )

    return _least_squares(name, initial, evaluate, endpoint, settings)


__all__ = [
    "BackwardEulerEvaluation",
    "ImplicitSolveOutcome",
    "ImplicitStepSettings",
    "central_difference_jacobian",
    "component_rate_scales",
    "evaluate_backward_euler_residual",
    "saturated_storage_vector",
    "solve_backward_euler_step",
    "solve_zero_rate_algebraic",
    "zero_rate_evaluation",
]
