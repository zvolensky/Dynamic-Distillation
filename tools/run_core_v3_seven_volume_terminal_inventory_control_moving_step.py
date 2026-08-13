#!/usr/bin/env python
"""Prepare or execute DD-187's controlled moving implicit-step proof."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
import run_core_v3_seven_volume_terminal_inventory_control_stationary_step as dd186  # noqa: E402
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
    TerminalInventoryControlStepOutcome,
    solve_terminal_inventory_control_backward_euler_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
)


SCHEMA = "dd187-core-v3-seven-volume-terminal-control-moving-step-contract-v1"
RESULT_SCHEMA = "dd187-core-v3-seven-volume-terminal-control-moving-step-result-v1"
DD186_CONTRACT = Path(
    "logs/dd186_core_v3_seven_volume_terminal_inventory_control_stationary_step_contract_20260813.json"
)
DD186_RESULT = Path(
    "logs/dd186_core_v3_seven_volume_terminal_inventory_control_stationary_step_20260813.json"
)
DD185_CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
CONTRACT = Path(
    "logs/dd187_core_v3_seven_volume_terminal_inventory_control_moving_step_contract_20260813.json"
)
RESULT = Path(
    "logs/dd187_core_v3_seven_volume_terminal_inventory_control_moving_step_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_187_core_v3_seven_volume_terminal_inventory_control_moving_step_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_187_core_v3_seven_volume_terminal_inventory_control_moving_step_20260813.md"
)
FEED_MULTIPLIER = 1.001
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/physical_refinement_policy_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_contract_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "tests/test_core_v3_terminal_inventory_control_numerical_v1.py",
    "tests/test_core_v3_terminal_inventory_control_implicit_step_v1.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_moving_step.py",
)


def _disturbed_inputs(
    source_mapping: Mapping[str, Any],
    operating_spec: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = deepcopy(dict(source_mapping))
    operating = deepcopy(dict(operating_spec))
    source["feed_component_lbmolph"] = [
        FEED_MULTIPLIER * float(value)
        for value in source["feed_component_lbmolph"]
    ]
    operating["feed_enthalpy_BTUph"] = (
        FEED_MULTIPLIER * float(operating["feed_enthalpy_BTUph"])
    )
    return source, operating


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-187 Seven-Volume Controlled Moving-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            f"- Feed and feed-enthalpy multiplier: `{FEED_MULTIPLIER}`",
            "- Feed composition and specific enthalpy: unchanged",
            "- Comparison: one `0.25 s` step versus two `0.125 s` steps",
            "- Terminal setpoints and PI tuning: unchanged from DD-186",
            "- Product references: fixed DD-169 rates for every step",
            "- Inventory refinement: frozen physical-scale Core V3 policy",
            "- Property evaluation during preparation: `False`",
            "- Timestep execution during preparation: `False`",
            "",
            "Commit before the one live execution. No tuning, retry, alternate "
            "disturbance, or trajectory is authorized.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    response = payload["response"]
    return "\n".join(
        (
            "# DD-187 Seven-Volume Controlled Moving-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residuals: `{steps['full']['residual_inf_norm']:.6e}`, "
            f"`{steps['half1']['residual_inf_norm']:.6e}`, "
            f"`{steps['half2']['residual_inf_norm']:.6e}`",
            f"- Ranks: `{steps['full']['jacobian_rank']} / "
            f"{steps['half1']['jacobian_rank']} / "
            f"{steps['half2']['jacobian_rank']}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Full/refined total inventory response: "
            f"`{response['full']['total_inventory_change_lbmol']:.6e}` / "
            f"`{response['refined']['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Maximum product relative movement: "
            f"`{payload['maximum_product_relative_movement']:.6e}`",
            f"- Logical provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Controller tuning/retry/trajectory attempted: `False / False / False`",
            "",
        )
    )


def prepare(
    source_contract_path: Path,
    source_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = dd186._load(source_contract_path)
    result = dd186._load(source_result_path)
    if not result["pass_gate"] or result["decision"] != (
        "authorize_one_frozen_small_controlled_moving_step_contract"
    ):
        raise RuntimeError("DD-187 requires the accepted DD-186 result")
    disturbed_source, disturbed_operating = _disturbed_inputs(
        source["source_mapping"], source["operating_spec"]
    )
    baseline_feed = np.asarray(source["source_mapping"]["feed_component_lbmolph"])
    disturbed_feed = np.asarray(disturbed_source["feed_component_lbmolph"])
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd186._git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): dd186._sha(ROOT / path)
            for path in (source_contract_path, source_result_path, DD185_CONTRACT)
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": disturbed_source,
        "operating_spec": disturbed_operating,
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
        "disturbance": {
            "kind": "controlled_feed_rate_step",
            "feed_multiplier": FEED_MULTIPLIER,
            "feed_enthalpy_multiplier": FEED_MULTIPLIER,
            "feed_composition_changed": False,
            "feed_specific_enthalpy_changed": False,
            "component_rate_increment_lbmolph": dd186._vector(
                disturbed_feed - baseline_feed
            ),
            "total_rate_increment_lbmolph": float(
                np.sum(disturbed_feed - baseline_feed)
            ),
        },
        "solver": source["solver"],
        "paths": {"full": [0.25], "refined": [0.125, 0.125]},
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "kinematic_identity": 1.0e-12,
            "controller_kinematic_identity": 1.0e-12,
            "controller_equation_closure": 1.0e-8,
            "minimum_total_inventory_response_lbmol": 1.0e-4,
            "maximum_total_inventory_response_lbmol": 1.0e-2,
            "global_component_inventory_identity_lbmol": 1.0e-6,
            "rate_coordinate_refinement": 1.0e-5,
            "algebraic_coordinate_refinement": 1.0e-5,
            "controller_memory_refinement": 1.0e-8,
            "product_relative_refinement": 1.0e-7,
            "level_fraction_refinement": 1.0e-8,
            "provider_calls": 40000,
            "wall_clock_sec": 120.0,
        },
        "physical_refinement_limits": {
            "maximum_absolute_component_difference_lbmol": 1.0e-4,
            "maximum_state_relative_difference_with_1_lbmol_floor": 1.0e-5,
            "maximum_volume_holdup_relative_component_difference": 1.0e-6,
            "component_difference_l1_lbmol": 2.0e-4,
            "absolute_signed_total_inventory_difference_lbmol": 1.0e-9,
        },
        "required_rank": 58,
        "exact_state_memoization": source["exact_state_memoization"],
        "implementation_sha256": {
            path: dd186._sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "any of the three controlled implicit roots fails",
            "any rank, condition, closure, physical, or conservation gate fails",
            "the positive feed disturbance lacks a bounded detectable response",
            "full and refined endpoints disagree beyond a frozen physical limit",
            "fixed product references or controller identities are violated",
            "provider ownership, call, or wall gate fails",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "disturbance_attempted": False,
        "controller_tuning_attempted": False,
        "retry_authorized": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = dd186._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-187 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd186._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-187 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-187 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-187 implementation changed: {path}")
    if dd186._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-187 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-187 result exists; rerun is prohibited")
    if not dd186._git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-187 contract is not committed")


def _external_component_rate(spec: Any, evaluation: Any) -> np.ndarray:
    state = evaluation.control_evaluation.base.physical_state
    return (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )


def _path_response(
    initial_inventory: np.ndarray,
    endpoints: Sequence[TerminalInventoryControlBackwardEulerEvaluation],
    seconds: Sequence[float],
    spec: Any,
) -> dict[str, Any]:
    final = endpoints[-1].endpoint_inventory_lbmol
    actual = np.sum(final - initial_inventory, axis=0)
    expected = sum(
        _external_component_rate(spec, endpoint) * (step / 3600.0)
        for endpoint, step in zip(endpoints, seconds, strict=True)
    )
    return {
        "component_inventory_change_lbmol": dd186._vector(actual),
        "expected_component_inventory_change_lbmol": dd186._vector(expected),
        "component_inventory_identity_max_abs_lbmol": float(
            np.max(np.abs(actual - expected))
        ),
        "total_inventory_change_lbmol": float(np.sum(actual)),
        "expected_total_inventory_change_lbmol": float(np.sum(expected)),
    }


def _controller_closure(outcome: TerminalInventoryControlStepOutcome) -> float:
    return float(np.max(np.abs(outcome.evaluation.raw[-4:])))


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = dd186._load(contract_path)
    _verify(payload, contract_path, result_path)
    dd185_contract = dd186._load(DD185_CONTRACT)
    spec = dd186.dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd186.dd171.dd168._reference(payload["reference"])
    state = dd186.dd171._state(payload["accepted_root_state"])
    controlled = dd185._controlled_contract(spec, dd185_contract)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-187 controlled structural contract changed")
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    initial = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["initial_controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    setpoint_values = np.asarray(
        (setpoints.top_fraction, setpoints.bottom_fraction), dtype=float
    )
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    provider = dd186.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd186._settings(payload)

    def run_step(
        *,
        name: str,
        template: Any,
        prior_inventory: np.ndarray,
        prior_memory: np.ndarray,
        coordinates: np.ndarray,
        seconds: float,
    ) -> TerminalInventoryControlStepOutcome:
        return solve_terminal_inventory_control_backward_euler_step(
            controlled,
            spec,
            reference,
            template,
            provider,
            audit,
            previous_inventory_lbmol=prior_inventory,
            previous_controller_memory=prior_memory,
            level_setpoints=setpoints,
            initial_solve_coordinates=coordinates,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=product_reference,
            step_seconds=seconds,
            settings=settings,
            name=name,
        )

    started = time.perf_counter()
    full = run_step(
        name="dd187_full_0p25s",
        template=state,
        prior_inventory=inventory,
        prior_memory=memory,
        coordinates=initial,
        seconds=0.25,
    )
    half1 = run_step(
        name="dd187_half1_0p125s",
        template=state,
        prior_inventory=inventory,
        prior_memory=memory,
        coordinates=initial,
        seconds=0.125,
    )
    half2 = run_step(
        name="dd187_half2_0p125s",
        template=half1.evaluation.control_evaluation.base.physical_state,
        prior_inventory=half1.evaluation.endpoint_inventory_lbmol,
        prior_memory=half1.evaluation.endpoint_controller_memory,
        coordinates=half1.final_coordinates,
        seconds=0.125,
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd186._provider_summary(audit)
    outcomes = {"full": full, "half1": half1, "half2": half2}
    step_seconds = {"full": 0.25, "half1": 0.125, "half2": 0.125}
    reports = {
        name: dd186._step_report(
            outcome,
            spec,
            inventory,
            initial,
            memory,
            setpoint_values,
            product_reference,
            step_seconds[name],
        )
        for name, outcome in outcomes.items()
    }
    response = {
        "full": _path_response(inventory, [full.evaluation], [0.25], spec),
        "refined": _path_response(
            inventory, [half1.evaluation, half2.evaluation], [0.125, 0.125], spec
        ),
    }
    physical_refinement = assess_inventory_refinement(
        inventory,
        full.evaluation.endpoint_inventory_lbmol,
        half2.evaluation.endpoint_inventory_lbmol,
        InventoryRefinementLimits.from_mapping(payload["physical_refinement_limits"]),
    )
    full_products = np.asarray(
        (full.evaluation.distillate_lbmolph, full.evaluation.bottoms_lbmolph)
    )
    refined_products = np.asarray(
        (half2.evaluation.distillate_lbmolph, half2.evaluation.bottoms_lbmolph)
    )
    refinement = {
        "physical_inventory": dict(physical_refinement.metrics),
        "legacy_unfloored_relative_inventory_diagnostic": (
            physical_refinement.legacy_unfloored_relative_diagnostic
        ),
        "rate_coordinate_difference": float(
            np.max(
                np.abs(
                    full.evaluation.rate_coordinates
                    - half2.evaluation.rate_coordinates
                )
            )
        ),
        "algebraic_coordinate_difference": float(
            np.max(
                np.abs(
                    full.evaluation.algebraic_coordinates
                    - half2.evaluation.algebraic_coordinates
                )
            )
        ),
        "controller_memory_difference": float(
            np.max(
                np.abs(
                    full.evaluation.endpoint_controller_memory
                    - half2.evaluation.endpoint_controller_memory
                )
            )
        ),
        "product_relative_difference": float(
            np.max(np.abs(full_products - refined_products) / product_reference)
        ),
        "level_fraction_difference": float(
            np.max(
                np.abs(
                    full.evaluation.level_fraction - half2.evaluation.level_fraction
                )
            )
        ),
    }
    limits = payload["limits"]
    step_gates = {
        name: {
            "success": report["success"]
            and report["nfev"] <= payload["solver"]["max_nfev"],
            "residual": report["residual_inf_norm"] < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == payload["required_rank"],
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
            "controller_equations": _controller_closure(outcomes[name])
            < limits["controller_equation_closure"],
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
        **dict(physical_refinement.gates),
        "rate": refinement["rate_coordinate_difference"]
        < limits["rate_coordinate_refinement"],
        "algebraic": refinement["algebraic_coordinate_difference"]
        < limits["algebraic_coordinate_refinement"],
        "controller_memory": refinement["controller_memory_difference"]
        < limits["controller_memory_refinement"],
        "product": refinement["product_relative_difference"]
        < limits["product_relative_refinement"],
        "level": refinement["level_fraction_difference"]
        < limits["level_fraction_refinement"],
    }
    campaign_gates = {
        "steps": all(all(values.values()) for values in step_gates.values()),
        "response": all(all(values.values()) for values in response_gates.values()),
        "refinement": all(refinement_gates.values()),
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "terminal_inventory_control_moving_step_passed"
            if passed
            else "terminal_inventory_control_moving_step_failed"
        ),
        "decision": (
            "authorize_one_frozen_short_controlled_trajectory_contract"
            if passed
            else "stop_terminal_control_before_trajectory"
        ),
        "contract_commit": dd186._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": float(elapsed),
        "steps": reports,
        "response": response,
        "refinement": refinement,
        "worst_condition": max(
            report["jacobian_condition"] for report in reports.values()
        ),
        "maximum_product_relative_movement": max(
            report["product_relative_movement"] for report in reports.values()
        ),
        "maximum_controller_memory_movement": max(
            report["controller_memory_movement"] for report in reports.values()
        ),
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "step_gates": step_gates,
        "response_gates": response_gates,
        "refinement_gates": refinement_gates,
        "campaign_gates": campaign_gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "disturbance_attempted": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
        "trajectory_attempted": False,
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
    parser.add_argument("--source-contract", type=Path, default=DD186_CONTRACT)
    parser.add_argument("--source-result", type=Path, default=DD186_RESULT)
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
                    "required_rank": output["required_rank"],
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
