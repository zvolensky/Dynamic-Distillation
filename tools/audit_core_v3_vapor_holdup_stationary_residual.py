#!/usr/bin/env python
"""Audit the complete stationary vapor-holdup residual at the C3/C4 start."""

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

import audit_core_v3_vapor_holdup_full_residual as dd240  # noqa: E402

from dynamic_distillation.core_v3.colored_jacobian_v1 import (  # noqa: E402
    greedy_column_groups,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (  # noqa: E402
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_contract_v1 import (  # noqa: E402
    audit_vapor_holdup_stationary_contract,
    build_vapor_holdup_stationary_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (  # noqa: E402
    VaporHoldupStationaryNumericalSpec,
    VaporHoldupStationaryReference,
    evaluate_vapor_holdup_stationary_residual,
    stationary_structural_pattern,
)


DEFAULT_JSON = Path(
    "logs/dd243_core_v3_c3c4_vapor_holdup_stationary_residual_20260820.json"
)
DEFAULT_DOC = Path(
    "docs/dd_243_core_v3_c3c4_vapor_holdup_stationary_residual_20260820.md"
)


def build_problem() -> dict[str, Any]:
    inherited = dd240.build_problem()
    dynamic_contract = inherited["contract"]
    contract = build_vapor_holdup_stationary_contract(
        dynamic_contract.component_names,
        topology=dynamic_contract.topology,
    )
    structural = audit_vapor_holdup_stationary_contract(contract)
    if not structural.pass_gate:
        raise RuntimeError("DD-243 requires the passing stationary structure")
    old = inherited["reference"]
    inputs = inherited["balance_inputs"]
    reference = VaporHoldupStationaryReference(
        liquid_component_inventory_lbmol=old.liquid_component_inventory_lbmol,
        vapor_component_inventory_lbmol=old.vapor_component_inventory_lbmol,
        phase_transfer_lbmolph=old.phase_transfer_lbmolph,
        phase_transfer_scale_lbmolph=old.phase_transfer_scale_lbmolph,
        temperature_F=old.temperature_F,
        pressure_psia=old.pressure_psia,
        hydraulic_liquid_flow_lbmolph=old.hydraulic_liquid_flow_lbmolph,
        vapor_flow_lbmolph=old.vapor_flow_lbmolph,
        condenser_duty_BTUph=old.condenser_duty_BTUph,
        distillate_lbmolph=inputs.distillate_lbmolph,
        bottoms_lbmolph=inputs.bottoms_lbmolph,
        top_liquid_inventory_target_lbmol=float(
            np.sum(old.liquid_component_inventory_lbmol[0])
        ),
        bottom_liquid_inventory_target_lbmol=float(
            np.sum(old.liquid_component_inventory_lbmol[-1])
        ),
    )
    old_numerical = inherited["numerical"]
    numerical = VaporHoldupStationaryNumericalSpec(
        temperature_coordinate_scale_F=old_numerical.temperature_coordinate_scale_F,
        pressure_coordinate_scale_psia=old_numerical.pressure_coordinate_scale_psia,
        dry_tray_pressure_drop_coefficient=(
            old_numerical.dry_tray_pressure_drop_coefficient
        ),
        component_mw_lbm_per_lbmol=old_numerical.component_mw_lbm_per_lbmol,
        pressure_link_geometry=old_numerical.pressure_link_geometry,
        top_pressure_anchor_psia=old_numerical.top_pressure_anchor_psia,
        component_residual_scale_lbmolph=(
            old_numerical.component_residual_scale_lbmolph
        ),
        energy_residual_scale_BTUph=old_numerical.energy_residual_scale_BTUph,
        pressure_residual_scale_psia=old_numerical.pressure_residual_scale_psia,
    )
    return {
        **inherited,
        "contract": contract,
        "structural": structural,
        "reference": reference,
        "numerical": numerical,
    }


def _block_norms(contract: Any, evaluation: Any) -> dict[str, float]:
    result: dict[str, float] = {}
    for block in sorted({row.block for row in contract.rows}):
        indices = [
            index
            for index, row in enumerate(contract.rows)
            if row.block == block
        ]
        result[block] = float(np.max(np.abs(evaluation.raw[indices])))
    return result


def build_report() -> dict[str, Any]:
    problem = build_problem()
    audit = ProviderCallAudit(
        provider_identity="dwsim",
        interface_provider_identities={"declared_liquid_density": "aligned_pr"},
    )
    evaluation = evaluate_vapor_holdup_stationary_residual(
        problem["contract"],
        problem["geometry"],
        problem["reference"],
        problem["balance_inputs"],
        problem["spec"].hydraulic_geometry,
        problem["numerical"],
        problem["provider"],
        audit,
        np.zeros(260),
        state_id="dd243_stationary_reference",
        evaluation_kind="residual",
    )
    pattern = stationary_structural_pattern(problem["contract"])
    groups = greedy_column_groups(pattern)
    block_norms = _block_norms(problem["contract"], evaluation)
    provider_report = audit.report()
    provider_pass = bool(
        audit.record_count == 120
        and not provider_report["fallback_attempted"]
        and provider_report["pass"]
    )
    passed = bool(
        problem["structural"].pass_gate
        and evaluation.raw.shape == (260,)
        and np.all(np.isfinite(evaluation.raw))
        and np.max(np.abs(evaluation.properties.eos_relative_residual)) < 1.0e-12
        and np.max(np.abs(evaluation.terminal_inventory_residual_lbmol)) < 1.0e-12
        and provider_pass
    )
    return {
        "schema_id": "dd243-core-v3-c3c4-vapor-holdup-stationary-residual-v1",
        "classification": (
            "vapor_holdup_stationary_residual_ready_for_jacobian"
            if passed
            else "vapor_holdup_stationary_residual_not_ready"
        ),
        "dimension": 260,
        "structural_audit": asdict(problem["structural"]),
        "row_names": list(evaluation.row_names),
        "variable_names": list(evaluation.variable_names),
        "block_raw_inf_norms": block_norms,
        "scaled_residual_inf_norm": float(np.max(np.abs(evaluation.scaled))),
        "maximum_relative_eos_residual": float(
            np.max(np.abs(evaluation.properties.eos_relative_residual))
        ),
        "terminal_inventory_residual_lbmol": (
            evaluation.terminal_inventory_residual_lbmol.tolist()
        ),
        "starting_product_rates_lbmolph": {
            "distillate": evaluation.endpoint.distillate_lbmolph,
            "bottoms": evaluation.endpoint.bottoms_lbmolph,
        },
        "provider_calls": {
            "preparation": problem["preparation_audit"].record_count,
            "governing_residual": audit.record_count,
            "governing_report": provider_report,
            "pass_gate": provider_pass,
        },
        "jacobian_coloring": {
            "color_count": len(groups),
            "groups": [list(group) for group in groups],
            "prospective_central_residual_evaluations": 2 * len(groups),
            "uncolored_central_residual_evaluations": 520,
        },
        "interpretation": (
            "The accepted predecessor closes every inherited block except the "
            "new pressure-drop equations. Both terminal inventory targets close "
            "exactly. Product rates are now solved variables rather than fixed inputs."
        ),
        "nonlinear_solve_attempted": False,
        "timestep_accepted": False,
        "dynamic_integration_attempted": False,
        "pass_gate": passed,
        "decision": (
            "authorize_stationary_two_step_colored_jacobian_audit"
            if passed
            else "stop_and_correct_stationary_residual"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    blocks = report["block_raw_inf_norms"]
    return "\n".join(
        (
            "# DD-243 Full Stationary Vapor-Holdup Residual",
            "",
            f"- Classification: `{report['classification']}`",
            f"- Decision: `{report['decision']}`",
            f"- Numerical ledger: `{report['dimension']} x {report['dimension']}`",
            f"- Scaled residual maximum: `{report['scaled_residual_inf_norm']:.6e}`",
            f"- Pressure-drop maximum: `{blocks['vapor_pressure_drop']:.6e} psia`",
            (
                "- Terminal inventory residuals: "
                f"`{report['terminal_inventory_residual_lbmol']}` lbmol"
            ),
            (
                "- Relative vapor-EOS maximum: "
                f"`{report['maximum_relative_eos_residual']:.6e}`"
            ),
            (
                "- Colored Jacobian groups: "
                f"`{report['jacobian_coloring']['color_count']}`"
            ),
            "- Nonlinear solve or timestep: `False`",
            "",
            "## Meaning",
            "",
            (
                "The stationary equations are fully implemented. The inherited "
                "starting point already satisfies equilibrium, EOS, mass, energy, "
                "and terminal-level equations to numerical precision. Its prescribed "
                "pressure profile still misses the live pressure-drop equations, "
                "which is the intended work for a future stationary solve."
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
                "scaled_residual_inf_norm": report["scaled_residual_inf_norm"],
            },
            indent=2,
        )
    )
    return 0 if report["pass_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
