# tests/test_thermo_provider_v1.py
"""
test_thermo_provider_v1.py

Dynamic Distillation - Thermo Provider Tests

PURPOSE
-------
Validate `ThermoProviderV1` API behavior using backend monkeypatching so tests
remain independent of local DWSIM availability.

SCOPE
-----
- component setup calls, flash return handling, and derived-property helpers
- deterministic behavior under fake backend responses

KEY DEPENDENCIES
----------------
- thermo_provider_v1
- pytest monkeypatch + numpy fixtures
"""


from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


class _FakeBackend:
    def __init__(self):
        self.set_ids_called = None
        self.set_names_called = None
        self.set_property_package_called = None
        self.flash_calls = []
        self.coeff_calls = []
        self.debug_trace_hook = None
        self.debug_trace_context = None

    def set_component_ids(self, ids):
        self.set_ids_called = list(ids)

    def set_component_names(self, names):
        self.set_names_called = list(names)

    def set_property_package(self, package):
        self.set_property_package_called = str(package)

    def set_debug_trace_hook(self, hook):
        self.debug_trace_hook = hook

    def set_debug_trace_context(self, context):
        self.debug_trace_context = context

    def silence_console(self, enabled=True):
        class _CM:
            def __enter__(self_inner): return None
            def __exit__(self_inner, exc_type, exc, tb): return False
        return _CM()

    def flash_TP_full_F_psia(self, T_F, P_psia, z):
        self.flash_calls.append((float(T_F), float(P_psia), np.asarray(z, dtype=float)))
        z = np.asarray(z, dtype=float)
        x = z / z.sum()
        y = (z + 0.1) / (z + 0.1).sum()
        K = y / x
        HL = 100.0 + 2.0 * float(T_F)   # linear in T
        HV = 200.0 + 3.0 * float(T_F)
        return x, y, K, HL, HV

    def get_thermo_coefficients(self, T_F, P_psia, z, perturbation_dt=1.0):
        self.coeff_calls.append((float(T_F), float(P_psia), np.asarray(z, dtype=float), float(perturbation_dt)))
        coeffs = {
            "HL_B": 2.0,
            "HV_B": 3.0,
            "K_A": np.array([0.0]),
            "K_B": np.array([0.0]),
            "HL_A": 0.0,
            "HV_A": 0.0,
        }
        props = {"x": np.array(z), "y": np.array(z), "HL": 0.0, "HV": 0.0}
        return coeffs, props

    def phase_fugacity_coefficients(self, T_F, P_psia, comp, phase):
        values = np.asarray(comp, dtype=float)
        multiplier = 2.0 if str(phase).lower() == "liquid" else 0.5
        return multiplier * np.ones_like(values)



def test_provider_configures_backend_and_flashes(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()
    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)

    prov = ThermoProviderV1(
        component_names_excel=["n-Propane", "n-Butane"],
        component_ids_dwsim=["Propane", "N-butane"],
        cp_dt_F=1.0,
        silence_backend_console=True,
    )

    res = prov.flash_TP_full(100.0, 200.0, [0.7, 0.3])

    assert fake.set_ids_called == ["Propane", "N-butane"]
    assert fake.set_names_called == ["n-Propane", "n-Butane"]

    assert res.x.shape == (2,)
    assert res.y.shape == (2,)
    assert res.K.shape == (2,)
    assert isinstance(res.HL_BTU_lbmol, float)
    assert isinstance(res.HV_BTU_lbmol, float)
    assert res.cpL_BTU_lbmolF == 2.0
    assert res.cpV_BTU_lbmolF == 3.0


def test_provider_normalizes_z(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()
    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)

    prov = ThermoProviderV1(["A", "B"], ["A", "B"])
    prov.flash_TP_full(100.0, 200.0, [7.0, 3.0])

    _T, _P, z_passed = fake.flash_calls[-1]
    assert abs(float(z_passed.sum()) - 1.0) < 1e-12
    assert np.allclose(z_passed, np.array([0.7, 0.3]))


def test_provider_cp_fallback_if_coefficients_missing(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()

    # Force the provider to skip the coefficient path and use finite-difference.
    # (Deleting doesn't work because methods live on the class, not the instance.)
    def _raise(*args, **kwargs):
        raise AttributeError("no get_thermo_coefficients")

    fake.get_thermo_coefficients = _raise  # override on the instance

    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)

    prov = ThermoProviderV1(["A", "B"], ["A", "B"], cp_dt_F=2.0)
    res = prov.flash_TP_full(10.0, 100.0, [0.5, 0.5])

    # HL = 100 + 2*T so cpL should be ~2, HV = 200 + 3*T so cpV ~3
    assert abs(res.cpL_BTU_lbmolF - 2.0) < 1e-12
    assert abs(res.cpV_BTU_lbmolF - 3.0) < 1e-12


def test_provider_lightweight_flash_skips_cp_coefficients(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()
    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)

    prov = ThermoProviderV1(["A", "B"], ["A", "B"], cp_dt_F=2.0)
    x, y, K, HL, HV, Z = prov.flash_TP_full_F_psia(10.0, 100.0, [0.5, 0.5])

    assert np.allclose(x, [0.5, 0.5])
    assert np.allclose(y, np.asarray([0.6, 0.6]) / 1.2)
    assert np.allclose(K, y / x)
    assert HL == pytest.approx(120.0)
    assert HV == pytest.approx(230.0)
    assert Z is None
    assert len(fake.flash_calls) == 1
    assert fake.coeff_calls == []


def test_provider_stage_aware_lightweight_flash_skips_cp_coefficients(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()
    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)

    prov = ThermoProviderV1(["A", "B"], ["A", "B"])
    res = prov.flash_TP_full_stage_F_psia(3, 15.0, 120.0, [0.8, 0.2])

    assert len(res) == 6
    assert len(fake.flash_calls) == 1
    assert fake.coeff_calls == []


def test_provider_exposes_phase_fugacity_coefficients(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()
    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)
    provider = ThermoProviderV1(["A", "B"], ["A", "B"])

    values = provider.phase_fugacity_coefficients(
        "liquid",
        100.0,
        200.0,
        [7.0, 3.0],
    )

    assert np.allclose(values, [2.0, 2.0])
    assert provider.get_call_counters()["uncategorized"]["fugacity_requests"] == 1


def test_provider_records_call_counters_and_cache_hits(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()
    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)

    prov = ThermoProviderV1(["A", "B"], ["A", "B"])
    with prov.thermo_call_category("main_tray_refresh"):
        prov.flash_TP_full_F_psia(25.0, 120.0, [0.5, 0.5])
    with prov.thermo_call_category("temperature_state_cp_lookup"):
        cpL_1, cpV_1 = prov.cp_liq_vap_btu_per_lbmolF(25.0, 120.0, [0.5, 0.5])
    with prov.thermo_call_category("temperature_state_cp_lookup"):
        cpL_2, cpV_2 = prov.cp_liq_vap_btu_per_lbmolF(25.0, 120.0, [0.5, 0.5])

    counters = prov.get_call_counters()

    assert cpL_1 == pytest.approx(2.0)
    assert cpV_1 == pytest.approx(3.0)
    assert cpL_2 == pytest.approx(2.0)
    assert cpV_2 == pytest.approx(3.0)
    assert counters["main_tray_refresh"]["flash_requests"] == 1
    assert counters["main_tray_refresh"]["backend_flash_equivalents"] == 1
    assert counters["main_tray_refresh"]["wall_sec"] >= 0.0
    assert counters["temperature_state_cp_lookup"]["cp_requests"] == 1
    assert counters["temperature_state_cp_lookup"]["cp_cache_misses"] == 1
    assert counters["temperature_state_cp_lookup"]["cp_cache_hits"] == 1
    assert counters["temperature_state_cp_lookup"]["backend_flash_equivalents"] == 2
    assert counters["temperature_state_cp_lookup"]["wall_sec"] >= 0.0


def test_provider_thermo_call_category_scopes_debug_trace_context(monkeypatch):
    import dynamic_distillation.thermo_provider_v1 as tp_mod

    fake = _FakeBackend()
    monkeypatch.setattr(tp_mod, "backend", fake, raising=True)

    prov = ThermoProviderV1(["A", "B"], ["A", "B"])
    prov.configure_backend()
    prov.set_debug_trace_context("runtime_step_1")

    with prov.thermo_call_category("helper_flash"):
        assert prov.debug_trace_context == "runtime_step_1:helper_flash"
        assert fake.debug_trace_context == "runtime_step_1:helper_flash"

    assert prov.debug_trace_context == "runtime_step_1"
    assert fake.debug_trace_context == "runtime_step_1"
