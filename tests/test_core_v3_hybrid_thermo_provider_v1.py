from __future__ import annotations

from contextlib import contextmanager

import numpy as np
import pytest

from dynamic_distillation.core_v3.hybrid_thermo_provider_v1 import (
    HybridThermoProviderV1,
)


class _Provider:
    def __init__(self, name, components=("A", "B")):
        self.name = name
        self.component_names_excel = list(components)
        self.component_ids_dwsim = list(components)
        self.calls = []

    def phase_fugacity_coefficients(self, phase, T, P, composition):
        self.calls.append(("fugacity", phase))
        return np.full(len(composition), 2.0 if self.name == "fugacity" else 9.0)

    def phase_enthalpy_BTU_lbmol(self, phase, T, P, composition):
        self.calls.append(("enthalpy", phase))
        return 100.0

    def liquid_density_lbmol_ft3(self, T, P, composition):
        self.calls.append(("density", "liquid"))
        return 0.5

    def vapor_z_factor_F_psia(self, T, P, composition):
        self.calls.append(("z", "vapor"))
        return 0.8

    def component_mw_lbm_per_lbmol(self):
        self.calls.append(("mw", "fixed"))
        return np.array([10.0, 20.0])

    def flash_TP_full_F_psia(self, T, P, composition):
        self.calls.append(("flash", "tp"))
        z = np.asarray(composition, dtype=float)
        return z, z, np.ones_like(z), 0.0, 0.0

    @contextmanager
    def thermo_call_category(self, category):
        self.calls.append(("category", category))
        yield


def test_hybrid_routes_only_fugacity_to_fugacity_provider():
    fugacity = _Provider("fugacity")
    bulk = _Provider("bulk")
    provider = HybridThermoProviderV1(
        fugacity_provider=fugacity,
        bulk_provider=bulk,
    )

    assert np.allclose(
        provider.phase_fugacity_coefficients("liquid", 100.0, 200.0, [0.5, 0.5]),
        2.0,
    )
    assert provider.phase_enthalpy_BTU_lbmol(
        "liquid", 100.0, 200.0, [0.5, 0.5]
    ) == 100.0
    assert provider.liquid_density_lbmol_ft3(100.0, 200.0, [0.5, 0.5]) == 0.5
    assert provider.vapor_z_factor_F_psia(100.0, 200.0, [0.5, 0.5]) == 0.8
    assert np.allclose(provider.component_mw_lbm_per_lbmol(), [10.0, 20.0])
    provider.flash_TP_full_F_psia(100.0, 200.0, [0.5, 0.5])

    assert fugacity.calls == [("fugacity", "liquid")]
    assert ("fugacity", "liquid") not in bulk.calls
    assert {name for name, _detail in bulk.calls} == {
        "enthalpy",
        "density",
        "z",
        "mw",
        "flash",
    }


def test_hybrid_rejects_mismatched_component_order():
    with pytest.raises(ValueError, match="same component order"):
        HybridThermoProviderV1(
            fugacity_provider=_Provider("fugacity", ("A", "B")),
            bulk_provider=_Provider("bulk", ("B", "A")),
        )
