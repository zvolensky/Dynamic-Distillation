"""Explicit density-only routing for a Core V3 thermodynamic provider."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Any, Sequence

import numpy as np


class DensityRoutedThermoProviderV1:
    """Keep bulk thermodynamics on one provider and route only liquid density."""

    def __init__(
        self,
        *,
        bulk_provider: Any,
        density_provider: Any,
        density_provider_identity: str,
    ) -> None:
        identity = str(density_provider_identity).strip()
        if not identity:
            raise ValueError("density provider identity is required")
        bulk_components = tuple(
            str(value) for value in getattr(bulk_provider, "component_names_excel", ())
        )
        density_components = tuple(
            str(value) for value in getattr(density_provider, "component_names_excel", ())
        )
        if bulk_components and density_components and bulk_components != density_components:
            raise ValueError("bulk and density providers must use the same component order")
        self.bulk_provider = bulk_provider
        self.density_provider = density_provider
        self.density_provider_identity = identity
        self.provider_identity = f"{getattr(bulk_provider, 'provider_identity', 'bulk')}+{identity}-density"
        self.component_names_excel = list(bulk_components or density_components)
        self.component_ids_dwsim = list(
            getattr(bulk_provider, "component_ids_dwsim", self.component_names_excel)
        )

    def phase_fugacity_coefficients(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> np.ndarray:
        values = self.bulk_provider.phase_fugacity_coefficients(
            phase, temperature_F, pressure_psia, composition
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
                phase, temperature_F, pressure_psia, composition
            )
        )

    def liquid_density_lbmol_ft3(
        self,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> float | None:
        value = self.density_provider.liquid_density_lbmol_ft3(
            temperature_F, pressure_psia, composition
        )
        return None if value is None else float(value)

    def vapor_z_factor_F_psia(
        self,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> float | None:
        value = self.bulk_provider.vapor_z_factor_F_psia(
            temperature_F, pressure_psia, composition
        )
        return None if value is None else float(value)

    def component_mw_lbm_per_lbmol(self) -> np.ndarray:
        values = self.bulk_provider.component_mw_lbm_per_lbmol()
        return np.asarray(values, dtype=float).reshape((-1,)).copy()

    @contextmanager
    def thermo_call_category(self, category: str | None):
        with ExitStack() as stack:
            for provider in (self.bulk_provider, self.density_provider):
                context = getattr(provider, "thermo_call_category", None)
                if callable(context):
                    stack.enter_context(context(category))
            yield

    def set_exact_state_memoization(
        self, enabled: bool, *, clear: bool = True
    ) -> None:
        for provider in (self.bulk_provider, self.density_provider):
            setter = getattr(provider, "set_exact_state_memoization", None)
            if callable(setter):
                setter(bool(enabled), clear=bool(clear))

    def get_exact_state_memoization_stats(self) -> dict[str, Any]:
        getter = getattr(self.bulk_provider, "get_exact_state_memoization_stats", None)
        bulk = getter() if callable(getter) else {}
        density_counters = getattr(self.density_provider, "get_call_counters", None)
        return {
            "bulk_provider": bulk,
            "density_provider_identity": self.density_provider_identity,
            "density_provider_call_counters": (
                density_counters() if callable(density_counters) else {}
            ),
        }

    def __getattr__(self, name: str) -> Any:
        return getattr(self.bulk_provider, name)


__all__ = ["DensityRoutedThermoProviderV1"]
