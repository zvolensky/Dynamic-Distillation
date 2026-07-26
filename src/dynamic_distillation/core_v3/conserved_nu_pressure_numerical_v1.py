"""Live residual kernel for the conserved-N/U algebraic-pressure DAE."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Sequence

import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    ConservedNUPressureDAEContract,
)
from dynamic_distillation.core_v3.implicit_step_v1 import governing_storage_vector
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLayerEvaluation,
    PressureNumericalSpec,
    evaluate_pressure_layer_residual,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


@dataclass(frozen=True)
class ConservedNUPressureEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    component_rate_lbmolph: np.ndarray
    internal_energy_rate_BTUph: np.ndarray
    lower_internal_energy_state_BTU: np.ndarray
    live_internal_energy_BTU: np.ndarray
    storage_closure_BTU: np.ndarray
    pressure_evaluation: PressureLayerEvaluation


@dataclass(frozen=True)
class ConservedNUJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]
    color_count: int


def nu_pressure_variable_names(
    contract: ConservedNUPressureDAEContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )


def nu_pressure_pattern(contract: ConservedNUPressureDAEContract) -> np.ndarray:
    names = nu_pressure_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            pattern[row_index, index[dependency]] = True
    return pattern


def _block_indices(
    contract: ConservedNUPressureDAEContract,
    block: str,
) -> np.ndarray:
    return np.asarray(
        [index for index, row in enumerate(contract.rows) if row.block == block],
        dtype=int,
    )


def evaluate_conserved_nu_pressure_residual(
    contract: ConservedNUPressureDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    lower_internal_energy_BTU: Sequence[float],
    top_storage_gradient_BTU_lbmol: Sequence[float],
    energy_rate_scales_BTUph: Sequence[float],
    solve_coordinates: Sequence[float],
    fixed_steady_scales: Sequence[float],
    storage_scales_BTU: Sequence[float],
    numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> ConservedNUPressureEvaluation:
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("conserved-N/U pressure coordinates are invalid")
    inventory = np.asarray(inventory_lbmol, dtype=float)
    expected_inventory = (len(VOLUME_IDS), len(spec.component_names))
    if inventory.shape != expected_inventory or np.any(inventory <= 0.0):
        raise ValueError("conserved-N/U inventory is invalid")
    lower_u = np.asarray(lower_internal_energy_BTU, dtype=float).reshape((-1,))
    top_gradient = np.asarray(top_storage_gradient_BTU_lbmol, dtype=float).reshape((-1,))
    energy_scales = np.asarray(energy_rate_scales_BTUph, dtype=float).reshape((-1,))
    storage_scales = np.asarray(storage_scales_BTU, dtype=float).reshape((-1,))
    lower_count = len(VOLUME_IDS) - 1
    if (
        lower_u.shape != (lower_count,)
        or top_gradient.shape != (len(spec.component_names),)
        or energy_scales.shape != (lower_count,)
        or storage_scales.shape != (lower_count,)
        or np.any(~np.isfinite(lower_u))
        or np.any(~np.isfinite(top_gradient))
        or np.any(~np.isfinite(energy_scales))
        or np.any(energy_scales <= 0.0)
        or np.any(~np.isfinite(storage_scales))
        or np.any(storage_scales <= 0.0)
    ):
        raise ValueError("conserved-N/U energy state or scale is invalid")

    component_rate_count = len(VOLUME_IDS) * len(spec.component_names)
    energy_rate_count = lower_count
    base_algebraic_count = len(
        contract.pressure_dae.pressure_contract.base_contract.algebraic_variables
    )
    component_coordinates = point[:component_rate_count]
    energy_coordinates = point[
        component_rate_count : component_rate_count + energy_rate_count
    ]
    algebraic_start = component_rate_count + energy_rate_count
    base_algebraic = point[
        algebraic_start : algebraic_start + base_algebraic_count
    ]
    pressure_coordinates = point[algebraic_start + base_algebraic_count :]
    pressure = evaluate_pressure_layer_residual(
        contract.pressure_dae.pressure_contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        rate_coordinates=component_coordinates,
        base_algebraic_coordinates=base_algebraic,
        pressure_coordinates=pressure_coordinates,
        storage_gradient_BTU_lbmol=np.zeros_like(inventory),
        fixed_steady_scales=fixed_steady_scales,
        numerical=numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    raw = np.asarray(pressure.raw, dtype=float).copy()
    energy_indices = _block_indices(contract, "energy_balance")
    if energy_indices.shape != (len(VOLUME_IDS),):
        raise RuntimeError("conserved-N/U contract has invalid energy rows")
    component_rate = np.asarray(
        pressure.base_evaluation.component_rate_lbmolph, dtype=float
    )
    top_storage_rate = float(np.dot(top_gradient, component_rate[0]))
    lower_storage_rate = energy_coordinates * energy_scales
    raw[energy_indices[0]] += top_storage_rate
    raw[energy_indices[1:]] += lower_storage_rate

    live_spec = replace(spec, pressure_psia=pressure.pressure_psia)
    live_storage = governing_storage_vector(
        live_spec,
        pressure.base_evaluation,
        inventory,
    )
    storage_closure = lower_u - live_storage[1:]
    raw = np.concatenate((raw, storage_closure))
    scales = np.concatenate((pressure.scales, storage_scales))
    if raw.shape != scales.shape or raw.shape != (len(contract.rows),):
        raise RuntimeError("conserved-N/U pressure residual has invalid shape")
    return ConservedNUPressureEvaluation(
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        row_names=tuple(row.name for row in contract.rows),
        variable_names=nu_pressure_variable_names(contract),
        component_rate_lbmolph=component_rate,
        internal_energy_rate_BTUph=np.concatenate(
            (np.asarray((top_storage_rate,)), lower_storage_rate)
        ),
        lower_internal_energy_state_BTU=lower_u.copy(),
        live_internal_energy_BTU=live_storage,
        storage_closure_BTU=storage_closure,
        pressure_evaluation=pressure,
    )


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def audit_conserved_nu_leading_jacobian(
    contract: ConservedNUPressureDAEContract,
    objective: Callable[[np.ndarray, str], ConservedNUPressureEvaluation],
    point: Sequence[float],
    *,
    step: float,
    coupling_tolerance: float,
    use_coloring: bool = True,
) -> ConservedNUJacobianAudit:
    pattern = nu_pressure_pattern(contract)
    coordinates = np.asarray(point, dtype=float).reshape((-1,))
    if use_coloring:
        matrix, groups = colored_central_difference_jacobian(
            lambda candidate, state_id: objective(candidate, state_id).scaled,
            coordinates,
            pattern=pattern,
            step=step,
            state_id=f"dd109:leading:{step:g}",
        )
    else:
        matrix = np.empty(pattern.shape, dtype=float)
        for column in range(coordinates.size):
            delta = np.zeros_like(coordinates)
            delta[column] = float(step)
            plus = objective(
                coordinates + delta,
                f"dd109:leading_full:{step:g}:{column}:plus",
            ).scaled
            minus = objective(
                coordinates - delta,
                f"dd109:leading_full:{step:g}:{column}:minus",
            ).scaled
            matrix[:, column] = (plus - minus) / (2.0 * float(step))
        groups = tuple((column,) for column in range(coordinates.size))
    rank, condition, singular = _rank_condition(matrix)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    names = nu_pressure_variable_names(contract)
    unexpected = tuple(
        f"{contract.rows[row].name} <- {names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    return ConservedNUJacobianAudit(
        step=float(step),
        matrix=matrix,
        rank=rank,
        condition=condition,
        singular_values=singular,
        zero_rows=tuple(
            contract.rows[index].name
            for index in np.flatnonzero(row_norm <= coupling_tolerance)
        ),
        zero_columns=tuple(
            names[index]
            for index in np.flatnonzero(column_norm <= coupling_tolerance)
        ),
        unexpected_couplings=unexpected,
        color_count=len(groups),
    )


__all__ = [
    "ConservedNUJacobianAudit",
    "ConservedNUPressureEvaluation",
    "audit_conserved_nu_leading_jacobian",
    "evaluate_conserved_nu_pressure_residual",
    "nu_pressure_pattern",
    "nu_pressure_variable_names",
]
