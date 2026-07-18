from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    audit_points,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
)
from dynamic_distillation.core_v2.energy_owned_vapor_steady_solve_v1 import (
    SteadySolveSettings,
    central_difference_jacobian,
    independent_smooth_start,
    pairwise_root_agreement,
    physical_bounds,
    prepare_campaign,
)
from test_core_v2_energy_owned_vapor_numerical_gate_v1 import _fixture


def test_dd085_bounds_are_finite_and_contain_all_frozen_starts():
    provider, spec, reference = _fixture()
    settings = SteadySolveSettings()
    definition = prepare_campaign(spec, reference, provider, settings)

    assert definition.lower_bounds.shape == (37,)
    assert definition.upper_bounds.shape == (37,)
    assert np.all(np.isfinite(definition.lower_bounds))
    assert np.all(np.isfinite(definition.upper_bounds))
    assert tuple(definition.starts) == (
        "canonical_role_mapped_seed",
        "deterministic_combined_perturbation",
        "independent_smooth_physical_seed",
    )
    for point in definition.starts.values():
        assert np.all(point > definition.lower_bounds)
        assert np.all(point < definition.upper_bounds)


def test_dd085_physical_bounds_decode_to_declared_limits():
    _provider, spec, reference = _fixture()
    settings = SteadySolveSettings()
    lower, upper = physical_bounds(spec, reference, settings)
    layout = coordinate_layout(spec)

    assert np.allclose(
        lower[layout.temperature],
        (settings.temperature_min_F - reference.temperature_F) / 100.0,
    )
    assert np.allclose(
        upper[layout.temperature],
        (settings.temperature_max_F - reference.temperature_F) / 100.0,
    )
    assert np.allclose(
        lower[layout.liquid_flows],
        np.log(settings.internal_flow_min_ratio),
    )
    assert np.allclose(
        upper[layout.liquid_flows],
        np.log(settings.internal_flow_max_ratio),
    )
    assert np.allclose(
        lower[layout.vapor_flows],
        np.log(settings.internal_flow_min_ratio),
    )
    assert np.allclose(
        upper[layout.vapor_flows],
        np.log(settings.internal_flow_max_ratio),
    )


def test_dd085_smooth_start_is_independent_physical_and_monotonic():
    provider, spec, reference = _fixture()
    point = independent_smooth_start(spec, reference, provider)
    state = decode_coordinates(spec, reference, point)

    assert np.all(np.diff(state.temperature_F) > 0.0)
    assert np.all(state.liquid_mole_fraction > 0.0)
    assert np.all(state.vapor_mole_fraction > 0.0)
    assert np.allclose(np.sum(state.liquid_mole_fraction, axis=1), 1.0)
    assert np.allclose(np.sum(state.vapor_mole_fraction, axis=1), 1.0)
    assert np.allclose(
        state.liquid_moles_lbmol[[0, -1]],
        spec.terminal_liquid_targets_lbmol,
    )
    assert np.allclose(
        state.distillate_lbmolph + state.bottoms_lbmolph,
        np.sum(spec.feed_component_lbmolph),
    )


def test_dd085_jacobian_is_dd084_uncolored_central_difference():
    provider, spec, reference = _fixture()
    point = audit_points(spec)["deterministic_combined_perturbation"]
    baseline = evaluate_residual(spec, reference, provider, point)
    matrix = central_difference_jacobian(
        spec,
        reference,
        provider,
        point,
        fixed_scales=baseline.scales,
        step=1.0e-5,
    )

    assert matrix.shape == (37, 37)
    assert np.linalg.matrix_rank(matrix) == 37


def test_dd085_pairwise_root_agreement_uses_physical_variables():
    provider, spec, reference = _fixture()
    definition = prepare_campaign(
        spec,
        reference,
        provider,
        SteadySolveSettings(),
    )
    point = audit_points(spec)["canonical_role_mapped_seed"]
    comparisons = pairwise_root_agreement(
        spec,
        reference,
        {"a": point, "b": point.copy()},
        definition.physical_comparison_scales,
    )

    assert comparisons == {"a__vs__b": 0.0}
