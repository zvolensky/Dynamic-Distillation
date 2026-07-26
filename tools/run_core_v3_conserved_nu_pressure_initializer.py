#!/usr/bin/env python
"""Prepare or execute the frozen DD-112 conserved-N/U initializer campaign."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_pressure_layer_numerical as dd102
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    audit_conserved_nu_pressure_initializer_contract,
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerNumericalSpec,
    InitializerSolveSettings,
    audit_initializer_constraint_jacobian,
    evaluate_initializer_constraints,
    initializer_constraint_pattern,
    initializer_objective_gradient,
    initializer_variable_names,
    kkt_stationarity_inf_norm,
    solve_equality_constrained_initializer,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit


SCHEMA = "dd112-core-v3-conserved-nu-pressure-initializer-contract-v1"
RESULT_SCHEMA = "dd112-core-v3-conserved-nu-pressure-initializer-result-v1"
CONTRACT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json")
RESULT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json")
CONTRACT_DOC = Path("docs/dd_112_core_v3_conserved_nu_pressure_initializer_contract_20260726.md")
RESULT_DOC = Path("docs/dd_112_core_v3_conserved_nu_pressure_initializer_20260726.md")
DD111 = Path("logs/dd111_core_v3_conserved_nu_pressure_initializer_20260726.json")
DD110 = Path("logs/dd110_core_v3_dd109_physical_gate_adjudication_20260726.json")
DD109_CONTRACT = Path("logs/dd109_core_v3_conserved_nu_pressure_numerical_contract_20260726.json")
DD109_RESULT = Path("logs/dd109_core_v3_conserved_nu_pressure_numerical_20260726.json")
DD103_CONTRACT = Path("logs/dd103_core_v3_pressure_layer_steady_root_contract_20260726.json")
DD103_RESULT = Path("logs/dd103_core_v3_pressure_layer_steady_root_20260726.json")
DD096_RESULT = Path("logs/dd096_core_v3_dynamic_dae_numerical_20260725.json")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_initializer_contract_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_initializer_numerical_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_numerical_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tests/test_core_v3_conserved_nu_pressure_initializer_contract_v1.py",
    "tests/test_core_v3_conserved_nu_pressure_initializer_numerical_v1.py",
    "tools/run_core_v3_conserved_nu_pressure_initializer.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def prepare() -> dict[str, Any]:
    dd111 = _load(DD111)
    dd110 = _load(DD110)
    dd109_contract = _load(DD109_CONTRACT)
    dd109_result = _load(DD109_RESULT)
    dd103_contract = _load(DD103_CONTRACT)
    dd103_result = _load(DD103_RESULT)
    dd096 = _load(DD096_RESULT)
    if not dd111["audit"]["pass_gate"] or not dd110["pass"]:
        raise RuntimeError("DD-112 requires passed DD-110 and DD-111 evidence")
    if dd110["decision"] != "authorize_frozen_conserved_nu_initializer_contract":
        raise RuntimeError("DD-110 did not authorize DD-112")
    inventory = np.asarray(dd109_contract["inventory_lbmol"], dtype=float)
    storage = np.asarray(
        dd096["storage_gradient"]["steps"][0]["internal_energy_BTU"], dtype=float
    )
    lower_u_reference = storage[1:]
    lower_u_scale = np.maximum(np.abs(lower_u_reference), 1.0)
    canonical_solve = np.asarray(
        dd109_contract["states"][0]["solve_coordinates"], dtype=float
    )
    pressure_solve = np.asarray(
        dd109_contract["states"][1]["solve_coordinates"], dtype=float
    )
    pressure_live_u = np.asarray(
        dd109_result["states"][1]["live_internal_energy_BTU"], dtype=float
    )[1:]
    canonical = np.concatenate((np.zeros(19), canonical_solve))
    pressure_start = np.concatenate(
        (
            np.zeros(15),
            (pressure_live_u - lower_u_reference) / lower_u_scale,
            pressure_solve,
        )
    )
    algebraic_lower = np.asarray(dd103_contract["lower_bounds"], dtype=float)
    algebraic_upper = np.asarray(dd103_contract["upper_bounds"], dtype=float)
    if algebraic_lower.shape != algebraic_upper.shape or algebraic_lower.shape != (27,):
        raise RuntimeError("DD-112 could not recover algebraic bounds")
    state_lower = np.concatenate((np.full(15, -np.log(20.0)), np.full(4, -5.0)))
    state_upper = np.concatenate((np.full(15, np.log(20.0)), np.full(4, 5.0)))
    rate_lower = np.full(19, -10.0)
    rate_upper = np.full(19, 10.0)
    lower = np.concatenate((state_lower, rate_lower, algebraic_lower))
    upper = np.concatenate((state_upper, rate_upper, algebraic_upper))
    for name, point in (
        ("dd094_storage_and_pressure_profile", canonical),
        ("dd103_pressure_endpoint_live_storage", pressure_start),
    ):
        if np.any(~np.isfinite(point)) or np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"DD-112 start is not strictly interior: {name}")
    objective_weights = np.concatenate(
        (np.ones(19), np.full(19, 10.0), np.ones(27))
    )
    contract = build_conserved_nu_pressure_initializer_contract(
        tuple(dd109_contract["source_mapping"]["component_names"])
    )
    structural = audit_conserved_nu_pressure_initializer_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-112 structural prerequisite changed")
    pattern = initializer_constraint_pattern(contract)
    groups = greedy_column_groups(pattern)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD111,
                DD110,
                DD109_CONTRACT,
                DD109_RESULT,
                DD103_CONTRACT,
                DD103_RESULT,
                DD096_RESULT,
            )
        },
        "workbook": dd109_contract["workbook"],
        "workbook_sha256": dd109_contract["workbook_sha256"],
        "property_package": dd109_contract["property_package"],
        "source_mapping": dd109_contract["source_mapping"],
        "operating_spec": dd109_contract["operating_spec"],
        "reference": dd109_contract["reference"],
        "accepted_root_state": dd109_contract["accepted_root_state"],
        "inventory_reference_lbmol": inventory.tolist(),
        "lower_internal_energy_reference_BTU": _vector(lower_u_reference),
        "lower_internal_energy_scale_BTU": _vector(lower_u_scale),
        "component_total_targets_lbmol": _vector(np.sum(inventory, axis=0)),
        "stored_energy_target_BTU": float(np.sum(storage)),
        "terminal_total_targets_lbmol": _vector(
            (np.sum(inventory[0]), np.sum(inventory[-1]))
        ),
        "top_storage_gradient_BTU_lbmol": dd109_contract["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": dd109_contract["energy_rate_scales_BTUph"],
        "storage_scales_BTU": dd109_contract["storage_scales_BTU"],
        "fixed_steady_residual_scales": dd109_contract["fixed_steady_residual_scales"],
        "pressure_reference_psia": dd109_contract["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": dd109_contract["pressure_coordinate_scale_psia"],
        "pressure_residual_scale_psia": dd109_contract["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": dd109_contract["dry_tray_pressure_drop_coefficient"],
        "pressure_link_geometry": dd109_contract["pressure_link_geometry"],
        "variable_names": list(initializer_variable_names(contract)),
        "constraint_names": [row.name for row in contract.constraints],
        "objective_center": _vector(canonical),
        "objective_weights": _vector(objective_weights),
        "objective_weight_blocks": {
            "conserved_state_movement": 1.0,
            "conserved_rate": 10.0,
            "algebraic_movement": 1.0,
        },
        "lower_bounds": _vector(lower),
        "upper_bounds": _vector(upper),
        "starts": [
            {"name": "dd094_storage_and_pressure_profile", "coordinates": _vector(canonical)},
            {"name": "dd103_pressure_endpoint_live_storage", "coordinates": _vector(pressure_start)},
        ],
        "coordinate_definition": {
            "component_inventory": "log(N/N_DD094)",
            "lower_internal_energy": "(U-U_DD096)/max(abs(U_DD096),1)",
            "component_and_energy_rates": "existing DD-109 normalized rate coordinates",
            "algebraic": "existing DD-103 transformed coordinates",
        },
        "constraint_scaling": {
            "dae": "unchanged DD-109 scales",
            "component_totals": "each target total",
            "stored_energy": "absolute whole-column target",
            "terminal_totals": "each target terminal total",
        },
        "color_groups": [list(group) for group in groups],
        "color_count": len(groups),
        "solver": asdict(InitializerSolveSettings()),
        "jacobian_steps": list(JACOBIAN_STEPS),
        "required_constraint_rank": 52,
        "constraint_limit": 1.0e-8,
        "common_solution_limit": 1.0e-6,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "colored_full_difference_limit": 1.0e-8,
        "kkt_stationarity_limit": 1.0e-5,
        "active_bound_tolerance": 1.0e-6,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "provider_call_limit": 150_000,
        "wall_clock_limit_sec": 300.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "either precommitted start fails or reaches a different constrained optimum",
            "any exact constraint exceeds 1e-8 or the endpoint constraint Jacobian loses rank",
            "conditioning, spectrum, registered coupling, or colored/full agreement fails",
            "the endpoint violates physicality, pressure ordering, conservation, provider, or bounds",
            "KKT stationarity exceeds the frozen limit",
            "call or wall limit is exceeded",
            "a retry, alternate solver, changed weight, changed bound, continuation, timestep, or dynamics is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-112 Frozen Conserved N/U Pressure Initializer Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Primal variables / exact constraints: `65 / 52`",
                f"- Constraint Jacobian colors: `{payload['color_count']}`",
                "- Starts: DD-094 pressure profile and DD-103 pressure endpoint",
                "- Solver: one `SLSQP` equality-constrained campaign",
                "- Objective weights, state/rate/algebraic: `1 / 10 / 1`",
                "- Live property evaluation during preparation: `False`",
                "- Initializer execution during preparation: `False`",
                "",
                "Execution is permitted once only after this exact contract is committed. No retry, alternate solver, changed weight, continuation, timestep, or dynamics is authorized.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-112 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-112 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-112 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-112 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-112 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec = dd102._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd102._reference(payload["reference"])
    template = dd102._state(payload["accepted_root_state"])
    contract = build_conserved_nu_pressure_initializer_contract(spec.component_names)
    if not audit_conserved_nu_pressure_initializer_contract(contract).pass_gate:
        raise RuntimeError("DD-112 structural prerequisite changed")
    provider = dd102._provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    molecular_weight = call_audit.component_molecular_weights(
        provider,
        caller="dd112_molecular_weight",
        state_id="dd112:preparation",
        evaluation_kind="preparation",
    )
    pressure_numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(payload["pressure_reference_psia"]),
        pressure_coordinate_scale_psia=float(payload["pressure_coordinate_scale_psia"]),
        pressure_residual_scale_psia=float(payload["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(payload["dry_tray_pressure_drop_coefficient"]),
        component_mw_lbm_per_lbmol=molecular_weight,
        link_geometry=tuple(PressureLinkGeometry(**item) for item in payload["pressure_link_geometry"]),
        enforce_pressure_order=False,
    )
    numerical = InitializerNumericalSpec(
        inventory_reference_lbmol=np.asarray(payload["inventory_reference_lbmol"]),
        lower_internal_energy_reference_BTU=np.asarray(payload["lower_internal_energy_reference_BTU"]),
        lower_internal_energy_scale_BTU=np.asarray(payload["lower_internal_energy_scale_BTU"]),
        component_total_targets_lbmol=np.asarray(payload["component_total_targets_lbmol"]),
        stored_energy_target_BTU=float(payload["stored_energy_target_BTU"]),
        terminal_total_targets_lbmol=np.asarray(payload["terminal_total_targets_lbmol"]),
        objective_center=np.asarray(payload["objective_center"]),
        objective_weights=np.asarray(payload["objective_weights"]),
        lower_bounds=np.asarray(payload["lower_bounds"]),
        upper_bounds=np.asarray(payload["upper_bounds"]),
        jacobian_step=float(payload["solver"]["jacobian_step"]),
    )
    settings = InitializerSolveSettings(**payload["solver"])
    common = {
        "top_storage_gradient_BTU_lbmol": payload["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": pressure_numerical,
    }

    def constraint_objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        evaluation_kind = "jacobian" if any(
            token in state_id for token in ("jacobian", "audit", "color", "full")
        ) else "residual"
        return evaluate_initializer_constraints(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=candidate,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
            **common,
        ).scaled

    started = time.perf_counter()
    records = []
    endpoints = []
    canonical_colored = None
    canonical_full = None
    for start_index, start_payload in enumerate(payload["starts"]):
        outcome = solve_equality_constrained_initializer(
            contract,
            numerical,
            start_payload["coordinates"],
            constraint_objective,
            settings=settings,
        )
        endpoint = evaluate_initializer_constraints(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=outcome.final_coordinates,
            state_id=f"dd112:{start_payload['name']}:endpoint",
            evaluation_kind="residual",
            **common,
        )
        jacobians = [
            audit_initializer_constraint_jacobian(
                contract,
                constraint_objective,
                outcome.final_coordinates,
                step=step,
                coupling_tolerance=float(payload["coupling_tolerance"]),
                use_coloring=True,
            )
            for step in payload["jacobian_steps"]
        ]
        if start_index == 0:
            canonical_colored = jacobians[0].matrix.copy()
            canonical_full = audit_initializer_constraint_jacobian(
                contract,
                constraint_objective,
                outcome.final_coordinates,
                step=float(payload["jacobian_steps"][0]),
                coupling_tolerance=float(payload["coupling_tolerance"]),
                use_coloring=False,
            )
        physical = endpoint.dae_evaluation.pressure_evaluation.base_evaluation.physical_state
        pressure = endpoint.dae_evaluation.pressure_evaluation.pressure_psia
        minimum_bound_distance = float(
            np.min(
                np.minimum(
                    outcome.final_coordinates - numerical.lower_bounds,
                    numerical.upper_bounds - outcome.final_coordinates,
                )
                / (numerical.upper_bounds - numerical.lower_bounds)
            )
        )
        stationarity = kkt_stationarity_inf_norm(
            numerical, outcome.final_coordinates, jacobians[0].matrix
        )
        steady = endpoint.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
        records.append(
            {
                "name": start_payload["name"],
                "success": outcome.success,
                "status": outcome.status,
                "message": outcome.message,
                "iterations": outcome.iterations,
                "objective_evaluations": outcome.objective_evaluations,
                "gradient_evaluations": outcome.gradient_evaluations,
                "final_objective": outcome.final_objective,
                "final_coordinates": _vector(outcome.final_coordinates),
                "constraint_inf_norm": float(np.max(np.abs(endpoint.scaled))),
                "component_total_residual_lbmol": _vector(endpoint.component_total_residual_lbmol),
                "stored_energy_residual_BTU": endpoint.stored_energy_residual_BTU,
                "terminal_total_residual_lbmol": _vector(endpoint.terminal_total_residual_lbmol),
                "component_conservation": float(steady.component_telescoping_relative_error),
                "energy_conservation": float(steady.energy_telescoping_relative_error),
                "pressure_psia": _vector(pressure),
                "temperature_F": _vector(physical.temperature_F),
                "inventory_lbmol": np.asarray(endpoint.inventory_lbmol).tolist(),
                "lower_internal_energy_BTU": _vector(endpoint.lower_internal_energy_BTU),
                "component_rate_lbmolph": np.asarray(endpoint.dae_evaluation.component_rate_lbmolph).tolist(),
                "internal_energy_rate_BTUph": _vector(endpoint.dae_evaluation.internal_energy_rate_BTUph),
                "liquid_flow_lbmolph": _vector(physical.hydraulic_liquid_flow_lbmolph),
                "vapor_flow_lbmolph": _vector(physical.vapor_flow_lbmolph),
                "distillate_lbmolph": float(physical.distillate_lbmolph),
                "bottoms_lbmolph": float(physical.bottoms_lbmolph),
                "condenser_duty_BTUph": float(physical.condenser_duty_BTUph),
                "minimum_normalized_bound_distance": minimum_bound_distance,
                "kkt_stationarity_inf_norm": stationarity,
                "spectrum_change": _spectrum_change(jacobians[0].singular_values, jacobians[1].singular_values),
                "jacobians": [
                    {
                        "step": item.step,
                        "rank": item.rank,
                        "condition": item.condition,
                        "singular_values": _vector(item.singular_values),
                        "zero_rows": list(item.zero_rows),
                        "zero_columns": list(item.zero_columns),
                        "unexpected_couplings": list(item.unexpected_couplings),
                        "color_count": item.color_count,
                    }
                    for item in jacobians
                ],
            }
        )
        endpoints.append(endpoint)
    elapsed = time.perf_counter() - started
    if canonical_colored is None or canonical_full is None:
        raise RuntimeError("DD-112 canonical Jacobian cross-check was not evaluated")
    colored_full_difference = float(np.max(np.abs(canonical_colored - canonical_full.matrix)))
    common_difference = float(
        np.max(
            np.abs(
                np.asarray(records[0]["final_coordinates"])
                - np.asarray(records[1]["final_coordinates"])
            )
        )
    )
    provenance = call_audit.report()
    all_jacobians = [item for record in records for item in record["jacobians"]]
    gates = {
        "solver_success": all(record["success"] for record in records),
        "constraints": all(record["constraint_inf_norm"] < payload["constraint_limit"] for record in records),
        "common_solution": common_difference < payload["common_solution_limit"],
        "rank": all(item["rank"] == payload["required_constraint_rank"] for item in all_jacobians) and canonical_full.rank == payload["required_constraint_rank"],
        "condition": all(item["condition"] < payload["condition_limit"] for item in all_jacobians) and canonical_full.condition < payload["condition_limit"],
        "spectrum": all(record["spectrum_change"] < payload["spectrum_change_limit"] for record in records),
        "structure": all(not item["zero_rows"] and not item["zero_columns"] and not item["unexpected_couplings"] for item in all_jacobians) and not canonical_full.zero_rows and not canonical_full.zero_columns and not canonical_full.unexpected_couplings,
        "colored_full": colored_full_difference < payload["colored_full_difference_limit"],
        "kkt_stationarity": all(record["kkt_stationarity_inf_norm"] < payload["kkt_stationarity_limit"] for record in records),
        "interior_bounds": all(record["minimum_normalized_bound_distance"] > payload["active_bound_tolerance"] for record in records),
        "pressure_order": all(np.all(np.diff(record["pressure_psia"]) > 0.0) for record in records),
        "physical": all(
            np.all(np.asarray(record["inventory_lbmol"]) > 0.0)
            and np.all(np.asarray(record["liquid_flow_lbmolph"]) > 0.0)
            and np.all(np.asarray(record["vapor_flow_lbmolph"]) > 0.0)
            and record["distillate_lbmolph"] > 0.0
            and record["bottoms_lbmolph"] > 0.0
            and np.all(np.isfinite(np.asarray(record["temperature_F"])))
            for record in records
        ),
        "conservation": all(
            abs(record["component_conservation"]) < payload["component_conservation_limit"]
            and abs(record["energy_conservation"]) < payload["energy_conservation_limit"]
            for record in records
        ),
        "provider": provenance["pass"],
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd112_passed" if passed else "dd112_failed",
        "decision": (
            "authorize_frozen_zero_time_initializer_audit"
            if passed
            else "stop_conserved_nu_pressure_initializer"
        ),
        "wall_clock_sec": elapsed,
        "provider_provenance": provenance,
        "starts": records,
        "common_solution_coordinate_difference": common_difference,
        "colored_full_matrix_difference": colored_full_difference,
        "canonical_full_jacobian": {
            "rank": canonical_full.rank,
            "condition": canonical_full.condition,
            "unexpected_couplings": list(canonical_full.unexpected_couplings),
        },
        "gates": gates,
        "pass": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "dynamic_integration_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-112 Conserved N/U Pressure Initializer Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Provider calls: `{provenance['total_calls']}`",
                f"- Common-solution difference: `{common_difference:.6e}`",
                f"- Colored/full difference: `{colored_full_difference:.6e}`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
