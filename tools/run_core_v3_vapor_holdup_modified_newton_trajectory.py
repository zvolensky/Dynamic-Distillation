#!/usr/bin/env python
"""Prepare or execute DD-255's modified-Newton vapor-holdup trajectory."""

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


SCHEMA = "dd255-core-v3-c3c4-vapor-holdup-modified-newton-contract-v1"
RESULT_SCHEMA = "dd255-core-v3-c3c4-vapor-holdup-modified-newton-result-v1"
CONTRACT = Path(
    "logs/dd255_core_v3_c3c4_vapor_holdup_modified_newton_contract_20260820.json"
)
RESULT = Path(
    "logs/dd255_core_v3_c3c4_vapor_holdup_modified_newton_20260820.json"
)
CONTRACT_DOC = Path(
    "docs/dd_255_core_v3_c3c4_vapor_holdup_modified_newton_contract_20260820.md"
)
RESULT_DOC = Path(
    "docs/dd_255_core_v3_c3c4_vapor_holdup_modified_newton_20260820.md"
)
EVIDENCE = Path(
    "logs/dd255_core_v3_c3c4_vapor_holdup_modified_newton_20260820.npz"
)
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_modified_newton_trajectory.py"),
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
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    baseline = json.loads((ROOT / dd254.RESULT).read_text(encoding="utf-8"))
    source_contract = json.loads((ROOT / dd254.CONTRACT).read_text(encoding="utf-8"))
    if baseline.get("decision") != "retain_serial_vapor_holdup_step_path":
        raise RuntimeError("DD-255 requires DD-254's retained serial path")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd254.CONTRACT.as_posix(): _sha(dd254.CONTRACT),
            dd254.RESULT.as_posix(): _sha(dd254.RESULT),
            dd254.EVIDENCE.as_posix(): _sha(dd254.EVIDENCE),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "method": {
            "name": "one-fresh-jacobian-per-root modified Newton",
            "jacobian": "28-color central difference at the root initial point",
            "reuse_scope": "within one endpoint root only",
            "fresh_jacobians_per_root": 1,
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
            "logical_provider_call_ratio": 0.30,
            "trajectory_wall_ratio": 0.65,
            "logical_provider_calls": 50000,
            "wall_clock_sec": 60.0,
        },
        "hard_stops": [
            "any of the four roots fails or exceeds the unchanged solver evaluation limit",
            "more than one finite-difference Jacobian is built for any root",
            "an endpoint, response, scientific, conservation, or provider gate fails",
            "logical work is not below 30 percent of the DD-254 serial path",
            "wall is not below 65 percent of the DD-254 serial path",
            "retry, alternate grid, parallel worker, controller, fallback, or longer trajectory occurs",
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
        raise RuntimeError("DD-255 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-255 Modified-Newton Vapor-Holdup Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Path: four serial `0.25 s` endpoints under the unchanged DD-254 disturbance.",
            "- Jacobian: one fresh 28-color matrix at the start of each root, then fixed within that root.",
            "- Reference: all four accepted DD-254 serial endpoints.",
            "- Endpoint, residual, conservation, physical, rank, and provider gates remain mandatory.",
            "- Calls must fall below 30% and wall below 65% of DD-254 serial.",
            "- Retry, alternate grid, parallel worker, controller, or longer trajectory: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-255 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-255 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-255 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-255 result exists; rerun is prohibited")
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
    matrices: dict[str, np.ndarray] = {}
    build_counts: dict[str, int] = {}
    callback_counts: dict[str, int] = {}

    def modified_newton_factory(objective, point, state_id, root_epoch, _reference):
        callback_counts[root_epoch] = callback_counts.get(root_epoch, 0) + 1
        if root_epoch not in matrices:
            matrix, groups = colored_central_difference_jacobian(
                objective,
                point,
                pattern=pattern,
                step=float(payload["solver"]["difference_step"]),
                state_id=state_id,
            )
            if len(groups) != 28:
                raise RuntimeError("DD-255 color count changed")
            matrices[root_epoch] = matrix
            build_counts[root_epoch] = 1
        return matrices[root_epoch]

    started = time.perf_counter()
    path = dd254._run_path(
        "modified_newton",
        context,
        payload,
        modified_newton_factory,
    )
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
    root_names = [f"dd254:modified_newton:root_{index}" for index in range(1, 5)]
    gates = {
        "path_complete": len(path["evaluations"]) == baseline["endpoint_count"] == 4,
        "scientific_endpoints": endpoints_scientific,
        "one_fresh_jacobian_per_root": all(build_counts.get(root) == 1 for root in root_names),
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
            "modified_newton_vapor_holdup_trajectory_passed"
            if passed
            else "modified_newton_vapor_holdup_trajectory_failed"
        ),
        "decision": (
            "adopt_one_fresh_jacobian_per_root"
            if passed
            else "retain_full_jacobian_refresh_per_iteration"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "endpoints": path["endpoint_reports"],
        "response": path["response"],
        "jacobian_build_counts": build_counts,
        "jacobian_callback_counts": callback_counts,
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
        "alternate_grid_attempted": False,
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
        **{f"jacobian_root_{index}": matrices[root] for index, root in enumerate(root_names, 1)},
    )
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-255 Modified-Newton Vapor-Holdup Trajectory Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Endpoints completed: `{len(payload['endpoints'])}`",
            f"- Maximum endpoint-coordinate difference: `{max(payload['coordinate_max_abs_differences']):.6e}`",
            f"- Jacobian builds by root: `{payload['jacobian_build_counts']}`",
            f"- Provider calls: `{payload['logical_provider_calls']}` versus `{payload['baseline_logical_provider_calls']}` baseline",
            f"- Call ratio: `{payload['logical_provider_call_ratio']:.6f}`",
            f"- Wall: `{payload['wall_clock_sec']:.6f} s` versus `{payload['baseline_wall_clock_sec']:.6f} s` baseline",
            f"- Speedup: `{payload['trajectory_speedup']:.3f}x`",
            f"- Gates: `{payload['gates']}`",
            "- Retry, alternate grid, parallel worker, controller, or longer trajectory: `False`",
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
        print(
            json.dumps(
                {
                    "schema_id": report["schema_id"],
                    "contract_payload_sha256": report["contract_payload_sha256"],
                    "method": report["method"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc, args.evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
