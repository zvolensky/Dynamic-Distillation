import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.controlled_terminal_implicit_step_v1 import (
    controlled_terminal_step_pattern,
    evaluate_controlled_terminal_backward_euler_residual,
)
from dynamic_distillation.core_v3.controlled_terminal_zero_time_v1 import (
    TerminalLevelSetpoints,
    terminal_level_fractions,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from test_core_v3_controlled_terminal_zero_time_v1 import _contract
from test_core_v3_conserved_nu_pressure_numerical_v1 import _nu_basis
from test_core_v3_dynamic_dae_numerical_audit_v1 import _scales


def _basis():
    provider, spec, reference, state, base, inventory, storage, numerical, point = _nu_basis()
    contract = _contract(spec.component_names)
    base_rate_count = len(base.derivative_variables)
    controlled_point = np.concatenate(
        (point[:base_rate_count], np.zeros(2), point[base_rate_count:], np.zeros(2))
    )
    base_eval = evaluate_controlled_terminal_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_top_internal_energy_BTU=storage[0],
        previous_lower_internal_energy_BTU=storage[1:],
        previous_controller_memory=np.zeros(2),
        level_setpoints=TerminalLevelSetpoints(0.5, 0.5),
        component_rate_scale_lbmolph=12584.8,
        energy_rate_scales_BTUph=np.full(4, 1.0e8),
        solve_coordinates=controlled_point,
        step_seconds=1.0,
        fixed_steady_scales=_scales(),
        storage_scales_BTU=np.maximum(np.abs(storage[1:]), 1.0),
        pressure_numerical=numerical,
        state_id="dd128_test_basis",
        evaluation_kind="residual",
    )
    levels = terminal_level_fractions(
        inventory,
        base_eval.base.dae_evaluation.pressure_evaluation.base_evaluation
        .steady_evaluation.properties.liquid_density_lbmol_ft3,
        contract.geometry,
    )
    return provider, spec, reference, state, contract, inventory, storage, numerical, controlled_point, levels


def _evaluate(point, memory, setpoints, step_seconds=1.0):
    provider, spec, reference, state, contract, inventory, storage, numerical, _, _ = _basis()
    return evaluate_controlled_terminal_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_top_internal_energy_BTU=storage[0],
        previous_lower_internal_energy_BTU=storage[1:],
        previous_controller_memory=memory,
        level_setpoints=TerminalLevelSetpoints(*setpoints),
        component_rate_scale_lbmolph=12584.8,
        energy_rate_scales_BTUph=np.full(4, 1.0e8),
        solve_coordinates=point,
        step_seconds=step_seconds,
        fixed_steady_scales=_scales(),
        storage_scales_BTU=np.maximum(np.abs(storage[1:]), 1.0),
        pressure_numerical=numerical,
        state_id="dd128_test",
        evaluation_kind="residual",
    )


def test_dd128_step_pattern_is_square_and_full_rank():
    contract = _contract(("n-Propane", "n-Butane", "n-Pentane"))
    pattern = controlled_terminal_step_pattern(contract)

    assert pattern.shape == (50, 50)
    assert structural_rank(csr_matrix(pattern)) == 50


def test_dd128_step_pattern_remains_generic_for_two_components():
    contract = _contract(("water", "methanol"))
    pattern = controlled_terminal_step_pattern(contract)

    assert pattern.shape == (40, 40)
    assert structural_rank(csr_matrix(pattern)) == 40


def test_dd128_stationary_controller_memory_and_products_are_bumpless():
    _, _, _, _, _, _, _, _, point, levels = _basis()
    result = _evaluate(point, np.zeros(2), levels)

    assert np.max(np.abs(result.scaled[-4:])) < 1.0e-12
    assert np.array_equal(result.endpoint_controller_memory, np.zeros(2))
    assert np.array_equal(result.product_log_ratio, np.zeros(2))


def test_dd128_controller_memory_uses_seconds_not_hours():
    _, _, _, _, _, _, _, _, point, levels = _basis()
    point = point.copy()
    point[19:21] = (0.01, -0.02)
    result = _evaluate(point, (0.3, -0.4), levels, step_seconds=0.5)

    assert np.allclose(result.endpoint_controller_memory, (0.305, -0.41))


def test_dd128_component_and_energy_kinematics_are_exact():
    _, _, _, _, _, inventory, storage, _, point, levels = _basis()
    point = point.copy()
    point[:3] = (0.01, -0.02, 0.03)
    point[15:19] = (0.1, -0.2, 0.3, -0.4)
    result = _evaluate(point, np.zeros(2), levels, step_seconds=0.5)
    step_hours = 0.5 / 3600.0

    assert np.allclose(
        result.base.endpoint_inventory_lbmol - inventory,
        step_hours * result.base.component_rate_lbmolph,
    )
    assert np.allclose(
        result.base.endpoint_lower_internal_energy_BTU - storage[1:],
        step_hours * result.base.internal_energy_rate_BTUph[1:],
    )
