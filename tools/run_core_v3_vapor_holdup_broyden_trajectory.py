#!/usr/bin/env python
"""Prepare or execute DD-256's secant-updated vapor-holdup trajectory."""

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
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_modified_newton_trajectory as dd255  # noqa: E402
import run_core_v3_vapor_holdup_parallel_trajectory as dd254  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    vapor_holdup_structural_pattern,
)


SCHEMA = "dd256-core-v3-c3c4-vapor-holdup-broyden-contract-v1"
RESULT_SCHEMA = "dd256-core-v3-c3c4-vapor-holdup-broyden-result-v1"
CONTRACT = Path("logs/dd256_core_v3_c3c4_vapor_holdup_broyden_contract_20260820.json")
RESULT = Path("logs/dd256_core_v3_c3c4_vapor_holdup_broyden_20260820.json")
CONTRACT_DOC = Path("docs/dd_256_core_v3_c3c4_vapor_holdup_broyden_contract_20260820.md")
RESULT_DOC = Path("docs/dd_256_core_v3_c3c4_vapor_holdup_broyden_20260820.md")
EVIDENCE = Path("logs/dd256_core_v3_c3c4_vapor_holdup_broyden_20260820.npz")
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_broyden_trajectory.py"),
    Path("tools/run_core_v3_vapor_holdup_parallel_trajectory.py"),
    Path("src/dynamic_distillation/core_v3/colored_jacobian_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments), cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def good_broyden_update(
    matrix: np.ndarray,
    coordinate_change: np.ndarray,
    residual_change: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Return the rank-one good-Broyden update and its secant error."""
    jacobian = np.asarray(matrix, dtype=float)
    step = np.asarray(coordinate_change, dtype=float).reshape((-1,))
    change = np.asarray(residual_change, dtype=float).reshape((-1,))
    denominator = float(step @ step)
    if denominator <= np.finfo(float).eps:
        raise RuntimeError("DD-256 Broyden coordinate step is too small")
    updated = jacobian + np.outer(change - jacobian @ step, step) / denominator
    secant_error = float(np.max(np.abs(updated @ step - change)))
    if np.any(~np.isfinite(updated)):
        raise RuntimeError("DD-256 Broyden matrix is nonfinite")
    return updated, secant_error


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    source = json.loads((ROOT / dd255.RESULT).read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / dd254.RESULT).read_text(encoding="utf-8"))
    source_contract = json.loads((ROOT / dd255.CONTRACT).read_text(encoding="utf-8"))
    if source.get("decision") != "retain_full_jacobian_refresh_per_iteration":
        raise RuntimeError("DD-256 requires DD-255's formal rejection")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd255.CONTRACT.as_posix(): _sha(dd255.CONTRACT),
            dd255.RESULT.as_posix(): _sha(dd255.RESULT),
            dd255.EVIDENCE.as_posix(): _sha(dd255.EVIDENCE),
            dd254.RESULT.as_posix(): _sha(dd254.RESULT),
            dd254.EVIDENCE.as_posix(): _sha(dd254.EVIDENCE),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "method": {
            "name": "good Broyden rank-one Jacobian updates",
            "fresh_jacobians_per_root": 1,
            "fresh_jacobian": "28-color central difference at each root initial point",
            "update": "B_next = B + ((delta_r - B*delta_x)*delta_x.T)/(delta_x.T*delta_x)",
            "update_scope": "within one endpoint root only",
            "parallel_workers": 0,
        },
        "trajectory": source_contract["trajectory"],
        "solver": source_contract["solver"],
        "baseline": {
            "serial_logical_provider_calls": baseline["comparison"]["serial_logical_work"],
            "serial_wall_clock_sec": baseline["serial"]["wall_clock_sec"],
            "endpoint_count": len(baseline["serial"]["endpoints"]),
            "response": baseline["serial"]["response"],
        },
        "limits": {
            "scaled_residual": 1.0e-8,
            "rank": 258,
            "condition": 1.0e8,
            "fugacity_residual": 1.0e-10,
            "eos_relative_residual": 1.0e-10,
            "coordinate_absolute_difference": 1.0e-9,
            "response_absolute_difference_lbmol": 1.0e-10,
            "component_identity_lbmol": 1.0e-6,
            "energy_identity_relative": 1.0e-8,
            "secant_absolute_error": 1.0e-10,
            "logical_provider_call_ratio": 0.30,
            "trajectory_wall_ratio": 0.65,
            "logical_provider_calls": 50000,
            "wall_clock_sec": 60.0,
        },
        "hard_stops": [
            "any root, endpoint-equivalence, science, conservation, or provider gate fails",
            "a root builds more than one finite-difference Jacobian or skips a requested secant update",
            "the deterministic Broyden secant identity fails",
            "call or wall ratios exceed the fixed DD-256 limits",
            "retry, alternate update, damping, reset, parallel worker, controller, fallback, or longer trajectory occurs",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-256 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-256 Broyden Vapor-Holdup Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Path: four serial `0.25 s` endpoints under the unchanged disturbance.",
            "- Each root begins with one fresh 28-color finite-difference Jacobian.",
            "- Later Jacobian callbacks use the fixed good-Broyden rank-one secant formula.",
            "- Every new endpoint discards the old matrix and starts fresh.",
            "- All DD-255 scientific and DD-254 endpoint-reference gates remain fixed.",
            "- Retry, alternate update, damping, reset, worker, controller, or extension: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-256 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-256 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-256 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-256 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    context = dd254._make_main_context()
    pattern = vapor_holdup_structural_pattern(context["contract"])
    state: dict[str, dict[str, Any]] = {}

    def broyden_factory(objective, point, state_id, root_epoch, _reference):
        current = np.asarray(point, dtype=float).copy()
        residual = np.asarray(objective(current, f"{state_id}:secant_residual"), dtype=float)
        if root_epoch not in state:
            matrix, groups = colored_central_difference_jacobian(
                objective,
                current,
                pattern=pattern,
                step=float(payload["solver"]["difference_step"]),
                state_id=state_id,
            )
            if len(groups) != 28:
                raise RuntimeError("DD-256 color count changed")
            state[root_epoch] = {
                "matrix": matrix,
                "coordinates": current,
                "residual": residual,
                "build_count": 1,
                "callback_count": 1,
                "update_count": 0,
                "secant_errors": [],
            }
            return matrix
        root = state[root_epoch]
        matrix, secant_error = good_broyden_update(
            root["matrix"],
            current - root["coordinates"],
            residual - root["residual"],
        )
        root["matrix"] = matrix
        root["coordinates"] = current
        root["residual"] = residual
        root["callback_count"] += 1
        root["update_count"] += 1
        root["secant_errors"].append(secant_error)
        return matrix

    started = time.perf_counter()
    path = dd254._run_path("broyden", context, payload, broyden_factory)
    wall = time.perf_counter() - started
    baseline_coordinates = np.load(ROOT / dd254.EVIDENCE)["serial_coordinates"]
    endpoint_coordinates = np.stack([solution.x for solution in path["solutions"]])
    coordinate_differences = np.max(
        np.abs(endpoint_coordinates - baseline_coordinates), axis=1
    )
    baseline = payload["baseline"]
    response_difference = abs(
        path["response"]["total_inventory_change_lbmol"]
        - baseline["response"]["total_inventory_change_lbmol"]
    )
    provider_report = compact_provider_report(context["audit"].report())
    provider_calls = int(context["audit"].record_count)
    call_ratio = provider_calls / int(baseline["serial_logical_provider_calls"])
    wall_ratio = wall / float(baseline["serial_wall_clock_sec"])
    limits = payload["limits"]
    endpoints_scientific = all(
        item["success"]
        and item["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and item["jacobian_rank"] == limits["rank"]
        and item["jacobian_condition"] < limits["condition"]
        and item["maximum_fugacity_residual"] < limits["fugacity_residual"]
        and item["maximum_eos_relative_residual"] < limits["eos_relative_residual"]
        and item["physical_pass"]
        for item in path["endpoint_reports"]
    )
    root_names = [f"dd254:broyden:root_{index}" for index in range(1, 5)]
    maximum_secant_error = max(
        error for root in state.values() for error in root["secant_errors"]
    )
    gates = {
        "path_complete": len(path["evaluations"]) == baseline["endpoint_count"] == 4,
        "scientific_endpoints": endpoints_scientific,
        "one_fresh_jacobian_per_root": all(state[root]["build_count"] == 1 for root in root_names),
        "all_callbacks_updated": all(
            state[root]["update_count"] == state[root]["callback_count"] - 1
            for root in root_names
        ),
        "secant_identity": maximum_secant_error < limits["secant_absolute_error"],
        "endpoint_equivalence": float(np.max(coordinate_differences))
        <= limits["coordinate_absolute_difference"],
        "response_equivalence": response_difference
        <= limits["response_absolute_difference_lbmol"],
        "component_identity": path["response"]["component_inventory_identity_max_abs_lbmol"]
        < limits["component_identity_lbmol"],
        "energy_identity": path["response"]["energy_identity_relative"]
        < limits["energy_identity_relative"],
        "provider": provider_report["pass"] and not provider_report["fallback_attempted"],
        "call_count": provider_calls < limits["logical_provider_calls"],
        "call_reduction": call_ratio < limits["logical_provider_call_ratio"],
        "wall_clock": wall < limits["wall_clock_sec"],
        "wall_reduction": wall_ratio < limits["trajectory_wall_ratio"],
        "serial_only": True,
        "no_retry_or_controller": True,
    }
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "broyden_vapor_holdup_trajectory_passed"
            if passed
            else "broyden_vapor_holdup_trajectory_failed"
        ),
        "decision": (
            "adopt_broyden_updated_vapor_holdup_step_path"
            if passed
            else "retain_full_jacobian_refresh_per_iteration"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "endpoints": path["endpoint_reports"],
        "response": path["response"],
        "root_evidence": {
            root: {
                "build_count": item["build_count"],
                "callback_count": item["callback_count"],
                "update_count": item["update_count"],
                "secant_errors": item["secant_errors"],
            }
            for root, item in state.items()
        },
        "maximum_secant_absolute_error": maximum_secant_error,
        "coordinate_max_abs_differences": coordinate_differences.tolist(),
        "response_absolute_difference_lbmol": response_difference,
        "provider": provider_report,
        "logical_provider_calls": provider_calls,
        "baseline_logical_provider_calls": baseline["serial_logical_provider_calls"],
        "logical_provider_call_ratio": call_ratio,
        "wall_clock_sec": wall,
        "baseline_wall_clock_sec": baseline["serial_wall_clock_sec"],
        "trajectory_wall_ratio": wall_ratio,
        "trajectory_speedup": 1.0 / wall_ratio,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_update_attempted": False,
        "damping_or_reset_attempted": False,
        "parallel_worker_attempted": False,
        "controller_attempted": False,
        "longer_trajectory_attempted": False,
    }
    (ROOT / result_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (ROOT / result_doc_path).write_text(_result_markdown(report), encoding="utf-8")
    np.savez_compressed(
        ROOT / evidence_path,
        endpoint_coordinates=endpoint_coordinates,
        baseline_coordinates=baseline_coordinates,
        final_liquid_inventory=path["evaluations"][-1].endpoint.liquid_component_inventory_lbmol,
        final_vapor_inventory=path["evaluations"][-1].endpoint.vapor_component_inventory_lbmol,
        **{f"jacobian_root_{index}": state[root]["matrix"] for index, root in enumerate(root_names, 1)},
    )
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-256 Broyden Vapor-Holdup Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Endpoints completed: `{len(payload['endpoints'])}`",
            f"- Maximum endpoint-coordinate difference: `{max(payload['coordinate_max_abs_differences']):.6e}`",
            f"- Maximum secant error: `{payload['maximum_secant_absolute_error']:.6e}`",
            f"- Provider calls: `{payload['logical_provider_calls']}` versus `{payload['baseline_logical_provider_calls']}` baseline",
            f"- Call ratio: `{payload['logical_provider_call_ratio']:.6f}`",
            f"- Wall: `{payload['wall_clock_sec']:.6f} s` versus `{payload['baseline_wall_clock_sec']:.6f} s` baseline",
            f"- Speedup: `{payload['trajectory_speedup']:.3f}x`",
            f"- Gates: `{payload['gates']}`",
            "- Retry, alternate update, damping, reset, worker, controller, or extension: `False`",
            "",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.prepare:
        report = prepare(args.contract, args.contract_doc)
        print(json.dumps({
            "schema_id": report["schema_id"],
            "contract_payload_sha256": report["contract_payload_sha256"],
            "method": report["method"],
            "campaign_executed": report["campaign_executed"],
        }, indent=2))
        return 0
    report = execute(args.contract, args.result, args.result_doc, args.evidence)
    print(json.dumps({
        "classification": report["classification"],
        "pass_gate": report["pass_gate"],
        "decision": report["decision"],
    }, indent=2))
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
