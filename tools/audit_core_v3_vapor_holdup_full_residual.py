#!/usr/bin/env python
"""Audit the complete 258-row vapor-holdup residual at the accepted C3/C4 state."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_core_v3_aligned_pr_density_parity as dd229  # noqa: E402
import audit_core_v3_provider_governed_numerical as dd092  # noqa: E402
import run_core_v3_full_c3c4_steady_root as dd223  # noqa: E402

from dynamic_distillation.column_spec_builder_v1 import (  # noqa: E402
    build_column_spec_from_case,
)
from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    greedy_column_groups,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (  # noqa: E402
    PressureLinkGeometry,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (  # noqa: E402
    VaporHoldupBalanceInputs,
    evaluate_two_phase_transport,
    stationary_phase_transfer_from_vapor_transport,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_dae_contract,
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (  # noqa: E402
    build_column_vapor_geometry,
    gross_capacity_mapping,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (  # noqa: E402
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (  # noqa: E402
    evaluate_vapor_holdup_properties,
)
from dynamic_distillation.excel_case_loader_v1 import (  # noqa: E402
    load_case_from_excel,
)


SOURCE_ROOT = Path("logs/dd231_core_v3_full_c3c4_aligned_density_root_20260815.json")
SOURCE_MODEL_CONTRACT = dd223.SOURCE_CONTRACT
DEFAULT_JSON = Path("logs/dd240_core_v3_c3c4_vapor_holdup_full_residual_20260820.json")
DEFAULT_DOC = Path("docs/dd_240_core_v3_c3c4_vapor_holdup_full_residual_20260820.md")


def _load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _pressure_geometry(
    column: Any,
    source: dict[str, Any],
    topology: Any,
) -> tuple[PressureLinkGeometry, ...]:
    roles = tuple(source["source_mapping"]["roles"])
    stages = tuple(
        int(value) - 1 for value in source["source_mapping"]["source_stage_1based"]
    )
    geometry = column.geometry
    if geometry is None:
        raise RuntimeError("DD-240 requires declared pressure-link geometry")
    result = []
    for source_volume, _destination, _symbol in topology.vapor_links:
        source_stage = stages[roles.index(source_volume)]
        result.append(
            PressureLinkGeometry(
                active_area_ft2=float(
                    geometry.active_area_ft2_per_stage[source_stage]
                ),
                tray_area_ft2=float(geometry.area_ft2_per_stage[source_stage]),
                weir_height_in=float(
                    geometry.weir_height_in_per_stage[source_stage]
                ),
                include_liquid_head=source_volume != topology.bottom_volume,
            )
        )
    return tuple(result)


def build_problem() -> dict[str, Any]:
    source = _load(SOURCE_MODEL_CONTRACT)
    root = _load(SOURCE_ROOT)
    if not root.get("campaign_pass"):
        raise RuntimeError("DD-240 requires the accepted DD-231 root")
    state = root["starts"]["source_mapped_seed"]["state"]
    workbook, dwsim_provider, spec, _old_reference = dd223._source_model(source)
    case = load_case_from_excel(str(workbook))
    column = build_column_spec_from_case(case)
    geometry = build_column_vapor_geometry(column, case.specs, spec.topology)
    topology = build_vapor_holdup_topology(
        column=spec.topology,
        vapor_volume_ft3=gross_capacity_mapping(geometry),
    )
    contract = build_vapor_holdup_dae_contract(
        spec.component_names,
        topology=topology,
    )
    structural = audit_vapor_holdup_dae_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-240 requires the passing vapor-holdup structure")
    liquid_moles = np.asarray(state["liquid_moles_lbmol"], dtype=float)
    liquid_x = np.asarray(state["liquid_mole_fraction"], dtype=float)
    liquid_inventory = liquid_moles[:, np.newaxis] * liquid_x
    vapor_y = np.vstack(
        (
            np.asarray(state["bubble_vapor_mole_fraction"], dtype=float),
            np.asarray(state["vapor_mole_fraction"], dtype=float),
        )
    )
    provider = dd229.DensityRoutedProvider(
        dwsim_provider,
        dd092._independent_provider(source),
    )
    preparation_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    reference_properties = evaluate_vapor_holdup_properties(
        geometry,
        liquid_inventory,
        liquid_x,
        vapor_y,
        state["temperature_F"],
        spec.pressure_psia,
        provider,
        preparation_audit,
        state_id="dd240:reference",
    )
    molecular_weight = preparation_audit.component_molecular_weights(
        provider,
        caller="dd240_fixed_component_data",
        state_id="dd240:preparation",
        evaluation_kind="preparation",
    )
    balance_inputs = VaporHoldupBalanceInputs(
        topology=spec.topology,
        feed_component_lbmolph=np.asarray(spec.feed_component_lbmolph, dtype=float),
        feed_enthalpy_BTUph=float(spec.feed_enthalpy_BTUph),
        reflux_lbmolph=float(spec.reflux_lbmolph),
        distillate_lbmolph=float(state["distillate_lbmolph"]),
        bottoms_lbmolph=float(state["bottoms_lbmolph"]),
        condenser_duty_BTUph=float(state["condenser_duty_BTUph"]),
        reboiler_duty_BTUph=float(spec.reboiler_duty_BTUph),
    )
    reference_transport = evaluate_two_phase_transport(
        balance_inputs,
        liquid_x,
        vapor_y,
        state["hydraulic_liquid_flow_lbmolph"],
        state["vapor_flow_lbmolph"],
        reference_properties.liquid_enthalpy_BTU_lbmol,
        reference_properties.vapor_enthalpy_BTU_lbmol,
    )
    phase_transfer = stationary_phase_transfer_from_vapor_transport(
        reference_transport
    )
    component_scale = np.maximum(
        np.asarray(spec.feed_component_lbmolph, dtype=float),
        1.0,
    )
    transfer_scale = np.maximum(np.abs(phase_transfer), component_scale[np.newaxis, :])
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=(
            reference_properties.vapor_component_inventory_lbmol
        ),
        phase_transfer_lbmolph=phase_transfer,
        phase_transfer_scale_lbmolph=transfer_scale,
        temperature_F=np.asarray(state["temperature_F"], dtype=float),
        pressure_psia=np.asarray(spec.pressure_psia, dtype=float),
        hydraulic_liquid_flow_lbmolph=np.asarray(
            state["hydraulic_liquid_flow_lbmolph"], dtype=float
        ),
        vapor_flow_lbmolph=np.asarray(state["vapor_flow_lbmolph"], dtype=float),
        condenser_duty_BTUph=float(state["condenser_duty_BTUph"]),
        total_stored_energy_BTU=reference_properties.total_stored_energy_BTU,
    )
    numerical = VaporHoldupImplicitNumericalSpec(
        timestep_sec=1.0,
        temperature_coordinate_scale_F=10.0,
        pressure_coordinate_scale_psia=1.0,
        dry_tray_pressure_drop_coefficient=40.0,
        component_mw_lbm_per_lbmol=np.asarray(molecular_weight, dtype=float),
        pressure_link_geometry=_pressure_geometry(column, source, spec.topology),
        top_pressure_anchor_psia=float(spec.pressure_psia[0]),
        component_residual_scale_lbmolph=component_scale,
        energy_residual_scale_BTUph=max(
            abs(float(spec.feed_enthalpy_BTUph)),
            abs(float(spec.reboiler_duty_BTUph)),
            abs(float(state["condenser_duty_BTUph"])),
        ),
        pressure_residual_scale_psia=1.0,
    )
    return {
        "source": source,
        "state": state,
        "provider": provider,
        "spec": spec,
        "geometry": geometry,
        "contract": contract,
        "structural": structural,
        "reference": reference,
        "balance_inputs": balance_inputs,
        "numerical": numerical,
        "preparation_audit": preparation_audit,
    }


def build_report() -> dict[str, Any]:
    problem = build_problem()
    contract = problem["contract"]
    point = np.zeros(len(contract.derivative_variables) + len(contract.algebraic_variables))
    call_audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    evaluation = evaluate_vapor_holdup_implicit_residual(
        contract,
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        problem["provider"],
        call_audit,
        point,
        state_id="dd240:accepted-root",
        evaluation_kind="residual",
    )
    block_norms: dict[str, float] = {}
    for block in sorted({row.block for row in contract.rows}):
        indices = [index for index, row in enumerate(contract.rows) if row.block == block]
        block_norms[block] = float(np.max(np.abs(evaluation.raw[indices])))
    pattern = vapor_holdup_structural_pattern(contract)
    groups = greedy_column_groups(pattern)
    component_telescoping = float(
        np.max(
            np.abs(
                evaluation.balances.global_component_telescoping_error_lbmolph
            )
        )
    )
    energy_telescoping = abs(
        float(evaluation.balances.global_energy_telescoping_error_BTUph)
    )
    pressure_max = float(np.max(np.abs(evaluation.pressure_drop.residual_psia)))
    inherited_blocks_pass = bool(
        block_norms["liquid_component_balance"] <= 1.0e-7
        and block_norms["vapor_component_balance"] <= 1.0e-7
        and block_norms["full_phase_equilibrium"] <= 1.0e-8
        and np.max(np.abs(evaluation.properties.eos_relative_residual)) <= 1.0e-12
        and block_norms["total_energy_balance"] <= 1.0e-4
        and block_norms["francis_hydraulics"] <= 1.0e-6
        and block_norms["pressure_anchor"] <= 1.0e-12
    )
    provider_pass = bool(
        call_audit.record_count == 120
        and not call_audit.fallback_attempted
        and all(
            record.evaluation_kind == "residual" for record in call_audit.records
        )
    )
    passed = bool(
        problem["structural"].pass_gate
        and evaluation.raw.shape == (258,)
        and pattern.shape == (258, 258)
        and inherited_blocks_pass
        and pressure_max < 1.0
        and component_telescoping <= 1.0e-10
        and energy_telescoping <= 1.0e-6
        and provider_pass
    )
    return {
        "schema_id": "dd240-core-v3-c3c4-vapor-holdup-full-residual-v1",
        "classification": (
            "vapor_holdup_full_residual_ready_for_jacobian"
            if passed
            else "vapor_holdup_full_residual_not_ready"
        ),
        "dimension": 258,
        "structural_audit": asdict(problem["structural"]),
        "row_names": list(evaluation.row_names),
        "variable_names": list(evaluation.variable_names),
        "block_raw_inf_norms": block_norms,
        "scaled_residual_inf_norm": float(np.max(np.abs(evaluation.scaled))),
        "maximum_relative_eos_residual": float(
            np.max(np.abs(evaluation.properties.eos_relative_residual))
        ),
        "maximum_pressure_drop_residual_psia": pressure_max,
        "pressure_drop_residual_psia": [
            float(value) for value in evaluation.pressure_drop.residual_psia
        ],
        "component_telescoping_error_lbmolph": component_telescoping,
        "energy_telescoping_error_BTUph": energy_telescoping,
        "provider_calls": {
            "preparation": problem["preparation_audit"].record_count,
            "governing_residual": call_audit.record_count,
            "fallback_attempted": call_audit.fallback_attempted,
            "pass_gate": provider_pass,
        },
        "jacobian_coloring": {
            "color_count": len(groups),
            "groups": [list(group) for group in groups],
            "prospective_central_residual_evaluations": 2 * len(groups),
            "uncolored_central_residual_evaluations": 2 * 258,
        },
        "interpretation": (
            "The inherited stationary blocks close. The nonzero pressure-drop block "
            "is expected because DD-231 prescribed pressure; the successor must solve it."
        ),
        "nonlinear_solve_attempted": False,
        "timestep_accepted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_two_step_colored_jacobian_audit"
            if passed
            else "stop_and_correct_full_residual"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    blocks = report["block_raw_inf_norms"]
    return "\n".join(
        (
            "# DD-240 Full Vapor-Holdup Residual",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Numerical ledger: `{report['dimension']} x {report['dimension']}`",
            f"- Liquid balance maximum: `{blocks['liquid_component_balance']:.6e} lbmol/h`",
            f"- Vapor balance maximum: `{blocks['vapor_component_balance']:.6e} lbmol/h`",
            f"- Fugacity maximum: `{blocks['full_phase_equilibrium']:.6e}`",
            f"- Relative EOS maximum: `{report['maximum_relative_eos_residual']:.6e}`",
            f"- Energy maximum: `{blocks['total_energy_balance']:.6e} BTU/h`",
            f"- Francis maximum: `{blocks['francis_hydraulics']:.6e} lbmol/h`",
            f"- Pressure-drop maximum: `{report['maximum_pressure_drop_residual_psia']:.6e} psia`",
            f"- Jacobian colors: `{report['jacobian_coloring']['color_count']}`",
            f"- Governing property calls: `{report['provider_calls']['governing_residual']}`",
            "",
            "The inherited stationary blocks close. Pressure drop does not close because the DD-231 root used a prescribed pressure profile. That visible mismatch is the physical work assigned to the successor pressure/flow equations.",
            "",
            "No nonlinear solve, accepted timestep, or integration occurred.",
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
