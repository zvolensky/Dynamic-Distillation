#!/usr/bin/env python
"""Prepare or execute DD-179's zero-call DD-178 response adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DD178_CONTRACT = Path(
    "logs/dd178_core_v3_seven_volume_physical_modest_trajectory_contract_20260812.json"
)
DD178_RESULT = Path(
    "logs/dd178_core_v3_seven_volume_physical_modest_trajectory_20260812.json"
)
CONTRACT = Path(
    "logs/dd179_core_v3_seven_volume_modest_response_adjudication_contract_20260812.json"
)
RESULT = Path(
    "logs/dd179_core_v3_seven_volume_modest_response_adjudication_20260812"
)
IMPLEMENTATION = (
    "tools/adjudicate_core_v3_seven_volume_modest_response.py",
    "tests/test_core_v3_seven_volume_modest_response_adjudication.py",
)


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


def _validate_source(result: Mapping[str, Any]) -> None:
    if result.get("pass_gate") is not False:
        raise RuntimeError("DD-179 requires DD-178's preserved formal failure")
    if result.get("decision") != "stop_physical_trajectory_path":
        raise RuntimeError("DD-178 stop decision changed")
    expected_campaign = {
        "coarse_complete": True,
        "refined_complete": True,
        "response": False,
        "shared_time_refinement": True,
        "legacy_ratio_diagnostic_only": True,
        "provider": True,
        "provider_calls": True,
        "wall_clock": True,
    }
    if result.get("campaign_gates") != expected_campaign:
        raise RuntimeError("DD-178 campaign failure pattern changed")
    for name, gates in result["response_gates"].items():
        failed = [gate for gate, passed in gates.items() if not passed]
        if failed != ["bounded"]:
            raise RuntimeError(
                f"DD-178 {name} did not fail only the inherited bounded gate"
            )
    if not result["shared_time_refinement"]["pass_gate"]:
        raise RuntimeError("DD-178 physical refinement did not pass")


def _response_metrics(response: Mapping[str, Any]) -> dict[str, float]:
    actual = float(response["total_inventory_change_lbmol"])
    expected = float(response["expected_total_inventory_change_lbmol"])
    if expected <= 0.0:
        raise ValueError("duration-scaled expected response must be positive")
    return {
        "actual_total_inventory_change_lbmol": actual,
        "expected_total_inventory_change_lbmol": expected,
        "absolute_response_error_lbmol": abs(actual - expected),
        "relative_response_error": abs(actual - expected) / abs(expected),
        "actual_to_expected_ratio": actual / expected,
        "component_inventory_identity_max_abs_lbmol": float(
            response["component_inventory_identity_max_abs_lbmol"]
        ),
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-179 Duration-Scaled Response Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Source: immutable DD-178 response and gate evidence",
            "- Provider/model/solver calls permitted: `0 / 0 / 0`",
            "- DD-178 formal classification may change: `False`",
            "- Actual/expected relative response error: `<1e-6`",
            "- Coarse/refined total-response difference: `<1e-9 lbmol`",
            "",
            "Commit before the one static execution. This contract cannot "
            "regenerate a root or trajectory endpoint.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-179 Duration-Scaled Response Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Coarse relative response error: "
            f"`{payload['metrics']['coarse']['relative_response_error']:.6e}`",
            f"- Refined relative response error: "
            f"`{payload['metrics']['refined']['relative_response_error']:.6e}`",
            f"- Coarse/refined total difference: "
            f"`{payload['metrics']['cross_grid_total_difference_lbmol']:.6e} lbmol`",
            "- Provider/model/solver calls: `0 / 0 / 0`",
            "- DD-178 remains formally failed: `True`",
            "",
        )
    )


def prepare(
    dd178_contract_path: Path,
    dd178_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source_contract = _load(dd178_contract_path)
    source_result = _load(dd178_result_path)
    _validate_source(source_result)
    inherited_ceiling = float(
        source_contract["limits"]["maximum_total_inventory_response_lbmol"]
    )
    expected = min(
        float(item["expected_total_inventory_change_lbmol"])
        for item in source_result["response"].values()
    )
    if expected <= inherited_ceiling:
        raise RuntimeError("DD-178 expected response does not exceed inherited ceiling")
    payload: dict[str, Any] = {
        "schema_id": "dd179-core-v3-duration-scaled-response-contract-v1",
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd178_contract_path": str(dd178_contract_path).replace("\\", "/"),
        "dd178_contract_sha256": _sha(ROOT / dd178_contract_path),
        "dd178_result_path": str(dd178_result_path).replace("\\", "/"),
        "dd178_result_sha256": _sha(ROOT / dd178_result_path),
        "duration_seconds": source_contract["paths"]["duration_seconds"],
        "inherited_absolute_ceiling_lbmol": inherited_ceiling,
        "response": source_result["response"],
        "response_gates": source_result["response_gates"],
        "campaign_gates": source_result["campaign_gates"],
        "limits": {
            "relative_actual_expected_response_error": 1.0e-6,
            "cross_grid_total_response_difference_lbmol": 1.0e-9,
            "global_component_inventory_identity_lbmol": 1.0e-6,
        },
        "prospective_policy": {
            "response_scale": "integrated_external_flow_over_contract_duration",
            "absolute_duration_independent_response_ceiling": False,
            "positive_and_monotone_required": True,
        },
        "interpretation_rules": [
            "DD-178 remains formally failed regardless of adjudication",
            "a pass may authorize only a separately frozen longer trajectory contract",
            "no model, provider, solver, or endpoint regeneration is permitted",
        ],
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "model_calls_attempted": False,
        "provider_calls_attempted": False,
        "solver_calls_attempted": False,
        "endpoint_regeneration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-179 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-179 contract payload hash mismatch")
    for source_key, hash_key in (
        ("dd178_contract_path", "dd178_contract_sha256"),
        ("dd178_result_path", "dd178_result_sha256"),
    ):
        if _sha(ROOT / payload[source_key]) != payload[hash_key]:
            raise RuntimeError(f"DD-179 source changed: {payload[source_key]}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-179 implementation changed: {path}")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-179 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-179 contract is not committed")


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    source_result = _load(Path(payload["dd178_result_path"]))
    _validate_source(source_result)
    coarse = _response_metrics(payload["response"]["coarse"])
    refined = _response_metrics(payload["response"]["refined"])
    cross_grid = abs(
        coarse["actual_total_inventory_change_lbmol"]
        - refined["actual_total_inventory_change_lbmol"]
    )
    limits = payload["limits"]
    gates = {
        "coarse_actual_expected": coarse["relative_response_error"]
        < limits["relative_actual_expected_response_error"],
        "refined_actual_expected": refined["relative_response_error"]
        < limits["relative_actual_expected_response_error"],
        "cross_grid_total": cross_grid
        < limits["cross_grid_total_response_difference_lbmol"],
        "coarse_component_identity": coarse[
            "component_inventory_identity_max_abs_lbmol"
        ] < limits["global_component_inventory_identity_lbmol"],
        "refined_component_identity": refined[
            "component_inventory_identity_max_abs_lbmol"
        ] < limits["global_component_inventory_identity_lbmol"],
        "coarse_positive_monotone": all(
            (
                source_result["response_gates"]["coarse"]["positive"],
                source_result["response_gates"]["coarse"]["monotone"],
            )
        ),
        "refined_positive_monotone": all(
            (
                source_result["response_gates"]["refined"]["positive"],
                source_result["response_gates"]["refined"]["monotone"],
            )
        ),
        "all_nonresponse_campaign_gates": all(
            passed
            for name, passed in source_result["campaign_gates"].items()
            if name != "response"
        ),
        "dd178_formal_failure_preserved": source_result["pass_gate"] is False,
        "zero_live_calls": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": "dd179-core-v3-duration-scaled-response-result-v1",
        "classification": (
            "duration_scaled_response_adjudication_passed"
            if passed
            else "duration_scaled_response_adjudication_failed"
        ),
        "decision": (
            "authorize_one_frozen_longer_open_loop_trajectory_contract"
            if passed
            else "stop_physical_trajectory_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "source_dd178_classification": source_result["classification"],
        "source_dd178_formal_failure_preserved": True,
        "metrics": {
            "coarse": coarse,
            "refined": refined,
            "cross_grid_total_difference_lbmol": cross_grid,
        },
        "limits": limits,
        "gates": gates,
        "pass_gate": passed,
        "wall_clock_sec": float(time.perf_counter() - started),
        "model_call_count": 0,
        "provider_call_count": 0,
        "solver_call_count": 0,
        "endpoint_regeneration_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _result_markdown(result), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd178-contract", type=Path, default=DD178_CONTRACT)
    parser.add_argument("--dd178-result", type=Path, default=DD178_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd178_contract, args.dd178_result, args.contract)
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "campaign_executed": output["campaign_executed"],
                },
                indent=2,
            )
        )
    else:
        output = execute(args.contract, args.result)
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
