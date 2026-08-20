#!/usr/bin/env python
"""Map the accepted DD-245 root into the successor dynamic state ledger."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (  # noqa: E402
    build_column_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dae_contract,
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)


SOURCE_ROOT = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_20260820.json"
)
SOURCE_CONTRACT = Path(
    "logs/dd245_core_v3_c3c4_vapor_holdup_stationary_root_contract_20260820.json"
)
DEFAULT_JSON = Path(
    "logs/dd246_core_v3_c3c4_vapor_holdup_dynamic_handoff_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_246_core_v3_c3c4_vapor_holdup_dynamic_handoff_20260820.md"
)
COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def _flatten(values: list[list[float]]) -> list[float]:
    return [float(value) for row in values for value in row]


def build_report() -> dict[str, Any]:
    root = json.loads((ROOT / SOURCE_ROOT).read_text(encoding="utf-8"))
    source_contract = json.loads(
        (ROOT / SOURCE_CONTRACT).read_text(encoding="utf-8")
    )
    if not root.get("pass_gate"):
        raise RuntimeError("DD-246 requires the accepted DD-245 root")
    column = build_column_topology(
        rectifying_volume_count=10,
        stripping_volume_count=7,
    )
    topology = build_vapor_holdup_topology(
        column=column,
        vapor_volume_ft3={volume: 100.0 for volume in column.volume_ids},
    )
    contract = build_vapor_holdup_dae_contract(
        COMPONENTS,
        topology=topology,
        product_flow_parameters=("D_dd245_root", "B_dd245_root"),
    )
    structural = audit_vapor_holdup_dae_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-246 requires the passing successor DAE structure")

    endpoint = root["endpoint"]
    liquid_inventory = np.asarray(
        endpoint["liquid_component_inventory_lbmol"], dtype=float
    )
    vapor_inventory = np.asarray(
        endpoint["vapor_component_inventory_lbmol"], dtype=float
    )
    phase_transfer = np.asarray(endpoint["phase_transfer_lbmolph"], dtype=float)
    temperature = np.asarray(endpoint["temperature_F"], dtype=float)
    pressure = np.asarray(endpoint["pressure_psia"], dtype=float)
    liquid_flow = np.asarray(
        endpoint["hydraulic_liquid_flow_lbmolph"], dtype=float
    )
    vapor_flow = np.asarray(endpoint["vapor_flow_lbmolph"], dtype=float)
    stationary_names = tuple(source_contract["variable_names"])
    stationary_values = tuple(
        (
            *_flatten(liquid_inventory.tolist()),
            *_flatten(vapor_inventory.tolist()),
            *_flatten(phase_transfer.tolist()),
            *temperature.tolist(),
            *pressure.tolist(),
            *liquid_flow.tolist(),
            *vapor_flow.tolist(),
            float(endpoint["condenser_duty_BTUph"]),
            float(endpoint["distillate_lbmolph"]),
            float(endpoint["bottoms_lbmolph"]),
        )
    )
    if len(stationary_names) != 260 or len(stationary_values) != 260:
        raise RuntimeError("DD-246 stationary ledger is invalid")
    stationary = dict(zip(stationary_names, stationary_values, strict=True))
    state_names = tuple(contract.state_coordinates)
    derivative_names = tuple(variable.name for variable in contract.derivative_variables)
    algebraic_names = tuple(variable.name for variable in contract.algebraic_variables)
    state = {name: stationary[name] for name in state_names}
    derivatives = {name: 0.0 for name in derivative_names}
    algebraic = {name: stationary[name] for name in algebraic_names}
    products = {
        "D_dd245_root": stationary["D"],
        "B_dd245_root": stationary["B"],
    }
    consumed = set(state_names) | set(algebraic_names) | {"D", "B"}
    missing = tuple(sorted(set(stationary_names) - consumed))
    extra = tuple(sorted(consumed - set(stationary_names)))
    duplicates = len(state_names) + len(algebraic_names) + 2 - len(consumed)

    history_current = dict(state)
    history_previous = dict(state)
    energy_slots = tuple(
        f"U_total[{volume}]" for volume in column.volume_ids
    )
    terminal_targets = {
        "top_liquid_inventory_lbmol": float(np.sum(liquid_inventory[0])),
        "bottom_liquid_inventory_lbmol": float(np.sum(liquid_inventory[-1])),
    }
    pass_gate = bool(
        structural.pass_gate
        and len(state) == 120
        and len(derivatives) == 120
        and len(algebraic) == 138
        and len(products) == 2
        and len(stationary) == 260
        and not missing
        and not extra
        and duplicates == 0
        and history_current == history_previous == state
        and all(value == 0.0 for value in derivatives.values())
        and len(energy_slots) == 20
        and all(value > 0.0 for value in state.values())
        and products["D_dd245_root"] > 0.0
        and products["B_dd245_root"] > 0.0
    )
    return {
        "schema_id": "dd246-core-v3-c3c4-vapor-holdup-dynamic-handoff-v1",
        "classification": (
            "vapor_holdup_dynamic_handoff_passed"
            if pass_gate
            else "vapor_holdup_dynamic_handoff_failed"
        ),
        "source_root": str(SOURCE_ROOT).replace("\\", "/"),
        "source_contract": str(SOURCE_CONTRACT).replace("\\", "/"),
        "structural_audit": asdict(structural),
        "stationary_coordinate_count": len(stationary),
        "mapping": {
            "conserved_state_count": len(state),
            "zero_derivative_count": len(derivatives),
            "algebraic_count": len(algebraic),
            "fixed_product_reference_count": len(products),
            "consumed_once_count": len(consumed),
            "missing_stationary_coordinates": list(missing),
            "extra_mapping_coordinates": list(extra),
            "duplicate_consumption_count": duplicates,
        },
        "current_state": state,
        "zero_derivatives": derivatives,
        "algebraic_state": algebraic,
        "fixed_product_references_lbmolph": products,
        "terminal_liquid_inventory_targets": terminal_targets,
        "bdf2_history": {
            "current_component_inventories": history_current,
            "previous_component_inventories": history_previous,
            "current_total_energy_slots": list(energy_slots),
            "previous_total_energy_slots": list(energy_slots),
            "energy_values_deferred_to_live_audit": True,
            "component_history_values": 240,
            "energy_history_values_deferred": 40,
            "total_history_values_after_live_reconstruction": 280,
        },
        "controller_execution_attempted": False,
        "controller_references_deferred": True,
        "property_evaluation_attempted": False,
        "residual_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "timestep_attempted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": pass_gate,
        "decision": (
            "authorize_live_zero_motion_energy_and_residual_audit"
            if pass_gate
            else "stop_and_correct_dynamic_handoff"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    mapping = report["mapping"]
    history = report["bdf2_history"]
    return "\n".join(
        (
            "# DD-246 Vapor-Holdup Dynamic Handoff",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            (
                "- Stationary coordinates consumed once: "
                f"`{mapping['consumed_once_count']}/260`"
            ),
            f"- Conserved liquid/vapor states: `{mapping['conserved_state_count']}`",
            f"- Initial state rates: `{mapping['zero_derivative_count']} zero`",
            f"- Algebraic values: `{mapping['algebraic_count']}`",
            "- Product references: `D and B from DD-245`",
            (
                "- BDF2 component/energy history values: "
                f"`{history['component_history_values']} / "
                f"{history['energy_history_values_deferred']}`"
            ),
            "- Property, residual, solve, timestep, or integration calls: `False`",
            "",
            "Both component-history levels repeat the accepted root exactly. "
            "Two-phase stored energy is intentionally deferred to one live audit.",
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
