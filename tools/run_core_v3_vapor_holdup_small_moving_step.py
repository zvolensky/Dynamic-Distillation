#!/usr/bin/env python
"""Prepare or execute the frozen DD-249 vapor-holdup moving-step gate."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_stationary_hold as dd248  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitEvaluation,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)


SCHEMA = "dd249-core-v3-c3c4-vapor-holdup-small-moving-step-contract-v1"
RESULT_SCHEMA = "dd249-core-v3-c3c4-vapor-holdup-small-moving-step-result-v1"
CONTRACT = Path(
    "logs/dd249_core_v3_c3c4_vapor_holdup_small_moving_step_contract_20260820.json"
)
RESULT = Path(
    "logs/dd249_core_v3_c3c4_vapor_holdup_small_moving_step_20260820.json"
)
CONTRACT_DOC = Path(
    "docs/dd_249_core_v3_c3c4_vapor_holdup_small_moving_step_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_249_core_v3_c3c4_vapor_holdup_small_moving_step_20260820.md"
)
MATRIX = Path(
    "logs/dd249_core_v3_c3c4_vapor_holdup_small_moving_step_20260820.npz"
)
SOURCE_MATRIX = Path(
    "logs/dd247_core_v3_c3c4_vapor_holdup_zero_motion_20260820.npz"
)
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_small_moving_step.py"),
    Path("tools/run_core_v3_vapor_holdup_stationary_hold.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_balances_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_properties_v1.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _coordinate_scale() -> np.ndarray:
    evidence = np.load(ROOT / SOURCE_MATRIX)
    matrix = np.asarray(evidence["jacobian_h1"], dtype=float)
    norms = np.linalg.norm(matrix, axis=0)
    scale = 1.0 / np.maximum(norms, 1.0e-30)
    scale /= np.median(scale)
    if scale.shape != (258,) or np.any(~np.isfinite(scale)) or np.any(scale <= 0.0):
        raise RuntimeError("DD-249 coordinate scale is invalid")
    return scale


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    scale = _coordinate_scale()
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "source_stationary_hold": dd248.DEFAULT_JSON.as_posix(),
        "source_zero_motion_matrix": SOURCE_MATRIX.as_posix(),
        "source_sha256": {
            dd248.DEFAULT_JSON.as_posix(): _sha(dd248.DEFAULT_JSON),
            SOURCE_MATRIX.as_posix(): _sha(SOURCE_MATRIX),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "disturbance": {
            "feed_component_multiplier": 1.001,
            "feed_enthalpy_multiplier": 1.001,
            "feed_composition_changed": False,
            "feed_specific_enthalpy_changed": False,
        },
        "steps": {"full_seconds": 0.25, "half_seconds": 0.125},
        "solver": {
            "method": "trf",
            "jacobian": "28-color central difference",
            "difference_step": 1.0e-5,
            "endpoint_difference_steps": [1.0e-5, 5.0e-6],
            "ftol": 1.0e-11,
            "xtol": 1.0e-11,
            "gtol": 1.0e-11,
            "max_nfev_per_step": 30,
            "x_scale": scale.tolist(),
            "x_scale_source": "inverse DD-247 h=1e-5 Jacobian column norm, median normalized",
        },
        "bounds": {
            "inventory_log_increment": [-0.01, 0.01],
            "phase_transfer_coordinate": [-0.1, 0.1],
            "temperature_coordinate": [-0.1, 0.1],
            "pressure_coordinate": [-0.1, 0.1],
            "flow_and_duty_log_increment": [-0.01, 0.01],
        },
        "required_dimension": 258,
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "spectrum_relative_change": 0.25,
            "matrix_relative_change": 0.05,
            "fugacity_residual": 1.0e-10,
            "eos_relative_residual": 1.0e-10,
            "component_inventory_identity_lbmol": 1.0e-6,
            "energy_identity_relative": 1.0e-8,
            "minimum_total_inventory_response_lbmol": 1.0e-4,
            "maximum_total_inventory_response_lbmol": 1.0e-2,
            "maximum_component_inventory_difference_lbmol": 2.0e-5,
            "component_inventory_difference_l1_lbmol": 5.0e-4,
            "signed_total_inventory_difference_lbmol": 1.0e-8,
            "temperature_difference_F": 2.0e-3,
            "pressure_difference_psia": 2.0e-4,
            "flow_relative_difference": 2.0e-4,
            "phase_transfer_scaled_difference": 2.0e-4,
            "duty_relative_difference": 2.0e-4,
            "provider_calls": 300000,
            "wall_clock_sec": 300.0,
        },
        "hard_stops": [
            "any of the three solves fails a residual, rank, condition, provider, or physical gate",
            "the positive feed disturbance lacks a bounded positive inventory response",
            "the discrete external component or energy balance does not explain the endpoint change",
            "the full and refined endpoints disagree outside the frozen limits",
            "a retry, alternate timestep, controller, fallback, or trajectory is needed",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "disturbance_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-249 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-249 Vapor-Holdup Small Moving-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Disturbance: `+0.1%` feed component rates and feed enthalpy.",
            "- Comparison: one `0.25 s` backward-Euler step versus two `0.125 s` steps.",
            "- Products, reflux, reboiler duty, and top-pressure anchor remain fixed.",
            "- Condenser duty, pressure, vapor traffic, phase transfer, and both phase inventories remain solved.",
            "- Solver: one frozen TRF configuration with a 28-color central Jacobian.",
            "- Coordinate scaling: fixed from the accepted DD-247 Jacobian before execution.",
            "- Retry, alternate step, controller action, or trajectory: `False`.",
            "",
            "Failure stops trajectory work. Passing authorizes only one separately frozen short open-loop trajectory contract.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-249 contract checksum or schema failed")
    for path, expected in payload["source_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-249 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-249 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-249 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _bounds() -> tuple[np.ndarray, np.ndarray]:
    lower = np.full(258, -0.1)
    upper = np.full(258, 0.1)
    lower[:120] = -0.01
    upper[:120] = 0.01
    lower[220:] = -0.01
    upper[220:] = 0.01
    return lower, upper


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return rank, condition, singular


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30)
    return float(np.linalg.norm(left - right) / denominator)


def _next_reference(
    prior: VaporHoldupImplicitReference,
    evaluation: VaporHoldupImplicitEvaluation,
) -> VaporHoldupImplicitReference:
    endpoint = evaluation.endpoint
    return VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=endpoint.liquid_component_inventory_lbmol.copy(),
        vapor_component_inventory_lbmol=endpoint.vapor_component_inventory_lbmol.copy(),
        phase_transfer_lbmolph=endpoint.phase_transfer_lbmolph.copy(),
        phase_transfer_scale_lbmolph=prior.phase_transfer_scale_lbmolph.copy(),
        temperature_F=endpoint.temperature_F.copy(),
        pressure_psia=endpoint.pressure_psia.copy(),
        hydraulic_liquid_flow_lbmolph=endpoint.hydraulic_liquid_flow_lbmolph.copy(),
        vapor_flow_lbmolph=endpoint.vapor_flow_lbmolph.copy(),
        condenser_duty_BTUph=float(endpoint.condenser_duty_BTUph),
        total_stored_energy_BTU=evaluation.properties.total_stored_energy_BTU.copy(),
    )


def _physical(evaluation: VaporHoldupImplicitEvaluation) -> bool:
    endpoint = evaluation.endpoint
    return bool(
        np.all(endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(endpoint.temperature_F > -459.67)
        and np.all(endpoint.pressure_psia > 0.0)
        and np.all(np.diff(endpoint.pressure_psia) >= 0.0)
        and np.all(endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(endpoint.vapor_flow_lbmolph > 0.0)
        and endpoint.condenser_duty_BTUph < 0.0
        and np.min(evaluation.properties.free_volume.free_vapor_volume_ft3) > 0.0
    )


def _path_response(
    initial: VaporHoldupImplicitReference,
    evaluations: list[VaporHoldupImplicitEvaluation],
    seconds: list[float],
) -> dict[str, Any]:
    final = evaluations[-1]
    actual_component = np.sum(
        final.endpoint.liquid_component_inventory_lbmol
        + final.endpoint.vapor_component_inventory_lbmol
        - initial.liquid_component_inventory_lbmol
        - initial.vapor_component_inventory_lbmol,
        axis=0,
    )
    expected_component = sum(
        evaluation.transport.external_component_rate_lbmolph * (duration / 3600.0)
        for evaluation, duration in zip(evaluations, seconds, strict=True)
    )
    actual_energy = float(
        np.sum(final.properties.total_stored_energy_BTU - initial.total_stored_energy_BTU)
    )
    expected_energy = float(
        sum(
            evaluation.transport.external_energy_rate_BTUph * (duration / 3600.0)
            for evaluation, duration in zip(evaluations, seconds, strict=True)
        )
    )
    energy_scale = max(abs(actual_energy), abs(expected_energy), 1.0)
    return {
        "component_inventory_change_lbmol": actual_component.tolist(),
        "expected_component_inventory_change_lbmol": expected_component.tolist(),
        "component_inventory_identity_max_abs_lbmol": float(
            np.max(np.abs(actual_component - expected_component))
        ),
        "total_inventory_change_lbmol": float(np.sum(actual_component)),
        "expected_total_inventory_change_lbmol": float(np.sum(expected_component)),
        "stored_energy_change_BTU": actual_energy,
        "expected_stored_energy_change_BTU": expected_energy,
        "energy_identity_relative": abs(actual_energy - expected_energy) / energy_scale,
    }


def execute(contract_path: Path, result_path: Path, result_doc_path: Path, matrix_path: Path) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    problem = dd248._problem()
    contract = problem["contract"]
    initial_reference = problem["reference"]
    multiplier = float(payload["disturbance"]["feed_component_multiplier"])
    balance_inputs = replace(
        problem["balance_inputs"],
        feed_component_lbmolph=(problem["balance_inputs"].feed_component_lbmolph * multiplier),
        feed_enthalpy_BTUph=(problem["balance_inputs"].feed_enthalpy_BTUph * multiplier),
    )
    pattern = vapor_holdup_structural_pattern(contract)
    lower, upper = _bounds()
    coordinate_scale = np.asarray(payload["solver"]["x_scale"], dtype=float)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    counters = {"function": 0, "jacobian": 0}

    def run_step(name: str, reference: VaporHoldupImplicitReference, seconds: float):
        numerical = replace(problem["numerical"], timestep_sec=float(seconds))

        def objective(candidate: np.ndarray, state_id: str = "solver") -> np.ndarray:
            counters["function"] += 1
            return evaluate_vapor_holdup_implicit_residual(
                contract,
                problem["geometry"],
                reference,
                balance_inputs,
                problem["spec"].hydraulic_geometry,
                numerical,
                provider,
                audit,
                candidate,
                state_id=f"dd249:{name}:{state_id}:{counters['function']}",
                evaluation_kind="jacobian",
            ).scaled

        def jacobian(candidate: np.ndarray) -> np.ndarray:
            counters["jacobian"] += 1
            matrix, _groups = colored_central_difference_jacobian(
                objective,
                candidate,
                pattern=pattern,
                step=float(payload["solver"]["difference_step"]),
                state_id=f"dd249:{name}:solver_jacobian:{counters['jacobian']}",
            )
            return matrix

        solution = least_squares(
            objective,
            np.zeros(258),
            jac=jacobian,
            bounds=(lower, upper),
            method="trf",
            x_scale=coordinate_scale,
            ftol=float(payload["solver"]["ftol"]),
            xtol=float(payload["solver"]["xtol"]),
            gtol=float(payload["solver"]["gtol"]),
            max_nfev=int(payload["solver"]["max_nfev_per_step"]),
            verbose=0,
        )
        final = evaluate_vapor_holdup_implicit_residual(
            contract,
            problem["geometry"],
            reference,
            balance_inputs,
            problem["spec"].hydraulic_geometry,
            numerical,
            provider,
            audit,
            solution.x,
            state_id=f"dd249:{name}:accepted_candidate",
            evaluation_kind="residual",
        )
        jacobian_matrix = np.asarray(solution.jac, dtype=float)
        rank, condition, singular = _rank_condition(jacobian_matrix)
        return solution, final, jacobian_matrix, rank, condition, singular

    started = time.perf_counter()
    full = run_step("full_0p25s", initial_reference, float(payload["steps"]["full_seconds"]))
    half_1 = run_step("half1_0p125s", initial_reference, float(payload["steps"]["half_seconds"]))
    half_1_reference = _next_reference(initial_reference, half_1[1])
    half_2 = run_step("half2_0p125s", half_1_reference, float(payload["steps"]["half_seconds"]))

    endpoint_matrices: list[np.ndarray] = []
    endpoint_singular: list[np.ndarray] = []
    endpoint_steps: list[dict[str, Any]] = []
    refined_reference = half_1_reference
    refined_numerical = replace(problem["numerical"], timestep_sec=float(payload["steps"]["half_seconds"]))

    def refined_objective(candidate: np.ndarray, state_id: str = "endpoint") -> np.ndarray:
        counters["function"] += 1
        return evaluate_vapor_holdup_implicit_residual(
            contract,
            problem["geometry"],
            refined_reference,
            balance_inputs,
            problem["spec"].hydraulic_geometry,
            refined_numerical,
            provider,
            audit,
            candidate,
            state_id=f"dd249:refined:{state_id}:{counters['function']}",
            evaluation_kind="jacobian",
        ).scaled

    for step in payload["solver"]["endpoint_difference_steps"]:
        matrix, groups = colored_central_difference_jacobian(
            refined_objective,
            half_2[0].x,
            pattern=pattern,
            step=float(step),
            state_id=f"dd249:refined_endpoint:h={float(step):.1e}",
        )
        rank, condition, singular = _rank_condition(matrix)
        endpoint_matrices.append(matrix)
        endpoint_singular.append(singular)
        endpoint_steps.append(
            {"step": float(step), "rank": rank, "condition": condition, "color_count": len(groups)}
        )
    spectrum_change = _relative_change(endpoint_singular[0], endpoint_singular[1])
    matrix_change = _relative_change(endpoint_matrices[0], endpoint_matrices[1])
    wall = time.perf_counter() - started

    outcomes = {"full": full, "half_1": half_1, "half_2": half_2}
    step_reports: dict[str, Any] = {}
    for name, (solution, final, _matrix, rank, condition, _singular) in outcomes.items():
        step_reports[name] = {
            "success": bool(solution.success),
            "status": int(solution.status),
            "message": str(solution.message),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "scaled_residual_inf_norm": float(np.max(np.abs(final.scaled))),
            "jacobian_rank": rank,
            "jacobian_condition": condition,
            "maximum_fugacity_residual": float(np.max(np.abs(final.fugacity_residual))),
            "maximum_eos_relative_residual": float(
                np.max(np.abs(final.properties.eos_relative_residual))
            ),
            "minimum_free_vapor_volume_ft3": float(
                np.min(final.properties.free_volume.free_vapor_volume_ft3)
            ),
            "maximum_inventory_rate_lbmolph": float(
                max(
                    np.max(np.abs(final.endpoint.liquid_component_rate_lbmolph)),
                    np.max(np.abs(final.endpoint.vapor_component_rate_lbmolph)),
                )
            ),
            "physical_pass": _physical(final),
        }

    response = {
        "full": _path_response(
            initial_reference,
            [full[1]],
            [float(payload["steps"]["full_seconds"])],
        ),
        "refined": _path_response(
            initial_reference,
            [half_1[1], half_2[1]],
            [float(payload["steps"]["half_seconds"])] * 2,
        ),
    }
    full_endpoint = full[1].endpoint
    refined_endpoint = half_2[1].endpoint
    full_inventory = (
        full_endpoint.liquid_component_inventory_lbmol
        + full_endpoint.vapor_component_inventory_lbmol
    )
    refined_inventory = (
        refined_endpoint.liquid_component_inventory_lbmol
        + refined_endpoint.vapor_component_inventory_lbmol
    )
    inventory_difference = full_inventory - refined_inventory

    def relative_max(left: np.ndarray, right: np.ndarray) -> float:
        return float(np.max(np.abs(left - right) / np.maximum(np.abs(right), 1.0)))

    refinement = {
        "maximum_component_inventory_difference_lbmol": float(np.max(np.abs(inventory_difference))),
        "component_inventory_difference_l1_lbmol": float(np.sum(np.abs(inventory_difference))),
        "signed_total_inventory_difference_lbmol": float(abs(np.sum(inventory_difference))),
        "temperature_difference_F": float(
            np.max(np.abs(full_endpoint.temperature_F - refined_endpoint.temperature_F))
        ),
        "pressure_difference_psia": float(
            np.max(np.abs(full_endpoint.pressure_psia - refined_endpoint.pressure_psia))
        ),
        "liquid_flow_relative_difference": relative_max(
            full_endpoint.hydraulic_liquid_flow_lbmolph,
            refined_endpoint.hydraulic_liquid_flow_lbmolph,
        ),
        "vapor_flow_relative_difference": relative_max(
            full_endpoint.vapor_flow_lbmolph,
            refined_endpoint.vapor_flow_lbmolph,
        ),
        "phase_transfer_scaled_difference": float(
            np.max(
                np.abs(full_endpoint.phase_transfer_lbmolph - refined_endpoint.phase_transfer_lbmolph)
                / initial_reference.phase_transfer_scale_lbmolph
            )
        ),
        "duty_relative_difference": float(
            abs(full_endpoint.condenser_duty_BTUph - refined_endpoint.condenser_duty_BTUph)
            / abs(refined_endpoint.condenser_duty_BTUph)
        ),
    }
    limits = payload["limits"]
    step_gates = {
        name: {
            "success": values["success"],
            "residual": values["scaled_residual_inf_norm"] < limits["scaled_residual"],
            "rank": values["jacobian_rank"] == payload["required_dimension"],
            "condition": values["jacobian_condition"] < limits["condition"],
            "fugacity": values["maximum_fugacity_residual"] < limits["fugacity_residual"],
            "eos": values["maximum_eos_relative_residual"] < limits["eos_relative_residual"],
            "physical": values["physical_pass"],
        }
        for name, values in step_reports.items()
    }
    response_gates = {
        name: {
            "positive": values["total_inventory_change_lbmol"] > 0.0,
            "detectable": values["total_inventory_change_lbmol"] > limits["minimum_total_inventory_response_lbmol"],
            "bounded": values["total_inventory_change_lbmol"] < limits["maximum_total_inventory_response_lbmol"],
            "component_identity": values["component_inventory_identity_max_abs_lbmol"] < limits["component_inventory_identity_lbmol"],
            "energy_identity": values["energy_identity_relative"] < limits["energy_identity_relative"],
        }
        for name, values in response.items()
    }
    refinement_gates = {
        "component_max": refinement["maximum_component_inventory_difference_lbmol"] < limits["maximum_component_inventory_difference_lbmol"],
        "component_l1": refinement["component_inventory_difference_l1_lbmol"] < limits["component_inventory_difference_l1_lbmol"],
        "signed_total": refinement["signed_total_inventory_difference_lbmol"] < limits["signed_total_inventory_difference_lbmol"],
        "temperature": refinement["temperature_difference_F"] < limits["temperature_difference_F"],
        "pressure": refinement["pressure_difference_psia"] < limits["pressure_difference_psia"],
        "liquid_flow": refinement["liquid_flow_relative_difference"] < limits["flow_relative_difference"],
        "vapor_flow": refinement["vapor_flow_relative_difference"] < limits["flow_relative_difference"],
        "phase_transfer": refinement["phase_transfer_scaled_difference"] < limits["phase_transfer_scaled_difference"],
        "duty": refinement["duty_relative_difference"] < limits["duty_relative_difference"],
    }
    endpoint_stability = {
        "steps": endpoint_steps,
        "spectrum_relative_change": spectrum_change,
        "matrix_relative_change": matrix_change,
        "pass": bool(
            all(item["rank"] == payload["required_dimension"] for item in endpoint_steps)
            and all(item["condition"] < limits["condition"] for item in endpoint_steps)
            and spectrum_change < limits["spectrum_relative_change"]
            and matrix_change < limits["matrix_relative_change"]
        ),
    }
    provider_report = compact_provider_report(audit.report())
    campaign_gates = {
        "steps": all(all(gates.values()) for gates in step_gates.values()),
        "response": all(all(gates.values()) for gates in response_gates.values()),
        "refinement": all(refinement_gates.values()),
        "endpoint_stability": endpoint_stability["pass"],
        "provider": provider_report["pass"] and not provider_report["fallback_attempted"],
        "provider_calls": audit.record_count < limits["provider_calls"],
        "wall_clock": wall < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "vapor_holdup_small_moving_step_passed"
            if passed
            else "vapor_holdup_small_moving_step_failed"
        ),
        "decision": (
            "authorize_one_separately_frozen_short_open_loop_trajectory_contract"
            if passed
            else "stop_vapor_holdup_before_trajectory"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": wall,
        "solver_observed": counters,
        "steps": step_reports,
        "response": response,
        "refinement": refinement,
        "endpoint_stability": endpoint_stability,
        "step_gates": step_gates,
        "response_gates": response_gates,
        "refinement_gates": refinement_gates,
        "campaign_gates": campaign_gates,
        "provider": provider_report,
        "logical_provider_calls": audit.record_count,
        "retry_attempted": False,
        "controller_action_attempted": False,
        "alternate_timestep_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed_once": True,
        "pass_gate": passed,
    }
    destination = ROOT / result_path
    document = ROOT / result_doc_path
    matrix_destination = ROOT / matrix_path
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(report), encoding="utf-8")
    np.savez_compressed(
        matrix_destination,
        full_coordinates=full[0].x,
        half_1_coordinates=half_1[0].x,
        half_2_coordinates=half_2[0].x,
        full_jacobian=full[2],
        half_1_jacobian=half_1[2],
        half_2_jacobian=half_2[2],
        refined_jacobian_h1=endpoint_matrices[0],
        refined_jacobian_h2=endpoint_matrices[1],
    )
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    response = payload["response"]
    refinement = payload["refinement"]
    return "\n".join(
        (
            "# DD-249 Vapor-Holdup Small Moving-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residuals: `{steps['full']['scaled_residual_inf_norm']:.6e}`, `{steps['half_1']['scaled_residual_inf_norm']:.6e}`, `{steps['half_2']['scaled_residual_inf_norm']:.6e}`",
            f"- Ranks: `{steps['full']['jacobian_rank']} / {steps['half_1']['jacobian_rank']} / {steps['half_2']['jacobian_rank']}`",
            f"- Worst condition: `{max(item['jacobian_condition'] for item in steps.values()):.6e}`",
            f"- Full/refined total inventory response: `{response['full']['total_inventory_change_lbmol']:.6e}` / `{response['refined']['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Full/refined component difference max: `{refinement['maximum_component_inventory_difference_lbmol']:.6e} lbmol`",
            f"- Provider calls: `{payload['logical_provider_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Retry, controllers, alternate timestep, or trajectory: `False`",
            "",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.prepare:
        report = prepare(args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": report["schema_id"],
                    "contract_payload_sha256": report["contract_payload_sha256"],
                    "required_dimension": report["required_dimension"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc, args.matrix)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
