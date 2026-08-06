from __future__ import annotations

from contextlib import nullcontext

import numpy as np

import dynamic_distillation.thermo_provider_v1 as provider_module
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


class _Backend:
    def __init__(self):
        self.fugacity_calls = 0
        self.enthalpy_calls = 0
        self.density_calls = 0
        self.z_calls = 0

    def set_component_ids(self, _values): pass
    def set_component_names_excel(self, _values): pass
    def set_property_package(self, _value): pass
    def set_debug_trace_hook(self, _value): pass
    def set_debug_trace_context(self, _value): pass
    def silence_console(self, _enabled=True): return nullcontext()

    def phase_fugacity_coefficients(self, _temperature, _pressure, composition, _phase):
        self.fugacity_calls += 1
        return np.asarray(composition, dtype=float) + 1.0

    def phase_enthalpy_BTU_lbmol(self, temperature, pressure, composition, _phase):
        self.enthalpy_calls += 1
        return float(temperature + pressure + sum(composition))

    def liquid_density_lbmol_ft3(self, temperature, pressure, composition):
        self.density_calls += 1
        return float(1.0 + temperature * 1.0e-3 + pressure * 1.0e-4 + sum(composition))

    def vapor_z_factor_F_psia(self, temperature, pressure, composition):
        self.z_calls += 1
        return float(0.8 + temperature * 1.0e-5 + pressure * 1.0e-6 + sum(composition) * 1.0e-4)


def _provider(monkeypatch):
    backend = _Backend()
    monkeypatch.setattr(provider_module, "backend", backend, raising=True)
    return ThermoProviderV1(["A", "B"], ["A", "B"]), backend


def test_production_exact_memo_uses_exact_keys_and_copy_safe_arrays(monkeypatch):
    provider, backend = _provider(monkeypatch)
    provider.set_exact_state_memoization(True)
    first = provider.phase_fugacity_coefficients("liquid", 100.0, 20.0, [0.4, 0.6])
    first[0] = -99.0
    repeated = provider.phase_fugacity_coefficients("liquid", 100.0, 20.0, [0.4, 0.6])
    provider.phase_fugacity_coefficients("liquid", 100.0 + 1.0e-12, 20.0, [0.4, 0.6])
    assert backend.fugacity_calls == 2
    assert repeated[0] > 0.0
    assert provider.get_exact_state_memoization_stats()["families"]["fugacity"] == {
        "hits": 1,
        "misses": 2,
        "entries": 2,
    }


def test_production_exact_memo_covers_all_runtime_property_families(monkeypatch):
    provider, backend = _provider(monkeypatch)
    provider.set_exact_state_memoization(True)
    for _ in range(2):
        provider.phase_enthalpy_BTU_lbmol("liquid", 100.0, 20.0, [0.4, 0.6])
        provider.liquid_density_lbmol_ft3(100.0, 20.0, [0.4, 0.6])
        provider.vapor_z_factor_F_psia(100.0, 20.0, [0.4, 0.6])
    assert (backend.enthalpy_calls, backend.density_calls, backend.z_calls) == (1, 1, 1)
    stats = provider.get_exact_state_memoization_stats()
    assert stats["hits"] == 3
    assert stats["misses"] == 3


def test_clear_starts_a_new_exact_memo_scope(monkeypatch):
    provider, backend = _provider(monkeypatch)
    provider.set_exact_state_memoization(True)
    provider.phase_enthalpy_BTU_lbmol("liquid", 100.0, 20.0, [0.4, 0.6])
    provider.phase_enthalpy_BTU_lbmol("liquid", 100.0, 20.0, [0.4, 0.6])
    provider.clear_exact_state_memoization()
    provider.phase_enthalpy_BTU_lbmol("liquid", 100.0, 20.0, [0.4, 0.6])
    assert backend.enthalpy_calls == 2
    stats = provider.get_exact_state_memoization_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 1
