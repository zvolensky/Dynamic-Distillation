"""Live zero-time kernel for the Core V3 controlled-terminal DAE."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import acos, pi, sqrt
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    ConservedNUPressureDAEContract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_numerical_v1 import (
    ConservedNUPressureEvaluation,
    evaluate_conserved_nu_pressure_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_dynamic_contract_v1 import (
    ControlledTerminalDynamicContract,
    LevelControllerSpecification,
    TerminalGeometry,
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


@dataclass(frozen=True)
class TerminalLevelSetpoints:
    drum_fraction: float
    sump_fraction: float


@dataclass(frozen=True)
class ControlledTerminalZeroTimeEvaluation:
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
    base: ConservedNUPressureEvaluation


def horizontal_drum_total_volume_ft3(geometry: TerminalGeometry) -> float:
    radius = 0.5 * float(geometry.drum_diameter_ft)
    return (
        pi * radius * radius * float(geometry.drum_tangent_length_ft)
        + 4.0 * pi * radius**3 / 3.0
    )


def horizontal_drum_liquid_volume_ft3(
    depth_ft: float,
    geometry: TerminalGeometry,
) -> float:
    radius = 0.5 * float(geometry.drum_diameter_ft)
    depth = float(depth_ft)
    if not 0.0 <= depth <= 2.0 * radius:
        raise ValueError("horizontal-drum liquid depth is outside the vessel")
    radicand = max(0.0, 2.0 * radius * depth - depth * depth)
    segment_area = (
        radius * radius * acos((radius - depth) / radius)
        - (radius - depth) * sqrt(radicand)
    )
    shell = segment_area * float(geometry.drum_tangent_length_ft)
    paired_heads = pi * depth * depth * (radius - depth / 3.0)
    return shell + paired_heads


def horizontal_drum_level_fraction(
    liquid_volume_ft3: float,
    geometry: TerminalGeometry,
) -> float:
    volume = float(liquid_volume_ft3)
    total = horizontal_drum_total_volume_ft3(geometry)
    if not np.isfinite(volume) or volume < 0.0 or volume > total:
        raise ValueError("horizontal-drum liquid volume is outside the vessel")
    low = 0.0
    high = float(geometry.drum_diameter_ft)
    for _ in range(80):
        midpoint = 0.5 * (low + high)
        if horizontal_drum_liquid_volume_ft3(midpoint, geometry) < volume:
            low = midpoint
        else:
            high = midpoint
    return 0.5 * (low + high) / float(geometry.drum_diameter_ft)


def vertical_sump_level_fraction(
    liquid_volume_ft3: float,
    geometry: TerminalGeometry,
) -> float:
    radius = 0.5 * float(geometry.sump_diameter_ft)
    total = pi * radius * radius * float(geometry.sump_height_ft)
    volume = float(liquid_volume_ft3)
    if not np.isfinite(volume) or volume < 0.0 or volume > total:
        raise ValueError("sump liquid volume is outside the vessel")
    return volume / total


def terminal_level_fractions(
    inventory_lbmol: Sequence[Sequence[float]],
    liquid_density_lbmol_ft3: Sequence[float],
    geometry: TerminalGeometry,
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
        raise ValueError("terminal inventory or density is invalid")
    volume = np.sum(inventory, axis=1) / density
    return np.asarray(
        (
            horizontal_drum_level_fraction(float(volume[0]), geometry),
            vertical_sump_level_fraction(float(volume[-1]), geometry),
        ),
        dtype=float,
    )


def controlled_terminal_zero_time_variable_names(
    contract: ControlledTerminalDynamicContract,
) -> tuple[str, ...]:
    return tuple(
        variable.name
        for variable in (*contract.derivative_variables, *contract.algebraic_variables)
    )


def controlled_terminal_zero_time_pattern(
    contract: ControlledTerminalDynamicContract,
) -> np.ndarray:
    names = controlled_terminal_zero_time_variable_names(contract)
    index = {name: column for column, name in enumerate(names)}
    pattern = np.zeros((len(contract.rows), len(names)), dtype=bool)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            if dependency in index:
                pattern[row_index, index[dependency]] = True
    return pattern


def _split_coordinates(
    contract: ControlledTerminalDynamicContract,
    coordinates: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    expected = len(contract.rows)
    if point.shape != (expected,) or np.any(~np.isfinite(point)):
        raise ValueError("controlled-terminal zero-time coordinates are invalid")
    base_rate_count = len(contract.base.derivative_variables)
    controller_rate_count = 2
    base_algebraic_count = len(contract.base.algebraic_variables)
    rate_stop = base_rate_count
    controller_stop = rate_stop + controller_rate_count
    algebraic_stop = controller_stop + base_algebraic_count
    base_coordinates = np.concatenate(
        (point[:rate_stop], point[controller_stop:algebraic_stop])
    )
    return base_coordinates, point[rate_stop:controller_stop], point[algebraic_stop:]


def evaluate_controlled_terminal_zero_time(
    contract: ControlledTerminalDynamicContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    inventory_lbmol: Sequence[Sequence[float]],
    lower_internal_energy_BTU: Sequence[float],
    controller_memory: Sequence[float],
    level_setpoints: TerminalLevelSetpoints,
    solve_coordinates: Sequence[float],
    top_storage_gradient_BTU_lbmol: Sequence[float],
    energy_rate_scales_BTUph: Sequence[float],
    fixed_steady_scales: Sequence[float],
    storage_scales_BTU: Sequence[float],
    numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> ControlledTerminalZeroTimeEvaluation:
    base_coordinates, controller_rates, product_logs = _split_coordinates(
        contract, solve_coordinates
    )
    memory = np.asarray(controller_memory, dtype=float).reshape((-1,))
    if memory.shape != (2,) or np.any(~np.isfinite(memory)):
        raise ValueError("controller memory is invalid")
    products = np.asarray(
        (
            float(template.distillate_lbmolph) * np.exp(product_logs[0]),
            float(template.bottoms_lbmolph) * np.exp(product_logs[1]),
        ),
        dtype=float,
    )
    if np.any(~np.isfinite(products)) or np.any(products <= 0.0):
        raise ValueError("controlled-terminal product output is invalid")
    live_template = replace(
        template,
        distillate_lbmolph=float(products[0]),
        bottoms_lbmolph=float(products[1]),
    )
    base = evaluate_conserved_nu_pressure_residual(
        contract.base,
        spec,
        reference,
        live_template,
        provider,
        call_audit,
        inventory_lbmol=inventory_lbmol,
        lower_internal_energy_BTU=lower_internal_energy_BTU,
        top_storage_gradient_BTU_lbmol=top_storage_gradient_BTU_lbmol,
        energy_rate_scales_BTUph=energy_rate_scales_BTUph,
        solve_coordinates=base_coordinates,
        fixed_steady_scales=fixed_steady_scales,
        storage_scales_BTU=storage_scales_BTU,
        numerical=numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    density = (
        base.pressure_evaluation.base_evaluation.steady_evaluation.properties
        .liquid_density_lbmol_ft3
    )
    levels = terminal_level_fractions(inventory_lbmol, density, contract.geometry)
    setpoints = np.asarray(
        (level_setpoints.drum_fraction, level_setpoints.sump_fraction), dtype=float
    )
    if np.any(~np.isfinite(setpoints)) or np.any((setpoints <= 0.0) | (setpoints >= 1.0)):
        raise ValueError("terminal level setpoints are invalid")
    errors = levels - setpoints
    tuning: LevelControllerSpecification = contract.controllers
    gains = np.asarray((tuning.drum_kc, tuning.sump_kc), dtype=float)
    times = np.asarray((tuning.drum_ti_sec, tuning.sump_ti_sec), dtype=float)
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
    return ControlledTerminalZeroTimeEvaluation(
        raw=raw,
        scaled=scaled,
        row_names=tuple(row.name for row in contract.rows),
        variable_names=controlled_terminal_zero_time_variable_names(contract),
        coordinates=np.asarray(solve_coordinates, dtype=float).copy(),
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
    "ControlledTerminalZeroTimeEvaluation",
    "TerminalLevelSetpoints",
    "controlled_terminal_zero_time_pattern",
    "controlled_terminal_zero_time_variable_names",
    "evaluate_controlled_terminal_zero_time",
    "horizontal_drum_level_fraction",
    "horizontal_drum_liquid_volume_ft3",
    "horizontal_drum_total_volume_ft3",
    "terminal_level_fractions",
    "vertical_sump_level_fraction",
]
