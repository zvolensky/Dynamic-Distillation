#!/usr/bin/env python
"""Prepare or execute DD-168's frozen seven-volume live numerical audit."""

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
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_provider_governed_numerical as dd092

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
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
    audit_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
    residual_rows,
    solve_local_bubble,
    structural_pattern,
    tp_flash_diagnostics,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


SCHEMA = "dd168-core-v3-seven-volume-numerical-contract-v1"
RESULT_SCHEMA = "dd168-core-v3-seven-volume-numerical-result-v1"
CONTRACT = Path("logs/dd168_core_v3_seven_volume_numerical_contract_20260806.json")
RESULT = Path("logs/dd168_core_v3_seven_volume_numerical_20260806")
WORKBOOK = Path("sandbox/mini8/input/distillation_column_template_8stage.xlsx")
PROPERTY_PACKAGE = "pr"
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
COUPLING_TOLERANCE = 1.0e-7
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.25
COMPONENT_CONSERVATION_LIMIT = 1.0e-12
ENERGY_CONSERVATION_LIMIT = 1.0e-10
BUBBLE_RESIDUAL_LIMIT = 1.0e-10
INDEPENDENT_TEMPERATURE_LIMIT_F = 1.0e-3
INDEPENDENT_COMPOSITION_LIMIT = 1.0e-6
FLASH_VAPOR_FRACTION_LIMIT = 1.0e-3
FLASH_CLOSURE_LIMIT = 1.0e-12
PROVIDER_CALL_LIMIT = 20000
WALL_CLOCK_LIMIT_SEC = 120.0
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tools/audit_core_v3_seven_volume_numerical.py",
    "tests/test_core_v3_provider_governed_residual_v1.py",
    "tests/test_core_v3_scaled_topology_v1.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _topology():
    return build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )


def _select_source_indices(column: Any) -> tuple[int, ...]:
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("DD-168 requires a staged feed")
    last = int(column.n_stages) - 1
    feed_index = int(feed.stage_1based) - 1
    rectifying = tuple(range(1, feed_index))
    stripping = tuple(range(feed_index + 1, last))
    if len(rectifying) < 2 or len(stripping) < 2:
        raise ValueError("source profile cannot supply two volumes per section")
    rect_selected = (rectifying[0], rectifying[-1])
    strip_selected = (stripping[0], stripping[-1])
    selected = (0, *rect_selected, feed_index, *strip_selected, last)
    if len(set(selected)) != 7:
        raise ValueError("DD-168 source-role mapping is not distinct")
    return selected


def _source_data(workbook: Path) -> tuple[Any, Any, dict[str, Any]]:
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    if column.M_L_lbmol is None:
        raise ValueError("DD-168 input requires liquid holdups")
    topology = _topology()
    indices = _select_source_indices(column)
    provider = dd092._provider(column, PROPERTY_PACKAGE)
    feed = column.streams.get("Feed")
    distillate = column.streams.get("Distillate")
    bottoms = column.streams.get("Bottom")
    if feed is None or distillate is None or bottoms is None:
        raise ValueError("DD-168 requires feed and both products")
    components = tuple(column.components_excel)
    liquid_moles = np.asarray(
        [
            dd092._required_spec_float(column, "Top Accumulator Holdup (lbmol)"),
            *(float(column.M_L_lbmol[index]) for index in indices[1:-1]),
            dd092._required_spec_float(column, "Bottom Holdup (lbmol)"),
        ],
        dtype=float,
    )
    liquid_x = np.asarray(
        [dd092.normalize_composition(column.x0[index]) for index in indices]
    )
    vapor_y = np.asarray(
        [dd092.normalize_composition(column.y0[index]) for index in indices[1:]]
    )
    source = {
        "component_names": list(components),
        "component_ids_dwsim": list(column.components_dwsim),
        "source_stage_1based": [index + 1 for index in indices],
        "roles": list(topology.volume_ids),
        "liquid_moles_lbmol": dd092._float_list(liquid_moles),
        "liquid_mole_fraction": dd092._float_rows(liquid_x),
        "temperature_F": dd092._float_list(
            [column.T_f[index] for index in indices]
        ),
        "pressure_psia": dd092._float_list(
            [column.P_psia[index] for index in indices]
        ),
        "vapor_mole_fraction": dd092._float_rows(vapor_y),
        "liquid_flow_reference_lbmolph": dd092._float_list(
            [column.L_lbmolph[index] for index in indices[1:-1]]
        ),
        "vapor_flow_reference_lbmolph": dd092._float_list(
            [
                column.V_lbmolph[indices[topology.volume_ids.index(source_volume)]]
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
        "distillate_reference_lbmolph": float(
            distillate.total_molar_flow_lbmolph
        ),
        "bottoms_reference_lbmolph": float(bottoms.total_molar_flow_lbmolph),
        "seed_mapping_used_flash_or_column_closure": False,
    }
    arrays = (
        liquid_moles,
        liquid_x,
        vapor_y,
        np.asarray(source["liquid_flow_reference_lbmolph"]),
        np.asarray(source["vapor_flow_reference_lbmolph"]),
    )
    if any(np.any(~np.isfinite(value)) or np.any(value <= 0.0) for value in arrays):
        raise ValueError("DD-168 source mapping is not finite and positive")
    return column, provider, source


def _spec(source: Mapping[str, Any], feed_enthalpy: float) -> OperatingSpec:
    return OperatingSpec(
        component_names=tuple(source["component_names"]),
        pressure_psia=np.asarray(source["pressure_psia"], dtype=float),
        reflux_lbmolph=float(source["reflux_lbmolph"]),
        feed_component_lbmolph=np.asarray(
            source["feed_component_lbmolph"], dtype=float
        ),
        feed_enthalpy_BTUph=float(feed_enthalpy),
        reboiler_duty_BTUph=float(source["reboiler_duty_BTUph"]),
        terminal_liquid_targets_lbmol=np.asarray(
            source["terminal_liquid_targets_lbmol"], dtype=float
        ),
        hydraulic_geometry=tuple(
            HydraulicGeometry(**item) for item in source["hydraulic_geometry"]
        ),
        topology=_topology(),
    )


def _reference(payload: Mapping[str, Any]) -> NumericalReference:
    return NumericalReference(
        liquid_moles_lbmol=np.asarray(payload["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=np.asarray(payload["liquid_mole_fraction"], dtype=float),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(payload["vapor_mole_fraction"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_reference_BTUph=float(
            payload["condenser_duty_reference_BTUph"]
        ),
        condenser_duty_scale_BTUph=float(payload["condenser_duty_scale_BTUph"]),
    )


def _reference_payload(reference: NumericalReference) -> dict[str, Any]:
    return {
        "liquid_moles_lbmol": dd092._float_list(reference.liquid_moles_lbmol),
        "liquid_mole_fraction": dd092._float_rows(reference.liquid_mole_fraction),
        "temperature_F": dd092._float_list(reference.temperature_F),
        "vapor_mole_fraction": dd092._float_rows(reference.vapor_mole_fraction),
        "hydraulic_liquid_flow_lbmolph": dd092._float_list(
            reference.hydraulic_liquid_flow_lbmolph
        ),
        "vapor_flow_lbmolph": dd092._float_list(reference.vapor_flow_lbmolph),
        "distillate_lbmolph": float(reference.distillate_lbmolph),
        "bottoms_lbmolph": float(reference.bottoms_lbmolph),
        "bubble_vapor_mole_fraction": dd092._float_list(
            reference.bubble_vapor_mole_fraction
        ),
        "condenser_duty_reference_BTUph": float(
            reference.condenser_duty_reference_BTUph
        ),
        "condenser_duty_scale_BTUph": float(reference.condenser_duty_scale_BTUph),
    }


def _scales(spec: OperatingSpec, reference: NumericalReference) -> np.ndarray:
    flow = max(
        float(np.sum(spec.feed_component_lbmolph)),
        float(spec.reflux_lbmolph),
        float(np.max(reference.hydraulic_liquid_flow_lbmolph)),
        float(np.max(reference.vapor_flow_lbmolph)),
        float(reference.distillate_lbmolph),
        float(reference.bottoms_lbmolph),
        1.0,
    )
    energy = max(
        abs(float(reference.condenser_duty_reference_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(spec.feed_enthalpy_BTUph)),
        1.0,
    )
    hydraulic_index = {
        volume: index
        for index, volume in enumerate(spec.topology.hydraulic_volume_ids)
    }
    values: list[float] = []
    for row in residual_rows(spec):
        if row.block in {"full_phase_equilibrium", "condenser_bubble_fugacity"}:
            values.append(1.0)
        elif row.block == "component_balance":
            values.append(flow)
        elif row.block == "energy_balance":
            values.append(energy)
        elif row.block == "francis_hydraulics":
            values.append(
                max(
                    float(
                        reference.hydraulic_liquid_flow_lbmolph[
                            hydraulic_index[row.owner]
                        ]
                    ),
                    1.0,
                )
            )
        elif row.block == "terminal_amount_specification":
            index = 0 if row.owner == spec.topology.top_volume else 1
            values.append(max(float(spec.terminal_liquid_targets_lbmol[index]), 1.0))
        else:
            raise RuntimeError(f"unscaled residual block {row.block!r}")
    return np.asarray(values, dtype=float)


def prepare(workbook: Path, contract_path: Path) -> dict[str, Any]:
    column, provider, source = _source_data(workbook)
    call_audit = ProviderCallAudit()
    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    feed_total = float(np.sum(feed_component))
    feed_h = call_audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=float(source["feed_temperature_F"]),
        pressure_psia=float(source["feed_pressure_psia"]),
        composition=feed_component / feed_total,
        caller="feed_enthalpy_seed",
        state_id="dd168_preparation",
        evaluation_kind="preparation",
    )
    spec = _spec(source, feed_total * feed_h)
    liquid_x = np.asarray(source["liquid_mole_fraction"], dtype=float)
    vapor_y = np.asarray(source["vapor_mole_fraction"], dtype=float)
    temperature = np.asarray(source["temperature_F"], dtype=float)
    settings = BubbleSolveSettings()
    bubble = solve_local_bubble(
        provider,
        call_audit,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=liquid_x[0],
        temperature_guess_F=float(temperature[0]),
        vapor_guess=vapor_y[0],
        state_id="canonical_seven_volume_state",
        evaluation_kind="preparation",
        settings=settings,
    )
    if not bubble.success or bubble.residual_inf_norm >= BUBBLE_RESIDUAL_LIMIT:
        raise RuntimeError("DD-168 canonical bubble reconstruction failed")
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
        call_audit,
        spec,
        provisional_state,
        state_id="canonical_seven_volume_state",
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
    scales = _scales(spec, reference)
    registry = audit_provider_governed_registry(
        build_provider_governed_registry(
            spec.component_names, topology=spec.topology
        )
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "workbook": str(workbook.resolve()),
        "workbook_sha256": _sha(workbook),
        "property_package": PROPERTY_PACKAGE,
        "source_mapping": source,
        "topology": asdict(spec.topology),
        "operating_spec": {
            "feed_enthalpy_BTUph": float(spec.feed_enthalpy_BTUph),
            "temperature_scale_F": float(spec.temperature_scale_F),
        },
        "reference": _reference_payload(reference),
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in rows],
        "fixed_residual_scales": dd092._float_list(scales),
        "state": dd092._float_list(np.zeros(dimension)),
        "state_construction": {
            "bubble": dd092._bubble_payload(bubble),
            "condenser_energy": duty_terms,
            "full_column_residual_used": False,
            "nonlinear_balance_solve_used": False,
        },
        "independent_pr_parameters": dd092._extract_pr_parameters(
            provider, source["component_ids_dwsim"]
        ),
        "bubble_solve_settings": asdict(settings),
        "jacobian": {
            "method": "uncolored_central_difference",
            "steps": list(JACOBIAN_STEPS),
            "coupling_tolerance": COUPLING_TOLERANCE,
        },
        "limits": {
            "condition": CONDITION_LIMIT,
            "spectrum_relative_change": SPECTRUM_CHANGE_LIMIT,
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
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "structural_registry_passed": bool(registry.pass_gate),
        "preparation_provider_provenance": call_audit.report(),
        "live_full_residual_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    contract_path.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-168 Frozen Seven-Volume Numerical-Audit Contract",
                "",
                f"- Coordinates/residuals: `{dimension} / {len(rows)}`",
                f"- Source roles: `{source['source_stage_1based']}`",
                f"- Contract SHA-256: `{payload['contract_payload_sha256']}`",
                "- Full residual evaluated during preparation: `False`",
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
        raise RuntimeError("DD-168 contract differs from committed content")
    payload = json.loads(path.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA or claimed != actual:
        raise RuntimeError("DD-168 contract schema or checksum failed")
    for implementation, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / implementation) != digest:
            raise RuntimeError(f"DD-168 implementation changed: {implementation}")
    return payload, _git("rev-parse", "HEAD")


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract, commit = _load_committed_contract(contract_path)
    workbook = Path(contract["workbook"])
    if _sha(workbook) != contract["workbook_sha256"]:
        raise RuntimeError("DD-168 workbook differs from contract")
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    provider = dd092._provider(column, str(contract["property_package"]))
    spec = _spec(
        contract["source_mapping"],
        float(contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = _reference(contract["reference"])
    point = np.asarray(contract["state"], dtype=float)
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-168 coordinate ledger changed")
    if [row.name for row in rows] != contract["residual_names"]:
        raise RuntimeError("DD-168 residual ledger changed")
    pattern = structural_pattern(spec)
    structural_rank_value = int(structural_rank(csr_matrix(pattern)))
    registry = audit_provider_governed_registry(
        build_provider_governed_registry(
            spec.component_names, topology=spec.topology
        )
    )
    q_rows = np.flatnonzero(pattern[:, layout.condenser_duty]).tolist()
    drum_energy = next(
        index
        for index, row in enumerate(rows)
        if row.name == f"energy_balance[{spec.topology.top_volume}]"
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
        state_id="canonical_seven_volume_state",
        evaluation_kind="residual",
    )
    jacobians = [
        audit_numerical_jacobian(
            spec,
            reference,
            provider,
            audit,
            point,
            fixed_scales=scales,
            state_id="canonical_seven_volume_state",
            step=step,
            coupling_tolerance=COUPLING_TOLERANCE,
        )
        for step in JACOBIAN_STEPS
    ]
    flash = tp_flash_diagnostics(
        provider,
        audit,
        temperature_F=float(evaluation.state.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        overall_z=evaluation.state.liquid_mole_fraction[0],
        state_id="canonical_seven_volume_state",
    )
    independent = dd092._independent_provider(contract)
    independent_bubble = solve_local_bubble(
        independent,
        audit,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=evaluation.state.liquid_mole_fraction[0],
        temperature_guess_F=float(evaluation.state.temperature_F[0]),
        vapor_guess=evaluation.state.bubble_vapor_mole_fraction,
        state_id="canonical_seven_volume_state",
        evaluation_kind="validation",
        independent=True,
        settings=BubbleSolveSettings(**contract["bubble_solve_settings"]),
    )
    elapsed = time.perf_counter() - started
    singular_a = jacobians[0].singular_values
    singular_b = jacobians[1].singular_values
    spectrum_change = float(
        np.max(np.abs(singular_a - singular_b) / np.maximum(np.abs(singular_a), 1e-15))
    )
    heights = evaluation.properties.liquid_height_ft[
        [spec.topology.volume_ids.index(v) for v in spec.topology.hydraulic_volume_ids]
    ]
    spacings = np.asarray(
        [geometry.tray_spacing_ft for geometry in spec.hydraulic_geometry]
    )
    bubble_indices = [
        index
        for index, row in enumerate(rows)
        if row.block == "condenser_bubble_fugacity"
    ]
    bubble_residual = float(np.max(np.abs(evaluation.raw[bubble_indices])))
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
    provenance = audit.report()
    call_count = int(provenance["total_calls"])
    numerical_pass = all(
        item.rank == len(layout.names)
        and item.condition < CONDITION_LIMIT
        and item.bubble_rank == len(spec.component_names)
        and not item.zero_rows
        and not item.zero_columns
        and not item.unexpected_couplings
        and not item.bubble_zero_rows
        and not item.bubble_zero_columns
        for item in jacobians
    )
    physical_pass = bool(
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
    )
    conservation_pass = bool(
        evaluation.component_telescoping_relative_error
        < COMPONENT_CONSERVATION_LIMIT
        and evaluation.energy_telescoping_relative_error
        < ENERGY_CONSERVATION_LIMIT
    )
    flash_pass = bool(
        not flash["stable_vapor"]
        and flash["vapor_fraction"] <= FLASH_VAPOR_FRACTION_LIMIT
        and flash["flash_Kx_identity_max_abs"] < FLASH_CLOSURE_LIMIT
        and flash["lever_rule_closure_max_abs"] < FLASH_CLOSURE_LIMIT
    )
    independent_pass = bool(
        independent_bubble.success
        and abs(independent_temperature) < INDEPENDENT_TEMPERATURE_LIMIT_F
        and independent_composition < INDEPENDENT_COMPOSITION_LIMIT
    )
    passed = bool(
        structural_rank_value == len(layout.names)
        and registry.pass_gate
        and q_rows == [drum_energy]
        and numerical_pass
        and spectrum_change < SPECTRUM_CHANGE_LIMIT
        and physical_pass
        and conservation_pass
        and bubble_residual < BUBBLE_RESIDUAL_LIMIT
        and flash_pass
        and independent_pass
        and provenance["pass"]
        and call_count < PROVIDER_CALL_LIMIT
        and elapsed < WALL_CLOCK_LIMIT_SEC
        and not evaluation.clipping_or_projection_used
        and not evaluation.property_fallback_used
    )
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "seven_volume_live_numerical_gate_passed"
            if passed
            else "seven_volume_live_numerical_gate_failed"
        ),
        "decision": (
            "authorize_one_frozen_seven_volume_stationary_root_campaign"
            if passed
            else "stop_seven_volume_path_before_root_solve"
        ),
        "contract_commit": commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "unknown_count": len(layout.names),
        "residual_count": len(rows),
        "structural_rank": structural_rank_value,
        "scaled_residual_inf_norm_diagnostic": float(
            np.max(np.abs(evaluation.scaled))
        ),
        "dominant_residuals": dd092._dominant_rows(evaluation),
        "jacobians": [dd092._jacobian_payload(item) for item in jacobians],
        "spectrum_relative_change": spectrum_change,
        "bubble_residual_inf_norm": bubble_residual,
        "component_telescoping_relative_error": float(
            evaluation.component_telescoping_relative_error
        ),
        "energy_telescoping_relative_error": float(
            evaluation.energy_telescoping_relative_error
        ),
        "physical_pass": physical_pass,
        "conservation_pass": conservation_pass,
        "numerical_jacobian_pass": numerical_pass,
        "tp_flash_diagnostic": dd092._json_diagnostic(flash),
        "tp_flash_pass": flash_pass,
        "independent_pr_validation": {
            "temperature_difference_F": independent_temperature,
            "vapor_max_abs": independent_composition,
            "pass": independent_pass,
        },
        "ownership": {
            "q_c_residual_rows_zero_based": q_rows,
            "drum_energy_row_zero_based": drum_energy,
            "registry_pass": bool(registry.pass_gate),
        },
        "provider_provenance": provenance,
        "provider_call_count": call_count,
        "wall_clock_sec": elapsed,
        "full_column_nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-168 Seven-Volume Live Numerical Audit",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Rank: `{structural_rank_value}/{len(layout.names)}`",
                f"- Worst condition: `{max(item.condition for item in jacobians):.6e}`",
                f"- Spectrum change: `{spectrum_change:.6e}`",
                f"- Calls: `{call_count}`",
                f"- Wall clock: `{elapsed:.3f} s`",
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
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--workbook", type=Path, default=WORKBOOK)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--out-prefix", type=Path, default=RESULT)
    args = parser.parse_args()
    if args.prepare_only:
        prepare(args.workbook, args.contract)
        return 0
    result = execute(args.contract, args.out_prefix)
    print(json.dumps(result, indent=2))
    return 0 if result["pass_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
