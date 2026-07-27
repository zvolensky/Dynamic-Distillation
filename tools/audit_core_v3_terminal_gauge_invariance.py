#!/usr/bin/env python
"""Prepare or execute the frozen DD-121 terminal gauge-invariance audit."""

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

import audit_core_v3_pressure_layer_numerical as dd102
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerNumericalSpec,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.terminal_gauge_invariance_v1 import (
    assess_terminal_gauge_invariance,
    scale_terminal_gauge_coordinates,
)
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import (
    evaluate_zero_rate_readiness,
)


SCHEMA = "dd121-core-v3-terminal-gauge-invariance-contract-v1"
RESULT_SCHEMA = "dd121-core-v3-terminal-gauge-invariance-result-v1"
CONTRACT = Path("logs/dd121_core_v3_terminal_gauge_invariance_contract_20260727.json")
RESULT = Path("logs/dd121_core_v3_terminal_gauge_invariance_20260727.json")
CONTRACT_DOC = Path("docs/dd_121_core_v3_terminal_gauge_invariance_contract_20260727.md")
RESULT_DOC = Path("docs/dd_121_core_v3_terminal_gauge_invariance_20260727.md")
DD120_CONTRACT = Path("logs/dd120_core_v3_zero_rate_root_contract_20260727.json")
DD120_RESULT = Path("logs/dd120_core_v3_zero_rate_root_20260727.json")
REVIEW = Path("docs/independent_review_core_v3_zero_rate_initialization_20260727.md")
PERTURBATIONS = (
    ("reflux_drum_plus_1pct", "reflux_drum", 1.01),
    ("reflux_drum_minus_1pct", "reflux_drum", 0.99),
    ("combined_reboiler_sump_plus_1pct", "combined_reboiler_sump", 1.01),
    ("combined_reboiler_sump_minus_1pct", "combined_reboiler_sump", 0.99),
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/terminal_gauge_invariance_v1.py",
    "src/dynamic_distillation/core_v3/zero_rate_readiness_v1.py",
    "tests/test_core_v3_terminal_gauge_invariance_v1.py",
    "tools/audit_core_v3_terminal_gauge_invariance.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def prepare() -> dict[str, Any]:
    source = _load(DD120_CONTRACT)
    result = _load(DD120_RESULT)
    if result["pass"] or result["decision"] != "retire_terminal_scaled_zero_rate_root_path":
        raise RuntimeError("DD-121 requires the failed DD-120 decision")
    endpoint = result["starts"][0]["final_coordinates"]
    if len(endpoint) != 46:
        raise RuntimeError("DD-120 endpoint does not contain 46 coordinates")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD120_CONTRACT, DD120_RESULT, REVIEW)
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "initializer_numerical": source["initializer_numerical"],
        "top_storage_gradient_BTU_lbmol": source["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "pressure_reference_psia": source["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": source["pressure_coordinate_scale_psia"],
        "pressure_residual_scale_psia": source["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": source["dry_tray_pressure_drop_coefficient"],
        "pressure_link_geometry": source["pressure_link_geometry"],
        "endpoint_coordinates": endpoint,
        "perturbations": [
            {"name": name, "terminal": terminal, "factor": factor}
            for name, terminal, factor in PERTURBATIONS
        ],
        "evaluation_count": 6,
        "absolute_invariance_floor": 1.0e-10,
        "repeatability_multiplier": 10.0,
        "composition_invariance_limit": 1.0e-12,
        "specific_energy_invariance_limit": 1.0e-10,
        "inventory_scaling_limit": 1.0e-10,
        "fixed_algebraic_limit": 0.0,
        "provider_call_limit": 1000,
        "wall_clock_limit_sec": 30.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "any DAE row changes beyond max(1e-10, 10 times provider repeatability)",
            "terminal composition or bottom specific internal energy changes",
            "any algebraic coordinate changes or terminal inventory fails exact scaling",
            "provider ownership, call-count, wall-clock, or physicality gate fails",
            "a Jacobian, nonlinear solve, continuation, timestep, controller, or dynamics is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-121 Frozen Terminal Gauge-Invariance Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Evaluations: two repeated DD-120 endpoints plus four terminal +/-1% inventory perturbations",
                "- Fixed: every algebraic coordinate, composition, and bottom specific internal energy",
                "- Gate: DAE change <= `max(1e-10, 10 * provider repeatability)`",
                "- Jacobian, solve, timestep, controller, or dynamics: `False`",
                "",
                "Pass authorizes drafting one frozen 48 x 48 controlled-terminal root contract. Failure requires a hidden terminal-owner audit.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _verify(payload: dict[str, Any]) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-121 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-121 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-121 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-121 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-121 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _context(payload: Mapping[str, Any]):
    spec = dd102._spec(
        payload["source_mapping"], float(payload["operating_spec"]["feed_enthalpy_BTUph"])
    )
    reference = dd102._reference(payload["reference"])
    template = dd102._state(payload["accepted_root_state"])
    contract = build_conserved_nu_pressure_initializer_contract(spec.component_names)
    provider = dd102._provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    molecular_weight = call_audit.component_molecular_weights(
        provider,
        caller="dd121_molecular_weight",
        state_id="dd121:preparation",
        evaluation_kind="preparation",
    )
    pressure_numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(payload["pressure_reference_psia"]),
        pressure_coordinate_scale_psia=float(payload["pressure_coordinate_scale_psia"]),
        pressure_residual_scale_psia=float(payload["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(payload["dry_tray_pressure_drop_coefficient"]),
        component_mw_lbm_per_lbmol=molecular_weight,
        link_geometry=tuple(PressureLinkGeometry(**item) for item in payload["pressure_link_geometry"]),
        enforce_pressure_order=False,
    )
    data = payload["initializer_numerical"]
    numerical = InitializerNumericalSpec(
        inventory_reference_lbmol=np.asarray(data["inventory_reference_lbmol"]),
        lower_internal_energy_reference_BTU=np.asarray(data["lower_internal_energy_reference_BTU"]),
        lower_internal_energy_scale_BTU=np.asarray(data["lower_internal_energy_scale_BTU"]),
        component_total_targets_lbmol=np.asarray(data["component_total_targets_lbmol"]),
        stored_energy_target_BTU=float(data["stored_energy_target_BTU"]),
        terminal_total_targets_lbmol=np.asarray(data["terminal_total_targets_lbmol"]),
        objective_center=np.asarray(data["objective_center"]),
        objective_weights=np.asarray(data["objective_weights"]),
        lower_bounds=np.asarray(data["lower_bounds"]),
        upper_bounds=np.asarray(data["upper_bounds"]),
        jacobian_step=float(data.get("jacobian_step", 1.0e-5)),
    )
    common = {
        "top_storage_gradient_BTU_lbmol": payload["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": pressure_numerical,
    }
    return spec, reference, template, contract, provider, call_audit, numerical, common


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec, reference, template, contract, provider, call_audit, numerical, common = _context(payload)
    point = np.asarray(payload["endpoint_coordinates"], dtype=float)
    started = time.perf_counter()

    def evaluate(candidate: np.ndarray, state_id: str):
        return evaluate_zero_rate_readiness(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=candidate,
            state_id=state_id,
            evaluation_kind="residual",
            **common,
        )

    baseline = evaluate(point, "dd121:baseline:1")
    repeated = evaluate(point, "dd121:baseline:2")
    baseline_inventory = np.asarray(baseline.full_evaluation.inventory_lbmol, dtype=float)
    baseline_composition = baseline_inventory / np.sum(baseline_inventory, axis=1, keepdims=True)
    baseline_specific_energy = float(
        baseline.full_evaluation.lower_internal_energy_BTU[-1]
        / np.sum(baseline_inventory[-1])
    )
    perturbation_vectors = {}
    composition_differences = {}
    specific_energy_differences = {}
    records = []
    state_count = baseline.full_evaluation.inventory_lbmol.size + len(
        baseline.full_evaluation.lower_internal_energy_BTU
    )
    for name, terminal, factor in PERTURBATIONS:
        trial_point = scale_terminal_gauge_coordinates(
            numerical, point, terminal=terminal, factor=factor
        )
        trial = evaluate(trial_point, f"dd121:{name}")
        inventory = np.asarray(trial.full_evaluation.inventory_lbmol, dtype=float)
        composition = inventory / np.sum(inventory, axis=1, keepdims=True)
        specific_energy = float(
            trial.full_evaluation.lower_internal_energy_BTU[-1] / np.sum(inventory[-1])
        )
        volume_index = 0 if terminal == "reflux_drum" else inventory.shape[0] - 1
        scaling_error = float(
            np.max(np.abs(inventory[volume_index] - factor * baseline_inventory[volume_index]))
        )
        composition_difference = float(np.max(np.abs(composition - baseline_composition)))
        specific_energy_difference = abs(specific_energy - baseline_specific_energy)
        algebraic_difference = float(np.max(np.abs(trial_point[state_count:] - point[state_count:])))
        perturbation_vectors[name] = trial.dae_scaled
        composition_differences[name] = composition_difference
        specific_energy_differences[name] = specific_energy_difference
        records.append(
            {
                "name": name,
                "terminal": terminal,
                "factor": factor,
                "dae_residual_difference_inf_norm": float(np.max(np.abs(trial.dae_scaled - baseline.dae_scaled))),
                "dae_residual_difference": _vector(trial.dae_scaled - baseline.dae_scaled),
                "terminal_scaled_residual": _vector(trial.terminal_scaled),
                "terminal_scaled_residual_difference": _vector(trial.terminal_scaled - baseline.terminal_scaled),
                "composition_difference_inf_norm": composition_difference,
                "bottom_specific_energy_difference": specific_energy_difference,
                "terminal_inventory_scaling_error_lbmol": scaling_error,
                "algebraic_coordinate_difference_inf_norm": algebraic_difference,
            }
        )
    assessment = assess_terminal_gauge_invariance(
        baseline.dae_scaled,
        repeated.dae_scaled,
        perturbation_vectors,
        composition_differences,
        specific_energy_differences,
        absolute_floor=float(payload["absolute_invariance_floor"]),
        repeatability_multiplier=float(payload["repeatability_multiplier"]),
    )
    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    gates = {
        "evaluation_count": len(records) + 2 == payload["evaluation_count"],
        "dae_invariance": assessment.pass_gate,
        "inventory_scaling": all(item["terminal_inventory_scaling_error_lbmol"] <= payload["inventory_scaling_limit"] for item in records),
        "fixed_algebraics": all(item["algebraic_coordinate_difference_inf_norm"] <= payload["fixed_algebraic_limit"] for item in records),
        "provider": provenance["pass"],
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd121_passed" if passed else "dd121_failed",
        "decision": "authorize_frozen_controlled_terminal_48x48_contract" if passed else "stop_for_hidden_terminal_owner_audit",
        "baseline_dae_scaled": _vector(baseline.dae_scaled),
        "baseline_terminal_scaled": _vector(baseline.terminal_scaled),
        "provider_repeatability_inf_norm": assessment.provider_repeatability_inf_norm,
        "invariance_limit": assessment.invariance_limit,
        "perturbations": records,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": passed,
        "audit_executed_once": True,
        "jacobian_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    worst = max(item["dae_residual_difference_inf_norm"] for item in records)
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-121 Core V3 Terminal Gauge-Invariance Audit",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Provider repeatability: `{assessment.provider_repeatability_inf_norm:.6e}`",
                f"- Invariance limit: `{assessment.invariance_limit:.6e}`",
                f"- Worst DAE change: `{worst:.6e}`",
                f"- DWSIM calls: `{provenance['total_calls']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                "",
                "DD-121 performed no Jacobian, nonlinear solve, timestep, controller action, or dynamics.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    args = parser.parse_args()
    result = prepare() if args.mode == "prepare" else execute()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
