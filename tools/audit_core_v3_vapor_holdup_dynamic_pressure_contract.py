#!/usr/bin/env python
"""Audit the fixed-duty, dynamic-top-pressure vapor-holdup successor."""

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

from dynamic_distillation.column_spec_builder_v1 import build_column_spec_from_case  # noqa: E402
from dynamic_distillation.core_v3.provider_governed_registry_v1 import build_column_topology  # noqa: E402
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dynamic_pressure_contract_v1 import (  # noqa: E402
    CONTRACT_VERSION,
    audit_vapor_holdup_dynamic_pressure_contract,
    build_vapor_holdup_dynamic_pressure_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (  # noqa: E402
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.excel_case_loader_v1 import load_case_from_excel  # noqa: E402


DEFAULT_WORKBOOK = Path(
    "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"
)
DEFAULT_JSON = Path(
    "logs/dd272_core_v3_vapor_holdup_dynamic_pressure_contract_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_272_core_v3_vapor_holdup_dynamic_pressure_contract_20260820.md"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(workbook_path: Path = DEFAULT_WORKBOOK) -> dict[str, Any]:
    workbook = (ROOT / workbook_path).resolve()
    case = load_case_from_excel(str(workbook))
    column = build_column_spec_from_case(case)
    feed_stage = int(column.streams["Feed"].stage_1based)
    topology = build_column_topology(
        rectifying_volume_count=feed_stage - 2,
        stripping_volume_count=int(column.n_stages) - feed_stage - 1,
    )
    volume_geometry = build_column_vapor_geometry(column, case.specs, topology)
    vapor_topology = build_vapor_holdup_topology(
        column=topology,
        vapor_volume_ft3=gross_capacity_mapping(volume_geometry),
    )
    geometry = terminal_geometry_from_specs(case.specs)
    controllers = level_controllers_from_specs(case.specs)

    def audited(components: tuple[str, ...]) -> dict[str, Any]:
        base = build_vapor_holdup_dae_contract(components, topology=vapor_topology)
        terminal = build_vapor_holdup_terminal_control_contract(
            base,
            geometry=geometry,
            controllers=controllers,
        )
        successor = build_vapor_holdup_dynamic_pressure_contract(terminal)
        return asdict(audit_vapor_holdup_dynamic_pressure_contract(successor))

    actual = audited(tuple(column.components_excel))
    generic = audited(("component_1", "component_2"))
    passed = bool(actual["pass_gate"] and generic["pass_gate"])
    implementation = Path(
        "src/dynamic_distillation/core_v3/"
        "vapor_holdup_dynamic_pressure_contract_v1.py"
    )
    test = Path("tests/test_core_v3_vapor_holdup_dynamic_pressure_contract_v1.py")
    return {
        "schema_id": "dd272-core-v3-vapor-holdup-dynamic-pressure-contract-v1",
        "classification": (
            "vapor_holdup_dynamic_pressure_structure_passed"
            if passed
            else "vapor_holdup_dynamic_pressure_structure_failed"
        ),
        "decision": (
            "authorize_separately_frozen_fixed_duty_residual_audit"
            if passed
            else "stop_dynamic_pressure_successor"
        ),
        "contract_version": CONTRACT_VERSION,
        "workbook": str(workbook),
        "workbook_sha256": _sha(workbook),
        "implementation_sha256": _sha(ROOT / implementation),
        "test_sha256": _sha(ROOT / test),
        "component_names": list(column.components_excel),
        "actual_c3c4_audit": actual,
        "two_component_generic_audit": generic,
        "equation_change": {
            "removed": "P[reflux_drum] - P_anchor = 0",
            "added": "Q_C - Q_C_specified = 0",
            "unchanged": (
                "vapor inventories, EOS volume closure, energy balances, "
                "pressure-drop hydraulics, and terminal level controllers"
            ),
        },
        "pressure_ownership": (
            "Absolute pressure is no longer prescribed. With condenser duty "
            "specified, pressure must emerge from conserved vapor inventory, "
            "temperature/energy, EOS volume closure, and hydraulic pressure drop."
        ),
        "historical_result_modified": False,
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "pass_gate": passed,
    }


def _markdown(report: dict[str, Any]) -> str:
    actual = report["actual_c3c4_audit"]
    generic = report["two_component_generic_audit"]
    return "\n".join(
        (
            "# DD-272 Vapor-Holdup Dynamic-Pressure Contract",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- C3/C4 system/rank: `{actual['solve_variable_count']} x "
            f"{actual['row_count']} / {actual['structural_rank']}`",
            f"- Generic two-component system/rank: `{generic['solve_variable_count']} x "
            f"{generic['row_count']} / {generic['structural_rank']}`",
            "- Pressure-anchor rows: `0`",
            "- Condenser-duty specification rows: `1`",
            "- Property call, residual, solve, or timestep: `False`",
            "",
            "## Correction",
            "",
            "The fixed reflux-drum pressure equation is removed. It is replaced "
            "one-for-one by a specified condenser-duty equation, while `Q_C` "
            "remains coupled to the reflux-drum total-energy balance. The system "
            "therefore remains square and full rank.",
            "",
            "Pressure is now structurally free to respond to vapor inventory, "
            "temperature, EOS free-volume closure, and tray pressure losses. No "
            "pressure-dynamic result is claimed yet. One separately frozen live "
            "fixed-duty residual and Jacobian audit is required before a timestep.",
            "",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()
    report = build_report(args.workbook)
    (ROOT / args.json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (ROOT / args.doc).write_text(_markdown(report), encoding="utf-8")
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
