#!/usr/bin/env python
"""Prepare or execute DD-178's ten-second physical-policy trajectory."""

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

import run_core_v3_seven_volume_physical_short_trajectory as dd177  # noqa: E402

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (  # noqa: E402
    InventoryRefinementLimits,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.short_trajectory_v1 import (  # noqa: E402
    run_short_trajectory,
)


SCHEMA = "dd178-core-v3-seven-volume-physical-modest-trajectory-contract-v1"
RESULT_SCHEMA = "dd178-core-v3-seven-volume-physical-modest-trajectory-result-v1"
DD177_CONTRACT = Path(
    "logs/dd177_core_v3_seven_volume_physical_short_trajectory_contract_20260812.json"
)
DD177_RESULT = Path(
    "logs/dd177_core_v3_seven_volume_physical_short_trajectory_20260812.json"
)
CONTRACT = Path(
    "logs/dd178_core_v3_seven_volume_physical_modest_trajectory_contract_20260812.json"
)
RESULT = Path(
    "logs/dd178_core_v3_seven_volume_physical_modest_trajectory_20260812"
)
DURATION_SEC = 10.0
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
    "tools/run_core_v3_seven_volume_physical_modest_trajectory.py",
    "tests/test_core_v3_seven_volume_physical_modest_trajectory.py",
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
    if result.get("pass_gate") is not True:
        raise RuntimeError("DD-178 requires the accepted DD-177 result")
    if result.get("decision") != (
        "authorize_one_frozen_modest_open_loop_trajectory_contract"
    ):
        raise RuntimeError("DD-177 did not authorize DD-178")
    if not all(result.get("campaign_gates", {}).values()):
        raise RuntimeError("DD-177 contains a failed campaign gate")
    if result.get("completed_roots") != 24:
        raise RuntimeError("DD-177 root evidence changed")
    if result.get("controller_attempted") is not False:
        raise RuntimeError("DD-177 controller boundary changed")


def _compact_path(report: Mapping[str, Any]) -> dict[str, Any]:
    steps = list(report["steps"])
    if not steps:
        raise ValueError("DD-178 cannot compact an empty trajectory")
    compact_steps = []
    for step in steps:
        compact_steps.append(
            {
                "index": step["index"],
                "time_seconds": step["time_seconds"],
                "success": step["success"],
                "nfev": step["nfev"],
                "njev": step["njev"],
                "wall_clock_sec": step["wall_clock_sec"],
                "residual_inf_norm": step["residual_inf_norm"],
                "jacobian_rank": step["jacobian_rank"],
                "jacobian_condition": step["jacobian_condition"],
                "component_rate_max_abs_lbmolph": step[
                    "component_rate_max_abs_lbmolph"
                ],
                "energy_storage_rate_max_abs_BTUph": step[
                    "energy_storage_rate_max_abs_BTUph"
                ],
                "maximum_equilibrium_residual": step[
                    "maximum_equilibrium_residual"
                ],
                "component_conservation_relative_error": step[
                    "component_conservation_relative_error"
                ],
                "energy_conservation_relative_error": step[
                    "energy_conservation_relative_error"
                ],
                "component_kinematic_identity": step[
                    "component_kinematic_identity"
                ],
                "energy_kinematic_identity": step["energy_kinematic_identity"],
                "physical_pass": step["physical_pass"],
                "gates": step["gates"],
            }
        )
    endpoint = steps[-1]
    return {
        "name": report["name"],
        "step_seconds": report["step_seconds"],
        "requested_steps": report["requested_steps"],
        "completed_steps": report["completed_steps"],
        "completed": report["completed"],
        "step_gates_pass": report["step_gates_pass"],
        "total_inventory_history_lbmol": report[
            "total_inventory_history_lbmol"
        ],
        "total_inventory_strictly_increasing": report[
            "total_inventory_strictly_increasing"
        ],
        "steps": compact_steps,
        "endpoint": {
            "inventory_lbmol": endpoint["inventory_lbmol"],
            "rate_coordinates": endpoint["rate_coordinates"],
            "algebraic_coordinates": endpoint["algebraic_coordinates"],
            "temperature_F": endpoint["temperature_F"],
            "physical": endpoint["physical"],
        },
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    return "\n".join(
        (
            "# DD-178 Seven-Volume Physical-Policy Modest-Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Disturbance: unchanged DD-177 open-loop feed step",
            f"- Duration: `{paths['duration_seconds']} s`",
            f"- Coarse path: `{paths['coarse_steps']} x "
            f"{paths['coarse_step_seconds']} s`",
            f"- Refined path: `{paths['refined_steps']} x "
            f"{paths['refined_step_seconds']} s`",
            f"- Shared-time comparisons: `{paths['shared_time_count']}`",
            "- Evidence: compact per-root scalars plus complete endpoints",
            "- Legacy unfloored component ratio: diagnostic only",
            "- Controllers: disabled",
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
            "# DD-178 Seven-Volume Physical-Policy Modest-Trajectory Result",
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
    dd177_contract_path: Path,
    dd177_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd177_contract_path)
    result = _load(dd177_result_path)
    _validate_source(result)
    coarse_steps = dd177._step_count(DURATION_SEC, COARSE_DT_SEC)
    refined_steps = dd177._step_count(DURATION_SEC, REFINED_DT_SEC)
    pairs = dd177._shared_step_pairs(coarse_steps, refined_steps)
    limits = dict(source["limits"])
    limits["provider_calls"] = 650_000
    limits["wall_clock_sec"] = 240.0
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd177_contract_path": str(dd177_contract_path).replace("\\", "/"),
        "dd177_contract_sha256": _sha(ROOT / dd177_contract_path),
        "dd177_result_path": str(dd177_result_path).replace("\\", "/"),
        "dd177_result_sha256": _sha(ROOT / dd177_result_path),
        "accuracy_policy_document": source["accuracy_policy_document"],
        "accuracy_policy_document_sha256": source[
            "accuracy_policy_document_sha256"
        ],
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
        "evidence_policy": {
            "compact_per_root_scalars": True,
            "complete_endpoint_states": True,
            "all_shared_time_refinement_metrics": True,
        },
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
        raise RuntimeError("DD-178 contract already exists")
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
        raise RuntimeError("DD-178 contract payload hash mismatch")
    for source_key, hash_key in (
        ("dd177_contract_path", "dd177_contract_sha256"),
        ("dd177_result_path", "dd177_result_sha256"),
        ("accuracy_policy_document", "accuracy_policy_document_sha256"),
    ):
        if _sha(ROOT / payload[source_key]) != payload[hash_key]:
            raise RuntimeError(f"DD-178 source changed: {payload[source_key]}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-178 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-178 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-178 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-178 contract is not committed")


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    _validate_source(_load(Path(payload["dd177_result_path"])))
    spec = dd177.dd175.dd173.dd172.dd171.dd168._spec(
        payload["disturbed_source_mapping"],
        float(payload["disturbed_operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd177.dd175.dd173.dd172.dd171.dd168._reference(
        payload["reference"]
    )
    state = dd177.dd175.dd173.dd172.dd171._state(payload["accepted_root_state"])
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=payload["accepted_root_artifact"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-178 structural contract changed")
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-178 inventory mapping changed")
    if not np.allclose(algebraic, payload["accepted_root_algebraic_coordinates"]):
        raise RuntimeError("DD-178 algebraic mapping changed")

    provider = dd177.dd175.dd173.dd172.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd177.dd175.dd173.dd172._settings(payload)
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
        name="dd178_coarse_0p25s",
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
        name="dd178_refined_0p125s",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd177.dd175.dd173.dd172._provider_summary(audit)

    limits = payload["limits"]
    coarse_report = dd177._trajectory_report(
        coarse,
        spec,
        inventory,
        algebraic,
        limits,
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    refined_report = dd177._trajectory_report(
        refined,
        spec,
        inventory,
        algebraic,
        limits,
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    coarse_evaluations = dd177._evaluations(coarse)
    refined_evaluations = dd177._evaluations(refined)
    physical_limits = InventoryRefinementLimits.from_mapping(
        payload["physical_refinement_limits"]
    )
    shared_refinement = dd177._shared_refinement(
        inventory,
        coarse_evaluations,
        refined_evaluations,
        paths["shared_step_pairs_1based"],
        physical_limits,
        limits["refinement_rate_coordinate"],
        limits["refinement_algebraic"],
    )
    response = {
        "coarse": dd177.dd175.dd173._path_response(
            inventory,
            coarse_evaluations,
            [COARSE_DT_SEC] * len(coarse_evaluations),
            spec,
        ),
        "refined": dd177.dd175.dd173._path_response(
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
            "seven_volume_physical_modest_trajectory_passed"
            if passed
            else "seven_volume_physical_modest_trajectory_failed"
        ),
        "decision": (
            "authorize_one_frozen_longer_open_loop_trajectory_contract"
            if passed
            else "stop_physical_trajectory_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "disturbance": payload["disturbance"],
        "paths": paths,
        "wall_clock_sec": float(elapsed),
        "coarse": _compact_path(coarse_report),
        "refined": _compact_path(refined_report),
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
    parser.add_argument("--dd177-contract", type=Path, default=DD177_CONTRACT)
    parser.add_argument("--dd177-result", type=Path, default=DD177_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd177_contract, args.dd177_result, args.contract)
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
