"""Explicit property-level provider routing for Core V3 qualification work."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Any, Sequence

import numpy as np


class HybridThermoProviderV1:
    """Route fugacity to one provider and all bulk properties to another."""

    provider_identity = "clapeyron-dwsim-hybrid"

    def __init__(self, *, fugacity_provider: Any, bulk_provider: Any) -> None:
        self.fugacity_provider = fugacity_provider
        self.bulk_provider = bulk_provider
        fugacity_components = tuple(
            str(value)
            for value in getattr(fugacity_provider, "component_names_excel", ())
        )
        bulk_components = tuple(
            str(value)
            for value in getattr(bulk_provider, "component_names_excel", ())
        )
        if fugacity_components and bulk_components and fugacity_components != bulk_components:
            raise ValueError("hybrid thermo providers must use the same component order")
        self.component_names_excel = list(
            bulk_components or fugacity_components
        )
        self.component_ids_dwsim = list(
            getattr(bulk_provider, "component_ids_dwsim", ())
        )

    def phase_fugacity_coefficients(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> np.ndarray:
        values = self.fugacity_provider.phase_fugacity_coefficients(
            phase,
            temperature_F,
            pressure_psia,
            composition,
        )
        return np.asarray(values, dtype=float).reshape((-1,)).copy()

    def phase_enthalpy_BTU_lbmol(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> float:
        return float(
            self.bulk_provider.phase_enthalpy_BTU_lbmol(
                phase,
                temperature_F,
                pressure_psia,
                composition,
            )
        )

    def liquid_density_lbmol_ft3(
        self,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> float | None:
        return self.bulk_provider.liquid_density_lbmol_ft3(
            temperature_F,
            pressure_psia,
            composition,
        )

    def vapor_z_factor_F_psia(
        self,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> float | None:
        return self.bulk_provider.vapor_z_factor_F_psia(
            temperature_F,
            pressure_psia,
            composition,
        )

    def component_mw_lbm_per_lbmol(self) -> np.ndarray:
        values = self.bulk_provider.component_mw_lbm_per_lbmol()
        return np.asarray(values, dtype=float).reshape((-1,)).copy()

    def flash_TP_full_F_psia(
        self,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> Any:
        return self.bulk_provider.flash_TP_full_F_psia(
            temperature_F,
            pressure_psia,
            composition,
        )

    @contextmanager
    def thermo_call_category(self, category: str | None):
        with ExitStack() as stack:
            for provider in (self.fugacity_provider, self.bulk_provider):
                context = getattr(provider, "thermo_call_category", None)
                if callable(context):
                    stack.enter_context(context(category))
            yield

    def set_exact_state_memoization(self, enabled: bool, *, clear: bool = False) -> None:
        for provider in (self.fugacity_provider, self.bulk_provider):
            setter = getattr(provider, "set_exact_state_memoization", None)
            if callable(setter):
                setter(bool(enabled), clear=bool(clear))

    def get_exact_state_memoization_stats(self) -> dict[str, Any]:
        fugacity = self.fugacity_provider.get_exact_state_memoization_stats()
        bulk = self.bulk_provider.get_exact_state_memoization_stats()
        families = {
            "fugacity": dict(fugacity["families"]["fugacity"]),
            **{
                name: dict(bulk["families"][name])
                for name in ("enthalpy", "density", "vapor_z")
            },
        }
        return {
            "enabled": bool(fugacity["enabled"] and bulk["enabled"]),
            "hits": int(sum(item["hits"] for item in families.values())),
            "misses": int(sum(item["misses"] for item in families.values())),
            "families": families,
        }

    def __getattr__(self, name: str) -> Any:
        # Optional non-governing compatibility helpers remain bulk-provider
        # owned. Governing methods above are explicit and cannot fall through.
        return getattr(self.bulk_provider, name)


__all__ = ["HybridThermoProviderV1"]
