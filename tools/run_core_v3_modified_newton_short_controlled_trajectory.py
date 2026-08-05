#!/usr/bin/env python
"""Prepare or execute the frozen DD-134 short controlled trajectory."""

from __future__ import annotations

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

import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_trajectory_v1 import (
    run_controlled_terminal_trajectory,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    evaluate_controlled_terminal_zero_time,
)
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings


SCHEMA = "dd134-core-v3-modified-newton-short-controlled-trajectory-contract-v1"
RESULT_SCHEMA = "dd134-core-v3-modified-newton-short-controlled-trajectory-result-v1"
DD132_CONTRACT = Path("logs/dd132_core_v3_modified_newton_live_efficiency_contract_20260805.json")
DD132_RESULT = Path("logs/dd132_core_v3_modified_newton_live_efficiency_20260805.json")
DD133_CONTRACT = Path("logs/dd133_core_v3_dd132_physical_equivalence_adjudication_contract_20260805.json")
DD133_RESULT = Path("logs/dd133_core_v3_dd132_physical_equivalence_adjudication_20260805.json")
CONTRACT = Path("logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json")
RESULT = Path("logs/dd134_core_v3_modified_newton_short_controlled_trajectory_20260805.json")
CONTRACT_DOC = Path("docs/dd_134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.md")
RESULT_DOC = Path("docs/dd_134_core_v3_modified_newton_short_controlled_trajectory_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_trajectory_v1.py",
    "src/dynamic_distillation/core_v3/modified_newton_v1.py",
    "tests/test_core_v3_controlled_terminal_trajectory_v1.py",
    "tests/test_core_v3_modified_newton_v1.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
    "tools/run_core_v3_controlled_terminal_first_step.py",
    "tools/run_core_v3_modified_newton_short_controlled_trajectory.py",
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
    source = _load(DD132_CONTRACT)
    dd132 = _load(DD132_RESULT)
    dd133 = _load(DD133_RESULT)
    if (
        not dd133["pass"]
        or dd133["decision"]
        != "authorize_frozen_modified_newton_short_controlled_trajectory_contract"
    ):
        raise RuntimeError("DD-134 requires the passed DD-133 authorization")
    if sorted(key for key, value in dd132["gates"].items() if not value) != [
        "endpoint_reproduction"
    ]:
        raise RuntimeError("DD-134 requires DD-132's reproduction-only failure")
    contract = dd128._contract(source)
    pattern = controlled_terminal_step_pattern(contract)
    if pattern.shape != (50, 50):
        raise RuntimeError("DD-134 requires the frozen 50 x 50 controlled structure")
    copied = (
        "workbook",
        "workbook_sha256",
        "property_package",
        "source_mapping",
        "operating_spec",
        "reference",
        "accepted_root_state",
        "initializer_numerical",
        "top_storage_gradient_BTU_lbmol",
        "energy_rate_scales_BTUph",
        "storage_scales_BTU",
        "fixed_steady_residual_scales",
        "pressure_reference_psia",
        "pressure_coordinate_scale_psia",
        "pressure_residual_scale_psia",
        "dry_tray_pressure_drop_coefficient",
        "pressure_link_geometry",
        "geometry",
        "controllers",
        "inventory_lbmol",
        "lower_internal_energy_BTU",
        "controller_memory",
        "zero_time_coordinates",
        "expected_distillate_lbmolph",
        "expected_bottoms_lbmolph",
        "original_level_setpoints",
        "moved_level_setpoints",
        "setpoint_multiplier",
        "disturbance_definition",
        "component_rate_scale_lbmolph",
        "residual_limit",
        "component_conservation_limit",
        "energy_conservation_limit",
        "discrete_kinematic_limit",
    )
    sources = (DD132_CONTRACT, DD132_RESULT, DD133_CONTRACT, DD133_RESULT)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path) for path in sources
        },
        **{key: source[key] for key in copied},
        "saved_dd132_first_step": dd132["outcomes"]["coarse"],
        "algorithm": source["algorithm"],
        "jacobian_step": float(source["jacobian_step"]),
        "step_pattern_shape": list(pattern.shape),
        "step_color_count": int(source["step_color_count"]),
        "required_rank": 50,
        "trajectory_grid": {
            "duration_seconds": 10.0,
            "coarse_step_seconds": 1.0,
            "coarse_steps": 10,
            "refined_step_seconds": 0.5,
            "refined_steps": 20,
        },
        "first_step_reproduction_limits": {
            "inventory": 2.0e-7,
            "energy": 2.0e-7,
            "memory": 2.0e-7,
            "level": 2.0e-7,
            "product": 1.0e-7,
        },
        "endpoint_refinement_limits": {
            "inventory": 5.0e-6,
            "energy": 5.0e-6,
            "memory": 5.0e-6,
            "coordinates": 5.0e-4,
            "product": 1.0e-5,
            "level": 1.0e-6,
        },
        "minimum_endpoint_product_change_relative": 1.0e-4,
        "provider_call_limit": 80000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-132 or DD-133 source or implementation hash changes",
            "either the 10 x 1.0 second or 20 x 0.5 second path is incomplete",
            "any root uses other than one colored Jacobian and one factorization",
            "any root, first-step reproduction, refinement, direction, kinematic, pressure, physical, conservation, provider, call, or wall gate fails",
            "any product or controller memory reverses the commanded direction",
            "either terminal endpoint fails to move closer to its raised level setpoint",
            "a Jacobian rebuild, alternate solver, clipping, projection, fallback, retry, changed disturbance, or changed grid occurs",
            "any execution is attempted before explicit post-contract authorization",
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
                "# DD-134 Frozen Modified-Newton Short Controlled-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Initial state and disturbance: exact DD-132",
                "- Duration: `10 s`",
                "- Grids: `10 x 1.0 s` and `20 x 0.5 s`",
                "- Solver: one frozen 21-color Jacobian and one LU factorization per root",
                "- Provider-call limit: `<80000`",
                "- Wall-clock limit: `<180 s`",
                "- Rebuild, fallback, retry, clipping, projection, or changed grid: `False`",
                "",
                "This commit freezes the contract only. Trajectory execution requires explicit authorization after the contract commit is reviewed.",
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
        raise RuntimeError("DD-134 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-134 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-134 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-134 result already exists")
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
    settings = ModifiedNewtonSettings(
        **{
            key: payload["algorithm"][key]
            for key in (
                "residual_tolerance",
                "max_iterations",
                "line_search_fractions",
                "armijo_fraction",
                "condition_limit",
            )
        }
    )
    lower = np.full(point.shape, -np.inf)
    upper = np.full(point.shape, np.inf)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    lower[-2:] = np.log(product_low)
    upper[-2:] = np.log(product_high)
    step_common = {
        "component_rate_scale_lbmolph": float(payload["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }

    started = time.perf_counter()
    zero = evaluate_controlled_terminal_zero_time(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        controller_memory=memory,
        level_setpoints=original_setpoints,
        solve_coordinates=point,
        state_id="dd134:initial_state",
        evaluation_kind="residual",
        **common,
    )
    top_u = float(zero.base.live_internal_energy_BTU[0])

    def objective_factory(previous_n, previous_top_u, previous_lower_u, previous_memory, seconds):
        def objective(candidate, state_id):
            return evaluate_controlled_terminal_backward_euler_residual(
                contract,
                spec,
                reference,
                template,
                provider,
                call_audit,
                previous_inventory_lbmol=previous_n,
                previous_top_internal_energy_BTU=previous_top_u,
                previous_lower_internal_energy_BTU=previous_lower_u,
                previous_controller_memory=previous_memory,
                level_setpoints=moved_setpoints,
                solve_coordinates=candidate,
                step_seconds=seconds,
                state_id=state_id,
                evaluation_kind="jacobian" if "jacobian" in state_id else "residual",
                **step_common,
            )

        return objective

    def jacobian_factory(objective):
        def jacobian(candidate, state_id):
            matrix, _groups = colored_central_difference_jacobian(
                lambda trial, trial_id: objective(trial, trial_id).scaled,
                candidate,
                pattern=pattern,
                step=float(payload["jacobian_step"]),
                state_id=state_id,
            )
            return matrix

        return jacobian

    grid = payload["trajectory_grid"]
    common_trajectory = {
        "objective_factory": objective_factory,
        "jacobian_factory": jacobian_factory,
        "initial_inventory_lbmol": inventory,
        "initial_top_internal_energy_BTU": top_u,
        "initial_lower_internal_energy_BTU": lower_u,
        "initial_controller_memory": memory,
        "initial_coordinates": point,
        "lower_bounds": lower,
        "upper_bounds": upper,
        "duration_seconds": float(grid["duration_seconds"]),
        "settings": settings,
    }
    coarse = run_controlled_terminal_trajectory(
        **common_trajectory,
        step_seconds=float(grid["coarse_step_seconds"]),
        name="dd134:coarse",
    )
    refined = run_controlled_terminal_trajectory(
        **common_trajectory,
        step_seconds=float(grid["refined_step_seconds"]),
        name="dd134:refined",
    )
    elapsed = time.perf_counter() - started
    trajectories = (coarse, refined)
    all_steps = tuple(step for trajectory in trajectories for step in trajectory.steps)

    def endpoint_values(trajectory):
        outcome = trajectory.endpoint_outcome
        evaluation = outcome.final_evaluation
        energy = np.concatenate(
            (
                [evaluation.base.endpoint_top_internal_energy_BTU],
                evaluation.base.endpoint_lower_internal_energy_BTU,
            )
        )
        return outcome, evaluation, energy

    coarse_outcome, coarse_eval, coarse_energy = endpoint_values(coarse)
    refined_outcome, refined_eval, refined_energy = endpoint_values(refined)
    initial_energy = np.concatenate(([top_u], lower_u))
    refinement = {
        "inventory": float(
            np.max(
                np.abs(
                    coarse_eval.base.endpoint_inventory_lbmol
                    - refined_eval.base.endpoint_inventory_lbmol
                )
                / np.maximum(np.abs(inventory), 1.0)
            )
        ),
        "energy": float(
            np.max(np.abs(coarse_energy - refined_energy) / np.maximum(np.abs(initial_energy), 1.0))
        ),
        "memory": float(
            np.max(
                np.abs(
                    coarse_eval.endpoint_controller_memory
                    - refined_eval.endpoint_controller_memory
                )
            )
        ),
        "coordinates": float(
            np.max(
                np.abs(coarse_outcome.final_coordinates - refined_outcome.final_coordinates)
                / np.maximum(np.abs(point), 1.0)
            )
        ),
        "product": max(
            abs(coarse_eval.distillate_lbmolph - refined_eval.distillate_lbmolph)
            / payload["expected_distillate_lbmolph"],
            abs(coarse_eval.bottoms_lbmolph - refined_eval.bottoms_lbmolph)
            / payload["expected_bottoms_lbmolph"],
        ),
        "level": float(np.max(np.abs(coarse_eval.level_fraction - refined_eval.level_fraction))),
    }

    saved = payload["saved_dd132_first_step"]
    first = coarse.steps[0].outcome
    first_eval = first.final_evaluation
    saved_energy = np.concatenate(
        ([saved["top_internal_energy_BTU"]], saved["lower_internal_energy_BTU"])
    )
    first_energy = np.concatenate(
        ([first_eval.base.endpoint_top_internal_energy_BTU], first_eval.base.endpoint_lower_internal_energy_BTU)
    )
    first_reproduction = {
        "inventory": float(
            np.max(
                np.abs(first_eval.base.endpoint_inventory_lbmol - np.asarray(saved["inventory_lbmol"]))
                / np.maximum(np.abs(np.asarray(saved["inventory_lbmol"])), 1.0)
            )
        ),
        "energy": float(
            np.max(np.abs(first_energy - saved_energy) / np.maximum(np.abs(saved_energy), 1.0))
        ),
        "memory": float(
            np.max(np.abs(first_eval.endpoint_controller_memory - np.asarray(saved["controller_memory"])))
        ),
        "level": float(np.max(np.abs(first_eval.level_fraction - np.asarray(saved["level_fraction"])))),
        "product": max(
            abs(first_eval.distillate_lbmolph - saved["distillate_lbmolph"])
            / saved["distillate_lbmolph"],
            abs(first_eval.bottoms_lbmolph - saved["bottoms_lbmolph"])
            / saved["bottoms_lbmolph"],
        ),
    }

    def kinematic(step, seconds):
        evaluation = step.outcome.final_evaluation
        step_hours = seconds / 3600.0
        component = float(
            np.max(
                np.abs(
                    evaluation.base.endpoint_inventory_lbmol
                    - evaluation.base.previous_inventory_lbmol
                    - step_hours * evaluation.base.component_rate_lbmolph
                )
                / np.maximum(np.abs(evaluation.base.endpoint_inventory_lbmol), 1.0)
            )
        )
        previous_energy = np.concatenate(
            ([evaluation.base.previous_top_internal_energy_BTU], evaluation.base.previous_lower_internal_energy_BTU)
        )
        endpoint_energy = np.concatenate(
            ([evaluation.base.endpoint_top_internal_energy_BTU], evaluation.base.endpoint_lower_internal_energy_BTU)
        )
        energy = float(
            np.max(
                np.abs(endpoint_energy - previous_energy - step_hours * evaluation.base.internal_energy_rate_BTUph)
                / np.maximum(np.abs(endpoint_energy), 1.0)
            )
        )
        controller = float(
            np.max(
                np.abs(
                    evaluation.endpoint_controller_memory
                    - evaluation.previous_controller_memory
                    - seconds * evaluation.controller_rate_per_sec
                )
            )
        )
        return {"component": component, "energy": energy, "controller": controller}

    kinematics = {
        f"{trajectory.name}:{step.index}": kinematic(step, trajectory.step_seconds)
        for trajectory in trajectories
        for step in trajectory.steps
    }
    initial_moved_error = np.asarray(zero.level_fraction) - np.asarray(
        (moved_setpoints.drum_fraction, moved_setpoints.sump_fraction)
    )
    direction = {
        "coarse_product_relative": [
            (coarse_eval.distillate_lbmolph - payload["expected_distillate_lbmolph"])
            / payload["expected_distillate_lbmolph"],
            (coarse_eval.bottoms_lbmolph - payload["expected_bottoms_lbmolph"])
            / payload["expected_bottoms_lbmolph"],
        ],
        "refined_product_relative": [
            (refined_eval.distillate_lbmolph - payload["expected_distillate_lbmolph"])
            / payload["expected_distillate_lbmolph"],
            (refined_eval.bottoms_lbmolph - payload["expected_bottoms_lbmolph"])
            / payload["expected_bottoms_lbmolph"],
        ],
        "coarse_level_error": _vector(coarse_eval.level_error),
        "refined_level_error": _vector(refined_eval.level_error),
        "initial_moved_level_error": _vector(initial_moved_error),
        "coarse_controller_memory_change": _vector(coarse_eval.endpoint_controller_memory - memory),
        "refined_controller_memory_change": _vector(refined_eval.endpoint_controller_memory - memory),
    }
    evaluations = tuple(step.outcome.final_evaluation for step in all_steps)
    physical = tuple(
        item.base.dae_evaluation.pressure_evaluation.base_evaluation.physical_state
        for item in evaluations
    )
    pressure = tuple(
        item.base.dae_evaluation.pressure_evaluation.pressure_psia for item in evaluations
    )
    steady = tuple(
        item.base.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
        for item in evaluations
    )
    provenance = call_audit.report()
    first_limits = payload["first_step_reproduction_limits"]
    refinement_limits = payload["endpoint_refinement_limits"]
    all_product_below_initial = all(
        item.distillate_lbmolph < payload["expected_distillate_lbmolph"]
        and item.bottoms_lbmolph < payload["expected_bottoms_lbmolph"]
        for item in evaluations
    )
    all_memory_below_initial = all(
        np.all(item.endpoint_controller_memory < memory) for item in evaluations
    )
    gates = {
        "trajectory_complete": bool(
            coarse.completed
            and refined.completed
            and coarse.completed_steps == grid["coarse_steps"]
            and refined.completed_steps == grid["refined_steps"]
        ),
        "solver_success": all(step.outcome.success for step in all_steps),
        "residual": all(
            step.outcome.final_residual_inf_norm < payload["residual_limit"] for step in all_steps
        ),
        "single_jacobian_factorization": all(
            step.outcome.jacobian_evaluations == 1
            and step.outcome.jacobian_rank == payload["required_rank"]
            and step.outcome.jacobian_condition < payload["algorithm"]["condition_limit"]
            for step in all_steps
        ),
        "first_step_reproduction": all(
            value < first_limits[key] for key, value in first_reproduction.items()
        ),
        "endpoint_refinement": all(
            value < refinement_limits[key] for key, value in refinement.items()
        ),
        "controller_direction": bool(
            all_product_below_initial
            and all_memory_below_initial
            and np.all(np.abs(coarse_eval.level_error) < np.abs(initial_moved_error))
            and np.all(np.abs(refined_eval.level_error) < np.abs(initial_moved_error))
            and max(abs(value) for value in direction["coarse_product_relative"])
            > payload["minimum_endpoint_product_change_relative"]
            and max(abs(value) for value in direction["refined_product_relative"])
            > payload["minimum_endpoint_product_change_relative"]
        ),
        "discrete_kinematics": all(
            max(values.values()) < payload["discrete_kinematic_limit"]
            for values in kinematics.values()
        ),
        "pressure_order": all(np.all(np.diff(item) > 0.0) for item in pressure),
        "physical": all(
            np.all(item.base.endpoint_inventory_lbmol > 0.0)
            and np.all((item.level_fraction > 0.01) & (item.level_fraction < 0.99))
            for item in evaluations
        )
        and all(
            np.all(np.asarray(item.hydraulic_liquid_flow_lbmolph) > 0.0)
            and np.all(np.asarray(item.vapor_flow_lbmolph) > 0.0)
            for item in physical
        ),
        "conservation": all(
            abs(item.component_telescoping_relative_error)
            < payload["component_conservation_limit"]
            and abs(item.energy_telescoping_relative_error)
            < payload["energy_conservation_limit"]
            for item in steady
        ),
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_rebuild_fallback_retry_or_grid_change": True,
    }
    passed = all(bool(value) for value in gates.values())

    def step_record(step):
        outcome = step.outcome
        evaluation = outcome.final_evaluation
        return {
            "index": step.index,
            "time_seconds": step.time_seconds,
            "success": outcome.success,
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
            "controller_rate_per_sec": _vector(evaluation.controller_rate_per_sec),
            "level_fraction": _vector(evaluation.level_fraction),
            "level_error": _vector(evaluation.level_error),
            "distillate_lbmolph": evaluation.distillate_lbmolph,
            "bottoms_lbmolph": evaluation.bottoms_lbmolph,
        }

    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd134_passed" if passed else "dd134_failed",
        "decision": (
            "authorize_separately_frozen_controlled_trajectory_extension_contract"
            if passed
            else "stop_modified_newton_controlled_trajectory_path"
        ),
        "trajectories": {
            "coarse": [step_record(step) for step in coarse.steps],
            "refined": [step_record(step) for step in refined.steps],
        },
        "first_step_reproduction": first_reproduction,
        "endpoint_refinement": refinement,
        "direction": direction,
        "discrete_kinematics": kinematics,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(passed),
        "jacobian_rebuild_attempted": False,
        "fallback_attempted": False,
        "retry_attempted": False,
        "grid_changed": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-134 Modified-Newton Short Controlled-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Completed steps: `{coarse.completed_steps} / {refined.completed_steps}`",
                f"- Worst residual: `{max(step.outcome.final_residual_inf_norm for step in all_steps):.6e}`",
                f"- DWSIM calls: `{provenance['total_calls']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                "",
                "No rebuild, fallback, retry, or grid change was attempted.",
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
