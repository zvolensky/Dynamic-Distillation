#!/usr/bin/env python
"""Prepare or execute DD-212's frozen BDF2 predictor benchmark."""

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
import run_core_v3_terminal_inventory_control_bdf2_production_backend_replay as dd208  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_worker_scaling as dd210  # noqa: E402
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


SCHEMA = "dd212-core-v3-bdf2-predictor-benchmark-contract-v1"
RESULT_SCHEMA = "dd212-core-v3-bdf2-predictor-benchmark-result-v1"
DD209_CONTRACT = dd209.CONTRACT
DD209_RESULT = dd210.DD209_RESULT
DD210_RESULT = Path(
    "logs/dd210_core_v3_terminal_inventory_control_bdf2_worker_scaling_20260814.json"
)
DD211_DOC = Path("docs/dd_211_core_v3_bdf2_linear_coordinate_predictor_20260814.md")
CONTRACT = Path(
    "logs/dd212_core_v3_terminal_inventory_control_bdf2_predictor_benchmark_contract_20260814.json"
)
RESULT = Path(
    "logs/dd212_core_v3_terminal_inventory_control_bdf2_predictor_benchmark_20260814"
)
CONTRACT_DOC = Path(
    "docs/dd_212_core_v3_terminal_inventory_control_bdf2_predictor_benchmark_contract_20260814.md"
)
RESULT_DOC = Path(
    "docs/dd_212_core_v3_terminal_inventory_control_bdf2_predictor_benchmark_20260814.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/persistent_parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_parallel_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "tools/run_core_v3_terminal_inventory_control_bdf2_predictor_benchmark.py",
    "tests/test_core_v3_terminal_inventory_control_bdf2_predictor_benchmark.py",
)


def _science_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Select accepted science while excluding expected solver-work changes."""
    return {
        key: report[key]
        for key in (
            "index",
            "time_seconds",
            "method",
            "inventory_lbmol",
            "rate_coordinates",
            "algebraic_coordinates",
            "controller_memory",
            "level_fraction",
            "distillate_lbmolph",
            "bottoms_lbmolph",
            "physical",
        )
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    limits = payload["limits"]
    integration = payload["integration"]
    return "\n".join(
        (
            "# DD-212 BDF2 Linear-Predictor Benchmark Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Paths: `{integration['steps']} x {integration['step_seconds']} s` baseline and predictor",
            f"- Worker count: `{integration['worker_count']}` with separate fresh pools",
            "- Baseline policy: `accepted_endpoint`",
            "- Candidate policy: `linear_extrapolation`",
            f"- Accepted-science absolute limit: `{limits['science_absolute']}`",
            f"- Required matrix reduction / speedup: `{limits['minimum_matrix_reduction_fraction']}` / `{limits['minimum_speedup']}x`",
            f"- Governed wall limit: `{limits['wall_clock_sec']} s`",
            "- Retry, alternate duration/grid/predictor, tuning, fallback, clipping, projection, or equation change: prohibited",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    performance = payload["performance"]
    work = payload["work"]
    return "\n".join(
        (
            "# DD-212 BDF2 Linear-Predictor Benchmark Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Baseline/predictor trajectory wall: `{performance['baseline_trajectory_wall_sec']:.6f}` / `{performance['predictor_trajectory_wall_sec']:.6f} s`",
            f"- Predictor speedup: `{performance['predictor_speedup']:.3f}x`",
            f"- Baseline/predictor matrices: `{work['baseline_matrix_count']}` / `{work['predictor_matrix_count']}`",
            f"- Matrix/call reductions: `{work['matrix_reduction_fraction']:.3%}` / `{work['call_reduction_fraction']:.3%}`",
            f"- Maximum accepted-science difference: `{payload['science_comparison']['maximum_numeric_difference']:.6e}`",
            f"- Governed wall: `{performance['total_governed_wall_sec']:.3f} s`",
            "- Retry, tuning, alternate predictor, or fallback: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = dd209._load(DD209_CONTRACT)
    horizon = dd209._load(DD209_RESULT)
    scaling = dd209._load(DD210_RESULT)
    if not horizon["pass_gate"]:
        raise RuntimeError("DD-212 requires accepted DD-209")
    if not scaling["pass_gate"] or scaling["decision"] != (
        "adopt_eight_worker_production_jacobian_backend"
    ):
        raise RuntimeError("DD-212 requires accepted DD-210")
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
            "physical_refinement_limits",
        )
    }
    payload.update(
        {
            "schema_id": SCHEMA,
            "result_schema_id": RESULT_SCHEMA,
            "campaign_id": "DD-212",
            "preparation_base_commit": dd209._git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): dd209._sha(ROOT / path)
                for path in (DD209_CONTRACT, DD209_RESULT, DD210_RESULT, DD211_DOC)
            },
            "integration": {
                "duration_seconds": 10.0,
                "step_seconds": 0.25,
                "steps": 40,
                "worker_count": 8,
                "color_count": 17,
                "tasks_per_matrix": 34,
                "startup_ping_delay_sec": 0.15,
                "baseline_policy": "accepted_endpoint",
                "predictor_policy": "linear_extrapolation",
            },
            "root_limits": source["limits"],
            "limits": {
                "science_absolute": 1.0e-9,
                "minimum_matrix_reduction_fraction": 0.10,
                "minimum_call_reduction_fraction": 0.08,
                "minimum_speedup": 1.10,
                "logical_provider_calls": 400000,
                "startup_wall_sec": 30.0,
                "wall_clock_sec": 180.0,
            },
            "implementation_sha256": {
                path: dd209._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either path fails any of 40 roots or an inherited root gate",
                "accepted physical science differs beyond 1e-9",
                "predictor matrix count is not reduced by at least ten percent",
                "predictor logical calls are not reduced by at least eight percent",
                "predictor warm trajectory speedup is below 1.10x",
                "any matrix omits a worker or any root violates basis lifecycle",
                "provider ownership fails or any fallback occurs",
                "call, startup, or governed-wall ceiling is exceeded",
                "a retry, alternate duration, grid, predictor, tuning, clipping, projection, fallback, or equation change occurs",
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
        raise RuntimeError("DD-212 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd209._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-212 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-212 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-212 implementation changed: {path}")
    if dd209._sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-212 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-212 result exists; rerun prohibited")
    dd209._git("ls-files", "--error-unmatch", str(contract_path))


def _run_path(
    payload: Mapping[str, Any],
    contract_path: Path,
    policy: str,
    deadline: float,
) -> dict[str, Any]:
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
    worker_count = int(integration["worker_count"])
    pattern = terminal_inventory_control_step_pattern(controlled)
    spawn = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=spawn,
        initializer=dd204._worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(dd204._worker_ping, integration["startup_ping_delay_sec"])
            for _ in range(worker_count)
        ]
        ping_ids = sorted({int(future.result()) for future in pings})
        startup_raw = time.perf_counter() - pool_started
        startup_adjusted = max(
            startup_raw - float(integration["startup_ping_delay_sec"]), 0.0
        )
        jacobians = PersistentParallelColoredJacobian(
            pool,
            dd204._worker_evaluate,
            pattern=pattern,
            step=settings.jacobian_step,
            worker_count=worker_count,
        )
        backend = TerminalInventoryControlBDF2ParallelStepSolvers(jacobians)
        trajectory_started = time.perf_counter()
        trajectory = run_terminal_inventory_control_bdf2_trajectory(
            controlled,
            spec,
            reference,
            state,
            provider,
            audit,
            initial_inventory_lbmol=inventory,
            initial_controller_memory=memory,
            level_setpoints=setpoints,
            initial_solve_coordinates=coordinates,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            product_reference_lbmolph=products,
            duration_seconds=float(integration["duration_seconds"]),
            step_seconds=float(integration["step_seconds"]),
            settings=settings,
            name="dd212_predictor_equivalence",
            step_solver_backend=backend,
            deadline_monotonic=deadline,
            bdf2_initial_guess_policy=policy,
        )
        trajectory_wall = time.perf_counter() - trajectory_started
        evidence = [asdict(item) for item in jacobians.evidence]
        worker_calls = jacobians.logical_provider_calls
    reports = [
        dd202.base._step_report(record, spec, payload["root_limits"], 58)
        for record in trajectory.records
    ]
    response = None
    if trajectory.records:
        response, _duplicate_reports = dd202.base._path_report(
            trajectory, spec, inventory, payload["root_limits"], 58
        )
    provider_summary = dd202.base.dd187.dd186._provider_summary(audit)
    provider.set_exact_state_memoization(False, clear=True)
    return {
        "policy": policy,
        "completed": bool(trajectory.completed),
        "completed_steps": int(trajectory.completed_steps),
        "stop_reason": trajectory.stop_reason,
        "reports": reports,
        "science_reports": [_science_report(report) for report in reports],
        "response": response,
        "matrix_count": len(evidence),
        "worker_evidence": evidence,
        "basis": dd209._basis_summary(evidence, worker_count),
        "provider": provider_summary,
        "logical_provider_calls": int(provider_summary["total_calls"] + worker_calls),
        "startup_ping_process_ids": ping_ids,
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "trajectory_wall_sec": float(trajectory_wall),
    }


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = dd209._load(contract_path)
    _verify(payload, contract_path, result_path)
    integration = payload["integration"]
    limits = payload["limits"]
    total_started = time.perf_counter()
    deadline = total_started + float(limits["wall_clock_sec"])
    baseline = _run_path(
        payload, contract_path, integration["baseline_policy"], deadline
    )
    predictor = _run_path(
        payload, contract_path, integration["predictor_policy"], deadline
    )
    total_wall = time.perf_counter() - total_started

    science_difference = dd208._maximum_numeric_difference(
        baseline["science_reports"], predictor["science_reports"]
    )
    science_comparison = {
        "serialized_exact": dd208._normalized(baseline["science_reports"])
        == dd208._normalized(predictor["science_reports"]),
        "maximum_numeric_difference": science_difference,
    }
    baseline_matrices = int(baseline["matrix_count"])
    predictor_matrices = int(predictor["matrix_count"])
    baseline_calls = int(baseline["logical_provider_calls"])
    predictor_calls = int(predictor["logical_provider_calls"])
    work = {
        "baseline_matrix_count": baseline_matrices,
        "predictor_matrix_count": predictor_matrices,
        "matrix_reduction_fraction": float(
            (baseline_matrices - predictor_matrices) / baseline_matrices
        ),
        "baseline_logical_provider_calls": baseline_calls,
        "predictor_logical_provider_calls": predictor_calls,
        "call_reduction_fraction": float(
            (baseline_calls - predictor_calls) / baseline_calls
        ),
    }
    performance = {
        "baseline_trajectory_wall_sec": baseline["trajectory_wall_sec"],
        "predictor_trajectory_wall_sec": predictor["trajectory_wall_sec"],
        "predictor_speedup": float(
            baseline["trajectory_wall_sec"] / predictor["trajectory_wall_sec"]
        ),
        "baseline_startup_wall_sec_adjusted": baseline["startup_wall_sec_adjusted"],
        "predictor_startup_wall_sec_adjusted": predictor["startup_wall_sec_adjusted"],
        "total_governed_wall_sec": float(total_wall),
    }

    def path_gate(path: Mapping[str, Any]) -> bool:
        evidence = path["worker_evidence"]
        return (
            path["completed"]
            and path["completed_steps"] == integration["steps"]
            and len(path["reports"]) == integration["steps"]
            and all(all(report["gates"].values()) for report in path["reports"])
            and path["response"] is not None
            and path["response"]["total_inventory_strictly_increasing"]
            and path["basis"]["pass"]
            and path["basis"]["root_count"] == integration["steps"]
            and bool(evidence)
            and all(
                len(item["worker_ids"]) == integration["worker_count"]
                and item["color_count"] == integration["color_count"]
                and item["task_count"] == integration["tasks_per_matrix"]
                and item["provider_pass"]
                and not item["fallback_attempted"]
                for item in evidence
            )
            and path["provider"]["pass"]
        )

    gates = {
        "baseline_path": path_gate(baseline),
        "predictor_path": path_gate(predictor),
        "science_equivalence": science_difference < limits["science_absolute"],
        "matrix_reduction": work["matrix_reduction_fraction"]
        >= limits["minimum_matrix_reduction_fraction"],
        "call_reduction": work["call_reduction_fraction"]
        >= limits["minimum_call_reduction_fraction"],
        "speedup": performance["predictor_speedup"] >= limits["minimum_speedup"],
        "provider_calls": baseline_calls + predictor_calls
        < limits["logical_provider_calls"],
        "startup_wall": max(
            baseline["startup_wall_sec_adjusted"],
            predictor["startup_wall_sec_adjusted"],
        )
        < limits["startup_wall_sec"],
        "wall_clock": total_wall < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-212",
        "classification": (
            "controlled_bdf2_linear_predictor_passed"
            if passed
            else "controlled_bdf2_linear_predictor_failed"
        ),
        "decision": (
            "adopt_linear_extrapolation_bdf2_initial_guess"
            if passed
            else "retain_accepted_endpoint_bdf2_initial_guess"
        ),
        "contract_commit": dd209._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "baseline": baseline,
        "predictor": predictor,
        "science_comparison": science_comparison,
        "work": work,
        "performance": performance,
        "logical_provider_calls": baseline_calls + predictor_calls,
        "campaign_gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_predictor_attempted": False,
        "alternate_grid_attempted": False,
        "controller_tuning_attempted": False,
        "fallback_attempted": False,
        "longer_trajectory_attempted": False,
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
