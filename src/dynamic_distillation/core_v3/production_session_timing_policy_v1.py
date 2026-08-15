"""Explicit performance accounting for reusable Core V3 production sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from .terminal_inventory_control_bdf2_session_v1 import (
    ProductionSessionSegmentEvidence,
    ProductionSessionTiming,
)


@dataclass(frozen=True)
class ProductionSegmentTimingLimit:
    name: str
    maximum_wall_seconds: float

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("production segment timing limit needs a name")
        if not np.isfinite(self.maximum_wall_seconds) or self.maximum_wall_seconds <= 0:
            raise ValueError("production segment wall limit must be positive")


@dataclass(frozen=True)
class ProductionSessionTimingLimits:
    segment_limits: tuple[ProductionSegmentTimingLimit, ...]
    maximum_startup_wall_seconds: float
    maximum_active_wall_seconds: float
    maximum_shutdown_wall_seconds: float
    maximum_total_wall_seconds: float
    maximum_unattributed_wall_seconds: float
    identity_tolerance_seconds: float = 1.0e-9

    def __post_init__(self) -> None:
        if not self.segment_limits:
            raise ValueError("production timing policy needs at least one segment")
        names = tuple(str(item.name).strip() for item in self.segment_limits)
        if len(set(names)) != len(names):
            raise ValueError("production segment timing-limit names must be unique")
        positive = (
            self.maximum_startup_wall_seconds,
            self.maximum_active_wall_seconds,
            self.maximum_shutdown_wall_seconds,
            self.maximum_total_wall_seconds,
        )
        if any(not np.isfinite(value) or value <= 0 for value in positive):
            raise ValueError("production session wall limits must be positive")
        nonnegative = (
            self.maximum_unattributed_wall_seconds,
            self.identity_tolerance_seconds,
        )
        if any(not np.isfinite(value) or value < 0 for value in nonnegative):
            raise ValueError(
                "production timing overhead and identity tolerance must be nonnegative"
            )


@dataclass(frozen=True)
class ProductionSegmentTimingAssessment:
    name: str
    observed_wall_seconds: float
    maximum_wall_seconds: float
    completed_without_exception: bool
    pass_gate: bool


@dataclass(frozen=True)
class ProductionSessionTimingAssessment:
    segment_assessments: tuple[ProductionSegmentTimingAssessment, ...]
    observed_active_wall_seconds: float
    observed_unattributed_wall_seconds: float
    observed_values_pass: bool
    segment_contract_pass: bool
    segments_pass: bool
    active_identity_pass: bool
    active_wall_pass: bool
    startup_wall_pass: bool
    shutdown_present_pass: bool
    shutdown_wall_pass: bool
    total_present_pass: bool
    total_wall_pass: bool
    attribution_identity_pass: bool

    @property
    def gates(self) -> Mapping[str, bool]:
        return {
            "observed_values": self.observed_values_pass,
            "segment_contract": self.segment_contract_pass,
            "segments": self.segments_pass,
            "active_identity": self.active_identity_pass,
            "active_wall": self.active_wall_pass,
            "startup_wall": self.startup_wall_pass,
            "shutdown_present": self.shutdown_present_pass,
            "shutdown_wall": self.shutdown_wall_pass,
            "total_present": self.total_present_pass,
            "total_wall": self.total_wall_pass,
            "attribution_identity": self.attribution_identity_pass,
        }

    @property
    def pass_gate(self) -> bool:
        return all(self.gates.values())


def assess_production_session_timing(
    timing: ProductionSessionTiming,
    segments: Sequence[ProductionSessionSegmentEvidence],
    limits: ProductionSessionTimingLimits,
) -> ProductionSessionTimingAssessment:
    """Assess active and complete-session performance without hiding overhead."""
    evidence = tuple(segments)
    expected_names = tuple(item.name for item in limits.segment_limits)
    observed_names = tuple(item.name for item in evidence)
    segment_contract_pass = observed_names == expected_names
    limit_by_name = {item.name: item for item in limits.segment_limits}
    segment_assessments = tuple(
        ProductionSegmentTimingAssessment(
            name=item.name,
            observed_wall_seconds=float(item.wall_seconds),
            maximum_wall_seconds=float(
                limit_by_name[item.name].maximum_wall_seconds
                if item.name in limit_by_name
                else float("nan")
            ),
            completed_without_exception=bool(item.completed_without_exception),
            pass_gate=(
                item.name in limit_by_name
                and np.isfinite(item.wall_seconds)
                and item.wall_seconds >= 0.0
                and item.wall_seconds <= limit_by_name[item.name].maximum_wall_seconds
                and bool(item.completed_without_exception)
            ),
        )
        for item in evidence
    )
    observed_active = float(sum(item.wall_seconds for item in evidence))
    shutdown = timing.shutdown_wall_seconds
    total = timing.total_wall_seconds
    values = [
        timing.startup_wall_seconds,
        timing.trajectory_wall_seconds,
        observed_active,
        *(item.wall_seconds for item in evidence),
    ]
    if shutdown is not None:
        values.append(shutdown)
    if total is not None:
        values.append(total)
    observed_values_pass = all(np.isfinite(value) and value >= 0.0 for value in values)
    active_identity_pass = bool(
        np.isfinite(observed_active)
        and np.isfinite(timing.trajectory_wall_seconds)
        and abs(observed_active - timing.trajectory_wall_seconds)
        <= limits.identity_tolerance_seconds
    )
    shutdown_present_pass = shutdown is not None
    total_present_pass = total is not None
    attributed = float("nan")
    unattributed = float("nan")
    if shutdown is not None and total is not None:
        attributed = (
            float(timing.startup_wall_seconds) + observed_active + float(shutdown)
        )
        unattributed = float(total) - attributed
    attribution_identity_pass = bool(
        np.isfinite(unattributed)
        and unattributed >= -limits.identity_tolerance_seconds
        and unattributed <= limits.maximum_unattributed_wall_seconds
    )
    return ProductionSessionTimingAssessment(
        segment_assessments=segment_assessments,
        observed_active_wall_seconds=observed_active,
        observed_unattributed_wall_seconds=unattributed,
        observed_values_pass=observed_values_pass,
        segment_contract_pass=segment_contract_pass,
        segments_pass=(
            len(segment_assessments) == len(limits.segment_limits)
            and all(item.pass_gate for item in segment_assessments)
        ),
        active_identity_pass=active_identity_pass,
        active_wall_pass=(
            np.isfinite(observed_active)
            and observed_active <= limits.maximum_active_wall_seconds
        ),
        startup_wall_pass=(
            np.isfinite(timing.startup_wall_seconds)
            and timing.startup_wall_seconds <= limits.maximum_startup_wall_seconds
        ),
        shutdown_present_pass=shutdown_present_pass,
        shutdown_wall_pass=(
            shutdown is not None
            and np.isfinite(shutdown)
            and shutdown <= limits.maximum_shutdown_wall_seconds
        ),
        total_present_pass=total_present_pass,
        total_wall_pass=(
            total is not None
            and np.isfinite(total)
            and total <= limits.maximum_total_wall_seconds
        ),
        attribution_identity_pass=attribution_identity_pass,
    )


__all__ = [
    "ProductionSegmentTimingAssessment",
    "ProductionSegmentTimingLimit",
    "ProductionSessionTimingAssessment",
    "ProductionSessionTimingLimits",
    "assess_production_session_timing",
]
