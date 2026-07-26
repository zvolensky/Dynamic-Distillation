#!/usr/bin/env python
"""Prepare or execute the frozen DD-109 live conserved-N/U pressure audit."""

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
from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    audit_conserved_nu_pressure_dae_contract,
    build_conserved_nu_pressure_dae_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_numerical_v1 import (
    audit_conserved_nu_leading_jacobian,
    evaluate_conserved_nu_pressure_residual,
    nu_pressure_pattern,
    nu_pressure_variable_names,
)
from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import residual_rows


SCHEMA = "dd109-core-v3-conserved-nu-pressure-numerical-contract-v1"
RESULT_SCHEMA = "dd109-core-v3-conserved-nu-pressure-numerical-result-v1"
CONTRACT = Path("logs/dd109_core_v3_conserved_nu_pressure_numerical_contract_20260726.json")
RESULT = Path("logs/dd109_core_v3_conserved_nu_pressure_numerical_20260726.json")
CONTRACT_DOC = Path("docs/dd_109_core_v3_conserved_nu_pressure_numerical_contract_20260726.md")
RESULT_DOC = Path("docs/dd_109_core_v3_conserved_nu_pressure_numerical_20260726.md")
DD108 = Path("logs/dd108_core_v3_conserved_nu_pressure_dae_20260726.json")
DD107 = Path("logs/dd107_core_v3_pressure_initializer_readiness_20260726.json")
DD103_CONTRACT = Path("logs/dd103_core_v3_pressure_layer_steady_root_contract_20260726.json")
DD103_RESULT = Path("logs/dd103_core_v3_pressure_layer_steady_root_20260726.json")
DD096_RESULT = Path("logs/dd096_core_v3_dynamic_dae_numerical_20260725.json")
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/conserved_nu_pressure_numerical_v1.py",
    "src/dynamic_distillation/core_v3/pressure_layer_numerical_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "tools/audit_core_v3_conserved_nu_pressure_numerical.py",
    "tests/test_core_v3_conserved_nu_pressure_dae_contract_v1.py",
    "tests/test_core_v3_conserved_nu_pressure_numerical_v1.py",
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
    structural = _load(DD108)
    readiness = _load(DD107)
    source = _load(DD103_CONTRACT)
    pressure_result = _load(DD103_RESULT)
    storage_result = _load(DD096_RESULT)
    if not structural["audit"]["pass_gate"]:
        raise RuntimeError("DD-109 requires passed DD-108")
    if readiness["decision"] != "stop_dd106_before_live_execution":
        raise RuntimeError("DD-109 requires the DD-107 ownership stop")
    storage_step = storage_result["storage_gradient"]["steps"][0]
    internal_energy = np.asarray(storage_step["internal_energy_BTU"], dtype=float)
    top_gradient = np.asarray(storage_step["gradient_BTU_lbmol"], dtype=float)[0]
    spec = dd102._spec(
        source["source_mapping"],
        float(source["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    rows = residual_rows(spec)
    fixed_scales = np.asarray(source["fixed_steady_residual_scales"], dtype=float)
    energy_scales = np.asarray(
        [fixed_scales[index] for index, row in enumerate(rows) if row.block == "energy_balance"],
        dtype=float,
    )
    if energy_scales.shape != (5,):
        raise RuntimeError("DD-109 could not reconstruct fixed energy scales")
    accepted = np.asarray(source["starts"][0]["coordinates"], dtype=float)
    pressure_endpoint = np.asarray(
        pressure_result["starts"][0]["final_coordinates"], dtype=float
    )
    states = (
        {
            "name": "dd094_state_dd094_algebraic_pressure_profile",
            "solve_coordinates": _vector(np.concatenate((np.zeros(19), accepted))),
            "storage_closure_must_pass": True,
        },
        {
            "name": "dd094_state_dd103_pressure_endpoint_guess",
            "solve_coordinates": _vector(np.concatenate((np.zeros(19), pressure_endpoint))),
            "storage_closure_must_pass": False,
        },
    )
    contract = build_conserved_nu_pressure_dae_contract(spec.component_names)
    pattern = nu_pressure_pattern(contract)
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD108, DD107, DD103_CONTRACT, DD103_RESULT, DD096_RESULT)
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "inventory_lbmol": source["dynamic_inventory_lbmol"],
        "lower_internal_energy_BTU": _vector(internal_energy[1:]),
        "top_storage_gradient_BTU_lbmol": _vector(top_gradient),
        "energy_rate_scales_BTUph": _vector(energy_scales[1:]),
        "storage_scales_BTU": _vector(np.maximum(np.abs(internal_energy[1:]), 1.0)),
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "pressure_reference_psia": source["pressure_reference_psia"],
        "pressure_coordinate_scale_psia": source["pressure_coordinate_scale_psia"],
        "pressure_residual_scale_psia": source["pressure_residual_scale_psia"],
        "dry_tray_pressure_drop_coefficient": source["dry_tray_pressure_drop_coefficient"],
        "pressure_link_geometry": source["pressure_link_geometry"],
        "states": list(states),
        "solve_variable_names": list(nu_pressure_variable_names(contract)),
        "row_names": [row.name for row in contract.rows],
        "color_groups": [list(group) for group in greedy_column_groups(pattern)],
        "color_count": len(greedy_column_groups(pattern)),
        "jacobian_steps": list(JACOBIAN_STEPS),
        "required_rank": 46,
        "storage_constraint_rank": 4,
        "condition_limit": 1.0e8,
        "spectrum_change_limit": 0.25,
        "coupling_tolerance": 1.0e-7,
        "colored_full_matrix_difference_limit": 1.0e-8,
        "canonical_storage_scaled_residual_limit": 1.0e-10,
        "component_conservation_limit": 1.0e-12,
        "energy_conservation_limit": 1.0e-10,
        "provider_call_limit": 25_000,
        "wall_clock_limit_sec": 180.0,
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "any leading Jacobian loses rank or exceeds condition limit",
            "storage constraint row rank is below four",
            "colored and full canonical Jacobians disagree or reveal off-pattern coupling",
            "canonical lower storage closure exceeds the frozen limit",
            "pressure ordering, conservation, provider, call, or wall gate fails",
            "a nonlinear solve, initializer, timestep, retry, or integration is attempted",
        ],
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    (ROOT / CONTRACT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / CONTRACT_DOC).write_text(
        "\n".join(
            (
                "# DD-109 Frozen Conserved N/U Pressure Numerical Contract",
                "",
                f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
                "- Live system: `46 x 46` leading residual",
                f"- Colored Jacobian groups: `{payload['color_count']}`",
                "- States: DD-094 algebraic profile and DD-103 pressure endpoint guess",
                "- Jacobian steps: `1e-5`, `5e-6`",
                "- Canonical cross-check: one full central-difference Jacobian",
                "- Live property evaluation during preparation: `False`",
                "- Nonlinear solve during preparation: `False`",
                "- Initializer or integration during preparation: `False`",
                "",
                "Execution is permitted once only after this contract is committed. "
                "No root solve, timestep, or initializer is part of DD-109.",
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
        raise RuntimeError("DD-109 contract hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-109 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-109 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-109 workbook changed")
    if (ROOT / RESULT).exists():
        raise RuntimeError("DD-109 result already exists")
    _git("ls-files", "--error-unmatch", str(CONTRACT))


def execute() -> dict[str, Any]:
    payload = _load(CONTRACT)
    _verify(payload)
    spec = dd102._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd102._reference(payload["reference"])
    template = dd102._state(payload["accepted_root_state"])
    contract = build_conserved_nu_pressure_dae_contract(spec.component_names)
    if not audit_conserved_nu_pressure_dae_contract(contract).pass_gate:
        raise RuntimeError("DD-109 structural prerequisite changed")
    provider = dd102._provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    component_mw = call_audit.component_molecular_weights(
        provider,
        caller="dd109_molecular_weight",
        state_id="dd109:preparation",
        evaluation_kind="preparation",
    )
    numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(payload["pressure_reference_psia"], dtype=float),
        pressure_coordinate_scale_psia=float(payload["pressure_coordinate_scale_psia"]),
        pressure_residual_scale_psia=float(payload["pressure_residual_scale_psia"]),
        dry_tray_pressure_drop_coefficient=float(payload["dry_tray_pressure_drop_coefficient"]),
        component_mw_lbm_per_lbmol=component_mw,
        link_geometry=tuple(PressureLinkGeometry(**item) for item in payload["pressure_link_geometry"]),
        enforce_pressure_order=False,
    )
    common = {
        "inventory_lbmol": payload["inventory_lbmol"],
        "lower_internal_energy_BTU": payload["lower_internal_energy_BTU"],
        "top_storage_gradient_BTU_lbmol": payload["top_storage_gradient_BTU_lbmol"],
        "energy_rate_scales_BTUph": payload["energy_rate_scales_BTUph"],
        "fixed_steady_scales": payload["fixed_steady_residual_scales"],
        "storage_scales_BTU": payload["storage_scales_BTU"],
        "numerical": numerical,
    }
    started = time.perf_counter()
    records = []
    canonical_full = None
    canonical_colored_matrix = None
    for state_index, state_payload in enumerate(payload["states"]):
        point = np.asarray(state_payload["solve_coordinates"], dtype=float)

        def objective(candidate: np.ndarray, state_id: str):
            return evaluate_conserved_nu_pressure_residual(
                contract,
                spec,
                reference,
                template,
                provider,
                call_audit,
                solve_coordinates=candidate,
                state_id=state_id,
                evaluation_kind="jacobian" if "leading" in state_id else "residual",
                **common,
            )

        endpoint = objective(point, f"dd109:{state_payload['name']}:endpoint")
        jacobians = [
            audit_conserved_nu_leading_jacobian(
                contract,
                objective,
                point,
                step=step,
                coupling_tolerance=float(payload["coupling_tolerance"]),
                use_coloring=True,
            )
            for step in payload["jacobian_steps"]
        ]
        if state_index == 0:
            canonical_colored_matrix = jacobians[0].matrix.copy()
            canonical_full = audit_conserved_nu_leading_jacobian(
                contract,
                objective,
                point,
                step=float(payload["jacobian_steps"][0]),
                coupling_tolerance=float(payload["coupling_tolerance"]),
                use_coloring=False,
            )
        storage_indices = np.asarray(
            [index for index, row in enumerate(contract.rows) if row.block == "liquid_internal_energy_storage"]
        )
        storage_ranks = [int(np.linalg.matrix_rank(item.matrix[storage_indices, :])) for item in jacobians]
        records.append(
            {
                "name": state_payload["name"],
                "scaled_residual_inf_norm": float(np.max(np.abs(endpoint.scaled))),
                "storage_scaled_residual_inf_norm": float(
                    np.max(np.abs(endpoint.storage_closure_BTU / np.asarray(payload["storage_scales_BTU"])))
                ),
                "pressure_psia": _vector(endpoint.pressure_evaluation.pressure_psia),
                "temperature_F": _vector(endpoint.pressure_evaluation.base_evaluation.physical_state.temperature_F),
                "liquid_moles_lbmol": _vector(endpoint.pressure_evaluation.base_evaluation.physical_state.liquid_moles_lbmol),
                "liquid_mole_fraction": [
                    _vector(row)
                    for row in endpoint.pressure_evaluation.base_evaluation.physical_state.liquid_mole_fraction
                ],
                "vapor_mole_fraction": [
                    _vector(row)
                    for row in endpoint.pressure_evaluation.base_evaluation.physical_state.vapor_mole_fraction
                ],
                "hydraulic_liquid_flow_lbmolph": _vector(endpoint.pressure_evaluation.base_evaluation.physical_state.hydraulic_liquid_flow_lbmolph),
                "vapor_flow_lbmolph": _vector(endpoint.pressure_evaluation.base_evaluation.physical_state.vapor_flow_lbmolph),
                "distillate_lbmolph": float(endpoint.pressure_evaluation.base_evaluation.physical_state.distillate_lbmolph),
                "bottoms_lbmolph": float(endpoint.pressure_evaluation.base_evaluation.physical_state.bottoms_lbmolph),
                "condenser_duty_BTUph": float(endpoint.pressure_evaluation.base_evaluation.physical_state.condenser_duty_BTUph),
                "liquid_density_lbmol_ft3": _vector(endpoint.pressure_evaluation.base_evaluation.steady_evaluation.properties.liquid_density_lbmol_ft3),
                "liquid_height_ft": _vector(endpoint.pressure_evaluation.base_evaluation.steady_evaluation.properties.liquid_height_ft),
                "over_weir_head_ft": _vector(endpoint.pressure_evaluation.pressure_drop.over_weir_head_ft),
                "liquid_head_drop_psia": _vector(endpoint.pressure_evaluation.pressure_drop.liquid_head_drop_psia),
                "dry_tray_drop_psia": _vector(endpoint.pressure_evaluation.pressure_drop.dry_tray_drop_psia),
                "vapor_compressibility_factor": _vector(endpoint.pressure_evaluation.pressure_drop.vapor_compressibility_factor),
                "live_internal_energy_BTU": _vector(endpoint.live_internal_energy_BTU),
                "storage_constraint_ranks": storage_ranks,
                "component_conservation": float(endpoint.pressure_evaluation.base_evaluation.steady_evaluation.component_telescoping_relative_error),
                "energy_conservation": float(endpoint.pressure_evaluation.base_evaluation.steady_evaluation.energy_telescoping_relative_error),
                "spectrum_change": _spectrum_change(jacobians[0].singular_values, jacobians[1].singular_values),
                "jacobians": [
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
                    for item in jacobians
                ],
            }
        )
    elapsed = time.perf_counter() - started
    if canonical_full is None or canonical_colored_matrix is None:
        raise RuntimeError("DD-109 canonical Jacobians were not evaluated")
    colored_full_difference = float(
        np.max(np.abs(canonical_colored_matrix - canonical_full.matrix))
    )
    provenance = call_audit.report()
    finite_fields = (
        "pressure_psia",
        "temperature_F",
        "liquid_moles_lbmol",
        "liquid_mole_fraction",
        "vapor_mole_fraction",
        "hydraulic_liquid_flow_lbmolph",
        "vapor_flow_lbmolph",
        "liquid_density_lbmol_ft3",
        "liquid_height_ft",
        "over_weir_head_ft",
        "liquid_head_drop_psia",
        "dry_tray_drop_psia",
        "vapor_compressibility_factor",
        "live_internal_energy_BTU",
    )
    liquid_head_links = np.asarray(
        [item["include_liquid_head"] for item in payload["pressure_link_geometry"]],
        dtype=bool,
    )
    gates = {
        "rank": all(j["rank"] == payload["required_rank"] for record in records for j in record["jacobians"]) and canonical_full.rank == payload["required_rank"],
        "condition": all(j["condition"] < payload["condition_limit"] for record in records for j in record["jacobians"]) and canonical_full.condition < payload["condition_limit"],
        "spectrum": all(record["spectrum_change"] < payload["spectrum_change_limit"] for record in records),
        "structure": all(not j["zero_rows"] and not j["zero_columns"] and not j["unexpected_couplings"] for record in records for j in record["jacobians"]) and not canonical_full.zero_rows and not canonical_full.zero_columns and not canonical_full.unexpected_couplings,
        "storage_rank": all(all(rank == payload["storage_constraint_rank"] for rank in record["storage_constraint_ranks"]) for record in records),
        "colored_full": colored_full_difference < payload["colored_full_matrix_difference_limit"],
        "canonical_storage": records[0]["storage_scaled_residual_inf_norm"] < payload["canonical_storage_scaled_residual_limit"],
        "finite_physical_state": all(
            all(np.all(np.isfinite(np.asarray(record[field], dtype=float))) for field in finite_fields)
            and np.isfinite(record["distillate_lbmolph"])
            and np.isfinite(record["bottoms_lbmolph"])
            and np.isfinite(record["condenser_duty_BTUph"])
            for record in records
        ),
        "positive_inventory_and_flows": all(
            np.all(np.asarray(record["liquid_moles_lbmol"]) > 0.0)
            and np.all(np.asarray(record["hydraulic_liquid_flow_lbmolph"]) > 0.0)
            and np.all(np.asarray(record["vapor_flow_lbmolph"]) > 0.0)
            and record["distillate_lbmolph"] > 0.0
            and record["bottoms_lbmolph"] > 0.0
            for record in records
        ),
        "normalized_compositions": all(
            np.all(np.asarray(record["liquid_mole_fraction"]) > 0.0)
            and np.all(np.asarray(record["vapor_mole_fraction"]) > 0.0)
            and np.allclose(np.sum(record["liquid_mole_fraction"], axis=1), 1.0, atol=1.0e-12, rtol=0.0)
            and np.allclose(np.sum(record["vapor_mole_fraction"], axis=1), 1.0, atol=1.0e-12, rtol=0.0)
            for record in records
        ),
        "pressure": all(
            np.all(np.asarray(record["pressure_psia"]) > 0.0)
            and np.all(np.diff(record["pressure_psia"]) > 0.0)
            for record in records
        ),
        "positive_pressure_and_geometry_terms": all(
            np.all(np.asarray(record["liquid_density_lbmol_ft3"]) > 0.0)
            and np.all(np.asarray(record["liquid_height_ft"]) > 0.0)
            and np.all(np.asarray(record["over_weir_head_ft"])[liquid_head_links] > 0.0)
            and np.all(np.asarray(record["liquid_head_drop_psia"])[liquid_head_links] > 0.0)
            and np.all(np.abs(np.asarray(record["liquid_head_drop_psia"])[~liquid_head_links]) <= 1.0e-14)
            and np.all(np.asarray(record["dry_tray_drop_psia"]) > 0.0)
            and np.all(np.asarray(record["vapor_compressibility_factor"]) > 0.0)
            for record in records
        ),
        "conservation": all(abs(record["component_conservation"]) < payload["component_conservation_limit"] and abs(record["energy_conservation"]) < payload["energy_conservation_limit"] for record in records),
        "provider": provenance["pass"],
        "calls": provenance["total_calls"] < payload["provider_call_limit"],
        "wall": elapsed < payload["wall_clock_limit_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": "dd109_passed" if passed else "dd109_failed",
        "decision": "authorize_frozen_nu_initializer_contract" if passed else "stop_conserved_nu_pressure_numerical_path",
        "wall_clock_sec": elapsed,
        "states": records,
        "canonical_full_jacobian": {
            "rank": canonical_full.rank,
            "condition": canonical_full.condition,
            "unexpected_couplings": list(canonical_full.unexpected_couplings),
        },
        "colored_full_matrix_difference": colored_full_difference,
        "provider_provenance": provenance,
        "gates": gates,
        "pass": passed,
        "campaign_executed_once": True,
        "nonlinear_solve_attempted": False,
        "initializer_attempted": False,
        "dynamic_integration_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / RESULT_DOC).write_text(
        "\n".join(
            (
                "# DD-109 Conserved N/U Pressure Numerical Result",
                "",
                f"- Classification: `{result['classification']}`",
                f"- Decision: `{result['decision']}`",
                f"- Wall clock: `{elapsed:.3f} s`",
                f"- Provider calls: `{provenance['total_calls']}`",
                f"- Colored/full difference: `{colored_full_difference:.6e}`",
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
