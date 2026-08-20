#!/usr/bin/env python
"""Prepare or execute DD-262's read-only DD-261 balance adjudication."""

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
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_core_v3_vapor_holdup_five_second_recovery as dd259  # noqa: E402
import run_core_v3_vapor_holdup_parallel_trajectory as dd254  # noqa: E402
import run_core_v3_vapor_holdup_small_moving_step as dd249  # noqa: E402
import run_core_v3_vapor_holdup_thirty_second_resume as dd261  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import compact_provider_report  # noqa: E402

from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (  # noqa: E402
    evaluate_two_phase_transport,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    decode_vapor_holdup_endpoint,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)


SCHEMA = "dd262-core-v3-c3c4-vapor-holdup-thirty-second-balance-adjudication-contract-v1"
RESULT_SCHEMA = "dd262-core-v3-c3c4-vapor-holdup-thirty-second-balance-adjudication-result-v1"
CONTRACT = Path("logs/dd262_core_v3_c3c4_vapor_holdup_thirty_second_balance_contract_20260820.json")
RESULT = Path("logs/dd262_core_v3_c3c4_vapor_holdup_thirty_second_balance_20260820.json")
EVIDENCE = Path("logs/dd262_core_v3_c3c4_vapor_holdup_thirty_second_balance_20260820.npz")
CONTRACT_DOC = Path("docs/dd_262_core_v3_c3c4_vapor_holdup_thirty_second_balance_contract_20260820.md")
RESULT_DOC = Path("docs/dd_262_core_v3_c3c4_vapor_holdup_thirty_second_balance_20260820.md")
IMPLEMENTATION = (
    Path("tools/adjudicate_core_v3_vapor_holdup_thirty_second_balances.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_implicit_residual_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_properties_v1.py"),
    Path("src/dynamic_distillation/core_v3/vapor_holdup_balances_v1.py"),
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


def _coordinate_sources() -> list[Path]:
    journals = sorted((ROOT / dd261.JOURNAL).glob("endpoint_*.json"))
    return [dd261.SOURCE_RECOVERY, *[path.relative_to(ROOT) for path in journals]]


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    dd261_result = json.loads((ROOT / dd261.RESULT).read_text(encoding="utf-8"))
    if dd261_result.get("pass_gate"):
        raise RuntimeError("DD-262 requires DD-261's aggregate-balance reporting failure")
    failed = {name for name, value in dd261_result["gates"].items() if not value}
    if failed != {"component_identity", "energy_identity"}:
        raise RuntimeError(f"DD-262 scope does not cover DD-261 failures: {sorted(failed)}")
    coordinate_sources = _coordinate_sources()
    if len(coordinate_sources) != 40:
        raise RuntimeError("DD-262 requires one DD-260 recovery plus 39 DD-261 journals")
    source_paths = [
        dd261.CONTRACT,
        dd261.RESULT,
        dd261.EVIDENCE,
        dd261.RECOVERY,
        *coordinate_sources,
    ]
    limits = json.loads((ROOT / dd261.CONTRACT).read_text(encoding="utf-8"))["limits"]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "authorization": {
            "source": "DD-261 isolated aggregate-rate formula defect",
            "scope": "one read-only 120-endpoint property replay; no solve or state advance",
            "preserve_dd261_classification": True,
        },
        "sources": {path.as_posix(): _sha(path) for path in source_paths},
        "implementation_sha256": {path.as_posix(): _sha(path) for path in IMPLEMENTATION},
        "replay": {
            "endpoint_count": 120,
            "timestep_sec": 0.25,
            "duration_sec": 30.0,
            "coordinate_decode": "saved coordinates against sequential saved/reconstructed references",
            "properties": "live DWSIM replay at each saved endpoint",
            "expected_component_change": "sum endpoint external component rates times dt",
            "expected_energy_change": "sum endpoint external energy rates times dt",
        },
        "limits": {
            "component_identity_lbmol": limits["component_identity_lbmol"],
            "energy_identity_relative": limits["energy_identity_relative"],
            "endpoint81_reference_parity": 1.0e-10,
            "final_state_parity": 1.0e-10,
            "provider_calls": 20_000,
            "wall_clock_sec": 120.0,
        },
        "hard_stops": [
            "the saved coordinate ledger is incomplete or changes checksum",
            "endpoint 81 or final endpoint fails saved-state parity",
            "the correctly accumulated component or energy identity exceeds its frozen limit",
            "provider ownership or fallback gates fail",
            "a nonlinear solve, timestep, state change, retry, or controller occurs",
        ],
        "property_replay_attempted": False,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    if (ROOT / contract_path).exists() or (ROOT / contract_doc_path).exists():
        raise RuntimeError("DD-262 contract artifact already exists")
    (ROOT / contract_path).write_text(dd259._json_text(payload), encoding="utf-8")
    (ROOT / contract_doc_path).write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-262 Thirty-Second Balance Adjudication Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- DD-261 remains formally failed and unchanged.",
            "- Replay exactly 120 saved endpoints with live DWSIM properties.",
            "- Sum each endpoint's changing component and energy boundary rates over `0.25 s`.",
            "- Compare those sums with the saved initial-to-final inventory and stored-energy changes.",
            "- No nonlinear solve, timestep, state change, retry, controller, or alternate calculation is authorized.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-262 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-262 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-262 implementation changed: {path}")
    if (ROOT / result_path).exists() or (ROOT / EVIDENCE).exists():
        raise RuntimeError("DD-262 output already exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _saved_coordinates() -> np.ndarray:
    recovered = json.loads((ROOT / dd261.SOURCE_RECOVERY).read_text(encoding="utf-8"))
    coordinates = list(np.asarray(recovered["endpoint_coordinates"], dtype=float))
    for path in sorted((ROOT / dd261.JOURNAL).glob("endpoint_*.json")):
        journal = json.loads(path.read_text(encoding="utf-8"))
        coordinates.append(np.asarray(journal["endpoint_coordinates"], dtype=float))
    result = np.stack(coordinates)
    if result.shape != (120, 258):
        raise RuntimeError(f"DD-262 coordinate shape changed: {result.shape}")
    return result


def _max_reference_difference(left: Any, right: Any) -> float:
    arrays = (
        "liquid_component_inventory_lbmol",
        "vapor_component_inventory_lbmol",
        "phase_transfer_lbmolph",
        "temperature_F",
        "pressure_psia",
        "hydraulic_liquid_flow_lbmolph",
        "vapor_flow_lbmolph",
        "total_stored_energy_BTU",
    )
    values = [float(np.max(np.abs(getattr(left, name) - getattr(right, name)))) for name in arrays]
    values.append(abs(float(left.condenser_duty_BTUph) - float(right.condenser_duty_BTUph)))
    return max(values)


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    payload = json.loads((ROOT / contract_path).read_text(encoding="utf-8"))
    _verify(payload, contract_path, result_path)
    dd261_result = json.loads((ROOT / dd261.RESULT).read_text(encoding="utf-8"))
    recovered = json.loads((ROOT / dd261.SOURCE_RECOVERY).read_text(encoding="utf-8"))
    saved_endpoint81 = dd254._reference_from_payload(recovered["next_reference"])
    coordinates = _saved_coordinates()
    context = dd254._make_main_context()
    reference = context["reference"]
    initial_reference = reference
    expected_component = np.zeros(3)
    expected_energy = 0.0
    external_component_rates: list[np.ndarray] = []
    external_energy_rates: list[float] = []
    endpoint81_parity = np.inf
    final_endpoint = None
    final_properties = None
    started = time.perf_counter()
    for index, point in enumerate(coordinates, start=1):
        endpoint = decode_vapor_holdup_endpoint(
            context["contract"], reference, context["numerical"], point
        )
        properties = evaluate_vapor_holdup_trial_properties(
            context["geometry"],
            endpoint.liquid_component_inventory_lbmol,
            endpoint.vapor_component_inventory_lbmol,
            endpoint.temperature_F,
            endpoint.pressure_psia,
            context["provider"],
            context["audit"],
            state_id=f"dd262:endpoint_{index}",
            evaluation_kind="residual",
        )
        liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
            endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
        )
        vapor_y = endpoint.vapor_component_inventory_lbmol / np.sum(
            endpoint.vapor_component_inventory_lbmol, axis=1, keepdims=True
        )
        live_inputs = replace(
            context["balance_inputs"],
            condenser_duty_BTUph=float(endpoint.condenser_duty_BTUph),
        )
        transport = evaluate_two_phase_transport(
            live_inputs,
            liquid_x,
            vapor_y,
            endpoint.hydraulic_liquid_flow_lbmolph,
            endpoint.vapor_flow_lbmolph,
            properties.liquid_enthalpy_BTU_lbmol,
            properties.vapor_enthalpy_BTU_lbmol,
        )
        external_component_rates.append(transport.external_component_rate_lbmolph.copy())
        external_energy_rates.append(float(transport.external_energy_rate_BTUph))
        expected_component += transport.external_component_rate_lbmolph * (0.25 / 3600.0)
        expected_energy += float(transport.external_energy_rate_BTUph) * (0.25 / 3600.0)
        reference = dd249._next_reference(
            reference,
            type("ReplayEvaluation", (), {"endpoint": endpoint, "properties": properties})(),
        )
        if index == 81:
            endpoint81_parity = _max_reference_difference(reference, saved_endpoint81)
        final_endpoint = endpoint
        final_properties = properties
    wall = time.perf_counter() - started
    if final_endpoint is None or final_properties is None:
        raise RuntimeError("DD-262 replay produced no endpoint")
    actual_component = np.sum(
        final_endpoint.liquid_component_inventory_lbmol
        + final_endpoint.vapor_component_inventory_lbmol
        - initial_reference.liquid_component_inventory_lbmol
        - initial_reference.vapor_component_inventory_lbmol,
        axis=0,
    )
    actual_energy = float(
        np.sum(final_properties.total_stored_energy_BTU - initial_reference.total_stored_energy_BTU)
    )
    component_error = float(np.max(np.abs(actual_component - expected_component)))
    energy_scale = max(abs(actual_energy), abs(expected_energy), 1.0)
    energy_error = abs(actual_energy - expected_energy) / energy_scale
    saved = np.load(ROOT / dd261.EVIDENCE)
    final_parity = max(
        float(np.max(np.abs(final_endpoint.liquid_component_inventory_lbmol - saved["final_liquid_inventory"]))),
        float(np.max(np.abs(final_endpoint.vapor_component_inventory_lbmol - saved["final_vapor_inventory"]))),
        float(np.max(np.abs(final_endpoint.temperature_F - saved["final_temperature_F"]))),
        float(np.max(np.abs(final_endpoint.pressure_psia - saved["final_pressure_psia"]))),
        float(np.max(np.abs(final_endpoint.hydraulic_liquid_flow_lbmolph - saved["final_liquid_flow_lbmolph"]))),
        float(np.max(np.abs(final_endpoint.vapor_flow_lbmolph - saved["final_vapor_flow_lbmolph"]))),
    )
    provider = compact_provider_report(context["audit"].report())
    calls = int(context["audit"].record_count)
    limits = payload["limits"]
    gates = {
        "coordinate_count": coordinates.shape == (120, 258),
        "endpoint81_parity": endpoint81_parity < limits["endpoint81_reference_parity"],
        "final_state_parity": final_parity < limits["final_state_parity"],
        "component_identity": component_error < limits["component_identity_lbmol"],
        "energy_identity": energy_error < limits["energy_identity_relative"],
        "provider": bool(provider["pass"] and not provider["fallback_attempted"]),
        "provider_calls": calls < limits["provider_calls"],
        "wall_clock": wall < limits["wall_clock_sec"],
        "no_solve_or_state_advance": True,
    }
    passed = bool(all(gates.values()))
    report = {
        "schema_id": RESULT_SCHEMA,
        "classification": "thirty_second_balance_adjudication_passed" if passed else "thirty_second_balance_adjudication_failed",
        "decision": "accept_dd261_scientific_trajectory_through_thirty_seconds" if passed else "retain_dd261_formal_failure_without_scientific_acceptance",
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "dd261_formal_classification_preserved": dd261_result["classification"],
        "endpoint_count": 120,
        "actual_component_inventory_change_lbmol": actual_component,
        "expected_component_inventory_change_lbmol": expected_component,
        "component_inventory_identity_max_abs_lbmol": component_error,
        "actual_stored_energy_change_BTU": actual_energy,
        "expected_stored_energy_change_BTU": expected_energy,
        "energy_identity_relative": energy_error,
        "endpoint81_reference_parity_max_abs": endpoint81_parity,
        "final_state_parity_max_abs": final_parity,
        "provider": provider,
        "provider_calls": calls,
        "wall_clock_sec": wall,
        "gates": gates,
        "pass_gate": passed,
        "nonlinear_solve_attempted": False,
        "state_advance_attempted": False,
        "retry_attempted": False,
        "controller_attempted": False,
    }
    dd259._atomic_npz(
        evidence_path,
        endpoint_coordinates=coordinates,
        external_component_rate_lbmolph=np.stack(external_component_rates),
        external_energy_rate_BTUph=np.asarray(external_energy_rates),
        actual_component_inventory_change_lbmol=actual_component,
        expected_component_inventory_change_lbmol=expected_component,
    )
    dd259._atomic_json(result_path, report)
    (ROOT / result_doc_path).write_text(_result_markdown(dd259.json_native(report)), encoding="utf-8")
    return dd259.json_native(report)


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-262 Thirty-Second Balance Adjudication Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Replayed endpoints: `{payload['endpoint_count']}`",
            f"- Component identity: `{payload['component_inventory_identity_max_abs_lbmol']:.6e} lbmol`",
            f"- Energy identity relative: `{payload['energy_identity_relative']:.6e}`",
            f"- Endpoint-81 parity: `{payload['endpoint81_reference_parity_max_abs']:.6e}`",
            f"- Final-state parity: `{payload['final_state_parity_max_abs']:.6e}`",
            f"- Provider calls: `{payload['provider_calls']}`; wall: `{payload['wall_clock_sec']:.3f} s`",
            f"- Gates: `{payload['gates']}`",
            "",
            "DD-261's formal failed classification is preserved. DD-262 corrects only the",
            "aggregate assessment: the expected changes are sums of all endpoint boundary",
            "rates, not the final endpoint rate multiplied by the full duration.",
            "",
            "Nonlinear solve, timestep, state advance, retry, or controller: `False`",
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
        print(dd259._json_text({
            "schema_id": report["schema_id"],
            "contract_payload_sha256": report["contract_payload_sha256"],
            "replay": report["replay"],
            "campaign_executed": report["campaign_executed"],
        }), end="")
        return 0
    report = execute(args.contract, args.result, args.result_doc, args.evidence)
    print(dd259._json_text({
        "classification": report["classification"],
        "pass_gate": report["pass_gate"],
        "decision": report["decision"],
    }), end="")
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
