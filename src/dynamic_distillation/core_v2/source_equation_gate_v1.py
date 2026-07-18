"""Property-free source-equation assembly for equilibrium-DAE v2 Gate A."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BinarySourceColumnSpec:
    """Generic bottom-to-top constant-relative-volatility source model."""

    n_stages: int = 41
    feed_stage_from_bottom: int = 21
    relative_volatility: float = 1.5
    liquid_hydraulic_tau_min: float = 0.063
    nominal_feed_kmol_min: float = 1.0
    nominal_feed_liquid_fraction: float = 1.0
    nominal_rectifying_liquid_kmol_min: float = 2.70629
    nominal_boilup_kmol_min: float = 3.20629
    liquid_vapor_coupling: float = 0.0
    reflux_kmol_min: float = 2.70629
    boilup_kmol_min: float = 3.20629
    distillate_kmol_min: float = 0.5
    bottoms_kmol_min: float = 0.5
    feed_kmol_min: float = 1.0
    feed_light_mole_fraction: float = 0.5
    feed_liquid_fraction: float = 1.0
    nominal_liquid_holdup_kmol: float = 0.5

    @property
    def nominal_stripping_liquid_kmol_min(self) -> float:
        return (
            self.nominal_rectifying_liquid_kmol_min
            + self.nominal_feed_liquid_fraction
            * self.nominal_feed_kmol_min
        )

    @property
    def nominal_rectifying_vapor_kmol_min(self) -> float:
        return (
            self.nominal_boilup_kmol_min
            + (1.0 - self.nominal_feed_liquid_fraction)
            * self.nominal_feed_kmol_min
        )


@dataclass(frozen=True)
class BinarySourceEvaluation:
    """Rates reconstructed from the source material-balance equations."""

    vapor_light_mole_fraction: np.ndarray
    liquid_downflow_kmol_min: np.ndarray
    vapor_upflow_kmol_min: np.ndarray
    total_holdup_rate_kmol_min: np.ndarray
    light_inventory_rate_kmol_min: np.ndarray
    light_mole_fraction_rate_per_min: np.ndarray

    @property
    def packed_state_rate(self) -> np.ndarray:
        return np.concatenate(
            (
                self.light_mole_fraction_rate_per_min,
                self.total_holdup_rate_kmol_min,
            )
        )


def _validated_state(
    spec: BinarySourceColumnSpec,
    light_mole_fraction: np.ndarray,
    liquid_holdup_kmol: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if int(spec.n_stages) < 3:
        raise ValueError("source-equation gate requires at least three stages")
    if not 1 < int(spec.feed_stage_from_bottom) < int(spec.n_stages):
        raise ValueError("feed stage must be an interior stage")
    if float(spec.relative_volatility) <= 0.0:
        raise ValueError("relative volatility must be positive")
    if float(spec.liquid_hydraulic_tau_min) <= 0.0:
        raise ValueError("liquid hydraulic time constant must be positive")

    n_stages = int(spec.n_stages)
    x = np.asarray(light_mole_fraction, dtype=float).reshape((-1,))
    holdup = np.asarray(liquid_holdup_kmol, dtype=float).reshape((-1,))
    if x.size != n_stages or holdup.size != n_stages:
        raise ValueError(
            f"expected {n_stages} stage values, got {x.size} and "
            f"{holdup.size}"
        )
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(holdup)):
        raise ValueError("source-equation state must be finite")
    if np.any(x < 0.0) or np.any(x > 1.0):
        raise ValueError("source-equation compositions must lie in [0, 1]")
    if np.any(holdup <= 0.0):
        raise ValueError("source-equation liquid holdups must be positive")
    return x, holdup


def evaluate_binary_source_column(
    spec: BinarySourceColumnSpec,
    *,
    light_mole_fraction: np.ndarray,
    liquid_holdup_kmol: np.ndarray,
) -> BinarySourceEvaluation:
    """Evaluate the source material equations without solving or integrating.

    Arrays are ordered from the reboiler at index zero to the total condenser
    at the final index, matching the published source equation convention.
    """

    x, holdup = _validated_state(
        spec,
        light_mole_fraction,
        liquid_holdup_kmol,
    )
    n_stages = int(spec.n_stages)
    feed_index = int(spec.feed_stage_from_bottom) - 1
    alpha = float(spec.relative_volatility)

    vapor_x = alpha * x[:-1] / (1.0 + (alpha - 1.0) * x[:-1])

    vapor = np.full(
        n_stages - 1,
        float(spec.boilup_kmol_min),
        dtype=float,
    )
    vapor[feed_index:] += (
        (1.0 - float(spec.feed_liquid_fraction))
        * float(spec.feed_kmol_min)
    )

    liquid = np.zeros(n_stages, dtype=float)
    nominal_holdup = float(spec.nominal_liquid_holdup_kmol)
    tau = float(spec.liquid_hydraulic_tau_min)
    coupling = float(spec.liquid_vapor_coupling)

    stripping_indices = np.arange(1, feed_index + 1, dtype=int)
    liquid[stripping_indices] = (
        float(spec.nominal_stripping_liquid_kmol_min)
        + (holdup[stripping_indices] - nominal_holdup) / tau
        + coupling
        * (
            vapor[stripping_indices - 1]
            - float(spec.nominal_boilup_kmol_min)
        )
    )

    rectifying_indices = np.arange(
        feed_index + 1,
        n_stages - 1,
        dtype=int,
    )
    liquid[rectifying_indices] = (
        float(spec.nominal_rectifying_liquid_kmol_min)
        + (holdup[rectifying_indices] - nominal_holdup) / tau
        + coupling
        * (
            vapor[rectifying_indices - 1]
            - float(spec.nominal_rectifying_vapor_kmol_min)
        )
    )
    liquid[-1] = float(spec.reflux_kmol_min)

    d_holdup = np.zeros(n_stages, dtype=float)
    d_light = np.zeros(n_stages, dtype=float)
    interior = slice(1, n_stages - 1)
    d_holdup[interior] = (
        liquid[2:]
        - liquid[1:-1]
        + vapor[:-1]
        - vapor[1:]
    )
    d_light[interior] = (
        liquid[2:] * x[2:]
        - liquid[1:-1] * x[1:-1]
        + vapor[:-1] * vapor_x[:-1]
        - vapor[1:] * vapor_x[1:]
    )

    d_holdup[feed_index] += float(spec.feed_kmol_min)
    d_light[feed_index] += (
        float(spec.feed_kmol_min)
        * float(spec.feed_light_mole_fraction)
    )

    d_holdup[0] = (
        liquid[1]
        - vapor[0]
        - float(spec.bottoms_kmol_min)
    )
    d_light[0] = (
        liquid[1] * x[1]
        - vapor[0] * vapor_x[0]
        - float(spec.bottoms_kmol_min) * x[0]
    )

    d_holdup[-1] = (
        vapor[-1]
        - float(spec.reflux_kmol_min)
        - float(spec.distillate_kmol_min)
    )
    d_light[-1] = (
        vapor[-1] * vapor_x[-1]
        - (
            float(spec.reflux_kmol_min)
            + float(spec.distillate_kmol_min)
        )
        * x[-1]
    )

    d_x = (d_light - x * d_holdup) / holdup
    return BinarySourceEvaluation(
        vapor_light_mole_fraction=vapor_x,
        liquid_downflow_kmol_min=liquid,
        vapor_upflow_kmol_min=vapor,
        total_holdup_rate_kmol_min=d_holdup,
        light_inventory_rate_kmol_min=d_light,
        light_mole_fraction_rate_per_min=d_x,
    )
