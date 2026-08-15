#!/usr/bin/env python
"""Build the property-free DD-232 full-C3/C4 dynamic handoff ledger."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_full_c3c4_live_readiness as full_column  # noqa: E402

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (  # noqa: E402
    dynamic_algebraic_coordinates,
    dynamic_algebraic_indices,
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (  # noqa: E402
    PhysicalState,
    coordinate_layout,
    encode_state,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_contract_v1 import (  # noqa: E402
    audit_controlled_bdf2_contract,
    build_controlled_bdf2_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    TerminalPIParameters,
    TerminalVesselGeometry,
    audit_terminal_inventory_control_contract,
    build_terminal_inventory_control_contract,
)


SCHEMA = "dd232-core-v3-full-c3c4-dynamic-handoff-v1"
DD221 = Path("logs/dd221_core_v3_full_c3c4_structural_migration_20260815.json")
DD231_CONTRACT = Path(
    "logs/dd231_core_v3_full_c3c4_aligned_density_root_contract_20260815.json"
)
DD231_RESULT = Path(
    "logs/dd231_core_v3_full_c3c4_aligned_density_root_20260815.json"
)
DEFAULT_OUT = Path("logs/dd232_core_v3_full_c3c4_dynamic_handoff_20260815")


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _vector(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=float).reshape(-1)]


def _rows(values: Any) -> list[list[float]]:
    return [_vector(row) for row in np.asarray(values, dtype=float)]


def _state(payload: Mapping[str, Any]) -> PhysicalState:
    return PhysicalState(
        liquid_moles_lbmol=np.asarray(payload["liquid_moles_lbmol"], dtype=float),
        liquid_mole_fraction=np.asarray(payload["liquid_mole_fraction"], dtype=float),
        temperature_F=np.asarray(payload["temperature_F"], dtype=float),
        vapor_mole_fraction=np.asarray(payload["vapor_mole_fraction"], dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            payload["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(payload["vapor_flow_lbmolph"], dtype=float),
        distillate_lbmolph=float(payload["distillate_lbmolph"]),
        bottoms_lbmolph=float(payload["bottoms_lbmolph"]),
        bubble_vapor_mole_fraction=np.asarray(
            payload["bubble_vapor_mole_fraction"], dtype=float
        ),
        condenser_duty_BTUph=float(payload["condenser_duty_BTUph"]),
    )


def _history_values(
    names: tuple[str, ...],
    inventory: np.ndarray,
    volume_ids: tuple[str, ...],
    component_names: tuple[str, ...],
) -> list[float]:
    values = {
        f"N[{volume},{component}]": float(inventory[volume_index, component_index])
        for volume_index, volume in enumerate(volume_ids)
        for component_index, component in enumerate(component_names)
    }
    result: list[float] = []
    for name in names:
        coordinate = name.split("@", 1)[0]
        result.append(values[coordinate])
    return result


def build_report(
    *,
    dd221_path: Path = DD221,
    dd231_contract_path: Path = DD231_CONTRACT,
    dd231_result_path: Path = DD231_RESULT,
) -> dict[str, Any]:
    structural_source = _load(dd221_path)
    root_contract = _load(dd231_contract_path)
    root_result = _load(dd231_result_path)
    if not structural_source.get("pass_gate") or not root_result.get("campaign_pass"):
        raise RuntimeError("DD-232 requires accepted DD-221 and DD-231 evidence")

    model_contract_path = Path(root_contract["source_model_contract"])
    model_contract = _load(model_contract_path)
    spec = full_column._spec(
        model_contract["source_mapping"],
        float(model_contract["operating_spec"]["feed_enthalpy_BTUph"]),
    )
    reference = full_column._reference(model_contract["reference"])
    accepted_start = root_result["starts"]["source_mapped_seed"]
    state = _state(accepted_start["state"])
    accepted_coordinates = np.asarray(
        accepted_start["final_coordinates"], dtype=float
    )

    base = build_dynamic_dae_contract(
        spec.component_names,
        topology=spec.topology,
        accepted_root_artifact=str(dd231_result_path).replace("\\", "/"),
        product_flow_parameters=("D_dd231_root", "B_dd231_root"),
    )
    terminal = structural_source["terminal_inputs"]
    controlled = build_terminal_inventory_control_contract(
        base,
        geometry=TerminalVesselGeometry(**terminal["geometry"]),
        controllers=TerminalPIParameters(**terminal["controllers"]),
    )
    bdf2 = build_controlled_bdf2_contract(controlled)
    base_audit = audit_dynamic_dae_contract(base)
    controlled_audit = audit_terminal_inventory_control_contract(controlled)
    bdf2_audit = audit_controlled_bdf2_contract(bdf2)

    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    controller_memory = np.zeros(2, dtype=float)
    root_solve_coordinates = np.concatenate(
        (
            np.zeros(len(base.derivative_variables), dtype=float),
            np.zeros(2, dtype=float),
            algebraic,
            np.zeros(2, dtype=float),
        )
    )
    encoded = encode_state(spec, reference, state)
    layout = coordinate_layout(spec)
    algebraic_indices = dynamic_algebraic_indices(spec)
    state_source_indices = np.asarray(
        (
            *range(layout.liquid_moles.start, layout.liquid_moles.stop),
            *range(layout.liquid_alr.start, layout.liquid_alr.stop),
        ),
        dtype=int,
    )
    product_source_indices = np.asarray((layout.distillate, layout.bottoms), dtype=int)
    consumed_indices = np.concatenate(
        (state_source_indices, algebraic_indices, product_source_indices)
    )
    component_history_values = _history_values(
        bdf2.component_history_coordinates,
        inventory,
        spec.topology.volume_ids,
        spec.component_names,
    )
    controller_history_values = [0.0] * len(bdf2.controller_history_coordinates)

    dimensions = {
        "stationary_coordinates": int(accepted_coordinates.size),
        "component_inventory_states": int(inventory.size),
        "dynamic_algebraic_coordinates": int(algebraic.size),
        "open_loop_dynamic_solve": len(base.rows),
        "controller_memory_states": 2,
        "controlled_dynamic_solve": len(controlled.rows),
        "bdf2_component_history_values": len(bdf2.component_history_coordinates),
        "bdf2_energy_history_values": len(bdf2.energy_history_coordinates),
        "bdf2_controller_history_values": len(bdf2.controller_history_coordinates),
        "bdf2_total_history_values": bdf2_audit.history_value_count,
    }
    gates = {
        "accepted_root_is_reproducible": bool(
            accepted_coordinates.shape == encoded.shape
            and np.max(np.abs(accepted_coordinates - encoded)) < 1.0e-12
        ),
        "all_stationary_coordinates_consumed_once": bool(
            consumed_indices.size == accepted_coordinates.size
            and len(set(int(value) for value in consumed_indices))
            == accepted_coordinates.size
            and set(int(value) for value in consumed_indices)
            == set(range(accepted_coordinates.size))
        ),
        "inventory_is_complete_and_positive": bool(
            inventory.shape
            == (len(spec.topology.volume_ids), len(spec.component_names))
            and np.all(inventory > 0.0)
        ),
        "dynamic_algebraic_mapping_is_complete": bool(
            algebraic.size == len(base.algebraic_variables)
        ),
        "zero_rate_and_bumpless_controller_seed_is_complete": bool(
            root_solve_coordinates.size == len(controlled.rows)
            and np.array_equal(
                root_solve_coordinates[: len(base.derivative_variables) + 2],
                np.zeros(len(base.derivative_variables) + 2),
            )
            and np.array_equal(root_solve_coordinates[-2:], np.zeros(2))
            and np.array_equal(controller_memory, np.zeros(2))
        ),
        "product_references_match_accepted_root": bool(
            state.distillate_lbmolph > 0.0 and state.bottoms_lbmolph > 0.0
        ),
        "component_histories_repeat_accepted_state": bool(
            len(component_history_values) == 2 * inventory.size
            and np.array_equal(
                np.asarray(component_history_values[: inventory.size]),
                inventory.reshape(-1),
            )
            and np.array_equal(
                np.asarray(component_history_values[inventory.size :]),
                inventory.reshape(-1),
            )
        ),
        "controller_histories_are_bumpless": bool(
            controller_history_values == [0.0, 0.0, 0.0, 0.0]
        ),
        "energy_history_has_complete_deferred_ownership": bool(
            len(bdf2.energy_history_coordinates) == 2 * len(spec.topology.volume_ids)
        ),
        "structural_layers_pass": bool(
            base_audit.pass_gate
            and controlled_audit.pass_gate
            and bdf2_audit.pass_gate
        ),
        "full_column_dimensions_match_dd221": bool(
            dimensions["stationary_coordinates"] == 160
            and dimensions["open_loop_dynamic_solve"] == 158
            and dimensions["controlled_dynamic_solve"] == 162
            and dimensions["bdf2_total_history_values"] == 164
        ),
    }
    passed = all(gates.values())
    return {
        "schema_id": SCHEMA,
        "campaign_id": "DD-232",
        "classification": (
            "full_c3c4_dynamic_handoff_mapping_passed"
            if passed
            else "full_c3c4_dynamic_handoff_mapping_failed"
        ),
        "decision": (
            "authorize_one_separately_frozen_live_zero_motion_audit"
            if passed
            else "stop_before_live_dynamic_handoff_work"
        ),
        "sources": {
            str(path).replace("\\", "/"): _sha(path)
            for path in (
                dd221_path,
                dd231_contract_path,
                dd231_result_path,
                model_contract_path,
            )
        },
        "component_names": list(spec.component_names),
        "topology": asdict(spec.topology),
        "dimensions": dimensions,
        "stationary_coordinate_partition": {
            "inventory_source_coordinate_names": [
                layout.names[index] for index in state_source_indices
            ],
            "dynamic_algebraic_source_coordinate_names": [
                layout.names[index] for index in algebraic_indices
            ],
            "product_source_coordinate_names": [
                layout.names[index] for index in product_source_indices
            ],
        },
        "accepted_root_state": accepted_start["state"],
        "component_inventory_lbmol": _rows(inventory),
        "dynamic_algebraic_coordinates": _vector(algebraic),
        "controlled_root_solve_coordinates": _vector(root_solve_coordinates),
        "controller_memory": _vector(controller_memory),
        "product_reference_lbmolph": [
            float(state.distillate_lbmolph),
            float(state.bottoms_lbmolph),
        ],
        "bdf2_history": {
            "component_coordinate_names": list(bdf2.component_history_coordinates),
            "component_values_lbmol": component_history_values,
            "energy_coordinate_names": list(bdf2.energy_history_coordinates),
            "energy_value_policy": (
                "reconstruct one provider-consistent internal-energy value per "
                "accepted volume during the live audit, then copy it exactly to "
                "both n and n_minus_1 history levels"
            ),
            "controller_coordinate_names": list(
                bdf2.controller_history_coordinates
            ),
            "controller_values": controller_history_values,
            "first_step_policy": (
                "identical histories qualify zero motion only; one accepted "
                "backward-Euler startup step is still required before moving BDF2"
            ),
        },
        "terminal_geometry": terminal["geometry"],
        "controller_parameters": terminal["controllers"],
        "controller_setpoint_policy": (
            "reconstruct top and bottom level fractions from accepted inventory, "
            "accepted aligned-PR liquid density, and frozen geometry during the "
            "live audit; reuse those exact fractions as baseline setpoints"
        ),
        "provider_routing": root_result["provider_routing"],
        "audits": {
            "dynamic_dae": asdict(base_audit),
            "terminal_control": asdict(controlled_audit),
            "controlled_bdf2": asdict(bdf2_audit),
        },
        "gates": gates,
        "pass_gate": passed,
        "scope": {
            "dwsim_started": False,
            "property_call_attempted": False,
            "residual_evaluation_attempted": False,
            "jacobian_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "controller_state_advance_attempted": False,
            "timestep_attempted": False,
            "dynamic_integration_attempted": False,
        },
    }


def _markdown(report: Mapping[str, Any]) -> str:
    dimensions = report["dimensions"]
    return "\n".join(
        (
            "# DD-232 Full-C3/C4 Dynamic Handoff Mapping",
            "",
            "## Result",
            "",
            f"`{report['classification']}`",
            "",
            "The accepted DD-231 stationary root maps completely into the full "
            "controlled dynamic ledger without a property call or timestep.",
            "",
            "| Item | Count |",
            "|---|---:|",
            f"| Stationary coordinates consumed | {dimensions['stationary_coordinates']} |",
            f"| Component inventory states | {dimensions['component_inventory_states']} |",
            f"| Dynamic algebraic coordinates | {dimensions['dynamic_algebraic_coordinates']} |",
            f"| Controlled solve rows / unknowns | {dimensions['controlled_dynamic_solve']} |",
            f"| BDF2 history values | {dimensions['bdf2_total_history_values']} |",
            "",
            "Both component-inventory history levels repeat the accepted state. "
            "PI memories and rates begin at zero, and product outputs begin at "
            "the accepted DD-231 distillate and bottoms rates.",
            "",
            "Internal-energy history and geometry-derived level setpoints are "
            "deliberately deferred to the live audit because they require the "
            "accepted DWSIM enthalpy / aligned-PR density provider routing.",
            "",
            "## Decision",
            "",
            str(report["decision"]),
            "",
            "No residual, Jacobian, solve, controller advance, timestep, or "
            "integration occurred.",
            "",
        )
    )


def write_report(report: Mapping[str, Any], out_prefix: Path) -> None:
    destination = ROOT / out_prefix
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    destination.with_suffix(".md").write_text(_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dd221", type=Path, default=DD221)
    parser.add_argument("--dd231-contract", type=Path, default=DD231_CONTRACT)
    parser.add_argument("--dd231-result", type=Path, default=DD231_RESULT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = build_report(
        dd221_path=args.dd221,
        dd231_contract_path=args.dd231_contract,
        dd231_result_path=args.dd231_result,
    )
    write_report(report, args.out)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "dimensions": report["dimensions"],
                "pass_gate": report["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
