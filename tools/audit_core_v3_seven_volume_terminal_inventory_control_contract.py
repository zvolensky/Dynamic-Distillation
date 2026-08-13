#!/usr/bin/env python
"""Generate DD-184's structural terminal-inventory control contract."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (  # noqa: E402
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (  # noqa: E402
    build_column_topology,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (  # noqa: E402
    CONTRACT_NAME,
    CONTRACT_VERSION,
    TerminalPIParameters,
    TerminalVesselGeometry,
    audit_terminal_inventory_control_contract,
    build_terminal_inventory_control_contract,
)


SOURCE = (
    ROOT / "logs/dd183_core_v3_seven_volume_parallel_short_trajectory_20260813.json"
)
OUT = (
    ROOT
    / "logs/dd184_core_v3_seven_volume_terminal_inventory_control_contract_20260813"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_markdown(report: dict) -> str:
    audit = report["audit"]
    return "\n".join(
        (
            "# DD-184 Seven-Volume Terminal Inventory Control Contract",
            "",
            "## Verdict",
            "",
            f"**Structural gate: `{audit['pass_gate']}`.** The accepted open-loop "
            "seven-volume DAE now has a square, topology-generic terminal "
            "inventory-control ownership ledger.",
            "",
            "## Ledger",
            "",
            f"- Physical volumes: `{audit['volume_count']}`",
            f"- Differential states: `{audit['state_coordinate_count']}`",
            f"- Derivative variables: `{audit['derivative_variable_count']}`",
            f"- Algebraic variables: `{audit['algebraic_variable_count']}`",
            f"- Rows / structural rank: `{audit['row_count']} / "
            f"{audit['structural_rank']}`",
            f"- Structural nullity: `{audit['structural_nullity']}`",
            f"- Controller states / rates / outputs / rows: "
            f"`{audit['controller_state_count']} / "
            f"{audit['controller_rate_count']} / "
            f"{audit['controller_output_count']} / "
            f"{audit['controller_row_count']}`",
            "",
            "## Ownership Change",
            "",
            "- Distillate and bottoms rates are no longer fixed parameters.",
            "- Positive log-ratio controller outputs own the live product rates.",
            "- The top output enters only top component and energy balances.",
            "- The bottom output enters only bottom component and energy balances.",
            "- Product component rates use each terminal's live liquid composition.",
            "- Two PI memory states supply integral action; geometry-derived level "
            "fractions are the controlled variables.",
            "- Every interior balance, equilibrium relation, Francis equation, and "
            "energy-owned vapor link is unchanged.",
            "",
            "## Geometry And Parameters",
            "",
            "The structural contract carries the established C3/C4 vessel "
            "geometry and prior positive PI constants so units and equation signs "
            "are explicit. DD-184 does not qualify those constants as tuned values.",
            "",
            "## Scope Boundary",
            "",
            "No property evaluation, residual evaluation, Jacobian evaluation, "
            "nonlinear solve, controller execution, timestep selection, or dynamic "
            "integration occurred. Passing does not show that the controlled DAE is "
            "numerically conditioned or dynamically well tuned.",
            "",
            "## Decision",
            "",
            report["decision"],
            "",
        )
    )


def run(source_path: Path, out_prefix: Path) -> dict:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if (
        not source.get("pass_gate")
        or source.get("decision")
        != "authorize_persistent_parallel_production_step_path"
    ):
        raise RuntimeError("DD-184 requires the accepted DD-183 trajectory proof")

    components = ("Propane", "n-Butane", "n-Pentane")
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    base = build_dynamic_dae_contract(
        components,
        topology=topology,
        accepted_root_artifact=(
            "logs/dd169_core_v3_seven_volume_steady_root_20260807.json"
        ),
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    geometry = TerminalVesselGeometry(
        top_diameter_ft=12.1,
        top_tangent_length_ft=36.3,
        top_head_shape="two_hemispherical",
        bottom_diameter_ft=18.1759,
        bottom_height_ft=12.0,
    )
    controllers = TerminalPIParameters(
        top_kc=0.5,
        top_ti_sec=120.0,
        bottom_kc=8.0,
        bottom_ti_sec=120.0,
        product_rate_ratio_bounds=(0.25, 2.0),
    )
    contract = build_terminal_inventory_control_contract(
        base,
        geometry=geometry,
        controllers=controllers,
    )
    audit = audit_terminal_inventory_control_contract(contract)
    decision = (
        "Authorize one separately frozen live zero-time residual and leading-"
        "Jacobian audit at the DD-169 root. Controller tuning, timestepping, and "
        "controlled trajectories remain unauthorized."
        if audit.pass_gate
        else "Stop. Repair the controller ownership ledger before live evaluation."
    )
    report = {
        "schema_id": "dd184-core-v3-seven-volume-terminal-inventory-control-contract-v1",
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "classification": (
            "terminal_inventory_control_structural_gate_passed"
            if audit.pass_gate
            else "terminal_inventory_control_structural_gate_failed"
        ),
        "campaign_pass": bool(audit.pass_gate),
        "decision": decision,
        "source": {
            "path": str(source_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256(source_path),
        },
        "component_names": list(components),
        "topology": asdict(topology),
        "geometry": asdict(geometry),
        "controllers": asdict(controllers),
        "parameter_provenance": {
            "geometry": "established C3/C4 workbook vessel geometry used by DD-123",
            "top_kc": "prior C3/C4 top level-controller definition",
            "top_ti_sec": "prior C3/C4 controller default",
            "bottom_kc": "prior C3/C4 bottom level-controller definition",
            "bottom_ti_sec": "prior C3/C4 bottom level-controller definition",
            "qualification": "structural validity only; no tuning acceptance",
        },
        "state_coordinates": list(contract.state_coordinates),
        "derivative_variables": [
            asdict(item) for item in contract.derivative_variables
        ],
        "algebraic_variables": [asdict(item) for item in contract.algebraic_variables],
        "rows": [asdict(item) for item in contract.rows],
        "fixed_parameters": list(contract.fixed_parameters),
        "product_output_variables": list(contract.product_output_variables),
        "measurement_definition": contract.measurement_definition,
        "controller_definition": contract.controller_definition,
        "audit": asdict(audit),
        "scope": {
            "property_evaluation_attempted": False,
            "residual_evaluation_attempted": False,
            "jacobian_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "controller_execution_attempted": False,
            "timestep_selected": False,
            "dynamic_integration_attempted": False,
        },
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(_render_markdown(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    report = run(args.source.resolve(), args.out.resolve())
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "rows": report["audit"]["row_count"],
                "rank": report["audit"]["structural_rank"],
                "pass_gate": report["audit"]["pass_gate"],
                "decision": report["decision"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
