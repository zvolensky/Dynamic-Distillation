from __future__ import annotations

import numpy as np

from dynamic_distillation.core_v2.condenser_saturated_liquid_numerical_gate_v1 import (
    CondenserNumericalReference,
    coordinate_layout,
    decode_coordinates,
)
from dynamic_distillation.core_v2.condenser_saturated_liquid_steady_solve_v1 import (
    CondenserSteadySolveSettings,
    central_difference_jacobian,
    independent_smooth_phase_stable_start,
    pairwise_root_agreement,
    physical_bounds,
    physical_vector_and_scales,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
)
from test_core_v2_condenser_saturated_liquid_numerical_gate_v1 import (
    _condenser_reference,
    _fixture,
)


class _FlashResult:
    def __init__(self, K):
        self.K = np.asarray(K, dtype=float)


def _with_flash(provider):
    def flash_TP_full(T_F, P_psia, z):
        x = normalize_composition(z)
        phi_l = provider.phase_fugacity_coefficients(
            "liquid",
            T_F,
            P_psia,
            x,
        )
        phi_v = provider.phase_fugacity_coefficients(
            "vapor",
            T_F,
            P_psia,
            x,
        )
        return _FlashResult(np.asarray(phi_l) / np.asarray(phi_v))

    provider.flash_TP_full = flash_TP_full
    return provider


def _root_fixture():
    provider, spec, base = _fixture()
    provider = _with_flash(provider)
    reference = _condenser_reference(provider, spec, base)
    return provider, spec, reference


def test_dd088_bounds_include_signed_duty_and_all_composition_families():
    _provider, spec, reference = _root_fixture()
    settings = CondenserSteadySolveSettings()
    lower, upper = physical_bounds(spec, reference, settings)
    layout = coordinate_layout(spec)

    assert lower.shape == (40,)
    assert upper.shape == (40,)
    assert np.all(np.isfinite(lower))
    assert np.all(np.isfinite(upper))
    duty_at_lower = (
        reference.condenser_duty_reference_BTUph
        + reference.condenser_duty_scale_BTUph
        * lower[layout.condenser_duty]
    )
    duty_at_upper = (
        reference.condenser_duty_reference_BTUph
        + reference.condenser_duty_scale_BTUph
        * upper[layout.condenser_duty]
    )
    assert duty_at_lower == -3.0 * abs(
        reference.condenser_duty_reference_BTUph
    )
    assert duty_at_upper == -0.1 * abs(
        reference.condenser_duty_reference_BTUph
    )
    assert layout.bubble_logits.stop - layout.bubble_logits.start == 2


def test_dd088_independent_seed_has_independent_drum_and_own_bubble_state():
    provider, spec, reference = _root_fixture()
    point, metadata = independent_smooth_phase_stable_start(
        spec,
        reference,
        provider,
    )
    state, condenser = decode_coordinates(spec, reference, point)

    assert point.shape == (40,)
    assert not np.allclose(
        state.liquid_mole_fraction[0],
        reference.base.liquid_mole_fraction[0],
    )
    assert np.all(np.diff(state.temperature_F) > 0.0)
    assert np.all(state.liquid_mole_fraction > 0.0)
    assert np.all(state.vapor_mole_fraction > 0.0)
    assert np.all(condenser.bubble_vapor_mole_fraction > 0.0)
    assert condenser.condenser_duty_BTUph < 0.0
    assert metadata["bubble_residual_inf_norm"] < 1.0e-10
    assert not metadata["partial_column_solve_used"]
    assert not metadata["balance_back_calculation_used"]
    assert not metadata["dd085_root_used"]


def test_dd088_frozen_jacobian_is_uncolored_central_difference():
    provider, spec, reference = _root_fixture()
    point = np.zeros(40)
    scales = np.ones(40)
    scales[12:32] = 1.0e7
    matrix = central_difference_jacobian(
        spec,
        reference,
        provider,
        point,
        fixed_scales=scales,
        step=1.0e-5,
    )

    assert matrix.shape == (40, 40)
    assert np.linalg.matrix_rank(matrix) == 40


def test_dd088_pairwise_agreement_includes_bubble_and_duty():
    _provider, spec, reference = _root_fixture()
    canonical = np.zeros(40)
    physical_scales = physical_vector_and_scales(
        spec,
        reference,
        canonical,
    )[1]
    bubble_changed = canonical.copy()
    bubble_changed[37] = 0.01
    duty_changed = canonical.copy()
    duty_changed[39] = 0.01

    comparisons = pairwise_root_agreement(
        spec,
        reference,
        {
            "canonical": canonical,
            "bubble": bubble_changed,
            "duty": duty_changed,
        },
        physical_scales,
    )

    assert comparisons["canonical__vs__bubble"] > 0.0
    assert comparisons["canonical__vs__duty"] > 0.0


def test_dd088_reference_type_remains_dd087_boundary():
    _provider, _spec, reference = _root_fixture()
    assert isinstance(reference, CondenserNumericalReference)
