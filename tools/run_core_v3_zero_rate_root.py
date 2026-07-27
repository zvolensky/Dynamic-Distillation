#!/usr/bin/env python
"""Prepare or execute the frozen DD-120 Core V3 zero-rate root campaign."""

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
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_pressure_layer_numerical as dd102
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerNumericalSpec,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import (
    audit_zero_rate_jacobian,
    evaluate_zero_rate_readiness,
    zero_rate_pattern,
)
from dynamic_distillation.core_v3.zero_rate_root_v1 import (
    ZeroRateRootSettings,
    solve_zero_rate_root,
)


SCHEMA = "dd120-core-v3-zero-rate-root-contract-v1"
RESULT_SCHEMA = "dd120-core-v3-zero-rate-root-result-v1"
CONTRACT = Path("logs/dd120_core_v3_zero_rate_root_contract_20260727.json")
RESULT = Path("logs/dd120_core_v3_zero_rate_root_20260727.json")
CONTRACT_DOC = Path("docs/dd_120_core_v3_zero_rate_root_contract_20260727.md")
RESULT_DOC = Path("docs/dd_120_core_v3_zero_rate_root_20260727.md")
DD119_CONTRACT = Path("logs/dd119_core_v3_live_zero_rate_readiness_contract_20260727.json")
DD119_RESULT = Path("logs/dd119_core_v3_live_zero_rate_readiness_20260727.json")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/zero_rate_root_v1.py",
    "src/dynamic_distillation/core_v3/zero_rate_readiness_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_initializer_numerical_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tests/test_core_v3_zero_rate_root_v1.py",
    "tests/test_core_v3_zero_rate_readiness_v1.py",
    "tools/run_core_v3_zero_rate_root.py",
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
    source = _load(DD119_CONTRACT)
    readiness = _load(DD119_RESULT)
    if not readiness["pass"] or readiness["decision"] != "authorize_frozen_zero_rate_root_contract":
        raise RuntimeError("DD-120 requires the passed DD-119 authorization")
    columns = np.concatenate((np.arange(19), np.arange(38, 65)))
    numerical = source["initializer_numerical"]
    lower = np.asarray(numerical["lower_bounds"], dtype=float)[columns]
    upper = np.asarray(numerical["upper_bounds"], dtype=float)[columns]
    starts = source["states"]
    for item in starts:
        point = np.asarray(item["coordinates"], dtype=float)
        if point.shape != (46,) or np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"DD-120 start is invalid: {item['name']}")
    settings = ZeroRateRootSettings()
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD119_CONTRACT, DD119_RESULT)
        },
        "source_contract_payload_sha256": source["contract_payload_sha256"],
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "initializer_numerical": source["initializer_numerical"],
        "top_storage_gradient_BTU_lbmol": source["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "pressure_reference_psia": source["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": source["pressure_coordinate_scale_psia"],
        "pressure_residual_scale_psia": source["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": source["dry_tray_pressure_drop_coefficient"],
        "pressure_link_geometry": source["pressure_link_geometry"],
        "variable_names": source["variable_names"],
        "row_names": source["row_names"],
        "starts": starts,
        "lower_bounds": _vector(lower),
        "upper_bounds": _vector(upper),
        "solver": asdict(settings),
        "jacobian_steps": list(JACOBIAN_STEPS),
        "required_rank": 46,
        "residual_limit": 1.0e-8,
        "terminal_residual_limit": 1.0e-8,
        "common_root_limit": 1.0e-6,
        "optimality_limit": 1.0e-8,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "colored_full_difference_limit": 1.0e-8,
        "active_bound_tolerance": 1.0e-6,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "provider_call_limit": 100_000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "either frozen start fails, reaches a different endpoint, or leaves any of 48 residuals above 1e-8",
            "either terminal total-holdup row remains above 1e-8",
            "an endpoint Jacobian loses rank or exceeds condition, spectrum, coloring, or registry limits",
            "an endpoint reaches a bound or violates physicality, pressure order, conservation, or provider ownership",
            "call or wall-clock limits are exceeded",
            "a retry, alternate solver, continuation, changed target, changed tolerance, timestep, controller, or dynamics is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-120 Frozen Core V3 Zero-Rate Root Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- System: overdetermined `48 x 46` zero-rate residual",
                "- Starts: DD-112 canonical and DD-115 refined one-second state",
                "- Solver: one bounded `least_squares(method='trf')` configuration",
                "- Jacobian: unchanged 20-color central difference",
                "- Acceptance: every row below `1e-8`, common root below `1e-6`",
                "- Retry, continuation, timestep, controller, or dynamics: `False`",
                "",
                "Execution is permitted once only after this exact contract is committed. Failure retires the terminal-scaled zero-rate root path without tuning.",
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
        raise RuntimeError("DD-120 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-120 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-120 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-120 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-120 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _full_jacobian(objective, point: np.ndarray, step: float) -> np.ndarray:
    matrix = np.empty((48, 46), dtype=float)
    for column in range(46):
        delta = np.zeros(46)
        delta[column] = step
        plus = objective(point + delta, f"dd120:full:{column}:plus")
        minus = objective(point - delta, f"dd120:full:{column}:minus")
        matrix[:, column] = (plus - minus) / (2.0 * step)
    return matrix


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec = dd102._spec(
        payload["source_mapping"], float(payload["operating_spec"]["feed_enthalpy_BTUph"])
    )
    reference = dd102._reference(payload["reference"])
    template = dd102._state(payload["accepted_root_state"])
    contract = build_conserved_nu_pressure_initializer_contract(spec.component_names)
    pattern = zero_rate_pattern(contract)
    provider = dd102._provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    molecular_weight = call_audit.component_molecular_weights(
        provider,
        caller="dd120_molecular_weight",
        state_id="dd120:preparation",
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
    data = payload["initializer_numerical"]
    numerical = InitializerNumericalSpec(
        inventory_reference_lbmol=np.asarray(data["inventory_reference_lbmol"]),
        lower_internal_energy_reference_BTU=np.asarray(data["lower_internal_energy_reference_BTU"]),
        lower_internal_energy_scale_BTU=np.asarray(data["lower_internal_energy_scale_BTU"]),
        component_total_targets_lbmol=np.asarray(data["component_total_targets_lbmol"]),
        stored_energy_target_BTU=float(data["stored_energy_target_BTU"]),
        terminal_total_targets_lbmol=np.asarray(data["terminal_total_targets_lbmol"]),
        objective_center=np.asarray(data["objective_center"]),
        objective_weights=np.asarray(data["objective_weights"]),
        lower_bounds=np.asarray(data["lower_bounds"]),
        upper_bounds=np.asarray(data["upper_bounds"]),
        jacobian_step=float(payload["solver"]["jacobian_step"]),
    )
    common = {
        "top_storage_gradient_BTU_lbmol": payload["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": pressure_numerical,
    }

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_zero_rate_readiness(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=candidate,
            state_id=state_id,
            evaluation_kind="jacobian" if "jacobian" in state_id or "color" in state_id or "full" in state_id else "residual",
            **common,
        ).scaled

    settings = ZeroRateRootSettings(**payload["solver"])
    lower = np.asarray(payload["lower_bounds"], dtype=float)
    upper = np.asarray(payload["upper_bounds"], dtype=float)
    started = time.perf_counter()
    records = []
    canonical_colored = None
    for index, start in enumerate(payload["starts"]):
        point = np.asarray(start["coordinates"], dtype=float)
        solve_started = time.perf_counter()
        outcome = solve_zero_rate_root(
            objective,
            point,
            lower_bounds=lower,
            upper_bounds=upper,
            pattern=pattern,
            settings=settings,
            state_id=f"dd120:{start['name']}",
        )
        solve_elapsed = time.perf_counter() - solve_started
        endpoint = evaluate_zero_rate_readiness(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=outcome.final_coordinates,
            state_id=f"dd120:{start['name']}:endpoint",
            evaluation_kind="residual",
            **common,
        )
        jacobians = [
            audit_zero_rate_jacobian(
                contract,
                objective,
                outcome.final_coordinates,
                endpoint.scaled,
                step=float(step),
                coupling_tolerance=float(payload["coupling_tolerance"]),
                state_id=f"dd120:{start['name']}:audit:{step:g}",
            )
            for step in payload["jacobian_steps"]
        ]
        if index == 0:
            canonical_colored = jacobians[0].matrix.copy()
        physical = endpoint.full_evaluation.dae_evaluation.pressure_evaluation.base_evaluation.physical_state
        pressure = endpoint.full_evaluation.dae_evaluation.pressure_evaluation.pressure_psia
        steady = endpoint.full_evaluation.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
        bound_distance = float(
            np.min(
                np.minimum(
                    outcome.final_coordinates - lower,
                    upper - outcome.final_coordinates,
                )
                / (upper - lower)
            )
        )
        records.append(
            {
                "name": start["name"],
                "success": outcome.success,
                "status": outcome.status,
                "message": outcome.message,
                "residual_evaluations": outcome.residual_evaluations,
                "jacobian_evaluations": outcome.jacobian_evaluations,
                "solve_wall_clock_sec": solve_elapsed,
                "cost": outcome.cost,
                "optimality": outcome.optimality,
                "final_coordinates": _vector(outcome.final_coordinates),
                "movement_from_start_inf_norm": float(np.max(np.abs(outcome.final_coordinates - point))),
                "residual_inf_norm": float(np.max(np.abs(endpoint.scaled))),
                "dae_residual_inf_norm": float(np.max(np.abs(endpoint.dae_scaled))),
                "terminal_scaled_residual": _vector(endpoint.terminal_scaled),
                "component_total_residual_lbmol": _vector(endpoint.component_total_residual_lbmol),
                "stored_energy_residual_BTU": endpoint.stored_energy_residual_BTU,
                "terminal_total_residual_lbmol": _vector(endpoint.terminal_total_residual_lbmol),
                "minimum_normalized_bound_distance": bound_distance,
                "component_conservation": float(steady.component_telescoping_relative_error),
                "energy_conservation": float(steady.energy_telescoping_relative_error),
                "pressure_psia": _vector(pressure),
                "temperature_F": _vector(physical.temperature_F),
                "inventory_lbmol": np.asarray(endpoint.full_evaluation.inventory_lbmol).tolist(),
                "lower_internal_energy_BTU": _vector(endpoint.full_evaluation.lower_internal_energy_BTU),
                "liquid_flow_lbmolph": _vector(physical.hydraulic_liquid_flow_lbmolph),
                "vapor_flow_lbmolph": _vector(physical.vapor_flow_lbmolph),
                "distillate_lbmolph": float(physical.distillate_lbmolph),
                "bottoms_lbmolph": float(physical.bottoms_lbmolph),
                "condenser_duty_BTUph": float(physical.condenser_duty_BTUph),
                "spectrum_change": _spectrum_change(
                    jacobians[0].augmented_singular_values,
                    jacobians[1].augmented_singular_values,
                ),
                "jacobians": [
                    {
                        "step": item.step,
                        "rank": item.augmented_rank,
                        "condition": item.augmented_condition,
                        "singular_values": _vector(item.augmented_singular_values),
                        "zero_rows": list(item.zero_rows),
                        "zero_columns": list(item.zero_columns),
                        "unexpected_couplings": list(item.unexpected_couplings),
                        "left_null_projection_norm": item.left_null_projection_norm,
                    }
                    for item in jacobians
                ],
            }
        )
    if canonical_colored is None:
        raise RuntimeError("DD-120 canonical endpoint Jacobian was not evaluated")
    full = _full_jacobian(
        objective,
        np.asarray(records[0]["final_coordinates"], dtype=float),
        float(payload["jacobian_steps"][0]),
    )
    colored_full_difference = float(np.max(np.abs(canonical_colored - full)))
    unexpected_full = tuple(
        f"{payload['row_names'][row]} <- {payload['variable_names'][column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(full) > payload["coupling_tolerance"]))
        )
    )
    elapsed = time.perf_counter() - started
    common_difference = float(
        np.max(
            np.abs(
                np.asarray(records[0]["final_coordinates"])
                - np.asarray(records[1]["final_coordinates"])
            )
        )
    )
    provenance = call_audit.report()
    audits = [item for record in records for item in record["jacobians"]]
    gates = {
        "solver_success": all(record["success"] for record in records),
        "residual": all(record["residual_inf_norm"] < payload["residual_limit"] for record in records),
        "terminal_residual": all(
            np.max(np.abs(record["terminal_scaled_residual"])) < payload["terminal_residual_limit"]
            for record in records
        ),
        "common_root": common_difference < payload["common_root_limit"],
        "optimality": all(record["optimality"] < payload["optimality_limit"] for record in records),
        "rank": all(item["rank"] == payload["required_rank"] for item in audits),
        "condition": all(item["condition"] < payload["condition_limit"] for item in audits),
        "spectrum": all(record["spectrum_change"] < payload["spectrum_change_limit"] for record in records),
        "structure": all(
            not item["zero_rows"] and not item["zero_columns"] and not item["unexpected_couplings"]
            for item in audits
        ) and not unexpected_full,
        "colored_full": colored_full_difference < payload["colored_full_difference_limit"],
        "interior_bounds": all(record["minimum_normalized_bound_distance"] > payload["active_bound_tolerance"] for record in records),
        "pressure_order": all(np.all(np.diff(record["pressure_psia"]) > 0.0) for record in records),
        "physical": all(
            np.all(np.asarray(record["inventory_lbmol"]) > 0.0)
            and np.all(np.asarray(record["liquid_flow_lbmolph"]) > 0.0)
            and np.all(np.asarray(record["vapor_flow_lbmolph"]) > 0.0)
            and record["distillate_lbmolph"] > 0.0
            and record["bottoms_lbmolph"] > 0.0
            and np.all(np.isfinite(record["temperature_F"]))
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
        "classification": "dd120_passed" if passed else "dd120_failed",
        "decision": (
            "authorize_frozen_zero_rate_dynamic_handoff_contract"
            if passed
            else "retire_terminal_scaled_zero_rate_root_path"
        ),
        "starts": records,
        "common_root_coordinate_difference": common_difference,
        "canonical_colored_full_matrix_difference": colored_full_difference,
        "canonical_full_unexpected_couplings": list(unexpected_full),
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "continuation_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-120 Core V3 Zero-Rate Root Campaign",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- DWSIM calls: `{provenance['total_calls']}`",
                f"- Final residuals: `{[item['residual_inf_norm'] for item in records]}`",
                f"- Common-root difference: `{common_difference:.6e}`",
                f"- Conditions: `{[item['jacobians'][0]['condition'] for item in records]}`",
                f"- Gates: `{gates}`",
                "",
                "DD-120 performed no timestep or dynamics. Its frozen decision controls whether zero-rate dynamic handoff may proceed.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    result = prepare() if args.mode == "prepare" else execute()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
