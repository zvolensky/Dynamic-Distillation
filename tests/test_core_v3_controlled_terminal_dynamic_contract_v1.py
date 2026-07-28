from dynamic_distillation.core_v3.controlled_terminal_dynamic_contract_v1 import (
    LevelControllerSpecification,
    TerminalGeometry,
    audit_controlled_terminal_dynamic_contract,
    build_controlled_terminal_dynamic_contract,
)


def _build(components):
    return build_controlled_terminal_dynamic_contract(
        components,
        geometry=TerminalGeometry(
            drum_diameter_ft=12.1,
            drum_tangent_length_ft=36.3,
            drum_head_shape="two_hemispherical",
            sump_diameter_ft=18.1759,
            sump_height_ft=12.0,
        ),
        controllers=LevelControllerSpecification(
            drum_kc=0.5,
            drum_ti_sec=120.0,
            sump_kc=8.0,
            sump_ti_sec=120.0,
            product_rate_ratio_bounds=(0.25, 2.0),
        ),
    )


def test_dd123_three_component_controlled_dynamic_contract_passes():
    audit = audit_controlled_terminal_dynamic_contract(
        _build(("n-Propane", "n-Butane", "n-Pentane"))
    )

    assert audit.pass_gate
    assert audit.solve_variable_count == audit.row_count == 50
    assert audit.structural_rank == 50
    assert audit.state_coordinate_count == 21
    assert audit.derivative_variable_count == 21
    assert audit.algebraic_variable_count == 29
    assert audit.controller_row_count == 4
    assert audit.boundary_rows_own_product_outputs


def test_dd123_contract_remains_generic_in_component_count():
    audit = audit_controlled_terminal_dynamic_contract(
        _build(("water", "methanol"))
    )

    assert audit.pass_gate
    assert audit.solve_variable_count == audit.row_count == 40
    assert audit.structural_rank == 40
    assert audit.state_coordinate_count == 16


def test_dd123_invalid_geometry_fails_without_repair():
    contract = build_controlled_terminal_dynamic_contract(
        ("a", "b"),
        geometry=TerminalGeometry(
            drum_diameter_ft=12.1,
            drum_tangent_length_ft=36.3,
            drum_head_shape="horizontal_cylinder",
            sump_diameter_ft=18.1759,
            sump_height_ft=12.0,
        ),
        controllers=LevelControllerSpecification(
            drum_kc=0.5,
            drum_ti_sec=120.0,
            sump_kc=8.0,
            sump_ti_sec=120.0,
            product_rate_ratio_bounds=(0.25, 2.0),
        ),
    )

    assert not audit_controlled_terminal_dynamic_contract(contract).pass_gate
