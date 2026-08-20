#!/usr/bin/env python
"""Run the single frozen DD-265 controlled vapor-holdup hold step."""

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

import run_core_v3_vapor_holdup_stationary_hold as dd248  # noqa: E402
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
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_implicit_residual_v1 import (  # noqa: E402
    controlled_implicit_initial_coordinates,
    evaluate_vapor_holdup_terminal_control_implicit_residual,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_zero_time_v1 import (  # noqa: E402
    vapor_holdup_terminal_control_pattern,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)


SOURCE_ZERO_TIME = Path(
    "logs/dd264_core_v3_c3c4_vapor_holdup_terminal_control_zero_time_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd265_core_v3_c3c4_vapor_holdup_terminal_control_hold_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_265_core_v3_c3c4_vapor_holdup_terminal_control_hold_20260820.md"
)
DEFAULT_MATRIX = Path(
    "logs/dd265_core_v3_c3c4_vapor_holdup_terminal_control_hold_20260820.npz"
)
TIMESTEP_SEC = 0.25
DIFFERENCE_STEP = 1.0e-5
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_LIMIT = 1.0e-8
CONTROLLER_RESIDUAL_LIMIT = 1.0e-10
CONDITION_LIMIT = 1.0e8
SPECTRUM_LIMIT = 0.25
MATRIX_LIMIT = 0.05
COMPONENT_IDENTITY_LIMIT_LBMOL = 1.0e-6
ENERGY_IDENTITY_LIMIT = 1.0e-8
PRODUCT_RELATIVE_MOVEMENT_LIMIT = 1.0e-3
TEMPERATURE_MOVEMENT_LIMIT_F = 1.0e-2
PRESSURE_MOVEMENT_LIMIT_PSIA = 1.0e-2
FLOW_RELATIVE_MOVEMENT_LIMIT = 1.0e-3
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


def _relative_max(left: np.ndarray, right: np.ndarray) -> float:
    return float(
        np.max(np.abs(left - right) / np.maximum(np.abs(right), 1.0))
    )


def _bounds(contract) -> tuple[np.ndarray, np.ndarray]:
    dimension = len(contract.rows)
    lower = np.full(dimension, -0.1)
    upper = np.full(dimension, 0.1)
    base_rate_count = len(contract.base.derivative_variables)
    base_algebraic_count = len(contract.base.algebraic_variables)
    lower[:base_rate_count] = -0.01
    upper[:base_rate_count] = 0.01
    base_algebraic_start = base_rate_count + 2
    tight_algebraic_start = base_algebraic_start + 100
    base_algebraic_stop = base_algebraic_start + base_algebraic_count
    lower[tight_algebraic_start:base_algebraic_stop] = -0.01
    upper[tight_algebraic_start:base_algebraic_stop] = 0.01
    lower[base_algebraic_stop:] = -0.01
    upper[base_algebraic_stop:] = 0.01
    return lower, upper


def _physical(evaluation) -> bool:
    endpoint = evaluation.base.endpoint
    return bool(
        np.all(endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(endpoint.temperature_F > -459.67)
        and np.all(endpoint.pressure_psia > 0.0)
        and np.all(np.diff(endpoint.pressure_psia) >= 0.0)
        and np.all(np.diff(endpoint.temperature_F) >= 0.0)
        and np.all(endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(endpoint.vapor_flow_lbmolph > 0.0)
        and endpoint.condenser_duty_BTUph < 0.0
        and np.min(evaluation.base.properties.free_volume.free_vapor_volume_ft3)
        > 0.0
        and np.all((evaluation.level_fraction > 0.01) & (evaluation.level_fraction < 0.99))
    )


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    problem = dd248._problem()
    zero_time = json.loads((ROOT / SOURCE_ZERO_TIME).read_text(encoding="utf-8"))
    if not zero_time.get("pass_gate"):
        raise RuntimeError("DD-265 requires the accepted DD-264 handoff")
    case = load_case_from_excel(str(problem["source"]["workbook"]))
    base_contract = build_vapor_holdup_dae_contract(
        problem["contract"].component_names,
        topology=problem["contract"].topology,
    )
    contract = build_vapor_holdup_terminal_control_contract(
        base_contract,
        geometry=terminal_geometry_from_specs(case.specs),
        controllers=level_controllers_from_specs(case.specs),
    )
    numerical = replace(problem["numerical"], timestep_sec=TIMESTEP_SEC)
    initial = zero_time["bumpless_initialization"]
    memory_previous = np.asarray(initial["controller_memory"], dtype=float)
    rate_predictor = np.asarray(initial["controller_rate_per_sec"], dtype=float)
    point = controlled_implicit_initial_coordinates(
        contract,
        controller_rates_per_sec=rate_predictor,
        timestep_sec=TIMESTEP_SEC,
    )
    lower, upper = _bounds(contract)
    pattern = vapor_holdup_terminal_control_pattern(contract)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    counters = {"function": 0, "jacobian": 0}

    def objective(candidate: np.ndarray, state_id: str = "solver") -> np.ndarray:
        counters["function"] += 1
        return evaluate_vapor_holdup_terminal_control_implicit_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            problem["balance_inputs"],
            problem["spec"].hydraulic_geometry,
            numerical,
            provider,
            audit,
            candidate,
            controller_memory_previous=memory_previous,
            state_id=f"dd265:{state_id}:{counters['function']}",
            evaluation_kind="jacobian",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        counters["jacobian"] += 1
        matrix, _groups = colored_central_difference_jacobian(
            objective,
            candidate,
            pattern=pattern,
            step=DIFFERENCE_STEP,
            state_id=f"dd265:solver_jacobian:{counters['jacobian']}",
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
    final = evaluate_vapor_holdup_terminal_control_implicit_residual(
        contract,
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        numerical,
        provider,
        audit,
        solution.x,
        controller_memory_previous=memory_previous,
        state_id="dd265:accepted_candidate",
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
            state_id=f"dd265:endpoint:h={step:.1e}",
        )
        rank, condition, singular = _rank_condition(matrix)
        matrices.append(matrix)
        step_results.append(
            {
                "step": step,
                "rank": rank,
                "condition": condition,
                "singular_values": singular.tolist(),
                "color_count": len(groups),
                "zero_rows": int(
                    np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)
                ),
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
    endpoint = final.base.endpoint
    reference = problem["reference"]
    initial_levels = np.asarray(
        (
            zero_time["terminal_levels"]["reflux_drum_fraction"],
            zero_time["terminal_levels"]["bottom_sump_fraction"],
        ),
        dtype=float,
    )
    source_products = np.asarray(
        (
            float(problem["balance_inputs"].distillate_lbmolph),
            float(problem["balance_inputs"].bottoms_lbmolph),
        )
    )
    endpoint_products = np.asarray(
        (final.distillate_lbmolph, final.bottoms_lbmolph)
    )
    product_relative_change = endpoint_products / source_products - 1.0
    actual_component = np.sum(
        endpoint.liquid_component_inventory_lbmol
        + endpoint.vapor_component_inventory_lbmol
        - reference.liquid_component_inventory_lbmol
        - reference.vapor_component_inventory_lbmol,
        axis=0,
    )
    expected_component = (
        final.base.transport.external_component_rate_lbmolph
        * (TIMESTEP_SEC / 3600.0)
    )
    actual_energy = float(
        np.sum(final.base.properties.total_stored_energy_BTU - reference.total_stored_energy_BTU)
    )
    expected_energy = float(
        final.base.transport.external_energy_rate_BTUph * (TIMESTEP_SEC / 3600.0)
    )
    energy_scale = max(abs(actual_energy), abs(expected_energy), 1.0)
    component_identity = float(np.max(np.abs(actual_component - expected_component)))
    energy_identity = abs(actual_energy - expected_energy) / energy_scale
    temperature_movement = float(
        np.max(np.abs(endpoint.temperature_F - reference.temperature_F))
    )
    pressure_movement = float(
        np.max(np.abs(endpoint.pressure_psia - reference.pressure_psia))
    )
    liquid_flow_movement = _relative_max(
        endpoint.hydraulic_liquid_flow_lbmolph,
        reference.hydraulic_liquid_flow_lbmolph,
    )
    vapor_flow_movement = _relative_max(
        endpoint.vapor_flow_lbmolph,
        reference.vapor_flow_lbmolph,
    )
    controller_residual = float(np.max(np.abs(final.scaled[-4:])))
    residual_norm = float(np.max(np.abs(final.scaled)))
    provider_report = compact_provider_report(audit.report())
    wall = time.perf_counter() - started
    gates = {
        "solver": bool(solution.success),
        "residual": residual_norm < RESIDUAL_LIMIT,
        "controller_residual": controller_residual < CONTROLLER_RESIDUAL_LIMIT,
        "physical": _physical(final),
        "distillate_direction": final.distillate_lbmolph < source_products[0],
        "bottoms_direction": final.bottoms_lbmolph > source_products[1],
        "drum_level_direction": final.level_fraction[0] > initial_levels[0],
        "sump_level_direction": final.level_fraction[1] < initial_levels[1],
        "product_movement": float(np.max(np.abs(product_relative_change)))
        < PRODUCT_RELATIVE_MOVEMENT_LIMIT,
        "temperature_movement": temperature_movement < TEMPERATURE_MOVEMENT_LIMIT_F,
        "pressure_movement": pressure_movement < PRESSURE_MOVEMENT_LIMIT_PSIA,
        "liquid_flow_movement": liquid_flow_movement < FLOW_RELATIVE_MOVEMENT_LIMIT,
        "vapor_flow_movement": vapor_flow_movement < FLOW_RELATIVE_MOVEMENT_LIMIT,
        "component_identity": component_identity < COMPONENT_IDENTITY_LIMIT_LBMOL,
        "energy_identity": energy_identity < ENERGY_IDENTITY_LIMIT,
        "jacobian": bool(
            all(item["rank"] == len(contract.rows) for item in step_results)
            and all(item["condition"] < CONDITION_LIMIT for item in step_results)
            and all(item["zero_rows"] == 0 for item in step_results)
            and all(item["zero_columns"] == 0 for item in step_results)
            and spectrum_change < SPECTRUM_LIMIT
            and matrix_change < MATRIX_LIMIT
        ),
        "provider": bool(
            provider_report["pass"] and not provider_report["fallback_attempted"]
        ),
        "calls": audit.record_count < CALL_LIMIT,
        "wall": wall < WALL_LIMIT_SEC,
    }
    gates = {key: bool(value) for key, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": "dd265-core-v3-c3c4-vapor-holdup-terminal-control-hold-v1",
        "classification": (
            "vapor_holdup_terminal_control_hold_passed"
            if passed
            else "vapor_holdup_terminal_control_hold_failed"
        ),
        "decision": (
            "authorize_separately_frozen_short_controlled_trajectory_contract"
            if passed
            else "stop_and_correct_first_controlled_endpoint"
        ),
        "timestep_sec": TIMESTEP_SEC,
        "dimension": len(contract.rows),
        "solver": {
            "success": bool(solution.success),
            "status": int(solution.status),
            "message": str(solution.message),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "observed": counters,
        },
        "scaled_residual_inf_norm": residual_norm,
        "controller_residual_inf_norm": controller_residual,
        "terminal": {
            "initial_level_fraction": initial_levels.tolist(),
            "endpoint_level_fraction": final.level_fraction.tolist(),
            "level_change_fraction": (final.level_fraction - initial_levels).tolist(),
            "controller_rate_per_sec": final.controller_rate_per_sec.tolist(),
            "controller_memory_previous": memory_previous.tolist(),
            "controller_memory_endpoint": final.controller_memory_endpoint.tolist(),
            "product_log_ratio": final.product_log_ratio.tolist(),
            "source_product_lbmolph": source_products.tolist(),
            "endpoint_product_lbmolph": endpoint_products.tolist(),
            "product_relative_change": product_relative_change.tolist(),
        },
        "movement": {
            "maximum_temperature_F": temperature_movement,
            "maximum_pressure_psia": pressure_movement,
            "maximum_liquid_flow_relative": liquid_flow_movement,
            "maximum_vapor_flow_relative": vapor_flow_movement,
        },
        "conservation": {
            "actual_component_change_lbmol": actual_component.tolist(),
            "expected_component_change_lbmol": expected_component.tolist(),
            "component_identity_max_abs_lbmol": component_identity,
            "actual_energy_change_BTU": actual_energy,
            "expected_energy_change_BTU": expected_energy,
            "energy_identity_relative": energy_identity,
        },
        "endpoint_jacobian": {
            "steps": step_results,
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_change": matrix_change,
        },
        "provider": provider_report,
        "logical_provider_calls": audit.record_count,
        "wall_clock_sec": wall,
        "gates": gates,
        "prior_serialization_failure": True,
        "retry_attempted": True,
        "alternate_setting_attempted": False,
        "timestep_accepted": passed,
        "trajectory_attempted": False,
        "pass_gate": passed,
    }
    evidence = {
        "endpoint_coordinates": solution.x,
        "scaled_residual": final.scaled,
        "controller_memory_previous": memory_previous,
        "controller_memory_endpoint": final.controller_memory_endpoint,
        "terminal_level_fraction": final.level_fraction,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    terminal = report["terminal"]
    movement = report["movement"]
    conservation = report["conservation"]
    first, second = report["endpoint_jacobian"]["steps"]
    return "\n".join(
        (
            "# DD-265 Vapor-Holdup Terminal-Control Hold",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Evaluated endpoint: `{report['timestep_sec']} s`",
            f"- Residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Controller residual maximum: `{report['controller_residual_inf_norm']:.6e}`",
            f"- Drum level, initial to endpoint: `{terminal['initial_level_fraction'][0]:.9f}` to `{terminal['endpoint_level_fraction'][0]:.9f}`",
            f"- Sump level, initial to endpoint: `{terminal['initial_level_fraction'][1]:.9f}` to `{terminal['endpoint_level_fraction'][1]:.9f}`",
            f"- Distillate, initial to endpoint: `{terminal['source_product_lbmolph'][0]:.6f}` to `{terminal['endpoint_product_lbmolph'][0]:.6f} lbmol/h`",
            f"- Bottoms, initial to endpoint: `{terminal['source_product_lbmolph'][1]:.6f}` to `{terminal['endpoint_product_lbmolph'][1]:.6f} lbmol/h`",
            f"- Maximum temperature movement: `{movement['maximum_temperature_F']:.6e} F`",
            f"- Maximum pressure movement: `{movement['maximum_pressure_psia']:.6e} psia`",
            f"- Component identity error: `{conservation['component_identity_max_abs_lbmol']:.6e} lbmol`",
            f"- Energy identity error: `{conservation['energy_identity_relative']:.6e}`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- DWSIM calls: `{report['logical_provider_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            "- Serialization recovery execution: `True`",
            "- Alternate numerical setting or trajectory: `False`",
            "",
            "The first controlled endpoint is intentionally not motionless. The drum is below setpoint, so distillate begins to decrease and drum level begins to rise. The sump is above setpoint, so bottoms begins to increase and sump level begins to fall. All changes must remain small and smooth.",
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
                "terminal": report["terminal"],
                "failed_gates": [
                    key for key, value in report["gates"].items() if not value
                ],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
