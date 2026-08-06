#!/usr/bin/env python
"""Prepare or execute the DD-163 hybrid-fugacity root reconstruction."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_terminal_gauge_invariance as dd121
import run_core_v3_controlled_terminal_first_step as dd128
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.captured_modified_newton_v1 import (
    solve_captured_modified_newton,
)
from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    controlled_terminal_zero_time_pattern,
    evaluate_controlled_terminal_zero_time,
)
from dynamic_distillation.core_v3.hybrid_thermo_provider_v1 import (
    HybridThermoProviderV1,
)
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_backend_factory_v1 import (
    _clapeyron_dwsim_pr_userlocations,
)
from dynamic_distillation.thermo_clapeyron_provider_v1 import (
    ThermoClapeyronProviderV1,
)


SCHEMA = "dd163-core-v3-hybrid-fugacity-root-contract-v1"
RESULT_SCHEMA = "dd163-core-v3-hybrid-fugacity-root-result-v1"
DD160 = Path(
    "logs/dd160_core_v3_memoized_captured_multiminute_trajectory_contract_20260806.json"
)
DD162_CONTRACT = Path(
    "logs/dd162_core_v3_hybrid_fugacity_benchmark_contract_20260806.json"
)
DD162_RESULT = Path(
    "logs/dd162_core_v3_hybrid_fugacity_benchmark_20260806.json"
)
CONTRACT = Path(
    "logs/dd163_core_v3_hybrid_fugacity_root_reconstruction_contract_20260806.json"
)
RESULT = Path(
    "logs/dd163_core_v3_hybrid_fugacity_root_reconstruction_20260806.json"
)
CONTRACT_DOC = Path(
    "docs/dd_163_core_v3_hybrid_fugacity_root_reconstruction_contract_20260806.md"
)
RESULT_DOC = Path(
    "docs/dd_163_core_v3_hybrid_fugacity_root_reconstruction_20260806.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/captured_modified_newton_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_zero_time_v1.py",
    "src/dynamic_distillation/core_v3/hybrid_thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/thermo_clapeyron_provider_v1.py",
    "tools/run_core_v3_hybrid_fugacity_root_reconstruction.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def prepare() -> dict[str, Any]:
    dd162 = _load(DD162_RESULT)
    if (
        not dd162["pass"]
        or dd162["classification"]
        != "hybrid_fugacity_residual_jacobian_passed"
        or dd162["decision"]
        != "authorize_separately_frozen_hybrid_root_reconstruction_contract"
    ):
        raise RuntimeError("DD-163 requires the passing DD-162 authorization")
    source = _load(DD160)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD160, DD162_CONTRACT, DD162_RESULT)
        },
        "state": "exact DD-160 accepted controlled-terminal zero-time root",
        "provider_routing": {
            "direct_imposed_phase_fugacity": "clapeyron",
            "all_bulk_properties_and_tp_flash": "dwsim",
        },
        "algorithm": {
            key: source["algorithm"][key]
            for key in (
                "residual_tolerance",
                "max_iterations",
                "line_search_fractions",
                "armijo_fraction",
                "condition_limit",
            )
        },
        "jacobian_step": 1.0e-5,
        "required_rank": 50,
        "endpoint_condition_limit": 1.0e8,
        "residual_limit": 1.0e-8,
        "identity_limit": 1.0e-14,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-12,
        "engineering_equivalence_limits": {
            "temperature_F_max_abs": 0.25,
            "liquid_mole_fraction_max_abs": 5.0e-4,
            "vapor_mole_fraction_max_abs": 5.0e-4,
            "bubble_vapor_mole_fraction_max_abs": 5.0e-4,
            "pressure_psia_max_abs": 0.05,
            "liquid_flow_max_relative": 5.0e-3,
            "vapor_flow_max_relative": 5.0e-3,
            "product_flow_max_relative": 5.0e-3,
            "condenser_duty_max_relative": 5.0e-3,
            "level_fraction_max_abs": 1.0e-3,
        },
        "provider_call_limit": 12000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a source or DD-163 implementation hash changes",
            "the single frozen-Jacobian solve does not converge without retry",
            "the endpoint loses rank, exceeds the condition limit, or violates physicality",
            "the reconstructed state exceeds any frozen engineering-equivalence limit",
            "provider ownership fails or imposed-phase fugacity falls back",
            "any clipping, projection, fresh-Jacobian retry, timestep, or trajectory occurs",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-163 Frozen Hybrid Fugacity Root-Reconstruction Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Start: exact accepted DD-160 DWSIM zero-time root",
                "- Solve: one captured modified-Newton reconstruction on the hybrid basis",
                "- Jacobian: one frozen colored central difference at `1e-5`",
                "- Endpoint: independent residual/Jacobian, physicality, conservation, and engineering-equivalence audit",
                "- Retry, fallback, clipping, projection, timestep, or trajectory: prohibited",
                "",
                "Passing authorizes only integration of the hybrid provider into a separately frozen trajectory contract.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-163 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-163 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-163 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-163 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _matrix_metrics(matrix: np.ndarray) -> dict[str, Any]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    cutoff = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > cutoff))
    condition = float(np.inf if singular[-1] <= cutoff else singular[0] / singular[-1])
    return {
        "rank": rank,
        "condition": condition,
        "singular_values": singular.tolist(),
    }


def _relative(left: np.ndarray, right: np.ndarray) -> float:
    denominator = np.maximum(np.abs(left), 1.0)
    return float(np.max(np.abs(right - left) / denominator))


def _physical(evaluation: Any) -> Any:
    return evaluation.base.pressure_evaluation.base_evaluation.physical_state


def _steady(evaluation: Any) -> Any:
    return evaluation.base.pressure_evaluation.base_evaluation.steady_evaluation


def _state_comparison(reference_evaluation: Any, candidate_evaluation: Any) -> dict[str, float]:
    left = _physical(reference_evaluation)
    right = _physical(candidate_evaluation)
    left_products = np.asarray(
        (reference_evaluation.distillate_lbmolph, reference_evaluation.bottoms_lbmolph)
    )
    right_products = np.asarray(
        (candidate_evaluation.distillate_lbmolph, candidate_evaluation.bottoms_lbmolph)
    )
    return {
        "temperature_F_max_abs": float(np.max(np.abs(right.temperature_F - left.temperature_F))),
        "liquid_mole_fraction_max_abs": float(
            np.max(np.abs(right.liquid_mole_fraction - left.liquid_mole_fraction))
        ),
        "vapor_mole_fraction_max_abs": float(
            np.max(np.abs(right.vapor_mole_fraction - left.vapor_mole_fraction))
        ),
        "bubble_vapor_mole_fraction_max_abs": float(
            np.max(
                np.abs(
                    right.bubble_vapor_mole_fraction - left.bubble_vapor_mole_fraction
                )
            )
        ),
        "pressure_psia_max_abs": float(
            np.max(
                np.abs(
                    candidate_evaluation.base.pressure_evaluation.pressure_psia
                    - reference_evaluation.base.pressure_evaluation.pressure_psia
                )
            )
        ),
        "liquid_flow_max_relative": _relative(
            left.hydraulic_liquid_flow_lbmolph, right.hydraulic_liquid_flow_lbmolph
        ),
        "vapor_flow_max_relative": _relative(left.vapor_flow_lbmolph, right.vapor_flow_lbmolph),
        "product_flow_max_relative": _relative(left_products, right_products),
        "condenser_duty_max_relative": _relative(
            np.asarray((left.condenser_duty_BTUph,)),
            np.asarray((right.condenser_duty_BTUph,)),
        ),
        "level_fraction_max_abs": float(
            np.max(
                np.abs(
                    candidate_evaluation.level_fraction
                    - reference_evaluation.level_fraction
                )
            )
        ),
    }


def _capture(outcome: Any) -> list[dict[str, Any]]:
    return [
        {
            "iteration": item.iteration,
            "residual_inf_norm_before": item.residual_inf_norm_before,
            "correction_inf_norm": float(np.max(np.abs(item.correction))),
            "trials": [
                {
                    "fraction": trial.fraction,
                    "within_bounds": trial.within_bounds,
                    "residual_inf_norm": trial.residual_inf_norm,
                    "armijo_accepted": trial.armijo_accepted,
                }
                for trial in item.trials
            ],
        }
        for item in outcome.iteration_captures
    ]


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    source = _load(DD160)
    spec, reference, template, _initializer, dwsim, _audit, _numerical, common = (
        dd121._context(source)
    )
    contract = dd128._contract(source)
    pattern = controlled_terminal_zero_time_pattern(contract)
    point = np.asarray(source["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(source["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(source["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(source["controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**source["original_level_setpoints"])

    case = load_case_from_excel(source["workbook"])
    column = build_column_spec_from_case(case)
    bulk = dd121.dd102._provider(Path(source["workbook"]), source["property_package"])
    clapeyron = ThermoClapeyronProviderV1(
        column.components_excel,
        column.components_dwsim,
        model_name="PR",
        model_kwargs=_clapeyron_dwsim_pr_userlocations(column),
    )
    clapeyron.validate_backend_available()
    hybrid = HybridThermoProviderV1(fugacity_provider=clapeyron, bulk_provider=bulk)
    for provider in (dwsim, hybrid):
        setter = getattr(provider, "set_exact_state_memoization", None)
        if callable(setter):
            setter(True, clear=True)
    reference_audit = ProviderCallAudit()
    hybrid_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"direct_imposed_phase_fugacity": "clapeyron"},
    )

    def evaluate(provider, audit, candidate, state_id, evaluation_kind):
        return evaluate_controlled_terminal_zero_time(
            contract,
            spec,
            reference,
            template,
            provider,
            audit,
            inventory_lbmol=inventory,
            lower_internal_energy_BTU=lower_u,
            controller_memory=memory,
            level_setpoints=setpoints,
            solve_coordinates=candidate,
            state_id=state_id,
            evaluation_kind=evaluation_kind,
            **common,
        )

    def objective(candidate, state_id):
        kind = "jacobian" if "jacobian" in state_id else "residual"
        return evaluate(hybrid, hybrid_audit, candidate, state_id, kind)

    jacobian_records: list[dict[str, Any]] = []

    def build_jacobian(candidate, state_id):
        started = time.perf_counter()
        matrix, groups = colored_central_difference_jacobian(
            lambda trial, trial_id: objective(trial, trial_id).scaled,
            candidate,
            pattern=pattern,
            step=float(payload["jacobian_step"]),
            state_id=state_id,
        )
        jacobian_records.append(
            {
                "purpose": "solver_frozen",
                "wall_clock_sec": float(time.perf_counter() - started),
                "color_count": len(groups),
                "metrics": _matrix_metrics(matrix),
                "matrix": matrix.tolist(),
            }
        )
        return matrix

    settings = ModifiedNewtonSettings(**payload["algorithm"])
    lower = np.full(point.shape, -np.inf)
    upper = np.full(point.shape, np.inf)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    lower[-2:] = np.log(product_low)
    upper[-2:] = np.log(product_high)

    started = time.perf_counter()
    reference_evaluation = evaluate(
        dwsim, reference_audit, point, "dd163:dwsim_reference", "residual"
    )
    outcome = solve_captured_modified_newton(
        objective,
        build_jacobian,
        point,
        settings,
        lower_bounds=lower,
        upper_bounds=upper,
        name="dd163:hybrid_root",
    )
    endpoint = outcome.final_evaluation
    endpoint_matrix_started = time.perf_counter()
    endpoint_matrix, endpoint_groups = colored_central_difference_jacobian(
        lambda trial, trial_id: objective(trial, trial_id).scaled,
        outcome.final_coordinates,
        pattern=pattern,
        step=float(payload["jacobian_step"]),
        state_id="dd163:endpoint_jacobian",
    )
    endpoint_matrix_wall = time.perf_counter() - endpoint_matrix_started
    elapsed = time.perf_counter() - started

    endpoint_metrics = _matrix_metrics(endpoint_matrix)
    comparison = _state_comparison(reference_evaluation, endpoint)
    physical = _physical(endpoint)
    steady = _steady(endpoint)
    pressures = endpoint.base.pressure_evaluation.pressure_psia
    provenance = hybrid_audit.report()
    reference_provenance = reference_audit.report()
    limits = payload["engineering_equivalence_limits"]
    physical_gate = bool(
        np.all(physical.liquid_moles_lbmol > 0.0)
        and np.all(physical.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(physical.vapor_flow_lbmolph > 0.0)
        and np.all((physical.liquid_mole_fraction > 0.0) & (physical.liquid_mole_fraction < 1.0))
        and np.all((physical.vapor_mole_fraction > 0.0) & (physical.vapor_mole_fraction < 1.0))
        and np.all(np.diff(physical.temperature_F) > 0.0)
        and np.all(np.diff(pressures) > 0.0)
        and np.all((endpoint.level_fraction > 0.01) & (endpoint.level_fraction < 0.99))
        and physical.condenser_duty_BTUph < 0.0
    )
    gates = {
        "source_and_shape": point.shape == (50,) and endpoint.scaled.shape == (50,),
        "single_solve_converged": outcome.success
        and outcome.final_residual_inf_norm < payload["residual_limit"]
        and outcome.jacobian_evaluations == 1,
        "solver_rank_and_condition": outcome.jacobian_rank == payload["required_rank"]
        and outcome.jacobian_condition < payload["algorithm"]["condition_limit"],
        "endpoint_rank_and_condition": endpoint_metrics["rank"] == payload["required_rank"]
        and endpoint_metrics["condition"] < payload["endpoint_condition_limit"],
        "solver_evaluation_identity": outcome.final_residual_vs_evaluation_max_abs
        <= payload["identity_limit"]
        and outcome.final_coordinates_vs_evaluation_max_abs <= payload["identity_limit"],
        "engineering_equivalence": all(comparison[key] <= limits[key] for key in limits),
        "physical": physical_gate,
        "conservation": abs(steady.component_telescoping_relative_error)
        <= payload["component_conservation_limit"]
        and abs(steady.energy_telescoping_relative_error)
        <= payload["energy_conservation_limit"],
        "provider": provenance["pass"] and reference_provenance["pass"],
        "calls": provenance["total_calls"] <= payload["provider_call_limit"],
        "wall": elapsed <= payload["wall_clock_limit_sec"],
        "no_forbidden_actions": True,
    }
    passed = all(bool(value) for value in gates.values())
    if passed:
        classification = "hybrid_fugacity_root_reconstructed_and_equivalent"
        decision = "authorize_separately_frozen_hybrid_trajectory_integration_contract"
    else:
        classification = "hybrid_fugacity_root_reconstruction_failed"
        decision = "retain_dwsim_only_and_stop_hybrid_acceleration_path"
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "solver": {
            "success": outcome.success,
            "message": outcome.message,
            "iterations": outcome.iterations,
            "residual_evaluations": outcome.residual_evaluations,
            "jacobian_evaluations": outcome.jacobian_evaluations,
            "linear_solves": outcome.linear_solves,
            "accepted_steps": outcome.accepted_steps,
            "rejected_line_search_steps": outcome.rejected_line_search_steps,
            "rejected_bound_steps": outcome.rejected_bound_steps,
            "initial_residual_inf_norm": outcome.initial_residual_inf_norm,
            "final_residual_inf_norm": outcome.final_residual_inf_norm,
            "rank": outcome.jacobian_rank,
            "condition": outcome.jacobian_condition,
            "final_residual_identity_max_abs": outcome.final_residual_vs_evaluation_max_abs,
            "final_coordinate_identity_max_abs": outcome.final_coordinates_vs_evaluation_max_abs,
            "initial_coordinates": outcome.initial_coordinates.tolist(),
            "final_coordinates": outcome.final_coordinates.tolist(),
            "final_residual": outcome.final_residual.tolist(),
            "iterations_capture": _capture(outcome),
        },
        "jacobians": {
            "solver": jacobian_records[0],
            "endpoint": {
                "wall_clock_sec": float(endpoint_matrix_wall),
                "color_count": len(endpoint_groups),
                "metrics": endpoint_metrics,
                "matrix": endpoint_matrix.tolist(),
            },
        },
        "engineering_comparison_to_dwsim_root": comparison,
        "engineering_equivalence_limits": limits,
        "endpoint": {
            "temperature_F": physical.temperature_F.tolist(),
            "liquid_mole_fraction": physical.liquid_mole_fraction.tolist(),
            "vapor_mole_fraction": physical.vapor_mole_fraction.tolist(),
            "pressure_psia": pressures.tolist(),
            "liquid_flow_lbmolph": physical.hydraulic_liquid_flow_lbmolph.tolist(),
            "vapor_flow_lbmolph": physical.vapor_flow_lbmolph.tolist(),
            "distillate_lbmolph": endpoint.distillate_lbmolph,
            "bottoms_lbmolph": endpoint.bottoms_lbmolph,
            "condenser_duty_BTUph": physical.condenser_duty_BTUph,
            "level_fraction": endpoint.level_fraction.tolist(),
            "component_conservation_relative": steady.component_telescoping_relative_error,
            "energy_conservation_relative": steady.energy_telescoping_relative_error,
        },
        "provider_provenance": provenance,
        "reference_provider_provenance": reference_provenance,
        "wall_clock_sec": float(elapsed),
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(passed),
        "fresh_jacobian_retry_attempted": False,
        "fallback_attempted": False,
        "clipping_or_projection_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# DD-163 Hybrid Fugacity Root-Reconstruction Result",
        "",
        f"- Classification: `{classification}`",
        f"- Decision: `{decision}`",
        f"- Initial/final scaled residual: `{outcome.initial_residual_inf_norm:.9e}` / `{outcome.final_residual_inf_norm:.9e}`",
        f"- Iterations/residual evaluations: `{outcome.iterations}` / `{outcome.residual_evaluations}`",
        f"- Solver rank/condition: `{outcome.jacobian_rank}` / `{outcome.jacobian_condition:.9e}`",
        f"- Endpoint rank/condition: `{endpoint_metrics['rank']}` / `{endpoint_metrics['condition']:.9e}`",
        f"- Maximum temperature shift: `{comparison['temperature_F_max_abs']:.6g} F`",
        f"- Maximum liquid/vapor composition shift: `{comparison['liquid_mole_fraction_max_abs']:.6g}` / `{comparison['vapor_mole_fraction_max_abs']:.6g}`",
        f"- Maximum pressure shift: `{comparison['pressure_psia_max_abs']:.6g} psia`",
        f"- Maximum liquid/vapor flow relative shift: `{comparison['liquid_flow_max_relative']:.6g}` / `{comparison['vapor_flow_max_relative']:.6g}`",
        f"- Hybrid provider calls: `{provenance['total_calls']}`",
        f"- Wall clock: `{elapsed:.3f} s`",
        "",
        "No reconstructed endpoint was accepted as a simulation state; no timestep or trajectory advanced.",
        "",
    ]
    (ROOT / RESULT_DOC).write_text("\n".join(lines), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
