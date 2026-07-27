import numpy as np
import pytest

from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.terminal_gauge_invariance_v1 import (
    assess_terminal_gauge_invariance,
    scale_terminal_gauge_coordinates,
)
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import (
    evaluate_zero_rate_readiness,
)
from test_core_v3_zero_rate_readiness_v1 import _zero_fixture


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
        state_id="dd121_test",
        evaluation_kind="residual",
        **common,
    )


def test_dd121_terminal_coordinate_scaling_is_homogeneous():
    numerical = _zero_fixture()[5]
    point = _zero_fixture()[6]
    top = scale_terminal_gauge_coordinates(
        numerical, point, terminal="reflux_drum", factor=1.01
    )
    bottom = scale_terminal_gauge_coordinates(
        numerical, point, terminal="combined_reboiler_sump", factor=0.99
    )

    assert np.allclose(top[:3] - point[:3], np.log(1.01))
    assert np.allclose(top[3:], point[3:])
    assert np.allclose(bottom[12:15] - point[12:15], np.log(0.99))
    assert not np.isclose(bottom[18], point[18])
    assert np.allclose(bottom[19:], point[19:])


def test_dd121_fixture_dae_is_invariant_to_terminal_scale():
    numerical = _zero_fixture()[5]
    point = _zero_fixture()[6]
    baseline = _evaluate(point)
    perturbed = {}
    composition = {}
    specific_energy = {}
    baseline_composition = baseline.full_evaluation.inventory_lbmol / np.sum(
        baseline.full_evaluation.inventory_lbmol, axis=1, keepdims=True
    )
    baseline_specific = baseline.full_evaluation.lower_internal_energy_BTU[-1] / np.sum(
        baseline.full_evaluation.inventory_lbmol[-1]
    )
    for terminal, factor in (
        ("reflux_drum", 1.01),
        ("reflux_drum", 0.99),
        ("combined_reboiler_sump", 1.01),
        ("combined_reboiler_sump", 0.99),
    ):
        name = f"{terminal}_{factor:g}"
        result = _evaluate(
            scale_terminal_gauge_coordinates(
                numerical, point, terminal=terminal, factor=factor
            )
        )
        trial_composition = result.full_evaluation.inventory_lbmol / np.sum(
            result.full_evaluation.inventory_lbmol, axis=1, keepdims=True
        )
        perturbed[name] = result.dae_scaled
        composition[name] = np.max(np.abs(trial_composition - baseline_composition))
        specific_energy[name] = abs(
            result.full_evaluation.lower_internal_energy_BTU[-1]
            / np.sum(result.full_evaluation.inventory_lbmol[-1])
            - baseline_specific
        )
    assessment = assess_terminal_gauge_invariance(
        baseline.dae_scaled,
        _evaluate(point).dae_scaled,
        perturbed,
        composition,
        specific_energy,
    )

    assert assessment.pass_gate
    assert max(assessment.perturbation_difference_inf_norms.values()) < 1.0e-12


def test_dd121_rejects_invalid_terminal_or_scale():
    numerical = _zero_fixture()[5]
    point = _zero_fixture()[6]
    with pytest.raises(ValueError, match="inputs are invalid"):
        scale_terminal_gauge_coordinates(
            numerical, point, terminal="feed_tray", factor=1.01
        )
    with pytest.raises(ValueError, match="inputs are invalid"):
        scale_terminal_gauge_coordinates(
            numerical, point, terminal="reflux_drum", factor=0.0
        )
