#!/usr/bin/env python
"""Prepare or execute the frozen DD-092 Core V3 live numerical audit."""

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
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    HYDRAULIC_VOLUME_IDS,
    VOLUME_IDS,
    audit_provider_governed_registry,
    build_provider_governed_registry,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    BubbleSolveSettings,
    HydraulicGeometry,
    IndependentPengRobinsonProvider,
    NumericalReference,
    OperatingSpec,
    PengRobinsonParameters,
    PhysicalState,
    alr_coordinates,
    audit_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    encode_state,
    evaluate_residual,
    normalize_composition,
    residual_rows,
    solve_local_bubble,
    structural_pattern,
    tp_flash_diagnostics,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SCHEMA_ID = "dd092-core-v3-provider-governed-numerical-contract-v1"
RESULT_SCHEMA_ID = "dd092-core-v3-provider-governed-numerical-result-v1"
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
JACOBIAN_COUPLING_TOLERANCE = 1.0e-7
JACOBIAN_CONDITION_HARD_STOP = 1.0e8
COMPONENT_CONSERVATION_TOLERANCE = 1.0e-12
ENERGY_CONSERVATION_TOLERANCE = 1.0e-10
BUBBLE_RESIDUAL_TOLERANCE = 1.0e-10
INDEPENDENT_PR_TEMPERATURE_TOLERANCE_F = 1.0e-3
INDEPENDENT_PR_COMPOSITION_TOLERANCE = 1.0e-6
TP_FLASH_VAPOR_FRACTION_TOLERANCE = 1.0e-3
TP_FLASH_INTERNAL_TOLERANCE = 1.0e-12

CONTRACT_IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/__init__.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tools/audit_core_v3_provider_governed_numerical.py",
    "tests/test_core_v3_provider_governed_registry_v1.py",
    "tests/test_core_v3_provider_call_audit_v1.py",
    "tests/test_core_v3_provider_governed_residual_v1.py",
    "docs/dd_092_core_v3_provider_governed_numerical_contract_20260719.md",
)


def _float_list(values: Any) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _float_rows(values: Any) -> list[list[float]]:
    return [_float_list(row) for row in np.asarray(values, dtype=float)]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _normalized_key(value: str) -> str:
    return "".join(
        character for character in str(value).casefold() if character.isalnum()
    )


def _stream_component_vector(stream: Any, component_names: Sequence[str]) -> np.ndarray:
    values = stream.component_molar_flows_lbmolph
    if values is None:
        raise ValueError(f"{stream.name} requires component molar flows")
    by_key = {
        _normalized_key(name): float(value) for name, value in values.items()
    }
    result = np.asarray(
        [by_key[_normalized_key(component)] for component in component_names],
        dtype=float,
    )
    if np.any(~np.isfinite(result)) or np.any(result < 0.0):
        raise ValueError(f"{stream.name} component flows are invalid")
    return result


def _select_role_indices(column: Any) -> tuple[int, ...]:
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("DD-092 requires a staged feed")
    stage_count = int(column.n_stages)
    if stage_count < 5:
        raise ValueError("DD-092 requires at least five source locations")
    last = stage_count - 1
    feed_index = int(feed.stage_1based) - 1
    if feed_index <= 1 or feed_index >= last - 1:
        raise ValueError("DD-092 requires source trays above and below the feed")
    rectifying = max(1, feed_index // 2)
    stripping = min(last - 1, feed_index + max(1, (last - feed_index) // 2))
    selected = (0, rectifying, feed_index, stripping, last)
    if len(set(selected)) != len(VOLUME_IDS):
        raise ValueError("source profile cannot supply five distinct roles")
    return selected


def _required_spec_float(column: Any, name: str) -> float:
    value = column.specs_raw.get(name)
    if value is None:
        raise ValueError(f"DD-092 requires specification {name!r}")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"DD-092 specification {name!r} must be positive")
    return result


def _geometry_at(column: Any, stage_index: int) -> HydraulicGeometry:
    geometry = column.geometry
    if geometry is None:
        raise ValueError("DD-092 requires tray geometry")
    factors = geometry.hydraulic_c_factor_per_stage
    return HydraulicGeometry(
        active_area_ft2=float(geometry.active_area_ft2_per_stage[stage_index]),
        tray_spacing_ft=float(geometry.tray_spacing_ft_per_stage[stage_index]),
        weir_height_in=float(geometry.weir_height_in_per_stage[stage_index]),
        weir_length_ft=float(geometry.weir_length_ft_per_stage[stage_index]),
        hydraulic_c_factor=(
            1.0 if factors is None else float(factors[stage_index])
        ),
    )


def _provider(column: Any, property_package: str) -> ThermoProviderV1:
    return ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=property_package,
        silence_backend_console=True,
    )


def _source_data(
    workbook: Path,
    property_package: str,
) -> tuple[Any, ThermoProviderV1, dict[str, Any]]:
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    if column.M_L_lbmol is None:
        raise ValueError("DD-092 input requires source liquid holdups")
    indices = _select_role_indices(column)
    provider = _provider(column, property_package)
    feed = column.streams.get("Feed")
    distillate = column.streams.get("Distillate")
    bottoms = column.streams.get("Bottom")
    if feed is None or distillate is None or bottoms is None:
        raise ValueError("DD-092 requires Feed, Distillate, and Bottom streams")
    if feed.temperature_f is None or feed.pressure_psia is None:
        raise ValueError("DD-092 feed requires declared temperature and pressure")
    if column.duties.q_reb_btu_per_h is None:
        raise ValueError("DD-092 requires declared reboiler duty")
    components = tuple(column.components_excel)
    feed_component = _stream_component_vector(feed, components)
    liquid_moles = np.asarray(
        (
            _required_spec_float(column, "Top Accumulator Holdup (lbmol)"),
            float(column.M_L_lbmol[indices[1]]),
            float(column.M_L_lbmol[indices[2]]),
            float(column.M_L_lbmol[indices[3]]),
            _required_spec_float(column, "Bottom Holdup (lbmol)"),
        ),
        dtype=float,
    )
    liquid_x = np.asarray(
        [normalize_composition(column.x0[index]) for index in indices],
        dtype=float,
    )
    temperature = np.asarray(
        [float(column.T_f[index]) for index in indices], dtype=float
    )
    pressure = np.asarray(
        [float(column.P_psia[index]) for index in indices], dtype=float
    )
    vapor_y = np.asarray(
        [
            normalize_composition(column.y0[indices[VOLUME_IDS.index(volume)]])
            for volume in VOLUME_IDS[1:]
        ],
        dtype=float,
    )
    liquid_flow = np.asarray(
        [
            float(column.L_lbmolph[indices[VOLUME_IDS.index(volume)]])
            for volume in HYDRAULIC_VOLUME_IDS
        ],
        dtype=float,
    )
    vapor_flow = np.asarray(
        [
            float(column.V_lbmolph[indices[VOLUME_IDS.index(source)]])
            for source, _destination, _symbol in (
                (
                    "combined_reboiler_sump",
                    "stripping_tray",
                    "",
                ),
                ("stripping_tray", "feed_tray", ""),
                ("feed_tray", "rectifying_tray", ""),
                ("rectifying_tray", "reflux_drum", ""),
            )
        ],
        dtype=float,
    )
    positive = (liquid_moles, liquid_x, vapor_y, liquid_flow, vapor_flow)
    if any(np.any(~np.isfinite(values)) or np.any(values <= 0.0) for values in positive):
        raise ValueError("DD-092 source mapping is not finite and positive")
    source = {
        "component_names": list(components),
        "component_ids_dwsim": list(column.components_dwsim),
        "source_stage_1based": [int(index + 1) for index in indices],
        "roles": list(VOLUME_IDS),
        "liquid_moles_lbmol": _float_list(liquid_moles),
        "liquid_mole_fraction": _float_rows(liquid_x),
        "temperature_F": _float_list(temperature),
        "pressure_psia": _float_list(pressure),
        "vapor_mole_fraction": _float_rows(vapor_y),
        "liquid_flow_reference_lbmolph": _float_list(liquid_flow),
        "vapor_flow_reference_lbmolph": _float_list(vapor_flow),
        "reflux_lbmolph": float(column.L_lbmolph[0]),
        "feed_component_lbmolph": _float_list(feed_component),
        "feed_temperature_F": float(feed.temperature_f),
        "feed_pressure_psia": float(feed.pressure_psia),
        "reboiler_duty_BTUph": float(column.duties.q_reb_btu_per_h),
        "terminal_liquid_targets_lbmol": [
            float(liquid_moles[0]),
            float(liquid_moles[-1]),
        ],
        "hydraulic_geometry": [
            asdict(_geometry_at(column, indices[VOLUME_IDS.index(volume)]))
            for volume in HYDRAULIC_VOLUME_IDS
        ],
        "distillate_reference_lbmolph": float(
            distillate.total_molar_flow_lbmolph
        ),
        "bottoms_reference_lbmolph": float(bottoms.total_molar_flow_lbmolph),
        "seed_mapping_used_flash_or_column_closure": False,
    }
    return column, provider, source


def _extract_pr_parameters(
    provider: ThermoProviderV1,
    component_ids: Sequence[str],
) -> dict[str, Any]:
    from dynamic_distillation import pr_flash_backend_v1 as backend

    provider.configure_backend()
    backend._init_dwsim()

    def constant(component_id: str, name: str) -> float:
        return float(backend._dtlc.GetCompoundConstProp(component_id, name))

    tc = [constant(component, "criticalTemperature") for component in component_ids]
    pc = [constant(component, "criticalPressure") for component in component_ids]
    omega = [constant(component, "acentricFactor") for component in component_ids]
    kij = np.zeros((len(component_ids), len(component_ids)), dtype=float)
    interactions = backend._prop_package.m_pr.InteractionParameters
    for i, left in enumerate(component_ids):
        for j, right in enumerate(component_ids):
            if i == j:
                continue
            for first, second in ((left, right), (right, left)):
                try:
                    kij[i, j] = float(interactions[first][second].kij)
                    break
                except Exception:
                    continue
    return {
        "critical_temperature_K": _float_list(tc),
        "critical_pressure_Pa": _float_list(pc),
        "acentric_factor": _float_list(omega),
        "binary_interaction": _float_rows(kij),
        "source": (
            "DWSIM compound constants and PengRobinsonPropertyPackage "
            "interaction parameters; equations evaluated independently"
        ),
    }


def _spec_from_source(source: Mapping[str, Any], feed_enthalpy: float) -> OperatingSpec:
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
            HydraulicGeometry(**values)
            for values in source["hydraulic_geometry"]
        ),
    )


def _condenser_duty(
    provider: Any,
    call_audit: ProviderCallAudit,
    spec: OperatingSpec,
    state: PhysicalState,
    *,
    state_id: str,
    evaluation_kind: str,
) -> tuple[float, dict[str, float]]:
    h_liquid = call_audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=float(state.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        composition=state.liquid_mole_fraction[0],
        caller="condenser_energy_seed",
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    h_vapor = call_audit.phase_enthalpy(
        provider,
        phase="vapor",
        temperature_F=float(state.temperature_F[1]),
        pressure_psia=float(spec.pressure_psia[1]),
        composition=state.vapor_mole_fraction[0],
        caller="condenser_energy_seed",
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    top_vapor = float(state.vapor_flow_lbmolph[-1])
    outlet_liquid = float(spec.reflux_lbmolph + state.distillate_lbmolph)
    duty = outlet_liquid * h_liquid - top_vapor * h_vapor
    if not np.isfinite(duty) or duty >= 0.0:
        raise RuntimeError("DD-092 condenser energy seed is not negative")
    return float(duty), {
        "drum_liquid_enthalpy_BTU_lbmol": h_liquid,
        "top_vapor_enthalpy_BTU_lbmol": h_vapor,
        "top_vapor_flow_lbmolph": top_vapor,
        "outlet_liquid_flow_lbmolph": outlet_liquid,
        "condenser_duty_BTUph": float(duty),
    }


def _residual_scales(
    spec: OperatingSpec,
    reference: NumericalReference,
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
    energy_scale = max(
        abs(float(reference.condenser_duty_reference_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(spec.feed_enthalpy_BTUph)),
        1.0,
    )
    values: list[float] = []
    for row in residual_rows(spec):
        if row.block in {
            "full_phase_equilibrium",
            "condenser_bubble_fugacity",
        }:
            values.append(1.0)
        elif row.block == "component_balance":
            values.append(flow_scale)
        elif row.block == "energy_balance":
            values.append(energy_scale)
        elif row.block == "francis_hydraulics":
            index = HYDRAULIC_VOLUME_IDS.index(row.owner)
            values.append(
                max(
                    float(reference.hydraulic_liquid_flow_lbmolph[index]),
                    1.0,
                )
            )
        elif row.block == "terminal_amount_specification":
            index = 0 if row.owner == VOLUME_IDS[0] else 1
            values.append(
                max(float(spec.terminal_liquid_targets_lbmol[index]), 1.0)
            )
        else:
            raise RuntimeError(f"unscaled Core V3 residual block {row.block!r}")
    result = np.asarray(values, dtype=float)
    if result.shape != (40,) or np.any(result <= 0.0):
        raise RuntimeError("Core V3 generated residual scales are invalid")
    return result


def _reference_payload(reference: NumericalReference) -> dict[str, Any]:
    return {
        "liquid_moles_lbmol": _float_list(reference.liquid_moles_lbmol),
        "liquid_mole_fraction": _float_rows(reference.liquid_mole_fraction),
        "temperature_F": _float_list(reference.temperature_F),
        "vapor_mole_fraction": _float_rows(reference.vapor_mole_fraction),
        "hydraulic_liquid_flow_lbmolph": _float_list(
            reference.hydraulic_liquid_flow_lbmolph
        ),
        "vapor_flow_lbmolph": _float_list(reference.vapor_flow_lbmolph),
        "distillate_lbmolph": float(reference.distillate_lbmolph),
        "bottoms_lbmolph": float(reference.bottoms_lbmolph),
        "bubble_vapor_mole_fraction": _float_list(
            reference.bubble_vapor_mole_fraction
        ),
        "condenser_duty_reference_BTUph": float(
            reference.condenser_duty_reference_BTUph
        ),
        "condenser_duty_scale_BTUph": float(
            reference.condenser_duty_scale_BTUph
        ),
    }


def _reference_from_payload(payload: Mapping[str, Any]) -> NumericalReference:
    return NumericalReference(
        liquid_moles_lbmol=np.asarray(payload["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=np.asarray(
            payload["liquid_mole_fraction"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(
            payload["vapor_mole_fraction"], dtype=float
        ),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(
            payload["vapor_flow_lbmolph"], dtype=float
        ),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_reference_BTUph=float(
            payload["condenser_duty_reference_BTUph"]
        ),
        condenser_duty_scale_BTUph=float(
            payload["condenser_duty_scale_BTUph"]
        ),
    )


def _bubble_payload(result: Any) -> dict[str, Any]:
    return {
        "temperature_F": float(result.temperature_F),
        "vapor_mole_fraction": _float_list(result.vapor_mole_fraction),
        "scaled_coordinates": _float_list(result.scaled_coordinates),
        "residual": _float_list(result.residual),
        "residual_inf_norm": float(result.residual_inf_norm),
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "nfev": int(result.nfev),
        "njev": result.njev,
    }


def _contract_markdown(contract: Mapping[str, Any]) -> str:
    states = contract["states"]
    return "\n".join(
        (
            "# DD-092 Frozen Core V3 Numerical-Audit Contract",
            "",
            f"- Schema: `{contract['schema_id']}`",
            f"- Payload SHA-256: `{contract['contract_payload_sha256']}`",
            f"- Preparation base commit: `{contract['preparation_base_commit']}`",
            f"- Workbook SHA-256: `{contract['workbook_sha256']}`",
            f"- Property package: `{contract['property_package']}`",
            f"- Coordinates/residuals: "
            f"`{len(contract['coordinate_names'])} / "
            f"{len(contract['residual_names'])}`",
            "- Full live column residual evaluated during preparation: `False`",
            "- Full nonlinear root solve attempted: `False`",
            "- Dynamic integration attempted: `False`",
            "",
            "## Frozen States",
            "",
            f"- Canonical vector length: "
            f"`{len(states['canonical_core_v3_state'])}`",
            f"- Perturbed vector length: "
            f"`{len(states['deterministic_combined_perturbation'])}`",
            "- Both drum states were constructed by local direct-fugacity "
            "bubble solves.",
            "- Each state carries its independently reconstructed negative "
            "condenser duty.",
            "",
            "## Execution",
            "",
            "After this contract and implementation are committed, execute one "
            "two-state audit. Use uncolored central differences at `1e-5` and "
            "`5e-6`, then run TP-flash diagnostics and independent PR validation "
            "outside the residual/Jacobian path.",
            "",
            "No full-column nonlinear solve, root import, mass-matrix work, or "
            "dynamic integration is authorized.",
            "",
        )
    )


def prepare(
    workbook: Path,
    property_package: str,
    contract_path: Path,
) -> dict[str, Any]:
    column, provider, source = _source_data(workbook, property_package)
    call_audit = ProviderCallAudit()
    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    feed_total = float(np.sum(feed_component))
    feed_x = feed_component / feed_total
    feed_h = call_audit.phase_enthalpy(
        provider,
        phase="liquid",
        temperature_F=float(source["feed_temperature_F"]),
        pressure_psia=float(source["feed_pressure_psia"]),
        composition=feed_x,
        caller="feed_enthalpy_seed",
        state_id="contract_preparation",
        evaluation_kind="preparation",
    )
    feed_enthalpy = feed_total * feed_h
    spec = _spec_from_source(source, feed_enthalpy)
    settings = BubbleSolveSettings()
    source_liquid_x = np.asarray(source["liquid_mole_fraction"], dtype=float)
    source_vapor_y = np.asarray(source["vapor_mole_fraction"], dtype=float)
    source_temperature = np.asarray(source["temperature_F"], dtype=float)
    canonical_bubble = solve_local_bubble(
        provider,
        call_audit,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=source_liquid_x[0],
        temperature_guess_F=float(source_temperature[0]),
        vapor_guess=source_vapor_y[0],
        state_id="canonical_core_v3_state",
        evaluation_kind="preparation",
        settings=settings,
    )
    if (
        not canonical_bubble.success
        or canonical_bubble.residual_inf_norm >= BUBBLE_RESIDUAL_TOLERANCE
    ):
        raise RuntimeError("canonical Core V3 bubble seed failed")
    canonical_temperature = source_temperature.copy()
    canonical_temperature[0] = canonical_bubble.temperature_F
    provisional_reference = NumericalReference(
        liquid_moles_lbmol=np.asarray(source["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=source_liquid_x,
        temperature_F=canonical_temperature,
        vapor_mole_fraction=source_vapor_y,
        hydraulic_liquid_flow_lbmolph=np.asarray(
            source["liquid_flow_reference_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(
            source["vapor_flow_reference_lbmolph"], dtype=float
        ),
        distillate_lbmolph=float(source["distillate_reference_lbmolph"]),
        bottoms_lbmolph=float(source["bottoms_reference_lbmolph"]),
        bubble_vapor_mole_fraction=canonical_bubble.vapor_mole_fraction,
        condenser_duty_reference_BTUph=-1.0,
        condenser_duty_scale_BTUph=1.0,
    )
    provisional_state = decode_coordinates(
        spec, provisional_reference, np.zeros(40, dtype=float)
    )
    canonical_duty, canonical_energy = _condenser_duty(
        provider,
        call_audit,
        spec,
        provisional_state,
        state_id="canonical_core_v3_state",
        evaluation_kind="preparation",
    )
    duty_scale = max(
        abs(canonical_duty),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(spec.feed_enthalpy_BTUph)),
    )
    reference = NumericalReference(
        **{
            **provisional_reference.__dict__,
            "condenser_duty_reference_BTUph": canonical_duty,
            "condenser_duty_scale_BTUph": duty_scale,
        }
    )
    canonical = np.zeros(40, dtype=float)

    layout = coordinate_layout(spec)
    perturbation = np.zeros(40, dtype=float)
    interior = np.arange(1, 4, dtype=float)
    perturbation[layout.liquid_moles.start + 1 : layout.liquid_moles.stop - 1] = (
        0.003 * np.sin(interior)
    )
    perturbation[layout.liquid_alr] = 0.002 * np.cos(
        np.arange(1, layout.liquid_alr.stop - layout.liquid_alr.start + 1)
    )
    perturbation[layout.temperature.start + 1 : layout.temperature.stop] = (
        0.002 * np.sin(np.arange(2, 6, dtype=float))
    )
    perturbation[layout.vapor_alr] = 0.002 * np.cos(
        np.arange(1, layout.vapor_alr.stop - layout.vapor_alr.start + 1)
    )
    perturbation[layout.liquid_flows] = np.asarray([0.002, -0.001, 0.0015])
    perturbation[layout.vapor_flows] = np.asarray(
        [-0.0015, 0.001, 0.0015, -0.001]
    )
    perturbation[layout.distillate] = -0.001
    perturbation[layout.bottoms] = 0.001
    provisional_perturbed = decode_coordinates(spec, reference, perturbation)
    perturbed_bubble = solve_local_bubble(
        provider,
        call_audit,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=provisional_perturbed.liquid_mole_fraction[0],
        temperature_guess_F=float(reference.temperature_F[0]),
        vapor_guess=reference.bubble_vapor_mole_fraction,
        state_id="deterministic_combined_perturbation",
        evaluation_kind="preparation",
        settings=settings,
    )
    if (
        not perturbed_bubble.success
        or perturbed_bubble.residual_inf_norm >= BUBBLE_RESIDUAL_TOLERANCE
    ):
        raise RuntimeError("perturbed Core V3 bubble seed failed")
    perturbed_temperature = provisional_perturbed.temperature_F.copy()
    perturbed_temperature[0] = perturbed_bubble.temperature_F
    perturbed_without_duty = PhysicalState(
        liquid_moles_lbmol=provisional_perturbed.liquid_moles_lbmol,
        liquid_mole_fraction=provisional_perturbed.liquid_mole_fraction,
        temperature_F=perturbed_temperature,
        vapor_mole_fraction=provisional_perturbed.vapor_mole_fraction,
        hydraulic_liquid_flow_lbmolph=(
            provisional_perturbed.hydraulic_liquid_flow_lbmolph
        ),
        vapor_flow_lbmolph=provisional_perturbed.vapor_flow_lbmolph,
        distillate_lbmolph=provisional_perturbed.distillate_lbmolph,
        bottoms_lbmolph=provisional_perturbed.bottoms_lbmolph,
        bubble_vapor_mole_fraction=perturbed_bubble.vapor_mole_fraction,
        condenser_duty_BTUph=canonical_duty,
    )
    perturbed_duty, perturbed_energy = _condenser_duty(
        provider,
        call_audit,
        spec,
        perturbed_without_duty,
        state_id="deterministic_combined_perturbation",
        evaluation_kind="preparation",
    )
    perturbed_state = PhysicalState(
        **{
            **perturbed_without_duty.__dict__,
            "condenser_duty_BTUph": perturbed_duty,
        }
    )
    perturbed = encode_state(spec, reference, perturbed_state)

    scales = _residual_scales(spec, reference)
    registry_audit = audit_provider_governed_registry(
        build_provider_governed_registry(spec.component_names)
    )
    pr_parameters = _extract_pr_parameters(
        provider, source["component_ids_dwsim"]
    )
    implementation_hashes = {
        path: _sha256_file(ROOT / path)
        for path in CONTRACT_IMPLEMENTATION_PATHS
        if (ROOT / path).exists()
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "workbook": str(workbook.resolve()),
        "workbook_sha256": _sha256_file(workbook),
        "property_package": property_package,
        "source_mapping": source,
        "operating_spec": {
            "feed_enthalpy_BTUph": float(spec.feed_enthalpy_BTUph),
            "temperature_scale_F": float(spec.temperature_scale_F),
        },
        "reference": _reference_payload(reference),
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in residual_rows(spec)],
        "residual_blocks": {
            "full_phase_equilibrium": 12,
            "component_balance": 15,
            "energy_balance": 5,
            "francis_hydraulics": 3,
            "terminal_amount_specification": 2,
            "condenser_bubble_fugacity": 3,
        },
        "fixed_residual_scales": _float_list(scales),
        "states": {
            "canonical_core_v3_state": _float_list(canonical),
            "deterministic_combined_perturbation": _float_list(perturbed),
        },
        "state_construction": {
            "canonical_bubble": _bubble_payload(canonical_bubble),
            "canonical_condenser_energy": canonical_energy,
            "deterministic_perturbed_bubble": _bubble_payload(perturbed_bubble),
            "deterministic_perturbed_condenser_energy": perturbed_energy,
            "signed_affine_duty_scale_BTUph": float(duty_scale),
            "full_column_residual_used": False,
            "dd088_root_or_status_used": False,
        },
        "independent_pr_parameters": pr_parameters,
        "bubble_solve_settings": asdict(settings),
        "jacobian": {
            "method": "uncolored_central_difference",
            "steps": list(JACOBIAN_STEPS),
            "coupling_tolerance": JACOBIAN_COUPLING_TOLERANCE,
        },
        "tolerances": {
            "jacobian_condition_hard_stop": JACOBIAN_CONDITION_HARD_STOP,
            "component_conservation_relative": (
                COMPONENT_CONSERVATION_TOLERANCE
            ),
            "energy_conservation_relative": ENERGY_CONSERVATION_TOLERANCE,
            "bubble_residual_inf": BUBBLE_RESIDUAL_TOLERANCE,
            "independent_pr_temperature_abs_F": (
                INDEPENDENT_PR_TEMPERATURE_TOLERANCE_F
            ),
            "independent_pr_vapor_max_abs": (
                INDEPENDENT_PR_COMPOSITION_TOLERANCE
            ),
            "tp_flash_vapor_fraction": TP_FLASH_VAPOR_FRACTION_TOLERANCE,
            "tp_flash_Kx_identity_max_abs": TP_FLASH_INTERNAL_TOLERANCE,
            "tp_flash_lever_rule_max_abs": TP_FLASH_INTERNAL_TOLERANCE,
        },
        "provider_call_restrictions": {
            "governing": [
                "dwsim.direct_imposed_phase_fugacity",
                "dwsim.declared_phase_enthalpy",
                "dwsim.declared_liquid_density",
            ],
            "diagnostic_only": ["dwsim.tp_flash"],
            "validation_only": [
                "independent.parameter_aligned_peng_robinson"
            ],
            "fallback_permitted": False,
            "mixed_basis_K_flash_z_gate_permitted": False,
            "direct_y_equals_flash_y_gate_present": False,
        },
        "hard_stops": [
            "rank_below_40",
            "local_bubble_rank_below_3",
            "condition_above_1e8",
            "unauthorized_provider_call",
            "mixed_basis_K_flash_z",
            "stable_vapor_condenser",
            "independent_pr_disagreement",
            "flash_internal_coherence_failure",
            "conservation_failure",
            "positive_condenser_duty",
            "fallback_or_projection",
        ],
        "implementation_sha256": implementation_hashes,
        "structural_registry_passed": bool(registry_audit.pass_gate),
        "preparation_provider_provenance": call_audit.report(),
        "full_live_column_residual_evaluation_attempted": False,
        "full_column_nonlinear_solve_attempted": False,
        "root_import_attempted": False,
        "mass_matrix_derivation_attempted": False,
        "dynamic_integration_attempted": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    contract_path.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    claimed = str(contract.pop("contract_payload_sha256", ""))
    actual = _payload_hash(contract)
    contract["contract_payload_sha256"] = claimed
    if contract.get("schema_id") != SCHEMA_ID:
        raise RuntimeError("DD-092 contract schema does not match")
    if claimed != actual:
        raise RuntimeError("DD-092 contract payload checksum does not match")
    return contract


def _verify_contract_is_committed(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    current = path.read_text(encoding="utf-8")
    if committed.replace("\r\n", "\n") != current.replace("\r\n", "\n"):
        raise RuntimeError("DD-092 contract differs from committed HEAD")
    relevant = (
        *CONTRACT_IMPLEMENTATION_PATHS,
        relative,
        Path(relative).with_suffix(".md").as_posix(),
    )
    if _git("status", "--short", "--", *relevant):
        raise RuntimeError("DD-092 contract implementation has tracked changes")
    return _git("rev-parse", "HEAD")


def _verify_implementation_hashes(contract: Mapping[str, Any]) -> None:
    for relative, expected in contract["implementation_sha256"].items():
        actual = _sha256_file(ROOT / relative)
        if actual != expected:
            raise RuntimeError(
                f"DD-092 implementation changed after preparation: {relative}"
            )


def _independent_provider(contract: Mapping[str, Any]) -> IndependentPengRobinsonProvider:
    raw = contract["independent_pr_parameters"]
    return IndependentPengRobinsonProvider(
        PengRobinsonParameters(
            critical_temperature_K=np.asarray(
                raw["critical_temperature_K"], dtype=float
            ),
            critical_pressure_Pa=np.asarray(
                raw["critical_pressure_Pa"], dtype=float
            ),
            acentric_factor=np.asarray(raw["acentric_factor"], dtype=float),
            binary_interaction=np.asarray(
                raw["binary_interaction"], dtype=float
            ),
        )
    )


def _jacobian_payload(audit: Any) -> dict[str, Any]:
    return {
        "step": float(audit.step),
        "rank": int(audit.rank),
        "condition": float(audit.condition),
        "singular_values": _float_list(audit.singular_values),
        "zero_rows": list(audit.zero_rows),
        "zero_columns": list(audit.zero_columns),
        "unexpected_couplings": list(audit.unexpected_couplings),
        "bubble_rank": int(audit.bubble_rank),
        "bubble_singular_values": _float_list(audit.bubble_singular_values),
        "bubble_zero_rows": list(audit.bubble_zero_rows),
        "bubble_zero_columns": list(audit.bubble_zero_columns),
    }


def _dominant_rows(evaluation: Any, count: int = 10) -> list[dict[str, Any]]:
    order = np.argsort(np.abs(evaluation.scaled))[::-1][:count]
    return [
        {
            "name": evaluation.rows[index].name,
            "block": evaluation.rows[index].block,
            "raw": float(evaluation.raw[index]),
            "scaled": float(evaluation.scaled[index]),
        }
        for index in order
    ]


def _json_diagnostic(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: (
            _float_list(value)
            if isinstance(value, np.ndarray)
            else bool(value)
            if isinstance(value, np.bool_)
            else float(value)
            if isinstance(value, np.floating)
            else value
        )
        for key, value in values.items()
    }


def _state_report(
    spec: OperatingSpec,
    evaluation: Any,
    jacobians: Sequence[Any],
    flash: Mapping[str, Any],
    independent_bubble: Any,
) -> dict[str, Any]:
    state = evaluation.state
    properties = evaluation.properties
    heights = [
        float(properties.liquid_height_ft[VOLUME_IDS.index(volume)])
        for volume in HYDRAULIC_VOLUME_IDS
    ]
    spacings = [
        float(geometry.tray_spacing_ft) for geometry in spec.hydraulic_geometry
    ]
    bubble_rows = [
        index
        for index, row in enumerate(evaluation.rows)
        if row.block == "condenser_bubble_fugacity"
    ]
    bubble_residual = float(
        np.max(np.abs(evaluation.raw[np.asarray(bubble_rows, dtype=int)]))
    )
    independent_temperature = float(
        independent_bubble.temperature_F - state.temperature_F[0]
    )
    independent_vapor = float(
        np.max(
            np.abs(
                independent_bubble.vapor_mole_fraction
                - state.bubble_vapor_mole_fraction
            )
        )
    )
    jacobian_pass = all(
        item.rank == 40
        and item.condition < JACOBIAN_CONDITION_HARD_STOP
        and item.bubble_rank == 3
        and not item.zero_rows
        and not item.zero_columns
        and not item.unexpected_couplings
        and not item.bubble_zero_rows
        and not item.bubble_zero_columns
        and np.all(np.isfinite(item.singular_values))
        and np.all(np.isfinite(item.bubble_singular_values))
        for item in jacobians
    )
    conservation_pass = bool(
        evaluation.component_telescoping_relative_error
        < COMPONENT_CONSERVATION_TOLERANCE
        and evaluation.energy_telescoping_relative_error
        < ENERGY_CONSERVATION_TOLERANCE
    )
    phase_pass = bool(
        not flash["stable_vapor"]
        and float(flash["vapor_fraction"])
        <= TP_FLASH_VAPOR_FRACTION_TOLERANCE
        and float(flash["flash_Kx_identity_max_abs"])
        < TP_FLASH_INTERNAL_TOLERANCE
        and float(flash["lever_rule_closure_max_abs"])
        < TP_FLASH_INTERNAL_TOLERANCE
    )
    independent_pass = bool(
        abs(independent_temperature)
        < INDEPENDENT_PR_TEMPERATURE_TOLERANCE_F
        and independent_vapor < INDEPENDENT_PR_COMPOSITION_TOLERANCE
        and independent_bubble.success
    )
    physical_pass = bool(
        np.all(np.isfinite(evaluation.raw))
        and np.all(np.isfinite(properties.liquid_enthalpy_BTU_lbmol))
        and np.all(np.isfinite(properties.vapor_enthalpy_BTU_lbmol[1:]))
        and np.all(np.isfinite(properties.liquid_density_lbmol_ft3[1:4]))
        and np.all(properties.liquid_density_lbmol_ft3[1:4] > 0.0)
        and np.all(state.liquid_moles_lbmol > 0.0)
        and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(state.vapor_flow_lbmolph > 0.0)
        and state.distillate_lbmolph > 0.0
        and state.bottoms_lbmolph > 0.0
        and state.condenser_duty_BTUph < 0.0
        and np.all(np.isfinite(state.temperature_F))
        and np.all(state.liquid_mole_fraction > 0.0)
        and np.all(state.vapor_mole_fraction > 0.0)
        and np.all(state.bubble_vapor_mole_fraction > 0.0)
        and np.allclose(np.sum(state.liquid_mole_fraction, axis=1), 1.0)
        and np.allclose(np.sum(state.vapor_mole_fraction, axis=1), 1.0)
        and np.isclose(np.sum(state.bubble_vapor_mole_fraction), 1.0)
        and all(height < spacing for height, spacing in zip(heights, spacings))
    )
    pass_gate = bool(
        jacobian_pass
        and conservation_pass
        and phase_pass
        and independent_pass
        and physical_pass
        and bubble_residual < BUBBLE_RESIDUAL_TOLERANCE
        and not evaluation.clipping_or_projection_used
        and not evaluation.property_fallback_used
    )
    return {
        "pass_gate": pass_gate,
        "scaled_residual_inf_norm_diagnostic": float(
            np.max(np.abs(evaluation.scaled))
        ),
        "raw_residual_inf_norm_diagnostic": float(
            np.max(np.abs(evaluation.raw))
        ),
        "dominant_residuals": _dominant_rows(evaluation),
        "bubble_residual_inf_norm": bubble_residual,
        "component_telescoping_error_lbmolph": _float_list(
            evaluation.component_telescoping_error_lbmolph
        ),
        "component_telescoping_relative_error": float(
            evaluation.component_telescoping_relative_error
        ),
        "energy_telescoping_error_BTUph": float(
            evaluation.energy_telescoping_error_BTUph
        ),
        "energy_telescoping_relative_error": float(
            evaluation.energy_telescoping_relative_error
        ),
        "condenser_duty_BTUph": float(state.condenser_duty_BTUph),
        "liquid_height_ft": heights,
        "tray_spacing_ft": spacings,
        "physical_pass": physical_pass,
        "conservation_pass": conservation_pass,
        "jacobian_pass": jacobian_pass,
        "tp_flash_diagnostic": _json_diagnostic(flash),
        "tp_flash_pass": phase_pass,
        "independent_pr_validation": {
            "temperature_difference_F": independent_temperature,
            "vapor_max_abs": independent_vapor,
            "residual_inf_norm": float(independent_bubble.residual_inf_norm),
            "pass": independent_pass,
        },
        "clipping_or_projection_used": bool(
            evaluation.clipping_or_projection_used
        ),
        "property_fallback_used": bool(evaluation.property_fallback_used),
        "jacobians": [_jacobian_payload(item) for item in jacobians],
    }


def _result_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# DD-092 Core V3 Provider-Governed Numerical Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Contract commit: `{report['contract_commit']}`",
        f"- Structural rank: `{report['structural_rank']}/40`",
        f"- Provider provenance pass: "
        f"`{report['provider_provenance']['pass']}`",
        f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
        "- Full nonlinear solve attempted: `False`",
        "- Dynamic integration attempted: `False`",
        "",
        "## Numerical States",
        "",
        "| State | Residual inf (diagnostic) | Rank h / h/2 | Bubble rank | "
        "Worst condition | Beta | Pass |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, state in report["states"].items():
        jac = state["jacobians"]
        lines.append(
            f"| {name} | "
            f"{state['scaled_residual_inf_norm_diagnostic']:.6e} | "
            f"{jac[0]['rank']} / {jac[1]['rank']} | "
            f"{jac[0]['bubble_rank']} / {jac[1]['bubble_rank']} | "
            f"{max(jac[0]['condition'], jac[1]['condition']):.6e} | "
            f"{state['tp_flash_diagnostic']['vapor_fraction']:.6e} | "
            f"{state['pass_gate']} |"
        )
    lines.extend(
        (
            "",
            "## Authorization",
            "",
            str(report["authorization"]),
            "",
        )
    )
    return "\n".join(lines)


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract_commit = _verify_contract_is_committed(contract_path)
    contract = _load_contract(contract_path)
    _verify_implementation_hashes(contract)
    workbook = Path(contract["workbook"])
    if _sha256_file(workbook) != contract["workbook_sha256"]:
        raise RuntimeError("DD-092 workbook differs from the frozen contract")
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    provider = _provider(column, str(contract["property_package"]))
    source = contract["source_mapping"]
    if list(column.components_excel) != source["component_names"]:
        raise RuntimeError("DD-092 live components differ from the contract")
    spec = _spec_from_source(
        source, float(contract["operating_spec"]["feed_enthalpy_BTUph"])
    )
    reference = _reference_from_payload(contract["reference"])
    layout = coordinate_layout(spec)
    rows = residual_rows(spec)
    if list(layout.names) != contract["coordinate_names"]:
        raise RuntimeError("DD-092 coordinate names differ from the contract")
    if [row.name for row in rows] != contract["residual_names"]:
        raise RuntimeError("DD-092 residual names differ from the contract")
    scales = np.asarray(contract["fixed_residual_scales"], dtype=float)
    pattern = structural_pattern(spec)
    structural_rank_value = int(structural_rank(csr_matrix(pattern)))
    registry = audit_provider_governed_registry(
        build_provider_governed_registry(spec.component_names)
    )
    q_rows = np.flatnonzero(pattern[:, layout.condenser_duty]).tolist()
    drum_energy_index = next(
        index
        for index, row in enumerate(rows)
        if row.name == "energy_balance[reflux_drum]"
    )
    ownership_pass = bool(
        structural_rank_value == 40
        and registry.pass_gate
        and q_rows == [drum_energy_index]
    )
    independent = _independent_provider(contract)
    call_audit = ProviderCallAudit()
    settings = BubbleSolveSettings(**contract["bubble_solve_settings"])
    started = time.perf_counter()
    states: dict[str, Any] = {}
    for state_id, values in contract["states"].items():
        point = np.asarray(values, dtype=float)
        evaluation = evaluate_residual(
            spec,
            reference,
            provider,
            call_audit,
            point,
            fixed_scales=scales,
            state_id=state_id,
            evaluation_kind="residual",
        )
        jacobians = [
            audit_numerical_jacobian(
                spec,
                reference,
                provider,
                call_audit,
                point,
                fixed_scales=scales,
                state_id=state_id,
                step=float(step),
                coupling_tolerance=JACOBIAN_COUPLING_TOLERANCE,
            )
            for step in JACOBIAN_STEPS
        ]
        flash = tp_flash_diagnostics(
            provider,
            call_audit,
            temperature_F=float(evaluation.state.temperature_F[0]),
            pressure_psia=float(spec.pressure_psia[0]),
            overall_z=evaluation.state.liquid_mole_fraction[0],
            state_id=state_id,
        )
        independent_bubble = solve_local_bubble(
            independent,
            call_audit,
            pressure_psia=float(spec.pressure_psia[0]),
            liquid_x=evaluation.state.liquid_mole_fraction[0],
            temperature_guess_F=float(evaluation.state.temperature_F[0]),
            vapor_guess=evaluation.state.bubble_vapor_mole_fraction,
            state_id=state_id,
            evaluation_kind="validation",
            independent=True,
            settings=settings,
        )
        states[state_id] = _state_report(
            spec,
            evaluation,
            jacobians,
            flash,
            independent_bubble,
        )
    provenance = call_audit.report()
    passed = bool(
        ownership_pass
        and provenance["pass"]
        and all(state["pass_gate"] for state in states.values())
    )
    report: dict[str, Any] = {
        "schema_id": RESULT_SCHEMA_ID,
        "classification": (
            "dd092_core_v3_provider_governed_numerical_passed"
            if passed
            else "dd092_core_v3_provider_governed_numerical_failed"
        ),
        "decision": (
            "authorize_drafting_one_bounded_three_start_core_v3_root_contract"
            if passed
            else "stop_core_v3_before_root_campaign"
        ),
        "authorization": (
            "DD-092 passes. One bounded three-start Core V3 steady-root "
            "campaign may be drafted and committed under a separate frozen "
            "contract. Execution, mass-matrix work, and dynamics remain "
            "unauthorized."
            if passed
            else "DD-092 met a frozen hard stop. Do not substitute providers, "
            "change tolerances, import the DD-088 root, solve the column, or "
            "begin dynamic work."
        ),
        "contract_path": str(contract_path.resolve()),
        "contract_commit": contract_commit,
        "contract_payload_sha256": contract["contract_payload_sha256"],
        "workbook": str(workbook.resolve()),
        "workbook_sha256": contract["workbook_sha256"],
        "property_package": contract["property_package"],
        "unknown_count": len(layout.names),
        "residual_count": len(rows),
        "structural_rank": structural_rank_value,
        "ownership": {
            "q_c_residual_rows_zero_based": q_rows,
            "drum_energy_row_zero_based": drum_energy_index,
            "q_c_only_in_drum_energy": q_rows == [drum_energy_index],
            "q_c_external_energy_closure_occurrences": 1,
            "registry_pass": bool(registry.pass_gate),
            "pass": ownership_pass,
        },
        "states": states,
        "provider_provenance": provenance,
        "mixed_basis_K_flash_z_evaluated": False,
        "direct_y_equals_flash_y_gate_evaluated": False,
        "interface_fallback_permitted": False,
        "full_column_nonlinear_solve_attempted": False,
        "root_import_attempted": False,
        "mass_matrix_derivation_attempted": False,
        "dynamic_integration_attempted": False,
        "wall_clock_sec": float(time.perf_counter() - started),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(
        _result_markdown(report), encoding="utf-8"
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path("sandbox/mini8/input/distillation_column_template_8stage.xlsx"),
    )
    parser.add_argument("--property-package", default="pr")
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(
            "logs/dd092_core_v3_provider_governed_numerical_contract_20260719.json"
        ),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path(
            "logs/dd092_core_v3_provider_governed_numerical_20260719"
        ),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare_only:
        output = prepare(
            args.workbook.resolve(),
            args.property_package,
            args.contract,
        )
        summary = {
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "state_lengths": {
                name: len(values) for name, values in output["states"].items()
            },
            "full_live_column_residual_evaluation_attempted": False,
        }
        exit_code = 0
    else:
        output = execute(args.contract, args.out_prefix)
        summary = {
            "classification": output["classification"],
            "decision": output["decision"],
            "wall_clock_sec": output["wall_clock_sec"],
        }
        exit_code = (
            0
            if output["classification"]
            == "dd092_core_v3_provider_governed_numerical_passed"
            else 2
        )
    print(json.dumps(summary, indent=2))
    raise SystemExit(exit_code)
