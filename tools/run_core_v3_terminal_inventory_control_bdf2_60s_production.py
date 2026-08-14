#!/usr/bin/env python
"""Prepare or execute DD-213's frozen 60-second production BDF2 milestone."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_trajectory as dd202  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_30s_production as dd209  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence as dd204  # noqa: E402
from dynamic_distillation.core_v3.persistent_parallel_colored_jacobian_v1 import (  # noqa: E402
    PersistentParallelColoredJacobian,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_parallel_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2ParallelStepSolvers,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_trajectory_v1 import (  # noqa: E402
    run_terminal_inventory_control_bdf2_trajectory,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    terminal_inventory_control_step_pattern,
)


SCHEMA = "dd213-core-v3-bdf2-60s-production-contract-v1"
RESULT_SCHEMA = "dd213-core-v3-bdf2-60s-production-result-v1"
DD209_CONTRACT = dd209.CONTRACT
DD209_RESULT = Path(
    "logs/dd209_core_v3_terminal_inventory_control_bdf2_30s_production_20260814.json"
)
DD210_RESULT = Path(
    "logs/dd210_core_v3_terminal_inventory_control_bdf2_worker_scaling_20260814.json"
)
DD212_RESULT = Path(
    "logs/dd212_core_v3_terminal_inventory_control_bdf2_predictor_benchmark_20260814.json"
)
CONTRACT = Path(
    "logs/dd213_core_v3_terminal_inventory_control_bdf2_60s_production_contract_20260814.json"
)
RESULT = Path(
    "logs/dd213_core_v3_terminal_inventory_control_bdf2_60s_production_20260814"
)
CONTRACT_DOC = Path(
    "docs/dd_213_core_v3_terminal_inventory_control_bdf2_60s_production_contract_20260814.md"
)
RESULT_DOC = Path(
    "docs/dd_213_core_v3_terminal_inventory_control_bdf2_60s_production_20260814.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/persistent_parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_parallel_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "tools/run_core_v3_terminal_inventory_control_bdf2_60s_production.py",
    "tests/test_core_v3_terminal_inventory_control_bdf2_60s_production.py",
)


def _paths(
    duration_seconds: float = 60.0,
    coarse_step_seconds: float = 0.25,
    refined_step_seconds: float = 0.125,
) -> dict[str, Any]:
    coarse_steps = int(round(duration_seconds / coarse_step_seconds))
    refined_steps = int(round(duration_seconds / refined_step_seconds))
    if coarse_steps * coarse_step_seconds != duration_seconds:
        raise ValueError("DD-213 coarse grid does not divide duration")
    if refined_steps * refined_step_seconds != duration_seconds:
        raise ValueError("DD-213 refined grid does not divide duration")
    ratio = int(round(coarse_step_seconds / refined_step_seconds))
    if ratio * refined_step_seconds != coarse_step_seconds:
        raise ValueError("DD-213 refinement ratio is not integral")
    pairs = [[index, ratio * index] for index in range(1, coarse_steps + 1)]
    return {
        "duration_seconds": float(duration_seconds),
        "coarse_step_seconds": float(coarse_step_seconds),
        "coarse_steps": coarse_steps,
        "refined_step_seconds": float(refined_step_seconds),
        "refined_steps": refined_steps,
        "shared_time_count": len(pairs),
        "shared_step_pairs_1based": pairs,
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    limits = payload["performance_limits"]
    production = payload["production"]
    return "\n".join(
        (
            "# DD-213 60-Second Production BDF2 Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Coarse path: `{paths['coarse_steps']} x {paths['coarse_step_seconds']} s`",
            f"- Refined path: `{paths['refined_steps']} x {paths['refined_step_seconds']} s`",
            f"- Workers / BDF2 initial guess: `{production['worker_count']}` / `{production['bdf2_initial_guess_policy']}`",
            "- Science: unchanged DD-209 disturbance, controllers, equations, solver, and DWSIM PR provider",
            "- Refinement: frozen absolute physical/controller/response limits",
            f"- Logical provider-call ceiling: `{limits['logical_provider_calls']}`",
            f"- Governed wall deadline: `{limits['deadline_seconds']} s`",
            "- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    shared = payload.get("shared_time_refinement") or {}
    performance = payload["performance"]
    return "\n".join(
        (
            "# DD-213 60-Second Production BDF2 Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}` / `{payload['requested_roots']}`",
            f"- Coarse/refined stop reasons: `{payload['stop_reasons']['coarse']}` / `{payload['stop_reasons']['refined']}`",
            f"- Worst residual / condition: `{payload['worst_residual']:.6e}` / `{payload['worst_condition']:.6e}`",
            f"- Worst shared inventory max / L1: `{shared.get('worst_absolute_component_difference_lbmol', float('nan')):.6e}` / `{shared.get('worst_component_l1_lbmol', float('nan')):.6e} lbmol`",
            f"- Matrix count / logical provider calls: `{payload['worker']['matrix_count']}` / `{payload['logical_provider_calls']}`",
            f"- Trajectory / governed wall: `{performance['trajectory_wall_sec']:.3f}` / `{performance['total_governed_wall_sec']:.3f} s`",
            "- Retry, tuning, alternate grid, or fallback: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = dd209._load(DD209_CONTRACT)
    horizon = dd209._load(DD209_RESULT)
    scaling = dd209._load(DD210_RESULT)
    predictor = dd209._load(DD212_RESULT)
    if not horizon["pass_gate"] or horizon["completed_roots"] != 360:
        raise RuntimeError("DD-213 requires accepted DD-209")
    if not scaling["pass_gate"] or scaling["decision"] != (
        "adopt_eight_worker_production_jacobian_backend"
    ):
        raise RuntimeError("DD-213 requires accepted DD-210")
    if not predictor["pass_gate"] or predictor["decision"] != (
        "adopt_linear_extrapolation_bdf2_initial_guess"
    ):
        raise RuntimeError("DD-213 requires accepted DD-212")
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
            "campaign_id": "DD-213",
            "preparation_base_commit": dd209._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd209._sha(ROOT / path)
                for path in (
                    DD209_CONTRACT,
                    DD209_RESULT,
                    DD210_RESULT,
                    DD212_RESULT,
                )
            },
            "paths": _paths(),
            "production": {
                "worker_count": 8,
                "color_count": 17,
                "tasks_per_matrix": 34,
                "startup_ping_delay_sec": 0.15,
                "bdf2_initial_guess_policy": "linear_extrapolation",
            },
            "performance_limits": {
                "logical_provider_calls": 3200000,
                "startup_wall_sec": 30.0,
                "deadline_seconds": 300.0,
                "governed_wall_sec": 300.0,
            },
            "refinement_acceptance": "frozen_absolute_limits",
            "accuracy_baseline_use": "diagnostic_only",
            "implementation_sha256": {
                path: dd209._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either path fails to complete every root",
                "any root loses closure, rank, conditioning, physicality, equilibrium, conservation, or controller closure",
                "shared physical, controller, product, level, or response refinement exceeds a frozen limit",
                "provider ownership, all-worker participation, or per-root basis lifecycle fails",
                "provider-call, startup, in-execution, or governed-wall ceiling is exceeded",
                "a retry, alternate grid, tuning, fallback, clipping, projection, or equation change occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "trajectory_attempted": False,
            "controller_tuning_attempted": False,
            "retry_authorized": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = dd209._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-213 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd209._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-213 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-213 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-213 implementation changed: {path}")
    if dd209._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-213 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-213 result exists; rerun prohibited")
    dd209._git("ls-files", "--error-unmatch", str(contract_path))


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = dd209._load(contract_path)
    _verify(payload, contract_path, result_path)
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
    settings = dd202.base.dd187.dd186._settings(payload)
    paths = payload["paths"]
    production = payload["production"]
    performance_limits = payload["performance_limits"]
    pattern = terminal_inventory_control_step_pattern(controlled)
    total_started = time.perf_counter()
    deadline = total_started + float(performance_limits["deadline_seconds"])
    spawn = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(production["worker_count"]),
        mp_context=spawn,
        initializer=dd204._worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(dd204._worker_ping, production["startup_ping_delay_sec"])
            for _ in range(int(production["worker_count"]))
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(production["startup_ping_delay_sec"]), 0.0
        )
        jacobians = PersistentParallelColoredJacobian(
            pool,
            dd204._worker_evaluate,
            pattern=pattern,
            step=settings.jacobian_step,
            worker_count=int(production["worker_count"]),
        )
        backend = TerminalInventoryControlBDF2ParallelStepSolvers(jacobians)
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
            duration_seconds=float(paths["duration_seconds"]),
            step_solver_backend=backend,
            deadline_monotonic=deadline,
            bdf2_initial_guess_policy=production["bdf2_initial_guess_policy"],
        )
        trajectory_started = time.perf_counter()
        coarse = run_terminal_inventory_control_bdf2_trajectory(
            **common,
            step_seconds=float(paths["coarse_step_seconds"]),
            name="dd213_coarse",
        )
        refined = run_terminal_inventory_control_bdf2_trajectory(
            **common,
            step_seconds=float(paths["refined_step_seconds"]),
            name="dd213_refined",
        )
        trajectory_wall = time.perf_counter() - trajectory_started
        worker_evidence = [asdict(item) for item in jacobians.evidence]
        worker_calls = jacobians.logical_provider_calls
    total_wall = time.perf_counter() - total_started

    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd202.base.dd187.dd186._provider_summary(audit)
    limits = payload["limits"]
    coarse_response = None
    refined_response = None
    coarse_steps: list[dict[str, Any]] = []
    refined_steps: list[dict[str, Any]] = []
    shared = None
    cross_grid = None
    response_gates = {
        "coarse": False,
        "refined": False,
        "cross_grid_explained": False,
        "cross_grid_response_relative": False,
    }
    if coarse.records:
        coarse_response, coarse_steps = dd202.base._path_report(
            coarse, spec, inventory, limits, payload["required_rank"]
        )
    if refined.records:
        refined_response, refined_steps = dd202.base._path_report(
            refined, spec, inventory, limits, payload["required_rank"]
        )
    complete_paths = (
        coarse.completed
        and coarse.completed_steps == paths["coarse_steps"]
        and refined.completed
        and refined.completed_steps == paths["refined_steps"]
    )
    if complete_paths and coarse_response is not None and refined_response is not None:
        shared = dd202.base._shared(
            inventory,
            coarse,
            refined,
            coarse_response,
            refined_response,
            paths["shared_step_pairs_1based"],
            payload,
        )
        cross_grid, response_gates = dd209._response_gates(
            coarse_response, refined_response, limits
        )

    all_steps = coarse_steps + refined_steps
    requested_roots = int(paths["coarse_steps"] + paths["refined_steps"])
    basis = dd209._basis_summary(worker_evidence, int(production["worker_count"]))
    logical_calls = int(provider_summary["total_calls"] + worker_calls)
    performance = {
        "trajectory_wall_sec": float(trajectory_wall),
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "total_governed_wall_sec": float(total_wall),
        "simulated_seconds_per_trajectory_wall_second": float(
            2.0 * paths["duration_seconds"] / max(trajectory_wall, 1.0e-12)
        ),
    }
    worst_residual = max(
        (float(item["residual_inf_norm"]) for item in all_steps),
        default=float("inf"),
    )
    worst_condition = max(
        (float(item["jacobian_condition"]) for item in all_steps),
        default=float("inf"),
    )
    gates = {
        "coarse_complete": coarse.completed
        and coarse.completed_steps == paths["coarse_steps"],
        "refined_complete": refined.completed
        and refined.completed_steps == paths["refined_steps"],
        "roots": len(all_steps) == requested_roots
        and all(all(item["gates"].values()) for item in all_steps),
        "shared_physical": shared is not None and shared["physical_pass"],
        "response": all(response_gates.values()),
        "worker_participation": bool(worker_evidence)
        and all(
            len(item["worker_ids"]) == production["worker_count"]
            and item["color_count"] == production["color_count"]
            and item["task_count"] == production["tasks_per_matrix"]
            for item in worker_evidence
        ),
        "worker_basis": basis["pass"] and basis["root_count"] == requested_roots,
        "provider": provider_summary["pass"]
        and all(item["provider_pass"] for item in worker_evidence)
        and not any(item["fallback_attempted"] for item in worker_evidence),
        "provider_calls": logical_calls < performance_limits["logical_provider_calls"],
        "startup_wall": startup_adjusted < performance_limits["startup_wall_sec"],
        "wall_clock": total_wall < performance_limits["governed_wall_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-213",
        "classification": (
            "controlled_bdf2_60s_production_passed"
            if passed
            else "controlled_bdf2_60s_production_failed"
        ),
        "decision": (
            "authorize_single_grid_production_qualification"
            if passed
            else "classify_60s_failure_before_further_integration"
        ),
        "contract_commit": dd209._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "paths": paths,
        "production": production,
        "requested_roots": requested_roots,
        "completed_roots": len(all_steps),
        "stop_reasons": {
            "coarse": coarse.stop_reason,
            "refined": refined.stop_reason,
        },
        "coarse": {"steps": coarse_steps},
        "refined": {"steps": refined_steps},
        "shared_time_refinement": shared,
        "accuracy_baseline": payload["accuracy_baseline"],
        "accuracy_baseline_use": payload["accuracy_baseline_use"],
        "response": {"coarse": coarse_response, "refined": refined_response},
        "cross_grid": cross_grid,
        "response_gates": response_gates,
        "worst_residual": worst_residual,
        "worst_condition": worst_condition,
        "worker": {
            "startup_ping_process_ids": ping_ids,
            "matrix_count": len(worker_evidence),
            "basis": basis,
            "evidence": worker_evidence,
        },
        "logical_provider_calls": logical_calls,
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "performance": performance,
        "campaign_gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "controller_tuning_attempted": False,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "fallback_attempted": False,
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
                    "production": output["production"],
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
