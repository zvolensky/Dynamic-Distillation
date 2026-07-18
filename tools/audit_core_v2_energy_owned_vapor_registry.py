#!/usr/bin/env python
"""Run the structural-only DD-083 energy-owned vapor-flow audit."""

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

from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    VAPOR_LINKS,
    audit_energy_owned_vapor_registry,
    build_energy_owned_vapor_registry,
)


def _render_markdown(report: dict) -> str:
    audit = report["audit"]
    return "\n".join(
        (
            "# DD-083 Energy-Owned Vapor-Flow Structural Audit",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Unknowns/residuals: `{audit['unknown_count']} / "
            f"{audit['residual_count']}`",
            f"- Structural rank/nullity: `{audit['structural_rank']} / "
            f"{audit['structural_nullity']}`",
            f"- Independent vapor links: `{audit['vapor_unknown_count']}`",
            f"- Full fugacity rows: `{audit['full_fugacity_row_count']}`",
            f"- Component telescoping: `{audit['component_conservation_passed']}`",
            f"- Energy telescoping: `{audit['energy_conservation_passed']}`",
            f"- Structural gate: `{audit['pass_gate']}`",
            "",
            "## Ownership",
            "",
            "- pressure remains prescribed;",
            "- reflux and condenser/reboiler duties remain operating parameters;",
            "- each internal vapor link is an independent algebraic unknown;",
            "- simultaneous MESH component and energy balances own vapor traffic;",
            "- every equilibrium outlet has all component fugacity equalities;",
            "- Francis equations remain the sole owner of tray liquid flow;",
            "- terminal liquid amounts remain specified and D/B remain unknown;",
            "- no profile, previous-step flow, cap, controller, or relaxation is present.",
            "",
            "## Authorization",
            "",
            report["authorization"],
            "",
        )
    )


def run(component_names: tuple[str, ...], out_prefix: Path) -> dict:
    registry = build_energy_owned_vapor_registry(component_names)
    audit = audit_energy_owned_vapor_registry(registry)
    report = {
        "schema_id": "dd083-core-v2-energy-owned-vapor-registry-v1",
        "classification": (
            "dd083_structural_gate_passed"
            if audit.pass_gate
            else "dd083_structural_gate_failed"
        ),
        "authorization": (
            "The structural ledger is admissible for an independent live-property "
            "numerical audit. No nonlinear solve or dynamic integration is "
            "authorized by DD-083."
            if audit.pass_gate
            else "Stop and correct the equation or ownership ledger."
        ),
        "component_names": list(registry.component_names),
        "vapor_links": [
            {"source": source, "destination": destination, "unknown": symbol}
            for source, destination, symbol in VAPOR_LINKS
        ],
        "pressure_mode": "prescribed",
        "liquid_flow_mode": "francis-only",
        "vapor_flow_mode": "energy-owned-simultaneous-mesh",
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
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
        default=Path("logs/dd083_energy_owned_vapor_structural_20260718"),
    )
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(tuple(args.components), args.out_prefix)
    print(json.dumps(result, indent=2))
    raise SystemExit(
        0 if result["classification"] == "dd083_structural_gate_passed" else 2
    )
