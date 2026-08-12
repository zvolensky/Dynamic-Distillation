#!/usr/bin/env python
"""Prepare or execute DD-174's zero-call DD-173 endpoint adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DD173_CONTRACT = Path(
    "logs/dd173_core_v3_seven_volume_moving_step_contract_20260812.json"
)
DD173_RESULT = Path("logs/dd173_core_v3_seven_volume_moving_step_20260812.json")
CONTRACT = Path(
    "logs/dd174_core_v3_moving_step_physical_adjudication_contract_20260812.json"
)
RESULT = Path("logs/dd174_core_v3_moving_step_physical_adjudication_20260812")
IMPLEMENTATION = (
    "tools/adjudicate_core_v3_seven_volume_moving_step.py",
    "tests/test_core_v3_seven_volume_moving_step_adjudication.py",
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


def _physical_metrics(
    initial_inventory: Any,
    full_inventory: Any,
    refined_inventory: Any,
) -> dict[str, Any]:
    initial = np.asarray(initial_inventory, dtype=float)
    full = np.asarray(full_inventory, dtype=float)
    refined = np.asarray(refined_inventory, dtype=float)
    if (
        initial.ndim != 2
        or full.shape != initial.shape
        or refined.shape != initial.shape
        or np.any(~np.isfinite(initial))
        or np.any(~np.isfinite(full))
        or np.any(~np.isfinite(refined))
        or np.any(initial <= 0.0)
    ):
        raise ValueError("adjudication inventories are invalid")
    difference = full - refined
    absolute = np.abs(difference)
    initial_floor = np.maximum(initial, 1.0)
    volume_scale = np.sum(initial, axis=1)[:, None]
    worst_absolute = np.unravel_index(int(np.argmax(absolute)), absolute.shape)
    state_relative = absolute / initial_floor
    worst_state = np.unravel_index(
        int(np.argmax(state_relative)), state_relative.shape
    )
    volume_relative = absolute / volume_scale
    worst_volume = np.unravel_index(
        int(np.argmax(volume_relative)), volume_relative.shape
    )
    return {
        "maximum_absolute_component_difference_lbmol": float(
            absolute[worst_absolute]
        ),
        "maximum_absolute_component_index": [int(value) for value in worst_absolute],
        "maximum_state_relative_difference_with_1_lbmol_floor": float(
            state_relative[worst_state]
        ),
        "maximum_state_relative_index": [int(value) for value in worst_state],
        "maximum_volume_holdup_relative_component_difference": float(
            volume_relative[worst_volume]
        ),
        "maximum_volume_relative_index": [int(value) for value in worst_volume],
        "component_difference_l1_lbmol": float(np.sum(absolute)),
        "signed_total_inventory_difference_lbmol": float(np.sum(difference)),
        "absolute_signed_total_inventory_difference_lbmol": float(
            abs(np.sum(difference))
        ),
        "difference_matrix_lbmol": difference.tolist(),
    }


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-174 Moving-Step Physical-Scale Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Source: immutable DD-173 full and refined endpoints",
            "- Provider/model/solver calls permitted: `0 / 0 / 0`",
            "- DD-173 formal classification may change: `False`",
            "",
            "The adjudication uses predeclared absolute, state-floor, and "
            "volume-holdup scales. Commit this contract before its one static "
            "execution.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["metrics"]
    return "\n".join(
        (
            "# DD-174 Moving-Step Physical-Scale Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Maximum absolute component difference: "
            f"`{metrics['maximum_absolute_component_difference_lbmol']:.6e} lbmol`",
            f"- Maximum state-relative difference with floor: "
            f"`{metrics['maximum_state_relative_difference_with_1_lbmol_floor']:.6e}`",
            f"- Maximum volume-scale relative difference: "
            f"`{metrics['maximum_volume_holdup_relative_component_difference']:.6e}`",
            f"- Component-difference L1: "
            f"`{metrics['component_difference_l1_lbmol']:.6e} lbmol`",
            f"- Signed total difference: "
            f"`{metrics['signed_total_inventory_difference_lbmol']:.6e} lbmol`",
            "- Provider/model/solver calls: `0 / 0 / 0`",
            "- DD-173 remains formally failed: `True`",
            "",
        )
    )


def _validate_source(result: Mapping[str, Any]) -> None:
    if result.get("pass_gate") is not False:
        raise RuntimeError("DD-174 requires DD-173's formal failed result")
    if result.get("decision") != "stop_before_trajectory":
        raise RuntimeError("DD-173 stop decision changed")
    if result["campaign_gates"] != {
        "steps": True,
        "response": True,
        "refinement": False,
        "provider": True,
        "provider_calls": True,
        "wall_clock": True,
    }:
        raise RuntimeError("DD-173 campaign failure pattern changed")
    failed_refinement = [
        name for name, passed in result["refinement_gates"].items() if not passed
    ]
    if failed_refinement != ["inventory"]:
        raise RuntimeError("DD-173 did not fail only inventory refinement")
    if any(
        not all(gates.values()) for gates in result["step_gates"].values()
    ) or any(
        not all(gates.values()) for gates in result["response_gates"].values()
    ):
        raise RuntimeError("DD-173 has another failed step or response gate")


def prepare(
    dd173_contract_path: Path,
    dd173_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source_contract = _load(dd173_contract_path)
    source_result = _load(dd173_result_path)
    _validate_source(source_result)
    payload: dict[str, Any] = {
        "schema_id": "dd174-core-v3-moving-step-physical-adjudication-contract-v1",
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd173_contract_path": str(dd173_contract_path).replace("\\", "/"),
        "dd173_contract_sha256": _sha(ROOT / dd173_contract_path),
        "dd173_result_path": str(dd173_result_path).replace("\\", "/"),
        "dd173_result_sha256": _sha(ROOT / dd173_result_path),
        "component_names": source_contract["disturbed_source_mapping"][
            "component_names"
        ],
        "volume_roles": source_contract["disturbed_source_mapping"]["roles"],
        "initial_inventory_lbmol": source_contract[
            "accepted_root_inventory_lbmol"
        ],
        "full_inventory_lbmol": source_result["steps"]["full"][
            "inventory_lbmol"
        ],
        "refined_inventory_lbmol": source_result["steps"]["half2"][
            "inventory_lbmol"
        ],
        "inherited_dd173_refinement": source_result["refinement"],
        "inherited_dd173_response": source_result["response"],
        "limits": {
            "maximum_absolute_component_difference_lbmol": 1.0e-4,
            "maximum_state_relative_difference_with_1_lbmol_floor": 1.0e-5,
            "maximum_volume_holdup_relative_component_difference": 1.0e-6,
            "component_difference_l1_lbmol": 2.0e-4,
            "absolute_signed_total_inventory_difference_lbmol": 1.0e-9,
            "inherited_total_inventory_refinement_lbmol": 1.0e-6,
            "inherited_global_component_identity_lbmol": 1.0e-6,
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "interpretation_rules": [
            "DD-173 remains formally failed regardless of adjudication",
            "a pass may authorize only a smaller-timestep moving proof contract",
            "a fail stops the moving dynamic path",
            "no model, provider, solver, or endpoint regeneration is permitted",
        ],
        "model_calls_attempted": False,
        "provider_calls_attempted": False,
        "solver_calls_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-174 contract already exists")
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
        raise RuntimeError("DD-174 contract payload hash mismatch")
    if _sha(ROOT / payload["dd173_contract_path"]) != payload[
        "dd173_contract_sha256"
    ]:
        raise RuntimeError("DD-173 source contract changed")
    if _sha(ROOT / payload["dd173_result_path"]) != payload[
        "dd173_result_sha256"
    ]:
        raise RuntimeError("DD-173 source result changed")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-174 implementation changed: {path}")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-174 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-174 contract is not committed")


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    source_result = _load(Path(payload["dd173_result_path"]))
    _validate_source(source_result)
    metrics = _physical_metrics(
        payload["initial_inventory_lbmol"],
        payload["full_inventory_lbmol"],
        payload["refined_inventory_lbmol"],
    )
    limits = payload["limits"]
    inherited_response = payload["inherited_dd173_response"]
    gates = {
        "absolute_component": metrics[
            "maximum_absolute_component_difference_lbmol"
        ]
        < limits["maximum_absolute_component_difference_lbmol"],
        "state_relative_with_floor": metrics[
            "maximum_state_relative_difference_with_1_lbmol_floor"
        ]
        < limits["maximum_state_relative_difference_with_1_lbmol_floor"],
        "volume_holdup_relative": metrics[
            "maximum_volume_holdup_relative_component_difference"
        ]
        < limits["maximum_volume_holdup_relative_component_difference"],
        "component_l1": metrics["component_difference_l1_lbmol"]
        < limits["component_difference_l1_lbmol"],
        "signed_total": metrics[
            "absolute_signed_total_inventory_difference_lbmol"
        ]
        < limits["absolute_signed_total_inventory_difference_lbmol"],
        "inherited_total_response_refinement": abs(
            inherited_response["full"]["total_inventory_change_lbmol"]
            - inherited_response["refined"]["total_inventory_change_lbmol"]
        )
        < limits["inherited_total_inventory_refinement_lbmol"],
        "inherited_global_component_identity": max(
            inherited_response["full"][
                "component_inventory_identity_max_abs_lbmol"
            ],
            inherited_response["refined"][
                "component_inventory_identity_max_abs_lbmol"
            ],
        )
        < limits["inherited_global_component_identity_lbmol"],
        "dd173_formal_failure_preserved": source_result["pass_gate"] is False,
        "zero_live_calls": True,
    }
    passed = all(gates.values())
    result = {
        "schema_id": "dd174-core-v3-moving-step-physical-adjudication-result-v1",
        "classification": (
            "moving_step_physical_scale_adjudication_passed"
            if passed
            else "moving_step_physical_scale_adjudication_failed"
        ),
        "decision": (
            "authorize_one_frozen_smaller_timestep_moving_proof_contract"
            if passed
            else "stop_moving_dynamic_path"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "source_dd173_classification": source_result["classification"],
        "source_dd173_formal_failure_preserved": True,
        "metrics": metrics,
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
    parser.add_argument("--dd173-contract", type=Path, default=DD173_CONTRACT)
    parser.add_argument("--dd173-result", type=Path, default=DD173_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd173_contract, args.dd173_result, args.contract)
        print(json.dumps({
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "campaign_executed": output["campaign_executed"],
        }, indent=2))
    else:
        output = execute(args.contract, args.result)
        print(json.dumps({
            "classification": output["classification"],
            "pass_gate": output["pass_gate"],
            "decision": output["decision"],
        }, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
