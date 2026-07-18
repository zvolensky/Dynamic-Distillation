"""Live residual and Jacobian audit for the DD-084 numerical gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    VAPOR_LINKS,
    VOLUME_IDS,
    build_energy_owned_vapor_registry,
)
from dynamic_distillation.core_v2.five_volume_residual_gate_v1 import (
    _francis_flow,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    OneVolumeGeometry,
    normalize_composition,
    vapor_from_logits,
    vapor_logits,
)


@dataclass(frozen=True)
class EnergyOwnedOperatingSpec:
    component_names: tuple[str, ...]
    pressure_psia: np.ndarray
    reflux_lbmolph: float
    feed_component_lbmolph: np.ndarray
    feed_enthalpy_BTUph: float
    condenser_duty_BTUph: float
    reboiler_duty_BTUph: float
    terminal_liquid_targets_lbmol: np.ndarray
    hydraulic_geometry: tuple[OneVolumeGeometry, ...]
    temperature_scale_F: float = 100.0


@dataclass(frozen=True)
class EnergyOwnedReference:
    liquid_moles_lbmol: np.ndarray
    liquid_mole_fraction: np.ndarray
    temperature_F: np.ndarray
    vapor_mole_fraction: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float


@dataclass(frozen=True)
class CoordinateLayout:
    names: tuple[str, ...]
    liquid_moles: slice
    liquid_logits: slice
    temperature: slice
    vapor_logits: slice
    liquid_flows: slice
    vapor_flows: slice
    distillate: int
    bottoms: int


@dataclass(frozen=True)
class EnergyOwnedState:
    liquid_moles_lbmol: np.ndarray
    liquid_mole_fraction: np.ndarray
    temperature_F: np.ndarray
    vapor_mole_fraction: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float


@dataclass(frozen=True)
class EnergyOwnedProperties:
    liquid_enthalpy_BTU_lbmol: np.ndarray
    liquid_density_lbmol_ft3: np.ndarray
    vapor_enthalpy_BTU_lbmol: np.ndarray
    francis_flow_lbmolph: np.ndarray
    liquid_height_ft: np.ndarray
    over_weir_head_ft: np.ndarray


@dataclass(frozen=True)
class ResidualRow:
    name: str
    block: str
    owner: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class ResidualEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    rows: tuple[ResidualRow, ...]
    state: EnergyOwnedState
    properties: EnergyOwnedProperties
    component_telescoping_error_lbmolph: np.ndarray
    component_telescoping_relative_error: float
    energy_telescoping_error_BTUph: float
    energy_telescoping_relative_error: float
    clipping_or_projection_used: bool = False
    property_fallback_used: bool = False


@dataclass(frozen=True)
class NumericalJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]


def _validate_spec(spec: EnergyOwnedOperatingSpec) -> None:
    component_count = len(spec.component_names)
    if component_count < 2:
        raise ValueError("DD-084 requires at least two components")
    if np.asarray(spec.pressure_psia).shape != (len(VOLUME_IDS),):
        raise ValueError("pressure profile shape is invalid")
    if np.any(~np.isfinite(spec.pressure_psia)) or np.any(spec.pressure_psia <= 0):
        raise ValueError("pressures must be finite and positive")
    if np.any(np.diff(spec.pressure_psia) <= 0):
        raise ValueError("pressure must increase monotonically toward the bottom")
    feed = np.asarray(spec.feed_component_lbmolph, dtype=float)
    if feed.shape != (component_count,) or np.any(feed < 0):
        raise ValueError("feed component flow is invalid")
    if np.asarray(spec.terminal_liquid_targets_lbmol).shape != (2,):
        raise ValueError("two terminal liquid targets are required")
    if len(spec.hydraulic_geometry) != len(HYDRAULIC_VOLUME_IDS):
        raise ValueError("three hydraulic geometry records are required")
    positive = (
        spec.reflux_lbmolph,
        *np.asarray(spec.terminal_liquid_targets_lbmol, dtype=float),
    )
    if any(not np.isfinite(value) or value <= 0 for value in positive):
        raise ValueError("operating flow and inventory parameters must be positive")


def _validate_reference(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
) -> None:
    component_count = len(spec.component_names)
    shapes = (
        (reference.liquid_moles_lbmol, (len(VOLUME_IDS),)),
        (
            reference.liquid_mole_fraction,
            (len(VOLUME_IDS), component_count),
        ),
        (reference.temperature_F, (len(VOLUME_IDS),)),
        (
            reference.vapor_mole_fraction,
            (len(EQUILIBRIUM_VOLUME_IDS), component_count),
        ),
        (
            reference.hydraulic_liquid_flow_lbmolph,
            (len(HYDRAULIC_VOLUME_IDS),),
        ),
        (reference.vapor_flow_lbmolph, (len(VAPOR_LINKS),)),
    )
    for values, expected in shapes:
        if np.asarray(values).shape != expected:
            raise ValueError(f"reference shape {np.asarray(values).shape} != {expected}")
    positive_arrays = (
        reference.liquid_moles_lbmol,
        reference.liquid_mole_fraction,
        reference.vapor_mole_fraction,
        reference.hydraulic_liquid_flow_lbmolph,
        reference.vapor_flow_lbmolph,
    )
    if any(np.any(np.asarray(values, dtype=float) <= 0) for values in positive_arrays):
        raise ValueError("reference physical quantities must be positive")
    if reference.distillate_lbmolph <= 0 or reference.bottoms_lbmolph <= 0:
        raise ValueError("reference product flows must be positive")
    for values in (
        *np.asarray(reference.liquid_mole_fraction),
        *np.asarray(reference.vapor_mole_fraction),
    ):
        normalize_composition(values)


def coordinate_layout(spec: EnergyOwnedOperatingSpec) -> CoordinateLayout:
    _validate_spec(spec)
    names: list[str] = []
    independent_count = len(spec.component_names) - 1

    start = len(names)
    names.extend(f"log_NL[{volume}]" for volume in VOLUME_IDS)
    liquid_moles = slice(start, len(names))

    start = len(names)
    for volume in VOLUME_IDS:
        names.extend(
            f"x_logit[{volume},{component}]"
            for component in spec.component_names[:-1]
        )
    liquid_logits = slice(start, len(names))

    start = len(names)
    names.extend(f"T[{volume}]" for volume in VOLUME_IDS)
    temperature = slice(start, len(names))

    start = len(names)
    for volume in EQUILIBRIUM_VOLUME_IDS:
        names.extend(
            f"y_logit[{volume},{component}]"
            for component in spec.component_names[:-1]
        )
    vapor_logits_slice = slice(start, len(names))

    start = len(names)
    names.extend(f"log_L[{volume}]" for volume in HYDRAULIC_VOLUME_IDS)
    liquid_flows = slice(start, len(names))

    start = len(names)
    names.extend(f"log_{symbol}" for _, _, symbol in VAPOR_LINKS)
    vapor_flows = slice(start, len(names))

    distillate = len(names)
    names.append("log_D")
    bottoms = len(names)
    names.append("log_B")
    expected = 9 * len(spec.component_names) + 10
    if independent_count < 1 or len(names) != expected:
        raise RuntimeError("DD-084 coordinate count is inconsistent")
    return CoordinateLayout(
        names=tuple(names),
        liquid_moles=liquid_moles,
        liquid_logits=liquid_logits,
        temperature=temperature,
        vapor_logits=vapor_logits_slice,
        liquid_flows=liquid_flows,
        vapor_flows=vapor_flows,
        distillate=distillate,
        bottoms=bottoms,
    )


def decode_coordinates(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    coordinates: Sequence[float],
) -> EnergyOwnedState:
    _validate_reference(spec, reference)
    layout = coordinate_layout(spec)
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.size != len(layout.names):
        raise ValueError(f"expected {len(layout.names)} coordinates, got {point.size}")
    component_count = len(spec.component_names)
    independent_count = component_count - 1
    liquid_moles = np.asarray(reference.liquid_moles_lbmol, dtype=float) * np.exp(
        point[layout.liquid_moles]
    )
    liquid_x = np.empty((len(VOLUME_IDS), component_count), dtype=float)
    liquid_offsets = point[layout.liquid_logits].reshape(
        (len(VOLUME_IDS), independent_count)
    )
    for index, values in enumerate(reference.liquid_mole_fraction):
        liquid_x[index] = vapor_from_logits(
            vapor_logits(values) + liquid_offsets[index]
        )
    temperature = np.asarray(reference.temperature_F, dtype=float) + (
        float(spec.temperature_scale_F) * point[layout.temperature]
    )
    vapor_y = np.empty(
        (len(EQUILIBRIUM_VOLUME_IDS), component_count),
        dtype=float,
    )
    vapor_offsets = point[layout.vapor_logits].reshape(
        (len(EQUILIBRIUM_VOLUME_IDS), independent_count)
    )
    for index, values in enumerate(reference.vapor_mole_fraction):
        vapor_y[index] = vapor_from_logits(
            vapor_logits(values) + vapor_offsets[index]
        )
    liquid_flow = np.asarray(
        reference.hydraulic_liquid_flow_lbmolph,
        dtype=float,
    ) * np.exp(point[layout.liquid_flows])
    vapor_flow = np.asarray(
        reference.vapor_flow_lbmolph,
        dtype=float,
    ) * np.exp(point[layout.vapor_flows])
    return EnergyOwnedState(
        liquid_moles_lbmol=liquid_moles,
        liquid_mole_fraction=liquid_x,
        temperature_F=temperature,
        vapor_mole_fraction=vapor_y,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        vapor_flow_lbmolph=vapor_flow,
        distillate_lbmolph=float(reference.distillate_lbmolph)
        * float(np.exp(point[layout.distillate])),
        bottoms_lbmolph=float(reference.bottoms_lbmolph)
        * float(np.exp(point[layout.bottoms])),
    )


def _full_fugacity_residual(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: np.ndarray,
    vapor_y: np.ndarray,
) -> np.ndarray:
    phi_liquid = np.asarray(
        provider.phase_fugacity_coefficients(
            "liquid",
            float(temperature_F),
            float(pressure_psia),
            liquid_x.tolist(),
        ),
        dtype=float,
    ).reshape(liquid_x.shape)
    phi_vapor = np.asarray(
        provider.phase_fugacity_coefficients(
            "vapor",
            float(temperature_F),
            float(pressure_psia),
            vapor_y.tolist(),
        ),
        dtype=float,
    ).reshape(vapor_y.shape)
    if (
        np.any(~np.isfinite(phi_liquid))
        or np.any(~np.isfinite(phi_vapor))
        or np.any(phi_liquid <= 0)
        or np.any(phi_vapor <= 0)
    ):
        raise RuntimeError("live fugacity coefficients are non-physical")
    return np.log(vapor_y * phi_vapor / (liquid_x * phi_liquid))


def _evaluate_properties(
    spec: EnergyOwnedOperatingSpec,
    state: EnergyOwnedState,
    provider: Any,
) -> tuple[EnergyOwnedProperties, np.ndarray]:
    volume_count = len(VOLUME_IDS)
    h_liquid = np.empty(volume_count, dtype=float)
    density = np.empty(volume_count, dtype=float)
    h_vapor = np.full(volume_count, np.nan, dtype=float)
    francis = np.full(volume_count, np.nan, dtype=float)
    height = np.full(volume_count, np.nan, dtype=float)
    head = np.full(volume_count, np.nan, dtype=float)
    equilibrium: list[float] = []
    for index, volume in enumerate(VOLUME_IDS):
        h_liquid[index] = float(
            provider.phase_enthalpy_BTU_lbmol(
                "liquid",
                float(state.temperature_F[index]),
                float(spec.pressure_psia[index]),
                state.liquid_mole_fraction[index].tolist(),
            )
        )
        density_raw = provider.liquid_density_lbmol_ft3(
            float(state.temperature_F[index]),
            float(spec.pressure_psia[index]),
            state.liquid_mole_fraction[index].tolist(),
        )
        if density_raw is None:
            raise RuntimeError("live liquid density is unavailable")
        density[index] = float(density_raw)
        if not np.isfinite(density[index]) or density[index] <= 0:
            raise RuntimeError("live liquid density is non-physical")
        if volume in EQUILIBRIUM_VOLUME_IDS:
            vapor_index = EQUILIBRIUM_VOLUME_IDS.index(volume)
            equilibrium.extend(
                _full_fugacity_residual(
                    provider,
                    temperature_F=float(state.temperature_F[index]),
                    pressure_psia=float(spec.pressure_psia[index]),
                    liquid_x=state.liquid_mole_fraction[index],
                    vapor_y=state.vapor_mole_fraction[vapor_index],
                )
            )
            h_vapor[index] = float(
                provider.phase_enthalpy_BTU_lbmol(
                    "vapor",
                    float(state.temperature_F[index]),
                    float(spec.pressure_psia[index]),
                    state.vapor_mole_fraction[vapor_index].tolist(),
                )
            )
        if volume in HYDRAULIC_VOLUME_IDS:
            hydraulic_index = HYDRAULIC_VOLUME_IDS.index(volume)
            francis[index], height[index], head[index] = _francis_flow(
                liquid_moles_lbmol=float(state.liquid_moles_lbmol[index]),
                density_lbmol_ft3=float(density[index]),
                geometry=spec.hydraulic_geometry[hydraulic_index],
            )
    if np.any(~np.isfinite(h_liquid)) or np.any(~np.isfinite(h_vapor[1:])):
        raise RuntimeError("live phase enthalpy is non-finite")
    return (
        EnergyOwnedProperties(
            liquid_enthalpy_BTU_lbmol=h_liquid,
            liquid_density_lbmol_ft3=density,
            vapor_enthalpy_BTU_lbmol=h_vapor,
            francis_flow_lbmolph=francis,
            liquid_height_ft=height,
            over_weir_head_ft=head,
        ),
        np.asarray(equilibrium, dtype=float),
    )


def _component_balances(
    spec: EnergyOwnedOperatingSpec,
    state: EnergyOwnedState,
) -> np.ndarray:
    x = state.liquid_mole_fraction
    y_rect, y_feed, y_strip, y_bottom = state.vapor_mole_fraction
    l_rect, l_feed, l_strip = state.hydraulic_liquid_flow_lbmolph
    v_bottom_strip, v_strip_feed, v_feed_rect, v_rect_drum = (
        state.vapor_flow_lbmolph
    )
    reflux = float(spec.reflux_lbmolph)
    d = float(state.distillate_lbmolph)
    b = float(state.bottoms_lbmolph)
    return np.asarray(
        (
            v_rect_drum * y_rect - (reflux + d) * x[0],
            reflux * x[0]
            + v_feed_rect * y_feed
            - l_rect * x[1]
            - v_rect_drum * y_rect,
            l_rect * x[1]
            + v_strip_feed * y_strip
            + np.asarray(spec.feed_component_lbmolph, dtype=float)
            - l_feed * x[2]
            - v_feed_rect * y_feed,
            l_feed * x[2]
            + v_bottom_strip * y_bottom
            - l_strip * x[3]
            - v_strip_feed * y_strip,
            l_strip * x[3] - b * x[4] - v_bottom_strip * y_bottom,
        ),
        dtype=float,
    )


def _energy_balances(
    spec: EnergyOwnedOperatingSpec,
    state: EnergyOwnedState,
    properties: EnergyOwnedProperties,
) -> np.ndarray:
    h_l = properties.liquid_enthalpy_BTU_lbmol
    h_v = properties.vapor_enthalpy_BTU_lbmol
    l_rect, l_feed, l_strip = state.hydraulic_liquid_flow_lbmolph
    v_bottom_strip, v_strip_feed, v_feed_rect, v_rect_drum = (
        state.vapor_flow_lbmolph
    )
    reflux = float(spec.reflux_lbmolph)
    d = float(state.distillate_lbmolph)
    b = float(state.bottoms_lbmolph)
    return np.asarray(
        (
            v_rect_drum * h_v[1]
            + float(spec.condenser_duty_BTUph)
            - (reflux + d) * h_l[0],
            reflux * h_l[0]
            + v_feed_rect * h_v[2]
            - l_rect * h_l[1]
            - v_rect_drum * h_v[1],
            l_rect * h_l[1]
            + v_strip_feed * h_v[3]
            + float(spec.feed_enthalpy_BTUph)
            - l_feed * h_l[2]
            - v_feed_rect * h_v[2],
            l_feed * h_l[2]
            + v_bottom_strip * h_v[4]
            - l_strip * h_l[3]
            - v_strip_feed * h_v[3],
            l_strip * h_l[3]
            + float(spec.reboiler_duty_BTUph)
            - b * h_l[4]
            - v_bottom_strip * h_v[4],
        ),
        dtype=float,
    )


def _coordinate_dependency_name(name: str) -> str | None:
    if name.startswith("NL["):
        return "log_" + name
    if name.startswith("x["):
        return name.replace("x[", "x_logit[", 1)
    if name.startswith("y["):
        return name.replace("y[", "y_logit[", 1)
    if name.startswith("L[") or name.startswith("V["):
        return "log_" + name
    if name == "D" or name == "B":
        return "log_" + name
    if name.startswith("T["):
        return name
    return None


def residual_rows(spec: EnergyOwnedOperatingSpec) -> tuple[ResidualRow, ...]:
    registry = build_energy_owned_vapor_registry(spec.component_names)
    rows = []
    for entry in registry.residuals:
        dependencies = tuple(
            mapped
            for dependency in entry.dependencies
            if (mapped := _coordinate_dependency_name(dependency)) is not None
        )
        rows.append(
            ResidualRow(
                name=entry.name,
                block=entry.block,
                owner=entry.owner,
                dependencies=tuple(dict.fromkeys(dependencies)),
            )
        )
    return tuple(rows)


def _residual_scales(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    properties: EnergyOwnedProperties,
) -> np.ndarray:
    flow_scale = max(
        float(np.sum(spec.feed_component_lbmolph)),
        float(spec.reflux_lbmolph),
        float(np.max(reference.hydraulic_liquid_flow_lbmolph)),
        float(np.max(reference.vapor_flow_lbmolph)),
        float(reference.distillate_lbmolph),
        float(reference.bottoms_lbmolph),
        1.0,
    )
    enthalpy_scale = max(
        float(np.max(np.abs(properties.liquid_enthalpy_BTU_lbmol))),
        float(np.nanmax(np.abs(properties.vapor_enthalpy_BTU_lbmol))),
        1.0,
    )
    energy_scale = max(
        abs(float(spec.feed_enthalpy_BTUph)),
        abs(float(spec.condenser_duty_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        flow_scale * enthalpy_scale,
        1.0,
    )
    values = []
    for row in residual_rows(spec):
        if row.block == "full_phase_equilibrium":
            values.append(1.0)
        elif row.block == "component_balance":
            values.append(flow_scale)
        elif row.block == "energy_balance":
            values.append(energy_scale)
        elif row.block == "francis_hydraulics":
            hydraulic_index = HYDRAULIC_VOLUME_IDS.index(row.owner)
            values.append(
                max(
                    float(reference.hydraulic_liquid_flow_lbmolph[hydraulic_index]),
                    1.0,
                )
            )
        elif row.block == "terminal_level_specification":
            target_index = 0 if row.owner == VOLUME_IDS[0] else 1
            values.append(
                max(float(spec.terminal_liquid_targets_lbmol[target_index]), 1.0)
            )
        else:
            raise RuntimeError(f"unscaled DD-084 residual block {row.block!r}")
    return np.asarray(values, dtype=float)


def evaluate_residual(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float] | None = None,
) -> ResidualEvaluation:
    state = decode_coordinates(spec, reference, coordinates)
    properties, equilibrium = _evaluate_properties(spec, state, provider)
    component = _component_balances(spec, state)
    energy = _energy_balances(spec, state, properties)
    francis = np.asarray(
        [
            state.hydraulic_liquid_flow_lbmolph[index]
            - properties.francis_flow_lbmolph[VOLUME_IDS.index(volume)]
            for index, volume in enumerate(HYDRAULIC_VOLUME_IDS)
        ],
        dtype=float,
    )
    terminal = np.asarray(
        (
            state.liquid_moles_lbmol[0] - spec.terminal_liquid_targets_lbmol[0],
            state.liquid_moles_lbmol[-1] - spec.terminal_liquid_targets_lbmol[1],
        ),
        dtype=float,
    )
    balance_values: list[float] = []
    for index in range(len(VOLUME_IDS)):
        balance_values.extend(float(value) for value in component[index])
        balance_values.append(float(energy[index]))
    raw = np.concatenate(
        (
            equilibrium,
            np.asarray(balance_values, dtype=float),
            francis,
            terminal,
        )
    )
    rows = residual_rows(spec)
    if raw.size != len(rows):
        raise RuntimeError(f"DD-084 residual size {raw.size} != {len(rows)}")
    scales = (
        _residual_scales(spec, reference, properties)
        if fixed_scales is None
        else np.asarray(fixed_scales, dtype=float).reshape((-1,))
    )
    if scales.shape != raw.shape or np.any(~np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError("DD-084 residual scales are invalid")

    component_external = (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )
    component_error = np.sum(component, axis=0) - component_external
    component_denominator = max(
        float(np.max(np.abs(spec.feed_component_lbmolph))),
        float(np.max(np.abs(component_external))),
        1.0,
    )
    energy_external = (
        float(spec.feed_enthalpy_BTUph)
        + float(spec.condenser_duty_BTUph)
        + float(spec.reboiler_duty_BTUph)
        - state.distillate_lbmolph * properties.liquid_enthalpy_BTU_lbmol[0]
        - state.bottoms_lbmolph * properties.liquid_enthalpy_BTU_lbmol[-1]
    )
    energy_error = float(np.sum(energy) - energy_external)
    energy_denominator = max(
        abs(float(spec.feed_enthalpy_BTUph)),
        abs(float(spec.condenser_duty_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(energy_external),
        1.0,
    )
    return ResidualEvaluation(
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        rows=rows,
        state=state,
        properties=properties,
        component_telescoping_error_lbmolph=component_error,
        component_telescoping_relative_error=float(
            np.max(np.abs(component_error)) / component_denominator
        ),
        energy_telescoping_error_BTUph=energy_error,
        energy_telescoping_relative_error=float(
            abs(energy_error) / energy_denominator
        ),
    )


def structural_pattern(spec: EnergyOwnedOperatingSpec) -> np.ndarray:
    layout = coordinate_layout(spec)
    index = {name: position for position, name in enumerate(layout.names)}
    rows = residual_rows(spec)
    pattern = np.zeros((len(rows), len(layout.names)), dtype=bool)
    for row_index, row in enumerate(rows):
        for dependency in row.dependencies:
            pattern[row_index, index[dependency]] = True
    return pattern


def _rank_and_condition(matrix: np.ndarray) -> tuple[int, float]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition


def audit_numerical_jacobian(
    spec: EnergyOwnedOperatingSpec,
    reference: EnergyOwnedReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    step: float,
    coupling_tolerance: float = 1.0e-7,
) -> NumericalJacobianAudit:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    baseline = evaluate_residual(
        spec,
        reference,
        provider,
        point,
        fixed_scales=fixed_scales,
    )
    matrix = np.empty((baseline.scaled.size, point.size), dtype=float)
    for column in range(point.size):
        perturbation = np.zeros_like(point)
        perturbation[column] = float(step)
        plus = evaluate_residual(
            spec,
            reference,
            provider,
            point + perturbation,
            fixed_scales=fixed_scales,
        ).scaled
        minus = evaluate_residual(
            spec,
            reference,
            provider,
            point - perturbation,
            fixed_scales=fixed_scales,
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    pattern = structural_pattern(spec)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    layout = coordinate_layout(spec)
    zero_rows = tuple(
        baseline.rows[index].name
        for index in np.flatnonzero(row_norm <= coupling_tolerance)
    )
    zero_columns = tuple(
        layout.names[index]
        for index in np.flatnonzero(column_norm <= coupling_tolerance)
    )
    unexpected = tuple(
        f"{baseline.rows[row].name} <- {layout.names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    rank, condition = _rank_and_condition(matrix)
    return NumericalJacobianAudit(
        step=float(step),
        matrix=matrix,
        rank=rank,
        condition=condition,
        zero_rows=zero_rows,
        zero_columns=zero_columns,
        unexpected_couplings=unexpected,
    )


def audit_points(spec: EnergyOwnedOperatingSpec) -> Mapping[str, np.ndarray]:
    layout = coordinate_layout(spec)
    canonical = np.zeros(len(layout.names), dtype=float)
    combined = canonical.copy()
    combined[layout.liquid_moles] = 0.003 * np.sin(
        np.arange(1, len(VOLUME_IDS) + 1, dtype=float)
    )
    combined[layout.liquid_logits] = 0.002 * np.cos(
        np.arange(1, layout.liquid_logits.stop - layout.liquid_logits.start + 1)
    )
    combined[layout.temperature] = 0.002 * np.sin(
        np.arange(1, len(VOLUME_IDS) + 1, dtype=float)
    )
    combined[layout.vapor_logits] = 0.002 * np.cos(
        np.arange(1, layout.vapor_logits.stop - layout.vapor_logits.start + 1)
    )
    combined[layout.liquid_flows] = np.asarray([0.002, -0.001, 0.0015])
    combined[layout.vapor_flows] = np.asarray(
        [-0.0015, 0.001, 0.0015, -0.001]
    )
    combined[layout.distillate] = -0.001
    combined[layout.bottoms] = 0.001
    return {
        "canonical_role_mapped_seed": canonical,
        "deterministic_combined_perturbation": combined,
    }


__all__ = [
    "CoordinateLayout",
    "EnergyOwnedOperatingSpec",
    "EnergyOwnedReference",
    "EnergyOwnedState",
    "NumericalJacobianAudit",
    "ResidualEvaluation",
    "audit_numerical_jacobian",
    "audit_points",
    "coordinate_layout",
    "decode_coordinates",
    "evaluate_residual",
    "residual_rows",
    "structural_pattern",
]
