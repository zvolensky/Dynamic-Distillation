#!/usr/bin/env python
"""Run the DD-077 structural gate for the isolated equilibrium-DAE core."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v2.reduced_column_spec_v1 import (
    build_reduced_column_spec,
)
from dynamic_distillation.core_v2.reduced_residual_registry_v1 import (
    audit_conservation,
    audit_ownership,
    audit_structure,
    build_reduced_residual_registry,
)


def _render_markdown(report: dict) -> str:
    structure = report["structure"]
    ownership = report["ownership"]
    conservation = report["conservation"]
    return "\n".join(
        (
            "# DD-077 Core V2 Reduced Structural Registry",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Vapor-flow owner: `{report['vapor_flow_mode']}`",
            f"- Inventory volumes: `{report['inventory_volume_count']}`",
            f"- Components: `{report['component_count']}`",
            f"- Unknowns/residuals: `{structure['unknown_count']} / "
            f"{structure['residual_count']}`",
            f"- Structural rank/nullity: `{structure['structural_rank']} / "
            f"{structure['structural_nullity']}`",
            f"- Structure gate: `{structure['pass_gate']}`",
            f"- Ownership gate: `{ownership['pass_gate']}`",
            f"- Conservation gate: `{conservation['pass_gate']}`",
            "",
            "## Deliberate First-Layer Choices",
            "",
            "- pressure is prescribed data, not an unknown;",
            "- rectifying and stripping vapor rates are prescribed section parameters;",
            "- tray liquid outlets are owned only by Francis equations;",
            "- terminal liquid amounts are specified and D/B are solved;",
            "- the total condenser has no inventory volume;",
            "- the bottom is one combined reboiler/sump volume;",
            "- no imported profile enters a physical residual;",
            "- no controller, property call, nonlinear solve, or integration is present.",
            "",
            "## Authorization",
            "",
            report["authorization"],
            "",
        )
    )


def run(component_names: tuple[str, ...], out_prefix: Path) -> dict:
    spec = build_reduced_column_spec(component_names)
    registry = build_reduced_residual_registry(spec)
    structure = audit_structure(registry)
    ownership = audit_ownership(registry)
    conservation = audit_conservation(registry)
    passed = structure.pass_gate and ownership.pass_gate and conservation.pass_gate
    report = {
        "schema_id": "dd077-core-v2-reduced-structural-registry-v1",
        "classification": (
            "dd077_structural_gate_passed"
            if passed
            else "dd077_structural_gate_failed"
        ),
        "decision": (
            "authorize_source_equation_residual_evaluator"
            if passed
            else "stop_before_residual_evaluation"
        ),
        "authorization": (
            "Implement the property-free Gate A source-equation residual "
            "comparison next. Live DWSIM, nonlinear solves, and dynamic "
            "integration remain unauthorized."
            if passed
            else
            "Stop core-v2 implementation and correct topology, ownership, "
            "or equation assembly before adding numerical physics."
        ),
        "component_names": list(spec.component_names),
        "component_count": len(spec.component_names),
        "inventory_volume_count": len(spec.topology.control_volumes),
        "control_volume_roles": [
            volume.role for volume in spec.topology.control_volumes
        ],
        "vapor_flow_mode": spec.vapor_flow_mode,
        "pressure_parameters": list(spec.pressure_parameters),
        "vapor_flow_parameters": list(spec.vapor_flow_parameters),
        "terminal_product_unknowns": list(spec.terminal_product_unknowns),
        "terminal_level_parameters": list(spec.terminal_level_parameters),
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "live_property_evaluation_attempted": False,
        "structure": asdict(structure),
        "ownership": asdict(ownership),
        "conservation": asdict(conservation),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(
        _render_markdown(report), encoding="utf-8"
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--components",
        nargs="+",
        default=("Propane", "n-Butane", "n-Pentane"),
    )
    parser.add_argument(
        "--out-prefix",
        type=Path,
        default=Path("logs/dd077_core_v2_structural_audit_20260718"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(tuple(args.components), args.out_prefix)
    print(json.dumps(result, indent=2))
    raise SystemExit(
        0
        if result["classification"] == "dd077_structural_gate_passed"
        else 2
    )
