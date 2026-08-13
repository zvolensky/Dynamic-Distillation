#!/usr/bin/env python
"""Prepare or execute DD-189's zero-call controlled-response adjudication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import run_core_v3_seven_volume_terminal_inventory_control_moving_step as dd187  # noqa: E402


SCHEMA = "dd189-core-v3-controlled-response-adjudication-contract-v1"
RESULT_SCHEMA = "dd189-core-v3-controlled-response-adjudication-result-v1"
DD188_RESULT = Path(
    "logs/dd188_core_v3_seven_volume_terminal_inventory_control_short_trajectory_20260813.json"
)
CONTRACT = Path(
    "logs/dd189_core_v3_terminal_inventory_control_response_adjudication_contract_20260813.json"
)
RESULT = Path(
    "logs/dd189_core_v3_terminal_inventory_control_response_adjudication_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_189_core_v3_terminal_inventory_control_response_adjudication_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_189_core_v3_terminal_inventory_control_response_adjudication_20260813.md"
)
IMPLEMENTATION = (
    "tools/adjudicate_core_v3_terminal_inventory_control_short_trajectory.py",
    "tests/test_core_v3_terminal_inventory_control_response_adjudication.py",
)


def _failed_names(values: Mapping[str, Any]) -> list[str]:
    return [name for name, passed in values.items() if not passed]


def _validate_source(source: Mapping[str, Any]) -> None:
    if source.get("pass_gate") is not False or source.get("decision") != (
        "stop_terminal_control_trajectory_path"
    ):
        raise RuntimeError("DD-189 requires DD-188's preserved formal failure")
    if _failed_names(source["campaign_gates"]) != [
        "response",
        "shared_time_refinement",
    ]:
        raise RuntimeError("DD-188 campaign failure pattern changed")
    if _failed_names(source["response_gates"]["cross_grid"]) != ["total_inventory"]:
        raise RuntimeError("DD-188 cross-grid response failure changed")
    if not all(source["response_gates"][name][gate] for name in ("coarse", "refined") for gate in source["response_gates"][name]):
        raise RuntimeError("DD-188 individual response path no longer passes")
    if not source["coarse"]["step_gates_pass"] or not source["refined"]["step_gates_pass"]:
        raise RuntimeError("DD-188 per-root gates changed")
    comparisons = source["shared_time_refinement"]["comparisons"]
    for item in comparisons:
        failed = _failed_names(item["gates"])
        if failed not in ([], ["signed_total"]):
            raise RuntimeError("DD-188 shared-time failure is not signed-total only")


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-189 Controlled-Response Zero-Call Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Source: immutable DD-188 result only",
            "- Model/provider/solver/endpoint-regeneration calls: prohibited",
            "- DD-188 formal classification: preserved",
            "- Test: actual cross-grid total difference versus independently integrated external-flow difference",
            "- Prospective response-relative limit: `<1e-5`",
            "",
            "Commit before execution. This adjudication cannot rerun or reclassify DD-188.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["metrics"]
    return "\n".join(
        (
            "# DD-189 Controlled-Response Zero-Call Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Actual cross-grid difference: `{metrics['actual_cross_grid_difference_lbmol']:.6e} lbmol`",
            f"- Expected external-flow difference: `{metrics['expected_cross_grid_difference_lbmol']:.6e} lbmol`",
            f"- Unexplained difference: `{metrics['unexplained_cross_grid_difference_lbmol']:.6e} lbmol`",
            f"- Difference relative to response: `{metrics['cross_grid_difference_relative_to_response']:.6e}`",
            "- Model/provider/solver/endpoint-regeneration calls: `0 / 0 / 0 / 0`",
            f"- Wall clock: `{payload['wall_clock_sec']:.6f} s`",
            "- DD-188 reclassified or rerun: `False / False`",
            "",
        )
    )


def prepare(
    source_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = dd187.dd186._load(source_path)
    _validate_source(source)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": dd187.dd186._git("rev-parse", "HEAD"),
        "source_path": str(source_path).replace("\\", "/"),
        "source_sha256": dd187.dd186._sha(ROOT / source_path),
        "source_contract_commit": source["contract_commit"],
        "preserved_source_classification": source["classification"],
        "preserved_source_decision": source["decision"],
        "limits": {
            "individual_path_integrated_relative_error": 1.0e-6,
            "unexplained_cross_grid_difference_lbmol": 1.0e-10,
            "cross_grid_difference_relative_to_response": 1.0e-5,
            "component_inventory_identity_lbmol": 1.0e-6,
            "wall_clock_sec": 5.0,
        },
        "prospective_policy": {
            "scope": "controlled trajectories with evolving external product outputs",
            "retain_all_non_signed_total_physical_refinement_gates": True,
            "signed_total_is_reported_diagnostic": True,
            "require_actual_grid_difference_to_match_integrated_external_flow_difference": True,
            "require_response_relative_grid_difference": True,
        },
        "implementation_sha256": {
            path: dd187.dd186._sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "DD-188 formal failure pattern differs from the frozen source",
            "either path fails its integrated external-flow identity",
            "cross-grid difference is not explained by integrated external flow",
            "cross-grid difference exceeds the response-relative limit",
            "any model, provider, solver, or endpoint-regeneration call occurs",
        ],
        "model_calls_attempted": False,
        "provider_calls_attempted": False,
        "solver_calls_attempted": False,
        "endpoint_regeneration_attempted": False,
        "source_reclassification_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = dd187.dd186._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-189 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = dd187.dd186._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-189 contract payload hash mismatch")
    if dd187.dd186._sha(ROOT / payload["source_path"]) != payload["source_sha256"]:
        raise RuntimeError("DD-189 source changed")
    for path, expected in payload["implementation_sha256"].items():
        if dd187.dd186._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-189 implementation changed: {path}")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-189 result exists; rerun is prohibited")
    if not dd187.dd186._git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-189 contract is not committed")


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    payload = dd187.dd186._load(contract_path)
    _verify(payload, contract_path, result_path)
    source = dd187.dd186._load(Path(payload["source_path"]))
    _validate_source(source)
    coarse = source["response"]["coarse"]
    refined = source["response"]["refined"]
    actual_difference = float(coarse["total_inventory_change_lbmol"]) - float(
        refined["total_inventory_change_lbmol"]
    )
    expected_difference = float(
        coarse["expected_total_inventory_change_lbmol"]
    ) - float(refined["expected_total_inventory_change_lbmol"])
    unexplained = abs(actual_difference - expected_difference)
    response_scale = max(
        abs(float(coarse["total_inventory_change_lbmol"])),
        abs(float(refined["total_inventory_change_lbmol"])),
        1.0e-12,
    )
    relative = abs(actual_difference) / response_scale
    limits = payload["limits"]
    path_relative = {
        name: abs(
            float(values["total_inventory_change_lbmol"])
            - float(values["expected_total_inventory_change_lbmol"])
        )
        / max(abs(float(values["expected_total_inventory_change_lbmol"])), 1.0e-12)
        for name, values in (("coarse", coarse), ("refined", refined))
    }
    metrics = {
        "actual_cross_grid_difference_lbmol": actual_difference,
        "expected_cross_grid_difference_lbmol": expected_difference,
        "unexplained_cross_grid_difference_lbmol": unexplained,
        "cross_grid_difference_relative_to_response": relative,
        "individual_path_integrated_relative_error": path_relative,
        "maximum_component_inventory_identity_lbmol": max(
            float(coarse["component_inventory_identity_max_abs_lbmol"]),
            float(refined["component_inventory_identity_max_abs_lbmol"]),
        ),
    }
    gates = {
        "source_failure_preserved": source["pass_gate"] is False,
        "coarse_integrated_identity": path_relative["coarse"]
        < limits["individual_path_integrated_relative_error"],
        "refined_integrated_identity": path_relative["refined"]
        < limits["individual_path_integrated_relative_error"],
        "external_flow_explains_grid_difference": unexplained
        < limits["unexplained_cross_grid_difference_lbmol"],
        "response_relative_grid_difference": relative
        < limits["cross_grid_difference_relative_to_response"],
        "component_inventory_identity": metrics[
            "maximum_component_inventory_identity_lbmol"
        ]
        < limits["component_inventory_identity_lbmol"],
        "zero_live_calls": True,
    }
    elapsed = time.perf_counter() - started
    gates["wall_clock"] = elapsed < limits["wall_clock_sec"]
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "controlled_response_policy_adjudication_passed"
            if passed
            else "controlled_response_policy_adjudication_failed"
        ),
        "decision": (
            "authorize_one_frozen_modest_controlled_trajectory_contract_under_response_scaled_policy"
            if passed
            else "retain_controlled_trajectory_stop"
        ),
        "contract_commit": dd187.dd186._git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "preserved_dd188_classification": source["classification"],
        "preserved_dd188_decision": source["decision"],
        "metrics": metrics,
        "gates": gates,
        "pass_gate": passed,
        "wall_clock_sec": float(elapsed),
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "endpoint_regeneration_calls": 0,
        "dd188_reclassified": False,
        "dd188_rerun": False,
        "campaign_executed_once": True,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--source", type=Path, default=DD188_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.source, args.contract, args.contract_doc)
        print(json.dumps({"schema_id": output["schema_id"], "contract_payload_sha256": output["contract_payload_sha256"], "campaign_executed": output["campaign_executed"]}, indent=2))
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(json.dumps({"classification": output["classification"], "pass_gate": output["pass_gate"], "decision": output["decision"]}, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
