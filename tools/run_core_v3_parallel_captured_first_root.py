#!/usr/bin/env python
"""Prepare or execute DD-148 serial/parallel captured first-root integration."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
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

import audit_core_v3_captured_modified_newton as dd137
import audit_core_v3_terminal_gauge_invariance as dd121
import benchmark_core_v3_parallel_dwsim_jacobian as dd147
import run_core_v3_controlled_terminal_first_step as dd128
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
from dynamic_distillation.core_v3.modified_newton_v1 import ModifiedNewtonSettings
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)


SCHEMA = "dd148-core-v3-parallel-captured-first-root-contract-v1"
RESULT_SCHEMA = "dd148-core-v3-parallel-captured-first-root-result-v1"
DD146_RESULT = Path(
    "logs/dd146_core_v3_longer_post_cachefix_captured_trajectory_20260805.json"
)
DD147_CONTRACT = Path(
    "logs/dd147_core_v3_parallel_dwsim_jacobian_benchmark_contract_20260805.json"
)
DD147_RESULT = Path(
    "logs/dd147_core_v3_parallel_dwsim_jacobian_benchmark_20260805.json"
)
CONTRACT = Path(
    "logs/dd148_core_v3_parallel_captured_first_root_contract_20260805.json"
)
RESULT = Path("logs/dd148_core_v3_parallel_captured_first_root_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_148_core_v3_parallel_captured_first_root_contract_20260805.md"
)
RESULT_DOC = Path("docs/dd_148_core_v3_parallel_captured_first_root_20260805.md")
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd147.IMPLEMENTATION,
            "src/dynamic_distillation/core_v3/captured_modified_newton_v1.py",
            "tests/test_core_v3_captured_modified_newton_v1.py",
            "tests/test_core_v3_parallel_colored_jacobian_v1.py",
            "tools/audit_core_v3_captured_modified_newton.py",
            "tools/run_core_v3_parallel_captured_first_root.py",
        )
    )
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
    prior_contract = _load(DD147_CONTRACT)
    prior_result = _load(DD147_RESULT)
    dd146_result = _load(DD146_RESULT)
    if (
        not prior_result["pass"]
        or prior_result["decision"]
        != "authorize_parallel_colored_jacobian_integration_contract"
        or not dd146_result["pass"]
    ):
        raise RuntimeError("DD-148 requires immutable passing DD-146/DD-147 decisions")
    payload = {
        key: value
        for key, value in prior_contract.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "source_contract_payload_sha256",
            "source_dd146_result_sha256",
            "implementation_sha256",
            "hard_stops",
            "contract_payload_sha256",
            "live_property_evaluation_attempted",
            "nonlinear_solve_attempted",
            "timestep_attempted",
            "dynamic_integration_attempted",
            "campaign_executed",
        }
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD146_RESULT, DD147_CONTRACT, DD147_RESULT)
            },
            "source_contract_payload_sha256": prior_contract[
                "contract_payload_sha256"
            ],
            "source_dd147_result_sha256": _sha(ROOT / DD147_RESULT),
            "integration": {
                "root": "DD-146 first coarse implicit root",
                "worker_count": 4,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.25,
                "serial_and_parallel_captured_solves": 2,
                "root_acceptance_or_state_advance": False,
                "matrix_absolute_limit": 0.0,
                "root_equivalence_absolute_limit": 1.0e-12,
                "dd146_reproduction_absolute_limit": 1.0e-10,
                "provider_calls_per_parallel_task": 28,
                "provider_calls_per_parallel_matrix": 1176,
                "main_provider_call_limit": 3000,
                "wall_clock_limit_sec": 180.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-146/DD-147 source or DD-148 implementation hash changes",
                "the four worker processes do not own independent DWSIM runtimes",
                "serial and parallel solvers do not use the same main-process residual path, settings, point, and bounds",
                "either captured root fails or omits immutable globalization evidence",
                "serial/parallel matrices, corrections, trials, roots, or residuals differ beyond a frozen limit",
                "the parallel root does not reproduce the accepted DD-146 first root",
                "a retry, fallback, endpoint acceptance, timestep, trajectory, clipping, or projection occurs",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-148 Frozen Parallel Captured First-Root Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Root: exact DD-146 first coarse implicit root",
                "- Solves: one serial and one four-worker parallel captured modified-Newton solve",
                "- Residual/line search: same main-process DWSIM provider and objective",
                "- Parallel work: frozen 21-color central-difference Jacobian only",
                "- Matrix equality: exact",
                "- Captured root/correction/trial equality: `<=1e-12`",
                "- DD-146 root reproduction: `<=1e-10`",
                "- Endpoint acceptance, timestep, or trajectory: prohibited",
                "- Wall-clock limit: `<180 s`",
                "",
                "Passing may authorize one separately frozen parallel captured short-trajectory contract. Failure retains the serial trajectory path.",
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
        raise RuntimeError("DD-148 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-148 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-148 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-148 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _capture_equivalence(serial, parallel) -> dict[str, Any]:
    correction_difference = 0.0
    trial_residual_difference = 0.0
    trial_coordinate_difference = 0.0
    trial_metadata_equal = len(serial.iteration_captures) == len(
        parallel.iteration_captures
    )
    if trial_metadata_equal:
        for left, right in zip(
            serial.iteration_captures,
            parallel.iteration_captures,
            strict=True,
        ):
            correction_difference = max(
                correction_difference,
                float(np.max(np.abs(left.correction - right.correction))),
            )
            trial_metadata_equal = trial_metadata_equal and len(left.trials) == len(
                right.trials
            )
            if len(left.trials) != len(right.trials):
                continue
            for left_trial, right_trial in zip(left.trials, right.trials, strict=True):
                trial_metadata_equal = trial_metadata_equal and (
                    left_trial.fraction == right_trial.fraction
                    and left_trial.within_bounds == right_trial.within_bounds
                    and left_trial.armijo_accepted == right_trial.armijo_accepted
                )
                trial_coordinate_difference = max(
                    trial_coordinate_difference,
                    float(
                        np.max(
                            np.abs(
                                left_trial.coordinates - right_trial.coordinates
                            )
                        )
                    ),
                )
                if left_trial.residual is not None and right_trial.residual is not None:
                    trial_residual_difference = max(
                        trial_residual_difference,
                        float(
                            np.max(
                                np.abs(left_trial.residual - right_trial.residual)
                            )
                        ),
                    )
                elif (left_trial.residual is None) != (right_trial.residual is None):
                    trial_metadata_equal = False
    return {
        "initial_residual_max_abs": float(
            np.max(np.abs(serial.initial_residual - parallel.initial_residual))
        ),
        "matrix_max_abs": float(
            np.max(np.abs(serial.frozen_jacobian - parallel.frozen_jacobian))
        ),
        "correction_max_abs": float(correction_difference),
        "trial_coordinate_max_abs": float(trial_coordinate_difference),
        "trial_residual_max_abs": float(trial_residual_difference),
        "final_coordinate_max_abs": float(
            np.max(np.abs(serial.final_coordinates - parallel.final_coordinates))
        ),
        "final_residual_max_abs": float(
            np.max(np.abs(serial.final_residual - parallel.final_residual))
        ),
        "trial_metadata_equal": bool(trial_metadata_equal),
        "outcome_metadata_equal": bool(
            serial.success == parallel.success
            and serial.iterations == parallel.iterations
            and serial.residual_evaluations == parallel.residual_evaluations
            and serial.jacobian_evaluations == parallel.jacobian_evaluations
            and serial.linear_solves == parallel.linear_solves
            and serial.accepted_steps == parallel.accepted_steps
            and serial.rejected_line_search_steps
            == parallel.rejected_line_search_steps
            and serial.rejected_bound_steps == parallel.rejected_bound_steps
        ),
    }


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    integration = payload["integration"]
    dd146_result = _load(DD146_RESULT)
    accepted = dd146_result["captured_trajectory_evidence"]["dd134:coarse"][0][
        "capture"
    ]
    spec, reference, template, _initializer, provider, call_audit, _numerical, common = (
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
    zero = evaluate_controlled_terminal_zero_time(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=lower_u,
        controller_memory=memory,
        level_setpoints=original_setpoints,
        solve_coordinates=point,
        state_id="dd148:main:warmup",
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

    def objective(candidate, state_id):
        return evaluate_controlled_terminal_backward_euler_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=inventory,
            previous_top_internal_energy_BTU=top_u,
            previous_lower_internal_energy_BTU=lower_u,
            previous_controller_memory=memory,
            level_setpoints=moved_setpoints,
            solve_coordinates=candidate,
            step_seconds=1.0,
            state_id=state_id,
            evaluation_kind="jacobian" if "jacobian" in state_id else "residual",
            **step_common,
        )

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
    serial_evidence: list[dict[str, Any]] = []
    parallel_evidence: list[dict[str, Any]] = []

    def serial_jacobian(candidate, state_id):
        started = time.perf_counter()
        matrix, groups = colored_central_difference_jacobian(
            lambda trial, trial_id: objective(trial, trial_id).scaled,
            candidate,
            pattern=pattern,
            step=float(payload["jacobian_step"]),
            state_id=state_id,
        )
        serial_evidence.append(
            {
                "wall_clock_sec": float(time.perf_counter() - started),
                "color_count": len(groups),
                "matrix": matrix.tolist(),
            }
        )
        return matrix

    context = mp.get_context("spawn")
    started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(integration["worker_count"]),
        mp_context=context,
        initializer=dd147._worker_initialize,
        initargs=(str((ROOT / CONTRACT).resolve()),),
    ) as pool:
        pings = [
            pool.submit(
                dd147._worker_ping, float(integration["startup_ping_delay_sec"])
            )
            for _ in range(int(integration["worker_count"]))
        ]
        process_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started

        def parallel_jacobian(candidate, state_id):
            tasks, groups = build_colored_central_difference_tasks(
                candidate,
                pattern=pattern,
                step=float(payload["jacobian_step"]),
                state_id=state_id,
            )
            jac_started = time.perf_counter()
            raw = list(pool.map(dd147._worker_evaluate, tasks, chunksize=1))
            matrix = assemble_colored_central_difference_jacobian(
                tasks,
                [
                    ColoredCentralDifferenceResult(
                        order=int(item["order"]),
                        residual=tuple(float(value) for value in item["residual"]),
                    )
                    for item in raw
                ],
                pattern=pattern,
                step=float(payload["jacobian_step"]),
            )
            parallel_evidence.append(
                {
                    "wall_clock_sec": float(time.perf_counter() - jac_started),
                    "color_count": len(groups),
                    "task_count": len(raw),
                    "task_process_ids": sorted(
                        {int(item["process_id"]) for item in raw}
                    ),
                    "provider_calls": int(
                        sum(int(item["provider_calls"]) for item in raw)
                    ),
                    "per_task_provider_calls": [
                        int(item["provider_calls"]) for item in raw
                    ],
                    "matrix": matrix.tolist(),
                }
            )
            return matrix

        serial = solve_captured_modified_newton(
            objective,
            serial_jacobian,
            point,
            settings,
            lower_bounds=lower,
            upper_bounds=upper,
            name="dd148:serial",
        )
        parallel = solve_captured_modified_newton(
            objective,
            parallel_jacobian,
            point,
            settings,
            lower_bounds=lower,
            upper_bounds=upper,
            name="dd148:parallel",
        )
    elapsed = time.perf_counter() - started

    equivalence = _capture_equivalence(serial, parallel)
    accepted_matrix = np.asarray(accepted["frozen_jacobian"], dtype=float)
    accepted_coordinates = np.asarray(accepted["final_coordinates"], dtype=float)
    accepted_residual = np.asarray(accepted["final_residual"], dtype=float)
    dd146_reproduction = {
        "matrix_max_abs": float(
            np.max(np.abs(parallel.frozen_jacobian - accepted_matrix))
        ),
        "final_coordinate_max_abs": float(
            np.max(np.abs(parallel.final_coordinates - accepted_coordinates))
        ),
        "final_residual_max_abs": float(
            np.max(np.abs(parallel.final_residual - accepted_residual))
        ),
    }
    main_provenance = call_audit.report()
    limit = float(integration["root_equivalence_absolute_limit"])
    capture_values = [
        equivalence[key]
        for key in equivalence
        if key.endswith("_max_abs")
    ]
    gates = {
        "two_captured_solves": serial.jacobian_evaluations == 1
        and parallel.jacobian_evaluations == 1,
        "both_converged": serial.success
        and parallel.success
        and serial.final_residual_inf_norm < payload["residual_limit"]
        and parallel.final_residual_inf_norm < payload["residual_limit"],
        "process_isolation": len(process_ids) == integration["worker_count"]
        and len(parallel_evidence) == 1
        and len(parallel_evidence[0]["task_process_ids"])
        == integration["worker_count"],
        "parallel_calls": parallel_evidence[0]["provider_calls"]
        == integration["provider_calls_per_parallel_matrix"]
        and all(
            value == integration["provider_calls_per_parallel_task"]
            for value in parallel_evidence[0]["per_task_provider_calls"]
        ),
        "exact_matrix_equivalence": equivalence["matrix_max_abs"]
        <= integration["matrix_absolute_limit"],
        "captured_root_equivalence": max(capture_values) <= limit
        and equivalence["trial_metadata_equal"]
        and equivalence["outcome_metadata_equal"],
        "dd146_reproduction": max(dd146_reproduction.values())
        <= integration["dd146_reproduction_absolute_limit"],
        "rank_and_condition": serial.jacobian_rank == parallel.jacobian_rank == 50
        and serial.jacobian_condition == parallel.jacobian_condition
        and parallel.jacobian_condition < payload["algorithm"]["condition_limit"],
        "residual_identity": serial.final_residual_vs_evaluation_max_abs == 0.0
        and parallel.final_residual_vs_evaluation_max_abs == 0.0,
        "complete_capture": dd137._record(serial)["all_capture_arrays_read_only"]
        and dd137._record(parallel)["all_capture_arrays_read_only"],
        "main_provider": main_provenance["pass"]
        and main_provenance["total_calls"] < integration["main_provider_call_limit"],
        "wall": elapsed < integration["wall_clock_limit_sec"],
        "no_state_acceptance_or_retry": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "parallel_captured_first_root_equivalent"
            if passed
            else "parallel_captured_first_root_integration_failed"
        ),
        "decision": (
            "authorize_separately_frozen_parallel_captured_short_trajectory_contract"
            if passed
            else "retain_serial_captured_trajectory_path"
        ),
        "serial_capture": dd137._record(serial),
        "parallel_capture": dd137._record(parallel),
        "serial_jacobian_evidence": serial_evidence,
        "parallel_jacobian_evidence": parallel_evidence,
        "worker_process_ids": process_ids,
        "pool_startup_wall_sec_raw": float(startup_raw),
        "equivalence": equivalence,
        "dd146_reproduction": dd146_reproduction,
        "main_provider_provenance": main_provenance,
        "wall_clock_sec": float(elapsed),
        "gates": gates,
        "pass": bool(passed),
        "campaign_executed_once": True,
        "root_accepted": False,
        "state_advanced": False,
        "timestep_attempted": False,
        "trajectory_attempted": False,
        "retry_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-148 Parallel Captured First-Root Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Serial/parallel Jacobian wall: `{serial_evidence[0]['wall_clock_sec']:.6f} s` / `{parallel_evidence[0]['wall_clock_sec']:.6f} s`",
                f"- Matrix difference: `{equivalence['matrix_max_abs']:.9e}`",
                f"- Final coordinate difference: `{equivalence['final_coordinate_max_abs']:.9e}`",
                f"- Final residual difference: `{equivalence['final_residual_max_abs']:.9e}`",
                f"- DD-146 reproduction: `{dd146_reproduction}`",
                f"- Pool startup: `{startup_raw:.3f} s`",
                f"- Total wall: `{elapsed:.3f} s`",
                f"- Gates: `{gates}`",
                "",
                "The root is reconstructed for integration evidence only. No endpoint is accepted and no timestep or trajectory occurs.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    output = prepare() if args.prepare else execute()
    print(
        json.dumps(
            {
                key: output[key]
                for key in output
                if key
                in {
                    "schema_id",
                    "classification",
                    "decision",
                    "contract_payload_sha256",
                    "wall_clock_sec",
                    "pass",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
