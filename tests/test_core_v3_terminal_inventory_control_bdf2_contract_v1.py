from dataclasses import replace

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    build_column_topology,
)
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_contract_v1 import (
    audit_controlled_bdf2_contract,
    build_controlled_bdf2_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (
    TerminalPIParameters,
    TerminalVesselGeometry,
    build_terminal_inventory_control_contract,
)


def _contract(*, rectifying=2, stripping=2, components=("a", "b", "c")):
    topology = build_column_topology(
        rectifying_volume_count=rectifying,
        stripping_volume_count=stripping,
    )
    base = build_dynamic_dae_contract(
        components,
        topology=topology,
        accepted_root_artifact="accepted.json",
        product_flow_parameters=("D", "B"),
    )
    controlled = build_terminal_inventory_control_contract(
        base,
        geometry=TerminalVesselGeometry(
            top_diameter_ft=12.0,
            top_tangent_length_ft=36.0,
            top_head_shape="two_hemispherical",
            bottom_diameter_ft=18.0,
            bottom_height_ft=12.0,
        ),
        controllers=TerminalPIParameters(
            top_kc=0.5,
            top_ti_sec=120.0,
            bottom_kc=8.0,
            bottom_ti_sec=120.0,
            product_rate_ratio_bounds=(0.25, 2.0),
        ),
    )
    return build_controlled_bdf2_contract(controlled)


def test_dd195_seven_volume_bdf2_keeps_the_58_by_58_full_rank_system():
    audit = audit_controlled_bdf2_contract(_contract())

    assert audit.volume_count == 7
    assert audit.differential_state_count == 23
    assert audit.solve_variable_count == audit.row_count == 58
    assert audit.structural_rank == 58
    assert audit.structural_nullity == 0
    assert audit.backward_euler_pattern_equal
    assert audit.pass_gate


def test_dd195_history_owns_components_derived_energy_and_controller_memory():
    contract = _contract()
    audit = audit_controlled_bdf2_contract(contract)

    assert audit.derived_energy_history_count == 7
    assert audit.history_value_count == audit.expected_history_value_count == 60
    assert audit.two_history_levels
    assert audit.all_history_coordinates_unique
    assert audit.component_history_complete
    assert audit.energy_history_complete
    assert audit.controller_history_complete


def test_dd195_requires_backward_euler_startup_and_restart_after_dt_change():
    audit = audit_controlled_bdf2_contract(_contract())

    assert audit.existing_backward_euler_startup
    assert audit.constant_step_only
    assert audit.positive_inventory_endpoint


def test_dd195_scales_without_named_interior_volume_logic():
    audit = audit_controlled_bdf2_contract(
        _contract(rectifying=3, stripping=2, components=("a", "b", "c", "d"))
    )

    assert audit.volume_count == 8
    assert audit.differential_state_count == 34
    assert audit.history_value_count == 84
    assert audit.solve_variable_count == audit.row_count == 82
    assert audit.structural_rank == 82
    assert audit.pass_gate


def test_dd195_is_structural_only_and_rejects_incomplete_history():
    contract = _contract()
    audit = audit_controlled_bdf2_contract(contract)
    incomplete = replace(
        contract,
        energy_history_coordinates=contract.energy_history_coordinates[:-1],
    )

    assert audit.preparation_only
    assert not audit_controlled_bdf2_contract(incomplete).pass_gate
