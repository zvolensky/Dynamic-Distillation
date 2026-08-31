"""Pressure and overhead-composition control for the Core V3 column."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.sparse import csr_matrix

from .dynamic_dae_contract_v1 import DAERow, SolveVariable
from .structural_rank_v1 import structural_rank_fast
from .vapor_holdup_dynamic_pressure_contract_v1 import CONDENSER_DUTY_PARAMETER
from .vapor_holdup_terminal_control_contract_v1 import (
    VaporHoldupTerminalControlContract,
)


CONTRACT_NAME = "Core V3 - Vapor-Holdup Regulatory Control"
CONTRACT_VERSION = "core-v3-vapor-holdup-regulatory-control-contract-v1"
PRESSURE_RATE = "dI_pressure/dt"
COMPOSITION_RATE = "dI_distillate_composition/dt"
REFLUX_OUTPUT = "log_reflux_composition_output"


@dataclass(frozen=True)
class VaporHoldupRegulatoryControllerSpecification:
    pressure_setpoint_psia: float
    pressure_kc_per_psia: float
    pressure_ti_sec: float
    condenser_duty_reference_BTUph: float
    condenser_duty_ratio_bounds: tuple[float, float]
    composition_component: str
    composition_setpoint_molfrac: float
    composition_kc_per_molfrac: float
    composition_ti_sec: float
    reflux_reference_lbmolph: float
    reflux_ratio_bounds: tuple[float, float]


@dataclass(frozen=True)
class VaporHoldupRegulatoryControlContract:
    predecessor: VaporHoldupTerminalControlContract
    state_coordinates: tuple[str, ...]
    derivative_variables: tuple[SolveVariable, ...]
    algebraic_variables: tuple[SolveVariable, ...]
    rows: tuple[DAERow, ...]
    fixed_parameters: tuple[str, ...]
    regulatory: VaporHoldupRegulatoryControllerSpecification

    @property
    def name(self) -> str:
        return CONTRACT_NAME

    @property
    def version(self) -> str:
        return CONTRACT_VERSION

    @property
    def base(self):
        return self.predecessor.base

    @property
    def geometry(self):
        return self.predecessor.geometry

    @property
    def controllers(self):
        return self.predecessor.controllers


@dataclass(frozen=True)
class VaporHoldupRegulatoryControlAudit:
    solve_variable_count: int
    row_count: int
    structural_rank: int
    structural_nullity: int
    zero_rows: tuple[str, ...]
    zero_columns: tuple[str, ...]
    pressure_controller_row_count: int
    composition_controller_row_count: int
    fixed_condenser_duty_removed: bool
    tuning_valid: bool
    pass_gate: bool


def _composition_dependencies(
    predecessor: VaporHoldupTerminalControlContract,
) -> tuple[str, ...]:
    top = predecessor.base.topology.column.top_volume
    return tuple(
        variable.name
        for variable in predecessor.base.derivative_variables
        if variable.block == "liquid_component_inventory_rate"
        and variable.owner == top
    )


def build_vapor_holdup_regulatory_control_contract(
    predecessor: VaporHoldupTerminalControlContract,
    regulatory: VaporHoldupRegulatoryControllerSpecification,
) -> VaporHoldupRegulatoryControlContract:
    """Replace fixed condenser duty with pressure PI and add reflux composition PI."""
    top = predecessor.base.topology.column.top_volume
    pressure_name = f"P[{top}]"
    pressure_state = f"I_pressure[{top}]"
    composition_state = f"I_distillate_composition[{top}]"
    composition_dependencies = _composition_dependencies(predecessor)
    reflux_owners: set[str] = set()
    for source, destination, symbol in predecessor.base.topology.column.liquid_links:
        if symbol == "R":
            reflux_owners.update((source, destination))

    rows: list[DAERow] = []
    for row in predecessor.rows:
        if row.block == "condenser_duty_specification":
            rows.append(
                DAERow(
                    name=f"pressure_controller_output[{top}]",
                    block="pressure_controller_output",
                    owner=top,
                    solve_dependencies=("Q_C", PRESSURE_RATE, pressure_name),
                    state_dependencies=(pressure_state,),
                )
            )
            continue
        if (
            row.owner in reflux_owners
            and row.block in {"liquid_component_balance", "total_energy_balance"}
        ):
            row = replace(
                row,
                solve_dependencies=tuple(
                    dict.fromkeys((*row.solve_dependencies, REFLUX_OUTPUT))
                ),
            )
        rows.append(row)

    rows.extend(
        (
            DAERow(
                name=f"pressure_controller_integrator[{top}]",
                block="pressure_controller_integrator",
                owner=top,
                solve_dependencies=(PRESSURE_RATE, pressure_name),
                state_dependencies=(pressure_state,),
            ),
            DAERow(
                name=f"distillate_composition_integrator[{top}]",
                block="distillate_composition_controller_integrator",
                owner=top,
                solve_dependencies=(COMPOSITION_RATE, *composition_dependencies),
                state_dependencies=(composition_state,),
            ),
            DAERow(
                name=f"distillate_composition_output[{top}]",
                block="distillate_composition_controller_output",
                owner=top,
                solve_dependencies=(
                    REFLUX_OUTPUT,
                    COMPOSITION_RATE,
                    *composition_dependencies,
                ),
                state_dependencies=(composition_state,),
            ),
        )
    )
    fixed = tuple(
        parameter
        for parameter in predecessor.fixed_parameters
        if parameter != CONDENSER_DUTY_PARAMETER
    )
    fixed = tuple(
        dict.fromkeys(
            (
                *fixed,
                "pressure_controller_tuning",
                "condenser_duty_reference",
                "distillate_composition_controller_tuning",
                "reflux_reference",
            )
        )
    )
    return VaporHoldupRegulatoryControlContract(
        predecessor=predecessor,
        state_coordinates=(
            *predecessor.state_coordinates,
            pressure_state,
            composition_state,
        ),
        derivative_variables=(
            *predecessor.derivative_variables,
            SolveVariable(PRESSURE_RATE, "pressure_controller_integrator_rate", top),
            SolveVariable(
                COMPOSITION_RATE,
                "distillate_composition_controller_integrator_rate",
                top,
            ),
        ),
        algebraic_variables=(
            *predecessor.algebraic_variables,
            SolveVariable(
                REFLUX_OUTPUT,
                "distillate_composition_controller_output",
                top,
            ),
        ),
        rows=tuple(rows),
        fixed_parameters=fixed,
        regulatory=regulatory,
    )


def audit_vapor_holdup_regulatory_control_contract(
    contract: VaporHoldupRegulatoryControlContract,
) -> VaporHoldupRegulatoryControlAudit:
    variables = (*contract.derivative_variables, *contract.algebraic_variables)
    names = tuple(variable.name for variable in variables)
    index = {name: column for column, name in enumerate(names)}
    matrix = np.zeros((len(contract.rows), len(names)), dtype=np.int8)
    for row_index, row in enumerate(contract.rows):
        for dependency in row.solve_dependencies:
            column = index.get(dependency)
            if column is not None:
                matrix[row_index, column] = 1
    sparse = csr_matrix(matrix)
    rank = structural_rank_fast(sparse)
    row_counts = np.asarray(sparse.sum(axis=1)).ravel()
    column_counts = np.asarray(sparse.sum(axis=0)).ravel()
    zero_rows = tuple(
        row.name
        for row, count in zip(contract.rows, row_counts, strict=True)
        if not count
    )
    zero_columns = tuple(
        name for name, count in zip(names, column_counts, strict=True) if not count
    )
    spec = contract.regulatory
    q_lo, q_hi = spec.condenser_duty_ratio_bounds
    r_lo, r_hi = spec.reflux_ratio_bounds
    tuning_valid = bool(
        spec.pressure_setpoint_psia > 0.0
        and spec.pressure_kc_per_psia > 0.0
        and spec.pressure_ti_sec > 0.0
        and spec.condenser_duty_reference_BTUph < 0.0
        and 0.0 < q_lo < 1.0 < q_hi
        and spec.composition_component in contract.base.component_names
        and 0.0 < spec.composition_setpoint_molfrac < 1.0
        and spec.composition_kc_per_molfrac > 0.0
        and spec.composition_ti_sec > 0.0
        and spec.reflux_reference_lbmolph > 0.0
        and 0.0 < r_lo < 1.0 < r_hi
    )
    pressure_rows = sum(row.block.startswith("pressure_controller_") for row in contract.rows)
    composition_rows = sum(
        row.block.startswith("distillate_composition_controller_")
        for row in contract.rows
    )
    fixed_removed = CONDENSER_DUTY_PARAMETER not in contract.fixed_parameters
    passed = bool(
        len(names) == len(contract.rows)
        and len(names) == len(contract.predecessor.rows) + 3
        and rank == len(names)
        and not zero_rows
        and not zero_columns
        and len(set(names)) == len(names)
        and pressure_rows == 2
        and composition_rows == 2
        and fixed_removed
        and tuning_valid
    )
    return VaporHoldupRegulatoryControlAudit(
        solve_variable_count=len(names),
        row_count=len(contract.rows),
        structural_rank=rank,
        structural_nullity=len(names) - rank,
        zero_rows=zero_rows,
        zero_columns=zero_columns,
        pressure_controller_row_count=pressure_rows,
        composition_controller_row_count=composition_rows,
        fixed_condenser_duty_removed=fixed_removed,
        tuning_valid=tuning_valid,
        pass_gate=passed,
    )


__all__ = [
    "COMPOSITION_RATE",
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "PRESSURE_RATE",
    "REFLUX_OUTPUT",
    "VaporHoldupRegulatoryControlAudit",
    "VaporHoldupRegulatoryControlContract",
    "VaporHoldupRegulatoryControllerSpecification",
    "audit_vapor_holdup_regulatory_control_contract",
    "build_vapor_holdup_regulatory_control_contract",
]
