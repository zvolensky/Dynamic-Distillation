import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import (
    audit_zero_rate_jacobian,
    evaluate_zero_rate_readiness,
    expand_zero_rate_coordinates,
    zero_rate_pattern,
)
from test_core_v3_conserved_nu_pressure_initializer_numerical_v1 import _fixture


def _zero_fixture():
    provider, spec, reference, state, contract, numerical, canonical, common = _fixture()
    point = np.concatenate((canonical[:19], canonical[38:]))
    return provider, spec, reference, state, contract, numerical, point, common


def _evaluate(point):
    provider, spec, reference, state, contract, numerical, _, common = _zero_fixture()
    return evaluate_zero_rate_readiness(
        contract,
        numerical,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        coordinates=point,
        state_id="dd119_test",
        evaluation_kind="residual",
        **common,
    )


def test_dd119_expansion_preserves_state_and_algebraic_and_zeros_rates():
    contract = _zero_fixture()[4]
    point = _zero_fixture()[6] + np.linspace(-0.1, 0.1, 46)
    expanded = expand_zero_rate_coordinates(contract, point)

    assert expanded.shape == (65,)
    assert np.allclose(expanded[:19], point[:19])
    assert np.allclose(expanded[19:38], 0.0)
    assert np.allclose(expanded[38:], point[19:])


def test_dd119_pattern_is_48_by_46_and_conflict_free():
    contract = _zero_fixture()[4]
    pattern = zero_rate_pattern(contract)

    assert pattern.shape == (48, 46)
    for group in greedy_column_groups(pattern):
        occupied = np.concatenate(
            [np.flatnonzero(pattern[:, column]) for column in group]
        )
        assert np.unique(occupied).size == occupied.size


def test_dd119_evaluation_selects_dae_and_terminal_rows_only():
    result = _evaluate(_zero_fixture()[6])

    assert result.scaled.shape == (48,)
    assert result.dae_scaled.shape == (46,)
    assert result.terminal_scaled.shape == (2,)
    assert np.allclose(result.scaled[:46], result.full_evaluation.scaled[:46])
    assert np.allclose(result.scaled[46:], result.full_evaluation.scaled[-2:])
    assert np.allclose(result.component_total_residual_lbmol, 0.0)
    assert np.isclose(result.stored_energy_residual_BTU, 0.0, atol=1.0e-8)


def test_dd119_colored_jacobian_matches_full_difference():
    contract = _zero_fixture()[4]
    point = _zero_fixture()[6]

    def objective(candidate, _state_id):
        return _evaluate(candidate).scaled

    result = _evaluate(point)
    colored = audit_zero_rate_jacobian(
        contract,
        objective,
        point,
        result.scaled,
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        state_id="dd119_test",
    )
    full = np.empty((48, 46))
    for column in range(46):
        delta = np.zeros(46)
        delta[column] = 1.0e-5
        full[:, column] = (objective(point + delta, "plus") - objective(point - delta, "minus")) / 2.0e-5

    assert np.allclose(colored.matrix, full, rtol=1.0e-8, atol=1.0e-9)
    assert colored.augmented_rank == 46
    assert not colored.zero_columns
    assert not colored.unexpected_couplings
