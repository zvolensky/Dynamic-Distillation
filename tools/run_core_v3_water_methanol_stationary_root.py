#!/usr/bin/env python
"""Run one bounded Core V3 stationary solve for the water-methanol case."""

from __future__ import annotations

import argparse
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
import audit_core_v3_water_methanol_stationary_jacobian as source_jacobian  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
    stationary_structural_pattern,
    stationary_variable_names,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_bounds_v1 import (  # noqa: E402
    vapor_holdup_stationary_coordinate_bounds,
)


DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_stationary_root_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_stationary_root_20260831.md"
)
DEFAULT_EVIDENCE = Path(
    "logs/core_v3_water_methanol_stationary_root_20260831.npz"
)
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)
SETTINGS = {
    "method": "trf",
    "difference_step": 1.0e-5,
    "ftol": 1.0e-11,
    "xtol": 1.0e-11,
    "gtol": 1.0e-11,
    "max_nfev": 120,
}
LIMITS = {
    "scaled_residual_inf_norm": 1.0e-8,
    "endpoint_condition": 1.0e8,
    "endpoint_spectrum_relative_change": 0.25,
    "endpoint_matrix_relative_change": 0.05,
    "relative_eos_residual": 1.0e-10,
    "fugacity_residual": 1.0e-8,
    "component_balance_lbmolph": 1.0e-6,
    "energy_balance_BTUph": 1.0e-3,
    "pressure_residual_psia": 1.0e-8,
    "terminal_inventory_residual_lbmol": 1.0e-8,
    "minimum_bound_distance": 1.0e-6,
    "logical_provider_calls": 1_000_000,
    "wall_clock_sec": 600.0,
}


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


def compact_provider_report(report: dict[str, Any]) -> dict[str, Any]:
    compact = dict(report)
    records = compact.pop("grouped_records", [])
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record["provider_interface"]),
            str(record["evaluation_kind"]),
            str(record["quantity"]),
        )
        item = grouped.setdefault(
            key,
            {
                "provider_interface": key[0],
                "evaluation_kind": key[1],
                "quantity": key[2],
                "group_count": 0,
                "call_count": 0,
            },
        )
        item["group_count"] += 1
        item["call_count"] += int(record["count"])
    compact["grouped_record_summary"] = [grouped[key] for key in sorted(grouped)]
    if sum(item["call_count"] for item in compact["grouped_record_summary"]) != int(
        compact["total_calls"]
    ):
        raise RuntimeError("provider report compaction changed the call total")
    return compact


def _bounds(
    contract: Any,
    reference: Any | None = None,
    *,
    policy: str = "component_reference",
) -> tuple[np.ndarray, np.ndarray]:
    if policy == "phase_total":
        if reference is None:
            raise ValueError("phase-total bounds require the stationary reference")
        return vapor_holdup_stationary_coordinate_bounds(contract, reference)
    if policy != "component_reference":
        raise ValueError(f"unknown stationary bound policy {policy!r}")
    lower = np.empty(len(contract.variables), dtype=float)
    upper = np.empty(len(contract.variables), dtype=float)
    for index, variable in enumerate(contract.variables):
        if variable.block in {
            "liquid_component_inventory",
            "vapor_component_inventory",
        }:
            lower[index], upper[index] = np.log(0.1), np.log(10.0)
        elif variable.block == "interphase_component_transfer":
            lower[index], upper[index] = -5.0, 5.0
        elif variable.block == "temperature":
            lower[index], upper[index] = -5.0, 5.0
        elif variable.block == "pressure":
            lower[index], upper[index] = -20.0, 20.0
        elif variable.block in {
            "francis_liquid_flow",
            "pressure_driven_vapor_flow",
        }:
            lower[index], upper[index] = np.log(0.2), np.log(5.0)
        elif variable.block in {
            "solved_condenser_duty",
            "terminal_level_product_flow",
        }:
            lower[index], upper[index] = np.log(0.5), np.log(1.5)
        else:
            raise RuntimeError(f"no stationary bound rule for {variable.block!r}")
    return lower, upper


def _load_jacobian_evidence(
    report_path: Path,
    matrix_path: Path,
    *,
    density_model: str | None,
) -> tuple[dict[str, Any], Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not report.get("pass_gate") or report.get("dimension") != 100:
        raise RuntimeError("stationary solve requires the passing water-methanol Jacobian")
    if report.get("density_model") != density_model:
        raise RuntimeError("stationary solve density model does not match the Jacobian audit")
    matrices = np.load(matrix_path)
    return report, matrices


def _coordinate_scale(matrices: Any) -> np.ndarray:
    norm_h1 = np.linalg.norm(matrices["jacobian_h1"], axis=0)
    norm_h2 = np.linalg.norm(matrices["jacobian_h2"], axis=0)
    geometric_norm = np.sqrt(norm_h1 * norm_h2)
    scale = 1.0 / np.maximum(geometric_norm, 1.0e-30)
    return scale / np.median(scale)


def execute(
    *,
    density_model: str | None = None,
    source_jacobian_json: Path | None = None,
    source_jacobian_matrix: Path | None = None,
    bound_policy: str = "component_reference",
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    jacobian_report_path = _rooted(
        source_jacobian_json or source_jacobian.DEFAULT_JSON
    ).resolve()
    jacobian_matrix_path = _rooted(
        source_jacobian_matrix or source_jacobian.DEFAULT_MATRIX
    ).resolve()
    jacobian_report, source_matrices = _load_jacobian_evidence(
        jacobian_report_path,
        jacobian_matrix_path,
        density_model=density_model,
    )
    problem = starting_state.build_problem(density_model=density_model)
    contract = problem["contract"]
    variable_names = stationary_variable_names(contract)
    dimension = len(variable_names)
    if dimension != jacobian_report["dimension"]:
        raise RuntimeError("stationary variable ledger changed after the Jacobian audit")
    start = np.zeros(dimension)
    lower, upper = _bounds(
        contract,
        problem["reference"],
        policy=bound_policy,
    )
    coordinate_scale = _coordinate_scale(source_matrices)
    pattern = stationary_structural_pattern(contract)
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    evaluation_counter = 0
    jacobian_counter = 0

    def objective(candidate: np.ndarray, label: str = "solver") -> np.ndarray:
        nonlocal evaluation_counter
        evaluation_counter += 1
        return evaluate_vapor_holdup_stationary_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            candidate,
            state_id=f"water_methanol:{label}:{evaluation_counter}",
            evaluation_kind="jacobian" if label != "final" else "residual",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal jacobian_counter
        jacobian_counter += 1
        matrix, _groups = colored_central_difference_jacobian(
            lambda point, state_id: objective(point, state_id),
            candidate,
            pattern=pattern,
            step=float(SETTINGS["difference_step"]),
            state_id=f"water_methanol:solver_jacobian:{jacobian_counter}",
        )
        return matrix

    started = time.perf_counter()
    solution = least_squares(
        lambda point: objective(point),
        start,
        jac=jacobian,
        bounds=(lower, upper),
        method=str(SETTINGS["method"]),
        x_scale=coordinate_scale,
        ftol=float(SETTINGS["ftol"]),
        xtol=float(SETTINGS["xtol"]),
        gtol=float(SETTINGS["gtol"]),
        max_nfev=int(SETTINGS["max_nfev"]),
        verbose=0,
    )
    final_evaluation = evaluate_vapor_holdup_stationary_residual(
        contract,
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        provider,
        audit,
        solution.x,
        state_id="water_methanol:final",
        evaluation_kind="residual",
    )
    final_norm = float(np.max(np.abs(final_evaluation.scaled)))

    endpoint_matrices: list[np.ndarray] = []
    endpoint_results: list[dict[str, Any]] = []
    if final_norm < 1.0e-6:
        for step in ENDPOINT_STEPS:
            matrix, _groups = colored_central_difference_jacobian(
                lambda point, state_id: objective(point, state_id),
                solution.x,
                pattern=pattern,
                step=step,
                state_id=f"water_methanol:endpoint:h={step:.1e}",
            )
            rank, condition, singular = _rank_condition(matrix)
            endpoint_matrices.append(matrix)
            endpoint_results.append(
                {
                    "step": step,
                    "rank": rank,
                    "condition": condition,
                    "singular_values": [float(value) for value in singular],
                    "zero_rows": int(np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)),
                    "zero_columns": int(np.count_nonzero(np.linalg.norm(matrix, axis=0) <= 1.0e-12)),
                }
            )
    spectrum_change = np.inf
    matrix_change = np.inf
    if len(endpoint_matrices) == 2:
        spectrum_change = _relative_change(
            np.asarray(endpoint_results[0]["singular_values"]),
            np.asarray(endpoint_results[1]["singular_values"]),
        )
        matrix_change = _relative_change(endpoint_matrices[0], endpoint_matrices[1])

    endpoint = final_evaluation.endpoint
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    vapor_y = endpoint.vapor_component_inventory_lbmol / np.sum(
        endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
    )
    pressure_ordered = bool(np.all(np.diff(endpoint.pressure_psia) > 0.0))
    bound_distance = float(np.min(np.minimum(solution.x - lower, upper - solution.x)))
    component_max = float(
        max(
            np.max(np.abs(final_evaluation.balances.liquid_component_residual_lbmolph)),
            np.max(np.abs(final_evaluation.balances.vapor_component_residual_lbmolph)),
        )
    )
    energy_max = float(np.max(np.abs(final_evaluation.balances.energy_residual_BTUph)))
    pressure_max = float(
        max(
            np.max(np.abs(final_evaluation.pressure_drop.residual_psia)),
            abs(final_evaluation.pressure_anchor_residual_psia),
        )
    )
    terminal_max = float(np.max(np.abs(final_evaluation.terminal_inventory_residual_lbmol)))
    eos_max = float(np.max(np.abs(final_evaluation.properties.eos_relative_residual)))
    fugacity_max = float(np.max(np.abs(final_evaluation.fugacity_residual)))
    endpoint_jacobian_pass = bool(
        len(endpoint_results) == 2
        and all(item["rank"] == dimension for item in endpoint_results)
        and all(item["condition"] < LIMITS["endpoint_condition"] for item in endpoint_results)
        and all(item["zero_rows"] == 0 for item in endpoint_results)
        and all(item["zero_columns"] == 0 for item in endpoint_results)
        and spectrum_change < LIMITS["endpoint_spectrum_relative_change"]
        and matrix_change < LIMITS["endpoint_matrix_relative_change"]
    )
    wall = time.perf_counter() - started
    provider_report = compact_provider_report(audit.report())
    physical_pass = bool(
        np.all(endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(endpoint.vapor_flow_lbmolph > 0.0)
        and np.all(final_evaluation.properties.free_volume.free_vapor_volume_ft3 > 0.0)
        and endpoint.condenser_duty_BTUph < 0.0
        and endpoint.distillate_lbmolph > 0.0
        and endpoint.bottoms_lbmolph > 0.0
        and pressure_ordered
    )
    conservation_pass = bool(
        np.max(np.abs(final_evaluation.balances.global_component_telescoping_error_lbmolph))
        < 1.0e-9
        and abs(final_evaluation.balances.global_energy_telescoping_error_BTUph) < 1.0e-5
    )
    passed = bool(
        solution.success
        and final_norm < LIMITS["scaled_residual_inf_norm"]
        and component_max < LIMITS["component_balance_lbmolph"]
        and energy_max < LIMITS["energy_balance_BTUph"]
        and pressure_max < LIMITS["pressure_residual_psia"]
        and terminal_max < LIMITS["terminal_inventory_residual_lbmol"]
        and eos_max < LIMITS["relative_eos_residual"]
        and fugacity_max < LIMITS["fugacity_residual"]
        and bound_distance > LIMITS["minimum_bound_distance"]
        and endpoint_jacobian_pass
        and physical_pass
        and conservation_pass
        and provider_report["pass"]
        and not provider_report["fallback_attempted"]
        and audit.record_count < LIMITS["logical_provider_calls"]
        and wall < LIMITS["wall_clock_sec"]
    )
    memo = (
        provider.get_exact_state_memoization_stats()
        if hasattr(provider, "get_exact_state_memoization_stats")
        else {}
    )
    report = {
        "schema_id": "core-v3-water-methanol-stationary-root-v1",
        "classification": (
            "stationary_root_accepted" if passed else "stationary_root_rejected"
        ),
        "bulk_provider": "dwsim",
        "liquid_density_provider": (
            "dwsim"
            if problem["density_model"] is None
            else f"clapeyron_{problem['density_model'].lower()}"
        ),
        "density_model": problem["density_model"],
        "bound_policy": bound_policy,
        "source_jacobian": str(jacobian_report_path.relative_to(ROOT)).replace("\\", "/"),
        "source_jacobian_sha256": _sha256(jacobian_report_path),
        "source_jacobian_matrix_sha256": _sha256(jacobian_matrix_path),
        "settings": SETTINGS,
        "limits": LIMITS,
        "coordinate_scale_range": [
            float(np.min(coordinate_scale)),
            float(np.max(coordinate_scale)),
        ],
        "solver": {
            "success": bool(solution.success),
            "status": int(solution.status),
            "message": str(solution.message),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "cost": float(solution.cost),
            "optimality": float(solution.optimality),
            "function_calls_observed": evaluation_counter,
            "jacobian_calls_observed": jacobian_counter,
        },
        "scaled_residual_inf_norm": final_norm,
        "raw_block_maxima": {
            "component_balance_lbmolph": component_max,
            "energy_balance_BTUph": energy_max,
            "pressure_residual_psia": pressure_max,
            "terminal_inventory_residual_lbmol": terminal_max,
            "fugacity": fugacity_max,
            "relative_eos": eos_max,
        },
        "endpoint_jacobian": {
            "steps": endpoint_results,
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_change": matrix_change,
            "pass_gate": endpoint_jacobian_pass,
        },
        "endpoint": {
            "volume_roles": list(contract.topology.column.volume_ids),
            "component_names": list(contract.component_names),
            "coordinates": solution.x.tolist(),
            "maximum_coordinate_movement": float(np.max(np.abs(solution.x))),
            "minimum_bound_distance": bound_distance,
            "liquid_component_inventory_lbmol": endpoint.liquid_component_inventory_lbmol.tolist(),
            "vapor_component_inventory_lbmol": endpoint.vapor_component_inventory_lbmol.tolist(),
            "liquid_mole_fraction": liquid_x.tolist(),
            "vapor_mole_fraction": vapor_y.tolist(),
            "phase_transfer_lbmolph": endpoint.phase_transfer_lbmolph.tolist(),
            "temperature_F": endpoint.temperature_F.tolist(),
            "pressure_psia": endpoint.pressure_psia.tolist(),
            "hydraulic_liquid_flow_lbmolph": endpoint.hydraulic_liquid_flow_lbmolph.tolist(),
            "vapor_flow_lbmolph": endpoint.vapor_flow_lbmolph.tolist(),
            "condenser_duty_BTUph": endpoint.condenser_duty_BTUph,
            "distillate_lbmolph": endpoint.distillate_lbmolph,
            "bottoms_lbmolph": endpoint.bottoms_lbmolph,
            "top_liquid_inventory_lbmol": float(np.sum(endpoint.liquid_component_inventory_lbmol[0])),
            "bottom_liquid_inventory_lbmol": float(np.sum(endpoint.liquid_component_inventory_lbmol[-1])),
            "total_liquid_inventory_lbmol": float(np.sum(endpoint.liquid_component_inventory_lbmol)),
            "total_vapor_inventory_lbmol": float(np.sum(endpoint.vapor_component_inventory_lbmol)),
            "minimum_free_vapor_volume_ft3": float(np.min(final_evaluation.properties.free_volume.free_vapor_volume_ft3)),
            "pressure_ordered": pressure_ordered,
            "physical_pass": physical_pass,
        },
        "conservation_pass": conservation_pass,
        "provider": provider_report,
        "logical_provider_calls": audit.record_count,
        "preparation_provider_calls": problem["preparation_audit"].record_count,
        "memoization": memo,
        "wall_clock_sec": wall,
        "retry_attempted": False,
        "continuation_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "ready_for_zero_time_dynamic_handoff_audit"
            if passed
            else "stop_stationary_nonlinear_work"
        ),
    }
    evidence = {
        "coordinates": solution.x,
        "scaled_residual": final_evaluation.scaled,
        "raw_residual": final_evaluation.raw,
        "structural_pattern": pattern,
    }
    if len(endpoint_matrices) == 2:
        evidence["endpoint_jacobian_h1"] = endpoint_matrices[0]
        evidence["endpoint_jacobian_h2"] = endpoint_matrices[1]
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    solver = report["solver"]
    endpoint = report["endpoint"]
    conditions = [item["condition"] for item in report["endpoint_jacobian"]["steps"]]
    top_x = endpoint["liquid_mole_fraction"][0]
    bottom_x = endpoint["liquid_mole_fraction"][-1]
    condition_text = (
        " / ".join(f"{value:.6e}" for value in conditions)
        if conditions
        else "not evaluated because the residual remained above 1e-6"
    )
    meaning = (
        "The stationary state passed the equation, physical, conservation, and "
        "endpoint-Jacobian checks."
        if report["pass_gate"]
        else "The candidate remained physical, but it did not close the stationary "
        "equations. It was rejected and no retry was attempted."
    )
    return "\n".join(
        (
            "# Core V3 water-methanol stationary solution",
            "",
            f"- Result: `{report['classification']}`",
            f"- Next gate: `{report['decision']}`",
            f"- Solver success: `{solver['success']}`",
            f"- Liquid-density provider: `{report['liquid_density_provider']}`",
            f"- Coordinate-bound policy: `{report['bound_policy']}`",
            f"- Function/Jacobian evaluations: `{solver['nfev']} / {solver['njev']}`",
            f"- Largest scaled equation error: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Endpoint Jacobian condition: `{condition_text}`",
            f"- Distillate/bottoms: `{endpoint['distillate_lbmolph']:.6f} / {endpoint['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Condenser duty: `{endpoint['condenser_duty_BTUph'] / 1.0e6:.6f} MMBTU/h`",
            f"- Top liquid Water/Methanol: `{top_x[0]:.8f} / {top_x[1]:.8f}`",
            f"- Bottom liquid Water/Methanol: `{bottom_x[0]:.8f} / {bottom_x[1]:.8f}`",
            f"- Pressure range: `{endpoint['pressure_psia'][0]:.6f} to {endpoint['pressure_psia'][-1]:.6f} psia`",
            f"- Minimum free vapor space: `{endpoint['minimum_free_vapor_volume_ft3']:.6f} ft3`",
            f"- Live property calls: `{report['logical_provider_calls']}`",
            f"- Wall time: `{report['wall_clock_sec']:.3f} seconds`",
            "- Retry, continuation, or timestep: `False`",
            "",
            meaning,
            "",
        )
    )


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--density-model", choices=("VTPR",), default=None)
    parser.add_argument(
        "--bound-policy",
        choices=("component_reference", "phase_total"),
        default="component_reference",
    )
    parser.add_argument(
        "--source-jacobian-json",
        type=Path,
        default=source_jacobian.DEFAULT_JSON,
    )
    parser.add_argument(
        "--source-jacobian-matrix",
        type=Path,
        default=source_jacobian.DEFAULT_MATRIX,
    )
    args = parser.parse_args()
    report, evidence = execute(
        density_model=args.density_model,
        source_jacobian_json=args.source_jacobian_json,
        source_jacobian_matrix=args.source_jacobian_matrix,
        bound_policy=args.bound_policy,
    )
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    evidence_path = _rooted(args.evidence)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    np.savez_compressed(evidence_path, **evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "scaled_residual_inf_norm": report["scaled_residual_inf_norm"],
                "wall_clock_sec": report["wall_clock_sec"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
