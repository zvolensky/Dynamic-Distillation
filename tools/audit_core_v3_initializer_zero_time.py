#!/usr/bin/env python
"""Prepare or execute the frozen DD-114 canonical initializer zero-time audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
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
    audit_conserved_nu_pressure_initializer_contract,
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerNumericalSpec,
    audit_initializer_constraint_jacobian,
    evaluate_initializer_constraints,
)
from dynamic_distillation.core_v3.initializer_zero_time_audit_v1 import (
    compare_saved_initializer_endpoint,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit


SCHEMA = "dd114-core-v3-initializer-zero-time-audit-contract-v1"
RESULT_SCHEMA = "dd114-core-v3-initializer-zero-time-audit-result-v1"
DD112_CONTRACT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json")
DD112_RESULT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json")
DD113_RESULT = Path("logs/dd113_core_v3_dd112_physical_equivalence_adjudication_20260727.json")
CONTRACT = Path("logs/dd114_core_v3_initializer_zero_time_audit_contract_20260727.json")
RESULT = Path("logs/dd114_core_v3_initializer_zero_time_audit_20260727.json")
CONTRACT_DOC = Path("docs/dd_114_core_v3_initializer_zero_time_audit_contract_20260727.md")
RESULT_DOC = Path("docs/dd_114_core_v3_initializer_zero_time_audit_20260727.md")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
REPRODUCTION_LIMITS = {
    "inventory_scaled_difference": 1.0e-8,
    "lower_internal_energy_scaled_difference": 1.0e-8,
    "component_rate_scaled_difference": 1.0e-8,
    "internal_energy_rate_scaled_difference": 1.0e-8,
    "pressure_scaled_difference": 1.0e-8,
    "temperature_abs_difference_F": 1.0e-6,
    "liquid_flow_scaled_difference": 1.0e-8,
    "vapor_flow_scaled_difference": 1.0e-8,
    "distillate_scaled_difference": 1.0e-8,
    "bottoms_scaled_difference": 1.0e-8,
    "condenser_duty_scaled_difference": 1.0e-8,
}
COMPARISON_SCALES = {
    "material_rate_scale_lbmolph": 12584.8,
    "energy_rate_scale_BTUph": 55003568.3093669,
    "pressure_scale_psia": 10.0,
}
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/initializer_zero_time_audit_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_initializer_contract_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_initializer_numerical_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_numerical_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tests/test_core_v3_initializer_zero_time_audit_v1.py",
    "tools/audit_core_v3_initializer_zero_time.py",
    "tools/audit_core_v3_pressure_layer_numerical.py",
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


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def prepare() -> dict[str, Any]:
    dd112_contract = _load(DD112_CONTRACT)
    dd112_result = _load(DD112_RESULT)
    dd113 = _load(DD113_RESULT)
    if not dd113["pass"] or dd113["decision"] != "authorize_frozen_zero_time_initializer_audit":
        raise RuntimeError("DD-114 requires the passed DD-113 authorization")
    canonical_name = dd113["adjudication"]["canonical_start"]
    canonical = next(
        (item for item in dd112_result["starts"] if item["name"] == canonical_name),
        None,
    )
    if canonical is None:
        raise RuntimeError("DD-114 canonical endpoint is missing")
    contract = build_conserved_nu_pressure_initializer_contract(
        tuple(dd112_contract["source_mapping"]["component_names"])
    )
    if not audit_conserved_nu_pressure_initializer_contract(contract).pass_gate:
        raise RuntimeError("DD-114 structural prerequisite changed")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD112_CONTRACT, DD112_RESULT, DD113_RESULT)
        },
        "source_dd112_contract_commit": dd112_result["contract_commit"],
        "source_dd113_contract_commit": dd113["contract_commit"],
        "canonical_start": canonical_name,
        "canonical_coordinates": canonical["final_coordinates"],
        "canonical_coordinates_sha256": _hash(
            {"coordinates": canonical["final_coordinates"]}
        ),
        "jacobian_steps": list(JACOBIAN_STEPS),
        "constraint_limit": 1.0e-8,
        "required_constraint_rank": 52,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "colored_full_difference_limit": 1.0e-8,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "reproduction_limits": REPRODUCTION_LIMITS,
        "comparison_scales": COMPARISON_SCALES,
        "provider_call_limit": 50_000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "the DD-112 or DD-113 source hash changes",
            "the canonical coordinates or implementation hash changes",
            "any of the 52 live constraints exceeds 1e-8",
            "either endpoint Jacobian loses rank or fails condition, spectrum, registry, or colored/full agreement",
            "the fresh endpoint fails to reproduce the saved physical endpoint",
            "physicality, pressure ordering, conservation, or provider ownership fails",
            "the provider-call or wall-clock limit is exceeded",
            "a nonlinear solve, initializer, timestep, controller, or dynamic integration is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "residual_or_jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-114 Frozen Core V3 Initializer Zero-Time Audit Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                f"- Canonical endpoint: `{canonical_name}`",
                "- Live equations / coordinates: `52 / 65`",
                "- Jacobians: two 21-color steps plus one full cross-check",
                "- Nonlinear solve, initializer, timestep, or dynamics: `False`",
                "- Provider call / wall limits: `50000 / 180 s`",
                "",
                "One live zero-time execution is permitted only after this exact contract is committed. Passing authorizes only a separately frozen first-step refinement contract.",
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
        raise RuntimeError("DD-114 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-114 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-114 implementation changed: {path}")
    if _hash({"coordinates": payload["canonical_coordinates"]}) != payload["canonical_coordinates_sha256"]:
        raise RuntimeError("DD-114 canonical coordinates changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-114 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    dd112_contract = _load(DD112_CONTRACT)
    dd112_result = _load(DD112_RESULT)
    saved = next(
        item
        for item in dd112_result["starts"]
        if item["name"] == payload["canonical_start"]
    )
    if saved["final_coordinates"] != payload["canonical_coordinates"]:
        raise RuntimeError("DD-114 source endpoint changed")

    spec = dd102._spec(
        dd112_contract["source_mapping"],
        float(dd112_contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd102._reference(dd112_contract["reference"])
    template = dd102._state(dd112_contract["accepted_root_state"])
    contract = build_conserved_nu_pressure_initializer_contract(spec.component_names)
    if not audit_conserved_nu_pressure_initializer_contract(contract).pass_gate:
        raise RuntimeError("DD-114 structural prerequisite changed")
    provider = dd102._provider(
        Path(dd112_contract["workbook"]), dd112_contract["property_package"]
    )
    call_audit = ProviderCallAudit()
    molecular_weight = call_audit.component_molecular_weights(
        provider,
        caller="dd114_molecular_weight",
        state_id="dd114:preparation",
        evaluation_kind="preparation",
    )
    pressure_numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(dd112_contract["pressure_reference_psia"]),
        pressure_coordinate_scale_psia=float(dd112_contract["pressure_coordinate_scale_psia"]),
        pressure_residual_scale_psia=float(dd112_contract["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(dd112_contract["dry_tray_pressure_drop_coefficient"]),
        component_mw_lbm_per_lbmol=molecular_weight,
        link_geometry=tuple(
            PressureLinkGeometry(**item)
            for item in dd112_contract["pressure_link_geometry"]
        ),
        enforce_pressure_order=False,
    )
    numerical = InitializerNumericalSpec(
        inventory_reference_lbmol=np.asarray(dd112_contract["inventory_reference_lbmol"]),
        lower_internal_energy_reference_BTU=np.asarray(dd112_contract["lower_internal_energy_reference_BTU"]),
        lower_internal_energy_scale_BTU=np.asarray(dd112_contract["lower_internal_energy_scale_BTU"]),
        component_total_targets_lbmol=np.asarray(dd112_contract["component_total_targets_lbmol"]),
        stored_energy_target_BTU=float(dd112_contract["stored_energy_target_BTU"]),
        terminal_total_targets_lbmol=np.asarray(dd112_contract["terminal_total_targets_lbmol"]),
        objective_center=np.asarray(dd112_contract["objective_center"]),
        objective_weights=np.asarray(dd112_contract["objective_weights"]),
        lower_bounds=np.asarray(dd112_contract["lower_bounds"]),
        upper_bounds=np.asarray(dd112_contract["upper_bounds"]),
        jacobian_step=float(dd112_contract["solver"]["jacobian_step"]),
    )
    common = {
        "top_storage_gradient_BTU_lbmol": dd112_contract["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": dd112_contract["energy_rate_scales_BTUph"],
        "fixed_steady_scales": dd112_contract["fixed_steady_residual_scales"],
        "storage_scales_BTU": dd112_contract["storage_scales_BTU"],
        "pressure_numerical": pressure_numerical,
    }
    coordinates = np.asarray(payload["canonical_coordinates"], dtype=float)

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_initializer_constraints(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=candidate,
            state_id=state_id,
            evaluation_kind="jacobian",
            **common,
        ).scaled

    started = time.perf_counter()
    endpoint = evaluate_initializer_constraints(
        contract,
        numerical,
        spec,
        reference,
        template,
        provider,
        call_audit,
        coordinates=coordinates,
        state_id="dd114:canonical:endpoint",
        evaluation_kind="residual",
        **common,
    )
    jacobians = [
        audit_initializer_constraint_jacobian(
            contract,
            objective,
            coordinates,
            step=step,
            coupling_tolerance=float(payload["coupling_tolerance"]),
            use_coloring=True,
        )
        for step in payload["jacobian_steps"]
    ]
    full = audit_initializer_constraint_jacobian(
        contract,
        objective,
        coordinates,
        step=float(payload["jacobian_steps"][0]),
        coupling_tolerance=float(payload["coupling_tolerance"]),
        use_coloring=False,
    )
    elapsed = time.perf_counter() - started
    physical = endpoint.dae_evaluation.pressure_evaluation.base_evaluation.physical_state
    pressure = endpoint.dae_evaluation.pressure_evaluation.pressure_psia
    steady = endpoint.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
    fresh = {
        "inventory_lbmol": np.asarray(endpoint.inventory_lbmol).tolist(),
        "lower_internal_energy_BTU": _vector(endpoint.lower_internal_energy_BTU),
        "component_rate_lbmolph": np.asarray(endpoint.dae_evaluation.component_rate_lbmolph).tolist(),
        "internal_energy_rate_BTUph": _vector(endpoint.dae_evaluation.internal_energy_rate_BTUph),
        "pressure_psia": _vector(pressure),
        "temperature_F": _vector(physical.temperature_F),
        "liquid_flow_lbmolph": _vector(physical.hydraulic_liquid_flow_lbmolph),
        "vapor_flow_lbmolph": _vector(physical.vapor_flow_lbmolph),
        "distillate_lbmolph": float(physical.distillate_lbmolph),
        "bottoms_lbmolph": float(physical.bottoms_lbmolph),
        "condenser_duty_BTUph": float(physical.condenser_duty_BTUph),
        "liquid_mole_fraction": np.asarray(physical.liquid_mole_fraction).tolist(),
        "vapor_mole_fraction": np.asarray(physical.vapor_mole_fraction).tolist(),
        "bubble_vapor_mole_fraction": _vector(physical.bubble_vapor_mole_fraction),
    }
    reproduction = compare_saved_initializer_endpoint(
        saved,
        fresh,
        inventory_scale_lbmol=dd112_contract["inventory_reference_lbmol"],
        lower_energy_scale_BTU=dd112_contract["lower_internal_energy_scale_BTU"],
        limits=payload["reproduction_limits"],
        **payload["comparison_scales"],
    )
    provenance = call_audit.report()
    colored_full_difference = float(np.max(np.abs(jacobians[0].matrix - full.matrix)))
    spectrum_change = _spectrum_change(
        jacobians[0].singular_values, jacobians[1].singular_values
    )
    all_jacobians = (*jacobians, full)
    compositions = (
        np.asarray(physical.liquid_mole_fraction),
        np.asarray(physical.vapor_mole_fraction),
        np.asarray(physical.bubble_vapor_mole_fraction),
    )
    gates = {
        "constraints": float(np.max(np.abs(endpoint.scaled))) < payload["constraint_limit"],
        "rank": all(item.rank == payload["required_constraint_rank"] for item in all_jacobians),
        "condition": all(item.condition < payload["condition_limit"] for item in all_jacobians),
        "spectrum": spectrum_change < payload["spectrum_change_limit"],
        "structure": all(not item.zero_rows and not item.zero_columns and not item.unexpected_couplings for item in all_jacobians),
        "colored_full": colored_full_difference < payload["colored_full_difference_limit"],
        "saved_endpoint_reproduction": reproduction.pass_gate,
        "pressure_order": bool(np.all(np.diff(pressure) > 0.0)),
        "physical": bool(
            np.all(np.asarray(endpoint.inventory_lbmol) > 0.0)
            and np.all(np.asarray(physical.hydraulic_liquid_flow_lbmolph) > 0.0)
            and np.all(np.asarray(physical.vapor_flow_lbmolph) > 0.0)
            and physical.distillate_lbmolph > 0.0
            and physical.bottoms_lbmolph > 0.0
            and all(
                np.all(value > 0.0)
                and np.allclose(np.sum(value, axis=-1), 1.0, atol=1.0e-12)
                for value in compositions
            )
        ),
        "conservation": bool(
            abs(steady.component_telescoping_relative_error) < payload["component_conservation_limit"]
            and abs(steady.energy_telescoping_relative_error) < payload["energy_conservation_limit"]
        ),
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd114_passed" if passed else "dd114_failed",
        "decision": (
            "authorize_frozen_first_step_refinement_contract"
            if passed
            else "stop_pressure_enabled_initializer_handoff"
        ),
        "canonical_start": payload["canonical_start"],
        "constraint_inf_norm": float(np.max(np.abs(endpoint.scaled))),
        "component_total_residual_lbmol": _vector(endpoint.component_total_residual_lbmol),
        "stored_energy_residual_BTU": float(endpoint.stored_energy_residual_BTU),
        "terminal_total_residual_lbmol": _vector(endpoint.terminal_total_residual_lbmol),
        "component_conservation": float(steady.component_telescoping_relative_error),
        "energy_conservation": float(steady.energy_telescoping_relative_error),
        "jacobians": [
            {
                "kind": "colored" if item is not full else "full",
                "step": float(item.step),
                "rank": int(item.rank),
                "condition": float(item.condition),
                "singular_values": _vector(item.singular_values),
                "zero_rows": list(item.zero_rows),
                "zero_columns": list(item.zero_columns),
                "unexpected_couplings": list(item.unexpected_couplings),
                "color_count": int(item.color_count),
            }
            for item in all_jacobians
        ],
        "spectrum_change": spectrum_change,
        "colored_full_matrix_difference": colored_full_difference,
        "saved_endpoint_reproduction": asdict(reproduction),
        "fresh_endpoint": fresh,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": bool(passed),
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "audit_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-114 Core V3 Initializer Zero-Time Audit Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Constraint infinity norm: `{result['constraint_inf_norm']:.6e}`",
                f"- Provider calls: `{provenance['total_calls']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                "- Nonlinear solve, timestep, or dynamics: `False`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = prepare() if args.prepare else execute()
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if args.prepare or output["pass"] else 2)
