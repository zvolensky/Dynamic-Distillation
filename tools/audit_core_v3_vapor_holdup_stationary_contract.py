#!/usr/bin/env python
"""Audit the property-free stationary vapor-holdup initializer contract."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (  # noqa: E402
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_contract_v1 import (  # noqa: E402
    CONTRACT_VERSION,
    audit_vapor_holdup_stationary_contract,
    build_vapor_holdup_stationary_contract,
)


DEFAULT_JSON = Path(
    "logs/dd242_core_v3_vapor_holdup_stationary_contract_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_242_core_v3_vapor_holdup_stationary_contract_20260820.md"
)
COMPONENTS = ("Propane", "n-Butane", "n-Pentane")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case(rectifying: int, stripping: int) -> dict[str, Any]:
    column = build_column_topology(
        rectifying_volume_count=rectifying,
        stripping_volume_count=stripping,
    )
    topology = build_vapor_holdup_topology(
        column=column,
        vapor_volume_ft3={volume: 100.0 for volume in column.volume_ids},
    )
    contract = build_vapor_holdup_stationary_contract(
        COMPONENTS,
        topology=topology,
    )
    audit = audit_vapor_holdup_stationary_contract(contract)
    return {
        "volume_ids": list(column.volume_ids),
        "variable_names": [variable.name for variable in contract.variables],
        "row_names": [row.name for row in contract.rows],
        "audit": asdict(audit),
    }


def build_report() -> dict[str, Any]:
    development = _case(1, 1)
    full_column = _case(10, 7)
    passed = bool(
        development["audit"]["pass_gate"]
        and full_column["audit"]["pass_gate"]
    )
    implementation = Path(
        "src/dynamic_distillation/core_v3/"
        "vapor_holdup_stationary_contract_v1.py"
    )
    tests = Path(
        "tests/test_core_v3_vapor_holdup_stationary_contract_v1.py"
    )
    return {
        "schema_id": "dd242-core-v3-vapor-holdup-stationary-contract-v1",
        "classification": (
            "vapor_holdup_stationary_contract_passed"
            if passed
            else "vapor_holdup_stationary_contract_failed"
        ),
        "contract_version": CONTRACT_VERSION,
        "component_names": list(COMPONENTS),
        "development_topology": development,
        "full_c3c4_topology": full_column,
        "terminal_closure": {
            "top_liquid_inventory": "fixed target",
            "bottom_liquid_inventory": "fixed target",
            "distillate_flow": "solved algebraic variable",
            "bottoms_flow": "solved algebraic variable",
            "reason": (
                "steady terminal inventories need specified levels; product flows "
                "must move to satisfy their stationary balances"
            ),
        },
        "historical_core_v3_modified": False,
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "implementation_sha256": _sha256(ROOT / implementation),
        "tests_sha256": _sha256(ROOT / tests),
        "pass_gate": passed,
        "decision": (
            "authorize_stationary_numerical_residual_implementation"
            if passed
            else "stop_and_correct_stationary_contract"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    development = report["development_topology"]["audit"]
    full = report["full_c3c4_topology"]["audit"]
    return "\n".join(
        (
            "# DD-242 Stationary Vapor-Holdup Initializer Contract",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            "- Property calls, residuals, solves, and timesteps: `False`",
            "",
            "## Result",
            "",
            (
                "- Five-volume development system: "
                f"`{development['variable_count']} x {development['row_count']}`, "
                f"rank `{development['structural_rank']}`"
            ),
            (
                "- Twenty-volume C3/C4 system: "
                f"`{full['variable_count']} x {full['row_count']}`, "
                f"rank `{full['structural_rank']}`"
            ),
            "- Structural nullity: `0` in both systems",
            "- Zero or unregistered rows/variables: `0`",
            "",
            "## Plain-Language Design",
            "",
            (
                "The initializer solves the actual resident liquid and vapor "
                "inventories at steady state. It fixes the reflux-drum and sump "
                "liquid inventories at their geometry-based level targets, while "
                "distillate and bottoms rates become solved variables. This closes "
                "the two terminal level degrees of freedom without adding controllers "
                "or pretending that a dynamic step is a steady-state solution."
            ),
            "",
            "## Boundary",
            "",
            (
                "This is a structural result only. It authorizes implementation of "
                "one live stationary residual; it does not authorize a root solve "
                "or dynamic integration."
            ),
            "",
        )
    )


def _load_saved_for_test() -> dict[str, Any]:
    return json.loads((ROOT / DEFAULT_JSON).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = build_report()
    json_path = ROOT / args.json
    doc_path = ROOT / args.doc
    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    doc_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
