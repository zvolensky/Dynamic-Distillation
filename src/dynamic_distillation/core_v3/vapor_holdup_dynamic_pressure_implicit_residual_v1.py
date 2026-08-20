"""Fixed-duty implicit residual for dynamic reflux-drum pressure."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Sequence

import numpy as np

from .provider_call_audit_v1 import ProviderCallAudit
from .vapor_holdup_dynamic_pressure_contract_v1 import (
    audit_vapor_holdup_dynamic_pressure_contract,
)
from .vapor_holdup_implicit_residual_v1 import VaporHoldupImplicitNumericalSpec
from .vapor_holdup_terminal_control_contract_v1 import (
    VaporHoldupTerminalControlContract,
)
from .vapor_holdup_terminal_control_implicit_residual_v1 import (
    VaporHoldupTerminalControlImplicitEvaluation,
    evaluate_vapor_holdup_terminal_control_implicit_residual,
)


def evaluate_vapor_holdup_dynamic_pressure_implicit_residual(
    contract: VaporHoldupTerminalControlContract,
    geometry: Sequence[Any],
    reference: Any,
    balance_inputs: Any,
    hydraulic_geometry: Sequence[Any],
    numerical: VaporHoldupImplicitNumericalSpec,
    provider: Any,
    call_audit: ProviderCallAudit,
    coordinates: Sequence[float],
    *,
    controller_memory_previous: Sequence[float],
    specified_condenser_duty_BTUph: float,
    state_id: str,
    evaluation_kind: str,
) -> VaporHoldupTerminalControlImplicitEvaluation:
    """Evaluate the successor after replacing only the pressure-anchor row."""
    specified_duty = float(specified_condenser_duty_BTUph)
    if not np.isfinite(specified_duty) or specified_duty >= 0.0:
        raise ValueError("specified condenser duty must be finite and negative")
    audit = audit_vapor_holdup_dynamic_pressure_contract(contract)
    if not audit.pass_gate:
        raise ValueError("dynamic-pressure structural contract has not passed")
    evaluation = evaluate_vapor_holdup_terminal_control_implicit_residual(
        contract,
        geometry,
        reference,
        balance_inputs,
        hydraulic_geometry,
        numerical,
        provider,
        call_audit,
        coordinates,
        controller_memory_previous=controller_memory_previous,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    duty_rows = tuple(
        index
        for index, row in enumerate(contract.base.rows)
        if row.block == "condenser_duty_specification"
    )
    if len(duty_rows) != 1:
        raise RuntimeError("dynamic-pressure contract requires one duty row")
    duty_index = duty_rows[0]
    live_duty = float(evaluation.base.endpoint.condenser_duty_BTUph)
    if not np.isfinite(live_duty) or live_duty >= 0.0:
        raise RuntimeError("dynamic-pressure endpoint condenser duty is invalid")
    duty_residual = float(np.log(live_duty / specified_duty))
    base_raw = evaluation.base.raw.copy()
    base_scaled = evaluation.base.scaled.copy()
    base_raw[duty_index] = duty_residual
    base_scaled[duty_index] = duty_residual
    base = replace(evaluation.base, raw=base_raw, scaled=base_scaled)
    raw = evaluation.raw.copy()
    scaled = evaluation.scaled.copy()
    raw[duty_index] = duty_residual
    scaled[duty_index] = duty_residual
    return replace(evaluation, raw=raw, scaled=scaled, base=base)


__all__ = ["evaluate_vapor_holdup_dynamic_pressure_implicit_residual"]
