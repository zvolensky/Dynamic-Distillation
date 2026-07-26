from pathlib import Path

from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    TOP_PRESSURE_PARAMETER,
    audit_pressure_layer_contract,
    build_pressure_layer_contract,
)
from dynamic_distillation.core_v3.provider_governed_registry_v1 import (
    VAPOR_LINKS,
    VOLUME_IDS,
)


def _contract():
    return build_pressure_layer_contract(("n-Propane", "n-Butane", "n-Pentane"))


def test_dd101_pressure_layer_is_square_and_full_structural_rank():
    audit = audit_pressure_layer_contract(_contract())

    assert audit.solve_variable_count == audit.row_count == 42
    assert audit.structural_rank == 42
    assert audit.structural_nullity == 0
    assert not audit.zero_solve_columns
    assert not audit.zero_rows
    assert not audit.unregistered_dependencies
    assert audit.pass_gate


def test_dd101_pressure_layer_has_one_unknown_and_one_row_per_vapor_link():
    contract = _contract()
    audit = audit_pressure_layer_contract(contract)

    assert audit.pressure_variable_count == len(VOLUME_IDS) - 1 == 4
    assert audit.pressure_drop_row_count == len(VAPOR_LINKS) == 4
    assert audit.vapor_flow_variable_count == len(VAPOR_LINKS) == 4
    assert TOP_PRESSURE_PARAMETER in contract.fixed_parameters
    assert not audit.prescribed_interior_pressure_parameters


def test_dd101_pressure_rows_retain_energy_owned_vapor_flows():
    contract = _contract()
    rows = {
        row.name: row
        for row in contract.rows
        if row.block == "vapor_pressure_drop"
    }
    for source, destination, vapor_symbol in VAPOR_LINKS:
        row = rows[f"vapor_pressure_drop[{source}->{destination}]"]
        assert vapor_symbol in row.solve_dependencies
        assert f"P[{source}]" in row.solve_dependencies
        if destination != "reflux_drum":
            assert f"P[{destination}]" in row.solve_dependencies


def test_dd101_pressure_layer_adds_pressure_to_property_rows_only():
    contract = _contract()
    component_rows = [
        row for row in contract.rows if row.block == "component_balance"
    ]
    equilibrium_rows = [
        row for row in contract.rows if row.block == "full_phase_equilibrium"
    ]

    assert not any(
        dependency.startswith("P[")
        for row in component_rows
        for dependency in row.solve_dependencies
    )
    assert all(
        f"P[{row.owner}]" in row.solve_dependencies
        for row in equilibrium_rows
    )


def test_dd101_pressure_layer_declares_direct_z_and_density_ownership():
    audit = audit_pressure_layer_contract(_contract())

    assert audit.pressure_drop_property_quantities == (
        "declared_liquid_density",
        "declared_vapor_compressibility_factor",
    )
    assert audit.ordered_pressure_gate_declared


def test_dd101_pressure_layer_preserves_scope_boundaries():
    audit = audit_pressure_layer_contract(_contract())

    assert audit.component_conservation_inherited
    assert audit.energy_conservation_inherited
    assert not audit.controller_rows
    assert not audit.profile_dependencies
    assert not audit.cap_or_relaxation_dependencies
    assert not audit.explicit_vapor_inventory_present
    assert audit.preparation_only


def test_dd101_pressure_layer_does_not_import_retired_residuals():
    source = (
        Path(__file__).parents[1]
        / "src/dynamic_distillation/core_v3/pressure_layer_contract_v1.py"
    ).read_text(encoding="utf-8")

    assert "core_v2" not in source
    assert "direct_steady_state_residual_v1" not in source
    assert "column_rhs_v1" not in source
