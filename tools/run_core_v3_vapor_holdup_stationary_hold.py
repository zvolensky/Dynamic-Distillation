#!/usr/bin/env python
"""Run the single frozen DD-248 stationary vapor-holdup hold step."""

from __future__ import annotations

import argparse
from dataclasses import replace
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
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)


SOURCE_ROOT = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.json"
)
SOURCE_ZERO_MOTION = Path(
    "logs/dd247_core_v3_c3c4_vapor_holdup_zero_motion_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd248_core_v3_c3c4_vapor_holdup_stationary_hold_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_248_core_v3_c3c4_vapor_holdup_stationary_hold_20260820.md"
)
DEFAULT_MATRIX = Path(
    "logs/dd248_core_v3_c3c4_vapor_holdup_stationary_hold_20260820.npz"
)
TIMESTEP_SEC = 0.25
DIFFERENCE_STEP = 1.0e-5
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_LIMIT = 1.0e-8
MOVEMENT_LIMIT = 1.0e-8
RATE_LIMIT_LBMOLPH = 1.0e-5
CONDITION_LIMIT = 1.0e8
CALL_LIMIT = 100000
WALL_LIMIT_SEC = 180.0


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(
        float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30
    )
    return float(np.linalg.norm(left - right) / denominator)


def _problem() -> dict[str, Any]:
    root = json.loads((ROOT / SOURCE_ROOT).read_text(encoding="utf-8"))
    zero_motion = json.loads(
        (ROOT / SOURCE_ZERO_MOTION).read_text(encoding="utf-8")
    )
    if not root.get("pass_gate") or not zero_motion.get("pass_gate"):
        raise RuntimeError("DD-248 requires accepted DD-245/DD-247 evidence")
    base = dd243.build_problem()
    endpoint = root["endpoint"]
    liquid_inventory = np.asarray(
        endpoint["liquid_component_inventory_lbmol"], dtype=float
    )
    vapor_inventory = np.asarray(
        endpoint["vapor_component_inventory_lbmol"], dtype=float
    )
    phase_transfer = np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float)
    stationary_numerical = base["numerical"]
    contract = build_vapor_holdup_dae_contract(
        base["contract"].component_names,
        topology=base["contract"].topology,
        product_flow_parameters=("D_dd245_root", "B_dd245_root"),
    )
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=vapor_inventory,
        phase_transfer_lbmolph=phase_transfer,
        phase_transfer_scale_lbmolph=np.maximum(
            np.abs(phase_transfer),
            stationary_numerical.component_residual_scale_lbmolph,
        ),
        temperature_F=np.asarray(endpoint["temperature_F"], dtype=float),
        pressure_psia=np.asarray(endpoint["pressure_psia"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            endpoint["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(endpoint["vapor_flow_lbmolph"], dtype=float),
        condenser_duty_BTUph=float(endpoint["condenser_duty_BTUph"]),
        total_stored_energy_BTU=np.asarray(
            zero_motion["energy_history"]["current_total_energy_BTU"], dtype=float
        ),
    )
    balance_inputs = replace(
        base["balance_inputs"],
        distillate_lbmolph=float(endpoint["distillate_lbmolph"]),
        bottoms_lbmolph=float(endpoint["bottoms_lbmolph"]),
        condenser_duty_BTUph=float(endpoint["condenser_duty_BTUph"]),
    )
    numerical = VaporHoldupImplicitNumericalSpec(
        timestep_sec=TIMESTEP_SEC,
        temperature_coordinate_scale_F=(
            stationary_numerical.temperature_coordinate_scale_F
        ),
        pressure_coordinate_scale_psia=(
            stationary_numerical.pressure_coordinate_scale_psia
        ),
        dry_tray_pressure_drop_coefficient=(
            stationary_numerical.dry_tray_pressure_drop_coefficient
        ),
        component_mw_lbm_per_lbmol=(
            stationary_numerical.component_mw_lbm_per_lbmol
        ),
        pressure_link_geometry=stationary_numerical.pressure_link_geometry,
        top_pressure_anchor_psia=float(reference.pressure_psia[0]),
        component_residual_scale_lbmolph=(
            stationary_numerical.component_residual_scale_lbmolph
        ),
        energy_residual_scale_BTUph=(
            stationary_numerical.energy_residual_scale_BTUph
        ),
        pressure_residual_scale_psia=(
            stationary_numerical.pressure_residual_scale_psia
        ),
    )
    return {
        **base,
        "contract": contract,
        "reference": reference,
        "balance_inputs": balance_inputs,
        "numerical": numerical,
    }


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    problem = _problem()
    contract = problem["contract"]
    dimension = 258
    point = np.zeros(dimension)
    lower = np.full(dimension, -0.1)
    upper = np.full(dimension, 0.1)
    lower[:120] = -0.01
    upper[:120] = 0.01
    lower[220:] = -0.01
    upper[220:] = 0.01
    pattern = vapor_holdup_structural_pattern(contract)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    function_calls = 0
    jacobian_calls = 0

    def objective(candidate: np.ndarray, state_id: str = "solver") -> np.ndarray:
        nonlocal function_calls
        function_calls += 1
        return evaluate_vapor_holdup_implicit_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            candidate,
            state_id=f"dd248:{state_id}:{function_calls}",
            evaluation_kind="jacobian",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal jacobian_calls
        jacobian_calls += 1
        matrix, _groups = colored_central_difference_jacobian(
            objective,
            candidate,
            pattern=pattern,
            step=DIFFERENCE_STEP,
            state_id=f"dd248:solver_jacobian:{jacobian_calls}",
        )
        return matrix

    solution = least_squares(
        objective,
        point,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=1.0,
        ftol=1.0e-11,
        xtol=1.0e-11,
        gtol=1.0e-11,
        max_nfev=20,
        verbose=0,
    )
    final = evaluate_vapor_holdup_implicit_residual(
        contract,
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        provider,
        audit,
        solution.x,
        state_id="dd248:accepted_candidate",
        evaluation_kind="residual",
    )
    matrices: list[np.ndarray] = []
    step_results: list[dict[str, Any]] = []
    for step in ENDPOINT_STEPS:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            solution.x,
            pattern=pattern,
            step=step,
            state_id=f"dd248:endpoint:h={step:.1e}",
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
            }
        )
    spectrum_change = _relative_change(
        np.asarray(step_results[0]["singular_values"]),
        np.asarray(step_results[1]["singular_values"]),
    )
    matrix_change = _relative_change(matrices[0], matrices[1])
    wall = time.perf_counter() - started
    residual_norm = float(np.max(np.abs(final.scaled)))
    movement = float(np.max(np.abs(solution.x)))
    maximum_rate = float(
        max(
            np.max(np.abs(final.endpoint.liquid_component_rate_lbmolph)),
            np.max(np.abs(final.endpoint.vapor_component_rate_lbmolph)),
        )
    )
    provider_report = compact_provider_report(audit.report())
    passed = bool(
        solution.success
        and residual_norm < RESIDUAL_LIMIT
        and movement < MOVEMENT_LIMIT
        and maximum_rate < RATE_LIMIT_LBMOLPH
        and all(item["rank"] == dimension for item in step_results)
        and all(item["condition"] < CONDITION_LIMIT for item in step_results)
        and spectrum_change < 0.25
        and matrix_change < 0.05
        and provider_report["pass"]
        and not provider_report["fallback_attempted"]
        and audit.record_count < CALL_LIMIT
        and wall < WALL_LIMIT_SEC
    )
    report = {
        "schema_id": "dd248-core-v3-c3c4-vapor-holdup-stationary-hold-v1",
        "classification": (
            "vapor_holdup_stationary_hold_passed"
            if passed
            else "vapor_holdup_stationary_hold_failed"
        ),
        "timestep_sec": TIMESTEP_SEC,
        "solver": {
            "success": bool(solution.success),
            "status": int(solution.status),
            "message": str(solution.message),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "function_calls_observed": function_calls,
            "jacobian_calls_observed": jacobian_calls,
        },
        "scaled_residual_inf_norm": residual_norm,
        "maximum_coordinate_movement": movement,
        "maximum_inventory_rate_lbmolph": maximum_rate,
        "endpoint_coordinates": solution.x.tolist(),
        "endpoint_jacobian": {
            "steps": step_results,
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_change": matrix_change,
        },
        "provider": provider_report,
        "logical_provider_calls": audit.record_count,
        "wall_clock_sec": wall,
        "retry_attempted": False,
        "disturbance_applied": False,
        "timestep_accepted": passed,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_one_small_moving_step_contract"
            if passed
            else "stop_vapor_holdup_dynamic_work"
        ),
    }
    evidence = {
        "coordinates": solution.x,
        "scaled_residual": final.scaled,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["endpoint_jacobian"]["steps"]
    return "\n".join(
        (
            "# DD-248 Vapor-Holdup Stationary Hold",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Accepted timestep: `{report['timestep_sec']} s`",
            f"- Residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Maximum coordinate movement: `{report['maximum_coordinate_movement']:.6e}`",
            f"- Maximum inventory rate: `{report['maximum_inventory_rate_lbmolph']:.6e} lbmol/h`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- Provider calls: `{report['logical_provider_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            "- Retry or disturbance: `False`",
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
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
