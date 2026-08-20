"""Live zero-time handoff for vapor-holdup terminal level controllers."""

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


@dataclass(frozen=True)
class VaporHoldupTerminalZeroTimeEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    coordinates: np.ndarray
    level_fraction: np.ndarray
    level_error: np.ndarray
    controller_rate_per_sec: np.ndarray
    controller_memory: np.ndarray
    product_log_ratio: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    base: VaporHoldupImplicitEvaluation


def vapor_holdup_terminal_control_variable_names(
    contract: VaporHoldupTerminalControlContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )


def vapor_holdup_terminal_control_pattern(
    contract: VaporHoldupTerminalControlContract,
) -> np.ndarray:
    names = vapor_holdup_terminal_control_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                pattern[row_index, index[dependency]] = True
    return pattern


def _split_coordinates(
    contract: VaporHoldupTerminalControlContract,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("vapor-holdup terminal-control coordinates are invalid")
    base_rate_count = len(contract.base.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    controller_rate_stop = base_rate_count + 2
    base_algebraic_stop = controller_rate_stop + base_algebraic_count
    base_coordinates = np.concatenate(
        (point[:base_rate_count], point[controller_rate_stop:base_algebraic_stop])
    )
    return (
        base_coordinates,
        point[base_rate_count:controller_rate_stop],
        point[base_algebraic_stop:],
    )


def bumpless_controller_state(
    contract: VaporHoldupTerminalControlContract,
    level_fraction: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    levels = np.asarray(level_fraction, dtype=float).reshape((-1,))
    if levels.shape != (2,) or np.any(~np.isfinite(levels)):
        raise ValueError("terminal levels are invalid")
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
    controller_rates = gains * errors / times
    product_logs = np.zeros(2, dtype=float)
    controller_memory = product_logs - gains * errors
    return controller_rates, controller_memory, product_logs


def controlled_zero_time_coordinates(
    contract: VaporHoldupTerminalControlContract,
    *,
    controller_rates_per_sec: Sequence[float],
    product_log_ratios: Sequence[float],
) -> np.ndarray:
    rates = np.asarray(controller_rates_per_sec, dtype=float).reshape((-1,))
    products = np.asarray(product_log_ratios, dtype=float).reshape((-1,))
    if (
        rates.shape != (2,)
        or products.shape != (2,)
        or np.any(~np.isfinite(rates))
        or np.any(~np.isfinite(products))
    ):
        raise ValueError("controller rates or outputs are invalid")
    point = np.zeros(len(contract.rows), dtype=float)
    base_rate_count = len(contract.base.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    point[base_rate_count : base_rate_count + 2] = rates
    output_start = base_rate_count + 2 + base_algebraic_count
    point[output_start:] = products
    return point


def evaluate_vapor_holdup_terminal_zero_time(
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
    controller_memory: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> VaporHoldupTerminalZeroTimeEvaluation:
    base_coordinates, controller_rates, product_logs = _split_coordinates(
        contract, coordinates
    )
    memory = np.asarray(controller_memory, dtype=float).reshape((-1,))
    if memory.shape != (2,) or np.any(~np.isfinite(memory)):
        raise ValueError("controller memory is invalid")
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
            product_logs[0] - memory[0] - gains[0] * errors[0],
            times[1] * controller_rates[1] - gains[1] * errors[1],
            product_logs[1] - memory[1] - gains[1] * errors[1],
        ),
        dtype=float,
    )
    raw = np.concatenate((base.raw, controller_raw))
    scaled = np.concatenate((base.scaled, controller_raw))
    names = vapor_holdup_terminal_control_variable_names(contract)
    if raw.shape != scaled.shape or raw.shape != (len(names),):
        raise RuntimeError("terminal-control residual ledger is invalid")
    return VaporHoldupTerminalZeroTimeEvaluation(
        raw=raw,
        scaled=scaled,
        row_names=tuple(row.name for row in contract.rows),
        variable_names=names,
        coordinates=np.asarray(coordinates, dtype=float).copy(),
        level_fraction=levels,
        level_error=errors,
        controller_rate_per_sec=controller_rates.copy(),
        controller_memory=memory.copy(),
        product_log_ratio=product_logs.copy(),
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
        base=base,
    )


__all__ = [
    "VaporHoldupTerminalZeroTimeEvaluation",
    "bumpless_controller_state",
    "controlled_zero_time_coordinates",
    "evaluate_vapor_holdup_terminal_zero_time",
    "vapor_holdup_terminal_control_pattern",
    "vapor_holdup_terminal_control_variable_names",
]
