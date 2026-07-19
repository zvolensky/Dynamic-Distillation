"""Property-only diagnostics for DWSIM PR phase-interface consistency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from scipy.optimize import least_squares

from dynamic_distillation.core_v2.condenser_phase_stability_v1 import (
    rachford_rice_vapor_fraction,
)
from dynamic_distillation.core_v2.one_volume_property_gate_v1 import (
    normalize_composition,
    vapor_from_logits,
    vapor_logits,
)


R_SI = 8.31446261815324
PSIA_TO_PA = 6894.757293168


@dataclass(frozen=True)
class PengRobinsonParameters:
    critical_temperature_K: np.ndarray
    critical_pressure_Pa: np.ndarray
    acentric_factor: np.ndarray
    binary_interaction: np.ndarray


@dataclass(frozen=True)
class BubbleSolveResult:
    temperature_F: float
    vapor_mole_fraction: np.ndarray
    residual: np.ndarray
    residual_inf_norm: float
    success: bool
    status: int
    message: str
    nfev: int


def _temperature_K(temperature_F: float) -> float:
    return (float(temperature_F) - 32.0) * 5.0 / 9.0 + 273.15


def _phase_fugacity_residual(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    liquid_x: Sequence[float],
    vapor_y: Sequence[float],
) -> np.ndarray:
    x = normalize_composition(liquid_x)
    y = normalize_composition(vapor_y)
    phi_l = np.asarray(
        provider.phase_fugacity_coefficients(
            "liquid",
            float(temperature_F),
            float(pressure_psia),
            x.tolist(),
        ),
        dtype=float,
    )
    phi_v = np.asarray(
        provider.phase_fugacity_coefficients(
            "vapor",
            float(temperature_F),
            float(pressure_psia),
            y.tolist(),
        ),
        dtype=float,
    )
    if (
        phi_l.shape != x.shape
        or phi_v.shape != y.shape
        or np.any(~np.isfinite(phi_l))
        or np.any(~np.isfinite(phi_v))
        or np.any(phi_l <= 0.0)
        or np.any(phi_v <= 0.0)
    ):
        raise RuntimeError("non-physical imposed-phase fugacity coefficients")
    return np.log(y * phi_v / (x * phi_l))


def solve_bubble_from_fugacity(
    provider: Any,
    *,
    pressure_psia: float,
    liquid_x: Sequence[float],
    temperature_guess_F: float,
    vapor_guess: Sequence[float],
    temperature_min_F: float = 80.0,
    temperature_max_F: float = 260.0,
    temperature_scale_F: float = 100.0,
    jacobian_step: float = 1.0e-5,
    max_nfev: int = 100,
) -> BubbleSolveResult:
    """Solve one local bubble state using only imposed-phase fugacities."""
    x = normalize_composition(liquid_x)
    y0 = normalize_composition(vapor_guess)
    reference_logits = vapor_logits(y0)
    point0 = np.zeros(x.size, dtype=float)
    lower = np.concatenate(
        (
            [
                (float(temperature_min_F) - float(temperature_guess_F))
                / float(temperature_scale_F)
            ],
            np.full(x.size - 1, -25.0),
        )
    )
    upper = np.concatenate(
        (
            [
                (float(temperature_max_F) - float(temperature_guess_F))
                / float(temperature_scale_F)
            ],
            np.full(x.size - 1, 25.0),
        )
    )

    def decode(point: np.ndarray) -> tuple[float, np.ndarray]:
        temperature = float(temperature_guess_F) + (
            float(temperature_scale_F) * float(point[0])
        )
        vapor = vapor_from_logits(reference_logits + point[1:])
        return temperature, vapor

    def objective(point: np.ndarray) -> np.ndarray:
        temperature, vapor = decode(point)
        return _phase_fugacity_residual(
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
            delta[column] = float(jacobian_step)
            matrix[:, column] = (
                objective(point + delta) - objective(point - delta)
            ) / (2.0 * float(jacobian_step))
        return matrix

    result = least_squares(
        objective,
        point0,
        jac=jacobian,
        bounds=(lower, upper),
        method="trf",
        ftol=1.0e-12,
        xtol=1.0e-12,
        gtol=1.0e-12,
        max_nfev=int(max_nfev),
        x_scale=1.0,
    )
    temperature, vapor = decode(result.x)
    residual = objective(result.x)
    return BubbleSolveResult(
        temperature_F=float(temperature),
        vapor_mole_fraction=vapor,
        residual=residual,
        residual_inf_norm=float(np.max(np.abs(residual))),
        success=bool(result.success),
        status=int(result.status),
        message=str(result.message),
        nfev=int(result.nfev),
    )


class IndependentPengRobinsonProvider:
    """Small independent PR fugacity implementation for cross-checking."""

    def __init__(self, parameters: PengRobinsonParameters):
        tc = np.asarray(parameters.critical_temperature_K, dtype=float)
        pc = np.asarray(parameters.critical_pressure_Pa, dtype=float)
        omega = np.asarray(parameters.acentric_factor, dtype=float)
        kij = np.asarray(parameters.binary_interaction, dtype=float)
        n = tc.size
        if (
            tc.shape != (n,)
            or pc.shape != (n,)
            or omega.shape != (n,)
            or kij.shape != (n, n)
            or np.any(tc <= 0.0)
            or np.any(pc <= 0.0)
            or np.any(~np.isfinite(kij))
        ):
            raise ValueError("invalid independent PR parameters")
        self.parameters = PengRobinsonParameters(tc, pc, omega, kij)

    def phase_fugacity_coefficients(
        self,
        phase: str,
        temperature_F: float,
        pressure_psia: float,
        composition: Sequence[float],
    ) -> np.ndarray:
        z = normalize_composition(composition)
        params = self.parameters
        temperature = _temperature_K(temperature_F)
        pressure = float(pressure_psia) * PSIA_TO_PA
        tc = params.critical_temperature_K
        pc = params.critical_pressure_Pa
        omega = params.acentric_factor
        kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega * omega
        alpha = (
            1.0 + kappa * (1.0 - np.sqrt(temperature / tc))
        ) ** 2
        ai = 0.45724 * R_SI * R_SI * tc * tc * alpha / pc
        bi = 0.07780 * R_SI * tc / pc
        aij = np.sqrt(np.outer(ai, ai)) * (
            1.0 - params.binary_interaction
        )
        amix = float(z @ aij @ z)
        bmix = float(z @ bi)
        A = amix * pressure / (R_SI * R_SI * temperature * temperature)
        B = bmix * pressure / (R_SI * temperature)
        roots = np.roots(
            [
                1.0,
                -(1.0 - B),
                A - 3.0 * B * B - 2.0 * B,
                -(A * B - B * B - B**3),
            ]
        )
        real = np.sort(
            np.asarray(
                [
                    float(root.real)
                    for root in roots
                    if abs(float(root.imag)) <= 1.0e-9
                    and float(root.real) > B
                ],
                dtype=float,
            )
        )
        if real.size == 0:
            raise RuntimeError("independent PR calculation has no physical root")
        phase_key = str(phase).strip().lower()
        if phase_key in {"liquid", "liq", "l"}:
            Z = float(real[0])
        elif phase_key in {"vapor", "vapour", "vap", "v"}:
            Z = float(real[-1])
        else:
            raise ValueError("phase must be liquid or vapor")
        sqrt_two = np.sqrt(2.0)
        sum_aij = aij @ z
        log_ratio = np.log(
            (Z + (1.0 + sqrt_two) * B)
            / (Z + (1.0 - sqrt_two) * B)
        )
        ln_phi = (
            bi / bmix * (Z - 1.0)
            - np.log(Z - B)
            - A
            / (2.0 * sqrt_two * B)
            * (2.0 * sum_aij / amix - bi / bmix)
            * log_ratio
        )
        phi = np.exp(ln_phi)
        if np.any(~np.isfinite(phi)) or np.any(phi <= 0.0):
            raise RuntimeError("independent PR returned invalid fugacities")
        return phi


def evaluate_interface_state(
    provider: Any,
    *,
    temperature_F: float,
    pressure_psia: float,
    overall_z: Sequence[float],
    direct_bubble_y: Sequence[float],
) -> dict[str, Any]:
    """Compare imposed-phase bubble equations with the raw DWSIM TP flash."""
    z = normalize_composition(overall_z)
    direct_y = normalize_composition(direct_bubble_y)
    raw = provider.flash_TP_full_F_psia(
        float(temperature_F),
        float(pressure_psia),
        z.tolist(),
    )
    if len(raw) not in {5, 6}:
        raise RuntimeError("unexpected DWSIM flash result")
    flash_x = normalize_composition(raw[0])
    flash_y = normalize_composition(raw[1])
    K = np.asarray(raw[2], dtype=float).reshape(z.shape)
    if np.any(~np.isfinite(K)) or np.any(K <= 0.0):
        raise RuntimeError("DWSIM flash returned invalid K values")
    beta = float(rachford_rice_vapor_fraction(K, z))
    Kz = normalize_composition(K * z)
    Kx_flash = normalize_composition(K * flash_x)
    reconstructed_z = (1.0 - beta) * flash_x + beta * flash_y

    direct_minus_Kz = direct_y - Kz
    direct_minus_flash_y = direct_y - flash_y
    flash_y_minus_Kx_flash = flash_y - Kx_flash
    Kx_flash_minus_Kz = Kx_flash - Kz
    decomposition = (
        direct_minus_flash_y
        + flash_y_minus_Kx_flash
        + Kx_flash_minus_Kz
    )
    direct_fugacity = _phase_fugacity_residual(
        provider,
        temperature_F=temperature_F,
        pressure_psia=pressure_psia,
        liquid_x=z,
        vapor_y=direct_y,
    )
    flash_fugacity = _phase_fugacity_residual(
        provider,
        temperature_F=temperature_F,
        pressure_psia=pressure_psia,
        liquid_x=flash_x,
        vapor_y=flash_y,
    )
    return {
        "temperature_F": float(temperature_F),
        "pressure_psia": float(pressure_psia),
        "overall_z": z,
        "direct_bubble_y": direct_y,
        "flash_x": flash_x,
        "flash_y": flash_y,
        "flash_K": K,
        "rachford_rice_beta": beta,
        "Kz_normalized": Kz,
        "Kx_flash_normalized": Kx_flash,
        "reconstructed_overall_z": reconstructed_z,
        "direct_bubble_residual": direct_fugacity,
        "flash_phase_residual": flash_fugacity,
        "direct_y_minus_Kz": direct_minus_Kz,
        "direct_y_minus_flash_y": direct_minus_flash_y,
        "flash_y_minus_Kx_flash": flash_y_minus_Kx_flash,
        "Kx_flash_minus_Kz": Kx_flash_minus_Kz,
        "decomposition_closure": direct_minus_Kz - decomposition,
        "metrics": {
            "legacy_direct_y_minus_Kz_max_abs": float(
                np.max(np.abs(direct_minus_Kz))
            ),
            "direct_y_minus_flash_y_max_abs": float(
                np.max(np.abs(direct_minus_flash_y))
            ),
            "flash_y_minus_Kx_flash_max_abs": float(
                np.max(np.abs(flash_y_minus_Kx_flash))
            ),
            "Kx_flash_minus_Kz_max_abs": float(
                np.max(np.abs(Kx_flash_minus_Kz))
            ),
            "flash_x_minus_overall_z_max_abs": float(
                np.max(np.abs(flash_x - z))
            ),
            "lever_rule_closure_max_abs": float(
                np.max(np.abs(reconstructed_z - z))
            ),
            "decomposition_closure_max_abs": float(
                np.max(np.abs(direct_minus_Kz - decomposition))
            ),
            "direct_bubble_residual_inf": float(
                np.max(np.abs(direct_fugacity))
            ),
            "flash_phase_residual_inf": float(
                np.max(np.abs(flash_fugacity))
            ),
        },
    }


__all__ = [
    "BubbleSolveResult",
    "IndependentPengRobinsonProvider",
    "PengRobinsonParameters",
    "evaluate_interface_state",
    "solve_bubble_from_fugacity",
]
