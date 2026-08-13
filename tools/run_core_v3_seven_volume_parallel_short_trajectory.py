#!/usr/bin/env python
"""Prepare or execute DD-183's persistent-parallel short trajectory proof."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing as mp
import os
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

import run_core_v3_seven_volume_parallel_first_root as dd182  # noqa: E402
import run_core_v3_seven_volume_physical_short_trajectory as dd177  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
    contract_sparsity_pattern,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    BackwardEulerEvaluation,
    component_rate_scales,
    evaluate_backward_euler_residual,
    governing_storage_vector,
    solve_backward_euler_step,
    zero_rate_evaluation,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    ColoredCentralDifferenceTask,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.short_trajectory_v1 import (  # noqa: E402
    run_short_trajectory,
)


SCHEMA = "dd183-core-v3-seven-volume-parallel-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd183-core-v3-seven-volume-parallel-short-trajectory-result-v1"
DD182_CONTRACT = Path(
    "logs/dd182_core_v3_seven_volume_parallel_first_root_contract_20260812.json"
)
DD182_RESULT = Path(
    "logs/dd182_core_v3_seven_volume_parallel_first_root_20260812.json"
)
CONTRACT = Path(
    "logs/dd183_core_v3_seven_volume_parallel_short_trajectory_contract_20260813.json"
)
RESULT = Path(
    "logs/dd183_core_v3_seven_volume_parallel_short_trajectory_20260813.json"
)
CONTRACT_DOC = Path(
    "docs/dd_183_core_v3_seven_volume_parallel_short_trajectory_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_183_core_v3_seven_volume_parallel_short_trajectory_20260813.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/short_trajectory_v1.py",
    "tests/test_core_v3_seven_volume_parallel_short_trajectory.py",
    "tools/run_core_v3_seven_volume_parallel_short_trajectory.py",
)


_WORKER_CONTEXT: dict[str, Any] | None = None


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


def _state_payload(state: Any) -> dict[str, Any]:
    return {
        "liquid_moles_lbmol": np.asarray(state.liquid_moles_lbmol).tolist(),
        "liquid_mole_fraction": np.asarray(state.liquid_mole_fraction).tolist(),
        "temperature_F": np.asarray(state.temperature_F).tolist(),
        "vapor_mole_fraction": np.asarray(state.vapor_mole_fraction).tolist(),
        "hydraulic_liquid_flow_lbmolph": np.asarray(
            state.hydraulic_liquid_flow_lbmolph
        ).tolist(),
        "vapor_flow_lbmolph": np.asarray(state.vapor_flow_lbmolph).tolist(),
        "distillate_lbmolph": float(state.distillate_lbmolph),
        "bottoms_lbmolph": float(state.bottoms_lbmolph),
        "bubble_vapor_mole_fraction": np.asarray(
            state.bubble_vapor_mole_fraction
        ).tolist(),
        "condenser_duty_BTUph": float(state.condenser_duty_BTUph),
    }


def _worker_initialize(contract_path: str) -> None:
    global _WORKER_CONTEXT
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    spec, reference, state, contract, provider, audit = dd182._context(payload)
    _WORKER_CONTEXT = {
        "spec": spec,
        "reference": reference,
        "initial_state": state,
        "contract": contract,
        "provider": provider,
        "audit": audit,
        "fixed_scales": payload["fixed_steady_residual_scales"],
        "root_epoch": None,
    }


def _worker_ping(delay_seconds: float) -> int:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-183 worker context was not initialized")
    time.sleep(float(delay_seconds))
    return int(os.getpid())


def _worker_evaluate(work: Mapping[str, Any]) -> dict[str, Any]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-183 worker context was not initialized")
    context = _WORKER_CONTEXT
    task: ColoredCentralDifferenceTask = work["task"]
    root_epoch = str(work["root_epoch"])
    provider = context["provider"]
    audit = context["audit"]
    before_records = len(audit.records)
    before_memo = provider.get_exact_state_memoization_stats()
    basis_rebuilt = context["root_epoch"] != root_epoch
    if basis_rebuilt:
        template = dd177.dd175.dd173.dd172.dd171._state(work["template_state"])
        previous = np.asarray(work["previous_inventory_lbmol"], dtype=float)
        algebraic = np.asarray(work["initial_algebraic_coordinates"], dtype=float)
        baseline = zero_rate_evaluation(
            context["contract"],
            context["spec"],
            context["reference"],
            template,
            provider,
            audit,
            inventory_lbmol=previous,
            algebraic_coordinates=algebraic,
            fixed_steady_scales=context["fixed_scales"],
            state_id=f"{root_epoch}:worker_{os.getpid()}:scale_basis",
            evaluation_kind="residual",
        )
        context.update(
            {
                "root_epoch": root_epoch,
                "template": template,
                "previous_inventory": previous,
                "previous_storage": governing_storage_vector(
                    context["spec"], baseline, previous
                ),
                "rate_scales": component_rate_scales(context["contract"], baseline),
            }
        )
    started = time.perf_counter()
    evaluation = evaluate_backward_euler_residual(
        context["contract"],
        context["spec"],
        context["reference"],
        context["template"],
        provider,
        audit,
        previous_inventory_lbmol=context["previous_inventory"],
        previous_internal_energy_BTU=context["previous_storage"],
        rate_scales_lbmolph=context["rate_scales"],
        solve_coordinates=np.asarray(task.coordinates, dtype=float),
        step_seconds=float(work["step_seconds"]),
        fixed_steady_scales=context["fixed_scales"],
        state_id=task.state_id,
        evaluation_kind="jacobian",
    )
    elapsed = time.perf_counter() - started
    after_memo = provider.get_exact_state_memoization_stats()
    return {
        "order": int(task.order),
        "residual": np.asarray(evaluation.scaled, dtype=float).tolist(),
        "process_id": int(os.getpid()),
        "root_epoch": root_epoch,
        "basis_rebuilt": bool(basis_rebuilt),
        "logical_provider_calls": int(len(audit.records) - before_records),
        "memo_hits": int(after_memo["hits"] - before_memo["hits"]),
        "memo_misses": int(after_memo["misses"] - before_memo["misses"]),
        "wall_clock_sec": float(elapsed),
    }


def _trajectory_comparison(serial: Any, parallel: Any) -> dict[str, Any]:
    if len(serial.steps) != len(parallel.steps):
        raise ValueError("trajectory step counts differ")
    steps = []
    for serial_step, parallel_step in zip(
        serial.steps, parallel.steps, strict=True
    ):
        comparison = dd182._outcome_comparison(
            serial_step.outcome, parallel_step.outcome
        )
        comparison.update(
            {
                "index_equal": serial_step.index == parallel_step.index,
                "time_equal": serial_step.time_seconds
                == parallel_step.time_seconds,
            }
        )
        steps.append(comparison)
    numeric_keys = tuple(
        key
        for key, value in steps[0].items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    boolean_keys = tuple(
        key for key, value in steps[0].items() if isinstance(value, bool)
    )
    return {
        "step_count": len(steps),
        "per_step": steps,
        "maximum_numeric_differences": {
            key: float(max(step[key] for step in steps)) for key in numeric_keys
        },
        "all_metadata_equal": all(
            all(step[key] for key in boolean_keys) for step in steps
        ),
    }


def prepare() -> dict[str, Any]:
    source = _load(DD182_CONTRACT)
    prior = _load(DD182_RESULT)
    if (
        prior.get("pass_gate") is not True
        or prior.get("decision")
        != "authorize_persistent_parallel_short_trajectory_contract"
    ):
        raise RuntimeError("DD-183 requires the passing DD-182 decision")
    duration = 4.0
    step = 0.25
    steps = int(round(duration / step))
    payload = {
        key: value
        for key, value in source.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "integration",
            "implementation_sha256",
            "hard_stops",
            "contract_payload_sha256",
            "property_evaluation_attempted",
            "nonlinear_solve_attempted",
            "timestep_attempted",
            "state_advance_attempted",
            "controller_attempted",
            "trajectory_attempted",
            "campaign_executed",
        }
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD182_CONTRACT, DD182_RESULT)
            },
            "parallel_trajectory": {
                "duration_seconds": duration,
                "step_seconds": step,
                "steps_per_path": steps,
                "serial_paths": 1,
                "parallel_paths": 1,
                "worker_count": 4,
                "persistent_pool_count": 1,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.15,
                "matrix_absolute_limit": 0.0,
                "solver_decision_limit": 0.0,
                "endpoint_absolute_limit": 1.0e-12,
                "response_relative_limit": 1.0e-6,
                "parallel_trajectory_time_ratio_limit": 0.65,
                "parallel_governed_time_ratio_limit": 0.85,
                "main_logical_provider_call_limit_each": 100_000,
                "worker_logical_provider_call_limit": 100_000,
                "wall_clock_limit_sec": 120.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-182 source or DD-183 implementation hash changes",
                "the serial and parallel paths do not use identical equations, state, disturbance, grid, scales, solver, and main-process residual ownership",
                "a worker reuses a prior root's inventory, storage, rate scales, or physical-state template",
                "any corresponding Jacobian, SciPy decision, accepted state, or endpoint differs beyond its frozen limit",
                "either path fails closure, rank, condition, physicality, conservation, response, or provider ownership",
                "the persistent parallel trajectory is not at least 35 percent faster excluding startup",
                "the parallel path including startup is not at least 15 percent faster",
                "a retry, controller, alternate grid, projection, clipping, or fallback occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "state_advance_attempted": False,
            "controller_attempted": False,
            "trajectory_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-183 Seven-Volume Persistent-Parallel Short-Trajectory Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Disturbance: unchanged `+0.1%` feed rate and enthalpy",
                "- Paths: one serial and one persistent four-worker parallel",
                f"- Grid: `{steps} x {step} s = {duration} s` per path",
                "- Equivalence: every Jacobian exact; every accepted state within `1e-12`",
                "- Performance: parallel trajectory `<=65%` serial excluding startup",
                "- Governed performance: parallel plus startup `<=85%` serial",
                "- Controller, retry, alternate grid, clipping, projection, and fallback: prohibited",
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
        raise RuntimeError("DD-183 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-183 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-183 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-183 result exists; rerun is prohibited")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    limits = payload["parallel_trajectory"]
    serial_spec, serial_ref, serial_state, contract, serial_provider, serial_audit = (
        dd182._context(payload)
    )
    parallel_spec, parallel_ref, parallel_state, pcontract, pprovider, paudit = (
        dd182._context(payload)
    )
    pattern, _names = contract_sparsity_pattern(
        contract, include_state_rate_dependencies=True
    )
    ppattern, _pnames = contract_sparsity_pattern(
        pcontract, include_state_rate_dependencies=True
    )
    if not np.array_equal(pattern, ppattern):
        raise RuntimeError("DD-183 sparsity differs between paths")
    settings = dd177.dd175.dd173.dd172._settings(payload)
    serial_matrices: list[np.ndarray] = []
    parallel_matrices: list[np.ndarray] = []
    serial_jacobian_wall: list[float] = []
    parallel_jacobian_wall: list[float] = []
    worker_evidence: list[dict[str, Any]] = []

    def serial_step_solver(*args, **kwargs):
        def builder(objective, point, state_id):
            started = time.perf_counter()
            matrix, groups = colored_central_difference_jacobian(
                objective,
                point,
                pattern=pattern,
                step=settings.jacobian_step,
                state_id=state_id,
            )
            if len(groups) != 17:
                raise RuntimeError("DD-183 serial color count changed")
            serial_jacobian_wall.append(float(time.perf_counter() - started))
            serial_matrices.append(matrix.copy())
            return matrix

        return solve_backward_euler_step(*args, **kwargs, jacobian_builder=builder)

    total_started = time.perf_counter()
    serial_started = time.perf_counter()
    serial = run_short_trajectory(
        contract,
        serial_spec,
        serial_ref,
        serial_state,
        serial_provider,
        serial_audit,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=float(limits["step_seconds"]),
        duration_seconds=float(limits["duration_seconds"]),
        settings=settings,
        name="dd183:serial",
        step_solver=serial_step_solver,
    )
    serial_wall = time.perf_counter() - serial_started

    context = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(limits["worker_count"]),
        mp_context=context,
        initializer=_worker_initialize,
        initargs=(str((ROOT / CONTRACT).resolve()),),
    ) as pool:
        pings = [
            pool.submit(_worker_ping, limits["startup_ping_delay_sec"])
            for _ in range(int(limits["worker_count"]))
        ]
        worker_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(limits["startup_ping_delay_sec"]), 0.0
        )

        def parallel_step_solver(*args, **kwargs):
            template = args[3]
            previous = np.asarray(kwargs["previous_inventory_lbmol"], dtype=float)
            algebraic = np.asarray(
                kwargs["initial_algebraic_coordinates"], dtype=float
            )
            root_epoch = str(kwargs["name"])
            template_payload = _state_payload(template)

            def builder(_objective, point, state_id):
                tasks, groups = build_colored_central_difference_tasks(
                    point,
                    pattern=pattern,
                    step=settings.jacobian_step,
                    state_id=state_id,
                )
                work = [
                    {
                        "task": task,
                        "root_epoch": root_epoch,
                        "template_state": template_payload,
                        "previous_inventory_lbmol": previous.tolist(),
                        "initial_algebraic_coordinates": algebraic.tolist(),
                        "step_seconds": float(kwargs["step_seconds"]),
                    }
                    for task in tasks
                ]
                started = time.perf_counter()
                raw = list(pool.map(_worker_evaluate, work, chunksize=1))
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
                    step=settings.jacobian_step,
                )
                parallel_jacobian_wall.append(float(time.perf_counter() - started))
                parallel_matrices.append(matrix.copy())
                worker_evidence.append(
                    {
                        "root_epoch": root_epoch,
                        "color_count": len(groups),
                        "task_count": len(raw),
                        "worker_ids": sorted({int(item["process_id"]) for item in raw}),
                        "basis_rebuilds": int(sum(item["basis_rebuilt"] for item in raw)),
                        "logical_provider_calls": int(
                            sum(item["logical_provider_calls"] for item in raw)
                        ),
                        "memo_hits": int(sum(item["memo_hits"] for item in raw)),
                        "memo_misses": int(sum(item["memo_misses"] for item in raw)),
                    }
                )
                return matrix

            return solve_backward_euler_step(
                *args, **kwargs, jacobian_builder=builder
            )

        parallel_started = time.perf_counter()
        parallel = run_short_trajectory(
            pcontract,
            parallel_spec,
            parallel_ref,
            parallel_state,
            pprovider,
            paudit,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step_seconds=float(limits["step_seconds"]),
            duration_seconds=float(limits["duration_seconds"]),
            settings=settings,
            name="dd183:parallel",
            step_solver=parallel_step_solver,
        )
        parallel_wall = time.perf_counter() - parallel_started
    total_wall = time.perf_counter() - total_started

    initial_inventory = inventory_from_state(serial_state)
    initial_algebraic = dynamic_algebraic_coordinates(
        serial_spec, serial_ref, serial_state
    )
    serial_report = dd177._trajectory_report(
        serial,
        serial_spec,
        initial_inventory,
        initial_algebraic,
        payload["limits"],
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    parallel_report = dd177._trajectory_report(
        parallel,
        parallel_spec,
        initial_inventory,
        initial_algebraic,
        payload["limits"],
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    comparison = _trajectory_comparison(serial, parallel)
    if len(serial_matrices) != len(parallel_matrices):
        matrix_differences = [float("inf")]
    else:
        matrix_differences = [
            dd182._maximum_absolute_difference(a, b)
            for a, b in zip(serial_matrices, parallel_matrices, strict=True)
        ]
    expected_response = (
        float(payload["disturbance"]["total_rate_increment_lbmolph"])
        * float(limits["duration_seconds"])
        / 3600.0
    )
    serial_response = float(
        serial_report["total_inventory_history_lbmol"][-1]
        - serial_report["total_inventory_history_lbmol"][0]
    )
    parallel_response = float(
        parallel_report["total_inventory_history_lbmol"][-1]
        - parallel_report["total_inventory_history_lbmol"][0]
    )
    response_relative = {
        "serial": abs(serial_response - expected_response) / expected_response,
        "parallel": abs(parallel_response - expected_response) / expected_response,
    }
    serial_provider_summary = serial_audit.report()
    parallel_provider_summary = paudit.report()
    worker_calls = sum(item["logical_provider_calls"] for item in worker_evidence)
    parallel_ratio = parallel_wall / serial_wall
    governed_ratio = (startup_adjusted + parallel_wall) / serial_wall
    numeric_max = comparison["maximum_numeric_differences"]
    endpoint_keys = tuple(
        key
        for key in numeric_max
        if key not in {"cost_difference", "optimality_difference"}
    )
    first_matrix_by_root: dict[str, int] = {}
    basis_pattern_valid = True
    for item in worker_evidence:
        root = item["root_epoch"]
        occurrence = first_matrix_by_root.get(root, 0)
        if occurrence == 0:
            basis_pattern_valid = basis_pattern_valid and item["basis_rebuilds"] == 4
        else:
            basis_pattern_valid = basis_pattern_valid and item["basis_rebuilds"] == 0
        first_matrix_by_root[root] = occurrence + 1
    gates = {
        "paths_complete": serial.completed and parallel.completed,
        "scientific_steps": serial_report["step_gates_pass"]
        and parallel_report["step_gates_pass"],
        "response": max(response_relative.values())
        <= limits["response_relative_limit"],
        "monotone_response": serial_report["total_inventory_strictly_increasing"]
        and parallel_report["total_inventory_strictly_increasing"],
        "jacobian_count": len(serial_matrices) == len(parallel_matrices) > 0,
        "every_jacobian_exact": max(matrix_differences)
        <= limits["matrix_absolute_limit"],
        "solver_decisions_exact": comparison["all_metadata_equal"]
        and numeric_max["cost_difference"] <= limits["solver_decision_limit"]
        and numeric_max["optimality_difference"]
        <= limits["solver_decision_limit"],
        "accepted_states_equivalent": all(
            numeric_max[key] <= limits["endpoint_absolute_limit"]
            for key in endpoint_keys
        ),
        "process_isolation": len(worker_ids) == limits["worker_count"]
        and all(
            len(item["worker_ids"]) == limits["worker_count"]
            for item in worker_evidence
        ),
        "task_ownership": all(
            item["color_count"] == 17 and item["task_count"] == 34
            for item in worker_evidence
        ),
        "evolving_basis": len(first_matrix_by_root) == limits["steps_per_path"]
        and basis_pattern_valid,
        "provider": serial_provider_summary["pass"]
        and parallel_provider_summary["pass"],
        "provider_calls": serial_provider_summary["total_calls"]
        < limits["main_logical_provider_call_limit_each"]
        and parallel_provider_summary["total_calls"]
        < limits["main_logical_provider_call_limit_each"]
        and worker_calls < limits["worker_logical_provider_call_limit"],
        "parallel_trajectory_speed": parallel_ratio
        <= limits["parallel_trajectory_time_ratio_limit"],
        "governed_speed_including_startup": governed_ratio
        <= limits["parallel_governed_time_ratio_limit"],
        "wall_clock": total_wall < limits["wall_clock_limit_sec"],
        "no_controller_or_retry": True,
    }
    passed = all(gates.values())
    compact_steps = lambda report: [
        {
            key: step[key]
            for key in (
                "index",
                "time_seconds",
                "success",
                "nfev",
                "njev",
                "wall_clock_sec",
                "residual_inf_norm",
                "jacobian_rank",
                "jacobian_condition",
                "physical_pass",
                "gates",
            )
        }
        for step in report["steps"]
    ]
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "persistent_parallel_short_trajectory_exact_and_faster"
            if passed
            else "persistent_parallel_short_trajectory_failed"
        ),
        "decision": (
            "authorize_persistent_parallel_production_step_path"
            if passed
            else "retain_serial_production_step_path"
        ),
        "serial": {
            "wall_clock_sec": float(serial_wall),
            "steps": compact_steps(serial_report),
            "response_lbmol": serial_response,
            "provider": serial_provider_summary,
        },
        "parallel": {
            "wall_clock_sec": float(parallel_wall),
            "steps": compact_steps(parallel_report),
            "response_lbmol": parallel_response,
            "provider": parallel_provider_summary,
        },
        "expected_response_lbmol": float(expected_response),
        "response_relative_error": response_relative,
        "trajectory_comparison": comparison,
        "jacobian_evaluations_per_path": len(serial_matrices),
        "jacobian_pair_max_abs_differences": matrix_differences,
        "serial_total_jacobian_wall_sec": float(sum(serial_jacobian_wall)),
        "parallel_total_jacobian_wall_sec": float(sum(parallel_jacobian_wall)),
        "parallel_trajectory_time_ratio": float(parallel_ratio),
        "parallel_trajectory_speedup": float(1.0 / parallel_ratio),
        "parallel_governed_time_ratio": float(governed_ratio),
        "parallel_governed_speedup": float(1.0 / governed_ratio),
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "worker_ids": worker_ids,
        "worker_evidence": worker_evidence,
        "worker_logical_provider_calls": int(worker_calls),
        "total_wall_clock_sec": float(total_wall),
        "gates": gates,
        "pass_gate": bool(passed),
        "campaign_executed_once": True,
        "serial_roots_executed": serial.completed_steps,
        "parallel_roots_executed": parallel.completed_steps,
        "controller_attempted": False,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "projection_attempted": False,
        "clipping_attempted": False,
        "fallback_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-183 Seven-Volume Persistent-Parallel Short-Trajectory Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Roots: `{serial.completed_steps}` serial / `{parallel.completed_steps}` parallel",
                f"- Jacobians per path: `{len(serial_matrices)}`",
                f"- Worst paired Jacobian difference: `{max(matrix_differences):.6e}`",
                f"- Worst accepted-state difference: `{max(numeric_max[key] for key in endpoint_keys):.6e}`",
                f"- Serial/parallel trajectory wall: `{serial_wall:.3f} s` / `{parallel_wall:.3f} s`",
                f"- Parallel trajectory speedup excluding startup: `{1.0 / parallel_ratio:.3f}x`",
                f"- Adjusted startup: `{startup_adjusted:.3f} s`",
                f"- Governed speedup including startup: `{1.0 / governed_ratio:.3f}x`",
                f"- Actual/expected response: `{serial_response:.12f}` / `{expected_response:.12f} lbmol`",
                f"- Gates: `{gates}`",
                "",
                "One persistent four-process DWSIM pool supplied every parallel Jacobian while the main process retained all residual, trust-region, convergence, and state-acceptance decisions. No controller, retry, alternate grid, projection, clipping, or fallback occurred.",
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
                    "jacobian_evaluations_per_path",
                    "parallel_trajectory_speedup",
                    "parallel_governed_speedup",
                    "total_wall_clock_sec",
                    "pass_gate",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass_gate"] else 2)
