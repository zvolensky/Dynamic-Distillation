#!/usr/bin/env python
"""Run a short fixed-product feed pulse, then restore the nominal feed."""

from __future__ import annotations

from dataclasses import replace
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
from run_core_v3_water_methanol_stationary_root import compact_provider_report  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_step_bounds_v1 import (  # noqa: E402
    vapor_holdup_implicit_step_coordinate_bounds,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_trial_properties,
)


SOURCE_ROOT = Path(
    "logs/core_v3_water_methanol_vtpr_phase_total_stationary_root_20260831.json"
)
SOURCE_SMALL_STEP = Path(
    "logs/core_v3_water_methanol_vtpr_small_feed_step_20260831.json"
)
SOURCE_SMALL_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_small_feed_step_20260831.npz"
)
DEFAULT_JSON = Path(
    "logs/core_v3_water_methanol_vtpr_feed_pulse_trajectory_20260831.json"
)
DEFAULT_DOC = Path(
    "docs/core_v3_water_methanol_vtpr_feed_pulse_trajectory_20260831.md"
)
DEFAULT_MATRIX = Path(
    "logs/core_v3_water_methanol_vtpr_feed_pulse_trajectory_20260831.npz"
)

TIMESTEP_SEC = 0.25
PULSE_MULTIPLIER = 1.001
PULSE_STEPS = 4
RESTORED_STEPS = 1
DIFFERENCE_STEP = 1.0e-5
ENDPOINT_STEPS = (1.0e-5, 5.0e-6)
RESIDUAL_LIMIT = 1.0e-8
COMPONENT_IDENTITY_LIMIT_LBMOL = 1.0e-6
ENERGY_IDENTITY_RELATIVE_LIMIT = 1.0e-8
ENERGY_IDENTITY_ABSOLUTE_LIMIT_BTU = 1.0e-5
CONDITION_LIMIT = 1.0e8
SPECTRUM_CHANGE_LIMIT = 0.25
MATRIX_CHANGE_LIMIT = 0.05
CALL_LIMIT = 250000
WALL_LIMIT_SEC = 600.0
MAX_NFEV = 20


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


def _coordinate_scale(matrix_path: Path, dimension: int) -> np.ndarray:
    with np.load(matrix_path) as evidence:
        matrix = np.asarray(evidence["jacobian_h1"], dtype=float)
    norms = np.linalg.norm(matrix, axis=0)
    scale = 1.0 / np.maximum(norms, 1.0e-30)
    scale /= np.median(scale)
    if scale.shape != (dimension,) or np.any(~np.isfinite(scale)) or np.any(scale <= 0.0):
        raise RuntimeError("small-step Jacobian produced an invalid coordinate scale")
    return scale


def _physical(final: Any) -> bool:
    return bool(
        np.all(final.endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(final.endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(final.endpoint.temperature_F > -459.67)
        and np.all(final.endpoint.pressure_psia > 0.0)
        and np.all(np.diff(final.endpoint.pressure_psia) > 0.0)
        and np.all(final.endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(final.endpoint.vapor_flow_lbmolph > 0.0)
        and final.endpoint.condenser_duty_BTUph < 0.0
        and np.min(final.properties.free_volume.free_vapor_volume_ft3) > 0.0
    )


def execute() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    started = time.perf_counter()
    root_path = _rooted(SOURCE_ROOT).resolve()
    small_path = _rooted(SOURCE_SMALL_STEP).resolve()
    small_matrix_path = _rooted(SOURCE_SMALL_MATRIX).resolve()
    root = json.loads(root_path.read_text(encoding="utf-8"))
    small = json.loads(small_path.read_text(encoding="utf-8"))
    if (
        not root.get("pass_gate")
        or not small.get("pass_gate")
        or small.get("decision")
        != "authorize_separately_bounded_short_fixed_product_trajectory"
        or small.get("component_specific_logic") is not False
    ):
        raise RuntimeError("trajectory requires the accepted root and small feed step")

    problem = starting_state.build_problem(density_model=root["density_model"])
    endpoint = root["endpoint"]
    liquid_inventory = np.asarray(endpoint["liquid_component_inventory_lbmol"], dtype=float)
    vapor_inventory = np.asarray(endpoint["vapor_component_inventory_lbmol"], dtype=float)
    phase_transfer = np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float)
    temperature = np.asarray(endpoint["temperature_F"], dtype=float)
    pressure = np.asarray(endpoint["pressure_psia"], dtype=float)
    liquid_flow = np.asarray(endpoint["hydraulic_liquid_flow_lbmolph"], dtype=float)
    vapor_flow = np.asarray(endpoint["vapor_flow_lbmolph"], dtype=float)
    condenser_duty = float(endpoint["condenser_duty_BTUph"])

    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    history_audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    initial_properties = evaluate_vapor_holdup_trial_properties(
        problem["geometry"],
        liquid_inventory,
        vapor_inventory,
        temperature,
        pressure,
        provider,
        history_audit,
        state_id="water_methanol:feed_pulse:energy_history",
        evaluation_kind="residual",
    )

    stationary_numerical = problem["numerical"]
    numerical = VaporHoldupImplicitNumericalSpec(
        timestep_sec=TIMESTEP_SEC,
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
        product_flow_parameters=("D_stationary_root", "B_stationary_root"),
    )
    dimension = len(contract.rows)
    lower, upper = vapor_holdup_implicit_step_coordinate_bounds(contract)
    pattern = vapor_holdup_structural_pattern(contract)
    coordinate_scale = _coordinate_scale(small_matrix_path, dimension)
    base_inputs = replace(
        problem["balance_inputs"],
        distillate_lbmolph=float(endpoint["distillate_lbmolph"]),
        bottoms_lbmolph=float(endpoint["bottoms_lbmolph"]),
        condenser_duty_BTUph=condenser_duty,
    )
    base_feed = np.asarray(base_inputs.feed_component_lbmolph, dtype=float)
    base_feed_enthalpy = float(base_inputs.feed_enthalpy_BTUph)
    phase_scale_floor = np.asarray(
        stationary_numerical.component_residual_scale_lbmolph, dtype=float
    )
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=vapor_inventory,
        phase_transfer_lbmolph=phase_transfer,
        phase_transfer_scale_lbmolph=np.maximum(np.abs(phase_transfer), phase_scale_floor),
        temperature_F=temperature,
        pressure_psia=pressure,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        vapor_flow_lbmolph=vapor_flow,
        condenser_duty_BTUph=condenser_duty,
        total_stored_energy_BTU=initial_properties.total_stored_energy_BTU,
    )

    multipliers = [PULSE_MULTIPLIER] * PULSE_STEPS + [1.0] * RESTORED_STEPS
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    step_reports: list[dict[str, Any]] = []
    coordinates_history: list[np.ndarray] = []
    liquid_history = [liquid_inventory.copy()]
    vapor_history = [vapor_inventory.copy()]
    temperature_history = [temperature.copy()]
    pressure_history = [pressure.copy()]
    duty_history = [condenser_duty]
    previous_guess = np.zeros(dimension, dtype=float)
    final = None
    final_objective = None
    final_solution = None

    for step_index, multiplier in enumerate(multipliers, start=1):
        inputs = replace(
            base_inputs,
            feed_component_lbmolph=base_feed * multiplier,
            feed_enthalpy_BTUph=base_feed_enthalpy * multiplier,
        )
        step_reference = reference
        step_inputs = inputs
        step_number = step_index
        counters = {"function": 0, "jacobian": 0}

        def objective(candidate: np.ndarray, state_id: str = "solver") -> np.ndarray:
            counters["function"] += 1
            return evaluate_vapor_holdup_implicit_residual(
                contract,
                problem["geometry"],
                step_reference,
                step_inputs,
                problem["spec"].hydraulic_geometry,
                numerical,
                provider,
                audit,
                candidate,
                state_id=(
                    f"water_methanol:feed_pulse:step={step_number}:"
                    f"{state_id}:{counters['function']}"
                ),
                evaluation_kind="jacobian",
            ).scaled

        def jacobian(candidate: np.ndarray) -> np.ndarray:
            counters["jacobian"] += 1
            matrix, _groups = colored_central_difference_jacobian(
                objective,
                candidate,
                pattern=pattern,
                step=DIFFERENCE_STEP,
                state_id=(
                    f"water_methanol:feed_pulse:step={step_number}:"
                    f"solver_jacobian:{counters['jacobian']}"
                ),
            )
            return matrix

        guess = previous_guess if multiplier == PULSE_MULTIPLIER else np.zeros(dimension)
        solution = least_squares(
            objective,
            guess,
            jac=jacobian,
            bounds=(lower, upper),
            method="trf",
            x_scale=coordinate_scale,
            ftol=1.0e-11,
            xtol=1.0e-11,
            gtol=1.0e-11,
            max_nfev=MAX_NFEV,
            verbose=0,
        )
        final = evaluate_vapor_holdup_implicit_residual(
            contract,
            problem["geometry"],
            reference,
            inputs,
            problem["spec"].hydraulic_geometry,
            numerical,
            provider,
            audit,
            solution.x,
            state_id=f"water_methanol:feed_pulse:step={step_index}:final",
            evaluation_kind="residual",
        )
        actual_component = np.sum(
            final.endpoint.liquid_component_inventory_lbmol
            + final.endpoint.vapor_component_inventory_lbmol
            - reference.liquid_component_inventory_lbmol
            - reference.vapor_component_inventory_lbmol,
            axis=0,
        )
        expected_component = (
            final.transport.external_component_rate_lbmolph * TIMESTEP_SEC / 3600.0
        )
        component_error = float(np.max(np.abs(actual_component - expected_component)))
        actual_energy = float(
            np.sum(final.properties.total_stored_energy_BTU - reference.total_stored_energy_BTU)
        )
        expected_energy = float(
            final.transport.external_energy_rate_BTUph * TIMESTEP_SEC / 3600.0
        )
        energy_error_absolute = abs(actual_energy - expected_energy)
        energy_error_relative = energy_error_absolute / max(
            abs(actual_energy), abs(expected_energy), 1.0
        )
        residual_norm = float(np.max(np.abs(final.scaled)))
        movement = float(np.max(np.abs(solution.x)))
        minimum_bound_distance = float(
            np.min(np.minimum(solution.x - lower, upper - solution.x))
        )
        fugacity_maximum = float(np.max(np.abs(final.fugacity_residual)))
        eos_maximum = float(np.max(np.abs(final.properties.eos_relative_residual)))
        restored_input_exact = bool(
            multiplier != 1.0
            or (
                np.array_equal(np.asarray(inputs.feed_component_lbmolph), base_feed)
                and float(inputs.feed_enthalpy_BTUph) == base_feed_enthalpy
            )
        )
        direction_pass = bool(
            multiplier == 1.0
            or (
                float(np.sum(actual_component)) > 0.0
                and float(np.sum(expected_component)) > 0.0
            )
        )
        step_gates = {
            "solver": bool(solution.success),
            "residual": residual_norm < RESIDUAL_LIMIT,
            "bounds": minimum_bound_distance > 1.0e-6,
            "component_identity": component_error < COMPONENT_IDENTITY_LIMIT_LBMOL,
            "energy_identity": bool(
                energy_error_relative < ENERGY_IDENTITY_RELATIVE_LIMIT
                or energy_error_absolute < ENERGY_IDENTITY_ABSOLUTE_LIMIT_BTU
            ),
            "physical": _physical(final),
            "fugacity": fugacity_maximum < 1.0e-8,
            "eos": eos_maximum < 1.0e-10,
            "direction": direction_pass,
            "restored_input": restored_input_exact,
        }
        step_gates = {name: bool(value) for name, value in step_gates.items()}
        step_pass = all(step_gates.values())
        step_reports.append(
            {
                "step_index": step_index,
                "time_sec": step_index * TIMESTEP_SEC,
                "feed_multiplier": multiplier,
                "disturbance_active": multiplier != 1.0,
                "solver_success": bool(solution.success),
                "nfev": int(solution.nfev),
                "njev": int(solution.njev or 0),
                "observed": counters,
                "scaled_residual_inf_norm": residual_norm,
                "maximum_coordinate_movement": movement,
                "minimum_bound_distance": minimum_bound_distance,
                "total_component_change_lbmol": float(np.sum(actual_component)),
                "expected_total_component_change_lbmol": float(
                    np.sum(expected_component)
                ),
                "component_identity_error_lbmol": component_error,
                "actual_energy_change_BTU": actual_energy,
                "expected_energy_change_BTU": expected_energy,
                "energy_identity_absolute_error_BTU": energy_error_absolute,
                "energy_identity_relative_error": energy_error_relative,
                "maximum_fugacity_residual": fugacity_maximum,
                "maximum_eos_relative_residual": eos_maximum,
                "gates": step_gates,
                "pass_gate": step_pass,
            }
        )
        print(
            json.dumps(
                {
                    "step": step_index,
                    "time_sec": step_index * TIMESTEP_SEC,
                    "feed_multiplier": multiplier,
                    "pass_gate": step_pass,
                    "residual": residual_norm,
                }
            ),
            flush=True,
        )
        coordinates_history.append(solution.x.copy())
        liquid_history.append(final.endpoint.liquid_component_inventory_lbmol.copy())
        vapor_history.append(final.endpoint.vapor_component_inventory_lbmol.copy())
        temperature_history.append(final.endpoint.temperature_F.copy())
        pressure_history.append(final.endpoint.pressure_psia.copy())
        duty_history.append(float(final.endpoint.condenser_duty_BTUph))
        final_objective = objective
        final_solution = solution
        if not step_pass:
            break
        reference = VaporHoldupImplicitReference(
            liquid_component_inventory_lbmol=(
                final.endpoint.liquid_component_inventory_lbmol.copy()
            ),
            vapor_component_inventory_lbmol=(
                final.endpoint.vapor_component_inventory_lbmol.copy()
            ),
            phase_transfer_lbmolph=final.endpoint.phase_transfer_lbmolph.copy(),
            phase_transfer_scale_lbmolph=np.maximum(
                np.abs(final.endpoint.phase_transfer_lbmolph), phase_scale_floor
            ),
            temperature_F=final.endpoint.temperature_F.copy(),
            pressure_psia=final.endpoint.pressure_psia.copy(),
            hydraulic_liquid_flow_lbmolph=(
                final.endpoint.hydraulic_liquid_flow_lbmolph.copy()
            ),
            vapor_flow_lbmolph=final.endpoint.vapor_flow_lbmolph.copy(),
            condenser_duty_BTUph=float(final.endpoint.condenser_duty_BTUph),
            total_stored_energy_BTU=final.properties.total_stored_energy_BTU.copy(),
        )
        previous_guess = solution.x.copy()

    endpoint_matrices: list[np.ndarray] = []
    endpoint_steps: list[dict[str, Any]] = []
    if len(step_reports) == len(multipliers) and all(
        item["pass_gate"] for item in step_reports
    ):
        assert final_objective is not None and final_solution is not None
        for difference_step in ENDPOINT_STEPS:
            matrix, groups = colored_central_difference_jacobian(
                final_objective,
                final_solution.x,
                pattern=pattern,
                step=difference_step,
                state_id=f"water_methanol:feed_pulse:restored_endpoint:h={difference_step:.1e}",
            )
            rank, condition, singular = _rank_condition(matrix)
            endpoint_matrices.append(matrix)
            endpoint_steps.append(
                {
                    "step": difference_step,
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
    if len(endpoint_matrices) == 2:
        spectrum_change = _relative_change(
            np.asarray(endpoint_steps[0]["singular_values"]),
            np.asarray(endpoint_steps[1]["singular_values"]),
        )
        matrix_change = _relative_change(endpoint_matrices[0], endpoint_matrices[1])
        jacobian_pass = bool(
            all(item["rank"] == dimension for item in endpoint_steps)
            and all(item["condition"] < CONDITION_LIMIT for item in endpoint_steps)
            and all(item["zero_rows"] == 0 for item in endpoint_steps)
            and all(item["zero_columns"] == 0 for item in endpoint_steps)
            and spectrum_change < SPECTRUM_CHANGE_LIMIT
            and matrix_change < MATRIX_CHANGE_LIMIT
        )
    else:
        spectrum_change = float("inf")
        matrix_change = float("inf")
        jacobian_pass = False

    history_report = compact_provider_report(history_audit.report())
    provider_report = compact_provider_report(audit.report())
    provider_pass = bool(
        history_report["pass"]
        and provider_report["pass"]
        and not history_audit.fallback_attempted
        and not audit.fallback_attempted
    )
    wall = time.perf_counter() - started
    trajectory_complete = len(step_reports) == len(multipliers)
    all_steps_pass = trajectory_complete and all(item["pass_gate"] for item in step_reports)
    feed_restored = bool(
        trajectory_complete
        and step_reports[-1]["feed_multiplier"] == 1.0
        and not step_reports[-1]["disturbance_active"]
        and step_reports[-1]["gates"]["restored_input"]
    )
    gates = {
        "all_steps": all_steps_pass,
        "feed_restored": feed_restored,
        "endpoint_jacobian": jacobian_pass,
        "provider": provider_pass,
        "calls": history_audit.record_count + audit.record_count < CALL_LIMIT,
        "wall": wall < WALL_LIMIT_SEC,
    }
    gates = {name: bool(value) for name, value in gates.items()}
    passed = all(gates.values())
    report = {
        "schema_id": "core-v3-water-methanol-vtpr-feed-pulse-trajectory-v1",
        "classification": (
            "fixed_product_feed_pulse_restored_passed"
            if passed
            else "fixed_product_feed_pulse_or_restoration_failed"
        ),
        "decision": (
            "feed_pulse_experiment_complete_nominal_feed_restored"
            if passed
            else "stop_with_nominal_feed_commanded_and_correct_trajectory"
        ),
        "sources": {
            str(SOURCE_ROOT).replace("\\", "/"): _sha256(root_path),
            str(SOURCE_SMALL_STEP).replace("\\", "/"): _sha256(small_path),
            str(SOURCE_SMALL_MATRIX).replace("\\", "/"): _sha256(small_matrix_path),
        },
        "component_specific_logic": False,
        "handoff_mode": "fixed_terminal_products",
        "condenser_duty_mode": "solved_column_variable",
        "timestep_sec": TIMESTEP_SEC,
        "pulse": {
            "feed_multiplier": PULSE_MULTIPLIER,
            "step_count": PULSE_STEPS,
            "duration_sec": PULSE_STEPS * TIMESTEP_SEC,
            "composition_changed": False,
            "specific_enthalpy_changed": False,
        },
        "restoration": {
            "feed_multiplier": 1.0,
            "step_count": RESTORED_STEPS,
            "restored_before_final_step": feed_restored,
            "disturbance_active_at_end": not feed_restored,
        },
        "step_count_requested": len(multipliers),
        "step_count_completed": len(step_reports),
        "steps": step_reports,
        "endpoint_jacobian": {
            "steps": endpoint_steps,
            "spectrum_relative_change": spectrum_change,
            "matrix_relative_change": matrix_change,
            "pass_gate": jacobian_pass,
        },
        "provider": {
            "history": history_report,
            "trajectory": provider_report,
            "total_calls": history_audit.record_count + audit.record_count,
            "pass_gate": provider_pass,
        },
        "gates": gates,
        "wall_clock_sec": wall,
        "retry_attempted": False,
        "adaptive_timestep_used": False,
        "feed_disturbance_removed": feed_restored,
        "pass_gate": passed,
    }
    empty_matrix = np.empty((0, dimension), dtype=float)
    evidence = {
        "time_sec": np.arange(len(liquid_history), dtype=float) * TIMESTEP_SEC,
        "feed_multiplier": np.asarray([1.0, *multipliers[: len(step_reports)]], dtype=float),
        "coordinates": (
            np.stack(coordinates_history) if coordinates_history else empty_matrix
        ),
        "liquid_component_inventory_lbmol": np.stack(liquid_history),
        "vapor_component_inventory_lbmol": np.stack(vapor_history),
        "temperature_F": np.stack(temperature_history),
        "pressure_psia": np.stack(pressure_history),
        "condenser_duty_BTUph": np.asarray(duty_history, dtype=float),
        "jacobian_h1": (
            endpoint_matrices[0] if endpoint_matrices else np.empty((0, 0))
        ),
        "jacobian_h2": (
            endpoint_matrices[1] if len(endpoint_matrices) > 1 else np.empty((0, 0))
        ),
        "structural_pattern": pattern,
    }
    return report, evidence


def _markdown(report: dict[str, Any]) -> str:
    final_step = report["steps"][-1] if report["steps"] else {}
    return "\n".join(
        (
            "# Core V3 water-methanol feed-pulse trajectory",
            "",
            f"- Result: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Pulse: `{report['pulse']['feed_multiplier']}x` feed for `{report['pulse']['duration_sec']} s`",
            f"- Steps completed: `{report['step_count_completed']} / {report['step_count_requested']}`",
            f"- Final feed multiplier: `{report['restoration']['feed_multiplier']}`",
            f"- Disturbance active at end: `{report['restoration']['disturbance_active_at_end']}`",
            f"- Final residual maximum: `{final_step.get('scaled_residual_inf_norm', float('nan')):.6e}`",
            f"- Final Jacobian pass: `{report['endpoint_jacobian']['pass_gate']}`",
            f"- Provider pass: `{report['provider']['pass_gate']}`",
            "- Retry or adaptive timestep: `False`",
            "",
            "The feed-rate pulse was removed before the final step. The saved final input is the original nominal feed; the column state retains the physical response accumulated during the pulse.",
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
                "feed_disturbance_removed": report["feed_disturbance_removed"],
                "decision": report["decision"],
            },
            indent=2,
        ),
        flush=True,
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
