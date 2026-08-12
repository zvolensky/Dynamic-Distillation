#!/usr/bin/env python
"""Prepare or execute DD-173's seven-volume open-loop moving step."""

from __future__ import annotations

import argparse
from copy import deepcopy
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

import run_core_v3_seven_volume_stationary_step as dd172  # noqa: E402

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
    ImplicitSolveOutcome,
    solve_backward_euler_step,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)


SCHEMA = "dd173-core-v3-seven-volume-moving-step-contract-v1"
RESULT_SCHEMA = "dd173-core-v3-seven-volume-moving-step-result-v1"
DD172_CONTRACT = Path(
    "logs/dd172_core_v3_seven_volume_stationary_step_contract_20260812.json"
)
DD172_RESULT = Path(
    "logs/dd172_core_v3_seven_volume_stationary_step_20260812.json"
)
CONTRACT = Path("logs/dd173_core_v3_seven_volume_moving_step_contract_20260812.json")
RESULT = Path("logs/dd173_core_v3_seven_volume_moving_step_20260812")
FEED_MULTIPLIER = 1.001
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tools/run_core_v3_seven_volume_stationary_step.py",
    "tools/run_core_v3_seven_volume_moving_step.py",
    "tests/test_core_v3_seven_volume_moving_step_v1.py",
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


def _disturbed_inputs(
    source_mapping: Mapping[str, Any],
    operating_spec: Mapping[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not np.isfinite(multiplier) or multiplier <= 1.0:
        raise ValueError("moving-step feed multiplier must exceed one")
    source = deepcopy(dict(source_mapping))
    operating = deepcopy(dict(operating_spec))
    source["feed_component_lbmolph"] = [
        float(multiplier) * float(value)
        for value in source["feed_component_lbmolph"]
    ]
    operating["feed_enthalpy_BTUph"] = (
        float(multiplier) * float(operating["feed_enthalpy_BTUph"])
    )
    return source, operating


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    disturbance = payload["disturbance"]
    return "\n".join(
        (
            "# DD-173 Seven-Volume Moving-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            f"- Feed-rate multiplier: `{disturbance['feed_multiplier']}`",
            f"- Feed-enthalpy multiplier: "
            f"`{disturbance['feed_enthalpy_multiplier']}`",
            "- Feed composition and specific enthalpy: unchanged",
            "- Comparison: one `1.0 s` step versus two `0.5 s` steps",
            "- Solver/Jacobian: unchanged from DD-172",
            "- Live property evaluation during preparation: `False`",
            "",
            "Commit before the one live execution. No controller, retry, "
            "alternate disturbance, or multi-step trajectory is authorized.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    response = payload["response"]
    return "\n".join(
        (
            "# DD-173 Seven-Volume Moving-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residuals: `{steps['full']['residual_inf_norm']:.6e}`, "
            f"`{steps['half1']['residual_inf_norm']:.6e}`, "
            f"`{steps['half2']['residual_inf_norm']:.6e}`",
            f"- Full-step total inventory change: "
            f"`{response['full']['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Refined total inventory change: "
            f"`{response['refined']['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Full/refined inventory difference: "
            f"`{payload['refinement']['relative_inventory_difference']:.6e}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Logical provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Controller or trajectory attempted: `False / False`",
            "",
        )
    )


def prepare(
    dd172_contract_path: Path,
    dd172_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd172_contract_path)
    result = _load(dd172_result_path)
    if not result["pass_gate"] or result["decision"] != (
        "authorize_one_frozen_moving_step_contract"
    ):
        raise RuntimeError("DD-173 requires the accepted DD-172 result")
    disturbed_source, disturbed_operating = _disturbed_inputs(
        source["source_mapping"],
        source["operating_spec"],
        FEED_MULTIPLIER,
    )
    baseline_feed = np.asarray(
        source["source_mapping"]["feed_component_lbmolph"], dtype=float
    )
    disturbed_feed = np.asarray(
        disturbed_source["feed_component_lbmolph"], dtype=float
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd172_contract_path": str(dd172_contract_path).replace("\\", "/"),
        "dd172_contract_sha256": _sha(ROOT / dd172_contract_path),
        "dd172_result_path": str(dd172_result_path).replace("\\", "/"),
        "dd172_result_sha256": _sha(ROOT / dd172_result_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "baseline_source_mapping": source["source_mapping"],
        "baseline_operating_spec": source["operating_spec"],
        "disturbed_source_mapping": disturbed_source,
        "disturbed_operating_spec": disturbed_operating,
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source[
            "accepted_root_inventory_lbmol"
        ],
        "accepted_root_algebraic_coordinates": source[
            "accepted_root_algebraic_coordinates"
        ],
        "fixed_steady_residual_scales": source[
            "fixed_steady_residual_scales"
        ],
        "disturbance": {
            "kind": "open_loop_feed_rate_step",
            "feed_multiplier": FEED_MULTIPLIER,
            "feed_enthalpy_multiplier": FEED_MULTIPLIER,
            "feed_composition_changed": False,
            "feed_specific_enthalpy_changed": False,
            "component_rate_increment_lbmolph": (
                disturbed_feed - baseline_feed
            ).tolist(),
            "total_rate_increment_lbmolph": float(
                np.sum(disturbed_feed - baseline_feed)
            ),
        },
        "solver": source["solver"],
        "paths": {"full": [1.0], "refined": [0.5, 0.5]},
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "kinematic_identity": 1.0e-12,
            "minimum_total_inventory_response_lbmol": 1.0e-4,
            "maximum_total_inventory_response_lbmol": 1.0e-2,
            "global_component_inventory_identity_lbmol": 1.0e-6,
            "refinement_inventory": 1.0e-7,
            "refinement_rate_coordinate": 1.0e-5,
            "refinement_algebraic": 1.0e-5,
            "refinement_total_inventory_lbmol": 1.0e-6,
            "provider_calls": 30000,
            "wall_clock_sec": 120.0,
        },
        "required_rank": 54,
        "exact_state_memoization": source["exact_state_memoization"],
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "any root, rank, condition, physical, or conservation gate fails",
            "the feed response is absent, negative, or implausibly large",
            "global component accumulation does not match external flow",
            "full and refined endpoints disagree beyond a frozen limit",
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
        raise RuntimeError("DD-173 contract already exists")
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
        raise RuntimeError("DD-173 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-173 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-173 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-173 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-173 contract is not committed")


def _solve_step(
    name: str,
    seconds: float,
    contract: Any,
    spec: Any,
    reference: Any,
    template: Any,
    provider: Any,
    audit: ProviderCallAudit,
    inventory: np.ndarray,
    algebraic: np.ndarray,
    scales: Any,
    settings: Any,
) -> ImplicitSolveOutcome:
    return solve_backward_euler_step(
        contract,
        spec,
        reference,
        template,
        provider,
        audit,
        previous_inventory_lbmol=inventory,
        initial_algebraic_coordinates=algebraic,
        fixed_steady_scales=scales,
        step_seconds=seconds,
        settings=settings,
        name=name,
    )


def _external_component_rate(spec: Any, evaluation: BackwardEulerEvaluation):
    state = evaluation.dynamic_evaluation.physical_state
    return (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )


def _path_response(
    initial_inventory: np.ndarray,
    endpoints: list[BackwardEulerEvaluation],
    seconds: list[float],
    spec: Any,
) -> dict[str, Any]:
    final = endpoints[-1].endpoint_inventory_lbmol
    actual = np.sum(final - initial_inventory, axis=0)
    expected = sum(
        _external_component_rate(spec, endpoint) * (step / 3600.0)
        for endpoint, step in zip(endpoints, seconds, strict=True)
    )
    return {
        "component_inventory_change_lbmol": dd172._vector(actual),
        "expected_component_inventory_change_lbmol": dd172._vector(expected),
        "component_inventory_identity_max_abs_lbmol": float(
            np.max(np.abs(actual - expected))
        ),
        "total_inventory_change_lbmol": float(np.sum(actual)),
        "expected_total_inventory_change_lbmol": float(np.sum(expected)),
    }


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    spec = dd172.dd171.dd168._spec(
        payload["disturbed_source_mapping"],
        float(payload["disturbed_operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd172.dd171.dd168._reference(payload["reference"])
    state = dd172.dd171._state(payload["accepted_root_state"])
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=payload["dd172_result_path"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-173 structural contract changed")
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-173 inventory mapping changed")
    if not np.allclose(
        algebraic, payload["accepted_root_algebraic_coordinates"]
    ):
        raise RuntimeError("DD-173 algebraic mapping changed")

    provider = dd172.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd172._settings(payload)
    started = time.perf_counter()
    full = _solve_step(
        "dd173_full_1s", 1.0, contract, spec, reference, state, provider,
        audit, inventory, algebraic, payload["fixed_steady_residual_scales"],
        settings,
    )
    half1 = _solve_step(
        "dd173_half1_0p5s", 0.5, contract, spec, reference, state, provider,
        audit, inventory, algebraic, payload["fixed_steady_residual_scales"],
        settings,
    )
    if not isinstance(half1.evaluation, BackwardEulerEvaluation):
        raise TypeError("DD-173 first half-step evaluation is invalid")
    half2 = _solve_step(
        "dd173_half2_0p5s",
        0.5,
        contract,
        spec,
        reference,
        half1.evaluation.dynamic_evaluation.physical_state,
        provider,
        audit,
        half1.evaluation.endpoint_inventory_lbmol,
        half1.evaluation.algebraic_coordinates,
        payload["fixed_steady_residual_scales"],
        settings,
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd172._provider_summary(audit)

    outcomes = {"full": full, "half1": half1, "half2": half2}
    step_seconds = {"full": 1.0, "half1": 0.5, "half2": 0.5}
    reports = {
        name: dd172._step_report(
            outcome, spec, inventory, algebraic, step_seconds[name]
        )
        for name, outcome in outcomes.items()
    }
    evaluations = {
        name: outcome.evaluation for name, outcome in outcomes.items()
    }
    if not all(
        isinstance(value, BackwardEulerEvaluation)
        for value in evaluations.values()
    ):
        raise TypeError("DD-173 endpoint evaluation is invalid")
    full_eval = evaluations["full"]
    half1_eval = evaluations["half1"]
    half2_eval = evaluations["half2"]
    assert isinstance(full_eval, BackwardEulerEvaluation)
    assert isinstance(half1_eval, BackwardEulerEvaluation)
    assert isinstance(half2_eval, BackwardEulerEvaluation)
    response = {
        "full": _path_response(inventory, [full_eval], [1.0], spec),
        "refined": _path_response(
            inventory, [half1_eval, half2_eval], [0.5, 0.5], spec
        ),
    }
    refinement = {
        "relative_inventory_difference": float(
            np.max(
                np.abs(
                    full_eval.endpoint_inventory_lbmol
                    - half2_eval.endpoint_inventory_lbmol
                )
                / inventory
            )
        ),
        "rate_coordinate_difference": float(
            np.max(
                np.abs(full_eval.rate_coordinates - half2_eval.rate_coordinates)
            )
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
    limits = payload["limits"]
    step_gates = {
        name: {
            "success": report["success"]
            and report["nfev"] <= payload["solver"]["max_nfev"],
            "residual": report["residual_inf_norm"]
            < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == payload["required_rank"],
            "condition": report["jacobian_condition"] < limits["condition"],
            "equilibrium": report["maximum_equilibrium_residual"]
            < limits["equilibrium_residual"],
            "component_conservation": report[
                "component_conservation_relative_error"
            ]
            < limits["component_conservation"],
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
            ]
            < limits["global_component_inventory_identity_lbmol"],
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
    campaign_gates = {
        "steps": all(all(values.values()) for values in step_gates.values()),
        "response": all(
            all(values.values()) for values in response_gates.values()
        ),
        "refinement": all(refinement_gates.values()),
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"]
        < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "seven_volume_open_loop_moving_step_passed"
            if passed
            else "seven_volume_open_loop_moving_step_failed"
        ),
        "decision": (
            "authorize_one_frozen_short_open_loop_trajectory_contract"
            if passed
            else "stop_before_trajectory"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "disturbance": payload["disturbance"],
        "wall_clock_sec": float(elapsed),
        "steps": reports,
        "response": response,
        "refinement": refinement,
        "worst_condition": max(
            report["jacobian_condition"] for report in reports.values()
        ),
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "step_gates": step_gates,
        "response_gates": response_gates,
        "refinement_gates": refinement_gates,
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
    parser.add_argument("--dd172-contract", type=Path, default=DD172_CONTRACT)
    parser.add_argument("--dd172-result", type=Path, default=DD172_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd172_contract, args.dd172_result, args.contract)
        print(json.dumps({
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "disturbance": output["disturbance"],
            "campaign_executed": output["campaign_executed"],
        }, indent=2))
    else:
        output = execute(args.contract, args.result)
        print(json.dumps({
            "classification": output["classification"],
            "pass_gate": output["pass_gate"],
            "decision": output["decision"],
        }, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
