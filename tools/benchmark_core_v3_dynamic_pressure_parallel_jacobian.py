#!/usr/bin/env python
"""Benchmark serial and persistent-parallel Core V3 pressure Jacobians."""

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

import run_core_v3_dynamic as production  # noqa: E402
import run_core_v3_vapor_holdup_dynamic_pressure_thirty_second_trajectory as dd274  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402

from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitReference,
)


SCHEMA = "core-v3-dynamic-pressure-parallel-jacobian-benchmark-v1"
_WORKER_CONTEXT: dict[str, Any] | None = None


def _reference_payload(reference: VaporHoldupImplicitReference) -> dict[str, Any]:
    return {
        **{
            name: np.asarray(value, dtype=float).tolist()
            for name, value in production._reference_arrays(reference).items()
            if name != "condenser_duty_BTUph"
        },
        "condenser_duty_BTUph": float(reference.condenser_duty_BTUph),
    }


def _reference_from_payload(payload: Mapping[str, Any]) -> VaporHoldupImplicitReference:
    return VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=np.asarray(
            payload["liquid_component_inventory_lbmol"], dtype=float
        ),
        vapor_component_inventory_lbmol=np.asarray(
            payload["vapor_component_inventory_lbmol"], dtype=float
        ),
        phase_transfer_lbmolph=np.asarray(payload["phase_transfer_lbmolph"], dtype=float),
        phase_transfer_scale_lbmolph=np.asarray(
            payload["phase_transfer_scale_lbmolph"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        pressure_psia=np.asarray(payload["pressure_psia"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        condenser_duty_BTUph=float(payload["condenser_duty_BTUph"]),
        total_stored_energy_BTU=np.asarray(payload["total_stored_energy_BTU"], dtype=float),
    )


def _worker_initialize() -> None:
    global _WORKER_CONTEXT
    context = production._context()
    provider = context["provider"]
    setter = getattr(provider, "set_exact_state_memoization", None)
    if callable(setter):
        setter(True, clear=True)
    _WORKER_CONTEXT = {
        "context": context,
        "root_epoch": None,
        "reference": None,
        "memory": None,
        "timestep_sec": None,
        "specified_duty": None,
    }


def _worker_ping(delay_sec: float) -> int:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("parallel benchmark worker is unavailable")
    time.sleep(float(delay_sec))
    return int(os.getpid())


def _worker_evaluate(work: Mapping[str, Any]) -> dict[str, Any]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("parallel benchmark worker is unavailable")
    worker = _WORKER_CONTEXT
    epoch = str(work["root_epoch"])
    rebuilt = worker["root_epoch"] != epoch
    if rebuilt:
        worker["reference"] = _reference_from_payload(work["reference"])
        worker["memory"] = np.asarray(work["memory"], dtype=float)
        worker["timestep_sec"] = float(work["timestep_sec"])
        worker["specified_duty"] = float(work["specified_duty"])
        worker["root_epoch"] = epoch
        provider = worker["context"]["provider"]
        setter = getattr(provider, "set_exact_state_memoization", None)
        if callable(setter):
            setter(True, clear=True)
        worker["context"]["audit"] = ProviderCallAudit(
            provider_identity="dwsim",
            interface_provider_identities={"declared_liquid_density": "aligned_pr"},
        )

    task = work["task"]
    context = worker["context"]
    audit = context["audit"]
    before = audit.record_count
    evaluation = dd274._evaluate(
        context,
        worker["reference"],
        worker["memory"],
        np.asarray(task.coordinates, dtype=float),
        worker["timestep_sec"],
        worker["specified_duty"],
        task.state_id,
    )
    provider_report = audit.report()
    return {
        "order": int(task.order),
        "residual": evaluation.scaled.tolist(),
        "process_id": int(os.getpid()),
        "method": str(work["method"]),
        "root_epoch": epoch,
        "basis_rebuilt": rebuilt,
        "logical_provider_calls": int(audit.record_count - before),
        "provider_pass": bool(provider_report["pass"]),
        "fallback_attempted": bool(provider_report["fallback_attempted"]),
    }


def _predicted_point(
    context: Mapping[str, Any],
    previous_coordinates: np.ndarray,
    prior: Any,
    timestep_sec: float,
) -> np.ndarray:
    return dd274.controlled_implicit_initial_coordinates(
        context["contract"],
        controller_rates_per_sec=prior.controller_rate_per_sec,
        timestep_sec=float(timestep_sec),
        previous_coordinates=previous_coordinates,
        product_log_ratios_previous=prior.product_log_ratio,
    )


def benchmark(
    *,
    workbook: Path,
    checkpoint: Path,
    worker_count: int,
    difference_step: float,
    ping_delay_sec: float,
) -> dict[str, Any]:
    workbook = workbook.expanduser().resolve()
    checkpoint = checkpoint.expanduser().resolve()
    context = production._context()
    metadata, reference, memory, previous_coordinates, prior = production._load_checkpoint(
        checkpoint, workbook=workbook, context=context
    )
    timestep_sec = production.ACCEPTED_TIMESTEP_SEC
    specified_duty = float(metadata["specified_condenser_duty_BTUph"])
    point = _predicted_point(context, previous_coordinates, prior, timestep_sec)
    pattern = dd274.vapor_holdup_terminal_control_pattern(context["contract"])
    tasks, groups = build_colored_central_difference_tasks(
        point,
        pattern=pattern,
        step=float(difference_step),
        state_id="core_v3_dynamic_pressure_benchmark:serial",
    )

    provider = context["provider"]
    setter = getattr(provider, "set_exact_state_memoization", None)
    if callable(setter):
        setter(True, clear=True)
    audit = context["audit"]
    serial_before = audit.record_count
    serial_started = time.perf_counter()
    serial_raw = []
    for task in tasks:
        evaluation = dd274._evaluate(
            context,
            reference,
            memory,
            np.asarray(task.coordinates, dtype=float),
            timestep_sec,
            specified_duty,
            task.state_id,
        )
        serial_raw.append(
            ColoredCentralDifferenceResult(
                order=int(task.order),
                residual=tuple(float(value) for value in evaluation.scaled),
            )
        )
    serial_matrix = assemble_colored_central_difference_jacobian(
        tasks,
        serial_raw,
        pattern=pattern,
        step=float(difference_step),
    )
    serial_wall = time.perf_counter() - serial_started
    serial_calls = int(audit.record_count - serial_before)
    serial_provider = audit.report()

    mp_context = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(worker_count),
        mp_context=mp_context,
        initializer=_worker_initialize,
    ) as pool:
        pings = [pool.submit(_worker_ping, ping_delay_sec) for _ in range(worker_count)]
        startup_ids = sorted({int(item.result()) for item in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(startup_raw - float(ping_delay_sec), 0.0)
        parallel_started = time.perf_counter()
        work = [
            {
                "task": task,
                "method": "backward_euler",
                "root_epoch": "core_v3_dynamic_pressure_benchmark:root_1",
                "reference": _reference_payload(reference),
                "memory": np.asarray(memory, dtype=float).tolist(),
                "timestep_sec": timestep_sec,
                "specified_duty": specified_duty,
            }
            for task in tasks
        ]
        parallel_raw = list(pool.map(_worker_evaluate, work, chunksize=1))
        parallel_wall = time.perf_counter() - parallel_started

    parallel_matrix = assemble_colored_central_difference_jacobian(
        tasks,
        [
            ColoredCentralDifferenceResult(
                order=int(item["order"]),
                residual=tuple(float(value) for value in item["residual"]),
            )
            for item in parallel_raw
        ],
        pattern=pattern,
        step=float(difference_step),
    )
    serial_rank, serial_condition, serial_singular = dd249._rank_condition(serial_matrix)
    parallel_rank, parallel_condition, parallel_singular = dd249._rank_condition(
        parallel_matrix
    )
    maximum_difference = float(np.max(np.abs(serial_matrix - parallel_matrix)))
    relative_difference = dd249._relative_change(serial_matrix, parallel_matrix)
    spectrum_difference = dd249._relative_change(serial_singular, parallel_singular)
    worker_ids = sorted({int(item["process_id"]) for item in parallel_raw})
    parallel_calls = int(sum(int(item["logical_provider_calls"]) for item in parallel_raw))
    parallel_ratio = parallel_wall / serial_wall
    projected_1200_root_ratio = (
        startup_adjusted + 1200.0 * parallel_wall
    ) / (1200.0 * serial_wall)
    gates = {
        "shape": pattern.shape == (262, 262) and len(groups) == 16 and len(tasks) == 32,
        "process_isolation": len(startup_ids) == worker_count and len(worker_ids) == worker_count,
        "matrix_exact": maximum_difference <= 1.0e-10,
        "matrix_relative": relative_difference <= 1.0e-10,
        "spectrum": spectrum_difference <= 1.0e-8,
        "rank": serial_rank == parallel_rank == 262,
        "condition": max(serial_condition, parallel_condition) < 1.0e8,
        "provider": bool(serial_provider["pass"])
        and not bool(serial_provider["fallback_attempted"])
        and all(bool(item["provider_pass"]) for item in parallel_raw)
        and not any(bool(item["fallback_attempted"]) for item in parallel_raw),
        "logical_work_parity": serial_calls == parallel_calls,
        "matrix_speed": parallel_ratio <= 0.80,
        "projected_long_run_speed": projected_1200_root_ratio <= 0.80,
    }
    return {
        "schema": SCHEMA,
        "checkpoint": str(checkpoint),
        "checkpoint_final_time_s": float(metadata["final_time_s"]),
        "matrix_shape": list(pattern.shape),
        "color_count": len(groups),
        "task_count": len(tasks),
        "worker_count": int(worker_count),
        "serial": {
            "wall_s": serial_wall,
            "logical_provider_calls": serial_calls,
            "rank": serial_rank,
            "condition": serial_condition,
        },
        "parallel": {
            "wall_s": parallel_wall,
            "logical_provider_calls": parallel_calls,
            "rank": parallel_rank,
            "condition": parallel_condition,
            "worker_ids": worker_ids,
            "startup_worker_ids": startup_ids,
        },
        "comparison": {
            "matrix_max_abs_difference": maximum_difference,
            "matrix_relative_difference": relative_difference,
            "spectrum_relative_difference": spectrum_difference,
            "parallel_matrix_speedup": 1.0 / parallel_ratio,
            "startup_wall_s_adjusted": startup_adjusted,
            "projected_1200_root_speedup": 1.0 / projected_1200_root_ratio,
        },
        "gates": gates,
        "pass_gate": all(gates.values()),
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--difference-step", type=float, default=1.0e-5)
    parser.add_argument("--ping-delay-sec", type=float, default=0.15)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.workers < 1:
        raise ValueError("worker count must be positive")
    report = benchmark(
        workbook=args.excel,
        checkpoint=args.checkpoint,
        worker_count=args.workers,
        difference_step=args.difference_step,
        ping_delay_sec=args.ping_delay_sec,
    )
    output = args.output
    if output is None:
        output = ROOT / "logs" / (
            "core_v3_dynamic_pressure_parallel_jacobian_benchmark_"
            + time.strftime("%Y%m%d_%H%M%S")
            + ".json"
        )
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **report["comparison"], "gates": report["gates"]}, indent=2))
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
