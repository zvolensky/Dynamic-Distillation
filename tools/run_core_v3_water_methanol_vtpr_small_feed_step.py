#!/usr/bin/env python
"""Run one bounded 0.25-second fixed-product step after a small feed increase."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import audit_core_v3_water_methanol_vtpr_zero_time_handoff as zero_time  # noqa: E402
from run_core_v3_water_methanol_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_step_bounds_v1 import (  # noqa: E402
    vapor_holdup_implicit_step_coordinate_bounds,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)


SOURCE_ROOT = zero_time.DEFAULT_SOURCE
SOURCE_ZERO_TIME = zero_time.DEFAULT_JSON
SOURCE_HOLD = Path(
    "logs/core_v3_water_methanol_vtpr_fixed_product_hold_step_20260831.json"
)
SOURCE_HOLD_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_fixed_product_hold_step_20260831.npz"
)
DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_vtpr_small_feed_step_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_vtpr_small_feed_step_20260831.md"
)
DEFAULT_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_small_feed_step_20260831.npz"
)
TIMESTEP_SEC = 0.25
FEED_MULTIPLIER = 1.001
DIFFERENCE_STEP = 1.0e-5
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_LIMIT = 1.0e-8
MINIMUM_MOVEMENT = 1.0e-12
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.25
MATRIX_CHANGE_LIMIT = 0.05
COMPONENT_IDENTITY_LIMIT_LBMOL = 1.0e-6
ENERGY_IDENTITY_RELATIVE_LIMIT = 1.0e-8
CALL_LIMIT = 100000
WALL_LIMIT_SEC = 180.0
MAX_NFEV = 20


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30)
    return float(np.linalg.norm(left - right) / denominator)


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def _coordinate_scale(matrix_path: Path, dimension: int) -> np.ndarray:
    with np.load(matrix_path) as evidence:
        matrix = np.asarray(evidence["jacobian_h1"], dtype=float)
    norms = np.linalg.norm(matrix, axis=0)
    scale = 1.0 / np.maximum(norms, 1.0e-30)
    scale /= np.median(scale)
    if scale.shape != (dimension,) or np.any(~np.isfinite(scale)) or np.any(scale <= 0.0):
        raise RuntimeError("zero-time Jacobian produced an invalid coordinate scale")
    return scale


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    root_path = _rooted(SOURCE_ROOT).resolve()
    zero_path = _rooted(SOURCE_ZERO_TIME).resolve()
    hold_path = _rooted(SOURCE_HOLD).resolve()
    hold_matrix_path = _rooted(SOURCE_HOLD_MATRIX).resolve()
    root = json.loads(root_path.read_text(encoding="utf-8"))
    zero = json.loads(zero_path.read_text(encoding="utf-8"))
    hold = json.loads(hold_path.read_text(encoding="utf-8"))
    if (
        not root.get("pass_gate")
        or not zero.get("pass_gate")
        or not hold.get("pass_gate")
        or hold.get("decision") != "authorize_separately_bounded_small_disturbance_step"
        or zero.get("handoff_mode") != "fixed_terminal_products"
    ):
        raise RuntimeError("disturbed step requires the accepted root, handoff, and hold step")

    problem = starting_state.build_problem(density_model=root["density_model"])
    endpoint = root["endpoint"]
    liquid_inventory = np.asarray(endpoint["liquid_component_inventory_lbmol"], dtype=float)
    vapor_inventory = np.asarray(endpoint["vapor_component_inventory_lbmol"], dtype=float)
    phase_transfer = np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float)
    temperature = np.asarray(endpoint["temperature_F"], dtype=float)
    pressure = np.asarray(endpoint["pressure_psia"], dtype=float)
    liquid_flow = np.asarray(endpoint["hydraulic_liquid_flow_lbmolph"], dtype=float)
    vapor_flow = np.asarray(endpoint["vapor_flow_lbmolph"], dtype=float)
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    history_audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    properties = evaluate_vapor_holdup_trial_properties(
        problem["geometry"],
        liquid_inventory,
        vapor_inventory,
        temperature,
        pressure,
        provider,
        history_audit,
        state_id="water_methanol:small_feed:energy_history",
        evaluation_kind="residual",
    )
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=vapor_inventory,
        phase_transfer_lbmolph=phase_transfer,
        phase_transfer_scale_lbmolph=np.maximum(
            np.abs(phase_transfer),
            problem["numerical"].component_residual_scale_lbmolph,
        ),
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        vapor_flow_lbmolph=vapor_flow,
        condenser_duty_BTUph=float(endpoint["condenser_duty_BTUph"]),
        total_stored_energy_BTU=properties.total_stored_energy_BTU,
    )
    balance_inputs = replace(
        problem["balance_inputs"],
        feed_component_lbmolph=(
            problem["balance_inputs"].feed_component_lbmolph * FEED_MULTIPLIER
        ),
        feed_enthalpy_BTUph=(
            problem["balance_inputs"].feed_enthalpy_BTUph * FEED_MULTIPLIER
        ),
        distillate_lbmolph=float(endpoint["distillate_lbmolph"]),
        bottoms_lbmolph=float(endpoint["bottoms_lbmolph"]),
        condenser_duty_BTUph=float(endpoint["condenser_duty_BTUph"]),
    )
    stationary_numerical = problem["numerical"]
    numerical = VaporHoldupImplicitNumericalSpec(
        timestep_sec=TIMESTEP_SEC,
        temperature_coordinate_scale_F=stationary_numerical.temperature_coordinate_scale_F,
        pressure_coordinate_scale_psia=stationary_numerical.pressure_coordinate_scale_psia,
        dry_tray_pressure_drop_coefficient=(
            stationary_numerical.dry_tray_pressure_drop_coefficient
        ),
        component_mw_lbm_per_lbmol=stationary_numerical.component_mw_lbm_per_lbmol,
        pressure_link_geometry=stationary_numerical.pressure_link_geometry,
        top_pressure_anchor_psia=float(pressure[0]),
        component_residual_scale_lbmolph=(
            stationary_numerical.component_residual_scale_lbmolph
        ),
        energy_residual_scale_BTUph=stationary_numerical.energy_residual_scale_BTUph,
        pressure_residual_scale_psia=stationary_numerical.pressure_residual_scale_psia,
    )
    contract = build_vapor_holdup_dae_contract(
        problem["contract"].component_names,
        topology=problem["contract"].topology,
        product_flow_parameters=("D_stationary_root", "B_stationary_root"),
    )
    dimension = len(contract.rows)
    point = np.zeros(dimension, dtype=float)
    lower, upper = vapor_holdup_implicit_step_coordinate_bounds(contract)
    pattern = vapor_holdup_structural_pattern(contract)
    coordinate_scale = _coordinate_scale(hold_matrix_path, dimension)
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    counters = {"function": 0, "jacobian": 0}

    def objective(candidate: np.ndarray, state_id: str = "solver") -> np.ndarray:
        counters["function"] += 1
        return evaluate_vapor_holdup_implicit_residual(
            contract,
            problem["geometry"],
            reference,
            balance_inputs,
            problem["spec"].hydraulic_geometry,
            numerical,
            provider,
            audit,
            candidate,
            state_id=f"water_methanol:small_feed:{state_id}:{counters['function']}",
            evaluation_kind="jacobian",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        counters["jacobian"] += 1
        matrix, _groups = colored_central_difference_jacobian(
            objective,
            candidate,
            pattern=pattern,
            step=DIFFERENCE_STEP,
            state_id=f"water_methanol:small_feed:solver_jacobian:{counters['jacobian']}",
        )
        return matrix

    solution = least_squares(
        objective,
        point,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=coordinate_scale,
        ftol=1.0e-11,
        xtol=1.0e-11,
        gtol=1.0e-11,
        max_nfev=MAX_NFEV,
        verbose=0,
    )
    final = evaluate_vapor_holdup_implicit_residual(
        contract,
        problem["geometry"],
        reference,
        balance_inputs,
        problem["spec"].hydraulic_geometry,
        numerical,
        provider,
        audit,
        solution.x,
        state_id="water_methanol:small_feed:final",
        evaluation_kind="residual",
    )

    matrices = []
    step_results = []
    for step in ENDPOINT_STEPS:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            solution.x,
            pattern=pattern,
            step=step,
            state_id=f"water_methanol:small_feed:endpoint:h={step:.1e}",
        )
        rank, condition, singular = _rank_condition(matrix)
        matrices.append(matrix)
        step_results.append(
            {
                "step": step,
                "rank": rank,
                "condition": condition,
                "singular_values": [float(value) for value in singular],
                "color_count": len(groups),
                "zero_rows": int(np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)),
                "zero_columns": int(
                    np.count_nonzero(np.linalg.norm(matrix, axis=0) <= 1.0e-12)
                ),
            }
        )
    spectrum_change = _relative_change(
        np.asarray(step_results[0]["singular_values"]),
        np.asarray(step_results[1]["singular_values"]),
    )
    matrix_change = _relative_change(matrices[0], matrices[1])
    residual_norm = float(np.max(np.abs(final.scaled)))
    movement = float(np.max(np.abs(solution.x)))
    maximum_rate = float(
        max(
            np.max(np.abs(final.endpoint.liquid_component_rate_lbmolph)),
            np.max(np.abs(final.endpoint.vapor_component_rate_lbmolph)),
        )
    )
    actual_component = np.sum(
        final.endpoint.liquid_component_inventory_lbmol
        + final.endpoint.vapor_component_inventory_lbmol
        - reference.liquid_component_inventory_lbmol
        - reference.vapor_component_inventory_lbmol,
        axis=0,
    )
    expected_component = (
        final.transport.external_component_rate_lbmolph * TIMESTEP_SEC / 3600.0
    )
    component_identity = float(np.max(np.abs(actual_component - expected_component)))
    total_component_change = float(np.sum(actual_component))
    expected_total_component_change = float(np.sum(expected_component))
    actual_energy = float(
        np.sum(final.properties.total_stored_energy_BTU - reference.total_stored_energy_BTU)
    )
    expected_energy = float(final.transport.external_energy_rate_BTUph * TIMESTEP_SEC / 3600.0)
    energy_identity = abs(actual_energy - expected_energy)
    energy_identity_relative = energy_identity / max(
        abs(actual_energy), abs(expected_energy), 1.0
    )
    maximum_inventory_change = float(
        max(
            np.max(
                np.abs(
                    final.endpoint.liquid_component_inventory_lbmol
                    - reference.liquid_component_inventory_lbmol
                )
            ),
            np.max(
                np.abs(
                    final.endpoint.vapor_component_inventory_lbmol
                    - reference.vapor_component_inventory_lbmol
                )
            ),
        )
    )
    maximum_temperature_change = float(
        np.max(np.abs(final.endpoint.temperature_F - reference.temperature_F))
    )
    maximum_pressure_change = float(
        np.max(np.abs(final.endpoint.pressure_psia - reference.pressure_psia))
    )
    maximum_flow_relative_change = float(
        max(
            np.max(
                np.abs(
                    final.endpoint.hydraulic_liquid_flow_lbmolph
                    / reference.hydraulic_liquid_flow_lbmolph
                    - 1.0
                )
            ),
            np.max(
                np.abs(
                    final.endpoint.vapor_flow_lbmolph / reference.vapor_flow_lbmolph
                    - 1.0
                )
            ),
        )
    )
    base_feed = np.asarray(problem["balance_inputs"].feed_component_lbmolph, dtype=float)
    disturbed_feed = np.asarray(balance_inputs.feed_component_lbmolph, dtype=float)
    base_feed_total = float(np.sum(base_feed))
    disturbed_feed_total = float(np.sum(disturbed_feed))
    composition_change = float(
        np.max(np.abs(base_feed / base_feed_total - disturbed_feed / disturbed_feed_total))
    )
    specific_enthalpy_change = abs(
        float(problem["balance_inputs"].feed_enthalpy_BTUph) / base_feed_total
        - float(balance_inputs.feed_enthalpy_BTUph) / disturbed_feed_total
    )
    physical = bool(
        np.all(final.endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(final.endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(final.endpoint.temperature_F > -459.67)
        and np.all(final.endpoint.pressure_psia > 0.0)
        and np.all(np.diff(final.endpoint.pressure_psia) > 0.0)
        and np.all(final.endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(final.endpoint.vapor_flow_lbmolph > 0.0)
        and final.endpoint.condenser_duty_BTUph < 0.0
        and np.min(final.properties.free_volume.free_vapor_volume_ft3) > 0.0
    )
    minimum_bound_distance = float(
        np.min(np.minimum(solution.x - lower, upper - solution.x))
    )
    history_report = compact_provider_report(history_audit.report())
    provider_report = compact_provider_report(audit.report())
    provider_pass = bool(
        history_report["pass"]
        and provider_report["pass"]
        and not history_audit.fallback_attempted
        and not audit.fallback_attempted
    )
    wall = time.perf_counter() - started
    gates = {
        "solver": bool(solution.success),
        "residual": residual_norm < RESIDUAL_LIMIT,
        "nonzero_response": movement > MINIMUM_MOVEMENT and maximum_rate > 0.0,
        "feed_definition": bool(
            composition_change < 1.0e-14
            and specific_enthalpy_change < 1.0e-10
            and abs(disturbed_feed_total / base_feed_total - FEED_MULTIPLIER) < 1.0e-14
        ),
        "inventory_direction": bool(
            total_component_change > 0.0
            and expected_total_component_change > 0.0
            and np.all(actual_component > 0.0)
        ),
        "component_identity": component_identity < COMPONENT_IDENTITY_LIMIT_LBMOL,
        "energy_identity": energy_identity_relative < ENERGY_IDENTITY_RELATIVE_LIMIT,
        "physical": physical,
        "bounds": minimum_bound_distance > 1.0e-6,
        "jacobian": bool(
            all(item["rank"] == dimension for item in step_results)
            and all(item["condition"] < CONDITION_LIMIT for item in step_results)
            and all(item["zero_rows"] == 0 for item in step_results)
            and all(item["zero_columns"] == 0 for item in step_results)
            and spectrum_change < SPECTRUM_CHANGE_LIMIT
            and matrix_change < MATRIX_CHANGE_LIMIT
        ),
        "provider": provider_pass,
        "calls": history_audit.record_count + audit.record_count < CALL_LIMIT,
        "wall": wall < WALL_LIMIT_SEC,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": "core-v3-water-methanol-vtpr-small-feed-step-v1",
        "classification": (
            "fixed_product_small_feed_step_passed"
            if passed
            else "fixed_product_small_feed_step_failed"
        ),
        "decision": (
            "authorize_separately_bounded_short_fixed_product_trajectory"
            if passed
            else "stop_and_correct_small_disturbance_step"
        ),
        "sources": {
            str(SOURCE_ROOT).replace("\\", "/"): _sha256(root_path),
            str(SOURCE_ZERO_TIME).replace("\\", "/"): _sha256(zero_path),
            str(SOURCE_HOLD).replace("\\", "/"): _sha256(hold_path),
            str(SOURCE_HOLD_MATRIX).replace("\\", "/"): _sha256(hold_matrix_path),
        },
        "component_specific_logic": False,
        "handoff_mode": "fixed_terminal_products",
        "timestep_sec": TIMESTEP_SEC,
        "dimension": dimension,
        "solver": {
            "success": bool(solution.success),
            "status": int(solution.status),
            "message": str(solution.message),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "observed": counters,
        },
        "scaled_residual_inf_norm": residual_norm,
        "maximum_coordinate_movement": movement,
        "maximum_inventory_rate_lbmolph": maximum_rate,
        "maximum_inventory_change_lbmol": maximum_inventory_change,
        "maximum_temperature_change_F": maximum_temperature_change,
        "maximum_pressure_change_psia": maximum_pressure_change,
        "maximum_flow_relative_change": maximum_flow_relative_change,
        "minimum_bound_distance": minimum_bound_distance,
        "component_inventory_identity_error_lbmol": component_identity,
        "energy_inventory_identity_error_BTU": energy_identity,
        "energy_inventory_identity_relative_error": energy_identity_relative,
        "actual_component_change_lbmol": [float(value) for value in actual_component],
        "expected_component_change_lbmol": [float(value) for value in expected_component],
        "total_component_change_lbmol": total_component_change,
        "expected_total_component_change_lbmol": expected_total_component_change,
        "actual_energy_change_BTU": actual_energy,
        "expected_energy_change_BTU": expected_energy,
        "disturbance": {
            "kind": "uniform_feed_rate_multiplier",
            "feed_multiplier": FEED_MULTIPLIER,
            "feed_composition_max_change": composition_change,
            "feed_specific_enthalpy_change_BTU_per_lbmol": specific_enthalpy_change,
            "terminal_product_flows_fixed": True,
            "condenser_duty_mode": "solved_column_variable",
        },
        "physical_pass": physical,
        "endpoint_jacobian": {
            "steps": step_results,
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_change": matrix_change,
            "pass_gate": gates["jacobian"],
        },
        "provider": {
            "history": history_report,
            "step": provider_report,
            "total_calls": history_audit.record_count + audit.record_count,
            "pass_gate": provider_pass,
        },
        "gates": gates,
        "wall_clock_sec": wall,
        "retry_attempted": False,
        "disturbance_applied": True,
        "timestep_accepted": passed,
        "dynamic_trajectory_attempted": False,
        "pass_gate": passed,
    }
    evidence = {
        "coordinates": solution.x,
        "scaled_residual": final.scaled,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": pattern,
        "liquid_component_inventory_lbmol": final.endpoint.liquid_component_inventory_lbmol,
        "vapor_component_inventory_lbmol": final.endpoint.vapor_component_inventory_lbmol,
        "total_stored_energy_BTU": final.properties.total_stored_energy_BTU,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["endpoint_jacobian"]["steps"]
    return "\n".join(
        (
            "# Core V3 water-methanol small feed step",
            "",
            f"- Result: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Accepted timestep: `{report['timestep_sec']} s`",
            f"- Residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Maximum coordinate movement: `{report['maximum_coordinate_movement']:.6e}`",
            f"- Maximum inventory rate: `{report['maximum_inventory_rate_lbmolph']:.6e} lbmol/h`",
            f"- Total inventory change: `{report['total_component_change_lbmol']:.6e} lbmol`",
            f"- Largest temperature/pressure changes: `{report['maximum_temperature_change_F']:.6e} F / {report['maximum_pressure_change_psia']:.6e} psia`",
            f"- Component/energy identity errors: `{report['component_inventory_identity_error_lbmol']:.6e} lbmol / {report['energy_inventory_identity_relative_error']:.6e} relative`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- Matrix step change: `{report['endpoint_jacobian']['matrix_relative_change']:.6e}`",
            f"- Feed multiplier: `{report['disturbance']['feed_multiplier']}`",
            "- Retry: `False`",
            "",
            "The fixed-product column gives a bounded, conservative response to a uniform feed-rate increase. Feed composition and specific enthalpy are unchanged.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    report, evidence = execute()
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    matrix_path = _rooted(args.matrix)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    np.savez_compressed(matrix_path, **evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "scaled_residual_inf_norm": report["scaled_residual_inf_norm"],
                "maximum_coordinate_movement": report["maximum_coordinate_movement"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
