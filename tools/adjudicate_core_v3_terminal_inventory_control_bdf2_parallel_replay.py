#!/usr/bin/env python
"""Prepare or execute DD-206's zero-call adjudication of DD-205."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "dd206-core-v3-controlled-bdf2-parallel-replay-adjudication-contract-v1"
RESULT_SCHEMA = "dd206-core-v3-controlled-bdf2-parallel-replay-adjudication-result-v1"
DD202_RESULT = Path(
    "logs/dd202_core_v3_seven_volume_terminal_inventory_control_bdf2_modest_20260814.json"
)
DD205_RESULT = Path(
    "logs/dd205_core_v3_terminal_inventory_control_bdf2_parallel_replay_20260814.json"
)
CONTRACT = Path(
    "logs/dd206_core_v3_terminal_inventory_control_bdf2_parallel_replay_adjudication_contract_20260814.json"
)
RESULT = Path(
    "logs/dd206_core_v3_terminal_inventory_control_bdf2_parallel_replay_adjudication_20260814"
)
CONTRACT_DOC = Path(
    "docs/dd_206_core_v3_terminal_inventory_control_bdf2_parallel_replay_adjudication_contract_20260814.md"
)
RESULT_DOC = Path(
    "docs/dd_206_core_v3_terminal_inventory_control_bdf2_parallel_replay_adjudication_20260814.md"
)
IMPLEMENTATION = (
    "tests/test_core_v3_terminal_inventory_control_bdf2_parallel_replay_adjudication.py",
    "tools/adjudicate_core_v3_terminal_inventory_control_bdf2_parallel_replay.py",
)
SCIENCE_KEYS = (
    "coarse",
    "refined",
    "shared_time_refinement",
    "response",
    "cross_grid",
    "response_gates",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return _canonical_hash(payload)


def _science(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: result[key] for key in SCIENCE_KEYS}


def _expected_representation_mismatches(paths: list[str]) -> bool:
    suffixes = {
        "physical_metrics.maximum_absolute_component_index",
        "physical_metrics.maximum_state_relative_index",
        "physical_metrics.maximum_volume_relative_index",
    }
    if len(paths) != 120:
        return False
    observed: dict[int, set[str]] = {index: set() for index in range(40)}
    for path in paths:
        prefix = "shared_time_refinement.comparisons["
        if not path.startswith(prefix) or "]." not in path:
            return False
        index_text, suffix = path[len(prefix) :].split("].", maxsplit=1)
        try:
            index = int(index_text)
        except ValueError:
            return False
        if index not in observed:
            return False
        observed[index].add(suffix)
    return all(values == suffixes for values in observed.values())


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-206 Zero-Call Parallel-Replay Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Sources: immutable DD-202 and DD-205 persisted JSON results",
            "- Comparison: canonical JSON equality for all saved scientific objects",
            "- Expected DD-205 failure: tuple/list representation metadata only",
            f"- Wall limit: `{payload['limits']['wall_clock_sec']} s`",
            "- Model, thermo, residual, solver, timestep, trajectory, and result regeneration calls: prohibited",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-206 Zero-Call Parallel-Replay Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Canonical science hash: `{payload['canonical_science_hash']}`",
            f"- Scientific objects exactly equal: `{payload['scientific_objects_exactly_equal']}`",
            f"- Confirmed representation-only mismatch paths: `{payload['representation_mismatch_count']}`",
            f"- Wall time: `{payload['wall_clock_sec']:.6f} s`",
            "- Model, provider, solver, and trajectory calls: `0`",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    dd202 = _load(DD202_RESULT)
    dd205 = _load(DD205_RESULT)
    if not dd202["pass_gate"] or dd205["pass_gate"]:
        raise RuntimeError("DD-206 requires accepted DD-202 and formally failed DD-205")
    payload = {
        "schema_id": SCHEMA,
        "result_schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-206",
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD202_RESULT, DD205_RESULT)
        },
        "science_keys": list(SCIENCE_KEYS),
        "expected_failed_gate": "saved_result_equivalence",
        "expected_representation_mismatch_count": 120,
        "limits": {"wall_clock_sec": 5.0},
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "DD-205 has any failed campaign gate beyond saved-result equivalence",
            "persisted DD-202 and DD-205 scientific objects are not exactly equal",
            "DD-205 mismatch paths are not exactly the known tuple/list diagnostic-index set",
            "DD-205 numeric comparison is nonzero",
            "the zero-call wall ceiling is exceeded",
            "any model, property, residual, solver, timestep, trajectory, retry, or regeneration occurs",
        ],
        "property_evaluation_attempted": False,
        "model_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "trajectory_attempted": False,
        "retry_authorized": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-206 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-206 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-206 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-206 implementation changed: {path}")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-206 result exists; rerun prohibited")
    _git("ls-files", "--error-unmatch", str(contract_path))


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    started = time.perf_counter()
    dd202 = _load(DD202_RESULT)
    dd205 = _load(DD205_RESULT)
    reference_science = _science(dd202)
    replay_science = _science(dd205)
    reference_hash = _canonical_hash(reference_science)
    replay_hash = _canonical_hash(replay_science)
    comparison = dd205["saved_result_comparison"]
    failed_gates = [key for key, value in dd205["campaign_gates"].items() if not value]
    elapsed = time.perf_counter() - started
    gates = {
        "source_status": dd202["pass_gate"] and not dd205["pass_gate"],
        "sole_failed_gate": failed_gates == [payload["expected_failed_gate"]],
        "numeric_comparison": comparison["maximum_numeric_difference"] == 0.0,
        "representation_paths": _expected_representation_mismatches(
            comparison["metadata_mismatches"]
        ),
        "canonical_hash": reference_hash == replay_hash,
        "exact_scientific_objects": reference_science == replay_science,
        "performance_evidence": dd205["campaign_gates"]["trajectory_speed"]
        and dd205["campaign_gates"]["startup_wall"]
        and dd205["campaign_gates"]["wall_clock"],
        "wall_clock": elapsed < payload["limits"]["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-206",
        "classification": (
            "controlled_bdf2_parallel_replay_adjudication_passed"
            if passed
            else "controlled_bdf2_parallel_replay_adjudication_failed"
        ),
        "decision": (
            "adopt_persistent_parallel_bdf2_trajectory_path"
            if passed
            else "retain_serial_bdf2_trajectory_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "canonical_science_hash": reference_hash,
        "replay_science_hash": replay_hash,
        "scientific_objects_exactly_equal": reference_science == replay_science,
        "representation_mismatch_count": len(comparison["metadata_mismatches"]),
        "dd205_numeric_difference": comparison["maximum_numeric_difference"],
        "dd205_failed_gates": failed_gates,
        "dd205_performance": dd205["performance"],
        "dd205_completed_roots": dd205["completed_roots"],
        "campaign_gates": gates,
        "wall_clock_sec": float(elapsed),
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "trajectory_calls": 0,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "dd205_rerun": False,
        "retry_attempted": False,
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
