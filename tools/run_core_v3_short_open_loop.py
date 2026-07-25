#!/usr/bin/env python
"""Prepare or execute the frozen DD-098 Core V3 short open-loop campaign."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
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
from dynamic_distillation.core_v3.implicit_step_v1 import BackwardEulerEvaluation
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.short_trajectory_v1 import (
    ShortTrajectoryResult,
    run_short_trajectory,
    scale_feed_throughput,
)
from tools import run_core_v3_implicit_step as dd097


SCHEMA_ID = "dd098-core-v3-short-open-loop-contract-v1"
RESULT_SCHEMA_ID = "dd098-core-v3-short-open-loop-result-v1"
DEFAULT_DD097_CONTRACT = Path(
    "logs/dd097_core_v3_implicit_step_contract_20260725.json"
)
DEFAULT_DD097_RESULT = Path("logs/dd097_core_v3_implicit_step_20260725.json")
DEFAULT_CONTRACT = Path(
    "logs/dd098_core_v3_short_open_loop_contract_20260725.json"
)
DEFAULT_RESULT = Path("logs/dd098_core_v3_short_open_loop_20260725.json")

FEED_FACTOR = 1.001
DURATION_SECONDS = 2.0
ROOT_HOLD_STEP_SECONDS = 1.0
PERTURBED_STEP_SECONDS = (1.0, 0.5)
LIMITS = {
    "scaled_residual": 1.0e-8,
    "condition": 1.0e8,
    "bubble_residual": 1.0e-10,
    "component_conservation": 1.0e-8,
    "energy_conservation": 1.0e-8,
    "root_component_rate_lbmolph": 1.0e-4,
    "root_relative_inventory_drift": 2.0e-9,
    "root_algebraic_drift": 2.0e-7,
    "motion_component_rate_lbmolph": 1.0e-3,
    "motion_total_inventory_lbmol": 1.0e-4,
    "expected_accumulation_relative_error": 1.0e-6,
    "refinement_inventory": 1.0e-5,
    "refinement_algebraic": 1.0e-4,
    "refinement_temperature_F": 1.0e-3,
    "refinement_accumulation": 1.0e-6,
}

IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "src/dynamic_distillation/core_v3/short_trajectory_v1.py",
    "tests/test_core_v3_implicit_step_v1.py",
    "tests/test_core_v3_short_trajectory_v1.py",
    "tools/run_core_v3_implicit_step.py",
    "tools/run_core_v3_short_open_loop.py",
    "docs/dd_098_core_v3_short_open_loop_contract_20260725.md",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [
        [float(value) for value in np.asarray(row, dtype=float).reshape((-1,))]
        for row in np.asarray(values, dtype=float)
    ]


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-098 Frozen Core V3 Short Open-Loop Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Root hold: `2.0 s` at `dt=1.0 s`",
            "- Feed step: `+0.1%`, `2.0 s` at `dt=1.0 s` and `0.5 s`",
            "- Live property evaluation during preparation: `False`",
            "- Trajectory during preparation: `False`",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-098 Core V3 Short Open-Loop Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Root-hold pass: `{payload['root_hold']['pass']}`",
            f"- Perturbed trajectory passes: "
            f"`{payload['perturbed'][0]['pass']}`, "
            f"`{payload['perturbed'][1]['pass']}`",
            f"- Expected accumulation: "
            f"`{payload['expected_total_accumulation_lbmol']:.6e} lbmol`",
            f"- Refinement pass: `{payload['refinement']['pass']}`",
            f"- Provider pass: `{payload['provider_provenance']['pass']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "",
        )
    )


def prepare(
    dd097_contract_path: Path,
    dd097_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    source = _load(dd097_contract_path)
    result = _load(dd097_result_path)
    if (
        not result["pass"]
        or result["decision"]
        != "authorize_short_open_loop_trajectory_contract_only"
    ):
        raise RuntimeError("DD-098 requires the accepted DD-097 result")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd097_contract_path": str(dd097_contract_path).replace("\\", "/"),
        "dd097_contract_sha256": _sha256(ROOT / dd097_contract_path),
        "dd097_result_path": str(dd097_result_path).replace("\\", "/"),
        "dd097_result_sha256": _sha256(ROOT / dd097_result_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "accepted_root_algebraic_coordinates": source[
            "accepted_root_algebraic_coordinates"
        ],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": source["solver"],
        "feed_factor": FEED_FACTOR,
        "duration_seconds": DURATION_SECONDS,
        "root_hold_step_seconds": ROOT_HOLD_STEP_SECONDS,
        "perturbed_step_seconds": list(PERTURBED_STEP_SECONDS),
        "limits": LIMITS,
        "required_step_rank": 38,
        "hard_stops": [
            "any requested trajectory step fails or is retried",
            "any per-step residual, rank, condition, or physical gate fails",
            "root hold develops artificial motion",
            "feed step lacks monotone expected global accumulation",
            "step-refined endpoints disagree above frozen limits",
            "provider ownership or no-fallback gate fails",
        ],
        "implementation_sha256": {
            path: _sha256(ROOT / path) for path in IMPLEMENTATION_PATHS
        },
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_step_attempted": False,
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


def _verify_execution_contract(
    payload: dict[str, Any], contract_path: Path, result_path: Path
) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-098 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha256(ROOT / path) != expected:
            raise RuntimeError(f"DD-098 implementation changed: {path}")
    if _sha256(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-098 workbook changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-098 result already exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-098 contract is not committed")


def _trajectory_report(
    trajectory: ShortTrajectoryResult,
    spec: Any,
    initial_inventory: np.ndarray,
    limits: Mapping[str, float],
    max_nfev: int,
    required_rank: int,
) -> dict[str, Any]:
    previous = np.asarray(initial_inventory, dtype=float)
    step_reports: list[dict[str, Any]] = []
    total_history = [float(np.sum(previous))]
    per_step_gates: list[dict[str, bool]] = []
    for record in trajectory.steps:
        outcome = record.outcome
        if not isinstance(outcome.evaluation, BackwardEulerEvaluation):
            raise TypeError("DD-098 trajectory contains a non-step endpoint")
        report = dd097._step_report(
            outcome, spec, previous, trajectory.step_seconds
        )
        report["index"] = record.index
        report["time_seconds"] = record.time_seconds
        gates = {
            "success": bool(report["success"]) and int(report["nfev"]) <= max_nfev,
            "residual": float(report["residual_inf_norm"])
            < float(limits["scaled_residual"]),
            "rank": int(report["jacobian_rank"]) == required_rank,
            "condition": float(report["jacobian_condition"])
            < float(limits["condition"]),
            "storage_bubble": float(report["maximum_bubble_residual"])
            < float(limits["bubble_residual"]),
            "component_conservation": float(
                report["component_conservation_relative_error"]
            )
            < float(limits["component_conservation"]),
            "energy_conservation": float(
                report["energy_conservation_relative_error"]
            )
            < float(limits["energy_conservation"]),
            "physical": bool(report["physical_pass"]),
        }
        step_reports.append(report)
        per_step_gates.append(gates)
        previous = outcome.evaluation.endpoint_inventory_lbmol
        total_history.append(float(np.sum(previous)))
    if not trajectory.steps:
        endpoint_inventory = initial_inventory.copy()
        endpoint_algebraic = trajectory.initial_algebraic_coordinates.copy()
        endpoint_temperature = np.asarray([], dtype=float)
    else:
        endpoint = trajectory.endpoint_evaluation
        endpoint_inventory = endpoint.endpoint_inventory_lbmol
        endpoint_algebraic = endpoint.algebraic_coordinates
        endpoint_temperature = endpoint.dynamic_evaluation.physical_state.temperature_F
    total_accumulation = float(np.sum(endpoint_inventory) - np.sum(initial_inventory))
    return {
        "name": trajectory.name,
        "step_seconds": trajectory.step_seconds,
        "duration_seconds": trajectory.duration_seconds,
        "requested_steps": trajectory.requested_steps,
        "completed_steps": trajectory.completed_steps,
        "completed": trajectory.completed,
        "steps": step_reports,
        "per_step_gates": per_step_gates,
        "per_step_pass": all(all(gate.values()) for gate in per_step_gates)
        and len(per_step_gates) == trajectory.requested_steps,
        "total_inventory_history_lbmol": total_history,
        "total_inventory_accumulation_lbmol": total_accumulation,
        "total_inventory_strictly_increasing": bool(
            np.all(np.diff(total_history) > 0.0)
        ),
        "maximum_component_rate_abs_lbmolph": max(
            (
                float(report["component_rate_max_abs_lbmolph"])
                for report in step_reports
            ),
            default=0.0,
        ),
        "relative_inventory_drift_from_initial": float(
            np.max(np.abs(endpoint_inventory - initial_inventory) / initial_inventory)
        ),
        "algebraic_drift_from_initial": float(
            np.max(
                np.abs(
                    endpoint_algebraic - trajectory.initial_algebraic_coordinates
                )
            )
        ),
        "endpoint_inventory_lbmol": _rows(endpoint_inventory),
        "endpoint_algebraic_coordinates": _vector(endpoint_algebraic),
        "endpoint_temperature_F": _vector(endpoint_temperature),
    }


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify_execution_contract(payload, contract_path, result_path)
    source = payload["source_mapping"]
    base_spec = dd097._spec(
        source, float(payload["operating_spec"]["feed_enthalpy_BTUph"])
    )
    reference = dd097._reference(payload["reference"])
    state = dd097._state(payload["accepted_root_state"])
    inventory = inventory_from_state(state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-098 inventory mapping changed")
    perturbed_spec = scale_feed_throughput(base_spec, float(payload["feed_factor"]))
    contract = build_dynamic_dae_contract(base_spec.component_names)
    provider = dd097._provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    settings = dd097._settings(payload)
    started = time.perf_counter()
    root_hold = run_short_trajectory(
        contract,
        base_spec,
        reference,
        state,
        provider,
        call_audit,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=float(payload["root_hold_step_seconds"]),
        duration_seconds=float(payload["duration_seconds"]),
        settings=settings,
        name="dd098_root_hold",
    )
    perturbed = [
        run_short_trajectory(
            contract,
            perturbed_spec,
            reference,
            state,
            provider,
            call_audit,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step_seconds=float(step),
            duration_seconds=float(payload["duration_seconds"]),
            settings=settings,
            name=f"dd098_feed_step_{step:g}s",
        )
        for step in payload["perturbed_step_seconds"]
    ]
    wall_clock = float(time.perf_counter() - started)
    limits = payload["limits"]
    max_nfev = int(payload["solver"]["max_nfev"])
    required_rank = int(payload["required_step_rank"])
    root_report = _trajectory_report(
        root_hold, base_spec, inventory, limits, max_nfev, required_rank
    )
    perturbed_reports = [
        _trajectory_report(
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
        * float(payload["duration_seconds"])
        / 3600.0
    )
    for report in perturbed_reports:
        accumulation_error = abs(
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
            "expected_accumulation": accumulation_error
            < float(limits["expected_accumulation_relative_error"]),
        }
        report["expected_accumulation_relative_error"] = accumulation_error
        report["gates"] = gates
        report["pass"] = all(gates.values())
    first = perturbed_reports[0]
    second = perturbed_reports[1]
    first_inventory = np.asarray(first["endpoint_inventory_lbmol"], dtype=float)
    second_inventory = np.asarray(second["endpoint_inventory_lbmol"], dtype=float)
    first_algebraic = np.asarray(first["endpoint_algebraic_coordinates"], dtype=float)
    second_algebraic = np.asarray(second["endpoint_algebraic_coordinates"], dtype=float)
    first_temperature = np.asarray(first["endpoint_temperature_F"], dtype=float)
    second_temperature = np.asarray(second["endpoint_temperature_F"], dtype=float)
    refinement = {
        "relative_inventory_difference": float(
            np.max(np.abs(first_inventory - second_inventory) / inventory)
        ),
        "algebraic_coordinate_difference": float(
            np.max(np.abs(first_algebraic - second_algebraic))
        ),
        "temperature_difference_F": float(
            np.max(np.abs(first_temperature - second_temperature))
        ),
        "accumulation_relative_difference": float(
            abs(
                first["total_inventory_accumulation_lbmol"]
                - second["total_inventory_accumulation_lbmol"]
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
    provider_report = dd097._provider_summary(call_audit)
    passed = (
        root_report["pass"]
        and all(report["pass"] for report in perturbed_reports)
        and refinement["pass"]
        and provider_report["pass"]
    )
    result = {
        "schema_id": RESULT_SCHEMA_ID,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "dd098_core_v3_short_open_loop_passed"
            if passed
            else "dd098_core_v3_short_open_loop_failed"
        ),
        "decision": (
            "authorize_longer_open_loop_contract_only"
            if passed
            else "stop_short_open_loop_path"
        ),
        "wall_clock_sec": wall_clock,
        "feed_factor": float(payload["feed_factor"]),
        "expected_total_accumulation_lbmol": expected_accumulation,
        "root_hold": root_report,
        "perturbed": perturbed_reports,
        "refinement": refinement,
        "provider_provenance": provider_report,
        "pass": passed,
        "campaign_executed_once": True,
        "controller_attempted": False,
        "trajectory_attempted": True,
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
    parser.add_argument("--dd097-contract", type=Path, default=DEFAULT_DD097_CONTRACT)
    parser.add_argument("--dd097-result", type=Path, default=DEFAULT_DD097_RESULT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd097_contract, args.dd097_result, args.contract)
        print(json.dumps(output, indent=2))
        raise SystemExit(0)
    output = execute(args.contract, args.result)
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if output["pass"] else 2)
