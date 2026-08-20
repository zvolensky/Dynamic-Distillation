"""Complete implicit residual for the Core V3 vapor-holdup successor."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    contract_sparsity_pattern,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    GAS_CONSTANT_PSIA_FT3_LBMOL_R,
    PSF_PER_PSIA,
    PressureLinkGeometry,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    HydraulicGeometry,
    _francis_flow,
)
from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (
    TwoPhaseBalanceEvaluation,
    TwoPhaseTransportEvaluation,
    VaporHoldupBalanceInputs,
    evaluate_two_phase_balances,
    evaluate_two_phase_transport,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    VaporHoldupDAEContract,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    VaporControlVolumeGeometry,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (
    VaporHoldupPropertyEvaluation,
    evaluate_vapor_holdup_trial_properties,
)


@dataclass(frozen=True)
class VaporHoldupImplicitReference:
    liquid_component_inventory_lbmol: np.ndarray
    vapor_component_inventory_lbmol: np.ndarray
    phase_transfer_lbmolph: np.ndarray
    phase_transfer_scale_lbmolph: np.ndarray
    temperature_F: np.ndarray
    pressure_psia: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    condenser_duty_BTUph: float
    total_stored_energy_BTU: np.ndarray


@dataclass(frozen=True)
class VaporHoldupImplicitNumericalSpec:
    timestep_sec: float
    temperature_coordinate_scale_F: float
    pressure_coordinate_scale_psia: float
    dry_tray_pressure_drop_coefficient: float
    component_mw_lbm_per_lbmol: np.ndarray
    pressure_link_geometry: tuple[PressureLinkGeometry, ...]
    top_pressure_anchor_psia: float
    component_residual_scale_lbmolph: np.ndarray
    energy_residual_scale_BTUph: float
    pressure_residual_scale_psia: float


@dataclass(frozen=True)
class VaporHoldupImplicitEndpoint:
    liquid_component_inventory_lbmol: np.ndarray
    vapor_component_inventory_lbmol: np.ndarray
    liquid_component_rate_lbmolph: np.ndarray
    vapor_component_rate_lbmolph: np.ndarray
    phase_transfer_lbmolph: np.ndarray
    temperature_F: np.ndarray
    pressure_psia: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    condenser_duty_BTUph: float


@dataclass(frozen=True)
class VaporPressureDropEvaluation:
    residual_psia: np.ndarray
    liquid_head_drop_psia: np.ndarray
    dry_tray_drop_psia: np.ndarray
    over_weir_head_ft: np.ndarray


@dataclass(frozen=True)
class VaporHoldupImplicitEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    endpoint: VaporHoldupImplicitEndpoint
    properties: VaporHoldupPropertyEvaluation
    transport: TwoPhaseTransportEvaluation
    balances: TwoPhaseBalanceEvaluation
    fugacity_residual: np.ndarray
    francis_residual_lbmolph: np.ndarray
    pressure_drop: VaporPressureDropEvaluation
    pressure_anchor_residual_psia: float


def vapor_holdup_variable_names(
    contract: VaporHoldupDAEContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )


def vapor_holdup_structural_pattern(
    contract: VaporHoldupDAEContract,
) -> np.ndarray:
    pattern, names = contract_sparsity_pattern(
        contract,
        include_state_rate_dependencies=True,
    )
    if names != vapor_holdup_variable_names(contract):
        raise RuntimeError("vapor-holdup variable registry changed during coloring")
    return pattern


def _positive_array(values: Sequence[float] | Sequence[Sequence[float]], name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if np.any(~np.isfinite(result)) or np.any(result <= 0.0):
        raise ValueError(f"{name} must be positive and finite")
    return result


def validate_vapor_holdup_implicit_problem(
    contract: VaporHoldupDAEContract,
    geometry: Sequence[VaporControlVolumeGeometry],
    reference: VaporHoldupImplicitReference,
    balance_inputs: VaporHoldupBalanceInputs,
    hydraulic_geometry: Sequence[HydraulicGeometry],
    numerical: VaporHoldupImplicitNumericalSpec,
) -> None:
    topology = contract.topology.column
    volume_count = len(topology.volume_ids)
    component_count = len(contract.component_names)
    expected_inventory_shape = (volume_count, component_count)
    if reference.liquid_component_inventory_lbmol.shape != expected_inventory_shape:
        raise ValueError("reference liquid inventory shape is invalid")
    if reference.vapor_component_inventory_lbmol.shape != expected_inventory_shape:
        raise ValueError("reference vapor inventory shape is invalid")
    _positive_array(reference.liquid_component_inventory_lbmol, "liquid inventory")
    _positive_array(reference.vapor_component_inventory_lbmol, "vapor inventory")
    if reference.phase_transfer_lbmolph.shape != expected_inventory_shape:
        raise ValueError("reference phase-transfer shape is invalid")
    if reference.phase_transfer_scale_lbmolph.shape != expected_inventory_shape:
        raise ValueError("phase-transfer scale shape is invalid")
    _positive_array(reference.phase_transfer_scale_lbmolph, "phase-transfer scale")
    one_per_volume = (
        reference.temperature_F,
        reference.pressure_psia,
        reference.total_stored_energy_BTU,
    )
    if any(np.asarray(values).shape != (volume_count,) for values in one_per_volume):
        raise ValueError("reference volume arrays have invalid shapes")
    _positive_array(reference.temperature_F + 459.67, "absolute temperature")
    _positive_array(reference.pressure_psia, "pressure")
    if reference.hydraulic_liquid_flow_lbmolph.shape != (
        len(topology.hydraulic_volume_ids),
    ):
        raise ValueError("reference liquid-flow shape is invalid")
    if reference.vapor_flow_lbmolph.shape != (len(topology.vapor_links),):
        raise ValueError("reference vapor-flow shape is invalid")
    _positive_array(reference.hydraulic_liquid_flow_lbmolph, "liquid flow")
    _positive_array(reference.vapor_flow_lbmolph, "vapor flow")
    if not np.isfinite(reference.condenser_duty_BTUph) or reference.condenser_duty_BTUph >= 0.0:
        raise ValueError("reference condenser duty must be finite and negative")
    if tuple(record.volume_id for record in geometry) != topology.volume_ids:
        raise ValueError("geometry does not match the residual topology")
    if balance_inputs.topology != topology:
        raise ValueError("balance inputs do not match the residual topology")
    if len(hydraulic_geometry) != len(topology.hydraulic_volume_ids):
        raise ValueError("liquid hydraulic geometry count is invalid")
    if len(numerical.pressure_link_geometry) != len(topology.vapor_links):
        raise ValueError("pressure-link geometry count is invalid")
    if numerical.component_mw_lbm_per_lbmol.shape != (component_count,):
        raise ValueError("component molecular-weight shape is invalid")
    _positive_array(numerical.component_mw_lbm_per_lbmol, "component molecular weight")
    _positive_array(numerical.component_residual_scale_lbmolph, "component residual scale")
    scalar_positive = (
        numerical.timestep_sec,
        numerical.temperature_coordinate_scale_F,
        numerical.pressure_coordinate_scale_psia,
        numerical.dry_tray_pressure_drop_coefficient,
        numerical.energy_residual_scale_BTUph,
        numerical.pressure_residual_scale_psia,
        numerical.top_pressure_anchor_psia,
    )
    if any(not np.isfinite(value) or value <= 0.0 for value in scalar_positive):
        raise ValueError("vapor-holdup numerical settings must be positive")


def decode_vapor_holdup_endpoint(
    contract: VaporHoldupDAEContract,
    reference: VaporHoldupImplicitReference,
    numerical: VaporHoldupImplicitNumericalSpec,
    coordinates: Sequence[float],
) -> VaporHoldupImplicitEndpoint:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    variable_count = len(vapor_holdup_variable_names(contract))
    if point.shape != (variable_count,) or np.any(~np.isfinite(point)):
        raise ValueError("vapor-holdup solve coordinates are invalid")
    if np.max(np.abs(point)) > 50.0:
        raise RuntimeError("vapor-holdup coordinate exceeds the physical-domain guard")
    topology = contract.topology.column
    volume_count = len(topology.volume_ids)
    component_count = len(contract.component_names)
    inventory_count = volume_count * component_count
    hydraulic_count = len(topology.hydraulic_volume_ids)
    vapor_link_count = len(topology.vapor_links)
    cursor = 0
    liquid_log_increment = point[cursor : cursor + inventory_count].reshape(
        (volume_count, component_count)
    )
    cursor += inventory_count
    vapor_log_increment = point[cursor : cursor + inventory_count].reshape(
        (volume_count, component_count)
    )
    cursor += inventory_count
    transfer_coordinate = point[cursor : cursor + inventory_count].reshape(
        (volume_count, component_count)
    )
    cursor += inventory_count
    temperature_coordinate = point[cursor : cursor + volume_count]
    cursor += volume_count
    pressure_coordinate = point[cursor : cursor + volume_count]
    cursor += volume_count
    liquid_flow_coordinate = point[cursor : cursor + hydraulic_count]
    cursor += hydraulic_count
    vapor_flow_coordinate = point[cursor : cursor + vapor_link_count]
    cursor += vapor_link_count
    condenser_coordinate = float(point[cursor])
    cursor += 1
    if cursor != point.size:
        raise RuntimeError("vapor-holdup coordinate decoder did not consume the ledger")

    liquid_inventory = reference.liquid_component_inventory_lbmol * np.exp(
        liquid_log_increment
    )
    vapor_inventory = reference.vapor_component_inventory_lbmol * np.exp(
        vapor_log_increment
    )
    timestep_hr = float(numerical.timestep_sec) / 3600.0
    liquid_rate = (
        liquid_inventory - reference.liquid_component_inventory_lbmol
    ) / timestep_hr
    vapor_rate = (
        vapor_inventory - reference.vapor_component_inventory_lbmol
    ) / timestep_hr
    transfer = reference.phase_transfer_lbmolph + (
        reference.phase_transfer_scale_lbmolph * transfer_coordinate
    )
    temperature = reference.temperature_F + (
        float(numerical.temperature_coordinate_scale_F) * temperature_coordinate
    )
    pressure = reference.pressure_psia + (
        float(numerical.pressure_coordinate_scale_psia) * pressure_coordinate
    )
    liquid_flow = reference.hydraulic_liquid_flow_lbmolph * np.exp(
        liquid_flow_coordinate
    )
    vapor_flow = reference.vapor_flow_lbmolph * np.exp(vapor_flow_coordinate)
    condenser_duty = float(reference.condenser_duty_BTUph) * np.exp(
        condenser_coordinate
    )
    if np.any(temperature <= -459.67) or np.any(pressure <= 0.0):
        raise RuntimeError("vapor-holdup endpoint has nonphysical temperature or pressure")
    return VaporHoldupImplicitEndpoint(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=vapor_inventory,
        liquid_component_rate_lbmolph=liquid_rate,
        vapor_component_rate_lbmolph=vapor_rate,
        phase_transfer_lbmolph=transfer,
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        vapor_flow_lbmolph=vapor_flow,
        condenser_duty_BTUph=condenser_duty,
    )


def _fugacity_residuals(
    contract: VaporHoldupDAEContract,
    endpoint: VaporHoldupImplicitEndpoint,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    state_id: str,
    evaluation_kind: str,
) -> np.ndarray:
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    vapor_y = endpoint.vapor_component_inventory_lbmol / np.sum(
        endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
    )
    residual = np.empty_like(liquid_x)
    top = contract.topology.column.top_volume
    for index, volume in enumerate(contract.topology.column.volume_ids):
        quantity = (
            "condenser_bubble_equilibrium"
            if volume == top
            else "stage_fugacity_equilibrium"
        )
        common = {
            "temperature_F": float(endpoint.temperature_F[index]),
            "pressure_psia": float(endpoint.pressure_psia[index]),
            "caller": f"vapor_holdup_fugacity[{volume}]",
            "state_id": f"{state_id}:{volume}",
            "evaluation_kind": evaluation_kind,
            "quantity": quantity,
        }
        phi_liquid = call_audit.direct_phase_fugacity(
            provider,
            phase="liquid",
            composition=liquid_x[index],
            **common,
        )
        phi_vapor = call_audit.direct_phase_fugacity(
            provider,
            phase="vapor",
            composition=vapor_y[index],
            **common,
        )
        residual[index] = np.log(
            vapor_y[index] * phi_vapor / (liquid_x[index] * phi_liquid)
        )
    return residual


def _francis_residuals(
    contract: VaporHoldupDAEContract,
    endpoint: VaporHoldupImplicitEndpoint,
    properties: VaporHoldupPropertyEvaluation,
    hydraulic_geometry: Sequence[HydraulicGeometry],
) -> np.ndarray:
    topology = contract.topology.column
    volume_index = {volume: index for index, volume in enumerate(topology.volume_ids)}
    residual = np.empty(len(topology.hydraulic_volume_ids), dtype=float)
    for hydraulic_index, volume in enumerate(topology.hydraulic_volume_ids):
        index = volume_index[volume]
        calculated, _height, _head = _francis_flow(
            liquid_moles_lbmol=float(
                np.sum(endpoint.liquid_component_inventory_lbmol[index])
            ),
            density_lbmol_ft3=float(properties.liquid_density_lbmol_ft3[index]),
            geometry=hydraulic_geometry[hydraulic_index],
        )
        residual[hydraulic_index] = (
            float(endpoint.hydraulic_liquid_flow_lbmolph[hydraulic_index])
            - calculated
        )
    return residual


def _pressure_drop_residuals(
    contract: VaporHoldupDAEContract,
    endpoint: VaporHoldupImplicitEndpoint,
    properties: VaporHoldupPropertyEvaluation,
    numerical: VaporHoldupImplicitNumericalSpec,
) -> VaporPressureDropEvaluation:
    topology = contract.topology.column
    volume_index = {volume: index for index, volume in enumerate(topology.volume_ids)}
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    vapor_y = endpoint.vapor_component_inventory_lbmol / np.sum(
        endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
    )
    count = len(topology.vapor_links)
    residual = np.empty(count, dtype=float)
    liquid_drop = np.empty(count, dtype=float)
    dry_drop = np.empty(count, dtype=float)
    over_weir_head = np.empty(count, dtype=float)
    for link_index, (source, destination, _symbol) in enumerate(topology.vapor_links):
        source_index = volume_index[source]
        destination_index = volume_index[destination]
        geometry = numerical.pressure_link_geometry[link_index]
        density = float(properties.liquid_density_lbmol_ft3[source_index])
        liquid_total = float(
            np.sum(endpoint.liquid_component_inventory_lbmol[source_index])
        )
        liquid_height = liquid_total / (density * float(geometry.tray_area_ft2))
        over_weir_head[link_index] = (
            liquid_height - float(geometry.weir_height_in) / 12.0
        )
        if geometry.include_liquid_head and over_weir_head[link_index] <= 0.0:
            raise RuntimeError("vapor pressure-drop source has no over-weir head")
        liquid_mw = float(
            np.dot(liquid_x[source_index], numerical.component_mw_lbm_per_lbmol)
        )
        vapor_mw = float(
            np.dot(vapor_y[source_index], numerical.component_mw_lbm_per_lbmol)
        )
        liquid_drop[link_index] = 0.0
        if geometry.include_liquid_head:
            liquid_drop[link_index] = (
                density
                * liquid_mw
                * over_weir_head[link_index]
                / PSF_PER_PSIA
            )
        temperature_R = float(endpoint.temperature_F[source_index]) + 459.67
        vapor_molar_density = float(endpoint.pressure_psia[source_index]) / (
            float(properties.vapor_compressibility_factor[source_index])
            * GAS_CONSTANT_PSIA_FT3_LBMOL_R
            * temperature_R
        )
        vapor_mass_density = vapor_molar_density * vapor_mw
        volumetric_rate_ft3_s = (
            float(endpoint.vapor_flow_lbmolph[link_index])
            / 3600.0
            / vapor_molar_density
        )
        velocity_ft_s = volumetric_rate_ft3_s / float(geometry.active_area_ft2)
        dry_drop[link_index] = (
            float(numerical.dry_tray_pressure_drop_coefficient)
            * vapor_mass_density
            * velocity_ft_s**2
            / (2.0 * PSF_PER_PSIA)
        )
        residual[link_index] = (
            float(endpoint.pressure_psia[source_index])
            - float(endpoint.pressure_psia[destination_index])
            - liquid_drop[link_index]
            - dry_drop[link_index]
        )
    return VaporPressureDropEvaluation(
        residual_psia=residual,
        liquid_head_drop_psia=liquid_drop,
        dry_tray_drop_psia=dry_drop,
        over_weir_head_ft=over_weir_head,
    )


def evaluate_vapor_holdup_implicit_residual(
    contract: VaporHoldupDAEContract,
    geometry: Sequence[VaporControlVolumeGeometry],
    reference: VaporHoldupImplicitReference,
    balance_inputs: VaporHoldupBalanceInputs,
    hydraulic_geometry: Sequence[HydraulicGeometry],
    numerical: VaporHoldupImplicitNumericalSpec,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    state_id: str,
    evaluation_kind: str,
) -> VaporHoldupImplicitEvaluation:
    if evaluation_kind not in {"residual", "jacobian"}:
        raise ValueError("vapor-holdup residual requires residual/Jacobian evaluation")
    validate_vapor_holdup_implicit_problem(
        contract,
        geometry,
        reference,
        balance_inputs,
        hydraulic_geometry,
        numerical,
    )
    endpoint = decode_vapor_holdup_endpoint(
        contract,
        reference,
        numerical,
        coordinates,
    )
    properties = evaluate_vapor_holdup_trial_properties(
        geometry,
        endpoint.liquid_component_inventory_lbmol,
        endpoint.vapor_component_inventory_lbmol,
        endpoint.temperature_F,
        endpoint.pressure_psia,
        provider,
        call_audit,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    vapor_y = endpoint.vapor_component_inventory_lbmol / np.sum(
        endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
    )
    live_inputs = replace(
        balance_inputs,
        condenser_duty_BTUph=float(endpoint.condenser_duty_BTUph),
    )
    transport = evaluate_two_phase_transport(
        live_inputs,
        liquid_x,
        vapor_y,
        endpoint.hydraulic_liquid_flow_lbmolph,
        endpoint.vapor_flow_lbmolph,
        properties.liquid_enthalpy_BTU_lbmol,
        properties.vapor_enthalpy_BTU_lbmol,
    )
    stored_energy_rate = (
        properties.total_stored_energy_BTU - reference.total_stored_energy_BTU
    ) / (float(numerical.timestep_sec) / 3600.0)
    balances = evaluate_two_phase_balances(
        transport,
        endpoint.liquid_component_rate_lbmolph,
        endpoint.vapor_component_rate_lbmolph,
        endpoint.phase_transfer_lbmolph,
        stored_energy_rate,
    )
    fugacity = _fugacity_residuals(
        contract,
        endpoint,
        provider,
        call_audit,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    francis = _francis_residuals(
        contract,
        endpoint,
        properties,
        hydraulic_geometry,
    )
    pressure_drop = _pressure_drop_residuals(
        contract,
        endpoint,
        properties,
        numerical,
    )
    pressure_anchor = float(endpoint.pressure_psia[0]) - float(
        numerical.top_pressure_anchor_psia
    )

    component_scale = np.asarray(
        numerical.component_residual_scale_lbmolph, dtype=float
    )
    raw_values: list[float] = []
    scale_values: list[float] = []
    for volume_index in range(len(contract.topology.column.volume_ids)):
        for component_index in range(len(contract.component_names)):
            raw_values.append(
                float(
                    balances.liquid_component_residual_lbmolph[
                        volume_index, component_index
                    ]
                )
            )
            scale_values.append(float(component_scale[component_index]))
            raw_values.append(
                float(
                    balances.vapor_component_residual_lbmolph[
                        volume_index, component_index
                    ]
                )
            )
            scale_values.append(float(component_scale[component_index]))
        raw_values.extend(float(value) for value in fugacity[volume_index])
        scale_values.extend(1.0 for _ in contract.component_names)
        raw_values.append(float(properties.eos_volume_residual_ft3[volume_index]))
        scale_values.append(
            float(properties.free_volume.free_vapor_volume_ft3[volume_index])
        )
        raw_values.append(float(balances.energy_residual_BTUph[volume_index]))
        scale_values.append(float(numerical.energy_residual_scale_BTUph))
    raw_values.extend(float(value) for value in francis)
    scale_values.extend(
        float(value) for value in reference.hydraulic_liquid_flow_lbmolph
    )
    raw_values.extend(float(value) for value in pressure_drop.residual_psia)
    scale_values.extend(
        float(numerical.pressure_residual_scale_psia)
        for _ in pressure_drop.residual_psia
    )
    raw_values.append(pressure_anchor)
    scale_values.append(float(numerical.pressure_residual_scale_psia))
    raw = np.asarray(raw_values, dtype=float)
    scales = np.asarray(scale_values, dtype=float)
    row_names = tuple(row.name for row in contract.rows)
    variable_names = vapor_holdup_variable_names(contract)
    if (
        raw.shape != scales.shape
        or raw.shape != (len(variable_names),)
        or len(row_names) != len(variable_names)
        or np.any(~np.isfinite(raw))
        or np.any(~np.isfinite(scales))
        or np.any(scales <= 0.0)
    ):
        raise RuntimeError("vapor-holdup implicit residual ledger is invalid")
    return VaporHoldupImplicitEvaluation(
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        row_names=row_names,
        variable_names=variable_names,
        endpoint=endpoint,
        properties=properties,
        transport=transport,
        balances=balances,
        fugacity_residual=fugacity,
        francis_residual_lbmolph=francis,
        pressure_drop=pressure_drop,
        pressure_anchor_residual_psia=pressure_anchor,
    )


__all__ = [
    "VaporHoldupImplicitEndpoint",
    "VaporHoldupImplicitEvaluation",
    "VaporHoldupImplicitNumericalSpec",
    "VaporHoldupImplicitReference",
    "VaporPressureDropEvaluation",
    "decode_vapor_holdup_endpoint",
    "evaluate_vapor_holdup_implicit_residual",
    "validate_vapor_holdup_implicit_problem",
    "vapor_holdup_structural_pattern",
    "vapor_holdup_variable_names",
]
