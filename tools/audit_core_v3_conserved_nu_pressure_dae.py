#!/usr/bin/env python
"""Run the property-free DD-108 conserved-N/U pressure-DAE audit."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    audit_conserved_nu_pressure_dae_contract,
    build_conserved_nu_pressure_dae_contract,
)


OUTPUT = ROOT / "logs/dd108_core_v3_conserved_nu_pressure_dae_20260726.json"
COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def main() -> int:
    contract = build_conserved_nu_pressure_dae_contract(COMPONENTS)
    audit = audit_conserved_nu_pressure_dae_contract(contract)
    payload = {
        "schema_id": "dd108-core-v3-conserved-nu-pressure-dae-v1",
        "classification": (
            "dd108_structural_passed" if audit.pass_gate else "dd108_structural_failed"
        ),
        "decision": (
            "authorize_one_frozen_live_nu_pressure_numerical_contract"
            if audit.pass_gate
            else "stop_conserved_nu_pressure_architecture"
        ),
        "contract": {
            "name": contract.name,
            "version": contract.version,
            "storage_definition": contract.storage_definition,
            "energy_balance_definition": contract.energy_balance_definition,
            "pressure_definition": contract.pressure_definition,
            "storage_property_quantities": list(contract.storage_property_quantities),
            "index_claim": contract.index_claim,
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
