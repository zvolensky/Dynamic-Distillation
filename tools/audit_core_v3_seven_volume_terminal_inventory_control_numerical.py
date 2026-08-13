#!/usr/bin/env python
"""Prepare or execute DD-185's live terminal-control numerical audit."""

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

import audit_core_v3_seven_volume_dynamic_dae_numerical as dd171  # noqa: E402
from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    TerminalPIParameters,
    TerminalVesselGeometry,
    audit_terminal_inventory_control_contract,
    build_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
    audit_terminal_inventory_control_leading_jacobian,
    evaluate_terminal_inventory_control_residual,
)


SCHEMA = "dd185-core-v3-seven-volume-terminal-control-numerical-contract-v1"
RESULT_SCHEMA = "dd185-core-v3-seven-volume-terminal-control-numerical-result-v1"
DD184 = Path(
    "logs/dd184_core_v3_seven_volume_terminal_inventory_control_contract_20260813.json"
)
DD171 = Path("logs/dd171_core_v3_seven_volume_dynamic_dae_numerical_20260812.json")
DD169_CONTRACT = Path(
    "logs/dd169_core_v3_seven_volume_steady_root_contract_20260807.json"
)
DD169_RESULT = Path("logs/dd169_core_v3_seven_volume_steady_root_20260807.json")
CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
RESULT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_185_core_v3_seven_volume_terminal_inventory_control_numerical_20260813.md"
)
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_contract_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "tools/audit_core_v3_seven_volume_terminal_inventory_control_numerical.py",
    "tests/test_core_v3_terminal_inventory_control_contract_v1.py",
    "tests/test_core_v3_terminal_inventory_control_numerical_v1.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _spectrum_change(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.maximum.reduce(
        (np.abs(first), np.abs(second), np.full_like(first, 1.0e-15))
    )
    return float(np.max(np.abs(first - second) / denominator))


def _controlled_contract(spec, dd184: Mapping[str, Any]):
    base = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=str(DD169_RESULT).replace("\\", "/"),
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    return build_terminal_inventory_control_contract(
        base,
        geometry=TerminalVesselGeometry(**dd184["geometry"]),
        controllers=TerminalPIParameters(**dd184["controllers"]),
    )


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-185 Seven-Volume Terminal Control Numerical Contract",
            "",
            f"- Contract payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Leading system: `58 x 58`",
            "- Jacobian steps: `1e-5`, `5e-6`",
            "- Controller setpoints: reconstructed once from the accepted root's "
            "live geometry-based levels",
            "- Controller memory and product log ratios: zero for bumpless handoff",
            "- DD-171 accepted storage gradient: reused without recomputation",
            "- Property, residual, or Jacobian calls during preparation: `False`",
            "- Nonlinear solve, controller-state advance, or timestep: `False`",
            "",
            "## Authorization",
            "",
            "Commit this contract before its one live execution. Execution may "
            "reconstruct root levels, evaluate the complete zero-time residual, "
            "and build the two frozen leading Jacobians. It may not solve for a "
            "state, advance controller memory, select a timestep, tune a "
            "controller, or integrate dynamics.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    ranks = " / ".join(str(item["rank"]) for item in payload["jacobians"])
    levels = payload["terminal_levels"]
    return "\n".join(
        (
            "# DD-185 Seven-Volume Terminal Control Numerical Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Complete residual infinity norm: "
            f"`{payload['zero_time_scaled_residual_inf_norm']:.6e}`",
            f"- Controller residual infinity norm: "
            f"`{payload['controller_scaled_residual_inf_norm']:.6e}`",
            f"- Top / bottom level fractions: "
            f"`{levels['top_fraction']:.6f} / {levels['bottom_fraction']:.6f}`",
            f"- Leading ranks: `{ranks}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Spectrum relative change: "
            f"`{payload['spectrum_relative_change']:.6e}`",
            f"- Logical provider calls: "
            f"`{payload['provider_provenance']['total_calls']}`",
            f"- Exact memo hits: `{payload['exact_state_memoization']['hits']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Nonlinear solve, controller-state advance, timestep, or dynamics: "
            "`False`",
            "",
        )
    )


def prepare(
    dd184_path: Path,
    dd171_path: Path,
    dd169_contract_path: Path,
    dd169_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    dd184 = _load(dd184_path)
    dd171_result = _load(dd171_path)
    source = _load(dd169_contract_path)
    root_result = _load(dd169_result_path)
    if (
        not dd184["audit"]["pass_gate"]
        or not dd171_result["pass_gate"]
        or not root_result["campaign_pass"]
    ):
        raise RuntimeError("DD-185 prerequisites are not accepted")
    spec = dd171.dd168._spec(
        source["source_mapping"],
        float(source["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd171.dd168._reference(source["reference"])
    root = root_result["starts"]["source_mapped_seed"]["state"]
    state = dd171._state(root)
    controlled = _controlled_contract(spec, dd184)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-185 structural prerequisite changed")
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    point = np.concatenate(
        (
            np.zeros(len(controlled.base.derivative_variables)),
            np.zeros(2),
            algebraic,
            np.zeros(2),
        )
    )
    storage_gradient = dd171_result["storage_gradient"]["steps"][0][
        "gradient_BTU_lbmol"
    ]
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (
                dd184_path,
                dd171_path,
                dd169_contract_path,
                dd169_result_path,
            )
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": root,
        "accepted_root_inventory_lbmol": _rows(inventory),
        "root_solve_coordinates": _vector(point),
        "controller_memory": [0.0, 0.0],
        "product_reference_lbmolph": [
            float(state.distillate_lbmolph),
            float(state.bottoms_lbmolph),
        ],
        "setpoint_policy": (
            "reconstruct once from accepted-root terminal inventory, live DWSIM "
            "liquid density, and frozen vessel geometry; use those exact fractions "
            "for the baseline and both Jacobians"
        ),
        "geometry": dd184["geometry"],
        "controllers": dd184["controllers"],
        "fixed_steady_residual_scales": source["fixed_residual_scales"],
        "storage_gradient_BTU_lbmol": storage_gradient,
        "storage_gradient_source": str(dd171_path).replace("\\", "/"),
        "structural_audit": asdict(structural),
        "leading_jacobian_steps": list(JACOBIAN_STEPS),
        "required_rank": 58,
        "limits": {
            "zero_time_scaled_residual": 1.0e-8,
            "base_scaled_residual": 1.0e-8,
            "controller_scaled_residual": 1.0e-10,
            "level_error": 1.0e-12,
            "minimum_level_fraction": 0.01,
            "maximum_level_fraction": 0.99,
            "product_relative_difference": 1.0e-12,
            "coupling_tolerance": 1.0e-7,
            "condition": 1.0e8,
            "spectrum_relative_change": 0.25,
            "component_conservation": 1.0e-12,
            "energy_conservation": 1.0e-10,
            "provider_calls": 35000,
            "wall_clock_sec": 120.0,
        },
        "exact_state_memoization": {
            "enabled": True,
            "exact_unrounded_keys": True,
            "cleared_before_execution": True,
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "complete or controller zero-time residual exceeds its limit",
            "terminal level is nonphysical or product handoff is not bumpless",
            "either leading Jacobian is not rank 58",
            "condition, spectrum, or registered-coupling gate fails",
            "conservation, provider, call, or wall gate fails",
        ],
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "jacobian_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "controller_state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _payload_hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-185 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _payload_hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-185 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-185 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-185 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-185 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-185 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-185 contract is not committed")


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    source = _load(DD169_CONTRACT)
    dd184 = _load(DD184)
    spec = dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd171.dd168._reference(payload["reference"])
    state = dd171._state(payload["accepted_root_state"])
    controlled = _controlled_contract(spec, dd184)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-185 structural contract changed")
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    point = np.asarray(payload["root_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    storage_gradient = np.asarray(payload["storage_gradient_BTU_lbmol"], dtype=float)
    provider = dd171._provider(Path(payload["workbook"]), payload["property_package"])
    provider.set_exact_state_memoization(True, clear=True)
    call_audit = ProviderCallAudit()
    started = time.perf_counter()
    seed = evaluate_terminal_inventory_control_residual(
        controlled,
        spec,
        reference,
        state,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        controller_memory=memory,
        level_setpoints=TerminalLevelSetpoints(0.5, 0.5),
        solve_coordinates=point,
        storage_gradient_BTU_lbmol=storage_gradient,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        state_id="dd185_setpoint_reconstruction",
        evaluation_kind="residual",
    )
    setpoints = TerminalLevelSetpoints(*seed.level_fraction)
    baseline = evaluate_terminal_inventory_control_residual(
        controlled,
        spec,
        reference,
        state,
        provider,
        call_audit,
        inventory_lbmol=inventory,
        controller_memory=memory,
        level_setpoints=setpoints,
        solve_coordinates=point,
        storage_gradient_BTU_lbmol=storage_gradient,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        state_id="dd185_zero_time_root",
        evaluation_kind="residual",
    )
    jacobians = tuple(
        audit_terminal_inventory_control_leading_jacobian(
            controlled,
            spec,
            reference,
            state,
            provider,
            call_audit,
            inventory_lbmol=inventory,
            controller_memory=memory,
            level_setpoints=setpoints,
            root_solve_coordinates=point,
            storage_gradient_BTU_lbmol=storage_gradient,
            fixed_steady_scales=payload["fixed_steady_residual_scales"],
            step=step,
            coupling_tolerance=float(payload["limits"]["coupling_tolerance"]),
            state_id=f"dd185_leading_{step:g}",
        )
        for step in payload["leading_jacobian_steps"]
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provenance = call_audit.report()
    limits = payload["limits"]
    spectrum_change = _spectrum_change(
        jacobians[0].singular_values, jacobians[1].singular_values
    )
    complete_norm = float(np.max(np.abs(baseline.scaled)))
    base_norm = float(np.max(np.abs(baseline.scaled[:-4])))
    controller_norm = float(np.max(np.abs(baseline.scaled[-4:])))
    maximum_level_error = float(np.max(np.abs(baseline.level_error)))
    density = np.asarray(
        baseline.base.steady_evaluation.properties.liquid_density_lbmol_ft3,
        dtype=float,
    )
    products = np.asarray(
        (baseline.distillate_lbmolph, baseline.bottoms_lbmolph), dtype=float
    )
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    product_relative = float(
        np.max(np.abs(products - product_reference) / product_reference)
    )
    component_error = float(
        baseline.base.steady_evaluation.component_telescoping_relative_error
    )
    energy_error = float(
        baseline.base.steady_evaluation.energy_telescoping_relative_error
    )
    gates = {
        "structural": structural.pass_gate,
        "complete_zero_time_residual": complete_norm
        < limits["zero_time_scaled_residual"],
        "base_zero_time_residual": base_norm < limits["base_scaled_residual"],
        "controller_zero_time_residual": controller_norm
        < limits["controller_scaled_residual"],
        "zero_level_error": maximum_level_error < limits["level_error"],
        "physical_levels": bool(
            np.all(baseline.level_fraction > limits["minimum_level_fraction"])
            and np.all(baseline.level_fraction < limits["maximum_level_fraction"])
        ),
        "positive_density": bool(
            np.all(np.isfinite(density)) and np.all(density > 0.0)
        ),
        "bumpless_products": product_relative < limits["product_relative_difference"],
        "zero_controller_rates": bool(
            np.array_equal(baseline.controller_rate_per_sec, np.zeros(2))
        ),
        "zero_product_log_ratios": bool(
            np.array_equal(baseline.product_log_ratio, np.zeros(2))
        ),
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
        "spectrum_stable": spectrum_change < limits["spectrum_relative_change"],
        "component_conservation": component_error < limits["component_conservation"],
        "energy_conservation": energy_error < limits["energy_conservation"],
        "provider_provenance": bool(provenance["pass"]),
        "provider_calls": provenance["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "terminal_inventory_control_numerical_gate_passed"
            if passed
            else "terminal_inventory_control_numerical_gate_failed"
        ),
        "decision": (
            "authorize_one_frozen_controlled_stationary_root_hold_step_contract"
            if passed
            else "stop_terminal_control_before_any_timestep"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": float(elapsed),
        "terminal_levels": asdict(setpoints),
        "liquid_density_lbmol_ft3": _vector(density),
        "distillate_lbmolph": baseline.distillate_lbmolph,
        "bottoms_lbmolph": baseline.bottoms_lbmolph,
        "product_relative_difference": product_relative,
        "zero_time_scaled_residual_inf_norm": complete_norm,
        "base_scaled_residual_inf_norm": base_norm,
        "controller_scaled_residual_inf_norm": controller_norm,
        "maximum_level_error": maximum_level_error,
        "scaled_residual": _vector(baseline.scaled),
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
        "controller_state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd184", type=Path, default=DD184)
    parser.add_argument("--dd171", type=Path, default=DD171)
    parser.add_argument("--dd169-contract", type=Path, default=DD169_CONTRACT)
    parser.add_argument("--dd169-result", type=Path, default=DD169_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.dd184,
            args.dd171,
            args.dd169_contract,
            args.dd169_result,
            args.contract,
            args.contract_doc,
        )
        print(
            json.dumps(
                {
                    "schema_id": output["schema_id"],
                    "contract_payload_sha256": output["contract_payload_sha256"],
                    "required_rank": output["required_rank"],
                    "campaign_executed": output["campaign_executed"],
                },
                indent=2,
            )
        )
    else:
        output = execute(args.contract, args.result, args.result_doc)
        print(
            json.dumps(
                {
                    "classification": output["classification"],
                    "pass_gate": output["pass_gate"],
                    "decision": output["decision"],
                },
                indent=2,
            )
        )
        raise SystemExit(0 if output["pass_gate"] else 2)
