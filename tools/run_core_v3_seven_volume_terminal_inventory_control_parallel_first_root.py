#!/usr/bin/env python
"""Prepare or execute DD-191's controlled serial/parallel first-root proof."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_seven_volume_terminal_inventory_control_numerical as dd185  # noqa: E402
import run_core_v3_seven_volume_parallel_first_root as dd182  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_modest_trajectory as dd190  # noqa: E402
from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    component_rate_scales,
    governing_storage_vector,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    ColoredCentralDifferenceTask,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    audit_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    TerminalInventoryControlBackwardEulerEvaluation,
    evaluate_terminal_inventory_control_backward_euler_residual,
    solve_terminal_inventory_control_backward_euler_step,
    terminal_inventory_control_step_pattern,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
)


SCHEMA = "dd191-core-v3-terminal-control-parallel-first-root-contract-v1"
RESULT_SCHEMA = "dd191-core-v3-terminal-control-parallel-first-root-result-v1"
DD190_CONTRACT = Path(
    "logs/dd190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_contract_20260813.json"
)
DD190_RESULT = Path(
    "logs/dd190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_20260813.json"
)
DD185_CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
CONTRACT = Path(
    "logs/dd191_core_v3_terminal_inventory_control_parallel_first_root_contract_20260813.json"
)
RESULT = Path(
    "logs/dd191_core_v3_terminal_inventory_control_parallel_first_root_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_191_core_v3_terminal_inventory_control_parallel_first_root_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_191_core_v3_terminal_inventory_control_parallel_first_root_20260813.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "tests/test_core_v3_terminal_inventory_control_implicit_step_v1.py",
    "tests/test_core_v3_terminal_inventory_control_parallel_first_root.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_parallel_first_root.py",
)


_WORKER_OBJECTIVE = None
_WORKER_AUDIT = None
_WORKER_PROVIDER = None


def _validate_source(result: Mapping[str, Any]) -> None:
    if result.get("pass_gate") is not False or result.get("decision") != (
        "stop_terminal_control_trajectory_path"
    ):
        raise RuntimeError("DD-191 requires DD-190's preserved formal stop")
    if [name for name, value in result["campaign_gates"].items() if not value] != [
        "shared_time_refinement"
    ]:
        raise RuntimeError("DD-190 failure pattern changed")
    if result.get("completed_roots") != 120:
        raise RuntimeError("DD-190 did not preserve all completed roots")
    if not result["coarse"]["step_gates_pass"] or not result["refined"][
        "step_gates_pass"
    ]:
        raise RuntimeError("DD-190 per-root health changed")


def _build_controlled(spec: Any, dd185_contract: Mapping[str, Any]):
    controlled = dd185._controlled_contract(spec, dd185_contract)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-191 controlled structure changed")
    return controlled


def _context(payload: Mapping[str, Any]):
    spec = dd190.dd188.dd187.dd186.dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd190.dd188.dd187.dd186.dd171.dd168._reference(
        payload["reference"]
    )
    state = dd190.dd188.dd187.dd186.dd171._state(payload["accepted_root_state"])
    dd185_contract = dd190.dd188.dd187.dd186._load(DD185_CONTRACT)
    controlled = _build_controlled(spec, dd185_contract)
    provider = dd190.dd188.dd187.dd186.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    memory = np.asarray(payload["initial_controller_memory"], dtype=float)
    initial = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    return (
        spec,
        reference,
        state,
        controlled,
        provider,
        audit,
        inventory,
        memory,
        initial,
        setpoints,
        product_reference,
    )


def _worker_context(payload: Mapping[str, Any]):
    (
        spec,
        reference,
        state,
        controlled,
        provider,
        audit,
        inventory,
        memory,
        initial,
        setpoints,
        product_reference,
    ) = _context(payload)
    baseline = evaluate_terminal_inventory_control_residual(
        controlled,
        spec,
        reference,
        state,
        provider,
        audit,
        inventory_lbmol=inventory,
        controller_memory=memory,
        level_setpoints=setpoints,
        solve_coordinates=initial,
        storage_gradient_BTU_lbmol=np.zeros_like(inventory),
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=product_reference,
        state_id=f"dd191:worker_{os.getpid()}:scale_basis",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(controlled.base, baseline.base)
    previous_storage = governing_storage_vector(
        spec, baseline.base, inventory
    )
    step_seconds = float(payload["integration"]["step_seconds"])

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_terminal_inventory_control_backward_euler_residual(
            controlled,
            spec,
            reference,
            state,
            provider,
            audit,
            previous_inventory_lbmol=inventory,
            previous_internal_energy_BTU=previous_storage,
            previous_controller_memory=memory,
            level_setpoints=setpoints,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=candidate,
            step_seconds=step_seconds,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=product_reference,
            state_id=state_id,
            evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
        ).scaled

    pattern = terminal_inventory_control_step_pattern(controlled)
    objective(initial, f"dd191:worker_{os.getpid()}:warmup_residual")
    return objective, audit, provider, pattern


def _worker_initialize(contract_path: str) -> None:
    global _WORKER_OBJECTIVE, _WORKER_AUDIT, _WORKER_PROVIDER
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    objective, audit, provider, _pattern = _worker_context(payload)
    _WORKER_OBJECTIVE = objective
    _WORKER_AUDIT = audit
    _WORKER_PROVIDER = provider


def _worker_ping(delay_seconds: float) -> int:
    if _WORKER_OBJECTIVE is None:
        raise RuntimeError("DD-191 worker was not initialized")
    time.sleep(float(delay_seconds))
    return int(os.getpid())


def _worker_evaluate(task: ColoredCentralDifferenceTask) -> dict[str, Any]:
    if _WORKER_OBJECTIVE is None or _WORKER_AUDIT is None or _WORKER_PROVIDER is None:
        raise RuntimeError("DD-191 worker was not initialized")
    before_records = len(_WORKER_AUDIT.records)
    before_memo = _WORKER_PROVIDER.get_exact_state_memoization_stats()
    started = time.perf_counter()
    residual = np.asarray(
        _WORKER_OBJECTIVE(np.asarray(task.coordinates), task.state_id), dtype=float
    ).reshape((-1,))
    elapsed = time.perf_counter() - started
    after_memo = _WORKER_PROVIDER.get_exact_state_memoization_stats()
    report = _WORKER_AUDIT.report()
    return {
        "order": int(task.order),
        "residual": residual.tolist(),
        "process_id": int(os.getpid()),
        "logical_provider_calls": int(len(_WORKER_AUDIT.records) - before_records),
        "memo_hits": int(after_memo["hits"] - before_memo["hits"]),
        "memo_misses": int(after_memo["misses"] - before_memo["misses"]),
        "provider_pass": bool(report["pass"]),
        "fallback_attempted": bool(report["fallback_attempted"]),
        "wall_clock_sec": float(elapsed),
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    integration = payload["integration"]
    return "\n".join(
        (
            "# DD-191 Controlled Parallel First-Root Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            f"- Root: first controlled `{integration['step_seconds']} s` refined step",
            f"- Matrix: `58 x 58`, `{integration['color_count']}` colors, "
            f"`{integration['tasks_per_matrix']}` perturbation tasks",
            "- Comparison: serial in-process versus four isolated DWSIM workers",
            "- Equivalence: Jacobians, SciPy decisions, and all endpoint quantities",
            "- Performance: parallel solve excluding startup at least `10%` faster",
            "- Endpoint acceptance, second timestep, trajectory, tuning, and retry: prohibited",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-191 Controlled Parallel First-Root Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Serial/parallel residuals: `{payload['serial']['residual_inf_norm']:.6e}` / "
            f"`{payload['parallel']['residual_inf_norm']:.6e}`",
            f"- Paired Jacobian maximum difference: "
            f"`{payload['matrix_comparison']['maximum_absolute_difference']:.6e}`",
            f"- Endpoint maximum difference: "
            f"`{payload['outcome_comparison']['maximum_numeric_difference']:.6e}`",
            f"- Serial/parallel solve wall: `{payload['serial']['wall_clock_sec']:.6f}` / "
            f"`{payload['parallel']['wall_clock_sec']:.6f} s`",
            f"- Solve speedup: `{payload['performance']['solve_speedup']:.3f}x`",
            f"- Four-worker adjusted startup: "
            f"`{payload['performance']['startup_wall_sec_adjusted']:.3f} s`",
            "- Endpoint accepted/state advanced: `False / False`",
            "",
        )
    )


def prepare(
    source_contract_path: Path,
    source_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = dd190.dd188.dd187.dd186._load(source_contract_path)
    result = dd190.dd188.dd187.dd186._load(source_result_path)
    _validate_source(result)
    spec = dd190.dd188.dd187.dd186.dd171.dd168._spec(
        source["source_mapping"],
        float(source["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    controlled = _build_controlled(
        spec, dd190.dd188.dd187.dd186._load(DD185_CONTRACT)
    )
    pattern = terminal_inventory_control_step_pattern(controlled)
    tasks, groups = build_colored_central_difference_tasks(
        source["initial_solve_coordinates"],
        pattern=pattern,
        step=float(source["solver"]["jacobian_step"]),
        state_id="dd191:preparation",
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd190.dd188.dd187.dd186._git(
            "rev-parse", "HEAD"
        ),
        "sources": {
            str(path).replace("\\", "/"): dd190.dd188.dd187.dd186._sha(ROOT / path)
            for path in (source_contract_path, source_result_path, DD185_CONTRACT)
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "initial_solve_coordinates": source["initial_solve_coordinates"],
        "initial_controller_memory": source["initial_controller_memory"],
        "level_setpoints": source["level_setpoints"],
        "product_reference_lbmolph": source["product_reference_lbmolph"],
        "geometry": source["geometry"],
        "controllers": source["controllers"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": source["solver"],
        "integration": {
            "step_seconds": 0.125,
            "matrix_shape": list(pattern.shape),
            "color_count": len(groups),
            "tasks_per_matrix": len(tasks),
            "worker_count": 4,
            "startup_ping_delay_sec": 0.15,
            "matrix_absolute_limit": 1.0e-10,
            "endpoint_absolute_limit": 1.0e-12,
            "residual_limit": 1.0e-8,
            "rank": 58,
            "condition_limit": 1.0e8,
            "parallel_solve_ratio_limit": 0.90,
            "logical_provider_call_limit": 40000,
            "wall_clock_limit_sec": 120.0,
        },
        "implementation_sha256": {
            path: dd190.dd188.dd187.dd186._sha(ROOT / path)
            for path in IMPLEMENTATION
        },
        "hard_stops": [
            "serial or parallel root fails closure, rank, condition, or provider ownership",
            "a paired Jacobian, SciPy decision, or endpoint differs beyond its limit",
            "all four isolated workers do not participate",
            "parallel solve excluding startup is not at least ten percent faster",
            "an endpoint is accepted, a second timestep runs, or tuning/retry occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "endpoint_accepted": False,
        "state_advanced": False,
        "controller_tuning_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = dd190.dd188.dd187.dd186._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-191 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd190.dd188.dd187.dd186._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-191 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd190.dd188.dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-191 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd190.dd188.dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-191 implementation changed: {path}")
    if dd190.dd188.dd187.dd186._sha(Path(payload["workbook"])) != payload[
        "workbook_sha256"
    ]:
        raise RuntimeError("DD-191 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-191 result exists; rerun is prohibited")
    if not dd190.dd188.dd187.dd186._git(
        "ls-files", "--error-unmatch", str(contract_path)
    ):
        raise RuntimeError("DD-191 contract is not committed")


def _summary(outcome: Any) -> dict[str, Any]:
    singular = np.linalg.svd(outcome.final_jacobian, compute_uv=False)
    return {
        "success": bool(outcome.success),
        "status": int(outcome.status),
        "message": str(outcome.message),
        "nfev": int(outcome.nfev),
        "njev": None if outcome.njev is None else int(outcome.njev),
        "cost": float(outcome.cost),
        "optimality": float(outcome.optimality),
        "wall_clock_sec": float(outcome.wall_clock_sec),
        "residual_inf_norm": float(np.max(np.abs(outcome.final_residual))),
        "jacobian_rank": int(np.linalg.matrix_rank(outcome.final_jacobian)),
        "jacobian_condition": float(singular[0] / singular[-1]),
        "jacobian_sha256": dd182._matrix_sha(outcome.final_jacobian),
    }


def _outcome_comparison(serial: Any, parallel: Any) -> dict[str, Any]:
    first = serial.evaluation
    second = parallel.evaluation
    if not isinstance(first, TerminalInventoryControlBackwardEulerEvaluation) or not isinstance(
        second, TerminalInventoryControlBackwardEulerEvaluation
    ):
        raise TypeError("DD-191 outcomes lack controlled evaluations")
    numeric = {
        "cost": abs(float(serial.cost) - float(parallel.cost)),
        "optimality": abs(float(serial.optimality) - float(parallel.optimality)),
        "initial_coordinates": dd182._maximum_absolute_difference(
            serial.initial_coordinates, parallel.initial_coordinates
        ),
        "final_coordinates": dd182._maximum_absolute_difference(
            serial.final_coordinates, parallel.final_coordinates
        ),
        "final_residual": dd182._maximum_absolute_difference(
            serial.final_residual, parallel.final_residual
        ),
        "returned_jacobian": dd182._maximum_absolute_difference(
            serial.final_jacobian, parallel.final_jacobian
        ),
        "inventory_lbmol": dd182._maximum_absolute_difference(
            first.endpoint_inventory_lbmol, second.endpoint_inventory_lbmol
        ),
        "component_rate_lbmolph": dd182._maximum_absolute_difference(
            first.component_rate_lbmolph, second.component_rate_lbmolph
        ),
        "algebraic_coordinates": dd182._maximum_absolute_difference(
            first.algebraic_coordinates, second.algebraic_coordinates
        ),
        "controller_memory": dd182._maximum_absolute_difference(
            first.endpoint_controller_memory, second.endpoint_controller_memory
        ),
        "level_fraction": dd182._maximum_absolute_difference(
            first.level_fraction, second.level_fraction
        ),
        "product_log_ratio": dd182._maximum_absolute_difference(
            first.product_log_ratio, second.product_log_ratio
        ),
        "distillate_lbmolph": abs(first.distillate_lbmolph - second.distillate_lbmolph),
        "bottoms_lbmolph": abs(first.bottoms_lbmolph - second.bottoms_lbmolph),
        "endpoint_energy_BTU": dd182._maximum_absolute_difference(
            first.endpoint_internal_energy_BTU, second.endpoint_internal_energy_BTU
        ),
    }
    return {
        "success_equal": serial.success == parallel.success,
        "status_equal": serial.status == parallel.status,
        "message_equal": serial.message == parallel.message,
        "nfev_equal": serial.nfev == parallel.nfev,
        "njev_equal": serial.njev == parallel.njev,
        "numeric_differences": numeric,
        "maximum_numeric_difference": max(numeric.values()),
    }


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = dd190.dd188.dd187.dd186._load(contract_path)
    _verify(payload, contract_path, result_path)
    _validate_source(dd190.dd188.dd187.dd186._load(DD190_RESULT))
    serial_context = _context(payload)
    parallel_context = _context(payload)
    (
        serial_spec, serial_reference, serial_state, controlled,
        serial_provider, serial_audit, inventory, memory, initial,
        setpoints, product_reference,
    ) = serial_context
    (
        parallel_spec, parallel_reference, parallel_state, parallel_controlled,
        parallel_provider, parallel_audit, parallel_inventory, parallel_memory,
        parallel_initial, parallel_setpoints, parallel_product_reference,
    ) = parallel_context
    pattern = terminal_inventory_control_step_pattern(controlled)
    parallel_pattern = terminal_inventory_control_step_pattern(parallel_controlled)
    if not np.array_equal(pattern, parallel_pattern):
        raise RuntimeError("DD-191 serial and parallel patterns differ")
    settings = dd190.dd188.dd187.dd186._settings(payload)
    serial_matrices: list[np.ndarray] = []
    parallel_matrices: list[np.ndarray] = []
    serial_times: list[float] = []
    parallel_times: list[float] = []
    worker_evidence: list[dict[str, Any]] = []

    def serial_builder(objective, point, state_id):
        started = time.perf_counter()
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=settings.jacobian_step,
            state_id=state_id,
        )
        if len(groups) != payload["integration"]["color_count"]:
            raise RuntimeError("DD-191 serial color count changed")
        serial_times.append(time.perf_counter() - started)
        serial_matrices.append(matrix.copy())
        return matrix

    integration = payload["integration"]
    spawn = mp.get_context("spawn")
    total_started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(integration["worker_count"]),
        mp_context=spawn,
        initializer=_worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(_worker_ping, integration["startup_ping_delay_sec"])
            for _ in range(int(integration["worker_count"]))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(integration["startup_ping_delay_sec"]), 0.0
        )
        serial = solve_terminal_inventory_control_backward_euler_step(
            controlled,
            serial_spec,
            serial_reference,
            serial_state,
            serial_provider,
            serial_audit,
            previous_inventory_lbmol=inventory,
            previous_controller_memory=memory,
            level_setpoints=setpoints,
            initial_solve_coordinates=initial,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=product_reference,
            step_seconds=float(integration["step_seconds"]),
            settings=settings,
            name="dd191:serial",
            jacobian_builder=serial_builder,
        )

        def parallel_builder(_objective, point, state_id):
            tasks, groups = build_colored_central_difference_tasks(
                point,
                pattern=pattern,
                step=settings.jacobian_step,
                state_id=state_id,
            )
            started = time.perf_counter()
            raw = list(pool.map(_worker_evaluate, tasks, chunksize=1))
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
            parallel_times.append(time.perf_counter() - started)
            parallel_matrices.append(matrix.copy())
            worker_evidence.append(
                {
                    "color_count": len(groups),
                    "task_count": len(raw),
                    "worker_ids": sorted({int(item["process_id"]) for item in raw}),
                    "logical_provider_calls": int(
                        sum(item["logical_provider_calls"] for item in raw)
                    ),
                    "memo_hits": int(sum(item["memo_hits"] for item in raw)),
                    "memo_misses": int(sum(item["memo_misses"] for item in raw)),
                    "provider_pass": all(item["provider_pass"] for item in raw),
                    "fallback_attempted": any(
                        item["fallback_attempted"] for item in raw
                    ),
                }
            )
            return matrix

        parallel = solve_terminal_inventory_control_backward_euler_step(
            parallel_controlled,
            parallel_spec,
            parallel_reference,
            parallel_state,
            parallel_provider,
            parallel_audit,
            previous_inventory_lbmol=parallel_inventory,
            previous_controller_memory=parallel_memory,
            level_setpoints=parallel_setpoints,
            initial_solve_coordinates=parallel_initial,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=parallel_product_reference,
            step_seconds=float(integration["step_seconds"]),
            settings=settings,
            name="dd191:parallel",
            jacobian_builder=parallel_builder,
        )
    total_wall = time.perf_counter() - total_started
    serial_memo = serial_provider.get_exact_state_memoization_stats()
    parallel_memo = parallel_provider.get_exact_state_memoization_stats()
    serial_provider.set_exact_state_memoization(False, clear=True)
    parallel_provider.set_exact_state_memoization(False, clear=True)
    matrix_differences = [
        dd182._maximum_absolute_difference(first, second)
        for first, second in zip(serial_matrices, parallel_matrices, strict=True)
    ]
    matrix_comparison = {
        "serial_count": len(serial_matrices),
        "parallel_count": len(parallel_matrices),
        "serial_sha256": [dd182._matrix_sha(value) for value in serial_matrices],
        "parallel_sha256": [dd182._matrix_sha(value) for value in parallel_matrices],
        "per_matrix_max_abs_difference": matrix_differences,
        "maximum_absolute_difference": max(matrix_differences),
    }
    comparison = _outcome_comparison(serial, parallel)
    serial_summary = _summary(serial)
    parallel_summary = _summary(parallel)
    provider_summary = {
        "serial": dd190.dd188.dd187.dd186._provider_summary(serial_audit),
        "parallel_main": dd190.dd188.dd187.dd186._provider_summary(parallel_audit),
        "workers": worker_evidence,
    }
    logical_calls = (
        provider_summary["serial"]["total_calls"]
        + provider_summary["parallel_main"]["total_calls"]
        + sum(item["logical_provider_calls"] for item in worker_evidence)
    )
    performance = {
        "serial_total_jacobian_wall_sec": float(sum(serial_times)),
        "parallel_total_jacobian_wall_sec": float(sum(parallel_times)),
        "serial_solve_wall_sec": serial.wall_clock_sec,
        "parallel_solve_wall_sec": parallel.wall_clock_sec,
        "parallel_solve_ratio": parallel.wall_clock_sec / serial.wall_clock_sec,
        "solve_speedup": serial.wall_clock_sec / parallel.wall_clock_sec,
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "total_governed_wall_sec": float(total_wall),
    }
    decisions_equal = all(
        comparison[name]
        for name in (
            "success_equal", "status_equal", "message_equal", "nfev_equal", "njev_equal"
        )
    )
    gates = {
        "serial_root": serial.success
        and serial_summary["residual_inf_norm"] < integration["residual_limit"]
        and serial_summary["jacobian_rank"] == integration["rank"]
        and serial_summary["jacobian_condition"] < integration["condition_limit"],
        "parallel_root": parallel.success
        and parallel_summary["residual_inf_norm"] < integration["residual_limit"]
        and parallel_summary["jacobian_rank"] == integration["rank"]
        and parallel_summary["jacobian_condition"] < integration["condition_limit"],
        "matrix_count": len(serial_matrices) == len(parallel_matrices) > 0,
        "matrix_equivalence": matrix_comparison["maximum_absolute_difference"]
        < integration["matrix_absolute_limit"],
        "decision_equivalence": decisions_equal,
        "endpoint_equivalence": comparison["maximum_numeric_difference"]
        < integration["endpoint_absolute_limit"],
        "worker_participation": len(ping_ids) == integration["worker_count"]
        and all(
            len(item["worker_ids"]) == integration["worker_count"]
            for item in worker_evidence
        ),
        "provider": provider_summary["serial"]["pass"]
        and provider_summary["parallel_main"]["pass"]
        and all(item["provider_pass"] for item in worker_evidence)
        and not any(item["fallback_attempted"] for item in worker_evidence),
        "provider_calls": logical_calls < integration["logical_provider_call_limit"],
        "parallel_speed": performance["parallel_solve_ratio"]
        < integration["parallel_solve_ratio_limit"],
        "wall_clock": total_wall < integration["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "controlled_parallel_first_root_passed"
            if passed
            else "controlled_parallel_first_root_failed"
        ),
        "decision": (
            "authorize_persistent_parallel_controlled_step_path"
            if passed
            else "retain_serial_controlled_step_path"
        ),
        "contract_commit": dd190.dd188.dd187.dd186._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "serial": serial_summary,
        "parallel": parallel_summary,
        "matrix_comparison": matrix_comparison,
        "outcome_comparison": comparison,
        "worker_ping_ids": ping_ids,
        "provider": provider_summary,
        "logical_provider_calls": int(logical_calls),
        "serial_memoization": serial_memo,
        "parallel_main_memoization": parallel_memo,
        "performance": performance,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "endpoint_accepted": False,
        "state_advanced": False,
        "second_timestep_attempted": False,
        "controller_tuning_attempted": False,
        "trajectory_attempted": False,
        "retry_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--source-contract", type=Path, default=DD190_CONTRACT)
    parser.add_argument("--source-result", type=Path, default=DD190_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.source_contract,
            args.source_result,
            args.contract,
            args.contract_doc,
        )
        print(json.dumps({"schema_id": output["schema_id"], "contract_payload_sha256": output["contract_payload_sha256"], "integration": output["integration"], "campaign_executed": output["campaign_executed"]}, indent=2))
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(json.dumps({"classification": output["classification"], "pass_gate": output["pass_gate"], "decision": output["decision"]}, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
