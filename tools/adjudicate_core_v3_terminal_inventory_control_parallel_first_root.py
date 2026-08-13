#!/usr/bin/env python
"""Prepare or execute DD-192's zero-call DD-191 worker adjudication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_terminal_inventory_control_parallel_first_root as dd191  # noqa: E402


SCHEMA = "dd192-core-v3-controlled-parallel-worker-adjudication-contract-v1"
RESULT_SCHEMA = "dd192-core-v3-controlled-parallel-worker-adjudication-result-v1"
DD191_RESULT = Path(
    "logs/dd191_core_v3_terminal_inventory_control_parallel_first_root_20260813.json"
)
CONTRACT = Path(
    "logs/dd192_core_v3_terminal_inventory_control_parallel_worker_adjudication_contract_20260813.json"
)
RESULT = Path(
    "logs/dd192_core_v3_terminal_inventory_control_parallel_worker_adjudication_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_192_core_v3_terminal_inventory_control_parallel_worker_adjudication_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_192_core_v3_terminal_inventory_control_parallel_worker_adjudication_20260813.md"
)
IMPLEMENTATION = (
    "tools/adjudicate_core_v3_terminal_inventory_control_parallel_first_root.py",
    "tests/test_core_v3_terminal_inventory_control_parallel_adjudication.py",
)


def _failed_names(values: Mapping[str, Any]) -> list[str]:
    return [name for name, passed in values.items() if not passed]


def _actual_worker_sets(source: Mapping[str, Any]) -> list[set[int]]:
    return [
        {int(worker_id) for worker_id in item["worker_ids"]}
        for item in source["provider"]["workers"]
    ]


def _validate_source(source: Mapping[str, Any]) -> None:
    if source.get("pass_gate") is not False or source.get("decision") != (
        "retain_serial_controlled_step_path"
    ):
        raise RuntimeError("DD-192 requires DD-191's preserved formal failure")
    if _failed_names(source["gates"]) != ["worker_participation"]:
        raise RuntimeError("DD-191 failure is not worker-participation only")
    if len(source["worker_ping_ids"]) >= 4:
        raise RuntimeError("DD-191 ping evidence no longer explains the formal failure")
    worker_sets = _actual_worker_sets(source)
    if not worker_sets or any(len(worker_set) != 4 for worker_set in worker_sets):
        raise RuntimeError("DD-191 actual Jacobian tasks did not use four workers")
    if any(worker_set != worker_sets[0] for worker_set in worker_sets[1:]):
        raise RuntimeError("DD-191 actual Jacobian worker membership changed")
    if source["matrix_comparison"]["maximum_absolute_difference"] != 0.0:
        raise RuntimeError("DD-191 Jacobians are not exactly equivalent")
    if source["outcome_comparison"]["maximum_numeric_difference"] != 0.0:
        raise RuntimeError("DD-191 endpoints are not exactly equivalent")
    if source["performance"]["parallel_solve_ratio"] >= 0.9:
        raise RuntimeError("DD-191 parallel speed gate changed")
    if source.get("endpoint_accepted") or source.get("state_advanced"):
        raise RuntimeError("DD-191 endpoint preservation changed")
    if source.get("second_timestep_attempted"):
        raise RuntimeError("DD-191 second-step prohibition changed")


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-192 Controlled Parallel Worker Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Source: immutable DD-191 result only",
            "- DD-191 formal classification: preserved",
            "- Test: actual Jacobian-task worker participation replaces startup-ping participation",
            "- Model/provider/solver/endpoint-regeneration calls: prohibited",
            "- Numerical and performance gates: immutable",
            "",
            "Commit before execution. This adjudication cannot rerun or reclassify DD-191.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["metrics"]
    return "\n".join(
        (
            "# DD-192 Controlled Parallel Worker Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Startup-ping workers observed: `{metrics['startup_ping_worker_count']}`",
            f"- Actual workers per Jacobian: `{metrics['actual_workers_per_jacobian']}`",
            f"- Jacobians audited: `{metrics['jacobian_count']}`",
            f"- Serial/parallel matrix difference: `{metrics['matrix_max_abs_difference']:.6e}`",
            f"- Serial/parallel endpoint difference: `{metrics['endpoint_max_abs_difference']:.6e}`",
            f"- Parallel solve ratio / speedup: `{metrics['parallel_solve_ratio']:.6f}` / `{metrics['solve_speedup']:.3f}x`",
            "- Model/provider/solver/endpoint-regeneration calls: `0 / 0 / 0 / 0`",
            "- DD-191 reclassified or rerun: `False / False`",
            "",
        )
    )


def prepare(
    source_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = dd191.dd190.dd188.dd187.dd186._load(source_path)
    _validate_source(source)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd191.dd190.dd188.dd187.dd186._git(
            "rev-parse", "HEAD"
        ),
        "source_path": str(source_path).replace("\\", "/"),
        "source_sha256": dd191.dd190.dd188.dd187.dd186._sha(ROOT / source_path),
        "source_contract_commit": source["contract_commit"],
        "preserved_source_classification": source["classification"],
        "preserved_source_decision": source["decision"],
        "limits": {
            "worker_count": 4,
            "matrix_absolute_limit": 1.0e-10,
            "endpoint_absolute_limit": 1.0e-12,
            "parallel_solve_ratio_limit": 0.90,
            "wall_clock_sec": 5.0,
        },
        "policy": {
            "startup_ping_is_diagnostic_only": True,
            "actual_jacobian_tasks_are_worker_participation_evidence": True,
            "require_same_four_workers_in_every_jacobian": True,
            "preserve_all_dd191_numerical_and_performance_gates": True,
        },
        "implementation_sha256": {
            path: dd191.dd190.dd188.dd187.dd186._sha(ROOT / path)
            for path in IMPLEMENTATION
        },
        "hard_stops": [
            "DD-191 failure pattern differs from worker-participation only",
            "any actual Jacobian does not use the same four workers",
            "matrix, endpoint, provider, root, or performance evidence changes",
            "any model, provider, solver, or endpoint-regeneration call occurs",
        ],
        "model_calls_attempted": False,
        "provider_calls_attempted": False,
        "solver_calls_attempted": False,
        "endpoint_regeneration_attempted": False,
        "source_reclassification_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = dd191.dd190.dd188.dd187.dd186._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-192 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd191.dd190.dd188.dd187.dd186._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-192 contract payload hash mismatch")
    if dd191.dd190.dd188.dd187.dd186._sha(ROOT / payload["source_path"]) != payload[
        "source_sha256"
    ]:
        raise RuntimeError("DD-192 source changed")
    for path, expected in payload["implementation_sha256"].items():
        if dd191.dd190.dd188.dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-192 implementation changed: {path}")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-192 result exists; rerun is prohibited")
    if not dd191.dd190.dd188.dd187.dd186._git(
        "ls-files", "--error-unmatch", str(contract_path)
    ):
        raise RuntimeError("DD-192 contract is not committed")


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    payload = dd191.dd190.dd188.dd187.dd186._load(contract_path)
    _verify(payload, contract_path, result_path)
    source = dd191.dd190.dd188.dd187.dd186._load(Path(payload["source_path"]))
    _validate_source(source)
    worker_sets = _actual_worker_sets(source)
    limits = payload["limits"]
    metrics = {
        "startup_ping_worker_count": len(source["worker_ping_ids"]),
        "actual_workers_per_jacobian": [len(value) for value in worker_sets],
        "actual_worker_ids": [sorted(value) for value in worker_sets],
        "jacobian_count": len(worker_sets),
        "matrix_max_abs_difference": source["matrix_comparison"][
            "maximum_absolute_difference"
        ],
        "endpoint_max_abs_difference": source["outcome_comparison"][
            "maximum_numeric_difference"
        ],
        "parallel_solve_ratio": source["performance"]["parallel_solve_ratio"],
        "solve_speedup": source["performance"]["solve_speedup"],
    }
    preserved_gates = {
        name: passed
        for name, passed in source["gates"].items()
        if name != "worker_participation"
    }
    gates = {
        "source_failure_preserved": source["pass_gate"] is False,
        "source_failure_is_ping_only": _failed_names(source["gates"])
        == ["worker_participation"],
        "actual_four_worker_participation": all(
            count == limits["worker_count"]
            for count in metrics["actual_workers_per_jacobian"]
        ),
        "stable_worker_membership": all(value == worker_sets[0] for value in worker_sets),
        "matrix_equivalence": metrics["matrix_max_abs_difference"]
        < limits["matrix_absolute_limit"],
        "endpoint_equivalence": metrics["endpoint_max_abs_difference"]
        < limits["endpoint_absolute_limit"],
        "parallel_speed": metrics["parallel_solve_ratio"]
        < limits["parallel_solve_ratio_limit"],
        "all_other_dd191_gates": all(preserved_gates.values()),
        "zero_live_calls": True,
    }
    elapsed = time.perf_counter() - started
    gates["wall_clock"] = elapsed < limits["wall_clock_sec"]
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "controlled_parallel_worker_adjudication_passed"
            if passed
            else "controlled_parallel_worker_adjudication_failed"
        ),
        "decision": (
            "authorize_persistent_parallel_controlled_step_path_under_task_participation_policy"
            if passed
            else "retain_serial_controlled_step_path"
        ),
        "contract_commit": dd191.dd190.dd188.dd187.dd186._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "preserved_dd191_classification": source["classification"],
        "preserved_dd191_decision": source["decision"],
        "metrics": metrics,
        "preserved_dd191_gates": preserved_gates,
        "gates": gates,
        "pass_gate": passed,
        "wall_clock_sec": float(elapsed),
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "endpoint_regeneration_calls": 0,
        "dd191_reclassified": False,
        "dd191_rerun": False,
        "adjudication_executed_once": True,
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
    parser.add_argument("--source", type=Path, default=DD191_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.source, args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
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
