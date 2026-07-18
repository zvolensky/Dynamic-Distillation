#!/usr/bin/env python
"""Run the DD-069 terminal/interior energy, volume, and scaling audit."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    build_energy_only_targets,
)
from dynamic_distillation.dynamic_run_scaffold_v1 import read_native_checkpoint
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    _array_or_default,
    _layout_from_checkpoint,
    _scalar_array,
    build_frozen_checkpoint_bridge,
    run_local_closure_audit,
    run_terminal_closure_audit,
)
from dynamic_distillation.least_movement_redistribution_v1 import (
    build_movement_scales,
)
from dynamic_distillation.terminal_energy_volume_audit_v1 import (
    EnergyVolumeRegionInput,
    audit_empty_placeholder_invariance,
    audit_energy_scaling,
    audit_energy_volume_region,
)
from dynamic_distillation.uv_flash_sandbox_v1 import _build_provider
from dynamic_distillation.uv_flash_stage_v1 import BTU_PER_PSI_FT3


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


def _region_document(row) -> Dict[str, Any]:
    return _json_value(asdict(row))


def _selected_control_stages(bridge, arrays: Dict[str, np.ndarray]) -> tuple[int, ...]:
    active = tuple(int(value) for value in bridge.spec.active_stage1)
    feed_default = (
        active[int(bridge.spec.feed_term.stage_active_idx)]
        if bridge.spec.feed_term is not None
        else active[len(active) // 2]
    )
    feed_stage = int(
        round(
            _scalar_array(
                arrays,
                "diag__feed_stage_1based",
                float(feed_default),
            )
        )
    )
    selected = (active[0], feed_stage, active[-1])
    return tuple(dict.fromkeys(stage for stage in selected if stage in active))


def _render_markdown(report: Dict[str, Any]) -> str:
    tests = report["falsification_tests"]
    lines = [
        "# DD-069 Terminal Energy, Volume, and Basis Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Checkpoint: `{report['checkpoint_run_id']}` at `{report['checkpoint_time_s']:.6g} s`",
        f"- Thermo: `{report['thermo_mode']}`",
        f"- Decision: {report['decision']}",
        "",
        "## Falsification Tests",
        "",
        "| Test | Pass | Evidence |",
        "|---|---:|---|",
        f"| A: H/U/PV round trip | {tests['A_enthalpy_internal_energy_round_trip']['pass']} | max relative error `{tests['A_enthalpy_internal_energy_round_trip']['maximum_relative_error']:.6g}` |",
        f"| B: fixed-volume reconstruction | {tests['B_volume_reconstruction']['pass']} | max relative error `{tests['B_volume_reconstruction']['maximum_relative_error']:.6g}` |",
        f"| C: phase aggregation and mapped-U basis | {tests['C_phase_aggregation']['pass']} | max phase error `{tests['C_phase_aggregation']['maximum_phase_relative_error']:.6g}`; max mapped-U error `{tests['C_phase_aggregation']['maximum_mapped_u_relative_error']:.6g}` |",
        f"| D: empty condenser placeholder invariance | {tests['D_empty_total_condenser_invariance']['pass']} | raw H `{tests['D_empty_total_condenser_invariance']['raw_stored_enthalpy_abs_BTU']:.6g} BTU`; mapped V `{tests['D_empty_total_condenser_invariance']['mapped_volume_abs_ft3']:.6g} ft3` |",
        f"| E: normalized-energy scaling neutrality | {tests['E_scaling_neutrality']['pass']} | max/min cost ratio `{tests['E_scaling_neutrality']['maximum_to_minimum_cost_ratio']:.6g}` |",
        "",
        "## Energy And Volume Reconstruction",
        "",
        "| Region | Category | Stored H, BTU | Reconstructed H, BTU | Fixed PV, BTU | Mapped U, BTU | Reconstructed phase U, BTU | Fixed V, ft3 | Phase V, ft3 | V rel error | H rel error |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["regions"]:
        stored_h = (
            "N/A"
            if row["stored_enthalpy_BTU"] is None
            else f"{row['stored_enthalpy_BTU']:.6g}"
        )
        h_error = (
            "N/A"
            if row["stored_vs_reconstructed_enthalpy_relative"] is None
            else f"{row['stored_vs_reconstructed_enthalpy_relative']:.6g}"
        )
        lines.append(
            f"| {row['region_id']} | {row['category']} | {stored_h} | "
            f"{row['reconstructed_enthalpy_BTU']:.6g} | "
            f"{row['fixed_volume_pv_BTU']:.6g} | "
            f"{row['mapped_internal_energy_BTU']:.6g} | "
            f"{row['phase_sum_internal_energy_BTU']:.6g} | "
            f"{row['fixed_total_volume_ft3']:.6g} | "
            f"{row['reconstructed_total_volume_ft3']:.6g} | "
            f"{row['volume_reconstruction_relative']:.6g} | {h_error} |"
        )
    lines.extend(
        [
            "",
            "## Energy Scaling",
            "",
            f"A `{report['scaling']['test_move_BTU']:.6g} BTU` move is priced with the DD-068 normalized L2 scale.",
            "",
            "| Node | Category | Inventory, lbmol | Energy scale, BTU | Normalized cost | Cost / median interior |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    selected_ids = set(report["scaling"]["reported_node_ids"])
    for row in report["scaling"]["rows"]:
        if row["node_id"] not in selected_ids:
            continue
        lines.append(
            f"| {row['node_id']} | {row['category']} | "
            f"{row['total_inventory_lbmol']:.6g} | "
            f"{row['energy_scale_BTU']:.6g} | "
            f"{row['normalized_l2_cost_for_test_move']:.6g} | "
            f"{row['cost_relative_to_median_interior']:.6g} |"
        )
    lines.extend(
        [
            "",
            "## Basis Contract",
            "",
            f"- PV conversion: `{report['basis_contract']['BTU_per_psia_ft3']:.12g} BTU/(psia ft3)`.",
            "- Pressure is absolute psia; volume is ft3; enthalpy and internal energy are BTU.",
            "- All property reconstructions use the same runtime provider and component ordering.",
            "- Interior and terminal-stage stored H comes from checkpoint EL+EV.",
            "- Drum and sump boundary H/U is property-reconstructed because the checkpoint layout has no boundary energy state.",
            "",
            "## Decision",
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
        targets = build_energy_only_targets(
            bridge=bridge,
            local=local,
            terminal=terminal,
        )
        scales = build_movement_scales(targets)
        node_by_id = {
            str(node.node_id): node
            for node in bridge.terminal_inventory_map.nodes
        }

        tray_l = np.asarray(unpacked["tray_L"], dtype=float)
        tray_v = np.asarray(unpacked["tray_V"], dtype=float)
        tray_el = np.asarray(unpacked["tray_EL_BTU"], dtype=float)
        tray_ev = np.asarray(unpacked["tray_EV_BTU"], dtype=float)
        control_stages = _selected_control_stages(bridge, arrays)
        region_inputs = []

        for node_id in ("reflux_drum", "reboiler_stage", "bottoms_sump"):
            node = node_by_id[node_id]
            if node_id == "reboiler_stage":
                stored_h = float(tray_el[-1] + tray_ev[-1])
                basis = "stored_enthalpy_minus_fixed_pv"
            else:
                stored_h = None
                basis = "phase_property_sum"
            region_inputs.append(
                EnergyVolumeRegionInput(
                    region_id=node_id,
                    category="terminal_equipment",
                    source_blocks=tuple(node.source_blocks),
                    temperature_F=float(node.temperature_guess_F),
                    pressure_psia=float(node.pressure_guess_psia),
                    liquid_inventory_lbmol=np.asarray(
                        node.liquid_inventory_lbmol,
                        dtype=float,
                    ),
                    vapor_inventory_lbmol=np.asarray(
                        node.vapor_inventory_lbmol,
                        dtype=float,
                    ),
                    fixed_total_volume_ft3=float(
                        node.fixed_total_volume_ft3
                    ),
                    mapped_internal_energy_BTU=float(
                        node.total_internal_energy_BTU
                    ),
                    mapped_energy_basis=basis,
                    stored_enthalpy_BTU=stored_h,
                )
            )

        active_stage_to_index = {
            int(stage): idx
            for idx, stage in enumerate(bridge.spec.active_stage1)
        }
        for stage_1based in control_stages:
            stage0 = int(stage_1based) - 1
            active_idx = active_stage_to_index[int(stage_1based)]
            region_inputs.append(
                EnergyVolumeRegionInput(
                    region_id=f"tray_{stage_1based}",
                    category="interior_control",
                    source_blocks=(f"tray_stage_{stage_1based}",),
                    temperature_F=float(temperature_full[stage0]),
                    pressure_psia=float(pressure_full[stage0]),
                    liquid_inventory_lbmol=tray_l[stage0, :].copy(),
                    vapor_inventory_lbmol=tray_v[stage0, :].copy(),
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
            )

        region_rows = tuple(
            audit_energy_volume_region(provider=provider, region=region)
            for region in region_inputs
        )
        condenser_node = node_by_id["condenser_stage"]
        placeholder = audit_empty_placeholder_invariance(
            region_id="condenser_stage",
            raw_component_inventory_lbmol=(
                tray_l[0, :] + tray_v[0, :]
            ),
            raw_stored_enthalpy_BTU=float(tray_el[0] + tray_ev[0]),
            mapped_internal_energy_BTU=float(
                condenser_node.total_internal_energy_BTU
            ),
            mapped_volume_ft3=float(condenser_node.fixed_total_volume_ft3),
        )
        scaling = audit_energy_scaling(
            targets=targets,
            scales=scales,
            test_move_BTU=float(args.scaling_test_move_BTU),
            neutrality_cost_ratio_limit=float(args.scaling_cost_ratio_limit),
        )

        round_trip_max = max(
            row.enthalpy_round_trip_relative for row in region_rows
        )
        volume_max = max(
            row.volume_reconstruction_relative for row in region_rows
        )
        phase_max = max(
            row.phase_aggregation_relative for row in region_rows
        )
        mapped_u_max = max(
            row.mapped_vs_expected_internal_energy_relative
            for row in region_rows
        )
        stored_h_rows = [
            row
            for row in region_rows
            if row.stored_vs_reconstructed_enthalpy_relative is not None
        ]
        stored_h_max = max(
            (
                float(row.stored_vs_reconstructed_enthalpy_relative)
                for row in stored_h_rows
            ),
            default=0.0,
        )
        test_a_pass = all(row.enthalpy_round_trip_pass for row in region_rows)
        test_b_pass = all(
            row.volume_reconstruction_pass for row in region_rows
        )
        test_c_pass = all(
            row.phase_aggregation_pass
            and row.mapped_internal_energy_basis_pass
            and row.stored_enthalpy_basis_pass
            for row in region_rows
        )
        terminal_rows = [
            row for row in region_rows if row.category == "terminal_equipment"
        ]
        interior_rows = [
            row for row in region_rows if row.category == "interior_control"
        ]
        terminal_basis_volume_pass = all(
            row.volume_reconstruction_pass
            and row.phase_aggregation_pass
            and row.mapped_internal_energy_basis_pass
            and row.stored_enthalpy_basis_pass
            for row in terminal_rows
        )
        interior_control_pass = all(
            row.volume_reconstruction_pass
            and row.phase_aggregation_pass
            and row.mapped_internal_energy_basis_pass
            and row.stored_enthalpy_basis_pass
            for row in interior_rows
        )

        failed_reasons = []
        if not terminal_basis_volume_pass:
            failed_reasons.append(
                "one or more terminal energy/volume basis checks fail"
            )
        if not interior_control_pass:
            failed_reasons.append(
                "one or more representative interior controls fail"
            )
        if not placeholder.pass_gate:
            failed_reasons.append(
                "the empty condenser placeholder is not invariant"
            )
        if not scaling.pass_gate:
            failed_reasons.append(
                "DD-068 local energy scaling is not neutral"
            )

        if not terminal_basis_volume_pass or not placeholder.pass_gate:
            classification = "dd069_terminal_basis_or_volume_defect_found"
            decision = (
                "Checkpoint repair remains paused. Correct the concrete terminal "
                "energy/volume mapping defects and the DD-068 scaling bias, then "
                "repeat DD-067/DD-068 before any hydraulic work."
            )
        elif not scaling.pass_gate:
            classification = "dd069_redistribution_scaling_defect_found"
            decision = (
                "Checkpoint repair remains paused. Replace the terminal-biased "
                "energy normalization, then repeat DD-068 before deciding whether "
                "the checkpoint itself is impractical."
            )
        else:
            classification = "dd069_checkpoint_repair_retired"
            decision = (
                "The terminal basis and scaling audit is clean. Retire checkpoint "
                "projection and formulate the direct conserved steady-state solve "
                "from operating specifications."
            )
        if failed_reasons:
            decision += " Failed checks: " + "; ".join(failed_reasons) + "."

        scaling_doc = _json_value(asdict(scaling))
        report_ids = {
            "top_terminal",
            "bottom_terminal",
            *(f"tray_{stage}" for stage in control_stages),
        }
        scaling_doc["reported_node_ids"] = sorted(report_ids)
        report: Dict[str, Any] = {
            "classification": classification,
            "decision": decision,
            "thermo_mode": thermo_mode,
            "excel_path": bridge.excel_path,
            "checkpoint_path": bridge.checkpoint_path,
            "checkpoint_run_id": bridge.checkpoint_run_id,
            "checkpoint_time_s": bridge.checkpoint_time_s,
            "component_names": list(bridge.spec.component_names),
            "control_stages_1based": list(control_stages),
            "basis_contract": {
                "pressure_unit": "psia",
                "volume_unit": "ft3",
                "enthalpy_unit": "BTU",
                "internal_energy_unit": "BTU",
                "temperature_property_unit": "F",
                "absolute_temperature_conversion": "T_R = T_F + 459.67",
                "BTU_per_psia_ft3": BTU_PER_PSI_FT3,
                "provider_common_to_all_regions": True,
                "component_order_common_to_all_regions": list(
                    bridge.spec.component_names
                ),
                "boundary_energy_state_present": False,
            },
            "regions": [_region_document(row) for row in region_rows],
            "placeholder_invariance": _json_value(asdict(placeholder)),
            "scaling": scaling_doc,
            "falsification_tests": {
                "A_enthalpy_internal_energy_round_trip": {
                    "pass": test_a_pass,
                    "required_relative_tolerance": 1.0e-10,
                    "maximum_relative_error": round_trip_max,
                },
                "B_volume_reconstruction": {
                    "pass": test_b_pass,
                    "required_relative_tolerance": 1.0e-8,
                    "maximum_relative_error": volume_max,
                    "terminal_pass": terminal_basis_volume_pass,
                    "interior_control_pass": interior_control_pass,
                },
                "C_phase_aggregation": {
                    "pass": test_c_pass,
                    "required_phase_relative_tolerance": 1.0e-10,
                    "required_stored_h_relative_tolerance": 1.0e-6,
                    "required_mapped_u_relative_tolerance": 1.0e-10,
                    "maximum_phase_relative_error": phase_max,
                    "maximum_stored_h_relative_error": stored_h_max,
                    "maximum_mapped_u_relative_error": mapped_u_max,
                },
                "D_empty_total_condenser_invariance": {
                    **_json_value(asdict(placeholder)),
                    "pass": placeholder.pass_gate,
                },
                "E_scaling_neutrality": {
                    "pass": scaling.pass_gate,
                    "test_move_BTU": scaling.test_move_BTU,
                    "cost_ratio_limit": scaling.neutrality_cost_ratio_limit,
                    "maximum_to_minimum_cost_ratio": (
                        scaling.maximum_to_minimum_cost_ratio
                    ),
                    "terminal_to_interior_cost_ratio_min": (
                        scaling.terminal_to_interior_cost_ratio_min
                    ),
                    "terminal_to_interior_cost_ratio_max": (
                        scaling.terminal_to_interior_cost_ratio_max
                    ),
                },
            },
            "go_gate": {
                "terminal_basis_volume_pass": terminal_basis_volume_pass,
                "interior_controls_pass": interior_control_pass,
                "placeholder_invariance_pass": placeholder.pass_gate,
                "scaling_neutrality_pass": scaling.pass_gate,
                "repeat_dd068_after_concrete_fix": bool(
                    not terminal_basis_volume_pass
                    or not placeholder.pass_gate
                    or not scaling.pass_gate
                ),
                "retire_checkpoint_repair": bool(
                    terminal_basis_volume_pass
                    and placeholder.pass_gate
                    and scaling.pass_gate
                ),
            },
        }
        out_prefix = Path(args.out_prefix)
        out_prefix.parent.mkdir(parents=True, exist_ok=True)
        json_path = out_prefix.with_suffix(".json")
        md_path = out_prefix.with_suffix(".md")
        json_path.write_text(
            json.dumps(report, indent=2, allow_nan=False),
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
    parser.add_argument(
        "--thermo-table",
        default=r"cache\thermo_table.json",
    )
    parser.add_argument(
        "--scaling-test-move-BTU",
        type=float,
        default=1000.0,
    )
    parser.add_argument(
        "--scaling-cost-ratio-limit",
        type=float,
        default=10.0,
    )
    parser.add_argument(
        "--out-prefix",
        default=r"logs\terminal_energy_volume_basis_audit_20260717",
    )
    return parser


if __name__ == "__main__":
    print(json.dumps(run(_parser().parse_args()), indent=2))
