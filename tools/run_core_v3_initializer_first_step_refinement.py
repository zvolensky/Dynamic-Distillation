#!/usr/bin/env python
"""Prepare or execute the frozen DD-115 initializer first-step refinement."""

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
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.conserved_nu_implicit_step_v1 import (
    audit_conserved_nu_step_jacobian,
    conserved_nu_step_pattern,
    evaluate_conserved_nu_backward_euler_residual,
    solve_conserved_nu_backward_euler_step,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    audit_conserved_nu_pressure_dae_contract,
    build_conserved_nu_pressure_dae_contract,
)
from dynamic_distillation.core_v3.implicit_step_v1 import ImplicitStepSettings
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit


SCHEMA = "dd115-core-v3-initializer-first-step-refinement-contract-v1"
RESULT_SCHEMA = "dd115-core-v3-initializer-first-step-refinement-result-v1"
DD112_CONTRACT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json")
DD112_RESULT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json")
DD114_RESULT = Path("logs/dd114_core_v3_initializer_zero_time_audit_20260727.json")
CONTRACT = Path("logs/dd115_core_v3_initializer_first_step_refinement_contract_20260727.json")
RESULT = Path("logs/dd115_core_v3_initializer_first_step_refinement_20260727.json")
CONTRACT_DOC = Path("docs/dd_115_core_v3_initializer_first_step_refinement_contract_20260727.md")
RESULT_DOC = Path("docs/dd_115_core_v3_initializer_first_step_refinement_20260727.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/conserved_nu_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_numerical_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tests/test_core_v3_conserved_nu_implicit_step_v1.py",
    "tools/run_core_v3_initializer_first_step_refinement.py",
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
    dd114 = _load(DD114_RESULT)
    if not dd114["pass"] or dd114["decision"] != "authorize_frozen_first_step_refinement_contract":
        raise RuntimeError("DD-115 requires the passed DD-114 authorization")
    canonical_name = dd114["canonical_start"]
    canonical = next(
        (item for item in dd112_result["starts"] if item["name"] == canonical_name),
        None,
    )
    if canonical is None:
        raise RuntimeError("DD-115 canonical endpoint is missing")
    contract = build_conserved_nu_pressure_dae_contract(
        tuple(dd112_contract["source_mapping"]["component_names"])
    )
    structural = audit_conserved_nu_pressure_dae_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-115 structural prerequisite changed")
    pattern = conserved_nu_step_pattern(contract)
    groups = greedy_column_groups(pattern)
    settings = ImplicitStepSettings(
        method="trf",
        ftol=1.0e-12,
        xtol=1.0e-12,
        gtol=1.0e-12,
        max_nfev=50,
        x_scale=1.0,
        jacobian_step=1.0e-5,
        jacobian_mode="colored",
    )
    lower_u = canonical["lower_internal_energy_BTU"]
    top_u = float(dd112_contract["stored_energy_target_BTU"] - np.sum(lower_u))
    initial_coordinates = canonical["final_coordinates"][19:]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD112_CONTRACT, DD112_RESULT, DD114_RESULT)
        },
        "source_dd114_contract_commit": dd114["contract_commit"],
        "canonical_start": canonical_name,
        "previous_inventory_lbmol": canonical["inventory_lbmol"],
        "previous_top_internal_energy_BTU": top_u,
        "previous_lower_internal_energy_BTU": lower_u,
        "initial_component_rate_lbmolph": canonical["component_rate_lbmolph"],
        "initial_internal_energy_rate_BTUph": canonical["internal_energy_rate_BTUph"],
        "component_rate_scale_lbmolph": 12584.8,
        "initial_coordinates": initial_coordinates,
        "initial_coordinates_sha256": _hash({"coordinates": initial_coordinates}),
        "grid": {
            "coarse": [1.0],
            "refined": [0.5, 0.5],
            "common_endpoint_seconds": 1.0,
        },
        "solver": asdict(settings),
        "step_pattern_shape": list(pattern.shape),
        "step_color_count": len(groups),
        "endpoint_jacobian_step": 1.0e-5,
        "spectrum_check_step": 5.0e-6,
        "required_rank": 46,
        "residual_limit": 1.0e-8,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "inventory_refinement_limit": 1.0e-4,
        "lower_energy_refinement_limit": 1.0e-4,
        "top_energy_refinement_limit": 1.0e-4,
        "algebraic_refinement_limit": 1.0e-3,
        "pressure_refinement_limit_psia": 1.0e-2,
        "temperature_refinement_limit_F": 1.0e-2,
        "flow_refinement_limit": 1.0e-3,
        "initial_component_rate_consistency_limit": 1.0e-3,
        "initial_energy_rate_consistency_limit": 1.0e-3,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "discrete_kinematic_limit": 1.0e-12,
        "provider_call_limit": 100_000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "a DD-112 or DD-114 source hash changes",
            "the canonical state, rate predictor, or initial-coordinate hash changes",
            "any of the three precommitted solves fails or exceeds the residual limit",
            "an endpoint Jacobian loses rank or fails condition, spectrum, or registry gates",
            "the one-second coarse and refined endpoints exceed any frozen refinement limit",
            "the first numerical rates disagree materially with the accepted zero-time rates",
            "physicality, pressure ordering, conservation, provider, call, or wall gates fail",
            "a retry, alternate solver, changed step, changed tolerance, controller, or longer trajectory is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-115 Frozen Core V3 Initializer First-Step Refinement Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                f"- Canonical endpoint: `{canonical_name}`",
                "- Coarse/refined grids to `t=1 s`: `1 x 1.0 s / 2 x 0.5 s`",
                "- System: exact conserved-N/U `46 x 46` backward Euler",
                f"- Colored Jacobian groups: `{len(groups)}`",
                "- Solver: one frozen trust-region configuration, no retry",
                "- Controllers or longer trajectory: `False`",
                "",
                "Execution is permitted once only after this exact contract is committed. Passing authorizes only a separately frozen short open-loop trajectory contract.",
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
        raise RuntimeError("DD-115 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-115 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-115 implementation changed: {path}")
    if _hash({"coordinates": payload["initial_coordinates"]}) != payload["initial_coordinates_sha256"]:
        raise RuntimeError("DD-115 initial coordinates changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-115 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    source = _load(DD112_CONTRACT)
    spec = dd102._spec(
        source["source_mapping"], float(source["operating_spec"]["feed_enthalpy_BTUph"])
    )
    reference = dd102._reference(source["reference"])
    template = dd102._state(source["accepted_root_state"])
    contract = build_conserved_nu_pressure_dae_contract(spec.component_names)
    if not audit_conserved_nu_pressure_dae_contract(contract).pass_gate:
        raise RuntimeError("DD-115 structural prerequisite changed")
    provider = dd102._provider(Path(source["workbook"]), source["property_package"])
    call_audit = ProviderCallAudit()
    molecular_weight = call_audit.component_molecular_weights(
        provider,
        caller="dd115_molecular_weight",
        state_id="dd115:preparation",
        evaluation_kind="preparation",
    )
    pressure_numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(source["pressure_reference_psia"]),
        pressure_coordinate_scale_psia=float(source["pressure_coordinate_scale_psia"]),
        pressure_residual_scale_psia=float(source["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(source["dry_tray_pressure_drop_coefficient"]),
        component_mw_lbm_per_lbmol=molecular_weight,
        link_geometry=tuple(
            PressureLinkGeometry(**item) for item in source["pressure_link_geometry"]
        ),
        enforce_pressure_order=False,
    )
    settings = ImplicitStepSettings(**payload["solver"])
    common = {
        "component_rate_scale_lbmolph": float(payload["component_rate_scale_lbmolph"]),
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "fixed_steady_scales": source["fixed_steady_residual_scales"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "numerical": pressure_numerical,
    }

    def make_objective(previous_n, previous_top_u, previous_lower_u, step_seconds):
        def objective(point: np.ndarray, state_id: str):
            return evaluate_conserved_nu_backward_euler_residual(
                contract,
                spec,
                reference,
                template,
                provider,
                call_audit,
                previous_inventory_lbmol=previous_n,
                previous_top_internal_energy_BTU=previous_top_u,
                previous_lower_internal_energy_BTU=previous_lower_u,
                solve_coordinates=point,
                step_seconds=step_seconds,
                state_id=state_id,
                evaluation_kind=("jacobian" if "jacobian" in state_id else "residual"),
                **common,
            )
        return objective

    previous_n = np.asarray(payload["previous_inventory_lbmol"], dtype=float)
    previous_top_u = float(payload["previous_top_internal_energy_BTU"])
    previous_lower_u = np.asarray(payload["previous_lower_internal_energy_BTU"], dtype=float)
    initial = np.asarray(payload["initial_coordinates"], dtype=float)
    started = time.perf_counter()
    coarse_objective = make_objective(previous_n, previous_top_u, previous_lower_u, 1.0)
    coarse = solve_conserved_nu_backward_euler_step(
        contract, coarse_objective, initial, settings, name="dd115:coarse"
    )
    half1_objective = make_objective(previous_n, previous_top_u, previous_lower_u, 0.5)
    half1 = solve_conserved_nu_backward_euler_step(
        contract, half1_objective, initial, settings, name="dd115:half1"
    )
    half1_evaluation = half1.evaluation
    half2_objective = make_objective(
        half1_evaluation.endpoint_inventory_lbmol,
        half1_evaluation.endpoint_top_internal_energy_BTU,
        half1_evaluation.endpoint_lower_internal_energy_BTU,
        0.5,
    )
    half2 = solve_conserved_nu_backward_euler_step(
        contract,
        half2_objective,
        half1.final_coordinates,
        settings,
        name="dd115:half2",
    )
    endpoint_audits = {
        "coarse": [
            audit_conserved_nu_step_jacobian(
                contract,
                coarse_objective,
                coarse.final_coordinates,
                step=float(payload["endpoint_jacobian_step"]),
                coupling_tolerance=float(payload["coupling_tolerance"]),
            ),
            audit_conserved_nu_step_jacobian(
                contract,
                coarse_objective,
                coarse.final_coordinates,
                step=float(payload["spectrum_check_step"]),
                coupling_tolerance=float(payload["coupling_tolerance"]),
            ),
        ],
        "half1": [
            audit_conserved_nu_step_jacobian(
                contract,
                half1_objective,
                half1.final_coordinates,
                step=float(payload["endpoint_jacobian_step"]),
                coupling_tolerance=float(payload["coupling_tolerance"]),
            )
        ],
        "half2": [
            audit_conserved_nu_step_jacobian(
                contract,
                half2_objective,
                half2.final_coordinates,
                step=float(payload["endpoint_jacobian_step"]),
                coupling_tolerance=float(payload["coupling_tolerance"]),
            )
        ],
    }
    elapsed = time.perf_counter() - started
    outcomes = {"coarse": coarse, "half1": half1, "half2": half2}

    def physical(outcome):
        return outcome.evaluation.dae_evaluation.pressure_evaluation.base_evaluation.physical_state

    def pressure(outcome):
        return outcome.evaluation.dae_evaluation.pressure_evaluation.pressure_psia

    coarse_eval = coarse.evaluation
    refined_eval = half2.evaluation
    coarse_physical = physical(coarse)
    refined_physical = physical(half2)
    material_scale = float(common["component_rate_scale_lbmolph"])
    energy_scale = float(max(source["energy_rate_scales_BTUph"]))
    inventory_scale = np.asarray(payload["previous_inventory_lbmol"], dtype=float)
    lower_u_scale = np.asarray(source["lower_internal_energy_scale_BTU"], dtype=float)
    top_u_scale = max(abs(previous_top_u), 1.0)
    algebraic_start = 19
    refinement = {
        "inventory": float(np.max(np.abs(coarse_eval.endpoint_inventory_lbmol - refined_eval.endpoint_inventory_lbmol) / inventory_scale)),
        "lower_energy": float(np.max(np.abs(coarse_eval.endpoint_lower_internal_energy_BTU - refined_eval.endpoint_lower_internal_energy_BTU) / lower_u_scale)),
        "top_energy": abs(coarse_eval.endpoint_top_internal_energy_BTU - refined_eval.endpoint_top_internal_energy_BTU) / top_u_scale,
        "algebraic": float(np.max(np.abs(coarse.final_coordinates[algebraic_start:] - half2.final_coordinates[algebraic_start:]))),
        "pressure_psia": float(np.max(np.abs(pressure(coarse) - pressure(half2)))),
        "temperature_F": float(np.max(np.abs(np.asarray(coarse_physical.temperature_F) - np.asarray(refined_physical.temperature_F)))),
        "liquid_flow": float(np.max(np.abs(np.asarray(coarse_physical.hydraulic_liquid_flow_lbmolph) - np.asarray(refined_physical.hydraulic_liquid_flow_lbmolph))) / material_scale),
        "vapor_flow": float(np.max(np.abs(np.asarray(coarse_physical.vapor_flow_lbmolph) - np.asarray(refined_physical.vapor_flow_lbmolph))) / material_scale),
    }
    initial_component_rate = np.asarray(payload["initial_component_rate_lbmolph"])
    initial_energy_rate = np.asarray(payload["initial_internal_energy_rate_BTUph"])
    rate_consistency = {
        "coarse_component": float(np.max(np.abs(coarse_eval.component_rate_lbmolph - initial_component_rate)) / material_scale),
        "half1_component": float(np.max(np.abs(half1_evaluation.component_rate_lbmolph - initial_component_rate)) / material_scale),
        "coarse_energy": float(np.max(np.abs(coarse_eval.internal_energy_rate_BTUph - initial_energy_rate)) / energy_scale),
        "half1_energy": float(np.max(np.abs(half1_evaluation.internal_energy_rate_BTUph - initial_energy_rate)) / energy_scale),
    }

    def kinematic_errors(outcome, step_seconds):
        evaluation = outcome.evaluation
        step_hours = step_seconds / 3600.0
        component_denominator = np.maximum(np.abs(evaluation.endpoint_inventory_lbmol), 1.0)
        component = float(np.max(np.abs(
            evaluation.endpoint_inventory_lbmol
            - evaluation.previous_inventory_lbmol
            - step_hours * evaluation.component_rate_lbmolph
        ) / component_denominator))
        previous_energy = np.concatenate((
            np.asarray((evaluation.previous_top_internal_energy_BTU,)),
            evaluation.previous_lower_internal_energy_BTU,
        ))
        endpoint_energy = np.concatenate((
            np.asarray((evaluation.endpoint_top_internal_energy_BTU,)),
            evaluation.endpoint_lower_internal_energy_BTU,
        ))
        energy = float(np.max(np.abs(
            endpoint_energy - previous_energy - step_hours * evaluation.internal_energy_rate_BTUph
        ) / np.maximum(np.abs(endpoint_energy), 1.0)))
        return component, energy

    kinematic = {
        name: dict(zip(("component", "energy"), kinematic_errors(outcome, 1.0 if name == "coarse" else 0.5)))
        for name, outcome in outcomes.items()
    }
    all_audits = [item for values in endpoint_audits.values() for item in values]
    spectrum_change = _spectrum_change(
        endpoint_audits["coarse"][0].singular_values,
        endpoint_audits["coarse"][1].singular_values,
    )
    provenance = call_audit.report()
    gates = {
        "solver_success": all(outcome.success for outcome in outcomes.values()),
        "residual": all(outcome.final_scaled_residual_inf_norm < payload["residual_limit"] for outcome in outcomes.values()),
        "rank": all(item.rank == payload["required_rank"] for item in all_audits),
        "condition": all(item.condition < payload["condition_limit"] for item in all_audits),
        "spectrum": spectrum_change < payload["spectrum_change_limit"],
        "structure": all(not item.zero_rows and not item.zero_columns and not item.unexpected_couplings for item in all_audits),
        "grid_refinement": bool(
            refinement["inventory"] < payload["inventory_refinement_limit"]
            and refinement["lower_energy"] < payload["lower_energy_refinement_limit"]
            and refinement["top_energy"] < payload["top_energy_refinement_limit"]
            and refinement["algebraic"] < payload["algebraic_refinement_limit"]
            and refinement["pressure_psia"] < payload["pressure_refinement_limit_psia"]
            and refinement["temperature_F"] < payload["temperature_refinement_limit_F"]
            and refinement["liquid_flow"] < payload["flow_refinement_limit"]
            and refinement["vapor_flow"] < payload["flow_refinement_limit"]
        ),
        "initial_rate_consistency": bool(
            rate_consistency["coarse_component"] < payload["initial_component_rate_consistency_limit"]
            and rate_consistency["half1_component"] < payload["initial_component_rate_consistency_limit"]
            and rate_consistency["coarse_energy"] < payload["initial_energy_rate_consistency_limit"]
            and rate_consistency["half1_energy"] < payload["initial_energy_rate_consistency_limit"]
        ),
        "pressure_order": all(np.all(np.diff(pressure(outcome)) > 0.0) for outcome in outcomes.values()),
        "physical": all(
            np.all(outcome.evaluation.endpoint_inventory_lbmol > 0.0)
            and np.all(np.asarray(physical(outcome).hydraulic_liquid_flow_lbmolph) > 0.0)
            and np.all(np.asarray(physical(outcome).vapor_flow_lbmolph) > 0.0)
            for outcome in outcomes.values()
        ),
        "conservation": all(
            abs(outcome.evaluation.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation.component_telescoping_relative_error) < payload["component_conservation_limit"]
            and abs(outcome.evaluation.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation.energy_telescoping_relative_error) < payload["energy_conservation_limit"]
            for outcome in outcomes.values()
        ),
        "discrete_kinematics": all(
            max(values.values()) < payload["discrete_kinematic_limit"]
            for values in kinematic.values()
        ),
        "provider": bool(provenance["pass"]),
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())

    def outcome_record(name, outcome):
        evaluation = outcome.evaluation
        state = physical(outcome)
        return {
            "name": name,
            "success": outcome.success,
            "status": outcome.status,
            "message": outcome.message,
            "nfev": outcome.nfev,
            "njev": outcome.njev,
            "wall_clock_sec": outcome.wall_clock_sec,
            "residual_inf_norm": outcome.final_scaled_residual_inf_norm,
            "final_coordinates": _vector(outcome.final_coordinates),
            "inventory_lbmol": np.asarray(evaluation.endpoint_inventory_lbmol).tolist(),
            "top_internal_energy_BTU": evaluation.endpoint_top_internal_energy_BTU,
            "lower_internal_energy_BTU": _vector(evaluation.endpoint_lower_internal_energy_BTU),
            "component_rate_lbmolph": np.asarray(evaluation.component_rate_lbmolph).tolist(),
            "internal_energy_rate_BTUph": _vector(evaluation.internal_energy_rate_BTUph),
            "pressure_psia": _vector(pressure(outcome)),
            "temperature_F": _vector(state.temperature_F),
            "liquid_flow_lbmolph": _vector(state.hydraulic_liquid_flow_lbmolph),
            "vapor_flow_lbmolph": _vector(state.vapor_flow_lbmolph),
            "distillate_lbmolph": float(state.distillate_lbmolph),
            "bottoms_lbmolph": float(state.bottoms_lbmolph),
            "condenser_duty_BTUph": float(state.condenser_duty_BTUph),
        }

    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd115_passed" if passed else "dd115_failed",
        "decision": (
            "authorize_frozen_short_open_loop_contract"
            if passed
            else "stop_initializer_dynamic_handoff"
        ),
        "outcomes": {name: outcome_record(name, outcome) for name, outcome in outcomes.items()},
        "jacobians": {
            name: [
                {
                    "step": item.step,
                    "rank": item.rank,
                    "condition": item.condition,
                    "singular_values": _vector(item.singular_values),
                    "zero_rows": list(item.zero_rows),
                    "zero_columns": list(item.zero_columns),
                    "unexpected_couplings": list(item.unexpected_couplings),
                    "color_count": item.color_count,
                }
                for item in values
            ]
            for name, values in endpoint_audits.items()
        },
        "spectrum_change": spectrum_change,
        "refinement": refinement,
        "initial_rate_consistency": rate_consistency,
        "discrete_kinematics": kinematic,
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": bool(passed),
        "retry_attempted": False,
        "controller_attempted": False,
        "longer_trajectory_attempted": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-115 Core V3 Initializer First-Step Refinement Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Provider calls: `{provenance['total_calls']}`",
                f"- Inventory refinement: `{refinement['inventory']:.6e}`",
                f"- Algebraic refinement: `{refinement['algebraic']:.6e}`",
                f"- Pressure refinement: `{refinement['pressure_psia']:.6e} psia`",
                "- Retry, controller, or longer trajectory: `False`",
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
