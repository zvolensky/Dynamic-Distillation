#!/usr/bin/env python
"""Prepare or execute DD-222's frozen full-C3/C4 live readiness audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_provider_governed_numerical as dd092
import audit_core_v3_seven_volume_numerical as dd168

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    audit_provider_governed_registry,
    build_column_topology,
    build_provider_governed_registry,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    BubbleSolveSettings,
    HydraulicGeometry,
    NumericalReference,
    OperatingSpec,
    audit_colored_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
    residual_rows,
    solve_local_bubble,
    structural_pattern,
    tp_flash_diagnostics,
)
from dynamic_distillation.core_v3.structural_rank_v1 import structural_rank_fast
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


SCHEMA = "dd222-core-v3-full-c3c4-live-readiness-contract-v1"
RESULT_SCHEMA = "dd222-core-v3-full-c3c4-live-readiness-result-v1"
WORKBOOK = Path(
    "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"
)
CONTRACT = Path("logs/dd222_core_v3_full_c3c4_live_readiness_contract_20260815.json")
RESULT = Path("logs/dd222_core_v3_full_c3c4_live_readiness_20260815")
PROPERTY_PACKAGE = "pr"
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
COUPLING_TOLERANCE = 1.0e-7
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.25
SENTINEL_RELATIVE_LIMIT = 1.0e-6
COMPONENT_CONSERVATION_LIMIT = 1.0e-12
ENERGY_CONSERVATION_LIMIT = 1.0e-10
BUBBLE_RESIDUAL_LIMIT = 1.0e-10
INDEPENDENT_TEMPERATURE_LIMIT_F = 1.0e-3
INDEPENDENT_COMPOSITION_LIMIT = 1.0e-6
FLASH_VAPOR_FRACTION_LIMIT = 1.0e-3
FLASH_CLOSURE_LIMIT = 1.0e-12
PROVIDER_CALL_LIMIT = 100000
WALL_CLOCK_LIMIT_SEC = 900.0
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/structural_rank_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tools/audit_core_v3_seven_volume_numerical.py",
    "tools/audit_core_v3_full_c3c4_live_readiness.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _topology(stage_count: int, feed_stage_1based: int):
    return build_column_topology(
        rectifying_volume_count=feed_stage_1based - 2,
        stripping_volume_count=stage_count - feed_stage_1based - 1,
    )


def _source_mapping(column: Any) -> dict[str, Any]:
    feed = column.streams.get("Feed")
    distillate = column.streams.get("Distillate")
    bottoms = column.streams.get("Bottom")
    if feed is None or feed.stage_1based is None or distillate is None or bottoms is None:
        raise ValueError("DD-222 requires one staged feed and both products")
    if column.M_L_lbmol is None:
        raise ValueError("DD-222 requires source liquid holdups")
    stage_count = int(column.n_stages)
    topology = _topology(stage_count, int(feed.stage_1based))
    indices = tuple(range(stage_count))
    components = tuple(column.components_excel)
    liquid_moles = np.asarray(
        [
            dd092._required_spec_float(column, "Top Accumulator Holdup (lbmol)"),
            *(float(column.M_L_lbmol[index]) for index in indices[1:-1]),
            dd092._required_spec_float(column, "Bottom Holdup (lbmol)"),
        ],
        dtype=float,
    )
    source_index = {
        volume: index for index, volume in enumerate(topology.volume_ids)
    }
    source = {
        "component_names": list(components),
        "component_ids_dwsim": list(column.components_dwsim),
        "source_stage_1based": [index + 1 for index in indices],
        "roles": list(topology.volume_ids),
        "liquid_moles_lbmol": dd092._float_list(liquid_moles),
        "liquid_mole_fraction": dd092._float_rows(
            [dd092.normalize_composition(column.x0[index]) for index in indices]
        ),
        "temperature_F": dd092._float_list(column.T_f),
        "pressure_psia": dd092._float_list(column.P_psia),
        "vapor_mole_fraction": dd092._float_rows(
            [dd092.normalize_composition(column.y0[index]) for index in indices[1:]]
        ),
        "liquid_flow_reference_lbmolph": dd092._float_list(column.L_lbmolph[1:-1]),
        "vapor_flow_reference_lbmolph": dd092._float_list(
            [
                column.V_lbmolph[source_index[source_volume]]
                for source_volume, _destination, _symbol in topology.vapor_links
            ]
        ),
        "reflux_lbmolph": float(column.L_lbmolph[0]),
        "feed_component_lbmolph": dd092._float_list(
            dd092._stream_component_vector(feed, components)
        ),
        "feed_temperature_F": float(feed.temperature_f),
        "feed_pressure_psia": float(feed.pressure_psia),
        "reboiler_duty_BTUph": float(column.duties.q_reb_btu_per_h),
        "terminal_liquid_targets_lbmol": [
            float(liquid_moles[0]),
            float(liquid_moles[-1]),
        ],
        "hydraulic_geometry": [
            asdict(dd092._geometry_at(column, index)) for index in indices[1:-1]
        ],
        "distillate_reference_lbmolph": float(distillate.total_molar_flow_lbmolph),
        "bottoms_reference_lbmolph": float(bottoms.total_molar_flow_lbmolph),
        "seed_is_accepted_root": False,
        "seed_mapping_used_flash_or_column_closure": False,
    }
    arrays = (
        liquid_moles,
        np.asarray(source["liquid_mole_fraction"]),
        np.asarray(source["vapor_mole_fraction"]),
        np.asarray(source["liquid_flow_reference_lbmolph"]),
        np.asarray(source["vapor_flow_reference_lbmolph"]),
    )
    if any(np.any(~np.isfinite(value)) or np.any(value <= 0.0) for value in arrays):
        raise ValueError("DD-222 source mapping is not finite and positive")
    return source


def _spec(source: Mapping[str, Any], feed_enthalpy: float) -> OperatingSpec:
    topology = _topology(
        len(source["source_stage_1based"]),
        source["roles"].index("feed_tray") + 1,
    )
    return OperatingSpec(
        component_names=tuple(source["component_names"]),
        pressure_psia=np.asarray(source["pressure_psia"], dtype=float),
        reflux_lbmolph=float(source["reflux_lbmolph"]),
        feed_component_lbmolph=np.asarray(source["feed_component_lbmolph"], dtype=float),
        feed_enthalpy_BTUph=float(feed_enthalpy),
        reboiler_duty_BTUph=float(source["reboiler_duty_BTUph"]),
        terminal_liquid_targets_lbmol=np.asarray(
            source["terminal_liquid_targets_lbmol"], dtype=float
        ),
        hydraulic_geometry=tuple(
            HydraulicGeometry(**item) for item in source["hydraulic_geometry"]
        ),
        topology=topology,
    )


def _reference(payload: Mapping[str, Any]) -> NumericalReference:
    return dd168._reference(payload)


def _sentinel_columns(layout: Any) -> tuple[int, ...]:
    indices: list[int] = []
    for block in (
        layout.liquid_moles,
        layout.liquid_alr,
        layout.temperature,
        layout.vapor_alr,
        layout.liquid_flows,
        layout.vapor_flows,
        layout.bubble_alr,
    ):
        indices.extend((block.start, block.stop - 1))
    indices.extend((layout.distillate, layout.bottoms, layout.condenser_duty))
    return tuple(dict.fromkeys(indices))


def prepare(workbook: Path, contract_path: Path) -> dict[str, Any]:
    source_path = (ROOT / workbook).resolve()
    column = build_column_spec_from_case(load_case_from_excel(str(source_path)))
    source = _source_mapping(column)
    provider = dd092._provider(column, PROPERTY_PACKAGE)
    audit = ProviderCallAudit()
    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    feed_total = float(np.sum(feed_component))
    feed_h = audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=float(source["feed_temperature_F"]),
        pressure_psia=float(source["feed_pressure_psia"]),
        composition=feed_component / feed_total,
        caller="feed_enthalpy_seed",
        state_id="dd222_preparation",
        evaluation_kind="preparation",
    )
    spec = _spec(source, feed_total * feed_h)
    liquid_x = np.asarray(source["liquid_mole_fraction"], dtype=float)
    vapor_y = np.asarray(source["vapor_mole_fraction"], dtype=float)
    temperature = np.asarray(source["temperature_F"], dtype=float)
    settings = BubbleSolveSettings()
    bubble = solve_local_bubble(
        provider,
        audit,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=liquid_x[0],
        temperature_guess_F=float(temperature[0]),
        vapor_guess=vapor_y[0],
        state_id="dd222_source_audit_point",
        evaluation_kind="preparation",
        settings=settings,
    )
    if not bubble.success or bubble.residual_inf_norm >= BUBBLE_RESIDUAL_LIMIT:
        raise RuntimeError("DD-222 condenser bubble reconstruction failed")
    temperature[0] = bubble.temperature_F
    provisional = NumericalReference(
        liquid_moles_lbmol=np.asarray(source["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=liquid_x,
        temperature_F=temperature,
        vapor_mole_fraction=vapor_y,
        hydraulic_liquid_flow_lbmolph=np.asarray(
            source["liquid_flow_reference_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(
            source["vapor_flow_reference_lbmolph"], dtype=float
        ),
        distillate_lbmolph=float(source["distillate_reference_lbmolph"]),
        bottoms_lbmolph=float(source["bottoms_reference_lbmolph"]),
        bubble_vapor_mole_fraction=bubble.vapor_mole_fraction,
        condenser_duty_reference_BTUph=-1.0,
        condenser_duty_scale_BTUph=1.0,
    )
    dimension = len(coordinate_layout(spec).names)
    provisional_state = decode_coordinates(spec, provisional, np.zeros(dimension))
    duty, duty_terms = dd092._condenser_duty(
        provider,
        audit,
        spec,
        provisional_state,
        state_id="dd222_source_audit_point",
        evaluation_kind="preparation",
    )
    duty_scale = max(
        abs(duty),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(spec.feed_enthalpy_BTUph)),
    )
    reference = NumericalReference(
        **{
            **provisional.__dict__,
            "condenser_duty_reference_BTUph": duty,
            "condenser_duty_scale_BTUph": duty_scale,
        }
    )
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    pattern = structural_pattern(spec)
    groups = greedy_column_groups(pattern)
    sentinels = _sentinel_columns(layout)
    registry = audit_provider_governed_registry(
        build_provider_governed_registry(spec.component_names, topology=spec.topology)
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "workbook": str(source_path),
        "workbook_sha256": _sha(source_path),
        "property_package": PROPERTY_PACKAGE,
        "source_mapping": source,
        "topology": asdict(spec.topology),
        "operating_spec": {
            "feed_enthalpy_BTUph": float(spec.feed_enthalpy_BTUph),
            "temperature_scale_F": float(spec.temperature_scale_F),
        },
        "reference": dd168._reference_payload(reference),
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in rows],
        "fixed_residual_scales": dd092._float_list(dd168._scales(spec, reference)),
        "state": dd092._float_list(np.zeros(dimension)),
        "state_construction": {
            "bubble": dd092._bubble_payload(bubble),
            "condenser_energy": duty_terms,
            "source_seed_is_accepted_root": False,
            "full_column_residual_used": False,
            "nonlinear_balance_solve_used": False,
        },
        "independent_pr_parameters": dd092._extract_pr_parameters(
            provider, source["component_ids_dwsim"]
        ),
        "bubble_solve_settings": asdict(settings),
        "jacobian": {
            "method": "structurally_colored_central_difference",
            "steps": list(JACOBIAN_STEPS),
            "color_groups": [list(group) for group in groups],
            "color_count": len(groups),
            "sentinel_columns_zero_based": list(sentinels),
            "sentinel_coordinate_names": [layout.names[index] for index in sentinels],
            "prospective_residual_evaluations": 1
            + len(JACOBIAN_STEPS) * (1 + 2 * len(groups))
            + 2 * len(sentinels),
            "equivalent_uncolored_residual_evaluations": 1
            + len(JACOBIAN_STEPS) * (1 + 2 * dimension),
            "coupling_tolerance": COUPLING_TOLERANCE,
        },
        "limits": {
            "condition": CONDITION_LIMIT,
            "spectrum_relative_change": SPECTRUM_CHANGE_LIMIT,
            "sentinel_colored_relative": SENTINEL_RELATIVE_LIMIT,
            "component_conservation_relative": COMPONENT_CONSERVATION_LIMIT,
            "energy_conservation_relative": ENERGY_CONSERVATION_LIMIT,
            "bubble_residual_inf": BUBBLE_RESIDUAL_LIMIT,
            "independent_temperature_abs_F": INDEPENDENT_TEMPERATURE_LIMIT_F,
            "independent_vapor_max_abs": INDEPENDENT_COMPOSITION_LIMIT,
            "tp_flash_vapor_fraction": FLASH_VAPOR_FRACTION_LIMIT,
            "tp_flash_internal_closure": FLASH_CLOSURE_LIMIT,
            "provider_call_count": PROVIDER_CALL_LIMIT,
            "wall_clock_sec": WALL_CLOCK_LIMIT_SEC,
        },
        "required_rank": dimension,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "structural_registry_passed": bool(registry.pass_gate),
        "preparation_provider_provenance": audit.report(),
        "live_full_residual_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-222 contract already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-222 Frozen Full-C3/C4 Live-Readiness Contract",
                "",
                f"- Coordinates/residuals: `{dimension} / {len(rows)}`",
                f"- Structural colors: `{len(groups)}`",
                f"- Prospective residual evaluations: `{payload['jacobian']['prospective_residual_evaluations']}`",
                f"- Uncolored equivalent: `{payload['jacobian']['equivalent_uncolored_residual_evaluations']}`",
                "- Workbook profile is an audit point, not an accepted root.",
                "- Nonlinear solve, timestep, or integration: `False`",
                "",
                "One execution is authorized after this contract is committed.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _load_committed_contract(path: Path) -> tuple[dict[str, Any], str]:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    if committed.replace("\r\n", "\n").strip() != path.read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n").strip():
        raise RuntimeError("DD-222 contract differs from committed content")
    payload = json.loads(path.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA or claimed != actual:
        raise RuntimeError("DD-222 contract schema or checksum failed")
    for implementation, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / implementation) != digest:
            raise RuntimeError(f"DD-222 implementation changed: {implementation}")
    return payload, _git("rev-parse", "HEAD")


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    return float(
        np.max(np.abs(first - second) / np.maximum(np.abs(first), 1.0e-15))
    )


def _direct_column(
    spec: OperatingSpec,
    reference: NumericalReference,
    provider: Any,
    audit: ProviderCallAudit,
    point: np.ndarray,
    scales: np.ndarray,
    column: int,
    step: float,
) -> np.ndarray:
    delta = np.zeros_like(point)
    delta[column] = step
    values = []
    for suffix, candidate in (("plus", point + delta), ("minus", point - delta)):
        values.append(
            evaluate_residual(
                spec,
                reference,
                provider,
                audit,
                candidate,
                fixed_scales=scales,
                state_id=f"dd222_sentinel_{column}:{suffix}",
                evaluation_kind="jacobian",
            ).scaled
        )
    return (values[0] - values[1]) / (2.0 * step)


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract, commit = _load_committed_contract(ROOT / contract_path)
    workbook = Path(contract["workbook"])
    if _sha(workbook) != contract["workbook_sha256"]:
        raise RuntimeError("DD-222 workbook differs from contract")
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    provider = dd092._provider(column, str(contract["property_package"]))
    provider.set_exact_state_memoization(True, clear=True)
    spec = _spec(
        contract["source_mapping"],
        float(contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = _reference(contract["reference"])
    point = np.asarray(contract["state"], dtype=float)
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    pattern = structural_pattern(spec)
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-222 coordinate ledger changed")
    if [row.name for row in rows] != contract["residual_names"]:
        raise RuntimeError("DD-222 residual ledger changed")
    if [list(group) for group in greedy_column_groups(pattern)] != contract["jacobian"]["color_groups"]:
        raise RuntimeError("DD-222 color groups changed")
    registry = audit_provider_governed_registry(
        build_provider_governed_registry(spec.component_names, topology=spec.topology)
    )
    audit = ProviderCallAudit()
    started = time.perf_counter()
    evaluation = evaluate_residual(
        spec,
        reference,
        provider,
        audit,
        point,
        fixed_scales=scales,
        state_id="dd222_source_audit_point",
        evaluation_kind="residual",
    )
    colored = []
    groups = []
    for step in contract["jacobian"]["steps"]:
        item, item_groups = audit_colored_numerical_jacobian(
            spec,
            reference,
            provider,
            audit,
            point,
            fixed_scales=scales,
            state_id=f"dd222_colored_{step:g}",
            step=float(step),
            coupling_tolerance=float(contract["jacobian"]["coupling_tolerance"]),
        )
        colored.append(item)
        groups.append(item_groups)
    sentinel_records = []
    first_step = float(contract["jacobian"]["steps"][0])
    for column_index in contract["jacobian"]["sentinel_columns_zero_based"]:
        direct = _direct_column(
            spec,
            reference,
            provider,
            audit,
            point,
            scales,
            int(column_index),
            first_step,
        )
        expected = colored[0].matrix[:, int(column_index)]
        difference = float(np.max(np.abs(direct - expected)))
        relative = difference / max(float(np.max(np.abs(direct))), 1.0e-15)
        sentinel_records.append(
            {
                "column_zero_based": int(column_index),
                "coordinate": layout.names[int(column_index)],
                "maximum_abs_difference": difference,
                "relative_difference": relative,
                "off_pattern_max_abs": float(
                    np.max(np.abs(direct[~pattern[:, int(column_index)]]), initial=0.0)
                ),
            }
        )
    flash = tp_flash_diagnostics(
        provider,
        audit,
        temperature_F=float(evaluation.state.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        overall_z=evaluation.state.liquid_mole_fraction[0],
        state_id="dd222_source_audit_point",
    )
    independent = dd092._independent_provider(contract)
    independent_bubble = solve_local_bubble(
        independent,
        audit,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=evaluation.state.liquid_mole_fraction[0],
        temperature_guess_F=float(evaluation.state.temperature_F[0]),
        vapor_guess=evaluation.state.bubble_vapor_mole_fraction,
        state_id="dd222_source_audit_point",
        evaluation_kind="validation",
        independent=True,
        settings=BubbleSolveSettings(**contract["bubble_solve_settings"]),
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provenance = audit.report()
    limits = contract["limits"]
    spectrum_change = _spectrum_change(
        colored[0].singular_values, colored[1].singular_values
    )
    bubble_indices = [
        index for index, row in enumerate(rows)
        if row.block == "condenser_bubble_fugacity"
    ]
    bubble_residual = float(np.max(np.abs(evaluation.raw[bubble_indices])))
    heights = evaluation.properties.liquid_height_ft[
        [spec.topology.volume_ids.index(v) for v in spec.topology.hydraulic_volume_ids]
    ]
    spacings = np.asarray([item.tray_spacing_ft for item in spec.hydraulic_geometry])
    independent_temperature = float(
        independent_bubble.temperature_F - evaluation.state.temperature_F[0]
    )
    independent_composition = float(
        np.max(
            np.abs(
                independent_bubble.vapor_mole_fraction
                - evaluation.state.bubble_vapor_mole_fraction
            )
        )
    )
    sentinel_max = max(item["relative_difference"] for item in sentinel_records)
    gates = {
        "structural": structural_rank_fast(pattern) == len(layout.names) and registry.pass_gate,
        "colored_rank": all(item.rank == contract["required_rank"] for item in colored),
        "colored_condition": all(item.condition < limits["condition"] for item in colored),
        "colored_structure": all(
            not item.zero_rows and not item.zero_columns and not item.unexpected_couplings
            and item.bubble_rank == len(spec.component_names)
            and not item.bubble_zero_rows and not item.bubble_zero_columns
            for item in colored
        ),
        "spectrum_stable": spectrum_change < limits["spectrum_relative_change"],
        "sentinel_colored_agreement": sentinel_max < limits["sentinel_colored_relative"],
        "physical": bool(
            np.all(np.isfinite(evaluation.raw))
            and np.all(evaluation.state.liquid_moles_lbmol > 0.0)
            and np.all(evaluation.state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(evaluation.state.vapor_flow_lbmolph > 0.0)
            and evaluation.state.distillate_lbmolph > 0.0
            and evaluation.state.bottoms_lbmolph > 0.0
            and evaluation.state.condenser_duty_BTUph < 0.0
            and np.all(evaluation.properties.liquid_density_lbmol_ft3 > 0.0)
            and np.all(heights > 0.0)
            and np.all(heights < spacings)
        ),
        "component_conservation": evaluation.component_telescoping_relative_error
        < limits["component_conservation_relative"],
        "energy_conservation": evaluation.energy_telescoping_relative_error
        < limits["energy_conservation_relative"],
        "bubble": bubble_residual < limits["bubble_residual_inf"],
        "tp_flash": bool(
            not flash["stable_vapor"]
            and flash["vapor_fraction"] <= limits["tp_flash_vapor_fraction"]
            and flash["flash_Kx_identity_max_abs"] < limits["tp_flash_internal_closure"]
            and flash["lever_rule_closure_max_abs"] < limits["tp_flash_internal_closure"]
        ),
        "independent_pr": bool(
            independent_bubble.success
            and abs(independent_temperature) < limits["independent_temperature_abs_F"]
            and independent_composition < limits["independent_vapor_max_abs"]
        ),
        "provider_provenance": bool(provenance["pass"]),
        "provider_calls": int(provenance["total_calls"]) < limits["provider_call_count"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
        "no_fallback_or_projection": not evaluation.clipping_or_projection_used
        and not evaluation.property_fallback_used,
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "full_c3c4_live_readiness_passed"
            if passed else "full_c3c4_live_readiness_failed"
        ),
        "decision": (
            "authorize_one_frozen_full_c3c4_stationary_root_campaign"
            if passed else "stop_before_full_c3c4_root_solve"
        ),
        "contract_commit": commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "unknown_count": len(layout.names),
        "residual_count": len(rows),
        "source_seed_is_accepted_root": False,
        "scaled_residual_inf_norm_diagnostic": float(np.max(np.abs(evaluation.scaled))),
        "dominant_residuals": dd092._dominant_rows(evaluation),
        "jacobians": [dd092._jacobian_payload(item) for item in colored],
        "color_count": len(groups[0]),
        "sentinel_columns": sentinel_records,
        "sentinel_max_relative_difference": sentinel_max,
        "spectrum_relative_change": spectrum_change,
        "bubble_residual_inf_norm": bubble_residual,
        "component_telescoping_relative_error": float(
            evaluation.component_telescoping_relative_error
        ),
        "energy_telescoping_relative_error": float(
            evaluation.energy_telescoping_relative_error
        ),
        "tp_flash_diagnostic": dd092._json_diagnostic(flash),
        "independent_pr_validation": {
            "temperature_difference_F": independent_temperature,
            "vapor_max_abs": independent_composition,
        },
        "provider_provenance": provenance,
        "provider_call_count": int(provenance["total_calls"]),
        "exact_state_memoization": memo,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass_gate": passed,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    destination = ROOT / out_prefix
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.with_suffix(".json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-222 Full-C3/C4 Live-Readiness Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Rank: `{min(item.rank for item in colored)}/{len(layout.names)}`",
                f"- Colors: `{result['color_count']}`",
                f"- Calls: `{result['provider_call_count']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Source residual diagnostic: `{result['scaled_residual_inf_norm_diagnostic']:.6e}`",
                "- Nonlinear solve, timestep, or integration: `False`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--workbook", type=Path, default=WORKBOOK)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    if args.prepare:
        output = prepare(args.workbook, args.contract)
    else:
        output = execute(args.contract, args.result)
    print(json.dumps(output, indent=2))
    return 0 if args.prepare or output["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
