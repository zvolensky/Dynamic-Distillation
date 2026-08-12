#!/usr/bin/env python
"""Generate the structural-only DD-170 seven-volume dynamic DAE contract."""

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
    CONTRACT_NAME,
    CONTRACT_VERSION,
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (  # noqa: E402
    build_column_topology,
)


DEFAULT_ROOT = ROOT / "logs/dd169_core_v3_seven_volume_steady_root_20260807.json"
DEFAULT_OUT = ROOT / "logs/dd170_core_v3_seven_volume_dynamic_dae_contract_20260812"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_markdown(report: dict) -> str:
    audit = report["audit"]
    topology = report["topology"]
    return "\n".join(
        (
            "# DD-170 Seven-Volume Dynamic DAE Structural Contract",
            "",
            "## Verdict",
            "",
            f"**Structural gate: `{audit['pass_gate']}`.** The accepted DD-169 "
            "stationary root has been mapped into a conserved, open-loop "
            "dynamic DAE ledger without executing dynamics.",
            "",
            "## Ledger",
            "",
            f"- Physical volumes: `{len(topology['volume_ids'])}`",
            f"- Component inventory coordinates: "
            f"`{audit['state_coordinate_count']}`",
            f"- Derivative variables: `{audit['derivative_variable_count']}`",
            f"- Algebraic variables: `{audit['algebraic_variable_count']}`",
            f"- Rows / structural rank: `{audit['row_count']} / "
            f"{audit['structural_rank']}`",
            f"- Structural nullity: `{audit['structural_nullity']}`",
            "",
            "| Equation block | Count |",
            "|---|---:|",
            f"| Component inventory balances | {audit['component_balance_count']} |",
            f"| Energy balances | {audit['energy_balance_count']} |",
            f"| Full fugacity equilibrium | {audit['full_fugacity_count']} |",
            f"| Francis liquid hydraulics | {audit['francis_count']} |",
            f"| Condenser bubble equations | {audit['condenser_bubble_count']} |",
            "",
            "## Ownership",
            "",
            "- Differential states are component inventories only.",
            "- Internal energy is derived from inventory, temperature, and "
            "provider properties; it is not an independent coordinate.",
            "- Temperatures, phase compositions, liquid flows, vapor flows, "
            "and condenser duty are algebraic variables.",
            "- Pressure, feed, reflux, reboiler duty, geometry, and accepted "
            "DD-169 product rates are fixed open-loop parameters.",
            "- No controller, terminal amount constraint, imported profile, "
            "flow cap, relaxation, clipping, projection, or fallback is present.",
            "",
            "## Scope Boundary",
            "",
            "No property evaluation, numerical mass-matrix evaluation, "
            "nonlinear solve, timestep selection, controller execution, or "
            "dynamic integration occurred in DD-170.",
            "",
            "## Decision",
            "",
            report["decision"],
            "",
        )
    )


def run(root_path: Path, out_prefix: Path) -> dict:
    source = json.loads(root_path.read_text(encoding="utf-8"))
    if not source.get("campaign_pass"):
        raise RuntimeError("DD-170 requires the accepted DD-169 campaign root")

    components = ("Propane", "n-Butane", "n-Pentane")
    topology = build_column_topology(
        rectifying_volume_count=2,
        stripping_volume_count=2,
    )
    contract = build_dynamic_dae_contract(
        components,
        topology=topology,
        accepted_root_artifact=str(root_path.relative_to(ROOT)).replace("\\", "/"),
        product_flow_parameters=("D_dd169_root", "B_dd169_root"),
    )
    audit = audit_dynamic_dae_contract(contract)
    classification = (
        "seven_volume_dynamic_dae_structural_contract_passed"
        if audit.pass_gate
        else "seven_volume_dynamic_dae_structural_contract_failed"
    )
    decision = (
        "Authorize one frozen live numerical leading-Jacobian and consistent-"
        "derivative audit. Dynamic integration remains unauthorized."
        if audit.pass_gate
        else "Stop. Repair the structural ledger before any numerical audit."
    )
    report = {
        "schema_id": "dd170-core-v3-seven-volume-dynamic-dae-contract-v1",
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "classification": classification,
        "decision": decision,
        "source_root_path": str(root_path.relative_to(ROOT)).replace("\\", "/"),
        "source_root_sha256": _sha256(root_path),
        "component_names": list(components),
        "topology": asdict(topology),
        "state_coordinates": list(contract.state_coordinates),
        "derivative_variables": [
            asdict(variable) for variable in contract.derivative_variables
        ],
        "algebraic_variables": [
            asdict(variable) for variable in contract.algebraic_variables
        ],
        "rows": [asdict(row) for row in contract.rows],
        "fixed_parameters": list(contract.fixed_parameters),
        "accepted_root_artifact": contract.accepted_root_artifact,
        "internal_energy_storage": contract.internal_energy_storage,
        "index_claim": contract.index_claim,
        "audit": asdict(audit),
        "scope": {
            "property_evaluation_attempted": False,
            "mass_matrix_evaluation_attempted": False,
            "nonlinear_solve_attempted": False,
            "timestep_selected": False,
            "controller_execution_attempted": False,
            "dynamic_integration_attempted": False,
        },
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(
        _render_markdown(report), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = run(args.root.resolve(), args.out.resolve())
    print(json.dumps({
        "classification": report["classification"],
        "rows": report["audit"]["row_count"],
        "rank": report["audit"]["structural_rank"],
        "pass_gate": report["audit"]["pass_gate"],
        "decision": report["decision"],
    }, indent=2))


if __name__ == "__main__":
    main()
