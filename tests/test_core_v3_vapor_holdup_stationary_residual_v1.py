from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.vapor_holdup_stationary_contract_v1 import (
    build_vapor_holdup_stationary_contract,
)
from dynamic_distillation.core_v3.vapor_holdup_stationary_residual_v1 import (
    VaporHoldupStationaryNumericalSpec,
    VaporHoldupStationaryReference,
    decode_vapor_holdup_stationary_endpoint,
    evaluate_vapor_holdup_stationary_residual,
    stationary_structural_pattern,
)
from test_core_v3_vapor_holdup_implicit_residual_v1 import _problem


def _stationary_problem():
    provider, spec, dynamic_contract, geometry, reference, inputs, numerical = _problem()
    contract = build_vapor_holdup_stationary_contract(
        spec.component_names,
        topology=dynamic_contract.topology,
    )
    stationary_reference = VaporHoldupStationaryReference(
        liquid_component_inventory_lbmol=reference.liquid_component_inventory_lbmol,
        vapor_component_inventory_lbmol=reference.vapor_component_inventory_lbmol,
        phase_transfer_lbmolph=reference.phase_transfer_lbmolph,
        phase_transfer_scale_lbmolph=reference.phase_transfer_scale_lbmolph,
        temperature_F=reference.temperature_F,
        pressure_psia=reference.pressure_psia,
        hydraulic_liquid_flow_lbmolph=reference.hydraulic_liquid_flow_lbmolph,
        vapor_flow_lbmolph=reference.vapor_flow_lbmolph,
        condenser_duty_BTUph=reference.condenser_duty_BTUph,
        distillate_lbmolph=inputs.distillate_lbmolph,
        bottoms_lbmolph=inputs.bottoms_lbmolph,
        top_liquid_inventory_target_lbmol=float(
            np.sum(reference.liquid_component_inventory_lbmol[0])
        ),
        bottom_liquid_inventory_target_lbmol=float(
            np.sum(reference.liquid_component_inventory_lbmol[-1])
        ),
    )
    stationary_numerical = VaporHoldupStationaryNumericalSpec(
        temperature_coordinate_scale_F=numerical.temperature_coordinate_scale_F,
        pressure_coordinate_scale_psia=numerical.pressure_coordinate_scale_psia,
        dry_tray_pressure_drop_coefficient=numerical.dry_tray_pressure_drop_coefficient,
        component_mw_lbm_per_lbmol=numerical.component_mw_lbm_per_lbmol,
        pressure_link_geometry=numerical.pressure_link_geometry,
        top_pressure_anchor_psia=numerical.top_pressure_anchor_psia,
        component_residual_scale_lbmolph=numerical.component_residual_scale_lbmolph,
        energy_residual_scale_BTUph=numerical.energy_residual_scale_BTUph,
        pressure_residual_scale_psia=numerical.pressure_residual_scale_psia,
    )
    return (
        provider,
        spec,
        contract,
        geometry,
        stationary_reference,
        inputs,
        stationary_numerical,
    )


def test_stationary_five_volume_residual_has_exact_65_row_ledger():
    provider, spec, contract, geometry, reference, inputs, numerical = (
        _stationary_problem()
    )
    audit = ProviderCallAudit()
    evaluation = evaluate_vapor_holdup_stationary_residual(
        contract,
        geometry,
        reference,
        inputs,
        spec.hydraulic_geometry,
        numerical,
        provider,
        audit,
        np.zeros(65),
        state_id="stationary_baseline",
        evaluation_kind="residual",
    )

    assert evaluation.raw.shape == evaluation.scaled.shape == (65,)
    assert evaluation.row_names == tuple(row.name for row in contract.rows)
    assert evaluation.variable_names == tuple(
        variable.name for variable in contract.variables
    )
    assert np.array_equal(evaluation.terminal_inventory_residual_lbmol, [0.0, 0.0])
    assert np.max(np.abs(evaluation.properties.eos_relative_residual)) < 1.0e-12
    assert audit.record_count == 30


def test_zero_coordinates_preserve_stationary_reference():
    _provider, _spec, contract, _geometry, reference, _inputs, numerical = (
        _stationary_problem()
    )
    endpoint = decode_vapor_holdup_stationary_endpoint(
        contract, reference, numerical, np.zeros(65)
    )

    assert np.array_equal(
        endpoint.liquid_component_inventory_lbmol,
        reference.liquid_component_inventory_lbmol,
    )
    assert np.array_equal(
        endpoint.vapor_component_inventory_lbmol,
        reference.vapor_component_inventory_lbmol,
    )
    assert endpoint.distillate_lbmolph == reference.distillate_lbmolph
    assert endpoint.bottoms_lbmolph == reference.bottoms_lbmolph


def test_product_coordinates_are_positive_and_independent():
    _provider, _spec, contract, _geometry, reference, _inputs, numerical = (
        _stationary_problem()
    )
    point = np.zeros(65)
    point[-2] = 0.1
    endpoint = decode_vapor_holdup_stationary_endpoint(
        contract, reference, numerical, point
    )

    assert endpoint.distillate_lbmolph > reference.distillate_lbmolph
    assert endpoint.bottoms_lbmolph == reference.bottoms_lbmolph


def test_stationary_pattern_is_square_and_contains_terminal_closure():
    _provider, _spec, contract, _geometry, _reference, _inputs, _numerical = (
        _stationary_problem()
    )
    pattern = stationary_structural_pattern(contract)
    rows = tuple(row.name for row in contract.rows)
    variables = tuple(variable.name for variable in contract.variables)

    assert pattern.shape == (65, 65)
    assert pattern[rows.index("top_liquid_inventory_target[reflux_drum]"), 0]
    assert pattern[
        rows.index(
            "bottom_liquid_inventory_target[combined_reboiler_sump]"
        ),
        variables.index("NL[combined_reboiler_sump,A]"),
    ]
