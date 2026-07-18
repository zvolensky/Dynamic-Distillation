"""Bounded dynamic wrapper for the property-free DD-079 Gate A model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

from dynamic_distillation.core_v2.source_equation_gate_v1 import (
    BinarySourceColumnSpec,
    evaluate_binary_source_column,
)


@dataclass(frozen=True)
class SourceIntegrationOptions:
    method: str = "BDF"
    rtol: float = 1.0e-10
    atol: float = 1.0e-12
    max_step_min: float = 1.0


@dataclass(frozen=True)
class SourceFeedSchedule:
    step_time_min: float
    feed_before_kmol_min: float
    feed_after_kmol_min: float

    def feed_at(self, time_min: float) -> float:
        if float(time_min) < float(self.step_time_min):
            return float(self.feed_before_kmol_min)
        return float(self.feed_after_kmol_min)


@dataclass(frozen=True)
class SourceTrajectory:
    time_min: np.ndarray
    packed_state: np.ndarray
    cumulative_external_total_kmol: np.ndarray
    cumulative_external_light_kmol: np.ndarray
    method: str
    nfev: int
    success: bool
    message: str
    feed_step_time_min: float | None
    safeguard_activated: bool = False

    @property
    def n_stages(self) -> int:
        return int(self.packed_state.shape[1] // 2)

    @property
    def light_mole_fraction(self) -> np.ndarray:
        return np.asarray(
            self.packed_state[:, : self.n_stages],
            dtype=float,
        )

    @property
    def liquid_holdup_kmol(self) -> np.ndarray:
        return np.asarray(
            self.packed_state[:, self.n_stages :],
            dtype=float,
        )


def pack_source_state(
    light_mole_fraction: np.ndarray,
    liquid_holdup_kmol: np.ndarray,
) -> np.ndarray:
    x = np.asarray(light_mole_fraction, dtype=float).reshape((-1,))
    holdup = np.asarray(liquid_holdup_kmol, dtype=float).reshape((-1,))
    if x.size != holdup.size:
        raise ValueError("composition and holdup stage counts must match")
    return np.concatenate((x, holdup))


def unpack_source_state(
    packed_state: np.ndarray,
    *,
    n_stages: int,
) -> tuple[np.ndarray, np.ndarray]:
    state = np.asarray(packed_state, dtype=float).reshape((-1,))
    if state.size != 2 * int(n_stages):
        raise ValueError(
            f"expected packed state size {2 * int(n_stages)}, "
            f"got {state.size}"
        )
    return (
        np.asarray(state[:n_stages], dtype=float),
        np.asarray(state[n_stages:], dtype=float),
    )


def external_material_rates(
    spec: BinarySourceColumnSpec,
    light_mole_fraction: np.ndarray,
) -> tuple[float, float]:
    x = np.asarray(light_mole_fraction, dtype=float).reshape((-1,))
    if x.size != int(spec.n_stages):
        raise ValueError("terminal composition stage count mismatch")
    total_rate = (
        float(spec.feed_kmol_min)
        - float(spec.distillate_kmol_min)
        - float(spec.bottoms_kmol_min)
    )
    light_rate = (
        float(spec.feed_kmol_min)
        * float(spec.feed_light_mole_fraction)
        - float(spec.distillate_kmol_min) * float(x[-1])
        - float(spec.bottoms_kmol_min) * float(x[0])
    )
    return float(total_rate), float(light_rate)


def core_v2_augmented_rhs(
    _time_min: float,
    augmented_state: np.ndarray,
    spec: BinarySourceColumnSpec,
) -> np.ndarray:
    n_stages = int(spec.n_stages)
    augmented = np.asarray(augmented_state, dtype=float).reshape((-1,))
    if augmented.size != 2 * n_stages + 2:
        raise ValueError("augmented source state size mismatch")
    x, holdup = unpack_source_state(
        augmented[: 2 * n_stages],
        n_stages=n_stages,
    )
    evaluation = evaluate_binary_source_column(
        spec,
        light_mole_fraction=x,
        liquid_holdup_kmol=holdup,
    )
    external_total, external_light = external_material_rates(spec, x)
    return np.concatenate(
        (
            evaluation.packed_state_rate,
            np.asarray([external_total, external_light], dtype=float),
        )
    )


def _validated_output_grid(time_min: np.ndarray) -> np.ndarray:
    times = np.asarray(time_min, dtype=float).reshape((-1,))
    if times.size < 2:
        raise ValueError("integration requires at least two output times")
    if not np.all(np.isfinite(times)):
        raise ValueError("output times must be finite")
    if np.any(np.diff(times) <= 0.0):
        raise ValueError("output times must be strictly increasing")
    return times


def _integration_segments(
    *,
    start: float,
    stop: float,
    base_spec: BinarySourceColumnSpec,
    feed_schedule: SourceFeedSchedule | None,
) -> tuple[tuple[float, float, BinarySourceColumnSpec], ...]:
    if feed_schedule is None:
        return ((start, stop, base_spec),)
    step = float(feed_schedule.step_time_min)
    before = replace(
        base_spec,
        feed_kmol_min=float(feed_schedule.feed_before_kmol_min),
    )
    after = replace(
        base_spec,
        feed_kmol_min=float(feed_schedule.feed_after_kmol_min),
    )
    if step <= start:
        return ((start, stop, after),)
    if step >= stop:
        return ((start, stop, before),)
    return (
        (start, step, before),
        (step, stop, after),
    )


def integrate_source_trajectory(
    *,
    base_spec: BinarySourceColumnSpec,
    initial_packed_state: np.ndarray,
    time_min: np.ndarray,
    options: SourceIntegrationOptions = SourceIntegrationOptions(),
    feed_schedule: SourceFeedSchedule | None = None,
    augmented_rhs: Callable[
        [float, np.ndarray, BinarySourceColumnSpec],
        np.ndarray,
    ] = core_v2_augmented_rhs,
) -> SourceTrajectory:
    """Integrate exact schedule segments without clipping or projection."""

    times = _validated_output_grid(time_min)
    n_stages = int(base_spec.n_stages)
    initial = np.asarray(initial_packed_state, dtype=float).reshape((-1,))
    x0, holdup0 = unpack_source_state(initial, n_stages=n_stages)
    evaluate_binary_source_column(
        base_spec,
        light_mole_fraction=x0,
        liquid_holdup_kmol=holdup0,
    )
    augmented = np.concatenate((initial, np.zeros(2, dtype=float)))

    stored_times: list[float] = []
    stored_states: list[np.ndarray] = []
    nfev = 0
    message = ""
    segments = _integration_segments(
        start=float(times[0]),
        stop=float(times[-1]),
        base_spec=base_spec,
        feed_schedule=feed_schedule,
    )
    for segment_index, (start, stop, segment_spec) in enumerate(segments):
        if segment_index == 0:
            requested = times[(times >= start) & (times <= stop)]
        else:
            requested = times[(times > start) & (times <= stop)]
        solver_times = np.unique(
            np.concatenate((requested, np.asarray([stop], dtype=float)))
        )
        solution = solve_ivp(
            fun=lambda time, state: augmented_rhs(
                time,
                state,
                segment_spec,
            ),
            t_span=(float(start), float(stop)),
            y0=augmented,
            method=str(options.method),
            t_eval=solver_times,
            rtol=float(options.rtol),
            atol=float(options.atol),
            max_step=float(options.max_step_min),
            vectorized=False,
        )
        nfev += int(solution.nfev)
        message = str(solution.message)
        if not solution.success:
            raise RuntimeError(
                f"{options.method} source integration failed: "
                f"{solution.message}"
            )
        augmented = np.asarray(solution.y[:, -1], dtype=float)
        for requested_time in requested:
            index = int(
                np.argmin(
                    np.abs(
                        np.asarray(solution.t, dtype=float)
                        - float(requested_time)
                    )
                )
            )
            if (
                abs(float(solution.t[index]) - float(requested_time))
                > 1.0e-10
            ):
                raise RuntimeError("solver output grid does not match request")
            stored_times.append(float(requested_time))
            stored_states.append(
                np.asarray(solution.y[:, index], dtype=float).copy()
            )

    output_time = np.asarray(stored_times, dtype=float)
    output = np.asarray(stored_states, dtype=float)
    if output_time.size != times.size or not np.allclose(
        output_time,
        times,
        rtol=0.0,
        atol=1.0e-12,
    ):
        raise RuntimeError("piecewise integration did not preserve output grid")

    packed = np.asarray(output[:, : 2 * n_stages], dtype=float)
    x = packed[:, :n_stages]
    holdup = packed[:, n_stages:]
    if (
        not np.all(np.isfinite(packed))
        or np.any(x < 0.0)
        or np.any(x > 1.0)
        or np.any(holdup <= 0.0)
    ):
        raise RuntimeError(
            "source trajectory left the physical domain; no repair applied"
        )

    return SourceTrajectory(
        time_min=output_time,
        packed_state=packed,
        cumulative_external_total_kmol=np.asarray(
            output[:, 2 * n_stages],
            dtype=float,
        ),
        cumulative_external_light_kmol=np.asarray(
            output[:, 2 * n_stages + 1],
            dtype=float,
        ),
        method=str(options.method),
        nfev=nfev,
        success=True,
        message=message,
        feed_step_time_min=(
            None
            if feed_schedule is None
            else float(feed_schedule.step_time_min)
        ),
        safeguard_activated=False,
    )
