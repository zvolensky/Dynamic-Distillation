#!/usr/bin/env python
"""Prepare or execute DD-220's JSON-only DD-219 successor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import adjudicate_core_v3_bdf2_300s_controlled_response as dd219  # noqa: E402
import run_core_v3_terminal_inventory_control_bdf2_30s_production as dd209  # noqa: E402


SCHEMA = "dd220-core-v3-bdf2-300s-controlled-response-jsonfix-contract-v1"
RESULT_SCHEMA = "dd220-core-v3-bdf2-300s-controlled-response-jsonfix-result-v1"
DD219_CONTRACT = dd219.CONTRACT
DD219_RESULT_DOC = dd219.RESULT_DOC
CONTRACT = Path(
    "logs/dd220_core_v3_bdf2_300s_controlled_response_jsonfix_contract_20260815.json"
)
RESULT = Path("logs/dd220_core_v3_bdf2_300s_controlled_response_jsonfix_20260815")
CONTRACT_DOC = Path(
    "docs/dd_220_core_v3_bdf2_300s_controlled_response_jsonfix_contract_20260815.md"
)
RESULT_DOC = Path(
    "docs/dd_220_core_v3_bdf2_300s_controlled_response_jsonfix_20260815.md"
)
IMPLEMENTATION = (
    "tools/adjudicate_core_v3_bdf2_300s_controlled_response.py",
    "tools/adjudicate_core_v3_bdf2_300s_controlled_response_jsonfix.py",
    "tests/test_core_v3_bdf2_300s_controlled_response_jsonfix.py",
)


def _json_native(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_native(item) for item in value]
    if isinstance(value, list):
        return [_json_native(item) for item in value]
    return value


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-220 Controlled-Response JSON Successor Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- DD-219 source, limits, calculations, and gates: exact",
            "- Sole change: recursive NumPy scalar to native JSON scalar conversion",
            "- Model/provider/solver/trajectory calls: `0`",
            "- Retry or policy change: prohibited",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["response_assessment"]["metrics"]
    return "\n".join(
        (
            "# DD-220 Controlled-Response Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Inventory initial / peak / final: `{metrics['inventory_initial_lbmol']:.9f}` / `{metrics['inventory_peak_lbmol']:.9f}` / `{metrics['inventory_final_lbmol']:.9f} lbmol`",
            f"- Peak time / final decline samples: `{metrics['inventory_peak_time_seconds']:.1f} s` / `{metrics['consecutive_final_declines']}`",
            f"- Bottoms initial / final: `{metrics['bottoms_initial_lbmolph']:.6f}` / `{metrics['bottoms_final_lbmolph']:.6f} lbmol/h`",
            f"- Level range: `{metrics['minimum_level_fraction']:.6f}` to `{metrics['maximum_level_fraction']:.6f}`",
            "- Model/provider/solver/timestep calls: `0`",
            "- DD-218 formal classification: unchanged",
            "",
        )
    )


def prepare(
    contract_path: Path = CONTRACT, contract_doc_path: Path = CONTRACT_DOC
) -> dict[str, Any]:
    source = dd209._load(DD219_CONTRACT)
    if (ROOT / dd219.RESULT).with_suffix(".json").exists():
        raise RuntimeError("DD-220 requires absent DD-219 result")
    payload = {
        "schema_id": SCHEMA,
        "result_schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-220",
        "preparation_base_commit": dd209._git("rev-parse", "HEAD"),
        "dd219_contract": {
            "path": str(DD219_CONTRACT).replace("\\", "/"),
            "sha256": dd209._sha(ROOT / DD219_CONTRACT),
            "payload_sha256": source["contract_payload_sha256"],
        },
        "dd219_aborted_result": {
            "path": str(DD219_RESULT_DOC).replace("\\", "/"),
            "sha256": dd209._sha(ROOT / DD219_RESULT_DOC),
        },
        "source": source["source"],
        "limits": source["limits"],
        "implementation_sha256": {
            path: dd209._sha(ROOT / path) for path in IMPLEMENTATION
        },
        "allowed_change": "numpy_scalar_to_native_json_scalar_conversion_only",
        "model_calls": 0,
        "provider_calls": 0,
        "solver_calls": 0,
        "trajectory_calls": 0,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = dd209._hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-220 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def execute(
    contract_path: Path = CONTRACT,
    result_path: Path = RESULT,
    result_doc_path: Path = RESULT_DOC,
) -> dict[str, Any]:
    payload = dd209._load(contract_path)
    claimed = payload.pop("contract_payload_sha256")
    actual = dd209._hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-220 contract payload hash mismatch")
    if dd209._sha(ROOT / DD219_CONTRACT) != payload["dd219_contract"]["sha256"]:
        raise RuntimeError("DD-220 DD-219 contract changed")
    if dd209._sha(ROOT / DD219_RESULT_DOC) != payload["dd219_aborted_result"]["sha256"]:
        raise RuntimeError("DD-220 DD-219 failure record changed")
    for path, expected in payload["implementation_sha256"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-220 implementation changed: {path}")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-220 result exists; rerun prohibited")
    dd209._git("ls-files", "--error-unmatch", str(contract_path))
    source = dd209._load(dd219.DD218_RESULT)
    response = source["response_summary"]
    assessment = _json_native(
        dd219._analyze(source["sampled_steps"], payload["limits"])
    )
    gates = {
        "source_response_only_failure": [
            name for name, passed in source["campaign_gates"].items() if not passed
        ]
        == ["response"],
        "all_roots_complete": source["completed_roots"]
        == source["requested_roots"]
        == 1200,
        "nonresponse_campaign_gates": all(
            passed
            for name, passed in source["campaign_gates"].items()
            if name != "response"
        ),
        "endpoint_root_gates": all(source["endpoint"]["gates"].values()),
        "inventory_identity": response["component_inventory_identity_max_abs_lbmol"]
        < payload["limits"]["global_inventory_identity_limit_lbmol"],
        "inventory_relative": response["total_inventory_relative_error"]
        < payload["limits"]["global_inventory_relative_limit"],
        "controlled_response": assessment["pass_gate"],
        "zero_live_calls": payload["model_calls"]
        == payload["provider_calls"]
        == payload["solver_calls"]
        == payload["trajectory_calls"]
        == 0,
    }
    passed = all(gates.values())
    result = _json_native(
        {
            "schema_id": RESULT_SCHEMA,
            "campaign_id": "DD-220",
            "classification": (
                "controlled_five_minute_dynamics_accepted"
                if passed
                else "controlled_response_adjudication_failed"
            ),
            "decision": (
                "accept_dd218_science_under_controlled_response_policy"
                if passed
                else "retain_dd217_60s_production_boundary"
            ),
            "contract_commit": dd209._git("rev-parse", "HEAD"),
            "contract_payload_sha256": claimed,
            "source": payload["source"],
            "dd218_formal_classification_unchanged": True,
            "dd219_aborted_without_scientific_result": True,
            "response_assessment": assessment,
            "conservation": {
                "component_inventory_identity_max_abs_lbmol": response[
                    "component_inventory_identity_max_abs_lbmol"
                ],
                "total_inventory_relative_error": response[
                    "total_inventory_relative_error"
                ],
            },
            "gates": gates,
            "pass_gate": passed,
            "model_calls": 0,
            "provider_calls": 0,
            "solver_calls": 0,
            "trajectory_calls": 0,
            "campaign_executed_once": True,
        }
    )
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
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.contract, args.contract_doc)
        print(json.dumps(output, indent=2))
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
