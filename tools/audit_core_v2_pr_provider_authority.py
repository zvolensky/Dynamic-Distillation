#!/usr/bin/env python
"""Prepare or execute the structural DD-090 PR provider-authority audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v2.pr_provider_authority_contract_v1 import (
    audit_contract_structure,
    build_pr_provider_authority_contract,
    contract_payload,
    evaluate_dd089_evidence,
)


SCHEMA_ID = "dd090-pr-provider-authority-contract-v1"
RESULT_SCHEMA_ID = "dd090-pr-provider-authority-result-v1"
DD089_RESULT = ROOT / "logs/dd089_dwsim_pr_interface_consistency_20260719.json"
DD089_CONTRACT = ROOT / (
    "logs/dd089_dwsim_pr_interface_consistency_contract_20260719.json"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    authority = payload["provider_authority"]
    lines = [
        "# DD-090 PR Provider-Authority Contract",
        "",
        f"- Schema: `{payload['schema_id']}`",
        f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
        f"- Preparation base commit: `{payload['preparation_base_commit']}`",
        f"- DD-089 result SHA-256: `{payload['dd089_result_sha256']}`",
        f"- Quantity rules: `{len(authority['quantities'])}`",
        "",
        "## Authority Table",
        "",
        "| Quantity | Authority | Basis | Tolerance |",
        "|---|---|---|---|",
    ]
    for item in authority["quantities"]:
        tolerance = item["tolerance_name"] or "classification/no scalar gate"
        lines.append(
            f"| `{item['quantity']}` | {item['authority']} | "
            f"{item['expected_basis']} | `{tolerance}` |"
        )
    lines.extend(
        (
            "",
            "## Frozen Policy",
            "",
            "- Direct imposed-phase fugacity is the production equilibrium authority.",
            "- Independent parameter-aligned PR is validation-only.",
            "- TP flash owns phase classification, phase fraction, phase "
            "compositions, and lever-rule closure.",
            "- Flash K-values are interpreted only on the flash phase bases.",
            "- `normalize(K_flash*z)` is prohibited as a strict bubble-vapor "
            "gate when beta is nonzero.",
            "- No fallback is permitted between direct fugacity and TP flash.",
            "- No strict direct-y versus flash-y equality is required.",
            "",
            "Execution performs a static audit against the immutable DD-089 "
            "evidence. No property call, column residual, solve, or dynamic "
            "integration is authorized.",
            "",
        )
    )
    return "\n".join(lines)


def prepare(contract_path: Path) -> dict[str, Any]:
    contract = build_pr_provider_authority_contract()
    structure = audit_contract_structure(contract)
    if not structure["pass"]:
        raise RuntimeError("DD-090 proposed authority contract is incomplete")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd089_result_path": str(DD089_RESULT.relative_to(ROOT)),
        "dd089_result_sha256": _sha256_file(DD089_RESULT),
        "dd089_contract_path": str(DD089_CONTRACT.relative_to(ROOT)),
        "dd089_contract_sha256": _sha256_file(DD089_CONTRACT),
        "provider_authority": contract_payload(contract),
        "structural_audit": structure,
        "execution_scope": {
            "evaluate_only_frozen_dd089_evidence": True,
            "live_property_calls": False,
            "column_residual": False,
            "column_solve": False,
            "dynamic_integration": False,
            "dd088_reclassification": False,
        },
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    contract_path.with_suffix(".md").write_text(
        _contract_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _load_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    claimed = str(payload.pop("contract_payload_sha256", ""))
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if payload.get("schema_id") != SCHEMA_ID:
        raise RuntimeError("DD-090 contract schema does not match")
    if claimed != actual:
        raise RuntimeError("DD-090 contract payload checksum does not match")
    return payload


def _verify_contract_is_committed(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    _git("ls-files", "--error-unmatch", relative)
    committed = _git("show", f"HEAD:{relative}")
    current = path.read_text(encoding="utf-8")
    if committed.replace("\r\n", "\n") != current.replace("\r\n", "\n"):
        raise RuntimeError("DD-090 contract differs from committed HEAD")
    relevant = (
        "src/dynamic_distillation/core_v2/pr_provider_authority_contract_v1.py",
        "tools/audit_core_v2_pr_provider_authority.py",
        "tests/test_core_v2_pr_provider_authority_contract_v1.py",
        "docs/dd_090_pr_provider_authority_contract_20260719.md",
        relative,
        Path(relative).with_suffix(".md").as_posix(),
    )
    if _git("status", "--short", "--", *relevant):
        raise RuntimeError("DD-090 implementation has tracked changes")
    return _git("rev-parse", "HEAD")


def _evidence_from_dd089(report: Mapping[str, Any]) -> dict[str, Any]:
    base = report["base_state_analysis"]
    independent = report["independent_pr_base_comparison"]
    beta = float(base["rachford_rice_beta"])
    return {
        "direct_fugacity_residual_inf": float(
            base["direct_bubble_residual_inf"]
        ),
        "independent_pr_temperature_delta_F": float(
            independent["temperature_F"]
        ),
        "independent_pr_vapor_max_abs": float(independent["vapor_max_abs"]),
        "flash_Kx_reconstruction_max_abs": float(
            base["flash_y_minus_Kx_flash_max_abs"]
        ),
        "flash_lever_rule_max_abs": float(
            base["lever_rule_closure_max_abs"]
        ),
        "beta": beta,
        "stable_vapor": bool(beta >= 1.0 - 1.0e-12),
        "fresh_process_repeatability_max_abs": float(
            report["repeatability"]["overall_max_abs"]
        ),
        "mixed_basis_reported_separately": bool(
            "Kx_flash_minus_Kz_max_abs" in base
        ),
        "cross_interface_y_reported_without_equality_gate": bool(
            "direct_y_minus_flash_y_max_abs" in base
        ),
        "fallback_used": False,
        "diagnostic_only": {
            "direct_y_minus_flash_y_max_abs": float(
                base["direct_y_minus_flash_y_max_abs"]
            ),
            "mixed_basis_shift_max_abs": float(
                base["Kx_flash_minus_Kz_max_abs"]
            ),
            "legacy_mixed_metric_max_abs": float(
                base["legacy_direct_y_minus_Kz_max_abs"]
            ),
            "flash_phase_residual_inf": float(
                base["flash_phase_residual_inf"]
            ),
        },
    }


def _result_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# DD-090 PR Provider-Authority Result",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Contract commit: `{report['contract_commit']}`",
        "",
        "## Checks",
        "",
        "| Check | Pass |",
        "|---|---|",
    ]
    for name, passed in report["audit"]["checks"].items():
        lines.append(f"| `{name}` | `{passed}` |")
    lines.extend(
        (
            "",
            "## Authorization",
            "",
            report["authorization"],
            "",
        )
    )
    return "\n".join(lines)


def execute(contract_path: Path, out_prefix: Path) -> dict[str, Any]:
    contract_commit = _verify_contract_is_committed(contract_path)
    frozen = _load_contract(contract_path)
    if _sha256_file(DD089_RESULT) != frozen["dd089_result_sha256"]:
        raise RuntimeError("DD-089 result changed after DD-090 preparation")
    if _sha256_file(DD089_CONTRACT) != frozen["dd089_contract_sha256"]:
        raise RuntimeError("DD-089 contract changed after DD-090 preparation")
    authority = build_pr_provider_authority_contract()
    if contract_payload(authority) != frozen["provider_authority"]:
        raise RuntimeError("DD-090 live authority differs from frozen contract")
    dd089 = json.loads(DD089_RESULT.read_text(encoding="utf-8"))
    evidence = _evidence_from_dd089(dd089)
    audit = evaluate_dd089_evidence(authority, evidence)
    passed = bool(audit["pass"])
    report: dict[str, Any] = {
        "schema_id": RESULT_SCHEMA_ID,
        "classification": (
            "dd090_pr_provider_authority_passed"
            if passed
            else "dd090_pr_provider_authority_failed"
        ),
        "decision": (
            "authorize_successor_architecture_decision"
            if passed
            else "provider_authority_contract_not_ready"
        ),
        "authorization": (
            "DD-090 passes. A project decision may now be made on a separately "
            "versioned successor condenser architecture using this prospective "
            "property authority. No column solve, DD-088 reclassification, "
            "or dynamic integration is authorized."
            if passed
            else "DD-090 fails. Do not define a successor architecture or "
            "perform column or dynamic work from this contract."
        ),
        "contract_commit": contract_commit,
        "contract_payload_sha256": frozen["contract_payload_sha256"],
        "dd089_result_sha256": frozen["dd089_result_sha256"],
        "dd089_contract_sha256": frozen["dd089_contract_sha256"],
        "provider_authority": frozen["provider_authority"],
        "evidence": evidence,
        "audit": audit,
        "live_property_calls": False,
        "column_residual_evaluated": False,
        "column_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "dd088_reclassified": False,
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    out_prefix.with_suffix(".md").write_text(
        _result_markdown(report),
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("logs/dd090_pr_provider_authority_contract_20260719.json"),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd090_pr_provider_authority_20260719"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare_only:
        output = prepare(args.contract)
        summary = {
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "quantity_count": len(
                output["provider_authority"]["quantities"]
            ),
        }
    else:
        output = execute(args.contract, args.out_prefix)
        summary = {
            "classification": output["classification"],
            "decision": output["decision"],
        }
    print(json.dumps(summary, indent=2))
    raise SystemExit(
        0
        if not args.execute
        or output["classification"] == "dd090_pr_provider_authority_passed"
        else 2
    )
