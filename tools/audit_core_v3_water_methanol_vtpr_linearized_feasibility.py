#!/usr/bin/env python
"""Audit full-system linearized feasibility at the rejected VTPR endpoint."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import run_core_v3_water_methanol_stationary_root as stationary_root  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.stationary_closure_audit_v1 import (  # noqa: E402
    aggregate_residual_block_gradient,
    find_active_coordinate_bounds,
    linearized_closure_correction,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
    stationary_structural_pattern,
)


DEFAULT_SOURCE = Path(
    "logs/core_v3_water_methanol_vtpr_density_stationary_root_20260831.json"
)
DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_vtpr_linearized_feasibility_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_vtpr_linearized_feasibility_20260831.md"
)
DEFAULT_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_linearized_feasibility_20260831.npz"
)
STEPS = (1.0e-5, 5.0e-6)
CONDITION_LIMIT = 1.0e8
MATRIX_CHANGE_LIMIT = 0.05
CORRECTION_CHANGE_LIMIT = 0.05


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30)
    return float(np.linalg.norm(left - right) / denominator)


def _block_sensitivity_summary(
    contract: Any,
    coordinates: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    residual: np.ndarray,
    jacobian: np.ndarray,
    energy_gradient: np.ndarray,
    global_energy_residual: float,
) -> list[dict[str, Any]]:
    by_block: dict[str, list[dict[str, Any]]] = {}
    threshold = max(float(np.max(np.abs(energy_gradient))) * 1.0e-12, 1.0e-12)
    for index, variable in enumerate(contract.variables):
        derivative = float(energy_gradient[index])
        if abs(derivative) <= threshold:
            continue
        correction = -float(global_energy_residual) / derivative
        target = float(coordinates[index] + correction)
        within_bounds = bool(lower[index] <= target <= upper[index])
        predicted = residual + jacobian[:, index] * correction
        item = {
            "index": index,
            "variable": variable.name,
            "block": variable.block,
            "raw_global_energy_derivative_BTUph_per_coordinate": derivative,
            "single_variable_energy_closure_correction": correction,
            "target_coordinate": target,
            "within_bounds": within_bounds,
            "predicted_scaled_residual_inf_norm": float(np.max(np.abs(predicted))),
            "predicted_least_squares_cost": float(0.5 * np.dot(predicted, predicted)),
        }
        by_block.setdefault(variable.block, []).append(item)

    summaries = []
    for block, items in sorted(by_block.items()):
        feasible = [item for item in items if item["within_bounds"]]
        ranked = sorted(
            feasible or items,
            key=lambda item: item["predicted_least_squares_cost"],
        )
        summaries.append(
            {
                "block": block,
                "sensitive_variable_count": len(items),
                "within_bounds_count": len(feasible),
                "maximum_absolute_energy_derivative_BTUph_per_coordinate": max(
                    abs(item["raw_global_energy_derivative_BTUph_per_coordinate"])
                    for item in items
                ),
                "best_single_variable_candidate": ranked[0],
            }
        )
    return summaries


def execute(
    source: Path = DEFAULT_SOURCE,
    *,
    bound_policy: str = "component_reference",
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    source_path = _rooted(source).resolve()
    saved = json.loads(source_path.read_text(encoding="utf-8"))
    if saved.get("classification") != "stationary_root_rejected":
        raise RuntimeError("linearized audit requires a rejected stationary endpoint")
    density_model = saved.get("density_model")
    coordinates = np.asarray(saved["endpoint"]["coordinates"], dtype=float)
    problem = starting_state.build_problem(density_model=density_model)
    contract = problem["contract"]
    dimension = len(contract.variables)
    if coordinates.shape != (dimension,):
        raise RuntimeError("saved endpoint does not match the current variable ledger")
    lower, upper = stationary_root._bounds(
        contract,
        problem["reference"],
        policy=bound_policy,
    )
    active = find_active_coordinate_bounds(
        contract.variables,
        coordinates,
        lower,
        upper,
    )
    pattern = stationary_structural_pattern(contract)
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    def evaluate(point: np.ndarray, state_id: str) -> Any:
        return evaluate_vapor_holdup_stationary_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            point,
            state_id=state_id,
            evaluation_kind="jacobian",
        )

    base = evaluate(coordinates, "linearized_feasibility:base")
    if not np.isclose(
        np.max(np.abs(base.scaled)),
        float(saved["scaled_residual_inf_norm"]),
        rtol=1.0e-10,
        atol=1.0e-12,
    ):
        raise RuntimeError("saved endpoint residual was not reproduced")

    started = time.perf_counter()
    matrices = []
    corrections = []
    step_results = []
    energy_gradients = []
    global_energy_residual = float(np.sum(base.balances.energy_residual_BTUph))
    for step in STEPS:
        matrix, groups = colored_central_difference_jacobian(
            lambda point, state_id: evaluate(point, state_id).scaled,
            coordinates,
            pattern=pattern,
            step=step,
            state_id=f"linearized_feasibility:h={step:.1e}",
        )
        correction = linearized_closure_correction(
            contract.variables,
            coordinates,
            lower,
            upper,
            base.scaled,
            matrix,
        )
        gradient = aggregate_residual_block_gradient(
            contract.rows,
            matrix,
            base.scales,
            block="total_energy_balance",
        )
        matrices.append(matrix)
        corrections.append(np.asarray([item.correction for item in correction.movements]))
        energy_gradients.append(gradient)
        violations = [
            asdict(item) for item in correction.movements if item.bound_violation
        ]
        outward_active = []
        active_by_index = {item.index: item for item in active}
        for movement in correction.movements:
            finding = active_by_index.get(movement.index)
            if finding is None:
                continue
            outward = (
                finding.side == "upper" and movement.correction > 0.0
            ) or (
                finding.side == "lower" and movement.correction < 0.0
            )
            if outward:
                outward_active.append(asdict(movement))
        step_results.append(
            {
                "step": step,
                "color_count": len(groups),
                "rank": correction.rank,
                "condition": correction.condition,
                "correction_l2_norm": correction.correction_l2_norm,
                "correction_inf_norm": correction.correction_inf_norm,
                "predicted_residual_inf_norm": correction.predicted_residual_inf_norm,
                "maximum_feasible_step_fraction": (
                    correction.maximum_feasible_step_fraction
                ),
                "bound_violation_count": len(violations),
                "bound_violations": sorted(
                    violations,
                    key=lambda item: item["bound_overshoot"],
                    reverse=True,
                ),
                "active_bounds_with_outward_correction": outward_active,
            }
        )

    matrix_change = _relative_change(matrices[0], matrices[1])
    correction_change = _relative_change(corrections[0], corrections[1])
    energy_gradient_change = _relative_change(energy_gradients[0], energy_gradients[1])
    derivative_gate = bool(
        all(item["rank"] == dimension for item in step_results)
        and all(item["condition"] < CONDITION_LIMIT for item in step_results)
        and matrix_change < MATRIX_CHANGE_LIMIT
        and correction_change < CORRECTION_CHANGE_LIMIT
        and not audit.fallback_attempted
    )
    active_bound_conflict = bool(
        derivative_gate
        and all(item["active_bounds_with_outward_correction"] for item in step_results)
    )
    coordinated_bound_conflict = bool(
        derivative_gate
        and all(item["bound_violation_count"] > 0 for item in step_results)
    )
    sensitivity = _block_sensitivity_summary(
        contract,
        coordinates,
        lower,
        upper,
        base.scaled,
        matrices[0],
        energy_gradients[0],
        global_energy_residual,
    )
    wall = time.perf_counter() - started
    provider_report = stationary_root.compact_provider_report(audit.report())
    passed = bool(derivative_gate and provider_report["pass"])
    report = {
        "schema_id": "core-v3-stationary-linearized-feasibility-audit-v1",
        "classification": (
            "coordinated_closure_conflicts_with_active_generic_bound"
            if active_bound_conflict
            else "linearized_full_closure_outside_generic_bounds"
            if coordinated_bound_conflict
            else "linearized_full_closure_within_generic_bounds"
            if derivative_gate
            else "linearized_feasibility_derivatives_unreliable"
        ),
        "source_root_result": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "component_specific_logic": False,
        "dimension": dimension,
        "density_model": density_model,
        "bound_policy": bound_policy,
        "base_scaled_residual_inf_norm": float(np.max(np.abs(base.scaled))),
        "base_least_squares_cost": float(0.5 * np.dot(base.scaled, base.scaled)),
        "global_energy_residual_BTUph": global_energy_residual,
        "active_coordinate_bounds": [asdict(item) for item in active],
        "step_results": step_results,
        "matrix_relative_change": matrix_change,
        "correction_relative_change": correction_change,
        "global_energy_gradient_relative_change": energy_gradient_change,
        "energy_sensitivity_by_variable_block": sensitivity,
        "limits": {
            "condition": CONDITION_LIMIT,
            "matrix_relative_change": MATRIX_CHANGE_LIMIT,
            "correction_relative_change": CORRECTION_CHANGE_LIMIT,
        },
        "derivative_gate_pass": derivative_gate,
        "active_bound_conflict": active_bound_conflict,
        "coordinated_bound_conflict": coordinated_bound_conflict,
        "provider": provider_report,
        "logical_provider_calls": audit.record_count,
        "wall_clock_sec": wall,
        "nonlinear_solve_attempted": False,
        "bounds_changed": False,
        "equations_changed": False,
        "timestep_attempted": False,
        "pass_gate": passed,
        "decision": (
            "review_generic_bound_construction_before_any_second_solve"
            if coordinated_bound_conflict
            else "authorize_one_bounded_stationary_solve"
            if derivative_gate
            else "stop_before_model_or_bound_changes"
        ),
    }
    evidence = {
        "coordinates": coordinates,
        "scaled_residual": base.scaled,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "newton_correction_h1": corrections[0],
        "newton_correction_h2": corrections[1],
        "global_energy_gradient_h1": energy_gradients[0],
        "global_energy_gradient_h2": energy_gradients[1],
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["step_results"]
    active = report["active_coordinate_bounds"]
    active_text = ", ".join(item["variable"] for item in active) or "none"
    return "\n".join(
        (
            "# Core V3 linearized stationary feasibility audit",
            "",
            f"- Finding: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Active bounds: `{active_text}`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- Matrix step change: `{report['matrix_relative_change']:.6e}`",
            f"- Newton-correction step change: `{report['correction_relative_change']:.6e}`",
            f"- Feasible Newton fraction: `{first['maximum_feasible_step_fraction']:.6e} / {second['maximum_feasible_step_fraction']:.6e}`",
            f"- Global energy residual: `{report['global_energy_residual_BTUph']:.6e} BTU/h`",
            f"- Component-specific logic: `{report['component_specific_logic']}`",
            "- Nonlinear solve, bound change, equation change, or timestep: `False`",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument(
        "--bound-policy",
        choices=("component_reference", "phase_total"),
        default="component_reference",
    )
    args = parser.parse_args()
    report, evidence = execute(args.source, bound_policy=args.bound_policy)
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
                "matrix_relative_change": report["matrix_relative_change"],
                "correction_relative_change": report["correction_relative_change"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
