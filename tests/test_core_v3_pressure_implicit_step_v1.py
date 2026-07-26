import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    component_rate_scales,
    governing_storage_vector,
    zero_rate_evaluation,
)
from dynamic_distillation.core_v3.pressure_implicit_dae_contract_v1 import (
    build_pressure_implicit_dae_contract,
)
from dynamic_distillation.core_v3.pressure_implicit_step_v1 import (
    evaluate_pressure_backward_euler_residual,
    pressure_step_pattern,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import (
    PressureLinkGeometry,
    PressureNumericalSpec,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_dynamic_dae_numerical_audit_v1 import _scales, _state
from test_core_v3_provider_governed_residual_v1 import _fixture


def _basis():
    provider, spec, reference = _fixture()
    provider.vapor_z_factor_F_psia = lambda _temperature, _pressure, _z: 1.0
    state = _state(reference)
    contract = build_pressure_implicit_dae_contract(spec.component_names)
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    baseline = zero_rate_evaluation(
        contract.pressure_contract.base_contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory,
        algebraic_coordinates=algebraic,
        fixed_steady_scales=_scales(),
        state_id="dd105_test_basis",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(
        contract.pressure_contract.base_contract, baseline
    )
    storage = governing_storage_vector(spec, baseline, inventory)
    geometry = tuple(
        PressureLinkGeometry(100.0, 120.0, 1.0, include_liquid_head=index != 0)
        for index in range(4)
    )
    numerical = PressureNumericalSpec(
        reference_pressure_psia=np.asarray(spec.pressure_psia),
        pressure_coordinate_scale_psia=10.0,
        pressure_residual_scale_psia=1.0,
        dry_tray_pressure_drop_coefficient=40.0,
        component_mw_lbm_per_lbmol=np.asarray((44.1, 58.1, 72.2)),
        link_geometry=geometry,
        enforce_pressure_order=False,
    )
    point = np.concatenate((np.zeros(15), algebraic, np.zeros(4)))
    return provider, spec, reference, state, contract, inventory, rate_scales, storage, numerical, point


def test_dd105_pressure_step_residual_is_42_and_uses_exact_storage():
    provider, spec, reference, state, contract, inventory, scales, storage, numerical, point = _basis()
    result = evaluate_pressure_backward_euler_residual(
        contract, spec, reference, state, provider, ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        rate_scales_lbmolph=scales,
        solve_coordinates=point,
        step_seconds=1.0,
        fixed_steady_scales=_scales(),
        numerical=numerical,
        state_id="dd105_stationary",
        evaluation_kind="residual",
    )
    assert result.raw.shape == result.scaled.shape == (42,)
    assert np.array_equal(result.endpoint_inventory_lbmol, inventory)
    assert np.allclose(result.energy_storage_rate_BTUph, 0.0)


def test_dd105_pressure_motion_changes_storage_even_without_inventory_motion():
    provider, spec, reference, state, contract, inventory, scales, storage, numerical, point = _basis()
    point[-4:] = (-0.01, -0.02, -0.03, -0.04)
    result = evaluate_pressure_backward_euler_residual(
        contract, spec, reference, state, provider, ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        rate_scales_lbmolph=scales,
        solve_coordinates=point,
        step_seconds=1.0,
        fixed_steady_scales=_scales(),
        numerical=numerical,
        state_id="dd105_pressure_move",
        evaluation_kind="residual",
    )
    assert np.allclose(result.component_rate_lbmolph, 0.0)
    assert np.any(np.abs(result.energy_storage_rate_BTUph) > 0.0)


def test_dd105_pattern_is_42_by_42_and_uses_twenty_colors():
    contract = _basis()[4]
    pattern = pressure_step_pattern(contract)
    assert pattern.shape == (42, 42)
    assert len(greedy_column_groups(pattern)) == 20
