#!/usr/bin/env python
"""Execute the property-free DD-123 controlled-terminal dynamic audit."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dynamic_distillation.core_v3.controlled_terminal_dynamic_contract_v1 import (
    LevelControllerSpecification,
    TerminalGeometry,
    audit_controlled_terminal_dynamic_contract,
    build_controlled_terminal_dynamic_contract,
)


SCHEMA = "dd123-core-v3-controlled-terminal-dynamic-contract-result-v1"
RESULT = Path("logs/dd123_core_v3_controlled_terminal_dynamic_contract_20260727.json")
DOC = Path("docs/dd_123_core_v3_controlled_terminal_dynamic_contract_20260727.md")
DD122_CONTRACT = Path("logs/dd122_core_v3_controlled_terminal_zero_rate_contract_20260727.json")
DD122_RESULT = Path("logs/dd122_core_v3_controlled_terminal_zero_rate_20260727.json")
GEOMETRY_WORKBOOK = Path("distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _load(path: Path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = _load(DD122_CONTRACT)
    result = _load(DD122_RESULT)
    if not result["pass"] or result["decision"] != "authorize_zero_rate_dynamic_handoff_contract":
        raise RuntimeError("DD-123 requires the passed DD-122 authorization")
    geometry = TerminalGeometry(
        drum_diameter_ft=12.1,
        drum_tangent_length_ft=36.3,
        drum_head_shape="two_hemispherical",
        sump_diameter_ft=18.1759,
        sump_height_ft=12.0,
    )
    controllers = LevelControllerSpecification(
        drum_kc=0.5,
        drum_ti_sec=120.0,
        sump_kc=8.0,
        sump_ti_sec=120.0,
        product_rate_ratio_bounds=(0.25, 2.0),
    )
    component_names = tuple(source["source_mapping"]["component_names"])
    contract = build_controlled_terminal_dynamic_contract(
        component_names, geometry=geometry, controllers=controllers
    )
    generic = build_controlled_terminal_dynamic_contract(
        ("component_1", "component_2"), geometry=geometry, controllers=controllers
    )
    audit = audit_controlled_terminal_dynamic_contract(contract)
    generic_audit = audit_controlled_terminal_dynamic_contract(generic)
    endpoint = result["starts"][0]
    payload = {
        "schema_id": SCHEMA,
        "commit": _git("rev-parse", "HEAD"),
        "sources": {
            str(path).replace("\\", "/"): _sha(ROOT / path)
            for path in (DD122_CONTRACT, DD122_RESULT, GEOMETRY_WORKBOOK)
        },
        "geometry_source_workbook": str(GEOMETRY_WORKBOOK).replace("\\", "/"),
        "geometry": asdict(geometry),
        "controllers": asdict(controllers),
        "controller_tuning_provenance": {
            "drum_kc": "source workbook Top Level Kc",
            "drum_ti_sec": "existing project default because source workbook is blank",
            "sump_kc": "source workbook Bottom Level Kc",
            "sump_ti_sec": "source workbook Bottom Level Ti",
        },
        "terminal_inventory_setpoints_lbmol": source["initializer_numerical"]["terminal_total_targets_lbmol"],
        "bumpless_controller_memory": {
            "log_D_over_template": endpoint["final_coordinates"][-2],
            "log_B_over_template": endpoint["final_coordinates"][-1],
            "distillate_lbmolph": endpoint["distillate_lbmolph"],
            "bottoms_lbmolph": endpoint["bottoms_lbmolph"],
        },
        "state_coordinates": list(contract.state_coordinates),
        "derivative_variables": [asdict(item) for item in contract.derivative_variables],
        "algebraic_variables": [asdict(item) for item in contract.algebraic_variables],
        "rows": [asdict(item) for item in contract.rows],
        "level_definition": contract.level_definition,
        "controller_definition": contract.controller_definition,
        "three_component_audit": asdict(audit),
        "two_component_generic_audit": asdict(generic_audit),
        "pass": bool(audit.pass_gate and generic_audit.pass_gate),
        "decision": (
            "authorize_frozen_live_controlled_terminal_handoff_contract"
            if audit.pass_gate and generic_audit.pass_gate
            else "retire_controlled_terminal_dynamic_structure"
        ),
        "property_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
    }
    (ROOT / RESULT).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ROOT / DOC).write_text(
        "\n".join(
            (
                "# DD-123 Core V3 Controlled-Terminal Dynamic Contract",
                "",
                f"- Classification: `{'passed' if payload['pass'] else 'failed'}`",
                f"- Decision: `{payload['decision']}`",
                f"- Three-component system: `{audit.solve_variable_count} x {audit.row_count}`, rank `{audit.structural_rank}`",
                f"- Generic two-component system: `{generic_audit.solve_variable_count} x {generic_audit.row_count}`, rank `{generic_audit.structural_rank}`",
                "- Differential states: conserved component inventories, four lower internal energies, and two level-controller memories",
                "- Controller outputs: positive distillate and bottoms rates",
                "- Geometry: horizontal drum with two hemispherical heads and vertical cylindrical sump",
                f"- Bumpless outputs: `D={endpoint['distillate_lbmolph']:.6f}`, `B={endpoint['bottoms_lbmolph']:.6f} lbmol/h`",
                "- Property call, nonlinear solve, timestep, or dynamics: `False`",
                "",
                "The DD-122 terminal amounts remain inventory setpoints until the live property audit calculates their geometry-based physical levels. Passing authorizes only one frozen live zero-time controller-handoff audit before any timestep.",
                "",
            )
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
