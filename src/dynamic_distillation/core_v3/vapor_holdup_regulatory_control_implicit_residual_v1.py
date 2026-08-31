"""Implicit pressure and distillate-composition PI control for Core V3."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from .provider_call_audit_v1 import ProviderCallAudit
from .vapor_holdup_implicit_residual_v1 import (
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
)
from .vapor_holdup_regulatory_control_contract_v1 import (
    VaporHoldupRegulatoryControlContract,
    audit_vapor_holdup_regulatory_control_contract,
)
from .vapor_holdup_terminal_control_implicit_residual_v1 import (
    VaporHoldupTerminalControlImplicitEvaluation,
    evaluate_vapor_holdup_terminal_control_implicit_residual,
)


@dataclass(frozen=True)
class VaporHoldupRegulatoryControlImplicitEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    coordinates: np.ndarray
    level_fraction: np.ndarray
    level_error: np.ndarray
    controller_rate_per_sec: np.ndarray
    controller_memory_previous: np.ndarray
    controller_memory_endpoint: np.ndarray
    product_log_ratio: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    pressure_error_psia: float
    composition_molfrac: float
    composition_error_molfrac: float
    condenser_duty_log_ratio: float
    reflux_log_ratio: float
    reflux_lbmolph: float
    level: VaporHoldupTerminalControlImplicitEvaluation
    base: Any


def regulatory_control_variable_names(
    contract: VaporHoldupRegulatoryControlContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )


def regulatory_control_pattern(
    contract: VaporHoldupRegulatoryControlContract,
) -> np.ndarray:
    names = regulatory_control_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            column = index.get(dependency)
            if column is not None:
                pattern[row_index, column] = True
    return pattern


def _split_coordinates(
    contract: VaporHoldupRegulatoryControlContract,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, float]:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("regulatory-control coordinates are invalid")
    predecessor_rate_count = len(contract.predecessor.derivative_variables)
    predecessor_algebraic_count = len(contract.predecessor.algebraic_variables)
    regulatory_rate_stop = predecessor_rate_count + 2
    predecessor_algebraic_stop = regulatory_rate_stop + predecessor_algebraic_count
    predecessor_coordinates = np.concatenate(
        (
            point[:predecessor_rate_count],
            point[regulatory_rate_stop:predecessor_algebraic_stop],
        )
    )
    return (
        predecessor_coordinates,
        point[predecessor_rate_count:regulatory_rate_stop],
        float(point[predecessor_algebraic_stop]),
    )


def regulatory_control_initial_coordinates(
    contract: VaporHoldupRegulatoryControlContract,
    *,
    controller_rates_per_sec: Sequence[float],
    timestep_sec: float,
    previous_coordinates: Sequence[float] | None,
    product_log_ratios_previous: Sequence[float],
    reflux_log_ratio_previous: float,
) -> np.ndarray:
    rates = np.asarray(controller_rates_per_sec, dtype=float).reshape((-1,))
    if rates.shape != (4,) or np.any(~np.isfinite(rates)):
        raise ValueError("four regulatory controller rates are required")
    timestep = float(timestep_sec)
    if not np.isfinite(timestep) or timestep <= 0.0:
        raise ValueError("controller timestep must be positive")
    predecessor_count = len(contract.predecessor.rows)
    if previous_coordinates is None:
        point = np.zeros(len(contract.rows), dtype=float)
    else:
        previous = np.asarray(previous_coordinates, dtype=float).reshape((-1,))
        if previous.shape == (predecessor_count,):
            point = np.zeros(len(contract.rows), dtype=float)
            predecessor_rate_count = len(contract.predecessor.derivative_variables)
            point[:predecessor_rate_count] = previous[:predecessor_rate_count]
            point[predecessor_rate_count + 2 : -1] = previous[predecessor_rate_count:]
        elif previous.shape == (len(contract.rows),):
            point = previous.copy()
        else:
            raise ValueError("previous regulatory coordinates have the wrong dimension")
        if np.any(~np.isfinite(point)):
            raise ValueError("previous regulatory coordinates are invalid")
    predecessor_rate_count = len(contract.predecessor.derivative_variables)
    predecessor_algebraic_count = len(contract.predecessor.algebraic_variables)
    point[predecessor_rate_count : predecessor_rate_count + 2] = rates[2:]
    base_rate_count = len(contract.base.derivative_variables)
    point[base_rate_count : base_rate_count + 2] = rates[:2]
    level_output_start = predecessor_rate_count + 2 + len(contract.base.algebraic_variables)
    level_logs = np.asarray(product_log_ratios_previous, dtype=float).reshape((2,))
    point[level_output_start : level_output_start + 2] = (
        level_logs + timestep * rates[:2]
    )
    reflux_index = predecessor_rate_count + 2 + predecessor_algebraic_count
    point[reflux_index] = float(reflux_log_ratio_previous) + timestep * rates[3]
    return point


def regulatory_control_bounds(
    contract: VaporHoldupRegulatoryControlContract,
    reference: VaporHoldupImplicitReference,
) -> tuple[np.ndarray, np.ndarray]:
    dimension = len(contract.rows)
    lower = np.full(dimension, -0.1)
    upper = np.full(dimension, 0.1)
    base_rate_count = len(contract.base.derivative_variables)
    predecessor_rate_count = len(contract.predecessor.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    lower[:base_rate_count] = -0.01
    upper[:base_rate_count] = 0.01
    base_algebraic_start = predecessor_rate_count + 2
    tight_algebraic_start = base_algebraic_start + 100
    base_algebraic_stop = base_algebraic_start + base_algebraic_count
    lower[tight_algebraic_start:base_algebraic_stop] = -0.01
    upper[tight_algebraic_start:base_algebraic_stop] = 0.01

    variable_names = regulatory_control_variable_names(contract)
    # Vapor flows are logarithmic endpoint ratios.  A feed-enthalpy step can
    # require an immediate redistribution larger than the generic one-percent
    # algebraic trust envelope even though the resulting flows remain physical.
    # Keep the other tight algebraic bounds unchanged and give only vapor links
    # a five-percent log-coordinate envelope.
    vapor_flow_indices = [
        index for index, name in enumerate(variable_names) if name.startswith("V[")
    ]
    lower[vapor_flow_indices] = -0.05
    upper[vapor_flow_indices] = 0.05
    q_index = variable_names.index("Q_C")
    spec = contract.regulatory
    q_lo, q_hi = spec.condenser_duty_ratio_bounds
    current = abs(float(reference.condenser_duty_BTUph))
    bias = abs(float(spec.condenser_duty_reference_BTUph))
    lower[q_index] = np.log(q_lo * bias / current)
    upper[q_index] = np.log(q_hi * bias / current)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    product_start = base_algebraic_stop
    lower[product_start : product_start + 2] = np.log(product_low)
    upper[product_start : product_start + 2] = np.log(product_high)
    reflux_index = len(variable_names) - 1
    reflux_low, reflux_high = spec.reflux_ratio_bounds
    lower[reflux_index] = np.log(reflux_low)
    upper[reflux_index] = np.log(reflux_high)
    return lower, upper


def evaluate_vapor_holdup_regulatory_control_implicit_residual(
    contract: VaporHoldupRegulatoryControlContract,
    geometry: Sequence[Any],
    reference: VaporHoldupImplicitReference,
    balance_inputs: Any,
    hydraulic_geometry: Sequence[Any],
    numerical: VaporHoldupImplicitNumericalSpec,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    controller_memory_previous: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> VaporHoldupRegulatoryControlImplicitEvaluation:
    if not audit_vapor_holdup_regulatory_control_contract(contract).pass_gate:
        raise ValueError("regulatory-control structural contract has not passed")
    predecessor_coordinates, regulatory_rates, reflux_log = _split_coordinates(
        contract, coordinates
    )
    memory_previous = np.asarray(controller_memory_previous, dtype=float).reshape((-1,))
    if memory_previous.shape != (4,) or np.any(~np.isfinite(memory_previous)):
        raise ValueError("four previous controller memories are required")
    timestep = float(numerical.timestep_sec)
    memory_endpoint = memory_previous + timestep * np.concatenate(
        (np.zeros(2), regulatory_rates)
    )
    reflux = float(contract.regulatory.reflux_reference_lbmolph) * np.exp(reflux_log)
    if not np.isfinite(reflux) or reflux <= 0.0:
        raise RuntimeError("composition controller produced a nonphysical reflux rate")
    level = evaluate_vapor_holdup_terminal_control_implicit_residual(
        contract.predecessor,
        geometry,
        reference,
        replace(balance_inputs, reflux_lbmolph=reflux),
        hydraulic_geometry,
        numerical,
        provider,
        call_audit,
        predecessor_coordinates,
        controller_memory_previous=memory_previous[:2],
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    memory_endpoint[:2] = level.controller_memory_endpoint
    endpoint = level.base.endpoint
    topology = contract.base.topology.column
    top_index = topology.volume_ids.index(topology.top_volume)
    pressure = float(endpoint.pressure_psia[top_index])
    liquid = np.asarray(endpoint.liquid_component_inventory_lbmol[top_index], dtype=float)
    composition = liquid / np.sum(liquid)
    component_index = contract.base.component_names.index(
        contract.regulatory.composition_component
    )
    composition_pv = float(composition[component_index])
    pressure_error = pressure - float(contract.regulatory.pressure_setpoint_psia)
    composition_error = (
        composition_pv - float(contract.regulatory.composition_setpoint_molfrac)
    )
    duty = float(endpoint.condenser_duty_BTUph)
    duty_bias = float(contract.regulatory.condenser_duty_reference_BTUph)
    if duty >= 0.0 or duty_bias >= 0.0:
        raise RuntimeError("pressure controller requires negative condenser duties")
    duty_log = float(np.log(duty / duty_bias))
    pressure_output = (
        duty_log
        - memory_endpoint[2]
        - float(contract.regulatory.pressure_kc_per_psia) * pressure_error
    )
    pressure_integrator = (
        float(contract.regulatory.pressure_ti_sec) * regulatory_rates[0]
        - float(contract.regulatory.pressure_kc_per_psia) * pressure_error
    )
    composition_integrator = (
        float(contract.regulatory.composition_ti_sec) * regulatory_rates[1]
        - float(contract.regulatory.composition_kc_per_molfrac) * composition_error
    )
    composition_output = (
        reflux_log
        - memory_endpoint[3]
        - float(contract.regulatory.composition_kc_per_molfrac) * composition_error
    )

    duty_rows = tuple(
        index
        for index, row in enumerate(contract.predecessor.rows)
        if row.block == "condenser_duty_specification"
    )
    if len(duty_rows) != 1:
        raise RuntimeError("regulatory predecessor requires one condenser-duty row")
    duty_index = duty_rows[0]
    predecessor_raw = level.raw.copy()
    predecessor_scaled = level.scaled.copy()
    predecessor_raw[duty_index] = pressure_output
    predecessor_scaled[duty_index] = pressure_output
    base_raw = level.base.raw.copy()
    base_scaled = level.base.scaled.copy()
    base_raw[duty_index] = pressure_output
    base_scaled[duty_index] = pressure_output
    base = replace(level.base, raw=base_raw, scaled=base_scaled)
    level = replace(level, raw=predecessor_raw, scaled=predecessor_scaled, base=base)
    controller_raw = np.asarray(
        (pressure_integrator, composition_integrator, composition_output),
        dtype=float,
    )
    raw = np.concatenate((predecessor_raw, controller_raw))
    scaled = np.concatenate((predecessor_scaled, controller_raw))
    rates = np.concatenate((level.controller_rate_per_sec, regulatory_rates))
    names = regulatory_control_variable_names(contract)
    if raw.shape != (len(names),) or np.any(~np.isfinite(raw)):
        raise RuntimeError("regulatory-control residual ledger is invalid")
    return VaporHoldupRegulatoryControlImplicitEvaluation(
        raw=raw,
        scaled=scaled,
        row_names=tuple(row.name for row in contract.rows),
        variable_names=names,
        coordinates=np.asarray(coordinates, dtype=float).copy(),
        level_fraction=level.level_fraction,
        level_error=level.level_error,
        controller_rate_per_sec=rates,
        controller_memory_previous=memory_previous.copy(),
        controller_memory_endpoint=memory_endpoint,
        product_log_ratio=level.product_log_ratio,
        distillate_lbmolph=level.distillate_lbmolph,
        bottoms_lbmolph=level.bottoms_lbmolph,
        pressure_error_psia=pressure_error,
        composition_molfrac=composition_pv,
        composition_error_molfrac=composition_error,
        condenser_duty_log_ratio=duty_log,
        reflux_log_ratio=float(reflux_log),
        reflux_lbmolph=reflux,
        level=level,
        base=base,
    )


__all__ = [
    "VaporHoldupRegulatoryControlImplicitEvaluation",
    "evaluate_vapor_holdup_regulatory_control_implicit_residual",
    "regulatory_control_bounds",
    "regulatory_control_initial_coordinates",
    "regulatory_control_pattern",
    "regulatory_control_variable_names",
]
