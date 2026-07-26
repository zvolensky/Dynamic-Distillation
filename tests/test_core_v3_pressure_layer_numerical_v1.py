import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    audit_storage_gradient,
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.pressure_layer_contract_v1 import (
    build_pressure_layer_contract,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
    audit_pressure_layer_jacobian,
    evaluate_pressure_layer_residual,
    pressure_profile_from_coordinates,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import PhysicalState
from test_core_v3_provider_governed_residual_v1 import _fixture


def _state(reference):
    return PhysicalState(
        liquid_moles_lbmol=reference.liquid_moles_lbmol,
        liquid_mole_fraction=reference.liquid_mole_fraction,
        temperature_F=reference.temperature_F,
        vapor_mole_fraction=reference.vapor_mole_fraction,
        hydraulic_liquid_flow_lbmolph=reference.hydraulic_liquid_flow_lbmolph,
        vapor_flow_lbmolph=reference.vapor_flow_lbmolph,
        distillate_lbmolph=reference.distillate_lbmolph,
        bottoms_lbmolph=reference.bottoms_lbmolph,
        bubble_vapor_mole_fraction=reference.bubble_vapor_mole_fraction,
        condenser_duty_BTUph=reference.condenser_duty_reference_BTUph,
    )


def _scales():
    scales = np.ones(40)
    scales[12:32] = 1.0e8
    scales[32:35] = 1.0e4
    scales[35:37] = 1.0e3
    return scales


def _problem():
    provider, spec, reference = _fixture()
    provider.vapor_z_factor_F_psia = (
        lambda temperature_F, pressure_psia, composition: (
            0.75 + 1.0e-4 * (float(temperature_F) - 180.0)
        )
    )
    state = _state(reference)
    contract = build_pressure_layer_contract(spec.component_names)
    geometry = tuple(
        PressureLinkGeometry(
            active_area_ft2=50.0,
            tray_area_ft2=60.0,
            weir_height_in=3.0,
        )
        for _ in range(4)
    )
    numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(spec.pressure_psia, dtype=float),
        pressure_coordinate_scale_psia=10.0,
        pressure_residual_scale_psia=1.0,
        dry_tray_pressure_drop_coefficient=40.0,
        component_mw_lbm_per_lbmol=np.asarray([44.0, 58.0, 72.0]),
        link_geometry=geometry,
    )
    storage = audit_storage_gradient(
        spec,
        state,
        provider,
        ProviderCallAudit(),
        relative_steps=(1.0e-5,),
        state_id="pressure_storage",
    ).steps[0].gradient_BTU_lbmol
    return provider, spec, reference, state, contract, numerical, storage


def test_dd102_pressure_coordinates_preserve_top_anchor_and_order():
    _provider, _spec, _reference, _state0, _contract, numerical, _storage = (
        _problem()
    )
    pressure = pressure_profile_from_coordinates(
        numerical, np.asarray([0.002, 0.004, 0.006, 0.008])
    )

    assert pressure[0] == numerical.reference_pressure_psia[0]
    assert np.allclose(
        pressure[1:] - numerical.reference_pressure_psia[1:],
        [0.02, 0.04, 0.06, 0.08],
    )
    assert np.all(np.diff(pressure) > 0.0)


def test_dd102_live_residual_extends_accepted_dynamic_ledger_to_42():
    provider, spec, reference, state, contract, numerical, storage = _problem()
    audit = ProviderCallAudit()
    evaluation = evaluate_pressure_layer_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        inventory_lbmol=inventory_from_state(state),
        rate_coordinates=np.zeros(15),
        base_algebraic_coordinates=dynamic_algebraic_coordinates(
            spec, reference, state
        ),
        pressure_coordinates=np.zeros(4),
        storage_gradient_BTU_lbmol=storage,
        fixed_steady_scales=_scales(),
        numerical=numerical,
        state_id="pressure_root",
        evaluation_kind="residual",
    )

    assert evaluation.raw.shape == evaluation.scaled.shape == (42,)
    assert len(evaluation.row_names) == len(evaluation.variable_names) == 42
    assert np.all(np.isfinite(evaluation.pressure_drop.raw_residual_psia))
    assert np.all(evaluation.pressure_drop.vapor_compressibility_factor > 0.0)
    assert (
        evaluation.base_evaluation.steady_evaluation.component_telescoping_relative_error
        < 1.0e-12
    )
    assert evaluation.base_evaluation.steady_evaluation.energy_telescoping_relative_error < 1.0e-10
    z_records = [
        record
        for record in audit.records
        if record.quantity == "vapor_compressibility_factor"
    ]
    assert len(z_records) == 4
    assert audit.report()["pass"]


def test_dd102_analytic_pressure_jacobian_is_full_rank_and_registered():
    provider, spec, reference, state, contract, numerical, storage = _problem()
    audit = audit_pressure_layer_jacobian(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory_from_state(state),
        root_base_algebraic_coordinates=dynamic_algebraic_coordinates(
            spec, reference, state
        ),
        pressure_coordinates=np.zeros(4),
        storage_gradient_BTU_lbmol=storage,
        fixed_steady_scales=_scales(),
        numerical=numerical,
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        state_id="pressure_jacobian",
    )

    assert audit.matrix.shape == (42, 42)
    assert audit.rank == 42
    assert np.isfinite(audit.condition)
    assert not audit.zero_rows
    assert not audit.zero_columns
    assert not audit.unexpected_couplings
