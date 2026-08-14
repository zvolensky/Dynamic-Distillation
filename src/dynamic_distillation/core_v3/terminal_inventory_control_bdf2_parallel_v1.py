"""Parallel Jacobian step-solver adapter for controlled BDF2 trajectories."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from .persistent_parallel_colored_jacobian_v1 import (
    PersistentParallelColoredJacobian,
)
from .terminal_inventory_control_bdf2_residual_v1 import (
    solve_terminal_inventory_control_bdf2_step,
)
from .terminal_inventory_control_implicit_step_v1 import (
    solve_terminal_inventory_control_backward_euler_step,
)


def physical_state_payload(state: Any) -> dict[str, Any]:
    return {
        "liquid_moles_lbmol": np.asarray(state.liquid_moles_lbmol).tolist(),
        "liquid_mole_fraction": np.asarray(state.liquid_mole_fraction).tolist(),
        "temperature_F": np.asarray(state.temperature_F).tolist(),
        "vapor_mole_fraction": np.asarray(state.vapor_mole_fraction).tolist(),
        "hydraulic_liquid_flow_lbmolph": np.asarray(
            state.hydraulic_liquid_flow_lbmolph
        ).tolist(),
        "vapor_flow_lbmolph": np.asarray(state.vapor_flow_lbmolph).tolist(),
        "distillate_lbmolph": float(state.distillate_lbmolph),
        "bottoms_lbmolph": float(state.bottoms_lbmolph),
        "bubble_vapor_mole_fraction": np.asarray(
            state.bubble_vapor_mole_fraction
        ).tolist(),
        "condenser_duty_BTUph": float(state.condenser_duty_BTUph),
    }


def controlled_bdf2_history_payload(history: Any) -> dict[str, Any]:
    return {
        "step_seconds": float(history.step_seconds),
        "current_inventory_lbmol": np.asarray(history.current_inventory_lbmol).tolist(),
        "prior_inventory_lbmol": np.asarray(history.prior_inventory_lbmol).tolist(),
        "current_internal_energy_BTU": np.asarray(
            history.current_internal_energy_BTU
        ).tolist(),
        "prior_internal_energy_BTU": np.asarray(
            history.prior_internal_energy_BTU
        ).tolist(),
        "current_controller_memory": np.asarray(
            history.current_controller_memory
        ).tolist(),
        "prior_controller_memory": np.asarray(history.prior_controller_memory).tolist(),
    }


class TerminalInventoryControlBDF2ParallelStepSolvers:
    """Supply method-aware parallel Jacobians to the existing step solvers."""

    def __init__(self, jacobians: PersistentParallelColoredJacobian) -> None:
        self.jacobians = jacobians

    def _builder(self, method: str, root_epoch: str, work_basis: Mapping[str, Any]):
        def build(_objective, point, state_id):
            return self.jacobians.build(
                point,
                state_id,
                method=method,
                root_epoch=root_epoch,
                work_basis=work_basis,
            )

        return build

    def startup_step_solver(self, *args, **kwargs):
        if "jacobian_builder" in kwargs:
            raise ValueError("parallel startup solver owns the Jacobian builder")
        basis = {
            "template_state": physical_state_payload(args[3]),
            "previous_inventory_lbmol": np.asarray(
                kwargs["previous_inventory_lbmol"], dtype=float
            ).tolist(),
            "previous_controller_memory": np.asarray(
                kwargs["previous_controller_memory"], dtype=float
            ).tolist(),
            "initial_solve_coordinates": np.asarray(
                kwargs["initial_solve_coordinates"], dtype=float
            ).tolist(),
            "step_seconds": float(kwargs["step_seconds"]),
        }
        return solve_terminal_inventory_control_backward_euler_step(
            *args,
            **kwargs,
            jacobian_builder=self._builder(
                "backward_euler", str(kwargs["name"]), basis
            ),
        )

    def bdf2_step_solver(self, *args, **kwargs):
        if "jacobian_builder" in kwargs:
            raise ValueError("parallel BDF2 solver owns the Jacobian builder")
        basis = {
            "template_state": physical_state_payload(args[3]),
            "history": controlled_bdf2_history_payload(kwargs["history"]),
            "rate_scales_lbmolph": np.asarray(
                kwargs["rate_scales_lbmolph"], dtype=float
            ).tolist(),
            "step_seconds": float(kwargs["step_seconds"]),
        }
        return solve_terminal_inventory_control_bdf2_step(
            *args,
            **kwargs,
            jacobian_builder=self._builder("bdf2", str(kwargs["name"]), basis),
        )


__all__ = [
    "TerminalInventoryControlBDF2ParallelStepSolvers",
    "controlled_bdf2_history_payload",
    "physical_state_payload",
]
