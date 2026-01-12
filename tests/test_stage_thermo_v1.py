import numpy as np
import pytest

from dynamic_distillation.stage_thermo_v1 import flash_TP_full_F_psia


class _FakeThermoProvider:
    def __init__(self):
        self.calls = []

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        self.calls.append((float(T_F), float(P_psia), list(z)))
        z = np.asarray(z, dtype=float)
        z = z / z.sum()
        # Return x=y=z, K=ones, HL/HV constants
        x = z.copy()
        y = z.copy()
        K = np.ones_like(z)
        HL = -1000.0
        HV = 500.0
        return x.tolist(), y.tolist(), K.tolist(), HL, HV


def test_stage_flash_adapter_calls_provider_and_normalizes():
    prov = _FakeThermoProvider()
    res = flash_TP_full_F_psia(prov, T_F=100.0, P_psia=200.0, z=[2.0, 2.0], n_components=2)

    assert len(prov.calls) == 1
    assert abs(sum(res.x) - 1.0) < 1e-12
    assert abs(sum(res.y) - 1.0) < 1e-12
    assert np.allclose(res.K, [1.0, 1.0])
    assert res.HL_BTU_lbmol == -1000.0
    assert res.HV_BTU_lbmol == 500.0


class _FakeThermoProviderWithZ:
    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        z = np.asarray(z, dtype=float)
        z = z / z.sum()
        x = z.copy()
        y = z.copy()
        K = np.ones_like(z)
        HL = -123.0
        HV = 456.0
        Z = 0.85
        return x.tolist(), y.tolist(), K.tolist(), HL, HV, Z


def test_stage_flash_adapter_accepts_optional_Z_factor():
    prov = _FakeThermoProviderWithZ()
    res = flash_TP_full_F_psia(prov, T_F=100.0, P_psia=200.0, z=[1.0, 1.0], n_components=2)
    assert res.Z == pytest.approx(0.85)
