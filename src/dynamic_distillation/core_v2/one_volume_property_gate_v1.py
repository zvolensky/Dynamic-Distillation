"""One-volume live-property and energy closure for the DD-080 Gate B test."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares


BTU_PER_PSI_FT3 = (6894.7572931783 * 0.028316846592) / 1055.05585262
FRANCIS_C_US = 3.33
SECONDS_PER_HOUR = 3600.0


@dataclass(frozen=True)
class OneVolumeGeometry:
    active_area_ft2: float
    tray_spacing_ft: float
    weir_height_in: float
    weir_length_ft: float
    hydraulic_c_factor: float = 1.0


@dataclass(frozen=True)
class OneVolumeSpec:
    component_names: tuple[str, ...]
    pressure_psia: float
    temperature_reference_F: float
    temperature_scale_F: float
    energy_scale_BTU: float
    geometry: OneVolumeGeometry
    component_mw_lbm_per_lbmol: np.ndarray


@dataclass(frozen=True)
class OneVolumeConservedState:
    component_inventory_lbmol: np.ndarray
    internal_energy_BTU: float


@dataclass(frozen=True)
class OneVolumeClosure:
    temperature_F: float
    liquid_mole_fraction: np.ndarray
    vapor_mole_fraction: np.ndarray
    liquid_moles_lbmol: float
    liquid_enthalpy_BTU_lbmol: float
    liquid_internal_energy_BTU_lbmol: float
    liquid_density_lbmol_ft3: float
    liquid_volume_ft3: float
    liquid_height_ft: float
    over_weir_head_ft: float
    francis_flow_lbmolph: float
    mean_molecular_weight_lbm_lbmol: float
    mass_density_lbm_ft3: float
    phase_fugacity_common_ratio: float
    residual: np.ndarray
    scaled_unknown: np.ndarray
    converged: bool
    iterations: int
    active_bounds: bool = False
    clipping_or_projection_used: bool = False


@dataclass(frozen=True)
class JacobianAudit:
    matrix: np.ndarray
    rank: int
    condition: float
    zero_rows: tuple[int, ...]
    zero_columns: tuple[int, ...]
    step_factor: float


@dataclass(frozen=True)
class OneVolumeBoundary:
    flow_lbmolps: float
    inlet_mole_fraction: np.ndarray
    inlet_enthalpy_BTU_lbmol: float
    heat_duty_BTUps: float


@dataclass(frozen=True)
class OneVolumeIntegrationOptions:
    method: str = "BDF"
    rtol: float = 1.0e-8
    atol: float = 1.0e-10
    max_step_sec: float = 2.0


@dataclass(frozen=True)
class OneVolumeTrajectory:
    time_sec: np.ndarray
    conserved_state: np.ndarray
    cumulative_external_component_lbmol: np.ndarray
    cumulative_external_energy_BTU: np.ndarray
    temperature_F: np.ndarray
    liquid_mole_fraction: np.ndarray
    vapor_mole_fraction: np.ndarray
    algebraic_residual_max: float
    method: str
    nfev: int
    success: bool
    message: str
    clipping_or_projection_used: bool = False


def normalize_composition(values: Sequence[float]) -> np.ndarray:
    composition = np.asarray(values, dtype=float).reshape((-1,))
    total = float(np.sum(composition))
    if (
        composition.size < 2
        or np.any(~np.isfinite(composition))
        or np.any(composition <= 0.0)
        or not np.isfinite(total)
        or total <= 0.0
    ):
        raise ValueError("composition must be finite and strictly positive")
    return composition / total


def reconstruct_liquid_inventory(
    component_inventory_lbmol: Sequence[float],
) -> tuple[float, np.ndarray]:
    inventory = np.asarray(component_inventory_lbmol, dtype=float).reshape((-1,))
    if np.any(~np.isfinite(inventory)) or np.any(inventory <= 0.0):
        raise ValueError("component inventories must be finite and strictly positive")
    liquid_moles = float(np.sum(inventory))
    return liquid_moles, inventory / liquid_moles


def vapor_logits(vapor_mole_fraction: Sequence[float]) -> np.ndarray:
    vapor = normalize_composition(vapor_mole_fraction)
    return np.log(vapor[:-1] / vapor[-1])


def vapor_from_logits(logits: Sequence[float]) -> np.ndarray:
    free = np.asarray(logits, dtype=float).reshape((-1,))
    shifted = np.concatenate((free, np.zeros(1, dtype=float)))
    shifted -= float(np.max(shifted))
    weights = np.exp(shifted)
    return weights / float(np.sum(weights))


def _liquid_properties(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_mole_fraction: np.ndarray,
) -> tuple[float, float, float]:
    enthalpy = float(
        provider.phase_enthalpy_BTU_lbmol(
            "liquid",
            float(temperature_F),
            float(pressure_psia),
            liquid_mole_fraction.tolist(),
        )
    )
    density_raw = provider.liquid_density_lbmol_ft3(
        float(temperature_F),
        float(pressure_psia),
        liquid_mole_fraction.tolist(),
    )
    if density_raw is None:
        raise RuntimeError("live liquid density is unavailable")
    density = float(density_raw)
    if not np.isfinite(density) or density <= 0.0:
        raise RuntimeError("live liquid density is non-physical")
    internal_energy = (
        enthalpy - float(pressure_psia) * (1.0 / density) * BTU_PER_PSI_FT3
    )
    if not np.isfinite(enthalpy) or not np.isfinite(internal_energy):
        raise RuntimeError("live liquid energy property is non-finite")
    return enthalpy, internal_energy, density


def _relative_fugacity_residual(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_mole_fraction: np.ndarray,
    vapor_mole_fraction: np.ndarray,
) -> tuple[np.ndarray, float]:
    phi_liquid = np.asarray(
        provider.phase_fugacity_coefficients(
            "liquid",
            float(temperature_F),
            float(pressure_psia),
            liquid_mole_fraction.tolist(),
        ),
        dtype=float,
    ).reshape(liquid_mole_fraction.shape)
    phi_vapor = np.asarray(
        provider.phase_fugacity_coefficients(
            "vapor",
            float(temperature_F),
            float(pressure_psia),
            vapor_mole_fraction.tolist(),
        ),
        dtype=float,
    ).reshape(vapor_mole_fraction.shape)
    if (
        np.any(~np.isfinite(phi_liquid))
        or np.any(~np.isfinite(phi_vapor))
        or np.any(phi_liquid <= 0.0)
        or np.any(phi_vapor <= 0.0)
    ):
        raise RuntimeError("live fugacity coefficients are non-physical")
    log_ratio = np.log(
        vapor_mole_fraction * phi_vapor / (liquid_mole_fraction * phi_liquid)
    )
    return (
        log_ratio[:-1] - log_ratio[-1],
        float(np.exp(np.mean(log_ratio))),
    )


def evaluate_one_volume_residual(
    spec: OneVolumeSpec,
    state: OneVolumeConservedState,
    provider: Any,
    scaled_unknown: Sequence[float],
) -> tuple[np.ndarray, dict[str, Any]]:
    unknown = np.asarray(scaled_unknown, dtype=float).reshape((-1,))
    expected = len(spec.component_names)
    if unknown.size != expected:
        raise ValueError(f"expected {expected} algebraic unknowns, got {unknown.size}")
    liquid_moles, liquid_x = reconstruct_liquid_inventory(
        state.component_inventory_lbmol
    )
    temperature_F = float(spec.temperature_reference_F) + float(
        spec.temperature_scale_F
    ) * float(unknown[0])
    vapor_y = vapor_from_logits(unknown[1:])
    enthalpy, internal_energy, density = _liquid_properties(
        provider,
        temperature_F=temperature_F,
        pressure_psia=float(spec.pressure_psia),
        liquid_mole_fraction=liquid_x,
    )
    energy_residual = (
        float(state.internal_energy_BTU) - liquid_moles * internal_energy
    ) / float(spec.energy_scale_BTU)
    equilibrium_residual, phase_fugacity_common_ratio = _relative_fugacity_residual(
        provider,
        temperature_F=temperature_F,
        pressure_psia=float(spec.pressure_psia),
        liquid_mole_fraction=liquid_x,
        vapor_mole_fraction=vapor_y,
    )
    residual = np.concatenate(
        (np.asarray([energy_residual], dtype=float), equilibrium_residual)
    )
    return residual, {
        "temperature_F": float(temperature_F),
        "liquid_moles_lbmol": float(liquid_moles),
        "liquid_mole_fraction": liquid_x,
        "vapor_mole_fraction": vapor_y,
        "liquid_enthalpy_BTU_lbmol": float(enthalpy),
        "liquid_internal_energy_BTU_lbmol": float(internal_energy),
        "liquid_density_lbmol_ft3": float(density),
        "phase_fugacity_common_ratio": float(phase_fugacity_common_ratio),
    }


def solve_one_volume_closure(
    spec: OneVolumeSpec,
    state: OneVolumeConservedState,
    provider: Any,
    *,
    initial_temperature_F: float | None = None,
    initial_vapor_mole_fraction: Sequence[float] | None = None,
    max_nfev: int = 100,
) -> OneVolumeClosure:
    component_count = len(spec.component_names)
    if (
        component_count
        != np.asarray(
            state.component_inventory_lbmol,
            dtype=float,
        ).size
    ):
        raise ValueError("component inventory size does not match spec")
    temperature_guess = (
        float(spec.temperature_reference_F)
        if initial_temperature_F is None
        else float(initial_temperature_F)
    )
    vapor_guess = (
        np.full(component_count, 1.0 / component_count, dtype=float)
        if initial_vapor_mole_fraction is None
        else normalize_composition(initial_vapor_mole_fraction)
    )
    initial = np.concatenate(
        (
            np.asarray(
                [
                    (temperature_guess - float(spec.temperature_reference_F))
                    / float(spec.temperature_scale_F)
                ],
                dtype=float,
            ),
            vapor_logits(vapor_guess),
        )
    )
    solution = least_squares(
        lambda unknown: evaluate_one_volume_residual(
            spec,
            state,
            provider,
            unknown,
        )[0],
        initial,
        method="trf",
        jac="3-point",
        x_scale="jac",
        ftol=1.0e-12,
        xtol=1.0e-12,
        gtol=1.0e-12,
        max_nfev=int(max_nfev),
    )
    residual, values = evaluate_one_volume_residual(
        spec,
        state,
        provider,
        solution.x,
    )
    geometry = spec.geometry
    liquid_moles = float(values["liquid_moles_lbmol"])
    density = float(values["liquid_density_lbmol_ft3"])
    liquid_volume = liquid_moles / density
    liquid_height = liquid_volume / float(geometry.active_area_ft2)
    over_weir_head = max(
        liquid_height - float(geometry.weir_height_in) / 12.0,
        0.0,
    )
    volumetric_flow_ft3_s = (
        FRANCIS_C_US
        * float(geometry.hydraulic_c_factor)
        * float(geometry.weir_length_ft)
        * over_weir_head**1.5
    )
    francis_flow = volumetric_flow_ft3_s * density * SECONDS_PER_HOUR
    liquid_x = np.asarray(values["liquid_mole_fraction"], dtype=float)
    mean_mw = float(np.dot(liquid_x, spec.component_mw_lbm_per_lbmol))
    converged = bool(solution.success and np.max(np.abs(residual)) < 1.0e-9)
    return OneVolumeClosure(
        temperature_F=float(values["temperature_F"]),
        liquid_mole_fraction=liquid_x.copy(),
        vapor_mole_fraction=np.asarray(
            values["vapor_mole_fraction"],
            dtype=float,
        ).copy(),
        liquid_moles_lbmol=liquid_moles,
        liquid_enthalpy_BTU_lbmol=float(values["liquid_enthalpy_BTU_lbmol"]),
        liquid_internal_energy_BTU_lbmol=float(
            values["liquid_internal_energy_BTU_lbmol"]
        ),
        liquid_density_lbmol_ft3=density,
        liquid_volume_ft3=float(liquid_volume),
        liquid_height_ft=float(liquid_height),
        over_weir_head_ft=float(over_weir_head),
        francis_flow_lbmolph=float(francis_flow),
        mean_molecular_weight_lbm_lbmol=mean_mw,
        mass_density_lbm_ft3=float(density * mean_mw),
        phase_fugacity_common_ratio=float(values["phase_fugacity_common_ratio"]),
        residual=np.asarray(residual, dtype=float),
        scaled_unknown=np.asarray(solution.x, dtype=float),
        converged=converged,
        iterations=int(solution.nfev),
    )


def audit_one_volume_jacobian(
    spec: OneVolumeSpec,
    state: OneVolumeConservedState,
    provider: Any,
    scaled_unknown: Sequence[float],
    *,
    step_factor: float,
) -> JacobianAudit:
    point = np.asarray(scaled_unknown, dtype=float).reshape((-1,))
    step = float(step_factor) * 1.0e-5
    matrix = np.zeros((point.size, point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros(point.size, dtype=float)
        delta[column] = step
        plus = evaluate_one_volume_residual(
            spec,
            state,
            provider,
            point + delta,
        )[0]
        minus = evaluate_one_volume_residual(
            spec,
            state,
            provider,
            point - delta,
        )[0]
        matrix[:, column] = (plus - minus) / (2.0 * step)
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * max(float(singular[0]), 1.0)
    rank = int(np.sum(singular > tolerance))
    condition = (
        float(singular[0] / singular[-1]) if singular[-1] > 0.0 else float("inf")
    )
    row_norm = np.linalg.norm(matrix, axis=1)
    column_norm = np.linalg.norm(matrix, axis=0)
    return JacobianAudit(
        matrix=matrix,
        rank=rank,
        condition=condition,
        zero_rows=tuple(int(i) for i in np.where(row_norm <= 1.0e-12)[0]),
        zero_columns=tuple(int(i) for i in np.where(column_norm <= 1.0e-12)[0]),
        step_factor=float(step_factor),
    )


def _one_volume_augmented_rhs(
    _time_sec: float,
    augmented_state: np.ndarray,
    *,
    spec: OneVolumeSpec,
    provider: Any,
    boundary: OneVolumeBoundary,
    initial_vapor_mole_fraction: np.ndarray,
) -> np.ndarray:
    component_count = len(spec.component_names)
    inventory = np.asarray(
        augmented_state[:component_count],
        dtype=float,
    )
    internal_energy = float(augmented_state[component_count])
    closure = solve_one_volume_closure(
        spec,
        OneVolumeConservedState(inventory, internal_energy),
        provider,
        initial_vapor_mole_fraction=initial_vapor_mole_fraction,
    )
    if not closure.converged:
        raise RuntimeError("one-volume algebraic closure failed during integration")
    flow = float(boundary.flow_lbmolps)
    component_rate = flow * (
        np.asarray(boundary.inlet_mole_fraction, dtype=float)
        - closure.liquid_mole_fraction
    )
    energy_rate = flow * (
        float(boundary.inlet_enthalpy_BTU_lbmol)
        - float(closure.liquid_enthalpy_BTU_lbmol)
    ) + float(boundary.heat_duty_BTUps)
    external = np.concatenate((component_rate, np.asarray([energy_rate], dtype=float)))
    return np.concatenate((external, external))


def integrate_one_volume(
    *,
    spec: OneVolumeSpec,
    initial_state: OneVolumeConservedState,
    provider: Any,
    boundary: OneVolumeBoundary,
    initial_vapor_mole_fraction: Sequence[float],
    time_sec: Sequence[float],
    options: OneVolumeIntegrationOptions,
) -> OneVolumeTrajectory:
    times = np.asarray(time_sec, dtype=float).reshape((-1,))
    if times.size < 2 or np.any(~np.isfinite(times)) or np.any(np.diff(times) <= 0.0):
        raise ValueError("time_sec must be finite and strictly increasing")
    component_count = len(spec.component_names)
    initial_conserved = np.concatenate(
        (
            np.asarray(
                initial_state.component_inventory_lbmol,
                dtype=float,
            ),
            np.asarray([initial_state.internal_energy_BTU], dtype=float),
        )
    )
    augmented_initial = np.concatenate(
        (initial_conserved, np.zeros_like(initial_conserved))
    )
    vapor_guess = normalize_composition(initial_vapor_mole_fraction)
    solution = solve_ivp(
        fun=lambda time, state: _one_volume_augmented_rhs(
            time,
            state,
            spec=spec,
            provider=provider,
            boundary=boundary,
            initial_vapor_mole_fraction=vapor_guess,
        ),
        t_span=(float(times[0]), float(times[-1])),
        y0=augmented_initial,
        method=str(options.method),
        t_eval=times,
        rtol=float(options.rtol),
        atol=float(options.atol),
        max_step=float(options.max_step_sec),
        vectorized=False,
    )
    if not solution.success:
        raise RuntimeError(
            f"{options.method} one-volume integration failed: {solution.message}"
        )
    conserved = np.asarray(
        solution.y[: component_count + 1, :].T,
        dtype=float,
    )
    cumulative = np.asarray(
        solution.y[component_count + 1 :, :].T,
        dtype=float,
    )
    temperatures: list[float] = []
    liquid_compositions: list[np.ndarray] = []
    vapor_compositions: list[np.ndarray] = []
    residual_max = 0.0
    output_guess = vapor_guess
    for row in conserved:
        closure = solve_one_volume_closure(
            spec,
            OneVolumeConservedState(
                row[:component_count],
                float(row[component_count]),
            ),
            provider,
            initial_vapor_mole_fraction=output_guess,
        )
        if not closure.converged:
            raise RuntimeError(
                "one-volume algebraic closure failed at accepted output state"
            )
        output_guess = closure.vapor_mole_fraction
        temperatures.append(float(closure.temperature_F))
        liquid_compositions.append(closure.liquid_mole_fraction)
        vapor_compositions.append(closure.vapor_mole_fraction)
        residual_max = max(
            residual_max,
            float(np.max(np.abs(closure.residual))),
        )
    return OneVolumeTrajectory(
        time_sec=np.asarray(solution.t, dtype=float),
        conserved_state=conserved,
        cumulative_external_component_lbmol=cumulative[:, :component_count],
        cumulative_external_energy_BTU=cumulative[:, component_count],
        temperature_F=np.asarray(temperatures, dtype=float),
        liquid_mole_fraction=np.asarray(liquid_compositions, dtype=float),
        vapor_mole_fraction=np.asarray(vapor_compositions, dtype=float),
        algebraic_residual_max=float(residual_max),
        method=str(options.method),
        nfev=int(solution.nfev),
        success=bool(solution.success),
        message=str(solution.message),
    )
