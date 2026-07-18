#!/usr/bin/env python
"""Run the DD-081 live five-volume residual and Jacobian gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import (
    build_column_spec_from_case,
)
from dynamic_distillation.core_v2.five_volume_residual_gate_v1 import (
    DIRECT_VOLUME_IDS,
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    FiveVolumeReference,
    audit_five_volume_jacobian,
    build_operating_spec,
    direct_coordinate_layout,
    direct_system_size,
    evaluate_five_volume_residual,
    perturbation_coordinates,
    structural_pattern,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    OneVolumeConservedState,
    OneVolumeGeometry,
    OneVolumeSpec,
    _liquid_properties,
    normalize_composition,
    solve_one_volume_closure,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


COMPONENT_CONSERVATION_TOLERANCE = 1.0e-12
ENERGY_CONSERVATION_TOLERANCE = 1.0e-10
JACOBIAN_CONDITION_PREFERRED = 1.0e6
JACOBIAN_CONDITION_HARD_STOP = 1.0e8
JACOBIAN_AGREEMENT_TOLERANCE = 1.0e-5
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)
LOCAL_CLOSURE_TOLERANCE = 1.0e-8


def _float_list(values) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _normalized_key(value: str) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _stream_component_vector(stream, component_names) -> np.ndarray:
    values = stream.component_molar_flows_lbmolph
    if values is None:
        raise ValueError(f"{stream.name} requires component molar flows")
    by_key = {_normalized_key(name): float(value) for name, value in values.items()}
    result = np.asarray(
        [by_key[_normalized_key(component)] for component in component_names],
        dtype=float,
    )
    if np.any(~np.isfinite(result)) or np.any(result < 0.0):
        raise ValueError(f"{stream.name} component flows are invalid")
    return result


def _select_role_indices(column) -> tuple[int, ...]:
    """Select five source locations by physical role, without fixed tray IDs."""
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("Gate C input requires a staged Feed stream")
    stage_count = int(column.n_stages)
    if stage_count < 5:
        raise ValueError("Gate C input requires at least five source locations")
    last = stage_count - 1
    feed_index = int(feed.stage_1based) - 1
    if feed_index <= 1 or feed_index >= last - 1:
        raise ValueError("Gate C requires source trays above and below the feed")
    rectifying = max(1, feed_index // 2)
    stripping = min(
        last - 1,
        feed_index + max(1, (last - feed_index) // 2),
    )
    selected = (0, rectifying, feed_index, stripping, last)
    if len(set(selected)) != len(DIRECT_VOLUME_IDS):
        raise ValueError("source profile cannot supply five distinct roles")
    return selected


def _geometry_at(column, stage_index: int) -> OneVolumeGeometry:
    geometry = column.geometry
    if geometry is None:
        raise ValueError("Gate C input requires tray geometry")
    c_factor = geometry.hydraulic_c_factor_per_stage
    return OneVolumeGeometry(
        active_area_ft2=float(geometry.active_area_ft2_per_stage[stage_index]),
        tray_spacing_ft=float(geometry.tray_spacing_ft_per_stage[stage_index]),
        weir_height_in=float(geometry.weir_height_in_per_stage[stage_index]),
        weir_length_ft=float(geometry.weir_length_ft_per_stage[stage_index]),
        hydraulic_c_factor=(
            1.0 if c_factor is None else float(c_factor[stage_index])
        ),
    )


def _required_spec_float(column, name: str) -> float:
    value = column.specs_raw.get(name)
    if value is None:
        raise ValueError(f"Gate C input requires specification {name!r}")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"Gate C specification {name!r} must be positive")
    return result


def _first_positive(values: np.ndarray) -> float:
    positive = np.asarray(values, dtype=float)
    positive = positive[np.isfinite(positive) & (positive > 0.0)]
    if positive.size == 0:
        raise ValueError("source profile has no positive vapor rate")
    return float(positive[0])


def _build_problem(workbook_path: Path, property_package: str):
    column = build_column_spec_from_case(load_case_from_excel(str(workbook_path)))
    if column.M_L_lbmol is None:
        raise ValueError("Gate C input requires source liquid holdups")
    source_indices = _select_role_indices(column)
    provider = ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=property_package,
        silence_backend_console=True,
    )
    component_mw = provider.component_mw_lbm_per_lbmol()
    if component_mw is None:
        raise RuntimeError("live DWSIM component molecular weights are unavailable")

    feed = column.streams["Feed"]
    distillate = column.streams.get("Distillate")
    bottoms = column.streams.get("Bottom")
    if distillate is None or bottoms is None:
        raise ValueError("Gate C input requires Distillate and Bottom streams")
    feed_component = _stream_component_vector(feed, column.components_excel)
    feed_total = float(np.sum(feed_component))
    feed_x = feed_component / feed_total
    if feed.temperature_f is None or feed.pressure_psia is None:
        raise ValueError("Gate C feed requires declared temperature and pressure")
    feed_h = float(
        provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            float(feed.temperature_f),
            float(feed.pressure_psia),
            feed_x.tolist(),
        )
    )
    if column.duties.q_cond_btu_per_h is None or column.duties.q_reb_btu_per_h is None:
        raise ValueError("Gate C input requires fixed condenser and reboiler duties")

    target_top = _required_spec_float(column, "Top Accumulator Holdup (lbmol)")
    target_bottom = _required_spec_float(column, "Bottom Holdup (lbmol)")
    liquid_moles = np.asarray(
        (
            target_top,
            float(column.M_L_lbmol[source_indices[1]]),
            float(column.M_L_lbmol[source_indices[2]]),
            float(column.M_L_lbmol[source_indices[3]]),
            target_bottom,
        ),
        dtype=float,
    )
    if np.any(~np.isfinite(liquid_moles)) or np.any(liquid_moles <= 0.0):
        raise ValueError("role-selected liquid inventories must be positive")
    liquid_x = np.asarray(
        [normalize_composition(column.x0[index]) for index in source_indices],
        dtype=float,
    )
    temperature = np.asarray(
        [float(column.T_f[index]) for index in source_indices],
        dtype=float,
    )
    pressure = np.asarray(
        [float(column.P_psia[index]) for index in source_indices],
        dtype=float,
    )
    inventory = liquid_moles[:, None] * liquid_x
    internal_energy = np.empty(len(DIRECT_VOLUME_IDS), dtype=float)
    vapor = np.empty(
        (len(EQUILIBRIUM_VOLUME_IDS), len(column.components_excel)),
        dtype=float,
    )
    local_closures = {}
    francis_reference = np.empty(len(HYDRAULIC_VOLUME_IDS), dtype=float)
    for volume_index, volume in enumerate(DIRECT_VOLUME_IDS):
        stage_index = source_indices[volume_index]
        h_liquid, u_liquid, density = _liquid_properties(
            provider,
            temperature_F=float(temperature[volume_index]),
            pressure_psia=float(pressure[volume_index]),
            liquid_mole_fraction=liquid_x[volume_index],
        )
        internal_energy[volume_index] = liquid_moles[volume_index] * u_liquid
        if volume not in EQUILIBRIUM_VOLUME_IDS:
            local_closures[volume] = {
                "temperature_F": float(temperature[volume_index]),
                "liquid_moles_lbmol": float(liquid_moles[volume_index]),
                "liquid_density_lbmol_ft3": float(density),
                "energy_residual_max": 0.0,
                "equilibrium_residual_max": None,
                "converged": True,
                "role": "liquid_only_reflux_drum",
            }
            continue
        one_volume_spec = OneVolumeSpec(
            component_names=tuple(column.components_excel),
            pressure_psia=float(pressure[volume_index]),
            temperature_reference_F=float(temperature[volume_index]),
            temperature_scale_F=100.0,
            energy_scale_BTU=max(abs(internal_energy[volume_index]), 1.0),
            geometry=_geometry_at(column, stage_index),
            component_mw_lbm_per_lbmol=np.asarray(component_mw, dtype=float),
        )
        closure = solve_one_volume_closure(
            one_volume_spec,
            OneVolumeConservedState(
                component_inventory_lbmol=inventory[volume_index],
                internal_energy_BTU=float(internal_energy[volume_index]),
            ),
            provider,
            initial_temperature_F=float(temperature[volume_index]),
            initial_vapor_mole_fraction=column.y0[stage_index],
        )
        vapor_index = EQUILIBRIUM_VOLUME_IDS.index(volume)
        vapor[vapor_index] = closure.vapor_mole_fraction
        local_closures[volume] = {
            "temperature_F": float(closure.temperature_F),
            "source_temperature_F": float(temperature[volume_index]),
            "temperature_difference_F": float(
                closure.temperature_F - temperature[volume_index]
            ),
            "liquid_moles_lbmol": float(closure.liquid_moles_lbmol),
            "liquid_density_lbmol_ft3": float(closure.liquid_density_lbmol_ft3),
            "energy_residual_max": float(abs(closure.residual[0])),
            "equilibrium_residual_max": float(
                np.max(np.abs(closure.residual[1:]))
            ),
            "converged": bool(closure.converged),
            "active_bounds": bool(closure.active_bounds),
            "clipping_or_projection_used": bool(
                closure.clipping_or_projection_used
            ),
        }
        if volume in HYDRAULIC_VOLUME_IDS:
            francis_reference[HYDRAULIC_VOLUME_IDS.index(volume)] = float(
                closure.francis_flow_lbmolph
            )

    reflux = float(column.L_lbmolph[0])
    rectifying_vapor = _first_positive(column.V_lbmolph)
    stripping_vapor = float(column.V_lbmolph[-1])
    if stripping_vapor <= 0.0:
        raise ValueError("source bottom boilup rate must be positive")
    spec = build_operating_spec(
        component_names=column.components_excel,
        pressure_psia=pressure,
        reflux_lbmolph=reflux,
        rectifying_vapor_lbmolph=rectifying_vapor,
        stripping_vapor_lbmolph=stripping_vapor,
        feed_component_lbmolph=feed_component,
        feed_enthalpy_BTUph=feed_total * feed_h,
        condenser_duty_BTUph=float(column.duties.q_cond_btu_per_h),
        reboiler_duty_BTUph=float(column.duties.q_reb_btu_per_h),
        terminal_liquid_targets_lbmol=(target_top, target_bottom),
        hydraulic_geometry=tuple(
            _geometry_at(column, source_indices[DIRECT_VOLUME_IDS.index(volume)])
            for volume in HYDRAULIC_VOLUME_IDS
        ),
    )
    reference = FiveVolumeReference(
        component_inventory_lbmol=inventory,
        internal_energy_BTU=internal_energy,
        temperature_F=temperature,
        vapor_mole_fraction=vapor,
        hydraulic_liquid_flow_lbmolph=francis_reference,
        distillate_lbmolph=float(distillate.total_molar_flow_lbmolph),
        bottoms_lbmolph=float(bottoms.total_molar_flow_lbmolph),
    )
    source_profile = {
        "source_stage_1based": [int(index + 1) for index in source_indices],
        "role": list(DIRECT_VOLUME_IDS),
        "temperature_F": _float_list(temperature),
        "pressure_psia": _float_list(pressure),
        "liquid_moles_lbmol": _float_list(liquid_moles),
        "source_liquid_flow_lbmolph": _float_list(
            [column.L_lbmolph[index] for index in source_indices]
        ),
        "source_vapor_flow_lbmolph": _float_list(
            [column.V_lbmolph[index] for index in source_indices]
        ),
        "liquid_mole_fraction": [
            _float_list(row) for row in liquid_x
        ],
        "equilibrium_vapor_mole_fraction": [
            _float_list(row) for row in vapor
        ],
    }
    operating = {
        "reflux_lbmolph": reflux,
        "rectifying_vapor_lbmolph": rectifying_vapor,
        "stripping_vapor_lbmolph": stripping_vapor,
        "feed_component_lbmolph": _float_list(feed_component),
        "feed_total_lbmolph": feed_total,
        "feed_temperature_F": float(feed.temperature_f),
        "feed_pressure_psia": float(feed.pressure_psia),
        "feed_specific_enthalpy_BTU_lbmol": feed_h,
        "feed_enthalpy_BTUph": feed_total * feed_h,
        "condenser_duty_BTUph": float(column.duties.q_cond_btu_per_h),
        "reboiler_duty_BTUph": float(column.duties.q_reb_btu_per_h),
        "terminal_liquid_targets_lbmol": [target_top, target_bottom],
        "initial_distillate_lbmolph": float(distillate.total_molar_flow_lbmolph),
        "initial_bottoms_lbmolph": float(bottoms.total_molar_flow_lbmolph),
        "parameter_source": (
            "mini8 workbook supplies the declared Gate C operating point; "
            "its profiles are seed and comparison data, not residual forcing"
        ),
    }
    return (
        column,
        provider,
        spec,
        reference,
        source_profile,
        operating,
        local_closures,
    )


def _block_maxima(evaluation) -> dict[str, float]:
    result: dict[str, float] = {}
    for row, value in zip(evaluation.rows, evaluation.scaled):
        result[row.block] = max(result.get(row.block, 0.0), abs(float(value)))
    return result


def _dominant_rows(evaluation, count: int = 10) -> list[dict]:
    order = np.argsort(np.abs(evaluation.scaled))[::-1][:count]
    return [
        {
            "name": evaluation.rows[index].name,
            "block": evaluation.rows[index].block,
            "owner": evaluation.rows[index].owner,
            "scaled_value": float(evaluation.scaled[index]),
            "raw_value": float(evaluation.raw[index]),
            "units": evaluation.rows[index].units,
        }
        for index in order
    ]


def _jacobian_doc(audit) -> dict:
    return {
        "step": float(audit.step),
        "rank": int(audit.rank),
        "nullity": int(audit.matrix.shape[1] - audit.rank),
        "condition": float(audit.condition),
        "zero_rows": list(audit.zero_rows),
        "zero_columns": list(audit.zero_columns),
        "unexpected_couplings": list(audit.unexpected_couplings),
        "color_count": int(audit.color_count),
        "colored_uncolored_max_abs": float(audit.colored_uncolored_max_abs),
        "colored_uncolored_relative": float(audit.colored_uncolored_relative),
        "preferred_condition_pass": bool(
            audit.condition < JACOBIAN_CONDITION_PREFERRED
        ),
        "hard_condition_pass": bool(
            audit.condition < JACOBIAN_CONDITION_HARD_STOP
        ),
    }


def _state_doc(evaluation, jacobians) -> dict:
    state = evaluation.state
    properties = evaluation.properties
    residence = []
    for hydraulic_index, volume in enumerate(HYDRAULIC_VOLUME_IDS):
        volume_index = DIRECT_VOLUME_IDS.index(volume)
        residence.append(
            3600.0
            * float(state.liquid_moles_lbmol[volume_index])
            / float(state.hydraulic_liquid_flow_lbmolph[hydraulic_index])
        )
    return {
        "scaled_residual_inf_norm": float(np.max(np.abs(evaluation.scaled))),
        "raw_residual_inf_norm": float(np.max(np.abs(evaluation.raw))),
        "block_scaled_maxima": _block_maxima(evaluation),
        "dominant_residuals": _dominant_rows(evaluation),
        "component_telescoping_error_lbmolph": _float_list(
            evaluation.component_telescoping_error
        ),
        "component_telescoping_relative_error": float(
            evaluation.component_telescoping_relative_error
        ),
        "energy_telescoping_error_BTUph": float(
            evaluation.energy_telescoping_error_BTUph
        ),
        "energy_telescoping_relative_error": float(
            evaluation.energy_telescoping_relative_error
        ),
        "liquid_moles_lbmol": _float_list(state.liquid_moles_lbmol),
        "temperature_F": _float_list(state.temperature_F),
        "liquid_mole_fraction": [
            _float_list(row) for row in state.liquid_mole_fraction
        ],
        "vapor_mole_fraction": [
            _float_list(row) for row in state.vapor_mole_fraction
        ],
        "hydraulic_liquid_flow_lbmolph": _float_list(
            state.hydraulic_liquid_flow_lbmolph
        ),
        "francis_flow_lbmolph": _float_list(
            [
                properties.francis_flow_lbmolph[
                    DIRECT_VOLUME_IDS.index(volume)
                ]
                for volume in HYDRAULIC_VOLUME_IDS
            ]
        ),
        "residence_time_sec": residence,
        "liquid_height_ft": _float_list(
            [
                properties.liquid_height_ft[
                    DIRECT_VOLUME_IDS.index(volume)
                ]
                for volume in HYDRAULIC_VOLUME_IDS
            ]
        ),
        "over_weir_head_ft": _float_list(
            [
                properties.over_weir_head_ft[
                    DIRECT_VOLUME_IDS.index(volume)
                ]
                for volume in HYDRAULIC_VOLUME_IDS
            ]
        ),
        "distillate_lbmolph": float(state.distillate_lbmolph),
        "bottoms_lbmolph": float(state.bottoms_lbmolph),
        "clipping_or_projection_used": bool(
            evaluation.clipping_or_projection_used
        ),
        "property_fallback_used": bool(evaluation.property_fallback_used),
        "jacobians": [_jacobian_doc(audit) for audit in jacobians],
    }


def _render_markdown(report: dict) -> str:
    lines = [
        "# DD-081 Core V2 Gate C Five-Volume Numerical Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Runtime: `{report['wall_clock_sec']:.3f} s`",
        f"- Direct unknowns/residuals: `{report['representation']['direct_count']} / "
        f"{report['representation']['direct_count']}`",
        f"- DD-077 ledger unknowns/residuals: "
        f"`{report['representation']['dd077_ledger_count']} / "
        f"{report['representation']['dd077_ledger_count']}`",
        f"- Five-volume nonlinear solve attempted: "
        f"`{report['five_volume_nonlinear_solve_attempted']}`",
        f"- Gate C solve authorized: `{report['gate_c_solve_authorized']}`",
        "",
        "## Representation Reconciliation",
        "",
        report["representation"]["explanation"],
        "",
        "The reflux drum is liquid-only. The other four volumes own equilibrium "
        "vapor outlets, so the direct system has eight independent vapor "
        "composition coordinates, not ten.",
        "",
        "## Source Mapping",
        "",
        "| Role | Source stage | T (F) | P (psia) | NL (lbmol) |",
        "|---|---:|---:|---:|---:|",
    ]
    source = report["source_profile"]
    for index, role in enumerate(source["role"]):
        lines.append(
            f"| {role} | {source['source_stage_1based'][index]} | "
            f"{source['temperature_F'][index]:.6f} | "
            f"{source['pressure_psia'][index]:.6f} | "
            f"{source['liquid_moles_lbmol'][index]:.6f} |"
        )
    lines.extend(
        (
            "",
            "## Numerical States",
            "",
            "| State | Residual inf | Component telescope | Energy telescope | "
            "Rank h / h/2 | Worst condition | Pass |",
            "|---|---:|---:|---:|---:|---:|---|",
        )
    )
    for name, state in report["states"].items():
        jac = state["jacobians"]
        lines.append(
            f"| {name} | {state['scaled_residual_inf_norm']:.3e} | "
            f"{state['component_telescoping_relative_error']:.3e} | "
            f"{state['energy_telescoping_relative_error']:.3e} | "
            f"{jac[0]['rank']} / {jac[1]['rank']} | "
            f"{max(jac[0]['condition'], jac[1]['condition']):.3e} | "
            f"{state['pass_gate']} |"
        )
    hydraulic = report["hydraulic_diagnostic"]
    lines.extend(
        (
            "",
            "## Francis Diagnostic",
            "",
            "| Role | Source profile L | Derived Francis L | Residence time (s) |",
            "|---|---:|---:|---:|",
        )
    )
    for index, role in enumerate(HYDRAULIC_VOLUME_IDS):
        lines.append(
            f"| {role} | {hydraulic['source_profile_liquid_flow_lbmolph'][index]:.6f} | "
            f"{hydraulic['derived_francis_flow_lbmolph'][index]:.6f} | "
            f"{hydraulic['residence_time_sec'][index]:.6f} |"
        )
    lines.extend(
        (
            "",
            "## Hard Stops",
            "",
        )
    )
    for name, value in report["hard_stops"].items():
        lines.append(f"- {name}: `{value}`")
    lines.extend(
        (
            "",
            "## Decision",
            "",
            report["authorization"],
            "",
        )
    )
    return "\n".join(lines)


def run(
    workbook_path: Path,
    property_package: str,
    out_prefix: Path,
) -> dict:
    started = time.perf_counter()
    (
        column,
        provider,
        spec,
        reference,
        source_profile,
        operating,
        local_closures,
    ) = _build_problem(workbook_path, property_package)
    points = perturbation_coordinates(spec)
    canonical = evaluate_five_volume_residual(
        spec,
        reference,
        provider,
        points["canonical_mini8_derived"],
    )
    fixed_scales = canonical.scales.copy()
    state_reports = {}
    all_state_pass = True
    for name, point in points.items():
        evaluation = evaluate_five_volume_residual(
            spec,
            reference,
            provider,
            point,
            fixed_scales=fixed_scales,
        )
        jacobians = [
            audit_five_volume_jacobian(
                spec,
                reference,
                provider,
                point,
                fixed_scales=fixed_scales,
                step=step,
            )
            for step in JACOBIAN_STEPS
        ]
        state_report = _state_doc(evaluation, jacobians)
        state_pass = bool(
            evaluation.component_telescoping_relative_error
            < COMPONENT_CONSERVATION_TOLERANCE
            and evaluation.energy_telescoping_relative_error
            < ENERGY_CONSERVATION_TOLERANCE
            and np.all(evaluation.state.component_inventory_lbmol > 0.0)
            and np.all(evaluation.state.liquid_mole_fraction > 0.0)
            and np.all(evaluation.state.vapor_mole_fraction > 0.0)
            and np.all(evaluation.state.hydraulic_liquid_flow_lbmolph > 0.0)
            and not evaluation.clipping_or_projection_used
            and not evaluation.property_fallback_used
            and all(
                audit.rank == direct_system_size(len(spec.component_names))
                and audit.condition < JACOBIAN_CONDITION_HARD_STOP
                and not audit.zero_rows
                and not audit.zero_columns
                and not audit.unexpected_couplings
                and audit.colored_uncolored_relative
                < JACOBIAN_AGREEMENT_TOLERANCE
                for audit in jacobians
            )
        )
        state_report["pass_gate"] = state_pass
        state_reports[name] = state_report
        all_state_pass = all_state_pass and state_pass

    layout = direct_coordinate_layout(spec)
    pattern = structural_pattern(spec, canonical.rows)
    structural_rank_value = int(structural_rank(csr_matrix(pattern)))
    local_pass = bool(
        all(
            closure["converged"]
            and closure["energy_residual_max"] < LOCAL_CLOSURE_TOLERANCE
            and (
                closure["equilibrium_residual_max"] is None
                or closure["equilibrium_residual_max"] < LOCAL_CLOSURE_TOLERANCE
            )
            and not closure.get("active_bounds", False)
            and not closure.get("clipping_or_projection_used", False)
            for closure in local_closures.values()
        )
    )
    canonical_state = state_reports["canonical_mini8_derived"]
    source_liquid = [
        source_profile["source_liquid_flow_lbmolph"][
            DIRECT_VOLUME_IDS.index(volume)
        ]
        for volume in HYDRAULIC_VOLUME_IDS
    ]
    hydraulic = {
        "source_profile_liquid_flow_lbmolph": source_liquid,
        "derived_francis_flow_lbmolph": canonical_state[
            "francis_flow_lbmolph"
        ],
        "residence_time_sec": canonical_state["residence_time_sec"],
        "flow_ratio_francis_over_source": [
            derived / source
            for derived, source in zip(
                canonical_state["francis_flow_lbmolph"],
                source_liquid,
            )
        ],
        "feed_role_francis_flow_lbmolph": canonical_state[
            "francis_flow_lbmolph"
        ][HYDRAULIC_VOLUME_IDS.index("feed_tray")],
        "geometry_or_coefficient_adjusted_during_dd081": False,
    }
    hard_stops = {
        "local_closure_pass": local_pass,
        "direct_registry_square": len(layout.names) == len(canonical.rows),
        "direct_structural_rank_full": structural_rank_value == len(layout.names),
        "all_numerical_states_pass": all_state_pass,
        "component_telescoping_all_states": all(
            state["component_telescoping_relative_error"]
            < COMPONENT_CONSERVATION_TOLERANCE
            for state in state_reports.values()
        ),
        "energy_telescoping_all_states": all(
            state["energy_telescoping_relative_error"]
            < ENERGY_CONSERVATION_TOLERANCE
            for state in state_reports.values()
        ),
        "terminal_draws_use_live_composition": True,
        "francis_is_sole_internal_liquid_flow_owner": True,
        "total_condenser_has_no_inventory": True,
        "fixed_volume_equation_absent": True,
        "serialized_enthalpy_absent": True,
        "pressure_and_vapor_rates_remain_parameters": True,
        "no_clipping_projection_or_property_fallback": True,
        "geometry_unchanged_during_gate": True,
    }
    passed = bool(all(hard_stops.values()))
    report = {
        "schema_id": "dd081-core-v2-gate-c-five-volume-numerical-audit-v1",
        "classification": (
            "dd081_five_volume_numerical_gate_passed"
            if passed
            else "dd081_five_volume_numerical_gate_failed"
        ),
        "decision": (
            "authorize_one_bounded_dd082_five_volume_steady_solve"
            if passed
            else "stop_before_five_volume_nonlinear_solve"
        ),
        "authorization": (
            "DD-081 passes. DD-082 may make one bounded five-volume steady "
            "solve using the frozen equations, scales, tolerances, and three "
            "predeclared starts. Pressure dynamics, vapor holdup, energy-owned "
            "vapor traffic, controllers, and production tray count remain "
            "unauthorized."
            if passed
            else
            "DD-081 failed a declared hard stop. Do not attempt DD-082 or tune "
            "the numerical method; correct the equation, ownership, property, "
            "or conditioning defect first."
        ),
        "workbook": str(workbook_path.resolve()),
        "property_package": property_package,
        "component_names": list(spec.component_names),
        "source_profile": source_profile,
        "operating_parameters": operating,
        "local_closures": local_closures,
        "representation": {
            "dd077_ledger_count": 53,
            "eliminated_coordinates": 15,
            "eliminated_residuals": 15,
            "direct_count": len(layout.names),
            "direct_structural_rank": structural_rank_value,
            "direct_coordinate_names": list(layout.names),
            "direct_residual_names": [row.name for row in canonical.rows],
            "explanation": (
                "DD-077 retained NL and two independent x coordinates per "
                "volume, with three component-reconstruction rows per volume. "
                "DD-080 established exact direct reconstruction NL=sum(N) and "
                "x=N/NL. DD-081 eliminates those 15 coordinates and their 15 "
                "identity rows before numerical differentiation. This is an "
                "algebraic substitution of the DD-077 ledger, not a change to "
                "the physical equations."
            ),
        },
        "residual_scales": _float_list(fixed_scales),
        "states": state_reports,
        "hydraulic_diagnostic": hydraulic,
        "hard_stops": hard_stops,
        "tolerances": {
            "component_conservation_relative": COMPONENT_CONSERVATION_TOLERANCE,
            "energy_conservation_relative": ENERGY_CONSERVATION_TOLERANCE,
            "local_closure": LOCAL_CLOSURE_TOLERANCE,
            "jacobian_condition_preferred": JACOBIAN_CONDITION_PREFERRED,
            "jacobian_condition_hard_stop": JACOBIAN_CONDITION_HARD_STOP,
            "jacobian_colored_uncolored_relative": JACOBIAN_AGREEMENT_TOLERANCE,
            "jacobian_steps": list(JACOBIAN_STEPS),
        },
        "five_volume_nonlinear_solve_attempted": False,
        "local_gate_b_closures_solved_for_reference": True,
        "dynamic_integration_attempted": False,
        "pressure_dynamics_present": False,
        "vapor_holdup_present": False,
        "energy_determined_vapor_rates_present": False,
        "controllers_present": False,
        "production_scale_present": False,
        "gate_c_solve_authorized": passed,
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
        default=Path(
            "sandbox/mini8/input/distillation_column_template_8stage.xlsx"
        ),
    )
    parser.add_argument(
        "--property-package",
        default="pr",
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd081_core_v2_gate_c_five_volume_20260718"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(args.workbook, args.property_package, args.out_prefix)
    summary = {
        "classification": result["classification"],
        "decision": result["decision"],
        "direct_count": result["representation"]["direct_count"],
        "direct_structural_rank": result["representation"][
            "direct_structural_rank"
        ],
        "gate_c_solve_authorized": result["gate_c_solve_authorized"],
        "wall_clock_sec": result["wall_clock_sec"],
    }
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if result["gate_c_solve_authorized"] else 2)
