#!/usr/bin/env python
"""Prepare or execute the frozen DD-128 controlled-terminal root-hold step."""

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
    greedy_column_groups,
)
from dynamic_distillation.core_v3.controlled_terminal_dynamic_contract_v1 import (
    LevelControllerSpecification,
    TerminalGeometry,
    build_controlled_terminal_dynamic_contract,
)
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
    solve_controlled_terminal_backward_euler_step,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    evaluate_controlled_terminal_zero_time,
)
from dynamic_distillation.core_v3.implicit_step_v1 import ImplicitStepSettings


SCHEMA = "dd128-core-v3-controlled-terminal-first-step-contract-v1"
RESULT_SCHEMA = "dd128-core-v3-controlled-terminal-first-step-result-v1"
DD127_CONTRACT = Path("logs/dd127_core_v3_controlled_terminal_jacobian_contract_20260805.json")
DD127_RESULT = Path("logs/dd127_core_v3_controlled_terminal_jacobian_20260805.json")
CONTRACT = Path("logs/dd128_core_v3_controlled_terminal_first_step_contract_20260805.json")
RESULT = Path("logs/dd128_core_v3_controlled_terminal_first_step_20260805.json")
CONTRACT_DOC = Path("docs/dd_128_core_v3_controlled_terminal_first_step_contract_20260805.md")
RESULT_DOC = Path("docs/dd_128_core_v3_controlled_terminal_first_step_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_zero_time_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_implicit_step_v1.py",
    "tests/test_core_v3_controlled_terminal_implicit_step_v1.py",
    "tools/run_core_v3_controlled_terminal_first_step.py",
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


def _contract(payload: Mapping[str, Any]):
    return build_controlled_terminal_dynamic_contract(
        tuple(payload["source_mapping"]["component_names"]),
        geometry=TerminalGeometry(**payload["geometry"]),
        controllers=LevelControllerSpecification(**payload["controllers"]),
    )


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def prepare() -> dict[str, Any]:
    source = _load(DD127_CONTRACT)
    result = _load(DD127_RESULT)
    if (
        not result["pass"]
        or result["decision"] != "authorize_frozen_controlled_terminal_first_step_contract"
    ):
        raise RuntimeError("DD-128 requires the passed DD-127 authorization")
    contract = _contract(source)
    pattern = controlled_terminal_step_pattern(contract)
    if pattern.shape != (50, 50) or structural_rank(csr_matrix(pattern)) != 50:
        raise RuntimeError("DD-128 finite-step pattern is not full rank")
    settings = ImplicitStepSettings(
        method="trf",
        ftol=1.0e-12,
        xtol=1.0e-12,
        gtol=1.0e-12,
        max_nfev=20,
        x_scale=1.0,
        jacobian_step=1.0e-5,
        jacobian_mode="colored",
    )
    copied = (
        "workbook", "workbook_sha256", "property_package", "source_mapping",
        "operating_spec", "reference", "accepted_root_state",
        "initializer_numerical", "top_storage_gradient_BTU_lbmol",
        "energy_rate_scales_BTUph", "storage_scales_BTU",
        "fixed_steady_residual_scales", "pressure_reference_psia",
        "pressure_coordinate_scale_psia", "pressure_residual_scale_psia",
        "dry_tray_pressure_drop_coefficient", "pressure_link_geometry",
        "geometry", "controllers", "inventory_lbmol",
        "lower_internal_energy_BTU", "controller_memory", "level_setpoints",
        "zero_time_coordinates", "expected_distillate_lbmolph",
        "expected_bottoms_lbmolph", "variable_names", "row_names",
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD127_CONTRACT, DD127_RESULT)
        },
        **{key: source[key] for key in copied},
        "grid": {"coarse": [1.0], "refined": [0.5, 0.5], "endpoint_sec": 1.0},
        "top_internal_energy_rule": "evaluate the accepted zero-time state once and use its derived reflux-drum internal energy as the previous state",
        "component_rate_scale_lbmolph": 12584.8,
        "solver": asdict(settings),
        "step_pattern_shape": list(pattern.shape),
        "step_structural_rank": int(structural_rank(csr_matrix(pattern))),
        "step_color_count": len(greedy_column_groups(pattern)),
        "jacobian_steps": [1.0e-5, 5.0e-6],
        "required_rank": 50,
        "residual_limit": 1.0e-8,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "stationary_inventory_limit": 1.0e-10,
        "stationary_energy_limit": 1.0e-10,
        "stationary_memory_limit": 1.0e-10,
        "stationary_coordinate_limit": 1.0e-8,
        "stationary_product_relative_limit": 1.0e-10,
        "stationary_level_error_limit": 1.0e-10,
        "refinement_limit": 1.0e-8,
        "discrete_kinematic_limit": 1.0e-12,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "provider_call_limit": 20000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-127 source or frozen implementation hash changes",
            "any of the three precommitted roots fails or exceeds the residual limit",
            "the finite-step leading matrix loses rank or exceeds conditioning, spectrum, or registry limits",
            "the accepted stationary state moves above any frozen root-hold limit",
            "coarse and refined endpoints disagree above the frozen limit",
            "physicality, pressure, conservation, provider, call, or wall gates fail",
            "a retry, changed grid, perturbation, controller tuning, or trajectory is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "perturbation_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join((
            "# DD-128 Frozen Core V3 Controlled-Terminal First-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Grid: `1 x 1.0 s` versus `2 x 0.5 s`",
            "- System: controlled-terminal conserved `50 x 50` backward Euler",
            f"- Colored Jacobian groups: `{payload['step_color_count']}`",
            "- Initial condition: accepted DD-127 stationary root",
            "- Perturbation or trajectory: `False`",
            "",
            "Execution is permitted once only after this exact contract is committed. Passing authorizes only a separately frozen moving-step contract.",
            "",
        )),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-128 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-128 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-128 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-128 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _jacobian(objective, point, pattern, step, tolerance):
    matrix, groups = colored_central_difference_jacobian(
        objective, point, pattern=pattern, step=step,
        state_id=f"dd128:endpoint_jacobian:{step:g}",
    )
    singular = np.linalg.svd(matrix, compute_uv=False)
    cutoff = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > cutoff))
    condition = float(np.inf if singular[-1] <= cutoff else singular[0] / singular[-1])
    unexpected = [
        (int(row), int(column))
        for row, column in zip(*np.where((~pattern) & (np.abs(matrix) > tolerance)))
    ]
    return matrix, singular, rank, condition, len(groups), unexpected


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = dd121._context(payload)
    contract = _contract(payload)
    pattern = controlled_terminal_step_pattern(contract)
    point = np.asarray(payload["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(payload["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    settings = ImplicitStepSettings(**payload["solver"])
    started = time.perf_counter()
    zero = evaluate_controlled_terminal_zero_time(
        contract, spec, reference, template, provider, call_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        controller_memory=memory,
        level_setpoints=setpoints,
        solve_coordinates=point,
        state_id="dd128:initial_state",
        evaluation_kind="residual",
        **common,
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
                level_setpoints=setpoints,
                solve_coordinates=candidate,
                step_seconds=seconds,
                state_id=state_id,
                evaluation_kind="jacobian" if "jacobian" in state_id else "residual",
                **step_common,
            )
        return objective

    coarse_objective = make_objective(inventory, top_u, lower_u, memory, 1.0)
    half1_objective = make_objective(inventory, top_u, lower_u, memory, 0.5)
    coarse = solve_controlled_terminal_backward_euler_step(
        contract, coarse_objective, point, settings, name="dd128:coarse"
    )
    half1 = solve_controlled_terminal_backward_euler_step(
        contract, half1_objective, point, settings, name="dd128:half1"
    )
    first = half1.evaluation
    half2_objective = make_objective(
        first.base.endpoint_inventory_lbmol,
        first.base.endpoint_top_internal_energy_BTU,
        first.base.endpoint_lower_internal_energy_BTU,
        first.endpoint_controller_memory,
        0.5,
    )
    half2 = solve_controlled_terminal_backward_euler_step(
        contract, half2_objective, half1.final_coordinates, settings, name="dd128:half2"
    )
    audits = []
    matrices = []
    for step in payload["jacobian_steps"]:
        matrix, singular, rank, condition, colors, unexpected = _jacobian(
            lambda candidate, state_id: coarse_objective(candidate, state_id).scaled,
            coarse.final_coordinates, pattern, float(step),
            float(payload["coupling_tolerance"]),
        )
        matrices.append(matrix)
        audits.append({
            "step": float(step), "rank": rank, "condition": condition,
            "singular_values": _vector(singular), "color_count": colors,
            "unexpected_couplings": unexpected,
            "zero_rows": [int(i) for i in np.flatnonzero(np.max(np.abs(matrix), axis=1) <= payload["coupling_tolerance"])],
            "zero_columns": [int(i) for i in np.flatnonzero(np.max(np.abs(matrix), axis=0) <= payload["coupling_tolerance"])],
        })
    elapsed = time.perf_counter() - started
    outcomes = {"coarse": coarse, "half1": half1, "half2": half2}
    refined = half2.evaluation
    initial_energy = np.concatenate(([top_u], lower_u))
    coarse_energy = np.concatenate((
        [coarse.evaluation.base.endpoint_top_internal_energy_BTU],
        coarse.evaluation.base.endpoint_lower_internal_energy_BTU,
    ))
    energy_scale = np.maximum(np.abs(initial_energy), 1.0)
    coordinate_scale = np.maximum(np.abs(point), 1.0)
    stationary = {
        "inventory": float(np.max(np.abs(coarse.evaluation.base.endpoint_inventory_lbmol - inventory) / np.maximum(inventory, 1.0))),
        "energy": float(np.max(np.abs(coarse_energy - initial_energy) / energy_scale)),
        "memory": float(np.max(np.abs(coarse.evaluation.endpoint_controller_memory - memory))),
        "coordinates": float(np.max(np.abs(coarse.final_coordinates - point) / coordinate_scale)),
        "product_relative": max(
            abs(coarse.evaluation.distillate_lbmolph - payload["expected_distillate_lbmolph"]) / payload["expected_distillate_lbmolph"],
            abs(coarse.evaluation.bottoms_lbmolph - payload["expected_bottoms_lbmolph"]) / payload["expected_bottoms_lbmolph"],
        ),
        "level_error": float(np.max(np.abs(coarse.evaluation.level_error))),
    }
    refinement = {
        "inventory": float(np.max(np.abs(coarse.evaluation.base.endpoint_inventory_lbmol - refined.base.endpoint_inventory_lbmol) / np.maximum(inventory, 1.0))),
        "energy": float(np.max(np.abs(coarse_energy - np.concatenate(([refined.base.endpoint_top_internal_energy_BTU], refined.base.endpoint_lower_internal_energy_BTU))) / energy_scale)),
        "memory": float(np.max(np.abs(coarse.evaluation.endpoint_controller_memory - refined.endpoint_controller_memory))),
        "coordinates": float(np.max(np.abs(coarse.final_coordinates - half2.final_coordinates) / coordinate_scale)),
    }

    def kinematic(outcome, seconds):
        evaluation = outcome.evaluation
        hours = seconds / 3600.0
        component = float(np.max(np.abs(
            evaluation.base.endpoint_inventory_lbmol - evaluation.base.previous_inventory_lbmol
            - hours * evaluation.base.component_rate_lbmolph
        ) / np.maximum(np.abs(evaluation.base.endpoint_inventory_lbmol), 1.0)))
        energy_previous = np.concatenate(([evaluation.base.previous_top_internal_energy_BTU], evaluation.base.previous_lower_internal_energy_BTU))
        energy_endpoint = np.concatenate(([evaluation.base.endpoint_top_internal_energy_BTU], evaluation.base.endpoint_lower_internal_energy_BTU))
        energy = float(np.max(np.abs(
            energy_endpoint - energy_previous - hours * evaluation.base.internal_energy_rate_BTUph
        ) / np.maximum(np.abs(energy_endpoint), 1.0)))
        controller = float(np.max(np.abs(
            evaluation.endpoint_controller_memory - evaluation.previous_controller_memory
            - seconds * evaluation.controller_rate_per_sec
        )))
        return {"component": component, "energy": energy, "controller": controller}

    kinematics = {
        name: kinematic(outcome, 1.0 if name == "coarse" else 0.5)
        for name, outcome in outcomes.items()
    }
    physical = [
        item.evaluation.base.dae_evaluation.pressure_evaluation.base_evaluation.physical_state
        for item in outcomes.values()
    ]
    pressure = [
        item.evaluation.base.dae_evaluation.pressure_evaluation.pressure_psia
        for item in outcomes.values()
    ]
    steady = [
        item.evaluation.base.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
        for item in outcomes.values()
    ]
    provenance = call_audit.report()
    spectrum = _spectrum_change(
        np.asarray(audits[0]["singular_values"]), np.asarray(audits[1]["singular_values"])
    )
    gates = {
        "solver_success": all(item.success for item in outcomes.values()),
        "residual": all(item.final_scaled_residual_inf_norm < payload["residual_limit"] for item in outcomes.values()),
        "rank": all(item["rank"] == payload["required_rank"] for item in audits),
        "condition": all(item["condition"] < payload["condition_limit"] for item in audits),
        "spectrum": spectrum < payload["spectrum_change_limit"],
        "structure": all(not item["zero_rows"] and not item["zero_columns"] and not item["unexpected_couplings"] for item in audits),
        "stationary": bool(
            stationary["inventory"] < payload["stationary_inventory_limit"]
            and stationary["energy"] < payload["stationary_energy_limit"]
            and stationary["memory"] < payload["stationary_memory_limit"]
            and stationary["coordinates"] < payload["stationary_coordinate_limit"]
            and stationary["product_relative"] < payload["stationary_product_relative_limit"]
            and stationary["level_error"] < payload["stationary_level_error_limit"]
        ),
        "refinement": max(refinement.values()) < payload["refinement_limit"],
        "discrete_kinematics": all(max(item.values()) < payload["discrete_kinematic_limit"] for item in kinematics.values()),
        "pressure_order": all(np.all(np.diff(item) > 0.0) for item in pressure),
        "physical": all(np.all(item.evaluation.base.endpoint_inventory_lbmol > 0.0) and np.all((item.evaluation.level_fraction > 0.01) & (item.evaluation.level_fraction < 0.99)) for item in outcomes.values()) and all(np.all(np.asarray(item.hydraulic_liquid_flow_lbmolph) > 0.0) and np.all(np.asarray(item.vapor_flow_lbmolph) > 0.0) for item in physical),
        "conservation": all(abs(item.component_telescoping_relative_error) < payload["component_conservation_limit"] and abs(item.energy_telescoping_relative_error) < payload["energy_conservation_limit"] for item in steady),
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
        "no_perturbation_or_trajectory": True,
    }
    passed = all(gates.values())

    def record(name, outcome):
        evaluation = outcome.evaluation
        return {
            "name": name, "success": outcome.success, "status": outcome.status,
            "message": outcome.message, "nfev": outcome.nfev, "njev": outcome.njev,
            "wall_clock_sec": outcome.wall_clock_sec,
            "residual_inf_norm": outcome.final_scaled_residual_inf_norm,
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
        "classification": "dd128_passed" if passed else "dd128_failed",
        "decision": "authorize_frozen_controlled_terminal_moving_step_contract" if passed else "stop_controlled_terminal_dynamic_handoff",
        "initial_top_internal_energy_BTU": top_u,
        "outcomes": {name: record(name, outcome) for name, outcome in outcomes.items()},
        "jacobians": audits,
        "spectrum_change": spectrum,
        "stationary_motion": stationary,
        "refinement": refinement,
        "discrete_kinematics": kinematics,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": passed,
        "retry_attempted": False,
        "perturbation_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text("\n".join((
        "# DD-128 Core V3 Controlled-Terminal First-Step Result", "",
        f"- Classification: `{result['classification']}`",
        f"- Decision: `{result['decision']}`",
        f"- Worst residual: `{max(item.final_scaled_residual_inf_norm for item in outcomes.values()):.6e}`",
        f"- Worst stationary-motion metric: `{max(stationary.values()):.6e}`",
        f"- Worst refinement metric: `{max(refinement.values()):.6e}`",
        f"- Jacobian ranks: `{[item['rank'] for item in audits]}`",
        f"- Worst condition: `{max(item['condition'] for item in audits):.6e}`",
        f"- DWSIM calls: `{provenance['total_calls']}`",
        f"- Wall clock: `{elapsed:.3f} s`", "",
        "DD-128 performed only the frozen stationary root-hold comparison. No perturbation or trajectory was attempted.", "",
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
