#!/usr/bin/env python
"""Prepare or execute the frozen DD-132 modified-Newton live proof."""

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

import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    evaluate_controlled_terminal_zero_time,
)
from dynamic_distillation.core_v3.modified_newton_v1 import (
    ModifiedNewtonSettings,
    solve_modified_newton,
)


SCHEMA = "dd132-core-v3-modified-newton-live-efficiency-contract-v1"
RESULT_SCHEMA = "dd132-core-v3-modified-newton-live-efficiency-result-v1"
DD130_CONTRACT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_contract_20260805.json")
DD130_RESULT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_20260805.json")
DD131_CONTRACT = Path("logs/dd131_core_v3_modified_newton_efficiency_contract_20260805.json")
DD131_RESULT = Path("logs/dd131_core_v3_modified_newton_efficiency_20260805.json")
CONTRACT = Path("logs/dd132_core_v3_modified_newton_live_efficiency_contract_20260805.json")
RESULT = Path("logs/dd132_core_v3_modified_newton_live_efficiency_20260805.json")
CONTRACT_DOC = Path("docs/dd_132_core_v3_modified_newton_live_efficiency_contract_20260805.md")
RESULT_DOC = Path("docs/dd_132_core_v3_modified_newton_live_efficiency_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/modified_newton_v1.py",
    "tests/test_core_v3_modified_newton_v1.py",
    "tools/audit_core_v3_modified_newton_efficiency.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
    "tools/run_core_v3_controlled_terminal_first_step.py",
    "tools/run_core_v3_modified_newton_live_efficiency.py",
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


def prepare() -> dict[str, Any]:
    source = _load(DD130_CONTRACT)
    baseline = _load(DD130_RESULT)
    design = _load(DD131_CONTRACT)
    authorization = _load(DD131_RESULT)
    if (
        not authorization["pass"]
        or authorization["decision"]
        != "authorize_frozen_modified_newton_live_efficiency_contract"
    ):
        raise RuntimeError("DD-132 requires the passed DD-131 authorization")
    false_gates = sorted(key for key, value in baseline["gates"].items() if not value)
    if false_gates != ["calls"]:
        raise RuntimeError("DD-132 requires DD-130's efficiency-only failure")
    contract = dd128._contract(source)
    pattern = controlled_terminal_step_pattern(contract)
    algorithm = design["algorithm"]
    copied = (
        "workbook", "workbook_sha256", "property_package", "source_mapping",
        "operating_spec", "reference", "accepted_root_state",
        "initializer_numerical", "top_storage_gradient_BTU_lbmol",
        "energy_rate_scales_BTUph", "storage_scales_BTU",
        "fixed_steady_residual_scales", "pressure_reference_psia",
        "pressure_coordinate_scale_psia", "pressure_residual_scale_psia",
        "dry_tray_pressure_drop_coefficient", "pressure_link_geometry",
        "geometry", "controllers", "inventory_lbmol",
        "lower_internal_energy_BTU", "controller_memory",
        "zero_time_coordinates", "expected_distillate_lbmolph",
        "expected_bottoms_lbmolph", "original_level_setpoints",
        "moved_level_setpoints", "setpoint_multiplier",
        "disturbance_definition", "grid", "component_rate_scale_lbmolph",
        "residual_limit", "component_conservation_limit",
        "energy_conservation_limit", "wall_clock_limit_sec",
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD130_CONTRACT, DD130_RESULT, DD131_CONTRACT, DD131_RESULT)
        },
        **{key: source[key] for key in copied},
        "saved_dd130_outcomes": baseline["outcomes"],
        "algorithm": {
            key: algorithm[key]
            for key in (
                "residual_tolerance", "max_iterations", "line_search_fractions",
                "armijo_fraction", "condition_limit", "jacobian_builds_per_root",
                "factorizations_per_root", "jacobian_rebuild_or_fallback",
                "bound_handling", "acceptance_norm",
            )
        },
        "jacobian_step": 1.0e-5,
        "step_pattern_shape": list(pattern.shape),
        "step_color_count": int(design["three_component_color_count"]),
        "required_rank": 50,
        "endpoint_reproduction_limit": 1.0e-7,
        "inventory_refinement_limit": float(source["inventory_refinement_limit"]),
        "energy_refinement_limit": float(source["energy_refinement_limit"]),
        "memory_refinement_limit": float(source["memory_refinement_limit"]),
        "coordinate_refinement_limit": float(source["coordinate_refinement_limit"]),
        "product_refinement_limit": float(source["product_refinement_limit"]),
        "level_refinement_limit": float(source["level_refinement_limit"]),
        "minimum_product_signal_relative": float(source["minimum_product_signal_relative"]),
        "minimum_controller_rate_signal_per_sec": float(source["minimum_controller_rate_signal_per_sec"]),
        "minimum_terminal_accumulation_lbmolph": float(source["minimum_terminal_accumulation_lbmolph"]),
        "discrete_kinematic_limit": float(source["discrete_kinematic_limit"]),
        "provider_call_limit": 8000,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "DD-130 or DD-131 evidence or implementation hashes change",
            "any root uses other than one colored Jacobian and one factorization",
            "any Jacobian rebuild, alternate solver, clipping, projection, or fallback occurs",
            "any root, saved-endpoint reproduction, direction, refinement, kinematic, physical, conservation, provider, 8000-call, or wall gate fails",
            "a retry, changed disturbance, changed grid, tuning, or trajectory occurs",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text("\n".join((
        "# DD-132 Frozen Modified-Newton Live Efficiency Contract", "",
        f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
        "- Physical state, disturbance, and grids: exact DD-130",
        "- Solver: one frozen 21-color Jacobian and one LU factorization per root",
        "- Corrections/line search: at most `12 / 4` per root",
        "- Saved DD-130 endpoint reproduction limit: `1e-7` normalized",
        "- Provider-call limit: `<8000`",
        "- Rebuild, fallback, retry, or trajectory: `False`", "",
        "Execution is permitted once only after this exact contract is committed.", "",
    )), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-132 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-132 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-132 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-132 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = dd121._context(payload)
    contract = dd128._contract(payload)
    pattern = controlled_terminal_step_pattern(contract)
    point = np.asarray(payload["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(payload["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    original_setpoints = TerminalLevelSetpoints(**payload["original_level_setpoints"])
    moved_setpoints = TerminalLevelSetpoints(**payload["moved_level_setpoints"])
    settings = ModifiedNewtonSettings(**{
        key: payload["algorithm"][key]
        for key in (
            "residual_tolerance", "max_iterations", "line_search_fractions",
            "armijo_fraction", "condition_limit",
        )
    })
    started = time.perf_counter()
    zero = evaluate_controlled_terminal_zero_time(
        contract, spec, reference, template, provider, call_audit,
        inventory_lbmol=inventory, lower_internal_energy_BTU=lower_u,
        controller_memory=memory, level_setpoints=original_setpoints,
        solve_coordinates=point, state_id="dd132:initial_state",
        evaluation_kind="residual", **common,
    )
    top_u = float(zero.base.live_internal_energy_BTU[0])
    step_common = {
        "component_rate_scale_lbmolph": float(payload["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }

    def make_objective(previous_n, previous_top_u, previous_lower_u, previous_memory, seconds):
        def objective(candidate, state_id):
            return evaluate_controlled_terminal_backward_euler_residual(
                contract, spec, reference, template, provider, call_audit,
                previous_inventory_lbmol=previous_n,
                previous_top_internal_energy_BTU=previous_top_u,
                previous_lower_internal_energy_BTU=previous_lower_u,
                previous_controller_memory=previous_memory,
                level_setpoints=moved_setpoints, solve_coordinates=candidate,
                step_seconds=seconds, state_id=state_id,
                evaluation_kind="jacobian" if "jacobian" in state_id else "residual",
                **step_common,
            )
        return objective

    def make_jacobian(objective):
        def jacobian(candidate, state_id):
            matrix, _groups = colored_central_difference_jacobian(
                lambda trial, trial_id: objective(trial, trial_id).scaled,
                candidate, pattern=pattern, step=float(payload["jacobian_step"]),
                state_id=state_id,
            )
            return matrix
        return jacobian

    lower = np.full(point.shape, -np.inf)
    upper = np.full(point.shape, np.inf)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    lower[-2:] = np.log(product_low)
    upper[-2:] = np.log(product_high)
    coarse_objective = make_objective(inventory, top_u, lower_u, memory, 1.0)
    half1_objective = make_objective(inventory, top_u, lower_u, memory, 0.5)
    coarse = solve_modified_newton(coarse_objective, make_jacobian(coarse_objective), point, settings, lower_bounds=lower, upper_bounds=upper, name="dd132:coarse")
    half1 = solve_modified_newton(half1_objective, make_jacobian(half1_objective), point, settings, lower_bounds=lower, upper_bounds=upper, name="dd132:half1")
    first = half1.final_evaluation
    half2_objective = make_objective(
        first.base.endpoint_inventory_lbmol,
        first.base.endpoint_top_internal_energy_BTU,
        first.base.endpoint_lower_internal_energy_BTU,
        first.endpoint_controller_memory, 0.5,
    )
    half2 = solve_modified_newton(half2_objective, make_jacobian(half2_objective), half1.final_coordinates, settings, lower_bounds=lower, upper_bounds=upper, name="dd132:half2")
    outcomes = {"coarse": coarse, "half1": half1, "half2": half2}
    elapsed = time.perf_counter() - started

    def compare(name, outcome):
        saved = payload["saved_dd130_outcomes"][name]
        evaluation = outcome.final_evaluation
        saved_inventory = np.asarray(saved["inventory_lbmol"], dtype=float)
        saved_energy = np.concatenate(([saved["top_internal_energy_BTU"]], saved["lower_internal_energy_BTU"]))
        live_energy = np.concatenate(([evaluation.base.endpoint_top_internal_energy_BTU], evaluation.base.endpoint_lower_internal_energy_BTU))
        return {
            "inventory": float(np.max(np.abs(evaluation.base.endpoint_inventory_lbmol - saved_inventory) / np.maximum(np.abs(saved_inventory), 1.0))),
            "energy": float(np.max(np.abs(live_energy - saved_energy) / np.maximum(np.abs(saved_energy), 1.0))),
            "memory": float(np.max(np.abs(evaluation.endpoint_controller_memory - np.asarray(saved["controller_memory"])) )),
            "level": float(np.max(np.abs(evaluation.level_fraction - np.asarray(saved["level_fraction"])) )),
            "product": max(abs(evaluation.distillate_lbmolph - saved["distillate_lbmolph"]) / saved["distillate_lbmolph"], abs(evaluation.bottoms_lbmolph - saved["bottoms_lbmolph"]) / saved["bottoms_lbmolph"]),
            "coordinates": float(np.max(np.abs(outcome.final_coordinates - np.asarray(saved["final_coordinates"])) / np.maximum(np.abs(saved["final_coordinates"]), 1.0))),
        }

    reproduction = {name: compare(name, outcome) for name, outcome in outcomes.items()}
    refined = half2.final_evaluation
    coarse_eval = coarse.final_evaluation
    initial_energy = np.concatenate(([top_u], lower_u))
    coarse_energy = np.concatenate(([coarse_eval.base.endpoint_top_internal_energy_BTU], coarse_eval.base.endpoint_lower_internal_energy_BTU))
    refined_energy = np.concatenate(([refined.base.endpoint_top_internal_energy_BTU], refined.base.endpoint_lower_internal_energy_BTU))
    refinement = {
        "inventory": float(np.max(np.abs(coarse_eval.base.endpoint_inventory_lbmol - refined.base.endpoint_inventory_lbmol) / np.maximum(inventory, 1.0))),
        "energy": float(np.max(np.abs(coarse_energy - refined_energy) / np.maximum(np.abs(initial_energy), 1.0))),
        "memory": float(np.max(np.abs(coarse_eval.endpoint_controller_memory - refined.endpoint_controller_memory))),
        "coordinates": float(np.max(np.abs(coarse.final_coordinates - half2.final_coordinates) / np.maximum(np.abs(point), 1.0))),
        "product": max(abs(coarse_eval.distillate_lbmolph - refined.distillate_lbmolph) / payload["expected_distillate_lbmolph"], abs(coarse_eval.bottoms_lbmolph - refined.bottoms_lbmolph) / payload["expected_bottoms_lbmolph"]),
        "level": float(np.max(np.abs(coarse_eval.level_fraction - refined.level_fraction))),
    }
    terminal_accumulation = np.asarray((np.sum(coarse_eval.base.component_rate_lbmolph[0]), np.sum(coarse_eval.base.component_rate_lbmolph[-1])))
    signal = {
        "distillate_relative_change": (coarse_eval.distillate_lbmolph - payload["expected_distillate_lbmolph"]) / payload["expected_distillate_lbmolph"],
        "bottoms_relative_change": (coarse_eval.bottoms_lbmolph - payload["expected_bottoms_lbmolph"]) / payload["expected_bottoms_lbmolph"],
        "controller_rate_per_sec": _vector(coarse_eval.controller_rate_per_sec),
        "terminal_accumulation_lbmolph": _vector(terminal_accumulation),
    }

    def kinematic(outcome, seconds):
        evaluation = outcome.final_evaluation
        hours = seconds / 3600.0
        component = float(np.max(np.abs(evaluation.base.endpoint_inventory_lbmol - evaluation.base.previous_inventory_lbmol - hours * evaluation.base.component_rate_lbmolph) / np.maximum(np.abs(evaluation.base.endpoint_inventory_lbmol), 1.0)))
        previous_energy = np.concatenate(([evaluation.base.previous_top_internal_energy_BTU], evaluation.base.previous_lower_internal_energy_BTU))
        endpoint_energy = np.concatenate(([evaluation.base.endpoint_top_internal_energy_BTU], evaluation.base.endpoint_lower_internal_energy_BTU))
        energy = float(np.max(np.abs(endpoint_energy - previous_energy - hours * evaluation.base.internal_energy_rate_BTUph) / np.maximum(np.abs(endpoint_energy), 1.0)))
        controller = float(np.max(np.abs(evaluation.endpoint_controller_memory - evaluation.previous_controller_memory - seconds * evaluation.controller_rate_per_sec)))
        return {"component": component, "energy": energy, "controller": controller}

    kinematics = {name: kinematic(outcome, 1.0 if name == "coarse" else 0.5) for name, outcome in outcomes.items()}
    physical = [item.final_evaluation.base.dae_evaluation.pressure_evaluation.base_evaluation.physical_state for item in outcomes.values()]
    pressure = [item.final_evaluation.base.dae_evaluation.pressure_evaluation.pressure_psia for item in outcomes.values()]
    steady = [item.final_evaluation.base.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation for item in outcomes.values()]
    provenance = call_audit.report()
    gates = {
        "solver_success": all(item.success for item in outcomes.values()),
        "residual": all(item.final_residual_inf_norm < payload["residual_limit"] for item in outcomes.values()),
        "single_jacobian_factorization": all(item.jacobian_evaluations == 1 and item.jacobian_rank == payload["required_rank"] and item.jacobian_condition < payload["algorithm"]["condition_limit"] for item in outcomes.values()),
        "endpoint_reproduction": all(max(values.values()) < payload["endpoint_reproduction_limit"] for values in reproduction.values()),
        "controller_direction": bool(signal["distillate_relative_change"] < 0.0 and signal["bottoms_relative_change"] < 0.0 and np.all(coarse_eval.controller_rate_per_sec < 0.0) and np.all(terminal_accumulation > 0.0)),
        "movement_signal": bool(max(abs(signal["distillate_relative_change"]), abs(signal["bottoms_relative_change"])) > payload["minimum_product_signal_relative"] and np.max(np.abs(coarse_eval.controller_rate_per_sec)) > payload["minimum_controller_rate_signal_per_sec"] and np.max(terminal_accumulation) > payload["minimum_terminal_accumulation_lbmolph"]),
        "refinement": bool(refinement["inventory"] < payload["inventory_refinement_limit"] and refinement["energy"] < payload["energy_refinement_limit"] and refinement["memory"] < payload["memory_refinement_limit"] and refinement["coordinates"] < payload["coordinate_refinement_limit"] and refinement["product"] < payload["product_refinement_limit"] and refinement["level"] < payload["level_refinement_limit"]),
        "discrete_kinematics": all(max(values.values()) < payload["discrete_kinematic_limit"] for values in kinematics.values()),
        "pressure_order": all(np.all(np.diff(item) > 0.0) for item in pressure),
        "physical": all(np.all(item.final_evaluation.base.endpoint_inventory_lbmol > 0.0) and np.all((item.final_evaluation.level_fraction > 0.01) & (item.final_evaluation.level_fraction < 0.99)) for item in outcomes.values()) and all(np.all(np.asarray(item.hydraulic_liquid_flow_lbmolph) > 0.0) and np.all(np.asarray(item.vapor_flow_lbmolph) > 0.0) for item in physical),
        "conservation": all(abs(item.component_telescoping_relative_error) < payload["component_conservation_limit"] and abs(item.energy_telescoping_relative_error) < payload["energy_conservation_limit"] for item in steady),
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_rebuild_fallback_retry_or_trajectory": True,
    }
    passed = all(gates.values())

    def record(name, outcome):
        evaluation = outcome.final_evaluation
        return {
            "name": name, "success": outcome.success, "message": outcome.message,
            "iterations": outcome.iterations,
            "residual_evaluations": outcome.residual_evaluations,
            "jacobian_evaluations": outcome.jacobian_evaluations,
            "linear_solves": outcome.linear_solves,
            "rejected_line_search_steps": outcome.rejected_line_search_steps,
            "rejected_bound_steps": outcome.rejected_bound_steps,
            "residual_inf_norm": outcome.final_residual_inf_norm,
            "jacobian_rank": outcome.jacobian_rank,
            "jacobian_condition": outcome.jacobian_condition,
            "final_coordinates": _vector(outcome.final_coordinates),
            "inventory_lbmol": np.asarray(evaluation.base.endpoint_inventory_lbmol).tolist(),
            "top_internal_energy_BTU": evaluation.base.endpoint_top_internal_energy_BTU,
            "lower_internal_energy_BTU": _vector(evaluation.base.endpoint_lower_internal_energy_BTU),
            "controller_memory": _vector(evaluation.endpoint_controller_memory),
            "level_fraction": _vector(evaluation.level_fraction),
            "distillate_lbmolph": evaluation.distillate_lbmolph,
            "bottoms_lbmolph": evaluation.bottoms_lbmolph,
        }

    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd132_passed" if passed else "dd132_failed",
        "decision": "authorize_frozen_controlled_terminal_short_trajectory_contract" if passed else "stop_modified_newton_live_path",
        "outcomes": {name: record(name, outcome) for name, outcome in outcomes.items()},
        "endpoint_reproduction": reproduction,
        "movement_signal": signal,
        "refinement": refinement,
        "discrete_kinematics": kinematics,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(passed),
        "jacobian_rebuild_attempted": False,
        "fallback_attempted": False,
        "retry_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text("\n".join((
        "# DD-132 Modified-Newton Live Efficiency Result", "",
        f"- Classification: `{result['classification']}`",
        f"- Decision: `{result['decision']}`",
        f"- Iterations: `{[item['iterations'] for item in result['outcomes'].values()]}`",
        f"- Jacobian builds: `{[item['jacobian_evaluations'] for item in result['outcomes'].values()]}`",
        f"- Worst residual: `{max(item['residual_inf_norm'] for item in result['outcomes'].values()):.6e}`",
        f"- Worst endpoint reproduction: `{max(max(item.values()) for item in reproduction.values()):.6e}`",
        f"- DWSIM calls: `{provenance['total_calls']}`",
        f"- Wall clock: `{elapsed:.3f} s`", "",
        "No Jacobian rebuild, fallback, retry, or trajectory was attempted.", "",
    )), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    output = prepare() if args.mode == "prepare" else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.mode == "prepare" or output["pass"] else 2)


if __name__ == "__main__":
    main()
