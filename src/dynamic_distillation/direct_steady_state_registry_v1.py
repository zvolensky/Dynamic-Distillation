"""Deterministic DD-071 registry for the direct conserved steady-state system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class UnknownEntry:
    name: str
    block: str
    owner: str
    units: str
    closure_residual: str | None


@dataclass(frozen=True)
class ResidualEntry:
    name: str
    block: str
    owner: str
    units: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class DirectSteadyStateRegistry:
    component_names: tuple[str, ...]
    active_stage_ids: tuple[str, ...]
    unknowns: tuple[UnknownEntry, ...]
    residuals: tuple[ResidualEntry, ...]
    deliberate_eliminations: tuple[str, ...]


@dataclass(frozen=True)
class RegistryStructureAudit:
    unknown_count: int
    residual_count: int
    equation_count_difference: int
    square: bool
    structural_rank: int
    structural_nullity: int
    structurally_empty_rows: tuple[str, ...]
    structurally_empty_columns: tuple[str, ...]
    unmatched_unknowns: tuple[str, ...]
    unmatched_residuals: tuple[str, ...]
    missing_closure_owners: tuple[str, ...]
    duplicate_unknown_names: tuple[str, ...]
    duplicate_residual_names: tuple[str, ...]
    unknown_counts_by_block: dict[str, int]
    residual_counts_by_block: dict[str, int]
    pass_gate: bool


def _independent_components(component_names: Sequence[str]) -> tuple[str, ...]:
    names = tuple(str(name) for name in component_names)
    if len(names) < 2:
        raise ValueError("direct steady-state registry requires at least two components")
    if len(set(names)) != len(names):
        raise ValueError("component names must be unique")
    return names[:-1]


def _unique_names(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        name = str(value)
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    return tuple(duplicates)


def _block_counts(entries: Sequence[UnknownEntry | ResidualEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[str(entry.block)] = counts.get(str(entry.block), 0) + 1
    return counts


def build_direct_steady_state_registry(
    *,
    component_names: Sequence[str],
    active_stage_ids: Sequence[str | int],
) -> DirectSteadyStateRegistry:
    """Build the proposed DD-071 equations without adding a missing specification."""
    components = tuple(str(name) for name in component_names)
    independent = _independent_components(components)
    stages = tuple(str(stage) for stage in active_stage_ids)
    if not stages:
        raise ValueError("at least one physical tray is required")
    if len(set(stages)) != len(stages):
        raise ValueError("active stage identifiers must be unique")

    drum = "reflux_drum"
    reboiler = "partial_reboiler"
    sump = "bottoms_sump"
    tray_nodes = tuple(f"tray_{stage}" for stage in stages)
    two_phase_nodes = (drum, *tray_nodes, reboiler)
    all_nodes = (*two_phase_nodes, sump)

    unknowns: list[UnknownEntry] = []
    residuals: list[ResidualEntry] = []

    def add_unknown(
        name: str,
        block: str,
        owner: str,
        units: str,
        closure_residual: str | None,
    ) -> None:
        unknowns.append(
            UnknownEntry(
                name=name,
                block=block,
                owner=owner,
                units=units,
                closure_residual=closure_residual,
            )
        )

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
                dependencies=tuple(dict.fromkeys(str(dep) for dep in dependencies)),
            )
        )

    def n_name(node: str, component: str) -> str:
        return f"N[{node},{component}]"

    def x_name(node: str, component: str) -> str:
        return f"x[{node},{component}]"

    def y_name(node: str, component: str) -> str:
        return f"y[{node},{component}]"

    def phase_dependencies(node: str) -> tuple[str, ...]:
        return (
            f"T[{node}]",
            f"P[{node}]",
            f"NL[{node}]",
            f"NV[{node}]",
            *(x_name(node, comp) for comp in independent),
            *(y_name(node, comp) for comp in independent),
        )

    for node in two_phase_nodes:
        for component in components:
            add_unknown(
                n_name(node, component),
                "conserved_component",
                node,
                "lbmol",
                f"component_closure[{node},{component}]",
            )
        add_unknown(
            f"U[{node}]",
            "conserved_energy",
            node,
            "BTU",
            f"energy_closure[{node}]",
        )
        add_unknown(f"T[{node}]", "local_thermo", node, "F", f"energy_closure[{node}]")
        add_unknown(f"P[{node}]", "local_thermo", node, "psia", f"volume_closure[{node}]")
        add_unknown(f"NL[{node}]", "phase_amount", node, "lbmol", f"volume_closure[{node}]")
        add_unknown(f"NV[{node}]", "phase_amount", node, "lbmol", f"volume_closure[{node}]")
        for component in independent:
            add_unknown(
                x_name(node, component),
                "liquid_composition",
                node,
                "mole_fraction",
                f"equilibrium[{node},{component}]",
            )
            add_unknown(
                y_name(node, component),
                "vapor_composition",
                node,
                "mole_fraction",
                f"equilibrium[{node},{component}]",
            )

        phase_deps = phase_dependencies(node)
        for component in components:
            add_residual(
                f"component_closure[{node},{component}]",
                "local_component_closure",
                node,
                "lbmol",
                (
                    n_name(node, component),
                    f"NL[{node}]",
                    f"NV[{node}]",
                    *(x_name(node, comp) for comp in independent),
                    *(y_name(node, comp) for comp in independent),
                ),
            )
        add_residual(
            f"energy_closure[{node}]",
            "local_energy_closure",
            node,
            "BTU",
            (f"U[{node}]", *phase_deps),
        )
        add_residual(
            f"volume_closure[{node}]",
            "local_volume_closure",
            node,
            "ft3",
            phase_deps,
        )
        for component in components:
            add_residual(
                f"equilibrium[{node},{component}]",
                "local_equilibrium",
                node,
                "dimensionless",
                (
                    f"T[{node}]",
                    f"P[{node}]",
                    *(x_name(node, comp) for comp in independent),
                    *(y_name(node, comp) for comp in independent),
                ),
            )

    for component in components:
        add_unknown(
            n_name(sump, component),
            "conserved_component",
            sump,
            "lbmol",
            f"component_closure[{sump},{component}]",
        )
    add_unknown(
        f"U[{sump}]",
        "conserved_energy",
        sump,
        "BTU",
        f"energy_closure[{sump}]",
    )
    add_unknown(f"T[{sump}]", "local_thermo", sump, "F", f"energy_closure[{sump}]")
    add_unknown(f"P[{sump}]", "local_thermo", sump, "psia", "sump_pressure_equal_reboiler")
    add_unknown(f"NL[{sump}]", "phase_amount", sump, "lbmol", "spec_sump_level")
    for component in independent:
        add_unknown(
            x_name(sump, component),
            "liquid_composition",
            sump,
            "mole_fraction",
            f"component_closure[{sump},{component}]",
        )
    for component in components:
        add_residual(
            f"component_closure[{sump},{component}]",
            "local_component_closure",
            sump,
            "lbmol",
            (
                n_name(sump, component),
                f"NL[{sump}]",
                *(x_name(sump, comp) for comp in independent),
            ),
        )
    add_residual(
        f"energy_closure[{sump}]",
        "local_energy_closure",
        sump,
        "BTU",
        (
            f"U[{sump}]",
            f"T[{sump}]",
            f"P[{sump}]",
            f"NL[{sump}]",
            *(x_name(sump, comp) for comp in independent),
        ),
    )

    liquid_flow_names = tuple(f"L_out[{node}]" for node in tray_nodes)
    reboiler_liquid_flow = "L_out[partial_reboiler_to_bottoms_sump]"
    for node, flow_name in zip(tray_nodes, liquid_flow_names):
        add_unknown(
            flow_name,
            "liquid_flow",
            node,
            "lbmol_per_h",
            f"liquid_hydraulics[{node}]",
        )
    add_unknown(
        reboiler_liquid_flow,
        "liquid_flow",
        reboiler,
        "lbmol_per_h",
        None,
    )

    vapor_sources = (*tray_nodes, reboiler)
    vapor_flow_names = tuple(f"V_out[{node}]" for node in vapor_sources)
    for node, flow_name in zip(vapor_sources, vapor_flow_names):
        add_unknown(
            flow_name,
            "vapor_flow",
            node,
            "lbmol_per_h",
            f"vapor_pressure_drop[{node}]",
        )

    for name, owner, closure in (
        ("D", drum, "spec_drum_level"),
        ("B", sump, "spec_sump_level"),
        ("Q_C", drum, "spec_top_pressure"),
        ("Q_R", reboiler, "spec_bottoms_propane"),
    ):
        add_unknown(
            name,
            "manipulated_variable",
            owner,
            "BTU_per_h" if name.startswith("Q_") else "lbmol_per_h",
            closure,
        )

    reflux_flow = "R_fixed"
    feed_terms = tuple(f"F[{node}]" for node in tray_nodes)
    for node_index, node in enumerate(all_nodes):
        for component in components:
            dependencies: list[str] = []
            if node == drum:
                dependencies.extend(
                    (
                        "V_out[tray_" + stages[0] + "]",
                        *(y_name(tray_nodes[0], comp) for comp in independent),
                        reflux_flow,
                        "D",
                        *(x_name(drum, comp) for comp in independent),
                    )
                )
            elif node in tray_nodes:
                tray_index = tray_nodes.index(node)
                if tray_index == 0:
                    dependencies.extend((reflux_flow, *(x_name(drum, comp) for comp in independent)))
                else:
                    above = tray_nodes[tray_index - 1]
                    dependencies.extend(
                        (f"L_out[{above}]", *(x_name(above, comp) for comp in independent))
                    )
                dependencies.extend(
                    (f"L_out[{node}]", *(x_name(node, comp) for comp in independent))
                )
                below = reboiler if tray_index == len(tray_nodes) - 1 else tray_nodes[tray_index + 1]
                dependencies.extend(
                    (f"V_out[{below}]", *(y_name(below, comp) for comp in independent))
                )
                dependencies.extend(
                    (f"V_out[{node}]", *(y_name(node, comp) for comp in independent))
                )
                dependencies.append(feed_terms[tray_index])
            elif node == reboiler:
                dependencies.extend(
                    (
                        f"L_out[{tray_nodes[-1]}]",
                        *(x_name(tray_nodes[-1], comp) for comp in independent),
                        reboiler_liquid_flow,
                        *(x_name(reboiler, comp) for comp in independent),
                        f"V_out[{reboiler}]",
                        *(y_name(reboiler, comp) for comp in independent),
                    )
                )
            else:
                dependencies.extend(
                    (
                        reboiler_liquid_flow,
                        *(x_name(reboiler, comp) for comp in independent),
                        "B",
                        *(x_name(sump, comp) for comp in independent),
                    )
                )
            add_residual(
                f"component_balance[{node},{component}]",
                "steady_component_balance",
                node,
                "lbmol_per_h",
                dependencies,
            )

        energy_dependencies = [
            *phase_dependencies(node if node != sump else reboiler),
        ]
        if node == drum:
            energy_dependencies.extend(
                (
                    "V_out[tray_" + stages[0] + "]",
                    *phase_dependencies(tray_nodes[0]),
                    reflux_flow,
                    "D",
                    "Q_C",
                )
            )
        elif node in tray_nodes:
            tray_index = tray_nodes.index(node)
            energy_dependencies.extend((f"L_out[{node}]", f"V_out[{node}]"))
            if tray_index == 0:
                energy_dependencies.extend(
                    (reflux_flow, *phase_dependencies(drum))
                )
            else:
                above = tray_nodes[tray_index - 1]
                energy_dependencies.extend(
                    (f"L_out[{above}]", *phase_dependencies(above))
                )
            below = (
                reboiler
                if tray_index == len(tray_nodes) - 1
                else tray_nodes[tray_index + 1]
            )
            energy_dependencies.extend(
                (f"V_out[{below}]", *phase_dependencies(below))
            )
            energy_dependencies.append(feed_terms[tray_index])
        elif node == reboiler:
            energy_dependencies.extend(
                (
                    f"L_out[{tray_nodes[-1]}]",
                    *phase_dependencies(tray_nodes[-1]),
                    f"V_out[{reboiler}]",
                    "Q_R",
                )
            )
        else:
            energy_dependencies.extend(("B",))
        add_residual(
            f"energy_balance[{node}]",
            "steady_energy_balance",
            node,
            "BTU_per_h",
            energy_dependencies,
        )

    for node, flow_name in zip(tray_nodes, liquid_flow_names):
        add_residual(
            f"liquid_hydraulics[{node}]",
            "liquid_hydraulics",
            node,
            "lbmol_per_h",
            (
                flow_name,
                f"NL[{node}]",
                f"T[{node}]",
                f"P[{node}]",
                *(x_name(node, comp) for comp in independent),
            ),
        )

    vapor_destinations = (drum, *tray_nodes[:-1], tray_nodes[-1])
    for source, destination, flow_name in zip(
        vapor_sources,
        vapor_destinations,
        vapor_flow_names,
    ):
        add_residual(
            f"vapor_pressure_drop[{source}]",
            "vapor_pressure_drop",
            source,
            "psia",
            (
                flow_name,
                f"P[{source}]",
                f"P[{destination}]",
                f"T[{source}]",
                f"NL[{source}]",
                *(x_name(source, comp) for comp in independent),
                *(y_name(source, comp) for comp in independent),
            ),
        )

    add_residual(
        "sump_pressure_equal_reboiler",
        "terminal_pressure_coupling",
        sump,
        "psia",
        (f"P[{sump}]", f"P[{reboiler}]"),
    )
    add_residual(
        "spec_top_pressure",
        "operating_specification",
        drum,
        "psia",
        (f"P[{drum}]",),
    )
    add_residual(
        "spec_bottoms_propane",
        "operating_specification",
        sump,
        "mole_fraction",
        (x_name(sump, independent[0]),),
    )
    add_residual(
        "spec_drum_level",
        "operating_specification",
        drum,
        "ft3",
        (
            f"T[{drum}]",
            f"P[{drum}]",
            f"NL[{drum}]",
            *(x_name(drum, comp) for comp in independent),
        ),
    )
    add_residual(
        "spec_sump_level",
        "operating_specification",
        sump,
        "ft3",
        (
            f"T[{sump}]",
            f"P[{sump}]",
            f"NL[{sump}]",
            *(x_name(sump, comp) for comp in independent),
        ),
    )

    return DirectSteadyStateRegistry(
        component_names=components,
        active_stage_ids=stages,
        unknowns=tuple(unknowns),
        residuals=tuple(residuals),
        deliberate_eliminations=(
            "empty total-condenser placeholder",
            f"last liquid and vapor mole fractions reconstructed as 1-sum(first {len(independent)})",
            (
                "feed phase split eliminated from conserved total balances; "
                "external feed component and enthalpy rates enter unchanged"
            ),
            "controller dynamic states replaced by four steady operating specifications",
        ),
    )


def combine_reboiler_and_sump_registry(
    registry: DirectSteadyStateRegistry,
) -> DirectSteadyStateRegistry:
    """Select one conserved bottom control volume without inventing an outlet law."""
    reboiler = "partial_reboiler"
    sump = "bottoms_sump"
    liquid_outlet = "L_out[partial_reboiler_to_bottoms_sump]"
    sump_unknown_prefixes = (
        f"N[{sump},",
        f"U[{sump}]",
        f"T[{sump}]",
        f"P[{sump}]",
        f"NL[{sump}]",
        f"x[{sump},",
    )

    def is_sump_unknown(name: str) -> bool:
        return any(name.startswith(prefix) for prefix in sump_unknown_prefixes)

    unknowns: list[UnknownEntry] = []
    for entry in registry.unknowns:
        if is_sump_unknown(entry.name) or entry.name == liquid_outlet:
            continue
        if entry.name in {"B", "Q_R"}:
            entry = UnknownEntry(
                name=entry.name,
                block=entry.block,
                owner="combined_reboiler_sump",
                units=entry.units,
                closure_residual=entry.closure_residual,
            )
        unknowns.append(entry)

    remove_residual_prefixes = (
        f"component_closure[{sump},",
        f"energy_closure[{sump}]",
        f"component_balance[{sump},",
        f"energy_balance[{sump}]",
    )

    def replace_sump_dependency(dependency: str) -> str:
        replacements = {
            f"T[{sump}]": f"T[{reboiler}]",
            f"P[{sump}]": f"P[{reboiler}]",
            f"NL[{sump}]": f"NL[{reboiler}]",
        }
        if dependency in replacements:
            return replacements[dependency]
        if dependency.startswith(f"x[{sump},"):
            return dependency.replace(f"x[{sump},", f"x[{reboiler},", 1)
        return dependency

    reboiler_x = tuple(
        entry.name
        for entry in unknowns
        if entry.name.startswith(f"x[{reboiler},")
    )
    residuals: list[ResidualEntry] = []
    for entry in registry.residuals:
        if entry.name == "sump_pressure_equal_reboiler" or any(
            entry.name.startswith(prefix) for prefix in remove_residual_prefixes
        ):
            continue
        dependencies = [
            replace_sump_dependency(dependency)
            for dependency in entry.dependencies
            if dependency != liquid_outlet
        ]
        owner = entry.owner
        if entry.name.startswith(f"component_balance[{reboiler},"):
            dependencies.extend(("B", *reboiler_x))
            owner = "combined_reboiler_sump"
        elif entry.name == f"energy_balance[{reboiler}]":
            dependencies.append("B")
            owner = "combined_reboiler_sump"
        elif entry.name in {"spec_bottoms_propane", "spec_sump_level"}:
            owner = "combined_reboiler_sump"
        residuals.append(
            ResidualEntry(
                name=entry.name,
                block=entry.block,
                owner=owner,
                units=entry.units,
                dependencies=tuple(dict.fromkeys(dependencies)),
            )
        )

    return DirectSteadyStateRegistry(
        component_names=registry.component_names,
        active_stage_ids=registry.active_stage_ids,
        unknowns=tuple(unknowns),
        residuals=tuple(residuals),
        deliberate_eliminations=(
            *registry.deliberate_eliminations,
            (
                "partial-reboiler vapor and liquid-only sump combined into one "
                "conserved bottom control volume"
            ),
            (
                "internal reboiler-to-sump liquid transfer eliminated because "
                "it crosses no boundary of the combined control volume"
            ),
        ),
    )


def structural_pattern(registry: DirectSteadyStateRegistry) -> csr_matrix:
    unknown_index = {
        entry.name: idx for idx, entry in enumerate(registry.unknowns)
    }
    rows: list[int] = []
    columns: list[int] = []
    for row_index, residual in enumerate(registry.residuals):
        for dependency in residual.dependencies:
            column_index = unknown_index.get(dependency)
            if column_index is None:
                continue
            rows.append(row_index)
            columns.append(column_index)
    data = np.ones(len(rows), dtype=np.int8)
    return csr_matrix(
        (data, (rows, columns)),
        shape=(len(registry.residuals), len(registry.unknowns)),
    )


def _deterministic_bipartite_matching(
    pattern: csr_matrix,
) -> tuple[np.ndarray, np.ndarray]:
    """Return row-to-column and column-to-row maximum-cardinality matches."""
    matrix = pattern.tocsr()
    row_count, column_count = matrix.shape
    column_to_row = np.full(column_count, -1, dtype=int)

    def augment(row: int, seen_columns: np.ndarray) -> bool:
        start = int(matrix.indptr[row])
        stop = int(matrix.indptr[row + 1])
        for column in matrix.indices[start:stop]:
            column_index = int(column)
            if seen_columns[column_index]:
                continue
            seen_columns[column_index] = True
            prior_row = int(column_to_row[column_index])
            if prior_row < 0 or augment(prior_row, seen_columns):
                column_to_row[column_index] = row
                return True
        return False

    for row in range(row_count):
        augment(row, np.zeros(column_count, dtype=bool))

    row_to_column = np.full(row_count, -1, dtype=int)
    for column, row in enumerate(column_to_row):
        if row >= 0:
            row_to_column[int(row)] = int(column)
    return row_to_column, column_to_row


def audit_registry_structure(
    registry: DirectSteadyStateRegistry,
) -> RegistryStructureAudit:
    pattern = structural_pattern(registry)
    unknown_names = tuple(entry.name for entry in registry.unknowns)
    residual_names = tuple(entry.name for entry in registry.residuals)
    duplicate_unknowns = _unique_names(unknown_names)
    duplicate_residuals = _unique_names(residual_names)
    row_counts = np.asarray(pattern.getnnz(axis=1), dtype=int)
    column_counts = np.asarray(pattern.getnnz(axis=0), dtype=int)
    empty_rows = tuple(
        residual_names[idx] for idx in np.flatnonzero(row_counts == 0)
    )
    empty_columns = tuple(
        unknown_names[idx] for idx in np.flatnonzero(column_counts == 0)
    )

    row_match, column_match = _deterministic_bipartite_matching(pattern)
    structural_rank = int(np.count_nonzero(row_match >= 0))
    unmatched_unknowns = tuple(
        unknown_names[idx] for idx in np.flatnonzero(column_match < 0)
    )
    unmatched_residuals = tuple(
        residual_names[idx] for idx in np.flatnonzero(row_match < 0)
    )
    missing_owners = tuple(
        entry.name
        for entry in registry.unknowns
        if entry.closure_residual is None
    )
    unknown_count = len(registry.unknowns)
    residual_count = len(registry.residuals)
    square = unknown_count == residual_count
    nullity = max(unknown_count - structural_rank, 0)
    passed = bool(
        square
        and structural_rank == unknown_count
        and not empty_rows
        and not empty_columns
        and not missing_owners
        and not duplicate_unknowns
        and not duplicate_residuals
    )
    return RegistryStructureAudit(
        unknown_count=unknown_count,
        residual_count=residual_count,
        equation_count_difference=unknown_count - residual_count,
        square=square,
        structural_rank=structural_rank,
        structural_nullity=nullity,
        structurally_empty_rows=empty_rows,
        structurally_empty_columns=empty_columns,
        unmatched_unknowns=unmatched_unknowns,
        unmatched_residuals=unmatched_residuals,
        missing_closure_owners=missing_owners,
        duplicate_unknown_names=duplicate_unknowns,
        duplicate_residual_names=duplicate_residuals,
        unknown_counts_by_block=_block_counts(registry.unknowns),
        residual_counts_by_block=_block_counts(registry.residuals),
        pass_gate=passed,
    )
