#!/usr/bin/env python
"""Audit a runtime checkpoint against frozen UV and hydraulic closure gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    build_frozen_checkpoint_bridge,
    classify_frozen_closure,
    run_hydraulic_closure_audit,
    run_local_closure_audit,
    run_terminal_closure_audit,
)
from dynamic_distillation.uv_flash_sandbox_v1 import _build_provider


def _as_json_number(value: float) -> float | None:
    return float(value) if np.isfinite(float(value)) else None


def _format_optional(value: float | None) -> str:
    return "not run" if value is None else f"{float(value):.6g}"


def _render_markdown(report: Dict[str, Any]) -> str:
    local = report["local_closure"]
    hydraulic = report.get("hydraulic_closure")
    lines = [
        "# Frozen Checkpoint Closure Audit",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Checkpoint run: `{report['checkpoint_run_id']}` at `{report['checkpoint_time_s']:.6g} s`",
        f"- Thermo: `{report['thermo_mode']}`",
        f"- Terminal mapping complete: `{report['terminal_mapping_complete']}`",
        f"- Terminal algebraic coupling complete: `{report['terminal_coupling_complete']}`",
        "",
        "## Local UV Closure",
        "",
        "| Metric | Value | Gate |",
        "|---|---:|---:|",
        f"| All stages converged | {local['converged']} | True |",
        f"| Component reconstruction relative max | {local['component_relative_max']:.6g} | <1e-8 |",
        f"| Energy relative max | {local['energy_relative_max']:.6g} | <1e-7 |",
        f"| Volume relative max | {local['volume_relative_max']:.6g} | <1e-7 |",
        f"| Equilibrium beta residual max | {local['equilibrium_beta_max']:.6g} | <1e-6 |",
        f"| Negative phase count | {local['negative_phase_count']} | 0 |",
        f"| Solver projection count | {local['projection_count']} | 0 |",
        f"| Rejected/attempted projection count | {local['attempted_projection_count']} | diagnostic |",
        f"| Fugacity residual available | {local['fugacity_residual_available']} | True |",
        "",
        "The DWSIM provider protocol currently returns a TP-flash result but not phase fugacity "
        "coefficients. The beta/flash consistency result is reported, but the requested fugacity "
        "gate remains explicitly unverified.",
    ]
    if hydraulic is not None:
        lines.extend(
            [
                "",
                "## Column Hydraulic Closure",
                "",
                "| Metric | Value | Gate |",
                "|---|---:|---:|",
                f"| Nominal simultaneous solve converged | {hydraulic['converged']} | True |",
                f"| Liquid-flow scaled residual | {hydraulic['liquid_flow_scaled_residual']:.6g} | <1e-5 |",
                f"| Vapor/pressure-drop scaled residual | {hydraulic['vapor_flow_scaled_residual']:.6g} | <1e-5 |",
                f"| Local UV vs global pressure max, psi | {hydraulic['local_vs_global_pressure_max_psi']:.6g} | <0.1 |",
                f"| Active liquid profile/previous-flow limiters | {hydraulic['active_liquid_limiter_count']} | 0 |",
                f"| Active vapor profile/previous-flow limiters | {hydraulic['active_vapor_limiter_count']} | 0 |",
                f"| Solver projection count | {hydraulic['projection_count']} | 0 |",
                f"| Rejected/attempted projection count | {hydraulic['attempted_projection_count']} | diagnostic |",
                f"| +/-10% perturbations run | {hydraulic['perturbations_run']} | True |",
                f"| +/-10% pressure spread, psi | {_format_optional(hydraulic['perturbation_pressure_spread_max_psi'])} | <0.1 |",
                f"| +/-10% flow relative spread | {_format_optional(hydraulic['perturbation_flow_relative_spread_max'])} | <1e-4 |",
            ]
        )
    terminal = report["terminal_inventory"]
    lines.extend(
        [
            "",
            "## Terminal Conserved Inventory",
            "",
            "| Metric | Value | Gate |",
            "|---|---:|---:|",
            f"| All expected source blocks mapped | {terminal['accounting_complete']} | True |",
            f"| Component accounting max error, lbmol | {terminal['component_balance_abs_max_lbmol']:.6g} | numerical zero |",
            f"| Internal-energy accounting error, BTU | {terminal['energy_balance_abs_BTU']:.6g} | numerical zero |",
            f"| Algebraic coupling complete | {terminal['algebraic_coupling_complete']} | True |",
            "",
            "| Node | Topology role | Conserved | Inventory, lbmol | Volume, ft3 | T guess, F | P guess, psia |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for node in terminal["nodes"]:
        lines.append(
            f"| {node['node_id']} | {node['topology_role']} | "
            f"{node['conserved']} | {node['total_inventory_lbmol']:.6g} | "
            f"{node['fixed_total_volume_ft3']:.6g} | "
            f"{node['temperature_guess_F']:.6g} | {node['pressure_guess_psia']:.6g} |"
        )
    terminal_closure = report["terminal_closure"]
    lines.extend(
        [
            "",
            "## Terminal UV Assemblies",
            "",
            "| Metric | Value | Gate |",
            "|---|---:|---:|",
            f"| Both assemblies converged | {terminal_closure['converged']} | True |",
            f"| Component reconstruction relative max | {terminal_closure['component_relative_max']:.6g} | <1e-8 |",
            f"| Energy relative max | {terminal_closure['energy_relative_max']:.6g} | <1e-7 |",
            f"| Volume relative max | {terminal_closure['volume_relative_max']:.6g} | <1e-7 |",
            f"| Equilibrium beta residual max | {terminal_closure['equilibrium_beta_max']:.6g} | <1e-6 |",
            f"| Accepted projections | {terminal_closure['accepted_projection_count']} | 0 |",
            f"| Bottom minus top pressure, psi | {terminal_closure['bottom_minus_top_pressure_psi']:.6g} | >0 |",
            "",
            "| Assembly | T, F | P, psia | Vapor fraction |",
            "|---|---:|---:|---:|",
        ]
    )
    for assembly in terminal_closure["assemblies"]:
        lines.append(
            f"| {assembly['assembly_id']} | {assembly['T_F']:.6g} | "
            f"{assembly['P_psia']:.6g} | {assembly['beta_vapor']:.6g} |"
        )
    lines.extend(["", "## Mapping Notes", ""])
    lines.extend(f"- {note}" for note in report["mapping_notes"])
    lines.extend(
        [
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
    checkpoint = str(Path(args.checkpoint).resolve())
    col = build_column_spec_from_case(load_case_from_excel(excel))
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
            checkpoint_path=checkpoint,
            provider=provider,
        )
        local = run_local_closure_audit(bridge=bridge, provider=provider)
        terminal_closure = run_terminal_closure_audit(
            bridge=bridge,
            provider=provider,
        )
        hydraulic = None
        if not args.local_only:
            hydraulic = run_hydraulic_closure_audit(
                bridge=bridge,
                provider=provider,
                local=local,
                max_iter=args.max_iter,
                run_perturbations=not args.skip_perturbations,
            )
        classification = classify_frozen_closure(
            bridge=bridge,
            local=local,
            hydraulic=hydraulic,
        )
        if classification == "frozen_closure_passed":
            decision = "Proceed to a one-step implicit dynamic residual prototype."
        elif classification == "local_uv_failed":
            decision = (
                "Stop before hydraulic or production DAE work. Reconcile the checkpoint U mapping, "
                "fixed tray volume, or property interface."
            )
        elif classification == "terminal_inventory_mapped_algebraic_coupling_incomplete":
            decision = (
                "Terminal checkpoint inventory is fully accounted, but the four terminal conserved "
                "nodes must still be added to the simultaneous algebraic residual before a production "
                "DAE prototype can be accepted."
            )
        else:
            decision = (
                "Do not begin the production DAE rewrite. Local closure and global hydraulic closure "
                "are not yet both demonstrated under the strict gates."
            )
        report: Dict[str, Any] = {
            "classification": classification,
            "decision": decision,
            "thermo_mode": thermo_mode,
            "excel_path": bridge.excel_path,
            "checkpoint_path": bridge.checkpoint_path,
            "checkpoint_run_id": bridge.checkpoint_run_id,
            "checkpoint_time_s": bridge.checkpoint_time_s,
            "terminal_mapping_complete": bridge.terminal_mapping_complete,
            "terminal_coupling_complete": bridge.terminal_coupling_complete,
            "mapping_notes": list(bridge.mapping_notes),
            "terminal_inventory": {
                "accounting_complete": bridge.terminal_inventory_map.accounting_complete,
                "algebraic_coupling_complete": (
                    bridge.terminal_inventory_map.algebraic_coupling_complete
                ),
                "component_balance_abs_max_lbmol": (
                    bridge.terminal_inventory_map.component_balance_abs_max_lbmol
                ),
                "energy_balance_abs_BTU": (
                    bridge.terminal_inventory_map.energy_balance_abs_BTU
                ),
                "checkpoint_total_components_lbmol": (
                    bridge.terminal_inventory_map.checkpoint_total_components_lbmol.tolist()
                ),
                "mapped_total_components_lbmol": (
                    bridge.terminal_inventory_map.mapped_total_components_lbmol.tolist()
                ),
                "checkpoint_total_internal_energy_BTU": (
                    bridge.terminal_inventory_map.checkpoint_total_internal_energy_BTU
                ),
                "mapped_total_internal_energy_BTU": (
                    bridge.terminal_inventory_map.mapped_total_internal_energy_BTU
                ),
                "expected_source_blocks": list(
                    bridge.terminal_inventory_map.expected_source_blocks
                ),
                "mapped_source_blocks": list(
                    bridge.terminal_inventory_map.mapped_source_blocks
                ),
                "nodes": [
                    {
                        "node_id": node.node_id,
                        "topology_role": node.topology_role,
                        "source_blocks": list(node.source_blocks),
                        "conserved": node.conserved,
                        "total_inventory_lbmol": float(
                            np.sum(node.total_component_inventory_lbmol)
                        ),
                        "total_component_inventory_lbmol": (
                            node.total_component_inventory_lbmol.tolist()
                        ),
                        "total_internal_energy_BTU": node.total_internal_energy_BTU,
                        "fixed_total_volume_ft3": node.fixed_total_volume_ft3,
                        "liquid_inventory_lbmol": float(
                            np.sum(node.liquid_inventory_lbmol)
                        ),
                        "vapor_inventory_lbmol": float(
                            np.sum(node.vapor_inventory_lbmol)
                        ),
                        "temperature_guess_F": node.temperature_guess_F,
                        "pressure_guess_psia": node.pressure_guess_psia,
                    }
                    for node in bridge.terminal_inventory_map.nodes
                ],
            },
            "terminal_closure": {
                "converged": terminal_closure.converged,
                "strict_gate_pass": terminal_closure.strict_gate_pass,
                "component_relative_max": terminal_closure.component_relative_max,
                "energy_relative_max": terminal_closure.energy_relative_max,
                "volume_relative_max": terminal_closure.volume_relative_max,
                "equilibrium_beta_max": terminal_closure.equilibrium_beta_max,
                "accepted_projection_count": (
                    terminal_closure.accepted_projection_count
                ),
                "attempted_projection_count": (
                    terminal_closure.attempted_projection_count
                ),
                "bottom_minus_top_pressure_psi": (
                    terminal_closure.bottom_minus_top_pressure_psi
                ),
                "pressure_ordering_pass": terminal_closure.pressure_ordering_pass,
                "assemblies": [
                    {
                        "assembly_id": row.assembly_id,
                        "source_node_ids": list(row.source_node_ids),
                        "T_F": row.result.T_F,
                        "P_psia": row.result.P_psia,
                        "beta_vapor": row.result.beta_vapor,
                        "component_relative_residual": (
                            row.component_relative_residual
                        ),
                        "energy_relative_residual": row.energy_relative_residual,
                        "volume_relative_residual": row.volume_relative_residual,
                        "equilibrium_beta_residual": (
                            row.equilibrium_beta_residual
                        ),
                        "accepted_projection_count": (
                            row.result.accepted_projection_count
                        ),
                        "attempted_projection_count": row.result.projection_count,
                    }
                    for row in terminal_closure.assemblies
                ],
            },
            "local_closure": {
                "converged": local.converged,
                "strict_gate_pass": local.strict_gate_pass,
                "component_relative_max": local.component_relative_max,
                "energy_relative_max": local.energy_relative_max,
                "volume_relative_max": local.volume_relative_max,
                "equilibrium_beta_max": local.equilibrium_beta_max,
                "negative_phase_count": local.negative_phase_count,
                "projection_count": local.projection_count,
                "attempted_projection_count": local.attempted_projection_count,
                "fugacity_residual_available": local.fugacity_residual_available,
                "stages": [
                    {
                        "stage": row.stage_1based,
                        "converged": row.result.converged,
                        "iterations": row.result.iterations,
                        "T_F": row.result.T_F,
                        "P_psia": row.result.P_psia,
                        "beta_vapor": row.result.beta_vapor,
                        "component_relative_residual": row.component_relative_residual,
                        "energy_relative_residual": row.energy_relative_residual,
                        "volume_relative_residual": row.volume_relative_residual,
                        "equilibrium_beta_residual": row.equilibrium_beta_residual,
                        "projection_count": row.result.projection_count,
                        "accepted_projection_count": row.result.accepted_projection_count,
                    }
                    for row in local.stages
                ],
            },
        }
        if hydraulic is not None:
            report["hydraulic_closure"] = {
                "converged": hydraulic.nominal.converged,
                "failed": hydraulic.nominal.failed,
                "iterations": hydraulic.nominal.iterations,
                "strict_gate_pass": hydraulic.strict_gate_pass,
                "liquid_flow_scaled_residual": hydraulic.liquid_flow_scaled_residual,
                "vapor_flow_scaled_residual": hydraulic.vapor_flow_scaled_residual,
                "pressure_drop_scaled_residual": hydraulic.pressure_drop_scaled_residual,
                "local_vs_global_pressure_max_psi": hydraulic.local_vs_global_pressure_max_psi,
                "active_liquid_limiter_count": hydraulic.active_liquid_limiter_count,
                "active_vapor_limiter_count": hydraulic.active_vapor_limiter_count,
                "projection_count": hydraulic.projection_count,
                "attempted_projection_count": hydraulic.attempted_projection_count,
                "perturbations_run": hydraulic.perturbations_run,
                "perturbation_pressure_spread_max_psi": _as_json_number(
                    hydraulic.perturbation_pressure_spread_max_psi
                ),
                "perturbation_flow_relative_spread_max": _as_json_number(
                    hydraulic.perturbation_flow_relative_spread_max
                ),
                "perturbation_converged": [
                    bool(result.converged and not result.failed)
                    for result in hydraulic.perturbations
                ],
            }

        out_prefix = Path(args.out_prefix)
        out_prefix.parent.mkdir(parents=True, exist_ok=True)
        json_path = out_prefix.with_suffix(".json")
        md_path = out_prefix.with_suffix(".md")
        json_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
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
    parser.add_argument("--thermo", choices=["dwsim", "table", "table-pool", "auto"], default="dwsim")
    parser.add_argument("--thermo-table", default=r"cache\thermo_table.json")
    parser.add_argument("--max-iter", type=int, default=12)
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--skip-perturbations", action="store_true")
    parser.add_argument(
        "--out-prefix",
        default=r"logs\frozen_checkpoint_closure_20260717",
    )
    return parser


if __name__ == "__main__":
    result = run(_parser().parse_args())
    print(json.dumps(result, indent=2, default=_as_json_number))
