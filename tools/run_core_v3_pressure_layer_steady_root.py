#!/usr/bin/env python
"""Prepare or execute the frozen DD-103 pressure-layer steady-root campaign."""

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
TOOLS = ROOT / "tools"
for path in (SRC, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_pressure_layer_numerical as dd102
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_indices,
)
from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    audit_pressure_layer_contract,
    build_pressure_layer_contract,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.pressure_layer_steady_root_v1 import (
    PressureRootSettings,
    algebraic_sparsity_pattern,
    audit_algebraic_jacobian,
    solve_pressure_layer_root,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VOLUME_IDS
from dynamic_distillation.core_v3.provider_governed_steady_root_v1 import (
    SteadyRootSettings,
    physical_bounds,
)


SCHEMA_ID = "dd103-core-v3-pressure-layer-steady-root-contract-v1"
RESULT_SCHEMA_ID = "dd103-core-v3-pressure-layer-steady-root-result-v1"
DEFAULT_DD102_RESULT = Path(
    "logs/dd102_core_v3_pressure_layer_numerical_20260725.json"
)
DEFAULT_DD102_CONTRACT = Path(
    "logs/dd102_core_v3_pressure_layer_numerical_contract_20260725.json"
)
DEFAULT_CONTRACT = Path(
    "logs/dd103_core_v3_pressure_layer_steady_root_contract_20260726.json"
)
DEFAULT_CONTRACT_DOC = Path(
    "docs/dd_103_core_v3_pressure_layer_steady_root_contract_20260726.md"
)
DEFAULT_RESULT = Path(
    "logs/dd103_core_v3_pressure_layer_steady_root_20260726.json"
)
DEFAULT_RESULT_DOC = Path(
    "docs/dd_103_core_v3_pressure_layer_steady_root_20260726.md"
)

ENDPOINT_JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_LIMIT = 1.0e-8
COMMON_ROOT_LIMIT = 1.0e-7
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.25
COUPLING_TOLERANCE = 1.0e-7
ACTIVE_BOUND_TOLERANCE = 1.0e-6
COMPONENT_CONSERVATION_LIMIT = 1.0e-12
ENERGY_CONSERVATION_LIMIT = 1.0e-10
PROVIDER_CALL_LIMIT = 100_000
WALL_CLOCK_LIMIT_SEC = 180.0
MAX_PRESSURE_PSIA = 245.0
MIN_PRESSURE_ABOVE_TOP_PSIA = 1.0e-3

IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/pressure_layer_contract_v1.py",
    "src/dynamic_distillation/core_v3/pressure_layer_numerical_v1.py",
    "src/dynamic_distillation/core_v3/pressure_layer_steady_root_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tools/run_core_v3_pressure_layer_steady_root.py",
    "tests/test_core_v3_pressure_layer_numerical_v1.py",
    "tests/test_core_v3_pressure_layer_steady_root_v1.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
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


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def _dry_terminal_geometry(items: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    geometry = [dict(item) for item in items]
    if len(geometry) != 4:
        raise RuntimeError("DD-103 requires four pressure-link geometries")
    for index, item in enumerate(geometry):
        item["include_liquid_head"] = index != 0
    return geometry


def _projected_pressure_profile(dd102_result: Mapping[str, Any]) -> np.ndarray:
    root = dd102_result["states"][0]
    liquid = np.asarray(root["liquid_head_drop_psia"], dtype=float)
    dry = np.asarray(root["dry_tray_drop_psia"], dtype=float)
    drops = liquid + dry
    drops[0] = dry[0]
    top = float(root["pressure_psia"][0])
    pressure = np.empty(5, dtype=float)
    pressure[0] = top
    pressure[1] = pressure[0] + drops[3]
    pressure[2] = pressure[1] + drops[2]
    pressure[3] = pressure[2] + drops[1]
    pressure[4] = pressure[3] + drops[0]
    if np.any(np.diff(pressure) <= 0.0):
        raise RuntimeError("DD-103 projected pressure seed is not ordered")
    return pressure


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-103 Frozen Core V3 Pressure-Layer Steady-Root Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Residual system: `42` equations with all `15` rates fixed at zero",
            "- Solve coordinates: `27` algebraic variables",
            f"- Structural Jacobian colors: `{payload['color_count']}`",
            "- Starts: accepted-root algebraic state and independent source-profile state",
            "- Solver: bounded `least_squares(method='trf')`",
            "- Governing Jacobian: frozen colored central difference",
            "- Endpoint Jacobians: full central differences at `1e-5` and `5e-6`",
            "- Live property evaluation during preparation: `False`",
            "- Nonlinear solve during preparation: `False`",
            "- Dynamic integration during preparation: `False`",
            "",
            "## Bottom Boundary Decision",
            "",
            "The combined reboiler/sump link is dry-resistance-only. Merged sump "
            "inventory is not converted into tray liquid head. The remaining three "
            "tray links retain dry plus liquid-head closure. This rule is based on "
            "terminal link role and contains no stage-number condition.",
            "",
            "## Hard Stop",
            "",
            "Both starts must reach one common, interior, ordered-pressure root with "
            "scaled residual below `1e-8`, full algebraic column rank, stable "
            "endpoint spectra, exact conservation, and declared provider ownership. "
            "No tuning, continuation, alternate geometry, or rerun follows failure.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# DD-103 Core V3 Pressure-Layer Steady-Root Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
        f"- Provider calls: `{payload['provider_provenance']['total_calls']}`",
        f"- Common-root difference: `{payload['common_root_coordinate_difference']:.6e}`",
        f"- Worst condition: `{payload['worst_condition']:.6e}`",
        "",
    ]
    for start in payload["starts"]:
        lines.extend(
            (
                f"## {start['name']}",
                "",
                f"- Success: `{start['success']}`",
                f"- Evaluations: `{start['nfev']}` residual / `{start['njev']}` Jacobian",
                f"- Final residual: `{start['final_scaled_residual_inf_norm']:.6e}`",
                f"- Pressure, psia: `{start['pressure_psia']}`",
                f"- Temperature, F: `{start['temperature_F']}`",
                f"- Vapor flow, lbmol/h: `{start['vapor_flow_lbmolph']}`",
                f"- Liquid flow, lbmol/h: `{start['liquid_flow_lbmolph']}`",
                f"- Condenser duty, MMBTU/h: `{start['condenser_duty_MMBTUph']:.6f}`",
                "",
            )
        )
    return "\n".join(lines)


def prepare(
    dd102_result_path: Path,
    dd102_contract_path: Path,
    contract_path: Path,
    contract_doc: Path,
) -> dict[str, Any]:
    result = _load(dd102_result_path)
    source = _load(dd102_contract_path)
    if not result["pass"]:
        raise RuntimeError("DD-103 requires accepted DD-102 evidence")
    spec = dd102._spec(
        source["source_mapping"],
        float(source["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd102._reference(source["reference"])
    contract = build_pressure_layer_contract(spec.component_names)
    structural = audit_pressure_layer_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-103 pressure structure changed")
    base_lower, base_upper = physical_bounds(
        spec, reference, SteadyRootSettings()
    )
    indices = dynamic_algebraic_indices(spec)
    lower = _vector(base_lower[indices])
    upper = _vector(base_upper[indices])
    pressure_reference = np.asarray(source["pressure_reference_psia"], dtype=float)
    pressure_scale = float(source["pressure_coordinate_scale_psia"])
    pressure_lower = (
        float(pressure_reference[0])
        + MIN_PRESSURE_ABOVE_TOP_PSIA
        - pressure_reference[1:]
    ) / pressure_scale
    pressure_upper = (MAX_PRESSURE_PSIA - pressure_reference[1:]) / pressure_scale
    lower.extend(_vector(pressure_lower))
    upper.extend(_vector(pressure_upper))
    accepted_base = np.asarray(source["root_base_algebraic_coordinates"], dtype=float)
    canonical = np.concatenate((accepted_base, np.zeros(4)))
    projected_pressure = _projected_pressure_profile(result)
    projected_coordinates = (
        projected_pressure[1:] - pressure_reference[1:]
    ) / pressure_scale
    independent = np.concatenate((np.zeros(accepted_base.size), projected_coordinates))
    pattern, names = algebraic_sparsity_pattern(contract)
    from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups

    groups = greedy_column_groups(pattern)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd102_result_path": str(dd102_result_path).replace("\\", "/"),
        "dd102_result_sha256": _sha256(ROOT / dd102_result_path),
        "dd102_contract_path": str(dd102_contract_path).replace("\\", "/"),
        "dd102_contract_sha256": _sha256(ROOT / dd102_contract_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "dynamic_inventory_lbmol": source["dynamic_inventory_lbmol"],
        "storage_gradient_BTU_lbmol": source["storage_gradient_BTU_lbmol"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "pressure_reference_psia": source["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": source[
            "pressure_coordinate_scale_psia"
        ],
        "pressure_residual_scale_psia": source["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": source[
            "dry_tray_pressure_drop_coefficient"
        ],
        "pressure_link_geometry": _dry_terminal_geometry(
            source["pressure_link_geometry"]
        ),
        "bottom_link_geometry_decision": (
            "terminal reboiler/sump return is dry-only; merged sump inventory "
            "does not create tray liquid head"
        ),
        "solve_variable_names": list(names),
        "solve_row_count": 42,
        "solve_variable_count": 27,
        "color_groups": [list(group) for group in groups],
        "color_count": len(groups),
        "lower_bounds": lower,
        "upper_bounds": upper,
        "starts": [
            {
                "name": "accepted_algebraic_old_pressure",
                "coordinates": _vector(canonical),
            },
            {
                "name": "source_algebraic_projected_pressure",
                "coordinates": _vector(independent),
            },
        ],
        "projected_pressure_seed_psia": _vector(projected_pressure),
        "solver": asdict(PressureRootSettings()),
        "endpoint_jacobian_steps": list(ENDPOINT_JACOBIAN_STEPS),
        "residual_limit": RESIDUAL_LIMIT,
        "common_root_limit": COMMON_ROOT_LIMIT,
        "condition_limit": CONDITION_LIMIT,
        "spectrum_change_limit": SPECTRUM_CHANGE_LIMIT,
        "coupling_tolerance": COUPLING_TOLERANCE,
        "active_bound_tolerance": ACTIVE_BOUND_TOLERANCE,
        "component_conservation_limit": COMPONENT_CONSERVATION_LIMIT,
        "energy_conservation_limit": ENERGY_CONSERVATION_LIMIT,
        "provider_call_limit": PROVIDER_CALL_LIMIT,
        "wall_clock_limit_sec": WALL_CLOCK_LIMIT_SEC,
        "hard_stops": [
            "either start fails or reaches a different endpoint",
            "any endpoint residual exceeds 1e-8",
            "pressure is non-positive, unordered, or on a bound",
            "terminal dry-only or tray liquid-head ownership is violated",
            "algebraic Jacobian rank is below 27 or condition exceeds 1e8",
            "spectrum, registered coupling, conservation, or provider gate fails",
            "provider calls exceed 100000 or wall time exceeds 180 seconds",
            "any continuation, retry, alternate geometry, or integration is attempted",
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
        raise RuntimeError("DD-103 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha256(ROOT / path) != expected:
            raise RuntimeError(f"DD-103 implementation changed: {path}")
    if _sha256(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-103 workbook changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-103 result already exists; rerun is prohibited")
    _git("ls-files", "--error-unmatch", str(contract_path))


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify_contract(payload, contract_path, result_path)
    spec = dd102._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd102._reference(payload["reference"])
    state = dd102._state(payload["accepted_root_state"])
    contract = build_pressure_layer_contract(spec.component_names)
    provider = dd102._provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    molecular_weight = call_audit.component_molecular_weights(
        provider,
        caller="pressure_layer_fixed_parameters",
        state_id="dd103",
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
        component_mw_lbm_per_lbmol=molecular_weight,
        link_geometry=tuple(
            PressureLinkGeometry(**item)
            for item in payload["pressure_link_geometry"]
        ),
        enforce_pressure_order=False,
    )
    inventory = np.asarray(payload["dynamic_inventory_lbmol"], dtype=float)
    storage = np.asarray(payload["storage_gradient_BTU_lbmol"], dtype=float)
    settings = PressureRootSettings(**payload["solver"])
    lower = np.asarray(payload["lower_bounds"], dtype=float)
    upper = np.asarray(payload["upper_bounds"], dtype=float)
    started = time.perf_counter()
    outcomes = [
        solve_pressure_layer_root(
            contract,
            spec,
            reference,
            state,
            provider,
            call_audit,
            start_name=start["name"],
            initial_coordinates=start["coordinates"],
            lower_bounds=lower,
            upper_bounds=upper,
            inventory_lbmol=inventory,
            storage_gradient_BTU_lbmol=storage,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            numerical=numerical,
            settings=settings,
            active_bound_tolerance=float(payload["active_bound_tolerance"]),
        )
        for start in payload["starts"]
    ]
    endpoint_reports = []
    all_jacobians = []
    for outcome in outcomes:
        jacobians = [
            audit_algebraic_jacobian(
                contract,
                spec,
                reference,
                state,
                provider,
                call_audit,
                inventory_lbmol=inventory,
                coordinates=outcome.final_coordinates,
                storage_gradient_BTU_lbmol=storage,
                fixed_steady_scales=payload["fixed_steady_residual_scales"],
                numerical=numerical,
                step=float(step),
                coupling_tolerance=float(payload["coupling_tolerance"]),
                state_id=f"dd103:{outcome.start_name}:endpoint_jac:{step:g}",
            )
            for step in payload["endpoint_jacobian_steps"]
        ]
        all_jacobians.extend(jacobians)
        evaluation = outcome.final_evaluation
        physical = evaluation.base_evaluation.physical_state
        steady = evaluation.base_evaluation.steady_evaluation
        endpoint_reports.append(
            {
                "name": outcome.start_name,
                "success": outcome.success,
                "status": outcome.status,
                "message": outcome.message,
                "nfev": outcome.nfev,
                "njev": outcome.njev,
                "wall_clock_sec": outcome.wall_clock_sec,
                "initial_coordinates": _vector(outcome.initial_coordinates),
                "final_coordinates": _vector(outcome.final_coordinates),
                "final_scaled_residual_inf_norm": (
                    outcome.final_scaled_residual_inf_norm
                ),
                "base_scaled_residual_inf_norm": float(
                    np.max(np.abs(evaluation.scaled[:38]))
                ),
                "pressure_residual_inf_norm_psia": float(
                    np.max(np.abs(evaluation.pressure_drop.raw_residual_psia))
                ),
                "pressure_psia": _vector(evaluation.pressure_psia),
                "pressure_residual_psia": _vector(
                    evaluation.pressure_drop.raw_residual_psia
                ),
                "liquid_head_drop_psia": _vector(
                    evaluation.pressure_drop.liquid_head_drop_psia
                ),
                "dry_tray_drop_psia": _vector(
                    evaluation.pressure_drop.dry_tray_drop_psia
                ),
                "vapor_compressibility_factor": _vector(
                    evaluation.pressure_drop.vapor_compressibility_factor
                ),
                "temperature_F": _vector(physical.temperature_F),
                "liquid_mole_fraction": _rows(physical.liquid_mole_fraction),
                "vapor_mole_fraction": _rows(physical.vapor_mole_fraction),
                "liquid_flow_lbmolph": _vector(
                    physical.hydraulic_liquid_flow_lbmolph
                ),
                "vapor_flow_lbmolph": _vector(physical.vapor_flow_lbmolph),
                "condenser_duty_BTUph": float(physical.condenser_duty_BTUph),
                "condenser_duty_MMBTUph": float(
                    physical.condenser_duty_BTUph / 1.0e6
                ),
                "active_lower_bounds": list(outcome.active_lower_bounds),
                "active_upper_bounds": list(outcome.active_upper_bounds),
                "color_count": len(outcome.color_groups),
                "component_conservation_relative_error": float(
                    steady.component_telescoping_relative_error
                ),
                "energy_conservation_relative_error": float(
                    steady.energy_telescoping_relative_error
                ),
                "spectrum_relative_change": _spectrum_change(
                    jacobians[0].singular_values, jacobians[1].singular_values
                ),
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
    common_difference = float(
        np.max(
            np.abs(
                outcomes[0].final_coordinates - outcomes[1].final_coordinates
            )
        )
    )
    gates = {
        "solver_success": all(item.success for item in outcomes),
        "residual": all(
            item.final_scaled_residual_inf_norm < float(payload["residual_limit"])
            for item in outcomes
        ),
        "common_root": common_difference < float(payload["common_root_limit"]),
        "interior_bounds": all(
            not item.active_lower_bounds and not item.active_upper_bounds
            for item in outcomes
        ),
        "positive_ordered_pressure": all(
            np.all(np.asarray(item["pressure_psia"]) > 0.0)
            and np.all(np.diff(item["pressure_psia"]) > 0.0)
            for item in endpoint_reports
        ),
        "pressure_closure": all(
            item["pressure_residual_inf_norm_psia"]
            < float(payload["residual_limit"])
            for item in endpoint_reports
        ),
        "terminal_dry_only": all(
            item["liquid_head_drop_psia"][0] == 0.0
            and np.all(np.asarray(item["liquid_head_drop_psia"])[1:] > 0.0)
            for item in endpoint_reports
        ),
        "temperature_order": all(
            np.all(np.diff(item["temperature_F"]) > 0.0)
            for item in endpoint_reports
        ),
        "negative_condenser_duty": all(
            item["condenser_duty_BTUph"] < 0.0 for item in endpoint_reports
        ),
        "jacobian_rank": all(item.rank == 27 for item in all_jacobians),
        "jacobian_condition": all(
            item.condition < float(payload["condition_limit"])
            for item in all_jacobians
        ),
        "jacobian_structure": all(
            not item.zero_columns and not item.unexpected_couplings
            for item in all_jacobians
        ),
        "spectrum_stable": all(
            item["spectrum_relative_change"]
            < float(payload["spectrum_change_limit"])
            for item in endpoint_reports
        ),
        "component_conservation": all(
            item["component_conservation_relative_error"]
            < float(payload["component_conservation_limit"])
            for item in endpoint_reports
        ),
        "energy_conservation": all(
            item["energy_conservation_relative_error"]
            < float(payload["energy_conservation_limit"])
            for item in endpoint_reports
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
            "dd103_core_v3_pressure_layer_steady_root_passed"
            if passed
            else "dd103_core_v3_pressure_layer_steady_root_failed"
        ),
        "decision": (
            "authorize_pressure_enabled_implicit_step_contract_only"
            if passed
            else "stop_algebraic_pressure_path_before_dynamics"
        ),
        "wall_clock_sec": float(elapsed),
        "bottom_link_geometry_decision": payload[
            "bottom_link_geometry_decision"
        ],
        "starts": endpoint_reports,
        "common_root_coordinate_difference": common_difference,
        "worst_condition": max(item.condition for item in all_jacobians),
        "provider_provenance": provider_report,
        "gates": gates,
        "pass": passed,
        "campaign_executed_once": True,
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
    parser.add_argument("--dd102-result", type=Path, default=DEFAULT_DD102_RESULT)
    parser.add_argument("--dd102-contract", type=Path, default=DEFAULT_DD102_CONTRACT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-doc", type=Path, default=DEFAULT_CONTRACT_DOC)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--result-doc", type=Path, default=DEFAULT_RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.dd102_result,
            args.dd102_contract,
            args.contract,
            args.contract_doc,
        )
    else:
        output = execute(args.contract, args.result, args.result_doc)
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
