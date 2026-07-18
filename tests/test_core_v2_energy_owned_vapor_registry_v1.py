from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    EQUILIBRIUM_VOLUME_IDS,
    VAPOR_LINKS,
    audit_energy_owned_vapor_registry,
    build_energy_owned_vapor_registry,
)


def _registry(components=("C3", "C4", "C5")):
    return build_energy_owned_vapor_registry(components)


def test_dd083_three_component_registry_is_37_by_37_and_full_rank():
    audit = audit_energy_owned_vapor_registry(_registry())

    assert audit.unknown_count == 37
    assert audit.residual_count == 37
    assert audit.structural_rank == 37
    assert audit.structural_nullity == 0
    assert audit.unmatched_unknowns == ()
    assert audit.unmatched_residuals == ()
    assert audit.pass_gate


def test_dd083_registry_scales_as_nine_c_plus_ten():
    for components in (("light", "heavy"), ("a", "b", "c", "d")):
        audit = audit_energy_owned_vapor_registry(_registry(components))
        expected = 9 * len(components) + 10

        assert audit.unknown_count == audit.residual_count == expected
        assert audit.structural_rank == expected
        assert audit.pass_gate


def test_dd083_has_four_independent_vapor_unknowns_and_no_section_parameters():
    registry = _registry()
    vapor_unknowns = {
        entry.name
        for entry in registry.unknowns
        if entry.block == "energy_owned_vapor_flow"
    }

    assert vapor_unknowns == {symbol for _, _, symbol in VAPOR_LINKS}
    assert "V_rectifying" not in registry.external_parameters
    assert "V_stripping" not in registry.external_parameters


def test_dd083_uses_full_fugacity_equalities_to_close_saturation():
    registry = _registry()
    rows = [
        entry
        for entry in registry.residuals
        if entry.block == "full_phase_equilibrium"
    ]

    assert len(rows) == len(EQUILIBRIUM_VOLUME_IDS) * 3
    assert {
        entry.owner for entry in rows
    } == set(EQUILIBRIUM_VOLUME_IDS)


def test_dd083_retains_fixed_pressure_duties_and_terminal_inventory_specs():
    registry = _registry()
    unknown_names = {entry.name for entry in registry.unknowns}

    assert {"Q_C", "Q_R", "R"} <= set(registry.external_parameters)
    assert {
        "NL_target[reflux_drum]",
        "NL_target[combined_reboiler_sump]",
    } <= set(registry.external_parameters)
    assert not {
        "Q_C",
        "Q_R",
        "R",
        "P[reflux_drum]",
    } & unknown_names
    assert {"D", "B"} <= unknown_names


def test_dd083_has_clean_ownership_and_exact_internal_telescoping():
    audit = audit_energy_owned_vapor_registry(_registry())

    assert audit.unregistered_dependencies == ()
    assert audit.imported_profile_dependencies == ()
    assert audit.component_conservation_passed
    assert audit.energy_conservation_passed
    assert audit.pass_gate
