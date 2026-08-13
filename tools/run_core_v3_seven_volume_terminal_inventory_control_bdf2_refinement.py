#!/usr/bin/env python
"""Prepare or execute DD-199's short controlled BDF2 refinement proof."""

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
import run_core_v3_seven_volume_terminal_inventory_control_moving_step as dd187  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_short_trajectory as dd188  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step as dd198  # noqa: E402
from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (  # noqa: E402
    InventoryRefinementLimits,
    assess_inventory_refinement,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_residual_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2StepOutcome,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_trajectory_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2TrajectoryRecord,
    TerminalInventoryControlBDF2TrajectoryResult,
    run_terminal_inventory_control_bdf2_trajectory,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    audit_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    TerminalInventoryControlStepOutcome,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
)


SCHEMA = "dd199-core-v3-seven-volume-controlled-bdf2-refinement-contract-v1"
RESULT_SCHEMA = "dd199-core-v3-seven-volume-controlled-bdf2-refinement-result-v1"
DD187_CONTRACT = Path("logs/dd187_core_v3_seven_volume_terminal_inventory_control_moving_step_contract_20260813.json")
DD188_RESULT = Path("logs/dd188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_20260813.json")
DD198_RESULT = Path("logs/dd198_core_v3_seven_volume_terminal_inventory_control_bdf2_moving_step_20260813.json")
DD185_CONTRACT = Path("logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json")
CONTRACT = Path("logs/dd199_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_contract_20260813.json")
RESULT = Path("logs/dd199_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_20260813")
CONTRACT_DOC = Path("docs/dd_199_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_contract_20260813.md")
RESULT_DOC = Path("docs/dd_199_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_20260813.md")
DURATION_SEC = 2.0
COARSE_DT_SEC = 0.25
REFINED_DT_SEC = 0.125
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_kinematics_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_residual_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/physical_refinement_policy_v1.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement.py",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _rank_condition(matrix: Sequence[Sequence[float]]) -> tuple[int, float]:
    values = np.asarray(matrix, dtype=float)
    singular = np.linalg.svd(values, compute_uv=False)
    tolerance = max(values.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return rank, condition


def _endpoint(record: TerminalInventoryControlBDF2TrajectoryRecord) -> Any:
    evaluation = record.outcome.evaluation
    if record.method == "backward_euler":
        return {
            "inventory": evaluation.endpoint_inventory_lbmol,
            "component_rate": evaluation.component_rate_lbmolph,
            "rate_coordinates": evaluation.rate_coordinates,
            "energy_rate": evaluation.energy_storage_rate_BTUph,
            "memory": evaluation.endpoint_controller_memory,
            "controller_rate": evaluation.controller_rate_per_sec,
            "algebraic": evaluation.algebraic_coordinates,
            "levels": evaluation.level_fraction,
            "products": np.asarray((evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph)),
            "control": evaluation.control_evaluation,
            "equilibrium": evaluation.maximum_equilibrium_residual,
        }
    return {
        "inventory": evaluation.kinematics.endpoint_inventory_lbmol,
        "component_rate": evaluation.kinematics.component_rate_lbmolph,
        "rate_coordinates": evaluation.kinematics.component_rate_coordinates,
        "energy_rate": evaluation.kinematics.energy_storage_rate_BTUph,
        "memory": evaluation.kinematics.endpoint_controller_memory,
        "controller_rate": evaluation.kinematics.controller_rate_per_sec,
        "algebraic": evaluation.algebraic_coordinates,
        "levels": evaluation.level_fraction,
        "products": np.asarray((evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph)),
        "control": evaluation.control_evaluation,
        "equilibrium": evaluation.maximum_equilibrium_residual,
    }


def _external_component_rate(spec: Any, endpoint: Mapping[str, Any]) -> np.ndarray:
    state = endpoint["control"].base.physical_state
    return (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )


def _bdf2_expected_inventory_history(
    initial_inventory: np.ndarray,
    external_rates: Sequence[np.ndarray],
    step_seconds: float,
) -> list[np.ndarray]:
    """Reconstruct BE startup plus BDF2 inventory from endpoint external rates."""
    h = float(step_seconds) / 3600.0
    expected = [np.asarray(initial_inventory, dtype=float).copy()]
    first_total = np.sum(expected[0], axis=0) + h * np.asarray(external_rates[0])
    first = expected[0].copy()
    first[-1] += first_total - np.sum(first, axis=0)
    expected.append(first)
    for rate in external_rates[1:]:
        next_total = (
            4.0 * np.sum(expected[-1], axis=0)
            - np.sum(expected[-2], axis=0)
            + 2.0 * h * np.asarray(rate)
        ) / 3.0
        next_state = expected[-1].copy()
        next_state[-1] += next_total - np.sum(next_state, axis=0)
        expected.append(next_state)
    return expected


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    return "\n".join((
        "# DD-199 Controlled BDF2 Short-Refinement Contract",
        "",
        f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
        f"- Preparation base commit: `{payload['preparation_base_commit']}`",
        "- Disturbance/controllers/product references: unchanged from DD-187",
        f"- Coarse path: `{paths['coarse_steps']} x {paths['coarse_step_seconds']} s`",
        f"- Refined path: `{paths['refined_steps']} x {paths['refined_step_seconds']} s`",
        "- Each path: one backward-Euler startup, then constant-step BDF2",
        f"- Shared-time comparisons: `{paths['shared_time_count']}`",
        "- Accuracy gate: worst shared inventory max and L1 errors below `0.8 x` DD-188",
        "- Retry, alternate grid, tuning, fallback, or longer trajectory: `False`",
        "",
        "Commit this immutable contract before its one execution.",
        "",
    ))


def _result_markdown(payload: Mapping[str, Any]) -> str:
    shared = payload["shared_time_refinement"]
    return "\n".join((
        "# DD-199 Controlled BDF2 Short-Refinement Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Completed roots: `{payload['completed_roots']}`",
        f"- Worst residual / condition: `{payload['worst_residual']:.6e}` / `{payload['worst_condition']:.6e}`",
        f"- Worst shared inventory max / L1: `{shared['worst_absolute_component_difference_lbmol']:.6e}` / `{shared['worst_component_l1_lbmol']:.6e} lbmol`",
        f"- DD-188 max / L1 ratios: `{shared['dd188_max_error_ratio']:.6f}` / `{shared['dd188_l1_error_ratio']:.6f}`",
        f"- Coarse/refined accumulation: `{payload['response']['coarse']['total_inventory_change_lbmol']:.6e}` / `{payload['response']['refined']['total_inventory_change_lbmol']:.6e} lbmol`",
        f"- Provider calls / wall: `{payload['provider']['total_calls']}` / `{payload['wall_clock_sec']:.3f} s`",
        "- Retry, tuning, alternate grid, or longer trajectory: `False`",
        "",
    ))


def prepare(source_path: Path, dd198_path: Path, dd188_path: Path, contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    source = _load(source_path)
    dd198 = _load(dd198_path)
    dd188 = _load(dd188_path)
    if not dd198["pass_gate"] or not all(dd198["gates"].values()):
        raise RuntimeError("DD-199 requires accepted DD-198")
    coarse_steps = int(round(DURATION_SEC / COARSE_DT_SEC))
    refined_steps = int(round(DURATION_SEC / REFINED_DT_SEC))
    pairs = [[index, 2 * index] for index in range(1, coarse_steps + 1)]
    baseline = dd188["shared_time_refinement"]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd187.dd186._git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): dd187.dd186._sha(ROOT / path)
            for path in (source_path, dd198_path, dd188_path, DD185_CONTRACT)
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
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": source["solver"],
        "paths": {
            "duration_seconds": DURATION_SEC,
            "coarse_step_seconds": COARSE_DT_SEC,
            "coarse_steps": coarse_steps,
            "refined_step_seconds": REFINED_DT_SEC,
            "refined_steps": refined_steps,
            "shared_time_count": len(pairs),
            "shared_step_pairs_1based": pairs,
        },
        "dd188_accuracy_baseline": {
            "worst_absolute_component_difference_lbmol": baseline["worst_absolute_component_difference_lbmol"],
            "worst_component_l1_lbmol": baseline["worst_component_l1_lbmol"],
            "required_ratio": 0.8,
        },
        "limits": {
            "scaled_residual": 1e-8,
            "condition": 1e8,
            "equilibrium_residual": 1e-10,
            "component_conservation": 1e-8,
            "energy_conservation": 1e-8,
            "kinematic_identity": 1e-6,
            "controller_equation_closure": 1e-8,
            "global_component_inventory_identity_lbmol": 1e-6,
            "integrated_response_relative_error": 1e-6,
            "response_relative_cross_grid": 1e-5,
            "external_flow_explanation_lbmol": 1e-10,
            "rate_coordinate_refinement": 1e-5,
            "algebraic_coordinate_refinement": 1e-5,
            "controller_memory_refinement": 1e-7,
            "product_relative_refinement": 1e-6,
            "level_fraction_refinement": 1e-8,
            "provider_calls": 150000,
            "wall_clock_sec": 120.0,
        },
        "physical_refinement_limits": source["physical_refinement_limits"],
        "required_rank": 58,
        "implementation_sha256": {path: dd187.dd186._sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "either path fails to complete every root",
            "any root loses closure, rank, condition, physicality, equilibrium, conservation, or kinematics",
            "shared physical/controller refinement exceeds a frozen limit",
            "worst inventory max or L1 refinement is not below 0.8 times DD-188",
            "response, provider, call, or wall gate fails",
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
        raise RuntimeError("DD-199 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd187.dd186._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-199 contract hash mismatch")
    for path, expected in payload["sources"].items():
        if dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-199 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-199 implementation changed: {path}")
    if dd187.dd186._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-199 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-199 result exists; rerun prohibited")
    if not dd187.dd186._git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-199 contract is not committed")


def _step_report(record: TerminalInventoryControlBDF2TrajectoryRecord, spec: Any, limits: Mapping[str, float], required_rank: int) -> dict[str, Any]:
    outcome = record.outcome
    endpoint = _endpoint(record)
    rank, condition = _rank_condition(outcome.final_jacobian)
    state = endpoint["control"].base.physical_state
    properties = endpoint["control"].base.steady_evaluation.properties
    component_error = np.sum(endpoint["component_rate"], axis=0) - _external_component_rate(spec, endpoint)
    component_scale = max(float(np.max(np.abs(spec.feed_component_lbmolph))), 1.0)
    energy_external = (
        float(spec.feed_enthalpy_BTUph) + float(spec.reboiler_duty_BTUph)
        + float(state.condenser_duty_BTUph)
        - state.distillate_lbmolph * properties.liquid_enthalpy_BTU_lbmol[0]
        - state.bottoms_lbmolph * properties.liquid_enthalpy_BTU_lbmol[-1]
    )
    energy_scale = max(abs(float(spec.feed_enthalpy_BTUph)), abs(float(spec.reboiler_duty_BTUph)), abs(float(state.condenser_duty_BTUph)), 1.0)
    physical = dd198._physical(spec, outcome) if isinstance(outcome, TerminalInventoryControlBDF2StepOutcome) else dd187.dd186._step_report(
        outcome, spec, outcome.evaluation.previous_inventory_lbmol,
        outcome.initial_coordinates, outcome.evaluation.previous_controller_memory,
        endpoint["levels"], endpoint["products"], record.time_seconds,
    )["physical"]
    report = {
        "index": record.index,
        "time_seconds": record.time_seconds,
        "method": record.method,
        "success": outcome.success,
        "nfev": outcome.nfev,
        "njev": outcome.njev,
        "residual_inf_norm": float(np.max(np.abs(outcome.final_residual))),
        "jacobian_rank": rank,
        "jacobian_condition": condition,
        "maximum_equilibrium_residual": float(endpoint["equilibrium"]),
        "component_conservation_relative_error": float(np.max(np.abs(component_error)) / component_scale),
        "energy_conservation_relative_error": abs(float(np.sum(endpoint["energy_rate"]) - energy_external)) / energy_scale,
        "controller_equation_closure": float(np.max(np.abs(endpoint["control"].raw[-4:]))),
        "inventory_lbmol": _rows(endpoint["inventory"]),
        "rate_coordinates": _rows(endpoint["rate_coordinates"]),
        "algebraic_coordinates": _vector(endpoint["algebraic"]),
        "controller_memory": _vector(endpoint["memory"]),
        "level_fraction": _vector(endpoint["levels"]),
        "distillate_lbmolph": float(endpoint["products"][0]),
        "bottoms_lbmolph": float(endpoint["products"][1]),
        "physical": physical,
    }
    report["gates"] = {
        "success": outcome.success,
        "residual": report["residual_inf_norm"] < limits["scaled_residual"],
        "rank": rank == required_rank,
        "condition": condition < limits["condition"],
        "equilibrium": report["maximum_equilibrium_residual"] < limits["equilibrium_residual"],
        "component_conservation": report["component_conservation_relative_error"] < limits["component_conservation"],
        "energy_conservation": report["energy_conservation_relative_error"] < limits["energy_conservation"],
        "controller_equations": report["controller_equation_closure"] < limits["controller_equation_closure"],
        "physical": all(physical.values()),
    }
    return report


def _path_report(trajectory: TerminalInventoryControlBDF2TrajectoryResult, spec: Any, initial_inventory: np.ndarray, limits: Mapping[str, float], required_rank: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    endpoints = [_endpoint(record) for record in trajectory.records]
    reports = [_step_report(record, spec, limits, required_rank) for record in trajectory.records]
    external = [_external_component_rate(spec, endpoint) for endpoint in endpoints]
    expected = _bdf2_expected_inventory_history(initial_inventory, external, trajectory.step_seconds)
    final = endpoints[-1]["inventory"]
    expected_total = np.sum(expected[-1] - expected[0], axis=0)
    actual_total = np.sum(final - initial_inventory, axis=0)
    totals = [float(np.sum(initial_inventory)), *[float(np.sum(endpoint["inventory"])) for endpoint in endpoints]]
    response = {
        "component_inventory_change_lbmol": _vector(actual_total),
        "expected_component_inventory_change_lbmol": _vector(expected_total),
        "component_inventory_identity_max_abs_lbmol": float(np.max(np.abs(actual_total - expected_total))),
        "total_inventory_change_lbmol": float(np.sum(actual_total)),
        "expected_total_inventory_change_lbmol": float(np.sum(expected_total)),
        "total_inventory_strictly_increasing": bool(np.all(np.diff(totals) > 0.0)),
    }
    response["total_inventory_relative_error"] = abs(response["total_inventory_change_lbmol"] - response["expected_total_inventory_change_lbmol"]) / max(abs(response["expected_total_inventory_change_lbmol"]), 1e-12)
    return response, reports


def _shared(initial_inventory: np.ndarray, coarse: TerminalInventoryControlBDF2TrajectoryResult, refined: TerminalInventoryControlBDF2TrajectoryResult, pairs: Sequence[Sequence[int]], payload: Mapping[str, Any]) -> dict[str, Any]:
    limits = payload["limits"]
    physical_limits = InventoryRefinementLimits.from_mapping(payload["physical_refinement_limits"])
    comparisons = []
    for coarse_index, refined_index in pairs:
        c = _endpoint(coarse.records[int(coarse_index) - 1])
        r = _endpoint(refined.records[int(refined_index) - 1])
        physical = assess_inventory_refinement(initial_inventory, c["inventory"], r["inventory"], physical_limits)
        product_scale = np.maximum(np.abs(c["products"]), 1.0)
        metrics = {
            "rate_coordinate_difference": float(np.max(np.abs(c["rate_coordinates"] - r["rate_coordinates"]))),
            "algebraic_coordinate_difference": float(np.max(np.abs(c["algebraic"] - r["algebraic"]))),
            "controller_memory_difference": float(np.max(np.abs(c["memory"] - r["memory"]))),
            "product_relative_difference": float(np.max(np.abs(c["products"] - r["products"]) / product_scale)),
            "level_fraction_difference": float(np.max(np.abs(c["levels"] - r["levels"]))),
        }
        gates = {
            **dict(physical.gates),
            "rate": metrics["rate_coordinate_difference"] < limits["rate_coordinate_refinement"],
            "algebraic": metrics["algebraic_coordinate_difference"] < limits["algebraic_coordinate_refinement"],
            "controller_memory": metrics["controller_memory_difference"] < limits["controller_memory_refinement"],
            "product": metrics["product_relative_difference"] < limits["product_relative_refinement"],
            "level": metrics["level_fraction_difference"] < limits["level_fraction_refinement"],
        }
        comparisons.append({
            "coarse_step": int(coarse_index), "refined_step": int(refined_index),
            "time_seconds": float(coarse_index) * COARSE_DT_SEC,
            "physical_metrics": dict(physical.metrics), **metrics,
            "gates": gates, "pass_gate": all(gates.values()),
        })
    worst_max = max(item["physical_metrics"]["maximum_absolute_component_difference_lbmol"] for item in comparisons)
    worst_l1 = max(item["physical_metrics"]["component_difference_l1_lbmol"] for item in comparisons)
    baseline = payload["dd188_accuracy_baseline"]
    return {
        "comparisons": comparisons,
        "worst_absolute_component_difference_lbmol": worst_max,
        "worst_component_l1_lbmol": worst_l1,
        "worst_rate_coordinate_difference": max(item["rate_coordinate_difference"] for item in comparisons),
        "worst_algebraic_coordinate_difference": max(item["algebraic_coordinate_difference"] for item in comparisons),
        "worst_controller_memory_difference": max(item["controller_memory_difference"] for item in comparisons),
        "worst_product_relative_difference": max(item["product_relative_difference"] for item in comparisons),
        "worst_level_fraction_difference": max(item["level_fraction_difference"] for item in comparisons),
        "dd188_max_error_ratio": worst_max / baseline["worst_absolute_component_difference_lbmol"],
        "dd188_l1_error_ratio": worst_l1 / baseline["worst_component_l1_lbmol"],
        "physical_pass": all(item["pass_gate"] for item in comparisons),
    }


def execute(contract_path: Path, result_path: Path, result_doc_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    dd185_contract = _load(DD185_CONTRACT)
    spec = dd187.dd186.dd171.dd168._spec(payload["source_mapping"], float(payload["operating_spec"]["feed_enthalpy_BTUph"]))
    reference = dd187.dd186.dd171.dd168._reference(payload["reference"])
    state = dd187.dd186.dd171._state(payload["accepted_root_state"])
    contract = dd185._controlled_contract(spec, dd185_contract)
    structural = audit_terminal_inventory_control_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-199 structural contract changed")
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    coordinates = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["initial_controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    products = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    provider = dd187.dd186.dd171._provider(Path(payload["workbook"]), payload["property_package"])
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = dd187.dd186._settings(payload)
    common = dict(
        contract=contract, spec=spec, reference=reference, initial_template=state,
        provider=provider, call_audit=audit, initial_inventory_lbmol=inventory,
        initial_controller_memory=memory, level_setpoints=setpoints,
        initial_solve_coordinates=coordinates,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=products, duration_seconds=DURATION_SEC, settings=settings,
    )
    started = time.perf_counter()
    coarse = run_terminal_inventory_control_bdf2_trajectory(**common, step_seconds=COARSE_DT_SEC, name="dd199_coarse")
    refined = run_terminal_inventory_control_bdf2_trajectory(**common, step_seconds=REFINED_DT_SEC, name="dd199_refined")
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd187.dd186._provider_summary(audit)
    limits = payload["limits"]
    coarse_response, coarse_steps = _path_report(coarse, spec, inventory, limits, payload["required_rank"])
    refined_response, refined_steps = _path_report(refined, spec, inventory, limits, payload["required_rank"])
    shared = _shared(inventory, coarse, refined, payload["paths"]["shared_step_pairs_1based"], payload)
    response = {"coarse": coarse_response, "refined": refined_response}
    cross_difference = coarse_response["total_inventory_change_lbmol"] - refined_response["total_inventory_change_lbmol"]
    expected_difference = coarse_response["expected_total_inventory_change_lbmol"] - refined_response["expected_total_inventory_change_lbmol"]
    response_scale = max(abs(coarse_response["total_inventory_change_lbmol"]), abs(refined_response["total_inventory_change_lbmol"]), 1e-12)
    response_gates = {
        "coarse": coarse_response["total_inventory_change_lbmol"] > 0.0 and coarse_response["total_inventory_strictly_increasing"] and coarse_response["total_inventory_relative_error"] < limits["integrated_response_relative_error"] and coarse_response["component_inventory_identity_max_abs_lbmol"] < limits["global_component_inventory_identity_lbmol"],
        "refined": refined_response["total_inventory_change_lbmol"] > 0.0 and refined_response["total_inventory_strictly_increasing"] and refined_response["total_inventory_relative_error"] < limits["integrated_response_relative_error"] and refined_response["component_inventory_identity_max_abs_lbmol"] < limits["global_component_inventory_identity_lbmol"],
        "cross_grid_explained": abs(cross_difference - expected_difference) < limits["external_flow_explanation_lbmol"],
        "cross_grid_response_relative": abs(cross_difference) / response_scale < limits["response_relative_cross_grid"],
    }
    all_steps = coarse_steps + refined_steps
    baseline_ratio = payload["dd188_accuracy_baseline"]["required_ratio"]
    gates = {
        "coarse_complete": coarse.completed and len(coarse_steps) == payload["paths"]["coarse_steps"],
        "refined_complete": refined.completed and len(refined_steps) == payload["paths"]["refined_steps"],
        "roots": all(all(item["gates"].values()) for item in all_steps),
        "shared_physical": shared["physical_pass"],
        "accuracy_max": shared["dd188_max_error_ratio"] < baseline_ratio,
        "accuracy_l1": shared["dd188_l1_error_ratio"] < baseline_ratio,
        "response": all(response_gates.values()),
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": "controlled_bdf2_refinement_passed" if passed else "controlled_bdf2_refinement_failed",
        "decision": "authorize_one_frozen_modest_bdf2_trajectory_contract" if passed else "stop_bdf2_trajectory_path",
        "contract_commit": dd187.dd186._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "paths": payload["paths"],
        "wall_clock_sec": float(elapsed),
        "completed_roots": len(all_steps),
        "worst_residual": max(item["residual_inf_norm"] for item in all_steps),
        "worst_condition": max(item["jacobian_condition"] for item in all_steps),
        "coarse": {"steps": coarse_steps},
        "refined": {"steps": refined_steps},
        "shared_time_refinement": shared,
        "response": response,
        "cross_grid": {"actual_difference_lbmol": cross_difference, "expected_external_difference_lbmol": expected_difference, "unexplained_difference_lbmol": cross_difference - expected_difference, "response_relative_difference": abs(cross_difference) / response_scale},
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "response_gates": response_gates,
        "campaign_gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
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
    parser.add_argument("--source", type=Path, default=DD187_CONTRACT)
    parser.add_argument("--dd198", type=Path, default=DD198_RESULT)
    parser.add_argument("--dd188", type=Path, default=DD188_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.source, args.dd198, args.dd188, args.contract, args.contract_doc)
        print(json.dumps({"schema_id": output["schema_id"], "contract_payload_sha256": output["contract_payload_sha256"], "paths": output["paths"], "campaign_executed": output["campaign_executed"]}, indent=2))
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(json.dumps({"classification": output["classification"], "pass_gate": output["pass_gate"], "decision": output["decision"]}, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
