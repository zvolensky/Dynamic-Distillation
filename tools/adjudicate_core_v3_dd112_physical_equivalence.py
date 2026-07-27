#!/usr/bin/env python
"""Prepare or execute the static DD-113 DD-112 endpoint adjudication."""

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

from dynamic_distillation.core_v3.dd112_physical_equivalence_adjudication_v1 import (
    REPLACEABLE_GATES,
    adjudicate_dd112_physical_equivalence,
)


SCHEMA = "dd113-core-v3-dd112-physical-equivalence-adjudication-contract-v1"
RESULT_SCHEMA = "dd113-core-v3-dd112-physical-equivalence-adjudication-result-v1"
DD112_CONTRACT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json")
DD112_RESULT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json")
CONTRACT = Path("logs/dd113_core_v3_dd112_physical_equivalence_adjudication_contract_20260727.json")
RESULT = Path("logs/dd113_core_v3_dd112_physical_equivalence_adjudication_20260727.json")
CONTRACT_DOC = Path("docs/dd_113_core_v3_dd112_physical_equivalence_adjudication_contract_20260727.md")
RESULT_DOC = Path("docs/dd_113_core_v3_dd112_physical_equivalence_adjudication_20260727.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dd112_physical_equivalence_adjudication_v1.py",
    "tests/test_core_v3_dd112_physical_equivalence_adjudication_v1.py",
    "tools/adjudicate_core_v3_dd112_physical_equivalence.py",
)
LIMITS = {
    "objective_abs_difference": 1.0e-9,
    "inventory_scaled_difference": 1.0e-5,
    "liquid_composition_abs_difference": 1.0e-6,
    "lower_internal_energy_scaled_difference": 1.0e-6,
    "component_rate_scaled_difference": 1.0e-6,
    "internal_energy_rate_scaled_difference": 1.0e-6,
    "pressure_scaled_difference": 1.0e-6,
    "temperature_abs_difference_F": 1.0e-3,
    "vapor_composition_abs_difference": 1.0e-6,
    "bubble_composition_abs_difference": 1.0e-6,
    "liquid_flow_scaled_difference": 1.0e-6,
    "vapor_flow_scaled_difference": 1.0e-6,
    "distillate_scaled_difference": 1.0e-6,
    "bottoms_scaled_difference": 1.0e-6,
    "condenser_duty_scaled_difference": 1.0e-6,
}
SCALES = {
    "material_rate_scale_lbmolph": 12584.8,
    "energy_rate_scale_BTUph": 55003568.3093669,
    "pressure_scale_psia": 10.0,
}


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


def _audit(result: Mapping[str, Any], contract: Mapping[str, Any]):
    return adjudicate_dd112_physical_equivalence(
        result, contract, limits=LIMITS, **SCALES
    )


def prepare() -> dict[str, Any]:
    dd112_contract = _load(DD112_CONTRACT)
    dd112_result = _load(DD112_RESULT)
    audit = _audit(dd112_result, dd112_contract)
    if set(audit.source_failed_gates) != set(REPLACEABLE_GATES):
        raise RuntimeError("DD-113 source failure is outside the authorized scope")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "governance_exception": {
            "authorized_by_user": True,
            "authorization_date": "2026-07-27",
            "reason": (
                "DD-112 passed every equation, physical, conservation, provider, "
                "and efficiency gate but missed a transformed-coordinate comparison"
            ),
            "scope": (
                "statically adjudicate physical endpoint equivalence only; preserve "
                "the DD-112 classification, all numerical evidence, and every other gate"
            ),
        },
        "source_dd112_contract": str(DD112_CONTRACT).replace("\\", "/"),
        "source_dd112_contract_sha256": _sha(ROOT / DD112_CONTRACT),
        "source_dd112_result": str(DD112_RESULT).replace("\\", "/"),
        "source_dd112_result_sha256": _sha(ROOT / DD112_RESULT),
        "source_dd112_contract_commit": dd112_result["contract_commit"],
        "source_dd112_contract_payload_sha256": dd112_result["contract_payload_sha256"],
        "source_failed_gates": list(audit.source_failed_gates),
        "replaceable_gates": sorted(REPLACEABLE_GATES),
        "preserved_gates": audit.preserved_gates,
        "physical_equivalence_limits": LIMITS,
        "physical_comparison_scales": SCALES,
        "canonical_selection_rule": "lowest final objective, then lexical start name",
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "the DD-112 result or contract hash changes",
            "any failed DD-112 gate lies outside common_solution",
            "any inherited DD-112 gate is changed or false",
            "any frozen physical-equivalence metric reaches or exceeds its limit",
            "either endpoint has a nonphysical reconstructed composition",
            "a property call, residual evaluation, Jacobian, solve, initializer, timestep, or dynamics is attempted",
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
                "# DD-113 Frozen DD-112 Physical-Equivalence Adjudication Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                f"- DD-112 result SHA-256: `{payload['source_dd112_result_sha256']}`",
                "- Replaceable gate: `common_solution`",
                "- Comparison basis: physical inventories, compositions, energy, rates, pressure, temperature, flows, products, and condenser duty",
                "- Canonical selection: lowest final objective, then lexical start name",
                "- Live property calls: `False`",
                "- Residual, Jacobian, solve, initializer, timestep, or dynamics: `False`",
                "",
                "Execution is a one-time static adjudication after commit. DD-112 remains formally failed; its numerical evidence and every gate other than the interpretation of endpoint equivalence remain immutable.",
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
        raise RuntimeError("DD-113 contract checksum mismatch")
    if _sha(ROOT / DD112_CONTRACT) != payload["source_dd112_contract_sha256"]:
        raise RuntimeError("DD-112 contract changed")
    if _sha(ROOT / DD112_RESULT) != payload["source_dd112_result_sha256"]:
        raise RuntimeError("DD-112 result changed")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-113 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-113 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    dd112_contract = _load(DD112_CONTRACT)
    dd112_result = _load(DD112_RESULT)
    audit = adjudicate_dd112_physical_equivalence(
        dd112_result,
        dd112_contract,
        limits=payload["physical_equivalence_limits"],
        **payload["physical_comparison_scales"],
    )
    preserved_unchanged = audit.preserved_gates == payload["preserved_gates"]
    passed = audit.pass_gate and preserved_unchanged
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "source_dd112_result_sha256": payload["source_dd112_result_sha256"],
        "classification": "dd113_passed" if passed else "dd113_failed",
        "decision": (
            "authorize_frozen_zero_time_initializer_audit"
            if passed
            else "stop_conserved_nu_pressure_initializer_path"
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
                "# DD-113 DD-112 Physical-Equivalence Adjudication Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Canonical endpoint: `{audit.canonical_start}`",
                f"- DD-112 evidence changed: `{result['source_numerical_evidence_changed']}`",
                "- Live property calls: `0`",
                "- Residual/Jacobian evaluations: `0/0`",
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
