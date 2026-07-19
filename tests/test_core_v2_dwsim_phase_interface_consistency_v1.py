from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from dynamic_distillation.core_v2.dwsim_phase_interface_consistency_v1 import (
    IndependentPengRobinsonProvider,
    PengRobinsonParameters,
    evaluate_interface_state,
)


class _FlashProvider:
    def __init__(self):
        self.x = np.asarray([0.69, 0.29, 0.02])
        self.y = np.asarray([0.84, 0.15, 0.01])
        self.K = self.y / self.x

    def flash_TP_full_F_psia(self, _temperature, _pressure, _z):
        return self.x, self.y, self.K, 0.0, 0.0

    def phase_fugacity_coefficients(
        self, phase, _temperature, _pressure, composition
    ):
        comp = np.asarray(composition, dtype=float)
        if str(phase).lower() == "liquid":
            return np.ones_like(comp)
        return np.ones_like(comp)


def test_interface_decomposition_separates_flash_liquid_from_overall_z():
    provider = _FlashProvider()
    beta = 0.001
    z = (1.0 - beta) * provider.x + beta * provider.y
    result = evaluate_interface_state(
        provider,
        temperature_F=130.0,
        pressure_psia=200.0,
        overall_z=z,
        direct_bubble_y=provider.y,
    )

    assert result["metrics"]["legacy_direct_y_minus_Kz_max_abs"] > 0.0
    assert result["metrics"]["direct_y_minus_flash_y_max_abs"] < 1.0e-14
    assert result["metrics"]["flash_y_minus_Kx_flash_max_abs"] < 1.0e-14
    assert result["metrics"]["lever_rule_closure_max_abs"] < 1.0e-12
    assert result["metrics"]["decomposition_closure_max_abs"] < 1.0e-14


def test_independent_pr_fugacities_are_finite_for_both_roots():
    provider = IndependentPengRobinsonProvider(
        PengRobinsonParameters(
            critical_temperature_K=np.asarray([369.83, 425.12, 469.7]),
            critical_pressure_Pa=np.asarray([4.248e6, 3.796e6, 3.37e6]),
            acentric_factor=np.asarray([0.152, 0.2, 0.251]),
            binary_interaction=np.zeros((3, 3)),
        )
    )
    composition = [0.70, 0.28, 0.02]
    phi_l = provider.phase_fugacity_coefficients(
        "liquid", 133.7, 218.44, composition
    )
    phi_v = provider.phase_fugacity_coefficients(
        "vapor", 133.7, 218.44, composition
    )

    assert phi_l.shape == (3,)
    assert phi_v.shape == (3,)
    assert np.all(np.isfinite(phi_l))
    assert np.all(np.isfinite(phi_v))
    assert np.all(phi_l > 0.0)
    assert np.all(phi_v > 0.0)


def test_provider_study_kernel_has_no_column_solve_or_integrator_import():
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "src"
        / "dynamic_distillation"
        / "core_v2"
        / "dwsim_phase_interface_consistency_v1.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not any(name.startswith("scipy.integrate") for name in imported)
    assert not any("steady_solve" in name for name in imported)
    assert not any("residual_gate" in name for name in imported)
