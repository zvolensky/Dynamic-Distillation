#!/usr/bin/env python
"""Prepare or execute DD-166, the memoization-API-only DD-165 successor."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_hybrid_jacobian_memoized_short_trajectory as dd165


SCHEMA = "dd166-core-v3-hybrid-jacobian-memoized-short-trajectory-contract-v1"
RESULT_SCHEMA = "dd166-core-v3-hybrid-jacobian-memoized-short-trajectory-result-v1"
DD165_CONTRACT = Path(
    "logs/dd165_core_v3_hybrid_jacobian_memoized_short_trajectory_contract_20260806.json"
)
DD165_ABORT = Path(
    "logs/dd165_core_v3_hybrid_jacobian_memoized_short_trajectory_20260806.json"
)
CONTRACT = Path(
    "logs/dd166_core_v3_hybrid_jacobian_memoized_short_trajectory_contract_20260806.json"
)
RESULT = Path(
    "logs/dd166_core_v3_hybrid_jacobian_memoized_short_trajectory_20260806.json"
)
CONTRACT_DOC = Path(
    "docs/dd_166_core_v3_hybrid_jacobian_memoized_short_trajectory_contract_20260806.md"
)
RESULT_DOC = Path(
    "docs/dd_166_core_v3_hybrid_jacobian_memoized_short_trajectory_20260806.md"
)
IMPLEMENTATION = tuple(
    dict.fromkeys(
        (
            *dd165.IMPLEMENTATION,
            "tests/test_thermo_clapeyron_provider_v1.py",
            "tools/run_core_v3_hybrid_jacobian_memoized_short_trajectory_successor.py",
        )
    )
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
    source = _load(DD165_CONTRACT)
    aborted = _load(DD165_ABORT)
    if (
        aborted["classification"] != "integration_aborted_before_scientific_result"
        or aborted["decision"]
        != "authorize_exact_memoization_api_correction_and_separately_frozen_successor"
        or aborted["root_accepted"]
        or aborted["state_advanced"]
    ):
        raise RuntimeError("DD-166 requires the immutable non-scientific DD-165 abort")
    excluded = {
        "schema_id",
        "preparation_base_commit",
        "sources",
        "implementation_sha256",
        "hard_stops",
        "contract_payload_sha256",
        "live_property_evaluation_attempted",
        "nonlinear_solve_attempted",
        "timestep_attempted",
        "dynamic_integration_attempted",
        "campaign_executed",
    }
    payload = {key: value for key, value in source.items() if key not in excluded}
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": _git("rev-parse", "HEAD"),
            "sources": {
                str(path).replace("\\", "/"): _sha(ROOT / path)
                for path in (DD165_CONTRACT, DD165_ABORT)
            },
            "administrative_correction": {
                "scope": "exact-state imposed-phase Clapeyron fugacity memoization API",
                "enabled_by_default": False,
                "exact_keys_without_rounding": True,
                "scientific_contract_changes": [],
            },
            "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
            "hard_stops": [
                "a DD-165 source or DD-166 implementation hash changes",
                "any DD-165 scientific input, gate, solver, grid, controller, or worker count changes",
                "memoization is enabled outside caller-owned Jacobian epochs",
                "neighboring finite-difference states share an exact memo key",
                "any original DD-165 hard stop occurs",
                "a retry, fallback, clipping, projection, controller change, or grid change occurs",
            ],
            "live_property_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
            "campaign_executed": False,
        }
    )
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-166 Frozen Hybrid-Jacobian Short-Trajectory Successor",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Scientific contract: exactly DD-165",
                "- Sole correction: disabled-by-default exact-key Clapeyron fugacity memoization and statistics",
                "- Solver, grids, controls, worker count, gates, and limits: unchanged",
                "- DD-165 will not be rerun",
                "",
                "Passing authorizes a separately frozen longer derivative-accelerated trajectory. Failure retires the path.",
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
        raise RuntimeError("DD-166 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-166 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-166 implementation changed: {path}")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-166 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    original = (dd165.CONTRACT, dd165.RESULT, dd165.RESULT_DOC, dd165.RESULT_SCHEMA)
    dd165.CONTRACT = CONTRACT
    dd165.RESULT = RESULT
    dd165.RESULT_DOC = RESULT_DOC
    dd165.RESULT_SCHEMA = RESULT_SCHEMA
    try:
        result = dd165.execute()
    finally:
        dd165.CONTRACT, dd165.RESULT, dd165.RESULT_DOC, dd165.RESULT_SCHEMA = original
    result["schema_id"] = RESULT_SCHEMA
    result["dd165_scientific_contract_unchanged"] = True
    result["memoization_api_successor"] = True
    (ROOT / RESULT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    doc = (ROOT / RESULT_DOC).read_text(encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        doc.replace("# DD-165 ", "# DD-166 ", 1), encoding="utf-8"
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
