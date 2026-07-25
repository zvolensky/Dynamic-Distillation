"""Independent live residual and numerical-audit kernel for Core V3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    VAPOR_LINKS,
    VOLUME_IDS,
    build_provider_governed_registry,
)


FRANCIS_C_US = 3.33
SECONDS_PER_HOUR = 3600.0
R_SI = 8.31446261815324
PSIA_TO_PA = 6894.757293168


@dataclass(frozen=True)
class HydraulicGeometry:
    active_area_ft2: float
    tray_spacing_ft: float
    weir_height_in: float
    weir_length_ft: float
    hydraulic_c_factor: float = 1.0


@dataclass(frozen=True)
class OperatingSpec:
    component_names: tuple[str, ...]
    pressure_psia: np.ndarray
    reflux_lbmolph: float
    feed_component_lbmolph: np.ndarray
    feed_enthalpy_BTUph: float
    reboiler_duty_BTUph: float
    terminal_liquid_targets_lbmol: np.ndarray
    hydraulic_geometry: tuple[HydraulicGeometry, ...]
    temperature_scale_F: float = 100.0


@dataclass(frozen=True)
class NumericalReference:
    liquid_moles_lbmol: np.ndarray
    liquid_mole_fraction: np.ndarray
    temperature_F: np.ndarray
    vapor_mole_fraction: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    bubble_vapor_mole_fraction: np.ndarray
    condenser_duty_reference_BTUph: float
    condenser_duty_scale_BTUph: float


@dataclass(frozen=True)
class CoordinateLayout:
    names: tuple[str, ...]
    liquid_moles: slice
    liquid_alr: slice
    temperature: slice
    vapor_alr: slice
    liquid_flows: slice
    vapor_flows: slice
    distillate: int
    bottoms: int
    bubble_alr: slice
    condenser_duty: int


@dataclass(frozen=True)
class PhysicalState:
    liquid_moles_lbmol: np.ndarray
    liquid_mole_fraction: np.ndarray
    temperature_F: np.ndarray
    vapor_mole_fraction: np.ndarray
    hydraulic_liquid_flow_lbmolph: np.ndarray
    vapor_flow_lbmolph: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    bubble_vapor_mole_fraction: np.ndarray
    condenser_duty_BTUph: float


@dataclass(frozen=True)
class LiveProperties:
    liquid_enthalpy_BTU_lbmol: np.ndarray
    vapor_enthalpy_BTU_lbmol: np.ndarray
    liquid_density_lbmol_ft3: np.ndarray
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
    state: PhysicalState
    properties: LiveProperties
    component_telescoping_error_lbmolph: np.ndarray
    component_telescoping_relative_error: float
    energy_telescoping_error_BTUph: float
    energy_telescoping_relative_error: float
    clipping_or_projection_used: bool = False
    property_fallback_used: bool = False


@dataclass(frozen=True)
class JacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]
    bubble_matrix: np.ndarray
    bubble_rank: int
    bubble_singular_values: np.ndarray
    bubble_zero_rows: tuple[str, ...]
    bubble_zero_columns: tuple[str, ...]


@dataclass(frozen=True)
class BubbleSolveSettings:
    method: str = "trf"
    jacobian_step: float = 1.0e-5
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 100
    temperature_min_F: float = 80.0
    temperature_max_F: float = 260.0
    temperature_scale_F: float = 100.0


@dataclass(frozen=True)
class BubbleSolveResult:
    temperature_F: float
    vapor_mole_fraction: np.ndarray
    scaled_coordinates: np.ndarray
    residual: np.ndarray
    residual_inf_norm: float
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None


@dataclass(frozen=True)
class PengRobinsonParameters:
    critical_temperature_K: np.ndarray
    critical_pressure_Pa: np.ndarray
    acentric_factor: np.ndarray
    binary_interaction: np.ndarray


class IndependentPengRobinsonProvider:
    """Parameter-aligned PR equations used only through validation calls."""

    def __init__(self, parameters: PengRobinsonParameters):
        tc = np.asarray(parameters.critical_temperature_K, dtype=float)
        pc = np.asarray(parameters.critical_pressure_Pa, dtype=float)
        omega = np.asarray(parameters.acentric_factor, dtype=float)
        kij = np.asarray(parameters.binary_interaction, dtype=float)
        size = tc.size
        if (
            tc.shape != (size,)
            or pc.shape != (size,)
            or omega.shape != (size,)
            or kij.shape != (size, size)
            or np.any(tc <= 0.0)
            or np.any(pc <= 0.0)
            or np.any(~np.isfinite(omega))
            or np.any(~np.isfinite(kij))
        ):
            raise ValueError("invalid independent PR parameters")
        self.parameters = PengRobinsonParameters(tc, pc, omega, kij)

    def phase_fugacity_coefficients(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> np.ndarray:
        z = normalize_composition(composition)
        params = self.parameters
        temperature_K = (float(temperature_F) - 32.0) * 5.0 / 9.0 + 273.15
        pressure_Pa = float(pressure_psia) * PSIA_TO_PA
        tc = params.critical_temperature_K
        pc = params.critical_pressure_Pa
        omega = params.acentric_factor
        kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega * omega
        alpha = (1.0 + kappa * (1.0 - np.sqrt(temperature_K / tc))) ** 2
        ai = 0.45724 * R_SI**2 * tc**2 * alpha / pc
        bi = 0.07780 * R_SI * tc / pc
        aij = np.sqrt(np.outer(ai, ai)) * (1.0 - params.binary_interaction)
        amix = float(z @ aij @ z)
        bmix = float(z @ bi)
        A = amix * pressure_Pa / (R_SI**2 * temperature_K**2)
        B = bmix * pressure_Pa / (R_SI * temperature_K)
        roots = np.roots(
            (
                1.0,
                -(1.0 - B),
                A - 3.0 * B**2 - 2.0 * B,
                -(A * B - B**2 - B**3),
            )
        )
        real = np.sort(
            np.asarray(
                [
                    float(root.real)
                    for root in roots
                    if abs(float(root.imag)) <= 1.0e-9 and float(root.real) > B
                ],
                dtype=float,
            )
        )
        if real.size == 0:
            raise RuntimeError("independent PR has no physical compressibility root")
        key = str(phase).strip().lower()
        if key in {"liquid", "liq", "l"}:
            Z = float(real[0])
        elif key in {"vapor", "vapour", "vap", "v"}:
            Z = float(real[-1])
        else:
            raise ValueError("phase must be liquid or vapor")
        sqrt_two = np.sqrt(2.0)
        sum_aij = aij @ z
        log_ratio = np.log(
            (Z + (1.0 + sqrt_two) * B)
            / (Z + (1.0 - sqrt_two) * B)
        )
        ln_phi = (
            bi / bmix * (Z - 1.0)
            - np.log(Z - B)
            - A
            / (2.0 * sqrt_two * B)
            * (2.0 * sum_aij / amix - bi / bmix)
            * log_ratio
        )
        result = np.exp(ln_phi)
        if np.any(~np.isfinite(result)) or np.any(result <= 0.0):
            raise RuntimeError("independent PR returned invalid fugacities")
        return result


def normalize_composition(values: Sequence[float]) -> np.ndarray:
    composition = np.asarray(values, dtype=float).reshape((-1,))
    total = float(np.sum(composition))
    if (
        composition.size < 2
        or np.any(~np.isfinite(composition))
        or np.any(composition <= 0.0)
        or not np.isfinite(total)
        or total <= 0.0
    ):
        raise ValueError("composition must be finite and strictly positive")
    return composition / total


def alr_coordinates(composition: Sequence[float]) -> np.ndarray:
    normalized = normalize_composition(composition)
    return np.log(normalized[:-1] / normalized[-1])


def composition_from_alr(coordinates: Sequence[float]) -> np.ndarray:
    free = np.asarray(coordinates, dtype=float).reshape((-1,))
    shifted = np.concatenate((free, np.zeros(1, dtype=float)))
    shifted -= float(np.max(shifted))
    weights = np.exp(shifted)
    return weights / float(np.sum(weights))


def coordinate_layout(spec: OperatingSpec) -> CoordinateLayout:
    independent = len(spec.component_names) - 1
    if independent < 1:
        raise ValueError("Core V3 requires at least two components")
    names: list[str] = []
    start = len(names)
    names.extend(f"log_NL[{volume}]" for volume in VOLUME_IDS)
    liquid_moles = slice(start, len(names))
    start = len(names)
    for volume in VOLUME_IDS:
        names.extend(
            f"x_alr[{volume},{component}]"
            for component in spec.component_names[:-1]
        )
    liquid_alr = slice(start, len(names))
    start = len(names)
    names.extend(f"T[{volume}]" for volume in VOLUME_IDS)
    temperature = slice(start, len(names))
    start = len(names)
    for volume in EQUILIBRIUM_VOLUME_IDS:
        names.extend(
            f"y_alr[{volume},{component}]"
            for component in spec.component_names[:-1]
        )
    vapor_alr = slice(start, len(names))
    start = len(names)
    names.extend(f"log_L[{volume}]" for volume in HYDRAULIC_VOLUME_IDS)
    liquid_flows = slice(start, len(names))
    start = len(names)
    names.extend(f"log_{symbol}" for _source, _destination, symbol in VAPOR_LINKS)
    vapor_flows = slice(start, len(names))
    distillate = len(names)
    names.append("log_D")
    bottoms = len(names)
    names.append("log_B")
    start = len(names)
    names.extend(
        f"y_bubble_alr[reflux_drum,{component}]"
        for component in spec.component_names[:-1]
    )
    bubble_alr = slice(start, len(names))
    condenser_duty = len(names)
    names.append("q_Q_C")
    expected = 10 * len(spec.component_names) + 10
    if len(names) != expected:
        raise RuntimeError(f"Core V3 coordinate count {len(names)} != {expected}")
    return CoordinateLayout(
        names=tuple(names),
        liquid_moles=liquid_moles,
        liquid_alr=liquid_alr,
        temperature=temperature,
        vapor_alr=vapor_alr,
        liquid_flows=liquid_flows,
        vapor_flows=vapor_flows,
        distillate=distillate,
        bottoms=bottoms,
        bubble_alr=bubble_alr,
        condenser_duty=condenser_duty,
    )


def decode_coordinates(
    spec: OperatingSpec,
    reference: NumericalReference,
    coordinates: Sequence[float],
) -> PhysicalState:
    layout = coordinate_layout(spec)
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(layout.names),):
        raise ValueError(f"expected {len(layout.names)} coordinates")
    independent = len(spec.component_names) - 1
    liquid_x = np.empty(
        (len(VOLUME_IDS), len(spec.component_names)),
        dtype=float,
    )
    liquid_offsets = point[layout.liquid_alr].reshape(
        (len(VOLUME_IDS), independent)
    )
    for index, values in enumerate(reference.liquid_mole_fraction):
        liquid_x[index] = composition_from_alr(
            alr_coordinates(values) + liquid_offsets[index]
        )
    vapor_y = np.empty(
        (len(EQUILIBRIUM_VOLUME_IDS), len(spec.component_names)),
        dtype=float,
    )
    vapor_offsets = point[layout.vapor_alr].reshape(
        (len(EQUILIBRIUM_VOLUME_IDS), independent)
    )
    for index, values in enumerate(reference.vapor_mole_fraction):
        vapor_y[index] = composition_from_alr(
            alr_coordinates(values) + vapor_offsets[index]
        )
    bubble_y = composition_from_alr(
        alr_coordinates(reference.bubble_vapor_mole_fraction)
        + point[layout.bubble_alr]
    )
    return PhysicalState(
        liquid_moles_lbmol=np.asarray(
            reference.liquid_moles_lbmol, dtype=float
        )
        * np.exp(point[layout.liquid_moles]),
        liquid_mole_fraction=liquid_x,
        temperature_F=np.asarray(reference.temperature_F, dtype=float)
        + float(spec.temperature_scale_F) * point[layout.temperature],
        vapor_mole_fraction=vapor_y,
        hydraulic_liquid_flow_lbmolph=np.asarray(
            reference.hydraulic_liquid_flow_lbmolph, dtype=float
        )
        * np.exp(point[layout.liquid_flows]),
        vapor_flow_lbmolph=np.asarray(
            reference.vapor_flow_lbmolph, dtype=float
        )
        * np.exp(point[layout.vapor_flows]),
        distillate_lbmolph=float(reference.distillate_lbmolph)
        * float(np.exp(point[layout.distillate])),
        bottoms_lbmolph=float(reference.bottoms_lbmolph)
        * float(np.exp(point[layout.bottoms])),
        bubble_vapor_mole_fraction=bubble_y,
        condenser_duty_BTUph=float(reference.condenser_duty_reference_BTUph)
        + float(reference.condenser_duty_scale_BTUph)
        * float(point[layout.condenser_duty]),
    )


def encode_state(
    spec: OperatingSpec,
    reference: NumericalReference,
    state: PhysicalState,
) -> np.ndarray:
    layout = coordinate_layout(spec)
    point = np.zeros(len(layout.names), dtype=float)
    point[layout.liquid_moles] = np.log(
        np.asarray(state.liquid_moles_lbmol, dtype=float)
        / np.asarray(reference.liquid_moles_lbmol, dtype=float)
    )
    point[layout.liquid_alr] = np.concatenate(
        [
            alr_coordinates(row) - alr_coordinates(reference.liquid_mole_fraction[i])
            for i, row in enumerate(state.liquid_mole_fraction)
        ]
    )
    point[layout.temperature] = (
        np.asarray(state.temperature_F, dtype=float)
        - np.asarray(reference.temperature_F, dtype=float)
    ) / float(spec.temperature_scale_F)
    point[layout.vapor_alr] = np.concatenate(
        [
            alr_coordinates(row) - alr_coordinates(reference.vapor_mole_fraction[i])
            for i, row in enumerate(state.vapor_mole_fraction)
        ]
    )
    point[layout.liquid_flows] = np.log(
        np.asarray(state.hydraulic_liquid_flow_lbmolph, dtype=float)
        / np.asarray(reference.hydraulic_liquid_flow_lbmolph, dtype=float)
    )
    point[layout.vapor_flows] = np.log(
        np.asarray(state.vapor_flow_lbmolph, dtype=float)
        / np.asarray(reference.vapor_flow_lbmolph, dtype=float)
    )
    point[layout.distillate] = np.log(
        float(state.distillate_lbmolph) / float(reference.distillate_lbmolph)
    )
    point[layout.bottoms] = np.log(
        float(state.bottoms_lbmolph) / float(reference.bottoms_lbmolph)
    )
    point[layout.bubble_alr] = (
        alr_coordinates(state.bubble_vapor_mole_fraction)
        - alr_coordinates(reference.bubble_vapor_mole_fraction)
    )
    point[layout.condenser_duty] = (
        float(state.condenser_duty_BTUph)
        - float(reference.condenser_duty_reference_BTUph)
    ) / float(reference.condenser_duty_scale_BTUph)
    return point


def _coordinate_dependency_name(name: str) -> str | None:
    if name.startswith("NL["):
        return "log_" + name
    if name.startswith("x["):
        return name.replace("x[", "x_alr[", 1)
    if name.startswith("y_bubble["):
        return name.replace("y_bubble[", "y_bubble_alr[", 1)
    if name.startswith("y["):
        return name.replace("y[", "y_alr[", 1)
    if name.startswith("L[") or name.startswith("V["):
        return "log_" + name
    if name in {"D", "B"}:
        return "log_" + name
    if name == "Q_C":
        return "q_Q_C"
    if name.startswith("T["):
        return name
    return None


def residual_rows(spec: OperatingSpec) -> tuple[ResidualRow, ...]:
    registry = build_provider_governed_registry(spec.component_names)
    rows: list[ResidualRow] = []
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
                owner=entry.physical_owner,
                dependencies=tuple(dict.fromkeys(dependencies)),
            )
        )
    return tuple(rows)


def structural_pattern(spec: OperatingSpec) -> np.ndarray:
    layout = coordinate_layout(spec)
    index = {name: position for position, name in enumerate(layout.names)}
    rows = residual_rows(spec)
    pattern = np.zeros((len(rows), len(layout.names)), dtype=bool)
    for row_index, row in enumerate(rows):
        for dependency in row.dependencies:
            pattern[row_index, index[dependency]] = True
    return pattern


def _fugacity_residual(
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: Sequence[float],
    vapor_y: Sequence[float],
    quantity: str,
    caller: str,
    state_id: str,
    evaluation_kind: str,
    independent: bool = False,
) -> np.ndarray:
    x = normalize_composition(liquid_x)
    y = normalize_composition(vapor_y)
    call = (
        call_audit.independent_phase_fugacity
        if independent
        else call_audit.direct_phase_fugacity
    )
    common = {
        "temperature_F": float(temperature_F),
        "pressure_psia": float(pressure_psia),
        "caller": caller,
        "state_id": state_id,
        "evaluation_kind": evaluation_kind,
    }
    if independent:
        phi_l = call(
            provider,
            phase="liquid",
            composition=x,
            **common,
        )
        phi_v = call(
            provider,
            phase="vapor",
            composition=y,
            **common,
        )
    else:
        phi_l = call(
            provider,
            phase="liquid",
            composition=x,
            quantity=quantity,
            **common,
        )
        phi_v = call(
            provider,
            phase="vapor",
            composition=y,
            quantity=quantity,
            **common,
        )
    return np.log(y * phi_v / (x * phi_l))


def _francis_flow(
    *,
    liquid_moles_lbmol: float,
    density_lbmol_ft3: float,
    geometry: HydraulicGeometry,
) -> tuple[float, float, float]:
    liquid_volume = float(liquid_moles_lbmol) / float(density_lbmol_ft3)
    liquid_height = liquid_volume / float(geometry.active_area_ft2)
    over_weir_head = liquid_height - float(geometry.weir_height_in) / 12.0
    if not np.isfinite(over_weir_head) or over_weir_head <= 0.0:
        raise RuntimeError("Core V3 state has no positive over-weir head")
    volumetric_flow_ft3_s = (
        FRANCIS_C_US
        * float(geometry.hydraulic_c_factor)
        * float(geometry.weir_length_ft)
        * over_weir_head**1.5
    )
    flow = volumetric_flow_ft3_s * density_lbmol_ft3 * SECONDS_PER_HOUR
    return float(flow), float(liquid_height), float(over_weir_head)


def _evaluate_properties(
    spec: OperatingSpec,
    state: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    state_id: str,
    evaluation_kind: str,
) -> tuple[LiveProperties, np.ndarray, np.ndarray]:
    volume_count = len(VOLUME_IDS)
    h_liquid = np.empty(volume_count, dtype=float)
    h_vapor = np.full(volume_count, np.nan, dtype=float)
    density = np.full(volume_count, np.nan, dtype=float)
    francis = np.full(volume_count, np.nan, dtype=float)
    height = np.full(volume_count, np.nan, dtype=float)
    head = np.full(volume_count, np.nan, dtype=float)
    stage_equilibrium: list[float] = []
    for index, volume in enumerate(VOLUME_IDS):
        h_liquid[index] = call_audit.phase_enthalpy(
            provider,
            phase="liquid",
            temperature_F=float(state.temperature_F[index]),
            pressure_psia=float(spec.pressure_psia[index]),
            composition=state.liquid_mole_fraction[index],
            caller=f"energy_balance[{volume}]",
            state_id=state_id,
            evaluation_kind=evaluation_kind,
        )
        if volume in EQUILIBRIUM_VOLUME_IDS:
            vapor_index = EQUILIBRIUM_VOLUME_IDS.index(volume)
            stage_equilibrium.extend(
                _fugacity_residual(
                    provider,
                    call_audit,
                    temperature_F=float(state.temperature_F[index]),
                    pressure_psia=float(spec.pressure_psia[index]),
                    liquid_x=state.liquid_mole_fraction[index],
                    vapor_y=state.vapor_mole_fraction[vapor_index],
                    quantity="stage_fugacity_equilibrium",
                    caller=f"full_phase_equilibrium[{volume}]",
                    state_id=state_id,
                    evaluation_kind=evaluation_kind,
                )
            )
            h_vapor[index] = call_audit.phase_enthalpy(
                provider,
                phase="vapor",
                temperature_F=float(state.temperature_F[index]),
                pressure_psia=float(spec.pressure_psia[index]),
                composition=state.vapor_mole_fraction[vapor_index],
                caller=f"energy_balance[{volume}]",
                state_id=state_id,
                evaluation_kind=evaluation_kind,
            )
        if volume in HYDRAULIC_VOLUME_IDS:
            hydraulic_index = HYDRAULIC_VOLUME_IDS.index(volume)
            density[index] = call_audit.liquid_density(
                provider,
                temperature_F=float(state.temperature_F[index]),
                pressure_psia=float(spec.pressure_psia[index]),
                composition=state.liquid_mole_fraction[index],
                caller=f"francis_hydraulics[{volume}]",
                state_id=state_id,
                evaluation_kind=evaluation_kind,
            )
            francis[index], height[index], head[index] = _francis_flow(
                liquid_moles_lbmol=float(state.liquid_moles_lbmol[index]),
                density_lbmol_ft3=float(density[index]),
                geometry=spec.hydraulic_geometry[hydraulic_index],
            )
    bubble = _fugacity_residual(
        provider,
        call_audit,
        temperature_F=float(state.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=state.liquid_mole_fraction[0],
        vapor_y=state.bubble_vapor_mole_fraction,
        quantity="condenser_bubble_equilibrium",
        caller="condenser_bubble_fugacity[reflux_drum]",
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    return (
        LiveProperties(
            liquid_enthalpy_BTU_lbmol=h_liquid,
            vapor_enthalpy_BTU_lbmol=h_vapor,
            liquid_density_lbmol_ft3=density,
            francis_flow_lbmolph=francis,
            liquid_height_ft=height,
            over_weir_head_ft=head,
        ),
        np.asarray(stage_equilibrium, dtype=float),
        np.asarray(bubble, dtype=float),
    )


def _component_balances(
    spec: OperatingSpec,
    state: PhysicalState,
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
    spec: OperatingSpec,
    state: PhysicalState,
    properties: LiveProperties,
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
            + state.condenser_duty_BTUph
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


def evaluate_residual(
    spec: OperatingSpec,
    reference: NumericalReference,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    state_id: str,
    evaluation_kind: str,
) -> ResidualEvaluation:
    if evaluation_kind not in {"residual", "jacobian"}:
        raise ValueError("full residual evaluation kind must be residual or jacobian")
    state = decode_coordinates(spec, reference, coordinates)
    properties, equilibrium, bubble = _evaluate_properties(
        spec,
        state,
        provider,
        call_audit,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
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
            bubble,
        )
    )
    rows = residual_rows(spec)
    scales = np.asarray(fixed_scales, dtype=float).reshape((-1,))
    if raw.shape != (40,) or scales.shape != raw.shape or len(rows) != 40:
        raise RuntimeError("Core V3 live residual is not 40 x 40")
    if np.any(~np.isfinite(scales)) or np.any(scales <= 0.0):
        raise ValueError("Core V3 residual scales are invalid")
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
        + float(spec.reboiler_duty_BTUph)
        + float(state.condenser_duty_BTUph)
        - state.distillate_lbmolph * properties.liquid_enthalpy_BTU_lbmol[0]
        - state.bottoms_lbmolph * properties.liquid_enthalpy_BTU_lbmol[-1]
    )
    energy_error = float(np.sum(energy) - energy_external)
    energy_denominator = max(
        abs(float(spec.feed_enthalpy_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(state.condenser_duty_BTUph)),
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


def audit_numerical_jacobian(
    spec: OperatingSpec,
    reference: NumericalReference,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    state_id: str,
    step: float,
    coupling_tolerance: float,
) -> JacobianAudit:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    baseline = evaluate_residual(
        spec,
        reference,
        provider,
        call_audit,
        point,
        fixed_scales=fixed_scales,
        state_id=state_id,
        evaluation_kind="jacobian",
    )
    matrix = np.empty((40, 40), dtype=float)
    for column in range(40):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = evaluate_residual(
            spec,
            reference,
            provider,
            call_audit,
            point + delta,
            fixed_scales=fixed_scales,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled
        minus = evaluate_residual(
            spec,
            reference,
            provider,
            call_audit,
            point - delta,
            fixed_scales=fixed_scales,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    pattern = structural_pattern(spec)
    rows = baseline.rows
    layout = coordinate_layout(spec)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    unexpected = tuple(
        f"{rows[row].name} <- {layout.names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    rank, condition, singular = _rank_condition_singular(matrix)
    bubble_rows = np.asarray(
        [
            index
            for index, row in enumerate(rows)
            if row.block == "condenser_bubble_fugacity"
        ],
        dtype=int,
    )
    bubble_columns = np.asarray(
        (
            layout.names.index("T[reflux_drum]"),
            *range(layout.bubble_alr.start, layout.bubble_alr.stop),
        ),
        dtype=int,
    )
    bubble_matrix = matrix[np.ix_(bubble_rows, bubble_columns)]
    bubble_rank, _condition, bubble_singular = _rank_condition_singular(
        bubble_matrix
    )
    bubble_row_norm = np.max(np.abs(bubble_matrix), axis=1)
    bubble_column_norm = np.max(np.abs(bubble_matrix), axis=0)
    return JacobianAudit(
        step=float(step),
        matrix=matrix,
        rank=rank,
        condition=condition,
        singular_values=singular,
        zero_rows=tuple(
            rows[index].name
            for index in np.flatnonzero(row_norm <= coupling_tolerance)
        ),
        zero_columns=tuple(
            layout.names[index]
            for index in np.flatnonzero(column_norm <= coupling_tolerance)
        ),
        unexpected_couplings=unexpected,
        bubble_matrix=bubble_matrix,
        bubble_rank=bubble_rank,
        bubble_singular_values=bubble_singular,
        bubble_zero_rows=tuple(
            rows[bubble_rows[index]].name
            for index in np.flatnonzero(
                bubble_row_norm <= coupling_tolerance
            )
        ),
        bubble_zero_columns=tuple(
            layout.names[bubble_columns[index]]
            for index in np.flatnonzero(
                bubble_column_norm <= coupling_tolerance
            )
        ),
    )


def solve_local_bubble(
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    pressure_psia: float,
    liquid_x: Sequence[float],
    temperature_guess_F: float,
    vapor_guess: Sequence[float],
    state_id: str,
    evaluation_kind: str,
    independent: bool = False,
    governing: bool = False,
    settings: BubbleSolveSettings = BubbleSolveSettings(),
) -> BubbleSolveResult:
    if independent and evaluation_kind != "validation":
        raise ValueError("independent bubble solve must be validation-only")
    permitted_direct_kinds = {"preparation", "validation"}
    if governing:
        permitted_direct_kinds.update({"residual", "jacobian"})
    if not independent and evaluation_kind not in permitted_direct_kinds:
        raise ValueError("direct local bubble solve is preparation or validation only")
    if independent and governing:
        raise ValueError("independent bubble solve cannot be governing")
    x = normalize_composition(liquid_x)
    y0 = normalize_composition(vapor_guess)
    reference_alr = alr_coordinates(y0)
    point0 = np.zeros(x.size, dtype=float)
    lower = np.concatenate(
        (
            [
                (settings.temperature_min_F - float(temperature_guess_F))
                / settings.temperature_scale_F
            ],
            np.full(x.size - 1, -25.0),
        )
    )
    upper = np.concatenate(
        (
            [
                (settings.temperature_max_F - float(temperature_guess_F))
                / settings.temperature_scale_F
            ],
            np.full(x.size - 1, 25.0),
        )
    )

    def decode(point: np.ndarray) -> tuple[float, np.ndarray]:
        temperature = float(temperature_guess_F) + (
            settings.temperature_scale_F * float(point[0])
        )
        vapor = composition_from_alr(reference_alr + point[1:])
        return temperature, vapor

    def objective(point: np.ndarray) -> np.ndarray:
        temperature, vapor = decode(point)
        return _fugacity_residual(
            provider,
            call_audit,
            temperature_F=temperature,
            pressure_psia=pressure_psia,
            liquid_x=x,
            vapor_y=vapor,
            quantity="bubble_temperature_and_incipient_vapor",
            caller="local_bubble_seed",
            state_id=state_id,
            evaluation_kind=evaluation_kind,
            independent=independent,
        )

    def jacobian(point: np.ndarray) -> np.ndarray:
        matrix = np.empty((point.size, point.size), dtype=float)
        for column in range(point.size):
            delta = np.zeros_like(point)
            delta[column] = settings.jacobian_step
            matrix[:, column] = (
                objective(point + delta) - objective(point - delta)
            ) / (2.0 * settings.jacobian_step)
        return matrix

    result = least_squares(
        objective,
        point0,
        jac=jacobian,
        bounds=(lower, upper),
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=1.0,
    )
    temperature, vapor = decode(result.x)
    residual = objective(result.x)
    return BubbleSolveResult(
        temperature_F=temperature,
        vapor_mole_fraction=vapor,
        scaled_coordinates=np.asarray(result.x, dtype=float),
        residual=np.asarray(residual, dtype=float),
        residual_inf_norm=float(np.max(np.abs(residual))),
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
        njev=None if result.njev is None else int(result.njev),
    )


def rachford_rice_vapor_fraction(
    K: Sequence[float],
    overall_composition: Sequence[float],
) -> float:
    k = np.asarray(K, dtype=float).reshape((-1,))
    z = normalize_composition(overall_composition)
    if k.shape != z.shape or np.any(~np.isfinite(k)) or np.any(k <= 0.0):
        raise ValueError("invalid flash K values")

    def residual(beta: float) -> float:
        denominator = 1.0 + float(beta) * (k - 1.0)
        if np.any(denominator <= 0.0):
            raise ValueError("invalid Rachford-Rice denominator")
        return float(np.sum(z * (k - 1.0) / denominator))

    at_liquid = residual(0.0)
    at_vapor = residual(1.0)
    if at_liquid <= 0.0:
        return 0.0
    if at_vapor >= 0.0:
        return 1.0
    lower, upper = 0.0, 1.0
    for _ in range(100):
        midpoint = 0.5 * (lower + upper)
        value = residual(midpoint)
        if abs(value) <= 1.0e-14:
            return midpoint
        if value > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return 0.5 * (lower + upper)


def tp_flash_diagnostics(
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    temperature_F: float,
    pressure_psia: float,
    overall_z: Sequence[float],
    state_id: str,
) -> dict[str, Any]:
    z = normalize_composition(overall_z)
    flash_x_raw, flash_y_raw, K = call_audit.tp_flash(
        provider,
        temperature_F=temperature_F,
        pressure_psia=pressure_psia,
        overall_composition=z,
        caller="condenser_phase_diagnostic",
        state_id=state_id,
        evaluation_kind="diagnostic",
    )
    flash_x = normalize_composition(flash_x_raw)
    flash_y = normalize_composition(flash_y_raw)
    beta = rachford_rice_vapor_fraction(K, z)
    reconstructed_y = normalize_composition(K * flash_x)
    reconstructed_z = (1.0 - beta) * flash_x + beta * flash_y
    return {
        "flash_x": flash_x,
        "flash_y": flash_y,
        "flash_K": K,
        "vapor_fraction": float(beta),
        "stable_vapor": bool(beta >= 1.0 - 1.0e-8),
        "flash_Kx_identity_max_abs": float(
            np.max(np.abs(flash_y - reconstructed_y))
        ),
        "lever_rule_closure_max_abs": float(
            np.max(np.abs(z - reconstructed_z))
        ),
    }


__all__ = [
    "BubbleSolveResult",
    "BubbleSolveSettings",
    "CoordinateLayout",
    "HydraulicGeometry",
    "IndependentPengRobinsonProvider",
    "JacobianAudit",
    "LiveProperties",
    "NumericalReference",
    "OperatingSpec",
    "PengRobinsonParameters",
    "PhysicalState",
    "ResidualEvaluation",
    "ResidualRow",
    "alr_coordinates",
    "audit_numerical_jacobian",
    "composition_from_alr",
    "coordinate_layout",
    "decode_coordinates",
    "encode_state",
    "evaluate_residual",
    "normalize_composition",
    "rachford_rice_vapor_fraction",
    "residual_rows",
    "solve_local_bubble",
    "structural_pattern",
    "tp_flash_diagnostics",
]
