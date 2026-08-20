#!/usr/bin/env python
"""Prepare or execute DD-257's five-second vapor-holdup trajectory."""

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


SCHEMA = "dd257-core-v3-c3c4-vapor-holdup-five-second-contract-v1"
RESULT_SCHEMA = "dd257-core-v3-c3c4-vapor-holdup-five-second-result-v1"
CONTRACT = Path("logs/dd257_core_v3_c3c4_vapor_holdup_five_second_contract_20260820.json")
RESULT = Path("logs/dd257_core_v3_c3c4_vapor_holdup_five_second_20260820.json")
CONTRACT_DOC = Path("docs/dd_257_core_v3_c3c4_vapor_holdup_five_second_contract_20260820.md")
RESULT_DOC = Path("docs/dd_257_core_v3_c3c4_vapor_holdup_five_second_20260820.md")
EVIDENCE = Path("logs/dd257_core_v3_c3c4_vapor_holdup_five_second_20260820.npz")
IMPLEMENTATION = (
    Path("tools/run_core_v3_vapor_holdup_five_second_trajectory.py"),
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


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    baseline = json.loads((ROOT / dd254.RESULT).read_text(encoding="utf-8"))
    source_contract = json.loads((ROOT / dd254.CONTRACT).read_text(encoding="utf-8"))
    if not baseline["gates"]["scientific_endpoints"]:
        raise RuntimeError("DD-257 requires DD-254's accepted scientific path")
    trajectory = {
        "duration_sec": 5.0,
        "step_sec": 0.25,
        "steps_per_path": 20,
        "serial_path_count": 1,
        "parallel_path_count": 0,
        "worker_count": 0,
        "matrix_shape": source_contract["trajectory"]["matrix_shape"],
        "color_count": source_contract["trajectory"]["color_count"],
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "sources": {
            dd254.CONTRACT.as_posix(): _sha(dd254.CONTRACT),
            dd254.RESULT.as_posix(): _sha(dd254.RESULT),
            dd254.EVIDENCE.as_posix(): _sha(dd254.EVIDENCE),
        },
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "trajectory": trajectory,
        "disturbance": {
            "feed_component_multiplier": 1.001,
            "feed_enthalpy_multiplier": 1.001,
            "products_reflux_reboiler_duty_and_top_pressure": "fixed",
        },
        "solver": source_contract["solver"],
        "baseline": {
            "first_second_endpoint_count": 4,
            "response": baseline["serial"]["response"],
        },
        "limits": {
            "scaled_residual": 1.0e-8,
            "rank": 258,
            "condition": 1.0e8,
            "fugacity_residual": 1.0e-10,
            "eos_relative_residual": 1.0e-10,
            "first_second_coordinate_difference": 1.0e-12,
            "first_second_response_difference_lbmol": 1.0e-12,
            "component_identity_lbmol": 1.0e-6,
            "energy_identity_relative": 1.0e-8,
            "logical_provider_calls": 1200000,
            "wall_clock_sec": 240.0,
        },
        "hard_stops": [
            "any endpoint fails residual, rank, condition, physical, fugacity, EOS, conservation, or provider gates",
            "the first second does not reproduce DD-254",
            "inventory accumulation is not positive and monotonic",
            "call or wall limits fail",
            "retry, alternate step, worker, controller, fallback, or extension beyond five seconds occurs",
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
        raise RuntimeError("DD-257 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-257 Five-Second Vapor-Holdup Trajectory Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Path: 20 serial full-refresh backward-Euler endpoints of `0.25 s` each.",
            "- Disturbance: unchanged `+0.1%` feed and feed enthalpy.",
            "- Replay: the first four endpoints must reproduce DD-254.",
            "- Output: complete final 20-volume temperature, pressure, inventory, composition, and traffic profile.",
            "- Controllers, workers, retries, alternate steps, and extension beyond five seconds: `False`.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-257 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-257 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-257 implementation changed: {path}")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-257 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _stage_profile(context: Mapping[str, Any], evaluation: Any) -> list[dict[str, Any]]:
    endpoint = evaluation.endpoint
    topology = context["contract"].topology.column
    x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    y = endpoint.vapor_component_inventory_lbmol / np.sum(
        endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
    )
    liquid_by_source = {
        volume: float(endpoint.hydraulic_liquid_flow_lbmolph[index])
        for index, volume in enumerate(topology.hydraulic_volume_ids)
    }
    vapor_by_source = {
        link.source_volume: float(endpoint.vapor_flow_lbmolph[index])
        for index, link in enumerate(topology.vapor_links)
    }
    profile = []
    for index, volume in enumerate(topology.volume_ids):
        profile.append(
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
                "liquid_mole_fractions": x[index].tolist(),
                "vapor_mole_fractions": y[index].tolist(),
            }
        )
    return profile


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
            raise RuntimeError("DD-257 color count changed")
        return matrix

    started = time.perf_counter()
    path = dd254._run_path("five_second", context, payload, serial_factory)
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
    total_inventory = [
        float(
            np.sum(item.endpoint.liquid_component_inventory_lbmol)
            + np.sum(item.endpoint.vapor_component_inventory_lbmol)
        )
        for item in path["evaluations"]
    ]
    changes = np.asarray(total_inventory) - initial_total
    first_second_change = changes[3]
    first_second_response_difference = abs(
        first_second_change - payload["baseline"]["response"]["total_inventory_change_lbmol"]
    )
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
        "call_count": provider_calls < limits["logical_provider_calls"],
        "wall_clock": wall < limits["wall_clock_sec"],
        "no_retry_or_controller": True,
    }
    passed = all(gates.values())
    profile = _stage_profile(context, path["evaluations"][-1])
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
        "# DD-257 Five-Second Vapor-Holdup Trajectory Result",
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
        "| Volume | T (F) | P (psia) | N_L (lbmol) | N_V (lbmol) | L out (lbmol/h) | V out (lbmol/h) |",
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
            "trajectory": report["trajectory"],
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
