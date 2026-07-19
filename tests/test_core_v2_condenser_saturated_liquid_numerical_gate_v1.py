from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from dynamic_distillation.core_v2.condenser_saturated_liquid_numerical_gate_v1 import (
    BubbleSeedSettings,
    CondenserNumericalReference,
    audit_numerical_jacobian,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
    solve_local_bubble_seed,
    structural_pattern,
)
from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedOperatingSpec,
    EnergyOwnedReference,
    audit_points,
    coordinate_layout as base_coordinate_layout,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    OneVolumeGeometry,
    normalize_composition,
)


class _AnalyticProvider:
    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        x = normalize_composition(comp)
        phase_offset = 6000.0 if str(phase).lower() == "vapor" else 0.0
        return (
            1000.0
            + 20.0 * (float(T_F) - 100.0)
            + 0.5 * float(P_psia)
            + 100.0 * x[0]
            + phase_offset
        )

    def liquid_density_lbmol_ft3(self, T_F, P_psia, comp):
        x = normalize_composition(comp)
        return 0.55 - 0.0002 * (float(T_F) - 150.0) + 0.01 * x[0]

    def phase_fugacity_coefficients(self, phase, T_F, P_psia, comp):
        x = normalize_composition(comp)
        pressure_term = 0.0001 * (float(P_psia) - 200.0)
        if str(phase).lower() == "liquid":
            base = np.asarray([1.4, 0.9, 0.6], dtype=float)
            return base * np.exp(
                0.01 * (float(T_F) - 150.0) + pressure_term + 0.02 * x
            )
        return np.exp(-0.003 * (float(T_F) - 150.0) + 0.01 * x)


def _fixture():
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
    spec = EnergyOwnedOperatingSpec(
        component_names=components,
        pressure_psia=np.asarray([200.0, 202.0, 204.0, 206.0, 208.0]),
        reflux_lbmolph=5000.0,
        feed_component_lbmolph=np.asarray([700.0, 1000.0, 300.0]),
        feed_enthalpy_BTUph=3.0e7,
        condenser_duty_BTUph=-4.0e7,
        reboiler_duty_BTUph=4.5e7,
        terminal_liquid_targets_lbmol=np.asarray([50.0, 50.0]),
        hydraulic_geometry=geometry,
    )
    liquid_x = np.asarray(
        (
            (0.70, 0.25, 0.05),
            (0.60, 0.32, 0.08),
            (0.40, 0.45, 0.15),
            (0.25, 0.55, 0.20),
            (0.10, 0.60, 0.30),
        )
    )
    vapor_y = np.asarray(
        (
            (0.72, 0.23, 0.05),
            (0.55, 0.35, 0.10),
            (0.35, 0.48, 0.17),
            (0.18, 0.57, 0.25),
        )
    )
    reference = EnergyOwnedReference(
        liquid_moles_lbmol=np.full(5, 50.0),
        liquid_mole_fraction=liquid_x,
        temperature_F=np.asarray([140.0, 145.0, 150.0, 155.0, 160.0]),
        vapor_mole_fraction=vapor_y,
        hydraulic_liquid_flow_lbmolph=np.asarray([9000.0, 10000.0, 9500.0]),
        vapor_flow_lbmolph=np.asarray([6500.0, 6400.0, 7000.0, 6900.0]),
        distillate_lbmolph=1500.0,
        bottoms_lbmolph=500.0,
    )
    return _AnalyticProvider(), spec, reference


def _condenser_reference(provider, spec, base):
    bubble = solve_local_bubble_seed(
        provider,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=base.liquid_mole_fraction[0],
        temperature_guess_F=float(base.temperature_F[0]),
        vapor_guess=base.liquid_mole_fraction[0],
        settings=BubbleSeedSettings(
            temperature_min_F=80.0,
            temperature_max_F=260.0,
        ),
    )
    assert bubble.success
    assert bubble.residual_inf_norm < 1.0e-10
    live_base = EnergyOwnedReference(
        liquid_moles_lbmol=base.liquid_moles_lbmol.copy(),
        liquid_mole_fraction=base.liquid_mole_fraction.copy(),
        temperature_F=np.asarray(
            [bubble.temperature_F, *base.temperature_F[1:]],
            dtype=float,
        ),
        vapor_mole_fraction=base.vapor_mole_fraction.copy(),
        hydraulic_liquid_flow_lbmolph=base.hydraulic_liquid_flow_lbmolph.copy(),
        vapor_flow_lbmolph=base.vapor_flow_lbmolph.copy(),
        distillate_lbmolph=base.distillate_lbmolph,
        bottoms_lbmolph=base.bottoms_lbmolph,
    )
    return CondenserNumericalReference(
        base=live_base,
        bubble_vapor_mole_fraction=bubble.vapor_mole_fraction,
        condenser_duty_reference_BTUph=-4.0e7,
        condenser_duty_scale_BTUph=4.5e7,
    )


def test_dd087_layout_retains_base_coordinates_and_adds_signed_duty():
    provider, spec, base = _fixture()
    reference = _condenser_reference(provider, spec, base)
    layout = coordinate_layout(spec)
    canonical = np.zeros(40)
    more_cooling = canonical.copy()
    more_cooling[layout.condenser_duty] = -0.1
    less_cooling = canonical.copy()
    less_cooling[layout.condenser_duty] = 0.1

    assert len(layout.names) == 40
    assert layout.names[:37] == base_coordinate_layout(spec).names
    assert layout.names[-3:] == (
        "y_bubble_logit[reflux_drum,A]",
        "y_bubble_logit[reflux_drum,B]",
        "q_Q_C",
    )
    assert decode_coordinates(spec, reference, more_cooling)[1].condenser_duty_BTUph < -4.0e7
    assert decode_coordinates(spec, reference, less_cooling)[1].condenser_duty_BTUph > -4.0e7


def test_dd087_local_bubble_seed_closes_three_independent_equations():
    provider, spec, base = _fixture()
    result = solve_local_bubble_seed(
        provider,
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=base.liquid_mole_fraction[0],
        temperature_guess_F=140.0,
        vapor_guess=(0.75, 0.20, 0.05),
    )

    assert result.success
    assert result.residual_inf_norm < 1.0e-10
    assert np.all(result.vapor_mole_fraction > 0.0)
    assert np.sum(result.vapor_mole_fraction) == pytest.approx(1.0)


def test_dd087_residual_is_40_and_conserves_with_solved_duty():
    provider, spec, base = _fixture()
    reference = _condenser_reference(provider, spec, base)
    point = np.zeros(40)
    scales = np.ones(40)
    scales[12:32] = 1.0e7
    evaluation = evaluate_residual(
        spec,
        reference,
        provider,
        point,
        fixed_scales=scales,
    )

    assert evaluation.raw.shape == (40,)
    assert evaluation.base.component_telescoping_relative_error < 1.0e-14
    assert evaluation.base.energy_telescoping_relative_error < 1.0e-14
    assert not evaluation.base.clipping_or_projection_used
    assert not evaluation.base.property_fallback_used


def test_dd087_pattern_assigns_condenser_duty_only_to_drum_energy():
    _provider, spec, _base = _fixture()
    layout = coordinate_layout(spec)
    pattern = structural_pattern(spec)
    q_rows = np.flatnonzero(pattern[:, layout.condenser_duty])

    assert pattern.shape == (40, 40)
    assert q_rows.tolist() == [15]


def test_dd087_analytic_jacobian_and_local_bubble_block_are_full_rank():
    provider, spec, base = _fixture()
    reference = _condenser_reference(provider, spec, base)
    point = np.concatenate(
        (
            audit_points(spec)["deterministic_combined_perturbation"],
            np.asarray([0.0015, -0.001, 0.001]),
        )
    )
    scales = np.ones(40)
    scales[12:32] = 1.0e7
    audit = audit_numerical_jacobian(
        spec,
        reference,
        provider,
        point,
        fixed_scales=scales,
        step=1.0e-5,
    )

    assert audit.matrix.shape == (40, 40)
    assert audit.rank == 40
    assert audit.bubble_rank == 3
    assert audit.zero_rows == ()
    assert audit.zero_columns == ()
    assert audit.unexpected_couplings == ()
    assert audit.bubble_zero_rows == ()
    assert audit.bubble_zero_columns == ()


def test_dd087_module_has_no_dynamic_integrator():
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "src"
        / "dynamic_distillation"
        / "core_v2"
        / "condenser_saturated_liquid_numerical_gate_v1.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not any(name.startswith("scipy.integrate") for name in imported)
