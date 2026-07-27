import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.conserved_nu_implicit_step_v1 import (
    audit_conserved_nu_step_jacobian,
    conserved_nu_step_pattern,
    evaluate_conserved_nu_backward_euler_residual,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_conserved_nu_pressure_numerical_v1 import _nu_basis
from test_core_v3_dynamic_dae_numerical_audit_v1 import _scales


def _evaluate(point, *, step_seconds=1.0):
    provider, spec, reference, state, contract, inventory, storage, numerical, _ = _nu_basis()
    return evaluate_conserved_nu_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_top_internal_energy_BTU=storage[0],
        previous_lower_internal_energy_BTU=storage[1:],
        component_rate_scale_lbmolph=12584.8,
        energy_rate_scales_BTUph=np.full(4, 1.0e8),
        solve_coordinates=point,
        step_seconds=step_seconds,
        fixed_steady_scales=_scales(),
        storage_scales_BTU=np.maximum(np.abs(storage[1:]), 1.0),
        numerical=numerical,
        state_id="dd115_test",
        evaluation_kind="residual",
    )


def test_dd115_stationary_kinematics_preserve_n_and_u():
    point = _nu_basis()[-1]
    result = _evaluate(point)

    assert result.raw.shape == result.scaled.shape == (46,)
    assert np.array_equal(
        result.endpoint_inventory_lbmol, result.previous_inventory_lbmol
    )
    assert np.array_equal(
        result.endpoint_lower_internal_energy_BTU,
        result.previous_lower_internal_energy_BTU,
    )
    assert np.allclose(result.component_rate_lbmolph, 0.0)
    assert np.allclose(result.internal_energy_rate_BTUph, 0.0)


def test_dd115_nonzero_rates_advance_conserved_states_exactly():
    point = _nu_basis()[-1].copy()
    point[:3] = (0.01, -0.02, 0.03)
    point[15:19] = (0.1, -0.2, 0.3, -0.4)
    result = _evaluate(point, step_seconds=0.5)
    step_hours = 0.5 / 3600.0

    assert np.allclose(
        result.endpoint_inventory_lbmol - result.previous_inventory_lbmol,
        step_hours * result.component_rate_lbmolph,
    )
    assert np.allclose(
        result.endpoint_lower_internal_energy_BTU
        - result.previous_lower_internal_energy_BTU,
        step_hours * result.internal_energy_rate_BTUph[1:],
    )
    assert np.isclose(
        result.endpoint_top_internal_energy_BTU
        - result.previous_top_internal_energy_BTU,
        step_hours * result.internal_energy_rate_BTUph[0],
    )


def test_dd115_step_pattern_is_square_and_conflict_free():
    contract = _nu_basis()[4]
    pattern = conserved_nu_step_pattern(contract)
    groups = greedy_column_groups(pattern)

    assert pattern.shape == (46, 46)
    assert 0 < len(groups) < 46
    for group in groups:
        occupied = np.concatenate(
            [np.flatnonzero(pattern[:, column]) for column in group]
        )
        assert np.unique(occupied).size == occupied.size


def test_dd115_pressure_motion_enters_lower_storage_closure():
    point = _nu_basis()[-1].copy()
    point[-4:] = (-0.01, -0.02, -0.03, -0.04)
    result = _evaluate(point)

    assert np.any(np.abs(result.dae_evaluation.storage_closure_BTU) > 0.0)


def test_dd115_colored_step_jacobian_matches_full_fixture_difference():
    contract = _nu_basis()[4]
    point = _nu_basis()[-1]

    def objective(candidate, _state_id):
        return _evaluate(candidate)

    colored = audit_conserved_nu_step_jacobian(
        contract,
        objective,
        point,
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
    )
    full = np.empty_like(colored.matrix)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = 1.0e-5
        full[:, column] = (
            objective(point + delta, "full_plus").scaled
            - objective(point - delta, "full_minus").scaled
        ) / 2.0e-5

    assert colored.rank == 46
    assert not colored.zero_rows
    assert not colored.zero_columns
    assert not colored.unexpected_couplings
    assert np.allclose(colored.matrix, full, rtol=1.0e-8, atol=1.0e-9)
