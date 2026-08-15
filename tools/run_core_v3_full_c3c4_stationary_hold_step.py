#!/usr/bin/env python
"""Prepare or execute the frozen DD-234 full-column stationary hold step."""

from __future__ import annotations

import argparse
from collections import Counter
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

import audit_core_v3_aligned_pr_density_parity as dd229  # noqa: E402
import audit_core_v3_full_c3c4_dynamic_handoff as dd232  # noqa: E402
import audit_core_v3_full_c3c4_zero_motion as dd233  # noqa: E402
import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402
import run_core_v3_full_c3c4_steady_root as dd223  # noqa: E402

from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    ImplicitStepSettings,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    solve_terminal_inventory_control_backward_euler_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
)


SCHEMA = "dd234-core-v3-full-c3c4-stationary-hold-contract-v1"
RESULT_SCHEMA = "dd234-core-v3-full-c3c4-stationary-hold-result-v1"
DD232 = dd233.DD232
DD233_CONTRACT = dd233.CONTRACT
DD233_RESULT = Path("logs/dd233_core_v3_full_c3c4_zero_motion_20260815.json")
CONTRACT = Path("logs/dd234_core_v3_full_c3c4_stationary_hold_contract_20260815.json")
RESULT = Path("logs/dd234_core_v3_full_c3c4_stationary_hold_20260815")
CONTRACT_DOC = Path("docs/dd_234_core_v3_full_c3c4_stationary_hold_contract_20260815.md")
RESULT_DOC = Path("docs/dd_234_core_v3_full_c3c4_stationary_hold_20260815.md")
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "tools/audit_core_v3_aligned_pr_density_parity.py",
    "tools/audit_core_v3_full_c3c4_zero_motion.py",
    "tools/run_core_v3_full_c3c4_stationary_hold_step.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape(-1)]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _settings(payload: Mapping[str, Any]) -> ImplicitStepSettings:
    values = dict(payload["solver"])
    values["x_scale"] = np.asarray(values["x_scale"], dtype=float)
    return ImplicitStepSettings(**values)


def prepare(contract_path: Path, contract_doc_path: Path) -> dict[str, Any]:
    zero_contract = _load(DD233_CONTRACT)
    zero_result = _load(DD233_RESULT)
    handoff = _load(DD232)
    if not zero_result.get("pass_gate") or not handoff.get("pass_gate"):
        raise RuntimeError("DD-234 requires accepted DD-232/DD-233 evidence")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(path)
            for path in (DD232, DD233_CONTRACT, DD233_RESULT)
        },
        "model_contract": zero_contract["model_contract"],
        "workbook": zero_contract["workbook"],
        "workbook_sha256": zero_contract["workbook_sha256"],
        "provider_routing": zero_contract["provider_routing"],
        "accepted_root_state": zero_contract["accepted_root_state"],
        "inventory_lbmol": zero_contract["inventory_lbmol"],
        "initial_solve_coordinates": zero_contract["root_solve_coordinates"],
        "controller_memory": zero_contract["controller_memory"],
        "level_setpoints": zero_result["terminal_levels"],
        "product_reference_lbmolph": zero_contract["product_reference_lbmolph"],
        "fixed_steady_residual_scales": zero_contract[
            "fixed_steady_residual_scales"
        ],
        "coordinate_scale_source": str(DD233_CONTRACT).replace("\\", "/"),
        "solver": {
            "method": "trf",
            "ftol": 1.0e-12,
            "xtol": 1.0e-12,
            "gtol": 1.0e-12,
            "max_nfev": 20,
            "x_scale": zero_contract["coordinate_scale"],
            "jacobian_step": 1.0e-5,
            "jacobian_mode": "colored",
        },
        "steps": {
            "full_seconds": 0.25,
            "half_seconds": 0.125,
            "sequence": ["full", "half_1", "half_2"],
            "adopted_startup_candidate": "full",
        },
        "required_rank": 162,
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "component_rate_lbmolph": 1.0e-4,
            "energy_rate_BTUph": 1.0e-3,
            "controller_rate_per_sec": 1.0e-10,
            "relative_inventory_movement": 1.0e-9,
            "algebraic_movement": 1.0e-7,
            "controller_memory_movement": 1.0e-10,
            "product_relative_movement": 1.0e-9,
            "level_error": 1.0e-10,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "kinematic_identity": 1.0e-10,
            "refinement_inventory": 1.0e-9,
            "refinement_rate": 1.0e-7,
            "refinement_algebraic": 1.0e-7,
            "refinement_controller_memory": 1.0e-10,
            "refinement_product": 1.0e-9,
            "provider_calls": 100000,
            "wall_clock_sec": 300.0,
        },
        "implementation_sha256": {path: _sha(Path(path)) for path in IMPLEMENTATION},
        "hard_stops": [
            "any root fails or exceeds the residual, rank, or condition limit",
            "the full or refined endpoint moves outside stationary tolerances",
            "the full and refined endpoints disagree outside refinement tolerances",
            "a physicality, equilibrium, conservation, kinematic, or provider gate fails",
            "the call or wall limit is exceeded",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "controller_state_advance_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-234 contract artifact already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-234 Full-C3/C4 Stationary Hold Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            "- Solver: `least_squares(method=trf)` with colored central differences",
            "- Comparison: one `0.25 s` backward-Euler step versus two `0.125 s` steps",
            "- State and controller setpoints: exact accepted DD-233 handoff",
            "- Thermo: DWSIM fugacity/enthalpy; aligned-PR liquid density",
            "- DD-233 coordinate scale reused without modification",
            "- Disturbance, tuning, retry, or trajectory: `False`",
            "",
            "Commit this immutable contract before its one live execution.",
            "",
        )
    )


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual or payload.get("schema_id") != SCHEMA:
        raise RuntimeError("DD-234 contract checksum or schema failed")
    for path, expected in payload["sources"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-234 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(Path(path)) != expected:
            raise RuntimeError(f"DD-234 implementation changed: {path}")
    if hashlib.sha256(Path(payload["workbook"]).read_bytes()).hexdigest() != payload["workbook_sha256"]:
        raise RuntimeError("DD-234 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-234 result exists; rerun is prohibited")
    relative = (ROOT / contract_path).resolve().relative_to(ROOT).as_posix()
    _git("ls-files", "--error-unmatch", relative)


def _rank_condition(matrix: np.ndarray, coordinate_scale: np.ndarray) -> tuple[int, float]:
    scaled = np.asarray(matrix, dtype=float) * coordinate_scale[None, :]
    singular = np.linalg.svd(scaled, compute_uv=False)
    tolerance = max(scaled.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(np.inf if singular[-1] <= tolerance else singular[0] / singular[-1])
    return rank, condition


def _provider_summary(audit: ProviderCallAudit) -> dict[str, Any]:
    report = audit.report()
    counts = Counter(
        (record.provider_interface, record.evaluation_kind) for record in audit.records
    )
    return {
        "provider_identity": report["provider_identity"],
        "interface_provider_identities": report["interface_provider_identities"],
        "total_calls": report["total_calls"],
        "counts": [
            {
                "provider_interface": key[0],
                "evaluation_kind": key[1],
                "count": int(value),
            }
            for key, value in sorted(counts.items())
        ],
        "violations": report["violations"],
        "fallback_attempted": report["fallback_attempted"],
        "pass": report["pass"],
    }


def _step_report(
    outcome: Any,
    *,
    original_inventory: np.ndarray,
    original_coordinates: np.ndarray,
    original_memory: np.ndarray,
    product_reference: np.ndarray,
    step_seconds: float,
    coordinate_scale: np.ndarray,
) -> dict[str, Any]:
    evaluation = outcome.evaluation
    state = evaluation.control_evaluation.base.physical_state
    steady = evaluation.control_evaluation.base.steady_evaluation
    rank, condition = _rank_condition(outcome.final_jacobian, coordinate_scale)
    step_hours = float(step_seconds) / 3600.0
    algebraic_start = len(original_inventory.reshape(-1)) + 2
    products = np.asarray(
        (evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph), dtype=float
    )
    component_identity = float(
        np.max(
            np.abs(
                evaluation.endpoint_inventory_lbmol
                - evaluation.previous_inventory_lbmol
                - evaluation.component_rate_lbmolph * step_hours
            )
        )
    )
    energy_identity = float(
        np.max(
            np.abs(
                evaluation.endpoint_internal_energy_BTU
                - evaluation.previous_internal_energy_BTU
                - evaluation.energy_storage_rate_BTUph * step_hours
            )
        )
    )
    controller_identity = float(
        np.max(
            np.abs(
                evaluation.endpoint_controller_memory
                - evaluation.previous_controller_memory
                - evaluation.controller_rate_per_sec * step_seconds
            )
        )
    )
    physical = bool(
        np.all(evaluation.endpoint_inventory_lbmol > 0.0)
        and np.all(state.liquid_mole_fraction > 0.0)
        and np.all(state.vapor_mole_fraction > 0.0)
        and np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(state.vapor_flow_lbmolph > 0.0)
        and np.all((evaluation.level_fraction > 0.01) & (evaluation.level_fraction < 0.99))
        and np.all(np.diff(state.temperature_F) > 0.0)
        and state.condenser_duty_BTUph < 0.0
    )
    return {
        "success": bool(outcome.success),
        "status": int(outcome.status),
        "nfev": int(outcome.nfev),
        "njev": None if outcome.njev is None else int(outcome.njev),
        "wall_clock_sec": float(outcome.wall_clock_sec),
        "scaled_residual_inf_norm": float(np.max(np.abs(outcome.final_residual))),
        "jacobian_rank": rank,
        "jacobian_condition": condition,
        "component_rate_max_abs_lbmolph": float(
            np.max(np.abs(evaluation.component_rate_lbmolph))
        ),
        "energy_rate_max_abs_BTUph": float(
            np.max(np.abs(evaluation.energy_storage_rate_BTUph))
        ),
        "controller_rate_max_abs_per_sec": float(
            np.max(np.abs(evaluation.controller_rate_per_sec))
        ),
        "relative_inventory_movement": float(
            np.max(
                np.abs(evaluation.endpoint_inventory_lbmol - original_inventory)
                / original_inventory
            )
        ),
        "algebraic_movement": float(
            np.max(
                np.abs(
                    outcome.final_coordinates[algebraic_start:-2]
                    - original_coordinates[algebraic_start:-2]
                )
            )
        ),
        "controller_memory_movement": float(
            np.max(np.abs(evaluation.endpoint_controller_memory - original_memory))
        ),
        "product_relative_movement": float(
            np.max(np.abs(products - product_reference) / product_reference)
        ),
        "maximum_level_error": float(np.max(np.abs(evaluation.level_error))),
        "maximum_equilibrium_residual": float(evaluation.maximum_equilibrium_residual),
        "component_conservation_relative_error": float(
            steady.component_telescoping_relative_error
        ),
        "energy_conservation_relative_error": float(
            steady.energy_telescoping_relative_error
        ),
        "component_kinematic_identity": component_identity,
        "energy_kinematic_identity": energy_identity,
        "controller_kinematic_identity": controller_identity,
        "inventory_lbmol": _rows(evaluation.endpoint_inventory_lbmol),
        "internal_energy_BTU": _vector(evaluation.endpoint_internal_energy_BTU),
        "controller_memory": _vector(evaluation.endpoint_controller_memory),
        "solve_coordinates": _vector(outcome.final_coordinates),
        "level_fraction": _vector(evaluation.level_fraction),
        "distillate_lbmolph": float(evaluation.distillate_lbmolph),
        "bottoms_lbmolph": float(evaluation.bottoms_lbmolph),
        "physical_pass": physical,
    }


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    model_contract = _load(Path(payload["model_contract"]))
    _workbook, dwsim, spec, reference = dd223._source_model(model_contract)
    aligned = dd092._independent_provider(model_contract)
    provider = dd229.DensityRoutedProvider(dwsim, aligned)
    handoff = _load(DD232)
    controlled = dd233._controlled_contract(spec, handoff)
    state = dd232._state(payload["accepted_root_state"])
    inventory = np.asarray(payload["inventory_lbmol"], dtype=float)
    point = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    products = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    coordinate_scale = np.asarray(payload["solver"]["x_scale"], dtype=float)
    settings = _settings(payload)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    provider.set_exact_state_memoization(True, clear=True)
    started = time.perf_counter()
    full = solve_terminal_inventory_control_backward_euler_step(
        controlled,
        spec,
        reference,
        state,
        provider,
        audit,
        previous_inventory_lbmol=inventory,
        previous_controller_memory=memory,
        level_setpoints=setpoints,
        initial_solve_coordinates=point,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=products,
        step_seconds=payload["steps"]["full_seconds"],
        settings=settings,
        name="dd234_full_0p25s",
    )
    half_1 = solve_terminal_inventory_control_backward_euler_step(
        controlled,
        spec,
        reference,
        state,
        provider,
        audit,
        previous_inventory_lbmol=inventory,
        previous_controller_memory=memory,
        level_setpoints=setpoints,
        initial_solve_coordinates=point,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=products,
        step_seconds=payload["steps"]["half_seconds"],
        settings=settings,
        name="dd234_half1_0p125s",
    )
    half_2 = solve_terminal_inventory_control_backward_euler_step(
        controlled,
        spec,
        reference,
        half_1.evaluation.control_evaluation.base.physical_state,
        provider,
        audit,
        previous_inventory_lbmol=half_1.evaluation.endpoint_inventory_lbmol,
        previous_controller_memory=half_1.evaluation.endpoint_controller_memory,
        level_setpoints=setpoints,
        initial_solve_coordinates=half_1.final_coordinates,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        product_reference_lbmolph=products,
        step_seconds=payload["steps"]["half_seconds"],
        settings=settings,
        name="dd234_half2_0p125s",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = _provider_summary(audit)
    outcomes = {"full": full, "half_1": half_1, "half_2": half_2}
    step_seconds = {
        "full": payload["steps"]["full_seconds"],
        "half_1": payload["steps"]["half_seconds"],
        "half_2": payload["steps"]["half_seconds"],
    }
    reports = {
        name: _step_report(
            outcome,
            original_inventory=inventory,
            original_coordinates=point,
            original_memory=memory,
            product_reference=products,
            step_seconds=step_seconds[name],
            coordinate_scale=coordinate_scale,
        )
        for name, outcome in outcomes.items()
    }
    refinement = {
        "relative_inventory_difference": float(
            np.max(
                np.abs(
                    full.evaluation.endpoint_inventory_lbmol
                    - half_2.evaluation.endpoint_inventory_lbmol
                )
                / inventory
            )
        ),
        "rate_coordinate_difference": float(
            np.max(
                np.abs(
                    full.evaluation.rate_coordinates
                    - half_2.evaluation.rate_coordinates
                )
            )
        ),
        "algebraic_coordinate_difference": float(
            np.max(
                np.abs(
                    full.evaluation.algebraic_coordinates
                    - half_2.evaluation.algebraic_coordinates
                )
            )
        ),
        "controller_memory_difference": float(
            np.max(
                np.abs(
                    full.evaluation.endpoint_controller_memory
                    - half_2.evaluation.endpoint_controller_memory
                )
            )
        ),
        "product_relative_difference": float(
            np.max(
                np.abs(
                    np.asarray(
                        (full.evaluation.distillate_lbmolph, full.evaluation.bottoms_lbmolph)
                    )
                    - np.asarray(
                        (half_2.evaluation.distillate_lbmolph, half_2.evaluation.bottoms_lbmolph)
                    )
                )
                / products
            )
        ),
    }
    limits = payload["limits"]
    step_gates = {
        name: {
            "success": report["success"],
            "residual": report["scaled_residual_inf_norm"] < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == payload["required_rank"],
            "condition": report["jacobian_condition"] < limits["condition"],
            "component_rate": report["component_rate_max_abs_lbmolph"] < limits["component_rate_lbmolph"],
            "energy_rate": report["energy_rate_max_abs_BTUph"] < limits["energy_rate_BTUph"],
            "controller_rate": report["controller_rate_max_abs_per_sec"] < limits["controller_rate_per_sec"],
            "inventory": report["relative_inventory_movement"] < limits["relative_inventory_movement"],
            "algebraic": report["algebraic_movement"] < limits["algebraic_movement"],
            "controller_memory": report["controller_memory_movement"] < limits["controller_memory_movement"],
            "product": report["product_relative_movement"] < limits["product_relative_movement"],
            "level": report["maximum_level_error"] < limits["level_error"],
            "equilibrium": report["maximum_equilibrium_residual"] < limits["equilibrium_residual"],
            "component_conservation": report["component_conservation_relative_error"] < limits["component_conservation"],
            "energy_conservation": report["energy_conservation_relative_error"] < limits["energy_conservation"],
            "component_kinematics": report["component_kinematic_identity"] < limits["kinematic_identity"],
            "energy_kinematics": report["energy_kinematic_identity"] < limits["kinematic_identity"],
            "controller_kinematics": report["controller_kinematic_identity"] < limits["kinematic_identity"],
            "physical": report["physical_pass"],
        }
        for name, report in reports.items()
    }
    refinement_gates = {
        "inventory": refinement["relative_inventory_difference"] < limits["refinement_inventory"],
        "rate": refinement["rate_coordinate_difference"] < limits["refinement_rate"],
        "algebraic": refinement["algebraic_coordinate_difference"] < limits["refinement_algebraic"],
        "controller_memory": refinement["controller_memory_difference"] < limits["refinement_controller_memory"],
        "product": refinement["product_relative_difference"] < limits["refinement_product"],
    }
    campaign_gates = {
        "steps": all(all(values.values()) for values in step_gates.values()),
        "refinement": all(refinement_gates.values()),
        "provider": provider_summary["pass"],
        "provider_calls": provider_summary["total_calls"] < limits["provider_calls"],
        "wall_clock": elapsed < limits["wall_clock_sec"],
    }
    passed = all(campaign_gates.values())
    result = {
        "schema_id": RESULT_SCHEMA,
        "classification": (
            "full_c3c4_stationary_hold_passed"
            if passed
            else "full_c3c4_stationary_hold_failed"
        ),
        "decision": (
            "authorize_one_separately_frozen_small_full_c3c4_moving_step"
            if passed
            else "stop_full_c3c4_dynamics_before_moving_conditions"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": float(elapsed),
        "steps": reports,
        "refinement": refinement,
        "step_gates": step_gates,
        "refinement_gates": refinement_gates,
        "campaign_gates": campaign_gates,
        "provider": provider_summary,
        "exact_state_memoization": memo,
        "pass_gate": passed,
        "campaign_executed_once": True,
        "disturbance_attempted": False,
        "controller_tuning_attempted": False,
        "trajectory_attempted": False,
    }
    destination = (ROOT / result_path).with_suffix(".json")
    document = ROOT / result_doc_path
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    document.write_text(_result_markdown(result), encoding="utf-8")
    return result


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    return "\n".join(
        (
            "# DD-234 Full-C3/C4 Stationary Hold Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residuals: `{steps['full']['scaled_residual_inf_norm']:.6e}`, `{steps['half_1']['scaled_residual_inf_norm']:.6e}`, `{steps['half_2']['scaled_residual_inf_norm']:.6e}`",
            f"- Ranks: `{steps['full']['jacobian_rank']} / {steps['half_1']['jacobian_rank']} / {steps['half_2']['jacobian_rank']}`",
            f"- Worst condition: `{max(item['jacobian_condition'] for item in steps.values()):.6e}`",
            f"- Maximum component rate: `{max(item['component_rate_max_abs_lbmolph'] for item in steps.values()):.6e} lbmol/h`",
            f"- Maximum relative inventory motion: `{max(item['relative_inventory_movement'] for item in steps.values()):.6e}`",
            f"- Provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Disturbance, tuning, or trajectory: `False`",
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
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.prepare:
        report = prepare(args.contract, args.contract_doc)
        print(
            json.dumps(
                {
                    "schema_id": report["schema_id"],
                    "contract_payload_sha256": report["contract_payload_sha256"],
                    "required_rank": report["required_rank"],
                    "campaign_executed": report["campaign_executed"],
                },
                indent=2,
            )
        )
        return 0
    report = execute(args.contract, args.result, args.result_doc)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
