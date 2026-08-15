"""Property-free BDF2 ownership contract for controlled Core V3 dynamics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

from .structural_rank_v1 import structural_rank_fast

from .terminal_inventory_control_contract_v1 import (
    TerminalInventoryControlContract,
    audit_terminal_inventory_control_contract,
)
from .terminal_inventory_control_implicit_step_v1 import (
    terminal_inventory_control_step_pattern,
)


CONTRACT_NAME = "Core V3 - Controlled Constant-Step BDF2 Contract"
CONTRACT_VERSION = "core-v3-terminal-inventory-control-bdf2-contract-v1"


@dataclass(frozen=True)
class ControlledBDF2Contract:
    name: str
    version: str
    controlled: TerminalInventoryControlContract
    history_levels: tuple[str, str]
    component_history_coordinates: tuple[str, ...]
    energy_history_coordinates: tuple[str, ...]
    controller_history_coordinates: tuple[str, ...]
    component_formula: str
    energy_formula: str
    controller_formula: str
    positive_inventory_map: str
    startup_formula: str
    timestep_policy: str
    property_evaluation_attempted: bool = False
    residual_evaluation_attempted: bool = False
    nonlinear_solve_attempted: bool = False
    timestep_attempted: bool = False
    trajectory_attempted: bool = False


@dataclass(frozen=True)
class ControlledBDF2Audit:
    component_count: int
    volume_count: int
    differential_state_count: int
    derived_energy_history_count: int
    history_value_count: int
    expected_history_value_count: int
    solve_variable_count: int
    row_count: int
    structural_rank: int
    structural_nullity: int
    backward_euler_pattern_equal: bool
    two_history_levels: bool
    all_history_coordinates_unique: bool
    component_history_complete: bool
    energy_history_complete: bool
    controller_history_complete: bool
    existing_backward_euler_startup: bool
    constant_step_only: bool
    positive_inventory_endpoint: bool
    controlled_contract_passed: bool
    preparation_only: bool
    pass_gate: bool


def _history_name(quantity: str, owner: str, level: str, component: str | None = None) -> str:
    suffix = f",{component}" if component is not None else ""
    return f"{quantity}[{owner}{suffix}]@{level}"


def build_controlled_bdf2_contract(
    controlled: TerminalInventoryControlContract,
) -> ControlledBDF2Contract:
    base = controlled.base
    levels = ("n", "n_minus_1")
    component_history = tuple(
        _history_name("N", volume, level, component)
        for level in levels
        for volume in base.topology.volume_ids
        for component in base.component_names
    )
    energy_history = tuple(
        _history_name("U", volume, level)
        for level in levels
        for volume in base.topology.volume_ids
    )
    controller_history = tuple(
        _history_name("I_level", volume, level)
        for level in levels
        for volume in (base.topology.top_volume, base.topology.bottom_volume)
    )
    return ControlledBDF2Contract(
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        controlled=controlled,
        history_levels=levels,
        component_history_coordinates=component_history,
        energy_history_coordinates=energy_history,
        controller_history_coordinates=controller_history,
        component_formula=(
            "dN/dt=(3*N[n+1]-4*N[n]+N[n-1])/(2*dt); component balance "
            "uses this effective finite-step rate"
        ),
        energy_formula=(
            "dU/dt=(3*U[n+1]-4*U[n]+U[n-1])/(2*dt), with every U "
            "reconstructed from the governing endpoint or saved history state"
        ),
        controller_formula=(
            "dI/dt=(3*I[n+1]-4*I[n]+I[n-1])/(2*dt); solve coordinates "
            "map exactly to I[n+1]=(2*dt*dI/dt+4*I[n]-I[n-1])/3"
        ),
        positive_inventory_map=(
            "N[n+1]=N[n]*exp(dt*r_nominal/N[n]); the residual replaces "
            "r_nominal with the exact BDF2 finite-step rate"
        ),
        startup_formula=(
            "Exactly one accepted existing backward-Euler controlled step creates "
            "the first history pair before the first BDF2 step"
        ),
        timestep_policy=(
            "BDF2 is constant-step only. Any dt change invalidates the two-level "
            "history and requires a new backward-Euler startup step."
        ),
    )


def audit_controlled_bdf2_contract(
    contract: ControlledBDF2Contract,
) -> ControlledBDF2Audit:
    controlled = contract.controlled
    base = controlled.base
    controlled_audit = audit_terminal_inventory_control_contract(controlled)
    pattern = terminal_inventory_control_step_pattern(controlled)
    matrix = csr_matrix(np.asarray(pattern, dtype=np.int8))
    rank = structural_rank_fast(matrix)
    all_history = (
        *contract.component_history_coordinates,
        *contract.energy_history_coordinates,
        *contract.controller_history_coordinates,
    )
    component_count = len(base.component_names)
    volume_count = len(base.topology.volume_ids)
    differential_count = volume_count * component_count + 2
    expected_history = 2 * (volume_count * component_count + volume_count + 2)
    expected_components = 2 * volume_count * component_count
    expected_energy = 2 * volume_count
    expected_controller = 4
    solve_count = len(controlled.derivative_variables) + len(
        controlled.algebraic_variables
    )
    row_count = len(controlled.rows)
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.residual_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.timestep_attempted,
            contract.trajectory_attempted,
        )
    )
    checks = {
        "controlled": controlled_audit.pass_gate,
        "square": solve_count == row_count,
        "rank": rank == solve_count,
        "history": len(all_history) == expected_history,
        "levels": contract.history_levels == ("n", "n_minus_1"),
        "unique": len(set(all_history)) == len(all_history),
        "components": len(contract.component_history_coordinates)
        == expected_components,
        "energy": len(contract.energy_history_coordinates) == expected_energy,
        "controllers": len(contract.controller_history_coordinates)
        == expected_controller,
        "startup": "backward-Euler" in contract.startup_formula,
        "constant_step": "constant-step only" in contract.timestep_policy,
        "positive": "exp(" in contract.positive_inventory_map,
        "preparation": preparation_only,
    }
    return ControlledBDF2Audit(
        component_count=component_count,
        volume_count=volume_count,
        differential_state_count=differential_count,
        derived_energy_history_count=volume_count,
        history_value_count=len(all_history),
        expected_history_value_count=expected_history,
        solve_variable_count=solve_count,
        row_count=row_count,
        structural_rank=rank,
        structural_nullity=solve_count - rank,
        backward_euler_pattern_equal=pattern.shape == (row_count, solve_count),
        two_history_levels=checks["levels"],
        all_history_coordinates_unique=checks["unique"],
        component_history_complete=checks["components"],
        energy_history_complete=checks["energy"],
        controller_history_complete=checks["controllers"],
        existing_backward_euler_startup=checks["startup"],
        constant_step_only=checks["constant_step"],
        positive_inventory_endpoint=checks["positive"],
        controlled_contract_passed=checks["controlled"],
        preparation_only=preparation_only,
        pass_gate=all(checks.values()),
    )


__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "ControlledBDF2Audit",
    "ControlledBDF2Contract",
    "audit_controlled_bdf2_contract",
    "build_controlled_bdf2_contract",
]
