import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    audit_leading_jacobian,
    audit_storage_gradient,
    dynamic_algebraic_coordinates,
    evaluate_dynamic_implicit_residual,
    inventory_from_state,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    PhysicalState,
)
from test_core_v3_provider_governed_residual_v1 import _fixture


def _state(reference):
    return PhysicalState(
        liquid_moles_lbmol=reference.liquid_moles_lbmol,
        liquid_mole_fraction=reference.liquid_mole_fraction,
        temperature_F=reference.temperature_F,
        vapor_mole_fraction=reference.vapor_mole_fraction,
        hydraulic_liquid_flow_lbmolph=(
            reference.hydraulic_liquid_flow_lbmolph
        ),
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


def _gradient(provider, spec, state):
    return audit_storage_gradient(
        spec,
        state,
        provider,
        ProviderCallAudit(),
        relative_steps=(1.0e-5, 5.0e-6),
        state_id="analytic_storage",
    )


def test_dd096_storage_gradient_is_finite_and_step_stable():
    provider, spec, reference = _fixture()
    result = _gradient(provider, spec, _state(reference))

    assert len(result.steps) == 2
    assert result.steps[0].gradient_BTU_lbmol.shape == (5, 3)
    assert result.all_finite
    assert result.maximum_relative_change < 1.0e-6
    assert max(step.maximum_bubble_residual for step in result.steps) < 1.0e-10


def test_dd096_zero_rate_mapping_preserves_fixed_products_and_row_ledger():
    provider, spec, reference = _fixture()
    state = _state(reference)
    contract = build_dynamic_dae_contract(spec.component_names)
    storage = _gradient(provider, spec, state)
    evaluation = evaluate_dynamic_implicit_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory_from_state(state),
        rate_coordinates=np.zeros(15),
        algebraic_coordinates=dynamic_algebraic_coordinates(
            spec, reference, state
        ),
        storage_gradient_BTU_lbmol=storage.steps[0].gradient_BTU_lbmol,
        fixed_steady_scales=_scales(),
        state_id="analytic_dynamic",
        evaluation_kind="residual",
    )

    assert evaluation.raw.shape == evaluation.scaled.shape == (38,)
    assert evaluation.row_names == tuple(row.name for row in contract.rows)
    assert np.allclose(evaluation.component_rate_lbmolph, 0.0)
    assert np.allclose(evaluation.energy_storage_rate_BTUph, 0.0)
    assert evaluation.physical_state.distillate_lbmolph == state.distillate_lbmolph
    assert evaluation.physical_state.bottoms_lbmolph == state.bottoms_lbmolph
    assert not any("terminal_amount" in name for name in evaluation.row_names)


def test_dd096_rate_coordinates_have_identity_component_balance_scaling():
    provider, spec, reference = _fixture()
    state = _state(reference)
    contract = build_dynamic_dae_contract(spec.component_names)
    storage = _gradient(provider, spec, state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    inventory = inventory_from_state(state)
    delta = 1.0e-6
    plus_rate = np.zeros(15)
    minus_rate = np.zeros(15)
    plus_rate[4] = delta
    minus_rate[4] = -delta
    common = dict(
        contract=contract,
        spec=spec,
        reference=reference,
        template=state,
        provider=provider,
        inventory_lbmol=inventory,
        algebraic_coordinates=algebraic,
        storage_gradient_BTU_lbmol=storage.steps[0].gradient_BTU_lbmol,
        fixed_steady_scales=_scales(),
        evaluation_kind="jacobian",
    )
    plus = evaluate_dynamic_implicit_residual(
        **common,
        call_audit=ProviderCallAudit(),
        rate_coordinates=plus_rate,
        state_id="rate_plus",
    ).scaled
    minus = evaluate_dynamic_implicit_residual(
        **common,
        call_audit=ProviderCallAudit(),
        rate_coordinates=minus_rate,
        state_id="rate_minus",
    ).scaled
    column = (plus - minus) / (2.0 * delta)

    assert np.isclose(column[4], 1.0)
    assert np.count_nonzero(np.abs(column[:15]) > 1.0e-10) == 1
    assert np.any(np.abs(column[15:20]) > 0.0)


def test_dd096_analytic_leading_jacobian_matches_contract_and_is_full_rank():
    provider, spec, reference = _fixture()
    state = _state(reference)
    contract = build_dynamic_dae_contract(spec.component_names)
    storage = _gradient(provider, spec, state)
    audit = audit_leading_jacobian(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory_from_state(state),
        root_algebraic_coordinates=dynamic_algebraic_coordinates(
            spec, reference, state
        ),
        storage_gradient_BTU_lbmol=storage.steps[0].gradient_BTU_lbmol,
        fixed_steady_scales=_scales(),
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        state_id="analytic_leading",
    )

    assert audit.matrix.shape == (38, 38)
    assert audit.rank == 38
    assert np.isfinite(audit.condition)
    assert audit.zero_rows == ()
    assert audit.zero_columns == ()
    assert audit.unexpected_couplings == ()
