#!/usr/bin/env python
"""Prepare or execute DD-201's zero-call DD-200 response adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DD200_CONTRACT = Path("logs/dd200_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_contract_20260813.json")
DD200_RESULT = Path("logs/dd200_core_v3_seven_volume_terminal_inventory_control_bdf2_refinement_20260813.json")
DD189_RESULT = Path("logs/dd189_core_v3_terminal_inventory_control_response_adjudication_20260813.json")
CONTRACT = Path("logs/dd201_core_v3_terminal_inventory_control_bdf2_refinement_response_contract_20260813.json")
RESULT = Path("logs/dd201_core_v3_terminal_inventory_control_bdf2_refinement_response_20260813")
CONTRACT_DOC = Path("docs/dd_201_core_v3_terminal_inventory_control_bdf2_refinement_response_contract_20260813.md")
RESULT_DOC = Path("docs/dd_201_core_v3_terminal_inventory_control_bdf2_refinement_response_20260813.md")
IMPLEMENTATION = "tools/adjudicate_core_v3_terminal_inventory_control_bdf2_refinement_response.py"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _expected_total_history(initial_total: float, external_rates: Sequence[float], step_seconds: float) -> list[float]:
    h = float(step_seconds) / 3600.0
    expected = [float(initial_total), float(initial_total) + h * float(external_rates[0])]
    for rate in external_rates[1:]:
        expected.append((4.0 * expected[-1] - expected[-2] + 2.0 * h * float(rate)) / 3.0)
    return expected


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join((
        "# DD-201 BDF2 Response Adjudication Contract",
        "",
        f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
        f"- Preparation base commit: `{payload['preparation_base_commit']}`",
        "- DD-200 formal failure retained: `True`",
        "- Inputs: immutable saved inventories plus feed/distillate/bottoms rates",
        "- Expected response: BE startup followed by constant-step BDF2 recurrence",
        "- Unexplained difference limit: `<1e-10 lbmol`",
        "- Response-relative difference limit: `<1e-5`",
        "- Model/provider/solver/endpoint-regeneration calls: `0`",
        "",
        "Commit before the one zero-call execution.",
        "",
    ))


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join((
        "# DD-201 BDF2 Response Adjudication Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Shared times: `{len(payload['shared_time_adjudication'])}`",
        f"- Worst unexplained difference: `{payload['worst_unexplained_difference_lbmol']:.6e} lbmol`",
        f"- Worst response-relative difference: `{payload['worst_response_relative_difference']:.6e}`",
        "- DD-200 remains formally failed: `True`",
        "- Model/provider/solver/endpoint-regeneration calls: `0 / 0 / 0 / 0`",
        "",
    ))


def prepare(contract_path: Path, result_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    source = _load(DD200_CONTRACT)
    result = _load(DD200_RESULT)
    policy = _load(DD189_RESULT)
    if result["pass_gate"] or result["campaign_gates"]["shared_physical"]:
        raise RuntimeError("DD-201 requires DD-200's shared-physical-only failure")
    if not policy["pass_gate"]:
        raise RuntimeError("DD-201 requires accepted DD-189 policy")
    payload: dict[str, Any] = {
        "schema_id": "dd201-core-v3-bdf2-response-adjudication-contract-v1",
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {str(path).replace("\\", "/"): _sha(ROOT / path) for path in (DD200_CONTRACT, DD200_RESULT, DD189_RESULT)},
        "implementation_sha256": _sha(ROOT / IMPLEMENTATION),
        "limits": {"unexplained_difference_lbmol": 1e-10, "response_relative_difference": 1e-5},
        "required_failed_subgate": "signed_total",
        "dd200_must_remain_failed": True,
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "endpoint_regeneration_calls": 0,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-201 contract exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-201 contract hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-201 source changed: {path}")
    if _sha(ROOT / IMPLEMENTATION) != payload["implementation_sha256"]:
        raise RuntimeError("DD-201 implementation changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-201 result exists")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-201 contract is not committed")


def execute(contract_path: Path, result_path: Path, result_doc_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    source = _load(DD200_CONTRACT)
    result = _load(DD200_RESULT)
    feed_total = float(np.sum(source["source_mapping"]["feed_component_lbmolph"]))
    initial_total = float(np.sum(source["accepted_root_inventory_lbmol"]))
    path_data: dict[str, Any] = {}
    for name in ("coarse", "refined"):
        steps = result[name]["steps"]
        external = [feed_total - float(item["distillate_lbmolph"]) - float(item["bottoms_lbmolph"]) for item in steps]
        expected = _expected_total_history(initial_total, external, result["paths"][f"{name}_step_seconds"])
        actual = [initial_total, *[float(np.sum(item["inventory_lbmol"])) for item in steps]]
        path_data[name] = {"actual_total_inventory_lbmol": actual, "expected_total_inventory_lbmol": expected}
    adjudications = []
    limits = payload["limits"]
    preserved = True
    for comparison, pair in zip(result["shared_time_refinement"]["comparisons"], result["paths"]["shared_step_pairs_1based"], strict=True):
        failed = [name for name, value in comparison["gates"].items() if not value]
        preserved &= failed in ([], [payload["required_failed_subgate"]])
        coarse_index, refined_index = (int(pair[0]), int(pair[1]))
        actual_difference = path_data["coarse"]["actual_total_inventory_lbmol"][coarse_index] - path_data["refined"]["actual_total_inventory_lbmol"][refined_index]
        expected_difference = path_data["coarse"]["expected_total_inventory_lbmol"][coarse_index] - path_data["refined"]["expected_total_inventory_lbmol"][refined_index]
        unexplained = actual_difference - expected_difference
        coarse_response = path_data["coarse"]["actual_total_inventory_lbmol"][coarse_index] - initial_total
        refined_response = path_data["refined"]["actual_total_inventory_lbmol"][refined_index] - initial_total
        scale = max(abs(coarse_response), abs(refined_response), 1e-12)
        relative = abs(actual_difference) / scale
        gates = {"external_flow_explanation": abs(unexplained) < limits["unexplained_difference_lbmol"], "response_relative": relative < limits["response_relative_difference"]}
        adjudications.append({"time_seconds": comparison["time_seconds"], "original_failed_subgates": failed, "actual_difference_lbmol": actual_difference, "expected_external_difference_lbmol": expected_difference, "unexplained_difference_lbmol": unexplained, "response_relative_difference": relative, "gates": gates, "pass_gate": all(gates.values())})
    inherited = dict(result["campaign_gates"])
    inherited.pop("shared_physical")
    gates = {
        "dd200_remains_failed": not result["pass_gate"],
        "only_signed_total_failed": preserved,
        "all_other_campaign_gates": all(inherited.values()),
        "all_other_shared_gates": preserved,
        "adjudication": all(item["pass_gate"] for item in adjudications),
        "zero_calls": all(payload[name] == 0 for name in ("model_calls", "provider_calls", "solver_calls", "endpoint_regeneration_calls")),
    }
    passed = all(gates.values())
    output = {
        "schema_id": "dd201-core-v3-bdf2-response-adjudication-result-v1",
        "classification": "bdf2_response_policy_passed" if passed else "bdf2_response_policy_failed",
        "decision": "authorize_one_frozen_modest_bdf2_trajectory_contract" if passed else "retain_bdf2_trajectory_stop",
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "dd200_formal_failure_retained": True,
        "shared_time_adjudication": adjudications,
        "worst_unexplained_difference_lbmol": max(abs(item["unexplained_difference_lbmol"]) for item in adjudications),
        "worst_response_relative_difference": max(item["response_relative_difference"] for item in adjudications),
        "gates": gates,
        "pass_gate": passed,
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "endpoint_regeneration_calls": 0,
        "campaign_executed_once": True,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(output), encoding="utf-8")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.contract, args.result, args.contract_doc)
        print(json.dumps({"schema_id": output["schema_id"], "contract_payload_sha256": output["contract_payload_sha256"], "campaign_executed": output["campaign_executed"]}, indent=2))
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(json.dumps({"classification": output["classification"], "pass_gate": output["pass_gate"], "decision": output["decision"]}, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
