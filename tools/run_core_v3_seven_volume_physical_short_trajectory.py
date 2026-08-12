#!/usr/bin/env python
"""Prepare or execute DD-177's physical-policy short open-loop trajectory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_smaller_moving_step as dd175  # noqa: E402

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    BackwardEulerEvaluation,
)
from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (  # noqa: E402
    InventoryRefinementLimits,
    assess_inventory_refinement,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.short_trajectory_v1 import (  # noqa: E402
    ShortTrajectoryResult,
    run_short_trajectory,
)


SCHEMA = "dd177-core-v3-seven-volume-physical-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd177-core-v3-seven-volume-physical-short-trajectory-result-v1"
DD175_CONTRACT = Path(
    "logs/dd175_core_v3_seven_volume_smaller_moving_step_contract_20260812.json"
)
DD175_RESULT = Path(
    "logs/dd175_core_v3_seven_volume_smaller_moving_step_20260812.json"
)
CONTRACT = Path(
    "logs/dd177_core_v3_seven_volume_physical_short_trajectory_contract_20260812.json"
)
RESULT = Path(
    "logs/dd177_core_v3_seven_volume_physical_short_trajectory_20260812"
)
DURATION_SEC = 2.0
COARSE_DT_SEC = 0.25
REFINED_DT_SEC = 0.125
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/physical_refinement_policy_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/short_trajectory_v1.py",
    "tools/run_core_v3_seven_volume_stationary_step.py",
    "tools/run_core_v3_seven_volume_moving_step.py",
    "tools/run_core_v3_seven_volume_smaller_moving_step.py",
    "tools/run_core_v3_seven_volume_physical_short_trajectory.py",
    "tests/test_core_v3_seven_volume_physical_short_trajectory.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _validate_source(result: Mapping[str, Any]) -> None:
    if result.get("pass_gate") is not False:
        raise RuntimeError("DD-177 requires DD-175's preserved formal failure")
    if result.get("decision") != "stop_before_trajectory":
        raise RuntimeError("DD-175 stop decision changed")
    expected_campaign = {
        "steps": True,
        "response": True,
        "refinement": False,
        "physical_refinement": True,
        "provider": True,
        "provider_calls": True,
        "wall_clock": True,
    }
    if result.get("campaign_gates") != expected_campaign:
        raise RuntimeError("DD-175 failure pattern changed")
    failed = [
        name for name, passed in result["refinement_gates"].items() if not passed
    ]
    if failed != ["inventory"]:
        raise RuntimeError("DD-175 did not fail only legacy inventory refinement")
    if not all(result["physical_refinement_gates"].values()):
        raise RuntimeError("DD-175 did not pass the physical refinement gates")


def _step_count(duration: float, step: float) -> int:
    count = int(round(float(duration) / float(step)))
    if count <= 0 or not np.isclose(count * step, duration, atol=1.0e-12):
        raise ValueError("trajectory duration must be an exact step multiple")
    return count


def _shared_step_pairs(
    coarse_count: int, refined_count: int
) -> tuple[tuple[int, int], ...]:
    if coarse_count <= 0 or refined_count != 2 * coarse_count:
        raise ValueError("refined trajectory must contain two steps per coarse step")
    return tuple((coarse_index, 2 * coarse_index) for coarse_index in range(1, coarse_count + 1))


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    return "\n".join(
        (
            "# DD-177 Seven-Volume Physical-Policy Short-Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Disturbance: unchanged DD-173 `+0.1%` feed rate and enthalpy",
            f"- Duration: `{paths['duration_seconds']} s`",
            f"- Coarse path: `{paths['coarse_steps']} x "
            f"{paths['coarse_step_seconds']} s`",
            f"- Refined path: `{paths['refined_steps']} x "
            f"{paths['refined_step_seconds']} s`",
            f"- Shared-time comparisons: `{paths['shared_time_count']}`",
            "- Legacy unfloored component ratio: diagnostic only",
            "- Controllers: disabled",
            "- Live property evaluation during preparation: `False`",
            "",
            "Commit before the one execution. Retry, alternate grid, controller, "
            "projection, clipping, fallback, or continuation is prohibited.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    refinement = payload["shared_time_refinement"]
    return "\n".join(
        (
            "# DD-177 Seven-Volume Physical-Policy Short-Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}`",
            f"- Worst residual: `{payload['worst_residual']:.6e}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Worst physical absolute refinement: "
            f"`{refinement['worst_absolute_component_difference_lbmol']:.6e} lbmol`",
            f"- Worst physical volume-relative refinement: "
            f"`{refinement['worst_volume_holdup_relative_difference']:.6e}`",
            f"- Legacy unfloored ratio diagnostic: "
            f"`{refinement['worst_legacy_unfloored_relative_diagnostic']:.6e}`",
            f"- Logical provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Controllers attempted: `False`",
            "",
        )
    )


def prepare(
    dd175_contract_path: Path,
    dd175_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd175_contract_path)
    result = _load(dd175_result_path)
    _validate_source(result)
    coarse_steps = _step_count(DURATION_SEC, COARSE_DT_SEC)
    refined_steps = _step_count(DURATION_SEC, REFINED_DT_SEC)
    pairs = _shared_step_pairs(coarse_steps, refined_steps)
    limits = dict(source["limits"])
    limits["provider_calls"] = 150_000
    limits["wall_clock_sec"] = 180.0
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd175_contract_path": str(dd175_contract_path).replace("\\", "/"),
        "dd175_contract_sha256": _sha(ROOT / dd175_contract_path),
        "dd175_result_path": str(dd175_result_path).replace("\\", "/"),
        "dd175_result_sha256": _sha(ROOT / dd175_result_path),
        "accuracy_policy_document": "docs/core_v3_dynamic_accuracy_policy_20260812.md",
        "accuracy_policy_document_sha256": _sha(
            ROOT / "docs/core_v3_dynamic_accuracy_policy_20260812.md"
        ),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "disturbed_source_mapping": source["disturbed_source_mapping"],
        "disturbed_operating_spec": source["disturbed_operating_spec"],
        "reference": source["reference"],
        "accepted_root_artifact": source["accepted_root_artifact"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "accepted_root_algebraic_coordinates": source[
            "accepted_root_algebraic_coordinates"
        ],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "disturbance": source["disturbance"],
        "solver": source["solver"],
        "paths": {
            "duration_seconds": DURATION_SEC,
            "coarse_step_seconds": COARSE_DT_SEC,
            "coarse_steps": coarse_steps,
            "refined_step_seconds": REFINED_DT_SEC,
            "refined_steps": refined_steps,
            "shared_time_count": len(pairs),
            "shared_step_pairs_1based": [list(pair) for pair in pairs],
        },
        "limits": limits,
        "physical_refinement_limits": source["physical_refinement_limits"],
        "required_rank": source["required_rank"],
        "exact_state_memoization": source["exact_state_memoization"],
        "legacy_unfloored_relative_inventory_is_gate": False,
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "any root, rank, condition, physical, or conservation gate fails",
            "any shared-time physical refinement gate fails",
            "rate or algebraic shared-time refinement exceeds its frozen limit",
            "the feed response is absent, nonmonotone, or inconsistent",
            "provider ownership, call, or wall gate fails",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "controller_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-177 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-177 contract payload hash mismatch")
    for source_key, hash_key in (
        ("dd175_contract_path", "dd175_contract_sha256"),
        ("dd175_result_path", "dd175_result_sha256"),
        ("accuracy_policy_document", "accuracy_policy_document_sha256"),
    ):
        if _sha(ROOT / payload[source_key]) != payload[hash_key]:
            raise RuntimeError(f"DD-177 source changed: {payload[source_key]}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-177 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-177 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-177 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-177 contract is not committed")


def _trajectory_report(
    trajectory: ShortTrajectoryResult,
    spec: Any,
    initial_inventory: np.ndarray,
    initial_algebraic: np.ndarray,
    limits: Mapping[str, float],
    required_rank: int,
    max_nfev: int,
) -> dict[str, Any]:
    previous_inventory = initial_inventory
    previous_algebraic = initial_algebraic
    reports = []
    total_history = [float(np.sum(initial_inventory))]
    for record in trajectory.steps:
        report = dd175.dd173.dd172._step_report(
            record.outcome,
            spec,
            previous_inventory,
            previous_algebraic,
            trajectory.step_seconds,
        )
        report["index"] = record.index
        report["time_seconds"] = record.time_seconds
        report["gates"] = {
            "success": report["success"] and report["nfev"] <= max_nfev,
            "residual": report["residual_inf_norm"] < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == required_rank,
            "condition": report["jacobian_condition"] < limits["condition"],
            "equilibrium": report["maximum_equilibrium_residual"]
            < limits["equilibrium_residual"],
            "component_conservation": report[
                "component_conservation_relative_error"
            ] < limits["component_conservation"],
            "energy_conservation": report["energy_conservation_relative_error"]
            < limits["energy_conservation"],
            "component_kinematics": report["component_kinematic_identity"]
            < limits["kinematic_identity"],
            "energy_kinematics": report["energy_kinematic_identity"]
            < limits["kinematic_identity"],
            "physical": report["physical_pass"],
        }
        reports.append(report)
        evaluation = record.outcome.evaluation
        if not isinstance(evaluation, BackwardEulerEvaluation):
            raise TypeError("DD-177 trajectory contains a non-step endpoint")
        previous_inventory = evaluation.endpoint_inventory_lbmol
        previous_algebraic = evaluation.algebraic_coordinates
        total_history.append(float(np.sum(previous_inventory)))
    return {
        "name": trajectory.name,
        "step_seconds": trajectory.step_seconds,
        "requested_steps": trajectory.requested_steps,
        "completed_steps": trajectory.completed_steps,
        "completed": trajectory.completed,
        "steps": reports,
        "step_gates_pass": len(reports) == trajectory.requested_steps
        and all(all(report["gates"].values()) for report in reports),
        "total_inventory_history_lbmol": total_history,
        "total_inventory_strictly_increasing": bool(
            np.all(np.diff(total_history) > 0.0)
        ),
    }


def _evaluations(trajectory: ShortTrajectoryResult) -> list[BackwardEulerEvaluation]:
    values = []
    for record in trajectory.steps:
        evaluation = record.outcome.evaluation
        if not isinstance(evaluation, BackwardEulerEvaluation):
            raise TypeError("DD-177 trajectory endpoint is invalid")
        values.append(evaluation)
    return values


def _shared_refinement(
    initial_inventory: np.ndarray,
    coarse: Sequence[BackwardEulerEvaluation],
    refined: Sequence[BackwardEulerEvaluation],
    pairs: Sequence[Sequence[int]],
    limits: InventoryRefinementLimits,
    rate_limit: float,
    algebraic_limit: float,
) -> dict[str, Any]:
    comparisons = []
    for coarse_1based, refined_1based in pairs:
        coarse_evaluation = coarse[int(coarse_1based) - 1]
        refined_evaluation = refined[int(refined_1based) - 1]
        assessment = assess_inventory_refinement(
            initial_inventory,
            coarse_evaluation.endpoint_inventory_lbmol,
            refined_evaluation.endpoint_inventory_lbmol,
            limits,
        )
        rate_difference = float(
            np.max(
                np.abs(
                    coarse_evaluation.rate_coordinates
                    - refined_evaluation.rate_coordinates
                )
            )
        )
        algebraic_difference = float(
            np.max(
                np.abs(
                    coarse_evaluation.algebraic_coordinates
                    - refined_evaluation.algebraic_coordinates
                )
            )
        )
        gates = dict(assessment.gates)
        gates["rate"] = rate_difference < rate_limit
        gates["algebraic"] = algebraic_difference < algebraic_limit
        comparisons.append(
            {
                "coarse_step": int(coarse_1based),
                "refined_step": int(refined_1based),
                "time_seconds": float(coarse_1based) * COARSE_DT_SEC,
                "metrics": dict(assessment.metrics),
                "legacy_unfloored_relative_diagnostic": (
                    assessment.legacy_unfloored_relative_diagnostic
                ),
                "rate_coordinate_difference": rate_difference,
                "algebraic_coordinate_difference": algebraic_difference,
                "gates": gates,
                "pass_gate": all(gates.values()),
            }
        )
    return {
        "comparisons": comparisons,
        "comparison_count": len(comparisons),
        "worst_absolute_component_difference_lbmol": max(
            item["metrics"]["maximum_absolute_component_difference_lbmol"]
            for item in comparisons
        ),
        "worst_volume_holdup_relative_difference": max(
            item["metrics"][
                "maximum_volume_holdup_relative_component_difference"
            ]
            for item in comparisons
        ),
        "worst_component_l1_lbmol": max(
            item["metrics"]["component_difference_l1_lbmol"]
            for item in comparisons
        ),
        "worst_legacy_unfloored_relative_diagnostic": max(
            item["legacy_unfloored_relative_diagnostic"] for item in comparisons
        ),
        "worst_rate_coordinate_difference": max(
            item["rate_coordinate_difference"] for item in comparisons
        ),
        "worst_algebraic_coordinate_difference": max(
            item["algebraic_coordinate_difference"] for item in comparisons
        ),
        "pass_gate": all(item["pass_gate"] for item in comparisons),
    }


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    _validate_source(_load(Path(payload["dd175_result_path"])))
    spec = dd175.dd173.dd172.dd171.dd168._spec(
        payload["disturbed_source_mapping"],
        float(payload["disturbed_operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd175.dd173.dd172.dd171.dd168._reference(payload["reference"])
    state = dd175.dd173.dd172.dd171._state(payload["accepted_root_state"])
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=payload["accepted_root_artifact"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-177 structural contract changed")
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-177 inventory mapping changed")
    if not np.allclose(algebraic, payload["accepted_root_algebraic_coordinates"]):
        raise RuntimeError("DD-177 algebraic mapping changed")

    provider = dd175.dd173.dd172.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd175.dd173.dd172._settings(payload)
    paths = payload["paths"]
    started = time.perf_counter()
    coarse = run_short_trajectory(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=float(paths["coarse_step_seconds"]),
        duration_seconds=float(paths["duration_seconds"]),
        settings=settings,
        name="dd177_coarse_0p25s",
    )
    refined = run_short_trajectory(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=float(paths["refined_step_seconds"]),
        duration_seconds=float(paths["duration_seconds"]),
        settings=settings,
        name="dd177_refined_0p125s",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd175.dd173.dd172._provider_summary(audit)

    limits = payload["limits"]
    coarse_report = _trajectory_report(
        coarse,
        spec,
        inventory,
        algebraic,
        limits,
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    refined_report = _trajectory_report(
        refined,
        spec,
        inventory,
        algebraic,
        limits,
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    coarse_evaluations = _evaluations(coarse)
    refined_evaluations = _evaluations(refined)
    physical_limits = InventoryRefinementLimits.from_mapping(
        payload["physical_refinement_limits"]
    )
    shared_refinement = _shared_refinement(
        inventory,
        coarse_evaluations,
        refined_evaluations,
        paths["shared_step_pairs_1based"],
        physical_limits,
        limits["refinement_rate_coordinate"],
        limits["refinement_algebraic"],
    )
    response = {
        "coarse": dd175.dd173._path_response(
            inventory,
            coarse_evaluations,
            [COARSE_DT_SEC] * len(coarse_evaluations),
            spec,
        ),
        "refined": dd175.dd173._path_response(
            inventory,
            refined_evaluations,
            [REFINED_DT_SEC] * len(refined_evaluations),
            spec,
        ),
    }
    response_gates = {
        name: {
            "positive": values["total_inventory_change_lbmol"] > 0.0,
            "detectable": values["total_inventory_change_lbmol"]
            > limits["minimum_total_inventory_response_lbmol"],
            "bounded": values["total_inventory_change_lbmol"]
            < limits["maximum_total_inventory_response_lbmol"],
            "global_component_identity": values[
                "component_inventory_identity_max_abs_lbmol"
            ] < limits["global_component_inventory_identity_lbmol"],
            "monotone": (
                coarse_report["total_inventory_strictly_increasing"]
                if name == "coarse"
                else refined_report["total_inventory_strictly_increasing"]
            ),
        }
        for name, values in response.items()
    }
    all_step_reports = coarse_report["steps"] + refined_report["steps"]
    campaign_gates = {
        "coarse_complete": coarse_report["completed"]
        and coarse_report["step_gates_pass"],
        "refined_complete": refined_report["completed"]
        and refined_report["step_gates_pass"],
        "response": all(all(gates.values()) for gates in response_gates.values()),
        "shared_time_refinement": shared_refinement["pass_gate"],
        "legacy_ratio_diagnostic_only": payload[
            "legacy_unfloored_relative_inventory_is_gate"
        ]
        is False,
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"]
        < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "seven_volume_physical_short_trajectory_passed"
            if passed
            else "seven_volume_physical_short_trajectory_failed"
        ),
        "decision": (
            "authorize_one_frozen_modest_open_loop_trajectory_contract"
            if passed
            else "stop_physical_trajectory_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "disturbance": payload["disturbance"],
        "paths": paths,
        "wall_clock_sec": float(elapsed),
        "coarse": coarse_report,
        "refined": refined_report,
        "response": response,
        "response_gates": response_gates,
        "shared_time_refinement": shared_refinement,
        "completed_roots": len(all_step_reports),
        "worst_residual": max(
            report["residual_inf_norm"] for report in all_step_reports
        ),
        "worst_condition": max(
            report["jacobian_condition"] for report in all_step_reports
        ),
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "campaign_gates": campaign_gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_attempted": False,
        "projection_attempted": False,
        "clipping_attempted": False,
        "fallback_attempted": provider_summary["fallback_attempted"],
    }
    destination = (ROOT / result_path).with_suffix(".json")
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _result_markdown(result), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd175-contract", type=Path, default=DD175_CONTRACT)
    parser.add_argument("--dd175-result", type=Path, default=DD175_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd175_contract, args.dd175_result, args.contract)
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
        output = execute(args.contract, args.result)
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
