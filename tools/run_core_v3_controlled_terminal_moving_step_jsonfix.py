#!/usr/bin/env python
"""Prepare or execute the DD-130 JSON-coercion-only DD-129 successor."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_controlled_terminal_moving_step as dd129


SCHEMA = "dd130-core-v3-controlled-terminal-moving-step-jsonfix-contract-v1"
RESULT_SCHEMA = "dd130-core-v3-controlled-terminal-moving-step-jsonfix-result-v1"
DD129_CONTRACT = Path("logs/dd129_core_v3_controlled_terminal_moving_step_contract_20260805.json")
DD129_ABORT = Path("logs/dd129_core_v3_controlled_terminal_moving_step_20260805.json")
CONTRACT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_contract_20260805.json")
RESULT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_20260805.json")
CONTRACT_DOC = Path("docs/dd_130_core_v3_controlled_terminal_moving_step_jsonfix_contract_20260805.md")
RESULT_DOC = Path("docs/dd_130_core_v3_controlled_terminal_moving_step_jsonfix_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/controlled_terminal_implicit_step_v1.py",
    "tests/test_core_v3_controlled_terminal_implicit_step_v1.py",
    "tests/test_core_v3_controlled_terminal_moving_step_jsonfix.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
    "tools/run_core_v3_controlled_terminal_first_step.py",
    "tools/run_core_v3_controlled_terminal_moving_step.py",
    "tools/run_core_v3_controlled_terminal_moving_step_jsonfix.py",
)
GOVERNANCE_FIELDS = {
    "schema_id",
    "preparation_base_commit",
    "sources",
    "implementation_sha256",
    "hard_stops",
    "live_property_evaluation_attempted",
    "nonlinear_solve_attempted",
    "timestep_attempted",
    "dynamic_integration_attempted",
    "campaign_executed",
    "contract_payload_sha256",
}


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


def scientific_contract_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in payload.items()
        if key not in GOVERNANCE_FIELDS
    }


def native_json_booleans(value: Any) -> Any:
    """Recursively convert only NumPy booleans to native JSON booleans."""
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, dict):
        return {key: native_json_booleans(item) for key, item in value.items()}
    if isinstance(value, list):
        return [native_json_booleans(item) for item in value]
    if isinstance(value, tuple):
        return tuple(native_json_booleans(item) for item in value)
    return value


class _BooleanSafeJSON:
    @staticmethod
    def loads(*args: Any, **kwargs: Any) -> Any:
        return json.loads(*args, **kwargs)

    @staticmethod
    def dumps(value: Any, *args: Any, **kwargs: Any) -> str:
        return json.dumps(native_json_booleans(value), *args, **kwargs)


def prepare() -> dict[str, Any]:
    source = _load(DD129_CONTRACT)
    abort = _load(DD129_ABORT)
    if (
        abort["classification"] != "dd129_aborted_during_result_serialization"
        or abort["scientific_gate_result"] is not None
        or abort["retry_attempted"]
    ):
        raise RuntimeError("DD-130 requires the immutable unclassified DD-129 abort")
    payload = copy.deepcopy(source)
    payload["schema_id"] = SCHEMA
    payload["preparation_base_commit"] = _git("rev-parse", "HEAD")
    payload["sources"] = {
        str(path).replace("\\", "/"): _sha(ROOT / path)
        for path in (DD129_CONTRACT, DD129_ABORT)
    }
    payload["implementation_sha256"] = {
        path: _sha(ROOT / path) for path in IMPLEMENTATION
    }
    payload["hard_stops"] = [
        "the DD-129 contract or abort hash changes",
        "the DD-130 scientific projection differs from DD-129",
        "any change beyond native JSON boolean coercion or successor reporting occurs",
        *source["hard_stops"],
    ]
    payload["live_property_evaluation_attempted"] = False
    payload["nonlinear_solve_attempted"] = False
    payload["timestep_attempted"] = False
    payload["dynamic_integration_attempted"] = False
    payload["campaign_executed"] = False
    payload.pop("contract_payload_sha256", None)
    if scientific_contract_projection(payload) != scientific_contract_projection(source):
        raise RuntimeError("DD-130 changed the frozen DD-129 scientific contract")
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join((
            "# DD-130 Frozen Controlled-Terminal Moving-Step JSON Fix", "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Scientific contract relative to DD-129: `identical`",
            "- Runtime change: recursively coerce only `numpy.bool_` values to native `bool` before JSON serialization",
            "- Disturbance, grids, solver, gates, and limits: `unchanged`",
            "- Retry or trajectory before commit: `False`", "",
            "Execution is permitted once only after this exact contract is committed.", "",
        )),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-130 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-130 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-130 implementation changed: {path}")
    if scientific_contract_projection(payload) != scientific_contract_projection(
        _load(DD129_CONTRACT)
    ):
        raise RuntimeError("DD-130 scientific contract differs from DD-129")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-130 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    original = {
        "CONTRACT": dd129.CONTRACT,
        "RESULT": dd129.RESULT,
        "RESULT_DOC": dd129.RESULT_DOC,
        "RESULT_SCHEMA": dd129.RESULT_SCHEMA,
        "json": dd129.json,
    }
    dd129.CONTRACT = CONTRACT
    dd129.RESULT = RESULT
    dd129.RESULT_DOC = RESULT_DOC
    dd129.RESULT_SCHEMA = RESULT_SCHEMA
    dd129.json = _BooleanSafeJSON
    try:
        dd129.execute()
    finally:
        dd129.CONTRACT = original["CONTRACT"]
        dd129.RESULT = original["RESULT"]
        dd129.RESULT_DOC = original["RESULT_DOC"]
        dd129.RESULT_SCHEMA = original["RESULT_SCHEMA"]
        dd129.json = original["json"]
    result = _load(RESULT)
    result["classification"] = "dd130_passed" if result["pass"] else "dd130_failed"
    result["source_campaign"] = "DD-129 scientific contract, unchanged"
    result["json_boolean_coercion_applied"] = True
    result["retry_attempted_after_dd130"] = False
    json.dumps(result)
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join((
            "# DD-130 Core V3 Controlled-Terminal Moving-Step Result", "",
            f"- Classification: `{result['classification']}`",
            f"- Decision: `{result['decision']}`",
            f"- Distillate change: `{result['movement_signal']['distillate_relative_change']:.6e}` relative",
            f"- Bottoms change: `{result['movement_signal']['bottoms_relative_change']:.6e}` relative",
            f"- Terminal accumulation: `{result['movement_signal']['terminal_accumulation_lbmolph']}` lbmol/h",
            f"- Worst refinement metric: `{max(result['refinement'].values()):.6e}`",
            f"- Jacobian ranks: `{[item['rank'] for item in result['jacobians']]}`",
            f"- Worst condition: `{max(item['condition'] for item in result['jacobians']):.6e}`",
            f"- DWSIM calls: `{result['provider_provenance']['total_calls']}`",
            f"- Wall clock: `{result['wall_clock_sec']:.3f} s`", "",
            "DD-130 changed only JSON boolean coercion relative to DD-129. No retry, tuning, or trajectory was attempted.", "",
        )),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    output = prepare() if args.mode == "prepare" else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.mode == "prepare" or output["pass"] else 2)


if __name__ == "__main__":
    main()
