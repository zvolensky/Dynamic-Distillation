import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v3.dynamic_dae_numerical_audit_v1 import (
    dynamic_algebraic_coordinates,
    inventory_from_state,
)
from dynamic_distillation.core_v3.implicit_step_v1 import (
    ImplicitStepSettings,
    governing_storage_vector,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.terminal_inventory_control_implicit_step_v1 import (
    evaluate_terminal_inventory_control_backward_euler_residual,
    solve_terminal_inventory_control_backward_euler_step,
    terminal_inventory_control_step_pattern,
)
from dynamic_distillation.core_v3.terminal_inventory_control_numerical_v1 import (
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
)
from test_core_v3_dynamic_dae_numerical_audit_v1 import _fixture, _scales, _state
from test_core_v3_terminal_inventory_control_numerical_v1 import _contract


def _basis():
    provider, spec, reference = _fixture()
    state = _state(reference)
    contract = _contract(spec.component_names)
    inventory = inventory_from_state(state)
    point = np.concatenate(
        (
            np.zeros(len(contract.base.derivative_variables)),
            np.zeros(2),
            dynamic_algebraic_coordinates(spec, reference, state),
            np.zeros(2),
        )
    )
    seed = evaluate_terminal_inventory_control_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory,
        controller_memory=np.zeros(2),
        level_setpoints=TerminalLevelSetpoints(0.5, 0.5),
        solve_coordinates=point,
        storage_gradient_BTU_lbmol=np.zeros_like(inventory),
        fixed_steady_scales=_scales(),
        state_id="dd186_test_seed",
        evaluation_kind="residual",
    )
    setpoints = TerminalLevelSetpoints(*seed.level_fraction)
    baseline = evaluate_terminal_inventory_control_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        inventory_lbmol=inventory,
        controller_memory=np.zeros(2),
        level_setpoints=setpoints,
        solve_coordinates=point,
        storage_gradient_BTU_lbmol=np.zeros_like(inventory),
        fixed_steady_scales=_scales(),
        state_id="dd186_test_baseline",
        evaluation_kind="residual",
    )
    scales = np.asarray(
        [
            baseline.base.scales[index]
            for index, row in enumerate(contract.base.rows)
            if row.block == "component_balance"
        ]
    ).reshape(inventory.shape)
    storage = governing_storage_vector(spec, baseline.base, inventory)
    return (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        point,
        setpoints,
        scales,
        storage,
    )


def test_dd186_step_pattern_is_square_and_full_rank():
    _, spec, _, _, contract, *_ = _basis()
    pattern = terminal_inventory_control_step_pattern(contract)

    assert pattern.shape == (42, 42)
    assert structural_rank(csr_matrix(pattern)) == 42
    assert len(spec.topology.volume_ids) == 5


def test_dd186_stationary_evaluation_is_bumpless():
    (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        point,
        setpoints,
        scales,
        storage,
    ) = _basis()
    result = evaluate_terminal_inventory_control_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        previous_controller_memory=np.zeros(2),
        level_setpoints=setpoints,
        rate_scales_lbmolph=scales,
        solve_coordinates=point,
        step_seconds=1.0,
        fixed_steady_scales=_scales(),
        state_id="dd186_test_stationary",
        evaluation_kind="residual",
    )

    assert np.array_equal(result.endpoint_inventory_lbmol, inventory)
    assert np.array_equal(result.endpoint_controller_memory, np.zeros(2))
    assert np.array_equal(result.product_log_ratio, np.zeros(2))
    assert np.max(np.abs(result.scaled[-4:])) == 0.0


def test_dd186_controller_memory_advances_in_seconds():
    (
        provider,
        spec,
        reference,
        state,
        contract,
        inventory,
        point,
        setpoints,
        scales,
        storage,
    ) = _basis()
    point = point.copy()
    point[15:17] = (0.01, -0.02)
    result = evaluate_terminal_inventory_control_backward_euler_residual(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_internal_energy_BTU=storage,
        previous_controller_memory=(0.3, -0.4),
        level_setpoints=setpoints,
        rate_scales_lbmolph=scales,
        solve_coordinates=point,
        step_seconds=0.5,
        fixed_steady_scales=_scales(),
        state_id="dd186_test_memory",
        evaluation_kind="residual",
    )

    assert np.allclose(result.endpoint_controller_memory, (0.305, -0.41))


def test_dd186_stationary_solver_retains_complete_jacobian():
    provider, spec, reference, state, contract, inventory, point, setpoints, *_ = (
        _basis()
    )
    outcome = solve_terminal_inventory_control_backward_euler_step(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        previous_inventory_lbmol=inventory,
        previous_controller_memory=np.zeros(2),
        level_setpoints=setpoints,
        initial_solve_coordinates=point,
        fixed_steady_scales=_scales(),
        step_seconds=1.0,
        settings=ImplicitStepSettings(max_nfev=3, jacobian_mode="colored"),
        name="dd186_test_solver",
    )

    assert outcome.nfev > 0
    assert outcome.final_jacobian.shape == (42, 42)
    assert np.all(np.isfinite(outcome.final_jacobian))
