#!/usr/bin/env python
"""Prepare or execute DD-186's controlled stationary implicit step."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_seven_volume_dynamic_dae_numerical as dd171  # noqa: E402
import audit_core_v3_seven_volume_terminal_inventory_control_numerical as dd185  # noqa: E402
from dynamic_distillation.core_v3.implicit_step_v1 import (  # noqa: E402
    ImplicitStepSettings,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    audit_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (  # noqa: E402
    TerminalInventoryControlBackwardEulerEvaluation,
    TerminalInventoryControlStepOutcome,
    solve_terminal_inventory_control_backward_euler_step,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (  # noqa: E402
    TerminalLevelSetpoints,
)


SCHEMA = "dd186-core-v3-seven-volume-terminal-control-stationary-step-contract-v1"
RESULT_SCHEMA = "dd186-core-v3-seven-volume-terminal-control-stationary-step-result-v1"
DD185_CONTRACT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_contract_20260813.json"
)
DD185_RESULT = Path(
    "logs/dd185_core_v3_seven_volume_terminal_inventory_control_numerical_20260813.json"
)
CONTRACT = Path(
    "logs/dd186_core_v3_seven_volume_terminal_inventory_control_stationary_step_contract_20260813.json"
)
RESULT = Path(
    "logs/dd186_core_v3_seven_volume_terminal_inventory_control_stationary_step_20260813"
)
CONTRACT_DOC = Path(
    "docs/dd_186_core_v3_seven_volume_terminal_inventory_control_stationary_step_contract_20260813.md"
)
RESULT_DOC = Path(
    "docs/dd_186_core_v3_seven_volume_terminal_inventory_control_stationary_step_20260813.md"
)
SETTINGS = ImplicitStepSettings(
    method="trf",
    ftol=1.0e-12,
    xtol=1.0e-12,
    gtol=1.0e-12,
    max_nfev=20,
    x_scale=1.0,
    jacobian_step=1.0e-5,
    jacobian_mode="colored",
)
IMPLEMENTATION = (
    "src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py",
    "src/dynamic_distillation/core_v3/implicit_step_v1.py",
    "src/dynamic_distillation/core_v3/colored_jacobian_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_contract_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_numerical_v1.py",
    "src/dynamic_distillation/core_v3/terminal_inventory_control_implicit_step_v1.py",
    "tests/test_core_v3_terminal_inventory_control_implicit_step_v1.py",
    "tools/run_core_v3_seven_volume_terminal_inventory_control_stationary_step.py",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _settings(payload: Mapping[str, Any]) -> ImplicitStepSettings:
    values = payload["solver"]
    return ImplicitStepSettings(
        method=str(values["method"]),
        ftol=float(values["ftol"]),
        xtol=float(values["xtol"]),
        gtol=float(values["gtol"]),
        max_nfev=int(values["max_nfev"]),
        x_scale=float(values["x_scale"]),
        jacobian_step=float(values["jacobian_step"]),
        jacobian_mode=str(values["jacobian_mode"]),
    )


def _rank_condition(matrix: Sequence[Sequence[float]]) -> tuple[int, float]:
    values = np.asarray(matrix, dtype=float)
    singular = np.linalg.svd(values, compute_uv=False)
    tolerance = max(values.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition


def _contract_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            "# DD-186 Seven-Volume Controlled Stationary-Step Contract",
            "",
            f"- Payload SHA-256: `{payload['contract_payload_sha256']}`",
            f"- Preparation base commit: `{payload['preparation_base_commit']}`",
            "- Solver: `least_squares(method=trf)`",
            "- Jacobian: topology-generated graph coloring, central difference",
            "- Comparison: one `1.0 s` step versus two `0.5 s` steps",
            "- Terminal setpoints: exact DD-185 live levels",
            "- Initial controller memories and product log ratios: zero",
            "- Product reference rates: fixed DD-169 accepted rates",
            "- Property evaluation during preparation: `False`",
            "- Timestep execution during preparation: `False`",
            "",
            "Commit this immutable contract before its one live execution. No "
            "disturbance, controller tuning, retry, or trajectory is authorized.",
            "",
        )
    )


def _result_markdown(payload: Mapping[str, Any]) -> str:
    steps = payload["steps"]
    return "\n".join(
        (
            "# DD-186 Seven-Volume Controlled Stationary-Step Result",
            "",
            f"- Classification: `{payload['classification']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Residuals: `{steps['full']['residual_inf_norm']:.6e}`, "
            f"`{steps['half1']['residual_inf_norm']:.6e}`, "
            f"`{steps['half2']['residual_inf_norm']:.6e}`",
            f"- Ranks: `{steps['full']['jacobian_rank']} / "
            f"{steps['half1']['jacobian_rank']} / "
            f"{steps['half2']['jacobian_rank']}`",
            f"- Worst condition: `{payload['worst_condition']:.6e}`",
            f"- Maximum controller-memory motion: "
            f"`{payload['maximum_controller_memory_movement']:.6e}`",
            f"- Maximum product relative motion: "
            f"`{payload['maximum_product_relative_movement']:.6e}`",
            f"- Logical provider calls: `{payload['provider']['total_calls']}`",
            f"- Wall clock: `{payload['wall_clock_sec']:.3f} s`",
            "- Disturbance/tuning/trajectory attempted: `False / False / False`",
            "",
        )
    )


def prepare(
    dd185_contract_path: Path,
    dd185_result_path: Path,
    contract_path: Path,
    contract_doc_path: Path,
) -> dict[str, Any]:
    source = _load(dd185_contract_path)
    result = _load(dd185_result_path)
    if not result["pass_gate"] or result["decision"] != (
        "authorize_one_frozen_controlled_stationary_root_hold_step_contract"
    ):
        raise RuntimeError("DD-186 requires the accepted DD-185 result")
    payload: dict[str, Any] = {
        "schema_id": SCHEMA,
        "preparation_base_commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (dd185_contract_path, dd185_result_path)
        },
        "workbook": source["workbook"],
        "workbook_sha256": source["workbook_sha256"],
        "property_package": source["property_package"],
        "source_mapping": source["source_mapping"],
        "operating_spec": source["operating_spec"],
        "reference": source["reference"],
        "accepted_root_state": source["accepted_root_state"],
        "accepted_root_inventory_lbmol": source["accepted_root_inventory_lbmol"],
        "initial_solve_coordinates": source["root_solve_coordinates"],
        "initial_controller_memory": source["controller_memory"],
        "level_setpoints": result["terminal_levels"],
        "product_reference_lbmolph": source["product_reference_lbmolph"],
        "geometry": source["geometry"],
        "controllers": source["controllers"],
        "fixed_steady_residual_scales": source["fixed_steady_residual_scales"],
        "solver": {
            "method": SETTINGS.method,
            "ftol": SETTINGS.ftol,
            "xtol": SETTINGS.xtol,
            "gtol": SETTINGS.gtol,
            "max_nfev": SETTINGS.max_nfev,
            "x_scale": SETTINGS.x_scale,
            "jacobian_step": SETTINGS.jacobian_step,
            "jacobian_mode": SETTINGS.jacobian_mode,
            "product_log_ratio_bounds": source["controllers"][
                "product_rate_ratio_bounds"
            ],
        },
        "paths": {"full": [1.0], "refined": [0.5, 0.5]},
        "limits": {
            "scaled_residual": 1.0e-8,
            "condition": 1.0e8,
            "component_rate_lbmolph": 1.0e-4,
            "relative_inventory_movement": 1.0e-9,
            "algebraic_movement": 1.0e-7,
            "controller_rate_per_sec": 1.0e-9,
            "controller_memory_movement": 1.0e-9,
            "level_error": 1.0e-9,
            "product_relative_movement": 1.0e-9,
            "equilibrium_residual": 1.0e-10,
            "component_conservation": 1.0e-8,
            "energy_conservation": 1.0e-8,
            "kinematic_identity": 1.0e-12,
            "controller_kinematic_identity": 1.0e-15,
            "refinement_inventory": 1.0e-9,
            "refinement_rate_coordinate": 1.0e-7,
            "refinement_algebraic": 1.0e-7,
            "refinement_controller_memory": 1.0e-9,
            "refinement_product": 1.0e-9,
            "provider_calls": 40000,
            "wall_clock_sec": 120.0,
        },
        "required_rank": 58,
        "exact_state_memoization": {
            "enabled": True,
            "exact_unrounded_keys": True,
            "cleared_before_execution": True,
        },
        "implementation_sha256": {path: _sha(ROOT / path) for path in IMPLEMENTATION},
        "hard_stops": [
            "any of the three controlled implicit roots fails",
            "any rank, condition, closure, physical, or conservation gate fails",
            "inventory, product, level, or controller memory moves beyond its limit",
            "full and refined endpoints disagree beyond a frozen limit",
            "provider ownership, call, or wall gate fails",
        ],
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "disturbance_attempted": False,
        "controller_tuning_attempted": False,
        "trajectory_attempted": False,
        "campaign_executed": False,
    }
    payload["contract_payload_sha256"] = _hash(payload)
    destination = ROOT / contract_path
    document = ROOT / contract_doc_path
    if destination.exists() or document.exists():
        raise RuntimeError("DD-186 contract already exists")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    document.write_text(_contract_markdown(payload), encoding="utf-8")
    return payload


def _verify(payload: dict[str, Any], contract_path: Path, result_path: Path) -> None:
    claimed = payload.pop("contract_payload_sha256")
    actual = _hash(payload)
    payload["contract_payload_sha256"] = claimed
    if claimed != actual:
        raise RuntimeError("DD-186 contract payload hash mismatch")
    for path, expected in payload["sources"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-186 source changed: {path}")
    for path, expected in payload["implementation_sha256"].items():
        if _sha(ROOT / path) != expected:
            raise RuntimeError(f"DD-186 implementation changed: {path}")
    if _sha(Path(payload["workbook"])) != payload["workbook_sha256"]:
        raise RuntimeError("DD-186 workbook changed")
    if (ROOT / result_path).with_suffix(".json").exists():
        raise RuntimeError("DD-186 result exists; rerun is prohibited")
    if not _git("ls-files", "--error-unmatch", str(contract_path)):
        raise RuntimeError("DD-186 contract is not committed")


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
    outcome: TerminalInventoryControlStepOutcome,
    spec: Any,
    original_inventory: np.ndarray,
    initial_coordinates: np.ndarray,
    initial_memory: np.ndarray,
    level_setpoints: np.ndarray,
    product_reference: np.ndarray,
    step_seconds: float,
) -> dict[str, Any]:
    evaluation = outcome.evaluation
    if not isinstance(evaluation, TerminalInventoryControlBackwardEulerEvaluation):
        raise TypeError("DD-186 step lacks a controlled backward-Euler evaluation")
    state = evaluation.control_evaluation.base.physical_state
    properties = evaluation.control_evaluation.base.steady_evaluation.properties
    rank, condition = _rank_condition(outcome.final_jacobian)
    step_hours = float(step_seconds) / 3600.0
    component_external = (
        np.asarray(spec.feed_component_lbmolph, dtype=float)
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )
    component_error = (
        np.sum(evaluation.component_rate_lbmolph, axis=0) - component_external
    )
    component_scale = max(float(np.max(np.abs(spec.feed_component_lbmolph))), 1.0)
    energy_external = (
        float(spec.feed_enthalpy_BTUph)
        + float(spec.reboiler_duty_BTUph)
        + float(state.condenser_duty_BTUph)
        - state.distillate_lbmolph * properties.liquid_enthalpy_BTU_lbmol[0]
        - state.bottoms_lbmolph * properties.liquid_enthalpy_BTU_lbmol[-1]
    )
    energy_error = float(np.sum(evaluation.energy_storage_rate_BTUph) - energy_external)
    energy_scale = max(
        abs(float(spec.feed_enthalpy_BTUph)),
        abs(float(spec.reboiler_duty_BTUph)),
        abs(float(state.condenser_duty_BTUph)),
        1.0,
    )
    products = np.asarray(
        (evaluation.distillate_lbmolph, evaluation.bottoms_lbmolph), dtype=float
    )
    algebraic_start = len(outcome.final_coordinates) - (
        len(evaluation.algebraic_coordinates) + 2
    )
    initial_algebraic_and_product = initial_coordinates[algebraic_start:]
    final_algebraic_and_product = outcome.final_coordinates[algebraic_start:]
    hydraulic_indices = [
        spec.topology.volume_ids.index(volume)
        for volume in spec.topology.hydraulic_volume_ids
    ]
    heights = np.asarray(properties.liquid_height_ft)[hydraulic_indices]
    spacings = np.asarray(
        [geometry.tray_spacing_ft for geometry in spec.hydraulic_geometry]
    )
    physical = {
        "positive_inventory": bool(np.all(evaluation.endpoint_inventory_lbmol > 0.0)),
        "positive_liquid_composition": bool(np.all(state.liquid_mole_fraction > 0.0)),
        "positive_vapor_composition": bool(np.all(state.vapor_mole_fraction > 0.0)),
        "positive_flows": bool(
            np.all(state.hydraulic_liquid_flow_lbmolph > 0.0)
            and np.all(state.vapor_flow_lbmolph > 0.0)
            and np.all(products > 0.0)
        ),
        "physical_levels": bool(
            np.all(evaluation.level_fraction > 0.01)
            and np.all(evaluation.level_fraction < 0.99)
        ),
        "ordered_temperature": bool(np.all(np.diff(state.temperature_F) > 0.0)),
        "ordered_pressure": bool(np.all(np.diff(spec.pressure_psia) > 0.0)),
        "negative_condenser_duty": bool(state.condenser_duty_BTUph < 0.0),
        "hydraulic_height_below_spacing": bool(np.all(heights < spacings)),
        "all_finite": bool(
            np.all(np.isfinite(outcome.final_coordinates))
            and np.all(np.isfinite(outcome.final_residual))
        ),
    }
    return {
        "success": outcome.success,
        "status": outcome.status,
        "message": outcome.message,
        "nfev": outcome.nfev,
        "njev": outcome.njev,
        "wall_clock_sec": outcome.wall_clock_sec,
        "residual_inf_norm": float(np.max(np.abs(outcome.final_residual))),
        "jacobian_rank": rank,
        "jacobian_condition": condition,
        "component_rate_max_abs_lbmolph": float(
            np.max(np.abs(evaluation.component_rate_lbmolph))
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
            np.max(np.abs(final_algebraic_and_product - initial_algebraic_and_product))
        ),
        "controller_memory_movement": float(
            np.max(np.abs(evaluation.endpoint_controller_memory - initial_memory))
        ),
        "level_error": float(
            np.max(np.abs(evaluation.level_fraction - level_setpoints))
        ),
        "product_relative_movement": float(
            np.max(np.abs(products - product_reference) / product_reference)
        ),
        "component_kinematic_identity": float(
            np.max(
                np.abs(
                    evaluation.endpoint_inventory_lbmol
                    - evaluation.previous_inventory_lbmol
                    - evaluation.component_rate_lbmolph * step_hours
                )
            )
        ),
        "energy_kinematic_identity": float(
            np.max(
                np.abs(
                    evaluation.endpoint_internal_energy_BTU
                    - evaluation.previous_internal_energy_BTU
                    - evaluation.energy_storage_rate_BTUph * step_hours
                )
            )
        ),
        "controller_kinematic_identity": float(
            np.max(
                np.abs(
                    evaluation.endpoint_controller_memory
                    - evaluation.previous_controller_memory
                    - evaluation.controller_rate_per_sec * step_seconds
                )
            )
        ),
        "maximum_equilibrium_residual": evaluation.maximum_equilibrium_residual,
        "component_conservation_relative_error": float(
            np.max(np.abs(component_error)) / component_scale
        ),
        "energy_conservation_relative_error": abs(energy_error) / energy_scale,
        "inventory_lbmol": _rows(evaluation.endpoint_inventory_lbmol),
        "rate_coordinates": _rows(evaluation.rate_coordinates),
        "algebraic_coordinates": _vector(evaluation.algebraic_coordinates),
        "controller_memory": _vector(evaluation.endpoint_controller_memory),
        "level_fraction": _vector(evaluation.level_fraction),
        "product_log_ratio": _vector(evaluation.product_log_ratio),
        "distillate_lbmolph": evaluation.distillate_lbmolph,
        "bottoms_lbmolph": evaluation.bottoms_lbmolph,
        "physical": physical,
        "physical_pass": all(physical.values()),
    }


def execute(
    contract_path: Path,
    result_path: Path,
    result_doc_path: Path,
) -> dict[str, Any]:
    payload = _load(contract_path)
    _verify(payload, contract_path, result_path)
    dd185_contract = _load(DD185_CONTRACT)
    spec = dd171.dd168._spec(
        payload["source_mapping"],
        float(payload["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = dd171.dd168._reference(payload["reference"])
    state = dd171._state(payload["accepted_root_state"])
    controlled = dd185._controlled_contract(spec, dd185_contract)
    structural = audit_terminal_inventory_control_contract(controlled)
    if not structural.pass_gate or structural.solve_variable_count != 58:
        raise RuntimeError("DD-186 controlled structural contract changed")
    inventory = np.asarray(payload["accepted_root_inventory_lbmol"], dtype=float)
    initial = np.asarray(payload["initial_solve_coordinates"], dtype=float)
    memory = np.asarray(payload["initial_controller_memory"], dtype=float)
    setpoints = TerminalLevelSetpoints(**payload["level_setpoints"])
    setpoint_values = np.asarray(
        (setpoints.top_fraction, setpoints.bottom_fraction), dtype=float
    )
    product_reference = np.asarray(payload["product_reference_lbmolph"], dtype=float)
    provider = dd171._provider(Path(payload["workbook"]), payload["property_package"])
    provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit()
    settings = _settings(payload)
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
        initial_solve_coordinates=initial,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=1.0,
        settings=settings,
        name="dd186_full_1s",
    )
    half1 = solve_terminal_inventory_control_backward_euler_step(
        controlled,
        spec,
        reference,
        state,
        provider,
        audit,
        previous_inventory_lbmol=inventory,
        previous_controller_memory=memory,
        level_setpoints=setpoints,
        initial_solve_coordinates=initial,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=0.5,
        settings=settings,
        name="dd186_half1_0p5s",
    )
    half1_state = half1.evaluation.control_evaluation.base.physical_state
    half2 = solve_terminal_inventory_control_backward_euler_step(
        controlled,
        spec,
        reference,
        half1_state,
        provider,
        audit,
        previous_inventory_lbmol=half1.evaluation.endpoint_inventory_lbmol,
        previous_controller_memory=half1.evaluation.endpoint_controller_memory,
        level_setpoints=setpoints,
        initial_solve_coordinates=half1.final_coordinates,
        fixed_steady_scales=payload["fixed_steady_residual_scales"],
        step_seconds=0.5,
        settings=settings,
        name="dd186_half2_0p5s",
    )
    elapsed = time.perf_counter() - started
    memo = provider.get_exact_state_memoization_stats()
    provider.set_exact_state_memoization(False, clear=True)
    provider_summary = _provider_summary(audit)
    outcomes = {"full": full, "half1": half1, "half2": half2}
    step_seconds = {"full": 1.0, "half1": 0.5, "half2": 0.5}
    reports = {
        name: _step_report(
            outcome,
            spec,
            inventory,
            initial,
            memory,
            setpoint_values,
            product_reference,
            step_seconds[name],
        )
        for name, outcome in outcomes.items()
    }
    refinement = {
        "relative_inventory_difference": float(
            np.max(
                np.abs(
                    full.evaluation.endpoint_inventory_lbmol
                    - half2.evaluation.endpoint_inventory_lbmol
                )
                / inventory
            )
        ),
        "rate_coordinate_difference": float(
            np.max(
                np.abs(
                    full.evaluation.rate_coordinates - half2.evaluation.rate_coordinates
                )
            )
        ),
        "algebraic_coordinate_difference": float(
            np.max(
                np.abs(
                    full.evaluation.algebraic_coordinates
                    - half2.evaluation.algebraic_coordinates
                )
            )
        ),
        "controller_memory_difference": float(
            np.max(
                np.abs(
                    full.evaluation.endpoint_controller_memory
                    - half2.evaluation.endpoint_controller_memory
                )
            )
        ),
        "product_relative_difference": float(
            np.max(
                np.abs(
                    np.asarray(
                        (
                            full.evaluation.distillate_lbmolph,
                            full.evaluation.bottoms_lbmolph,
                        )
                    )
                    - np.asarray(
                        (
                            half2.evaluation.distillate_lbmolph,
                            half2.evaluation.bottoms_lbmolph,
                        )
                    )
                )
                / product_reference
            )
        ),
    }
    limits = payload["limits"]
    step_gates = {
        name: {
            "success": report["success"]
            and report["nfev"] <= payload["solver"]["max_nfev"],
            "residual": report["residual_inf_norm"] < limits["scaled_residual"],
            "rank": report["jacobian_rank"] == payload["required_rank"],
            "condition": report["jacobian_condition"] < limits["condition"],
            "stationary_rate": report["component_rate_max_abs_lbmolph"]
            < limits["component_rate_lbmolph"],
            "stationary_inventory": report["relative_inventory_movement"]
            < limits["relative_inventory_movement"],
            "stationary_algebraic": report["algebraic_movement"]
            < limits["algebraic_movement"],
            "stationary_controller_rate": report["controller_rate_max_abs_per_sec"]
            < limits["controller_rate_per_sec"],
            "stationary_controller_memory": report["controller_memory_movement"]
            < limits["controller_memory_movement"],
            "stationary_level": report["level_error"] < limits["level_error"],
            "stationary_product": report["product_relative_movement"]
            < limits["product_relative_movement"],
            "equilibrium": report["maximum_equilibrium_residual"]
            < limits["equilibrium_residual"],
            "component_conservation": report["component_conservation_relative_error"]
            < limits["component_conservation"],
            "energy_conservation": report["energy_conservation_relative_error"]
            < limits["energy_conservation"],
            "component_kinematics": report["component_kinematic_identity"]
            < limits["kinematic_identity"],
            "energy_kinematics": report["energy_kinematic_identity"]
            < limits["kinematic_identity"],
            "controller_kinematics": report["controller_kinematic_identity"]
            < limits["controller_kinematic_identity"],
            "physical": report["physical_pass"],
        }
        for name, report in reports.items()
    }
    refinement_gates = {
        "inventory": refinement["relative_inventory_difference"]
        < limits["refinement_inventory"],
        "rate": refinement["rate_coordinate_difference"]
        < limits["refinement_rate_coordinate"],
        "algebraic": refinement["algebraic_coordinate_difference"]
        < limits["refinement_algebraic"],
        "controller_memory": refinement["controller_memory_difference"]
        < limits["refinement_controller_memory"],
        "product": refinement["product_relative_difference"]
        < limits["refinement_product"],
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
            "terminal_inventory_control_stationary_step_passed"
            if passed
            else "terminal_inventory_control_stationary_step_failed"
        ),
        "decision": (
            "authorize_one_frozen_small_controlled_moving_step_contract"
            if passed
            else "stop_terminal_control_before_moving_dynamics"
        ),
        "contract_commit": _git("rev-parse", "HEAD"),
        "contract_payload_sha256": payload["contract_payload_sha256"],
        "wall_clock_sec": float(elapsed),
        "steps": reports,
        "refinement": refinement,
        "worst_condition": max(
            report["jacobian_condition"] for report in reports.values()
        ),
        "maximum_controller_memory_movement": max(
            report["controller_memory_movement"] for report in reports.values()
        ),
        "maximum_product_relative_movement": max(
            report["product_relative_movement"] for report in reports.values()
        ),
        "exact_state_memoization": memo,
        "provider": provider_summary,
        "step_gates": step_gates,
        "refinement_gates": refinement_gates,
        "campaign_gates": campaign_gates,
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--dd185-contract", type=Path, default=DD185_CONTRACT)
    parser.add_argument("--dd185-result", type=Path, default=DD185_RESULT)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--result", type=Path, default=RESULT)
    parser.add_argument("--contract-doc", type=Path, default=CONTRACT_DOC)
    parser.add_argument("--result-doc", type=Path, default=RESULT_DOC)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    if args.prepare:
        output = prepare(
            args.dd185_contract,
            args.dd185_result,
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
