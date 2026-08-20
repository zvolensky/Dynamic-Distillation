"""Numerical residual for the stationary vapor-holdup initializer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from .pressure_layer_numerical_v1 import PressureLinkGeometry
from .provider_call_audit_v1 import ProviderCallAudit
from .provider_governed_residual_v1 import HydraulicGeometry
from .vapor_holdup_balances_v1 import (
    TwoPhaseBalanceEvaluation,
    TwoPhaseTransportEvaluation,
    VaporHoldupBalanceInputs,
    evaluate_two_phase_balances,
    evaluate_two_phase_transport,
)
from .vapor_holdup_geometry_v1 import VaporControlVolumeGeometry
from .vapor_holdup_implicit_residual_v1 import (
    VaporHoldupImplicitEndpoint,
    VaporPressureDropEvaluation,
    _francis_residuals,
    _fugacity_residuals,
    _pressure_drop_residuals,
)
from .vapor_holdup_properties_v1 import (
    VaporHoldupPropertyEvaluation,
    evaluate_vapor_holdup_trial_properties,
)
from .vapor_holdup_stationary_contract_v1 import (
    VaporHoldupStationaryContract,
    stationary_sparsity_pattern,
)


@dataclass(frozen=True)
class VaporHoldupStationaryReference:
    liquid_component_inventory_lbmol: np.ndarray
    vapor_component_inventory_lbmol: np.ndarray
    phase_transfer_lbmolph: np.ndarray
    phase_transfer_scale_lbmolph: np.ndarray
    temperature_F: np.ndarray
    pressure_psia: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    condenser_duty_BTUph: float
    distillate_lbmolph: float
    bottoms_lbmolph: float
    top_liquid_inventory_target_lbmol: float
    bottom_liquid_inventory_target_lbmol: float


@dataclass(frozen=True)
class VaporHoldupStationaryNumericalSpec:
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
class VaporHoldupStationaryEndpoint:
    liquid_component_inventory_lbmol: np.ndarray
    vapor_component_inventory_lbmol: np.ndarray
    phase_transfer_lbmolph: np.ndarray
    temperature_F: np.ndarray
    pressure_psia: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    condenser_duty_BTUph: float
    distillate_lbmolph: float
    bottoms_lbmolph: float


@dataclass(frozen=True)
class VaporHoldupStationaryEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    endpoint: VaporHoldupStationaryEndpoint
    properties: VaporHoldupPropertyEvaluation
    transport: TwoPhaseTransportEvaluation
    balances: TwoPhaseBalanceEvaluation
    fugacity_residual: np.ndarray
    francis_residual_lbmolph: np.ndarray
    pressure_drop: VaporPressureDropEvaluation
    pressure_anchor_residual_psia: float
    terminal_inventory_residual_lbmol: np.ndarray


def stationary_variable_names(
    contract: VaporHoldupStationaryContract,
) -> tuple[str, ...]:
    return tuple(variable.name for variable in contract.variables)


def stationary_structural_pattern(
    contract: VaporHoldupStationaryContract,
) -> np.ndarray:
    pattern, names, unknown = stationary_sparsity_pattern(contract)
    if unknown or names != stationary_variable_names(contract):
        raise RuntimeError("stationary vapor-holdup variable registry is invalid")
    return pattern.toarray().astype(bool)


def _positive(values: np.ndarray, name: str) -> None:
    if np.any(~np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError(f"{name} must be positive and finite")


def validate_vapor_holdup_stationary_problem(
    contract: VaporHoldupStationaryContract,
    geometry: Sequence[VaporControlVolumeGeometry],
    reference: VaporHoldupStationaryReference,
    balance_inputs: VaporHoldupBalanceInputs,
    hydraulic_geometry: Sequence[HydraulicGeometry],
    numerical: VaporHoldupStationaryNumericalSpec,
) -> None:
    topology = contract.topology.column
    volume_count = len(topology.volume_ids)
    component_count = len(contract.component_names)
    shape = (volume_count, component_count)
    arrays = (
        reference.liquid_component_inventory_lbmol,
        reference.vapor_component_inventory_lbmol,
        reference.phase_transfer_lbmolph,
        reference.phase_transfer_scale_lbmolph,
    )
    if any(np.asarray(values).shape != shape for values in arrays):
        raise ValueError("stationary inventory/transfer array shape is invalid")
    _positive(reference.liquid_component_inventory_lbmol, "liquid inventory")
    _positive(reference.vapor_component_inventory_lbmol, "vapor inventory")
    _positive(reference.phase_transfer_scale_lbmolph, "phase-transfer scale")
    if np.any(~np.isfinite(reference.phase_transfer_lbmolph)):
        raise ValueError("phase transfer must be finite")
    one_per_volume = (reference.temperature_F, reference.pressure_psia)
    if any(np.asarray(values).shape != (volume_count,) for values in one_per_volume):
        raise ValueError("stationary temperature/pressure shape is invalid")
    _positive(reference.temperature_F + 459.67, "absolute temperature")
    _positive(reference.pressure_psia, "pressure")
    if reference.hydraulic_liquid_flow_lbmolph.shape != (
        len(topology.hydraulic_volume_ids),
    ):
        raise ValueError("stationary liquid-flow shape is invalid")
    if reference.vapor_flow_lbmolph.shape != (len(topology.vapor_links),):
        raise ValueError("stationary vapor-flow shape is invalid")
    _positive(reference.hydraulic_liquid_flow_lbmolph, "liquid flow")
    _positive(reference.vapor_flow_lbmolph, "vapor flow")
    positive_scalars = (
        reference.distillate_lbmolph,
        reference.bottoms_lbmolph,
        reference.top_liquid_inventory_target_lbmol,
        reference.bottom_liquid_inventory_target_lbmol,
        numerical.temperature_coordinate_scale_F,
        numerical.pressure_coordinate_scale_psia,
        numerical.dry_tray_pressure_drop_coefficient,
        numerical.top_pressure_anchor_psia,
        numerical.energy_residual_scale_BTUph,
        numerical.pressure_residual_scale_psia,
    )
    if any(not np.isfinite(value) or value <= 0.0 for value in positive_scalars):
        raise ValueError("stationary scalar settings must be positive")
    if not np.isfinite(reference.condenser_duty_BTUph) or reference.condenser_duty_BTUph >= 0.0:
        raise ValueError("stationary condenser duty must be finite and negative")
    if tuple(item.volume_id for item in geometry) != topology.volume_ids:
        raise ValueError("stationary geometry does not match topology")
    if balance_inputs.topology != topology:
        raise ValueError("stationary balance inputs do not match topology")
    if len(hydraulic_geometry) != len(topology.hydraulic_volume_ids):
        raise ValueError("stationary hydraulic geometry count is invalid")
    if len(numerical.pressure_link_geometry) != len(topology.vapor_links):
        raise ValueError("stationary pressure geometry count is invalid")
    if numerical.component_mw_lbm_per_lbmol.shape != (component_count,):
        raise ValueError("stationary molecular-weight shape is invalid")
    if numerical.component_residual_scale_lbmolph.shape != (component_count,):
        raise ValueError("stationary component scale shape is invalid")
    _positive(numerical.component_mw_lbm_per_lbmol, "component molecular weight")
    _positive(numerical.component_residual_scale_lbmolph, "component residual scale")


def decode_vapor_holdup_stationary_endpoint(
    contract: VaporHoldupStationaryContract,
    reference: VaporHoldupStationaryReference,
    numerical: VaporHoldupStationaryNumericalSpec,
    coordinates: Sequence[float],
) -> VaporHoldupStationaryEndpoint:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.variables),) or np.any(~np.isfinite(point)):
        raise ValueError("stationary vapor-holdup coordinates are invalid")
    if np.max(np.abs(point)) > 50.0:
        raise RuntimeError("stationary coordinate exceeds physical-domain guard")
    topology = contract.topology.column
    volume_count = len(topology.volume_ids)
    component_count = len(contract.component_names)
    inventory_count = volume_count * component_count
    liquid_count = len(topology.hydraulic_volume_ids)
    vapor_count = len(topology.vapor_links)
    cursor = 0

    liquid_inventory = reference.liquid_component_inventory_lbmol * np.exp(
        point[cursor : cursor + inventory_count].reshape(
            (volume_count, component_count)
        )
    )
    cursor += inventory_count
    vapor_inventory = reference.vapor_component_inventory_lbmol * np.exp(
        point[cursor : cursor + inventory_count].reshape(
            (volume_count, component_count)
        )
    )
    cursor += inventory_count
    transfer = reference.phase_transfer_lbmolph + (
        reference.phase_transfer_scale_lbmolph
        * point[cursor : cursor + inventory_count].reshape(
            (volume_count, component_count)
        )
    )
    cursor += inventory_count
    temperature = reference.temperature_F + (
        numerical.temperature_coordinate_scale_F
        * point[cursor : cursor + volume_count]
    )
    cursor += volume_count
    pressure = reference.pressure_psia + (
        numerical.pressure_coordinate_scale_psia
        * point[cursor : cursor + volume_count]
    )
    cursor += volume_count
    liquid_flow = reference.hydraulic_liquid_flow_lbmolph * np.exp(
        point[cursor : cursor + liquid_count]
    )
    cursor += liquid_count
    vapor_flow = reference.vapor_flow_lbmolph * np.exp(
        point[cursor : cursor + vapor_count]
    )
    cursor += vapor_count
    condenser_duty = reference.condenser_duty_BTUph * np.exp(point[cursor])
    cursor += 1
    distillate = reference.distillate_lbmolph * np.exp(point[cursor])
    cursor += 1
    bottoms = reference.bottoms_lbmolph * np.exp(point[cursor])
    cursor += 1
    if cursor != point.size:
        raise RuntimeError("stationary coordinate decoder did not consume ledger")
    if np.any(temperature <= -459.67) or np.any(pressure <= 0.0):
        raise RuntimeError("stationary endpoint has nonphysical temperature or pressure")
    return VaporHoldupStationaryEndpoint(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=vapor_inventory,
        phase_transfer_lbmolph=transfer,
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        vapor_flow_lbmolph=vapor_flow,
        condenser_duty_BTUph=float(condenser_duty),
        distillate_lbmolph=float(distillate),
        bottoms_lbmolph=float(bottoms),
    )


def evaluate_vapor_holdup_stationary_residual(
    contract: VaporHoldupStationaryContract,
    geometry: Sequence[VaporControlVolumeGeometry],
    reference: VaporHoldupStationaryReference,
    balance_inputs: VaporHoldupBalanceInputs,
    hydraulic_geometry: Sequence[HydraulicGeometry],
    numerical: VaporHoldupStationaryNumericalSpec,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    state_id: str,
    evaluation_kind: str,
) -> VaporHoldupStationaryEvaluation:
    if evaluation_kind not in {"residual", "jacobian"}:
        raise ValueError("stationary residual requires residual/Jacobian evaluation")
    validate_vapor_holdup_stationary_problem(
        contract,
        geometry,
        reference,
        balance_inputs,
        hydraulic_geometry,
        numerical,
    )
    endpoint = decode_vapor_holdup_stationary_endpoint(
        contract, reference, numerical, coordinates
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
        distillate_lbmolph=endpoint.distillate_lbmolph,
        bottoms_lbmolph=endpoint.bottoms_lbmolph,
        condenser_duty_BTUph=endpoint.condenser_duty_BTUph,
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
    zero_rates = np.zeros_like(endpoint.liquid_component_inventory_lbmol)
    balances = evaluate_two_phase_balances(
        transport,
        zero_rates,
        zero_rates,
        endpoint.phase_transfer_lbmolph,
        np.zeros(len(contract.topology.column.volume_ids), dtype=float),
    )
    helper_endpoint = VaporHoldupImplicitEndpoint(
        liquid_component_inventory_lbmol=endpoint.liquid_component_inventory_lbmol,
        vapor_component_inventory_lbmol=endpoint.vapor_component_inventory_lbmol,
        liquid_component_rate_lbmolph=zero_rates,
        vapor_component_rate_lbmolph=zero_rates,
        phase_transfer_lbmolph=endpoint.phase_transfer_lbmolph,
        temperature_F=endpoint.temperature_F,
        pressure_psia=endpoint.pressure_psia,
        hydraulic_liquid_flow_lbmolph=endpoint.hydraulic_liquid_flow_lbmolph,
        vapor_flow_lbmolph=endpoint.vapor_flow_lbmolph,
        condenser_duty_BTUph=endpoint.condenser_duty_BTUph,
    )
    fugacity = _fugacity_residuals(
        contract,
        helper_endpoint,
        provider,
        call_audit,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    francis = _francis_residuals(
        contract, helper_endpoint, properties, hydraulic_geometry
    )
    pressure_drop = _pressure_drop_residuals(
        contract, helper_endpoint, properties, numerical
    )
    pressure_anchor = float(endpoint.pressure_psia[0]) - float(
        numerical.top_pressure_anchor_psia
    )
    terminal_inventory = np.asarray(
        (
            np.sum(endpoint.liquid_component_inventory_lbmol[0])
            - reference.top_liquid_inventory_target_lbmol,
            np.sum(endpoint.liquid_component_inventory_lbmol[-1])
            - reference.bottom_liquid_inventory_target_lbmol,
        ),
        dtype=float,
    )

    component_scale = numerical.component_residual_scale_lbmolph
    raw_values: list[float] = []
    scale_values: list[float] = []
    for volume_index in range(len(contract.topology.column.volume_ids)):
        for component_index in range(len(contract.component_names)):
            raw_values.append(
                float(balances.liquid_component_residual_lbmolph[volume_index, component_index])
            )
            scale_values.append(float(component_scale[component_index]))
            raw_values.append(
                float(balances.vapor_component_residual_lbmolph[volume_index, component_index])
            )
            scale_values.append(float(component_scale[component_index]))
        raw_values.extend(float(value) for value in fugacity[volume_index])
        scale_values.extend(1.0 for _ in contract.component_names)
        raw_values.append(float(properties.eos_volume_residual_ft3[volume_index]))
        scale_values.append(float(properties.free_volume.free_vapor_volume_ft3[volume_index]))
        raw_values.append(float(balances.energy_residual_BTUph[volume_index]))
        scale_values.append(float(numerical.energy_residual_scale_BTUph))
    raw_values.extend(float(value) for value in francis)
    scale_values.extend(float(value) for value in reference.hydraulic_liquid_flow_lbmolph)
    raw_values.extend(float(value) for value in pressure_drop.residual_psia)
    scale_values.extend(
        numerical.pressure_residual_scale_psia for _ in pressure_drop.residual_psia
    )
    raw_values.append(pressure_anchor)
    scale_values.append(numerical.pressure_residual_scale_psia)
    raw_values.extend(float(value) for value in terminal_inventory)
    scale_values.extend(
        (
            reference.top_liquid_inventory_target_lbmol,
            reference.bottom_liquid_inventory_target_lbmol,
        )
    )
    raw = np.asarray(raw_values, dtype=float)
    scales = np.asarray(scale_values, dtype=float)
    variable_names = stationary_variable_names(contract)
    row_names = tuple(row.name for row in contract.rows)
    if (
        raw.shape != scales.shape
        or raw.shape != (len(variable_names),)
        or len(row_names) != len(variable_names)
        or np.any(~np.isfinite(raw))
        or np.any(~np.isfinite(scales))
        or np.any(scales <= 0.0)
    ):
        raise RuntimeError("stationary vapor-holdup residual ledger is invalid")
    return VaporHoldupStationaryEvaluation(
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
        terminal_inventory_residual_lbmol=terminal_inventory,
    )


__all__ = [
    "VaporHoldupStationaryEndpoint",
    "VaporHoldupStationaryEvaluation",
    "VaporHoldupStationaryNumericalSpec",
    "VaporHoldupStationaryReference",
    "decode_vapor_holdup_stationary_endpoint",
    "evaluate_vapor_holdup_stationary_residual",
    "stationary_structural_pattern",
    "stationary_variable_names",
    "validate_vapor_holdup_stationary_problem",
]
