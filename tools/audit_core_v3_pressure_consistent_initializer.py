#!/usr/bin/env python
"""Audit the property-free DD-106 pressure-consistent initializer contract."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.pressure_consistent_initializer_contract_v1 import (
    audit_pressure_consistent_initializer_contract,
    build_pressure_consistent_initializer_contract,
)


COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")
OUTPUT = ROOT / "logs/dd106_core_v3_pressure_consistent_initializer_20260726.json"


def main() -> int:
    contract = build_pressure_consistent_initializer_contract(COMPONENTS)
    audit = audit_pressure_consistent_initializer_contract(contract)
    payload = {
        "schema_id": "dd106-core-v3-pressure-consistent-initializer-v1",
        "classification": (
            "dd106_structural_passed" if audit.pass_gate else "dd106_structural_failed"
        ),
        "decision": (
            "authorize_one_frozen_live_initializer_numerical_contract"
            if audit.pass_gate
            else "stop_pressure_consistent_initializer"
        ),
        "contract": {
            "name": contract.name,
            "version": contract.version,
            "component_inventory_reference": contract.component_inventory_reference,
            "stored_energy_reference": contract.stored_energy_reference,
            "terminal_inventory_reference": contract.terminal_inventory_reference,
            "state_parameterization": contract.state_parameterization,
            "solve_form": contract.solve_form,
            "selection_objective": [asdict(term) for term in contract.selection_objective],
        },
        "audit": asdict(audit),
        "scope": {
            "property_evaluation_attempted": contract.property_evaluation_attempted,
            "nonlinear_solve_attempted": contract.nonlinear_solve_attempted,
            "dynamic_integration_attempted": contract.dynamic_integration_attempted,
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if audit.pass_gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
