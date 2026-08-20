#!/usr/bin/env python
"""Audit the property-free Core V3 vapor-holdup successor contract."""

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
    CONTRACT_VERSION,
    audit_vapor_holdup_dae_contract,
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)


DEFAULT_JSON = Path(
    "logs/dd236_core_v3_vapor_holdup_structural_contract_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_236_core_v3_vapor_holdup_structural_contract_20260820.md"
)
COMPONENTS = ("Propane", "n-Butane", "n-Pentane")
STRUCTURAL_VOLUME_FT3 = 100.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case(rectifying: int, stripping: int) -> dict[str, Any]:
    column = build_column_topology(
        rectifying_volume_count=rectifying,
        stripping_volume_count=stripping,
    )
    declared_volumes = {
        volume: STRUCTURAL_VOLUME_FT3 for volume in column.volume_ids
    }
    topology = build_vapor_holdup_topology(
        column=column,
        vapor_volume_ft3=declared_volumes,
    )
    contract = build_vapor_holdup_dae_contract(
        COMPONENTS,
        topology=topology,
    )
    audit = audit_vapor_holdup_dae_contract(contract)
    return {
        "volume_ids": list(column.volume_ids),
        "vapor_control_volume_ids": list(topology.vapor_control_volume_ids),
        "declared_structural_volume_ft3": declared_volumes,
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
        "src/dynamic_distillation/core_v3/vapor_holdup_dae_contract_v1.py"
    )
    tests = Path("tests/test_core_v3_vapor_holdup_dae_contract_v1.py")
    return {
        "schema_id": "dd236-core-v3-vapor-holdup-structural-contract-v1",
        "classification": (
            "vapor_holdup_structural_contract_passed"
            if passed
            else "vapor_holdup_structural_contract_failed"
        ),
        "contract_version": CONTRACT_VERSION,
        "component_names": list(COMPONENTS),
        "development_topology": development,
        "full_c3c4_topology": full_column,
        "volume_declaration_role": (
            "positive structural test values only; not accepted physical geometry"
        ),
        "physical_geometry_required_before_live_properties": True,
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
            "authorize_live_vapor_property_and_eos_residual_implementation"
            if passed
            else "stop_vapor_holdup_successor"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    development = report["development_topology"]["audit"]
    full = report["full_c3c4_topology"]["audit"]
    return "\n".join(
        (
            "# DD-236 Core V3 Vapor-Holdup Structural Contract",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            "- Historical Core V3 contracts/results modified: `False`",
            "- Live properties, residual, solve, timestep, or trajectory: `False`",
            "",
            "## Structural Results",
            "",
            (
                "- Five-volume development contract: "
                f"`{development['solve_variable_count']} x "
                f"{development['row_count']}`, rank "
                f"`{development['structural_rank']}`"
            ),
            (
                "- Twenty-volume C3/C4 contract: "
                f"`{full['solve_variable_count']} x {full['row_count']}`, "
                f"rank `{full['structural_rank']}`"
            ),
            "- Conserved states per volume: `N_L[j,k]` and `N_V[j,k]`",
            "- Vapor composition: derived only as `N_V/sum(N_V)`",
            "- Pressure: vapor EOS + interstage pressure drop + one top anchor",
            "- Energy storage: `U_total = U_L + U_V`",
            "- Phase transfer: equal and opposite in liquid/vapor balances",
            "",
            "## Boundary",
            "",
            (
                "The positive volume values used here are structural test values, "
                "not accepted tray or vessel geometry. Real free-volume geometry "
                "is mandatory before a live property or numerical residual audit."
            ),
            "",
        )
    )


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
