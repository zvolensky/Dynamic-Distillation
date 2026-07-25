import numpy as np

from dynamic_distillation.core_v3.dynamic_dae_contract_v1 import (
    build_dynamic_dae_contract,
)
from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    central_difference_jacobian,
    component_rate_scales,
    evaluate_backward_euler_residual,
    saturated_storage_vector,
    zero_rate_evaluation,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from test_core_v3_dynamic_dae_numerical_audit_v1 import _scales, _state
from test_core_v3_provider_governed_residual_v1 import _fixture


def _basis():
    provider, spec, reference = _fixture()
    state = _state(reference)
    contract = build_dynamic_dae_contract(spec.component_names)
    inventory = inventory_from_state(state)
    algebraic = dynamic_algebraic_coordinates(spec, reference, state)
    baseline = zero_rate_evaluation(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory,
        algebraic_coordinates=algebraic,
        fixed_steady_scales=_scales(),
        state_id="step_basis",
        evaluation_kind="residual",
    )
    rate_scales = component_rate_scales(contract, baseline)
    storage, _ = saturated_storage_vector(
        spec,
        state,
        provider,
        ProviderCallAudit(),
        inventory,
        state_id="step_storage",
        evaluation_kind="residual",
    )
    return (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        algebraic,
        baseline,
        rate_scales,
        storage,
    )


def test_dd097_central_difference_jacobian_matches_known_rectangular_system():
    def objective(point, _state_id):
        return np.asarray(
            (
                point[0] + 2.0 * point[1],
                point[0] ** 2 - point[1],
                3.0 * point[1],
            )
        )

    point = np.asarray((0.4, -0.2))
    result = central_difference_jacobian(
        objective, point, step=1.0e-6, state_id="known"
    )
    expected = np.asarray(((1.0, 2.0), (0.8, -1.0), (0.0, 3.0)))

    assert np.allclose(result, expected, atol=1.0e-9)


def test_dd097_zero_rate_evaluation_retains_dd095_row_ledger():
    *_, contract, _inventory, _algebraic, baseline, _rate_scales, _storage = (
        _basis()
    )

    assert baseline.raw.shape == baseline.scaled.shape == (38,)
    assert baseline.row_names == tuple(row.name for row in contract.rows)
    assert np.allclose(baseline.component_rate_lbmolph, 0.0)
    assert np.allclose(baseline.energy_storage_rate_BTUph, 0.0)


def test_dd097_zero_rate_backward_euler_endpoint_is_exactly_stationary():
    (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        algebraic,
        baseline,
        rate_scales,
        storage,
    ) = _basis()
    point = np.concatenate((np.zeros(15), algebraic))
    evaluation = evaluate_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        rate_scales_lbmolph=rate_scales,
        solve_coordinates=point,
        step_seconds=1.0,
        fixed_steady_scales=_scales(),
        state_id="stationary",
        evaluation_kind="residual",
    )

    assert np.array_equal(evaluation.endpoint_inventory_lbmol, inventory)
    assert np.allclose(evaluation.component_rate_lbmolph, 0.0)
    assert np.allclose(evaluation.energy_storage_rate_BTUph, 0.0)
    assert np.allclose(evaluation.raw, baseline.raw, atol=1.0e-8)
    assert evaluation.maximum_bubble_residual < 1.0e-10


def test_dd097_exponential_endpoint_map_is_positive_and_closes_be_rate():
    (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        algebraic,
        _baseline,
        rate_scales,
        storage,
    ) = _basis()
    nominal_rates = np.linspace(-1.0e-8, 1.0e-8, 15)
    point = np.concatenate((nominal_rates, algebraic))
    step_seconds = 2.0
    evaluation = evaluate_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        rate_scales_lbmolph=rate_scales,
        solve_coordinates=point,
        step_seconds=step_seconds,
        fixed_steady_scales=_scales(),
        state_id="moving",
        evaluation_kind="residual",
    )
    reconstructed = inventory + (
        step_seconds / 3600.0
    ) * evaluation.component_rate_lbmolph

    assert np.all(evaluation.endpoint_inventory_lbmol > 0.0)
    assert np.allclose(evaluation.endpoint_inventory_lbmol, reconstructed)
    assert np.all(np.isfinite(evaluation.endpoint_internal_energy_BTU))
    assert np.any(np.abs(evaluation.energy_storage_rate_BTUph) > 0.0)


def test_dd097_invalid_step_is_rejected_without_clipping():
    (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        algebraic,
        _baseline,
        rate_scales,
        storage,
    ) = _basis()
    point = np.concatenate((np.zeros(15), algebraic))

    try:
        evaluate_backward_euler_residual(
            contract,
            spec,
            reference,
            state,
            provider,
            ProviderCallAudit(),
            previous_inventory_lbmol=inventory,
            previous_internal_energy_BTU=storage,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=point,
            step_seconds=0.0,
            fixed_steady_scales=_scales(),
            state_id="invalid",
            evaluation_kind="residual",
        )
    except ValueError as exc:
        assert "step must be positive" in str(exc)
    else:
        raise AssertionError("zero backward-Euler step was accepted")


def test_dd097_storage_property_chain_is_recorded_as_governing():
    provider, spec, reference = _fixture()
    state = _state(reference)
    audit = ProviderCallAudit()
    storage, bubble = saturated_storage_vector(
        spec,
        state,
        provider,
        audit,
        inventory_from_state(state),
        state_id="governing_storage",
        evaluation_kind="residual",
    )

    assert np.all(np.isfinite(storage))
    assert bubble < 1.0e-10
    assert audit.records
    assert {record.evaluation_kind for record in audit.records} == {"residual"}
    assert audit.report()["pass"]
