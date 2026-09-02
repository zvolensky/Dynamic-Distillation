"""Side-effect-free tray hydraulic operating-envelope diagnostics for Core V3."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np

from .pressure_layer_numerical_v1 import (
    GAS_CONSTANT_PSIA_FT3_LBMOL_R,
    PSF_PER_PSIA,
)


CORRELATION_VERSION = "core-v3-souders-brown-declared-capacity-factor-v1"
BACKUP_METHOD = "clear-liquid-height-plus-dry-tray-pressure-head-v1"
CLASSIFICATION_ORDER = {
    "not_evaluated": -1,
    "normal": 0,
    "advisory": 1,
    "high_loading": 2,
    "predicted_flooding": 3,
}


@dataclass(frozen=True)
class TrayHydraulicOperatingEnvelopeSpec:
    """Declared correlation inputs and alert semantics.

    ``capacity_factor_ft_s`` is deliberately optional.  Omitting it produces
    ``not_evaluated`` rather than silently assuming a safe tray capacity.
    """

    capacity_factor_ft_s: float | None = None
    system_factor: float = 1.0
    correlation_name: str = "Souders-Brown with declared tray capacity factor"
    correlation_version: str = CORRELATION_VERSION
    surface_tension_treatment: str = "included in declared capacity factor"
    advisory_fraction: float = 0.70
    high_loading_fraction: float = 0.85
    predicted_flooding_fraction: float = 1.0
    hard_stop_fraction: float | None = None


@dataclass(frozen=True)
class TrayHydraulicStageEvaluation:
    stage: int
    volume: str
    source_link_index: int
    vapor_flow_lbmolph: float
    liquid_flow_lbmolph: float
    vapor_superficial_velocity_ft_s: float
    vapor_f_factor: float
    liquid_to_vapor_mass_flow_parameter: float
    liquid_mass_density_lbm_ft3: float
    vapor_mass_density_lbm_ft3: float
    critical_effective_capacity_factor_ft_s: float
    predicted_flooding_velocity_ft_s: float
    flooding_fraction: float
    clear_liquid_height_ft: float
    over_weir_head_ft: float
    dry_tray_pressure_drop_psia: float
    liquid_head_pressure_drop_psia: float
    total_tray_pressure_drop_psia: float
    backup_head_ft: float
    backup_fraction_of_tray_spacing: float
    capacity_classification: str
    backup_classification: str
    overall_classification: str
    weeping_classification: str
    evaluable: bool
    limitation: str | None


@dataclass(frozen=True)
class TrayHydraulicOperatingEnvelopeEvaluation:
    correlation_name: str
    correlation_version: str
    capacity_factor_ft_s: float | None
    system_factor: float
    surface_tension_treatment: str
    backup_method: str
    advisory_fraction: float
    high_loading_fraction: float
    predicted_flooding_fraction: float
    hard_stop_fraction: float | None
    stages: tuple[TrayHydraulicStageEvaluation, ...]
    fully_evaluable: bool
    overall_classification: str
    maximum_flooding_fraction: float
    flooding_limiting_stage: int | None
    maximum_critical_effective_capacity_factor_ft_s: float
    critical_effective_capacity_factor_limiting_stage: int | None
    maximum_backup_fraction: float
    backup_limiting_stage: int | None
    maximum_hydraulic_load_fraction: float
    limiting_stage: int | None
    predicted_flooding: bool
    hard_stop_reached: bool
    limitations: tuple[str, ...]


def _validated_spec(
    spec: TrayHydraulicOperatingEnvelopeSpec,
) -> TrayHydraulicOperatingEnvelopeSpec:
    if not str(spec.correlation_name).strip() or not str(spec.correlation_version).strip():
        raise ValueError("hydraulic correlation name and version are required")
    capacity = spec.capacity_factor_ft_s
    if capacity is not None and (not np.isfinite(capacity) or capacity <= 0.0):
        raise ValueError("tray flooding capacity factor must be positive when declared")
    if not np.isfinite(spec.system_factor) or spec.system_factor <= 0.0:
        raise ValueError("tray hydraulic system factor must be positive")
    thresholds = (
        float(spec.advisory_fraction),
        float(spec.high_loading_fraction),
        float(spec.predicted_flooding_fraction),
    )
    if (
        any(not np.isfinite(value) or value <= 0.0 for value in thresholds)
        or not thresholds[0] < thresholds[1] < thresholds[2]
    ):
        raise ValueError("hydraulic alert fractions must be positive and ordered")
    if spec.hard_stop_fraction is not None and (
        not np.isfinite(spec.hard_stop_fraction) or spec.hard_stop_fraction <= 0.0
    ):
        raise ValueError("hydraulic hard-stop fraction must be positive when declared")
    return spec


def validate_tray_hydraulic_operating_envelope_spec(
    spec: TrayHydraulicOperatingEnvelopeSpec,
) -> TrayHydraulicOperatingEnvelopeSpec:
    """Validate declared correlation inputs before a trajectory starts."""

    return _validated_spec(spec)


def _classification(
    fraction: float,
    spec: TrayHydraulicOperatingEnvelopeSpec,
) -> str:
    if not np.isfinite(fraction):
        return "not_evaluated"
    if fraction >= float(spec.predicted_flooding_fraction):
        return "predicted_flooding"
    if fraction >= float(spec.high_loading_fraction):
        return "high_loading"
    if fraction >= float(spec.advisory_fraction):
        return "advisory"
    return "normal"


def _worst_classification(values: Sequence[str]) -> str:
    if not values:
        return "not_evaluated"
    return max(values, key=lambda value: CLASSIFICATION_ORDER[value])


def _finite_maximum(
    values: Sequence[float],
    stages: Sequence[int],
) -> tuple[float, int | None]:
    array = np.asarray(values, dtype=float)
    finite = np.flatnonzero(np.isfinite(array))
    if finite.size == 0:
        return float("nan"), None
    local = finite[int(np.argmax(array[finite]))]
    return float(array[local]), int(stages[local])


def evaluate_tray_hydraulic_operating_envelope(
    *,
    topology: Any,
    endpoint: Any,
    properties: Any,
    pressure_drop: Any,
    hydraulic_geometry: Sequence[Any],
    pressure_link_geometry: Sequence[Any],
    component_mw_lbm_per_lbmol: Sequence[float],
    spec: TrayHydraulicOperatingEnvelopeSpec,
) -> TrayHydraulicOperatingEnvelopeEvaluation:
    """Evaluate every normal physical tray without changing model equations."""

    spec = _validated_spec(spec)
    volume_ids = tuple(topology.volume_ids)
    volume_index = {volume: index for index, volume in enumerate(volume_ids)}
    hydraulic_ids = tuple(topology.hydraulic_volume_ids)
    hydraulic_index = {volume: index for index, volume in enumerate(hydraulic_ids)}
    links = tuple(topology.vapor_links)
    if len(pressure_link_geometry) != len(links):
        raise ValueError("pressure-link geometry does not match the column topology")
    if len(hydraulic_geometry) != len(hydraulic_ids):
        raise ValueError("liquid hydraulic geometry does not match the column topology")

    molecular_weight = np.asarray(component_mw_lbm_per_lbmol, dtype=float)
    liquid_inventory = np.asarray(endpoint.liquid_component_inventory_lbmol, dtype=float)
    vapor_inventory = np.asarray(endpoint.vapor_component_inventory_lbmol, dtype=float)
    pressure = np.asarray(endpoint.pressure_psia, dtype=float)
    temperature = np.asarray(endpoint.temperature_F, dtype=float)
    vapor_flow = np.asarray(endpoint.vapor_flow_lbmolph, dtype=float)
    liquid_flow = np.asarray(endpoint.hydraulic_liquid_flow_lbmolph, dtype=float)
    liquid_density = np.asarray(properties.liquid_density_lbmol_ft3, dtype=float)
    vapor_z = np.asarray(properties.vapor_compressibility_factor, dtype=float)
    liquid_drop = np.asarray(pressure_drop.liquid_head_drop_psia, dtype=float)
    dry_drop = np.asarray(pressure_drop.dry_tray_drop_psia, dtype=float)
    over_weir = np.asarray(pressure_drop.over_weir_head_ft, dtype=float)
    component_count = molecular_weight.size
    volume_count = len(volume_ids)
    if (
        molecular_weight.shape != (component_count,)
        or liquid_inventory.shape != (volume_count, component_count)
        or vapor_inventory.shape != (volume_count, component_count)
        or pressure.shape != (volume_count,)
        or temperature.shape != (volume_count,)
        or vapor_flow.shape != (len(links),)
        or liquid_flow.shape != (len(hydraulic_ids),)
        or liquid_density.shape != (volume_count,)
        or vapor_z.shape != (volume_count,)
        or liquid_drop.shape != (len(links),)
        or dry_drop.shape != (len(links),)
        or over_weir.shape != (len(links),)
    ):
        raise ValueError("hydraulic-envelope input arrays have inconsistent shapes")
    numeric_arrays = (
        molecular_weight,
        liquid_inventory,
        vapor_inventory,
        pressure,
        temperature,
        vapor_flow,
        liquid_flow,
        liquid_density,
        vapor_z,
        liquid_drop,
        dry_drop,
        over_weir,
    )
    if any(np.any(~np.isfinite(values)) for values in numeric_arrays):
        raise ValueError("hydraulic-envelope inputs must be finite")
    if (
        np.any(molecular_weight <= 0.0)
        or np.any(liquid_inventory <= 0.0)
        or np.any(vapor_inventory <= 0.0)
        or np.any(pressure <= 0.0)
        or np.any(temperature <= -459.67)
        or np.any(vapor_flow <= 0.0)
        or np.any(liquid_flow <= 0.0)
        or np.any(liquid_density <= 0.0)
        or np.any(vapor_z <= 0.0)
    ):
        raise ValueError("hydraulic-envelope state must be physical")

    stage_results: list[TrayHydraulicStageEvaluation] = []
    for link_index, (source, _destination, _symbol) in enumerate(links):
        link_geometry = pressure_link_geometry[link_index]
        if not bool(link_geometry.include_liquid_head):
            continue
        if source not in hydraulic_index:
            raise ValueError(f"physical tray {source!r} has no liquid hydraulic geometry")
        source_index = volume_index[source]
        liquid_geometry = hydraulic_geometry[hydraulic_index[source]]
        liquid_x = liquid_inventory[source_index] / np.sum(liquid_inventory[source_index])
        vapor_y = vapor_inventory[source_index] / np.sum(vapor_inventory[source_index])
        liquid_mw = float(np.dot(liquid_x, molecular_weight))
        vapor_mw = float(np.dot(vapor_y, molecular_weight))
        rho_l_mass = float(liquid_density[source_index]) * liquid_mw
        temperature_R = float(temperature[source_index]) + 459.67
        rho_v_molar = float(pressure[source_index]) / (
            float(vapor_z[source_index])
            * GAS_CONSTANT_PSIA_FT3_LBMOL_R
            * temperature_R
        )
        rho_v_mass = rho_v_molar * vapor_mw
        volumetric_vapor_ft3_s = (
            float(vapor_flow[link_index]) / 3600.0 / rho_v_molar
        )
        velocity = volumetric_vapor_ft3_s / float(link_geometry.active_area_ft2)
        f_factor = velocity * np.sqrt(rho_v_mass)
        liquid_mass_flow = (
            float(liquid_flow[hydraulic_index[source]]) * liquid_mw
        )
        vapor_mass_flow = float(vapor_flow[link_index]) * vapor_mw
        flow_parameter = (
            liquid_mass_flow / vapor_mass_flow * np.sqrt(rho_v_mass / rho_l_mass)
        )
        liquid_height = (
            float(over_weir[link_index])
            + float(link_geometry.weir_height_in) / 12.0
        )
        dry_pressure_head = float(dry_drop[link_index]) * PSF_PER_PSIA / rho_l_mass
        backup_head = liquid_height + dry_pressure_head
        spacing = float(liquid_geometry.tray_spacing_ft)
        if spacing <= 0.0 or not np.isfinite(spacing):
            raise ValueError("tray spacing must be positive for backup evaluation")
        backup_fraction = backup_head / spacing
        backup_classification = _classification(backup_fraction, spec)

        limitation: str | None = None
        critical_effective_capacity_factor = float("nan")
        predicted_velocity = float("nan")
        flooding_fraction = float("nan")
        capacity_classification = "not_evaluated"
        evaluable = spec.capacity_factor_ft_s is not None
        if rho_l_mass <= rho_v_mass:
            limitation = "liquid mass density does not exceed vapor mass density"
            evaluable = False
        else:
            density_capacity_term = np.sqrt(
                (rho_l_mass - rho_v_mass) / rho_v_mass
            )
            critical_effective_capacity_factor = velocity / density_capacity_term
            if evaluable:
                predicted_velocity = (
                    float(spec.capacity_factor_ft_s)
                    * float(spec.system_factor)
                    * density_capacity_term
                )
                flooding_fraction = velocity / predicted_velocity
                capacity_classification = _classification(flooding_fraction, spec)
        if spec.capacity_factor_ft_s is None:
            limitation = "no declared tray flooding capacity factor"
        overall = (
            _worst_classification((capacity_classification, backup_classification))
            if evaluable
            else "not_evaluated"
        )
        stage_results.append(
            TrayHydraulicStageEvaluation(
                stage=source_index + 1,
                volume=str(source),
                source_link_index=link_index,
                vapor_flow_lbmolph=float(vapor_flow[link_index]),
                liquid_flow_lbmolph=float(liquid_flow[hydraulic_index[source]]),
                vapor_superficial_velocity_ft_s=float(velocity),
                vapor_f_factor=float(f_factor),
                liquid_to_vapor_mass_flow_parameter=float(flow_parameter),
                liquid_mass_density_lbm_ft3=float(rho_l_mass),
                vapor_mass_density_lbm_ft3=float(rho_v_mass),
                critical_effective_capacity_factor_ft_s=float(
                    critical_effective_capacity_factor
                ),
                predicted_flooding_velocity_ft_s=float(predicted_velocity),
                flooding_fraction=float(flooding_fraction),
                clear_liquid_height_ft=float(liquid_height),
                over_weir_head_ft=float(over_weir[link_index]),
                dry_tray_pressure_drop_psia=float(dry_drop[link_index]),
                liquid_head_pressure_drop_psia=float(liquid_drop[link_index]),
                total_tray_pressure_drop_psia=float(
                    dry_drop[link_index] + liquid_drop[link_index]
                ),
                backup_head_ft=float(backup_head),
                backup_fraction_of_tray_spacing=float(backup_fraction),
                capacity_classification=capacity_classification,
                backup_classification=backup_classification,
                overall_classification=overall,
                weeping_classification="not_evaluated",
                evaluable=bool(evaluable),
                limitation=limitation,
            )
        )

    if not stage_results:
        raise ValueError("column topology contains no physical tray pressure links")
    stages = [item.stage for item in stage_results]
    maximum_flooding, flooding_stage = _finite_maximum(
        [item.flooding_fraction for item in stage_results], stages
    )
    maximum_critical_factor, critical_factor_stage = _finite_maximum(
        [
            item.critical_effective_capacity_factor_ft_s
            for item in stage_results
        ],
        stages,
    )
    maximum_backup, backup_stage = _finite_maximum(
        [item.backup_fraction_of_tray_spacing for item in stage_results], stages
    )
    hydraulic_load = [
        max(item.flooding_fraction, item.backup_fraction_of_tray_spacing)
        if item.evaluable
        else float("nan")
        for item in stage_results
    ]
    maximum_load, limiting_stage = _finite_maximum(hydraulic_load, stages)
    fully_evaluable = all(item.evaluable for item in stage_results)
    overall = (
        _worst_classification([item.overall_classification for item in stage_results])
        if fully_evaluable
        else "not_evaluated"
    )
    predicted = bool(
        fully_evaluable
        and np.isfinite(maximum_load)
        and maximum_load >= float(spec.predicted_flooding_fraction)
    )
    hard_stop = bool(
        spec.hard_stop_fraction is not None
        and fully_evaluable
        and np.isfinite(maximum_load)
        and maximum_load >= float(spec.hard_stop_fraction)
    )
    limitations = {
        item.limitation for item in stage_results if item.limitation is not None
    }
    limitations.add(
        "downcomer friction and aerated-froth head are not represented by the v1 backup screen"
    )
    limitations.add(
        "weeping/dumping is not evaluated because hole or valve geometry is not declared"
    )
    return TrayHydraulicOperatingEnvelopeEvaluation(
        correlation_name=str(spec.correlation_name),
        correlation_version=str(spec.correlation_version),
        capacity_factor_ft_s=(
            None if spec.capacity_factor_ft_s is None else float(spec.capacity_factor_ft_s)
        ),
        system_factor=float(spec.system_factor),
        surface_tension_treatment=str(spec.surface_tension_treatment),
        backup_method=BACKUP_METHOD,
        advisory_fraction=float(spec.advisory_fraction),
        high_loading_fraction=float(spec.high_loading_fraction),
        predicted_flooding_fraction=float(spec.predicted_flooding_fraction),
        hard_stop_fraction=(
            None if spec.hard_stop_fraction is None else float(spec.hard_stop_fraction)
        ),
        stages=tuple(stage_results),
        fully_evaluable=bool(fully_evaluable),
        overall_classification=overall,
        maximum_flooding_fraction=float(maximum_flooding),
        flooding_limiting_stage=flooding_stage,
        maximum_critical_effective_capacity_factor_ft_s=float(
            maximum_critical_factor
        ),
        critical_effective_capacity_factor_limiting_stage=critical_factor_stage,
        maximum_backup_fraction=float(maximum_backup),
        backup_limiting_stage=backup_stage,
        maximum_hydraulic_load_fraction=float(maximum_load),
        limiting_stage=limiting_stage,
        predicted_flooding=predicted,
        hard_stop_reached=hard_stop,
        limitations=tuple(sorted(limitations)),
    )


def tray_hydraulic_stage_dict(
    evaluation: TrayHydraulicStageEvaluation,
) -> dict[str, Any]:
    return asdict(evaluation)


def tray_hydraulic_summary_dict(
    evaluation: TrayHydraulicOperatingEnvelopeEvaluation,
    *,
    include_stages: bool = False,
) -> dict[str, Any]:
    result = asdict(evaluation)
    if not include_stages:
        result.pop("stages", None)
    return result


__all__ = [
    "BACKUP_METHOD",
    "CORRELATION_VERSION",
    "TrayHydraulicOperatingEnvelopeEvaluation",
    "TrayHydraulicOperatingEnvelopeSpec",
    "TrayHydraulicStageEvaluation",
    "evaluate_tray_hydraulic_operating_envelope",
    "tray_hydraulic_stage_dict",
    "tray_hydraulic_summary_dict",
    "validate_tray_hydraulic_operating_envelope_spec",
]
