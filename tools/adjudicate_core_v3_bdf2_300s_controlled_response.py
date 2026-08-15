#!/usr/bin/env python
"""Prepare or execute DD-219's zero-call DD-218 response adjudication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_terminal_inventory_control_bdf2_30s_production as dd209  # noqa: E402


SCHEMA = "dd219-core-v3-bdf2-300s-controlled-response-contract-v1"
RESULT_SCHEMA = "dd219-core-v3-bdf2-300s-controlled-response-result-v1"
DD218_RESULT = Path("logs/dd218_core_v3_bdf2_300s_dynamic_production_20260815.json")
CONTRACT = Path(
    "logs/dd219_core_v3_bdf2_300s_controlled_response_contract_20260815.json"
)
RESULT = Path("logs/dd219_core_v3_bdf2_300s_controlled_response_20260815")
CONTRACT_DOC = Path(
    "docs/dd_219_core_v3_bdf2_300s_controlled_response_contract_20260815.md"
)
RESULT_DOC = Path("docs/dd_219_core_v3_bdf2_300s_controlled_response_20260815.md")
IMPLEMENTATION = (
    "tools/adjudicate_core_v3_bdf2_300s_controlled_response.py",
    "tests/test_core_v3_bdf2_300s_controlled_response.py",
)


def _total_inventory(step: Mapping[str, Any]) -> float:
    return float(np.asarray(step["inventory_lbmol"], dtype=float).sum())


def _analyze(
    samples: Sequence[Mapping[str, Any]], limits: Mapping[str, Any]
) -> dict[str, Any]:
    if not samples:
        raise ValueError("DD-219 requires sampled DD-218 states")
    times = np.asarray([float(item["time_seconds"]) for item in samples])
    inventory = np.asarray([_total_inventory(item) for item in samples])
    bottoms = np.asarray([float(item["bottoms_lbmolph"]) for item in samples])
    distillate = np.asarray([float(item["distillate_lbmolph"]) for item in samples])
    levels = np.asarray([item["level_fraction"] for item in samples], dtype=float)
    peak_index = int(np.argmax(inventory))
    decline_count = 0
    for index in range(len(inventory) - 1, 0, -1):
        if inventory[index] < inventory[index - 1]:
            decline_count += 1
        else:
            break
    tolerance = float(limits["monotonic_tolerance"])
    metrics = {
        "sample_count": len(samples),
        "first_time_seconds": float(times[0]),
        "final_time_seconds": float(times[-1]),
        "inventory_initial_lbmol": float(inventory[0]),
        "inventory_peak_lbmol": float(inventory[peak_index]),
        "inventory_peak_time_seconds": float(times[peak_index]),
        "inventory_final_lbmol": float(inventory[-1]),
        "inventory_excursion_lbmol": float(inventory.max() - inventory.min()),
        "peak_minus_final_lbmol": float(inventory[peak_index] - inventory[-1]),
        "consecutive_final_declines": decline_count,
        "bottoms_initial_lbmolph": float(bottoms[0]),
        "bottoms_final_lbmolph": float(bottoms[-1]),
        "distillate_initial_lbmolph": float(distillate[0]),
        "distillate_final_lbmolph": float(distillate[-1]),
        "minimum_level_fraction": float(levels.min()),
        "maximum_level_fraction": float(levels.max()),
    }
    gates = {
        "sample_count": len(samples) >= int(limits["minimum_sample_count"]),
        "ordered_times": bool(np.all(np.diff(times) > 0.0)),
        "complete_horizon": abs(times[-1] - limits["duration_seconds"])
        <= limits["time_tolerance_seconds"],
        "bounded_inventory": metrics["inventory_excursion_lbmol"]
        <= limits["maximum_inventory_excursion_lbmol"],
        "late_peak": limits["minimum_peak_time_seconds"]
        <= metrics["inventory_peak_time_seconds"]
        <= limits["maximum_peak_time_seconds"],
        "corrective_decline": decline_count
        >= int(limits["minimum_consecutive_final_declines"])
        and metrics["peak_minus_final_lbmol"]
        >= limits["minimum_peak_minus_final_lbmol"],
        "bottoms_action": bool(np.all(np.diff(bottoms) >= -tolerance)),
        "distillate_action": bool(np.all(np.diff(distillate) <= tolerance)),
        "physical_levels": bool(
            np.all(levels > limits["minimum_level_fraction"])
            and np.all(levels < limits["maximum_level_fraction"])
        ),
        "finite": bool(
            np.all(np.isfinite(times))
            and np.all(np.isfinite(inventory))
            and np.all(np.isfinite(bottoms))
            and np.all(np.isfinite(distillate))
            and np.all(np.isfinite(levels))
        ),
    }
    return {"metrics": metrics, "gates": gates, "pass_gate": all(gates.values())}


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    limits = payload["limits"]
    return "\n".join(
        (
            "# DD-219 Controlled-Response Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Source: immutable DD-218 result; zero live calls",
            f"- Inventory excursion limit: `{limits['maximum_inventory_excursion_lbmol']} lbmol`",
            f"- Peak window: `{limits['minimum_peak_time_seconds']}-{limits['maximum_peak_time_seconds']} s`",
            f"- Required final declines / peak-to-final correction: `{limits['minimum_consecutive_final_declines']}` / `{limits['minimum_peak_minus_final_lbmol']} lbmol`",
            "- Bottoms action nondecreasing; distillate action nonincreasing; levels physical",
            "- DD-218 formal classification remains unchanged",
            "",
            "Commit this immutable contract before its one execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["response_assessment"]["metrics"]
    return "\n".join(
        (
            "# DD-219 Controlled-Response Adjudication Result",
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
    source = dd209._load(DD218_RESULT)
    failed = [name for name, passed in source["campaign_gates"].items() if not passed]
    if source["completed_roots"] != 1200 or failed != ["response"]:
        raise RuntimeError("DD-219 requires DD-218's response-only formal failure")
    payload = {
        "schema_id": SCHEMA,
        "result_schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-219",
        "preparation_base_commit": dd209._git("rev-parse", "HEAD"),
        "source": {
            "path": str(DD218_RESULT).replace("\\", "/"),
            "sha256": dd209._sha(ROOT / DD218_RESULT),
            "formal_classification": source["classification"],
            "formal_failed_gates": failed,
            "completed_roots": source["completed_roots"],
        },
        "limits": {
            "duration_seconds": 300.0,
            "time_tolerance_seconds": 1.0e-12,
            "minimum_sample_count": 61,
            "maximum_inventory_excursion_lbmol": 1.0,
            "minimum_peak_time_seconds": 240.0,
            "maximum_peak_time_seconds": 295.0,
            "minimum_consecutive_final_declines": 4,
            "minimum_peak_minus_final_lbmol": 1.0e-4,
            "monotonic_tolerance": 1.0e-9,
            "minimum_level_fraction": 0.0,
            "maximum_level_fraction": 1.0,
            "global_inventory_identity_limit_lbmol": 1.0e-6,
            "global_inventory_relative_limit": 1.0e-6,
        },
        "implementation_sha256": {
            path: dd209._sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "DD-218 has any failed gate other than legacy monotonic response",
            "global inventory recurrence or endpoint root evidence fails",
            "sampled inventory is unbounded or lacks sustained controller correction",
            "sampled terminal actions or levels are nonphysical",
            "any model, provider, solver, timestep, endpoint regeneration, or rerun occurs",
        ],
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
        raise RuntimeError("DD-219 contract already exists")
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
        raise RuntimeError("DD-219 contract payload hash mismatch")
    if dd209._sha(ROOT / DD218_RESULT) != payload["source"]["sha256"]:
        raise RuntimeError("DD-219 source changed")
    for path, expected in payload["implementation_sha256"].items():
        if dd209._sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-219 implementation changed: {path}")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-219 result exists; rerun prohibited")
    dd209._git("ls-files", "--error-unmatch", str(contract_path))
    source = dd209._load(DD218_RESULT)
    limits = payload["limits"]
    response = source["response_summary"]
    response_assessment = _analyze(source["sampled_steps"], limits)
    nonresponse_gates = all(
        passed
        for name, passed in source["campaign_gates"].items()
        if name != "response"
    )
    endpoint_gates = all(source["endpoint"]["gates"].values())
    gates = {
        "source_response_only_failure": [
            name for name, passed in source["campaign_gates"].items() if not passed
        ]
        == ["response"],
        "all_roots_complete": source["completed_roots"]
        == source["requested_roots"]
        == 1200,
        "nonresponse_campaign_gates": nonresponse_gates,
        "endpoint_root_gates": endpoint_gates,
        "inventory_identity": response["component_inventory_identity_max_abs_lbmol"]
        < limits["global_inventory_identity_limit_lbmol"],
        "inventory_relative": response["total_inventory_relative_error"]
        < limits["global_inventory_relative_limit"],
        "controlled_response": response_assessment["pass_gate"],
        "zero_live_calls": payload["model_calls"]
        == payload["provider_calls"]
        == payload["solver_calls"]
        == payload["trajectory_calls"]
        == 0,
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "campaign_id": "DD-219",
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
        "response_assessment": response_assessment,
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
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "source": output["source"],
                    "limits": output["limits"],
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
