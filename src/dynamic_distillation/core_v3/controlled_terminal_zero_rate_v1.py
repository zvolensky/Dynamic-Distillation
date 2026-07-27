"""Controlled-terminal extension of the Core V3 zero-rate residual."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    ConservedNUPressureInitializerContract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    InitializerNumericalSpec,
)
from dynamic_distillation.core_v3.pressure_layer_numerical_v1 import PressureNumericalSpec
from dynamic_distillation.core_v3.provider_call_audit_v1 import ProviderCallAudit
from dynamic_distillation.core_v3.provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from dynamic_distillation.core_v3.zero_rate_readiness_v1 import (
    ZeroRateReadinessEvaluation,
    evaluate_zero_rate_readiness,
    zero_rate_pattern,
    zero_rate_row_names,
    zero_rate_variable_names,
)


PRODUCT_VARIABLE_NAMES = ("log_D_level_output", "log_B_level_output")


@dataclass(frozen=True)
class ControlledTerminalEvaluation:
    scaled: np.ndarray
    coordinates: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    base: ZeroRateReadinessEvaluation


def controlled_terminal_variable_names(
    contract: ConservedNUPressureInitializerContract,
) -> tuple[str, ...]:
    return (*zero_rate_variable_names(contract), *PRODUCT_VARIABLE_NAMES)


def controlled_terminal_pattern(
    contract: ConservedNUPressureInitializerContract,
) -> np.ndarray:
    base = zero_rate_pattern(contract)
    pattern = np.pad(base, ((0, 0), (0, 2)), constant_values=False)
    for row_index, row_name in enumerate(zero_rate_row_names(contract)):
        if row_name.startswith("component_balance[reflux_drum,") or row_name == "energy_balance[reflux_drum]":
            pattern[row_index, -2] = True
        if row_name.startswith("component_balance[combined_reboiler_sump,") or row_name == "energy_balance[combined_reboiler_sump]":
            pattern[row_index, -1] = True
    return pattern


def evaluate_controlled_terminal_zero_rate(
    contract: ConservedNUPressureInitializerContract,
    numerical: InitializerNumericalSpec,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    coordinates: Sequence[float],
    top_storage_gradient_BTU_lbmol: Sequence[float],
    energy_rate_scales_BTUph: Sequence[float],
    fixed_steady_scales: Sequence[float],
    storage_scales_BTU: Sequence[float],
    pressure_numerical: PressureNumericalSpec,
    state_id: str,
    evaluation_kind: str,
) -> ControlledTerminalEvaluation:
    point = np.asarray(coordinates, dtype=float).reshape((-1,))
    base_count = len(zero_rate_variable_names(contract))
    if point.shape != (base_count + 2,) or np.any(~np.isfinite(point)):
        raise ValueError("controlled-terminal coordinates are invalid")
    distillate = float(template.distillate_lbmolph) * float(np.exp(point[-2]))
    bottoms = float(template.bottoms_lbmolph) * float(np.exp(point[-1]))
    if not np.isfinite(distillate) or not np.isfinite(bottoms):
        raise ValueError("controlled-terminal product rates are invalid")
    live_template = replace(
        template,
        distillate_lbmolph=distillate,
        bottoms_lbmolph=bottoms,
    )
    base = evaluate_zero_rate_readiness(
        contract,
        numerical,
        spec,
        reference,
        live_template,
        provider,
        call_audit,
        coordinates=point[:-2],
        top_storage_gradient_BTU_lbmol=top_storage_gradient_BTU_lbmol,
        energy_rate_scales_BTUph=energy_rate_scales_BTUph,
        fixed_steady_scales=fixed_steady_scales,
        storage_scales_BTU=storage_scales_BTU,
        pressure_numerical=pressure_numerical,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    return ControlledTerminalEvaluation(
        scaled=base.scaled.copy(),
        coordinates=point.copy(),
        distillate_lbmolph=distillate,
        bottoms_lbmolph=bottoms,
        base=base,
    )


__all__ = [
    "ControlledTerminalEvaluation",
    "PRODUCT_VARIABLE_NAMES",
    "controlled_terminal_pattern",
    "controlled_terminal_variable_names",
    "evaluate_controlled_terminal_zero_rate",
]
