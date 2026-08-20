#!/usr/bin/env python
"""Prepare or execute the frozen DD-250 vapor-holdup short trajectory."""

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

import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
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


SCHEMA = "dd250-core-v3-c3c4-vapor-holdup-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd250-core-v3-c3c4-vapor-holdup-short-trajectory-result-v1"
CONTRACT = Path(
    "logs/dd250_core_v3_c3c4_vapor_holdup_short_trajectory_contract_20260820.json"
)
RESULT = Path(
    "logs/dd250_core_v3_c3c4_vapor_holdup_short_trajectory_20260820.json"
)
CONTRACT_DOC = Path(
    "docs/dd_250_core_v3_c3c4_vapor_holdup_short_trajectory_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_250_core_v3_c3c4_vapor_holdup_short_trajectory_20260820.md"
)
MATRIX = Path(
    "logs/dd250_core_v3_c3c4_vapor_holdup_short_trajectory_20260820.npz"
)
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_short_trajectory.py"),
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


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    dd249_contract = json.loads((ROOT / dd249.CONTRACT).read_text(encoding="utf-8"))
    dd249_result = json.loads((ROOT / dd249.RESULT).read_text(encoding="utf-8"))
    if not dd249_result.get("pass_gate"):
        raise RuntimeError("DD-250 requires accepted DD-249 evidence")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd249.CONTRACT.as_posix(): _sha(dd249.CONTRACT),
            dd249.RESULT.as_posix(): _sha(dd249.RESULT),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "disturbance": {
            "feed_component_multiplier": 1.001,
            "feed_enthalpy_multiplier": 1.001,
            "feed_composition_changed": False,
            "feed_specific_enthalpy_changed": False,
        },
        "trajectory": {
            "duration_sec": 1.0,
            "nominal_step_sec": 0.25,
            "refined_step_sec": 0.125,
            "nominal_endpoint_count": 4,
            "refined_endpoint_count": 8,
        },
        "solver": {
            "method": "trf",
            "jacobian": "28-color central difference",
            "difference_step": 1.0e-5,
            "final_refined_check_step": 5.0e-6,
            "ftol": 1.0e-11,
            "xtol": 1.0e-11,
            "gtol": 1.0e-11,
            "max_nfev_per_endpoint": 20,
            "x_scale": dd249_contract["solver"]["x_scale"],
            "warm_start": "previous endpoint relative coordinates",
        },
        "required_dimension": 258,
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "fugacity_residual": 1.0e-10,
            "eos_relative_residual": 1.0e-10,
            "component_inventory_identity_lbmol": 1.0e-6,
            "energy_identity_relative": 1.0e-8,
            "minimum_final_inventory_response_lbmol": 1.0e-3,
            "maximum_final_inventory_response_lbmol": 1.0e-2,
            "maximum_common_time_component_difference_lbmol": 5.0e-5,
            "maximum_common_time_component_l1_lbmol": 1.0e-3,
            "maximum_common_time_signed_total_difference_lbmol": 1.0e-8,
            "maximum_common_time_temperature_difference_F": 1.0e-2,
            "maximum_common_time_pressure_difference_psia": 1.0e-3,
            "maximum_common_time_flow_relative_difference": 1.0e-3,
            "maximum_common_time_phase_transfer_scaled_difference": 1.0e-3,
            "maximum_common_time_duty_relative_difference": 1.0e-3,
            "final_spectrum_relative_change": 0.25,
            "final_matrix_relative_change": 0.05,
            "provider_calls": 1500000,
            "wall_clock_sec": 600.0,
        },
        "hard_stops": [
            "any endpoint fails its solve, residual, rank, condition, provider, or physical gate",
            "inventory response is not positive and monotonic",
            "the discrete external component or energy balance does not explain each path",
            "nominal and refined trajectories disagree outside the frozen common-time limits",
            "a retry, alternate grid, controller, fallback, or longer trajectory is needed",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-250 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    trajectory = payload["trajectory"]
    return "\n".join(
        (
            "# DD-250 Vapor-Holdup Short Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Disturbance: `+0.1%` feed component rates and feed enthalpy.",
            f"- Duration: `{trajectory['duration_sec']} s`.",
            f"- Nominal path: `{trajectory['nominal_endpoint_count']}` endpoints at `{trajectory['nominal_step_sec']} s`.",
            f"- Refined path: `{trajectory['refined_endpoint_count']}` endpoints at `{trajectory['refined_step_sec']} s`.",
            "- Products, reflux, reboiler duty, and top-pressure anchor remain fixed.",
            "- Every endpoint must remain full rank, conservative, physical, and provider-governed.",
            "- Retry, alternate grid, controller action, or longer trajectory: `False`.",
            "",
            "Failure stops trajectory extension. Passing authorizes only a separately frozen dynamic-scope decision.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-250 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-250 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-250 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-250 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _trajectory_response(
    initial: VaporHoldupImplicitReference,
    evaluations: list[VaporHoldupImplicitEvaluation],
    step_sec: float,
) -> list[dict[str, Any]]:
    return [
        {
            "time_sec": float((index + 1) * step_sec),
            **dd249._path_response(
                initial,
                evaluations[: index + 1],
                [step_sec] * (index + 1),
            ),
        }
        for index in range(len(evaluations))
    ]


def _common_time_comparison(
    nominal: list[VaporHoldupImplicitEvaluation],
    refined: list[VaporHoldupImplicitEvaluation],
    initial: VaporHoldupImplicitReference,
) -> list[dict[str, float]]:
    comparisons: list[dict[str, float]] = []
    for index, coarse in enumerate(nominal):
        fine = refined[2 * index + 1]
        coarse_endpoint = coarse.endpoint
        fine_endpoint = fine.endpoint
        coarse_inventory = (
            coarse_endpoint.liquid_component_inventory_lbmol
            + coarse_endpoint.vapor_component_inventory_lbmol
        )
        fine_inventory = (
            fine_endpoint.liquid_component_inventory_lbmol
            + fine_endpoint.vapor_component_inventory_lbmol
        )
        difference = coarse_inventory - fine_inventory

        def relative_max(left: np.ndarray, right: np.ndarray) -> float:
            return float(np.max(np.abs(left - right) / np.maximum(np.abs(right), 1.0)))

        comparisons.append(
            {
                "time_sec": float((index + 1) * 0.25),
                "maximum_component_difference_lbmol": float(np.max(np.abs(difference))),
                "component_difference_l1_lbmol": float(np.sum(np.abs(difference))),
                "signed_total_difference_lbmol": float(abs(np.sum(difference))),
                "temperature_difference_F": float(
                    np.max(np.abs(coarse_endpoint.temperature_F - fine_endpoint.temperature_F))
                ),
                "pressure_difference_psia": float(
                    np.max(np.abs(coarse_endpoint.pressure_psia - fine_endpoint.pressure_psia))
                ),
                "liquid_flow_relative_difference": relative_max(
                    coarse_endpoint.hydraulic_liquid_flow_lbmolph,
                    fine_endpoint.hydraulic_liquid_flow_lbmolph,
                ),
                "vapor_flow_relative_difference": relative_max(
                    coarse_endpoint.vapor_flow_lbmolph,
                    fine_endpoint.vapor_flow_lbmolph,
                ),
                "phase_transfer_scaled_difference": float(
                    np.max(
                        np.abs(
                            coarse_endpoint.phase_transfer_lbmolph
                            - fine_endpoint.phase_transfer_lbmolph
                        )
                        / initial.phase_transfer_scale_lbmolph
                    )
                ),
                "duty_relative_difference": float(
                    abs(
                        coarse_endpoint.condenser_duty_BTUph
                        - fine_endpoint.condenser_duty_BTUph
                    )
                    / abs(fine_endpoint.condenser_duty_BTUph)
                ),
            }
        )
    return comparisons


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
    matrix_path: Path,
) -> dict[str, Any]:
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
    lower, upper = dd249._bounds()
    coordinate_scale = np.asarray(payload["solver"]["x_scale"], dtype=float)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    counters = {"function": 0, "jacobian": 0}

    def run_path(name: str, step_sec: float, endpoint_count: int):
        reference = initial_reference
        initial_coordinates = np.zeros(258)
        evaluations: list[VaporHoldupImplicitEvaluation] = []
        coordinates: list[np.ndarray] = []
        matrices: list[np.ndarray] = []
        reports: list[dict[str, Any]] = []
        prior_references: list[VaporHoldupImplicitReference] = []
        numerical = replace(problem["numerical"], timestep_sec=step_sec)
        for endpoint_index in range(endpoint_count):
            endpoint_name = f"{name}:{endpoint_index + 1}"

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
                    state_id=f"dd250:{endpoint_name}:{state_id}:{counters['function']}",
                    evaluation_kind="jacobian",
                ).scaled

            def jacobian(candidate: np.ndarray) -> np.ndarray:
                counters["jacobian"] += 1
                matrix, _groups = colored_central_difference_jacobian(
                    objective,
                    candidate,
                    pattern=pattern,
                    step=float(payload["solver"]["difference_step"]),
                    state_id=f"dd250:{endpoint_name}:jacobian:{counters['jacobian']}",
                )
                return matrix

            prior_references.append(reference)
            solution = least_squares(
                objective,
                initial_coordinates,
                jac=jacobian,
                bounds=(lower, upper),
                method="trf",
                x_scale=coordinate_scale,
                ftol=float(payload["solver"]["ftol"]),
                xtol=float(payload["solver"]["xtol"]),
                gtol=float(payload["solver"]["gtol"]),
                max_nfev=int(payload["solver"]["max_nfev_per_endpoint"]),
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
                state_id=f"dd250:{endpoint_name}:accepted",
                evaluation_kind="residual",
            )
            matrix = np.asarray(solution.jac, dtype=float)
            rank, condition, _singular = dd249._rank_condition(matrix)
            reports.append(
                {
                    "time_sec": float((endpoint_index + 1) * step_sec),
                    "success": bool(solution.success),
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
                    "physical_pass": dd249._physical(final),
                }
            )
            evaluations.append(final)
            coordinates.append(solution.x.copy())
            matrices.append(matrix)
            reference = dd249._next_reference(reference, final)
            initial_coordinates = solution.x.copy()
        return {
            "evaluations": evaluations,
            "coordinates": coordinates,
            "matrices": matrices,
            "reports": reports,
            "prior_references": prior_references,
        }

    started = time.perf_counter()
    trajectory = payload["trajectory"]
    nominal = run_path(
        "nominal",
        float(trajectory["nominal_step_sec"]),
        int(trajectory["nominal_endpoint_count"]),
    )
    refined = run_path(
        "refined",
        float(trajectory["refined_step_sec"]),
        int(trajectory["refined_endpoint_count"]),
    )
    final_reference = refined["prior_references"][-1]
    final_coordinates = refined["coordinates"][-1]
    final_numerical = replace(
        problem["numerical"], timestep_sec=float(trajectory["refined_step_sec"])
    )

    def final_objective(candidate: np.ndarray, state_id: str = "endpoint") -> np.ndarray:
        counters["function"] += 1
        return evaluate_vapor_holdup_implicit_residual(
            contract,
            problem["geometry"],
            final_reference,
            balance_inputs,
            problem["spec"].hydraulic_geometry,
            final_numerical,
            provider,
            audit,
            candidate,
            state_id=f"dd250:final:{state_id}:{counters['function']}",
            evaluation_kind="jacobian",
        ).scaled

    final_h2, groups = colored_central_difference_jacobian(
        final_objective,
        final_coordinates,
        pattern=pattern,
        step=float(payload["solver"]["final_refined_check_step"]),
        state_id="dd250:final:h=5e-6",
    )
    final_h1 = refined["matrices"][-1]
    final_rank_h2, final_condition_h2, singular_h2 = dd249._rank_condition(final_h2)
    _rank_h1, _condition_h1, singular_h1 = dd249._rank_condition(final_h1)
    final_spectrum_change = dd249._relative_change(singular_h1, singular_h2)
    final_matrix_change = dd249._relative_change(final_h1, final_h2)
    wall = time.perf_counter() - started

    nominal_response = _trajectory_response(
        initial_reference,
        nominal["evaluations"],
        float(trajectory["nominal_step_sec"]),
    )
    refined_response = _trajectory_response(
        initial_reference,
        refined["evaluations"],
        float(trajectory["refined_step_sec"]),
    )
    comparisons = _common_time_comparison(
        nominal["evaluations"], refined["evaluations"], initial_reference
    )
    limits = payload["limits"]
    all_endpoint_reports = nominal["reports"] + refined["reports"]
    endpoint_gates = [
        {
            "success": item["success"],
            "residual": item["scaled_residual_inf_norm"] < limits["scaled_residual"],
            "rank": item["jacobian_rank"] == payload["required_dimension"],
            "condition": item["jacobian_condition"] < limits["condition"],
            "fugacity": item["maximum_fugacity_residual"] < limits["fugacity_residual"],
            "eos": item["maximum_eos_relative_residual"] < limits["eos_relative_residual"],
            "physical": item["physical_pass"],
        }
        for item in all_endpoint_reports
    ]
    response_gates = {
        "nominal_monotonic": bool(
            np.all(np.diff([0.0] + [item["total_inventory_change_lbmol"] for item in nominal_response]) > 0.0)
        ),
        "refined_monotonic": bool(
            np.all(np.diff([0.0] + [item["total_inventory_change_lbmol"] for item in refined_response]) > 0.0)
        ),
        "nominal_final_detectable": nominal_response[-1]["total_inventory_change_lbmol"] > limits["minimum_final_inventory_response_lbmol"],
        "refined_final_detectable": refined_response[-1]["total_inventory_change_lbmol"] > limits["minimum_final_inventory_response_lbmol"],
        "nominal_final_bounded": nominal_response[-1]["total_inventory_change_lbmol"] < limits["maximum_final_inventory_response_lbmol"],
        "refined_final_bounded": refined_response[-1]["total_inventory_change_lbmol"] < limits["maximum_final_inventory_response_lbmol"],
        "component_identity": max(
            item["component_inventory_identity_max_abs_lbmol"]
            for item in nominal_response + refined_response
        ) < limits["component_inventory_identity_lbmol"],
        "energy_identity": max(
            item["energy_identity_relative"] for item in nominal_response + refined_response
        ) < limits["energy_identity_relative"],
    }
    refinement_gates = {
        "component_max": max(item["maximum_component_difference_lbmol"] for item in comparisons) < limits["maximum_common_time_component_difference_lbmol"],
        "component_l1": max(item["component_difference_l1_lbmol"] for item in comparisons) < limits["maximum_common_time_component_l1_lbmol"],
        "signed_total": max(item["signed_total_difference_lbmol"] for item in comparisons) < limits["maximum_common_time_signed_total_difference_lbmol"],
        "temperature": max(item["temperature_difference_F"] for item in comparisons) < limits["maximum_common_time_temperature_difference_F"],
        "pressure": max(item["pressure_difference_psia"] for item in comparisons) < limits["maximum_common_time_pressure_difference_psia"],
        "liquid_flow": max(item["liquid_flow_relative_difference"] for item in comparisons) < limits["maximum_common_time_flow_relative_difference"],
        "vapor_flow": max(item["vapor_flow_relative_difference"] for item in comparisons) < limits["maximum_common_time_flow_relative_difference"],
        "phase_transfer": max(item["phase_transfer_scaled_difference"] for item in comparisons) < limits["maximum_common_time_phase_transfer_scaled_difference"],
        "duty": max(item["duty_relative_difference"] for item in comparisons) < limits["maximum_common_time_duty_relative_difference"],
    }
    final_jacobian = {
        "h1_rank": refined["reports"][-1]["jacobian_rank"],
        "h1_condition": refined["reports"][-1]["jacobian_condition"],
        "h2_rank": final_rank_h2,
        "h2_condition": final_condition_h2,
        "color_count": len(groups),
        "spectrum_relative_change": final_spectrum_change,
        "matrix_relative_change": final_matrix_change,
        "pass": bool(
            final_rank_h2 == payload["required_dimension"]
            and final_condition_h2 < limits["condition"]
            and final_spectrum_change < limits["final_spectrum_relative_change"]
            and final_matrix_change < limits["final_matrix_relative_change"]
        ),
    }
    provider_report = compact_provider_report(audit.report())
    campaign_gates = {
        "endpoints": all(all(gate.values()) for gate in endpoint_gates),
        "response": all(response_gates.values()),
        "refinement": all(refinement_gates.values()),
        "final_jacobian": final_jacobian["pass"],
        "provider": provider_report["pass"] and not provider_report["fallback_attempted"],
        "provider_calls": audit.record_count < limits["provider_calls"],
        "wall_clock": wall < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "vapor_holdup_short_trajectory_passed"
            if passed
            else "vapor_holdup_short_trajectory_failed"
        ),
        "decision": (
            "authorize_separately_frozen_dynamic_scope_decision"
            if passed
            else "stop_vapor_holdup_trajectory_extension"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": wall,
        "solver_observed": counters,
        "nominal_endpoints": nominal["reports"],
        "refined_endpoints": refined["reports"],
        "nominal_response": nominal_response,
        "refined_response": refined_response,
        "common_time_comparison": comparisons,
        "endpoint_gates": endpoint_gates,
        "response_gates": response_gates,
        "refinement_gates": refinement_gates,
        "final_jacobian": final_jacobian,
        "campaign_gates": campaign_gates,
        "provider": provider_report,
        "logical_provider_calls": audit.record_count,
        "retry_attempted": False,
        "controller_action_attempted": False,
        "alternate_grid_attempted": False,
        "longer_trajectory_attempted": False,
        "campaign_executed_once": True,
        "pass_gate": passed,
    }
    destination = ROOT / result_path
    document = ROOT / result_doc_path
    matrix_destination = ROOT / matrix_path
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(report), encoding="utf-8")

    def stack_endpoint(path: dict[str, Any], attribute: str) -> np.ndarray:
        return np.stack(
            [getattr(item.endpoint, attribute) for item in path["evaluations"]]
        )

    np.savez_compressed(
        matrix_destination,
        nominal_liquid_inventory=stack_endpoint(nominal, "liquid_component_inventory_lbmol"),
        nominal_vapor_inventory=stack_endpoint(nominal, "vapor_component_inventory_lbmol"),
        nominal_temperature=stack_endpoint(nominal, "temperature_F"),
        nominal_pressure=stack_endpoint(nominal, "pressure_psia"),
        nominal_liquid_flow=stack_endpoint(nominal, "hydraulic_liquid_flow_lbmolph"),
        nominal_vapor_flow=stack_endpoint(nominal, "vapor_flow_lbmolph"),
        refined_liquid_inventory=stack_endpoint(refined, "liquid_component_inventory_lbmol"),
        refined_vapor_inventory=stack_endpoint(refined, "vapor_component_inventory_lbmol"),
        refined_temperature=stack_endpoint(refined, "temperature_F"),
        refined_pressure=stack_endpoint(refined, "pressure_psia"),
        refined_liquid_flow=stack_endpoint(refined, "hydraulic_liquid_flow_lbmolph"),
        refined_vapor_flow=stack_endpoint(refined, "vapor_flow_lbmolph"),
        final_jacobian_h1=final_h1,
        final_jacobian_h2=final_h2,
    )
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    nominal = payload["nominal_response"][-1]
    refined = payload["refined_response"][-1]
    comparison = payload["common_time_comparison"][-1]
    endpoints = payload["nominal_endpoints"] + payload["refined_endpoints"]
    return "\n".join(
        (
            "# DD-250 Vapor-Holdup Short Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Endpoints: `{len(payload['nominal_endpoints'])}` nominal / `{len(payload['refined_endpoints'])}` refined",
            f"- Worst residual: `{max(item['scaled_residual_inf_norm'] for item in endpoints):.6e}`",
            f"- Worst condition: `{max(item['jacobian_condition'] for item in endpoints):.6e}`",
            f"- Final nominal/refined inventory gain: `{nominal['total_inventory_change_lbmol']:.6e}` / `{refined['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Final common-time component difference: `{comparison['maximum_component_difference_lbmol']:.6e} lbmol`",
            f"- Provider calls: `{payload['logical_provider_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Retry, controllers, alternate grid, or longer trajectory: `False`",
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
                    "trajectory": report["trajectory"],
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
