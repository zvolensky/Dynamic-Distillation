#!/usr/bin/env python
"""Prepare or execute DD-188's short controlled seven-volume trajectory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_seven_volume_terminal_inventory_control_numerical as dd185  # noqa: E402
import run_core_v3_seven_volume_physical_short_trajectory as dd177  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_moving_step as dd187  # noqa: E402
from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (  # noqa: E402
    InventoryRefinementLimits,
    assess_inventory_refinement,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    audit_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    TerminalInventoryControlBackwardEulerEvaluation,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
)
from dynamic_distillation.core_v3.terminal_inventory_control_trajectory_v1 import (  # noqa: E402
    TerminalInventoryControlTrajectoryResult,
    run_terminal_inventory_control_trajectory,
)


SCHEMA = "dd188-core-v3-seven-volume-terminal-control-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd188-core-v3-seven-volume-terminal-control-short-trajectory-result-v1"
DD187_CONTRACT = Path(
    "logs/dd187_core_v3_seven_volume_terminal_inventory_control_moving_step_contract_20260813.json"
)
DD187_RESULT = Path(
    "logs/dd187_core_v3_seven_volume_terminal_inventory_control_moving_step_20260813.json"
)
DD185_CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
CONTRACT = Path(
    "logs/dd188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_contract_20260813.json"
)
RESULT = Path(
    "logs/dd188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_20260813.md"
)
DURATION_SEC = 2.0
COARSE_DT_SEC = 0.25
REFINED_DT_SEC = 0.125
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/physical_refinement_policy_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_contract_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_trajectory_v1.py",
    "tests/test_core_v3_terminal_inventory_control_trajectory_v1.py",
    "tests/test_core_v3_terminal_inventory_control_short_trajectory.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_short_trajectory.py",
)


def _validate_source(result: Mapping[str, Any]) -> None:
    if not result.get("pass_gate") or result.get("decision") != (
        "authorize_one_frozen_short_controlled_trajectory_contract"
    ):
        raise RuntimeError("DD-188 requires the accepted DD-187 result")
    if result.get("controller_tuning_attempted") is not False:
        raise RuntimeError("DD-187 controller tuning status changed")
    if not all(result.get("campaign_gates", {}).values()):
        raise RuntimeError("DD-187 campaign gates changed")


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    return "\n".join(
        (
            "# DD-188 Seven-Volume Controlled Short-Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Disturbance, setpoints, PI constants, and product references: unchanged from DD-187",
            f"- Duration: `{paths['duration_seconds']} s`",
            f"- Coarse path: `{paths['coarse_steps']} x {paths['coarse_step_seconds']} s`",
            f"- Refined path: `{paths['refined_steps']} x {paths['refined_step_seconds']} s`",
            f"- Shared-time comparisons: `{paths['shared_time_count']}`",
            "- Response acceptance: duration-scaled integrated external flow",
            "- Property evaluation during preparation: `False`",
            "- Timestep execution during preparation: `False`",
            "",
            "Commit before the one execution. No tuning, retry, alternate grid, "
            "projection, clipping, or fallback is authorized.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    shared = payload["shared_time_refinement"]
    return "\n".join(
        (
            "# DD-188 Seven-Volume Controlled Short-Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}`",
            f"- Worst residual: `{payload['worst_residual']:.6e}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Worst absolute inventory refinement: "
            f"`{shared['worst_absolute_component_difference_lbmol']:.6e} lbmol`",
            f"- Worst product relative refinement: "
            f"`{shared['worst_product_relative_difference']:.6e}`",
            f"- Coarse/refined total accumulation: "
            f"`{payload['response']['coarse']['total_inventory_change_lbmol']:.6e}` / "
            f"`{payload['response']['refined']['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Logical provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Controller tuning/retry attempted: `False / False`",
            "",
        )
    )


def prepare(
    source_contract_path: Path,
    source_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = dd187.dd186._load(source_contract_path)
    result = dd187.dd186._load(source_result_path)
    _validate_source(result)
    coarse_count = dd177._step_count(DURATION_SEC, COARSE_DT_SEC)
    refined_count = dd177._step_count(DURATION_SEC, REFINED_DT_SEC)
    pairs = dd177._shared_step_pairs(coarse_count, refined_count)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd187.dd186._git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): dd187.dd186._sha(ROOT / path)
            for path in (source_contract_path, source_result_path, DD185_CONTRACT)
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "initial_solve_coordinates": source["initial_solve_coordinates"],
        "initial_controller_memory": source["initial_controller_memory"],
        "level_setpoints": source["level_setpoints"],
        "product_reference_lbmolph": source["product_reference_lbmolph"],
        "geometry": source["geometry"],
        "controllers": source["controllers"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "disturbance": source["disturbance"],
        "solver": source["solver"],
        "paths": {
            "duration_seconds": DURATION_SEC,
            "coarse_step_seconds": COARSE_DT_SEC,
            "coarse_steps": coarse_count,
            "refined_step_seconds": REFINED_DT_SEC,
            "refined_steps": refined_count,
            "shared_time_count": len(pairs),
            "shared_step_pairs_1based": [list(pair) for pair in pairs],
        },
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "kinematic_identity": 1.0e-12,
            "controller_kinematic_identity": 1.0e-12,
            "controller_equation_closure": 1.0e-8,
            "global_component_inventory_identity_lbmol": 1.0e-6,
            "integrated_response_relative_error": 1.0e-6,
            "cross_grid_total_inventory_lbmol": 1.0e-9,
            "rate_coordinate_refinement": 1.0e-5,
            "algebraic_coordinate_refinement": 1.0e-5,
            "controller_memory_refinement": 1.0e-7,
            "product_relative_refinement": 1.0e-6,
            "level_fraction_refinement": 1.0e-8,
            "provider_calls": 150000,
            "wall_clock_sec": 180.0,
        },
        "physical_refinement_limits": source["physical_refinement_limits"],
        "required_rank": 58,
        "exact_state_memoization": source["exact_state_memoization"],
        "implementation_sha256": {
            path: dd187.dd186._sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "either trajectory fails to complete every root",
            "any root loses closure, rank, condition, physicality, or conservation",
            "response is not positive, monotone, or consistent with external flow",
            "any shared-time physical or controller refinement gate fails",
            "fixed product references, provider ownership, call, or wall gates fail",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "controller_tuning_attempted": False,
        "retry_authorized": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = dd187.dd186._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-188 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd187.dd186._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-188 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-188 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-188 implementation changed: {path}")
    if dd187.dd186._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-188 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-188 result exists; rerun is prohibited")
    if not dd187.dd186._git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-188 contract is not committed")


def _evaluations(
    trajectory: TerminalInventoryControlTrajectoryResult,
) -> list[TerminalInventoryControlBackwardEulerEvaluation]:
    values = []
    for record in trajectory.steps:
        evaluation = record.outcome.evaluation
        if not isinstance(evaluation, TerminalInventoryControlBackwardEulerEvaluation):
            raise TypeError("DD-188 trajectory endpoint is invalid")
        values.append(evaluation)
    return values


def _trajectory_report(
    trajectory: TerminalInventoryControlTrajectoryResult,
    spec: Any,
    initial_inventory: np.ndarray,
    initial_coordinates: np.ndarray,
    initial_memory: np.ndarray,
    setpoints: np.ndarray,
    product_reference: np.ndarray,
    limits: Mapping[str, float],
    required_rank: int,
    max_nfev: int,
) -> dict[str, Any]:
    reports = []
    totals = [float(np.sum(initial_inventory))]
    for record in trajectory.steps:
        report = dd187.dd186._step_report(
            record.outcome,
            spec,
            initial_inventory,
            initial_coordinates,
            initial_memory,
            setpoints,
            product_reference,
            trajectory.step_seconds,
        )
        report["index"] = record.index
        report["time_seconds"] = record.time_seconds
        report["controller_equation_closure"] = dd187._controller_closure(
            record.outcome
        )
        report["gates"] = {
            "success": report["success"] and report["nfev"] <= max_nfev,
            "residual": report["residual_inf_norm"] < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == required_rank,
            "condition": report["jacobian_condition"] < limits["condition"],
            "equilibrium": report["maximum_equilibrium_residual"]
            < limits["equilibrium_residual"],
            "component_conservation": report["component_conservation_relative_error"]
            < limits["component_conservation"],
            "energy_conservation": report["energy_conservation_relative_error"]
            < limits["energy_conservation"],
            "component_kinematics": report["component_kinematic_identity"]
            < limits["kinematic_identity"],
            "energy_kinematics": report["energy_kinematic_identity"]
            < limits["kinematic_identity"],
            "controller_kinematics": report["controller_kinematic_identity"]
            < limits["controller_kinematic_identity"],
            "controller_equations": report["controller_equation_closure"]
            < limits["controller_equation_closure"],
            "physical": report["physical_pass"],
        }
        reports.append(report)
        totals.append(float(np.sum(record.outcome.evaluation.endpoint_inventory_lbmol)))
    return {
        "name": trajectory.name,
        "step_seconds": trajectory.step_seconds,
        "requested_steps": trajectory.requested_steps,
        "completed_steps": trajectory.completed_steps,
        "completed": trajectory.completed,
        "steps": reports,
        "step_gates_pass": len(reports) == trajectory.requested_steps
        and all(all(report["gates"].values()) for report in reports),
        "total_inventory_history_lbmol": totals,
        "total_inventory_strictly_increasing": bool(np.all(np.diff(totals) > 0.0)),
    }


def _shared_refinement(
    initial_inventory: np.ndarray,
    coarse: Sequence[TerminalInventoryControlBackwardEulerEvaluation],
    refined: Sequence[TerminalInventoryControlBackwardEulerEvaluation],
    pairs: Sequence[Sequence[int]],
    physical_limits: InventoryRefinementLimits,
    limits: Mapping[str, float],
) -> dict[str, Any]:
    comparisons = []
    for coarse_1based, refined_1based in pairs:
        coarse_eval = coarse[int(coarse_1based) - 1]
        refined_eval = refined[int(refined_1based) - 1]
        physical = assess_inventory_refinement(
            initial_inventory,
            coarse_eval.endpoint_inventory_lbmol,
            refined_eval.endpoint_inventory_lbmol,
            physical_limits,
        )
        coarse_products = np.asarray(
            (coarse_eval.distillate_lbmolph, coarse_eval.bottoms_lbmolph)
        )
        refined_products = np.asarray(
            (refined_eval.distillate_lbmolph, refined_eval.bottoms_lbmolph)
        )
        product_scale = np.maximum(np.abs(coarse_products), 1.0)
        metrics = {
            "rate_coordinate_difference": float(
                np.max(np.abs(coarse_eval.rate_coordinates - refined_eval.rate_coordinates))
            ),
            "algebraic_coordinate_difference": float(
                np.max(
                    np.abs(
                        coarse_eval.algebraic_coordinates
                        - refined_eval.algebraic_coordinates
                    )
                )
            ),
            "controller_memory_difference": float(
                np.max(
                    np.abs(
                        coarse_eval.endpoint_controller_memory
                        - refined_eval.endpoint_controller_memory
                    )
                )
            ),
            "product_relative_difference": float(
                np.max(np.abs(coarse_products - refined_products) / product_scale)
            ),
            "level_fraction_difference": float(
                np.max(np.abs(coarse_eval.level_fraction - refined_eval.level_fraction))
            ),
        }
        gates = {
            **dict(physical.gates),
            "rate": metrics["rate_coordinate_difference"]
            < limits["rate_coordinate_refinement"],
            "algebraic": metrics["algebraic_coordinate_difference"]
            < limits["algebraic_coordinate_refinement"],
            "controller_memory": metrics["controller_memory_difference"]
            < limits["controller_memory_refinement"],
            "product": metrics["product_relative_difference"]
            < limits["product_relative_refinement"],
            "level": metrics["level_fraction_difference"]
            < limits["level_fraction_refinement"],
        }
        comparisons.append(
            {
                "coarse_step": int(coarse_1based),
                "refined_step": int(refined_1based),
                "time_seconds": float(coarse_1based) * COARSE_DT_SEC,
                "physical_metrics": dict(physical.metrics),
                "legacy_unfloored_relative_diagnostic": (
                    physical.legacy_unfloored_relative_diagnostic
                ),
                **metrics,
                "gates": gates,
                "pass_gate": all(gates.values()),
            }
        )
    return {
        "comparisons": comparisons,
        "comparison_count": len(comparisons),
        "worst_absolute_component_difference_lbmol": max(
            item["physical_metrics"]["maximum_absolute_component_difference_lbmol"]
            for item in comparisons
        ),
        "worst_component_l1_lbmol": max(
            item["physical_metrics"]["component_difference_l1_lbmol"]
            for item in comparisons
        ),
        "worst_rate_coordinate_difference": max(
            item["rate_coordinate_difference"] for item in comparisons
        ),
        "worst_algebraic_coordinate_difference": max(
            item["algebraic_coordinate_difference"] for item in comparisons
        ),
        "worst_controller_memory_difference": max(
            item["controller_memory_difference"] for item in comparisons
        ),
        "worst_product_relative_difference": max(
            item["product_relative_difference"] for item in comparisons
        ),
        "worst_level_fraction_difference": max(
            item["level_fraction_difference"] for item in comparisons
        ),
        "pass_gate": all(item["pass_gate"] for item in comparisons),
    }


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = dd187.dd186._load(contract_path)
    _verify(payload, contract_path, result_path)
    _validate_source(dd187.dd186._load(DD187_RESULT))
    dd185_contract = dd187.dd186._load(DD185_CONTRACT)
    spec = dd187.dd186.dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd187.dd186.dd171.dd168._reference(payload["reference"])
    state = dd187.dd186.dd171._state(payload["accepted_root_state"])
    controlled = dd185._controlled_contract(spec, dd185_contract)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-188 controlled structural contract changed")
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    initial = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["initial_controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    setpoint_values = np.asarray(
        (setpoints.top_fraction, setpoints.bottom_fraction), dtype=float
    )
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    provider = dd187.dd186.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd187.dd186._settings(payload)
    paths = payload["paths"]
    common = dict(
        contract=controlled,
        spec=spec,
        reference=reference,
        initial_template=state,
        provider=provider,
        call_audit=audit,
        initial_inventory_lbmol=inventory,
        initial_controller_memory=memory,
        level_setpoints=setpoints,
        initial_solve_coordinates=initial,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=product_reference,
        duration_seconds=float(paths["duration_seconds"]),
        settings=settings,
    )
    started = time.perf_counter()
    coarse = run_terminal_inventory_control_trajectory(
        **common,
        step_seconds=float(paths["coarse_step_seconds"]),
        name="dd188_coarse_0p25s",
    )
    refined = run_terminal_inventory_control_trajectory(
        **common,
        step_seconds=float(paths["refined_step_seconds"]),
        name="dd188_refined_0p125s",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd187.dd186._provider_summary(audit)
    limits = payload["limits"]
    coarse_report = _trajectory_report(
        coarse, spec, inventory, initial, memory, setpoint_values,
        product_reference, limits, payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    refined_report = _trajectory_report(
        refined, spec, inventory, initial, memory, setpoint_values,
        product_reference, limits, payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    coarse_evaluations = _evaluations(coarse)
    refined_evaluations = _evaluations(refined)
    shared = _shared_refinement(
        inventory,
        coarse_evaluations,
        refined_evaluations,
        paths["shared_step_pairs_1based"],
        InventoryRefinementLimits.from_mapping(payload["physical_refinement_limits"]),
        limits,
    )
    response = {
        "coarse": dd187._path_response(
            inventory,
            coarse_evaluations,
            [COARSE_DT_SEC] * len(coarse_evaluations),
            spec,
        ),
        "refined": dd187._path_response(
            inventory,
            refined_evaluations,
            [REFINED_DT_SEC] * len(refined_evaluations),
            spec,
        ),
    }
    response_gates = {}
    for name, values in response.items():
        expected = values["expected_total_inventory_change_lbmol"]
        relative_error = abs(values["total_inventory_change_lbmol"] - expected) / max(
            abs(expected), 1.0e-12
        )
        report = coarse_report if name == "coarse" else refined_report
        response_gates[name] = {
            "positive": values["total_inventory_change_lbmol"] > 0.0,
            "monotone": report["total_inventory_strictly_increasing"],
            "integrated_expected": relative_error
            < limits["integrated_response_relative_error"],
            "component_identity": values["component_inventory_identity_max_abs_lbmol"]
            < limits["global_component_inventory_identity_lbmol"],
        }
        values["total_inventory_relative_error"] = relative_error
    response_gates["cross_grid"] = {
        "total_inventory": abs(
            response["coarse"]["total_inventory_change_lbmol"]
            - response["refined"]["total_inventory_change_lbmol"]
        )
        < limits["cross_grid_total_inventory_lbmol"]
    }
    all_reports = coarse_report["steps"] + refined_report["steps"]
    campaign_gates = {
        "coarse_complete": coarse_report["completed"]
        and coarse_report["step_gates_pass"],
        "refined_complete": refined_report["completed"]
        and refined_report["step_gates_pass"],
        "response": all(all(values.values()) for values in response_gates.values()),
        "shared_time_refinement": shared["pass_gate"],
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "terminal_inventory_control_short_trajectory_passed"
            if passed
            else "terminal_inventory_control_short_trajectory_failed"
        ),
        "decision": (
            "authorize_one_frozen_modest_controlled_trajectory_contract"
            if passed
            else "stop_terminal_control_trajectory_path"
        ),
        "contract_commit": dd187.dd186._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "paths": paths,
        "wall_clock_sec": float(elapsed),
        "completed_roots": len(all_reports),
        "worst_residual": max(item["residual_inf_norm"] for item in all_reports),
        "worst_condition": max(item["jacobian_condition"] for item in all_reports),
        "coarse": coarse_report,
        "refined": refined_report,
        "shared_time_refinement": shared,
        "response": response,
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "response_gates": response_gates,
        "campaign_gates": campaign_gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--source-contract", type=Path, default=DD187_CONTRACT)
    parser.add_argument("--source-result", type=Path, default=DD187_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.source_contract,
            args.source_result,
            args.contract,
            args.contract_doc,
        )
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "paths": output["paths"],
                    "campaign_executed": output["campaign_executed"],
                },
                indent=2,
            )
        )
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(
            json.dumps(
                {
                    "classification": output["classification"],
                    "pass_gate": output["pass_gate"],
                    "decision": output["decision"],
                },
                indent=2,
            )
        )
        raise SystemExit(0 if output["pass_gate"] else 2)
