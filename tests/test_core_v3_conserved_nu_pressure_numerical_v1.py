import numpy as np

from dynamic_distillation.core_v3.colored_jacobian_v1 import greedy_column_groups
from dynamic_distillation.core_v3.conserved_nu_pressure_dae_contract_v1 import (
    build_conserved_nu_pressure_dae_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_numerical_v1 import (
    audit_conserved_nu_leading_jacobian,
    evaluate_conserved_nu_pressure_residual,
    nu_pressure_pattern,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_dynamic_dae_numerical_audit_v1 import _scales
from test_core_v3_pressure_implicit_step_v1 import _basis


def _nu_basis():
    (
        provider,
        spec,
        reference,
        state,
        _pressure_contract,
        inventory,
        _rate_scales,
        storage,
        numerical,
        pressure_point,
    ) = _basis()
    contract = build_conserved_nu_pressure_dae_contract(spec.component_names)
    point = np.concatenate(
        (
            pressure_point[:15],
            np.zeros(4),
            pressure_point[15:],
        )
    )
    return (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        storage,
        numerical,
        point,
    )


def _evaluate(point, *, storage=None, top_gradient=None):
    provider, spec, reference, state, contract, inventory, basis_storage, numerical, _ = _nu_basis()
    if storage is None:
        storage = basis_storage[1:]
    if top_gradient is None:
        top_gradient = np.asarray((100.0, 200.0, 300.0))
    return evaluate_conserved_nu_pressure_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory,
        lower_internal_energy_BTU=storage,
        top_storage_gradient_BTU_lbmol=top_gradient,
        energy_rate_scales_BTUph=np.full(4, 1.0e8),
        solve_coordinates=point,
        fixed_steady_scales=_scales(),
        storage_scales_BTU=np.maximum(np.abs(storage), 1.0),
        numerical=numerical,
        state_id="dd109_test",
        evaluation_kind="residual",
    )


def test_dd109_live_residual_has_46_rows_and_exact_stationary_storage():
    point = _nu_basis()[-1]
    result = _evaluate(point)

    assert result.raw.shape == result.scaled.shape == (46,)
    assert np.allclose(result.component_rate_lbmolph, 0.0)
    assert np.allclose(result.internal_energy_rate_BTUph, 0.0)
    assert np.allclose(result.storage_closure_BTU, 0.0)


def test_dd109_lower_energy_rate_coordinates_own_lower_energy_rows():
    point = _nu_basis()[-1].copy()
    baseline = _evaluate(point)
    point[15:19] = (0.1, -0.2, 0.3, -0.4)
    result = _evaluate(point)
    energy_rows = np.asarray(
        [index for index, name in enumerate(result.row_names) if name.startswith("energy_balance[")]
    )

    assert np.allclose(
        result.raw[energy_rows[1:]] - baseline.raw[energy_rows[1:]],
        np.asarray((0.1, -0.2, 0.3, -0.4)) * 1.0e8,
    )
    assert result.raw[energy_rows[0]] == baseline.raw[energy_rows[0]]


def test_dd109_top_energy_uses_fixed_pressure_inventory_gradient():
    point = _nu_basis()[-1].copy()
    baseline = _evaluate(point)
    point[0:3] = (0.2, -0.1, 0.3)
    result = _evaluate(point, top_gradient=np.asarray((100.0, 200.0, 300.0)))
    top_energy = next(
        index
        for index, name in enumerate(result.row_names)
        if name == "energy_balance[reflux_drum]"
    )
    expected = float(
        np.dot(
            np.asarray((100.0, 200.0, 300.0)),
            result.component_rate_lbmolph[0],
        )
    )

    assert np.isclose(result.raw[top_energy] - baseline.raw[top_energy], expected)


def test_dd109_pressure_motion_is_seen_by_lower_storage_closure():
    point = _nu_basis()[-1].copy()
    point[-4:] = (-0.01, -0.02, -0.03, -0.04)
    result = _evaluate(point)

    assert np.any(np.abs(result.storage_closure_BTU) > 0.0)


def test_dd109_pattern_is_square_and_colored_without_conflict():
    contract = _nu_basis()[4]
    pattern = nu_pressure_pattern(contract)
    groups = greedy_column_groups(pattern)

    assert pattern.shape == (46, 46)
    assert 0 < len(groups) < 46
    for group in groups:
        occupied = np.concatenate(
            [np.flatnonzero(pattern[:, column]) for column in group]
        )
        assert np.unique(occupied).size == occupied.size


def test_dd109_colored_and_full_jacobians_agree_for_registered_fixture():
    contract = _nu_basis()[4]
    point = _nu_basis()[-1]

    def objective(candidate, _state_id):
        return _evaluate(candidate)

    colored = audit_conserved_nu_leading_jacobian(
        contract,
        objective,
        point,
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        use_coloring=True,
    )
    full = audit_conserved_nu_leading_jacobian(
        contract,
        objective,
        point,
        step=1.0e-5,
        coupling_tolerance=1.0e-7,
        use_coloring=False,
    )

    assert colored.color_count < full.color_count == 46
    assert np.allclose(colored.matrix, full.matrix, rtol=1.0e-8, atol=1.0e-10)
    assert not full.unexpected_couplings
