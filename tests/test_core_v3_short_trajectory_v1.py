from types import SimpleNamespace

import numpy as np

from dynamic_distillation.core_v3.implicit_step_v1 import (
    ImplicitSolveOutcome,
    ImplicitStepSettings,
    component_rate_scales,
    evaluate_backward_euler_residual,
    governing_storage_vector,
    zero_rate_evaluation,
)
from dynamic_distillation.core_v3.provider_call_audit_v1 import (
    ProviderCallAudit,
)
from dynamic_distillation.core_v3.short_trajectory_v1 import (
    run_short_trajectory,
    scale_feed_throughput,
)
from test_core_v3_implicit_step_v1 import _basis


def test_dd098_feed_scaling_preserves_composition_and_specific_enthalpy():
    _provider, spec, *_rest = _basis()
    factor = 1.001
    perturbed = scale_feed_throughput(spec, factor)

    assert np.allclose(
        perturbed.feed_component_lbmolph,
        factor * spec.feed_component_lbmolph,
    )
    assert np.isclose(
        perturbed.feed_enthalpy_BTUph,
        factor * spec.feed_enthalpy_BTUph,
    )
    assert np.allclose(
        perturbed.feed_component_lbmolph
        / np.sum(perturbed.feed_component_lbmolph),
        spec.feed_component_lbmolph / np.sum(spec.feed_component_lbmolph),
    )
    assert np.isclose(
        perturbed.feed_enthalpy_BTUph
        / np.sum(perturbed.feed_component_lbmolph),
        spec.feed_enthalpy_BTUph / np.sum(spec.feed_component_lbmolph),
    )


def test_dd098_trajectory_rejects_nonintegral_or_nonpositive_time_grid():
    provider, spec, reference, state, contract, *_rest = _basis()
    common = dict(
        contract=contract,
        spec=spec,
        reference=reference,
        initial_state=state,
        provider=provider,
        call_audit=ProviderCallAudit(),
        fixed_steady_scales=np.ones(40),
        settings=ImplicitStepSettings(),
        name="invalid_grid",
    )
    for step, duration in ((0.0, 1.0), (1.0, 0.0), (0.6, 1.0)):
        try:
            run_short_trajectory(
                **common, step_seconds=step, duration_seconds=duration
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid trajectory grid was accepted")


def test_dd098_trajectory_chains_successful_step_endpoints_without_retry():
    (
        provider,
        spec,
        reference,
        state,
        contract,
        _inventory,
        _algebraic,
        _baseline,
        _rate_scales,
        _storage,
    ) = _basis()
    seen_inventory = []

    def stationary_solver(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        *,
        previous_inventory_lbmol,
        initial_algebraic_coordinates,
        fixed_steady_scales,
        step_seconds,
        settings,
        name,
    ):
        del settings
        previous = np.asarray(previous_inventory_lbmol, dtype=float)
        algebraic = np.asarray(initial_algebraic_coordinates, dtype=float)
        seen_inventory.append(previous.copy())
        baseline = zero_rate_evaluation(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            inventory_lbmol=previous,
            algebraic_coordinates=algebraic,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{name}:basis",
            evaluation_kind="residual",
        )
        rate_scales = component_rate_scales(contract, baseline)
        storage = governing_storage_vector(spec, baseline, previous)
        point = np.concatenate((np.zeros(15), algebraic))
        evaluation = evaluate_backward_euler_residual(
            contract,
            spec,
            reference,
            template,
            provider,
            call_audit,
            previous_inventory_lbmol=previous,
            previous_internal_energy_BTU=storage,
            rate_scales_lbmolph=rate_scales,
            solve_coordinates=point,
            step_seconds=step_seconds,
            fixed_steady_scales=fixed_steady_scales,
            state_id=f"{name}:endpoint",
            evaluation_kind="residual",
        )
        return ImplicitSolveOutcome(
            name=name,
            success=True,
            status=1,
            message="synthetic pass",
            nfev=1,
            njev=1,
            cost=0.0,
            optimality=0.0,
            wall_clock_sec=0.0,
            initial_coordinates=point,
            final_coordinates=point,
            final_residual=evaluation.scaled,
            jacobian=np.eye(38),
            evaluation=evaluation,
        )

    result = run_short_trajectory(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        fixed_steady_scales=np.ones(40),
        step_seconds=1.0,
        duration_seconds=2.0,
        settings=ImplicitStepSettings(),
        name="stationary",
        step_solver=stationary_solver,
    )

    assert result.completed
    assert result.requested_steps == result.completed_steps == 2
    assert len(seen_inventory) == 2
    assert np.array_equal(seen_inventory[0], seen_inventory[1])
    assert np.array_equal(
        result.endpoint_evaluation.endpoint_inventory_lbmol,
        result.initial_inventory_lbmol,
    )


def test_dd098_trajectory_stops_after_first_failed_step():
    provider, spec, reference, state, contract, *_rest = _basis()
    calls = []

    def failed_solver(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(success=False)

    result = run_short_trajectory(
        contract,
        spec,
        reference,
        state,
        provider,
        ProviderCallAudit(),
        fixed_steady_scales=np.ones(40),
        step_seconds=0.5,
        duration_seconds=2.0,
        settings=ImplicitStepSettings(),
        name="fail_fast",
        step_solver=failed_solver,
    )

    assert not result.completed
    assert result.completed_steps == 1
    assert len(calls) == 1
