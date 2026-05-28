from __future__ import annotations

import sys
from types import ModuleType

import numpy as np
import pytest

from dynamic_distillation.thermo_clapeyron_provider_v1 import ThermoClapeyronProviderV1


def _install_fake_pyclapeyron(monkeypatch) -> ModuleType:
    mod = ModuleType("pyclapeyron")
    mod._tp_flash_calls = 0
    mod._volume_calls = 0
    mod._enthalpy_calls = 0
    mod._cp_calls = 0
    mod._zfactor_calls = 0

    def PR(components, **kwargs):
        return {
            "model": "PR",
            "components": list(components),
            "kwargs": dict(kwargs),
        }

    def WalkerIdeal(*args, **kwargs):
        return ("WalkerIdeal", args, kwargs)

    def tp_flash(model, p, T, n):
        _ = (model, p, T, n)
        mod._tp_flash_calls += 1
        return (
            np.array([[0.8, 0.2], [0.2, 0.8]], dtype=float),
            np.array([[0.8, 0.2], [0.2, 0.8]], dtype=float),
            0.0,
        )

    def compressibility_factor(model, p, T, z, phase=None):
        _ = (model, p, T, phase)
        mod._zfactor_calls += 1
        z_arr = np.asarray(z, dtype=float).reshape((-1,))
        return 0.1 if z_arr[0] > z_arr[-1] else 0.9

    def enthalpy(model, p, T, z, phase=None):
        _ = (model, p, T, z)
        mod._enthalpy_calls += 1
        return 100.0 if str(phase).lower().startswith("liq") else 200.0

    def isobaric_heat_capacity(model, p, T, z, phase=None):
        _ = (model, p, T, z)
        mod._cp_calls += 1
        return 10.0 if str(phase).lower().startswith("liq") else 20.0

    def volume(model, p, T, z, phase=None):
        _ = (model, p, T, z)
        mod._volume_calls += 1
        return 1.0e-4 if str(phase).lower().startswith("liq") else 2.0e-2

    def bubble_temperature(model, p, x):
        _ = (model, p, x)
        return (350.0, 0.0, 0.0, np.array([0.2, 0.8], dtype=float))

    mod.PR = PR
    mod.WalkerIdeal = WalkerIdeal
    mod.tp_flash = tp_flash
    mod.compressibility_factor = compressibility_factor
    mod.enthalpy = enthalpy
    mod.isobaric_heat_capacity = isobaric_heat_capacity
    mod.volume = volume
    mod.bubble_temperature = bubble_temperature
    monkeypatch.setitem(sys.modules, "pyclapeyron", mod)
    return mod


def test_clapeyron_provider_flash_and_scalar_helpers(monkeypatch):
    mod = _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
        ideal_model_name="WalkerIdeal",
    )

    x, y, K, HL, HV, Z = provider.flash_TP_full_F_psia(80.0, 14.7, [0.5, 0.5])
    cpL, cpV = provider.cp_liq_vap_btu_per_lbmolF(80.0, 14.7, [0.5, 0.5])
    rhoL = provider.liquid_density_lbmol_ft3(80.0, 14.7, [0.8, 0.2])
    T_bub = provider.bubble_point_temperature_F_psia(14.7, [0.8, 0.2])

    assert np.allclose(x, np.array([0.8, 0.2], dtype=float))
    assert np.allclose(y, np.array([0.2, 0.8], dtype=float))
    assert np.allclose(K, np.array([0.25, 4.0], dtype=float))
    assert HL == pytest.approx(42.992256, rel=1e-6)
    assert HV == pytest.approx(85.984512, rel=1e-6)
    assert Z == pytest.approx(0.9, rel=1e-9)
    assert cpL == pytest.approx(2.38845867, rel=1e-6)
    assert cpV == pytest.approx(4.77691734, rel=1e-6)
    assert rhoL == pytest.approx(0.624279605, rel=1e-6)
    assert T_bub == pytest.approx(170.33, abs=0.05)
    assert mod._tp_flash_calls == 1
    assert mod._volume_calls == 1
    counters = provider.get_call_counters()
    assert counters["uncategorized"]["flash_cache_misses"] == 1
    assert counters["uncategorized"]["flash_cache_hits"] == 1


def test_clapeyron_provider_batch_flash_reuses_scalar_contract(monkeypatch):
    mod = _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
    )

    batch = provider.flash_TP_full_batch(
        [80.0, 90.0],
        [14.7, 14.7],
        [[0.5, 0.5], [0.6, 0.4]],
    )
    counters = provider.get_call_counters()

    assert len(batch) == 2
    assert len(batch[0]) == 8
    assert np.allclose(np.asarray(batch[0][0], dtype=float), np.array([0.8, 0.2], dtype=float))
    assert np.allclose(np.asarray(batch[0][1], dtype=float), np.array([0.2, 0.8], dtype=float))
    assert np.allclose(np.asarray(batch[1][2], dtype=float), np.array([0.25, 4.0], dtype=float))
    assert batch[0][6] == pytest.approx(2.38845867, rel=1e-6)
    assert batch[0][7] == pytest.approx(4.77691734, rel=1e-6)
    assert counters["uncategorized"]["batch_flash_requests"] == 1
    assert counters["uncategorized"]["batch_flash_rows"] == 2
    assert counters["uncategorized"]["flash_requests"] == 2
    assert counters["uncategorized"]["flash_cache_misses"] == 2
    assert mod._tp_flash_calls == 2
    assert mod._cp_calls == 4


def test_clapeyron_provider_equilibrium_batch_skips_enthalpy_and_cp(monkeypatch):
    mod = _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
    )

    batch = provider.flash_TP_equilibrium_batch_F_psia(
        [80.0, 90.0],
        [14.7, 14.7],
        [[0.5, 0.5], [0.6, 0.4]],
    )
    counters = provider.get_call_counters()

    assert len(batch) == 2
    assert np.allclose(np.asarray(batch[0][0], dtype=float), np.array([0.8, 0.2], dtype=float))
    assert np.allclose(np.asarray(batch[0][1], dtype=float), np.array([0.2, 0.8], dtype=float))
    assert np.allclose(np.asarray(batch[1][2], dtype=float), np.array([0.25, 4.0], dtype=float))
    assert batch[0][3] == pytest.approx(0.9, rel=1e-9)
    assert counters["uncategorized"]["equilibrium_only_batch_flash_requests"] == 1
    assert counters["uncategorized"]["equilibrium_only_flash_requests"] == 2
    assert mod._tp_flash_calls == 2
    assert mod._zfactor_calls == 4
    assert mod._enthalpy_calls == 0
    assert mod._cp_calls == 0


def test_clapeyron_provider_warm_startup_kernels_primes_density_and_flash(monkeypatch):
    mod = _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
    )

    info = provider.warm_startup_kernels(
        density_state=(80.0, 14.7, [0.8, 0.2]),
        flash_rows=[
            (80.0, 14.7, [0.8, 0.2]),
            (90.0, 14.7, [0.6, 0.4]),
        ],
    )
    counters = provider.get_call_counters()

    assert info["density_ready"] is True
    assert info["flash_ready"] is True
    assert info["flash_rows"] == 2
    assert mod._volume_calls == 1
    assert mod._tp_flash_calls == 2
    assert mod._cp_calls == 0
    assert counters["uncategorized"]["liquid_density_requests"] == 1
    assert counters["uncategorized"]["batch_flash_requests"] == 1
    assert counters["uncategorized"]["batch_flash_rows"] == 2

    rho = provider.liquid_density_lbmol_ft3(80.0, 14.7, [0.8, 0.2])
    batch = provider.flash_TP_full_batch(
        [80.0, 90.0],
        [14.7, 14.7],
        [[0.8, 0.2], [0.6, 0.4]],
    )
    counters2 = provider.get_call_counters()

    assert rho == pytest.approx(0.624279605, rel=1e-6)
    assert len(batch) == 2
    assert mod._volume_calls == 1
    assert mod._tp_flash_calls == 2
    assert counters2["uncategorized"]["liquid_density_cache_hits"] == 1
    assert counters2["uncategorized"]["flash_cache_hits"] == 2


def test_clapeyron_provider_batch_flash_defers_cp_until_explicit_lookup(monkeypatch):
    mod = _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
    )

    batch = provider.flash_TP_full_batch_no_cp(
        [80.0],
        [14.7],
        [[0.5, 0.5]],
    )
    counters0 = provider.get_call_counters()

    assert len(batch) == 1
    assert mod._tp_flash_calls == 1
    assert mod._cp_calls == 0
    assert "cp_requests" not in counters0["uncategorized"]

    cpL, cpV = provider.cp_liq_vap_btu_per_lbmolF(80.0, 14.7, [0.5, 0.5])
    counters1 = provider.get_call_counters()

    assert cpL == pytest.approx(2.38845867, rel=1e-6)
    assert cpV == pytest.approx(4.77691734, rel=1e-6)
    assert mod._tp_flash_calls == 1
    assert mod._cp_calls == 2
    assert counters1["uncategorized"]["flash_cache_hits"] >= 1
    assert counters1["uncategorized"]["cp_requests"] == 1


def test_clapeyron_provider_exact_state_cache_reuses_tp_flash(monkeypatch):
    mod = _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
    )

    provider.flash_TP_full(80.0, 14.7, [0.5, 0.5])
    provider.flash_TP_full(80.0, 14.7, [0.5, 0.5])
    counters = provider.get_call_counters()

    assert mod._tp_flash_calls == 1
    assert counters["uncategorized"]["flash_requests"] == 1
    assert counters["uncategorized"]["flash_cache_misses"] == 1
    assert counters["uncategorized"]["flash_cache_hits"] == 1


def test_clapeyron_provider_liquid_density_uses_exact_state_cache(monkeypatch):
    mod = _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
    )

    rho0 = provider.liquid_density_lbmol_ft3(80.0, 14.7, [0.8, 0.2])
    rho1 = provider.liquid_density_lbmol_ft3(80.0, 14.7, [0.8, 0.2])
    counters = provider.get_call_counters()

    assert rho0 == pytest.approx(rho1, rel=1e-12)
    assert mod._volume_calls == 1
    assert counters["uncategorized"]["liquid_density_requests"] == 1
    assert counters["uncategorized"]["liquid_density_cache_misses"] == 1
    assert counters["uncategorized"]["liquid_density_cache_hits"] == 1


def test_clapeyron_provider_batch_flash_requires_matching_row_counts(monkeypatch):
    _install_fake_pyclapeyron(monkeypatch)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A", "B"],
        component_ids_dwsim=["A", "B"],
        model_name="PR",
    )

    with pytest.raises(ValueError, match="equal-length"):
        provider.flash_TP_full_batch([80.0], [14.7, 15.0], [[0.5, 0.5]])


def test_clapeyron_provider_requires_optional_package(monkeypatch):
    monkeypatch.delitem(sys.modules, "pyclapeyron", raising=False)

    def fake_import_module(name):
        if name == "pyclapeyron":
            raise ImportError("missing pyclapeyron")
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr("dynamic_distillation.thermo_clapeyron_provider_v1.importlib.import_module", fake_import_module)
    provider = ThermoClapeyronProviderV1(
        component_names_excel=["A"],
        component_ids_dwsim=["A"],
        model_name="PR",
    )

    with pytest.raises(RuntimeError, match="pyclapeyron"):
        provider.flash_TP_full_F_psia(80.0, 14.7, [1.0])
