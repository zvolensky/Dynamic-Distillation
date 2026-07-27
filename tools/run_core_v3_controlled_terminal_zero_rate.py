#!/usr/bin/env python
"""Prepare or execute the frozen DD-122 controlled-terminal root campaign."""

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
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_terminal_gauge_invariance as dd121
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_rate_v1 import (
    controlled_terminal_pattern,
    controlled_terminal_variable_names,
    evaluate_controlled_terminal_zero_rate,
)
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import zero_rate_row_names
from dynamic_distillation.core_v3.zero_rate_root_v1 import (
    ZeroRateRootSettings,
    solve_zero_rate_root,
)


SCHEMA = "dd122-core-v3-controlled-terminal-zero-rate-contract-v1"
RESULT_SCHEMA = "dd122-core-v3-controlled-terminal-zero-rate-result-v1"
CONTRACT = Path("logs/dd122_core_v3_controlled_terminal_zero_rate_contract_20260727.json")
RESULT = Path("logs/dd122_core_v3_controlled_terminal_zero_rate_20260727.json")
CONTRACT_DOC = Path("docs/dd_122_core_v3_controlled_terminal_zero_rate_contract_20260727.md")
RESULT_DOC = Path("docs/dd_122_core_v3_controlled_terminal_zero_rate_20260727.md")
DD121_CONTRACT = Path("logs/dd121_core_v3_terminal_gauge_invariance_contract_20260727.json")
DD121_RESULT = Path("logs/dd121_core_v3_terminal_gauge_invariance_20260727.json")
DD120_CONTRACT = Path("logs/dd120_core_v3_zero_rate_root_contract_20260727.json")
DD120_RESULT = Path("logs/dd120_core_v3_zero_rate_root_20260727.json")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/controlled_terminal_zero_rate_v1.py",
    "src/dynamic_distillation/core_v3/zero_rate_root_v1.py",
    "tests/test_core_v3_controlled_terminal_zero_rate_v1.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
    "tools/run_core_v3_controlled_terminal_zero_rate.py",
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
    gauge = _load(DD121_RESULT)
    source = _load(DD120_CONTRACT)
    failed_root = _load(DD120_RESULT)
    if not gauge["pass"] or gauge["decision"] != "authorize_frozen_controlled_terminal_48x48_contract":
        raise RuntimeError("DD-122 requires the passed DD-121 authorization")
    spec = dd121.dd102._spec(
        source["source_mapping"], float(source["operating_spec"]["feed_enthalpy_BTUph"])
    )
    structural_contract = build_conserved_nu_pressure_initializer_contract(spec.component_names)
    pattern = controlled_terminal_pattern(structural_contract)
    rank = int(structural_rank(csr_matrix(pattern)))
    if pattern.shape != (48, 48) or rank != 48:
        raise RuntimeError("DD-122 controlled-terminal graph is not full rank")

    canonical = np.concatenate(
        (np.asarray(failed_root["starts"][0]["final_coordinates"], dtype=float), np.zeros(2))
    )
    independent = canonical.copy()
    component_count = len(spec.component_names)
    interior_offsets = np.asarray((0.02, -0.015, 0.01), dtype=float)
    for volume_index in range(1, 4):
        start = volume_index * component_count
        independent[start : start + component_count] += np.roll(
            interior_offsets, volume_index - 1
        )
    independent[15:18] += np.asarray((0.02, -0.015, 0.01))
    independent[-2:] = np.log((1.10, 0.90))
    lower = np.concatenate(
        (np.asarray(source["lower_bounds"], dtype=float), np.log((0.25, 0.25)))
    )
    upper = np.concatenate(
        (np.asarray(source["upper_bounds"], dtype=float), np.log((2.0, 2.0)))
    )
    starts = (
        {"name": "dd120_common_endpoint", "coordinates": _vector(canonical)},
        {"name": "independent_interior_and_product_perturbation", "coordinates": _vector(independent)},
    )
    for item in starts:
        point = np.asarray(item["coordinates"])
        if np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"DD-122 start is outside bounds: {item['name']}")
    settings = ZeroRateRootSettings()
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD121_CONTRACT, DD121_RESULT, DD120_CONTRACT, DD120_RESULT)
        },
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
        "variable_names": list(controlled_terminal_variable_names(structural_contract)),
        "row_names": list(zero_rate_row_names(structural_contract)),
        "structural_shape": list(pattern.shape),
        "structural_rank": rank,
        "starts": list(starts),
        "lower_bounds": _vector(lower),
        "upper_bounds": _vector(upper),
        "product_rate_ratio_bounds": [0.25, 2.0],
        "solver": asdict(settings),
        "jacobian_steps": list(JACOBIAN_STEPS),
        "residual_limit": 1.0e-8,
        "common_root_limit": 1.0e-6,
        "optimality_limit": 1.0e-8,
        "required_rank": 48,
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
            "either start fails, reaches a different endpoint, or leaves a residual above 1e-8",
            "an endpoint loses rank, exceeds condition, changes spectrum, or violates registered coupling",
            "D or B reaches a bound or any physical, pressure, conservation, or provider gate fails",
            "call or wall-clock limits are exceeded",
            "a retry, alternate solver, changed bound, target, scale, tolerance, continuation, timestep, controller action, or dynamics is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-122 Frozen Controlled-Terminal Zero-Rate Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- System: `48 x 48`, structural rank `48`",
                "- Added unknowns: positive distillate and bottoms level-controller outputs",
                "- Retained targets: reflux-drum and combined-reboiler/sump total inventory",
                "- Starts: DD-120 endpoint and one independent interior/product-rate perturbation",
                "- Solver: one bounded `least_squares(method='trf')` configuration",
                "- Full initial and final residual vectors: required",
                "- Retry, continuation, timestep, controller action, or dynamics: `False`",
                "",
                "Execution is permitted once only after this exact contract is committed.",
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
        raise RuntimeError("DD-122 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-122 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-122 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-122 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-122 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _jacobian(objective, point, pattern, step, state_id):
    matrix, groups = colored_central_difference_jacobian(
        objective, point, pattern=pattern, step=step, state_id=state_id
    )
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return matrix, singular, rank, condition, len(groups)


def _full_jacobian(objective, point, step):
    matrix = np.empty((point.size, point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = step
        plus = objective(point + delta, f"dd122:full:{column}:plus")
        minus = objective(point - delta, f"dd122:full:{column}:minus")
        matrix[:, column] = (plus - minus) / (2.0 * step)
    return matrix


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec, reference, template, contract, provider, call_audit, numerical, common = dd121._context(payload)
    pattern = controlled_terminal_pattern(contract)

    def evaluate(candidate, state_id):
        return evaluate_controlled_terminal_zero_rate(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=candidate,
            state_id=state_id,
            evaluation_kind="jacobian" if "jacobian" in state_id or "full" in state_id else "residual",
            **common,
        )

    def objective(candidate, state_id):
        return evaluate(candidate, state_id).scaled

    settings = ZeroRateRootSettings(**payload["solver"])
    lower = np.asarray(payload["lower_bounds"], dtype=float)
    upper = np.asarray(payload["upper_bounds"], dtype=float)
    started = time.perf_counter()
    records = []
    canonical_matrix = None
    for start in payload["starts"]:
        point = np.asarray(start["coordinates"], dtype=float)
        initial = evaluate(point, f"dd122:{start['name']}:initial")
        solve_started = time.perf_counter()
        outcome = solve_zero_rate_root(
            objective,
            point,
            lower_bounds=lower,
            upper_bounds=upper,
            pattern=pattern,
            settings=settings,
            state_id=f"dd122:{start['name']}",
        )
        solve_elapsed = time.perf_counter() - solve_started
        endpoint = evaluate(outcome.final_coordinates, f"dd122:{start['name']}:endpoint")
        audits = []
        for step in payload["jacobian_steps"]:
            matrix, singular, rank, condition, colors = _jacobian(
                objective,
                outcome.final_coordinates,
                pattern,
                float(step),
                f"dd122:{start['name']}:jacobian:{step:g}",
            )
            if canonical_matrix is None:
                canonical_matrix = matrix.copy()
            unexpected = tuple(
                f"{payload['row_names'][row]} <- {payload['variable_names'][column]}"
                for row, column in zip(*np.where((~pattern) & (np.abs(matrix) > payload["coupling_tolerance"])))
            )
            audits.append(
                {
                    "step": step,
                    "rank": rank,
                    "condition": condition,
                    "singular_values": _vector(singular),
                    "color_count": colors,
                    "zero_rows": [payload["row_names"][i] for i in np.flatnonzero(np.max(np.abs(matrix), axis=1) <= payload["coupling_tolerance"])],
                    "zero_columns": [payload["variable_names"][i] for i in np.flatnonzero(np.max(np.abs(matrix), axis=0) <= payload["coupling_tolerance"])],
                    "unexpected_couplings": list(unexpected),
                }
            )
        base = endpoint.base.full_evaluation
        physical = base.dae_evaluation.pressure_evaluation.base_evaluation.physical_state
        pressure = base.dae_evaluation.pressure_evaluation.pressure_psia
        steady = base.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
        bound_distance = float(np.min(np.minimum(outcome.final_coordinates - lower, upper - outcome.final_coordinates) / (upper - lower)))
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
                "initial_coordinates": _vector(point),
                "initial_scaled_residual": _vector(initial.scaled),
                "final_coordinates": _vector(outcome.final_coordinates),
                "final_scaled_residual": _vector(endpoint.scaled),
                "residual_inf_norm": float(np.max(np.abs(endpoint.scaled))),
                "dae_residual_inf_norm": float(np.max(np.abs(endpoint.base.dae_scaled))),
                "terminal_scaled_residual": _vector(endpoint.base.terminal_scaled),
                "distillate_lbmolph": endpoint.distillate_lbmolph,
                "bottoms_lbmolph": endpoint.bottoms_lbmolph,
                "distillate_deviation_from_reference_lbmolph": endpoint.distillate_lbmolph - reference.distillate_lbmolph,
                "bottoms_deviation_from_reference_lbmolph": endpoint.bottoms_lbmolph - reference.bottoms_lbmolph,
                "minimum_normalized_bound_distance": bound_distance,
                "pressure_psia": _vector(pressure),
                "temperature_F": _vector(physical.temperature_F),
                "inventory_lbmol": np.asarray(base.inventory_lbmol).tolist(),
                "lower_internal_energy_BTU": _vector(base.lower_internal_energy_BTU),
                "liquid_flow_lbmolph": _vector(physical.hydraulic_liquid_flow_lbmolph),
                "vapor_flow_lbmolph": _vector(physical.vapor_flow_lbmolph),
                "condenser_duty_BTUph": float(physical.condenser_duty_BTUph),
                "component_conservation": float(steady.component_telescoping_relative_error),
                "energy_conservation": float(steady.energy_telescoping_relative_error),
                "spectrum_change": _spectrum_change(np.asarray(audits[0]["singular_values"]), np.asarray(audits[1]["singular_values"])),
                "jacobians": audits,
            }
        )
    if canonical_matrix is None:
        raise RuntimeError("DD-122 endpoint Jacobian was not evaluated")
    full = _full_jacobian(objective, np.asarray(records[0]["final_coordinates"]), float(payload["jacobian_steps"][0]))
    colored_full_difference = float(np.max(np.abs(canonical_matrix - full)))
    full_unexpected = tuple(
        f"{payload['row_names'][row]} <- {payload['variable_names'][column]}"
        for row, column in zip(*np.where((~pattern) & (np.abs(full) > payload["coupling_tolerance"])))
    )
    common_difference = float(np.max(np.abs(np.asarray(records[0]["final_coordinates"]) - np.asarray(records[1]["final_coordinates"]))))
    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    audits = [item for record in records for item in record["jacobians"]]
    gates = {
        "solver_success": all(record["success"] for record in records),
        "residual": all(record["residual_inf_norm"] < payload["residual_limit"] for record in records),
        "common_root": common_difference < payload["common_root_limit"],
        "optimality": all(record["optimality"] < payload["optimality_limit"] for record in records),
        "rank": all(item["rank"] == payload["required_rank"] for item in audits),
        "condition": all(item["condition"] < payload["condition_limit"] for item in audits),
        "spectrum": all(record["spectrum_change"] < payload["spectrum_change_limit"] for record in records),
        "structure": all(not item["zero_rows"] and not item["zero_columns"] and not item["unexpected_couplings"] for item in audits) and not full_unexpected,
        "colored_full": colored_full_difference < payload["colored_full_difference_limit"],
        "interior_bounds": all(record["minimum_normalized_bound_distance"] > payload["active_bound_tolerance"] for record in records),
        "pressure_order": all(np.all(np.diff(record["pressure_psia"]) > 0.0) for record in records),
        "physical": all(record["distillate_lbmolph"] > 0.0 and record["bottoms_lbmolph"] > 0.0 and np.all(np.asarray(record["inventory_lbmol"]) > 0.0) and np.all(np.asarray(record["liquid_flow_lbmolph"]) > 0.0) and np.all(np.asarray(record["vapor_flow_lbmolph"]) > 0.0) for record in records),
        "conservation": all(abs(record["component_conservation"]) < payload["component_conservation_limit"] and abs(record["energy_conservation"]) < payload["energy_conservation_limit"] for record in records),
        "provider": provenance["pass"],
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd122_passed" if passed else "dd122_failed",
        "decision": "authorize_zero_rate_dynamic_handoff_contract" if passed else "retire_controlled_terminal_zero_rate_path",
        "starts": records,
        "common_root_coordinate_difference": common_difference,
        "canonical_colored_full_matrix_difference": colored_full_difference,
        "canonical_full_unexpected_couplings": list(full_unexpected),
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
                "# DD-122 Core V3 Controlled-Terminal Zero-Rate Campaign",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Final residuals: `{[item['residual_inf_norm'] for item in records]}`",
                f"- Common-root difference: `{common_difference:.6e}`",
                f"- Distillate rates: `{[item['distillate_lbmolph'] for item in records]}` lbmol/h",
                f"- Bottoms rates: `{[item['bottoms_lbmolph'] for item in records]}` lbmol/h",
                f"- DWSIM calls: `{provenance['total_calls']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "DD-122 performed no timestep, controller action, continuation, or dynamics.",
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
