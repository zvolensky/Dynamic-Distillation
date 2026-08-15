#!/usr/bin/env python
"""Prepare or execute DD-215's frozen reusable-session live proof."""

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
import run_core_v3_terminal_inventory_control_bdf2_60s_production as dd213  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence as dd204  # noqa: E402
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_session_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2ProductionSession,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    terminal_inventory_control_step_pattern,
)


SCHEMA = "dd215-core-v3-bdf2-reusable-session-proof-contract-v1"
RESULT_SCHEMA = "dd215-core-v3-bdf2-reusable-session-proof-result-v1"
DD213_CONTRACT = dd213.CONTRACT
DD213_RESULT = Path(
    "logs/dd213_core_v3_terminal_inventory_control_bdf2_60s_production_20260814.json"
)
DD214_DOC = Path("docs/dd_214_core_v3_reusable_production_session_20260814.md")
CONTRACT = Path("logs/dd215_core_v3_bdf2_reusable_session_proof_contract_20260815.json")
RESULT = Path("logs/dd215_core_v3_bdf2_reusable_session_proof_20260815")
CONTRACT_DOC = Path(
    "docs/dd_215_core_v3_bdf2_reusable_session_proof_contract_20260815.md"
)
RESULT_DOC = Path("docs/dd_215_core_v3_bdf2_reusable_session_proof_20260815.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/persistent_parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_parallel_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_session_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "tools/run_core_v3_bdf2_reusable_session_proof.py",
    "tests/test_core_v3_bdf2_reusable_session_proof.py",
)


def _paths(
    duration_seconds: float = 2.0,
    coarse_step_seconds: float = 0.25,
    refined_step_seconds: float = 0.125,
) -> dict[str, Any]:
    return dd213._paths(
        duration_seconds=duration_seconds,
        coarse_step_seconds=coarse_step_seconds,
        refined_step_seconds=refined_step_seconds,
    )


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    limits = payload["performance_limits"]
    return "\n".join(
        (
            "# DD-215 Reusable Production-Session Proof Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Coarse path: `{paths['coarse_steps']} x {paths['coarse_step_seconds']} s`",
            f"- Refined path: `{paths['refined_steps']} x {paths['refined_step_seconds']} s`",
            "- Lifecycle: one eight-worker session, two uniquely named trajectories, one final close",
            "- Predictor: `linear_extrapolation`",
            "- Science: unchanged DD-213 equations, controls, solver, grids, and DWSIM PR provider",
            f"- Logical-call / total-wall ceilings: `{limits['logical_provider_calls']}` / `{limits['session_wall_sec']} s`",
            "- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    timing = payload["session"]["timing"]
    return "\n".join(
        (
            "# DD-215 Reusable Production-Session Proof Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}` / `{payload['requested_roots']}`",
            f"- Worst residual / condition: `{payload['worst_residual']:.6e}` / `{payload['worst_condition']:.6e}`",
            f"- Startup / trajectories / shutdown: `{timing['startup_wall_seconds']:.3f}` / `{timing['trajectory_wall_seconds']:.3f}` / `{timing['shutdown_wall_seconds']:.3f} s`",
            f"- Total session wall: `{timing['total_wall_seconds']:.3f} s`",
            f"- Matrix count / logical calls: `{payload['worker']['matrix_count']}` / `{payload['logical_provider_calls']}`",
            f"- Intermediate shutdown observed: `{payload['session']['intermediate_shutdown_observed']}`",
            "- Retry, tuning, alternate grid, or fallback: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = dd209._load(DD213_CONTRACT)
    result = dd209._load(DD213_RESULT)
    if result["completed_roots"] != 720 or not all(
        passed
        for name, passed in result["campaign_gates"].items()
        if name != "wall_clock"
    ):
        raise RuntimeError("DD-215 requires DD-213's accepted scientific evidence")
    if not (ROOT / DD214_DOC).exists():
        raise RuntimeError("DD-215 requires DD-214")
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
            "campaign_id": "DD-215",
            "preparation_base_commit": dd209._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd209._sha(ROOT / path)
                for path in (DD213_CONTRACT, DD213_RESULT, DD214_DOC)
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
                "logical_provider_calls": 180000,
                "startup_wall_sec": 30.0,
                "shutdown_wall_sec": 60.0,
                "deadline_seconds": 120.0,
                "session_wall_sec": 120.0,
            },
            "implementation_sha256": {
                path: dd209._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either trajectory fails to complete every root",
                "any root or shared-time scientific gate fails",
                "the executor shuts down or the session closes between trajectories",
                "any Jacobian misses a worker or any root misses its worker-basis lifecycle",
                "provider ownership, call, startup, shutdown, deadline, or total-wall gate fails",
                "a retry, alternate grid, tuning, fallback, clipping, projection, or equation change occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "trajectory_attempted": False,
            "retry_authorized": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = dd209._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-215 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd209._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-215 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-215 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-215 implementation changed: {path}")
    if dd209._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-215 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-215 result exists; rerun prohibited")
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
    deadline = time.perf_counter() + float(performance_limits["deadline_seconds"])
    spawn = mp.get_context("spawn")
    session = TerminalInventoryControlBDF2ProductionSession(
        lambda: ProcessPoolExecutor(
            max_workers=int(production["worker_count"]),
            mp_context=spawn,
            initializer=dd204._worker_initialize,
            initargs=(str((ROOT / contract_path).resolve()),),
        ),
        dd204._worker_evaluate,
        pattern=pattern,
        step=settings.jacobian_step,
        worker_count=int(production["worker_count"]),
        startup_probe=dd204._worker_ping,
        startup_probe_args=(production["startup_ping_delay_sec"],),
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
        duration_seconds=float(paths["duration_seconds"]),
        deadline_monotonic=deadline,
        bdf2_initial_guess_policy=production["bdf2_initial_guess_policy"],
    )
    session.start()
    try:
        coarse = session.run_trajectory(
            **common,
            step_seconds=float(paths["coarse_step_seconds"]),
            name="dd215_coarse",
        )
        after_coarse_state = session.state
        after_coarse_shutdown = session.timing.shutdown_wall_seconds
        refined = session.run_trajectory(
            **common,
            step_seconds=float(paths["refined_step_seconds"]),
            name="dd215_refined",
        )
        before_close_state = session.state
        before_close_shutdown = session.timing.shutdown_wall_seconds
        worker_evidence = [asdict(item) for item in session.jacobians.evidence]
        worker_calls = session.jacobians.logical_provider_calls
    finally:
        session.close()

    timing = asdict(session.timing)
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
    complete_paths = (
        coarse.completed
        and coarse.completed_steps == paths["coarse_steps"]
        and refined.completed
        and refined.completed_steps == paths["refined_steps"]
    )
    shared = None
    cross_grid = None
    response_gates = {
        "coarse": False,
        "refined": False,
        "cross_grid_explained": False,
        "cross_grid_response_relative": False,
    }
    if complete_paths:
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
    worst_residual = max(float(item["residual_inf_norm"]) for item in all_steps)
    worst_condition = max(float(item["jacobian_condition"]) for item in all_steps)
    intermediate_shutdown = (
        after_coarse_shutdown is not None or before_close_shutdown is not None
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
        "session_remained_open": after_coarse_state == "started"
        and before_close_state == "started"
        and not intermediate_shutdown,
        "session_closed_once": session.state == "closed"
        and timing["shutdown_wall_seconds"] is not None,
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
        "startup_wall": timing["startup_wall_seconds"]
        < performance_limits["startup_wall_sec"],
        "shutdown_wall": timing["shutdown_wall_seconds"]
        < performance_limits["shutdown_wall_sec"],
        "session_wall": timing["total_wall_seconds"]
        < performance_limits["session_wall_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-215",
        "classification": (
            "reusable_production_session_proof_passed"
            if passed
            else "reusable_production_session_proof_failed"
        ),
        "decision": (
            "adopt_reusable_production_session_lifecycle"
            if passed
            else "retain_dd214_property_free_boundary"
        ),
        "contract_commit": dd209._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "paths": paths,
        "requested_roots": requested_roots,
        "completed_roots": len(all_steps),
        "stop_reasons": {
            "coarse": coarse.stop_reason,
            "refined": refined.stop_reason,
        },
        "coarse": {"steps": coarse_steps},
        "refined": {"steps": refined_steps},
        "shared_time_refinement": shared,
        "response": {"coarse": coarse_response, "refined": refined_response},
        "cross_grid": cross_grid,
        "response_gates": response_gates,
        "worst_residual": worst_residual,
        "worst_condition": worst_condition,
        "session": {
            "startup_process_ids": list(session.startup_process_ids),
            "after_coarse_state": after_coarse_state,
            "before_close_state": before_close_state,
            "final_state": session.state,
            "intermediate_shutdown_observed": intermediate_shutdown,
            "segments": [asdict(item) for item in session.segments],
            "timing": timing,
        },
        "worker": {
            "matrix_count": len(worker_evidence),
            "basis": basis,
            "evidence": worker_evidence,
        },
        "logical_provider_calls": logical_calls,
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "campaign_gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_grid_attempted": False,
        "controller_tuning_attempted": False,
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
