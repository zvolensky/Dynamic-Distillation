"""Live 40 x 40 numerical gate for the DD-086 condenser architecture."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v2.condenser_phase_stability_v1 import (
    rachford_rice_vapor_fraction,
)
from dynamic_distillation.core_v2.condenser_saturated_liquid_registry_v1 import (
    build_condenser_saturated_liquid_registry,
)
from dynamic_distillation.core_v2.energy_owned_vapor_numerical_gate_v1 import (
    EnergyOwnedOperatingSpec,
    EnergyOwnedReference,
    ResidualEvaluation,
    ResidualRow,
    coordinate_layout as base_coordinate_layout,
    decode_coordinates as decode_base_coordinates,
    evaluate_residual as evaluate_base_residual,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
    vapor_from_logits,
    vapor_logits,
)


@dataclass(frozen=True)
class CondenserNumericalReference:
    base: EnergyOwnedReference
    bubble_vapor_mole_fraction: np.ndarray
    condenser_duty_reference_BTUph: float
    condenser_duty_scale_BTUph: float


@dataclass(frozen=True)
class CondenserCoordinateLayout:
    names: tuple[str, ...]
    base: slice
    bubble_logits: slice
    condenser_duty: int


@dataclass(frozen=True)
class CondenserNumericalState:
    bubble_vapor_mole_fraction: np.ndarray
    condenser_duty_BTUph: float


@dataclass(frozen=True)
class CondenserResidualEvaluation:
    raw: np.ndarray
    scaled: np.ndarray
    scales: np.ndarray
    rows: tuple[ResidualRow, ...]
    base: ResidualEvaluation
    condenser: CondenserNumericalState


@dataclass(frozen=True)
class CondenserJacobianAudit:
    step: float
    matrix: np.ndarray
    rank: int
    condition: float
    singular_values: np.ndarray
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    unexpected_couplings: tuple[str, ...]
    bubble_matrix: np.ndarray
    bubble_rank: int
    bubble_singular_values: np.ndarray
    bubble_zero_rows: tuple[str, ...]
    bubble_zero_columns: tuple[str, ...]


@dataclass(frozen=True)
class BubbleSeedSettings:
    method: str = "trf"
    jacobian_step: float = 1.0e-5
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 100
    temperature_min_F: float = 80.0
    temperature_max_F: float = 260.0
    temperature_scale_F: float = 100.0


@dataclass(frozen=True)
class BubbleSeedResult:
    temperature_F: float
    vapor_mole_fraction: np.ndarray
    scaled_coordinates: np.ndarray
    residual: np.ndarray
    residual_inf_norm: float
    success: bool
    status: int
    message: str
    nfev: int
    njev: int | None


def coordinate_layout(
    spec: EnergyOwnedOperatingSpec,
) -> CondenserCoordinateLayout:
    base = base_coordinate_layout(spec)
    names = list(base.names)
    base_slice = slice(0, len(names))
    start = len(names)
    names.extend(
        f"y_bubble_logit[reflux_drum,{component}]"
        for component in spec.component_names[:-1]
    )
    bubble = slice(start, len(names))
    condenser_duty = len(names)
    names.append("q_Q_C")
    if len(names) != 10 * len(spec.component_names) + 10:
        raise RuntimeError("DD-087 coordinate count is inconsistent")
    return CondenserCoordinateLayout(
        names=tuple(names),
        base=base_slice,
        bubble_logits=bubble,
        condenser_duty=condenser_duty,
    )


def decode_coordinates(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    coordinates: Sequence[float],
) -> tuple[Any, CondenserNumericalState]:
    layout = coordinate_layout(spec)
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    if point.size != len(layout.names):
        raise ValueError(f"expected {len(layout.names)} coordinates, got {point.size}")
    base_state = decode_base_coordinates(
        spec,
        reference.base,
        point[layout.base],
    )
    bubble_y = vapor_from_logits(
        vapor_logits(reference.bubble_vapor_mole_fraction)
        + point[layout.bubble_logits]
    )
    condenser_duty = float(reference.condenser_duty_reference_BTUph) + (
        float(reference.condenser_duty_scale_BTUph)
        * float(point[layout.condenser_duty])
    )
    return (
        base_state,
        CondenserNumericalState(
            bubble_vapor_mole_fraction=bubble_y,
            condenser_duty_BTUph=condenser_duty,
        ),
    )


def _fugacity_residual(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: Sequence[float],
    vapor_y: Sequence[float],
) -> np.ndarray:
    x = normalize_composition(liquid_x)
    y = normalize_composition(vapor_y)
    phi_liquid = np.asarray(
        provider.phase_fugacity_coefficients(
            "liquid",
            float(temperature_F),
            float(pressure_psia),
            x.tolist(),
        ),
        dtype=float,
    ).reshape(x.shape)
    phi_vapor = np.asarray(
        provider.phase_fugacity_coefficients(
            "vapor",
            float(temperature_F),
            float(pressure_psia),
            y.tolist(),
        ),
        dtype=float,
    ).reshape(y.shape)
    if (
        np.any(~np.isfinite(phi_liquid))
        or np.any(~np.isfinite(phi_vapor))
        or np.any(phi_liquid <= 0.0)
        or np.any(phi_vapor <= 0.0)
    ):
        raise RuntimeError("non-physical condenser fugacity coefficients")
    return np.log(y * phi_vapor / (x * phi_liquid))


def residual_rows(
    spec: EnergyOwnedOperatingSpec,
    base_rows: Sequence[ResidualRow],
) -> tuple[ResidualRow, ...]:
    dependencies = (
        "T[reflux_drum]",
        *(
            f"x_logit[reflux_drum,{component}]"
            for component in spec.component_names[:-1]
        ),
        *(
            f"y_bubble_logit[reflux_drum,{component}]"
            for component in spec.component_names[:-1]
        ),
    )
    return (
        *tuple(base_rows),
        *(
            ResidualRow(
                name=f"condenser_bubble_fugacity[{component}]",
                block="condenser_saturated_liquid",
                owner="total_condenser_reflux_drum_boundary",
                dependencies=dependencies,
            )
            for component in spec.component_names
        ),
    )


def evaluate_residual(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
) -> CondenserResidualEvaluation:
    layout = coordinate_layout(spec)
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    base_state, condenser = decode_coordinates(spec, reference, point)
    scales = np.asarray(fixed_scales, dtype=float).reshape((-1,))
    if scales.shape != (len(layout.names),) or np.any(scales <= 0.0):
        raise ValueError("DD-087 fixed residual scales are invalid")
    live_spec = replace(
        spec,
        condenser_duty_BTUph=condenser.condenser_duty_BTUph,
    )
    base = evaluate_base_residual(
        live_spec,
        reference.base,
        provider,
        point[layout.base],
        fixed_scales=scales[layout.base],
    )
    bubble = _fugacity_residual(
        provider,
        temperature_F=float(base_state.temperature_F[0]),
        pressure_psia=float(spec.pressure_psia[0]),
        liquid_x=base_state.liquid_mole_fraction[0],
        vapor_y=condenser.bubble_vapor_mole_fraction,
    )
    raw = np.concatenate((base.raw, bubble))
    rows = residual_rows(spec, base.rows)
    if raw.shape != scales.shape or len(rows) != raw.size:
        raise RuntimeError("DD-087 residual assembly is not 40 x 40")
    return CondenserResidualEvaluation(
        raw=raw,
        scaled=raw / scales,
        scales=scales,
        rows=rows,
        base=base,
        condenser=condenser,
    )


def _dependency_coordinate_name(name: str) -> str | None:
    if name.startswith("NL["):
        return "log_" + name
    if name.startswith("x["):
        return name.replace("x[", "x_logit[", 1)
    if name.startswith("y_bubble["):
        return name.replace("y_bubble[", "y_bubble_logit[", 1)
    if name.startswith("y["):
        return name.replace("y[", "y_logit[", 1)
    if name.startswith("L[") or name.startswith("V["):
        return "log_" + name
    if name in {"D", "B"}:
        return "log_" + name
    if name == "Q_C":
        return "q_Q_C"
    if name.startswith("T["):
        return name
    return None


def structural_pattern(spec: EnergyOwnedOperatingSpec) -> np.ndarray:
    registry = build_condenser_saturated_liquid_registry(spec.component_names)
    layout = coordinate_layout(spec)
    index = {name: position for position, name in enumerate(layout.names)}
    pattern = np.zeros(
        (len(registry.residuals), len(registry.unknowns)),
        dtype=bool,
    )
    for row_index, residual in enumerate(registry.residuals):
        for dependency in residual.dependencies:
            coordinate = _dependency_coordinate_name(dependency)
            if coordinate is not None:
                pattern[row_index, index[coordinate]] = True
    return pattern


def _rank_condition_singular(
    matrix: np.ndarray,
) -> tuple[int, float, np.ndarray]:
    singular = np.linalg.svd(matrix, compute_uv=False)
    tolerance = max(matrix.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    condition = float(
        np.inf if singular[-1] <= tolerance else singular[0] / singular[-1]
    )
    return rank, condition, singular


def audit_numerical_jacobian(
    spec: EnergyOwnedOperatingSpec,
    reference: CondenserNumericalReference,
    provider: Any,
    coordinates: Sequence[float],
    *,
    fixed_scales: Sequence[float],
    step: float,
    coupling_tolerance: float = 1.0e-7,
) -> CondenserJacobianAudit:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    baseline = evaluate_residual(
        spec,
        reference,
        provider,
        point,
        fixed_scales=fixed_scales,
    )
    matrix = np.empty((point.size, point.size), dtype=float)
    for column in range(point.size):
        delta = np.zeros_like(point)
        delta[column] = float(step)
        plus = evaluate_residual(
            spec,
            reference,
            provider,
            point + delta,
            fixed_scales=fixed_scales,
        ).scaled
        minus = evaluate_residual(
            spec,
            reference,
            provider,
            point - delta,
            fixed_scales=fixed_scales,
        ).scaled
        matrix[:, column] = (plus - minus) / (2.0 * float(step))
    pattern = structural_pattern(spec)
    row_norm = np.max(np.abs(matrix), axis=1)
    column_norm = np.max(np.abs(matrix), axis=0)
    layout = coordinate_layout(spec)
    zero_rows = tuple(
        baseline.rows[index].name
        for index in np.flatnonzero(row_norm <= coupling_tolerance)
    )
    zero_columns = tuple(
        layout.names[index]
        for index in np.flatnonzero(column_norm <= coupling_tolerance)
    )
    unexpected = tuple(
        f"{baseline.rows[row].name} <- {layout.names[column]}"
        for row, column in zip(
            *np.where((~pattern) & (np.abs(matrix) > coupling_tolerance))
        )
    )
    rank, condition, singular = _rank_condition_singular(matrix)
    bubble_rows = np.asarray(
        [
            index
            for index, row in enumerate(baseline.rows)
            if row.block == "condenser_saturated_liquid"
        ],
        dtype=int,
    )
    bubble_columns = np.asarray(
        (
            layout.names.index("T[reflux_drum]"),
            *range(layout.bubble_logits.start, layout.bubble_logits.stop),
        ),
        dtype=int,
    )
    bubble_matrix = matrix[np.ix_(bubble_rows, bubble_columns)]
    bubble_rank, _bubble_condition, bubble_singular = _rank_condition_singular(
        bubble_matrix
    )
    bubble_row_norm = np.max(np.abs(bubble_matrix), axis=1)
    bubble_column_norm = np.max(np.abs(bubble_matrix), axis=0)
    return CondenserJacobianAudit(
        step=float(step),
        matrix=matrix,
        rank=rank,
        condition=condition,
        singular_values=singular,
        zero_rows=zero_rows,
        zero_columns=zero_columns,
        unexpected_couplings=unexpected,
        bubble_matrix=bubble_matrix,
        bubble_rank=bubble_rank,
        bubble_singular_values=bubble_singular,
        bubble_zero_rows=tuple(
            baseline.rows[bubble_rows[index]].name
            for index in np.flatnonzero(
                bubble_row_norm <= coupling_tolerance
            )
        ),
        bubble_zero_columns=tuple(
            layout.names[bubble_columns[index]]
            for index in np.flatnonzero(
                bubble_column_norm <= coupling_tolerance
            )
        ),
    )


def solve_local_bubble_seed(
    provider: Any,
    *,
    pressure_psia: float,
    liquid_x: Sequence[float],
    temperature_guess_F: float,
    vapor_guess: Sequence[float],
    settings: BubbleSeedSettings = BubbleSeedSettings(),
) -> BubbleSeedResult:
    """Solve only the local 3 x 3 bubble equations used to construct a seed."""
    x = normalize_composition(liquid_x)
    y0 = normalize_composition(vapor_guess)
    reference_logits = vapor_logits(y0)
    point0 = np.zeros(x.size, dtype=float)
    lower = np.concatenate(
        (
            [
                (settings.temperature_min_F - float(temperature_guess_F))
                / settings.temperature_scale_F
            ],
            np.full(x.size - 1, -25.0),
        )
    )
    upper = np.concatenate(
        (
            [
                (settings.temperature_max_F - float(temperature_guess_F))
                / settings.temperature_scale_F
            ],
            np.full(x.size - 1, 25.0),
        )
    )

    def decode(point: np.ndarray) -> tuple[float, np.ndarray]:
        temperature = float(temperature_guess_F) + (
            settings.temperature_scale_F * float(point[0])
        )
        vapor = vapor_from_logits(reference_logits + point[1:])
        return temperature, vapor

    def objective(point: np.ndarray) -> np.ndarray:
        temperature, vapor = decode(point)
        return _fugacity_residual(
            provider,
            temperature_F=temperature,
            pressure_psia=pressure_psia,
            liquid_x=x,
            vapor_y=vapor,
        )

    def jacobian(point: np.ndarray) -> np.ndarray:
        matrix = np.empty((point.size, point.size), dtype=float)
        for column in range(point.size):
            delta = np.zeros_like(point)
            delta[column] = settings.jacobian_step
            matrix[:, column] = (
                objective(point + delta) - objective(point - delta)
            ) / (2.0 * settings.jacobian_step)
        return matrix

    result = least_squares(
        objective,
        point0,
        jac=jacobian,
        bounds=(lower, upper),
        method=settings.method,
        ftol=settings.ftol,
        xtol=settings.xtol,
        gtol=settings.gtol,
        max_nfev=settings.max_nfev,
        x_scale=1.0,
    )
    temperature, vapor = decode(result.x)
    residual = objective(result.x)
    return BubbleSeedResult(
        temperature_F=temperature,
        vapor_mole_fraction=vapor,
        scaled_coordinates=result.x.copy(),
        residual=residual,
        residual_inf_norm=float(np.max(np.abs(residual))),
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
        njev=None if result.njev is None else int(result.njev),
    )


def phase_stability_diagnostics(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: Sequence[float],
    bubble_y: Sequence[float],
) -> dict[str, Any]:
    x = normalize_composition(liquid_x)
    y = normalize_composition(bubble_y)
    flash = provider.flash_TP_full(
        float(temperature_F),
        float(pressure_psia),
        x.tolist(),
    )
    K = np.asarray(flash.K, dtype=float).reshape(x.shape)
    beta = rachford_rice_vapor_fraction(K, x)
    reconstructed = normalize_composition(K * x)
    return {
        "K": K,
        "bubble_sum_xK_minus_one": float(np.sum(x * K) - 1.0),
        "vapor_fraction": float(beta),
        "Kx_normalized": reconstructed,
        "bubble_y_minus_Kx_max_abs": float(
            np.max(np.abs(y - reconstructed))
        ),
    }


__all__ = [
    "BubbleSeedResult",
    "BubbleSeedSettings",
    "CondenserCoordinateLayout",
    "CondenserJacobianAudit",
    "CondenserNumericalReference",
    "CondenserResidualEvaluation",
    "audit_numerical_jacobian",
    "coordinate_layout",
    "decode_coordinates",
    "evaluate_residual",
    "phase_stability_diagnostics",
    "residual_rows",
    "solve_local_bubble_seed",
    "structural_pattern",
]
