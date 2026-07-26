#!/usr/bin/env python
"""Run the property-free DD-107 initializer numerical-readiness audit."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.pressure_consistent_initializer_contract_v1 import (
    build_pressure_consistent_initializer_contract,
)
from dynamic_distillation.core_v3.pressure_initializer_readiness_v1 import (
    audit_pressure_initializer_readiness,
)


OUTPUT = ROOT / "logs/dd107_core_v3_pressure_initializer_readiness_20260726.json"
COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def main() -> int:
    contract = build_pressure_consistent_initializer_contract(COMPONENTS)
    audit = audit_pressure_initializer_readiness(contract)
    payload = {
        "schema_id": "dd107-core-v3-pressure-initializer-readiness-v1",
        "classification": "dd107_preexecution_stop",
        "decision": audit.decision,
        "audit": asdict(audit),
        "reason": (
            "DD-106 allows nonzero inventory rates but defines energy storage "
            "only by an exact backward-Euler difference. With pressure "
            "algebraic and no timestep, independent U/dU ownership, or "
            "pressure-aware reduced derivative, continuous dU/dt is undefined."
        ),
        "prohibited_successors": [
            "reuse the DD-096 fixed-pressure storage gradient",
            "introduce a hidden initialization timestep",
            "execute the DD-106 constrained optimizer",
            "tune objective weights or solver settings",
        ],
        "authorized_successor": (
            "property-free conserved N/U plus algebraic-pressure DAE ownership audit"
        ),
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
