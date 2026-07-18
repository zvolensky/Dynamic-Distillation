"""Live five-volume residual and numerical audit for the DD-081 Gate C test."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    FRANCIS_C_US,
    SECONDS_PER_HOUR,
    OneVolumeGeometry,
    _liquid_properties,
    _relative_fugacity_residual,
    normalize_composition,
    reconstruct_liquid_inventory,
    vapor_from_logits,
    vapor_logits,
)
from dynamic_distillation.core_v2.reduced_topology_v1 import (
    ReducedColumnTopology,
    build_five_volume_topology,
)


DIRECT_VOLUME_IDS = (
    "reflux_drum",
    "rectifying_tray",
    "feed_tray",
    "stripping_tray",
    "combined_reboiler_sump",
)
EQUILIBRIUM_VOLUME_IDS = DIRECT_VOLUME_IDS[1:]
HYDRAULIC_VOLUME_IDS = DIRECT_VOLUME_IDS[1:4]


@dataclass(frozen=True)
class FiveVolumeOperatingSpec:
    component_names: tuple[str, ...]
    topology: ReducedColumnTopology
    pressure_psia: np.ndarray
    reflux_lbmolph: float
    rectifying_vapor_lbmolph: float
    stripping_vapor_lbmolph: float
    feed_component_lbmolph: np.ndarray
    feed_enthalpy_BTUph: float
    condenser_duty_BTUph: float
    reboiler_duty_BTUph: float
    terminal_liquid_targets_lbmol: np.ndarray
    hydraulic_geometry: tuple[OneVolumeGeometry, ...]
    temperature_scale_F: float = 100.0


@dataclass(frozen=True)
class FiveVolumeReference:
    component_inventory_lbmol: np.ndarray
    internal_energy_BTU: np.ndarray
    temperature_F: np.ndarray
    vapor_mole_fraction: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float


@dataclass(frozen=True)
class DirectCoordinateLayout:
    names: tuple[str, ...]
    component_inventory: slice
    internal_energy: slice
    temperature: slice
    vapor_logits: slice
    hydraulic_flows: slice
    distillate: int
    bottoms: int


@dataclass(frozen=True)
class FiveVolumeState:
    component_inventory_lbmol: np.ndarray
    internal_energy_BTU: np.ndarray
    temperature_F: np.ndarray
    liquid_moles_lbmol: np.ndarray
    liquid_mole_fraction: np.ndarray
    vapor_mole_fraction: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float


@dataclass(frozen=True)
class FiveVolumeProperties:
    liquid_enthalpy_BTU_lbmol: np.ndarray
    liquid_internal_energy_BTU_lbmol: np.ndarray
    liquid_density_lbmol_ft3: np.ndarray
    vapor_enthalpy_BTU_lbmol: np.ndarray
    liquid_height_ft: np.ndarray
    over_weir_head_ft: np.ndarray
    francis_flow_lbmolph: np.ndarray


@dataclass(frozen=True)
class ResidualRow:
    name: str
    block: str
    owner: str
    units: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class FiveVolumeResidualEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    rows: tuple[ResidualRow, ...]
    state: FiveVolumeState
    properties: FiveVolumeProperties
    component_telescoping_error: np.ndarray
    component_telescoping_relative_error: float
    energy_telescoping_error_BTUph: float
    energy_telescoping_relative_error: float
    clipping_or_projection_used: bool = False
    property_fallback_used: bool = False


@dataclass(frozen=True)
class NumericalJacobianAudit:
    step: float
    matrix: np.ndarray
    colored_matrix: np.ndarray
    rank: int
    condition: float
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]
    color_count: int
    colored_uncolored_max_abs: float
    colored_uncolored_relative: float


def _validate_spec(spec: FiveVolumeOperatingSpec) -> None:
    component_count = len(spec.component_names)
    if spec.topology.volume_ids != DIRECT_VOLUME_IDS:
        raise ValueError("Gate C requires the declared five-volume topology")
    if component_count < 2:
        raise ValueError("Gate C requires at least two components")
    if np.asarray(spec.pressure_psia).shape != (len(DIRECT_VOLUME_IDS),):
        raise ValueError("pressure profile size does not match the topology")
    if np.any(~np.isfinite(spec.pressure_psia)) or np.any(spec.pressure_psia <= 0):
        raise ValueError("pressures must be finite and positive")
    if np.any(np.diff(spec.pressure_psia) <= 0.0):
        raise ValueError("pressure must increase monotonically toward the bottom")
    feed = np.asarray(spec.feed_component_lbmolph, dtype=float)
    if feed.shape != (component_count,) or np.any(feed < 0.0):
        raise ValueError("feed component flow size or sign is invalid")
    if len(spec.hydraulic_geometry) != len(HYDRAULIC_VOLUME_IDS):
        raise ValueError("each hydraulic tray requires one geometry record")
    if np.asarray(spec.terminal_liquid_targets_lbmol).shape != (2,):
        raise ValueError("two terminal liquid targets are required")
    positive_parameters = (
        spec.reflux_lbmolph,
        spec.rectifying_vapor_lbmolph,
        spec.stripping_vapor_lbmolph,
        *np.asarray(spec.terminal_liquid_targets_lbmol, dtype=float),
    )
    if any(not np.isfinite(value) or value <= 0.0 for value in positive_parameters):
        raise ValueError("flow and terminal inventory parameters must be positive")


def direct_coordinate_layout(spec: FiveVolumeOperatingSpec) -> DirectCoordinateLayout:
    _validate_spec(spec)
    names: list[str] = []
    component_count = len(spec.component_names)
    start = 0
    for volume in DIRECT_VOLUME_IDS:
        for component in spec.component_names:
            names.append(f"N[{volume},{component}]")
    inventory = slice(start, len(names))
    start = len(names)
    for volume in DIRECT_VOLUME_IDS:
        names.append(f"U[{volume}]")
    energy = slice(start, len(names))
    start = len(names)
    for volume in DIRECT_VOLUME_IDS:
        names.append(f"T[{volume}]")
    temperature = slice(start, len(names))
    start = len(names)
    for volume in EQUILIBRIUM_VOLUME_IDS:
        for component in spec.component_names[:-1]:
            names.append(f"y_logit[{volume},{component}]")
    vapor = slice(start, len(names))
    start = len(names)
    for volume in HYDRAULIC_VOLUME_IDS:
        names.append(f"log_L[{volume}]")
    liquid_flow = slice(start, len(names))
    distillate = len(names)
    names.append("log_D")
    bottoms = len(names)
    names.append("log_B")
    expected = (
        len(DIRECT_VOLUME_IDS) * component_count
        + len(DIRECT_VOLUME_IDS)
        + len(DIRECT_VOLUME_IDS)
        + len(EQUILIBRIUM_VOLUME_IDS) * (component_count - 1)
        + len(HYDRAULIC_VOLUME_IDS)
        + 2
    )
    if len(names) != expected:
        raise RuntimeError("direct coordinate registry count is inconsistent")
    return DirectCoordinateLayout(
        names=tuple(names),
        component_inventory=inventory,
        internal_energy=energy,
        temperature=temperature,
        vapor_logits=vapor,
        hydraulic_flows=liquid_flow,
        distillate=distillate,
        bottoms=bottoms,
    )


def direct_system_size(component_count: int) -> int:
    """Return the direct-reconstruction Gate C equation count."""
    return (
        len(DIRECT_VOLUME_IDS) * int(component_count)
        + len(DIRECT_VOLUME_IDS)
        + len(DIRECT_VOLUME_IDS)
        + len(EQUILIBRIUM_VOLUME_IDS) * (int(component_count) - 1)
        + len(HYDRAULIC_VOLUME_IDS)
        + 2
    )


def _validate_reference(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
) -> None:
    component_count = len(spec.component_names)
    volume_count = len(DIRECT_VOLUME_IDS)
    shapes = (
        (reference.component_inventory_lbmol, (volume_count, component_count)),
        (reference.internal_energy_BTU, (volume_count,)),
        (reference.temperature_F, (volume_count,)),
        (
            reference.vapor_mole_fraction,
            (len(EQUILIBRIUM_VOLUME_IDS), component_count),
        ),
        (
            reference.hydraulic_liquid_flow_lbmolph,
            (len(HYDRAULIC_VOLUME_IDS),),
        ),
    )
    for value, expected in shapes:
        if np.asarray(value).shape != expected:
            raise ValueError(f"reference shape {np.asarray(value).shape} != {expected}")
    if np.any(np.asarray(reference.component_inventory_lbmol) <= 0.0):
        raise ValueError("reference component inventories must be positive")
    if np.any(np.asarray(reference.hydraulic_liquid_flow_lbmolph) <= 0.0):
        raise ValueError("reference hydraulic flows must be positive")
    if reference.distillate_lbmolph <= 0.0 or reference.bottoms_lbmolph <= 0.0:
        raise ValueError("reference terminal product flows must be positive")
    for row in np.asarray(reference.vapor_mole_fraction):
        normalize_composition(row)


def decode_direct_coordinates(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    coordinates: Sequence[float],
) -> FiveVolumeState:
    _validate_reference(spec, reference)
    layout = direct_coordinate_layout(spec)
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.size != len(layout.names):
        raise ValueError(f"expected {len(layout.names)} coordinates, got {point.size}")
    component_count = len(spec.component_names)
    inventory_ref = np.asarray(reference.component_inventory_lbmol, dtype=float)
    inventory = inventory_ref * np.exp(
        point[layout.component_inventory].reshape(inventory_ref.shape)
    )
    energy_ref = np.asarray(reference.internal_energy_BTU, dtype=float)
    energy_scale = np.maximum(np.abs(energy_ref), 1.0)
    energy = energy_ref + energy_scale * point[layout.internal_energy]
    temperature = np.asarray(reference.temperature_F, dtype=float) + (
        float(spec.temperature_scale_F) * point[layout.temperature]
    )
    liquid_moles = np.empty(len(DIRECT_VOLUME_IDS), dtype=float)
    liquid_x = np.empty((len(DIRECT_VOLUME_IDS), component_count), dtype=float)
    for index in range(len(DIRECT_VOLUME_IDS)):
        liquid_moles[index], liquid_x[index] = reconstruct_liquid_inventory(
            inventory[index]
        )
    vapor = np.empty(
        (len(EQUILIBRIUM_VOLUME_IDS), component_count),
        dtype=float,
    )
    vapor_coordinates = point[layout.vapor_logits].reshape(
        (len(EQUILIBRIUM_VOLUME_IDS), component_count - 1)
    )
    for index, reference_y in enumerate(reference.vapor_mole_fraction):
        vapor[index] = vapor_from_logits(
            vapor_logits(reference_y) + vapor_coordinates[index]
        )
    hydraulic_flow = np.asarray(
        reference.hydraulic_liquid_flow_lbmolph,
        dtype=float,
    ) * np.exp(point[layout.hydraulic_flows])
    return FiveVolumeState(
        component_inventory_lbmol=inventory,
        internal_energy_BTU=energy,
        temperature_F=temperature,
        liquid_moles_lbmol=liquid_moles,
        liquid_mole_fraction=liquid_x,
        vapor_mole_fraction=vapor,
        hydraulic_liquid_flow_lbmolph=hydraulic_flow,
        distillate_lbmolph=float(reference.distillate_lbmolph)
        * float(np.exp(point[layout.distillate])),
        bottoms_lbmolph=float(reference.bottoms_lbmolph)
        * float(np.exp(point[layout.bottoms])),
    )


def encode_direct_state(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    state: FiveVolumeState,
) -> np.ndarray:
    """Encode a physical state in the fixed DD-081 transformed coordinates."""
    _validate_reference(spec, reference)
    layout = direct_coordinate_layout(spec)
    inventory = np.asarray(state.component_inventory_lbmol, dtype=float)
    inventory_ref = np.asarray(reference.component_inventory_lbmol, dtype=float)
    if inventory.shape != inventory_ref.shape or np.any(inventory <= 0.0):
        raise ValueError("encoded component inventories must be positive")
    energy = np.asarray(state.internal_energy_BTU, dtype=float)
    temperature = np.asarray(state.temperature_F, dtype=float)
    vapor = np.asarray(state.vapor_mole_fraction, dtype=float)
    hydraulic_flow = np.asarray(
        state.hydraulic_liquid_flow_lbmolph,
        dtype=float,
    )
    if energy.shape != np.asarray(reference.internal_energy_BTU).shape:
        raise ValueError("encoded internal-energy shape is invalid")
    if temperature.shape != np.asarray(reference.temperature_F).shape:
        raise ValueError("encoded temperature shape is invalid")
    if vapor.shape != np.asarray(reference.vapor_mole_fraction).shape:
        raise ValueError("encoded vapor-composition shape is invalid")
    if (
        hydraulic_flow.shape
        != np.asarray(reference.hydraulic_liquid_flow_lbmolph).shape
        or np.any(hydraulic_flow <= 0.0)
    ):
        raise ValueError("encoded hydraulic flows must be positive")
    if state.distillate_lbmolph <= 0.0 or state.bottoms_lbmolph <= 0.0:
        raise ValueError("encoded product flows must be positive")
    coordinates = np.zeros(len(layout.names), dtype=float)
    coordinates[layout.component_inventory] = np.log(
        inventory / inventory_ref
    ).reshape((-1,))
    energy_ref = np.asarray(reference.internal_energy_BTU, dtype=float)
    coordinates[layout.internal_energy] = (
        energy - energy_ref
    ) / np.maximum(np.abs(energy_ref), 1.0)
    coordinates[layout.temperature] = (
        temperature - np.asarray(reference.temperature_F, dtype=float)
    ) / float(spec.temperature_scale_F)
    vapor_coordinates = np.empty(
        (
            len(EQUILIBRIUM_VOLUME_IDS),
            len(spec.component_names) - 1,
        ),
        dtype=float,
    )
    for index, values in enumerate(vapor):
        vapor_coordinates[index] = (
            vapor_logits(values)
            - vapor_logits(reference.vapor_mole_fraction[index])
        )
    coordinates[layout.vapor_logits] = vapor_coordinates.reshape((-1,))
    coordinates[layout.hydraulic_flows] = np.log(
        hydraulic_flow
        / np.asarray(reference.hydraulic_liquid_flow_lbmolph, dtype=float)
    )
    coordinates[layout.distillate] = np.log(
        float(state.distillate_lbmolph) / float(reference.distillate_lbmolph)
    )
    coordinates[layout.bottoms] = np.log(
        float(state.bottoms_lbmolph) / float(reference.bottoms_lbmolph)
    )
    return coordinates


def _francis_flow(
    *,
    liquid_moles_lbmol: float,
    density_lbmol_ft3: float,
    geometry: OneVolumeGeometry,
) -> tuple[float, float, float]:
    liquid_volume = float(liquid_moles_lbmol) / float(density_lbmol_ft3)
    liquid_height = liquid_volume / float(geometry.active_area_ft2)
    over_weir_head = liquid_height - float(geometry.weir_height_in) / 12.0
    if not np.isfinite(over_weir_head) or over_weir_head <= 0.0:
        raise RuntimeError("Gate C audit state has no positive over-weir head")
    volumetric_flow_ft3_s = (
        FRANCIS_C_US
        * float(geometry.hydraulic_c_factor)
        * float(geometry.weir_length_ft)
        * over_weir_head**1.5
    )
    flow = volumetric_flow_ft3_s * density_lbmol_ft3 * SECONDS_PER_HOUR
    return float(flow), float(liquid_height), float(over_weir_head)


def _coordinate_names_for_volume(
    spec: FiveVolumeOperatingSpec,
    volume: str,
    *,
    phase: str,
) -> tuple[str, ...]:
    if phase == "liquid":
        return tuple(f"N[{volume},{component}]" for component in spec.component_names)
    return tuple(
        f"y_logit[{volume},{component}]"
        for component in spec.component_names[:-1]
    )


def _build_rows(spec: FiveVolumeOperatingSpec) -> tuple[ResidualRow, ...]:
    rows: list[ResidualRow] = []

    def add(
        name: str,
        block: str,
        owner: str,
        units: str,
        dependencies: Sequence[str],
    ) -> None:
        rows.append(
            ResidualRow(
                name=name,
                block=block,
                owner=owner,
                units=units,
                dependencies=tuple(dict.fromkeys(dependencies)),
            )
        )

    for volume in DIRECT_VOLUME_IDS:
        add(
            f"energy_reconstruction[{volume}]",
            "energy_reconstruction",
            volume,
            "BTU",
            (
                *_coordinate_names_for_volume(spec, volume, phase="liquid"),
                f"U[{volume}]",
                f"T[{volume}]",
            ),
        )
    for volume in EQUILIBRIUM_VOLUME_IDS:
        dependencies = (
            *_coordinate_names_for_volume(spec, volume, phase="liquid"),
            f"T[{volume}]",
            *_coordinate_names_for_volume(spec, volume, phase="vapor"),
        )
        for component in spec.component_names[:-1]:
            add(
                f"phase_equilibrium[{volume},{component}]",
                "phase_equilibrium",
                volume,
                "dimensionless",
                dependencies,
            )

    liquid_sources = {
        "reflux_drum": ("reflux_drum",),
        "rectifying_tray": ("reflux_drum", "rectifying_tray"),
        "feed_tray": ("rectifying_tray", "feed_tray"),
        "stripping_tray": ("feed_tray", "stripping_tray"),
        "combined_reboiler_sump": (
            "stripping_tray",
            "combined_reboiler_sump",
        ),
    }
    vapor_sources = {
        "reflux_drum": ("rectifying_tray",),
        "rectifying_tray": ("feed_tray", "rectifying_tray"),
        "feed_tray": ("stripping_tray", "feed_tray"),
        "stripping_tray": (
            "combined_reboiler_sump",
            "stripping_tray",
        ),
        "combined_reboiler_sump": ("combined_reboiler_sump",),
    }
    flow_dependencies = {
        "reflux_drum": ("log_D",),
        "rectifying_tray": ("log_L[rectifying_tray]",),
        "feed_tray": (
            "log_L[rectifying_tray]",
            "log_L[feed_tray]",
        ),
        "stripping_tray": (
            "log_L[feed_tray]",
            "log_L[stripping_tray]",
        ),
        "combined_reboiler_sump": (
            "log_L[stripping_tray]",
            "log_B",
        ),
    }
    for volume in DIRECT_VOLUME_IDS:
        dependencies: list[str] = list(flow_dependencies[volume])
        for source in liquid_sources[volume]:
            dependencies.extend(
                _coordinate_names_for_volume(spec, source, phase="liquid")
            )
        for source in vapor_sources[volume]:
            dependencies.extend(
                _coordinate_names_for_volume(spec, source, phase="vapor")
            )
        for component in spec.component_names:
            add(
                f"component_balance[{volume},{component}]",
                "component_balance",
                volume,
                "lbmol_per_h",
                dependencies,
            )
    for volume in DIRECT_VOLUME_IDS:
        dependencies = list(flow_dependencies[volume])
        for source in liquid_sources[volume]:
            dependencies.extend(
                (
                    *_coordinate_names_for_volume(spec, source, phase="liquid"),
                    f"T[{source}]",
                )
            )
        for source in vapor_sources[volume]:
            dependencies.extend(
                (
                    *_coordinate_names_for_volume(spec, source, phase="vapor"),
                    f"T[{source}]",
                )
            )
        add(
            f"energy_balance[{volume}]",
            "energy_balance",
            volume,
            "BTU_per_h",
            dependencies,
        )
    for volume in HYDRAULIC_VOLUME_IDS:
        add(
            f"francis_hydraulics[{volume}]",
            "francis_hydraulics",
            volume,
            "lbmol_per_h",
            (
                *_coordinate_names_for_volume(spec, volume, phase="liquid"),
                f"T[{volume}]",
                f"log_L[{volume}]",
            ),
        )
    for volume in ("reflux_drum", "combined_reboiler_sump"):
        add(
            f"terminal_level[{volume}]",
            "terminal_level_specification",
            volume,
            "lbmol",
            _coordinate_names_for_volume(spec, volume, phase="liquid"),
        )
    expected = direct_system_size(len(spec.component_names))
    if len(rows) != expected:
        raise RuntimeError(f"direct residual row count {len(rows)} != {expected}")
    return tuple(rows)


def _evaluate_properties(
    spec: FiveVolumeOperatingSpec,
    state: FiveVolumeState,
    provider: Any,
) -> tuple[FiveVolumeProperties, np.ndarray]:
    volume_count = len(DIRECT_VOLUME_IDS)
    h_liquid = np.empty(volume_count, dtype=float)
    u_liquid = np.empty(volume_count, dtype=float)
    density = np.empty(volume_count, dtype=float)
    h_vapor = np.full(volume_count, np.nan, dtype=float)
    equilibrium: list[float] = []
    height = np.full(volume_count, np.nan, dtype=float)
    head = np.full(volume_count, np.nan, dtype=float)
    francis = np.full(volume_count, np.nan, dtype=float)
    for index, volume in enumerate(DIRECT_VOLUME_IDS):
        h_liquid[index], u_liquid[index], density[index] = _liquid_properties(
            provider,
            temperature_F=float(state.temperature_F[index]),
            pressure_psia=float(spec.pressure_psia[index]),
            liquid_mole_fraction=state.liquid_mole_fraction[index],
        )
        if volume in EQUILIBRIUM_VOLUME_IDS:
            vapor_index = EQUILIBRIUM_VOLUME_IDS.index(volume)
            residual, _ = _relative_fugacity_residual(
                provider,
                temperature_F=float(state.temperature_F[index]),
                pressure_psia=float(spec.pressure_psia[index]),
                liquid_mole_fraction=state.liquid_mole_fraction[index],
                vapor_mole_fraction=state.vapor_mole_fraction[vapor_index],
            )
            equilibrium.extend(float(value) for value in residual)
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
    return (
        FiveVolumeProperties(
            liquid_enthalpy_BTU_lbmol=h_liquid,
            liquid_internal_energy_BTU_lbmol=u_liquid,
            liquid_density_lbmol_ft3=density,
            vapor_enthalpy_BTU_lbmol=h_vapor,
            liquid_height_ft=height,
            over_weir_head_ft=head,
            francis_flow_lbmolph=francis,
        ),
        np.asarray(equilibrium, dtype=float),
    )


def _material_balances(
    spec: FiveVolumeOperatingSpec,
    state: FiveVolumeState,
) -> np.ndarray:
    x = state.liquid_mole_fraction
    y_rect, y_feed, y_strip, y_bottom = state.vapor_mole_fraction
    l_rect, l_feed, l_strip = state.hydraulic_liquid_flow_lbmolph
    r = float(spec.reflux_lbmolph)
    vr = float(spec.rectifying_vapor_lbmolph)
    vs = float(spec.stripping_vapor_lbmolph)
    d = float(state.distillate_lbmolph)
    b = float(state.bottoms_lbmolph)
    return np.asarray(
        (
            vr * y_rect - (r + d) * x[0],
            r * x[0] + vr * y_feed - l_rect * x[1] - vr * y_rect,
            l_rect * x[1]
            + vs * y_strip
            + np.asarray(spec.feed_component_lbmolph, dtype=float)
            - l_feed * x[2]
            - vr * y_feed,
            l_feed * x[2] + vs * y_bottom - l_strip * x[3] - vs * y_strip,
            l_strip * x[3] - b * x[4] - vs * y_bottom,
        ),
        dtype=float,
    )


def _energy_balances(
    spec: FiveVolumeOperatingSpec,
    state: FiveVolumeState,
    properties: FiveVolumeProperties,
) -> np.ndarray:
    h_l = properties.liquid_enthalpy_BTU_lbmol
    h_v = properties.vapor_enthalpy_BTU_lbmol
    l_rect, l_feed, l_strip = state.hydraulic_liquid_flow_lbmolph
    r = float(spec.reflux_lbmolph)
    vr = float(spec.rectifying_vapor_lbmolph)
    vs = float(spec.stripping_vapor_lbmolph)
    d = float(state.distillate_lbmolph)
    b = float(state.bottoms_lbmolph)
    return np.asarray(
        (
            vr * h_v[1]
            + float(spec.condenser_duty_BTUph)
            - (r + d) * h_l[0],
            r * h_l[0] + vr * h_v[2] - l_rect * h_l[1] - vr * h_v[1],
            l_rect * h_l[1]
            + vs * h_v[3]
            + float(spec.feed_enthalpy_BTUph)
            - l_feed * h_l[2]
            - vr * h_v[2],
            l_feed * h_l[2]
            + vs * h_v[4]
            - l_strip * h_l[3]
            - vs * h_v[3],
            l_strip * h_l[3]
            + float(spec.reboiler_duty_BTUph)
            - b * h_l[4]
            - vs * h_v[4],
        ),
        dtype=float,
    )


def _residual_scales(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    properties: FiveVolumeProperties,
) -> np.ndarray:
    flow_scale = max(
        float(np.sum(spec.feed_component_lbmolph)),
        float(spec.reflux_lbmolph),
        float(spec.rectifying_vapor_lbmolph),
        float(spec.stripping_vapor_lbmolph),
        float(reference.distillate_lbmolph),
        float(reference.bottoms_lbmolph),
        1.0,
    )
    enthalpy_scale = max(
        float(np.max(np.abs(properties.liquid_enthalpy_BTU_lbmol))),
        float(np.nanmax(np.abs(properties.vapor_enthalpy_BTU_lbmol))),
        1.0,
    )
    energy_flow_scale = max(
        abs(float(spec.feed_enthalpy_BTUph)),
        abs(float(spec.condenser_duty_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        flow_scale * enthalpy_scale,
        1.0,
    )
    local_energy = np.maximum(
        np.abs(np.asarray(reference.internal_energy_BTU, dtype=float)),
        1.0,
    )
    return np.concatenate(
        (
            local_energy,
            np.ones(len(EQUILIBRIUM_VOLUME_IDS) * (len(spec.component_names) - 1)),
            np.full(len(DIRECT_VOLUME_IDS) * len(spec.component_names), flow_scale),
            np.full(len(DIRECT_VOLUME_IDS), energy_flow_scale),
            np.maximum(
                np.asarray(reference.hydraulic_liquid_flow_lbmolph, dtype=float),
                1.0,
            ),
            np.maximum(
                np.asarray(spec.terminal_liquid_targets_lbmol, dtype=float),
                1.0,
            ),
        )
    )


def evaluate_five_volume_residual(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float] | None = None,
) -> FiveVolumeResidualEvaluation:
    state = decode_direct_coordinates(spec, reference, coordinates)
    properties, equilibrium = _evaluate_properties(spec, state, provider)
    local_energy = state.internal_energy_BTU - (
        state.liquid_moles_lbmol * properties.liquid_internal_energy_BTU_lbmol
    )
    component = _material_balances(spec, state)
    energy = _energy_balances(spec, state, properties)
    francis = np.asarray(
        [
            state.hydraulic_liquid_flow_lbmolph[index]
            - properties.francis_flow_lbmolph[
                DIRECT_VOLUME_IDS.index(volume)
            ]
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
    raw = np.concatenate(
        (
            local_energy,
            equilibrium,
            component.reshape((-1,)),
            energy,
            francis,
            terminal,
        )
    )
    rows = _build_rows(spec)
    if raw.size != len(rows):
        raise RuntimeError(f"residual size {raw.size} != registry size {len(rows)}")
    scales = (
        _residual_scales(spec, reference, properties)
        if fixed_scales is None
        else np.asarray(fixed_scales, dtype=float).reshape((-1,))
    )
    if scales.shape != raw.shape or np.any(~np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError("fixed residual scales are invalid")
    component_external = (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )
    component_error = np.sum(component, axis=0) - component_external
    component_denominator = max(
        float(np.max(np.abs(component_external))),
        float(np.max(np.abs(spec.feed_component_lbmolph))),
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
        abs(float(energy_external)),
        1.0,
    )
    return FiveVolumeResidualEvaluation(
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        rows=rows,
        state=state,
        properties=properties,
        component_telescoping_error=component_error,
        component_telescoping_relative_error=float(
            np.max(np.abs(component_error)) / component_denominator
        ),
        energy_telescoping_error_BTUph=energy_error,
        energy_telescoping_relative_error=float(
            abs(energy_error) / energy_denominator
        ),
    )


def structural_pattern(
    spec: FiveVolumeOperatingSpec,
    rows: Sequence[ResidualRow] | None = None,
) -> np.ndarray:
    layout = direct_coordinate_layout(spec)
    residual_rows = _build_rows(spec) if rows is None else tuple(rows)
    index = {name: column for column, name in enumerate(layout.names)}
    pattern = np.zeros((len(residual_rows), len(layout.names)), dtype=bool)
    for row_index, row in enumerate(residual_rows):
        for dependency in row.dependencies:
            pattern[row_index, index[dependency]] = True
    return pattern


def _greedy_column_colors(pattern: np.ndarray) -> tuple[int, ...]:
    column_count = pattern.shape[1]
    conflicts = pattern.T.astype(np.int8) @ pattern.astype(np.int8)
    colors = [-1] * column_count
    for column in range(column_count):
        unavailable = {
            colors[other]
            for other in range(column)
            if conflicts[column, other] and colors[other] >= 0
        }
        color = 0
        while color in unavailable:
            color += 1
        colors[column] = color
    return tuple(colors)


def _rank_and_condition(matrix: np.ndarray) -> tuple[int, float]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    if singular.size == 0:
        return 0, float("inf")
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition


def colored_finite_difference_jacobian(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    step: float,
) -> np.ndarray:
    """Return the registry-colored central-difference scaled Jacobian."""
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    baseline = evaluate_five_volume_residual(
        spec,
        reference,
        provider,
        point,
        fixed_scales=fixed_scales,
    )
    pattern = structural_pattern(spec, baseline.rows)
    colors = _greedy_column_colors(pattern)
    matrix = np.zeros((baseline.scaled.size, point.size), dtype=float)
    for color in range(max(colors) + 1):
        columns = tuple(
            index for index, value in enumerate(colors) if value == color
        )
        perturbation = np.zeros_like(point)
        perturbation[list(columns)] = float(step)
        plus = evaluate_five_volume_residual(
            spec,
            reference,
            provider,
            point + perturbation,
            fixed_scales=fixed_scales,
        ).scaled
        minus = evaluate_five_volume_residual(
            spec,
            reference,
            provider,
            point - perturbation,
            fixed_scales=fixed_scales,
        ).scaled
        difference = (plus - minus) / (2.0 * float(step))
        for column in columns:
            matrix[pattern[:, column], column] = difference[
                pattern[:, column]
            ]
    return matrix


def audit_five_volume_jacobian(
    spec: FiveVolumeOperatingSpec,
    reference: FiveVolumeReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    step: float,
    coupling_tolerance: float = 1.0e-7,
) -> NumericalJacobianAudit:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    baseline = evaluate_five_volume_residual(
        spec,
        reference,
        provider,
        point,
        fixed_scales=fixed_scales,
    )
    pattern = structural_pattern(spec, baseline.rows)
    matrix = np.empty((baseline.scaled.size, point.size), dtype=float)
    for column in range(point.size):
        perturbation = np.zeros_like(point)
        perturbation[column] = float(step)
        plus = evaluate_five_volume_residual(
            spec,
            reference,
            provider,
            point + perturbation,
            fixed_scales=fixed_scales,
        ).scaled
        minus = evaluate_five_volume_residual(
            spec,
            reference,
            provider,
            point - perturbation,
            fixed_scales=fixed_scales,
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))

    colors = _greedy_column_colors(pattern)
    colored = colored_finite_difference_jacobian(
        spec,
        reference,
        provider,
        point,
        fixed_scales=fixed_scales,
        step=step,
    )

    layout = direct_coordinate_layout(spec)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
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
        for row, column in zip(*np.where((~pattern) & (np.abs(matrix) > coupling_tolerance)))
    )
    rank, condition = _rank_and_condition(matrix)
    agreement = float(np.max(np.abs(matrix - colored)))
    relative = agreement / max(float(np.max(np.abs(matrix))), 1.0)
    return NumericalJacobianAudit(
        step=float(step),
        matrix=matrix,
        colored_matrix=colored,
        rank=rank,
        condition=condition,
        zero_rows=zero_rows,
        zero_columns=zero_columns,
        unexpected_couplings=unexpected,
        color_count=max(colors) + 1,
        colored_uncolored_max_abs=agreement,
        colored_uncolored_relative=float(relative),
    )


def reference_coordinates(spec: FiveVolumeOperatingSpec) -> np.ndarray:
    return np.zeros(direct_system_size(len(spec.component_names)), dtype=float)


def perturbation_coordinates(
    spec: FiveVolumeOperatingSpec,
) -> Mapping[str, np.ndarray]:
    layout = direct_coordinate_layout(spec)
    base = reference_coordinates(spec)
    inventory = base.copy()
    inventory[layout.component_inventory] = np.log(1.01)

    energy = base.copy()
    energy[layout.internal_energy] = 0.005

    composition = base.copy()
    component_count = len(spec.component_names)
    feed_offset = DIRECT_VOLUME_IDS.index("feed_tray") * component_count
    composition[layout.component_inventory.start + feed_offset] = np.log(0.995)
    composition[layout.component_inventory.start + feed_offset + 1] = np.log(1.005)

    combined = base.copy()
    combined[layout.component_inventory] = 0.003 * np.sin(
        np.arange(1, layout.component_inventory.stop + 1, dtype=float)
    )
    combined[layout.internal_energy] = 0.002 * np.cos(
        np.arange(1, len(DIRECT_VOLUME_IDS) + 1, dtype=float)
    )
    combined[layout.temperature] = 0.002 * np.sin(
        np.arange(1, len(DIRECT_VOLUME_IDS) + 1, dtype=float)
    )
    combined[layout.vapor_logits] = 0.002 * np.cos(
        np.arange(1, layout.vapor_logits.stop - layout.vapor_logits.start + 1)
    )
    combined[layout.hydraulic_flows] = np.asarray([0.002, -0.001, 0.0015])
    combined[layout.distillate] = -0.001
    combined[layout.bottoms] = 0.001
    return {
        "canonical_mini8_derived": base,
        "bounded_inventory_perturbation": inventory,
        "bounded_energy_perturbation": energy,
        "feed_role_composition_transfer": composition,
        "combined_bounded_perturbation": combined,
    }


def build_operating_spec(
    *,
    component_names: Sequence[str],
    pressure_psia: Sequence[float],
    reflux_lbmolph: float,
    rectifying_vapor_lbmolph: float,
    stripping_vapor_lbmolph: float,
    feed_component_lbmolph: Sequence[float],
    feed_enthalpy_BTUph: float,
    condenser_duty_BTUph: float,
    reboiler_duty_BTUph: float,
    terminal_liquid_targets_lbmol: Sequence[float],
    hydraulic_geometry: Sequence[OneVolumeGeometry],
) -> FiveVolumeOperatingSpec:
    spec = FiveVolumeOperatingSpec(
        component_names=tuple(str(value) for value in component_names),
        topology=build_five_volume_topology(),
        pressure_psia=np.asarray(pressure_psia, dtype=float),
        reflux_lbmolph=float(reflux_lbmolph),
        rectifying_vapor_lbmolph=float(rectifying_vapor_lbmolph),
        stripping_vapor_lbmolph=float(stripping_vapor_lbmolph),
        feed_component_lbmolph=np.asarray(feed_component_lbmolph, dtype=float),
        feed_enthalpy_BTUph=float(feed_enthalpy_BTUph),
        condenser_duty_BTUph=float(condenser_duty_BTUph),
        reboiler_duty_BTUph=float(reboiler_duty_BTUph),
        terminal_liquid_targets_lbmol=np.asarray(
            terminal_liquid_targets_lbmol,
            dtype=float,
        ),
        hydraulic_geometry=tuple(hydraulic_geometry),
    )
    _validate_spec(spec)
    return spec


__all__ = [
    "DIRECT_VOLUME_IDS",
    "EQUILIBRIUM_VOLUME_IDS",
    "HYDRAULIC_VOLUME_IDS",
    "DirectCoordinateLayout",
    "FiveVolumeOperatingSpec",
    "FiveVolumeProperties",
    "FiveVolumeReference",
    "FiveVolumeResidualEvaluation",
    "FiveVolumeState",
    "NumericalJacobianAudit",
    "ResidualRow",
    "audit_five_volume_jacobian",
    "build_operating_spec",
    "colored_finite_difference_jacobian",
    "decode_direct_coordinates",
    "direct_coordinate_layout",
    "direct_system_size",
    "encode_direct_state",
    "evaluate_five_volume_residual",
    "perturbation_coordinates",
    "reference_coordinates",
    "structural_pattern",
]
