#!/usr/bin/env python
"""Prepare or execute DD-171's seven-volume dynamic DAE numerical audit."""

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

import audit_core_v3_seven_volume_numerical as dd168  # noqa: E402

from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    audit_leading_jacobian,
    audit_storage_gradient,
    dynamic_algebraic_coordinates,
    evaluate_dynamic_implicit_residual,
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (  # noqa: E402
    PhysicalState,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)


SCHEMA = "dd171-core-v3-seven-volume-dynamic-dae-numerical-contract-v1"
RESULT_SCHEMA = "dd171-core-v3-seven-volume-dynamic-dae-numerical-result-v1"
DD170 = Path("logs/dd170_core_v3_seven_volume_dynamic_dae_contract_20260812.json")
DD169_CONTRACT = Path(
    "logs/dd169_core_v3_seven_volume_steady_root_contract_20260807.json"
)
DD169_RESULT = Path("logs/dd169_core_v3_seven_volume_steady_root_20260807.json")
CONTRACT = Path(
    "logs/dd171_core_v3_seven_volume_dynamic_dae_numerical_contract_20260812.json"
)
RESULT = Path("logs/dd171_core_v3_seven_volume_dynamic_dae_numerical_20260812")
STORAGE_STEPS = (1.0e-5, 5.0e-6)
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_call_audit_v1.py",
    "src/dynamic_distillation/core_v3/provider_governed_residual_v1.py",
    "tools/audit_core_v3_seven_volume_dynamic_dae_numerical.py",
    "tests/test_core_v3_dynamic_dae_numerical_audit_v1.py",
    "tests/test_core_v3_scaled_dynamic_dae_numerical_audit_v1.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape(-1)]


def _rows(values: Any) -> list[list[float]]:
    return [
        _vector(row) for row in np.asarray(values, dtype=float)
    ]


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


def _provider(workbook: Path, package: str):
    column = build_column_spec_from_case(load_case_from_excel(str(workbook)))
    return dd168.dd092._provider(column, package)


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-171 Seven-Volume Dynamic DAE Numerical Contract",
            "",
            f"- Contract payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Leading system: `54 x 54`",
            "- Storage-gradient steps: `1e-5`, `5e-6`",
            "- Leading-Jacobian steps: `1e-5`, `5e-6`",
            "- Exact-state provider memoization: enabled",
            "- Property calls during preparation: `False`",
            "- Nonlinear solve or timestep during preparation: `False`",
            "",
            "## Authorization",
            "",
            "Commit this contract before its one live execution. The execution "
            "may evaluate the accepted root, storage derivatives, and two "
            "leading Jacobians only. It may not solve for a state, choose a "
            "timestep, run a controller, or integrate dynamics.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    ranks = " / ".join(str(item["rank"]) for item in payload["jacobians"])
    return "\n".join(
        (
            "# DD-171 Seven-Volume Dynamic DAE Numerical Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Zero-rate scaled residual: "
            f"`{payload['zero_rate_scaled_residual_inf_norm']:.6e}`",
            f"- Storage-gradient relative change: "
            f"`{payload['storage_gradient']['maximum_relative_change']:.6e}`",
            f"- Leading ranks: `{ranks}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Spectrum relative change: "
            f"`{payload['spectrum_relative_change']:.6e}`",
            f"- Logical provider calls: "
            f"`{payload['provider_provenance']['total_calls']}`",
            f"- Exact memo hits: `{payload['exact_state_memoization']['hits']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Nonlinear state solve attempted: `False`",
            "- Dynamic integration attempted: `False`",
            "",
        )
    )


def prepare(
    dd170_path: Path,
    dd169_contract_path: Path,
    dd169_result_path: Path,
    contract_path: Path,
) -> dict[str, Any]:
    dd170 = _load(dd170_path)
    source = _load(dd169_contract_path)
    result = _load(dd169_result_path)
    if not dd170["audit"]["pass_gate"] or not result["campaign_pass"]:
        raise RuntimeError("DD-171 requires accepted DD-169 and DD-170 evidence")

    spec = dd168._spec(
        source["source_mapping"],
        float(source["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd168._reference(source["reference"])
    root = result["starts"]["source_mapped_seed"]["state"]
    state = _state(root)
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=str(dd169_result_path).replace("\\", "/"),
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-171 structural prerequisite changed")

    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "dd170_path": str(dd170_path).replace("\\", "/"),
        "dd170_sha256": _sha(ROOT / dd170_path),
        "dd169_contract_path": str(dd169_contract_path).replace("\\", "/"),
        "dd169_contract_sha256": _sha(ROOT / dd169_contract_path),
        "dd169_result_path": str(dd169_result_path).replace("\\", "/"),
        "dd169_result_sha256": _sha(ROOT / dd169_result_path),
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": root,
        "accepted_root_inventory_lbmol": _rows(inventory_from_state(state)),
        "accepted_root_algebraic_coordinates": _vector(
            dynamic_algebraic_coordinates(spec, reference, state)
        ),
        "fixed_steady_residual_scales": source["fixed_residual_scales"],
        "structural_audit": asdict(structural),
        "storage_relative_steps": list(STORAGE_STEPS),
        "leading_jacobian_steps": list(JACOBIAN_STEPS),
        "limits": {
            "zero_rate_scaled_residual": 1.0e-8,
            "storage_gradient_relative_change": 1.0e-3,
            "bubble_residual": 1.0e-10,
            "coupling_tolerance": 1.0e-7,
            "condition": 1.0e8,
            "spectrum_relative_change": 0.25,
            "component_conservation": 1.0e-12,
            "energy_conservation": 1.0e-10,
            "provider_calls": 30000,
            "wall_clock_sec": 120.0,
        },
        "required_rank": 54,
        "exact_state_memoization": {
            "enabled": True,
            "exact_unrounded_keys": True,
            "cleared_before_execution": True,
        },
        "implementation_sha256": {
            path: _sha(ROOT / path) for path in IMPLEMENTATION
        },
        "hard_stops": [
            "zero-rate accepted root does not close below 1e-8",
            "storage gradient is nonfinite, step-sensitive, or phase-invalid",
            "either leading Jacobian is not rank 54",
            "condition, spectrum, or registered-coupling gate fails",
            "component or energy conservation gate fails",
            "provider ownership, call, or wall gate fails",
        ],
        "property_evaluation_attempted": False,
        "mass_matrix_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "controller_execution_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    if destination.exists():
        raise RuntimeError("DD-171 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _contract_markdown(payload), encoding="utf-8"
    )
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-171 contract payload hash mismatch")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-171 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-171 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-171 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-171 contract is not committed")


def execute(contract_path: Path, result_path: Path) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    spec = dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd168._reference(payload["reference"])
    state = _state(payload["accepted_root_state"])
    contract = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=payload["dd169_result_path"],
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    structural = audit_dynamic_dae_contract(contract)
    if not structural.pass_gate or structural.solve_variable_count != 54:
        raise RuntimeError("DD-171 structural contract changed")

    provider = _provider(Path(payload["workbook"]), payload["property_package"])
    provider.set_exact_state_memoization(True, clear=True)
    call_audit = ProviderCallAudit()
    started = time.perf_counter()
    storage = audit_storage_gradient(
        spec,
        state,
        provider,
        call_audit,
        relative_steps=payload["storage_relative_steps"],
        state_id="dd171_storage",
    )
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    if not np.allclose(inventory, payload["accepted_root_inventory_lbmol"]):
        raise RuntimeError("DD-171 inventory mapping changed")
    if not np.allclose(
        algebraic, payload["accepted_root_algebraic_coordinates"]
    ):
        raise RuntimeError("DD-171 algebraic mapping changed")

    baseline = evaluate_dynamic_implicit_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        rate_coordinates=np.zeros(len(contract.derivative_variables)),
        algebraic_coordinates=algebraic,
        storage_gradient_BTU_lbmol=storage.steps[0].gradient_BTU_lbmol,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        state_id="dd171_zero_rate_root",
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
            coupling_tolerance=float(
                payload["limits"]["coupling_tolerance"]
            ),
            state_id=f"dd171_leading_{step:g}",
        )
        for step in payload["leading_jacobian_steps"]
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provenance = call_audit.report()
    spectrum_change = _spectrum_change(
        jacobians[0].singular_values, jacobians[1].singular_values
    )
    limits = payload["limits"]
    zero_rate_norm = float(np.max(np.abs(baseline.scaled)))
    component_error = float(
        baseline.steady_evaluation.component_telescoping_relative_error
    )
    energy_error = float(
        baseline.steady_evaluation.energy_telescoping_relative_error
    )
    bubble_max = max(
        item.maximum_bubble_residual for item in storage.steps
    )
    gates = {
        "structural": structural.pass_gate,
        "zero_rate_root": zero_rate_norm < limits["zero_rate_scaled_residual"],
        "zero_component_rates": bool(
            np.max(np.abs(baseline.component_rate_lbmolph)) == 0.0
        ),
        "zero_energy_storage_rates": bool(
            np.max(np.abs(baseline.energy_storage_rate_BTUph)) == 0.0
        ),
        "storage_finite": storage.all_finite,
        "storage_step_stable": (
            storage.maximum_relative_change
            < limits["storage_gradient_relative_change"]
        ),
        "storage_bubble": bubble_max < limits["bubble_residual"],
        "leading_rank": all(
            item.rank == payload["required_rank"] for item in jacobians
        ),
        "leading_condition": all(
            item.condition < limits["condition"] for item in jacobians
        ),
        "leading_structure": all(
            not item.zero_rows
            and not item.zero_columns
            and not item.unexpected_couplings
            for item in jacobians
        ),
        "spectrum_stable": (
            spectrum_change < limits["spectrum_relative_change"]
        ),
        "component_conservation": component_error
        < limits["component_conservation"],
        "energy_conservation": energy_error < limits["energy_conservation"],
        "provider_provenance": bool(provenance["pass"]),
        "provider_calls": provenance["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "seven_volume_dynamic_dae_numerical_gate_passed"
            if passed
            else "seven_volume_dynamic_dae_numerical_gate_failed"
        ),
        "decision": (
            "authorize_one_frozen_stationary_root_hold_step_contract"
            if passed
            else "stop_before_any_timestep"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": float(elapsed),
        "zero_rate_scaled_residual_inf_norm": zero_rate_norm,
        "zero_rate_raw_residual_inf_norm": float(
            np.max(np.abs(baseline.raw))
        ),
        "component_rate_max_abs_lbmolph": float(
            np.max(np.abs(baseline.component_rate_lbmolph))
        ),
        "energy_storage_rate_max_abs_BTUph": float(
            np.max(np.abs(baseline.energy_storage_rate_BTUph))
        ),
        "storage_gradient": {
            "maximum_relative_change": storage.maximum_relative_change,
            "all_finite": storage.all_finite,
            "maximum_bubble_residual": bubble_max,
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
        "jacobians": [
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
        "exact_state_memoization": memo,
        "provider_provenance": provenance,
        "gates": gates,
        "pass_gate": passed,
        "nonlinear_state_solve_attempted": False,
        "timestep_attempted": False,
        "controller_execution_attempted": False,
        "dynamic_integration_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    destination.with_suffix(".md").write_text(
        _result_markdown(result), encoding="utf-8"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd170", type=Path, default=DD170)
    parser.add_argument("--dd169-contract", type=Path, default=DD169_CONTRACT)
    parser.add_argument("--dd169-result", type=Path, default=DD169_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.dd170,
            args.dd169_contract,
            args.dd169_result,
            args.contract,
        )
        print(json.dumps({
            "schema_id": output["schema_id"],
            "contract_payload_sha256": output["contract_payload_sha256"],
            "required_rank": output["required_rank"],
            "campaign_executed": output["campaign_executed"],
        }, indent=2))
    else:
        output = execute(args.contract, args.result)
        print(json.dumps({
            "classification": output["classification"],
            "pass_gate": output["pass_gate"],
            "decision": output["decision"],
        }, indent=2))
        raise SystemExit(0 if output["pass_gate"] else 2)
