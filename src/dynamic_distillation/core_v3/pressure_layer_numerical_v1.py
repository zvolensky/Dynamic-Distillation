"""Live numerical kernel for the Core V3 algebraic pressure layer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    DynamicImplicitEvaluation,
    evaluate_dynamic_implicit_residual,
)
from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    PressureLayerContract,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    VAPOR_LINKS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)


GAS_CONSTANT_PSIA_FT3_LBMOL_R = 10.7316
PSF_PER_PSIA = 144.0


@dataclass(frozen=True)
class PressureLinkGeometry:
    active_area_ft2: float
    tray_area_ft2: float
    weir_height_in: float


@dataclass(frozen=True)
class PressureNumericalSpec:
    reference_pressure_psia: np.ndarray
    pressure_coordinate_scale_psia: float
    pressure_residual_scale_psia: float
    dry_tray_pressure_drop_coefficient: float
    component_mw_lbm_per_lbmol: np.ndarray
    link_geometry: tuple[PressureLinkGeometry, ...]


@dataclass(frozen=True)
class PressureDropEvaluation:
    raw_residual_psia: np.ndarray
    liquid_head_drop_psia: np.ndarray
    dry_tray_drop_psia: np.ndarray
    vapor_compressibility_factor: np.ndarray
    over_weir_head_ft: np.ndarray


@dataclass(frozen=True)
class PressureLayerEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    pressure_psia: np.ndarray
    base_evaluation: DynamicImplicitEvaluation
    pressure_drop: PressureDropEvaluation


@dataclass(frozen=True)
class PressureLayerJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]


def pressure_layer_variable_names(
    contract: PressureLayerContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )


def pressure_profile_from_coordinates(
    numerical: PressureNumericalSpec,
    pressure_coordinates: Sequence[float],
) -> np.ndarray:
    reference = np.asarray(numerical.reference_pressure_psia, dtype=float)
    coordinates = np.asarray(pressure_coordinates, dtype=float).reshape((-1,))
    if reference.shape != (len(VOLUME_IDS),) or coordinates.shape != (
        len(VOLUME_IDS) - 1,
    ):
        raise ValueError("pressure profile or coordinate shape is invalid")
    if (
        np.any(~np.isfinite(reference))
        or np.any(reference <= 0.0)
        or not np.isfinite(numerical.pressure_coordinate_scale_psia)
        or numerical.pressure_coordinate_scale_psia <= 0.0
    ):
        raise ValueError("pressure reference or scale is invalid")
    pressure = reference.copy()
    pressure[1:] += (
        float(numerical.pressure_coordinate_scale_psia) * coordinates
    )
    if np.any(~np.isfinite(pressure)) or np.any(pressure <= 0.0):
        raise RuntimeError("pressure layer produced non-positive pressure")
    if np.any(np.diff(pressure) <= 0.0):
        raise RuntimeError("pressure layer produced a non-ordered pressure profile")
    return pressure


def _validate_numerical_spec(numerical: PressureNumericalSpec) -> None:
    molecular_weight = np.asarray(
        numerical.component_mw_lbm_per_lbmol, dtype=float
    ).reshape((-1,))
    if (
        molecular_weight.size < 2
        or np.any(~np.isfinite(molecular_weight))
        or np.any(molecular_weight <= 0.0)
        or len(numerical.link_geometry) != len(VAPOR_LINKS)
        or not np.isfinite(numerical.pressure_residual_scale_psia)
        or numerical.pressure_residual_scale_psia <= 0.0
        or not np.isfinite(numerical.dry_tray_pressure_drop_coefficient)
        or numerical.dry_tray_pressure_drop_coefficient <= 0.0
    ):
        raise ValueError("pressure numerical specification is invalid")
    for geometry in numerical.link_geometry:
        if (
            geometry.active_area_ft2 <= 0.0
            or geometry.tray_area_ft2 <= 0.0
            or geometry.weir_height_in < 0.0
        ):
            raise ValueError("pressure-link geometry is invalid")


def _complete_pressure_drop(
    state: PhysicalState,
    liquid_density_lbmol_ft3: np.ndarray,
    pressure_psia: np.ndarray,
    numerical: PressureNumericalSpec,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    state_id: str,
    evaluation_kind: str,
) -> PressureDropEvaluation:
    molecular_weight = np.asarray(
        numerical.component_mw_lbm_per_lbmol, dtype=float
    )
    density = np.asarray(liquid_density_lbmol_ft3, dtype=float)
    residual = np.empty(len(VAPOR_LINKS), dtype=float)
    liquid_drop = np.empty_like(residual)
    dry_drop = np.empty_like(residual)
    z_factor = np.empty_like(residual)
    over_weir_head = np.empty_like(residual)
    for link_index, (source, destination, _symbol) in enumerate(VAPOR_LINKS):
        source_index = VOLUME_IDS.index(source)
        destination_index = VOLUME_IDS.index(destination)
        geometry = numerical.link_geometry[link_index]
        liquid_x = np.asarray(state.liquid_mole_fraction[source_index], dtype=float)
        vapor_y = np.asarray(
            state.vapor_mole_fraction[EQUILIBRIUM_VOLUME_IDS.index(source)],
            dtype=float,
        )
        rho_liquid_molar = float(density[source_index])
        if not np.isfinite(rho_liquid_molar) or rho_liquid_molar <= 0.0:
            raise RuntimeError("pressure layer received invalid liquid density")
        liquid_height = float(state.liquid_moles_lbmol[source_index]) / (
            rho_liquid_molar * float(geometry.tray_area_ft2)
        )
        over_weir_head[link_index] = (
            liquid_height - float(geometry.weir_height_in) / 12.0
        )
        if over_weir_head[link_index] <= 0.0:
            raise RuntimeError("pressure layer has no positive over-weir head")
        liquid_mw = float(np.dot(liquid_x, molecular_weight))
        vapor_mw = float(np.dot(vapor_y, molecular_weight))
        liquid_drop[link_index] = (
            rho_liquid_molar
            * liquid_mw
            * over_weir_head[link_index]
            / PSF_PER_PSIA
        )
        z_factor[link_index] = call_audit.vapor_compressibility_factor(
            provider,
            temperature_F=float(state.temperature_F[source_index]),
            pressure_psia=float(pressure_psia[source_index]),
            composition=vapor_y,
            caller=f"vapor_pressure_drop[{source}->{destination}]",
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        temperature_R = float(state.temperature_F[source_index]) + 459.67
        rho_vapor_molar = float(pressure_psia[source_index]) / (
            z_factor[link_index]
            * GAS_CONSTANT_PSIA_FT3_LBMOL_R
            * temperature_R
        )
        rho_vapor_mass = rho_vapor_molar * vapor_mw
        volumetric_rate_ft3_s = (
            float(state.vapor_flow_lbmolph[link_index])
            / 3600.0
            / rho_vapor_molar
        )
        velocity_ft_s = volumetric_rate_ft3_s / float(
            geometry.active_area_ft2
        )
        dry_drop[link_index] = (
            float(numerical.dry_tray_pressure_drop_coefficient)
            * rho_vapor_mass
            * velocity_ft_s**2
            / (2.0 * PSF_PER_PSIA)
        )
        residual[link_index] = (
            float(pressure_psia[source_index])
            - float(pressure_psia[destination_index])
            - liquid_drop[link_index]
            - dry_drop[link_index]
        )
    return PressureDropEvaluation(
        raw_residual_psia=residual,
        liquid_head_drop_psia=liquid_drop,
        dry_tray_drop_psia=dry_drop,
        vapor_compressibility_factor=z_factor,
        over_weir_head_ft=over_weir_head,
    )


def evaluate_pressure_layer_residual(
    contract: PressureLayerContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    rate_coordinates: Sequence[float],
    base_algebraic_coordinates: Sequence[float],
    pressure_coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> PressureLayerEvaluation:
    _validate_numerical_spec(numerical)
    pressure = pressure_profile_from_coordinates(numerical, pressure_coordinates)
    live_spec = replace(spec, pressure_psia=pressure)
    base = evaluate_dynamic_implicit_residual(
        contract.base_contract,
        live_spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory_lbmol,
        rate_coordinates=rate_coordinates,
        algebraic_coordinates=base_algebraic_coordinates,
        storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
        fixed_steady_scales=fixed_steady_scales,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    pressure_drop = _complete_pressure_drop(
        base.physical_state,
        base.steady_evaluation.properties.liquid_density_lbmol_ft3,
        pressure,
        numerical,
        provider,
        call_audit,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    pressure_scales = np.full(
        len(VAPOR_LINKS), float(numerical.pressure_residual_scale_psia)
    )
    raw = np.concatenate((base.raw, pressure_drop.raw_residual_psia))
    scales = np.concatenate((base.scales, pressure_scales))
    variable_names = pressure_layer_variable_names(contract)
    row_names = tuple(row.name for row in contract.rows)
    if raw.shape != scales.shape or raw.shape != (42,):
        raise RuntimeError("Core V3 pressure residual is not 42 x 42")
    return PressureLayerEvaluation(
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        row_names=row_names,
        variable_names=variable_names,
        pressure_psia=pressure,
        base_evaluation=base,
        pressure_drop=pressure_drop,
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


def _structural_pattern(contract: PressureLayerContract) -> np.ndarray:
    names = pressure_layer_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            pattern[row_index, index[dependency]] = True
    return pattern


def audit_pressure_layer_jacobian(
    contract: PressureLayerContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    root_base_algebraic_coordinates: Sequence[float],
    pressure_coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    numerical: PressureNumericalSpec,
    step: float,
    coupling_tolerance: float,
    state_id: str,
) -> PressureLayerJacobianAudit:
    rate_count = len(contract.derivative_variables)
    base_algebraic_count = len(contract.base_contract.algebraic_variables)
    point = np.concatenate(
        (
            np.zeros(rate_count, dtype=float),
            np.asarray(root_base_algebraic_coordinates, dtype=float),
            np.asarray(pressure_coordinates, dtype=float),
        )
    )
    if point.shape != (42,) or not np.isfinite(step) or step <= 0.0:
        raise ValueError("pressure Jacobian point or step is invalid")
    matrix = np.empty((42, 42), dtype=float)
    for column in range(42):
        delta = np.zeros_like(point)
        delta[column] = float(step)

        def evaluate(candidate: np.ndarray, suffix: str) -> np.ndarray:
            return evaluate_pressure_layer_residual(
                contract,
                spec,
                reference,
                template,
                provider,
                call_audit,
                inventory_lbmol=inventory_lbmol,
                rate_coordinates=candidate[:rate_count],
                base_algebraic_coordinates=candidate[
                    rate_count : rate_count + base_algebraic_count
                ],
                pressure_coordinates=candidate[
                    rate_count + base_algebraic_count :
                ],
                storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
                fixed_steady_scales=fixed_steady_scales,
                numerical=numerical,
                state_id=f"{state_id}:{column}:{suffix}",
                evaluation_kind="jacobian",
            ).scaled

        matrix[:, column] = (
            evaluate(point + delta, "plus") - evaluate(point - delta, "minus")
        ) / (2.0 * float(step))
    pattern = _structural_pattern(contract)
    variable_names = pressure_layer_variable_names(contract)
    unexpected = tuple(
        f"{contract.rows[row].name} <- {variable_names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    rank, condition, singular = _rank_condition_singular(matrix)
    return PressureLayerJacobianAudit(
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


__all__ = [
    "PressureDropEvaluation",
    "PressureLayerEvaluation",
    "PressureLayerJacobianAudit",
    "PressureLinkGeometry",
    "PressureNumericalSpec",
    "audit_pressure_layer_jacobian",
    "evaluate_pressure_layer_residual",
    "pressure_layer_variable_names",
    "pressure_profile_from_coordinates",
]
