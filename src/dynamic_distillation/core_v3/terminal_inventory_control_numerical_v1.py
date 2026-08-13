"""Live zero-time numerical kernel for terminal inventory control."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import acos, pi, sqrt
from typing import Any, Sequence

import numpy as np

from .dynamic_dae_numerical_audit_v1 import (
    DynamicImplicitEvaluation,
    LeadingJacobianAudit,
    evaluate_dynamic_implicit_residual,
)
from .provider_call_audit_v1 import ProviderCallAudit
from .provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from .terminal_inventory_control_contract_v1 import (
    TerminalInventoryControlContract,
    TerminalPIParameters,
    TerminalVesselGeometry,
)


@dataclass(frozen=True)
class TerminalLevelSetpoints:
    top_fraction: float
    bottom_fraction: float


@dataclass(frozen=True)
class TerminalInventoryControlEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    solve_coordinates: np.ndarray
    level_fraction: np.ndarray
    level_error: np.ndarray
    controller_rate_per_sec: np.ndarray
    controller_memory: np.ndarray
    product_log_ratio: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    base: DynamicImplicitEvaluation


def horizontal_terminal_total_volume_ft3(
    geometry: TerminalVesselGeometry,
) -> float:
    radius = 0.5 * float(geometry.top_diameter_ft)
    return (
        pi * radius * radius * float(geometry.top_tangent_length_ft)
        + 4.0 * pi * radius**3 / 3.0
    )


def horizontal_terminal_liquid_volume_ft3(
    depth_ft: float,
    geometry: TerminalVesselGeometry,
) -> float:
    radius = 0.5 * float(geometry.top_diameter_ft)
    depth = float(depth_ft)
    if not 0.0 <= depth <= 2.0 * radius:
        raise ValueError("horizontal terminal liquid depth is outside the vessel")
    radicand = max(0.0, 2.0 * radius * depth - depth * depth)
    segment_area = radius * radius * acos((radius - depth) / radius) - (
        radius - depth
    ) * sqrt(radicand)
    shell = segment_area * float(geometry.top_tangent_length_ft)
    paired_heads = pi * depth * depth * (radius - depth / 3.0)
    return shell + paired_heads


def horizontal_terminal_level_fraction(
    liquid_volume_ft3: float,
    geometry: TerminalVesselGeometry,
) -> float:
    volume = float(liquid_volume_ft3)
    total = horizontal_terminal_total_volume_ft3(geometry)
    if not np.isfinite(volume) or volume < 0.0 or volume > total:
        raise ValueError("horizontal terminal liquid volume is outside the vessel")
    low = 0.0
    high = float(geometry.top_diameter_ft)
    for _ in range(80):
        midpoint = 0.5 * (low + high)
        if horizontal_terminal_liquid_volume_ft3(midpoint, geometry) < volume:
            low = midpoint
        else:
            high = midpoint
    return 0.5 * (low + high) / float(geometry.top_diameter_ft)


def vertical_terminal_level_fraction(
    liquid_volume_ft3: float,
    geometry: TerminalVesselGeometry,
) -> float:
    radius = 0.5 * float(geometry.bottom_diameter_ft)
    total = pi * radius * radius * float(geometry.bottom_height_ft)
    volume = float(liquid_volume_ft3)
    if not np.isfinite(volume) or volume < 0.0 or volume > total:
        raise ValueError("vertical terminal liquid volume is outside the vessel")
    return volume / total


def terminal_level_fractions(
    inventory_lbmol: Sequence[Sequence[float]],
    liquid_density_lbmol_ft3: Sequence[float],
    geometry: TerminalVesselGeometry,
) -> np.ndarray:
    inventory = np.asarray(inventory_lbmol, dtype=float)
    density = np.asarray(liquid_density_lbmol_ft3, dtype=float).reshape((-1,))
    if (
        inventory.ndim != 2
        or density.shape != (inventory.shape[0],)
        or np.any(inventory <= 0.0)
        or np.any(density <= 0.0)
        or np.any(~np.isfinite(inventory))
        or np.any(~np.isfinite(density))
    ):
        raise ValueError("terminal inventory or liquid density is invalid")
    liquid_volume = np.sum(inventory, axis=1) / density
    return np.asarray(
        (
            horizontal_terminal_level_fraction(float(liquid_volume[0]), geometry),
            vertical_terminal_level_fraction(float(liquid_volume[-1]), geometry),
        ),
        dtype=float,
    )


def terminal_inventory_control_variable_names(
    contract: TerminalInventoryControlContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (
            *contract.derivative_variables,
            *contract.algebraic_variables,
        )
    )


def terminal_inventory_control_pattern(
    contract: TerminalInventoryControlContract,
) -> np.ndarray:
    names = terminal_inventory_control_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                pattern[row_index, index[dependency]] = True
    return pattern


def _split_coordinates(
    contract: TerminalInventoryControlContract,
    solve_coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("terminal-control solve coordinates are invalid")
    base_rate_count = len(contract.base.derivative_variables)
    controller_rate_count = 2
    base_algebraic_count = len(contract.base.algebraic_variables)
    base_rate_stop = base_rate_count
    controller_rate_stop = base_rate_stop + controller_rate_count
    base_algebraic_stop = controller_rate_stop + base_algebraic_count
    return (
        point[:base_rate_stop],
        point[base_rate_stop:controller_rate_stop],
        point[controller_rate_stop:base_algebraic_stop],
        point[base_algebraic_stop:],
    )


def evaluate_terminal_inventory_control_residual(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    controller_memory: Sequence[float],
    level_setpoints: TerminalLevelSetpoints,
    solve_coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> TerminalInventoryControlEvaluation:
    base_rates, controller_rates, base_algebraic, product_logs = _split_coordinates(
        contract, solve_coordinates
    )
    memory = np.asarray(controller_memory, dtype=float).reshape((-1,))
    if memory.shape != (2,) or np.any(~np.isfinite(memory)):
        raise ValueError("terminal controller memory is invalid")
    setpoints = np.asarray(
        (level_setpoints.top_fraction, level_setpoints.bottom_fraction),
        dtype=float,
    )
    if np.any(~np.isfinite(setpoints)) or np.any(
        (setpoints <= 0.0) | (setpoints >= 1.0)
    ):
        raise ValueError("terminal level setpoints are invalid")
    products = np.asarray(
        (
            float(template.distillate_lbmolph) * np.exp(product_logs[0]),
            float(template.bottoms_lbmolph) * np.exp(product_logs[1]),
        ),
        dtype=float,
    )
    if np.any(~np.isfinite(products)) or np.any(products <= 0.0):
        raise ValueError("terminal controller product output is invalid")
    live_template = replace(
        template,
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
    )
    base = evaluate_dynamic_implicit_residual(
        contract.base,
        spec,
        reference,
        live_template,
        provider,
        call_audit,
        inventory_lbmol=inventory_lbmol,
        rate_coordinates=base_rates,
        algebraic_coordinates=base_algebraic,
        storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
        fixed_steady_scales=fixed_steady_scales,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    levels = terminal_level_fractions(
        inventory_lbmol,
        base.steady_evaluation.properties.liquid_density_lbmol_ft3,
        contract.geometry,
    )
    errors = levels - setpoints
    tuning: TerminalPIParameters = contract.controllers
    gains = np.asarray((tuning.top_kc, tuning.bottom_kc), dtype=float)
    times = np.asarray((tuning.top_ti_sec, tuning.bottom_ti_sec), dtype=float)
    controller_raw = np.asarray(
        (
            times[0] * controller_rates[0] - gains[0] * errors[0],
            product_logs[0] - memory[0] - gains[0] * errors[0],
            times[1] * controller_rates[1] - gains[1] * errors[1],
            product_logs[1] - memory[1] - gains[1] * errors[1],
        ),
        dtype=float,
    )
    return TerminalInventoryControlEvaluation(
        raw=np.concatenate((base.raw, controller_raw)),
        scaled=np.concatenate((base.scaled, controller_raw)),
        row_names=tuple(row.name for row in contract.rows),
        variable_names=terminal_inventory_control_variable_names(contract),
        solve_coordinates=np.asarray(solve_coordinates, dtype=float).copy(),
        level_fraction=levels,
        level_error=errors,
        controller_rate_per_sec=controller_rates.copy(),
        controller_memory=memory.copy(),
        product_log_ratio=product_logs.copy(),
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
        base=base,
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


def audit_terminal_inventory_control_leading_jacobian(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    controller_memory: Sequence[float],
    level_setpoints: TerminalLevelSetpoints,
    root_solve_coordinates: Sequence[float],
    storage_gradient_BTU_lbmol: Sequence[Sequence[float]],
    fixed_steady_scales: Sequence[float],
    step: float,
    coupling_tolerance: float,
    state_id: str,
) -> LeadingJacobianAudit:
    point = np.asarray(root_solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),):
        raise ValueError("terminal-control root coordinates are invalid")
    matrix = np.empty((len(contract.rows), point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = evaluate_terminal_inventory_control_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            controller_memory=controller_memory,
            level_setpoints=level_setpoints,
            solve_coordinates=point + delta,
            storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{state_id}:{column}:plus",
            evaluation_kind="jacobian",
        ).scaled
        minus = evaluate_terminal_inventory_control_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=inventory_lbmol,
            controller_memory=controller_memory,
            level_setpoints=level_setpoints,
            solve_coordinates=point - delta,
            storage_gradient_BTU_lbmol=storage_gradient_BTU_lbmol,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{state_id}:{column}:minus",
            evaluation_kind="jacobian",
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    pattern = terminal_inventory_control_pattern(contract)
    names = terminal_inventory_control_variable_names(contract)
    unexpected = tuple(
        f"{contract.rows[row].name} <- {names[column]}"
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
            names[index] for index in np.flatnonzero(column_norm <= coupling_tolerance)
        ),
        unexpected_couplings=unexpected,
    )


__all__ = [
    "TerminalInventoryControlEvaluation",
    "TerminalLevelSetpoints",
    "audit_terminal_inventory_control_leading_jacobian",
    "evaluate_terminal_inventory_control_residual",
    "horizontal_terminal_level_fraction",
    "horizontal_terminal_liquid_volume_ft3",
    "horizontal_terminal_total_volume_ft3",
    "terminal_inventory_control_pattern",
    "terminal_inventory_control_variable_names",
    "terminal_level_fractions",
    "vertical_terminal_level_fraction",
]
