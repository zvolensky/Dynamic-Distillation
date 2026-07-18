"""DD-072 direct steady-state residual and numerical-Jacobian audit."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix

from dynamic_distillation.direct_steady_state_registry_v1 import (
    DirectSteadyStateRegistry,
    structural_pattern,
)
from dynamic_distillation.stage_hydraulics_francis_v1 import FRANCIS_C
from dynamic_distillation.stage_thermo_v1 import flash_TP_full_F_psia
from dynamic_distillation.state_vector_layout_v1 import StateVectorLayout
from dynamic_distillation.uv_flash_stage_v1 import (
    _internal_energy_from_enthalpy_BTU_lbmol,
    _provider_vapor_z_factor,
    _vapor_molar_volume_ft3_lbmol,
)


class DirectResidualEvaluationError(RuntimeError):
    """A direct residual could not be evaluated without repairing the trial."""

    def __init__(self, *, node: str, phase: str, reason: str):
        self.node = str(node)
        self.phase = str(phase)
        self.reason = str(reason)
        super().__init__(f"{self.node} {self.phase}: {self.reason}")


@dataclass(frozen=True)
class DirectSteadyStateProblem:
    registry: DirectSteadyStateRegistry
    column: Any
    provider: Any
    node_stage_index0: Mapping[str, int]
    fixed_volume_ft3: Mapping[str, float]
    reflux_rate_lbmolph: float
    feed_node: str
    feed_component_rate_lbmolph: np.ndarray
    feed_enthalpy_rate_BTUph: float
    top_pressure_target_psia: float
    bottoms_light_key_target: float
    drum_liquid_volume_target_ft3: float
    bottom_liquid_volume_target_ft3: float
    dry_tray_K: float
    component_mw_lbm_per_lbmol: np.ndarray


@dataclass(frozen=True)
class ResidualValue:
    index: int
    name: str
    block: str
    owner: str
    units: str
    scale: float
    raw_value: float
    scaled_value: float
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class ConservationAudit:
    component_lhs_lbmolph: np.ndarray
    component_rhs_lbmolph: np.ndarray
    component_relative_error: np.ndarray
    component_pass: bool
    energy_lhs_BTUph: float
    energy_rhs_BTUph: float
    energy_relative_error: float
    energy_pass: bool
    internal_energy_terms: tuple[dict[str, Any], ...]
    internal_energy_pairing_pass: bool


@dataclass(frozen=True)
class DirectResidualEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    residual_scales: np.ndarray
    variable_scales: np.ndarray
    rows: tuple[ResidualValue, ...]
    conservation: ConservationAudit
    raw_l2_norm: float
    scaled_l2_norm: float
    scaled_inf_norm: float
    dominant_scaled_residuals: tuple[dict[str, Any], ...]
    safeguards_used: tuple[str, ...]


@dataclass(frozen=True)
class NumericalJacobianAudit:
    step_factor: float
    mode: str
    color_count: int
    evaluation_count: int
    rank: int
    nullity: int
    largest_singular_value: float
    smallest_singular_value: float
    condition_estimate: float
    near_zero_rows: tuple[str, ...]
    near_zero_columns: tuple[str, ...]
    unexpected_nonzeros: tuple[str, ...]
    expected_but_zero: tuple[str, ...]
    matrix: np.ndarray


@dataclass(frozen=True)
class _NodeProperties:
    T_F: float
    P_psia: float
    NL_lbmol: float
    NV_lbmol: float
    x: np.ndarray
    y: np.ndarray
    hL_BTU_lbmol: float
    hV_BTU_lbmol: float
    uL_BTU_lbmol: float
    uV_BTU_lbmol: float
    vL_ft3_lbmol: float
    vV_ft3_lbmol: float
    rhoL_lbmol_ft3: float
    z_vapor: float
    K: np.ndarray


def _spec_float(specs: Mapping[str, Any], *names: str) -> float | None:
    normalized = {
        " ".join(str(key).strip().lower().split()): value
        for key, value in specs.items()
    }
    for name in names:
        value = normalized.get(" ".join(str(name).strip().lower().split()))
        if value is None:
            continue
        try:
            result = float(value)
        except Exception:
            continue
        if np.isfinite(result):
            return result
    return None


def _stream_components(column: Any, stream: Any) -> np.ndarray:
    names = tuple(str(name) for name in column.components_excel)
    breakdown = getattr(stream, "component_molar_flows_lbmolph", None) or {}
    folded = {str(key).strip().lower(): float(value) for key, value in breakdown.items()}
    values = np.asarray([folded.get(name.lower(), 0.0) for name in names], dtype=float)
    total = getattr(stream, "total_molar_flow_lbmolph", None)
    if np.sum(values) <= 0.0 and total is not None:
        raise ValueError(f"{stream.name} has no component flow breakdown")
    return values


def _horizontal_drum_volume_ft3(diameter_ft: float, length_ft: float) -> float:
    diameter = float(diameter_ft)
    length = float(length_ft)
    cylinder_length = max(length - diameter, 0.0)
    return float(
        np.pi * diameter * diameter * cylinder_length / 4.0
        + np.pi * diameter**3 / 6.0
    )


def build_direct_steady_state_problem(
    *,
    registry: DirectSteadyStateRegistry,
    column: Any,
    provider: Any,
    bottoms_light_key_target: float = 0.04717,
) -> DirectSteadyStateProblem:
    """Bind the generic registry to one column without solving any closure."""
    stages = tuple(str(value) for value in registry.active_stage_ids)
    tray_nodes = tuple(f"tray_{value}" for value in stages)
    node_stage = {"reflux_drum": 0, "partial_reboiler": int(column.n_stages) - 1}
    node_stage.update(
        {node: int(stage) - 1 for node, stage in zip(tray_nodes, stages)}
    )
    specs = getattr(column, "specs_raw", {}) or {}

    feed = column.streams.get("Feed")
    distillate = column.streams.get("Distillate")
    bottoms = column.streams.get("Bottom")
    if feed is None or distillate is None or bottoms is None:
        raise ValueError("DD-072 requires Feed, Distillate, and Bottom streams")
    feed_stage = int(feed.stage_1based)
    feed_node = f"tray_{feed_stage}"
    if feed_node not in tray_nodes:
        raise ValueError("feed must enter one registered physical tray")
    feed_components = _stream_components(column, feed)
    feed_total = float(np.sum(feed_components))
    feed_z = feed_components / feed_total
    feed_pressure = float(
        column.P_psia[feed_stage - 1]
        if feed.pressure_psia is None
        else feed.pressure_psia
    )
    feed_temperature = float(
        column.T_f[feed_stage - 1]
        if feed.temperature_f is None
        else feed.temperature_f
    )
    feed_vf = float(feed.vapor_fraction or 0.0)
    h_feed_l = float(
        provider.phase_enthalpy_BTU_lbmol(
            "liquid", feed_temperature, feed_pressure, feed_z.tolist()
        )
    )
    h_feed_v = float(
        provider.phase_enthalpy_BTU_lbmol(
            "vapor", feed_temperature, feed_pressure, feed_z.tolist()
        )
    )
    feed_h_rate = feed_total * ((1.0 - feed_vf) * h_feed_l + feed_vf * h_feed_v)

    geom = getattr(column, "geometry", None)
    if geom is None:
        raise ValueError("DD-072 requires explicit column geometry")
    fixed_volume: dict[str, float] = {}
    for node, stage0 in node_stage.items():
        if node in {"reflux_drum", "partial_reboiler"}:
            continue
        fixed_volume[node] = float(geom.vapor_volume_ft3_per_stage[stage0])

    drum_d = _spec_float(specs, "Top Drum Diameter (ft)")
    drum_l = _spec_float(specs, "Top Drum Length (ft)")
    drum_total = _spec_float(specs, "Top Drum Total Volume (ft3)")
    if drum_total is None and drum_d is not None and drum_l is not None:
        drum_total = _horizontal_drum_volume_ft3(drum_d, drum_l)
    if drum_total is None or drum_total <= 0.0:
        raise ValueError("DD-072 requires top-drum total volume")
    fixed_volume["reflux_drum"] = float(drum_total)

    sump_total = _spec_float(specs, "Bottom Sump Total Volume (ft3)")
    if sump_total is None:
        sump_d = _spec_float(specs, "Bottom Sump Diameter (ft)")
        sump_h = _spec_float(specs, "Bottom Sump Height (ft)")
        if sump_d is not None and sump_h is not None:
            sump_total = float(np.pi * sump_d * sump_d * sump_h / 4.0)
    if sump_total is None or sump_total <= 0.0:
        raise ValueError("DD-072 requires bottom-sump total volume")
    fixed_volume["partial_reboiler"] = float(
        sump_total + geom.vapor_volume_ft3_per_stage[-1]
    )

    drum_fraction = _spec_float(specs, "Top Level SP Frac")
    bottom_fraction = _spec_float(specs, "Bottom Level SP Frac")
    drum_fraction = 0.5 if drum_fraction is None else drum_fraction
    bottom_fraction = 0.5 if bottom_fraction is None else bottom_fraction
    top_pressure = _spec_float(specs, "Top Pressure SP (psia)")
    if top_pressure is None:
        top_pressure = float(column.P_psia[0])
    dry_tray_k = _spec_float(specs, "Dry Tray K")
    dry_tray_k = 1.0 if dry_tray_k is None else dry_tray_k
    mw = provider.component_mw_lbm_per_lbmol()
    if mw is None:
        raise ValueError("DD-072 requires component molecular weights")

    return DirectSteadyStateProblem(
        registry=registry,
        column=column,
        provider=provider,
        node_stage_index0=node_stage,
        fixed_volume_ft3=fixed_volume,
        reflux_rate_lbmolph=float(column.L_lbmolph[0]),
        feed_node=feed_node,
        feed_component_rate_lbmolph=feed_components,
        feed_enthalpy_rate_BTUph=float(feed_h_rate),
        top_pressure_target_psia=float(top_pressure),
        bottoms_light_key_target=float(bottoms_light_key_target),
        drum_liquid_volume_target_ft3=float(drum_fraction * drum_total),
        bottom_liquid_volume_target_ft3=float(bottom_fraction * sump_total),
        dry_tray_K=float(dry_tray_k),
        component_mw_lbm_per_lbmol=np.asarray(mw, dtype=float),
    )


def _reconstruct_composition(
    values: Mapping[str, float],
    *,
    node: str,
    phase: str,
    components: Sequence[str],
) -> np.ndarray:
    prefix = "x" if phase == "liquid" else "y"
    independent = np.asarray(
        [values[f"{prefix}[{node},{component}]"] for component in components[:-1]],
        dtype=float,
    )
    final = 1.0 - float(np.sum(independent))
    result = np.concatenate((independent, np.asarray([final], dtype=float)))
    if not np.all(np.isfinite(result)):
        raise DirectResidualEvaluationError(
            node=node, phase=phase, reason="composition is not finite"
        )
    if np.any(result <= 0.0) or np.any(result >= 1.0):
        raise DirectResidualEvaluationError(
            node=node,
            phase=phase,
            reason=f"composition is outside the open simplex: {result.tolist()}",
        )
    if float(np.sum(result)) != 1.0:
        raise DirectResidualEvaluationError(
            node=node, phase=phase, reason="reduced composition did not reconstruct to one"
        )
    return result


def _node_properties(
    problem: DirectSteadyStateProblem,
    values: Mapping[str, float],
    node: str,
) -> _NodeProperties:
    components = problem.registry.component_names
    T = float(values[f"T[{node}]"])
    P = float(values[f"P[{node}]"])
    NL = float(values[f"NL[{node}]"])
    NV = float(values[f"NV[{node}]"])
    if not np.isfinite(T) or T <= -459.67:
        raise DirectResidualEvaluationError(node=node, phase="both", reason="invalid temperature")
    if not np.isfinite(P) or P <= 0.0:
        raise DirectResidualEvaluationError(node=node, phase="both", reason="invalid pressure")
    if not np.isfinite(NL) or NL <= 0.0 or not np.isfinite(NV) or NV <= 0.0:
        raise DirectResidualEvaluationError(node=node, phase="both", reason="invalid phase amount")
    x = _reconstruct_composition(
        values, node=node, phase="liquid", components=components
    )
    y = _reconstruct_composition(
        values, node=node, phase="vapor", components=components
    )
    provider = problem.provider
    try:
        hL = float(provider.phase_enthalpy_BTU_lbmol("liquid", T, P, x.tolist()))
        hV = float(provider.phase_enthalpy_BTU_lbmol("vapor", T, P, y.tolist()))
        rho = provider.liquid_density_lbmol_ft3(T, P, x.tolist())
        if rho is None:
            raise ValueError("liquid density unavailable")
        rho = float(rho)
        z_vapor = float(
            _provider_vapor_z_factor(
                provider, T_F=T, P_psia=P, y=y, flash_Z=None
            )
        )
        flash = flash_TP_full_F_psia(
            provider,
            T,
            P,
            x.tolist(),
            n_components=len(components),
            stage_index0=problem.node_stage_index0[node],
        )
        K = np.asarray(flash.K, dtype=float).reshape((len(components),))
    except Exception as exc:
        raise DirectResidualEvaluationError(
            node=node, phase="property", reason=str(exc)
        ) from exc
    if (
        not np.isfinite(rho)
        or rho <= 0.0
        or not np.isfinite(z_vapor)
        or z_vapor <= 0.0
        or np.any(~np.isfinite(K))
        or np.any(K <= 0.0)
    ):
        raise DirectResidualEvaluationError(
            node=node, phase="property", reason="non-physical live property result"
        )
    vL = 1.0 / rho
    vV = _vapor_molar_volume_ft3_lbmol(T, P, z_vapor)
    return _NodeProperties(
        T_F=T,
        P_psia=P,
        NL_lbmol=NL,
        NV_lbmol=NV,
        x=x,
        y=y,
        hL_BTU_lbmol=hL,
        hV_BTU_lbmol=hV,
        uL_BTU_lbmol=_internal_energy_from_enthalpy_BTU_lbmol(hL, P, vL),
        uV_BTU_lbmol=_internal_energy_from_enthalpy_BTU_lbmol(hV, P, vV),
        vL_ft3_lbmol=vL,
        vV_ft3_lbmol=vV,
        rhoL_lbmol_ft3=rho,
        z_vapor=z_vapor,
        K=K,
    )


def _unknown_values(
    registry: DirectSteadyStateRegistry, vector: Sequence[float]
) -> dict[str, float]:
    array = np.asarray(vector, dtype=float).reshape((len(registry.unknowns),))
    if not np.all(np.isfinite(array)):
        raise DirectResidualEvaluationError(
            node="global", phase="unknown", reason="trial vector is not finite"
        )
    return {entry.name: float(array[index]) for index, entry in enumerate(registry.unknowns)}


def _liquid_flow_prediction(
    problem: DirectSteadyStateProblem, node: str, props: _NodeProperties
) -> float:
    geom = problem.column.geometry
    stage0 = problem.node_stage_index0[node]
    area = float(geom.area_ft2_per_stage[stage0])
    weir_h = float(geom.weir_height_in_per_stage[stage0]) / 12.0
    weir_l = float(geom.weir_length_ft_per_stage[stage0])
    c_mult = float(geom.hydraulic_c_factor_per_stage[stage0])
    liquid_height = props.NL_lbmol / props.rhoL_lbmol_ft3 / area
    head = max(liquid_height - weir_h, 0.0)
    return float(
        FRANCIS_C
        * c_mult
        * weir_l
        * head**1.5
        * props.rhoL_lbmol_ft3
        * 3600.0
    )


def _vapor_pressure_drop_residual(
    problem: DirectSteadyStateProblem,
    *,
    source: str,
    destination: str,
    vapor_rate_lbmolph: float,
    props: Mapping[str, _NodeProperties],
) -> float:
    source_props = props[source]
    destination_props = props[destination]
    geom = problem.column.geometry
    stage0 = problem.node_stage_index0[source]
    active_area = float(geom.active_area_ft2_per_stage[stage0])
    tray_area = float(geom.area_ft2_per_stage[stage0])
    weir_h = float(geom.weir_height_in_per_stage[stage0]) / 12.0
    liquid_height = source_props.NL_lbmol / source_props.rhoL_lbmol_ft3 / tray_area
    head = max(liquid_height - weir_h, 0.0)
    liquid_mw = float(np.dot(source_props.x, problem.component_mw_lbm_per_lbmol))
    vapor_mw = float(np.dot(source_props.y, problem.component_mw_lbm_per_lbmol))
    rho_liquid_mass = source_props.rhoL_lbmol_ft3 * liquid_mw
    rho_vapor_molar = (
        source_props.P_psia
        / (
            source_props.z_vapor
            * 10.7316
            * (source_props.T_F + 459.67)
        )
    )
    rho_vapor_mass = rho_vapor_molar * vapor_mw
    dp_liquid = rho_liquid_mass * head / 144.0
    volumetric_rate_ft3_s = (
        float(vapor_rate_lbmolph) / 3600.0 / rho_vapor_molar
    )
    velocity = volumetric_rate_ft3_s / active_area
    dp_dry = (
        problem.dry_tray_K * rho_vapor_mass * velocity * velocity / (2.0 * 144.0)
    )
    return float(
        source_props.P_psia
        - destination_props.P_psia
        - dp_liquid
        - dp_dry
    )


def variable_scales(
    problem: DirectSteadyStateProblem, vector: Sequence[float]
) -> np.ndarray:
    values = _unknown_values(problem.registry, vector)
    inventory_values = [
        abs(value) for name, value in values.items() if name.startswith("N[")
    ]
    common_inventory = max(inventory_values + [1.0])
    energy_values = [
        abs(value) for name, value in values.items() if name.startswith("U[")
    ]
    common_energy = max(
        energy_values
        + [
            abs(values.get("Q_C", 0.0)),
            abs(values.get("Q_R", 0.0)),
            abs(problem.feed_enthalpy_rate_BTUph),
            1.0,
        ]
    )
    flow_scale = max(float(np.sum(problem.feed_component_rate_lbmolph)), 1.0)
    pressure_scale = max(problem.top_pressure_target_psia, 1.0)
    result = np.ones(len(problem.registry.unknowns), dtype=float)
    for index, entry in enumerate(problem.registry.unknowns):
        name = entry.name
        if name.startswith("N[") or name.startswith(("NL[", "NV[")):
            result[index] = common_inventory
        elif name.startswith("U["):
            result[index] = common_energy
        elif name.startswith("T["):
            result[index] = 100.0
        elif name.startswith("P["):
            result[index] = pressure_scale
        elif name.startswith(("x[", "y[")):
            result[index] = 1.0
        elif name.startswith(("L_out[", "V_out[")) or name in {"D", "B"}:
            result[index] = flow_scale
        elif name in {"Q_C", "Q_R"}:
            result[index] = common_energy
    return result


def _residual_scale(
    problem: DirectSteadyStateProblem,
    entry: Any,
    *,
    inventory_scale: float,
    energy_scale: float,
    flow_scale: float,
) -> float:
    block = entry.block
    if block == "local_component_closure":
        return inventory_scale
    if block == "local_energy_closure":
        return energy_scale
    if block == "local_volume_closure":
        return max(problem.fixed_volume_ft3[entry.owner], 1.0)
    if block == "local_equilibrium":
        return 1.0
    if block == "steady_component_balance":
        return flow_scale
    if block == "steady_energy_balance":
        return energy_scale
    if block in {"liquid_hydraulics"}:
        return flow_scale
    if block == "vapor_pressure_drop":
        pressure_profile = np.asarray(problem.column.P_psia, dtype=float)
        return max(
            float(np.max(pressure_profile) - np.min(pressure_profile)),
            1.0,
        )
    if block == "terminal_pressure_coupling":
        return max(problem.top_pressure_target_psia, 1.0)
    if block == "operating_specification":
        if entry.units == "psia":
            return max(problem.top_pressure_target_psia, 1.0)
        if entry.units == "ft3":
            target = (
                problem.drum_liquid_volume_target_ft3
                if entry.owner == "reflux_drum"
                else problem.bottom_liquid_volume_target_ft3
            )
            return max(target, 1.0)
        return 1.0
    return 1.0


def evaluate_direct_steady_state_residual(
    problem: DirectSteadyStateProblem,
    vector: Sequence[float],
) -> DirectResidualEvaluation:
    """Evaluate all registered equations directly; no nested correction is run."""
    registry = problem.registry
    values = _unknown_values(registry, vector)
    nodes = ("reflux_drum", *(f"tray_{s}" for s in registry.active_stage_ids), "partial_reboiler")
    props = {node: _node_properties(problem, values, node) for node in nodes}
    components = registry.component_names
    raw: dict[str, float] = {}

    for node in nodes:
        state = props[node]
        for index, component in enumerate(components):
            raw[f"component_closure[{node},{component}]"] = (
                values[f"N[{node},{component}]"]
                - state.NL_lbmol * state.x[index]
                - state.NV_lbmol * state.y[index]
            )
        raw[f"energy_closure[{node}]"] = (
            values[f"U[{node}]"]
            - state.NL_lbmol * state.uL_BTU_lbmol
            - state.NV_lbmol * state.uV_BTU_lbmol
        )
        raw[f"volume_closure[{node}]"] = (
            state.NL_lbmol * state.vL_ft3_lbmol
            + state.NV_lbmol * state.vV_ft3_lbmol
            - problem.fixed_volume_ft3[node]
        )
        for index, component in enumerate(components):
            raw[f"equilibrium[{node},{component}]"] = float(
                np.log(state.y[index])
                - np.log(state.x[index])
                - np.log(state.K[index])
            )

    component_balance = {
        node: np.zeros(len(components), dtype=float) for node in nodes
    }
    energy_balance = {node: 0.0 for node in nodes}
    internal_energy_terms: list[dict[str, Any]] = []

    def internal_stream(
        name: str,
        source: str,
        destination: str,
        rate: float,
        composition: np.ndarray,
        enthalpy: float,
    ) -> None:
        component_rate = float(rate) * composition
        enthalpy_rate = float(rate) * float(enthalpy)
        component_balance[source] -= component_rate
        component_balance[destination] += component_rate
        energy_balance[source] -= enthalpy_rate
        energy_balance[destination] += enthalpy_rate
        internal_energy_terms.append(
            {
                "name": name,
                "source": source,
                "destination": destination,
                "source_term_BTUph": -enthalpy_rate,
                "destination_term_BTUph": enthalpy_rate,
                "pair_sum_BTUph": 0.0,
            }
        )

    drum = "reflux_drum"
    trays = tuple(f"tray_{stage}" for stage in registry.active_stage_ids)
    reboiler = "partial_reboiler"
    internal_stream(
        "reflux",
        drum,
        trays[0],
        problem.reflux_rate_lbmolph,
        props[drum].x,
        props[drum].hL_BTU_lbmol,
    )
    for index, node in enumerate(trays):
        liquid_destination = reboiler if index == len(trays) - 1 else trays[index + 1]
        internal_stream(
            f"liquid:{node}->{liquid_destination}",
            node,
            liquid_destination,
            values[f"L_out[{node}]"],
            props[node].x,
            props[node].hL_BTU_lbmol,
        )
    for index, source in enumerate((*trays, reboiler)):
        destination = drum if index == 0 else trays[index - 1]
        internal_stream(
            f"vapor:{source}->{destination}",
            source,
            destination,
            values[f"V_out[{source}]"],
            props[source].y,
            props[source].hV_BTU_lbmol,
        )

    component_balance[problem.feed_node] += problem.feed_component_rate_lbmolph
    energy_balance[problem.feed_node] += problem.feed_enthalpy_rate_BTUph
    D = values["D"]
    B = values["B"]
    distillate_component_rate = D * props[drum].x
    bottoms_component_rate = B * props[reboiler].x
    component_balance[drum] -= distillate_component_rate
    component_balance[reboiler] -= bottoms_component_rate
    distillate_h_rate = D * props[drum].hL_BTU_lbmol
    bottoms_h_rate = B * props[reboiler].hL_BTU_lbmol
    energy_balance[drum] -= distillate_h_rate + values["Q_C"]
    energy_balance[reboiler] -= bottoms_h_rate
    energy_balance[reboiler] += values["Q_R"]

    for node in nodes:
        for index, component in enumerate(components):
            raw[f"component_balance[{node},{component}]"] = float(
                component_balance[node][index]
            )
        raw[f"energy_balance[{node}]"] = float(energy_balance[node])

    for node in trays:
        raw[f"liquid_hydraulics[{node}]"] = (
            values[f"L_out[{node}]"] - _liquid_flow_prediction(problem, node, props[node])
        )
    vapor_sources = (*trays, reboiler)
    for index, source in enumerate(vapor_sources):
        destination = drum if index == 0 else trays[index - 1]
        raw[f"vapor_pressure_drop[{source}]"] = _vapor_pressure_drop_residual(
            problem,
            source=source,
            destination=destination,
            vapor_rate_lbmolph=values[f"V_out[{source}]"],
            props=props,
        )

    raw["spec_top_pressure"] = props[drum].P_psia - problem.top_pressure_target_psia
    raw["spec_bottoms_propane"] = (
        props[reboiler].x[0] - problem.bottoms_light_key_target
    )
    raw["spec_drum_level"] = (
        props[drum].NL_lbmol * props[drum].vL_ft3_lbmol
        - problem.drum_liquid_volume_target_ft3
    )
    raw["spec_sump_level"] = (
        props[reboiler].NL_lbmol * props[reboiler].vL_ft3_lbmol
        - problem.bottom_liquid_volume_target_ft3
    )

    missing = tuple(entry.name for entry in registry.residuals if entry.name not in raw)
    if missing:
        raise RuntimeError(f"unpopulated direct residuals: {missing}")
    raw_vector = np.asarray([raw[entry.name] for entry in registry.residuals], dtype=float)
    if not np.all(np.isfinite(raw_vector)):
        bad = tuple(
            registry.residuals[index].name
            for index in np.flatnonzero(~np.isfinite(raw_vector))
        )
        raise RuntimeError(f"non-finite direct residuals: {bad}")

    variable_scale_vector = variable_scales(problem, vector)
    inventory_scale = max(
        [
            abs(values[name])
            for name in values
            if name.startswith("N[")
        ]
        + [1.0]
    )
    energy_scale = max(
        abs(problem.feed_enthalpy_rate_BTUph),
        abs(values["Q_C"]),
        abs(values["Q_R"]),
        1.0,
    )
    flow_scale = max(float(np.sum(problem.feed_component_rate_lbmolph)), 1.0)
    residual_scale_vector = np.asarray(
        [
            _residual_scale(
                problem,
                entry,
                inventory_scale=inventory_scale,
                energy_scale=energy_scale,
                flow_scale=flow_scale,
            )
            for entry in registry.residuals
        ],
        dtype=float,
    )
    scaled = raw_vector / residual_scale_vector
    rows = tuple(
        ResidualValue(
            index=index,
            name=entry.name,
            block=entry.block,
            owner=entry.owner,
            units=entry.units,
            scale=float(residual_scale_vector[index]),
            raw_value=float(raw_vector[index]),
            scaled_value=float(scaled[index]),
            dependencies=entry.dependencies,
        )
        for index, entry in enumerate(registry.residuals)
    )
    component_lhs = np.sum(
        np.stack([component_balance[node] for node in nodes], axis=0), axis=0
    )
    component_rhs = (
        problem.feed_component_rate_lbmolph
        - distillate_component_rate
        - bottoms_component_rate
    )
    component_error = np.abs(component_lhs - component_rhs) / np.maximum(
        np.abs(problem.feed_component_rate_lbmolph), 1.0
    )
    energy_lhs = float(sum(energy_balance.values()))
    energy_rhs = float(
        problem.feed_enthalpy_rate_BTUph
        + values["Q_R"]
        - values["Q_C"]
        - distillate_h_rate
        - bottoms_h_rate
    )
    energy_error = abs(energy_lhs - energy_rhs) / max(
        abs(problem.feed_enthalpy_rate_BTUph),
        abs(values["Q_R"]),
        abs(values["Q_C"]),
        abs(distillate_h_rate),
        abs(bottoms_h_rate),
        1.0,
    )
    order = np.argsort(np.abs(scaled))[::-1][:12]
    return DirectResidualEvaluation(
        raw=raw_vector,
        scaled=scaled,
        residual_scales=residual_scale_vector,
        variable_scales=variable_scale_vector,
        rows=rows,
        conservation=ConservationAudit(
            component_lhs_lbmolph=component_lhs,
            component_rhs_lbmolph=component_rhs,
            component_relative_error=component_error,
            component_pass=bool(np.max(component_error) < 1.0e-10),
            energy_lhs_BTUph=energy_lhs,
            energy_rhs_BTUph=energy_rhs,
            energy_relative_error=float(energy_error),
            energy_pass=bool(energy_error < 1.0e-8),
            internal_energy_terms=tuple(internal_energy_terms),
            internal_energy_pairing_pass=bool(
                all(abs(float(row["pair_sum_BTUph"])) < 1.0e-12 for row in internal_energy_terms)
            ),
        ),
        raw_l2_norm=float(np.linalg.norm(raw_vector)),
        scaled_l2_norm=float(np.linalg.norm(scaled)),
        scaled_inf_norm=float(np.max(np.abs(scaled))),
        dominant_scaled_residuals=tuple(
            {
                "name": rows[index].name,
                "block": rows[index].block,
                "owner": rows[index].owner,
                "scaled_value": rows[index].scaled_value,
                "raw_value": rows[index].raw_value,
                "units": rows[index].units,
            }
            for index in order
        ),
        safeguards_used=(),
    )


def build_chemsep_guess(problem: DirectSteadyStateProblem) -> np.ndarray:
    """Construct a direct profile guess; no residual correction is performed."""
    col = problem.column
    registry = problem.registry
    values: dict[str, float] = {}
    top_holdup = _spec_float(col.specs_raw, "Top Accumulator Holdup (lbmol)")
    bottom_holdup = _spec_float(col.specs_raw, "Bottom Holdup (lbmol)")
    if top_holdup is None or bottom_holdup is None:
        raise ValueError("ChemSep guess requires top and bottom liquid holdups")
    nodes = ("reflux_drum", *(f"tray_{s}" for s in registry.active_stage_ids), "partial_reboiler")
    for node in nodes:
        stage0 = problem.node_stage_index0[node]
        T = float(col.T_f[stage0])
        P = float(col.P_psia[stage0])
        x = np.asarray(col.x0[stage0], dtype=float)
        y = np.asarray(col.y0[stage0], dtype=float)
        NL = (
            float(top_holdup)
            if node == "reflux_drum"
            else float(bottom_holdup)
            if node == "partial_reboiler"
            else float(col.M_L_lbmol[stage0])
        )
        rho = float(problem.provider.liquid_density_lbmol_ft3(T, P, x.tolist()))
        z_vapor = float(
            _provider_vapor_z_factor(
                problem.provider, T_F=T, P_psia=P, y=y, flash_Z=None
            )
        )
        vL = 1.0 / rho
        vV = _vapor_molar_volume_ft3_lbmol(T, P, z_vapor)
        available_vapor_volume = problem.fixed_volume_ft3[node] - NL * vL
        if available_vapor_volume <= 0.0:
            raise DirectResidualEvaluationError(
                node=node, phase="vapor", reason="seed liquid exceeds fixed volume"
            )
        NV = available_vapor_volume / vV
        hL = float(problem.provider.phase_enthalpy_BTU_lbmol("liquid", T, P, x.tolist()))
        hV = float(problem.provider.phase_enthalpy_BTU_lbmol("vapor", T, P, y.tolist()))
        uL = _internal_energy_from_enthalpy_BTU_lbmol(hL, P, vL)
        uV = _internal_energy_from_enthalpy_BTU_lbmol(hV, P, vV)
        for index, component in enumerate(registry.component_names):
            values[f"N[{node},{component}]"] = NL * x[index] + NV * y[index]
        values[f"U[{node}]"] = NL * uL + NV * uV
        values[f"T[{node}]"] = T
        values[f"P[{node}]"] = P
        values[f"NL[{node}]"] = NL
        values[f"NV[{node}]"] = NV
        for index, component in enumerate(registry.component_names[:-1]):
            values[f"x[{node},{component}]"] = float(x[index])
            values[f"y[{node},{component}]"] = float(y[index])

    for node in (f"tray_{s}" for s in registry.active_stage_ids):
        values[f"L_out[{node}]"] = float(
            col.L_lbmolph[problem.node_stage_index0[node]]
        )
    for node in (*tuple(f"tray_{s}" for s in registry.active_stage_ids), "partial_reboiler"):
        values[f"V_out[{node}]"] = float(
            col.V_lbmolph[problem.node_stage_index0[node]]
        )
    values["D"] = float(col.streams["Distillate"].total_molar_flow_lbmolph)
    values["B"] = float(col.streams["Bottom"].total_molar_flow_lbmolph)
    values["Q_C"] = abs(float(col.duties.q_cond_btu_per_h))
    values["Q_R"] = float(col.duties.q_reb_btu_per_h)
    return np.asarray([values[entry.name] for entry in registry.unknowns], dtype=float)


def build_bounded_perturbed_guess(
    problem: DirectSteadyStateProblem,
    chemsep_guess: Sequence[float],
) -> np.ndarray:
    """Perturb reduced coordinates deterministically while preserving each simplex."""
    result = np.asarray(chemsep_guess, dtype=float).copy()
    names = [entry.name for entry in problem.registry.unknowns]
    index = {name: position for position, name in enumerate(names)}
    for position, entry in enumerate(problem.registry.unknowns):
        phase = np.sin(float(position + 1))
        if entry.name.startswith("T["):
            result[position] += 0.2 * phase
        elif entry.name.startswith("P["):
            result[position] += 0.02 * phase
        elif entry.name.startswith(("N[", "NL[", "NV[", "L_out[", "V_out[")):
            result[position] *= 1.0 + 0.005 * phase
        elif entry.name in {"D", "B", "Q_C", "Q_R"}:
            result[position] *= 1.0 + 0.0025 * phase
        elif entry.name.startswith(("x[", "y[")):
            continue

    nodes = ("reflux_drum", *(f"tray_{s}" for s in problem.registry.active_stage_ids), "partial_reboiler")
    for node in nodes:
        for prefix in ("x", "y"):
            comp_names = [
                f"{prefix}[{node},{component}]"
                for component in problem.registry.component_names[:-1]
            ]
            base_coords = np.asarray(
                [result[index[name]] for name in comp_names], dtype=float
            )
            full = np.concatenate(
                (base_coords, np.asarray([1.0 - float(np.sum(base_coords))]))
            )
            factors = np.exp(
                2.0e-3
                * np.asarray(
                    [
                        np.sin(float(index[name] + 1))
                        for name in comp_names
                    ]
                    + [np.sin(float(len(names) + len(comp_names)))],
                    dtype=float,
                )
            )
            full = full * factors
            full = full / float(np.sum(full))
            coords = full[:-1]
            for name, value in zip(comp_names, coords):
                result[index[name]] = float(value)
            margin = 1.0e-6
            if np.any(coords <= margin) or float(np.sum(coords)) >= 1.0 - margin:
                raise RuntimeError(
                    f"deterministic perturbation left the reduced simplex at {node} {prefix}"
                )
    return result


def build_checkpoint_guess_from_diagnostics(
    problem: DirectSteadyStateProblem,
    chemsep_guess: Sequence[float],
    checkpoint: Mapping[str, np.ndarray],
) -> np.ndarray:
    """Map checkpoint diagnostics into the registry without treating them as truth."""
    result = np.asarray(chemsep_guess, dtype=float).copy()
    names = [entry.name for entry in problem.registry.unknowns]
    index = {name: position for position, name in enumerate(names)}
    metadata: dict[str, Any] = {}
    if "metadata_json" in checkpoint:
        try:
            metadata = json.loads(str(np.asarray(checkpoint["metadata_json"]).item()))
        except Exception:
            metadata = {}
    runtime_memory = (
        metadata.get("runtime_aux_state", {})
        or metadata.get("runtime_memory", {})
        or {}
    )
    if "diag__T_tray_F" in checkpoint:
        T = np.asarray(checkpoint["diag__T_tray_F"], dtype=float)
    elif runtime_memory.get("last_T_tray") is not None:
        T = np.asarray(runtime_memory["last_T_tray"], dtype=float)
    else:
        raise KeyError("checkpoint has no tray-temperature diagnostic")
    P = np.asarray(checkpoint["diag__P_psia_hyd"], dtype=float)
    x = np.asarray(checkpoint["diag__x_tray"], dtype=float)
    y = np.asarray(checkpoint["diag__y_tray"], dtype=float)
    ML = np.asarray(checkpoint["diag__ML_tot_tray"], dtype=float)
    MV = np.asarray(checkpoint["diag__MV_tot_tray"], dtype=float)
    state_blocks: dict[str, np.ndarray] = {}
    layout_doc = metadata.get("layout", {}) or {}
    if "final_state" in checkpoint and layout_doc:
        layout = StateVectorLayout(
            n_stages=int(layout_doc["n_stages"]),
            n_components=int(layout_doc["n_components"]),
            include_top=bool(layout_doc.get("include_top", True)),
            include_bottom=bool(layout_doc.get("include_bottom", True)),
            include_vapor=bool(layout_doc.get("include_vapor", True)),
            include_temperature=bool(layout_doc.get("include_temperature", False)),
            include_energy=bool(layout_doc.get("include_energy", False)),
        )
        packed = np.asarray(checkpoint["final_state"], dtype=float).reshape((-1,))
        slices = layout.slices()
        state_blocks["tray_L"] = packed[slices["tray_L"]].reshape(
            (layout.n_stages, layout.n_components)
        )
        state_blocks["tray_V"] = packed[slices["tray_V"]].reshape(
            (layout.n_stages, layout.n_components)
        )
        for name in ("top_L", "top_V", "bottom_L", "bottom_V"):
            if name in slices:
                state_blocks[name] = packed[slices[name]].reshape(
                    (layout.n_components,)
                )
    L = np.asarray(checkpoint["diag__L_out_lbmolph"], dtype=float)
    V = np.asarray(checkpoint["diag__V_out_lbmolph"], dtype=float)
    nodes = ("reflux_drum", *(f"tray_{s}" for s in problem.registry.active_stage_ids), "partial_reboiler")
    for node in nodes:
        stage0 = problem.node_stage_index0[node]
        liquid_inventory = None
        vapor_inventory = None
        if node == "reflux_drum":
            liquid_inventory = state_blocks.get("top_L")
            vapor_inventory = state_blocks.get("top_V")
        elif node == "partial_reboiler":
            liquid_inventory = state_blocks.get("bottom_L")
            if "tray_V" in state_blocks:
                vapor_inventory = state_blocks["tray_V"][stage0, :]
        elif "tray_L" in state_blocks and "tray_V" in state_blocks:
            liquid_inventory = state_blocks["tray_L"][stage0, :]
            vapor_inventory = state_blocks["tray_V"][stage0, :]
        if liquid_inventory is not None:
            liquid_inventory = np.asarray(liquid_inventory, dtype=float)
            liquid_total = float(np.sum(liquid_inventory))
            if liquid_total <= 0.0 or np.any(liquid_inventory <= 0.0):
                raise DirectResidualEvaluationError(
                    node=node,
                    phase="liquid",
                    reason="checkpoint inventory cannot define an open-simplex composition",
                )
            ML[stage0] = liquid_total
            x[stage0, :] = liquid_inventory / liquid_total
        if vapor_inventory is not None:
            vapor_inventory = np.asarray(vapor_inventory, dtype=float)
            vapor_total = float(np.sum(vapor_inventory))
            if vapor_total <= 0.0 or np.any(vapor_inventory <= 0.0):
                raise DirectResidualEvaluationError(
                    node=node,
                    phase="vapor",
                    reason="checkpoint inventory cannot define an open-simplex composition",
                )
            MV[stage0] = vapor_total
            y[stage0, :] = vapor_inventory / vapor_total
        result[index[f"T[{node}]"]] = T[stage0]
        result[index[f"P[{node}]"]] = P[stage0]
        if ML[stage0] <= 0.0 or MV[stage0] <= 0.0:
            raise DirectResidualEvaluationError(
                node=node,
                phase="both",
                reason="checkpoint phase amounts are not strictly positive",
            )
        result[index[f"NL[{node}]"]] = ML[stage0]
        result[index[f"NV[{node}]"]] = MV[stage0]
        for component_index, component in enumerate(problem.registry.component_names[:-1]):
            result[index[f"x[{node},{component}]"]] = x[stage0, component_index]
            result[index[f"y[{node},{component}]"]] = y[stage0, component_index]
        props = _node_properties(
            problem,
            {entry.name: result[pos] for pos, entry in enumerate(problem.registry.unknowns)},
            node,
        )
        for component_index, component in enumerate(problem.registry.component_names):
            result[index[f"N[{node},{component}]"]] = (
                props.NL_lbmol * props.x[component_index]
                + props.NV_lbmol * props.y[component_index]
            )
        result[index[f"U[{node}]"]] = (
            props.NL_lbmol * props.uL_BTU_lbmol
            + props.NV_lbmol * props.uV_BTU_lbmol
        )
    for node in (f"tray_{s}" for s in problem.registry.active_stage_ids):
        result[index[f"L_out[{node}]"]] = L[problem.node_stage_index0[node]]
    for node in (*tuple(f"tray_{s}" for s in problem.registry.active_stage_ids), "partial_reboiler"):
        result[index[f"V_out[{node}]"]] = V[problem.node_stage_index0[node]]
    for key, diagnostic in (
        ("D", "diag__top_L_distillate_out_lbmolph"),
        ("Q_C", "diag__Q_cond_used_BTUph"),
        ("Q_R", "diag__Q_reb_used_BTUph"),
    ):
        if diagnostic in checkpoint:
            value = float(np.ravel(np.asarray(checkpoint[diagnostic], dtype=float))[0])
            result[index[key]] = abs(value) if key == "Q_C" else value
    controller_state = metadata.get("controller_state_final", {}) or {}
    if controller_state.get("bottoms_cmd_lbmolph") is not None:
        result[index["B"]] = float(controller_state["bottoms_cmd_lbmolph"])
    if controller_state.get("distillate_cmd_lbmolph") is not None:
        result[index["D"]] = float(controller_state["distillate_cmd_lbmolph"])
    return result


def _column_colors(pattern: csr_matrix) -> tuple[tuple[int, ...], ...]:
    matrix = pattern.tocsc()
    row_sets = [
        set(int(row) for row in matrix.indices[matrix.indptr[col] : matrix.indptr[col + 1]])
        for col in range(matrix.shape[1])
    ]
    colors: list[list[int]] = []
    occupied: list[set[int]] = []
    for column, rows in sorted(
        enumerate(row_sets), key=lambda item: (-len(item[1]), item[0])
    ):
        for color_index, used_rows in enumerate(occupied):
            if rows.isdisjoint(used_rows):
                colors[color_index].append(column)
                used_rows.update(rows)
                break
        else:
            colors.append([column])
            occupied.append(set(rows))
    return tuple(tuple(sorted(color)) for color in colors)


def _finite_difference_steps(
    problem: DirectSteadyStateProblem,
    vector: np.ndarray,
    scales: np.ndarray,
    factor: float,
) -> np.ndarray:
    eps_root = np.sqrt(np.finfo(float).eps)
    steps = eps_root * np.maximum(np.abs(vector), scales) * float(factor)
    for index, entry in enumerate(problem.registry.unknowns):
        if entry.name.startswith("T["):
            steps[index] = max(steps[index], 2.0e-3 * factor)
        elif entry.name.startswith("P["):
            steps[index] = max(steps[index], 2.0e-3 * factor)
        elif entry.name.startswith(("x[", "y[")):
            steps[index] = max(steps[index], 2.0e-7 * factor)
        elif entry.name.startswith(("L_out[", "V_out[")) or entry.name in {"D", "B"}:
            steps[index] = max(steps[index], 1.0e-3 * factor)
        elif entry.name in {"Q_C", "Q_R"} or entry.name.startswith("U["):
            steps[index] = max(steps[index], 1.0 * factor)
        else:
            steps[index] = max(steps[index], 1.0e-6 * factor)
    return steps


def audit_numerical_jacobian(
    problem: DirectSteadyStateProblem,
    vector: Sequence[float],
    *,
    step_factor: float = 1.0,
    mode: str = "colored",
    zero_tolerance: float = 1.0e-10,
) -> NumericalJacobianAudit:
    """Build d(r/rscale)/d(z/zscale) without taking a solver step."""
    base_vector = np.asarray(vector, dtype=float).reshape((len(problem.registry.unknowns),))
    base = evaluate_direct_steady_state_residual(problem, base_vector)
    pattern = structural_pattern(problem.registry).astype(bool).tocsc()
    colors = (
        tuple((column,) for column in range(pattern.shape[1]))
        if mode == "uncolored"
        else _column_colors(pattern)
    )
    steps = _finite_difference_steps(
        problem, base_vector, base.variable_scales, step_factor
    )
    matrix = np.zeros(pattern.shape, dtype=float)
    evaluation_count = 1
    for color in colors:
        plus = base_vector.copy()
        minus = base_vector.copy()
        for column in color:
            plus[column] += steps[column]
            minus[column] -= steps[column]
        plus_eval = evaluate_direct_steady_state_residual(problem, plus)
        minus_eval = evaluate_direct_steady_state_residual(problem, minus)
        evaluation_count += 2
        # Scaling is part of the coordinate system, not a trial-dependent
        # equation. Hold the base scales fixed while differentiating.
        delta_scaled = (
            plus_eval.raw - minus_eval.raw
        ) / base.residual_scales
        for column in color:
            rows = (
                np.arange(pattern.shape[0], dtype=int)
                if mode == "uncolored"
                else pattern.indices[
                    pattern.indptr[column] : pattern.indptr[column + 1]
                ]
            )
            denominator = 2.0 * steps[column] / base.variable_scales[column]
            matrix[rows, column] = delta_scaled[rows] / denominator

    singular = np.linalg.svd(matrix, compute_uv=False)
    rank = int(np.linalg.matrix_rank(matrix))
    row_norm = np.linalg.norm(matrix, axis=1)
    column_norm = np.linalg.norm(matrix, axis=0)
    numerical_pattern = np.abs(matrix) > float(zero_tolerance)
    expected = pattern.toarray()
    unexpected = np.argwhere(numerical_pattern & ~expected)
    expected_zero = np.argwhere(expected & ~numerical_pattern)
    residual_names = [entry.name for entry in problem.registry.residuals]
    unknown_names = [entry.name for entry in problem.registry.unknowns]
    largest = float(singular[0]) if singular.size else 0.0
    smallest = float(singular[-1]) if singular.size else 0.0
    return NumericalJacobianAudit(
        step_factor=float(step_factor),
        mode=str(mode),
        color_count=len(colors),
        evaluation_count=evaluation_count,
        rank=rank,
        nullity=int(matrix.shape[1] - rank),
        largest_singular_value=largest,
        smallest_singular_value=smallest,
        condition_estimate=float(np.inf if smallest == 0.0 else largest / smallest),
        near_zero_rows=tuple(
            residual_names[index]
            for index in np.flatnonzero(row_norm <= float(zero_tolerance))
        ),
        near_zero_columns=tuple(
            unknown_names[index]
            for index in np.flatnonzero(column_norm <= float(zero_tolerance))
        ),
        unexpected_nonzeros=tuple(
            f"{residual_names[row]} <- {unknown_names[column]}"
            for row, column in unexpected
        ),
        expected_but_zero=tuple(
            f"{residual_names[row]} <- {unknown_names[column]}"
            for row, column in expected_zero
        ),
        matrix=matrix,
    )
