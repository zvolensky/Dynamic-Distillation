from dynamic_distillation.direct_steady_state_registry_v1 import (
    audit_registry_structure,
    build_direct_steady_state_registry,
    combine_reboiler_and_sump_registry,
    structural_pattern,
)


def _registry():
    return build_direct_steady_state_registry(
        component_names=("C3", "C4", "C5"),
        active_stage_ids=tuple(range(2, 20)),
    )


def test_dd071_registry_is_deterministic_and_one_equation_short():
    first = _registry()
    second = _registry()

    assert first == second
    audit = audit_registry_structure(first)
    assert audit.unknown_count == 291
    assert audit.residual_count == 290
    assert audit.equation_count_difference == 1
    assert audit.square is False
    assert audit.pass_gate is False


def test_dd071_registry_identifies_unowned_reboiler_liquid_outlet():
    audit = audit_registry_structure(_registry())

    assert audit.missing_closure_owners == (
        "L_out[partial_reboiler_to_bottoms_sump]",
    )
    assert audit.structurally_empty_rows == ()
    assert audit.structurally_empty_columns == ()
    assert audit.duplicate_unknown_names == ()
    assert audit.duplicate_residual_names == ()
    assert audit.structural_nullity >= 1


def test_dd071_pattern_contains_only_registered_unknown_dependencies():
    registry = _registry()
    pattern = structural_pattern(registry)

    assert pattern.shape == (290, 291)
    assert pattern.nnz > 0
    registered = {entry.name for entry in registry.unknowns}
    external = {
        dependency
        for residual in registry.residuals
        for dependency in residual.dependencies
        if dependency not in registered
    }
    assert external == {
        "F[tray_2]",
        "F[tray_3]",
        "F[tray_4]",
        "F[tray_5]",
        "F[tray_6]",
        "F[tray_7]",
        "F[tray_8]",
        "F[tray_9]",
        "F[tray_10]",
        "F[tray_11]",
        "F[tray_12]",
        "F[tray_13]",
        "F[tray_14]",
        "F[tray_15]",
        "F[tray_16]",
        "F[tray_17]",
        "F[tray_18]",
        "F[tray_19]",
        "R_fixed",
    }


def test_dd071_registry_is_generic_in_stage_identifiers():
    registry = build_direct_steady_state_registry(
        component_names=("A", "B"),
        active_stage_ids=("top_active", "middle", "bottom_active"),
    )
    names = {entry.name for entry in registry.unknowns}

    assert "L_out[tray_middle]" in names
    assert "V_out[tray_bottom_active]" in names
    assert not any("tray_12" in name for name in names)


def test_dd071_combined_bottom_control_volume_is_square_and_owned():
    combined = combine_reboiler_and_sump_registry(_registry())
    audit = audit_registry_structure(combined)

    assert audit.unknown_count == 281
    assert audit.residual_count == 281
    assert audit.equation_count_difference == 0
    assert audit.square is True
    assert audit.structural_rank == 281
    assert audit.structural_nullity == 0
    assert audit.missing_closure_owners == ()
    assert audit.pass_gate is True
    names = {entry.name for entry in combined.unknowns}
    assert "L_out[partial_reboiler_to_bottoms_sump]" not in names
    assert not any(name.startswith("N[bottoms_sump,") for name in names)
