from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.core_v2.five_volume_residual_gate_v1 import (
    DIRECT_VOLUME_IDS,
    EQUILIBRIUM_VOLUME_IDS,
    FiveVolumeReference,
    audit_five_volume_jacobian,
    build_operating_spec,
    decode_direct_coordinates,
    direct_coordinate_layout,
    direct_system_size,
    encode_direct_state,
    evaluate_five_volume_residual,
    perturbation_coordinates,
    reference_coordinates,
    structural_pattern,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    BTU_PER_PSI_FT3,
    FRANCIS_C_US,
    SECONDS_PER_HOUR,
    OneVolumeGeometry,
    normalize_composition,
)
from dynamic_distillation.core_v2.five_volume_steady_solve_v1 import (
    FixedSteadySolveSettings,
    build_coordinate_bounds,
    build_independent_smooth_profile_start,
    normalized_physical_difference,
)


class _AnalyticProvider:
    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        _ = P_psia
        x = normalize_composition(comp)
        phase_offset = 5000.0 if str(phase).lower() == "vapor" else 0.0
        return (
            1000.0
            + 20.0 * (float(T_F) - 100.0)
            + 100.0 * x[0]
            + phase_offset
        )

    def liquid_density_lbmol_ft3(self, T_F, P_psia, comp):
        _ = T_F, P_psia, comp
        return 0.5

    def phase_fugacity_coefficients(self, phase, T_F, P_psia, comp):
        _ = T_F, P_psia, comp
        if str(phase).lower() == "liquid":
            return np.asarray([2.0, 1.0, 0.5], dtype=float)
        return np.ones(3, dtype=float)

    def component_mw_lbm_per_lbmol(self):
        return np.asarray([40.0, 50.0, 60.0], dtype=float)


def _fixture():
    provider = _AnalyticProvider()
    components = ("A", "B", "C")
    geometry = tuple(
        OneVolumeGeometry(
            active_area_ft2=100.0,
            tray_spacing_ft=2.0,
            weir_height_in=2.0,
            weir_length_ft=5.0,
            hydraulic_c_factor=1.0,
        )
        for _ in range(3)
    )
    pressure = np.asarray([200.0, 202.0, 204.0, 206.0, 208.0])
    feed_component = np.asarray([700.0, 1000.0, 300.0])
    feed_x = feed_component / np.sum(feed_component)
    feed_h = provider.phase_enthalpy_BTU_lbmol(
        "liquid", 150.0, pressure[2], feed_x
    )
    spec = build_operating_spec(
        component_names=components,
        pressure_psia=pressure,
        reflux_lbmolph=5000.0,
        rectifying_vapor_lbmolph=7000.0,
        stripping_vapor_lbmolph=6500.0,
        feed_component_lbmolph=feed_component,
        feed_enthalpy_BTUph=float(np.sum(feed_component)) * feed_h,
        condenser_duty_BTUph=-4.0e7,
        reboiler_duty_BTUph=4.5e7,
        terminal_liquid_targets_lbmol=(50.0, 50.0),
        hydraulic_geometry=geometry,
    )
    x = np.asarray(
        [
            [0.70, 0.25, 0.05],
            [0.60, 0.32, 0.08],
            [0.40, 0.45, 0.15],
            [0.25, 0.55, 0.20],
            [0.10, 0.60, 0.30],
        ],
        dtype=float,
    )
    liquid_moles = np.full(5, 50.0)
    inventory = liquid_moles[:, None] * x
    temperature = np.asarray([140.0, 145.0, 150.0, 155.0, 160.0])
    internal_energy = np.empty(5)
    for index in range(5):
        h_liquid = provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            temperature[index],
            pressure[index],
            x[index],
        )
        u_liquid = h_liquid - pressure[index] * 2.0 * BTU_PER_PSI_FT3
        internal_energy[index] = liquid_moles[index] * u_liquid
    liquid_phi = np.asarray([2.0, 1.0, 0.5])
    vapor = np.asarray(
        [normalize_composition(x[index] * liquid_phi) for index in range(1, 5)]
    )
    head = 50.0 / 0.5 / 100.0 - 2.0 / 12.0
    francis = (
        FRANCIS_C_US * 5.0 * head**1.5 * 0.5 * SECONDS_PER_HOUR
    )
    reference = FiveVolumeReference(
        component_inventory_lbmol=inventory,
        internal_energy_BTU=internal_energy,
        temperature_F=temperature,
        vapor_mole_fraction=vapor,
        hydraulic_liquid_flow_lbmolph=np.full(3, francis),
        distillate_lbmolph=1500.0,
        bottoms_lbmolph=500.0,
    )
    return provider, spec, reference


def test_direct_gate_c_registry_eliminates_reconstruction_coordinates():
    _provider, spec, _reference = _fixture()
    layout = direct_coordinate_layout(spec)

    assert direct_system_size(3) == 38
    assert len(layout.names) == 38
    assert not any(name.startswith("NL[") for name in layout.names)
    assert not any(name.startswith("x[") for name in layout.names)
    assert sum(name.startswith("y_logit[") for name in layout.names) == 8


def test_reference_reconstructs_liquid_state_without_projection():
    _provider, spec, reference = _fixture()
    state = decode_direct_coordinates(
        spec,
        reference,
        reference_coordinates(spec),
    )

    assert np.allclose(state.component_inventory_lbmol, reference.component_inventory_lbmol)
    assert np.allclose(state.liquid_moles_lbmol, 50.0)
    assert np.allclose(np.sum(state.liquid_mole_fraction, axis=1), 1.0)
    assert np.all(state.liquid_mole_fraction > 0.0)
    assert np.allclose(
        state.vapor_mole_fraction,
        reference.vapor_mole_fraction,
    )


def test_physical_state_coordinate_round_trip():
    _provider, spec, reference = _fixture()
    point = perturbation_coordinates(spec)["combined_bounded_perturbation"]
    state = decode_direct_coordinates(spec, reference, point)

    encoded = encode_direct_state(spec, reference, state)
    decoded = decode_direct_coordinates(spec, reference, encoded)

    assert np.allclose(encoded, point, rtol=0.0, atol=2.0e-15)
    assert np.allclose(
        decoded.component_inventory_lbmol,
        state.component_inventory_lbmol,
    )
    assert np.allclose(decoded.internal_energy_BTU, state.internal_energy_BTU)
    assert np.allclose(decoded.temperature_F, state.temperature_F)
    assert np.allclose(decoded.vapor_mole_fraction, state.vapor_mole_fraction)


def test_live_residual_has_exact_local_closure_and_telescoping():
    provider, spec, reference = _fixture()
    evaluation = evaluate_five_volume_residual(
        spec,
        reference,
        provider,
        reference_coordinates(spec),
    )
    blocks = {}
    for row, value in zip(evaluation.rows, evaluation.raw):
        blocks.setdefault(row.block, []).append(float(value))

    assert evaluation.raw.shape == (38,)
    assert np.max(np.abs(blocks["energy_reconstruction"])) < 1.0e-10
    assert np.max(np.abs(blocks["phase_equilibrium"])) < 1.0e-12
    assert np.max(np.abs(blocks["francis_hydraulics"])) < 1.0e-10
    assert np.max(np.abs(blocks["terminal_level_specification"])) < 1.0e-12
    assert evaluation.component_telescoping_relative_error < 1.0e-14
    assert evaluation.energy_telescoping_relative_error < 1.0e-14
    assert not evaluation.clipping_or_projection_used
    assert not evaluation.property_fallback_used


def test_product_draws_use_live_terminal_compositions():
    provider, spec, reference = _fixture()
    evaluation = evaluate_five_volume_residual(
        spec,
        reference,
        provider,
        reference_coordinates(spec),
    )
    state = evaluation.state
    expected_external = (
        spec.feed_component_lbmolph
        - state.distillate_lbmolph * state.liquid_mole_fraction[0]
        - state.bottoms_lbmolph * state.liquid_mole_fraction[-1]
    )
    component_rows = np.asarray(
        [
            value
            for row, value in zip(evaluation.rows, evaluation.raw)
            if row.block == "component_balance"
        ]
    ).reshape((len(DIRECT_VOLUME_IDS), len(spec.component_names)))

    assert np.allclose(np.sum(component_rows, axis=0), expected_external)


def test_structural_pattern_is_square_and_has_no_empty_rows_or_columns():
    _provider, spec, _reference = _fixture()
    pattern = structural_pattern(spec)

    assert pattern.shape == (38, 38)
    assert np.all(np.any(pattern, axis=1))
    assert np.all(np.any(pattern, axis=0))


def test_fixed_dd082_bounds_contain_predeclared_starts():
    provider, spec, reference = _fixture()
    settings = FixedSteadySolveSettings()
    bounds = build_coordinate_bounds(spec, reference, settings)
    smooth, metadata = build_independent_smooth_profile_start(
        spec,
        reference,
        provider,
        settings,
    )
    starts = (
        reference_coordinates(spec),
        perturbation_coordinates(spec)["combined_bounded_perturbation"],
        smooth,
    )

    assert all(np.all(point > bounds.lower) for point in starts)
    assert all(np.all(point < bounds.upper) for point in starts)
    assert metadata["used_mini8_internal_profile"] is False
    assert np.all(np.diff(metadata["temperature_F"]) > 0.0)
    assert np.all(np.asarray(metadata["hydraulic_liquid_flow_lbmolph"]) > 0.0)


def test_normalized_physical_difference_is_symmetric_and_scaled():
    first = np.asarray([1.0, 100.0, -5.0])
    second = np.asarray([1.1, 90.0, -4.0])
    scales = np.asarray([1.0, 100.0, 10.0])

    forward = normalized_physical_difference(first, second, scales)
    reverse = normalized_physical_difference(second, first, scales)

    assert forward == pytest.approx(reverse)
    assert forward == pytest.approx(0.1)


def test_colored_and_uncolored_jacobians_agree_for_analytic_provider():
    provider, spec, reference = _fixture()
    point = perturbation_coordinates(spec)["combined_bounded_perturbation"]
    baseline = evaluate_five_volume_residual(spec, reference, provider, point)
    audit = audit_five_volume_jacobian(
        spec,
        reference,
        provider,
        point,
        fixed_scales=baseline.scales,
        step=1.0e-5,
    )

    assert audit.matrix.shape == (38, 38)
    assert audit.zero_rows == ()
    assert audit.zero_columns == ()
    assert audit.unexpected_couplings == ()
    assert audit.colored_uncolored_relative < 1.0e-8
    assert audit.color_count < 38


@pytest.mark.parametrize(
    "name",
    (
        "canonical_mini8_derived",
        "bounded_inventory_perturbation",
        "bounded_energy_perturbation",
        "feed_role_composition_transfer",
        "combined_bounded_perturbation",
    ),
)
def test_predeclared_audit_states_remain_physical(name):
    provider, spec, reference = _fixture()
    point = perturbation_coordinates(spec)[name]
    evaluation = evaluate_five_volume_residual(spec, reference, provider, point)

    assert np.all(evaluation.state.component_inventory_lbmol > 0.0)
    assert np.all(evaluation.state.liquid_mole_fraction > 0.0)
    assert np.all(evaluation.state.vapor_mole_fraction > 0.0)
    assert np.all(evaluation.state.hydraulic_liquid_flow_lbmolph > 0.0)
    assert np.all(np.isfinite(evaluation.raw))
