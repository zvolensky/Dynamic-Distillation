#!/usr/bin/env python
"""Audit the accepted vapor-holdup root as a zero-motion implicit state."""

from __future__ import annotations

import argparse
from dataclasses import replace
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
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)


SOURCE_ROOT = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd247_core_v3_c3c4_vapor_holdup_zero_motion_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_247_core_v3_c3c4_vapor_holdup_zero_motion_20260820.md"
)
DEFAULT_MATRIX = Path(
    "logs/dd247_core_v3_c3c4_vapor_holdup_zero_motion_20260820.npz"
)
TIMESTEP_SEC = 0.25
STEPS = (1.0e-5, 5.0e-6)
CONDITION_LIMIT = 1.0e8
SPECTRUM_LIMIT = 0.25
MATRIX_LIMIT = 0.05
RESIDUAL_LIMIT = 1.0e-8
CALL_LIMIT = 30000
WALL_LIMIT_SEC = 180.0


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
    if not root.get("pass_gate"):
        raise RuntimeError("DD-247 requires the accepted DD-245 root")
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
        state_id="dd247:energy_history",
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
    contract = build_vapor_holdup_dae_contract(
        problem["contract"].component_names,
        topology=problem["contract"].topology,
        product_flow_parameters=("D_dd245_root", "B_dd245_root"),
    )
    point = np.zeros(258)
    pattern = vapor_holdup_structural_pattern(contract)
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )

    def objective(candidate: np.ndarray, state_id: str) -> np.ndarray:
        return evaluate_vapor_holdup_implicit_residual(
            contract,
            problem["geometry"],
            reference,
            balance_inputs,
            problem["spec"].hydraulic_geometry,
            numerical,
            provider,
            audit,
            candidate,
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled

    residual = evaluate_vapor_holdup_implicit_residual(
        contract,
        problem["geometry"],
        reference,
        balance_inputs,
        problem["spec"].hydraulic_geometry,
        numerical,
        provider,
        audit,
        point,
        state_id="dd247:zero_motion_residual",
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
            state_id=f"dd247:h={step:.1e}",
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
    wall = time.perf_counter() - started
    residual_norm = float(np.max(np.abs(residual.scaled)))
    energy_identity = bool(
        np.array_equal(
            properties.total_stored_energy_BTU,
            reference.total_stored_energy_BTU,
        )
    )
    rates_zero = bool(
        np.all(residual.endpoint.liquid_component_rate_lbmolph == 0.0)
        and np.all(residual.endpoint.vapor_component_rate_lbmolph == 0.0)
    )
    provider_pass = bool(
        energy_audit.report()["pass"]
        and audit.report()["pass"]
        and not energy_audit.fallback_attempted
        and not audit.fallback_attempted
    )
    passed = bool(
        residual_norm < RESIDUAL_LIMIT
        and energy_identity
        and rates_zero
        and all(item["rank"] == 258 for item in step_results)
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
        "schema_id": "dd247-core-v3-c3c4-vapor-holdup-zero-motion-v1",
        "classification": (
            "vapor_holdup_zero_motion_passed"
            if passed
            else "vapor_holdup_zero_motion_failed"
        ),
        "timestep_sec": TIMESTEP_SEC,
        "dimension": 258,
        "scaled_residual_inf_norm": residual_norm,
        "maximum_inventory_rate_lbmolph": float(
            max(
                np.max(np.abs(residual.endpoint.liquid_component_rate_lbmolph)),
                np.max(np.abs(residual.endpoint.vapor_component_rate_lbmolph)),
            )
        ),
        "energy_history": {
            "current_total_energy_BTU": properties.total_stored_energy_BTU.tolist(),
            "previous_total_energy_BTU": properties.total_stored_energy_BTU.tolist(),
            "current_previous_identical": energy_identity,
            "liquid_total_BTU": float(np.sum(properties.liquid_stored_energy_BTU)),
            "vapor_total_BTU": float(np.sum(properties.vapor_stored_energy_BTU)),
            "combined_total_BTU": float(np.sum(properties.total_stored_energy_BTU)),
        },
        "jacobian_steps": step_results,
        "spectrum_relative_change": spectrum_change,
        "matrix_relative_change": matrix_change,
        "provider": {
            "energy_reconstruction": compact_provider_report(energy_audit.report()),
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
            "authorize_one_stationary_hold_step_contract"
            if passed
            else "stop_and_correct_vapor_holdup_dynamic_handoff"
        ),
    }
    evidence = {
        "zero_motion_scaled_residual": residual.scaled,
        "total_stored_energy_BTU": properties.total_stored_energy_BTU,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["jacobian_steps"]
    energy = report["energy_history"]
    return "\n".join(
        (
            "# DD-247 Vapor-Holdup Zero-Motion Audit",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Nominal implicit step: `{report['timestep_sec']} s`",
            f"- Residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Inventory-rate maximum: `{report['maximum_inventory_rate_lbmolph']:.6e} lbmol/h`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- Liquid/vapor stored energy: `{energy['liquid_total_BTU']:.6e} / {energy['vapor_total_BTU']:.6e} BTU`",
            f"- Provider calls: `{report['provider']['total_calls']}`",
            f"- Wall clock: `{report['wall_clock_sec']:.3f} s`",
            "- Nonlinear solve or accepted timestep: `False`",
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
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
