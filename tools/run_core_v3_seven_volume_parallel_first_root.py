#!/usr/bin/env python
"""Prepare or execute DD-182's serial/parallel seven-volume root proof."""

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

import benchmark_core_v3_seven_volume_parallel_jacobian as dd181  # noqa: E402
import run_core_v3_seven_volume_physical_modest_trajectory as dd178  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
    contract_sparsity_pattern,
)
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    BackwardEulerEvaluation,
    solve_backward_euler_step,
)
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)


SCHEMA = "dd182-core-v3-seven-volume-parallel-first-root-contract-v1"
RESULT_SCHEMA = "dd182-core-v3-seven-volume-parallel-first-root-result-v1"
DD181_CONTRACT = Path(
    "logs/dd181_core_v3_seven_volume_parallel_jacobian_benchmark_contract_20260812.json"
)
DD181_RESULT = Path(
    "logs/dd181_core_v3_seven_volume_parallel_jacobian_benchmark_20260812.json"
)
CONTRACT = Path(
    "logs/dd182_core_v3_seven_volume_parallel_first_root_contract_20260812.json"
)
RESULT = Path(
    "logs/dd182_core_v3_seven_volume_parallel_first_root_20260812.json"
)
CONTRACT_DOC = Path(
    "docs/dd_182_core_v3_seven_volume_parallel_first_root_contract_20260812.md"
)
RESULT_DOC = Path(
    "docs/dd_182_core_v3_seven_volume_parallel_first_root_20260812.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "tests/test_core_v3_implicit_step_v1.py",
    "tests/test_core_v3_seven_volume_parallel_first_root.py",
    "tools/run_core_v3_seven_volume_parallel_first_root.py",
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


def _matrix_sha(matrix: Any) -> str:
    return hashlib.sha256(np.asarray(matrix, dtype="<f8").tobytes()).hexdigest()


def _maximum_absolute_difference(first: Any, second: Any) -> float:
    a = np.asarray(first, dtype=float)
    b = np.asarray(second, dtype=float)
    if a.shape != b.shape:
        raise ValueError("comparison arrays have different shapes")
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def _context(payload: Mapping[str, Any]):
    spec = dd178.dd177.dd175.dd173.dd172.dd171.dd168._spec(
        payload["disturbed_source_mapping"],
        float(payload["disturbed_operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd178.dd177.dd175.dd173.dd172.dd171.dd168._reference(
        payload["reference"]
    )
    state = dd178.dd177.dd175.dd173.dd172.dd171._state(
        payload["accepted_root_state"]
    )
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=payload["accepted_root_artifact"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-182 seven-volume contract changed")
    provider = dd178.dd177.dd175.dd173.dd172.dd171._provider(
        Path(payload["workbook"]), payload["property_package"]
    )
    provider.set_exact_state_memoization(True, clear=True)
    return spec, reference, state, contract, provider, ProviderCallAudit()


def _outcome_comparison(serial: Any, parallel: Any) -> dict[str, Any]:
    serial_eval = serial.evaluation
    parallel_eval = parallel.evaluation
    if not isinstance(serial_eval, BackwardEulerEvaluation) or not isinstance(
        parallel_eval, BackwardEulerEvaluation
    ):
        raise TypeError("DD-182 outcomes must contain backward-Euler evaluations")
    return {
        "success_equal": serial.success == parallel.success,
        "status_equal": serial.status == parallel.status,
        "message_equal": serial.message == parallel.message,
        "nfev_equal": serial.nfev == parallel.nfev,
        "njev_equal": serial.njev == parallel.njev,
        "cost_difference": abs(float(serial.cost) - float(parallel.cost)),
        "optimality_difference": abs(
            float(serial.optimality) - float(parallel.optimality)
        ),
        "initial_coordinate_max_abs": _maximum_absolute_difference(
            serial.initial_coordinates, parallel.initial_coordinates
        ),
        "final_coordinate_max_abs": _maximum_absolute_difference(
            serial.final_coordinates, parallel.final_coordinates
        ),
        "final_residual_max_abs": _maximum_absolute_difference(
            serial.final_residual, parallel.final_residual
        ),
        "returned_jacobian_max_abs": _maximum_absolute_difference(
            serial.jacobian, parallel.jacobian
        ),
        "endpoint_inventory_max_abs_lbmol": _maximum_absolute_difference(
            serial_eval.endpoint_inventory_lbmol,
            parallel_eval.endpoint_inventory_lbmol,
        ),
        "component_rate_max_abs_lbmolph": _maximum_absolute_difference(
            serial_eval.component_rate_lbmolph,
            parallel_eval.component_rate_lbmolph,
        ),
        "algebraic_coordinate_max_abs": _maximum_absolute_difference(
            serial_eval.algebraic_coordinates,
            parallel_eval.algebraic_coordinates,
        ),
        "endpoint_energy_max_abs_BTU": _maximum_absolute_difference(
            serial_eval.endpoint_internal_energy_BTU,
            parallel_eval.endpoint_internal_energy_BTU,
        ),
        "energy_storage_rate_max_abs_BTUph": _maximum_absolute_difference(
            serial_eval.energy_storage_rate_BTUph,
            parallel_eval.energy_storage_rate_BTUph,
        ),
    }


def _outcome_summary(outcome: Any) -> dict[str, Any]:
    values = np.linalg.svd(np.asarray(outcome.jacobian, dtype=float), compute_uv=False)
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
        "jacobian_sha256": _matrix_sha(outcome.jacobian),
        "jacobian_rank": int(np.linalg.matrix_rank(outcome.jacobian)),
        "jacobian_condition": float(values[0] / values[-1]),
    }


def prepare() -> dict[str, Any]:
    source = _load(DD181_CONTRACT)
    prior = _load(DD181_RESULT)
    if (
        prior.get("pass_gate") is not True
        or prior.get("decision") != "authorize_persistent_parallel_step_solver_design"
    ):
        raise RuntimeError("DD-182 requires the passing DD-181 decision")
    payload = {
        key: value
        for key, value in source.items()
        if key
        not in {
            "schema_id",
            "preparation_base_commit",
            "sources",
            "dd180_runtime_accounting",
            "implementation_sha256",
            "hard_stops",
            "contract_payload_sha256",
            "property_evaluation_attempted",
            "nonlinear_solve_attempted",
            "timestep_attempted",
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
                for path in (DD181_CONTRACT, DD181_RESULT)
            },
            "integration": {
                "state": "DD-180 first coarse implicit root",
                "step_seconds": 0.25,
                "serial_roots": 1,
                "parallel_roots": 1,
                "worker_count": 4,
                "persistent_pool_count": 1,
                "spawn_context": True,
                "startup_ping_delay_sec": 0.15,
                "exact_matrix_limit": 0.0,
                "solver_decision_limit": 0.0,
                "endpoint_absolute_limit": 1.0e-12,
                "residual_limit": 1.0e-8,
                "rank": 54,
                "condition_limit": 1.0e8,
                "parallel_solve_time_ratio_limit": 0.90,
                "main_logical_provider_call_limit_each": 10000,
                "worker_logical_provider_call_limit": 10000,
                "wall_clock_limit_sec": 120.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "a DD-181 source or DD-182 implementation hash changes",
                "the serial and parallel roots do not use the same equation, solver, scale, step, state, and main-process residual path",
                "the four workers do not own isolated DWSIM provider instances",
                "any corresponding Jacobian, SciPy decision, or endpoint differs beyond its frozen limit",
                "either root fails closure, rank, condition, physicality, conservation, or provider ownership",
                "parallel solve time excluding startup is not at least 10 percent faster",
                "a retry, state acceptance, second timestep, controller, or trajectory occurs",
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
                "# DD-182 Seven-Volume Parallel First-Root Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Root: DD-180 first `0.25 s` coarse implicit root",
                "- Solves: one serial and one persistent four-worker parallel root",
                "- Main process: identical SciPy residual, trust-region, and acceptance path",
                "- Delegated work: only 17-color central-difference perturbation residuals",
                "- Equivalence: every requested Jacobian exact; endpoint within `1e-12`",
                "- Performance: parallel solve excluding startup at least `10%` faster",
                "- State acceptance, second timestep, controller, trajectory, and retry: prohibited",
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
        raise RuntimeError("DD-182 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-182 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-182 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-182 result exists; rerun is prohibited")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    limits = payload["integration"]
    serial_context = _context(payload)
    parallel_context = _context(payload)
    serial_spec, serial_reference, serial_state, contract, serial_provider, serial_audit = (
        serial_context
    )
    (
        parallel_spec,
        parallel_reference,
        parallel_state,
        parallel_contract,
        parallel_provider,
        parallel_audit,
    ) = parallel_context
    pattern, _names = contract_sparsity_pattern(
        contract, include_state_rate_dependencies=True
    )
    parallel_pattern, _parallel_names = contract_sparsity_pattern(
        parallel_contract, include_state_rate_dependencies=True
    )
    if not np.array_equal(pattern, parallel_pattern):
        raise RuntimeError("DD-182 serial and parallel sparsity differ")
    settings = dd178.dd177.dd175.dd173.dd172._settings(payload)
    serial_matrices: list[np.ndarray] = []
    serial_jacobian_times: list[float] = []
    parallel_matrices: list[np.ndarray] = []
    parallel_jacobian_times: list[float] = []
    parallel_worker_evidence: list[dict[str, Any]] = []

    def serial_builder(objective, point, state_id):
        started = time.perf_counter()
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=settings.jacobian_step,
            state_id=state_id,
        )
        if len(groups) != 17:
            raise RuntimeError("DD-182 serial color count changed")
        serial_jacobian_times.append(float(time.perf_counter() - started))
        serial_matrices.append(matrix.copy())
        return matrix

    context = mp.get_context("spawn")
    total_started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(limits["worker_count"]),
        mp_context=context,
        initializer=dd181._worker_initialize,
        initargs=(str((ROOT / CONTRACT).resolve()),),
    ) as pool:
        pings = [
            pool.submit(dd181._worker_ping, limits["startup_ping_delay_sec"])
            for _ in range(int(limits["worker_count"]))
        ]
        worker_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(limits["startup_ping_delay_sec"]), 0.0
        )

        serial = solve_backward_euler_step(
            contract,
            serial_spec,
            serial_reference,
            serial_state,
            serial_provider,
            serial_audit,
            previous_inventory_lbmol=inventory_from_state(serial_state),
            initial_algebraic_coordinates=dynamic_algebraic_coordinates(
                serial_spec, serial_reference, serial_state
            ),
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step_seconds=float(limits["step_seconds"]),
            settings=settings,
            name="dd182:serial",
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
            raw = list(pool.map(dd181._worker_evaluate, tasks, chunksize=1))
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
            parallel_jacobian_times.append(float(time.perf_counter() - started))
            parallel_matrices.append(matrix.copy())
            parallel_worker_evidence.append(
                {
                    "color_count": len(groups),
                    "task_count": len(raw),
                    "worker_ids": sorted({int(item["process_id"]) for item in raw}),
                    "logical_provider_calls": int(
                        sum(item["logical_provider_calls"] for item in raw)
                    ),
                    "memo_hits": int(sum(item["memo_hits"] for item in raw)),
                    "memo_misses": int(sum(item["memo_misses"] for item in raw)),
                }
            )
            return matrix

        parallel = solve_backward_euler_step(
            parallel_contract,
            parallel_spec,
            parallel_reference,
            parallel_state,
            parallel_provider,
            parallel_audit,
            previous_inventory_lbmol=inventory_from_state(parallel_state),
            initial_algebraic_coordinates=dynamic_algebraic_coordinates(
                parallel_spec, parallel_reference, parallel_state
            ),
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step_seconds=float(limits["step_seconds"]),
            settings=settings,
            name="dd182:parallel",
            jacobian_builder=parallel_builder,
        )
    total_wall = time.perf_counter() - total_started

    if len(serial_matrices) != len(parallel_matrices):
        pair_differences = [float("inf")]
    else:
        pair_differences = [
            _maximum_absolute_difference(a, b)
            for a, b in zip(serial_matrices, parallel_matrices, strict=True)
        ]
    comparison = _outcome_comparison(serial, parallel)
    serial_summary = _outcome_summary(serial)
    parallel_summary = _outcome_summary(parallel)
    serial_provider_summary = serial_audit.report()
    parallel_provider_summary = parallel_audit.report()
    worker_calls = sum(
        item["logical_provider_calls"] for item in parallel_worker_evidence
    )
    solve_ratio = parallel.wall_clock_sec / serial.wall_clock_sec
    endpoint_fields = (
        "initial_coordinate_max_abs",
        "final_coordinate_max_abs",
        "final_residual_max_abs",
        "returned_jacobian_max_abs",
        "endpoint_inventory_max_abs_lbmol",
        "component_rate_max_abs_lbmolph",
        "algebraic_coordinate_max_abs",
        "endpoint_energy_max_abs_BTU",
        "energy_storage_rate_max_abs_BTUph",
    )
    gates = {
        "root_success": serial.success and parallel.success,
        "root_residual": serial_summary["residual_inf_norm"] < limits["residual_limit"]
        and parallel_summary["residual_inf_norm"] < limits["residual_limit"],
        "root_rank_condition": serial_summary["jacobian_rank"] == limits["rank"]
        and parallel_summary["jacobian_rank"] == limits["rank"]
        and serial_summary["jacobian_condition"] < limits["condition_limit"]
        and parallel_summary["jacobian_condition"] < limits["condition_limit"],
        "jacobian_count": len(serial_matrices) == len(parallel_matrices) > 0,
        "every_jacobian_exact": max(pair_differences) <= limits["exact_matrix_limit"],
        "solver_decisions_exact": all(
            comparison[key]
            for key in (
                "success_equal",
                "status_equal",
                "message_equal",
                "nfev_equal",
                "njev_equal",
            )
        )
        and comparison["cost_difference"] <= limits["solver_decision_limit"]
        and comparison["optimality_difference"] <= limits["solver_decision_limit"],
        "endpoint_equivalence": all(
            comparison[key] <= limits["endpoint_absolute_limit"]
            for key in endpoint_fields
        ),
        "process_isolation": len(worker_ids) == limits["worker_count"]
        and all(
            len(item["worker_ids"]) == limits["worker_count"]
            for item in parallel_worker_evidence
        ),
        "task_ownership": all(
            item["color_count"] == 17 and item["task_count"] == 34
            for item in parallel_worker_evidence
        ),
        "provider": serial_provider_summary["pass"]
        and parallel_provider_summary["pass"],
        "provider_calls": serial_provider_summary["total_calls"]
        < limits["main_logical_provider_call_limit_each"]
        and parallel_provider_summary["total_calls"]
        < limits["main_logical_provider_call_limit_each"]
        and worker_calls < limits["worker_logical_provider_call_limit"],
        "meaningful_speed": solve_ratio
        <= limits["parallel_solve_time_ratio_limit"],
        "wall_clock": total_wall < limits["wall_clock_limit_sec"],
        "no_state_advance_or_controller": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "persistent_parallel_first_root_exact_and_faster"
            if passed
            else "persistent_parallel_first_root_failed"
        ),
        "decision": (
            "authorize_persistent_parallel_short_trajectory_contract"
            if passed
            else "retain_serial_solver"
        ),
        "serial": serial_summary,
        "parallel": parallel_summary,
        "comparison": comparison,
        "jacobian_evaluations": len(serial_matrices),
        "jacobian_pair_max_abs_differences": pair_differences,
        "serial_jacobian_wall_sec": serial_jacobian_times,
        "parallel_jacobian_wall_sec": parallel_jacobian_times,
        "serial_total_jacobian_wall_sec": float(sum(serial_jacobian_times)),
        "parallel_total_jacobian_wall_sec": float(sum(parallel_jacobian_times)),
        "parallel_solve_time_ratio": float(solve_ratio),
        "parallel_solve_speedup": float(1.0 / solve_ratio),
        "worker_ids": worker_ids,
        "worker_evidence": parallel_worker_evidence,
        "worker_logical_provider_calls": int(worker_calls),
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "total_wall_clock_sec": float(total_wall),
        "serial_provider": serial_provider_summary,
        "parallel_provider": parallel_provider_summary,
        "gates": gates,
        "pass_gate": bool(passed),
        "campaign_executed_once": True,
        "serial_roots_executed": 1,
        "parallel_roots_executed": 1,
        "state_advance_attempted": False,
        "controller_attempted": False,
        "trajectory_attempted": False,
        "retry_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-182 Seven-Volume Parallel First-Root Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Serial/parallel residual: `{serial_summary['residual_inf_norm']:.6e}` / `{parallel_summary['residual_inf_norm']:.6e}`",
                f"- Serial/parallel `nfev,njev`: `{serial.nfev},{serial.njev}` / `{parallel.nfev},{parallel.njev}`",
                f"- Jacobian evaluations: `{len(serial_matrices)}` each",
                f"- Worst paired Jacobian difference: `{max(pair_differences):.6e}`",
                f"- Final-coordinate difference: `{comparison['final_coordinate_max_abs']:.6e}`",
                f"- Serial/parallel solve wall: `{serial.wall_clock_sec:.6f} s` / `{parallel.wall_clock_sec:.6f} s`",
                f"- Parallel solve speedup excluding startup: `{result['parallel_solve_speedup']:.3f}x`",
                f"- Persistent-pool startup: `{startup_adjusted:.3f} s` adjusted",
                f"- Gates: `{gates}`",
                "",
                "The main process retained the same SciPy residual, trust-region decisions, convergence test, and endpoint evaluation. Only colored-Jacobian perturbation residuals were delegated. No endpoint was accepted as a state advance.",
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
                    "jacobian_evaluations",
                    "parallel_solve_speedup",
                    "total_wall_clock_sec",
                    "pass_gate",
                }
            },
            indent=2,
        )
    )
    raise SystemExit(0 if args.prepare or output["pass_gate"] else 2)
