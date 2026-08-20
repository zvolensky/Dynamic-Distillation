"""Implicit vapor-holdup residual with terminal PI level control."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from .provider_call_audit_v1 import ProviderCallAudit
from .vapor_holdup_implicit_residual_v1 import (
    VaporHoldupImplicitEvaluation,
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
)
from .vapor_holdup_terminal_control_contract_v1 import (
    VaporHoldupTerminalControlContract,
    terminal_level_fractions,
)
from .vapor_holdup_terminal_control_zero_time_v1 import (
    _split_coordinates,
    vapor_holdup_terminal_control_variable_names,
)


@dataclass(frozen=True)
class VaporHoldupTerminalControlImplicitEvaluation:
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
    base: VaporHoldupImplicitEvaluation


def controlled_implicit_initial_coordinates(
    contract: VaporHoldupTerminalControlContract,
    *,
    controller_rates_per_sec: Sequence[float],
    timestep_sec: float,
) -> np.ndarray:
    """Build the zero-motion predictor with one PI-memory advance."""
    rates = np.asarray(controller_rates_per_sec, dtype=float).reshape((-1,))
    if rates.shape != (2,) or np.any(~np.isfinite(rates)):
        raise ValueError("controller rates are invalid")
    timestep = float(timestep_sec)
    if not np.isfinite(timestep) or timestep <= 0.0:
        raise ValueError("controller timestep must be positive")
    point = np.zeros(len(contract.rows), dtype=float)
    base_rate_count = len(contract.base.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    point[base_rate_count : base_rate_count + 2] = rates
    output_start = base_rate_count + 2 + base_algebraic_count
    point[output_start:] = timestep * rates
    return point


def evaluate_vapor_holdup_terminal_control_implicit_residual(
    contract: VaporHoldupTerminalControlContract,
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
) -> VaporHoldupTerminalControlImplicitEvaluation:
    """Evaluate one backward-Euler endpoint with live terminal PI control."""
    base_coordinates, controller_rates, product_logs = _split_coordinates(
        contract, coordinates
    )
    memory_previous = np.asarray(
        controller_memory_previous, dtype=float
    ).reshape((-1,))
    if memory_previous.shape != (2,) or np.any(~np.isfinite(memory_previous)):
        raise ValueError("previous controller memory is invalid")
    timestep = float(numerical.timestep_sec)
    if not np.isfinite(timestep) or timestep <= 0.0:
        raise ValueError("controller timestep must be positive")
    memory_endpoint = memory_previous + timestep * controller_rates
    products = np.asarray(
        (
            float(balance_inputs.distillate_lbmolph) * np.exp(product_logs[0]),
            float(balance_inputs.bottoms_lbmolph) * np.exp(product_logs[1]),
        ),
        dtype=float,
    )
    if np.any(~np.isfinite(products)) or np.any(products <= 0.0):
        raise RuntimeError("terminal controller produced a nonphysical product rate")
    live_inputs = replace(
        balance_inputs,
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
    )
    base = evaluate_vapor_holdup_implicit_residual(
        contract.base,
        geometry,
        reference,
        live_inputs,
        hydraulic_geometry,
        numerical,
        provider,
        call_audit,
        base_coordinates,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    levels = terminal_level_fractions(
        base.endpoint.liquid_component_inventory_lbmol,
        base.properties.liquid_density_lbmol_ft3,
        contract.geometry,
    )
    tuning = contract.controllers
    setpoints = np.asarray(
        (
            tuning.drum_level_setpoint_fraction,
            tuning.sump_level_setpoint_fraction,
        ),
        dtype=float,
    )
    gains = np.asarray((tuning.drum_kc, tuning.sump_kc), dtype=float)
    times = np.asarray((tuning.drum_ti_sec, tuning.sump_ti_sec), dtype=float)
    errors = levels - setpoints
    controller_raw = np.asarray(
        (
            times[0] * controller_rates[0] - gains[0] * errors[0],
            product_logs[0] - memory_endpoint[0] - gains[0] * errors[0],
            times[1] * controller_rates[1] - gains[1] * errors[1],
            product_logs[1] - memory_endpoint[1] - gains[1] * errors[1],
        ),
        dtype=float,
    )
    raw = np.concatenate((base.raw, controller_raw))
    scaled = np.concatenate((base.scaled, controller_raw))
    names = vapor_holdup_terminal_control_variable_names(contract)
    if raw.shape != scaled.shape or raw.shape != (len(names),):
        raise RuntimeError("terminal-control implicit residual ledger is invalid")
    return VaporHoldupTerminalControlImplicitEvaluation(
        raw=raw,
        scaled=scaled,
        row_names=tuple(row.name for row in contract.rows),
        variable_names=names,
        coordinates=np.asarray(coordinates, dtype=float).copy(),
        level_fraction=levels,
        level_error=errors,
        controller_rate_per_sec=controller_rates.copy(),
        controller_memory_previous=memory_previous.copy(),
        controller_memory_endpoint=memory_endpoint,
        product_log_ratio=product_logs.copy(),
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
        base=base,
    )


__all__ = [
    "VaporHoldupTerminalControlImplicitEvaluation",
    "controlled_implicit_initial_coordinates",
    "evaluate_vapor_holdup_terminal_control_implicit_residual",
]
