#!/usr/bin/env python
"""Prepare the DD-094 reporting-only recovery contract without execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ID = "dd094-core-v3-steady-root-recovery-contract-v1"
SOURCE_CONTRACT = Path(
    "logs/dd093_core_v3_steady_root_contract_20260719.json"
)
IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/__init__.py",
    "src/dynamic_distillation/core_v3/provider_governed_registry_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_steady_root_v1.py",
    "tests/test_core_v3_provider_governed_registry_v1.py",
    "tests/test_core_v3_provider_call_audit_v1.py",
    "tests/test_core_v3_provider_governed_residual_v1.py",
    "tests/test_core_v3_provider_governed_steady_root_v1.py",
    "tools/run_core_v3_provider_governed_steady_root.py",
    "tools/prepare_core_v3_dd094_recovery_contract.py",
    "docs/dd_094_core_v3_reporting_recovery_contract_20260725.md",
)
MATHEMATICAL_KEYS = (
    "dd092_contract_payload_sha256",
    "workbook",
    "workbook_sha256",
    "property_package",
    "source_mapping",
    "operating_spec",
    "reference",
    "independent_pr_parameters",
    "coordinate_names",
    "residual_names",
    "fixed_residual_scales",
    "physical_comparison_scales",
    "lower_bounds",
    "upper_bounds",
    "starts",
    "start_construction",
    "solver_settings",
    "physical_bounds",
    "provider_authority",
    "required_report_fields",
    "hard_stops",
    "prohibited_followups_after_failure",
)


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_source(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    claimed = payload.pop("contract_payload_sha256")
    if _canonical_hash(payload) != claimed:
        raise RuntimeError("DD-093 source contract checksum mismatch")
    payload["contract_payload_sha256"] = claimed
    return payload


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def prepare(source_path: Path, output_path: Path) -> dict[str, Any]:
    source = _load_source(source_path)
    mathematical = {key: source[key] for key in MATHEMATICAL_KEYS}
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "governance_exception": {
            "authorized_by_user": True,
            "authorization_date": "2026-07-25",
            "reason": (
                "DD-093 failed only in post-solve reporting before evidence "
                "serialization; no equation, solver, or physical gate failed"
            ),
            "scope": (
                "repair scalar product/duty movement reporting and add "
                "regression coverage; preserve the entire mathematical campaign"
            ),
        },
        "supersedes_execution_record_commit": (
            "d74a40b"
        ),
        "source_dd093_contract_path": str(source_path.resolve()),
        "source_dd093_contract_payload_sha256": source[
            "contract_payload_sha256"
        ],
        "mathematical_contract_sha256": _canonical_hash(mathematical),
        **mathematical,
        "reporting_repair": {
            "products_before": (
                "delta[layout.distillate.start:layout.bottoms.stop]"
            ),
            "products_after": (
                "delta[[layout.distillate, layout.bottoms]]"
            ),
            "duty_before": "delta[layout.condenser_duty][0]",
            "duty_after": "delta[layout.condenser_duty]",
            "equations_changed": False,
            "starts_changed": False,
            "bounds_changed": False,
            "solver_or_tolerances_changed": False,
            "provider_rules_changed": False,
        },
        "implementation_sha256": {
            relative: _file_hash(ROOT / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "full_residual_evaluated_during_preparation": False,
        "campaign_executed": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
    }
    payload["contract_payload_sha256"] = _canonical_hash(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    output_path.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-094 Frozen Reporting-Recovery Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                f"- Mathematical contract SHA-256: `{payload['mathematical_contract_sha256']}`",
                f"- DD-093 source payload: `{payload['source_dd093_contract_payload_sha256']}`",
                "- Mathematical changes: `False`",
                "- Campaign executed: `False`",
                "",
                "Only scalar product/duty movement reporting and its regression "
                "coverage differ from DD-093. Execution requires this contract "
                "to be committed and clean.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", required=True)
    parser.add_argument("--source", type=Path, default=SOURCE_CONTRACT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "logs/dd094_core_v3_steady_root_recovery_contract_20260725.json"
        ),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = prepare(args.source, args.output)
    print(
        json.dumps(
            {
                "schema_id": result["schema_id"],
                "contract_payload_sha256": result[
                    "contract_payload_sha256"
                ],
                "mathematical_contract_sha256": result[
                    "mathematical_contract_sha256"
                ],
                "start_lengths": {
                    name: len(values)
                    for name, values in result["starts"].items()
                },
                "campaign_executed": False,
            },
            indent=2,
        )
    )
