from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.vapor_holdup_balances_v1 import (
    VaporHoldupBalanceInputs,
    evaluate_two_phase_transport,
    stationary_phase_transfer_from_vapor_transport,
)
from dynamic_distillation.core_v3.vapor_holdup_dae_contract_v1 import (
    build_vapor_holdup_dae_contract,
    build_vapor_holdup_topology,
)
from dynamic_distillation.core_v3.vapor_holdup_geometry_v1 import (
    VaporControlVolumeGeometry,
)
from dynamic_distillation.core_v3.vapor_holdup_implicit_residual_v1 import (
    VaporHoldupImplicitNumericalSpec,
    VaporHoldupImplicitReference,
    decode_vapor_holdup_endpoint,
    evaluate_vapor_holdup_implicit_residual,
    vapor_holdup_structural_pattern,
    vapor_holdup_variable_names,
)
from dynamic_distillation.core_v3.vapor_holdup_properties_v1 import (
    evaluate_vapor_holdup_properties,
)
from test_core_v3_provider_governed_residual_v1 import _fixture


def _problem():
    provider, spec, old_reference = _fixture()
    provider.vapor_z_factor_F_psia = lambda temperature_F, pressure_psia, composition: 0.8
    topology = build_vapor_holdup_topology(
        column=spec.topology,
        vapor_volume_ft3={volume: 2000.0 for volume in spec.topology.volume_ids},
    )
    contract = build_vapor_holdup_dae_contract(
        spec.component_names,
        topology=topology,
    )
    geometry = tuple(
        VaporControlVolumeGeometry(
            volume_id=volume,
            source_stage_1based=index + 1,
            geometry_kind="unit_test",
            gross_capacity_ft3=2000.0,
            fixed_vapor_extension_ft3=0.0,
            liquid_displacement_active=True,
            provenance="unit_test",
        )
        for index, volume in enumerate(spec.topology.volume_ids)
    )
    liquid_inventory = (
        old_reference.liquid_moles_lbmol[:, np.newaxis]
        * old_reference.liquid_mole_fraction
    )
    vapor_y = np.vstack(
        (
            old_reference.bubble_vapor_mole_fraction,
            old_reference.vapor_mole_fraction,
        )
    )
    property_reference = evaluate_vapor_holdup_properties(
        geometry,
        liquid_inventory,
        old_reference.liquid_mole_fraction,
        vapor_y,
        old_reference.temperature_F,
        spec.pressure_psia,
        provider,
        ProviderCallAudit(),
        state_id="reference",
    )
    balance_inputs = VaporHoldupBalanceInputs(
        topology=spec.topology,
        feed_component_lbmolph=spec.feed_component_lbmolph,
        feed_enthalpy_BTUph=spec.feed_enthalpy_BTUph,
        reflux_lbmolph=spec.reflux_lbmolph,
        distillate_lbmolph=old_reference.distillate_lbmolph,
        bottoms_lbmolph=old_reference.bottoms_lbmolph,
        condenser_duty_BTUph=old_reference.condenser_duty_reference_BTUph,
        reboiler_duty_BTUph=spec.reboiler_duty_BTUph,
    )
    transport = evaluate_two_phase_transport(
        balance_inputs,
        old_reference.liquid_mole_fraction,
        vapor_y,
        old_reference.hydraulic_liquid_flow_lbmolph,
        old_reference.vapor_flow_lbmolph,
        property_reference.liquid_enthalpy_BTU_lbmol,
        property_reference.vapor_enthalpy_BTU_lbmol,
    )
    transfer = stationary_phase_transfer_from_vapor_transport(transport)
    transfer_scale = np.maximum(np.abs(transfer), spec.feed_component_lbmolph)
    reference = VaporHoldupImplicitReference(
        liquid_component_inventory_lbmol=liquid_inventory,
        vapor_component_inventory_lbmol=(
            property_reference.vapor_component_inventory_lbmol
        ),
        phase_transfer_lbmolph=transfer,
        phase_transfer_scale_lbmolph=transfer_scale,
        temperature_F=old_reference.temperature_F,
        pressure_psia=spec.pressure_psia,
        hydraulic_liquid_flow_lbmolph=(
            old_reference.hydraulic_liquid_flow_lbmolph
        ),
        vapor_flow_lbmolph=old_reference.vapor_flow_lbmolph,
        condenser_duty_BTUph=old_reference.condenser_duty_reference_BTUph,
        total_stored_energy_BTU=property_reference.total_stored_energy_BTU,
    )
    pressure_geometry = tuple(
        PressureLinkGeometry(
            active_area_ft2=50.0,
            tray_area_ft2=60.0,
            weir_height_in=3.0,
            include_liquid_head=source != spec.topology.bottom_volume,
        )
        for source, _destination, _symbol in spec.topology.vapor_links
    )
    numerical = VaporHoldupImplicitNumericalSpec(
        timestep_sec=1.0,
        temperature_coordinate_scale_F=10.0,
        pressure_coordinate_scale_psia=1.0,
        dry_tray_pressure_drop_coefficient=40.0,
        component_mw_lbm_per_lbmol=np.asarray([44.0, 58.0, 72.0]),
        pressure_link_geometry=pressure_geometry,
        top_pressure_anchor_psia=float(spec.pressure_psia[0]),
        component_residual_scale_lbmolph=spec.feed_component_lbmolph,
        energy_residual_scale_BTUph=1.0e8,
        pressure_residual_scale_psia=1.0,
    )
    return (
        provider,
        spec,
        contract,
        geometry,
        reference,
        balance_inputs,
        numerical,
    )


def test_complete_five_volume_residual_has_exact_63_row_ledger():
    provider, spec, contract, geometry, reference, inputs, numerical = _problem()
    audit = ProviderCallAudit()
    point = np.zeros(63)

    evaluation = evaluate_vapor_holdup_implicit_residual(
        contract,
        geometry,
        reference,
        inputs,
        spec.hydraulic_geometry,
        numerical,
        provider,
        audit,
        point,
        state_id="baseline",
        evaluation_kind="residual",
    )

    assert evaluation.raw.shape == evaluation.scaled.shape == (63,)
    assert evaluation.row_names == tuple(row.name for row in contract.rows)
    assert evaluation.variable_names == vapor_holdup_variable_names(contract)
    assert np.all(np.isfinite(evaluation.raw))
    assert np.max(np.abs(evaluation.properties.eos_relative_residual)) < 1.0e-12
    assert evaluation.pressure_anchor_residual_psia == 0.0
    assert audit.record_count == 30


def test_zero_coordinates_preserve_both_phase_inventories():
    _provider, _spec, contract, _geometry, reference, _inputs, numerical = _problem()

    endpoint = decode_vapor_holdup_endpoint(
        contract,
        reference,
        numerical,
        np.zeros(63),
    )

    assert np.array_equal(
        endpoint.liquid_component_inventory_lbmol,
        reference.liquid_component_inventory_lbmol,
    )
    assert np.array_equal(
        endpoint.vapor_component_inventory_lbmol,
        reference.vapor_component_inventory_lbmol,
    )
    assert np.all(endpoint.liquid_component_rate_lbmolph == 0.0)
    assert np.all(endpoint.vapor_component_rate_lbmolph == 0.0)


def test_log_rate_coordinate_moves_only_owned_endpoint_inventory():
    _provider, _spec, contract, _geometry, reference, _inputs, numerical = _problem()
    point = np.zeros(63)
    point[0] = 1.0e-3

    endpoint = decode_vapor_holdup_endpoint(contract, reference, numerical, point)

    assert endpoint.liquid_component_inventory_lbmol[0, 0] > (
        reference.liquid_component_inventory_lbmol[0, 0]
    )
    assert np.array_equal(
        endpoint.liquid_component_inventory_lbmol.ravel()[1:],
        reference.liquid_component_inventory_lbmol.ravel()[1:],
    )
    assert np.array_equal(
        endpoint.vapor_component_inventory_lbmol,
        reference.vapor_component_inventory_lbmol,
    )


def test_structural_pattern_includes_liquid_inventory_in_pressure_drop():
    _provider, spec, contract, _geometry, _reference, _inputs, _numerical = _problem()
    pattern = vapor_holdup_structural_pattern(contract)
    rows = tuple(row.name for row in contract.rows)
    columns = vapor_holdup_variable_names(contract)
    source = spec.topology.vapor_links[1][0]
    row = rows.index(
        f"vapor_pressure_drop[{source}->{spec.topology.vapor_links[1][1]}]"
    )
    liquid_rate = columns.index(f"dNL[{source},A]/dt")
    vapor_rate = columns.index(f"dNV[{source},A]/dt")

    assert pattern.shape == (63, 63)
    assert pattern[row, liquid_rate]
    assert pattern[row, vapor_rate]
