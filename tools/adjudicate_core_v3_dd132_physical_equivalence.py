#!/usr/bin/env python
"""Prepare or execute the static DD-133 DD-132 physical adjudication."""

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

from dynamic_distillation.core_v3.dd132_physical_equivalence_adjudication_v1 import (
    DD130_REPLACEABLE_GATES,
    DD132_REPLACEABLE_GATES,
    adjudicate_dd132_physical_equivalence,
)


SCHEMA = "dd133-core-v3-dd132-physical-equivalence-adjudication-contract-v1"
RESULT_SCHEMA = "dd133-core-v3-dd132-physical-equivalence-adjudication-result-v1"
DD130_CONTRACT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_contract_20260805.json")
DD130_RESULT = Path("logs/dd130_core_v3_controlled_terminal_moving_step_jsonfix_20260805.json")
DD132_CONTRACT = Path("logs/dd132_core_v3_modified_newton_live_efficiency_contract_20260805.json")
DD132_RESULT = Path("logs/dd132_core_v3_modified_newton_live_efficiency_20260805.json")
CONTRACT = Path("logs/dd133_core_v3_dd132_physical_equivalence_adjudication_contract_20260805.json")
RESULT = Path("logs/dd133_core_v3_dd132_physical_equivalence_adjudication_20260805.json")
CONTRACT_DOC = Path("docs/dd_133_core_v3_dd132_physical_equivalence_adjudication_contract_20260805.md")
RESULT_DOC = Path("docs/dd_133_core_v3_dd132_physical_equivalence_adjudication_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dd132_physical_equivalence_adjudication_v1.py",
    "tests/test_core_v3_dd132_physical_equivalence_adjudication_v1.py",
    "tools/adjudicate_core_v3_dd132_physical_equivalence.py",
)
LIMITS = {
    "inventory_relative_difference": 2.0e-7,
    "liquid_holdup_relative_difference": 2.0e-7,
    "liquid_composition_abs_difference": 2.0e-7,
    "component_rate_scaled_difference": 2.0e-6,
    "top_internal_energy_relative_difference": 2.0e-7,
    "lower_internal_energy_relative_difference": 2.0e-7,
    "lower_energy_rate_scaled_difference": 2.0e-7,
    "controller_memory_abs_difference": 2.0e-7,
    "controller_rate_abs_difference_per_sec": 2.0e-7,
    "level_fraction_abs_difference": 2.0e-7,
    "temperature_abs_difference_F": 5.0e-5,
    "vapor_composition_abs_difference": 2.0e-7,
    "liquid_flow_relative_difference": 2.0e-7,
    "vapor_flow_relative_difference": 2.0e-7,
    "bubble_composition_abs_difference": 2.0e-7,
    "pressure_abs_difference_psia": 2.0e-6,
    "distillate_relative_difference": 1.0e-7,
    "bottoms_relative_difference": 1.0e-7,
    "condenser_duty_scaled_difference": 2.0e-7,
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


def _audit(
    dd130_result: Mapping[str, Any],
    dd132_result: Mapping[str, Any],
    dd130_contract: Mapping[str, Any],
):
    return adjudicate_dd132_physical_equivalence(
        dd130_result, dd132_result, dd130_contract, limits=LIMITS
    )


def prepare() -> dict[str, Any]:
    dd130_contract = _load(DD130_CONTRACT)
    dd130_result = _load(DD130_RESULT)
    dd132_result = _load(DD132_RESULT)
    audit = _audit(dd130_result, dd132_result, dd130_contract)
    if set(audit.dd130_failed_gates) != set(DD130_REPLACEABLE_GATES):
        raise RuntimeError("DD-133 DD-130 source failure is outside scope")
    if set(audit.dd132_failed_gates) != set(DD132_REPLACEABLE_GATES):
        raise RuntimeError("DD-133 DD-132 source failure is outside scope")
    sources = (DD130_CONTRACT, DD130_RESULT, DD132_CONTRACT, DD132_RESULT)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "governance_exception": {
            "authorized_by_user": True,
            "authorization_date": "2026-08-05",
            "reason": (
                "DD-132 passed every scientific and physical gate but narrowly "
                "missed one transformed-coordinate reproduction limit"
            ),
            "scope": (
                "statically compare the saved DD-130 and DD-132 physical endpoints; "
                "preserve both classifications and all source evidence"
            ),
        },
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path) for path in sources
        },
        "dd130_failed_gates": list(audit.dd130_failed_gates),
        "dd132_failed_gates": list(audit.dd132_failed_gates),
        "dd130_replaceable_gates": sorted(DD130_REPLACEABLE_GATES),
        "dd132_replaceable_gates": sorted(DD132_REPLACEABLE_GATES),
        "preserved_dd130_gates": audit.preserved_dd130_gates,
        "preserved_dd132_gates": audit.preserved_dd132_gates,
        "physical_equivalence_limits": LIMITS,
        "comparison_outcomes": ["coarse", "half1", "half2"],
        "comparison_basis": [
            "component inventories, total liquid holdups, and liquid compositions",
            "component rates, stored energies, and lower-volume energy rates",
            "controller memories, controller rates, levels, and product flows",
            "temperatures, vapor and bubble compositions, liquid and vapor flows",
            "ordered pressure profile and condenser duty",
        ],
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-130 or DD-132 source artifact hash changes",
            "a failed source gate lies outside calls or endpoint_reproduction respectively",
            "an inherited source gate is changed or false",
            "a physical-equivalence metric reaches or exceeds its frozen limit",
            "a decoded endpoint is nonphysical or a stored product disagrees with its coordinate",
            "a property call, residual, Jacobian, solve, initializer, timestep, or dynamics is attempted",
            "a source classification or numerical result is modified",
        ],
        "live_property_evaluation_attempted": False,
        "residual_or_jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "adjudication_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-133 Frozen DD-132 Physical-Equivalence Adjudication Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- DD-130 replaceable gate: `calls`",
                "- DD-132 replaceable gate: `endpoint_reproduction`",
                "- Outcomes: `coarse`, `half1`, and `half2`",
                "- Vapor-flow relative-difference limit: `<2e-7`",
                "- Live property calls: `0`",
                "- Residual, Jacobian, solve, initializer, timestep, or dynamics: `0`",
                "",
                "Execution is one static adjudication after commit. DD-130 and DD-132 remain formally failed and their evidence remains immutable.",
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
        raise RuntimeError("DD-133 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-133 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-133 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-133 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    dd130_contract = _load(DD130_CONTRACT)
    dd130_result = _load(DD130_RESULT)
    dd132_result = _load(DD132_RESULT)
    audit = adjudicate_dd132_physical_equivalence(
        dd130_result,
        dd132_result,
        dd130_contract,
        limits=payload["physical_equivalence_limits"],
    )
    preserved_unchanged = bool(
        audit.preserved_dd130_gates == payload["preserved_dd130_gates"]
        and audit.preserved_dd132_gates == payload["preserved_dd132_gates"]
    )
    passed = bool(audit.pass_gate and preserved_unchanged)
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "source_sha256": payload["sources"],
        "classification": "dd133_passed" if passed else "dd133_failed",
        "decision": (
            "authorize_frozen_modified_newton_short_controlled_trajectory_contract"
            if passed
            else "stop_modified_newton_controlled_handoff"
        ),
        "adjudication": asdict(audit),
        "preserved_gates_unchanged": preserved_unchanged,
        "source_numerical_evidence_changed": False,
        "live_property_calls": 0,
        "residual_evaluations": 0,
        "jacobian_evaluations": 0,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass": passed,
        "adjudication_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    worst_name, worst_metric, worst_value = max(
        (
            (name, metric, value)
            for name, values in audit.metrics.items()
            for metric, value in values.items()
        ),
        key=lambda item: item[2] / audit.limits[item[1]],
    )
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-133 DD-132 Physical-Equivalence Adjudication Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Tightest metric: `{worst_name}.{worst_metric}` = `{worst_value:.9e}`",
                f"- Tightest limit: `<{audit.limits[worst_metric]:.9e}`",
                f"- Decoded states physical: `{audit.decoded_states_physical}`",
                f"- Stored products match coordinates: `{audit.stored_products_match_coordinates}`",
                "- Live property calls: `0`",
                "- Residual/Jacobian evaluations: `0/0`",
                "- Timesteps or dynamics: `0`",
                "",
                "DD-130 and DD-132 retain their original formal classifications. This adjudication only determines whether their saved physical endpoints are equivalent under the frozen DD-133 limits.",
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
