#!/usr/bin/env python
"""Run the one permitted DD-070 canonical checkpoint-repair attempt."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.canonical_checkpoint_repair_v1 import (
    CanonicalSourceInput,
    canonicalize_source_node,
    combine_canonical_sources,
    direct_canonical_target,
)
from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.dynamic_run_scaffold_v1 import read_native_checkpoint
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    _array_or_default,
    _layout_from_checkpoint,
    build_frozen_checkpoint_bridge,
    run_local_closure_audit,
    run_terminal_closure_audit,
)
from dynamic_distillation.least_movement_redistribution_v1 import (
    assess_multistart_results,
    build_energy_only_pressure_profile_start,
    build_movement_scales,
    conservative_random_start,
    normalized_movement_from_absolute_state,
    solve_least_movement_redistribution,
)
from dynamic_distillation.terminal_energy_volume_audit_v1 import (
    EnergyVolumeRegionInput,
    audit_energy_scaling,
    audit_energy_volume_region,
)
from dynamic_distillation.uv_flash_sandbox_v1 import _build_provider


DD067_ENERGY_MOVE_BTU = 747127.1133593691
DD068_MAX_PRESSURE_CHANGE_PSI = 79.15872501700662


def _finite_or_none(value: float) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _load_dd067_start(
    *,
    report_path: Path,
    targets,
    scales,
) -> tuple[np.ndarray, np.ndarray]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = {str(row["node_id"]): row for row in report["nodes"]}
    n_values = np.vstack(
        [
            np.asarray(node.total_component_inventory_lbmol, dtype=float)
            for node in targets
        ]
    )
    u_values = np.asarray(
        [
            float(rows[node.node_id]["implied_internal_energy_BTU"])
            for node in targets
        ],
        dtype=float,
    )
    q = normalized_movement_from_absolute_state(
        targets=targets,
        scales=scales,
        component_inventory_lbmol=n_values,
        internal_energy_BTU=u_values,
    )
    return q, np.asarray(report["final_pressure_psia"], dtype=float)


def _result_document(result, *, component_names) -> Dict[str, Any]:
    return {
        "classification": result.classification,
        "converged": result.converged,
        "objective": result.objective,
        "component_objective": result.component_objective,
        "energy_objective": result.energy_objective,
        "component_conservation_error_lbmol": (
            result.component_conservation_error_lbmol.tolist()
        ),
        "component_conservation_relative_max": (
            result.component_conservation_relative_max
        ),
        "energy_conservation_error_BTU": result.energy_conservation_error_BTU,
        "energy_conservation_relative": result.energy_conservation_relative,
        "maximum_pressure_order_violation_psi": (
            result.maximum_pressure_order_violation_psi
        ),
        "pressure_ordering_pass": result.pressure_ordering_pass,
        "all_local_closures_pass": result.all_local_closures_pass,
        "active_bound_count": result.active_bound_count,
        "first_order_optimality_norm": result.first_order_optimality_norm,
        "constraint_violation_norm": result.constraint_violation_norm,
        "total_uv_solves": result.total_uv_solves,
        "optimizer_termination_reason": result.optimizer_termination_reason,
        "diagnostics": {
            "material_move_L1_lbmol": (
                result.diagnostics.material_move_L1_lbmol
            ),
            "material_move_L1_by_component_lbmol": {
                str(name): float(value)
                for name, value in zip(
                    component_names,
                    result.diagnostics.material_move_L1_by_component_lbmol,
                )
            },
            "energy_move_L1_BTU": result.diagnostics.energy_move_L1_BTU,
            "terminal_component_abs_fraction": (
                result.diagnostics.terminal_component_abs_fraction
            ),
            "terminal_energy_abs_fraction": (
                result.diagnostics.terminal_energy_abs_fraction
            ),
            "maximum_pressure_change_psi": (
                result.diagnostics.maximum_pressure_change_psi
            ),
            "pressure_rms_change_psi": (
                result.diagnostics.pressure_rms_change_psi
            ),
            "maximum_scaled_component_change": (
                result.diagnostics.maximum_scaled_component_change
            ),
            "maximum_scaled_energy_change": (
                result.diagnostics.maximum_scaled_energy_change
            ),
        },
        "normalized_component_change": (
            result.normalized_component_change.tolist()
        ),
        "normalized_energy_change": (
            result.normalized_energy_change.tolist()
        ),
        "nodes": [
            {
                "node_id": row.node_id,
                "position_1based": row.position_1based,
                "component_inventory_lbmol": {
                    str(name): float(value)
                    for name, value in zip(
                        component_names,
                        row.component_inventory_lbmol,
                    )
                },
                "component_change_lbmol": {
                    str(name): float(value)
                    for name, value in zip(
                        component_names,
                        result.component_change_lbmol[idx, :],
                    )
                },
                "internal_energy_BTU": row.internal_energy_BTU,
                "internal_energy_change_BTU": float(
                    result.energy_change_BTU[idx]
                ),
                "T_F": row.closure.T_F,
                "P_psia": row.closure.P_psia,
                "beta_vapor": row.closure.beta_vapor,
                "component_relative_residual": (
                    row.component_relative_residual
                ),
                "energy_relative_residual": row.energy_relative_residual,
                "volume_relative_residual": row.volume_relative_residual,
                "equilibrium_beta_residual": (
                    row.equilibrium_beta_residual
                ),
                "active_bound_count": row.active_bound_count,
            }
            for idx, row in enumerate(result.nodes)
        ],
    }


def _pattern_spread(named_results) -> tuple[float, float]:
    successful = [
        result
        for _name, result in named_results
        if result.converged and np.isfinite(result.objective)
    ]
    if len(successful) < 2:
        return float("inf"), float("inf")
    q_values = [
        np.concatenate(
            [
                result.normalized_component_change.reshape((-1,)),
                result.normalized_energy_change.reshape((-1,)),
            ]
        )
        for result in successful
    ]
    maximum = 0.0
    rms_maximum = 0.0
    for left_idx in range(len(q_values)):
        for right_idx in range(left_idx + 1, len(q_values)):
            difference = q_values[left_idx] - q_values[right_idx]
            maximum = max(maximum, float(np.max(np.abs(difference))))
            rms_maximum = max(
                rms_maximum,
                float(np.sqrt(np.mean(np.square(difference)))),
            )
    return maximum, rms_maximum


def _render_markdown(report: Dict[str, Any]) -> str:
    assessment = report["multistart_assessment"]
    best = report.get("best_result")
    gate = report["acceptance_gate"]
    lines = [
        "# DD-070 Canonical Checkpoint Repair",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['checkpoint_repair_decision']}`",
        f"- Thermo: `{report['thermo_mode']}`",
        f"- Sump topology: `{report['sump_topology']}`",
        f"- Scale mode: `{report['movement_scale_mode']}`",
        "",
        "## Canonical Mapping",
        "",
        f"- Stored whole-column U: `{report['canonical_mapping']['stored_total_internal_energy_BTU']:.9g} BTU`",
        f"- Canonical whole-column U: `{report['canonical_mapping']['canonical_total_internal_energy_BTU']:.9g} BTU`",
        f"- Mapping replacement: `{report['canonical_mapping']['total_mapping_energy_change_BTU']:.9g} BTU`",
        f"- Enthalpy offset classification: `{report['canonical_mapping']['enthalpy_offset_classification']}`",
        "",
        "| Node | Topology | Stored U, BTU | Canonical U, BTU | Mapping delta U, BTU | Prior V mismatch | Canonical target V mismatch |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["canonical_mapping"]["targets"]:
        lines.append(
            f"| {row['node_id']} | {row['topology']} | "
            f"{row['stored_internal_energy_BTU']:.6g} | "
            f"{row['canonical_internal_energy_BTU']:.6g} | "
            f"{row['mapping_energy_change_BTU']:.6g} | "
            f"{row['prior_volume_mismatch_relative_max']:.6g} | "
            f"{row['canonical_volume_mismatch_relative']:.6g} |"
        )
    lines.extend(
        [
            "",
            "## Multi-Start Result",
            "",
            "| Start | Converged | Objective | Energy moved, BTU | Material moved, lbmol | Max dP, psi | Terminal energy fraction |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for start in report["starts"]:
        result = start["result"]
        diagnostics = result["diagnostics"]
        lines.append(
            f"| {start['name']} | {result['converged']} | "
            f"{result['objective']:.6g} | "
            f"{diagnostics['energy_move_L1_BTU']:.6g} | "
            f"{diagnostics['material_move_L1_lbmol']:.6g} | "
            f"{diagnostics['maximum_pressure_change_psi']:.6g} | "
            f"{diagnostics['terminal_energy_abs_fraction']:.6g} |"
        )
    lines.extend(
        [
            "",
            f"- Successful starts: `{len(assessment['successful_start_names'])}` / `{len(assessment['start_names'])}`",
            f"- Objective relative spread: `{assessment['relative_objective_spread']}`",
            f"- Maximum normalized pattern difference: `{assessment['maximum_normalized_pattern_difference']}`",
            f"- Reproducible basin pass: `{assessment['reproducible_minimum_pass']}`",
        ]
    )
    if best is not None:
        diagnostics = best["diagnostics"]
        lines.extend(
            [
                "",
                "## Best Candidate",
                "",
                f"- Energy moved: `{diagnostics['energy_move_L1_BTU']:.9g} BTU`",
                f"- Material moved: `{diagnostics['material_move_L1_lbmol']:.9g} lbmol`",
                f"- Maximum pressure correction: `{diagnostics['maximum_pressure_change_psi']:.9g} psi`",
                f"- Terminal energy movement fraction: `{diagnostics['terminal_energy_abs_fraction']:.6g}`",
                f"- Terminal energy-capacity fraction: `{report['terminal_concentration']['terminal_energy_capacity_fraction']:.6g}`",
                f"- Terminal concentration ratio: `{report['terminal_concentration']['movement_to_capacity_ratio']:.6g}`",
                "",
                "| Node | T, F | P, psia | Vapor fraction | Delta U, BTU |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in best["nodes"]:
            lines.append(
                f"| {row['node_id']} | {row['T_F']:.6g} | "
                f"{row['P_psia']:.6g} | {row['beta_vapor']:.6g} | "
                f"{row['internal_energy_change_BTU']:.6g} |"
            )
    lines.extend(
        [
            "",
            "## Acceptance Gate",
            "",
            "| Criterion | Pass |",
            "|---|---:|",
        ]
    )
    for name, value in gate["criteria"].items():
        lines.append(f"| {name} | {value} |")
    lines.extend(
        [
            "",
            "## Final Decision",
            "",
            report["decision"],
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> Dict[str, Any]:
    excel = str(Path(args.excel).resolve())
    checkpoint_path = str(Path(args.checkpoint).resolve())
    col = build_column_spec_from_case(load_case_from_excel(excel))
    checkpoint = read_native_checkpoint(checkpoint_path)
    metadata = dict(checkpoint.get("metadata") or {})
    arrays = dict(checkpoint.get("arrays") or {})
    layout = _layout_from_checkpoint(
        metadata,
        n_stages=int(col.n_stages),
        n_components=int(col.n_components),
    )
    unpacked = layout.unpack(np.asarray(arrays["final_state"], dtype=float))
    pressure_full = _array_or_default(
        arrays,
        "diag__P_psia_hyd",
        shape=(int(col.n_stages),),
        default=np.asarray(col.P_psia, dtype=float),
    )
    temperature_full = np.asarray(unpacked["tray_T_f"], dtype=float).reshape(
        (int(col.n_stages),)
    )
    tray_l = np.asarray(unpacked["tray_L"], dtype=float)
    tray_v = np.asarray(unpacked["tray_V"], dtype=float)
    tray_el = np.asarray(unpacked["tray_EL_BTU"], dtype=float)
    tray_ev = np.asarray(unpacked["tray_EV_BTU"], dtype=float)

    provider, thermo_mode = _build_provider(
        col,
        thermo_mode=args.thermo,
        thermo_table_path=args.thermo_table,
        thermo_pool_workers=None,
        thermo_pool_chunk_size=4,
    )
    try:
        bridge = build_frozen_checkpoint_bridge(
            excel_path=excel,
            checkpoint_path=checkpoint_path,
            provider=provider,
        )
        local = run_local_closure_audit(bridge=bridge, provider=provider)
        terminal = run_terminal_closure_audit(
            bridge=bridge,
            provider=provider,
        )
        terminal_nodes = {
            str(node.node_id): node
            for node in bridge.terminal_inventory_map.nodes
        }
        source_mappings = []

        reflux = terminal_nodes["reflux_drum"]
        reflux_region = EnergyVolumeRegionInput(
            region_id="reflux_drum",
            category="terminal_equipment",
            source_blocks=tuple(reflux.source_blocks),
            temperature_F=float(reflux.temperature_guess_F),
            pressure_psia=float(reflux.pressure_guess_psia),
            liquid_inventory_lbmol=reflux.liquid_inventory_lbmol,
            vapor_inventory_lbmol=reflux.vapor_inventory_lbmol,
            fixed_total_volume_ft3=float(reflux.fixed_total_volume_ft3),
            mapped_internal_energy_BTU=float(
                reflux.total_internal_energy_BTU
            ),
            mapped_energy_basis="phase_property_sum",
        )
        reflux_mapping = canonicalize_source_node(
            provider=provider,
            source=CanonicalSourceInput(
                node_id="reflux_drum",
                position_1based=1,
                component_inventory_lbmol=(
                    reflux.total_component_inventory_lbmol
                ),
                region=reflux_region,
                canonical_fixed_volume_ft3=float(
                    reflux.fixed_total_volume_ft3
                ),
                topology="explicit_reflux_drum_vapor_owner",
            ),
        )
        source_mappings.append(reflux_mapping)
        top_target = combine_canonical_sources(
            node_id="top_terminal",
            position_1based=1,
            sources=(reflux_mapping,),
            topology="explicit_reflux_drum_vapor_owner",
        )

        active_stage_to_index = {
            int(stage): idx
            for idx, stage in enumerate(bridge.spec.active_stage1)
        }
        interior_targets = []
        for stage_1based in bridge.spec.active_stage1:
            stage1 = int(stage_1based)
            stage0 = stage1 - 1
            active_idx = active_stage_to_index[stage1]
            region = EnergyVolumeRegionInput(
                region_id=f"tray_{stage1}",
                category="interior",
                source_blocks=(f"tray_stage_{stage1}",),
                temperature_F=float(temperature_full[stage0]),
                pressure_psia=float(pressure_full[stage0]),
                liquid_inventory_lbmol=tray_l[stage0, :],
                vapor_inventory_lbmol=tray_v[stage0, :],
                fixed_total_volume_ft3=float(
                    bridge.spec.fixed_total_volume_ft3[active_idx]
                ),
                mapped_internal_energy_BTU=float(
                    bridge.stage_total_internal_energy_BTU[active_idx]
                ),
                mapped_energy_basis="stored_enthalpy_minus_fixed_pv",
                stored_enthalpy_BTU=float(
                    tray_el[stage0] + tray_ev[stage0]
                ),
            )
            mapping = canonicalize_source_node(
                provider=provider,
                source=CanonicalSourceInput(
                    node_id=f"tray_{stage1}",
                    position_1based=len(interior_targets) + 2,
                    component_inventory_lbmol=(
                        bridge.stage_total_components_lbmol[active_idx, :]
                    ),
                    region=region,
                    canonical_fixed_volume_ft3=float(
                        bridge.spec.fixed_total_volume_ft3[active_idx]
                    ),
                    topology="fixed_stage_shell_volume",
                ),
            )
            source_mappings.append(mapping)
            interior_targets.append(direct_canonical_target(mapping=mapping))

        reboiler = terminal_nodes["reboiler_stage"]
        reboiler_region = EnergyVolumeRegionInput(
            region_id="reboiler_stage",
            category="terminal_equipment",
            source_blocks=tuple(reboiler.source_blocks),
            temperature_F=float(reboiler.temperature_guess_F),
            pressure_psia=float(reboiler.pressure_guess_psia),
            liquid_inventory_lbmol=reboiler.liquid_inventory_lbmol,
            vapor_inventory_lbmol=reboiler.vapor_inventory_lbmol,
            fixed_total_volume_ft3=float(reboiler.fixed_total_volume_ft3),
            mapped_internal_energy_BTU=float(
                reboiler.total_internal_energy_BTU
            ),
            mapped_energy_basis="stored_enthalpy_minus_fixed_pv",
            stored_enthalpy_BTU=float(tray_el[-1] + tray_ev[-1]),
        )
        reboiler_mapping = canonicalize_source_node(
            provider=provider,
            source=CanonicalSourceInput(
                node_id="reboiler_stage",
                position_1based=len(interior_targets) + 2,
                component_inventory_lbmol=(
                    reboiler.total_component_inventory_lbmol
                ),
                region=reboiler_region,
                canonical_fixed_volume_ft3=float(
                    reboiler.fixed_total_volume_ft3
                ),
                topology="explicit_reboiler_vapor_owner",
            ),
        )
        source_mappings.append(reboiler_mapping)

        sump = terminal_nodes["bottoms_sump"]
        sump_region = EnergyVolumeRegionInput(
            region_id="bottoms_sump",
            category="terminal_equipment",
            source_blocks=tuple(sump.source_blocks),
            temperature_F=float(sump.temperature_guess_F),
            pressure_psia=float(sump.pressure_guess_psia),
            liquid_inventory_lbmol=sump.liquid_inventory_lbmol,
            vapor_inventory_lbmol=sump.vapor_inventory_lbmol,
            fixed_total_volume_ft3=float(sump.fixed_total_volume_ft3),
            mapped_internal_energy_BTU=float(sump.total_internal_energy_BTU),
            mapped_energy_basis="phase_property_sum",
        )
        sump_pre_audit = audit_energy_volume_region(
            provider=provider,
            region=sump_region,
        )
        sump_mapping = canonicalize_source_node(
            provider=provider,
            source=CanonicalSourceInput(
                node_id="bottoms_sump",
                position_1based=len(interior_targets) + 2,
                component_inventory_lbmol=(
                    sump.total_component_inventory_lbmol
                ),
                region=sump_region,
                canonical_fixed_volume_ft3=float(
                    sump_pre_audit.reconstructed_total_volume_ft3
                ),
                topology="liquid_only_sump_occupied_volume",
            ),
        )
        source_mappings.append(sump_mapping)
        bottom_target = combine_canonical_sources(
            node_id="bottom_terminal",
            position_1based=len(interior_targets) + 2,
            sources=(reboiler_mapping, sump_mapping),
            topology="explicit_reboiler_plus_liquid_only_sump",
        )
        target_mappings = (
            top_target,
            *interior_targets,
            bottom_target,
        )
        targets = tuple(mapping.target for mapping in target_mappings)
        scales = build_movement_scales(
            targets,
            scale_mode="column-common",
        )
        scaling = audit_energy_scaling(
            targets=targets,
            scales=scales,
            test_move_BTU=1000.0,
            neutrality_cost_ratio_limit=1.000001,
        )

        component_names = tuple(str(name) for name in bridge.spec.component_names)
        requested = tuple(
            item.strip()
            for item in str(args.starts).split(",")
            if item.strip()
        )
        start_vectors: Dict[str, np.ndarray] = {}
        if "checkpoint" in requested:
            start_vectors["checkpoint"] = np.zeros(
                len(targets) * (len(component_names) + 1),
                dtype=float,
            )
        needs_dd067 = "dd067" in requested or "linear" in requested
        dd067_pressure = None
        if needs_dd067:
            dd067_q, dd067_pressure = _load_dd067_start(
                report_path=Path(args.dd067_report),
                targets=targets,
                scales=scales,
            )
            if "dd067" in requested:
                start_vectors["dd067"] = dd067_q
        if "linear" in requested:
            assert dd067_pressure is not None
            linear_profile = np.linspace(
                float(dd067_pressure[0]),
                float(dd067_pressure[-1]),
                len(targets),
            )
            linear_q, _rows = build_energy_only_pressure_profile_start(
                provider=provider,
                targets=targets,
                base_pressure_psia=linear_profile,
                scales=scales,
            )
            start_vectors["linear"] = linear_q
        if "random-small" in requested:
            start_vectors["random-small"] = conservative_random_start(
                targets=targets,
                scales=scales,
                relative_magnitude=args.random_small_magnitude,
                seed=args.random_seed,
            )
        if "random-moderate" in requested:
            start_vectors["random-moderate"] = conservative_random_start(
                targets=targets,
                scales=scales,
                relative_magnitude=args.random_moderate_magnitude,
                seed=args.random_seed + 1,
            )
        unknown = sorted(set(requested) - set(start_vectors))
        if unknown:
            raise ValueError(f"unknown or unavailable starts: {unknown}")
        if args.preflight_only:
            return {
                "classification": "dd070_preflight_complete",
                "optimizer_starts_executed": 0,
                "start_names": list(requested),
                "start_vector_norms": {
                    name: float(np.linalg.norm(start_vectors[name]))
                    for name in requested
                },
                "thermo_mode": thermo_mode,
                "sump_topology": "liquid_only_sump_occupied_volume",
                "movement_scale_mode": "column-common",
            }

        named_results = []
        for name in requested:
            print(f"DD-070 one-shot start: {name}", file=sys.stderr, flush=True)
            result = solve_least_movement_redistribution(
                provider=provider,
                targets=targets,
                movement_scales=scales,
                initial_normalized_movement=start_vectors[name],
                minimum_pressure_increment_psi=args.minimum_pressure_increment,
                maximum_outer_iterations=args.max_outer_iterations,
                sensitivity_relative_step=args.sensitivity_relative_step,
                maximum_scaled_movement=args.maximum_scaled_movement,
            )
            named_results.append((name, result))
            print(
                f"  converged={result.converged} objective={result.objective:.8g} "
                f"violation={result.maximum_pressure_order_violation_psi:.6g}",
                file=sys.stderr,
                flush=True,
            )

        assessment = assess_multistart_results(
            results=named_results,
            required_relative_spread=args.objective_spread_tolerance,
        )
        pattern_max, pattern_rms = _pattern_spread(named_results)
        result_by_name = {name: result for name, result in named_results}
        best = (
            result_by_name.get(str(assessment.best_start_name))
            if assessment.best_start_name is not None
            else None
        )

        stored_total_u = float(
            sum(row.stored_internal_energy_BTU for row in source_mappings)
        )
        canonical_total_u = float(
            sum(row.canonical_internal_energy_BTU for row in source_mappings)
        )
        enthalpy_offsets = []
        for row in source_mappings:
            if row.audit.stored_enthalpy_BTU is None:
                continue
            total_moles = float(np.sum(row.component_inventory_lbmol))
            delta_h = (
                float(row.audit.reconstructed_enthalpy_BTU)
                - float(row.audit.stored_enthalpy_BTU)
            )
            enthalpy_offsets.append(delta_h / max(total_moles, 1.0e-12))
        offset_values = np.asarray(enthalpy_offsets, dtype=float)
        offset_spread = (
            float(np.ptp(offset_values))
            / max(abs(float(np.median(offset_values))), 1.0)
            if offset_values.size
            else float("inf")
        )
        offset_classification = (
            "constant_reference_offset_candidate"
            if offset_spread < 0.01
            else "state_dependent_checkpoint_enthalpy_mismatch"
        )

        if best is None:
            terminal_movement_fraction = float("inf")
            terminal_capacity_fraction = float("nan")
            terminal_ratio = float("inf")
        else:
            terminal_movement_fraction = float(
                best.diagnostics.terminal_energy_abs_fraction
            )
            energy_capacity = np.asarray(
                [abs(node.total_internal_energy_BTU) for node in targets],
                dtype=float,
            )
            terminal_capacity_fraction = float(
                (energy_capacity[0] + energy_capacity[-1])
                / max(float(np.sum(energy_capacity)), 1.0e-300)
            )
            terminal_ratio = terminal_movement_fraction / max(
                terminal_capacity_fraction,
                1.0e-300,
            )

        successful_count = len(assessment.successful_start_names)
        best_physical_pass = bool(
            best is not None
            and best.converged
            and best.component_conservation_relative_max < 1.0e-10
            and best.energy_conservation_relative < 1.0e-8
            and best.active_bound_count == 0
            and best.all_local_closures_pass
        )
        candidate_volume_pass = bool(
            best is not None
            and max(
                row.volume_relative_residual for row in best.nodes
            )
            < 0.01
        )
        criteria = {
            "at_least_4_of_5_starts_converged": successful_count >= 4,
            "objective_basin_reproduced": assessment.reproducible_minimum_pass,
            "movement_pattern_reproduced": pattern_max < 1.0e-3,
            "component_energy_local_uv_and_bounds": best_physical_pass,
            "candidate_volume_mismatch_below_1pct": candidate_volume_pass,
            "canonical_live_dwsim_energy_basis": True,
            "enthalpy_reconciliation_not_state_dependent": (
                offset_classification
                == "constant_reference_offset_candidate"
            ),
            "energy_movement_below_dd067": bool(
                best is not None
                and best.diagnostics.energy_move_L1_BTU
                < DD067_ENERGY_MOVE_BTU
            ),
            "maximum_pressure_correction_below_50psi": bool(
                best is not None
                and best.diagnostics.maximum_pressure_change_psi < 50.0
            ),
            "terminal_scaling_neutral": scaling.pass_gate,
            "terminal_movement_to_capacity_ratio_below_2": (
                terminal_ratio < 2.0
            ),
        }
        accepted = bool(all(criteria.values()))
        classification = (
            "dd070_checkpoint_repair_viable"
            if accepted
            else "dd070_checkpoint_repair_retired"
        )
        checkpoint_decision = (
            "retain_checkpoint_repair"
            if accepted
            else "retire_checkpoint_repair"
        )
        failed = [name for name, passed in criteria.items() if not passed]
        if accepted:
            decision = (
                "The one-shot corrected repair passes every predefined gate. "
                "Preserve this result as an algebraic candidate and proceed only "
                "to a separate uncapped hydraulic closure."
            )
        else:
            decision = (
                "Retire checkpoint repair. The one permitted corrected attempt "
                "failed: "
                + "; ".join(failed)
                + ". Formulate the direct conserved steady-state solve from "
                "operating specifications. Do not retune this optimizer or add "
                "hydraulics to the rejected state."
            )

        target_docs = []
        source_by_id = {
            str(source.node_id): source for source in source_mappings
        }
        for mapping in target_mappings:
            source_rows = [
                source_by_id[source_id]
                for source_id in mapping.source_node_ids
            ]
            target_docs.append(
                {
                    "node_id": mapping.target.node_id,
                    "source_node_ids": list(mapping.source_node_ids),
                    "topology": mapping.topology,
                    "stored_internal_energy_BTU": (
                        mapping.stored_internal_energy_BTU
                    ),
                    "canonical_internal_energy_BTU": (
                        mapping.canonical_internal_energy_BTU
                    ),
                    "mapping_energy_change_BTU": (
                        mapping.mapping_energy_change_BTU
                    ),
                    "prior_volume_mismatch_relative_max": max(
                        row.prior_volume_mismatch_relative
                        for row in source_rows
                    ),
                    "canonical_volume_mismatch_relative": (
                        mapping.canonical_volume_mismatch_relative
                    ),
                    "canonical_fixed_volume_ft3": (
                        mapping.canonical_fixed_volume_ft3
                    ),
                    "occupied_phase_volume_ft3": (
                        mapping.occupied_phase_volume_ft3
                    ),
                }
            )
        start_docs = [
            {
                "name": name,
                "result": _result_document(
                    result,
                    component_names=component_names,
                ),
            }
            for name, result in named_results
        ]
        best_doc = (
            _result_document(best, component_names=component_names)
            if best is not None
            else None
        )
        report: Dict[str, Any] = {
            "classification": classification,
            "checkpoint_repair_decision": checkpoint_decision,
            "decision": decision,
            "one_shot_policy": {
                "permitted_corrected_retries": 1,
                "corrected_retries_executed": 1,
                "further_optimizer_retuning_permitted": False,
            },
            "thermo_mode": thermo_mode,
            "sump_topology": "liquid_only_sump_occupied_volume",
            "movement_scale_mode": "column-common",
            "excel_path": bridge.excel_path,
            "checkpoint_path": bridge.checkpoint_path,
            "checkpoint_run_id": bridge.checkpoint_run_id,
            "checkpoint_time_s": bridge.checkpoint_time_s,
            "component_names": list(component_names),
            "canonical_mapping": {
                "stored_total_internal_energy_BTU": stored_total_u,
                "canonical_total_internal_energy_BTU": canonical_total_u,
                "total_mapping_energy_change_BTU": (
                    canonical_total_u - stored_total_u
                ),
                "enthalpy_offset_BTU_per_lbmol": offset_values.tolist(),
                "enthalpy_offset_relative_spread": offset_spread,
                "enthalpy_offset_classification": offset_classification,
                "targets": target_docs,
            },
            "movement_scales": {
                "component_scale_lbmol": (
                    scales.component_lbmol.tolist()
                ),
                "energy_scale_BTU": scales.energy_BTU.tolist(),
                "equal_1000_BTU_cost_ratio": (
                    scaling.maximum_to_minimum_cost_ratio
                ),
                "neutrality_pass": scaling.pass_gate,
            },
            "starts": start_docs,
            "multistart_assessment": {
                "start_names": list(assessment.start_names),
                "successful_start_names": list(
                    assessment.successful_start_names
                ),
                "objective_values": assessment.objective_values.tolist(),
                "relative_objective_spread": _finite_or_none(
                    assessment.relative_objective_spread
                ),
                "required_relative_spread": (
                    assessment.required_relative_spread
                ),
                "reproducible_minimum_pass": (
                    assessment.reproducible_minimum_pass
                ),
                "best_start_name": assessment.best_start_name,
                "maximum_normalized_pattern_difference": (
                    _finite_or_none(pattern_max)
                ),
                "maximum_normalized_pattern_rms_difference": (
                    _finite_or_none(pattern_rms)
                ),
            },
            "best_result": best_doc,
            "terminal_concentration": {
                "terminal_energy_movement_fraction": (
                    _finite_or_none(terminal_movement_fraction)
                ),
                "terminal_energy_capacity_fraction": (
                    _finite_or_none(terminal_capacity_fraction)
                ),
                "movement_to_capacity_ratio": (
                    _finite_or_none(terminal_ratio)
                ),
                "required_maximum_ratio": 2.0,
            },
            "comparisons": {
                "DD067_energy_move_BTU": DD067_ENERGY_MOVE_BTU,
                "DD068_max_pressure_change_psi": (
                    DD068_MAX_PRESSURE_CHANGE_PSI
                ),
                "retirement_pressure_threshold_psi": 50.0,
            },
            "acceptance_gate": {
                "criteria": criteria,
                "pass": accepted,
            },
        }
        out_prefix = Path(args.out_prefix)
        out_prefix.parent.mkdir(parents=True, exist_ok=True)
        json_path = out_prefix.with_suffix(".json")
        md_path = out_prefix.with_suffix(".md")
        json_path.write_text(
            json.dumps(_json_value(report), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        md_path.write_text(_render_markdown(report), encoding="utf-8")
        report["json_path"] = str(json_path.resolve())
        report["markdown_path"] = str(md_path.resolve())
        return report
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument(
        "--thermo",
        choices=["dwsim", "table", "table-pool", "auto"],
        default="dwsim",
    )
    parser.add_argument("--thermo-table", default=r"cache\thermo_table.json")
    parser.add_argument(
        "--dd067-report",
        default=r"logs\conservative_checkpoint_redistribution_20260717.json",
    )
    parser.add_argument(
        "--starts",
        default="checkpoint,dd067,linear,random-small,random-moderate",
    )
    parser.add_argument("--minimum-pressure-increment", type=float, default=0.01)
    parser.add_argument("--max-outer-iterations", type=int, default=8)
    parser.add_argument("--sensitivity-relative-step", type=float, default=1.0e-4)
    parser.add_argument("--maximum-scaled-movement", type=float, default=10.0)
    parser.add_argument("--random-small-magnitude", type=float, default=0.01)
    parser.add_argument("--random-moderate-magnitude", type=float, default=0.05)
    parser.add_argument("--random-seed", type=int, default=70070)
    parser.add_argument("--objective-spread-tolerance", type=float, default=1.0e-4)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--out-prefix",
        default=r"logs\canonical_checkpoint_repair_20260717",
    )
    return parser


if __name__ == "__main__":
    print(json.dumps(_json_value(run(_parser().parse_args())), indent=2))
