#!/usr/bin/env python
"""Prepare or execute DD-253's zero-call DD-252 accounting adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "dd253-core-v3-vapor-holdup-parallel-first-root-adjudication-contract-v1"
RESULT_SCHEMA = "dd253-core-v3-vapor-holdup-parallel-first-root-adjudication-result-v1"
SOURCE = Path(
    "logs/dd252_core_v3_c3c4_vapor_holdup_parallel_first_root_20260820.json"
)
CONTRACT = Path(
    "logs/dd253_core_v3_vapor_holdup_parallel_first_root_adjudication_contract_20260820.json"
)
RESULT = Path(
    "logs/dd253_core_v3_vapor_holdup_parallel_first_root_adjudication_20260820.json"
)
CONTRACT_DOC = Path(
    "docs/dd_253_core_v3_vapor_holdup_parallel_first_root_adjudication_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_253_core_v3_vapor_holdup_parallel_first_root_adjudication_20260820.md"
)
IMPLEMENTATION = Path(
    "tools/adjudicate_core_v3_vapor_holdup_parallel_first_root.py"
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    source = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    failed = {name for name, passed in source["gates"].items() if not passed}
    if source.get("pass_gate") or failed != {"process_isolation", "provider_calls"}:
        raise RuntimeError("DD-253 requires the exact DD-252 accounting-only failure")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "source": SOURCE.as_posix(),
        "source_sha256": _sha(SOURCE),
        "implementation_sha256": _sha(IMPLEMENTATION),
        "adjudication": {
            "numerical_gates_must_remain_true": [
                "root_success",
                "root_residual",
                "rank",
                "condition",
                "solver_decisions",
                "jacobian_count",
                "jacobian_equivalence",
                "coordinate_equivalence",
                "residual_equivalence",
                "worker_tasks",
                "provider",
                "meaningful_speed",
                "wall_clock",
                "no_state_advance",
            ],
            "worker_participation_rule": "all eight workers appear in every governing Jacobian",
            "logical_work_rule": "serial main calls equal parallel main plus worker calls",
            "required_worker_count": 8,
            "required_work_difference": 0,
            "provider_ownership_must_pass": True,
            "parallel_time_ratio_limit": 0.75,
            "property_calls": 0,
            "rerun": False,
        },
        "hard_stops": [
            "DD-252 numerical, physical, provider, or speed evidence changes",
            "any governing Jacobian omits a worker",
            "serial and parallel total logical work differ",
            "DD-252 is rerun or any property, solve, state, controller, or trajectory call occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-253 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-253 Parallel First-Root Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Source: immutable failed DD-252 result.",
            "- Scope: adjudicate only worker-participation and logical-call accounting semantics.",
            "- Worker rule: all eight workers must appear in every governing Jacobian.",
            "- Work rule: serial main calls must equal parallel main plus worker calls.",
            "- All DD-252 numerical, provider, and performance gates must remain true.",
            "- Property calls, rerun, solve, state advance, controller, or trajectory: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-253 contract checksum or schema failed")
    if _sha(Path(payload["source"])) != payload["source_sha256"]:
        raise RuntimeError("DD-253 source changed")
    if _sha(IMPLEMENTATION) != payload["implementation_sha256"]:
        raise RuntimeError("DD-253 implementation changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-253 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def execute(contract_path: Path, result_path: Path, result_doc_path: Path) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    source = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    rules = payload["adjudication"]
    workers_pass = all(
        len(item["worker_ids"]) == rules["required_worker_count"]
        for item in source["worker_evidence"]
    )
    serial_work = int(source["serial_main_provider_calls"])
    parallel_work = int(
        source["parallel_main_provider_calls"]
        + source["worker_logical_provider_calls"]
    )
    work_difference = parallel_work - serial_work
    gates = {
        "source_failure_is_accounting_only": {
            name for name, passed in source["gates"].items() if not passed
        }
        == {"process_isolation", "provider_calls"},
        "all_original_science_gates": all(
            source["gates"][name]
            for name in rules["numerical_gates_must_remain_true"]
        ),
        "governing_worker_participation": workers_pass,
        "logical_work_parity": work_difference == rules["required_work_difference"],
        "provider_ownership": source["gates"]["provider"],
        "parallel_speed": source["comparison"]["parallel_solve_time_ratio"]
        <= rules["parallel_time_ratio_limit"],
        "zero_call_adjudication": True,
    }
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "parallel_first_root_accounting_adjudication_passed"
            if passed
            else "parallel_first_root_accounting_adjudication_failed"
        ),
        "decision": (
            "authorize_persistent_parallel_vapor_holdup_trajectory_contract"
            if passed
            else "retain_serial_vapor_holdup_solver"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "source_classification": source["classification"],
        "source_failed_gates": [
            name for name, gate in source["gates"].items() if not gate
        ],
        "governing_jacobian_count": len(source["worker_evidence"]),
        "worker_count_each": [
            len(item["worker_ids"]) for item in source["worker_evidence"]
        ],
        "serial_logical_work": serial_work,
        "parallel_logical_work": parallel_work,
        "logical_work_difference": work_difference,
        "parallel_solve_speedup": source["comparison"]["parallel_solve_speedup"],
        "gates": gates,
        "property_calls": 0,
        "rerun_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "controller_attempted": False,
        "trajectory_attempted": False,
        "pass_gate": passed,
    }
    destination = ROOT / result_path
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(report), encoding="utf-8")
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-253 Parallel First-Root Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- DD-252 failed gates: `{payload['source_failed_gates']}`",
            f"- Workers per governing Jacobian: `{payload['worker_count_each']}`",
            f"- Serial/parallel logical work: `{payload['serial_logical_work']} / {payload['parallel_logical_work']}`",
            f"- Parallel solve speedup: `{payload['parallel_solve_speedup']:.3f}x`",
            f"- Gates: `{payload['gates']}`",
            "- Property calls, rerun, solve, state advance, controller, or trajectory: `False`",
            "",
        )
    )


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


def main() -> int:
    args = _parser().parse_args()
    if args.prepare:
        report = prepare(args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": report["schema_id"],
                    "contract_payload_sha256": report["contract_payload_sha256"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
