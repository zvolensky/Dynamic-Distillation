"""Live numerical audit kernel for the Core V3 dynamic DAE contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    DynamicDAEContract,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
    ResidualEvaluation,
    coordinate_layout,
    decode_coordinates,
    encode_state,
    evaluate_residual,
    solve_local_bubble,
)
from dynamic_distillation.uv_flash_stage_v1 import BTU_PER_PSI_FT3


@dataclass(frozen=True)
class StorageGradientStep:
    relative_step: float
    internal_energy_BTU: np.ndarray
    gradient_BTU_lbmol: np.ndarray
    maximum_bubble_residual: float


@dataclass(frozen=True)
class StorageGradientAudit:
    steps: tuple[StorageGradientStep, ...]
    maximum_relative_change: float
    all_finite: bool


@dataclass(frozen=True)
class DynamicImplicitEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    row_names: tuple[str, ...]
    physical_state: PhysicalState
    steady_evaluation: ResidualEvaluation
    component_rate_lbmolph: np.ndarray
    energy_storage_rate_BTUph: np.ndarray


@dataclass(frozen=True)
class LeadingJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]


def inventory_from_state(state: PhysicalState) -> np.ndarray:
    return (
        np.asarray(state.liquid_moles_lbmol, dtype=float)[:, None]
        * np.asarray(state.liquid_mole_fraction, dtype=float)
    )


def dynamic_algebraic_indices(spec: OperatingSpec) -> np.ndarray:
    layout = coordinate_layout(spec)
    return np.asarray(
        (
            *range(layout.temperature.start, layout.temperature.stop),
            *range(layout.vapor_alr.start, layout.vapor_alr.stop),
            *range(layout.liquid_flows.start, layout.liquid_flows.stop),
            *range(layout.vapor_flows.start, layout.vapor_flows.stop),
            *range(layout.bubble_alr.start, layout.bubble_alr.stop),
            layout.condenser_duty,
        ),
        dtype=int,
    )


def dynamic_algebraic_coordinates(
    spec: OperatingSpec,
    reference: NumericalReference,
    state: PhysicalState,
) -> np.ndarray:
    return encode_state(spec, reference, state)[dynamic_algebraic_indices(spec)]


def _state_from_inventory_and_algebraic(
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    inventory_lbmol: Sequence[Sequence[float]],
    algebraic_coordinates: Sequence[float],
) -> PhysicalState:
    inventory = np.asarray(inventory_lbmol, dtype=float)
    expected = (len(VOLUME_IDS), len(spec.component_names))
    if inventory.shape != expected or np.any(~np.isfinite(inventory)):
        raise ValueError("dynamic inventory has an invalid shape or value")
    if np.any(inventory <= 0.0):
        raise ValueError("dynamic component inventories must be positive")
    totals = np.sum(inventory, axis=1)
    composition = inventory / totals[:, None]
    inventory_state = PhysicalState(
        liquid_moles_lbmol=totals,
        liquid_mole_fraction=composition,
        temperature_F=np.asarray(template.temperature_F, dtype=float),
        vapor_mole_fraction=np.asarray(
            template.vapor_mole_fraction, dtype=float
        ),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            template.hydraulic_liquid_flow_lbmolph, dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(template.vapor_flow_lbmolph, dtype=float),
        distillate_lbmolph=float(template.distillate_lbmolph),
        bottoms_lbmolph=float(template.bottoms_lbmolph),
        bubble_vapor_mole_fraction=np.asarray(
            template.bubble_vapor_mole_fraction, dtype=float
        ),
        condenser_duty_BTUph=float(template.condenser_duty_BTUph),
    )
    full = encode_state(spec, reference, inventory_state)
    indices = dynamic_algebraic_indices(spec)
    algebraic = np.asarray(algebraic_coordinates, dtype=float).reshape((-1,))
    if algebraic.shape != indices.shape or np.any(~np.isfinite(algebraic)):
        raise ValueError("dynamic algebraic coordinates are invalid")
    full[indices] = algebraic
    state = decode_coordinates(spec, reference, full)
    if not np.isclose(state.distillate_lbmolph, template.distillate_lbmolph):
        raise RuntimeError("dynamic mapping changed fixed distillate flow")
    if not np.isclose(state.bottoms_lbmolph, template.bottoms_lbmolph):
        raise RuntimeError("dynamic mapping changed fixed bottoms flow")
    return state


def _saturated_liquid_internal_energy(
    spec: OperatingSpec,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    volume_index: int,
    inventory_lbmol: np.ndarray,
    temperature_guess_F: float,
    vapor_guess: np.ndarray,
    state_id: str,
) -> tuple[float, float]:
    total = float(np.sum(inventory_lbmol))
    if total <= 0.0 or np.any(inventory_lbmol <= 0.0):
        raise ValueError("storage derivative requires positive inventory")
    liquid_x = np.asarray(inventory_lbmol, dtype=float) / total
    bubble = solve_local_bubble(
        provider,
        call_audit,
        pressure_psia=float(spec.pressure_psia[volume_index]),
        liquid_x=liquid_x,
        temperature_guess_F=float(temperature_guess_F),
        vapor_guess=vapor_guess,
        state_id=state_id,
        evaluation_kind="validation",
    )
    if not bubble.success or bubble.residual_inf_norm >= 1.0e-10:
        raise RuntimeError("storage derivative bubble reconstruction failed")
    volume = VOLUME_IDS[volume_index]
    enthalpy = call_audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=bubble.temperature_F,
        pressure_psia=float(spec.pressure_psia[volume_index]),
        composition=liquid_x,
        caller=f"dynamic_energy_storage[{volume}]",
        state_id=state_id,
        evaluation_kind="validation",
    )
    density = call_audit.liquid_density(
        provider,
        temperature_F=bubble.temperature_F,
        pressure_psia=float(spec.pressure_psia[volume_index]),
        composition=liquid_x,
        caller=f"dynamic_energy_storage[{volume}]",
        state_id=state_id,
        evaluation_kind="validation",
    )
    molar_volume = 1.0 / float(density)
    internal_energy = float(enthalpy) - (
        float(spec.pressure_psia[volume_index])
        * molar_volume
        * BTU_PER_PSI_FT3
    )
    return total * internal_energy, bubble.residual_inf_norm


def audit_storage_gradient(
    spec: OperatingSpec,
    state: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    relative_steps: Sequence[float],
    state_id: str,
) -> StorageGradientAudit:
    inventory = inventory_from_state(state)
    vapor_guesses = (
        np.asarray(state.bubble_vapor_mole_fraction, dtype=float),
        *(
            np.asarray(row, dtype=float)
            for row in np.asarray(state.vapor_mole_fraction, dtype=float)
        ),
    )
    results: list[StorageGradientStep] = []
    for relative_step in relative_steps:
        if not np.isfinite(relative_step) or relative_step <= 0.0:
            raise ValueError("storage derivative step must be positive")
        storage = np.empty(len(VOLUME_IDS), dtype=float)
        gradient = np.empty_like(inventory)
        maximum_bubble = 0.0
        for volume_index, volume in enumerate(VOLUME_IDS):
            storage[volume_index], residual = _saturated_liquid_internal_energy(
                spec,
                provider,
                call_audit,
                volume_index=volume_index,
                inventory_lbmol=inventory[volume_index],
                temperature_guess_F=float(state.temperature_F[volume_index]),
                vapor_guess=vapor_guesses[volume_index],
                state_id=f"{state_id}:{relative_step:g}:{volume}:base",
            )
            maximum_bubble = max(maximum_bubble, residual)
            total = float(np.sum(inventory[volume_index]))
            floor = max(total / len(spec.component_names), 1.0)
            for component_index in range(len(spec.component_names)):
                delta = float(relative_step) * max(
                    abs(float(inventory[volume_index, component_index])),
                    floor,
                )
                plus = inventory[volume_index].copy()
                minus = inventory[volume_index].copy()
                plus[component_index] += delta
                minus[component_index] -= delta
                if minus[component_index] <= 0.0:
                    raise RuntimeError("storage derivative perturbation is nonpositive")
                u_plus, residual_plus = _saturated_liquid_internal_energy(
                    spec,
                    provider,
                    call_audit,
                    volume_index=volume_index,
                    inventory_lbmol=plus,
                    temperature_guess_F=float(state.temperature_F[volume_index]),
                    vapor_guess=vapor_guesses[volume_index],
                    state_id=(
                        f"{state_id}:{relative_step:g}:{volume}:"
                        f"{component_index}:plus"
                    ),
                )
                u_minus, residual_minus = _saturated_liquid_internal_energy(
                    spec,
                    provider,
                    call_audit,
                    volume_index=volume_index,
                    inventory_lbmol=minus,
                    temperature_guess_F=float(state.temperature_F[volume_index]),
                    vapor_guess=vapor_guesses[volume_index],
                    state_id=(
                        f"{state_id}:{relative_step:g}:{volume}:"
                        f"{component_index}:minus"
                    ),
                )
                gradient[volume_index, component_index] = (
                    u_plus - u_minus
                ) / (2.0 * delta)
                maximum_bubble = max(
                    maximum_bubble, residual_plus, residual_minus
                )
        results.append(
            StorageGradientStep(
                relative_step=float(relative_step),
                internal_energy_BTU=storage,
                gradient_BTU_lbmol=gradient,
                maximum_bubble_residual=float(maximum_bubble),
            )
        )
    maximum_change = 0.0
    if len(results) > 1:
        baseline = results[0].gradient_BTU_lbmol
        for result in results[1:]:
            denominator = np.maximum.reduce(
                (
                    np.abs(baseline),
                    np.abs(result.gradient_BTU_lbmol),
                    np.ones_like(baseline),
                )
            )
            maximum_change = max(
                maximum_change,
                float(
                    np.max(
                        np.abs(result.gradient_BTU_lbmol - baseline)
                        / denominator
                    )
                ),
            )
    finite = all(
        np.all(np.isfinite(result.internal_energy_BTU))
        and np.all(np.isfinite(result.gradient_BTU_lbmol))
        for result in results
    )
    return StorageGradientAudit(
        steps=tuple(results),
        maximum_relative_change=float(maximum_change),
        all_finite=bool(finite),
    )


def _steady_rows_by_name(
    evaluation: ResidualEvaluation,
) -> dict[str, int]:
    return {row.name: index for index, row in enumerate(evaluation.rows)}


def _steady_row_name(contract_row_name: str) -> str:
    if contract_row_name.startswith("full_phase_equilibrium["):
        return contract_row_name.replace(
            "full_phase_equilibrium[", "phase_fugacity[", 1
        )
    return contract_row_name


def evaluate_dynamic_implicit_residual(
    contract: DynamicDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    rate_coordinates: Sequence[float],
    algebraic_coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> DynamicImplicitEvaluation:
    state = _state_from_inventory_and_algebraic(
        spec,
        reference,
        template,
        inventory_lbmol,
        algebraic_coordinates,
    )
    full_coordinates = encode_state(spec, reference, state)
    steady = evaluate_residual(
        spec,
        reference,
        provider,
        call_audit,
        full_coordinates,
        fixed_scales=fixed_steady_scales,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    by_name = _steady_rows_by_name(steady)
    component_names = tuple(
        row.name for row in contract.rows if row.block == "component_balance"
    )
    component_scales = np.asarray(
        [
            steady.scales[by_name[_steady_row_name(name)]]
            for name in component_names
        ],
        dtype=float,
    ).reshape((len(VOLUME_IDS), len(spec.component_names)))
    rates = np.asarray(rate_coordinates, dtype=float).reshape(
        component_scales.shape
    ) * component_scales
    gradient = np.asarray(storage_gradient_BTU_lbmol, dtype=float)
    if gradient.shape != rates.shape or np.any(~np.isfinite(gradient)):
        raise ValueError("storage gradient shape or values are invalid")
    energy_storage_rate = np.sum(gradient * rates, axis=1)

    raw: list[float] = []
    scales: list[float] = []
    component_index = 0
    energy_index = 0
    for row in contract.rows:
        steady_index = by_name[_steady_row_name(row.name)]
        value = float(steady.raw[steady_index])
        if row.block == "component_balance":
            value = float(rates.reshape((-1,))[component_index]) - value
            component_index += 1
        elif row.block == "energy_balance":
            value = float(energy_storage_rate[energy_index]) - value
            energy_index += 1
        raw.append(value)
        scales.append(float(steady.scales[steady_index]))
    raw_array = np.asarray(raw, dtype=float)
    scale_array = np.asarray(scales, dtype=float)
    return DynamicImplicitEvaluation(
        raw=raw_array,
        scaled=raw_array / scale_array,
        scales=scale_array,
        row_names=tuple(row.name for row in contract.rows),
        physical_state=state,
        steady_evaluation=steady,
        component_rate_lbmolph=rates,
        energy_storage_rate_BTUph=energy_storage_rate,
    )


def _rank_condition_singular(
    matrix: np.ndarray,
) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def _contract_pattern(
    contract: DynamicDAEContract,
) -> tuple[np.ndarray, tuple[str, ...]]:
    variables = (
        *contract.derivative_variables,
        *contract.algebraic_variables,
    )
    names = tuple(variable.name for variable in variables)
    index = {name: position for position, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            pattern[row_index, index[dependency]] = True
    return pattern, names


def audit_leading_jacobian(
    contract: DynamicDAEContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    root_algebraic_coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    step: float,
    coupling_tolerance: float,
    state_id: str,
) -> LeadingJacobianAudit:
    rate_count = len(contract.derivative_variables)
    algebraic = np.asarray(root_algebraic_coordinates, dtype=float).reshape((-1,))
    point = np.concatenate((np.zeros(rate_count, dtype=float), algebraic))
    matrix = np.empty((len(contract.rows), point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = evaluate_dynamic_implicit_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            rate_coordinates=point[:rate_count] + delta[:rate_count],
            algebraic_coordinates=point[rate_count:] + delta[rate_count:],
            storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{state_id}:{column}:plus",
            evaluation_kind="jacobian",
        ).scaled
        minus = evaluate_dynamic_implicit_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            rate_coordinates=point[:rate_count] - delta[:rate_count],
            algebraic_coordinates=point[rate_count:] - delta[rate_count:],
            storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{state_id}:{column}:minus",
            evaluation_kind="jacobian",
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    pattern, variable_names = _contract_pattern(contract)
    unexpected = tuple(
        f"{contract.rows[row].name} <- {variable_names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    rank, condition, singular = _rank_condition_singular(matrix)
    return LeadingJacobianAudit(
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
            variable_names[index]
            for index in np.flatnonzero(column_norm <= coupling_tolerance)
        ),
        unexpected_couplings=unexpected,
    )
