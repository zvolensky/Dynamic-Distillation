"""Generic bound, vapor-inventory, and energy closure diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .provider_governed_registry_v1 import ColumnTopology
from .vapor_holdup_balances_v1 import VaporHoldupBalanceInputs


@dataclass(frozen=True)
class ActiveCoordinateBound:
    index: int
    variable: str
    block: str
    side: str
    coordinate: float
    bound: float
    distance: float


@dataclass(frozen=True)
class EnergyContribution:
    volume_id: str
    category: str
    label: str
    rate_BTUph: float


@dataclass(frozen=True)
class EnergyClosureRow:
    volume_id: str
    contributions: tuple[EnergyContribution, ...]
    net_energy_transport_BTUph: float
    stationary_energy_residual_BTUph: float


@dataclass(frozen=True)
class LinearizedVariableMovement:
    index: int
    variable: str
    block: str
    coordinate: float
    correction: float
    target_coordinate: float
    lower_bound: float
    upper_bound: float
    bound_violation: bool
    bound_overshoot: float


@dataclass(frozen=True)
class LinearizedClosureResult:
    rank: int
    condition: float
    correction_l2_norm: float
    correction_inf_norm: float
    predicted_residual_inf_norm: float
    maximum_feasible_step_fraction: float
    movements: tuple[LinearizedVariableMovement, ...]


def find_active_coordinate_bounds(
    variables: Sequence[Any],
    coordinates: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    *,
    tolerance: float = 1.0e-8,
) -> tuple[ActiveCoordinateBound, ...]:
    """Find active bounds without relying on stage or component names."""
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    lower = np.asarray(lower_bounds, dtype=float).reshape((-1,))
    upper = np.asarray(upper_bounds, dtype=float).reshape((-1,))
    if len(variables) != point.size or lower.shape != point.shape or upper.shape != point.shape:
        raise ValueError("coordinate variables and bounds must have matching lengths")
    if np.any(~np.isfinite(point)) or np.any(lower >= upper):
        raise ValueError("coordinates and bounds are invalid")
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("bound tolerance must be nonnegative and finite")

    findings: list[ActiveCoordinateBound] = []
    for index, variable in enumerate(variables):
        distances = (float(point[index] - lower[index]), float(upper[index] - point[index]))
        side_index = int(np.argmin(distances))
        distance = distances[side_index]
        if distance <= tolerance:
            findings.append(
                ActiveCoordinateBound(
                    index=index,
                    variable=str(variable.name),
                    block=str(variable.block),
                    side="lower" if side_index == 0 else "upper",
                    coordinate=float(point[index]),
                    bound=float(lower[index] if side_index == 0 else upper[index]),
                    distance=distance,
                )
            )
    return tuple(findings)


def eos_required_vapor_component_inventory(
    vapor_component_inventory_lbmol: Sequence[Sequence[float]],
    free_vapor_volume_ft3: Sequence[float],
    vapor_molar_volume_ft3_lbmol: Sequence[float],
) -> np.ndarray:
    """Return the inventory implied by P, T, Z, free volume, and composition."""
    inventory = np.asarray(vapor_component_inventory_lbmol, dtype=float)
    free_volume = np.asarray(free_vapor_volume_ft3, dtype=float).reshape((-1,))
    molar_volume = np.asarray(vapor_molar_volume_ft3_lbmol, dtype=float).reshape((-1,))
    if inventory.ndim != 2 or inventory.shape[0] != free_volume.size:
        raise ValueError("vapor inventory and volume arrays do not align")
    if molar_volume.shape != free_volume.shape:
        raise ValueError("vapor molar-volume array does not align")
    if (
        np.any(~np.isfinite(inventory))
        or np.any(inventory <= 0.0)
        or np.any(~np.isfinite(free_volume))
        or np.any(free_volume <= 0.0)
        or np.any(~np.isfinite(molar_volume))
        or np.any(molar_volume <= 0.0)
    ):
        raise ValueError("vapor inventory and volumes must be positive and finite")
    composition = inventory / np.sum(inventory, axis=1, keepdims=True)
    required_total = free_volume / molar_volume
    return required_total[:, np.newaxis] * composition


def stationary_energy_closure(
    topology: ColumnTopology,
    endpoint: Any,
    properties: Any,
    inputs: VaporHoldupBalanceInputs,
) -> tuple[EnergyClosureRow, ...]:
    """Build an auditable energy ledger for an arbitrary column topology."""
    volumes = tuple(topology.volume_ids)
    volume_index = {volume: index for index, volume in enumerate(volumes)}
    hydraulic_index = {
        volume: index for index, volume in enumerate(topology.hydraulic_volume_ids)
    }
    liquid_h = np.asarray(properties.liquid_enthalpy_BTU_lbmol, dtype=float)
    vapor_h = np.asarray(properties.vapor_enthalpy_BTU_lbmol, dtype=float)
    liquid_flow = np.asarray(endpoint.hydraulic_liquid_flow_lbmolph, dtype=float)
    vapor_flow = np.asarray(endpoint.vapor_flow_lbmolph, dtype=float)
    if liquid_h.shape != (len(volumes),) or vapor_h.shape != (len(volumes),):
        raise ValueError("enthalpy arrays do not match the column topology")
    if liquid_flow.shape != (len(topology.hydraulic_volume_ids),):
        raise ValueError("liquid-flow array does not match the column topology")
    if vapor_flow.shape != (len(topology.vapor_links),):
        raise ValueError("vapor-flow array does not match the column topology")

    terms: dict[str, list[EnergyContribution]] = {volume: [] for volume in volumes}

    def add(volume: str, category: str, label: str, rate: float) -> None:
        terms[volume].append(
            EnergyContribution(volume, category, label, float(rate))
        )

    for source, destination, symbol in topology.liquid_links:
        source_index = volume_index[source]
        flow = (
            float(inputs.reflux_lbmolph)
            if symbol == "R"
            else float(liquid_flow[hydraulic_index[source]])
        )
        rate = flow * float(liquid_h[source_index])
        add(source, "liquid_link", f"{symbol}:out", -rate)
        add(destination, "liquid_link", f"{symbol}:in", rate)

    for link_index, (source, destination, symbol) in enumerate(topology.vapor_links):
        rate = float(vapor_flow[link_index]) * float(vapor_h[volume_index[source]])
        add(source, "vapor_link", f"{symbol}:out", -rate)
        add(destination, "vapor_link", f"{symbol}:in", rate)

    add(topology.feed_volume, "external", "feed_enthalpy", inputs.feed_enthalpy_BTUph)
    add(topology.top_volume, "external", "condenser_duty", endpoint.condenser_duty_BTUph)
    add(
        topology.top_volume,
        "external",
        "distillate_enthalpy",
        -float(endpoint.distillate_lbmolph) * float(liquid_h[0]),
    )
    add(topology.bottom_volume, "external", "reboiler_duty", inputs.reboiler_duty_BTUph)
    add(
        topology.bottom_volume,
        "external",
        "bottoms_enthalpy",
        -float(endpoint.bottoms_lbmolph) * float(liquid_h[-1]),
    )

    rows = []
    for volume in volumes:
        contributions = tuple(terms[volume])
        net = float(sum(item.rate_BTUph for item in contributions))
        rows.append(
            EnergyClosureRow(
                volume_id=volume,
                contributions=contributions,
                net_energy_transport_BTUph=net,
                stationary_energy_residual_BTUph=-net,
            )
        )
    return tuple(rows)


def linearized_closure_correction(
    variables: Sequence[Any],
    coordinates: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
    scaled_residual: Sequence[float],
    scaled_jacobian: Sequence[Sequence[float]],
) -> LinearizedClosureResult:
    """Compute the full-system Newton correction and its generic bound conflicts."""
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    lower = np.asarray(lower_bounds, dtype=float).reshape((-1,))
    upper = np.asarray(upper_bounds, dtype=float).reshape((-1,))
    residual = np.asarray(scaled_residual, dtype=float).reshape((-1,))
    jacobian = np.asarray(scaled_jacobian, dtype=float)
    size = point.size
    if (
        len(variables) != size
        or lower.shape != point.shape
        or upper.shape != point.shape
        or residual.shape != point.shape
        or jacobian.shape != (size, size)
    ):
        raise ValueError("linearized closure arrays must match the variable ledger")
    if any(
        np.any(~np.isfinite(values))
        for values in (point, lower, upper, residual, jacobian)
    ) or np.any(lower >= upper):
        raise ValueError("linearized closure arrays must be finite and valid")

    singular = np.linalg.svd(jacobian, compute_uv=False)
    tolerance = size * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    correction = np.linalg.lstsq(jacobian, -residual, rcond=None)[0]
    predicted = residual + jacobian @ correction
    target = point + correction

    feasible_fractions = [1.0]
    movements = []
    for index, variable in enumerate(variables):
        delta = float(correction[index])
        if delta > 0.0:
            feasible_fractions.append(max(0.0, float((upper[index] - point[index]) / delta)))
        elif delta < 0.0:
            feasible_fractions.append(max(0.0, float((lower[index] - point[index]) / delta)))
        below = max(float(lower[index] - target[index]), 0.0)
        above = max(float(target[index] - upper[index]), 0.0)
        overshoot = max(below, above)
        movements.append(
            LinearizedVariableMovement(
                index=index,
                variable=str(variable.name),
                block=str(variable.block),
                coordinate=float(point[index]),
                correction=delta,
                target_coordinate=float(target[index]),
                lower_bound=float(lower[index]),
                upper_bound=float(upper[index]),
                bound_violation=bool(overshoot > 0.0),
                bound_overshoot=overshoot,
            )
        )
    return LinearizedClosureResult(
        rank=rank,
        condition=condition,
        correction_l2_norm=float(np.linalg.norm(correction)),
        correction_inf_norm=float(np.max(np.abs(correction))),
        predicted_residual_inf_norm=float(np.max(np.abs(predicted))),
        maximum_feasible_step_fraction=float(min(feasible_fractions)),
        movements=tuple(movements),
    )


def aggregate_residual_block_gradient(
    rows: Sequence[Any],
    scaled_jacobian: Sequence[Sequence[float]],
    residual_scales: Sequence[float],
    *,
    block: str,
) -> np.ndarray:
    """Differentiate the raw sum of a named residual block."""
    jacobian = np.asarray(scaled_jacobian, dtype=float)
    scales = np.asarray(residual_scales, dtype=float).reshape((-1,))
    if jacobian.ndim != 2 or jacobian.shape[0] != len(rows):
        raise ValueError("Jacobian rows do not match the residual ledger")
    if scales.shape != (len(rows),) or np.any(~np.isfinite(scales)):
        raise ValueError("residual scales do not match the residual ledger")
    indices = [index for index, row in enumerate(rows) if str(row.block) == str(block)]
    if not indices:
        raise ValueError(f"residual block {block!r} is not present")
    return np.sum(jacobian[indices] * scales[indices, np.newaxis], axis=0)


__all__ = [
    "ActiveCoordinateBound",
    "EnergyClosureRow",
    "EnergyContribution",
    "LinearizedClosureResult",
    "LinearizedVariableMovement",
    "aggregate_residual_block_gradient",
    "eos_required_vapor_component_inventory",
    "find_active_coordinate_bounds",
    "linearized_closure_correction",
    "stationary_energy_closure",
]
