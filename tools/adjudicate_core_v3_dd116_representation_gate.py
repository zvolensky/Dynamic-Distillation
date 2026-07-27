#!/usr/bin/env python
"""Prepare or execute the static DD-117 DD-116 gate adjudication."""

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

from dynamic_distillation.core_v3.dd116_gate_adjudication_v1 import (
    REPLACEABLE_GATES,
    adjudicate_dd116_representation_gate,
)


SCHEMA = "dd117-core-v3-dd116-representation-gate-adjudication-contract-v1"
RESULT_SCHEMA = "dd117-core-v3-dd116-representation-gate-adjudication-result-v1"
DD116_CONTRACT = Path("logs/dd116_core_v3_initializer_handoff_term_audit_contract_20260727.json")
DD116_RESULT = Path("logs/dd116_core_v3_initializer_handoff_term_audit_20260727.json")
DD115_CONTRACT = Path("logs/dd115_core_v3_initializer_first_step_refinement_contract_20260727.json")
DD115_RESULT = Path("logs/dd115_core_v3_initializer_first_step_refinement_20260727.json")
CONTRACT = Path("logs/dd117_core_v3_dd116_representation_gate_adjudication_contract_20260727.json")
RESULT = Path("logs/dd117_core_v3_dd116_representation_gate_adjudication_20260727.json")
CONTRACT_DOC = Path("docs/dd_117_core_v3_dd116_representation_gate_adjudication_contract_20260727.md")
RESULT_DOC = Path("docs/dd_117_core_v3_dd116_representation_gate_adjudication_20260727.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dd116_gate_adjudication_v1.py",
    "tests/test_core_v3_dd116_gate_adjudication_v1.py",
    "tools/adjudicate_core_v3_dd116_representation_gate.py",
)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def prepare() -> dict[str, Any]:
    evidence = (_load(DD116_CONTRACT), _load(DD116_RESULT), _load(DD115_CONTRACT), _load(DD115_RESULT))
    audit = adjudicate_dd116_representation_gate(*evidence)
    if set(audit.source_failed_gates) != set(REPLACEABLE_GATES):
        raise RuntimeError("DD-117 source failure is outside the authorized scope")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "governance_exception": {
            "authorized_by_user": True,
            "authorization_date": "2026-07-27",
            "reason": "DD-116 grouped a nominal exponential-step coordinate with physical-field reproduction",
            "scope": "statically replace only physical_reproduction while preserving all numerical evidence and other gates",
        },
        "sources": {str(path).replace("\\", "/"): _sha(ROOT / path) for path in (DD116_CONTRACT, DD116_RESULT, DD115_CONTRACT, DD115_RESULT)},
        "source_failed_gates": list(audit.source_failed_gates),
        "replaceable_gates": sorted(REPLACEABLE_GATES),
        "preserved_gates": {key: value for key, value in evidence[1]["gates"].items() if key not in REPLACEABLE_GATES},
        "limits": {
            "physical": evidence[0]["physical_reproduction_limit"],
            "pressure_psia": evidence[0]["pressure_reproduction_limit_psia"],
            "temperature_F": evidence[0]["temperature_reproduction_limit_F"],
            "transform_reconstruction": 1.0e-12,
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "any DD-115 or DD-116 source hash changes",
            "any DD-116 failed gate lies outside physical_reproduction",
            "any actual physical reproduction metric fails its frozen limit",
            "the exponential endpoint, effective rate, or reported coordinate mismatch cannot be reconstructed",
            "any inherited DD-116 gate is changed or false",
            "a property call, residual, Jacobian, solve, initializer, timestep, controller, or trajectory is attempted",
        ],
        "live_property_calls": 0,
        "residual_evaluations": 0,
        "jacobian_evaluations": 0,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "adjudication_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text("\n".join((
        "# DD-117 Frozen DD-116 Representation-Gate Adjudication Contract",
        "",
        f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
        "- Replaceable gate: `physical_reproduction` only",
        "- Live property/residual/Jacobian calls: `0/0/0`",
        "- Solve, initializer, timestep, controller, or trajectory: `False`",
        "",
        "This one-time static adjudication proves or rejects the nominal-versus-effective exponential-step rate representation while preserving every physical value and all other DD-116 gates.",
        "",
    )), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any]) -> None:
    copy = dict(payload)
    expected = copy.pop("contract_payload_sha256")
    if _hash(copy) != expected:
        raise RuntimeError("DD-117 contract checksum mismatch")
    for path, digest in payload["sources"].items():
        if _sha(ROOT / path) != digest:
            raise RuntimeError(f"DD-117 source changed: {path}")
    for path, digest in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != digest:
            raise RuntimeError(f"DD-117 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-117 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    audit = adjudicate_dd116_representation_gate(_load(DD116_CONTRACT), _load(DD116_RESULT), _load(DD115_CONTRACT), _load(DD115_RESULT))
    preserved = {key: value for key, value in audit.final_gates.items() if key not in REPLACEABLE_GATES and key != "nominal_effective_rate_representation_proven"}
    preserved_unchanged = preserved == payload["preserved_gates"]
    passed = audit.pass_gate and preserved_unchanged
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd117_passed" if passed else "dd117_failed",
        "decision": "authorize_structural_zero_rate_feasibility_audit" if passed else "stop_core_v3_initializer_work",
        "adjudication": asdict(audit),
        "preserved_gates_unchanged": bool(preserved_unchanged),
        "source_numerical_evidence_changed": False,
        "live_property_calls": 0,
        "residual_evaluations": 0,
        "jacobian_evaluations": 0,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass": bool(passed),
        "adjudication_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text("\n".join((
        "# DD-117 DD-116 Representation-Gate Adjudication Result",
        "",
        f"- Classification: `{result['classification']}`",
        f"- Decision: `{result['decision']}`",
        f"- Endpoint inventory reconstruction: `{audit.endpoint_inventory_reconstruction_maximum:.6e}`",
        f"- Effective-rate reconstruction: `{audit.effective_rate_reconstruction_maximum:.6e}`",
        f"- Coordinate-mismatch reconstruction: `{audit.coordinate_mismatch_reconstruction_maximum:.6e}`",
        "- Property/residual/Jacobian calls: `0/0/0`",
        "",
    )), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
