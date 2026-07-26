import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import (
    colored_central_difference_jacobian,
    contract_sparsity_pattern,
    greedy_column_groups,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    central_difference_jacobian,
    evaluate_backward_euler_residual,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_dynamic_dae_numerical_audit_v1 import _scales
from test_core_v3_implicit_step_v1 import _basis


def test_dd099_coloring_matches_known_sparse_jacobian_with_fewer_calls():
    calls = []

    def objective(point, state_id):
        calls.append(state_id)
        return np.asarray(
            (
                point[0] + point[2] ** 2,
                2.0 * point[1],
                point[0] - 3.0 * point[2],
            )
        )

    point = np.asarray((0.4, -0.2, 0.7))
    pattern = np.asarray(
        (
            (True, False, True),
            (False, True, False),
            (True, False, True),
        )
    )
    matrix, groups = colored_central_difference_jacobian(
        objective,
        point,
        pattern=pattern,
        step=1.0e-6,
        state_id="known_colored",
    )
    expected = np.asarray(((1.0, 0.0, 1.4), (0.0, 2.0, 0.0), (1.0, 0.0, -3.0)))

    assert groups == ((0, 1), (2,))
    assert len(calls) == 2 * len(groups) == 4
    assert np.allclose(matrix, expected, atol=1.0e-9)


def test_dd099_backward_euler_pattern_includes_inventory_rate_chain():
    *_prefix, contract, _inventory, _algebraic, _baseline, _rate_scales, _storage = _basis()
    pattern, names = contract_sparsity_pattern(
        contract, include_state_rate_dependencies=True
    )
    groups = greedy_column_groups(pattern)
    equilibrium_row = next(
        index
        for index, row in enumerate(contract.rows)
        if row.name == "full_phase_equilibrium[feed_tray,A]"
    )

    for component in contract.component_names:
        rate_name = f"dN[feed_tray,{component}]/dt"
        assert pattern[equilibrium_row, names.index(rate_name)]
    assert len(groups) == 17
    assert 2 * len(groups) == 34


def test_dd099_colored_backward_euler_jacobian_matches_uncolored_fixture():
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
    point = np.concatenate((np.linspace(-1.0e-8, 1.0e-8, 15), algebraic))

    def objective(coordinates, state_id):
        return evaluate_backward_euler_residual(
            contract,
            spec,
            reference,
            state,
            provider,
            ProviderCallAudit(),
            previous_inventory_lbmol=inventory,
            previous_internal_energy_BTU=storage,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=coordinates,
            step_seconds=1.0,
            fixed_steady_scales=_scales(),
            state_id=state_id,
            evaluation_kind="jacobian",
        ).scaled

    pattern, _names = contract_sparsity_pattern(
        contract, include_state_rate_dependencies=True
    )
    uncolored = central_difference_jacobian(
        objective, point, step=1.0e-6, state_id="uncolored"
    )
    colored, groups = colored_central_difference_jacobian(
        objective,
        point,
        pattern=pattern,
        step=1.0e-6,
        state_id="colored",
    )

    assert len(groups) == 17
    assert np.allclose(colored, uncolored, atol=2.0e-7, rtol=2.0e-7)


def test_dd099_backward_euler_storage_uses_no_nested_bubble_calls():
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
    audit = ProviderCallAudit()
    point = np.concatenate((np.zeros(15), algebraic))
    evaluation = evaluate_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        audit,
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        rate_scales_lbmolph=rate_scales,
        solve_coordinates=point,
        step_seconds=1.0,
        fixed_steady_scales=_scales(),
        state_id="property_reuse",
        evaluation_kind="residual",
    )

    assert np.all(np.isfinite(evaluation.endpoint_internal_energy_BTU))
    assert not any(
        record.quantity == "bubble_temperature_and_incipient_vapor"
        for record in audit.records
    )
    assert not any(
        record.caller.startswith("implicit_energy_storage")
        for record in audit.records
    )
    assert sum(record.quantity == "liquid_density" for record in audit.records) == 5
