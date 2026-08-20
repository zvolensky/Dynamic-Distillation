from __future__ import annotations

from dynamic_distillation.core_v3.provider_governed_registry_v1 import DEFAULT_TOPOLOGY
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_contract_v1 import (
    audit_vapor_holdup_stationary_contract,
    build_vapor_holdup_stationary_contract,
    stationary_sparsity_pattern,
)


def _contract(component_count: int = 3):
    topology = build_vapor_holdup_topology(
        column=DEFAULT_TOPOLOGY,
        vapor_volume_ft3={volume: 1000.0 for volume in DEFAULT_TOPOLOGY.volume_ids},
    )
    return build_vapor_holdup_stationary_contract(
        tuple(f"C{index + 1}" for index in range(component_count)),
        topology=topology,
    )


def test_five_volume_stationary_contract_is_square_and_full_rank():
    contract = _contract()
    audit = audit_vapor_holdup_stationary_contract(contract)

    assert audit.variable_count == audit.row_count == 65
    assert audit.structural_rank == 65
    assert audit.structural_nullity == 0
    assert audit.pass_gate


def test_stationary_contract_solves_products_and_owns_terminal_levels():
    contract = _contract()
    names = tuple(variable.name for variable in contract.variables)
    rows = tuple(row.name for row in contract.rows)

    assert names[-2:] == ("D", "B")
    assert not ({"D", "B", "D_fixed", "B_fixed"} & set(contract.fixed_parameters))
    assert "top_liquid_inventory_target[reflux_drum]" in rows
    assert "bottom_liquid_inventory_target[combined_reboiler_sump]" in rows


def test_stationary_product_rates_enter_owned_terminal_balances():
    contract = _contract()
    top = contract.topology.column.top_volume
    bottom = contract.topology.column.bottom_volume
    top_rows = tuple(
        row
        for row in contract.rows
        if row.name.startswith(f"liquid_component_balance[{top},")
    )
    bottom_rows = tuple(
        row
        for row in contract.rows
        if row.name.startswith(f"liquid_component_balance[{bottom},")
    )

    assert all("D" in row.solve_dependencies for row in top_rows)
    assert all("B" in row.solve_dependencies for row in bottom_rows)


def test_stationary_contract_is_generic_in_component_count():
    contract = _contract(component_count=4)
    audit = audit_vapor_holdup_stationary_contract(contract)

    assert audit.variable_count == audit.row_count == 80
    assert audit.structural_rank == 80
    assert audit.pass_gate


def test_stationary_pattern_has_no_unregistered_dependencies():
    contract = _contract()
    pattern, names, unknown = stationary_sparsity_pattern(contract)

    assert pattern.shape == (65, 65)
    assert len(names) == 65
    assert unknown == ()
