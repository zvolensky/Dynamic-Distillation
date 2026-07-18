"""Structural registry for the solved-duty saturated-liquid condenser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import structural_rank

from dynamic_distillation.core_v2.energy_owned_vapor_registry_v1 import (
    EnergyOwnedVaporRegistry,
    StructuralEntry,
    audit_energy_owned_vapor_registry,
    build_energy_owned_vapor_registry,
)


CONDENSER_OWNER = "total_condenser_reflux_drum_boundary"


@dataclass(frozen=True)
class CondenserRegistryAudit:
    unknown_count: int
    residual_count: int
    structural_rank: int
    structural_nullity: int
    zero_unknown_columns: tuple[str, ...]
    zero_residual_rows: tuple[str, ...]
    unregistered_dependencies: tuple[str, ...]
    imported_profile_dependencies: tuple[str, ...]
    condenser_duty_unknown_count: int
    condenser_incipient_vapor_coordinate_count: int
    condenser_bubble_equation_count: int
    fixed_condenser_duty_parameter_present: bool
    base_component_conservation_passed: bool
    base_energy_conservation_passed: bool
    nonlinear_solve_attempted: bool
    live_property_call_attempted: bool
    pass_gate: bool


def _components(component_names: Sequence[str]) -> tuple[str, ...]:
    values = tuple(str(value).strip() for value in component_names)
    if len(values) < 2 or any(not value for value in values):
        raise ValueError("DD-086 requires at least two named components")
    if len(set(values)) != len(values):
        raise ValueError("DD-086 component names must be unique")
    return values


def _incipient_vapor_coordinates(
    components: Sequence[str],
) -> tuple[str, ...]:
    return tuple(
        f"y_bubble[reflux_drum,{component}]"
        for component in tuple(components)[:-1]
    )


def build_condenser_saturated_liquid_registry(
    component_names: Sequence[str],
) -> EnergyOwnedVaporRegistry:
    """Replace fixed condenser duty with solved duty and bubble closure."""
    components = _components(component_names)
    base = build_energy_owned_vapor_registry(components)
    incipient = _incipient_vapor_coordinates(components)
    unknowns = (
        *base.unknowns,
        *(
            StructuralEntry(name, "condenser_incipient_vapor", CONDENSER_OWNER)
            for name in incipient
        ),
        StructuralEntry("Q_C", "solved_condenser_duty", CONDENSER_OWNER),
    )
    bubble_dependencies = (
        "T[reflux_drum]",
        "P[reflux_drum]",
        *(
            f"x[reflux_drum,{component}]"
            for component in components[:-1]
        ),
        *incipient,
    )
    residuals = (
        *base.residuals,
        *(
            StructuralEntry(
                f"condenser_bubble_fugacity[{component}]",
                "condenser_saturated_liquid",
                CONDENSER_OWNER,
                bubble_dependencies,
            )
            for component in components
        ),
    )
    external = tuple(
        parameter for parameter in base.external_parameters if parameter != "Q_C"
    )
    return EnergyOwnedVaporRegistry(
        component_names=components,
        unknowns=tuple(unknowns),
        residuals=tuple(residuals),
        external_parameters=external,
        contributions=base.contributions,
    )


def _pattern(registry: EnergyOwnedVaporRegistry) -> csr_matrix:
    unknown_index = {
        entry.name: index for index, entry in enumerate(registry.unknowns)
    }
    rows: list[int] = []
    columns: list[int] = []
    for row, residual in enumerate(registry.residuals):
        for dependency in residual.dependencies:
            if dependency in unknown_index:
                rows.append(row)
                columns.append(unknown_index[dependency])
    return csr_matrix(
        (
            np.ones(len(rows), dtype=np.int8),
            (rows, columns),
        ),
        shape=(len(registry.residuals), len(registry.unknowns)),
    )


def audit_condenser_saturated_liquid_registry(
    registry: EnergyOwnedVaporRegistry,
) -> CondenserRegistryAudit:
    pattern = _pattern(registry)
    row_nonzero = np.asarray(pattern.getnnz(axis=1)).reshape((-1,))
    column_nonzero = np.asarray(pattern.getnnz(axis=0)).reshape((-1,))
    unknown_names = tuple(entry.name for entry in registry.unknowns)
    residual_names = tuple(entry.name for entry in registry.residuals)
    known = set(unknown_names) | set(registry.external_parameters)
    dependencies = tuple(
        dependency
        for residual in registry.residuals
        for dependency in residual.dependencies
    )
    unregistered = tuple(sorted(set(dependencies) - known))
    imported = tuple(
        sorted(
            {
                dependency
                for dependency in dependencies
                if "profile" in dependency.lower()
                or "chemsep" in dependency.lower()
            }
        )
    )
    rank = int(structural_rank(pattern))
    q_c_count = sum(
        entry.name == "Q_C" and entry.block == "solved_condenser_duty"
        for entry in registry.unknowns
    )
    incipient_count = sum(
        entry.block == "condenser_incipient_vapor"
        for entry in registry.unknowns
    )
    bubble_count = sum(
        entry.block == "condenser_saturated_liquid"
        for entry in registry.residuals
    )
    base_audit = audit_energy_owned_vapor_registry(
        build_energy_owned_vapor_registry(registry.component_names)
    )
    expected = 10 * len(registry.component_names) + 10
    passed = bool(
        len(unknown_names) == expected
        and len(residual_names) == expected
        and rank == expected
        and not np.any(row_nonzero == 0)
        and not np.any(column_nonzero == 0)
        and not unregistered
        and not imported
        and q_c_count == 1
        and incipient_count == len(registry.component_names) - 1
        and bubble_count == len(registry.component_names)
        and "Q_C" not in registry.external_parameters
        and base_audit.component_conservation_passed
        and base_audit.energy_conservation_passed
    )
    return CondenserRegistryAudit(
        unknown_count=len(unknown_names),
        residual_count=len(residual_names),
        structural_rank=rank,
        structural_nullity=max(len(unknown_names) - rank, 0),
        zero_unknown_columns=tuple(
            unknown_names[index]
            for index in np.flatnonzero(column_nonzero == 0)
        ),
        zero_residual_rows=tuple(
            residual_names[index] for index in np.flatnonzero(row_nonzero == 0)
        ),
        unregistered_dependencies=unregistered,
        imported_profile_dependencies=imported,
        condenser_duty_unknown_count=q_c_count,
        condenser_incipient_vapor_coordinate_count=incipient_count,
        condenser_bubble_equation_count=bubble_count,
        fixed_condenser_duty_parameter_present=bool(
            "Q_C" in registry.external_parameters
        ),
        base_component_conservation_passed=bool(
            base_audit.component_conservation_passed
        ),
        base_energy_conservation_passed=bool(
            base_audit.energy_conservation_passed
        ),
        nonlinear_solve_attempted=False,
        live_property_call_attempted=False,
        pass_gate=passed,
    )


__all__ = [
    "CONDENSER_OWNER",
    "CondenserRegistryAudit",
    "audit_condenser_saturated_liquid_registry",
    "build_condenser_saturated_liquid_registry",
]
