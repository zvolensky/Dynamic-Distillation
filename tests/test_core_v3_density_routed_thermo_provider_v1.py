from __future__ import annotations

import numpy as np
import pytest

from dynamic_distillation.core_v3.density_routed_thermo_provider_v1 import (
    DensityRoutedThermoProviderV1,
)


class _Provider:
    component_names_excel = ["Water", "Methanol"]
    component_ids_dwsim = ["Water", "Methanol"]
    provider_identity = "bulk"

    def __init__(self, density: float) -> None:
        self.density = density
        self.memo_calls = []

    def phase_fugacity_coefficients(self, *_args):
        return np.array([1.1, 0.9])

    def phase_enthalpy_BTU_lbmol(self, *_args):
        return 123.0

    def liquid_density_lbmol_ft3(self, *_args):
        return self.density

    def vapor_z_factor_F_psia(self, *_args):
        return 0.98

    def component_mw_lbm_per_lbmol(self):
        return np.array([18.0, 32.0])

    def set_exact_state_memoization(self, enabled, *, clear=True):
        self.memo_calls.append((enabled, clear))

    def get_exact_state_memoization_stats(self):
        return {"enabled": True}


def test_density_router_changes_only_liquid_density_ownership():
    bulk = _Provider(1.0)
    density = _Provider(2.5)
    provider = DensityRoutedThermoProviderV1(
        bulk_provider=bulk,
        density_provider=density,
        density_provider_identity="clapeyron_vtpr",
    )

    composition = [0.4, 0.6]
    assert provider.liquid_density_lbmol_ft3(150.0, 15.0, composition) == 2.5
    assert provider.phase_enthalpy_BTU_lbmol("liquid", 150.0, 15.0, composition) == 123.0
    assert np.array_equal(
        provider.phase_fugacity_coefficients("liquid", 150.0, 15.0, composition),
        [1.1, 0.9],
    )
    assert provider.vapor_z_factor_F_psia(150.0, 15.0, composition) == 0.98
    assert np.array_equal(provider.component_mw_lbm_per_lbmol(), [18.0, 32.0])


def test_density_router_controls_both_provider_memoization_scopes():
    bulk = _Provider(1.0)
    density = _Provider(2.5)
    provider = DensityRoutedThermoProviderV1(
        bulk_provider=bulk,
        density_provider=density,
        density_provider_identity="clapeyron_vtpr",
    )

    provider.set_exact_state_memoization(True, clear=True)

    assert bulk.memo_calls == [(True, True)]
    assert density.memo_calls == [(True, True)]
    assert provider.get_exact_state_memoization_stats()["density_provider_identity"] == "clapeyron_vtpr"


def test_density_router_rejects_component_order_mismatch():
    bulk = _Provider(1.0)
    density = _Provider(2.5)
    density.component_names_excel = ["Methanol", "Water"]

    with pytest.raises(ValueError, match="same component order"):
        DensityRoutedThermoProviderV1(
            bulk_provider=bulk,
            density_provider=density,
            density_provider_identity="clapeyron_vtpr",
        )
