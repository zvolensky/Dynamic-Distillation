from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np

from dynamic_distillation.core_v2.pr_provider_authority_contract_v1 import (
    audit_contract_structure,
    build_pr_provider_authority_contract,
    contract_payload,
    evaluate_dd089_evidence,
    flash_internal_coherence,
    phase_region_pass,
)


def _passing_evidence():
    return {
        "direct_fugacity_residual_inf": 4.0e-15,
        "independent_pr_temperature_delta_F": 4.0e-5,
        "independent_pr_vapor_max_abs": 5.0e-9,
        "flash_Kx_reconstruction_max_abs": 5.0e-19,
        "flash_lever_rule_max_abs": 5.0e-15,
        "beta": 6.5e-4,
        "stable_vapor": False,
        "fresh_process_repeatability_max_abs": 0.0,
        "mixed_basis_reported_separately": True,
        "cross_interface_y_reported_without_equality_gate": True,
        "fallback_used": False,
    }


def test_dd090_contract_has_complete_nonoverlapping_authority():
    contract = build_pr_provider_authority_contract()
    audit = audit_contract_structure(contract)

    assert audit["pass"]
    assert audit["quantity_count"] == 11
    assert audit["duplicate_quantities"] == ()
    assert audit["missing_quantities"] == ()
    assert contract.direct_fugacity_is_primary
    assert contract.independent_pr_is_validation_only
    assert contract.tp_flash_is_phase_region_authority


def test_dd090_contract_payload_is_json_native_and_round_trips():
    payload = contract_payload(build_pr_provider_authority_contract())

    assert json.loads(json.dumps(payload)) == payload


def test_dd090_prohibits_mixed_basis_and_interface_fallback():
    contract = build_pr_provider_authority_contract()
    flash_K = next(
        item
        for item in contract.quantities
        if item.quantity == "tp_flash_K_values"
    )

    assert contract.mixed_basis_equilibrium_gate_prohibited
    assert not contract.cross_interface_y_equality_required
    assert not contract.fallback_between_direct_and_flash_permitted
    assert any("K_flash*z" in use for use in flash_K.forbidden_uses)


def test_dd090_flash_coherence_uses_flash_liquid_basis():
    x = np.asarray([0.69, 0.29, 0.02])
    y = np.asarray([0.84, 0.15, 0.01])
    K = y / x
    beta = 0.001
    z = (1.0 - beta) * x + beta * y
    audit = flash_internal_coherence(
        overall_z=z,
        flash_x=x,
        flash_y=y,
        flash_K=K,
        beta=beta,
    )

    assert audit["Kx_reconstruction_max_abs"] < 1.0e-14
    assert audit["lever_rule_max_abs"] < 1.0e-14
    assert audit["mixed_basis_shift_max_abs"] > 0.0


def test_dd090_evidence_gate_accepts_provider_roles_not_y_equality():
    contract = build_pr_provider_authority_contract()
    evidence = _passing_evidence()
    evidence["direct_y_minus_flash_y_max_abs"] = 4.3e-5
    result = evaluate_dd089_evidence(contract, evidence)

    assert result["pass"]
    assert result["failed_checks"] == ()
    assert "direct_y_minus_flash_y_max_abs" not in result["checks"]


def test_dd090_phase_region_rejects_stable_vapor_and_large_beta():
    contract = build_pr_provider_authority_contract()

    assert phase_region_pass(beta=6.5e-4, stable_vapor=False, contract=contract)
    assert not phase_region_pass(beta=6.5e-4, stable_vapor=True, contract=contract)
    assert not phase_region_pass(beta=2.0e-3, stable_vapor=False, contract=contract)


def test_dd090_fails_if_mixed_basis_is_reintroduced_as_gate():
    contract = build_pr_provider_authority_contract()
    evidence = _passing_evidence()
    evidence["mixed_basis_reported_separately"] = False
    result = evaluate_dd089_evidence(contract, evidence)

    assert not result["pass"]
    assert result["failed_checks"] == ("mixed_basis_not_used_as_gate",)


def test_dd090_module_has_no_solver_or_integrator_import():
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "src"
        / "dynamic_distillation"
        / "core_v2"
        / "pr_provider_authority_contract_v1.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not any(name.startswith("scipy") for name in imported)
    assert not any("steady_solve" in name for name in imported)
    assert not any("residual" in name for name in imported)
