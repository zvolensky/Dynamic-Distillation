#!/usr/bin/env python
"""Write the deterministic DD-104 pressure-enabled implicit-DAE audit."""

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

from dynamic_distillation.core_v3.pressure_implicit_dae_contract_v1 import (
    audit_pressure_implicit_dae_contract,
    build_pressure_implicit_dae_contract,
)


DEFAULT_OUTPUT = Path("logs/dd104_core_v3_pressure_implicit_dae_20260726.json")
DEFAULT_DOCUMENT = Path(
    "docs/dd_104_core_v3_pressure_implicit_dae_contract_20260726.md"
)


def execute(output: Path, document: Path) -> dict:
    contract = build_pressure_implicit_dae_contract(
        ("n-Propane", "n-Butane", "n-Pentane")
    )
    audit = audit_pressure_implicit_dae_contract(contract)
    payload = {
        "schema_id": "dd104-core-v3-pressure-implicit-dae-structural-audit-v1",
        "contract_name": contract.name,
        "contract_version": contract.version,
        "state_coordinates": list(contract.state_coordinates),
        "derivative_variables": [
            asdict(variable) for variable in contract.derivative_variables
        ],
        "algebraic_variables": [
            asdict(variable) for variable in contract.algebraic_variables
        ],
        "rows": [asdict(row) for row in contract.rows],
        "pressure_link_ownership": [
            asdict(link) for link in contract.pressure_link_ownership
        ],
        "endpoint_inventory_map": contract.endpoint_inventory_map,
        "energy_storage": contract.energy_storage,
        "index_claim": contract.index_claim,
        "audit": asdict(audit),
        "pass": audit.pass_gate,
        "live_property_evaluation_attempted": False,
        "mass_matrix_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "next_authorization": (
            "one frozen live pressure-enabled leading-Jacobian and consistent-rate audit"
            if audit.pass_gate
            else "stop pressure-enabled implicit-DAE path"
        ),
    }
    destination = ROOT / output
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report = ROOT / document
    report.write_text(
        "\n".join(
            (
                "# DD-104 Core V3 Pressure-Enabled Implicit DAE Contract",
                "",
                "## Decision",
                "",
                f"DD-104 structural gate pass: `{audit.pass_gate}`.",
                "",
                "DD-103 proved that the DD-094 inventories cannot be held fixed while",
                "the pressure-enabled equations are forced to zero rate. DD-104 therefore",
                "does not attempt another steady repair. It restores the 15 component-",
                "inventory rates as simultaneous implicit unknowns beside the 27 algebraic",
                "coordinates.",
                "",
                "## Structural Ledger",
                "",
                f"- State coordinates: `{audit.state_coordinate_count}`",
                f"- Inventory-rate variables: `{audit.derivative_variable_count}`",
                f"- Algebraic variables: `{audit.algebraic_variable_count}`",
                f"- Total solve variables / rows: `{audit.solve_variable_count} / {audit.row_count}`",
                f"- Structural rank / nullity: `{audit.structural_rank} / {audit.structural_nullity}`",
                f"- Pressure variables / pressure rates: `{audit.pressure_variable_count} / {audit.pressure_rate_variable_count}`",
                f"- Jacobian colors: `{audit.color_count}`",
                f"- Zero rows / columns: `{len(audit.zero_rows)} / {len(audit.zero_solve_columns)}`",
                "",
                "For three components the solve vector is `15` inventory rates plus",
                "`27` algebraic coordinates. The equations are the existing `15` component",
                "balances, `5` energy balances, `15` fugacity equations, `3` Francis",
                "relations, and `4` pressure-drop equations.",
                "",
                "## Pressure Ownership",
                "",
                "Reflux-drum pressure remains the sole fixed anchor. Four lower-volume",
                "pressures are algebraic unknowns; there is no pressure derivative or",
                "resident vapor inventory. The terminal reboiler/sump return is dry-only.",
                "The other three links are physical tray links with dry resistance plus",
                "liquid head. Vapor flow remains energy-owned on every link.",
                "",
                "## Implicit Ownership",
                "",
                f"`{contract.endpoint_inventory_map}`",
                "",
                f"`{contract.energy_storage}`",
                "",
                "The structural Jacobian includes every rate-to-endpoint-inventory chain.",
                "The terminal dry-only pressure row has no false sump-inventory/head",
                "coupling; the three tray pressure rows retain their nine component-rate",
                "couplings. The deterministic coloring is conflict-free.",
                "",
                "## Scope And Authorization",
                "",
                "No property call, mass-matrix evaluation, nonlinear solve, numerical",
                "step, controller, or integration was attempted. Component and energy",
                "conservation are inherited exactly. Fixed DD-094 product rates remain the",
                "open-loop boundary condition.",
                "",
                "A pass authorizes one separately frozen live leading-Jacobian and",
                "consistent-rate audit at the DD-094 state using the DD-103 pressure seed.",
                "It does not authorize a time step, trajectory, controller, vapor holdup,",
                "or production-scale model.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT)
    args = parser.parse_args()
    print(json.dumps(execute(args.output, args.document), indent=2))
