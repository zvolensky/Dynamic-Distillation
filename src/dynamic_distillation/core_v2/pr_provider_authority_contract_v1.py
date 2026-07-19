"""Prospective thermodynamic authority contract for PR property interfaces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class QuantityAuthority:
    quantity: str
    authority: str
    expected_basis: str
    permitted_uses: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    tolerance_name: str | None
    fallback_policy: str


@dataclass(frozen=True)
class PRProviderAuthorityContract:
    version: str
    quantities: tuple[QuantityAuthority, ...]
    tolerances: Mapping[str, float]
    direct_fugacity_is_primary: bool
    independent_pr_is_validation_only: bool
    tp_flash_is_phase_region_authority: bool
    mixed_basis_equilibrium_gate_prohibited: bool
    cross_interface_y_equality_required: bool
    fallback_between_direct_and_flash_permitted: bool


REQUIRED_QUANTITIES = (
    "direct_phase_fugacity_residual",
    "direct_bubble_temperature",
    "direct_incipient_vapor_composition",
    "independent_pr_bubble_temperature",
    "independent_pr_incipient_vapor_composition",
    "tp_flash_phase_classification",
    "tp_flash_phase_fraction",
    "tp_flash_liquid_composition",
    "tp_flash_vapor_composition",
    "tp_flash_K_values",
    "tp_flash_lever_rule",
)


def build_pr_provider_authority_contract() -> PRProviderAuthorityContract:
    no_fallback = "fail explicitly; do not substitute another interface"
    quantities = (
        QuantityAuthority(
            quantity="direct_phase_fugacity_residual",
            authority="DWSIM imposed-phase fugacity",
            expected_basis="declared liquid x and incipient vapor y",
            permitted_uses=(
                "bubble and dew equilibrium acceptance",
                "equilibrium-stage saturation equations",
            ),
            forbidden_uses=("phase fraction or stable-phase classification",),
            tolerance_name="direct_fugacity_residual_inf",
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="direct_bubble_temperature",
            authority="DWSIM imposed-phase fugacity",
            expected_basis="fixed pressure and declared liquid x",
            permitted_uses=("production bubble temperature",),
            forbidden_uses=("TP-flash material split",),
            tolerance_name="direct_fugacity_residual_inf",
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="direct_incipient_vapor_composition",
            authority="DWSIM imposed-phase fugacity",
            expected_basis="fixed pressure and declared liquid x",
            permitted_uses=("production incipient vapor composition",),
            forbidden_uses=("finite TP-flash vapor inventory",),
            tolerance_name="direct_fugacity_residual_inf",
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="independent_pr_bubble_temperature",
            authority="independent parameter-aligned Peng-Robinson",
            expected_basis="same pressure, liquid x, constants, omega, and kij",
            permitted_uses=("validation of direct bubble temperature",),
            forbidden_uses=("production property evaluation",),
            tolerance_name="independent_pr_temperature_abs_F",
            fallback_policy="validation failure stops authorization",
        ),
        QuantityAuthority(
            quantity="independent_pr_incipient_vapor_composition",
            authority="independent parameter-aligned Peng-Robinson",
            expected_basis="same pressure, liquid x, constants, omega, and kij",
            permitted_uses=("validation of direct incipient vapor",),
            forbidden_uses=("production property evaluation",),
            tolerance_name="independent_pr_vapor_max_abs",
            fallback_policy="validation failure stops authorization",
        ),
        QuantityAuthority(
            quantity="tp_flash_phase_classification",
            authority="DWSIM TP flash",
            expected_basis="overall composition z at declared T and P",
            permitted_uses=("stable-phase and phase-region classification",),
            forbidden_uses=("direct fugacity equilibrium acceptance",),
            tolerance_name=None,
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="tp_flash_phase_fraction",
            authority="DWSIM TP flash",
            expected_basis="overall composition z",
            permitted_uses=("phase split and near-boundary classification",),
            forbidden_uses=("exact bubble equation",),
            tolerance_name="bubble_region_vapor_fraction",
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="tp_flash_liquid_composition",
            authority="DWSIM TP flash",
            expected_basis="flash liquid phase x_flash",
            permitted_uses=("flash material split", "flash K-value basis"),
            forbidden_uses=("replacement for declared overall z",),
            tolerance_name=None,
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="tp_flash_vapor_composition",
            authority="DWSIM TP flash",
            expected_basis="flash vapor phase y_flash",
            permitted_uses=("flash material split", "flash K-value basis"),
            forbidden_uses=("strict equality to direct incipient vapor",),
            tolerance_name=None,
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="tp_flash_K_values",
            authority="DWSIM TP flash",
            expected_basis="K_flash = y_flash / x_flash",
            permitted_uses=(
                "reconstruct y_flash from x_flash",
                "Rachford-Rice phase split",
            ),
            forbidden_uses=(
                "strict bubble-vapor oracle from K_flash*z when beta is nonzero",
            ),
            tolerance_name="flash_Kx_reconstruction_max_abs",
            fallback_policy=no_fallback,
        ),
        QuantityAuthority(
            quantity="tp_flash_lever_rule",
            authority="DWSIM TP flash",
            expected_basis="z = (1-beta)*x_flash + beta*y_flash",
            permitted_uses=("flash material closure",),
            forbidden_uses=("direct fugacity equilibrium acceptance",),
            tolerance_name="flash_lever_rule_max_abs",
            fallback_policy=no_fallback,
        ),
    )
    return PRProviderAuthorityContract(
        version="dd090-pr-provider-authority-v1",
        quantities=quantities,
        tolerances={
            "direct_fugacity_residual_inf": 1.0e-10,
            "independent_pr_temperature_abs_F": 1.0e-3,
            "independent_pr_vapor_max_abs": 1.0e-6,
            "flash_Kx_reconstruction_max_abs": 1.0e-12,
            "flash_lever_rule_max_abs": 1.0e-12,
            "bubble_region_vapor_fraction": 1.0e-3,
            "fresh_process_repeatability_max_abs": 1.0e-10,
        },
        direct_fugacity_is_primary=True,
        independent_pr_is_validation_only=True,
        tp_flash_is_phase_region_authority=True,
        mixed_basis_equilibrium_gate_prohibited=True,
        cross_interface_y_equality_required=False,
        fallback_between_direct_and_flash_permitted=False,
    )


def contract_payload(contract: PRProviderAuthorityContract) -> dict[str, Any]:
    return {
        "version": contract.version,
        "quantities": [asdict(quantity) for quantity in contract.quantities],
        "tolerances": dict(contract.tolerances),
        "direct_fugacity_is_primary": contract.direct_fugacity_is_primary,
        "independent_pr_is_validation_only": (
            contract.independent_pr_is_validation_only
        ),
        "tp_flash_is_phase_region_authority": (
            contract.tp_flash_is_phase_region_authority
        ),
        "mixed_basis_equilibrium_gate_prohibited": (
            contract.mixed_basis_equilibrium_gate_prohibited
        ),
        "cross_interface_y_equality_required": (
            contract.cross_interface_y_equality_required
        ),
        "fallback_between_direct_and_flash_permitted": (
            contract.fallback_between_direct_and_flash_permitted
        ),
    }


def audit_contract_structure(
    contract: PRProviderAuthorityContract,
) -> dict[str, Any]:
    names = tuple(quantity.quantity for quantity in contract.quantities)
    duplicate = tuple(
        sorted({name for name in names if names.count(name) > 1})
    )
    missing = tuple(name for name in REQUIRED_QUANTITIES if name not in names)
    tolerance_names = {
        quantity.tolerance_name
        for quantity in contract.quantities
        if quantity.tolerance_name is not None
    }
    missing_tolerances = tuple(
        sorted(name for name in tolerance_names if name not in contract.tolerances)
    )
    empty_fallbacks = tuple(
        quantity.quantity
        for quantity in contract.quantities
        if not quantity.fallback_policy.strip()
    )
    pass_gate = bool(
        not duplicate
        and not missing
        and not missing_tolerances
        and not empty_fallbacks
        and contract.direct_fugacity_is_primary
        and contract.independent_pr_is_validation_only
        and contract.tp_flash_is_phase_region_authority
        and contract.mixed_basis_equilibrium_gate_prohibited
        and not contract.cross_interface_y_equality_required
        and not contract.fallback_between_direct_and_flash_permitted
    )
    return {
        "pass": pass_gate,
        "quantity_count": len(names),
        "duplicate_quantities": duplicate,
        "missing_quantities": missing,
        "missing_tolerances": missing_tolerances,
        "empty_fallback_policies": empty_fallbacks,
    }


def flash_internal_coherence(
    *,
    overall_z: Sequence[float],
    flash_x: Sequence[float],
    flash_y: Sequence[float],
    flash_K: Sequence[float],
    beta: float,
) -> dict[str, float]:
    z = np.asarray(overall_z, dtype=float)
    x = np.asarray(flash_x, dtype=float)
    y = np.asarray(flash_y, dtype=float)
    K = np.asarray(flash_K, dtype=float)
    z = z / np.sum(z)
    x = x / np.sum(x)
    y = y / np.sum(y)
    reconstructed_y = K * x
    reconstructed_y = reconstructed_y / np.sum(reconstructed_y)
    reconstructed_z = (1.0 - float(beta)) * x + float(beta) * y
    mixed_basis_y = K * z
    mixed_basis_y = mixed_basis_y / np.sum(mixed_basis_y)
    return {
        "Kx_reconstruction_max_abs": float(
            np.max(np.abs(y - reconstructed_y))
        ),
        "lever_rule_max_abs": float(
            np.max(np.abs(z - reconstructed_z))
        ),
        "mixed_basis_shift_max_abs": float(
            np.max(np.abs(reconstructed_y - mixed_basis_y))
        ),
    }


def phase_region_pass(
    *,
    beta: float,
    stable_vapor: bool,
    contract: PRProviderAuthorityContract,
) -> bool:
    return bool(
        np.isfinite(float(beta))
        and float(beta)
        <= float(contract.tolerances["bubble_region_vapor_fraction"])
        and not bool(stable_vapor)
    )


def evaluate_dd089_evidence(
    contract: PRProviderAuthorityContract,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    tolerances = contract.tolerances
    checks = {
        "contract_structure": audit_contract_structure(contract)["pass"],
        "direct_fugacity": (
            float(evidence["direct_fugacity_residual_inf"])
            < float(tolerances["direct_fugacity_residual_inf"])
        ),
        "independent_pr_temperature": (
            abs(float(evidence["independent_pr_temperature_delta_F"]))
            < float(tolerances["independent_pr_temperature_abs_F"])
        ),
        "independent_pr_vapor": (
            float(evidence["independent_pr_vapor_max_abs"])
            < float(tolerances["independent_pr_vapor_max_abs"])
        ),
        "flash_Kx": (
            float(evidence["flash_Kx_reconstruction_max_abs"])
            < float(tolerances["flash_Kx_reconstruction_max_abs"])
        ),
        "flash_lever_rule": (
            float(evidence["flash_lever_rule_max_abs"])
            < float(tolerances["flash_lever_rule_max_abs"])
        ),
        "phase_region": phase_region_pass(
            beta=float(evidence["beta"]),
            stable_vapor=bool(evidence["stable_vapor"]),
            contract=contract,
        ),
        "fresh_process_repeatability": (
            float(evidence["fresh_process_repeatability_max_abs"])
            <= float(tolerances["fresh_process_repeatability_max_abs"])
        ),
        "mixed_basis_not_used_as_gate": bool(
            evidence["mixed_basis_reported_separately"]
        ),
        "cross_interface_y_not_used_as_gate": bool(
            evidence["cross_interface_y_reported_without_equality_gate"]
        ),
        "no_fallback": not bool(evidence["fallback_used"]),
    }
    return {
        "pass": bool(all(checks.values())),
        "checks": checks,
        "failed_checks": tuple(
            name for name, passed in checks.items() if not passed
        ),
    }


__all__ = [
    "PRProviderAuthorityContract",
    "QuantityAuthority",
    "REQUIRED_QUANTITIES",
    "audit_contract_structure",
    "build_pr_provider_authority_contract",
    "contract_payload",
    "evaluate_dd089_evidence",
    "flash_internal_coherence",
    "phase_region_pass",
]
