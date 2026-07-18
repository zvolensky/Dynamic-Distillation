from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedOperatingSpec,
    EnergyOwnedReference,
    audit_numerical_jacobian,
    audit_points,
    coordinate_layout,
    decode_coordinates,
    evaluate_residual,
    structural_pattern,
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
        ),
        dtype=float,
    )
    vapor_y = np.asarray(
        (
            (0.72, 0.23, 0.05),
            (0.55, 0.35, 0.10),
            (0.35, 0.48, 0.17),
            (0.18, 0.57, 0.25),
        ),
        dtype=float,
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


def test_dd084_coordinate_and_residual_counts_are_37():
    _provider, spec, reference = _fixture()
    layout = coordinate_layout(spec)
    evaluation = evaluate_residual(
        spec,
        reference,
        _provider,
        audit_points(spec)["canonical_role_mapped_seed"],
    )

    assert len(layout.names) == 37
    assert evaluation.raw.shape == (37,)
    assert sum(name.startswith("log_V[") for name in layout.names) == 4
    assert sum(row.block == "full_phase_equilibrium" for row in evaluation.rows) == 12


def test_dd084_transformed_states_are_physical_and_normalized():
    _provider, spec, reference = _fixture()
    for point in audit_points(spec).values():
        state = decode_coordinates(spec, reference, point)

        assert np.all(state.liquid_moles_lbmol > 0)
        assert np.all(state.liquid_mole_fraction > 0)
        assert np.all(state.vapor_mole_fraction > 0)
        assert np.allclose(np.sum(state.liquid_mole_fraction, axis=1), 1.0)
        assert np.allclose(np.sum(state.vapor_mole_fraction, axis=1), 1.0)
        assert np.all(state.hydraulic_liquid_flow_lbmolph > 0)
        assert np.all(state.vapor_flow_lbmolph > 0)


def test_dd084_residual_telescopes_and_uses_no_safeguard():
    provider, spec, reference = _fixture()
    evaluation = evaluate_residual(
        spec,
        reference,
        provider,
        audit_points(spec)["deterministic_combined_perturbation"],
    )

    assert np.all(np.isfinite(evaluation.raw))
    assert evaluation.component_telescoping_relative_error < 1.0e-14
    assert evaluation.energy_telescoping_relative_error < 1.0e-14
    assert not evaluation.clipping_or_projection_used
    assert not evaluation.property_fallback_used


def test_dd084_structural_pattern_is_square_and_full():
    _provider, spec, _reference = _fixture()
    pattern = structural_pattern(spec)

    assert pattern.shape == (37, 37)
    assert np.all(np.any(pattern, axis=0))
    assert np.all(np.any(pattern, axis=1))


def test_dd084_analytic_jacobian_has_registered_couplings():
    provider, spec, reference = _fixture()
    point = audit_points(spec)["deterministic_combined_perturbation"]
    baseline = evaluate_residual(spec, reference, provider, point)
    audit = audit_numerical_jacobian(
        spec,
        reference,
        provider,
        point,
        fixed_scales=baseline.scales,
        step=1.0e-5,
    )

    assert audit.matrix.shape == (37, 37)
    assert audit.rank == 37
    assert audit.zero_rows == ()
    assert audit.zero_columns == ()
    assert audit.unexpected_couplings == ()


def test_dd084_module_contains_no_solver_or_integrator_import():
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "src"
        / "dynamic_distillation"
        / "core_v2"
        / "energy_owned_vapor_numerical_gate_v1.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any(name.startswith("scipy.optimize") for name in imported)
    assert not any(name.startswith("scipy.integrate") for name in imported)
