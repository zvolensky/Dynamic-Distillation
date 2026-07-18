#!/usr/bin/env python
"""Audit the DD-071 direct steady-state registry before residual implementation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case
from dynamic_distillation.direct_steady_state_registry_v1 import (
    audit_registry_structure,
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel


def _render_markdown(report: dict) -> str:
    proposed = report["proposed_separate_topology_audit"]
    audit = report["selected_topology_audit"]
    lines = [
        "# DD-071 Direct Conserved Steady-State Registry",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Decision: `{report['decision_code']}`",
        f"- Unknowns: `{audit['unknown_count']}`",
        f"- Residuals: `{audit['residual_count']}`",
        f"- Difference: `{audit['equation_count_difference']}`",
        f"- Structural rank upper bound: `{audit['structural_rank']}`",
        f"- Structural nullity lower bound: `{audit['structural_nullity']}`",
        f"- Selected topology: `{report['selected_bottom_topology']}`",
        "",
        "## Unknown Counts",
        "",
        "| Block | Count |",
        "|---|---:|",
    ]
    for name, count in audit["unknown_counts_by_block"].items():
        lines.append(f"| {name} | {count} |")
    lines.extend(["", "## Residual Counts", "", "| Block | Count |", "|---|---:|"])
    for name, count in audit["residual_counts_by_block"].items():
        lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "## Ownership Failure",
            "",
            "The proposed topology contains separate conserved partial-reboiler "
            "and liquid-only sump states. Their connecting liquid outlet is an "
            "unknown, but no hydraulic, valve, overflow, residence-time, or "
            "level relation owns it.",
            "",
        ]
    )
    for name in proposed["missing_closure_owners"]:
        lines.append(f"- Unowned unknown: `{name}`")
    lines.extend(
        [
            "",
            "The selected correction combines reboiler vapor and sump liquid "
            "inside one conserved bottom control volume. The internal liquid "
            "transfer then crosses no control-volume boundary and is eliminated "
            "without adding an arbitrary equation.",
            "",
            "## Selected Structure",
            "",
            f"- Unknowns: `{audit['unknown_count']}`",
            f"- Residuals: `{audit['residual_count']}`",
            f"- Structural rank: `{audit['structural_rank']}`",
            f"- Structural nullity: `{audit['structural_nullity']}`",
            f"- Structure gate: `{audit['pass_gate']}`",
            "",
            "## Deferred Deliverables",
            "",
            "This structural registry slice does not yet contain numerical "
            "property and balance evaluation. "
            "ChemSep, checkpoint, and perturbed residual vectors, numerical "
            "Jacobian rank, and nonlinear-solver work remain deferred to the "
            "next DD-071 implementation slice.",
            "",
            "## Decision",
            "",
            report["decision"],
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict:
    col = build_column_spec_from_case(load_case_from_excel(args.excel))
    active_stages = tuple(
        int(stage)
        for stage in col.stage_1based
        if int(stage) not in (int(col.stage_1based[0]), int(col.stage_1based[-1]))
    )
    registry = build_direct_steady_state_registry(
        component_names=tuple(str(name) for name in col.components_excel),
        active_stage_ids=active_stages,
    )
    proposed_audit = audit_registry_structure(registry)
    selected_registry = combine_reboiler_and_sump_registry(registry)
    audit = audit_registry_structure(selected_registry)
    classification = (
        "dd071_registry_structure_passed_combined_bottom"
        if audit.pass_gate
        else "dd071_stopped_equation_count_and_ownership"
    )
    decision_code = (
        "authorize_numeric_residual_evaluator"
        if audit.pass_gate
        else "resolve_terminal_liquid_outlet_ownership_before_residual_evaluator"
    )
    decision = (
        (
            "The combined bottom control-volume registry is square and "
            "structurally full rank. Implement numerical residual evaluation "
            "next; a nonlinear solve remains unauthorized."
        )
        if audit.pass_gate
        else (
            "Stop DD-071 before numerical residual or solver work. Select a "
            "physical partial-reboiler/sump topology that either combines the "
            "inventories or supplies a justified reboiler liquid-outlet relation. "
            "Do not invent a tuning equation to close the count."
        )
    )
    report = {
        "classification": classification,
        "decision_code": decision_code,
        "decision": decision,
        "excel_path": str(Path(args.excel).resolve()),
        "component_names": list(registry.component_names),
        "active_stage_ids": list(registry.active_stage_ids),
        "topology": {
            "total_condenser_placeholder": "eliminated",
            "reflux_drum": "separate_two_phase_conserved_node",
            "active_trays": "generic_two_phase_conserved_nodes",
            "partial_reboiler": "separate_two_phase_conserved_node",
            "bottoms_sump": "separate_liquid_only_conserved_node",
        },
        "selected_bottom_topology": (
            "combined_reboiler_vapor_and_sump_liquid_control_volume"
        ),
        "operating_pairs": {
            "drum_level": "D",
            "sump_level": "B",
            "top_pressure": "Q_C",
            "bottoms_propane": "Q_R",
        },
        "deliberate_eliminations": list(selected_registry.deliberate_eliminations),
        "proposed_separate_topology_audit": {
            "unknown_count": proposed_audit.unknown_count,
            "residual_count": proposed_audit.residual_count,
            "equation_count_difference": proposed_audit.equation_count_difference,
            "square": proposed_audit.square,
            "structural_rank": proposed_audit.structural_rank,
            "structural_nullity": proposed_audit.structural_nullity,
            "missing_closure_owners": list(
                proposed_audit.missing_closure_owners
            ),
            "pass_gate": proposed_audit.pass_gate,
        },
        "selected_topology_audit": {
            "unknown_count": audit.unknown_count,
            "residual_count": audit.residual_count,
            "equation_count_difference": audit.equation_count_difference,
            "square": audit.square,
            "structural_rank": audit.structural_rank,
            "structural_nullity": audit.structural_nullity,
            "structurally_empty_rows": list(audit.structurally_empty_rows),
            "structurally_empty_columns": list(audit.structurally_empty_columns),
            "unmatched_unknowns": list(audit.unmatched_unknowns),
            "unmatched_residuals": list(audit.unmatched_residuals),
            "missing_closure_owners": list(audit.missing_closure_owners),
            "duplicate_unknown_names": list(audit.duplicate_unknown_names),
            "duplicate_residual_names": list(audit.duplicate_residual_names),
            "unknown_counts_by_block": audit.unknown_counts_by_block,
            "residual_counts_by_block": audit.residual_counts_by_block,
            "pass_gate": audit.pass_gate,
        },
        "numeric_evaluations": {
            "status": "not_run_structural_registry_slice_only",
            "chemsep_guess": None,
            "checkpoint_guess": None,
            "perturbed_guess": None,
        },
        "nonlinear_solve_attempted": False,
    }
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_prefix.with_suffix(".json")
    markdown_path = out_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", required=True)
    parser.add_argument(
        "--out-prefix",
        default=r"logs\direct_steady_state_registry_20260718",
    )
    return parser


if __name__ == "__main__":
    print(json.dumps(run(_parser().parse_args()), indent=2))
