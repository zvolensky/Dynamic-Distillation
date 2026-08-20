#!/usr/bin/env python
"""Audit workbook-backed terminal level-control ownership for vapor holdup."""

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

from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (  # noqa: E402
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (  # noqa: E402
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.core_v3.vapor_holdup_terminal_control_contract_v1 import (  # noqa: E402
    CONTRACT_VERSION,
    audit_vapor_holdup_terminal_control_contract,
    build_vapor_holdup_terminal_control_contract,
    level_controllers_from_specs,
    terminal_geometry_from_specs,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)


DEFAULT_WORKBOOK = Path(
    "distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx"
)
DEFAULT_JSON = Path(
    "logs/dd263_core_v3_vapor_holdup_terminal_control_contract_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_263_core_v3_vapor_holdup_terminal_control_contract_20260820.md"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(workbook_path: Path = DEFAULT_WORKBOOK) -> dict[str, Any]:
    workbook = (ROOT / workbook_path).resolve()
    case = load_case_from_excel(str(workbook))
    column = build_column_spec_from_case(case)
    feed = column.streams.get("Feed")
    if feed is None or feed.stage_1based is None:
        raise ValueError("terminal-control audit requires one staged feed")
    topology = build_column_topology(
        rectifying_volume_count=int(feed.stage_1based) - 2,
        stripping_volume_count=int(column.n_stages) - int(feed.stage_1based) - 1,
    )
    volume_geometry = build_column_vapor_geometry(column, case.specs, topology)
    vapor_topology = build_vapor_holdup_topology(
        column=topology,
        vapor_volume_ft3=gross_capacity_mapping(volume_geometry),
    )
    geometry = terminal_geometry_from_specs(case.specs)
    controllers = level_controllers_from_specs(case.specs)

    def audited(component_names: tuple[str, ...]) -> dict[str, Any]:
        base = build_vapor_holdup_dae_contract(
            component_names,
            topology=vapor_topology,
        )
        contract = build_vapor_holdup_terminal_control_contract(
            base,
            geometry=geometry,
            controllers=controllers,
        )
        return asdict(audit_vapor_holdup_terminal_control_contract(contract))

    actual = audited(tuple(column.components_excel))
    generic = audited(("component_1", "component_2"))
    passed = bool(actual["pass_gate"] and generic["pass_gate"])
    implementation = Path(
        "src/dynamic_distillation/core_v3/"
        "vapor_holdup_terminal_control_contract_v1.py"
    )
    unit_test = Path(
        "tests/test_core_v3_vapor_holdup_terminal_control_contract_v1.py"
    )
    return {
        "schema_id": "dd263-core-v3-vapor-holdup-terminal-control-contract-v1",
        "classification": (
            "vapor_holdup_terminal_control_structure_passed"
            if passed
            else "vapor_holdup_terminal_control_structure_failed"
        ),
        "contract_version": CONTRACT_VERSION,
        "workbook": str(workbook),
        "workbook_sha256": _sha256(workbook),
        "implementation_sha256": _sha256(ROOT / implementation),
        "unit_test_sha256": _sha256(ROOT / unit_test),
        "component_names": list(column.components_excel),
        "stage_count": int(column.n_stages),
        "feed_stage_1based": int(feed.stage_1based),
        "geometry": asdict(geometry),
        "controllers": asdict(controllers),
        "geometry_ownership": {
            "reflux_drum": (
                "workbook Top Drum Diameter/Length; horizontal cylinder with "
                "two hemispherical heads"
            ),
            "bottom_sump": (
                "workbook Bottom Sump Diameter/Height; vertical cylinder; "
                "reboiler vapor extension excluded from level"
            ),
        },
        "product_ownership": {
            "reflux_drum_level_controller": "distillate flow D",
            "bottom_sump_level_controller": "bottoms flow B",
            "product_composition": "live terminal liquid composition",
            "reflux": "fixed operating input",
            "reboiler_duty": "fixed operating input",
        },
        "actual_c3c4_audit": actual,
        "two_component_generic_audit": generic,
        "historical_contract_modified": False,
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_separately_frozen_live_zero_motion_control_audit"
            if passed
            else "stop_vapor_holdup_terminal_control_path"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    geometry = report["geometry"]
    actual = report["actual_c3c4_audit"]
    return "\n".join(
        (
            "# DD-263 C3/C4 Vapor-Holdup Terminal Level-Control Contract",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Structural system: `{actual['solve_variable_count']} x "
            f"{actual['row_count']}`",
            f"- Structural rank: `{actual['structural_rank']}`",
            "- Historical contracts or results modified: `False`",
            "- Property call, residual, solve, timestep, or dynamics: `False`",
            "",
            "## Workbook Geometry",
            "",
            f"- Reflux drum diameter: `{geometry['drum_diameter_ft']:.4f} ft`",
            f"- Reflux drum tangent length: `{geometry['drum_tangent_length_ft']:.4f} ft`",
            "- Reflux drum heads: `two hemispherical`",
            f"- Reflux drum gross capacity: `{geometry['drum_gross_capacity_ft3']:.6f} ft3`",
            f"- Bottom sump diameter: `{geometry['sump_diameter_ft']:.4f} ft`",
            f"- Bottom sump height: `{geometry['sump_height_ft']:.4f} ft`",
            f"- Bottom sump gross capacity: `{geometry['sump_gross_capacity_ft3']:.6f} ft3`",
            "",
            "The dimensions are read through the normalized Excel loader from the "
            "C3/C4 workbook. They are not copied into the controller setup. The "
            "reboiler vapor extension remains part of bottom vapor capacity but is "
            "not part of the sump liquid-level calculation.",
            "",
            "## Ownership",
            "",
            "- The reflux-drum level controller manipulates distillate flow `D`.",
            "- The bottom-sump level controller manipulates bottoms flow `B`.",
            "- Product compositions use the live terminal liquid compositions.",
            "- Reflux and reboiler duty remain fixed inputs for this first control step.",
            "- Controller memories are new differential states.",
            "- Fixed `D/B` parameters are removed from the controlled contract.",
            "",
            "## Boundary",
            "",
            "This is a structural pass only. The next permitted work is one separately "
            "frozen live zero-motion audit that reconstructs terminal levels from "
            "live liquid density and initializes controller memory bumplessly. A "
            "controlled trajectory is not yet authorized.",
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
