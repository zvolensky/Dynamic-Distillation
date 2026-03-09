import numpy as np
import pytest

from dynamic_distillation.uv_flash_stage_v1 import (
    BTU_PER_PSI_FT3,
    R_GAS_PSIA_FT3_PER_LBMOL_R,
    initialize_uv_stage_state_from_tp_profile,
    solve_uv_flash_stage,
)


class _FakeUvProvider:
    def __init__(self):
        self.x = np.array([0.5, 0.5], dtype=float)
        self.y = np.array([0.25, 0.75], dtype=float)
        self.rhoL = 8.0

    def _hL(self, T_F: float, P_psia: float) -> float:
        return 12.0 + 0.8 * float(T_F) + 0.05 * float(P_psia)

    def _hV(self, T_F: float, P_psia: float) -> float:
        return 30.0 + 1.1 * float(T_F) + 0.02 * float(P_psia)

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        x = self.x.copy()
        y = self.y.copy()
        K = y / x
        return x.tolist(), y.tolist(), K.tolist(), self._hL(T_F, P_psia), self._hV(T_F, P_psia)

    def liquid_density_lbmol_ft3(self, T_F, P_psia, x):
        return float(self.rhoL)

    def vapor_z_factor_F_psia(self, T_F, P_psia, y):
        return 1.0

    def phase_enthalpy_BTU_lbmol(self, phase, T_F, P_psia, comp):
        phase_name = str(phase).strip().lower()
        if phase_name == "liquid":
            return self._hL(T_F, P_psia)
        if phase_name == "vapor":
            return self._hV(T_F, P_psia)
        raise ValueError("unknown phase")


def test_solve_uv_flash_stage_recovers_known_solution():
    prov = _FakeUvProvider()
    beta_true = 0.4
    z = (1.0 - beta_true) * prov.x + beta_true * prov.y
    T_true = 120.0
    P_true = 210.0
    vL = 1.0 / prov.rhoL
    vV = R_GAS_PSIA_FT3_PER_LBMOL_R * (T_true + 459.67) / P_true
    hL = prov._hL(T_true, P_true)
    hV = prov._hV(T_true, P_true)
    uL = hL - P_true * vL * BTU_PER_PSI_FT3
    uV = hV - P_true * vV * BTU_PER_PSI_FT3
    u_target = (1.0 - beta_true) * uL + beta_true * uV
    v_target = (1.0 - beta_true) * vL + beta_true * vV

    res = solve_uv_flash_stage(
        prov,
        z_overall=z,
        u_target_BTU_lbmol=u_target,
        v_target_ft3_lbmol=v_target,
    )

    assert res.converged is True
    assert res.T_F == pytest.approx(T_true, abs=1.0e-6)
    assert res.P_psia == pytest.approx(P_true, abs=1.0e-6)
    assert res.beta_vapor == pytest.approx(beta_true, abs=1.0e-8)
    assert res.residual_u_BTU_lbmol == pytest.approx(0.0, abs=1.0e-6)
    assert res.residual_v_ft3_lbmol == pytest.approx(0.0, abs=1.0e-9)
    assert res.residual_beta == pytest.approx(0.0, abs=1.0e-9)


def test_initialize_uv_stage_state_from_tp_profile_builds_total_state():
    prov = _FakeUvProvider()
    T_F = 150.0
    P_psia = 220.0
    x = np.array([0.6, 0.4], dtype=float)
    y = np.array([0.2, 0.8], dtype=float)
    ML = 10.0
    vapor_volume = 20.0

    ref = initialize_uv_stage_state_from_tp_profile(
        prov,
        T_F=T_F,
        P_psia=P_psia,
        x_liq=x,
        y_vap=y,
        liquid_holdup_lbmol=ML,
        vapor_volume_ft3=vapor_volume,
    )

    vL = 1.0 / prov.rhoL
    vV = R_GAS_PSIA_FT3_PER_LBMOL_R * (T_F + 459.67) / P_psia
    MV = vapor_volume / vV
    hL = prov._hL(T_F, P_psia)
    hV = prov._hV(T_F, P_psia)
    uL = hL - P_psia * vL * BTU_PER_PSI_FT3
    uV = hV - P_psia * vV * BTU_PER_PSI_FT3
    n_expected = ML * x + MV * y
    U_expected = ML * uL + MV * uV
    V_expected = ML * vL + MV * vV

    assert np.allclose(ref.total_component_holdup_lbmol, n_expected)
    assert ref.total_internal_energy_BTU == pytest.approx(U_expected)
    assert ref.total_volume_ft3 == pytest.approx(V_expected)
    assert ref.total_moles_lbmol == pytest.approx(np.sum(n_expected))
    assert ref.vapor_moles_lbmol == pytest.approx(MV)
    assert ref.initial_guess.T_F == pytest.approx(T_F)
    assert ref.initial_guess.P_psia == pytest.approx(P_psia)
