from dataclasses import replace

import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    InitializerConstraint,
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerNumericalSpec,
    InitializerSolveSettings,
    audit_initializer_constraint_jacobian,
    decode_initializer_coordinates,
    evaluate_initializer_constraints,
    initializer_constraint_pattern,
    initializer_objective,
    initializer_objective_gradient,
    kkt_stationarity_inf_norm,
    solve_equality_constrained_initializer,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_conserved_nu_pressure_numerical_v1 import _nu_basis
from test_core_v3_dynamic_dae_numerical_audit_v1 import _scales


def _fixture():
    (
        provider,
        spec,
        reference,
        state,
        _nu_contract,
        inventory,
        storage,
        pressure_numerical,
        solve_point,
    ) = _nu_basis()
    contract = build_conserved_nu_pressure_initializer_contract(spec.component_names)
    canonical = np.concatenate((np.zeros(19), solve_point))
    numerical = InitializerNumericalSpec(
        inventory_reference_lbmol=inventory,
        lower_internal_energy_reference_BTU=storage[1:],
        lower_internal_energy_scale_BTU=np.maximum(np.abs(storage[1:]), 1.0),
        component_total_targets_lbmol=np.sum(inventory, axis=0),
        stored_energy_target_BTU=float(np.sum(storage)),
        terminal_total_targets_lbmol=np.asarray(
            (np.sum(inventory[0]), np.sum(inventory[-1]))
        ),
        objective_center=canonical,
        objective_weights=np.ones(65),
        lower_bounds=np.full(65, -10.0),
        upper_bounds=np.full(65, 10.0),
        jacobian_step=1.0e-5,
    )
    common = {
        "top_storage_gradient_BTU_lbmol": np.asarray((100.0, 200.0, 300.0)),
        "energy_rate_scales_BTUph": np.full(4, 1.0e8),
        "fixed_steady_scales": _scales(),
        "storage_scales_BTU": np.maximum(np.abs(storage[1:]), 1.0),
        "pressure_numerical": pressure_numerical,
    }
    return provider, spec, reference, state, contract, numerical, canonical, common


def _evaluate(point):
    provider, spec, reference, state, contract, numerical, _, common = _fixture()
    return evaluate_initializer_constraints(
        contract,
        numerical,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        coordinates=point,
        state_id="dd112_test",
        evaluation_kind="residual",
        **common,
    )


def test_dd112_canonical_coordinates_decode_to_reference_state():
    _, _, _, _, contract, numerical, canonical, _ = _fixture()
    inventory, lower_u, solve = decode_initializer_coordinates(
        contract, numerical, canonical
    )

    assert np.allclose(inventory, numerical.inventory_reference_lbmol)
    assert np.allclose(lower_u, numerical.lower_internal_energy_reference_BTU)
    assert np.allclose(solve, canonical[19:])


def test_dd112_constraint_vector_contains_exact_global_targets():
    canonical = _fixture()[6]
    result = _evaluate(canonical)

    assert result.scaled.shape == (52,)
    assert np.allclose(result.component_total_residual_lbmol, 0.0)
    assert np.isclose(result.stored_energy_residual_BTU, 0.0, atol=1.0e-8)
    assert np.allclose(result.terminal_total_residual_lbmol, 0.0)
    assert np.allclose(result.scaled[-6:], 0.0, atol=1.0e-12)


def test_dd112_constraint_pattern_is_52_by_65_with_21_colors():
    contract = _fixture()[4]
    pattern = initializer_constraint_pattern(contract)
    groups = greedy_column_groups(pattern)

    assert pattern.shape == (52, 65)
    assert len(groups) == 21
    for group in groups:
        occupied = np.concatenate(
            [np.flatnonzero(pattern[:, column]) for column in group]
        )
        assert np.unique(occupied).size == occupied.size


def test_dd112_colored_and_full_constraint_jacobians_agree():
    contract = _fixture()[4]
    canonical = _fixture()[6]

    def objective(candidate, _state_id):
        return _evaluate(candidate).scaled

    colored = audit_initializer_constraint_jacobian(
        contract,
        objective,
        canonical,
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        use_coloring=True,
    )
    full = audit_initializer_constraint_jacobian(
        contract,
        objective,
        canonical,
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        use_coloring=False,
    )

    assert colored.color_count == 21
    assert full.color_count == 65
    assert colored.rank == full.rank == 52
    assert np.allclose(colored.matrix, full.matrix, rtol=1.0e-8, atol=1.0e-9)
    assert not full.unexpected_couplings


def test_dd112_quadratic_objective_has_exact_gradient_and_stationarity_metric():
    numerical = _fixture()[5]
    point = numerical.objective_center + 0.1
    gradient = initializer_objective_gradient(numerical, point)

    assert np.isclose(initializer_objective(numerical, point), 0.5 * 65 * 0.01)
    assert np.allclose(gradient, 0.1)
    jacobian = np.zeros((1, 65))
    jacobian[0, 0] = 1.0
    assert kkt_stationarity_inf_norm(numerical, numerical.objective_center, jacobian) == 0.0


def test_dd112_slsqp_enforces_equality_without_penalty_relaxation():
    _, _, _, _, contract, numerical, canonical, _ = _fixture()
    first_name = contract.state_variables[0].name
    reduced = replace(
        contract,
        constraints=(
            InitializerConstraint(
                name="unit_test_equality",
                block="unit_test",
                owner="unit_test",
                dependencies=(first_name,),
            ),
        ),
    )

    outcome = solve_equality_constrained_initializer(
        reduced,
        numerical,
        canonical,
        lambda candidate, _state_id: np.asarray((candidate[0] - 1.0,)),
        settings=InitializerSolveSettings(maxiter=20),
    )

    assert outcome.success
    assert np.isclose(outcome.final_coordinates[0], 1.0, atol=1.0e-10)
    assert np.max(np.abs(outcome.final_constraints)) < 1.0e-10
