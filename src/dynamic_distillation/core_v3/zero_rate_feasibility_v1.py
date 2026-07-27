"""Structural zero-rate feasibility audit for the Core V3 initializer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix, vstack
from scipy.sparse.csgraph import maximum_bipartite_matching, structural_rank

from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_contract_v1 import (
    build_conserved_nu_pressure_initializer_contract,
)
from dynamic_distillation.core_v3.conserved_nu_pressure_initializer_numerical_v1 import (
    initializer_constraint_pattern,
)


RATE_BLOCKS = frozenset(("component_inventory_rate", "internal_energy_rate"))
GLOBAL_TARGET_BLOCKS = frozenset(("global_component_inventory", "global_stored_energy"))
TERMINAL_TARGET_BLOCK = "terminal_total_inventory"


@dataclass(frozen=True)
class ZeroRateFeasibilityAudit:
    component_count: int
    primal_count: int
    rate_count: int
    zero_rate_unknown_count: int
    dae_row_count: int
    retained_target_row_count: int
    zero_rate_dae_shape: tuple[int, int]
    zero_rate_dae_structural_rank: int
    all_target_shape: tuple[int, int]
    all_target_structural_rank: int
    all_target_equation_surplus: int
    augmented_shape: tuple[int, int]
    augmented_structural_rank: int
    augmented_equation_surplus: int
    unmatched_all_target_rows: tuple[str, ...]
    global_target_rows: tuple[str, ...]
    terminal_target_rows: tuple[str, ...]
    recommended_shape: tuple[int, int]
    recommended_structural_rank: int
    recommended_equation_surplus: int
    released_global_target_count: int
    terminal_scale_freedom_count: int
    exact_zero_rate_with_all_targets_generically_overdetermined: bool
    zero_rate_dae_core_structurally_viable: bool
    pass_gate: bool


def audit_zero_rate_feasibility(component_names: tuple[str, ...]) -> ZeroRateFeasibilityAudit:
    contract = build_conserved_nu_pressure_initializer_contract(component_names)
    variables = (*contract.state_variables, *contract.derivative_variables, *contract.algebraic_variables)
    pattern = np.asarray(initializer_constraint_pattern(contract), dtype=bool)
    rate_columns = tuple(index for index, variable in enumerate(variables) if variable.block in RATE_BLOCKS)
    nonrate_columns = tuple(index for index in range(len(variables)) if index not in rate_columns)
    dae_rows = tuple(range(len(contract.pressure_dae.rows)))
    global_rows = tuple(index for index, row in enumerate(contract.constraints) if row.block in GLOBAL_TARGET_BLOCKS)
    terminal_rows = tuple(index for index, row in enumerate(contract.constraints) if row.block == TERMINAL_TARGET_BLOCK)
    target_rows = (*global_rows, *terminal_rows)

    dae = csr_matrix(pattern[np.ix_(dae_rows, nonrate_columns)])
    all_targets = csr_matrix(pattern[:, nonrate_columns])
    recommended = csr_matrix(pattern[np.ix_((*dae_rows, *terminal_rows), nonrate_columns)])

    zero_rows = np.zeros((len(rate_columns), len(variables)), dtype=bool)
    for row, column in enumerate(rate_columns):
        zero_rows[row, column] = True
    augmented = vstack(
        (
            csr_matrix(pattern[np.asarray(dae_rows)]),
            csr_matrix(zero_rows),
            csr_matrix(pattern[np.asarray(target_rows)]),
        ),
        format="csr",
    )
    matching = maximum_bipartite_matching(all_targets, perm_type="column")
    unmatched = tuple(
        contract.constraints[index].name for index in np.flatnonzero(matching < 0)
    )
    dae_rank = int(structural_rank(dae))
    all_rank = int(structural_rank(all_targets))
    augmented_rank = int(structural_rank(augmented))
    recommended_rank = int(structural_rank(recommended))
    all_surplus = all_targets.shape[0] - all_targets.shape[1]
    augmented_surplus = augmented.shape[0] - augmented.shape[1]
    recommended_surplus = recommended.shape[0] - recommended.shape[1]
    expected_global_count = len(component_names) + 1
    expected_terminal_count = 2
    zero_core_viable = dae.shape[0] == dae.shape[1] == dae_rank
    overdetermined = bool(
        all_rank == all_targets.shape[1]
        and all_surplus == len(component_names) + 3
        and set(unmatched)
        == {contract.constraints[index].name for index in target_rows}
    )
    passed = bool(
        len(rate_columns) == len(contract.state_variables)
        and zero_core_viable
        and overdetermined
        and augmented_rank == augmented.shape[1] == len(variables)
        and augmented_surplus == len(component_names) + 3
        and len(global_rows) == expected_global_count
        and len(terminal_rows) == expected_terminal_count
        and recommended_rank == recommended.shape[1]
        and recommended_surplus == expected_terminal_count
    )
    return ZeroRateFeasibilityAudit(
        component_count=len(component_names),
        primal_count=len(variables),
        rate_count=len(rate_columns),
        zero_rate_unknown_count=len(nonrate_columns),
        dae_row_count=len(dae_rows),
        retained_target_row_count=len(target_rows),
        zero_rate_dae_shape=dae.shape,
        zero_rate_dae_structural_rank=dae_rank,
        all_target_shape=all_targets.shape,
        all_target_structural_rank=all_rank,
        all_target_equation_surplus=all_surplus,
        augmented_shape=augmented.shape,
        augmented_structural_rank=augmented_rank,
        augmented_equation_surplus=augmented_surplus,
        unmatched_all_target_rows=unmatched,
        global_target_rows=tuple(contract.constraints[index].name for index in global_rows),
        terminal_target_rows=tuple(contract.constraints[index].name for index in terminal_rows),
        recommended_shape=recommended.shape,
        recommended_structural_rank=recommended_rank,
        recommended_equation_surplus=recommended_surplus,
        released_global_target_count=len(global_rows),
        terminal_scale_freedom_count=len(terminal_rows),
        exact_zero_rate_with_all_targets_generically_overdetermined=overdetermined,
        zero_rate_dae_core_structurally_viable=zero_core_viable,
        pass_gate=passed,
    )


__all__ = ["ZeroRateFeasibilityAudit", "audit_zero_rate_feasibility"]
