from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    BTU_PER_PSI_FT3,
    OneVolumeBoundary,
    OneVolumeConservedState,
    OneVolumeGeometry,
    OneVolumeIntegrationOptions,
    OneVolumeSpec,
    audit_one_volume_jacobian,
    integrate_one_volume,
    normalize_composition,
    reconstruct_liquid_inventory,
    solve_one_volume_closure,
)


class _AnalyticProvider:
    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        _ = phase, P_psia
        x = normalize_composition(comp)
        return 1000.0 + 20.0 * (float(T_F) - 100.0) + 100.0 * x[0]

    def liquid_density_lbmol_ft3(self, T_F, P_psia, comp):
        _ = T_F, P_psia, comp
        return 0.5

    def phase_fugacity_coefficients(self, phase, T_F, P_psia, comp):
        _ = T_F, P_psia, comp
        if str(phase).lower() == "liquid":
            return np.asarray([2.0, 1.0, 0.5], dtype=float)
        return np.ones(3, dtype=float)


def _fixture():
    provider = _AnalyticProvider()
    x = np.asarray([0.3, 0.6, 0.1], dtype=float)
    y = normalize_composition(x * np.asarray([2.0, 1.0, 0.5]))
    liquid_moles = 50.0
    pressure = 200.0
    temperature = 150.0
    enthalpy = provider.phase_enthalpy_BTU_lbmol(
        "liquid",
        temperature,
        pressure,
        x,
    )
    internal_energy = enthalpy - pressure * 2.0 * BTU_PER_PSI_FT3
    state = OneVolumeConservedState(
        component_inventory_lbmol=liquid_moles * x,
        internal_energy_BTU=liquid_moles * internal_energy,
    )
    spec = OneVolumeSpec(
        component_names=("A", "B", "C"),
        pressure_psia=pressure,
        temperature_reference_F=temperature,
        temperature_scale_F=100.0,
        energy_scale_BTU=max(abs(state.internal_energy_BTU), 1.0),
        geometry=OneVolumeGeometry(
            active_area_ft2=100.0,
            tray_spacing_ft=2.0,
            weir_height_in=2.0,
            weir_length_ft=5.0,
        ),
        component_mw_lbm_per_lbmol=np.asarray([40.0, 50.0, 60.0]),
    )
    return provider, spec, state, x, y, temperature


def test_direct_inventory_reconstruction():
    liquid_moles, x = reconstruct_liquid_inventory([15.0, 30.0, 5.0])

    assert liquid_moles == pytest.approx(50.0)
    assert np.allclose(x, [0.3, 0.6, 0.1])


def test_canonical_state_round_trips_from_different_guesses():
    provider, spec, state, x, y, temperature = _fixture()
    roots = [
        solve_one_volume_closure(
            spec,
            state,
            provider,
            initial_temperature_F=guess_temperature,
            initial_vapor_mole_fraction=guess_y,
        )
        for guess_temperature, guess_y in (
            (temperature, y),
            (temperature + 20.0, [0.7, 0.2, 0.1]),
            (temperature - 20.0, [0.2, 0.5, 0.3]),
        )
    ]

    assert all(root.converged for root in roots)
    assert all(not root.clipping_or_projection_used for root in roots)
    assert max(abs(root.temperature_F - temperature) for root in roots) < 1.0e-8
    assert (
        max(np.max(np.abs(root.liquid_mole_fraction - x)) for root in roots) < 1.0e-14
    )
    assert max(np.max(np.abs(root.vapor_mole_fraction - y)) for root in roots) < 1.0e-10
    assert max(np.max(np.abs(root.residual)) for root in roots) < 1.0e-10


def test_jacobian_is_full_rank_at_two_steps():
    provider, spec, state, _x, y, _temperature = _fixture()
    closure = solve_one_volume_closure(
        spec,
        state,
        provider,
        initial_vapor_mole_fraction=y,
    )
    audits = [
        audit_one_volume_jacobian(
            spec,
            state,
            provider,
            closure.scaled_unknown,
            step_factor=factor,
        )
        for factor in (1.0, 0.5)
    ]

    assert all(audit.rank == 3 for audit in audits)
    assert all(audit.condition < 1.0e8 for audit in audits)
    assert all(not audit.zero_rows for audit in audits)
    assert all(not audit.zero_columns for audit in audits)


def test_nominal_dynamic_case_is_stationary_and_conservative():
    provider, spec, state, x, y, _temperature = _fixture()
    closure = solve_one_volume_closure(
        spec,
        state,
        provider,
        initial_vapor_mole_fraction=y,
    )
    boundary = OneVolumeBoundary(
        flow_lbmolps=1.0,
        inlet_mole_fraction=x,
        inlet_enthalpy_BTU_lbmol=closure.liquid_enthalpy_BTU_lbmol,
        heat_duty_BTUps=0.0,
    )
    trajectory = integrate_one_volume(
        spec=spec,
        initial_state=state,
        provider=provider,
        boundary=boundary,
        initial_vapor_mole_fraction=y,
        time_sec=np.linspace(0.0, 20.0, 5),
        options=OneVolumeIntegrationOptions(
            method="BDF",
            rtol=1.0e-9,
            atol=1.0e-11,
            max_step_sec=1.0,
        ),
    )

    assert (
        np.max(np.abs(trajectory.conserved_state - trajectory.conserved_state[0]))
        < 1.0e-10
    )
    assert trajectory.algebraic_residual_max < 1.0e-9
    assert (
        np.max(
            np.abs(
                trajectory.conserved_state[:, :3]
                - trajectory.conserved_state[0, :3]
                - trajectory.cumulative_external_component_lbmol
            )
        )
        < 1.0e-10
    )
    assert (
        np.max(
            np.abs(
                trajectory.conserved_state[:, 3]
                - trajectory.conserved_state[0, 3]
                - trajectory.cumulative_external_energy_BTU
            )
        )
        < 1.0e-8
    )
