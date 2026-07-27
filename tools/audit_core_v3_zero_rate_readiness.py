#!/usr/bin/env python
"""Prepare or execute the frozen DD-119 live zero-rate readiness audit."""

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
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
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
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import (
    audit_zero_rate_jacobian,
    evaluate_zero_rate_readiness,
    zero_rate_pattern,
    zero_rate_row_names,
    zero_rate_variable_names,
)


SCHEMA = "dd119-core-v3-live-zero-rate-readiness-contract-v1"
RESULT_SCHEMA = "dd119-core-v3-live-zero-rate-readiness-result-v1"
CONTRACT = Path("logs/dd119_core_v3_live_zero_rate_readiness_contract_20260727.json")
RESULT = Path("logs/dd119_core_v3_live_zero_rate_readiness_20260727.json")
CONTRACT_DOC = Path("docs/dd_119_core_v3_live_zero_rate_readiness_contract_20260727.md")
RESULT_DOC = Path("docs/dd_119_core_v3_live_zero_rate_readiness_20260727.md")
DD112_CONTRACT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_contract_20260726.json")
DD112_RESULT = Path("logs/dd112_core_v3_conserved_nu_pressure_initializer_20260726.json")
DD115_RESULT = Path("logs/dd115_core_v3_initializer_first_step_refinement_20260727.json")
DD117_RESULT = Path("logs/dd117_core_v3_dd116_representation_gate_adjudication_20260727.json")
DD118_RESULT = Path("logs/dd118_core_v3_zero_rate_feasibility_20260727.json")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/zero_rate_readiness_v1.py",
    "src/dynamic_distillation/core_v3/zero_rate_feasibility_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_initializer_numerical_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "tests/test_core_v3_zero_rate_readiness_v1.py",
    "tools/audit_core_v3_zero_rate_readiness.py",
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


def _zero_point_from_initializer(coordinates: Any) -> np.ndarray:
    point = np.asarray(coordinates, dtype=float)
    if point.shape != (65,):
        raise RuntimeError("DD-119 expected a 65-coordinate initializer endpoint")
    return np.concatenate((point[:19], point[38:]))


def prepare() -> dict[str, Any]:
    source = _load(DD112_CONTRACT)
    dd112 = _load(DD112_RESULT)
    dd115 = _load(DD115_RESULT)
    dd117 = _load(DD117_RESULT)
    dd118 = _load(DD118_RESULT)
    if not dd117["pass"] or dd117["decision"] != "authorize_structural_zero_rate_feasibility_audit":
        raise RuntimeError("DD-119 requires the passed DD-117 adjudication")
    if not dd118["pass"] or dd118["decision"] != "authorize_frozen_live_zero_rate_readiness_contract":
        raise RuntimeError("DD-119 requires the passed DD-118 structural audit")
    canonical = next(
        item
        for item in dd112["starts"]
        if item["name"] == "dd094_storage_and_pressure_profile"
    )
    first = _zero_point_from_initializer(canonical["final_coordinates"])
    refined = dd115["outcomes"]["half2"]
    inventory_reference = np.asarray(source["inventory_reference_lbmol"], dtype=float)
    inventory = np.asarray(refined["inventory_lbmol"], dtype=float)
    lower_u_reference = np.asarray(source["lower_internal_energy_reference_BTU"], dtype=float)
    lower_u_scale = np.asarray(source["lower_internal_energy_scale_BTU"], dtype=float)
    state_coordinates = np.concatenate(
        (
            np.log(inventory / inventory_reference).reshape((-1,)),
            (
                np.asarray(refined["lower_internal_energy_BTU"], dtype=float)
                - lower_u_reference
            )
            / lower_u_scale,
        )
    )
    second = np.concatenate(
        (state_coordinates, np.asarray(refined["final_coordinates"], dtype=float)[19:])
    )
    columns = np.concatenate(
        (np.arange(19), np.arange(38, 65))
    )
    lower = np.asarray(source["lower_bounds"], dtype=float)[columns]
    upper = np.asarray(source["upper_bounds"], dtype=float)[columns]
    for name, point in (("dd112_canonical", first), ("dd115_refined_one_second", second)):
        if point.shape != (46,) or np.any(~np.isfinite(point)):
            raise RuntimeError(f"DD-119 state is invalid: {name}")
        if np.any(point <= lower) or np.any(point >= upper):
            raise RuntimeError(f"DD-119 state is outside the frozen bounds: {name}")
    contract = build_conserved_nu_pressure_initializer_contract(
        tuple(source["source_mapping"]["component_names"])
    )
    pattern = zero_rate_pattern(contract)
    groups = greedy_column_groups(pattern)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                DD112_CONTRACT,
                DD112_RESULT,
                DD115_RESULT,
                DD117_RESULT,
                DD118_RESULT,
            )
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "initializer_numerical": {
            key: source[key]
            for key in (
                "inventory_reference_lbmol",
                "lower_internal_energy_reference_BTU",
                "lower_internal_energy_scale_BTU",
                "component_total_targets_lbmol",
                "stored_energy_target_BTU",
                "terminal_total_targets_lbmol",
                "objective_center",
                "objective_weights",
                "lower_bounds",
                "upper_bounds",
            )
        },
        "top_storage_gradient_BTU_lbmol": source["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": source["energy_rate_scales_BTUph"],
        "storage_scales_BTU": source["storage_scales_BTU"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "pressure_reference_psia": source["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": source["pressure_coordinate_scale_psia"],
        "pressure_residual_scale_psia": source["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": source["dry_tray_pressure_drop_coefficient"],
        "pressure_link_geometry": source["pressure_link_geometry"],
        "variable_names": list(zero_rate_variable_names(contract)),
        "row_names": list(zero_rate_row_names(contract)),
        "pattern_shape": list(pattern.shape),
        "color_groups": [list(group) for group in groups],
        "color_count": len(groups),
        "states": [
            {"name": "dd112_canonical", "coordinates": _vector(first)},
            {"name": "dd115_refined_one_second", "coordinates": _vector(second)},
        ],
        "coordinate_definition": {
            "state": "unchanged DD-112 conserved N/U state coordinates",
            "rates": "removed from the unknown vector and fixed exactly to zero",
            "algebraic": "unchanged DD-112 transformed algebraic coordinates",
        },
        "governing_rows": "46 zero-rate DAE constraints plus two terminal total-holdup constraints",
        "diagnostic_rows": "three global component totals plus one global stored-energy total",
        "jacobian_steps": list(JACOBIAN_STEPS),
        "minimum_dae_rank": 44,
        "maximum_dae_nullity": 2,
        "required_augmented_rank": 46,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "colored_full_difference_limit": 1.0e-8,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "provider_call_limit": 20_000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "either frozen state fails live evaluation",
            "the terminal-augmented Jacobian loses full column rank or exceeds the condition limit",
            "the DAE-only Jacobian has more than two null directions or terminal rows fail to restore them",
            "finite-difference spectra, coloring, registered coupling, physicality, conservation, or provider ownership fail",
            "call or wall-clock limits are exceeded",
            "a nonlinear solve, timestep, controller, retry, fallback, or tolerance change is attempted",
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
                "# DD-119 Frozen Core V3 Live Zero-Rate Readiness Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Frozen states: DD-112 canonical and DD-115 refined one-second endpoint",
                "- Unknowns: `46` conserved-state and algebraic coordinates; all `19` rates fixed to zero",
                "- Residual: `48` rows (`46` DAE plus `2` terminal holdup constraints)",
                "- Released global component and energy totals: diagnostics only",
                f"- Colored Jacobian groups: `{len(groups)}`",
                "- Nonlinear solve, timestep, controller, or retry: `False`",
                "",
                "Execution is permitted once only after this exact contract is committed. Passing authorizes a separately frozen zero-rate root contract; it does not authorize a solve in DD-119.",
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
        raise RuntimeError("DD-119 contract checksum mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-119 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-119 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-119 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-119 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def _full_jacobian(objective, point: np.ndarray, step: float) -> np.ndarray:
    matrix = np.empty((48, 46), dtype=float)
    for column in range(46):
        delta = np.zeros(46)
        delta[column] = step
        plus = objective(point + delta, f"dd119:full:{column}:plus")
        minus = objective(point - delta, f"dd119:full:{column}:minus")
        matrix[:, column] = (plus - minus) / (2.0 * step)
    return matrix


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
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
        caller="dd119_molecular_weight",
        state_id="dd119:preparation",
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
        jacobian_step=float(payload["jacobian_steps"][0]),
    )
    common = {
        "top_storage_gradient_BTU_lbmol": payload["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "pressure_numerical": pressure_numerical,
    }

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
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
            evaluation_kind="jacobian" if "color" in state_id or "full" in state_id else "residual",
            **common,
        ).scaled

    started = time.perf_counter()
    records = []
    canonical_colored = None
    for state_index, state in enumerate(payload["states"]):
        point = np.asarray(state["coordinates"], dtype=float)
        endpoint = evaluate_zero_rate_readiness(
            contract,
            numerical,
            spec,
            reference,
            template,
            provider,
            call_audit,
            coordinates=point,
            state_id=f"dd119:{state['name']}:endpoint",
            evaluation_kind="residual",
            **common,
        )
        jacobians = [
            audit_zero_rate_jacobian(
                contract,
                objective,
                point,
                endpoint.scaled,
                step=float(step),
                coupling_tolerance=float(payload["coupling_tolerance"]),
                state_id=f"dd119:{state['name']}:{step:g}",
            )
            for step in payload["jacobian_steps"]
        ]
        if state_index == 0:
            canonical_colored = jacobians[0].matrix.copy()
        physical = endpoint.full_evaluation.dae_evaluation.pressure_evaluation.base_evaluation.physical_state
        pressure = endpoint.full_evaluation.dae_evaluation.pressure_evaluation.pressure_psia
        steady = endpoint.full_evaluation.dae_evaluation.pressure_evaluation.base_evaluation.steady_evaluation
        records.append(
            {
                "name": state["name"],
                "residual_inf_norm": float(np.max(np.abs(endpoint.scaled))),
                "dae_residual_inf_norm": float(np.max(np.abs(endpoint.dae_scaled))),
                "terminal_scaled_residual": _vector(endpoint.terminal_scaled),
                "component_total_residual_lbmol": _vector(endpoint.component_total_residual_lbmol),
                "stored_energy_residual_BTU": endpoint.stored_energy_residual_BTU,
                "terminal_total_residual_lbmol": _vector(endpoint.terminal_total_residual_lbmol),
                "component_conservation": float(steady.component_telescoping_relative_error),
                "energy_conservation": float(steady.energy_telescoping_relative_error),
                "pressure_psia": _vector(pressure),
                "temperature_F": _vector(physical.temperature_F),
                "inventory_lbmol": np.asarray(endpoint.full_evaluation.inventory_lbmol).tolist(),
                "liquid_flow_lbmolph": _vector(physical.hydraulic_liquid_flow_lbmolph),
                "vapor_flow_lbmolph": _vector(physical.vapor_flow_lbmolph),
                "distillate_lbmolph": float(physical.distillate_lbmolph),
                "bottoms_lbmolph": float(physical.bottoms_lbmolph),
                "condenser_duty_BTUph": float(physical.condenser_duty_BTUph),
                "spectrum_change": _spectrum_change(
                    jacobians[0].augmented_singular_values,
                    jacobians[1].augmented_singular_values,
                ),
                "jacobians": [
                    {
                        "step": item.step,
                        "augmented_rank": item.augmented_rank,
                        "dae_rank": item.dae_rank,
                        "rank_gain_from_terminal_rows": item.augmented_rank - item.dae_rank,
                        "augmented_condition": item.augmented_condition,
                        "dae_condition": item.dae_condition,
                        "augmented_singular_values": _vector(item.augmented_singular_values),
                        "dae_singular_values": _vector(item.dae_singular_values),
                        "zero_rows": list(item.zero_rows),
                        "zero_columns": list(item.zero_columns),
                        "unexpected_couplings": list(item.unexpected_couplings),
                        "color_count": item.color_count,
                        "left_null_projection_norm": item.left_null_projection_norm,
                    }
                    for item in jacobians
                ],
            }
        )
    if canonical_colored is None:
        raise RuntimeError("DD-119 canonical Jacobian was not evaluated")
    full = _full_jacobian(
        objective,
        np.asarray(payload["states"][0]["coordinates"], dtype=float),
        float(payload["jacobian_steps"][0]),
    )
    colored_full_difference = float(np.max(np.abs(canonical_colored - full)))
    pattern = zero_rate_pattern(contract)
    unexpected_full = tuple(
        f"{payload['row_names'][row]} <- {payload['variable_names'][column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(full) > payload["coupling_tolerance"]))
        )
    )
    elapsed = time.perf_counter() - started
    provenance = call_audit.report()
    audits = [item for record in records for item in record["jacobians"]]
    gates = {
        "finite_residuals": all(np.isfinite(record["residual_inf_norm"]) for record in records),
        "dae_rank": all(item["dae_rank"] >= payload["minimum_dae_rank"] for item in audits),
        "dae_nullity": all(46 - item["dae_rank"] <= payload["maximum_dae_nullity"] for item in audits),
        "augmented_rank": all(item["augmented_rank"] == payload["required_augmented_rank"] for item in audits),
        "terminal_rank_restoration": all(
            item["rank_gain_from_terminal_rows"] == 46 - item["dae_rank"] for item in audits
        ),
        "condition": all(item["augmented_condition"] < payload["condition_limit"] for item in audits),
        "spectrum": all(record["spectrum_change"] < payload["spectrum_change_limit"] for record in records),
        "structure": all(
            not item["zero_rows"] and not item["zero_columns"] and not item["unexpected_couplings"]
            for item in audits
        ) and not unexpected_full,
        "colored_full": colored_full_difference < payload["colored_full_difference_limit"],
        "pressure_order": all(np.all(np.diff(record["pressure_psia"]) > 0.0) for record in records),
        "physical": all(
            np.all(np.asarray(record["inventory_lbmol"]) > 0.0)
            and np.all(np.asarray(record["liquid_flow_lbmolph"]) > 0.0)
            and np.all(np.asarray(record["vapor_flow_lbmolph"]) > 0.0)
            and record["distillate_lbmolph"] > 0.0
            and record["bottoms_lbmolph"] > 0.0
            and np.all(np.isfinite(record["temperature_F"]))
            for record in records
        ),
        "conservation": all(
            abs(record["component_conservation"]) < payload["component_conservation_limit"]
            and abs(record["energy_conservation"]) < payload["energy_conservation_limit"]
            for record in records
        ),
        "provider": provenance["pass"],
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd119_passed" if passed else "dd119_failed",
        "decision": (
            "authorize_frozen_zero_rate_root_contract"
            if passed
            else "stop_zero_rate_initializer_path"
        ),
        "states": records,
        "canonical_colored_full_matrix_difference": colored_full_difference,
        "canonical_full_unexpected_couplings": list(unexpected_full),
        "provider_provenance": provenance,
        "wall_clock_sec": elapsed,
        "gates": gates,
        "pass": passed,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "retry_attempted": False,
        "campaign_executed_once": True,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-119 Core V3 Live Zero-Rate Readiness Audit",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- DWSIM calls: `{provenance['total_calls']}`",
                f"- Canonical colored/full Jacobian difference: `{colored_full_difference:.6e}`",
                f"- DAE ranks: `{[item['jacobians'][0]['dae_rank'] for item in records]}`",
                f"- Terminal-augmented ranks: `{[item['jacobians'][0]['augmented_rank'] for item in records]}`",
                f"- Augmented conditions: `{[item['jacobians'][0]['augmented_condition'] for item in records]}`",
                f"- Gates: `{gates}`",
                "",
                "DD-119 performed no nonlinear solve or timestep. Passing authorizes only a separately frozen zero-rate root contract.",
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
