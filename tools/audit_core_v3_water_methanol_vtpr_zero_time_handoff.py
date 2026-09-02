#!/usr/bin/env python
"""Audit the accepted stationary state in the fixed-product dynamic DAE at zero time."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
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

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
from run_core_v3_water_methanol_stationary_root import (  # noqa: E402
    compact_provider_report,
)

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dae_contract,
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
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    terminal_geometry_from_specs,
    terminal_level_fractions,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402


DEFAULT_SOURCE = Path(
    "logs/core_v3_water_methanol_vtpr_phase_total_stationary_root_20260831.json"
)
DEFAULT_JSON = Path("logs/core_v3_water_methanol_vtpr_zero_time_handoff_20260831.json")
DEFAULT_DOC = Path("docs/core_v3_water_methanol_vtpr_zero_time_handoff_20260831.md")
DEFAULT_MATRIX = Path("logs/core_v3_water_methanol_vtpr_zero_time_handoff_20260831.npz")
TIMESTEP_BASIS_SEC = 0.25
STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_LIMIT = 1.0e-8
STATE_PARITY_LIMIT = 1.0e-12
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.25
MATRIX_CHANGE_LIMIT = 0.05
CALL_LIMIT = 30000
WALL_LIMIT_SEC = 180.0
CONTROLLER_SPEC_KEYS = (
    "Top Level SP Frac",
    "Top Level Kc",
    "Bottom Level SP Frac",
    "Bottom Level Kc",
    "Bottom Level Ti (sec)",
)


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1.0e-30)
    return float(np.linalg.norm(left - right) / denominator)


def _rank_condition(matrix: np.ndarray) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def _maximum_relative_difference(left: Any, right: Any) -> float:
    left_values = np.asarray(left, dtype=float)
    right_values = np.asarray(right, dtype=float)
    denominator = np.maximum(np.maximum(np.abs(left_values), np.abs(right_values)), 1.0)
    return float(np.max(np.abs(left_values - right_values) / denominator))


def execute(source: Path = DEFAULT_SOURCE) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    source_path = _rooted(source).resolve()
    root = json.loads(source_path.read_text(encoding="utf-8"))
    if (
        not root.get("pass_gate")
        or root.get("classification") != "stationary_root_accepted"
        or root.get("density_model") != "VTPR"
        or root.get("bound_policy") != "phase_total"
    ):
        raise RuntimeError("zero-time audit requires the accepted VTPR phase-total root")

    problem = starting_state.build_problem(density_model=root["density_model"])
    endpoint = root["endpoint"]
    liquid_inventory = np.asarray(endpoint["liquid_component_inventory_lbmol"], dtype=float)
    vapor_inventory = np.asarray(endpoint["vapor_component_inventory_lbmol"], dtype=float)
    phase_transfer = np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float)
    temperature = np.asarray(endpoint["temperature_F"], dtype=float)
    pressure = np.asarray(endpoint["pressure_psia"], dtype=float)
    liquid_flow = np.asarray(endpoint["hydraulic_liquid_flow_lbmolph"], dtype=float)
    vapor_flow = np.asarray(endpoint["vapor_flow_lbmolph"], dtype=float)
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)

    energy_audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    properties = evaluate_vapor_holdup_trial_properties(
        problem["geometry"],
        liquid_inventory,
        vapor_inventory,
        temperature,
        pressure,
        provider,
        energy_audit,
        state_id="water_methanol:zero_time:energy_history",
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
        timestep_sec=TIMESTEP_BASIS_SEC,
        temperature_coordinate_scale_F=stationary_numerical.temperature_coordinate_scale_F,
        pressure_coordinate_scale_psia=stationary_numerical.pressure_coordinate_scale_psia,
        dry_tray_pressure_drop_coefficient=(
            stationary_numerical.dry_tray_pressure_drop_coefficient
        ),
        component_mw_lbm_per_lbmol=stationary_numerical.component_mw_lbm_per_lbmol,
        pressure_link_geometry=stationary_numerical.pressure_link_geometry,
        top_pressure_anchor_psia=float(pressure[0]),
        component_residual_scale_lbmolph=(
            stationary_numerical.component_residual_scale_lbmolph
        ),
        energy_residual_scale_BTUph=stationary_numerical.energy_residual_scale_BTUph,
        pressure_residual_scale_psia=stationary_numerical.pressure_residual_scale_psia,
    )

    contract = build_vapor_holdup_dae_contract(
        problem["contract"].component_names,
        topology=problem["contract"].topology,
    )
    structural = audit_vapor_holdup_dae_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("fixed-product dynamic structure did not pass")
    dimension = len(contract.rows)
    point = np.zeros(dimension, dtype=float)
    pattern = vapor_holdup_structural_pattern(contract)
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])

    def evaluate(candidate: np.ndarray, state_id: str, kind: str = "jacobian") -> Any:
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
            evaluation_kind=kind,
        )

    residual = evaluate(point, "water_methanol:zero_time:residual", "residual")
    matrices = []
    step_results = []
    for step in STEPS:
        matrix, groups = colored_central_difference_jacobian(
            lambda candidate, state_id: evaluate(candidate, state_id).scaled,
            point,
            pattern=pattern,
            step=step,
            state_id=f"water_methanol:zero_time:h={step:.1e}",
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
                "zero_rows": int(np.count_nonzero(np.linalg.norm(matrix, axis=1) <= 1.0e-12)),
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
    inventory_rate = float(
        max(
            np.max(np.abs(residual.endpoint.liquid_component_rate_lbmolph)),
            np.max(np.abs(residual.endpoint.vapor_component_rate_lbmolph)),
        )
    )
    state_parity = {
        "liquid_component_inventory": _maximum_relative_difference(
            residual.endpoint.liquid_component_inventory_lbmol,
            liquid_inventory,
        ),
        "vapor_component_inventory": _maximum_relative_difference(
            residual.endpoint.vapor_component_inventory_lbmol,
            vapor_inventory,
        ),
        "phase_transfer": _maximum_relative_difference(
            residual.endpoint.phase_transfer_lbmolph,
            phase_transfer,
        ),
        "temperature": _maximum_relative_difference(residual.endpoint.temperature_F, temperature),
        "pressure": _maximum_relative_difference(residual.endpoint.pressure_psia, pressure),
        "hydraulic_liquid_flow": _maximum_relative_difference(
            residual.endpoint.hydraulic_liquid_flow_lbmolph,
            liquid_flow,
        ),
        "vapor_flow": _maximum_relative_difference(residual.endpoint.vapor_flow_lbmolph, vapor_flow),
        "condenser_duty": _maximum_relative_difference(
            residual.endpoint.condenser_duty_BTUph,
            endpoint["condenser_duty_BTUph"],
        ),
    }
    case = load_case_from_excel(str(problem["workbook"]))
    missing_controller_specs = [key for key in CONTROLLER_SPEC_KEYS if case.specs.get(key) is None]
    terminal_geometry = terminal_geometry_from_specs(case.specs)
    levels = terminal_level_fractions(
        liquid_inventory,
        properties.liquid_density_lbmol_ft3,
        terminal_geometry,
    )
    energy_report = compact_provider_report(energy_audit.report())
    provider_report = compact_provider_report(audit.report())
    provider_pass = bool(
        energy_report["pass"]
        and provider_report["pass"]
        and not energy_audit.fallback_attempted
        and not audit.fallback_attempted
    )
    wall = time.perf_counter() - started
    passed = bool(
        residual_norm < RESIDUAL_LIMIT
        and inventory_rate == 0.0
        and max(state_parity.values()) < STATE_PARITY_LIMIT
        and np.all((levels > 0.01) & (levels < 0.99))
        and all(item["rank"] == dimension for item in step_results)
        and all(item["condition"] < CONDITION_LIMIT for item in step_results)
        and all(item["zero_rows"] == 0 for item in step_results)
        and all(item["zero_columns"] == 0 for item in step_results)
        and spectrum_change < SPECTRUM_CHANGE_LIMIT
        and matrix_change < MATRIX_CHANGE_LIMIT
        and provider_pass
        and energy_audit.record_count + audit.record_count < CALL_LIMIT
        and wall < WALL_LIMIT_SEC
    )
    report = {
        "schema_id": "core-v3-water-methanol-vtpr-zero-time-handoff-v1",
        "classification": (
            "fixed_product_zero_time_dynamic_handoff_passed"
            if passed
            else "fixed_product_zero_time_dynamic_handoff_failed"
        ),
        "source_stationary_root": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "source_stationary_root_sha256": _sha256(source_path),
        "workbook_sha256": _sha256(problem["workbook"]),
        "component_specific_logic": False,
        "handoff_mode": "fixed_terminal_products",
        "controller_mode_selected": False,
        "missing_controller_specifications": missing_controller_specs,
        "density_model": root["density_model"],
        "bound_policy": root["bound_policy"],
        "timestep_basis_sec": TIMESTEP_BASIS_SEC,
        "dimension": dimension,
        "structural_audit": asdict(structural),
        "scaled_residual_inf_norm": residual_norm,
        "maximum_physical_inventory_rate_lbmolph": inventory_rate,
        "state_relative_difference": state_parity,
        "maximum_state_relative_difference": max(state_parity.values()),
        "fixed_terminal_products": {
            "distillate_lbmolph": float(balance_inputs.distillate_lbmolph),
            "bottoms_lbmolph": float(balance_inputs.bottoms_lbmolph),
            "source_distillate_lbmolph": float(endpoint["distillate_lbmolph"]),
            "source_bottoms_lbmolph": float(endpoint["bottoms_lbmolph"]),
            "instantaneous_product_jump": False,
        },
        "terminal_levels": {
            "reflux_drum_fraction": float(levels[0]),
            "bottom_sump_fraction": float(levels[1]),
            "geometry_provenance": terminal_geometry.provenance,
        },
        "jacobian_steps": step_results,
        "spectrum_relative_change": spectrum_change,
        "matrix_relative_change": matrix_change,
        "provider": {
            "energy_and_level_reconstruction": energy_report,
            "residual_and_jacobian": provider_report,
            "total_calls": energy_audit.record_count + audit.record_count,
            "pass_gate": provider_pass,
        },
        "wall_clock_sec": wall,
        "nonlinear_solve_attempted": False,
        "timestep_accepted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_separately_bounded_fixed_product_hold_step"
            if passed
            else "stop_and_correct_zero_time_dynamic_handoff"
        ),
    }
    evidence = {
        "zero_time_coordinates": point,
        "zero_time_scaled_residual": residual.scaled,
        "terminal_level_fraction": levels,
        "jacobian_h1": matrices[0],
        "jacobian_h2": matrices[1],
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    first, second = report["jacobian_steps"]
    levels = report["terminal_levels"]
    products = report["fixed_terminal_products"]
    return "\n".join(
        (
            "# Core V3 water-methanol zero-time dynamic handoff",
            "",
            f"- Result: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Handoff mode: `{report['handoff_mode']}`",
            f"- Residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Physical inventory-rate maximum: `{report['maximum_physical_inventory_rate_lbmolph']:.6e} lbmol/h`",
            f"- Maximum stationary/dynamic state difference: `{report['maximum_state_relative_difference']:.6e}`",
            f"- Reflux-drum/bottom-sump levels: `{levels['reflux_drum_fraction']:.6f} / {levels['bottom_sump_fraction']:.6f}`",
            f"- Fixed D/B: `{products['distillate_lbmolph']:.6f} / {products['bottoms_lbmolph']:.6f} lbmol/h`",
            "- Instantaneous product-flow jump: `False`",
            f"- Jacobian rank: `{first['rank']} / {second['rank']}`",
            f"- Jacobian condition: `{first['condition']:.6e} / {second['condition']:.6e}`",
            f"- Matrix step change: `{report['matrix_relative_change']:.6e}`",
            f"- Missing controller specifications: `{report['missing_controller_specifications']}`",
            "- Nonlinear solve or accepted timestep: `False`",
            "",
            "The stationary state is mapped without a jump into the generic fixed-product dynamic DAE. No controller settings were invented for the workbook.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    report, evidence = execute(args.source)
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    matrix_path = _rooted(args.matrix)
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
                "scaled_residual_inf_norm": report["scaled_residual_inf_norm"],
                "maximum_state_relative_difference": report[
                    "maximum_state_relative_difference"
                ],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
