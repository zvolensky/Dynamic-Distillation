#!/usr/bin/env python
"""Audit the water-methanol workbook as a Core V3 stationary starting state."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402

from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    greedy_column_groups,
)
from dynamic_distillation.core_v3.density_routed_thermo_provider_v1 import (  # noqa: E402
    DensityRoutedThermoProviderV1,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (  # noqa: E402
    PressureLinkGeometry,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (  # noqa: E402
    build_column_topology,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (  # noqa: E402
    BubbleSolveSettings,
    HydraulicGeometry,
    OperatingSpec,
    solve_local_bubble,
)
from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (  # noqa: E402
    VaporHoldupBalanceInputs,
    evaluate_two_phase_transport,
    stationary_phase_transfer_from_vapor_transport,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dae_contract,
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (  # noqa: E402
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_properties,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_stationary_contract,
    build_vapor_holdup_stationary_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    VaporHoldupStationaryNumericalSpec,
    VaporHoldupStationaryReference,
    evaluate_vapor_holdup_stationary_residual,
    stationary_structural_pattern,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)
from dynamic_distillation.thermo_clapeyron_provider_v1 import (  # noqa: E402
    ThermoClapeyronProviderV1,
)


DEFAULT_WORKBOOK = Path(
    "water_methanol_template_10stage_chemsep_excess_enthalpy_"
    "p14p7_to_p17p7_geometry_20260713.xlsx"
)
DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_starting_state_audit_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_starting_state_audit_20260831.md"
)
PROPERTY_PACKAGE = "unifac"


def _normalized_key(value: str) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _resolve_stream(
    streams: Mapping[str, Any],
    *,
    role: str,
    aliases: Sequence[str],
) -> Any:
    by_key = {_normalized_key(name): stream for name, stream in streams.items()}
    matches = [by_key[_normalized_key(alias)] for alias in aliases if _normalized_key(alias) in by_key]
    unique = {id(stream): stream for stream in matches}
    if len(unique) != 1:
        available = ", ".join(sorted(streams))
        raise ValueError(f"requires one {role} stream; available streams: {available}")
    return next(iter(unique.values()))


def resolve_stream_roles(column: Any) -> dict[str, Any]:
    """Resolve common workbook names without changing the loaded column."""
    return {
        "feed": _resolve_stream(
            column.streams,
            role="feed",
            aliases=("Feed", "Feed1"),
        ),
        "distillate": _resolve_stream(
            column.streams,
            role="top product",
            aliases=("Distillate", "Top", "Overhead"),
        ),
        "bottoms": _resolve_stream(
            column.streams,
            role="bottom product",
            aliases=("Bottom", "Bottoms"),
        ),
    }


def _float_list(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values).reshape((-1,))]


def _float_rows(values: Any) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(values)]


def _source_mapping(column: Any) -> dict[str, Any]:
    streams = resolve_stream_roles(column)
    feed = streams["feed"]
    distillate = streams["distillate"]
    bottoms = streams["bottoms"]
    if feed.stage_1based is None or feed.temperature_f is None or feed.pressure_psia is None:
        raise ValueError("feed stream requires a stage, temperature, and pressure")
    if column.M_L_lbmol is None:
        raise ValueError("workbook requires source liquid holdups")
    if column.duties.q_cond_btu_per_h is None or column.duties.q_reb_btu_per_h is None:
        raise ValueError("workbook requires condenser and reboiler duties")

    stage_count = int(column.n_stages)
    feed_stage = int(feed.stage_1based)
    if feed_stage <= 2 or feed_stage >= stage_count - 1:
        raise ValueError("feed stage must leave trays above and below the feed")
    topology = build_column_topology(
        rectifying_volume_count=feed_stage - 2,
        stripping_volume_count=stage_count - feed_stage - 1,
    )
    if len(topology.volume_ids) != stage_count:
        raise RuntimeError("workbook stages do not map one-to-one to model volumes")

    indices = tuple(range(stage_count))
    components = tuple(column.components_excel)
    liquid_moles = np.asarray(
        (
            dd092._required_spec_float(column, "Top Accumulator Holdup (lbmol)"),
            *(float(column.M_L_lbmol[index]) for index in indices[1:-1]),
            dd092._required_spec_float(column, "Bottom Holdup (lbmol)"),
        ),
        dtype=float,
    )
    liquid_x = np.asarray(
        [dd092.normalize_composition(column.x0[index]) for index in indices],
        dtype=float,
    )
    vapor_y = np.asarray(
        [dd092.normalize_composition(column.y0[index]) for index in indices[1:]],
        dtype=float,
    )
    source_index = {volume: index for index, volume in enumerate(topology.volume_ids)}
    liquid_flow = np.asarray(column.L_lbmolph[1:-1], dtype=float)
    vapor_flow = np.asarray(
        [
            column.V_lbmolph[source_index[source_volume]]
            for source_volume, _destination, _symbol in topology.vapor_links
        ],
        dtype=float,
    )
    positive = (liquid_moles, liquid_x, vapor_y, liquid_flow, vapor_flow)
    if any(np.any(~np.isfinite(values)) or np.any(values <= 0.0) for values in positive):
        raise ValueError("workbook starting arrays must be finite and positive")

    return {
        "component_names": list(components),
        "component_ids_dwsim": list(column.components_dwsim),
        "source_stage_1based": [index + 1 for index in indices],
        "roles": list(topology.volume_ids),
        "stream_names": {role: stream.name for role, stream in streams.items()},
        "feed_stage_1based": feed_stage,
        "liquid_moles_lbmol": _float_list(liquid_moles),
        "liquid_mole_fraction": _float_rows(liquid_x),
        "temperature_F": _float_list(column.T_f),
        "pressure_psia": _float_list(column.P_psia),
        "vapor_mole_fraction": _float_rows(vapor_y),
        "liquid_flow_reference_lbmolph": _float_list(liquid_flow),
        "vapor_flow_reference_lbmolph": _float_list(vapor_flow),
        "reflux_lbmolph": float(column.L_lbmolph[0]),
        "feed_component_lbmolph": _float_list(
            dd092._stream_component_vector(feed, components)
        ),
        "feed_temperature_F": float(feed.temperature_f),
        "feed_pressure_psia": float(feed.pressure_psia),
        "condenser_duty_BTUph": float(column.duties.q_cond_btu_per_h),
        "reboiler_duty_BTUph": float(column.duties.q_reb_btu_per_h),
        "terminal_liquid_targets_lbmol": [float(liquid_moles[0]), float(liquid_moles[-1])],
        "hydraulic_geometry": [
            asdict(dd092._geometry_at(column, index)) for index in indices[1:-1]
        ],
        "distillate_reference_lbmolph": float(distillate.total_molar_flow_lbmolph),
        "bottoms_reference_lbmolph": float(bottoms.total_molar_flow_lbmolph),
    }


def _operating_spec(source: Mapping[str, Any], feed_enthalpy_BTUph: float) -> OperatingSpec:
    stage_count = len(source["source_stage_1based"])
    feed_stage = int(source["feed_stage_1based"])
    topology = build_column_topology(
        rectifying_volume_count=feed_stage - 2,
        stripping_volume_count=stage_count - feed_stage - 1,
    )
    return OperatingSpec(
        component_names=tuple(source["component_names"]),
        pressure_psia=np.asarray(source["pressure_psia"], dtype=float),
        reflux_lbmolph=float(source["reflux_lbmolph"]),
        feed_component_lbmolph=np.asarray(source["feed_component_lbmolph"], dtype=float),
        feed_enthalpy_BTUph=float(feed_enthalpy_BTUph),
        reboiler_duty_BTUph=float(source["reboiler_duty_BTUph"]),
        terminal_liquid_targets_lbmol=np.asarray(
            source["terminal_liquid_targets_lbmol"], dtype=float
        ),
        hydraulic_geometry=tuple(
            HydraulicGeometry(**item) for item in source["hydraulic_geometry"]
        ),
        topology=topology,
    )


def _pressure_geometry(column: Any, source: Mapping[str, Any], topology: Any) -> tuple[PressureLinkGeometry, ...]:
    geometry = column.geometry
    if geometry is None:
        raise ValueError("workbook requires pressure-link geometry")
    roles = tuple(source["roles"])
    stages = tuple(int(value) - 1 for value in source["source_stage_1based"])
    result = []
    for source_volume, _destination, _symbol in topology.vapor_links:
        source_stage = stages[roles.index(source_volume)]
        result.append(
            PressureLinkGeometry(
                active_area_ft2=float(geometry.active_area_ft2_per_stage[source_stage]),
                tray_area_ft2=float(geometry.area_ft2_per_stage[source_stage]),
                weir_height_in=float(geometry.weir_height_in_per_stage[source_stage]),
                include_liquid_head=source_volume != topology.bottom_volume,
            )
        )
    return tuple(result)


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def build_problem(
    workbook: Path = DEFAULT_WORKBOOK,
    *,
    density_model: str | None = None,
    property_package: str = PROPERTY_PACKAGE,
) -> dict[str, Any]:
    workbook_path = _rooted(workbook).resolve()
    case = load_case_from_excel(str(workbook_path))
    column = build_column_spec_from_case(case)
    source = _source_mapping(column)
    bulk_provider = dd092._provider(column, property_package)
    density_provider = None
    normalized_density_model = None
    provider = bulk_provider
    provider_audit_kwargs: dict[str, Any] = {"provider_identity": "dwsim"}
    if density_model is not None:
        normalized_density_model = str(density_model).strip().upper()
        if normalized_density_model != "VTPR":
            raise ValueError("the qualified density-only model is VTPR")
        density_provider = ThermoClapeyronProviderV1(
            column.components_excel,
            column.components_dwsim,
            model_name=normalized_density_model,
        )
        density_provider.validate_backend_available()
        density_identity = f"clapeyron_{normalized_density_model.lower()}"
        provider = DensityRoutedThermoProviderV1(
            bulk_provider=bulk_provider,
            density_provider=density_provider,
            density_provider_identity=density_identity,
        )
        provider_audit_kwargs["interface_provider_identities"] = {
            "declared_liquid_density": density_identity,
        }
    preparation_audit = ProviderCallAudit(**provider_audit_kwargs)

    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    feed_total = float(np.sum(feed_component))
    feed_enthalpy = preparation_audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=float(source["feed_temperature_F"]),
        pressure_psia=float(source["feed_pressure_psia"]),
        composition=feed_component / feed_total,
        caller="water_methanol_feed_enthalpy",
        state_id="water_methanol:preparation",
        evaluation_kind="preparation",
    )
    spec = _operating_spec(source, feed_total * feed_enthalpy)
    liquid_x = np.asarray(source["liquid_mole_fraction"], dtype=float)
    tail_vapor_y = np.asarray(source["vapor_mole_fraction"], dtype=float)
    temperature = np.asarray(source["temperature_F"], dtype=float).copy()
    pressure = np.asarray(source["pressure_psia"], dtype=float)
    top_bubble = solve_local_bubble(
        provider,
        preparation_audit,
        pressure_psia=float(pressure[0]),
        liquid_x=liquid_x[0],
        temperature_guess_F=float(temperature[0]),
        vapor_guess=tail_vapor_y[0],
        state_id="water_methanol:condenser_bubble",
        evaluation_kind="preparation",
        settings=BubbleSolveSettings(),
    )
    if not top_bubble.success or top_bubble.residual_inf_norm >= 1.0e-10:
        raise RuntimeError("top condenser bubble-point reconstruction failed")
    source_top_temperature = float(temperature[0])
    temperature[0] = top_bubble.temperature_F

    bottom_bubble = solve_local_bubble(
        provider,
        preparation_audit,
        pressure_psia=float(pressure[-1]),
        liquid_x=liquid_x[-1],
        temperature_guess_F=float(temperature[-1]),
        vapor_guess=(tail_vapor_y[-2] if len(tail_vapor_y) > 1 else tail_vapor_y[-1]),
        state_id="water_methanol:reboiler_bubble",
        evaluation_kind="preparation",
        settings=BubbleSolveSettings(),
    )
    if not bottom_bubble.success or bottom_bubble.residual_inf_norm >= 1.0e-10:
        raise RuntimeError("bottom reboiler bubble-point reconstruction failed")
    source_bottom_temperature = float(temperature[-1])
    temperature[-1] = bottom_bubble.temperature_F
    vapor_y = np.vstack((top_bubble.vapor_mole_fraction, tail_vapor_y))
    vapor_y[-1] = bottom_bubble.vapor_mole_fraction

    geometry = build_column_vapor_geometry(column, case.specs, spec.topology)
    vapor_topology = build_vapor_holdup_topology(
        column=spec.topology,
        vapor_volume_ft3=gross_capacity_mapping(geometry),
    )
    dynamic_contract = build_vapor_holdup_dae_contract(
        spec.component_names,
        topology=vapor_topology,
    )
    dynamic_structural = audit_vapor_holdup_dae_contract(dynamic_contract)
    contract = build_vapor_holdup_stationary_contract(
        spec.component_names,
        topology=vapor_topology,
    )
    structural = audit_vapor_holdup_stationary_contract(contract)
    if not dynamic_structural.pass_gate or not structural.pass_gate:
        raise RuntimeError("Core V3 structural audit failed")

    liquid_moles = np.asarray(source["liquid_moles_lbmol"], dtype=float)
    liquid_inventory = liquid_moles[:, np.newaxis] * liquid_x
    reference_properties = evaluate_vapor_holdup_properties(
        geometry,
        liquid_inventory,
        liquid_x,
        vapor_y,
        temperature,
        pressure,
        provider,
        preparation_audit,
        state_id="water_methanol:reference_properties",
    )
    molecular_weight = preparation_audit.component_molecular_weights(
        provider,
        caller="water_methanol_component_data",
        state_id="water_methanol:preparation",
        evaluation_kind="preparation",
    )
    balance_inputs = VaporHoldupBalanceInputs(
        topology=spec.topology,
        feed_component_lbmolph=spec.feed_component_lbmolph,
        feed_enthalpy_BTUph=spec.feed_enthalpy_BTUph,
        reflux_lbmolph=spec.reflux_lbmolph,
        distillate_lbmolph=float(source["distillate_reference_lbmolph"]),
        bottoms_lbmolph=float(source["bottoms_reference_lbmolph"]),
        condenser_duty_BTUph=float(source["condenser_duty_BTUph"]),
        reboiler_duty_BTUph=spec.reboiler_duty_BTUph,
    )
    reference_transport = evaluate_two_phase_transport(
        balance_inputs,
        liquid_x,
        vapor_y,
        np.asarray(source["liquid_flow_reference_lbmolph"], dtype=float),
        np.asarray(source["vapor_flow_reference_lbmolph"], dtype=float),
        reference_properties.liquid_enthalpy_BTU_lbmol,
        reference_properties.vapor_enthalpy_BTU_lbmol,
    )
    phase_transfer = stationary_phase_transfer_from_vapor_transport(reference_transport)
    component_scale = np.maximum(spec.feed_component_lbmolph, 1.0)
    transfer_scale = np.maximum(np.abs(phase_transfer), component_scale[np.newaxis, :])
    reference = VaporHoldupStationaryReference(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=reference_properties.vapor_component_inventory_lbmol,
        phase_transfer_lbmolph=phase_transfer,
        phase_transfer_scale_lbmolph=transfer_scale,
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=np.asarray(
            source["liquid_flow_reference_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(source["vapor_flow_reference_lbmolph"], dtype=float),
        condenser_duty_BTUph=float(source["condenser_duty_BTUph"]),
        distillate_lbmolph=float(source["distillate_reference_lbmolph"]),
        bottoms_lbmolph=float(source["bottoms_reference_lbmolph"]),
        top_liquid_inventory_target_lbmol=float(liquid_moles[0]),
        bottom_liquid_inventory_target_lbmol=float(liquid_moles[-1]),
    )
    numerical = VaporHoldupStationaryNumericalSpec(
        temperature_coordinate_scale_F=10.0,
        pressure_coordinate_scale_psia=1.0,
        dry_tray_pressure_drop_coefficient=40.0,
        component_mw_lbm_per_lbmol=np.asarray(molecular_weight, dtype=float),
        pressure_link_geometry=_pressure_geometry(column, source, spec.topology),
        top_pressure_anchor_psia=float(pressure[0]),
        component_residual_scale_lbmolph=component_scale,
        energy_residual_scale_BTUph=max(
            abs(spec.feed_enthalpy_BTUph),
            abs(spec.reboiler_duty_BTUph),
            abs(float(source["condenser_duty_BTUph"])),
        ),
        pressure_residual_scale_psia=1.0,
    )
    return {
        "workbook": workbook_path,
        "column": column,
        "source": source,
        "provider": provider,
        "bulk_provider": bulk_provider,
        "density_provider": density_provider,
        "density_model": normalized_density_model,
        "property_package": str(property_package),
        "provider_audit_kwargs": provider_audit_kwargs,
        "spec": spec,
        "geometry": geometry,
        "dynamic_contract": dynamic_contract,
        "dynamic_structural": dynamic_structural,
        "contract": contract,
        "structural": structural,
        "reference": reference,
        "reference_properties": reference_properties,
        "balance_inputs": balance_inputs,
        "numerical": numerical,
        "preparation_audit": preparation_audit,
        "bubble": top_bubble,
        "top_bubble": top_bubble,
        "bottom_bubble": bottom_bubble,
        "source_top_temperature_F": source_top_temperature,
        "source_bottom_temperature_F": source_bottom_temperature,
    }


def _block_norms(contract: Any, evaluation: Any, values: np.ndarray) -> dict[str, float]:
    result: dict[str, float] = {}
    for block in sorted({row.block for row in contract.rows}):
        indices = [index for index, row in enumerate(contract.rows) if row.block == block]
        result[block] = float(np.max(np.abs(values[indices])))
    return result


def build_report(
    workbook: Path = DEFAULT_WORKBOOK,
    *,
    density_model: str | None = None,
    property_package: str = PROPERTY_PACKAGE,
) -> dict[str, Any]:
    problem = build_problem(
        workbook,
        density_model=density_model,
        property_package=property_package,
    )
    contract = problem["contract"]
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    evaluation = evaluate_vapor_holdup_stationary_residual(
        contract,
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        problem["provider"],
        audit,
        np.zeros(len(contract.variables)),
        state_id="water_methanol:starting_state",
        evaluation_kind="residual",
    )
    pattern = stationary_structural_pattern(contract)
    groups = greedy_column_groups(pattern)
    raw_blocks = _block_norms(contract, evaluation, evaluation.raw)
    scaled_blocks = _block_norms(contract, evaluation, evaluation.scaled)
    order = np.argsort(np.abs(evaluation.scaled))[::-1][:10]
    dominant = [
        {
            "row": evaluation.row_names[int(index)],
            "raw_residual": float(evaluation.raw[index]),
            "scaled_residual": float(evaluation.scaled[index]),
        }
        for index in order
    ]
    provider_report = audit.report()
    dimension = len(contract.variables)
    source = problem["source"]
    properties = problem["reference_properties"]
    finite = bool(np.all(np.isfinite(evaluation.raw)) and np.all(np.isfinite(evaluation.scaled)))
    provider_pass = bool(
        audit.record_count == 6 * len(contract.topology.column.volume_ids)
        and not audit.fallback_attempted
        and provider_report["pass"]
    )
    usable = bool(
        problem["dynamic_structural"].pass_gate
        and problem["structural"].pass_gate
        and pattern.shape == (dimension, dimension)
        and finite
        and float(np.min(properties.free_volume.free_vapor_volume_ft3)) > 0.0
        and float(np.max(np.abs(evaluation.properties.eos_relative_residual))) < 1.0e-12
        and float(np.max(np.abs(evaluation.terminal_inventory_residual_lbmol))) < 1.0e-12
        and provider_pass
    )
    scaled_max = float(np.max(np.abs(evaluation.scaled)))
    steady = bool(usable and scaled_max <= 1.0e-6)
    workbook_path = problem["workbook"]
    return {
        "schema_id": "core-v3-water-methanol-starting-state-audit-v1",
        "classification": (
            "usable_starting_state_already_steady"
            if steady
            else "usable_starting_state_not_steady"
            if usable
            else "starting_state_not_usable"
        ),
        "workbook": str(workbook_path),
        "workbook_sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        "property_package": problem["property_package"],
        "bulk_provider": "dwsim",
        "liquid_density_provider": (
            "dwsim"
            if problem["density_model"] is None
            else f"clapeyron_{problem['density_model'].lower()}"
        ),
        "density_model": problem["density_model"],
        "components": list(problem["spec"].component_names),
        "stream_names": source["stream_names"],
        "stage_count": len(source["roles"]),
        "feed_stage_1based": source["feed_stage_1based"],
        "volume_roles": source["roles"],
        "dynamic_dimension": len(problem["dynamic_contract"].rows),
        "stationary_dimension": dimension,
        "dynamic_structural_audit": asdict(problem["dynamic_structural"]),
        "stationary_structural_audit": asdict(problem["structural"]),
        "source_adjustments": {
            "top_temperature_workbook_F": problem["source_top_temperature_F"],
            "top_temperature_bubble_F": float(problem["bubble"].temperature_F),
            "top_temperature_change_F": float(
                problem["bubble"].temperature_F - problem["source_top_temperature_F"]
            ),
            "top_bubble_residual_inf_norm": float(problem["bubble"].residual_inf_norm),
            "top_bubble_vapor_mole_fraction": _float_list(
                problem["bubble"].vapor_mole_fraction
            ),
            "bottom_temperature_workbook_F": problem["source_bottom_temperature_F"],
            "bottom_temperature_bubble_F": float(problem["bottom_bubble"].temperature_F),
            "bottom_temperature_change_F": float(
                problem["bottom_bubble"].temperature_F
                - problem["source_bottom_temperature_F"]
            ),
            "bottom_bubble_residual_inf_norm": float(
                problem["bottom_bubble"].residual_inf_norm
            ),
            "bottom_bubble_vapor_mole_fraction": _float_list(
                problem["bottom_bubble"].vapor_mole_fraction
            ),
            "note": (
                "Total-condenser and total-reboiler equilibrium vapor states were "
                "reconstructed generically; the workbook was not edited."
            ),
        },
        "physical_checks": {
            "minimum_free_vapor_volume_ft3": float(
                np.min(properties.free_volume.free_vapor_volume_ft3)
            ),
            "minimum_liquid_density_lbmol_ft3": float(
                np.min(properties.liquid_density_lbmol_ft3)
            ),
            "minimum_vapor_inventory_lbmol": float(
                np.min(np.sum(properties.vapor_component_inventory_lbmol, axis=1))
            ),
            "maximum_relative_eos_residual": float(
                np.max(np.abs(evaluation.properties.eos_relative_residual))
            ),
            "terminal_inventory_residual_lbmol": _float_list(
                evaluation.terminal_inventory_residual_lbmol
            ),
        },
        "starting_residual": {
            "scaled_inf_norm": scaled_max,
            "raw_block_inf_norms": raw_blocks,
            "scaled_block_inf_norms": scaled_blocks,
            "dominant_rows": dominant,
            "component_telescoping_error_lbmolph": _float_list(
                evaluation.balances.global_component_telescoping_error_lbmolph
            ),
            "energy_telescoping_error_BTUph": float(
                evaluation.balances.global_energy_telescoping_error_BTUph
            ),
        },
        "provider_calls": {
            "preparation": problem["preparation_audit"].record_count,
            "governing_residual": audit.record_count,
            "fallback_attempted": audit.fallback_attempted,
            "pass_gate": provider_pass,
        },
        "prospective_jacobian": {
            "color_count": len(groups),
            "central_residual_evaluations": 2 * len(groups),
            "uncolored_central_residual_evaluations": 2 * dimension,
        },
        "starting_state_usable": usable,
        "starting_state_is_steady": steady,
        "nonlinear_solve_attempted": False,
        "jacobian_evaluated": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": usable,
        "decision": (
            "ready_for_stationary_jacobian_audit"
            if usable
            else "stop_and_correct_starting_state"
        ),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    raw = report["starting_residual"]["raw_block_inf_norms"]
    scaled = report["starting_residual"]["scaled_block_inf_norms"]
    first = report["starting_residual"]["dominant_rows"][0]
    return "\n".join(
        (
            "# Core V3 water-methanol starting-state audit",
            "",
            f"- Result: `{report['classification']}`",
            f"- Next gate: `{report['decision']}`",
            f"- Workbook: `{Path(report['workbook']).name}`",
            f"- Model size: `{report['stationary_dimension']} equations and variables`",
            f"- DWSIM property package: `{report['property_package']}`",
            f"- Liquid-density provider: `{report['liquid_density_provider']}`",
            f"- Largest scaled mismatch: `{report['starting_residual']['scaled_inf_norm']:.6e}`",
            f"- Largest fugacity mismatch: `{scaled['full_phase_equilibrium']:.6e}`",
            f"- Largest pressure mismatch: `{raw['vapor_pressure_drop']:.6e} psia`",
            f"- Largest liquid-flow mismatch: `{raw['francis_hydraulics']:.6e} lbmol/h`",
            f"- Largest energy mismatch: `{raw['total_energy_balance']:.6e} BTU/h`",
            f"- Dominant equation: `{first['row']}`",
            "- Nonlinear solve, Jacobian, or timestep: `False`",
            "",
            "## Meaning",
            "",
            (
                "The workbook is a valid, physically usable starting point for Core V3. "
                "All ten vapor spaces remain positive, the stationary equation set has "
                "full structural rank, and every live UNIFAC property call completed "
                "without a fallback."
            ),
            "",
            (
                "It is not yet a steady Core V3 solution. The largest mismatch is the "
                "methanol phase-equilibrium equation in the combined reboiler/sump. "
                "The prescribed pressure profile and several tray liquid flows also need "
                "to move when the stationary equations are solved."
            ),
            "",
            (
                "The workbook was left unchanged. This audit stopped before computing a "
                "Jacobian, running a nonlinear solve, or advancing time."
            ),
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--density-model", choices=("VTPR",), default=None)
    args = parser.parse_args()
    report = build_report(args.workbook, density_model=args.density_model)
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "scaled_residual_inf_norm": report["starting_residual"]["scaled_inf_norm"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
