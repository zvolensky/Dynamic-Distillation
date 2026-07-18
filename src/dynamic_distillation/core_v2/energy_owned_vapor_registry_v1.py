"""Structural registry for the DD-083 energy-owned vapor-flow architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.sparse import csr_matrix


VOLUME_IDS = (
    "reflux_drum",
    "rectifying_tray",
    "feed_tray",
    "stripping_tray",
    "combined_reboiler_sump",
)
EQUILIBRIUM_VOLUME_IDS = VOLUME_IDS[1:]
HYDRAULIC_VOLUME_IDS = VOLUME_IDS[1:4]
TERMINAL_VOLUME_IDS = (VOLUME_IDS[0], VOLUME_IDS[-1])

LIQUID_LINKS = (
    ("reflux_drum", "rectifying_tray", "R"),
    ("rectifying_tray", "feed_tray", "L[rectifying_tray]"),
    ("feed_tray", "stripping_tray", "L[feed_tray]"),
    (
        "stripping_tray",
        "combined_reboiler_sump",
        "L[stripping_tray]",
    ),
)
VAPOR_LINKS = (
    (
        "combined_reboiler_sump",
        "stripping_tray",
        "V[combined_reboiler_sump->stripping_tray]",
    ),
    (
        "stripping_tray",
        "feed_tray",
        "V[stripping_tray->feed_tray]",
    ),
    (
        "feed_tray",
        "rectifying_tray",
        "V[feed_tray->rectifying_tray]",
    ),
    (
        "rectifying_tray",
        "reflux_drum",
        "V[rectifying_tray->reflux_drum]",
    ),
)


@dataclass(frozen=True)
class StructuralEntry:
    name: str
    block: str
    owner: str
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class BalanceContribution:
    family: str
    stream: str
    component: str | None
    coefficient: int


@dataclass(frozen=True)
class EnergyOwnedVaporRegistry:
    component_names: tuple[str, ...]
    unknowns: tuple[StructuralEntry, ...]
    residuals: tuple[StructuralEntry, ...]
    external_parameters: tuple[str, ...]
    contributions: tuple[BalanceContribution, ...]


@dataclass(frozen=True)
class RegistryAudit:
    unknown_count: int
    residual_count: int
    structural_rank: int
    structural_nullity: int
    unmatched_unknowns: tuple[str, ...]
    unmatched_residuals: tuple[str, ...]
    unregistered_dependencies: tuple[str, ...]
    imported_profile_dependencies: tuple[str, ...]
    full_fugacity_row_count: int
    vapor_unknown_count: int
    component_conservation_passed: bool
    energy_conservation_passed: bool
    pass_gate: bool


def _validated_components(component_names: Sequence[str]) -> tuple[str, ...]:
    components = tuple(str(value).strip() for value in component_names)
    if len(components) < 2:
        raise ValueError("DD-083 requires at least two components")
    if any(not value for value in components):
        raise ValueError("component names must be nonempty")
    if len(set(components)) != len(components):
        raise ValueError("component names must be unique")
    return components


def _phase_coordinates(
    components: tuple[str, ...],
    phase: str,
    volume: str,
) -> tuple[str, ...]:
    return tuple(
        f"{phase}[{volume},{component}]" for component in components[:-1]
    )


def _phase_state_dependencies(
    components: tuple[str, ...],
    phase: str,
    volume: str,
) -> tuple[str, ...]:
    coordinate_phase = {
        "liquid": "x",
        "vapor": "y",
    }.get(phase, phase)
    return (
        f"T[{volume}]",
        f"P[{volume}]",
        *_phase_coordinates(components, coordinate_phase, volume),
    )


def build_energy_owned_vapor_registry(
    component_names: Sequence[str],
) -> EnergyOwnedVaporRegistry:
    """Build the structural-only 5-volume steady MESH registry.

    The four vapor links are independent algebraic unknowns. Four full
    saturation conditions, one per equilibrium outlet, close the degrees of
    freedom that prescribed vapor traffic occupied in DD-081/DD-082.
    """
    components = _validated_components(component_names)
    unknowns: list[StructuralEntry] = []
    residuals: list[StructuralEntry] = []
    contributions: list[BalanceContribution] = []

    for volume in VOLUME_IDS:
        unknowns.append(StructuralEntry(f"NL[{volume}]", "liquid_amount", volume))
        for name in _phase_coordinates(components, "x", volume):
            unknowns.append(StructuralEntry(name, "liquid_composition", volume))
        unknowns.append(StructuralEntry(f"T[{volume}]", "temperature", volume))
    for volume in EQUILIBRIUM_VOLUME_IDS:
        for name in _phase_coordinates(components, "y", volume):
            unknowns.append(StructuralEntry(name, "vapor_composition", volume))
    for volume in HYDRAULIC_VOLUME_IDS:
        unknowns.append(
            StructuralEntry(f"L[{volume}]", "francis_liquid_flow", volume)
        )
    for source, destination, symbol in VAPOR_LINKS:
        unknowns.append(
            StructuralEntry(
                symbol,
                "energy_owned_vapor_flow",
                f"{source}->{destination}",
            )
        )
    unknowns.extend(
        (
            StructuralEntry("D", "terminal_product_flow", "reflux_drum"),
            StructuralEntry(
                "B",
                "terminal_product_flow",
                "combined_reboiler_sump",
            ),
        )
    )

    for volume in EQUILIBRIUM_VOLUME_IDS:
        dependencies = (
            f"T[{volume}]",
            f"P[{volume}]",
            *_phase_coordinates(components, "x", volume),
            *_phase_coordinates(components, "y", volume),
        )
        for component in components:
            residuals.append(
                StructuralEntry(
                    f"phase_fugacity[{volume},{component}]",
                    "full_phase_equilibrium",
                    volume,
                    dependencies,
                )
            )

    internal_links = tuple(
        (source, destination, symbol, "liquid")
        for source, destination, symbol in LIQUID_LINKS
    ) + tuple(
        (source, destination, symbol, "vapor")
        for source, destination, symbol in VAPOR_LINKS
    )
    for volume in VOLUME_IDS:
        for component in components:
            dependencies: list[str] = []
            for source, destination, symbol, phase in internal_links:
                if volume not in {source, destination}:
                    continue
                dependencies.append(symbol)
                coordinate_phase = "x" if phase == "liquid" else "y"
                dependencies.extend(
                    _phase_coordinates(components, coordinate_phase, source)
                )
                coefficient = -1 if volume == source else 1
                contributions.append(
                    BalanceContribution(
                        "component",
                        symbol,
                        component,
                        coefficient,
                    )
                )
            if volume == "feed_tray":
                dependencies.append(f"F_component[{component}]")
            if volume == "reflux_drum":
                dependencies.extend(("D", *_phase_coordinates(components, "x", volume)))
            if volume == "combined_reboiler_sump":
                dependencies.extend(("B", *_phase_coordinates(components, "x", volume)))
            residuals.append(
                StructuralEntry(
                    f"component_balance[{volume},{component}]",
                    "component_balance",
                    volume,
                    tuple(dict.fromkeys(dependencies)),
                )
            )

        energy_dependencies: list[str] = []
        for source, destination, symbol, phase in internal_links:
            if volume not in {source, destination}:
                continue
            energy_dependencies.append(symbol)
            energy_dependencies.extend(
                _phase_state_dependencies(components, phase, source)
            )
            contributions.append(
                BalanceContribution(
                    "energy",
                    symbol,
                    None,
                    -1 if volume == source else 1,
                )
            )
        if volume == "feed_tray":
            energy_dependencies.append("H_feed")
        if volume == "reflux_drum":
            energy_dependencies.extend(
                ("D", "Q_C", *_phase_state_dependencies(components, "x", volume))
            )
        if volume == "combined_reboiler_sump":
            energy_dependencies.extend(
                ("B", "Q_R", *_phase_state_dependencies(components, "x", volume))
            )
        residuals.append(
            StructuralEntry(
                f"energy_balance[{volume}]",
                "energy_balance",
                volume,
                tuple(dict.fromkeys(energy_dependencies)),
            )
        )

    for volume in HYDRAULIC_VOLUME_IDS:
        residuals.append(
            StructuralEntry(
                f"francis_hydraulics[{volume}]",
                "francis_hydraulics",
                volume,
                (
                    f"L[{volume}]",
                    f"NL[{volume}]",
                    f"T[{volume}]",
                    f"P[{volume}]",
                    *_phase_coordinates(components, "x", volume),
                    f"francis_geometry[{volume}]",
                ),
            )
        )
    for volume in TERMINAL_VOLUME_IDS:
        residuals.append(
            StructuralEntry(
                f"terminal_level[{volume}]",
                "terminal_level_specification",
                volume,
                (f"NL[{volume}]", f"NL_target[{volume}]"),
            )
        )

    external = (
        *(f"P[{volume}]" for volume in VOLUME_IDS),
        "R",
        *(f"F_component[{component}]" for component in components),
        "H_feed",
        "Q_C",
        "Q_R",
        *(f"francis_geometry[{volume}]" for volume in HYDRAULIC_VOLUME_IDS),
        *(f"NL_target[{volume}]" for volume in TERMINAL_VOLUME_IDS),
    )
    return EnergyOwnedVaporRegistry(
        component_names=components,
        unknowns=tuple(unknowns),
        residuals=tuple(residuals),
        external_parameters=tuple(external),
        contributions=tuple(contributions),
    )


def _structural_pattern(registry: EnergyOwnedVaporRegistry) -> csr_matrix:
    index = {entry.name: position for position, entry in enumerate(registry.unknowns)}
    row_index: list[int] = []
    column_index: list[int] = []
    for row, residual in enumerate(registry.residuals):
        for dependency in residual.dependencies:
            if dependency in index:
                row_index.append(row)
                column_index.append(index[dependency])
    return csr_matrix(
        (
            np.ones(len(row_index), dtype=np.int8),
            (row_index, column_index),
        ),
        shape=(len(registry.residuals), len(registry.unknowns)),
    )


def _matching(pattern: csr_matrix) -> tuple[np.ndarray, np.ndarray]:
    matrix = pattern.tocsr()
    row_count, column_count = matrix.shape
    column_to_row = np.full(column_count, -1, dtype=int)

    def augment(row: int, seen: np.ndarray) -> bool:
        start = int(matrix.indptr[row])
        stop = int(matrix.indptr[row + 1])
        for column in matrix.indices[start:stop]:
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


def _conservation_passes(
    contributions: Iterable[BalanceContribution],
    *,
    family: str,
    streams: Iterable[str],
    components: Iterable[str | None],
) -> bool:
    records = tuple(contributions)
    for stream in streams:
        for component in components:
            coefficients = tuple(
                record.coefficient
                for record in records
                if record.family == family
                and record.stream == stream
                and record.component == component
            )
            if len(coefficients) != 2 or sum(coefficients) != 0:
                return False
    return True


def audit_energy_owned_vapor_registry(
    registry: EnergyOwnedVaporRegistry,
) -> RegistryAudit:
    pattern = _structural_pattern(registry)
    row_match, column_match = _matching(pattern)
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
    rank = int(np.count_nonzero(row_match >= 0))
    internal_symbols = tuple(
        symbol for _, _, symbol in (*LIQUID_LINKS, *VAPOR_LINKS)
    )
    component_passed = _conservation_passes(
        registry.contributions,
        family="component",
        streams=internal_symbols,
        components=registry.component_names,
    )
    energy_passed = _conservation_passes(
        registry.contributions,
        family="energy",
        streams=internal_symbols,
        components=(None,),
    )
    full_fugacity_count = sum(
        entry.block == "full_phase_equilibrium" for entry in registry.residuals
    )
    vapor_count = sum(
        entry.block == "energy_owned_vapor_flow" for entry in registry.unknowns
    )
    passed = bool(
        len(unknown_names) == len(residual_names)
        and rank == len(unknown_names)
        and not unregistered
        and not imported
        and component_passed
        and energy_passed
        and full_fugacity_count
        == len(EQUILIBRIUM_VOLUME_IDS) * len(registry.component_names)
        and vapor_count == len(VAPOR_LINKS)
    )
    return RegistryAudit(
        unknown_count=len(unknown_names),
        residual_count=len(residual_names),
        structural_rank=rank,
        structural_nullity=max(len(unknown_names) - rank, 0),
        unmatched_unknowns=tuple(
            unknown_names[index] for index in np.flatnonzero(column_match < 0)
        ),
        unmatched_residuals=tuple(
            residual_names[index] for index in np.flatnonzero(row_match < 0)
        ),
        unregistered_dependencies=unregistered,
        imported_profile_dependencies=imported,
        full_fugacity_row_count=full_fugacity_count,
        vapor_unknown_count=vapor_count,
        component_conservation_passed=component_passed,
        energy_conservation_passed=energy_passed,
        pass_gate=passed,
    )


__all__ = [
    "EQUILIBRIUM_VOLUME_IDS",
    "HYDRAULIC_VOLUME_IDS",
    "LIQUID_LINKS",
    "TERMINAL_VOLUME_IDS",
    "VAPOR_LINKS",
    "VOLUME_IDS",
    "EnergyOwnedVaporRegistry",
    "RegistryAudit",
    "audit_energy_owned_vapor_registry",
    "build_energy_owned_vapor_registry",
]
