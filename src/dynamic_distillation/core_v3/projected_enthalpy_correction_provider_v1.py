"""Configurable smooth phase-enthalpy correction for a thermo provider."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Sequence

import numpy as np


class ProjectedEnthalpyCorrectionProviderV1:
    """Add phase-specific Chebyshev enthalpy corrections along a projection."""

    def __init__(
        self,
        *,
        base_provider: Any,
        projection: Sequence[float],
        projection_limits: Sequence[float],
        liquid_correction_coefficients_BTU_lbmol: Sequence[Sequence[float]],
        vapor_correction_coefficients_BTU_lbmol: Sequence[Sequence[float]],
        provider_identity: str = "projected-enthalpy-correction",
    ) -> None:
        components = tuple(
            str(value)
            for value in getattr(base_provider, "component_names_excel", ())
        )
        projection_array = np.asarray(projection, dtype=float).reshape((-1,))
        if projection_array.size == 0 or np.any(~np.isfinite(projection_array)):
            raise ValueError("composition projection must be finite and non-empty")
        liquid = np.asarray(liquid_correction_coefficients_BTU_lbmol, dtype=float)
        vapor = np.asarray(vapor_correction_coefficients_BTU_lbmol, dtype=float)
        if (
            liquid.ndim != 2
            or liquid.shape[0] != 1
            or liquid.shape != vapor.shape
            or liquid.shape[1] == 0
            or np.any(~np.isfinite(liquid))
            or np.any(~np.isfinite(vapor))
        ):
            raise ValueError("phase correction arrays must be finite matching rows")
        limits = np.asarray(projection_limits, dtype=float).reshape((-1,))
        if limits.shape != (2,) or np.any(~np.isfinite(limits)) or limits[1] <= limits[0]:
            raise ValueError("projection limits must be two increasing finite values")
        if components and len(components) != projection_array.size:
            raise ValueError("provider component order and projection size disagree")
        identity = str(provider_identity).strip()
        if not identity:
            raise ValueError("provider identity is required")
        self.base_provider = base_provider
        self.projection = projection_array.copy()
        self.projection_limits = (float(limits[0]), float(limits[1]))
        self.liquid_correction_coefficients_BTU_lbmol = liquid[0].copy()
        self.vapor_correction_coefficients_BTU_lbmol = vapor[0].copy()
        self.provider_identity = identity
        self.component_names_excel = list(components)
        self.component_ids_dwsim = list(
            getattr(base_provider, "component_ids_dwsim", components)
        )

    def _coordinate(self, composition: Sequence[float]) -> float:
        values = np.asarray(composition, dtype=float).reshape((-1,))
        if values.shape != self.projection.shape or np.any(~np.isfinite(values)):
            raise ValueError("composition and projection dimensions disagree")
        total = float(np.sum(values))
        if total <= 0.0 or np.any(values < 0.0):
            raise ValueError("composition must be finite and non-negative")
        projected = float(np.dot(values / total, self.projection))
        lower, upper = self.projection_limits
        return 2.0 * (projected - lower) / (upper - lower) - 1.0

    def enthalpy_correction_BTU_lbmol(
        self, phase: str, composition: Sequence[float]
    ) -> float:
        phase_name = str(phase).strip().casefold()
        if phase_name == "liquid":
            coefficients = self.liquid_correction_coefficients_BTU_lbmol
        elif phase_name in {"vapor", "vapour"}:
            coefficients = self.vapor_correction_coefficients_BTU_lbmol
        else:
            raise ValueError(f"unsupported phase {phase!r}")
        result = float(
            np.polynomial.chebyshev.chebval(self._coordinate(composition), coefficients)
        )
        if not np.isfinite(result):
            raise RuntimeError("enthalpy correction is non-finite")
        return result

    def phase_enthalpy_BTU_lbmol(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> float:
        base = float(
            self.base_provider.phase_enthalpy_BTU_lbmol(
                phase, temperature_F, pressure_psia, composition
            )
        )
        result = base + self.enthalpy_correction_BTU_lbmol(phase, composition)
        if not np.isfinite(result):
            raise RuntimeError("corrected phase enthalpy is non-finite")
        return float(result)

    def phase_fugacity_coefficients(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> np.ndarray:
        return np.asarray(
            self.base_provider.phase_fugacity_coefficients(
                phase, temperature_F, pressure_psia, composition
            ),
            dtype=float,
        ).reshape((-1,))

    @contextmanager
    def thermo_call_category(self, category: str | None):
        context = getattr(self.base_provider, "thermo_call_category", None)
        if callable(context):
            with context(category):
                yield
        else:
            yield

    def set_exact_state_memoization(
        self, enabled: bool, *, clear: bool = True
    ) -> None:
        setter = getattr(self.base_provider, "set_exact_state_memoization", None)
        if callable(setter):
            setter(bool(enabled), clear=bool(clear))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_provider, name)


__all__ = ["ProjectedEnthalpyCorrectionProviderV1"]
