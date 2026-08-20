"""Dynamic top-pressure successor for the vapor-holdup level-control contract."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.sparse import csr_matrix

from .dynamic_dae_contract_v1 import DAERow
from .structural_rank_v1 import structural_rank_fast
from .vapor_holdup_dae_contract_v1 import TOP_PRESSURE_PARAMETER
from .vapor_holdup_terminal_control_contract_v1 import (
    VaporHoldupTerminalControlContract,
)


CONTRACT_NAME = "Core V3 - Vapor-Holdup Dynamic Top Pressure"
CONTRACT_VERSION = "core-v3-vapor-holdup-dynamic-top-pressure-contract-v1"
CONDENSER_DUTY_PARAMETER = "Q_C_specified"


@dataclass(frozen=True)
class VaporHoldupDynamicPressureAudit:
    solve_variable_count: int
    row_count: int
    structural_rank: int
    structural_nullity: int
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    duplicate_variable_names: tuple[str, ...]
    pressure_anchor_count: int
    condenser_duty_specification_count: int
    condenser_duty_variable_count: int
    top_pressure_variable_count: int
    top_pressure_coupled_outside_anchor: bool
    condenser_duty_coupled_to_energy_and_specification: bool
    fixed_top_pressure_removed: bool
    fixed_condenser_duty_present: bool
    preparation_only: bool
    pass_gate: bool


def _duty_row(row: DAERow, top_volume: str) -> DAERow:
    if row.block != "pressure_anchor":
        return row
    return DAERow(
        name=f"condenser_duty_specification[{top_volume}]",
        block="condenser_duty_specification",
        owner=top_volume,
        solve_dependencies=("Q_C",),
        state_dependencies=(),
    )


def build_vapor_holdup_dynamic_pressure_contract(
    predecessor: VaporHoldupTerminalControlContract,
) -> VaporHoldupTerminalControlContract:
    """Replace the fixed top-pressure equation with a fixed-duty equation."""
    top_volume = predecessor.base.topology.column.top_volume
    base_rows = tuple(_duty_row(row, top_volume) for row in predecessor.base.rows)
    rows = tuple(_duty_row(row, top_volume) for row in predecessor.rows)
    base_parameters = tuple(
        parameter
        for parameter in predecessor.base.fixed_parameters
        if parameter != TOP_PRESSURE_PARAMETER
    )
    fixed_parameters = tuple(
        parameter
        for parameter in predecessor.fixed_parameters
        if parameter != TOP_PRESSURE_PARAMETER
    )
    successor_base = replace(
        predecessor.base,
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        rows=base_rows,
        fixed_parameters=tuple(dict.fromkeys((*base_parameters, CONDENSER_DUTY_PARAMETER))),
    )
    return replace(
        predecessor,
        name=CONTRACT_NAME,
        version=CONTRACT_VERSION,
        base=successor_base,
        rows=rows,
        fixed_parameters=tuple(
            dict.fromkeys((*fixed_parameters, CONDENSER_DUTY_PARAMETER))
        ),
    )


def _incidence(
    contract: VaporHoldupTerminalControlContract,
) -> tuple[csr_matrix, tuple[str, ...]]:
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    matrix = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            column = index.get(dependency)
            if column is not None:
                matrix[row_index, column] = 1
    return csr_matrix(matrix), names


def audit_vapor_holdup_dynamic_pressure_contract(
    contract: VaporHoldupTerminalControlContract,
) -> VaporHoldupDynamicPressureAudit:
    matrix, names = _incidence(contract)
    rank = structural_rank_fast(matrix)
    row_counts = np.asarray(matrix.sum(axis=1)).ravel()
    column_counts = np.asarray(matrix.sum(axis=0)).ravel()
    zero_rows = tuple(
        row.name
        for row, count in zip(contract.rows, row_counts, strict=True)
        if not count
    )
    zero_columns = tuple(
        name for name, count in zip(names, column_counts, strict=True) if not count
    )
    duplicates = tuple(sorted({name for name in names if names.count(name) > 1}))
    top_volume = contract.base.topology.column.top_volume
    pressure_name = f"P[{top_volume}]"
    pressure_rows = tuple(
        row for row in contract.rows if pressure_name in row.solve_dependencies
    )
    duty_rows = tuple(
        row for row in contract.rows if "Q_C" in row.solve_dependencies
    )
    pressure_anchor_count = sum(row.block == "pressure_anchor" for row in contract.rows)
    duty_specification_count = sum(
        row.block == "condenser_duty_specification" for row in contract.rows
    )
    duty_variable_count = names.count("Q_C")
    top_pressure_count = names.count(pressure_name)
    preparation_only = not any(
        (
            contract.property_evaluation_attempted,
            contract.nonlinear_solve_attempted,
            contract.dynamic_integration_attempted,
        )
    )
    passed = bool(
        len(names) == len(contract.rows)
        and rank == len(names)
        and not zero_rows
        and not zero_columns
        and not duplicates
        and pressure_anchor_count == 0
        and duty_specification_count == 1
        and duty_variable_count == 1
        and top_pressure_count == 1
        and pressure_rows
        and all(row.block != "pressure_anchor" for row in pressure_rows)
        and {row.block for row in duty_rows}
        >= {"total_energy_balance", "condenser_duty_specification"}
        and TOP_PRESSURE_PARAMETER not in contract.fixed_parameters
        and CONDENSER_DUTY_PARAMETER in contract.fixed_parameters
        and preparation_only
    )
    return VaporHoldupDynamicPressureAudit(
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        zero_rows=zero_rows,
        zero_columns=zero_columns,
        duplicate_variable_names=duplicates,
        pressure_anchor_count=pressure_anchor_count,
        condenser_duty_specification_count=duty_specification_count,
        condenser_duty_variable_count=duty_variable_count,
        top_pressure_variable_count=top_pressure_count,
        top_pressure_coupled_outside_anchor=bool(
            pressure_rows and all(row.block != "pressure_anchor" for row in pressure_rows)
        ),
        condenser_duty_coupled_to_energy_and_specification=bool(
            {row.block for row in duty_rows}
            >= {"total_energy_balance", "condenser_duty_specification"}
        ),
        fixed_top_pressure_removed=TOP_PRESSURE_PARAMETER not in contract.fixed_parameters,
        fixed_condenser_duty_present=CONDENSER_DUTY_PARAMETER in contract.fixed_parameters,
        preparation_only=preparation_only,
        pass_gate=passed,
    )


__all__ = [
    "CONDENSER_DUTY_PARAMETER",
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "VaporHoldupDynamicPressureAudit",
    "audit_vapor_holdup_dynamic_pressure_contract",
    "build_vapor_holdup_dynamic_pressure_contract",
]
