#!/usr/bin/env python
"""Execute the single frozen DD-245 stationary vapor-holdup root campaign."""

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

import audit_core_v3_vapor_holdup_stationary_residual as dd243  # noqa: E402

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


DEFAULT_CONTRACT = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_contract_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.md"
)
DEFAULT_MATRIX = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.npz"
)
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_sha(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(
        float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30
    )
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
    """Replace per-state grouped records with exact route-level totals."""
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
    compact["grouped_record_summary"] = [
        grouped[key] for key in sorted(grouped)
    ]
    if sum(item["call_count"] for item in compact["grouped_record_summary"]) != int(
        compact["total_calls"]
    ):
        raise RuntimeError("provider report compaction changed the call total")
    return compact


def _load_and_validate_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    expected = contract.pop("contract_payload_sha256")
    actual = _payload_sha(contract)
    contract["contract_payload_sha256"] = expected
    if actual != expected:
        raise RuntimeError("DD-245 contract payload checksum changed")
    for key in ("source_residual", "source_jacobian", "source_matrix"):
        if _sha256(ROOT / contract[key]) != contract[f"{key}_sha256"]:
            raise RuntimeError(f"DD-245 {key} evidence changed")
    for relative, expected_hash in contract["implementation_sha256"].items():
        if _sha256(ROOT / relative) != expected_hash:
            raise RuntimeError(f"DD-245 implementation changed: {relative}")
    return contract


def execute(contract_path: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    contract_payload = _load_and_validate_contract(contract_path)
    settings = contract_payload["solver"]
    limits = contract_payload["acceptance"]
    started = time.perf_counter()
    problem = dd243.build_problem()
    model_contract = problem["contract"]
    variable_names = stationary_variable_names(model_contract)
    if list(variable_names) != contract_payload["variable_names"]:
        raise RuntimeError("DD-245 variable ledger changed")
    dimension = len(variable_names)
    start = np.asarray(contract_payload["start"], dtype=float)
    lower = np.asarray(contract_payload["lower_bounds"], dtype=float)
    upper = np.asarray(contract_payload["upper_bounds"], dtype=float)
    coordinate_scale = np.asarray(
        contract_payload["coordinate_scale"], dtype=float
    )
    if any(array.shape != (dimension,) for array in (start, lower, upper, coordinate_scale)):
        raise RuntimeError("DD-245 frozen coordinate arrays are invalid")
    pattern = stationary_structural_pattern(model_contract)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    evaluation_counter = 0
    jacobian_counter = 0

    def objective(candidate: np.ndarray, label: str = "solver") -> np.ndarray:
        nonlocal evaluation_counter
        evaluation_counter += 1
        return evaluate_vapor_holdup_stationary_residual(
            model_contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            candidate,
            state_id=f"dd245:{label}:{evaluation_counter}",
            evaluation_kind="jacobian" if label != "final" else "residual",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal jacobian_counter
        jacobian_counter += 1
        matrix, _groups = colored_central_difference_jacobian(
            lambda point, state_id: objective(point, state_id),
            candidate,
            pattern=pattern,
            step=float(settings["difference_step"]),
            state_id=f"dd245:solver_jacobian:{jacobian_counter}",
        )
        return matrix

    solution = least_squares(
        lambda point: objective(point),
        start,
        jac=jacobian,
        bounds=(lower, upper),
        method=settings["method"],
        x_scale=coordinate_scale,
        ftol=float(settings["ftol"]),
        xtol=float(settings["xtol"]),
        gtol=float(settings["gtol"]),
        max_nfev=int(settings["max_nfev"]),
        verbose=0,
    )
    final_evaluation = evaluate_vapor_holdup_stationary_residual(
        model_contract,
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        provider,
        audit,
        solution.x,
        state_id="dd245:final_endpoint",
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
                state_id=f"dd245:endpoint:h={step:.1e}",
            )
            rank, condition, singular = _rank_condition(matrix)
            endpoint_matrices.append(matrix)
            endpoint_results.append(
                {
                    "step": step,
                    "rank": rank,
                    "condition": condition,
                    "singular_values": [float(value) for value in singular],
                    "zero_rows": int(
                        np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)
                    ),
                    "zero_columns": int(
                        np.count_nonzero(np.linalg.norm(matrix, axis=0) <= 1.0e-12)
                    ),
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
    pressure_ordered = bool(np.all(np.diff(endpoint.pressure_psia) > 0.0))
    bound_distance = float(
        np.min(np.minimum(solution.x - lower, upper - solution.x))
    )
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
    terminal_max = float(
        np.max(np.abs(final_evaluation.terminal_inventory_residual_lbmol))
    )
    eos_max = float(
        np.max(np.abs(final_evaluation.properties.eos_relative_residual))
    )
    fugacity_max = float(np.max(np.abs(final_evaluation.fugacity_residual)))
    endpoint_jacobian_pass = bool(
        len(endpoint_results) == 2
        and all(item["rank"] == int(limits["endpoint_rank"]) for item in endpoint_results)
        and all(item["condition"] < limits["endpoint_condition"] for item in endpoint_results)
        and all(item["zero_rows"] == 0 for item in endpoint_results)
        and all(item["zero_columns"] == 0 for item in endpoint_results)
        and spectrum_change < limits["endpoint_spectrum_relative_change"]
        and matrix_change < limits["endpoint_matrix_relative_change"]
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
        np.max(
            np.abs(
                final_evaluation.balances.global_component_telescoping_error_lbmolph
            )
        )
        < 1.0e-9
        and abs(final_evaluation.balances.global_energy_telescoping_error_BTUph)
        < 1.0e-5
    )
    passed = bool(
        solution.success
        and final_norm < limits["scaled_residual_inf_norm"]
        and component_max < limits["component_balance_lbmolph"]
        and energy_max < limits["energy_balance_BTUph"]
        and pressure_max < limits["pressure_residual_psia"]
        and terminal_max < limits["terminal_inventory_residual_lbmol"]
        and eos_max < limits["relative_eos_residual"]
        and fugacity_max < limits["fugacity_residual"]
        and bound_distance > limits["minimum_bound_distance"]
        and endpoint_jacobian_pass
        and physical_pass
        and conservation_pass
        and provider_report["pass"]
        and not provider_report["fallback_attempted"]
        and audit.record_count < limits["logical_provider_calls"]
        and wall < limits["wall_clock_sec"]
    )
    memo = (
        provider.get_exact_state_memoization_stats()
        if hasattr(provider, "get_exact_state_memoization_stats")
        else {}
    )
    report = {
        "schema_id": "dd245-core-v3-c3c4-vapor-holdup-stationary-root-v1",
        "classification": (
            "stationary_vapor_holdup_root_accepted"
            if passed
            else "stationary_vapor_holdup_root_rejected"
        ),
        "contract": str(contract_path.relative_to(ROOT)).replace("\\", "/"),
        "contract_payload_sha256": contract_payload["contract_payload_sha256"],
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
            "coordinates": solution.x.tolist(),
            "maximum_coordinate_movement": float(np.max(np.abs(solution.x))),
            "minimum_bound_distance": bound_distance,
            "liquid_component_inventory_lbmol": (
                endpoint.liquid_component_inventory_lbmol.tolist()
            ),
            "vapor_component_inventory_lbmol": (
                endpoint.vapor_component_inventory_lbmol.tolist()
            ),
            "phase_transfer_lbmolph": endpoint.phase_transfer_lbmolph.tolist(),
            "temperature_F": endpoint.temperature_F.tolist(),
            "pressure_psia": endpoint.pressure_psia.tolist(),
            "hydraulic_liquid_flow_lbmolph": (
                endpoint.hydraulic_liquid_flow_lbmolph.tolist()
            ),
            "vapor_flow_lbmolph": endpoint.vapor_flow_lbmolph.tolist(),
            "condenser_duty_BTUph": endpoint.condenser_duty_BTUph,
            "distillate_lbmolph": endpoint.distillate_lbmolph,
            "bottoms_lbmolph": endpoint.bottoms_lbmolph,
            "top_liquid_inventory_lbmol": float(
                np.sum(endpoint.liquid_component_inventory_lbmol[0])
            ),
            "bottom_liquid_inventory_lbmol": float(
                np.sum(endpoint.liquid_component_inventory_lbmol[-1])
            ),
            "total_liquid_inventory_lbmol": float(
                np.sum(endpoint.liquid_component_inventory_lbmol)
            ),
            "total_vapor_inventory_lbmol": float(
                np.sum(endpoint.vapor_component_inventory_lbmol)
            ),
            "minimum_free_vapor_volume_ft3": float(
                np.min(final_evaluation.properties.free_volume.free_vapor_volume_ft3)
            ),
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
            "authorize_stationary_dynamic_handoff_contract"
            if passed
            else "stop_stationary_vapor_holdup_nonlinear_work"
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
    jacobian = report["endpoint_jacobian"]
    conditions = [item["condition"] for item in jacobian["steps"]]
    return "\n".join(
        (
            "# DD-245 Stationary Vapor-Holdup Root",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Solver success: `{solver['success']}`",
            f"- Function/Jacobian evaluations: `{solver['nfev']} / {solver['njev']}`",
            f"- Scaled residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            (
                "- Endpoint conditions: `"
                + " / ".join(f"{value:.6e}" for value in conditions)
                + "`"
                if conditions
                else "- Endpoint Jacobian: `not evaluated`"
            ),
            f"- D/B: `{endpoint['distillate_lbmolph']:.6f} / {endpoint['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Qc: `{endpoint['condenser_duty_BTUph'] / 1.0e6:.6f} MMBTU/h`",
            f"- Total liquid/vapor inventory: `{endpoint['total_liquid_inventory_lbmol']:.6f} / {endpoint['total_vapor_inventory_lbmol']:.6f} lbmol`",
            f"- Logical provider calls: `{report['logical_provider_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            "- Retry, continuation, timestep, or integration: `False`",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    report, evidence = execute(ROOT / args.contract)
    json_path = ROOT / args.json
    doc_path = ROOT / args.doc
    matrix_path = ROOT / args.matrix
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
                "wall_clock_sec": report["wall_clock_sec"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
