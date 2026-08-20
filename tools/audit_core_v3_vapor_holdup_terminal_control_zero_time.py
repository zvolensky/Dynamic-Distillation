#!/usr/bin/env python
"""Audit the live bumpless terminal-control handoff at the stationary root."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_vapor_holdup_stationary_residual as dd243  # noqa: E402
from run_core_v3_vapor_holdup_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
    terminal_level_fractions,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_zero_time_v1 import (  # noqa: E402
    bumpless_controller_state,
    controlled_zero_time_coordinates,
    evaluate_vapor_holdup_terminal_zero_time,
    vapor_holdup_terminal_control_pattern,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)


SOURCE_ROOT = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.json"
)
SOURCE_STRUCTURE = Path(
    "logs/dd263_core_v3_vapor_holdup_terminal_control_contract_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd264_core_v3_c3c4_vapor_holdup_terminal_control_zero_time_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_264_core_v3_c3c4_vapor_holdup_terminal_control_zero_time_20260820.md"
)
DEFAULT_MATRIX = Path(
    "logs/dd264_core_v3_c3c4_vapor_holdup_terminal_control_zero_time_20260820.npz"
)
TIMESTEP_SEC = 0.25
STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_LIMIT = 1.0e-8
CONTROLLER_RESIDUAL_LIMIT = 1.0e-10
PRODUCT_PARITY_LIMIT = 1.0e-12
CONDITION_LIMIT = 1.0e8
SPECTRUM_LIMIT = 0.25
MATRIX_LIMIT = 0.05
CALL_LIMIT = 35000
WALL_LIMIT_SEC = 180.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(
        float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30
    )
    return float(np.linalg.norm(left - right) / denominator)


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    root = json.loads((ROOT / SOURCE_ROOT).read_text(encoding="utf-8"))
    structure = json.loads((ROOT / SOURCE_STRUCTURE).read_text(encoding="utf-8"))
    if not root.get("pass_gate") or not structure.get("pass_gate"):
        raise RuntimeError("DD-264 requires accepted DD-245 and DD-263 sources")
    problem = dd243.build_problem()
    endpoint = root["endpoint"]
    liquid_inventory = np.asarray(
        endpoint["liquid_component_inventory_lbmol"], dtype=float
    )
    vapor_inventory = np.asarray(
        endpoint["vapor_component_inventory_lbmol"], dtype=float
    )
    temperature = np.asarray(endpoint["temperature_F"], dtype=float)
    pressure = np.asarray(endpoint["pressure_psia"], dtype=float)
    phase_transfer = np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float)
    liquid_flow = np.asarray(
        endpoint["hydraulic_liquid_flow_lbmolph"], dtype=float
    )
    vapor_flow = np.asarray(endpoint["vapor_flow_lbmolph"], dtype=float)
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    energy_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    properties = evaluate_vapor_holdup_trial_properties(
        problem["geometry"],
        liquid_inventory,
        vapor_inventory,
        temperature,
        pressure,
        provider,
        energy_audit,
        state_id="dd264:energy_and_level_history",
        evaluation_kind="residual",
    )
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=vapor_inventory,
        phase_transfer_lbmolph=phase_transfer,
        phase_transfer_scale_lbmolph=np.maximum(
            np.abs(phase_transfer),
            problem["numerical"].component_residual_scale_lbmolph,
        ),
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        vapor_flow_lbmolph=vapor_flow,
        condenser_duty_BTUph=float(endpoint["condenser_duty_BTUph"]),
        total_stored_energy_BTU=properties.total_stored_energy_BTU,
    )
    balance_inputs = replace(
        problem["balance_inputs"],
        distillate_lbmolph=float(endpoint["distillate_lbmolph"]),
        bottoms_lbmolph=float(endpoint["bottoms_lbmolph"]),
        condenser_duty_BTUph=float(endpoint["condenser_duty_BTUph"]),
    )
    stationary_numerical = problem["numerical"]
    numerical = VaporHoldupImplicitNumericalSpec(
        timestep_sec=TIMESTEP_SEC,
        temperature_coordinate_scale_F=(
            stationary_numerical.temperature_coordinate_scale_F
        ),
        pressure_coordinate_scale_psia=(
            stationary_numerical.pressure_coordinate_scale_psia
        ),
        dry_tray_pressure_drop_coefficient=(
            stationary_numerical.dry_tray_pressure_drop_coefficient
        ),
        component_mw_lbm_per_lbmol=(
            stationary_numerical.component_mw_lbm_per_lbmol
        ),
        pressure_link_geometry=stationary_numerical.pressure_link_geometry,
        top_pressure_anchor_psia=float(pressure[0]),
        component_residual_scale_lbmolph=(
            stationary_numerical.component_residual_scale_lbmolph
        ),
        energy_residual_scale_BTUph=(
            stationary_numerical.energy_residual_scale_BTUph
        ),
        pressure_residual_scale_psia=(
            stationary_numerical.pressure_residual_scale_psia
        ),
    )
    workbook = Path(problem["source"]["workbook"])
    case = load_case_from_excel(str(workbook))
    terminal_geometry = terminal_geometry_from_specs(case.specs)
    controllers = level_controllers_from_specs(case.specs)
    base_contract = build_vapor_holdup_dae_contract(
        problem["contract"].component_names,
        topology=problem["contract"].topology,
    )
    contract = build_vapor_holdup_terminal_control_contract(
        base_contract,
        geometry=terminal_geometry,
        controllers=controllers,
    )
    initial_levels = terminal_level_fractions(
        liquid_inventory,
        properties.liquid_density_lbmol_ft3,
        terminal_geometry,
    )
    controller_rates, controller_memory, product_logs = bumpless_controller_state(
        contract, initial_levels
    )
    point = controlled_zero_time_coordinates(
        contract,
        controller_rates_per_sec=controller_rates,
        product_log_ratios=product_logs,
    )
    pattern = vapor_holdup_terminal_control_pattern(contract)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_vapor_holdup_terminal_zero_time(
            contract,
            problem["geometry"],
            reference,
            balance_inputs,
            problem["spec"].hydraulic_geometry,
            numerical,
            provider,
            audit,
            candidate,
            controller_memory=controller_memory,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled

    residual = evaluate_vapor_holdup_terminal_zero_time(
        contract,
        problem["geometry"],
        reference,
        balance_inputs,
        problem["spec"].hydraulic_geometry,
        numerical,
        provider,
        audit,
        point,
        controller_memory=controller_memory,
        state_id="dd264:zero_time_residual",
        evaluation_kind="residual",
    )
    matrices: list[np.ndarray] = []
    step_results: list[dict[str, Any]] = []
    for step in STEPS:
        matrix, groups = colored_central_difference_jacobian(
            objective,
            point,
            pattern=pattern,
            step=step,
            state_id=f"dd264:h={step:.1e}",
        )
        rank, condition, singular = _rank_condition(matrix)
        matrices.append(matrix)
        step_results.append(
            {
                "step": step,
                "rank": rank,
                "condition": condition,
                "singular_values": [float(value) for value in singular],
                "color_count": len(groups),
                "zero_rows": int(
                    np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)
                ),
                "zero_columns": int(
                    np.count_nonzero(np.linalg.norm(matrix, axis=0) <= 1.0e-12)
                ),
            }
        )
    spectrum_change = _relative_change(
        np.asarray(step_results[0]["singular_values"]),
        np.asarray(step_results[1]["singular_values"]),
    )
    matrix_change = _relative_change(matrices[0], matrices[1])
    residual_norm = float(np.max(np.abs(residual.scaled)))
    controller_residual = float(np.max(np.abs(residual.scaled[-4:])))
    inventory_rate = float(
        max(
            np.max(np.abs(residual.base.endpoint.liquid_component_rate_lbmolph)),
            np.max(np.abs(residual.base.endpoint.vapor_component_rate_lbmolph)),
        )
    )
    product_relative_difference = np.asarray(
        (
            residual.distillate_lbmolph / float(endpoint["distillate_lbmolph"]) - 1.0,
            residual.bottoms_lbmolph / float(endpoint["bottoms_lbmolph"]) - 1.0,
        )
    )
    provider_pass = bool(
        energy_audit.report()["pass"]
        and audit.report()["pass"]
        and not energy_audit.fallback_attempted
        and not audit.fallback_attempted
    )
    wall = time.perf_counter() - started
    passed = bool(
        residual_norm < RESIDUAL_LIMIT
        and controller_residual < CONTROLLER_RESIDUAL_LIMIT
        and inventory_rate == 0.0
        and np.max(np.abs(product_relative_difference)) < PRODUCT_PARITY_LIMIT
        and np.all((residual.level_fraction > 0.01) & (residual.level_fraction < 0.99))
        and np.all(np.isfinite(residual.controller_memory))
        and np.all(np.isfinite(residual.controller_rate_per_sec))
        and all(item["rank"] == 262 for item in step_results)
        and all(item["condition"] < CONDITION_LIMIT for item in step_results)
        and all(item["zero_rows"] == 0 for item in step_results)
        and all(item["zero_columns"] == 0 for item in step_results)
        and spectrum_change < SPECTRUM_LIMIT
        and matrix_change < MATRIX_LIMIT
        and provider_pass
        and energy_audit.record_count + audit.record_count < CALL_LIMIT
        and wall < WALL_LIMIT_SEC
    )
    report = {
        "schema_id": "dd264-core-v3-c3c4-vapor-holdup-terminal-control-zero-time-v1",
        "classification": (
            "vapor_holdup_terminal_control_zero_time_passed"
            if passed
            else "vapor_holdup_terminal_control_zero_time_failed"
        ),
        "sources": {
            str(SOURCE_ROOT).replace("\\", "/"): _sha256(ROOT / SOURCE_ROOT),
            str(SOURCE_STRUCTURE).replace("\\", "/"): _sha256(
                ROOT / SOURCE_STRUCTURE
            ),
            str(workbook): _sha256(workbook),
        },
        "timestep_basis_sec": TIMESTEP_SEC,
        "dimension": 262,
        "scaled_residual_inf_norm": residual_norm,
        "controller_residual_inf_norm": controller_residual,
        "maximum_physical_inventory_rate_lbmolph": inventory_rate,
        "terminal_levels": {
            "reflux_drum_fraction": float(residual.level_fraction[0]),
            "bottom_sump_fraction": float(residual.level_fraction[1]),
            "setpoint_fraction": [
                controllers.drum_level_setpoint_fraction,
                controllers.sump_level_setpoint_fraction,
            ],
            "error_fraction": residual.level_error.tolist(),
        },
        "bumpless_initialization": {
            "controller_memory": residual.controller_memory.tolist(),
            "controller_rate_per_sec": residual.controller_rate_per_sec.tolist(),
            "product_log_ratio": residual.product_log_ratio.tolist(),
            "distillate_lbmolph": residual.distillate_lbmolph,
            "bottoms_lbmolph": residual.bottoms_lbmolph,
            "source_distillate_lbmolph": float(endpoint["distillate_lbmolph"]),
            "source_bottoms_lbmolph": float(endpoint["bottoms_lbmolph"]),
            "product_relative_difference": product_relative_difference.tolist(),
            "instantaneous_product_jump": False,
            "controller_integrators_stationary": bool(
                np.all(residual.controller_rate_per_sec == 0.0)
            ),
            "interpretation": (
                "Physical inventories and D/B are motionless at activation. PI "
                "integrators move smoothly because reconstructed levels differ "
                "from the workbook 50 percent setpoints."
            ),
        },
        "geometry": {
            "drum_diameter_ft": terminal_geometry.drum_diameter_ft,
            "drum_tangent_length_ft": terminal_geometry.drum_tangent_length_ft,
            "sump_diameter_ft": terminal_geometry.sump_diameter_ft,
            "sump_height_ft": terminal_geometry.sump_height_ft,
        },
        "jacobian_steps": step_results,
        "spectrum_relative_change": spectrum_change,
        "matrix_relative_change": matrix_change,
        "provider": {
            "energy_and_level_reconstruction": compact_provider_report(
                energy_audit.report()
            ),
            "residual_and_jacobian": compact_provider_report(audit.report()),
            "total_calls": energy_audit.record_count + audit.record_count,
            "pass_gate": provider_pass,
        },
        "wall_clock_sec": wall,
        "nonlinear_solve_attempted": False,
        "timestep_accepted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_separately_frozen_stationary_control_hold_step"
            if passed
            else "stop_and_correct_vapor_holdup_terminal_control_handoff"
        ),
    }
    evidence = {
        "zero_time_coordinates": point,
        "controller_memory": controller_memory,
        "zero_time_scaled_residual": residual.scaled,
        "terminal_level_fraction": residual.level_fraction,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["jacobian_steps"]
    levels = report["terminal_levels"]
    initial = report["bumpless_initialization"]
    return "\n".join(
        (
            "# DD-264 Vapor-Holdup Terminal-Control Zero-Time Audit",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Controller residual maximum: `{report['controller_residual_inf_norm']:.6e}`",
            f"- Physical inventory-rate maximum: `{report['maximum_physical_inventory_rate_lbmolph']:.6e} lbmol/h`",
            f"- Reflux-drum level: `{levels['reflux_drum_fraction']:.6f}`",
            f"- Bottom-sump level: `{levels['bottom_sump_fraction']:.6f}`",
            f"- Level setpoints: `{levels['setpoint_fraction']}`",
            f"- Initial D/B: `{initial['distillate_lbmolph']:.6f} / {initial['bottoms_lbmolph']:.6f} lbmol/h`",
            f"- Controller memory: `{initial['controller_memory']}`",
            f"- Controller rates: `{initial['controller_rate_per_sec']} 1/s`",
            "- Instantaneous product-flow jump: `False`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- Provider calls: `{report['provider']['total_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            "- Nonlinear solve or accepted timestep: `False`",
            "",
            "The physical column and product rates are motionless at controller "
            "activation. The PI memories cancel the initial proportional terms, "
            "so enabling control causes no D/B jump. The integrators are not "
            "stationary because the live levels differ from the 50% setpoints; "
            "they will begin a smooth corrective response on the first timestep.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    report, evidence = execute()
    json_path = ROOT / args.json
    doc_path = ROOT / args.doc
    matrix_path = ROOT / args.matrix
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    np.savez_compressed(matrix_path, **evidence)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
                "levels": report["terminal_levels"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
