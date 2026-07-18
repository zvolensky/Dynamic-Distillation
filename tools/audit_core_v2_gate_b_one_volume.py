#!/usr/bin/env python
"""Run the DD-080 one-volume live-property and energy closure gate."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import (
    build_column_spec_from_case,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    BTU_PER_PSI_FT3,
    OneVolumeBoundary,
    OneVolumeConservedState,
    OneVolumeGeometry,
    OneVolumeIntegrationOptions,
    OneVolumeSpec,
    audit_one_volume_jacobian,
    integrate_one_volume,
    normalize_composition,
    solve_one_volume_closure,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


ROUND_TRIP_TOLERANCES = {
    "temperature_F": 1.0e-6,
    "liquid_mole_fraction": 1.0e-12,
    "vapor_mole_fraction": 1.0e-8,
    "energy_residual": 1.0e-9,
    "equilibrium_residual": 1.0e-8,
}
JACOBIAN_CONDITION_LIMIT = 1.0e8
DYNAMIC_ALGEBRAIC_TOLERANCE = 1.0e-8
DYNAMIC_COMPONENT_CONSERVATION_TOLERANCE = 1.0e-9
DYNAMIC_ENERGY_CONSERVATION_TOLERANCE = 1.0e-8
DYNAMIC_INTEGRATOR_AGREEMENT_TOLERANCE = 1.0e-6


def _float_list(values) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape((-1,))]


def _role_selected_volume(column) -> int:
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("mini8 Gate B input requires a role-identified feed volume")
    stage0 = int(feed.stage_1based) - 1
    if stage0 <= 0 or stage0 >= int(column.n_stages) - 1:
        raise ValueError("Gate B representative volume must be an interior tray")
    return stage0


def _build_problem(workbook_path: Path, property_package: str):
    column = build_column_spec_from_case(load_case_from_excel(str(workbook_path)))
    stage0 = _role_selected_volume(column)
    if column.M_L_lbmol is None:
        raise ValueError("Gate B input requires liquid holdup")
    geometry = column.geometry
    if geometry is None:
        raise ValueError("Gate B input requires tray geometry")
    provider = ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=property_package,
        silence_backend_console=True,
    )
    x0 = normalize_composition(column.x0[stage0, :])
    y_seed = normalize_composition(column.y0[stage0, :])
    liquid_moles = float(column.M_L_lbmol[stage0])
    temperature_F = float(column.T_f[stage0])
    pressure_psia = float(column.P_psia[stage0])
    enthalpy = provider.phase_enthalpy_BTU_lbmol(
        "liquid",
        temperature_F,
        pressure_psia,
        x0,
    )
    density = provider.liquid_density_lbmol_ft3(
        temperature_F,
        pressure_psia,
        x0,
    )
    if density is None or float(density) <= 0.0:
        raise RuntimeError("canonical DWSIM liquid density is unavailable")
    internal_energy = float(enthalpy) - (
        pressure_psia * (1.0 / float(density)) * BTU_PER_PSI_FT3
    )
    component_mw = provider.component_mw_lbm_per_lbmol()
    if component_mw is None:
        raise RuntimeError(
            "canonical DWSIM component molecular weights are unavailable"
        )
    hydraulic_c = geometry.hydraulic_c_factor_per_stage
    c_factor = 1.0 if hydraulic_c is None else float(hydraulic_c[stage0])
    spec = OneVolumeSpec(
        component_names=tuple(column.components_excel),
        pressure_psia=pressure_psia,
        temperature_reference_F=temperature_F,
        temperature_scale_F=100.0,
        energy_scale_BTU=max(
            abs(liquid_moles * internal_energy),
            liquid_moles * 1.0e4,
            1.0,
        ),
        geometry=OneVolumeGeometry(
            active_area_ft2=float(geometry.active_area_ft2_per_stage[stage0]),
            tray_spacing_ft=float(geometry.tray_spacing_ft_per_stage[stage0]),
            weir_height_in=float(geometry.weir_height_in_per_stage[stage0]),
            weir_length_ft=float(geometry.weir_length_ft_per_stage[stage0]),
            hydraulic_c_factor=c_factor,
        ),
        component_mw_lbm_per_lbmol=np.asarray(
            component_mw,
            dtype=float,
        ),
    )
    state = OneVolumeConservedState(
        component_inventory_lbmol=liquid_moles * x0,
        internal_energy_BTU=liquid_moles * internal_energy,
    )
    return column, stage0, provider, spec, state, y_seed


def _perturbation_states(
    canonical: OneVolumeConservedState,
) -> dict[str, OneVolumeConservedState]:
    inventory = np.asarray(
        canonical.component_inventory_lbmol,
        dtype=float,
    )
    total = float(np.sum(inventory))
    specific_energy = float(canonical.internal_energy_BTU) / total

    transferred = inventory.copy()
    delta = 0.002 * total
    transferred[0] -= delta
    transferred[1] += delta

    combined_inventory = 1.005 * inventory
    combined_delta = 0.001 * float(np.sum(combined_inventory))
    combined_inventory[0] -= combined_delta
    combined_inventory[1] += combined_delta
    combined_specific_energy = specific_energy + 0.002 * abs(specific_energy)
    return {
        "nominal_canonical": canonical,
        "inventory_plus_1_percent": OneVolumeConservedState(
            1.01 * inventory,
            1.01 * float(canonical.internal_energy_BTU),
        ),
        "internal_energy_plus_0p5_percent": OneVolumeConservedState(
            inventory.copy(),
            float(canonical.internal_energy_BTU)
            + 0.005 * abs(float(canonical.internal_energy_BTU)),
        ),
        "propane_to_butane_transfer": OneVolumeConservedState(
            transferred,
            float(canonical.internal_energy_BTU),
        ),
        "combined_bounded": OneVolumeConservedState(
            combined_inventory,
            float(np.sum(combined_inventory)) * combined_specific_energy,
        ),
    }


def _closure_doc(closure) -> dict:
    return {
        "temperature_F": float(closure.temperature_F),
        "liquid_moles_lbmol": float(closure.liquid_moles_lbmol),
        "liquid_mole_fraction": _float_list(closure.liquid_mole_fraction),
        "vapor_mole_fraction": _float_list(closure.vapor_mole_fraction),
        "liquid_enthalpy_BTU_lbmol": float(closure.liquid_enthalpy_BTU_lbmol),
        "liquid_internal_energy_BTU_lbmol": float(
            closure.liquid_internal_energy_BTU_lbmol
        ),
        "liquid_density_lbmol_ft3": float(closure.liquid_density_lbmol_ft3),
        "mass_density_lbm_ft3": float(closure.mass_density_lbm_ft3),
        "mean_molecular_weight_lbm_lbmol": float(
            closure.mean_molecular_weight_lbm_lbmol
        ),
        "liquid_volume_ft3": float(closure.liquid_volume_ft3),
        "liquid_height_ft": float(closure.liquid_height_ft),
        "over_weir_head_ft": float(closure.over_weir_head_ft),
        "francis_flow_lbmolph": float(closure.francis_flow_lbmolph),
        "phase_fugacity_common_ratio": float(closure.phase_fugacity_common_ratio),
        "residual": _float_list(closure.residual),
        "residual_max_abs": float(np.max(np.abs(closure.residual))),
        "converged": bool(closure.converged),
        "iterations": int(closure.iterations),
        "active_bounds": bool(closure.active_bounds),
        "clipping_or_projection_used": bool(closure.clipping_or_projection_used),
    }


def _static_audit(spec, states, provider, y_seed):
    reports = {}
    canonical_closure = solve_one_volume_closure(
        spec,
        states["nominal_canonical"],
        provider,
        initial_temperature_F=float(spec.temperature_reference_F),
        initial_vapor_mole_fraction=y_seed,
    )
    guess_definitions = (
        (
            "source_near",
            float(spec.temperature_reference_F),
            canonical_closure.vapor_mole_fraction,
        ),
        (
            "hot_light",
            float(spec.temperature_reference_F) + 20.0,
            np.asarray([0.70, 0.25, 0.05]),
        ),
        (
            "cool_heavy",
            float(spec.temperature_reference_F) - 20.0,
            np.asarray([0.20, 0.60, 0.20]),
        ),
    )
    all_pass = True
    for name, state in states.items():
        roots = [
            solve_one_volume_closure(
                spec,
                state,
                provider,
                initial_temperature_F=temperature_guess,
                initial_vapor_mole_fraction=vapor_guess,
            )
            for _, temperature_guess, vapor_guess in guess_definitions
        ]
        reference = roots[0]
        jacobians = [
            audit_one_volume_jacobian(
                spec,
                state,
                provider,
                reference.scaled_unknown,
                step_factor=factor,
            )
            for factor in (1.0, 0.5)
        ]
        root_temperature_spread = max(
            abs(root.temperature_F - reference.temperature_F) for root in roots
        )
        root_vapor_spread = max(
            float(
                np.max(np.abs(root.vapor_mole_fraction - reference.vapor_mole_fraction))
            )
            for root in roots
        )
        geometry_valid = bool(
            reference.liquid_volume_ft3 > 0.0
            and reference.liquid_height_ft > 0.0
            and reference.liquid_height_ft < float(spec.geometry.tray_spacing_ft)
        )
        phase_valid = bool(
            np.all(reference.liquid_mole_fraction > 0.0)
            and np.all(reference.vapor_mole_fraction > 0.0)
            and abs(float(np.sum(reference.liquid_mole_fraction)) - 1.0) < 1.0e-12
            and abs(float(np.sum(reference.vapor_mole_fraction)) - 1.0) < 1.0e-12
            and np.isfinite(reference.phase_fugacity_common_ratio)
            and reference.phase_fugacity_common_ratio > 0.0
        )
        jacobian_pass = all(
            audit.rank == len(spec.component_names)
            and audit.condition < JACOBIAN_CONDITION_LIMIT
            and not audit.zero_rows
            and not audit.zero_columns
            for audit in jacobians
        )
        case_pass = bool(
            all(root.converged for root in roots)
            and all(
                np.max(np.abs(root.residual)) < ROUND_TRIP_TOLERANCES["energy_residual"]
                for root in roots
            )
            and root_temperature_spread < ROUND_TRIP_TOLERANCES["temperature_F"]
            and root_vapor_spread < ROUND_TRIP_TOLERANCES["vapor_mole_fraction"]
            and geometry_valid
            and phase_valid
            and jacobian_pass
            and all(
                not root.active_bounds and not root.clipping_or_projection_used
                for root in roots
            )
        )
        all_pass = all_pass and case_pass
        reports[name] = {
            "state": {
                "component_inventory_lbmol": _float_list(
                    state.component_inventory_lbmol
                ),
                "internal_energy_BTU": float(state.internal_energy_BTU),
            },
            "solution": _closure_doc(reference),
            "predefined_roots": {
                guess_name: _closure_doc(root)
                for (guess_name, _, _), root in zip(
                    guess_definitions,
                    roots,
                )
            },
            "root_temperature_spread_F": float(root_temperature_spread),
            "root_vapor_composition_spread": float(root_vapor_spread),
            "jacobians": {
                f"h_x_{audit.step_factor:g}": {
                    "rank": int(audit.rank),
                    "condition": float(audit.condition),
                    "zero_rows": list(audit.zero_rows),
                    "zero_columns": list(audit.zero_columns),
                    "matrix": np.asarray(
                        audit.matrix,
                        dtype=float,
                    ).tolist(),
                }
                for audit in jacobians
            },
            "geometry_valid": geometry_valid,
            "phase_valid": phase_valid,
            "pass_gate": case_pass,
        }
    canonical = reports["nominal_canonical"]["solution"]
    canonical_round_trip_pass = bool(
        abs(float(canonical["temperature_F"]) - float(spec.temperature_reference_F))
        < ROUND_TRIP_TOLERANCES["temperature_F"]
        and np.max(
            np.abs(
                np.asarray(canonical["liquid_mole_fraction"])
                - normalize_composition(
                    states["nominal_canonical"].component_inventory_lbmol
                )
            )
        )
        < ROUND_TRIP_TOLERANCES["liquid_mole_fraction"]
        and float(canonical["residual_max_abs"])
        < ROUND_TRIP_TOLERANCES["energy_residual"]
    )
    return (
        reports,
        canonical_closure,
        bool(all_pass and canonical_round_trip_pass),
        canonical_round_trip_pass,
    )


def _dynamic_cases(canonical_state, combined_state, canonical_closure):
    x = canonical_closure.liquid_mole_fraction
    composition_step = x.copy()
    composition_step[0] += 0.001
    composition_step[1] -= 0.001
    combined_inlet = x.copy()
    combined_inlet[0] -= 0.0005
    combined_inlet[1] += 0.0005
    flow = max(canonical_closure.francis_flow_lbmolph / 3600.0, 1.0e-6)
    enthalpy = canonical_closure.liquid_enthalpy_BTU_lbmol
    return {
        "nominal_no_disturbance": (
            canonical_state,
            OneVolumeBoundary(flow, x, enthalpy, 0.0),
        ),
        "inlet_composition_step": (
            canonical_state,
            OneVolumeBoundary(
                flow,
                composition_step,
                enthalpy,
                0.0,
            ),
        ),
        "inlet_enthalpy_step": (
            canonical_state,
            OneVolumeBoundary(flow, x, enthalpy + 25.0, 0.0),
        ),
        "bounded_combined": (
            combined_state,
            OneVolumeBoundary(
                flow,
                combined_inlet,
                enthalpy + 10.0,
                2.0,
            ),
        ),
    }


def _trajectory_scales(initial_state, spec):
    inventory = np.asarray(
        initial_state.component_inventory_lbmol,
        dtype=float,
    )
    return np.concatenate(
        (
            np.maximum(np.abs(inventory), 1.0),
            np.asarray([float(spec.energy_scale_BTU)]),
        )
    )


def _dynamic_audit(
    spec,
    states,
    provider,
    canonical_closure,
    horizon_sec,
    output_interval_sec,
):
    times = np.arange(
        0.0,
        float(horizon_sec) + 0.5 * float(output_interval_sec),
        float(output_interval_sec),
    )
    primary_options = OneVolumeIntegrationOptions(
        method="BDF",
        rtol=1.0e-7,
        atol=1.0e-9,
        max_step_sec=2.0,
    )
    refinement_options = OneVolumeIntegrationOptions(
        method="Radau",
        rtol=1.0e-7,
        atol=1.0e-9,
        max_step_sec=1.0,
    )
    reports = {}
    profile_rows = []
    all_pass = True
    cases = _dynamic_cases(
        states["nominal_canonical"],
        states["combined_bounded"],
        canonical_closure,
    )
    for name, (initial_state, boundary) in cases.items():
        primary = integrate_one_volume(
            spec=spec,
            initial_state=initial_state,
            provider=provider,
            boundary=boundary,
            initial_vapor_mole_fraction=(canonical_closure.vapor_mole_fraction),
            time_sec=times,
            options=primary_options,
        )
        refinement = integrate_one_volume(
            spec=spec,
            initial_state=initial_state,
            provider=provider,
            boundary=boundary,
            initial_vapor_mole_fraction=(canonical_closure.vapor_mole_fraction),
            time_sec=times,
            options=refinement_options,
        )
        scales = _trajectory_scales(initial_state, spec)
        conserved_agreement = float(
            np.max(
                np.abs(primary.conserved_state - refinement.conserved_state)
                / scales[None, :]
            )
        )
        derived_agreement = max(
            float(
                np.max(
                    np.abs(primary.temperature_F - refinement.temperature_F)
                    / float(spec.temperature_scale_F)
                )
            ),
            float(
                np.max(
                    np.abs(
                        primary.liquid_mole_fraction - refinement.liquid_mole_fraction
                    )
                )
            ),
            float(
                np.max(
                    np.abs(primary.vapor_mole_fraction - refinement.vapor_mole_fraction)
                )
            ),
        )
        integrator_agreement = max(
            conserved_agreement,
            derived_agreement,
        )
        initial_conserved = np.concatenate(
            (
                np.asarray(
                    initial_state.component_inventory_lbmol,
                    dtype=float,
                ),
                np.asarray(
                    [initial_state.internal_energy_BTU],
                    dtype=float,
                ),
            )
        )
        component_closure = (
            primary.conserved_state[:, :-1]
            - initial_conserved[:-1]
            - primary.cumulative_external_component_lbmol
        )
        energy_closure = (
            primary.conserved_state[:, -1]
            - initial_conserved[-1]
            - primary.cumulative_external_energy_BTU
        )
        component_conservation = float(
            np.max(np.abs(component_closure) / scales[:-1][None, :])
        )
        energy_conservation = float(
            np.max(np.abs(energy_closure)) / float(spec.energy_scale_BTU)
        )
        physical = bool(
            np.all(primary.conserved_state[:, :-1] > 0.0)
            and np.all(primary.liquid_mole_fraction > 0.0)
            and np.all(primary.vapor_mole_fraction > 0.0)
            and np.all(np.isfinite(primary.temperature_F))
        )
        nominal_stationary = True
        if name == "nominal_no_disturbance":
            nominal_stationary = bool(
                np.max(
                    np.abs(primary.conserved_state - primary.conserved_state[0])
                    / scales[None, :]
                )
                < 1.0e-10
            )
        case_pass = bool(
            primary.success
            and refinement.success
            and primary.algebraic_residual_max < DYNAMIC_ALGEBRAIC_TOLERANCE
            and refinement.algebraic_residual_max < DYNAMIC_ALGEBRAIC_TOLERANCE
            and component_conservation < DYNAMIC_COMPONENT_CONSERVATION_TOLERANCE
            and energy_conservation < DYNAMIC_ENERGY_CONSERVATION_TOLERANCE
            and integrator_agreement < DYNAMIC_INTEGRATOR_AGREEMENT_TOLERANCE
            and physical
            and nominal_stationary
            and not primary.clipping_or_projection_used
            and not refinement.clipping_or_projection_used
        )
        all_pass = all_pass and case_pass
        reports[name] = {
            "primary": {
                "method": primary.method,
                "nfev": int(primary.nfev),
                "algebraic_residual_max": float(primary.algebraic_residual_max),
            },
            "refinement": {
                "method": refinement.method,
                "nfev": int(refinement.nfev),
                "algebraic_residual_max": float(refinement.algebraic_residual_max),
            },
            "component_conservation_normalized": component_conservation,
            "energy_conservation_normalized": energy_conservation,
            "integrator_agreement_normalized": integrator_agreement,
            "physical": physical,
            "nominal_stationary": nominal_stationary,
            "pass_gate": case_pass,
        }
        for index, time_value in enumerate(primary.time_sec):
            row = {
                "case": name,
                "time_sec": float(time_value),
                "temperature_F": float(primary.temperature_F[index]),
                "internal_energy_BTU": float(primary.conserved_state[index, -1]),
            }
            for component_index, component in enumerate(spec.component_names):
                key = "".join(
                    character for character in component if character.isalnum()
                ).lower()
                row[f"N_{key}_lbmol"] = float(
                    primary.conserved_state[
                        index,
                        component_index,
                    ]
                )
                row[f"x_{key}"] = float(
                    primary.liquid_mole_fraction[
                        index,
                        component_index,
                    ]
                )
                row[f"y_{key}"] = float(
                    primary.vapor_mole_fraction[
                        index,
                        component_index,
                    ]
                )
            profile_rows.append(row)
    return (
        reports,
        profile_rows,
        bool(all_pass),
        asdict(primary_options),
        asdict(refinement_options),
    )


def _render_markdown(report: dict) -> str:
    lines = [
        "# DD-080 Gate B One-Volume Property and Energy Closure",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Source role: `{report['source_volume']['role']}`",
        f"- Source stage: `{report['source_volume']['source_stage_1based']}`",
        f"- Prescribed pressure: `{report['source_volume']['pressure_psia']:.6g} psia`",
        f"- Static gate: `{report['static_gate_pass']}`",
        f"- Dynamic gate: `{report['dynamic_gate_pass']}`",
        f"- Wall time: `{report['wall_clock_sec']:.3f} s`",
        "",
        "## Static Cases",
        "",
        "| Case | T (F) | max residual | Jacobian condition | Height (ft) | Francis L (lbmol/h) | Pass |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, case in report["static_cases"].items():
        solution = case["solution"]
        condition = max(
            jacobian["condition"] for jacobian in case["jacobians"].values()
        )
        lines.append(
            f"| {name} | {solution['temperature_F']:.6f} | "
            f"{solution['residual_max_abs']:.3e} | {condition:.3e} | "
            f"{solution['liquid_height_ft']:.6f} | "
            f"{solution['francis_flow_lbmolph']:.3f} | "
            f"{case['pass_gate']} |"
        )
    lines.extend(
        (
            "",
            "## Dynamic Cases",
            "",
            "| Case | Algebraic residual | Component closure | Energy closure | BDF/Radau | Pass |",
            "|---|---:|---:|---:|---:|---:|",
        )
    )
    for name, case in report["dynamic_cases"].items():
        lines.append(
            f"| {name} | "
            f"{case['primary']['algebraic_residual_max']:.3e} | "
            f"{case['component_conservation_normalized']:.3e} | "
            f"{case['energy_conservation_normalized']:.3e} | "
            f"{case['integrator_agreement_normalized']:.3e} | "
            f"{case['pass_gate']} |"
        )
    lines.extend(
        (
            "",
            "## Interpretation",
            "",
            "The conserved state is exactly `N_k, U`. Liquid amount and "
            "composition are reconstructed directly. Temperature and the "
            "two independent vapor-composition coordinates are solved from "
            "one live DWSIM liquid-energy equation and two independent "
            "relative-fugacity equations.",
            "",
            "The mini8 workbook supplies only the role-selected source "
            "state, geometry, components, and pressure. Canonical energy is "
            "rebuilt from live DWSIM PR enthalpy and density. Serialized "
            "enthalpy, fixed vessel-volume closure, vapor holdup, clipping, "
            "projection, phase relaxation, and legacy governing equations "
            "are not used.",
            "",
            "The reported common fugacity ratio is a saturation-proximity "
            "diagnostic. The algebraic equilibrium equations are the two "
            "independent relative-fugacity relations for a three-component "
            "normalized vapor composition.",
            "",
            "## Authorization",
            "",
            report["authorization"],
            "",
        )
    )
    return "\n".join(lines)


def run(
    *,
    workbook_path: Path,
    out_prefix: Path,
    property_package: str,
    horizon_sec: float,
    output_interval_sec: float,
) -> dict:
    started = time.perf_counter()
    (
        column,
        stage0,
        provider,
        spec,
        canonical_state,
        y_seed,
    ) = _build_problem(workbook_path, property_package)
    states = _perturbation_states(canonical_state)
    (
        static_cases,
        canonical_closure,
        static_pass,
        round_trip_pass,
    ) = _static_audit(spec, states, provider, y_seed)
    (
        dynamic_cases,
        profile_rows,
        dynamic_pass,
        primary_options,
        refinement_options,
    ) = _dynamic_audit(
        spec,
        states,
        provider,
        canonical_closure,
        horizon_sec,
        output_interval_sec,
    )
    passed = bool(static_pass and dynamic_pass)
    profile_path = out_prefix.with_name(f"{out_prefix.name}_profiles").with_suffix(
        ".csv"
    )
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    with profile_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(profile_rows[0]),
        )
        writer.writeheader()
        writer.writerows(profile_rows)
    try:
        workbook_label = str(workbook_path.resolve().relative_to(ROOT))
    except ValueError:
        workbook_label = str(workbook_path)
    try:
        profile_label = str(profile_path.resolve().relative_to(ROOT))
    except ValueError:
        profile_label = str(profile_path)
    report = {
        "schema_id": "dd080-core-v2-gate-b-one-volume-v1",
        "classification": ("dd080_gate_b_passed" if passed else "dd080_gate_b_failed"),
        "decision": (
            "authorize_gate_c_five_volume_prescribed_pressure_model"
            if passed
            else "stop_before_gate_c_and_correct_local_thermodynamic_core"
        ),
        "authorization": (
            "Gate B is complete. Gate C may begin as one five-volume "
            "prescribed-pressure Francis column. Gates D through G remain "
            "unauthorized."
            if passed
            else "Stop before a column solve. Correct the one-volume live "
            "property, energy, equilibrium, geometry, rank, or dynamic "
            "closure without loosening the declared tolerances."
        ),
        "source_workbook": workbook_label,
        "property_provider": "DWSIM",
        "property_package": property_package,
        "source_volume": {
            "role": "feed_tray",
            "source_stage_1based": int(stage0 + 1),
            "temperature_F": float(spec.temperature_reference_F),
            "pressure_psia": float(spec.pressure_psia),
            "component_names": list(spec.component_names),
        },
        "conserved_state": ["N_k", "U"],
        "algebraic_unknowns": ["T", "y_independent_1", "y_independent_2"],
        "round_trip_tolerances": ROUND_TRIP_TOLERANCES,
        "jacobian_condition_limit": JACOBIAN_CONDITION_LIMIT,
        "dynamic_tolerances": {
            "algebraic": DYNAMIC_ALGEBRAIC_TOLERANCE,
            "component_conservation": (DYNAMIC_COMPONENT_CONSERVATION_TOLERANCE),
            "energy_conservation": DYNAMIC_ENERGY_CONSERVATION_TOLERANCE,
            "integrator_agreement": (DYNAMIC_INTEGRATOR_AGREEMENT_TOLERANCE),
        },
        "geometry": asdict(spec.geometry),
        "canonical_state": {
            "component_inventory_lbmol": _float_list(
                canonical_state.component_inventory_lbmol
            ),
            "internal_energy_BTU": float(canonical_state.internal_energy_BTU),
            "live_solution": _closure_doc(canonical_closure),
        },
        "canonical_round_trip_pass": round_trip_pass,
        "static_cases": static_cases,
        "static_gate_pass": static_pass,
        "dynamic_horizon_sec": float(horizon_sec),
        "dynamic_output_interval_sec": float(output_interval_sec),
        "primary_integration": primary_options,
        "refinement_integration": refinement_options,
        "dynamic_cases": dynamic_cases,
        "dynamic_gate_pass": dynamic_pass,
        "profile_csv": profile_label,
        "live_property_evaluation_attempted": True,
        "nonlinear_algebraic_solve_attempted": True,
        "dynamic_integration_attempted": True,
        "serialized_enthalpy_used": False,
        "fixed_vessel_volume_equation_used": False,
        "vapor_holdup_used": False,
        "phase_relaxation_used": False,
        "legacy_governing_equation_used": False,
        "clipping_or_projection_used": False,
        "wall_clock_sec": float(time.perf_counter() - started),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    out_prefix.with_suffix(".md").write_text(
        _render_markdown(report),
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path("sandbox/mini8/input/" "distillation_column_template_8stage.xlsx"),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd080_core_v2_gate_b_one_volume_20260718"),
    )
    parser.add_argument("--property-package", default="pr")
    parser.add_argument("--horizon-sec", type=float, default=10.0)
    parser.add_argument(
        "--output-interval-sec",
        type=float,
        default=2.0,
    )
    return parser


if __name__ == "__main__":
    arguments = _parser().parse_args()
    result = run(
        workbook_path=arguments.workbook,
        out_prefix=arguments.out_prefix,
        property_package=arguments.property_package,
        horizon_sec=arguments.horizon_sec,
        output_interval_sec=arguments.output_interval_sec,
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["classification"] == "dd080_gate_b_passed" else 2)
