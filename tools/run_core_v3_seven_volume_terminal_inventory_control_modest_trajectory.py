#!/usr/bin/env python
"""Prepare or execute DD-190's modest controlled seven-volume trajectory."""

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

import adjudicate_core_v3_terminal_inventory_control_short_trajectory as dd189  # noqa: E402
import audit_core_v3_seven_volume_terminal_inventory_control_numerical as dd185  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_short_trajectory as dd188  # noqa: E402
from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (  # noqa: E402
    InventoryRefinementLimits,
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
    run_terminal_inventory_control_trajectory,
)


SCHEMA = "dd190-core-v3-seven-volume-terminal-control-modest-trajectory-contract-v1"
RESULT_SCHEMA = "dd190-core-v3-seven-volume-terminal-control-modest-trajectory-result-v1"
DD188_CONTRACT = Path(
    "logs/dd188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_contract_20260813.json"
)
DD188_RESULT = Path(
    "logs/dd188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_20260813.json"
)
DD189_RESULT = Path(
    "logs/dd189_core_v3_terminal_inventory_control_response_adjudication_20260813.json"
)
DD185_CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
CONTRACT = Path(
    "logs/dd190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_contract_20260813.json"
)
RESULT = Path(
    "logs/dd190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_20260813.md"
)
DURATION_SEC = 10.0
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
    "tools/run_core_v3_seven_volume_terminal_inventory_control_modest_trajectory.py",
    "tests/test_core_v3_terminal_inventory_control_modest_trajectory.py",
)


def _validate_sources(dd188_result: Mapping[str, Any], dd189_result: Mapping[str, Any]) -> None:
    dd189._validate_source(dd188_result)
    if not dd189_result.get("pass_gate") or dd189_result.get("decision") != (
        "authorize_one_frozen_modest_controlled_trajectory_contract_under_response_scaled_policy"
    ):
        raise RuntimeError("DD-190 requires the accepted DD-189 policy")
    if any(
        int(dd189_result.get(name, -1)) != 0
        for name in (
            "model_calls",
            "provider_calls",
            "solver_calls",
            "endpoint_regeneration_calls",
        )
    ):
        raise RuntimeError("DD-189 is no longer a zero-call adjudication")
    if dd189_result.get("dd188_reclassified") or dd189_result.get("dd188_rerun"):
        raise RuntimeError("DD-188 preservation status changed")


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    return "\n".join(
        (
            "# DD-190 Seven-Volume Controlled Modest-Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Disturbance, setpoints, PI constants, product references, solver, and provider: unchanged",
            f"- Duration: `{paths['duration_seconds']} s`",
            f"- Coarse path: `{paths['coarse_steps']} x {paths['coarse_step_seconds']} s`",
            f"- Refined path: `{paths['refined_steps']} x {paths['refined_step_seconds']} s`",
            f"- Shared-time comparisons: `{paths['shared_time_count']}`",
            "- Controlled signed-total policy: external-flow explanation plus response-relative gate",
            "- Property evaluation during preparation: `False`",
            "- Timestep execution during preparation: `False`",
            "",
            "Commit before the one execution. No tuning, retry, alternate grid, "
            "projection, clipping, fallback, or parallel substitution is authorized.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    shared = payload["shared_time_refinement"]
    response = payload["response"]
    return "\n".join(
        (
            "# DD-190 Seven-Volume Controlled Modest-Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}`",
            f"- Worst residual: `{payload['worst_residual']:.6e}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Worst absolute inventory refinement: "
            f"`{shared['worst_absolute_component_difference_lbmol']:.6e} lbmol`",
            f"- Worst response-relative total difference: "
            f"`{shared['worst_response_relative_total_difference']:.6e}`",
            f"- Coarse/refined total accumulation: "
            f"`{response['coarse']['total_inventory_change_lbmol']:.6e}` / "
            f"`{response['refined']['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Final coarse products D/B: "
            f"`{payload['final_controller_state']['coarse']['distillate_lbmolph']:.6f}` / "
            f"`{payload['final_controller_state']['coarse']['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Logical provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Controller tuning/retry/parallel substitution: `False / False / False`",
            "",
        )
    )


def prepare(
    source_contract_path: Path,
    dd188_result_path: Path,
    dd189_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = dd188.dd187.dd186._load(source_contract_path)
    dd188_result = dd188.dd187.dd186._load(dd188_result_path)
    dd189_result = dd188.dd187.dd186._load(dd189_result_path)
    _validate_sources(dd188_result, dd189_result)
    coarse_count = dd188.dd177._step_count(DURATION_SEC, COARSE_DT_SEC)
    refined_count = dd188.dd177._step_count(DURATION_SEC, REFINED_DT_SEC)
    pairs = dd188.dd177._shared_step_pairs(coarse_count, refined_count)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd188.dd187.dd186._git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): dd188.dd187.dd186._sha(ROOT / path)
            for path in (
                source_contract_path,
                dd188_result_path,
                dd189_result_path,
                DD185_CONTRACT,
            )
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
            "unexplained_cross_grid_difference_lbmol": 1.0e-10,
            "cross_grid_difference_relative_to_response": 1.0e-5,
            "rate_coordinate_refinement": 1.0e-5,
            "algebraic_coordinate_refinement": 1.0e-5,
            "controller_memory_refinement": 1.0e-7,
            "product_relative_refinement": 1.0e-6,
            "level_fraction_refinement": 1.0e-8,
            "provider_calls": 650000,
            "wall_clock_sec": 240.0,
        },
        "physical_refinement_limits": source["physical_refinement_limits"],
        "controlled_signed_total_policy": dd189_result["metrics"],
        "required_rank": 58,
        "exact_state_memoization": source["exact_state_memoization"],
        "implementation_sha256": {
            path: dd188.dd187.dd186._sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "either trajectory fails to complete every root",
            "any root loses closure, rank, condition, physicality, or conservation",
            "response is not positive, monotone, or consistent with external flow",
            "any shared-time physical or controller refinement gate fails",
            "any shared total difference is unexplained or too large relative to response",
            "provider ownership, call, or wall gates fail",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "controller_tuning_attempted": False,
        "retry_authorized": False,
        "parallel_substitution_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = dd188.dd187.dd186._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-190 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd188.dd187.dd186._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-190 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd188.dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-190 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd188.dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-190 implementation changed: {path}")
    if dd188.dd187.dd186._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-190 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-190 result exists; rerun is prohibited")
    if not dd188.dd187.dd186._git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-190 contract is not committed")


def _prefix_response(
    initial_inventory: np.ndarray,
    evaluations: Sequence[TerminalInventoryControlBackwardEulerEvaluation],
    count: int,
    step_seconds: float,
    spec: Any,
) -> dict[str, Any]:
    return dd188.dd187._path_response(
        initial_inventory,
        evaluations[:count],
        [step_seconds] * count,
        spec,
    )


def _controlled_shared_refinement(
    initial_inventory: np.ndarray,
    coarse: Sequence[TerminalInventoryControlBackwardEulerEvaluation],
    refined: Sequence[TerminalInventoryControlBackwardEulerEvaluation],
    pairs: Sequence[Sequence[int]],
    physical_limits: InventoryRefinementLimits,
    limits: Mapping[str, float],
    spec: Any,
) -> dict[str, Any]:
    base = dd188._shared_refinement(
        initial_inventory,
        coarse,
        refined,
        pairs,
        physical_limits,
        limits,
    )
    comparisons = []
    for item in base["comparisons"]:
        coarse_count = int(item["coarse_step"])
        refined_count = int(item["refined_step"])
        coarse_response = _prefix_response(
            initial_inventory, coarse, coarse_count, COARSE_DT_SEC, spec
        )
        refined_response = _prefix_response(
            initial_inventory, refined, refined_count, REFINED_DT_SEC, spec
        )
        actual_difference = (
            coarse_response["total_inventory_change_lbmol"]
            - refined_response["total_inventory_change_lbmol"]
        )
        expected_difference = (
            coarse_response["expected_total_inventory_change_lbmol"]
            - refined_response["expected_total_inventory_change_lbmol"]
        )
        unexplained = abs(actual_difference - expected_difference)
        response_scale = max(
            abs(coarse_response["total_inventory_change_lbmol"]),
            abs(refined_response["total_inventory_change_lbmol"]),
            1.0e-12,
        )
        response_relative = abs(actual_difference) / response_scale
        gates = dict(item["gates"])
        signed_total_pass = gates.pop("signed_total")
        gates["signed_total_reported_diagnostic"] = True
        gates["external_flow_explanation"] = (
            unexplained < limits["unexplained_cross_grid_difference_lbmol"]
        )
        gates["response_relative_total"] = (
            response_relative
            < limits["cross_grid_difference_relative_to_response"]
        )
        comparisons.append(
            {
                **item,
                "signed_total_original_gate": signed_total_pass,
                "actual_total_difference_lbmol": actual_difference,
                "expected_external_flow_difference_lbmol": expected_difference,
                "unexplained_total_difference_lbmol": unexplained,
                "response_relative_total_difference": response_relative,
                "gates": gates,
                "pass_gate": all(gates.values()),
            }
        )
    return {
        "comparisons": comparisons,
        "comparison_count": len(comparisons),
        "worst_absolute_component_difference_lbmol": base[
            "worst_absolute_component_difference_lbmol"
        ],
        "worst_component_l1_lbmol": base["worst_component_l1_lbmol"],
        "worst_rate_coordinate_difference": base[
            "worst_rate_coordinate_difference"
        ],
        "worst_algebraic_coordinate_difference": base[
            "worst_algebraic_coordinate_difference"
        ],
        "worst_controller_memory_difference": base[
            "worst_controller_memory_difference"
        ],
        "worst_product_relative_difference": base[
            "worst_product_relative_difference"
        ],
        "worst_level_fraction_difference": base[
            "worst_level_fraction_difference"
        ],
        "worst_unexplained_total_difference_lbmol": max(
            item["unexplained_total_difference_lbmol"] for item in comparisons
        ),
        "worst_response_relative_total_difference": max(
            item["response_relative_total_difference"] for item in comparisons
        ),
        "original_signed_total_failure_count": sum(
            not item["signed_total_original_gate"] for item in comparisons
        ),
        "pass_gate": all(item["pass_gate"] for item in comparisons),
    }


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = dd188.dd187.dd186._load(contract_path)
    _verify(payload, contract_path, result_path)
    dd188_result = dd188.dd187.dd186._load(DD188_RESULT)
    dd189_result = dd188.dd187.dd186._load(DD189_RESULT)
    _validate_sources(dd188_result, dd189_result)
    dd185_contract = dd188.dd187.dd186._load(DD185_CONTRACT)
    spec = dd188.dd187.dd186.dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd188.dd187.dd186.dd171.dd168._reference(payload["reference"])
    state = dd188.dd187.dd186.dd171._state(payload["accepted_root_state"])
    controlled = dd185._controlled_contract(spec, dd185_contract)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-190 controlled structural contract changed")
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    initial = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["initial_controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    setpoint_values = np.asarray(
        (setpoints.top_fraction, setpoints.bottom_fraction), dtype=float
    )
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    provider = dd188.dd187.dd186.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd188.dd187.dd186._settings(payload)
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
        name="dd190_coarse_0p25s",
    )
    refined = run_terminal_inventory_control_trajectory(
        **common,
        step_seconds=float(paths["refined_step_seconds"]),
        name="dd190_refined_0p125s",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd188.dd187.dd186._provider_summary(audit)
    limits = payload["limits"]
    coarse_report = dd188._trajectory_report(
        coarse, spec, inventory, initial, memory, setpoint_values,
        product_reference, limits, payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    refined_report = dd188._trajectory_report(
        refined, spec, inventory, initial, memory, setpoint_values,
        product_reference, limits, payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    coarse_evaluations = dd188._evaluations(coarse)
    refined_evaluations = dd188._evaluations(refined)
    shared = _controlled_shared_refinement(
        inventory,
        coarse_evaluations,
        refined_evaluations,
        paths["shared_step_pairs_1based"],
        InventoryRefinementLimits.from_mapping(payload["physical_refinement_limits"]),
        limits,
        spec,
    )
    response = {
        "coarse": dd188.dd187._path_response(
            inventory,
            coarse_evaluations,
            [COARSE_DT_SEC] * len(coarse_evaluations),
            spec,
        ),
        "refined": dd188.dd187._path_response(
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
        values["total_inventory_relative_error"] = relative_error
        response_gates[name] = {
            "positive": values["total_inventory_change_lbmol"] > 0.0,
            "monotone": report["total_inventory_strictly_increasing"],
            "integrated_expected": relative_error
            < limits["integrated_response_relative_error"],
            "component_identity": values["component_inventory_identity_max_abs_lbmol"]
            < limits["global_component_inventory_identity_lbmol"],
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
    final_controller_state = {}
    for name, evaluation in (
        ("coarse", coarse_evaluations[-1]),
        ("refined", refined_evaluations[-1]),
    ):
        final_controller_state[name] = {
            "level_fraction": dd188.dd187.dd186._vector(evaluation.level_fraction),
            "controller_memory": dd188.dd187.dd186._vector(
                evaluation.endpoint_controller_memory
            ),
            "product_log_ratio": dd188.dd187.dd186._vector(
                evaluation.product_log_ratio
            ),
            "distillate_lbmolph": evaluation.distillate_lbmolph,
            "bottoms_lbmolph": evaluation.bottoms_lbmolph,
        }
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "terminal_inventory_control_modest_trajectory_passed"
            if passed
            else "terminal_inventory_control_modest_trajectory_failed"
        ),
        "decision": (
            "authorize_controlled_parallel_jacobian_integration_contract"
            if passed
            else "stop_terminal_control_trajectory_path"
        ),
        "contract_commit": dd188.dd187.dd186._git("rev-parse", "HEAD"),
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
        "final_controller_state": final_controller_state,
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "response_gates": response_gates,
        "campaign_gates": campaign_gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
        "parallel_substitution_attempted": False,
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
    parser.add_argument("--source-contract", type=Path, default=DD188_CONTRACT)
    parser.add_argument("--dd188-result", type=Path, default=DD188_RESULT)
    parser.add_argument("--dd189-result", type=Path, default=DD189_RESULT)
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
            args.dd188_result,
            args.dd189_result,
            args.contract,
            args.contract_doc,
        )
        print(json.dumps({"schema_id": output["schema_id"], "contract_payload_sha256": output["contract_payload_sha256"], "paths": output["paths"], "campaign_executed": output["campaign_executed"]}, indent=2))
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(json.dumps({"classification": output["classification"], "pass_gate": output["pass_gate"], "decision": output["decision"]}, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
