"""Constant-step BDF2 residual assembly for controlled Core V3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .implicit_step_v1 import governing_storage_vector
from .provider_call_audit_v1 import ProviderCallAudit
from .provider_governed_residual_v1 import (
    NumericalReference,
    OperatingSpec,
    PhysicalState,
)
from .terminal_inventory_control_bdf2_kinematics_v1 import (
    ControlledBDF2History,
    ControlledBDF2Kinematics,
    evaluate_controlled_bdf2_kinematics,
)
from .terminal_inventory_control_contract_v1 import TerminalInventoryControlContract
from .terminal_inventory_control_implicit_step_v1 import (
    _coordinate_slices,
    _maximum_equilibrium_residual,
)
from .terminal_inventory_control_numerical_v1 import (
    TerminalInventoryControlEvaluation,
    TerminalLevelSetpoints,
    evaluate_terminal_inventory_control_residual,
)


@dataclass(frozen=True)
class TerminalInventoryControlBDF2Evaluation:
    raw: np.ndarray
    scaled: np.ndarray
    row_names: tuple[str, ...]
    variable_names: tuple[str, ...]
    solve_coordinates: np.ndarray
    history: ControlledBDF2History
    kinematics: ControlledBDF2Kinematics
    algebraic_coordinates: np.ndarray
    level_fraction: np.ndarray
    level_error: np.ndarray
    product_log_ratio: np.ndarray
    distillate_lbmolph: float
    bottoms_lbmolph: float
    control_evaluation: TerminalInventoryControlEvaluation
    maximum_equilibrium_residual: float


def evaluate_terminal_inventory_control_bdf2_residual(
    contract: TerminalInventoryControlContract,
    spec: OperatingSpec,
    reference: NumericalReference,
    template: PhysicalState,
    provider: Any,
    call_audit: ProviderCallAudit,
    *,
    history: ControlledBDF2History,
    level_setpoints: TerminalLevelSetpoints,
    rate_scales_lbmolph: Sequence[Sequence[float]],
    solve_coordinates: Sequence[float],
    step_seconds: float,
    fixed_steady_scales: Sequence[float],
    product_reference_lbmolph: Sequence[float] | None = None,
    state_id: str,
    evaluation_kind: str,
) -> TerminalInventoryControlBDF2Evaluation:
    """Evaluate one controlled BDF2 residual without owning a nonlinear solve."""
    expected = (len(spec.topology.volume_ids), len(spec.component_names))
    if history.current_inventory_lbmol.shape != expected:
        raise ValueError("BDF2 history does not match the operating topology")
    point = np.asarray(solve_coordinates, dtype=float).reshape((-1,))
    if point.shape != (len(contract.rows),) or np.any(~np.isfinite(point)):
        raise ValueError("controlled BDF2 solve coordinates are invalid")
    scales = np.asarray(rate_scales_lbmolph, dtype=float)
    if scales.shape != expected or np.any(~np.isfinite(scales)) or np.any(scales <= 0.0):
        raise ValueError("controlled BDF2 rate scales are invalid")
    rate_slice, controller_slice, algebraic_slice, product_slice = _coordinate_slices(
        contract
    )
    nominal_rate = point[rate_slice].reshape(expected) * scales
    controller_rate = point[controller_slice]
    preliminary = evaluate_controlled_bdf2_kinematics(
        history,
        nominal_component_rate_lbmolph=nominal_rate,
        component_rate_scales_lbmolph=scales,
        endpoint_internal_energy_BTU=history.current_internal_energy_BTU,
        controller_rate_per_sec=controller_rate,
        step_seconds=step_seconds,
    )
    effective = point.copy()
    effective[rate_slice] = preliminary.component_rate_coordinates.reshape((-1,))
    control = evaluate_terminal_inventory_control_residual(
        contract,
        spec,
        reference,
        template,
        provider,
        call_audit,
        inventory_lbmol=preliminary.endpoint_inventory_lbmol,
        controller_memory=preliminary.endpoint_controller_memory,
        level_setpoints=level_setpoints,
        solve_coordinates=effective,
        storage_gradient_BTU_lbmol=np.zeros(expected, dtype=float),
        fixed_steady_scales=fixed_steady_scales,
        product_reference_lbmolph=product_reference_lbmolph,
        state_id=state_id,
        evaluation_kind=evaluation_kind,
    )
    endpoint_storage = governing_storage_vector(
        spec, control.base, preliminary.endpoint_inventory_lbmol
    )
    kinematics = evaluate_controlled_bdf2_kinematics(
        history,
        nominal_component_rate_lbmolph=nominal_rate,
        component_rate_scales_lbmolph=scales,
        endpoint_internal_energy_BTU=endpoint_storage,
        controller_rate_per_sec=controller_rate,
        step_seconds=step_seconds,
    )
    raw = np.asarray(control.raw, dtype=float).copy()
    energy_indices = np.asarray(
        [
            index
            for index, row in enumerate(contract.base.rows)
            if row.block == "energy_balance"
        ],
        dtype=int,
    )
    if energy_indices.size != expected[0]:
        raise RuntimeError("controlled BDF2 contract needs one energy row per volume")
    raw[energy_indices] += kinematics.energy_storage_rate_BTUph
    residual_scales = np.concatenate(
        (np.asarray(control.base.scales, dtype=float), np.ones(4, dtype=float))
    )
    return TerminalInventoryControlBDF2Evaluation(
        raw=raw,
        scaled=raw / residual_scales,
        row_names=control.row_names,
        variable_names=control.variable_names,
        solve_coordinates=effective,
        history=history,
        kinematics=kinematics,
        algebraic_coordinates=effective[algebraic_slice].copy(),
        level_fraction=control.level_fraction.copy(),
        level_error=control.level_error.copy(),
        product_log_ratio=effective[product_slice].copy(),
        distillate_lbmolph=control.distillate_lbmolph,
        bottoms_lbmolph=control.bottoms_lbmolph,
        control_evaluation=control,
        maximum_equilibrium_residual=_maximum_equilibrium_residual(contract, control),
    )


__all__ = [
    "TerminalInventoryControlBDF2Evaluation",
    "evaluate_terminal_inventory_control_bdf2_residual",
]
