"""Configurable smooth log-fugacity correction for a thermodynamic provider."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Sequence

import numpy as np


class ProjectedFugacityCorrectionProviderV1:
    """Apply component-wise Chebyshev corrections along a composition projection.

    The adapter is deliberately component-agnostic.  A case supplies a projection
    vector and coefficient arrays; the simulator core neither identifies nor
    special-cases any chemical species.
    """

    def __init__(
        self,
        *,
        base_provider: Any,
        projection: Sequence[float],
        projection_limits: Sequence[float],
        liquid_log_coefficients: Sequence[Sequence[float]],
        vapor_log_coefficients: Sequence[Sequence[float]] | None = None,
        provider_identity: str = "projected-fugacity-correction",
    ) -> None:
        components = tuple(
            str(value)
            for value in getattr(base_provider, "component_names_excel", ())
        )
        projection_array = np.asarray(projection, dtype=float).reshape((-1,))
        liquid = np.asarray(liquid_log_coefficients, dtype=float)
        if projection_array.size == 0 or np.any(~np.isfinite(projection_array)):
            raise ValueError("composition projection must be finite and non-empty")
        if liquid.ndim != 2 or liquid.shape[0] != projection_array.size:
            raise ValueError(
                "liquid correction rows must match the composition dimension"
            )
        if liquid.shape[1] == 0 or np.any(~np.isfinite(liquid)):
            raise ValueError("liquid correction coefficients must be finite")
        if vapor_log_coefficients is None:
            vapor = np.zeros_like(liquid)
        else:
            vapor = np.asarray(vapor_log_coefficients, dtype=float)
            if vapor.shape != liquid.shape or np.any(~np.isfinite(vapor)):
                raise ValueError(
                    "vapor correction coefficients must match the liquid array"
                )
        limits = np.asarray(projection_limits, dtype=float).reshape((-1,))
        if limits.shape != (2,) or np.any(~np.isfinite(limits)) or limits[1] <= limits[0]:
            raise ValueError("projection limits must be two increasing finite values")
        identity = str(provider_identity).strip()
        if not identity:
            raise ValueError("provider identity is required")
        if components and len(components) != projection_array.size:
            raise ValueError("provider component order and projection size disagree")

        self.base_provider = base_provider
        self.projection = projection_array.copy()
        self.projection_limits = (float(limits[0]), float(limits[1]))
        self.liquid_log_coefficients = liquid.copy()
        self.vapor_log_coefficients = vapor.copy()
        self.provider_identity = identity
        self.component_names_excel = list(components)
        self.component_ids_dwsim = list(
            getattr(base_provider, "component_ids_dwsim", components)
        )

    def _normalized_projection(self, composition: Sequence[float]) -> float:
        values = np.asarray(composition, dtype=float).reshape((-1,))
        if values.shape != self.projection.shape or np.any(~np.isfinite(values)):
            raise ValueError("composition and projection dimensions disagree")
        total = float(np.sum(values))
        if total <= 0.0 or np.any(values < 0.0):
            raise ValueError("composition must be finite and non-negative")
        coordinate = float(np.dot(values / total, self.projection))
        lower, upper = self.projection_limits
        return 2.0 * (coordinate - lower) / (upper - lower) - 1.0

    def log_fugacity_correction(
        self, phase: str, composition: Sequence[float]
    ) -> np.ndarray:
        normalized = self._normalized_projection(composition)
        phase_name = str(phase).strip().casefold()
        if phase_name == "liquid":
            coefficients = self.liquid_log_coefficients
        elif phase_name in {"vapor", "vapour"}:
            coefficients = self.vapor_log_coefficients
        else:
            raise ValueError(f"unsupported phase {phase!r}")
        values = np.asarray(
            [
                np.polynomial.chebyshev.chebval(normalized, row)
                for row in coefficients
            ],
            dtype=float,
        )
        if np.any(~np.isfinite(values)):
            raise RuntimeError("log-fugacity correction is non-finite")
        return values

    def phase_fugacity_coefficients(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> np.ndarray:
        base = np.asarray(
            self.base_provider.phase_fugacity_coefficients(
                phase, temperature_F, pressure_psia, composition
            ),
            dtype=float,
        ).reshape((-1,))
        correction = self.log_fugacity_correction(phase, composition)
        if base.shape != correction.shape or np.any(base <= 0.0):
            raise RuntimeError("base fugacity coefficients are incompatible")
        corrected = base * np.exp(correction)
        if np.any(~np.isfinite(corrected)) or np.any(corrected <= 0.0):
            raise RuntimeError("corrected fugacity coefficients are non-physical")
        return corrected

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


__all__ = ["ProjectedFugacityCorrectionProviderV1"]
