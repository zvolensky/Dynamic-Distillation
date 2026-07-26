#!/usr/bin/env python
"""Prepare or execute the frozen DD-100 Core V3 longer open-loop gate."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.short_trajectory_v1 import (
    run_short_trajectory,
    scale_feed_throughput,
)
from tools import run_core_v3_implicit_step as dd097
from tools import run_core_v3_short_open_loop as dd098


SCHEMA_ID = "dd100-core-v3-longer-open-loop-contract-v1"
RESULT_SCHEMA_ID = "dd100-core-v3-longer-open-loop-result-v1"
DEFAULT_DD099_CONTRACT = Path(
    "logs/dd099_core_v3_performance_contract_20260725.json"
)
DEFAULT_DD099_RESULT = Path("logs/dd099_core_v3_performance_20260725.json")
DEFAULT_CONTRACT = Path(
    "logs/dd100_core_v3_longer_open_loop_contract_20260725.json"
)
DEFAULT_RESULT = Path("logs/dd100_core_v3_longer_open_loop_20260725.json")

FEED_FACTOR = 1.001
ROOT_DURATION_SECONDS = 5.0
PERTURBED_DURATION_SECONDS = 10.0
ROOT_STEP_SECONDS = 1.0
PERTURBED_STEP_SECONDS = (1.0, 0.5)
LIMITS = {
    "scaled_residual": 1.0e-8,
    "condition": 1.0e8,
    "bubble_residual": 1.0e-10,
    "component_conservation": 1.0e-8,
    "energy_conservation": 1.0e-8,
    "root_component_rate_lbmolph": 1.0e-4,
    "root_relative_inventory_drift": 1.0e-8,
    "root_algebraic_drift": 1.0e-6,
    "motion_component_rate_lbmolph": 1.0e-3,
    "motion_total_inventory_lbmol": 1.0e-4,
    "expected_accumulation_relative_error": 1.0e-6,
    "refinement_inventory": 1.0e-4,
    "refinement_algebraic": 1.0e-3,
    "refinement_temperature_F": 1.0e-2,
    "refinement_accumulation": 1.0e-6,
    "maximum_calls_per_endpoint": 6000.0,
    "maximum_campaign_wall_clock_sec": 180.0,
}

IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/short_trajectory_v1.py",
    "tests/test_core_v3_colored_jacobian_v1.py",
    "tests/test_core_v3_implicit_step_v1.py",
    "tests/test_core_v3_short_trajectory_v1.py",
    "tools/run_core_v3_longer_open_loop.py",
    "docs/dd_100_core_v3_longer_open_loop_contract_20260725.md",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-100 Frozen Core V3 Longer Open-Loop Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Root hold: `5.0 s` at `dt=1.0 s`",
            "- Feed step: `+0.1%`, `10.0 s` at `dt=1.0 s` and `0.5 s`",
            "- Jacobian: frozen 17-color central difference",
            "- Live property evaluation during preparation: `False`",
            "- Trajectory during preparation: `False`",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-100 Core V3 Longer Open-Loop Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Root-hold pass: `{payload['root_hold']['pass']}`",
            f"- Feed-step passes: `{payload['perturbed'][0]['pass']}`, "
            f"`{payload['perturbed'][1]['pass']}`",
            f"- Refinement pass: `{payload['refinement']['pass']}`",
            f"- Provider pass: `{payload['provider_provenance']['pass']}`",
            f"- Calls per endpoint: `{payload['calls_per_endpoint']:.1f}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "",
        )
    )


def prepare(
    dd099_contract_path: Path,
    dd099_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd099_contract_path)
    result = _load(dd099_result_path)
    if (
        not result["pass"]
        or result["decision"]
        != "authorize_one_modest_longer_open_loop_contract"
    ):
        raise RuntimeError("DD-100 requires the accepted DD-099 result")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd099_contract_path": str(dd099_contract_path).replace("\\", "/"),
        "dd099_contract_sha256": _sha256(ROOT / dd099_contract_path),
        "dd099_result_path": str(dd099_result_path).replace("\\", "/"),
        "dd099_result_sha256": _sha256(ROOT / dd099_result_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": {**source["solver"], "jacobian_mode": "colored"},
        "feed_factor": FEED_FACTOR,
        "root_duration_seconds": ROOT_DURATION_SECONDS,
        "perturbed_duration_seconds": PERTURBED_DURATION_SECONDS,
        "root_step_seconds": ROOT_STEP_SECONDS,
        "perturbed_step_seconds": list(PERTURBED_STEP_SECONDS),
        "requested_endpoint_count": 35,
        "limits": LIMITS,
        "required_step_rank": 38,
        "hard_stops": [
            "any endpoint fails or requires retry or substepping",
            "root hold develops material motion",
            "feed accumulation is nonmonotone or violates the external balance",
            "refined endpoints exceed the frozen difference limits",
            "rank, condition, physicality, conservation, or provider gate fails",
            "any nested bubble reconstruction occurs",
            "provider calls or wall time exceed the frozen efficiency limits",
            "any post-result tolerance, step, forcing, solver, or equation change",
        ],
        "implementation_sha256": {
            path: _sha256(ROOT / path) for path in IMPLEMENTATION_PATHS
        },
        "live_property_evaluation_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-100 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha256(ROOT / path) != expected:
            raise RuntimeError(f"DD-100 implementation changed: {path}")
    if _sha256(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-100 workbook changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-100 result already exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-100 contract is not committed")


def _provider_summary(audit: ProviderCallAudit) -> dict[str, Any]:
    report = dd097._provider_summary(audit)
    report["nested_bubble_calls"] = sum(
        record.quantity == "bubble_temperature_and_incipient_vapor"
        for record in audit.records
    )
    return report


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    source = payload["source_mapping"]
    base_spec = dd097._spec(
        source, float(payload["operating_spec"]["feed_enthalpy_BTUph"])
    )
    perturbed_spec = scale_feed_throughput(base_spec, float(payload["feed_factor"]))
    reference = dd097._reference(payload["reference"])
    state = dd097._state(payload["accepted_root_state"])
    inventory = inventory_from_state(state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-100 inventory mapping changed")
    contract = build_dynamic_dae_contract(base_spec.component_names)
    provider = dd097._provider(Path(payload["workbook"]), payload["property_package"])
    settings = replace(dd097._settings(payload), jacobian_mode="colored")
    audit = ProviderCallAudit()
    started = time.perf_counter()
    root = run_short_trajectory(
        contract,
        base_spec,
        reference,
        state,
        provider,
        audit,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=float(payload["root_step_seconds"]),
        duration_seconds=float(payload["root_duration_seconds"]),
        settings=settings,
        name="dd100_root_hold",
    )
    perturbed = [
        run_short_trajectory(
            contract,
            perturbed_spec,
            reference,
            state,
            provider,
            audit,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step_seconds=float(step),
            duration_seconds=float(payload["perturbed_duration_seconds"]),
            settings=settings,
            name=f"dd100_feed_step_{step:g}s",
        )
        for step in payload["perturbed_step_seconds"]
    ]
    wall_clock = float(time.perf_counter() - started)
    limits = payload["limits"]
    max_nfev = int(payload["solver"]["max_nfev"])
    required_rank = int(payload["required_step_rank"])
    root_report = dd098._trajectory_report(
        root, base_spec, inventory, limits, max_nfev, required_rank
    )
    perturbed_reports = [
        dd098._trajectory_report(
            trajectory,
            perturbed_spec,
            inventory,
            limits,
            max_nfev,
            required_rank,
        )
        for trajectory in perturbed
    ]
    root_gates = {
        "completed": root_report["completed"] and root_report["per_step_pass"],
        "component_rate": root_report["maximum_component_rate_abs_lbmolph"]
        < float(limits["root_component_rate_lbmolph"]),
        "inventory_drift": root_report["relative_inventory_drift_from_initial"]
        < float(limits["root_relative_inventory_drift"]),
        "algebraic_drift": root_report["algebraic_drift_from_initial"]
        < float(limits["root_algebraic_drift"]),
    }
    root_report["gates"] = root_gates
    root_report["pass"] = all(root_gates.values())
    expected_accumulation = float(
        (
            np.sum(perturbed_spec.feed_component_lbmolph)
            - state.distillate_lbmolph
            - state.bottoms_lbmolph
        )
        * float(payload["perturbed_duration_seconds"])
        / 3600.0
    )
    for report in perturbed_reports:
        error = abs(
            float(report["total_inventory_accumulation_lbmol"])
            - expected_accumulation
        ) / max(abs(expected_accumulation), 1.0e-15)
        gates = {
            "completed": report["completed"] and report["per_step_pass"],
            "monotone_inventory": report["total_inventory_strictly_increasing"],
            "nonzero_rate": report["maximum_component_rate_abs_lbmolph"]
            > float(limits["motion_component_rate_lbmolph"]),
            "nonzero_accumulation": report["total_inventory_accumulation_lbmol"]
            > float(limits["motion_total_inventory_lbmol"]),
            "expected_accumulation": error
            < float(limits["expected_accumulation_relative_error"]),
        }
        report["expected_accumulation_relative_error"] = error
        report["gates"] = gates
        report["pass"] = all(gates.values())
    first = perturbed[0].endpoint_evaluation
    second = perturbed[1].endpoint_evaluation
    refinement = {
        "relative_inventory_difference": float(
            np.max(
                np.abs(
                    first.endpoint_inventory_lbmol - second.endpoint_inventory_lbmol
                )
                / inventory
            )
        ),
        "algebraic_coordinate_difference": float(
            np.max(
                np.abs(first.algebraic_coordinates - second.algebraic_coordinates)
            )
        ),
        "temperature_difference_F": float(
            np.max(
                np.abs(
                    first.dynamic_evaluation.physical_state.temperature_F
                    - second.dynamic_evaluation.physical_state.temperature_F
                )
            )
        ),
        "accumulation_relative_difference": float(
            abs(
                perturbed_reports[0]["total_inventory_accumulation_lbmol"]
                - perturbed_reports[1]["total_inventory_accumulation_lbmol"]
            )
            / max(abs(expected_accumulation), 1.0e-15)
        ),
    }
    refinement_gates = {
        "inventory": refinement["relative_inventory_difference"]
        < float(limits["refinement_inventory"]),
        "algebraic": refinement["algebraic_coordinate_difference"]
        < float(limits["refinement_algebraic"]),
        "temperature": refinement["temperature_difference_F"]
        < float(limits["refinement_temperature_F"]),
        "accumulation": refinement["accumulation_relative_difference"]
        < float(limits["refinement_accumulation"]),
    }
    refinement["gates"] = refinement_gates
    refinement["pass"] = all(refinement_gates.values())
    provider_report = _provider_summary(audit)
    completed_endpoints = root.completed_steps + sum(
        trajectory.completed_steps for trajectory in perturbed
    )
    calls_per_endpoint = float(provider_report["total_calls"]) / max(
        completed_endpoints, 1
    )
    efficiency_gates = {
        "endpoint_count": completed_endpoints
        == int(payload["requested_endpoint_count"]),
        "no_nested_bubble": int(provider_report["nested_bubble_calls"]) == 0,
        "calls_per_endpoint": calls_per_endpoint
        < float(limits["maximum_calls_per_endpoint"]),
        "wall_clock": wall_clock
        < float(limits["maximum_campaign_wall_clock_sec"]),
    }
    passed = (
        root_report["pass"]
        and all(report["pass"] for report in perturbed_reports)
        and refinement["pass"]
        and provider_report["pass"]
        and all(efficiency_gates.values())
    )
    result = {
        "schema_id": RESULT_SCHEMA_ID,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "dd100_longer_open_loop_passed"
            if passed
            else "dd100_longer_open_loop_failed"
        ),
        "decision": (
            "authorize_next_dynamic_scope_decision"
            if passed
            else "stop_longer_open_loop_path"
        ),
        "wall_clock_sec": wall_clock,
        "completed_endpoint_count": completed_endpoints,
        "expected_total_accumulation_lbmol": expected_accumulation,
        "root_hold": root_report,
        "perturbed": perturbed_reports,
        "refinement": refinement,
        "provider_provenance": provider_report,
        "calls_per_endpoint": calls_per_endpoint,
        "efficiency_gates": efficiency_gates,
        "pass": passed,
        "campaign_executed_once": True,
        "trajectory_attempted": True,
        "controller_attempted": False,
        "pressure_dynamics_attempted": False,
        "vapor_holdup_attempted": False,
    }
    destination = ROOT / result_path
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _result_markdown(result), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd099-contract", type=Path, default=DEFAULT_DD099_CONTRACT)
    parser.add_argument("--dd099-result", type=Path, default=DEFAULT_DD099_RESULT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    output = (
        prepare(args.dd099_contract, args.dd099_result, args.contract)
        if args.prepare
        else execute(args.contract, args.result)
    )
    print(json.dumps(output, indent=2))
