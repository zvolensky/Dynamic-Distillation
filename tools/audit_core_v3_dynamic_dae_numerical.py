#!/usr/bin/env python
"""Prepare or execute the frozen DD-096 Core V3 dynamic DAE numerical audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    audit_leading_jacobian,
    audit_storage_gradient,
    dynamic_algebraic_coordinates,
    evaluate_dynamic_implicit_residual,
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    HydraulicGeometry,
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


SCHEMA_ID = "dd096-core-v3-dynamic-dae-numerical-contract-v1"
RESULT_SCHEMA_ID = "dd096-core-v3-dynamic-dae-numerical-result-v1"
DEFAULT_DD095 = Path("logs/dd095_core_v3_dynamic_dae_contract_20260725.json")
DEFAULT_DD094 = Path("logs/dd094_core_v3_steady_root_20260725.json")
DEFAULT_SOURCE = Path(
    "logs/dd094_core_v3_steady_root_recovery_contract_20260725.json"
)
DEFAULT_CONTRACT = Path(
    "logs/dd096_core_v3_dynamic_dae_numerical_contract_20260725.json"
)
DEFAULT_RESULT = Path("logs/dd096_core_v3_dynamic_dae_numerical_20260725.json")

IMPLEMENTATION_PATHS = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tests/test_core_v3_dynamic_dae_contract_v1.py",
    "tests/test_core_v3_dynamic_dae_numerical_audit_v1.py",
    "tools/audit_core_v3_dynamic_dae_numerical.py",
    "docs/dd_096_core_v3_dynamic_dae_numerical_contract_20260725.md",
)

STORAGE_RELATIVE_STEPS = (1.0e-5, 5.0e-6)
LEADING_JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
COUPLING_TOLERANCE = 1.0e-7
CONDITION_LIMIT = 1.0e8
SPECTRUM_RELATIVE_CHANGE_LIMIT = 0.25
STORAGE_GRADIENT_RELATIVE_CHANGE_LIMIT = 1.0e-3
BUBBLE_RESIDUAL_LIMIT = 1.0e-10
ROOT_SCALED_RESIDUAL_LIMIT = 1.0e-8
COMPONENT_CONSERVATION_LIMIT = 1.0e-12
ENERGY_CONSERVATION_LIMIT = 1.0e-10


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _rows(values: Any) -> list[list[float]]:
    return [
        [float(value) for value in np.asarray(row, dtype=float).reshape((-1,))]
        for row in np.asarray(values, dtype=float)
    ]


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _spec(source: Mapping[str, Any], feed_enthalpy: float) -> OperatingSpec:
    return OperatingSpec(
        component_names=tuple(source["component_names"]),
        pressure_psia=np.asarray(source["pressure_psia"], dtype=float),
        reflux_lbmolph=float(source["reflux_lbmolph"]),
        feed_component_lbmolph=np.asarray(
            source["feed_component_lbmolph"], dtype=float
        ),
        feed_enthalpy_BTUph=float(feed_enthalpy),
        reboiler_duty_BTUph=float(source["reboiler_duty_BTUph"]),
        terminal_liquid_targets_lbmol=np.asarray(
            source["terminal_liquid_targets_lbmol"], dtype=float
        ),
        hydraulic_geometry=tuple(
            HydraulicGeometry(**item) for item in source["hydraulic_geometry"]
        ),
    )


def _reference(payload: Mapping[str, Any]) -> NumericalReference:
    return NumericalReference(
        liquid_moles_lbmol=np.asarray(payload["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=np.asarray(
            payload["liquid_mole_fraction"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(
            payload["vapor_mole_fraction"], dtype=float
        ),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_reference_BTUph=float(
            payload["condenser_duty_reference_BTUph"]
        ),
        condenser_duty_scale_BTUph=float(payload["condenser_duty_scale_BTUph"]),
    )


def _state(payload: Mapping[str, Any]) -> PhysicalState:
    return PhysicalState(
        liquid_moles_lbmol=np.asarray(payload["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=np.asarray(
            payload["liquid_mole_fraction"], dtype=float
        ),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(
            payload["vapor_mole_fraction"], dtype=float
        ),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_BTUph=float(payload["condenser_duty_BTUph"]),
    )


def _provider(workbook: Path, package: str) -> ThermoProviderV1:
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    return ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=package,
        silence_backend_console=True,
    )


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-096 Frozen Core V3 Dynamic DAE Numerical Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Dynamic system: `38 x 38` implicit leading system",
            "- Storage derivative steps: `1e-5`, `5e-6`",
            "- Leading-Jacobian steps: `1e-5`, `5e-6`",
            "- Live property evaluation during preparation: `False`",
            "- Dynamic integration during preparation: `False`",
            "",
            "## Authorization",
            "",
            "Commit this contract before its one live execution. No integration, "
            "perturbation, controller, or alternate numerical campaign is "
            "authorized.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-096 Core V3 Dynamic DAE Numerical Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Root scaled residual: "
            f"`{payload['root_scaled_residual_inf_norm']:.6e}`",
            f"- Storage-gradient step change: "
            f"`{payload['storage_gradient']['maximum_relative_change']:.6e}`",
            f"- Leading ranks: "
            f"`{' / '.join(str(item['rank']) for item in payload['leading_jacobians'])}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Spectrum step change: "
            f"`{payload['spectrum_relative_change']:.6e}`",
            f"- Provider gate: `{payload['provider_provenance']['pass']}`",
            f"- Dynamic integration attempted: "
            f"`{payload['dynamic_integration_attempted']}`",
            "",
        )
    )


def prepare(
    dd095_path: Path,
    dd094_path: Path,
    source_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    dd095 = _load(dd095_path)
    dd094 = _load(dd094_path)
    source = _load(source_path)
    if not dd095["audit"]["pass_gate"] or not dd094["campaign_pass"]:
        raise RuntimeError("DD-096 requires accepted DD-094 and DD-095 evidence")
    root = dd094["starts"]["canonical_core_v3_seed"]
    endpoint = root["endpoint_evaluation"]["state"]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd095_path": str(dd095_path).replace("\\", "/"),
        "dd095_sha256": _sha256(ROOT / dd095_path),
        "dd094_path": str(dd094_path).replace("\\", "/"),
        "dd094_sha256": _sha256(ROOT / dd094_path),
        "source_contract_path": str(source_path).replace("\\", "/"),
        "source_contract_sha256": _sha256(ROOT / source_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": endpoint,
        "accepted_root_full_coordinates": root["final_coordinates"],
        "accepted_root_inventory_lbmol": dd095[
            "accepted_root_component_inventory_lbmol"
        ],
        "accepted_root_algebraic_coordinates": _vector(
            np.asarray(root["final_coordinates"], dtype=float)[
                [
                    *range(15, 20),
                    *range(20, 28),
                    *range(28, 31),
                    *range(31, 35),
                    *range(37, 39),
                    39,
                ]
            ]
        ),
        "fixed_steady_residual_scales": source["fixed_residual_scales"],
        "fixed_products_lbmolph": {
            "distillate": endpoint["distillate_lbmolph"],
            "bottoms": endpoint["bottoms_lbmolph"],
        },
        "storage_relative_steps": list(STORAGE_RELATIVE_STEPS),
        "leading_jacobian_steps": list(LEADING_JACOBIAN_STEPS),
        "coupling_tolerance": COUPLING_TOLERANCE,
        "condition_limit": CONDITION_LIMIT,
        "spectrum_relative_change_limit": SPECTRUM_RELATIVE_CHANGE_LIMIT,
        "storage_gradient_relative_change_limit": (
            STORAGE_GRADIENT_RELATIVE_CHANGE_LIMIT
        ),
        "bubble_residual_limit": BUBBLE_RESIDUAL_LIMIT,
        "root_scaled_residual_limit": ROOT_SCALED_RESIDUAL_LIMIT,
        "component_conservation_limit": COMPONENT_CONSERVATION_LIMIT,
        "energy_conservation_limit": ENERGY_CONSERVATION_LIMIT,
        "required_rank": 38,
        "hard_stops": [
            "root zero-derivative residual fails",
            "storage gradient is nonfinite or step-sensitive",
            "leading rank is below 38 at either step",
            "condition or singular-spectrum stability gate fails",
            "off-registry coupling or zero row/column appears",
            "component or energy conservation fails",
            "provider ownership or no-fallback gate fails",
        ],
        "implementation_sha256": {
            path: _sha256(ROOT / path) for path in IMPLEMENTATION_PATHS
        },
        "live_property_evaluation_attempted": False,
        "mass_matrix_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify_execution_contract(
    payload: dict[str, Any], contract_path: Path, result_path: Path
) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-096 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha256(ROOT / path) != expected:
            raise RuntimeError(f"DD-096 implementation changed: {path}")
    workbook = Path(payload["workbook"])
    if _sha256(workbook) != payload["workbook_sha256"]:
        raise RuntimeError("DD-096 workbook changed")
    if (ROOT / result_path).exists():
        raise RuntimeError("DD-096 result already exists; rerun is prohibited")
    tracked = _git("ls-files", "--error-unmatch", str(contract_path))
    if not tracked:
        raise RuntimeError("DD-096 contract is not committed")


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.ones_like(first) * 1.0e-15)
    )
    return float(np.max(np.abs(first - second) / denominator))


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify_execution_contract(payload, contract_path, result_path)
    source = payload["source_mapping"]
    spec = _spec(source, float(payload["operating_spec"]["feed_enthalpy_BTUph"]))
    reference = _reference(payload["reference"])
    state = _state(payload["accepted_root_state"])
    contract = build_dynamic_dae_contract(spec.component_names)
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-096 structural prerequisite failed")
    provider = _provider(Path(payload["workbook"]), payload["property_package"])
    call_audit = ProviderCallAudit()
    started = time.perf_counter()
    storage = audit_storage_gradient(
        spec,
        state,
        provider,
        call_audit,
        relative_steps=payload["storage_relative_steps"],
        state_id="dd096_storage",
    )
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-096 inventory mapping changed")
    if not np.allclose(algebraic, payload["accepted_root_algebraic_coordinates"]):
        raise RuntimeError("DD-096 algebraic mapping changed")
    baseline = evaluate_dynamic_implicit_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        rate_coordinates=np.zeros(38 - len(contract.algebraic_variables)),
        algebraic_coordinates=algebraic,
        storage_gradient_BTU_lbmol=storage.steps[0].gradient_BTU_lbmol,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        state_id="dd096_root",
        evaluation_kind="residual",
    )
    jacobians = tuple(
        audit_leading_jacobian(
            contract,
            spec,
            reference,
            state,
            provider,
            call_audit,
            inventory_lbmol=inventory,
            root_algebraic_coordinates=algebraic,
            storage_gradient_BTU_lbmol=storage.steps[0].gradient_BTU_lbmol,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step=step,
            coupling_tolerance=float(payload["coupling_tolerance"]),
            state_id=f"dd096_leading_{step:g}",
        )
        for step in payload["leading_jacobian_steps"]
    )
    elapsed = time.perf_counter() - started
    spectrum_change = _spectrum_change(
        jacobians[0].singular_values, jacobians[1].singular_values
    )
    provider_report = call_audit.report()
    root_norm = float(np.max(np.abs(baseline.scaled)))
    component_error = float(
        baseline.steady_evaluation.component_telescoping_relative_error
    )
    energy_error = float(
        baseline.steady_evaluation.energy_telescoping_relative_error
    )
    gates = {
        "root_zero_derivative": root_norm
        < float(payload["root_scaled_residual_limit"]),
        "storage_finite": storage.all_finite,
        "storage_step_stable": storage.maximum_relative_change
        < float(payload["storage_gradient_relative_change_limit"]),
        "storage_bubble": max(
            item.maximum_bubble_residual for item in storage.steps
        )
        < float(payload["bubble_residual_limit"]),
        "leading_rank": all(
            item.rank == int(payload["required_rank"]) for item in jacobians
        ),
        "leading_condition": all(
            item.condition < float(payload["condition_limit"])
            for item in jacobians
        ),
        "leading_structure": all(
            not item.zero_rows
            and not item.zero_columns
            and not item.unexpected_couplings
            for item in jacobians
        ),
        "spectrum_stable": spectrum_change
        < float(payload["spectrum_relative_change_limit"]),
        "component_conservation": component_error
        < float(payload["component_conservation_limit"]),
        "energy_conservation": energy_error
        < float(payload["energy_conservation_limit"]),
        "provider_provenance": bool(provider_report["pass"]),
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA_ID,
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "classification": (
            "dd096_core_v3_dynamic_dae_numerical_passed"
            if passed
            else "dd096_core_v3_dynamic_dae_numerical_failed"
        ),
        "decision": (
            "authorize_implicit_solver_contract_only"
            if passed
            else "stop_dynamic_dae_path_before_integration"
        ),
        "wall_clock_sec": float(elapsed),
        "root_scaled_residual_inf_norm": root_norm,
        "root_raw_residual_inf_norm": float(np.max(np.abs(baseline.raw))),
        "root_component_rate_max_abs_lbmolph": float(
            np.max(np.abs(baseline.component_rate_lbmolph))
        ),
        "root_energy_storage_rate_max_abs_BTUph": float(
            np.max(np.abs(baseline.energy_storage_rate_BTUph))
        ),
        "storage_gradient": {
            "maximum_relative_change": storage.maximum_relative_change,
            "all_finite": storage.all_finite,
            "steps": [
                {
                    "relative_step": item.relative_step,
                    "internal_energy_BTU": _vector(item.internal_energy_BTU),
                    "gradient_BTU_lbmol": _rows(item.gradient_BTU_lbmol),
                    "maximum_bubble_residual": item.maximum_bubble_residual,
                }
                for item in storage.steps
            ],
        },
        "leading_jacobians": [
            {
                "step": item.step,
                "rank": item.rank,
                "condition": item.condition,
                "singular_values": _vector(item.singular_values),
                "zero_rows": list(item.zero_rows),
                "zero_columns": list(item.zero_columns),
                "unexpected_couplings": list(item.unexpected_couplings),
                "matrix": _rows(item.matrix),
            }
            for item in jacobians
        ],
        "worst_condition": max(item.condition for item in jacobians),
        "spectrum_relative_change": spectrum_change,
        "component_conservation_relative_error": component_error,
        "energy_conservation_relative_error": energy_error,
        "provider_provenance": provider_report,
        "gates": gates,
        "pass": passed,
        "campaign_executed_once": True,
        "nonlinear_state_solve_attempted": False,
        "dynamic_integration_attempted": False,
    }
    destination = ROOT / result_path
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _result_markdown(result), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd095", type=Path, default=DEFAULT_DD095)
    parser.add_argument("--dd094", type=Path, default=DEFAULT_DD094)
    parser.add_argument("--source-contract", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(args.dd095, args.dd094, args.source_contract, args.contract)
        print(json.dumps(output, indent=2))
        raise SystemExit(0)
    output = execute(args.contract, args.result)
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if output["pass"] else 2)
