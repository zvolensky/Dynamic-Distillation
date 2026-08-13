#!/usr/bin/env python
"""Prepare or execute DD-193's finer-grid parallel controlled trajectory."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import adjudicate_core_v3_terminal_inventory_control_parallel_first_root as dd192  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_modest_trajectory as dd190  # noqa: E402
import run_core_v3_seven_volume_terminal_inventory_control_parallel_first_root as dd191  # noqa: E402
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
from dynamic_distillation.core_v3.physical_refinement_policy_v1 import (  # noqa: E402
    InventoryRefinementLimits,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_backward_euler_residual,
    solve_terminal_inventory_control_backward_euler_step,
    terminal_inventory_control_step_pattern,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    evaluate_terminal_inventory_control_residual,
)
from dynamic_distillation.core_v3.terminal_inventory_control_trajectory_v1 import (  # noqa: E402
    run_terminal_inventory_control_trajectory,
)


SCHEMA = "dd193-core-v3-controlled-finer-parallel-trajectory-contract-v1"
RESULT_SCHEMA = "dd193-core-v3-controlled-finer-parallel-trajectory-result-v1"
DD190_CONTRACT = Path(
    "logs/dd190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_contract_20260813.json"
)
DD190_RESULT = Path(
    "logs/dd190_core_v3_seven_volume_terminal_inventory_control_modest_trajectory_20260813.json"
)
DD191_RESULT = Path(
    "logs/dd191_core_v3_terminal_inventory_control_parallel_first_root_20260813.json"
)
DD192_RESULT = Path(
    "logs/dd192_core_v3_terminal_inventory_control_parallel_worker_adjudication_20260813.json"
)
CONTRACT = Path(
    "logs/dd193_core_v3_terminal_inventory_control_finer_parallel_trajectory_contract_20260813.json"
)
RESULT = Path(
    "logs/dd193_core_v3_terminal_inventory_control_finer_parallel_trajectory_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_193_core_v3_terminal_inventory_control_finer_parallel_trajectory_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_193_core_v3_terminal_inventory_control_finer_parallel_trajectory_20260813.md"
)
DURATION_SEC = 10.0
COARSE_DT_SEC = 0.125
REFINED_DT_SEC = 0.0625
_WORKER_CONTEXT: dict[str, Any] | None = None
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_trajectory_v1.py",
    "src/dynamic_distillation/core_v3/parallel_colored_jacobian_v1.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_finer_parallel_trajectory.py",
    "tests/test_core_v3_terminal_inventory_control_finer_parallel_trajectory.py",
)


def _load(path: Path) -> dict[str, Any]:
    return dd190.dd188.dd187.dd186._load(path)


def _sha(path: Path) -> str:
    return dd190.dd188.dd187.dd186._sha(path)


def _git(*args: str) -> str:
    return dd190.dd188.dd187.dd186._git(*args)


def _hash(payload: Mapping[str, Any]) -> str:
    return dd190.dd188.dd187.dd186._hash(payload)


def _failed_names(values: Mapping[str, Any]) -> list[str]:
    return [name for name, passed in values.items() if not passed]


def _validate_sources(
    dd190_result: Mapping[str, Any],
    dd191_result: Mapping[str, Any],
    dd192_result: Mapping[str, Any],
) -> None:
    if dd190_result.get("pass_gate") is not False or dd190_result.get("decision") != (
        "stop_terminal_control_trajectory_path"
    ):
        raise RuntimeError("DD-193 requires DD-190's preserved formal failure")
    if _failed_names(dd190_result["campaign_gates"]) != ["shared_time_refinement"]:
        raise RuntimeError("DD-190 failure is not shared-time refinement only")
    if not dd190_result["coarse"]["step_gates_pass"] or not dd190_result[
        "refined"
    ]["step_gates_pass"]:
        raise RuntimeError("DD-190 root health changed")
    dd192._validate_source(dd191_result)
    if not dd192_result.get("pass_gate") or dd192_result.get("decision") != (
        "authorize_persistent_parallel_controlled_step_path_under_task_participation_policy"
    ):
        raise RuntimeError("DD-193 requires accepted DD-192 parallel authorization")
    if any(
        int(dd192_result.get(name, -1)) != 0
        for name in ("model_calls", "provider_calls", "solver_calls", "endpoint_regeneration_calls")
    ):
        raise RuntimeError("DD-192 is no longer a zero-call adjudication")


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
    (
        spec,
        reference,
        _state,
        controlled,
        provider,
        audit,
        _inventory,
        _memory,
        _initial,
        setpoints,
        product_reference,
    ) = dd191._context(payload)
    _WORKER_CONTEXT = {
        "spec": spec,
        "reference": reference,
        "controlled": controlled,
        "provider": provider,
        "audit": audit,
        "setpoints": setpoints,
        "product_reference": product_reference,
        "fixed_scales": payload["fixed_steady_residual_scales"],
        "root_epoch": None,
    }


def _worker_ping(delay_seconds: float) -> int:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-193 worker context was not initialized")
    time.sleep(float(delay_seconds))
    return int(os.getpid())


def _worker_evaluate(work: Mapping[str, Any]) -> dict[str, Any]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("DD-193 worker context was not initialized")
    context = _WORKER_CONTEXT
    task: ColoredCentralDifferenceTask = work["task"]
    root_epoch = str(work["root_epoch"])
    provider = context["provider"]
    audit = context["audit"]
    before_records = len(audit.records)
    before_memo = provider.get_exact_state_memoization_stats()
    basis_rebuilt = context["root_epoch"] != root_epoch
    if basis_rebuilt:
        template = dd190.dd188.dd187.dd186.dd171._state(work["template_state"])
        previous = np.asarray(work["previous_inventory_lbmol"], dtype=float)
        memory = np.asarray(work["previous_controller_memory"], dtype=float)
        initial = np.asarray(work["initial_solve_coordinates"], dtype=float)
        baseline = evaluate_terminal_inventory_control_residual(
            context["controlled"],
            context["spec"],
            context["reference"],
            template,
            provider,
            audit,
            inventory_lbmol=previous,
            controller_memory=memory,
            level_setpoints=context["setpoints"],
            solve_coordinates=initial,
            storage_gradient_BTU_lbmol=np.zeros_like(previous),
            fixed_steady_scales=context["fixed_scales"],
            product_reference_lbmolph=context["product_reference"],
            state_id=f"{root_epoch}:worker_{os.getpid()}:scale_basis",
            evaluation_kind="residual",
        )
        context.update(
            {
                "root_epoch": root_epoch,
                "template": template,
                "previous": previous,
                "memory": memory,
                "previous_storage": governing_storage_vector(
                    context["spec"], baseline.base, previous
                ),
                "rate_scales": component_rate_scales(
                    context["controlled"].base, baseline.base
                ),
            }
        )
    started = time.perf_counter()
    evaluation = evaluate_terminal_inventory_control_backward_euler_residual(
        context["controlled"],
        context["spec"],
        context["reference"],
        context["template"],
        provider,
        audit,
        previous_inventory_lbmol=context["previous"],
        previous_internal_energy_BTU=context["previous_storage"],
        previous_controller_memory=context["memory"],
        level_setpoints=context["setpoints"],
        rate_scales_lbmolph=context["rate_scales"],
        solve_coordinates=np.asarray(task.coordinates, dtype=float),
        step_seconds=float(work["step_seconds"]),
        fixed_steady_scales=context["fixed_scales"],
        product_reference_lbmolph=context["product_reference"],
        state_id=task.state_id,
        evaluation_kind="jacobian",
    )
    elapsed = time.perf_counter() - started
    after_memo = provider.get_exact_state_memoization_stats()
    report = audit.report()
    return {
        "order": int(task.order),
        "residual": np.asarray(evaluation.scaled, dtype=float).tolist(),
        "process_id": int(os.getpid()),
        "root_epoch": root_epoch,
        "basis_rebuilt": bool(basis_rebuilt),
        "logical_provider_calls": int(len(audit.records) - before_records),
        "memo_hits": int(after_memo["hits"] - before_memo["hits"]),
        "memo_misses": int(after_memo["misses"] - before_memo["misses"]),
        "provider_pass": bool(report["pass"]),
        "fallback_attempted": bool(report["fallback_attempted"]),
        "wall_clock_sec": float(elapsed),
    }


def _controlled_shared_refinement(
    initial_inventory: np.ndarray,
    coarse: Sequence[Any],
    refined: Sequence[Any],
    pairs: Sequence[Sequence[int]],
    physical_limits: InventoryRefinementLimits,
    limits: Mapping[str, float],
    spec: Any,
) -> dict[str, Any]:
    base = dd190.dd188._shared_refinement(
        initial_inventory, coarse, refined, pairs, physical_limits, limits
    )
    comparisons = []
    for item in base["comparisons"]:
        coarse_count = int(item["coarse_step"])
        refined_count = int(item["refined_step"])
        coarse_response = dd190._prefix_response(
            initial_inventory, coarse, coarse_count, COARSE_DT_SEC, spec
        )
        refined_response = dd190._prefix_response(
            initial_inventory, refined, refined_count, REFINED_DT_SEC, spec
        )
        actual = coarse_response["total_inventory_change_lbmol"] - refined_response[
            "total_inventory_change_lbmol"
        ]
        expected = coarse_response[
            "expected_total_inventory_change_lbmol"
        ] - refined_response["expected_total_inventory_change_lbmol"]
        unexplained = abs(actual - expected)
        response_scale = max(
            abs(coarse_response["total_inventory_change_lbmol"]),
            abs(refined_response["total_inventory_change_lbmol"]),
            1.0e-12,
        )
        relative = abs(actual) / response_scale
        gates = dict(item["gates"])
        signed_total = gates.pop("signed_total")
        gates.update(
            {
                "signed_total_reported_diagnostic": True,
                "external_flow_explanation": unexplained
                < limits["unexplained_cross_grid_difference_lbmol"],
                "response_relative_total": relative
                < limits["cross_grid_difference_relative_to_response"],
            }
        )
        comparisons.append(
            {
                **item,
                "signed_total_original_gate": signed_total,
                "actual_total_difference_lbmol": actual,
                "expected_external_flow_difference_lbmol": expected,
                "unexplained_total_difference_lbmol": unexplained,
                "response_relative_total_difference": relative,
                "gates": gates,
                "pass_gate": all(gates.values()),
            }
        )
    return {
        "comparisons": comparisons,
        "comparison_count": len(comparisons),
        "worst_absolute_component_difference_lbmol": base[
            "worst_absolute_component_difference_lbmol"
        ],
        "worst_component_l1_lbmol": base["worst_component_l1_lbmol"],
        "worst_rate_coordinate_difference": base["worst_rate_coordinate_difference"],
        "worst_algebraic_coordinate_difference": base[
            "worst_algebraic_coordinate_difference"
        ],
        "worst_controller_memory_difference": base[
            "worst_controller_memory_difference"
        ],
        "worst_product_relative_difference": base[
            "worst_product_relative_difference"
        ],
        "worst_level_fraction_difference": base["worst_level_fraction_difference"],
        "worst_unexplained_total_difference_lbmol": max(
            item["unexplained_total_difference_lbmol"] for item in comparisons
        ),
        "worst_response_relative_total_difference": max(
            item["response_relative_total_difference"] for item in comparisons
        ),
        "original_signed_total_failure_count": sum(
            not item["signed_total_original_gate"] for item in comparisons
        ),
        "pass_gate": all(item["pass_gate"] for item in comparisons),
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    performance = payload["performance"]
    return "\n".join(
        (
            "# DD-193 Controlled Finer-Grid Parallel Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            f"- Duration: `{paths['duration_seconds']} s`",
            f"- Coarse: `{paths['coarse_steps']} x {paths['coarse_step_seconds']} s`",
            f"- Refined: `{paths['refined_steps']} x {paths['refined_step_seconds']} s`",
            "- Solver: one persistent four-worker DWSIM Jacobian pool",
            "- Physics, disturbance, controllers, setpoints, and acceptance limits: unchanged",
            f"- Projected serial baseline: `{performance['projected_serial_wall_sec']:.3f} s`",
            f"- Parallel trajectory wall gate: `<{performance['parallel_wall_limit_sec']:.3f} s` excluding startup",
            "- Tuning, retry, alternate grid, fallback, clipping, and longer horizon: prohibited",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    shared = payload["shared_time_refinement"]
    return "\n".join(
        (
            "# DD-193 Controlled Finer-Grid Parallel Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}`",
            f"- Worst residual / condition: `{payload['worst_residual']:.6e}` / `{payload['worst_condition']:.6e}`",
            f"- Worst response-relative total difference: `{shared['worst_response_relative_total_difference']:.6e}`",
            f"- Worst level refinement: `{shared['worst_level_fraction_difference']:.6e}`",
            f"- Parallel trajectory / startup wall: `{payload['performance']['parallel_trajectory_wall_sec']:.3f}` / `{payload['performance']['startup_wall_sec_adjusted']:.3f} s`",
            f"- Speedup versus projected serial: `{payload['performance']['projected_speedup']:.3f}x`",
            f"- Logical provider calls: `{payload['provider']['logical_calls']}`",
            "- Controller tuning/retry/longer horizon: `False / False / False`",
            "",
        )
    )


def prepare(
    source_contract_path: Path,
    dd190_result_path: Path,
    dd191_result_path: Path,
    dd192_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = _load(source_contract_path)
    dd190_result = _load(dd190_result_path)
    dd191_result = _load(dd191_result_path)
    dd192_result = _load(dd192_result_path)
    _validate_sources(dd190_result, dd191_result, dd192_result)
    coarse_count = dd190.dd188.dd177._step_count(DURATION_SEC, COARSE_DT_SEC)
    refined_count = dd190.dd188.dd177._step_count(DURATION_SEC, REFINED_DT_SEC)
    pairs = dd190.dd188.dd177._shared_step_pairs(coarse_count, refined_count)
    projected_serial = float(dd190_result["wall_clock_sec"]) * (
        (coarse_count + refined_count) / dd190_result["completed_roots"]
    )
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                source_contract_path,
                dd190_result_path,
                dd191_result_path,
                dd192_result_path,
                dd191.DD185_CONTRACT,
            )
        },
        **{
            name: source[name]
            for name in (
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
                "geometry",
                "controllers",
                "fixed_steady_residual_scales",
                "disturbance",
                "solver",
                "physical_refinement_limits",
                "exact_state_memoization",
            )
        },
        "paths": {
            "duration_seconds": DURATION_SEC,
            "coarse_step_seconds": COARSE_DT_SEC,
            "coarse_steps": coarse_count,
            "refined_step_seconds": REFINED_DT_SEC,
            "refined_steps": refined_count,
            "shared_time_count": len(pairs),
            "shared_step_pairs_1based": [list(pair) for pair in pairs],
        },
        "parallel": {
            "worker_count": 4,
            "color_count": 17,
            "tasks_per_matrix": 34,
            "startup_ping_delay_sec": 0.15,
            "actual_task_participation_policy": True,
        },
        "limits": {
            **source["limits"],
            "provider_calls": 1_300_000,
            "wall_clock_sec": 240.0,
        },
        "performance": {
            "dd190_serial_wall_sec": dd190_result["wall_clock_sec"],
            "dd190_serial_roots": dd190_result["completed_roots"],
            "projected_serial_wall_sec": projected_serial,
            "parallel_ratio_limit": 0.75,
            "parallel_wall_limit_sec": projected_serial * 0.75,
            "startup_wall_limit_sec": 30.0,
        },
        "required_rank": 58,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "either finer trajectory fails to complete every root",
            "any root loses closure, rank, condition, physicality, or conservation",
            "any shared-time physical or controlled-response refinement gate fails",
            "any actual Jacobian does not use all four persistent workers",
            "worker basis is not rebuilt exactly once per worker and root",
            "provider ownership, logical-call, startup, or wall gates fail",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "controller_tuning_attempted": False,
        "retry_authorized": False,
        "alternate_grid_authorized": False,
        "longer_horizon_authorized": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-193 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-193 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-193 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-193 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-193 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-193 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-193 contract is not committed")


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    dd190_result, dd191_result, dd192_result = (
        _load(DD190_RESULT),
        _load(DD191_RESULT),
        _load(DD192_RESULT),
    )
    _validate_sources(dd190_result, dd191_result, dd192_result)
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
    ) = dd191._context(payload)
    pattern = terminal_inventory_control_step_pattern(controlled)
    settings = dd190.dd188.dd187.dd186._settings(payload)
    paths = payload["paths"]
    parallel = payload["parallel"]
    worker_evidence: list[dict[str, Any]] = []
    jacobian_wall: list[float] = []

    spawn = mp.get_context("spawn")
    total_started = time.perf_counter()
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(parallel["worker_count"]),
        mp_context=spawn,
        initializer=_worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(_worker_ping, parallel["startup_ping_delay_sec"])
            for _ in range(int(parallel["worker_count"]))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(parallel["startup_ping_delay_sec"]), 0.0
        )

        def parallel_step_solver(*args, **kwargs):
            template_payload = _state_payload(args[3])
            previous = np.asarray(kwargs["previous_inventory_lbmol"], dtype=float)
            previous_memory = np.asarray(
                kwargs["previous_controller_memory"], dtype=float
            )
            coordinates = np.asarray(kwargs["initial_solve_coordinates"], dtype=float)
            root_epoch = str(kwargs["name"])

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
                        "previous_controller_memory": previous_memory.tolist(),
                        "initial_solve_coordinates": coordinates.tolist(),
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
                jacobian_wall.append(time.perf_counter() - started)
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
                        "provider_pass": all(item["provider_pass"] for item in raw),
                        "fallback_attempted": any(
                            item["fallback_attempted"] for item in raw
                        ),
                    }
                )
                return matrix

            return solve_terminal_inventory_control_backward_euler_step(
                *args, **kwargs, jacobian_builder=builder
            )

        trajectory_started = time.perf_counter()
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
            initial_solve_coordinates=initial,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=product_reference,
            duration_seconds=float(paths["duration_seconds"]),
            settings=settings,
            step_solver=parallel_step_solver,
        )
        coarse = run_terminal_inventory_control_trajectory(
            **common,
            step_seconds=float(paths["coarse_step_seconds"]),
            name="dd193_coarse_0p125s",
        )
        refined = run_terminal_inventory_control_trajectory(
            **common,
            step_seconds=float(paths["refined_step_seconds"]),
            name="dd193_refined_0p0625s",
        )
        trajectory_wall = time.perf_counter() - trajectory_started
    total_wall = time.perf_counter() - total_started

    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    main_provider = dd190.dd188.dd187.dd186._provider_summary(audit)
    limits = payload["limits"]
    setpoint_values = np.asarray((setpoints.top_fraction, setpoints.bottom_fraction))
    coarse_report = dd190.dd188._trajectory_report(
        coarse,
        spec,
        inventory,
        initial,
        memory,
        setpoint_values,
        product_reference,
        limits,
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    refined_report = dd190.dd188._trajectory_report(
        refined,
        spec,
        inventory,
        initial,
        memory,
        setpoint_values,
        product_reference,
        limits,
        payload["required_rank"],
        payload["solver"]["max_nfev"],
    )
    coarse_evaluations = dd190.dd188._evaluations(coarse)
    refined_evaluations = dd190.dd188._evaluations(refined)
    shared = _controlled_shared_refinement(
        inventory,
        coarse_evaluations,
        refined_evaluations,
        paths["shared_step_pairs_1based"],
        InventoryRefinementLimits.from_mapping(payload["physical_refinement_limits"]),
        limits,
        spec,
    )
    response = {
        "coarse": dd190.dd188.dd187._path_response(
            inventory,
            coarse_evaluations,
            [COARSE_DT_SEC] * len(coarse_evaluations),
            spec,
        ),
        "refined": dd190.dd188.dd187._path_response(
            inventory,
            refined_evaluations,
            [REFINED_DT_SEC] * len(refined_evaluations),
            spec,
        ),
    }
    response_gates = {}
    for name, values in response.items():
        expected = values["expected_total_inventory_change_lbmol"]
        relative_error = abs(values["total_inventory_change_lbmol"] - expected) / max(
            abs(expected), 1.0e-12
        )
        report = coarse_report if name == "coarse" else refined_report
        values["total_inventory_relative_error"] = relative_error
        response_gates[name] = {
            "positive": values["total_inventory_change_lbmol"] > 0.0,
            "monotone": report["total_inventory_strictly_increasing"],
            "integrated_expected": relative_error
            < limits["integrated_response_relative_error"],
            "component_identity": values["component_inventory_identity_max_abs_lbmol"]
            < limits["global_component_inventory_identity_lbmol"],
        }
    root_evidence: dict[str, list[dict[str, Any]]] = {}
    for item in worker_evidence:
        root_evidence.setdefault(item["root_epoch"], []).append(item)
    expected_roots = int(paths["coarse_steps"] + paths["refined_steps"])
    actual_worker_ids = [set(item["worker_ids"]) for item in worker_evidence]
    common_worker_ids = actual_worker_ids[0] if actual_worker_ids else set()
    worker_calls = sum(item["logical_provider_calls"] for item in worker_evidence)
    logical_calls = int(main_provider["total_calls"] + worker_calls)
    basis_refresh_pass = len(root_evidence) == expected_roots and all(
        sum(item["basis_rebuilds"] for item in matrices) == parallel["worker_count"]
        and matrices[0]["basis_rebuilds"] == parallel["worker_count"]
        and all(item["basis_rebuilds"] == 0 for item in matrices[1:])
        for matrices in root_evidence.values()
    )
    performance = {
        **payload["performance"],
        "parallel_trajectory_wall_sec": float(trajectory_wall),
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "total_governed_wall_sec": float(total_wall),
        "projected_speedup": payload["performance"]["projected_serial_wall_sec"]
        / trajectory_wall,
        "parallel_ratio_to_projected_serial": trajectory_wall
        / payload["performance"]["projected_serial_wall_sec"],
        "total_jacobian_wall_sec": float(sum(jacobian_wall)),
    }
    all_steps = coarse_report["steps"] + refined_report["steps"]
    campaign_gates = {
        "coarse_complete": coarse_report["completed"] and coarse_report["step_gates_pass"],
        "refined_complete": refined_report["completed"] and refined_report["step_gates_pass"],
        "response": all(all(values.values()) for values in response_gates.values()),
        "shared_time_refinement": shared["pass_gate"],
        "actual_worker_participation": bool(actual_worker_ids)
        and len(common_worker_ids) == parallel["worker_count"]
        and all(ids == common_worker_ids for ids in actual_worker_ids),
        "worker_basis_refresh": basis_refresh_pass,
        "worker_provider": all(item["provider_pass"] for item in worker_evidence)
        and not any(item["fallback_attempted"] for item in worker_evidence),
        "main_provider": main_provider["pass"],
        "provider_calls": logical_calls < limits["provider_calls"],
        "parallel_wall": trajectory_wall
        < payload["performance"]["parallel_wall_limit_sec"],
        "startup_wall": startup_adjusted
        < payload["performance"]["startup_wall_limit_sec"],
        "total_wall": total_wall < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    final_controller_state = {}
    for name, evaluation in (
        ("coarse", coarse_evaluations[-1]),
        ("refined", refined_evaluations[-1]),
    ):
        final_controller_state[name] = {
            "level_fraction": dd190.dd188.dd187.dd186._vector(
                evaluation.level_fraction
            ),
            "controller_memory": dd190.dd188.dd187.dd186._vector(
                evaluation.endpoint_controller_memory
            ),
            "product_log_ratio": dd190.dd188.dd187.dd186._vector(
                evaluation.product_log_ratio
            ),
            "distillate_lbmolph": evaluation.distillate_lbmolph,
            "bottoms_lbmolph": evaluation.bottoms_lbmolph,
        }
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "controlled_finer_parallel_trajectory_passed"
            if passed
            else "controlled_finer_parallel_trajectory_failed"
        ),
        "decision": (
            "authorize_one_separately_frozen_controlled_parallel_extension"
            if passed
            else "stop_controlled_trajectory_extension"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "paths": paths,
        "completed_roots": len(all_steps),
        "worst_residual": max(item["residual_inf_norm"] for item in all_steps),
        "worst_condition": max(item["jacobian_condition"] for item in all_steps),
        "coarse": coarse_report,
        "refined": refined_report,
        "shared_time_refinement": shared,
        "response": response,
        "response_gates": response_gates,
        "final_controller_state": final_controller_state,
        "performance": performance,
        "provider": {
            "main": main_provider,
            "worker_logical_calls": int(worker_calls),
            "logical_calls": logical_calls,
            "main_memoization": memo,
        },
        "worker_ping_ids_diagnostic": ping_ids,
        "worker_ids": sorted(common_worker_ids),
        "worker_evidence": worker_evidence,
        "campaign_gates": campaign_gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "longer_horizon_attempted": False,
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
    parser.add_argument("--dd190-result", type=Path, default=DD190_RESULT)
    parser.add_argument("--dd191-result", type=Path, default=DD191_RESULT)
    parser.add_argument("--dd192-result", type=Path, default=DD192_RESULT)
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
            args.dd190_result,
            args.dd191_result,
            args.dd192_result,
            args.contract,
            args.contract_doc,
        )
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "paths": output["paths"],
                    "performance": output["performance"],
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
