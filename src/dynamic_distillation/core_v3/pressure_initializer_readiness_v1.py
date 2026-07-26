"""Pre-execution readiness audit for the DD-106 initializer architecture."""

from __future__ import annotations

from dataclasses import dataclass

from dynamic_distillation.core_v3.pressure_consistent_initializer_contract_v1 import (
    PressureConsistentInitializerContract,
)


@dataclass(frozen=True)
class PressureInitializerReadinessAudit:
    component_inventory_state_count: int
    component_inventory_rate_count: int
    independent_energy_state_count: int
    energy_rate_variable_count: int
    algebraic_pressure_count: int
    pressure_rate_variable_count: int
    energy_balance_count: int
    exact_discrete_storage_declared: bool
    timestep_prohibited: bool
    objective_permits_nonzero_inventory_rates: bool
    nonzero_rates_fixed_by_constraint: bool
    continuous_pressure_aware_energy_rate_defined: bool
    fixed_pressure_gradient_reuse_permitted: bool
    live_numerical_contract_ready: bool
    decision: str


def audit_pressure_initializer_readiness(
    contract: PressureConsistentInitializerContract,
) -> PressureInitializerReadinessAudit:
    all_state_names = tuple(variable.name for variable in contract.state_variables)
    all_derivative_names = tuple(
        variable.name for variable in contract.derivative_variables
    )
    state_names = tuple(name for name in all_state_names if name.startswith("N["))
    derivative_names = tuple(
        name for name in all_derivative_names if name.startswith("dN[")
    )
    algebraic = contract.algebraic_variables
    energy_states = tuple(
        name for name in all_state_names if name.startswith("U[")
    )
    energy_rates = tuple(
        name for name in all_derivative_names if name.startswith("dU[")
    )
    pressure_variables = tuple(
        variable for variable in algebraic if variable.block == "algebraic_pressure"
    )
    pressure_rates = tuple(
        name for name in all_derivative_names if name.startswith("dP[")
    )
    energy_rows = tuple(
        row for row in contract.constraints if row.block == "energy_balance"
    )
    storage_text = contract.pressure_dae.energy_storage.lower()
    exact_discrete = (
        "u_next" in storage_text
        and "backward-euler" in storage_text
        and "exact" in storage_text
    )
    timestep_prohibited = "without a timestep" not in contract.solve_form.lower()
    # DD-106's solve form is intentionally time-free; check the registered
    # contract rather than relying on derivative notation such as dN/dt.
    timestep_prohibited = timestep_prohibited and not any(
        token in contract.solve_form.lower()
        for token in ("step_seconds", "backward-euler", "backward_euler")
    )
    rate_objective = any(
        term.block == "inventory_rate_norm" and term.dependencies
        for term in contract.selection_objective
    )
    rate_constraints = tuple(
        row
        for row in contract.constraints
        if row.block in {"zero_inventory_rate", "fixed_inventory_rate"}
    )
    nonzero_rates_fixed = bool(rate_constraints) and all(
        any(dependency in derivative_names for dependency in row.dependencies)
        for row in rate_constraints
    )

    # Exact continuous energy storage for algebraic moving pressure requires
    # either independent U/dU coordinates or an explicit pressure-aware
    # reduced derivative. DD-106 registers neither; its inherited statement is
    # deliberately discrete and therefore cannot define this derivative.
    continuous_energy_rate = bool(
        len(energy_states) == len(energy_rows)
        and len(energy_rates) == len(energy_rows)
    )
    objective_permits_nonzero = bool(rate_objective and not nonzero_rates_fixed)
    ready = bool(
        energy_rows
        and pressure_variables
        and timestep_prohibited
        and (
            nonzero_rates_fixed
            or continuous_energy_rate
        )
    )
    return PressureInitializerReadinessAudit(
        component_inventory_state_count=len(state_names),
        component_inventory_rate_count=len(derivative_names),
        independent_energy_state_count=len(energy_states),
        energy_rate_variable_count=len(energy_rates),
        algebraic_pressure_count=len(pressure_variables),
        pressure_rate_variable_count=len(pressure_rates),
        energy_balance_count=len(energy_rows),
        exact_discrete_storage_declared=exact_discrete,
        timestep_prohibited=timestep_prohibited,
        objective_permits_nonzero_inventory_rates=objective_permits_nonzero,
        nonzero_rates_fixed_by_constraint=nonzero_rates_fixed,
        continuous_pressure_aware_energy_rate_defined=continuous_energy_rate,
        fixed_pressure_gradient_reuse_permitted=False,
        live_numerical_contract_ready=ready,
        decision=(
            "authorize_live_numerical_contract"
            if ready
            else "stop_dd106_before_live_execution"
        ),
    )


__all__ = [
    "PressureInitializerReadinessAudit",
    "audit_pressure_initializer_readiness",
]
