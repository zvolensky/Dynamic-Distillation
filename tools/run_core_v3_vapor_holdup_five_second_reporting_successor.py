#!/usr/bin/env python
"""Prepare or execute DD-258's reporting-safe five-second trajectory."""

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

import run_core_v3_vapor_holdup_five_second_trajectory as dd257  # noqa: E402
import run_core_v3_vapor_holdup_parallel_trajectory as dd254  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitEndpoint,
    vapor_holdup_structural_pattern,
)


SCHEMA = "dd258-core-v3-c3c4-vapor-holdup-five-second-successor-contract-v1"
RESULT_SCHEMA = "dd258-core-v3-c3c4-vapor-holdup-five-second-successor-result-v1"
CONTRACT = Path("logs/dd258_core_v3_c3c4_vapor_holdup_five_second_contract_20260820.json")
RESULT = Path("logs/dd258_core_v3_c3c4_vapor_holdup_five_second_20260820.json")
CONTRACT_DOC = Path("docs/dd_258_core_v3_c3c4_vapor_holdup_five_second_contract_20260820.md")
RESULT_DOC = Path("docs/dd_258_core_v3_c3c4_vapor_holdup_five_second_20260820.md")
EVIDENCE = Path("logs/dd258_core_v3_c3c4_vapor_holdup_five_second_20260820.npz")
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_five_second_reporting_successor.py"),
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


def stage_profile(
    context: Mapping[str, Any], endpoint: VaporHoldupImplicitEndpoint
) -> list[dict[str, Any]]:
    """Map one endpoint to all physical volumes using tuple-based flow links."""
    topology = context["contract"].topology.column
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    vapor_y = endpoint.vapor_component_inventory_lbmol / np.sum(
        endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
    )
    liquid_by_source = {
        volume: float(endpoint.hydraulic_liquid_flow_lbmolph[index])
        for index, volume in enumerate(topology.hydraulic_volume_ids)
    }
    vapor_by_source = {
        source: float(endpoint.vapor_flow_lbmolph[index])
        for index, (source, _destination, _link_name) in enumerate(topology.vapor_links)
    }
    return [
        {
            "volume": volume,
            "temperature_F": float(endpoint.temperature_F[index]),
            "pressure_psia": float(endpoint.pressure_psia[index]),
            "liquid_inventory_lbmol": float(
                np.sum(endpoint.liquid_component_inventory_lbmol[index])
            ),
            "vapor_inventory_lbmol": float(
                np.sum(endpoint.vapor_component_inventory_lbmol[index])
            ),
            "liquid_flow_out_lbmolph": liquid_by_source.get(volume),
            "vapor_flow_out_lbmolph": vapor_by_source.get(volume),
            "liquid_mole_fractions": liquid_x[index].tolist(),
            "vapor_mole_fractions": vapor_y[index].tolist(),
        }
        for index, volume in enumerate(topology.volume_ids)
    ]


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    failed = json.loads((ROOT / dd257.RESULT).read_text(encoding="utf-8"))
    source = json.loads((ROOT / dd257.CONTRACT).read_text(encoding="utf-8"))
    if failed.get("decision") != "no_scientific_classification":
        raise RuntimeError("DD-258 requires DD-257's reporting-only abort")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd257.CONTRACT.as_posix(): _sha(dd257.CONTRACT),
            dd257.RESULT.as_posix(): _sha(dd257.RESULT),
            dd254.RESULT.as_posix(): _sha(dd254.RESULT),
            dd254.EVIDENCE.as_posix(): _sha(dd254.EVIDENCE),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "trajectory": source["trajectory"],
        "disturbance": source["disturbance"],
        "solver": source["solver"],
        "baseline": source["baseline"],
        "limits": source["limits"],
        "reporter": {
            "vapor_link_shape": ["source", "destination", "link_name"],
            "preflight_requires_all_volumes": 20,
            "preflight_requires_all_vapor_links": 19,
        },
        "hard_stops": [
            *source["hard_stops"],
            "the property-free reporter preflight does not pass before contract freeze",
            "any result or evidence serialization fails",
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
        raise RuntimeError("DD-258 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-258 Reporting-Safe Five-Second Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Science, solver, limits, disturbance, and 20 endpoint path are unchanged from DD-257.",
            "- Reporter preflight: all 20 volumes and 19 tuple-based vapor links must map property-free.",
            "- Output: JSON, NPZ evidence, and complete final stage-profile Markdown.",
            "- Retry, alternate step, worker, controller, fallback, or extension: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-258 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-258 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-258 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-258 result exists; rerun is prohibited")
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

    def serial_factory(objective, point, state_id, _root_epoch, _reference):
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=float(payload["solver"]["difference_step"]),
            state_id=state_id,
        )
        if len(groups) != 28:
            raise RuntimeError("DD-258 color count changed")
        return matrix

    started = time.perf_counter()
    path = dd254._run_path("five_second_successor", context, payload, serial_factory)
    wall = time.perf_counter() - started
    endpoint_coordinates = np.stack([solution.x for solution in path["solutions"]])
    baseline_coordinates = np.load(ROOT / dd254.EVIDENCE)["serial_coordinates"]
    replay_differences = np.max(
        np.abs(endpoint_coordinates[:4] - baseline_coordinates), axis=1
    )
    initial_total = float(
        np.sum(path["initial_reference"].liquid_component_inventory_lbmol)
        + np.sum(path["initial_reference"].vapor_component_inventory_lbmol)
    )
    total_inventory = np.asarray(
        [
            np.sum(item.endpoint.liquid_component_inventory_lbmol)
            + np.sum(item.endpoint.vapor_component_inventory_lbmol)
            for item in path["evaluations"]
        ],
        dtype=float,
    )
    changes = total_inventory - initial_total
    first_second_response_difference = abs(
        changes[3] - payload["baseline"]["response"]["total_inventory_change_lbmol"]
    )
    profile = stage_profile(context, path["evaluations"][-1].endpoint)
    provider_report = compact_provider_report(context["audit"].report())
    provider_calls = int(context["audit"].record_count)
    limits = payload["limits"]
    scientific = all(
        item["success"]
        and item["scaled_residual_inf_norm"] < limits["scaled_residual"]
        and item["jacobian_rank"] == limits["rank"]
        and item["jacobian_condition"] < limits["condition"]
        and item["maximum_fugacity_residual"] < limits["fugacity_residual"]
        and item["maximum_eos_relative_residual"] < limits["eos_relative_residual"]
        and item["physical_pass"]
        for item in path["endpoint_reports"]
    )
    gates = {
        "path_complete": len(path["evaluations"]) == 20,
        "scientific_endpoints": scientific,
        "first_second_coordinates": float(np.max(replay_differences))
        <= limits["first_second_coordinate_difference"],
        "first_second_response": first_second_response_difference
        <= limits["first_second_response_difference_lbmol"],
        "positive_monotonic_accumulation": bool(
            np.all(changes > 0.0) and np.all(np.diff(changes) > 0.0)
        ),
        "component_identity": path["response"]["component_inventory_identity_max_abs_lbmol"]
        < limits["component_identity_lbmol"],
        "energy_identity": path["response"]["energy_identity_relative"]
        < limits["energy_identity_relative"],
        "provider": provider_report["pass"] and not provider_report["fallback_attempted"],
        "report_complete": len(profile) == 20,
        "call_count": provider_calls < limits["logical_provider_calls"],
        "wall_clock": wall < limits["wall_clock_sec"],
        "no_retry_or_controller": True,
    }
    passed = all(gates.values())
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "five_second_vapor_holdup_trajectory_passed"
            if passed
            else "five_second_vapor_holdup_trajectory_failed"
        ),
        "decision": (
            "accept_repeated_vapor_holdup_dynamics_through_five_seconds"
            if passed
            else "retain_one_second_vapor_holdup_limit"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "component_names": list(context["contract"].component_names),
        "endpoints": path["endpoint_reports"],
        "inventory_change_by_endpoint_lbmol": changes.tolist(),
        "response": path["response"],
        "first_second_coordinate_differences": replay_differences.tolist(),
        "first_second_response_difference_lbmol": first_second_response_difference,
        "final_stage_profile": profile,
        "provider": provider_report,
        "logical_provider_calls": provider_calls,
        "wall_clock_sec": wall,
        "simulation_time_sec": 5.0,
        "simulation_to_wall_ratio": 5.0 / wall,
        "gates": gates,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "retry_attempted": False,
        "alternate_step_attempted": False,
        "parallel_worker_attempted": False,
        "controller_attempted": False,
        "longer_trajectory_attempted": False,
    }
    (ROOT / result_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (ROOT / result_doc_path).write_text(_result_markdown(report), encoding="utf-8")
    np.savez_compressed(
        ROOT / evidence_path,
        endpoint_coordinates=endpoint_coordinates,
        inventory_change_by_endpoint_lbmol=changes,
        final_liquid_inventory=path["evaluations"][-1].endpoint.liquid_component_inventory_lbmol,
        final_vapor_inventory=path["evaluations"][-1].endpoint.vapor_component_inventory_lbmol,
    )
    return report


def _result_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# DD-258 Reporting-Safe Five-Second Trajectory Result",
        "",
        f"- Classification: `{payload['classification']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Endpoints: `{len(payload['endpoints'])}`",
        f"- Final inventory change: `{payload['response']['total_inventory_change_lbmol']:.9e} lbmol`",
        f"- Worst residual: `{max(item['scaled_residual_inf_norm'] for item in payload['endpoints']):.6e}`",
        f"- Provider calls: `{payload['logical_provider_calls']}`",
        f"- Wall: `{payload['wall_clock_sec']:.3f} s`; simulation/wall: `{payload['simulation_to_wall_ratio']:.5f}`",
        f"- Gates: `{payload['gates']}`",
        "",
        "## Final stage profile",
        "",
        "| Volume | T (F) | P (psia) | N_L | N_V | L out | V out |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["final_stage_profile"]:
        liquid = "" if item["liquid_flow_out_lbmolph"] is None else f"{item['liquid_flow_out_lbmolph']:.3f}"
        vapor = "" if item["vapor_flow_out_lbmolph"] is None else f"{item['vapor_flow_out_lbmolph']:.3f}"
        lines.append(
            f"| {item['volume']} | {item['temperature_F']:.4f} | {item['pressure_psia']:.5f} | "
            f"{item['liquid_inventory_lbmol']:.5f} | {item['vapor_inventory_lbmol']:.5f} | {liquid} | {vapor} |"
        )
    lines.extend(("", "Retry, alternate step, worker, controller, or extension: `False`", ""))
    return "\n".join(lines)


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
            "reporter": report["reporter"],
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
