#!/usr/bin/env python
"""Prepare or execute DD-208's live production-backend replay."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
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

import run_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_trajectory as dd202  # noqa: E402
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


SCHEMA = "dd208-core-v3-bdf2-production-backend-replay-contract-v1"
RESULT_SCHEMA = "dd208-core-v3-bdf2-production-backend-replay-result-v1"
DD204_CONTRACT = dd204.CONTRACT
DD204_RESULT = Path(
    "logs/dd204_core_v3_terminal_inventory_control_bdf2_parallel_equivalence_20260814.json"
)
DD206_RESULT = Path(
    "logs/dd206_core_v3_terminal_inventory_control_bdf2_parallel_replay_adjudication_20260814.json"
)
DD207_DOC = Path(
    "docs/dd_207_core_v3_persistent_parallel_bdf2_production_integration_20260814.md"
)
CONTRACT = Path(
    "logs/dd208_core_v3_terminal_inventory_control_bdf2_production_backend_replay_contract_20260814.json"
)
RESULT = Path(
    "logs/dd208_core_v3_terminal_inventory_control_bdf2_production_backend_replay_20260814"
)
CONTRACT_DOC = Path(
    "docs/dd_208_core_v3_terminal_inventory_control_bdf2_production_backend_replay_contract_20260814.md"
)
RESULT_DOC = Path(
    "docs/dd_208_core_v3_terminal_inventory_control_bdf2_production_backend_replay_20260814.md"
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/persistent_parallel_colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_parallel_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_bdf2_trajectory_v1.py",
    "tests/test_core_v3_terminal_inventory_control_bdf2_production_backend_replay.py",
    "tools/run_core_v3_terminal_inventory_control_bdf2_production_backend_replay.py",
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


def _normalized(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def _maximum_numeric_difference(first: Any, second: Any) -> float:
    differences: list[float] = []

    def visit(left: Any, right: Any) -> None:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            if set(left) != set(right):
                differences.append(float("inf"))
                return
            for key in left:
                visit(left[key], right[key])
            return
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                differences.append(float("inf"))
                return
            for left_item, right_item in zip(left, right, strict=True):
                visit(left_item, right_item)
            return
        if (
            isinstance(left, (int, float))
            and not isinstance(left, bool)
            and isinstance(right, (int, float))
            and not isinstance(right, bool)
        ):
            differences.append(abs(float(left) - float(right)))

    visit(_normalized(first), _normalized(second))
    return max(differences, default=0.0)


def _basis_summary(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    roots = sorted({item["root_epoch"] for item in evidence})
    rebuilds = {
        root: sum(
            int(item["basis_rebuilds"])
            for item in evidence
            if item["root_epoch"] == root
        )
        for root in roots
    }
    return {
        "root_count": len(roots),
        "rebuilds_by_root": rebuilds,
        "pass": bool(roots) and all(value == 4 for value in rebuilds.values()),
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    limits = payload["limits"]
    return "\n".join(
        (
            "# DD-208 Production-Backend Live Replay Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Path: one `0.125 s` backward-Euler startup plus one `0.125 s` BDF2 root",
            "- Reference: immutable DD-204 accepted parallel reports",
            "- Backend: reusable Core V3 persistent parallel coordinator and BDF2 adapter",
            f"- Exact-report limit: `{limits['report_absolute']}`",
            f"- Trajectory regression limit: `{limits['maximum_reference_wall_ratio']}x` DD-204 parallel wall",
            f"- Governed wall limit: `{limits['wall_clock_sec']} s`",
            "- Retry, alternate step, tuning, fallback, clipping, projection, and longer trajectory: prohibited",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    performance = payload["performance"]
    return "\n".join(
        (
            "# DD-208 Production-Backend Live Replay Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots / Jacobians: `{payload['completed_roots']}` / `{payload['matrix_count']}`",
            f"- Maximum report difference: `{payload['report_comparison']['maximum_numeric_difference']:.6e}`",
            f"- Reference / production trajectory wall: `{performance['reference_parallel_wall_sec']:.6f}` / `{performance['trajectory_wall_sec']:.6f} s`",
            f"- Wall ratio: `{performance['reference_wall_ratio']:.3f}x`",
            f"- Adjusted startup / governed wall: `{performance['startup_wall_sec_adjusted']:.3f}` / `{performance['total_governed_wall_sec']:.3f} s`",
            f"- Logical provider calls: `{payload['logical_provider_calls']}`",
            "- Retry, tuning, alternate step, or fallback: `False`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = _load(DD204_CONTRACT)
    accepted = _load(DD204_RESULT)
    authorization = _load(DD206_RESULT)
    if not accepted["pass_gate"]:
        raise RuntimeError("DD-208 requires accepted DD-204")
    if not authorization["pass_gate"] or authorization["decision"] != (
        "adopt_persistent_parallel_bdf2_trajectory_path"
    ):
        raise RuntimeError("DD-208 requires accepted DD-206")
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
            "campaign_id": "DD-208",
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD204_CONTRACT, DD204_RESULT, DD206_RESULT, DD207_DOC)
            },
            "integration": dict(source["integration"]),
            "comparison_reference": {
                "parallel_reports": accepted["parallel"]["reports"],
                "parallel_wall_sec": accepted["performance"][
                    "parallel_trajectory_wall_sec"
                ],
                "matrix_count": len(accepted["worker_evidence"]),
            },
            "limits": {
                "report_absolute": 1.0e-12,
                "scaled_residual": 1.0e-8,
                "required_rank": 58,
                "condition": 1.0e8,
                "maximum_reference_wall_ratio": 1.25,
                "logical_provider_calls": 30000,
                "startup_wall_sec": 30.0,
                "wall_clock_sec": 60.0,
            },
            "implementation_sha256": {
                path: _sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either production-backend root fails an inherited numerical or physical gate",
                "serialized root reports differ from DD-204 beyond the frozen exact limit",
                "matrix count, all-worker participation, or per-root basis lifecycle differs",
                "provider ownership fails or any fallback occurs",
                "trajectory wall exceeds 1.25 times DD-204 or another wall/call ceiling is exceeded",
                "a retry, alternate step, tuning, clipping, projection, fallback, or longer trajectory occurs",
            ],
            "property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "trajectory_attempted": False,
            "retry_authorized": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-208 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-208 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-208 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-208 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-208 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-208 result exists; rerun prohibited")
    _git("ls-files", "--error-unmatch", str(contract_path))


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = _load(contract_path)
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
    integration = payload["integration"]
    limits = payload["limits"]
    pattern = terminal_inventory_control_step_pattern(controlled)
    total_started = time.perf_counter()
    deadline = total_started + float(limits["wall_clock_sec"])
    spawn = mp.get_context("spawn")
    pool_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=int(integration["worker_count"]),
        mp_context=spawn,
        initializer=dd204._worker_initialize,
        initargs=(str((ROOT / contract_path).resolve()),),
    ) as pool:
        pings = [
            pool.submit(dd204._worker_ping, integration["startup_ping_delay_sec"])
            for _ in range(int(integration["worker_count"]))
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
            worker_count=int(integration["worker_count"]),
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
            duration_seconds=integration["duration_seconds"],
            step_seconds=integration["step_seconds"],
            settings=settings,
            name="dd208_production_backend",
            step_solver_backend=backend,
            deadline_monotonic=deadline,
        )
        trajectory_wall = time.perf_counter() - trajectory_started
        worker_evidence = [asdict(item) for item in jacobians.evidence]
        worker_calls = jacobians.logical_provider_calls
    total_wall = time.perf_counter() - total_started

    source_limits = _load(dd204.DD202_CONTRACT)["limits"]
    reports = [
        dd202.base._step_report(record, spec, source_limits, 58)
        for record in trajectory.records
    ]
    expected_reports = payload["comparison_reference"]["parallel_reports"]
    normalized_equal = _normalized(reports) == _normalized(expected_reports)
    maximum_difference = _maximum_numeric_difference(reports, expected_reports)
    provider_summary = dd202.base.dd187.dd186._provider_summary(audit)
    logical_calls = int(provider_summary["total_calls"] + worker_calls)
    basis = _basis_summary(worker_evidence)
    performance = {
        "reference_parallel_wall_sec": float(
            payload["comparison_reference"]["parallel_wall_sec"]
        ),
        "trajectory_wall_sec": float(trajectory_wall),
        "reference_wall_ratio": float(
            trajectory_wall / payload["comparison_reference"]["parallel_wall_sec"]
        ),
        "startup_wall_sec_raw": float(startup_raw),
        "startup_wall_sec_adjusted": float(startup_adjusted),
        "total_governed_wall_sec": float(total_wall),
    }
    gates = {
        "complete": trajectory.completed
        and trajectory.completed_steps == integration["requested_roots"],
        "methods": [record.method for record in trajectory.records]
        == integration["methods"],
        "roots": len(reports) == 2
        and all(all(report["gates"].values()) for report in reports)
        and max(report["residual_inf_norm"] for report in reports)
        < limits["scaled_residual"]
        and min(report["jacobian_rank"] for report in reports)
        == limits["required_rank"]
        and max(report["jacobian_condition"] for report in reports)
        < limits["condition"],
        "exact_reports": normalized_equal
        and maximum_difference < limits["report_absolute"],
        "matrix_count": len(worker_evidence)
        == payload["comparison_reference"]["matrix_count"],
        "worker_participation": all(
            len(item["worker_ids"]) == integration["worker_count"]
            and item["color_count"] == integration["color_count"]
            and item["task_count"] == integration["tasks_per_matrix"]
            for item in worker_evidence
        ),
        "worker_basis": basis["pass"]
        and basis["root_count"] == integration["requested_roots"],
        "provider": provider_summary["pass"]
        and all(item["provider_pass"] for item in worker_evidence)
        and not any(item["fallback_attempted"] for item in worker_evidence),
        "provider_calls": logical_calls < limits["logical_provider_calls"],
        "trajectory_wall": performance["reference_wall_ratio"]
        <= limits["maximum_reference_wall_ratio"],
        "startup_wall": startup_adjusted < limits["startup_wall_sec"],
        "wall_clock": total_wall < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-208",
        "classification": (
            "controlled_bdf2_production_backend_replay_passed"
            if passed
            else "controlled_bdf2_production_backend_replay_failed"
        ),
        "decision": (
            "retire_campaign_local_parallel_bdf2_closures"
            if passed
            else "retain_campaign_local_parallel_bdf2_closures"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "completed_roots": len(reports),
        "matrix_count": len(worker_evidence),
        "reports": reports,
        "report_comparison": {
            "serialized_exact": normalized_equal,
            "maximum_numeric_difference": maximum_difference,
        },
        "worker": {
            "startup_ping_process_ids": ping_ids,
            "basis": basis,
            "evidence": worker_evidence,
        },
        "provider": provider_summary,
        "logical_provider_calls": logical_calls,
        "performance": performance,
        "campaign_gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_step_attempted": False,
        "controller_tuning_attempted": False,
        "longer_trajectory_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    provider.set_exact_state_memoization(False, clear=True)
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
