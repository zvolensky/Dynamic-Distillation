from dataclasses import replace

import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    contract_sparsity_pattern,
)
from dynamic_distillation.core_v3.pressure_implicit_dae_contract_v1 import (
    TERMINAL_BOTTOM_VOLUME,
    audit_pressure_implicit_dae_contract,
    build_pressure_implicit_dae_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import VAPOR_LINKS


COMPONENTS = ("n-Propane", "n-Butane", "n-Pentane")


def _contract():
    return build_pressure_implicit_dae_contract(COMPONENTS)


def test_dd104_pressure_implicit_ledger_is_square_and_full_rank():
    audit = audit_pressure_implicit_dae_contract(_contract())

    assert audit.state_coordinate_count == 15
    assert audit.derivative_variable_count == 15
    assert audit.algebraic_variable_count == 27
    assert audit.solve_variable_count == audit.row_count == 42
    assert audit.structural_rank == 42
    assert audit.structural_nullity == 0
    assert not audit.zero_solve_columns
    assert not audit.zero_rows
    assert audit.pass_gate


def test_dd104_pressure_is_algebraic_and_has_no_pressure_rate():
    contract = _contract()
    audit = audit_pressure_implicit_dae_contract(contract)

    assert audit.pressure_variable_count == 4
    assert audit.pressure_rate_variable_count == 0
    assert audit.pressure_drop_row_count == 4
    assert not any(
        variable.name.startswith("dP[") for variable in contract.derivative_variables
    )


def test_dd104_terminal_link_is_dry_only_and_tray_links_keep_head():
    contract = _contract()
    audit = audit_pressure_implicit_dae_contract(contract)
    terminal = next(
        link
        for link in contract.pressure_link_ownership
        if link.source == TERMINAL_BOTTOM_VOLUME
    )

    assert terminal.role == "terminal_reboiler_return"
    assert not terminal.includes_liquid_head
    assert audit.terminal_dry_only_link_count == 1
    assert audit.tray_liquid_head_link_count == len(VAPOR_LINKS) - 1 == 3
    assert audit.terminal_pressure_rate_couplings == ()
    assert audit.tray_pressure_rate_coupling_count == 9


def test_dd104_backward_euler_pattern_includes_endpoint_inventory_motion():
    contract = _contract()
    pattern, names = contract_sparsity_pattern(
        contract.pressure_contract,
        include_state_rate_dependencies=True,
    )
    index = {name: position for position, name in enumerate(names)}

    for row_index, row in enumerate(contract.rows):
        for state in row.state_dependencies:
            assert pattern[row_index, index[f"d{state}/dt"]]


def test_dd104_coloring_is_conflict_free_and_reduces_evaluations():
    audit = audit_pressure_implicit_dae_contract(_contract())

    assert audit.color_conflict_free
    assert 0 < audit.color_count < audit.solve_variable_count
    assert sorted(column for group in audit.color_groups for column in group) == list(
        range(audit.solve_variable_count)
    )


def test_dd104_preserves_open_loop_scope_and_conservation():
    contract = _contract()
    audit = audit_pressure_implicit_dae_contract(contract)

    assert audit.component_conservation_inherited
    assert audit.energy_conservation_inherited
    assert audit.top_pressure_anchor_present
    assert audit.fixed_product_rates_present
    assert not audit.controller_rows
    assert not audit.profile_dependencies
    assert not audit.cap_or_relaxation_dependencies
    assert not audit.explicit_vapor_inventory_present
    assert audit.preparation_only
    assert not contract.property_evaluation_attempted
    assert not contract.mass_matrix_evaluation_attempted
    assert not contract.nonlinear_solve_attempted
    assert not contract.dynamic_integration_attempted


def test_dd104_rejects_liquid_head_on_terminal_return():
    contract = _contract()
    ownership = tuple(
        replace(link, includes_liquid_head=True)
        if link.source == TERMINAL_BOTTOM_VOLUME
        else link
        for link in contract.pressure_link_ownership
    )
    audit = audit_pressure_implicit_dae_contract(
        replace(contract, pressure_link_ownership=ownership)
    )

    assert audit.terminal_dry_only_link_count == 0
    assert not audit.pass_gate


def test_dd104_pattern_has_no_duplicate_columns_inside_a_color():
    contract = _contract()
    audit = audit_pressure_implicit_dae_contract(contract)
    pattern, _names = contract_sparsity_pattern(
        contract.pressure_contract,
        include_state_rate_dependencies=True,
    )

    for group in audit.color_groups:
        occupied = np.concatenate(
            [np.flatnonzero(pattern[:, column]) for column in group]
        )
        assert np.unique(occupied).size == occupied.size
