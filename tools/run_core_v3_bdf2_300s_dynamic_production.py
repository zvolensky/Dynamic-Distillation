#!/usr/bin/env python
"""Prepare or execute DD-218's frozen five-minute dynamic production run."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
import multiprocessing as mp
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_trajectory as dd202  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_30s_production as dd209  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_parallel_equivalence as dd204  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_predictor_benchmark as dd212  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_production_backend_replay as dd208  # noqa: E402
from dynamic_distillation.core_v3.production_session_timing_policy_v1 import (  # noqa: E402
    ProductionSegmentTimingLimit,
    ProductionSessionTimingLimits,
    assess_production_session_timing,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_session_v1 import (  # noqa: E402
    TerminalInventoryControlBDF2ProductionSession,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    terminal_inventory_control_step_pattern,
)


SCHEMA = "dd218-core-v3-bdf2-300s-dynamic-production-contract-v1"
RESULT_SCHEMA = "dd218-core-v3-bdf2-300s-dynamic-production-result-v1"
DD217_CONTRACT = Path(
    "logs/dd217_core_v3_bdf2_60s_single_grid_production_contract_20260815.json"
)
DD217_RESULT = Path("logs/dd217_core_v3_bdf2_60s_single_grid_production_20260815.json")
CONTRACT = Path(
    "logs/dd218_core_v3_bdf2_300s_dynamic_production_contract_20260815.json"
)
RESULT = Path("logs/dd218_core_v3_bdf2_300s_dynamic_production_20260815")
CONTRACT_DOC = Path(
    "docs/dd_218_core_v3_bdf2_300s_dynamic_production_contract_20260815.md"
)
RESULT_DOC = Path("docs/dd_218_core_v3_bdf2_300s_dynamic_production_20260815.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/persistent_parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/production_session_timing_policy_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_parallel_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_session_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "tools/run_core_v3_bdf2_300s_dynamic_production.py",
    "tests/test_core_v3_bdf2_300s_dynamic_production.py",
)


def _integration() -> dict[str, Any]:
    return {
        "duration_seconds": 300.0,
        "step_seconds": 0.25,
        "steps": 1200,
        "name": "dd218_dynamic_300s",
    }


def _timing_limits(payload: Mapping[str, Any]) -> ProductionSessionTimingLimits:
    values = payload["timing_limits"]
    return ProductionSessionTimingLimits(
        segment_limits=(
            ProductionSegmentTimingLimit(
                payload["integration"]["name"], values["segment_wall_sec"]
            ),
        ),
        maximum_startup_wall_seconds=values["startup_wall_sec"],
        maximum_active_wall_seconds=values["active_wall_sec"],
        maximum_shutdown_wall_seconds=values["shutdown_wall_sec"],
        maximum_total_wall_seconds=values["total_wall_sec"],
        maximum_unattributed_wall_seconds=values["unattributed_wall_sec"],
        identity_tolerance_seconds=values["identity_tolerance_sec"],
    )


def _compact_steps(
    steps: Sequence[Mapping[str, Any]], sample_every_steps: int
) -> list[Mapping[str, Any]]:
    if int(sample_every_steps) <= 0:
        raise ValueError("DD-218 evidence sample interval must be positive")
    selected = [
        item
        for offset, item in enumerate(steps)
        if offset == 0
        or int(item["index"]) % int(sample_every_steps) == 0
        or offset == len(steps) - 1
    ]
    return selected


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    integration = payload["integration"]
    timing = payload["timing_limits"]
    return "\n".join(
        (
            "# DD-218 Five-Minute Dynamic Production Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Path: `{integration['steps']} x {integration['step_seconds']} s = {integration['duration_seconds']} s`",
            "- Model: accepted seven-volume Core V3 controlled DAE with DWSIM PR",
            "- Session: one reusable eight-worker backend and one final close",
            "- Initial guess: `linear_extrapolation` after one backward-Euler startup",
            f"- Active / total-session limits: `{timing['segment_wall_sec']}` / `{timing['total_wall_sec']} s`",
            f"- Logical provider-call ceiling: `{payload['logical_provider_call_limit']}`",
            f"- DD-217 60-second prefix limit: `{payload['prefix_science_limit']}`",
            f"- Evidence: canonical full hashes plus first/every-{payload['evidence']['sample_every_seconds']}-second/final samples",
            "- Retry, alternate grid, tuning, fallback, clipping, projection, or equation change: prohibited",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    timing = payload["session_timing"]
    return "\n".join(
        (
            "# DD-218 Five-Minute Dynamic Production Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload['completed_roots']}` / `{payload['requested_roots']}`",
            f"- Worst residual / condition: `{payload['root_summary']['worst_residual']:.6e}` / `{payload['root_summary']['worst_condition']:.6e}`",
            f"- DD-217 prefix maximum difference: `{payload['prefix_comparison']['maximum_numeric_difference']:.6e}`",
            f"- Startup / active / shutdown / total: `{timing['startup_wall_seconds']:.3f}` / `{timing['trajectory_wall_seconds']:.3f}` / `{timing['shutdown_wall_seconds']:.3f}` / `{timing['total_wall_seconds']:.3f} s`",
            f"- Simulated/active-wall ratio: `{payload['performance']['simulated_seconds_per_active_wall_second']:.4f}`",
            f"- Matrices / logical calls: `{payload['worker_summary']['matrix_count']}` / `{payload['logical_provider_calls']}`",
            f"- Saved samples: `{len(payload['sampled_steps'])}`; full step SHA-256: `{payload['evidence']['steps_sha256']}`",
            "- Retry, tuning, alternate grid, or fallback: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = dd209._load(DD217_CONTRACT)
    qualification = dd209._load(DD217_RESULT)
    if not qualification["pass_gate"] or qualification["decision"] != (
        "adopt_60s_single_grid_production_segment"
    ):
        raise RuntimeError("DD-218 requires accepted DD-217 production segment")
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
            "limits",
            "required_rank",
        )
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "result_schema_id": RESULT_SCHEMA,
            "campaign_id": "DD-218",
            "preparation_base_commit": dd209._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd209._sha(ROOT / path)
                for path in (DD217_CONTRACT, DD217_RESULT)
            },
            "integration": _integration(),
            "production": source["production"],
            "timing_limits": {
                "startup_wall_sec": 10.0,
                "segment_wall_sec": 900.0,
                "active_wall_sec": 900.0,
                "shutdown_wall_sec": 45.0,
                "total_wall_sec": 960.0,
                "unattributed_wall_sec": 2.0,
                "identity_tolerance_sec": 1.0e-6,
            },
            "deadline_seconds": 930.0,
            "logical_provider_call_limit": 5500000,
            "prefix_steps": 240,
            "prefix_science_limit": 1.0e-8,
            "evidence": {
                "sample_every_seconds": 5.0,
                "sample_every_steps": 20,
                "retain_first": True,
                "retain_final": True,
                "hash_all_steps": True,
                "hash_all_worker_evidence": True,
            },
            "implementation_sha256": {
                path: dd209._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "any of 1200 roots fails closure or an inherited scientific gate",
                "the first 240 accepted science records differ from DD-217",
                "full response, timing identity, provider, worker, call, or deadline gate fails",
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
        raise RuntimeError("DD-218 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd209._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-218 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-218 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-218 implementation changed: {path}")
    if dd209._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-218 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-218 result exists; rerun prohibited")
    dd209._git("ls-files", "--error-unmatch", str(contract_path))


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = dd209._load(contract_path)
    _verify(payload, contract_path, result_path)
    qualification = dd209._load(DD217_RESULT)
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
    integration = payload["integration"]
    production = payload["production"]
    pattern = terminal_inventory_control_step_pattern(controlled)
    deadline = time.perf_counter() + float(payload["deadline_seconds"])
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
    session.start()
    try:
        trajectory = session.run_trajectory(
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
            duration_seconds=float(integration["duration_seconds"]),
            step_seconds=float(integration["step_seconds"]),
            name=integration["name"],
            deadline_monotonic=deadline,
            bdf2_initial_guess_policy=production["bdf2_initial_guess_policy"],
        )
        before_close_state = session.state
        before_close_shutdown = session.timing.shutdown_wall_seconds
        worker_evidence = [asdict(item) for item in session.jacobians.evidence]
        worker_calls = session.jacobians.logical_provider_calls
    finally:
        session.close()

    timing = session.timing
    timing_assessment = assess_production_session_timing(
        timing, session.segments, _timing_limits(payload)
    )
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = dd202.base.dd187.dd186._provider_summary(audit)
    response, steps = dd202.base._path_report(
        trajectory,
        spec,
        inventory,
        payload["limits"],
        payload["required_rank"],
    )
    prefix_count = int(payload["prefix_steps"])
    prefix = [dd212._science_report(item) for item in steps[:prefix_count]]
    expected_prefix = [
        dd212._science_report(item) for item in qualification["steps"][:prefix_count]
    ]
    prefix_difference = dd208._maximum_numeric_difference(prefix, expected_prefix)
    requested_roots = int(integration["steps"])
    basis = dd209._basis_summary(worker_evidence, int(production["worker_count"]))
    logical_calls = int(provider_summary["total_calls"] + worker_calls)
    limits = payload["limits"]
    response_pass = (
        response["component_inventory_identity_max_abs_lbmol"]
        < limits["global_component_inventory_identity_lbmol"]
        and response["total_inventory_relative_error"]
        < limits["integrated_response_relative_error"]
        and response["total_inventory_strictly_increasing"]
    )
    gates = {
        "trajectory_complete": trajectory.completed
        and trajectory.completed_steps == requested_roots,
        "roots": len(steps) == requested_roots
        and all(all(item["gates"].values()) for item in steps),
        "response": response_pass,
        "qualified_prefix": prefix_difference < payload["prefix_science_limit"],
        "session_open_before_close": before_close_state == "started"
        and before_close_shutdown is None,
        "timing_policy": timing_assessment.pass_gate,
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
        "provider_calls": logical_calls < payload["logical_provider_call_limit"],
        "deadline": trajectory.stop_reason != "deadline",
    }
    passed = all(gates.values())
    timing_payload = asdict(timing_assessment)
    timing_payload["gates"] = dict(timing_assessment.gates)
    timing_payload["pass_gate"] = timing_assessment.pass_gate
    response_summary = {
        key: value for key, value in response.items() if not isinstance(value, list)
    }
    evidence = payload["evidence"]
    sampled_steps = _compact_steps(steps, int(evidence["sample_every_steps"]))
    root_summary = {
        "worst_residual": max(float(item["residual_inf_norm"]) for item in steps),
        "worst_condition": max(float(item["jacobian_condition"]) for item in steps),
        "maximum_equilibrium_residual": max(
            float(item["maximum_equilibrium_residual"]) for item in steps
        ),
        "maximum_component_conservation_relative_error": max(
            float(item["component_conservation_relative_error"]) for item in steps
        ),
        "maximum_energy_conservation_relative_error": max(
            float(item["energy_conservation_relative_error"]) for item in steps
        ),
        "maximum_controller_equation_closure": max(
            float(item["controller_equation_closure"]) for item in steps
        ),
        "total_nfev": sum(int(item["nfev"]) for item in steps),
        "total_njev": sum(int(item["njev"]) for item in steps),
    }
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-218",
        "classification": (
            "five_minute_dynamic_production_passed"
            if passed
            else "five_minute_dynamic_production_failed"
        ),
        "decision": (
            "accept_five_minute_core_v3_dynamics"
            if passed
            else "retain_dd217_60s_production_boundary"
        ),
        "contract_commit": dd209._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "integration": integration,
        "requested_roots": requested_roots,
        "completed_roots": len(steps),
        "stop_reason": trajectory.stop_reason,
        "prefix_comparison": {
            "reference": str(DD217_RESULT).replace("\\", "/"),
            "steps": prefix_count,
            "maximum_numeric_difference": prefix_difference,
        },
        "root_summary": root_summary,
        "response_summary": response_summary,
        "endpoint": steps[-1],
        "sampled_steps": sampled_steps,
        "session_timing": asdict(timing),
        "timing_assessment": timing_payload,
        "performance": {
            "simulated_seconds_per_active_wall_second": float(
                integration["duration_seconds"] / timing.trajectory_wall_seconds
            ),
            "simulated_seconds_per_complete_session_wall_second": float(
                integration["duration_seconds"] / timing.total_wall_seconds
            ),
        },
        "worker_summary": {
            "startup_process_ids": list(session.startup_process_ids),
            "matrix_count": len(worker_evidence),
            "basis": basis,
        },
        "logical_provider_calls": logical_calls,
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "evidence": {
            **evidence,
            "steps_sha256": dd209._hash(steps),
            "worker_evidence_sha256": dd209._hash(worker_evidence),
            "response_histories_sha256": dd209._hash(
                {
                    key: value
                    for key, value in response.items()
                    if isinstance(value, list)
                }
            ),
            "full_step_count": len(steps),
            "full_worker_matrix_count": len(worker_evidence),
        },
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
                    "integration": output["integration"],
                    "timing_limits": output["timing_limits"],
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
