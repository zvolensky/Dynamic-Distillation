"""Residual, ownership, rank, and conservation audits for DD-077."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.sparse import csr_matrix

from dynamic_distillation.core_v2.reduced_column_spec_v1 import ReducedColumnSpec
from dynamic_distillation.core_v2.reduced_topology_v1 import (
    ExternalStream,
    InternalStream,
)
from dynamic_distillation.core_v2.reduced_state_registry_v1 import (
    StateUnknown,
    build_state_unknowns,
    composition_unknowns,
    independent_components,
)


@dataclass(frozen=True)
class ResidualEntry:
    name: str
    block: str
    owner: str
    units: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class BalanceContribution:
    residual_name: str
    balance_family: str
    component: str | None
    stream_id: str
    internal: bool
    coefficient: int


@dataclass(frozen=True)
class ReducedResidualRegistry:
    spec: ReducedColumnSpec
    unknowns: tuple[StateUnknown, ...]
    residuals: tuple[ResidualEntry, ...]
    balance_contributions: tuple[BalanceContribution, ...]


@dataclass(frozen=True)
class StructuralAudit:
    unknown_count: int
    residual_count: int
    square: bool
    structural_rank: int
    structural_nullity: int
    unmatched_unknowns: tuple[str, ...]
    unmatched_residuals: tuple[str, ...]
    empty_unknown_columns: tuple[str, ...]
    empty_residual_rows: tuple[str, ...]
    duplicate_unknown_names: tuple[str, ...]
    duplicate_residual_names: tuple[str, ...]
    missing_closure_residuals: tuple[str, ...]
    unknown_counts_by_block: dict[str, int]
    residual_counts_by_block: dict[str, int]
    pass_gate: bool


@dataclass(frozen=True)
class OwnershipAudit:
    prescribed_pressure_is_parameter_only: bool
    prescribed_pressure_is_used: bool
    prescribed_vapor_is_parameter_only: bool
    prescribed_vapor_is_used: bool
    francis_tray_liquid_flows: tuple[str, ...]
    non_francis_tray_liquid_flows: tuple[str, ...]
    duplicate_flow_owners: tuple[str, ...]
    imported_profile_dependencies: tuple[str, ...]
    unregistered_dependencies: tuple[str, ...]
    pass_gate: bool


@dataclass(frozen=True)
class ConservationAudit:
    component_internal_telescoping: bool
    energy_internal_telescoping: bool
    component_failures: tuple[str, ...]
    energy_failures: tuple[str, ...]
    pass_gate: bool


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _counts_by_block(
    entries: Sequence[StateUnknown | ResidualEntry],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.block] = counts.get(entry.block, 0) + 1
    return counts


def _phase_dependencies(
    spec: ReducedColumnSpec,
    *,
    volume_id: str,
    phase: str,
) -> tuple[str, ...]:
    if phase == "liquid":
        return (
            f"T[{volume_id}]",
            f"P[{volume_id}]",
            *composition_unknowns(spec, phase="x", volume_id=volume_id),
        )
    return (
        f"T[{volume_id}]",
        f"P[{volume_id}]",
        *composition_unknowns(spec, phase="y", volume_id=volume_id),
    )


def build_reduced_residual_registry(
    spec: ReducedColumnSpec,
) -> ReducedResidualRegistry:
    unknowns = build_state_unknowns(spec)
    residuals: list[ResidualEntry] = []
    contributions: list[BalanceContribution] = []
    independent = independent_components(spec)

    def add_residual(
        name: str,
        block: str,
        owner: str,
        units: str,
        dependencies: Iterable[str],
    ) -> None:
        residuals.append(
            ResidualEntry(
                name=name,
                block=block,
                owner=owner,
                units=units,
                dependencies=tuple(dict.fromkeys(dependencies)),
            )
        )

    internal_by_volume: dict[str, list[tuple[InternalStream, int]]] = {
        node: [] for node in spec.topology.volume_ids
    }
    for stream in spec.topology.internal_streams:
        internal_by_volume[stream.source_volume].append((stream, -1))
        internal_by_volume[stream.destination_volume].append((stream, 1))
    external_by_volume: dict[str, list[tuple[ExternalStream, int]]] = {
        node: [] for node in spec.topology.volume_ids
    }
    for stream in spec.topology.external_streams:
        sign = 1 if stream.direction == "in" else -1
        external_by_volume[stream.volume_id].append((stream, sign))

    for volume in spec.topology.control_volumes:
        node = volume.volume_id
        x_dependencies = composition_unknowns(
            spec, phase="x", volume_id=node
        )
        for component in spec.component_names:
            add_residual(
                f"component_reconstruction[{node},{component}]",
                "component_reconstruction",
                node,
                "lbmol",
                (
                    f"N[{node},{component}]",
                    f"NL[{node}]",
                    *x_dependencies,
                ),
            )
        add_residual(
            f"energy_reconstruction[{node}]",
            "energy_reconstruction",
            node,
            "BTU",
            (
                f"U[{node}]",
                f"NL[{node}]",
                f"T[{node}]",
                f"P[{node}]",
                *x_dependencies,
            ),
        )
        if volume.equilibrium_vapor_outlet:
            y_dependencies = composition_unknowns(
                spec, phase="y", volume_id=node
            )
            for component in independent:
                add_residual(
                    f"phase_equilibrium[{node},{component}]",
                    "phase_equilibrium",
                    node,
                    "dimensionless",
                    (
                        f"T[{node}]",
                        f"P[{node}]",
                        *x_dependencies,
                        *y_dependencies,
                    ),
                )

        for component in spec.component_names:
            dependencies: list[str] = []
            residual_name = f"component_balance[{node},{component}]"
            for stream, sign in internal_by_volume[node]:
                dependencies.append(stream.flow_symbol)
                source = stream.source_volume
                phase = (
                    "liquid"
                    if stream.phase == "liquid"
                    else "vapor"
                )
                dependencies.extend(
                    composition_unknowns(
                        spec,
                        phase="x" if phase == "liquid" else "y",
                        volume_id=source,
                    )
                )
                contributions.append(
                    BalanceContribution(
                        residual_name,
                        "component",
                        component,
                        stream.stream_id,
                        True,
                        sign,
                    )
                )
            for stream, sign in external_by_volume[node]:
                dependencies.append(
                    (
                        f"F_component[{component}]"
                        if stream.phase == "feed"
                        else stream.flow_symbol
                    )
                )
                if stream.phase == "liquid":
                    dependencies.extend(x_dependencies)
                contributions.append(
                    BalanceContribution(
                        residual_name,
                        "component",
                        component,
                        stream.stream_id,
                        False,
                        sign,
                    )
                )
            add_residual(
                residual_name,
                "component_balance",
                node,
                "lbmol_per_h",
                dependencies,
            )

        energy_dependencies: list[str] = []
        energy_name = f"energy_balance[{node}]"
        for stream, sign in internal_by_volume[node]:
            energy_dependencies.append(stream.flow_symbol)
            phase = "liquid" if stream.phase == "liquid" else "vapor"
            energy_dependencies.extend(
                _phase_dependencies(
                    spec,
                    volume_id=stream.source_volume,
                    phase=phase,
                )
            )
            contributions.append(
                BalanceContribution(
                    energy_name,
                    "energy",
                    None,
                    stream.stream_id,
                    True,
                    sign,
                )
            )
        for stream, sign in external_by_volume[node]:
            if stream.phase == "feed":
                energy_dependencies.append("H_feed")
            else:
                energy_dependencies.append(stream.flow_symbol)
                energy_dependencies.extend(
                    _phase_dependencies(
                        spec,
                        volume_id=node,
                        phase="liquid",
                    )
                )
            contributions.append(
                BalanceContribution(
                    energy_name,
                    "energy",
                    None,
                    stream.stream_id,
                    False,
                    sign,
                )
            )
        if volume.role == "reflux_drum":
            energy_dependencies.append("Q_C")
        if volume.role == "combined_reboiler_sump":
            energy_dependencies.append("Q_R")
        add_residual(
            energy_name,
            "energy_balance",
            node,
            "BTU_per_h",
            energy_dependencies,
        )
        if volume.role in {"reflux_drum", "combined_reboiler_sump"}:
            add_residual(
                f"terminal_level[{node}]",
                "terminal_level_specification",
                node,
                "lbmol",
                (f"NL[{node}]", f"NL_target[{node}]"),
            )

    for stream in spec.topology.internal_streams:
        if not stream.hydraulic_unknown:
            continue
        node = stream.source_volume
        add_residual(
            f"francis_hydraulics[{node}]",
            "francis_hydraulics",
            node,
            "lbmol_per_h",
            (
                stream.flow_symbol,
                f"NL[{node}]",
                f"T[{node}]",
                f"P[{node}]",
                *composition_unknowns(spec, phase="x", volume_id=node),
                f"francis_geometry[{node}]",
            ),
        )

    return ReducedResidualRegistry(
        spec=spec,
        unknowns=unknowns,
        residuals=tuple(residuals),
        balance_contributions=tuple(contributions),
    )


def structural_pattern(registry: ReducedResidualRegistry) -> csr_matrix:
    unknown_index = {
        unknown.name: index for index, unknown in enumerate(registry.unknowns)
    }
    rows: list[int] = []
    columns: list[int] = []
    for row, residual in enumerate(registry.residuals):
        for dependency in residual.dependencies:
            column = unknown_index.get(dependency)
            if column is not None:
                rows.append(row)
                columns.append(column)
    return csr_matrix(
        (
            np.ones(len(rows), dtype=np.int8),
            (rows, columns),
        ),
        shape=(len(registry.residuals), len(registry.unknowns)),
    )


def _deterministic_matching(
    pattern: csr_matrix,
) -> tuple[np.ndarray, np.ndarray]:
    matrix = pattern.tocsr()
    row_count, column_count = matrix.shape
    column_to_row = np.full(column_count, -1, dtype=int)

    def augment(row: int, seen: np.ndarray) -> bool:
        for column in matrix.indices[
            int(matrix.indptr[row]) : int(matrix.indptr[row + 1])
        ]:
            column = int(column)
            if seen[column]:
                continue
            seen[column] = True
            previous = int(column_to_row[column])
            if previous < 0 or augment(previous, seen):
                column_to_row[column] = row
                return True
        return False

    for row in range(row_count):
        augment(row, np.zeros(column_count, dtype=bool))
    row_to_column = np.full(row_count, -1, dtype=int)
    for column, row in enumerate(column_to_row):
        if row >= 0:
            row_to_column[row] = column
    return row_to_column, column_to_row


def audit_structure(registry: ReducedResidualRegistry) -> StructuralAudit:
    pattern = structural_pattern(registry)
    unknown_names = tuple(entry.name for entry in registry.unknowns)
    residual_names = tuple(entry.name for entry in registry.residuals)
    row_match, column_match = _deterministic_matching(pattern)
    rank = int(np.count_nonzero(row_match >= 0))
    empty_rows = tuple(
        residual_names[index]
        for index in np.flatnonzero(np.asarray(pattern.getnnz(axis=1)) == 0)
    )
    empty_columns = tuple(
        unknown_names[index]
        for index in np.flatnonzero(np.asarray(pattern.getnnz(axis=0)) == 0)
    )
    residual_name_set = set(residual_names)
    missing_closures = tuple(
        unknown.name
        for unknown in registry.unknowns
        if unknown.closure_residual not in residual_name_set
    )
    duplicate_unknowns = _unique(unknown_names)
    duplicate_residuals = _unique(residual_names)
    unknown_count = len(unknown_names)
    residual_count = len(residual_names)
    passed = bool(
        unknown_count == residual_count
        and rank == unknown_count
        and not empty_rows
        and not empty_columns
        and not duplicate_unknowns
        and not duplicate_residuals
        and not missing_closures
    )
    return StructuralAudit(
        unknown_count=unknown_count,
        residual_count=residual_count,
        square=unknown_count == residual_count,
        structural_rank=rank,
        structural_nullity=max(unknown_count - rank, 0),
        unmatched_unknowns=tuple(
            unknown_names[index]
            for index in np.flatnonzero(column_match < 0)
        ),
        unmatched_residuals=tuple(
            residual_names[index] for index in np.flatnonzero(row_match < 0)
        ),
        empty_unknown_columns=empty_columns,
        empty_residual_rows=empty_rows,
        duplicate_unknown_names=duplicate_unknowns,
        duplicate_residual_names=duplicate_residuals,
        missing_closure_residuals=missing_closures,
        unknown_counts_by_block=_counts_by_block(registry.unknowns),
        residual_counts_by_block=_counts_by_block(registry.residuals),
        pass_gate=passed,
    )


def audit_ownership(registry: ReducedResidualRegistry) -> OwnershipAudit:
    unknown_names = {unknown.name for unknown in registry.unknowns}
    external = set(registry.spec.external_parameters)
    flow_owners: dict[str, set[str]] = {}
    for stream in (
        *registry.spec.topology.internal_streams,
        *registry.spec.topology.external_streams,
    ):
        flow_owners.setdefault(stream.flow_symbol, set()).add(stream.flow_owner)
    duplicate_flow_owners = tuple(
        symbol
        for symbol, owners in flow_owners.items()
        if len(owners) != 1
    )
    tray_liquid = tuple(
        stream.flow_symbol
        for stream in registry.spec.topology.internal_streams
        if stream.hydraulic_unknown
    )
    non_francis = tuple(
        stream.flow_symbol
        for stream in registry.spec.topology.internal_streams
        if stream.hydraulic_unknown
        and stream.flow_owner != "francis_hydraulics"
    )
    dependencies = tuple(
        dependency
        for residual in registry.residuals
        for dependency in residual.dependencies
    )
    imported_profile = tuple(
        sorted(
            {
                dependency
                for dependency in dependencies
                if "profile" in dependency.lower()
                or "chemsep" in dependency.lower()
            }
        )
    )
    unregistered = tuple(
        sorted(
            {
                dependency
                for dependency in dependencies
                if dependency not in unknown_names and dependency not in external
            }
        )
    )
    pressure_only = all(
        parameter not in unknown_names
        for parameter in registry.spec.pressure_parameters
    )
    pressure_used = all(
        parameter in dependencies
        for parameter in registry.spec.pressure_parameters
    )
    vapor_only = all(
        parameter not in unknown_names
        for parameter in registry.spec.vapor_flow_parameters
    )
    vapor_used = all(
        parameter in dependencies
        for parameter in registry.spec.vapor_flow_parameters
    )
    passed = bool(
        pressure_only
        and pressure_used
        and vapor_only
        and vapor_used
        and not non_francis
        and not duplicate_flow_owners
        and not imported_profile
        and not unregistered
    )
    return OwnershipAudit(
        prescribed_pressure_is_parameter_only=pressure_only,
        prescribed_pressure_is_used=pressure_used,
        prescribed_vapor_is_parameter_only=vapor_only,
        prescribed_vapor_is_used=vapor_used,
        francis_tray_liquid_flows=tray_liquid,
        non_francis_tray_liquid_flows=non_francis,
        duplicate_flow_owners=duplicate_flow_owners,
        imported_profile_dependencies=imported_profile,
        unregistered_dependencies=unregistered,
        pass_gate=passed,
    )


def audit_conservation(
    registry: ReducedResidualRegistry,
) -> ConservationAudit:
    component_failures: list[str] = []
    energy_failures: list[str] = []
    internal_ids = tuple(
        stream.stream_id for stream in registry.spec.topology.internal_streams
    )
    for stream_id in internal_ids:
        for component in registry.spec.component_names:
            terms = tuple(
                contribution.coefficient
                for contribution in registry.balance_contributions
                if contribution.internal
                and contribution.balance_family == "component"
                and contribution.stream_id == stream_id
                and contribution.component == component
            )
            if len(terms) != 2 or sum(terms) != 0:
                component_failures.append(f"{stream_id}:{component}")
        terms = tuple(
            contribution.coefficient
            for contribution in registry.balance_contributions
            if contribution.internal
            and contribution.balance_family == "energy"
            and contribution.stream_id == stream_id
        )
        if len(terms) != 2 or sum(terms) != 0:
            energy_failures.append(stream_id)
    return ConservationAudit(
        component_internal_telescoping=not component_failures,
        energy_internal_telescoping=not energy_failures,
        component_failures=tuple(component_failures),
        energy_failures=tuple(energy_failures),
        pass_gate=not component_failures and not energy_failures,
    )
