#!/usr/bin/env python
"""Prepare or execute DD-194's short incremental-audit qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_seven_volume_terminal_inventory_control_finer_parallel_trajectory as dd193  # noqa: E402


SCHEMA = "dd194-core-v3-controlled-incremental-audit-qualification-contract-v1"
RESULT_SCHEMA = "dd194-core-v3-controlled-incremental-audit-qualification-result-v1"
DD193_CONTRACT = dd193.CONTRACT
DD193_RESULT = Path(
    "logs/dd193_core_v3_terminal_inventory_control_finer_parallel_trajectory_20260813.json"
)
CONTRACT = Path(
    "logs/dd194_core_v3_terminal_inventory_control_incremental_audit_qualification_contract_20260813.json"
)
RESULT = Path(
    "logs/dd194_core_v3_terminal_inventory_control_incremental_audit_qualification_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_194_core_v3_terminal_inventory_control_incremental_audit_qualification_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_194_core_v3_terminal_inventory_control_incremental_audit_qualification_20260813.md"
)
DURATION_SEC = 2.0
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_trajectory_v1.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_finer_parallel_trajectory.py",
    "tools/run_core_v3_terminal_inventory_control_incremental_audit_qualification.py",
    "tests/test_core_v3_terminal_inventory_control_incremental_audit_qualification.py",
)


def _validate_source(source: Mapping[str, Any]) -> None:
    if source.get("pass_gate") is not False or source.get("classification") != (
        "controlled_finer_parallel_trajectory_aborted_on_wall_hard_stop"
    ):
        raise RuntimeError("DD-194 requires DD-193's preserved efficiency stop")
    if source.get("scientific_gates") != "not_evaluated":
        raise RuntimeError("DD-193 scientific non-classification changed")
    diagnosis = source.get("diagnosis", {})
    if diagnosis.get("category") != "worker_provenance_reporting_scaling_defect":
        raise RuntimeError("DD-193 audit-scaling diagnosis changed")
    if source.get("campaign_rerun") or not source.get("processes_stopped", {}).get(
        "all_confirmed_stopped"
    ):
        raise RuntimeError("DD-193 process or rerun preservation changed")


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    paths = payload["paths"]
    performance = payload["performance"]
    return "\n".join(
        (
            "# DD-194 Incremental Worker-Audit Qualification Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            f"- Duration: `{paths['duration_seconds']} s`",
            f"- Coarse/refined: `{paths['coarse_steps']} x {paths['coarse_step_seconds']} s` / `{paths['refined_steps']} x {paths['refined_step_seconds']} s`",
            "- Worker provider validation: incremental records only",
            "- In-execution total deadline: enabled",
            f"- Parallel trajectory wall gate: `<{performance['parallel_wall_limit_sec']:.3f} s`",
            "- DD-193 rerun, ten-second claim, tuning, and alternate grid: prohibited",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    performance = payload["performance"]
    return "\n".join(
        (
            "# DD-194 Incremental Worker-Audit Qualification Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Completed roots: `{payload.get('completed_roots')}`",
            f"- Worst residual: `{payload.get('worst_residual', float('nan')):.6e}`",
            f"- Trajectory/startup wall: `{performance['parallel_trajectory_wall_sec']:.3f}` / `{performance['startup_wall_sec_adjusted']:.3f} s`",
            f"- Projected serial speedup: `{performance.get('projected_speedup', 0.0):.3f}x`",
            f"- Logical provider calls: `{payload['provider']['logical_calls']}`",
            f"- In-execution deadline gate: `{payload['campaign_gates'].get('total_wall', False)}`",
            "- DD-193 rerun or reclassification: `False / False`",
            "",
        )
    )


def prepare(
    source_contract_path: Path,
    source_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    payload = dd193._load(source_contract_path)
    source_result = dd193._load(source_result_path)
    _validate_source(source_result)
    coarse_count = dd193.dd190.dd188.dd177._step_count(
        DURATION_SEC, dd193.COARSE_DT_SEC
    )
    refined_count = dd193.dd190.dd188.dd177._step_count(
        DURATION_SEC, dd193.REFINED_DT_SEC
    )
    pairs = dd193.dd190.dd188.dd177._shared_step_pairs(
        coarse_count, refined_count
    )
    dd190_result = dd193._load(dd193.DD190_RESULT)
    projected_serial = float(dd190_result["wall_clock_sec"]) * (
        (coarse_count + refined_count) / dd190_result["completed_roots"]
    )
    payload.update(
        {
            "schema_id": SCHEMA,
            "preparation_base_commit": dd193._git("rev-parse", "HEAD"),
            "paths": {
                "duration_seconds": DURATION_SEC,
                "coarse_step_seconds": dd193.COARSE_DT_SEC,
                "coarse_steps": coarse_count,
                "refined_step_seconds": dd193.REFINED_DT_SEC,
                "refined_steps": refined_count,
                "shared_time_count": len(pairs),
                "shared_step_pairs_1based": [list(pair) for pair in pairs],
            },
            "performance": {
                "dd190_serial_wall_sec": dd190_result["wall_clock_sec"],
                "dd190_serial_roots": dd190_result["completed_roots"],
                "projected_serial_wall_sec": projected_serial,
                "parallel_ratio_limit": 0.80,
                "parallel_wall_limit_sec": projected_serial * 0.80,
                "startup_wall_limit_sec": 30.0,
            },
            "limits": {
                **payload["limits"],
                "provider_calls": 300_000,
                "wall_clock_sec": 90.0,
            },
            "implementation_sha256": {
                path: dd193._sha(ROOT / path) for path in IMPLEMENTATION
            },
            "hard_stops": [
                "either short finer-grid path fails a scientific gate",
                "incremental worker validation loses provider ownership",
                "actual task participation or per-root basis refresh fails",
                "trajectory exceeds 80 percent of the projected serial baseline",
                "the in-execution 90-second deadline is reached",
            ],
            "dd193_source_path": str(source_result_path).replace("\\", "/"),
            "dd193_source_sha256": dd193._sha(ROOT / source_result_path),
            "qualification_only": True,
            "ten_second_claim_authorized": False,
            "campaign_executed": False,
        }
    )
    payload["sources"] = {
        **payload["sources"],
        str(source_result_path).replace("\\", "/"): payload["dd193_source_sha256"],
    }
    payload.pop("contract_payload_sha256", None)
    payload["contract_payload_sha256"] = dd193._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-194 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = dd193._load(contract_path)
    source = dd193._load(Path(payload["dd193_source_path"]))
    _validate_source(source)
    raw = dd193.execute(contract_path, result_path, result_doc_path)
    passed = bool(raw["pass_gate"])
    raw.update(
        {
            "schema_id": RESULT_SCHEMA,
            "classification": (
                "incremental_worker_audit_short_qualification_passed"
                if passed
                else "incremental_worker_audit_short_qualification_failed"
            ),
            "decision": (
                "authorize_one_separately_frozen_ten_second_finer_grid_campaign"
                if passed
                else "retain_finer_grid_campaign_stop"
            ),
            "preserved_dd193_classification": source["classification"],
            "dd193_rerun": False,
            "dd193_reclassified": False,
            "qualification_only": True,
            "ten_second_result_claimed": False,
        }
    )
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(raw), encoding="utf-8")
    return raw


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--source-contract", type=Path, default=DD193_CONTRACT)
    parser.add_argument("--source-result", type=Path, default=DD193_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.source_contract,
            args.source_result,
            args.contract,
            args.contract_doc,
        )
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "paths": output["paths"],
                    "performance": output["performance"],
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
