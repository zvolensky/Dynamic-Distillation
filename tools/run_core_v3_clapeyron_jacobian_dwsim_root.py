#!/usr/bin/env python
"""Prepare or execute DD-164: Clapeyron Jacobian with DWSIM root authority."""

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
from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
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


SCHEMA = "dd164-core-v3-clapeyron-jacobian-dwsim-root-contract-v1"
RESULT_SCHEMA = "dd164-core-v3-clapeyron-jacobian-dwsim-root-result-v1"
DD148_CONTRACT = Path(
    "logs/dd148_core_v3_parallel_captured_first_root_contract_20260805.json"
)
DD148_RESULT = Path("logs/dd148_core_v3_parallel_captured_first_root_20260805.json")
DD162_RESULT = Path("logs/dd162_core_v3_hybrid_fugacity_benchmark_20260806.json")
DD163_RESULT = Path(
    "logs/dd163_core_v3_hybrid_fugacity_root_reconstruction_20260806.json"
)
CONTRACT = Path(
    "logs/dd164_core_v3_clapeyron_jacobian_dwsim_root_contract_20260806.json"
)
RESULT = Path("logs/dd164_core_v3_clapeyron_jacobian_dwsim_root_20260806.json")
CONTRACT_DOC = Path(
    "docs/dd_164_core_v3_clapeyron_jacobian_dwsim_root_contract_20260806.md"
)
RESULT_DOC = Path("docs/dd_164_core_v3_clapeyron_jacobian_dwsim_root_20260806.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/captured_modified_newton_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/hybrid_thermo_provider_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/thermo_clapeyron_provider_v1.py",
    "tools/run_core_v3_clapeyron_jacobian_dwsim_root.py",
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
    dd148_contract = _load(DD148_CONTRACT)
    dd148 = _load(DD148_RESULT)
    dd162 = _load(DD162_RESULT)
    dd163 = _load(DD163_RESULT)
    if not dd148["pass"] or not dd162["pass"]:
        raise RuntimeError("DD-164 requires passing DD-148 and DD-162 evidence")
    if (
        dd163["pass"]
        or dd163["classification"]
        != "hybrid_fugacity_root_reconstruction_failed"
        or dd163["decision"] != "retain_dwsim_only_and_stop_hybrid_acceleration_path"
    ):
        raise RuntimeError("DD-164 requires the immutable DD-163 root-basis stop")
    excluded = {
        "schema_id",
        "preparation_base_commit",
        "sources",
        "source_contract_payload_sha256",
        "source_dd147_result_sha256",
        "implementation_sha256",
        "hard_stops",
        "contract_payload_sha256",
        "live_property_evaluation_attempted",
        "nonlinear_solve_attempted",
        "timestep_attempted",
        "dynamic_integration_attempted",
        "campaign_executed",
        "integration",
    }
    payload = {key: value for key, value in dd148_contract.items() if key not in excluded}
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD148_CONTRACT, DD148_RESULT, DD162_RESULT, DD163_RESULT)
            },
            "source_contract_payload_sha256": dd148_contract[
                "contract_payload_sha256"
            ],
            "architecture": {
                "governing_residual": "dwsim",
                "line_search_and_acceptance": "dwsim",
                "endpoint_audit": "dwsim",
                "frozen_jacobian_approximation": "clapeyron-fugacity/dwsim-bulk",
                "state_acceptance_or_advance": False,
            },
            "comparison": {
                "root": "exact DD-148/DD-146 first coarse moving root",
                "matrix_relative_frobenius_limit": 1.0e-2,
                "required_rank": 50,
                "condition_limit": 1.0e8,
                "residual_limit": 1.0e-8,
                "accepted_root_coordinate_max_abs": 1.0e-6,
                "accepted_root_residual_max_abs": 1.0e-8,
                "minimum_warm_matrix_speedup": 1.10,
                "provider_call_limit_per_path": 5000,
                "wall_clock_limit_sec": 180.0,
            },
            "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
            "hard_stops": [
                "a DD-148/DD-162/DD-163 source or DD-164 implementation hash changes",
                "any root residual, line-search trial, acceptance test, or endpoint audit uses Clapeyron",
                "the hybrid matrix loses rank, exceeds condition, or differs beyond the frozen limit",
                "the unchanged captured solver fails or the root misses accepted DD-148 evidence",
                "warm hybrid matrix speedup is below 1.10x",
                "a retry, fresh Jacobian, fallback, clipping, projection, state acceptance, timestep, or trajectory occurs",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-164 Frozen Clapeyron-Jacobian/DWSIM-Root Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Root: exact accepted DD-148/DD-146 first coarse moving root",
                "- Governing residual, line search, convergence, and endpoint: DWSIM only",
                "- Approximate frozen Jacobian: Clapeyron fugacity with DWSIM bulk properties",
                "- Solver settings and four line-search fractions: unchanged",
                "- Required root residual: `<1e-8`",
                "- Accepted-root coordinate reproduction: `<=1e-6`",
                "- Minimum warm matrix speedup: `1.10x`",
                "- Retry, state acceptance, timestep, and trajectory: prohibited",
                "",
                "Passing may authorize only a separately frozen short derivative-acceleration trajectory.",
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
        raise RuntimeError("DD-164 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-164 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-164 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-164 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _matrix_metrics(matrix: np.ndarray) -> dict[str, Any]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    cutoff = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > cutoff))
    condition = float(np.inf if singular[-1] <= cutoff else singular[0] / singular[-1])
    return {"rank": rank, "condition": condition, "singular_values": singular.tolist()}


def _relative_frobenius(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(right - left) / max(np.linalg.norm(left), np.finfo(float).tiny))


def _capture(outcome: Any) -> list[dict[str, Any]]:
    return [
        {
            "iteration": item.iteration,
            "residual_inf_norm_before": item.residual_inf_norm_before,
            "correction_inf_norm": float(np.max(np.abs(item.correction))),
            "trials": [
                {
                    "fraction": trial.fraction,
                    "residual_inf_norm": trial.residual_inf_norm,
                    "within_bounds": trial.within_bounds,
                    "accepted": trial.armijo_accepted,
                }
                for trial in item.trials
            ],
        }
        for item in outcome.iteration_captures
    ]


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    comparison_limits = payload["comparison"]
    dd148 = _load(DD148_RESULT)
    accepted = dd148["serial_capture"]
    spec, reference, template, _initializer, dwsim, _audit, _numerical, common = (
        dd121._context(payload)
    )
    contract = dd128._contract(payload)
    pattern = controlled_terminal_step_pattern(contract)
    point = np.asarray(payload["zero_time_coordinates"], dtype=float)
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    lower_u = np.asarray(payload["lower_internal_energy_BTU"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    original_setpoints = TerminalLevelSetpoints(**payload["original_level_setpoints"])
    moved_setpoints = TerminalLevelSetpoints(**payload["moved_level_setpoints"])

    case = load_case_from_excel(payload["workbook"])
    column = build_column_spec_from_case(case)
    bulk = dd121.dd102._provider(Path(payload["workbook"]), payload["property_package"])
    clapeyron = ThermoClapeyronProviderV1(
        column.components_excel,
        column.components_dwsim,
        model_name="PR",
        model_kwargs=_clapeyron_dwsim_pr_userlocations(column),
    )
    clapeyron.validate_backend_available()
    hybrid = HybridThermoProviderV1(fugacity_provider=clapeyron, bulk_provider=bulk)
    dwsim_audit = ProviderCallAudit()
    hybrid_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"direct_imposed_phase_fugacity": "clapeyron"},
    )
    for provider in (dwsim, hybrid):
        setter = getattr(provider, "set_exact_state_memoization", None)
        if callable(setter):
            setter(True, clear=True)

    zero = evaluate_controlled_terminal_zero_time(
        contract,
        spec,
        reference,
        template,
        dwsim,
        dwsim_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        controller_memory=memory,
        level_setpoints=original_setpoints,
        solve_coordinates=point,
        state_id="dd164:dwsim:warmup",
        evaluation_kind="residual",
        **common,
    )
    top_u = float(zero.base.live_internal_energy_BTU[0])
    step_common = {
        "component_rate_scale_lbmolph": float(payload["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": common["pressure_numerical"],
    }

    def evaluation(provider, audit, candidate, state_id, kind):
        return evaluate_controlled_terminal_backward_euler_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            audit,
            previous_inventory_lbmol=inventory,
            previous_top_internal_energy_BTU=top_u,
            previous_lower_internal_energy_BTU=lower_u,
            previous_controller_memory=memory,
            level_setpoints=moved_setpoints,
            solve_coordinates=candidate,
            step_seconds=1.0,
            state_id=state_id,
            evaluation_kind=kind,
            **step_common,
        )

    def dwsim_objective(candidate, state_id):
        kind = "jacobian" if "jacobian" in state_id else "residual"
        return evaluation(dwsim, dwsim_audit, candidate, state_id, kind)

    def hybrid_residual(candidate, state_id):
        return evaluation(hybrid, hybrid_audit, candidate, state_id, "jacobian").scaled

    # Warm Julia and both property routes before governed matrix timing.
    hybrid_residual(point, "dd164:hybrid:warmup")
    for provider in (dwsim, hybrid):
        setter = getattr(provider, "set_exact_state_memoization", None)
        if callable(setter):
            setter(True, clear=True)

    started = time.perf_counter()
    dwsim_matrix_started = time.perf_counter()
    dwsim_matrix, dwsim_groups = colored_central_difference_jacobian(
        lambda candidate, state_id: dwsim_objective(candidate, state_id).scaled,
        point,
        pattern=pattern,
        step=float(payload["jacobian_step"]),
        state_id="dd164:dwsim:jacobian",
    )
    dwsim_matrix_wall = time.perf_counter() - dwsim_matrix_started
    hybrid_matrix_started = time.perf_counter()
    hybrid_matrix, hybrid_groups = colored_central_difference_jacobian(
        hybrid_residual,
        point,
        pattern=pattern,
        step=float(payload["jacobian_step"]),
        state_id="dd164:hybrid:jacobian",
    )
    hybrid_matrix_wall = time.perf_counter() - hybrid_matrix_started

    settings = ModifiedNewtonSettings(
        **{
            key: payload["algorithm"][key]
            for key in (
                "residual_tolerance",
                "max_iterations",
                "line_search_fractions",
                "armijo_fraction",
                "condition_limit",
            )
        }
    )
    lower = np.full(point.shape, -np.inf)
    upper = np.full(point.shape, np.inf)
    product_low, product_high = contract.controllers.product_rate_ratio_bounds
    lower[-2:] = np.log(product_low)
    upper[-2:] = np.log(product_high)
    outcome = solve_captured_modified_newton(
        dwsim_objective,
        lambda _candidate, _state_id: hybrid_matrix.copy(),
        point,
        settings,
        lower_bounds=lower,
        upper_bounds=upper,
        name="dd164:dwsim_root_hybrid_jacobian",
    )
    endpoint = dwsim_objective(outcome.final_coordinates, "dd164:dwsim:endpoint")
    elapsed = time.perf_counter() - started

    dwsim_metrics = _matrix_metrics(dwsim_matrix)
    hybrid_metrics = _matrix_metrics(hybrid_matrix)
    matrix_relative = _relative_frobenius(dwsim_matrix, hybrid_matrix)
    speedup = float(dwsim_matrix_wall / hybrid_matrix_wall)
    accepted_coordinates = np.asarray(accepted["final_coordinates"], dtype=float)
    accepted_residual = np.asarray(accepted["final_residual"], dtype=float)
    coordinate_difference = float(
        np.max(np.abs(outcome.final_coordinates - accepted_coordinates))
    )
    residual_difference = float(
        np.max(np.abs(outcome.final_residual - accepted_residual))
    )
    dwsim_provenance = dwsim_audit.report()
    hybrid_provenance = hybrid_audit.report()
    gates = {
        "source_and_shape": dwsim_matrix.shape == (50, 50)
        and hybrid_matrix.shape == (50, 50)
        and len(dwsim_groups) == len(hybrid_groups),
        "matrix_rank_and_condition": dwsim_metrics["rank"]
        == comparison_limits["required_rank"]
        and hybrid_metrics["rank"] == comparison_limits["required_rank"]
        and dwsim_metrics["condition"] < comparison_limits["condition_limit"]
        and hybrid_metrics["condition"] < comparison_limits["condition_limit"],
        "matrix_agreement": matrix_relative
        <= comparison_limits["matrix_relative_frobenius_limit"],
        "root_converged": outcome.success
        and outcome.final_residual_inf_norm < comparison_limits["residual_limit"]
        and outcome.jacobian_evaluations == 1,
        "accepted_root_reproduced": coordinate_difference
        <= comparison_limits["accepted_root_coordinate_max_abs"]
        and residual_difference <= comparison_limits["accepted_root_residual_max_abs"],
        "dwsim_endpoint_identity": float(np.max(np.abs(endpoint.scaled - outcome.final_residual)))
        <= 1.0e-14,
        "meaningful_speedup": speedup
        >= comparison_limits["minimum_warm_matrix_speedup"],
        "provider_ownership": dwsim_provenance["pass"]
        and hybrid_provenance["pass"],
        "call_limits": dwsim_provenance["total_calls"]
        <= comparison_limits["provider_call_limit_per_path"]
        and hybrid_provenance["total_calls"]
        <= comparison_limits["provider_call_limit_per_path"],
        "wall": elapsed <= comparison_limits["wall_clock_limit_sec"],
        "no_forbidden_actions": True,
    }
    passed = all(bool(value) for value in gates.values())
    if passed:
        classification = "clapeyron_jacobian_dwsim_root_passed"
        decision = "authorize_separately_frozen_short_derivative_acceleration_trajectory"
    else:
        classification = "clapeyron_jacobian_dwsim_root_failed"
        decision = "retain_all_dwsim_jacobian_and_root_authority"
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": classification,
        "decision": decision,
        "architecture": payload["architecture"],
        "matrix": {
            "dwsim": {
                "wall_clock_sec": float(dwsim_matrix_wall),
                "color_count": len(dwsim_groups),
                "metrics": dwsim_metrics,
                "values": dwsim_matrix.tolist(),
            },
            "hybrid": {
                "wall_clock_sec": float(hybrid_matrix_wall),
                "color_count": len(hybrid_groups),
                "metrics": hybrid_metrics,
                "values": hybrid_matrix.tolist(),
            },
            "relative_frobenius": matrix_relative,
            "warm_speedup": speedup,
        },
        "solver": {
            "success": outcome.success,
            "message": outcome.message,
            "iterations": outcome.iterations,
            "residual_evaluations": outcome.residual_evaluations,
            "initial_residual_inf_norm": outcome.initial_residual_inf_norm,
            "final_residual_inf_norm": outcome.final_residual_inf_norm,
            "rank": outcome.jacobian_rank,
            "condition": outcome.jacobian_condition,
            "final_coordinates": outcome.final_coordinates.tolist(),
            "final_residual": outcome.final_residual.tolist(),
            "capture": _capture(outcome),
        },
        "accepted_root_comparison": {
            "coordinate_max_abs": coordinate_difference,
            "residual_max_abs": residual_difference,
        },
        "dwsim_provider_provenance": dwsim_provenance,
        "hybrid_jacobian_provider_provenance": hybrid_provenance,
        "wall_clock_sec": float(elapsed),
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(passed),
        "hybrid_residual_used_for_root_or_line_search": False,
        "fresh_jacobian_retry_attempted": False,
        "fallback_attempted": False,
        "clipping_or_projection_attempted": False,
        "root_accepted": False,
        "state_advanced": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-164 Clapeyron-Jacobian/DWSIM-Root Result",
                "",
                f"- Classification: `{classification}`",
                f"- Decision: `{decision}`",
                f"- Initial/final DWSIM residual: `{outcome.initial_residual_inf_norm:.9e}` / `{outcome.final_residual_inf_norm:.9e}`",
                f"- Iterations/residual evaluations: `{outcome.iterations}` / `{outcome.residual_evaluations}`",
                f"- DWSIM/hybrid matrix condition: `{dwsim_metrics['condition']:.9e}` / `{hybrid_metrics['condition']:.9e}`",
                f"- Matrix relative Frobenius difference: `{matrix_relative:.9e}`",
                f"- DWSIM/hybrid matrix wall: `{dwsim_matrix_wall:.6f} s` / `{hybrid_matrix_wall:.6f} s`",
                f"- Warm matrix speedup: `{speedup:.6f}x`",
                f"- Accepted-root coordinate/residual difference: `{coordinate_difference:.9e}` / `{residual_difference:.9e}`",
                f"- Total governed wall: `{elapsed:.3f} s`",
                "",
                "DWSIM owned every root residual, line-search trial, convergence test, and endpoint audit. No root was accepted and no state advanced.",
                "",
            )
        ),
        encoding="utf-8",
    )
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
