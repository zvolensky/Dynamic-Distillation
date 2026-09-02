#!/usr/bin/env python
"""Run the ChemSep-specification-aware water-methanol stationary root."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any

import numpy as np
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_water_methanol_starting_state as starting_state  # noqa: E402
import run_core_v3_water_methanol_prescribed_pressure_root as prescribed  # noqa: E402
from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    colored_central_difference_jacobian,
)
from dynamic_distillation.core_v3.prescribed_pressure_stationary_v1 import (  # noqa: E402
    apply_prescribed_pressure_targets,
    prescribed_pressure_structural_pattern,
)
from dynamic_distillation.core_v3.projected_enthalpy_correction_provider_v1 import (  # noqa: E402
    ProjectedEnthalpyCorrectionProviderV1,
)
from dynamic_distillation.core_v3.projected_fugacity_correction_provider_v1 import (  # noqa: E402
    ProjectedFugacityCorrectionProviderV1,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit  # noqa: E402
from dynamic_distillation.core_v3.stationary_specification_ownership_v1 import (  # noqa: E402
    fixed_bottoms_solved_reboiler_pattern,
    fixed_bottoms_solved_reboiler_trial,
    specification_aware_variable_names,
)
from dynamic_distillation.core_v3.total_reboiler_stationary_v1 import (  # noqa: E402
    apply_total_reboiler_boundary,
    total_reboiler_structural_pattern,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    evaluate_vapor_holdup_stationary_residual,
    stationary_structural_pattern,
)


DEFAULT_JSON = Path("logs/core_v3_water_methanol_specification_aware_root_20260901.json")
DEFAULT_DOC = Path("docs/core_v3_water_methanol_specification_aware_root_20260901.md")
DEFAULT_EVIDENCE = Path("logs/core_v3_water_methanol_specification_aware_root_20260901.npz")
CHEMSEP_LIQUID_ENTHALPY_BTU_LBMOL = np.asarray(
    (-101438.0, -102286.0, -103639.0, -105754.0, -108890.0,
     -112863.0, -116254.0, -117919.0, -119936.0, -119936.0),
    dtype=float,
)
CHEMSEP_VAPOR_ENTHALPY_BTU_LBMOL = np.asarray(
    (-101438.0, -86110.8, -86584.2, -87334.3, -88495.1,
     -90194.6, -92327.1, -94160.0, -99611.1, -102414.0),
    dtype=float,
)
CHEMSEP_FEED_ENTHALPY_BTU_LBMOL = -110923.0


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _normalized_rows(values: Any) -> np.ndarray:
    rows = np.asarray(values, dtype=float)
    if rows.ndim != 2 or np.any(~np.isfinite(rows)) or np.any(rows <= 0.0):
        raise ValueError("ChemSep composition profile must be finite and positive")
    return rows / np.sum(rows, axis=1, keepdims=True)


def _log_fugacity_residual(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: np.ndarray,
    vapor_y: np.ndarray,
) -> np.ndarray:
    phi_liquid = np.asarray(
        provider.phase_fugacity_coefficients(
            "liquid", temperature_F, pressure_psia, liquid_x
        ),
        dtype=float,
    )
    phi_vapor = np.asarray(
        provider.phase_fugacity_coefficients(
            "vapor", temperature_F, pressure_psia, vapor_y
        ),
        dtype=float,
    )
    return np.log(vapor_y * phi_vapor / (liquid_x * phi_liquid))


def _chemsep_profile_calibration(
    problem: dict[str, Any],
    *,
    pressure_psia: float,
    degree: int,
) -> tuple[ProjectedFugacityCorrectionProviderV1, dict[str, Any]]:
    if degree < 0:
        raise ValueError("correction degree must be non-negative")
    base = problem["provider"]
    source = problem["source"]
    liquid_x = _normalized_rows(source["liquid_mole_fraction"])
    reported_y = _normalized_rows(problem["column"].y0)
    temperature = np.asarray(source["temperature_F"], dtype=float)
    if reported_y.shape != liquid_x.shape or temperature.shape != (len(liquid_x),):
        raise ValueError("ChemSep liquid, vapor, and temperature profiles disagree")

    target_y = reported_y.copy()
    terminal_candidates = (len(reported_y) - 2, len(reported_y) - 1)
    candidate_error = []
    for candidate in terminal_candidates:
        residual = _log_fugacity_residual(
            base,
            temperature_F=float(temperature[-1]),
            pressure_psia=float(pressure_psia),
            liquid_x=liquid_x[-1],
            vapor_y=reported_y[candidate],
        )
        candidate_error.append(float(np.max(np.abs(residual))))
    selected_terminal_row = terminal_candidates[int(np.argmin(candidate_error))]
    target_y[-1] = reported_y[selected_terminal_row]

    residual_before = np.asarray(
        [
            _log_fugacity_residual(
                base,
                temperature_F=float(temperature[index]),
                pressure_psia=float(pressure_psia),
                liquid_x=liquid_x[index],
                vapor_y=target_y[index],
            )
            for index in range(len(liquid_x))
        ],
        dtype=float,
    )
    spans = np.ptp(liquid_x, axis=0)
    projection_index = int(np.argmax(spans))
    projection = np.zeros(liquid_x.shape[1], dtype=float)
    projection[projection_index] = 1.0
    coordinate = liquid_x @ projection
    lower = float(np.min(coordinate))
    upper = float(np.max(coordinate))
    normalized = 2.0 * (coordinate - lower) / (upper - lower) - 1.0
    unique_count = len(np.unique(np.round(normalized, decimals=12)))
    fitted_degree = min(int(degree), unique_count - 1)
    coefficients = np.asarray(
        [
            np.polynomial.chebyshev.chebfit(
                normalized, residual_before[:, component], fitted_degree
            )
            for component in range(liquid_x.shape[1])
        ],
        dtype=float,
    )
    provider = ProjectedFugacityCorrectionProviderV1(
        base_provider=base,
        projection=projection,
        projection_limits=(lower, upper),
        liquid_log_coefficients=coefficients,
        provider_identity="dwsim-chemsep-profile-calibrated",
    )
    residual_after = np.asarray(
        [
            _log_fugacity_residual(
                provider,
                temperature_F=float(temperature[index]),
                pressure_psia=float(pressure_psia),
                liquid_x=liquid_x[index],
                vapor_y=target_y[index],
            )
            for index in range(len(liquid_x))
        ],
        dtype=float,
    )
    return provider, {
        "enabled": True,
        "source": "ChemSep reported equilibrium profile",
        "equation": "component-wise liquid log-fugacity Chebyshev correction",
        "component_selection_rule": "largest reported liquid-composition span",
        "projection_component_index": projection_index,
        "projection": projection.tolist(),
        "projection_limits": [lower, upper],
        "requested_degree": int(degree),
        "fitted_degree": fitted_degree,
        "liquid_log_coefficients": coefficients.tolist(),
        "terminal_vapor_candidate_rows_1based": [value + 1 for value in terminal_candidates],
        "terminal_vapor_candidate_max_errors": candidate_error,
        "selected_terminal_vapor_row_1based": selected_terminal_row + 1,
        "maximum_abs_log_residual_before": float(np.max(np.abs(residual_before))),
        "rms_log_residual_before": float(np.sqrt(np.mean(residual_before**2))),
        "maximum_abs_log_residual_after": float(np.max(np.abs(residual_after))),
        "rms_log_residual_after": float(np.sqrt(np.mean(residual_after**2))),
        "use_limit": (
            "local ChemSep initialization/parity aid; dynamic extrapolation is not qualified"
        ),
    }


def _chemsep_enthalpy_calibration(
    problem: dict[str, Any],
    *,
    pressure_psia: float,
    degree: int,
) -> tuple[ProjectedEnthalpyCorrectionProviderV1, dict[str, Any]]:
    if degree < 0:
        raise ValueError("enthalpy correction degree must be non-negative")
    base = problem["provider"]
    source = problem["source"]
    liquid_x = _normalized_rows(source["liquid_mole_fraction"])
    vapor_y = _normalized_rows(problem["column"].y0)
    temperature = np.asarray(source["temperature_F"], dtype=float)
    feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
    feed_z = feed_component / np.sum(feed_component)
    if (
        liquid_x.shape != vapor_y.shape
        or temperature.shape != (len(liquid_x),)
        or CHEMSEP_LIQUID_ENTHALPY_BTU_LBMOL.shape != temperature.shape
        or CHEMSEP_VAPOR_ENTHALPY_BTU_LBMOL.shape != temperature.shape
    ):
        raise ValueError("ChemSep enthalpy and composition profiles disagree")

    spans = np.ptp(liquid_x, axis=0)
    projection_index = int(np.argmax(spans))
    projection = np.zeros(liquid_x.shape[1], dtype=float)
    projection[projection_index] = 1.0
    liquid_composition = np.vstack((liquid_x, feed_z))
    liquid_temperature = np.append(temperature, float(source["feed_temperature_F"]))
    liquid_target = np.append(
        CHEMSEP_LIQUID_ENTHALPY_BTU_LBMOL, CHEMSEP_FEED_ENTHALPY_BTU_LBMOL
    )
    # The first ChemSep vapor enthalpy is the total-condenser liquid product.
    # It is not a transported vapor state, so the vapor fit starts at stage 2.
    vapor_composition = vapor_y[1:]
    vapor_temperature = temperature[1:]
    vapor_target = CHEMSEP_VAPOR_ENTHALPY_BTU_LBMOL[1:]
    all_coordinate = np.concatenate(
        (liquid_composition @ projection, vapor_composition @ projection)
    )
    lower = float(np.min(all_coordinate))
    upper = float(np.max(all_coordinate))

    def normalized(composition: np.ndarray) -> np.ndarray:
        coordinate = composition @ projection
        return 2.0 * (coordinate - lower) / (upper - lower) - 1.0

    liquid_base = np.asarray(
        [
            base.phase_enthalpy_BTU_lbmol(
                "liquid",
                float(liquid_temperature[index]),
                float(pressure_psia),
                liquid_composition[index],
            )
            for index in range(len(liquid_composition))
        ],
        dtype=float,
    )
    vapor_base = np.asarray(
        [
            base.phase_enthalpy_BTU_lbmol(
                "vapor",
                float(vapor_temperature[index]),
                float(pressure_psia),
                vapor_composition[index],
            )
            for index in range(len(vapor_composition))
        ],
        dtype=float,
    )
    unique_count = min(
        len(np.unique(np.round(normalized(liquid_composition), decimals=12))),
        len(np.unique(np.round(normalized(vapor_composition), decimals=12))),
    )
    fitted_degree = min(int(degree), unique_count - 1)
    liquid_coefficients = np.polynomial.chebyshev.chebfit(
        normalized(liquid_composition), liquid_target - liquid_base, fitted_degree
    )
    vapor_coefficients = np.polynomial.chebyshev.chebfit(
        normalized(vapor_composition), vapor_target - vapor_base, fitted_degree
    )
    provider = ProjectedEnthalpyCorrectionProviderV1(
        base_provider=base,
        projection=projection,
        projection_limits=(lower, upper),
        liquid_correction_coefficients_BTU_lbmol=(liquid_coefficients,),
        vapor_correction_coefficients_BTU_lbmol=(vapor_coefficients,),
        provider_identity="dwsim-chemsep-profile-enthalpy-calibrated",
    )
    liquid_after = np.asarray(
        [
            provider.phase_enthalpy_BTU_lbmol(
                "liquid",
                float(liquid_temperature[index]),
                float(pressure_psia),
                liquid_composition[index],
            )
            for index in range(len(liquid_composition))
        ]
    )
    vapor_after = np.asarray(
        [
            provider.phase_enthalpy_BTU_lbmol(
                "vapor",
                float(vapor_temperature[index]),
                float(pressure_psia),
                vapor_composition[index],
            )
            for index in range(len(vapor_composition))
        ]
    )
    liquid_error = liquid_after - liquid_target
    vapor_error = vapor_after - vapor_target
    return provider, {
        "enabled": True,
        "source": "ChemSep reported stage and feed enthalpy profile",
        "equation": "phase-specific projected Chebyshev enthalpy correction",
        "projection_component_index": projection_index,
        "projection": projection.tolist(),
        "projection_limits": [lower, upper],
        "requested_degree": int(degree),
        "fitted_degree": fitted_degree,
        "liquid_correction_coefficients_BTU_lbmol": liquid_coefficients.tolist(),
        "vapor_correction_coefficients_BTU_lbmol": vapor_coefficients.tolist(),
        "maximum_abs_liquid_fit_error_BTU_lbmol": float(
            np.max(np.abs(liquid_error))
        ),
        "rms_liquid_fit_error_BTU_lbmol": float(
            np.sqrt(np.mean(liquid_error**2))
        ),
        "maximum_abs_vapor_fit_error_BTU_lbmol": float(
            np.max(np.abs(vapor_error))
        ),
        "rms_vapor_fit_error_BTU_lbmol": float(
            np.sqrt(np.mean(vapor_error**2))
        ),
        "use_limit": (
            "local ChemSep initialization/parity aid; dynamic extrapolation is not qualified"
        ),
    }


def execute(
    *,
    pressure_mode: str = "template_profile",
    chemsep_pressure_psia: float = 14.6959,
    chemsep_profile_calibration: bool = False,
    correction_degree: int = 4,
    reboiler_type: str = "partial",
    chemsep_enthalpy_calibration: bool = False,
    enthalpy_correction_degree: int = 4,
    initial_coordinates: Path | None = None,
    hydraulic_design_bottom_pressure_psia: float | None = None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    problem = starting_state.build_problem(
        density_model="VTPR",
        property_package="unifac",
    )
    source = problem["source"]
    contract = problem["contract"]
    dimension = len(contract.variables)
    if pressure_mode == "template_profile":
        target_pressure = np.asarray(source["pressure_psia"], dtype=float)
        pressure_ownership = "fixed_workbook_parameter"
    elif pressure_mode == "chemsep_constant":
        if not np.isfinite(chemsep_pressure_psia) or chemsep_pressure_psia <= 0.0:
            raise ValueError("ChemSep constant pressure must be positive and finite")
        target_pressure = np.full(
            len(source["pressure_psia"]), float(chemsep_pressure_psia), dtype=float
        )
        pressure_ownership = "fixed_original_chemsep_parameter"
    elif pressure_mode == "hydraulic_free":
        target_pressure = None
        pressure_ownership = "solved_by_tray_hydraulics_with_top_pressure_anchor"
    else:
        raise ValueError(f"unknown pressure mode {pressure_mode!r}")
    calibration: dict[str, Any] = {"enabled": False}
    if chemsep_profile_calibration:
        provider, calibration = _chemsep_profile_calibration(
            problem,
            pressure_psia=float(chemsep_pressure_psia),
            degree=int(correction_degree),
        )
        problem["provider"] = provider
        problem["provider_audit_kwargs"]["provider_identity"] = (
            "dwsim_chemsep_profile_calibrated"
        )
    enthalpy_calibration: dict[str, Any] = {"enabled": False}
    if chemsep_enthalpy_calibration:
        provider, enthalpy_calibration = _chemsep_enthalpy_calibration(
            problem,
            pressure_psia=float(chemsep_pressure_psia),
            degree=int(enthalpy_correction_degree),
        )
        problem["provider"] = provider
        problem["provider_audit_kwargs"]["provider_identity"] = (
            "dwsim_chemsep_profile_enthalpy_calibrated"
        )
        feed_component = np.asarray(source["feed_component_lbmolph"], dtype=float)
        feed_total = float(np.sum(feed_component))
        feed_enthalpy = provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            float(source["feed_temperature_F"]),
            float(chemsep_pressure_psia),
            feed_component / feed_total,
        )
        problem["balance_inputs"] = replace(
            problem["balance_inputs"],
            feed_enthalpy_BTUph=feed_total * float(feed_enthalpy),
        )
    fixed_bottoms = float(source["bottoms_reference_lbmolph"])
    pressure_pattern = (
        stationary_structural_pattern(contract)
        if target_pressure is None
        else prescribed_pressure_structural_pattern(contract)
    )
    if reboiler_type == "total":
        pressure_pattern = total_reboiler_structural_pattern(
            contract, base_pattern=pressure_pattern
        )
    elif reboiler_type != "partial":
        raise ValueError(f"unknown reboiler type {reboiler_type!r}")
    pattern = fixed_bottoms_solved_reboiler_pattern(
        contract, base_pattern=pressure_pattern
    )
    lower, upper = prescribed.free_root._bounds(
        contract,
        problem["reference"],
        policy="phase_total",
    )
    provider = problem["provider"]
    if hasattr(provider, "set_exact_state_memoization"):
        provider.set_exact_state_memoization(True, clear=True)
    audit = ProviderCallAudit(**problem["provider_audit_kwargs"])
    function_calls = 0
    jacobian_calls = 0

    def evaluate(candidate: np.ndarray, label: str) -> tuple[Any, Any]:
        nonlocal function_calls
        function_calls += 1
        trial = fixed_bottoms_solved_reboiler_trial(
            contract,
            problem["reference"],
            problem["balance_inputs"],
            candidate,
            fixed_bottoms_lbmolph=fixed_bottoms,
        )
        base = evaluate_vapor_holdup_stationary_residual(
            contract,
            problem["geometry"],
            problem["reference"],
            trial.balance_inputs,
            problem["spec"].hydraulic_geometry,
            problem["numerical"],
            provider,
            audit,
            trial.base_coordinates,
            state_id=f"water_methanol:specification_aware:{label}:{function_calls}",
            evaluation_kind="residual" if label == "final" else "jacobian",
        )
        if reboiler_type == "total":
            base = apply_total_reboiler_boundary(
                contract,
                base,
                temperature_scale_F=problem["numerical"].temperature_coordinate_scale_F,
            )
        if target_pressure is None:
            return base, trial
        return (
            apply_prescribed_pressure_targets(
                contract,
                base,
                target_pressure,
                residual_scale_psia=problem["numerical"].pressure_residual_scale_psia,
            ),
            trial,
        )

    def objective(candidate: np.ndarray, label: str = "solver") -> np.ndarray:
        pressure, _trial = evaluate(candidate, label)
        return pressure.scaled

    def jacobian(candidate: np.ndarray) -> np.ndarray:
        nonlocal jacobian_calls
        jacobian_calls += 1
        matrix, _groups = colored_central_difference_jacobian(
            lambda point, state_id: objective(point, state_id),
            candidate,
            pattern=pattern,
            step=float(prescribed.SETTINGS["difference_step"]),
            state_id=f"water_methanol:specification_aware:jacobian:{jacobian_calls}",
        )
        return matrix

    started = time.perf_counter()
    starting_coordinates = np.zeros(dimension, dtype=float)
    initial_coordinates_path = None
    if initial_coordinates is not None:
        initial_coordinates_path = _rooted(initial_coordinates).resolve()
        with np.load(initial_coordinates_path, allow_pickle=False) as saved:
            if "coordinates" not in saved:
                raise ValueError("initial-coordinate evidence has no coordinates array")
            starting_coordinates = np.asarray(saved["coordinates"], dtype=float)
        if starting_coordinates.shape != (dimension,) or np.any(
            ~np.isfinite(starting_coordinates)
        ):
            raise ValueError("initial-coordinate evidence has the wrong shape")
        if np.any(starting_coordinates <= lower) or np.any(starting_coordinates >= upper):
            raise ValueError("initial coordinates lie outside the active bounds")
    pressure_drop_calibration: dict[str, Any] = {"enabled": False}
    if hydraulic_design_bottom_pressure_psia is not None:
        if target_pressure is not None or initial_coordinates_path is None:
            raise ValueError(
                "dry-tray calibration requires hydraulic-free mode and restart coordinates"
            )
        design_bottom = float(hydraulic_design_bottom_pressure_psia)
        design_top = float(problem["numerical"].top_pressure_anchor_psia)
        if not np.isfinite(design_bottom) or design_bottom <= design_top:
            raise ValueError("design bottom pressure must exceed the top-pressure anchor")
        calibration_evaluation, _calibration_trial = evaluate(
            starting_coordinates, "dry_tray_coefficient_calibration"
        )
        calibration_base = getattr(
            calibration_evaluation, "base", calibration_evaluation
        )
        current_coefficient = float(
            problem["numerical"].dry_tray_pressure_drop_coefficient
        )
        liquid_drop = float(
            np.sum(calibration_base.pressure_drop.liquid_head_drop_psia)
        )
        dry_drop = float(np.sum(calibration_base.pressure_drop.dry_tray_drop_psia))
        unit_dry_drop = dry_drop / current_coefficient
        design_total_drop = design_bottom - design_top
        inferred_coefficient = (design_total_drop - liquid_drop) / unit_dry_drop
        if (
            not np.isfinite(unit_dry_drop)
            or unit_dry_drop <= 0.0
            or not np.isfinite(inferred_coefficient)
            or inferred_coefficient <= 0.0
        ):
            raise RuntimeError(
                "the design pressure profile cannot produce a positive dry-tray coefficient"
            )
        problem["numerical"] = replace(
            problem["numerical"],
            dry_tray_pressure_drop_coefficient=float(inferred_coefficient),
        )
        pressure_drop_calibration = {
            "enabled": True,
            "method": "infer one column-wide dry-tray coefficient from design endpoint pressure",
            "design_top_pressure_psia": design_top,
            "design_bottom_pressure_psia": design_bottom,
            "design_total_pressure_drop_psia": design_total_drop,
            "seed_liquid_head_drop_psia": liquid_drop,
            "seed_dry_drop_at_original_coefficient_psia": dry_drop,
            "original_dry_tray_coefficient": current_coefficient,
            "inferred_dry_tray_coefficient": float(inferred_coefficient),
        }
    solution = least_squares(
        lambda point: objective(point),
        starting_coordinates,
        jac=jacobian,
        bounds=(lower, upper),
        method=str(prescribed.SETTINGS["method"]),
        x_scale="jac",
        ftol=float(prescribed.SETTINGS["ftol"]),
        xtol=float(prescribed.SETTINGS["xtol"]),
        gtol=float(prescribed.SETTINGS["gtol"]),
        max_nfev=int(prescribed.SETTINGS["max_nfev"]),
        verbose=0,
    )
    final, final_trial = evaluate(solution.x, "final")
    endpoint_matrix = jacobian(solution.x)
    rank, condition, singular = prescribed._rank_condition(endpoint_matrix)
    wall = float(time.perf_counter() - started)

    base = getattr(final, "base", final)
    endpoint = base.endpoint
    liquid_x = endpoint.liquid_component_inventory_lbmol / np.sum(
        endpoint.liquid_component_inventory_lbmol, axis=1, keepdims=True
    )
    component_max = float(
        max(
            np.max(np.abs(base.balances.liquid_component_residual_lbmolph)),
            np.max(np.abs(base.balances.vapor_component_residual_lbmolph)),
        )
    )
    energy_max = float(np.max(np.abs(base.balances.energy_residual_BTUph)))
    pressure_target_max = (
        0.0
        if target_pressure is None
        else float(np.max(np.abs(final.pressure_target_residual_psia)))
    )
    fugacity_max = float(np.max(np.abs(base.fugacity_residual)))
    eos_max = float(np.max(np.abs(base.properties.eos_relative_residual)))
    terminal_max = float(np.max(np.abs(base.terminal_inventory_residual_lbmol)))
    residual_max = float(np.max(np.abs(final.scaled)))
    bound_distance = float(np.min(np.minimum(solution.x - lower, upper - solution.x)))
    levels = prescribed._terminal_levels(
        endpoint, base.properties, problem["geometry"]
    )
    provider_report = prescribed.free_root.compact_provider_report(audit.report())
    physical_pass = bool(
        np.all(endpoint.liquid_component_inventory_lbmol > 0.0)
        and np.all(endpoint.vapor_component_inventory_lbmol > 0.0)
        and np.all(endpoint.hydraulic_liquid_flow_lbmolph > 0.0)
        and np.all(endpoint.vapor_flow_lbmolph > 0.0)
        and np.all(base.properties.free_volume.free_vapor_volume_ft3 > 0.0)
        and endpoint.condenser_duty_BTUph < 0.0
        and final_trial.reboiler_duty_BTUph > 0.0
        and endpoint.distillate_lbmolph > 0.0
        and np.isclose(endpoint.bottoms_lbmolph, fixed_bottoms, rtol=0.0, atol=1.0e-9)
    )
    passed = bool(
        solution.success
        and residual_max < prescribed.LIMITS["scaled_residual_inf_norm"]
        and component_max < prescribed.LIMITS["component_balance_lbmolph"]
        and energy_max < prescribed.LIMITS["energy_balance_BTUph"]
        and pressure_target_max < prescribed.LIMITS["pressure_target_psia"]
        and fugacity_max < prescribed.LIMITS["fugacity_residual"]
        and eos_max < prescribed.LIMITS["relative_eos_residual"]
        and terminal_max < prescribed.LIMITS["terminal_inventory_lbmol"]
        and rank == dimension
        and condition < prescribed.LIMITS["jacobian_condition"]
        and bound_distance > prescribed.LIMITS["minimum_bound_distance"]
        and physical_pass
        and provider_report["pass"]
        and not provider_report["fallback_attempted"]
        and wall < prescribed.LIMITS["wall_clock_sec"]
    )
    product = {
        "distillate": {
            "flow_lbmolph": float(endpoint.distillate_lbmolph),
            "temperature_F": float(endpoint.temperature_F[0]),
            "pressure_psia": float(endpoint.pressure_psia[0]),
            "liquid_mole_fraction": [float(value) for value in liquid_x[0]],
            "molar_enthalpy_BTU_lbmol": float(base.properties.liquid_enthalpy_BTU_lbmol[0]),
            "molar_density_lbmol_ft3": float(base.properties.liquid_density_lbmol_ft3[0]),
        },
        "bottoms": {
            "flow_lbmolph": float(endpoint.bottoms_lbmolph),
            "temperature_F": float(endpoint.temperature_F[-1]),
            "pressure_psia": float(endpoint.pressure_psia[-1]),
            "liquid_mole_fraction": [float(value) for value in liquid_x[-1]],
            "molar_enthalpy_BTU_lbmol": float(base.properties.liquid_enthalpy_BTU_lbmol[-1]),
            "molar_density_lbmol_ft3": float(base.properties.liquid_density_lbmol_ft3[-1]),
        },
    }
    reflux = float(problem["spec"].reflux_lbmolph)
    reflux_ratio = reflux / float(endpoint.distillate_lbmolph)
    workbook_path = problem["workbook"]
    report = {
        "schema_id": "core-v3-water-methanol-specification-aware-root-v1",
        "classification": "stationary_root_accepted" if passed else "stationary_root_rejected",
        "mode": (
            "hydraulic_pressure_fixed_bottoms_solved_reboiler_duty"
            if target_pressure is None
            else "prescribed_pressure_fixed_bottoms_solved_reboiler_duty"
        ),
        "pressure_mode": pressure_mode,
        "reboiler_type": reboiler_type,
        "workbook": str(workbook_path),
        "workbook_sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        "bulk_provider": (
            "dwsim_unifac_with_chemsep_profile_calibration"
            if chemsep_profile_calibration or chemsep_enthalpy_calibration
            else "dwsim_unifac"
        ),
        "liquid_density_provider": "clapeyron_vtpr",
        "fugacity_calibration": calibration,
        "enthalpy_calibration": enthalpy_calibration,
        "pressure_hydraulics": {
            "dry_tray_pressure_drop_coefficient": float(
                problem["numerical"].dry_tray_pressure_drop_coefficient
            ),
            "coefficient_calibration": pressure_drop_calibration,
            "final_total_pressure_drop_psia": float(
                endpoint.pressure_psia[-1] - endpoint.pressure_psia[0]
            ),
            "final_liquid_head_drop_psia": [
                float(value) for value in base.pressure_drop.liquid_head_drop_psia
            ],
            "final_dry_tray_drop_psia": [
                float(value) for value in base.pressure_drop.dry_tray_drop_psia
            ],
        },
        "specification_ownership": {
            "pressure_profile": pressure_ownership,
            "pressure_target_psia": (
                None
                if target_pressure is None
                else [float(value) for value in target_pressure]
            ),
            "reflux_lbmolph": reflux,
            "bottoms_lbmolph": fixed_bottoms,
            "terminal_liquid_inventories": "fixed_targets",
            "distillate_lbmolph": "solved",
            "condenser_duty_BTUph": "solved",
            "reboiler_duty_BTUph": "solved",
            "reboiler_phase_boundary": (
                "equal_liquid_vapor_composition_no_separation"
                if reboiler_type == "total"
                else "full_phase_equilibrium"
            ),
            "reflux_ratio": reflux_ratio,
            "variable_names": list(specification_aware_variable_names(contract)),
        },
        "solver": {
            "success": bool(solution.success),
            "status": int(solution.status),
            "message": str(solution.message),
            "nfev": int(solution.nfev),
            "njev": int(solution.njev or 0),
            "function_calls_observed": function_calls,
            "jacobian_calls_observed": jacobian_calls,
            "wall_clock_sec": wall,
            "initial_coordinates": (
                None
                if initial_coordinates_path is None
                else str(initial_coordinates_path)
            ),
        },
        "stationary_equation_score": residual_max,
        "raw_maxima": {
            "component_balance_lbmolph": component_max,
            "energy_balance_BTUph": energy_max,
            "pressure_target_psia": pressure_target_max,
            "free_pressure_equation_mismatch_psia": float(
                np.max(np.abs(base.pressure_drop.residual_psia))
            ),
            "fugacity": fugacity_max,
            "relative_eos": eos_max,
            "terminal_inventory_lbmol": terminal_max,
        },
        "jacobian": {
            "rank": rank,
            "dimension": dimension,
            "condition": condition,
            "singular_values": [float(value) for value in singular],
        },
        "duties": {
            "condenser_BTUph": float(endpoint.condenser_duty_BTUph),
            "reboiler_BTUph": float(final_trial.reboiler_duty_BTUph),
        },
        "products": product,
        "terminal_levels": {
            "distillate_drum_fraction": levels[0],
            "bottom_sump_fraction": levels[1],
        },
        "chemsep_comparison": {
            "distillate_flow_difference_lbmolph": float(
                endpoint.distillate_lbmolph - source["distillate_reference_lbmolph"]
            ),
            "bottoms_flow_difference_lbmolph": float(
                endpoint.bottoms_lbmolph - source["bottoms_reference_lbmolph"]
            ),
            "reflux_ratio_difference": float(reflux_ratio - 2.0),
            "condenser_duty_difference_BTUph": float(
                endpoint.condenser_duty_BTUph - source["condenser_duty_BTUph"]
            ),
            "reboiler_duty_difference_BTUph": float(
                final_trial.reboiler_duty_BTUph - source["reboiler_duty_BTUph"]
            ),
            "top_temperature_difference_F": float(
                endpoint.temperature_F[0] - source["temperature_F"][0]
            ),
            "bottom_temperature_difference_F": float(
                endpoint.temperature_F[-1] - source["temperature_F"][-1]
            ),
            "top_liquid_mole_fraction_difference": (
                liquid_x[0] - np.asarray(source["liquid_mole_fraction"])[0]
            ).tolist(),
            "bottom_liquid_mole_fraction_difference": (
                liquid_x[-1] - np.asarray(source["liquid_mole_fraction"])[-1]
            ).tolist(),
        },
        "minimum_bound_distance": bound_distance,
        "physical_pass": physical_pass,
        "provider": provider_report,
        "tray_profiles": prescribed._profile(
            problem,
            final if hasattr(final, "base") else SimpleNamespace(base=final),
        ),
        "pass_gate": passed,
        "decision": (
            "specification_ownership_reconciled"
            if passed
            else "stop_specification_aware_nonlinear_work"
        ),
    }
    evidence = {
        "coordinates": solution.x,
        "raw_residual": final.raw,
        "scaled_residual": final.scaled,
        "structural_pattern": pattern,
        "endpoint_jacobian": endpoint_matrix,
    }
    return report, evidence


def render_markdown(report: dict[str, Any]) -> str:
    duties = report["duties"]
    products = report["products"]
    levels = report["terminal_levels"]
    comparison = report["chemsep_comparison"]
    ownership = report["specification_ownership"]
    lines = [
        "# Core V3 water-methanol specification-aware stationary root",
        "",
        f"- Result: `{report['classification']}`",
        f"- Equation score: `{report['stationary_equation_score']:.6e}`",
        f"- Jacobian rank/condition: `{report['jacobian']['rank']}/{report['jacobian']['dimension']}` / `{report['jacobian']['condition']:.6e}`",
        f"- Wall time: `{report['solver']['wall_clock_sec']:.3f} s`",
        f"- Fixed bottoms: `{ownership['bottoms_lbmolph']:.6f} lbmol/h`",
        f"- Solved reflux ratio: `{ownership['reflux_ratio']:.9f}`",
        "",
        "## Final operating summary",
        "",
        f"- Qc: `{duties['condenser_BTUph']:.6f} BTU/h`",
        f"- Qr: `{duties['reboiler_BTUph']:.6f} BTU/h`",
        f"- Distillate: `{products['distillate']['flow_lbmolph']:.6f} lbmol/h`, `T={products['distillate']['temperature_F']:.6f} F`, `P={products['distillate']['pressure_psia']:.6f} psia`, `x={products['distillate']['liquid_mole_fraction']}`",
        f"- Bottoms: `{products['bottoms']['flow_lbmolph']:.6f} lbmol/h`, `T={products['bottoms']['temperature_F']:.6f} F`, `P={products['bottoms']['pressure_psia']:.6f} psia`, `x={products['bottoms']['liquid_mole_fraction']}`",
        f"- Distillate drum level: `{100.0 * levels['distillate_drum_fraction']:.6f}%`",
        f"- Bottom sump level: `{100.0 * levels['bottom_sump_fraction']:.6f}%`",
        f"- Stationary equation score: `{report['stationary_equation_score']:.6e}`",
        "",
        "## Difference from ChemSep",
        "",
        f"- D/B flow difference: `{comparison['distillate_flow_difference_lbmolph']:+.6f}` / `{comparison['bottoms_flow_difference_lbmolph']:+.6f} lbmol/h`",
        f"- Reflux-ratio difference: `{comparison['reflux_ratio_difference']:+.9f}`",
        f"- Qc/Qr difference: `{comparison['condenser_duty_difference_BTUph']:+.6f}` / `{comparison['reboiler_duty_difference_BTUph']:+.6f} BTU/h`",
        f"- Top/bottom temperature difference: `{comparison['top_temperature_difference_F']:+.6f}` / `{comparison['bottom_temperature_difference_F']:+.6f} F`",
        "",
        "## Tray profiles",
        "",
        "| Stage | Volume | T (F) | P (psia) | x1 | x2 | y1 | y2 | L (lbmol/h) | V (lbmol/h) |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["tray_profiles"]:
        lines.append(
            f"| {row['stage']} | {row['volume']} | {row['temperature_F']:.6f} | "
            f"{row['pressure_psia']:.6f} | {row['liquid_mole_fraction'][0]:.9f} | "
            f"{row['liquid_mole_fraction'][1]:.9f} | {row['vapor_mole_fraction'][0]:.9f} | "
            f"{row['vapor_mole_fraction'][1]:.9f} | {row['liquid_flow_lbmolph']:.6f} | "
            f"{row['vapor_flow_lbmolph']:.6f} |"
        )
    lines.append("")
    return "\n".join(lines)


def print_summary(report: dict[str, Any]) -> None:
    duties = report["duties"]
    products = report["products"]
    levels = report["terminal_levels"]
    print(f"Qc={duties['condenser_BTUph']:.6f} BTU/h")
    print(f"Qr={duties['reboiler_BTUph']:.6f} BTU/h")
    for name in ("distillate", "bottoms"):
        row = products[name]
        print(
            f"{name}: F={row['flow_lbmolph']:.6f} lbmol/h, "
            f"T={row['temperature_F']:.6f} F, P={row['pressure_psia']:.6f} psia, "
            f"x={row['liquid_mole_fraction']}"
        )
    print(
        f"levels: top={100.0 * levels['distillate_drum_fraction']:.6f}%, "
        f"bottom={100.0 * levels['bottom_sump_fraction']:.6f}%"
    )
    print(f"stationary_equation_score={report['stationary_equation_score']:.6e}")
    print("tray_profiles:")
    for row in report["tray_profiles"]:
        print(
            f"stage={row['stage']:02d} T={row['temperature_F']:.6f} "
            f"P={row['pressure_psia']:.6f} x={row['liquid_mole_fraction']} "
            f"y={row['vapor_mole_fraction']} L={row['liquid_flow_lbmolph']:.6f} "
            f"V={row['vapor_flow_lbmolph']:.6f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument(
        "--pressure-mode",
        choices=("template_profile", "chemsep_constant", "hydraulic_free"),
        default="template_profile",
    )
    parser.add_argument("--chemsep-pressure-psia", type=float, default=14.6959)
    parser.add_argument("--chemsep-profile-calibration", action="store_true")
    parser.add_argument("--correction-degree", type=int, default=4)
    parser.add_argument("--chemsep-enthalpy-calibration", action="store_true")
    parser.add_argument("--enthalpy-correction-degree", type=int, default=4)
    parser.add_argument(
        "--reboiler-type", choices=("partial", "total"), default="partial"
    )
    parser.add_argument("--initial-coordinates", type=Path)
    parser.add_argument("--hydraulic-design-bottom-pressure-psia", type=float)
    args = parser.parse_args()
    report, evidence = execute(
        pressure_mode=args.pressure_mode,
        chemsep_pressure_psia=args.chemsep_pressure_psia,
        chemsep_profile_calibration=args.chemsep_profile_calibration,
        correction_degree=args.correction_degree,
        reboiler_type=args.reboiler_type,
        chemsep_enthalpy_calibration=args.chemsep_enthalpy_calibration,
        enthalpy_correction_degree=args.enthalpy_correction_degree,
        initial_coordinates=args.initial_coordinates,
        hydraulic_design_bottom_pressure_psia=(
            args.hydraulic_design_bottom_pressure_psia
        ),
    )
    json_path = _rooted(args.json)
    doc_path = _rooted(args.doc)
    evidence_path = _rooted(args.evidence)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(render_markdown(report), encoding="utf-8")
    np.savez_compressed(evidence_path, **evidence)
    print_summary(report)
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
