#!/usr/bin/env python
"""Write the deterministic DD-101 Core V3 pressure-layer structural audit."""

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

from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    audit_pressure_layer_contract,
    build_pressure_layer_contract,
)


DEFAULT_OUTPUT = Path("logs/dd101_core_v3_pressure_layer_20260725.json")


def execute(output: Path) -> dict:
    contract = build_pressure_layer_contract(
        ("n-Propane", "n-Butane", "n-Pentane")
    )
    audit = audit_pressure_layer_contract(contract)
    payload = {
        "schema_id": "dd101-core-v3-pressure-layer-structural-audit-v1",
        "contract_name": contract.name,
        "contract_version": contract.version,
        "pressure_reconstruction": contract.pressure_reconstruction,
        "pressure_variables": [
            asdict(variable) for variable in contract.pressure_variables
        ],
        "pressure_drop_rows": [
            asdict(row)
            for row in contract.rows
            if row.block == "vapor_pressure_drop"
        ],
        "fixed_parameters": list(contract.fixed_parameters),
        "audit": asdict(audit),
        "pass": audit.pass_gate,
        "live_property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "next_authorization": (
            "one frozen live residual and Jacobian audit"
            if audit.pass_gate
            else "stop pressure-layer path"
        ),
    }
    destination = ROOT / output
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    destination.with_suffix(".md").write_text(
        "\n".join(
            (
                "# DD-101 Core V3 Pressure-Layer Structural Audit",
                "",
                f"- Pass: `{payload['pass']}`",
                f"- Solve variables: `{audit.solve_variable_count}`",
                f"- Rows: `{audit.row_count}`",
                f"- Structural rank: `{audit.structural_rank}`",
                f"- Structural nullity: `{audit.structural_nullity}`",
                f"- Pressure variables: `{audit.pressure_variable_count}`",
                f"- Pressure-drop rows: `{audit.pressure_drop_row_count}`",
                "- Live property evaluation: `False`",
                "- Nonlinear solve: `False`",
                "- Dynamic integration: `False`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(execute(args.output), indent=2))
