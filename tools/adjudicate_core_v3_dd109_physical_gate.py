#!/usr/bin/env python
"""Prepare or execute the static DD-110 DD-109 gate adjudication."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.dd109_gate_adjudication_v1 import (
    REPLACEABLE_GATES,
    adjudicate_dd109_physical_gates,
)


SCHEMA = "dd110-core-v3-dd109-physical-gate-adjudication-contract-v1"
RESULT_SCHEMA = "dd110-core-v3-dd109-physical-gate-adjudication-result-v1"
DD109_CONTRACT = Path("logs/dd109_core_v3_conserved_nu_pressure_numerical_contract_20260726.json")
DD109_RESULT = Path("logs/dd109_core_v3_conserved_nu_pressure_numerical_20260726.json")
CONTRACT = Path("logs/dd110_core_v3_dd109_physical_gate_adjudication_contract_20260726.json")
RESULT = Path("logs/dd110_core_v3_dd109_physical_gate_adjudication_20260726.json")
CONTRACT_DOC = Path("docs/dd_110_core_v3_dd109_physical_gate_adjudication_contract_20260726.md")
RESULT_DOC = Path("docs/dd_110_core_v3_dd109_physical_gate_adjudication_20260726.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dd109_gate_adjudication_v1.py",
    "tests/test_core_v3_dd109_gate_adjudication_v1.py",
    "tools/adjudicate_core_v3_dd109_physical_gate.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def prepare() -> dict[str, Any]:
    dd109_contract = _load(DD109_CONTRACT)
    dd109_result = _load(DD109_RESULT)
    audit = adjudicate_dd109_physical_gates(
        dd109_result, dd109_contract["pressure_link_geometry"]
    )
    if set(audit.source_failed_gates) != set(REPLACEABLE_GATES):
        raise RuntimeError("DD-110 source failure is outside the authorized scope")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "governance_exception": {
            "authorized_by_user": True,
            "authorization_date": "2026-07-26",
            "reason": (
                "DD-109 completed all numerical work but its reporting gate "
                "applied Francis tray-height requirements to non-Francis terminals"
            ),
            "scope": (
                "statically re-adjudicate only the two failed physical gates; "
                "preserve every numerical value and all other gates"
            ),
        },
        "source_dd109_contract": str(DD109_CONTRACT).replace("\\", "/"),
        "source_dd109_contract_sha256": _sha(ROOT / DD109_CONTRACT),
        "source_dd109_result": str(DD109_RESULT).replace("\\", "/"),
        "source_dd109_result_sha256": _sha(ROOT / DD109_RESULT),
        "source_dd109_contract_commit": dd109_result["contract_commit"],
        "source_dd109_contract_payload_sha256": dd109_result["contract_payload_sha256"],
        "source_failed_gates": list(audit.source_failed_gates),
        "replaceable_gates": sorted(REPLACEABLE_GATES),
        "pressure_link_geometry": dd109_contract["pressure_link_geometry"],
        "applicable_volume_indices": list(audit.applicable_volume_indices),
        "terminal_sentinel_indices": list(audit.terminal_sentinel_indices),
        "liquid_head_link_mask": list(audit.liquid_head_link_mask),
        "preserved_gates": {
            key: value
            for key, value in dd109_result["gates"].items()
            if key not in REPLACEABLE_GATES
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "the DD-109 result or contract hash changes",
            "any failed DD-109 gate lies outside the two authorized physical gates",
            "any applicable Francis tray height is nonfinite or nonpositive",
            "either non-Francis terminal lacks its intentional NaN height sentinel",
            "the dry-only link carries liquid head or a liquid-head link lacks positive head",
            "any inherited DD-109 gate is changed or false",
            "a property call, residual evaluation, Jacobian, solve, initializer, or timestep is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "residual_or_jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "dynamic_integration_attempted": False,
        "adjudication_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-110 Frozen DD-109 Physical-Gate Adjudication Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                f"- DD-109 result SHA-256: `{payload['source_dd109_result_sha256']}`",
                "- Replaceable gates: `finite_physical_state`, `positive_pressure_and_geometry_terms`",
                "- Live property calls: `False`",
                "- Residual, Jacobian, solve, initializer, or timestep: `False`",
                "",
                "Execution is a one-time static adjudication after commit. All numerical evidence and every other DD-109 gate remain immutable.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-110 contract checksum mismatch")
    if _sha(ROOT / DD109_CONTRACT) != payload["source_dd109_contract_sha256"]:
        raise RuntimeError("DD-109 contract changed")
    if _sha(ROOT / DD109_RESULT) != payload["source_dd109_result_sha256"]:
        raise RuntimeError("DD-109 result changed")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-110 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-110 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    dd109_result = _load(DD109_RESULT)
    audit = adjudicate_dd109_physical_gates(
        dd109_result, payload["pressure_link_geometry"]
    )
    preserved = {
        key: value
        for key, value in audit.final_gates.items()
        if key not in REPLACEABLE_GATES and key != "terminal_height_sentinels"
    }
    preserved_unchanged = preserved == payload["preserved_gates"]
    passed = audit.pass_gate and preserved_unchanged
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "source_dd109_result_sha256": payload["source_dd109_result_sha256"],
        "classification": "dd110_passed" if passed else "dd110_failed",
        "decision": (
            "authorize_frozen_conserved_nu_initializer_contract"
            if passed
            else "stop_conserved_nu_pressure_path"
        ),
        "adjudication": asdict(audit),
        "preserved_gates_unchanged": preserved_unchanged,
        "source_numerical_evidence_changed": False,
        "live_property_calls": 0,
        "residual_evaluations": 0,
        "jacobian_evaluations": 0,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "dynamic_integration_attempted": False,
        "pass": bool(passed),
        "adjudication_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-110 DD-109 Physical-Gate Adjudication Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- DD-109 evidence changed: `{result['source_numerical_evidence_changed']}`",
                f"- Live property calls: `{result['live_property_calls']}`",
                f"- Residual/Jacobian evaluations: `0/0`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
