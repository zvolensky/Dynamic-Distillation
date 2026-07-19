from dataclasses import replace

from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    HYDRAULIC_VOLUME_IDS,
    NO_FALLBACK,
    VAPOR_LINKS,
    ProviderAuthority,
    Residual,
    audit_provider_governed_registry,
    build_provider_governed_registry,
)


def _registry(components=("Propane", "n-Butane", "n-Pentane")):
    return build_provider_governed_registry(components)


def test_dd091_three_component_registry_is_40_by_40_and_full_rank():
    audit = audit_provider_governed_registry(_registry())

    assert audit.unknown_count == audit.residual_count == 40
    assert audit.structural_rank == 40
    assert audit.structural_nullity == 0
    assert audit.zero_unknown_columns == ()
    assert audit.zero_residual_rows == ()
    assert audit.pass_gate


def test_dd091_registry_scales_as_ten_c_plus_ten():
    for components in (("light", "heavy"), ("a", "b", "c", "d")):
        audit = audit_provider_governed_registry(_registry(components))
        expected = 10 * len(components) + 10

        assert audit.unknown_count == audit.residual_count == expected
        assert audit.structural_rank == expected
        assert audit.pass_gate


def test_dd091_physical_ownership_is_unique_and_conservative():
    registry = _registry()
    audit = audit_provider_governed_registry(registry)

    assert audit.vapor_unknown_count == len(VAPOR_LINKS) == 4
    assert audit.francis_liquid_unknown_count == len(HYDRAULIC_VOLUME_IDS) == 3
    assert audit.condenser_duty_unknown_count == 1
    assert not audit.fixed_condenser_duty_parameter_present
    assert audit.component_conservation_passed
    assert audit.energy_conservation_passed
    assert "Q_C" not in registry.external_parameters


def test_dd091_equilibrium_rows_use_direct_fugacity_only():
    registry = _registry()
    stage_rows = tuple(
        residual
        for residual in registry.residuals
        if residual.block == "full_phase_equilibrium"
    )
    bubble_rows = tuple(
        residual
        for residual in registry.residuals
        if residual.block == "condenser_bubble_fugacity"
    )

    assert len(stage_rows) == len(EQUILIBRIUM_VOLUME_IDS) * 3
    assert len(bubble_rows) == 3
    assert all(
        residual.property_quantities == ("stage_fugacity_equilibrium",)
        for residual in stage_rows
    )
    assert all(
        "condenser_bubble_equilibrium" in residual.property_quantities
        for residual in bubble_rows
    )


def test_dd091_provider_table_separates_governing_diagnostics_and_validation():
    registry = _registry()
    authority = {
        entry.quantity: entry for entry in registry.provider_authorities
    }

    assert authority["stage_fugacity_equilibrium"].role == "governing_equation"
    assert authority["phase_enthalpy"].role == "governing_balance"
    assert authority["stable_phase"].role == "diagnostic_gate"
    assert authority["flash_x_y_K"].expected_basis == (
        "K_flash = y_flash/x_flash"
    )
    assert authority["independent_pr_bubble"].role == "validation_only"
    assert all(entry.fallback_policy for entry in authority.values())
    assert all(
        entry.fallback_policy == NO_FALLBACK
        for entry in authority.values()
        if entry.role != "validation_only"
    )


def test_dd091_future_acceptance_contract_is_declared_but_not_executed():
    registry = _registry()
    audit = audit_provider_governed_registry(registry)

    assert audit.prospective_acceptance_contract_passed
    assert not audit.live_property_evaluation_attempted
    assert not audit.nonlinear_solve_attempted
    assert not audit.dynamic_integration_attempted


def test_dd091_rejects_tp_flash_in_a_governing_equilibrium_row():
    registry = _registry()
    authorities = (
        *registry.provider_authorities,
        ProviderAuthority(
            "bad_flash_equilibrium",
            "dwsim.tp_flash",
            "governing_equation",
            "overall z",
            ("full_phase_equilibrium",),
            NO_FALLBACK,
        ),
    )
    first = registry.residuals[0]
    bad_first = replace(
        first,
        property_quantities=(*first.property_quantities, "bad_flash_equilibrium"),
    )
    bad = replace(
        registry,
        residuals=(bad_first, *registry.residuals[1:]),
        provider_authorities=authorities,
    )
    audit = audit_provider_governed_registry(bad)

    assert audit.governing_tp_flash_uses
    assert not audit.pass_gate


def test_dd091_rejects_independent_pr_in_a_production_residual():
    registry = _registry()
    first = registry.residuals[0]
    bad_first = replace(
        first,
        property_quantities=(*first.property_quantities, "independent_pr_bubble"),
    )
    bad = replace(registry, residuals=(bad_first, *registry.residuals[1:]))
    audit = audit_provider_governed_registry(bad)

    assert audit.production_independent_pr_uses
    assert not audit.pass_gate


def test_dd091_rejects_mixed_flash_k_overall_composition_dependency():
    registry = _registry()
    first = registry.residuals[0]
    bad_first = replace(
        first,
        dependencies=(*first.dependencies, "normalize(K_flash*z_overall)"),
    )
    bad = replace(
        registry,
        residuals=(bad_first, *registry.residuals[1:]),
        external_parameters=(
            *registry.external_parameters,
            "normalize(K_flash*z_overall)",
        ),
    )
    audit = audit_provider_governed_registry(bad)

    assert audit.mixed_basis_dependencies
    assert not audit.pass_gate


def test_dd091_rejects_fixed_condenser_duty_and_interface_fallback():
    registry = _registry()
    fixed = replace(
        registry,
        external_parameters=(*registry.external_parameters, "Q_C"),
    )
    fallback = replace(registry, interface_fallback_permitted=True)

    assert not audit_provider_governed_registry(fixed).pass_gate
    assert not audit_provider_governed_registry(fallback).pass_gate


def test_dd091_rejects_historical_acceptance_or_core_v2_owner_import():
    registry = _registry()
    historical = replace(registry, historical_acceptance_imported=True)
    first = registry.residuals[0]
    imported = replace(
        registry,
        residuals=(
            Residual(
                first.name,
                first.block,
                "dynamic_distillation.core_v2.residual_owner",
                first.dependencies,
                first.property_quantities,
            ),
            *registry.residuals[1:],
        ),
    )

    assert not audit_provider_governed_registry(historical).pass_gate
    assert audit_provider_governed_registry(imported).core_v2_residual_owner_imported
    assert not audit_provider_governed_registry(imported).pass_gate
