#!/usr/bin/env python
"""Prepare or execute the frozen DD-235 full-column small moving step."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
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

import audit_core_v3_aligned_pr_density_parity as dd229  # noqa: E402
import audit_core_v3_full_c3c4_dynamic_handoff as dd232  # noqa: E402
import audit_core_v3_full_c3c4_zero_motion as dd233  # noqa: E402
import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402
import run_core_v3_full_c3c4_stationary_hold_step as dd234  # noqa: E402
import run_core_v3_full_c3c4_steady_root as dd223  # noqa: E402

from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (  # noqa: E402
    InventoryRefinementLimits,
    assess_inventory_refinement,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    solve_terminal_inventory_control_backward_euler_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
)


SCHEMA = "dd235-core-v3-full-c3c4-small-moving-step-contract-v1"
RESULT_SCHEMA = "dd235-core-v3-full-c3c4-small-moving-step-result-v1"
DD232 = dd233.DD232
DD234_CONTRACT = dd234.CONTRACT
DD234_RESULT = Path("logs/dd234_core_v3_full_c3c4_stationary_hold_20260815.json")
CONTRACT = Path("logs/dd235_core_v3_full_c3c4_small_moving_step_contract_20260815.json")
RESULT = Path("logs/dd235_core_v3_full_c3c4_small_moving_step_20260815")
CONTRACT_DOC = Path("docs/dd_235_core_v3_full_c3c4_small_moving_step_contract_20260815.md")
RESULT_DOC = Path("docs/dd_235_core_v3_full_c3c4_small_moving_step_20260815.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/physical_refinement_policy_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "tools/audit_core_v3_aligned_pr_density_parity.py",
    "tools/run_core_v3_full_c3c4_stationary_hold_step.py",
    "tools/run_core_v3_full_c3c4_small_moving_step.py",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape(-1)]


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    source_contract = _load(DD234_CONTRACT)
    source_result = _load(DD234_RESULT)
    if not source_result.get("pass_gate"):
        raise RuntimeError("DD-235 requires the accepted DD-234 stationary step")
    model_contract = _load(Path(source_contract["model_contract"]))
    baseline_feed = np.asarray(
        model_contract["source_mapping"]["feed_component_lbmolph"], dtype=float
    )
    multiplier = 1.001
    increment = baseline_feed * (multiplier - 1.0)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd234._git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(path)
            for path in (DD234_CONTRACT, DD234_RESULT, Path(source_contract["model_contract"]))
        },
        "model_contract": source_contract["model_contract"],
        "workbook": source_contract["workbook"],
        "workbook_sha256": source_contract["workbook_sha256"],
        "provider_routing": source_contract["provider_routing"],
        "accepted_root_state": source_contract["accepted_root_state"],
        "prior_inventory_lbmol": source_result["steps"]["full"]["inventory_lbmol"],
        "initial_solve_coordinates": source_result["steps"]["full"]["solve_coordinates"],
        "prior_controller_memory": source_result["steps"]["full"]["controller_memory"],
        "level_setpoints": source_contract["level_setpoints"],
        "product_reference_lbmolph": source_contract["product_reference_lbmolph"],
        "fixed_steady_residual_scales": source_contract["fixed_steady_residual_scales"],
        "solver": source_contract["solver"],
        "steps": {
            "full_seconds": 0.25,
            "half_seconds": 0.125,
            "sequence": ["full", "half_1", "half_2"],
        },
        "disturbance": {
            "kind": "controlled_feed_rate_step",
            "feed_multiplier": multiplier,
            "feed_enthalpy_multiplier": multiplier,
            "feed_composition_changed": False,
            "feed_specific_enthalpy_changed": False,
            "component_rate_increment_lbmolph": _vector(increment),
            "total_rate_increment_lbmolph": float(np.sum(increment)),
        },
        "required_rank": 162,
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "kinematic_identity": 1.0e-10,
            "controller_equation_closure": 1.0e-8,
            "minimum_total_inventory_response_lbmol": 1.0e-4,
            "maximum_total_inventory_response_lbmol": 1.0e-2,
            "global_component_inventory_identity_lbmol": 1.0e-6,
            "rate_coordinate_refinement": 1.0e-5,
            "algebraic_coordinate_refinement": 1.0e-5,
            "controller_memory_refinement": 1.0e-8,
            "product_relative_refinement": 1.0e-7,
            "level_fraction_refinement": 1.0e-8,
            "provider_calls": 100000,
            "wall_clock_sec": 300.0,
        },
        "physical_refinement_limits": {
            "maximum_absolute_component_difference_lbmol": 1.0e-4,
            "maximum_state_relative_difference_with_1_lbmol_floor": 1.0e-5,
            "maximum_volume_holdup_relative_component_difference": 1.0e-6,
            "component_difference_l1_lbmol": 2.0e-4,
            "absolute_signed_total_inventory_difference_lbmol": 1.0e-9,
        },
        "implementation_sha256": {path: _sha(Path(path)) for path in IMPLEMENTATION},
        "hard_stops": [
            "any root fails or exceeds residual, rank, condition, or physical gates",
            "the positive feed disturbance lacks a bounded detectable response",
            "global component response is not explained by external flow",
            "full and refined endpoints disagree outside the frozen physical policy",
            "provider, call, or wall gates fail",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "disturbance_attempted": False,
        "controller_tuning_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-235 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    disturbance = payload["disturbance"]
    return "\n".join(
        (
            "# DD-235 Full-C3/C4 Small Moving-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Feed and feed-enthalpy multiplier: `{disturbance['feed_multiplier']}`",
            "- Feed composition and specific enthalpy: unchanged",
            "- Comparison: one `0.25 s` step versus two `0.125 s` steps",
            "- Initial state: accepted DD-234 stationary startup endpoint",
            "- Thermo, controllers, products, scales, and solver: unchanged",
            "- Tuning, retry, alternate disturbance, or trajectory: `False`",
            "",
            "Commit this immutable contract before its one live execution.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-235 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-235 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-235 implementation changed: {path}")
    if hashlib.sha256(Path(payload["workbook"]).read_bytes()).hexdigest() != payload["workbook_sha256"]:
        raise RuntimeError("DD-235 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-235 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    dd234._git("ls-files", "--error-unmatch", relative)


def _external_component_rate(spec: Any, evaluation: Any) -> np.ndarray:
    state = evaluation.control_evaluation.base.physical_state
    return (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - float(evaluation.distillate_lbmolph) * state.liquid_mole_fraction[0]
        - float(evaluation.bottoms_lbmolph) * state.liquid_mole_fraction[-1]
    )


def _path_response(
    initial_inventory: np.ndarray,
    evaluations: Sequence[Any],
    seconds: Sequence[float],
    spec: Any,
) -> dict[str, Any]:
    actual = np.sum(evaluations[-1].endpoint_inventory_lbmol - initial_inventory, axis=0)
    expected = sum(
        _external_component_rate(spec, endpoint) * (step / 3600.0)
        for endpoint, step in zip(evaluations, seconds, strict=True)
    )
    return {
        "component_inventory_change_lbmol": _vector(actual),
        "expected_component_inventory_change_lbmol": _vector(expected),
        "component_inventory_identity_max_abs_lbmol": float(
            np.max(np.abs(actual - expected))
        ),
        "total_inventory_change_lbmol": float(np.sum(actual)),
        "expected_total_inventory_change_lbmol": float(np.sum(expected)),
    }


def _controller_closure(outcome: Any) -> float:
    return float(np.max(np.abs(outcome.evaluation.raw[-4:])))


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    model_contract = _load(Path(payload["model_contract"]))
    _workbook, dwsim, base_spec, reference = dd223._source_model(model_contract)
    multiplier = float(payload["disturbance"]["feed_multiplier"])
    spec = replace(
        base_spec,
        feed_component_lbmolph=np.asarray(base_spec.feed_component_lbmolph) * multiplier,
        feed_enthalpy_BTUph=float(base_spec.feed_enthalpy_BTUph) * multiplier,
    )
    aligned = dd092._independent_provider(model_contract)
    provider = dd229.DensityRoutedProvider(dwsim, aligned)
    controlled = dd233._controlled_contract(spec, _load(DD232))
    state = dd232._state(payload["accepted_root_state"])
    inventory = np.asarray(payload["prior_inventory_lbmol"], dtype=float)
    initial = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["prior_controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    products = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    coordinate_scale = np.asarray(payload["solver"]["x_scale"], dtype=float)
    settings = dd234._settings(payload)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider.set_exact_state_memoization(True, clear=True)

    def run_step(
        *,
        name: str,
        template: Any,
        prior_inventory: np.ndarray,
        prior_memory: np.ndarray,
        coordinates: np.ndarray,
        seconds: float,
    ):
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
            product_reference_lbmolph=products,
            step_seconds=seconds,
            settings=settings,
            name=name,
        )

    started = time.perf_counter()
    full = run_step(
        name="dd235_full_0p25s",
        template=state,
        prior_inventory=inventory,
        prior_memory=memory,
        coordinates=initial,
        seconds=payload["steps"]["full_seconds"],
    )
    half_1 = run_step(
        name="dd235_half1_0p125s",
        template=state,
        prior_inventory=inventory,
        prior_memory=memory,
        coordinates=initial,
        seconds=payload["steps"]["half_seconds"],
    )
    half_2 = run_step(
        name="dd235_half2_0p125s",
        template=half_1.evaluation.control_evaluation.base.physical_state,
        prior_inventory=half_1.evaluation.endpoint_inventory_lbmol,
        prior_memory=half_1.evaluation.endpoint_controller_memory,
        coordinates=half_1.final_coordinates,
        seconds=payload["steps"]["half_seconds"],
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd234._provider_summary(audit)
    outcomes = {"full": full, "half_1": half_1, "half_2": half_2}
    seconds = {
        "full": payload["steps"]["full_seconds"],
        "half_1": payload["steps"]["half_seconds"],
        "half_2": payload["steps"]["half_seconds"],
    }
    reports = {
        name: dd234._step_report(
            outcome,
            original_inventory=inventory,
            original_coordinates=initial,
            original_memory=memory,
            product_reference=products,
            step_seconds=seconds[name],
            coordinate_scale=coordinate_scale,
        )
        for name, outcome in outcomes.items()
    }
    response = {
        "full": _path_response(inventory, [full.evaluation], [seconds["full"]], spec),
        "refined": _path_response(
            inventory,
            [half_1.evaluation, half_2.evaluation],
            [seconds["half_1"], seconds["half_2"]],
            spec,
        ),
    }
    physical_refinement = assess_inventory_refinement(
        inventory,
        full.evaluation.endpoint_inventory_lbmol,
        half_2.evaluation.endpoint_inventory_lbmol,
        InventoryRefinementLimits.from_mapping(payload["physical_refinement_limits"]),
    )
    full_products = np.asarray(
        (full.evaluation.distillate_lbmolph, full.evaluation.bottoms_lbmolph)
    )
    refined_products = np.asarray(
        (half_2.evaluation.distillate_lbmolph, half_2.evaluation.bottoms_lbmolph)
    )
    refinement = {
        "physical_inventory": dict(physical_refinement.metrics),
        "rate_coordinate_difference": float(
            np.max(np.abs(full.evaluation.rate_coordinates - half_2.evaluation.rate_coordinates))
        ),
        "algebraic_coordinate_difference": float(
            np.max(
                np.abs(
                    full.evaluation.algebraic_coordinates
                    - half_2.evaluation.algebraic_coordinates
                )
            )
        ),
        "controller_memory_difference": float(
            np.max(
                np.abs(
                    full.evaluation.endpoint_controller_memory
                    - half_2.evaluation.endpoint_controller_memory
                )
            )
        ),
        "product_relative_difference": float(
            np.max(np.abs(full_products - refined_products) / products)
        ),
        "level_fraction_difference": float(
            np.max(np.abs(full.evaluation.level_fraction - half_2.evaluation.level_fraction))
        ),
    }
    limits = payload["limits"]
    step_gates = {
        name: {
            "success": report["success"] and report["nfev"] <= payload["solver"]["max_nfev"],
            "residual": report["scaled_residual_inf_norm"] < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == payload["required_rank"],
            "condition": report["jacobian_condition"] < limits["condition"],
            "equilibrium": report["maximum_equilibrium_residual"] < limits["equilibrium_residual"],
            "component_conservation": report["component_conservation_relative_error"] < limits["component_conservation"],
            "energy_conservation": report["energy_conservation_relative_error"] < limits["energy_conservation"],
            "component_kinematics": report["component_kinematic_identity"] < limits["kinematic_identity"],
            "energy_kinematics": report["energy_kinematic_identity"] < limits["kinematic_identity"],
            "controller_kinematics": report["controller_kinematic_identity"] < limits["kinematic_identity"],
            "controller_equations": _controller_closure(outcomes[name]) < limits["controller_equation_closure"],
            "physical": report["physical_pass"],
        }
        for name, report in reports.items()
    }
    response_gates = {
        name: {
            "positive": values["total_inventory_change_lbmol"] > 0.0,
            "detectable": values["total_inventory_change_lbmol"] > limits["minimum_total_inventory_response_lbmol"],
            "bounded": values["total_inventory_change_lbmol"] < limits["maximum_total_inventory_response_lbmol"],
            "global_component_identity": values["component_inventory_identity_max_abs_lbmol"] < limits["global_component_inventory_identity_lbmol"],
        }
        for name, values in response.items()
    }
    refinement_gates = {
        **dict(physical_refinement.gates),
        "rate": refinement["rate_coordinate_difference"] < limits["rate_coordinate_refinement"],
        "algebraic": refinement["algebraic_coordinate_difference"] < limits["algebraic_coordinate_refinement"],
        "controller_memory": refinement["controller_memory_difference"] < limits["controller_memory_refinement"],
        "product": refinement["product_relative_difference"] < limits["product_relative_refinement"],
        "level": refinement["level_fraction_difference"] < limits["level_fraction_refinement"],
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
            "full_c3c4_small_moving_step_passed"
            if passed
            else "full_c3c4_small_moving_step_failed"
        ),
        "decision": (
            "authorize_one_separately_frozen_short_full_c3c4_trajectory_contract"
            if passed
            else "stop_full_c3c4_before_trajectory"
        ),
        "contract_commit": dd234._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": float(elapsed),
        "steps": reports,
        "response": response,
        "refinement": refinement,
        "step_gates": step_gates,
        "response_gates": response_gates,
        "refinement_gates": refinement_gates,
        "campaign_gates": campaign_gates,
        "provider": provider_summary,
        "exact_state_memoization": memo,
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


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    response = payload["response"]
    return "\n".join(
        (
            "# DD-235 Full-C3/C4 Small Moving-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residuals: `{steps['full']['scaled_residual_inf_norm']:.6e}`, `{steps['half_1']['scaled_residual_inf_norm']:.6e}`, `{steps['half_2']['scaled_residual_inf_norm']:.6e}`",
            f"- Ranks: `{steps['full']['jacobian_rank']} / {steps['half_1']['jacobian_rank']} / {steps['half_2']['jacobian_rank']}`",
            f"- Worst condition: `{max(item['jacobian_condition'] for item in steps.values()):.6e}`",
            f"- Full/refined total inventory response: `{response['full']['total_inventory_change_lbmol']:.6e}` / `{response['refined']['total_inventory_change_lbmol']:.6e} lbmol`",
            f"- Provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Tuning, retry, or trajectory: `False`",
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
                    "required_rank": report["required_rank"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc)
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
