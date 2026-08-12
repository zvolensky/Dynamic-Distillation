#!/usr/bin/env python
"""Prepare or execute DD-175's smaller-timestep moving-step proof."""

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

import adjudicate_core_v3_seven_volume_moving_step as dd174  # noqa: E402
import run_core_v3_seven_volume_moving_step as dd173  # noqa: E402

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
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)


SCHEMA = "dd175-core-v3-seven-volume-smaller-moving-step-contract-v1"
RESULT_SCHEMA = "dd175-core-v3-seven-volume-smaller-moving-step-result-v1"
DD173_CONTRACT = Path(
    "logs/dd173_core_v3_seven_volume_moving_step_contract_20260812.json"
)
DD174_RESULT = Path(
    "logs/dd174_core_v3_moving_step_physical_adjudication_20260812.json"
)
CONTRACT = Path(
    "logs/dd175_core_v3_seven_volume_smaller_moving_step_contract_20260812.json"
)
RESULT = Path("logs/dd175_core_v3_seven_volume_smaller_moving_step_20260812")
FULL_DT_SEC = 0.25
HALF_DT_SEC = 0.125
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tools/run_core_v3_seven_volume_stationary_step.py",
    "tools/run_core_v3_seven_volume_moving_step.py",
    "tools/adjudicate_core_v3_seven_volume_moving_step.py",
    "tools/run_core_v3_seven_volume_smaller_moving_step.py",
    "tests/test_core_v3_seven_volume_smaller_moving_step_v1.py",
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


def _validate_authorization(adjudication: Mapping[str, Any]) -> None:
    if adjudication.get("pass_gate") is not True:
        raise RuntimeError("DD-175 requires the passing DD-174 adjudication")
    if adjudication.get("decision") != (
        "authorize_one_frozen_smaller_timestep_moving_proof_contract"
    ):
        raise RuntimeError("DD-174 did not authorize DD-175")
    if adjudication.get("source_dd173_formal_failure_preserved") is not True:
        raise RuntimeError("DD-173 formal failure was not preserved")
    if not all(adjudication.get("gates", {}).values()):
        raise RuntimeError("DD-174 contains a failed gate")
    if any(
        int(adjudication.get(name, -1)) != 0
        for name in ("model_call_count", "provider_call_count", "solver_call_count")
    ):
        raise RuntimeError("DD-174 was not a zero-call adjudication")


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-175 Seven-Volume Smaller Moving-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Disturbance: unchanged DD-173 `+0.1%` feed rate and enthalpy",
            "- Comparison: one `0.25 s` step versus two `0.125 s` steps",
            "- Strict DD-173 relative-inventory gate retained: `<1e-7`",
            "- DD-174 physical-scale gates retained",
            "- Solver/Jacobian/memoization: unchanged",
            "- Live property evaluation during preparation: `False`",
            "",
            "Commit before the one execution. No retry, controller, alternate "
            "disturbance, or trajectory is authorized by this contract.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    metrics = payload["physical_refinement"]
    return "\n".join(
        (
            "# DD-175 Seven-Volume Smaller Moving-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residuals: `{steps['full']['residual_inf_norm']:.6e}`, "
            f"`{steps['half1']['residual_inf_norm']:.6e}`, "
            f"`{steps['half2']['residual_inf_norm']:.6e}`",
            f"- Strict relative-inventory refinement: "
            f"`{payload['refinement']['relative_inventory_difference']:.6e}`",
            f"- Maximum absolute component difference: "
            f"`{metrics['maximum_absolute_component_difference_lbmol']:.6e} lbmol`",
            f"- Volume-holdup-relative difference: "
            f"`{metrics['maximum_volume_holdup_relative_component_difference']:.6e}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Logical provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Controller or trajectory attempted: `False / False`",
            "",
        )
    )


def prepare(
    dd173_contract_path: Path,
    dd174_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd173_contract_path)
    adjudication = _load(dd174_result_path)
    _validate_authorization(adjudication)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd173_contract_path": str(dd173_contract_path).replace("\\", "/"),
        "dd173_contract_sha256": _sha(ROOT / dd173_contract_path),
        "dd174_result_path": str(dd174_result_path).replace("\\", "/"),
        "dd174_result_sha256": _sha(ROOT / dd174_result_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "disturbed_source_mapping": source["disturbed_source_mapping"],
        "disturbed_operating_spec": source["disturbed_operating_spec"],
        "reference": source["reference"],
        "accepted_root_artifact": source["dd172_result_path"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "accepted_root_algebraic_coordinates": source[
            "accepted_root_algebraic_coordinates"
        ],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "disturbance": source["disturbance"],
        "solver": source["solver"],
        "paths": {"full": [FULL_DT_SEC], "refined": [HALF_DT_SEC, HALF_DT_SEC]},
        "limits": source["limits"],
        "physical_refinement_limits": adjudication["limits"],
        "required_rank": source["required_rank"],
        "exact_state_memoization": source["exact_state_memoization"],
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "any root, rank, condition, physical, or conservation gate fails",
            "the strict DD-173 relative-inventory refinement gate fails",
            "any DD-174 physical-scale refinement gate fails",
            "the feed response is absent, negative, or implausibly large",
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
        raise RuntimeError("DD-175 contract already exists")
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
        raise RuntimeError("DD-175 contract payload hash mismatch")
    for source_key, hash_key in (
        ("dd173_contract_path", "dd173_contract_sha256"),
        ("dd174_result_path", "dd174_result_sha256"),
    ):
        if _sha(ROOT / payload[source_key]) != payload[hash_key]:
            raise RuntimeError(f"DD-175 source changed: {payload[source_key]}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-175 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-175 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-175 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-175 contract is not committed")


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    _validate_authorization(_load(Path(payload["dd174_result_path"])))
    spec = dd173.dd172.dd171.dd168._spec(
        payload["disturbed_source_mapping"],
        float(payload["disturbed_operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd173.dd172.dd171.dd168._reference(payload["reference"])
    state = dd173.dd172.dd171._state(payload["accepted_root_state"])
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=payload["accepted_root_artifact"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-175 structural contract changed")
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-175 inventory mapping changed")
    if not np.allclose(algebraic, payload["accepted_root_algebraic_coordinates"]):
        raise RuntimeError("DD-175 algebraic mapping changed")

    provider = dd173.dd172.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd173.dd172._settings(payload)
    scales = payload["fixed_steady_residual_scales"]
    started = time.perf_counter()
    full = dd173._solve_step(
        "dd175_full_0p25s", FULL_DT_SEC, contract, spec, reference, state,
        provider, audit, inventory, algebraic, scales, settings,
    )
    half1 = dd173._solve_step(
        "dd175_half1_0p125s", HALF_DT_SEC, contract, spec, reference, state,
        provider, audit, inventory, algebraic, scales, settings,
    )
    if not isinstance(half1.evaluation, BackwardEulerEvaluation):
        raise TypeError("DD-175 first half-step evaluation is invalid")
    half2 = dd173._solve_step(
        "dd175_half2_0p125s", HALF_DT_SEC, contract, spec, reference,
        half1.evaluation.dynamic_evaluation.physical_state, provider, audit,
        half1.evaluation.endpoint_inventory_lbmol,
        half1.evaluation.algebraic_coordinates, scales, settings,
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd173.dd172._provider_summary(audit)

    outcomes = {"full": full, "half1": half1, "half2": half2}
    step_seconds = {
        "full": FULL_DT_SEC,
        "half1": HALF_DT_SEC,
        "half2": HALF_DT_SEC,
    }
    reports = {
        name: dd173.dd172._step_report(
            outcome, spec, inventory, algebraic, step_seconds[name]
        )
        for name, outcome in outcomes.items()
    }
    evaluations = {name: outcome.evaluation for name, outcome in outcomes.items()}
    if not all(
        isinstance(value, BackwardEulerEvaluation)
        for value in evaluations.values()
    ):
        raise TypeError("DD-175 endpoint evaluation is invalid")
    full_eval = evaluations["full"]
    half1_eval = evaluations["half1"]
    half2_eval = evaluations["half2"]
    assert isinstance(full_eval, BackwardEulerEvaluation)
    assert isinstance(half1_eval, BackwardEulerEvaluation)
    assert isinstance(half2_eval, BackwardEulerEvaluation)
    response = {
        "full": dd173._path_response(
            inventory, [full_eval], [FULL_DT_SEC], spec
        ),
        "refined": dd173._path_response(
            inventory,
            [half1_eval, half2_eval],
            [HALF_DT_SEC, HALF_DT_SEC],
            spec,
        ),
    }
    endpoint_difference = (
        full_eval.endpoint_inventory_lbmol - half2_eval.endpoint_inventory_lbmol
    )
    refinement = {
        "relative_inventory_difference": float(
            np.max(np.abs(endpoint_difference) / inventory)
        ),
        "rate_coordinate_difference": float(
            np.max(np.abs(full_eval.rate_coordinates - half2_eval.rate_coordinates))
        ),
        "algebraic_coordinate_difference": float(
            np.max(
                np.abs(
                    full_eval.algebraic_coordinates
                    - half2_eval.algebraic_coordinates
                )
            )
        ),
        "total_inventory_difference_lbmol": abs(
            response["full"]["total_inventory_change_lbmol"]
            - response["refined"]["total_inventory_change_lbmol"]
        ),
    }
    physical_refinement = dd174._physical_metrics(
        inventory,
        full_eval.endpoint_inventory_lbmol,
        half2_eval.endpoint_inventory_lbmol,
    )
    limits = payload["limits"]
    physical_limits = payload["physical_refinement_limits"]
    step_gates = {
        name: {
            "success": report["success"]
            and report["nfev"] <= payload["solver"]["max_nfev"],
            "residual": report["residual_inf_norm"] < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == payload["required_rank"],
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
        for name, report in reports.items()
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
        }
        for name, values in response.items()
    }
    refinement_gates = {
        "inventory": refinement["relative_inventory_difference"]
        < limits["refinement_inventory"],
        "rate": refinement["rate_coordinate_difference"]
        < limits["refinement_rate_coordinate"],
        "algebraic": refinement["algebraic_coordinate_difference"]
        < limits["refinement_algebraic"],
        "total_inventory": refinement["total_inventory_difference_lbmol"]
        < limits["refinement_total_inventory_lbmol"],
    }
    physical_refinement_gates = {
        "absolute_component": physical_refinement[
            "maximum_absolute_component_difference_lbmol"
        ] < physical_limits["maximum_absolute_component_difference_lbmol"],
        "state_relative_with_floor": physical_refinement[
            "maximum_state_relative_difference_with_1_lbmol_floor"
        ] < physical_limits[
            "maximum_state_relative_difference_with_1_lbmol_floor"
        ],
        "volume_holdup_relative": physical_refinement[
            "maximum_volume_holdup_relative_component_difference"
        ] < physical_limits[
            "maximum_volume_holdup_relative_component_difference"
        ],
        "component_l1": physical_refinement["component_difference_l1_lbmol"]
        < physical_limits["component_difference_l1_lbmol"],
        "signed_total": physical_refinement[
            "absolute_signed_total_inventory_difference_lbmol"
        ] < physical_limits["absolute_signed_total_inventory_difference_lbmol"],
    }
    campaign_gates = {
        "steps": all(all(values.values()) for values in step_gates.values()),
        "response": all(all(values.values()) for values in response_gates.values()),
        "refinement": all(refinement_gates.values()),
        "physical_refinement": all(physical_refinement_gates.values()),
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"]
        < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "seven_volume_smaller_moving_step_passed"
            if passed
            else "seven_volume_smaller_moving_step_failed"
        ),
        "decision": (
            "authorize_one_frozen_short_open_loop_trajectory_contract"
            if passed
            else "stop_before_trajectory"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "disturbance": payload["disturbance"],
        "paths": payload["paths"],
        "wall_clock_sec": float(elapsed),
        "steps": reports,
        "response": response,
        "refinement": refinement,
        "physical_refinement": physical_refinement,
        "worst_condition": max(
            report["jacobian_condition"] for report in reports.values()
        ),
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "step_gates": step_gates,
        "response_gates": response_gates,
        "refinement_gates": refinement_gates,
        "physical_refinement_gates": physical_refinement_gates,
        "campaign_gates": campaign_gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_attempted": False,
        "trajectory_attempted": False,
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
    parser.add_argument("--dd173-contract", type=Path, default=DD173_CONTRACT)
    parser.add_argument("--dd174-result", type=Path, default=DD174_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd173_contract, args.dd174_result, args.contract)
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
