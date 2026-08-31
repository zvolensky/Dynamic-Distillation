#!/usr/bin/env python
"""Compare serial and persistent-parallel Core V3 pressure trajectories."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import benchmark_core_v3_dynamic_pressure_parallel_jacobian as matrix_benchmark  # noqa: E402
import run_core_v3_dynamic as production  # noqa: E402
import run_core_v3_vapor_holdup_dynamic_pressure_thirty_second_trajectory as dd274  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402

from dynamic_distillation.core_v3.persistent_parallel_colored_jacobian_v1 import (  # noqa: E402
    PersistentParallelColoredJacobian,
)


SCHEMA = "core-v3-dynamic-pressure-parallel-trajectory-benchmark-v1"


def _endpoint_arrays(evaluation: Any) -> dict[str, np.ndarray]:
    endpoint = evaluation.base.endpoint
    return {
        "liquid_inventory": np.asarray(
            endpoint.liquid_component_inventory_lbmol, dtype=float
        ),
        "vapor_inventory": np.asarray(
            endpoint.vapor_component_inventory_lbmol, dtype=float
        ),
        "phase_transfer": np.asarray(endpoint.phase_transfer_lbmolph, dtype=float),
        "temperature": np.asarray(endpoint.temperature_F, dtype=float),
        "pressure": np.asarray(endpoint.pressure_psia, dtype=float),
        "liquid_flow": np.asarray(endpoint.hydraulic_liquid_flow_lbmolph, dtype=float),
        "vapor_flow": np.asarray(endpoint.vapor_flow_lbmolph, dtype=float),
        "liquid_rate": np.asarray(endpoint.liquid_component_rate_lbmolph, dtype=float),
        "vapor_rate": np.asarray(endpoint.vapor_component_rate_lbmolph, dtype=float),
        "condenser_duty": np.asarray([endpoint.condenser_duty_BTUph], dtype=float),
        "controller_memory": np.asarray(
            evaluation.controller_memory_endpoint, dtype=float
        ),
        "controller_rate": np.asarray(evaluation.controller_rate_per_sec, dtype=float),
        "product_log_ratio": np.asarray(evaluation.product_log_ratio, dtype=float),
        "scaled_residual": np.asarray(evaluation.scaled, dtype=float),
    }


def _maximum_endpoint_difference(left: Any, right: Any) -> tuple[float, dict[str, float]]:
    left_arrays = _endpoint_arrays(left)
    right_arrays = _endpoint_arrays(right)
    differences = {
        name: float(np.max(np.abs(left_arrays[name] - right_arrays[name])))
        for name in left_arrays
    }
    return max(differences.values()), differences


def _accepted(report: Mapping[str, Any], expected_rank: int) -> bool:
    return bool(
        report["scipy_success"]
        and report["scaled_residual_inf_norm"] < 1.0e-8
        and report["jacobian_rank"] == expected_rank
        and report["jacobian_condition"] < 1.0e8
        and report["physical_pass"]
    )


def _solve_parallel_endpoint(
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    reference: Any,
    memory: np.ndarray,
    previous_coordinates: np.ndarray,
    previous_evaluation: Any,
    timestep_sec: float,
    specified_duty: float,
    root_name: str,
    jacobians: PersistentParallelColoredJacobian,
) -> tuple[np.ndarray, Any, dict[str, Any], np.ndarray]:
    lower, upper = dd274.dd267.dd265._bounds(context["contract"])
    point = dd274.controlled_implicit_initial_coordinates(
        context["contract"],
        controller_rates_per_sec=previous_evaluation.controller_rate_per_sec,
        timestep_sec=timestep_sec,
        previous_coordinates=previous_coordinates,
        product_log_ratios_previous=previous_evaluation.product_log_ratio,
    )
    cached_matrix: np.ndarray | None = None
    calls = 0

    def objective(candidate: np.ndarray, state_id: str = "residual") -> np.ndarray:
        nonlocal calls
        calls += 1
        return dd274._evaluate(
            context,
            reference,
            memory,
            candidate,
            timestep_sec,
            specified_duty,
            f"{root_name}:{state_id}:{calls}",
        ).scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal cached_matrix
        if cached_matrix is None:
            cached_matrix = jacobians.build(
                candidate,
                f"{root_name}:jacobian",
                method="backward_euler",
                root_epoch=root_name,
                work_basis={
                    "reference": matrix_benchmark._reference_payload(reference),
                    "memory": np.asarray(memory, dtype=float).tolist(),
                    "timestep_sec": float(timestep_sec),
                    "specified_duty": float(specified_duty),
                },
            )
        return cached_matrix

    solution = least_squares(
        objective,
        point,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        x_scale=float(payload["solver"]["x_scale"]),
        ftol=float(payload["solver"]["ftol"]),
        xtol=float(payload["solver"]["xtol"]),
        gtol=float(payload["solver"]["gtol"]),
        max_nfev=int(payload["solver"]["max_nfev_per_root"]),
        verbose=0,
    )
    final = dd274._evaluate(
        context,
        reference,
        memory,
        solution.x,
        timestep_sec,
        specified_duty,
        f"{root_name}:accepted",
        "residual",
    )
    if cached_matrix is None:
        raise RuntimeError("parallel endpoint did not build a Jacobian")
    rank, condition, _ = dd249._rank_condition(cached_matrix)
    report = {
        "scipy_success": bool(solution.success),
        "scipy_status": int(solution.status),
        "nfev": int(solution.nfev),
        "njev": int(solution.njev or 0),
        "function_calls_observed": int(calls),
        "jacobian_build_count": 1,
        "color_count": int(jacobians.evidence[-1].color_count),
        "scaled_residual_inf_norm": float(np.max(np.abs(final.scaled))),
        "jacobian_rank": int(rank),
        "jacobian_condition": float(condition),
        "physical_pass": bool(dd274.dd267._physical(final)),
    }
    return solution.x.copy(), final, report, cached_matrix


def _run_path(
    *,
    name: str,
    context: Mapping[str, Any],
    metadata: Mapping[str, Any],
    reference: Any,
    memory: np.ndarray,
    coordinates: np.ndarray,
    prior: Any,
    payload: Mapping[str, Any],
    steps: int,
    solve: Any,
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    evaluations: list[Any] = []
    matrices: list[np.ndarray] = []
    coordinate_history: list[np.ndarray] = []
    started = time.perf_counter()
    for index in range(1, steps + 1):
        coordinates, final, report, matrix = solve(
            context,
            payload,
            reference,
            memory,
            coordinates,
            prior,
            production.ACCEPTED_TIMESTEP_SEC,
            float(metadata["specified_condenser_duty_BTUph"]),
            f"parallel_trajectory_benchmark:{name}:root_{index}",
        )
        reports.append(dict(report))
        evaluations.append(final)
        matrices.append(np.asarray(matrix, dtype=float))
        coordinate_history.append(np.asarray(coordinates, dtype=float).copy())
        reference = dd249._next_reference(reference, final.base)
        memory = final.controller_memory_endpoint.copy()
        prior = final
    return {
        "wall_s": time.perf_counter() - started,
        "coordinates": coordinates,
        "coordinate_history": coordinate_history,
        "reports": reports,
        "evaluations": evaluations,
        "matrices": matrices,
    }


def benchmark(
    *,
    workbook: Path,
    checkpoint: Path,
    worker_count: int,
    steps: int,
    ping_delay_sec: float,
) -> dict[str, Any]:
    workbook = workbook.expanduser().resolve()
    checkpoint = checkpoint.expanduser().resolve()
    payload = json.loads((ROOT / dd274.CONTRACT).read_text(encoding="utf-8"))
    serial_context = production._context()
    parallel_context = production._context()
    serial_state = production._load_checkpoint(
        checkpoint, workbook=workbook, context=serial_context
    )
    parallel_state = production._load_checkpoint(
        checkpoint, workbook=workbook, context=parallel_context
    )
    serial = _run_path(
        name="serial",
        context=serial_context,
        metadata=serial_state[0],
        reference=serial_state[1],
        memory=serial_state[2],
        coordinates=serial_state[3],
        prior=serial_state[4],
        payload=payload,
        steps=steps,
        solve=dd274._solve_endpoint,
    )

    pattern = dd274.vapor_holdup_terminal_control_pattern(parallel_context["contract"])
    mp_context = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=mp_context,
        initializer=matrix_benchmark._worker_initialize,
    ) as pool:
        pings = [
            pool.submit(matrix_benchmark._worker_ping, ping_delay_sec)
            for _ in range(worker_count)
        ]
        startup_ids = sorted({int(item.result()) for item in pings})
        startup_wall = max(time.perf_counter() - pool_started - ping_delay_sec, 0.0)
        jacobians = PersistentParallelColoredJacobian(
            pool,
            matrix_benchmark._worker_evaluate,
            pattern=pattern,
            step=float(payload["solver"]["difference_step"]),
            worker_count=worker_count,
            require_all_workers=True,
        )

        def parallel_solve(*args: Any):
            return _solve_parallel_endpoint(*args, jacobians=jacobians)

        parallel = _run_path(
            name="parallel",
            context=parallel_context,
            metadata=parallel_state[0],
            reference=parallel_state[1],
            memory=parallel_state[2],
            coordinates=parallel_state[3],
            prior=parallel_state[4],
            payload=payload,
            steps=steps,
            solve=parallel_solve,
        )

    matrix_differences = [
        float(np.max(np.abs(left - right)))
        for left, right in zip(serial["matrices"], parallel["matrices"], strict=True)
    ]
    coordinate_differences = [
        float(np.max(np.abs(left - right)))
        for left, right in zip(
            serial["coordinate_history"],
            parallel["coordinate_history"],
            strict=True,
        )
    ]
    endpoint_differences = [
        _maximum_endpoint_difference(left, right)[0]
        for left, right in zip(
            serial["evaluations"], parallel["evaluations"], strict=True
        )
    ]
    solver_decisions_equal = all(
        left["scipy_status"] == right["scipy_status"]
        and left["nfev"] == right["nfev"]
        and left["njev"] == right["njev"]
        for left, right in zip(serial["reports"], parallel["reports"], strict=True)
    )
    expected_rank = len(serial_context["contract"].rows)
    parallel_ratio = parallel["wall_s"] / serial["wall_s"]
    governed_ratio = (startup_wall + parallel["wall_s"]) / serial["wall_s"]
    jacobian_worker_ids = sorted(
        {worker_id for item in jacobians.evidence for worker_id in item.worker_ids}
    )
    gates = {
        "paths_complete": len(serial["reports"]) == len(parallel["reports"]) == steps,
        "scientific_endpoints": all(
            _accepted(item, expected_rank)
            for item in serial["reports"] + parallel["reports"]
        ),
        "solver_decisions_equal": solver_decisions_equal,
        "jacobians_exact": max(matrix_differences) <= 1.0e-10,
        "coordinates_exact": max(coordinate_differences) <= 1.0e-10,
        "endpoints_exact": max(endpoint_differences) <= 1.0e-10,
        "process_isolation": len(jacobian_worker_ids) == worker_count
        and all(len(item.worker_ids) == worker_count for item in jacobians.evidence),
        "provider": serial_context["audit"].report()["pass"]
        and parallel_context["audit"].report()["pass"]
        and all(item.provider_pass and not item.fallback_attempted for item in jacobians.evidence),
        "parallel_path_faster": parallel_ratio <= 0.80,
    }
    return {
        "schema": SCHEMA,
        "checkpoint": str(checkpoint),
        "steps_per_path": int(steps),
        "worker_count": int(worker_count),
        "serial": {"wall_s": serial["wall_s"], "reports": serial["reports"]},
        "parallel": {
            "wall_s": parallel["wall_s"],
            "startup_wall_s_adjusted": startup_wall,
            "reports": parallel["reports"],
            "startup_ping_worker_ids": startup_ids,
            "jacobian_worker_ids": jacobian_worker_ids,
        },
        "comparison": {
            "parallel_path_speedup": 1.0 / parallel_ratio,
            "governed_speedup_including_startup": 1.0 / governed_ratio,
            "matrix_max_abs_difference": max(matrix_differences),
            "coordinate_max_abs_difference": max(coordinate_differences),
            "endpoint_max_abs_difference": max(endpoint_differences),
        },
        "gates": gates,
        "pass_gate": all(gates.values()),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--ping-delay-sec", type=float, default=0.15)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.workers < 1 or args.steps < 1:
        raise ValueError("workers and steps must be positive")
    report = benchmark(
        workbook=args.excel,
        checkpoint=args.checkpoint,
        worker_count=args.workers,
        steps=args.steps,
        ping_delay_sec=args.ping_delay_sec,
    )
    output = args.output or ROOT / "logs" / (
        "core_v3_dynamic_pressure_parallel_trajectory_benchmark_"
        + time.strftime("%Y%m%d_%H%M%S")
        + ".json"
    )
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"output": str(output), **report["comparison"], "gates": report["gates"]},
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
