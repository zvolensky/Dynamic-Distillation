import numpy as np

from dynamic_distillation import pr_flash_backend_v1 as backend
from dynamic_distillation.thermo_provider_v1 import ThermoProviderV1


def _provider(monkeypatch):
    provider = ThermoProviderV1(["A", "B", "C"], ["A", "B", "C"])
    monkeypatch.setattr(provider, "configure_backend", lambda: None)
    monkeypatch.setattr(
        backend,
        "liquid_density_lbmol_ft3",
        lambda temperature, pressure, composition: float(
            temperature
            + 0.01 * pressure
            + 100.0 * np.dot(composition, [1.0, 2.0, 3.0])
        ),
    )
    return provider


def test_density_cache_aliases_distinct_temperatures_and_retains_first_value(monkeypatch):
    provider = _provider(monkeypatch)
    composition = [0.5, 0.3, 0.2]

    first = provider.liquid_density_lbmol_ft3(100.00040, 200.0, composition)
    second = provider.liquid_density_lbmol_ft3(100.00049, 200.0, composition)

    assert first == second
    counters = provider.get_call_counters()["uncategorized"]
    assert counters["rhoL_cache_misses"] == 1
    assert counters["rhoL_cache_hits"] == 1


def test_density_cache_alias_is_query_order_dependent(monkeypatch):
    composition = [0.5, 0.3, 0.2]
    forward = _provider(monkeypatch)
    low_then_high = (
        forward.liquid_density_lbmol_ft3(100.00040, 200.0, composition),
        forward.liquid_density_lbmol_ft3(100.00049, 200.0, composition),
    )
    reverse = _provider(monkeypatch)
    high_then_low = (
        reverse.liquid_density_lbmol_ft3(100.00049, 200.0, composition),
        reverse.liquid_density_lbmol_ft3(100.00040, 200.0, composition),
    )

    assert low_then_high[0] == low_then_high[1]
    assert high_then_low[0] == high_then_low[1]
    assert low_then_high[0] != high_then_low[0]


def test_cp_cache_has_the_same_temperature_alias(monkeypatch):
    provider = _provider(monkeypatch)
    monkeypatch.setattr(
        provider,
        "_cp_from_backend",
        lambda temperature, _pressure, _composition: (temperature, -temperature),
    )

    first = provider.cp_liq_vap_btu_per_lbmolF(
        100.00040, 200.0, [0.5, 0.3, 0.2]
    )
    second = provider.cp_liq_vap_btu_per_lbmolF(
        100.00049, 200.0, [0.5, 0.3, 0.2]
    )

    assert first == second
    assert provider.get_call_counters()["uncategorized"]["cp_cache_hits"] == 1
