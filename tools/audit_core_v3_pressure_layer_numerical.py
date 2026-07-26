#!/usr/bin/env python
"""Prepare or execute the frozen DD-102 Core V3 pressure-layer audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    audit_pressure_layer_contract,
    build_pressure_layer_contract,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
    audit_pressure_layer_jacobian,
    evaluate_pressure_layer_residual,
    pressure_profile_from_coordinates,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    VAPOR_LINKS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    HydraulicGeometry,
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SCHEMA_ID = "dd102-core-v3-pressure-layer-numerical-contract-v1"
RESULT_SCHEMA_ID = "dd102-core-v3-pressure-layer-numerical-result-v1"
DEFAULT_DD101 = Path("logs/dd101_core_v3_pressure_layer_20260725.json")
DEFAULT_DD096 = Path("logs/dd096_core_v3_dynamic_dae_numerical_20260725.json")
DEFAULT_DD094 = Path("logs/dd094_core_v3_steady_root_20260725.json")
DEFAULT_SOURCE = Path(
    "logs/dd092_core_v3_provider_governed_numerical_contract_20260719.json"
)
DEFAULT_CONTRACT = Path(
    "logs/dd102_core_v3_pressure_layer_numerical_contract_20260725.json"
)
DEFAULT_CONTRACT_DOC = Path(
    "docs/dd_102_core_v3_pressure_layer_numerical_contract_20260725.md"
)
DEFAULT_RESULT = Path(
    "logs/dd102_core_v3_pressure_layer_numerical_20260725.json"
)
DEFAULT_RESULT_DOC = Path(
    "docs/dd_102_core_v3_pressure_layer_numerical_20260725.md"
)

JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
PRESSURE_PERTURBATION_COORDINATES = (0.002, 0.004, 0.006, 0.008)
PRESSURE_COORDINATE_SCALE_PSIA = 10.0
PRESSURE_RESIDUAL_SCALE_PSIA = 1.0
COUPLING_TOLERANCE = 1.0e-7
CONDITION_LIMIT = 1.0e8
SPECTRUM_RELATIVE_CHANGE_LIMIT = 0.25
BASE_ROOT_RESIDUAL_LIMIT = 1.0e-8
COMPONENT_CONSERVATION_LIMIT = 1.0e-12
ENERGY_CONSERVATION_LIMIT = 1.0e-10
PROVIDER_CALL_LIMIT = 10_000
WALL_CLOCK_LIMIT_SEC = 180.0

IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/pressure_layer_contract_v1.py",
    "src/dynamic_distillation/core_v3/pressure_layer_numerical_v1.py",
    "tools/audit_core_v3_pressure_layer_numerical.py",
    "tests/test_core_v3_provider_call_audit_v1.py",
    "tests/test_core_v3_pressure_layer_contract_v1.py",
    "tests/test_core_v3_pressure_layer_numerical_v1.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


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
    )


def _reference(payload: Mapping[str, Any]) -> NumericalReference:
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


def _state(payload: Mapping[str, Any]) -> PhysicalState:
    return PhysicalState(
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
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_BTUph=float(payload["condenser_duty_BTUph"]),
    )


def _provider(workbook: Path, package: str) -> ThermoProviderV1:
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    return ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=package,
        silence_backend_console=True,
    )


def _pressure_geometry(column: Any, source: Mapping[str, Any]) -> list[dict[str, float]]:
    roles = tuple(source["roles"])
    stages = tuple(int(value) - 1 for value in source["source_stage_1based"])
    geometry = column.geometry
    if geometry is None:
        raise RuntimeError("DD-102 requires source tray geometry")
    result: list[dict[str, float]] = []
    for source_volume, _destination, _symbol in VAPOR_LINKS:
        stage = stages[roles.index(source_volume)]
        result.append(
            asdict(
                PressureLinkGeometry(
                    active_area_ft2=float(
                        geometry.active_area_ft2_per_stage[stage]
                    ),
                    tray_area_ft2=float(geometry.area_ft2_per_stage[stage]),
                    weir_height_in=float(
                        geometry.weir_height_in_per_stage[stage]
                    ),
                )
            )
        )
    return result


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-102 Frozen Core V3 Pressure-Layer Numerical Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- System: `42 x 42` dynamic leading ledger with algebraic pressure",
            "- States: accepted root pressure profile and one fixed ordered perturbation",
            "- Jacobian steps: `1e-5`, `5e-6`",
            "- Jacobian method: full central difference",
            f"- Provider-call ceiling: `{payload['provider_call_limit']}`",
            "- Live property evaluation during preparation: `False`",
            "- Nonlinear solve during preparation: `False`",
            "- Dynamic integration during preparation: `False`",
            "",
            "## Decision rule",
            "",
            "Both states must remain physical and conservative. All four Jacobians "
            "must be rank `42`, satisfy the fixed condition and spectrum gates, "
            "match the registered coupling pattern, and use only direct declared "
            "DWSIM properties. The pressure residual magnitude is diagnostic and "
            "will be reported without tuning.",
            "",
            "A pass authorizes only one separately frozen nonlinear pressure-layer "
            "steady-root contract. It does not authorize integration, vapor holdup, "
            "or controllers.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# DD-102 Core V3 Pressure-Layer Numerical Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
        f"- Provider calls: `{payload['provider_provenance']['total_calls']}`",
        f"- Worst condition: `{payload['worst_condition']:.6e}`",
        f"- Worst spectrum change: `{payload['worst_spectrum_change']:.6e}`",
        "",
        "## State results",
        "",
    ]
    for state in payload["states"]:
        lines.extend(
            (
                f"### {state['name']}",
                "",
                f"- Pressure, psia: `{state['pressure_psia']}`",
                f"- Pressure residual, psi: `{state['pressure_residual_psia']}`",
                f"- Liquid-head drop, psi: `{state['liquid_head_drop_psia']}`",
                f"- Dry-tray drop, psi: `{state['dry_tray_drop_psia']}`",
                f"- Vapor Z: `{state['vapor_compressibility_factor']}`",
                f"- Jacobian ranks: `{[item['rank'] for item in state['jacobians']]}`",
                "",
            )
        )
    return "\n".join(lines)


def prepare(
    dd101_path: Path,
    dd096_path: Path,
    dd094_path: Path,
    source_path: Path,
    contract_path: Path,
    contract_doc: Path,
) -> dict[str, Any]:
    dd101 = _load(dd101_path)
    dd096 = _load(dd096_path)
    dd094 = _load(dd094_path)
    source = _load(source_path)
    if (
        not dd101["audit"]["pass_gate"]
        or not dd096["pass"]
        or not dd094["campaign_pass"]
    ):
        raise RuntimeError("DD-102 requires accepted DD-101, DD-096, and DD-094")
    workbook = Path(source["workbook"])
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    dry_tray = float(column.specs_raw["Dry Tray K"])
    if not np.isfinite(dry_tray) or dry_tray <= 0.0:
        raise RuntimeError("DD-102 requires a positive dry-tray coefficient")
    pressure_reference = _vector(source["source_mapping"]["pressure_psia"])
    perturbation = _vector(PRESSURE_PERTURBATION_COORDINATES)
    perturbed_pressure = np.asarray(pressure_reference, dtype=float)
    perturbed_pressure[1:] += PRESSURE_COORDINATE_SCALE_PSIA * np.asarray(
        perturbation
    )
    if np.any(np.diff(perturbed_pressure) <= 0.0):
        raise RuntimeError("DD-102 frozen perturbation is not pressure ordered")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd101_path": str(dd101_path).replace("\\", "/"),
        "dd101_sha256": _sha256(ROOT / dd101_path),
        "dd096_path": str(dd096_path).replace("\\", "/"),
        "dd096_sha256": _sha256(ROOT / dd096_path),
        "dd094_path": str(dd094_path).replace("\\", "/"),
        "dd094_sha256": _sha256(ROOT / dd094_path),
        "source_path": str(source_path).replace("\\", "/"),
        "source_sha256": _sha256(ROOT / source_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": dd094["starts"]["canonical_core_v3_seed"]
        ["endpoint_evaluation"]["state"],
        "dynamic_inventory_lbmol": dd096.get(
            "accepted_root_inventory_lbmol",
            [
                [
                    float(total) * float(fraction)
                    for fraction in composition
                ]
                for total, composition in zip(
                    dd094["starts"]["canonical_core_v3_seed"]
                    ["endpoint_evaluation"]["state"]["liquid_moles_lbmol"],
                    dd094["starts"]["canonical_core_v3_seed"]
                    ["endpoint_evaluation"]["state"]["liquid_mole_fraction"],
                )
            ],
        ),
        "root_base_algebraic_coordinates": dd096.get(
            "accepted_root_algebraic_coordinates",
            _load(Path("logs/dd096_core_v3_dynamic_dae_numerical_contract_20260725.json"))[
                "accepted_root_algebraic_coordinates"
            ],
        ),
        "storage_gradient_BTU_lbmol": dd096["storage_gradient"]["steps"][0][
            "gradient_BTU_lbmol"
        ],
        "fixed_steady_residual_scales": source["fixed_residual_scales"],
        "pressure_reference_psia": pressure_reference,
        "pressure_coordinate_scale_psia": PRESSURE_COORDINATE_SCALE_PSIA,
        "pressure_residual_scale_psia": PRESSURE_RESIDUAL_SCALE_PSIA,
        "dry_tray_pressure_drop_coefficient": dry_tray,
        "pressure_link_geometry": _pressure_geometry(
            column, source["source_mapping"]
        ),
        "states": [
            {"name": "accepted_root_profile", "pressure_coordinates": [0.0] * 4},
            {
                "name": "bounded_ordered_pressure_perturbation",
                "pressure_coordinates": perturbation,
            },
        ],
        "jacobian_steps": list(JACOBIAN_STEPS),
        "coupling_tolerance": COUPLING_TOLERANCE,
        "condition_limit": CONDITION_LIMIT,
        "spectrum_relative_change_limit": SPECTRUM_RELATIVE_CHANGE_LIMIT,
        "base_root_residual_limit": BASE_ROOT_RESIDUAL_LIMIT,
        "component_conservation_limit": COMPONENT_CONSERVATION_LIMIT,
        "energy_conservation_limit": ENERGY_CONSERVATION_LIMIT,
        "provider_call_limit": PROVIDER_CALL_LIMIT,
        "wall_clock_limit_sec": WALL_CLOCK_LIMIT_SEC,
        "required_rank": 42,
        "hard_stops": [
            "either pressure state is non-positive or unordered",
            "any declared density or vapor Z is unavailable or non-physical",
            "any Jacobian loses rank, exceeds condition, or changes spectrum",
            "an off-registry coupling or zero row/column appears",
            "component or energy conservation fails",
            "provider ownership, no-fallback, call-count, or wall-time gate fails",
            "any nonlinear solve or dynamic integration is attempted",
        ],
        "implementation_sha256": {
            path: _sha256(ROOT / path) for path in IMPLEMENTATION_PATHS
        },
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    (ROOT / contract_path).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (ROOT / contract_doc).write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify_contract(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-102 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha256(ROOT / path) != expected:
            raise RuntimeError(f"DD-102 implementation changed: {path}")
    if _sha256(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-102 workbook changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-102 result already exists; rerun is prohibited")
    _git("ls-files", "--error-unmatch", str(contract_path))


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify_contract(payload, contract_path, result_path)
    source = payload["source_mapping"]
    spec = _spec(source, float(payload["operating_spec"]["feed_enthalpy_BTUph"]))
    reference = _reference(payload["reference"])
    state = _state(payload["accepted_root_state"])
    contract = build_pressure_layer_contract(spec.component_names)
    structural = audit_pressure_layer_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-102 structural prerequisite changed")
    provider = _provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    component_mw = call_audit.component_molecular_weights(
        provider,
        caller="pressure_layer_fixed_parameters",
        state_id="dd102",
        evaluation_kind="preparation",
    )
    numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(
            payload["pressure_reference_psia"], dtype=float
        ),
        pressure_coordinate_scale_psia=float(
            payload["pressure_coordinate_scale_psia"]
        ),
        pressure_residual_scale_psia=float(payload["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(
            payload["dry_tray_pressure_drop_coefficient"]
        ),
        component_mw_lbm_per_lbmol=component_mw,
        link_geometry=tuple(
            PressureLinkGeometry(**item)
            for item in payload["pressure_link_geometry"]
        ),
    )
    inventory = np.asarray(payload["dynamic_inventory_lbmol"], dtype=float)
    algebraic = np.asarray(
        payload["root_base_algebraic_coordinates"], dtype=float
    )
    storage = np.asarray(payload["storage_gradient_BTU_lbmol"], dtype=float)
    started = time.perf_counter()
    state_results = []
    all_jacobians = []
    for state_spec in payload["states"]:
        name = str(state_spec["name"])
        pressure_coordinates = np.asarray(
            state_spec["pressure_coordinates"], dtype=float
        )
        baseline = evaluate_pressure_layer_residual(
            contract,
            spec,
            reference,
            state,
            provider,
            call_audit,
            inventory_lbmol=inventory,
            rate_coordinates=np.zeros(len(contract.derivative_variables)),
            base_algebraic_coordinates=algebraic,
            pressure_coordinates=pressure_coordinates,
            storage_gradient_BTU_lbmol=storage,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            numerical=numerical,
            state_id=f"dd102:{name}:residual",
            evaluation_kind="residual",
        )
        jacobians = [
            audit_pressure_layer_jacobian(
                contract,
                spec,
                reference,
                state,
                provider,
                call_audit,
                inventory_lbmol=inventory,
                root_base_algebraic_coordinates=algebraic,
                pressure_coordinates=pressure_coordinates,
                storage_gradient_BTU_lbmol=storage,
                fixed_steady_scales=payload["fixed_steady_residual_scales"],
                numerical=numerical,
                step=float(step),
                coupling_tolerance=float(payload["coupling_tolerance"]),
                state_id=f"dd102:{name}:jac:{step:g}",
            )
            for step in payload["jacobian_steps"]
        ]
        spectrum_change = _spectrum_change(
            jacobians[0].singular_values, jacobians[1].singular_values
        )
        all_jacobians.extend(jacobians)
        steady = baseline.base_evaluation.steady_evaluation
        state_results.append(
            {
                "name": name,
                "pressure_coordinates": _vector(pressure_coordinates),
                "pressure_psia": _vector(baseline.pressure_psia),
                "base_scaled_residual_inf_norm": float(
                    np.max(np.abs(baseline.scaled[:38]))
                ),
                "full_scaled_residual_inf_norm": float(
                    np.max(np.abs(baseline.scaled))
                ),
                "pressure_residual_psia": _vector(
                    baseline.pressure_drop.raw_residual_psia
                ),
                "liquid_head_drop_psia": _vector(
                    baseline.pressure_drop.liquid_head_drop_psia
                ),
                "dry_tray_drop_psia": _vector(
                    baseline.pressure_drop.dry_tray_drop_psia
                ),
                "over_weir_head_ft": _vector(
                    baseline.pressure_drop.over_weir_head_ft
                ),
                "vapor_compressibility_factor": _vector(
                    baseline.pressure_drop.vapor_compressibility_factor
                ),
                "component_conservation_relative_error": float(
                    steady.component_telescoping_relative_error
                ),
                "energy_conservation_relative_error": float(
                    steady.energy_telescoping_relative_error
                ),
                "spectrum_relative_change": spectrum_change,
                "jacobians": [
                    {
                        "step": item.step,
                        "rank": item.rank,
                        "condition": item.condition,
                        "singular_values": _vector(item.singular_values),
                        "zero_rows": list(item.zero_rows),
                        "zero_columns": list(item.zero_columns),
                        "unexpected_couplings": list(item.unexpected_couplings),
                        "matrix": _rows(item.matrix),
                    }
                    for item in jacobians
                ],
            }
        )
    elapsed = time.perf_counter() - started
    provider_report = call_audit.report()
    root_state = state_results[0]
    perturb_state = state_results[1]
    pressure_response = float(
        np.max(
            np.abs(
                np.asarray(perturb_state["pressure_residual_psia"])
                - np.asarray(root_state["pressure_residual_psia"])
            )
        )
    )
    gates = {
        "structural": structural.pass_gate,
        "root_base_residual": root_state["base_scaled_residual_inf_norm"]
        < float(payload["base_root_residual_limit"]),
        "finite_pressure_residuals": all(
            np.all(np.isfinite(item["pressure_residual_psia"]))
            for item in state_results
        ),
        "positive_pressure_order": all(
            np.all(np.diff(item["pressure_psia"]) > 0.0)
            and np.all(np.asarray(item["pressure_psia"]) > 0.0)
            for item in state_results
        ),
        "positive_pressure_terms": all(
            np.all(np.asarray(item["liquid_head_drop_psia"]) > 0.0)
            and np.all(np.asarray(item["dry_tray_drop_psia"]) > 0.0)
            and np.all(np.asarray(item["vapor_compressibility_factor"]) > 0.0)
            for item in state_results
        ),
        "pressure_perturbation_response": pressure_response > 1.0e-8,
        "rank": all(
            item.rank == int(payload["required_rank"]) for item in all_jacobians
        ),
        "condition": all(
            item.condition < float(payload["condition_limit"])
            for item in all_jacobians
        ),
        "registered_structure": all(
            not item.zero_rows
            and not item.zero_columns
            and not item.unexpected_couplings
            for item in all_jacobians
        ),
        "spectrum_stable": all(
            item["spectrum_relative_change"]
            < float(payload["spectrum_relative_change_limit"])
            for item in state_results
        ),
        "component_conservation": all(
            item["component_conservation_relative_error"]
            < float(payload["component_conservation_limit"])
            for item in state_results
        ),
        "energy_conservation": all(
            item["energy_conservation_relative_error"]
            < float(payload["energy_conservation_limit"])
            for item in state_results
        ),
        "provider_provenance": bool(provider_report["pass"]),
        "provider_call_limit": int(provider_report["total_calls"])
        < int(payload["provider_call_limit"]),
        "wall_clock_limit": elapsed < float(payload["wall_clock_limit_sec"]),
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA_ID,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "dd102_core_v3_pressure_layer_numerical_passed"
            if passed
            else "dd102_core_v3_pressure_layer_numerical_failed"
        ),
        "decision": (
            "authorize_one_frozen_pressure_layer_steady_root_contract"
            if passed
            else "stop_pressure_layer_before_nonlinear_solve"
        ),
        "wall_clock_sec": float(elapsed),
        "states": state_results,
        "pressure_perturbation_response_psia": pressure_response,
        "worst_condition": max(item.condition for item in all_jacobians),
        "worst_spectrum_change": max(
            item["spectrum_relative_change"] for item in state_results
        ),
        "provider_provenance": provider_report,
        "gates": gates,
        "pass": passed,
        "campaign_executed_once": True,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
    }
    (ROOT / result_path).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (ROOT / result_doc).write_text(
        _result_markdown(result), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd101", type=Path, default=DEFAULT_DD101)
    parser.add_argument("--dd096", type=Path, default=DEFAULT_DD096)
    parser.add_argument("--dd094", type=Path, default=DEFAULT_DD094)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-doc", type=Path, default=DEFAULT_CONTRACT_DOC)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--result-doc", type=Path, default=DEFAULT_RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.dd101,
            args.dd096,
            args.dd094,
            args.source,
            args.contract,
            args.contract_doc,
        )
    else:
        output = execute(args.contract, args.result, args.result_doc)
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
