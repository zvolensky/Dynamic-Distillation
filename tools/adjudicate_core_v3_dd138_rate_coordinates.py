#!/usr/bin/env python
"""Prepare or execute the zero-call DD-139 DD-138 rate-coordinate adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.exponential_rate_coordinate_adjudication_v1 import (
    actual_component_rate_coordinates,
)


SCHEMA = "dd139-core-v3-dd138-rate-coordinate-adjudication-contract-v1"
RESULT_SCHEMA = "dd139-core-v3-dd138-rate-coordinate-adjudication-result-v1"
DD138_CONTRACT = Path(
    "logs/dd138_core_v3_captured_failed_root_reconstruction_contract_20260805.json"
)
DD138_RESULT = Path("logs/dd138_core_v3_captured_failed_root_reconstruction_20260805.json")
CONTRACT = Path("logs/dd139_core_v3_dd138_rate_coordinate_adjudication_contract_20260805.json")
RESULT = Path("logs/dd139_core_v3_dd138_rate_coordinate_adjudication_20260805.json")
CONTRACT_DOC = Path(
    "docs/dd_139_core_v3_dd138_rate_coordinate_adjudication_contract_20260805.md"
)
RESULT_DOC = Path("docs/dd_139_core_v3_dd138_rate_coordinate_adjudication_20260805.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/conserved_nu_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/exponential_rate_coordinate_adjudication_v1.py",
    "tests/test_core_v3_exponential_rate_coordinate_adjudication_v1.py",
    "tools/adjudicate_core_v3_dd138_rate_coordinates.py",
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


def prepare() -> dict[str, Any]:
    source = _load(DD138_RESULT)
    contract = _load(DD138_CONTRACT)
    failed = sorted(key for key, value in source["gates"].items() if not value)
    if (
        source["classification"] != "audit_invalid"
        or source["decision"] != "stop_pending_capture_integrity_review"
        or failed != ["solver_evaluation_identity"]
        or any(
            source[key]
            for key in (
                "fresh_jacobian_attempted",
                "retry_attempted",
                "fallback_attempted",
                "clipping_or_projection_attempted",
                "state_advance_attempted",
                "timestep_attempted",
                "dynamic_integration_attempted",
            )
        )
    ):
        raise RuntimeError("DD-139 requires DD-138's coordinate-identity-only failure")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD138_CONTRACT, DD138_RESULT)
        },
        "source_classification": source["classification"],
        "source_decision": source["decision"],
        "source_failed_gates": failed,
        "failure_cases": contract["failure_cases"],
        "component_rate_scale_lbmolph": float(
            _load(
                Path("logs/dd134_core_v3_modified_newton_short_controlled_trajectory_contract_20260805.json")
            )["component_rate_scale_lbmolph"]
        ),
        "mapping_identity_limit": 1.0e-14,
        "noncomponent_identity_limit": 0.0,
        "residual_identity_limit": 0.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-138 source or DD-139 implementation hash changes",
            "any DD-138 gate other than solver_evaluation_identity changes",
            "the nominal-to-actual exponential rate map does not reproduce saved evaluator coordinates below 1e-14",
            "any non-component coordinate or residual identity is nonzero",
            "a property, residual, Jacobian, solve, state advance, timestep, trajectory, retry, fallback, clipping, or projection is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "adjudication_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-139 Frozen DD-138 Rate-Coordinate Adjudication Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Source replacement scope: only `solver_evaluation_identity`",
                "- Mapping: nominal component rate -> exponential positive endpoint -> actual finite-step rate",
                "- Mapping tolerance: `<1e-14`",
                "- Non-component coordinate and residual identity: exact",
                "- Property, residual, Jacobian, solve, state advance, timestep, and trajectory calls: `0`",
                "",
                "DD-138's raw formal classification remains unchanged. Passing accepts its numerical evidence only.",
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
        raise RuntimeError("DD-139 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-139 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-139 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-139 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    source = _load(DD138_RESULT)
    cases = {case["name"]: case for case in payload["failure_cases"]}
    records: dict[str, Any] = {}
    for name, outcome in source["outcomes"].items():
        case = cases[name]
        solver = np.asarray(outcome["final_coordinates"], dtype=float)
        evaluator = np.asarray(
            outcome["final_evaluation_coordinates_at_return"], dtype=float
        )
        component_count = np.asarray(case["previous_inventory_lbmol"]).size
        actual = actual_component_rate_coordinates(
            solver[:component_count],
            case["previous_inventory_lbmol"],
            component_rate_scale_lbmolph=payload["component_rate_scale_lbmolph"],
            step_seconds=float(case["step_seconds"]),
        )
        expected = solver.copy()
        expected[:component_count] = actual
        records[name] = {
            "component_coordinate_count": int(component_count),
            "mapping_max_abs": float(np.max(np.abs(expected - evaluator))),
            "component_mapping_max_abs": float(
                np.max(np.abs(actual - evaluator[:component_count]))
            ),
            "noncomponent_identity_max_abs": float(
                np.max(np.abs(solver[component_count:] - evaluator[component_count:]))
            ),
            "nominal_to_actual_coordinate_max_abs": float(
                np.max(np.abs(solver[:component_count] - actual))
            ),
            "source_residual_identity_max_abs": float(
                outcome["final_residual_vs_evaluation_max_abs"]
            ),
            "source_success": bool(outcome["success"]),
            "source_final_residual_inf_norm": float(
                np.max(np.abs(outcome["final_residual"]))
            ),
            "source_jacobian_rank": int(outcome["jacobian_rank"]),
            "source_jacobian_condition": float(outcome["jacobian_condition"]),
        }
    inherited = {
        key: bool(value)
        for key, value in source["gates"].items()
        if key != "solver_evaluation_identity"
    }
    gates = {
        "source_classification_preserved": bool(
            source["classification"] == payload["source_classification"]
            and source["decision"] == payload["source_decision"]
        ),
        "inherited_gates": all(inherited.values()),
        "exponential_mapping": all(
            item["mapping_max_abs"] < payload["mapping_identity_limit"]
            for item in records.values()
        ),
        "noncomponent_identity": all(
            item["noncomponent_identity_max_abs"]
            <= payload["noncomponent_identity_limit"]
            for item in records.values()
        ),
        "residual_identity": all(
            item["source_residual_identity_max_abs"]
            <= payload["residual_identity_limit"]
            for item in records.values()
        ),
        "zero_model_calls": True,
    }
    passed = all(bool(value) for value in gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "dd138_rate_coordinate_adjudication_passed"
            if passed
            else "dd138_rate_coordinate_adjudication_failed"
        ),
        "decision": (
            "authorize_frozen_jacobian_repeatability_audit_contract"
            if passed
            else "stop_dd138_evidence_path"
        ),
        "source_classification_preserved": source["classification"],
        "source_decision_preserved": source["decision"],
        "records": records,
        "inherited_gates": inherited,
        "gates": {key: bool(value) for key, value in gates.items()},
        "pass": bool(passed),
        "live_property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "adjudication_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# DD-139 DD-138 Rate-Coordinate Adjudication Result",
        "",
        f"- Classification: `{result['classification']}`",
        f"- Decision: `{result['decision']}`",
    ]
    for name, item in records.items():
        lines.extend(
            (
                f"- {name} exponential-map identity: `{item['mapping_max_abs']:.9e}`",
                f"- {name} nominal-to-actual representation difference: `{item['nominal_to_actual_coordinate_max_abs']:.9e}`",
                f"- {name} non-component identity: `{item['noncomponent_identity_max_abs']:.1e}`",
                f"- {name} accepted success/residual evidence: `{item['source_success']}` / `{item['source_final_residual_inf_norm']:.9e}`",
            )
        )
    lines.extend(
        (
            "",
            "DD-138 remains formally failed. This zero-call adjudication accepts its captured numerical evidence by replacing only the overstrict coordinate-identity gate.",
            "",
        )
    )
    (ROOT / RESULT_DOC).write_text("\n".join(lines), encoding="utf-8")
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
