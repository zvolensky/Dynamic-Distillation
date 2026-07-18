from pathlib import Path

from dynamic_distillation.core_v2.reduced_column_spec_v1 import (
    PRESCRIBED_SECTION_VAPOR_MODE,
    build_reduced_column_spec,
)
from dynamic_distillation.core_v2.reduced_residual_registry_v1 import (
    audit_conservation,
    audit_ownership,
    audit_structure,
    build_reduced_residual_registry,
)


def _registry(component_names=("C3", "C4", "C5")):
    return build_reduced_residual_registry(
        build_reduced_column_spec(component_names)
    )


def test_dd077_topology_has_five_inventory_volumes_and_no_condenser_node():
    registry = _registry()
    topology = registry.spec.topology

    assert topology.volume_ids == (
        "reflux_drum",
        "rectifying_tray",
        "feed_tray",
        "stripping_tray",
        "combined_reboiler_sump",
    )
    assert "total_condenser" not in topology.volume_ids
    assert topology.feed_volume_id == "feed_tray"


def test_dd077_registry_is_square_and_structurally_full_rank():
    audit = audit_structure(_registry())

    assert audit.unknown_count == 53
    assert audit.residual_count == 53
    assert audit.structural_rank == 53
    assert audit.structural_nullity == 0
    assert audit.unmatched_unknowns == ()
    assert audit.unmatched_residuals == ()
    assert audit.missing_closure_residuals == ()
    assert audit.pass_gate


def test_dd077_registry_scales_generically_with_component_count():
    binary = audit_structure(_registry(("light", "heavy")))
    quaternary = audit_structure(_registry(("a", "b", "c", "d")))

    assert binary.unknown_count == binary.residual_count == 39
    assert binary.structural_rank == 39
    assert binary.pass_gate
    assert quaternary.unknown_count == quaternary.residual_count == 67
    assert quaternary.structural_rank == 67
    assert quaternary.pass_gate


def test_dd077_pressure_and_vapor_rates_are_parameters_with_single_owners():
    registry = _registry()
    audit = audit_ownership(registry)
    unknown_names = {unknown.name for unknown in registry.unknowns}

    assert registry.spec.vapor_flow_mode == PRESCRIBED_SECTION_VAPOR_MODE
    assert not set(registry.spec.pressure_parameters) & unknown_names
    assert not set(registry.spec.vapor_flow_parameters) & unknown_names
    assert audit.prescribed_pressure_is_parameter_only
    assert audit.prescribed_pressure_is_used
    assert audit.prescribed_vapor_is_parameter_only
    assert audit.prescribed_vapor_is_used
    assert audit.non_francis_tray_liquid_flows == ()
    assert audit.duplicate_flow_owners == ()
    assert audit.imported_profile_dependencies == ()
    assert audit.unregistered_dependencies == ()
    assert audit.pass_gate


def test_dd077_every_tray_liquid_outlet_has_one_francis_equation():
    registry = _registry()
    hydraulic_unknowns = {
        unknown.name
        for unknown in registry.unknowns
        if unknown.block == "liquid_flow"
    }
    hydraulic_residuals = {
        residual.name
        for residual in registry.residuals
        if residual.block == "francis_hydraulics"
    }

    assert hydraulic_unknowns == {
        "L[rectifying_tray]",
        "L[feed_tray]",
        "L[stripping_tray]",
    }
    assert hydraulic_residuals == {
        "francis_hydraulics[rectifying_tray]",
        "francis_hydraulics[feed_tray]",
        "francis_hydraulics[stripping_tray]",
    }


def test_dd077_terminal_levels_own_inventory_and_product_flows_are_unknowns():
    registry = _registry()
    unknown_names = {unknown.name for unknown in registry.unknowns}
    residual_names = {residual.name for residual in registry.residuals}

    assert {"D", "B"} <= unknown_names
    assert {
        "NL_target[reflux_drum]",
        "NL_target[combined_reboiler_sump]",
    } <= set(registry.spec.external_parameters)
    assert {
        "terminal_level[reflux_drum]",
        "terminal_level[combined_reboiler_sump]",
    } <= residual_names


def test_dd077_internal_component_and_energy_terms_telescope_exactly():
    audit = audit_conservation(_registry())

    assert audit.component_internal_telescoping
    assert audit.energy_internal_telescoping
    assert audit.component_failures == ()
    assert audit.energy_failures == ()
    assert audit.pass_gate


def test_dd077_core_does_not_import_legacy_rhs():
    import ast

    root = Path(__file__).resolve().parents[1]
    core = root / "src" / "dynamic_distillation" / "core_v2"
    imports = []
    for path in sorted(core.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports.extend(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        imports.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

    assert not any(name.endswith("column_rhs_v1") for name in imports)
