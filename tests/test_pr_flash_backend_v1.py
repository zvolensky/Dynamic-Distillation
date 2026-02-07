# tests/test_pr_flash_backend_v1.py
#
# Unit tests for pr_flash_backend_v1 liquid density computation without DWSIM.

from __future__ import annotations

import sys
import types

import numpy as np

import dynamic_distillation.pr_flash_backend_v1 as backend


class _DummyArray:
    def __class_getitem__(cls, _):
        # Mimic System.Array[float](seq) by returning a callable.
        return lambda seq: list(seq)


class _FakeDTLC:
    def __init__(self):
        self.calls = []

    def CalcProp(self, _prop_pack, prop, basis, phase, _carray, _T_K, _P_Pa, _x_array):
        self.calls.append((prop, basis, phase))
        # Return 1 kmol/m3 (heuristic path should multiply by 1000 -> mol/m3)
        if prop == "density" and basis == "Mole" and phase == "Liquid":
            return [1.0]
        return [np.nan]


class _FakeDTLCMassFallback:
    def __init__(self):
        self.calls = []

    def CalcProp(self, _prop_pack, prop, basis, phase, _carray, _T_K, _P_Pa, _x_array):
        self.calls.append((prop, basis, phase))
        # Force molar density to fail
        if prop == "density" and basis == "Mole" and phase == "Liquid":
            return [np.nan]
        # Provide mass density (kg/m3)
        if prop == "density" and basis == "Mass" and phase == "Liquid":
            return [800.0]
        # Provide molecular weight (kg/kmol style from DWSIM)
        if prop in ("molecularweight", "molecular weight", "mw") and basis == "Mole" and phase == "Liquid":
            return [58.0]
        return [np.nan]


def test_liquid_density_lbmol_ft3_from_molar_density(monkeypatch):
    # Stub DWSIM init and inject fake DTL calculator + System.Array
    monkeypatch.setattr(backend, "_init_dwsim", lambda: None, raising=True)
    monkeypatch.setattr(backend, "_dtlc", _FakeDTLC(), raising=True)
    monkeypatch.setattr(backend, "_prop_package", object(), raising=True)
    monkeypatch.setattr(backend, "_carray", object(), raising=True)
    monkeypatch.setattr(backend, "_component_ids", ["A", "B"], raising=True)
    monkeypatch.setitem(sys.modules, "System", types.SimpleNamespace(Array=_DummyArray))

    rho = backend.liquid_density_lbmol_ft3(100.0, 200.0, [0.5, 0.5])
    expected = backend._mol_m3_to_lbmol_ft3(1000.0)  # 1 kmol/m3 -> 1000 mol/m3

    assert rho is not None
    assert abs(float(rho) - float(expected)) < 1e-12


def test_liquid_density_lbmol_ft3_mass_density_fallback(monkeypatch):
    # Stub DWSIM init and inject fake DTL calculator + System.Array
    monkeypatch.setattr(backend, "_init_dwsim", lambda: None, raising=True)
    monkeypatch.setattr(backend, "_dtlc", _FakeDTLCMassFallback(), raising=True)
    monkeypatch.setattr(backend, "_prop_package", object(), raising=True)
    monkeypatch.setattr(backend, "_carray", object(), raising=True)
    monkeypatch.setattr(backend, "_component_ids", ["A", "B"], raising=True)
    monkeypatch.setitem(sys.modules, "System", types.SimpleNamespace(Array=_DummyArray))

    rho = backend.liquid_density_lbmol_ft3(100.0, 200.0, [0.5, 0.5])

    # Expected: rho_mass / MW (kg/m3 / kg/mol) => mol/m3, then convert to lbmol/ft3
    mw_kg_per_mol = 58.0 / 1000.0
    rho_mol_m3 = 800.0 / mw_kg_per_mol
    expected = backend._mol_m3_to_lbmol_ft3(rho_mol_m3)

    assert rho is not None
    assert abs(float(rho) - float(expected)) < 1e-12
