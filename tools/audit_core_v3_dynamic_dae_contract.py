#!/usr/bin/env python
"""Generate the structural-only DD-095 Core V3 dynamic DAE contract."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    CONTRACT_NAME,
    CONTRACT_VERSION,
    audit_dynamic_dae_contract,
    build_dynamic_dae_contract,
)


DEFAULT_RESULT = ROOT / "logs/dd094_core_v3_steady_root_20260725.json"
DEFAULT_SOURCE_CONTRACT = (
    ROOT / "logs/dd094_core_v3_steady_root_recovery_contract_20260725.json"
)
DEFAULT_OUT = ROOT / "logs/dd095_core_v3_dynamic_dae_contract_20260725"
SOURCE_RESULT_COMMIT = "c6421a3"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_markdown(report: dict) -> str:
    audit = report["audit"]
    mismatch = report["design_point_qualification"]
    return "\n".join(
        (
            "# DD-095 Core V3 Dynamic DAE Structural Contract",
            "",
            f"- Classification: `{report['classification']}`",
            f"- State coordinates: `{audit['state_coordinate_count']}`",
            f"- Derivative/algebraic solve variables: "
            f"`{audit['derivative_variable_count']} / "
            f"{audit['algebraic_variable_count']}`",
            f"- Rows/rank: `{audit['row_count']} / "
            f"{audit['structural_rank']}`",
            f"- Component/energy conservation: "
            f"`{audit['component_conservation_passed']} / "
            f"{audit['energy_conservation_passed']}`",
            f"- Structural gate: `{audit['pass_gate']}`",
            "",
            "## Storage And Index",
            "",
            f"- Internal energy: `{report['internal_energy_storage']}`",
            f"- Index status: `{report['index_claim']}`",
            "- Independent internal-energy coordinates are intentionally absent.",
            "- A live leading-Jacobian audit is required before an index-1 claim.",
            "",
            "## Open-Loop Ownership",
            "",
            "- Pressure, feed, reflux, reboiler duty, geometry, and DD-094 "
            "product draws are fixed parameters.",
            "- Four vapor links and condenser duty remain energy-owned "
            "algebraic quantities.",
            "- Francis equations are the only internal liquid-flow owner.",
            "- No terminal-level constraints, controllers, profiles, caps, "
            "relaxation, clipping, or fallback are present.",
            "",
            "## Design-Point Qualification",
            "",
            f"- DD-094 drum temperature: "
            f"`{mismatch['accepted_drum_temperature_F']:.6f} F`",
            f"- Frozen source drum temperature: "
            f"`{mismatch['source_drum_temperature_F']:.6f} F`",
            f"- Difference: `{mismatch['temperature_difference_F']:.6f} F`",
            "- DD-094 is a reduced-model feasibility root, not a production "
            "design-point acceptance result.",
            "",
            "## Scope",
            "",
            "- No property evaluation or numerical mass matrix was attempted.",
            "- No nonlinear solve, controller, initializer, or integration was "
            "attempted.",
            "",
            "## Authorization",
            "",
            report["authorization"],
            "",
        )
    )


def run(result_path: Path, source_contract_path: Path, out_prefix: Path) -> dict:
    result = _load_json(result_path)
    source_contract = _load_json(source_contract_path)
    if not result.get("campaign_pass"):
        raise RuntimeError("DD-095 requires an accepted DD-094 root")

    components = tuple(source_contract["source_mapping"]["component_names"])
    contract = build_dynamic_dae_contract(components)
    audit = audit_dynamic_dae_contract(contract)
    endpoint = result["starts"]["canonical_core_v3_seed"][
        "endpoint_evaluation"
    ]["state"]
    amounts = np.asarray(endpoint["liquid_moles_lbmol"], dtype=float)
    composition = np.asarray(endpoint["liquid_mole_fraction"], dtype=float)
    component_inventory = amounts[:, None] * composition
    source_temperature = float(source_contract["reference"]["temperature_F"][0])
    accepted_temperature = float(endpoint["temperature_F"][0])

    implementation_paths = (
        ROOT
        / "src/dynamic_distillation/core_v3/dynamic_dae_contract_v1.py",
        ROOT / "tools/audit_core_v3_dynamic_dae_contract.py",
        ROOT / "tests/test_core_v3_dynamic_dae_contract_v1.py",
    )
    classification = (
        "dd095_core_v3_dynamic_dae_structural_contract_passed"
        if audit.pass_gate
        else "dd095_core_v3_dynamic_dae_structural_contract_failed"
    )
    report = {
        "schema_id": "dd095-core-v3-dynamic-dae-structural-contract-v1",
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "classification": classification,
        "source_result_commit": SOURCE_RESULT_COMMIT,
        "source_result_path": str(result_path.relative_to(ROOT)).replace(
            "\\", "/"
        ),
        "source_result_sha256": _sha256(result_path),
        "source_contract_path": str(source_contract_path.relative_to(ROOT)).replace(
            "\\", "/"
        ),
        "source_contract_sha256": _sha256(source_contract_path),
        "component_names": list(components),
        "state_coordinates": list(contract.state_coordinates),
        "derivative_variables": [
            asdict(variable) for variable in contract.derivative_variables
        ],
        "algebraic_variables": [
            asdict(variable) for variable in contract.algebraic_variables
        ],
        "rows": [asdict(row) for row in contract.rows],
        "fixed_parameters": list(contract.fixed_parameters),
        "accepted_root_component_inventory_lbmol": component_inventory.tolist(),
        "accepted_root_algebraic_state": endpoint,
        "internal_energy_storage": contract.internal_energy_storage,
        "index_claim": contract.index_claim,
        "global_component_form": (
            "sum_j dN[j,k]/dt = F[k] - D*x_D[k] - B*x_B[k]"
        ),
        "global_energy_form": (
            "sum_j dU[j]/dt = H_feed + Q_R + Q_C - D*h_D - B*h_B"
        ),
        "consistent_initialization": {
            "state_source": "DD-094 canonical accepted root",
            "component_inventory_mapping": "N[j,k]=NL[j]*x[j,k]",
            "algebraic_source": "DD-094 canonical accepted root",
            "required_initial_derivative": "dN[j,k]/dt=0",
            "required_live_residual_max_abs": 1.0e-8,
            "required_leading_jacobian_rank": audit.solve_variable_count,
            "required_common_result_at_two_difference_steps": True,
        },
        "design_point_qualification": {
            "status": "reduced_feasibility_root_only",
            "accepted_drum_temperature_F": accepted_temperature,
            "source_drum_temperature_F": source_temperature,
            "temperature_difference_F": accepted_temperature
            - source_temperature,
            "accepted_drum_liquid_mole_fraction": endpoint[
                "liquid_mole_fraction"
            ][0],
            "source_drum_liquid_mole_fraction": source_contract["reference"][
                "liquid_mole_fraction"
            ][0],
            "production_acceptance_deferred": True,
        },
        "next_numerical_gate": {
            "name": "DD-096 live leading-Jacobian and consistent-derivative audit",
            "required_rank": audit.solve_variable_count,
            "finite_difference_steps": [1.0e-5, 5.0e-6],
            "requires_provider_chain_rule_consistency": True,
            "requires_exact_component_and_energy_telescoping": True,
            "permits_dynamic_integration": False,
        },
        "hard_stops": [
            "leading Jacobian is not full rank at either frozen step",
            "independent internal energy is introduced without vapor or pressure storage",
            "DD-094 root is not a zero-derivative consistent state",
            "provider energy derivatives and stream enthalpies use different bases",
            "component or energy telescoping fails",
            "a controller, profile, cap, relaxation, clipping, or fallback is required",
        ],
        "authorization": (
            "DD-096 may be drafted and precommitted as one live leading-"
            "Jacobian, provider-chain-rule, conservation, and consistent-"
            "derivative audit. Numerical mass-matrix implementation and "
            "dynamic integration remain unauthorized."
            if audit.pass_gate
            else "Stop. DD-096 and all dynamic work are unauthorized."
        ),
        "property_evaluation_attempted": False,
        "mass_matrix_evaluation_attempted": False,
        "nonlinear_solve_attempted": False,
        "dynamic_integration_attempted": False,
        "implementation_sha256": {
            str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path)
            for path in implementation_paths
        },
        "audit": asdict(audit),
    }
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    out_prefix.with_suffix(".md").write_text(
        _render_markdown(report), encoding="utf-8"
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument(
        "--source-contract", type=Path, default=DEFAULT_SOURCE_CONTRACT
    )
    parser.add_argument("--out-prefix", type=Path, default=DEFAULT_OUT)
    return parser


if __name__ == "__main__":
    args = _parser().parse_args()
    result = run(args.result, args.source_contract, args.out_prefix)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["audit"]["pass_gate"] else 2)
