import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    audit_storage_gradient,
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import PhysicalState
from dynamic_distillation.core_v3.terminal_inventory_control_contract_v1 import (
    TerminalPIParameters,
    TerminalVesselGeometry,
    build_terminal_inventory_control_contract,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
    horizontal_terminal_level_fraction,
    horizontal_terminal_liquid_volume_ft3,
    horizontal_terminal_total_volume_ft3,
    terminal_inventory_control_pattern,
    terminal_inventory_control_variable_names,
)
from test_core_v3_provider_governed_residual_v1 import _fixture


def _geometry():
    return TerminalVesselGeometry(
        top_diameter_ft=30.0,
        top_tangent_length_ft=90.0,
        top_head_shape="two_hemispherical",
        bottom_diameter_ft=30.0,
        bottom_height_ft=40.0,
    )


def _contract(components):
    return build_terminal_inventory_control_contract(
        build_dynamic_dae_contract(components),
        geometry=_geometry(),
        controllers=TerminalPIParameters(
            top_kc=0.5,
            top_ti_sec=120.0,
            bottom_kc=8.0,
            bottom_ti_sec=120.0,
            product_rate_ratio_bounds=(0.25, 2.0),
        ),
    )


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


def _point(contract, spec, reference, state):
    return np.concatenate(
        (
            np.zeros(len(contract.base.derivative_variables)),
            np.zeros(2),
            dynamic_algebraic_coordinates(spec, reference, state),
            np.zeros(2),
        )
    )


def test_dd185_horizontal_geometry_is_symmetric_and_invertible():
    geometry = _geometry()
    total = horizontal_terminal_total_volume_ft3(geometry)

    assert horizontal_terminal_liquid_volume_ft3(0.0, geometry) == 0.0
    assert np.isclose(
        horizontal_terminal_liquid_volume_ft3(geometry.top_diameter_ft, geometry),
        total,
    )
    assert np.isclose(horizontal_terminal_level_fraction(0.5 * total, geometry), 0.5)


def test_dd185_five_volume_pattern_is_42_by_42_and_full_rank():
    contract = _contract(("Propane", "n-Butane", "n-Pentane"))
    pattern = terminal_inventory_control_pattern(contract)

    assert pattern.shape == (42, 42)
    assert len(terminal_inventory_control_variable_names(contract)) == 42
    assert structural_rank(csr_matrix(pattern)) == 42


def test_dd185_bumpless_zero_time_controller_rows_close():
    provider, spec, reference = _fixture()
    state = _state(reference)
    contract = _contract(spec.component_names)
    inventory = inventory_from_state(state)
    storage = audit_storage_gradient(
        spec,
        state,
        provider,
        ProviderCallAudit(),
        relative_steps=(1.0e-5,),
        state_id="dd185_test_storage",
    )
    common = dict(
        contract=contract,
        spec=spec,
        reference=reference,
        template=state,
        provider=provider,
        inventory_lbmol=inventory,
        controller_memory=np.zeros(2),
        solve_coordinates=_point(contract, spec, reference, state),
        storage_gradient_BTU_lbmol=storage.steps[0].gradient_BTU_lbmol,
        fixed_steady_scales=_scales(),
        evaluation_kind="residual",
    )
    seed = evaluate_terminal_inventory_control_residual(
        **common,
        call_audit=ProviderCallAudit(),
        level_setpoints=TerminalLevelSetpoints(0.5, 0.5),
        state_id="dd185_test_seed",
    )
    baseline = evaluate_terminal_inventory_control_residual(
        **common,
        call_audit=ProviderCallAudit(),
        level_setpoints=TerminalLevelSetpoints(*seed.level_fraction),
        state_id="dd185_test_baseline",
    )

    assert baseline.scaled.shape == (42,)
    assert np.max(np.abs(baseline.scaled[-4:])) == 0.0
    assert np.array_equal(baseline.controller_rate_per_sec, np.zeros(2))
    assert np.array_equal(baseline.product_log_ratio, np.zeros(2))
    assert baseline.distillate_lbmolph == state.distillate_lbmolph
    assert baseline.bottoms_lbmolph == state.bottoms_lbmolph
    assert np.all((baseline.level_fraction > 0.0) & (baseline.level_fraction < 1.0))
