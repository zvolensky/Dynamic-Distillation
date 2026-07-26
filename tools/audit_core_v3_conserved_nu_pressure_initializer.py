#!/usr/bin/env python
"""Audit the property-free DD-111 conserved-N/U initializer contract."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    audit_conserved_nu_pressure_initializer_contract,
    build_conserved_nu_pressure_initializer_contract,
)


COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")
OUTPUT = ROOT / "logs/dd111_core_v3_conserved_nu_pressure_initializer_20260726.json"
DOC = ROOT / "docs/dd_111_core_v3_conserved_nu_pressure_initializer_contract_20260726.md"


def main() -> int:
    contract = build_conserved_nu_pressure_initializer_contract(COMPONENTS)
    audit = audit_conserved_nu_pressure_initializer_contract(contract)
    payload = {
        "schema_id": "dd111-core-v3-conserved-nu-pressure-initializer-contract-v1",
        "classification": (
            "dd111_structural_passed" if audit.pass_gate else "dd111_structural_failed"
        ),
        "decision": (
            "authorize_one_frozen_live_constrained_initializer_contract"
            if audit.pass_gate
            else "stop_conserved_nu_pressure_initializer"
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
    DOC.write_text(
        "\n".join(
            (
                "# DD-111 Conserved N/U Pressure Initializer Contract",
                "",
                f"- Classification: `{payload['classification']}`",
                f"- Decision: `{payload['decision']}`",
                f"- Primal variables: `{audit.primal_variable_count}`",
                f"- Exact constraints/rank: `{audit.equality_constraint_count}/{audit.equality_structural_rank}`",
                f"- Feasible-manifold dimension: `{audit.feasible_manifold_dimension}`",
                f"- KKT dimension/rank: `{audit.kkt_dimension}/{audit.kkt_structural_rank}`",
                "- Live property calls: `False`",
                "- Initializer solve or timestep: `False`",
                "",
                "The four lower internal-energy states and rates correct DD-106's missing continuous pressure-aware energy ownership. One separately frozen live constrained-initializer contract may be drafted; execution remains unauthorized.",
                "",
            )
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))
    return 0 if audit.pass_gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
