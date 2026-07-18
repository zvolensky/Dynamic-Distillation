#!/usr/bin/env python
"""Run the frozen DD-084 live residual and Jacobian audit."""

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

from audit_core_v2_gate_c_five_volume import (
    _geometry_at,
    _required_spec_float,
    _select_role_indices,
    _stream_component_vector,
)
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedOperatingSpec,
    EnergyOwnedReference,
    audit_numerical_jacobian,
    audit_points,
    coordinate_layout,
    evaluate_residual,
    structural_pattern,
)
from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    VAPOR_LINKS,
    VOLUME_IDS,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


COMPONENT_CONSERVATION_TOLERANCE = 1.0e-12
ENERGY_CONSERVATION_TOLERANCE = 1.0e-10
JACOBIAN_CONDITION_HARD_STOP = 1.0e8
JACOBIAN_COUPLING_TOLERANCE = 1.0e-7
JACOBIAN_STEPS = (1.0e-5, 5.0e-6)


def _float_list(values) -> list[float]:
    return [
        float(value)
        for value in np.asarray(values, dtype=float).reshape((-1,))
    ]


def _build_problem(workbook_path: Path, property_package: str):
    column = build_column_spec_from_case(load_case_from_excel(str(workbook_path)))
    if column.M_L_lbmol is None:
        raise ValueError("DD-084 input requires source liquid holdups")
    source_indices = _select_role_indices(column)
    provider = ThermoProviderV1(
        component_names_excel=column.components_excel,
        component_ids_dwsim=column.components_dwsim,
        property_package=property_package,
        silence_backend_console=True,
    )
    feed = column.streams.get("Feed")
    distillate = column.streams.get("Distillate")
    bottoms = column.streams.get("Bottom")
    if feed is None or distillate is None or bottoms is None:
        raise ValueError("DD-084 requires Feed, Distillate, and Bottom streams")
    if feed.temperature_f is None or feed.pressure_psia is None:
        raise ValueError("DD-084 feed requires temperature and pressure")
    if column.duties.q_cond_btu_per_h is None or column.duties.q_reb_btu_per_h is None:
        raise ValueError("DD-084 requires declared condenser and reboiler duties")

    components = tuple(column.components_excel)
    feed_component = _stream_component_vector(feed, components)
    feed_total = float(np.sum(feed_component))
    feed_x = feed_component / feed_total
    feed_h = float(
        provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            float(feed.temperature_f),
            float(feed.pressure_psia),
            feed_x.tolist(),
        )
    )
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
    vapor_y = np.asarray(
        [
            normalize_composition(column.y0[source_indices[VOLUME_IDS.index(volume)]])
            for volume in EQUILIBRIUM_VOLUME_IDS
        ],
        dtype=float,
    )
    liquid_flow = np.asarray(
        [
            float(column.L_lbmolph[source_indices[VOLUME_IDS.index(volume)]])
            for volume in HYDRAULIC_VOLUME_IDS
        ],
        dtype=float,
    )
    vapor_flow = np.asarray(
        [
            float(column.V_lbmolph[source_indices[VOLUME_IDS.index(source)]])
            for source, _destination, _symbol in VAPOR_LINKS
        ],
        dtype=float,
    )
    positive_arrays = (
        liquid_moles,
        liquid_x,
        vapor_y,
        liquid_flow,
        vapor_flow,
    )
    if any(
        np.any(~np.isfinite(values)) or np.any(values <= 0)
        for values in positive_arrays
    ):
        raise ValueError("DD-084 role-mapped seed must be finite and positive")

    spec = EnergyOwnedOperatingSpec(
        component_names=components,
        pressure_psia=pressure,
        reflux_lbmolph=float(column.L_lbmolph[0]),
        feed_component_lbmolph=feed_component,
        feed_enthalpy_BTUph=feed_total * feed_h,
        condenser_duty_BTUph=float(column.duties.q_cond_btu_per_h),
        reboiler_duty_BTUph=float(column.duties.q_reb_btu_per_h),
        terminal_liquid_targets_lbmol=np.asarray(
            [target_top, target_bottom],
            dtype=float,
        ),
        hydraulic_geometry=tuple(
            _geometry_at(column, source_indices[VOLUME_IDS.index(volume)])
            for volume in HYDRAULIC_VOLUME_IDS
        ),
    )
    reference = EnergyOwnedReference(
        liquid_moles_lbmol=liquid_moles,
        liquid_mole_fraction=liquid_x,
        temperature_F=temperature,
        vapor_mole_fraction=vapor_y,
        hydraulic_liquid_flow_lbmolph=liquid_flow,
        vapor_flow_lbmolph=vapor_flow,
        distillate_lbmolph=float(distillate.total_molar_flow_lbmolph),
        bottoms_lbmolph=float(bottoms.total_molar_flow_lbmolph),
    )
    source = {
        "source_stage_1based": [int(index + 1) for index in source_indices],
        "roles": list(VOLUME_IDS),
        "temperature_F": _float_list(temperature),
        "pressure_psia": _float_list(pressure),
        "liquid_moles_lbmol": _float_list(liquid_moles),
        "liquid_mole_fraction": [_float_list(row) for row in liquid_x],
        "vapor_mole_fraction": [_float_list(row) for row in vapor_y],
        "liquid_flow_reference_lbmolph": _float_list(liquid_flow),
        "vapor_flow_reference_lbmolph": _float_list(vapor_flow),
        "seed_mapping_used_flash_or_closure_solve": False,
    }
    operating = {
        "reflux_lbmolph": float(spec.reflux_lbmolph),
        "feed_component_lbmolph": _float_list(feed_component),
        "feed_enthalpy_BTUph": float(spec.feed_enthalpy_BTUph),
        "condenser_duty_BTUph": float(spec.condenser_duty_BTUph),
        "reboiler_duty_BTUph": float(spec.reboiler_duty_BTUph),
        "terminal_liquid_targets_lbmol": _float_list(
            spec.terminal_liquid_targets_lbmol
        ),
        "distillate_reference_lbmolph": float(reference.distillate_lbmolph),
        "bottoms_reference_lbmolph": float(reference.bottoms_lbmolph),
    }
    return provider, spec, reference, source, operating


def _dominant_rows(evaluation, count: int = 10) -> list[dict]:
    order = np.argsort(np.abs(evaluation.scaled))[::-1][:count]
    return [
        {
            "name": evaluation.rows[index].name,
            "block": evaluation.rows[index].block,
            "owner": evaluation.rows[index].owner,
            "raw": float(evaluation.raw[index]),
            "scaled": float(evaluation.scaled[index]),
        }
        for index in order
    ]


def _state_report(spec, evaluation, jacobians) -> dict:
    state = evaluation.state
    properties = evaluation.properties
    heights = [
        float(properties.liquid_height_ft[VOLUME_IDS.index(volume)])
        for volume in HYDRAULIC_VOLUME_IDS
    ]
    spacings = [
        float(geometry.tray_spacing_ft) for geometry in spec.hydraulic_geometry
    ]
    jacobian_pass = all(
        audit.rank == len(evaluation.raw)
        and audit.condition < JACOBIAN_CONDITION_HARD_STOP
        and not audit.zero_rows
        and not audit.zero_columns
        and not audit.unexpected_couplings
        for audit in jacobians
    )
    physical_pass = bool(
        np.all(np.isfinite(evaluation.raw))
        and np.all(state.liquid_moles_lbmol > 0)
        and np.all(state.temperature_F > 0)
        and np.all(state.liquid_mole_fraction > 0)
        and np.all(state.vapor_mole_fraction > 0)
        and np.all(state.hydraulic_liquid_flow_lbmolph > 0)
        and np.all(state.vapor_flow_lbmolph > 0)
        and state.distillate_lbmolph > 0
        and state.bottoms_lbmolph > 0
        and all(height < spacing for height, spacing in zip(heights, spacings))
    )
    conservation_pass = bool(
        evaluation.component_telescoping_relative_error
        < COMPONENT_CONSERVATION_TOLERANCE
        and evaluation.energy_telescoping_relative_error
        < ENERGY_CONSERVATION_TOLERANCE
    )
    passed = bool(
        jacobian_pass
        and physical_pass
        and conservation_pass
        and not evaluation.clipping_or_projection_used
        and not evaluation.property_fallback_used
    )
    return {
        "pass_gate": passed,
        "scaled_residual_inf_norm": float(np.max(np.abs(evaluation.scaled))),
        "raw_residual_inf_norm": float(np.max(np.abs(evaluation.raw))),
        "dominant_residuals": _dominant_rows(evaluation),
        "component_telescoping_error_lbmolph": _float_list(
            evaluation.component_telescoping_error_lbmolph
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
        "liquid_flow_lbmolph": _float_list(
            state.hydraulic_liquid_flow_lbmolph
        ),
        "vapor_flow_lbmolph": _float_list(state.vapor_flow_lbmolph),
        "francis_flow_lbmolph": _float_list(
            [
                properties.francis_flow_lbmolph[VOLUME_IDS.index(volume)]
                for volume in HYDRAULIC_VOLUME_IDS
            ]
        ),
        "liquid_height_ft": heights,
        "tray_spacing_ft": spacings,
        "distillate_lbmolph": float(state.distillate_lbmolph),
        "bottoms_lbmolph": float(state.bottoms_lbmolph),
        "physical_pass": physical_pass,
        "conservation_pass": conservation_pass,
        "jacobian_pass": jacobian_pass,
        "jacobians": [
            {
                "step": float(audit.step),
                "rank": int(audit.rank),
                "condition": float(audit.condition),
                "zero_rows": list(audit.zero_rows),
                "zero_columns": list(audit.zero_columns),
                "unexpected_couplings": list(audit.unexpected_couplings),
            }
            for audit in jacobians
        ],
    }


def _render_markdown(report: dict) -> str:
    lines = [
        "# DD-084 Energy-Owned Vapor Numerical Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision']}`",
        f"- Runtime: `{report['wall_clock_sec']:.3f} s`",
        f"- Unknowns/residuals: `{report['unknown_count']} / "
        f"{report['residual_count']}`",
        f"- Structural rank: `{report['structural_rank']}`",
        f"- Nonlinear solve attempted: `{report['nonlinear_solve_attempted']}`",
        f"- Dynamic integration attempted: `{report['dynamic_integration_attempted']}`",
        "",
        "## Numerical States",
        "",
        "| State | Residual inf | Rank h / h/2 | Worst condition | Pass |",
        "|---|---:|---:|---:|---|",
    ]
    for name, state in report["states"].items():
        jac = state["jacobians"]
        lines.append(
            f"| {name} | {state['scaled_residual_inf_norm']:.6e} | "
            f"{jac[0]['rank']} / {jac[1]['rank']} | "
            f"{max(jac[0]['condition'], jac[1]['condition']):.6e} | "
            f"{state['pass_gate']} |"
        )
    lines.extend(("", "## Decision", "", report["authorization"], ""))
    return "\n".join(lines)


def run(workbook_path: Path, property_package: str, out_prefix: Path) -> dict:
    started = time.perf_counter()
    provider, spec, reference, source, operating = _build_problem(
        workbook_path,
        property_package,
    )
    points = audit_points(spec)
    canonical = evaluate_residual(
        spec,
        reference,
        provider,
        points["canonical_role_mapped_seed"],
    )
    fixed_scales = canonical.scales.copy()
    states = {}
    for name, point in points.items():
        evaluation = evaluate_residual(
            spec,
            reference,
            provider,
            point,
            fixed_scales=fixed_scales,
        )
        jacobians = [
            audit_numerical_jacobian(
                spec,
                reference,
                provider,
                point,
                fixed_scales=fixed_scales,
                step=step,
                coupling_tolerance=JACOBIAN_COUPLING_TOLERANCE,
            )
            for step in JACOBIAN_STEPS
        ]
        states[name] = _state_report(spec, evaluation, jacobians)

    layout = coordinate_layout(spec)
    pattern = structural_pattern(spec)
    structural_rank_value = int(structural_rank(csr_matrix(pattern)))
    passed = bool(
        len(layout.names) == 37
        and canonical.raw.size == 37
        and structural_rank_value == 37
        and all(state["pass_gate"] for state in states.values())
    )
    report = {
        "schema_id": "dd084-core-v2-energy-owned-vapor-numerical-audit-v1",
        "classification": (
            "dd084_numerical_gate_passed"
            if passed
            else "dd084_numerical_gate_failed"
        ),
        "decision": (
            "authorize_drafting_one_frozen_steady_root_contract"
            if passed
            else "stop_energy_owned_vapor_architecture_before_root_solve"
        ),
        "authorization": (
            "DD-084 passes. One bounded steady-root campaign may be designed "
            "and precommitted next. No nonlinear solve or dynamic integration "
            "is authorized by this audit."
            if passed
            else "DD-084 failed a frozen hard stop. Do not tune the audit or "
            "attempt a nonlinear solve."
        ),
        "workbook": str(workbook_path.resolve()),
        "property_package": property_package,
        "component_names": list(spec.component_names),
        "unknown_count": len(layout.names),
        "residual_count": int(canonical.raw.size),
        "structural_rank": structural_rank_value,
        "coordinate_names": list(layout.names),
        "residual_names": [row.name for row in canonical.rows],
        "fixed_residual_scales": _float_list(fixed_scales),
        "source_mapping": source,
        "operating_parameters": operating,
        "states": states,
        "tolerances": {
            "component_conservation_relative": COMPONENT_CONSERVATION_TOLERANCE,
            "energy_conservation_relative": ENERGY_CONSERVATION_TOLERANCE,
            "jacobian_condition_hard_stop": JACOBIAN_CONDITION_HARD_STOP,
            "jacobian_coupling": JACOBIAN_COUPLING_TOLERANCE,
            "jacobian_steps": list(JACOBIAN_STEPS),
        },
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "clipping_projection_profile_forcing_or_controller_present": False,
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
        default=Path("sandbox/mini8/input/distillation_column_template_8stage.xlsx"),
    )
    parser.add_argument("--property-package", default="pr")
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd084_energy_owned_vapor_numerical_20260718"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(args.workbook, args.property_package, args.out_prefix)
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "decision": result["decision"],
                "structural_rank": result["structural_rank"],
                "wall_clock_sec": result["wall_clock_sec"],
            },
            indent=2,
        )
    )
    raise SystemExit(
        0 if result["classification"] == "dd084_numerical_gate_passed" else 2
    )
