"""Numerical kernel for the conserved-N/U pressure initializer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    ConservedNUPressureInitializerContract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_numerical_v1 import (
    ConservedNUPressureEvaluation,
    evaluate_conserved_nu_pressure_residual,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


@dataclass(frozen=True)
class InitializerNumericalSpec:
    inventory_reference_lbmol: np.ndarray
    lower_internal_energy_reference_BTU: np.ndarray
    lower_internal_energy_scale_BTU: np.ndarray
    component_total_targets_lbmol: np.ndarray
    stored_energy_target_BTU: float
    terminal_total_targets_lbmol: np.ndarray
    objective_center: np.ndarray
    objective_weights: np.ndarray
    lower_bounds: np.ndarray
    upper_bounds: np.ndarray
    jacobian_step: float


@dataclass(frozen=True)
class InitializerConstraintEvaluation:
    scaled: np.ndarray
    row_names: tuple[str, ...]
    coordinates: np.ndarray
    inventory_lbmol: np.ndarray
    lower_internal_energy_BTU: np.ndarray
    solve_coordinates: np.ndarray
    component_total_residual_lbmol: np.ndarray
    stored_energy_residual_BTU: float
    terminal_total_residual_lbmol: np.ndarray
    dae_evaluation: ConservedNUPressureEvaluation


@dataclass(frozen=True)
class InitializerSolveSettings:
    method: str = "SLSQP"
    ftol: float = 1.0e-10
    maxiter: int = 80
    jacobian_step: float = 1.0e-5
    disp: bool = False


@dataclass(frozen=True)
class InitializerSolveOutcome:
    success: bool
    status: int
    message: str
    iterations: int
    objective_evaluations: int
    gradient_evaluations: int
    final_coordinates: np.ndarray
    final_objective: float
    final_constraints: np.ndarray


@dataclass(frozen=True)
class InitializerJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]
    color_count: int


def initializer_variable_names(
    contract: ConservedNUPressureInitializerContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (
            *contract.state_variables,
            *contract.derivative_variables,
            *contract.algebraic_variables,
        )
    )


def initializer_constraint_pattern(
    contract: ConservedNUPressureInitializerContract,
) -> np.ndarray:
    names = initializer_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.constraints), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.constraints):
        for dependency in row.dependencies:
            pattern[row_index, index[dependency]] = True
    return pattern


def _validate_numerical_spec(
    contract: ConservedNUPressureInitializerContract,
    numerical: InitializerNumericalSpec,
) -> None:
    component_count = len(contract.pressure_dae.component_names)
    variable_count = len(initializer_variable_names(contract))
    if (
        np.asarray(numerical.inventory_reference_lbmol).shape
        != (len(VOLUME_IDS), component_count)
        or np.any(np.asarray(numerical.inventory_reference_lbmol) <= 0.0)
        or np.asarray(numerical.lower_internal_energy_reference_BTU).shape
        != (len(VOLUME_IDS) - 1,)
        or np.asarray(numerical.lower_internal_energy_scale_BTU).shape
        != (len(VOLUME_IDS) - 1,)
        or np.any(np.asarray(numerical.lower_internal_energy_scale_BTU) <= 0.0)
        or np.asarray(numerical.component_total_targets_lbmol).shape
        != (component_count,)
        or np.any(np.asarray(numerical.component_total_targets_lbmol) <= 0.0)
        or not np.isfinite(numerical.stored_energy_target_BTU)
        or numerical.stored_energy_target_BTU == 0.0
        or np.asarray(numerical.terminal_total_targets_lbmol).shape != (2,)
        or np.any(np.asarray(numerical.terminal_total_targets_lbmol) <= 0.0)
        or np.asarray(numerical.objective_center).shape != (variable_count,)
        or np.asarray(numerical.objective_weights).shape != (variable_count,)
        or np.any(np.asarray(numerical.objective_weights) <= 0.0)
        or np.asarray(numerical.lower_bounds).shape != (variable_count,)
        or np.asarray(numerical.upper_bounds).shape != (variable_count,)
        or np.any(np.asarray(numerical.lower_bounds) >= np.asarray(numerical.upper_bounds))
        or not np.isfinite(numerical.jacobian_step)
        or numerical.jacobian_step <= 0.0
    ):
        raise ValueError("initializer numerical specification is invalid")


def decode_initializer_coordinates(
    contract: ConservedNUPressureInitializerContract,
    numerical: InitializerNumericalSpec,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    _validate_numerical_spec(contract, numerical)
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.shape != numerical.objective_center.shape or np.any(~np.isfinite(point)):
        raise ValueError("initializer coordinates are invalid")
    component_state_count = len(VOLUME_IDS) * len(contract.pressure_dae.component_names)
    energy_state_count = len(VOLUME_IDS) - 1
    inventory = np.asarray(numerical.inventory_reference_lbmol, dtype=float) * np.exp(
        point[:component_state_count].reshape(
            np.asarray(numerical.inventory_reference_lbmol).shape
        )
    )
    energy_start = component_state_count
    energy_stop = energy_start + energy_state_count
    lower_u = np.asarray(
        numerical.lower_internal_energy_reference_BTU, dtype=float
    ) + point[energy_start:energy_stop] * np.asarray(
        numerical.lower_internal_energy_scale_BTU, dtype=float
    )
    return inventory, lower_u, point[energy_stop:]


def evaluate_initializer_constraints(
    contract: ConservedNUPressureInitializerContract,
    numerical: InitializerNumericalSpec,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    coordinates: Sequence[float],
    top_storage_gradient_BTU_lbmol: Sequence[float],
    energy_rate_scales_BTUph: Sequence[float],
    fixed_steady_scales: Sequence[float],
    storage_scales_BTU: Sequence[float],
    pressure_numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> InitializerConstraintEvaluation:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    inventory, lower_u, solve = decode_initializer_coordinates(
        contract, numerical, point
    )
    dae = evaluate_conserved_nu_pressure_residual(
        contract.pressure_dae,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        top_storage_gradient_BTU_lbmol=top_storage_gradient_BTU_lbmol,
        energy_rate_scales_BTUph=energy_rate_scales_BTUph,
        solve_coordinates=solve,
        fixed_steady_scales=fixed_steady_scales,
        storage_scales_BTU=storage_scales_BTU,
        numerical=pressure_numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    component_residual = (
        np.sum(inventory, axis=0)
        - np.asarray(numerical.component_total_targets_lbmol, dtype=float)
    )
    stored_energy_residual = float(
        dae.live_internal_energy_BTU[0]
        + np.sum(lower_u)
        - float(numerical.stored_energy_target_BTU)
    )
    terminal_totals = np.asarray(
        (np.sum(inventory[0]), np.sum(inventory[-1])), dtype=float
    )
    terminal_residual = terminal_totals - np.asarray(
        numerical.terminal_total_targets_lbmol, dtype=float
    )
    extra_scaled = np.concatenate(
        (
            component_residual
            / np.asarray(numerical.component_total_targets_lbmol, dtype=float),
            np.asarray(
                (stored_energy_residual / abs(numerical.stored_energy_target_BTU),)
            ),
            terminal_residual
            / np.asarray(numerical.terminal_total_targets_lbmol, dtype=float),
        )
    )
    scaled = np.concatenate((dae.scaled, extra_scaled))
    if scaled.shape != (len(contract.constraints),):
        raise RuntimeError("initializer constraint vector has invalid shape")
    return InitializerConstraintEvaluation(
        scaled=scaled,
        row_names=tuple(row.name for row in contract.constraints),
        coordinates=point.copy(),
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        solve_coordinates=solve,
        component_total_residual_lbmol=component_residual,
        stored_energy_residual_BTU=stored_energy_residual,
        terminal_total_residual_lbmol=terminal_residual,
        dae_evaluation=dae,
    )


def initializer_objective(
    numerical: InitializerNumericalSpec, coordinates: Sequence[float]
) -> float:
    delta = np.asarray(coordinates, dtype=float) - np.asarray(
        numerical.objective_center, dtype=float
    )
    return float(0.5 * np.dot(numerical.objective_weights * delta, delta))


def initializer_objective_gradient(
    numerical: InitializerNumericalSpec, coordinates: Sequence[float]
) -> np.ndarray:
    return np.asarray(numerical.objective_weights, dtype=float) * (
        np.asarray(coordinates, dtype=float)
        - np.asarray(numerical.objective_center, dtype=float)
    )


def initializer_constraint_jacobian(
    contract: ConservedNUPressureInitializerContract,
    objective: Callable[[np.ndarray, str], np.ndarray],
    coordinates: Sequence[float],
    *,
    step: float,
    state_id: str,
    use_coloring: bool = True,
) -> tuple[np.ndarray, int]:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    pattern = initializer_constraint_pattern(contract)
    if use_coloring:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=step,
            state_id=state_id,
        )
        return matrix, len(groups)
    matrix = np.empty(pattern.shape, dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = objective(point + delta, f"{state_id}:full:{column}:plus")
        minus = objective(point - delta, f"{state_id}:full:{column}:minus")
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    return matrix, point.size


def solve_equality_constrained_initializer(
    contract: ConservedNUPressureInitializerContract,
    numerical: InitializerNumericalSpec,
    start: Sequence[float],
    constraint_objective: Callable[[np.ndarray, str], np.ndarray],
    *,
    settings: InitializerSolveSettings,
) -> InitializerSolveOutcome:
    point = np.asarray(start, dtype=float).reshape((-1,))
    _validate_numerical_spec(contract, numerical)
    if settings.method != "SLSQP":
        raise ValueError("DD-112 permits only SLSQP")
    if not np.isclose(settings.jacobian_step, numerical.jacobian_step, rtol=0.0, atol=0.0):
        raise ValueError("solver and numerical Jacobian steps differ")
    calls = {"constraint": 0, "jacobian": 0}

    def constraints(candidate: np.ndarray) -> np.ndarray:
        calls["constraint"] += 1
        return constraint_objective(
            candidate, f"dd112:solve:constraint:{calls['constraint']}"
        )

    def constraint_jac(candidate: np.ndarray) -> np.ndarray:
        calls["jacobian"] += 1
        matrix, _ = initializer_constraint_jacobian(
            contract,
            constraint_objective,
            candidate,
            step=numerical.jacobian_step,
            state_id=f"dd112:solve:jacobian:{calls['jacobian']}",
            use_coloring=True,
        )
        return matrix

    result = minimize(
        lambda candidate: initializer_objective(numerical, candidate),
        point,
        method=settings.method,
        jac=lambda candidate: initializer_objective_gradient(numerical, candidate),
        bounds=list(zip(numerical.lower_bounds, numerical.upper_bounds, strict=True)),
        constraints={"type": "eq", "fun": constraints, "jac": constraint_jac},
        options={
            "ftol": settings.ftol,
            "maxiter": settings.maxiter,
            "disp": settings.disp,
        },
    )
    final = np.asarray(result.x, dtype=float)
    final_constraints = constraints(final)
    return InitializerSolveOutcome(
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        iterations=int(result.nit),
        objective_evaluations=int(result.nfev),
        gradient_evaluations=int(result.njev),
        final_coordinates=final,
        final_objective=float(result.fun),
        final_constraints=final_constraints,
    )


def audit_initializer_constraint_jacobian(
    contract: ConservedNUPressureInitializerContract,
    objective: Callable[[np.ndarray, str], np.ndarray],
    coordinates: Sequence[float],
    *,
    step: float,
    coupling_tolerance: float,
    use_coloring: bool = True,
) -> InitializerJacobianAudit:
    matrix, color_count = initializer_constraint_jacobian(
        contract,
        objective,
        coordinates,
        step=step,
        state_id=f"dd112:audit:{step:g}",
        use_coloring=use_coloring,
    )
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    pattern = initializer_constraint_pattern(contract)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    names = initializer_variable_names(contract)
    unexpected = tuple(
        f"{contract.constraints[row].name} <- {names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    return InitializerJacobianAudit(
        step=float(step),
        matrix=matrix,
        rank=rank,
        condition=condition,
        singular_values=singular,
        zero_rows=tuple(
            contract.constraints[index].name
            for index in np.flatnonzero(row_norm <= coupling_tolerance)
        ),
        zero_columns=tuple(
            names[index]
            for index in np.flatnonzero(column_norm <= coupling_tolerance)
        ),
        unexpected_couplings=unexpected,
        color_count=color_count,
    )


def kkt_stationarity_inf_norm(
    numerical: InitializerNumericalSpec,
    coordinates: Sequence[float],
    constraint_jacobian: Sequence[Sequence[float]],
) -> float:
    gradient = initializer_objective_gradient(numerical, coordinates)
    jacobian = np.asarray(constraint_jacobian, dtype=float)
    multiplier, *_ = np.linalg.lstsq(jacobian.T, -gradient, rcond=None)
    return float(np.max(np.abs(gradient + jacobian.T @ multiplier)))


__all__ = [
    "InitializerConstraintEvaluation",
    "InitializerJacobianAudit",
    "InitializerNumericalSpec",
    "InitializerSolveOutcome",
    "InitializerSolveSettings",
    "audit_initializer_constraint_jacobian",
    "decode_initializer_coordinates",
    "evaluate_initializer_constraints",
    "initializer_constraint_jacobian",
    "initializer_constraint_pattern",
    "initializer_objective",
    "initializer_objective_gradient",
    "initializer_variable_names",
    "kkt_stationarity_inf_norm",
    "solve_equality_constrained_initializer",
]
