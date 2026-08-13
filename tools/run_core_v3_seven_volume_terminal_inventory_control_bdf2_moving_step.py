#!/usr/bin/env python
"""Prepare or execute DD-198's first controlled BDF2 moving step."""

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

import audit_core_v3_seven_volume_terminal_inventory_control_numerical as dd185  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_stationary_step as dd186  # noqa: E402
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    component_rate_scales,
    governing_storage_vector,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_kinematics_v1 import (  # noqa: E402
    build_controlled_bdf2_history,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_residual_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2StepOutcome,
    solve_terminal_inventory_control_bdf2_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    audit_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
)


SCHEMA = "dd198-core-v3-seven-volume-controlled-bdf2-moving-step-contract-v1"
RESULT_SCHEMA = "dd198-core-v3-seven-volume-controlled-bdf2-moving-step-result-v1"
DD185_CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
DD187_CONTRACT = Path(
    "logs/dd187_core_v3_seven_volume_terminal_inventory_control_moving_step_contract_20260813.json"
)
DD187_RESULT = Path(
    "logs/dd187_core_v3_seven_volume_terminal_inventory_control_moving_step_20260813.json"
)
DD197_RESULT = Path(
    "logs/dd197_core_v3_seven_volume_terminal_inventory_control_bdf2_stationary_20260813.json"
)
CONTRACT = Path(
    "logs/dd198_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step_contract_20260813.json"
)
RESULT = Path(
    "logs/dd198_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_198_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_198_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step_20260813.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_kinematics_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_residual_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _rank_condition(matrix: Sequence[Sequence[float]]) -> tuple[int, float]:
    values = np.asarray(matrix, dtype=float)
    singular = np.linalg.svd(values, compute_uv=False)
    tolerance = max(values.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition


def _coordinates(report: Mapping[str, Any], prior_memory: np.ndarray, step: float) -> np.ndarray:
    memory = np.asarray(report["controller_memory"], dtype=float)
    controller_rate = (memory - prior_memory) / float(step)
    return np.concatenate(
        (
            np.asarray(report["rate_coordinates"], dtype=float).reshape((-1,)),
            controller_rate,
            np.asarray(report["algebraic_coordinates"], dtype=float),
            np.asarray(report["product_log_ratio"], dtype=float),
        )
    )


def _external_component_rate(spec: Any, evaluation: Any) -> np.ndarray:
    state = evaluation.control_evaluation.base.physical_state
    return (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-198 Controlled BDF2 Moving-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Disturbance: unchanged DD-187 `+0.1%` feed-rate and feed-enthalpy step",
            "- Startup history: DD-185 stationary state at `t=0`, accepted DD-187 backward-Euler half-step at `t=0.125 s`",
            "- BDF2 endpoint: one fixed `0.125 s` step to `t=0.25 s`",
            "- Reference: accepted DD-187 second backward-Euler half-step",
            "- Accuracy gate: BDF2 inventory must be closer than refined backward Euler to the DD-187 Richardson inventory estimate",
            "- Solver/settings/controllers/product references: unchanged",
            "- Retry, alternate step, tuning, or trajectory: `False`",
            "",
            "Commit this immutable contract before its one live execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-198 Controlled BDF2 Moving-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residual: `{payload['step']['residual_inf_norm']:.6e}`",
            f"- Rank / condition: `{payload['step']['jacobian_rank']} / {payload['step']['jacobian_condition']:.6e}`",
            f"- Function/Jacobian evaluations: `{payload['step']['nfev']} / {payload['step']['njev']}`",
            f"- Maximum BDF2/BE inventory difference: `{payload['comparison']['maximum_absolute_inventory_difference_lbmol']:.6e} lbmol`",
            f"- BDF2 Richardson max error: `{payload['comparison']['bdf2_richardson_max_abs_lbmol']:.6e} lbmol`",
            f"- BE Richardson max error: `{payload['comparison']['backward_euler_richardson_max_abs_lbmol']:.6e} lbmol`",
            f"- Accuracy improvement ratio: `{payload['comparison']['richardson_max_error_ratio']:.6f}`",
            f"- Provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Retry, tuning, alternate step, or trajectory: `False`",
            "",
        )
    )


def prepare(
    dd187_contract_path: Path,
    dd187_result_path: Path,
    dd197_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = _load(dd187_contract_path)
    reference = _load(dd187_result_path)
    dd197 = _load(dd197_result_path)
    if not reference["pass_gate"] or not dd197["pass_gate"]:
        raise RuntimeError("DD-198 prerequisites are not accepted")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                dd187_contract_path,
                dd187_result_path,
                dd197_result_path,
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
        "prior_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "prior_controller_memory": source["initial_controller_memory"],
        "prior_solve_coordinates": source["initial_solve_coordinates"],
        "current_backward_euler_report": reference["steps"]["half1"],
        "endpoint_backward_euler_report": reference["steps"]["half2"],
        "full_backward_euler_inventory_lbmol": reference["steps"]["full"]["inventory_lbmol"],
        "level_setpoints": source["level_setpoints"],
        "product_reference_lbmolph": source["product_reference_lbmolph"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": source["solver"],
        "step_seconds": 0.125,
        "required_rank": 58,
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "component_kinematic_identity": 1.0e-12,
            "energy_kinematic_identity_BTU": 1.0e-6,
            "controller_kinematic_identity": 1.0e-12,
            "controller_equation_closure": 1.0e-8,
            "maximum_absolute_inventory_difference_lbmol": 1.0e-4,
            "inventory_difference_l1_lbmol": 2.0e-4,
            "rate_coordinate_difference": 1.0e-4,
            "algebraic_coordinate_difference": 1.0e-4,
            "controller_memory_difference": 1.0e-8,
            "product_relative_difference": 1.0e-7,
            "level_fraction_difference": 1.0e-8,
            "richardson_error_ratio": 1.0,
            "global_component_inventory_identity_lbmol": 1.0e-6,
            "provider_calls": 25000,
            "wall_clock_sec": 120.0
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "the single BDF2 root fails closure, rank, condition, physicality, equilibrium, conservation, or kinematics",
            "the BDF2 endpoint exceeds any frozen backward-Euler comparison limit",
            "BDF2 is not closer than refined backward Euler to the fixed Richardson inventory estimate",
            "provider ownership, call, or wall gate fails"
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "controller_tuning_attempted": False,
        "retry_authorized": False,
        "trajectory_attempted": False,
        "campaign_executed": False
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-198 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-198 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-198 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-198 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-198 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-198 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-198 contract is not committed")


def _physical(spec: Any, outcome: TerminalInventoryControlBDF2StepOutcome) -> dict[str, bool]:
    evaluation = outcome.evaluation
    state = evaluation.control_evaluation.base.physical_state
    properties = evaluation.control_evaluation.base.steady_evaluation.properties
    hydraulic_indices = [
        spec.topology.volume_ids.index(volume)
        for volume in spec.topology.hydraulic_volume_ids
    ]
    heights = np.asarray(properties.liquid_height_ft)[hydraulic_indices]
    spacings = np.asarray([geometry.tray_spacing_ft for geometry in spec.hydraulic_geometry])
    return {
        "positive_inventory": bool(np.all(evaluation.kinematics.endpoint_inventory_lbmol > 0.0)),
        "positive_liquid_composition": bool(np.all(state.liquid_mole_fraction > 0.0)),
        "positive_vapor_composition": bool(np.all(state.vapor_mole_fraction > 0.0)),
        "positive_flows": bool(
            np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(state.vapor_flow_lbmolph > 0.0)
            and evaluation.distillate_lbmolph > 0.0
            and evaluation.bottoms_lbmolph > 0.0
        ),
        "physical_levels": bool(
            np.all(evaluation.level_fraction > 0.01)
            and np.all(evaluation.level_fraction < 0.99)
        ),
        "ordered_temperature": bool(np.all(np.diff(state.temperature_F) > 0.0)),
        "ordered_pressure": bool(np.all(np.diff(spec.pressure_psia) > 0.0)),
        "negative_condenser_duty": bool(state.condenser_duty_BTUph < 0.0),
        "hydraulic_height_below_spacing": bool(np.all(heights < spacings)),
        "all_finite": bool(
            np.all(np.isfinite(outcome.final_coordinates))
            and np.all(np.isfinite(outcome.final_residual))
        ),
    }


def execute(contract_path: Path, result_path: Path, result_doc_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    dd185_contract = _load(DD185_CONTRACT)
    spec = dd186.dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd186.dd171.dd168._reference(payload["reference"])
    root_state = dd186.dd171._state(payload["accepted_root_state"])
    contract = dd185._controlled_contract(spec, dd185_contract)
    structural = audit_terminal_inventory_control_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-198 controlled structural contract changed")
    prior_inventory = np.asarray(payload["prior_inventory_lbmol"], dtype=float)
    prior_memory = np.asarray(payload["prior_controller_memory"], dtype=float)
    prior_point = np.asarray(payload["prior_solve_coordinates"], dtype=float)
    current_report = payload["current_backward_euler_report"]
    endpoint_report = payload["endpoint_backward_euler_report"]
    current_inventory = np.asarray(current_report["inventory_lbmol"], dtype=float)
    current_memory = np.asarray(current_report["controller_memory"], dtype=float)
    endpoint_be_inventory = np.asarray(endpoint_report["inventory_lbmol"], dtype=float)
    current_point = _coordinates(current_report, prior_memory, payload["step_seconds"])
    endpoint_be_point = _coordinates(endpoint_report, current_memory, payload["step_seconds"])
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    provider = dd186.dd171._provider(Path(payload["workbook"]), payload["property_package"])
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    started = time.perf_counter()

    prior_eval = evaluate_terminal_inventory_control_residual(
        contract, spec, reference, root_state, provider, audit,
        inventory_lbmol=prior_inventory,
        controller_memory=prior_memory,
        level_setpoints=setpoints,
        solve_coordinates=prior_point,
        storage_gradient_BTU_lbmol=np.zeros_like(prior_inventory),
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=product_reference,
        state_id="dd198_prior_history",
        evaluation_kind="residual",
    )
    current_eval = evaluate_terminal_inventory_control_residual(
        contract, spec, reference, prior_eval.base.physical_state, provider, audit,
        inventory_lbmol=current_inventory,
        controller_memory=current_memory,
        level_setpoints=setpoints,
        solve_coordinates=current_point,
        storage_gradient_BTU_lbmol=np.zeros_like(current_inventory),
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=product_reference,
        state_id="dd198_current_history",
        evaluation_kind="residual",
    )
    prior_storage = governing_storage_vector(spec, prior_eval.base, prior_inventory)
    current_storage = governing_storage_vector(spec, current_eval.base, current_inventory)
    history = build_controlled_bdf2_history(
        step_seconds=payload["step_seconds"],
        current_inventory_lbmol=current_inventory,
        prior_inventory_lbmol=prior_inventory,
        current_internal_energy_BTU=current_storage,
        prior_internal_energy_BTU=prior_storage,
        current_controller_memory=current_memory,
        prior_controller_memory=prior_memory,
    )
    rate_scales = component_rate_scales(contract.base, current_eval.base)
    outcome = solve_terminal_inventory_control_bdf2_step(
        contract, spec, reference, current_eval.base.physical_state, provider, audit,
        history=history,
        level_setpoints=setpoints,
        rate_scales_lbmolph=rate_scales,
        initial_solve_coordinates=endpoint_be_point,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=product_reference,
        step_seconds=payload["step_seconds"],
        settings=dd186._settings(payload),
        name="dd198_bdf2_0p125s",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd186._provider_summary(audit)

    evaluation = outcome.evaluation
    endpoint = evaluation.kinematics.endpoint_inventory_lbmol
    full_inventory = np.asarray(payload["full_backward_euler_inventory_lbmol"], dtype=float)
    richardson = 2.0 * endpoint_be_inventory - full_inventory
    endpoint_difference = endpoint - endpoint_be_inventory
    bdf2_richardson = endpoint - richardson
    be_richardson = endpoint_be_inventory - richardson
    max_bdf2_richardson = float(np.max(np.abs(bdf2_richardson)))
    max_be_richardson = float(np.max(np.abs(be_richardson)))
    ratio = max_bdf2_richardson / max(max_be_richardson, 1e-30)
    rank, condition = _rank_condition(outcome.final_jacobian)
    state = evaluation.control_evaluation.base.physical_state
    properties = evaluation.control_evaluation.base.steady_evaluation.properties
    component_external = _external_component_rate(spec, evaluation)
    component_error = np.sum(evaluation.kinematics.component_rate_lbmolph, axis=0) - component_external
    component_scale = max(float(np.max(np.abs(spec.feed_component_lbmolph))), 1.0)
    energy_external = (
        float(spec.feed_enthalpy_BTUph)
        + float(spec.reboiler_duty_BTUph)
        + float(state.condenser_duty_BTUph)
        - state.distillate_lbmolph * properties.liquid_enthalpy_BTU_lbmol[0]
        - state.bottoms_lbmolph * properties.liquid_enthalpy_BTU_lbmol[-1]
    )
    energy_error = float(np.sum(evaluation.kinematics.energy_storage_rate_BTUph) - energy_external)
    energy_scale = max(
        abs(float(spec.feed_enthalpy_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(state.condenser_duty_BTUph)),
        1.0,
    )
    step_hours = float(payload["step_seconds"]) / 3600.0
    component_identity = float(np.max(np.abs(
        3.0 * (endpoint - current_inventory) - (current_inventory - prior_inventory)
        - 2.0 * step_hours * evaluation.kinematics.component_rate_lbmolph
    )))
    energy_identity = float(np.max(np.abs(
        3.0 * (evaluation.kinematics.endpoint_internal_energy_BTU - current_storage)
        - (current_storage - prior_storage)
        - 2.0 * step_hours * evaluation.kinematics.energy_storage_rate_BTUph
    )))
    controller_identity = float(np.max(np.abs(
        3.0 * (evaluation.kinematics.endpoint_controller_memory - current_memory)
        - (current_memory - prior_memory)
        - 2.0 * payload["step_seconds"] * evaluation.kinematics.controller_rate_per_sec
    )))
    actual_component_accumulation = np.sum(
        3.0 * (endpoint - current_inventory) - (current_inventory - prior_inventory),
        axis=0,
    )
    expected_component_accumulation = (
        2.0 * step_hours * _external_component_rate(spec, evaluation)
    )
    global_identity = float(
        np.max(np.abs(actual_component_accumulation - expected_component_accumulation))
    )
    endpoint_be_rate = np.asarray(endpoint_report["rate_coordinates"], dtype=float)
    endpoint_be_algebraic = np.asarray(endpoint_report["algebraic_coordinates"], dtype=float)
    endpoint_be_products = np.asarray(
        (endpoint_report["distillate_lbmolph"], endpoint_report["bottoms_lbmolph"]),
        dtype=float,
    )
    products = np.asarray((evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph))
    comparison = {
        "maximum_absolute_inventory_difference_lbmol": float(np.max(np.abs(endpoint_difference))),
        "inventory_difference_l1_lbmol": float(np.sum(np.abs(endpoint_difference))),
        "rate_coordinate_difference": float(np.max(np.abs(evaluation.kinematics.component_rate_coordinates - endpoint_be_rate))),
        "algebraic_coordinate_difference": float(np.max(np.abs(evaluation.algebraic_coordinates - endpoint_be_algebraic))),
        "controller_memory_difference": float(np.max(np.abs(evaluation.kinematics.endpoint_controller_memory - np.asarray(endpoint_report["controller_memory"])) )),
        "product_relative_difference": float(np.max(np.abs(products - endpoint_be_products) / product_reference)),
        "level_fraction_difference": float(np.max(np.abs(evaluation.level_fraction - np.asarray(endpoint_report["level_fraction"])) )),
        "bdf2_richardson_max_abs_lbmol": max_bdf2_richardson,
        "backward_euler_richardson_max_abs_lbmol": max_be_richardson,
        "richardson_max_error_ratio": ratio,
    }
    physical = _physical(spec, outcome)
    limits = payload["limits"]
    step = {
        "success": outcome.success,
        "status": outcome.status,
        "message": outcome.message,
        "nfev": outcome.nfev,
        "njev": outcome.njev,
        "wall_clock_sec": outcome.wall_clock_sec,
        "residual_inf_norm": float(np.max(np.abs(outcome.final_residual))),
        "jacobian_rank": rank,
        "jacobian_condition": condition,
        "maximum_equilibrium_residual": evaluation.maximum_equilibrium_residual,
        "component_conservation_relative_error": float(np.max(np.abs(component_error)) / component_scale),
        "energy_conservation_relative_error": abs(energy_error) / energy_scale,
        "component_kinematic_identity": component_identity,
        "energy_kinematic_identity_BTU": energy_identity,
        "controller_kinematic_identity": controller_identity,
        "controller_equation_closure": float(np.max(np.abs(evaluation.raw[-4:]))),
        "global_component_inventory_identity_lbmol": global_identity,
        "inventory_lbmol": _rows(endpoint),
        "rate_coordinates": _rows(evaluation.kinematics.component_rate_coordinates),
        "algebraic_coordinates": _vector(evaluation.algebraic_coordinates),
        "controller_memory": _vector(evaluation.kinematics.endpoint_controller_memory),
        "level_fraction": _vector(evaluation.level_fraction),
        "product_log_ratio": _vector(evaluation.product_log_ratio),
        "distillate_lbmolph": evaluation.distillate_lbmolph,
        "bottoms_lbmolph": evaluation.bottoms_lbmolph,
        "physical": physical,
    }
    gates = {
        "success": outcome.success and outcome.nfev <= payload["solver"]["max_nfev"],
        "residual": step["residual_inf_norm"] < limits["scaled_residual"],
        "rank": rank == payload["required_rank"],
        "condition": condition < limits["condition"],
        "equilibrium": evaluation.maximum_equilibrium_residual < limits["equilibrium_residual"],
        "component_conservation": step["component_conservation_relative_error"] < limits["component_conservation"],
        "energy_conservation": step["energy_conservation_relative_error"] < limits["energy_conservation"],
        "component_kinematics": component_identity < limits["component_kinematic_identity"],
        "energy_kinematics": energy_identity < limits["energy_kinematic_identity_BTU"],
        "controller_kinematics": controller_identity < limits["controller_kinematic_identity"],
        "controller_equations": step["controller_equation_closure"] < limits["controller_equation_closure"],
        "global_component_identity": global_identity < limits["global_component_inventory_identity_lbmol"],
        "physical": all(physical.values()),
        "inventory_max": comparison["maximum_absolute_inventory_difference_lbmol"] < limits["maximum_absolute_inventory_difference_lbmol"],
        "inventory_l1": comparison["inventory_difference_l1_lbmol"] < limits["inventory_difference_l1_lbmol"],
        "rate_comparison": comparison["rate_coordinate_difference"] < limits["rate_coordinate_difference"],
        "algebraic_comparison": comparison["algebraic_coordinate_difference"] < limits["algebraic_coordinate_difference"],
        "controller_comparison": comparison["controller_memory_difference"] < limits["controller_memory_difference"],
        "product_comparison": comparison["product_relative_difference"] < limits["product_relative_difference"],
        "level_comparison": comparison["level_fraction_difference"] < limits["level_fraction_difference"],
        "richardson_accuracy_improvement": ratio < limits["richardson_error_ratio"],
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": "controlled_bdf2_moving_step_passed" if passed else "controlled_bdf2_moving_step_failed",
        "decision": (
            "authorize_one_frozen_short_bdf2_refinement_contract"
            if passed else "stop_bdf2_moving_work"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": float(elapsed),
        "step": step,
        "comparison": comparison,
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
        "alternate_step_attempted": False,
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
    parser.add_argument("--dd187-contract", type=Path, default=DD187_CONTRACT)
    parser.add_argument("--dd187-result", type=Path, default=DD187_RESULT)
    parser.add_argument("--dd197-result", type=Path, default=DD197_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.dd187_contract,
            args.dd187_result,
            args.dd197_result,
            args.contract,
            args.contract_doc,
        )
        print(json.dumps({
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "campaign_executed": output["campaign_executed"],
        }, indent=2))
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(json.dumps({
            "classification": output["classification"],
            "pass_gate": output["pass_gate"],
            "decision": output["decision"],
        }, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
