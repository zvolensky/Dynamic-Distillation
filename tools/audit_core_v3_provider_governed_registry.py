#!/usr/bin/env python
"""Run the structural-only DD-091 Core V3 architecture audit."""

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

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    ARCHITECTURE_NAME,
    LIQUID_LINKS,
    VAPOR_LINKS,
    audit_provider_governed_registry,
    build_provider_governed_registry,
)


def _render_markdown(report: dict) -> str:
    audit = report["audit"]
    return "\n".join(
        (
            "# DD-091 Core V3 Provider-Governed Structural Audit",
            "",
            f"- Architecture: `{report['architecture_name']}`",
            f"- Classification: `{report['classification']}`",
            f"- Unknowns/residuals: `{audit['unknown_count']} / "
            f"{audit['residual_count']}`",
            f"- Structural rank/nullity: `{audit['structural_rank']} / "
            f"{audit['structural_nullity']}`",
            f"- Full stage-fugacity rows: `{audit['full_fugacity_row_count']}`",
            f"- Condenser bubble-fugacity rows: "
            f"`{audit['condenser_bubble_row_count']}`",
            f"- Energy-owned vapor links: `{audit['vapor_unknown_count']}`",
            f"- Francis-owned liquid flows: "
            f"`{audit['francis_liquid_unknown_count']}`",
            f"- Component telescoping: "
            f"`{audit['component_conservation_passed']}`",
            f"- Energy telescoping: `{audit['energy_conservation_passed']}`",
            f"- Provider contract: "
            f"`{audit['prospective_acceptance_contract_passed']}`",
            f"- Structural gate: `{audit['pass_gate']}`",
            "",
            "## Prohibited Uses",
            "",
            f"- TP flash in governing rows: `{audit['governing_tp_flash_uses']}`",
            f"- Independent PR in production rows: "
            f"`{audit['production_independent_pr_uses']}`",
            f"- Mixed-basis dependencies: `{audit['mixed_basis_dependencies']}`",
            f"- Interface fallbacks: `{audit['authority_fallbacks']}`",
            f"- Fixed condenser duty: "
            f"`{audit['fixed_condenser_duty_parameter_present']}`",
            f"- Imported historical acceptance: "
            f"`{audit['historical_acceptance_imported']}`",
            "",
            "## Scope",
            "",
            "- No DWSIM or independent-PR property evaluation was attempted.",
            "- No column residual was evaluated.",
            "- No nonlinear solve, root import, mass matrix, or dynamic "
            "integration was attempted.",
            "- The registry does not import a Core V2 residual owner.",
            "",
            "## Authorization",
            "",
            report["authorization"],
            "",
        )
    )


def run(component_names: tuple[str, ...], out_prefix: Path) -> dict:
    registry = build_provider_governed_registry(component_names)
    audit = audit_provider_governed_registry(registry)
    classification = (
        "dd091_core_v3_structural_gate_passed"
        if audit.pass_gate
        else "dd091_core_v3_structural_gate_failed"
    )
    report = {
        "schema_id": "dd091-core-v3-provider-governed-structural-v1",
        "architecture_name": ARCHITECTURE_NAME,
        "architecture_version": registry.architecture_version,
        "classification": classification,
        "authorization": (
            "DD-092 may perform exactly one precommitted Core V3 live residual, "
            "provider-ownership, conservation, and Jacobian audit. A root solve "
            "and dynamics remain unauthorized."
            if audit.pass_gate
            else "Stop. DD-092, root solving, and dynamics are unauthorized."
        ),
        "component_names": list(registry.component_names),
        "unknown_blocks": {
            block: sum(entry.block == block for entry in registry.unknowns)
            for block in sorted({entry.block for entry in registry.unknowns})
        },
        "residual_blocks": {
            block: sum(entry.block == block for entry in registry.residuals)
            for block in sorted({entry.block for entry in registry.residuals})
        },
        "provider_authorities": [
            asdict(authority) for authority in registry.provider_authorities
        ],
        "prospective_acceptance_rules": [
            asdict(rule) for rule in registry.acceptance_rules
        ],
        "liquid_links": [
            {"source": source, "destination": destination, "symbol": symbol}
            for source, destination, symbol in LIQUID_LINKS
        ],
        "vapor_links": [
            {"source": source, "destination": destination, "unknown": symbol}
            for source, destination, symbol in VAPOR_LINKS
        ],
        "global_component_form": "F_component - D*x_D - B*x_B",
        "global_energy_form": "H_feed + Q_R + Q_C - D*h_D - B*h_B",
        "live_property_evaluation_attempted": False,
        "column_residual_evaluation_attempted": False,
        "independent_pr_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "root_import_attempted": False,
        "mass_matrix_derivation_attempted": False,
        "dynamic_integration_attempted": False,
        "audit": asdict(audit),
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
        default=Path("logs/dd091_core_v3_provider_governed_structural_20260719"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(tuple(args.components), args.out_prefix)
    print(json.dumps(result, indent=2))
    raise SystemExit(
        0
        if result["classification"]
        == "dd091_core_v3_structural_gate_passed"
        else 2
    )
