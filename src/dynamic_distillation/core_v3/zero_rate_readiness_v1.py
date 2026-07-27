"""Live numerical readiness kernel for the Core V3 zero-rate system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    ConservedNUPressureInitializerContract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerConstraintEvaluation,
    InitializerNumericalSpec,
    evaluate_initializer_constraints,
    initializer_constraint_pattern,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


RATE_BLOCKS = frozenset(("component_inventory_rate", "internal_energy_rate"))
TERMINAL_TARGET_BLOCK = "terminal_total_inventory"


@dataclass(frozen=True)
class ZeroRateReadinessEvaluation:
    scaled: np.ndarray
    dae_scaled: np.ndarray
    terminal_scaled: np.ndarray
    row_names: tuple[str, ...]
    coordinates: np.ndarray
    expanded_coordinates: np.ndarray
    component_total_residual_lbmol: np.ndarray
    stored_energy_residual_BTU: float
    terminal_total_residual_lbmol: np.ndarray
    full_evaluation: InitializerConstraintEvaluation


@dataclass(frozen=True)
class ZeroRateJacobianAudit:
    step: float
    matrix: np.ndarray
    dae_matrix: np.ndarray
    augmented_rank: int
    dae_rank: int
    augmented_condition: float
    dae_condition: float
    augmented_singular_values: np.ndarray
    dae_singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]
    color_count: int
    left_null_projection_norm: float


def zero_rate_column_indices(
    contract: ConservedNUPressureInitializerContract,
) -> tuple[int, ...]:
    variables = (
        *contract.state_variables,
        *contract.derivative_variables,
        *contract.algebraic_variables,
    )
    return tuple(
        index for index, variable in enumerate(variables) if variable.block not in RATE_BLOCKS
    )


def zero_rate_row_indices(
    contract: ConservedNUPressureInitializerContract,
) -> tuple[int, ...]:
    dae = tuple(range(len(contract.pressure_dae.rows)))
    terminal = tuple(
        index
        for index, row in enumerate(contract.constraints)
        if row.block == TERMINAL_TARGET_BLOCK
    )
    if len(terminal) != 2:
        raise ValueError("zero-rate readiness requires exactly two terminal targets")
    return (*dae, *terminal)


def zero_rate_variable_names(
    contract: ConservedNUPressureInitializerContract,
) -> tuple[str, ...]:
    variables = (
        *contract.state_variables,
        *contract.derivative_variables,
        *contract.algebraic_variables,
    )
    return tuple(variables[index].name for index in zero_rate_column_indices(contract))


def zero_rate_row_names(
    contract: ConservedNUPressureInitializerContract,
) -> tuple[str, ...]:
    return tuple(contract.constraints[index].name for index in zero_rate_row_indices(contract))


def zero_rate_pattern(
    contract: ConservedNUPressureInitializerContract,
) -> np.ndarray:
    return np.asarray(initializer_constraint_pattern(contract), dtype=bool)[
        np.ix_(zero_rate_row_indices(contract), zero_rate_column_indices(contract))
    ]


def expand_zero_rate_coordinates(
    contract: ConservedNUPressureInitializerContract,
    coordinates: Sequence[float],
) -> np.ndarray:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    state_count = len(contract.state_variables)
    rate_count = len(contract.derivative_variables)
    expected = state_count + len(contract.algebraic_variables)
    if point.shape != (expected,) or np.any(~np.isfinite(point)):
        raise ValueError("zero-rate coordinates are invalid")
    return np.concatenate(
        (point[:state_count], np.zeros(rate_count), point[state_count:])
    )


def evaluate_zero_rate_readiness(
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
) -> ZeroRateReadinessEvaluation:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    expanded = expand_zero_rate_coordinates(contract, point)
    full = evaluate_initializer_constraints(
        contract,
        numerical,
        spec,
        reference,
        template,
        provider,
        call_audit,
        coordinates=expanded,
        top_storage_gradient_BTU_lbmol=top_storage_gradient_BTU_lbmol,
        energy_rate_scales_BTUph=energy_rate_scales_BTUph,
        fixed_steady_scales=fixed_steady_scales,
        storage_scales_BTU=storage_scales_BTU,
        pressure_numerical=pressure_numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    dae_count = len(contract.pressure_dae.rows)
    selected = np.asarray(full.scaled, dtype=float)[list(zero_rate_row_indices(contract))]
    return ZeroRateReadinessEvaluation(
        scaled=selected,
        dae_scaled=selected[:dae_count],
        terminal_scaled=selected[dae_count:],
        row_names=zero_rate_row_names(contract),
        coordinates=point.copy(),
        expanded_coordinates=expanded,
        component_total_residual_lbmol=full.component_total_residual_lbmol.copy(),
        stored_energy_residual_BTU=float(full.stored_energy_residual_BTU),
        terminal_total_residual_lbmol=full.terminal_total_residual_lbmol.copy(),
        full_evaluation=full,
    )


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return rank, condition, singular


def audit_zero_rate_jacobian(
    contract: ConservedNUPressureInitializerContract,
    objective: Callable[[np.ndarray, str], np.ndarray],
    coordinates: Sequence[float],
    residual: Sequence[float],
    *,
    step: float,
    coupling_tolerance: float,
    state_id: str,
) -> ZeroRateJacobianAudit:
    pattern = zero_rate_pattern(contract)
    matrix, groups = colored_central_difference_jacobian(
        objective,
        coordinates,
        pattern=pattern,
        step=step,
        state_id=state_id,
    )
    dae_count = len(contract.pressure_dae.rows)
    dae_matrix = matrix[:dae_count]
    augmented_rank, augmented_condition, augmented_singular = _rank_condition(matrix)
    dae_rank, dae_condition, dae_singular = _rank_condition(dae_matrix)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    names = zero_rate_variable_names(contract)
    row_names = zero_rate_row_names(contract)
    unexpected = tuple(
        f"{row_names[row]} <- {names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    left_vectors = np.linalg.svd(matrix, full_matrices=True)[0][:, matrix.shape[1] :]
    projection = float(
        np.linalg.norm(left_vectors.T @ np.asarray(residual, dtype=float))
        if left_vectors.size
        else 0.0
    )
    return ZeroRateJacobianAudit(
        step=float(step),
        matrix=matrix,
        dae_matrix=dae_matrix,
        augmented_rank=augmented_rank,
        dae_rank=dae_rank,
        augmented_condition=augmented_condition,
        dae_condition=dae_condition,
        augmented_singular_values=augmented_singular,
        dae_singular_values=dae_singular,
        zero_rows=tuple(row_names[index] for index in np.flatnonzero(row_norm <= coupling_tolerance)),
        zero_columns=tuple(names[index] for index in np.flatnonzero(column_norm <= coupling_tolerance)),
        unexpected_couplings=unexpected,
        color_count=len(groups),
        left_null_projection_norm=projection,
    )


__all__ = [
    "ZeroRateJacobianAudit",
    "ZeroRateReadinessEvaluation",
    "audit_zero_rate_jacobian",
    "evaluate_zero_rate_readiness",
    "expand_zero_rate_coordinates",
    "zero_rate_column_indices",
    "zero_rate_pattern",
    "zero_rate_row_indices",
    "zero_rate_row_names",
    "zero_rate_variable_names",
]
