#!/usr/bin/env python
"""Prepare or execute DD-205's persistent-pool replay of DD-202."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_trajectory as dd202  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence as dd204  # noqa: E402
from dynamic_distillation.core_v3.parallel_colored_jacobian_v1 import (  # noqa: E402
    ColoredCentralDifferenceResult,
    assemble_colored_central_difference_jacobian,
    build_colored_central_difference_tasks,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_residual_v1 import (  # noqa: E402
    solve_terminal_inventory_control_bdf2_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_trajectory_v1 import (  # noqa: E402
    run_terminal_inventory_control_bdf2_trajectory,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    solve_terminal_inventory_control_backward_euler_step,
    terminal_inventory_control_step_pattern,
)


SCHEMA = "dd205-core-v3-controlled-bdf2-parallel-replay-contract-v1"
RESULT_SCHEMA = "dd205-core-v3-controlled-bdf2-parallel-replay-result-v1"
DD202_CONTRACT = dd204.DD202_CONTRACT
DD202_RESULT = dd204.DD202_RESULT
DD204_RESULT = Path(
    "logs/dd204_core_v3_terminal_inventory_control_bdf2_parallel_equivalence_20260814.json"
)
CONTRACT = Path(
    "logs/dd205_core_v3_terminal_inventory_control_bdf2_parallel_replay_contract_20260814.json"
)
RESULT = Path(
    "logs/dd205_core_v3_terminal_inventory_control_bdf2_parallel_replay_20260814"
)
CONTRACT_DOC = Path(
    "docs/dd_205_core_v3_terminal_inventory_control_bdf2_parallel_replay_contract_20260814.md"
)
RESULT_DOC = Path(
    "docs/dd_205_core_v3_terminal_inventory_control_bdf2_parallel_replay_20260814.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_residual_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "tests/test_core_v3_terminal_inventory_control_bdf2_parallel_replay.py",
    "tools/run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence.py",
    "tools/run_core_v3_terminal_inventory_control_bdf2_parallel_replay.py",
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


def _json_comparison(expected: Any, actual: Any) -> dict[str, Any]:
    numeric_differences: list[tuple[str, float]] = []
    metadata_mismatches: list[str] = []

    def compare(first: Any, second: Any, path: str) -> None:
        if isinstance(first, Mapping):
            if not isinstance(second, Mapping) or set(first) != set(second):
                metadata_mismatches.append(path or "<root>")
                return
            for key in sorted(first):
                compare(first[key], second[key], f"{path}.{key}" if path else key)
            return
        if isinstance(first, list):
            if not isinstance(second, list) or len(first) != len(second):
                metadata_mismatches.append(path)
                return
            for index, (left, right) in enumerate(zip(first, second, strict=True)):
                compare(left, right, f"{path}[{index}]")
            return
        if (
            isinstance(first, (int, float))
            and not isinstance(first, bool)
            and isinstance(second, (int, float))
            and not isinstance(second, bool)
        ):
            left = float(first)
            right = float(second)
            difference = abs(left - right)
            if not math.isfinite(difference):
                difference = 0.0 if left == right else float("inf")
            numeric_differences.append((path, difference))
            return
        if first != second:
            metadata_mismatches.append(path)

    compare(expected, actual, "")
    worst_path, maximum = max(
        numeric_differences, key=lambda item: item[1], default=(None, 0.0)
    )
    return {
        "metadata_equal": not metadata_mismatches,
        "metadata_mismatches": metadata_mismatches,
        "numeric_leaf_count": len(numeric_differences),
        "maximum_numeric_difference": float(maximum),
        "worst_numeric_path": worst_path,
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    performance = payload["performance_limits"]
    return "\n".join(
        (
            "# DD-205 Persistent-Parallel BDF2 Replay Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Replay: exact DD-202 `40 x 0.25 s` and `80 x 0.125 s` paths",
            "- Execution: one persistent four-worker DWSIM pool for all 120 roots",
            f"- Saved-result absolute agreement: `{performance['saved_result_absolute']}`",
            f"- Required trajectory speedup: `{performance['minimum_speedup']}x`",
            f"- In-execution deadline: `{performance['deadline_seconds']} s`",
            "- No equation, property, controller, solver, grid, tolerance, or fallback change is authorized.",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    performance = payload["performance"]
    comparison = payload["saved_result_comparison"]
    return "\n".join(
        (
            "# DD-205 Persistent-Parallel BDF2 Replay Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}`",
            f"- Saved-result maximum difference: `{comparison['maximum_numeric_difference']:.6e}`",
            f"- DD-202 / parallel trajectory wall: `{performance['dd202_wall_sec']:.6f}` / `{performance['trajectory_wall_sec']:.6f} s`",
            f"- Trajectory speedup: `{performance['speedup']:.3f}x`",
            f"- Adjusted startup / governed wall: `{performance['startup_wall_sec_adjusted']:.3f}` / `{performance['total_governed_wall_sec']:.3f} s`",
            f"- Logical provider calls: `{payload['logical_provider_calls']}`",
            "- Retry, tuning, alternate grid, or fallback: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = _load(DD202_CONTRACT)
    accepted = _load(DD202_RESULT)
    authorization = _load(DD204_RESULT)
    if not accepted["pass_gate"] or accepted["completed_roots"] != 120:
        raise RuntimeError("DD-205 requires the accepted 120-root DD-202 result")
    if not authorization["pass_gate"] or authorization["decision"] != (
        "authorize_persistent_parallel_bdf2_trajectory_path"
    ):
        raise RuntimeError("DD-205 requires accepted DD-204 parallel equivalence")
    payload = {
        key: source[key]
        for key in (
            "workbook",
            "workbook_sha256",
            "property_package",
            "source_mapping",
            "operating_spec",
            "reference",
            "accepted_root_state",
            "accepted_root_inventory_lbmol",
            "initial_solve_coordinates",
            "initial_controller_memory",
            "level_setpoints",
            "product_reference_lbmolph",
            "fixed_steady_residual_scales",
            "solver",
            "paths",
            "accuracy_baseline",
            "limits",
            "physical_refinement_limits",
            "required_rank",
            "signed_total_policy",
        )
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "result_schema_id": RESULT_SCHEMA,
            "campaign_id": "DD-205",
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD202_CONTRACT, DD202_RESULT, DD204_RESULT)
            },
            "parallel": {
                "worker_count": 4,
                "color_count": 17,
                "tasks_per_matrix": 34,
                "startup_ping_delay_sec": 0.15,
            },
            "performance_limits": {
                "saved_result_absolute": 1.0e-12,
                "minimum_speedup": 1.10,
                "logical_provider_calls": 650000,
                "startup_wall_sec": 30.0,
                "deadline_seconds": 180.0,
                "governed_wall_sec": 180.0,
            },
            "reference_result_wall_sec": float(accepted["wall_clock_sec"]),
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either accepted DD-202 path does not complete every root under its original gates",
                "any saved root, shared-time metric, response, or decision differs beyond the frozen limit",
                "any actual Jacobian omits a worker or each worker does not rebuild its basis exactly once per root",
                "the persistent-pool trajectory is not at least ten percent faster than DD-202",
                "the provider-call, startup, in-execution, or governed-wall ceiling is exceeded",
                "a retry, alternate grid, tuning, fallback, clipping, or projection occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "trajectory_attempted": False,
            "controller_tuning_attempted": False,
            "retry_authorized": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-205 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-205 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-205 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-205 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-205 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-205 result exists; rerun prohibited")
    _git("ls-files", "--error-unmatch", str(contract_path))


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    accepted = _load(DD202_RESULT)
    (
        spec,
        reference,
        state,
        controlled,
        provider,
        audit,
        inventory,
        memory,
        coordinates,
        setpoints,
        products,
    ) = dd204.dd191._context(payload)
    pattern = terminal_inventory_control_step_pattern(controlled)
    settings = dd202.base.dd187.dd186._settings(payload)
    parallel = payload["parallel"]
    performance_limits = payload["performance_limits"]
    worker_evidence: list[dict[str, Any]] = []

    spawn = mp.get_context("spawn")
    total_started = time.perf_counter()
    deadline = total_started + float(performance_limits["deadline_seconds"])
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(parallel["worker_count"]),
        mp_context=spawn,
        initializer=dd204._worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(dd204._worker_ping, parallel["startup_ping_delay_sec"])
            for _ in range(int(parallel["worker_count"]))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(parallel["startup_ping_delay_sec"]), 0.0
        )

        def parallel_builder(
            method: str, root_epoch: str, work_basis: Mapping[str, Any]
        ):
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
                        "method": method,
                        "root_epoch": root_epoch,
                        **work_basis,
                    }
                    for task in tasks
                ]
                raw = list(pool.map(dd204._worker_evaluate, work, chunksize=1))
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
                worker_evidence.append(
                    {
                        "method": method,
                        "root_epoch": root_epoch,
                        "state_id": state_id,
                        "color_count": len(groups),
                        "task_count": len(raw),
                        "worker_ids": sorted({int(item["process_id"]) for item in raw}),
                        "basis_rebuilds": int(
                            sum(bool(item["basis_rebuilt"]) for item in raw)
                        ),
                        "logical_provider_calls": int(
                            sum(item["logical_provider_calls"] for item in raw)
                        ),
                        "provider_pass": all(item["provider_pass"] for item in raw),
                        "fallback_attempted": any(
                            item["fallback_attempted"] for item in raw
                        ),
                    }
                )
                return matrix

            return builder

        def parallel_startup(*args, **kwargs):
            basis = {
                "template_state": dd204._state_payload(args[3]),
                "previous_inventory_lbmol": np.asarray(
                    kwargs["previous_inventory_lbmol"], dtype=float
                ).tolist(),
                "previous_controller_memory": np.asarray(
                    kwargs["previous_controller_memory"], dtype=float
                ).tolist(),
                "initial_solve_coordinates": np.asarray(
                    kwargs["initial_solve_coordinates"], dtype=float
                ).tolist(),
                "step_seconds": float(kwargs["step_seconds"]),
            }
            return solve_terminal_inventory_control_backward_euler_step(
                *args,
                **kwargs,
                jacobian_builder=parallel_builder(
                    "backward_euler", str(kwargs["name"]), basis
                ),
            )

        def parallel_bdf2(*args, **kwargs):
            basis = {
                "template_state": dd204._state_payload(args[3]),
                "history": dd204._history_payload(kwargs["history"]),
                "rate_scales_lbmolph": np.asarray(
                    kwargs["rate_scales_lbmolph"], dtype=float
                ).tolist(),
                "step_seconds": float(kwargs["step_seconds"]),
            }
            return solve_terminal_inventory_control_bdf2_step(
                *args,
                **kwargs,
                jacobian_builder=parallel_builder("bdf2", str(kwargs["name"]), basis),
            )

        common = dict(
            contract=controlled,
            spec=spec,
            reference=reference,
            initial_template=state,
            provider=provider,
            call_audit=audit,
            initial_inventory_lbmol=inventory,
            initial_controller_memory=memory,
            level_setpoints=setpoints,
            initial_solve_coordinates=coordinates,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=products,
            settings=settings,
            duration_seconds=float(payload["paths"]["duration_seconds"]),
            startup_step_solver=parallel_startup,
            bdf2_step_solver=parallel_bdf2,
            deadline_monotonic=deadline,
        )
        trajectory_started = time.perf_counter()
        coarse = run_terminal_inventory_control_bdf2_trajectory(
            **common,
            step_seconds=float(payload["paths"]["coarse_step_seconds"]),
            name="dd205_coarse",
        )
        refined = run_terminal_inventory_control_bdf2_trajectory(
            **common,
            step_seconds=float(payload["paths"]["refined_step_seconds"]),
            name="dd205_refined",
        )
        trajectory_wall = time.perf_counter() - trajectory_started
    total_wall = time.perf_counter() - total_started

    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd202.base.dd187.dd186._provider_summary(audit)
    limits = payload["limits"]
    coarse_response, coarse_steps = dd202.base._path_report(
        coarse, spec, inventory, limits, payload["required_rank"]
    )
    refined_response, refined_steps = dd202.base._path_report(
        refined, spec, inventory, limits, payload["required_rank"]
    )
    shared = dd202.base._shared(
        inventory,
        coarse,
        refined,
        coarse_response,
        refined_response,
        payload["paths"]["shared_step_pairs_1based"],
        payload,
    )
    response = {"coarse": coarse_response, "refined": refined_response}
    cross_difference = (
        coarse_response["total_inventory_change_lbmol"]
        - refined_response["total_inventory_change_lbmol"]
    )
    expected_difference = (
        coarse_response["expected_total_inventory_change_lbmol"]
        - refined_response["expected_total_inventory_change_lbmol"]
    )
    response_scale = max(
        abs(coarse_response["total_inventory_change_lbmol"]),
        abs(refined_response["total_inventory_change_lbmol"]),
        1.0e-12,
    )
    cross_grid = {
        "actual_difference_lbmol": cross_difference,
        "expected_external_difference_lbmol": expected_difference,
        "unexplained_difference_lbmol": cross_difference - expected_difference,
        "response_relative_difference": abs(cross_difference) / response_scale,
    }
    response_gates = {
        "coarse": coarse_response["total_inventory_change_lbmol"] > 0.0
        and coarse_response["total_inventory_strictly_increasing"]
        and coarse_response["total_inventory_relative_error"]
        < limits["integrated_response_relative_error"]
        and coarse_response["component_inventory_identity_max_abs_lbmol"]
        < limits["global_component_inventory_identity_lbmol"],
        "refined": refined_response["total_inventory_change_lbmol"] > 0.0
        and refined_response["total_inventory_strictly_increasing"]
        and refined_response["total_inventory_relative_error"]
        < limits["integrated_response_relative_error"]
        and refined_response["component_inventory_identity_max_abs_lbmol"]
        < limits["global_component_inventory_identity_lbmol"],
        "cross_grid_explained": abs(cross_difference - expected_difference)
        < limits["external_flow_explanation_lbmol"],
        "cross_grid_response_relative": abs(cross_difference) / response_scale
        < limits["response_relative_cross_grid"],
    }
    actual_science = {
        "coarse": {"steps": coarse_steps},
        "refined": {"steps": refined_steps},
        "shared_time_refinement": shared,
        "response": response,
        "cross_grid": cross_grid,
        "response_gates": response_gates,
    }
    expected_science = {key: accepted[key] for key in actual_science}
    comparison = _json_comparison(expected_science, actual_science)
    all_steps = coarse_steps + refined_steps
    worker_basis = dd204._worker_basis_summary(
        worker_evidence, int(parallel["worker_count"])
    )
    logical_calls = provider_summary["total_calls"] + sum(
        item["logical_provider_calls"] for item in worker_evidence
    )
    performance = {
        "dd202_wall_sec": float(payload["reference_result_wall_sec"]),
        "trajectory_wall_sec": float(trajectory_wall),
        "trajectory_ratio": float(
            trajectory_wall / payload["reference_result_wall_sec"]
        ),
        "speedup": float(payload["reference_result_wall_sec"] / trajectory_wall),
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "total_governed_wall_sec": float(total_wall),
    }
    gates = {
        "coarse_complete": coarse.completed
        and len(coarse_steps) == payload["paths"]["coarse_steps"],
        "refined_complete": refined.completed
        and len(refined_steps) == payload["paths"]["refined_steps"],
        "roots": len(all_steps) == 120
        and all(all(item["gates"].values()) for item in all_steps),
        "shared_physical": shared["physical_pass"],
        "accuracy": shared["baseline_max_error_ratio"]
        < payload["accuracy_baseline"]["required_ratio"]
        and shared["baseline_l1_error_ratio"]
        < payload["accuracy_baseline"]["required_ratio"],
        "response": all(response_gates.values()),
        "saved_result_equivalence": comparison["metadata_equal"]
        and comparison["maximum_numeric_difference"]
        < performance_limits["saved_result_absolute"],
        "worker_participation": bool(worker_evidence)
        and all(
            len(item["worker_ids"]) == parallel["worker_count"]
            and item["color_count"] == parallel["color_count"]
            and item["task_count"] == parallel["tasks_per_matrix"]
            for item in worker_evidence
        ),
        "worker_basis": worker_basis["pass"] and worker_basis["root_count"] == 120,
        "provider": provider_summary["pass"]
        and all(item["provider_pass"] for item in worker_evidence)
        and not any(item["fallback_attempted"] for item in worker_evidence),
        "provider_calls": logical_calls < performance_limits["logical_provider_calls"],
        "trajectory_speed": performance["speedup"]
        >= performance_limits["minimum_speedup"],
        "startup_wall": startup_adjusted < performance_limits["startup_wall_sec"],
        "wall_clock": total_wall < performance_limits["governed_wall_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-205",
        "classification": (
            "controlled_bdf2_parallel_replay_passed"
            if passed
            else "controlled_bdf2_parallel_replay_failed"
        ),
        "decision": (
            "adopt_persistent_parallel_bdf2_trajectory_path"
            if passed
            else "retain_serial_bdf2_trajectory_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "paths": payload["paths"],
        "completed_roots": len(all_steps),
        "coarse": actual_science["coarse"],
        "refined": actual_science["refined"],
        "shared_time_refinement": shared,
        "response": response,
        "cross_grid": cross_grid,
        "response_gates": response_gates,
        "saved_result_comparison": comparison,
        "worker": {
            "startup_ping_process_ids": ping_ids,
            "matrix_count": len(worker_evidence),
            "basis": worker_basis,
            "evidence": worker_evidence,
        },
        "performance": performance,
        "logical_provider_calls": int(logical_calls),
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "campaign_gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
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
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "paths": output["paths"],
                    "campaign_executed": output["campaign_executed"],
                },
                indent=2,
            )
        )
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(
            json.dumps(
                {
                    "classification": output["classification"],
                    "pass_gate": output["pass_gate"],
                    "decision": output["decision"],
                },
                indent=2,
            )
        )
        raise SystemExit(0 if output["pass_gate"] else 2)
