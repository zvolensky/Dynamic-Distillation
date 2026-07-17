#!/usr/bin/env python
"""Probe conservative energy redistribution under ordered checkpoint pressure."""

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
from dynamic_distillation.conservative_checkpoint_redistribution_v1 import (
    build_energy_only_targets,
    solve_energy_only_pressure_ordering,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel
from dynamic_distillation.frozen_checkpoint_closure_v1 import (
    build_frozen_checkpoint_bridge,
    run_local_closure_audit,
    run_terminal_closure_audit,
)
from dynamic_distillation.uv_flash_sandbox_v1 import _build_provider


def _render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Conservative Checkpoint Redistribution Probe",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Limited feasibility pass: `{report['pressure_energy_feasibility_pass']}`",
        f"- Checkpoint: `{report['checkpoint_run_id']}` at `{report['checkpoint_time_s']:.6g} s`",
        f"- Thermo: `{report['thermo_mode']}`",
        "",
        "## Scope",
        "",
        "This first feasibility layer keeps every node component inventory and fixed "
        "volume unchanged. It imposes ordered pressure and redistributes only internal "
        "energy under exact whole-column energy conservation. Hydraulic equations are "
        "not included, so a pass is not production-model acceptance.",
        "",
        "## Conservation And Movement",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Component conservation max error, lbmol | {report['component_conservation_abs_max_lbmol']:.6g} |",
        f"| Total energy error, BTU | {report['total_internal_energy_error_BTU']:.6g} |",
        f"| Total energy relative error | {report['total_internal_energy_relative_error']:.6g} |",
        f"| Energy moved, BTU | {report['energy_moved_BTU']:.6g} |",
        f"| Energy L1 change, BTU | {report['energy_l1_change_BTU']:.6g} |",
        f"| Energy L1 fraction of inventory | {report['energy_l1_fraction_of_inventory']:.6g} |",
        f"| Maximum node energy change, BTU | {report['maximum_node_energy_change_BTU']:.6g} |",
        f"| Maximum node specific-energy change, BTU/lbmol | {report['maximum_node_specific_energy_change_BTU_lbmol']:.6g} |",
        f"| Maximum pressure change, psi | {report['maximum_pressure_change_psi']:.6g} |",
        f"| Pressure RMS change, psi | {report['pressure_rms_change_psi']:.6g} |",
        f"| Maximum temperature change, F | {report['maximum_temperature_change_F']:.6g} |",
        f"| Temperature RMS change, F | {report['temperature_rms_change_F']:.6g} |",
        "",
        "## Pressure Result",
        "",
        f"- Uniform pressure shift: `{report['uniform_pressure_shift_psi']:.6g} psi`",
        f"- Required minimum increment: `{report['minimum_pressure_increment_psi']:.6g} psi/node`",
        f"- Ordered profile pass: `{report['pressure_ordering_pass']}`",
        f"- Energy root converged: `{report['root_converged']}`",
        f"- Profile evaluations: `{report['profile_evaluations']}`",
        "",
        "| Node | P initial, psia | P final, psia | T final, F | Vapor fraction | Delta U, BTU | Volume rel. residual | Beta residual |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["nodes"]:
        lines.append(
            f"| {row['node_id']} | {row['initial_pressure_psia']:.6g} | "
            f"{row['pressure_psia']:.6g} | {row['temperature_F']:.6g} | "
            f"{row['beta_vapor']:.6g} | {row['internal_energy_change_BTU']:.6g} | "
            f"{row['volume_relative_residual']:.6g} | "
            f"{row['equilibrium_beta_residual']:.6g} |"
        )
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
        terminal = run_terminal_closure_audit(bridge=bridge, provider=provider)
        targets = build_energy_only_targets(
            bridge=bridge,
            local=local,
            terminal=terminal,
        )
        result = solve_energy_only_pressure_ordering(
            provider=provider,
            targets=targets,
            minimum_pressure_increment_psi=args.minimum_pressure_increment,
        )
        if result.pressure_energy_feasibility_pass:
            decision = (
                "Energy redistribution alone can recover an ordered local UV pressure "
                "profile while preserving all component totals and whole-column energy. "
                "Assess the movement magnitude, then extend the sandbox to simultaneous "
                "component redistribution and an uncapped hydraulic residual."
            )
        else:
            decision = (
                "Energy-only redistribution does not establish feasibility. Do not enlarge "
                "the production solver; inspect the reported failed node/root behavior and "
                "reconcile volume, energy, or terminal ownership first."
            )
        target_by_id = {target.node_id: target for target in targets}
        report: Dict[str, Any] = {
            "classification": result.classification,
            "decision": decision,
            "pressure_energy_feasibility_pass": (
                result.pressure_energy_feasibility_pass
            ),
            "scope": "fixed component inventory; redistributed internal energy; no hydraulics",
            "thermo_mode": thermo_mode,
            "excel_path": bridge.excel_path,
            "checkpoint_path": bridge.checkpoint_path,
            "checkpoint_run_id": bridge.checkpoint_run_id,
            "checkpoint_time_s": bridge.checkpoint_time_s,
            "minimum_pressure_increment_psi": result.minimum_pressure_increment_psi,
            "uniform_pressure_shift_psi": result.uniform_pressure_shift_psi,
            "maximum_pressure_change_psi": (
                result.maximum_pressure_change_psi
            ),
            "pressure_rms_change_psi": result.pressure_rms_change_psi,
            "maximum_temperature_change_F": (
                result.maximum_temperature_change_F
            ),
            "temperature_rms_change_F": result.temperature_rms_change_F,
            "pressure_ordering_pass": result.pressure_ordering_pass,
            "all_node_closures_converged": result.all_node_closures_converged,
            "component_conservation_abs_max_lbmol": (
                result.component_conservation_abs_max_lbmol
            ),
            "total_internal_energy_before_BTU": (
                result.total_internal_energy_before_BTU
            ),
            "total_internal_energy_after_BTU": (
                result.total_internal_energy_after_BTU
            ),
            "total_internal_energy_error_BTU": (
                result.total_internal_energy_error_BTU
            ),
            "total_internal_energy_relative_error": (
                result.total_internal_energy_relative_error
            ),
            "energy_moved_BTU": result.energy_moved_BTU,
            "energy_l1_change_BTU": result.energy_l1_change_BTU,
            "energy_l1_fraction_of_inventory": (
                result.energy_l1_fraction_of_inventory
            ),
            "maximum_node_energy_change_BTU": (
                result.maximum_node_energy_change_BTU
            ),
            "maximum_node_specific_energy_change_BTU_lbmol": (
                result.maximum_node_specific_energy_change_BTU_lbmol
            ),
            "root_bracket_psi": (
                list(result.root_bracket_psi)
                if result.root_bracket_psi is not None
                else None
            ),
            "root_converged": result.root_converged,
            "profile_evaluations": result.profile_evaluations,
            "initial_pressure_psia": result.initial_pressure_psia.tolist(),
            "isotonic_pressure_psia": result.isotonic_pressure_psia.tolist(),
            "final_pressure_psia": result.final_pressure_psia.tolist(),
            "nodes": [
                {
                    "node_id": row.node_id,
                    "position_1based": row.position_1based,
                    "initial_pressure_psia": (
                        target_by_id[row.node_id].initial_pressure_psia
                    ),
                    "initial_temperature_F": (
                        target_by_id[row.node_id].initial_temperature_F
                    ),
                    "pressure_psia": row.pressure_psia,
                    "temperature_F": row.temperature_F,
                    "beta_vapor": row.beta_vapor,
                    "implied_internal_energy_BTU": (
                        row.implied_internal_energy_BTU
                    ),
                    "internal_energy_change_BTU": (
                        row.internal_energy_change_BTU
                    ),
                    "volume_relative_residual": row.volume_relative_residual,
                    "equilibrium_beta_residual": (
                        row.equilibrium_beta_residual
                    ),
                    "component_relative_residual": (
                        row.component_relative_residual
                    ),
                    "converged": row.converged,
                    "function_evaluations": row.function_evaluations,
                    "active_bound_count": row.active_bound_count,
                }
                for row in result.nodes
            ],
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
    parser.add_argument("--thermo-table", default=r"cache\thermo_table.json")
    parser.add_argument(
        "--minimum-pressure-increment",
        type=float,
        default=0.01,
    )
    parser.add_argument(
        "--out-prefix",
        default=r"logs\conservative_checkpoint_redistribution_20260717",
    )
    return parser


if __name__ == "__main__":
    print(json.dumps(run(_parser().parse_args()), indent=2))
